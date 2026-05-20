#!/usr/bin/env python3
"""Focused tests for G109 regime-pill state helper."""

from __future__ import annotations

from Spyder.SpyderG_GUI.SpyderG109_RegimePillStateHelper import (
    build_regime_pill_state_plan,
)


def test_build_regime_pill_state_plan_prefers_live_s07_bull_state() -> None:
    plan = build_regime_pill_state_plan(
        metrics={
            "SWAN": {"value": 1.2},
            "DIX": {"value": 47.0},
            "SKEW": {"value": 120.0},
            "GEX": {"value": 1.0},
        },
        regime_sticky=None,
        vix_candidate_regime="RANGE",
        vix_candidate_count=0,
        vix_snapshot=None,
    )

    assert plan.s07_live is True
    assert plan.regime == "BULL"
    assert plan.next_regime_sticky == "BULL"
    assert plan.next_vix_candidate_regime == "RANGE"
    assert plan.next_vix_candidate_count == 1


def test_build_regime_pill_state_plan_debounces_vix_fallback_before_commit() -> None:
    plan = build_regime_pill_state_plan(
        metrics={},
        regime_sticky=None,
        vix_candidate_regime="CRISIS",
        vix_candidate_count=2,
        vix_snapshot={
            "VIX": {"last": 36.0},
            "VIX9D": {"last": 38.0},
            "SPX": {"change_pct": -2.0},
        },
    )

    assert plan.s07_live is False
    assert plan.regime == "CRISIS"
    assert plan.next_regime_sticky is None
    assert plan.next_vix_candidate_regime == "CRISIS"
    assert plan.next_vix_candidate_count == 3
