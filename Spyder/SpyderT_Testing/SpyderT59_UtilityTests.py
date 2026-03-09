#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT59_UtilityTests.py
Purpose: Unit tests for U-series utility modules (T59)

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-03-03 Time: 06:00:00

Module Description:
    Covers four self-contained U-series utility modules with no GUI or
    broker dependencies:
      - SpyderU06_MathUtils        — math/stats/finance helpers
      - SpyderU08_Validators       — input validation functions
      - SpyderU13_TechnicalIndicators — RSI, MACD, Bollinger Bands, etc.
      - SpyderU14_OptionStrategies — option payoffs and strategy builders

Change Log:
    2026-03-03:
        - Created (T59: U-series utility test suite)
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import importlib
import importlib.util
import math
import sys
import unittest
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


# Load modules under test.
# U06 has no local Spyder imports — load directly.
_u06 = _load("Spyder/SpyderU_Utilities/SpyderU06_MathUtils.py")

# U08 / U13 / U14 import SpyderLogger/SpyderErrorHandler.
# sys.path already contains _REPO_ROOT so the `Spyder.*` package is resolvable.
_u08 = _load("Spyder/SpyderU_Utilities/SpyderU08_Validators.py")
_u13 = _load("Spyder/SpyderU_Utilities/SpyderU13_TechnicalIndicators.py")
_u14 = _load("Spyder/SpyderU_Utilities/SpyderU14_OptionStrategies.py")

# ── U06 symbols ────────────────────────────────────────────────────────────────
round_price = _u06.round_price
round_to_tick = _u06.round_to_tick
calculate_percentage_change = _u06.calculate_percentage_change
calculate_compound_return = _u06.calculate_compound_return
calculate_mean = _u06.calculate_mean
calculate_std_dev = _u06.calculate_std_dev
calculate_kelly_criterion = _u06.calculate_kelly_criterion
calculate_risk_reward_ratio = _u06.calculate_risk_reward_ratio
linear_interpolation = _u06.linear_interpolation

# ── U08 symbols ────────────────────────────────────────────────────────────────
is_valid_string = _u08.is_valid_string
is_valid_number = _u08.is_valid_number
is_valid_integer = _u08.is_valid_integer
is_valid_boolean = _u08.is_valid_boolean
is_valid_symbol = _u08.is_valid_symbol
is_valid_price = _u08.is_valid_price
is_valid_quantity = _u08.is_valid_quantity
is_valid_order_type = _u08.is_valid_order_type
is_valid_time_in_force = _u08.is_valid_time_in_force
is_valid_percentage = _u08.is_valid_percentage
is_valid_account_balance = _u08.is_valid_account_balance

# ── U13 symbols ────────────────────────────────────────────────────────────────
TechnicalIndicators = _u13.TechnicalIndicators

# ── U14 symbols ────────────────────────────────────────────────────────────────
OptionStrategies = _u14.OptionStrategies
OptionType = _u14.OptionType
PositionType = _u14.PositionType
OptionStrategy = _u14.OptionStrategy
OptionLeg = _u14.OptionLeg


# ==============================================================================
# HELPERS
# ==============================================================================

try:
    import pandas as pd
    _pd_available = True
except ImportError:
    _pd_available = False


def _price_series(values):
    """Return a pd.Series from a list of floats (or a list if no pandas)."""
    if _pd_available:
        return pd.Series(values, dtype=float)
    return values


# ==============================================================================
# U06 — MathUtils tests
# ==============================================================================

class TestRoundPrice(unittest.TestCase):
    """round_price — Decimal-exact banker rounding."""

    def test_rounds_to_2_decimal_places_by_default(self):
        result = round_price(123.456)
        self.assertAlmostEqual(result, 123.46, places=2)

    def test_rounds_up_at_half(self):
        # ROUND_HALF_UP: 0.005 rounds to 0.01
        result = round_price(0.005)
        self.assertAlmostEqual(result, 0.01, places=2)

    def test_custom_precision_zero(self):
        result = round_price(99.7, precision=0)
        self.assertAlmostEqual(result, 100.0, places=0)

    def test_custom_precision_4(self):
        result = round_price(1.23456, precision=4)
        self.assertAlmostEqual(result, 1.2346, places=4)

    def test_returns_float(self):
        self.assertIsInstance(round_price(50.0), float)

    def test_integer_input_works(self):
        self.assertAlmostEqual(round_price(100, precision=2), 100.00, places=2)


