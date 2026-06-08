#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovG_GUI
Module: TradovG55_ReadinessReportPresenter.py
Purpose: Pure helpers for readiness report and audit export naming/payloads
"""

from __future__ import annotations

from typing import Any
from collections.abc import Mapping


def build_readiness_report_filename(
    result: Mapping[str, Any] | None,
    *,
    stamp: str,
) -> str:
    """Build the readiness report filename for a given decision result."""
    mapping = result if isinstance(result, Mapping) else {}
    decision = str(mapping.get("decision", "UNKNOWN")).replace(" ", "_")
    return f"trading_readiness_{stamp}_{decision}.json"


def build_readiness_bypass_audit_entry(
    *,
    action: str,
    decision: str,
    reason: str,
    stamp: str,
) -> dict[str, str]:
    """Build a standalone readiness bypass audit payload."""
    return {
        "audit_type": "session_start_gate",
        "action": action,
        "decision": decision,
        "bypass_reason": reason,
        "operator_ts_et": stamp,
    }


def build_readiness_bypass_audit_filename(*, action: str, stamp: str) -> str:
    """Build the standalone readiness bypass audit filename."""
    return f"trading_readiness_{stamp}_audit_{action}.json"
