#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT64_OptionStrategyPerformanceTests.py
Purpose: Tests for U14 OptionStrategies + U15 PerformanceMetrics

Author: Spyder Dev
Year Created: 2025
Last Updated: 2025-01-01 Time: 00:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import importlib.util
import math
import os
import sys
import types
from datetime import datetime, timedelta
from typing import List
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

# ==============================================================================
# BOOTSTRAP
# ==============================================================================
_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _load(rel_path: str):
    abs_path = os.path.join(_ROOT, rel_path)
    module_name = rel_path.replace("/", ".").replace(".py", "")
    spec = importlib.util.spec_from_file_location(module_name, abs_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ensure_pkg(name: str):
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)


_ensure_pkg("Spyder")
_ensure_pkg("Spyder.SpyderU_Utilities")

_u01 = _load("Spyder/SpyderU_Utilities/SpyderU01_Logger.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU01_Logger"] = _u01

_u02 = _load("Spyder/SpyderU_Utilities/SpyderU02_ErrorHandler.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler"] = _u02

_u14 = _load("Spyder/SpyderU_Utilities/SpyderU14_OptionStrategies.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU14_OptionStrategies"] = _u14

_u15 = _load("Spyder/SpyderU_Utilities/SpyderU15_PerformanceMetrics.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU15_PerformanceMetrics"] = _u15

# ==============================================================================
# U14 NAMES
# ==============================================================================
OptionType = _u14.OptionType
PositionType = _u14.PositionType
StrategyType = _u14.StrategyType
OptionLeg = _u14.OptionLeg
OptionStrategy = _u14.OptionStrategy
PayoffResult = _u14.PayoffResult
OptionStrategies = _u14.OptionStrategies
CONTRACT_MULTIPLIER = _u14.CONTRACT_MULTIPLIER

# ==============================================================================
# U15 NAMES
# ==============================================================================
PerformanceRating = _u15.PerformanceRating
MetricType = _u15.MetricType
PerformanceReport = _u15.PerformanceReport
DrawdownInfo = _u15.DrawdownInfo
PerformanceCalculator = _u15.PerformanceCalculator
TRADING_DAYS_PER_YEAR = _u15.TRADING_DAYS_PER_YEAR
MIN_PERIODS_FOR_CALCULATION = _u15.MIN_PERIODS_FOR_CALCULATION

# ==============================================================================
# SHARED FIXTURES / HELPERS
# ==============================================================================
EXPIRY = datetime.now() + timedelta(days=30)
UNDERLYING = 460.0


def _make_returns(n: int = 100, mean: float = 0.002, std: float = 0.015) -> pd.Series:
    """Generate a reproducible return series."""
    rng = np.random.default_rng(seed=42)
    return pd.Series(rng.normal(mean, std, n))


GOOD_RETURNS = _make_returns(100, 0.003, 0.01)    # consistently positive
BAD_RETURNS = _make_returns(100, -0.003, 0.01)    # consistently negative
MIXED_RETURNS = pd.Series([0.02, -0.01, 0.03, -0.005, 0.015, -0.008] * 20)  # 120 observations
SMALL_RETURNS = pd.Series([0.01, -0.005, 0.02])  # fewer than MIN_PERIODS_FOR_CALCULATION
EMPTY_RETURNS = pd.Series([], dtype=float)


# ==============================================================================
# U14 — ENUM TESTS
# ==============================================================================


class TestOptionTypeEnum:
    def test_call_value(self):
        assert OptionType.CALL.value == "CALL"

    def test_put_value(self):
        assert OptionType.PUT.value == "PUT"

    def test_two_members(self):
        assert len(OptionType) == 2


class TestPositionTypeEnum:
    def test_long_value(self):
        assert PositionType.LONG.value == "LONG"

    def test_short_value(self):
        assert PositionType.SHORT.value == "SHORT"

    def test_two_members(self):
        assert len(PositionType) == 2


class TestStrategyTypeEnum:
    def test_iron_condor(self):
        assert StrategyType.IRON_CONDOR.value == "iron_condor"

    def test_bull_call_spread(self):
        assert StrategyType.BULL_CALL_SPREAD.value == "bull_call_spread"

    def test_bear_put_spread(self):
        assert StrategyType.BEAR_PUT_SPREAD.value == "bear_put_spread"

    def test_straddle(self):
        assert StrategyType.STRADDLE.value == "straddle"

    def test_strangle(self):
        assert StrategyType.STRANGLE.value == "strangle"

    def test_iron_butterfly(self):
        assert StrategyType.IRON_BUTTERFLY.value == "iron_butterfly"

    def test_has_eleven_members(self):
        assert len(StrategyType) == 11


# ==============================================================================
# U14 — OptionLeg dataclass
# ==============================================================================


