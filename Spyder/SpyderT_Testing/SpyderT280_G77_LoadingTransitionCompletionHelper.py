#!/usr/bin/env python3
"""Focused tests for G77 loading-transition completion helper."""

from Spyder.SpyderG_GUI.SpyderG77_LoadingTransitionCompletionHelper import (
    build_loading_transition_completion_plan,
)


def test_build_loading_transition_completion_plan_noops_for_stale_generation() -> None:
    plan = build_loading_transition_completion_plan(
        expected_generation=2,
        current_generation=3,
        shutdown_in_progress=False,
        session_start_pending=True,
        trading_active=False,
        supervisor_running=False,
    )

    assert plan.action == "noop"
    assert plan.finalize_pending_start is False
    assert plan.set_timer_inactive is False
    assert plan.activate_button is False


def test_build_loading_transition_completion_plan_cancels_during_shutdown() -> None:
    plan = build_loading_transition_completion_plan(
        expected_generation=3,
        current_generation=3,
        shutdown_in_progress=True,
        session_start_pending=True,
        trading_active=False,
        supervisor_running=False,
    )

    assert plan.action == "cancel_loading"
    assert plan.finalize_pending_start is False
    assert plan.set_timer_inactive is False
    assert plan.activate_button is False


def test_build_loading_transition_completion_plan_completes_and_activates_when_running() -> None:
    plan = build_loading_transition_completion_plan(
        expected_generation=3,
        current_generation=3,
        shutdown_in_progress=False,
        session_start_pending=True,
        trading_active=False,
        supervisor_running=True,
    )

    assert plan.action == "complete"
    assert plan.finalize_pending_start is True
    assert plan.set_timer_inactive is True
    assert plan.activate_button is True
