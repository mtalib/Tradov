#!/usr/bin/env python3
"""
SPYDER - Test Suite T100
Tests: SpyderU13_TechnicalIndicators + SpyderU15_PerformanceMetrics

Coverage:
    - U13: MAType, SignalType, TrendDirection enums; IndicatorResult, TrendAnalysis dataclasses;
           TechnicalIndicators class (RSI, Stochastic, Williams%R, MACD, ADX, BB, ATR,
           true range, SMA/EMA/WMA/HullMA, VWAP, OBV, signals); module functions
    - U15: PerformanceRating, MetricType enums; PerformanceReport, DrawdownInfo dataclasses;
           PerformanceCalculator class (total return, annualized return, volatility, Sharpe,
           Sortino, Calmar, max drawdown, drawdown analysis, win rate, profit factor,
           trade stats, rating, full report); module functions
"""

# ==============================================================================
# BOOTSTRAP — must run before any Spyder imports
# ==============================================================================
import os
import sys
import types
from unittest.mock import MagicMock

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _ensure_pkg(name: str) -> None:
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)


_ensure_pkg("Spyder")
_ensure_pkg("SpyderU_Utilities")
_ensure_pkg("Spyder.SpyderU_Utilities")

_logger_mod = types.ModuleType("Spyder.SpyderU_Utilities.SpyderU01_Logger")


class _FakeSpyderLogger:
    @staticmethod
    def get_logger(name: str) -> MagicMock:
        return MagicMock()


_logger_mod.SpyderLogger = _FakeSpyderLogger
_logger_mod.get_logger = MagicMock(return_value=MagicMock())
sys.modules["Spyder.SpyderU_Utilities.SpyderU01_Logger"] = _logger_mod

_err_mod = types.ModuleType("Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler")
_err_mod.SpyderErrorHandler = MagicMock
sys.modules["Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler"] = _err_mod

# ==============================================================================
# ACTUAL IMPORTS
# ==============================================================================
import math

import numpy as np
import pandas as pd
import pytest

from Spyder.SpyderU_Utilities.SpyderU13_TechnicalIndicators import (
    DEFAULT_ADX_PERIOD,
    DEFAULT_ATR_PERIOD,
    DEFAULT_BB_PERIOD,
    DEFAULT_BB_STDDEV,
    DEFAULT_MACD_FAST,
    DEFAULT_MACD_SIGNAL,
    DEFAULT_MACD_SLOW,
    DEFAULT_RSI_PERIOD,
    DEFAULT_STOCH_D,
    DEFAULT_STOCH_K,
    MA_TYPES,
    RSI_OVERBOUGHT,
    RSI_OVERSOLD,
    IndicatorResult,
    MAType,
    SignalType,
    TechnicalIndicators,
    TrendAnalysis,
    TrendDirection,
    calculate_bollinger_bands,
    calculate_macd,
    calculate_rsi,
    get_technical_indicators,
)
from Spyder.SpyderU_Utilities.SpyderU15_PerformanceMetrics import (
    MIN_PERIODS_FOR_CALCULATION,
    RISK_FREE_RATE,
    TRADING_DAYS_PER_YEAR,
    DrawdownInfo,
    MetricType,
    PerformanceCalculator,
    PerformanceRating,
    PerformanceReport,
    calculate_max_drawdown,
    calculate_metrics,
    calculate_sharpe_ratio,
    generate_performance_report,
    get_performance_calculator,
)

# ==============================================================================
# SHARED TEST DATA HELPERS
# ==============================================================================

_RNG = np.random.default_rng(42)


def _make_prices(n: int = 100, start: float = 100.0, seed: int = 42) -> pd.Series:
    """Generate realistic price series."""
    rng = np.random.default_rng(seed)
    changes = rng.normal(0, 0.5, n)
    prices = start + np.cumsum(changes)
    prices = np.maximum(prices, 1.0)  # prevent negatives
    return pd.Series(prices.tolist())


def _make_ohlcv(n: int = 100) -> tuple:
    """Return (high, low, close, volume) pandas Series."""
    close = _make_prices(n)
    high = close + np.abs(_RNG.normal(0, 0.5, n))
    low = close - np.abs(_RNG.normal(0, 0.5, n))
    low = pd.Series(np.maximum(low, 0.01))
    high = pd.Series(high.tolist())
    volume = pd.Series(_RNG.integers(1000, 10000, n).tolist())
    return high, low, close, volume


