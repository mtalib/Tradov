#!/usr/bin/env python3
"""Focused tests for G86 shutdown timer stop helper."""

from Spyder.SpyderG_GUI.SpyderG86_ShutdownTimerStopHelper import (
    build_shutdown_timer_stop_plan,
)


def test_build_shutdown_timer_stop_plan_returns_empty_when_no_timers_present() -> None:
    plan = build_shutdown_timer_stop_plan(
        timer_presence={
            "_real_data_timer": False,
            "_fast_quote_timer": False,
            "_check_timer": False,
            "_decision_flow_timer": False,
        }
    )

    assert plan.timer_attrs == ()


def test_build_shutdown_timer_stop_plan_selects_only_present_timers() -> None:
    plan = build_shutdown_timer_stop_plan(
        timer_presence={
            "_real_data_timer": True,
            "_fast_quote_timer": False,
            "_check_timer": True,
            "_decision_flow_timer": False,
        }
    )

    assert plan.timer_attrs == ("_real_data_timer", "_check_timer")


def test_build_shutdown_timer_stop_plan_preserves_shutdown_order() -> None:
    plan = build_shutdown_timer_stop_plan(
        timer_presence={
            "_real_data_timer": True,
            "_fast_quote_timer": True,
            "_check_timer": True,
            "_decision_flow_timer": True,
        }
    )

    assert plan.timer_attrs == (
        "_real_data_timer",
        "_fast_quote_timer",
        "_check_timer",
        "_decision_flow_timer",
    )