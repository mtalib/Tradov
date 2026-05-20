#!/usr/bin/env python3
"""Pure selection logic for cached chart candle payloads."""

from __future__ import annotations

from typing import Any


def build_cached_chart_candles_result(
    loaded_caches: list[tuple[object, bool]],
) -> tuple[list[Any], bool]:
    """Return the first valid candle list, capped to the most recent 900 bars."""
    for candles, filter_to_today in loaded_caches:
        if not isinstance(candles, list):
            continue
        if len(candles) > 900:
            candles = candles[-900:]
        return list(candles), filter_to_today

    return [], True
