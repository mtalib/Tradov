#!/usr/bin/env python3
"""Focused tests for G133 cached chart bar series helper."""

from datetime import date, datetime

from Spyder.SpyderG_GUI.SpyderG133_CachedChartBarSeriesHelper import (
    CachedChartBarSeries,
    build_cached_chart_bar_series,
)


def test_build_cached_chart_bar_series_filters_to_preferred_date_and_uses_fallback_parser() -> None:
    fallback_calls: list[str] = []

    series = build_cached_chart_bar_series(
        [
            {
                "time": "not-an-iso-timestamp",
                "open": "741.0",
                "high": "742.0",
                "low": "740.5",
                "close": "741.5",
                "volume": "1000",
            },
            {
                "time": "2026-05-13T15:55:00",
                "open": 730.0,
                "high": 731.0,
                "low": 729.5,
                "close": 730.5,
                "volume": 900,
            },
        ],
        date(2026, 5, 14),
        lambda raw: fallback_calls.append(raw) or datetime(2026, 5, 14, 9, 35),
    )

    assert fallback_calls == ["not-an-iso-timestamp"]
    assert series == CachedChartBarSeries(
        opens=[741.0],
        highs=[742.0],
        lows=[740.5],
        closes=[741.5],
        volumes=[1000],
        dates=[datetime(2026, 5, 14, 9, 35)],
    )


def test_build_cached_chart_bar_series_uses_latest_bar_date_when_none_is_provided() -> None:
    series = build_cached_chart_bar_series(
        [
            {
                "time": "2026-05-13T15:55:00",
                "open": 730.0,
                "high": 731.0,
                "low": 729.5,
                "close": 730.5,
                "volume": 900,
            },
            {
                "time": "2026-05-14T09:35:00",
                "open": 741.0,
                "high": 742.0,
                "low": 740.5,
                "close": 741.5,
                "volume": 1000,
            },
        ],
        None,
        lambda raw: datetime.fromisoformat(raw),
    )

    assert series == CachedChartBarSeries(
        opens=[741.0],
        highs=[742.0],
        lows=[740.5],
        closes=[741.5],
        volumes=[1000],
        dates=[datetime(2026, 5, 14, 9, 35)],
    )


def test_build_cached_chart_bar_series_returns_empty_lists_for_empty_payload() -> None:
    assert build_cached_chart_bar_series([], None, lambda raw: datetime.fromisoformat(raw)) == CachedChartBarSeries(
        opens=[],
        highs=[],
        lows=[],
        closes=[],
        volumes=[],
        dates=[],
    )
