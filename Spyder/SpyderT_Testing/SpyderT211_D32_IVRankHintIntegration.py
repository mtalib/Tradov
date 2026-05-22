#!/usr/bin/env python3
"""Focused regressions for D32 live IV-rank hint handling."""

from __future__ import annotations

from datetime import UTC, date, datetime

import numpy as np
import pandas as pd

from Spyder.SpyderD_Strategies.SpyderD32_MultiLegStrategyCoordinator import (
    MarketCondition,
    MarketEnvironmentAnalysis,
    MultiLegStrategyConstructor,
    MultiLegMarketAnalyzer,
    VolatilityEnvironment,
)


def _market_data(rows: int = 120, iv_rank: float | None = None, ivr: float | None = None) -> pd.DataFrame:
    close = np.linspace(500.0, 520.0, rows)
    data: dict[str, object] = {"close": close}
    if iv_rank is not None:
        data["iv_rank"] = [iv_rank] * rows
    if ivr is not None:
        data["IVR"] = [ivr] * rows
    return pd.DataFrame(data)


def test_calculate_iv_rank_prefers_live_iv_rank_hint_without_warning(monkeypatch) -> None:
    analyzer = MultiLegMarketAnalyzer(config={})
    market_data = _market_data(iv_rank=44.5)
    logged: list[str] = []

    monkeypatch.setattr(
        analyzer.logger,
        "warning",
        lambda message, *args: logged.append(message % args if args else message),
    )

    iv_rank = analyzer._calculate_iv_rank(market_data, current_iv=0.25)

    assert iv_rank == 0.445
    assert logged == []


def test_calculate_iv_rank_prefers_live_ivr_column_without_warning(monkeypatch) -> None:
    analyzer = MultiLegMarketAnalyzer(config={})
    market_data = _market_data(ivr=62.0)
    logged: list[str] = []

    monkeypatch.setattr(
        analyzer.logger,
        "warning",
        lambda message, *args: logged.append(message % args if args else message),
    )

    iv_rank = analyzer._calculate_iv_rank(market_data, current_iv=0.25)

    assert iv_rank == 0.62
    assert logged == []


def test_calculate_iv_rank_warns_when_falling_back_to_proxy(monkeypatch) -> None:
    analyzer = MultiLegMarketAnalyzer(config={})
    market_data = _market_data()
    logged: list[str] = []

    monkeypatch.setattr(
        analyzer.logger,
        "warning",
        lambda message, *args: logged.append(message % args if args else message),
    )

    iv_rank = analyzer._calculate_iv_rank(market_data, current_iv=0.25)

    assert 0.0 <= iv_rank <= 1.0
    assert any("realized volatility proxy" in message.lower() for message in logged)


def test_construct_iron_condor_aligns_to_live_chain(monkeypatch) -> None:
    constructor = MultiLegStrategyConstructor(config={"underlying_symbol": "SPY"})
    market_analysis = MarketEnvironmentAnalysis(
        timestamp=datetime(2026, 5, 19, tzinfo=UTC),
        underlying_price=734.5,
        volatility_environment=VolatilityEnvironment.NORMAL_VOL,
        market_condition=MarketCondition.RANGE_BOUND,
        implied_volatility=0.25,
        vix_level=20.0,
        iv_rank=0.5,
        iv_percentile=0.5,
        volatility_skew=0.0,
        term_structure_slope=0.0,
        support_resistance_range=15.0,
        expected_move=35.0,
        trend_strength=0.0,
        momentum_score=0.0,
    )

    monkeypatch.setattr(constructor, "_calculate_optimal_wing_width", lambda _analysis: 10.0)
    monkeypatch.setattr(
        constructor,
        "_estimate_legs_pricing_and_greeks",
        lambda legs, *_args: None,
    )
    monkeypatch.setattr(constructor, "_calculate_net_credit", lambda _legs: 1.5)
    monkeypatch.setattr(
        constructor,
        "_estimate_probability_profit",
        lambda *_args: 0.73,
    )
    monkeypatch.setattr(
        constructor,
        "_get_live_option_chain_strikes",
        lambda symbol, expiration: {
            "put": [689.0, 690.0, 699.0, 700.0],
            "call": [770.0, 780.0],
        },
    )

    structure = constructor._construct_iron_condor(market_analysis, dte=30)

    assert structure is not None
    assert [leg.strike for leg in structure.legs] == [689.0, 699.0, 770.0, 780.0]
    assert structure.body_width == 71.0
    assert structure.wing_width == 10.0


def test_resolve_live_option_expiration_prefers_nearest_listed_contract(monkeypatch) -> None:
    constructor = MultiLegStrategyConstructor(config={"underlying_symbol": "SPY"})

    monkeypatch.setattr(
        constructor,
        "_get_live_option_expiration_dates",
        lambda symbol: [date(2026, 6, 18), date(2026, 6, 26)],
    )

    resolved_expiration = constructor._resolve_live_option_expiration(
        "SPY",
        datetime(2026, 6, 19, 15, 45, tzinfo=UTC),
    )

    assert resolved_expiration == datetime(2026, 6, 18, 15, 45, tzinfo=UTC)
