#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG53_GoNoGoPresenter.py
Purpose: Pure presentation helpers for the pre-open Go/No-Go display
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping


@dataclass(frozen=True)
class GoNoGoPresentation:
    """Dashboard-ready pre-open Go/No-Go decision presentation."""

    decision: str
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]
    checked_at_et: str
    status_text: str
    button_style: str
    start_enabled: bool
    log_message: str


def build_go_no_go_presentation(inner_result: Mapping[str, Any] | None) -> GoNoGoPresentation:
    """Build pre-open Go/No-Go result and UI presentation from readiness output."""
    result = inner_result if isinstance(inner_result, Mapping) else {}
    raw_decision = str(result.get("decision", "NO"))
    conditional = bool(result.get("conditional", False))
    reasons = tuple(str(reason) for reason in (result.get("reasons") or []))
    warnings = tuple(str(warning) for warning in (result.get("warnings") or []))
    checked_at_et = str(result.get("checked_at_et", ""))

    if raw_decision == "NO":
        decision = "NO-GO"
    elif conditional:
        decision = "CONDITIONAL GO"
    else:
        decision = "GO"

    colors = {
        "GO": "#00c800",
        "CONDITIONAL GO": "#ffa500",
        "NO-GO": "#c80000",
    }
    log_suffix = f" — {reasons[0]}" if reasons else ""

    return GoNoGoPresentation(
        decision=decision,
        reasons=reasons,
        warnings=warnings,
        checked_at_et=checked_at_et,
        status_text=f"Pre-open: {decision}",
        button_style=f"background-color: {colors.get(decision, '#888')};",
        start_enabled=(decision != "NO-GO"),
        log_message=f"Pre-open check: {decision}{log_suffix}",
    )
