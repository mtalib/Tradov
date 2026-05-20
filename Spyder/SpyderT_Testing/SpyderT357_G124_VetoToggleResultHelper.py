#!/usr/bin/env python3
"""Focused tests for G124 veto toggle result helper."""

from Spyder.SpyderG_GUI.SpyderG124_VetoToggleResultHelper import (
    build_veto_toggle_result_plan,
)


def test_build_veto_toggle_result_plan_for_failure() -> None:
    plan = build_veto_toggle_result_plan(
        success=False,
        next_state=False,
        detail="write failed",
    )

    assert plan.should_update_enabled_state is False
    assert plan.system_log_messages == (
        "⚠️ Failed to update veto controls: write failed",
    )


def test_build_veto_toggle_result_plan_for_success() -> None:
    plan = build_veto_toggle_result_plan(
        success=True,
        next_state=True,
        detail="/tmp/profile.json",
    )

    assert plan.should_update_enabled_state is True
    assert plan.system_log_messages == (
        "Veto controls ENABLED (saved: /tmp/profile.json)",
        "ℹ️ Restart autonomous agents/session to apply veto changes",
    )