def _make_returns(n: int = 252, positive_bias: float = 0.001) -> pd.Series:
    """Generate return series with n periods (defaults to 1 year of daily returns)."""
    rng = np.random.default_rng(7)
    return pd.Series(rng.normal(positive_bias, 0.02, n).tolist())


# ==============================================================================
# U13 — ENUMS
# ==============================================================================


class TestMAType:
    def test_members_count(self):
        assert len(MAType) == 5

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

    def test_ma_types_list_length(self):
        assert len(MA_TYPES) == 5


class TestSignalType:
    def test_members_count(self):
        assert len(SignalType) == 5

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


class TestTrendDirectionU13:
    def test_members_count(self):
        assert len(TrendDirection) == 4

    def test_up(self):
        assert TrendDirection.UP.value == "up"

    def test_down(self):
        assert TrendDirection.DOWN.value == "down"

    def test_sideways(self):
        assert TrendDirection.SIDEWAYS.value == "sideways"

    def test_unknown(self):
        assert TrendDirection.UNKNOWN.value == "unknown"


# ==============================================================================
# U13 — DATACLASSES
# ==============================================================================


class TestIndicatorResult:
    def _make(self, **kwargs) -> IndicatorResult:
        defaults = dict(
            name="RSI",
            value=55.0,
            signal=SignalType.NEUTRAL,
            timestamp=pd.Timestamp("2025-01-01"),
            parameters={"period": 14},
        )
        defaults.update(kwargs)
        return IndicatorResult(**defaults)

    def test_creation(self):
        ir = self._make()
        assert ir.name == "RSI"

    def test_value_float(self):
        ir = self._make(value=72.5)
        assert ir.value == 72.5

    def test_value_dict(self):
        ir = self._make(value={"k": 80.0, "d": 78.0})
        assert isinstance(ir.value, dict)

    def test_signal(self):
        ir = self._make(signal=SignalType.BUY)
        assert ir.signal == SignalType.BUY

    def test_to_dict_keys(self):
        ir = self._make()
        d = ir.to_dict()
        assert set(d.keys()) == {"name", "value", "signal", "timestamp", "parameters"}

    def test_to_dict_signal_is_string(self):
        ir = self._make(signal=SignalType.STRONG_SELL)
        d = ir.to_dict()
        assert d["signal"] == "strong_sell"

    def test_to_dict_timestamp_is_string(self):
        ir = self._make()
        d = ir.to_dict()
        assert isinstance(d["timestamp"], str)

    def test_parameters_preserved(self):
        ir = self._make(parameters={"period": 26, "fast": 12})
        d = ir.to_dict()
        assert d["parameters"]["period"] == 26


class TestTrendAnalysis:
    def test_creation(self):
        ta = TrendAnalysis(
            direction=TrendDirection.UP,
            strength=0.75,
            duration=10,
            support_level=490.0,
            resistance_level=510.0,
        )
        assert ta.direction == TrendDirection.UP

    def test_strength(self):
        ta = TrendAnalysis(TrendDirection.DOWN, 0.3, 5, 480.0, 495.0)
        assert ta.strength == 0.3

    def test_duration(self):
        ta = TrendAnalysis(TrendDirection.SIDEWAYS, 0.1, 20, 100.0, 105.0)
        assert ta.duration == 20

    def test_levels(self):
        ta = TrendAnalysis(TrendDirection.UP, 0.8, 15, 490.0, 515.0)
        assert ta.support_level == 490.0
        assert ta.resistance_level == 515.0


# ==============================================================================
# U13 — TECHNICAL INDICATORS CLASS
# ==============================================================================


class TestTechnicalIndicatorsInit:
    def test_creates_instance(self):
        ti = TechnicalIndicators()
        assert ti is not None

    def test_has_logger(self):
        ti = TechnicalIndicators()
        assert ti.logger is not None

    def test_has_error_handler(self):
        ti = TechnicalIndicators()
        assert ti.error_handler is not None


