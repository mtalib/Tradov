#!/usr/bin/env python3
"""Focused tests for G05 shutdown-time thread cleanup helpers."""

from types import SimpleNamespace

from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger


def _build_dashboard_stub() -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.logger = SpyderLogger.get_logger(__name__)
    return dash


def test_stop_qthread_for_shutdown_terminates_stuck_thread() -> None:
    dash = _build_dashboard_stub()
    calls: list[str] = []

    class _Thread:
        def isRunning(self) -> bool:
            return True

        def quit(self) -> None:
            calls.append("quit")

        def wait(self, timeout: int) -> bool:
            calls.append(f"wait:{timeout}")
            return timeout == 1000

        def terminate(self) -> None:
            calls.append("terminate")

    dash.market_thread = _Thread()

    dash._stop_qthread_for_shutdown("market_thread", "market_thread", wait_ms=3000)

    assert calls == ["quit", "wait:3000", "terminate", "wait:5000"]


def test_emit_market_worker_signal_ignores_shutdown_time_runtime_error() -> None:
    dash = _build_dashboard_stub()

    class _Signal:
        def emit(self) -> None:
            raise RuntimeError("signal source has been deleted")

    dash.market_worker = SimpleNamespace(fast_fetch_requested=_Signal())

    assert dash._emit_market_worker_signal("fast_fetch_requested") is False


def test_disconnect_market_worker_fetch_signals_disconnects_available_signals() -> None:
    dash = _build_dashboard_stub()
    calls: list[str] = []

    class _Signal:
        def __init__(self, label: str) -> None:
            self.label = label

        def disconnect(self) -> None:
            calls.append(self.label)

    dash.market_worker = SimpleNamespace(
        fetch_requested=_Signal("fetch"),
        fast_fetch_requested=_Signal("fast_fetch"),
    )

    dash._disconnect_market_worker_fetch_signals()

    assert calls == ["fetch", "fast_fetch"]


def test_stop_metrics_orchestrator_for_shutdown_stops_and_clears_owner() -> None:
    dash = _build_dashboard_stub()
    calls: list[str] = []
    dash._metrics_orchestrator = SimpleNamespace(stop=lambda: calls.append("stop"))

    dash._stop_metrics_orchestrator_for_shutdown()

    assert calls == ["stop"]
    assert dash._metrics_orchestrator is None
