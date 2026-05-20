#!/usr/bin/env python3
"""Focused tests for G79 start-button ready-state helper."""

from Spyder.SpyderG_GUI.SpyderG79_StartButtonReadyStateHelper import (
    build_start_button_ready_state_plan,
)


def test_build_start_button_ready_state_plan_noops_without_button() -> None:
    plan = build_start_button_ready_state_plan(
        has_start_button=False,
        trading_active=False,
        is_paper_mode=True,
        positive_color="#22aa33",
    )

    assert plan.action == "noop"
    assert plan.style_sheet is None
    assert plan.text is None
    assert plan.enabled is None
    assert plan.tooltip is None


def test_build_start_button_ready_state_plan_noops_while_trading_active() -> None:
    plan = build_start_button_ready_state_plan(
        has_start_button=True,
        trading_active=True,
        is_paper_mode=True,
        positive_color="#22aa33",
    )

    assert plan.action == "noop"
    assert plan.style_sheet is None
    assert plan.text is None
    assert plan.enabled is None
    assert plan.tooltip is None


def test_build_start_button_ready_state_plan_restores_paper_copy() -> None:
    plan = build_start_button_ready_state_plan(
        has_start_button=True,
        trading_active=False,
        is_paper_mode=True,
        positive_color="#22aa33",
    )

    assert plan.action == "restore"
    assert plan.style_sheet == "background-color: #22aa33; color: black;"
    assert plan.text == "START TRADING"
    assert plan.enabled is True
    assert plan.tooltip == "Start paper trading with simulated fills"


def test_build_start_button_ready_state_plan_restores_live_copy() -> None:
    plan = build_start_button_ready_state_plan(
        has_start_button=True,
        trading_active=False,
        is_paper_mode=False,
        positive_color="#22aa33",
    )

    assert plan.action == "restore"
    assert plan.style_sheet == "background-color: #22aa33; color: black;"
    assert plan.text == "START TRADING"
    assert plan.enabled is True
    assert plan.tooltip == "Start LIVE trading with real order execution"