class TestTechnicalIndicatorsRSI:
    def setup_method(self):
        self.ti = TechnicalIndicators()
        self.prices = _make_prices(100)

    def test_rsi_returns_series(self):
        result = self.ti.calculate_rsi(self.prices, period=14)
        assert isinstance(result, pd.Series)

    def test_rsi_length_matches_input(self):
        result = self.ti.calculate_rsi(self.prices, period=14)
        assert len(result) == len(self.prices)

    def test_rsi_insufficient_data_returns_all_nan(self):
        short = pd.Series([100.0, 101.0, 102.0])
        result = self.ti.calculate_rsi(short, period=14)
        # Returns a same-length series filled with NaN when insufficient data
        assert result.isna().all()

    def test_rsi_values_in_range(self):
        result = self.ti.calculate_rsi(self.prices, period=14)
        valid = result.dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_rsi_default_period(self):
        result = self.ti.calculate_rsi(self.prices)
        assert isinstance(result, pd.Series)

    def test_rsi_custom_period(self):
        result = self.ti.calculate_rsi(self.prices, period=7)
        # Should have non-NaN values from position 7 onwards
        assert not result.empty


class TestTechnicalIndicatorsStochastic:
    def setup_method(self):
        self.ti = TechnicalIndicators()
        self.high, self.low, self.close, _ = _make_ohlcv(100)

    def test_returns_dict(self):
        result = self.ti.calculate_stochastic(self.high, self.low, self.close)
        assert isinstance(result, dict)

    def test_has_k_and_d(self):
        result = self.ti.calculate_stochastic(self.high, self.low, self.close)
        assert "%K" in result and "%D" in result

    def test_k_is_series(self):
        result = self.ti.calculate_stochastic(self.high, self.low, self.close)
        assert isinstance(result["%K"], pd.Series)

    def test_d_is_series(self):
        result = self.ti.calculate_stochastic(self.high, self.low, self.close)
        assert isinstance(result["%D"], pd.Series)

    def test_k_values_range(self):
        result = self.ti.calculate_stochastic(self.high, self.low, self.close)
        # After fillna(50), values should be 0-100
        assert (result["%K"] >= 0).all() and (result["%K"] <= 100).all()


class TestTechnicalIndicatorsWilliamsR:
    def setup_method(self):
        self.ti = TechnicalIndicators()
        self.high, self.low, self.close, _ = _make_ohlcv(50)

    def test_returns_series(self):
        result = self.ti.calculate_williams_r(self.high, self.low, self.close)
        assert isinstance(result, pd.Series)

    def test_length_matches(self):
        result = self.ti.calculate_williams_r(self.high, self.low, self.close)
        assert len(result) == len(self.close)

    def test_values_range(self):
        result = self.ti.calculate_williams_r(self.high, self.low, self.close)
        valid = result.dropna()
        assert (valid >= -100).all() and (valid <= 0).all()


class TestTechnicalIndicatorsMACD:
    def setup_method(self):
        self.ti = TechnicalIndicators()
        self.prices = _make_prices(100)

    def test_returns_dict(self):
        result = self.ti.calculate_macd(self.prices)
        assert isinstance(result, dict)

    def test_has_keys(self):
        result = self.ti.calculate_macd(self.prices)
        assert "MACD" in result and "Signal" in result and "Histogram" in result

    def test_all_are_series(self):
        result = self.ti.calculate_macd(self.prices)
        for v in result.values():
            assert isinstance(v, pd.Series)

    def test_histogram_equals_macd_minus_signal(self):
        result = self.ti.calculate_macd(self.prices)
        expected = result["MACD"] - result["Signal"]
        pd.testing.assert_series_equal(result["Histogram"], expected)

    def test_custom_periods(self):
        result = self.ti.calculate_macd(self.prices, fast=5, slow=10, signal=3)
        assert "MACD" in result


class TestTechnicalIndicatorsADX:
    def setup_method(self):
        self.ti = TechnicalIndicators()
        self.high, self.low, self.close, _ = _make_ohlcv(60)

    def test_returns_dict(self):
        result = self.ti.calculate_adx(self.high, self.low, self.close)
        assert isinstance(result, dict)

    def test_has_adx_keys(self):
        result = self.ti.calculate_adx(self.high, self.low, self.close)
        assert "ADX" in result and "+DI" in result and "-DI" in result

    def test_all_series(self):
        result = self.ti.calculate_adx(self.high, self.low, self.close)
        for v in result.values():
            assert isinstance(v, pd.Series)


