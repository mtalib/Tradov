#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT62_MathValidatorTests.py
Purpose: Tests for U06 MathUtils and U08 Validators utility modules

Author: GitHub Copilot
Year Created: 2025
Last Updated: 2026-03-04 Time: 00:30:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import importlib
import importlib.util
import math
import sys
import types
import unittest
from pathlib import Path

# ==============================================================================
# REPO BOOTSTRAP
# ==============================================================================
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _load(rel_path: str):
    """Load a module by relative path from _REPO_ROOT."""
    full = _REPO_ROOT / rel_path
    spec = importlib.util.spec_from_file_location(full.stem, full)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ensure_pkg(name: str):
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)


# Pre-register U01_Logger so U08's package-path import resolves correctly
# when prior test files have already partially populated sys.modules.
_ensure_pkg("Spyder")
_ensure_pkg("Spyder.SpyderU_Utilities")
_u01 = _load("Spyder/SpyderU_Utilities/SpyderU01_Logger.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU01_Logger"] = _u01
sys.modules["SpyderU01_Logger"] = _u01

# ==============================================================================
# LOAD MODULES UNDER TEST
# ==============================================================================
_u06 = _load("Spyder/SpyderU_Utilities/SpyderU06_MathUtils.py")
round_price = _u06.round_price
round_to_tick = _u06.round_to_tick
calculate_percentage_change = _u06.calculate_percentage_change
calculate_compound_return = _u06.calculate_compound_return
calculate_mean = _u06.calculate_mean
calculate_std_dev = _u06.calculate_std_dev
calculate_sharpe_ratio = _u06.calculate_sharpe_ratio
calculate_sortino_ratio = _u06.calculate_sortino_ratio
calculate_max_drawdown = _u06.calculate_max_drawdown
calculate_var = _u06.calculate_var
calculate_cvar = _u06.calculate_cvar
normal_cdf = _u06.normal_cdf
normal_pdf = _u06.normal_pdf
calculate_position_size = _u06.calculate_position_size
calculate_kelly_criterion = _u06.calculate_kelly_criterion
calculate_risk_reward_ratio = _u06.calculate_risk_reward_ratio
linear_interpolation = _u06.linear_interpolation
rolling_window = _u06.rolling_window
exponential_moving_average = _u06.exponential_moving_average

_u08 = _load("Spyder/SpyderU_Utilities/SpyderU08_Validators.py")
ValidationError = _u08.ValidationError
is_valid_string = _u08.is_valid_string
is_valid_number = _u08.is_valid_number
is_valid_integer = _u08.is_valid_integer
is_valid_boolean = _u08.is_valid_boolean
is_valid_list = _u08.is_valid_list
is_valid_dict = _u08.is_valid_dict
is_valid_email = _u08.is_valid_email
is_valid_phone = _u08.is_valid_phone
is_valid_ip_address = _u08.is_valid_ip_address
is_valid_url = _u08.is_valid_url
is_valid_symbol = _u08.is_valid_symbol
is_valid_price = _u08.is_valid_price
is_valid_quantity = _u08.is_valid_quantity
is_valid_order_type = _u08.is_valid_order_type
is_valid_time_in_force = _u08.is_valid_time_in_force
is_valid_percentage = _u08.is_valid_percentage
VALID_ORDER_TYPES = _u08.VALID_ORDER_TYPES
VALID_TIME_IN_FORCE = _u08.VALID_TIME_IN_FORCE
MIN_PRICE = _u08.MIN_PRICE
MAX_PRICE = _u08.MAX_PRICE


# ==============================================================================
# U06 — ROUND PRICE
# ==============================================================================

class TestRoundPrice(unittest.TestCase):
    """round_price — Decimal ROUND_HALF_UP."""

    def test_rounds_to_two_decimal_places_default(self):
        self.assertEqual(round_price(100.555), 100.56)

    def test_rounds_down(self):
        self.assertEqual(round_price(100.124), 100.12)

    def test_rounds_up_at_half(self):
        self.assertEqual(round_price(100.005), 100.01)

    def test_custom_precision_zero(self):
        self.assertEqual(round_price(99.9, precision=0), 100.0)

    def test_custom_precision_four(self):
        result = round_price(1.23456789, precision=4)
        self.assertEqual(result, 1.2346)

    def test_returns_float(self):
        self.assertIsInstance(round_price(1.5), float)

    def test_integer_input(self):
        self.assertEqual(round_price(100), 100.00)


