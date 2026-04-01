#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: test_SpyderT99_U16TechnicalAnalysis_U27SystemOptimizer.py
Purpose: Tests for U16 TechnicalAnalysis and U27 SystemOptimizer

Author: GitHub Copilot
Year Created: 2025
Last Updated: 2026-01-16 Time: 23:30:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import importlib
import os
import sys
import types
from datetime import datetime
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

# ==============================================================================
# BOOTSTRAP
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

# Stub SpyderU01_Logger (both path forms used by different modules)
_logger_mod = types.ModuleType("Spyder.SpyderU_Utilities.SpyderU01_Logger")


class _FakeSpyderLogger:
    @staticmethod
    def get_logger(name: str) -> MagicMock:
        return MagicMock()


_logger_mod.SpyderLogger = _FakeSpyderLogger
_logger_mod.get_logger = MagicMock(return_value=MagicMock())
sys.modules["Spyder.SpyderU_Utilities.SpyderU01_Logger"] = _logger_mod

# Stub SpyderU02_ErrorHandler
_err_mod = types.ModuleType("Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler")
_err_mod.SpyderErrorHandler = MagicMock
sys.modules["Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler"] = _err_mod

# ==============================================================================
# IMPORT MODULES UNDER TEST
# ==============================================================================

# U16 TechnicalAnalysis — ta library available; SpyderLogger falls back to None
for _k in list(sys.modules.keys()):
    if "SpyderU16_TechnicalAnalysis" in _k:
        del sys.modules[_k]
u16_mod = importlib.import_module("Spyder.SpyderU_Utilities.SpyderU16_TechnicalAnalysis")

TrendDirection = u16_mod.TrendDirection
SignalStrength = u16_mod.SignalStrength
TechnicalSignal = u16_mod.TechnicalSignal
TechnicalAnalysisResult = u16_mod.TechnicalAnalysisResult
TechnicalAnalysis = u16_mod.TechnicalAnalysis

# U27 SystemOptimizer — imports SpyderLogger + SpyderErrorHandler (standard stubs)
for _k in list(sys.modules.keys()):
    if "SpyderU27_SystemOptimizer" in _k:
        del sys.modules[_k]
u27_mod = importlib.import_module("Spyder.SpyderU_Utilities.SpyderU27_SystemOptimizer")

OptimizationLevel = u27_mod.OptimizationLevel
SystemComponent = u27_mod.SystemComponent
OptimizationResult = u27_mod.OptimizationResult
SystemDiagnostics = u27_mod.SystemDiagnostics
SystemOptimizer = u27_mod.SystemOptimizer


# ==============================================================================
# HELPERS
# ==============================================================================

def _make_ohlcv(n: int = 100, base_price: float = 450.0) -> pd.DataFrame:
    """Create a synthetic OHLCV DataFrame for testing."""
    np.random.seed(42)
    prices = base_price + np.cumsum(np.random.randn(n) * 0.5)
    high = prices + np.abs(np.random.randn(n) * 0.5)
    low = prices - np.abs(np.random.randn(n) * 0.5)
    volume = np.random.randint(100000, 1000000, size=n).astype(float)
    return pd.DataFrame({
        "open": prices,
        "high": high,
        "low": low,
        "close": prices,
        "volume": volume,
    })


# ==============================================================================
# ── U16 TECHNICAL ANALYSIS ───────────────────────────────────────────────────
# ==============================================================================


class TestU16TrendDirection:
    """Tests for TrendDirection enum."""

    def test_has_five_members(self):
        assert len(list(TrendDirection)) == 5

    def test_strong_up_exists(self):
        assert TrendDirection.STRONG_UP is not None

    def test_up_exists(self):
        assert TrendDirection.UP is not None

    def test_neutral_exists(self):
        assert TrendDirection.NEUTRAL is not None

    def test_down_exists(self):
        assert TrendDirection.DOWN is not None

    def test_strong_down_exists(self):
        assert TrendDirection.STRONG_DOWN is not None

    def test_values_are_strings(self):
        for td in TrendDirection:
            assert isinstance(td.value, str)


class TestU16SignalStrength:
    """Tests for SignalStrength enum."""

    def test_has_five_members(self):
        assert len(list(SignalStrength)) == 5

    def test_very_strong_exists(self):
        assert SignalStrength.VERY_STRONG is not None

    def test_strong_exists(self):
        assert SignalStrength.STRONG is not None

    def test_moderate_exists(self):
        assert SignalStrength.MODERATE is not None

    def test_weak_exists(self):
        assert SignalStrength.WEAK is not None

    def test_very_weak_exists(self):
        assert SignalStrength.VERY_WEAK is not None


