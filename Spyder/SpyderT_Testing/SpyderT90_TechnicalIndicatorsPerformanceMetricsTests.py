#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT90_TechnicalIndicatorsPerformanceMetricsTests.py
Purpose: Tests for U13 TechnicalIndicators and U15 PerformanceMetrics

Year Created: 2025
Last Updated: 2026-01-01 Time: 00:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import math
import os
import sys
import types
from typing import Dict
from unittest.mock import MagicMock, patch

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
import pytest

# ==============================================================================
# BOOTSTRAP — add project root to sys.path and stub framework packages
# ==============================================================================
_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _ensure_pkg(name: str) -> None:
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)


_ensure_pkg("Spyder")
_ensure_pkg("SpyderU_Utilities")
_ensure_pkg("Spyder.SpyderU_Utilities")

# Stub SpyderLogger
_logger_mod = types.ModuleType("Spyder.SpyderU_Utilities.SpyderU01_Logger")


class _FakeSpyderLogger:
    @staticmethod
    def get_logger(name: str) -> MagicMock:
        return MagicMock()


_logger_mod.SpyderLogger = _FakeSpyderLogger
sys.modules["Spyder.SpyderU_Utilities.SpyderU01_Logger"] = _logger_mod

# Stub SpyderErrorHandler
_err_mod = types.ModuleType("Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler")
_err_mod.SpyderErrorHandler = MagicMock
sys.modules["Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler"] = _err_mod

# ==============================================================================
# IMPORT MODULES UNDER TEST
# ==============================================================================
import Spyder.SpyderU_Utilities.SpyderU13_TechnicalIndicators as _u13
import Spyder.SpyderU_Utilities.SpyderU15_PerformanceMetrics as _u15

TechnicalIndicators = _u13.TechnicalIndicators
MAType = _u13.MAType
SignalType = _u13.SignalType
TrendDirection = _u13.TrendDirection
IndicatorResult = _u13.IndicatorResult
TrendAnalysis = _u13.TrendAnalysis

PerformanceCalculator = _u15.PerformanceCalculator
PerformanceRating = _u15.PerformanceRating
MetricType = _u15.MetricType
PerformanceReport = _u15.PerformanceReport
DrawdownInfo = _u15.DrawdownInfo


# ==============================================================================
# HELPERS
# ==============================================================================

def _make_prices(n: int = 50, seed: int = 42, start: float = 100.0) -> pd.Series:
    """Return a deterministic price series."""
    rng = np.random.default_rng(seed)
    changes = rng.normal(0, 0.5, n)
    return pd.Series(start + np.cumsum(changes))


def _make_ohlcv(n: int = 50, seed: int = 42):
    """Return (high, low, close, volume) Series."""
    close = _make_prices(n, seed)
    rng = np.random.default_rng(seed + 1)
    high = close + rng.uniform(0.1, 1.0, n)
    low = close - rng.uniform(0.1, 1.0, n)
    volume = pd.Series(rng.integers(1000, 10000, n), dtype=float)
    return high, low, close, volume


def _make_returns(n: int = 60, seed: int = 7, mean: float = 0.001, std: float = 0.01) -> pd.Series:
    """Return a deterministic daily-return series with n >= 30 periods."""
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(mean, std, n))


# ==============================================================================
# ──────────────────────────────────────────────────────────────────────────────
# U13 TechnicalIndicators
# ──────────────────────────────────────────────────────────────────────────────
# ==============================================================================


class TestU13Constants:
    def test_rsi_period(self):
        assert _u13.DEFAULT_RSI_PERIOD == 14

    def test_macd_fast(self):
        assert _u13.DEFAULT_MACD_FAST == 12

    def test_macd_slow(self):
        assert _u13.DEFAULT_MACD_SLOW == 26

    def test_macd_signal(self):
        assert _u13.DEFAULT_MACD_SIGNAL == 9

    def test_bb_period(self):
        assert _u13.DEFAULT_BB_PERIOD == 20

    def test_bb_stddev(self):
        assert _u13.DEFAULT_BB_STDDEV == 2.0

    def test_rsi_overbought(self):
        assert _u13.RSI_OVERBOUGHT == 70

    def test_rsi_oversold(self):
        assert _u13.RSI_OVERSOLD == 30

    def test_stoch_overbought(self):
        assert _u13.STOCH_OVERBOUGHT == 80

    def test_stoch_oversold(self):
        assert _u13.STOCH_OVERSOLD == 20

    def test_ma_types_list(self):
        assert "SMA" in _u13.MA_TYPES
        assert "EMA" in _u13.MA_TYPES
        assert len(_u13.MA_TYPES) == 5


class TestMAType:
    def test_sma(self):
        assert MAType.SMA.value == "SMA"

    def test_ema(self):
        assert MAType.EMA.value == "EMA"

    def test_wma(self):
        assert MAType.WMA.value == "WMA"

    def test_hull(self):
        assert MAType.HULL.value == "HULL"

    def test_vwma(self):
        assert MAType.VWMA.value == "VWMA"

    def test_enum_count(self):
        assert len(MAType) == 5


