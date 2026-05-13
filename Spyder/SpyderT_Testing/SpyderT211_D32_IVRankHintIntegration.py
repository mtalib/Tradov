#!/usr/bin/env python3
"""Focused regressions for D32 live IV-rank hint handling."""

from __future__ import annotations

import numpy as np
import pandas as pd

from Spyder.SpyderD_Strategies.SpyderD32_MultiLegStrategyCoordinator import (
    MultiLegMarketAnalyzer,
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