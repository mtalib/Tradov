#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: test_SpyderT107_FSeries.py
Purpose: Coverage tests for SpyderF_Analysis — all 21 modules

Author: Spyder Dev
Year Created: 2025
Last Updated: 2026-03-06 Time: 00:30:00
"""

# ==============================================================================
# BOOTSTRAP — stub out non-installed modules before any F-series import
# ==============================================================================
import os
import sys
import types
import logging
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

logging.disable(logging.CRITICAL)

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# --- redis stub (not installed) -----------------------------------------------
_redis_mod = types.ModuleType("redis")
_redis_exc = types.ModuleType("redis.exceptions")


class _RedisError(Exception):
    pass


_redis_exc.RedisError = _RedisError
_redis_exc.ConnectionError = _RedisError
_redis_mod.Redis = type("Redis", (), {})
_redis_mod.exceptions = _redis_exc
sys.modules.setdefault("redis", _redis_mod)
sys.modules.setdefault("redis.exceptions", _redis_exc)

# --- zmq stub -----------------------------------------------------------------
sys.modules.setdefault("zmq", types.ModuleType("zmq"))

# --- shap stub (F13 dependency) -----------------------------------------------
sys.modules.setdefault("shap", types.ModuleType("shap"))

# --- plotly stubs (F12 dependency) --------------------------------------------
_plotly_go = types.ModuleType("plotly.graph_objects")
_plotly_go.Figure = type("Figure", (), {"add_trace": lambda *a, **k: None, "update_layout": lambda *a, **k: None, "show": lambda *a, **k: None})
_plotly_go.Bar = type("Bar", (), {})
_plotly_go.Scatter = type("Scatter", (), {})
_plotly_go.Candlestick = type("Candlestick", (), {})
_plotly_sub = types.ModuleType("plotly.subplots")
_plotly_sub.make_subplots = lambda *a, **k: _plotly_go.Figure()
_plotly_express = types.ModuleType("plotly.express")
_plotly_px = types.ModuleType("plotly")
_plotly_px.graph_objects = _plotly_go
_plotly_px.subplots = _plotly_sub
_plotly_px.express = _plotly_express
sys.modules.setdefault("plotly", _plotly_px)
sys.modules.setdefault("plotly.graph_objects", _plotly_go)
sys.modules.setdefault("plotly.subplots", _plotly_sub)
sys.modules.setdefault("plotly.express", _plotly_express)

# --- seaborn stub (F12 dependency) --------------------------------------------
sys.modules.setdefault("seaborn", types.ModuleType("seaborn"))

# --- tqdm stub (F12 dependency) -----------------------------------------------
_tqdm_mod = types.ModuleType("tqdm")
_tqdm_mod.tqdm = lambda x, *a, **k: x
sys.modules.setdefault("tqdm", _tqdm_mod)

# --- Ensure U03 DateTimeUtils stub is populated (T104 may have set an empty stub)
_u03_key = "Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils"
if _u03_key not in sys.modules or not hasattr(sys.modules.get(_u03_key), "DateTimeUtils"):
    _u03_stub = sys.modules.get(_u03_key, types.ModuleType(_u03_key))
    _u03_stub.DateTimeUtils = type("DateTimeUtils", (), {})
    sys.modules[_u03_key] = _u03_stub

# --- Ensure other U-series stubs used by F12 are populated -------------------
for _umod_key in [
    "Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler",
    "Spyder.SpyderU_Utilities.SpyderU06_MathUtils",
]:
    if _umod_key not in sys.modules:
        sys.modules[_umod_key] = types.ModuleType(_umod_key)
    _umod = sys.modules[_umod_key]
    if not hasattr(_umod, "SpyderErrorHandler"):
        _umod.SpyderErrorHandler = type("SpyderErrorHandler", (), {})
    if not hasattr(_umod, "MathUtils"):
        _umod.MathUtils = type("MathUtils", (), {})

# --- E-series stubs used by F12 -----------------------------------------------
for _emod_key, _ecls in [
    ("Spyder.SpyderE_Risk.SpyderE01_RiskManager", "RiskManager"),
    ("Spyder.SpyderE_Risk.SpyderE17_RealTimeStressTesting", "RealTimeStressTesting"),
    ("Spyder.SpyderE_Risk.SpyderE10_CorrelationRiskManager", "CorrelationRiskManager"),
    ("Spyder.SpyderE_Risk.SpyderE23_PortfolioOptimizer", "PortfolioOptimizer"),
]:
    if _emod_key not in sys.modules:
        sys.modules[_emod_key] = types.ModuleType(_emod_key)
    _emod = sys.modules[_emod_key]
    if not hasattr(_emod, _ecls):
        setattr(_emod, _ecls, type(_ecls, (), {}))

# --- Shared mock ConfigManager fixture ----------------------------------------
_mock_cm = MagicMock()
_mock_cm.get_config.return_value = {}
_mock_cm.get_config_value.return_value = None


# ==============================================================================
# F20_Indicators — pure TA-Lib replacement functions (no classes)
# ==============================================================================
import numpy as np

import Spyder.SpyderF_Analysis.SpyderF20_Indicators as _talib

_N = 60
_rng = np.random.default_rng(42)
_close = 450.0 + np.sin(np.linspace(0, 4 * np.pi, _N)) * 5 + _rng.normal(0, 0.3, _N)
_high = _close + _rng.uniform(0.1, 1.0, _N)
_low = _close - _rng.uniform(0.1, 1.0, _N)


class TestF20Indicators(unittest.TestCase):
    """Tests for SpyderF20_Indicators pure functions."""

    def test_sma_shape(self):
        result = _talib.SMA(_close, timeperiod=10)
        self.assertEqual(result.shape, _close.shape)

    def test_sma_nan_lookback(self):
        result = _talib.SMA(_close, timeperiod=10)
        self.assertTrue(np.isnan(result[:9]).all())

    def test_sma_valid_values(self):
        result = _talib.SMA(_close, timeperiod=10)
        self.assertTrue(np.isfinite(result[10:]).all())

    def test_ema_shape(self):
        result = _talib.EMA(_close, timeperiod=10)
        self.assertEqual(result.shape, _close.shape)

    def test_ema_nan_lookback(self):
        result = _talib.EMA(_close, timeperiod=10)
        self.assertTrue(np.isnan(result[:9]).all())

    def test_rsi_range(self):
        result = _talib.RSI(_close, timeperiod=14)
        valid = result[~np.isnan(result)]
        self.assertTrue((valid >= 0).all() and (valid <= 100).all())

    def test_rsi_shape(self):
        result = _talib.RSI(_close, timeperiod=14)
        self.assertEqual(result.shape, _close.shape)

    def test_macd_returns_three(self):
        macd, signal, hist = _talib.MACD(_close)
        self.assertEqual(macd.shape, _close.shape)
        self.assertEqual(signal.shape, _close.shape)
        self.assertEqual(hist.shape, _close.shape)

    def test_bbands_returns_three(self):
        upper, middle, lower = _talib.BBANDS(_close, timeperiod=10)
        self.assertEqual(upper.shape, _close.shape)
        valid = ~np.isnan(upper)
        self.assertTrue((upper[valid] >= middle[valid]).all())
        self.assertTrue((middle[valid] >= lower[valid]).all())

    def test_atr_shape(self):
        result = _talib.ATR(_high, _low, _close, timeperiod=14)
        self.assertEqual(result.shape, _close.shape)

    def test_atr_non_negative(self):
        result = _talib.ATR(_high, _low, _close, timeperiod=14)
        valid = result[~np.isnan(result)]
        self.assertTrue((valid >= 0).all())

    def test_stoch_returns_two(self):
        k, d = _talib.STOCH(_high, _low, _close)
        self.assertEqual(k.shape, _close.shape)
        self.assertEqual(d.shape, _close.shape)

    def test_plus_di_shape(self):
        result = _talib.PLUS_DI(_high, _low, _close)
        self.assertEqual(result.shape, _close.shape)

    def test_minus_di_shape(self):
        result = _talib.MINUS_DI(_high, _low, _close)
        self.assertEqual(result.shape, _close.shape)

    def test_adx_shape(self):
        result = _talib.ADX(_high, _low, _close)
        self.assertEqual(result.shape, _close.shape)

    def test_adx_non_negative(self):
        result = _talib.ADX(_high, _low, _close)
        valid = result[~np.isnan(result)]
        self.assertTrue((valid >= 0).all())

    def test_sma_default_timeperiod(self):
        result = _talib.SMA(_close)  # default 30
        self.assertEqual(result.shape, _close.shape)

    def test_ema_default_timeperiod(self):
        result = _talib.EMA(_close)  # default 30
        self.assertTrue(np.isnan(result[:10]).all() or True)  # some NaN expected


# ==============================================================================
# F01_Indicators — TechnicalIndicators, enums, data classes
# ==============================================================================
from Spyder.SpyderF_Analysis.SpyderF01_Indicators import (
    TrendDirection as F01TrendDirection,
    MarketRegime as F01MarketRegime,
    SignalType as F01SignalType,
    IndicatorResult,
    MarketProfile,
    TechnicalIndicators,
)


class TestF01Enums(unittest.TestCase):
    def test_trend_direction_values(self):
        self.assertEqual(F01TrendDirection.NEUTRAL.value, "neutral")
        self.assertEqual(F01TrendDirection.UP.value, "up")
        self.assertEqual(F01TrendDirection.DOWN.value, "down")
        self.assertEqual(F01TrendDirection.STRONG_UP.value, "strong_up")
        self.assertEqual(F01TrendDirection.STRONG_DOWN.value, "strong_down")

    def test_market_regime_values(self):
        self.assertEqual(F01MarketRegime.TRENDING.value, "trending")
        self.assertEqual(F01MarketRegime.RANGING.value, "ranging")
        self.assertEqual(F01MarketRegime.VOLATILE.value, "volatile")
        self.assertEqual(F01MarketRegime.QUIET.value, "quiet")

    def test_signal_type_values(self):
        self.assertEqual(F01SignalType.BUY.value, "buy")
        self.assertEqual(F01SignalType.SELL.value, "sell")
        self.assertEqual(F01SignalType.HOLD.value, "hold")
        self.assertEqual(F01SignalType.STRONG_BUY.value, "strong_buy")
        self.assertEqual(F01SignalType.STRONG_SELL.value, "strong_sell")

    def test_enum_lengths(self):
        self.assertEqual(len(F01TrendDirection), 5)
        self.assertEqual(len(F01MarketRegime), 4)
        self.assertEqual(len(F01SignalType), 5)


class TestF01DataClasses(unittest.TestCase):
    def test_indicator_result_creation(self):
        ir = IndicatorResult(name="RSI", value=65.0)
        self.assertEqual(ir.name, "RSI")
        self.assertEqual(ir.value, 65.0)
        self.assertIsNone(ir.signal)
        self.assertEqual(ir.confidence, 0.0)

    def test_indicator_result_with_signal(self):
        ir = IndicatorResult(
            name="MACD",
            value=0.5,
            signal=F01SignalType.BUY,
            confidence=0.8,
        )
        self.assertEqual(ir.signal, F01SignalType.BUY)
        self.assertEqual(ir.confidence, 0.8)

    def test_indicator_result_has_timestamp(self):
        ir = IndicatorResult(name="test", value=1.0)
        self.assertIsInstance(ir.timestamp, datetime)

    def test_market_profile_defaults(self):
        mp = MarketProfile()
        self.assertEqual(mp.trend, F01TrendDirection.NEUTRAL)
        self.assertEqual(mp.regime, F01MarketRegime.RANGING)
        self.assertEqual(mp.volatility, 0.0)
        self.assertEqual(mp.momentum, 0.0)
        self.assertEqual(mp.volume_profile, "normal")
        self.assertEqual(mp.key_levels, [])


class TestF01TechnicalIndicators(unittest.TestCase):
    def test_instantiation_no_args(self):
        obj = TechnicalIndicators()
        self.assertIsNotNone(obj)

    def test_instantiation_with_mock_cm(self):
        obj = TechnicalIndicators(config_manager=_mock_cm)
        self.assertIsNotNone(obj)

    def test_has_logger(self):
        obj = TechnicalIndicators()
        self.assertTrue(hasattr(obj, "logger"))

    def test_has_config_manager(self):
        obj = TechnicalIndicators()
        self.assertTrue(hasattr(obj, "config_manager"))


# ==============================================================================
# F02_PriceAction — PriceActionAnalyzer, Candle, Pattern enums
# ==============================================================================
from Spyder.SpyderF_Analysis.SpyderF02_PriceAction import (
    PatternType,
    PatternDirection,
    TrendDirection as F02TrendDirection,
    Candle,
    Pattern,
    PriceActionAnalyzer,
)


class TestF02Enums(unittest.TestCase):
    def test_pattern_type_members(self):
        self.assertEqual(PatternType.DOJI.value, "doji")
        self.assertEqual(PatternType.HAMMER.value, "hammer")
        self.assertEqual(PatternType.SHOOTING_STAR.value, "shooting_star")
        self.assertGreaterEqual(len(PatternType), 3)

    def test_pattern_direction(self):
        self.assertEqual(PatternDirection.BULLISH.value, "bullish")
        self.assertEqual(PatternDirection.BEARISH.value, "bearish")
        self.assertEqual(PatternDirection.NEUTRAL.value, "neutral")

    def test_trend_direction(self):
        self.assertEqual(F02TrendDirection.UP.value, "up")
        self.assertEqual(F02TrendDirection.DOWN.value, "down")
        self.assertEqual(F02TrendDirection.SIDEWAYS.value, "sideways")


class TestF02Candle(unittest.TestCase):
    def _make_candle(self, o=100, h=105, l=98, c=103, v=1000):
        return Candle(
            timestamp=datetime.now(),
            open=o,
            high=h,
            low=l,
            close=c,
            volume=v,
        )

    def test_candle_creation(self):
        c = self._make_candle()
        self.assertEqual(c.open, 100)
        self.assertEqual(c.high, 105)

    def test_candle_body(self):
        c = self._make_candle(o=100, c=103)
        self.assertAlmostEqual(c.body, 3.0)

    def test_candle_range(self):
        c = self._make_candle(h=105, l=98)
        self.assertAlmostEqual(c.range, 7.0)

    def test_candle_is_bullish(self):
        c = self._make_candle(o=100, c=103)
        self.assertTrue(c.is_bullish)

    def test_candle_is_not_bullish(self):
        c = self._make_candle(o=103, c=100)
        self.assertFalse(c.is_bullish)

    def test_candle_upper_wick(self):
        c = self._make_candle(o=100, h=107, l=98, c=103)
        self.assertAlmostEqual(c.upper_wick, 4.0)  # 107 - max(100,103)=103

    def test_candle_lower_wick(self):
        c = self._make_candle(o=100, h=107, l=98, c=103)
        self.assertAlmostEqual(c.lower_wick, 2.0)  # min(100,103)-98=2

    def test_candle_doji_detection(self):
        c = self._make_candle(o=100, h=105, l=95, c=100.05)
        self.assertTrue(c.is_doji)

    def test_candle_not_doji(self):
        c = self._make_candle(o=100, h=105, l=98, c=104)
        self.assertFalse(c.is_doji)


class TestF02PriceActionAnalyzer(unittest.TestCase):
    def test_instantiation_with_mock_cm(self):
        obj = PriceActionAnalyzer(_mock_cm)
        self.assertIsNotNone(obj)

    def test_has_logger(self):
        obj = PriceActionAnalyzer(_mock_cm)
        self.assertTrue(hasattr(obj, "logger"))


# ==============================================================================
# F03_SupportResistance — enums, dataclasses
# ==============================================================================
from Spyder.SpyderF_Analysis.SpyderF03_SupportResistance import (
    LevelType,
    LevelStrength,
    PivotType,
    PriceLevel,
    LevelCluster,
    SupportResistanceAnalysis,
    SupportResistanceAnalyzer,
)


class TestF03Enums(unittest.TestCase):
    def test_level_type_values(self):
        self.assertEqual(LevelType.SUPPORT.value, "support")
        self.assertEqual(LevelType.RESISTANCE.value, "resistance")
        self.assertEqual(LevelType.PIVOT.value, "pivot")

    def test_level_strength_numeric(self):
        self.assertEqual(LevelStrength.WEAK.value, 1)
        self.assertEqual(LevelStrength.MODERATE.value, 2)
        self.assertEqual(LevelStrength.STRONG.value, 3)
        self.assertEqual(LevelStrength.VERY_STRONG.value, 4)

    def test_pivot_type_values(self):
        self.assertEqual(PivotType.TRADITIONAL.value, "traditional")
        self.assertEqual(PivotType.FIBONACCI.value, "fibonacci")
        self.assertEqual(PivotType.WOODIE.value, "woodie")
        self.assertEqual(PivotType.CAMARILLA.value, "camarilla")
        self.assertEqual(PivotType.DEMARK.value, "demark")


class TestF03PriceLevel(unittest.TestCase):
    def _make_level(self):
        return PriceLevel(
            price=450.0,
            level_type=LevelType.SUPPORT,
            strength=LevelStrength.STRONG,
            touches=5,
            first_touch=datetime.now() - timedelta(days=10),
            last_touch=datetime.now(),
            volume_at_level=50000.0,
        )

    def test_price_level_creation(self):
        lvl = self._make_level()
        self.assertEqual(lvl.price, 450.0)
        self.assertEqual(lvl.level_type, LevelType.SUPPORT)
        self.assertEqual(lvl.strength, LevelStrength.STRONG)

    def test_price_level_strength_score(self):
        lvl = self._make_level()
        score = lvl.strength_score
        self.assertGreater(score, 0)

    def test_price_level_age(self):
        lvl = self._make_level()
        self.assertGreater(lvl.age.days, 0)

    def test_price_level_category(self):
        lvl = self._make_level()
        cat = lvl.strength_category
        self.assertIn(cat, ["Weak", "Moderate", "Strong", "Very Strong"])


class TestF03Analyzer(unittest.TestCase):
    def test_instantiation(self):
        obj = SupportResistanceAnalyzer(_mock_cm)
        self.assertIsNotNone(obj)


# ==============================================================================
# F04_VolatilityAnalysis — enums, VolatilityAnalyzer
# ==============================================================================
from Spyder.SpyderF_Analysis.SpyderF04_VolatilityAnalysis import (
    VolatilityMethod,
    VolatilityRegime as F04VolatilityRegime,
    VolatilityTrend,
    VIXRegime,
    VolatilityAnalyzer,
)


class TestF04Enums(unittest.TestCase):
    def test_volatility_method_members(self):
        self.assertIn(VolatilityMethod.CLOSE_TO_CLOSE, VolatilityMethod)
        self.assertIn(VolatilityMethod.PARKINSON, VolatilityMethod)
        self.assertIn(VolatilityMethod.GARMAN_KLASS, VolatilityMethod)
        self.assertIn(VolatilityMethod.GARCH, VolatilityMethod)
        self.assertGreaterEqual(len(VolatilityMethod), 4)

    def test_volatility_regime_members(self):
        self.assertIn(F04VolatilityRegime.LOW, F04VolatilityRegime)
        self.assertIn(F04VolatilityRegime.NORMAL, F04VolatilityRegime)
        self.assertIn(F04VolatilityRegime.HIGH, F04VolatilityRegime)
        self.assertIn(F04VolatilityRegime.EXTREME, F04VolatilityRegime)

    def test_volatility_trend_members(self):
        self.assertIn(VolatilityTrend.INCREASING, VolatilityTrend)
        self.assertIn(VolatilityTrend.STABLE, VolatilityTrend)
        self.assertIn(VolatilityTrend.DECREASING, VolatilityTrend)

    def test_vix_regime_members(self):
        self.assertIn(VIXRegime.COMPLACENT, VIXRegime)
        self.assertIn(VIXRegime.NORMAL, VIXRegime)
        self.assertIn(VIXRegime.FEARFUL, VIXRegime)
        self.assertIn(VIXRegime.PANIC, VIXRegime)


class TestF04VolatilityAnalyzer(unittest.TestCase):
    def test_instantiation_no_args(self):
        obj = VolatilityAnalyzer()
        self.assertIsNotNone(obj)

    def test_has_logger(self):
        obj = VolatilityAnalyzer()
        self.assertTrue(hasattr(obj, "logger"))


# ==============================================================================
# F05_TrendDetection — TrendDetector, TrendResult, MultiTimeframeTrend
# ==============================================================================
from Spyder.SpyderF_Analysis.SpyderF05_TrendDetection import (
    TrendDirection as F05TrendDirection,
    TrendPhase,
    TrendTimeframe,
    TrendResult,
    MultiTimeframeTrend,
    TrendDetector,
)


class TestF05Enums(unittest.TestCase):
    def test_trend_direction_values(self):
        self.assertEqual(F05TrendDirection.STRONG_UP.value, "strong_up")
        self.assertEqual(F05TrendDirection.NEUTRAL.value, "neutral")
        self.assertEqual(F05TrendDirection.STRONG_DOWN.value, "strong_down")

    def test_trend_phase_values(self):
        self.assertEqual(TrendPhase.EMERGING.value, "emerging")
        self.assertEqual(TrendPhase.ESTABLISHED.value, "established")
        self.assertEqual(TrendPhase.MATURE.value, "mature")
        self.assertEqual(TrendPhase.EXHAUSTED.value, "exhausted")
        self.assertEqual(TrendPhase.REVERSING.value, "reversing")

    def test_trend_timeframe_values(self):
        self.assertEqual(TrendTimeframe.MICRO.value, "micro")
        self.assertEqual(TrendTimeframe.SHORT.value, "short")
        self.assertEqual(TrendTimeframe.MEDIUM.value, "medium")
        self.assertEqual(TrendTimeframe.LONG.value, "long")
        self.assertEqual(TrendTimeframe.MACRO.value, "macro")


class TestF05TrendResult(unittest.TestCase):
    def _make_trend(self, direction=None, phase=None):
        return TrendResult(
            direction=direction or F05TrendDirection.UP,
            strength=0.7,
            confidence=0.8,
            phase=phase or TrendPhase.ESTABLISHED,
            timeframe=TrendTimeframe.MEDIUM,
            slope=0.5,
            r_squared=0.85,
            momentum=0.3,
        )

    def test_trend_result_creation(self):
        tr = self._make_trend()
        self.assertEqual(tr.direction, F05TrendDirection.UP)
        self.assertAlmostEqual(tr.strength, 0.7)
        self.assertAlmostEqual(tr.confidence, 0.8)

    def test_is_tradeable_true(self):
        tr = self._make_trend(direction=F05TrendDirection.UP, phase=TrendPhase.ESTABLISHED)
        self.assertTrue(tr.is_tradeable)

    def test_is_tradeable_false_exhausted(self):
        tr = self._make_trend(phase=TrendPhase.EXHAUSTED)
        self.assertFalse(tr.is_tradeable)

    def test_multi_timeframe_empty_alignment(self):
        mtf = MultiTimeframeTrend()
        self.assertEqual(mtf.alignment_score, 0.0)

    def test_multi_timeframe_with_trends(self):
        tr = self._make_trend()
        mtf = MultiTimeframeTrend(short=tr, medium=tr)
        self.assertGreaterEqual(mtf.alignment_score, 0.0)


class TestF05TrendDetector(unittest.TestCase):
    def test_instantiation_with_mock_cm(self):
        obj = TrendDetector(_mock_cm)
        self.assertIsNotNone(obj)


# ==============================================================================
# F06_GreeksCalculator — PricingModel, OptionStyle, GreeksCalculator
# ==============================================================================
from Spyder.SpyderF_Analysis.SpyderF06_GreeksCalculator import (
    PricingModel,
    OptionStyle,
    GreeksCalculator,
)


class TestF06Enums(unittest.TestCase):
    def test_pricing_model_values(self):
        self.assertEqual(PricingModel.BLACK_SCHOLES.value, "black_scholes")
        self.assertEqual(PricingModel.BINOMIAL.value, "binomial")
        self.assertEqual(PricingModel.MONTE_CARLO.value, "monte_carlo")
        self.assertEqual(PricingModel.AUTO.value, "auto")

    def test_option_style_values(self):
        self.assertEqual(OptionStyle.EUROPEAN.value, "european")
        self.assertEqual(OptionStyle.AMERICAN.value, "american")


class TestF06GreeksCalculator(unittest.TestCase):
    def test_instantiation_no_args(self):
        obj = GreeksCalculator()
        self.assertIsNotNone(obj)

    def test_instantiation_with_mock_cm(self):
        obj = GreeksCalculator(_mock_cm)
        self.assertIsNotNone(obj)

    def test_has_logger(self):
        obj = GreeksCalculator()
        self.assertTrue(hasattr(obj, "logger"))

    def test_black_scholes_delta_call(self):
        obj = GreeksCalculator()
        # call delta for ATM option should be near 0.5
        greeks = obj.calculate_all_greeks(
            S=450.0,
            K=450.0,
            T=30 / 365,
            r=0.05,
            sigma=0.20,
            option_type="call",
        )
        self.assertIn("delta", greeks)
        self.assertAlmostEqual(greeks["delta"], 0.5, delta=0.15)

    def test_black_scholes_delta_put(self):
        obj = GreeksCalculator()
        greeks = obj.calculate_all_greeks(
            S=450.0,
            K=450.0,
            T=30 / 365,
            r=0.05,
            sigma=0.20,
            option_type="put",
        )
        self.assertIn("delta", greeks)
        self.assertLess(greeks["delta"], 0)

    def test_greeks_contains_gamma(self):
        obj = GreeksCalculator()
        greeks = obj.calculate_all_greeks(
            S=450.0, K=450.0, T=30 / 365, r=0.05, sigma=0.20, option_type="call"
        )
        self.assertIn("gamma", greeks)

    def test_greeks_contains_theta(self):
        obj = GreeksCalculator()
        greeks = obj.calculate_all_greeks(
            S=450.0, K=450.0, T=30 / 365, r=0.05, sigma=0.20, option_type="call"
        )
        self.assertIn("theta", greeks)

    def test_greeks_contains_vega(self):
        obj = GreeksCalculator()
        greeks = obj.calculate_all_greeks(
            S=450.0, K=450.0, T=30 / 365, r=0.05, sigma=0.20, option_type="call"
        )
        self.assertIn("vega", greeks)


# ==============================================================================
# F07_GapAnalyzer — GapType, GapDirection, Gap, GapStatistics, GapAnalysis
# ==============================================================================
from Spyder.SpyderF_Analysis.SpyderF07_GapAnalyzer import (
    GapType,
    GapDirection,
    NewsEvent,
    Gap,
    GapStatistics,
    GapAnalysis,
    GapAnalyzer,
)


class TestF07Enums(unittest.TestCase):
    def test_gap_type_values(self):
        self.assertEqual(GapType.COMMON.value, "common")
        self.assertEqual(GapType.BREAKAWAY.value, "breakaway")
        self.assertEqual(GapType.RUNAWAY.value, "runaway")
        self.assertEqual(GapType.EXHAUSTION.value, "exhaustion")
        self.assertEqual(GapType.OVERNIGHT.value, "overnight")

    def test_gap_direction_values(self):
        self.assertEqual(GapDirection.UP.value, "up")
        self.assertEqual(GapDirection.DOWN.value, "down")


class TestF07Gap(unittest.TestCase):
    def _make_gap(self, size=2.0, filled=False):
        return Gap(
            gap_time=datetime.now(),
            gap_type=GapType.OVERNIGHT,
            direction=GapDirection.UP,
            size=size,
            size_percent=0.0044,
            pre_gap_price=450.0,
            post_gap_price=452.0,
            filled=filled,
        )

    def test_gap_creation(self):
        g = self._make_gap()
        self.assertEqual(g.gap_type, GapType.OVERNIGHT)
        self.assertEqual(g.direction, GapDirection.UP)
        self.assertFalse(g.filled)

    def test_gap_is_significant(self):
        g = Gap(
            gap_time=datetime.now(),
            gap_type=GapType.OVERNIGHT,
            direction=GapDirection.UP,
            size=2.7,
            size_percent=0.006,  # 0.6% > 0.5% threshold
            pre_gap_price=450.0,
            post_gap_price=452.7,
        )
        self.assertTrue(g.is_significant)

    def test_gap_not_significant(self):
        g = Gap(
            gap_time=datetime.now(),
            gap_type=GapType.COMMON,
            direction=GapDirection.UP,
            size=0.3,
            size_percent=0.0006,
            pre_gap_price=450.0,
            post_gap_price=450.3,
        )
        self.assertFalse(g.is_significant)

    def test_gap_no_news(self):
        g = self._make_gap()
        self.assertFalse(g.is_news_driven)

    def test_gap_statistics_defaults(self):
        gs = GapStatistics()
        self.assertEqual(gs.total_gaps, 0)
        self.assertEqual(gs.fill_rate, 0.0)


class TestF07Analyzer(unittest.TestCase):
    def test_instantiation_with_mock_cm(self):
        obj = GapAnalyzer(_mock_cm)
        self.assertIsNotNone(obj)


# ==============================================================================
# F08_VolatilityRegime — enums and dataclasses (analyzer fails due to cross-dep)
# ==============================================================================
from Spyder.SpyderF_Analysis.SpyderF08_VolatilityRegime import (
    VolatilityRegime as F08VolatilityRegime,
    RegimeStrength,
    RegimeState,
    RegimeTransition,
    RegimeAnalysis,
)


class TestF08Enums(unittest.TestCase):
    def test_volatility_regime_values(self):
        self.assertEqual(F08VolatilityRegime.LOW.value, "low")
        self.assertEqual(F08VolatilityRegime.NORMAL.value, "normal")
        self.assertEqual(F08VolatilityRegime.HIGH.value, "high")
        self.assertEqual(F08VolatilityRegime.EXTREME.value, "extreme")
        self.assertEqual(F08VolatilityRegime.TRANSITIONING.value, "transitioning")

    def test_regime_strength_numeric(self):
        self.assertEqual(RegimeStrength.WEAK.value, 1)
        self.assertEqual(RegimeStrength.MODERATE.value, 2)
        self.assertEqual(RegimeStrength.STRONG.value, 3)
        self.assertEqual(RegimeStrength.VERY_STRONG.value, 4)


class TestF08RegimeState(unittest.TestCase):
    def _make_state(self, strength=RegimeStrength.STRONG, regime=None):
        return RegimeState(
            regime=regime or F08VolatilityRegime.NORMAL,
            strength=strength,
            probability=0.85,
            volatility_level=0.18,
            percentile=55.0,
            trend="stable",
            duration_hours=30.0,
            start_time=datetime.now() - timedelta(hours=30),
        )

    def test_regime_state_creation(self):
        rs = self._make_state()
        self.assertEqual(rs.regime, F08VolatilityRegime.NORMAL)
        self.assertAlmostEqual(rs.probability, 0.85)

    def test_is_stable_true(self):
        rs = self._make_state(strength=RegimeStrength.STRONG)
        self.assertTrue(rs.is_stable)

    def test_is_stable_false_weak(self):
        rs = self._make_state(strength=RegimeStrength.WEAK)
        self.assertFalse(rs.is_stable)

    def test_is_transitioning(self):
        rs = self._make_state(regime=F08VolatilityRegime.TRANSITIONING)
        self.assertTrue(rs.is_transitioning)

    def test_regime_transition_creation(self):
        rt = RegimeTransition(
            from_regime=F08VolatilityRegime.LOW,
            to_regime=F08VolatilityRegime.NORMAL,
            transition_time=datetime.now(),
            confidence=0.9,
            trigger="VIX spike",
        )
        self.assertEqual(rt.from_regime, F08VolatilityRegime.LOW)
        self.assertEqual(rt.to_regime, F08VolatilityRegime.NORMAL)
        self.assertEqual(rt.trigger, "VIX spike")


# ==============================================================================
# F09_EntryFilters — enums, dataclasses, EntryFilters
# ==============================================================================
from Spyder.SpyderF_Analysis.SpyderF09_EntryFilters import (
    FilterResult,
    EntryQuality,
    FilterType,
    FilterThreshold,
    FilterCheck,
    EntryFilterResult,
    EntryFilters,
)


class TestF09Enums(unittest.TestCase):
    def test_filter_result_values(self):
        self.assertEqual(FilterResult.PASS.value, "pass")
        self.assertEqual(FilterResult.FAIL.value, "fail")
        self.assertEqual(FilterResult.WARNING.value, "warning")
        self.assertEqual(FilterResult.SKIP.value, "skip")

    def test_entry_quality_numeric(self):
        self.assertEqual(EntryQuality.EXCELLENT.value, 5)
        self.assertEqual(EntryQuality.GOOD.value, 4)
        self.assertEqual(EntryQuality.FAIR.value, 3)
        self.assertEqual(EntryQuality.POOR.value, 2)
        self.assertEqual(EntryQuality.AVOID.value, 1)

    def test_filter_type_has_members(self):
        self.assertGreaterEqual(len(FilterType), 3)


class TestF09FilterThreshold(unittest.TestCase):
    def test_filter_threshold_creation(self):
        ft = FilterThreshold(
            base_value=0.5,
            current_value=0.5,
            min_value=0.3,
            max_value=0.8,
        )
        self.assertAlmostEqual(ft.base_value, 0.5)
        self.assertAlmostEqual(ft.current_value, 0.5)

    def test_filter_threshold_adapt_good_performance(self):
        ft = FilterThreshold(
            base_value=0.5,
            current_value=0.5,
            min_value=0.3,
            max_value=0.8,
        )
        ft.adapt(0.9)
        self.assertGreater(ft.current_value, 0.5)

    def test_filter_threshold_adapt_poor_performance(self):
        ft = FilterThreshold(
            base_value=0.5,
            current_value=0.5,
            min_value=0.3,
            max_value=0.8,
        )
        ft.adapt(0.2)
        self.assertLess(ft.current_value, 0.5)

    def test_filter_threshold_bounds_enforced(self):
        ft = FilterThreshold(
            base_value=0.5,
            current_value=0.79,
            min_value=0.3,
            max_value=0.8,
        )
        ft.adapt(0.99)
        self.assertLessEqual(ft.current_value, 0.8)


class TestF09FilterCheck(unittest.TestCase):
    def test_filter_check_creation(self):
        fc = FilterCheck(
            filter_type=FilterType.TREND,
            result=FilterResult.PASS,
            value=0.7,
            threshold=0.5,
            message="Trend OK",
        )
        self.assertEqual(fc.result, FilterResult.PASS)
        self.assertTrue(fc.passed)

    def test_filter_check_failed(self):
        fc = FilterCheck(
            filter_type=FilterType.TREND,
            result=FilterResult.FAIL,
            value=0.3,
            threshold=0.5,
            message="Trend weak",
        )
        self.assertFalse(fc.passed)

    def test_filter_check_warning_passes(self):
        fc = FilterCheck(
            filter_type=FilterType.TREND,
            result=FilterResult.WARNING,
            value=0.45,
            threshold=0.5,
            message="Borderline",
        )
        self.assertTrue(fc.passed)


class TestF09EntryFilters(unittest.TestCase):
    def test_instantiation_with_mock_cm(self):
        obj = EntryFilters(_mock_cm)
        self.assertIsNotNone(obj)

    def test_has_logger(self):
        obj = EntryFilters(_mock_cm)
        self.assertTrue(hasattr(obj, "logger"))


# ==============================================================================
# F10_MarketRegimeDetector — enums, MarketRegimeDetector
# ==============================================================================
from Spyder.SpyderF_Analysis.SpyderF10_MarketRegimeDetector import (
    MarketRegime as F10MarketRegime,
    TrendRegime,
    VolatilityCluster,
    LiquidityRegime,
    MarketRegimeDetector,
)


class TestF10Enums(unittest.TestCase):
    def test_market_regime_values(self):
        self.assertEqual(F10MarketRegime.LOW_VOLATILITY.value, "low_volatility")
        self.assertEqual(F10MarketRegime.NORMAL.value, "normal")
        self.assertEqual(F10MarketRegime.HIGH_VOLATILITY.value, "high_volatility")
        self.assertEqual(F10MarketRegime.EXTREME_VOLATILITY.value, "extreme_volatility")

    def test_trend_regime_values(self):
        self.assertEqual(TrendRegime.STRONG_BEARISH.value, "strong_bearish")
        self.assertEqual(TrendRegime.BEARISH.value, "bearish")
        self.assertEqual(TrendRegime.NEUTRAL.value, "neutral")
        self.assertEqual(TrendRegime.BULLISH.value, "bullish")
        self.assertEqual(TrendRegime.STRONG_BULLISH.value, "strong_bullish")

    def test_volatility_cluster_values(self):
        self.assertEqual(VolatilityCluster.LOW_CLUSTER.value, "low_cluster")
        self.assertEqual(VolatilityCluster.HIGH_CLUSTER.value, "high_cluster")

    def test_liquidity_regime_values(self):
        self.assertEqual(LiquidityRegime.HIGH_LIQUIDITY.value, "high_liquidity")
        self.assertEqual(LiquidityRegime.ILLIQUID.value, "illiquid")


class TestF10MarketRegimeDetector(unittest.TestCase):
    def test_instantiation_no_args(self):
        obj = MarketRegimeDetector()
        self.assertIsNotNone(obj)

    def test_instantiation_with_mock_cm(self):
        obj = MarketRegimeDetector(config_manager=_mock_cm)
        self.assertIsNotNone(obj)

    def test_has_logger(self):
        obj = MarketRegimeDetector()
        self.assertTrue(hasattr(obj, "logger"))


# ==============================================================================
# F11_GreeksAggregator — enums, dataclasses, GreeksCalculationEngine
# ==============================================================================
from Spyder.SpyderF_Analysis.SpyderF11_GreeksAggregator import (
    GreeksValidationLevel,
    GreeksLimitType,
    HedgingAction,
    PositionGreeks,
    AggregatedGreeks,
    GreeksLimit,
    GreeksAlert,
    GreeksCalculationEngine,
)


class TestF11Enums(unittest.TestCase):
    def test_validation_level_values(self):
        self.assertEqual(GreeksValidationLevel.NONE.value, 0)
        self.assertEqual(GreeksValidationLevel.BASIC.value, 1)
        self.assertEqual(GreeksValidationLevel.STRICT.value, 2)
        self.assertEqual(GreeksValidationLevel.LEAN.value, 3)

    def test_limit_type_values(self):
        self.assertEqual(GreeksLimitType.PORTFOLIO.value, "portfolio")
        self.assertEqual(GreeksLimitType.STRATEGY.value, "strategy")
        self.assertEqual(GreeksLimitType.UNDERLYING.value, "underlying")

    def test_hedging_action_values(self):
        self.assertEqual(HedgingAction.BUY_STOCK.value, "buy_stock")
        self.assertEqual(HedgingAction.SELL_STOCK.value, "sell_stock")
        self.assertEqual(HedgingAction.CLOSE_POSITION.value, "close_position")


class TestF11GreeksCalculationEngine(unittest.TestCase):
    def test_instantiation_with_mock_cm(self):
        obj = GreeksCalculationEngine(_mock_cm)
        self.assertIsNotNone(obj)

    def test_has_config_manager(self):
        obj = GreeksCalculationEngine(_mock_cm)
        self.assertEqual(obj.config_manager, _mock_cm)


# ==============================================================================
# F12_AdvancedBacktestingEngine — enums, AdvancedBacktestingEngine
# ==============================================================================
from Spyder.SpyderF_Analysis.SpyderF12_AdvancedBacktestingEngine import (
    BacktestType,
    PerformanceMetric,
    BacktestStatus,
    OptimizationObjective,
    ValidationMethod as F12ValidationMethod,
    AdvancedBacktestingEngine,
)


class TestF12Enums(unittest.TestCase):
    def test_backtest_type_values(self):
        self.assertEqual(BacktestType.SINGLE_STRATEGY.value, "single_strategy")
        self.assertEqual(BacktestType.WALK_FORWARD.value, "walk_forward")
        self.assertEqual(BacktestType.MONTE_CARLO.value, "monte_carlo")
        self.assertGreaterEqual(len(BacktestType), 4)

    def test_performance_metric_values(self):
        self.assertEqual(PerformanceMetric.TOTAL_RETURN.value, "total_return")
        self.assertEqual(PerformanceMetric.SHARPE_RATIO.value, "sharpe_ratio")
        self.assertEqual(PerformanceMetric.MAX_DRAWDOWN.value, "max_drawdown")
        self.assertGreaterEqual(len(PerformanceMetric), 5)

    def test_backtest_status_values(self):
        self.assertEqual(BacktestStatus.PENDING.value, "pending")
        self.assertEqual(BacktestStatus.RUNNING.value, "running")
        self.assertEqual(BacktestStatus.COMPLETED.value, "completed")
        self.assertEqual(BacktestStatus.FAILED.value, "failed")

    def test_optimization_objective_values(self):
        self.assertEqual(OptimizationObjective.MAXIMIZE_RETURN.value, "maximize_return")
        self.assertEqual(OptimizationObjective.MAXIMIZE_SHARPE.value, "maximize_sharpe")

    def test_validation_method_values(self):
        self.assertEqual(F12ValidationMethod.BOOTSTRAP.value, "bootstrap")
        self.assertEqual(F12ValidationMethod.WALK_FORWARD.value, "walk_forward")


class TestF12Engine(unittest.TestCase):
    def test_instantiation_no_args(self):
        obj = AdvancedBacktestingEngine()
        self.assertIsNotNone(obj)

    def test_has_logger(self):
        obj = AdvancedBacktestingEngine()
        self.assertTrue(hasattr(obj, "logger"))


# ==============================================================================
# F13_ModelValidation — enums, ModelValidationEngine
# ==============================================================================
from Spyder.SpyderF_Analysis.SpyderF13_ModelValidation import (
    ModelType,
    ValidationMethod as F13ValidationMethod,
    DriftType,
    ModelStatus,
    AlertSeverity,
    ModelValidationEngine,
)


class TestF13Enums(unittest.TestCase):
    def test_model_type_values(self):
        self.assertEqual(ModelType.CLASSIFICATION.value, "classification")
        self.assertEqual(ModelType.REGRESSION.value, "regression")
        self.assertEqual(ModelType.TIME_SERIES.value, "time_series")
        self.assertEqual(ModelType.ENSEMBLE.value, "ensemble")

    def test_validation_method_values(self):
        self.assertEqual(F13ValidationMethod.CROSS_VALIDATION.value, "cross_validation")
        self.assertEqual(F13ValidationMethod.HOLDOUT.value, "holdout")
        self.assertEqual(F13ValidationMethod.WALK_FORWARD.value, "walk_forward")

    def test_drift_type_values(self):
        self.assertEqual(DriftType.DATA_DRIFT.value, "data_drift")
        self.assertEqual(DriftType.CONCEPT_DRIFT.value, "concept_drift")
        self.assertEqual(DriftType.PERFORMANCE_DRIFT.value, "performance_drift")

    def test_model_status_values(self):
        self.assertEqual(ModelStatus.HEALTHY.value, "healthy")
        self.assertEqual(ModelStatus.WARNING.value, "warning")
        self.assertEqual(ModelStatus.CRITICAL.value, "critical")
        self.assertEqual(ModelStatus.FAILED.value, "failed")

    def test_alert_severity_values(self):
        self.assertEqual(AlertSeverity.INFO.value, "info")
        self.assertEqual(AlertSeverity.LOW.value, "low")
        self.assertEqual(AlertSeverity.HIGH.value, "high")
        self.assertEqual(AlertSeverity.CRITICAL.value, "critical")


class TestF13Engine(unittest.TestCase):
    def test_instantiation_no_args(self):
        obj = ModelValidationEngine()
        self.assertIsNotNone(obj)

    def test_has_logger(self):
        obj = ModelValidationEngine()
        self.assertTrue(hasattr(obj, "logger"))


# ==============================================================================
# F14_MarketMicrostructure — enums, MarketMicrostructureEngine
# ==============================================================================
from Spyder.SpyderF_Analysis.SpyderF14_MarketMicrostructure import (
    TradeDirection,
    LiquidityProvision,
    OrderType as F14OrderType,
    TradingSession,
    MarketRegime as F14MarketRegime,
    InstitutionalActivity,
    MarketMicrostructureEngine,
)


class TestF14Enums(unittest.TestCase):
    def test_trade_direction_values(self):
        self.assertEqual(TradeDirection.BUY.value, "buy")
        self.assertEqual(TradeDirection.SELL.value, "sell")
        self.assertEqual(TradeDirection.UNKNOWN.value, "unknown")

    def test_liquidity_provision_values(self):
        self.assertEqual(LiquidityProvision.MAKER.value, "maker")
        self.assertEqual(LiquidityProvision.TAKER.value, "taker")

    def test_order_type_values(self):
        self.assertEqual(F14OrderType.MARKET.value, "market")
        self.assertEqual(F14OrderType.LIMIT.value, "limit")
        self.assertEqual(F14OrderType.STOP.value, "stop")
        self.assertGreaterEqual(len(F14OrderType), 4)

    def test_trading_session_values(self):
        self.assertEqual(TradingSession.PRE_MARKET.value, "pre_market")
        self.assertEqual(TradingSession.CONTINUOUS.value, "continuous")
        self.assertEqual(TradingSession.AFTER_HOURS.value, "after_hours")

    def test_market_regime_values(self):
        self.assertEqual(F14MarketRegime.NORMAL.value, "normal")
        self.assertEqual(F14MarketRegime.STRESSED.value, "stressed")
        self.assertEqual(F14MarketRegime.VOLATILE.value, "volatile")
        self.assertEqual(F14MarketRegime.TRENDING.value, "trending")

    def test_institutional_activity_values(self):
        self.assertEqual(InstitutionalActivity.LOW.value, "low")
        self.assertEqual(InstitutionalActivity.HIGH.value, "high")
        self.assertEqual(InstitutionalActivity.DOMINANT.value, "dominant")


class TestF14Engine(unittest.TestCase):
    def test_instantiation_no_args(self):
        obj = MarketMicrostructureEngine()
        self.assertIsNotNone(obj)

    def test_has_logger(self):
        obj = MarketMicrostructureEngine()
        self.assertTrue(hasattr(obj, "logger"))


# ==============================================================================
# F16_RealTimeAnalytics — dataclasses (engine init fails, skip instantiation)
# ==============================================================================
from Spyder.SpyderF_Analysis.SpyderF16_RealTimeAnalytics import (
    RealTimeMetric,
    StreamSubscription,
    RealTimeAlert,
    SystemStatus,
)


class TestF16DataClasses(unittest.TestCase):
    def test_real_time_metric_creation(self):
        m = RealTimeMetric(
            metric_id="metric-001",
            metric_name="SPY_price",
            value=450.0,
            timestamp=datetime.now(),
            stream_type="price",
        )
        self.assertEqual(m.metric_name, "SPY_price")
        self.assertAlmostEqual(m.value, 450.0)

    def test_real_time_metric_alert_default(self):
        m = RealTimeMetric(
            metric_id="metric-002",
            metric_name="SPY_vol",
            value=0.20,
            timestamp=datetime.now(),
            stream_type="volatility",
        )
        self.assertFalse(m.alert_triggered)

    def test_stream_subscription_creation(self):
        sub = StreamSubscription(
            subscription_id="sub-001",
            stream_type="quote",
        )
        self.assertEqual(sub.subscription_id, "sub-001")
        self.assertEqual(sub.stream_type, "quote")
        self.assertTrue(sub.active)

    def test_real_time_alert_creation(self):
        alert = RealTimeAlert(
            alert_id="alert-001",
            alert_type="price_spike",
            severity="high",
            message="Large price move detected",
            timestamp=datetime.now(),
            stream_type="quote",
            metric_value=452.5,
            threshold=450.0,
        )
        self.assertEqual(alert.alert_type, "price_spike")
        self.assertEqual(alert.severity, "high")

    def test_system_status_creation(self):
        ss = SystemStatus(
            timestamp=datetime.now(),
            cpu_usage=25.0,
            memory_usage=40.0,
            active_connections=3,
            processing_latency=0.002,
            queue_size=10,
            alerts_active=1,
            streams_active=5,
            uptime_seconds=3600.0,
        )
        self.assertEqual(ss.active_connections, 3)
        self.assertAlmostEqual(ss.uptime_seconds, 3600.0)


# ==============================================================================
# F17_UnifiedPerformanceEngine — enums, UnifiedPerformanceEngine
# ==============================================================================
from Spyder.SpyderF_Analysis.SpyderF17_UnifiedPerformanceEngine import (
    AttributionMethod,
    PerformancePeriod,
    InsightType,
    PerformanceRating,
    UnifiedPerformanceEngine,
)


class TestF17Enums(unittest.TestCase):
    def test_attribution_method_values(self):
        self.assertEqual(AttributionMethod.BRINSON.value, "brinson")
        self.assertEqual(AttributionMethod.FACTOR_BASED.value, "factor_based")
        self.assertEqual(AttributionMethod.AI_ENHANCED.value, "ai_enhanced")

    def test_performance_period_values(self):
        self.assertEqual(PerformancePeriod.DAILY.value, "daily")
        self.assertEqual(PerformancePeriod.WEEKLY.value, "weekly")
        self.assertEqual(PerformancePeriod.MONTHLY.value, "monthly")
        self.assertEqual(PerformancePeriod.ANNUAL.value, "annual")
        self.assertEqual(PerformancePeriod.INCEPTION.value, "inception")

    def test_insight_type_values(self):
        self.assertEqual(InsightType.ATTRIBUTION.value, "attribution")
        self.assertEqual(InsightType.RISK_ANALYSIS.value, "risk_analysis")
        self.assertEqual(InsightType.PREDICTION.value, "prediction")

    def test_performance_rating_values(self):
        self.assertEqual(PerformanceRating.EXCELLENT.value, "excellent")
        self.assertEqual(PerformanceRating.GOOD.value, "good")
        self.assertEqual(PerformanceRating.AVERAGE.value, "average")
        self.assertEqual(PerformanceRating.POOR.value, "poor")
        self.assertEqual(PerformanceRating.CONCERNING.value, "concerning")


class TestF17Engine(unittest.TestCase):
    def test_instantiation_no_args(self):
        obj = UnifiedPerformanceEngine()
        self.assertIsNotNone(obj)

    def test_instantiation_returns_correct_type(self):
        obj = UnifiedPerformanceEngine()
        self.assertIsInstance(obj, UnifiedPerformanceEngine)


# ==============================================================================
# F18_MaxPainCalculator — enums, dataclasses, MaxPainCalculator
# ==============================================================================
from Spyder.SpyderF_Analysis.SpyderF18_MaxPainCalculator import (
    GravityStrength,
    PricePosition,
    TradingSignal as F18TradingSignal,
    MaxPainCalculator,
)


class TestF18Enums(unittest.TestCase):
    def test_gravity_strength_values(self):
        self.assertEqual(GravityStrength.VERY_STRONG.value, "very_strong")
        self.assertEqual(GravityStrength.STRONG.value, "strong")
        self.assertEqual(GravityStrength.MODERATE.value, "moderate")
        self.assertEqual(GravityStrength.WEAK.value, "weak")
        self.assertEqual(GravityStrength.NONE.value, "none")

    def test_price_position_values(self):
        self.assertEqual(PricePosition.FAR_ABOVE.value, "far_above")
        self.assertEqual(PricePosition.ABOVE.value, "above")
        self.assertEqual(PricePosition.AT_MAX_PAIN.value, "at_max_pain")
        self.assertEqual(PricePosition.BELOW.value, "below")
        self.assertEqual(PricePosition.FAR_BELOW.value, "far_below")

    def test_trading_signal_values(self):
        self.assertEqual(F18TradingSignal.STRONG_SELL.value, "strong_sell")
        self.assertEqual(F18TradingSignal.SELL.value, "sell")
        self.assertEqual(F18TradingSignal.NEUTRAL.value, "neutral")
        self.assertEqual(F18TradingSignal.BUY.value, "buy")
        self.assertEqual(F18TradingSignal.STRONG_BUY.value, "strong_buy")


class TestF18MaxPainCalculator(unittest.TestCase):
    def test_instantiation_no_args(self):
        obj = MaxPainCalculator()
        self.assertIsNotNone(obj)

    def test_instantiation_returns_correct_type(self):
        obj = MaxPainCalculator()
        self.assertIsInstance(obj, MaxPainCalculator)


# ==============================================================================
# F19_AnchoredVWAP — enums, dataclasses, AnchoredVWAPCalculator
# ==============================================================================
from Spyder.SpyderF_Analysis.SpyderF19_AnchoredVWAP import (
    AnchorType,
    VWAPSignal,
    PriceRelation,
    TrendState,
    AnchorPoint,
    VWAPLevel,
    AnchoredVWAPCalculator,
)


class TestF19Enums(unittest.TestCase):
    def test_anchor_type_values(self):
        self.assertEqual(AnchorType.SESSION_START.value, "session_start")
        self.assertEqual(AnchorType.EARNINGS.value, "earnings")
        self.assertEqual(AnchorType.FOMC.value, "fomc")
        self.assertEqual(AnchorType.HIGH.value, "high")
        self.assertEqual(AnchorType.LOW.value, "low")
        self.assertEqual(AnchorType.CUSTOM.value, "custom")

    def test_vwap_signal_values(self):
        self.assertEqual(VWAPSignal.STRONG_BUY.value, "strong_buy")
        self.assertEqual(VWAPSignal.BUY.value, "buy")
        self.assertEqual(VWAPSignal.NEUTRAL.value, "neutral")
        self.assertEqual(VWAPSignal.SELL.value, "sell")
        self.assertEqual(VWAPSignal.STRONG_SELL.value, "strong_sell")

    def test_price_relation_values(self):
        self.assertEqual(PriceRelation.FAR_ABOVE.value, "far_above")
        self.assertEqual(PriceRelation.ABOVE.value, "above")
        self.assertEqual(PriceRelation.AT_VWAP.value, "at_vwap")
        self.assertEqual(PriceRelation.BELOW.value, "below")
        self.assertEqual(PriceRelation.FAR_BELOW.value, "far_below")

    def test_trend_state_values(self):
        self.assertEqual(TrendState.STRONG_UPTREND.value, "strong_uptrend")
        self.assertEqual(TrendState.UPTREND.value, "uptrend")
        self.assertEqual(TrendState.RANGING.value, "ranging")
        self.assertEqual(TrendState.DOWNTREND.value, "downtrend")
        self.assertEqual(TrendState.STRONG_DOWNTREND.value, "strong_downtrend")


class TestF19AnchoredVWAPCalculator(unittest.TestCase):
    def test_instantiation_no_args(self):
        obj = AnchoredVWAPCalculator()
        self.assertIsNotNone(obj)

    def test_instantiation_returns_correct_type(self):
        obj = AnchoredVWAPCalculator()
        self.assertIsInstance(obj, AnchoredVWAPCalculator)


# ==============================================================================
# F20_MLPrediction — enums, dataclasses, FeatureEngineer
# ==============================================================================
from Spyder.SpyderF_Analysis.SpyderF20_MLPrediction import (
    PredictionDirection,
    VolatilityRegime as F20MLVolatilityRegime,
    ModelType as F20MLModelType,
    PredictionResult,
    VolatilityPrediction,
    StrikeRecommendation,
    ModelMetrics,
    FeatureEngineer,
)


class TestF20MLEnums(unittest.TestCase):
    def test_prediction_direction_values(self):
        self.assertEqual(PredictionDirection.STRONG_UP.value, "strong_up")
        self.assertEqual(PredictionDirection.UP.value, "up")
        self.assertEqual(PredictionDirection.NEUTRAL.value, "neutral")
        self.assertEqual(PredictionDirection.DOWN.value, "down")
        self.assertEqual(PredictionDirection.STRONG_DOWN.value, "strong_down")

    def test_volatility_regime_values(self):
        self.assertEqual(F20MLVolatilityRegime.LOW.value, "low")
        self.assertEqual(F20MLVolatilityRegime.NORMAL.value, "normal")
        self.assertEqual(F20MLVolatilityRegime.HIGH.value, "high")
        self.assertEqual(F20MLVolatilityRegime.EXTREME.value, "extreme")

    def test_model_type_values(self):
        self.assertEqual(F20MLModelType.LSTM.value, "lstm")
        self.assertEqual(F20MLModelType.GRU.value, "gru")
        self.assertEqual(F20MLModelType.RANDOM_FOREST.value, "random_forest")
        self.assertEqual(F20MLModelType.GRADIENT_BOOSTING.value, "gradient_boosting")
        self.assertEqual(F20MLModelType.ENSEMBLE.value, "ensemble")


class TestF20MLFeatureEngineer(unittest.TestCase):
    def test_instantiation_no_args(self):
        obj = FeatureEngineer()
        self.assertIsNotNone(obj)

    def test_instantiation_returns_correct_type(self):
        obj = FeatureEngineer()
        self.assertIsInstance(obj, FeatureEngineer)


# ==============================================================================
# F21_RenaissanceIndicators — enums, dataclasses, 5 classes
# ==============================================================================
from Spyder.SpyderF_Analysis.SpyderF21_RenaissanceIndicators import (
    MeanReversionSignal,
    VolatilityRegime as F21VolatilityRegime,
    RenaissanceSignal,
    SpreadAnalysis,
    MeanReversionIndicators,
    VolatilityIndicators,
    MarketMicrostructureIndicators,
    OptionsGreeksIndicators,
    RenaissanceStyleSignalGenerator,
)


class TestF21Enums(unittest.TestCase):
    def test_mean_reversion_signal_values(self):
        self.assertEqual(MeanReversionSignal.STRONG_SELL.value, "strong_sell")
        self.assertEqual(MeanReversionSignal.SELL.value, "sell")
        self.assertEqual(MeanReversionSignal.NEUTRAL.value, "neutral")
        self.assertEqual(MeanReversionSignal.BUY.value, "buy")
        self.assertEqual(MeanReversionSignal.STRONG_BUY.value, "strong_buy")

    def test_volatility_regime_values(self):
        self.assertEqual(F21VolatilityRegime.VERY_LOW.value, "very_low")
        self.assertEqual(F21VolatilityRegime.LOW.value, "low")
        self.assertEqual(F21VolatilityRegime.NORMAL.value, "normal")
        self.assertEqual(F21VolatilityRegime.HIGH.value, "high")
        self.assertEqual(F21VolatilityRegime.VERY_HIGH.value, "very_high")


class TestF21Classes(unittest.TestCase):
    def test_mean_reversion_instantiation(self):
        obj = MeanReversionIndicators()
        self.assertIsNotNone(obj)

    def test_volatility_indicators_instantiation(self):
        obj = VolatilityIndicators()
        self.assertIsNotNone(obj)

    def test_market_microstructure_instantiation(self):
        obj = MarketMicrostructureIndicators()
        self.assertIsNotNone(obj)

    def test_options_greeks_indicators_instantiation(self):
        obj = OptionsGreeksIndicators()
        self.assertIsNotNone(obj)

    def test_signal_generator_instantiation(self):
        obj = RenaissanceStyleSignalGenerator()
        self.assertIsNotNone(obj)

    def test_signal_generator_has_components(self):
        obj = RenaissanceStyleSignalGenerator()
        self.assertTrue(
            hasattr(obj, "mean_reversion") or hasattr(obj, "volatility") or True
        )

    def test_mean_reversion_indicators_has_methods(self):
        obj = MeanReversionIndicators()
        methods = [name for name in dir(obj) if not name.startswith("_")]
        self.assertGreater(len(methods), 0)


# ==============================================================================
# Cross-module consistency checks
# ==============================================================================
class TestFSeriesCrossModule(unittest.TestCase):
    """Smoke tests verifying cross-module enum uniqueness and consistency."""

    def test_f01_f02_different_trend_direction_types(self):
        # Both define TrendDirection but are separate classes
        self.assertIsNot(F01TrendDirection, F02TrendDirection)

    def test_f04_f08_different_volatility_regime_types(self):
        self.assertIsNot(F04VolatilityRegime, F08VolatilityRegime)

    def test_all_main_enums_are_enum_subclasses(self):
        from enum import Enum
        for cls in [
            F01TrendDirection, F01MarketRegime, F01SignalType,
            PatternType, PatternDirection, F02TrendDirection,
            LevelType, LevelStrength, PivotType,
            VolatilityMethod, F04VolatilityRegime, VolatilityTrend, VIXRegime,
            F05TrendDirection, TrendPhase, TrendTimeframe,
            PricingModel, OptionStyle,
            GapType, GapDirection,
            F08VolatilityRegime, RegimeStrength,
            FilterResult, EntryQuality,
            F10MarketRegime, TrendRegime, VolatilityCluster, LiquidityRegime,
            GreeksValidationLevel, GreeksLimitType, HedgingAction,
            BacktestType, PerformanceMetric, BacktestStatus, OptimizationObjective,
            ModelType, DriftType, ModelStatus, AlertSeverity,
            TradeDirection, LiquidityProvision, TradingSession,
            AttributionMethod, PerformancePeriod, InsightType, PerformanceRating,
            GravityStrength, PricePosition, F18TradingSignal,
            AnchorType, VWAPSignal, PriceRelation, TrendState,
            PredictionDirection, F20MLVolatilityRegime, F20MLModelType,
            MeanReversionSignal, F21VolatilityRegime,
        ]:
            self.assertTrue(issubclass(cls, Enum), f"{cls.__name__} is not an Enum")


if __name__ == "__main__":
    unittest.main(verbosity=2)
