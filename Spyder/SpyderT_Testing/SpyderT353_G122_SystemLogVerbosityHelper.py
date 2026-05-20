#!/usr/bin/env python3
"""Focused tests for G122 system-log verbosity helper."""

from Spyder.SpyderG_GUI.SpyderG122_SystemLogVerbosityHelper import (
    build_system_log_verbosity_plan,
)


def test_build_system_log_verbosity_plan_for_debug_mode() -> None:
    plan = build_system_log_verbosity_plan(
        mode="debug",
        announce=True,
        debug_level=10,
        normal_level=40,
    )

    assert plan.selected_mode == "DEBUG"
    assert plan.logger_level == 10
    assert plan.normal_button_checked is False
    assert plan.debug_button_checked is True
    assert plan.announcement_message == "ℹ️ System log mode → DEBUG"


def test_build_system_log_verbosity_plan_defaults_to_normal() -> None:
    plan = build_system_log_verbosity_plan(
        mode="anything-else",
        announce=False,
        debug_level=10,
        normal_level=40,
    )

    assert plan.selected_mode == "NORMAL"
    assert plan.logger_level == 40
    assert plan.normal_button_checked is True
    assert plan.debug_button_checked is False
    assert plan.announcement_message is None