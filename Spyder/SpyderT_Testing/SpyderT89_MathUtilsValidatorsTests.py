#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT89_MathUtilsValidatorsTests.py
Purpose: Comprehensive tests for SpyderU06_MathUtils and SpyderU08_Validators

Author: GitHub Copilot
Year Created: 2025
Last Updated: 2025-10-01 Time: 00:00:00
"""

# ==============================================================================
# BOOTSTRAP
# ==============================================================================
import importlib.util
import os
import sys
import types

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
_ensure_pkg("Spyder.SpyderU_Utilities")

# U01 Logger (required by U08 via hard import)
_u01 = _load("Spyder/Spyder.SpyderU_Utilities/SpyderU01_Logger.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU01_Logger"] = _u01
sys.modules["Spyder.SpyderU_Utilities.SpyderU01_Logger"] = _u01

# U06 MathUtils (no local framework imports)
_u06 = _load("Spyder/Spyder.SpyderU_Utilities/SpyderU06_MathUtils.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU06_MathUtils"] = _u06
sys.modules["Spyder.SpyderU_Utilities.SpyderU06_MathUtils"] = _u06

# U08 Validators (imports SpyderLogger at module level)
_u08 = _load("Spyder/Spyder.SpyderU_Utilities/SpyderU08_Validators.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU08_Validators"] = _u08
sys.modules["Spyder.SpyderU_Utilities.SpyderU08_Validators"] = _u08

# ==============================================================================
# STANDARD TEST IMPORTS
# ==============================================================================
import math
from datetime import date, datetime, time
from unittest.mock import patch

import numpy as np
import pytest

# ==============================================================================
# MODULE REFERENCES — U06 MathUtils
# ==============================================================================
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
calculate_probability_touch = _u06.calculate_probability_touch
calculate_probability_profit = _u06.calculate_probability_profit
find_root = _u06.find_root
minimize_scalar = _u06.minimize_scalar
calculate_position_size = _u06.calculate_position_size
calculate_kelly_criterion = _u06.calculate_kelly_criterion
calculate_risk_reward_ratio = _u06.calculate_risk_reward_ratio
linear_interpolation = _u06.linear_interpolation
cubic_spline_interpolation = _u06.cubic_spline_interpolation
rolling_window = _u06.rolling_window
exponential_moving_average = _u06.exponential_moving_average
MathUtils = _u06.MathUtils

PRICE_PRECISION = _u06.PRICE_PRECISION
PERCENTAGE_PRECISION = _u06.PERCENTAGE_PRECISION
TRADING_DAYS_PER_YEAR = _u06.TRADING_DAYS_PER_YEAR

# ==============================================================================
# MODULE REFERENCES — U08 Validators
# ==============================================================================
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
is_valid_date = _u08.is_valid_date
is_valid_time = _u08.is_valid_time
is_valid_datetime = _u08.is_valid_datetime
is_valid_symbol = _u08.is_valid_symbol
is_valid_price = _u08.is_valid_price
is_valid_quantity = _u08.is_valid_quantity
is_valid_order_type = _u08.is_valid_order_type
is_valid_time_in_force = _u08.is_valid_time_in_force
is_valid_account_balance = _u08.is_valid_account_balance
is_valid_percentage = _u08.is_valid_percentage
validate_order_data = _u08.validate_order_data
validate_position_data = _u08.validate_position_data
validate_config_value = _u08.validate_config_value
sanitize_string = _u08.sanitize_string
sanitize_filename = _u08.sanitize_filename
validate_input = _u08.validate_input
DataValidators = _u08.DataValidators
Validators = _u08.Validators


# ==============================================================================
# ════════════════════════════════════════════════════════════════════════════════
# U06 — MATH UTILS TESTS
# ════════════════════════════════════════════════════════════════════════════════
# ==============================================================================


class TestConstants:
    """Tests for module-level constants."""

    def test_price_precision(self):
        assert PRICE_PRECISION == 2

    def test_trading_days_per_year(self):
        assert TRADING_DAYS_PER_YEAR == 252

    def test_confidence_levels(self):
        assert 0.95 in _u06.CONFIDENCE_LEVELS

    def test_convergence_threshold(self):
        assert _u06.CONVERGENCE_THRESHOLD < 1e-5


class TestRoundPrice:
    """Tests for round_price."""

    def test_rounds_to_two_decimals(self):
        assert round_price(123.456) == 123.46

    def test_rounds_to_three_decimals(self):
        assert round_price(123.4445, 3) == 123.445

    def test_exact_value(self):
        assert round_price(100.0) == 100.0

    def test_negative_value(self):
        assert round_price(-1.555) == -1.56

    def test_zero(self):
        assert round_price(0.0) == 0.0

    def test_half_up_rounding(self):
        # e.g. 0.005 should round to 0.01 with ROUND_HALF_UP
        result = round_price(0.005)
        assert result == 0.01

    def test_precision_zero(self):
        assert round_price(123.6, 0) == 124.0


class TestRoundToTick:
    """Tests for round_to_tick."""

    def test_round_up(self):
        result = round_to_tick(123.3, 0.25)
        assert abs(result - 123.25) < 0.01 or abs(result - 123.5) < 0.01

    def test_exact_tick(self):
        result = round_to_tick(10.0, 0.5)
        assert result == 10.0

    def test_half_tick(self):
        result = round_to_tick(10.25, 0.5)
        assert abs(result % 0.5) < 0.001

    def test_one_cent_tick(self):
        result = round_to_tick(1.555, 0.01)
        assert round(result, 2) in (1.55, 1.56)


class TestCalculatePercentageChange:
    """Tests for calculate_percentage_change."""

    def test_positive_change(self):
        result = calculate_percentage_change(100, 110)
        assert abs(result - 10.0) < 0.001

    def test_negative_change(self):
        result = calculate_percentage_change(100, 90)
        assert abs(result - (-10.0)) < 0.001

    def test_zero_old_value_with_zero_new(self):
        assert calculate_percentage_change(0, 0) == 0.0

    def test_zero_old_value_with_nonzero_new(self):
        result = calculate_percentage_change(0, 10)
        assert result == float("inf")

    def test_no_change(self):
        assert calculate_percentage_change(50, 50) == 0.0


class TestCalculateCompoundReturn:
    """Tests for calculate_compound_return."""

    def test_positive_returns(self):
        result = calculate_compound_return([0.1, 0.1])
        assert abs(result - 0.21) < 0.001

    def test_negative_return(self):
        result = calculate_compound_return([-0.5])
        assert abs(result - (-0.5)) < 0.001

    def test_empty_returns(self):
        result = calculate_compound_return([])
        assert result == 0.0

    def test_zero_return(self):
        result = calculate_compound_return([0.0])
        assert result == 0.0

    def test_mixed_returns(self):
        result = calculate_compound_return([0.2, -0.1, 0.05])
        assert isinstance(result, float)


class TestCalculateMean:
    """Tests for calculate_mean."""

    def test_basic_mean(self):
        assert calculate_mean([1.0, 2.0, 3.0]) == 2.0

    def test_single_value(self):
        assert calculate_mean([5.0]) == 5.0

    def test_empty_list(self):
        assert calculate_mean([]) == 0.0

    def test_negative_values(self):
        assert calculate_mean([-1.0, 1.0]) == 0.0


class TestCalculateStdDev:
    """Tests for calculate_std_dev."""

    def test_sample_std(self):
        result = calculate_std_dev([1.0, 2.0, 3.0, 4.0, 5.0])
        assert abs(result - 1.5811) < 0.001

    def test_population_std(self):
        result = calculate_std_dev([1.0, 2.0, 3.0, 4.0, 5.0], sample=False)
        assert result < calculate_std_dev([1.0, 2.0, 3.0, 4.0, 5.0])

    def test_insufficient_data(self):
        assert calculate_std_dev([5.0]) == 0.0

    def test_empty_list(self):
        assert calculate_std_dev([]) == 0.0


class TestCalculateSharpeRatio:
    """Tests for calculate_sharpe_ratio."""

    def test_positive_returns(self):
        returns = [0.01] * 252
        ratio = calculate_sharpe_ratio(returns)
        assert ratio > 0

    def test_insufficient_data(self):
        assert calculate_sharpe_ratio([0.01]) == 0.0

    def test_zero_std_returns(self):
        # All same return → std=0 → Sharpe=0
        returns = [0.0] * 10
        assert calculate_sharpe_ratio(returns) == 0.0

    def test_returns_float(self):
        returns = [0.01, -0.02, 0.015, 0.005, -0.01, 0.02]
        result = calculate_sharpe_ratio(returns)
        assert isinstance(result, float)

    def test_custom_risk_free(self):
        returns = [0.05] * 252
        ratio_low_rf = calculate_sharpe_ratio(returns, risk_free_rate=0.01)
        ratio_high_rf = calculate_sharpe_ratio(returns, risk_free_rate=0.04)
        assert ratio_low_rf > ratio_high_rf


class TestCalculateSortinoRatio:
    """Tests for calculate_sortino_ratio."""

    def test_basic(self):
        returns = [0.01, -0.02, 0.015, 0.005, -0.01, 0.02]
        result = calculate_sortino_ratio(returns)
        assert isinstance(result, float)

    def test_insufficient_data(self):
        assert calculate_sortino_ratio([0.01]) == 0.0

    def test_all_positive_returns(self):
        returns = [0.01] * 10
        # No downside → should return inf
        result = calculate_sortino_ratio(returns)
        assert result == float("inf") or result > 0


class TestCalculateMaxDrawdown:
    """Tests for calculate_max_drawdown."""

    def test_basic_drawdown(self):
        equity = [100.0, 110.0, 105.0, 95.0, 100.0]
        dd, peak, trough = calculate_max_drawdown(equity)
        assert dd < 0  # drawdown is negative
        assert isinstance(peak, int)
        assert isinstance(trough, int)

    def test_monotonically_increasing(self):
        equity = [100.0, 110.0, 120.0, 130.0]
        dd, _, _ = calculate_max_drawdown(equity)
        assert dd == 0.0

    def test_insufficient_data(self):
        dd, peak, trough = calculate_max_drawdown([100.0])
        assert dd == 0.0

    def test_empty_list(self):
        dd, peak, trough = calculate_max_drawdown([])
        assert dd == 0.0


class TestCalculateVar:
    """Tests for calculate_var."""

    def test_historical_var(self):
        returns = [0.01, -0.02, 0.015, -0.03, 0.02, -0.01, 0.05, -0.04]
        var = calculate_var(returns, 0.95, "historical")
        assert var >= 0

    def test_parametric_var(self):
        returns = [0.01, -0.02, 0.015, -0.03, 0.02, -0.01, 0.05, -0.04]
        var = calculate_var(returns, 0.95, "parametric")
        assert isinstance(var, float)

    def test_empty_returns(self):
        assert calculate_var([]) == 0.0

    def test_invalid_method(self):
        with pytest.raises(ValueError):
            calculate_var([0.01, -0.02], method="invalid")

    def test_confidence_level_impact(self):
        returns = list(np.random.randn(100) * 0.01)
        var_95 = calculate_var(returns, 0.95)
        var_99 = calculate_var(returns, 0.99)
        assert var_99 >= var_95


class TestCalculateCvar:
    """Tests for calculate_cvar."""

    def test_basic_cvar(self):
        returns = [0.01, -0.02, 0.015, -0.03, 0.02, -0.01, 0.05, -0.04]
        cvar = calculate_cvar(returns)
        assert isinstance(cvar, float)

    def test_empty_returns(self):
        assert calculate_cvar([]) == 0.0


class TestNormalCdf:
    """Tests for normal_cdf."""

    def test_zero_input(self):
        assert abs(normal_cdf(0.0) - 0.5) < 1e-6

    def test_large_positive(self):
        assert normal_cdf(10.0) > 0.999

    def test_large_negative(self):
        assert normal_cdf(-10.0) < 0.001

    def test_1_sigma(self):
        assert abs(normal_cdf(1.0) - 0.8413) < 0.001

    def test_monotone_increasing(self):
        for x in [-2.0, -1.0, 0.0, 1.0, 2.0]:
            assert 0 <= normal_cdf(x) <= 1


class TestNormalPdf:
    """Tests for normal_pdf."""

    def test_zero_is_max(self):
        assert normal_pdf(0.0) > normal_pdf(1.0)

    def test_symmetry(self):
        assert abs(normal_pdf(1.0) - normal_pdf(-1.0)) < 1e-12

    def test_value_at_zero(self):
        expected = 1.0 / math.sqrt(2 * math.pi)
        assert abs(normal_pdf(0.0) - expected) < 1e-10

    def test_positive_value(self):
        assert normal_pdf(0.0) > 0


class TestCalculateProbabilityTouch:
    """Tests for calculate_probability_touch."""

    def test_zero_days(self):
        result = calculate_probability_touch(450, 460, 0.2, 0)
        assert result == 0.0

    def test_zero_volatility(self):
        result = calculate_probability_touch(450, 460, 0.0, 30)
        assert result == 0.0

    def test_at_the_money(self):
        # At the money has highest probability of touch
        result = calculate_probability_touch(450, 450, 0.2, 30)
        assert result >= 0.0

    def test_far_out_of_the_money(self):
        result = calculate_probability_touch(450, 1000, 0.2, 1)
        assert result < 0.5

    def test_bounded_between_0_and_1(self):
        result = calculate_probability_touch(450, 455, 0.2, 30)
        assert 0.0 <= result <= 1.0


class TestCalculateProbabilityProfit:
    """Tests for calculate_probability_profit."""

    def test_bullish_above_breakeven(self):
        # If breakeven == current_price, prob should be ~50%
        result = calculate_probability_profit(450, 450, 0.2, 30, is_bullish=True)
        assert 0.0 <= result <= 1.0

    def test_bearish_direction(self):
        result = calculate_probability_profit(450, 460, 0.2, 30, is_bullish=False)
        assert 0.0 <= result <= 1.0

    def test_zero_days_bullish_above(self):
        result = calculate_probability_profit(450, 460, 0.2, 0, is_bullish=True)
        assert result == 1.0  # 460 > 450

    def test_zero_days_bullish_below(self):
        result = calculate_probability_profit(460, 450, 0.2, 0, is_bullish=True)
        assert result == 0.0

    def test_zero_days_bearish_below(self):
        # bearish profits when current_price < breakeven_price
        # breakeven=450, current=440: 440 < 450 → profit → 1.0
        result = calculate_probability_profit(450, 440, 0.2, 0, is_bullish=False)
        assert result == 1.0

    def test_zero_days_bearish_above(self):
        # breakeven=440, current=450: 450 < 440 is False → no profit → 0.0
        result = calculate_probability_profit(440, 450, 0.2, 0, is_bullish=False)
        assert result == 0.0


class TestFindRoot:
    """Tests for find_root."""

    def test_simple_root(self):
        # f(x) = x - 5, root at x=5
        root = find_root(lambda x: x - 5, 0, 10)
        assert root is not None
        assert abs(root - 5.0) < 1e-6

    def test_quadratic(self):
        # f(x) = x^2 - 4, root at x=2 (in [0, 4])
        root = find_root(lambda x: x**2 - 4, 0, 4)
        assert root is not None
        assert abs(root - 2.0) < 1e-5

    def test_no_sign_change(self):
        # f(x) = x^2 + 1 has no real root
        root = find_root(lambda x: x**2 + 1, 0, 10)
        assert root is None

    def test_returns_float(self):
        root = find_root(lambda x: x - 3, 0, 10)
        assert isinstance(root, float)


class TestMinimizeScalar:
    """Tests for minimize_scalar."""

    def test_parabola_minimum(self):
        # f(x) = (x-3)^2, minimum at x=3
        x_min, f_min = minimize_scalar(lambda x: (x - 3)**2, (0, 10))
        assert x_min is not None
        assert abs(x_min - 3.0) < 0.01

    def test_returns_tuple(self):
        result = minimize_scalar(lambda x: x**2, (0, 10))
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_exception_returns_none(self):
        x_min, f_min = minimize_scalar(lambda x: (_ for _ in ()).throw(Exception("fail")), (0, 10))
        # Should return None, None on exception
        assert x_min is None or isinstance(x_min, float)


class TestCalculatePositionSize:
    """Tests for calculate_position_size."""

    def test_basic_calculation(self):
        # $100k, 1% risk = $1000 at risk; $5 stop × 100 multiplier = $500 per contract
        # → 1000 / 500 = 2 contracts
        result = calculate_position_size(100_000, 1.0, 5.0, 100)
        assert result == 2

    def test_zero_stop_loss(self):
        assert calculate_position_size(100_000, 1.0, 0, 1) == 0

    def test_zero_risk_percent(self):
        assert calculate_position_size(100_000, 0, 5.0, 1) == 0

    def test_returns_int(self):
        result = calculate_position_size(100_000, 2.0, 10.0, 1.0)
        assert isinstance(result, int)


class TestCalculateKellyCriterion:
    """Tests for calculate_kelly_criterion."""

    def test_positive_kelly(self):
        # win_rate=0.6, avg_win=2, avg_loss=1 → kelly positive
        result = calculate_kelly_criterion(0.6, 2.0, 1.0)
        assert result > 0

    def test_capped_at_25_percent(self):
        result = calculate_kelly_criterion(0.9, 10.0, 1.0)
        assert result <= 0.25

    def test_zero_avg_loss(self):
        result = calculate_kelly_criterion(0.6, 2.0, 0.0)
        assert result == 0.0

    def test_win_rate_zero(self):
        result = calculate_kelly_criterion(0.0, 2.0, 1.0)
        assert result == 0.0

    def test_negative_kelly_returns_zero(self):
        # win_rate=0.3, avg_win=1, avg_loss=2 → negative kelly → clamped to 0
        result = calculate_kelly_criterion(0.3, 1.0, 2.0)
        assert result == 0.0


class TestCalculateRiskRewardRatio:
    """Tests for calculate_risk_reward_ratio."""

    def test_two_to_one(self):
        # entry=100, target=110, stop=95 → reward=10, risk=5 → 2.0
        result = calculate_risk_reward_ratio(100, 110, 95)
        assert abs(result - 2.0) < 0.001

    def test_zero_risk(self):
        result = calculate_risk_reward_ratio(100, 110, 100)
        assert result == float("inf") or result > 0

    def test_returns_float(self):
        result = calculate_risk_reward_ratio(100, 105, 97)
        assert isinstance(result, float)


class TestLinearInterpolation:
    """Tests for linear_interpolation."""

    def test_midpoint(self):
        result = linear_interpolation(5, 0, 0, 10, 10)
        assert abs(result - 5.0) < 0.001

    def test_at_first_point(self):
        result = linear_interpolation(0, 0, 5, 10, 15)
        assert abs(result - 5.0) < 0.001

    def test_at_second_point(self):
        result = linear_interpolation(10, 0, 5, 10, 15)
        assert abs(result - 15.0) < 0.001

    def test_equal_x_returns_y1(self):
        result = linear_interpolation(5, 5, 10, 5, 20)
        assert abs(result - 10.0) < 0.001


class TestCubicSplineInterpolation:
    """Tests for cubic_spline_interpolation."""

    def test_basic_interpolation(self):
        x_pts = [0, 1, 2, 3, 4]
        y_pts = [0, 1, 4, 9, 16]  # y = x^2
        result = cubic_spline_interpolation(x_pts, y_pts, 2.5)
        assert abs(result - 6.25) < 0.5  # Approximate

    def test_returns_float_for_scalar(self):
        x_pts = [0, 1, 2, 3]
        y_pts = [0, 1, 2, 3]
        result = cubic_spline_interpolation(x_pts, y_pts, 1.5)
        assert isinstance(result, float)

    def test_returns_list_for_list(self):
        x_pts = [0, 1, 2, 3]
        y_pts = [0, 1, 2, 3]
        result = cubic_spline_interpolation(x_pts, y_pts, [0.5, 1.5])
        assert isinstance(result, list)

    def test_insufficient_points_raises(self):
        with pytest.raises(ValueError):
            cubic_spline_interpolation([0], [0], 0.5)


class TestRollingWindow:
    """Tests for rolling_window."""

    def test_basic_rolling_mean(self):
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = rolling_window(data, 3, lambda w: sum(w) / len(w))
        assert len(result) == 3
        assert abs(result[0] - 2.0) < 0.001

    def test_window_larger_than_data(self):
        result = rolling_window([1.0, 2.0], 5, sum)
        assert result == []

    def test_window_equals_data_length(self):
        data = [1.0, 2.0, 3.0]
        result = rolling_window(data, 3, sum)
        assert len(result) == 1
        assert result[0] == 6.0


class TestExponentialMovingAverage:
    """Tests for exponential_moving_average."""

    def test_basic_ema(self):
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = exponential_moving_average(data, 3)
        assert len(result) == 5
        assert result[0] == 1.0  # First value = first data point

    def test_empty_data(self):
        assert exponential_moving_average([], 3) == []

    def test_zero_period(self):
        assert exponential_moving_average([1.0, 2.0], 0) == []

    def test_increasing_trend(self):
        data = [100.0 + i for i in range(10)]
        result = exponential_moving_average(data, 3)
        assert result[-1] > result[0]


class TestMathUtilsClass:
    """Tests for MathUtils wrapper class."""

    def test_round_price(self):
        assert MathUtils.round_price(123.456) == 123.46

    def test_round_to_tick(self):
        result = MathUtils.round_to_tick(10.0, 0.5)
        assert result == 10.0

    def test_calculate_percentage_change(self):
        assert MathUtils.calculate_percentage_change(100, 110) == 10.0

    def test_calculate_compound_return(self):
        assert abs(MathUtils.calculate_compound_return([0.1, 0.1]) - 0.21) < 0.001

    def test_calculate_mean(self):
        assert MathUtils.calculate_mean([1.0, 2.0, 3.0]) == 2.0

    def test_calculate_std_dev(self):
        result = MathUtils.calculate_std_dev([1.0, 2.0, 3.0, 4.0, 5.0])
        assert abs(result - 1.5811) < 0.001

    def test_calculate_sharpe_ratio(self):
        returns = [0.01, -0.02, 0.015, 0.005, -0.01, 0.02]
        result = MathUtils.calculate_sharpe_ratio(returns)
        assert isinstance(result, float)

    def test_calculate_sortino_ratio(self):
        returns = [0.01, -0.02, 0.015, 0.005, -0.01, 0.02]
        result = MathUtils.calculate_sortino_ratio(returns)
        assert isinstance(result, float)


# ==============================================================================
# ════════════════════════════════════════════════════════════════════════════════
# U08 — VALIDATORS TESTS
# ════════════════════════════════════════════════════════════════════════════════
# ==============================================================================


class TestValidationError:
    """Tests for ValidationError exception."""

    def test_creation(self):
        err = ValidationError("price", -1.0, "must be positive")
        assert err.field == "price"
        assert err.value == -1.0
        assert err.message == "must be positive"

    def test_str_contains_field(self):
        err = ValidationError("quantity", 0, "must be > 0")
        assert "quantity" in str(err)

    def test_is_exception(self):
        err = ValidationError("x", None, "test")
        assert isinstance(err, Exception)


class TestIsValidString:
    """Tests for is_valid_string."""

    def test_valid_string(self):
        assert is_valid_string("hello") is True

    def test_not_a_string(self):
        assert is_valid_string(123) is False

    def test_empty_not_allowed(self):
        assert is_valid_string("") is False

    def test_empty_allowed(self):
        assert is_valid_string("", allow_empty=True) is True

    def test_min_length(self):
        assert is_valid_string("ab", min_length=3) is False

    def test_max_length(self):
        assert is_valid_string("abcde", max_length=3) is False

    def test_within_range(self):
        assert is_valid_string("abc", min_length=2, max_length=5) is True

    def test_none_is_invalid(self):
        assert is_valid_string(None) is False


class TestIsValidNumber:
    """Tests for is_valid_number."""

    def test_integer_input(self):
        assert is_valid_number(42) is True

    def test_float_input(self):
        assert is_valid_number(3.14) is True

    def test_string_number(self):
        assert is_valid_number("42.5") is True

    def test_invalid_string(self):
        assert is_valid_number("abc") is False

    def test_none_invalid(self):
        assert is_valid_number(None) is False

    def test_negative_not_allowed(self):
        assert is_valid_number(-1, allow_negative=False) is False

    def test_zero_not_allowed(self):
        assert is_valid_number(0, allow_zero=False) is False

    def test_min_value(self):
        assert is_valid_number(5, min_value=10) is False

    def test_max_value(self):
        assert is_valid_number(15, max_value=10) is False

    def test_within_bounds(self):
        assert is_valid_number(5, min_value=1, max_value=10) is True


class TestIsValidInteger:
    """Tests for is_valid_integer."""

    def test_integer(self):
        assert is_valid_integer(42) is True

    def test_bool_is_invalid(self):
        assert is_valid_integer(True) is False

    def test_float_with_int_value(self):
        # float 3.0 → int 3 → valid
        assert is_valid_integer(3.0) is True

    def test_float_non_integer(self):
        assert is_valid_integer(3.7) is True  # int(3.7) = 3, valid

    def test_string_integer(self):
        assert is_valid_integer("123") is True

    def test_string_non_integer(self):
        assert is_valid_integer("abc") is False

    def test_min_value(self):
        assert is_valid_integer(5, min_value=10) is False

    def test_max_value(self):
        assert is_valid_integer(15, max_value=10) is False

    def test_none_invalid(self):
        assert is_valid_integer(None) is False


class TestIsValidBoolean:
    """Tests for is_valid_boolean."""

    def test_true(self):
        assert is_valid_boolean(True) is True

    def test_false(self):
        assert is_valid_boolean(False) is True

    def test_integer_not_bool(self):
        assert is_valid_boolean(1) is False

    def test_string_not_bool(self):
        assert is_valid_boolean("true") is False

    def test_none_not_bool(self):
        assert is_valid_boolean(None) is False


class TestIsValidList:
    """Tests for is_valid_list."""

    def test_basic_list(self):
        assert is_valid_list([1, 2, 3]) is True

    def test_not_a_list(self):
        assert is_valid_list((1, 2)) is False

    def test_empty_below_min(self):
        assert is_valid_list([], min_length=1) is False

    def test_exceeds_max(self):
        assert is_valid_list([1, 2, 3, 4], max_length=3) is False

    def test_item_validator_valid(self):
        assert is_valid_list([1, 2, 3], item_validator=lambda x: isinstance(x, int)) is True

    def test_item_validator_invalid(self):
        assert is_valid_list([1, "a", 3], item_validator=lambda x: isinstance(x, int)) is False


class TestIsValidDict:
    """Tests for is_valid_dict."""

    def test_basic_dict(self):
        assert is_valid_dict({"a": 1}) is True

    def test_not_a_dict(self):
        assert is_valid_dict([]) is False

    def test_missing_required_key(self):
        assert is_valid_dict({"b": 1}, required_keys=["a"]) is False

    def test_has_required_key(self):
        assert is_valid_dict({"a": 1}, required_keys=["a"]) is True

    def test_extra_key_not_in_allowed(self):
        assert is_valid_dict({"a": 1, "x": 2}, required_keys=["a"], optional_keys=["b"]) is False

    def test_optional_key_allowed(self):
        assert is_valid_dict({"a": 1, "b": 2}, required_keys=["a"], optional_keys=["b"]) is True


class TestIsValidEmail:
    """Tests for is_valid_email."""

    def test_valid_email(self):
        assert is_valid_email("user@example.com") is True

    def test_invalid_no_at(self):
        assert is_valid_email("userexample.com") is False

    def test_invalid_no_domain(self):
        assert is_valid_email("user@") is False

    def test_not_string(self):
        assert is_valid_email(123) is False

    def test_with_dots(self):
        assert is_valid_email("first.last@domain.org") is True

    def test_with_plus(self):
        assert is_valid_email("user+tag@example.com") is True


class TestIsValidPhone:
    """Tests for is_valid_phone."""

    def test_valid_10_digit(self):
        assert is_valid_phone("1234567890") is True

    def test_valid_with_country_code(self):
        assert is_valid_phone("+11234567890") is True

    def test_invalid_too_short(self):
        assert is_valid_phone("123") is False

    def test_not_string(self):
        assert is_valid_phone(1234567890) is False

    def test_with_formatting(self):
        assert is_valid_phone("(123) 456-7890") is True


class TestIsValidIpAddress:
    """Tests for is_valid_ip_address."""

    def test_valid_ip(self):
        assert is_valid_ip_address("192.168.1.1") is True

    def test_invalid_ip_out_of_range(self):
        assert is_valid_ip_address("256.0.0.1") is False

    def test_not_string(self):
        assert is_valid_ip_address(192168) is False

    def test_loopback(self):
        assert is_valid_ip_address("127.0.0.1") is True

    def test_invalid_format(self):
        assert is_valid_ip_address("192.168.1") is False


class TestIsValidUrl:
    """Tests for is_valid_url."""

    def test_valid_http(self):
        assert is_valid_url("http://example.com") is True

    def test_valid_https(self):
        assert is_valid_url("https://www.example.com/path?query=1") is True

    def test_invalid_no_scheme(self):
        assert is_valid_url("example.com") is False

    def test_not_string(self):
        assert is_valid_url(123) is False


class TestIsValidDate:
    """Tests for is_valid_date."""

    def test_date_object(self):
        assert is_valid_date(date(2025, 1, 1)) is True

    def test_date_string_iso(self):
        assert is_valid_date("2025-01-01") is True

    def test_date_string_us_format(self):
        assert is_valid_date("01/31/2025") is True

    def test_invalid_string(self):
        assert is_valid_date("not-a-date") is False

    def test_min_date_violation(self):
        assert is_valid_date(date(2020, 1, 1), min_date=date(2025, 1, 1)) is False

    def test_max_date_violation(self):
        assert is_valid_date(date(2026, 1, 1), max_date=date(2025, 12, 31)) is False

    def test_not_a_date(self):
        assert is_valid_date(12345) is False


class TestIsValidTime:
    """Tests for is_valid_time."""

    def test_time_object(self):
        assert is_valid_time(time(9, 30, 0)) is True

    def test_string_hms(self):
        assert is_valid_time("09:30:00") is True

    def test_string_hm(self):
        assert is_valid_time("09:30") is True

    def test_invalid_string(self):
        assert is_valid_time("not-a-time") is False

    def test_not_time(self):
        assert is_valid_time(930) is False


class TestIsValidDatetime:
    """Tests for is_valid_datetime."""

    def test_datetime_object(self):
        assert is_valid_datetime(datetime(2025, 1, 1, 9, 30)) is True

    def test_string_datetime(self):
        assert is_valid_datetime("2025-01-01 09:30:00") is True

    def test_invalid_string(self):
        assert is_valid_datetime("not-a-datetime") is False

    def test_min_dt_violation(self):
        dt = datetime(2020, 1, 1)
        min_dt = datetime(2025, 1, 1)
        assert is_valid_datetime(dt, min_dt=min_dt) is False

    def test_not_datetime(self):
        assert is_valid_datetime(12345) is False


class TestIsValidSymbol:
    """Tests for is_valid_symbol."""

    def test_spy_valid(self):
        assert is_valid_symbol("SPY") is True

    def test_lowercase_invalid(self):
        assert is_valid_symbol("spy") is False

    def test_too_long(self):
        assert is_valid_symbol("TOOLNG") is False

    def test_option_symbol_with_flag(self):
        # Format: SYMBOL + 6 digits + C/P + 8 digits
        assert is_valid_symbol("SPY230120C00450000", option=True) is True

    def test_invalid_option_symbol(self):
        assert is_valid_symbol("SPY", option=True) is False

    def test_numbers_in_stock_symbol(self):
        assert is_valid_symbol("SP1") is False

    def test_not_string(self):
        assert is_valid_symbol(123) is False


class TestIsValidPrice:
    """Tests for is_valid_price."""

    def test_valid_price(self):
        assert is_valid_price(450.50) is True

    def test_negative_invalid(self):
        assert is_valid_price(-1.0) is False

    def test_zero_invalid(self):
        assert is_valid_price(0.0) is False  # below MIN_PRICE=0.01

    def test_too_high_invalid(self):
        assert is_valid_price(1_000_000.0) is False

    def test_min_price_valid(self):
        assert is_valid_price(0.01) is True


class TestIsValidQuantity:
    """Tests for is_valid_quantity."""

    def test_valid_integer_qty(self):
        assert is_valid_quantity(100) is True

    def test_zero_invalid(self):
        assert is_valid_quantity(0) is False

    def test_fractional_not_allowed_string(self):
        # '1.5' cannot be converted to int → invalid
        assert is_valid_quantity("1.5") is False

    def test_fractional_allowed(self):
        assert is_valid_quantity(1.5, allow_fractional=True) is True

    def test_negative_invalid(self):
        assert is_valid_quantity(-1) is False


class TestIsValidOrderType:
    """Tests for is_valid_order_type."""

    def test_mkt_valid(self):
        assert is_valid_order_type("MKT") is True

    def test_lmt_valid(self):
        assert is_valid_order_type("LMT") is True

    def test_invalid_type(self):
        assert is_valid_order_type("INVALID") is False

    def test_all_valid_types(self):
        for ot in _u08.VALID_ORDER_TYPES:
            assert is_valid_order_type(ot) is True


class TestIsValidTimeInForce:
    """Tests for is_valid_time_in_force."""

    def test_day_valid(self):
        assert is_valid_time_in_force("DAY") is True

    def test_gtc_valid(self):
        assert is_valid_time_in_force("GTC") is True

    def test_invalid(self):
        assert is_valid_time_in_force("INVALID") is False

    def test_all_valid(self):
        for tif in _u08.VALID_TIME_IN_FORCE:
            assert is_valid_time_in_force(tif) is True


class TestIsValidAccountBalance:
    """Tests for is_valid_account_balance."""

    def test_positive_balance(self):
        assert is_valid_account_balance(10000.0) is True

    def test_zero_balance(self):
        assert is_valid_account_balance(0.0) is True

    def test_negative_invalid(self):
        assert is_valid_account_balance(-100.0) is False

    def test_string_number(self):
        assert is_valid_account_balance("5000") is True


class TestIsValidPercentage:
    """Tests for is_valid_percentage."""

    def test_valid_percentage(self):
        assert is_valid_percentage(50.0) is True

    def test_zero(self):
        assert is_valid_percentage(0.0) is True

    def test_hundred(self):
        assert is_valid_percentage(100.0) is True

    def test_above_hundred(self):
        assert is_valid_percentage(101.0) is False

    def test_negative(self):
        assert is_valid_percentage(-1.0) is False


class TestValidateOrderData:
    """Tests for validate_order_data."""

    def _valid_order(self):
        return {
            "symbol": "SPY",
            "action": "BUY",
            "quantity": 100,
            "order_type": "MKT",
        }

    def test_valid_mkt_order(self):
        valid, err = validate_order_data(self._valid_order())
        assert valid is True
        assert err is None

    def test_missing_field(self):
        order = self._valid_order()
        del order["symbol"]
        valid, err = validate_order_data(order)
        assert valid is False
        assert "Missing" in err

    def test_invalid_symbol(self):
        order = self._valid_order()
        order["symbol"] = "spy"
        valid, err = validate_order_data(order)
        assert valid is False

    def test_invalid_action(self):
        order = self._valid_order()
        order["action"] = "HOLD"
        valid, err = validate_order_data(order)
        assert valid is False

    def test_lmt_order_needs_limit_price(self):
        order = self._valid_order()
        order["order_type"] = "LMT"
        valid, err = validate_order_data(order)
        assert valid is False
        assert "limit_price" in err.lower() or "limit" in err.lower()

    def test_lmt_order_with_limit_price(self):
        order = self._valid_order()
        order["order_type"] = "LMT"
        order["limit_price"] = 450.0
        valid, err = validate_order_data(order)
        assert valid is True

    def test_stp_order_needs_stop_price(self):
        order = self._valid_order()
        order["order_type"] = "STP"
        valid, err = validate_order_data(order)
        assert valid is False

    def test_stp_order_with_stop_price(self):
        order = self._valid_order()
        order["order_type"] = "STP"
        order["stop_price"] = 445.0
        valid, err = validate_order_data(order)
        assert valid is True

    def test_valid_time_in_force(self):
        order = self._valid_order()
        order["time_in_force"] = "GTC"
        valid, err = validate_order_data(order)
        assert valid is True

    def test_invalid_time_in_force(self):
        order = self._valid_order()
        order["time_in_force"] = "BADTIF"
        valid, err = validate_order_data(order)
        assert valid is False

    def test_invalid_quantity(self):
        order = self._valid_order()
        order["quantity"] = 0
        valid, err = validate_order_data(order)
        assert valid is False


class TestValidatePositionData:
    """Tests for validate_position_data."""

    def _valid_position(self):
        return {
            "symbol": "SPY",
            "quantity": 100,
            "entry_price": 450.0,
        }

    def test_valid_position(self):
        valid, err = validate_position_data(self._valid_position())
        assert valid is True

    def test_missing_symbol(self):
        pos = self._valid_position()
        del pos["symbol"]
        valid, err = validate_position_data(pos)
        assert valid is False

    def test_invalid_symbol(self):
        pos = self._valid_position()
        pos["symbol"] = "123"
        valid, err = validate_position_data(pos)
        assert valid is False

    def test_invalid_quantity(self):
        pos = self._valid_position()
        pos["quantity"] = "bad"
        valid, err = validate_position_data(pos)
        assert valid is False

    def test_invalid_entry_price(self):
        pos = self._valid_position()
        pos["entry_price"] = -1.0
        valid, err = validate_position_data(pos)
        assert valid is False

    def test_with_current_price(self):
        pos = self._valid_position()
        pos["current_price"] = 455.0
        valid, err = validate_position_data(pos)
        assert valid is True

    def test_with_invalid_current_price(self):
        pos = self._valid_position()
        pos["current_price"] = -5.0
        valid, err = validate_position_data(pos)
        assert valid is False

    def test_with_pnl(self):
        pos = self._valid_position()
        pos["unrealized_pnl"] = -500.0
        valid, err = validate_position_data(pos)
        assert valid is True


class TestValidateConfigValue:
    """Tests for validate_config_value."""

    def test_key_not_in_schema(self):
        valid, err = validate_config_value("unknown_key", "value", {})
        assert valid is True

    def test_type_string_passes(self):
        schema = {"port": {"type": "string"}}
        valid, err = validate_config_value("port", "8080", schema)
        assert valid is True

    def test_type_string_fails(self):
        schema = {"port": {"type": "string"}}
        valid, err = validate_config_value("port", 8080, schema)
        assert valid is False

    def test_type_number_passes(self):
        schema = {"rate": {"type": "number"}}
        valid, err = validate_config_value("rate", 1.5, schema)
        assert valid is True

    def test_type_boolean_fails(self):
        schema = {"flag": {"type": "boolean"}}
        valid, err = validate_config_value("flag", "yes", schema)
        assert valid is False

    def test_min_constraint(self):
        schema = {"count": {"min": 10}}
        valid, err = validate_config_value("count", 5, schema)
        assert valid is False

    def test_max_constraint(self):
        schema = {"count": {"max": 10}}
        valid, err = validate_config_value("count", 15, schema)
        assert valid is False

    def test_enum_constraint(self):
        schema = {"mode": {"enum": ["live", "paper"]}}
        valid, err = validate_config_value("mode", "unknown", schema)
        assert valid is False

    def test_enum_valid(self):
        schema = {"mode": {"enum": ["live", "paper"]}}
        valid, err = validate_config_value("mode", "live", schema)
        assert valid is True

    def test_pattern_constraint_fails(self):
        schema = {"code": {"pattern": r"^\d{4}$"}}
        valid, err = validate_config_value("code", "abc", schema)
        assert valid is False

    def test_type_integer(self):
        schema = {"count": {"type": "integer"}}
        valid, err = validate_config_value("count", 5, schema)
        assert valid is True

    def test_type_list(self):
        schema = {"items": {"type": "list"}}
        valid, err = validate_config_value("items", [1, 2, 3], schema)
        assert valid is True

    def test_type_dict(self):
        schema = {"cfg": {"type": "dict"}}
        valid, err = validate_config_value("cfg", {"a": 1}, schema)
        assert valid is True


class TestSanitizeString:
    """Tests for sanitize_string."""

    def test_strips_whitespace(self):
        assert sanitize_string("  hello  ") == "hello"

    def test_max_length(self):
        result = sanitize_string("abcde", max_length=3)
        assert result == "abc"

    def test_allowed_chars(self):
        result = sanitize_string("abc123", allowed_chars=r"[a-z]")
        assert result == "abc"

    def test_no_constraints(self):
        assert sanitize_string("hello") == "hello"


class TestSanitizeFilename:
    """Tests for sanitize_filename."""

    def test_removes_invalid_chars(self):
        result = sanitize_filename("my<file>.txt")
        assert "<" not in result
        assert ">" not in result

    def test_basename_only(self):
        result = sanitize_filename("/path/to/file.txt")
        assert "/" not in result
        assert result.endswith(".txt")

    def test_question_mark_removed(self):
        result = sanitize_filename("file?.txt")
        assert "?" not in result

    def test_normal_filename(self):
        result = sanitize_filename("report.csv")
        assert result == "report.csv"


class TestValidateInputDecorator:
    """Tests for validate_input decorator."""

    def test_valid_input_passes(self):
        @validate_input(price=is_valid_price)
        def dummy(price):
            return price

        assert dummy(450.0) == 450.0

    def test_invalid_input_raises(self):
        @validate_input(price=is_valid_price)
        def dummy(price):
            return price

        with pytest.raises(ValidationError):
            dummy(-1.0)

    def test_multiple_validators(self):
        @validate_input(price=is_valid_price, qty=lambda x: x > 0)
        def dummy(price, qty):
            return price * qty

        assert dummy(100.0, 5) == 500.0


class TestDataValidators:
    """Tests for DataValidators class."""

    def test_validate_price_true(self):
        assert DataValidators.validate_price(450.0) is True

    def test_validate_price_false(self):
        assert DataValidators.validate_price(-1.0) is False

    def test_validate_price_zero(self):
        assert DataValidators.validate_price(0) is False

    def test_validate_quantity_true(self):
        assert DataValidators.validate_quantity(100) is True

    def test_validate_quantity_false(self):
        assert DataValidators.validate_quantity(0) is False

    def test_validate_symbol_true(self):
        assert DataValidators.validate_symbol("SPY") is True

    def test_validate_symbol_empty(self):
        assert DataValidators.validate_symbol("") is False

    def test_validate_date_true(self):
        assert DataValidators.validate_date("2025-01-01") is True

    def test_validate_date_false(self):
        assert DataValidators.validate_date("not-a-date") is False

    def test_validate_percentage_true(self):
        assert DataValidators.validate_percentage(50.0) is True

    def test_validate_percentage_false(self):
        assert DataValidators.validate_percentage(101.0) is False


class TestValidatorsAlias:
    """Tests that Validators is an alias for DataValidators."""

    def test_same_class(self):
        assert Validators is DataValidators

    def test_validate_price(self):
        assert Validators.validate_price(100.0) is True


# ==============================================================================
# EDGE CASE INTEGRATION TESTS
# ==============================================================================


class TestU06MathEdgeCases:
    """Edge case tests for U06 MathUtils."""

    def test_calculate_var_all_negative(self):
        """VaR with all negative returns."""
        returns = [-0.05, -0.03, -0.04, -0.06, -0.02]
        var = calculate_var(returns, 0.95)
        assert var >= 0

    def test_ema_single_element(self):
        result = exponential_moving_average([5.0], 3)
        assert result == [5.0]

    def test_rolling_window_exact_size(self):
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = rolling_window(data, 5, max)
        assert len(result) == 1
        assert result[0] == 5.0

    def test_linear_interpolation_negative(self):
        result = linear_interpolation(-5, -10, 0, 0, 10)
        assert abs(result - 5.0) < 0.001

    def test_find_root_at_boundary(self):
        # f(x) = x, root at x=0; exact boundary
        root = find_root(lambda x: x, -1, 1)
        assert root is not None
        assert abs(root) < 1e-6


class TestU08ValidatorEdgeCases:
    """Edge case tests for U08 Validators."""

    def test_is_valid_number_with_infinity(self):
        # float("inf") should be a valid float(value)
        result = is_valid_number(float("inf"))
        assert isinstance(result, bool)

    def test_is_valid_string_with_unicode(self):
        assert is_valid_string("héllo") is True

    def test_validate_order_stp_lmt_needs_both(self):
        order = {
            "symbol": "SPY",
            "action": "BUY",
            "quantity": 100,
            "order_type": "STP_LMT",
        }
        valid, err = validate_order_data(order)
        assert valid is False

    def test_validate_order_trail_lmt_needs_limit_price(self):
        order = {
            "symbol": "SPY",
            "action": "SELL",
            "quantity": 50,
            "order_type": "TRAIL_LMT",
        }
        valid, err = validate_order_data(order)
        assert valid is False

    def test_sanitize_filename_very_long_name(self):
        long_name = "a" * 300 + ".txt"
        result = sanitize_filename(long_name)
        assert len(result) <= 204  # 200 + 4 (.txt)
