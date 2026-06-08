#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovG_GUI
Module: TradovG64_ReadinessConnectionRefreshHelper.py
Purpose: Pure helper for readiness connection refresh decisions
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReadinessConnectionRefreshPlan:
    """Plan describing how a readiness probe should affect cached state."""

    api_connected: bool
    mkt_data_connected: bool
    connection_status: str | None
    market_data_status: str | None


def build_readiness_connection_refresh_plan(
    *,
    cached_api: bool,
    cached_mkt: bool,
    fresh_connected: bool | None = None,
    fresh_mode: str | None = None,
) -> ReadinessConnectionRefreshPlan:
    """Resolve refreshed readiness connectivity state from cached and probe inputs."""
    if cached_api or not fresh_connected:
        return ReadinessConnectionRefreshPlan(
            api_connected=cached_api,
            mkt_data_connected=cached_mkt,
            connection_status=None,
            market_data_status=None,
        )

    mode_text = str(fresh_mode or "")
    is_paper_mode = "PAPER" in mode_text.upper()
    market_data_status = "PAPER" if is_paper_mode else "LIVE"

    return ReadinessConnectionRefreshPlan(
        api_connected=True,
        mkt_data_connected=True,
        connection_status=f"API CONNECTED ({mode_text})",
        market_data_status=market_data_status,
    )