class TestSignalType:
    def test_buy(self):
        assert SignalType.BUY.value == "buy"

    def test_sell(self):
        assert SignalType.SELL.value == "sell"

    def test_neutral(self):
        assert SignalType.NEUTRAL.value == "neutral"

    def test_strong_buy(self):
        assert SignalType.STRONG_BUY.value == "strong_buy"

    def test_strong_sell(self):
        assert SignalType.STRONG_SELL.value == "strong_sell"


class TestTrendDirection:
    def test_up(self):
        assert TrendDirection.UP.value == "up"

    def test_down(self):
        assert TrendDirection.DOWN.value == "down"

    def test_sideways(self):
        assert TrendDirection.SIDEWAYS.value == "sideways"

    def test_unknown(self):
        assert TrendDirection.UNKNOWN.value == "unknown"


class TestIndicatorResult:
    def _make(self) -> IndicatorResult:
        return IndicatorResult(
            name="RSI",
            value=55.0,
            signal=SignalType.NEUTRAL,
            timestamp=pd.Timestamp("2024-01-01"),
            parameters={"period": 14},
        )

    def test_creation(self):
        ir = self._make()
        assert ir.name == "RSI"
        assert ir.value == 55.0
        assert ir.signal == SignalType.NEUTRAL

    def test_to_dict_keys(self):
        d = self._make().to_dict()
        assert "name" in d and "value" in d and "signal" in d

    def test_to_dict_signal_value(self):
        d = self._make().to_dict()
        assert d["signal"] == "neutral"

    def test_to_dict_timestamp_is_string(self):
        d = self._make().to_dict()
        assert isinstance(d["timestamp"], str)

    def test_dict_value_with_nested(self):
        ir = IndicatorResult(
            name="MACD",
            value={"MACD": 0.1, "Signal": 0.05},
            signal=SignalType.BUY,
            timestamp=pd.Timestamp("2024-01-02"),
            parameters={"fast": 12},
        )
        assert isinstance(ir.to_dict()["value"], dict)


class TestTrendAnalysis:
    def test_creation(self):
        ta = TrendAnalysis(
            direction=TrendDirection.UP,
            strength=0.75,
            duration=10,
            support_level=98.0,
            resistance_level=105.0,
        )
        assert ta.direction == TrendDirection.UP
        assert ta.strength == 0.75
        assert ta.duration == 10


class TestCalculateRSI:
    def setup_method(self):
        self.ind = TechnicalIndicators()

    def test_returns_series(self):
        prices = _make_prices(30)
        result = self.ind.calculate_rsi(prices, period=14)
        assert isinstance(result, pd.Series)

    def test_insufficient_data_returns_all_nan(self):
        # Returns pd.Series(dtype=float, index=prices.index) — same length, all NaN
        prices = pd.Series([100.0, 101.0])
        result = self.ind.calculate_rsi(prices, period=14)
        assert result.isna().all()

    def test_values_in_range(self):
        prices = _make_prices(60)
        rsi = self.ind.calculate_rsi(prices, period=14)
        valid = rsi.dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_length_preserved(self):
        prices = _make_prices(50)
        rsi = self.ind.calculate_rsi(prices, period=14)
        assert len(rsi) == 50

    def test_fills_nan_with_50(self):
        prices = _make_prices(50)
        rsi = self.ind.calculate_rsi(prices, period=14)
        assert not rsi.isna().any()

    def test_module_level_function(self):
        prices = _make_prices(50)
        result = _u13.calculate_rsi(prices, period=14)
        assert isinstance(result, pd.Series)


class TestCalculateStochastic:
    def setup_method(self):
        self.ind = TechnicalIndicators()

    def test_returns_dict_with_keys(self):
        h, lo, c, _ = _make_ohlcv(40)
        result = self.ind.calculate_stochastic(h, lo, c)
        assert "%K" in result and "%D" in result

    def test_k_in_range(self):
        h, lo, c, _ = _make_ohlcv(40)
        k = self.ind.calculate_stochastic(h, lo, c)["%K"]
        valid = k.dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_d_length_matches_close(self):
        h, lo, c, _ = _make_ohlcv(40)
        d = self.ind.calculate_stochastic(h, lo, c)["%D"]
        assert len(d) == len(c)

    def test_custom_periods(self):
        h, lo, c, _ = _make_ohlcv(40)
        result = self.ind.calculate_stochastic(h, lo, c, k_period=5, d_period=3)
        assert isinstance(result["%K"], pd.Series)


class TestCalculateWilliamsR:
    def setup_method(self):
        self.ind = TechnicalIndicators()

    def test_returns_series(self):
        h, lo, c, _ = _make_ohlcv(30)
        result = self.ind.calculate_williams_r(h, lo, c)
        assert isinstance(result, pd.Series)

    def test_values_in_range(self):
        h, lo, c, _ = _make_ohlcv(50)
        wr = self.ind.calculate_williams_r(h, lo, c, period=14)
        valid = wr.dropna()
        assert (valid >= -100).all() and (valid <= 0).all()

    def test_length_preserved(self):
        h, lo, c, _ = _make_ohlcv(50)
        wr = self.ind.calculate_williams_r(h, lo, c)
        assert len(wr) == len(c)


