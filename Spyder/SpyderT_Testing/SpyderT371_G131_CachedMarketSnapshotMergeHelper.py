#!/usr/bin/env python3
"""Focused tests for G131 cached market snapshot merge helper."""

from Spyder.SpyderG_GUI.SpyderG131_CachedMarketSnapshotMergeHelper import (
    build_cached_market_display_snapshot_result,
)


def test_build_cached_market_display_snapshot_result_preserves_first_source_precedence() -> None:
    result = build_cached_market_display_snapshot_result(
        [
            ("EOD snapshot", {"SPY": {"last": 742.31}, "VIX": {"last": 17.87}}),
            ("cached live quotes", {"SPY": {"last": 999.99}, "CPC": {"last": 1.206}}),
        ]
    )

    assert result == (
        {
            "SPY": {"last": 742.31},
            "VIX": {"last": 17.87},
            "CPC": {"last": 1.206},
        },
        "EOD snapshot + cached live quotes",
    )


def test_build_cached_market_display_snapshot_result_returns_single_label() -> None:
    result = build_cached_market_display_snapshot_result(
        [("cached live quotes", {"SPY": {"last": 742.31}})]
    )

    assert result == ({"SPY": {"last": 742.31}}, "cached live quotes")


def test_build_cached_market_display_snapshot_result_keeps_empty_dict_label_when_later_data_exists() -> None:
    result = build_cached_market_display_snapshot_result(
        [
            ("EOD snapshot", {}),
            ("cached live quotes", {"SPY": {"last": 742.31}, "_meta": "ignored"}),
            ("invalid payload", [1, 2, 3]),
        ]
    )

    assert result == ({"SPY": {"last": 742.31}}, "EOD snapshot + cached live quotes")
