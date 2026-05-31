"""Regression tests for R12 FLATTEN_REQUEST broker-cutoff guard wiring."""

from __future__ import annotations

import importlib
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# Ensure canonical Spyder imports resolve to this repository in CI.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_PACKAGE_ROOT = _REPO_ROOT / "Spyder"
for _path in (_REPO_ROOT, _PACKAGE_ROOT):
    _path_str = str(_path)
    if _path_str not in sys.path:
        sys.path.insert(0, _path_str)


def _is_local_spyder_package(module: object) -> bool:
    if not hasattr(module, "__path__"):
        return False
    package_root = str(_PACKAGE_ROOT)
    module_file = str(getattr(module, "__file__", "") or "")
    if module_file.startswith(package_root):
        return True
    module_paths = [str(path) for path in getattr(module, "__path__", [])]
    return any(path.startswith(package_root) for path in module_paths)


def _ensure_local_spyder_package() -> None:
    existing_spyder = sys.modules.get("Spyder")
    if existing_spyder is not None and _is_local_spyder_package(existing_spyder):
        return

    sys.modules.pop("Spyder", None)
    importlib.invalidate_caches()

    spec = importlib.util.spec_from_file_location(
        "Spyder",
        _PACKAGE_ROOT / "__init__.py",
        submodule_search_locations=[str(_PACKAGE_ROOT)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load Spyder package from {_PACKAGE_ROOT}")

    module = importlib.util.module_from_spec(spec)
    sys.modules["Spyder"] = module
    spec.loader.exec_module(module)


_ensure_local_spyder_package()

from Spyder.SpyderA_Core.SpyderA05_EventManager import EventType
from Spyder.SpyderA_Core.SpyderA05_EventManager import EventManager
from Spyder.SpyderH_Storage.SpyderH05_TradingSessionDB import TradingSessionDB
from Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor import SessionSupervisor


class _FakeEventManager:
    def __init__(self) -> None:
        self.is_running = True
        self._next_id = "sub-1"
        self.subscribe = MagicMock(return_value=self._next_id)
        self.unsubscribe = MagicMock()
        self.start = MagicMock()


class _BrokerWithoutVerified:
    def __init__(self) -> None:
        self._positions = [
            {"symbol": "SPY_20260504C00520000", "quantity": -1},
            {"symbol": "SPY", "quantity": -100},
            {"symbol": "SPY_20260504P00515000", "quantity": 2},
        ]
        self.close_position = MagicMock(return_value={"status": "ok"})

    def get_positions(self):
        return self._positions


class TestFlattenRequestSubscription:
    def test_start_event_manager_subscribes_to_flatten_request(self):
        supervisor = SessionSupervisor(mode="paper", dry_run=True, skip_orphan_sweep=True)
        fake_em = _FakeEventManager()

        with patch(
            "Spyder.SpyderA_Core.SpyderA05_EventManager.get_event_manager",
            return_value=fake_em,
        ):
            ok = supervisor._start_event_manager()

        assert ok is True
        fake_em.subscribe.assert_called_once()
        args = fake_em.subscribe.call_args.args
        assert args[0] == EventType.FLATTEN_REQUEST
        assert args[1] == supervisor._on_flatten_request
        assert supervisor._flatten_request_handler_id == "sub-1"


class TestFlattenRequestRouting:
    def test_broker_cutoff_event_routes_to_targeted_short_option_flatten(self):
        supervisor = SessionSupervisor(mode="paper", dry_run=True, skip_orphan_sweep=True)
        supervisor._flatten_positions = MagicMock()
        supervisor._flatten_at_risk_short_options = MagicMock(return_value=1)

        event = SimpleNamespace(
            data={
                "type": "broker_cutoff_flatten_guard",
                "reason": "broker_cutoff_protection",
            }
        )
        supervisor._on_flatten_request(event)

        supervisor._flatten_at_risk_short_options.assert_called_once_with(
            reason="broker_cutoff_protection"
        )
        supervisor._flatten_positions.assert_not_called()

    def test_non_guard_event_routes_to_full_flatten(self):
        supervisor = SessionSupervisor(mode="paper", dry_run=True, skip_orphan_sweep=True)
        supervisor._flatten_positions = MagicMock()
        supervisor._flatten_at_risk_short_options = MagicMock(return_value=0)

        event = SimpleNamespace(data={"type": "risk_stale", "reason": "data_stale"})
        supervisor._on_flatten_request(event)

        supervisor._flatten_positions.assert_called_once()
        supervisor._flatten_at_risk_short_options.assert_not_called()

    def test_strategy_group_flatten_routes_to_targeted_strategy_close(self):
        supervisor = SessionSupervisor(mode="paper", dry_run=True, skip_orphan_sweep=True)
        supervisor._flatten_positions = MagicMock(return_value=4)
        supervisor._flatten_at_risk_short_options = MagicMock(return_value=0)

        event = SimpleNamespace(
            data={
                "type": "strategy_group_flatten",
                "reason": "paper_orphan_carryover_strategy",
                "strategy_id": "iron_condor",
            }
        )
        supervisor._on_flatten_request(event)

        supervisor._flatten_positions.assert_called_once_with(
            reason="paper_orphan_carryover_strategy",
            strategy_id="iron_condor",
        )
        supervisor._flatten_at_risk_short_options.assert_not_called()


class TestTargetedShortOptionFlatten:
    def test_flatten_at_risk_short_options_closes_only_short_options(self):
        supervisor = SessionSupervisor(mode="paper", dry_run=True, skip_orphan_sweep=True)
        supervisor.broker = _BrokerWithoutVerified()

        closed = supervisor._flatten_at_risk_short_options(reason="broker_cutoff_protection")

        assert closed == 1
        supervisor.broker.close_position.assert_called_once_with(
            "SPY_20260504C00520000",
            urgency="IMMEDIATE",
            reason="broker_cutoff_protection",
            position_quantity=-1,
        )

    def test_flatten_positions_can_filter_by_strategy_id(self):
        supervisor = SessionSupervisor(mode="paper", dry_run=True, skip_orphan_sweep=True)
        supervisor._get_positions_for_flatten = MagicMock(
            return_value=[
                {"symbol": "SPY260618P00690000", "quantity": 1, "strategy_id": "iron_condor"},
                {"symbol": "SPY260618P00700000", "quantity": -1, "strategy_id": "iron_condor"},
                {"symbol": "SPY", "quantity": 10, "strategy_id": "pivot_mean_reversion"},
            ]
        )
        supervisor._submit_flatten_close = MagicMock(return_value={"status": "ok", "order": {"id": "ORD-1"}})

        closed = supervisor._flatten_positions(
            reason="paper_orphan_carryover_strategy",
            strategy_id="iron_condor",
        )

        assert closed == 2
        assert supervisor._submit_flatten_close.call_args_list[0].args == (
            "SPY260618P00690000",
            1,
        )
        assert supervisor._submit_flatten_close.call_args_list[0].kwargs == {
            "reason": "paper_orphan_carryover_strategy",
        }
        assert supervisor._submit_flatten_close.call_args_list[1].args == (
            "SPY260618P00700000",
            -1,
        )
        assert supervisor._submit_flatten_close.call_args_list[1].kwargs == {
            "reason": "paper_orphan_carryover_strategy",
        }

    def test_flatten_positions_strategy_filter_matches_strategy_alias_tokens(self):
        supervisor = SessionSupervisor(mode="paper", dry_run=True, skip_orphan_sweep=True)
        supervisor._get_positions_for_flatten = MagicMock(
            return_value=[
                {
                    "symbol": "SPY260618P00690000",
                    "quantity": 1,
                    "strategy_id": "ZeroDTEIronCondor",
                },
                {
                    "symbol": "SPY260618P00700000",
                    "quantity": -1,
                    "strategy_id": "zero_dte_iron_condor",
                },
                {
                    "symbol": "SPY260618C00715000",
                    "quantity": -1,
                    "strategy": "iron_condor_live_adapter",
                },
                {
                    "symbol": "SPY",
                    "quantity": 10,
                    "strategy_id": "pivot_mean_reversion",
                },
            ]
        )
        supervisor._submit_flatten_close = MagicMock(return_value={"status": "ok", "order": {"id": "ORD-2"}})

        closed = supervisor._flatten_positions(
            reason="paper_orphan_carryover_strategy",
            strategy_id="iron_condor",
        )

        assert closed == 3
        assert [call.args for call in supervisor._submit_flatten_close.call_args_list] == [
            ("SPY260618P00690000", 1),
            ("SPY260618P00700000", -1),
            ("SPY260618C00715000", -1),
        ]
        assert all(
            call.kwargs == {"reason": "paper_orphan_carryover_strategy"}
            for call in supervisor._submit_flatten_close.call_args_list
        )

    def test_flatten_positions_persists_verified_paper_close_and_emits_refresh(self):
        supervisor = SessionSupervisor(mode="paper", dry_run=True, skip_orphan_sweep=True)

        with TemporaryDirectory() as tmpdir:
            db = TradingSessionDB(Path(tmpdir) / "paper_positions.db")
            opened_at = datetime.fromisoformat("2026-05-26T09:51:09-04:00")
            db.upsert_position(
                position_id="paper:SPY",
                symbol="SPY",
                strategy="butterfly",
                quantity=10,
                entry_price=750.7252,
                current_price=749.16,
                unrealized_pnl=-15.65,
                status="OPEN",
                opened_at=opened_at,
            )
            # Simulate duplicate-orphan OPEN row for same symbol from a different
            # execution path; manual flatten should clear it before writing CLOSED.
            db.upsert_position(
                position_id="emergency_stop:SPY",
                symbol="SPY",
                strategy="butterfly",
                quantity=10,
                entry_price=750.7252,
                current_price=749.16,
                unrealized_pnl=-15.65,
                status="OPEN",
                opened_at=opened_at,
            )

            supervisor.engine = SimpleNamespace(
                _session_db=db,
                active_positions={"SPY": {"quantity": 10}},
                _active_positions_lock=threading.Lock(),
            )
            supervisor.broker = SimpleNamespace(close_position_verified=MagicMock())
            supervisor.em = MagicMock()
            supervisor._get_positions_for_flatten = MagicMock(
                return_value=[
                    {
                        "position_id": "paper:SPY",
                        "symbol": "SPY",
                        "strategy": "butterfly",
                        "quantity": 10,
                        "entry_price": 750.7252,
                        "current_price": 749.16,
                        "unrealized_pnl": -15.65,
                        "status": "OPEN",
                        "opened_at": opened_at.isoformat(),
                    }
                ]
            )
            supervisor._submit_flatten_close = MagicMock(
                return_value={
                    "status": "verified",
                    "order": {"order": {"id": "PAPER-000001"}},
                    "fill": {"order": {"status": "filled", "avg_fill_price": 749.16}},
                }
            )

            closed = supervisor._flatten_positions(
                reason="manual_close_dashboard",
                symbols=["SPY"],
            )

            assert closed == 1
            assert supervisor.engine.active_positions == {}
            assert db.get_open_positions() == []

            with db._connect() as conn:
                row = conn.execute(
                    "SELECT status, quantity, current_price, unrealized_pnl, realized_pnl FROM positions WHERE position_id = ?",
                    ("paper:SPY",),
                ).fetchone()
                duplicate_open = conn.execute(
                    "SELECT COUNT(*) AS count FROM positions WHERE position_id = ? AND status = 'OPEN'",
                    ("emergency_stop:SPY",),
                ).fetchone()
                trades = conn.execute(
                    "SELECT symbol, trade_type, side, quantity, notes FROM trades ORDER BY timestamp",
                ).fetchall()

            assert row["status"] == "CLOSED"
            assert row["quantity"] == 0
            assert row["current_price"] == 749.16
            assert row["unrealized_pnl"] == 0.0
            assert row["realized_pnl"] < 0.0
            assert duplicate_open["count"] == 0
            assert len(trades) == 1
            assert trades[0]["symbol"] == "SPY"
            assert trades[0]["trade_type"] == "STC"
            assert trades[0]["side"] == "sell"
            assert trades[0]["quantity"] == 10
            assert trades[0]["notes"] == "paper flatten close via SessionSupervisor"
            assert supervisor.em.emit.call_count == 2
            request_call = supervisor.em.emit.call_args_list[0]
            assert request_call.args == (
                EventType.POSITION_UPDATED,
                {
                    "symbol": "SPY",
                    "strategy_id": "butterfly",
                    "strategy": "butterfly",
                    "status": "CLOSE_REQUESTED",
                    "reason": "manual_close_dashboard",
                },
            )
            assert request_call.kwargs == {"source": "R12"}
            closed_call = supervisor.em.emit.call_args_list[1]
            assert closed_call.args == (
                EventType.POSITION_UPDATED,
                {
                    "symbol": "SPY",
                    "strategy_id": "butterfly",
                    "strategy": "butterfly",
                    "status": "CLOSED",
                    "reason": "manual_close_dashboard",
                },
            )
            assert closed_call.kwargs == {"source": "R12"}


class TestFlattenSubscriptionCleanup:
    def test_stop_unsubscribes_flatten_handler(self):
        supervisor = SessionSupervisor(mode="paper", dry_run=True, skip_orphan_sweep=True)
        supervisor._running = True
        supervisor._components = []
        supervisor.em = _FakeEventManager()
        supervisor._flatten_request_handler_id = "sub-1"

        supervisor.stop(flatten=False)

        supervisor.em.unsubscribe.assert_called_once_with("sub-1")
        assert supervisor._flatten_request_handler_id is None


class TestManualCloseButterflyExpansion:
    def test_flatten_positions_expands_single_leg_manual_close_to_butterfly_family(self):
        supervisor = SessionSupervisor(mode="paper", dry_run=True, skip_orphan_sweep=True)
        supervisor.broker = SimpleNamespace(close_position_verified=MagicMock())
        supervisor.engine = SimpleNamespace(
            active_positions={
                "SPY260529C00757000": {"quantity": 70},
                "SPY260529C00758000": {"quantity": -140},
                "SPY260529C00759000": {"quantity": 70},
                "SPY260529C00760000": {"quantity": 3},
            },
            _active_positions_lock=threading.Lock(),
        )
        supervisor._persist_verified_paper_flatten_close = MagicMock()
        supervisor._get_positions_for_flatten = MagicMock(
            return_value=[
                {
                    "position_id": "paper:SPY260529C00757000",
                    "symbol": "SPY260529C00757000",
                    "strategy": "butterfly",
                    "quantity": 70,
                    "expiration": "2026-05-29",
                    "opened_at": "2026-05-29T10:53:01-04:00",
                },
                {
                    "position_id": "paper:SPY260529C00758000",
                    "symbol": "SPY260529C00758000",
                    "strategy": "butterfly",
                    "quantity": -140,
                    "expiration": "2026-05-29",
                    "opened_at": "2026-05-29T10:53:04-04:00",
                },
                {
                    "position_id": "paper:SPY260529C00759000",
                    "symbol": "SPY260529C00759000",
                    "strategy": "butterfly",
                    "quantity": 70,
                    "expiration": "2026-05-29",
                    "opened_at": "2026-05-29T10:53:06-04:00",
                },
                {
                    "position_id": "paper:SPY260529C00760000",
                    "symbol": "SPY260529C00760000",
                    "strategy": "butterfly",
                    "quantity": 3,
                    "expiration": "2026-05-29",
                    "opened_at": "2026-05-29T10:54:20-04:00",
                },
            ]
        )
        supervisor._submit_flatten_close = MagicMock(
            side_effect=[
                {"status": "verified", "order": {"order": {"id": "PAPER-1"}}},
                {"status": "verified", "order": {"order": {"id": "PAPER-2"}}},
                {"status": "verified", "order": {"order": {"id": "PAPER-3"}}},
            ]
        )

        closed = supervisor._flatten_positions(
            reason="manual_close_dashboard",
            symbols=["SPY260529C00757000"],
        )

        assert closed == 3
        assert [call.args[:2] for call in supervisor._submit_flatten_close.call_args_list] == [
            ("SPY260529C00757000", 70),
            ("SPY260529C00758000", -140),
            ("SPY260529C00759000", 70),
        ]
        assert all(
            call.kwargs == {"reason": "manual_close_dashboard"}
            for call in supervisor._submit_flatten_close.call_args_list
        )


class TestPaperCarryoverManifestSource:
    def test_manifest_positions_prefer_h05_open_rows_over_stale_engine_snapshot(self):
        supervisor = SessionSupervisor(mode="paper", dry_run=True, skip_orphan_sweep=True)

        with TemporaryDirectory() as tmpdir:
            db = TradingSessionDB(Path(tmpdir) / "paper_positions.db")
            current_opened = "2026-05-14T14:39:04-04:00"
            db.upsert_position(
                position_id="paper:SPY260613C00783500",
                symbol="SPY260613C00783500",
                strategy="iron_condor",
                quantity=-1,
                entry_price=8.5843,
                current_price=8.5843,
                status="OPEN",
                opened_at=datetime.fromisoformat(current_opened),
                expiration="2026-06-13",
                strike=783.5,
                option_type="call",
            )

            supervisor.engine = MagicMock()
            supervisor.engine._session_db = db
            supervisor.engine.get_active_positions_snapshot.return_value = [
                {
                    "position_id": "paper:SPY260613C00783500",
                    "symbol": "SPY260613C00783500",
                    "strategy": "iron_condor",
                    "quantity": -1,
                    "opened_at": "2026-05-14T13:14:08-04:00",
                }
            ]
            supervisor.position_tracker = MagicMock()
            supervisor.position_tracker.get_positions.return_value = []

            rows = supervisor._get_positions_for_paper_carryover_manifest()

        assert len(rows) == 1
        assert rows[0]["opened_at"] == current_opened


class TestFlattenRequestEventBusIntegration:
    def test_emit_flatten_request_executes_targeted_close_path(self):
        supervisor = SessionSupervisor(mode="paper", dry_run=True, skip_orphan_sweep=True)
        supervisor.broker = _BrokerWithoutVerified()

        em = EventManager(persist_events=False)
        if not em.is_running:
            em.start()

        try:
            with patch(
                "Spyder.SpyderA_Core.SpyderA05_EventManager.get_event_manager",
                return_value=em,
            ):
                assert supervisor._start_event_manager() is True

            emitted = em.emit(
                EventType.FLATTEN_REQUEST,
                {
                    "type": "broker_cutoff_flatten_guard",
                    "reason": "broker_cutoff_protection",
                },
                source="test",
            )
            assert emitted is True

            deadline = time.time() + 2.0
            while time.time() < deadline and not supervisor.broker.close_position.called:
                time.sleep(0.02)

            supervisor.broker.close_position.assert_called_once_with(
                "SPY_20260504C00520000",
                urgency="IMMEDIATE",
                reason="broker_cutoff_protection",
                position_quantity=-1,
            )
        finally:
            if supervisor._flatten_request_handler_id:
                em.unsubscribe(supervisor._flatten_request_handler_id)
                supervisor._flatten_request_handler_id = None
            em.stop()
