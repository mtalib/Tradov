#!/usr/bin/env python3
"""Pure dialog and confirmation plans for the PAPER-to-LIVE switch."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PaperToLiveDialogPlan:
    """Critical dialog title and body for a PAPER-to-LIVE gate."""

    dialog_title: str
    dialog_text: str


@dataclass(frozen=True)
class PaperToLiveConfirmationPlan:
    """Typed confirmation parameters plus decline log for PAPER-to-LIVE."""

    required_phrase: str
    dialog_title: str
    header_text: str
    confirm_button_text: str
    declined_log_message: str


@dataclass(frozen=True)
class PaperToLiveSwitchPlan:
    """Pure PAPER-to-LIVE dialog and confirmation plans."""

    api_disconnected: PaperToLiveDialogPlan
    market_data_disconnected: PaperToLiveDialogPlan
    confirmation: PaperToLiveConfirmationPlan


def build_paper_to_live_switch_plan() -> PaperToLiveSwitchPlan:
    """Return the dialog and typed-confirmation plans for PAPER-to-LIVE."""
    return PaperToLiveSwitchPlan(
        api_disconnected=PaperToLiveDialogPlan(
            dialog_title="Tradier EXEC Not Connected",
            dialog_text=(
                "You must connect to Tradier EXEC before switching to LIVE trading.\n\n"
                "Click the TRADIER EXEC indicator in the toolbar to connect."
            ),
        ),
        market_data_disconnected=PaperToLiveDialogPlan(
            dialog_title="No Data Feed Connected",
            dialog_text=(
                "You must connect a market data feed (TRADIER DATA)\n"
                "before switching to LIVE trading.\n\n"
                "Click the data feed indicator in the toolbar to connect."
            ),
        ),
        confirmation=PaperToLiveConfirmationPlan(
            required_phrase="I WANT TO SWITCH TO REAL LIVE TRADING",
            dialog_title="⚠️  ENABLE REAL — CONFIRMATION REQUIRED",
            header_text="⚠️  YOU ARE ARMING REAL LIVE TRADING",
            confirm_button_text="ENABLE REAL LIVE TRADING",
            declined_log_message="Switch to LIVE cancelled by user",
        ),
    )
