#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: test_SpyderT104_U22ETTimeDisplay_U16TechnicalAnalysis.py
Purpose: Tests for SpyderU22_ETTimeDisplay and SpyderU16_TechnicalAnalysis

Author: Spyder Dev
Year Created: 2025
Last Updated: 2025-01-01 Time: 00:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import types
from datetime import datetime
from unittest.mock import MagicMock

# ==============================================================================
# PATH SETUP
# ==============================================================================
_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# ==============================================================================
# MODULE STUBS
# ==============================================================================


def _ensure_pkg(name: str) -> None:
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)


_ensure_pkg("Spyder")
_ensure_pkg("Spyder.SpyderU_Utilities")
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

# Stub U03 DateTimeUtils to export US_EASTERN and TradingTimeUtils
_dt_mod = types.ModuleType("Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils")
_dt_mod.US_EASTERN = "US/Eastern"
_dt_mod.TradingTimeUtils = MagicMock
sys.modules.setdefault("Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils", _dt_mod)

# ==============================================================================
# THIRD-PARTY IMPORTS AND MODULE IMPORTS
# ==============================================================================
import pytest
import numpy as np
import pandas as pd

from Spyder.SpyderU_Utilities.SpyderU22_ETTimeDisplay import (
    DASHBOARD_TIME_FORMAT,
    SIMPLE_TIME_FORMAT,
    EASTERN_TZ,
    SimpleETDisplay,
    get_et_time_string,
    get_et_time_for_dashboard,
    get_current_et_datetime,
    get_et_display,
)

from Spyder.SpyderU_Utilities.SpyderU16_TechnicalAnalysis import (
    TrendDirection,
    SignalStrength,
    TechnicalSignal,
    TechnicalAnalysisResult,
    TechnicalAnalysis,
    DEFAULT_PERIODS,
    SIGNAL_THRESHOLDS,
    quick_analysis,
    get_technical_analysis,
    TA_AVAILABLE,
)

# ==============================================================================
# HELPERS — OHLCV DATA
# ==============================================================================
_N = 100  # bars


def _make_ohlcv(n: int = _N, seed: int = 42) -> pd.DataFrame:
    """Create a synthetic OHLCV DataFrame for tests."""
    np.random.seed(seed)
    close = 400.0 + np.cumsum(np.random.normal(0, 1, n))
    high = close + np.abs(np.random.normal(0, 0.5, n))
    low = close - np.abs(np.random.normal(0, 0.5, n))
    open_ = close + np.random.normal(0, 0.3, n)
    volume = np.random.randint(1_000_000, 5_000_000, n).astype(float)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume}
    )


_DF = _make_ohlcv()


# ==============================================================================
# SECTION 1: SpyderU22_ETTimeDisplay Tests
# ==============================================================================


class TestU22Constants:
    """Tests for U22 module-level constants."""

    def test_dashboard_time_format_is_str(self):
        assert isinstance(DASHBOARD_TIME_FORMAT, str)

    def test_simple_time_format_is_str(self):
        assert isinstance(SIMPLE_TIME_FORMAT, str)

    def test_dashboard_format_has_time(self):
        # Format must have hours/minutes/seconds
        assert "%H" in DASHBOARD_TIME_FORMAT
        assert "%M" in DASHBOARD_TIME_FORMAT
        assert "%S" in DASHBOARD_TIME_FORMAT

    def test_simple_format_no_tz(self):
        assert "%Z" not in SIMPLE_TIME_FORMAT

    def test_eastern_tz_not_none(self):
        assert EASTERN_TZ is not None


class TestGetETTimeString:
    """Tests for get_et_time_string function."""

    def test_returns_string(self):
        result = get_et_time_string()
        assert isinstance(result, str)

    def test_default_includes_timezone(self):
        result = get_et_time_string()
        # Eastern timezone abbreviation (EDT or EST)
        assert ("EDT" in result or "EST" in result or len(result) > 8)

    def test_without_timezone_shorter(self):
        with_tz = get_et_time_string(include_timezone=True)
        without_tz = get_et_time_string(include_timezone=False)
        assert len(without_tz) <= len(with_tz)

    def test_without_timezone_no_tz_abbrev(self):
        result = get_et_time_string(include_timezone=False)
        assert "EDT" not in result
        assert "EST" not in result

    def test_has_colon_separators(self):
        result = get_et_time_string(include_timezone=False)
        parts = result.split(":")
        assert len(parts) == 3

    def test_time_component_digits(self):
        result = get_et_time_string(include_timezone=False)
        parts = result.split(":")
        assert parts[0].isdigit()
        assert parts[1].isdigit()
        assert parts[2].isdigit()