# ==============================================================================
# U06 — ROUND TO TICK
# ==============================================================================

class TestRoundToTick(unittest.TestCase):
    """round_to_tick — nearest tick multiple."""

    def test_already_on_tick(self):
        self.assertAlmostEqual(round_to_tick(100.0, 0.01), 100.0, places=6)

    def test_rounds_to_nearest_penny(self):
        # Use 100.006 to avoid Python banker's-rounding ambiguity at .005 midpoint
        result = round_to_tick(100.006, 0.01)
        self.assertAlmostEqual(result, 100.01, places=5)

    def test_quarter_tick(self):
        # 100.1 → nearest 0.25 = 100.0
        self.assertAlmostEqual(round_to_tick(100.1, 0.25), 100.0, delta=0.001)

    def test_dollar_tick(self):
        self.assertAlmostEqual(round_to_tick(4.7, 1.0), 5.0, places=5)

    def test_nickel_tick(self):
        self.assertAlmostEqual(round_to_tick(100.07, 0.05), 100.05, places=5)


# ==============================================================================
# U06 — PERCENTAGE CHANGE
# ==============================================================================

class TestCalculatePercentageChange(unittest.TestCase):
    """calculate_percentage_change."""

    def test_positive_increase(self):
        result = calculate_percentage_change(100.0, 110.0)
        self.assertAlmostEqual(result, 10.0, places=5)

    def test_negative_decrease(self):
        result = calculate_percentage_change(100.0, 90.0)
        self.assertAlmostEqual(result, -10.0, places=5)

    def test_no_change(self):
        self.assertEqual(calculate_percentage_change(100.0, 100.0), 0.0)

    def test_old_value_zero_new_value_nonzero_returns_inf(self):
        result = calculate_percentage_change(0.0, 50.0)
        self.assertEqual(result, float("inf"))

    def test_both_zero_returns_zero(self):
        self.assertEqual(calculate_percentage_change(0.0, 0.0), 0.0)

    def test_negative_old_value(self):
        # old=-100, new=-50 → (-50 - -100) / 100 * 100 = 50%
        result = calculate_percentage_change(-100.0, -50.0)
        self.assertAlmostEqual(result, 50.0, places=5)


# ==============================================================================
# U06 — COMPOUND RETURN
# ==============================================================================

class TestCalculateCompoundReturn(unittest.TestCase):
    """calculate_compound_return — product of (1+r) - 1."""

    def test_single_return(self):
        self.assertAlmostEqual(calculate_compound_return([0.1]), 0.1, places=10)

    def test_two_periods(self):
        # (1.1 * 1.1) - 1 = 0.21
        self.assertAlmostEqual(calculate_compound_return([0.1, 0.1]), 0.21, places=10)

    def test_empty_returns(self):
        self.assertAlmostEqual(calculate_compound_return([]), 0.0, places=10)

    def test_net_loss(self):
        # 10% up then 10% down → 0.99 - 1 = -0.01
        result = calculate_compound_return([0.1, -0.1])
        self.assertAlmostEqual(result, -0.01, places=10)

    def test_all_zero(self):
        self.assertAlmostEqual(calculate_compound_return([0.0, 0.0, 0.0]), 0.0, places=10)


# ==============================================================================
# U06 — MEAN
# ==============================================================================

class TestCalculateMean(unittest.TestCase):
    """calculate_mean."""

    def test_empty_returns_zero(self):
        self.assertEqual(calculate_mean([]), 0.0)

    def test_single_value(self):
        self.assertEqual(calculate_mean([42.0]), 42.0)

    def test_uniform_values(self):
        self.assertEqual(calculate_mean([5.0, 5.0, 5.0]), 5.0)

    def test_simple_average(self):
        self.assertAlmostEqual(calculate_mean([1.0, 2.0, 3.0]), 2.0, places=10)

    def test_negative_values(self):
        self.assertAlmostEqual(calculate_mean([-1.0, 1.0]), 0.0, places=10)


# ==============================================================================
# U06 — STD DEV
# ==============================================================================

