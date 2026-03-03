#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT60_FSeriesAnalysisTests.py
Purpose: Unit tests for F-series analysis modules (T60)

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-03-03 Time: 07:00:00

Module Description:
    Covers two self-contained F-series analysis modules with no GUI,
    broker, or ML dependencies:
      - SpyderF04_VolatilityAnalysis  — multi-method volatility calculation,
                                        regime/trend/percentile classification
      - SpyderF18_MaxPainCalculator   — max-pain position classification,
                                        gravity strength, trading signals,
                                        MaxPainResult properties

Change Log:
    2026-03-03:
        - Created (T60: F-series analysis test suite)
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import importlib
import importlib.util
import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

# ==============================================================================
# PATH SETUP
# ==============================================================================
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _load(rel_path: str):
    """Load a module from a repo-relative path via importlib."""
    full = _REPO_ROOT / rel_path
    spec = importlib.util.spec_from_file_location(full.stem, full)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_f04 = _load("Spyder/SpyderF_Analysis/SpyderF04_VolatilityAnalysis.py")
_f18 = _load("Spyder/SpyderF_Analysis/SpyderF18_MaxPainCalculator.py")

# ── F04 symbols ────────────────────────────────────────────────────────────────
VolatilityAnalyzer = _f04.VolatilityAnalyzer
VolatilityMethod   = _f04.VolatilityMethod
VolatilityRegime   = _f04.VolatilityRegime
VolatilityTrend    = _f04.VolatilityTrend
VIXRegime          = _f04.VIXRegime

LOW_VOL_THRESHOLD      = _f04.LOW_VOL_THRESHOLD       # 0.10
NORMAL_VOL_HIGH        = _f04.NORMAL_VOL_HIGH          # 0.20
HIGH_VOL_THRESHOLD     = _f04.HIGH_VOL_THRESHOLD       # 0.25
EXTREME_VOL_THRESHOLD  = _f04.EXTREME_VOL_THRESHOLD    # 0.35

VIX_LOW        = _f04.VIX_LOW         # 12
VIX_NORMAL_HIGH = _f04.VIX_NORMAL_HIGH  # 20
VIX_HIGH       = _f04.VIX_HIGH        # 25
VIX_EXTREME    = _f04.VIX_EXTREME     # 35

TRADING_DAYS_YEAR = _f04.TRADING_DAYS_YEAR  # 252

# ── F18 symbols ────────────────────────────────────────────────────────────────
MaxPainCalculator  = _f18.MaxPainCalculator
MaxPainResult      = _f18.MaxPainResult
StrikePainAnalysis = _f18.StrikePainAnalysis
GravityStrength    = _f18.GravityStrength
PricePosition      = _f18.PricePosition
TradingSignal      = _f18.TradingSignal


# ==============================================================================
# HELPERS
# ==============================================================================

try:
    import pandas as pd
    import numpy as np
    _pd_available = True
except ImportError:
    _pd_available = False


def _ohlcv(n: int = 30, start_price: float = 450.0, step: float = 0.5):
    """Build a minimal OHLCV DataFrame for volatility calculations."""
    closes = [start_price + i * step for i in range(n)]
    return pd.DataFrame({
        "open":   [c - 0.25 for c in closes],
        "high":   [c + 1.0  for c in closes],
        "low":    [c - 1.0  for c in closes],
        "close":  closes,
        "volume": [1_000_000] * n,
    })


def _make_max_pain_result(
    symbol: str = "SPY",
    expiry: date = date(2026, 3, 21),
    max_pain_strike: float = 455.0,
    current_price: float = 455.0,
    distance_dollars: float = 0.0,
    distance_percent: float = 0.0,
    position: "PricePosition" = None,
    gravity_strength: "GravityStrength" = None,
    trading_signal: "TradingSignal" = None,
    pinning_probability: float = 0.25,
    days_to_expiry: int = 3,
    total_call_oi: int = 100_000,
    total_put_oi: int = 100_000,
    put_call_oi_ratio: float = 1.0,
) -> "MaxPainResult":
    """Construct a MaxPainResult with sensible defaults."""
    return MaxPainResult(
        symbol=symbol,
        expiry=expiry,
        timestamp=datetime.now(),
        max_pain_strike=max_pain_strike,
        current_price=current_price,
        distance_dollars=distance_dollars,
        distance_percent=distance_percent,
        position=position or PricePosition.AT_MAX_PAIN,
        gravity_strength=gravity_strength or GravityStrength.NONE,
        trading_signal=trading_signal or TradingSignal.NEUTRAL,
        pinning_probability=pinning_probability,
        days_to_expiry=days_to_expiry,
        total_call_oi=total_call_oi,
        total_put_oi=total_put_oi,
        put_call_oi_ratio=put_call_oi_ratio,
    )


