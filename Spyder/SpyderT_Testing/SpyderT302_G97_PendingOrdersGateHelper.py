#!/usr/bin/env python3
"""Focused tests for G97 pending-orders gate helper."""

from __future__ import annotations

from Spyder.SpyderG_GUI.SpyderG97_PendingOrdersGateHelper import (
    build_pending_orders_gate_outcome,
    build_pending_orders_gate_prompt,
)


def test_build_pending_orders_gate_prompt_formats_preview_and_overflow_suffix() -> None:
    pending_orders = [
        {
            "id": index,
            "symbol": "SPY",
            "side": "buy" if index % 2 else "sell",
            "quantity": index,
            "status": "open",
        }
        for index in range(1, 12)
    ]

    prompt = build_pending_orders_gate_prompt(
        pending_orders=pending_orders,
        pending_mode_name="paper",
        target_label="LIVE",
    )

    assert prompt.prompt_title == "Pending Paper/Local Orders Must Be Cancelled"
    assert "You have 11 pending paper/local order(s):" in prompt.prompt_text
    assert "#1  SPY  BUY  qty 1  [OPEN]" in prompt.prompt_text
    assert "… and 1 more" in prompt.prompt_text
    assert prompt.declined_log_message == "Switch to LIVE cancelled — pending paper/local orders remain"


def test_build_pending_orders_gate_outcome_returns_live_messages() -> None:
    outcome = build_pending_orders_gate_outcome(
        pending_mode_name="live",
        support_suffix="Contact support.",
        cancelled_count=2,
        failed_count=1,
    )

    assert outcome.failure_dialog_title == "Cancellation Failed"
    assert outcome.failure_dialog_text == "1 order(s) could not be cancelled.\nContact support."
    assert outcome.success_log_message == "✅ 2 pending LIVE order(s) cancelled — continuing switch"
