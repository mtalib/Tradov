#!/usr/bin/env python3
"""Focused tests for G05 pre-open Go/No-Go checklist behavior."""

import threading
from pathlib import Path

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
from Spyder.SpyderG_GUI.SpyderG06_DashboardData import EventClockState
from Spyder.SpyderG_GUI.SpyderG13_EnhancedWidgets import TradingMode
from Spyder.SpyderG_GUI.SpyderG53_GoNoGoPresenter import GoNoGoPresentation
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger


class _Label:
    def __init__(self, text: str = "") -> None:
        self._text = text
        self.style = ""

    def setText(self, value: str) -> None:  # noqa: N802
        self._text = value

    def text(self) -> str:  # noqa: D401
        return self._text

    def setStyleSheet(self, value: str) -> None:  # noqa: N802
        self.style = value


class _Button:
    def __init__(self) -> None:
        self.style = ""
        self.enabled = True
        self.tooltip = ""

    def setStyleSheet(self, value: str) -> None:  # noqa: N802
        self.style = value

    def setEnabled(self, value: bool) -> None:  # noqa: N802
        self.enabled = bool(value)

    def setToolTip(self, value: str) -> None:  # noqa: N802
        self.tooltip = value


class _ConnectionInfo:
    def __init__(self) -> None:
        self.api_connected = True
        self.mkt_data_connected = True


def _build_dashboard_stub() -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.logger = SpyderLogger.get_logger(__name__)
    dash.connection_info = _ConnectionInfo()
    dash._event_clock_lock = threading.Lock()
    dash.event_clock_state = EventClockState(state="clear", enabled=True)
    dash.data_status_label = _Label("LIVE")
    dash.go_no_go_status_label = _Label("Pre-open: NOT RUN")
    dash.go_no_go_btn = _Button()
    dash.start_btn = _Button()
    dash.trading_mode = TradingMode.PAPER
    dash.trading_active = False
    dash._last_go_no_go_result = None
    dash._last_go_no_go_ts = None
    dash._go_no_go_ttl_seconds = 120
    dash._go_no_go_reports_dir = Path("/tmp/spyder_go_no_go_test")
    dash._startup_readiness_state = {
        "checked": True,
        "mode": "paper",
        "automation_enabled": True,
        "warnings": [],
        "errors": [],
        "safe_fallback_applied": False,
        "live_blocking": False,
        "source": "test",
    }
    dash._collect_startup_readiness_state = lambda: dict(dash._startup_readiness_state)
    dash._log_lines = []
    dash.add_system_log = lambda msg: dash._log_lines.append(str(msg))
    return dash


def test_go_no_go_returns_go_when_core_checks_pass() -> None:
    dash = _build_dashboard_stub()

    result = dash.run_preopen_go_no_go_check(show_dialog=False)

    assert result["decision"] == "GO"
    assert result["reasons"] == []
    assert "Pre-open: GO" in dash.go_no_go_status_label.text()


def test_go_no_go_returns_no_go_when_api_disconnected(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    dash.api_connected = False

    monkeypatch.setattr(
        g05,
        "check_api_connection",
        lambda: (False, "Tradier API not configured"),
    )

    result = dash.run_preopen_go_no_go_check(show_dialog=False)

    assert result["decision"] == "NO-GO"
    assert any("execution API is disconnected" in r for r in result["reasons"])
    assert "Pre-open: NO-GO" in dash.go_no_go_status_label.text()
    assert dash.start_btn.enabled is False


def test_go_no_go_returns_conditional_go_during_event_window() -> None:
    dash = _build_dashboard_stub()
    dash.event_clock_state = EventClockState(state="live", enabled=True)

    result = dash.run_preopen_go_no_go_check(show_dialog=False)

    assert result["decision"] == "CONDITIONAL GO"
    assert result["reasons"] == []
    assert result["warnings"]
    assert "Pre-open: CONDITIONAL GO" in dash.go_no_go_status_label.text()
    assert dash.start_btn.enabled is True


def test_go_no_go_uses_presenter_output(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    dash._build_preopen_check_snapshot = lambda: {"checked_at_et": "now"}
    dash._evaluate_trading_readiness_snapshot = lambda snapshot: {"decision": "OK"}

    monkeypatch.setattr(
        g05,
        "build_go_no_go_presentation",
        lambda inner: GoNoGoPresentation(
            decision="GO",
            reasons=("reason-1",),
            warnings=("warning-1",),
            checked_at_et="2026-05-15T09:31:22-04:00",
            status_text="Pre-open: CUSTOM",
            button_style="background-color: #123456;",
            start_enabled=False,
            log_message="custom log",
        ),
    )

    result = dash.run_preopen_go_no_go_check(show_dialog=False)

    assert result == {
        "decision": "GO",
        "reasons": ["reason-1"],
        "warnings": ["warning-1"],
        "checked_at_et": "2026-05-15T09:31:22-04:00",
    }
    assert dash.go_no_go_status_label.text() == "Pre-open: CUSTOM"
    assert dash.start_btn.enabled is False
    assert dash.go_no_go_btn.style == "background-color: #123456;"
    assert dash._log_lines[-1] == "custom log"
