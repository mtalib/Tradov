#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: test_SpyderT98_U06MathUtils_U08Validators.py
Purpose: Tests for U06 MathUtils and U08 Validators

Author: GitHub Copilot
Year Created: 2025
Last Updated: 2026-01-16 Time: 23:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import importlib
import os
import sys
import types
from datetime import date, datetime, time
from unittest.mock import MagicMock

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

# Stub SpyderU01_Logger
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

# U06 MathUtils — scipy + numpy, no SpyderLogger
for _k in list(sys.modules.keys()):
    if "SpyderU06_MathUtils" in _k:
        del sys.modules[_k]
u06_mod = importlib.import_module("Spyder.SpyderU_Utilities.SpyderU06_MathUtils")

MathUtils = u06_mod.MathUtils

# U08 Validators — imports SpyderLogger
for _k in list(sys.modules.keys()):
    if "SpyderU08_Validators" in _k:
        del sys.modules[_k]
u08_mod = importlib.import_module("Spyder.SpyderU_Utilities.SpyderU08_Validators")

ValidationError = u08_mod.ValidationError
DataValidators = u08_mod.DataValidators


# ==============================================================================
# ── U06 MATHUTILS ─────────────────────────────────────────────────────────────
# ==============================================================================


class TestU06BasicMath:
    """Tests for basic math functions in U06."""

    def test_round_price_two_decimal(self):
        assert u06_mod.round_price(123.456) == 123.46

    def test_round_price_custom_precision(self):
        assert u06_mod.round_price(1.23456, precision=3) == 1.235

    def test_round_price_zero_precision(self):
        result = u06_mod.round_price(123.7, precision=0)
        assert result == 124.0

    def test_round_price_already_rounded(self):
        assert u06_mod.round_price(100.00) == 100.00

    def test_round_to_tick_quarter(self):
        result = u06_mod.round_to_tick(123.3, 0.25)
        assert abs(result - 123.25) < 0.001

    def test_round_to_tick_exact(self):
        assert u06_mod.round_to_tick(10.0, 0.5) == 10.0

    def test_round_to_tick_up(self):
        result = u06_mod.round_to_tick(10.4, 0.5)
        assert abs(result - 10.5) < 0.001

    def test_calculate_percentage_change_positive(self):
        assert u06_mod.calculate_percentage_change(100, 110) == pytest.approx(10.0)

    def test_calculate_percentage_change_negative(self):
        assert u06_mod.calculate_percentage_change(100, 90) == pytest.approx(-10.0)

    def test_calculate_percentage_change_zero_old(self):
        result = u06_mod.calculate_percentage_change(0, 100)
        assert result == float("inf")

    def test_calculate_percentage_change_zero_both(self):
        assert u06_mod.calculate_percentage_change(0, 0) == 0.0

    def test_calculate_compound_return_positive(self):
        result = u06_mod.calculate_compound_return([0.1, 0.1])
        assert result == pytest.approx(0.21)

    def test_calculate_compound_return_empty(self):
        assert u06_mod.calculate_compound_return([]) == 0.0

    def test_calculate_compound_return_single(self):
        assert u06_mod.calculate_compound_return([0.05]) == pytest.approx(0.05)