class TestOptionLegDataclass:
    def _make_call_leg(self, position: PositionType = PositionType.LONG) -> OptionLeg:
        return OptionLeg(
            option_type=OptionType.CALL,
            position_type=position,
            strike=450.0,
            expiry=EXPIRY,
            premium=5.0,
            quantity=1,
        )

    def _make_put_leg(self, position: PositionType = PositionType.LONG) -> OptionLeg:
        return OptionLeg(
            option_type=OptionType.PUT,
            position_type=position,
            strike=450.0,
            expiry=EXPIRY,
            premium=5.0,
            quantity=1,
        )

    def test_is_call_true_for_call(self):
        leg = self._make_call_leg()
        assert leg.is_call is True

    def test_is_call_false_for_put(self):
        leg = self._make_put_leg()
        assert leg.is_call is False

    def test_is_put_true_for_put(self):
        leg = self._make_put_leg()
        assert leg.is_put is True

    def test_is_put_false_for_call(self):
        leg = self._make_call_leg()
        assert leg.is_put is False

    def test_is_long_true_for_long(self):
        leg = self._make_call_leg(PositionType.LONG)
        assert leg.is_long is True
        assert leg.is_short is False

    def test_is_short_true_for_short(self):
        leg = self._make_call_leg(PositionType.SHORT)
        assert leg.is_short is True
        assert leg.is_long is False

    def test_net_premium_long_is_negative(self):
        # Long pays premium → net_premium = -1 * premium * qty
        leg = self._make_call_leg(PositionType.LONG)
        assert leg.net_premium == -5.0

    def test_net_premium_short_is_positive(self):
        # Short receives premium → net_premium = +1 * premium * qty
        leg = self._make_call_leg(PositionType.SHORT)
        assert leg.net_premium == 5.0

    def test_net_premium_scales_with_quantity(self):
        leg = OptionLeg(
            option_type=OptionType.CALL,
            position_type=PositionType.SHORT,
            strike=450.0,
            expiry=EXPIRY,
            premium=5.0,
            quantity=3,
        )
        assert leg.net_premium == 15.0  # 3 contracts


# ==============================================================================
# U14 — OptionStrategy dataclass
# ==============================================================================


class TestOptionStrategyDataclass:
    def _make_spread(self) -> OptionStrategy:
        """Debit spread (net premium < 0)"""
        return OptionStrategy(
            name="Test Spread",
            strategy_type=StrategyType.BULL_CALL_SPREAD,
            legs=[
                OptionLeg(OptionType.CALL, PositionType.LONG, 440.0, EXPIRY, 8.0),
                OptionLeg(OptionType.CALL, PositionType.SHORT, 450.0, EXPIRY, 3.0),
            ],
            underlying_price=UNDERLYING,
        )

    def _make_credit_spread(self) -> OptionStrategy:
        """Credit spread (net premium > 0)"""
        return OptionStrategy(
            name="Credit Spread",
            strategy_type=StrategyType.BEAR_PUT_SPREAD,
            legs=[
                OptionLeg(OptionType.PUT, PositionType.SHORT, 450.0, EXPIRY, 8.0),
                OptionLeg(OptionType.PUT, PositionType.LONG, 440.0, EXPIRY, 3.0),
            ],
            underlying_price=UNDERLYING,
        )

    def test_net_premium_debit(self):
        s = self._make_spread()
        # Long call net = -8, Short call net = +3
        assert s.net_premium == pytest.approx(-5.0)

    def test_net_premium_credit(self):
        s = self._make_credit_spread()
        # Short put net = +8, Long put net = -3
        assert s.net_premium == pytest.approx(5.0)

    def test_is_debit_strategy(self):
        s = self._make_spread()
        assert s.is_debit_strategy is True
        assert s.is_credit_strategy is False

    def test_is_credit_strategy(self):
        s = self._make_credit_spread()
        assert s.is_credit_strategy is True
        assert s.is_debit_strategy is False


# ==============================================================================
# U14 — OptionStrategies class construction
# ==============================================================================


class TestOptionStrategiesConstruction:
    def test_creates_successfully(self):
        os_ = OptionStrategies()
        assert os_ is not None

    def test_has_logger(self):
        os_ = OptionStrategies()
        assert hasattr(os_, "logger")


# ==============================================================================
# U14 — calculate_option_payoff
# ==============================================================================