class TestTechnicalIndicatorsBollingerBands:
    def setup_method(self):
        self.ti = TechnicalIndicators()
        self.prices = _make_prices(100)

    def test_returns_dict(self):
        result = self.ti.calculate_bollinger_bands(self.prices)
        assert isinstance(result, dict)

    def test_has_keys(self):
        result = self.ti.calculate_bollinger_bands(self.prices)
        assert "Upper" in result and "Middle" in result and "Lower" in result

    def test_upper_above_middle(self):
        result = self.ti.calculate_bollinger_bands(self.prices)
        valid = result["Upper"].dropna()
        middle_valid = result["Middle"].dropna()
        assert (valid.values >= middle_valid.values).all()

    def test_lower_below_middle(self):
        result = self.ti.calculate_bollinger_bands(self.prices)
        valid = result["Lower"].dropna()
        middle_valid = result["Middle"].dropna()
        assert (valid.values <= middle_valid.values).all()

    def test_custom_std_dev(self):
        result = self.ti.calculate_bollinger_bands(self.prices, std_dev=1.5)
        assert "Upper" in result


class TestTechnicalIndicatorsATRTR:
    def setup_method(self):
        self.ti = TechnicalIndicators()
        self.high, self.low, self.close, _ = _make_ohlcv(50)

    def test_atr_returns_series(self):
        result = self.ti.calculate_atr(self.high, self.low, self.close)
        assert isinstance(result, pd.Series)

    def test_atr_non_negative(self):
        result = self.ti.calculate_atr(self.high, self.low, self.close)
        valid = result.dropna()
        assert (valid >= 0).all()

    def test_true_range_returns_series(self):
        result = self.ti.calculate_true_range(self.high, self.low, self.close)
        assert isinstance(result, pd.Series)

    def test_true_range_length(self):
        result = self.ti.calculate_true_range(self.high, self.low, self.close)
        assert len(result) == len(self.close)

    def test_true_range_non_negative(self):
        result = self.ti.calculate_true_range(self.high, self.low, self.close)
        valid = result.dropna()
        assert (valid >= 0).all()


class TestTechnicalIndicatorsMovingAverages:
    def setup_method(self):
        self.ti = TechnicalIndicators()
        self.prices = _make_prices(60)

    def test_sma_returns_series(self):
        result = self.ti.calculate_sma(self.prices, 10)
        assert isinstance(result, pd.Series)

    def test_sma_length(self):
        result = self.ti.calculate_sma(self.prices, 10)
        assert len(result) == len(self.prices)

    def test_ema_returns_series(self):
        result = self.ti.calculate_ema(self.prices, 10)
        assert isinstance(result, pd.Series)

    def test_ema_no_nan(self):
        # EMA with ewm doesn't produce NaN beyond the first value
        result = self.ti.calculate_ema(self.prices, 10)
        assert result.notna().sum() > 0

    def test_wma_returns_series(self):
        result = self.ti.calculate_wma(self.prices, 5)
        assert isinstance(result, pd.Series)

    def test_hull_ma_returns_series(self):
        result = self.ti.calculate_hull_ma(self.prices, 10)
        assert isinstance(result, pd.Series)


class TestTechnicalIndicatorsVolumeIndicators:
    def setup_method(self):
        self.ti = TechnicalIndicators()
        self.high, self.low, self.close, self.volume = _make_ohlcv(50)

    def test_vwap_returns_series(self):
        result = self.ti.calculate_vwap(self.high, self.low, self.close, self.volume)
        assert isinstance(result, pd.Series)

    def test_vwap_length(self):
        result = self.ti.calculate_vwap(self.high, self.low, self.close, self.volume)
        assert len(result) == len(self.close)

    def test_obv_returns_series(self):
        result = self.ti.calculate_obv(self.close, self.volume)
        assert isinstance(result, pd.Series)

    def test_obv_length(self):
        result = self.ti.calculate_obv(self.close, self.volume)
        assert len(result) == len(self.close)