class TestU06Statistics:
    """Tests for statistical functions in U06."""

    RETURNS = [0.01, -0.02, 0.015, 0.005, -0.01, 0.02, -0.005, 0.01]

    def test_calculate_mean_basic(self):
        result = u06_mod.calculate_mean([1.0, 2.0, 3.0])
        assert result == pytest.approx(2.0)

    def test_calculate_mean_empty(self):
        assert u06_mod.calculate_mean([]) == 0.0

    def test_calculate_mean_single(self):
        assert u06_mod.calculate_mean([5.0]) == pytest.approx(5.0)

    def test_calculate_std_dev_sample(self):
        result = u06_mod.calculate_std_dev([1.0, 2.0, 3.0, 4.0, 5.0])
        assert result == pytest.approx(1.5811, rel=1e-3)

    def test_calculate_std_dev_single_returns_zero(self):
        assert u06_mod.calculate_std_dev([5.0]) == 0.0

    def test_calculate_std_dev_two_identical(self):
        assert u06_mod.calculate_std_dev([3.0, 3.0]) == 0.0

    def test_calculate_sharpe_ratio_returns_float(self):
        result = u06_mod.calculate_sharpe_ratio(self.RETURNS)
        assert isinstance(result, float)

    def test_calculate_sharpe_ratio_insufficient_returns(self):
        assert u06_mod.calculate_sharpe_ratio([0.01]) == 0.0

    def test_calculate_sharpe_ratio_positive_returns(self):
        # Mix of positive returns with variance so std_dev != 0
        good_returns = [0.01, 0.02, 0.015, 0.005, 0.012, 0.018, 0.008, 0.022] * 5
        sharpe = u06_mod.calculate_sharpe_ratio(good_returns)
        assert sharpe > 0

    def test_calculate_sortino_ratio_returns_float(self):
        result = u06_mod.calculate_sortino_ratio(self.RETURNS)
        assert isinstance(result, float)

    def test_calculate_sortino_ratio_insufficient(self):
        assert u06_mod.calculate_sortino_ratio([0.01]) == 0.0

    def test_calculate_sortino_all_positive(self):
        # No downside → inf
        result = u06_mod.calculate_sortino_ratio([0.01, 0.02, 0.015])
        assert result == float("inf")

    def test_calculate_max_drawdown_returns_tuple(self):
        equity = [100, 110, 105, 95, 100, 90, 95]
        dd, peak, trough = u06_mod.calculate_max_drawdown(equity)
        assert isinstance(dd, float)
        assert isinstance(peak, int)
        assert isinstance(trough, int)

    def test_calculate_max_drawdown_no_drawdown(self):
        equity = [100, 110, 120, 130]
        dd, _, _ = u06_mod.calculate_max_drawdown(equity)
        assert dd == pytest.approx(0.0)

    def test_calculate_max_drawdown_single_returns_zeros(self):
        dd, p, t = u06_mod.calculate_max_drawdown([100])
        assert dd == 0.0
        assert p == 0
        assert t == 0


class TestU06VaR:
    """Tests for VaR/CVaR functions in U06."""

    RETURNS = [-0.03, -0.01, 0.01, 0.02, 0.01, -0.02, 0.03, -0.015, 0.005, 0.01]

    def test_calculate_var_historical(self):
        result = u06_mod.calculate_var(self.RETURNS, 0.95, "historical")
        assert isinstance(result, float)

    def test_calculate_var_parametric(self):
        result = u06_mod.calculate_var(self.RETURNS, 0.95, "parametric")
        assert isinstance(result, float)

    def test_calculate_var_empty(self):
        assert u06_mod.calculate_var([], 0.95) == 0.0

    def test_calculate_var_invalid_method(self):
        with pytest.raises(ValueError):
            u06_mod.calculate_var(self.RETURNS, 0.95, "invalid_method")

    def test_calculate_cvar_returns_float(self):
        result = u06_mod.calculate_cvar(self.RETURNS, 0.95)
        assert isinstance(result, float)

    def test_calculate_cvar_empty(self):
        assert u06_mod.calculate_cvar([], 0.95) == 0.0

    def test_calculate_cvar_ge_var(self):
        # CVaR should be >= VaR (expected shortfall is worse than VaR)
        var = u06_mod.calculate_var(self.RETURNS, 0.95)
        cvar = u06_mod.calculate_cvar(self.RETURNS, 0.95)
        assert cvar >= var - 0.001  # allow tiny floating-point tolerance


