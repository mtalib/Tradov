#!/usr/bin/env python3
"""Focused tests for G05 cached market snapshot merge wiring."""

from __future__ import annotations

import json
from pathlib import Path

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard


def _build_dashboard_stub(tmp_path: Path) -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.data_file = tmp_path / "live_data.json"
    return dash


def test_load_cached_market_display_snapshot_uses_helper_with_ordered_payloads(
    monkeypatch,
    tmp_path: Path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    helper_calls: list[list[tuple[str, object]]] = []
    eod_payload = {"SPY": {"last": 742.31}}
    live_payload = {"SPY": {"last": 999.99}, "CPC": {"last": 1.206}}

    (tmp_path / "eod_snapshot.json").write_text(json.dumps(eod_payload), encoding="utf-8")
    dash.data_file.write_text(json.dumps(live_payload), encoding="utf-8")
    monkeypatch.setattr(g05, "is_market_hours", lambda: False)
    monkeypatch.setattr(
        g05,
        "build_cached_market_display_snapshot_result",
        lambda loaded: helper_calls.append(list(loaded)) or ({"SPY": {"last": 742.31}}, "EOD snapshot + cached live quotes"),
    )

    result = SpyderTradingDashboard._load_cached_market_display_snapshot(dash)

    assert result == ({"SPY": {"last": 742.31}}, "EOD snapshot + cached live quotes")
    assert helper_calls == [[("EOD snapshot", eod_payload), ("cached live quotes", live_payload)]]


def test_load_cached_market_display_snapshot_preserves_parse_failure_boundary(
    monkeypatch,
    tmp_path: Path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    helper_calls: list[list[tuple[str, object]]] = []

    (tmp_path / "eod_snapshot.json").write_text("   ", encoding="utf-8")
    dash.data_file.write_text("{invalid json\n", encoding="utf-8")
    monkeypatch.setattr(g05, "is_market_hours", lambda: True)
    monkeypatch.setattr(
        g05,
        "build_cached_market_display_snapshot_result",
        lambda loaded: helper_calls.append(list(loaded)) or (None, None),
    )

    result = SpyderTradingDashboard._load_cached_market_display_snapshot(dash)

    assert result == (None, None)
    assert helper_calls == [[]]
