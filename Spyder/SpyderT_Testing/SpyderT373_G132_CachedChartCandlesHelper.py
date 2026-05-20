#!/usr/bin/env python3
"""Focused tests for G132 cached chart candle selection helper."""

from Spyder.SpyderG_GUI.SpyderG132_CachedChartCandlesHelper import (
    build_cached_chart_candles_result,
)


def test_build_cached_chart_candles_result_skips_non_lists_and_caps_to_recent_900() -> None:
    candle_bars = [{"time": f"2026-05-14T09:{index:02d}:00", "close": index} for index in range(1005)]

    candles, filter_to_today = build_cached_chart_candles_result(
        [
            ({"not": "a list"}, True),
            (candle_bars, False),
        ]
    )

    assert len(candles) == 900
    assert candles[0] == {"time": "2026-05-14T09:105:00", "close": 105}
    assert candles[-1] == {"time": "2026-05-14T09:1004:00", "close": 1004}
    assert filter_to_today is False


def test_build_cached_chart_candles_result_preserves_first_valid_list() -> None:
    candles, filter_to_today = build_cached_chart_candles_result(
        [
            ([{"time": "2026-05-13T15:55:00", "close": 742.31}], False),
            ([{"time": "2026-05-14T09:35:00", "close": 743.11}], True),
        ]
    )

    assert candles == [{"time": "2026-05-13T15:55:00", "close": 742.31}]
    assert filter_to_today is False


def test_build_cached_chart_candles_result_defaults_when_no_valid_list_exists() -> None:
    assert build_cached_chart_candles_result([({"bad": "payload"}, False), (None, True)]) == ([], True)