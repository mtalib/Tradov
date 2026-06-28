#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovG_GUI
Module: TradovG71_ReadinessGateDecisionHelper.py
Purpose: Pure helper for readiness-gated start-trading decisions
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class StartTradingReadinessGateDecisionPlan:
    """Plan describing how start_trading should react to readiness state."""

    latest_result: dict[str, object]
    blocked: bool
    requires_reason_prompt: bool
    restore_start_button_on_block: bool
    sync_go_no_go_on_block: bool
    block_audit_action: str | None
    block_audit_decision: str | None
    block_audit_reason: str


def build_start_trading_readiness_gate_decision_plan(
    *,
    decision: object,
    last_readiness_result: object,
    from_queued: bool,
) -> StartTradingReadinessGateDecisionPlan:
    """Decide how the start-trading readiness gate should behave."""
    latest_result = dict(last_readiness_result) if isinstance(last_readiness_result, Mapping) else {}
    blocked = str(decision) == "NO"

    return StartTradingReadinessGateDecisionPlan(
        latest_result=latest_result,
        blocked=blocked,
        requires_reason_prompt=False,
        restore_start_button_on_block=(blocked and from_queued),
        sync_go_no_go_on_block=(blocked and from_queued),
        block_audit_action="blocked" if blocked else None,
        block_audit_decision="NO hard-block" if blocked else None,
        block_audit_reason="",
    )
