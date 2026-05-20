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
    automation_active_color: str,
) -> StartButtonActiveStatePlan:
    """Decide whether to render the steady-state active button and its copy."""
    if not has_start_button:
        return StartButtonActiveStatePlan(action="noop")

    return StartButtonActiveStatePlan(
        action="render",
        style_sheet=f"background-color: {automation_active_color}; color: white;",
        text="PAPER ACTIVE" if is_paper_mode else "TRADING ACTIVE",
        enabled=True,
        tooltip=(
            "Paper trading session is active"
            if is_paper_mode
            else "Live trading session is active"
        ),
    )
