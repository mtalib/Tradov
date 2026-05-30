#!/usr/bin/env python3
"""Focused tests for G80 start-button active-state helper."""

from Spyder.SpyderG_GUI.SpyderG80_StartButtonActiveStateHelper import (
    build_start_button_active_state_plan,
)


def test_build_start_button_active_state_plan_noops_without_button() -> None:
    plan = build_start_button_active_state_plan(
        has_start_button=False,
        is_paper_mode=True,
        market_open=False,
        automation_active_color="#004466",
    )

    assert plan.action == "noop"
    assert plan.style_sheet is None
    assert plan.text is None
    assert plan.enabled is None
    assert plan.tooltip is None


def test_build_start_button_active_state_plan_renders_paper_copy() -> None:
    plan = build_start_button_active_state_plan(
        has_start_button=True,
        is_paper_mode=True,
        market_open=True,
        automation_active_color="#004466",
    )

    assert plan.action == "render"
    assert plan.style_sheet == "background-color: #004466; color: white;"
    assert plan.text == "PAPER ACTIVE"
    assert plan.enabled is True
    assert plan.tooltip == "Paper trading session is active"


def test_build_start_button_active_state_plan_renders_after_hours_paper_copy() -> None:
    plan = build_start_button_active_state_plan(
        has_start_button=True,
        is_paper_mode=True,
        market_open=False,
        automation_active_color="#004466",
    )

    assert plan.action == "render"
    assert plan.style_sheet == "background-color: #004466; color: white;"
    assert plan.text == "PAPER STANDBY"
    assert plan.enabled is True
    assert plan.tooltip == "Paper session is connected and waiting for market open"


def test_build_start_button_active_state_plan_renders_live_copy() -> None:
    plan = build_start_button_active_state_plan(
        has_start_button=True,
        is_paper_mode=False,
        market_open=False,
        automation_active_color="#004466",
    )

    assert plan.action == "render"
    assert plan.style_sheet == "background-color: #004466; color: white;"
    assert plan.text == "TRADING ACTIVE"
    assert plan.enabled is True
    assert plan.tooltip == "Live trading session is active"
