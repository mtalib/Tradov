#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT57_OptionsAnalyticsTests.py
Purpose: Unit tests for N-series options analytics (item B)

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-03-03 Time: 00:00:00

Module Description:
    Covers the core N-series options analytics modules:
      - SpyderN01_OptionsPricer      — Black-Scholes: norm_cdf/pdf, d1/d2,
                                       price_call/put, calculate_greeks,
                                       OptionContract, OptionPrice, put-call
                                       parity
      - SpyderN02_ImpliedVolatilityEngine — IVHistory.calculate_rank /
                                             calculate_percentile

Change Log:
    2026-03-03:
        - Created (item B: options analytics test suite)
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import importlib
import importlib.util
import math
import sys
import unittest
from datetime import datetime, timedelta
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


_n01 = _load("Spyder/SpyderN_OptionsAnalytics/SpyderN01_OptionsPricer.py")
_n02 = _load("Spyder/SpyderN_OptionsAnalytics/SpyderN02_ImpliedVolatilityEngine.py")

# Pull N01 names
norm_cdf = _n01.norm_cdf
norm_pdf = _n01.norm_pdf
calculate_d1_d2 = _n01.calculate_d1_d2
BlackScholesPricer = _n01.BlackScholesPricer
OptionContract = _n01.OptionContract
OptionType = _n01.OptionType
ExerciseStyle = _n01.ExerciseStyle
GreeksResult = _n01.GreeksResult

# Pull N02 names
IVHistory = _n02.IVHistory
IVSnapshot = _n02.IVSnapshot
VolatilityRegime = _n02.VolatilityRegime

# ==============================================================================
# HELPERS
# ==============================================================================

# Typical SPY-like parameters
_S = 500.0        # spot
_K = 500.0        # strike (ATM)
_T = 30 / 252.0   # ~30 trading days to expiry
_r = 0.05         # risk-free rate
_q = 0.013        # dividend yield
_sigma = 0.20     # 20% IV

_TOLERANCE = 1e-6   # for exact / near-exact assertions
_PRICE_TOL = 0.01   # $0.01 tolerance for put-call parity checks


def _call(S=_S, K=_K, T=_T, r=_r, q=_q, sigma=_sigma) -> float:
    return BlackScholesPricer.price_call(S, K, T, r, q, sigma)


def _put(S=_S, K=_K, T=_T, r=_r, q=_q, sigma=_sigma) -> float:
    return BlackScholesPricer.price_put(S, K, T, r, q, sigma)


def _greeks(option_type, S=_S, K=_K, T=_T, r=_r, q=_q, sigma=_sigma) -> GreeksResult:
    return BlackScholesPricer.calculate_greeks(S, K, T, r, q, sigma, option_type)


def _make_iv_snapshot(atm_iv: float, dts_ago: int = 0) -> IVSnapshot:
    ts = datetime.now() - timedelta(days=dts_ago)
    return IVSnapshot(
        timestamp=ts,
        underlying="SPY",
        spot_price=500.0,
        atm_iv=atm_iv,
        iv_points=[],
        term_structure={30: atm_iv, 60: atm_iv + 0.01},
        smile_parameters={},
        regime=VolatilityRegime.NORMAL,
    )


def _make_iv_history(ivs):
    """Build IVHistory from list of (atm_iv, days_ago) pairs."""
    snaps = [_make_iv_snapshot(iv, days) for iv, days in ivs]
    return IVHistory(underlying="SPY", data=snaps)


# ==============================================================================
# 1. NORM FUNCTIONS (N01)
# ==============================================================================


class TestNormCdf(unittest.TestCase):

    def test_at_zero_is_half(self):
        self.assertAlmostEqual(norm_cdf(0.0), 0.5, places=10)

    def test_large_positive_approaches_one(self):
        self.assertGreater(norm_cdf(8.0), 0.9999999)

    def test_large_negative_approaches_zero(self):
        self.assertLess(norm_cdf(-8.0), 1e-6)

    def test_monotonically_increasing(self):
        xs = [-2.0, -1.0, 0.0, 1.0, 2.0]
        vals = [norm_cdf(x) for x in xs]
        self.assertEqual(vals, sorted(vals))

    def test_symmetry(self):
        # norm_cdf(x) + norm_cdf(-x) = 1
        for x in [0.5, 1.0, 1.96, 2.5]:
            self.assertAlmostEqual(norm_cdf(x) + norm_cdf(-x), 1.0, places=10)

    def test_one_sigma(self):
        # P(Z < 1) ≈ 0.8413
        self.assertAlmostEqual(norm_cdf(1.0), 0.8413, places=3)

    def test_result_in_zero_one(self):
        for x in [-5.0, -1.0, 0.0, 1.0, 5.0]:
            v = norm_cdf(x)
            self.assertGreaterEqual(v, 0.0)
            self.assertLessEqual(v, 1.0)


