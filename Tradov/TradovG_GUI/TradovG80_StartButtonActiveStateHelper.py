#!/usr/bin/env python3
"""Pure plan builder for the steady-state active Start Trading button."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StartButtonActiveStatePlan:
    """Pure decision output for the active start-button state."""

    action: str
    style_sheet: str | None = None
    text: str | None = None
    enabled: bool | None = None
    tooltip: str | None = None


def build_start_button_active_state_plan(
    *,
    has_start_button: bool,
    is_paper_mode: bool,
    market_open: bool,
    automation_active_color: str,
) -> StartButtonActiveStatePlan:
    """Decide whether to render the steady-state active button and its copy."""
    if not has_start_button:
        return StartButtonActiveStatePlan(action="noop")

    is_after_hours_paper = is_paper_mode and not market_open

    return StartButtonActiveStatePlan(
        action="render",
        style_sheet=f"background-color: {automation_active_color}; color: white;",
        text=(
            "PAPER STANDBY"
            if is_after_hours_paper
            else ("PAPER ACTIVE" if is_paper_mode else "TRADING ACTIVE")
        ),
        enabled=True,
        tooltip=(
            "Paper session is connected; scanning begins at 09:20 ET and trading auto-starts at 09:35 ET"
            if is_after_hours_paper
            else (
                "Paper trading session is active; scanning begins at 09:20 ET and trading auto-starts at 09:35 ET"
                if is_paper_mode
                else "Live trading session is active; scanning begins at 09:20 ET and trading auto-starts at 09:35 ET"
            )
        ),
    )