class TestCalculateOptionPayoff:
    def setup_method(self):
        self.os_ = OptionStrategies()

    def test_long_call_itm(self):
        # Spot 460, strike 450, premium 5 → (10-5)*1*100 = 500
        payoff = self.os_.calculate_option_payoff("CALL", "LONG", 450.0, 5.0, 460.0, 1)
        assert payoff == pytest.approx(500.0)

    def test_long_call_otm(self):
        # Spot 440, strike 450, premium 5 → (0-5)*1*100 = -500
        payoff = self.os_.calculate_option_payoff("CALL", "LONG", 450.0, 5.0, 440.0, 1)
        assert payoff == pytest.approx(-500.0)

    def test_long_call_atm(self):
        # Spot = Strike → intrinsic=0 → (0-5)*100 = -500
        payoff = self.os_.calculate_option_payoff("CALL", "LONG", 450.0, 5.0, 450.0, 1)
        assert payoff == pytest.approx(-500.0)

    def test_short_call_itm_loses_money(self):
        # Short call ITM: (5-10)*100 = -500
        payoff = self.os_.calculate_option_payoff("CALL", "SHORT", 450.0, 5.0, 460.0, 1)
        assert payoff == pytest.approx(-500.0)

    def test_short_call_otm_keeps_premium(self):
        # Short call OTM: (5-0)*100 = 500
        payoff = self.os_.calculate_option_payoff("CALL", "SHORT", 450.0, 5.0, 440.0, 1)
        assert payoff == pytest.approx(500.0)

    def test_long_put_itm(self):
        # Spot 440, strike 450, premium 5 → (10-5)*100 = 500
        payoff = self.os_.calculate_option_payoff("PUT", "LONG", 450.0, 5.0, 440.0, 1)
        assert payoff == pytest.approx(500.0)

    def test_long_put_otm(self):
        # Spot 460, strike 450, premium 5 → (0-5)*100 = -500
        payoff = self.os_.calculate_option_payoff("PUT", "LONG", 450.0, 5.0, 460.0, 1)
        assert payoff == pytest.approx(-500.0)

    def test_short_put_itm_loses_money(self):
        # Short put ITM (spot 440, strike 450, prem 5): (5-10)*100 = -500
        payoff = self.os_.calculate_option_payoff("PUT", "SHORT", 450.0, 5.0, 440.0, 1)
        assert payoff == pytest.approx(-500.0)

    def test_short_put_otm_keeps_premium(self):
        # Short put OTM (spot 460): (5-0)*100 = 500
        payoff = self.os_.calculate_option_payoff("PUT", "SHORT", 450.0, 5.0, 460.0, 1)
        assert payoff == pytest.approx(500.0)

    def test_quantity_multiplies_payoff(self):
        # 2 contracts: (10-5)*2*100 = 1000
        payoff = self.os_.calculate_option_payoff("CALL", "LONG", 450.0, 5.0, 460.0, 2)
        assert payoff == pytest.approx(1000.0)

    def test_vectorized_array_input(self):
        spots = np.array([440.0, 450.0, 460.0, 470.0])
        payoffs = self.os_.calculate_option_payoff("CALL", "LONG", 450.0, 5.0, spots, 1)
        assert isinstance(payoffs, np.ndarray)
        assert len(payoffs) == 4
        # At spot=440: OTM → -500; at spot=460: ITM → 500
        assert payoffs[0] == pytest.approx(-500.0)
        assert payoffs[2] == pytest.approx(500.0)

    def test_invalid_option_type_returns_zero(self):
        # Catches exception → returns 0.0
        result = self.os_.calculate_option_payoff("INVALID", "LONG", 450, 5, 460)
        assert result == 0.0


# ==============================================================================
# U14 — create_bull_call_spread
# ==============================================================================


class TestCreateBullCallSpread:
    def setup_method(self):
        self.os_ = OptionStrategies()

    def _make_spread(self) -> OptionStrategy:
        return self.os_.create_bull_call_spread(
            long_strike=440.0,
            short_strike=450.0,
            expiry=EXPIRY,
            long_premium=8.0,
            short_premium=3.0,
            underlying_price=UNDERLYING,
        )

    def test_returns_option_strategy(self):
        s = self._make_spread()
        assert isinstance(s, OptionStrategy)

    def test_strategy_type(self):
        s = self._make_spread()
        assert s.strategy_type == StrategyType.BULL_CALL_SPREAD

    def test_has_two_legs(self):
        s = self._make_spread()
        assert len(s.legs) == 2

    def test_both_legs_are_calls(self):
        s = self._make_spread()
        for leg in s.legs:
            assert leg.option_type == OptionType.CALL

    def test_is_debit_strategy(self):
        s = self._make_spread()
        assert s.is_debit_strategy is True

    def test_net_premium_is_negative(self):
        s = self._make_spread()
        # Long prem 8 – short prem 3 = net 5 debit → -5
        assert s.net_premium == pytest.approx(-5.0)

    def test_max_profit_is_set(self):
        s = self._make_spread()
        assert s.max_profit is not None

    def test_max_loss_is_set(self):
        s = self._make_spread()
        assert s.max_loss is not None


# ==============================================================================
# U14 — create_bear_put_spread
# ==============================================================================