class TestNormPdf(unittest.TestCase):

    def test_maximum_at_zero(self):
        pdf_0 = norm_pdf(0.0)
        for x in [-2.0, -1.0, 0.5, 1.0, 2.0]:
            self.assertGreaterEqual(pdf_0, norm_pdf(x))

    def test_positive_everywhere(self):
        for x in [-5.0, -2.0, 0.0, 2.0, 5.0]:
            self.assertGreater(norm_pdf(x), 0.0)

    def test_symmetric(self):
        for x in [0.5, 1.0, 2.0]:
            self.assertAlmostEqual(norm_pdf(x), norm_pdf(-x), places=12)

    def test_value_at_zero(self):
        # 1 / sqrt(2pi) ≈ 0.3989
        self.assertAlmostEqual(norm_pdf(0.0), 1.0 / math.sqrt(2 * math.pi), places=10)

    def test_decreasing_from_zero(self):
        for x in [0.1, 0.5, 1.0, 2.0]:
            self.assertGreater(norm_pdf(x - 0.05), norm_pdf(x))


# ==============================================================================
# 2. CALCULATE D1/D2 (N01)
# ==============================================================================


class TestCalculateD1D2(unittest.TestCase):

    def test_expired_option_returns_zeros(self):
        d1, d2 = calculate_d1_d2(S=500, K=500, T=0, r=0.05, q=0, sigma=0.20)
        self.assertEqual(d1, 0.0)
        self.assertEqual(d2, 0.0)

    def test_zero_sigma_returns_zeros(self):
        d1, d2 = calculate_d1_d2(S=500, K=500, T=1.0, r=0.05, q=0, sigma=0.0)
        self.assertEqual(d1, 0.0)
        self.assertEqual(d2, 0.0)

    def test_d1_greater_than_d2(self):
        d1, d2 = calculate_d1_d2(S=500, K=500, T=1.0, r=0.05, q=0, sigma=0.20)
        self.assertGreater(d1, d2)

    def test_d1_minus_d2_equals_sigma_sqrt_T(self):
        sigma, T = 0.25, 0.5
        d1, d2 = calculate_d1_d2(500, 500, T, 0.05, 0, sigma)
        self.assertAlmostEqual(d1 - d2, sigma * math.sqrt(T), places=10)

    def test_atm_no_dividends_d1(self):
        # d1 = (r + 0.5*sigma^2)*T / (sigma*sqrt(T))
        sigma, T, r = 0.20, 1.0, 0.0
        d1, d2 = calculate_d1_d2(500, 500, T, r, 0, sigma)
        expected_d1 = 0.5 * sigma * math.sqrt(T)
        self.assertAlmostEqual(d1, expected_d1, places=8)

    def test_returns_tuple_of_two_floats(self):
        result = calculate_d1_d2(500, 495, 0.1, 0.05, 0, 0.20)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        for v in result:
            self.assertIsInstance(v, float)


# ==============================================================================
# 3. BLACK-SCHOLES CALL PRICING (N01)
# ==============================================================================


