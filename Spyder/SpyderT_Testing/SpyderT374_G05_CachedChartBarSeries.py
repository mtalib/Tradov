#!/usr/bin/env python3
"""Focused tests for G05 cached chart bar series wiring."""

from __future__ import annotations

from datetime import date, datetime, timezone

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
from Spyder.SpyderG_GUI.SpyderG133_CachedChartBarSeriesHelper import CachedChartBarSeries


class _DummySpine:
    def set_color(self, _color: str) -> None:
        return None


class _DummyAxes:
    def __init__(self) -> None:
        self.spines = {"left": _DummySpine(), "right": _DummySpine()}
        self.transAxes = object()

    def set_facecolor(self, _color: str) -> None:
        return None

    def text(self, *args, **kwargs) -> None:
        self.last_text = (args, kwargs)


class _DummyFigure:
    def clear(self) -> None:
        return None

    def add_subplot(self, *_args):
        return _DummyAxes()


class _DummyCanvas:
    def draw_idle(self) -> None:
        return None


class _FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 5, 14, 10, 15, tzinfo=tz)


def _build_dashboard_stub() -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.figure = _DummyFigure()
    dash.canvas = _DummyCanvas()
    return dash


def test_update_chart_passes_today_date_when_filtering_current_session(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    helper_calls: list[tuple[list[dict], date | None, object]] = []
    candles = [{"time": "2026-05-14T09:35:00", "close": 743.11}]

    monkeypatch.setattr(dash, "_load_chart_candles_from_cache", lambda: (candles, True))
    monkeypatch.setattr(g05, "datetime", _FrozenDateTime)
    monkeypatch.setattr(g05, "_get_eastern_timezone", lambda: timezone.utc)
    monkeypatch.setattr(
        g05,
        "build_cached_chart_bar_series",
        lambda candle_payload, preferred_target_date, fallback_parser: helper_calls.append(
            (candle_payload, preferred_target_date, fallback_parser)
        )
        or CachedChartBarSeries([], [], [], [], [], []),
    )

    SpyderTradingDashboard.update_chart(dash)

    assert helper_calls == [(candles, date(2026, 5, 14), g05._parse_chart_bar_timestamp)]


def test_update_chart_passes_none_target_date_for_off_hours_restore(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    helper_calls: list[tuple[list[dict], date | None, object]] = []
    candles = [{"time": "2026-05-13T15:55:00", "close": 742.31}]

    monkeypatch.setattr(dash, "_load_chart_candles_from_cache", lambda: (candles, False))
    monkeypatch.setattr(
        g05,
        "build_cached_chart_bar_series",
        lambda candle_payload, preferred_target_date, fallback_parser: helper_calls.append(
            (candle_payload, preferred_target_date, fallback_parser)
        )
        or CachedChartBarSeries([], [], [], [], [], []),
    )

    SpyderTradingDashboard.update_chart(dash)

    assert helper_calls == [(candles, None, g05._parse_chart_bar_timestamp)]