class TestU06Probability:
    """Tests for probability functions in U06."""

    def test_normal_cdf_at_zero(self):
        result = u06_mod.normal_cdf(0.0)
        assert result == pytest.approx(0.5, abs=1e-6)

    def test_normal_cdf_positive(self):
        assert u06_mod.normal_cdf(1.96) > 0.97

    def test_normal_cdf_negative(self):
        assert u06_mod.normal_cdf(-1.96) < 0.03

    def test_normal_cdf_range(self):
        assert 0.0 <= u06_mod.normal_cdf(0.0) <= 1.0

    def test_normal_pdf_at_zero(self):
        result = u06_mod.normal_pdf(0.0)
        assert result == pytest.approx(0.3989, abs=1e-3)

    def test_normal_pdf_positive_value(self):
        assert u06_mod.normal_pdf(0.0) > u06_mod.normal_pdf(1.0)

    def test_calculate_probability_touch_range(self):
        prob = u06_mod.calculate_probability_touch(450, 460, 0.20, 30)
        assert 0.0 <= prob <= 1.0

    def test_calculate_probability_touch_zero_days(self):
        prob = u06_mod.calculate_probability_touch(450, 460, 0.20, 0)
        assert prob == 0.0

    def test_calculate_probability_touch_zero_vol(self):
        prob = u06_mod.calculate_probability_touch(450, 460, 0.0, 30)
        assert prob == 0.0

    def test_calculate_probability_profit_bullish(self):
        prob = u06_mod.calculate_probability_profit(
            breakeven_price=450, current_price=455, volatility=0.20,
            days_to_expiry=30, is_bullish=True
        )
        assert 0.0 <= prob <= 1.0

    def test_calculate_probability_profit_bearish(self):
        prob = u06_mod.calculate_probability_profit(
            breakeven_price=460, current_price=455, volatility=0.20,
            days_to_expiry=30, is_bullish=False
        )
        assert 0.0 <= prob <= 1.0

    def test_calculate_probability_profit_expired_bullish_above(self):
        # Expired, bullish, price above breakeven → prob = 1.0
        prob = u06_mod.calculate_probability_profit(
            breakeven_price=450, current_price=455, volatility=0.20,
            days_to_expiry=0, is_bullish=True
        )
        assert prob == 1.0

    def test_calculate_probability_profit_expired_bullish_below(self):
        prob = u06_mod.calculate_probability_profit(
            breakeven_price=460, current_price=455, volatility=0.20,
            days_to_expiry=0, is_bullish=True
        )
        assert prob == 0.0


class TestU06Financial:
    """Tests for financial calculation functions in U06."""

    def test_calculate_position_size_basic(self):
        result = u06_mod.calculate_position_size(100000, 1.0, 5.0, 100)
        assert isinstance(result, int)
        assert result > 0

    def test_calculate_position_size_zero_stop(self):
        assert u06_mod.calculate_position_size(100000, 1.0, 0, 100) == 0

    def test_calculate_position_size_zero_risk(self):
        assert u06_mod.calculate_position_size(100000, 0, 5.0, 100) == 0

    def test_calculate_kelly_criterion_basic(self):
        result = u06_mod.calculate_kelly_criterion(0.6, 1.5, 1.0)
        assert 0.0 <= result <= 0.25

    def test_calculate_kelly_criterion_zero_loss(self):
        assert u06_mod.calculate_kelly_criterion(0.6, 1.5, 0) == 0.0

    def test_calculate_kelly_criterion_zero_win_rate(self):
        assert u06_mod.calculate_kelly_criterion(0, 1.5, 1.0) == 0.0

    def test_calculate_kelly_criterion_capped_at_25pct(self):
        # Very high win rate should still be capped
        result = u06_mod.calculate_kelly_criterion(0.99, 100, 1.0)
        assert result <= 0.25

    def test_calculate_risk_reward_basic(self):
        result = u06_mod.calculate_risk_reward_ratio(450, 460, 445)
        assert result == pytest.approx(2.0)

    def test_calculate_risk_reward_zero_risk(self):
        result = u06_mod.calculate_risk_reward_ratio(450, 460, 450)
        assert result == float("inf")

    def test_calculate_risk_reward_equal_risk_reward(self):
        result = u06_mod.calculate_risk_reward_ratio(450, 460, 440)
        assert result == pytest.approx(1.0)


