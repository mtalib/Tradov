"""Regression tests for R12 FLATTEN_REQUEST broker-cutoff guard wiring."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# Ensure canonical Spyder imports resolve to this repository in CI.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_PACKAGE_ROOT = _REPO_ROOT / "Spyder"
for _path in (_REPO_ROOT, _PACKAGE_ROOT):
    _path_str = str(_path)
    if _path_str not in sys.path:
        sys.path.insert(0, _path_str)

_existing_spyder = sys.modules.get("Spyder")
if _existing_spyder is not None:
    _spyder_file = getattr(_existing_spyder, "__file__", "") or ""
    _is_pkg = hasattr(_existing_spyder, "__path__")
    if (not _is_pkg) or (_spyder_file and not _spyder_file.startswith(str(_PACKAGE_ROOT))):
        sys.modules.pop("Spyder", None)

from Spyder.SpyderA_Core.SpyderA05_EventManager import EventType
from Spyder.SpyderA_Core.SpyderA05_EventManager import EventManager
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
