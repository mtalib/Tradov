#!/usr/bin/env python3
"""Focused tests for G05 system-log suppression wrapper behavior."""

from __future__ import annotations

from types import SimpleNamespace

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard


def test_after_hours_system_log_suppression_uses_helper_when_market_closed(monkeypatch) -> None:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash._quiet_after_hours_logs = True
    helper_calls: list[object] = []

    monkeypatch.setattr(g05, "is_market_hours", lambda: False)
    monkeypatch.setattr(
        g05,
        "should_suppress_after_hours_system_log_text",
        lambda message: helper_calls.append(message) or True,
    )

    result = SpyderTradingDashboard._should_suppress_after_hours_system_log(
        dash,
        "📊 EOD snapshot loaded",
    )

    assert result is True
    assert helper_calls == ["📊 EOD snapshot loaded"]


def test_after_hours_system_log_suppression_short_circuits_when_disabled(monkeypatch) -> None:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash._quiet_after_hours_logs = False

    helper = []
    monkeypatch.setattr(g05, "is_market_hours", lambda: False)
    monkeypatch.setattr(
        g05,
        "should_suppress_after_hours_system_log_text",
        lambda message: helper.append(message) or True,
    )

    result = SpyderTradingDashboard._should_suppress_after_hours_system_log(
        dash,
        "📊 EOD snapshot loaded",
    )

    assert result is False
    assert helper == []


def test_opening_warmup_system_log_suppression_uses_helper_when_active(monkeypatch) -> None:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    helper_calls: list[object] = []
    dash._is_opening_runtime_warmup_active = lambda: True

    monkeypatch.setattr(
        g05,
        "should_suppress_opening_warmup_system_log_text",
        lambda message: helper_calls.append(message) or False,
    )

    result = SpyderTradingDashboard._should_suppress_opening_warmup_system_log(
        dash,
        "🟡 Establishing live connections and loading live data",
    )

    assert result is False
    assert helper_calls == ["🟡 Establishing live connections and loading live data"]


def test_opening_warmup_system_log_suppression_short_circuits_when_inactive(monkeypatch) -> None:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash._is_opening_runtime_warmup_active = lambda: False
    helper_calls: list[object] = []

    monkeypatch.setattr(
        g05,
        "should_suppress_opening_warmup_system_log_text",
        lambda message: helper_calls.append(message) or True,
    )

    result = SpyderTradingDashboard._should_suppress_opening_warmup_system_log(
        dash,
        "📦 Restored 30 symbols from EOD snapshot",
    )

    assert result is False
    assert helper_calls == []
