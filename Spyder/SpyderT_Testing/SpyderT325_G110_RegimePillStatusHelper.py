#!/usr/bin/env python3
"""Focused tests for G110 regime-pill status helper."""

from __future__ import annotations

from Spyder.SpyderG_GUI.SpyderG110_RegimePillStatusHelper import (
    build_regime_pill_status_plan,
)


def test_build_regime_pill_status_plan_uses_regime_defaults_when_execution_truth_blank() -> None:
    plan = build_regime_pill_status_plan(
        regime="BULL",
        swan=2.2,
        s07_live=True,
        execution_truth={"stance": "", "gate": ""},
        fallback_stress=None,
    )

    assert plan.stance == "BULLISH"
    assert plan.stress == "HIGH"
    assert plan.gate == "BULL TREND"


def test_build_regime_pill_status_plan_preserves_execution_truth_and_fallback_stress() -> None:
    plan = build_regime_pill_status_plan(
        regime="RANGE",
        swan=1.2,
        s07_live=False,
        execution_truth={"stance": "choppy", "gate": "crisis"},
        fallback_stress="medium",
    )

    assert plan.stance == "CHOPPY"
    assert plan.stress == "MEDIUM"
    assert plan.gate == "CRISIS"