class TestBlackScholesPricerCall(unittest.TestCase):

    def test_call_non_negative(self):
        for K in [400, 480, 500, 520, 600]:
            price = _call(K=K)
            self.assertGreaterEqual(price, 0.0)

    def test_call_at_expiry_itm(self):
        # T=0, S>K → max(S-K, 0)
        price = _call(S=510, K=500, T=0)
        self.assertAlmostEqual(price, 10.0, places=4)

    def test_call_at_expiry_otm(self):
        price = _call(S=490, K=500, T=0)
        self.assertAlmostEqual(price, 0.0, places=4)

    def test_call_at_expiry_atm(self):
        price = _call(S=500, K=500, T=0)
        self.assertAlmostEqual(price, 0.0, places=4)

    def test_deep_itm_call_near_intrinsic(self):
        # S=600, K=400, T=30d: call >> intrinsic lower bound
        price = _call(S=600, K=400, T=30/252)
        self.assertGreater(price, 190.0)  # intrinsic = 200

    def test_deep_otm_call_near_zero(self):
        # K=600, S=500 → very unlikely
        price = _call(S=500, K=600, T=30/252, sigma=0.20)
        self.assertLess(price, 1.0)

    def test_call_increases_with_spot(self):
        prices = [_call(S=s) for s in [480, 490, 500, 510, 520]]
        self.assertEqual(prices, sorted(prices))

    def test_call_increases_with_volatility(self):
        prices = [_call(sigma=s) for s in [0.10, 0.15, 0.20, 0.25, 0.30]]
        self.assertEqual(prices, sorted(prices))

    def test_call_decreases_with_strike(self):
        prices = [_call(K=k) for k in [480, 490, 500, 510, 520]]
        self.assertEqual(prices, sorted(prices, reverse=True))

    def test_call_positive_with_time(self):
        # OTM but still has time value
        price = _call(S=490, K=500, T=60/252, sigma=0.20)
        self.assertGreater(price, 0.0)


# ==============================================================================
# 4. BLACK-SCHOLES PUT PRICING (N01)
# ==============================================================================


class TestBlackScholesPricerPut(unittest.TestCase):

    def test_put_non_negative(self):
        for K in [400, 480, 500, 520, 600]:
            price = _put(K=K)
            self.assertGreaterEqual(price, 0.0)

    def test_put_at_expiry_itm(self):
        price = _put(S=490, K=500, T=0)
        self.assertAlmostEqual(price, 10.0, places=4)

    def test_put_at_expiry_otm(self):
        price = _put(S=510, K=500, T=0)
        self.assertAlmostEqual(price, 0.0, places=4)

    def test_put_decreases_with_spot(self):
        prices = [_put(S=s) for s in [480, 490, 500, 510, 520]]
        self.assertEqual(prices, sorted(prices, reverse=True))

    def test_put_increases_with_strike(self):
        prices = [_put(K=k) for k in [480, 490, 500, 510, 520]]
        self.assertEqual(prices, sorted(prices))

    def test_put_increases_with_volatility(self):
        prices = [_put(sigma=s) for s in [0.10, 0.15, 0.20, 0.25, 0.30]]
        self.assertEqual(prices, sorted(prices))

    def test_deep_itm_put_near_intrinsic(self):
        # K=600, S=400 → intrinsic ≈ 200
        price = _put(S=400, K=600, T=30/252)
        self.assertGreater(price, 190.0)

    def test_deep_otm_put_near_zero(self):
        price = _put(S=600, K=400, T=30/252, sigma=0.20)
        self.assertLess(price, 1.0)


# ==============================================================================
# 5. PUT-CALL PARITY (N01)
# ==============================================================================


class TestPutCallParity(unittest.TestCase):
    """C - P = S*exp(-q*T) - K*exp(-r*T)"""

    def _check_parity(self, S, K, T, r, q, sigma):
        C = BlackScholesPricer.price_call(S, K, T, r, q, sigma)
        P = BlackScholesPricer.price_put(S, K, T, r, q, sigma)
        lhs = C - P
        rhs = S * math.exp(-q * T) - K * math.exp(-r * T)
        self.assertAlmostEqual(lhs, rhs, places=4,
            msg=f"Parity failed: C-P={lhs:.6f} rhs={rhs:.6f} params=({S},{K},{T},{r},{q},{sigma})")

    def test_atm(self):
        self._check_parity(500, 500, _T, _r, _q, _sigma)

    def test_itm_call(self):
        self._check_parity(520, 500, _T, _r, _q, _sigma)

    def test_otm_call(self):
        self._check_parity(480, 500, _T, _r, _q, _sigma)

    def test_long_dated(self):
        self._check_parity(500, 500, 1.0, 0.04, 0.01, 0.25)

    def test_no_dividends(self):
        self._check_parity(500, 500, 0.5, 0.05, 0.0, 0.20)

    def test_high_volatility(self):
        self._check_parity(500, 500, _T, _r, _q, 0.50)