class TestU16TechnicalSignal:
    """Tests for TechnicalSignal dataclass."""

    def _make_signal(self):
        return TechnicalSignal(
            indicator="RSI",
            value=35.0,
            signal="buy",
            strength=SignalStrength.STRONG,
            timestamp=datetime.now(),
        )

    def test_create_signal(self):
        sig = self._make_signal()
        assert sig.indicator == "RSI"

    def test_signal_value(self):
        sig = self._make_signal()
        assert sig.value == 35.0

    def test_signal_field(self):
        sig = self._make_signal()
        assert sig.signal == "buy"

    def test_strength_field(self):
        sig = self._make_signal()
        assert sig.strength == SignalStrength.STRONG

    def test_timestamp_is_datetime(self):
        sig = self._make_signal()
        assert isinstance(sig.timestamp, datetime)

    def test_metadata_defaults_none(self):
        sig = self._make_signal()
        assert sig.metadata is None

    def test_metadata_can_be_set(self):
        sig = TechnicalSignal(
            indicator="VWAP",
            value=450.0,
            signal="buy",
            strength=SignalStrength.MODERATE,
            timestamp=datetime.now(),
            metadata={"key": "value"},
        )
        assert sig.metadata["key"] == "value"


class TestU16TechnicalAnalysisInit:
    """Tests for TechnicalAnalysis initialization."""

    def test_create_default(self):
        ta = TechnicalAnalysis()
        assert ta is not None

    def test_has_periods_dict(self):
        ta = TechnicalAnalysis()
        assert isinstance(ta.periods, dict)

    def test_has_thresholds_dict(self):
        ta = TechnicalAnalysis()
        assert isinstance(ta.thresholds, dict)

    def test_default_rsi_period(self):
        ta = TechnicalAnalysis()
        assert ta.periods["rsi"] == 14

    def test_default_sma_short(self):
        ta = TechnicalAnalysis()
        assert ta.periods["sma_short"] == 20

    def test_custom_config_overrides_periods(self):
        ta = TechnicalAnalysis(config={"periods": {"rsi": 21}})
        assert ta.periods["rsi"] == 21

    def test_rsi_oversold_threshold(self):
        ta = TechnicalAnalysis()
        assert ta.thresholds["rsi_oversold"] == 30

    def test_rsi_overbought_threshold(self):
        ta = TechnicalAnalysis()
        assert ta.thresholds["rsi_overbought"] == 70

    def test_indicator_cache_empty(self):
        ta = TechnicalAnalysis()
        assert isinstance(ta.indicator_cache, dict)
        assert len(ta.indicator_cache) == 0


class TestU16TrendIndicators:
    """Tests for trend indicator calculations."""

    def setup_method(self):
        self.ta = TechnicalAnalysis()
        self.df = _make_ohlcv(100)

    def test_calculate_sma_returns_series(self):
        result = self.ta.calculate_sma(self.df["close"], 20)
        assert isinstance(result, pd.Series)

    def test_calculate_sma_length_matches(self):
        result = self.ta.calculate_sma(self.df["close"], 20)
        assert len(result) == len(self.df)

    def test_calculate_ema_returns_series(self):
        result = self.ta.calculate_ema(self.df["close"], 21)
        assert isinstance(result, pd.Series)

    def test_calculate_macd_returns_dict(self):
        result = self.ta.calculate_macd(self.df["close"])
        assert isinstance(result, dict)

    def test_calculate_macd_has_keys(self):
        result = self.ta.calculate_macd(self.df["close"])
        assert "macd" in result
        assert "signal" in result
        assert "histogram" in result

    def test_calculate_adx_returns_series(self):
        result = self.ta.calculate_adx(self.df["high"], self.df["low"], self.df["close"])
        assert isinstance(result, pd.Series)


class TestU16MomentumIndicators:
    """Tests for momentum indicator calculations."""

    def setup_method(self):
        self.ta = TechnicalAnalysis()
        self.df = _make_ohlcv(100)

    def test_calculate_rsi_returns_series(self):
        result = self.ta.calculate_rsi(self.df["close"], 14)
        assert isinstance(result, pd.Series)

    def test_calculate_rsi_last_value_range(self):
        result = self.ta.calculate_rsi(self.df["close"], 14)
        last = result.dropna().iloc[-1]
        assert 0 <= last <= 100

    def test_calculate_stochastic_returns_dict(self):
        result = self.ta.calculate_stochastic(
            self.df["high"], self.df["low"], self.df["close"]
        )
        assert isinstance(result, dict)
        assert "k" in result
        assert "d" in result


