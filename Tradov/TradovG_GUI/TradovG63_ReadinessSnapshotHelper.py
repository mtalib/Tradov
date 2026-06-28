#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovG_GUI
Module: TradovG63_ReadinessSnapshotHelper.py
Purpose: Pure helpers for readiness snapshot shaping
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from Tradov.TradovU_Utilities.TradovU03_DateTimeUtils import TradingTimeUtils


def normalize_readiness_data_status_label(value: Any) -> str:
    """Normalize readiness data-status copy into a stable uppercase label."""
    try:
        return str(value).strip().upper() if value is not None else ""
    except Exception:
        return ""


def build_preopen_check_snapshot_payload(
    *,
    startup_state: dict[str, Any],
    api_connected: bool,
    mkt_data_connected: bool,
    data_status_label: str,
    event_clock_enabled: bool,
    event_clock_state: str,
    checked_at_et: datetime,
) -> dict[str, object]:
    """Build the immutable readiness snapshot payload from scalar inputs."""
    return {
        "startup_state": startup_state,
        "api_connected": api_connected,
        "mkt_data_connected": mkt_data_connected,
        "data_status_label": data_status_label,
        "event_clock_enabled": event_clock_enabled,
        "event_clock_state": event_clock_state,
        "is_weekend": checked_at_et.weekday() >= 5,
        "is_market_hours": TradingTimeUtils.is_market_hours(checked_at_et),
        "checked_at_et": checked_at_et.isoformat(),
    }
