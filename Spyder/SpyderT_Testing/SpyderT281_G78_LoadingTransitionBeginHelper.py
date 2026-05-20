#!/usr/bin/env python3
"""Focused tests for G78 loading transition begin helper."""

from Spyder.SpyderG_GUI.SpyderG78_LoadingTransitionBeginHelper import (
    build_loading_transition_begin_plan,
)


def test_build_loading_transition_begin_plan_noops_outside_paper() -> None:
    plan = build_loading_transition_begin_plan(
        is_paper_mode=False,
        current_generation=4,
        delay_ms=25000,
        qtimer_available=True,
    )

    assert plan.action == "noop"
    assert plan.next_generation is None
    assert plan.delay_ms is None
    assert plan.set_timer_active is False
    assert plan.schedule_with_qtimer is False


def test_build_loading_transition_begin_plan_schedules_with_qtimer() -> None:
    plan = build_loading_transition_begin_plan(
        is_paper_mode=True,
        current_generation=4,
        delay_ms=25000,
        qtimer_available=True,
    )

    assert plan.action == "begin"
    assert plan.next_generation == 5
    assert plan.delay_ms == 25000
    assert plan.set_timer_active is True
    assert plan.schedule_with_qtimer is True


def test_build_loading_transition_begin_plan_completes_immediately_without_qtimer() -> None:
    plan = build_loading_transition_begin_plan(
        is_paper_mode=True,
        current_generation=1,
        delay_ms=-5,
        qtimer_available=False,
    )

    assert plan.action == "begin"
    assert plan.next_generation == 2
    assert plan.delay_ms == 0
    assert plan.set_timer_active is True
    assert plan.schedule_with_qtimer is False