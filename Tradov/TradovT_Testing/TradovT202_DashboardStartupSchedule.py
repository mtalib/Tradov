#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovT_Testing
Module: TradovT202_DashboardStartupSchedule.py
Purpose: Regression tests for dashboard startup-time scheduling
"""

from __future__ import annotations

from datetime import datetime

from Tradov.TradovU_Utilities.TradovU52_StartupSchedule import (
    resolve_opening_runtime_start_times,
)


def test_after_hours_starts_immediately():
    now_et = datetime(2026, 6, 26, 18, 15)
    loading_start_at, runtime_start_at = resolve_opening_runtime_start_times(
        now_et,
        live_data_loading_start_time=datetime.strptime("09:20", "%H:%M").time(),
        opening_data_warmup_end_time=datetime.strptime("09:35", "%H:%M").time(),
    )

    assert loading_start_at == now_et
    assert runtime_start_at == now_et


def test_pre_open_respects_launch_window():
    now_et = datetime(2026, 6, 26, 8, 0)
    loading_start_at, runtime_start_at = resolve_opening_runtime_start_times(
        now_et,
        live_data_loading_start_time=datetime.strptime("09:20", "%H:%M").time(),
        opening_data_warmup_end_time=datetime.strptime("09:35", "%H:%M").time(),
    )

    assert loading_start_at == now_et
    assert runtime_start_at == now_et
