#!/usr/bin/env python3
"""Pure startup-readiness state envelope shaping for dashboard startup UX."""

from __future__ import annotations

from typing import Any
from collections.abc import Iterable


def build_startup_readiness_base_state() -> dict[str, object]:
    """Return the default startup-readiness state before config access succeeds."""
    return {
        "checked": False,
        "pending": False,
        "mode": "paper",
        "automation_enabled": True,
        "warnings": [],
        "errors": [],
        "safe_fallback_applied": False,
        "live_blocking": False,
    }


def build_startup_readiness_success_state_payload(
    *,
    mode: str,
    automation_enabled: bool,
    warnings: Iterable[Any],
    errors: Iterable[Any],
    safe_fallback_applied: bool,
    live_blocking: bool,
) -> dict[str, object]:
    """Return the success-state payload derived from the normalized readiness plan."""
    return {
        "checked": True,
        "mode": mode,
        "automation_enabled": bool(automation_enabled),
        "warnings": list(warnings),
        "errors": list(errors),
        "safe_fallback_applied": bool(safe_fallback_applied),
        "live_blocking": bool(live_blocking),
    }