class TestRoundToTick(unittest.TestCase):
    """round_to_tick — snap to nearest tick increment."""

    def test_rounds_to_tick_0_05(self):
        result = round_to_tick(1.03, 0.05)
        self.assertAlmostEqual(result, 1.05, places=5)

    def test_rounds_down_when_closer(self):
        result = round_to_tick(1.02, 0.05)
        self.assertAlmostEqual(result, 1.00, places=5)

    def test_already_on_tick(self):
        result = round_to_tick(1.50, 0.50)
        self.assertAlmostEqual(result, 1.50, places=5)

    def test_tick_size_1(self):
        result = round_to_tick(5.6, 1.0)
        self.assertAlmostEqual(result, 6.0, places=5)


class TestCalculatePercentageChange(unittest.TestCase):
    """calculate_percentage_change — (new - old) / |old| * 100."""

    def test_positive_change(self):
        result = calculate_percentage_change(100.0, 110.0)
        self.assertAlmostEqual(result, 10.0, places=5)

    def test_negative_change(self):
        result = calculate_percentage_change(100.0, 90.0)
        self.assertAlmostEqual(result, -10.0, places=5)

    def test_no_change(self):
        result = calculate_percentage_change(50.0, 50.0)
        self.assertAlmostEqual(result, 0.0, places=5)

    def test_zero_old_value_nonzero_new(self):
        result = calculate_percentage_change(0.0, 5.0)
        self.assertEqual(result, float("inf"))

    def test_both_zero_returns_zero(self):
        result = calculate_percentage_change(0.0, 0.0)
        self.assertAlmostEqual(result, 0.0, places=5)

    def test_negative_old_value(self):
        # abs(old_value) used → ((−10−(−12))/10)*100 = 20%
        result = calculate_percentage_change(-10.0, -12.0)
        self.assertAlmostEqual(result, -20.0, places=5)


class TestCalculateCompoundReturn(unittest.TestCase):
    """calculate_compound_return — (1+r1)*(1+r2)*...-1."""

    def test_positive_returns(self):
        # (1.10)*(1.10) - 1 = 0.21
        result = calculate_compound_return([0.10, 0.10])
        self.assertAlmostEqual(result, 0.21, places=10)

    def test_empty_returns(self):
        result = calculate_compound_return([])
        self.assertAlmostEqual(result, 0.0, places=5)

    def test_mixed_returns(self):
        # (1.10)*(0.90) - 1 = -0.01
        result = calculate_compound_return([0.10, -0.10])
        self.assertAlmostEqual(result, -0.01, places=5)

    def test_single_return(self):
        self.assertAlmostEqual(calculate_compound_return([0.05]), 0.05, places=10)


class TestCalculateMean(unittest.TestCase):
    """calculate_mean — arithmetic mean."""

    def test_positive_values(self):
        result = calculate_mean([1.0, 2.0, 3.0, 4.0, 5.0])
        self.assertAlmostEqual(result, 3.0, places=10)

    def test_single_value(self):
        self.assertAlmostEqual(calculate_mean([7.0]), 7.0, places=10)

    def test_negative_values(self):
        self.assertAlmostEqual(calculate_mean([-1.0, 1.0]), 0.0, places=10)


class TestCalculateStdDev(unittest.TestCase):
    """calculate_std_dev — sample std by default."""

    def test_sample_stddev_is_positive(self):
        result = calculate_std_dev([1.0, 2.0, 3.0, 4.0, 5.0])
        self.assertGreater(result, 0.0)

    def test_identical_values_zero_std(self):
        result = calculate_std_dev([5.0, 5.0, 5.0, 5.0])
        self.assertAlmostEqual(result, 0.0, places=10)

    def test_population_std_smaller_than_sample(self):
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        sample = calculate_std_dev(data, sample=True)
        population = calculate_std_dev(data, sample=False)
        self.assertGreater(sample, population)


