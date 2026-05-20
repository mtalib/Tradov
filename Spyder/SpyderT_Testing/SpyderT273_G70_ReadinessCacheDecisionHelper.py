#!/usr/bin/env python3
"""Focused tests for G70 readiness cache-decision helper."""

from Spyder.SpyderG_GUI.SpyderG70_ReadinessCacheDecisionHelper import (
    build_readiness_cache_decision_plan,
)


def test_build_readiness_cache_decision_plan_reuses_fresh_cached_result() -> None:
    plan = build_readiness_cache_decision_plan(
        last_readiness_ts=100.0,
        last_readiness_result={"decision": "OK"},
        now=150.0,
        ttl_seconds=120,
    )

    assert plan.cached_decision == "OK"
    assert plan.refresh_required is False


def test_build_readiness_cache_decision_plan_refreshes_expired_or_invalid_cache() -> None:
    expired_plan = build_readiness_cache_decision_plan(
        last_readiness_ts=100.0,
        last_readiness_result={"decision": "OK"},
        now=250.0,
        ttl_seconds=120,
    )
    invalid_plan = build_readiness_cache_decision_plan(
        last_readiness_ts=None,
        last_readiness_result=None,
        now=150.0,
        ttl_seconds=120,
    )

    assert expired_plan.cached_decision is None
    assert expired_plan.refresh_required is True
    assert invalid_plan.cached_decision is None
    assert invalid_plan.refresh_required is True