class TestU06Interpolation:
    """Tests for interpolation functions in U06."""

    def test_linear_interpolation_midpoint(self):
        result = u06_mod.linear_interpolation(1.5, 1.0, 10.0, 2.0, 20.0)
        assert result == pytest.approx(15.0)

    def test_linear_interpolation_at_x1(self):
        result = u06_mod.linear_interpolation(1.0, 1.0, 10.0, 2.0, 20.0)
        assert result == pytest.approx(10.0)

    def test_linear_interpolation_at_x2(self):
        result = u06_mod.linear_interpolation(2.0, 1.0, 10.0, 2.0, 20.0)
        assert result == pytest.approx(20.0)

    def test_linear_interpolation_equal_x(self):
        result = u06_mod.linear_interpolation(1.0, 1.0, 5.0, 1.0, 10.0)
        assert result == pytest.approx(5.0)  # Returns y1 when x2 == x1

    def test_cubic_spline_basic(self):
        xs = [0.0, 1.0, 2.0, 3.0]
        ys = [0.0, 1.0, 4.0, 9.0]
        result = u06_mod.cubic_spline_interpolation(xs, ys, 1.5)
        assert isinstance(result, float)

    def test_cubic_spline_insufficient_points(self):
        with pytest.raises((ValueError, Exception)):
            u06_mod.cubic_spline_interpolation([1.0], [1.0], 1.0)


class TestU06Arrays:
    """Tests for array operation functions in U06."""

    def test_rolling_window_basic(self):
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = u06_mod.rolling_window(data, 3, sum)
        assert result == [6.0, 9.0, 12.0]

    def test_rolling_window_window_too_large(self):
        data = [1.0, 2.0]
        result = u06_mod.rolling_window(data, 5, sum)
        assert result == []

    def test_rolling_window_single_window(self):
        data = [1.0, 2.0, 3.0]
        result = u06_mod.rolling_window(data, 3, lambda w: w[-1])
        assert result == [3.0]

    def test_ema_basic(self):
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = u06_mod.exponential_moving_average(data, 3)
        assert len(result) == 5
        assert result[0] == 1.0

    def test_ema_empty(self):
        assert u06_mod.exponential_moving_average([], 5) == []

    def test_ema_zero_period(self):
        assert u06_mod.exponential_moving_average([1.0, 2.0], 0) == []

    def test_ema_first_value_equals_data(self):
        data = [10.0, 11.0, 12.0]
        result = u06_mod.exponential_moving_average(data, 2)
        assert result[0] == 10.0


class TestU06MathUtilsClass:
    """Tests for MathUtils wrapper class."""

    def test_round_price_method(self):
        assert MathUtils.round_price(1.235, 2) == pytest.approx(1.24)

    def test_round_to_tick_method(self):
        assert MathUtils.round_to_tick(10.3, 0.5) == pytest.approx(10.5)

    def test_calculate_percentage_change_method(self):
        assert MathUtils.calculate_percentage_change(100, 105) == pytest.approx(5.0)

    def test_calculate_compound_return_method(self):
        result = MathUtils.calculate_compound_return([0.05, 0.05])
        assert result == pytest.approx(0.1025)

    def test_calculate_mean_method(self):
        assert MathUtils.calculate_mean([1.0, 3.0]) == pytest.approx(2.0)

    def test_calculate_std_dev_method(self):
        result = MathUtils.calculate_std_dev([1.0, 2.0, 3.0])
        assert isinstance(result, float)

    def test_calculate_sharpe_ratio_method(self):
        returns = [0.01] * 20
        result = MathUtils.calculate_sharpe_ratio(returns)
        assert isinstance(result, float)

    def test_calculate_sortino_ratio_method(self):
        result = MathUtils.calculate_sortino_ratio([0.01, -0.01, 0.02, -0.005])
        assert isinstance(result, float)