# ==============================================================================
# 6. BLACK-SCHOLES GREEKS (N01)
# ==============================================================================


class TestBlackScholesGreeks(unittest.TestCase):

    def test_returns_greeks_result(self):
        g = _greeks(OptionType.CALL)
        self.assertIsInstance(g, GreeksResult)

    def test_call_delta_atm_near_half(self):
        # ATM call delta with r=5%, q=1.3% should be > 0.5
        g = _greeks(OptionType.CALL)
        self.assertGreater(g.delta, 0.45)
        self.assertLess(g.delta, 0.65)

    def test_put_delta_atm_near_minus_half(self):
        g = _greeks(OptionType.PUT)
        self.assertGreater(g.delta, -0.60)
        self.assertLess(g.delta, -0.40)

    def test_call_put_delta_sum_near_one(self):
        # For q=0: call_delta - put_delta = exp(-q*T) ≈ 1.0
        g_call = BlackScholesPricer.calculate_greeks(_S, _K, _T, _r, 0.0, _sigma, OptionType.CALL)
        g_put = BlackScholesPricer.calculate_greeks(_S, _K, _T, _r, 0.0, _sigma, OptionType.PUT)
        self.assertAlmostEqual(g_call.delta + abs(g_put.delta), 1.0, places=2)

    def test_gamma_positive(self):
        for ot in (OptionType.CALL, OptionType.PUT):
            g = _greeks(ot)
            self.assertGreater(g.gamma, 0)

    def test_call_gamma_equals_put_gamma(self):
        g_call = _greeks(OptionType.CALL)
        g_put = _greeks(OptionType.PUT)
        self.assertAlmostEqual(g_call.gamma, g_put.gamma, places=10)

    def test_vega_positive(self):
        for ot in (OptionType.CALL, OptionType.PUT):
            g = _greeks(ot)
            self.assertGreater(g.vega, 0)

    def test_call_vega_equals_put_vega(self):
        g_call = _greeks(OptionType.CALL)
        g_put = _greeks(OptionType.PUT)
        self.assertAlmostEqual(g_call.vega, g_put.vega, places=10)

    def test_call_theta_negative(self):
        # Theta is negative (time value decays)
        g = _greeks(OptionType.CALL)
        self.assertLess(g.theta, 0)

    def test_put_theta_negative(self):
        g = _greeks(OptionType.PUT)
        self.assertLess(g.theta, 0)

    def test_call_rho_positive(self):
        # Higher rates → higher call value → positive rho
        g = _greeks(OptionType.CALL)
        self.assertGreater(g.rho, 0)

    def test_put_rho_negative(self):
        g = _greeks(OptionType.PUT)
        self.assertLess(g.rho, 0)

    def test_itm_call_delta_greater_than_atm(self):
        g_atm = _greeks(OptionType.CALL, K=500)
        g_itm = _greeks(OptionType.CALL, K=480)  # lower strike = ITM call
        self.assertGreater(g_itm.delta, g_atm.delta)

    def test_all_fields_finite(self):
        g = _greeks(OptionType.CALL)
        for field in (g.delta, g.gamma, g.vega, g.theta, g.rho):
            self.assertTrue(math.isfinite(field))

    def test_expired_greeks_zeros(self):
        g = _greeks(OptionType.CALL, T=0)
        self.assertAlmostEqual(g.delta, 0.0)
        self.assertAlmostEqual(g.gamma, 0.0)
        self.assertAlmostEqual(g.vega, 0.0)


# ==============================================================================
# 7. OPTION CONTRACT (N01)
# ==============================================================================


