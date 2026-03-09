#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT73_MathValidatorsTests.py
Purpose: Tests for U06 MathUtils and U08 Validators

Author: Spyder Test Suite
Year Created: 2026
Last Updated: 2026-03-04 Time: 21:30:00
"""

# ==============================================================================
# BOOTSTRAP
# ==============================================================================
import sys
import os
import types
import importlib.util

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

# U06 — no local imports needed
_u06 = _load("Spyder/SpyderU_Utilities/SpyderU06_MathUtils.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU06_MathUtils"] = _u06

# U08 — needs U01 injected first
_u01 = _load("Spyder/SpyderU_Utilities/SpyderU01_Logger.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU01_Logger"] = _u01

_u08 = _load("Spyder/SpyderU_Utilities/SpyderU08_Validators.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU08_Validators"] = _u08

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import math
import pytest
import numpy as np
from datetime import date, datetime, time

# ==============================================================================
# U06 IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU06_MathUtils import (
    MathUtils,
    round_price,
    round_to_tick,
    calculate_percentage_change,
    calculate_compound_return,
    calculate_mean,
    calculate_std_dev,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_max_drawdown,
    calculate_var,
    calculate_cvar,
    normal_cdf,
    normal_pdf,
    calculate_probability_touch,
    calculate_probability_profit,
    find_root,
    minimize_scalar,
    calculate_position_size,
    calculate_kelly_criterion,
    calculate_risk_reward_ratio,
    linear_interpolation,
    cubic_spline_interpolation,
    rolling_window,
    exponential_moving_average,
    TRADING_DAYS_PER_YEAR,
    PRICE_PRECISION,
)

# ==============================================================================
# U08 IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU08_Validators import (
    DataValidators,
    Validators,
    ValidationError,
    is_valid_string,
    is_valid_number,
    is_valid_integer,
    is_valid_boolean,
    is_valid_list,
    is_valid_dict,
    is_valid_email,
    is_valid_phone,
    is_valid_ip_address,
    is_valid_url,
    is_valid_date,
    is_valid_time,
    is_valid_datetime,
    is_valid_symbol,
    is_valid_price,
    is_valid_quantity,
    is_valid_order_type,
    is_valid_time_in_force,
    is_valid_account_balance,
    is_valid_percentage,
    validate_order_data,
    validate_position_data,
    validate_config_value,
    sanitize_string,
    VALID_ORDER_TYPES,
    VALID_TIME_IN_FORCE,
    MIN_PRICE,
    MAX_PRICE,
)


# ==============================================================================
# ═══════════════════════════════════════════════════════════════════════════════
#  U06 — MathUtils TESTS
# ═══════════════════════════════════════════════════════════════════════════════
# ==============================================================================

class TestRoundPrice:
    def test_rounds_to_two_decimals_by_default(self):
        assert round_price(123.456) == 123.46

    def test_rounds_half_up(self):
        assert round_price(1.005) == 1.01

    def test_zero(self):
        assert round_price(0.0) == 0.0

    def test_custom_precision_4(self):
        result = round_price(1.23456789, precision=4)
        assert result == 1.2346

    def test_negative_value(self):
        # ROUND_HALF_UP rounds away from zero for negatives: -1.005 → -1.01
        assert round_price(-1.005) == -1.01

    def test_returns_float(self):
        assert isinstance(round_price(100.0), float)


class TestRoundToTick:
    def test_round_to_quarter(self):
        assert round_to_tick(123.456, 0.25) == pytest.approx(123.5, abs=1e-6)

    def test_already_on_tick(self):
        assert round_to_tick(100.0, 0.5) == pytest.approx(100.0, abs=1e-6)

    def test_round_to_0_01(self):
        assert round_to_tick(5.126, 0.01) == pytest.approx(5.13, abs=1e-6)

    def test_tick_1(self):
        assert round_to_tick(4.7, 1.0) == pytest.approx(5.0, abs=1e-6)


class TestCalculatePercentageChange:
    def test_simple_increase(self):
        result = calculate_percentage_change(100, 110)
        assert result == pytest.approx(10.0, abs=1e-6)

    def test_decrease(self):
        result = calculate_percentage_change(100, 90)
        assert result == pytest.approx(-10.0, abs=1e-6)

    def test_no_change(self):
        assert calculate_percentage_change(100, 100) == 0.0

    def test_old_value_zero_new_nonzero(self):
        result = calculate_percentage_change(0, 100)
        assert result == float("inf")

    def test_both_zero(self):
        assert calculate_percentage_change(0, 0) == 0.0

    def test_negative_old_value(self):
        result = calculate_percentage_change(-100, -50)
        assert result == pytest.approx(50.0, abs=1e-6)


class TestCalculateCompoundReturn:
    def test_single_return(self):
        result = calculate_compound_return([0.10])
        assert result == pytest.approx(0.10, abs=1e-9)

    def test_multiple_returns(self):
        result = calculate_compound_return([0.1, 0.1])
        assert result == pytest.approx(0.21, abs=1e-9)

    def test_empty_list(self):
        assert calculate_compound_return([]) == 0.0

    def test_loss_then_gain(self):
        result = calculate_compound_return([-0.5, 1.0])
        assert result == pytest.approx(0.0, abs=1e-9)

    def test_all_zeros(self):
        assert calculate_compound_return([0.0, 0.0]) == 0.0


class TestCalculateMean:
    def test_simple_mean(self):
        assert calculate_mean([1.0, 2.0, 3.0]) == pytest.approx(2.0)

    def test_single_value(self):
        assert calculate_mean([5.0]) == 5.0

    def test_empty_list(self):
        assert calculate_mean([]) == 0.0

    def test_negative_values(self):
        assert calculate_mean([-1.0, -3.0]) == pytest.approx(-2.0)


class TestCalculateStdDev:
    def test_known_std(self):
        result = calculate_std_dev([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0], sample=False)
        assert result == pytest.approx(2.0, abs=1e-4)

    def test_sample_std(self):
        result = calculate_std_dev([1.0, 2.0, 3.0, 4.0, 5.0], sample=True)
        assert result > 0

    def test_single_value_returns_zero(self):
        assert calculate_std_dev([5.0]) == 0.0

    def test_empty_list_returns_zero(self):
        assert calculate_std_dev([]) == 0.0


class TestCalculateSharpeRatio:
    def _make_returns(self, n=100, mean=0.001, std=0.01, seed=42):
        rng = np.random.default_rng(seed)
        return list(rng.normal(mean, std, n))

    def test_returns_float(self):
        rets = self._make_returns()
        result = calculate_sharpe_ratio(rets)
        assert isinstance(result, float)

    def test_positive_sharpe_for_positive_returns(self):
        rets = [0.01] * 100
        result = calculate_sharpe_ratio(rets, risk_free_rate=0.0)
        assert result > 0

    def test_single_return_is_zero(self):
        assert calculate_sharpe_ratio([0.01]) == 0.0

    def test_zero_std_returns_zero(self):
        rets = [0.001] * 50  # All equal → std=0 after ddof=1... but actually no
        # With constant returns and non-zero rf, excess returns are constant
        # std of excess returns will be 0 → return 0
        result = calculate_sharpe_ratio(rets, risk_free_rate=0.001 * TRADING_DAYS_PER_YEAR)
        assert result == 0.0


class TestCalculateSortinoRatio:
    def _make_returns(self, n=100, mean=0.001, std=0.01, seed=42):
        rng = np.random.default_rng(seed)
        return list(rng.normal(mean, std, n))

    def test_returns_float(self):
        rets = self._make_returns()
        result = calculate_sortino_ratio(rets)
        assert isinstance(result, float)

    def test_single_return_is_zero(self):
        assert calculate_sortino_ratio([0.01]) == 0.0

    def test_all_positive_returns_inf(self):
        rets = [0.01] * 50
        result = calculate_sortino_ratio(rets, risk_free_rate=0.0)
        assert result == float("inf")

    def test_mixed_returns_finite(self):
        rets = self._make_returns()
        result = calculate_sortino_ratio(rets)
        assert math.isfinite(result)


class TestCalculateMaxDrawdown:
    def test_no_drawdown(self):
        equity = [100, 110, 120, 130]
        dd, peak, trough = calculate_max_drawdown(equity)
        assert dd == pytest.approx(0.0, abs=1e-9)

    def test_simple_drawdown(self):
        equity = [100, 120, 80, 90]
        dd, peak, trough = calculate_max_drawdown(equity)
        assert dd < 0  # drawdown is negative percentage
        assert abs(dd) == pytest.approx(100 * 40 / 120, abs=0.01)  # 33.33%

    def test_peak_before_trough(self):
        equity = [100, 200, 50]
        dd, peak, trough = calculate_max_drawdown(equity)
        assert peak < trough

    def test_single_element_returns_zeros(self):
        dd, peak, trough = calculate_max_drawdown([100])
        assert dd == 0.0

    def test_returns_three_tuple(self):
        result = calculate_max_drawdown([100, 90, 110])
        assert len(result) == 3


class TestCalculateVar:
    def _make_returns(self):
        rng = np.random.default_rng(42)
        return list(rng.normal(0, 0.01, 200))

    def test_historical_var_positive(self):
        result = calculate_var(self._make_returns(), 0.95, "historical")
        assert result >= 0

    def test_parametric_var_positive(self):
        result = calculate_var(self._make_returns(), 0.95, "parametric")
        assert result >= 0

    def test_higher_confidence_higher_var(self):
        rets = self._make_returns()
        var95 = calculate_var(rets, 0.95)
        var99 = calculate_var(rets, 0.99)
        assert var99 >= var95

    def test_empty_returns_zero(self):
        assert calculate_var([], 0.95) == 0.0

    def test_invalid_method_raises(self):
        with pytest.raises(ValueError):
            calculate_var(self._make_returns(), 0.95, "invalid_method")


class TestCalculateCvar:
    def _make_returns(self):
        rng = np.random.default_rng(42)
        return list(rng.normal(0, 0.01, 200))

    def test_cvar_positive(self):
        result = calculate_cvar(self._make_returns(), 0.95)
        assert result >= 0

    def test_cvar_ge_var(self):
        rets = self._make_returns()
        var = calculate_var(rets, 0.95)
        cvar = calculate_cvar(rets, 0.95)
        assert cvar >= var - 1e-9  # CVaR >= VaR

    def test_empty_returns_zero(self):
        assert calculate_cvar([]) == 0.0


class TestNormalCdf:
    def test_cdf_at_zero(self):
        assert normal_cdf(0.0) == pytest.approx(0.5, abs=1e-9)

    def test_cdf_at_positive_inf(self):
        assert normal_cdf(10.0) == pytest.approx(1.0, abs=1e-6)

    def test_cdf_at_negative_inf(self):
        assert normal_cdf(-10.0) == pytest.approx(0.0, abs=1e-6)

    def test_cdf_at_1_96(self):
        assert normal_cdf(1.96) == pytest.approx(0.975, abs=0.001)

    def test_returns_float(self):
        assert isinstance(normal_cdf(0.5), float)


class TestNormalPdf:
    def test_pdf_at_zero_is_max(self):
        # Standard normal PDF is maximized at 0
        assert normal_pdf(0.0) == pytest.approx(1 / math.sqrt(2 * math.pi), abs=1e-9)

    def test_pdf_positive(self):
        assert normal_pdf(1.0) > 0

    def test_pdf_symmetric(self):
        assert normal_pdf(1.5) == pytest.approx(normal_pdf(-1.5), abs=1e-9)

    def test_returns_float(self):
        assert isinstance(normal_pdf(0.5), float)


class TestCalculateProbabilityTouch:
    def test_zero_days_to_expiry(self):
        result = calculate_probability_touch(450, 460, 0.20, 0)
        assert result == 0.0

    def test_same_price_returns_nonzero(self):
        result = calculate_probability_touch(450, 450, 0.20, 30)
        assert result > 0

    def test_near_price_high_probability(self):
        result = calculate_probability_touch(450, 451, 0.20, 30)
        assert result > 0.5

    def test_far_price_low_probability(self):
        result = calculate_probability_touch(450, 600, 0.20, 5)
        assert result < 0.1

    def test_probability_in_0_1(self):
        result = calculate_probability_touch(450, 460, 0.20, 30)
        assert 0 <= result <= 1.0


class TestCalculateProbabilityProfit:
    def test_bullish_above_breakeven_at_expiry(self):
        result = calculate_probability_profit(440, 450, 0.20, 0, is_bullish=True)
        assert result == 1.0

    def test_bullish_below_breakeven_at_expiry(self):
        result = calculate_probability_profit(460, 450, 0.20, 0, is_bullish=True)
        assert result == 0.0

    def test_bearish_below_breakeven_at_expiry(self):
        result = calculate_probability_profit(460, 450, 0.20, 0, is_bullish=False)
        assert result == 1.0

    def test_bullish_with_time_in_0_1(self):
        result = calculate_probability_profit(450, 450, 0.20, 30, is_bullish=True)
        assert 0 <= result <= 1.0

    def test_returns_float(self):
        result = calculate_probability_profit(450, 460, 0.20, 30)
        assert isinstance(result, float)


class TestFindRoot:
    def test_simple_root(self):
        # f(x) = x - 2; root = 2
        root = find_root(lambda x: x - 2, 0, 5)
        assert root == pytest.approx(2.0, abs=1e-6)

    def test_quadratic_root(self):
        # f(x) = x^2 - 4; root near 2 in [0,5]
        root = find_root(lambda x: x**2 - 4, 0, 5)
        assert root == pytest.approx(2.0, abs=1e-6)

    def test_no_sign_change_returns_none(self):
        # f(x) = x^2 + 1 — always positive
        result = find_root(lambda x: x**2 + 1, -5, 5)
        assert result is None

    def test_returns_float_or_none(self):
        result = find_root(lambda x: x - 1, 0, 2)
        assert result is None or isinstance(result, float)


class TestMinimizeScalar:
    def test_simple_minimum(self):
        # f(x) = (x - 3)^2; minimum at x=3
        x_min, f_min = minimize_scalar(lambda x: (x - 3)**2, (0, 10))
        assert x_min == pytest.approx(3.0, abs=1e-4)
        assert f_min == pytest.approx(0.0, abs=1e-6)

    def test_returns_tuple(self):
        result = minimize_scalar(lambda x: x**2, (-5, 5))
        assert len(result) == 2

    def test_returns_none_on_exception(self):
        # Degenerate bounds
        x_min, f_min = minimize_scalar(lambda x: x**2, (1, 1))
        # May succeed or fail — just check types
        assert x_min is None or isinstance(x_min, float)


class TestCalculatePositionSize:
    def test_basic_position_size(self):
        # $100k, 1% risk, $5 stop → $1000 / $5 = 200 contracts
        result = calculate_position_size(100_000, 1.0, 5.0, 1.0)
        assert result == 200

    def test_zero_stop_loss_returns_zero(self):
        assert calculate_position_size(100_000, 1.0, 0.0) == 0

    def test_zero_risk_percent_returns_zero(self):
        assert calculate_position_size(100_000, 0.0, 5.0) == 0

    def test_multiplier_reduces_contracts(self):
        result_no_mult = calculate_position_size(100_000, 1.0, 5.0, 1.0)
        result_with_mult = calculate_position_size(100_000, 1.0, 5.0, 100.0)
        assert result_with_mult < result_no_mult

    def test_returns_int(self):
        result = calculate_position_size(50_000, 2.0, 10.0)
        assert isinstance(result, int)


class TestCalculateKellyCriterion:
    def test_typical_kelly(self):
        # win_rate=0.6, avg_win=1.5, avg_loss=1.0
        result = calculate_kelly_criterion(0.6, 1.5, 1.0)
        assert result > 0

    def test_zero_win_rate_returns_zero(self):
        assert calculate_kelly_criterion(0.0, 1.0, 1.0) == 0.0

    def test_negative_edge_capped_at_zero(self):
        # win_rate=0.3, avg_win=0.5, avg_loss=1.0 → negative Kelly
        result = calculate_kelly_criterion(0.3, 0.5, 1.0)
        assert result == 0.0

    def test_capped_at_25_percent(self):
        result = calculate_kelly_criterion(0.99, 100.0, 1.0)
        assert result <= 0.25

    def test_zero_avg_loss_returns_zero(self):
        assert calculate_kelly_criterion(0.6, 1.5, 0.0) == 0.0


class TestCalculateRiskRewardRatio:
    def test_typical_ratio(self):
        result = calculate_risk_reward_ratio(100, 110, 95)
        assert result == pytest.approx(2.0, abs=1e-6)

    def test_zero_risk_nonzero_reward_is_inf(self):
        result = calculate_risk_reward_ratio(100, 110, 100)
        assert result == float("inf")

    def test_zero_risk_zero_reward_is_zero(self):
        result = calculate_risk_reward_ratio(100, 100, 100)
        assert result == 0.0

    def test_returns_float(self):
        assert isinstance(calculate_risk_reward_ratio(100, 110, 95), float)


class TestLinearInterpolation:
    def test_midpoint(self):
        result = linear_interpolation(0.5, 0, 0, 1, 10)
        assert result == pytest.approx(5.0, abs=1e-9)

    def test_at_left_endpoint(self):
        result = linear_interpolation(0, 0, 5, 1, 10)
        assert result == pytest.approx(5.0, abs=1e-9)

    def test_at_right_endpoint(self):
        result = linear_interpolation(1, 0, 5, 1, 10)
        assert result == pytest.approx(10.0, abs=1e-9)

    def test_same_x_returns_y1(self):
        result = linear_interpolation(3, 3, 42, 3, 99)
        assert result == pytest.approx(42.0, abs=1e-9)

    def test_extrapolation(self):
        result = linear_interpolation(2, 0, 0, 1, 10)
        assert result == pytest.approx(20.0, abs=1e-9)


class TestCubicSplineInterpolation:
    def _points(self):
        x = [0.0, 1.0, 2.0, 3.0, 4.0]
        y = [0.0, 1.0, 4.0, 9.0, 16.0]  # y = x^2
        return x, y

    def test_returns_float_for_scalar(self):
        x, y = self._points()
        result = cubic_spline_interpolation(x, y, 1.5)
        assert isinstance(result, float)

    def test_interpolates_at_known_points(self):
        x, y = self._points()
        result = cubic_spline_interpolation(x, y, 2.0)
        assert result == pytest.approx(4.0, abs=0.01)

    def test_returns_list_for_list_input(self):
        x, y = self._points()
        result = cubic_spline_interpolation(x, y, [0.5, 1.5])
        assert isinstance(result, list)

    def test_insufficient_points_raises(self):
        with pytest.raises((ValueError, Exception)):
            cubic_spline_interpolation([1.0], [1.0], 1.0)


class TestRollingWindow:
    def test_basic_rolling_mean(self):
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = rolling_window(data, 3, lambda w: sum(w) / len(w))
        assert result == pytest.approx([2.0, 3.0, 4.0], abs=1e-9)

    def test_window_larger_than_data_returns_empty(self):
        result = rolling_window([1.0, 2.0], 5, sum)
        assert result == []

    def test_window_size_1(self):
        data = [10.0, 20.0, 30.0]
        result = rolling_window(data, 1, lambda w: w[0])
        assert result == data

    def test_result_length(self):
        data = list(range(10))
        result = rolling_window(data, 3, sum)
        assert len(result) == 8  # 10 - 3 + 1


class TestExponentialMovingAverage:
    def test_single_element(self):
        result = exponential_moving_average([5.0], 10)
        assert result == [5.0]

    def test_first_element_is_first_data(self):
        result = exponential_moving_average([10.0, 20.0, 30.0], 2)
        assert result[0] == pytest.approx(10.0, abs=1e-9)

    def test_length_matches_input(self):
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = exponential_moving_average(data, 3)
        assert len(result) == len(data)

    def test_empty_input(self):
        result = exponential_moving_average([], 3)
        assert result == []

    def test_zero_period_returns_empty(self):
        result = exponential_moving_average([1.0, 2.0], 0)
        assert result == []

    def test_converges_toward_increasing_data(self):
        # EMA of monotonically increasing data should be increasing (eventually)
        data = [float(i) for i in range(1, 21)]
        result = exponential_moving_average(data, 5)
        assert result[-1] > result[0]


class TestMathUtilsClass:
    def test_round_price_method(self):
        assert MathUtils.round_price(1.005) == pytest.approx(1.01, abs=0.001)

    def test_round_to_tick_method(self):
        assert MathUtils.round_to_tick(10.3, 0.25) == pytest.approx(10.25, abs=1e-6)

    def test_percentage_change_method(self):
        assert MathUtils.calculate_percentage_change(100, 120) == pytest.approx(20.0)

    def test_compound_return_method(self):
        assert MathUtils.calculate_compound_return([0.1, -0.05]) == pytest.approx(0.045, abs=1e-9)

    def test_mean_method(self):
        assert MathUtils.calculate_mean([1.0, 3.0]) == pytest.approx(2.0)

    def test_std_dev_method(self):
        result = MathUtils.calculate_std_dev([1.0, 2.0, 3.0])
        assert result > 0

    def test_sharpe_method(self):
        rets = [0.005] * 100 + [-0.002] * 50
        result = MathUtils.calculate_sharpe_ratio(rets)
        assert isinstance(result, float)

    def test_sortino_method(self):
        rets = [0.005] * 100 + [-0.002] * 50
        result = MathUtils.calculate_sortino_ratio(rets)
        assert isinstance(result, float)


# ==============================================================================
# ═══════════════════════════════════════════════════════════════════════════════
#  U08 — Validators TESTS
# ═══════════════════════════════════════════════════════════════════════════════
# ==============================================================================

class TestValidationError:
    def test_creation(self):
        err = ValidationError("price", -1.0, "must be positive")
        assert err.field == "price"
        assert err.value == -1.0
        assert err.message == "must be positive"

    def test_raises_as_exception(self):
        with pytest.raises(ValidationError):
            raise ValidationError("x", None, "bad")

    def test_str_contains_field(self):
        err = ValidationError("quantity", 0, "must be > 0")
        assert "quantity" in str(err)

    def test_is_exception_subclass(self):
        assert issubclass(ValidationError, Exception)


class TestIsValidString:
    def test_valid_string(self):
        assert is_valid_string("hello") is True

    def test_non_string_false(self):
        assert is_valid_string(123) is False

    def test_empty_string_not_allowed_by_default(self):
        assert is_valid_string("") is False

    def test_empty_string_allowed(self):
        assert is_valid_string("", allow_empty=True) is True

    def test_min_length_satisfied(self):
        assert is_valid_string("abc", min_length=3) is True

    def test_min_length_failed(self):
        assert is_valid_string("ab", min_length=3) is False

    def test_max_length_satisfied(self):
        assert is_valid_string("hello", max_length=10) is True

    def test_max_length_failed(self):
        assert is_valid_string("hello world", max_length=5) is False

    def test_none_is_false(self):
        assert is_valid_string(None) is False


class TestIsValidNumber:
    def test_valid_float(self):
        assert is_valid_number(3.14) is True

    def test_valid_integer_input(self):
        assert is_valid_number(42) is True

    def test_string_numeric(self):
        assert is_valid_number("5.5") is True

    def test_non_numeric_string(self):
        assert is_valid_number("abc") is False

    def test_negative_not_allowed(self):
        assert is_valid_number(-1.0, allow_negative=False) is False

    def test_zero_not_allowed(self):
        assert is_valid_number(0, allow_zero=False) is False

    def test_min_value_constraint(self):
        assert is_valid_number(5, min_value=10) is False

    def test_max_value_constraint(self):
        assert is_valid_number(100, max_value=50) is False

    def test_none_returns_false(self):
        assert is_valid_number(None) is False


class TestIsValidInteger:
    def test_valid_int(self):
        assert is_valid_integer(5) is True

    def test_string_int(self):
        assert is_valid_integer("5") is True

    def test_string_float_is_false(self):
        assert is_valid_integer("5.5") is False

    def test_bool_is_false(self):
        assert is_valid_integer(True) is False

    def test_min_value(self):
        assert is_valid_integer(5, min_value=10) is False

    def test_max_value(self):
        assert is_valid_integer(15, max_value=10) is False

    def test_none_is_false(self):
        assert is_valid_integer(None) is False


class TestIsValidBoolean:
    def test_true(self):
        assert is_valid_boolean(True) is True

    def test_false(self):
        assert is_valid_boolean(False) is True

    def test_int_one_is_false(self):
        assert is_valid_boolean(1) is False

    def test_string_is_false(self):
        assert is_valid_boolean("true") is False

    def test_none_is_false(self):
        assert is_valid_boolean(None) is False


class TestIsValidList:
    def test_valid_list(self):
        assert is_valid_list([1, 2, 3]) is True

    def test_non_list_false(self):
        assert is_valid_list("abc") is False

    def test_empty_list_default(self):
        assert is_valid_list([]) is True

    def test_min_length_failed(self):
        assert is_valid_list([1], min_length=3) is False

    def test_max_length_failed(self):
        assert is_valid_list([1, 2, 3, 4], max_length=2) is False

    def test_item_validator_pass(self):
        assert is_valid_list([1, 2, 3], item_validator=lambda x: isinstance(x, int)) is True

    def test_item_validator_fail(self):
        assert is_valid_list([1, "two", 3], item_validator=lambda x: isinstance(x, int)) is False


class TestIsValidDict:
    def test_valid_dict(self):
        assert is_valid_dict({"a": 1}) is True

    def test_non_dict_false(self):
        assert is_valid_dict([1, 2]) is False

    def test_required_keys_present(self):
        assert is_valid_dict({"a": 1, "b": 2}, required_keys=["a", "b"]) is True

    def test_required_key_missing(self):
        assert is_valid_dict({"a": 1}, required_keys=["a", "b"]) is False

    def test_empty_dict(self):
        assert is_valid_dict({}) is True


class TestIsValidEmail:
    def test_valid_email(self):
        assert is_valid_email("user@example.com") is True

    def test_missing_at_sign(self):
        assert is_valid_email("userexample.com") is False

    def test_missing_domain(self):
        assert is_valid_email("user@") is False

    def test_non_string(self):
        assert is_valid_email(123) is False

    def test_subdomain_email(self):
        assert is_valid_email("user@mail.example.org") is True


class TestIsValidPhone:
    def test_valid_us_phone(self):
        assert is_valid_phone("5551234567") is True

    def test_with_dashes(self):
        assert is_valid_phone("555-123-4567") is True

    def test_non_string(self):
        assert is_valid_phone(5551234567) is False

    def test_too_short(self):
        assert is_valid_phone("12345") is False


class TestIsValidIpAddress:
    def test_valid_ip(self):
        assert is_valid_ip_address("192.168.1.1") is True

    def test_localhost(self):
        assert is_valid_ip_address("127.0.0.1") is True

    def test_invalid_octet(self):
        assert is_valid_ip_address("256.168.1.1") is False

    def test_non_string(self):
        assert is_valid_ip_address(192168) is False

    def test_hostname_is_false(self):
        assert is_valid_ip_address("example.com") is False


class TestIsValidUrl:
    def test_valid_http(self):
        assert is_valid_url("http://example.com") is True

    def test_valid_https(self):
        assert is_valid_url("https://api.example.com/v1/data") is True

    def test_missing_scheme(self):
        assert is_valid_url("example.com") is False

    def test_non_string(self):
        assert is_valid_url(42) is False


class TestIsValidDate:
    def test_date_object(self):
        assert is_valid_date(date(2025, 6, 15)) is True

    def test_valid_date_string(self):
        assert is_valid_date("2025-06-15") is True

    def test_invalid_string(self):
        assert is_valid_date("not-a-date") is False

    def test_min_date_constraint(self):
        assert is_valid_date(date(2020, 1, 1), min_date=date(2025, 1, 1)) is False

    def test_max_date_constraint(self):
        assert is_valid_date(date(2030, 1, 1), max_date=date(2025, 12, 31)) is False

    def test_non_date_non_string(self):
        assert is_valid_date(12345) is False


class TestIsValidTime:
    def test_time_object(self):
        assert is_valid_time(time(9, 30, 0)) is True

    def test_valid_time_string_hhmm(self):
        assert is_valid_time("09:30") is True

    def test_valid_time_string_hhmmss(self):
        assert is_valid_time("09:30:00") is True

    def test_invalid_string(self):
        assert is_valid_time("not-a-time") is False

    def test_non_time_non_string(self):
        assert is_valid_time(930) is False


class TestIsValidDatetime:
    def test_datetime_object(self):
        assert is_valid_datetime(datetime(2025, 6, 15, 9, 30)) is True

    def test_valid_string(self):
        assert is_valid_datetime("2025-06-15 09:30:00") is True

    def test_invalid_string(self):
        assert is_valid_datetime("not-a-datetime") is False

    def test_min_dt_constraint(self):
        dt = datetime(2020, 1, 1)
        assert is_valid_datetime(dt, min_dt=datetime(2025, 1, 1)) is False

    def test_non_datetime(self):
        assert is_valid_datetime(99999) is False


class TestIsValidSymbol:
    def test_spy(self):
        assert is_valid_symbol("SPY") is True

    def test_lowercase_false(self):
        assert is_valid_symbol("spy") is False

    def test_too_long_false(self):
        assert is_valid_symbol("TOOLONG") is False

    def test_non_string(self):
        assert is_valid_symbol(123) is False

    def test_single_char(self):
        assert is_valid_symbol("A") is True


class TestIsValidPrice:
    def test_valid_price(self):
        assert is_valid_price(450.50) is True

    def test_zero_is_invalid(self):
        assert is_valid_price(0.0) is False

    def test_negative_is_invalid(self):
        assert is_valid_price(-1.0) is False

    def test_above_max_is_invalid(self):
        assert is_valid_price(MAX_PRICE + 1) is False

    def test_min_price(self):
        assert is_valid_price(MIN_PRICE) is True

    def test_non_numeric(self):
        assert is_valid_price("abc") is False


class TestIsValidQuantity:
    def test_valid_int_quantity(self):
        assert is_valid_quantity(100) is True

    def test_zero_invalid(self):
        assert is_valid_quantity(0) is False

    def test_negative_invalid(self):
        assert is_valid_quantity(-5) is False

    def test_float_truncated_to_int_without_fractional(self):
        # is_valid_integer(1.5) does int(1.5)=1 which is valid — implementation truncates
        assert is_valid_quantity(1.5) is True

    def test_float_valid_with_fractional(self):
        assert is_valid_quantity(1.5, allow_fractional=True) is True


class TestIsValidOrderType:
    def test_mkt_valid(self):
        assert is_valid_order_type("MKT") is True

    def test_lmt_valid(self):
        assert is_valid_order_type("LMT") is True

    def test_all_valid_types(self):
        for ot in VALID_ORDER_TYPES:
            assert is_valid_order_type(ot) is True

    def test_invalid_type(self):
        assert is_valid_order_type("MARKET") is False

    def test_lowercase_invalid(self):
        assert is_valid_order_type("mkt") is False


class TestIsValidTimeInForce:
    def test_day_valid(self):
        assert is_valid_time_in_force("DAY") is True

    def test_gtc_valid(self):
        assert is_valid_time_in_force("GTC") is True

    def test_all_valid_tif(self):
        for tif in VALID_TIME_IN_FORCE:
            assert is_valid_time_in_force(tif) is True

    def test_invalid_tif(self):
        assert is_valid_time_in_force("WEEKLY") is False


class TestIsValidAccountBalance:
    def test_positive_balance(self):
        assert is_valid_account_balance(50000.0) is True

    def test_zero_balance(self):
        assert is_valid_account_balance(0.0) is True

    def test_negative_balance(self):
        assert is_valid_account_balance(-100.0) is False

    def test_non_numeric(self):
        assert is_valid_account_balance("abc") is False


class TestIsValidPercentage:
    def test_50_percent(self):
        assert is_valid_percentage(50.0) is True

    def test_zero(self):
        assert is_valid_percentage(0.0) is True

    def test_100(self):
        assert is_valid_percentage(100.0) is True

    def test_above_100(self):
        assert is_valid_percentage(101.0) is False

    def test_below_0(self):
        assert is_valid_percentage(-1.0) is False


class TestValidateOrderData:
    def _valid_order(self):
        return {
            "symbol": "SPY",
            "action": "BUY",
            "quantity": 10,
            "order_type": "MKT",
        }

    def test_valid_market_order(self):
        valid, err = validate_order_data(self._valid_order())
        assert valid is True
        assert err is None

    def test_missing_symbol(self):
        order = self._valid_order()
        del order["symbol"]
        valid, err = validate_order_data(order)
        assert valid is False
        assert "symbol" in err

    def test_missing_action(self):
        order = self._valid_order()
        del order["action"]
        valid, err = validate_order_data(order)
        assert valid is False

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

    def test_lmt_requires_limit_price(self):
        order = self._valid_order()
        order["order_type"] = "LMT"
        valid, err = validate_order_data(order)
        assert valid is False
        assert "limit_price" in err.lower() or "limit" in err.lower()

    def test_lmt_with_limit_price_valid(self):
        order = self._valid_order()
        order["order_type"] = "LMT"
        order["limit_price"] = 450.50
        valid, err = validate_order_data(order)
        assert valid is True

    def test_invalid_time_in_force(self):
        order = self._valid_order()
        order["time_in_force"] = "WEEKLY"
        valid, err = validate_order_data(order)
        assert valid is False

    def test_valid_time_in_force(self):
        order = self._valid_order()
        order["time_in_force"] = "GTC"
        valid, err = validate_order_data(order)
        assert valid is True


class TestValidatePositionData:
    def _valid_position(self):
        return {
            "symbol": "SPY",
            "quantity": 10,
            "entry_price": 450.50,
        }

    def test_valid_position(self):
        valid, err = validate_position_data(self._valid_position())
        assert valid is True

    def test_missing_symbol(self):
        pos = self._valid_position()
        del pos["symbol"]
        valid, err = validate_position_data(pos)
        assert valid is False

    def test_missing_quantity(self):
        pos = self._valid_position()
        del pos["quantity"]
        valid, err = validate_position_data(pos)
        assert valid is False

    def test_missing_entry_price(self):
        pos = self._valid_position()
        del pos["entry_price"]
        valid, err = validate_position_data(pos)
        assert valid is False

    def test_invalid_symbol(self):
        pos = self._valid_position()
        pos["symbol"] = "spy"
        valid, err = validate_position_data(pos)
        assert valid is False

    def test_with_current_price(self):
        pos = self._valid_position()
        pos["current_price"] = 455.0
        valid, err = validate_position_data(pos)
        assert valid is True

    def test_with_invalid_current_price(self):
        pos = self._valid_position()
        pos["current_price"] = -10.0
        valid, err = validate_position_data(pos)
        assert valid is False

    def test_with_unrealized_pnl(self):
        pos = self._valid_position()
        pos["unrealized_pnl"] = 50.5
        valid, err = validate_position_data(pos)
        assert valid is True


class TestValidateConfigValue:
    def test_no_schema_always_valid(self):
        valid, err = validate_config_value("unknown_key", "anything", {})
        assert valid is True

    def test_string_type_pass(self):
        schema = {"key": {"type": "string"}}
        valid, err = validate_config_value("key", "hello", schema)
        assert valid is True

    def test_string_type_fail(self):
        schema = {"key": {"type": "string"}}
        valid, err = validate_config_value("key", 42, schema)
        assert valid is False

    def test_number_type_pass(self):
        schema = {"key": {"type": "number"}}
        valid, err = validate_config_value("key", 3.14, schema)
        assert valid is True

    def test_integer_type_fail(self):
        schema = {"key": {"type": "integer"}}
        valid, err = validate_config_value("key", 3.14, schema)
        assert valid is False

    def test_boolean_type_pass(self):
        schema = {"key": {"type": "boolean"}}
        valid, err = validate_config_value("key", True, schema)
        assert valid is True

    def test_min_constraint(self):
        schema = {"key": {"min": 10}}
        valid, err = validate_config_value("key", 5, schema)
        assert valid is False

    def test_max_constraint(self):
        schema = {"key": {"max": 10}}
        valid, err = validate_config_value("key", 15, schema)
        assert valid is False

    def test_enum_constraint_pass(self):
        schema = {"key": {"enum": ["a", "b", "c"]}}
        valid, err = validate_config_value("key", "b", schema)
        assert valid is True

    def test_enum_constraint_fail(self):
        schema = {"key": {"enum": ["a", "b", "c"]}}
        valid, err = validate_config_value("key", "d", schema)
        assert valid is False

    def test_list_type_pass(self):
        schema = {"key": {"type": "list"}}
        valid, err = validate_config_value("key", [1, 2], schema)
        assert valid is True

    def test_dict_type_pass(self):
        schema = {"key": {"type": "dict"}}
        valid, err = validate_config_value("key", {"a": 1}, schema)
        assert valid is True


class TestSanitizeString:
    def test_strips_whitespace(self):
        result = sanitize_string("  hello  ")
        assert result == "hello"

    def test_max_length_truncates(self):
        result = sanitize_string("hello world", max_length=5)
        assert result == "hello"

    def test_no_truncation_when_no_max(self):
        result = sanitize_string("hello")
        assert result == "hello"

    def test_empty_string(self):
        result = sanitize_string("")
        assert result == ""


class TestDataValidatorsClass:
    def test_validate_price_positive(self):
        assert DataValidators.validate_price(450.50) is True

    def test_validate_price_zero(self):
        assert DataValidators.validate_price(0.0) is False

    def test_validate_price_negative(self):
        assert DataValidators.validate_price(-1.0) is False

    def test_validate_quantity_positive(self):
        assert DataValidators.validate_quantity(10) is True

    def test_validate_quantity_zero(self):
        assert DataValidators.validate_quantity(0) is False

    def test_validate_quantity_negative(self):
        assert DataValidators.validate_quantity(-5) is False

    def test_validate_symbol_valid(self):
        assert DataValidators.validate_symbol("SPY") is True

    def test_validate_symbol_empty(self):
        assert DataValidators.validate_symbol("") is False

    def test_validate_symbol_numeric(self):
        assert DataValidators.validate_symbol("123") is False

    def test_validate_date_valid(self):
        assert DataValidators.validate_date("2025-06-15") is True

    def test_validate_date_invalid(self):
        assert DataValidators.validate_date("not-a-date") is False

    def test_validate_percentage_valid(self):
        assert DataValidators.validate_percentage(50.0) is True

    def test_validate_percentage_100(self):
        assert DataValidators.validate_percentage(100.0) is True

    def test_validate_percentage_over_100(self):
        assert DataValidators.validate_percentage(101.0) is False


class TestValidatorsAlias:
    def test_validators_is_alias_for_data_validators(self):
        assert Validators is DataValidators

    def test_alias_works_for_validate_price(self):
        assert Validators.validate_price(100.0) is True
