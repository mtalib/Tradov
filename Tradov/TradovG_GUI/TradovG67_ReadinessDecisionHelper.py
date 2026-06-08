#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovG_GUI
Module: TradovG67_ReadinessDecisionHelper.py
Purpose: Pure helper for trading-readiness snapshot evaluation
"""

from __future__ import annotations

from collections.abc import Mapping

from Tradov.TradovG_GUI.TradovG69_LiveDataStatusHelper import (
    is_live_equivalent_data_status,
)


REDUCED_RISK_EVENT_CLOCK_STATES = frozenset({"pre", "live", "post"})


def build_trading_readiness_evaluation(
    snapshot: Mapping[str, object],
) -> dict[str, object]:
    """Evaluate trading readiness decision from an immutable snapshot."""
    reasons: list[str] = []
    warnings: list[str] = []

    if bool(snapshot.get("is_weekend", False)):
        reasons.append("Market is closed (weekend)")
    if not bool(snapshot.get("is_market_hours", True)):
        reasons.append("Market is closed (outside regular trading hours)")

    startup_state = snapshot.get("startup_state", {})
    if isinstance(startup_state, dict):
        if startup_state.get("live_blocking", False):
            reasons.append("A03 readiness validation reports live-blocking configuration errors")
        if startup_state.get("safe_fallback_applied", False):
            reasons.append("Automation safe fallback is active from startup readiness validation")

    if not bool(snapshot.get("api_connected", False)):
        reasons.append("Tradier execution API is disconnected")
    if not bool(snapshot.get("mkt_data_connected", False)):
        reasons.append("Market data feed is disconnected")

    raw_data_label = snapshot.get("data_status_label", "")
    data_label = str(raw_data_label).strip().upper()
    if data_label and not is_live_equivalent_data_status(raw_data_label):
        warnings.append(f"Data status is {data_label} (not explicit LIVE)")

    if bool(snapshot.get("event_clock_enabled", True)):
        state_name = str(snapshot.get("event_clock_state", "clear"))
        if state_name in REDUCED_RISK_EVENT_CLOCK_STATES:
            warnings.append(
                f"Event-clock state is {state_name}; reduced-risk policy recommended"
            )

    decision = "OK"
    conditional = False
    if reasons:
        decision = "NO"
    elif warnings:
        conditional = True

    return {
        "decision": decision,
        "conditional": conditional,
        "checked_at_et": str(snapshot.get("checked_at_et", "")),
        "reasons": reasons,
        "warnings": warnings,
        "startup_state": startup_state,
    }
