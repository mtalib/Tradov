#!/usr/bin/env python3
"""Focused tests for G49 compact trading-window badge presenter."""

from Spyder.SpyderG_GUI.SpyderG13_EnhancedWidgets import COLORS
from Spyder.SpyderG_GUI.SpyderG49_TradingWindowBadgePresenter import (
    build_trading_window_badge_presentation,
)


def test_build_trading_window_badge_presentation_for_open_market() -> None:
    presentation = build_trading_window_badge_presentation(
        is_open=True,
        colors=COLORS,
    )

    assert presentation.text == "MARKET OPEN"
    assert presentation.style == (
        f"color: {COLORS['positive']}; font-size: 12px; font-weight: normal;"
    )


def test_build_trading_window_badge_presentation_for_closed_market() -> None:
    presentation = build_trading_window_badge_presentation(
        is_open=False,
        colors=COLORS,
    )

    assert presentation.text == "MARKET CLOSED"
    assert presentation.style == (
        f"color: {COLORS['negative']}; font-size: 12px; font-weight: normal;"
    )