class TestCalculateMACD:
    def setup_method(self):
        self.ind = TechnicalIndicators()

    def test_returns_dict_with_three_keys(self):
        prices = _make_prices(60)
        result = self.ind.calculate_macd(prices)
        assert "MACD" in result and "Signal" in result and "Histogram" in result

    def test_histogram_equals_macd_minus_signal(self):
        prices = _make_prices(60)
        result = self.ind.calculate_macd(prices)
        expected = result["MACD"] - result["Signal"]
        pd.testing.assert_series_equal(result["Histogram"], expected, check_names=False)

    def test_custom_periods(self):
        prices = _make_prices(60)
        result = self.ind.calculate_macd(prices, fast=5, slow=13, signal=6)
        assert "MACD" in result

    def test_module_level_function(self):
        prices = _make_prices(60)
        result = _u13.calculate_macd(prices)
        assert "MACD" in result


class TestCalculateADX:
    def setup_method(self):
        self.ind = TechnicalIndicators()

    def test_returns_dict(self):
        h, lo, c, _ = _make_ohlcv(50)
        result = self.ind.calculate_adx(h, lo, c)
        assert "ADX" in result and "+DI" in result and "-DI" in result

    def test_adx_series_length(self):
        h, lo, c, _ = _make_ohlcv(50)
        adx = self.ind.calculate_adx(h, lo, c)["ADX"]
        assert len(adx) == len(c)


class TestCalculateBollingerBands:
    def setup_method(self):
        self.ind = TechnicalIndicators()

    def test_returns_dict(self):
        prices = _make_prices(50)
        result = self.ind.calculate_bollinger_bands(prices)
        assert "Upper" in result and "Middle" in result and "Lower" in result

    def test_upper_above_middle_above_lower(self):
        prices = _make_prices(50)
        result = self.ind.calculate_bollinger_bands(prices)
        # compare where all bands have valid values
        idx = result["Upper"].dropna().index
        assert (result["Upper"][idx] >= result["Middle"][idx]).all()
        assert (result["Middle"][idx] >= result["Lower"][idx]).all()

    def test_custom_params(self):
        prices = _make_prices(50)
        result = self.ind.calculate_bollinger_bands(prices, period=10, std_dev=1.5)
        assert isinstance(result["Middle"], pd.Series)

    def test_module_level_function(self):
        prices = _make_prices(50)
        result = _u13.calculate_bollinger_bands(prices)
        assert "Upper" in result


class TestCalculateATR:
    def setup_method(self):
        self.ind = TechnicalIndicators()

    def test_returns_series(self):
        h, lo, c, _ = _make_ohlcv(30)
        result = self.ind.calculate_atr(h, lo, c)
        assert isinstance(result, pd.Series)

    def test_atr_non_negative(self):
        h, lo, c, _ = _make_ohlcv(30)
        atr = self.ind.calculate_atr(h, lo, c)
        assert (atr.dropna() >= 0).all()


class TestCalculateTrueRange:
    def setup_method(self):
        self.ind = TechnicalIndicators()

    def test_returns_series(self):
        h, lo, c, _ = _make_ohlcv(20)
        result = self.ind.calculate_true_range(h, lo, c)
        assert isinstance(result, pd.Series)

    def test_non_negative(self):
        h, lo, c, _ = _make_ohlcv(20)
        tr = self.ind.calculate_true_range(h, lo, c)
        assert (tr.dropna() >= 0).all()

    def test_length_preserved(self):
        h, lo, c, _ = _make_ohlcv(20)
        tr = self.ind.calculate_true_range(h, lo, c)
        assert len(tr) == len(c)

    def test_first_value_is_high_minus_low(self):
        # At index 0, prev_close is NaN → tr2 and tr3 are NaN → falls back to h-lo
        h = pd.Series([102.0, 103.0])
        lo = pd.Series([98.0, 99.0])
        c = pd.Series([100.0, 101.0])
        tr = self.ind.calculate_true_range(h, lo, c)
        assert tr.iloc[0] == pytest.approx(4.0)


class TestCalculateSMA:
    def setup_method(self):
        self.ind = TechnicalIndicators()

    def test_exact_value(self):
        prices = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        sma = self.ind.calculate_sma(prices, period=3)
        assert sma.iloc[2] == pytest.approx(2.0)
        assert sma.iloc[4] == pytest.approx(4.0)

    def test_nan_before_period(self):
        prices = pd.Series([1.0, 2.0, 3.0, 4.0])
        sma = self.ind.calculate_sma(prices, period=3)
        assert pd.isna(sma.iloc[0])

    def test_length_preserved(self):
        prices = _make_prices(40)
        assert len(self.ind.calculate_sma(prices, 10)) == 40


class TestCalculateEMA:
    def setup_method(self):
        self.ind = TechnicalIndicators()

    def test_returns_series(self):
        prices = _make_prices(30)
        result = self.ind.calculate_ema(prices, period=10)
        assert isinstance(result, pd.Series)

    def test_no_nan(self):
        prices = _make_prices(30)
        ema = self.ind.calculate_ema(prices, period=5)
        assert not ema.isna().any()

    def test_length_preserved(self):
        prices = _make_prices(30)
        assert len(self.ind.calculate_ema(prices, 10)) == 30

    def test_single_period_equals_price(self):
        prices = pd.Series([10.0, 20.0, 30.0])
        ema = self.ind.calculate_ema(prices, period=1)
        pd.testing.assert_series_equal(ema, prices.astype(float), check_names=False)