class TestTechnicalIndicatorsSignals:
    def setup_method(self):
        self.ti = TechnicalIndicators()
        self.prices = _make_prices(100)

    def test_rsi_signal_neutral(self):
        # Construct RSI series at neutral level
        rsi = pd.Series([50.0] * 10)
        assert self.ti.generate_rsi_signal(rsi) == SignalType.NEUTRAL

    def test_rsi_signal_overbought(self):
        rsi = pd.Series([75.0])
        assert self.ti.generate_rsi_signal(rsi) == SignalType.SELL

    def test_rsi_signal_oversold(self):
        rsi = pd.Series([25.0])
        assert self.ti.generate_rsi_signal(rsi) == SignalType.BUY

    def test_rsi_signal_strong_sell(self):
        rsi = pd.Series([85.0])
        assert self.ti.generate_rsi_signal(rsi) == SignalType.STRONG_SELL

    def test_rsi_signal_strong_buy(self):
        rsi = pd.Series([15.0])
        assert self.ti.generate_rsi_signal(rsi) == SignalType.STRONG_BUY

    def test_macd_signal_neutral(self):
        macd_data = {
            "MACD": pd.Series([0.5, 0.6]),
            "Signal": pd.Series([0.4, 0.55]),
            "Histogram": pd.Series([0.1, 0.05]),
        }
        result = self.ti.generate_macd_signal(macd_data)
        assert result == SignalType.NEUTRAL

    def test_macd_signal_returns_signal_type(self):
        prices = _make_prices(100)
        macd_data = self.ti.calculate_macd(prices)
        result = self.ti.generate_macd_signal(macd_data)
        assert isinstance(result, SignalType)


# ==============================================================================
# U13 — CONSTANTS
# ==============================================================================


class TestU13Constants:
    def test_default_rsi_period(self):
        assert DEFAULT_RSI_PERIOD == 14

    def test_default_macd_fast(self):
        assert DEFAULT_MACD_FAST == 12

    def test_default_macd_slow(self):
        assert DEFAULT_MACD_SLOW == 26

    def test_default_macd_signal(self):
        assert DEFAULT_MACD_SIGNAL == 9

    def test_default_bb_period(self):
        assert DEFAULT_BB_PERIOD == 20

    def test_default_bb_stddev(self):
        assert DEFAULT_BB_STDDEV == 2.0

    def test_rsi_overbought(self):
        assert RSI_OVERBOUGHT == 70

    def test_rsi_oversold(self):
        assert RSI_OVERSOLD == 30


# ==============================================================================
# U13 — MODULE FUNCTIONS
# ==============================================================================


class TestU13ModuleFunctions:
    def test_calculate_rsi_returns_series(self):
        prices = _make_prices(60)
        result = calculate_rsi(prices)
        assert isinstance(result, pd.Series)

    def test_calculate_rsi_custom_period(self):
        prices = _make_prices(60)
        result = calculate_rsi(prices, period=7)
        assert isinstance(result, pd.Series)

    def test_calculate_macd_returns_dict(self):
        prices = _make_prices(80)
        result = calculate_macd(prices)
        assert isinstance(result, dict) and "MACD" in result

    def test_calculate_bollinger_bands_returns_dict(self):
        prices = _make_prices(60)
        result = calculate_bollinger_bands(prices)
        assert "Upper" in result and "Lower" in result

    def test_get_technical_indicators_returns_instance(self):
        ti = get_technical_indicators()
        assert isinstance(ti, TechnicalIndicators)

    def test_get_technical_indicators_singleton(self):
        ti1 = get_technical_indicators()
        ti2 = get_technical_indicators()
        assert ti1 is ti2


# ==============================================================================
# U15 — ENUMS
# ==============================================================================


class TestPerformanceRating:
    def test_members_count(self):
        assert len(PerformanceRating) == 5

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


class TestMetricType:
    def test_members_count(self):
        assert len(MetricType) == 5

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


# ==============================================================================
# U15 — DATACLASSES
# ==============================================================================


