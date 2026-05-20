#!/usr/bin/env python3
"""Focused tests for G56 readiness start-gate presenter."""

from Spyder.SpyderG_GUI.SpyderG56_ReadinessStartGatePresenter import (
    build_conditional_readiness_reason_dialog_presentation,
    build_start_trading_readiness_gate_presentation,
)


def test_build_start_trading_readiness_gate_presentation_formats_logs() -> None:
    presentation = build_start_trading_readiness_gate_presentation(
        mode_label="PAPER",
        reason="manual review completed",
    )

    assert (
        presentation.safe_mode_log
        == "⚠️ Safe mode reminder: automation fallback is active from startup readiness validation"
    )
    assert (
        presentation.blocked_log
        == "⛔ Session blocked by readiness check (NO) — PAPER trading start rejected"
    )
    assert (
        presentation.cancelled_log
        == "Trading start cancelled after OK-CONDITIONAL readiness result"
    )
    assert (
        presentation.override_log
        == "⚠️ OK-CONDITIONAL override accepted — bypass reason: manual review completed"
    )


def test_build_conditional_readiness_reason_dialog_presentation_returns_required_copy(
) -> None:
    presentation = build_conditional_readiness_reason_dialog_presentation()

    assert presentation.window_title == "OK-CONDITIONAL — Bypass Reason Required"
    assert "OK - CONDITIONAL" in presentation.instruction_html
    assert presentation.placeholder_text == "Enter bypass reason (required)…"
    assert presentation.warning_title == "Reason Required"
    assert (
        presentation.warning_text
        == "You must enter a bypass reason before proceeding."
    )