class TestCalculateWMA:
    def setup_method(self):
        self.ind = TechnicalIndicators()

    def test_returns_series(self):
        prices = _make_prices(30)
        result = self.ind.calculate_wma(prices, period=5)
        assert isinstance(result, pd.Series)

    def test_nan_before_period(self):
        prices = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        wma = self.ind.calculate_wma(prices, period=3)
        assert pd.isna(wma.iloc[0])

    def test_known_value(self):
        # weights [1,2,3] sum=6; wma = (1*1 + 2*2 + 3*3)/6 = 14/6 ≈ 2.333
        prices = pd.Series([1.0, 2.0, 3.0])
        wma = self.ind.calculate_wma(prices, period=3)
        assert wma.iloc[2] == pytest.approx(14 / 6, abs=1e-6)


class TestCalculateHullMA:
    def setup_method(self):
        self.ind = TechnicalIndicators()

    def test_returns_series(self):
        prices = _make_prices(50)
        result = self.ind.calculate_hull_ma(prices, period=9)
        assert isinstance(result, pd.Series)

    def test_length_preserved(self):
        prices = _make_prices(50)
        hull = self.ind.calculate_hull_ma(prices, period=9)
        assert len(hull) == 50


class TestCalculateVWAP:
    def setup_method(self):
        self.ind = TechnicalIndicators()

    def test_returns_series(self):
        h, lo, c, vol = _make_ohlcv(30)
        result = self.ind.calculate_vwap(h, lo, c, vol)
        assert isinstance(result, pd.Series)

    def test_length_preserved(self):
        h, lo, c, vol = _make_ohlcv(30)
        vwap = self.ind.calculate_vwap(h, lo, c, vol)
        assert len(vwap) == 30

    def test_cumulative_nature(self):
        # VWAP should be within the high-low range approximately
        h, lo, c, vol = _make_ohlcv(30)
        vwap = self.ind.calculate_vwap(h, lo, c, vol)
        assert (vwap >= lo.min()).all() and (vwap <= h.max()).all()


class TestCalculateOBV:
    def setup_method(self):
        self.ind = TechnicalIndicators()

    def test_returns_series(self):
        h, lo, c, vol = _make_ohlcv(20)
        result = self.ind.calculate_obv(c, vol)
        assert isinstance(result, pd.Series)

    def test_rising_close_adds_volume(self):
        close = pd.Series([10.0, 11.0, 12.0])
        volume = pd.Series([100.0, 200.0, 300.0])
        obv = self.ind.calculate_obv(close, volume)
        # first change: +200, second: +300 → cumsum [100, 300, 600]
        assert obv.iloc[2] > obv.iloc[1] > obv.iloc[0]

    def test_falling_close_subtracts_volume(self):
        close = pd.Series([12.0, 11.0, 10.0])
        volume = pd.Series([100.0, 200.0, 300.0])
        obv = self.ind.calculate_obv(close, volume)
        assert obv.iloc[2] < obv.iloc[1] < obv.iloc[0]


class TestGenerateRSISignal:
    def setup_method(self):
        self.ind = TechnicalIndicators()

    def test_strong_sell_at_85(self):
        rsi = pd.Series([50.0, 85.0])
        assert self.ind.generate_rsi_signal(rsi) == SignalType.STRONG_SELL

    def test_sell_at_75(self):
        rsi = pd.Series([50.0, 75.0])
        assert self.ind.generate_rsi_signal(rsi) == SignalType.SELL

    def test_strong_buy_at_15(self):
        rsi = pd.Series([50.0, 15.0])
        assert self.ind.generate_rsi_signal(rsi) == SignalType.STRONG_BUY

    def test_buy_at_25(self):
        rsi = pd.Series([50.0, 25.0])
        assert self.ind.generate_rsi_signal(rsi) == SignalType.BUY

    def test_neutral_at_50(self):
        rsi = pd.Series([50.0, 50.0])
        assert self.ind.generate_rsi_signal(rsi) == SignalType.NEUTRAL

    def test_boundary_70_is_sell(self):
        rsi = pd.Series([50.0, 70.0])
        assert self.ind.generate_rsi_signal(rsi) == SignalType.SELL

    def test_boundary_80_is_strong_sell(self):
        rsi = pd.Series([50.0, 80.0])
        assert self.ind.generate_rsi_signal(rsi) == SignalType.STRONG_SELL

    def test_boundary_30_is_buy(self):
        rsi = pd.Series([50.0, 30.0])
        assert self.ind.generate_rsi_signal(rsi) == SignalType.BUY

    def test_boundary_20_is_strong_buy(self):
        rsi = pd.Series([50.0, 20.0])
        assert self.ind.generate_rsi_signal(rsi) == SignalType.STRONG_BUY

    def test_empty_series_returns_neutral(self):
        rsi = pd.Series([], dtype=float)
        assert self.ind.generate_rsi_signal(rsi) == SignalType.NEUTRAL


