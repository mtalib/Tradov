#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovG_GUI
Module: TradovG74_SessionSupervisorStartHelper.py
Purpose: Pure helper for SessionSupervisor start branching
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SessionSupervisorStartPlan:
    """Plan describing how SessionSupervisor startup should proceed."""

    action: str


def build_session_supervisor_start_plan(
    *,
    has_supervisor: bool,
    autostart_in_progress: bool,
    supervisor_running: bool,
) -> SessionSupervisorStartPlan:
    """Decide whether startup should block, reuse, or create a supervisor."""
    if has_supervisor:
        if autostart_in_progress:
            return SessionSupervisorStartPlan(action="block_autostart")
        if supervisor_running:
            return SessionSupervisorStartPlan(action="already_running")
        return SessionSupervisorStartPlan(action="reuse_existing")

    return SessionSupervisorStartPlan(action="create_new")
