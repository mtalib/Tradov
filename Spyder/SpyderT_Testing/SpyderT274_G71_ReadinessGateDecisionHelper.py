#!/usr/bin/env python3
"""Focused tests for G71 readiness gate-decision helper."""

from Spyder.SpyderG_GUI.SpyderG71_ReadinessGateDecisionHelper import (
    build_start_trading_readiness_gate_decision_plan,
)


def test_build_start_trading_readiness_gate_decision_plan_blocks_queued_start() -> None:
    plan = build_start_trading_readiness_gate_decision_plan(
        decision="NO",
        last_readiness_result={"decision": "NO"},
        from_queued=True,
    )

    assert plan.latest_result == {"decision": "NO"}
    assert plan.blocked is True
    assert plan.requires_reason_prompt is False
    assert plan.restore_start_button_on_block is True
    assert plan.sync_go_no_go_on_block is True
    assert plan.block_audit_action == "blocked"
    assert plan.block_audit_decision == "NO hard-block"
    assert plan.block_audit_reason == ""


def test_build_start_trading_readiness_gate_decision_plan_requests_reason_for_conditional_result() -> None:
    plan = build_start_trading_readiness_gate_decision_plan(
        decision="OK",
        last_readiness_result={"decision": "OK", "conditional": True},
        from_queued=False,
    )

    assert plan.latest_result == {"decision": "OK", "conditional": True}
    assert plan.blocked is False
    assert plan.requires_reason_prompt is True
    assert plan.restore_start_button_on_block is False
    assert plan.sync_go_no_go_on_block is False
    assert plan.block_audit_action is None
    assert plan.block_audit_decision is None
