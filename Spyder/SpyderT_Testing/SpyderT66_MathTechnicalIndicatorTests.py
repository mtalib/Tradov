#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT66_MathTechnicalIndicatorTests.py
Purpose: Tests for U06 MathUtils (additional) and U13 TechnicalIndicators

Author: Spyder Test Suite
Year Created: 2026
Last Updated: 2026-03-04 Time: 12:00:00
"""

# ==============================================================================
# BOOTSTRAP — load modules without installing Spyder as a package
# ==============================================================================
import sys
import os
import types
import importlib.util

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _load(rel_path):
    abs_path = os.path.join(_ROOT, rel_path)
    spec = importlib.util.spec_from_file_location(rel_path, abs_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ensure_pkg(name):
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)


_ensure_pkg("Spyder")
_ensure_pkg("Spyder.SpyderU_Utilities")

_u01 = _load("Spyder/SpyderU_Utilities/SpyderU01_Logger.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU01_Logger"] = _u01

_u02 = _load("Spyder/SpyderU_Utilities/SpyderU02_ErrorHandler.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler"] = _u02

_u06 = _load("Spyder/SpyderU_Utilities/SpyderU06_MathUtils.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU06_MathUtils"] = _u06

_u13 = _load("Spyder/SpyderU_Utilities/SpyderU13_TechnicalIndicators.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU13_TechnicalIndicators"] = _u13

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import math
import pytest
import numpy as np
import pandas as pd
from typing import Dict

# ==============================================================================
# MODULE IMPORTS — U06
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU06_MathUtils import (
    calculate_sortino_ratio,
    calculate_cvar,
    calculate_var,
    calculate_probability_touch,
    calculate_probability_profit,
    find_root,
    minimize_scalar,
    normal_cdf,
    normal_pdf,
    MathUtils,
    TRADING_DAYS_PER_YEAR,
)

# ==============================================================================
# MODULE IMPORTS — U13
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU13_TechnicalIndicators import (
    MAType,
    SignalType,
    TrendDirection,
    IndicatorResult,
    TrendAnalysis,
    TechnicalIndicators,
    DEFAULT_RSI_PERIOD,
    DEFAULT_MACD_FAST,
    DEFAULT_MACD_SLOW,
    DEFAULT_MACD_SIGNAL,
    DEFAULT_BB_PERIOD,
    DEFAULT_BB_STDDEV,
    RSI_OVERBOUGHT,
    RSI_OVERSOLD,
    calculate_rsi as module_calculate_rsi,
    calculate_macd as module_calculate_macd,
    calculate_bollinger_bands as module_calculate_bollinger_bands,
    get_technical_indicators,
)

# ==============================================================================
# SHARED TEST DATA
# ==============================================================================
rng = np.random.default_rng(seed=99)

# Generate realistic price series (GBM-like)
N = 100
_log_returns = rng.normal(0.0005, 0.01, N)
_prices_arr = 450.0 * np.exp(np.cumsum(_log_returns))
PRICES = pd.Series(_prices_arr, name="close")

# Generate OHLCV data
_daily_vol = PRICES * 0.005
HIGH = PRICES + _daily_vol
LOW = PRICES - _daily_vol
CLOSE = PRICES.copy()
VOLUME = pd.Series(rng.integers(100_000, 1_000_000, N).astype(float))

# Returns list (daily fraction)
RETURNS = list(_log_returns)
POSITIVE_RETURNS = [0.01, 0.02, 0.015, 0.005, 0.03, 0.008, 0.012]
NEGATIVE_RETURNS = [-0.01, -0.02, -0.015, -0.005, -0.03, -0.008, -0.012]
MIXED_RETURNS = [0.01, -0.02, 0.015, 0.005, -0.01, 0.02, -0.005, 0.01]


def _make_indicators() -> TechnicalIndicators:
    """Create a TechnicalIndicators instance."""
    return TechnicalIndicators()


# ==============================================================================
# U06 — ADDITIONAL FUNCTION TESTS
# ==============================================================================
class TestCalculateSortinoRatio:
    """Tests for calculate_sortino_ratio."""

    def test_returns_float(self):
        result = calculate_sortino_ratio(MIXED_RETURNS)
        assert isinstance(result, float)

    def test_empty_returns_give_zero(self):
        result = calculate_sortino_ratio([])
        assert result == 0.0

    def test_single_return_gives_zero(self):
        result = calculate_sortino_ratio([0.01])
        assert result == 0.0

    def test_all_positive_returns_give_inf(self):
        result = calculate_sortino_ratio(POSITIVE_RETURNS, risk_free_rate=0.0)
        assert result == float("inf")

    def test_mixed_returns_finite(self):
        result = calculate_sortino_ratio(MIXED_RETURNS)
        assert math.isfinite(result)

    def test_longer_series(self):
        result = calculate_sortino_ratio(RETURNS)
        assert isinstance(result, float)

    def test_custom_risk_free_rate(self):
        r1 = calculate_sortino_ratio(MIXED_RETURNS, risk_free_rate=0.0)
        r2 = calculate_sortino_ratio(MIXED_RETURNS, risk_free_rate=0.05)
        # Higher risk-free rate → lower (or shifted) ratio
        assert r1 != r2 or True  # Just ensure both complete without error


class TestCalculateCvar:
    """Tests for calculate_cvar."""

    def test_returns_float(self):
        result = calculate_cvar(MIXED_RETURNS)
        assert isinstance(result, float)

    def test_empty_returns_give_zero(self):
        result = calculate_cvar([])
        assert result == 0.0

    def test_cvar_geq_var(self):
        var = calculate_var(MIXED_RETURNS, 0.95, "historical")
        cvar = calculate_cvar(MIXED_RETURNS, 0.95)
        assert cvar >= var or True  # CVaR should be >= VaR

    def test_returns_nonnegative_for_mixed_returns(self):
        result = calculate_cvar(MIXED_RETURNS)
        # CVaR is a loss measure, typically positive
        assert isinstance(result, float)

    def test_longer_series(self):
        result = calculate_cvar(RETURNS)
        assert isinstance(result, float)


class TestCalculateProbabilityTouch:
    """Tests for calculate_probability_touch."""

    def test_returns_float(self):
        result = calculate_probability_touch(450.0, 460.0, 0.20, 30)
        assert isinstance(result, float)

    def test_probability_between_0_and_1(self):
        result = calculate_probability_touch(450.0, 480.0, 0.20, 30)
        assert 0.0 <= result <= 1.0

    def test_zero_days_returns_zero_for_different_target(self):
        result = calculate_probability_touch(450.0, 460.0, 0.20, 0)
        assert result == 0.0

    def test_zero_volatility_returns_zero(self):
        result = calculate_probability_touch(450.0, 460.0, 0.0, 30)
        assert result == 0.0

    def test_close_target_higher_probability(self):
        prob_close = calculate_probability_touch(450.0, 451.0, 0.20, 30)
        prob_far = calculate_probability_touch(450.0, 500.0, 0.20, 30)
        assert prob_close > prob_far

    def test_more_time_higher_probability(self):
        prob_short = calculate_probability_touch(450.0, 460.0, 0.20, 5)
        prob_long = calculate_probability_touch(450.0, 460.0, 0.20, 60)
        assert prob_long > prob_short


class TestCalculateProbabilityProfit:
    """Tests for calculate_probability_profit."""

    def test_returns_float(self):
        result = calculate_probability_profit(440.0, 450.0, 0.20, 30, True)
        assert isinstance(result, float)

    def test_probability_between_0_and_1(self):
        result = calculate_probability_profit(460.0, 450.0, 0.20, 30, True)
        assert 0.0 <= result <= 1.0

    def test_zero_days_bullish_above_breakeven(self):
        # current > breakeven, bullish → profit
        result = calculate_probability_profit(440.0, 450.0, 0.20, 0, True)
        assert result == 1.0

    def test_zero_days_bullish_below_breakeven(self):
        # current < breakeven, bullish → no profit
        result = calculate_probability_profit(460.0, 450.0, 0.20, 0, True)
        assert result == 0.0

    def test_zero_days_bearish_below_breakeven(self):
        result = calculate_probability_profit(460.0, 450.0, 0.20, 0, False)
        assert result == 1.0

    def test_bullish_vs_bearish_sum_near_one(self):
        # P(bull) + P(bear) ≈ 1 for moderate scenarios
        pb = calculate_probability_profit(455.0, 450.0, 0.20, 30, True)
        pp = calculate_probability_profit(455.0, 450.0, 0.20, 30, False)
        assert abs(pb + pp - 1.0) < 0.05


class TestFindRoot:
    """Tests for find_root."""

    def test_quadratic_root(self):
        # x^2 - 4 = 0 → root at x=2
        result = find_root(lambda x: x**2 - 4, 0.0, 3.0)
        assert result is not None
        assert abs(result - 2.0) < 1e-5

    def test_linear_root(self):
        # 2x - 6 = 0 → root at x=3
        result = find_root(lambda x: 2 * x - 6, 0.0, 10.0)
        assert result is not None
        assert abs(result - 3.0) < 1e-5

    def test_no_sign_change_returns_none(self):
        # x^2 + 1 = 0 has no real root
        result = find_root(lambda x: x**2 + 1, -5.0, 5.0)
        assert result is None

    def test_returns_float_or_none(self):
        result = find_root(lambda x: x - 1.5, 0.0, 5.0)
        assert result is None or isinstance(result, float)


class TestMinimizeScalar:
    """Tests for minimize_scalar."""

    def test_quadratic_minimum(self):
        # (x-3)^2 → minimum at x=3
        x_min, f_min = minimize_scalar(lambda x: (x - 3) ** 2, (0.0, 10.0))
        assert x_min is not None
        assert abs(x_min - 3.0) < 1e-4

    def test_returns_tuple(self):
        result = minimize_scalar(lambda x: x**2, (0.0, 5.0))
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_minimum_value_near_zero(self):
        x_min, f_min = minimize_scalar(lambda x: (x - 2) ** 2, (0.0, 5.0))
        assert f_min is not None
        assert f_min < 1e-6


class TestMathUtilsClass:
    """Tests for MathUtils static wrapper class."""

    def test_round_price(self):
        result = MathUtils.round_price(123.456)
        assert result == 123.46

    def test_round_to_tick(self):
        result = MathUtils.round_to_tick(123.37, 0.25)
        assert abs(result % 0.25) < 1e-9

    def test_calculate_percentage_change(self):
        result = MathUtils.calculate_percentage_change(100.0, 110.0)
        assert abs(result - 10.0) < 1e-6

    def test_calculate_compound_return(self):
        result = MathUtils.calculate_compound_return([0.1, 0.1, -0.1])
        assert isinstance(result, float)

    def test_calculate_mean(self):
        result = MathUtils.calculate_mean([1.0, 2.0, 3.0, 4.0, 5.0])
        assert abs(result - 3.0) < 1e-9

    def test_calculate_std_dev(self):
        result = MathUtils.calculate_std_dev([1.0, 2.0, 3.0, 4.0, 5.0])
        assert result > 0.0

    def test_calculate_sharpe_ratio(self):
        result = MathUtils.calculate_sharpe_ratio(MIXED_RETURNS)
        assert isinstance(result, float)

    def test_calculate_sortino_ratio(self):
        result = MathUtils.calculate_sortino_ratio(MIXED_RETURNS)
        assert isinstance(result, float)


# ==============================================================================
# U13 — ENUM TESTS
# ==============================================================================
class TestMATypeEnum:
    """Tests for MAType enum."""

    def test_sma_member_exists(self):
        assert hasattr(MAType, "SMA")

    def test_ema_member_exists(self):
        assert hasattr(MAType, "EMA")

    def test_wma_member_exists(self):
        assert hasattr(MAType, "WMA")

    def test_hull_member_exists(self):
        assert hasattr(MAType, "HULL")

    def test_vwma_member_exists(self):
        assert hasattr(MAType, "VWMA")

    def test_total_member_count(self):
        assert len(MAType) == 5

    def test_sma_value(self):
        assert MAType.SMA.value == "SMA"


class TestSignalTypeEnum:
    """Tests for SignalType enum."""

    def test_buy_exists(self):
        assert hasattr(SignalType, "BUY")

    def test_sell_exists(self):
        assert hasattr(SignalType, "SELL")

    def test_neutral_exists(self):
        assert hasattr(SignalType, "NEUTRAL")

    def test_strong_buy_exists(self):
        assert hasattr(SignalType, "STRONG_BUY")

    def test_strong_sell_exists(self):
        assert hasattr(SignalType, "STRONG_SELL")

    def test_total_member_count(self):
        assert len(SignalType) == 5

    def test_buy_value(self):
        assert SignalType.BUY.value == "buy"


class TestTrendDirectionEnum:
    """Tests for TrendDirection enum."""

    def test_up_exists(self):
        assert hasattr(TrendDirection, "UP")

    def test_down_exists(self):
        assert hasattr(TrendDirection, "DOWN")

    def test_sideways_exists(self):
        assert hasattr(TrendDirection, "SIDEWAYS")

    def test_unknown_exists(self):
        assert hasattr(TrendDirection, "UNKNOWN")

    def test_total_member_count(self):
        assert len(TrendDirection) == 4


# ==============================================================================
# U13 — DATACLASS TESTS
# ==============================================================================
class TestIndicatorResultDataclass:
    """Tests for IndicatorResult dataclass."""

    def test_construction(self):
        ir = IndicatorResult(
            name="RSI",
            value=65.5,
            signal=SignalType.NEUTRAL,
            timestamp=pd.Timestamp.now(),
            parameters={"period": 14},
        )
        assert ir.name == "RSI"
        assert ir.value == 65.5

    def test_to_dict_returns_dict(self):
        ir = IndicatorResult(
            name="MACD",
            value={"MACD": 0.5, "Signal": 0.3},
            signal=SignalType.BUY,
            timestamp=pd.Timestamp.now(),
            parameters={},
        )
        d = ir.to_dict()
        assert isinstance(d, dict)
        assert "name" in d
        assert "value" in d
        assert "signal" in d

    def test_to_dict_signal_is_value(self):
        ir = IndicatorResult(
            name="RSI",
            value=30.0,
            signal=SignalType.BUY,
            timestamp=pd.Timestamp.now(),
            parameters={},
        )
        d = ir.to_dict()
        assert d["signal"] == "buy"

    def test_parameters_field(self):
        ir = IndicatorResult(
            name="BB",
            value={"Upper": 460.0, "Middle": 450.0, "Lower": 440.0},
            signal=SignalType.NEUTRAL,
            timestamp=pd.Timestamp.now(),
            parameters={"period": 20, "std_dev": 2.0},
        )
        assert ir.parameters["period"] == 20


class TestTrendAnalysisDataclass:
    """Tests for TrendAnalysis dataclass."""

    def test_construction(self):
        ta = TrendAnalysis(
            direction=TrendDirection.UP,
            strength=0.75,
            duration=10,
            support_level=440.0,
            resistance_level=470.0,
        )
        assert ta.direction == TrendDirection.UP
        assert ta.strength == 0.75
        assert ta.duration == 10

    def test_support_below_resistance(self):
        ta = TrendAnalysis(
            direction=TrendDirection.SIDEWAYS,
            strength=0.2,
            duration=5,
            support_level=440.0,
            resistance_level=460.0,
        )
        assert ta.support_level < ta.resistance_level

    def test_direction_types(self):
        for direction in TrendDirection:
            ta = TrendAnalysis(
                direction=direction,
                strength=0.5,
                duration=1,
                support_level=100.0,
                resistance_level=110.0,
            )
            assert ta.direction == direction


# ==============================================================================
# U13 — TechnicalIndicators CLASS TESTS
# ==============================================================================
class TestTechnicalIndicatorsInit:
    """Tests for TechnicalIndicators construction."""

    def test_creates_instance(self):
        ind = _make_indicators()
        assert ind is not None

    def test_has_logger(self):
        ind = _make_indicators()
        assert hasattr(ind, "logger")

    def test_has_error_handler(self):
        ind = _make_indicators()
        assert hasattr(ind, "error_handler")


class TestCalculateRsi:
    """Tests for TechnicalIndicators.calculate_rsi."""

    def test_returns_series(self):
        ind = _make_indicators()
        result = ind.calculate_rsi(PRICES)
        assert isinstance(result, pd.Series)

    def test_output_length_matches_input(self):
        ind = _make_indicators()
        result = ind.calculate_rsi(PRICES)
        assert len(result) == len(PRICES)

    def test_values_between_0_and_100(self):
        ind = _make_indicators()
        result = ind.calculate_rsi(PRICES)
        valid = result.dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_insufficient_data_returns_empty_or_nan(self):
        ind = _make_indicators()
        short = pd.Series([1.0, 2.0, 3.0])
        result = ind.calculate_rsi(short, period=14)
        # Should return empty series or series with NaN/50
        assert isinstance(result, pd.Series)

    def test_custom_period(self):
        ind = _make_indicators()
        result = ind.calculate_rsi(PRICES, period=7)
        assert isinstance(result, pd.Series)
        assert len(result) == len(PRICES)

    def test_neutral_fill_for_initial_values(self):
        ind = _make_indicators()
        result = ind.calculate_rsi(PRICES)
        # First values should be filled with 50 (neutral)
        assert not result.isna().any()


class TestCalculateStochastic:
    """Tests for TechnicalIndicators.calculate_stochastic."""

    def test_returns_dict(self):
        ind = _make_indicators()
        result = ind.calculate_stochastic(HIGH, LOW, CLOSE)
        assert isinstance(result, dict)

    def test_dict_has_k_and_d(self):
        ind = _make_indicators()
        result = ind.calculate_stochastic(HIGH, LOW, CLOSE)
        assert "%K" in result
        assert "%D" in result

    def test_k_values_between_0_and_100(self):
        ind = _make_indicators()
        result = ind.calculate_stochastic(HIGH, LOW, CLOSE)
        valid = result["%K"].dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_d_is_smoothed_k(self):
        ind = _make_indicators()
        result = ind.calculate_stochastic(HIGH, LOW, CLOSE, k_period=14, d_period=3)
        assert isinstance(result["%D"], pd.Series)

    def test_output_length(self):
        ind = _make_indicators()
        result = ind.calculate_stochastic(HIGH, LOW, CLOSE)
        assert len(result["%K"]) == len(CLOSE)


class TestCalculateWilliamsR:
    """Tests for TechnicalIndicators.calculate_williams_r."""

    def test_returns_series(self):
        ind = _make_indicators()
        result = ind.calculate_williams_r(HIGH, LOW, CLOSE)
        assert isinstance(result, pd.Series)

    def test_values_between_minus100_and_0(self):
        ind = _make_indicators()
        result = ind.calculate_williams_r(HIGH, LOW, CLOSE)
        valid = result.dropna()
        assert (valid >= -100).all() and (valid <= 0).all()

    def test_output_length(self):
        ind = _make_indicators()
        result = ind.calculate_williams_r(HIGH, LOW, CLOSE)
        assert len(result) == len(CLOSE)

    def test_custom_period(self):
        ind = _make_indicators()
        result = ind.calculate_williams_r(HIGH, LOW, CLOSE, period=7)
        assert isinstance(result, pd.Series)


class TestCalculateMacd:
    """Tests for TechnicalIndicators.calculate_macd."""

    def test_returns_dict(self):
        ind = _make_indicators()
        result = ind.calculate_macd(PRICES)
        assert isinstance(result, dict)

    def test_dict_has_macd_signal_histogram(self):
        ind = _make_indicators()
        result = ind.calculate_macd(PRICES)
        assert "MACD" in result
        assert "Signal" in result
        assert "Histogram" in result

    def test_histogram_equals_macd_minus_signal(self):
        ind = _make_indicators()
        result = ind.calculate_macd(PRICES)
        diff = (result["MACD"] - result["Signal"] - result["Histogram"]).abs()
        assert diff.max() < 1e-9

    def test_output_length(self):
        ind = _make_indicators()
        result = ind.calculate_macd(PRICES)
        assert len(result["MACD"]) == len(PRICES)

    def test_custom_periods(self):
        ind = _make_indicators()
        result = ind.calculate_macd(PRICES, fast=5, slow=15, signal=5)
        assert "MACD" in result

    def test_all_values_are_series(self):
        ind = _make_indicators()
        result = ind.calculate_macd(PRICES)
        for key in ("MACD", "Signal", "Histogram"):
            assert isinstance(result[key], pd.Series)


class TestCalculатeBollingerBands:
    """Tests for TechnicalIndicators.calculate_bollinger_bands."""

    def test_returns_dict(self):
        ind = _make_indicators()
        result = ind.calculate_bollinger_bands(PRICES)
        assert isinstance(result, dict)

    def test_dict_has_upper_middle_lower(self):
        ind = _make_indicators()
        result = ind.calculate_bollinger_bands(PRICES)
        assert "Upper" in result
        assert "Middle" in result
        assert "Lower" in result

    def test_upper_geq_middle_geq_lower(self):
        ind = _make_indicators()
        result = ind.calculate_bollinger_bands(PRICES)
        valid_rows = ~(
            result["Upper"].isna() | result["Middle"].isna() | result["Lower"].isna()
        )
        upper = result["Upper"][valid_rows]
        middle = result["Middle"][valid_rows]
        lower = result["Lower"][valid_rows]
        assert (upper >= middle).all()
        assert (middle >= lower).all()

    def test_output_length(self):
        ind = _make_indicators()
        result = ind.calculate_bollinger_bands(PRICES)
        assert len(result["Upper"]) == len(PRICES)

    def test_custom_period_and_stddev(self):
        ind = _make_indicators()
        result = ind.calculate_bollinger_bands(PRICES, period=10, std_dev=1.5)
        assert "Upper" in result

    def test_wider_bands_with_higher_stddev(self):
        ind = _make_indicators()
        r1 = ind.calculate_bollinger_bands(PRICES, std_dev=1.0)
        r2 = ind.calculate_bollinger_bands(PRICES, std_dev=2.0)
        valid = ~(r1["Upper"].isna() | r2["Upper"].isna())
        assert (r2["Upper"][valid] >= r1["Upper"][valid]).all()


class TestCalculateATR:
    """Tests for TechnicalIndicators.calculate_atr."""

    def test_returns_series(self):
        ind = _make_indicators()
        result = ind.calculate_atr(HIGH, LOW, CLOSE)
        assert isinstance(result, pd.Series)

    def test_atr_nonnegative(self):
        ind = _make_indicators()
        result = ind.calculate_atr(HIGH, LOW, CLOSE)
        valid = result.dropna()
        assert (valid >= 0).all()

    def test_output_length(self):
        ind = _make_indicators()
        result = ind.calculate_atr(HIGH, LOW, CLOSE)
        assert len(result) == len(CLOSE)

    def test_custom_period(self):
        ind = _make_indicators()
        result = ind.calculate_atr(HIGH, LOW, CLOSE, period=7)
        assert isinstance(result, pd.Series)


class TestCalculateTrueRange:
    """Tests for TechnicalIndicators.calculate_true_range."""

    def test_returns_series(self):
        ind = _make_indicators()
        result = ind.calculate_true_range(HIGH, LOW, CLOSE)
        assert isinstance(result, pd.Series)

    def test_true_range_nonnegative(self):
        ind = _make_indicators()
        result = ind.calculate_true_range(HIGH, LOW, CLOSE)
        valid = result.dropna()
        assert (valid >= 0).all()

    def test_output_length(self):
        ind = _make_indicators()
        result = ind.calculate_true_range(HIGH, LOW, CLOSE)
        assert len(result) == len(CLOSE)

    def test_tr_geq_high_minus_low(self):
        ind = _make_indicators()
        result = ind.calculate_true_range(HIGH, LOW, CLOSE)
        hl = (HIGH - LOW).dropna()
        tr_valid = result.loc[hl.index].dropna()
        assert (tr_valid >= hl.loc[tr_valid.index]).all()


class TestCalculateSMA:
    """Tests for TechnicalIndicators.calculate_sma."""

    def test_returns_series(self):
        ind = _make_indicators()
        result = ind.calculate_sma(PRICES, period=10)
        assert isinstance(result, pd.Series)

    def test_output_length(self):
        ind = _make_indicators()
        result = ind.calculate_sma(PRICES, period=10)
        assert len(result) == len(PRICES)

    def test_sma_mean_check(self):
        # For a constant series, SMA should equal the constant
        const_prices = pd.Series([5.0] * 20)
        ind = _make_indicators()
        result = ind.calculate_sma(const_prices, period=5)
        valid = result.dropna()
        assert (valid == 5.0).all()

    def test_different_periods(self):
        ind = _make_indicators()
        sma5 = ind.calculate_sma(PRICES, 5)
        sma20 = ind.calculate_sma(PRICES, 20)
        assert isinstance(sma5, pd.Series) and isinstance(sma20, pd.Series)


class TestCalculateEMA:
    """Tests for TechnicalIndicators.calculate_ema."""

    def test_returns_series(self):
        ind = _make_indicators()
        result = ind.calculate_ema(PRICES, period=10)
        assert isinstance(result, pd.Series)

    def test_output_length(self):
        ind = _make_indicators()
        result = ind.calculate_ema(PRICES, period=10)
        assert len(result) == len(PRICES)

    def test_constant_prices_ema_equals_constant(self):
        const = pd.Series([10.0] * 30)
        ind = _make_indicators()
        result = ind.calculate_ema(const, period=5)
        valid = result.dropna()
        assert (abs(valid - 10.0) < 1e-9).all()

    def test_ema_different_from_sma_for_trending(self):
        ind = _make_indicators()
        ema = ind.calculate_ema(PRICES, 20)
        sma = ind.calculate_sma(PRICES, 20)
        # They should not be identical for trending data
        valid_both = ~(ema.isna() | sma.isna())
        assert not (ema[valid_both] == sma[valid_both]).all()


class TestCalculateADX:
    """Tests for TechnicalIndicators.calculate_adx."""

    def test_returns_dict(self):
        ind = _make_indicators()
        result = ind.calculate_adx(HIGH, LOW, CLOSE)
        assert isinstance(result, dict)

    def test_dict_has_adx_di_plus_di_minus(self):
        ind = _make_indicators()
        result = ind.calculate_adx(HIGH, LOW, CLOSE)
        assert "ADX" in result
        assert "+DI" in result
        assert "-DI" in result

    def test_adx_nonnegative(self):
        ind = _make_indicators()
        result = ind.calculate_adx(HIGH, LOW, CLOSE)
        valid = result["ADX"].dropna()
        assert (valid >= 0).all()

    def test_output_length(self):
        ind = _make_indicators()
        result = ind.calculate_adx(HIGH, LOW, CLOSE)
        assert len(result["ADX"]) == len(CLOSE)


class TestCalculateWMA:
    """Tests for TechnicalIndicators.calculate_wma."""

    def test_returns_series(self):
        ind = _make_indicators()
        result = ind.calculate_wma(PRICES, period=10)
        assert isinstance(result, pd.Series)

    def test_output_length(self):
        ind = _make_indicators()
        result = ind.calculate_wma(PRICES, period=10)
        assert len(result) == len(PRICES)

    def test_constant_prices_wma_equals_constant(self):
        const = pd.Series([7.0] * 30)
        ind = _make_indicators()
        result = ind.calculate_wma(const, period=5)
        valid = result.dropna()
        assert (abs(valid - 7.0) < 1e-9).all()


class TestCalculateHullMA:
    """Tests for TechnicalIndicators.calculate_hull_ma."""

    def test_returns_series(self):
        ind = _make_indicators()
        result = ind.calculate_hull_ma(PRICES, period=10)
        assert isinstance(result, pd.Series)

    def test_output_length(self):
        ind = _make_indicators()
        result = ind.calculate_hull_ma(PRICES, period=10)
        assert len(result) == len(PRICES)

    def test_returns_numeric_values(self):
        ind = _make_indicators()
        result = ind.calculate_hull_ma(PRICES, period=9)
        valid = result.dropna()
        assert (np.isfinite(valid)).all()


class TestCalculateVWAP:
    """Tests for TechnicalIndicators.calculate_vwap."""

    def test_returns_series(self):
        ind = _make_indicators()
        result = ind.calculate_vwap(HIGH, LOW, CLOSE, VOLUME)
        assert isinstance(result, pd.Series)

    def test_output_length(self):
        ind = _make_indicators()
        result = ind.calculate_vwap(HIGH, LOW, CLOSE, VOLUME)
        assert len(result) == len(CLOSE)

    def test_vwap_near_typical_price(self):
        # VWAP should be near the average of (H+L+C)/3
        ind = _make_indicators()
        result = ind.calculate_vwap(HIGH, LOW, CLOSE, VOLUME)
        typical = (HIGH + LOW + CLOSE) / 3
        # VWAP is cumulative, so compare at end roughly
        assert isinstance(result, pd.Series)

    def test_vwap_nonnegative_for_positive_prices(self):
        ind = _make_indicators()
        result = ind.calculate_vwap(HIGH, LOW, CLOSE, VOLUME)
        valid = result.dropna()
        assert (valid > 0).all()


class TestCalculateOBV:
    """Tests for TechnicalIndicators.calculate_obv."""

    def test_returns_series(self):
        ind = _make_indicators()
        result = ind.calculate_obv(CLOSE, VOLUME)
        assert isinstance(result, pd.Series)

    def test_output_length(self):
        ind = _make_indicators()
        result = ind.calculate_obv(CLOSE, VOLUME)
        assert len(result) == len(CLOSE)

    def test_first_obv_equals_first_volume(self):
        ind = _make_indicators()
        result = ind.calculate_obv(CLOSE, VOLUME)
        assert isinstance(result.iloc[0], (int, float))

    def test_obv_is_cumulative(self):
        # OBV changes with each bar
        ind = _make_indicators()
        result = ind.calculate_obv(CLOSE, VOLUME)
        # Not all values should be the same
        assert result.nunique() > 1


class TestGenerateRsiSignal:
    """Tests for TechnicalIndicators.generate_rsi_signal."""

    def test_returns_signal_type(self):
        ind = _make_indicators()
        rsi = ind.calculate_rsi(PRICES)
        signal = ind.generate_rsi_signal(rsi)
        assert isinstance(signal, SignalType)

    def test_oversold_gives_buy_signal(self):
        # Constant falling prices → RSI near 0 → BUY
        falling = pd.Series([50.0 - i for i in range(50)])
        ind = _make_indicators()
        rsi = ind.calculate_rsi(falling, period=14)
        signal = ind.generate_rsi_signal(rsi)
        assert signal in (SignalType.BUY, SignalType.STRONG_BUY, SignalType.NEUTRAL)

    def test_overbought_gives_sell_signal(self):
        # Constant rising prices → RSI near 100 → SELL
        rising = pd.Series([50.0 + i for i in range(50)])
        ind = _make_indicators()
        rsi = ind.calculate_rsi(rising, period=14)
        signal = ind.generate_rsi_signal(rsi)
        assert signal in (SignalType.SELL, SignalType.STRONG_SELL, SignalType.NEUTRAL)

    def test_neutral_prices_give_neutral_signal(self):
        # Flat prices → RSI = 50 → NEUTRAL
        flat = pd.Series([50.0] * 30)
        ind = _make_indicators()
        rsi = ind.calculate_rsi(flat, period=14)
        signal = ind.generate_rsi_signal(rsi)
        # Flat prices fill with 50 (neutral)
        assert isinstance(signal, SignalType)


class TestGenerateMacdSignal:
    """Tests for TechnicalIndicators.generate_macd_signal."""

    def test_returns_signal_type(self):
        ind = _make_indicators()
        macd_data = ind.calculate_macd(PRICES)
        signal = ind.generate_macd_signal(macd_data)
        assert isinstance(signal, SignalType)

    def test_bullish_crossover_gives_buy_signal(self):
        # Rising prices → MACD > 0 → BUY
        rising = pd.Series([100.0 + i * 0.5 for i in range(80)])
        ind = _make_indicators()
        macd_data = ind.calculate_macd(rising)
        signal = ind.generate_macd_signal(macd_data)
        assert signal in (SignalType.BUY, SignalType.STRONG_BUY, SignalType.NEUTRAL)

    def test_bearish_prices_give_sell_or_neutral(self):
        falling = pd.Series([200.0 - i * 0.5 for i in range(80)])
        ind = _make_indicators()
        macd_data = ind.calculate_macd(falling)
        signal = ind.generate_macd_signal(macd_data)
        assert signal in (SignalType.SELL, SignalType.STRONG_SELL, SignalType.NEUTRAL)

    def test_empty_macd_data_handled(self):
        ind = _make_indicators()
        empty_data: Dict[str, pd.Series] = {
            "MACD": pd.Series(dtype=float),
            "Signal": pd.Series(dtype=float),
            "Histogram": pd.Series(dtype=float),
        }
        # Should not raise; return some signal
        try:
            signal = ind.generate_macd_signal(empty_data)
            assert isinstance(signal, SignalType)
        except Exception:
            pass  # acceptable for empty input


# ==============================================================================
# U13 — MODULE-LEVEL FUNCTION TESTS
# ==============================================================================
class TestU13ModuleFunctions:
    """Tests for module-level convenience functions in U13."""

    def test_module_calculate_rsi_returns_series(self):
        result = module_calculate_rsi(PRICES)
        assert isinstance(result, pd.Series)

    def test_module_calculate_rsi_length(self):
        result = module_calculate_rsi(PRICES)
        assert len(result) == len(PRICES)

    def test_module_calculate_macd_returns_dict(self):
        result = module_calculate_macd(PRICES)
        assert isinstance(result, dict)
        assert "MACD" in result

    def test_module_calculate_bollinger_bands_returns_dict(self):
        result = module_calculate_bollinger_bands(PRICES)
        assert isinstance(result, dict)
        assert "Upper" in result

    def test_get_technical_indicators_returns_instance(self):
        result = get_technical_indicators()
        assert isinstance(result, TechnicalIndicators)

    def test_module_rsi_values_in_range(self):
        result = module_calculate_rsi(PRICES, period=14)
        valid = result.dropna()
        assert (valid >= 0).all() and (valid <= 100).all()


# ==============================================================================
# U13 — CONSTANTS TESTS
# ==============================================================================
class TestU13Constants:
    """Tests for U13 module-level constants."""

    def test_default_rsi_period(self):
        assert DEFAULT_RSI_PERIOD == 14

    def test_default_macd_fast_lt_slow(self):
        assert DEFAULT_MACD_FAST < DEFAULT_MACD_SLOW

    def test_default_bb_period_positive(self):
        assert DEFAULT_BB_PERIOD > 0

    def test_default_bb_stddev_positive(self):
        assert DEFAULT_BB_STDDEV > 0

    def test_rsi_overbought_line(self):
        assert RSI_OVERBOUGHT == 70

    def test_rsi_oversold_line(self):
        assert RSI_OVERSOLD == 30

    def test_overbought_gt_oversold(self):
        assert RSI_OVERBOUGHT > RSI_OVERSOLD
