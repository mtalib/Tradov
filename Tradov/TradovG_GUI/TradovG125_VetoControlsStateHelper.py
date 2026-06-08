#!/usr/bin/env python3
"""Pure veto controls state resolution for the dashboard."""

from __future__ import annotations

from typing import Any


def resolve_veto_controls_enabled_state(
    *,
    profile_data: dict[str, Any] | None,
    default_enabled: bool,
    env_values: dict[str, str | None],
) -> bool:
    """Resolve the unified veto-enabled state from profile data or env fallback."""
    if isinstance(profile_data, dict):
        values = [
            bool(profile_data.get("enable_x16_veto", default_enabled)),
            bool(profile_data.get("enable_y03_trade_veto", default_enabled)),
            bool(profile_data.get("enable_y05_veto_consumption", default_enabled)),
        ]
        return all(values)

    def _env_bool(name: str) -> bool:
        raw = env_values.get(name)
        if raw is None:
            return default_enabled
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    return all(
        [
            _env_bool("ENABLE_X16_VETO"),
            _env_bool("ENABLE_Y03_TRADE_VETO"),
            _env_bool("ENABLE_Y05_VETO_CONSUMPTION"),
        ]
    )