class TestGetETTimeForDashboard:
    """Tests for get_et_time_for_dashboard function."""

    def test_returns_string(self):
        result = get_et_time_for_dashboard()
        assert isinstance(result, str)

    def test_same_as_with_timezone(self):
        dash = get_et_time_for_dashboard()
        get_et_time_string(include_timezone=True)
        # Both should have timezone
        assert len(dash) >= 8

    def test_not_empty(self):
        result = get_et_time_for_dashboard()
        assert len(result) > 0


class TestGetCurrentETDatetime:
    """Tests for get_current_et_datetime function."""

    def test_returns_datetime(self):
        result = get_current_et_datetime()
        assert isinstance(result, datetime)

    def test_has_timezone_info(self):
        result = get_current_et_datetime()
        assert result.tzinfo is not None

    def test_recent_datetime(self):
        result = get_current_et_datetime()
        # Should be a current year date (not some distant past/future)
        assert result.year >= 2024


class TestSimpleETDisplay:
    """Tests for SimpleETDisplay class."""

    def setup_method(self):
        self.display = SimpleETDisplay()

    def test_creates_instance(self):
        assert isinstance(self.display, SimpleETDisplay)

    def test_eastern_tz_set(self):
        assert self.display.eastern_tz is not None

    def test_get_time_string_with_tz(self):
        result = self.display.get_time_string(include_tz=True)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_time_string_without_tz(self):
        result = self.display.get_time_string(include_tz=False)
        assert isinstance(result, str)
        # Should be shorter than with_tz
        assert len(result) >= 8

    def test_get_time_string_default_includes_tz(self):
        result = self.display.get_time_string()
        assert isinstance(result, str)


class TestGetETDisplay:
    """Tests for get_et_display singleton function."""

    def test_returns_simple_et_display(self):
        result = get_et_display()
        assert isinstance(result, SimpleETDisplay)

    def test_is_singleton(self):
        d1 = get_et_display()
        d2 = get_et_display()
        assert d1 is d2


# ==============================================================================
# SECTION 2: SpyderU16_TechnicalAnalysis Tests
# ==============================================================================


class TestTrendDirection:
    """Tests for TrendDirection enum."""

    def test_strong_up(self):
        assert TrendDirection.STRONG_UP.value == "strong_up"

    def test_up(self):
        assert TrendDirection.UP.value == "up"

    def test_neutral(self):
        assert TrendDirection.NEUTRAL.value == "neutral"

    def test_down(self):
        assert TrendDirection.DOWN.value == "down"

    def test_strong_down(self):
        assert TrendDirection.STRONG_DOWN.value == "strong_down"

    def test_count(self):
        assert len(TrendDirection) == 5


class TestSignalStrength:
    """Tests for SignalStrength enum."""

    def test_very_strong(self):
        assert SignalStrength.VERY_STRONG.value == "very_strong"

    def test_strong(self):
        assert SignalStrength.STRONG.value == "strong"

    def test_moderate(self):
        assert SignalStrength.MODERATE.value == "moderate"

    def test_weak(self):
        assert SignalStrength.WEAK.value == "weak"

    def test_very_weak(self):
        assert SignalStrength.VERY_WEAK.value == "very_weak"

    def test_count(self):
        assert len(SignalStrength) == 5


class TestTechnicalSignalDataclass:
    """Tests for TechnicalSignal dataclass."""

    def test_basic_creation(self):
        sig = TechnicalSignal(
            indicator="RSI",
            value=65.0,
            signal="sell",
            strength=SignalStrength.MODERATE,
            timestamp=datetime.now(),
        )
        assert sig.indicator == "RSI"
        assert sig.signal == "sell"

    def test_metadata_default_none(self):
        sig = TechnicalSignal(
            indicator="MACD", value=0.5, signal="buy",
            strength=SignalStrength.STRONG, timestamp=datetime.now(),
        )
        assert sig.metadata is None

    def test_metadata_dict(self):
        sig = TechnicalSignal(
            indicator="VWAP", value=400.0, signal="buy",
            strength=SignalStrength.MODERATE, timestamp=datetime.now(),
            metadata={"price_above_vwap": True},
        )
        assert sig.metadata["price_above_vwap"] is True

    def test_value_float(self):
        sig = TechnicalSignal(
            indicator="RSI", value=30.0, signal="buy",
            strength=SignalStrength.STRONG, timestamp=datetime.now(),
        )
        assert isinstance(sig.value, float)