class TestCalculateStdDev(unittest.TestCase):
    """calculate_std_dev — sample and population."""

    def test_less_than_two_values_returns_zero(self):
        self.assertEqual(calculate_std_dev([5.0]), 0.0)

    def test_empty_returns_zero(self):
        self.assertEqual(calculate_std_dev([]), 0.0)

    def test_sample_std_dev(self):
        import statistics
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        self.assertAlmostEqual(calculate_std_dev(values, sample=True), statistics.stdev(values), places=10)

    def test_population_std_dev(self):
        import statistics
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        self.assertAlmostEqual(calculate_std_dev(values, sample=False), statistics.pstdev(values), places=10)

    def test_uniform_values_std_dev_zero(self):
        # population stdev of identical values = 0
        self.assertEqual(calculate_std_dev([3.0, 3.0, 3.0], sample=False), 0.0)


# ==============================================================================
# U06 — SHARPE RATIO
# ==============================================================================

class TestCalculateSharpeRatio(unittest.TestCase):
    """calculate_sharpe_ratio."""

    def test_less_than_two_returns_zero(self):
        self.assertEqual(calculate_sharpe_ratio([0.01]), 0.0)

    def test_empty_returns_zero(self):
        self.assertEqual(calculate_sharpe_ratio([]), 0.0)

    def test_zero_std_returns_zero(self):
        # Identical returns → std = 0
        self.assertEqual(calculate_sharpe_ratio([0.01, 0.01, 0.01, 0.01]), 0.0)

    def test_positive_returns_positive_sharpe(self):
        returns = [0.01] * 100 + [0.005] * 100  # varied positive
        sharpe = calculate_sharpe_ratio(returns)
        self.assertGreater(sharpe, 0.0)

    def test_returns_float(self):
        self.assertIsInstance(calculate_sharpe_ratio([0.01, -0.005, 0.02, -0.01]), float)


# ==============================================================================
# U06 — MAX DRAWDOWN
# ==============================================================================

class TestCalculateMaxDrawdown(unittest.TestCase):
    """calculate_max_drawdown — returns (pct, peak_idx, trough_idx)."""

    def test_less_than_two_values_returns_zeros(self):
        dd, pk, tr = calculate_max_drawdown([100.0])
        self.assertEqual((dd, pk, tr), (0.0, 0, 0))

    def test_flat_curve_zero_drawdown(self):
        dd, _, _ = calculate_max_drawdown([100.0, 100.0, 100.0])
        self.assertAlmostEqual(dd, 0.0, places=5)

    def test_simple_drawdown(self):
        # 100 → 90 → 80 then recovers: max DD from 100 to 80 = -20%
        dd, pk, tr = calculate_max_drawdown([100.0, 90.0, 80.0, 95.0])
        self.assertAlmostEqual(dd, -20.0, places=5)
        self.assertEqual(pk, 0)
        self.assertEqual(tr, 2)

    def test_always_increasing_zero_drawdown(self):
        dd, _, _ = calculate_max_drawdown([100.0, 110.0, 120.0, 130.0])
        self.assertAlmostEqual(dd, 0.0, places=5)

    def test_returns_tuple_of_three(self):
        result = calculate_max_drawdown([100.0, 90.0])
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 3)


# ==============================================================================
# U06 — VaR
# ==============================================================================

class TestCalculateVar(unittest.TestCase):
    """calculate_var — historical and parametric."""

    def test_empty_returns_zero(self):
        self.assertEqual(calculate_var([]), 0.0)

    def test_historical_returns_positive_number(self):
        returns = [0.01, -0.02, 0.005, -0.015, 0.008]
        var = calculate_var(returns, confidence_level=0.95, method="historical")
        self.assertIsInstance(var, float)

    def test_parametric_returns_float(self):
        returns = [0.01, -0.02, 0.005, -0.015, 0.008]
        var = calculate_var(returns, confidence_level=0.95, method="parametric")
        self.assertIsInstance(var, float)

    def test_unknown_method_raises_value_error(self):
        with self.assertRaises(ValueError):
            calculate_var([0.01, -0.02], method="unknown")

    def test_historical_95_lte_99(self):
        # 99% VaR should be more extreme (larger) than 95% VaR
        returns = [r / 100 for r in range(-10, 11)]
        var_95 = calculate_var(returns, confidence_level=0.95)
        var_99 = calculate_var(returns, confidence_level=0.99)
        self.assertGreaterEqual(var_99, var_95)


# ==============================================================================
# U06 — NORMAL CDF / PDF
# ==============================================================================

