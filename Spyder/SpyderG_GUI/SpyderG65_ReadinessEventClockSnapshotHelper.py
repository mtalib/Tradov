#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG65_ReadinessEventClockSnapshotHelper.py
Purpose: Pure helper for readiness event-clock snapshot normalization
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ReadinessEventClockSnapshot:
    """Normalized event-clock values used by readiness snapshots."""

    enabled: bool
    state: str


def build_readiness_event_clock_snapshot(
    event_state: Any | None,
) -> ReadinessEventClockSnapshot:
    """Normalize event-clock state into readiness snapshot scalars."""
    if event_state is None:
        return ReadinessEventClockSnapshot(enabled=True, state="clear")

    return ReadinessEventClockSnapshot(
        enabled=bool(getattr(event_state, "enabled", True)),
        state=str(getattr(event_state, "state", "clear")),
    )
