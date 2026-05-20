#!/usr/bin/env python3
"""Pure fetch-plan helpers for recent decision-flow diagnostics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecentDecisionFlowFetchPlan:
    """Pure request and fallback plan for recent decision-flow diagnostics."""

    run_mode: str
    limit: int
    fallback_result: dict[str, object]


def build_recent_decision_flow_fetch_plan(*, live_mode: bool, limit: int) -> RecentDecisionFlowFetchPlan:
    """Return the request parameters and empty fallback payload for panel fetches."""
    return RecentDecisionFlowFetchPlan(
        run_mode="live" if live_mode else "paper",
        limit=limit,
        fallback_result={
            "limit": limit,
            "dispatch": [],
            "drops": [],
            "decision_log": None,
        },
    )