class TestCreateBearPutSpread:
    def setup_method(self):
        self.os_ = OptionStrategies()

    def _make_spread(self) -> OptionStrategy:
        return self.os_.create_bear_put_spread(
            long_strike=450.0,
            short_strike=440.0,
            expiry=EXPIRY,
            long_premium=8.0,
            short_premium=3.0,
            underlying_price=UNDERLYING,
        )

    def test_returns_option_strategy(self):
        s = self._make_spread()
        assert isinstance(s, OptionStrategy)

    def test_strategy_type(self):
        s = self._make_spread()
        assert s.strategy_type == StrategyType.BEAR_PUT_SPREAD

    def test_has_two_legs(self):
        s = self._make_spread()
        assert len(s.legs) == 2

    def test_both_legs_are_puts(self):
        s = self._make_spread()
        for leg in s.legs:
            assert leg.option_type == OptionType.PUT

    def test_is_debit_strategy(self):
        s = self._make_spread()
        assert s.is_debit_strategy is True


# ==============================================================================
# U14 — create_iron_condor
# ==============================================================================


class TestCreateIronCondor:
    def setup_method(self):
        self.os_ = OptionStrategies()

    def _make_condor(self) -> OptionStrategy:
        return self.os_.create_iron_condor(
            put_long_strike=440.0,
            put_short_strike=450.0,
            call_short_strike=470.0,
            call_long_strike=480.0,
            expiry=EXPIRY,
            premiums=[2.0, 6.0, 6.0, 2.0],
            underlying_price=UNDERLYING,
        )

    def test_returns_option_strategy(self):
        ic = self._make_condor()
        assert isinstance(ic, OptionStrategy)

    def test_strategy_type(self):
        ic = self._make_condor()
        assert ic.strategy_type == StrategyType.IRON_CONDOR

    def test_has_four_legs(self):
        ic = self._make_condor()
        assert len(ic.legs) == 4

    def test_is_credit_strategy(self):
        ic = self._make_condor()
        # Net premium: -2+6+6-2 = 8 (credit)
        assert ic.is_credit_strategy is True

    def test_net_premium_positive(self):
        ic = self._make_condor()
        assert ic.net_premium == pytest.approx(8.0)

    def test_max_profit_set(self):
        ic = self._make_condor()
        assert ic.max_profit is not None

    def test_max_loss_set(self):
        ic = self._make_condor()
        assert ic.max_loss is not None


# ==============================================================================
# U14 — create_straddle
# ==============================================================================


class TestCreateStraddle:
    def setup_method(self):
        self.os_ = OptionStrategies()

    def _make_long_straddle(self) -> OptionStrategy:
        return self.os_.create_straddle(
            strike=460.0,
            expiry=EXPIRY,
            call_premium=8.0,
            put_premium=8.0,
            underlying_price=UNDERLYING,
            position_type="LONG",
        )

    def _make_short_straddle(self) -> OptionStrategy:
        return self.os_.create_straddle(
            strike=460.0,
            expiry=EXPIRY,
            call_premium=8.0,
            put_premium=8.0,
            underlying_price=UNDERLYING,
            position_type="SHORT",
        )

    def test_long_straddle_type(self):
        s = self._make_long_straddle()
        assert s.strategy_type == StrategyType.STRADDLE

    def test_has_two_legs(self):
        s = self._make_long_straddle()
        assert len(s.legs) == 2

    def test_long_straddle_has_call_and_put(self):
        s = self._make_long_straddle()
        types = {leg.option_type for leg in s.legs}
        assert OptionType.CALL in types
        assert OptionType.PUT in types

    def test_long_straddle_is_debit(self):
        s = self._make_long_straddle()
        assert s.is_debit_strategy is True

    def test_short_straddle_is_credit(self):
        s = self._make_short_straddle()
        assert s.is_credit_strategy is True

    def test_long_straddle_max_profit_is_inf(self):
        s = self._make_long_straddle()
        assert s.max_profit == float("inf")

    def test_short_straddle_max_loss_is_inf(self):
        s = self._make_short_straddle()
        assert s.max_loss == float("inf")

    def test_long_straddle_max_loss_is_finite(self):
        s = self._make_long_straddle()
        assert math.isfinite(s.max_loss)


# ==============================================================================
# U14 — get_payoff_diagram
# ==============================================================================


