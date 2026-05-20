#!/usr/bin/env python3
"""Focused tests for G66 readiness startup-state helper."""

from Spyder.SpyderG_GUI.SpyderG66_ReadinessStartupStateHelper import (
    build_readiness_startup_state_plan,
)


def test_build_readiness_startup_state_plan_reuses_nonempty_dict() -> None:
    startup_state = {"checked": True}

    plan = build_readiness_startup_state_plan(startup_state)

    assert plan.startup_state == startup_state
    assert plan.refresh_cache is False


def test_build_readiness_startup_state_plan_refreshes_empty_or_invalid_state() -> None:
    empty_plan = build_readiness_startup_state_plan({})
    invalid_plan = build_readiness_startup_state_plan(None)

    assert empty_plan.startup_state == {}
    assert empty_plan.refresh_cache is True
    assert invalid_plan.startup_state == {}
    assert invalid_plan.refresh_cache is True
