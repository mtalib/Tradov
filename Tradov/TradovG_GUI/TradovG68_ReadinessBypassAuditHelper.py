#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovG_GUI
Module: TradovG68_ReadinessBypassAuditHelper.py
Purpose: Pure helper for readiness bypass-audit export routing
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping


@dataclass(frozen=True)
class ReadinessBypassAuditPlan:
    """Plan describing how a readiness bypass audit should be persisted."""

    export_result: dict[str, Any] | None
    standalone_payload: dict[str, Any] | None


def build_readiness_bypass_audit_plan(
    last_result: Mapping[str, Any] | object,
    audit_entry: Mapping[str, Any],
) -> ReadinessBypassAuditPlan:
    """Decide whether to append a bypass audit to cached readiness state."""
    payload = dict(audit_entry)

    if isinstance(last_result, Mapping):
        export_result = dict(last_result)
        existing_audit = export_result.get("bypass_audit")
        if isinstance(existing_audit, list):
            export_result["bypass_audit"] = [*existing_audit, payload]
        else:
            export_result["bypass_audit"] = [payload]
        return ReadinessBypassAuditPlan(
            export_result=export_result,
            standalone_payload=None,
        )

    return ReadinessBypassAuditPlan(
        export_result=None,
        standalone_payload=payload,
    )