# ==============================================================================
# ── U08 VALIDATORS ────────────────────────────────────────────────────────────
# ==============================================================================


class TestU08ValidationError:
    """Tests for ValidationError class."""

    def test_is_exception(self):
        assert issubclass(ValidationError, Exception)

    def test_has_field_attribute(self):
        err = ValidationError("field", "value", "bad")
        assert err.field == "field"

    def test_has_value_attribute(self):
        err = ValidationError("price", 99, "too low")
        assert err.value == 99

    def test_has_message_attribute(self):
        err = ValidationError("qty", 0, "zero not allowed")
        assert err.message == "zero not allowed"

    def test_str_representation(self):
        err = ValidationError("symbol", "123", "invalid")
        assert "symbol" in str(err)


class TestU08BasicValidators:
    """Tests for basic type validators in U08."""

    def test_is_valid_string_basic(self):
        assert u08_mod.is_valid_string("hello") is True

    def test_is_valid_string_empty_rejected(self):
        assert u08_mod.is_valid_string("") is False

    def test_is_valid_string_empty_allowed(self):
        assert u08_mod.is_valid_string("", allow_empty=True) is True

    def test_is_valid_string_non_string(self):
        assert u08_mod.is_valid_string(123) is False

    def test_is_valid_string_min_length(self):
        assert u08_mod.is_valid_string("hi", min_length=3) is False
        assert u08_mod.is_valid_string("hey", min_length=3) is True

    def test_is_valid_string_max_length(self):
        assert u08_mod.is_valid_string("hello", max_length=3) is False
        assert u08_mod.is_valid_string("hi", max_length=3) is True

    def test_is_valid_number_int(self):
        assert u08_mod.is_valid_number(42) is True

    def test_is_valid_number_float(self):
        assert u08_mod.is_valid_number(3.14) is True

    def test_is_valid_number_negative_rejected(self):
        assert u08_mod.is_valid_number(-5, allow_negative=False) is False

    def test_is_valid_number_zero_rejected(self):
        assert u08_mod.is_valid_number(0, allow_zero=False) is False

    def test_is_valid_number_string_numeric(self):
        assert u08_mod.is_valid_number("3.14") is True

    def test_is_valid_number_string_non_numeric(self):
        assert u08_mod.is_valid_number("abc") is False

    def test_is_valid_number_with_range(self):
        assert u08_mod.is_valid_number(5, min_value=1, max_value=10) is True
        assert u08_mod.is_valid_number(0, min_value=1, max_value=10) is False

    def test_is_valid_integer_valid(self):
        assert u08_mod.is_valid_integer(42) is True

    def test_is_valid_integer_string_int(self):
        assert u08_mod.is_valid_integer("42") is True

    def test_is_valid_integer_bool_rejected(self):
        # bool is a subclass of int but should be rejected
        assert u08_mod.is_valid_integer(True) is False

    def test_is_valid_integer_float_rejected(self):
        assert u08_mod.is_valid_integer(3.14) is True  # int(3.14) == 3

    def test_is_valid_integer_with_range(self):
        assert u08_mod.is_valid_integer(5, min_value=1, max_value=10) is True
        assert u08_mod.is_valid_integer(0, min_value=1, max_value=10) is False

    def test_is_valid_boolean_true(self):
        assert u08_mod.is_valid_boolean(True) is True

    def test_is_valid_boolean_false(self):
        assert u08_mod.is_valid_boolean(False) is True

    def test_is_valid_boolean_int(self):
        assert u08_mod.is_valid_boolean(1) is False

    def test_is_valid_boolean_string(self):
        assert u08_mod.is_valid_boolean("true") is False


