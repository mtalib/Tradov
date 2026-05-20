#!/usr/bin/env python3
"""Focused tests for paper spread tree presentation helpers."""

from datetime import UTC, date, datetime

from Spyder.SpyderG_GUI.SpyderG13_EnhancedWidgets import COLORS
from Spyder.SpyderG_GUI.SpyderG39_PaperPositionsTreePresenter import (
    build_paper_spread_tree_presentation,
)


def test_build_paper_spread_tree_presentation_formats_header_and_legs() -> None:
    header, legs = build_paper_spread_tree_presentation(
        {
            "structure": "iron_condor",
            "lifecycle_state": "CARRIED OVER",
            "qty": 1,
            "credit": 1.55,
            "mtm_pnl": 0.0,
            "short_strike": 570.0,
            "long_strike": 565.0,
            "expiration": "2026-05-15",
            "opened_at": datetime(2026, 5, 12, 15, 12, tzinfo=UTC).timestamp(),
            "legs": [
                {"side": "Sell Put", "strike": 570.0, "qty": 1, "type": "P", "cost": -125.0, "pnl": 15.0},
                {"side": "Buy Put", "strike": 565.0, "qty": 1, "type": "P", "cost": 45.0, "pnl": -5.0},
                {"side": "Sell Call", "strike": 580.0, "qty": 1, "type": "C", "cost": -130.0, "pnl": -15.0},
                {"side": "Buy Call", "strike": 585.0, "qty": 1, "type": "C", "cost": 55.0, "pnl": 5.0},
            ],
        },
        date(2026, 5, 12),
        UTC,
        COLORS,
        "MANAGED BY AI",
    )

    assert header.timestamp_text == "2026-05-12 15:12"
    assert header.summary_text == "ACTIVE TRADE CARRIED OVER : IRON CONDOR  |  DTE: 03  |  STATUS: OPEN"
    assert header.pnl_text == "NET P&L +$0 (+0.0%)"
    assert header.pnl_color == COLORS["positive"]

    assert [leg.side_text.strip() for leg in legs] == ["Sell Put", "Buy Put", "Sell Call", "Buy Call"]
    assert [leg.strike_text for leg in legs] == ["$570P", "$565P", "$580C", "$585C"]
    assert [leg.price_text for leg in legs] == ["$1.25", "$0.45", "$1.30", "$0.55"]
    assert all(leg.expiry_text == "05/15" for leg in legs)
    assert legs[0].cost_text == "-$125"
    assert legs[0].pnl_text == "+$15"
    assert legs[0].cost_color == COLORS["negative"]
    assert legs[0].pnl_color == COLORS["positive"]


def test_build_paper_spread_tree_presentation_formats_closed_trade_history_rows() -> None:
    header, legs = build_paper_spread_tree_presentation(
        {
            "structure": "iron_condor",
            "qty": 1,
            "credit": 1.48,
            "realized_pnl": -38.0,
            "short_strike": 581.0,
            "long_strike": 576.0,
            "expiration": "2026-05-29",
            "closed_at": datetime(2026, 5, 16, 14, 46, tzinfo=UTC).timestamp(),
            "legs": [
                {"side": "Sell Put", "strike": 581.0, "qty": 1, "type": "P", "cost": -101.0, "pnl": -16.0},
                {"side": "Buy Put", "strike": 576.0, "qty": 1, "type": "P", "cost": 30.0, "pnl": 5.0},
                {"side": "Sell Call", "strike": 596.0, "qty": 1, "type": "C", "cost": -87.0, "pnl": -24.0},
                {"side": "Buy Call", "strike": 601.0, "qty": 1, "type": "C", "cost": 10.0, "pnl": -3.0},
            ],
        },
        date(2026, 5, 16),
        UTC,
        COLORS,
        "CLOSED",
        closed=True,
    )

    assert header.timestamp_text == "2026-05-16 14:46"
    assert header.summary_text == "CLOSED TRADE : IRON CONDOR  |  DTE: 13  |  STATUS: CLOSED"
    assert header.pnl_text == "NET P&L -$38 (-25.7%)"
    assert header.pnl_color == COLORS["negative"]
    assert [leg.side_text.strip() for leg in legs] == ["Sell Put", "Buy Put", "Sell Call", "Buy Call"]