class TestGenerateMACDSignal:
    def setup_method(self):
        self.ind = TechnicalIndicators()

    def _make_data(self, macd_val, signal_val, prev_hist, curr_hist):
        macd_line = pd.Series([0.0, macd_val])
        signal_line = pd.Series([0.0, signal_val])
        histogram = pd.Series([prev_hist, curr_hist])
        return {"MACD": macd_line, "Signal": signal_line, "Histogram": histogram}

    def test_bullish_crossover_returns_buy(self):
        data = self._make_data(0.5, 0.3, -0.1, 0.2)
        assert self.ind.generate_macd_signal(data) == SignalType.BUY

    def test_bearish_crossover_returns_sell(self):
        data = self._make_data(-0.5, -0.3, 0.1, -0.2)
        assert self.ind.generate_macd_signal(data) == SignalType.SELL

    def test_no_crossover_returns_neutral(self):
        data = self._make_data(0.1, 0.2, 0.1, 0.05)
        assert self.ind.generate_macd_signal(data) == SignalType.NEUTRAL

    def test_single_bar_returns_neutral(self):
        data = {
            "MACD": pd.Series([0.1]),
            "Signal": pd.Series([0.05]),
            "Histogram": pd.Series([0.05]),
        }
        assert self.ind.generate_macd_signal(data) == SignalType.NEUTRAL


class TestU13ModuleFunctions:
    def test_get_technical_indicators_returns_instance(self):
        inst = _u13.get_technical_indicators()
        assert isinstance(inst, TechnicalIndicators)

    def test_get_technical_indicators_is_singleton(self):
        a = _u13.get_technical_indicators()
        b = _u13.get_technical_indicators()
        assert a is b

    def test_singleton_module_var_matches(self):
        inst = _u13.get_technical_indicators()
        assert _u13._technical_indicators_instance is inst


# ==============================================================================
# ──────────────────────────────────────────────────────────────────────────────
# U15 PerformanceMetrics
# ──────────────────────────────────────────────────────────────────────────────
# ==============================================================================


class TestU15Constants:
    def test_trading_days(self):
        assert _u15.TRADING_DAYS_PER_YEAR == 252

    def test_risk_free_rate(self):
        assert pytest.approx(0.045) == _u15.RISK_FREE_RATE

    def test_min_periods(self):
        assert _u15.MIN_PERIODS_FOR_CALCULATION == 30

    def test_excellent_sharpe(self):
        assert _u15.EXCELLENT_SHARPE == 2.0

    def test_good_sharpe(self):
        assert _u15.GOOD_SHARPE == 1.0

    def test_poor_sharpe(self):
        assert _u15.POOR_SHARPE == 0.5


class TestPerformanceRating:
    def test_excellent(self):
        assert PerformanceRating.EXCELLENT.value == "excellent"

    def test_good(self):
        assert PerformanceRating.GOOD.value == "good"

    def test_average(self):
        assert PerformanceRating.AVERAGE.value == "average"

    def test_poor(self):
        assert PerformanceRating.POOR.value == "poor"

    def test_very_poor(self):
        assert PerformanceRating.VERY_POOR.value == "very_poor"

    def test_count(self):
        assert len(PerformanceRating) == 5


class TestMetricType:
    def test_return(self):
        assert MetricType.RETURN.value == "return"

    def test_risk(self):
        assert MetricType.RISK.value == "risk"

    def test_ratio(self):
        assert MetricType.RATIO.value == "ratio"

    def test_drawdown(self):
        assert MetricType.DRAWDOWN.value == "drawdown"

    def test_volatility(self):
        assert MetricType.VOLATILITY.value == "volatility"


class TestDrawdownInfo:
    def test_creation(self):
        di = DrawdownInfo(
            max_drawdown=-0.15,
            max_drawdown_duration=10,
            recovery_time=5,
            drawdown_periods=[(2, 11, -0.15)],
        )
        assert di.max_drawdown == -0.15
        assert di.max_drawdown_duration == 10
        assert di.recovery_time == 5
        assert len(di.drawdown_periods) == 1


class TestPerformanceReportDataclass:
    def _make_report(self) -> PerformanceReport:
        return PerformanceReport(
            total_return=0.1,
            annualized_return=0.1,
            volatility=0.15,
            sharpe_ratio=1.2,
            sortino_ratio=1.5,
            calmar_ratio=0.8,
            max_drawdown=-0.05,
            max_drawdown_duration=20,
            win_rate=55.0,
            profit_factor=1.5,
            avg_win=0.02,
            avg_loss=-0.01,
            largest_win=0.08,
            largest_loss=-0.04,
            total_trades=50,
            winning_trades=27,
            losing_trades=23,
            rating=PerformanceRating.GOOD,
        )

    def test_creation(self):
        r = self._make_report()
        assert r.total_return == 0.1
        assert r.rating == PerformanceRating.GOOD

    def test_to_dict_keys(self):
        d = self._make_report().to_dict()
        required = [
            "total_return", "annualized_return", "volatility", "sharpe_ratio",
            "sortino_ratio", "calmar_ratio", "max_drawdown", "win_rate",
            "profit_factor", "total_trades", "rating",
        ]
        for k in required:
            assert k in d

    def test_to_dict_rating_value(self):
        d = self._make_report().to_dict()
        assert d["rating"] == "good"


