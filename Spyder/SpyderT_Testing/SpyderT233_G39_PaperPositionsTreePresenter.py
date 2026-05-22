#!/usr/bin/env python3
"""Focused tests for paper positions tree presentation helpers."""

from datetime import date

from Spyder.SpyderG_GUI.SpyderG13_EnhancedWidgets import COLORS
from Spyder.SpyderG_GUI.SpyderG39_PaperPositionsTreePresenter import (
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
    assert presentation.cost_text == "-$125"
    assert presentation.pnl_text == "+$15.00"
    assert presentation.quantity_color == COLORS["negative"]
    assert presentation.cost_color == COLORS["negative"]
    assert presentation.pnl_color == COLORS["positive"]
    assert "Average entry: $1.25" in presentation.tooltip_text
    assert "Mark: $1.10" in presentation.tooltip_text