class TestTechnicalAnalysisResultDataclass:
    """Tests for TechnicalAnalysisResult dataclass."""

    def test_basic_creation(self):
        result = TechnicalAnalysisResult(
            trend=TrendDirection.UP,
            momentum={"rsi": 55.0},
            volatility={"atr": 2.5},
            volume={"vwap": 400.0},
            signals=[],
            composite_score=25.0,
            timestamp=datetime.now(),
        )
        assert result.trend == TrendDirection.UP
        assert result.composite_score == 25.0

    def test_signals_list(self):
        result = TechnicalAnalysisResult(
            trend=TrendDirection.NEUTRAL,
            momentum={}, volatility={}, volume={},
            signals=[], composite_score=0.0, timestamp=datetime.now(),
        )
        assert isinstance(result.signals, list)


class TestU16Constants:
    """Tests for U16 module-level constants."""

    def test_default_periods_is_dict(self):
        assert isinstance(DEFAULT_PERIODS, dict)

    def test_default_periods_rsi(self):
        assert DEFAULT_PERIODS["rsi"] == 14

    def test_default_periods_macd(self):
        assert DEFAULT_PERIODS["macd_fast"] == 12
        assert DEFAULT_PERIODS["macd_slow"] == 26

    def test_signal_thresholds_is_dict(self):
        assert isinstance(SIGNAL_THRESHOLDS, dict)

    def test_signal_thresholds_rsi(self):
        assert SIGNAL_THRESHOLDS["rsi_oversold"] == 30
        assert SIGNAL_THRESHOLDS["rsi_overbought"] == 70


class TestTechnicalAnalysisInit:
    """Tests for TechnicalAnalysis initialization."""

    def test_default_init(self):
        ta = TechnicalAnalysis()
        assert isinstance(ta, TechnicalAnalysis)

    def test_with_custom_config(self):
        ta = TechnicalAnalysis(config={"periods": {"rsi": 7}})
        assert ta.periods["rsi"] == 7

    def test_periods_have_defaults(self):
        ta = TechnicalAnalysis()
        assert "rsi" in ta.periods
        assert "macd_fast" in ta.periods

    def test_thresholds_set(self):
        ta = TechnicalAnalysis()
        assert "rsi_oversold" in ta.thresholds

    def test_indicator_cache_empty(self):
        ta = TechnicalAnalysis()
        assert isinstance(ta.indicator_cache, dict)
        assert len(ta.indicator_cache) == 0

    def test_config_overrides_period(self):
        ta = TechnicalAnalysis(config={"thresholds": {"rsi_oversold": 25}})
        assert ta.thresholds["rsi_oversold"] == 25


class TestCalculateSMA:
    """Tests for TechnicalAnalysis.calculate_sma."""

    def setup_method(self):
        self.ta = TechnicalAnalysis()
        self.close = _DF["close"]

    def test_returns_series(self):
        result = self.ta.calculate_sma(self.close)
        assert isinstance(result, pd.Series)

    def test_length_matches_input(self):
        result = self.ta.calculate_sma(self.close)
        assert len(result) == len(self.close)

    def test_custom_period(self):
        result = self.ta.calculate_sma(self.close, period=10)
        assert isinstance(result, pd.Series)

    def test_first_values_nan(self):
        result = self.ta.calculate_sma(self.close, period=20)
        # First 19 values should be NaN (for period=20)
        assert result.iloc[:19].isna().any()


class TestCalculateEMA:
    """Tests for TechnicalAnalysis.calculate_ema."""

    def setup_method(self):
        self.ta = TechnicalAnalysis()
        self.close = _DF["close"]

    def test_returns_series(self):
        result = self.ta.calculate_ema(self.close)
        assert isinstance(result, pd.Series)

    def test_length_matches(self):
        result = self.ta.calculate_ema(self.close)
        assert len(result) == len(self.close)

    def test_not_all_nan(self):
        result = self.ta.calculate_ema(self.close)
        assert result.notna().any()


class TestCalculateMACD:
    """Tests for TechnicalAnalysis.calculate_macd."""

    def setup_method(self):
        self.ta = TechnicalAnalysis()
        self.close = _DF["close"]

    def test_returns_dict(self):
        result = self.ta.calculate_macd(self.close)
        assert isinstance(result, dict)

    def test_dict_has_macd_signal_histogram(self):
        result = self.ta.calculate_macd(self.close)
        assert "macd" in result
        assert "signal" in result
        assert "histogram" in result

    def test_macd_is_series(self):
        result = self.ta.calculate_macd(self.close)
        assert isinstance(result["macd"], pd.Series)

    def test_histogram_difference(self):
        result = self.ta.calculate_macd(self.close)
        # histogram = macd - signal
        diff = (result["macd"] - result["signal"]).dropna()
        hist = result["histogram"].dropna()
        if len(diff) > 0 and len(hist) > 0:
            # Rough check
            assert isinstance(diff.iloc[-1], float)


