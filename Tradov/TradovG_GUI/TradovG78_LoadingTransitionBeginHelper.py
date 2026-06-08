#!/usr/bin/env python3
"""Pure plan builder for beginning the paper loading transition."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LoadingTransitionBeginPlan:
    """Pure decision output for beginning the delayed loading transition."""

    action: str
    next_generation: int | None = None
    delay_ms: int | None = None
    set_timer_active: bool = False
    schedule_with_qtimer: bool = False


def build_loading_transition_begin_plan(
    *,
    is_paper_mode: bool,
    current_generation: int,
    delay_ms: int,
    qtimer_available: bool,
) -> LoadingTransitionBeginPlan:
    """Decide whether to begin the paper loading transition and how to complete it."""
    if not is_paper_mode:
        return LoadingTransitionBeginPlan(action="noop")

    normalized_delay_ms = max(0, int(delay_ms))
    return LoadingTransitionBeginPlan(
        action="begin",
        next_generation=int(current_generation) + 1,
        delay_ms=normalized_delay_ms,
        set_timer_active=True,
        schedule_with_qtimer=bool(qtimer_available),
    )