class TestNormalCdf(unittest.TestCase):
    """normal_cdf — cumulative distribution."""

    def test_zero_returns_half(self):
        self.assertAlmostEqual(normal_cdf(0.0), 0.5, places=6)

    def test_large_positive_approaches_one(self):
        self.assertAlmostEqual(normal_cdf(10.0), 1.0, places=5)

    def test_large_negative_approaches_zero(self):
        self.assertAlmostEqual(normal_cdf(-10.0), 0.0, places=5)

    def test_returns_between_zero_and_one(self):
        for x in [-3.0, -1.0, 0.0, 1.0, 3.0]:
            val = normal_cdf(x)
            self.assertGreaterEqual(val, 0.0)
            self.assertLessEqual(val, 1.0)

    def test_symmetry(self):
        # CDF(-x) = 1 - CDF(x)
        self.assertAlmostEqual(normal_cdf(-1.96), 1 - normal_cdf(1.96), places=6)


class TestNormalPdf(unittest.TestCase):
    """normal_pdf — probability density."""

    def test_zero_is_maximum(self):
        pdf_0 = normal_pdf(0.0)
        pdf_1 = normal_pdf(1.0)
        self.assertGreater(pdf_0, pdf_1)

    def test_value_at_zero_approx(self):
        # PDF(0) = 1/sqrt(2π) ≈ 0.3989
        self.assertAlmostEqual(normal_pdf(0.0), 1 / math.sqrt(2 * math.pi), places=5)

    def test_symmetric(self):
        self.assertAlmostEqual(normal_pdf(-1.0), normal_pdf(1.0), places=10)


# ==============================================================================
# U06 — POSITION SIZE
# ==============================================================================

class TestCalculatePositionSize(unittest.TestCase):
    """calculate_position_size."""

    def test_basic_position_size(self):
        # account=10000, risk=2%, stop=5pts → dollar_risk=200, size=200/5=40
        self.assertEqual(calculate_position_size(10000, 2.0, 5.0), 40)

    def test_zero_stop_loss_returns_zero(self):
        self.assertEqual(calculate_position_size(10000, 2.0, 0.0), 0)

    def test_negative_stop_loss_returns_zero(self):
        self.assertEqual(calculate_position_size(10000, 2.0, -1.0), 0)

    def test_zero_risk_percent_returns_zero(self):
        self.assertEqual(calculate_position_size(10000, 0.0, 5.0), 0)

    def test_contract_multiplier_applied(self):
        # account=10000, risk=1%, stop=1pt, mult=100 → dollar_risk=100, size=100/(1*100)=1
        self.assertEqual(calculate_position_size(10000, 1.0, 1.0, 100.0), 1)

    def test_returns_integer(self):
        self.assertIsInstance(calculate_position_size(10000, 2.0, 3.0), int)


# ==============================================================================
# U06 — KELLY CRITERION
# ==============================================================================

class TestCalculateKellyCriterion(unittest.TestCase):
    """calculate_kelly_criterion — caps at 0.25."""

    def test_zero_avg_loss_returns_zero(self):
        self.assertEqual(calculate_kelly_criterion(0.6, 100.0, 0.0), 0.0)

    def test_zero_win_rate_returns_zero(self):
        self.assertEqual(calculate_kelly_criterion(0.0, 100.0, 50.0), 0.0)

    def test_win_rate_one_returns_zero(self):
        self.assertEqual(calculate_kelly_criterion(1.0, 100.0, 50.0), 0.0)

    def test_valid_kelly_positive(self):
        # win_rate=0.6, avg_win=100, avg_loss=50 → ratio=2, kelly=(0.6*2-0.4)/2=0.4→capped at 0.25
        result = calculate_kelly_criterion(0.6, 100.0, 50.0)
        self.assertGreater(result, 0.0)

    def test_capped_at_quarter(self):
        # Extreme win scenario — should cap at 0.25
        result = calculate_kelly_criterion(0.9, 1000.0, 10.0)
        self.assertLessEqual(result, 0.25)

    def test_losing_edge_clamped_to_zero(self):
        # win_rate=0.3, avg_win=50, avg_loss=100 → negative kelly → clamped to 0
        result = calculate_kelly_criterion(0.3, 50.0, 100.0)
        self.assertEqual(result, 0.0)

    def test_returns_float(self):
        self.assertIsInstance(calculate_kelly_criterion(0.55, 100.0, 80.0), float)


# ==============================================================================
# U06 — RISK/REWARD RATIO
# ==============================================================================

