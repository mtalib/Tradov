#!/usr/bin/env python3
"""Focused tests for G05 recent decision-flow diagnostics rendering."""

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard, TradingMode
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger


class _Label:
    """Tiny QLabel stand-in for logic-only tests."""

    def __init__(self) -> None:
        self.text = ""
        self.tooltip = ""

    def setText(self, value: str) -> None:  # noqa: N802 - Qt-style method name
        self.text = value

    def setToolTip(self, value: str) -> None:  # noqa: N802 - Qt-style method name
        self.tooltip = value


def _build_dashboard_stub() -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.logger = SpyderLogger.get_logger(__name__)
    dash.trading_mode = TradingMode.PAPER
    dash._decision_flow_recent_limit = 2
    dash.execution_recent_dispatch_value = _Label()
    dash.execution_recent_drop_value = _Label()
    return dash


def test_g05_recent_decision_flow_diagnostics_render_latest_dispatch_and_drop_records() -> None:
    dash = _build_dashboard_stub()
    dash._get_recent_decision_flow_for_panel = lambda: {
        "limit": 2,
        "decision_log": "logs/decisions/paper/2026-05-13.jsonl",
        "dispatch": [
            {
                "ts_utc": "2026-05-13T14:35:00Z",
                "event": "dispatch_rejected",
                "detail": "Daily trade limit reached",
            },
            {
                "ts_utc": "2026-05-13T14:33:00Z",
                "event": "dispatch_submitted",
                "detail": "submitted",
            },
        ],
        "drops": [
            {
                "ts_utc": "2026-05-13T14:36:00Z",
                "event": "signal_dropped",
                "reason": "session_window:outside_primary_window",
            }
        ],
    }

    dash._update_recent_decision_flow_diagnostics()

    assert dash.execution_recent_dispatch_value.text == (
        "14:35:00 | dispatch_rejected | Daily trade limit reached\n"
        "14:33:00 | dispatch_submitted | submitted"
    )
    assert dash.execution_recent_drop_value.text == (
        "14:36:00 | signal_dropped | session_window:outside_primary_window"
    )
    assert dash.execution_recent_dispatch_value.tooltip == "logs/decisions/paper/2026-05-13.jsonl"
    assert dash.execution_recent_drop_value.tooltip == "logs/decisions/paper/2026-05-13.jsonl"


def test_g05_recent_decision_flow_diagnostics_render_dash_when_no_records() -> None:
    dash = _build_dashboard_stub()
    dash._get_recent_decision_flow_for_panel = lambda: {
        "limit": 2,
        "decision_log": None,
        "dispatch": [],
        "drops": [],
    }

    dash._update_recent_decision_flow_diagnostics()

    assert dash.execution_recent_dispatch_value.text == "-"
    assert dash.execution_recent_drop_value.text == "-"
    assert dash.execution_recent_dispatch_value.tooltip == "Decision log unavailable"
    assert dash.execution_recent_drop_value.tooltip == "Decision log unavailable"


def test_g05_recent_decision_flow_diagnostics_uses_presenter_output(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    dash._get_recent_decision_flow_for_panel = lambda: {"dispatch": [], "drops": [], "decision_log": None}

    class _Presentation:
        dispatch_text = "dispatch-text"
        drop_text = "drop-text"
        tooltip = "decision-log-path"

    monkeypatch.setattr(
        g05,
        "build_recent_decision_flow_panel_presentation",
        lambda flow: _Presentation(),
    )

    dash._update_recent_decision_flow_diagnostics()

    assert dash.execution_recent_dispatch_value.text == "dispatch-text"
    assert dash.execution_recent_drop_value.text == "drop-text"
    assert dash.execution_recent_dispatch_value.tooltip == "decision-log-path"
    assert dash.execution_recent_drop_value.tooltip == "decision-log-path"