# ==============================================================================
# F04 — VolatilityAnalyzer tests
# ==============================================================================

class TestVolatilityAnalyzerConstruction(unittest.TestCase):
    """VolatilityAnalyzer — construction and defaults."""

    def test_creates_instance(self):
        va = VolatilityAnalyzer()
        self.assertIsInstance(va, VolatilityAnalyzer)

    def test_has_logger(self):
        va = VolatilityAnalyzer()
        self.assertIsNotNone(va.logger)

    def test_default_method_is_yang_zhang(self):
        va = VolatilityAnalyzer()
        self.assertEqual(va.default_method, VolatilityMethod.YANG_ZHANG)

    def test_volatility_history_starts_empty(self):
        va = VolatilityAnalyzer()
        self.assertEqual(va.volatility_history, [])

    def test_regime_history_starts_empty(self):
        va = VolatilityAnalyzer()
        self.assertEqual(va.regime_history, [])


class TestVolatilityEnums(unittest.TestCase):
    """Enum members exist and are unique."""

    def test_volatility_method_has_expected_members(self):
        expected = {"CLOSE_TO_CLOSE", "PARKINSON", "GARMAN_KLASS",
                    "ROGERS_SATCHELL", "YANG_ZHANG", "GARCH", "EWMA"}
        self.assertEqual({m.name for m in VolatilityMethod}, expected)

    def test_volatility_regime_has_five_levels(self):
        self.assertEqual(len(list(VolatilityRegime)), 5)

    def test_volatility_trend_has_four_directions(self):
        self.assertEqual(len(list(VolatilityTrend)), 4)

    def test_vix_regime_has_five_levels(self):
        self.assertEqual(len(list(VIXRegime)), 5)

    def test_all_regimes_unique(self):
        # No duplicated enum values
        values = [r.value for r in VolatilityRegime]
        self.assertEqual(len(values), len(set(values)))


class TestClassifyVolatilityRegime(unittest.TestCase):
    """_classify_volatility_regime — threshold-based classification."""

    def setUp(self):
        self.va = VolatilityAnalyzer()

    def test_low_regime_below_threshold(self):
        # Below LOW_VOL_THRESHOLD (0.10)
        result = self.va._classify_volatility_regime(0.05)
        self.assertEqual(result, VolatilityRegime.LOW)

    def test_normal_regime_between_low_and_high(self):
        # Between 0.10 and 0.20
        result = self.va._classify_volatility_regime(0.15)
        self.assertEqual(result, VolatilityRegime.NORMAL)

    def test_elevated_regime(self):
        # Between 0.20 and 0.25
        result = self.va._classify_volatility_regime(0.22)
        self.assertEqual(result, VolatilityRegime.ELEVATED)

    def test_high_regime(self):
        # Between 0.25 and 0.35
        result = self.va._classify_volatility_regime(0.30)
        self.assertEqual(result, VolatilityRegime.HIGH)

    def test_extreme_regime_above_threshold(self):
        # Above EXTREME_VOL_THRESHOLD (0.35)
        result = self.va._classify_volatility_regime(0.50)
        self.assertEqual(result, VolatilityRegime.EXTREME)

    def test_exact_low_threshold(self):
        # At exactly LOW_VOL_THRESHOLD — should be NORMAL (< is strict)
        result = self.va._classify_volatility_regime(LOW_VOL_THRESHOLD)
        self.assertEqual(result, VolatilityRegime.NORMAL)

    def test_exact_high_threshold(self):
        # At exactly HIGH_VOL_THRESHOLD — should be HIGH (< is strict)
        result = self.va._classify_volatility_regime(HIGH_VOL_THRESHOLD)
        self.assertEqual(result, VolatilityRegime.HIGH)


