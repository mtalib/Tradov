#!/usr/bin/env python3
"""Pure plan builder for restoring the idle Start Trading button."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StartButtonReadyStatePlan:
    """Pure decision output for the idle start-button state."""

    action: str
    style_sheet: str | None = None
    text: str | None = None
    enabled: bool | None = None
    tooltip: str | None = None


def build_start_button_ready_state_plan(
    *,
    has_start_button: bool,
    trading_active: bool,
    is_paper_mode: bool,
    positive_color: str,
) -> StartButtonReadyStatePlan:
    """Decide whether to restore the idle Start Trading button and its copy."""
    if not has_start_button or trading_active:
        return StartButtonReadyStatePlan(action="noop")

    return StartButtonReadyStatePlan(
        action="restore",
        style_sheet=f"background-color: {positive_color}; color: black;",
        text="START TRADING",
        enabled=True,
        tooltip=(
            "Start paper trading with simulated fills"
            if is_paper_mode
            else "Start LIVE trading with real order execution"
        ),
    )
