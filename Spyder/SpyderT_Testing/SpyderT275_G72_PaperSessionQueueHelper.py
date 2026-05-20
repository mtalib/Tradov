#!/usr/bin/env python3
"""Focused tests for G72 paper-session queue helper."""

from Spyder.SpyderG_GUI.SpyderG72_PaperSessionQueueHelper import (
    build_paper_session_queue_plan,
)


def test_build_paper_session_queue_plan_cancels_when_shutdown_in_progress() -> None:
    plan = build_paper_session_queue_plan(
        shutdown_in_progress=True,
        is_paper_mode=True,
        trading_active=False,
        supervisor_running=False,
        session_start_pending=False,
        show_failure_dialog=True,
        delay_ms=25_000,
    )

    assert plan.action == "cancel_loading"
    assert plan.set_pending is False
    assert plan.set_show_failure_dialog is False


def test_build_paper_session_queue_plan_begins_loading_when_delay_is_positive() -> None:
    plan = build_paper_session_queue_plan(
        shutdown_in_progress=False,
        is_paper_mode=True,
        trading_active=False,
        supervisor_running=False,
        session_start_pending=False,
        show_failure_dialog=True,
        delay_ms=25_000,
    )

    assert plan.action == "begin_loading"
    assert plan.set_pending is True
    assert plan.pending_value is True
    assert plan.set_show_failure_dialog is True
    assert plan.show_failure_dialog is True
    assert plan.delay_ms == 25_000


def test_build_paper_session_queue_plan_finalizes_immediately_when_delay_elapsed() -> None:
    plan = build_paper_session_queue_plan(
        shutdown_in_progress=False,
        is_paper_mode=True,
        trading_active=False,
        supervisor_running=False,
        session_start_pending=False,
        show_failure_dialog=False,
        delay_ms=0,
    )

    assert plan.action == "finalize_now"
    assert plan.set_pending is True
    assert plan.pending_value is True
    assert plan.set_show_failure_dialog is True
    assert plan.show_failure_dialog is False
    assert plan.delay_ms is None