#!/usr/bin/env python3
"""Focused tests for G119 ring-log helper logic."""

from Spyder.SpyderG_GUI.SpyderG119_RingLogBufferHelper import (
    build_log_widget_refresh_plan,
    build_ring_log_append_plan,
)


def test_build_ring_log_append_plan_appends_and_trims_buffer() -> None:
    plan = build_ring_log_append_plan(
        buffer=["[09:30:00] one", "[09:31:00] two"],
        message="three",
        max_buffer=2,
        timestamp_text="09:32:00",
    )

    assert plan.next_buffer == ["[09:31:00] two", "[09:32:00] three"]


def test_build_log_widget_refresh_plan_schedules_system_widget() -> None:
    plan = build_log_widget_refresh_plan(
        has_widget=True,
        is_system_widget=True,
        is_automation_widget=False,
        system_pending=False,
        automation_pending=False,
    )

    assert plan.action == "schedule"
    assert plan.target == "system"
    assert plan.set_system_pending is True
    assert plan.set_automation_pending is False


def test_build_log_widget_refresh_plan_skips_when_automation_flush_pending() -> None:
    plan = build_log_widget_refresh_plan(
        has_widget=True,
        is_system_widget=False,
        is_automation_widget=True,
        system_pending=False,
        automation_pending=True,
    )

    assert plan.action == "skip"
    assert plan.target is None


def test_build_log_widget_refresh_plan_flushes_other_widget_immediately() -> None:
    plan = build_log_widget_refresh_plan(
        has_widget=True,
        is_system_widget=False,
        is_automation_widget=False,
        system_pending=False,
        automation_pending=False,
    )

    assert plan.action == "flush"
    assert plan.target == "other"