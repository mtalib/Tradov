#!/usr/bin/env python3
"""Pure breadth-dialog sync planning for S07 custom metrics."""

from __future__ import annotations

import math
from collections.abc import Mapping


def build_custom_metric_breadth_dialog_payload(
    metrics: Mapping[str, object],
) -> dict[str, object] | None:
    """Return the Market Internals dialog payload when breadth values are usable."""
    tick_entry = metrics.get("TICK", {})
    add_entry = metrics.get("ADD", {})
    trin_entry = metrics.get("TRIN", {})
    nymo_entry = metrics.get("NYMO", {})

    if not (
        isinstance(tick_entry, dict)
        and isinstance(add_entry, dict)
        and isinstance(trin_entry, dict)
    ):
        return None

    if bool(tick_entry.get("stale")) or bool(add_entry.get("stale")) or bool(trin_entry.get("stale")):
        return {
            "tick": float("nan"),
            "add": float("nan"),
            "trin": float("nan"),
            "nymo": float("nan"),
            "breadth_regime": "",
            "stale": True,
        }

    tick = tick_entry.get("value", float("nan"))
    add = add_entry.get("value", float("nan"))
    trin = trin_entry.get("value", float("nan"))
    nymo = (
        nymo_entry.get("value", float("nan"))
        if isinstance(nymo_entry, dict) and not bool(nymo_entry.get("stale"))
        else float("nan")
    )

    if (
        isinstance(tick, float) and math.isnan(tick)
        and isinstance(add, float) and math.isnan(add)
        and isinstance(trin, float) and math.isnan(trin)
    ):
        return None

    breadth_entry = metrics.get("BREADTH_REGIME", {})
    regime = (
        breadth_entry.get("value", "")
        if isinstance(breadth_entry, dict) and not bool(breadth_entry.get("stale"))
        else ""
    )
    return {
        "tick": tick,
        "add": add,
        "trin": trin,
        "nymo": nymo,
        "breadth_regime": regime,
    }
