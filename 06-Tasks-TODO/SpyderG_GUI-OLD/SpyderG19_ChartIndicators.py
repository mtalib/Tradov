#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG19_ChartIndicators.py
Purpose: Pure-function chart indicator computation (§3 audit extraction)

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-04-16

Module Description:
    Pure functions that compute chart overlay values from OHLCV data.
    Extracted from SpyderG05_TradingDashboard.update_chart() per the
    2026-04-15 separation-of-concerns audit (§3):

        "These are indicator calculations, not rendering. They belong
         wherever the rest of SPYDER's technical analysis lives."

    These functions have no Qt dependency and are unit-testable without a
    display. SpyderG05 calls compute_chart_indicators() and receives a
    ChartIndicators dataclass ready for plotting.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from dataclasses import dataclass, field

# ==============================================================================
# TYPES
# ==============================================================================


@dataclass
class PivotLevels:
    """Standard floor-trader pivot levels derived from the session H/L/C."""
    pivot: float
    r1: float
    r2: float
    r3: float
    s1: float
    s2: float
    s3: float


@dataclass
class ChartIndicators:
    """All computed overlay series for one OHLCV dataset.

    Attributes:
        pivots:  Floor-trader pivot levels (P, R1-R3, S1-S3).
        ma20:    20-period simple moving average (None for the first 19 bars).
        vwap:    Session cumulative VWAP (one value per bar).
    """
    pivots: PivotLevels
    ma20: list[float | None] = field(default_factory=list)
    vwap: list[float] = field(default_factory=list)


# ==============================================================================
# PUBLIC API
# ==============================================================================

def compute_chart_indicators(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[int],
) -> ChartIndicators:
    """Compute pivot levels, MA(20), and session VWAP for an OHLCV dataset.

    This is a pure function — it performs no I/O, holds no state, and has no
    Qt dependency.  Callers must ensure all four lists have equal length and
    at least one element.

    Args:
        highs:   List of bar high prices.
        lows:    List of bar low prices.
        closes:  List of bar closing prices.
        volumes: List of bar volumes (integer tick counts or share counts).

    Returns:
        ChartIndicators dataclass containing pivot levels, MA(20) series,
        and VWAP series.

    Raises:
        ValueError: If *highs*, *lows*, *closes*, or *volumes* are empty or
                    have mismatched lengths.
    """
    n = len(closes)
    if n == 0:
        raise ValueError("OHLCV lists must not be empty")
    if not (len(highs) == len(lows) == len(volumes) == n):
        raise ValueError(
            "highs, lows, closes, and volumes must all have the same length"
        )

    pivots = _compute_pivot_levels(highs, lows, closes)
    ma20 = _compute_ma(closes, period=20)
    vwap = _compute_vwap(highs, lows, closes, volumes)

    return ChartIndicators(pivots=pivots, ma20=ma20, vwap=vwap)


# ==============================================================================
# PRIVATE HELPERS
# ==============================================================================

def _compute_pivot_levels(
    highs: list[float],
    lows: list[float],
    closes: list[float],
) -> PivotLevels:
    """Derive floor-trader pivot levels from the session range.

    The range is taken from the full OHLCV dataset (max high, min low, last
    close) as a proxy for the previous session when intraday bars are loaded.
    """
    prev_high = max(highs)
    prev_low = min(lows)
    prev_close = closes[-1]

    pivot = (prev_high + prev_low + prev_close) / 3
    rng = prev_high - prev_low
    return PivotLevels(
        pivot=pivot,
        r1=(2 * pivot) - prev_low,
        r2=pivot + rng,
        r3=prev_high + 2 * (pivot - prev_low),
        s1=(2 * pivot) - prev_high,
        s2=pivot - rng,
        s3=prev_low - 2 * (pivot - prev_low),
    )


def _compute_ma(prices: list[float], period: int = 20) -> list[float | None]:
    """Simple moving average.  Returns None for the first (period-1) bars."""
    result: list[float | None] = []
    for i in range(len(prices)):
        if i < period - 1:
            result.append(None)
        else:
            result.append(sum(prices[i - period + 1 : i + 1]) / period)
    return result


def _compute_vwap(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[int],
) -> list[float]:
    """Session cumulative VWAP using typical price × volume."""
    cumulative_pv = 0.0
    cumulative_volume = 0
    result: list[float] = []
    for i in range(len(closes)):
        typical = (highs[i] + lows[i] + closes[i]) / 3
        cumulative_pv += typical * volumes[i]
        cumulative_volume += volumes[i]
        # Guard against zero-volume bars (e.g. pre-market stubs)
        result.append(cumulative_pv / cumulative_volume if cumulative_volume else closes[i])
    return result