class TestGetPayoffDiagram:
    def setup_method(self):
        self.os_ = OptionStrategies()
        self.spread = self.os_.create_bull_call_spread(
            long_strike=440.0,
            short_strike=450.0,
            expiry=EXPIRY,
            long_premium=8.0,
            short_premium=3.0,
            underlying_price=UNDERLYING,
        )

    def test_returns_payoff_result(self):
        result = self.os_.get_payoff_diagram(self.spread)
        assert isinstance(result, PayoffResult)

    def test_spot_prices_is_array(self):
        result = self.os_.get_payoff_diagram(self.spread)
        assert isinstance(result.spot_prices, np.ndarray)

    def test_payoffs_is_array(self):
        result = self.os_.get_payoff_diagram(self.spread)
        assert isinstance(result.payoffs, np.ndarray)

    def test_has_100_points_default(self):
        result = self.os_.get_payoff_diagram(self.spread)
        assert len(result.spot_prices) == 100

    def test_custom_num_points(self):
        result = self.os_.get_payoff_diagram(self.spread, num_points=50)
        assert len(result.spot_prices) == 50

    def test_max_profit_greater_than_max_loss(self):
        result = self.os_.get_payoff_diagram(self.spread)
        assert result.max_profit > result.max_loss

    def test_breakeven_points_is_list(self):
        result = self.os_.get_payoff_diagram(self.spread)
        assert isinstance(result.breakeven_points, list)


# ==============================================================================
# U14 — calculate_max_profit / max_loss / breakevens / probability
# ==============================================================================


class TestRiskAnalysis:
    def setup_method(self):
        self.os_ = OptionStrategies()
        self.spread = self.os_.create_bull_call_spread(
            long_strike=440.0,
            short_strike=450.0,
            expiry=EXPIRY,
            long_premium=8.0,
            short_premium=3.0,
            underlying_price=UNDERLYING,
        )

    def test_calculate_max_profit_returns_float(self):
        result = self.os_.calculate_max_profit(self.spread)
        assert isinstance(result, float)

    def test_calculate_max_loss_returns_float(self):
        result = self.os_.calculate_max_loss(self.spread)
        assert isinstance(result, float)

    def test_max_profit_positive(self):
        result = self.os_.calculate_max_profit(self.spread)
        assert result > 0

    def test_max_loss_negative(self):
        result = self.os_.calculate_max_loss(self.spread)
        assert result < 0

    def test_breakeven_points_returns_list(self):
        result = self.os_.calculate_breakeven_points(self.spread)
        assert isinstance(result, list)

    def test_profit_probability_in_range(self):
        prob = self.os_.calculate_profit_probability(self.spread, 0.15, 30)
        assert 0.0 <= prob <= 1.0

    def test_profit_probability_returns_float(self):
        prob = self.os_.calculate_profit_probability(self.spread, 0.15, 30)
        assert isinstance(prob, float)


# ==============================================================================
# U14 — Module-level function
# ==============================================================================


class TestU14ModuleFunction:
    def test_calculate_option_payoff_fn(self):
        result = _u14.calculate_option_payoff("CALL", "LONG", 450.0, 5.0, 460.0)
        assert result == pytest.approx(500.0)

    def test_get_option_strategies_singleton(self):
        s1 = _u14.get_option_strategies()
        s2 = _u14.get_option_strategies()
        assert s1 is s2


# ==============================================================================
# U15 — ENUM TESTS
# ==============================================================================


class TestPerformanceRatingEnum:
    def test_excellent(self):
        assert PerformanceRating.EXCELLENT.value == "excellent"

    def test_good(self):
        assert PerformanceRating.GOOD.value == "good"

    def test_average(self):
        assert PerformanceRating.AVERAGE.value == "average"

    def test_poor(self):
        assert PerformanceRating.POOR.value == "poor"

    def test_very_poor(self):
        assert PerformanceRating.VERY_POOR.value == "very_poor"


class TestMetricTypeEnum:
    def test_return(self):
        assert MetricType.RETURN.value == "return"

    def test_risk(self):
        assert MetricType.RISK.value == "risk"

    def test_ratio(self):
        assert MetricType.RATIO.value == "ratio"

    def test_drawdown(self):
        assert MetricType.DRAWDOWN.value == "drawdown"

    def test_volatility(self):
        assert MetricType.VOLATILITY.value == "volatility"


# ==============================================================================
# U15 — DrawdownInfo
# ==============================================================================


class TestDrawdownInfoDataclass:
    def test_construction(self):
        dd = DrawdownInfo(
            max_drawdown=-0.15,
            max_drawdown_duration=20,
            recovery_time=10,
            drawdown_periods=[(5, 25, -0.15)],
        )
        assert dd.max_drawdown == -0.15
        assert dd.max_drawdown_duration == 20

    def test_empty_periods(self):
        dd = DrawdownInfo(0.0, 0, 0, [])
        assert dd.drawdown_periods == []


# ==============================================================================
# U15 — PerformanceCalculator construction
# ==============================================================================


class TestPerformanceCalculatorConstruction:
    def test_default_risk_free_rate(self):
        calc = PerformanceCalculator()
        assert calc.risk_free_rate == pytest.approx(0.045)

    def test_custom_risk_free_rate(self):
        calc = PerformanceCalculator(risk_free_rate=0.03)
        assert calc.risk_free_rate == pytest.approx(0.03)

    def test_has_logger(self):
        calc = PerformanceCalculator()
        assert hasattr(calc, "logger")


# ==============================================================================
# U15 — calculate_total_return
# ==============================================================================


