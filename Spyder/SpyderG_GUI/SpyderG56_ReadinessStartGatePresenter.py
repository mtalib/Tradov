#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG56_ReadinessStartGatePresenter.py
Purpose: Pure presentation helpers for readiness-gated trading start copy
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StartTradingReadinessGatePresentation:
    """Operator-facing log copy for readiness-gated trading start paths."""

    safe_mode_log: str
    blocked_log: str
    cancelled_log: str
    override_log: str


@dataclass(frozen=True)
class ConditionalReadinessReasonDialogPresentation:
    """Static copy for the conditional readiness bypass dialog."""

    window_title: str
    instruction_html: str
    placeholder_text: str
    warning_title: str
    warning_text: str


def build_start_trading_readiness_gate_presentation(
    *,
    mode_label: str,
    reason: str = "",
) -> StartTradingReadinessGatePresentation:
    """Build operator-facing log copy for readiness-gated start decisions."""
    normalized_mode_label = str(mode_label or "").strip() or "UNKNOWN"
    return StartTradingReadinessGatePresentation(
        safe_mode_log=(
            "⚠️ Safe mode reminder: automation fallback is active from startup readiness validation"
        ),
        blocked_log=(
            f"⛔ Session blocked by readiness check (NO) — {normalized_mode_label} trading start rejected"
        ),
        cancelled_log="Trading start cancelled after OK-CONDITIONAL readiness result",
        override_log=f"⚠️ OK-CONDITIONAL override accepted — bypass reason: {reason}",
    )


def build_conditional_readiness_reason_dialog_presentation(
) -> ConditionalReadinessReasonDialogPresentation:
    """Build the static dialog copy for conditional readiness bypass reasons."""
    return ConditionalReadinessReasonDialogPresentation(
        window_title="OK-CONDITIONAL — Bypass Reason Required",
        instruction_html=(
            "Trading readiness returned <b>OK - CONDITIONAL</b>.<br><br>"
            "Proceeding requires a documented reason.<br>"
            "This reason will be written to the session audit log."
        ),
        placeholder_text="Enter bypass reason (required)…",
        warning_title="Reason Required",
        warning_text="You must enter a bypass reason before proceeding.",
    )
