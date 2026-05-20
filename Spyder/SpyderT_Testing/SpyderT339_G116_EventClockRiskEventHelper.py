#!/usr/bin/env python3
"""Focused tests for G116 event-clock risk-event helper."""

from __future__ import annotations

from datetime import datetime, UTC

from Spyder.SpyderG_GUI.SpyderG116_EventClockRiskEventHelper import (
    build_event_clock_risk_event_plan,
)


def test_build_event_clock_risk_event_plan_accepts_direct_feed_payload() -> None:
    timestamp = datetime(2026, 5, 15, 13, 30, tzinfo=UTC)

    plan = build_event_clock_risk_event_plan(
        {
            "feed": "event_clock",
            "state": "live",
            "enabled": False,
            "sources": "calendar",
            "allowed_strategies": ["D03", "D04"],
            "blackout_pre_minutes": 10,
            "blackout_post_minutes": 12,
            "max_size_multiplier": 0.4,
        },
        timestamp=timestamp,
    )

    assert plan.should_update is True
    assert plan.state_kwargs == {
        "state": "live",
        "enabled": False,
        "sources": "calendar",
        "allowed_strategies": ["D03", "D04"],
        "blackout_pre_minutes": 10,
        "blackout_post_minutes": 12,
        "max_size_multiplier": 0.4,
        "timestamp": timestamp,
    }


def test_build_event_clock_risk_event_plan_unwraps_scheduler_payload() -> None:
    timestamp = datetime(2026, 5, 15, 13, 31, tzinfo=UTC)

    plan = build_event_clock_risk_event_plan(
        {
            "data": {
                "type": "event_clock_state",
                "payload": {
                    "feed": "event_clock",
                    "data": {
                        "state": "post",
                        "allowed_strategies": ["D11"],
                    },
                },
            }
        },
        timestamp=timestamp,
    )

    assert plan.should_update is True
    assert plan.state_kwargs is not None
    assert plan.state_kwargs["state"] == "post"
    assert plan.state_kwargs["allowed_strategies"] == ["D11"]
    assert plan.state_kwargs["sources"] == "calendar+manual"
    assert plan.state_kwargs["timestamp"] == timestamp


def test_build_event_clock_risk_event_plan_ignores_non_event_clock_payload() -> None:
    plan = build_event_clock_risk_event_plan(
        {"data": {"feed": "not_event_clock", "state": "live"}},
        timestamp=datetime(2026, 5, 15, 13, 32, tzinfo=UTC),
    )

    assert plan.should_update is False
    assert plan.state_kwargs is None
