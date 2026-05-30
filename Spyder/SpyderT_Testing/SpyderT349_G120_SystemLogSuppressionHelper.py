#!/usr/bin/env python3
"""Focused tests for G120 system-log suppression helper."""

from Spyder.SpyderG_GUI.SpyderG120_SystemLogSuppressionHelper import (
    should_suppress_after_hours_system_log_text,
    should_suppress_opening_warmup_system_log_text,
)


def test_should_suppress_opening_warmup_system_log_text_for_quiet_prefix() -> None:
    assert should_suppress_opening_warmup_system_log_text(
        "📦 Restored 30 symbols from EOD snapshot saved at 2026-05-13 09:29:58"
    ) is True


def test_should_suppress_opening_warmup_system_log_text_keeps_allowed_prefix() -> None:
    assert should_suppress_opening_warmup_system_log_text(
        "🟡 Establishing live connections and loading live data"
    ) is False
    assert should_suppress_opening_warmup_system_log_text(
        "⏳ ENTRY gate remains blocked until 10:30 ET"
    ) is False


def test_should_suppress_after_hours_system_log_text_for_quiet_prefix() -> None:
    assert should_suppress_after_hours_system_log_text(
        "AUTONOMOUS METRICS ACTIVE - DIX/SWAN stress monitor online"
    ) is True


def test_should_suppress_system_log_text_ignores_blank_and_unmatched_messages() -> None:
    assert should_suppress_after_hours_system_log_text("   ") is False
    assert should_suppress_opening_warmup_system_log_text("Operator attention required") is False


def test_should_never_suppress_eod_snapshot_detail_line() -> None:
    message = "📈 EOD snapshot details — DIA: $495.37 | VXV: 16.83"
    assert should_suppress_opening_warmup_system_log_text(message) is False
    assert should_suppress_after_hours_system_log_text(message) is False