class TestCalculateKellyCriterion(unittest.TestCase):
    """calculate_kelly_criterion — capped at 25%."""

    def test_typical_case(self):
        # Win 60%, avg_win = avg_loss → kelly = (0.6*1 - 0.4)/1 = 0.20
        result = calculate_kelly_criterion(0.60, 100.0, 100.0)
        self.assertAlmostEqual(result, 0.20, places=5)

    def test_result_capped_at_0_25(self):
        result = calculate_kelly_criterion(0.99, 1000.0, 1.0)
        self.assertLessEqual(result, 0.25)

    def test_zero_win_rate_returns_zero(self):
        result = calculate_kelly_criterion(0.0, 100.0, 100.0)
        self.assertAlmostEqual(result, 0.0, places=5)

    def test_negative_avg_loss_returns_zero(self):
        result = calculate_kelly_criterion(0.6, 100.0, -50.0)
        self.assertAlmostEqual(result, 0.0, places=5)

    def test_result_non_negative(self):
        result = calculate_kelly_criterion(0.3, 50.0, 100.0)
        self.assertGreaterEqual(result, 0.0)


class TestCalculateRiskRewardRatio(unittest.TestCase):
    """calculate_risk_reward_ratio — reward / risk."""

    def test_equal_risk_and_reward(self):
        result = calculate_risk_reward_ratio(100.0, 110.0, 90.0)
        self.assertAlmostEqual(result, 1.0, places=5)

    def test_two_to_one_ratio(self):
        result = calculate_risk_reward_ratio(100.0, 120.0, 90.0)
        self.assertAlmostEqual(result, 2.0, places=5)

    def test_zero_risk_non_zero_reward(self):
        result = calculate_risk_reward_ratio(100.0, 110.0, 100.0)
        self.assertEqual(result, float("inf"))

    def test_zero_risk_zero_reward(self):
        result = calculate_risk_reward_ratio(100.0, 100.0, 100.0)
        self.assertAlmostEqual(result, 0.0, places=5)


class TestLinearInterpolation(unittest.TestCase):
    """linear_interpolation — classic two-point lerp."""

    def test_midpoint(self):
        result = linear_interpolation(0.5, 0.0, 0.0, 1.0, 10.0)
        self.assertAlmostEqual(result, 5.0, places=10)

    def test_at_x1(self):
        result = linear_interpolation(0.0, 0.0, 100.0, 1.0, 200.0)
        self.assertAlmostEqual(result, 100.0, places=10)

    def test_at_x2(self):
        result = linear_interpolation(1.0, 0.0, 100.0, 1.0, 200.0)
        self.assertAlmostEqual(result, 200.0, places=10)

    def test_extrapolation(self):
        result = linear_interpolation(2.0, 0.0, 0.0, 1.0, 10.0)
        self.assertAlmostEqual(result, 20.0, places=10)


# ==============================================================================
# U08 — Validators tests
# ==============================================================================

class TestIsValidString(unittest.TestCase):
    """is_valid_string — type, length, empty-flag checks."""

    def test_simple_valid_string(self):
        self.assertTrue(is_valid_string("hello"))

    def test_empty_string_rejected_by_default(self):
        self.assertFalse(is_valid_string(""))

    def test_empty_string_allowed_when_flag_set(self):
        self.assertTrue(is_valid_string("", allow_empty=True))

    def test_non_string_rejected(self):
        self.assertFalse(is_valid_string(123))

    def test_min_length_violation(self):
        self.assertFalse(is_valid_string("ab", min_length=5))

    def test_max_length_violation(self):
        self.assertFalse(is_valid_string("abcdef", max_length=3))

    def test_within_length_bounds(self):
        self.assertTrue(is_valid_string("abc", min_length=1, max_length=5))


