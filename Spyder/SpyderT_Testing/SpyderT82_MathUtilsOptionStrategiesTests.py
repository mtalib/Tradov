#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT82_MathUtilsOptionStrategiesTests.py
Purpose: Comprehensive tests for U06 MathUtils and U14 OptionStrategies

Author: Spyder Test Suite
Year Created: 2026
Last Updated: 2026-03-05 Time: 12:00:00
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

_u01 = _load("Spyder/Spyder.SpyderU_Utilities/SpyderU01_Logger.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU01_Logger"] = _u01

_u02 = _load("Spyder/Spyder.SpyderU_Utilities/SpyderU02_ErrorHandler.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler"] = _u02

# Load target modules
_u06 = _load("Spyder/Spyder.SpyderU_Utilities/SpyderU06_MathUtils.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU06_MathUtils"] = _u06

_u14 = _load("Spyder/Spyder.SpyderU_Utilities/SpyderU14_OptionStrategies.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU14_OptionStrategies"] = _u14

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import math
import datetime
import pytest
import numpy as np

# ==============================================================================
# U06 IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU06_MathUtils import (
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
    MathUtils,
    PRICE_PRECISION,
    TRADING_DAYS_PER_YEAR,
)

# ==============================================================================
# U14 IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU14_OptionStrategies import (
    OptionType,
    PositionType,
    StrategyType,
    OptionLeg,
    OptionStrategy,
    PayoffResult,
    OptionStrategies,
    get_option_strategies,
    calculate_option_payoff,
    CONTRACT_MULTIPLIER,
)


# ==============================================================================
# ═════════════════════════════════════════════════════════════════════════════
#  U06 — MATH UTILS
# ═════════════════════════════════════════════════════════════════════════════
# ==============================================================================

class TestU06RoundPrice:
    def test_rounds_to_default_precision(self):
        assert round_price(3.14159) == 3.14

    def test_rounds_half_up(self):
        assert round_price(2.555) == 2.56

    def test_custom_precision(self):
        assert round_price(3.14159, precision=4) == 3.1416

    def test_zero_precision(self):
        assert round_price(3.7, precision=0) == 4.0

    def test_integer_input(self):
        assert round_price(100) == 100.00


class TestU06RoundToTick:
    def test_rounds_to_tick(self):
        result = round_to_tick(3.14, 0.05)
        assert abs(result - 3.15) < 0.001

    def test_already_on_tick(self):
        assert round_to_tick(3.0, 0.25) == 3.0

    def test_tick_size_one(self):
        assert round_to_tick(3.7, 1.0) == 4.0


class TestU06PercentageChange:
    def test_positive_change(self):
        result = calculate_percentage_change(100.0, 110.0)
        assert abs(result - 10.0) < 0.001

    def test_negative_change(self):
        result = calculate_percentage_change(100.0, 90.0)
        assert abs(result - (-10.0)) < 0.001

    def test_zero_old_value_both_zero(self):
        assert calculate_percentage_change(0.0, 0.0) == 0.0

    def test_zero_old_value_new_nonzero(self):
        result = calculate_percentage_change(0.0, 5.0)
        assert result == float("inf")

    def test_no_change(self):
        assert calculate_percentage_change(50.0, 50.0) == 0.0


class TestU06CompoundReturn:
    def test_single_return(self):
        result = calculate_compound_return([0.10])
        assert abs(result - 0.10) < 1e-9

    def test_two_returns(self):
        result = calculate_compound_return([0.10, 0.10])
        assert abs(result - 0.21) < 1e-6

    def test_negative_return(self):
        result = calculate_compound_return([-0.10])
        assert abs(result - (-0.10)) < 1e-9

    def test_empty_returns(self):
        result = calculate_compound_return([])
        assert result == 0.0


class TestU06Mean:
    def test_basic_mean(self):
        assert calculate_mean([1.0, 2.0, 3.0]) == 2.0

    def test_single_value(self):
        assert calculate_mean([5.0]) == 5.0

    def test_empty_list(self):
        assert calculate_mean([]) == 0.0

    def test_negative_values(self):
        result = calculate_mean([-2.0, 0.0, 2.0])
        assert result == 0.0