class TestClassifyVIXRegime(unittest.TestCase):
    """_classify_vix_regime — five VIX zones."""

    def setUp(self):
        self.va = VolatilityAnalyzer()

    def test_complacent_below_12(self):
        self.assertEqual(self.va._classify_vix_regime(10), VIXRegime.COMPLACENT)

    def test_normal_between_12_and_20(self):
        self.assertEqual(self.va._classify_vix_regime(15), VIXRegime.NORMAL)

    def test_anxious_between_20_and_25(self):
        self.assertEqual(self.va._classify_vix_regime(22), VIXRegime.ANXIOUS)

    def test_fearful_between_25_and_35(self):
        self.assertEqual(self.va._classify_vix_regime(30), VIXRegime.FEARFUL)

    def test_panic_above_35(self):
        self.assertEqual(self.va._classify_vix_regime(40), VIXRegime.PANIC)

    def test_exact_vix_low_threshold(self):
        # At exactly VIX_LOW (12) → NORMAL (strict <)
        self.assertEqual(self.va._classify_vix_regime(VIX_LOW), VIXRegime.NORMAL)


class TestAnalyzeVolatilityTrend(unittest.TestCase):
    """_analyze_volatility_trend — short/long vol comparison."""

    def setUp(self):
        self.va = VolatilityAnalyzer()

    def test_stable_when_single_window(self):
        result = self.va._analyze_volatility_trend({20: 0.15})
        self.assertEqual(result, VolatilityTrend.STABLE)

    def test_increasing_when_short_vol_much_higher(self):
        # short (5,10) >> long (20,30): ratio > 1.2 → INCREASING
        vols = {5: 0.30, 10: 0.28, 20: 0.15, 30: 0.14}
        result = self.va._analyze_volatility_trend(vols)
        self.assertEqual(result, VolatilityTrend.INCREASING)

    def test_decreasing_when_short_vol_much_lower(self):
        # short (5,10) << long (20,30): ratio < 0.8 → DECREASING
        vols = {5: 0.10, 10: 0.10, 20: 0.20, 30: 0.22}
        result = self.va._analyze_volatility_trend(vols)
        self.assertEqual(result, VolatilityTrend.DECREASING)

    def test_stable_when_balanced(self):
        # ratio ≈ 1.0, low coefficient of variation → STABLE
        vols = {5: 0.15, 10: 0.15, 20: 0.15, 30: 0.15}
        result = self.va._analyze_volatility_trend(vols)
        self.assertEqual(result, VolatilityTrend.STABLE)

    def test_returns_volatility_trend_instance(self):
        vols = {5: 0.15, 10: 0.15, 20: 0.15}
        result = self.va._analyze_volatility_trend(vols)
        self.assertIsInstance(result, VolatilityTrend)


class TestCalculateVolatilityPercentile(unittest.TestCase):
    """_calculate_volatility_percentile — bucket-based when history is thin."""

    def setUp(self):
        self.va = VolatilityAnalyzer()

    def test_below_10pct_returns_20th_percentile(self):
        result = self.va._calculate_volatility_percentile(0.08)
        self.assertAlmostEqual(result, 20.0, places=5)

    def test_between_10_and_15_returns_40th_percentile(self):
        result = self.va._calculate_volatility_percentile(0.12)
        self.assertAlmostEqual(result, 40.0, places=5)

    def test_between_15_and_20_returns_60th_percentile(self):
        result = self.va._calculate_volatility_percentile(0.17)
        self.assertAlmostEqual(result, 60.0, places=5)

    def test_between_20_and_25_returns_80th_percentile(self):
        result = self.va._calculate_volatility_percentile(0.22)
        self.assertAlmostEqual(result, 80.0, places=5)

    def test_above_25_returns_90th_percentile(self):
        result = self.va._calculate_volatility_percentile(0.30)
        self.assertAlmostEqual(result, 90.0, places=5)

    def test_result_is_float(self):
        self.assertIsInstance(self.va._calculate_volatility_percentile(0.15), float)


