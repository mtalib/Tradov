#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovG_GUI
Module: TradovG37_GreekBarPresenter.py
Purpose: Pure helpers for dashboard Greek risk-bar updates
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping, Sequence


@dataclass(frozen=True)
class GreekBarUpdate:
    """Resolved value and risk status for a Greek progress bar."""

    key: str
    value: float
    status: str


_BAR_SCALE_CONFIG: tuple[tuple[str, float, float], ...] = (
    ("delta", -100.0, 100.0),
    ("gamma", -10.0, 10.0),
    ("theta", -400.0, 0.0),
    ("vega", -600.0, 0.0),
)


def _normalize_greek_value(value: Any) -> float:
    """Return a float Greek value, or zero when the input is invalid."""
    return float(value) if isinstance(value, (int, float)) else 0.0


def _risk_status_from_scale(value: float, low: float, high: float) -> str:
    """Map a Greek value to the UI risk-status bucket for its configured scale."""
    scale = max(abs(low), abs(high))
    percent = abs(value) / scale if scale else 0.0
    percent = min(max(percent, 0.0), 1.0)
    if percent >= 0.8:
        return "HIGH RISK"
    if percent >= 0.6:
        return "ELEVATED"
    return "NORMAL"


def build_greek_bar_updates(greeks: Mapping[str, Any] | None) -> Sequence[GreekBarUpdate]:
    """Build normalized Greek bar updates from the current portfolio Greeks."""
    greeks = greeks or {}
    updates: list[GreekBarUpdate] = []
    for key, low, high in _BAR_SCALE_CONFIG:
        value = _normalize_greek_value(greeks.get(key, 0.0))
        updates.append(
            GreekBarUpdate(
                key=key,
                value=value,
                status=_risk_status_from_scale(value, low, high),
            )
        )
    return updates
