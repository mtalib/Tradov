#!/usr/bin/env python3
"""Pure normalization helper for the dashboard DJI proxy multiplier."""

from __future__ import annotations


def normalize_dji_proxy_multiplier(
    configured_value: object,
    default_multiplier: float,
) -> float:
    """Normalize the configured DJI proxy multiplier, falling back to default."""
    try:
        multiplier = float(configured_value)
    except (TypeError, ValueError):
        return default_multiplier

    if multiplier <= 0:
        return default_multiplier
    return multiplier
