#!/usr/bin/env python3
"""Focused tests for G103 LIVE-to-PAPER switch helper."""

from __future__ import annotations

from Spyder.SpyderG_GUI.SpyderG103_LiveToPaperSwitchHelper import (
    build_live_to_paper_switch_plan,
)


def test_build_live_to_paper_switch_plan_includes_open_positions_warning() -> None:
    plan = build_live_to_paper_switch_plan(open_positions_count=3)

    assert plan.open_positions_warning is not None
    assert plan.open_positions_warning.dialog_title == "Open Positions Detected"
    assert "You still have 3 open position(s) at Tradier." in plan.open_positions_warning.dialog_text
    assert plan.open_positions_warning.declined_log_message == (
        "Switch to PAPER cancelled — open positions remain"
    )
    assert plan.final_confirmation.dialog_title == "Switch to Paper Trading"


def test_build_live_to_paper_switch_plan_omits_warning_when_no_open_positions() -> None:
    plan = build_live_to_paper_switch_plan(open_positions_count=0)

    assert plan.open_positions_warning is None
    assert plan.final_confirmation.dialog_text == (
        "Switch to PAPER Trading?\n"
        "Simulated fills only — no real orders will be placed."
    )
    assert plan.final_confirmation.declined_log_message == "Switch to PAPER cancelled by user"