class TestCalculateTotalReturn:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_empty_returns_zero(self):
        assert self.calc.calculate_total_return(pd.Series([], dtype=float)) == 0.0

    def test_single_positive_return(self):
        result = self.calc.calculate_total_return(pd.Series([0.05]))
        assert result == pytest.approx(0.05, abs=1e-6)

    def test_two_periods(self):
        # (1+0.1)*(1+0.1) - 1 = 1.21 - 1 = 0.21
        result = self.calc.calculate_total_return(pd.Series([0.10, 0.10]))
        assert result == pytest.approx(0.21, abs=1e-6)

    def test_negative_returns(self):
        result = self.calc.calculate_total_return(pd.Series([-0.10]))
        assert result == pytest.approx(-0.10, abs=1e-6)

    def test_round_trip_zero(self):
        # +10% then -10% ≈ -1%
        result = self.calc.calculate_total_return(pd.Series([0.10, -0.10]))
        assert result < 0.0  # (1.10 * 0.90) - 1 = -0.01


class TestCalculateAnnualizedReturn:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_empty_returns_zero(self):
        result = self.calc.calculate_annualized_return(pd.Series([], dtype=float))
        assert result == 0.0

    def test_one_year_matches_total(self):
        rets = _make_returns(252, mean=0.001)
        ann = self.calc.calculate_annualized_return(rets)
        total = self.calc.calculate_total_return(rets)
        # annualized over 1 year ≈ total
        assert ann == pytest.approx(total, rel=0.01)

    def test_positive_drift_gives_positive_annualized(self):
        rets = pd.Series([0.005] * 252)
        ann = self.calc.calculate_annualized_return(rets)
        assert ann > 0.0


class TestCalculateVolatility:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_single_value_returns_zero(self):
        result = self.calc.calculate_volatility(pd.Series([0.01]))
        assert result == 0.0

    def test_constant_returns_zero_vol(self):
        result = self.calc.calculate_volatility(pd.Series([0.01] * 30))
        assert result == pytest.approx(0.0, abs=1e-10)

    def test_positive_vol(self):
        rets = _make_returns(60)
        vol = self.calc.calculate_volatility(rets)
        assert vol > 0.0

    def test_annualization(self):
        daily_std = 0.01
        rets = pd.Series([daily_std] * 60)
        rets = rets - rets.mean()  # zero mean
        rng = np.random.default_rng(1)
        rets = pd.Series(rng.normal(0, daily_std, 60))
        vol = self.calc.calculate_volatility(rets, periods_per_year=252)
        # annualized ≈ daily_std * sqrt(252)
        expected = rets.std() * np.sqrt(252)
        assert vol == pytest.approx(expected, rel=0.01)


class TestCalculateSharpeRatio:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_insufficient_data_returns_zero(self):
        rets = pd.Series([0.01] * 10)  # < 30
        assert self.calc.calculate_sharpe_ratio(rets) == 0.0

    def test_zero_std_returns_zero(self):
        # constant returns after excess return calculation
        rfr = _u15.RISK_FREE_RATE / 252
        rets = pd.Series([rfr] * 30)
        assert self.calc.calculate_sharpe_ratio(rets) == 0.0

    def test_zero_excess_returns_zero_sharpe(self):
        # rets == rfr_daily exactly → excess returns all 0 → std=0 → return 0.0
        rfr_daily = _u15.RISK_FREE_RATE / 252
        rets = pd.Series([rfr_daily] * 60)
        assert self.calc.calculate_sharpe_ratio(rets) == 0.0

    def test_positive_excess_returns_float(self):
        # constant positive excess returns; just verify result type
        rets = pd.Series([0.005] * 60)
        sharpe = self.calc.calculate_sharpe_ratio(rets)
        assert isinstance(sharpe, float)

    def test_volatile_series_gives_nonzero_sharpe(self):
        rets = _make_returns(60, mean=0.002, std=0.01)
        sharpe = self.calc.calculate_sharpe_ratio(rets)
        assert isinstance(sharpe, float)

    def test_module_level_function(self):
        rets = _make_returns(60)
        result = _u15.calculate_sharpe_ratio(rets)
        assert isinstance(result, float)


class TestCalculateSortinoRatio:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_insufficient_data_returns_zero(self):
        rets = pd.Series([0.01] * 20)
        assert self.calc.calculate_sortino_ratio(rets) == 0.0

    def test_all_positive_excess_returns_inf(self):
        # When there are no negative excess returns → returns inf
        rfr_daily = _u15.RISK_FREE_RATE / 252
        rets = pd.Series([rfr_daily + 0.01] * 60)  # always above rf
        result = self.calc.calculate_sortino_ratio(rets)
        assert result == float("inf")

    def test_mixed_returns_finite(self):
        rets = _make_returns(60, mean=0.001, std=0.02)
        sortino = self.calc.calculate_sortino_ratio(rets)
        assert math.isfinite(sortino)


