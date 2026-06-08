#!/usr/bin/env python3
"""Pure plan builder for early shutdown timer stop selection."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ShutdownTimerStopPlan:
    """Pure decision output for dashboard timer stop attempts."""

    timer_attrs: tuple[str, ...]


def build_shutdown_timer_stop_plan(
    *,
    timer_presence: dict[str, bool],
) -> ShutdownTimerStopPlan:
    """Select which known shutdown-timer attrs G05 should stop in order."""
    selected_attrs = tuple(
        timer_attr
        for timer_attr in (
            "_real_data_timer",
            "_fast_quote_timer",
            "_check_timer",
            "_decision_flow_timer",
        )
        if timer_presence.get(timer_attr, False)
    )
    return ShutdownTimerStopPlan(timer_attrs=selected_attrs)
