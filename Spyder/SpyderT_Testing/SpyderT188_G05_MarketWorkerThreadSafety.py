#!/usr/bin/env python3
"""Focused tests for G05 market-worker thread handoff behavior."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from Spyder.SpyderG_GUI import SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI import SpyderG18_MarketDataWorker as g18
from Spyder.SpyderG_GUI.SpyderG18_MarketDataWorker import ThreadSafeMarketDataWorker
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


def test_invoke_market_worker_slot_returns_false_without_running_thread(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    direct_slot = MagicMock()
    dash.market_worker = SimpleNamespace(pause_periodic_updates=direct_slot)
    dash.market_thread = SimpleNamespace(isRunning=lambda: False)

    def _unexpected_invoke_method(*_args, **_kwargs):
        raise AssertionError("invokeMethod should not be used without a running worker thread")

    monkeypatch.setattr(g05.QMetaObject, "invokeMethod", _unexpected_invoke_method)

    assert dash._invoke_market_worker_slot("pause_periodic_updates") is False
    direct_slot.assert_not_called()


def test_invoke_market_worker_slot_uses_helper_for_queue_path(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    dash.market_worker = SimpleNamespace(pause_periodic_updates=MagicMock())
    dash.market_thread = SimpleNamespace(isRunning=lambda: True)

    helper_calls: list[dict[str, object]] = []
    invoked: dict[str, object] = {}

    monkeypatch.setattr(
        g05,
        "build_market_worker_slot_invoke_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or SimpleNamespace(action="queue_invoke", warning_message=None),
    )
    monkeypatch.setattr(
        g05.QMetaObject,
        "invokeMethod",
        lambda worker, slot_name, connection_type: invoked.update(
            {
                "worker": worker,
                "slot_name": slot_name,
                "connection_type": connection_type,
            }
        )
        or True,
    )

    assert dash._invoke_market_worker_slot("pause_periodic_updates") is True
    assert helper_calls == [
        {
            "has_worker": True,
            "has_callable_slot": True,
            "thread_running": True,
            "slot_name": "pause_periodic_updates",
        }
    ]
    assert invoked["worker"] is dash.market_worker
    assert invoked["slot_name"] == "pause_periodic_updates"
    assert invoked["connection_type"] == g05.Qt.QueuedConnection
    dash.market_worker.pause_periodic_updates.assert_not_called()


def test_market_worker_pause_periodic_updates_stops_update_timer() -> None:
    worker = ThreadSafeMarketDataWorker.__new__(ThreadSafeMarketDataWorker)
    worker.update_timer = MagicMock()

    ThreadSafeMarketDataWorker.pause_periodic_updates(worker)

    worker.update_timer.stop.assert_called_once_with()


def test_market_worker_fetch_slots_respect_shutdown_requested() -> None:
    worker = ThreadSafeMarketDataWorker.__new__(ThreadSafeMarketDataWorker)
    worker._shutdown_requested = True
    worker._fetch_live_data_from_tradier = MagicMock()
    worker._fetch_quotes_fast = MagicMock()

    ThreadSafeMarketDataWorker.run_full_fetch(worker)
    ThreadSafeMarketDataWorker.run_fast_fetch(worker)

    worker._fetch_live_data_from_tradier.assert_not_called()
    worker._fetch_quotes_fast.assert_not_called()


def test_check_api_connection_uses_quote_probe(monkeypatch) -> None:
    class _Client:
        def __init__(self) -> None:
            self.calls: list[list[str]] = []

        def get_quotes(self, symbols: list[str]) -> dict:
            self.calls.append(symbols)
            return {"quotes": {"quote": {"symbol": "SPY"}}}

        def test_connection(self) -> bool:
            raise AssertionError("legacy account-profile probe should not be used")

    client = _Client()

    monkeypatch.setattr(g18, "TRADIER_AVAILABLE", True)
    monkeypatch.setattr(g18, "_build_market_data_client", lambda: client)
    monkeypatch.setenv("TRADING_MODE", "paper")

    connected, mode = g18.check_api_connection()

    assert connected is True
    assert mode == "Tradier API (PAPER)"
    assert client.calls == [["SPY"]]


def test_build_market_data_client_reuses_cached_client(monkeypatch) -> None:
    import dotenv

    class _TradingEnvironment:
        LIVE = "live"

    class _Client:
        init_calls: list[tuple[str, str, object]] = []

        def __init__(self, api_key: str, account_id: str, environment: object) -> None:
            self.api_key = api_key
            self.account_id = account_id
            self.environment = environment
            self.__class__.init_calls.append((api_key, account_id, environment))

    monkeypatch.setattr(g18, "TRADIER_AVAILABLE", True)
    monkeypatch.setattr(g18, "TradierClient", _Client)
    monkeypatch.setattr(g18, "TradingEnvironment", _TradingEnvironment)
    monkeypatch.setattr(g18, "_TRADIER_CLIENT_CACHE", {})
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setenv("TRADIER_LIVE_API_KEY", "test-key")
    monkeypatch.setenv("TRADIER_LIVE_ACCOUNT_ID", "test-account")
    monkeypatch.setenv("TRADIER_API_KEY", "test-key")
    monkeypatch.setenv("TRADIER_ACCOUNT_ID", "test-account")

    first_client = g18._build_market_data_client()
    second_client = g18._build_market_data_client()

    assert first_client is second_client
    assert _Client.init_calls == [("test-key", "test-account", "live")]


def test_market_worker_start_queues_initial_full_fetch_after_successful_probe(monkeypatch) -> None:
    timer_instances = []

    class _FakeTimer:
        def __init__(self, *_args, **_kwargs):
            self.timeout = SimpleNamespace(connect=lambda *_a, **_k: None)
            self.started_intervals: list[int] = []
            timer_instances.append(self)

        @staticmethod
        def singleShot(*_args, **_kwargs) -> None:
            return None

        def start(self, interval: int) -> None:
            self.started_intervals.append(interval)

        def stop(self) -> None:
            return None

    worker = ThreadSafeMarketDataWorker.__new__(ThreadSafeMarketDataWorker)
    worker._shutdown_requested = False
    worker._emit_data = lambda: None
    worker._check_market_hours = lambda: None
    worker._heartbeat_check = lambda: None
    worker._heartbeat_warning = lambda: None
    worker.fetch_requested = SimpleNamespace(emit=MagicMock())
    worker.connection_status_changed = SimpleNamespace(emit=MagicMock())
    worker.market_data_status_changed = SimpleNamespace(emit=MagicMock())
    worker.heartbeat_status_changed = SimpleNamespace(emit=MagicMock())
    worker.heartbeat_received = SimpleNamespace(emit=MagicMock())

    monkeypatch.setattr(g18, "QTimer", _FakeTimer)
    monkeypatch.setattr(g18, "is_market_hours", lambda: True)
    monkeypatch.setattr(g18, "check_api_connection", lambda: (True, "Tradier API (PAPER)"))

    ThreadSafeMarketDataWorker.start(worker)

    assert worker.api_connected is True
    worker.fetch_requested.emit.assert_called_once_with()
    assert len(timer_instances) == 4
