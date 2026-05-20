#!/usr/bin/env python3
"""Pure dedupe and dispatch plan for dashboard risk alert events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RiskAlertDispatchPlan:
    """Pure dispatch output for an entry/risk alert presentation."""

    should_skip: bool
    next_digest: str = ""
    next_timestamp: float = 0.0
    system_log_message: str = ""
    compact_display: str = ""


def build_risk_alert_dispatch_plan(
    *,
    presentation: Any,
    last_digest: str,
    last_timestamp: float,
    now_monotonic: float,
    dedupe_window_seconds: float = 15.0,
) -> RiskAlertDispatchPlan:
    """Build the risk-alert dedupe and dispatch plan after presentation shaping."""
    if presentation is None:
        return RiskAlertDispatchPlan(should_skip=True)

    digest = str(getattr(presentation, "digest", "") or "")
    if digest == str(last_digest or "") and (now_monotonic - float(last_timestamp)) < dedupe_window_seconds:
        return RiskAlertDispatchPlan(should_skip=True)

    return RiskAlertDispatchPlan(
        should_skip=False,
        next_digest=digest,
        next_timestamp=now_monotonic,
        system_log_message=str(getattr(presentation, "system_log_message", "") or ""),
        compact_display=str(getattr(presentation, "compact_display", "") or ""),
    )
