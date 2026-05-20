#!/usr/bin/env python3
"""Focused tests for G101 recent decision-flow fetch helper."""

from __future__ import annotations

from Spyder.SpyderG_GUI.SpyderG101_RecentDecisionFlowFetchHelper import (
    build_recent_decision_flow_fetch_plan,
)


def test_build_recent_decision_flow_fetch_plan_uses_live_request_mode() -> None:
    plan = build_recent_decision_flow_fetch_plan(live_mode=True, limit=4)

    assert plan.run_mode == "live"
    assert plan.limit == 4
    assert plan.fallback_result == {
        "limit": 4,
        "dispatch": [],
        "drops": [],
        "decision_log": None,
    }


def test_build_recent_decision_flow_fetch_plan_uses_paper_request_mode() -> None:
    plan = build_recent_decision_flow_fetch_plan(live_mode=False, limit=2)

    assert plan.run_mode == "paper"
    assert plan.limit == 2
    assert plan.fallback_result == {
        "limit": 2,
        "dispatch": [],
        "drops": [],
        "decision_log": None,
    }