class TestCalculateCalmarRatio:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_insufficient_data_returns_zero(self):
        rets = pd.Series([0.01] * 20)
        assert self.calc.calculate_calmar_ratio(rets) == 0.0

    def test_all_positive_no_drawdown_returns_inf(self):
        rets = pd.Series([0.001] * 60)  # monotone → cumsum always rising → drawdown=0
        result = self.calc.calculate_calmar_ratio(rets)
        assert result == float("inf")

    def test_returns_float(self):
        rets = _make_returns(60, mean=0.001, std=0.02)
        result = self.calc.calculate_calmar_ratio(rets)
        assert isinstance(result, float)


class TestCalculateMaxDrawdown:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_empty_returns_zero(self):
        result = self.calc.calculate_max_drawdown(pd.Series([], dtype=float))
        assert result == 0.0

    def test_monotone_increasing_no_drawdown(self):
        cum = pd.Series([0.01, 0.02, 0.03, 0.04, 0.05])
        assert self.calc.calculate_max_drawdown(cum) == pytest.approx(0.0, abs=1e-10)

    def test_simple_drawdown(self):
        # peak=0.10, then drops to 0.07 → (0.07-0.10)/0.10 = -0.3
        cum = pd.Series([0.05, 0.10, 0.07, 0.12])
        dd = self.calc.calculate_max_drawdown(cum)
        assert dd == pytest.approx(-0.30, abs=1e-6)

    def test_drawdown_is_negative(self):
        cum = pd.Series([0.1, 0.2, 0.15, 0.25])
        assert self.calc.calculate_max_drawdown(cum) < 0.0

    def test_module_level_function(self):
        cum = pd.Series([0.05, 0.10, 0.08])
        result = _u15.calculate_max_drawdown(cum)
        assert isinstance(result, float)


class TestAnalyzeDrawdowns:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_empty_series(self):
        di = self.calc.analyze_drawdowns(pd.Series([], dtype=float))
        assert di.max_drawdown == 0.0
        assert di.drawdown_periods == []

    def test_monotone_increasing_no_periods(self):
        cum = pd.Series([0.01, 0.02, 0.03, 0.04])
        di = self.calc.analyze_drawdowns(cum)
        assert di.drawdown_periods == []
        assert di.max_drawdown == pytest.approx(0.0, abs=1e-10)

    def test_simple_drawdown_then_recovery(self):
        cum = pd.Series([0.05, 0.10, 0.07, 0.12])
        di = self.calc.analyze_drawdowns(cum)
        assert len(di.drawdown_periods) >= 1
        assert di.max_drawdown < 0.0

    def test_ends_in_drawdown(self):
        # Starts high then drops, never recovers
        cum = pd.Series([0.10, 0.20, 0.15, 0.12])
        di = self.calc.analyze_drawdowns(cum)
        assert di.max_drawdown < 0.0

    def test_returns_drawdown_info_type(self):
        cum = pd.Series([0.1, 0.2, 0.15])
        di = self.calc.analyze_drawdowns(cum)
        assert isinstance(di, DrawdownInfo)

    def test_max_drawdown_duration_positive(self):
        cum = pd.Series([0.05, 0.10, 0.07, 0.06, 0.12])
        di = self.calc.analyze_drawdowns(cum)
        assert di.max_drawdown_duration >= 1


class TestCalculateWinRate:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_empty_returns_zero(self):
        assert self.calc.calculate_win_rate(pd.Series([], dtype=float)) == 0.0

    def test_all_wins(self):
        rets = pd.Series([0.01, 0.02, 0.03])
        assert self.calc.calculate_win_rate(rets) == pytest.approx(100.0)

    def test_all_losses(self):
        rets = pd.Series([-0.01, -0.02, -0.03])
        assert self.calc.calculate_win_rate(rets) == pytest.approx(0.0)

    def test_half_and_half(self):
        rets = pd.Series([0.01, -0.01, 0.01, -0.01])
        assert self.calc.calculate_win_rate(rets) == pytest.approx(50.0)

    def test_mixed(self):
        rets = pd.Series([0.01, 0.02, -0.01])  # 2/3
        assert self.calc.calculate_win_rate(rets) == pytest.approx(200 / 3, rel=0.01)


class TestCalculateProfitFactor:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_empty_returns_zero(self):
        assert self.calc.calculate_profit_factor(pd.Series([], dtype=float)) == 0.0

    def test_no_losses_returns_inf(self):
        rets = pd.Series([0.01, 0.02, 0.03])
        assert self.calc.calculate_profit_factor(rets) == float("inf")

    def test_no_wins_returns_zero(self):
        rets = pd.Series([-0.01, -0.02, -0.03])
        assert self.calc.calculate_profit_factor(rets) == 0.0

    def test_equal_wins_losses(self):
        rets = pd.Series([0.05, -0.05, 0.05, -0.05])
        assert self.calc.calculate_profit_factor(rets) == pytest.approx(1.0, abs=1e-6)

    def test_pf_greater_than_one_when_profitable(self):
        rets = pd.Series([0.10, 0.05, -0.02, -0.03])
        pf = self.calc.calculate_profit_factor(rets)
        assert pf > 1.0


