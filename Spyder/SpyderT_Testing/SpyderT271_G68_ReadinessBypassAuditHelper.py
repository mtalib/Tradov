#!/usr/bin/env python3
"""Focused tests for G68 readiness bypass-audit helper."""

from Spyder.SpyderG_GUI.SpyderG68_ReadinessBypassAuditHelper import (
    build_readiness_bypass_audit_plan,
)


def test_build_readiness_bypass_audit_plan_appends_to_cached_result_copy() -> None:
    last_result = {
        "decision": "OK",
        "bypass_audit": [{"audit_type": "existing"}],
    }
    audit_entry = {"audit_type": "new"}

    plan = build_readiness_bypass_audit_plan(last_result, audit_entry)

    assert plan.export_result == {
        "decision": "OK",
        "bypass_audit": [
            {"audit_type": "existing"},
            {"audit_type": "new"},
        ],
    }
    assert plan.standalone_payload is None
    assert last_result == {
        "decision": "OK",
        "bypass_audit": [{"audit_type": "existing"}],
    }


def test_build_readiness_bypass_audit_plan_returns_standalone_payload_without_cache() -> None:
    audit_entry = {"audit_type": "new"}

    plan = build_readiness_bypass_audit_plan(None, audit_entry)

    assert plan.export_result is None
    assert plan.standalone_payload == {"audit_type": "new"}