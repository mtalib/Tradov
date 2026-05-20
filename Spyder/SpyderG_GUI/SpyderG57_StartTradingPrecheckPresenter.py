#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG57_StartTradingPrecheckPresenter.py
Purpose: Pure presentation helpers for start-trading precheck dialogs and logs
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StartTradingPrecheckPresentation:
    """Operator-facing dialog and log copy for start-trading prechecks."""

    dialog_title: str
    dialog_text: str
    log_message: str


def build_start_trading_precheck_presentation(
    *,
    guard: str,
    mode_label: str = "",
    queued_start_requested: bool = False,
) -> StartTradingPrecheckPresentation:
    """Build dialog and log copy for a start-trading precheck branch."""
    guard_key = str(guard or "").strip().lower()

    if guard_key == "mode_not_armed":
        normalized_mode_label = str(mode_label or "").strip().upper() or "UNKNOWN"
        return StartTradingPrecheckPresentation(
            dialog_title=f"{normalized_mode_label} Trading Not Enabled",
            dialog_text=(
                f"{normalized_mode_label} trading is not armed. Click ENABLE "
                f"{normalized_mode_label} before starting."
            ),
            log_message=f"Start blocked: {normalized_mode_label} trading is not enabled",
        )

    if guard_key == "market_data_loading":
        return StartTradingPrecheckPresentation(
            dialog_title="Fresh Market Data Loading",
            dialog_text=(
                "Fresh market data is still loading.\n\n"
                "Trading will begin automatically after fresh market data is fetched "
                "and all startup checks pass."
            ),
            log_message=(
                "⏳ Start request already queued — waiting for fresh market data"
                if queued_start_requested
                else (
                    "⏳ Start requested — trading will begin automatically after fresh "
                    "market data is fetched and all startup checks pass"
                )
            ),
        )

    if guard_key == "market_closed":
        return StartTradingPrecheckPresentation(
            dialog_title="Market Closed",
            dialog_text=(
                "Trading start blocked: market is closed (outside regular trading hours)."
            ),
            log_message="⛔ Trading start blocked: market is closed (outside RTH)",
        )

    raise ValueError(f"Unsupported start-trading precheck guard: {guard}")