class TestIsValidNumber(unittest.TestCase):
    """is_valid_number — numeric conversion and constraint checks."""

    def test_integer_accepted(self):
        self.assertTrue(is_valid_number(5))

    def test_float_accepted(self):
        self.assertTrue(is_valid_number(3.14))

    def test_string_number_accepted(self):
        self.assertTrue(is_valid_number("42"))

    def test_non_numeric_string(self):
        self.assertFalse(is_valid_number("abc"))

    def test_negative_rejected_when_flag_false(self):
        self.assertFalse(is_valid_number(-1.0, allow_negative=False))

    def test_zero_rejected_when_flag_false(self):
        self.assertFalse(is_valid_number(0, allow_zero=False))

    def test_below_min_rejected(self):
        self.assertFalse(is_valid_number(5.0, min_value=10.0))

    def test_above_max_rejected(self):
        self.assertFalse(is_valid_number(100.0, max_value=50.0))

    def test_none_rejected(self):
        self.assertFalse(is_valid_number(None))


class TestIsValidInteger(unittest.TestCase):
    """is_valid_integer — booleans excluded, bounds check."""

    def test_int_accepted(self):
        self.assertTrue(is_valid_integer(42))

    def test_bool_rejected(self):
        # bool is subclass of int; must be explicitly rejected
        self.assertFalse(is_valid_integer(True))
        self.assertFalse(is_valid_integer(False))

    def test_float_is_converted_to_int(self):
        # Implementation uses int() conversion, so 3.14 → int(3.14)=3 → accepted
        self.assertTrue(is_valid_integer(3.14))

    def test_min_violation(self):
        self.assertFalse(is_valid_integer(1, min_value=5))

    def test_max_violation(self):
        self.assertFalse(is_valid_integer(10, max_value=5))

    def test_within_bounds(self):
        self.assertTrue(is_valid_integer(5, min_value=1, max_value=10))


class TestIsValidBoolean(unittest.TestCase):
    """is_valid_boolean — strict isinstance check."""

    def test_true_accepted(self):
        self.assertTrue(is_valid_boolean(True))

    def test_false_accepted(self):
        self.assertTrue(is_valid_boolean(False))

    def test_integer_one_rejected(self):
        self.assertFalse(is_valid_boolean(1))

    def test_string_rejected(self):
        self.assertFalse(is_valid_boolean("true"))

    def test_none_rejected(self):
        self.assertFalse(is_valid_boolean(None))


class TestIsValidSymbol(unittest.TestCase):
    """is_valid_symbol — 1-5 uppercase letters for equities."""

    def test_spy_valid(self):
        self.assertTrue(is_valid_symbol("SPY"))

    def test_single_letter(self):
        self.assertTrue(is_valid_symbol("A"))

    def test_five_letters(self):
        self.assertTrue(is_valid_symbol("GOOGL"))

    def test_six_letters_rejected(self):
        self.assertFalse(is_valid_symbol("TOOLNG"))

    def test_lowercase_rejected(self):
        self.assertFalse(is_valid_symbol("spy"))

    def test_digit_in_symbol_rejected(self):
        self.assertFalse(is_valid_symbol("SPY1"))

    def test_empty_rejected(self):
        self.assertFalse(is_valid_symbol(""))

    def test_non_string_rejected(self):
        self.assertFalse(is_valid_symbol(123))


class TestIsValidPrice(unittest.TestCase):
    """is_valid_price — must be within [MIN_PRICE, MAX_PRICE]."""

    def test_typical_price(self):
        self.assertTrue(is_valid_price(450.0))

    def test_zero_rejected(self):
        self.assertFalse(is_valid_price(0.0))

    def test_negative_rejected(self):
        self.assertFalse(is_valid_price(-1.0))

    def test_string_price_accepted(self):
        # is_valid_price → is_valid_number which converts strings
        self.assertTrue(is_valid_price("5.50"))

    def test_non_numeric_rejected(self):
        self.assertFalse(is_valid_price("price"))


class TestIsValidOrderType(unittest.TestCase):
    """is_valid_order_type — membership in VALID_ORDER_TYPES."""

    def test_market_order(self):
        self.assertTrue(is_valid_order_type("MKT"))

    def test_limit_order(self):
        self.assertTrue(is_valid_order_type("LMT"))

    def test_stop_limit(self):
        self.assertTrue(is_valid_order_type("STP_LMT"))

    def test_invalid_type(self):
        self.assertFalse(is_valid_order_type("INVALID"))

    def test_lowercase_invalid(self):
        self.assertFalse(is_valid_order_type("mkt"))


