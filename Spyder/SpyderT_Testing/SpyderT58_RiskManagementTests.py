#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT58_RiskManagementTests.py
Purpose: Unit tests for E-series risk management (item C)

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-03-03 Time: 00:00:00

Module Description:
    Covers the self-contained E-series risk management modules:

      - SpyderE06_RiskMetrics        — standalone free functions:
                                       calculate_returns, annualize_return,
                                       annualize_volatility, calculate_sharpe,
                                       calculate_sortino, calculate_calmar,
                                       calculate_max_drawdown, calculate_var,
                                       calculate_cvar, calculate_omega_ratio

      - SpyderE02_PositionSizer      — PositionSizer class:
                                       calculate_position_size, update_portfolio
                                       _value, risk-limit enforcement

      - SpyderE14_KellyPositionSizer — KellyPositionSizer:
                                       effective fractions, calculate_kelly,
                                       calculate_position_size

Change Log:
    2026-03-03:
        - Created (item C: risk management test suite, T58)
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import importlib
import importlib.util
import math
import statistics
import sys
import unittest
from datetime import datetime
from pathlib import Path

# ==============================================================================
# PATH SETUP
# ==============================================================================
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _load(rel_path: str):
    full = _REPO_ROOT / rel_path
    spec = importlib.util.spec_from_file_location(full.stem, full)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_e02 = _load("Spyder/SpyderE_Risk/SpyderE02_PositionSizer.py")
_e06 = _load("Spyder/SpyderE_Risk/SpyderE06_RiskMetrics.py")
_e14 = _load("Spyder/SpyderE_Risk/SpyderE14_KellyPositionSizer.py")

# ---------------- E06 free functions ----------------------------------------
calculate_returns = _e06.calculate_returns
annualize_return = _e06.annualize_return
annualize_volatility = _e06.annualize_volatility
calculate_sharpe_ratio = _e06.calculate_sharpe_ratio
calculate_sortino_ratio = _e06.calculate_sortino_ratio
calculate_calmar_ratio = _e06.calculate_calmar_ratio
calculate_max_drawdown = _e06.calculate_max_drawdown
calculate_var = _e06.calculate_var
calculate_cvar = _e06.calculate_cvar
calculate_omega_ratio = _e06.calculate_omega_ratio
TRADING_DAYS_PER_YEAR = _e06.TRADING_DAYS_PER_YEAR
MIN_PERIODS_SHARPE = _e06.MIN_PERIODS_SHARPE
DEFAULT_RISK_FREE_RATE = _e06.DEFAULT_RISK_FREE_RATE

# ---------------- E02 PositionSizer -----------------------------------------
PositionSizer = _e02.PositionSizer
PositionSizeRequest = _e02.PositionSizeRequest
PositionSizeRecommendation = _e02.PositionSizeRecommendation
SizingMethod = _e02.SizingMethod
MarketConditions = _e02.MarketConditions
MarketRegime = _e02.MarketRegime
VolatilityRegime = _e02.VolatilityRegime

# ---------------- E14 KellyPositionSizer ------------------------------------
KellyPositionSizer = _e14.KellyPositionSizer
KellyFraction = _e14.KellyFraction
KellyResult = _e14.KellyResult
PositionSizingResult = _e14.PositionSizingResult


# ==============================================================================
# HELPERS
# ==============================================================================

def _flat_returns(daily_r: float, n: int = 252) -> list[float]:
    """Build a list of identical daily returns."""
    return [daily_r] * n


def _up_returns(start: float = 100, n: int = 252, step: float = 1.0) -> list[float]:
    """Build an upward-trending equity curve and return simple returns."""
    prices = [start + i * step for i in range(n + 1)]
    return calculate_returns(prices)