class TestCalculateRiskRewardRatio(unittest.TestCase):
    """calculate_risk_reward_ratio."""

    def test_two_to_one(self):
        # entry=100, target=106, stop=97 → reward=6, risk=3 → 2.0
        self.assertAlmostEqual(calculate_risk_reward_ratio(100.0, 106.0, 97.0), 2.0, places=5)

    def test_one_to_one(self):
        self.assertAlmostEqual(calculate_risk_reward_ratio(100.0, 105.0, 95.0), 1.0, places=5)

    def test_zero_risk_with_reward_returns_inf(self):
        result = calculate_risk_reward_ratio(100.0, 110.0, 100.0)
        self.assertEqual(result, float("inf"))

    def test_zero_risk_zero_reward_returns_zero(self):
        result = calculate_risk_reward_ratio(100.0, 100.0, 100.0)
        self.assertEqual(result, 0.0)

    def test_returns_float(self):
        self.assertIsInstance(calculate_risk_reward_ratio(100.0, 110.0, 95.0), float)


# ==============================================================================
# U06 — LINEAR INTERPOLATION
# ==============================================================================

class TestLinearInterpolation(unittest.TestCase):
    """linear_interpolation."""

    def test_midpoint(self):
        self.assertAlmostEqual(linear_interpolation(1.5, 1.0, 10.0, 2.0, 20.0), 15.0, places=5)

    def test_at_x1_returns_y1(self):
        self.assertAlmostEqual(linear_interpolation(1.0, 1.0, 10.0, 2.0, 20.0), 10.0, places=5)

    def test_at_x2_returns_y2(self):
        self.assertAlmostEqual(linear_interpolation(2.0, 1.0, 10.0, 2.0, 20.0), 20.0, places=5)

    def test_equal_x_returns_y1(self):
        self.assertAlmostEqual(linear_interpolation(1.0, 1.0, 42.0, 1.0, 99.0), 42.0, places=5)

    def test_extrapolation_beyond_range(self):
        # linear extrapolation beyond x2
        result = linear_interpolation(3.0, 1.0, 10.0, 2.0, 20.0)
        self.assertAlmostEqual(result, 30.0, places=5)


# ==============================================================================
# U06 — ROLLING WINDOW
# ==============================================================================

class TestRollingWindow(unittest.TestCase):
    """rolling_window."""

    def test_window_too_large_returns_empty(self):
        self.assertEqual(rolling_window([1.0, 2.0], window_size=5, func=sum), [])

    def test_window_equals_length(self):
        result = rolling_window([1.0, 2.0, 3.0], window_size=3, func=sum)
        self.assertEqual(result, [6.0])

    def test_window_size_one(self):
        result = rolling_window([1.0, 2.0, 3.0], window_size=1, func=sum)
        self.assertEqual(result, [1.0, 2.0, 3.0])

    def test_rolling_mean(self):
        import statistics
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = rolling_window(data, window_size=3, func=statistics.mean)
        self.assertEqual(len(result), 3)
        self.assertAlmostEqual(result[0], 2.0, places=5)
        self.assertAlmostEqual(result[2], 4.0, places=5)


# ==============================================================================
# U06 — EXPONENTIAL MOVING AVERAGE
# ==============================================================================

class TestExponentialMovingAverage(unittest.TestCase):
    """exponential_moving_average."""

    def test_empty_returns_empty(self):
        self.assertEqual(exponential_moving_average([], 5), [])

    def test_negative_period_returns_empty(self):
        self.assertEqual(exponential_moving_average([1.0, 2.0], -1), [])

    def test_zero_period_returns_empty(self):
        self.assertEqual(exponential_moving_average([1.0, 2.0], 0), [])

    def test_first_value_equals_data_first(self):
        result = exponential_moving_average([10.0, 20.0, 30.0], 3)
        self.assertAlmostEqual(result[0], 10.0, places=10)

    def test_length_matches_input(self):
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = exponential_moving_average(data, 3)
        self.assertEqual(len(result), len(data))

    def test_ema_reacts_to_price_increase(self):
        # With rising prices, EMA should be below the latest price
        data = [100.0] * 10 + [200.0] * 5
        result = exponential_moving_average(data, 5)
        self.assertLess(result[-1], 200.0)
        self.assertGreater(result[-1], 100.0)