class TestIsValidTimeInForce(unittest.TestCase):
    """is_valid_time_in_force — membership in VALID_TIME_IN_FORCE."""

    def test_day(self):
        self.assertTrue(is_valid_time_in_force("DAY"))

    def test_gtc(self):
        self.assertTrue(is_valid_time_in_force("GTC"))

    def test_ioc(self):
        self.assertTrue(is_valid_time_in_force("IOC"))

    def test_invalid(self):
        self.assertFalse(is_valid_time_in_force("WEEK"))


class TestIsValidPercentage(unittest.TestCase):
    """is_valid_percentage — default range 0-100."""

    def test_zero_accepted(self):
        self.assertTrue(is_valid_percentage(0.0))

    def test_hundred_accepted(self):
        self.assertTrue(is_valid_percentage(100.0))

    def test_midpoint_accepted(self):
        self.assertTrue(is_valid_percentage(50.0))

    def test_negative_rejected(self):
        self.assertFalse(is_valid_percentage(-1.0))

    def test_over_100_rejected(self):
        self.assertFalse(is_valid_percentage(100.1))


# ==============================================================================
# U13 — TechnicalIndicators tests
# ==============================================================================

@unittest.skipUnless(_pd_available, "pandas required")
class TestTechnicalIndicatorsConstruction(unittest.TestCase):
    """TechnicalIndicators — basic construction."""

    def test_creates_instance(self):
        ti = TechnicalIndicators()
        self.assertIsInstance(ti, TechnicalIndicators)

    def test_has_logger(self):
        ti = TechnicalIndicators()
        self.assertIsNotNone(ti.logger)


@unittest.skipUnless(_pd_available, "pandas required")
class TestCalculateRSI(unittest.TestCase):
    """TechnicalIndicators.calculate_rsi — RSI values in [0, 100]."""

    def setUp(self):
        self.ti = TechnicalIndicators()

    def test_rsi_values_in_range(self):
        prices = _price_series([100 + i for i in range(30)])
        rsi = self.ti.calculate_rsi(prices, period=14)
        valid = rsi.dropna()
        self.assertTrue((valid >= 0).all() and (valid <= 100).all())

    def test_insufficient_data_returns_empty_or_nan(self):
        prices = _price_series([100, 101, 102])
        rsi = self.ti.calculate_rsi(prices, period=14)
        # Should return empty series or all-NaN (graceful handling)
        self.assertIsInstance(rsi, pd.Series)

    def test_all_up_prices_high_rsi(self):
        prices = _price_series([100 + i * 0.5 for i in range(30)])
        rsi = self.ti.calculate_rsi(prices, period=14)
        last_rsi = rsi.dropna().iloc[-1]
        self.assertGreater(last_rsi, 50)

    def test_all_down_prices_low_rsi(self):
        prices = _price_series([100 - i * 0.5 for i in range(30)])
        rsi = self.ti.calculate_rsi(prices, period=14)
        last_rsi = rsi.dropna().iloc[-1]
        self.assertLess(last_rsi, 50)

    def test_returns_series(self):
        prices = _price_series([100 + i for i in range(30)])
        result = self.ti.calculate_rsi(prices)
        self.assertIsInstance(result, pd.Series)


@unittest.skipUnless(_pd_available, "pandas required")
class TestCalculateMACD(unittest.TestCase):
    """TechnicalIndicators.calculate_macd — returns dict with expected keys."""

    def setUp(self):
        self.ti = TechnicalIndicators()
        self.prices = _price_series([100.0 + i * 0.3 for i in range(60)])

    def test_returns_dict(self):
        result = self.ti.calculate_macd(self.prices)
        self.assertIsInstance(result, dict)

    def test_has_macd_key(self):
        result = self.ti.calculate_macd(self.prices)
        self.assertIn("MACD", result)

    def test_has_signal_key(self):
        result = self.ti.calculate_macd(self.prices)
        self.assertIn("Signal", result)

    def test_macd_is_series(self):
        result = self.ti.calculate_macd(self.prices)
        self.assertIsInstance(result["MACD"], pd.Series)