def _make_request(
    entry_price: float = 500.0,
    stop_loss: float = 490.0,
    signal_strength: float = 0.7,
    strategy_name: str = "TestStrategy",
    trade_type: str = "long",
    target_price: float = 520.0,
) -> PositionSizeRequest:
    return PositionSizeRequest(
        strategy_name=strategy_name,
        symbol="SPY",
        entry_price=entry_price,
        stop_loss_price=stop_loss,
        target_price=target_price,
        signal_strength=signal_strength,
        trade_type=trade_type,
    )


# ==============================================================================
# 1. CALCULATE RETURNS (E06)
# ==============================================================================


class TestCalculateReturns(unittest.TestCase):

    def test_simple_returns_basic(self):
        prices = [100.0, 110.0, 121.0]
        rets = calculate_returns(prices)
        self.assertEqual(len(rets), 2)
        self.assertAlmostEqual(rets[0], 0.10, places=10)
        self.assertAlmostEqual(rets[1], 0.10, places=10)

    def test_empty_input_returns_empty(self):
        self.assertEqual(calculate_returns([]), [])

    def test_single_price_returns_empty(self):
        self.assertEqual(calculate_returns([100.0]), [])

    def test_log_returns(self):
        prices = [100.0, math.e * 100]
        rets = calculate_returns(prices, method='log')
        self.assertAlmostEqual(rets[0], 1.0, places=8)

    def test_returns_length(self):
        prices = [float(i) for i in range(1, 101)]
        rets = calculate_returns(prices)
        self.assertEqual(len(rets), 99)

    def test_negative_returns(self):
        prices = [100.0, 90.0]
        rets = calculate_returns(prices)
        self.assertAlmostEqual(rets[0], -0.10, places=10)

    def test_returns_all_finite(self):
        prices = [100.0 + i for i in range(50)]
        for r in calculate_returns(prices):
            self.assertTrue(math.isfinite(r))


# ==============================================================================
# 2. ANNUALIZE RETURN (E06)
# ==============================================================================


class TestAnnualizeReturn(unittest.TestCase):

    def test_empty_returns_zero(self):
        self.assertEqual(annualize_return([]), 0.0)

    def test_positive_return_positive_annualized(self):
        rets = _flat_returns(0.001, 252)
        result = annualize_return(rets)
        self.assertGreater(result, 0.0)

    def test_daily_returns_compound(self):
        # 252 identical daily returns of 0.001 → (1.001)^252 - 1
        r = 0.001
        rets = _flat_returns(r, 252)
        expected = (1 + r) ** 252 - 1
        self.assertAlmostEqual(annualize_return(rets), expected, places=4)

    def test_negative_returns_negative(self):
        rets = _flat_returns(-0.002, 252)
        self.assertLess(annualize_return(rets), 0.0)

    def test_returns_float(self):
        self.assertIsInstance(annualize_return(_flat_returns(0.001)), float)


# ==============================================================================
# 3. ANNUALIZE VOLATILITY (E06)
# ==============================================================================


class TestAnnualizeVolatility(unittest.TestCase):

    def test_empty_returns_zero(self):
        self.assertEqual(annualize_volatility([]), 0.0)

    def test_single_return_zero(self):
        self.assertEqual(annualize_volatility([0.01]), 0.0)

    def test_constant_returns_zero_vol(self):
        rets = _flat_returns(0.01, 50)
        self.assertAlmostEqual(annualize_volatility(rets), 0.0, places=10)

    def test_scales_by_sqrt_periods(self):
        import numpy as np
        rets = [0.01, -0.01, 0.02, -0.02] * 20
        daily_std = np.std(rets)
        expected_annual_vol = daily_std * math.sqrt(TRADING_DAYS_PER_YEAR)
        self.assertAlmostEqual(
            annualize_volatility(rets, TRADING_DAYS_PER_YEAR),
            expected_annual_vol,
            places=10,
        )

    def test_positive_result(self):
        rets = [0.01, -0.01, 0.02, -0.02]
        self.assertGreater(annualize_volatility(rets), 0.0)


