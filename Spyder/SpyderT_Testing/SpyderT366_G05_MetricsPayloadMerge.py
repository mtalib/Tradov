#!/usr/bin/env python3
"""Focused tests for the G05 metrics payload merge wrapper."""

from __future__ import annotations

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard


def test_merge_metrics_payload_uses_helper(monkeypatch) -> None:
    helper_calls: list[tuple[dict | None, dict | None]] = []

    monkeypatch.setattr(
        g05,
        "merge_metrics_payload",
        lambda current, incoming: helper_calls.append((current, incoming)) or {"SPY": {"value": 1.0}},
    )

    result = SpyderTradingDashboard._merge_metrics_payload(
        {"SPY": {"value": 0.5}},
        {"SPY": {"value": 1.0}},
    )

    assert helper_calls == [({"SPY": {"value": 0.5}}, {"SPY": {"value": 1.0}})]
    assert result == {"SPY": {"value": 1.0}}
