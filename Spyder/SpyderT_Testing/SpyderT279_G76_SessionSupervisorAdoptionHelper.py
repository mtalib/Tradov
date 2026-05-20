#!/usr/bin/env python3
"""Focused tests for G76 SessionSupervisor adoption helper."""

from Spyder.SpyderG_GUI.SpyderG76_SessionSupervisorAdoptionHelper import (
    build_session_supervisor_adoption_plan,
)


def test_build_session_supervisor_adoption_plan_marks_after_hours_paper_start() -> None:
    plan = build_session_supervisor_adoption_plan(
        trading_mode_value="PAPER",
        loading_timer_active=False,
        was_active=False,
        market_open=False,
    )

    assert plan.set_start_button_active is True
    assert plan.log_messages == ()
    assert plan.follow_up_action == "refresh_paper_positions"


def test_build_session_supervisor_adoption_plan_suppresses_button_during_paper_loading() -> None:
    plan = build_session_supervisor_adoption_plan(
        trading_mode_value="PAPER",
        loading_timer_active=True,
        was_active=True,
        market_open=True,
    )

    assert plan.set_start_button_active is False
    assert plan.log_messages == ()
    assert plan.follow_up_action == "refresh_paper_positions"


def test_build_session_supervisor_adoption_plan_starts_live_follow_up() -> None:
    plan = build_session_supervisor_adoption_plan(
        trading_mode_value="LIVE",
        loading_timer_active=False,
        was_active=False,
        market_open=True,
    )

    assert plan.set_start_button_active is True
    assert plan.log_messages == (
        "🚀 LIVE trading started — market data confirmed live",
        "TRADING ACTIVE [LIVE] - Unified session started",
    )
    assert plan.follow_up_action == "start_live_pnl_poll"
