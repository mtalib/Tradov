#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG48_TradingArmingPresenter.py
Purpose: Pure presentation helpers for REAL/PAPER arming controls
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class ButtonPresentation:
    """Text and stylesheet for a button-like control."""

    text: str
    style: str


@dataclass(frozen=True)
class TradingArmingPresentation:
    """Dashboard-ready REAL/PAPER arming button presentation."""

    real_status: ButtonPresentation
    real_toggle: ButtonPresentation
    paper_status: ButtonPresentation
    paper_toggle: ButtonPresentation


def build_trading_arming_presentation(
    *,
    real_armed: bool,
    paper_armed: bool,
    colors: Mapping[str, str],
) -> TradingArmingPresentation:
    """Build the four REAL/PAPER arming button presentations."""
    pill = "font-size: 12px; border-radius: 3px; padding: 4px 8px; border: none;"
    inactive = f"{pill} background-color: {colors['panel']}; color: #aaaaaa;"
    enable = f"{pill} background-color: {colors['blue']}; color: white;"
    disable = f"{pill} background-color: #5a5a5a; color: white;"

    return TradingArmingPresentation(
        real_status=ButtonPresentation(
            text="LIVE TRADING",
            style=(
                f"{pill} background-color: {colors['positive']}; color: black;"
                if real_armed
                else inactive
            ),
        ),
        real_toggle=ButtonPresentation(
            text="DISABLE REAL" if real_armed else "ENABLE REAL",
            style=disable if real_armed else enable,
        ),
        paper_status=ButtonPresentation(
            text="PAPER TRADING",
            style=(
                f"{pill} background-color: {colors['orange']}; color: black;"
                if paper_armed
                else inactive
            ),
        ),
        paper_toggle=ButtonPresentation(
            text="DISABLE PAPER" if paper_armed else "ENABLE PAPER",
            style=disable if paper_armed else enable,
        ),
    )
