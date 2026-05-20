#!/usr/bin/env python3
"""Focused tests for G113 close-strategy success helper."""

from __future__ import annotations

from Spyder.SpyderG_GUI.SpyderG113_CloseStrategySuccessHelper import (
    build_close_strategy_success_plan,
)


def test_build_close_strategy_success_plan_prefers_nested_order_id_and_formats_dialog() -> None:
    plan = build_close_strategy_success_plan(
        strategy_name="Iron Condor",
        num_legs=4,
        response={"order": {"id": 98765}, "id": 12345},
    )

    assert plan.order_id == 98765
    assert plan.log_message == "✅ Close order submitted for Iron Condor — order ID: 98765"
    assert plan.dialog_title == "Close Order Submitted"
    assert "Strategy 'Iron Condor' close order submitted successfully." in plan.dialog_text
    assert "Order ID: 98765" in plan.dialog_text
    assert "Legs: 4" in plan.dialog_text