class TestCalculateTotalReturn:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_empty_returns_zero(self):
        assert self.calc.calculate_total_return(EMPTY_RETURNS) == 0.0

    def test_all_positive_returns(self):
        returns = pd.Series([0.01, 0.01, 0.01])  # 3 * 1% = ~3.03%
        result = self.calc.calculate_total_return(returns)
        assert result > 0.0

    def test_single_return(self):
        returns = pd.Series([0.05])
        assert self.calc.calculate_total_return(returns) == pytest.approx(0.05)

    def test_mixed_returns_compounded(self):
        returns = pd.Series([0.1, -0.1])  # 1.1 * 0.9 - 1 = -0.01
        result = self.calc.calculate_total_return(returns)
        assert result == pytest.approx(-0.01, abs=1e-6)

    def test_good_returns_positive(self):
        result = self.calc.calculate_total_return(GOOD_RETURNS)
        assert result > 0.0


# ==============================================================================
# U15 — calculate_annualized_return
# ==============================================================================


class TestCalculateAnnualizedReturn:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_empty_returns_zero(self):
        assert self.calc.calculate_annualized_return(EMPTY_RETURNS) == 0.0

    def test_252_daily_returns_annualizes(self):
        # 252 days → 1 year of data
        returns = pd.Series([0.001] * 252)
        result = self.calc.calculate_annualized_return(returns)
        # Each day 0.1% → annualized ≈ (1.001^252 - 1) ≈ 28.4%
        assert result > 0.0

    def test_returns_float(self):
        result = self.calc.calculate_annualized_return(GOOD_RETURNS)
        assert isinstance(result, float)


# ==============================================================================
# U15 — calculate_volatility
# ==============================================================================


class TestCalculateVolatility:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_empty_returns_zero(self):
        assert self.calc.calculate_volatility(EMPTY_RETURNS) == 0.0

    def test_single_return_is_zero(self):
        assert self.calc.calculate_volatility(pd.Series([0.01])) == 0.0

    def test_volatile_series_higher_than_stable(self):
        stable = pd.Series([0.001] * 100)
        volatile = pd.Series([0.05, -0.05] * 50)
        assert self.calc.calculate_volatility(volatile) > self.calc.calculate_volatility(stable)

    def test_constant_series_near_zero(self):
        returns = pd.Series([0.001] * 100)
        result = self.calc.calculate_volatility(returns)
        assert result == pytest.approx(0.0, abs=1e-6)


# ==============================================================================
# U15 — calculate_sharpe_ratio
# ==============================================================================


class TestCalculateSharpeRatio:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_too_few_returns_gives_zero(self):
        # Less than MIN_PERIODS_FOR_CALCULATION → 0
        result = self.calc.calculate_sharpe_ratio(SMALL_RETURNS)
        assert result == 0.0

    def test_empty_returns_gives_zero(self):
        result = self.calc.calculate_sharpe_ratio(EMPTY_RETURNS)
        assert result == 0.0

    def test_positive_returns_positive_sharpe(self):
        result = self.calc.calculate_sharpe_ratio(GOOD_RETURNS)
        assert result > 0

    def test_negative_returns_negative_sharpe(self):
        result = self.calc.calculate_sharpe_ratio(BAD_RETURNS)
        assert result < 0

    def test_returns_float(self):
        result = self.calc.calculate_sharpe_ratio(GOOD_RETURNS)
        assert isinstance(result, float)

    def test_zero_volatility_returns_zero(self):
        # Constant returns → std=0 → returns 0
        returns = pd.Series([self.calc.risk_free_rate / TRADING_DAYS_PER_YEAR] * 100)
        result = self.calc.calculate_sharpe_ratio(returns)
        assert result == pytest.approx(0.0, abs=1e-6)


# ==============================================================================
# U15 — calculate_sortino_ratio
# ==============================================================================


class TestCalculateSortinoRatio:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_too_few_returns_gives_zero(self):
        result = self.calc.calculate_sortino_ratio(SMALL_RETURNS)
        assert result == 0.0

    def test_positive_returns_positive_sortino(self):
        result = self.calc.calculate_sortino_ratio(GOOD_RETURNS)
        assert result > 0 or result == float("inf")

    def test_all_positive_no_downside_returns_inf(self):
        # No negative returns → downside std = 0 → returns inf
        returns = pd.Series([0.01] * 100)
        result = self.calc.calculate_sortino_ratio(returns)
        assert result == float("inf")

    def test_returns_float_or_inf(self):
        result = self.calc.calculate_sortino_ratio(MIXED_RETURNS)
        assert isinstance(result, float) or result == float("inf")


# ==============================================================================
# U15 — calculate_calmar_ratio
# ==============================================================================


