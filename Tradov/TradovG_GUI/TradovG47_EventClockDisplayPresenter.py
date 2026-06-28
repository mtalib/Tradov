#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovG_GUI
Module: TradovG47_EventClockDisplayPresenter.py
Purpose: Pure presentation helpers for event-clock dashboard display
"""

from __future__ import annotations

from dataclasses import dataclass

from Tradov.TradovG_GUI.TradovG06_DashboardData import EventClockState


@dataclass(frozen=True)
class EventClockDisplayPresentation:
    """Dashboard-ready event-clock display values."""

    state_text: str
    state_style: str
    compact_text: str
    compact_style: str
    policy_text: str
    windows_text: str
    policy_and_windows_text: str
    strategies_text: str


def build_event_clock_display_presentation(
    state: EventClockState,
) -> EventClockDisplayPresentation:
    """Build event-clock label text and styles from the current state."""
    allowlist_text = ", ".join(state.allowed_strategies) if state.allowed_strategies else "None"
    policy_text = f"{'Enabled' if state.enabled else 'Disabled'} | Sources: {state.sources}"
    windows_text = (
        f"Window -{state.blackout_pre_minutes}m/+{state.blackout_post_minutes}m"
        f" | Size {state.max_size_multiplier:.0%}"
        f" | Allowlist {allowlist_text}"
    )
    compact_body = state.state_label.replace("✓ ", "").replace("✗ ", "")

    return EventClockDisplayPresentation(
        state_text=state.state_label,
        state_style=f"color: {state.state_color};",
        compact_text=f"EC: {compact_body}",
        compact_style=(
            f"color: {state.state_color}; font-size: 11px; font-weight: normal;"
        ),
        policy_text=policy_text,
        windows_text=windows_text,
        policy_and_windows_text=f"{policy_text} | {windows_text}",
        strategies_text=f"Allowlist {allowlist_text}",
    )