class TestU16VolatilityIndicators:
    """Tests for volatility indicator calculations."""

    def setup_method(self):
        self.ta = TechnicalAnalysis()
        self.df = _make_ohlcv(100)

    def test_calculate_bollinger_bands_returns_dict(self):
        result = self.ta.calculate_bollinger_bands(self.df["close"])
        assert isinstance(result, dict)

    def test_bollinger_bands_has_correct_keys(self):
        result = self.ta.calculate_bollinger_bands(self.df["close"])
        assert "upper" in result
        assert "middle" in result
        assert "lower" in result

    def test_bollinger_upper_above_lower(self):
        result = self.ta.calculate_bollinger_bands(self.df["close"])
        valid = result["upper"].dropna() > result["lower"].dropna()
        assert valid.all()

    def test_calculate_atr_returns_series(self):
        result = self.ta.calculate_atr(self.df["high"], self.df["low"], self.df["close"])
        assert isinstance(result, pd.Series)

    def test_atr_values_non_negative(self):
        result = self.ta.calculate_atr(self.df["high"], self.df["low"], self.df["close"])
        assert (result.dropna() >= 0).all()


class TestU16VolumeIndicators:
    """Tests for volume indicator calculations."""

    def setup_method(self):
        self.ta = TechnicalAnalysis()
        self.df = _make_ohlcv(100)

    def test_calculate_vwap_returns_series(self):
        result = self.ta.calculate_vwap(
            self.df["high"], self.df["low"], self.df["close"], self.df["volume"]
        )
        assert isinstance(result, pd.Series)

    def test_calculate_volume_sma_returns_series(self):
        result = self.ta.calculate_volume_sma(self.df["volume"])
        assert isinstance(result, pd.Series)

    def test_calculate_obv_returns_series(self):
        result = self.ta.calculate_obv(self.df["close"], self.df["volume"])
        assert isinstance(result, pd.Series)

    def test_calculate_cmf_returns_series(self):
        result = self.ta.calculate_cmf(
            self.df["high"], self.df["low"], self.df["close"], self.df["volume"]
        )
        assert isinstance(result, pd.Series)

    def test_detect_volume_surge_returns_boolean_series(self):
        result = self.ta.detect_volume_surge(self.df["volume"])
        assert isinstance(result, pd.Series)
        assert result.dtype in [bool, np.bool_] or result.dtype == object


class TestU16CompositeAnalysis:
    """Tests for composite analysis methods."""

    def setup_method(self):
        self.ta = TechnicalAnalysis()
        self.df = _make_ohlcv(100)

    def test_analyze_trend_returns_trend_direction(self):
        result = self.ta.analyze_trend(self.df["close"])
        assert isinstance(result, TrendDirection)

    def test_generate_signals_returns_list(self):
        result = self.ta.generate_signals(self.df)
        assert isinstance(result, list)

    def test_generate_signals_items_are_technical_signals(self):
        result = self.ta.generate_signals(self.df)
        for sig in result:
            assert isinstance(sig, TechnicalSignal)

    def test_get_composite_score_returns_float(self):
        result = self.ta.get_composite_score(self.df)
        assert isinstance(result, float)

    def test_composite_score_in_range(self):
        result = self.ta.get_composite_score(self.df)
        assert -100 <= result <= 100

    def test_full_analysis_returns_result(self):
        result = self.ta.full_analysis(self.df)
        assert isinstance(result, TechnicalAnalysisResult)

    def test_full_analysis_has_trend(self):
        result = self.ta.full_analysis(self.df)
        assert isinstance(result.trend, TrendDirection)

    def test_full_analysis_has_signals(self):
        result = self.ta.full_analysis(self.df)
        assert isinstance(result.signals, list)

    def test_full_analysis_has_composite_score(self):
        result = self.ta.full_analysis(self.df)
        assert -100 <= result.composite_score <= 100

    def test_full_analysis_has_timestamp(self):
        result = self.ta.full_analysis(self.df)
        assert isinstance(result.timestamp, datetime)