class TestCalculateCalmarRatio:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_too_few_returns_gives_zero(self):
        result = self.calc.calculate_calmar_ratio(SMALL_RETURNS)
        assert result == 0.0

    def test_returns_float(self):
        result = self.calc.calculate_calmar_ratio(MIXED_RETURNS)
        assert isinstance(result, float)

    def test_consistently_positive_returns_positive_calmar(self):
        result = self.calc.calculate_calmar_ratio(GOOD_RETURNS)
        # With positive returns, calmar should be positive or inf
        assert result >= 0


# ==============================================================================
# U15 — calculate_max_drawdown
# ==============================================================================


class TestCalculateMaxDrawdown:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_empty_returns_zero(self):
        assert self.calc.calculate_max_drawdown(EMPTY_RETURNS) == 0.0

    def test_monotonically_increasing_is_zero(self):
        cum_returns = pd.Series([0.01, 0.02, 0.03, 0.04, 0.05])
        result = self.calc.calculate_max_drawdown(cum_returns)
        assert result == pytest.approx(0.0)

    def test_drawdown_is_negative(self):
        cum_returns = pd.Series([0.1, 0.05, 0.08, 0.03, 0.12])
        result = self.calc.calculate_max_drawdown(cum_returns)
        assert result < 0

    def test_drawdown_bounded_zero_to_minus_one(self):
        cum_returns = pd.Series([0.2, 0.1, 0.05, 0.15, 0.25])
        result = self.calc.calculate_max_drawdown(cum_returns)
        assert result >= -1.0
        assert result <= 0.0


# ==============================================================================
# U15 — analyze_drawdowns
# ==============================================================================


class TestAnalyzeDrawdowns:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_empty_returns_default(self):
        result = self.calc.analyze_drawdowns(EMPTY_RETURNS)
        assert isinstance(result, DrawdownInfo)
        assert result.max_drawdown == 0.0

    def test_returns_drawdown_info(self):
        cum = pd.Series([0.1, 0.05, 0.08, 0.03, 0.12, 0.15])
        result = self.calc.analyze_drawdowns(cum)
        assert isinstance(result, DrawdownInfo)

    def test_monotonically_increasing_no_drawdown(self):
        cum = pd.Series([0.01, 0.02, 0.03, 0.04, 0.05])
        result = self.calc.analyze_drawdowns(cum)
        assert result.max_drawdown == pytest.approx(0.0)


# ==============================================================================
# U15 — calculate_win_rate
# ==============================================================================


class TestCalculateWinRate:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_empty_returns_zero(self):
        assert self.calc.calculate_win_rate(EMPTY_RETURNS) == 0.0

    def test_all_positive_100_percent(self):
        returns = pd.Series([0.01, 0.02, 0.03, 0.05])
        assert self.calc.calculate_win_rate(returns) == pytest.approx(100.0)

    def test_all_negative_zero_percent(self):
        returns = pd.Series([-0.01, -0.02, -0.03])
        assert self.calc.calculate_win_rate(returns) == pytest.approx(0.0)

    def test_50_percent_win_rate(self):
        returns = pd.Series([0.01, -0.01, 0.01, -0.01])
        assert self.calc.calculate_win_rate(returns) == pytest.approx(50.0)

    def test_win_rate_in_0_100_range(self):
        result = self.calc.calculate_win_rate(MIXED_RETURNS)
        assert 0.0 <= result <= 100.0


# ==============================================================================
# U15 — calculate_profit_factor
# ==============================================================================


class TestCalculateProfitFactor:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_empty_returns_zero(self):
        assert self.calc.calculate_profit_factor(EMPTY_RETURNS) == 0.0

    def test_all_positive_returns_inf(self):
        returns = pd.Series([0.01, 0.02, 0.03])
        result = self.calc.calculate_profit_factor(returns)
        assert result == float("inf")

    def test_all_negative_returns_zero(self):
        returns = pd.Series([-0.01, -0.02, -0.03])
        result = self.calc.calculate_profit_factor(returns)
        assert result == pytest.approx(0.0)

    def test_mixed_returns_positive_factor(self):
        returns = pd.Series([0.05, -0.01, 0.05, -0.01])  # wins > losses
        result = self.calc.calculate_profit_factor(returns)
        assert result > 1.0


# ==============================================================================
# U15 — calculate_trade_statistics
# ==============================================================================