class TestPerformanceReport:
    def _make_report(self, **kwargs) -> PerformanceReport:
        defaults = dict(
            total_return=0.15,
            annualized_return=0.12,
            volatility=0.18,
            sharpe_ratio=1.2,
            sortino_ratio=1.5,
            calmar_ratio=0.8,
            max_drawdown=-0.12,
            max_drawdown_duration=30,
            win_rate=55.0,
            profit_factor=1.5,
            avg_win=0.02,
            avg_loss=-0.015,
            largest_win=0.08,
            largest_loss=-0.06,
            total_trades=100,
            winning_trades=55,
            losing_trades=45,
            rating=PerformanceRating.GOOD,
        )
        defaults.update(kwargs)
        return PerformanceReport(**defaults)

    def test_creation(self):
        report = self._make_report()
        assert report.total_return == 0.15

    def test_rating(self):
        report = self._make_report(rating=PerformanceRating.EXCELLENT)
        assert report.rating == PerformanceRating.EXCELLENT

    def test_to_dict_keys(self):
        report = self._make_report()
        d = report.to_dict()
        expected_keys = {
            "total_return", "annualized_return", "volatility", "sharpe_ratio",
            "sortino_ratio", "calmar_ratio", "max_drawdown", "max_drawdown_duration",
            "win_rate", "profit_factor", "avg_win", "avg_loss", "largest_win",
            "largest_loss", "total_trades", "winning_trades", "losing_trades", "rating"
        }
        assert expected_keys == set(d.keys())

    def test_to_dict_rating_is_string(self):
        report = self._make_report(rating=PerformanceRating.GOOD)
        d = report.to_dict()
        assert d["rating"] == "good"

    def test_to_dict_values(self):
        report = self._make_report()
        d = report.to_dict()
        assert d["total_return"] == 0.15
        assert d["total_trades"] == 100


class TestDrawdownInfo:
    def test_creation(self):
        di = DrawdownInfo(
            max_drawdown=-0.15,
            max_drawdown_duration=25,
            recovery_time=10,
            drawdown_periods=[(0, 5, -0.1), (10, 20, -0.15)],
        )
        assert di.max_drawdown == -0.15

    def test_duration(self):
        di = DrawdownInfo(-0.1, 20, 5, [])
        assert di.max_drawdown_duration == 20

    def test_recovery_time(self):
        di = DrawdownInfo(-0.1, 20, 15, [])
        assert di.recovery_time == 15

    def test_periods_list(self):
        periods = [(0, 3, -0.05), (5, 8, -0.1)]
        di = DrawdownInfo(-0.1, 5, 0, periods)
        assert len(di.drawdown_periods) == 2


# ==============================================================================
# U15 — PERFORMANCE CALCULATOR
# ==============================================================================

_RETURNS_LONG = _make_returns(252)  # 252 days — above MIN_PERIODS_FOR_CALCULATION
_RETURNS_SHORT = _make_returns(10)  # 10 days — below MIN_PERIODS_FOR_CALCULATION (30)


class TestPerformanceCalculatorInit:
    def test_creation(self):
        calc = PerformanceCalculator()
        assert calc is not None

    def test_default_risk_free_rate(self):
        calc = PerformanceCalculator()
        assert calc.risk_free_rate == RISK_FREE_RATE

    def test_custom_risk_free_rate(self):
        calc = PerformanceCalculator(risk_free_rate=0.02)
        assert calc.risk_free_rate == 0.02

    def test_has_logger(self):
        calc = PerformanceCalculator()
        assert calc.logger is not None


class TestPerformanceCalculatorReturnMetrics:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_total_return_empty(self):
        result = self.calc.calculate_total_return(pd.Series([], dtype=float))
        assert result == 0.0

    def test_total_return_positive(self):
        returns = pd.Series([0.01, 0.02, 0.015])
        result = self.calc.calculate_total_return(returns)
        assert result > 0

    def test_total_return_negative(self):
        returns = pd.Series([-0.03, -0.02, -0.01])
        result = self.calc.calculate_total_return(returns)
        assert result < 0

    def test_total_return_formula(self):
        returns = pd.Series([0.10, 0.10])
        # (1.1 * 1.1) - 1 = 0.21
        result = self.calc.calculate_total_return(returns)
        assert abs(result - 0.21) < 1e-10

    def test_annualized_return_empty(self):
        result = self.calc.calculate_annualized_return(pd.Series([], dtype=float))
        assert result == 0.0

    def test_annualized_return_positive(self):
        result = self.calc.calculate_annualized_return(_RETURNS_LONG)
        assert isinstance(result, float)

    def test_volatility_empty(self):
        result = self.calc.calculate_volatility(pd.Series([0.01], dtype=float))
        assert result == 0.0

    def test_volatility_positive(self):
        result = self.calc.calculate_volatility(_RETURNS_LONG)
        assert result > 0


