#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovG_GUI
Module: TradovG51_ModeTitlePresenter.py
Purpose: Pure presentation helpers for mode-specific panel titles
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModeTitlePresentation:
    """Dashboard-ready mode-specific title values."""

    text: str
    style: str


def _build_mode_title_presentation(prefix: str, *, is_paper: bool) -> ModeTitlePresentation:
    mode_text = "PAPER TRADING" if is_paper else "LIVE TRADING"
    title_color = "#FFA500" if is_paper else "#00FF00"
    return ModeTitlePresentation(
        text=f"{prefix} - {mode_text}",
        style=f"font-weight: normal; color: {title_color};",
    )


def build_pnl_title_presentation(*, is_paper: bool) -> ModeTitlePresentation:
    """Build the mode-specific P&L title text and style."""
    return _build_mode_title_presentation("P&L PERFORMANCE", is_paper=is_paper)


def build_orders_title_presentation(*, is_paper: bool) -> ModeTitlePresentation:
    """Build the mode-specific orders title text and style."""
    return _build_mode_title_presentation("ORDERS & POSITIONS", is_paper=is_paper)