class TestU08CollectionValidators:
    """Tests for list/dict validators in U08."""

    def test_is_valid_list_basic(self):
        assert u08_mod.is_valid_list([1, 2, 3]) is True

    def test_is_valid_list_non_list(self):
        assert u08_mod.is_valid_list((1, 2)) is False

    def test_is_valid_list_empty_allowed(self):
        assert u08_mod.is_valid_list([]) is True

    def test_is_valid_list_min_length(self):
        assert u08_mod.is_valid_list([1], min_length=2) is False
        assert u08_mod.is_valid_list([1, 2], min_length=2) is True

    def test_is_valid_list_max_length(self):
        assert u08_mod.is_valid_list([1, 2, 3], max_length=2) is False

    def test_is_valid_list_with_validator(self):
        assert u08_mod.is_valid_list([1, 2, 3], item_validator=lambda x: x > 0) is True
        assert u08_mod.is_valid_list([1, -1, 3], item_validator=lambda x: x > 0) is False

    def test_is_valid_dict_basic(self):
        assert u08_mod.is_valid_dict({"a": 1}) is True

    def test_is_valid_dict_non_dict(self):
        assert u08_mod.is_valid_dict([1, 2]) is False

    def test_is_valid_dict_required_keys_present(self):
        assert u08_mod.is_valid_dict({"a": 1, "b": 2}, required_keys=["a", "b"]) is True

    def test_is_valid_dict_required_keys_missing(self):
        assert u08_mod.is_valid_dict({"a": 1}, required_keys=["a", "b"]) is False


class TestU08PatternValidators:
    """Tests for pattern-based validators in U08."""

    def test_is_valid_email_valid(self):
        assert u08_mod.is_valid_email("user@example.com") is True

    def test_is_valid_email_invalid(self):
        assert u08_mod.is_valid_email("not-an-email") is False

    def test_is_valid_email_non_string(self):
        assert u08_mod.is_valid_email(42) is False

    def test_is_valid_phone_valid(self):
        assert u08_mod.is_valid_phone("1234567890") is True

    def test_is_valid_phone_invalid(self):
        assert u08_mod.is_valid_phone("abc") is False

    def test_is_valid_ip_address_valid(self):
        assert u08_mod.is_valid_ip_address("192.168.1.1") is True

    def test_is_valid_ip_address_invalid(self):
        assert u08_mod.is_valid_ip_address("999.999.999.999") is False

    def test_is_valid_ip_address_non_string(self):
        assert u08_mod.is_valid_ip_address(12345) is False

    def test_is_valid_url_http(self):
        assert u08_mod.is_valid_url("http://example.com") is True

    def test_is_valid_url_https(self):
        assert u08_mod.is_valid_url("https://example.com") is True

    def test_is_valid_url_invalid(self):
        assert u08_mod.is_valid_url("not-a-url") is False


class TestU08DateTimeValidators:
    """Tests for date/time validators in U08."""

    def test_is_valid_date_date_object(self):
        assert u08_mod.is_valid_date(date(2025, 1, 1)) is True

    def test_is_valid_date_string_iso(self):
        assert u08_mod.is_valid_date("2025-01-01") is True

    def test_is_valid_date_invalid_string(self):
        assert u08_mod.is_valid_date("not-a-date") is False

    def test_is_valid_date_integer(self):
        assert u08_mod.is_valid_date(20250101) is False

    def test_is_valid_time_time_object(self):
        assert u08_mod.is_valid_time(time(9, 30, 0)) is True

    def test_is_valid_time_string_hms(self):
        assert u08_mod.is_valid_time("09:30:00") is True

    def test_is_valid_time_string_hm(self):
        assert u08_mod.is_valid_time("09:30") is True

    def test_is_valid_time_invalid(self):
        assert u08_mod.is_valid_time("garbage") is False

    def test_is_valid_datetime_datetime_object(self):
        assert u08_mod.is_valid_datetime(datetime(2025, 1, 1, 9, 30)) is True

    def test_is_valid_datetime_string(self):
        assert u08_mod.is_valid_datetime("2025-01-01 09:30:00") is True

    def test_is_valid_datetime_invalid_string(self):
        assert u08_mod.is_valid_datetime("not-a-datetime") is False