@unittest.skipUnless(_pd_available, "pandas required")
class TestCalculateBollingerBands(unittest.TestCase):
    """TechnicalIndicators.calculate_bollinger_bands — band ordering."""

    def setUp(self):
        self.ti = TechnicalIndicators()
        import numpy as np
        rng = [450 + 5 * (i % 7 - 3) for i in range(40)]
        self.prices = _price_series(rng)

    def test_returns_dict(self):
        result = self.ti.calculate_bollinger_bands(self.prices)
        self.assertIsInstance(result, dict)

    def test_has_middle_band(self):
        result = self.ti.calculate_bollinger_bands(self.prices)
        self.assertIn("Middle", result)

    def test_upper_above_middle(self):
        result = self.ti.calculate_bollinger_bands(self.prices)
        upper = result["Upper"].dropna()
        middle = result["Middle"].dropna()
        # Align by index
        common = upper.index.intersection(middle.index)
        if len(common) > 0:
            self.assertTrue((upper[common] >= middle[common]).all())

    def test_lower_below_middle(self):
        result = self.ti.calculate_bollinger_bands(self.prices)
        lower = result["Lower"].dropna()
        middle = result["Middle"].dropna()
        common = lower.index.intersection(middle.index)
        if len(common) > 0:
            self.assertTrue((lower[common] <= middle[common]).all())


# ==============================================================================
# U14 — OptionStrategies tests
# ==============================================================================

@unittest.skipUnless(_pd_available, "numpy/pandas required")
class TestOptionStrategiesConstruction(unittest.TestCase):
    """OptionStrategies — basic construction."""

    def test_creates_instance(self):
        os_util = OptionStrategies()
        self.assertIsInstance(os_util, OptionStrategies)


@unittest.skipUnless(_pd_available, "numpy/pandas required")
class TestOptionPayoff(unittest.TestCase):
    """OptionStrategies.calculate_option_payoff — at-expiry P&L."""

    # LONG CALL: payoff = max(spot - strike, 0) - premium, * 100
    def test_long_call_in_the_money(self):
        os_util = OptionStrategies()
        # strike=450, premium=5, spot=470 → (470-450-5)*100 = 1500
        result = os_util.calculate_option_payoff("CALL", "LONG", 450.0, 5.0, 470.0)
        self.assertAlmostEqual(result, 1500.0, places=5)

    def test_long_call_out_of_the_money(self):
        os_util = OptionStrategies()
        # spot < strike → intrinsic=0, payoff = (0 - 5)*100 = -500
        result = os_util.calculate_option_payoff("CALL", "LONG", 450.0, 5.0, 430.0)
        self.assertAlmostEqual(result, -500.0, places=5)

    # LONG PUT: payoff = max(strike - spot, 0) - premium, * 100
    def test_long_put_in_the_money(self):
        os_util = OptionStrategies()
        # strike=450, premium=5, spot=430 → (450-430-5)*100 = 1500
        result = os_util.calculate_option_payoff("PUT", "LONG", 450.0, 5.0, 430.0)
        self.assertAlmostEqual(result, 1500.0, places=5)

    def test_long_put_out_of_the_money(self):
        os_util = OptionStrategies()
        # spot > strike → intrinsic=0, payoff = (0 - 5)*100 = -500
        result = os_util.calculate_option_payoff("PUT", "LONG", 450.0, 5.0, 470.0)
        self.assertAlmostEqual(result, -500.0, places=5)

    # SHORT CALL: payoff = premium - max(spot - strike, 0), * 100
    def test_short_call_out_of_the_money(self):
        os_util = OptionStrategies()
        # spot < strike → intrinsic=0, payoff = (5 - 0)*100 = 500
        result = os_util.calculate_option_payoff("CALL", "SHORT", 450.0, 5.0, 430.0)
        self.assertAlmostEqual(result, 500.0, places=5)

    def test_short_put_out_of_the_money(self):
        os_util = OptionStrategies()
        # spot > strike → intrinsic=0, payoff = (5 - 0)*100 = 500
        result = os_util.calculate_option_payoff("PUT", "SHORT", 450.0, 5.0, 470.0)
        self.assertAlmostEqual(result, 500.0, places=5)