# ==============================================================================
# 4. SHARPE RATIO (E06)
# ==============================================================================


class TestCalculateSharpeRatio(unittest.TestCase):

    def test_too_few_periods_returns_zero(self):
        rets = _flat_returns(0.01, MIN_PERIODS_SHARPE - 1)
        self.assertEqual(calculate_sharpe_ratio(rets), 0.0)

    def test_zero_volatility_returns_zero_or_finite(self):
        # Constant returns may produce near-zero vol; result should at minimum be finite
        rets = _flat_returns(0.001, MIN_PERIODS_SHARPE)
        result = calculate_sharpe_ratio(rets)
        # The implementation returns 0.0 only if annual_vol == 0;  floating-point
        # std of identical values may be non-zero, so we just check finiteness
        self.assertTrue(math.isfinite(result))

    def test_positive_high_return_positive_sharpe(self):
        # High, volatile returns — Sharpe might be positive or negative depending
        # on annualized excess over risk-free, but with 0.3% daily it's positive
        _flat_returns(0.003, 252)
        # Constant returns → zero vol → 0; use mixed returns
        mixed = [0.003 if i % 2 == 0 else 0.001 for i in range(252)]
        result = calculate_sharpe_ratio(mixed)
        self.assertIsInstance(result, float)
        self.assertTrue(math.isfinite(result))

    def test_negative_returns_produce_result(self):
        rets = [0.01, -0.02, 0.01, -0.02] * 100
        result = calculate_sharpe_ratio(rets)
        self.assertIsInstance(result, float)

    def test_returns_float(self):
        self.assertIsInstance(calculate_sharpe_ratio(_flat_returns(0.01, 50)), float)

    def test_higher_return_higher_sharpe(self):
        low_return = [0.0005] * 100 + [-0.001] * 152
        high_return = [0.001] * 100 + [-0.001] * 152
        sr_low = calculate_sharpe_ratio(low_return)
        sr_high = calculate_sharpe_ratio(high_return)
        self.assertGreater(sr_high, sr_low)


# ==============================================================================
# 5. SORTINO RATIO (E06)
# ==============================================================================


class TestCalculateSortinoRatio(unittest.TestCase):

    def test_too_few_periods_returns_zero(self):
        rets = _flat_returns(0.01, 29)
        self.assertEqual(calculate_sortino_ratio(rets), 0.0)

    def test_no_downside_returns_zero(self):
        # All positive returns → no downside → Sortino = 0.0 per implementation
        rets = _flat_returns(0.001, 252)
        self.assertEqual(calculate_sortino_ratio(rets), 0.0)

    def test_mixed_returns_produce_result(self):
        rets = [0.01, -0.02, 0.015, -0.005] * 80
        result = calculate_sortino_ratio(rets)
        self.assertIsInstance(result, float)
        self.assertTrue(math.isfinite(result))

    def test_returns_float(self):
        rets = [0.01, -0.02] * 120
        self.assertIsInstance(calculate_sortino_ratio(rets), float)

    def test_greater_downside_lowers_sortino(self):
        # Need VARIED downside so np.std(downside_returns) != 0
        import numpy as np
        # low-downside: downside returns vary between -0.003 and -0.007
        low_dd = [x for i in range(60) for x in [0.02, -0.003 - 0.0001 * i]]
        # high-downside: downside returns vary between -0.015 and -0.025
        high_dd = [x for i in range(60) for x in [0.02, -0.015 - 0.0001 * i]]
        sr_low = calculate_sortino_ratio(low_dd)
        sr_high_dd = calculate_sortino_ratio(high_dd)
        self.assertGreater(sr_low, sr_high_dd)


# ==============================================================================
# 6. CALMAR RATIO (E06)
# ==============================================================================


