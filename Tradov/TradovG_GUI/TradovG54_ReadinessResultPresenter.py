#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovG_GUI
Module: TradovG54_ReadinessResultPresenter.py
Purpose: Pure presentation helpers for trading-readiness result logging
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping


@dataclass(frozen=True)
class ReadinessResultLogPresentation:
    """Dashboard-ready system log lines for a readiness result."""

    detail_lines: tuple[str, ...]
    summary_line: str


def build_readiness_result_log_presentation(
    result: Mapping[str, Any] | None,
) -> ReadinessResultLogPresentation:
    """Build system log lines for the latest readiness result."""
    mapping = result if isinstance(result, Mapping) else {}
    reasons = tuple(str(reason) for reason in (mapping.get("reasons") or []))
    warnings = tuple(str(warning) for warning in (mapping.get("warnings") or []))
    decision = str(mapping.get("decision", "NO"))
    conditional = bool(mapping.get("conditional", False))

    if decision == "NO":
        normalized_reasons = reasons or ("Unknown reason",)
        return ReadinessResultLogPresentation(
            detail_lines=tuple(f"  ✗ {reason}" for reason in normalized_reasons),
            summary_line=f"NO - {'; '.join(normalized_reasons)}",
        )

    if conditional:
        warning_text = "; ".join(warnings) if warnings else "Warnings present"
        return ReadinessResultLogPresentation(
            detail_lines=(),
            summary_line=f"OK - CONDITIONAL: {warning_text}",
        )

    return ReadinessResultLogPresentation(
        detail_lines=(),
        summary_line="OK - READY",
    )
