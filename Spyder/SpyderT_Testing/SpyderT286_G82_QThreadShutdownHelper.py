#!/usr/bin/env python3
"""Focused tests for G82 Qt thread shutdown helper."""

from Spyder.SpyderG_GUI.SpyderG82_QThreadShutdownHelper import build_qthread_shutdown_plan


def test_build_qthread_shutdown_plan_completes_after_quit_wait() -> None:
    plan = build_qthread_shutdown_plan(
        stop_succeeded_after_quit=True,
        stop_succeeded_after_terminate=None,
        label="market_thread",
        wait_ms=3000,
        terminate_wait_ms=5000,
    )

    assert plan.action == "done"
    assert plan.warning_message is None
    assert plan.error_message is None


def test_build_qthread_shutdown_plan_requests_terminate_after_quit_timeout() -> None:
    plan = build_qthread_shutdown_plan(
        stop_succeeded_after_quit=False,
        stop_succeeded_after_terminate=None,
        label="market_thread",
        wait_ms=3000,
        terminate_wait_ms=5000,
    )

    assert plan.action == "terminate_and_wait"
    assert plan.warning_message == "market_thread did not stop within 3000ms; terminating thread"
    assert plan.error_message is None


def test_build_qthread_shutdown_plan_completes_after_terminate_wait() -> None:
    plan = build_qthread_shutdown_plan(
        stop_succeeded_after_quit=False,
        stop_succeeded_after_terminate=True,
        label="market_thread",
        wait_ms=3000,
        terminate_wait_ms=5000,
    )

    assert plan.action == "done"
    assert plan.warning_message is None
    assert plan.error_message is None


def test_build_qthread_shutdown_plan_logs_error_after_terminate_timeout() -> None:
    plan = build_qthread_shutdown_plan(
        stop_succeeded_after_quit=False,
        stop_succeeded_after_terminate=False,
        label="market_thread",
        wait_ms=3000,
        terminate_wait_ms=5000,
    )

    assert plan.action == "log_error"
    assert plan.warning_message is None
    assert plan.error_message == "market_thread still running after terminate wait of 5000ms"