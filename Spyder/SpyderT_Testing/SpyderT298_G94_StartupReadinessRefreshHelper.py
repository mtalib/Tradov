#!/usr/bin/env python3
"""Focused tests for G94 startup-readiness refresh helper."""

from __future__ import annotations

from Spyder.SpyderG_GUI.SpyderG94_StartupReadinessRefreshHelper import (
    build_startup_readiness_refresh_plan,
)


def test_build_startup_readiness_refresh_plan_skips_during_shutdown() -> None:
    plan = build_startup_readiness_refresh_plan(shutdown_in_progress=True)

    assert plan.should_skip is True
    assert plan.step_names == ()


def test_build_startup_readiness_refresh_plan_returns_ordered_steps() -> None:
    plan = build_startup_readiness_refresh_plan(shutdown_in_progress=False)

    assert plan.should_skip is False
    assert plan.step_names == (
        "load_multiplier",
        "collect_state",
        "emit_logs",
    )