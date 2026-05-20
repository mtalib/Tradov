#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG77_LoadingTransitionCompletionHelper.py
Purpose: Pure helper for start-button loading transition completion decisions
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LoadingTransitionCompletionPlan:
    """Plan describing what should happen when loading completion fires."""

    action: str
    finalize_pending_start: bool = False
    set_timer_inactive: bool = False
    activate_button: bool = False


def build_loading_transition_completion_plan(
    *,
    expected_generation: int,
    current_generation: int,
    shutdown_in_progress: bool,
    session_start_pending: bool,
    trading_active: bool,
    supervisor_running: bool,
) -> LoadingTransitionCompletionPlan:
    """Decide how the loading transition completion should proceed."""
    if expected_generation != current_generation:
        return LoadingTransitionCompletionPlan(action="noop")

    if shutdown_in_progress:
        return LoadingTransitionCompletionPlan(action="cancel_loading")

    activate_button = bool(trading_active or supervisor_running)
    return LoadingTransitionCompletionPlan(
        action="complete",
        finalize_pending_start=bool(session_start_pending),
        set_timer_inactive=True,
        activate_button=activate_button,
    )
