#!/usr/bin/env python3
"""Pure merge logic for startup market snapshot restoration."""

from __future__ import annotations

from typing import Any


def build_cached_market_display_snapshot_result(
    loaded_snapshots: list[tuple[str, object]],
) -> tuple[dict[str, dict[str, Any]] | None, str | None]:
    """Merge ordered snapshot payloads while preserving first-source precedence."""
    merged_payload: dict[str, dict[str, Any]] = {}
    loaded_labels: list[str] = []

    for label, payload in loaded_snapshots:
        if not isinstance(payload, dict):
            continue

        for symbol, entry in payload.items():
            if not isinstance(entry, dict):
                continue
            if symbol not in merged_payload:
                merged_payload[symbol] = dict(entry)

        loaded_labels.append(label)

    if merged_payload:
        if len(loaded_labels) == 1:
            return merged_payload, loaded_labels[0]
        return merged_payload, " + ".join(loaded_labels)

    return None, None
