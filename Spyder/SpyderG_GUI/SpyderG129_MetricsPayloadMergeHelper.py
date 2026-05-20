#!/usr/bin/env python3
"""Pure merge logic for Market Overview metrics payloads."""

from __future__ import annotations

from typing import Any

import numpy as np


def merge_metrics_payload(
    existing_metrics: dict | None,
    incoming_metrics: dict | None,
) -> dict[str, dict[str, Any]]:
    """Merge partial metrics updates without clearing valid cached values."""
    merged: dict[str, dict[str, Any]] = {}

    if isinstance(existing_metrics, dict):
        for symbol, entry in existing_metrics.items():
            if isinstance(entry, dict):
                merged[symbol] = dict(entry)

    if not isinstance(incoming_metrics, dict):
        return merged

    for symbol, entry in incoming_metrics.items():
        if not isinstance(entry, dict):
            continue

        current_entry = dict(merged.get(symbol, {}))
        for key, value in entry.items():
            is_missing = value is None
            if isinstance(value, (float, np.floating)) and np.isnan(value):
                is_missing = True
            elif isinstance(value, dict) and not value:
                is_missing = True
            elif isinstance(value, str) and value == "":
                is_missing = True

            if not is_missing:
                current_entry[key] = value

        if current_entry:
            merged[symbol] = current_entry

    return merged