class TestCalculateTermStructure(unittest.TestCase):
    """_calculate_term_structure — normalized to 30-day vol."""

    def setUp(self):
        self.va = VolatilityAnalyzer()

    def test_30_day_normalizes_to_1(self):
        vols = {20: 0.12, 30: 0.15, 60: 0.18}
        result = self.va._calculate_term_structure(vols)
        self.assertAlmostEqual(result[30], 1.0, places=5)

    def test_higher_window_higher_ratio_when_vol_increases(self):
        vols = {20: 0.12, 30: 0.15, 60: 0.20}
        result = self.va._calculate_term_structure(vols)
        self.assertGreater(result[60], result[30])

    def test_returns_dict(self):
        vols = {20: 0.15, 30: 0.15}
        result = self.va._calculate_term_structure(vols)
        self.assertIsInstance(result, dict)

    def test_zero_base_vol_gives_ones(self):
        # Edge case: base_vol == 0 → all entries 1.0
        vols = {20: 0.0, 30: 0.0, 60: 0.0}
        result = self.va._calculate_term_structure(vols)
        for v in result.values():
            self.assertAlmostEqual(v, 1.0, places=5)


@unittest.skipUnless(_pd_available, "pandas/numpy required")
class TestCalculateVolatility(unittest.TestCase):
    """VolatilityAnalyzer.calculate_volatility — dict output shape."""

    def setUp(self):
        self.va = VolatilityAnalyzer()
        self.df = _ohlcv(n=40)

    def test_returns_dict_with_required_keys(self):
        result = self.va.calculate_volatility(self.df, window=10,
                                               method=VolatilityMethod.CLOSE_TO_CLOSE)
        self.assertIn("volatility", result)
        self.assertIn("annualized", result)
        self.assertIn("method", result)
        self.assertIn("window", result)

    def test_method_name_matches_enum(self):
        result = self.va.calculate_volatility(self.df, window=10,
                                               method=VolatilityMethod.CLOSE_TO_CLOSE)
        self.assertEqual(result["method"], "CLOSE_TO_CLOSE")

    def test_window_stored_in_result(self):
        result = self.va.calculate_volatility(self.df, window=15,
                                               method=VolatilityMethod.CLOSE_TO_CLOSE)
        self.assertEqual(result["window"], 15)

    def test_annualized_is_larger_than_daily_vol(self):
        result = self.va.calculate_volatility(self.df, window=10,
                                               method=VolatilityMethod.CLOSE_TO_CLOSE)
        self.assertGreaterEqual(result["annualized"], result["volatility"])

    def test_parkinson_method_accepted(self):
        result = self.va.calculate_volatility(self.df, window=10,
                                               method=VolatilityMethod.PARKINSON)
        self.assertIn("volatility", result)

    def test_ewma_method_accepted(self):
        result = self.va.calculate_volatility(self.df, window=10,
                                               method=VolatilityMethod.EWMA)
        self.assertIn("volatility", result)

    def test_volatility_non_negative(self):
        result = self.va.calculate_volatility(self.df, window=10,
                                               method=VolatilityMethod.CLOSE_TO_CLOSE)
        self.assertGreaterEqual(result["volatility"], 0.0)

    def test_short_data_uses_default(self):
        # Less data than window → returns default 0.15 / sqrt(252)
        short_df = _ohlcv(n=5)
        result = self.va.calculate_volatility(short_df, window=20,
                                               method=VolatilityMethod.CLOSE_TO_CLOSE)
        import math
        expected_default = 0.15 / math.sqrt(TRADING_DAYS_YEAR)
        self.assertAlmostEqual(result["volatility"], expected_default, places=5)


# ==============================================================================
# F18 — MaxPainCalculator tests
# ==============================================================================

class TestF18Enums(unittest.TestCase):
    """F18 enum members exist and have expected names."""

    def test_gravity_strength_members(self):
        expected = {"VERY_STRONG", "STRONG", "MODERATE", "WEAK", "NONE"}
        self.assertEqual({m.name for m in GravityStrength}, expected)

    def test_price_position_members(self):
        expected = {"FAR_ABOVE", "ABOVE", "AT_MAX_PAIN", "BELOW", "FAR_BELOW"}
        self.assertEqual({m.name for m in PricePosition}, expected)

    def test_trading_signal_members(self):
        expected = {"STRONG_SELL", "SELL", "NEUTRAL", "BUY", "STRONG_BUY"}
        self.assertEqual({m.name for m in TradingSignal}, expected)


