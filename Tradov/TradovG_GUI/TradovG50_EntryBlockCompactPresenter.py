#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovG_GUI
Module: TradovG50_EntryBlockCompactPresenter.py
Purpose: Pure presentation helpers for the compact entry-block label
"""

from __future__ import annotations

from dataclasses import dataclass


SUPPORTED_ENTRY_BLOCK_REASONS = {
    "entry_trust_gate_rejected",
    "validate_signal_rejected",
    "zero_dte_eod_force_close",
}


@dataclass(frozen=True)
class EntryBlockCompactPresentation:
    """Dashboard-ready compact entry-block label values."""

    text: str
    tooltip: str
    style: str


@dataclass(frozen=True)
class EntryBlockAlertPresentation:
    """Dashboard-ready entry-block alert values derived from risk events."""

    digest: str
    compact_display: str
    system_log_message: str


def build_entry_block_compact_presentation(text: str | None) -> EntryBlockCompactPresentation:
    """Build compact entry-block label text, tooltip, and style."""
    message = str(text or "").strip() or "BLOCK: -"
    return EntryBlockCompactPresentation(
        text=message,
        tooltip=message,
        style="color: #f5a623; font-size: 12px; font-weight: bold;",
    )


def build_entry_block_alert_presentation(
    reason: str | None,
    *,
    message: str | None = None,
    detail: str | None = None,
) -> EntryBlockAlertPresentation | None:
    """Build entry-block alert strings from a risk alert payload."""
    normalized_reason = str(reason or "").strip().lower()
    if normalized_reason not in SUPPORTED_ENTRY_BLOCK_REASONS:
        return None

    if normalized_reason == "zero_dte_eod_force_close":
        summary_text = (
            str(message or "").strip()
            or "0DTE paper option still open after 15:55 ET"
        )
        detail_text = str(detail or "").strip()
        compact_text = summary_text if len(summary_text) <= 64 else f"{summary_text[:61]}..."
        system_log_message = f"⚠️ {summary_text}"
        if detail_text:
            system_log_message = f"{system_log_message}: {detail_text}"

        return EntryBlockAlertPresentation(
            digest=f"{normalized_reason}:{summary_text}:{detail_text}",
            compact_display=f"BLOCK: {compact_text}",
            system_log_message=system_log_message,
        )

    detail_text = str(message or detail or normalized_reason).strip() or normalized_reason
    compact_text = detail_text if len(detail_text) <= 64 else f"{detail_text[:61]}..."

    return EntryBlockAlertPresentation(
        digest=f"{normalized_reason}:{detail_text}",
        compact_display=f"BLOCK: {compact_text}",
        system_log_message=f"⛔ Entry blocked ({normalized_reason}): {detail_text}",
    )
