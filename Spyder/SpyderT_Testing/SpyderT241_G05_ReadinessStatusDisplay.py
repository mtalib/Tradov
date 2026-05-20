#!/usr/bin/env python3
"""Focused tests for G05 readiness status display delegation."""

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard, TradingMode
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger


class _Widget:
    def __init__(self) -> None:
        self.text = ""
        self.style = ""
        self.enabled = None
        self.tooltip = ""

    def setText(self, value: str) -> None:  # noqa: N802
        self.text = value

    def setStyleSheet(self, value: str) -> None:  # noqa: N802
        self.style = value

    def setEnabled(self, value: bool) -> None:  # noqa: N802
        self.enabled = value

    def setToolTip(self, value: str) -> None:  # noqa: N802
        self.tooltip = value


def _build_dashboard_stub() -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.logger = SpyderLogger.get_logger(__name__)
    dash.trading_mode = TradingMode.PAPER
    dash.trading_active = False
    dash.readiness_status_label = _Widget()
    dash.readiness_btn = _Widget()
    dash.start_btn = _Widget()
    return dash


def test_g05_update_readiness_status_display_uses_presenter_output(monkeypatch) -> None:
    dash = _build_dashboard_stub()

    class _Presentation:
        status_text = "status"
        status_style = "status-style"
        button_text = "button"
        button_style = "button-style"
        start_enabled = False
        start_tooltip = "blocked"

    monkeypatch.setattr(
        g05,
        "build_readiness_status_presentation",
        lambda result, *, trading_mode, trading_active, colors: _Presentation(),
    )

    dash._update_readiness_status_display({"decision": "NO"})

    assert dash.readiness_status_label.text == "status"
    assert dash.readiness_status_label.style == "status-style"
    assert dash.readiness_btn.text == "button"
    assert dash.readiness_btn.style == "button-style"
    assert dash.start_btn.enabled is False
    assert dash.start_btn.tooltip == "blocked"


def test_g05_update_readiness_status_display_skips_missing_start_mutation() -> None:
    dash = _build_dashboard_stub()

    class _Presentation:
        status_text = "status"
        status_style = "status-style"
        button_text = "button"
        button_style = "button-style"
        start_enabled = None
        start_tooltip = None

    original_enabled = True
    original_tooltip = "keep"
    dash.start_btn.enabled = original_enabled
    dash.start_btn.tooltip = original_tooltip

    original_builder = g05.build_readiness_status_presentation
    g05.build_readiness_status_presentation = (
        lambda result, *, trading_mode, trading_active, colors: _Presentation()
    )
    try:
        dash._update_readiness_status_display({"decision": "NO"})
    finally:
        g05.build_readiness_status_presentation = original_builder

    assert dash.start_btn.enabled is original_enabled
    assert dash.start_btn.tooltip == original_tooltip