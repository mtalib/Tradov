#!/usr/bin/env python3
"""Focused tests for G87 late shutdown timer stop helper."""

from Spyder.SpyderG_GUI.SpyderG87_PostWorkerShutdownTimerHelper import (
    build_post_worker_shutdown_timer_plan,
)


def test_build_post_worker_shutdown_timer_plan_returns_empty_when_no_timers_present() -> None:
    plan = build_post_worker_shutdown_timer_plan(
        timer_presence={
            "datetime_timer": False,
            "chart_timer": False,
        }
    )

    assert plan.timer_attrs == ()


def test_build_post_worker_shutdown_timer_plan_selects_only_present_timers() -> None:
    plan = build_post_worker_shutdown_timer_plan(
        timer_presence={
            "datetime_timer": True,
            "chart_timer": False,
        }
    )

    assert plan.timer_attrs == ("datetime_timer",)


def test_build_post_worker_shutdown_timer_plan_preserves_shutdown_order() -> None:
    plan = build_post_worker_shutdown_timer_plan(
        timer_presence={
            "datetime_timer": True,
            "chart_timer": True,
        }
    )

    assert plan.timer_attrs == ("datetime_timer", "chart_timer")
