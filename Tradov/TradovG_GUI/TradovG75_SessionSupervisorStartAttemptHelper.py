#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovG_GUI
Module: TradovG75_SessionSupervisorStartAttemptHelper.py
Purpose: Pure helper for SessionSupervisor start-attempt outcomes
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SessionSupervisorStartAttemptPlan:
    """Plan describing the outcome of a SessionSupervisor start attempt."""

    return_value: bool
    clear_supervisor: bool = False
    log_message: str | None = None


def build_session_supervisor_start_attempt_plan(
    *,
    started: bool | None,
    error_text: str | None,
) -> SessionSupervisorStartAttemptPlan:
    """Decide how a SessionSupervisor start attempt should be applied."""
    if error_text:
        return SessionSupervisorStartAttemptPlan(
            return_value=False,
            clear_supervisor=True,
            log_message=f"❌ Unified session start failed: {error_text}",
        )

    if not bool(started):
        return SessionSupervisorStartAttemptPlan(
            return_value=False,
            clear_supervisor=True,
        )

    return SessionSupervisorStartAttemptPlan(return_value=True)
