#!/usr/bin/env python3
"""Focused tests for G05 market-data readiness gating."""

from __future__ import annotations

from contextlib import nullcontext
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from Spyder.SpyderG_GUI import SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger


class _Label:
    def __init__(self, text: str = "") -> None:
        self._text = text
        self.style = ""

    def setText(self, value: str) -> None:  # noqa: N802
        self._text = value

    def text(self) -> str:
        return self._text

    def setStyleSheet(self, value: str) -> None:  # noqa: N802
        self.style = value


class _Container:
    def __init__(self) -> None:
        self.cursor = None
        self.tooltip = ""

    def setCursor(self, value) -> None:  # noqa: ANN001
        self.cursor = value

    def setToolTip(self, value: str) -> None:  # noqa: N802
        self.tooltip = value


def _build_dashboard_stub(tmp_path: Path) -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.logger = SpyderLogger.get_logger(__name__)
    dash._market_data_initialized = False
    dash._queued_trading_start = False
    dash._start_button_loading_generation = 0
    dash._start_button_loading_timer_active = False
    dash._paper_session_start_pending = False
    dash._paper_session_start_show_failure_dialog = False
    dash._paper_launch_loading_deadline_monotonic = None
    dash._market_worker_started = False
    dash._opening_data_warmup_started = False
    dash._opening_runtime_warmup_completed = False
    dash._suppress_market_data_ready_log = False
    dash._log_lines = []
    dash.add_system_log = lambda message: dash._log_lines.append(str(message))
    dash.market_data = {}
    dash.connection_info = SimpleNamespace(
        last_successful_data=None,
        data_was_live=False,
        market_data_status="NONE",
    )
    dash.symbol_widgets = {}
    dash.signal_panel = None
    dash.data_file = tmp_path / "live_data.json"
    dash.update_toolbar_with_real_data = lambda *_args, **_kwargs: None
    dash.determine_data_status = lambda: "REAL-TIME"
    dash.update_data_status = MagicMock()
    dash.market_worker = None
    dash.start_btn = SimpleNamespace(
        setStyleSheet=MagicMock(),
        setText=MagicMock(),
        setEnabled=MagicMock(),
        setToolTip=MagicMock(),
    )
    dash.data_status_label = _Label("NO DATA")
    dash.data_status_container = _Container()
    dash.trading_active = False
    dash.trading_mode = g05.TradingMode.PAPER
    dash._paper_trading_armed = True
    dash._paper_trading_enabled_this_session = True
    dash._real_trading_armed = False
    dash._paper_start_authorized = False
    dash._confirm_paper_trading = MagicMock(return_value=True)
    dash._startup_readiness_state = {}
    dash._last_readiness_result = {}
    dash._schedule_runtime_followup_startup_tasks = MagicMock()
    return dash


def _build_required_live_snapshot() -> dict:
    payload = {
        "_fetch_time_ms": 1710000005000,
    }
    for index, symbol in enumerate(sorted(g05.STARTUP_READY_REQUIRED_SYMBOLS), start=1):
        payload[symbol] = {
            "last": 500.0 + index,
            "change": 1.0,
            "change_pct": 0.2,
            "timestamp_ms": 1710000000000 + index,
        }
    return payload


def _pin_dashboard_now(monkeypatch, hour: int, minute: int) -> None:
    class _FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 5, 25, hour, minute, tzinfo=tz)

    monkeypatch.setattr(g05, "datetime", _FakeDateTime)


def test_on_market_data_updated_does_not_mark_ready_for_worker_snapshot(monkeypatch, tmp_path) -> None:
    dash = _build_dashboard_stub(tmp_path)
    handled_payloads: list[dict] = []

    monkeypatch.setattr(
        g05,
        "handle_market_data_updated",
        lambda _dash, data: handled_payloads.append(dict(data)),
    )

    dash.on_market_data_updated({"SPY": {"last": 585.25, "change": 0.0, "change_pct": 0.0}})

    assert dash._market_data_initialized is False
    assert dash._log_lines == []
    assert handled_payloads == [{"SPY": {"last": 585.25, "change": 0.0, "change_pct": 0.0}}]


def test_apply_real_data_patch_does_not_mark_ready_before_live_refresh(monkeypatch, tmp_path) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash.real_data_active = False
    dash.update_with_real_data = MagicMock()
    dash.update_status_for_real_data = MagicMock()
    created_timers = []

    class _FakeTimer:
        def __init__(self, *_args, **_kwargs) -> None:
            self.timeout = SimpleNamespace(connect=lambda *_a, **_k: None)
            self.started_with: int | None = None
            created_timers.append(self)

        def start(self, interval: int) -> None:
            self.started_with = interval

        @staticmethod
        def singleShot(_interval: int, _callback) -> None:
            return None

    monkeypatch.setattr(g05, "QTimer", _FakeTimer)
    monkeypatch.setattr(g05, "is_market_hours", lambda: True)

    dash.apply_real_data_patch()

    assert dash.real_data_active is True
    assert dash._market_data_initialized is False
    assert sorted(
        timer.started_with for timer in created_timers if timer.started_with is not None
    ) == [1000, 10000]
    assert "✅ Market data loaded — system ready" not in dash._log_lines


