#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovG_GUI
Module: TradovG76_SessionSupervisorAdoptionHelper.py
Purpose: Pure helper for SessionSupervisor adoption UI policy
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SessionSupervisorAdoptionPlan:
    """Plan describing follow-up UI policy for an adopted supervisor."""

    set_start_button_active: bool
    log_messages: tuple[str, ...]
    follow_up_action: str


def build_session_supervisor_adoption_plan(
    *,
    trading_mode_value: str,
    loading_timer_active: bool,
    was_active: bool,
    market_open: bool,
) -> SessionSupervisorAdoptionPlan:
    """Decide logs and follow-up actions after supervisor adoption."""
    is_paper_mode = trading_mode_value == "PAPER"
    is_live_mode = trading_mode_value == "LIVE"

    log_messages: list[str] = []
    if not was_active and market_open:
        log_messages.append(
            f"🚀 {trading_mode_value} trading started — market data confirmed live"
        )
        log_messages.append(
            f"TRADING ACTIVE [{trading_mode_value}] - Unified session started"
        )

    if is_paper_mode:
        follow_up_action = "refresh_paper_positions"
    elif is_live_mode:
        follow_up_action = "start_live_pnl_poll"
    else:
        follow_up_action = "none"

    return SessionSupervisorAdoptionPlan(
        set_start_button_active=not (is_paper_mode and bool(loading_timer_active)),
        log_messages=tuple(log_messages),
        follow_up_action=follow_up_action,
    )
