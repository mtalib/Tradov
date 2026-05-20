#!/usr/bin/env python3
"""Pure veto toggle outcome planning for the dashboard."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VetoToggleResultPlan:
    """Pure outcome plan for a veto toggle attempt."""

    should_update_enabled_state: bool
    system_log_messages: tuple[str, ...]


def build_veto_toggle_result_plan(
    *,
    success: bool,
    next_state: bool,
    detail: str,
) -> VetoToggleResultPlan:
    """Return the dashboard update plan for a veto toggle persistence attempt."""
    if not success:
        return VetoToggleResultPlan(
            should_update_enabled_state=False,
            system_log_messages=(f"⚠️ Failed to update veto controls: {detail}",),
        )

    state_text = "ENABLED" if next_state else "DISABLED"
    return VetoToggleResultPlan(
        should_update_enabled_state=True,
        system_log_messages=(
            f"Veto controls {state_text} (saved: {detail})",
            "ℹ️ Restart autonomous agents/session to apply veto changes",
        ),
    )
