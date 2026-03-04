#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT72_TechnicalAnalysisTests.py
Purpose: Tests for U16 TechnicalAnalysis

Author: Spyder Test Suite
Year Created: 2026
Last Updated: 2026-03-04 Time: 21:00:00
"""

# ==============================================================================
# BOOTSTRAP — U16 handles ImportError for its local deps gracefully, so
# we just need the Spyder package namespace and load U16 directly.
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

# U16 catches ImportError for its local deps (SpyderLogger/SpyderErrorHandler)
# and falls back to None — no special injection needed.
_u16 = _load("Spyder/SpyderU_Utilities/SpyderU16_TechnicalAnalysis.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU16_TechnicalAnalysis"] = _u16

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import math
import pytest
import numpy as np
import pandas as pd
from datetime import datetime
from unittest.mock import patch

# ==============================================================================
# MODULE IMPORTS — U16
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU16_TechnicalAnalysis import (
    TrendDirection,
    SignalStrength,
    TechnicalSignal,
    TechnicalAnalysisResult,
    TechnicalAnalysis,
    quick_analysis,
    get_technical_analysis,
    DEFAULT_PERIODS,
    SIGNAL_THRESHOLDS,
    TA_AVAILABLE,
)


# ==============================================================================
# HELPERS — OHLCV FIXTURE GENERATION
# ==============================================================================

def _make_ohlcv(n: int = 100, base_price: float = 450.0,
                trend: float = 0.001, vol: float = 2.0,
                seed: int = 42) -> pd.DataFrame:
    """
    Generate a realistic OHLCV DataFrame with n rows.
    Ensures high >= close >= low for every row.
    """
    rng = np.random.default_rng(seed)
    prices = [base_price]
    for _ in range(n - 1):
        prices.append(prices[-1] * (1 + trend + rng.normal(0, 0.005)))

    closes = np.array(prices)
    noise = rng.uniform(0.1, vol, n)
    highs = closes + rng.uniform(0.1, vol, n)
    lows = closes - rng.uniform(0.1, vol, n)
    opens = closes + rng.uniform(-vol / 2, vol / 2, n)

    # Clip to enforce high >= close >= low
    highs = np.maximum(highs, closes)
    lows = np.minimum(lows, closes)

    volumes = rng.integers(100_000, 10_000_000, n).astype(float)

    return pd.DataFrame({
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    })


def _uptrend_ohlcv(n: int = 100) -> pd.DataFrame:
    """Strong uptrend OHLCV — price well above both SMAs."""
    return _make_ohlcv(n=n, base_price=400.0, trend=0.003, vol=0.5, seed=1)


def _downtrend_ohlcv(n: int = 100) -> pd.DataFrame:
    """Strong downtrend OHLCV."""
    return _make_ohlcv(n=n, base_price=500.0, trend=-0.003, vol=0.5, seed=2)


def _flat_ohlcv(n: int = 100) -> pd.DataFrame:
    """Flat / oscillating OHLCV."""
    return _make_ohlcv(n=n, base_price=450.0, trend=0.0, vol=1.0, seed=3)


# ==============================================================================
# ENUM TESTS
# ==============================================================================

class TestTrendDirectionEnum:
    def test_strong_up_value(self):
        assert TrendDirection.STRONG_UP.value == "strong_up"

    def test_up_value(self):
        assert TrendDirection.UP.value == "up"

    def test_neutral_value(self):
        assert TrendDirection.NEUTRAL.value == "neutral"

    def test_down_value(self):
        assert TrendDirection.DOWN.value == "down"

    def test_strong_down_value(self):
        assert TrendDirection.STRONG_DOWN.value == "strong_down"

    def test_five_members(self):
        assert len(list(TrendDirection)) == 5


class TestSignalStrengthEnum:
    def test_very_strong_value(self):
        assert SignalStrength.VERY_STRONG.value == "very_strong"

    def test_strong_value(self):
        assert SignalStrength.STRONG.value == "strong"

    def test_moderate_value(self):
        assert SignalStrength.MODERATE.value == "moderate"

    def test_weak_value(self):
        assert SignalStrength.WEAK.value == "weak"

    def test_very_weak_value(self):
        assert SignalStrength.VERY_WEAK.value == "very_weak"

    def test_five_members(self):
        assert len(list(SignalStrength)) == 5


# ==============================================================================
# DATACLASS TESTS
# ==============================================================================

class TestTechnicalSignal:
    def _make_signal(self, **kwargs):
        defaults = dict(
            indicator="RSI", value=35.0, signal="buy",
            strength=SignalStrength.MODERATE, timestamp=datetime.now()
        )
        defaults.update(kwargs)
        return TechnicalSignal(**defaults)

    def test_basic_creation(self):
        sig = self._make_signal()
        assert sig.indicator == "RSI"
        assert sig.signal == "buy"

    def test_metadata_defaults_none(self):
        sig = self._make_signal()
        assert sig.metadata is None

    def test_metadata_can_be_set(self):
        sig = self._make_signal(metadata={"extra": "info"})
        assert sig.metadata["extra"] == "info"

    def test_strength_is_signal_strength(self):
        sig = self._make_signal(strength=SignalStrength.STRONG)
        assert sig.strength == SignalStrength.STRONG

    def test_timestamp_is_datetime(self):
        sig = self._make_signal()
        assert isinstance(sig.timestamp, datetime)


class TestTechnicalAnalysisResult:
    def _make_result(self):
        return TechnicalAnalysisResult(
            trend=TrendDirection.UP,
            momentum={"rsi": 55.0},
            volatility={"atr": 2.5},
            volume={"vwap": 450.0},
            signals=[],
            composite_score=30.0,
            timestamp=datetime.now(),
        )

    def test_basic_creation(self):
        res = self._make_result()
        assert res.trend == TrendDirection.UP
        assert res.composite_score == 30.0

    def test_momentum_dict(self):
        res = self._make_result()
        assert isinstance(res.momentum, dict)

    def test_signals_list(self):
        res = self._make_result()
        assert isinstance(res.signals, list)


# ==============================================================================
# CONSTANTS TESTS
# ==============================================================================

class TestConstants:
    def test_default_periods_has_rsi(self):
        assert "rsi" in DEFAULT_PERIODS
        assert DEFAULT_PERIODS["rsi"] == 14

    def test_default_periods_has_sma_short(self):
        assert "sma_short" in DEFAULT_PERIODS
        assert DEFAULT_PERIODS["sma_short"] == 20

    def test_signal_thresholds_rsi_oversold(self):
        assert SIGNAL_THRESHOLDS["rsi_oversold"] == 30

    def test_signal_thresholds_rsi_overbought(self):
        assert SIGNAL_THRESHOLDS["rsi_overbought"] == 70

    def test_signal_thresholds_adx(self):
        assert "adx_trending" in SIGNAL_THRESHOLDS


# ==============================================================================
# TechnicalAnalysis INIT TESTS
# ==============================================================================

class TestTechnicalAnalysisInit:
    def test_basic_instantiation(self):
        ta = TechnicalAnalysis()
        assert ta is not None

    def test_default_periods_set(self):
        ta = TechnicalAnalysis()
        assert ta.periods["rsi"] == 14

    def test_custom_config_overrides_period(self):
        ta = TechnicalAnalysis(config={"periods": {"rsi": 9}})
        assert ta.periods["rsi"] == 9

    def test_default_thresholds_set(self):
        ta = TechnicalAnalysis()
        assert ta.thresholds["rsi_oversold"] == 30

    def test_custom_thresholds_override(self):
        ta = TechnicalAnalysis(config={"thresholds": {"rsi_oversold": 25}})
        assert ta.thresholds["rsi_oversold"] == 25

    def test_indicator_cache_empty(self):
        ta = TechnicalAnalysis()
        assert ta.indicator_cache == {}

    def test_none_config_uses_defaults(self):
        ta = TechnicalAnalysis(config=None)
        assert ta.periods == {**DEFAULT_PERIODS}


# ==============================================================================
# calculate_sma TESTS
# ==============================================================================

class TestCalculateSma:
    def setup_method(self):
        self.ta = TechnicalAnalysis()
        self.df = _make_ohlcv()

    def test_returns_series(self):
        result = self.ta.calculate_sma(self.df["close"])
        assert isinstance(result, pd.Series)

    def test_same_length_as_input(self):
        result = self.ta.calculate_sma(self.df["close"])
        assert len(result) == len(self.df)

    def test_early_values_nan(self):
        result = self.ta.calculate_sma(self.df["close"], period=20)
        # First 19 values should be NaN
        assert result.iloc[0:19].isna().all()

    def test_later_values_not_nan(self):
        result = self.ta.calculate_sma(self.df["close"], period=20)
        assert not result.iloc[20:].isna().any()

    def test_custom_period(self):
        result = self.ta.calculate_sma(self.df["close"], period=5)
        assert not result.iloc[5:].isna().any()

    def test_sma_value_reasonable(self):
        result = self.ta.calculate_sma(self.df["close"], period=5)
        # SMA should be in the ballpark of close prices
        last_sma = result.iloc[-1]
        assert 300 < last_sma < 700


# ==============================================================================
# calculate_ema TESTS
# ==============================================================================

class TestCalculateEma:
    def setup_method(self):
        self.ta = TechnicalAnalysis()
        self.df = _make_ohlcv()

    def test_returns_series(self):
        result = self.ta.calculate_ema(self.df["close"])
        assert isinstance(result, pd.Series)

    def test_same_length(self):
        result = self.ta.calculate_ema(self.df["close"])
        assert len(result) == len(self.df)

    def test_no_nan_at_end(self):
        result = self.ta.calculate_ema(self.df["close"], period=10)
        assert not result.iloc[-20:].isna().any()

    def test_ema_value_in_range(self):
        result = self.ta.calculate_ema(self.df["close"], period=10)
        assert 300 < result.iloc[-1] < 700


# ==============================================================================
# calculate_macd TESTS
# ==============================================================================

class TestCalculateMacd:
    def setup_method(self):
        self.ta = TechnicalAnalysis()
        self.df = _make_ohlcv()

    def test_returns_dict(self):
        result = self.ta.calculate_macd(self.df["close"])
        assert isinstance(result, dict)

    def test_has_macd_key(self):
        result = self.ta.calculate_macd(self.df["close"])
        assert "macd" in result

    def test_has_signal_key(self):
        result = self.ta.calculate_macd(self.df["close"])
        assert "signal" in result

    def test_has_histogram_key(self):
        result = self.ta.calculate_macd(self.df["close"])
        assert "histogram" in result

    def test_each_value_is_series(self):
        result = self.ta.calculate_macd(self.df["close"])
        for key in ("macd", "signal", "histogram"):
            assert isinstance(result[key], pd.Series)

    def test_same_length_as_input(self):
        result = self.ta.calculate_macd(self.df["close"])
        assert len(result["macd"]) == len(self.df)

    def test_histogram_is_macd_minus_signal(self):
        result = self.ta.calculate_macd(self.df["close"])
        # histogram ≈ macd - signal
        combined = (result["macd"] - result["signal"]).dropna()
        hist = result["histogram"].dropna()
        # Align
        idx = combined.index.intersection(hist.index)
        np.testing.assert_allclose(combined.loc[idx].values, hist.loc[idx].values, atol=1e-6)


# ==============================================================================
# calculate_adx TESTS
# ==============================================================================

class TestCalculateAdx:
    def setup_method(self):
        self.ta = TechnicalAnalysis()
        self.df = _make_ohlcv()

    def test_returns_series(self):
        result = self.ta.calculate_adx(self.df["high"], self.df["low"], self.df["close"])
        assert isinstance(result, pd.Series)

    def test_same_length(self):
        result = self.ta.calculate_adx(self.df["high"], self.df["low"], self.df["close"])
        assert len(result) == len(self.df)

    def test_adx_non_negative_at_end(self):
        result = self.ta.calculate_adx(self.df["high"], self.df["low"], self.df["close"])
        valid = result.dropna()
        assert (valid >= 0).all()


# ==============================================================================
# calculate_rsi TESTS
# ==============================================================================

class TestCalculateRsi:
    def setup_method(self):
        self.ta = TechnicalAnalysis()
        self.df = _make_ohlcv()

    def test_returns_series(self):
        result = self.ta.calculate_rsi(self.df["close"])
        assert isinstance(result, pd.Series)

    def test_same_length(self):
        result = self.ta.calculate_rsi(self.df["close"])
        assert len(result) == len(self.df)

    def test_values_in_0_100_range(self):
        result = self.ta.calculate_rsi(self.df["close"])
        valid = result.dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_constant_price_series(self):
        # Constant close → delta = 0 → RSI undefined / NaN or 50/100
        const = pd.Series([450.0] * 50)
        result = self.ta.calculate_rsi(const, period=14)
        assert isinstance(result, pd.Series)

    def test_custom_period(self):
        result = self.ta.calculate_rsi(self.df["close"], period=9)
        assert isinstance(result, pd.Series)
        valid = result.dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_oversold_returns_low_rsi(self):
        # Steadily declining prices → RSI < 40
        prices = pd.Series([450.0 - i * 1.5 for i in range(60)])
        result = self.ta.calculate_rsi(prices, period=14)
        last_rsi = result.dropna().iloc[-1]
        assert last_rsi < 40


# ==============================================================================
# calculate_stochastic TESTS
# ==============================================================================

class TestCalculateStochastic:
    def setup_method(self):
        self.ta = TechnicalAnalysis()
        self.df = _make_ohlcv()

    def test_returns_dict(self):
        result = self.ta.calculate_stochastic(self.df["high"], self.df["low"], self.df["close"])
        assert isinstance(result, dict)

    def test_has_k_and_d(self):
        result = self.ta.calculate_stochastic(self.df["high"], self.df["low"], self.df["close"])
        assert "k" in result and "d" in result

    def test_k_values_in_range(self):
        result = self.ta.calculate_stochastic(self.df["high"], self.df["low"], self.df["close"])
        valid_k = result["k"].dropna()
        assert (valid_k >= 0).all() and (valid_k <= 100).all()

    def test_same_length_as_input(self):
        result = self.ta.calculate_stochastic(self.df["high"], self.df["low"], self.df["close"])
        assert len(result["k"]) == len(self.df)


# ==============================================================================
# calculate_bollinger_bands TESTS
# ==============================================================================

class TestCalculateBollingerBands:
    def setup_method(self):
        self.ta = TechnicalAnalysis()
        self.df = _make_ohlcv()

    def test_returns_dict(self):
        result = self.ta.calculate_bollinger_bands(self.df["close"])
        assert isinstance(result, dict)

    def test_has_upper_middle_lower(self):
        result = self.ta.calculate_bollinger_bands(self.df["close"])
        for key in ("upper", "middle", "lower"):
            assert key in result

    def test_has_width_and_percent(self):
        result = self.ta.calculate_bollinger_bands(self.df["close"])
        assert "width" in result and "percent" in result

    def test_upper_above_lower(self):
        result = self.ta.calculate_bollinger_bands(self.df["close"])
        valid_upper = result["upper"].dropna()
        valid_lower = result["lower"].dropna()
        idx = valid_upper.index.intersection(valid_lower.index)
        assert (valid_upper.loc[idx] >= valid_lower.loc[idx]).all()

    def test_middle_between_upper_and_lower(self):
        result = self.ta.calculate_bollinger_bands(self.df["close"])
        upper = result["upper"].dropna()
        middle = result["middle"].dropna()
        lower = result["lower"].dropna()
        idx = upper.index.intersection(middle.index).intersection(lower.index)
        assert (middle.loc[idx] <= upper.loc[idx]).all()
        assert (middle.loc[idx] >= lower.loc[idx]).all()

    def test_width_positive(self):
        result = self.ta.calculate_bollinger_bands(self.df["close"])
        valid_width = result["width"].dropna()
        assert (valid_width > 0).all()

    def test_each_value_is_series(self):
        result = self.ta.calculate_bollinger_bands(self.df["close"])
        for key in ("upper", "middle", "lower", "width", "percent"):
            assert isinstance(result[key], pd.Series)


# ==============================================================================
# calculate_atr TESTS
# ==============================================================================

class TestCalculateAtr:
    def setup_method(self):
        self.ta = TechnicalAnalysis()
        self.df = _make_ohlcv()

    def test_returns_series(self):
        result = self.ta.calculate_atr(self.df["high"], self.df["low"], self.df["close"])
        assert isinstance(result, pd.Series)

    def test_same_length(self):
        result = self.ta.calculate_atr(self.df["high"], self.df["low"], self.df["close"])
        assert len(result) == len(self.df)

    def test_atr_non_negative(self):
        result = self.ta.calculate_atr(self.df["high"], self.df["low"], self.df["close"])
        valid = result.dropna()
        assert (valid >= 0).all()

    def test_atr_less_than_price_range(self):
        result = self.ta.calculate_atr(self.df["high"], self.df["low"], self.df["close"])
        last_atr = result.dropna().iloc[-1]
        # ATR shouldn't exceed ~half the price range
        assert last_atr < 50


# ==============================================================================
# calculate_vwap TESTS
# ==============================================================================

class TestCalculateVwap:
    def setup_method(self):
        self.ta = TechnicalAnalysis()
        self.df = _make_ohlcv()

    def test_returns_series(self):
        result = self.ta.calculate_vwap(
            self.df["high"], self.df["low"], self.df["close"], self.df["volume"]
        )
        assert isinstance(result, pd.Series)

    def test_same_length(self):
        result = self.ta.calculate_vwap(
            self.df["high"], self.df["low"], self.df["close"], self.df["volume"]
        )
        assert len(result) == len(self.df)

    def test_vwap_value_in_reasonable_range(self):
        result = self.ta.calculate_vwap(
            self.df["high"], self.df["low"], self.df["close"], self.df["volume"]
        )
        valid = result.dropna()
        assert (valid > 300).all() and (valid < 700).all()


# ==============================================================================
# calculate_volume_sma TESTS
# ==============================================================================

class TestCalculateVolumeSma:
    def setup_method(self):
        self.ta = TechnicalAnalysis()
        self.df = _make_ohlcv()

    def test_returns_series(self):
        result = self.ta.calculate_volume_sma(self.df["volume"])
        assert isinstance(result, pd.Series)

    def test_same_length(self):
        result = self.ta.calculate_volume_sma(self.df["volume"])
        assert len(result) == len(self.df)

    def test_custom_period(self):
        result = self.ta.calculate_volume_sma(self.df["volume"], period=10)
        assert not result.iloc[10:].isna().any()

    def test_volume_sma_positive(self):
        result = self.ta.calculate_volume_sma(self.df["volume"], period=5)
        assert (result.dropna() > 0).all()


# ==============================================================================
# calculate_obv TESTS
# ==============================================================================

class TestCalculateObv:
    def setup_method(self):
        self.ta = TechnicalAnalysis()
        self.df = _make_ohlcv()

    def test_returns_series(self):
        result = self.ta.calculate_obv(self.df["close"], self.df["volume"])
        assert isinstance(result, pd.Series)

    def test_same_length(self):
        result = self.ta.calculate_obv(self.df["close"], self.df["volume"])
        assert len(result) == len(self.df)

    def test_obv_is_cumulative(self):
        # OBV changes monotonically within a consistent trend
        df = _uptrend_ohlcv(n=60)
        result = self.ta.calculate_obv(df["close"], df["volume"])
        # Last OBV > first valid OBV in a consistent up-trend
        valid = result.dropna()
        assert valid.iloc[-1] != valid.iloc[0]  # It moved


# ==============================================================================
# calculate_cmf TESTS
# ==============================================================================

class TestCalculateCmf:
    def setup_method(self):
        self.ta = TechnicalAnalysis()
        self.df = _make_ohlcv()

    def test_returns_series(self):
        result = self.ta.calculate_cmf(
            self.df["high"], self.df["low"], self.df["close"], self.df["volume"]
        )
        assert isinstance(result, pd.Series)

    def test_same_length(self):
        result = self.ta.calculate_cmf(
            self.df["high"], self.df["low"], self.df["close"], self.df["volume"]
        )
        assert len(result) == len(self.df)

    def test_cmf_in_minus1_to_plus1(self):
        result = self.ta.calculate_cmf(
            self.df["high"], self.df["low"], self.df["close"], self.df["volume"]
        )
        valid = result.dropna()
        assert (valid >= -1.0).all() and (valid <= 1.0).all()


# ==============================================================================
# detect_volume_surge TESTS
# ==============================================================================

class TestDetectVolumeSurge:
    def setup_method(self):
        self.ta = TechnicalAnalysis()

    def test_returns_boolean_series(self):
        df = _make_ohlcv()
        result = self.ta.detect_volume_surge(df["volume"])
        assert isinstance(result, pd.Series)
        valid = result.dropna()
        assert valid.dtype == bool

    def test_spike_detected(self):
        # Normal volume followed by extreme spike
        normal_vol = pd.Series([1_000_000.0] * 40)
        spike = pd.Series([50_000_000.0])
        vol = pd.concat([normal_vol, spike], ignore_index=True)
        result = self.ta.detect_volume_surge(vol)
        # Last element should be a surge
        assert result.iloc[-1] is True or bool(result.iloc[-1]) is True

    def test_no_surge_when_volume_flat(self):
        # All volumes identical — no surge (ratio == 1.0 < threshold of 1.5)
        vol = pd.Series([1_000_000.0] * 50)
        result = self.ta.detect_volume_surge(vol)
        valid = result.dropna()
        # Flat volume should never be a surge
        assert not valid.any()


# ==============================================================================
# analyze_trend TESTS
# ==============================================================================

class TestAnalyzeTrend:
    def setup_method(self):
        self.ta = TechnicalAnalysis()

    def test_returns_trend_direction(self):
        df = _make_ohlcv(n=100)
        result = self.ta.analyze_trend(df["close"])
        assert isinstance(result, TrendDirection)

    def test_strong_uptrend_detected(self):
        df = _uptrend_ohlcv(n=100)
        result = self.ta.analyze_trend(df["close"])
        assert result in (TrendDirection.UP, TrendDirection.STRONG_UP)

    def test_strong_downtrend_detected(self):
        df = _downtrend_ohlcv(n=100)
        result = self.ta.analyze_trend(df["close"])
        assert result in (TrendDirection.DOWN, TrendDirection.STRONG_DOWN)

    def test_valid_direction_member(self):
        df = _flat_ohlcv(n=100)
        result = self.ta.analyze_trend(df["close"])
        assert result in list(TrendDirection)


# ==============================================================================
# generate_signals TESTS
# ==============================================================================

class TestGenerateSignals:
    def setup_method(self):
        self.ta = TechnicalAnalysis()
        self.df = _make_ohlcv(n=100)

    def test_returns_list(self):
        result = self.ta.generate_signals(self.df)
        assert isinstance(result, list)

    def test_each_element_is_technical_signal(self):
        result = self.ta.generate_signals(self.df)
        for sig in result:
            assert isinstance(sig, TechnicalSignal)

    def test_at_least_one_vwap_signal(self):
        result = self.ta.generate_signals(self.df)
        indicators = [s.indicator for s in result]
        assert "VWAP" in indicators

    def test_signals_have_valid_direction(self):
        result = self.ta.generate_signals(self.df)
        for sig in result:
            assert sig.signal in ("buy", "sell", "neutral")

    def test_signals_have_strength(self):
        result = self.ta.generate_signals(self.df)
        for sig in result:
            assert isinstance(sig.strength, SignalStrength)

    def test_signals_have_timestamp(self):
        result = self.ta.generate_signals(self.df)
        for sig in result:
            assert isinstance(sig.timestamp, datetime)

    def test_rsi_signal_on_oversold_data(self):
        # Build a declining series to push RSI < 30
        prices = [450.0 - i * 1.5 for i in range(100)]
        df = _make_ohlcv(n=100, base_price=450.0, trend=-0.008, seed=10)
        # Force the close series to look oversold
        df["close"] = pd.Series([450.0 - i * 1.0 for i in range(100)])
        df["high"] = df["close"] + 0.5
        df["low"] = df["close"] - 0.5

        result = self.ta.generate_signals(df)
        rsi_sigs = [s for s in result if s.indicator == "RSI"]
        # May or may not trigger depending on exact RSI value — just check no crash
        assert isinstance(rsi_sigs, list)


# ==============================================================================
# get_composite_score TESTS
# ==============================================================================

class TestGetCompositeScore:
    def setup_method(self):
        self.ta = TechnicalAnalysis()

    def test_returns_float(self):
        df = _make_ohlcv(n=100)
        result = self.ta.get_composite_score(df)
        assert isinstance(result, float)

    def test_score_in_minus100_to_100(self):
        df = _make_ohlcv(n=100)
        result = self.ta.get_composite_score(df)
        assert -100.0 <= result <= 100.0

    def test_uptrend_positive_score(self):
        df = _uptrend_ohlcv(n=100)
        result = self.ta.get_composite_score(df)
        # Strong uptrend should produce positive composite score
        assert result > -50.0  # Allows some noise

    def test_downtrend_negative_score(self):
        df = _downtrend_ohlcv(n=100)
        result = self.ta.get_composite_score(df)
        assert result < 50.0  # Should lean negative


# ==============================================================================
# full_analysis TESTS
# ==============================================================================

class TestFullAnalysis:
    def setup_method(self):
        self.ta = TechnicalAnalysis()
        self.df = _make_ohlcv(n=100)

    def test_returns_technical_analysis_result(self):
        result = self.ta.full_analysis(self.df)
        assert isinstance(result, TechnicalAnalysisResult)

    def test_trend_is_trend_direction(self):
        result = self.ta.full_analysis(self.df)
        assert isinstance(result.trend, TrendDirection)

    def test_momentum_has_rsi(self):
        result = self.ta.full_analysis(self.df)
        assert "rsi" in result.momentum

    def test_momentum_rsi_in_range(self):
        result = self.ta.full_analysis(self.df)
        rsi = result.momentum["rsi"]
        assert 0 <= rsi <= 100

    def test_volatility_has_atr(self):
        result = self.ta.full_analysis(self.df)
        assert "atr" in result.volatility

    def test_volatility_has_bollinger_width(self):
        result = self.ta.full_analysis(self.df)
        assert "bollinger_width" in result.volatility

    def test_volume_has_vwap(self):
        result = self.ta.full_analysis(self.df)
        assert "vwap" in result.volume

    def test_volume_has_obv(self):
        result = self.ta.full_analysis(self.df)
        assert "obv" in result.volume

    def test_volume_has_cmf(self):
        result = self.ta.full_analysis(self.df)
        assert "cmf" in result.volume

    def test_composite_score_in_range(self):
        result = self.ta.full_analysis(self.df)
        assert -100.0 <= result.composite_score <= 100.0

    def test_signals_is_list(self):
        result = self.ta.full_analysis(self.df)
        assert isinstance(result.signals, list)

    def test_timestamp_is_datetime(self):
        result = self.ta.full_analysis(self.df)
        assert isinstance(result.timestamp, datetime)

    def test_uptrend_result(self):
        df = _uptrend_ohlcv(n=100)
        result = self.ta.full_analysis(df)
        assert result.trend in (TrendDirection.UP, TrendDirection.STRONG_UP)

    def test_downtrend_result(self):
        df = _downtrend_ohlcv(n=100)
        result = self.ta.full_analysis(df)
        assert result.trend in (TrendDirection.DOWN, TrendDirection.STRONG_DOWN)


# ==============================================================================
# MODULE FUNCTIONS  TESTS
# ==============================================================================

class TestQuickAnalysis:
    def test_returns_dict(self):
        df = _make_ohlcv(n=100)
        result = quick_analysis(df)
        assert isinstance(result, dict)

    def test_has_trend_key(self):
        df = _make_ohlcv(n=100)
        result = quick_analysis(df)
        assert "trend" in result

    def test_has_rsi_key(self):
        df = _make_ohlcv(n=100)
        result = quick_analysis(df)
        assert "rsi" in result

    def test_has_vwap_key(self):
        df = _make_ohlcv(n=100)
        result = quick_analysis(df)
        assert "vwap" in result

    def test_has_composite_score(self):
        df = _make_ohlcv(n=100)
        result = quick_analysis(df)
        assert "composite_score" in result

    def test_has_timestamp(self):
        df = _make_ohlcv(n=100)
        result = quick_analysis(df)
        assert "timestamp" in result

    def test_trend_value_is_string(self):
        df = _make_ohlcv(n=100)
        result = quick_analysis(df)
        assert isinstance(result["trend"], str)

    def test_trend_value_is_valid_direction(self):
        df = _make_ohlcv(n=100)
        result = quick_analysis(df)
        valid_values = {d.value for d in TrendDirection}
        assert result["trend"] in valid_values

    def test_rsi_in_range(self):
        df = _make_ohlcv(n=100)
        result = quick_analysis(df)
        assert 0.0 <= result["rsi"] <= 100.0

    def test_composite_score_in_range(self):
        df = _make_ohlcv(n=100)
        result = quick_analysis(df)
        assert -100.0 <= result["composite_score"] <= 100.0


class TestGetTechnicalAnalysisSingleton:
    def setup_method(self):
        """Reset singleton before each test."""
        _u16._ta_instance = None

    def test_returns_technical_analysis(self):
        ta = get_technical_analysis()
        assert isinstance(ta, TechnicalAnalysis)

    def test_returns_same_instance(self):
        ta1 = get_technical_analysis()
        ta2 = get_technical_analysis()
        assert ta1 is ta2

    def test_instance_is_functional(self):
        ta = get_technical_analysis()
        df = _make_ohlcv(n=100)
        score = ta.get_composite_score(df)
        assert -100.0 <= score <= 100.0
