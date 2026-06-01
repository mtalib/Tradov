#!/usr/bin/env python3
"""Focused tests for G05 cached chart candle loading wiring."""

from __future__ import annotations

import json
from pathlib import Path

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard


def _build_dashboard_stub(tmp_path: Path) -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.data_file = tmp_path / "live_data.json"
    return dash


def test_load_chart_candles_from_cache_uses_helper_with_off_hours_priority(
    monkeypatch,
    tmp_path: Path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    helper_calls: list[list[tuple[object, bool]]] = []
    prev_day_bars = [{"time": "2026-05-13T15:55:00", "close": 742.31}]
    current_bars = [{"time": "2026-05-14T09:35:00", "close": 743.11}]

    (tmp_path / "spy_5min_prev_day.json").write_text(json.dumps(prev_day_bars), encoding="utf-8")
    (tmp_path / "spy_5min_chart.json").write_text(json.dumps(current_bars), encoding="utf-8")
    monkeypatch.setattr(g05, "is_market_hours", lambda: False)
    monkeypatch.setattr(
        g05,
        "build_cached_chart_candles_result",
        lambda loaded: helper_calls.append(list(loaded)) or (prev_day_bars, False),
    )

    result = SpyderTradingDashboard._load_chart_candles_from_cache(dash)

    assert result == (prev_day_bars, False)
    assert helper_calls == [[(prev_day_bars, False), (current_bars, False)]]


def test_load_chart_candles_from_cache_skips_unreadable_sources_before_helper(
    monkeypatch,
    tmp_path: Path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    helper_calls: list[list[tuple[object, bool]]] = []
    current_bars = [{"time": "2026-05-14T09:35:00", "close": 743.11}]

    (tmp_path / "spy_5min_prev_day.json").write_text("{invalid json\n", encoding="utf-8")
    (tmp_path / "spy_5min_chart.json").write_text(json.dumps(current_bars), encoding="utf-8")
    monkeypatch.setattr(g05, "is_market_hours", lambda: False)
    monkeypatch.setattr(
        g05,
        "build_cached_chart_candles_result",
        lambda loaded: helper_calls.append(list(loaded)) or (current_bars, False),
    )

    result = SpyderTradingDashboard._load_chart_candles_from_cache(dash)

    assert result == (current_bars, False)
    assert helper_calls == [[(current_bars, False)]]


def test_load_chart_candles_from_cache_prefers_spx_default_over_legacy_spy(
    monkeypatch,
    tmp_path: Path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    helper_calls: list[list[tuple[object, bool]]] = []
    spx_bars = [{"time": "2026-05-14T09:35:00", "close": 5431.25}]
    legacy_spy_bars = [{"time": "2026-05-14T09:35:00", "close": 5430.75}]

    (tmp_path / "spx_5min_chart.json").write_text(json.dumps(spx_bars), encoding="utf-8")
    (tmp_path / "spy_5min_chart.json").write_text(json.dumps(legacy_spy_bars), encoding="utf-8")
    monkeypatch.delenv("SPYDER_UNDERLYING_SYMBOL", raising=False)
    monkeypatch.setattr(g05, "is_market_hours", lambda: True)
    monkeypatch.setattr(
        g05,
        "build_cached_chart_candles_result",
        lambda loaded: helper_calls.append(list(loaded)) or (spx_bars, True),
    )

    result = SpyderTradingDashboard._load_chart_candles_from_cache(dash)

    assert result == (spx_bars, True)
    assert helper_calls == [[(spx_bars, True), (legacy_spy_bars, True)]]