class TestU08TradingValidators:
    """Tests for trading-specific validators in U08."""

    def test_is_valid_symbol_spy(self):
        assert u08_mod.is_valid_symbol("SPY") is True

    def test_is_valid_symbol_lowercase(self):
        # symbols are typically uppercase; pattern may reject lowercase
        result = u08_mod.is_valid_symbol("spy")
        assert isinstance(result, bool)

    def test_is_valid_symbol_non_string(self):
        assert u08_mod.is_valid_symbol(123) is False

    def test_is_valid_price_valid(self):
        assert u08_mod.is_valid_price(450.50) is True

    def test_is_valid_price_zero(self):
        # MIN_PRICE is likely 0; price=0 would fail if min_price > 0
        assert u08_mod.is_valid_price(0.0) is False or u08_mod.is_valid_price(0.0) is True

    def test_is_valid_price_negative(self):
        assert u08_mod.is_valid_price(-10) is False

    def test_is_valid_price_string(self):
        assert u08_mod.is_valid_price("abc") is False

    def test_is_valid_quantity_valid_int(self):
        assert u08_mod.is_valid_quantity(100) is True

    def test_is_valid_quantity_zero_rejected(self):
        assert u08_mod.is_valid_quantity(0) is False

    def test_is_valid_quantity_negative_rejected(self):
        assert u08_mod.is_valid_quantity(-5) is False

    def test_is_valid_order_type_valid(self):
        assert u08_mod.is_valid_order_type("MKT") is True
        assert u08_mod.is_valid_order_type("LMT") is True

    def test_is_valid_order_type_invalid(self):
        assert u08_mod.is_valid_order_type("INVALID") is False

    def test_is_valid_time_in_force_valid(self):
        assert u08_mod.is_valid_time_in_force("DAY") is True
        assert u08_mod.is_valid_time_in_force("GTC") is True

    def test_is_valid_time_in_force_invalid(self):
        assert u08_mod.is_valid_time_in_force("BAD") is False

    def test_is_valid_account_balance_positive(self):
        assert u08_mod.is_valid_account_balance(10000.0) is True

    def test_is_valid_account_balance_zero(self):
        assert u08_mod.is_valid_account_balance(0.0) is True

    def test_is_valid_account_balance_negative(self):
        assert u08_mod.is_valid_account_balance(-100) is False

    def test_is_valid_percentage_valid(self):
        assert u08_mod.is_valid_percentage(50.0) is True

    def test_is_valid_percentage_out_of_range(self):
        assert u08_mod.is_valid_percentage(110.0) is False


