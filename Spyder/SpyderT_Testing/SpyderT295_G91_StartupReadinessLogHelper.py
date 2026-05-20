#!/usr/bin/env python3
"""Focused tests for G91 startup-readiness log helper."""

from __future__ import annotations

from Spyder.SpyderG_GUI.SpyderG91_StartupReadinessLogHelper import (
    build_startup_readiness_log_plan,
)


def test_build_startup_readiness_log_plan_stays_quiet_during_preconnect_idle() -> None:
    plan = build_startup_readiness_log_plan(
        state={
            "pending": False,
            "checked": True,
            "mode": "paper",
            "warnings": [],
            "errors": [],
            "safe_fallback_applied": False,
            "live_blocking": False,
        },
        preconnect_idle=True,
        warning_color="#e6a817",
    )

    assert plan.log_messages == ()
    assert plan.start_button_plan is None


def test_build_startup_readiness_log_plan_returns_unavailable_message() -> None:
    plan = build_startup_readiness_log_plan(
        state={"checked": False, "source": "unavailable: mock failure"},
        preconnect_idle=False,
        warning_color="#e6a817",
    )

    assert plan.log_messages == (
        "ℹ️ Startup readiness state unavailable (unavailable: mock failure)",
    )
    assert plan.start_button_plan is None


def test_build_startup_readiness_log_plan_returns_safe_mode_button_plan() -> None:
    plan = build_startup_readiness_log_plan(
        state={
            "checked": True,
            "mode": "paper",
            "warnings": ["warn-a"],
            "errors": ["err-a"],
            "safe_fallback_applied": True,
            "live_blocking": False,
        },
        preconnect_idle=False,
        warning_color="#ffcc00",
    )

    assert plan.log_messages == (
        "⚠️ STARTUP SAFE MODE (PAPER): automation disabled by readiness validation",
        "⚠️ Readiness issues: 1 blocking error(s), 1 warning(s)",
    )
    assert plan.start_button_plan is not None
    assert plan.start_button_plan.text == "SAFE MODE (AUTO OFF)"
    assert plan.start_button_plan.style_sheet == "background-color: #ffcc00; color: black;"
    assert "automation.enabled=false" in plan.start_button_plan.tool_tip


def test_build_startup_readiness_log_plan_filters_market_closed_warning() -> None:
    plan = build_startup_readiness_log_plan(
        state={
            "checked": True,
            "mode": "paper",
            "warnings": [
                "Market is closed (outside regular trading hours)",
                "warn-a",
            ],
            "errors": [],
            "safe_fallback_applied": False,
            "live_blocking": False,
        },
        preconnect_idle=False,
        warning_color="#e6a817",
    )

    assert plan.log_messages == (
        "✅ Startup readiness validated (mode=PAPER, warnings=1, errors=0)",
        "⚠️ Startup readiness warning(s): warn-a",
    )
    assert plan.start_button_plan is None