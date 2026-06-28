#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovG_GUI
Module: TradovG58_StartTradingLiveGuardPresenter.py
Purpose: Pure presentation helpers for live-mode start-trading guard copy
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StartTradingLiveGuardPresentation:
    """Operator-facing dialog and log copy for live start-trading guards."""

    dialog_title: str
    dialog_text: str
    log_message: str


def build_start_trading_live_guard_presentation(
    *,
    guard: str,
) -> StartTradingLiveGuardPresentation:
    """Build dialog and log copy for a live-mode start-trading guard branch."""
    guard_key = str(guard or "").strip().lower()

    if guard_key == "api_disconnected":
        return StartTradingLiveGuardPresentation(
            dialog_title="API Disconnected",
            dialog_text="API is disconnected - cannot start trading",
            log_message="Cannot start trading - API disconnected",
        )

    if guard_key == "live_cancelled":
        return StartTradingLiveGuardPresentation(
            dialog_title="",
            dialog_text="",
            log_message="Live trading start cancelled by user",
        )

    if guard_key == "no_live_data":
        return StartTradingLiveGuardPresentation(
            dialog_title="No Live Data",
            dialog_text="NO LIVE DATA\n\nCannot start trading without live market data.",
            log_message="Cannot start trading - No live data",
        )

    raise ValueError(f"Unsupported live start-trading guard: {guard}")