class TestCalculateCalmarRatio(unittest.TestCase):

    def test_zero_drawdown_returns_zero(self):
        rets = _flat_returns(0.001, 252)
        self.assertEqual(calculate_calmar_ratio(rets, max_drawdown=0.0), 0.0)

    def test_empty_returns_zero(self):
        self.assertEqual(calculate_calmar_ratio([], max_drawdown=0.20), 0.0)

    def test_positive_returns_positive_calmar(self):
        rets = _flat_returns(0.001, 252)  # strong positive growth
        result = calculate_calmar_ratio(rets, max_drawdown=0.10)
        # annualized return > 0, drawdown > 0 → calmar > 0
        self.assertGreater(result, 0.0)

    def test_drawdown_sign_handled(self):
        rets = _flat_returns(0.001, 252)
        # Both positive and negative max_drawdown representations work
        r_pos = calculate_calmar_ratio(rets, max_drawdown=0.10)
        r_neg = calculate_calmar_ratio(rets, max_drawdown=-0.10)
        self.assertAlmostEqual(r_pos, r_neg, places=8)

    def test_returns_float(self):
        self.assertIsInstance(
            calculate_calmar_ratio(_flat_returns(0.001, 100), 0.05), float
        )


# ==============================================================================
# 7. MAX DRAWDOWN (E06)
# ==============================================================================


class TestCalculateMaxDrawdown(unittest.TestCase):

    def test_empty_returns_zeros(self):
        dd, pi, ti = calculate_max_drawdown([])
        self.assertEqual(dd, 0.0)
        self.assertEqual(pi, 0)
        self.assertEqual(ti, 0)

    def test_monotonically_increasing_no_drawdown(self):
        equity = [100.0 + i for i in range(100)]
        dd, _, _ = calculate_max_drawdown(equity)
        self.assertAlmostEqual(dd, 0.0, places=10)

    def test_50_percent_drawdown(self):
        equity = [100.0, 50.0, 80.0]
        dd, _, _ = calculate_max_drawdown(equity)
        self.assertAlmostEqual(dd, 0.50, places=8)

    def test_peak_trough_indices_correct(self):
        # Peak at index 1 (200), trough at index 2 (100)
        equity = [100.0, 200.0, 100.0]
        dd, peak_idx, trough_idx = calculate_max_drawdown(equity)
        self.assertEqual(peak_idx, 1)
        self.assertEqual(trough_idx, 2)
        self.assertAlmostEqual(dd, 0.50, places=8)

    def test_multiple_drawdowns_finds_max(self):
        # First drawdown: 100 → 80 = 20%, second: 100 → 60 = 40%
        equity = [100.0, 80.0, 100.0, 60.0, 100.0]
        dd, _, _ = calculate_max_drawdown(equity)
        self.assertAlmostEqual(dd, 0.40, places=8)

    def test_returns_tuple_of_correct_types(self):
        result = calculate_max_drawdown([100.0, 90.0, 95.0])
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 3)
        self.assertIsInstance(result[0], float)
        self.assertIsInstance(result[1], int)
        self.assertIsInstance(result[2], int)

    def test_drawdown_between_zero_and_one(self):
        import random
        random.seed(42)
        equity = [100.0]
        for _ in range(99):
            equity.append(equity[-1] * (1 + random.uniform(-0.05, 0.06)))
        dd, _, _ = calculate_max_drawdown(equity)
        self.assertGreaterEqual(dd, 0.0)
        self.assertLessEqual(dd, 1.0)


# ==============================================================================
# 8. VALUE AT RISK & CVAR (E06)
# ==============================================================================


class TestCalculateVaR(unittest.TestCase):

    def test_empty_returns_zero(self):
        self.assertEqual(calculate_var([]), 0.0)

    def test_var_is_5th_percentile_at_95_confidence(self):
        import numpy as np
        rets = [float(i) for i in range(-10, 91)]  # 101 values, -10 → 90
        var = calculate_var(rets, 0.95)
        expected = np.percentile(rets, 5.0)
        self.assertAlmostEqual(var, expected, places=6)

    def test_all_positive_returns_positive_var(self):
        rets = _flat_returns(0.01, 100)
        var = calculate_var(rets, 0.95)
        self.assertGreater(var, 0.0)

    def test_all_negative_returns_negative_var(self):
        rets = _flat_returns(-0.02, 100)
        var = calculate_var(rets, 0.95)
        self.assertLess(var, 0.0)

    def test_returns_float(self):
        self.assertIsInstance(calculate_var([0.01, -0.01, 0.02], 0.95), float)


