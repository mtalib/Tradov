#!/usr/bin/env python3
"""Focused tests for G75 SessionSupervisor start-attempt helper."""

from importlib import import_module


build_session_supervisor_start_attempt_plan = import_module(
    "Spyder.SpyderG_GUI.SpyderG75_SessionSupervisorStartAttemptHelper"
).build_session_supervisor_start_attempt_plan


def test_build_session_supervisor_start_attempt_plan_accepts_success() -> None:
    plan = build_session_supervisor_start_attempt_plan(
        started=True,
        error_text=None,
    )

    assert plan.return_value is True
    assert plan.clear_supervisor is False
    assert plan.log_message is None


def test_build_session_supervisor_start_attempt_plan_clears_on_false_start() -> None:
    plan = build_session_supervisor_start_attempt_plan(
        started=False,
        error_text=None,
    )

    assert plan.return_value is False
    assert plan.clear_supervisor is True
    assert plan.log_message is None


def test_build_session_supervisor_start_attempt_plan_logs_and_clears_on_error() -> None:
    plan = build_session_supervisor_start_attempt_plan(
        started=None,
        error_text="boom",
    )

    assert plan.return_value is False
    assert plan.clear_supervisor is True
    assert plan.log_message == "❌ Unified session start failed: boom"
