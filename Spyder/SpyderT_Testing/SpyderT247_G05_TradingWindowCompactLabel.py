#!/usr/bin/env python3
"""Focused tests for G05 compact trading-window badge delegation."""

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
from Spyder.SpyderG_GUI.SpyderG49_TradingWindowBadgePresenter import (
    TradingWindowBadgePresentation,
)
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger


class _Label:
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
    dash.trading_window_compact_label = _Label()
    return dash


def test_g05_update_trading_window_compact_label_uses_presenter_output(monkeypatch) -> None:
    dash = _build_dashboard_stub()

    monkeypatch.setattr(
        g05,
        "build_trading_window_badge_presentation",
        lambda *, is_open, colors: TradingWindowBadgePresentation(
            text="badge",
            style="badge-style",
        ),
    )

    dash._update_trading_window_compact_label()

    assert dash.trading_window_compact_label.text == "badge"
    assert dash.trading_window_compact_label.style == "badge-style"


def test_g05_update_trading_window_compact_label_skips_when_label_missing() -> None:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.logger = SpyderLogger.get_logger(__name__)
    dash.trading_window_compact_label = None

    dash._update_trading_window_compact_label()