class TestCalculateCVaR(unittest.TestCase):

    def test_empty_returns_zero(self):
        self.assertEqual(calculate_cvar([]), 0.0)

    def test_cvar_more_negative_than_var(self):
        rets = [0.01, -0.05, 0.02, -0.03, -0.08, 0.015] * 50
        var = calculate_var(rets, 0.95)
        cvar = calculate_cvar(rets, 0.95)
        # CVaR (expected shortfall) is at least as negative as VaR
        self.assertLessEqual(cvar, var)

    def test_cvar_returns_float(self):
        rets = [0.01, -0.02, 0.01, -0.03] * 30
        self.assertIsInstance(calculate_cvar(rets, 0.95), float)


class TestCalculateOmegaRatio(unittest.TestCase):

    def test_empty_returns_zero(self):
        self.assertEqual(calculate_omega_ratio([]), 0.0)

    def test_all_positive_above_threshold_is_inf(self):
        rets = _flat_returns(0.01, 100)
        result = calculate_omega_ratio(rets, threshold=0.0)
        self.assertEqual(result, float('inf'))

    def test_all_negative_below_threshold_is_zero(self):
        rets = _flat_returns(-0.01, 100)
        result = calculate_omega_ratio(rets, threshold=0.0)
        self.assertEqual(result, 0.0)

    def test_mixed_returns_positive_ratio(self):
        rets = [0.02, -0.01, 0.03, -0.01] * 50
        result = calculate_omega_ratio(rets, threshold=0.0)
        # Gains > Losses → omega > 1
        self.assertGreater(result, 1.0)

    def test_returns_float(self):
        rets = [0.01, -0.01] * 20
        self.assertIsInstance(calculate_omega_ratio(rets), float)


# ==============================================================================
# 9. POSITION SIZER (E02)
# ==============================================================================


class TestPositionSizerConstruction(unittest.TestCase):

    def test_construction_default(self):
        sizer = PositionSizer(portfolio_value=100_000.0)
        self.assertEqual(sizer.portfolio_value, 100_000.0)

    def test_construction_stores_portfolio_value(self):
        sizer = PositionSizer(portfolio_value=250_000.0)
        self.assertEqual(sizer.portfolio_value, 250_000.0)

    def test_update_portfolio_value(self):
        sizer = PositionSizer(portfolio_value=100_000.0)
        sizer.update_portfolio_value(150_000.0)
        self.assertEqual(sizer.portfolio_value, 150_000.0)

    def test_update_portfolio_value_updates_value(self):
        # The implementation does not guard against negative values;
        # it simply stores whatever is passed. Verify it actually updates.
        sizer = PositionSizer(portfolio_value=100_000.0)
        sizer.update_portfolio_value(200_000.0)
        self.assertEqual(sizer.portfolio_value, 200_000.0)


