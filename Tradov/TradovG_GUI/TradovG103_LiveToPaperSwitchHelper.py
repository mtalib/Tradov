#!/usr/bin/env python3
"""Pure dialog plans for the LIVE-to-PAPER mode switch."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LiveToPaperDialogPlan:
    """Title, body, and decline log for one LIVE-to-PAPER dialog step."""

    dialog_title: str
    dialog_text: str
    declined_log_message: str


@dataclass(frozen=True)
class LiveToPaperSwitchPlan:
    """Pure warning/confirmation plans for the LIVE-to-PAPER branch."""

    open_positions_warning: LiveToPaperDialogPlan | None
    final_confirmation: LiveToPaperDialogPlan


def build_live_to_paper_switch_plan(
    *,
    open_positions_count: int,
) -> LiveToPaperSwitchPlan:
    """Return the dialog plans used when switching from LIVE to PAPER."""
    open_positions_warning = None
    if open_positions_count > 0:
        open_positions_warning = LiveToPaperDialogPlan(
            dialog_title="Open Positions Detected",
            dialog_text=(
                f"You still have {open_positions_count} open position(s) at Tradier.\n\n"
                "Switching to Paper Trading will NOT close these positions — "
                "they will remain open at the broker and must be managed manually.\n\n"
                "Switch anyway?"
            ),
            declined_log_message="Switch to PAPER cancelled — open positions remain",
        )

    return LiveToPaperSwitchPlan(
        open_positions_warning=open_positions_warning,
        final_confirmation=LiveToPaperDialogPlan(
            dialog_title="Switch to Paper Trading",
            dialog_text=(
                "Switch to PAPER Trading?\n"
                "Simulated fills only — no real orders will be placed."
            ),
            declined_log_message="Switch to PAPER cancelled by user",
        ),
    )
