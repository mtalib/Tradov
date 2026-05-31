#!/usr/bin/env python3
"""Focused tests for paper positions tree presentation helpers."""

from datetime import UTC, date, datetime

from Spyder.SpyderG_GUI.SpyderG13_EnhancedWidgets import COLORS
from Spyder.SpyderG_GUI.SpyderG39_PaperPositionsTreePresenter import (
    build_paper_spread_tree_presentation,
    build_restored_position_group_presentations,
    build_restored_position_presentations,
    coerce_float,
    coerce_int,
    format_days_to_expiration,
    format_expiration_short,
)


def test_format_helpers_coerce_and_render_expiration_values() -> None:
    assert coerce_float("1.25", None) == 1.25
    assert coerce_float("", 2.0) == 2.0
    assert coerce_int("3.0", 0) == 3
    assert coerce_int(None, 2) == 2
    assert format_days_to_expiration("2026-05-15", date(2026, 5, 12)) == "03"
    assert format_days_to_expiration("", date(2026, 5, 12)) == "--"
    assert format_expiration_short("2026-05-15") == "05/15"
    assert format_expiration_short("") == "--"


def test_build_restored_position_presentations_formats_summary_and_detail_rows() -> None:
    presentations = build_restored_position_presentations(
        [
            {
                "symbol": "SPY260515P00570000",
                "quantity": -1,
                "entry_price": 1.25,
                "current_price": 1.10,
                "unrealized_pnl": 15.0,
                "strategy": "iron_condor",
                "status": "OPEN",
                "opened_at": "2026-05-12T15:12:30+00:00",
                "expiration": "2026-05-15",
                "strike": 570.0,
                "option_type": "put",
            }
        ],
        COLORS,
    )

    assert len(presentations) == 1
    presentation = presentations[0]
    assert "ACTIVE PAPER POSITION (CARRIED OVER) : IRON CONDOR" in presentation.summary_text
    assert "STATUS: OPEN" in presentation.summary_text
    assert presentation.action_text == "SELL PUT"
    assert presentation.leg_text == "SPY260515P00570000"
    assert presentation.strike_text == "$570P"
    assert presentation.quantity_text == "1"
    assert presentation.expiry_text == "05/15"
    assert presentation.entry_price_text == "$1.25"
    assert presentation.cost_text == "-$125.00"
    assert presentation.pnl_text == "+$15.00"
    assert presentation.quantity_color == COLORS["negative"]
    assert presentation.cost_color == COLORS["negative"]
    assert presentation.pnl_color == COLORS["positive"]
    assert "Average entry: $1.25" in presentation.tooltip_text
    assert "Mark: $1.10" in presentation.tooltip_text


def test_build_restored_position_presentations_prefers_strategy_id_for_bw_label() -> None:
    presentations = build_restored_position_presentations(
        [
            {
                "symbol": "SPY",
                "quantity": 1,
                "entry_price": 749.04,
                "current_price": 748.12,
                "unrealized_pnl": -92.0,
                "strategy": "butterfly",
                "strategy_id": "BrokenWingButterfly",
                "status": "OPEN",
                "opened_at": "2026-05-26T13:51:09+00:00",
            }
        ],
        COLORS,
    )

    assert len(presentations) == 1
    presentation = presentations[0]
    assert "Broken-Butterfly" in presentation.summary_text
    assert "Strategy: Broken-Butterfly" in presentation.tooltip_text


