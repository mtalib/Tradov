#!/usr/bin/env python3
"""Pure event-clock risk-event normalization for the dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class EventClockRiskEventPlan:
    """Normalized event-clock update plan for the risk-event handler."""

    should_update: bool
    state_kwargs: dict[str, Any] | None = None


def build_event_clock_risk_event_plan(
    event: object,
    *,
    timestamp: datetime,
) -> EventClockRiskEventPlan:
    """Normalize risk-event payload shapes into EventClockState kwargs."""
    event_payload = event
    if hasattr(event, "data") and isinstance(getattr(event, "data", None), dict):
        event_payload = event.data

    if not isinstance(event_payload, dict):
        return EventClockRiskEventPlan(should_update=False)

    event_data = event_payload.get("data", {}) if "data" in event_payload else event_payload
    if not isinstance(event_data, dict):
        return EventClockRiskEventPlan(should_update=False)

    if event_data.get("feed") != "event_clock" and isinstance(event_data.get("payload"), dict):
        wrapped_payload = event_data.get("payload")
        wrapped_data = wrapped_payload.get("data")
        if isinstance(wrapped_data, dict):
            event_data = dict(wrapped_data)
            if wrapped_payload.get("feed") and not event_data.get("feed"):
                event_data["feed"] = wrapped_payload.get("feed")

    if event_data.get("feed") != "event_clock":
        return EventClockRiskEventPlan(should_update=False)

    return EventClockRiskEventPlan(
        should_update=True,
        state_kwargs={
            "state": event_data.get("state", "clear"),
            "enabled": event_data.get("enabled", True),
            "sources": event_data.get("sources", "calendar+manual"),
            "allowed_strategies": list(event_data.get("allowed_strategies", []) or []),
            "blackout_pre_minutes": event_data.get("blackout_pre_minutes", 30),
            "blackout_post_minutes": event_data.get("blackout_post_minutes", 30),
            "max_size_multiplier": event_data.get("max_size_multiplier", 0.25),
            "timestamp": timestamp,
        },
    )
