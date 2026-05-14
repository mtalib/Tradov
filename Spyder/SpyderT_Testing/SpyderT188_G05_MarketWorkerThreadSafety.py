#!/usr/bin/env python3
"""Focused tests for G05 market-worker thread handoff behavior."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from Spyder.SpyderG_GUI import SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger


def _build_dashboard_stub() -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.logger = SpyderLogger.get_logger(__name__)
    dash.market_worker = None
    dash.market_thread = None
    return dash


def test_invoke_market_worker_slot_queues_to_running_worker_thread(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    dash.market_worker = SimpleNamespace(pause_periodic_updates=MagicMock())
    dash.market_thread = SimpleNamespace(isRunning=lambda: True)

    invoked: dict[str, object] = {}

    def _fake_invoke_method(worker, slot_name: str, connection_type):
        invoked["worker"] = worker
        invoked["slot_name"] = slot_name
        invoked["connection_type"] = connection_type
        return True

    monkeypatch.setattr(g05.QMetaObject, "invokeMethod", _fake_invoke_method)

    assert dash._invoke_market_worker_slot("pause_periodic_updates") is True
    assert invoked["worker"] is dash.market_worker
    assert invoked["slot_name"] == "pause_periodic_updates"
    assert invoked["connection_type"] == g05.Qt.QueuedConnection
    dash.market_worker.pause_periodic_updates.assert_not_called()


def test_invoke_market_worker_slot_calls_directly_without_running_thread(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    direct_slot = MagicMock()
    dash.market_worker = SimpleNamespace(pause_periodic_updates=direct_slot)
    dash.market_thread = SimpleNamespace(isRunning=lambda: False)

    def _unexpected_invoke_method(*_args, **_kwargs):
        raise AssertionError("invokeMethod should not be used without a running worker thread")

    monkeypatch.setattr(g05.QMetaObject, "invokeMethod", _unexpected_invoke_method)

    assert dash._invoke_market_worker_slot("pause_periodic_updates") is True
    direct_slot.assert_called_once_with()