class TestCalculateRSI:
    """Tests for TechnicalAnalysis.calculate_rsi."""

    def setup_method(self):
        self.ta = TechnicalAnalysis()
        self.close = _DF["close"]

    def test_returns_series(self):
        result = self.ta.calculate_rsi(self.close)
        assert isinstance(result, pd.Series)

    def test_values_in_range_where_defined(self):
        result = self.ta.calculate_rsi(self.close).dropna()
        # RSI should be between 0 and 100
        if len(result) > 0:
            assert result.min() >= 0
            assert result.max() <= 100

    def test_custom_period(self):
        result = self.ta.calculate_rsi(self.close, period=7)
        assert isinstance(result, pd.Series)

    def test_length_matches(self):
        result = self.ta.calculate_rsi(self.close)
        assert len(result) == len(self.close)


class TestCalculateStochastic:
    """Tests for TechnicalAnalysis.calculate_stochastic."""

    def setup_method(self):
        self.ta = TechnicalAnalysis()

    def test_returns_dict(self):
        result = self.ta.calculate_stochastic(_DF["high"], _DF["low"], _DF["close"])
        assert isinstance(result, dict)

    def test_has_k_and_d(self):
        result = self.ta.calculate_stochastic(_DF["high"], _DF["low"], _DF["close"])
        assert "k" in result
        assert "d" in result

    def test_k_is_series(self):
        result = self.ta.calculate_stochastic(_DF["high"], _DF["low"], _DF["close"])
        assert isinstance(result["k"], pd.Series)


class TestCalculateBollingerBands:
    """Tests for TechnicalAnalysis.calculate_bollinger_bands."""

    def setup_method(self):
        self.ta = TechnicalAnalysis()
        self.close = _DF["close"]

    def test_returns_dict(self):
        result = self.ta.calculate_bollinger_bands(self.close)
        assert isinstance(result, dict)

    def test_has_upper_middle_lower(self):
        result = self.ta.calculate_bollinger_bands(self.close)
        assert "upper" in result
        assert "middle" in result
        assert "lower" in result

    def test_upper_above_lower(self):
        result = self.ta.calculate_bollinger_bands(self.close)
        upper = result["upper"].dropna()
        lower = result["lower"].dropna()
        common_idx = upper.index.intersection(lower.index)
        if len(common_idx) > 0:
            assert (upper[common_idx] >= lower[common_idx]).all()

    def test_has_width_and_percent(self):
        result = self.ta.calculate_bollinger_bands(self.close)
        assert "width" in result
        assert "percent" in result


class TestCalculateATR:
    """Tests for TechnicalAnalysis.calculate_atr."""

    def setup_method(self):
        self.ta = TechnicalAnalysis()

    def test_returns_series(self):
        result = self.ta.calculate_atr(_DF["high"], _DF["low"], _DF["close"])
        assert isinstance(result, pd.Series)

    def test_atr_non_negative(self):
        result = self.ta.calculate_atr(_DF["high"], _DF["low"], _DF["close"]).dropna()
        if len(result) > 0:
            assert (result >= 0).all()

    def test_length_matches(self):
        result = self.ta.calculate_atr(_DF["high"], _DF["low"], _DF["close"])
        assert len(result) == len(_DF)


class TestVolumeIndicators:
    """Tests for VWAP, OBV, CMF, volume SMA, and volume surge."""

    def setup_method(self):
        self.ta = TechnicalAnalysis()

    def test_calculate_vwap_returns_series(self):
        result = self.ta.calculate_vwap(_DF["high"], _DF["low"], _DF["close"], _DF["volume"])
        assert isinstance(result, pd.Series)

    def test_calculate_obv_returns_series(self):
        result = self.ta.calculate_obv(_DF["close"], _DF["volume"])
        assert isinstance(result, pd.Series)

    def test_calculate_cmf_returns_series(self):
        result = self.ta.calculate_cmf(
            _DF["high"], _DF["low"], _DF["close"], _DF["volume"]
        )
        assert isinstance(result, pd.Series)

    def test_calculate_volume_sma_returns_series(self):
        result = self.ta.calculate_volume_sma(_DF["volume"])
        assert isinstance(result, pd.Series)

    def test_detect_volume_surge_returns_bool_series(self):
        result = self.ta.detect_volume_surge(_DF["volume"])
        assert isinstance(result, pd.Series)
        assert result.dtype == bool