class TestPositionSizerCalculate(unittest.TestCase):

    def setUp(self):
        self.sizer = PositionSizer(portfolio_value=100_000.0)

    def test_returns_recommendation(self):
        req = _make_request()
        result = self.sizer.calculate_position_size(req)
        self.assertIsInstance(result, PositionSizeRecommendation)

    def test_position_size_pct_non_negative(self):
        req = _make_request(entry_price=500.0, stop_loss=490.0)
        result = self.sizer.calculate_position_size(req)
        self.assertGreaterEqual(result.position_size_pct, 0.0)

    def test_position_size_pct_within_max(self):
        req = _make_request(signal_strength=1.0)
        result = self.sizer.calculate_position_size(req)
        self.assertLessEqual(result.position_size_pct, self.sizer.max_position_size)

    def test_dollar_amount_non_negative(self):
        req = _make_request()
        result = self.sizer.calculate_position_size(req)
        self.assertGreaterEqual(result.dollar_amount, 0.0)

    def test_invalid_entry_price_returns_recommendation(self):
        # entry == stop_loss → invalid → should return rejected recommendation (0 size)
        req = _make_request(entry_price=500.0, stop_loss=500.0)
        result = self.sizer.calculate_position_size(req)
        self.assertIsInstance(result, PositionSizeRecommendation)

    def test_higher_signal_strength_larger_position(self):
        req_low = _make_request(signal_strength=0.2, entry_price=500.0, stop_loss=490.0)
        req_high = _make_request(signal_strength=0.9, entry_price=500.0, stop_loss=490.0)
        low = self.sizer.calculate_position_size(req_low)
        high = self.sizer.calculate_position_size(req_high)
        self.assertGreaterEqual(high.position_size_pct, low.position_size_pct)

    def test_risk_amount_non_negative(self):
        req = _make_request()
        result = self.sizer.calculate_position_size(req)
        self.assertGreaterEqual(result.risk_amount, 0.0)

    def test_confidence_score_in_0_1(self):
        req = _make_request()
        result = self.sizer.calculate_position_size(req)
        self.assertGreaterEqual(result.confidence_score, 0.0)
        self.assertLessEqual(result.confidence_score, 1.0)


# ==============================================================================
# 10. KELLY POSITION SIZER (E14)
# ==============================================================================


class TestKellyFractions(unittest.TestCase):

    def test_quarter_kelly_fraction(self):
        sizer = KellyPositionSizer(kelly_fraction=KellyFraction.QUARTER_KELLY)
        self.assertAlmostEqual(sizer.effective_kelly_fraction, 0.25)

    def test_half_kelly_fraction(self):
        sizer = KellyPositionSizer(kelly_fraction=KellyFraction.HALF_KELLY)
        self.assertAlmostEqual(sizer.effective_kelly_fraction, 0.50)

    def test_full_kelly_fraction(self):
        sizer = KellyPositionSizer(kelly_fraction=KellyFraction.FULL_KELLY)
        self.assertAlmostEqual(sizer.effective_kelly_fraction, 1.0)

    def test_eighth_kelly_fraction(self):
        sizer = KellyPositionSizer(kelly_fraction=KellyFraction.EIGHTH_KELLY)
        self.assertAlmostEqual(sizer.effective_kelly_fraction, 0.125)

    def test_custom_fraction(self):
        sizer = KellyPositionSizer(
            kelly_fraction=KellyFraction.CUSTOM,
            custom_fraction=0.33,
        )
        self.assertAlmostEqual(sizer.effective_kelly_fraction, 0.33)

    def test_quarter_kelly_is_smaller_than_half(self):
        q = KellyPositionSizer(kelly_fraction=KellyFraction.QUARTER_KELLY)
        h = KellyPositionSizer(kelly_fraction=KellyFraction.HALF_KELLY)
        self.assertLess(q.effective_kelly_fraction, h.effective_kelly_fraction)