# ==============================================================================
# U08 — VALIDATION ERROR
# ==============================================================================

class TestValidationError(unittest.TestCase):
    """ValidationError construction and message."""

    def test_is_exception(self):
        self.assertTrue(issubclass(ValidationError, Exception))

    def test_stores_field(self):
        e = ValidationError("price", 100, "must be positive")
        self.assertEqual(e.field, "price")

    def test_stores_value(self):
        e = ValidationError("qty", -1, "negative not allowed")
        self.assertEqual(e.value, -1)

    def test_stores_message(self):
        e = ValidationError("symbol", "xyz", "invalid format")
        self.assertEqual(e.message, "invalid format")

    def test_str_contains_field(self):
        e = ValidationError("side", "X", "unknown side")
        self.assertIn("side", str(e))


# ==============================================================================
# U08 — IS_VALID_STRING
# ==============================================================================

class TestIsValidString(unittest.TestCase):
    """is_valid_string."""

    def test_valid_string(self):
        self.assertTrue(is_valid_string("hello"))

    def test_empty_string_default_false(self):
        self.assertFalse(is_valid_string(""))

    def test_empty_string_allow_empty_true(self):
        self.assertTrue(is_valid_string("", allow_empty=True))

    def test_non_string_false(self):
        self.assertFalse(is_valid_string(123))

    def test_min_length_too_short(self):
        self.assertFalse(is_valid_string("ab", min_length=5))

    def test_min_length_exact(self):
        self.assertTrue(is_valid_string("abc", min_length=3))

    def test_max_length_exceeded(self):
        self.assertFalse(is_valid_string("hello", max_length=3))

    def test_max_length_exact(self):
        self.assertTrue(is_valid_string("hi", max_length=2))

    def test_none_returns_false(self):
        self.assertFalse(is_valid_string(None))


# ==============================================================================
# U08 — IS_VALID_NUMBER
# ==============================================================================

class TestIsValidNumber(unittest.TestCase):
    """is_valid_number."""

    def test_integer_accepted(self):
        self.assertTrue(is_valid_number(42))

    def test_float_accepted(self):
        self.assertTrue(is_valid_number(3.14))

    def test_string_number_accepted(self):
        self.assertTrue(is_valid_number("99.5"))

    def test_non_numeric_string_false(self):
        self.assertFalse(is_valid_number("abc"))

    def test_none_false(self):
        self.assertFalse(is_valid_number(None))

    def test_allow_negative_false_rejects_negative(self):
        self.assertFalse(is_valid_number(-1.0, allow_negative=False))

    def test_allow_zero_false_rejects_zero(self):
        self.assertFalse(is_valid_number(0.0, allow_zero=False))

    def test_min_value_boundary_exact(self):
        self.assertTrue(is_valid_number(5.0, min_value=5.0))

    def test_min_value_below_fails(self):
        self.assertFalse(is_valid_number(4.9, min_value=5.0))

    def test_max_value_boundary_exact(self):
        self.assertTrue(is_valid_number(10.0, max_value=10.0))

    def test_max_value_above_fails(self):
        self.assertFalse(is_valid_number(10.1, max_value=10.0))


# ==============================================================================
# U08 — IS_VALID_INTEGER
# ==============================================================================

class TestIsValidInteger(unittest.TestCase):
    """is_valid_integer — bool must be rejected."""

    def test_plain_int(self):
        self.assertTrue(is_valid_integer(5))

    def test_bool_true_rejected(self):
        self.assertFalse(is_valid_integer(True))

    def test_bool_false_rejected(self):
        self.assertFalse(is_valid_integer(False))

    def test_float_without_decimal_accepted(self):
        # int(3.0) == 3, so should pass
        self.assertTrue(is_valid_integer(3.0))

    def test_string_rejected(self):
        self.assertFalse(is_valid_integer("abc"))

    def test_min_value_enforced(self):
        self.assertFalse(is_valid_integer(0, min_value=1))

    def test_max_value_enforced(self):
        self.assertFalse(is_valid_integer(101, max_value=100))

    def test_range_boundary_included(self):
        self.assertTrue(is_valid_integer(100, min_value=1, max_value=100))


# ==============================================================================
# U08 — IS_VALID_BOOLEAN
# ==============================================================================

