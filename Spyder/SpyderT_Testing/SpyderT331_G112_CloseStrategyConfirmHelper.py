#!/usr/bin/env python3
"""Focused tests for G112 close-strategy confirmation helper."""

from __future__ import annotations

from Spyder.SpyderG_GUI.SpyderG112_CloseStrategyConfirmHelper import (
    build_close_strategy_confirm_plan,
)


def test_build_close_strategy_confirm_plan_formats_strategy_summary_and_styles() -> None:
    plan = build_close_strategy_confirm_plan(
        strategy_data={
            "strategy": "Iron Condor",
            "timestamp": "2026-05-15 09:45:00",
            "dte": 0,
            "legs": [1, 2, 3, 4],
            "net_pnl": "$125",
            "pct_return": "4.2%",
            "status": "OPEN",
        },
        colors={"negative": "#f00", "panel": "#222", "text": "#eee"},
    )

    assert plan.title == "Close Strategy"
    assert "CLOSE ENTIRE STRATEGY" in plan.text
    assert "Iron Condor" in plan.text
    assert "Legs:         4 positions" in plan.text
    assert plan.yes_button_text == "CLOSE ALL POSITIONS"
    assert plan.yes_button_style == "background-color: #f00; color: white; padding: 5px 15px;"
    assert plan.cancel_button_style == "background-color: #222; color: white; padding: 5px 15px;"
    assert "font-family: monospace;" in plan.dialog_style
    assert "color: #eee;" in plan.dialog_style