def test_build_restored_position_group_presentations_uses_standard_header_metrics() -> None:
    presentations = build_restored_position_group_presentations(
        [
            {
                "symbol": "SPY260528C00753000",
                "quantity": 1,
                "entry_price": 0.35,
                "current_price": 0.39,
                "unrealized_pnl": 4.0,
                "strategy": "butterfly",
                "status": "OPEN",
                "_paper_open_origin": "active_session",
                "opened_at": datetime(2026, 5, 28, 19, 25, 32, tzinfo=UTC).isoformat(),
                "expiration": "2026-05-28",
                "strike": 753.0,
                "option_type": "call",
                "cash_held_dollars": 90.0,
            },
            {
                "symbol": "SPY260528C00754000",
                "quantity": -2,
                "entry_price": 0.10,
                "current_price": 0.06,
                "unrealized_pnl": 8.0,
                "strategy": "butterfly",
                "status": "OPEN",
                "_paper_open_origin": "active_session",
                "opened_at": datetime(2026, 5, 28, 19, 25, 33, tzinfo=UTC).isoformat(),
                "expiration": "2026-05-28",
                "strike": 754.0,
                "option_type": "call",
                "cash_held_dollars": 90.0,
            },
        ],
        COLORS,
        today=date(2026, 5, 28),
    )

    assert len(presentations) == 1
    presentation = presentations[0]
    assert presentation.timestamp_text
    assert presentation.summary_text == "STRATEGY EXECUTING : Reg-Butterfly  |  DTE: 00  |  STATUS: OPEN"
    assert presentation.cash_held_text == "CASH HELD: $90.00"
    assert presentation.pnl_text == "NET P&L +$12.00 (+13.3%)"
    assert presentation.pnl_color == COLORS["positive"]


def test_build_restored_position_group_presentations_uses_net_credit_cash_held_fallback() -> None:
    presentations = build_restored_position_group_presentations(
        [
            {
                "symbol": "SPY260528C00754000",
                "quantity": -9,
                "entry_price": 0.92,
                "current_price": 1.03,
                "unrealized_pnl": -99.0,
                "strategy": "butterfly",
                "status": "OPEN",
                "_paper_open_origin": "active_session",
                "opened_at": datetime(2026, 5, 28, 20, 25, 32, tzinfo=UTC).isoformat(),
                "expiration": "2026-05-28",
                "strike": 754.0,
                "option_type": "call",
            },
            {
                "symbol": "SPY260528C00756000",
                "quantity": 3,
                "entry_price": 0.05,
                "current_price": 0.22,
                "unrealized_pnl": -51.0,
                "strategy": "butterfly",
                "status": "OPEN",
                "_paper_open_origin": "active_session",
                "opened_at": datetime(2026, 5, 28, 20, 25, 33, tzinfo=UTC).isoformat(),
                "expiration": "2026-05-28",
                "strike": 756.0,
                "option_type": "call",
            },
        ],
        COLORS,
        today=date(2026, 5, 28),
    )

    assert len(presentations) == 1
    presentation = presentations[0]
    assert presentation.cash_held_text == "CASH HELD: $813.00"
    assert presentation.pnl_text == "NET P&L -$150.00 (-18.5%)"
    assert presentation.pnl_color == COLORS["negative"]


def test_build_restored_position_group_presentations_uses_absolute_signed_cash_held() -> None:
    presentations = build_restored_position_group_presentations(
        [
            {
                "symbol": "SPY260529C00750000",
                "quantity": -1,
                "entry_price": 1.10,
                "current_price": 1.02,
                "unrealized_pnl": 8.0,
                "strategy": "butterfly",
                "status": "OPEN",
                "_paper_open_origin": "active_session",
                "opened_at": datetime(2026, 5, 29, 14, 30, 0, tzinfo=UTC).isoformat(),
                "expiration": "2026-05-29",
                "strike": 750.0,
                "option_type": "call",
                "cash_held_dollars": -125.0,
            }
        ],
        COLORS,
        today=date(2026, 5, 29),
    )

    assert len(presentations) == 1
    assert presentations[0].cash_held_text == "CASH HELD: $125.00"


def test_build_paper_spread_tree_presentation_uses_absolute_net_leg_cost_fallback() -> None:
    header, _legs = build_paper_spread_tree_presentation(
        {
            "structure": "butterfly",
            "qty": 1,
            "credit": 0.0,
            "mtm_pnl": -20.0,
            "expiration": "2026-05-29",
            "opened_at": datetime(2026, 5, 29, 14, 30, 0, tzinfo=UTC).timestamp(),
            "legs": [
                {"side": "sell_to_open", "qty": 2, "price": 0.90, "type": "call"},
                {"side": "buy_to_open", "qty": 1, "price": 0.45, "type": "call"},
            ],
        },
        date(2026, 5, 29),
        UTC,
        COLORS,
        "EXECUTING",
    )

    # Net entry cost here is negative (-$135). CASH HELD should still display
    # absolute capital at risk from leg-cost fallback.
    assert header.cash_held_text == "CASH HELD: $135.00"
