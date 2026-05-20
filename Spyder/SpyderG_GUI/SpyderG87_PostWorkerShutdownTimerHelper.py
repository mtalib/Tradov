#!/usr/bin/env python3
"""Pure plan builder for late shutdown timer stop selection."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PostWorkerShutdownTimerPlan:
    """Pure decision output for late dashboard timer stop attempts."""

    timer_attrs: tuple[str, ...]


def build_post_worker_shutdown_timer_plan(
    *,
    timer_presence: dict[str, bool],
) -> PostWorkerShutdownTimerPlan:
    """Select which late shutdown timer attrs G05 should stop in order."""
    selected_attrs = tuple(
        timer_attr
        for timer_attr in ("datetime_timer", "chart_timer")
        if timer_presence.get(timer_attr, False)
    )
    return PostWorkerShutdownTimerPlan(timer_attrs=selected_attrs)
