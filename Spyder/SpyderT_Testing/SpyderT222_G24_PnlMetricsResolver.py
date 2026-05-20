#!/usr/bin/env python3
"""Focused tests for pure dashboard P&L metric helpers."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from Spyder.SpyderG_GUI.SpyderG24_PnlMetricsResolver import (
    build_today_trade_analytics,
    normalize_today_worker_metrics,
    overlay_period_pnl_summary,
)


ET = ZoneInfo("America/New_York")


def test_overlay_period_pnl_summary_preserves_existing_today_only() -> None:
    merged = overlay_period_pnl_summary(
        {
            "today_pnl": "$+10.00",
            "week_pnl": "$+5.00",
        },
        {
            "today": 25.0,
            "week": 40.0,
            "month": -12.5,
        },
        preserve_existing_today=True,
    )

    assert merged["today_pnl"] == "$+10.00"
    assert merged["week_pnl"] == "$+40.00"
    assert merged["month_pnl"] == "$-12.50"


def test_normalize_today_worker_metrics_formats_today_fields() -> None:
    normalized = normalize_today_worker_metrics(
        {
            "realized_pnl": "$+123.45",
            "win_rate": 0.75,
            "total_trades": 4,
        }
    )

    assert normalized["today_pnl"] == "$+123.45"
    assert normalized["today_win_rate"] == "75.0%"
    assert normalized["today_win_loss"] == "3/1"


def test_build_today_trade_analytics_handles_epoch_and_iso_trades() -> None:
    analytics = build_today_trade_analytics(
        [
            {
                "closed_at": datetime(2026, 5, 14, 14, 30, tzinfo=ET).timestamp(),
                "realized_pnl": 100.0,
                "max_loss_dollars": 200.0,
            },
            {
                "timestamp": "2026-05-14T19:45:00+00:00",
                "realized_pnl": -50.0,
                "return_on_risk_pct": -25.0,
            },
            {
                "timestamp": "2026-05-13T19:45:00+00:00",
                "realized_pnl": 999.0,
                "return_on_risk_pct": 99.0,
            },
        ],
        target_date=datetime(2026, 5, 14, 18, 0, tzinfo=ET).date(),
        display_tz=ET,
        calmar_mode="equity_curve",
        initial_capital=100000.0,
    )

    assert analytics["today_win_loss"] == "1/1"
    assert analytics["today_win_rate"] == "50.0%"
    assert analytics["today_profit_factor"] == "2.00"
    assert analytics["today_sharpe"]
    assert analytics["today_sortino"]
    assert analytics["today_calmar"]


def test_build_today_trade_analytics_supports_drawdown_based_calmar() -> None:
    analytics = build_today_trade_analytics(
        [
            {
                "closed_at": datetime(2026, 5, 14, 14, 30, tzinfo=ET).timestamp(),
                "realized_pnl": 100.0,
                "max_loss_dollars": 200.0,
            },
            {
                "closed_at": datetime(2026, 5, 14, 15, 30, tzinfo=ET).timestamp(),
                "realized_pnl": -20.0,
                "max_loss_dollars": 100.0,
            },
        ],
        target_date=datetime(2026, 5, 14, 18, 0, tzinfo=ET).date(),
        display_tz=ET,
        calmar_mode="drawdown_value",
        initial_capital=100000.0,
        realized_pnl_raw="$+80.00",
        max_drawdown_raw="0.002",
    )

    assert analytics["today_calmar"] == "0.40"