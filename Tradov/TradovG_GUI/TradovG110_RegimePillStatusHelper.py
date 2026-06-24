#!/usr/bin/env python3
"""Pure stance/stress/gate planning for the regime pill bar."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class RegimePillStatusPlan:
    """Derived stance, stress, and gate labels for the regime pill bar."""

    stance: str
    stress: str
    gate: str


def build_regime_pill_status_plan(
    *,
    regime: str,
    swan: float,
    s07_live: bool,
    execution_truth: Mapping[str, object],
    fallback_stress: str | None,
) -> RegimePillStatusPlan:
    """Return the derived stance, stress, and gate labels."""
    if regime == "UNAVAILABLE":
        return RegimePillStatusPlan(
            stance="UNAVAILABLE",
            stress="UNKNOWN",
            gate="UNAVAILABLE",
        )

    stance = str(execution_truth.get("stance", "")).strip().upper()
    if not stance:
        if regime == "BULL":
            stance = "BULLISH"
        elif regime == "CRISIS":
            stance = "CRISIS"
        else:
            stance = "CHOPPY"

    if s07_live:
        if swan >= 3.0:
            stress = "CRISIS"
        elif swan >= 2.0:
            stress = "HIGH"
        elif swan >= 1.5:
            stress = "MEDIUM"
        else:
            stress = "LOW"
    else:
        stress = str(fallback_stress or "UNKNOWN").strip().upper() or "UNKNOWN"

    gate = str(execution_truth.get("gate", "")).strip().upper()
    if not gate:
        gate = {
            "BULL": "BULL TREND",
            "BEAR": "BEAR TREND",
            "RANGE": "RANGE CALM",
            "VOLATILE": "HIGH VOL",
            "CRISIS": "CRISIS",
            "EVENT": "EVENT",
        }.get(regime, "RANGE CALM")

    return RegimePillStatusPlan(stance=stance, stress=stress, gate=gate)
