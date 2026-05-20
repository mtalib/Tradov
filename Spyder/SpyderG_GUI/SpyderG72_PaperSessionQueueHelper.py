#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG72_PaperSessionQueueHelper.py
Purpose: Pure helper for paper-session queue decisions
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PaperSessionQueuePlan:
    """Plan describing how paper-session queueing should proceed."""

    action: str
    set_pending: bool = False
    pending_value: bool | None = None
    set_show_failure_dialog: bool = False
    show_failure_dialog: bool = False
    delay_ms: int | None = None


def build_paper_session_queue_plan(
    *,
    shutdown_in_progress: bool,
    is_paper_mode: bool,
    trading_active: bool,
    supervisor_running: bool,
    session_start_pending: bool,
    show_failure_dialog: bool,
    delay_ms: int,
) -> PaperSessionQueuePlan:
    """Decide whether to queue, start, or ignore a paper-session request."""
    if shutdown_in_progress:
        return PaperSessionQueuePlan(action="cancel_loading")

    if not is_paper_mode:
        return PaperSessionQueuePlan(action="noop")

    if trading_active or supervisor_running:
        return PaperSessionQueuePlan(action="adopt_running")

    if session_start_pending:
        return PaperSessionQueuePlan(action="noop")

    if int(delay_ms) <= 0:
        return PaperSessionQueuePlan(
            action="finalize_now",
            set_pending=True,
            pending_value=True,
            set_show_failure_dialog=True,
            show_failure_dialog=bool(show_failure_dialog),
        )

    return PaperSessionQueuePlan(
        action="begin_loading",
        set_pending=True,
        pending_value=True,
        set_show_failure_dialog=True,
        show_failure_dialog=bool(show_failure_dialog),
        delay_ms=int(delay_ms),
    )
