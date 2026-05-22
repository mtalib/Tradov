#!/usr/bin/env python3
"""Focused regressions for D02 Iron Condor no-entry diagnostics."""

from __future__ import annotations

from datetime import UTC

import pandas as pd

from Spyder.SpyderD_Strategies.SpyderD02_IronCondor import (
    IronCondorAnalysis,
    IronCondorStrategy,
)


class _StubEventManager:
    def subscribe(self, *args, **kwargs):
        return None

    def emit(self, *args, **kwargs):
        return None

    def publish(self, *args, **kwargs):
        return None


def test_generate_signals_records_blockers_when_market_is_not_suitable(monkeypatch) -> None:
    strategy = IronCondorStrategy(event_manager=_StubEventManager(), config={})
    analysis = IronCondorAnalysis(
        market_suitable=False,
        iv_analysis={
            "iv_data_available": False,
            "iv_suitable_for_ic": False,
            "iv_rank": float("nan"),
        },
        volatility_skew=0.0,
        expected_move_analysis={
            "expected_move_percent": 0.01,
            "expected_move_suitable_for_ic": False,
        },
        trend_analysis={
            "is_range_bound": False,
            "trend_suitable_for_ic": False,
        },
        optimal_strikes=None,
        setup_recommendation="wait",
        confidence_score=0.0,
        risk_warnings=[],
    )
    market_data = pd.DataFrame(
        {
            "close": [500.0, 500.5],
            "high": [501.0, 501.2],
            "low": [499.5, 499.8],
        }
    )
    logged: list[str] = []

    monkeypatch.setattr(strategy, "analyze_iron_condor_opportunity", lambda _data: analysis)
    monkeypatch.setattr(
        strategy.logger,
        "info",
        lambda message, *args: logged.append(message % args if args else message),
    )

    signals = strategy.generate_signals(market_data)

    assert signals == []
    assert strategy.current_analysis is analysis
    assert analysis.risk_warnings == [
        "iv_data_unavailable",
        "expected_move_out_of_range",
        "trend_not_range_bound",
        "confidence_zero",
    ]
    assert logged
    assert "IronCondor no entry" in logged[-1]
    assert "iv_data_unavailable" in logged[-1]


def test_generate_signals_returns_utc_timestamp_for_valid_setup(monkeypatch) -> None:
    strategy = IronCondorStrategy(event_manager=_StubEventManager(), config={})
    analysis = IronCondorAnalysis(
        market_suitable=True,
        iv_analysis={
            "iv_data_available": True,
            "iv_suitable_for_ic": True,
            "iv_rank": 55.0,
        },
        volatility_skew=0.0,
        expected_move_analysis={
            "expected_move_percent": 0.01,
            "expected_move_suitable_for_ic": True,
        },
        trend_analysis={
            "is_range_bound": True,
            "trend_suitable_for_ic": True,
        },
        optimal_strikes={
            "short_put": 495.0,
            "long_put": 490.0,
            "short_call": 505.0,
            "long_call": 510.0,
        },
        setup_recommendation="enter",
        confidence_score=0.85,
        risk_warnings=[],
    )
    market_data = pd.DataFrame(
        {
            "close": [500.0, 500.5],
            "high": [501.0, 501.2],
            "low": [499.5, 499.8],
        }
    )

    monkeypatch.setattr(strategy, "analyze_iron_condor_opportunity", lambda _data: analysis)

    signals = strategy.generate_signals(market_data)

    assert len(signals) == 1
    signal = signals[0]
    assert signal.timestamp.tzinfo == UTC
    assert signal.expires_at.tzinfo == UTC
    assert signal.expires_at > signal.timestamp
    assert signal.metadata["strategy_type"] == "iron_condor"


def test_analyze_iv_for_iron_condor_prefers_explicit_iv_rank_hint() -> None:
    strategy = IronCondorStrategy(event_manager=_StubEventManager(), config={})
    market_data = pd.DataFrame(
        {
            "close": [500.0, 500.2, 500.1],
            "high": [500.3, 500.4, 500.2],
            "low": [499.8, 499.9, 499.7],
            "iv": [0.1838, 0.1838, 0.1838],
            "iv_rank": [44.5, 44.5, 44.5],
        }
    )

    analysis = strategy._analyze_iv_for_iron_condor(market_data)

    assert analysis["iv_data_available"] is True
    assert analysis["iv_rank"] == 44.5
    assert analysis["iv_suitable_for_ic"] is True


def test_analyze_iv_for_iron_condor_scales_fractional_iv_rank_hint() -> None:
    strategy = IronCondorStrategy(event_manager=_StubEventManager(), config={})
    market_data = pd.DataFrame(
        {
            "close": [500.0, 500.2, 500.1],
            "high": [500.3, 500.4, 500.2],
            "low": [499.8, 499.9, 499.7],
            "iv": [0.1838, 0.1838, 0.1838],
            "iv_rank": [0.445, 0.445, 0.445],
        }
    )

    analysis = strategy._analyze_iv_for_iron_condor(market_data)

    assert analysis["iv_data_available"] is True
    assert analysis["iv_rank"] == 44.5
    assert analysis["iv_suitable_for_ic"] is True


def test_analyze_iv_for_iron_condor_uses_neutral_rank_for_flat_live_snapshot() -> None:
    strategy = IronCondorStrategy(event_manager=_StubEventManager(), config={})
    market_data = pd.DataFrame(
        {
            "close": [500.0, 500.2, 500.1],
            "high": [500.3, 500.4, 500.2],
            "low": [499.8, 499.9, 499.7],
            "iv": [0.1838, 0.1838, 0.1838],
        }
    )

    analysis = strategy._analyze_iv_for_iron_condor(market_data)

    assert analysis["iv_data_available"] is True
    assert analysis["iv_rank"] == 50.0
    assert analysis["iv_suitable_for_ic"] is True