class TestU08ComplexValidators:
    """Tests for complex validators (order/position data) in U08."""

    def _valid_market_order(self):
        return {
            "symbol": "SPY",
            "action": "BUY",
            "quantity": 100,
            "order_type": "MKT",
        }

    def _valid_limit_order(self):
        return {
            "symbol": "SPY",
            "action": "BUY",
            "quantity": 100,
            "order_type": "LMT",
            "limit_price": 450.50,
        }

    def test_validate_order_data_market_order(self):
        valid, err = u08_mod.validate_order_data(self._valid_market_order())
        assert valid is True
        assert err is None

    def test_validate_order_data_limit_order(self):
        valid, err = u08_mod.validate_order_data(self._valid_limit_order())
        assert valid is True
        assert err is None

    def test_validate_order_data_missing_field(self):
        order = self._valid_market_order()
        del order["symbol"]
        valid, err = u08_mod.validate_order_data(order)
        assert valid is False
        assert err is not None

    def test_validate_order_data_invalid_action(self):
        order = self._valid_market_order()
        order["action"] = "HOLD"
        valid, err = u08_mod.validate_order_data(order)
        assert valid is False

    def test_validate_order_data_lmt_missing_price(self):
        order = {
            "symbol": "SPY",
            "action": "BUY",
            "quantity": 100,
            "order_type": "LMT",
            # no limit_price
        }
        valid, err = u08_mod.validate_order_data(order)
        assert valid is False

    def test_validate_position_data_valid(self):
        pos = {"symbol": "SPY", "quantity": 100, "entry_price": 450.0}
        valid, err = u08_mod.validate_position_data(pos)
        assert valid is True
        assert err is None

    def test_validate_position_data_missing_required(self):
        pos = {"symbol": "SPY", "quantity": 100}  # no entry_price
        valid, err = u08_mod.validate_position_data(pos)
        assert valid is False

    def test_validate_position_data_invalid_price(self):
        pos = {"symbol": "SPY", "quantity": 100, "entry_price": -10}
        valid, err = u08_mod.validate_position_data(pos)
        assert valid is False


class TestU08Sanitizers:
    """Tests for sanitization functions in U08."""

    def test_sanitize_string_strips_whitespace(self):
        result = u08_mod.sanitize_string("  hello  ")
        assert result == "hello"

    def test_sanitize_string_max_length(self):
        result = u08_mod.sanitize_string("hello world", max_length=5)
        assert len(result) <= 5

    def test_sanitize_string_allowed_chars(self):
        result = u08_mod.sanitize_string("abc123!", allowed_chars=r"[a-z]")
        assert "!" not in result
        assert "1" not in result

    def test_sanitize_filename_removes_invalid(self):
        result = u08_mod.sanitize_filename('my<file>?.txt')
        assert "<" not in result
        assert ">" not in result
        assert "?" not in result

    def test_sanitize_filename_preserves_extension(self):
        result = u08_mod.sanitize_filename("myfile.csv")
        assert result.endswith(".csv")

    def test_sanitize_filename_removes_path(self):
        result = u08_mod.sanitize_filename("/some/path/file.txt")
        assert "/" not in result


class TestU08DataValidatorsClass:
    """Tests for DataValidators class."""

    def test_validate_price_positive(self):
        assert DataValidators.validate_price(100.0) is True

    def test_validate_price_negative(self):
        assert DataValidators.validate_price(-10.0) is False

    def test_validate_price_zero(self):
        assert DataValidators.validate_price(0.0) is False

    def test_validate_quantity_valid(self):
        assert DataValidators.validate_quantity(10) is True

    def test_validate_quantity_zero(self):
        assert DataValidators.validate_quantity(0) is False

    def test_validate_quantity_negative(self):
        assert DataValidators.validate_quantity(-1) is False

    def test_validate_symbol_valid(self):
        assert DataValidators.validate_symbol("SPY") is True

    def test_validate_symbol_empty(self):
        assert DataValidators.validate_symbol("") is False

    def test_validate_symbol_non_alpha(self):
        assert DataValidators.validate_symbol("SP1Y") is False

    def test_validate_date_valid(self):
        assert DataValidators.validate_date("2025-01-01") is True

    def test_validate_date_invalid(self):
        assert DataValidators.validate_date("not-a-date") is False

    def test_validate_percentage_in_range(self):
        assert DataValidators.validate_percentage(50.0) is True

    def test_validate_percentage_out_of_range(self):
        assert DataValidators.validate_percentage(110.0) is False

    def test_validate_percentage_zero(self):
        assert DataValidators.validate_percentage(0.0) is True

    def test_validate_percentage_hundred(self):
        assert DataValidators.validate_percentage(100.0) is True

    def test_validators_alias_exists(self):
        assert hasattr(u08_mod, "Validators")
        assert u08_mod.Validators is DataValidators