class TestOptionContract(unittest.TestCase):

    def test_is_expired_for_past_expiry(self):
        contract = OptionContract(
            symbol="SPY240101C500",
            underlying="SPY",
            strike=500.0,
            expiry=datetime.now() - timedelta(days=1),
            option_type=OptionType.CALL,
        )
        self.assertTrue(contract.is_expired)

    def test_is_not_expired_for_future(self):
        contract = OptionContract(
            symbol="SPY250101C500",
            underlying="SPY",
            strike=500.0,
            expiry=datetime.now() + timedelta(days=30),
            option_type=OptionType.CALL,
        )
        self.assertFalse(contract.is_expired)

    def test_time_to_expiry_positive_for_future(self):
        contract = OptionContract(
            symbol="SPY250101C500",
            underlying="SPY",
            strike=500.0,
            expiry=datetime.now() + timedelta(days=30),
            option_type=OptionType.CALL,
        )
        self.assertGreater(contract.time_to_expiry, 0.0)

    def test_time_to_expiry_zero_for_expired(self):
        contract = OptionContract(
            symbol="SPY240101C500",
            underlying="SPY",
            strike=500.0,
            expiry=datetime.now() - timedelta(days=1),
            option_type=OptionType.CALL,
        )
        self.assertAlmostEqual(contract.time_to_expiry, 0.0, places=4)

    def test_default_exercise_style_american(self):
        contract = OptionContract(
            symbol="SPY240101C500",
            underlying="SPY",
            strike=500.0,
            expiry=datetime.now() + timedelta(days=30),
            option_type=OptionType.CALL,
        )
        self.assertEqual(contract.exercise_style, ExerciseStyle.AMERICAN)

    def test_put_option_type(self):
        contract = OptionContract(
            symbol="SPY240101P490",
            underlying="SPY",
            strike=490.0,
            expiry=datetime.now() + timedelta(days=30),
            option_type=OptionType.PUT,
        )
        self.assertEqual(contract.option_type, OptionType.PUT)


# ==============================================================================
# 8. IV HISTORY (N02)
# ==============================================================================


class TestIVHistoryCalculateRank(unittest.TestCase):

    def _history_with_range(self, min_iv: float, max_iv: float) -> IVHistory:
        """Build an IVHistory with 10 points from min_iv to max_iv linearly."""
        import numpy as np
        ivs = [(float(v), i) for i, v in enumerate(
            [min_iv + (max_iv - min_iv) * k / 9 for k in range(10)]
        )]
        return _make_iv_history(ivs)

    def test_rank_of_max_is_100(self):
        hist = self._history_with_range(0.10, 0.40)
        rank = hist.calculate_rank(current_iv=0.40)
        self.assertAlmostEqual(rank, 100.0, places=4)

    def test_rank_of_min_is_zero(self):
        hist = self._history_with_range(0.10, 0.40)
        rank = hist.calculate_rank(current_iv=0.10)
        self.assertAlmostEqual(rank, 0.0, places=4)

    def test_rank_of_midpoint_is_fifty(self):
        hist = self._history_with_range(0.10, 0.30)
        rank = hist.calculate_rank(current_iv=0.20)
        self.assertAlmostEqual(rank, 50.0, places=4)

    def test_empty_data_returns_50(self):
        hist = IVHistory(underlying="SPY", data=[])
        rank = hist.calculate_rank(current_iv=0.20)
        self.assertAlmostEqual(rank, 50.0)

    def test_rank_is_between_zero_and_100(self):
        hist = self._history_with_range(0.10, 0.40)
        for iv in [0.10, 0.15, 0.20, 0.30, 0.40]:
            rank = hist.calculate_rank(current_iv=iv)
            self.assertGreaterEqual(rank, 0.0)
            self.assertLessEqual(rank, 100.0)

    def test_flat_iv_returns_50(self):
        hist = _make_iv_history([(0.20, i) for i in range(5)])
        rank = hist.calculate_rank(current_iv=0.20)
        self.assertAlmostEqual(rank, 50.0)


class TestIVHistoryCalculatePercentile(unittest.TestCase):

    def test_percentile_returns_float(self):
        hist = _make_iv_history([(0.20, i) for i in range(10)])
        result = hist.calculate_percentile(current_iv=0.20)
        self.assertIsInstance(result, float)

    def test_percentile_empty_returns_50(self):
        hist = IVHistory(underlying="SPY", data=[])
        self.assertAlmostEqual(hist.calculate_percentile(0.20), 50.0)

    def test_percentile_in_range(self):
        hist = _make_iv_history([(0.10 + 0.02 * i, i) for i in range(10)])
        result = hist.calculate_percentile(current_iv=0.20)
        self.assertGreaterEqual(result, 0.0)
        self.assertLessEqual(result, 100.0)


# ==============================================================================
# MAIN
# ==============================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