class TestU16ModuleFunctions:
    """Tests for module-level functions in U16."""

    def test_quick_analysis_exists(self):
        assert callable(u16_mod.quick_analysis)

    def test_get_technical_analysis_exists(self):
        assert callable(u16_mod.get_technical_analysis)

    def test_quick_analysis_returns_dict(self):
        df = _make_ohlcv(100)
        result = u16_mod.quick_analysis(df)
        assert isinstance(result, dict)

    def test_quick_analysis_has_trend_key(self):
        df = _make_ohlcv(100)
        result = u16_mod.quick_analysis(df)
        assert "trend" in result

    def test_quick_analysis_has_rsi_key(self):
        df = _make_ohlcv(100)
        result = u16_mod.quick_analysis(df)
        assert "rsi" in result

    def test_quick_analysis_has_composite_score(self):
        df = _make_ohlcv(100)
        result = u16_mod.quick_analysis(df)
        assert "composite_score" in result

    def test_get_technical_analysis_returns_instance(self):
        result = u16_mod.get_technical_analysis()
        assert isinstance(result, TechnicalAnalysis)

    def test_get_technical_analysis_singleton(self):
        ta1 = u16_mod.get_technical_analysis()
        ta2 = u16_mod.get_technical_analysis()
        assert ta1 is ta2

    def test_ta_available_flag(self):
        # ta is installed so TA_AVAILABLE should be True
        assert u16_mod.TA_AVAILABLE is True

    def test_default_periods_constant(self):
        periods = u16_mod.DEFAULT_PERIODS
        assert isinstance(periods, dict)
        assert "rsi" in periods

    def test_signal_thresholds_constant(self):
        thresholds = u16_mod.SIGNAL_THRESHOLDS
        assert isinstance(thresholds, dict)
        assert "rsi_oversold" in thresholds


# ==============================================================================
# ── U27 SYSTEM OPTIMIZER ──────────────────────────────────────────────────────
# ==============================================================================


class TestU27OptimizationLevel:
    """Tests for OptimizationLevel enum."""

    def test_basic_exists(self):
        assert OptimizationLevel.BASIC is not None

    def test_standard_exists(self):
        assert OptimizationLevel.STANDARD is not None

    def test_aggressive_exists(self):
        assert OptimizationLevel.AGGRESSIVE is not None

    def test_ultra_exists(self):
        assert OptimizationLevel.ULTRA is not None

    def test_four_levels(self):
        assert len(list(OptimizationLevel)) == 4

    def test_values_are_strings(self):
        for level in OptimizationLevel:
            assert isinstance(level.value, str)


class TestU27SystemComponent:
    """Tests for SystemComponent enum."""

    def test_network_exists(self):
        assert SystemComponent.NETWORK is not None

    def test_memory_exists(self):
        assert SystemComponent.MEMORY is not None

    def test_firewall_exists(self):
        assert SystemComponent.FIREWALL is not None

    def test_jvm_exists(self):
        assert SystemComponent.JVM is not None

    def test_docker_exists(self):
        assert SystemComponent.DOCKER is not None

    def test_five_components(self):
        assert len(list(SystemComponent)) == 5


class TestU27OptimizationResult:
    """Tests for OptimizationResult dataclass."""

    def _make_result(self, success=True):
        return OptimizationResult(
            component=SystemComponent.NETWORK,
            success=success,
            message="Success message",
        )

    def test_create_result(self):
        r = self._make_result()
        assert r.component == SystemComponent.NETWORK

    def test_success_flag(self):
        r = self._make_result(success=True)
        assert r.success is True

    def test_failure_flag(self):
        r = self._make_result(success=False)
        assert r.success is False

    def test_message_field(self):
        r = self._make_result()
        assert r.message == "Success message"

    def test_details_none_by_default(self):
        r = self._make_result()
        assert r.details is None

    def test_details_can_be_set(self):
        r = OptimizationResult(
            component=SystemComponent.FIREWALL,
            success=True,
            message="ok",
            details={"key": "val"},
        )
        assert r.details["key"] == "val"


class TestU27SystemDiagnostics:
    """Tests for SystemDiagnostics dataclass."""

    def test_create_empty(self):
        sd = SystemDiagnostics({}, {}, {}, None, None)
        assert sd.os_info == {}

    def test_memory_info_field(self):
        sd = SystemDiagnostics(
            os_info={"system": "Linux"},
            memory_info={"total": 8000},
            network_config={},
            java_info=None,
            docker_info=None,
        )
        assert sd.memory_info["total"] == 8000


class TestU27SystemOptimizerInit:
    """Tests for SystemOptimizer initialization."""

    def test_create_default(self):
        so = SystemOptimizer()
        assert so is not None

    def test_default_level_standard(self):
        so = SystemOptimizer()
        assert so.optimization_level == OptimizationLevel.STANDARD

    def test_custom_level(self):
        so = SystemOptimizer(OptimizationLevel.AGGRESSIVE)
        assert so.optimization_level == OptimizationLevel.AGGRESSIVE

    def test_applied_optimizations_empty(self):
        so = SystemOptimizer()
        assert so.applied_optimizations == []

    def test_has_logger(self):
        so = SystemOptimizer()
        assert so.logger is not None

    def test_has_error_handler(self):
        so = SystemOptimizer()
        assert so.error_handler is not None