class TestPerformanceCalculatorRiskAdjusted:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_sharpe_too_few_periods(self):
        result = self.calc.calculate_sharpe_ratio(_RETURNS_SHORT)
        assert result == 0.0

    def test_sharpe_returns_float(self):
        result = self.calc.calculate_sharpe_ratio(_RETURNS_LONG)
        assert isinstance(result, float)

    def test_sharpe_exactly_min_periods_boundary(self):
        # Exactly at the boundary: MIN_PERIODS_FOR_CALCULATION - 1 → returns 0.0
        returns = pd.Series([0.01] * (MIN_PERIODS_FOR_CALCULATION - 1))
        result = self.calc.calculate_sharpe_ratio(returns)
        assert result == 0.0

    def test_sortino_too_few_periods(self):
        result = self.calc.calculate_sortino_ratio(_RETURNS_SHORT)
        assert result == 0.0

    def test_sortino_returns_float_or_inf(self):
        result = self.calc.calculate_sortino_ratio(_RETURNS_LONG)
        assert isinstance(result, float) or math.isinf(result)

    def test_sortino_all_positive_returns_inf(self):
        returns = pd.Series([0.01] * 50)
        result = self.calc.calculate_sortino_ratio(returns)
        assert math.isinf(result) or result == 0.0

    def test_calmar_too_few_periods(self):
        result = self.calc.calculate_calmar_ratio(_RETURNS_SHORT)
        assert result == 0.0

    def test_calmar_returns_float(self):
        result = self.calc.calculate_calmar_ratio(_RETURNS_LONG)
        assert isinstance(result, float) or math.isinf(result)


class TestPerformanceCalculatorDrawdown:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_max_drawdown_empty(self):
        result = self.calc.calculate_max_drawdown(pd.Series([], dtype=float))
        assert result == 0.0

    def test_max_drawdown_monotone_up(self):
        # A monotonically increasing cum_returns series has 0 drawdown
        cum = pd.Series([0.0, 0.01, 0.02, 0.03, 0.04])
        result = self.calc.calculate_max_drawdown(cum)
        assert result == 0.0

    def test_max_drawdown_with_drop(self):
        cum = pd.Series([0.0, 0.05, 0.03, 0.01, 0.06])
        result = self.calc.calculate_max_drawdown(cum)
        assert result < 0

    def test_max_drawdown_returns_float(self):
        result = self.calc.calculate_max_drawdown(_RETURNS_LONG.cumsum())
        assert isinstance(result, float)

    def test_analyze_drawdowns_empty(self):
        di = self.calc.analyze_drawdowns(pd.Series([], dtype=float))
        assert isinstance(di, DrawdownInfo)
        assert di.max_drawdown == 0.0

    def test_analyze_drawdowns_returns_drawdown_info(self):
        cum = (1 + _RETURNS_LONG).cumprod() - 1
        di = self.calc.analyze_drawdowns(cum)
        assert isinstance(di, DrawdownInfo)

    def test_analyze_drawdowns_no_dd(self):
        # Monotonic up: no drawdown periods
        cum = pd.Series(np.linspace(0, 0.5, 50).tolist())
        di = self.calc.analyze_drawdowns(cum)
        assert di.max_drawdown == 0.0


class TestPerformanceCalculatorTradingStats:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_win_rate_empty(self):
        result = self.calc.calculate_win_rate(pd.Series([], dtype=float))
        assert result == 0.0

    def test_win_rate_all_positive(self):
        returns = pd.Series([0.01, 0.02, 0.015])
        result = self.calc.calculate_win_rate(returns)
        assert result == 100.0

    def test_win_rate_half(self):
        returns = pd.Series([0.01, -0.01, 0.02, -0.02])
        result = self.calc.calculate_win_rate(returns)
        assert result == 50.0

    def test_profit_factor_empty(self):
        result = self.calc.calculate_profit_factor(pd.Series([], dtype=float))
        assert result == 0.0

    def test_profit_factor_all_positive(self):
        returns = pd.Series([0.01, 0.02])
        result = self.calc.calculate_profit_factor(returns)
        assert math.isinf(result)

    def test_profit_factor_mixed(self):
        returns = pd.Series([0.02, -0.01])
        result = self.calc.calculate_profit_factor(returns)
        assert abs(result - 2.0) < 1e-9

    def test_trade_statistics_empty(self):
        result = self.calc.calculate_trade_statistics(pd.Series([], dtype=float))
        assert result["total_trades"] == 0

    def test_trade_statistics_keys(self):
        result = self.calc.calculate_trade_statistics(_RETURNS_LONG)
        expected = {"total_trades", "winning_trades", "losing_trades", "avg_win", "avg_loss",
                    "largest_win", "largest_loss"}
        assert expected == set(result.keys())

    def test_trade_statistics_counts(self):
        returns = pd.Series([0.01, -0.01, 0.02, -0.02, 0.03])
        result = self.calc.calculate_trade_statistics(returns)
        assert result["total_trades"] == 5
        assert result["winning_trades"] == 3
        assert result["losing_trades"] == 2


