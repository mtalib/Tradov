#!/usr/bin/env python3
"""Pure startup-readiness log and button presentation for dashboard warmup."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


_MARKET_CLOSED_WARNING = "Market is closed (outside regular trading hours)"
_SAFE_MODE_TOOLTIP = (
    "Startup safe mode active: automation.enabled=false due to readiness errors. "
    "Fix config and restart to restore normal automation startup behavior."
)


@dataclass(frozen=True)
class StartupReadinessButtonPlan:
    """Pure start-button presentation for a startup-readiness outcome."""

    text: str
    style_sheet: str
    tool_tip: str


@dataclass(frozen=True)
class StartupReadinessLogPlan:
    """Pure operator-facing startup-readiness log output."""

    log_messages: tuple[str, ...]
    start_button_plan: StartupReadinessButtonPlan | None = None


def build_startup_readiness_log_plan(
    *,
    state: Mapping[str, object] | None,
    preconnect_idle: bool,
    warning_color: str,
) -> StartupReadinessLogPlan:
    """Build the visible startup-readiness log and optional button presentation."""
    normalized_state = state or {}
    normalized_warning_color = str(warning_color or "#e6a817")

    if normalized_state.get("pending", False):
        if preconnect_idle:
            return StartupReadinessLogPlan(log_messages=())
        return StartupReadinessLogPlan(
            log_messages=("ℹ️ Startup readiness warmup pending",),
        )

    if not normalized_state.get("checked", False):
        return StartupReadinessLogPlan(
            log_messages=(
                f"ℹ️ Startup readiness state unavailable ({normalized_state.get('source', 'unknown')})",
            ),
        )

    warnings = normalized_state.get("warnings", []) or []
    errors = normalized_state.get("errors", []) or []
    visible_warnings = tuple(
        str(warning)
        for warning in warnings
        if _MARKET_CLOSED_WARNING not in str(warning)
    )
    mode = str(normalized_state.get("mode", "paper")).upper()

    if normalized_state.get("safe_fallback_applied", False):
        return StartupReadinessLogPlan(
            log_messages=(
                f"⚠️ STARTUP SAFE MODE ({mode}): automation disabled by readiness validation",
                f"⚠️ Readiness issues: {len(errors)} blocking error(s), {len(visible_warnings)} warning(s)",
            ),
            start_button_plan=StartupReadinessButtonPlan(
                text="SAFE MODE (AUTO OFF)",
                style_sheet=f"background-color: {normalized_warning_color}; color: black;",
                tool_tip=_SAFE_MODE_TOOLTIP,
            ),
        )

    if normalized_state.get("live_blocking", False):
        return StartupReadinessLogPlan(
            log_messages=(
                "❌ LIVE readiness has blocking errors; startup should be corrected before trading",
            ),
        )

    if preconnect_idle and not visible_warnings:
        return StartupReadinessLogPlan(log_messages=())

    messages = [
        f"✅ Startup readiness validated (mode={mode}, warnings={len(visible_warnings)}, errors={len(errors)})"
    ]
    if visible_warnings:
        warning_text = "; ".join(visible_warnings[:3])
        messages.append(f"⚠️ Startup readiness warning(s): {warning_text}")
    return StartupReadinessLogPlan(log_messages=tuple(messages))