class TestMaxPainCalculatorConstruction(unittest.TestCase):
    """MaxPainCalculator — construction with no data provider."""

    def test_creates_instance_with_no_provider(self):
        calc = MaxPainCalculator(data_provider=None)
        self.assertIsInstance(calc, MaxPainCalculator)

    def test_cache_starts_empty(self):
        calc = MaxPainCalculator(data_provider=None)
        self.assertEqual(len(calc._cache), 0)

    def test_chain_cache_starts_empty(self):
        calc = MaxPainCalculator(data_provider=None)
        self.assertEqual(len(calc._chain_cache), 0)


class TestClassifyPosition(unittest.TestCase):
    """MaxPainCalculator._classify_position — threshold-based classification."""

    def setUp(self):
        self.calc = MaxPainCalculator(data_provider=None)

    def test_far_above_above_2pct(self):
        self.assertEqual(self.calc._classify_position(2.5), PricePosition.FAR_ABOVE)

    def test_above_between_0_5_and_2(self):
        self.assertEqual(self.calc._classify_position(1.0), PricePosition.ABOVE)

    def test_at_max_pain_near_zero(self):
        self.assertEqual(self.calc._classify_position(0.0), PricePosition.AT_MAX_PAIN)

    def test_at_max_pain_just_negative(self):
        self.assertEqual(self.calc._classify_position(-0.3), PricePosition.AT_MAX_PAIN)

    def test_below_between_neg_2_and_neg_0_5(self):
        self.assertEqual(self.calc._classify_position(-1.0), PricePosition.BELOW)

    def test_far_below_below_neg_2(self):
        self.assertEqual(self.calc._classify_position(-3.0), PricePosition.FAR_BELOW)

    def test_exact_half_percent_boundary(self):
        # Exactly 0.5 → ABOVE (> 0.5 is False, but 0.5 > -0.5 → AT_MAX_PAIN)
        # The condition is: distance_percent > 0.5 → ABOVE, else if > -0.5 → AT_MAX_PAIN
        # So 0.5 → NOT > 0.5 → falls to AT_MAX_PAIN check
        self.assertEqual(self.calc._classify_position(0.5), PricePosition.AT_MAX_PAIN)

    def test_exact_neg_2_boundary(self):
        # Exactly -2.0 → not > -2.0 → FAR_BELOW
        self.assertEqual(self.calc._classify_position(-2.0), PricePosition.FAR_BELOW)


class TestCalculateGravityStrength(unittest.TestCase):
    """MaxPainCalculator._calculate_gravity_strength — score-based enum."""

    def setUp(self):
        self.calc = MaxPainCalculator(data_provider=None)

    def test_very_strong_near_expiry_moderate_distance(self):
        # days_to_expiry=1 → days_factor=2.0
        # abs_distance=1.0 → distance_factor=1.5
        # score = 3.0 → VERY_STRONG
        result = self.calc._calculate_gravity_strength(1.0, days_to_expiry=1)
        self.assertEqual(result, GravityStrength.VERY_STRONG)

    def test_strong_near_expiry_far_distance(self):
        # days_to_expiry=1 → days_factor=2.0
        # abs_distance=2.0 → distance_factor=1.0
        # score = 2.0 → STRONG (not VERY_STRONG since < 2.5)
        result = self.calc._calculate_gravity_strength(2.0, days_to_expiry=1)
        self.assertEqual(result, GravityStrength.STRONG)

    def test_weak_far_from_expiry_at_max_pain(self):
        # days_to_expiry=30 → days_factor=0.5
        # abs_distance=0.0 → distance_factor=0.5
        # score=0.25 → NONE
        result = self.calc._calculate_gravity_strength(0.0, days_to_expiry=30)
        self.assertEqual(result, GravityStrength.NONE)

    def test_moderate_intraweek_moderate_distance(self):
        # days_to_expiry=7 → days_factor=1.0
        # abs_distance=1.0 → distance_factor=1.5
        # score=1.5 → STRONG (>= 1.5 but < 2.5)
        result = self.calc._calculate_gravity_strength(1.0, days_to_expiry=7)
        self.assertEqual(result, GravityStrength.STRONG)

    def test_returns_gravity_strength_enum(self):
        result = self.calc._calculate_gravity_strength(1.5, days_to_expiry=3)
        self.assertIsInstance(result, GravityStrength)


