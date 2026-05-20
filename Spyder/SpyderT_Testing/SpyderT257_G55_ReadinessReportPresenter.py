#!/usr/bin/env python3
"""Focused tests for G55 readiness report export helpers."""

from Spyder.SpyderG_GUI.SpyderG55_ReadinessReportPresenter import (
    build_readiness_bypass_audit_entry,
    build_readiness_bypass_audit_filename,
    build_readiness_report_filename,
)


def test_build_readiness_report_filename_normalizes_spaces_in_decision() -> None:
    filename = build_readiness_report_filename(
        {"decision": "CONDITIONAL GO"},
        stamp="20260515_094500",
    )

    assert filename == "trading_readiness_20260515_094500_CONDITIONAL_GO.json"


def test_build_readiness_bypass_audit_entry_uses_expected_payload_shape() -> None:
    entry = build_readiness_bypass_audit_entry(
        action="override",
        decision="OK - CONDITIONAL",
        reason="operator confirmed",
        stamp="20260515_094500",
    )

    assert entry == {
        "audit_type": "session_start_gate",
        "action": "override",
        "decision": "OK - CONDITIONAL",
        "bypass_reason": "operator confirmed",
        "operator_ts_et": "20260515_094500",
    }


def test_build_readiness_bypass_audit_filename_uses_action_suffix() -> None:
    filename = build_readiness_bypass_audit_filename(
        action="blocked",
        stamp="20260515_094500",
    )

    assert filename == "trading_readiness_20260515_094500_audit_blocked.json"