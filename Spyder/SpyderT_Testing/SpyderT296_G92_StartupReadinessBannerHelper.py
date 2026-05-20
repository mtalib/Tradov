#!/usr/bin/env python3
"""Focused tests for G92 startup-readiness banner helper."""

from __future__ import annotations

from Spyder.SpyderG_GUI.SpyderG92_StartupReadinessBannerHelper import (
    build_startup_readiness_banner_plan,
)


def test_build_startup_readiness_banner_plan_stays_quiet_during_preconnect_idle() -> None:
    plan = build_startup_readiness_banner_plan(
        state={
            "pending": False,
            "checked": True,
            "mode": "paper",
            "warnings": [],
            "errors": [],
            "safe_fallback_applied": False,
            "live_blocking": False,
        },
        startup_hms="09:30:00",
        preconnect_idle=True,
    )

    assert plan.system_log_messages == ()


def test_build_startup_readiness_banner_plan_returns_unavailable_message() -> None:
    plan = build_startup_readiness_banner_plan(
        state={"checked": False, "source": "unavailable: mock failure"},
        startup_hms="09:30:00",
        preconnect_idle=False,
    )

    assert plan.system_log_messages == (
        "[09:30:00] ℹ️ STARTUP READINESS: unavailable (unavailable: mock failure)",
    )


def test_build_startup_readiness_banner_plan_returns_safe_mode_messages() -> None:
    plan = build_startup_readiness_banner_plan(
        state={
            "checked": True,
            "mode": "paper",
            "warnings": ["warn-a"],
            "errors": ["err-a"],
            "safe_fallback_applied": True,
            "live_blocking": False,
        },
        startup_hms="09:30:00",
        preconnect_idle=False,
    )

    assert plan.system_log_messages == (
        "[09:30:00] ⚠️ STARTUP READINESS: SAFE MODE ACTIVE (PAPER)",
        "[09:30:00] ⚠️ automation.enabled=false due to 1 blocking config error(s)",
    )


def test_build_startup_readiness_banner_plan_filters_market_closed_warning() -> None:
    plan = build_startup_readiness_banner_plan(
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
        startup_hms="09:30:00",
        preconnect_idle=False,
    )

    assert plan.system_log_messages == (
        "[09:30:00] ✅ STARTUP READINESS: mode=PAPER warnings=1 errors=0",
        "[09:30:00] ⚠️ STARTUP READINESS WARNING(S): warn-a",
    )