class TestGenerateSignal(unittest.TestCase):
    """MaxPainCalculator._generate_signal — rules-based signal."""

    def setUp(self):
        self.calc = MaxPainCalculator(data_provider=None)

    def test_neutral_when_too_far_from_expiry(self):
        result = self.calc._generate_signal(
            PricePosition.FAR_ABOVE,
            GravityStrength.VERY_STRONG,
            days_to_expiry=15,
        )
        self.assertEqual(result, TradingSignal.NEUTRAL)

    def test_neutral_when_gravity_none(self):
        result = self.calc._generate_signal(
            PricePosition.FAR_ABOVE,
            GravityStrength.NONE,
            days_to_expiry=3,
        )
        self.assertEqual(result, TradingSignal.NEUTRAL)

    def test_strong_sell_far_above_very_strong_gravity(self):
        result = self.calc._generate_signal(
            PricePosition.FAR_ABOVE,
            GravityStrength.VERY_STRONG,
            days_to_expiry=3,
        )
        self.assertEqual(result, TradingSignal.STRONG_SELL)

    def test_sell_far_above_moderate_gravity(self):
        result = self.calc._generate_signal(
            PricePosition.FAR_ABOVE,
            GravityStrength.MODERATE,
            days_to_expiry=3,
        )
        self.assertEqual(result, TradingSignal.SELL)

    def test_neutral_at_max_pain(self):
        result = self.calc._generate_signal(
            PricePosition.AT_MAX_PAIN,
            GravityStrength.VERY_STRONG,
            days_to_expiry=1,
        )
        self.assertEqual(result, TradingSignal.NEUTRAL)

    def test_buy_below_very_strong_gravity(self):
        result = self.calc._generate_signal(
            PricePosition.BELOW,
            GravityStrength.VERY_STRONG,
            days_to_expiry=5,
        )
        self.assertEqual(result, TradingSignal.BUY)

    def test_strong_buy_far_below_very_strong_gravity(self):
        result = self.calc._generate_signal(
            PricePosition.FAR_BELOW,
            GravityStrength.VERY_STRONG,
            days_to_expiry=2,
        )
        self.assertEqual(result, TradingSignal.STRONG_BUY)

    def test_buy_far_below_weak_gravity(self):
        result = self.calc._generate_signal(
            PricePosition.FAR_BELOW,
            GravityStrength.MODERATE,
            days_to_expiry=2,
        )
        self.assertEqual(result, TradingSignal.BUY)


class TestEmptyResult(unittest.TestCase):
    """MaxPainCalculator._empty_result — returns zeroed MaxPainResult."""

    def setUp(self):
        self.calc = MaxPainCalculator(data_provider=None)

    def test_returns_max_pain_result(self):
        r = self.calc._empty_result("SPY", date(2026, 3, 21))
        self.assertIsInstance(r, MaxPainResult)

    def test_symbol_matches(self):
        r = self.calc._empty_result("SPY", date(2026, 3, 21))
        self.assertEqual(r.symbol, "SPY")

    def test_expiry_matches(self):
        expiry = date(2026, 3, 21)
        r = self.calc._empty_result("SPY", expiry)
        self.assertEqual(r.expiry, expiry)

    def test_max_pain_strike_is_zero(self):
        r = self.calc._empty_result("SPY", date(2026, 3, 21))
        self.assertEqual(r.max_pain_strike, 0)

    def test_current_price_is_zero(self):
        r = self.calc._empty_result("SPY", date(2026, 3, 21))
        self.assertEqual(r.current_price, 0)

    def test_trading_signal_is_neutral(self):
        r = self.calc._empty_result("SPY", date(2026, 3, 21))
        self.assertEqual(r.trading_signal, TradingSignal.NEUTRAL)


