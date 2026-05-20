#!/usr/bin/env python3
"""Focused tests for G67 readiness decision helper."""

import Spyder.SpyderG_GUI.SpyderG67_ReadinessDecisionHelper as g67
from Spyder.SpyderG_GUI.SpyderG67_ReadinessDecisionHelper import (
    build_trading_readiness_evaluation,
)


def test_build_trading_readiness_evaluation_accepts_live_equivalent_data_status() -> None:
    snapshot = {
        "is_weekend": False,
        "is_market_hours": True,
        "startup_state": {
            "live_blocking": False,
            "safe_fallback_applied": False,
        },
        "api_connected": True,
        "mkt_data_connected": True,
        "data_status_label": "REAL-TIME",
        "event_clock_enabled": False,
        "event_clock_state": "clear",
        "checked_at_et": "2026-05-15T09:31:00-04:00",
    }

    result = build_trading_readiness_evaluation(snapshot)

    assert result["decision"] == "OK"
    assert result["conditional"] is False
    assert result["warnings"] == []


def test_build_trading_readiness_evaluation_marks_conditional_for_warning_only_snapshot() -> None:
    snapshot = {
        "is_weekend": False,
        "is_market_hours": True,
        "startup_state": {},
        "api_connected": True,
        "mkt_data_connected": True,
        "data_status_label": "DELAYED",
        "event_clock_enabled": True,
        "event_clock_state": "pre",
        "checked_at_et": "2026-05-15T09:31:00-04:00",
    }

    result = build_trading_readiness_evaluation(snapshot)

    assert result["decision"] == "OK"
    assert result["conditional"] is True
    assert result["reasons"] == []
    assert result["warnings"] == [
        "Data status is DELAYED (not explicit LIVE)",
        "Event-clock state is pre; reduced-risk policy recommended",
    ]


def test_build_trading_readiness_evaluation_marks_no_for_blocking_conditions() -> None:
    snapshot = {
        "is_weekend": True,
        "is_market_hours": False,
        "startup_state": {
            "live_blocking": True,
            "safe_fallback_applied": True,
        },
        "api_connected": False,
        "mkt_data_connected": False,
        "data_status_label": "LIVE",
        "event_clock_enabled": False,
        "event_clock_state": "clear",
        "checked_at_et": "2026-05-17T09:31:00-04:00",
    }

    result = build_trading_readiness_evaluation(snapshot)

    assert result["decision"] == "NO"
    assert result["conditional"] is False
    assert result["warnings"] == []
    assert result["reasons"] == [
        "Market is closed (weekend)",
        "Market is closed (outside regular trading hours)",
        "A03 readiness validation reports live-blocking configuration errors",
        "Automation safe fallback is active from startup readiness validation",
        "Tradier execution API is disconnected",
        "Market data feed is disconnected",
    ]


def test_build_trading_readiness_evaluation_uses_live_data_status_helper(monkeypatch) -> None:
    helper_calls: list[object] = []

    monkeypatch.setattr(
        g67,
        "is_live_equivalent_data_status",
        lambda value: helper_calls.append(value) or False,
    )

    result = build_trading_readiness_evaluation(
        {
            "is_weekend": False,
            "is_market_hours": True,
            "startup_state": {},
            "api_connected": True,
            "mkt_data_connected": True,
            "data_status_label": "  live - real  ",
            "event_clock_enabled": False,
            "event_clock_state": "clear",
            "checked_at_et": "2026-05-15T09:31:00-04:00",
        }
    )

    assert helper_calls == ["  live - real  "]
    assert result["warnings"] == ["Data status is LIVE - REAL (not explicit LIVE)"]