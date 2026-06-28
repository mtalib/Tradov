#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovU_Utilities
Module: TradovU52_StartupSchedule.py
Purpose: Pure helpers for dashboard launch-time scheduling
"""

from __future__ import annotations

from datetime import datetime, time


def resolve_opening_runtime_start_times(
    now_et: datetime,
    *,
    live_data_loading_start_time: time,
    opening_data_warmup_end_time: time,
) -> tuple[datetime, datetime]:
    """Return hydration and runtime warmup timestamps for a launch time.

    Tradier connectivity is always attempted immediately on launch.
    """
    _ = live_data_loading_start_time, opening_data_warmup_end_time
    return now_et, now_et