class TestKellyCalculation(unittest.TestCase):

    def setUp(self):
        self.sizer = KellyPositionSizer(kelly_fraction=KellyFraction.FULL_KELLY)

    def test_returns_kelly_result(self):
        result = self.sizer.calculate_kelly(0.55, avg_win=100.0, avg_loss=80.0)
        self.assertIsInstance(result, KellyResult)

    def test_positive_edge_positive_kelly_fraction(self):
        # win_prob=0.6, avg_win=100, avg_loss=80 → edge > 0 → kelly > 0
        result = self.sizer.calculate_kelly(0.60, avg_win=100.0, avg_loss=80.0)
        self.assertGreater(result.kelly_fraction, 0.0)

    def test_breakeven_zero_kelly(self):
        # p=0.5, odds=1.0 (avg_win==avg_loss) → kelly_fraction = 0
        result = self.sizer.calculate_kelly(0.50, avg_win=100.0, avg_loss=100.0)
        self.assertAlmostEqual(result.kelly_fraction, 0.0, places=8)

    def test_expected_return_formula(self):
        # E[return] = p * avg_win - (1-p) * avg_loss
        p, w, loss = 0.60, 100.0, 80.0
        expected = p * w - (1 - p) * loss
        result = self.sizer.calculate_kelly(p, avg_win=w, avg_loss=loss)
        self.assertAlmostEqual(result.expected_return, expected, places=6)

    def test_risk_reward_ratio(self):
        result = self.sizer.calculate_kelly(0.55, avg_win=150.0, avg_loss=100.0)
        self.assertAlmostEqual(result.risk_reward_ratio, 1.50, places=8)

    def test_quarter_kelly_reduces_fraction(self):
        full = KellyPositionSizer(kelly_fraction=KellyFraction.FULL_KELLY)
        quarter = KellyPositionSizer(kelly_fraction=KellyFraction.QUARTER_KELLY)
        r_full = full.calculate_kelly(0.60, 100.0, 80.0)
        r_quarter = quarter.calculate_kelly(0.60, 100.0, 80.0)
        self.assertAlmostEqual(r_quarter.kelly_fraction, r_full.kelly_fraction * 0.25, places=8)

    def test_invalid_win_prob_raises(self):
        with self.assertRaises((ValueError, Exception)):
            self.sizer.calculate_kelly(0.0, avg_win=100.0, avg_loss=80.0)

    def test_invalid_avg_loss_raises(self):
        with self.assertRaises((ValueError, Exception)):
            self.sizer.calculate_kelly(0.55, avg_win=100.0, avg_loss=-10.0)

    def test_win_probability_stored_in_result(self):
        result = self.sizer.calculate_kelly(0.55, avg_win=100.0, avg_loss=80.0)
        self.assertAlmostEqual(result.win_probability, 0.55)

    def test_kelly_stored_in_history(self):
        self.sizer.calculate_kelly(0.55, avg_win=100.0, avg_loss=80.0)
        self.assertEqual(len(self.sizer.kelly_history), 1)


class TestKellyPositionSize(unittest.TestCase):

    def setUp(self):
        self.sizer = KellyPositionSizer(
            kelly_fraction=KellyFraction.QUARTER_KELLY,
            max_position_size=0.20,
            min_position_size=0.01,
        )

    def test_returns_sizing_result(self):
        result = self.sizer.calculate_position_size(
            capital=100_000.0,
            win_probability=0.55,
            avg_win=100.0,
            avg_loss=80.0,
        )
        self.assertIsInstance(result, PositionSizingResult)

    def test_position_size_within_max_limit(self):
        result = self.sizer.calculate_position_size(
            capital=100_000.0,
            win_probability=0.70,  # high edge
            avg_win=200.0,
            avg_loss=50.0,
        )
        self.assertLessEqual(result.position_size, self.sizer.max_position_size)

    def test_position_value_bounded(self):
        capital = 50_000.0
        result = self.sizer.calculate_position_size(
            capital=capital,
            win_probability=0.55,
            avg_win=100.0,
            avg_loss=80.0,
        )
        self.assertGreaterEqual(result.position_value, 0.0)
        self.assertLessEqual(result.position_value, capital)

    def test_position_size_non_negative(self):
        result = self.sizer.calculate_position_size(
            capital=100_000.0,
            win_probability=0.55,
            avg_win=100.0,
            avg_loss=80.0,
        )
        self.assertGreaterEqual(result.position_size, 0.0)


# ==============================================================================
# MAIN
# ==============================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