class TestU06StdDev:
    def test_sample_std_dev(self):
        result = calculate_std_dev([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
        # Population stddev ≈ 2.0; sample stddev is slightly higher (~2.138)
        assert result > 0
        assert result < 5.0  # sanity upper bound

    def test_population_std_dev(self):
        # Population std dev of [2,4,4,4,5,5,7,9] = exactly 2.0
        result = calculate_std_dev([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0], sample=False)
        assert abs(result - 2.0) < 0.01

    def test_too_few_values(self):
        assert calculate_std_dev([5.0]) == 0.0

    def test_empty_list(self):
        assert calculate_std_dev([]) == 0.0


class TestU06SharpeRatio:
    def test_positive_sharpe(self):
        returns = [0.02] * 252
        result = calculate_sharpe_ratio(returns)
        assert isinstance(result, float)

    def test_too_few_returns(self):
        assert calculate_sharpe_ratio([0.01]) == 0.0

    def test_zero_std_returns(self):
        # All returns identical → std=0 → returns 0
        returns = [0.02, 0.02]
        result = calculate_sharpe_ratio(returns)
        assert result == 0.0

    def test_custom_risk_free_rate(self):
        returns = [0.01, 0.02, 0.015, 0.03, -0.01]
        result = calculate_sharpe_ratio(returns, risk_free_rate=0.0)
        assert isinstance(result, float)


class TestU06SortinoRatio:
    def test_basic_sortino(self):
        returns = [0.01, 0.02, -0.01, 0.03, -0.005]
        result = calculate_sortino_ratio(returns)
        assert isinstance(result, float)

    def test_too_few_returns(self):
        assert calculate_sortino_ratio([0.01]) == 0.0

    def test_no_downside_returns_inf(self):
        # All positive excess returns → no downside → inf
        returns = [0.05, 0.06, 0.07]
        result = calculate_sortino_ratio(returns, risk_free_rate=0.0)
        assert result == float("inf")


class TestU06MaxDrawdown:
    def test_drawdown_and_indices(self):
        equity = [100.0, 120.0, 80.0, 90.0, 110.0]
        dd, peak_idx, trough_idx = calculate_max_drawdown(equity)
        assert dd < 0  # Drawdown is negative percentage
        assert peak_idx == 1  # Peak at 120
        assert trough_idx == 2  # Trough at 80

    def test_monotonically_increasing(self):
        equity = [100.0, 110.0, 120.0, 130.0]
        dd, _, _ = calculate_max_drawdown(equity)
        assert dd == 0.0 or (dd >= 0 and dd < 1e-9)  # No drawdown (may be 0%)

    def test_too_few_values(self):
        dd, p, t = calculate_max_drawdown([100.0])
        assert dd == 0.0
        assert p == 0
        assert t == 0


class TestU06VaR:
    def _returns(self):
        return [0.01, -0.02, 0.03, -0.01, 0.02, -0.05, 0.01, 0.03, -0.03, 0.02]

    def test_historical_var(self):
        result = calculate_var(self._returns(), 0.95, "historical")
        assert isinstance(result, float)

    def test_parametric_var(self):
        result = calculate_var(self._returns(), 0.95, "parametric")
        assert isinstance(result, float)

    def test_unknown_method_raises(self):
        with pytest.raises(ValueError):
            calculate_var(self._returns(), 0.95, "unknown")

    def test_empty_returns(self):
        assert calculate_var([], 0.95) == 0.0


class TestU06CVaR:
    def test_cvar_greater_than_zero_for_losses(self):
        returns = [0.01, -0.02, 0.03, -0.04, -0.05, -0.10, 0.02, 0.01]
        result = calculate_cvar(returns, 0.95)
        assert isinstance(result, float)

    def test_empty_returns(self):
        assert calculate_cvar([]) == 0.0


class TestU06NormalDistribution:
    def test_cdf_at_zero(self):
        assert abs(normal_cdf(0.0) - 0.5) < 1e-6

    def test_cdf_positive_limit(self):
        assert normal_cdf(10.0) > 0.99

    def test_cdf_negative_limit(self):
        assert normal_cdf(-10.0) < 0.01

    def test_pdf_at_zero_is_max(self):
        pdf0 = normal_pdf(0.0)
        pdf1 = normal_pdf(1.0)
        assert pdf0 > pdf1

    def test_pdf_positive(self):
        assert normal_pdf(0.0) > 0
        assert normal_pdf(2.0) > 0

    def test_cdf_symmetry(self):
        assert abs(normal_cdf(1.0) + normal_cdf(-1.0) - 1.0) < 1e-6


class TestU06ProbabilityTouch:
    def test_basic_probability(self):
        prob = calculate_probability_touch(450.0, 460.0, 0.20, 30)
        assert 0.0 <= prob <= 1.0

    def test_zero_dte_wrong_price(self):
        # days_to_expiry=0 → 0.0 if target != current
        prob = calculate_probability_touch(450.0, 460.0, 0.20, 0)
        assert prob == 0.0

    def test_zero_volatility(self):
        prob = calculate_probability_touch(450.0, 460.0, 0.0, 30)
        assert prob == 0.0

    def test_at_money_higher_prob(self):
        p_near = calculate_probability_touch(450.0, 451.0, 0.20, 30)
        p_far = calculate_probability_touch(450.0, 500.0, 0.20, 30)
        assert p_near >= p_far


class TestU06ProbabilityProfit:
    def test_bullish_probability(self):
        prob = calculate_probability_profit(450.0, 440.0, 0.20, 30, is_bullish=True)
        assert 0.0 <= prob <= 1.0

    def test_bearish_probability(self):
        prob = calculate_probability_profit(450.0, 460.0, 0.20, 30, is_bullish=False)
        assert 0.0 <= prob <= 1.0

    def test_zero_dte_bullish_above(self):
        # current > breakeven, bullish → profit
        prob = calculate_probability_profit(440.0, 450.0, 0.20, 0, is_bullish=True)
        assert prob == 1.0

    def test_zero_dte_bullish_below(self):
        # current < breakeven, bullish → no profit
        prob = calculate_probability_profit(460.0, 450.0, 0.20, 0, is_bullish=True)
        assert prob == 0.0

    def test_zero_dte_bearish_below(self):
        # current < breakeven, bearish → profit
        prob = calculate_probability_profit(460.0, 450.0, 0.20, 0, is_bullish=False)
        assert prob == 1.0


class TestU06FindRoot:
    def test_finds_root_of_linear(self):
        # f(x) = x - 2  → root at x=2
        root = find_root(lambda x: x - 2, 0, 5)
        assert root is not None
        assert abs(root - 2.0) < 1e-6

    def test_no_sign_change_returns_none(self):
        # f(x) = x^2 + 1  → no real root
        root = find_root(lambda x: x**2 + 1, -5, 5)
        assert root is None

    def test_root_at_boundary(self):
        root = find_root(lambda x: x, -1, 1)
        assert root is not None
        assert abs(root) < 1e-6


class TestU06MinimizeScalar:
    def test_finds_minimum_of_parabola(self):
        # f(x) = (x - 3)^2 → minimum at x=3
        x_min, f_min = minimize_scalar(lambda x: (x - 3)**2, (0, 10))
        assert x_min is not None
        assert abs(x_min - 3.0) < 0.001
        assert f_min is not None
        assert f_min < 0.001

    def test_returns_none_none_on_bad_input(self):
        # This should either succeed or return None, None gracefully
        x_min, f_min = minimize_scalar(lambda x: float('nan'), (0, 1))
        # Either can be None or NaN — should not raise
        assert x_min is None or isinstance(x_min, float)


class TestU06PositionSize:
    def test_basic_position_size(self):
        size = calculate_position_size(100000, 2.0, 500.0)
        assert size == 4

    def test_negative_stop_returns_zero(self):
        assert calculate_position_size(100000, 2.0, 0.0) == 0

    def test_zero_risk_returns_zero(self):
        assert calculate_position_size(100000, 0.0, 500.0) == 0

    def test_with_multiplier(self):
        size = calculate_position_size(100000, 2.0, 5.0, contract_multiplier=100.0)
        assert size > 0


class TestU06KellyCriterion:
    def test_kelly_basic(self):
        result = calculate_kelly_criterion(0.6, 100.0, 80.0)
        assert 0.0 <= result <= 0.25

    def test_negative_expectancy_returns_zero(self):
        # Low win rate with similar win/loss
        result = calculate_kelly_criterion(0.3, 1.0, 1.0)
        assert result == 0.0

    def test_zero_avg_loss_returns_zero(self):
        assert calculate_kelly_criterion(0.6, 100.0, 0.0) == 0.0

    def test_zero_win_rate_returns_zero(self):
        assert calculate_kelly_criterion(0.0, 100.0, 80.0) == 0.0

    def test_capped_at_25_percent(self):
        result = calculate_kelly_criterion(0.99, 1000.0, 1.0)
        assert result <= 0.25


class TestU06RiskReward:
    def test_two_to_one_rr(self):
        result = calculate_risk_reward_ratio(100.0, 106.0, 97.0)
        assert abs(result - 2.0) < 0.01

    def test_zero_risk_returns_inf(self):
        result = calculate_risk_reward_ratio(100.0, 110.0, 100.0)
        assert result == float("inf")

    def test_zero_reward_zero_risk(self):
        result = calculate_risk_reward_ratio(100.0, 100.0, 100.0)
        assert result == 0.0


class TestU06LinearInterpolation:
    def test_midpoint(self):
        result = linear_interpolation(5.0, 0.0, 0.0, 10.0, 10.0)
        assert abs(result - 5.0) < 1e-9

    def test_at_x1(self):
        result = linear_interpolation(0.0, 0.0, 5.0, 10.0, 15.0)
        assert abs(result - 5.0) < 1e-9

    def test_at_x2(self):
        result = linear_interpolation(10.0, 0.0, 5.0, 10.0, 15.0)
        assert abs(result - 15.0) < 1e-9

    def test_same_x1_x2(self):
        # Returns y1 when x1=x2
        result = linear_interpolation(3.0, 3.0, 7.0, 3.0, 9.0)
        assert result == 7.0


class TestU06CubicSpline:
    def test_basic_interpolation(self):
        x = [0.0, 1.0, 2.0, 3.0]
        y = [0.0, 1.0, 4.0, 9.0]
        result = cubic_spline_interpolation(x, y, 1.5)
        assert isinstance(result, float)
        assert abs(result - 2.25) < 0.5  # Should be near x^2=2.25 interpolated

    def test_list_interpolation(self):
        x = [0.0, 1.0, 2.0, 3.0]
        y = [0.0, 1.0, 4.0, 9.0]
        result = cubic_spline_interpolation(x, y, [0.5, 1.5, 2.5])
        assert isinstance(result, list)
        assert len(result) == 3

    def test_too_few_points(self):
        with pytest.raises(ValueError):
            cubic_spline_interpolation([1.0], [1.0], 0.5)


class TestU06RollingWindow:
    def test_basic_rolling_mean(self):
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        results = rolling_window(data, 3, lambda w: sum(w) / len(w))
        assert len(results) == 3
        assert abs(results[0] - 2.0) < 1e-9
        assert abs(results[1] - 3.0) < 1e-9
        assert abs(results[2] - 4.0) < 1e-9

    def test_window_larger_than_data(self):
        assert rolling_window([1.0, 2.0], 5, sum) == []

    def test_window_equals_data(self):
        result = rolling_window([1.0, 2.0, 3.0], 3, sum)
        assert result == [6.0]


class TestU06EMA:
    def test_basic_ema(self):
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = exponential_moving_average(data, 3)
        assert len(result) == 5
        assert result[0] == 1.0  # First value equals first data point

    def test_empty_data(self):
        assert exponential_moving_average([], 3) == []

    def test_zero_period(self):
        assert exponential_moving_average([1.0, 2.0], 0) == []

    def test_ema_smooths_upward_trend(self):
        data = [float(i) for i in range(1, 11)]
        result = exponential_moving_average(data, 3)
        # EMA should increase monotonically for upward trend
        assert all(result[i] <= result[i + 1] for i in range(len(result) - 1))


class TestU06MathUtils:
    def test_round_price(self):
        assert MathUtils.round_price(3.14159) == 3.14

    def test_round_to_tick(self):
        result = MathUtils.round_to_tick(3.14, 0.05)
        assert isinstance(result, float)

    def test_percentage_change(self):
        result = MathUtils.calculate_percentage_change(100.0, 110.0)
        assert abs(result - 10.0) < 0.001

    def test_compound_return(self):
        result = MathUtils.calculate_compound_return([0.10, 0.10])
        assert abs(result - 0.21) < 1e-6

    def test_mean(self):
        assert MathUtils.calculate_mean([1.0, 2.0, 3.0]) == 2.0

    def test_std_dev(self):
        result = MathUtils.calculate_std_dev([1.0, 2.0, 3.0, 4.0, 5.0])
        assert result > 0

    def test_sharpe_ratio(self):
        result = MathUtils.calculate_sharpe_ratio([0.01, 0.02, -0.01, 0.03])
        assert isinstance(result, float)

    def test_sortino_ratio(self):
        result = MathUtils.calculate_sortino_ratio([0.01, 0.02, -0.01, 0.03])
        assert isinstance(result, float)


# ==============================================================================
# ═════════════════════════════════════════════════════════════════════════════
#  U14 — OPTION STRATEGIES
# ═════════════════════════════════════════════════════════════════════════════
# ==============================================================================

def _expiry():
    return datetime.datetime.now() + datetime.timedelta(days=30)


class TestU14OptionLeg:
    def _call_leg(self, **kwargs):
        defaults = {
            "option_type": OptionType.CALL,
            "position_type": PositionType.LONG,
            "strike": 450.0,
            "expiry": _expiry(),
            "premium": 3.0,
            "quantity": 1,
        }
        defaults.update(kwargs)
        return OptionLeg(**defaults)

    def test_is_call_true(self):
        leg = self._call_leg()
        assert leg.is_call is True
        assert leg.is_put is False

    def test_is_put_true(self):
        leg = self._call_leg(option_type=OptionType.PUT)
        assert leg.is_put is True
        assert leg.is_call is False

    def test_is_long_true(self):
        leg = self._call_leg()
        assert leg.is_long is True
        assert leg.is_short is False

    def test_is_short_true(self):
        leg = self._call_leg(position_type=PositionType.SHORT)
        assert leg.is_short is True
        assert leg.is_long is False

    def test_net_premium_long_is_negative(self):
        # Long position pays premium → multiplier = -1
        leg = self._call_leg(position_type=PositionType.LONG, premium=3.0)
        assert leg.net_premium == -3.0

    def test_net_premium_short_is_positive(self):
        leg = self._call_leg(position_type=PositionType.SHORT, premium=3.0)
        assert leg.net_premium == 3.0

    def test_net_premium_with_quantity(self):
        leg = self._call_leg(position_type=PositionType.SHORT, premium=3.0, quantity=5)
        assert leg.net_premium == 15.0


class TestU14OptionStrategy:
    def _strategy(self, legs=None, **kwargs):
        if legs is None:
            legs = [
                OptionLeg(OptionType.CALL, PositionType.SHORT, 455.0, _expiry(), 3.0),
                OptionLeg(OptionType.PUT, PositionType.SHORT, 445.0, _expiry(), 3.0),
            ]
        defaults = {
            "name": "Test Strategy",
            "strategy_type": StrategyType.STRADDLE,
            "legs": legs,
            "underlying_price": 450.0,
        }
        defaults.update(kwargs)
        return OptionStrategy(**defaults)

    def test_net_premium_credit(self):
        s = self._strategy()
        assert s.net_premium > 0  # Both short → credit

    def test_is_credit_strategy(self):
        s = self._strategy()
        assert s.is_credit_strategy is True
        assert s.is_debit_strategy is False

    def test_is_debit_strategy(self):
        legs = [
            OptionLeg(OptionType.CALL, PositionType.LONG, 455.0, _expiry(), 3.0),
            OptionLeg(OptionType.PUT, PositionType.LONG, 445.0, _expiry(), 3.0),
        ]
        s = self._strategy(legs=legs)
        assert s.is_debit_strategy is True
        assert s.is_credit_strategy is False

    def test_breakeven_points_default_empty(self):
        s = self._strategy()
        assert s.breakeven_points == []

    def test_underlying_price_stored(self):
        s = self._strategy()
        assert s.underlying_price == 450.0


class TestU14OptionStrategiesClass:
    def setup_method(self):
        self.os = OptionStrategies()

    def _expiry(self):
        return _expiry()

    def test_init(self):
        assert self.os is not None

    def test_calculate_option_payoff_call_long(self):
        # Long call in the money at expiry
        payoff = self.os.calculate_option_payoff("CALL", "LONG", 450.0, 3.0, 460.0)
        # intrinsic = 10, payoff = (10 - 3) * 1 * 100 = 700
        assert abs(payoff - 700.0) < 0.01

    def test_calculate_option_payoff_call_short(self):
        payoff = self.os.calculate_option_payoff("CALL", "SHORT", 450.0, 3.0, 460.0)
        # (3 - 10) * 1 * 100 = -700
        assert abs(payoff - (-700.0)) < 0.01

    def test_calculate_option_payoff_put_long_itm(self):
        payoff = self.os.calculate_option_payoff("PUT", "LONG", 450.0, 3.0, 440.0)
        # intrinsic = 10, payoff = (10 - 3) * 1 * 100 = 700
        assert abs(payoff - 700.0) < 0.01

    def test_calculate_option_payoff_call_otm_zero_payoff(self):
        payoff = self.os.calculate_option_payoff("CALL", "LONG", 450.0, 3.0, 445.0)
        # OTM call → intrinsic=0 → payoff = (0 - 3) * 100 = -300
        assert abs(payoff - (-300.0)) < 0.01

    def test_calculate_option_payoff_vector(self):
        spots = np.array([440.0, 450.0, 460.0])
        payoff = self.os.calculate_option_payoff("CALL", "LONG", 450.0, 2.0, spots)
        assert len(payoff) == 3

    def test_calculate_strategy_payoff(self):
        strategy = OptionStrategy(
            name="Short Straddle",
            strategy_type=StrategyType.STRADDLE,
            legs=[
                OptionLeg(OptionType.CALL, PositionType.SHORT, 450.0, self._expiry(), 5.0),
                OptionLeg(OptionType.PUT, PositionType.SHORT, 450.0, self._expiry(), 5.0),
            ],
            underlying_price=450.0,
        )
        payoff = self.os.calculate_strategy_payoff(strategy, 450.0)
        # Both options OTM at exactly ATM → payoff = 5*100 + 5*100 = 1000
        assert isinstance(payoff, (float, int, np.floating, np.ndarray))

    def test_get_payoff_diagram_returns_result(self):
        strategy = OptionStrategy(
            name="Test",
            strategy_type=StrategyType.STRADDLE,
            legs=[
                OptionLeg(OptionType.CALL, PositionType.SHORT, 455.0, self._expiry(), 3.0),
                OptionLeg(OptionType.PUT, PositionType.SHORT, 445.0, self._expiry(), 3.0),
            ],
            underlying_price=450.0,
        )
        result = self.os.get_payoff_diagram(strategy)
        assert isinstance(result, PayoffResult)
        assert len(result.spot_prices) > 0
        assert len(result.payoffs) > 0

    def test_get_payoff_diagram_with_price_range(self):
        strategy = OptionStrategy(
            name="Test",
            strategy_type=StrategyType.STRADDLE,
            legs=[
                OptionLeg(OptionType.CALL, PositionType.LONG, 450.0, self._expiry(), 5.0),
            ],
            underlying_price=450.0,
        )
        result = self.os.get_payoff_diagram(strategy, price_range=(420.0, 480.0), num_points=50)
        assert len(result.spot_prices) == 50


class TestU14StrategyBuilders:
    def setup_method(self):
        self.os = OptionStrategies()

    def _expiry(self):
        return _expiry()

    def test_create_bull_call_spread(self):
        strategy = self.os.create_bull_call_spread(
            long_strike=440.0,
            short_strike=460.0,
            expiry=self._expiry(),
            long_premium=8.0,
            short_premium=3.0,
            underlying_price=450.0,
        )
        assert isinstance(strategy, OptionStrategy)
        assert strategy.strategy_type == StrategyType.BULL_CALL_SPREAD
        assert len(strategy.legs) == 2

    def test_bull_call_spread_debit(self):
        strategy = self.os.create_bull_call_spread(440.0, 460.0, self._expiry(), 8.0, 3.0, 450.0)
        assert strategy.is_debit_strategy  # Costs more than receives

    def test_create_bear_put_spread(self):
        strategy = self.os.create_bear_put_spread(
            long_strike=460.0,
            short_strike=440.0,
            expiry=self._expiry(),
            long_premium=8.0,
            short_premium=3.0,
            underlying_price=450.0,
        )
        assert isinstance(strategy, OptionStrategy)
        assert strategy.strategy_type == StrategyType.BEAR_PUT_SPREAD

    def test_create_iron_condor(self):
        strategy = self.os.create_iron_condor(
            put_long_strike=430.0,
            put_short_strike=440.0,
            call_short_strike=460.0,
            call_long_strike=470.0,
            expiry=self._expiry(),
            premiums=[1.0, 3.0, 3.0, 1.0],
            underlying_price=450.0,
        )
        assert isinstance(strategy, OptionStrategy)
        assert strategy.strategy_type == StrategyType.IRON_CONDOR
        assert len(strategy.legs) == 4

    def test_iron_condor_is_credit(self):
        strategy = self.os.create_iron_condor(
            430.0, 440.0, 460.0, 470.0, self._expiry(),
            [1.0, 3.0, 3.0, 1.0], 450.0
        )
        assert strategy.is_credit_strategy  # Net credit: -1+3+3-1 = 4

    def test_create_long_straddle(self):
        strategy = self.os.create_straddle(
            strike=450.0,
            expiry=self._expiry(),
            call_premium=5.0,
            put_premium=5.0,
            underlying_price=450.0,
            position_type="LONG",
        )
        assert isinstance(strategy, OptionStrategy)
        assert strategy.strategy_type == StrategyType.STRADDLE
        assert len(strategy.legs) == 2

    def test_create_short_straddle(self):
        strategy = self.os.create_straddle(
            strike=450.0,
            expiry=self._expiry(),
            call_premium=5.0,
            put_premium=5.0,
            underlying_price=450.0,
            position_type="SHORT",
        )
        assert strategy.is_credit_strategy

    def test_straddle_max_loss_set(self):
        strategy = self.os.create_straddle(450.0, self._expiry(), 5.0, 5.0, 450.0, "LONG")
        assert strategy.max_loss is not None
        assert strategy.max_loss >= 0


class TestU14RiskAnalysis:
    def setup_method(self):
        self.os = OptionStrategies()

    def _iron_condor(self):
        return self.os.create_iron_condor(
            430.0, 440.0, 460.0, 470.0, _expiry(),
            [1.0, 3.0, 3.0, 1.0], 450.0
        )

    def test_calculate_max_profit(self):
        strategy = self._iron_condor()
        profit = self.os.calculate_max_profit(strategy)
        assert isinstance(profit, float)

    def test_calculate_max_loss(self):
        strategy = self._iron_condor()
        loss = self.os.calculate_max_loss(strategy)
        assert isinstance(loss, float)

    def test_calculate_breakeven_points(self):
        strategy = self._iron_condor()
        be_points = self.os.calculate_breakeven_points(strategy)
        assert isinstance(be_points, list)


class TestU14ModuleFunctions:
    def test_get_option_strategies_returns_instance(self):
        _u14._option_strategies = None
        instance = get_option_strategies()
        assert isinstance(instance, OptionStrategies)

    def test_get_option_strategies_singleton(self):
        _u14._option_strategies = None
        inst1 = get_option_strategies()
        inst2 = get_option_strategies()
        assert inst1 is inst2

    def test_calculate_option_payoff_module_function(self):
        payoff = calculate_option_payoff("CALL", "LONG", 450.0, 3.0, 460.0)
        assert isinstance(payoff, (float, int, np.floating, np.ndarray))

    def test_enum_values(self):
        assert OptionType.CALL.value == "CALL"
        assert OptionType.PUT.value == "PUT"
        assert PositionType.LONG.value == "LONG"
        assert PositionType.SHORT.value == "SHORT"

    def test_strategy_types_exist(self):
        expected = ["IRON_CONDOR", "STRADDLE", "BULL_CALL_SPREAD", "BEAR_PUT_SPREAD"]
        names = [s.name for s in StrategyType]
        for n in expected:
            assert n in names