class TestCalculateTradeStatistics:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_empty_returns_default_dict(self):
        result = self.calc.calculate_trade_statistics(EMPTY_RETURNS)
        assert result["total_trades"] == 0

    def test_returns_dict_with_expected_keys(self):
        result = self.calc.calculate_trade_statistics(MIXED_RETURNS)
        required_keys = {
            "total_trades", "winning_trades", "losing_trades",
            "avg_win", "avg_loss", "largest_win", "largest_loss",
        }
        assert required_keys.issubset(result.keys())

    def test_total_trades_correct(self):
        returns = pd.Series([0.01, -0.005, 0.02, -0.01, 0.03])
        result = self.calc.calculate_trade_statistics(returns)
        assert result["total_trades"] == 5

    def test_winning_and_losing_sum_to_total(self):
        returns = pd.Series([0.01, -0.005, 0.02, -0.01, 0.03])
        result = self.calc.calculate_trade_statistics(returns)
        assert (
            result["winning_trades"] + result["losing_trades"]
            <= result["total_trades"]
        )

    def test_largest_win_positive(self):
        returns = pd.Series([0.01, -0.005, 0.05])
        result = self.calc.calculate_trade_statistics(returns)
        assert result["largest_win"] == pytest.approx(0.05)

    def test_largest_loss_negative(self):
        returns = pd.Series([0.01, -0.05, 0.02])
        result = self.calc.calculate_trade_statistics(returns)
        assert result["largest_loss"] == pytest.approx(-0.05)


# ==============================================================================
# U15 — rate_performance
# ==============================================================================


class TestRatePerformance:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_excellent_performance(self):
        # sharpe≥2 (+3), calmar≥1 (+3), win_rate≥60 (+3) = 9 → EXCELLENT
        result = self.calc.rate_performance(2.5, 1.5, 65.0)
        assert result == PerformanceRating.EXCELLENT

    def test_good_performance(self):
        # sharpe≥1 (+2), calmar≥0.5 (+2), win_rate≥50 (+2) = 6 → GOOD
        result = self.calc.rate_performance(1.5, 0.7, 55.0)
        assert result == PerformanceRating.GOOD

    def test_average_performance(self):
        # sharpe≥0.5 (+1), calmar≥0.25 (+1), win_rate≥40 (+1) = 3? → POOR (score<4)
        # Actually: (+1+1+1)=3 → POOR (score>=2 and <4)
        # For AVERAGE score must be ≥4
        # sharpe=1.0 (+2), calmar=0.5 (+2), win_rate=15 (0) = 4 → AVERAGE
        result = self.calc.rate_performance(1.0, 0.5, 15.0)
        assert result == PerformanceRating.AVERAGE

    def test_poor_performance(self):
        # sharpe≥0.5 (+1), calmar≥0.25 (+1), win_rate<40 (0) = 2 → POOR
        result = self.calc.rate_performance(0.6, 0.3, 30.0)
        assert result == PerformanceRating.POOR

    def test_very_poor_performance(self):
        # sharpe<0.5 (0), calmar<0.25 (0), win_rate<40 (0) = 0 → VERY_POOR
        result = self.calc.rate_performance(0.1, 0.1, 20.0)
        assert result == PerformanceRating.VERY_POOR

    def test_returns_performance_rating(self):
        result = self.calc.rate_performance(1.0, 0.5, 50.0)
        assert isinstance(result, PerformanceRating)


# ==============================================================================
# U15 — generate_performance_report
# ==============================================================================


class TestGeneratePerformanceReport:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_returns_performance_report(self):
        result = self.calc.generate_performance_report(MIXED_RETURNS)
        assert isinstance(result, PerformanceReport)

    def test_report_has_rating(self):
        result = self.calc.generate_performance_report(MIXED_RETURNS)
        assert isinstance(result.rating, PerformanceRating)

    def test_report_has_total_return(self):
        result = self.calc.generate_performance_report(MIXED_RETURNS)
        assert isinstance(result.total_return, float)

    def test_report_win_rate_in_range(self):
        result = self.calc.generate_performance_report(MIXED_RETURNS)
        assert 0.0 <= result.win_rate <= 100.0

    def test_report_to_dict(self):
        result = self.calc.generate_performance_report(MIXED_RETURNS)
        d = result.to_dict()
        assert "total_return" in d
        assert "sharpe_ratio" in d
        assert "rating" in d

    def test_empty_returns_returns_default(self):
        # Should return without crashing, with default VeryPoor rating
        result = self.calc.generate_performance_report(EMPTY_RETURNS)
        assert isinstance(result, PerformanceReport)


# ==============================================================================
# U15 — Module-level functions
# ==============================================================================


class TestU15ModuleFunctions:
    def test_calculate_sharpe_ratio_fn(self):
        result = _u15.calculate_sharpe_ratio(GOOD_RETURNS)
        assert isinstance(result, float)

    def test_calculate_max_drawdown_fn(self):
        cum = pd.Series([0.01, 0.05, 0.03, 0.08])
        result = _u15.calculate_max_drawdown(cum)
        assert isinstance(result, float)

    def test_generate_performance_report_fn(self):
        result = _u15.generate_performance_report(MIXED_RETURNS)
        assert isinstance(result, PerformanceReport)

    def test_get_performance_calculator_singleton(self):
        c1 = _u15.get_performance_calculator()
        c2 = _u15.get_performance_calculator()
        assert c1 is c2