@unittest.skipUnless(_pd_available, "numpy/pandas required")
class TestStrategyBuilders(unittest.TestCase):
    """OptionStrategies strategy factory methods — basic structural checks."""

    def setUp(self):
        self.os_util = OptionStrategies()
        from datetime import datetime, timedelta
        self.expiry = (datetime.now() + timedelta(days=30)).replace(microsecond=0)

    def test_create_bull_call_spread_returns_strategy(self):
        strategy = self.os_util.create_bull_call_spread(
            long_strike=455.0,
            short_strike=460.0,
            expiry=self.expiry,
            long_premium=3.00,
            short_premium=1.00,
            underlying_price=457.0,
        )
        self.assertIsInstance(strategy, OptionStrategy)

    def test_bull_call_spread_has_two_legs(self):
        strategy = self.os_util.create_bull_call_spread(
            long_strike=455.0,
            short_strike=460.0,
            expiry=self.expiry,
            long_premium=3.00,
            short_premium=1.00,
            underlying_price=457.0,
        )
        self.assertEqual(len(strategy.legs), 2)

    def test_create_bear_put_spread_returns_strategy(self):
        strategy = self.os_util.create_bear_put_spread(
            long_strike=450.0,
            short_strike=445.0,
            expiry=self.expiry,
            long_premium=3.00,
            short_premium=1.00,
            underlying_price=447.0,
        )
        self.assertIsInstance(strategy, OptionStrategy)

    def test_create_straddle_returns_strategy(self):
        strategy = self.os_util.create_straddle(
            strike=455.0,
            expiry=self.expiry,
            call_premium=3.00,
            put_premium=3.00,
            underlying_price=455.0,
        )
        self.assertIsInstance(strategy, OptionStrategy)

    def test_straddle_has_two_legs(self):
        strategy = self.os_util.create_straddle(
            strike=455.0,
            expiry=self.expiry,
            call_premium=3.00,
            put_premium=3.00,
            underlying_price=455.0,
        )
        self.assertEqual(len(strategy.legs), 2)

    def test_create_iron_condor_returns_strategy(self):
        strategy = self.os_util.create_iron_condor(
            put_long_strike=440.0,
            put_short_strike=445.0,
            call_short_strike=460.0,
            call_long_strike=465.0,
            expiry=self.expiry,
            premiums=[1.00, 2.50, 2.50, 1.00],
            underlying_price=452.0,
        )
        self.assertIsInstance(strategy, OptionStrategy)

    def test_iron_condor_has_four_legs(self):
        strategy = self.os_util.create_iron_condor(
            put_long_strike=440.0,
            put_short_strike=445.0,
            call_short_strike=460.0,
            call_long_strike=465.0,
            expiry=self.expiry,
            premiums=[1.00, 2.50, 2.50, 1.00],
            underlying_price=452.0,
        )
        self.assertEqual(len(strategy.legs), 4)


@unittest.skipUnless(_pd_available, "numpy/pandas required")
class TestStrategyMetrics(unittest.TestCase):
    """OptionStrategies strategy metric methods — return type checks."""

    def setUp(self):
        self.os_util = OptionStrategies()
        from datetime import datetime, timedelta
        expiry = (datetime.now() + timedelta(days=30)).replace(microsecond=0)
        self.bull_spread = self.os_util.create_bull_call_spread(
            long_strike=455.0,
            short_strike=460.0,
            expiry=expiry,
            long_premium=3.00,
            short_premium=1.00,
            underlying_price=457.0,
        )

    def test_max_profit_is_float(self):
        result = self.os_util.calculate_max_profit(self.bull_spread)
        self.assertIsInstance(result, (int, float))

    def test_max_loss_is_float(self):
        result = self.os_util.calculate_max_loss(self.bull_spread)
        self.assertIsInstance(result, (int, float))

    def test_breakeven_points_is_list(self):
        result = self.os_util.calculate_breakeven_points(self.bull_spread)
        self.assertIsInstance(result, list)

    def test_breakeven_points_are_numeric(self):
        result = self.os_util.calculate_breakeven_points(self.bull_spread)
        for pt in result:
            self.assertIsInstance(pt, (int, float))
            self.assertTrue(math.isfinite(pt))


# ==============================================================================
# ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
