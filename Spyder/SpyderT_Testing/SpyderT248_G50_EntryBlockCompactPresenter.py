#!/usr/bin/env python3
"""Focused tests for G50 entry-block presenter helpers."""

from Spyder.SpyderG_GUI.SpyderG50_EntryBlockCompactPresenter import (
    build_entry_block_alert_presentation,
    build_entry_block_compact_presentation,
)


def test_build_entry_block_compact_presentation_uses_message_verbatim() -> None:
    presentation = build_entry_block_compact_presentation("BLOCK: spread quality too low")

    assert presentation.text == "BLOCK: spread quality too low"
    assert presentation.tooltip == "BLOCK: spread quality too low"
    assert presentation.style == "color: #f5a623; font-size: 12px; font-weight: bold;"


def test_build_entry_block_compact_presentation_uses_fallback_for_blank_text() -> None:
    presentation = build_entry_block_compact_presentation("   ")

    assert presentation.text == "BLOCK: -"
    assert presentation.tooltip == "BLOCK: -"
    assert presentation.style == "color: #f5a623; font-size: 12px; font-weight: bold;"


def test_build_entry_block_alert_presentation_formats_digest_and_truncates_compact_text() -> None:
    detail = "spread quality too low " * 4

    presentation = build_entry_block_alert_presentation(
        "entry_trust_gate_rejected",
        message=detail,
    )

    assert presentation is not None
    assert presentation.digest == f"entry_trust_gate_rejected:{detail.strip()}"
    assert presentation.compact_display == f"BLOCK: {detail.strip()[:61]}..."
    assert presentation.system_log_message == (
        f"⛔ Entry blocked (entry_trust_gate_rejected): {detail.strip()}"
    )


def test_build_entry_block_alert_presentation_returns_none_for_unsupported_reason() -> None:
    assert build_entry_block_alert_presentation("other_reason", detail="ignored") is None


def test_build_entry_block_alert_presentation_formats_zero_dte_force_close_alert() -> None:
    presentation = build_entry_block_alert_presentation(
        "zero_dte_eod_force_close",
        message="0DTE paper options still open after 15:55 ET (2)",
        detail="SPY260528C00754000, SPY260528C00756000",
    )

    assert presentation is not None
    assert presentation.digest == (
        "zero_dte_eod_force_close:0DTE paper options still open after 15:55 ET (2):"
        "SPY260528C00754000, SPY260528C00756000"
    )
    assert presentation.compact_display == "BLOCK: 0DTE paper options still open after 15:55 ET (2)"
    assert presentation.system_log_message == (
        "⚠️ 0DTE paper options still open after 15:55 ET (2): "
        "SPY260528C00754000, SPY260528C00756000"
    )
