#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG49_TradingWindowBadgePresenter.py
Purpose: Pure presentation helpers for the compact RTH status badge
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class TradingWindowBadgePresentation:
    """Dashboard-ready compact RTH badge values."""

    text: str
    style: str


def build_trading_window_badge_presentation(
    *,
    is_open: bool,
    colors: Mapping[str, str],
) -> TradingWindowBadgePresentation:
    """Build the compact trading-window badge text and style."""
    if is_open:
        return TradingWindowBadgePresentation(
            text="MARKET OPEN",
            style=f"color: {colors['positive']}; font-size: 12px; font-weight: normal;",
        )
    return TradingWindowBadgePresentation(
        text="MARKET CLOSED",
        style=f"color: {colors['negative']}; font-size: 12px; font-weight: normal;",
    )
