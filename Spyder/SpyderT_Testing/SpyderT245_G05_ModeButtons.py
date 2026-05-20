#!/usr/bin/env python3
"""Focused tests for G05 mode-button presentation delegation."""

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
from Spyder.SpyderG_GUI.SpyderG48_TradingArmingPresenter import (
    ButtonPresentation,
    TradingArmingPresentation,
)
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger


class _Button:
    def __init__(self) -> None:
        self.text = ""
        self.style = ""

    def setText(self, value: str) -> None:  # noqa: N802
        self.text = value

    def setStyleSheet(self, value: str) -> None:  # noqa: N802
        self.style = value


def _build_dashboard_stub() -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.logger = SpyderLogger.get_logger(__name__)
    dash._real_trading_armed = False
    dash._paper_trading_armed = True
    dash._paper_trading_enabled_this_session = True
    dash._paper_start_authorized = False
    dash.live_btn = _Button()
    dash.paper_btn = _Button()
    dash.spyderbox_paper_status_btn = _Button()
    dash.spyderbox_paper_toggle_btn = _Button()
    return dash


def test_g05_update_mode_buttons_uses_presenter_output(monkeypatch) -> None:
    dash = _build_dashboard_stub()

    monkeypatch.setattr(
        g05,
        "build_trading_arming_presentation",
        lambda *, real_armed, paper_armed, colors: TradingArmingPresentation(
            real_status=ButtonPresentation(text="real-status", style="real-style"),
            real_toggle=ButtonPresentation(text="real-toggle", style="real-toggle-style"),
            paper_status=ButtonPresentation(text="paper-status", style="paper-style"),
            paper_toggle=ButtonPresentation(text="paper-toggle", style="paper-toggle-style"),
        ),
    )

    dash._update_mode_buttons()

    assert dash.live_btn.text == "real-status"
    assert dash.live_btn.style == "real-style"
    assert dash.paper_btn.text == "real-toggle"
    assert dash.paper_btn.style == "real-toggle-style"
    assert dash.spyderbox_paper_status_btn.text == "paper-status"
    assert dash.spyderbox_paper_status_btn.style == "paper-style"
    assert dash.spyderbox_paper_toggle_btn.text == "paper-toggle"
    assert dash.spyderbox_paper_toggle_btn.style == "paper-toggle-style"


def test_g05_update_mode_buttons_skips_optional_spyderbox_controls(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    dash.spyderbox_paper_status_btn = None
    dash.spyderbox_paper_toggle_btn = None

    monkeypatch.setattr(
        g05,
        "build_trading_arming_presentation",
        lambda *, real_armed, paper_armed, colors: TradingArmingPresentation(
            real_status=ButtonPresentation(text="real-status", style="real-style"),
            real_toggle=ButtonPresentation(text="real-toggle", style="real-toggle-style"),
            paper_status=ButtonPresentation(text="paper-status", style="paper-style"),
            paper_toggle=ButtonPresentation(text="paper-toggle", style="paper-toggle-style"),
        ),
    )

    dash._update_mode_buttons()

    assert dash.live_btn.text == "real-status"
    assert dash.paper_btn.text == "real-toggle"
