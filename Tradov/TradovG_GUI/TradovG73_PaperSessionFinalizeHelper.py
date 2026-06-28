#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovG_GUI
Module: TradovG73_PaperSessionFinalizeHelper.py
Purpose: Pure helper for delayed paper-session finalization outcomes
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PaperSessionFinalizeOutcomePlan:
    """Plan describing the delayed paper-session finalization outcome."""

    action: str
    show_dialog: bool = False


def build_paper_session_finalize_outcome_plan(
    *,
    market_open: bool,
    start_succeeded: bool,
    show_failure_dialog: bool,
) -> PaperSessionFinalizeOutcomePlan:
    """Decide the final delayed paper-session outcome after gating checks."""
    if not start_succeeded:
        return PaperSessionFinalizeOutcomePlan(
            action="start_failed",
            show_dialog=bool(show_failure_dialog),
        )

    return PaperSessionFinalizeOutcomePlan(action="adopt_running")