class TestMaxPainResultProperties(unittest.TestCase):
    """MaxPainResult — computed properties."""

    def test_is_actionable_true_when_valid(self):
        r = _make_max_pain_result(
            trading_signal=TradingSignal.SELL,
            days_to_expiry=3,
            distance_percent=1.0,
        )
        self.assertTrue(r.is_actionable)

    def test_is_not_actionable_when_neutral(self):
        r = _make_max_pain_result(
            trading_signal=TradingSignal.NEUTRAL,
            days_to_expiry=3,
            distance_percent=1.0,
        )
        self.assertFalse(r.is_actionable)

    def test_is_not_actionable_when_too_many_days(self):
        r = _make_max_pain_result(
            trading_signal=TradingSignal.SELL,
            days_to_expiry=10,   # must be <= 7
            distance_percent=1.0,
        )
        self.assertFalse(r.is_actionable)

    def test_is_not_actionable_when_distance_too_small(self):
        r = _make_max_pain_result(
            trading_signal=TradingSignal.SELL,
            days_to_expiry=3,
            distance_percent=0.4,   # abs < 0.5
        )
        self.assertFalse(r.is_actionable)

    def test_expected_move_positive_when_above_max_pain(self):
        # current < max_pain → expected_move > 0
        r = _make_max_pain_result(max_pain_strike=460.0, current_price=455.0)
        self.assertGreater(r.expected_move_to_max_pain, 0.0)

    def test_expected_move_negative_when_below_max_pain(self):
        # current > max_pain → expected_move < 0
        r = _make_max_pain_result(max_pain_strike=450.0, current_price=455.0)
        self.assertLess(r.expected_move_to_max_pain, 0.0)

    def test_expected_move_zero_at_max_pain(self):
        r = _make_max_pain_result(max_pain_strike=455.0, current_price=455.0)
        self.assertAlmostEqual(r.expected_move_to_max_pain, 0.0, places=5)

    def test_expected_move_magnitude(self):
        r = _make_max_pain_result(max_pain_strike=460.0, current_price=455.0)
        self.assertAlmostEqual(r.expected_move_to_max_pain, 5.0, places=5)


class TestMaxPainResultToDict(unittest.TestCase):
    """MaxPainResult.to_dict — key presence and types."""

    def setUp(self):
        self.r = _make_max_pain_result(
            symbol="SPY",
            max_pain_strike=455.0,
            current_price=454.0,
            trading_signal=TradingSignal.BUY,
            days_to_expiry=5,
            distance_percent=0.8,
        )
        self.d = self.r.to_dict()

    def test_returns_dict(self):
        self.assertIsInstance(self.d, dict)

    def test_symbol_key_present(self):
        self.assertIn("symbol", self.d)
        self.assertEqual(self.d["symbol"], "SPY")

    def test_max_pain_strike_key_present(self):
        self.assertIn("max_pain_strike", self.d)

    def test_trading_signal_is_string_value(self):
        self.assertIsInstance(self.d["trading_signal"], str)

    def test_position_is_string_value(self):
        self.assertIsInstance(self.d["position"], str)

    def test_is_actionable_key_present(self):
        self.assertIn("is_actionable", self.d)
        self.assertIsInstance(self.d["is_actionable"], bool)

    def test_expected_move_key_present(self):
        self.assertIn("expected_move", self.d)


class TestStrikePainAnalysisToDict(unittest.TestCase):
    """StrikePainAnalysis.to_dict — basic smoke test."""

    def test_to_dict_returns_expected_keys(self):
        spa = StrikePainAnalysis(
            strike=455.0,
            call_oi=50000,
            put_oi=60000,
            call_pain=1_000_000.0,
            put_pain=1_200_000.0,
            total_pain=2_200_000.0,
            call_value=3.00,
            put_value=5.00,
        )
        d = spa.to_dict()
        for key in ("strike", "call_oi", "put_oi", "call_pain", "put_pain", "total_pain"):
            self.assertIn(key, d)

    def test_strike_value_preserved(self):
        spa = StrikePainAnalysis(
            strike=460.0,
            call_oi=10000,
            put_oi=20000,
            call_pain=500_000.0,
            put_pain=800_000.0,
            total_pain=1_300_000.0,
            call_value=2.00,
            put_value=4.00,
        )
        self.assertAlmostEqual(spa.to_dict()["strike"], 460.0, places=5)


# ==============================================================================
# ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
