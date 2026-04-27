#!/usr/bin/env python3
"""
Tests for SpyderV09_IVEngine

Covers: BlackScholesCalculator (call/put price, put-call parity, IV recovery),
GreeksCalculator (delta bounds for calls/puts), CalculationCache (put/get/TTL),
OptionContract and Greeks dataclass construction.
"""

import os
import sys
import time
import unittest
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from Spyder.SpyderV_QuantModels.SpyderV09_IVEngine import (
    BlackScholesCalculator,
    CalculationCache,
    Greeks,
    GreeksCalculator,
    OptionContract,
    VolatilityModel,
)


# ---------------------------------------------------------------------------
# Shared test parameters (ATM SPY-like option)
# ---------------------------------------------------------------------------
S = 450.0    # spot
K = 450.0    # strike (ATM)
r = 0.05     # risk-free rate
q = 0.01     # dividend yield
sigma = 0.20 # 20% IV
T = 0.25     # 3 months to expiry


class TestBlackScholesCalculatorPrice(unittest.TestCase):
    def test_call_price_positive(self):
        price = BlackScholesCalculator.call_price(S, K, r, q, sigma, T)
        self.assertGreater(price, 0.0)

    def test_put_price_positive(self):
        price = BlackScholesCalculator.put_price(S, K, r, q, sigma, T)
        self.assertGreater(price, 0.0)

    def test_put_call_parity(self):
        call = BlackScholesCalculator.call_price(S, K, r, q, sigma, T)
        put  = BlackScholesCalculator.put_price(S, K, r, q, sigma, T)
        # C - P = S*e^(-qT) - K*e^(-rT)
        import math
        lhs = call - put
        rhs = S * math.exp(-q * T) - K * math.exp(-r * T)
        self.assertAlmostEqual(lhs, rhs, places=4)

    def test_expired_call_intrinsic_only(self):
        itm_call = BlackScholesCalculator.call_price(S, 430.0, r, q, sigma, T=0.0)
        self.assertAlmostEqual(itm_call, max(S - 430.0, 0.0))

    def test_expired_put_intrinsic_only(self):
        itm_put = BlackScholesCalculator.put_price(S, 470.0, r, q, sigma, T=0.0)
        self.assertAlmostEqual(itm_put, max(470.0 - S, 0.0))


class TestBlackScholesCalculatorIV(unittest.TestCase):
    def test_iv_recovery_call(self):
        """Solve for IV from a known BSM call price — should recover sigma."""
        market_price = BlackScholesCalculator.call_price(S, K, r, q, sigma, T)
        recovered_iv = BlackScholesCalculator.implied_volatility(
            market_price, S, K, r, q, T, option_type="CALL"
        )
        self.assertAlmostEqual(recovered_iv, sigma, places=4)

    def test_iv_recovery_put(self):
        market_price = BlackScholesCalculator.put_price(S, K, r, q, sigma, T)
        recovered_iv = BlackScholesCalculator.implied_volatility(
            market_price, S, K, r, q, T, option_type="PUT"
        )
        self.assertAlmostEqual(recovered_iv, sigma, places=4)

    def test_iv_with_zero_price_returns_none_or_min(self):
        """Zero market price should not raise; returns None or MIN_VOLATILITY."""
        result = BlackScholesCalculator.implied_volatility(
            0.0, S, K, r, q, T, option_type="CALL"
        )
        self.assertIsNone(result)


class TestGreeksCalculator(unittest.TestCase):
    def setUp(self):
        self.calc = GreeksCalculator()

    def test_call_delta_between_0_and_1(self):
        g = self.calc.calculate_greeks(S, K, r, q, sigma, T, option_type="CALL")
        self.assertIsInstance(g, Greeks)
        self.assertGreater(g.delta, 0.0)
        self.assertLess(g.delta, 1.0)

    def test_put_delta_between_minus1_and_0(self):
        g = self.calc.calculate_greeks(S, K, r, q, sigma, T, option_type="PUT")
        self.assertLess(g.delta, 0.0)
        self.assertGreater(g.delta, -1.0)

    def test_gamma_positive(self):
        g = self.calc.calculate_greeks(S, K, r, q, sigma, T, option_type="CALL")
        self.assertGreater(g.gamma, 0.0)

    def test_vega_positive(self):
        g = self.calc.calculate_greeks(S, K, r, q, sigma, T, option_type="CALL")
        self.assertGreater(g.vega, 0.0)

    def test_call_theta_negative(self):
        """Call theta (time decay) should be negative for a standard option."""
        g = self.calc.calculate_greeks(S, K, r, q, sigma, T, option_type="CALL")
        self.assertLess(g.theta, 0.0)


class TestCalculationCache(unittest.TestCase):
    def test_put_and_get(self):
        cache = CalculationCache(max_size=10, ttl=60.0)
        cache.put("key1", "value1")
        self.assertEqual(cache.get("key1"), "value1")

    def test_miss_returns_none(self):
        cache = CalculationCache(max_size=10, ttl=60.0)
        self.assertIsNone(cache.get("nonexistent"))

    def test_ttl_expiry(self):
        cache = CalculationCache(max_size=10, ttl=0.05)
        cache.put("expiring", "data")
        time.sleep(0.1)
        self.assertIsNone(cache.get("expiring"))

    def test_max_size_eviction(self):
        cache = CalculationCache(max_size=3, ttl=60.0)
        for i in range(4):
            cache.put(f"key{i}", i)
        # After inserting 4 items into a size-3 cache, oldest should be evicted
        self.assertIsNone(cache.get("key0"))
        self.assertEqual(cache.get("key3"), 3)

    def test_clear(self):
        cache = CalculationCache(max_size=10, ttl=60.0)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.clear()
        self.assertIsNone(cache.get("a"))
        self.assertIsNone(cache.get("b"))


class TestOptionContractDataclass(unittest.TestCase):
    def test_construction(self):
        contract = OptionContract(
            symbol="SPY231215C00450000",
            underlying="SPY",
            strike=450.0,
            expiry=date(2023, 12, 15),
            option_type="CALL",
            bid=5.10,
            ask=5.20,
            last=5.15,
            volume=1200,
            open_interest=8500,
            underlying_price=450.0,
        )
        self.assertEqual(contract.option_type, "CALL")
        self.assertAlmostEqual(contract.strike, 450.0)
        self.assertGreater(contract.timestamp, 0.0)


class TestVolatilityModelEnum(unittest.TestCase):
    def test_members(self):
        models = {m.value for m in VolatilityModel}
        self.assertIn("BLACK_SCHOLES", models)
        self.assertIn("SABR", models)


if __name__ == "__main__":
    unittest.main()