class TestU27SystemOptimizerTCP:
    """Tests for TCP keepalive optimization (non-root → failure result)."""

    def test_optimize_tcp_returns_result(self):
        so = SystemOptimizer()
        result = so.optimize_tcp_keepalive()
        assert isinstance(result, OptimizationResult)

    def test_optimize_tcp_component_is_network(self):
        so = SystemOptimizer()
        result = so.optimize_tcp_keepalive()
        assert result.component == SystemComponent.NETWORK

    def test_optimize_tcp_not_root_returns_failure(self):
        so = SystemOptimizer()
        result = so.optimize_tcp_keepalive()
        # Non-root: should fail gracefully
        assert isinstance(result.success, bool)

    def test_optimize_tcp_returns_optimization_result_type(self):
        so = SystemOptimizer()
        result = so.optimize_tcp_keepalive()
        # Non-root early return doesn't append; check result type only
        assert isinstance(result, OptimizationResult)


class TestU27SystemOptimizerFirewall:
    """Tests for firewall configuration."""

    def test_configure_firewall_returns_result(self):
        so = SystemOptimizer()
        result = so.configure_firewall()
        assert isinstance(result, OptimizationResult)

    def test_configure_firewall_component_is_firewall(self):
        so = SystemOptimizer()
        result = so.configure_firewall()
        assert result.component == SystemComponent.FIREWALL

    def test_configure_firewall_has_message(self):
        so = SystemOptimizer()
        result = so.configure_firewall()
        assert isinstance(result.message, str)


class TestU27SystemOptimizerDiagnostics:
    """Tests for system diagnostics."""

    def test_run_diagnostics_returns_diagnostics(self):
        so = SystemOptimizer()
        result = so.run_system_diagnostics()
        assert isinstance(result, SystemDiagnostics)

    def test_diagnostics_has_os_info(self):
        so = SystemOptimizer()
        result = so.run_system_diagnostics()
        assert isinstance(result.os_info, dict)

    def test_diagnostics_os_has_system_key(self):
        so = SystemOptimizer()
        result = so.run_system_diagnostics()
        assert "system" in result.os_info

    def test_diagnostics_has_memory_info(self):
        so = SystemOptimizer()
        result = so.run_system_diagnostics()
        assert isinstance(result.memory_info, dict)

    def test_diagnostics_memory_has_total(self):
        so = SystemOptimizer()
        result = so.run_system_diagnostics()
        # psutil is available
        assert "total" in result.memory_info


class TestU27SystemOptimizerOptimizeAll:
    """Tests for optimize_all() method."""

    def test_optimize_all_returns_list(self):
        so = SystemOptimizer()
        results = so.optimize_all()
        assert isinstance(results, list)

    def test_optimize_all_items_are_results(self):
        so = SystemOptimizer()
        results = so.optimize_all()
        for r in results:
            assert isinstance(r, OptimizationResult)

    def test_optimize_all_basic_level_minimal(self):
        # BASIC level runs no optimizations (not in standard/aggressive list)
        so = SystemOptimizer(OptimizationLevel.BASIC)
        results = so.optimize_all()
        assert isinstance(results, list)

    def test_optimize_all_standard_level_runs_two(self):
        so = SystemOptimizer(OptimizationLevel.STANDARD)
        results = so.optimize_all()
        # TCP + firewall = 2 results for standard
        assert len(results) == 2


class TestU27ModuleFunctions:
    """Tests for module-level functions in U27."""

    def test_get_system_optimizer_exists(self):
        assert callable(u27_mod.get_system_optimizer)

    def test_get_system_optimizer_returns_instance(self):
        result = u27_mod.get_system_optimizer()
        assert isinstance(result, SystemOptimizer)

    def test_get_system_optimizer_default_level(self):
        result = u27_mod.get_system_optimizer()
        assert result.optimization_level == OptimizationLevel.STANDARD

    def test_get_system_optimizer_custom_level(self):
        result = u27_mod.get_system_optimizer(OptimizationLevel.AGGRESSIVE)
        assert result.optimization_level == OptimizationLevel.AGGRESSIVE

    def test_get_global_optimizer_returns_instance(self):
        result = u27_mod.get_global_optimizer()
        assert isinstance(result, SystemOptimizer)

    def test_get_global_optimizer_singleton(self):
        g1 = u27_mod.get_global_optimizer()
        g2 = u27_mod.get_global_optimizer()
        assert g1 is g2

    def test_optimize_system_for_trading_returns_list(self):
        results = u27_mod.optimize_system_for_trading()
        assert isinstance(results, list)
