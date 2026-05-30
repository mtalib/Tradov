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
            "max_loss_per_contract": 345.0,
            "short_strike": 570.0,
            "long_strike": 565.0,
            "expiration": "2026-05-15",
            "opened_at": datetime(2026, 5, 12, 15, 12, tzinfo=UTC).timestamp(),
            "legs": [
                {"side": "Sell Put", "symbol": "SPY260515P00570000", "strike": 570.0, "qty": 1, "type": "P", "cost": -125.0, "pnl": 15.0},
                {"side": "Buy Put", "symbol": "SPY260515P00565000", "strike": 565.0, "qty": 1, "type": "P", "cost": 45.0, "pnl": -5.0},
                {"side": "Sell Call", "symbol": "SPY260515C00580000", "strike": 580.0, "qty": 1, "type": "C", "cost": -130.0, "pnl": -15.0},
                {"side": "Buy Call", "symbol": "SPY260515C00585000", "strike": 585.0, "qty": 1, "type": "C", "cost": 55.0, "pnl": 5.0},
            ],
        },
        date(2026, 5, 12),
        UTC,
        COLORS,
        "MANAGED BY AI",
    )

    assert header.timestamp_text == "2026-05-12 15:12"
    assert header.summary_text == "ACTIVE TRADE CARRIED OVER : IRON CONDOR  |  DTE: 03  |  STATUS: OPEN"
    assert header.cash_held_text == "CASH HELD: $345.00"
    assert header.pnl_text == "NET P&L +$0.00 (+0.0%)"
    assert header.pnl_color == COLORS["positive"]

    assert [leg.action_text for leg in legs] == ["SELL PUT", "BUY PUT", "SELL CALL", "BUY CALL"]
    assert [leg.leg_text for leg in legs] == [
        "SPY260515P00570000",
        "SPY260515P00565000",
        "SPY260515C00580000",
        "SPY260515C00585000",
    ]
    assert [leg.strike_text for leg in legs] == ["$570P", "$565P", "$580C", "$585C"]
    assert [leg.price_text for leg in legs] == ["$1.25", "$0.45", "$1.30", "$0.55"]
    assert all(leg.expiry_text == "05/15" for leg in legs)
    assert legs[0].cost_text == "+$125.00"
    assert legs[0].pnl_text == "+$15.00"
    assert legs[0].cost_color == COLORS["positive"]
    assert legs[0].pnl_color == COLORS["positive"]
    assert legs[1].cost_text == "-$45.00"
    assert legs[1].cost_color == COLORS["negative"]


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
                {"side": "Sell Put", "symbol": "SPY260529P00581000", "strike": 581.0, "qty": 1, "type": "P", "cost": -101.0, "pnl": -16.0},
                {"side": "Buy Put", "symbol": "SPY260529P00576000", "strike": 576.0, "qty": 1, "type": "P", "cost": 30.0, "pnl": 5.0},
                {"side": "Sell Call", "symbol": "SPY260529C00596000", "strike": 596.0, "qty": 1, "type": "C", "cost": -87.0, "pnl": -24.0},
                {"side": "Buy Call", "symbol": "SPY260529C00601000", "strike": 601.0, "qty": 1, "type": "C", "cost": 10.0, "pnl": -3.0},
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
    assert header.cash_held_text == ""
    assert header.pnl_text == "NET P&L -$38.00 (-25.7%)"
    assert header.pnl_color == COLORS["negative"]
    assert [leg.action_text for leg in legs] == ["SELL PUT", "BUY PUT", "SELL CALL", "BUY CALL"]


def test_build_paper_spread_tree_presentation_derives_cash_held_from_debit_butterfly() -> None:
    header, legs = build_paper_spread_tree_presentation(
        {
            "structure": "butterfly",
            "lifecycle_state": "EXECUTING",
            "qty": 10,
            "credit": 0.0,
            "mtm_pnl": -40.0,
            "max_loss": 0.09,
            "expiration": "2026-05-27",
            "opened_at": datetime(2026, 5, 27, 13, 45, tzinfo=UTC).timestamp(),
            "legs": [
                {"side": "Buy Call", "symbol": "SPY260527C00748000", "strike": 748.0, "qty": 10, "type": "C", "cost": 3331.70, "pnl": -586.70},
                {"side": "Sell Call", "symbol": "SPY260527C00749000", "strike": 749.0, "qty": 20, "type": "C", "cost": -5062.60, "pnl": 1542.60},
                {"side": "Buy Call", "symbol": "SPY260527C00750000", "strike": 750.0, "qty": 10, "type": "C", "cost": 1820.90, "pnl": -995.90},
            ],
        },
        date(2026, 5, 27),
        UTC,
        COLORS,
        "MANAGED BY AI",
    )

    assert header.cash_held_text == "CASH HELD: $90.00"
    assert header.pnl_text == "NET P&L -$40.00 (-44.4%)"
    assert [leg.cost_text for leg in legs] == ["-$3,331.70", "+$5,062.60", "-$1,820.90"]
    assert [leg.cost_color for leg in legs] == [COLORS["negative"], COLORS["positive"], COLORS["negative"]]
    assert [leg.leg_text for leg in legs] == [
        "SPY260527C00748000",
        "SPY260527C00749000",
        "SPY260527C00750000",
    ]


def test_build_paper_spread_tree_presentation_normalizes_cost_display_from_leg_side() -> None:
    _, legs = build_paper_spread_tree_presentation(
        {
            "structure": "call_vertical",
            "lifecycle_state": "EXECUTING",
            "qty": 1,
            "credit": 0.0,
            "mtm_pnl": -413.30,
            "expiration": "2026-05-28",
            "opened_at": datetime(2026, 5, 27, 13, 45, tzinfo=UTC).timestamp(),
            "legs": [
                {"side": "Sell Call", "symbol": "SPY260528C00749000", "strike": 749.0, "qty": 1, "type": "C", "cost": 5062.60, "pnl": -887.40},
                {"side": "Buy Call", "symbol": "SPY260528C00750000", "strike": 750.0, "qty": 1, "type": "C", "cost": -1820.90, "pnl": 474.10},
            ],
        },
        date(2026, 5, 27),
        UTC,
        COLORS,
        "MANAGED BY AI",
    )

    assert [leg.action_text for leg in legs] == ["SELL CALL", "BUY CALL"]
    assert [leg.cost_text for leg in legs] == ["+$5,062.60", "-$1,820.90"]
    assert [leg.cost_color for leg in legs] == [COLORS["positive"], COLORS["negative"]]
    assert [leg.pnl_text for leg in legs] == ["-$887.40", "+$474.10"]
    assert [leg.pnl_color for leg in legs] == [COLORS["negative"], COLORS["positive"]]
