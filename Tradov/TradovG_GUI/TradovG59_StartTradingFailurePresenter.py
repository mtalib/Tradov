#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovG_GUI
Module: TradovG59_StartTradingFailurePresenter.py
Purpose: Pure presentation helper for fail-closed start-trading copy
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StartTradingFailurePresentation:
    """Operator-facing dialog copy for fail-closed session-start failure."""

    dialog_title: str
    dialog_text: str


def build_start_trading_failure_presentation() -> StartTradingFailurePresentation:
    """Build the fail-closed dialog copy shown when session startup fails."""
    return StartTradingFailurePresentation(
        dialog_title="Start Failed",
        dialog_text=(
            "Unified backend session failed to start.\n"
            "Trading remains stopped (fail-closed)."
        ),
    )
