#!/usr/bin/env python3
"""Pure startup-readiness state assembly for dashboard startup UX."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from collections.abc import Iterable


_MARKET_CLOSED_WARNING = "Market is closed (outside regular trading hours)"


@dataclass(frozen=True)
class StartupReadinessStatePlan:
    """Pure readiness-state values derived from config and market-hours inputs."""

    mode: str
    automation_enabled: bool
    warnings: tuple[Any, ...]
    errors: tuple[Any, ...]
    safe_fallback_applied: bool
    live_blocking: bool


def build_startup_readiness_state_plan(
    *,
    env_mode: str | None,
    runtime_paper_mode: object,
    configured_mode: object,
    automation_enabled: bool,
    warnings: Iterable[Any] | None,
    errors: Iterable[Any] | None,
    market_hours_open: bool,
    preconnect_idle: bool,
) -> StartupReadinessStatePlan:
    """Build the startup-readiness state derived from normalized config inputs."""
    normalized_env_mode = str(env_mode or "").strip().lower()
    if normalized_env_mode in {"paper", "live", "production"}:
        mode = "live" if normalized_env_mode in {"live", "production"} else "paper"
    else:
        if isinstance(runtime_paper_mode, bool):
            mode = "paper" if runtime_paper_mode else "live"
        else:
            mode = str(configured_mode if configured_mode is not None else "paper").strip().lower()

    normalized_warnings = list(warnings or [])
    normalized_errors = list(errors or [])
    if not market_hours_open and not preconnect_idle:
        if _MARKET_CLOSED_WARNING not in normalized_warnings:
            normalized_warnings.append(_MARKET_CLOSED_WARNING)

    safe_fallback_applied = (mode != "live") and (not automation_enabled) and len(normalized_errors) > 0
    live_blocking = (mode == "live") and len(normalized_errors) > 0
    return StartupReadinessStatePlan(
        mode=mode,
        automation_enabled=bool(automation_enabled),
        warnings=tuple(normalized_warnings),
        errors=tuple(normalized_errors),
        safe_fallback_applied=safe_fallback_applied,
        live_blocking=live_blocking,
    )
