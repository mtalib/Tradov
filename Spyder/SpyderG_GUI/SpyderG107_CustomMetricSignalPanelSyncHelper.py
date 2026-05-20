#!/usr/bin/env python3
"""Pure signal-panel sync planning for S07 custom metrics."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class CustomMetricSignalPanelSyncPlan:
    """Signal-panel regime values plus live custom-metric payload."""

    regime_value: object
    swan: float
    dix: float
    skew: float
    gex: float
    live_data: dict[str, float]


def _coerce_metric_value(metrics: Mapping[str, object], key: str, default: float) -> float:
    entry = metrics.get(key)
    if not isinstance(entry, dict):
        return default

    value = entry.get("value", default)
    if isinstance(value, float) and math.isnan(value):
        return default
    return float(value)


def build_custom_metric_signal_panel_sync_plan(
    *,
    metrics: Mapping[str, object],
    metric_routing: Mapping[str, tuple[str, float]],
    regime_value: object,
) -> CustomMetricSignalPanelSyncPlan:
    """Return the signal-panel regime payload and live S07 values."""
    live_data: dict[str, float] = {}
    for s07_key, (widget_key, scale) in metric_routing.items():
        if s07_key in ("TICK", "ADD", "TRIN"):
            continue

        entry = metrics.get(s07_key)
        if not isinstance(entry, dict):
            continue

        raw = entry.get("value")
        if raw is None or (isinstance(raw, float) and math.isnan(raw)):
            continue

        live_data[widget_key] = raw * scale

    return CustomMetricSignalPanelSyncPlan(
        regime_value=regime_value,
        swan=_coerce_metric_value(metrics, "SWAN", 1.9),
        dix=_coerce_metric_value(metrics, "DIX", 42.0),
        skew=_coerce_metric_value(metrics, "SKEW", 120.0),
        gex=_coerce_metric_value(metrics, "GEX", 0.0),
        live_data=live_data,
    )
