#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG60_ReadinessStartBlockPresenter.py
Purpose: Pure presentation helper for readiness hard-block start copy
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class ReadinessStartBlockPresentation:
    """Operator-facing dialog and log copy for readiness hard-blocks."""

    dialog_title: str
    dialog_text: str
    log_message: str


def build_readiness_start_block_presentation(
    *,
    mode_label: str,
    reasons: Iterable[Any] | None,
) -> ReadinessStartBlockPresentation:
    """Build dialog and log copy for a readiness NO result at trading start."""
    normalized_mode_label = str(mode_label or "").strip().upper() or "UNKNOWN"
    reason_lines = [f"- {str(reason)}" for reason in list(reasons or [])[:6] if str(reason)]
    reason_text = "\n".join(reason_lines) or "- Unknown readiness failure"
    return ReadinessStartBlockPresentation(
        dialog_title=f"{normalized_mode_label} Start Blocked (NO)",
        dialog_text=(
            "Trading readiness evaluation returned NO.\n\n"
            f"Reasons:\n{reason_text}"
        ),
        log_message=f"❌ {normalized_mode_label} start blocked by readiness evaluation",
    )