class TestCalculateTradeStatistics:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_empty_returns_zeros(self):
        result = self.calc.calculate_trade_statistics(pd.Series([], dtype=float))
        assert result["total_trades"] == 0

    def test_total_trades_count(self):
        rets = pd.Series([0.01, -0.02, 0.03, -0.01, 0.02])
        result = self.calc.calculate_trade_statistics(rets)
        assert result["total_trades"] == 5

    def test_winning_losing_split(self):
        rets = pd.Series([0.01, -0.02, 0.03])
        result = self.calc.calculate_trade_statistics(rets)
        assert result["winning_trades"] == 2
        assert result["losing_trades"] == 1

    def test_avg_win_positive(self):
        rets = pd.Series([0.01, 0.03, -0.01])
        result = self.calc.calculate_trade_statistics(rets)
        assert result["avg_win"] > 0.0

    def test_avg_loss_negative(self):
        rets = pd.Series([0.01, -0.02])
        result = self.calc.calculate_trade_statistics(rets)
        assert result["avg_loss"] < 0.0

    def test_largest_win_largest_loss(self):
        rets = pd.Series([0.01, 0.05, -0.02, -0.08])
        result = self.calc.calculate_trade_statistics(rets)
        assert result["largest_win"] == pytest.approx(0.05)
        assert result["largest_loss"] == pytest.approx(-0.08)


class TestRatePerformance:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_all_zeros_is_very_poor(self):
        assert self.calc.rate_performance(0.0, 0.0, 0.0) == PerformanceRating.VERY_POOR

    def test_excellent_score(self):
        # sharpe≥2 (+3), calmar≥1 (+3), win_rate≥60 (+3) = 9 → EXCELLENT
        assert self.calc.rate_performance(2.5, 1.5, 65.0) == PerformanceRating.EXCELLENT

    def test_good_score(self):
        # sharpe≥1 (+2), calmar≥0.5 (+2), win_rate≥50 (+2) = 6 → GOOD
        assert self.calc.rate_performance(1.5, 0.75, 55.0) == PerformanceRating.GOOD

    def test_average_score(self):
        # sharpe≥1 (+2), calmar≥0.5 (+2), win_rate<40 (+0) = 4 → AVERAGE
        assert self.calc.rate_performance(1.5, 0.75, 35.0) == PerformanceRating.AVERAGE

    def test_poor_score(self):
        # sharpe≥0.5 (+1), calmar≥0.25 (+1), win_rate≥40 (+1) = 3 → POOR
        assert self.calc.rate_performance(0.75, 0.35, 45.0) == PerformanceRating.POOR

    def test_very_poor_score(self):
        # all below thresholds → 0 → VERY_POOR
        assert self.calc.rate_performance(0.1, 0.1, 30.0) == PerformanceRating.VERY_POOR

    def test_boundary_sharpe_2(self):
        # sharpe=2.0 exactly → EXCELLENT threshold
        assert self.calc.rate_performance(2.0, 1.0, 60.0) == PerformanceRating.EXCELLENT


class TestGeneratePerformanceReport:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_returns_performance_report(self):
        rets = _make_returns(60)
        report = self.calc.generate_performance_report(rets)
        assert isinstance(report, PerformanceReport)

    def test_win_rate_between_0_and_100(self):
        rets = _make_returns(60)
        report = self.calc.generate_performance_report(rets)
        assert 0.0 <= report.win_rate <= 100.0

    def test_report_trade_totals_consistent(self):
        rets = _make_returns(60)
        report = self.calc.generate_performance_report(rets)
        assert report.winning_trades + report.losing_trades <= report.total_trades

    def test_volatility_non_negative(self):
        rets = _make_returns(60)
        report = self.calc.generate_performance_report(rets)
        assert report.volatility >= 0.0

    def test_rating_is_performance_rating(self):
        rets = _make_returns(60)
        report = self.calc.generate_performance_report(rets)
        assert isinstance(report.rating, PerformanceRating)

    def test_to_dict_works(self):
        rets = _make_returns(60)
        report = self.calc.generate_performance_report(rets)
        d = report.to_dict()
        assert isinstance(d, dict)
        assert "total_return" in d

    def test_module_level_function(self):
        rets = _make_returns(60)
        report = _u15.generate_performance_report(rets)
        assert isinstance(report, PerformanceReport)


class TestU15ModuleFunctions:
    def test_get_performance_calculator_returns_instance(self):
        inst = _u15.get_performance_calculator()
        assert isinstance(inst, PerformanceCalculator)

    def test_get_performance_calculator_is_singleton(self):
        a = _u15.get_performance_calculator()
        b = _u15.get_performance_calculator()
        assert a is b

    def test_calculate_metrics_returns_dict(self):
        result = _u15.calculate_metrics()
        assert isinstance(result, dict)

    def test_calculate_metrics_has_sharpe_key(self):
        result = _u15.calculate_metrics()
        assert "sharpe_ratio" in result

    def test_calculate_metrics_with_data(self):
        result = _u15.calculate_metrics(data={"test": 1})
        assert "win_rate" in result


class TestPerformanceCalculatorInit:
    def test_default_risk_free_rate(self):
        calc = PerformanceCalculator()
        assert calc.risk_free_rate == pytest.approx(_u15.RISK_FREE_RATE)

    def test_custom_risk_free_rate(self):
        calc = PerformanceCalculator(risk_free_rate=0.02)
        assert calc.risk_free_rate == pytest.approx(0.02)
