#!/usr/bin/env python3
"""Focused tests for G05 shutdown-time thread cleanup helpers."""

from types import SimpleNamespace

from Spyder.SpyderG_GUI import SpyderG05_TradingDashboard as g05
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


def test_stop_qthread_for_shutdown_uses_helper_for_terminate_path(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    calls: list[str] = []
    helper_calls: list[dict[str, object]] = []

    class _Thread:
        def isRunning(self) -> bool:
            return True

        def quit(self) -> None:
            calls.append("quit")

        def wait(self, timeout: int) -> bool:
            calls.append(f"wait:{timeout}")
            return timeout == 5000

        def terminate(self) -> None:
            calls.append("terminate")

    dash.market_thread = _Thread()

    monkeypatch.setattr(
        g05,
        "build_qthread_shutdown_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or (
            SimpleNamespace(action="terminate_and_wait", warning_message="warn", error_message=None)
            if kwargs["stop_succeeded_after_terminate"] is None
            else SimpleNamespace(action="done", warning_message=None, error_message=None)
        ),
    )

    dash._stop_qthread_for_shutdown("market_thread", "market_thread", wait_ms=3000)

    assert helper_calls == [
        {
            "stop_succeeded_after_quit": False,
            "stop_succeeded_after_terminate": None,
            "label": "market_thread",
            "wait_ms": 3000,
            "terminate_wait_ms": 5000,
        },
        {
            "stop_succeeded_after_quit": False,
            "stop_succeeded_after_terminate": True,
            "label": "market_thread",
            "wait_ms": 3000,
            "terminate_wait_ms": 5000,
        },
    ]
    assert calls == ["quit", "wait:3000", "terminate", "wait:5000"]


def test_emit_market_worker_signal_ignores_shutdown_time_runtime_error() -> None:
    dash = _build_dashboard_stub()

    class _Signal:
        def emit(self) -> None:
            raise RuntimeError("signal source has been deleted")

    dash.market_worker = SimpleNamespace(fast_fetch_requested=_Signal())

    assert dash._emit_market_worker_signal("fast_fetch_requested") is False


