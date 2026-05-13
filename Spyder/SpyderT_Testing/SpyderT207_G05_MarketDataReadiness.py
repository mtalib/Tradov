#!/usr/bin/env python3
"""Focused tests for G05 market-data readiness gating."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from Spyder.SpyderG_GUI import SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger


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
    dash.trading_active = False
    dash.trading_mode = g05.TradingMode.PAPER
    dash._paper_trading_armed = True
    dash._real_trading_armed = False
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

    class _FakeTimer:
        def __init__(self, *_args, **_kwargs) -> None:
            self.timeout = SimpleNamespace(connect=lambda *_a, **_k: None)
            self.started_with: int | None = None

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


def test_update_with_real_data_marks_ready_after_hydrated_live_snapshot(tmp_path) -> None:
    dash = _build_dashboard_stub(tmp_path)
    payload = _build_required_live_snapshot()
    dash.data_file.write_text(json.dumps(payload), encoding="utf-8")

    dash.update_with_real_data()

    assert dash._market_data_initialized is True
    assert dash._log_lines == ["✅ Market data loaded — system ready"]
    assert dash.market_data["SPY"]["last"] == payload["SPY"]["last"]
    assert dash.connection_info.data_was_live is True


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
    assert [call[0] for call in timer_calls] == [3_120_000, 3_600_000]


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

    assert [call[0] for call in timer_calls] == [0, 420_000]


def test_begin_opening_data_warmup_window_announces_wait_and_starts_quiet_worker(
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash.start_market_worker = MagicMock()
    dash._opening_data_warmup_started = False
    dash._session_supervisor = SimpleNamespace(is_running=False)

    dash._begin_opening_data_warmup_window()

    assert dash._log_lines == [
        "🟡 Establishing live connections and loading live data",
        "⏳ Trading activity will activate at 09:33 ET",
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
        "⏳ Trading activity will activate at 09:33 ET",
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


def test_schedule_runtime_followup_startup_tasks_waits_until_warmup_release(
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
    assert [call[0] for call in timer_calls] == [1000, 1000, 4000]


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
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._market_data_initialized = True
    dash._market_hours_launch_loading_hold_active = True
    dash._complete_opening_runtime_warmup = MagicMock()

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

    monkeypatch.setattr(
        g05.QMessageBox,
        "information",
        lambda _parent, title, text: info_calls.append((title, text)),
    )

    dash.start_trading()

    assert dash._log_lines == [
        "⏳ Start requested — trading will begin automatically after fresh market data is fetched and all startup checks pass",
    ]
    assert dash._queued_trading_start is True
    dash.start_btn.setStyleSheet.assert_called_once_with("background-color: #d3d3d3; color: black;")
    dash.start_btn.setText.assert_called_once_with("LOADING LIVE DATA")
    dash.start_btn.setEnabled.assert_called_once_with(True)
    dash.start_btn.setToolTip.assert_called_once_with(
        "Waiting for the live-data loading window to complete"
    )
    assert info_calls == [
        (
            "Fresh Market Data Loading",
            "Fresh market data is still loading.\n\n"
            "Trading will begin automatically after fresh market data is fetched and all startup checks pass.",
        )
    ]


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

    monkeypatch.setattr(g05.QMessageBox, "warning", lambda *_args, **_kwargs: None)

    dash.start_trading(from_queued=True)

    assert dash._log_lines == ["Start blocked: PAPER trading is not enabled"]
    dash.start_btn.setStyleSheet.assert_called_once_with(
        f"background-color: {g05.COLORS['positive']}; color: black;",
    )
    dash.start_btn.setText.assert_called_once_with("START TRADING")
    dash.start_btn.setEnabled.assert_called_once_with(True)
    dash.start_btn.setToolTip.assert_called_once_with(
        "Start paper trading with simulated fills"
    )


def test_queued_start_rejected_by_readiness_resets_loading_button(
    monkeypatch,
    tmp_path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._market_data_initialized = True
    dash._last_readiness_result = {"decision": "NO"}
    dash._require_fresh_readiness_or_block = MagicMock(return_value="NO")
    dash._append_readiness_bypass_audit = MagicMock()
    dash._update_go_no_go_status_from_result = MagicMock()

    monkeypatch.setattr(g05, "is_market_hours", lambda: True)

    dash.start_trading(from_queued=True)

    assert dash._log_lines == [
        "⛔ Session blocked by readiness check (NO) — PAPER trading start rejected"
    ]
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