#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovG_GUI
Module: TradovG70_ReadinessCacheDecisionHelper.py
Purpose: Pure helper for readiness cache TTL decisions
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping


@dataclass(frozen=True)
class ReadinessCacheDecisionPlan:
    """Plan describing whether cached readiness state can be reused."""

    cached_decision: str | None
    refresh_required: bool


def build_readiness_cache_decision_plan(
    *,
    last_readiness_ts: object,
    last_readiness_result: object,
    now: float,
    ttl_seconds: object,
) -> ReadinessCacheDecisionPlan:
    """Decide whether a cached readiness decision is still fresh enough to use."""
    if isinstance(last_readiness_ts, (int, float)) and isinstance(last_readiness_result, Mapping):
        age = now - float(last_readiness_ts)
        if age <= float(ttl_seconds):
            return ReadinessCacheDecisionPlan(
                cached_decision=str(last_readiness_result.get("decision", "NO")),
                refresh_required=False,
            )

    return ReadinessCacheDecisionPlan(
        cached_decision=None,
        refresh_required=True,
    )