def test_emit_market_worker_signal_uses_helper_for_emit_attempt(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    helper_calls: list[dict[str, object]] = []

    class _Signal:
        def emit(self) -> None:
            raise RuntimeError("signal source has been deleted")

    dash.market_worker = SimpleNamespace(fast_fetch_requested=_Signal())

    monkeypatch.setattr(
        g05,
        "build_market_worker_signal_emit_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or SimpleNamespace(action="emit"),
    )

    assert dash._emit_market_worker_signal("fast_fetch_requested") is False
    assert helper_calls == [
        {
            "has_worker": True,
            "has_signal": True,
            "has_emit_method": True,
        }
    ]


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


def test_disconnect_market_worker_fetch_signals_uses_helper_selection(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    calls: list[str] = []
    helper_calls: list[dict[str, object]] = []

    class _Signal:
        def __init__(self, label: str) -> None:
            self.label = label

        def disconnect(self) -> None:
            calls.append(self.label)

    dash.market_worker = SimpleNamespace(
        fetch_requested=_Signal("fetch"),
        fast_fetch_requested=_Signal("fast_fetch"),
    )

    monkeypatch.setattr(
        g05,
        "build_market_worker_signal_disconnect_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or SimpleNamespace(signal_names=("fast_fetch_requested",)),
    )

    dash._disconnect_market_worker_fetch_signals()

    assert helper_calls == [
        {
            "has_worker": True,
            "disconnectable_signals": {
                "fetch_requested": True,
                "fast_fetch_requested": True,
            },
        }
    ]
    assert calls == ["fast_fetch"]


def test_stop_pre_worker_shutdown_timers_stops_present_timers() -> None:
    dash = _build_dashboard_stub()
    calls: list[str] = []

    class _Timer:
        def __init__(self, label: str) -> None:
            self.label = label

        def stop(self) -> None:
            calls.append(self.label)

    dash._real_data_timer = _Timer("real")
    dash._fast_quote_timer = None
    dash._check_timer = _Timer("check")
    dash._decision_flow_timer = _Timer("decision")

    dash._stop_pre_worker_shutdown_timers()

    assert calls == ["real", "check", "decision"]


def test_stop_pre_worker_shutdown_timers_uses_helper_selection(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    calls: list[str] = []
    helper_calls: list[dict[str, object]] = []

    class _Timer:
        def __init__(self, label: str) -> None:
            self.label = label

        def stop(self) -> None:
            calls.append(self.label)

    dash._real_data_timer = _Timer("real")
    dash._fast_quote_timer = _Timer("fast")
    dash._check_timer = _Timer("check")
    dash._decision_flow_timer = _Timer("decision")

    monkeypatch.setattr(
        g05,
        "build_shutdown_timer_stop_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or SimpleNamespace(timer_attrs=("_check_timer", "_decision_flow_timer")),
    )

    dash._stop_pre_worker_shutdown_timers()

    assert helper_calls == [
        {
            "timer_presence": {
                "_real_data_timer": True,
                "_fast_quote_timer": True,
                "_check_timer": True,
                "_decision_flow_timer": True,
            }
        }
    ]
    assert calls == ["check", "decision"]


def test_stop_post_worker_shutdown_timers_stops_present_timers() -> None:
    dash = _build_dashboard_stub()
    calls: list[str] = []

    class _Timer:
        def __init__(self, label: str) -> None:
            self.label = label

        def stop(self) -> None:
            calls.append(self.label)

    dash.datetime_timer = _Timer("datetime")
    dash.chart_timer = _Timer("chart")

    dash._stop_post_worker_shutdown_timers()

    assert calls == ["datetime", "chart"]


def test_stop_post_worker_shutdown_timers_uses_helper_selection(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    calls: list[str] = []
    helper_calls: list[dict[str, object]] = []

    class _Timer:
        def __init__(self, label: str) -> None:
            self.label = label

        def stop(self) -> None:
            calls.append(self.label)

    dash.datetime_timer = _Timer("datetime")
    dash.chart_timer = _Timer("chart")

    monkeypatch.setattr(
        g05,
        "build_post_worker_shutdown_timer_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or SimpleNamespace(timer_attrs=("chart_timer",)),
    )

    dash._stop_post_worker_shutdown_timers()

    assert helper_calls == [
        {
            "timer_presence": {
                "datetime_timer": True,
                "chart_timer": True,
            }
        }
    ]
    assert calls == ["chart"]


def test_stop_market_worker_for_shutdown_stops_worker_when_available() -> None:
    dash = _build_dashboard_stub()
    calls: list[str] = []
    dash.market_worker = SimpleNamespace(stop=lambda: None)
    dash._disconnect_market_worker_fetch_signals = lambda: calls.append("disconnect")
    dash._invoke_market_worker_slot = lambda slot_name: calls.append(slot_name) or True

    dash._stop_market_worker_for_shutdown()

    assert calls == ["disconnect", "stop"]


def test_stop_market_worker_for_shutdown_uses_helper_selection(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    calls: list[str] = []
    helper_calls: list[dict[str, object]] = []
    dash.market_worker = SimpleNamespace(stop=lambda: None)
    dash._disconnect_market_worker_fetch_signals = lambda: calls.append("disconnect")
    dash._invoke_market_worker_slot = lambda slot_name: calls.append(slot_name) or True

    monkeypatch.setattr(
        g05,
        "build_market_worker_shutdown_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or SimpleNamespace(action="noop"),
    )

    dash._stop_market_worker_for_shutdown()

    assert helper_calls == [
        {
            "has_worker": True,
            "has_stop_method": True,
        }
    ]
    assert calls == []


def test_log_close_event_shutdown_messages_uses_helper_copy(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    helper_calls: list[str] = []
    logs: list[str] = []
    dash.add_system_log = lambda message: logs.append(message)

    monkeypatch.setattr(
        g05,
        "build_dashboard_shutdown_message_plan",
        lambda: helper_calls.append("called")
        or SimpleNamespace(
            close_event_system_messages=("first", "second"),
            snapshot_system_message="snap",
        ),
    )

    dash._log_close_event_shutdown_messages()

    assert helper_calls == ["called"]
    assert logs == ["first", "second"]


def test_save_snapshot_on_shutdown_uses_helper_snapshot_message(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    helper_calls: list[str] = []
    calls: list[str] = []
    logs: list[str] = []
    dash._shutdown_snapshot_saved = False
    dash._save_snapshot = lambda: calls.append("save")
    dash.add_system_log = lambda message: logs.append(message)

    monkeypatch.setattr(
        g05,
        "build_dashboard_shutdown_message_plan",
        lambda: helper_calls.append("called")
        or SimpleNamespace(
            close_event_system_messages=("first", "second"),
            snapshot_system_message="snap",
        ),
    )

    dash._save_snapshot_on_shutdown()

    assert calls == ["save"]
    assert helper_calls == ["called"]
    assert logs == ["snap"]
    assert dash._shutdown_snapshot_saved is True


def test_run_close_event_shutdown_sequence_uses_helper_order(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    calls: list[object] = []
    helper_calls: list[str] = []
    event = SimpleNamespace(accept=lambda: calls.append("accept"))

    dash._cancel_start_button_loading_transition = lambda: calls.append("cancel")
    dash._stop_pre_worker_shutdown_timers = lambda: calls.append("pre_timers")
    dash._stop_market_worker_for_shutdown = lambda: calls.append("worker")
    dash._stop_qthread_for_shutdown = (
        lambda thread_attr, label, wait_ms=3000, terminate_wait_ms=5000: calls.append(
            (thread_attr, label, wait_ms, terminate_wait_ms)
        )
    )
    dash._stop_metrics_orchestrator_for_shutdown = lambda: calls.append("metrics")
    dash._stop_post_worker_shutdown_timers = lambda: calls.append("post_timers")
    dash._save_snapshot_on_shutdown = lambda: calls.append("snapshot")
    dash._log_close_event_shutdown_messages = lambda: calls.append("messages")

    monkeypatch.setattr(
        g05,
        "build_close_event_shutdown_sequence_plan",
        lambda: helper_calls.append("called")
        or SimpleNamespace(
            pre_qthread_methods=(
                "_cancel_start_button_loading_transition",
                "_stop_pre_worker_shutdown_timers",
                "_stop_market_worker_for_shutdown",
            ),
            qthread_shutdown_specs=(
                SimpleNamespace(
                    thread_attr="market_thread",
                    label="market_thread",
                    wait_ms=1,
                    terminate_wait_ms=2,
                ),
            ),
            post_qthread_methods=(
                "_stop_metrics_orchestrator_for_shutdown",
                "_stop_post_worker_shutdown_timers",
                "_save_snapshot_on_shutdown",
                "_log_close_event_shutdown_messages",
            ),
        ),
    )

    dash._run_close_event_shutdown_sequence(event)

    assert helper_calls == ["called"]
    assert calls == [
        "cancel",
        "pre_timers",
        "worker",
        ("market_thread", "market_thread", 1, 2),
        "metrics",
        "post_timers",
        "snapshot",
        "messages",
        "accept",
    ]


def test_stop_metrics_orchestrator_for_shutdown_stops_and_clears_owner() -> None:
    dash = _build_dashboard_stub()
    calls: list[str] = []
    dash._metrics_orchestrator = SimpleNamespace(stop=lambda: calls.append("stop"))

    dash._stop_metrics_orchestrator_for_shutdown()

    assert calls == ["stop"]
    assert dash._metrics_orchestrator is None


def test_stop_metrics_orchestrator_for_shutdown_uses_helper_for_warning_path(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    helper_calls: list[dict[str, object]] = []
    warnings: list[tuple[tuple[object, ...], dict[str, object]]] = []

    class _Orchestrator:
        def stop(self) -> None:
            raise RuntimeError("boom")

    dash._metrics_orchestrator = _Orchestrator()
    dash.logger = SimpleNamespace(warning=lambda *args, **kwargs: warnings.append((args, kwargs)))

    monkeypatch.setattr(
        g05,
        "build_metrics_orchestrator_shutdown_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or (
            SimpleNamespace(action="stop_and_clear", clear_owner=True, warning_template=None)
            if not kwargs["stop_failed"]
            else SimpleNamespace(
                action="warn_and_clear",
                clear_owner=True,
                warning_template="Metrics orchestrator stop error: %s",
            )
        ),
    )

    dash._stop_metrics_orchestrator_for_shutdown()

    assert helper_calls == [
        {
            "has_orchestrator": True,
            "has_stop_method": True,
            "stop_failed": False,
        },
        {
            "has_orchestrator": True,
            "has_stop_method": True,
            "stop_failed": True,
        },
    ]
    assert len(warnings) == 1
    warning_args, warning_kwargs = warnings[0]
    assert warning_args[0] == "Metrics orchestrator stop error: %s"
    assert isinstance(warning_args[1], RuntimeError)
    assert str(warning_args[1]) == "boom"
    assert warning_kwargs == {"exc_info": True}
    assert dash._metrics_orchestrator is None
