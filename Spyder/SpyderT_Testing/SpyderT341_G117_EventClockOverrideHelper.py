#!/usr/bin/env python3
"""Focused tests for G117 manual event-clock override helper."""

from Spyder.SpyderG_GUI.SpyderG117_EventClockOverrideHelper import (
    build_event_clock_override_plan,
)


def test_build_event_clock_override_plan_for_active_state() -> None:
    plan = build_event_clock_override_plan(True)

    assert plan.button_label == "Manual Blackout: ON"
    assert plan.event_name == "event_clock_manual_override"
    assert plan.event_payload == {
        "state": "live",
        "event_id": "manual_override",
        "event_type": "manual_blackout",
        "allowed_strategies": [],
        "max_size_multiplier": 0.0,
    }


def test_build_event_clock_override_plan_for_clear_state() -> None:
    plan = build_event_clock_override_plan(False)

    assert plan.button_label == "Manual Blackout: OFF"
    assert plan.event_name == "event_clock_manual_clear"
    assert plan.event_payload == {}