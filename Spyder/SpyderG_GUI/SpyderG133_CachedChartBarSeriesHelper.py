#!/usr/bin/env python3
"""Pure cached chart bar parsing and filtering helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from collections.abc import Callable


@dataclass(frozen=True)
class CachedChartBarSeries:
    """Raw chart series parsed from cached candle payloads."""

    opens: list[float]
    highs: list[float]
    lows: list[float]
    closes: list[float]
    volumes: list[int]
    dates: list[datetime]


def build_cached_chart_bar_series(
    candles: list[dict],
    preferred_target_date: date | None,
    fallback_timestamp_parser: Callable[[str], datetime],
) -> CachedChartBarSeries:
    """Parse cached bars and filter them to the preferred or latest session date."""
    parsed_bars: list[tuple[dict, datetime]] = []
    for bar in candles:
        raw_time = str(bar.get("time", ""))
        try:
            bar_dt = datetime.fromisoformat(raw_time)
        except ValueError:
            bar_dt = fallback_timestamp_parser(raw_time)
        parsed_bars.append((bar, bar_dt))

    target_date = preferred_target_date
    if target_date is None and parsed_bars:
        target_date = parsed_bars[-1][1].date()

    opens_raw: list[float] = []
    highs_raw: list[float] = []
    lows_raw: list[float] = []
    closes_raw: list[float] = []
    volumes_raw: list[int] = []
    dates_raw: list[datetime] = []

    for bar, bar_dt in parsed_bars:
        if target_date is not None and bar_dt.date() != target_date:
            continue
        opens_raw.append(float(bar.get("open", 0)))
        highs_raw.append(float(bar.get("high", 0)))
        lows_raw.append(float(bar.get("low", 0)))
        closes_raw.append(float(bar.get("close", 0)))
        volumes_raw.append(int(bar.get("volume", 0)))
        dates_raw.append(bar_dt)

    return CachedChartBarSeries(
        opens=opens_raw,
        highs=highs_raw,
        lows=lows_raw,
        closes=closes_raw,
        volumes=volumes_raw,
        dates=dates_raw,
    )