def test_apply_real_data_patch_skips_fast_quote_timer_outside_market_hours(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash.real_data_active = False
    dash.update_with_real_data = MagicMock()
    dash.update_status_for_real_data = MagicMock()
    created_timers = []

    class _FakeTimer:
        def __init__(self, *_args, **_kwargs) -> None:
            self.timeout = SimpleNamespace(connect=lambda *_a, **_k: None)
            self.started_with: int | None = None
            created_timers.append(self)

        def start(self, interval: int) -> None:
            self.started_with = interval

        def stop(self) -> None:
            self.started_with = None

        @staticmethod
        def singleShot(_interval: int, _callback) -> None:
            return None

    monkeypatch.setattr(g05, "QTimer", _FakeTimer)
    monkeypatch.setattr(g05, "is_market_hours", lambda: False)

    dash.apply_real_data_patch()

    assert dash.real_data_active is True
    assert dash._market_data_initialized is False
    assert getattr(dash, "_fast_quote_timer", None) is None
    assert sorted(
        timer.started_with for timer in created_timers if timer.started_with is not None
    ) == [1000]
    assert "✅ Market data loaded — system ready" not in dash._log_lines


def test_update_with_real_data_does_not_mark_ready_for_partial_live_snapshot(tmp_path) -> None:
    dash = _build_dashboard_stub(tmp_path)
    payload = {
        "SPY": {
            "last": 585.25,
            "change": 1.25,
            "change_pct": 0.21,
            "timestamp_ms": 1710000000000,
        },
        "_fetch_time_ms": 1710000005000,
    }
    dash.data_file.write_text(json.dumps(payload), encoding="utf-8")

    dash.update_with_real_data()

    assert dash._market_data_initialized is False
    assert dash._log_lines == []
    assert dash.market_data["SPY"]["last"] == 585.25
    assert dash.connection_info.data_was_live is True


def test_update_with_real_data_marks_ready_after_hydrated_live_snapshot(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    payload = _build_required_live_snapshot()
    dash.data_file.write_text(json.dumps(payload), encoding="utf-8")
    _pin_dashboard_now(monkeypatch, 10, 20)

    dash.update_with_real_data()

    assert dash._market_data_initialized is True
    assert dash._log_lines == ["✅ Market data loaded — system ready"]
    assert dash.market_data["SPY"]["last"] == payload["SPY"]["last"]
    assert dash.connection_info.data_was_live is True


def test_update_with_real_data_reports_entry_gate_before_embargo(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._resolve_first_entry_not_before_et = lambda: "09:45"
    payload = _build_required_live_snapshot()
    dash.data_file.write_text(json.dumps(payload), encoding="utf-8")
    _pin_dashboard_now(monkeypatch, 9, 40)

    dash.update_with_real_data()

    assert dash._market_data_initialized is True
    assert dash._log_lines == ["✅ Market data loaded — entry gate blocked until 09:45 ET"]


def test_update_with_real_data_keeps_dia_visible_outside_market_hours(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash.symbol_widgets["DIA"] = SimpleNamespace(
        update_data=MagicMock(),
        set_unavailable=MagicMock(),
    )
    payload = {
        "DIA": {
            "last": 506.12,
            "change": 3.01,
            "change_pct": 0.6,
            "timestamp_ms": 1779494400133,
        },
        "_fetch_time_ms": 1779712458667,
    }
    dash.data_file.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(g05, "is_market_hours", lambda: False)

    dash.update_with_real_data()

    dash.symbol_widgets["DIA"].update_data.assert_called_once_with(payload["DIA"])
    dash.symbol_widgets["DIA"].set_unavailable.assert_not_called()


def test_schedule_opening_runtime_startup_delays_worker_to_open_and_runtime_to_warmup(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    timer_calls: list[tuple[int, object]] = []

    class _FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 5, 13, 8, 33, tzinfo=tz)

    monkeypatch.setattr(g05, "datetime", _FakeDateTime)
    monkeypatch.setattr(
        g05,
        "QTimer",
        SimpleNamespace(singleShot=lambda ms, cb: timer_calls.append((ms, cb))),
    )

    dash._schedule_opening_runtime_startup()

    assert dash._suppress_market_data_ready_log is True
    assert [call[0] for call in timer_calls] == [0, 3_120_000, 3_600_000]
    assert timer_calls[0][1] == dash._begin_launch_live_data_prewarm


def test_schedule_opening_runtime_startup_starts_loading_immediately_after_925(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    timer_calls: list[tuple[int, object]] = []

    class _FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 5, 13, 9, 26, tzinfo=tz)

    monkeypatch.setattr(g05, "datetime", _FakeDateTime)
    monkeypatch.setattr(
        g05,
        "QTimer",
        SimpleNamespace(singleShot=lambda ms, cb: timer_calls.append((ms, cb))),
    )

    dash._schedule_opening_runtime_startup()

    assert [call[0] for call in timer_calls] == [0, 0, 420_000]
    assert timer_calls[0][1] == dash._begin_launch_live_data_prewarm


def test_begin_launch_live_data_prewarm_starts_quiet_worker_and_followups_once(
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash.start_market_worker = MagicMock()

    SpyderTradingDashboard._begin_launch_live_data_prewarm(dash)
    SpyderTradingDashboard._begin_launch_live_data_prewarm(dash)

    dash.start_market_worker.assert_called_once_with(quiet_startup=True, announce=False)
    dash._schedule_runtime_followup_startup_tasks.assert_called_once_with()


def test_begin_opening_data_warmup_window_announces_wait_and_starts_quiet_worker(
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash.start_market_worker = MagicMock()
    dash._opening_data_warmup_started = False
    dash._session_supervisor = SimpleNamespace(is_running=False)
    dash._build_entry_gate_embargo_message = lambda: "⏳ ENTRY gate remains blocked until 09:45 ET"

    dash._begin_opening_data_warmup_window()

    assert dash._log_lines == [
        "🟡 Establishing live connections and loading live data",
        "⏳ ENTRY gate remains blocked until 09:45 ET",
    ]
    dash.start_market_worker.assert_called_once_with(quiet_startup=True, announce=False)
    dash._schedule_runtime_followup_startup_tasks.assert_called_once_with()
    assert dash.start_btn.setText.call_args_list[-1].args == ("LOADING LIVE DATA",)


def test_begin_market_hours_launch_loading_window_starts_quiet_worker_without_logs(
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash.start_market_worker = MagicMock()
    dash._session_supervisor = SimpleNamespace(is_running=False)

    SpyderTradingDashboard._begin_market_hours_launch_loading_window(dash)

    assert dash._opening_data_warmup_started is True
    assert dash._suppress_market_data_ready_log is True
    assert dash._log_lines == []
    dash.start_market_worker.assert_called_once_with(quiet_startup=True, announce=False)
    dash._schedule_runtime_followup_startup_tasks.assert_called_once_with()
    assert dash.start_btn.setText.call_args_list[-1].args == ("LOADING LIVE DATA",)


def test_opening_warmup_system_log_suppresses_nonessential_lines(tmp_path) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._opening_data_warmup_started = True
    dash._opening_runtime_warmup_completed = False

    assert SpyderTradingDashboard._should_suppress_opening_warmup_system_log(
        dash,
        "📦 Restored 30 symbols from EOD snapshot saved at 2026-05-13 09:29:58",
    ) is True
    assert SpyderTradingDashboard._should_suppress_opening_warmup_system_log(
        dash,
        "✅ Startup readiness validated (mode=PAPER, warnings=0, errors=0)",
    ) is True
    assert SpyderTradingDashboard._should_suppress_opening_warmup_system_log(
        dash,
        "🟡 Establishing live connections and loading live data",
    ) is False
    assert SpyderTradingDashboard._should_suppress_opening_warmup_system_log(
        dash,
        "⏳ ENTRY gate remains blocked until 09:45 ET",
    ) is False


def test_emit_startup_readiness_logs_stays_quiet_before_925(monkeypatch, tmp_path) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._startup_readiness_state = {
        "pending": False,
        "checked": True,
        "mode": "paper",
        "warnings": [],
        "errors": [],
        "safe_fallback_applied": False,
        "live_blocking": False,
    }

    class _FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 5, 13, 8, 33, tzinfo=tz)

    monkeypatch.setattr(g05, "datetime", _FakeDateTime)

    SpyderTradingDashboard._emit_startup_readiness_logs(dash)

    assert dash._log_lines == []


def test_emit_startup_readiness_logs_uses_helper_plan(monkeypatch, tmp_path) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._startup_readiness_state = {"checked": True, "mode": "paper"}
    helper_calls: list[dict[str, object]] = []

    monkeypatch.setattr(g05, "_is_preconnect_idle_window", lambda: True)
    monkeypatch.setattr(
        g05,
        "build_startup_readiness_log_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs)) or SimpleNamespace(
            log_messages=("log-a", "log-b"),
            start_button_plan=SimpleNamespace(
                text="SAFE MODE (AUTO OFF)",
                style_sheet="background-color: #abc123; color: black;",
                tool_tip="helper tooltip",
            ),
        ),
    )

    SpyderTradingDashboard._emit_startup_readiness_logs(dash)

    assert helper_calls == [
        {
            "state": {"checked": True, "mode": "paper"},
            "preconnect_idle": True,
            "warning_color": g05.COLORS.get("warning", "#e6a817"),
        }
    ]
    assert dash._log_lines == ["log-a", "log-b"]
    assert dash.start_btn.setText.call_args_list[-1].args == ("SAFE MODE (AUTO OFF)",)
    assert dash.start_btn.setStyleSheet.call_args_list[-1].args == (
        "background-color: #abc123; color: black;",
    )
    assert dash.start_btn.setToolTip.call_args_list[-1].args == ("helper tooltip",)


def test_refresh_startup_readiness_state_uses_helper_order(monkeypatch, tmp_path) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._shutdown_in_progress = False
    helper_calls: list[dict[str, object]] = []
    call_order: list[str] = []

    monkeypatch.setattr(
        g05,
        "build_startup_readiness_refresh_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs)) or SimpleNamespace(
            should_skip=False,
            step_names=("collect_state", "load_multiplier", "emit_logs"),
        ),
    )
    dash._collect_startup_readiness_state = lambda: call_order.append("collect") or {
        "checked": True
    }
    dash._load_dji_proxy_multiplier = lambda: call_order.append("load") or 101.2
    dash._emit_startup_readiness_logs = lambda: call_order.append("emit")

    SpyderTradingDashboard._refresh_startup_readiness_state(dash)

    assert helper_calls == [{"shutdown_in_progress": False}]
    assert call_order == ["collect", "load", "emit"]
    assert dash._startup_readiness_state == {"checked": True}
    assert dash._dji_from_dia_multiplier == 101.2


def test_schedule_runtime_followup_startup_tasks_starts_launch_hydration_quickly(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._startup_runtime_followups_scheduled = False
    timer_calls: list[tuple[int, object]] = []

    monkeypatch.setattr(
        g05,
        "QTimer",
        SimpleNamespace(singleShot=lambda ms, cb: timer_calls.append((ms, cb))),
    )

    SpyderTradingDashboard._schedule_runtime_followup_startup_tasks(dash)
    SpyderTradingDashboard._schedule_runtime_followup_startup_tasks(dash)

    assert dash._startup_runtime_followups_scheduled is True
    assert [call[0] for call in timer_calls] == [250, 250, 250]


def test_trigger_initial_live_fetch_emits_fetch_request_even_when_probe_is_not_connected(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash.market_worker = SimpleNamespace(fetch_requested=SimpleNamespace(emit=MagicMock()))
    dash.api_connected = False
    dash._emit_market_worker_signal = MagicMock(return_value=True)
    timer_calls: list[tuple[int, object]] = []

    monkeypatch.setattr(
        g05,
        "QTimer",
        SimpleNamespace(singleShot=lambda ms, cb: timer_calls.append((ms, cb))),
    )

    SpyderTradingDashboard._trigger_initial_live_fetch(dash)

    dash._emit_market_worker_signal.assert_called_once_with("fetch_requested")
    assert timer_calls == []


def test_trigger_initial_live_fetch_retries_quickly_when_worker_signal_is_not_ready(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash.market_worker = SimpleNamespace(fetch_requested=SimpleNamespace(emit=MagicMock()))
    dash._emit_market_worker_signal = MagicMock(return_value=False)
    timer_calls: list[tuple[int, object]] = []

    monkeypatch.setattr(
        g05,
        "QTimer",
        SimpleNamespace(singleShot=lambda ms, cb: timer_calls.append((ms, cb))),
    )

    SpyderTradingDashboard._trigger_initial_live_fetch(dash)

    dash._emit_market_worker_signal.assert_called_once_with("fetch_requested")
    assert len(timer_calls) == 1
    assert timer_calls[0][0] == g05.STARTUP_INITIAL_LIVE_FETCH_RETRY_DELAY_MS


def test_determine_data_status_returns_pre_open_for_recent_live_launch_fetch(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash.real_data_active = True
    dash.api_connected = False
    et_tz = g05._get_eastern_timezone()
    dash.connection_info.last_market_data_fetch_time = et_tz.localize(
        datetime(2026, 5, 14, 9, 11, 0),
    )

    class _FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return cls(2026, 5, 14, 9, 11, 30)
            return tz.localize(cls(2026, 5, 14, 9, 11, 30))

    monkeypatch.setattr(g05, "datetime", _FakeDateTime)
    monkeypatch.setattr(g05, "is_market_hours", lambda: False)

    assert SpyderTradingDashboard.determine_data_status(dash) == "PRE-OPEN"


def test_determine_data_status_returns_none_without_real_market_data(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash.real_data_active = False
    dash.api_connected = False
    dash.market_worker = SimpleNamespace(
        update_timer=SimpleNamespace(isActive=lambda: True),
    )

    monkeypatch.setattr(g05, "is_market_hours", lambda: False)

    assert SpyderTradingDashboard.determine_data_status(dash) == "NONE"


def test_update_status_for_real_data_uses_pre_open_live_badge_when_fetch_is_recent(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._resolve_first_entry_not_before_et = lambda: "09:45"
    dash.real_data_active = True
    dash.api_connected = False
    dash.determine_data_status = lambda: SpyderTradingDashboard.determine_data_status(dash)
    dash.update_data_status = lambda status: SpyderTradingDashboard.update_data_status(dash, status)
    et_tz = g05._get_eastern_timezone()
    fetch_dt = et_tz.localize(datetime(2026, 5, 14, 9, 11, 0))
    dash.data_file.write_text(
        json.dumps({"_fetch_time_ms": int(fetch_dt.timestamp() * 1000)}),
        encoding="utf-8",
    )

    class _FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return cls(2026, 5, 14, 9, 11, 30)
            return tz.localize(cls(2026, 5, 14, 9, 11, 30))

    monkeypatch.setattr(g05, "datetime", _FakeDateTime)
    monkeypatch.setattr(g05, "is_market_hours", lambda: False)

    SpyderTradingDashboard.update_status_for_real_data(dash)

    assert dash.data_status_label.text() == "PRE-OPEN"
    assert "strategy hunting and entries remain blocked until 09:45 ET" in dash.data_status_container.tooltip
    assert dash.connection_info.market_data_status == "PRE-OPEN"


def test_schedule_after_launch_loading_hold_offsets_callback_until_release(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._paper_launch_loading_deadline_monotonic = 130.0
    timer_calls: list[tuple[int, object]] = []
    callback = MagicMock()

    monkeypatch.setattr(g05, "is_market_hours", lambda: True)
    monkeypatch.setattr(g05.time, "monotonic", lambda: 105.0)
    monkeypatch.setattr(
        g05,
        "QTimer",
        SimpleNamespace(singleShot=lambda ms, cb: timer_calls.append((ms, cb))),
    )

    SpyderTradingDashboard._schedule_after_launch_loading_hold(dash, callback, 75)

    assert timer_calls == [(25_075, callback)]


def test_mark_market_data_ready_suppresses_system_ready_log_during_opening_warmup(
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._suppress_market_data_ready_log = True

    dash._mark_market_data_ready()

    assert dash._market_data_initialized is True
    assert "✅ Market data loaded — system ready" not in dash._log_lines


def test_complete_market_hours_launch_loading_window_replays_ready_log_after_release(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._market_data_initialized = True
    dash._market_hours_launch_loading_hold_active = True
    dash._complete_opening_runtime_warmup = MagicMock()
    _pin_dashboard_now(monkeypatch, 10, 20)

    SpyderTradingDashboard._complete_market_hours_launch_loading_window(dash)

    assert dash._market_hours_launch_loading_hold_active is False
    dash._complete_opening_runtime_warmup.assert_called_once_with()
    assert dash._log_lines == ["✅ Market data loaded — system ready"]


def test_complete_opening_runtime_warmup_releases_market_worker_quiet_startup(
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._market_worker_started = True
    dash.market_worker = SimpleNamespace(_quiet_startup=True)
    dash.start_market_worker = MagicMock()
    dash._subscribe_to_events = MagicMock()
    dash._init_h07_performance_analytics = MagicMock()
    dash._start_decision_flow_timer = MagicMock()
    dash._schedule_runtime_followup_startup_tasks = MagicMock()

    SpyderTradingDashboard._complete_opening_runtime_warmup(dash)

    assert dash._opening_runtime_warmup_completed is True
    assert dash._suppress_market_data_ready_log is False
    assert dash.market_worker._quiet_startup is False
    dash.start_market_worker.assert_not_called()
    dash._subscribe_to_events.assert_called_once_with()
    dash._init_h07_performance_analytics.assert_called_once_with()
    dash._start_decision_flow_timer.assert_called_once_with()
    dash._schedule_runtime_followup_startup_tasks.assert_called_once_with()


def test_get_paper_open_positions_from_session_db_stays_empty_during_warmup(
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._opening_data_warmup_started = True
    dash._opening_runtime_warmup_completed = False
    dash._get_mode_session_db = MagicMock()

    rows = SpyderTradingDashboard._get_paper_open_positions_from_session_db(dash)

    assert rows == []
    dash._get_mode_session_db.assert_not_called()


def test_start_trading_reports_data_population_while_market_data_is_loading(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)

    info_calls: list[tuple[str, str]] = []
    presenter_calls: list[tuple[str, bool]] = []

    monkeypatch.setattr(
        g05.QMessageBox,
        "information",
        lambda _parent, title, text: info_calls.append((title, text)),
    )
    monkeypatch.setattr(
        g05,
        "build_start_trading_precheck_presentation",
        lambda *, guard, mode_label="", queued_start_requested=False: (
            presenter_calls.append((guard, queued_start_requested))
            or SimpleNamespace(
                dialog_title="custom loading title",
                dialog_text="custom loading text",
                log_message="custom loading log",
            )
        ),
    )

    dash.start_trading()

    assert presenter_calls == [("market_data_loading", False)]
    assert dash._log_lines == ["custom loading log"]
    assert dash._queued_trading_start is True
    dash.start_btn.setStyleSheet.assert_called_once_with("background-color: #d3d3d3; color: black;")
    dash.start_btn.setText.assert_called_once_with("LOADING LIVE DATA")
    dash.start_btn.setEnabled.assert_called_once_with(True)
    dash.start_btn.setToolTip.assert_called_once_with(
        "Waiting for the live-data loading window to complete"
    )
    assert info_calls == [("custom loading title", "custom loading text")]


def test_mark_market_data_ready_processes_queued_start_request(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._queued_trading_start = True
    start_calls: list[str] = []
    dash.start_trading = lambda from_queued=False: start_calls.append(
        "queued" if from_queued else "direct"
    )

    monkeypatch.setattr(
        g05,
        "QTimer",
        SimpleNamespace(singleShot=lambda _ms, cb: cb()),
    )
    _pin_dashboard_now(monkeypatch, 10, 20)

    dash._mark_market_data_ready()

    assert dash._market_data_initialized is True
    assert dash._queued_trading_start is False
    assert dash._log_lines == [
        "✅ Market data loaded — system ready",
        "✅ Fresh market data fetched — processing queued Start Trading request",
    ]
    assert start_calls == ["queued"]


def test_queued_start_restores_start_button_when_start_later_blocks(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._market_data_initialized = True
    dash._paper_trading_armed = False

    warning_calls: list[tuple[str, str]] = []
    presenter_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        g05.QMessageBox,
        "warning",
        lambda _parent, title, text: warning_calls.append((title, text)),
    )
    monkeypatch.setattr(
        g05,
        "build_start_trading_precheck_presentation",
        lambda *, guard, mode_label="", queued_start_requested=False: (
            presenter_calls.append((guard, mode_label))
            or SimpleNamespace(
                dialog_title="custom paper title",
                dialog_text="custom paper text",
                log_message="custom paper log",
            )
        ),
    )

    dash.start_trading(from_queued=True)

    assert presenter_calls == [("mode_not_armed", "PAPER")]
    assert warning_calls == [("custom paper title", "custom paper text")]
    assert dash._log_lines == ["custom paper log"]
    dash.start_btn.setStyleSheet.assert_called_once_with(
        f"background-color: {g05.COLORS['positive']}; color: black;",
    )
    dash.start_btn.setText.assert_called_once_with("START TRADING")
    dash.start_btn.setEnabled.assert_called_once_with(True)
    dash.start_btn.setToolTip.assert_called_once_with(
        "Start paper trading with simulated fills"
    )


def test_start_trading_paper_mode_cancelled_by_user_before_queueing(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._confirm_paper_trading = MagicMock(return_value=False)

    info_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        g05.QMessageBox,
        "information",
        lambda _parent, title, text: info_calls.append((title, text)),
    )

    dash.start_trading()

    dash._confirm_paper_trading.assert_called_once_with()
    assert dash._queued_trading_start is False
    assert dash._log_lines == ["PAPER trading start cancelled by user"]
    assert info_calls == []
    dash.start_btn.setStyleSheet.assert_not_called()
    dash.start_btn.setText.assert_not_called()
    dash.start_btn.setEnabled.assert_not_called()
    dash.start_btn.setToolTip.assert_not_called()


def test_start_trading_paper_mode_blocks_without_session_enable_even_if_armed(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._paper_trading_armed = True
    dash._paper_trading_enabled_this_session = False

    warning_calls: list[tuple[str, str]] = []
    presenter_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        g05.QMessageBox,
        "warning",
        lambda _parent, title, text: warning_calls.append((title, text)),
    )
    monkeypatch.setattr(
        g05,
        "build_start_trading_precheck_presentation",
        lambda *, guard, mode_label="", queued_start_requested=False: (
            presenter_calls.append((guard, mode_label))
            or SimpleNamespace(
                dialog_title="paper-disabled-title",
                dialog_text="paper-disabled-text",
                log_message="paper-disabled-log",
            )
        ),
    )

    dash.start_trading()

    assert presenter_calls == [("mode_not_armed", "PAPER")]
    assert warning_calls == [("paper-disabled-title", "paper-disabled-text")]
    assert dash._log_lines == ["paper-disabled-log"]
    dash._confirm_paper_trading.assert_not_called()


def test_start_trading_queued_paper_start_blocks_without_confirmation_authorization(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._market_data_initialized = True
    dash._confirm_paper_trading = MagicMock(return_value=False)
    dash._require_fresh_readiness_or_block = MagicMock(return_value="OK")
    dash._queue_paper_session_start = MagicMock()

    monkeypatch.setattr(g05, "is_market_hours", lambda: True)
    monkeypatch.setattr(
        g05,
        "build_start_trading_readiness_gate_presentation",
        lambda *, mode_label, reason="": SimpleNamespace(
            safe_mode_log="unused safe-mode log",
            blocked_log=f"unused blocked log: {mode_label}",
            cancelled_log="unused cancelled log",
            override_log=f"unused override log: {reason}",
        ),
    )

    dash.start_trading(from_queued=True)

    dash._confirm_paper_trading.assert_not_called()
    dash._queue_paper_session_start.assert_not_called()
    assert dash._log_lines == ["PAPER trading queued start blocked — confirmation missing"]
    dash.start_btn.setStyleSheet.assert_called_once_with(
        f"background-color: {g05.COLORS['positive']}; color: black;",
    )
    dash.start_btn.setText.assert_called_once_with("START TRADING")
    dash.start_btn.setEnabled.assert_called_once_with(True)
    dash.start_btn.setToolTip.assert_called_once_with(
        "Start paper trading with simulated fills"
    )


def test_start_trading_queued_paper_start_skips_second_confirmation_after_authorization(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._market_data_initialized = True
    dash._paper_start_authorized = True
    dash._confirm_paper_trading = MagicMock(return_value=False)
    dash._require_fresh_readiness_or_block = MagicMock(return_value="OK")
    dash._queue_paper_session_start = MagicMock()

    monkeypatch.setattr(g05, "is_market_hours", lambda: True)
    monkeypatch.setattr(
        g05,
        "build_start_trading_readiness_gate_presentation",
        lambda *, mode_label, reason="": SimpleNamespace(
            safe_mode_log="unused safe-mode log",
            blocked_log=f"unused blocked log: {mode_label}",
            cancelled_log="unused cancelled log",
            override_log=f"unused override log: {reason}",
        ),
    )

    dash.start_trading(from_queued=True)

    dash._confirm_paper_trading.assert_not_called()
    dash._queue_paper_session_start.assert_called_once_with(show_failure_dialog=True)



def test_queued_start_rejected_by_readiness_resets_loading_button(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._market_data_initialized = True
    dash._paper_start_authorized = True
    dash._last_readiness_result = {"decision": "NO"}
    dash._require_fresh_readiness_or_block = MagicMock(return_value="NO")
    dash._append_readiness_bypass_audit = MagicMock()
    dash._update_go_no_go_status_from_result = MagicMock()

    monkeypatch.setattr(g05, "is_market_hours", lambda: True)
    monkeypatch.setattr(
        g05,
        "build_start_trading_readiness_gate_presentation",
        lambda *, mode_label, reason="": SimpleNamespace(
            safe_mode_log="unused safe-mode log",
            blocked_log=f"blocked via presenter for {mode_label}",
            cancelled_log="unused cancelled log",
            override_log=f"unused override log: {reason}",
        ),
    )

    dash.start_trading(from_queued=True)

    assert dash._log_lines == ["blocked via presenter for PAPER"]
    dash.start_btn.setStyleSheet.assert_called_once_with(
        f"background-color: {g05.COLORS['positive']}; color: black;",
    )
    dash.start_btn.setText.assert_called_once_with("START TRADING")
    dash.start_btn.setEnabled.assert_called_once_with(True)
    dash.start_btn.setToolTip.assert_called_once_with(
        "Start paper trading with simulated fills"
    )
    dash._update_go_no_go_status_from_result.assert_called_once_with(
        {"decision": "NO"}
    )
    dash._append_readiness_bypass_audit.assert_called_once_with(
        "blocked",
        "NO hard-block",
        "",
    )


def test_start_trading_conditional_override_uses_presenter_log_and_queues_paper_start(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._market_data_initialized = True
    dash._last_readiness_result = {"decision": "OK", "conditional": True}
    dash._require_fresh_readiness_or_block = MagicMock(return_value="OK")
    dash._prompt_conditional_readiness_reason = MagicMock(
        return_value="manual review completed"
    )
    dash._append_readiness_bypass_audit = MagicMock()
    dash._queue_paper_session_start = MagicMock()

    monkeypatch.setattr(g05, "is_market_hours", lambda: True)
    monkeypatch.setattr(
        g05,
        "build_start_trading_readiness_gate_presentation",
        lambda *, mode_label, reason="": SimpleNamespace(
            safe_mode_log="unused safe-mode log",
            blocked_log=f"unused blocked log: {mode_label}",
            cancelled_log="unused cancelled log",
            override_log=f"override via presenter: {reason}",
        ),
    )

    dash.start_trading()

    assert dash._log_lines == ["override via presenter: manual review completed"]
    dash._append_readiness_bypass_audit.assert_called_once_with(
        "override",
        "OK - CONDITIONAL",
        "manual review completed",
    )
    dash._queue_paper_session_start.assert_called_once_with(show_failure_dialog=True)


def test_start_trading_uses_readiness_gate_helper_for_blocked_result(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._market_data_initialized = True
    dash._paper_start_authorized = True
    dash._last_readiness_result = {"decision": "NO"}
    dash._require_fresh_readiness_or_block = MagicMock(return_value="NO")
    dash._append_readiness_bypass_audit = MagicMock()
    dash._update_go_no_go_status_from_result = MagicMock()

    helper_calls: list[dict[str, object]] = []

    monkeypatch.setattr(g05, "is_market_hours", lambda: True)
    monkeypatch.setattr(
        g05,
        "build_start_trading_readiness_gate_decision_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or SimpleNamespace(
            latest_result={"decision": "NO", "helper": True},
            blocked=True,
            requires_reason_prompt=False,
            restore_start_button_on_block=True,
            sync_go_no_go_on_block=True,
            block_audit_action="blocked",
            block_audit_decision="NO hard-block",
            block_audit_reason="",
        ),
    )
    monkeypatch.setattr(
        g05,
        "build_start_trading_readiness_gate_presentation",
        lambda *, mode_label, reason="": SimpleNamespace(
            safe_mode_log="unused safe-mode log",
            blocked_log=f"blocked via helper for {mode_label}",
            cancelled_log="unused cancelled log",
            override_log=f"unused override log: {reason}",
        ),
    )

    dash.start_trading(from_queued=True)

    assert helper_calls == [
        {
            "decision": "NO",
            "last_readiness_result": {"decision": "NO"},
            "from_queued": True,
        }
    ]
    assert dash._log_lines == ["blocked via helper for PAPER"]
    dash._update_go_no_go_status_from_result.assert_called_once_with(
        {"decision": "NO", "helper": True}
    )
    dash._append_readiness_bypass_audit.assert_called_once_with(
        "blocked",
        "NO hard-block",
        "",
    )


def test_start_trading_live_mode_blocks_when_api_disconnected_uses_presenter_copy(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash.trading_mode = g05.TradingMode.LIVE
    dash._market_data_initialized = True
    dash._real_trading_armed = True
    dash.api_connected = False
    dash._require_fresh_readiness_or_block = MagicMock(return_value="OK")

    warning_calls: list[tuple[str, str]] = []
    presenter_calls: list[str] = []

    monkeypatch.setattr(g05, "is_market_hours", lambda: True)
    monkeypatch.setattr(
        g05.QMessageBox,
        "warning",
        lambda _parent, title, text: warning_calls.append((title, text)),
    )
    monkeypatch.setattr(
        g05,
        "build_start_trading_live_guard_presentation",
        lambda *, guard: (
            presenter_calls.append(guard)
            or SimpleNamespace(
                dialog_title="custom api title",
                dialog_text="custom api text",
                log_message="custom api log",
            )
        ),
    )

    dash.start_trading(from_queued=True)

    assert presenter_calls == ["api_disconnected"]
    assert warning_calls == [("custom api title", "custom api text")]
    assert dash._log_lines == ["custom api log"]
    dash.start_btn.setStyleSheet.assert_called_once_with(
        f"background-color: {g05.COLORS['positive']}; color: black;",
    )
    dash.start_btn.setText.assert_called_once_with("START TRADING")
    dash.start_btn.setEnabled.assert_called_once_with(True)
    dash.start_btn.setToolTip.assert_called_once_with(
        "Start LIVE trading with real order execution"
    )


def test_start_trading_live_mode_cancelled_by_user_uses_presenter_log(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash.trading_mode = g05.TradingMode.LIVE
    dash._market_data_initialized = True
    dash._real_trading_armed = True
    dash.api_connected = True
    dash._confirm_live_trading = MagicMock(return_value=False)
    dash._require_fresh_readiness_or_block = MagicMock(return_value="OK")

    presenter_calls: list[str] = []

    monkeypatch.setattr(g05, "is_market_hours", lambda: True)
    monkeypatch.setattr(
        g05,
        "build_start_trading_live_guard_presentation",
        lambda *, guard: (
            presenter_calls.append(guard)
            or SimpleNamespace(
                dialog_title="",
                dialog_text="",
                log_message="custom cancelled log",
            )
        ),
    )

    dash.start_trading(from_queued=True)

    dash._confirm_live_trading.assert_called_once_with()
    assert presenter_calls == ["live_cancelled"]
    assert dash._log_lines == ["custom cancelled log"]
    dash.start_btn.setStyleSheet.assert_called_once_with(
        f"background-color: {g05.COLORS['positive']}; color: black;",
    )
    dash.start_btn.setText.assert_called_once_with("START TRADING")
    dash.start_btn.setEnabled.assert_called_once_with(True)
    dash.start_btn.setToolTip.assert_called_once_with(
        "Start LIVE trading with real order execution"
    )


def test_start_trading_live_mode_blocks_when_status_not_live_uses_presenter_copy(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash.trading_mode = g05.TradingMode.LIVE
    dash._market_data_initialized = True
    dash._real_trading_armed = True
    dash.api_connected = True
    dash._confirm_live_trading = MagicMock(return_value=True)
    dash._require_fresh_readiness_or_block = MagicMock(return_value="OK")
    dash.data_status_label = _Label("DELAYED")

    warning_calls: list[tuple[str, str]] = []
    presenter_calls: list[str] = []

    monkeypatch.setattr(g05, "is_market_hours", lambda: True)
    monkeypatch.setattr(
        g05.QMessageBox,
        "warning",
        lambda _parent, title, text: warning_calls.append((title, text)),
    )
    monkeypatch.setattr(
        g05,
        "build_start_trading_live_guard_presentation",
        lambda *, guard: (
            presenter_calls.append(guard)
            or SimpleNamespace(
                dialog_title="custom live data title",
                dialog_text="custom live data text",
                log_message="custom live data log",
            )
        ),
    )

    dash.start_trading(from_queued=True)

    dash._confirm_live_trading.assert_called_once_with()
    assert presenter_calls == ["no_live_data"]
    assert warning_calls == [(
        "custom live data title",
        "custom live data text",
    )]
    assert dash._log_lines == ["custom live data log"]
    dash.start_btn.setStyleSheet.assert_called_once_with(
        f"background-color: {g05.COLORS['positive']}; color: black;",
    )
    dash.start_btn.setText.assert_called_once_with("START TRADING")
    dash.start_btn.setEnabled.assert_called_once_with(True)
    dash.start_btn.setToolTip.assert_called_once_with(
        "Start LIVE trading with real order execution"
    )


def test_start_trading_live_mode_uses_live_data_status_helper(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash.trading_mode = g05.TradingMode.LIVE
    dash._market_data_initialized = True
    dash._real_trading_armed = True
    dash.api_connected = True
    dash._confirm_live_trading = MagicMock(return_value=True)
    dash._require_fresh_readiness_or_block = MagicMock(return_value="OK")
    dash._start_unified_session_supervisor = MagicMock(return_value=True)
    dash.data_status_label = _Label("LIVE")

    helper_calls: list[object] = []
    warning_calls: list[tuple[str, str]] = []
    presenter_calls: list[str] = []

    monkeypatch.setattr(g05, "is_market_hours", lambda: True)
    monkeypatch.setattr(
        g05,
        "is_live_equivalent_data_status",
        lambda value: helper_calls.append(value) or False,
    )
    monkeypatch.setattr(
        g05.QMessageBox,
        "warning",
        lambda _parent, title, text: warning_calls.append((title, text)),
    )
    monkeypatch.setattr(
        g05,
        "build_start_trading_live_guard_presentation",
        lambda *, guard: (
            presenter_calls.append(guard)
            or SimpleNamespace(
                dialog_title="custom helper title",
                dialog_text="custom helper text",
                log_message="custom helper log",
            )
        ),
    )

    dash.start_trading(from_queued=True)

    dash._confirm_live_trading.assert_called_once_with()
    assert helper_calls == ["LIVE"]
    assert presenter_calls == ["no_live_data"]
    assert warning_calls == [("custom helper title", "custom helper text")]
    assert dash._log_lines == ["custom helper log"]
    dash._start_unified_session_supervisor.assert_not_called()


def test_start_trading_live_mode_shows_fail_closed_dialog_from_presenter(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash.trading_mode = g05.TradingMode.LIVE
    dash._market_data_initialized = True
    dash._real_trading_armed = True
    dash.api_connected = True
    dash._confirm_live_trading = MagicMock(return_value=True)
    dash._require_fresh_readiness_or_block = MagicMock(return_value="OK")
    dash._start_unified_session_supervisor = MagicMock(return_value=False)
    dash.data_status_label = _Label("LIVE")

    critical_calls: list[tuple[str, str]] = []
    presenter_calls: list[str] = []

    monkeypatch.setattr(g05, "is_market_hours", lambda: True)
    monkeypatch.setattr(
        g05.QMessageBox,
        "critical",
        lambda _parent, title, text: critical_calls.append((title, text)),
    )
    monkeypatch.setattr(
        g05,
        "build_start_trading_failure_presentation",
        lambda: (
            presenter_calls.append("called")
            or SimpleNamespace(
                dialog_title="custom failure title",
                dialog_text="custom failure text",
            )
        ),
    )

    dash.start_trading(from_queued=True)

    dash._confirm_live_trading.assert_called_once_with()
    dash._start_unified_session_supervisor.assert_called_once_with()
    assert presenter_calls == ["called"]
    assert critical_calls == [("custom failure title", "custom failure text")]
    assert dash._log_lines == []
    dash.start_btn.setStyleSheet.assert_called_once_with(
        f"background-color: {g05.COLORS['positive']}; color: black;",
    )
    dash.start_btn.setText.assert_called_once_with("START TRADING")
    dash.start_btn.setEnabled.assert_called_once_with(True)
    dash.start_btn.setToolTip.assert_called_once_with(
        "Start LIVE trading with real order execution"
    )


def test_require_fresh_readiness_or_block_uses_presenter_for_no_result(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash.trading_mode = g05.TradingMode.PAPER
    dash._last_readiness_ts = None
    dash._readiness_ttl_seconds = 120
    dash.run_trading_readiness_check = MagicMock(
        return_value={"decision": "NO", "reasons": ["broker disconnected"]}
    )

    critical_calls: list[tuple[str, str]] = []
    presenter_calls: list[tuple[str, list[str]]] = []

    monkeypatch.setattr(
        g05.QMessageBox,
        "critical",
        lambda _parent, title, text: critical_calls.append((title, text)),
    )
    monkeypatch.setattr(
        g05,
        "build_readiness_start_block_presentation",
        lambda *, mode_label, reasons: (
            presenter_calls.append((mode_label, list(reasons)))
            or SimpleNamespace(
                dialog_title="custom readiness title",
                dialog_text="custom readiness text",
                log_message="custom readiness log",
            )
        ),
    )

    decision = dash._require_fresh_readiness_or_block(g05.TradingMode.PAPER)

    assert decision == "NO"
    dash.run_trading_readiness_check.assert_called_once_with(show_dialog=False)
    assert presenter_calls == [("PAPER", ["broker disconnected"])]
    assert critical_calls == [("custom readiness title", "custom readiness text")]
    assert dash._log_lines == ["custom readiness log"]


def test_require_fresh_readiness_or_block_uses_helper_for_fresh_cached_result(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash.trading_mode = g05.TradingMode.PAPER
    dash._last_readiness_ts = 100.0
    dash._last_readiness_result = {"decision": "OK"}
    dash._readiness_ttl_seconds = 120
    dash.run_trading_readiness_check = MagicMock()

    helper_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        g05.time,
        "time",
        lambda: 150.0,
    )
    monkeypatch.setattr(
        g05,
        "build_readiness_cache_decision_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or SimpleNamespace(cached_decision="OK", refresh_required=False),
    )

    decision = dash._require_fresh_readiness_or_block(g05.TradingMode.PAPER)

    assert decision == "OK"
    assert helper_calls == [
        {
            "last_readiness_ts": 100.0,
            "last_readiness_result": {"decision": "OK"},
            "now": 150.0,
            "ttl_seconds": 120,
        }
    ]
    dash.run_trading_readiness_check.assert_not_called()
    assert dash._log_lines == []


def test_run_trading_readiness_check_async_logs_when_worker_already_running_via_presenter(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._readiness_worker_thread = object()

    monkeypatch.setattr(
        g05,
        "build_readiness_async_already_running_log_message",
        lambda: "custom already-running log",
    )

    dash.run_trading_readiness_check_async()

    assert dash._log_lines == ["custom already-running log"]


def test_run_trading_readiness_check_async_logs_start_via_presenter(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._readiness_worker_thread = None
    dash._readiness_worker = None
    dash.readiness_btn = SimpleNamespace(setEnabled=MagicMock())
    dash._build_preopen_check_snapshot = MagicMock(return_value={"sample": True})
    dash._evaluate_trading_readiness_snapshot = MagicMock()

    class _Signal:
        def __init__(self) -> None:
            self.callbacks: list[object] = []

        def connect(self, callback) -> None:  # noqa: ANN001
            self.callbacks.append(callback)

    class _FakeThread:
        def __init__(self, *_args, **_kwargs) -> None:
            self.started = _Signal()
            self.finished = _Signal()
            self.started_called = False

        def start(self) -> None:
            self.started_called = True

        def quit(self) -> None:
            return None

    class _FakeWorker:
        def __init__(self, snapshot, evaluator) -> None:  # noqa: ANN001
            self.snapshot = snapshot
            self.evaluator = evaluator
            self.finished = _Signal()
            self.failed = _Signal()
            self.thread = None

        def run(self) -> None:
            return None

        def moveToThread(self, thread) -> None:  # noqa: ANN001, N802
            self.thread = thread

    monkeypatch.setattr(
        g05,
        "QThread",
        _FakeThread,
    )
    monkeypatch.setattr(
        g05,
        "_ReadinessCheckWorker",
        _FakeWorker,
    )
    monkeypatch.setattr(
        g05,
        "build_readiness_async_start_log_message",
        lambda: "custom async start log",
    )

    dash.run_trading_readiness_check_async()

    dash._build_preopen_check_snapshot.assert_called_once_with()
    dash.readiness_btn.setEnabled.assert_called_once_with(False)
    assert dash._log_lines == ["custom async start log"]
    assert isinstance(dash._readiness_worker_thread, _FakeThread)
    assert isinstance(dash._readiness_worker, _FakeWorker)
    assert dash._readiness_worker.snapshot == {"sample": True}
    assert dash._readiness_worker.evaluator is dash._evaluate_trading_readiness_snapshot
    assert dash._readiness_worker.thread is dash._readiness_worker_thread
    assert dash._readiness_worker_thread.started_called is True


def test_on_readiness_worker_failed_uses_presenter_copy(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)

    critical_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        g05.QMessageBox,
        "critical",
        lambda _parent, title, text: critical_calls.append((title, text)),
    )
    monkeypatch.setattr(
        g05,
        "build_readiness_async_failure_presentation",
        lambda error_message: SimpleNamespace(
            dialog_title="custom async error title",
            dialog_text=f"custom async error text: {error_message}",
            log_message=f"custom async error log: {error_message}",
        ),
    )

    dash._on_readiness_worker_failed("boom")

    assert dash._log_lines == ["custom async error log: boom"]
    assert critical_calls == [(
        "custom async error title",
        "custom async error text: boom",
    )]


def test_cleanup_readiness_worker_uses_helper_plan_and_clears_references(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash.readiness_btn = SimpleNamespace(setEnabled=MagicMock())
    dash._readiness_worker = SimpleNamespace(deleteLater=MagicMock())
    dash._readiness_worker_thread = SimpleNamespace(deleteLater=MagicMock())
    custom_target = SimpleNamespace(deleteLater=MagicMock())

    monkeypatch.setattr(
        g05,
        "build_readiness_worker_cleanup_plan",
        lambda *, readiness_button, readiness_worker, readiness_worker_thread: (
            SimpleNamespace(
                enable_button=False,
                delete_targets=(custom_target,),
            )
        ),
    )

    dash._cleanup_readiness_worker()

    dash.readiness_btn.setEnabled.assert_not_called()
    custom_target.deleteLater.assert_called_once_with()
    assert dash._readiness_worker is None
    assert dash._readiness_worker_thread is None


def test_build_preopen_check_snapshot_uses_helper_after_refreshing_cached_connection_state(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._startup_readiness_state = {}
    dash._collect_startup_readiness_state = MagicMock(return_value={"seeded": True})
    dash.data_status_label = _Label("  live - real  ")
    dash._event_clock_lock = nullcontext()
    dash.event_clock_state = SimpleNamespace(enabled=False, state="post")
    dash.api_connected = False
    dash.mkt_data_connected = False
    dash.on_connection_status_changed = MagicMock()
    dash.on_market_data_status_changed = MagicMock()

    startup_calls: list[object] = []
    event_clock_calls: list[object] = []
    refresh_calls: list[dict[str, object]] = []
    helper_calls: list[dict[str, object]] = []
    fake_now = datetime(2026, 5, 15, 9, 31)

    class _FakeDateTime:
        @staticmethod
        def now(_tz=None) -> datetime:
            return fake_now

    monkeypatch.setattr(g05, "datetime", _FakeDateTime)
    monkeypatch.setattr(g05, "check_api_connection", lambda: (True, "PAPER"))
    monkeypatch.setattr(
        g05,
        "build_readiness_startup_state_plan",
        lambda startup_state: startup_calls.append(startup_state) or SimpleNamespace(
            startup_state={},
            refresh_cache=True,
        ),
    )
    monkeypatch.setattr(
        g05,
        "build_readiness_event_clock_snapshot",
        lambda event_state: event_clock_calls.append(event_state) or SimpleNamespace(
            enabled=True,
            state="custom event state",
        ),
    )
    monkeypatch.setattr(
        g05,
        "build_readiness_connection_refresh_plan",
        lambda **kwargs: refresh_calls.append(dict(kwargs)) or SimpleNamespace(
            api_connected=True,
            mkt_data_connected=True,
            connection_status="custom connection status",
            market_data_status="custom market status",
        ),
    )
    monkeypatch.setattr(
        g05,
        "build_preopen_check_snapshot_payload",
        lambda **kwargs: helper_calls.append(dict(kwargs)) or {"built": True},
    )

    snapshot = dash._build_preopen_check_snapshot()

    assert snapshot == {"built": True}
    assert startup_calls == [{}]
    dash._collect_startup_readiness_state.assert_called_once_with()
    assert event_clock_calls == [dash.event_clock_state]
    dash.on_connection_status_changed.assert_called_once_with(True, "custom connection status")
    dash.on_market_data_status_changed.assert_called_once_with("custom market status")
    assert refresh_calls == [
        {
            "cached_api": False,
            "cached_mkt": False,
            "fresh_connected": True,
            "fresh_mode": "PAPER",
        }
    ]
    assert helper_calls == [
        {
            "startup_state": {"seeded": True},
            "api_connected": True,
            "mkt_data_connected": True,
            "data_status_label": "LIVE - REAL",
            "event_clock_enabled": True,
            "event_clock_state": "custom event state",
            "checked_at_et": fake_now,
        }
    ]


def test_build_preopen_check_snapshot_uses_cached_startup_state_when_helper_skips_refresh(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._startup_readiness_state = {"cached": True}
    dash._collect_startup_readiness_state = MagicMock(return_value={"seeded": True})
    dash.data_status_label = _Label("LIVE")
    dash._event_clock_lock = nullcontext()
    dash.event_clock_state = SimpleNamespace(enabled=True, state="clear")
    dash.api_connected = True
    dash.mkt_data_connected = True

    startup_calls: list[object] = []
    helper_calls: list[dict[str, object]] = []
    fake_now = datetime(2026, 5, 15, 9, 31)

    class _FakeDateTime:
        @staticmethod
        def now(_tz=None) -> datetime:
            return fake_now

    monkeypatch.setattr(g05, "datetime", _FakeDateTime)
    monkeypatch.setattr(
        g05,
        "build_readiness_startup_state_plan",
        lambda startup_state: startup_calls.append(startup_state) or SimpleNamespace(
            startup_state={"cached": "from helper"},
            refresh_cache=False,
        ),
    )
    monkeypatch.setattr(
        g05,
        "build_readiness_event_clock_snapshot",
        lambda event_state: SimpleNamespace(enabled=True, state="clear"),
    )
    monkeypatch.setattr(
        g05,
        "build_readiness_connection_refresh_plan",
        lambda **_kwargs: SimpleNamespace(
            api_connected=True,
            mkt_data_connected=True,
            connection_status=None,
            market_data_status=None,
        ),
    )
    monkeypatch.setattr(
        g05,
        "build_preopen_check_snapshot_payload",
        lambda **kwargs: helper_calls.append(dict(kwargs)) or {"built": True},
    )

    snapshot = dash._build_preopen_check_snapshot()

    assert snapshot == {"built": True}
    assert startup_calls == [{"cached": True}]
    dash._collect_startup_readiness_state.assert_not_called()
    assert helper_calls == [
        {
            "startup_state": {"cached": "from helper"},
            "api_connected": True,
            "mkt_data_connected": True,
            "data_status_label": "LIVE",
            "event_clock_enabled": True,
            "event_clock_state": "clear",
            "checked_at_et": fake_now,
        }
    ]


def test_evaluate_trading_readiness_snapshot_delegates_to_helper(monkeypatch) -> None:
    snapshot = {"checked_at_et": "2026-05-15T09:31:00-04:00"}
    helper_calls: list[dict[str, object]] = []
    expected = {
        "decision": "NO",
        "conditional": False,
        "checked_at_et": "2026-05-15T09:31:00-04:00",
        "reasons": ["custom reason"],
        "warnings": [],
        "startup_state": {},
    }

    monkeypatch.setattr(
        g05,
        "build_trading_readiness_evaluation",
        lambda seen_snapshot: helper_calls.append(dict(seen_snapshot)) or expected,
    )

    result = g05.SpyderTradingDashboard._evaluate_trading_readiness_snapshot(snapshot)

    assert helper_calls == [snapshot]
    assert result == expected



def test_start_trading_defers_paper_session_start_until_launch_window_completes(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._market_data_initialized = True
    dash._require_fresh_readiness_or_block = MagicMock(return_value="OK")
    dash._start_unified_session_supervisor = MagicMock(
        side_effect=lambda: setattr(dash._session_supervisor, "is_running", True) or True
    )
    dash._adopt_running_session_supervisor_ui_state = MagicMock(
        side_effect=lambda: setattr(dash, "trading_active", True)
    )
    dash._session_supervisor = SimpleNamespace(is_running=False)
    dash._paper_launch_loading_deadline_monotonic = 130.0

    timer_calls: list[tuple[int, object]] = []

    monkeypatch.setattr(g05, "is_market_hours", lambda: True)
    monkeypatch.setattr(g05.time, "monotonic", lambda: 105.0)
    monkeypatch.setattr(
        g05,
        "QTimer",
        SimpleNamespace(singleShot=lambda ms, cb: timer_calls.append((ms, cb))),
    )

    dash.start_trading()

    dash._start_unified_session_supervisor.assert_not_called()
    dash._adopt_running_session_supervisor_ui_state.assert_not_called()
    assert timer_calls and timer_calls[0][0] == 25_000
    assert dash._start_button_loading_timer_active is True
    assert dash._paper_session_start_pending is True
    assert dash.start_btn.setStyleSheet.call_args_list[-1].args == (
        "background-color: #d3d3d3; color: black;",
    )
    assert dash.start_btn.setText.call_args_list[-1].args == ("LOADING LIVE DATA",)
    assert dash.start_btn.setEnabled.call_args_list[-1].args == (True,)
    assert dash.start_btn.setToolTip.call_args_list[-1].args == (
        "Waiting for the live-data loading window to complete",
    )

    timer_calls[0][1]()

    dash._start_unified_session_supervisor.assert_called_once_with()
    dash._adopt_running_session_supervisor_ui_state.assert_called_once_with()
    assert dash._start_button_loading_timer_active is False
    assert dash._paper_session_start_pending is False
    assert dash.start_btn.setStyleSheet.call_args_list[-1].args == (
        f"background-color: {g05.COLORS['automation_active']}; color: white;",
    )
    assert dash.start_btn.setText.call_args_list[-1].args == ("PAPER ACTIVE",)
    assert dash.start_btn.setEnabled.call_args_list[-1].args == (True,)
    assert dash.start_btn.setToolTip.call_args_list[-1].args == (
        "Paper trading session is active",
    )


def test_delayed_paper_start_cancels_when_authorization_is_revoked(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._market_data_initialized = True
    dash._require_fresh_readiness_or_block = MagicMock(return_value="OK")
    dash._start_unified_session_supervisor = MagicMock(return_value=True)
    dash._adopt_running_session_supervisor_ui_state = MagicMock()
    dash._session_supervisor = SimpleNamespace(is_running=False)
    dash._paper_launch_loading_deadline_monotonic = 130.0

    timer_calls: list[tuple[int, object]] = []

    monkeypatch.setattr(g05, "is_market_hours", lambda: True)
    monkeypatch.setattr(g05.time, "monotonic", lambda: 105.0)
    monkeypatch.setattr(
        g05,
        "QTimer",
        SimpleNamespace(singleShot=lambda ms, cb: timer_calls.append((ms, cb))),
    )

    dash.start_trading()

    assert dash._paper_start_authorized is True
    assert dash._paper_session_start_pending is True

    dash._paper_trading_armed = False
    dash._paper_start_authorized = False
    timer_calls[0][1]()

    dash._start_unified_session_supervisor.assert_not_called()
    dash._adopt_running_session_supervisor_ui_state.assert_not_called()
    assert dash._paper_session_start_pending is False
    assert dash._start_button_loading_timer_active is False
    assert dash._log_lines[-1] == "Delayed PAPER start cancelled — authorization no longer active"
    assert dash.start_btn.setStyleSheet.call_args_list[-1].args == (
        f"background-color: {g05.COLORS['positive']}; color: black;",
    )
    assert dash.start_btn.setText.call_args_list[-1].args == ("START TRADING",)
    assert dash.start_btn.setEnabled.call_args_list[-1].args == (True,)
    assert dash.start_btn.setToolTip.call_args_list[-1].args == (
        "Start paper trading with simulated fills",
    )


def test_start_trading_starts_paper_immediately_after_launch_window_expires(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._market_data_initialized = True
    dash._require_fresh_readiness_or_block = MagicMock(return_value="OK")
    dash._start_unified_session_supervisor = MagicMock(
        side_effect=lambda: setattr(dash._session_supervisor, "is_running", True) or True
    )
    dash._adopt_running_session_supervisor_ui_state = MagicMock(
        side_effect=lambda: setattr(dash, "trading_active", True)
    )
    dash._session_supervisor = SimpleNamespace(is_running=False)
    dash._paper_launch_loading_deadline_monotonic = 100.0

    timer_calls: list[tuple[int, object]] = []

    monkeypatch.setattr(g05, "is_market_hours", lambda: True)
    monkeypatch.setattr(g05.time, "monotonic", lambda: 131.0)
    monkeypatch.setattr(
        g05,
        "QTimer",
        SimpleNamespace(singleShot=lambda ms, cb: timer_calls.append((ms, cb))),
    )

    dash.start_trading()

    assert timer_calls == []
    dash._start_unified_session_supervisor.assert_called_once_with()
    dash._adopt_running_session_supervisor_ui_state.assert_called_once_with()
    assert dash._paper_session_start_pending is False
    assert dash._start_button_loading_timer_active is False


def test_queue_paper_session_start_uses_helper_to_finalize_immediately(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash.trading_mode = g05.TradingMode.PAPER
    dash._session_supervisor = SimpleNamespace(is_running=False)
    dash._cancel_start_button_loading_transition = MagicMock()
    dash._adopt_running_session_supervisor_ui_state = MagicMock()
    dash._finalize_queued_paper_session_start = MagicMock()
    dash._begin_start_button_loading_transition = MagicMock()
    dash._remaining_paper_start_loading_delay_ms = MagicMock(return_value=0)

    helper_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        g05,
        "build_paper_session_queue_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or SimpleNamespace(
            action="finalize_now",
            set_pending=True,
            pending_value=True,
            set_show_failure_dialog=True,
            show_failure_dialog=True,
            delay_ms=None,
        ),
    )

    dash._queue_paper_session_start(show_failure_dialog=True)

    assert helper_calls == [
        {
            "shutdown_in_progress": False,
            "is_paper_mode": True,
            "trading_active": False,
            "supervisor_running": False,
            "session_start_pending": False,
            "show_failure_dialog": True,
            "delay_ms": 0,
        }
    ]
    assert dash._paper_session_start_pending is True
    assert dash._paper_session_start_show_failure_dialog is True
    dash._finalize_queued_paper_session_start.assert_called_once_with()
    dash._begin_start_button_loading_transition.assert_not_called()
    dash._adopt_running_session_supervisor_ui_state.assert_not_called()
    dash._cancel_start_button_loading_transition.assert_not_called()


def test_finalize_queued_paper_session_start_starts_after_hours_paper_session(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._paper_session_start_pending = True
    dash._paper_session_start_show_failure_dialog = False
    dash._paper_start_authorized = True
    dash._restore_start_button_ready_state = MagicMock()
    dash._cancel_start_button_loading_transition = MagicMock()
    dash._start_unified_session_supervisor = MagicMock(return_value=True)
    dash._adopt_running_session_supervisor_ui_state = MagicMock()

    helper_calls: list[dict[str, object]] = []
    warning_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(g05, "is_market_hours", lambda: False)
    monkeypatch.setattr(
        g05.QMessageBox,
        "warning",
        lambda _parent, title, text: warning_calls.append((title, text)),
    )
    monkeypatch.setattr(
        g05,
        "build_paper_session_finalize_outcome_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or SimpleNamespace(action="adopt_running", show_dialog=False),
    )

    dash._finalize_queued_paper_session_start()

    assert helper_calls == [
        {
            "market_open": False,
            "start_succeeded": True,
            "show_failure_dialog": False,
        }
    ]
    assert dash._paper_session_start_pending is False
    assert dash._paper_session_start_show_failure_dialog is False
    assert dash._log_lines == []
    assert warning_calls == []
    dash._start_unified_session_supervisor.assert_called_once_with()
    dash._adopt_running_session_supervisor_ui_state.assert_called_once_with()
    dash._restore_start_button_ready_state.assert_not_called()
    dash._cancel_start_button_loading_transition.assert_not_called()


def test_finalize_queued_paper_session_start_uses_helper_to_restore_on_start_failure(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._paper_session_start_pending = True
    dash._paper_session_start_show_failure_dialog = True
    dash._paper_start_authorized = True
    dash._restore_start_button_ready_state = MagicMock()
    dash._start_unified_session_supervisor = MagicMock(return_value=False)
    dash._adopt_running_session_supervisor_ui_state = MagicMock()

    helper_calls: list[dict[str, object]] = []
    critical_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(g05, "is_market_hours", lambda: True)
    monkeypatch.setattr(
        g05.QMessageBox,
        "critical",
        lambda _parent, title, text: critical_calls.append((title, text)),
    )
    monkeypatch.setattr(
        g05,
        "build_paper_session_finalize_outcome_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or SimpleNamespace(action="start_failed", show_dialog=True),
    )

    dash._finalize_queued_paper_session_start()

    assert helper_calls == [
        {
            "market_open": True,
            "start_succeeded": False,
            "show_failure_dialog": True,
        }
    ]
    assert dash._paper_session_start_pending is False
    assert dash._paper_session_start_show_failure_dialog is False
    assert critical_calls == [
        (
            "Start Failed",
            "Unified backend session failed to start.\n"
            "Trading remains stopped (fail-closed).",
        )
    ]
    dash._start_unified_session_supervisor.assert_called_once_with()
    dash._adopt_running_session_supervisor_ui_state.assert_not_called()
    dash._restore_start_button_ready_state.assert_called_once_with()
    assert dash._log_lines == []


def test_finalize_queued_paper_session_start_allows_explicit_injected_autostart(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._paper_trading_armed = False
    dash._paper_trading_enabled_this_session = False
    dash._paper_start_authorized = False
    dash._paper_session_start_pending = True
    dash._paper_session_start_show_failure_dialog = False
    dash._session_supervisor = SimpleNamespace(
        is_running=False,
        _spyder_paper_start_authorized=True,
    )
    dash._start_unified_session_supervisor = MagicMock(return_value=True)
    dash._adopt_running_session_supervisor_ui_state = MagicMock()

    monkeypatch.setattr(g05, "is_market_hours", lambda: True)

    dash._finalize_queued_paper_session_start()

    dash._start_unified_session_supervisor.assert_called_once_with()
    dash._adopt_running_session_supervisor_ui_state.assert_called_once_with()
    assert dash._paper_session_start_pending is False
    assert dash._paper_session_start_show_failure_dialog is False
    assert dash._log_lines == []
