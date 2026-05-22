#!/usr/bin/env python3
"""Focused tests for R12 paper ExitMonitor authoritative-position wiring."""

from __future__ import annotations

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

from Spyder.SpyderA_Core.SpyderA05_EventManager import EventType
from Spyder.SpyderR_Runtime.SpyderR14_ExitMonitor import create_exit_monitor
from Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor import SessionSupervisor


def test_r12_start_exit_monitor_uses_engine_positions_for_paper(monkeypatch) -> None:
    strategy = MagicMock()
    strategy.check_exit.return_value = None

    monkeypatch.setattr(
        "Spyder.SpyderP_PortfolioMgmt.get_global_portfolio_manager",
        lambda: None,
    )
    monkeypatch.setattr(
        "Spyder.SpyderR_Runtime.SpyderR14_ExitMonitor.ExitMonitor.start",
        lambda self: True,
    )

    supervisor = SessionSupervisor(mode="paper", dry_run=True, skip_orphan_sweep=True)
    supervisor.em = SimpleNamespace()
    supervisor.orchestrator = SimpleNamespace(active_strategies={"iron_condor": strategy})
    supervisor.engine = SimpleNamespace(
        portfolio_manager=None,
        active_positions={
            "SPY260620P00500000": {
                "symbol": "SPY260620P00500000",
                "quantity": -1,
                "entry_price": 3.50,
                "current_price": 3.60,
                "strategy": "iron_condor",
            }
        },
        _is_market_open=lambda: True,
        _active_positions_lock=threading.Lock(),
    )

    supervisor._start_exit_monitor()

    assert supervisor.exit_monitor is not None

    supervisor.exit_monitor._sweep_once()

    strategy.check_exit.assert_called_once()
    position_view = strategy.check_exit.call_args.args[0]
    assert position_view.strategy_id == "iron_condor"
    assert position_view.cost_basis == 3.50
    assert position_view.current_price == 3.60
    assert supervisor.exit_monitor.portfolio_manager is None


def test_r12_start_exit_monitor_suppresses_paper_positions_after_hours(monkeypatch) -> None:
    strategy = MagicMock()
    strategy.check_exit.return_value = None

    monkeypatch.setattr(
        "Spyder.SpyderP_PortfolioMgmt.get_global_portfolio_manager",
        lambda: None,
    )
    monkeypatch.setattr(
        "Spyder.SpyderR_Runtime.SpyderR14_ExitMonitor.ExitMonitor.start",
        lambda self: True,
    )

    supervisor = SessionSupervisor(mode="paper", dry_run=True, skip_orphan_sweep=True)
    supervisor.em = SimpleNamespace()
    supervisor.orchestrator = SimpleNamespace(active_strategies={"iron_condor": strategy})
    supervisor.engine = SimpleNamespace(
        portfolio_manager=None,
        active_positions={
            "SPY260620P00500000": {
                "symbol": "SPY260620P00500000",
                "quantity": -1,
                "entry_price": 3.50,
                "current_price": 3.60,
                "strategy": "iron_condor",
            }
        },
        _is_market_open=lambda: False,
        _active_positions_lock=threading.Lock(),
    )

    supervisor._start_exit_monitor()

    assert supervisor.exit_monitor is not None

    supervisor.exit_monitor._sweep_once()

    strategy.check_exit.assert_not_called()


class _ExitEventManagerStub:
    def __init__(self) -> None:
        self.emitted: list[dict[str, object]] = []

    def emit(self, **kwargs) -> None:  # noqa: ANN003
        self.emitted.append(kwargs)


def test_exit_monitor_requests_group_flatten_for_orphaned_hydrated_paper_condor() -> None:
    event_manager = _ExitEventManagerStub()
    monitor = create_exit_monitor(
        portfolio_manager=None,
        strategy_map={},
        event_manager=event_manager,
        positions_provider=lambda: {
            "SPY260618P00690000": {
                "symbol": "SPY260618P00690000",
                "quantity": 1,
                "entry_price": 4.22,
                "current_price": 4.22,
                "unrealized_pnl": -167.21,
                "strategy_id": "iron_condor",
                "position_source": "session_db_hydration",
            }
        },
    )

    monitor._sweep_once()

    assert len(event_manager.emitted) == 2
    orphan_event = event_manager.emitted[0]
    flatten_event = event_manager.emitted[1]
    assert orphan_event["event_type"] == EventType.RISK_VIOLATION
    assert orphan_event["data"]["type"] == "ORPHAN_POSITION"
    assert flatten_event["event_type"] == EventType.FLATTEN_REQUEST
    assert flatten_event["data"] == {
        "type": "strategy_group_flatten",
        "reason": "paper_orphan_carryover_strategy",
        "strategy_id": "iron_condor",
    }


def test_exit_monitor_suppresses_close_after_group_flatten_request_for_same_hydrated_leg() -> None:
    event_manager = _ExitEventManagerStub()
    positions = {
        "SPY260618P00704000": {
            "symbol": "SPY260618P00704000",
            "quantity": -1,
            "entry_price": 4.24,
            "current_price": 3.99,
            "unrealized_pnl": 450.92,
            "strategy_id": "iron_condor",
            "position_source": "session_db_hydration",
        }
    }
    strategy = MagicMock()
    strategy.check_exit.return_value = "close"

    monitor = create_exit_monitor(
        portfolio_manager=None,
        strategy_map={},
        event_manager=event_manager,
        positions_provider=lambda: positions,
    )

    monitor._sweep_once()

    monitor.register_strategy("iron_condor", strategy)
    monitor._sweep_once()

    strategy.check_exit.assert_not_called()
    assert [event["event_type"] for event in event_manager.emitted] == [
        EventType.RISK_VIOLATION,
        EventType.FLATTEN_REQUEST,
    ]


def test_r12_flatten_positions_evicts_verified_symbol_from_engine_active_positions() -> None:
    """R12 _flatten_positions must evict each verified close from engine.active_positions.

    Without this eviction, ExitMonitor reads stale data (FillReconciler is never
    called for the flatten path) and re-dispatches duplicate close signals.
    """
    symbol = "SPY260618P00704000"

    # Minimal broker stub that returns a verified close result.
    class _VerifiedBroker:
        def close_position(self, sym, **_kw):
            return {"order": {"order": {"id": "PAPER-000042"}}}

        def close_position_verified(self, sym, **_kw):
            return {
                "status": "verified",
                "order": {"order": {"id": "PAPER-000042"}},
            }

        def get_positions(self):
            return [{"symbol": symbol, "quantity": -1, "strategy_id": "iron_condor"}]

    lock = threading.Lock()
    active_positions = {
        symbol: {
            "symbol": symbol,
            "quantity": -1,
            "entry_price": 4.24,
            "strategy": "iron_condor",
        }
    }

    supervisor = SessionSupervisor(mode="paper", dry_run=True, skip_orphan_sweep=True)
    supervisor.broker = _VerifiedBroker()
    supervisor.engine = SimpleNamespace(
        _active_positions_lock=lock,
        active_positions=active_positions,
        get_active_positions_snapshot=lambda: [
            {"symbol": symbol, "quantity": -1, "strategy_id": "iron_condor"}
        ],
    )

    closed = supervisor._flatten_positions(reason="test_flatten")

    assert closed == 1, "expected one verified close"
    assert symbol not in active_positions, (
        "engine.active_positions must be cleared after a verified flatten so "
        "ExitMonitor does not re-fire a duplicate close"
    )
