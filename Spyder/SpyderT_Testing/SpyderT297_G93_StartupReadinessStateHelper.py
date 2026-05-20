#!/usr/bin/env python3
"""Focused tests for G93 startup-readiness state helper."""

from __future__ import annotations

from Spyder.SpyderG_GUI.SpyderG93_StartupReadinessStateHelper import (
    build_startup_readiness_state_plan,
)


def test_build_startup_readiness_state_plan_marks_safe_fallback_in_paper_mode() -> None:
    plan = build_startup_readiness_state_plan(
        env_mode="",
        runtime_paper_mode=None,
        configured_mode="paper",
        automation_enabled=False,
        warnings=["paper mode fallback"],
        errors=["execution.degrade_size_multiplier out of bounds"],
        market_hours_open=True,
        preconnect_idle=False,
    )

    assert plan.mode == "paper"
    assert plan.automation_enabled is False
    assert plan.safe_fallback_applied is True
    assert plan.live_blocking is False


def test_build_startup_readiness_state_plan_prefers_env_mode() -> None:
    plan = build_startup_readiness_state_plan(
        env_mode="paper",
        runtime_paper_mode=None,
        configured_mode="live",
        automation_enabled=True,
        warnings=[],
        errors=[],
        market_hours_open=True,
        preconnect_idle=True,
    )

    assert plan.mode == "paper"


def test_build_startup_readiness_state_plan_uses_runtime_paper_mode_bool() -> None:
    plan = build_startup_readiness_state_plan(
        env_mode="",
        runtime_paper_mode=False,
        configured_mode="paper",
        automation_enabled=True,
        warnings=[],
        errors=["err-a"],
        market_hours_open=True,
        preconnect_idle=True,
    )

    assert plan.mode == "live"
    assert plan.live_blocking is True


def test_build_startup_readiness_state_plan_appends_market_closed_warning_once() -> None:
    plan = build_startup_readiness_state_plan(
        env_mode="",
        runtime_paper_mode=None,
        configured_mode="paper",
        automation_enabled=True,
        warnings=["warn-a"],
        errors=[],
        market_hours_open=False,
        preconnect_idle=False,
    )

    assert list(plan.warnings) == [
        "warn-a",
        "Market is closed (outside regular trading hours)",
    ]