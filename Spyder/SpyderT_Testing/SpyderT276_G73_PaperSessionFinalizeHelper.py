#!/usr/bin/env python3
"""Focused tests for G73 delayed paper-session finalization helper."""

from Spyder.SpyderG_GUI.SpyderG73_PaperSessionFinalizeHelper import (
    build_paper_session_finalize_outcome_plan,
)


def test_build_paper_session_finalize_outcome_plan_adopts_running_session_after_hours() -> None:
    plan = build_paper_session_finalize_outcome_plan(
        market_open=False,
        start_succeeded=True,
        show_failure_dialog=True,
    )

    assert plan.action == "adopt_running"
    assert plan.show_dialog is False


def test_build_paper_session_finalize_outcome_plan_marks_start_failure() -> None:
    plan = build_paper_session_finalize_outcome_plan(
        market_open=True,
        start_succeeded=False,
        show_failure_dialog=False,
    )

    assert plan.action == "start_failed"
    assert plan.show_dialog is False


def test_build_paper_session_finalize_outcome_plan_adopts_running_session() -> None:
    plan = build_paper_session_finalize_outcome_plan(
        market_open=True,
        start_succeeded=True,
        show_failure_dialog=True,
    )

    assert plan.action == "adopt_running"
    assert plan.show_dialog is False