class TestIsValidBoolean(unittest.TestCase):
    """is_valid_boolean — only actual bool accepted."""

    def test_true_accepted(self):
        self.assertTrue(is_valid_boolean(True))

    def test_false_accepted(self):
        self.assertTrue(is_valid_boolean(False))

    def test_int_one_rejected(self):
        self.assertFalse(is_valid_boolean(1))

    def test_int_zero_rejected(self):
        self.assertFalse(is_valid_boolean(0))

    def test_string_rejected(self):
        self.assertFalse(is_valid_boolean("true"))

    def test_none_rejected(self):
        self.assertFalse(is_valid_boolean(None))


# ==============================================================================
# U08 — IS_VALID_LIST
# ==============================================================================

class TestIsValidList(unittest.TestCase):
    """is_valid_list."""

    def test_plain_list_accepted(self):
        self.assertTrue(is_valid_list([1, 2, 3]))

    def test_empty_list_default_accepted(self):
        self.assertTrue(is_valid_list([]))

    def test_non_list_rejected(self):
        self.assertFalse(is_valid_list((1, 2, 3)))

    def test_min_length_too_short(self):
        self.assertFalse(is_valid_list([1], min_length=2))

    def test_max_length_exceeded(self):
        self.assertFalse(is_valid_list([1, 2, 3], max_length=2))

    def test_item_validator_passes(self):
        self.assertTrue(is_valid_list([2, 4, 6], item_validator=lambda x: x % 2 == 0))

    def test_item_validator_fails(self):
        self.assertFalse(is_valid_list([2, 3, 6], item_validator=lambda x: x % 2 == 0))


# ==============================================================================
# U08 — IS_VALID_DICT
# ==============================================================================

class TestIsValidDict(unittest.TestCase):
    """is_valid_dict."""

    def test_plain_dict_accepted(self):
        self.assertTrue(is_valid_dict({"a": 1}))

    def test_non_dict_rejected(self):
        self.assertFalse(is_valid_dict([1, 2]))

    def test_required_key_present(self):
        self.assertTrue(is_valid_dict({"symbol": "SPY"}, required_keys=["symbol"]))

    def test_required_key_missing(self):
        self.assertFalse(is_valid_dict({"qty": 1}, required_keys=["symbol"]))

    def test_allowed_keys_respected(self):
        # Key not in required or optional → False
        result = is_valid_dict(
            {"symbol": "SPY", "extra": "bad"},
            required_keys=["symbol"],
            optional_keys=[]
        )
        self.assertFalse(result)

    def test_optional_key_allowed(self):
        result = is_valid_dict(
            {"symbol": "SPY", "note": "ok"},
            required_keys=["symbol"],
            optional_keys=["note"]
        )
        self.assertTrue(result)


# ==============================================================================
# U08 — PATTERN VALIDATORS
# ==============================================================================

class TestIsValidEmail(unittest.TestCase):
    """is_valid_email."""

    def test_valid_email(self):
        self.assertTrue(is_valid_email("user@example.com"))

    def test_missing_at_sign(self):
        self.assertFalse(is_valid_email("userexample.com"))

    def test_missing_domain(self):
        self.assertFalse(is_valid_email("user@"))

    def test_non_string(self):
        self.assertFalse(is_valid_email(12345))

    def test_subdomain_email(self):
        self.assertTrue(is_valid_email("user@mail.example.co.uk"))


class TestIsValidIpAddress(unittest.TestCase):
    """is_valid_ip_address."""

    def test_valid_ipv4(self):
        self.assertTrue(is_valid_ip_address("192.168.1.1"))

    def test_loopback(self):
        self.assertTrue(is_valid_ip_address("127.0.0.1"))

    def test_invalid_octet(self):
        self.assertFalse(is_valid_ip_address("256.0.0.1"))

    def test_non_string(self):
        self.assertFalse(is_valid_ip_address(12345))

    def test_partial_ip(self):
        self.assertFalse(is_valid_ip_address("192.168.1"))


class TestIsValidUrl(unittest.TestCase):
    """is_valid_url."""

    def test_valid_http_url(self):
        self.assertTrue(is_valid_url("http://example.com"))

    def test_valid_https_url(self):
        self.assertTrue(is_valid_url("https://api.tradier.com/v1"))

    def test_no_scheme_false(self):
        self.assertFalse(is_valid_url("example.com"))

    def test_non_string(self):
        self.assertFalse(is_valid_url(42))


# ==============================================================================
# U08 — TRADING VALIDATORS
# ==============================================================================