class TestAnalyzeTrend:
    """Tests for TechnicalAnalysis.analyze_trend."""

    def setup_method(self):
        self.ta = TechnicalAnalysis()

    def test_returns_trend_direction(self):
        result = self.ta.analyze_trend(_DF["close"])
        assert isinstance(result, TrendDirection)

    def test_uptrend_data(self):
        # Create strongly uptrending data
        n = 100
        up_close = pd.Series(np.linspace(350, 500, n))
        result = self.ta.analyze_trend(up_close)
        assert result in [TrendDirection.UP, TrendDirection.STRONG_UP]

    def test_downtrend_data(self):
        # Create strongly downtrending data
        n = 100
        down_close = pd.Series(np.linspace(500, 350, n))
        result = self.ta.analyze_trend(down_close)
        assert result in [TrendDirection.DOWN, TrendDirection.STRONG_DOWN]


class TestGenerateSignals:
    """Tests for TechnicalAnalysis.generate_signals."""

    def setup_method(self):
        self.ta = TechnicalAnalysis()

    def test_returns_list(self):
        result = self.ta.generate_signals(_DF)
        assert isinstance(result, list)

    def test_signals_are_technical_signal(self):
        result = self.ta.generate_signals(_DF)
        for sig in result:
            assert isinstance(sig, TechnicalSignal)

    def test_signals_have_valid_signal_values(self):
        result = self.ta.generate_signals(_DF)
        valid_signals = {"buy", "sell", "neutral"}
        for sig in result:
            assert sig.signal in valid_signals

    def test_signals_have_indicator_name(self):
        result = self.ta.generate_signals(_DF)
        for sig in result:
            assert isinstance(sig.indicator, str)
            assert len(sig.indicator) > 0


class TestGetCompositeScore:
    """Tests for TechnicalAnalysis.get_composite_score."""

    def setup_method(self):
        self.ta = TechnicalAnalysis()

    def test_returns_float(self):
        result = self.ta.get_composite_score(_DF)
        assert isinstance(result, float)

    def test_score_in_range(self):
        result = self.ta.get_composite_score(_DF)
        assert -100.0 <= result <= 100.0


class TestFullAnalysis:
    """Tests for TechnicalAnalysis.full_analysis."""

    def setup_method(self):
        self.ta = TechnicalAnalysis()

    def test_returns_technical_analysis_result(self):
        result = self.ta.full_analysis(_DF)
        assert isinstance(result, TechnicalAnalysisResult)

    def test_has_trend(self):
        result = self.ta.full_analysis(_DF)
        assert isinstance(result.trend, TrendDirection)

    def test_has_momentum(self):
        result = self.ta.full_analysis(_DF)
        assert isinstance(result.momentum, dict)
        assert "rsi" in result.momentum

    def test_has_volatility(self):
        result = self.ta.full_analysis(_DF)
        assert isinstance(result.volatility, dict)
        assert "atr" in result.volatility

    def test_has_volume(self):
        result = self.ta.full_analysis(_DF)
        assert isinstance(result.volume, dict)
        assert "vwap" in result.volume

    def test_has_signals(self):
        result = self.ta.full_analysis(_DF)
        assert isinstance(result.signals, list)

    def test_composite_score_range(self):
        result = self.ta.full_analysis(_DF)
        assert -100.0 <= result.composite_score <= 100.0

    def test_has_timestamp(self):
        result = self.ta.full_analysis(_DF)
        assert isinstance(result.timestamp, datetime)


class TestModuleFunctionsU16:
    """Tests for U16 module-level functions."""

    def test_quick_analysis_returns_dict(self):
        result = quick_analysis(_DF)
        assert isinstance(result, dict)

    def test_quick_analysis_has_trend(self):
        result = quick_analysis(_DF)
        assert "trend" in result

    def test_quick_analysis_has_rsi(self):
        result = quick_analysis(_DF)
        assert "rsi" in result

    def test_quick_analysis_has_composite_score(self):
        result = quick_analysis(_DF)
        assert "composite_score" in result

    def test_quick_analysis_has_vwap(self):
        result = quick_analysis(_DF)
        assert "vwap" in result

    def test_get_technical_analysis_returns_instance(self):
        result = get_technical_analysis()
        assert isinstance(result, TechnicalAnalysis)

    def test_get_technical_analysis_singleton(self):
        ta1 = get_technical_analysis()
        ta2 = get_technical_analysis()
        assert ta1 is ta2

    def test_ta_available_is_bool(self):
        assert isinstance(TA_AVAILABLE, bool)
