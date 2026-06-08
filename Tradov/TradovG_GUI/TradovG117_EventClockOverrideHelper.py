#!/usr/bin/env python3
"""Pure manual event-clock override planning for the dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EventClockOverridePlan:
    """Pure UI/event payload plan for the manual override toggle."""

    button_label: str
    event_name: str
    event_payload: dict[str, Any]


def build_event_clock_override_plan(active: bool) -> EventClockOverridePlan:
    """Return the override label and event payload for the current toggle state."""
    if active:
        return EventClockOverridePlan(
            button_label="Manual Blackout: ON",
            event_name="event_clock_manual_override",
            event_payload={
                "state": "live",
                "event_id": "manual_override",
                "event_type": "manual_blackout",
                "allowed_strategies": [],
                "max_size_multiplier": 0.0,
            },
        )

    return EventClockOverridePlan(
        button_label="Manual Blackout: OFF",
        event_name="event_clock_manual_clear",
        event_payload={},
    )