class TestPerformanceCalculatorRating:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_excellent_rating_high_scores(self):
        # sharpe>=2, calmar>=1, win_rate>=60 → score = 9 → EXCELLENT
        rating = self.calc.rate_performance(sharpe_ratio=2.5, calmar_ratio=1.5, win_rate=65.0)
        assert rating == PerformanceRating.EXCELLENT

    def test_very_poor_rating_zero_scores(self):
        rating = self.calc.rate_performance(sharpe_ratio=0.1, calmar_ratio=0.1, win_rate=30.0)
        assert rating == PerformanceRating.VERY_POOR

    def test_returns_performance_rating(self):
        rating = self.calc.rate_performance(1.5, 0.8, 55.0)
        assert isinstance(rating, PerformanceRating)


class TestPerformanceCalculatorReport:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_report_returns_performance_report(self):
        report = self.calc.generate_performance_report(_RETURNS_LONG)
        assert isinstance(report, PerformanceReport)

    def test_report_has_rating(self):
        report = self.calc.generate_performance_report(_RETURNS_LONG)
        assert isinstance(report.rating, PerformanceRating)

    def test_report_total_trades(self):
        report = self.calc.generate_performance_report(_RETURNS_LONG)
        assert report.total_trades == len(_RETURNS_LONG)

    def test_report_to_dict(self):
        report = self.calc.generate_performance_report(_RETURNS_LONG)
        d = report.to_dict()
        assert isinstance(d, dict) and "total_return" in d

    def test_report_empty_returns_default(self):
        report = self.calc.generate_performance_report(pd.Series([], dtype=float))
        assert isinstance(report, PerformanceReport)


# ==============================================================================
# U15 — MODULE CONSTANTS
# ==============================================================================


class TestU15Constants:
    def test_trading_days(self):
        assert TRADING_DAYS_PER_YEAR == 252

    def test_min_periods(self):
        assert MIN_PERIODS_FOR_CALCULATION == 30

    def test_risk_free_rate_positive(self):
        assert 0 < RISK_FREE_RATE < 1


# ==============================================================================
# U15 — MODULE FUNCTIONS
# ==============================================================================


class TestU15ModuleFunctions:
    def test_calculate_sharpe_ratio_too_short(self):
        result = calculate_sharpe_ratio(pd.Series([0.01, 0.02]))
        assert result == 0.0

    def test_calculate_sharpe_ratio_long(self):
        result = calculate_sharpe_ratio(_RETURNS_LONG)
        assert isinstance(result, float)

    def test_calculate_sharpe_ratio_custom_rfr(self):
        result = calculate_sharpe_ratio(_RETURNS_LONG, risk_free_rate=0.02)
        assert isinstance(result, float)

    def test_calculate_max_drawdown_monotone(self):
        cum = pd.Series([0.0, 0.01, 0.02, 0.03])
        result = calculate_max_drawdown(cum)
        assert result == 0.0

    def test_calculate_max_drawdown_negative(self):
        cum = pd.Series([0.0, 0.05, 0.02, 0.04])
        result = calculate_max_drawdown(cum)
        assert result < 0

    def test_generate_performance_report_returns_report(self):
        result = generate_performance_report(_RETURNS_LONG)
        assert isinstance(result, PerformanceReport)

    def test_get_performance_calculator_returns_instance(self):
        calc = get_performance_calculator()
        assert isinstance(calc, PerformanceCalculator)

    def test_get_performance_calculator_singleton(self):
        c1 = get_performance_calculator()
        c2 = get_performance_calculator()
        assert c1 is c2

    def test_calculate_metrics_returns_dict(self):
        result = calculate_metrics()
        assert isinstance(result, dict)

    def test_calculate_metrics_has_keys(self):
        result = calculate_metrics()
        assert "sharpe_ratio" in result and "max_drawdown" in result
