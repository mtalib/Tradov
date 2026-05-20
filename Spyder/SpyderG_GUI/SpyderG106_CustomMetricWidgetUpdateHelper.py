#!/usr/bin/env python3
"""Pure widget-update planning for one S07 custom metric entry."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class CustomMetricWidgetUpdatePlan:
    """Computed widget payload plus optional next previous-value state."""

    payload: dict[str, object]
    next_previous_value: float | None


def build_custom_metric_widget_update_plan(
    *,
    entry: object,
    scale: float,
    previous_value: float | None,
) -> CustomMetricWidgetUpdatePlan | None:
    """Return the widget payload for one S07 metric entry, if it is usable."""
    if not isinstance(entry, dict):
        return None

    raw = entry.get("value")
    if raw is None or (isinstance(raw, float) and math.isnan(raw)):
        return None

    value = raw * scale
    pre_change = entry.get("change")
    next_previous_value: float | None = None
    if pre_change is not None and not (isinstance(pre_change, float) and math.isnan(pre_change)):
        change = float(pre_change) * scale
        change_pct = (change / abs(value - change) * 100.0) if (value - change) else 0.0
    else:
        previous = value if previous_value is None else previous_value
        change = value - previous
        change_pct = (change / abs(previous) * 100.0) if previous else 0.0
        next_previous_value = value

    detail_block = entry.get("details", {})
    if not isinstance(detail_block, dict):
        detail_block = {}
    nested_details = detail_block.get("details", {})
    if not isinstance(nested_details, dict):
        nested_details = {}

    return CustomMetricWidgetUpdatePlan(
        payload={
            "last": value,
            "change": change,
            "change_pct": change_pct,
            "status": detail_block.get("status"),
            "phase": nested_details.get("phase"),
        },
        next_previous_value=next_previous_value,
    )