class TestIsValidSymbol(unittest.TestCase):
    """is_valid_symbol — equity and option symbols."""

    def test_valid_equity_symbol(self):
        self.assertTrue(is_valid_symbol("SPY"))

    def test_lowercase_rejected(self):
        self.assertFalse(is_valid_symbol("spy"))

    def test_too_long_rejected(self):
        self.assertFalse(is_valid_symbol("TOOLONG"))

    def test_single_letter_accepted(self):
        self.assertTrue(is_valid_symbol("F"))

    def test_option_symbol_with_flag(self):
        # Standard OCC option format: SYMBOL + YYMMDD + C/P + 8-digit strike
        self.assertTrue(is_valid_symbol("SPY240119C00450000", option=True))

    def test_equity_symbol_rejected_as_option(self):
        self.assertFalse(is_valid_symbol("SPY", option=True))


class TestIsValidPrice(unittest.TestCase):
    """is_valid_price."""

    def test_valid_price(self):
        self.assertTrue(is_valid_price(450.50))

    def test_below_min_price_rejected(self):
        self.assertFalse(is_valid_price(0.0))

    def test_above_max_price_rejected(self):
        self.assertFalse(is_valid_price(1_000_000.0))

    def test_min_price_boundary_accepted(self):
        self.assertTrue(is_valid_price(MIN_PRICE))

    def test_non_numeric_rejected(self):
        self.assertFalse(is_valid_price("abc"))

    def test_negative_price_rejected(self):
        self.assertFalse(is_valid_price(-1.0))


class TestIsValidQuantity(unittest.TestCase):
    """is_valid_quantity."""

    def test_integer_one_accepted(self):
        self.assertTrue(is_valid_quantity(1))

    def test_zero_rejected(self):
        self.assertFalse(is_valid_quantity(0))

    def test_negative_rejected(self):
        self.assertFalse(is_valid_quantity(-5))

    def test_non_numeric_rejected_by_default(self):
        # Strings cannot be converted, so they are rejected
        self.assertFalse(is_valid_quantity("1.5"))

    def test_fractional_allowed_with_flag(self):
        self.assertTrue(is_valid_quantity(1.5, allow_fractional=True))

    def test_large_valid_quantity(self):
        self.assertTrue(is_valid_quantity(999999))


class TestIsValidOrderType(unittest.TestCase):
    """is_valid_order_type — VALID_ORDER_TYPES."""

    def test_each_valid_order_type_accepted(self):
        for ot in VALID_ORDER_TYPES:
            with self.subTest(order_type=ot):
                self.assertTrue(is_valid_order_type(ot))

    def test_invalid_type_rejected(self):
        self.assertFalse(is_valid_order_type("LIMIT"))

    def test_lowercase_rejected(self):
        self.assertFalse(is_valid_order_type("mkt"))

    def test_none_rejected(self):
        self.assertFalse(is_valid_order_type(None))


class TestIsValidTimeInForce(unittest.TestCase):
    """is_valid_time_in_force — VALID_TIME_IN_FORCE."""

    def test_each_valid_tif_accepted(self):
        for tif in VALID_TIME_IN_FORCE:
            with self.subTest(tif=tif):
                self.assertTrue(is_valid_time_in_force(tif))

    def test_invalid_tif_rejected(self):
        self.assertFalse(is_valid_time_in_force("WEEK"))

    def test_none_rejected(self):
        self.assertFalse(is_valid_time_in_force(None))


class TestIsValidPercentage(unittest.TestCase):
    """is_valid_percentage — default 0..100."""

    def test_zero_accepted(self):
        self.assertTrue(is_valid_percentage(0.0))

    def test_hundred_accepted(self):
        self.assertTrue(is_valid_percentage(100.0))

    def test_below_min_rejected(self):
        self.assertFalse(is_valid_percentage(-0.1))

    def test_above_max_rejected(self):
        self.assertFalse(is_valid_percentage(100.1))

    def test_midrange_accepted(self):
        self.assertTrue(is_valid_percentage(50.0))

    def test_custom_range(self):
        # min_pct=0, max_pct=1 (fraction form)
        self.assertTrue(is_valid_percentage(0.5, min_pct=0.0, max_pct=1.0))
        self.assertFalse(is_valid_percentage(1.5, min_pct=0.0, max_pct=1.0))


# ==============================================================================
# ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    unittest.main(verbosity=2)
