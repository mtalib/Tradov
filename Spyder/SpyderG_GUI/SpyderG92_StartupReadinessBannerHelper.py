#!/usr/bin/env python3
"""Pure startup-readiness banner copy for the dashboard startup ring buffer."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping


_MARKET_CLOSED_WARNING = "Market is closed (outside regular trading hours)"


@dataclass(frozen=True)
class StartupReadinessBannerPlan:
    """Pure startup banner lines for startup-readiness state."""

    system_log_messages: tuple[str, ...]


def build_startup_readiness_banner_plan(
    *,
    state: Mapping[str, object] | None,
    startup_hms: str,
    preconnect_idle: bool,
) -> StartupReadinessBannerPlan:
    """Build the startup ring-buffer banner lines for readiness state."""
    normalized_state = state or {}

    if normalized_state.get("pending", False):
        return StartupReadinessBannerPlan(system_log_messages=())

    if not normalized_state.get("checked", False):
        return StartupReadinessBannerPlan(
            system_log_messages=(
                f"[{startup_hms}] ℹ️ STARTUP READINESS: unavailable ({normalized_state.get('source', 'unknown')})",
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
        return StartupReadinessBannerPlan(
            system_log_messages=(
                f"[{startup_hms}] ⚠️ STARTUP READINESS: SAFE MODE ACTIVE ({mode})",
                f"[{startup_hms}] ⚠️ automation.enabled=false due to {len(errors)} blocking config error(s)",
            ),
        )

    if normalized_state.get("live_blocking", False):
        return StartupReadinessBannerPlan(
            system_log_messages=(
                f"[{startup_hms}] ❌ STARTUP READINESS: LIVE BLOCKING ({len(errors)} error(s))",
            ),
        )

    if preconnect_idle and not visible_warnings:
        return StartupReadinessBannerPlan(system_log_messages=())

    messages = [
        f"[{startup_hms}] ✅ STARTUP READINESS: mode={mode} warnings={len(visible_warnings)} errors={len(errors)}"
    ]
    if visible_warnings:
        warning_text = "; ".join(visible_warnings[:3])
        messages.append(
            f"[{startup_hms}] ⚠️ STARTUP READINESS WARNING(S): {warning_text}"
        )
    return StartupReadinessBannerPlan(system_log_messages=tuple(messages))
