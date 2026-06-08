#!/usr/bin/env python3
"""Pure orchestration plan for post-paint startup-readiness refresh."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StartupReadinessRefreshPlan:
    """Pure ordered step plan for startup-readiness refresh."""

    should_skip: bool
    step_names: tuple[str, ...]


def build_startup_readiness_refresh_plan(
    *,
    shutdown_in_progress: bool,
) -> StartupReadinessRefreshPlan:
    """Build the post-paint startup-readiness refresh plan."""
    if shutdown_in_progress:
        return StartupReadinessRefreshPlan(
            should_skip=True,
            step_names=(),
        )

    return StartupReadinessRefreshPlan(
        should_skip=False,
        step_names=(
            "load_multiplier",
            "collect_state",
            "emit_logs",
        ),
    )
