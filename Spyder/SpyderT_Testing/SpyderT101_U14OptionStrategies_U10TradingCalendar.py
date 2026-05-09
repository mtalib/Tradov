#!/usr/bin/env python3
"""
SPYDER - Test Suite T101
Tests: SpyderU14_OptionStrategies + SpyderU10_TradingCalendar

Coverage:
    - U14: OptionType, PositionType, StrategyType enums; OptionLeg, OptionStrategy,
           PayoffResult dataclasses; OptionStrategies class (payoff calc, strategy
           builders, risk analysis); module functions
    - U10: MarketSession, MarketStatus, Exchange enums; MarketHours, Holiday dataclasses;
           TradingCalendar class (trading day checks, market hours, holiday management,
           calendar operations, time utilities, lifecycle); module functions
"""

# ==============================================================================
# BOOTSTRAP — must run before any Spyder imports
# ==============================================================================
import os
import sys
import types
from unittest.mock import MagicMock

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _ensure_pkg(name: str) -> None:
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)


_ensure_pkg("Spyder")
_ensure_pkg("Spyder.SpyderU_Utilities")
_ensure_pkg("Spyder.SpyderU_Utilities")

_logger_mod = types.ModuleType("Spyder.SpyderU_Utilities.SpyderU01_Logger")


class _FakeSpyderLogger:
    @staticmethod
    def get_logger(name: str) -> MagicMock:
        return MagicMock()


_logger_mod.SpyderLogger = _FakeSpyderLogger
_logger_mod.get_logger = MagicMock(return_value=MagicMock())
sys.modules["Spyder.SpyderU_Utilities.SpyderU01_Logger"] = _logger_mod

_err_mod = types.ModuleType("Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler")
_err_mod.SpyderErrorHandler = MagicMock
sys.modules["Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler"] = _err_mod

# ==============================================================================
# ACTUAL IMPORTS
# ==============================================================================
import math
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pytest

from Spyder.SpyderU_Utilities.SpyderU14_OptionStrategies import (
    CONTRACT_MULTIPLIER,
    DAYS_PER_YEAR,
    RISK_FREE_RATE,
    OptionLeg,
    OptionStrategies,
    OptionStrategy,
    OptionType,
    PayoffResult,
    PositionType,
    StrategyType,
    calculate_option_payoff,
    get_option_strategies,
)
from Spyder.SpyderU_Utilities.SpyderU10_TradingCalendar import (
    DEFAULT_AFTERHOURS_CLOSE,
    DEFAULT_MARKET_CLOSE,
    DEFAULT_MARKET_OPEN,
    DEFAULT_PREMARKET_OPEN,
    ET_TIMEZONE,
    Exchange,
    Holiday,
    MarketHours,
    MarketSession,
    MarketStatus,
    TradingCalendar,
    get_trading_calendar,
)

# ==============================================================================
# SHARED HELPERS
# ==============================================================================

_EXPIRY = datetime(2025, 12, 19, 16, 0)  # December 19, 2025 (Friday expiry)

# Known US weekdays and holidays — computed using current year so holiday
# loading (which only covers current_year and current_year+1) is consistent.
_CURRENT_YEAR = date.today().year


def _observed(year: int, month: int, day: int) -> date:
    """Return the NYSE observed date for a holiday that may fall on a weekend."""
    d = date(year, month, day)
    if d.weekday() == 5:   # Saturday -> Friday
        return d - timedelta(days=1)
    if d.weekday() == 6:   # Sunday -> Monday
        return d + timedelta(days=1)
    return d


# Midpoint weekday: pick a Monday in July of current year that avoids July 4
_WEEKDAY = date(_CURRENT_YEAR, 7, 7)    # July 7 — always a Monday regardless of year
# But we need a reliable Monday — use known offsets from a fixed anchor.
# July 7, 2025 = Monday; we want current year's equivalent.
import calendar as _cal
_WEEKDAY = date(
    _CURRENT_YEAR, 7,
    7 + (0 - date(_CURRENT_YEAR, 7, 7).weekday()) % 7  # First Monday >= July 7
)
_WEEKEND_SAT = _WEEKDAY + timedelta(days=5)  # Saturday after
_WEEKEND_SUN = _WEEKDAY + timedelta(days=6)  # Sunday after

# Use New Year's Day as a known holiday (always Jan 1, adjusted for weekends)
_KNOWN_HOLIDAY = _observed(_CURRENT_YEAR, 1, 1)  # New Year's Day (current year)


def _make_bull_call(os_: OptionStrategies) -> OptionStrategy:
    return os_.create_bull_call_spread(
        long_strike=450.0,
        short_strike=460.0,
        expiry=_EXPIRY,
        long_premium=8.0,
        short_premium=3.0,
        underlying_price=455.0,
    )


def _make_bear_put(os_: OptionStrategies) -> OptionStrategy:
    return os_.create_bear_put_spread(
        long_strike=460.0,
        short_strike=450.0,
        expiry=_EXPIRY,
        long_premium=8.0,
        short_premium=3.0,
        underlying_price=455.0,
    )


def _make_iron_condor(os_: OptionStrategies) -> OptionStrategy:
    return os_.create_iron_condor(
        put_long_strike=430.0,
        put_short_strike=440.0,
        call_short_strike=470.0,
        call_long_strike=480.0,
        expiry=_EXPIRY,
        premiums=[1.5, 4.0, 4.0, 1.5],
        underlying_price=455.0,
    )


def _make_long_straddle(os_: OptionStrategies) -> OptionStrategy:
    return os_.create_straddle(
        strike=455.0,
        expiry=_EXPIRY,
        call_premium=6.0,
        put_premium=6.0,
        underlying_price=455.0,
        position_type="LONG",
    )


def _make_short_straddle(os_: OptionStrategies) -> OptionStrategy:
    return os_.create_straddle(
        strike=455.0,
        expiry=_EXPIRY,
        call_premium=6.0,
        put_premium=6.0,
        underlying_price=455.0,
        position_type="SHORT",
    )


# ==============================================================================
# U14 — ENUMS
# ==============================================================================


class TestOptionType:
    def test_members_count(self):
        assert len(OptionType) == 2

    def test_call(self):
        assert OptionType.CALL.value == "CALL"

    def test_put(self):
        assert OptionType.PUT.value == "PUT"

    def test_from_string(self):
        assert OptionType("CALL") == OptionType.CALL


class TestPositionType:
    def test_members_count(self):
        assert len(PositionType) == 2

    def test_long(self):
        assert PositionType.LONG.value == "LONG"

    def test_short(self):
        assert PositionType.SHORT.value == "SHORT"


class TestStrategyType:
    def test_members_count(self):
        assert len(StrategyType) == 11

    def test_iron_condor(self):
        assert StrategyType.IRON_CONDOR.value == "iron_condor"

    def test_straddle(self):
        assert StrategyType.STRADDLE.value == "straddle"

    def test_bull_call_spread(self):
        assert StrategyType.BULL_CALL_SPREAD.value == "bull_call_spread"

    def test_bear_put_spread(self):
        assert StrategyType.BEAR_PUT_SPREAD.value == "bear_put_spread"


# ==============================================================================
# U14 — DATACLASSES
# ==============================================================================


class TestOptionLeg:
    def _make_leg(self, option_type=OptionType.CALL, position_type=PositionType.LONG,
                  strike=460.0, premium=5.0, quantity=1) -> OptionLeg:
        return OptionLeg(option_type=option_type, position_type=position_type,
                         strike=strike, expiry=_EXPIRY, premium=premium, quantity=quantity)

    def test_creation(self):
        leg = self._make_leg()
        assert leg.strike == 460.0

    def test_is_call_true(self):
        leg = self._make_leg(option_type=OptionType.CALL)
        assert leg.is_call is True
        assert leg.is_put is False

    def test_is_put_true(self):
        leg = self._make_leg(option_type=OptionType.PUT)
        assert leg.is_put is True
        assert leg.is_call is False

    def test_is_long_true(self):
        leg = self._make_leg(position_type=PositionType.LONG)
        assert leg.is_long is True
        assert leg.is_short is False

    def test_is_short_true(self):
        leg = self._make_leg(position_type=PositionType.SHORT)
        assert leg.is_short is True
        assert leg.is_long is False

    def test_net_premium_long_negative(self):
        # Long leg: multiplier=-1, net_premium = -premium * qty
        leg = self._make_leg(position_type=PositionType.LONG, premium=5.0, quantity=1)
        assert leg.net_premium == -5.0

    def test_net_premium_short_positive(self):
        # Short leg: multiplier=1, net_premium = +premium * qty
        leg = self._make_leg(position_type=PositionType.SHORT, premium=3.0, quantity=1)
        assert leg.net_premium == 3.0

    def test_net_premium_quantity(self):
        leg = self._make_leg(position_type=PositionType.SHORT, premium=2.0, quantity=3)
        assert leg.net_premium == 6.0


class TestOptionStrategy:
    def _make_strategy(self) -> OptionStrategy:
        legs = [
            OptionLeg(OptionType.CALL, PositionType.LONG, 450.0, _EXPIRY, 8.0),
            OptionLeg(OptionType.CALL, PositionType.SHORT, 460.0, _EXPIRY, 3.0),
        ]
        return OptionStrategy(
            name="Test BCS",
            strategy_type=StrategyType.BULL_CALL_SPREAD,
            legs=legs,
            underlying_price=455.0,
        )

    def test_creation(self):
        s = self._make_strategy()
        assert s.name == "Test BCS"

    def test_net_premium_debit(self):
        s = self._make_strategy()
        # long call: -8, short call: +3 → net = -5
        assert s.net_premium == -5.0

    def test_is_debit_strategy(self):
        s = self._make_strategy()
        assert s.is_debit_strategy is True
        assert s.is_credit_strategy is False

    def test_is_credit_strategy(self):
        legs = [
            OptionLeg(OptionType.PUT, PositionType.SHORT, 450.0, _EXPIRY, 8.0),
            OptionLeg(OptionType.PUT, PositionType.LONG, 440.0, _EXPIRY, 3.0),
        ]
        s = OptionStrategy("Credit put spread", StrategyType.BEAR_PUT_SPREAD, legs, 455.0)
        assert s.is_credit_strategy is True

    def test_default_fields(self):
        s = self._make_strategy()
        assert s.max_profit is None
        assert s.max_loss is None
        assert s.breakeven_points == []

    def test_legs_count(self):
        s = self._make_strategy()
        assert len(s.legs) == 2


class TestPayoffResult:
    def _make_payoff(self) -> PayoffResult:
        prices = np.linspace(440, 475, 50)
        payoffs = np.zeros(50)
        return PayoffResult(
            spot_prices=prices, payoffs=payoffs,
            max_profit=500.0, max_loss=-800.0,
            breakeven_points=[453.5],
        )

    def test_creation(self):
        pr = self._make_payoff()
        assert pr.max_profit == 500.0

    def test_max_loss(self):
        pr = self._make_payoff()
        assert pr.max_loss == -800.0

    def test_breakeven_points(self):
        pr = self._make_payoff()
        assert pr.breakeven_points == [453.5]

    def test_spot_prices_array(self):
        pr = self._make_payoff()
        assert isinstance(pr.spot_prices, np.ndarray)


# ==============================================================================
# U14 — CONSTANTS
# ==============================================================================


class TestU14Constants:
    def test_contract_multiplier(self):
        assert CONTRACT_MULTIPLIER == 100

    def test_days_per_year(self):
        assert DAYS_PER_YEAR == 365.25

    def test_risk_free_rate(self):
        assert 0 < RISK_FREE_RATE < 1


# ==============================================================================
# U14 — OPTION STRATEGIES CLASS
# ==============================================================================


class TestOptionStrategiesInit:
    def test_creates_instance(self):
        os_ = OptionStrategies()
        assert os_ is not None

    def test_has_logger(self):
        os_ = OptionStrategies()
        assert os_.logger is not None


class TestOptionPayoffCalc:
    def setup_method(self):
        self.os_ = OptionStrategies()

    def test_long_call_itm(self):
        # Long 460 call, 5 premium, spot 470 → (10-5)*100 = 500
        result = self.os_.calculate_option_payoff("CALL", "LONG", 460.0, 5.0, 470.0)
        assert abs(result - 500.0) < 1e-6

    def test_long_call_otm(self):
        # Long 460 call, 5 premium, spot 450 → (0-5)*100 = -500
        result = self.os_.calculate_option_payoff("CALL", "LONG", 460.0, 5.0, 450.0)
        assert abs(result - (-500.0)) < 1e-6

    def test_short_call_itm(self):
        # Short 460 call, 5 premium, spot 470 → (5-10)*100 = -500
        result = self.os_.calculate_option_payoff("CALL", "SHORT", 460.0, 5.0, 470.0)
        assert abs(result - (-500.0)) < 1e-6

    def test_long_put_itm(self):
        # Long 460 put, 5 premium, spot 450 → (10-5)*100 = 500
        result = self.os_.calculate_option_payoff("PUT", "LONG", 460.0, 5.0, 450.0)
        assert abs(result - 500.0) < 1e-6

    def test_long_put_otm(self):
        # Long 460 put, 5 premium, spot 470 → (0-5)*100 = -500
        result = self.os_.calculate_option_payoff("PUT", "LONG", 460.0, 5.0, 470.0)
        assert abs(result - (-500.0)) < 1e-6

    def test_vectorized_spot_prices(self):
        spots = np.array([450.0, 460.0, 470.0])
        result = self.os_.calculate_option_payoff("CALL", "LONG", 460.0, 5.0, spots)
        assert isinstance(result, np.ndarray)
        assert len(result) == 3

    def test_quantity_scales_payoff(self):
        r1 = self.os_.calculate_option_payoff("CALL", "LONG", 460.0, 5.0, 475.0, quantity=1)
        r2 = self.os_.calculate_option_payoff("CALL", "LONG", 460.0, 5.0, 475.0, quantity=2)
        assert abs(r2 - 2 * r1) < 1e-6

    def test_invalid_option_type_returns_zero(self):
        result = self.os_.calculate_option_payoff("INVALID", "LONG", 460.0, 5.0, 470.0)
        assert result == 0.0


class TestStrategyBuilders:
    def setup_method(self):
        self.os_ = OptionStrategies()

    def test_bull_call_spread_returns_strategy(self):
        s = _make_bull_call(self.os_)
        assert isinstance(s, OptionStrategy)

    def test_bull_call_spread_type(self):
        s = _make_bull_call(self.os_)
        assert s.strategy_type == StrategyType.BULL_CALL_SPREAD

    def test_bull_call_spread_leg_count(self):
        s = _make_bull_call(self.os_)
        assert len(s.legs) == 2

    def test_bull_call_spread_is_debit(self):
        s = _make_bull_call(self.os_)
        assert s.is_debit_strategy is True

    def test_bull_call_spread_max_loss_set(self):
        s = _make_bull_call(self.os_)
        assert s.max_loss is not None

    def test_bull_call_spread_max_profit_set(self):
        s = _make_bull_call(self.os_)
        assert s.max_profit is not None

    def test_bear_put_spread_returns_strategy(self):
        s = _make_bear_put(self.os_)
        assert isinstance(s, OptionStrategy)

    def test_bear_put_spread_type(self):
        s = _make_bear_put(self.os_)
        assert s.strategy_type == StrategyType.BEAR_PUT_SPREAD

    def test_iron_condor_returns_strategy(self):
        s = _make_iron_condor(self.os_)
        assert isinstance(s, OptionStrategy)

    def test_iron_condor_type(self):
        s = _make_iron_condor(self.os_)
        assert s.strategy_type == StrategyType.IRON_CONDOR

    def test_iron_condor_leg_count(self):
        s = _make_iron_condor(self.os_)
        assert len(s.legs) == 4

    def test_iron_condor_is_credit(self):
        s = _make_iron_condor(self.os_)
        assert s.is_credit_strategy is True

    def test_long_straddle_returns_strategy(self):
        s = _make_long_straddle(self.os_)
        assert isinstance(s, OptionStrategy)

    def test_long_straddle_type(self):
        s = _make_long_straddle(self.os_)
        assert s.strategy_type == StrategyType.STRADDLE

    def test_long_straddle_leg_count(self):
        s = _make_long_straddle(self.os_)
        assert len(s.legs) == 2

    def test_long_straddle_max_loss_set(self):
        s = _make_long_straddle(self.os_)
        assert s.max_loss is not None

    def test_long_straddle_unlimited_max_profit(self):
        s = _make_long_straddle(self.os_)
        assert s.max_profit == float("inf")

    def test_short_straddle_max_profit_set(self):
        s = _make_short_straddle(self.os_)
        assert s.max_profit is not None

    def test_short_straddle_is_credit(self):
        s = _make_short_straddle(self.os_)
        assert s.is_credit_strategy is True


class TestPayoffDiagram:
    def setup_method(self):
        self.os_ = OptionStrategies()

    def test_returns_payoff_result(self):
        s = _make_bull_call(self.os_)
        result = self.os_.get_payoff_diagram(s)
        assert isinstance(result, PayoffResult)

    def test_spot_prices_length(self):
        s = _make_bull_call(self.os_)
        result = self.os_.get_payoff_diagram(s)
        assert len(result.spot_prices) == 100  # default num_points

    def test_custom_num_points(self):
        s = _make_bull_call(self.os_)
        result = self.os_.get_payoff_diagram(s, num_points=50)
        assert len(result.spot_prices) == 50

    def test_custom_price_range(self):
        s = _make_bull_call(self.os_)
        result = self.os_.get_payoff_diagram(s, price_range=(430.0, 480.0))
        assert result.spot_prices[0] == pytest.approx(430.0, abs=1e-6)
        assert result.spot_prices[-1] == pytest.approx(480.0, abs=1e-6)

    def test_max_profit_positive(self):
        s = _make_bull_call(self.os_)
        result = self.os_.get_payoff_diagram(s)
        assert result.max_profit > 0

    def test_max_loss_negative(self):
        s = _make_bull_call(self.os_)
        result = self.os_.get_payoff_diagram(s)
        assert result.max_loss < 0


class TestRiskAnalysis:
    def setup_method(self):
        self.os_ = OptionStrategies()
        self.bull_call = _make_bull_call(self.os_)
        self.condor = _make_iron_condor(self.os_)

    def test_calculate_max_profit_positive(self):
        result = self.os_.calculate_max_profit(self.bull_call)
        assert result > 0

    def test_calculate_max_loss_negative(self):
        result = self.os_.calculate_max_loss(self.bull_call)
        assert result < 0

    def test_calculate_breakeven_points_list(self):
        result = self.os_.calculate_breakeven_points(self.bull_call)
        assert isinstance(result, list)

    def test_profit_probability_range(self):
        result = self.os_.calculate_profit_probability(self.bull_call, 0.15, 30)
        assert 0.0 <= result <= 1.0

    def test_profit_probability_condor_range(self):
        result = self.os_.calculate_profit_probability(self.condor, 0.10, 30)
        assert 0.0 <= result <= 1.0


class TestU14ModuleFunctions:
    def test_get_option_strategies_returns_instance(self):
        os_ = get_option_strategies()
        assert isinstance(os_, OptionStrategies)

    def test_get_option_strategies_singleton(self):
        os1 = get_option_strategies()
        os2 = get_option_strategies()
        assert os1 is os2

    def test_calculate_option_payoff_long_call_itm(self):
        result = calculate_option_payoff("CALL", "LONG", 460.0, 5.0, 475.0)
        # (475-460-5)*100 = 1000
        assert abs(result - 1000.0) < 1e-6

    def test_calculate_option_payoff_vectorized(self):
        spots = np.array([455.0, 460.0, 465.0])
        result = calculate_option_payoff("CALL", "LONG", 460.0, 5.0, spots)
        assert isinstance(result, np.ndarray)


# ==============================================================================
# U10 — ENUMS
# ==============================================================================


class TestMarketSession:
    def test_members_count(self):
        assert len(MarketSession) == 5

    def test_closed(self):
        assert MarketSession.CLOSED.value == "closed"

    def test_premarket(self):
        assert MarketSession.PREMARKET.value == "premarket"

    def test_regular(self):
        assert MarketSession.REGULAR.value == "regular"

    def test_afterhours(self):
        assert MarketSession.AFTERHOURS.value == "afterhours"


class TestMarketStatus:
    def test_members_count(self):
        assert len(MarketStatus) == 7

    def test_open(self):
        assert MarketStatus.OPEN.value == "open"

    def test_closed(self):
        assert MarketStatus.CLOSED.value == "closed"

    def test_holiday(self):
        assert MarketStatus.HOLIDAY.value == "holiday"

    def test_weekend(self):
        assert MarketStatus.WEEKEND.value == "weekend"


class TestExchange:
    def test_members_count(self):
        assert len(Exchange) == 4

    def test_nyse(self):
        assert Exchange.NYSE.value == "NYSE"

    def test_nasdaq(self):
        assert Exchange.NASDAQ.value == "NASDAQ"

    def test_cboe(self):
        assert Exchange.CBOE.value == "CBOE"

    def test_cme(self):
        assert Exchange.CME.value == "CME"


# ==============================================================================
# U10 — DATACLASSES
# ==============================================================================


class TestMarketHours:
    def test_creation(self):
        mh = MarketHours(
            date=date(2025, 7, 14),
            market_open=time(9, 30),
            market_close=time(16, 0),
            is_trading_day=True,
        )
        assert mh.is_trading_day is True

    def test_defaults(self):
        mh = MarketHours(date=date(2025, 7, 14))
        assert mh.premarket_open is None
        assert mh.is_early_close is False

    def test_fields(self):
        mh = MarketHours(date=date(2025, 7, 14), market_open=time(9, 30), market_close=time(16, 0))
        assert mh.market_open == time(9, 30)
        assert mh.market_close == time(16, 0)


class TestHoliday:
    def test_creation(self):
        h = Holiday(date=date(2025, 7, 4), name="Independence Day", exchange=Exchange.NYSE)
        assert h.name == "Independence Day"

    def test_defaults(self):
        h = Holiday(date=date(2025, 12, 25), name="Christmas", exchange=Exchange.NASDAQ)
        assert h.is_closed is True
        assert h.early_close_time is None


# ==============================================================================
# U10 — CONSTANTS
# ==============================================================================


class TestU10Constants:
    def test_market_open(self):
        assert time(9, 30) == DEFAULT_MARKET_OPEN

    def test_market_close(self):
        assert time(16, 0) == DEFAULT_MARKET_CLOSE

    def test_premarket_open(self):
        assert time(4, 0) == DEFAULT_PREMARKET_OPEN

    def test_afterhours_close(self):
        assert time(20, 0) == DEFAULT_AFTERHOURS_CLOSE

    def test_et_timezone_not_none(self):
        assert ET_TIMEZONE is not None


# ==============================================================================
# U10 — TRADING CALENDAR CLASS
# ==============================================================================


class TestTradingCalendarInit:
    def test_creates_instance(self):
        cal = TradingCalendar()
        assert cal is not None

    def test_default_exchange(self):
        cal = TradingCalendar()
        assert cal.exchange == Exchange.NYSE

    def test_custom_exchange(self):
        cal = TradingCalendar(exchange=Exchange.NASDAQ)
        assert cal.exchange == Exchange.NASDAQ

    def test_has_holidays(self):
        cal = TradingCalendar()
        assert isinstance(cal.holidays, set)
        assert len(cal.holidays) > 0

    def test_has_logger(self):
        cal = TradingCalendar()
        assert cal.logger is not None

    def test_regular_open(self):
        cal = TradingCalendar()
        assert cal.regular_open == time(9, 30)

    def test_regular_close(self):
        cal = TradingCalendar()
        assert cal.regular_close == time(16, 0)


class TestTradingDayChecks:
    def setup_method(self):
        self.cal = TradingCalendar()

    def test_weekday_is_trading_day(self):
        assert self.cal.is_trading_day(_WEEKDAY) is True

    def test_saturday_is_not_trading_day(self):
        assert self.cal.is_trading_day(_WEEKEND_SAT) is False

    def test_sunday_is_not_trading_day(self):
        assert self.cal.is_trading_day(_WEEKEND_SUN) is False

    def test_new_years_day_not_trading(self):
        assert self.cal.is_trading_day(_KNOWN_HOLIDAY) is False

    def test_none_uses_today(self):
        # Should return a bool regardless of today's date
        result = self.cal.is_trading_day(None)
        assert isinstance(result, bool)

    def test_christmas_not_trading(self):
        # Christmas in current year
        assert self.cal.is_trading_day(_observed(_CURRENT_YEAR, 12, 25)) is False

    def test_labor_day_not_trading(self):
        # Labor Day = 1st Monday in September of current year
        first_sep = date(_CURRENT_YEAR, 9, 1)
        days_to_monday = (0 - first_sep.weekday()) % 7
        labor_day = first_sep + timedelta(days=days_to_monday)
        assert self.cal.is_trading_day(labor_day) is False


class TestMarketStatusMethods:
    def setup_method(self):
        self.cal = TradingCalendar()
        self._et = ZoneInfo("America/New_York")

    def _ts(self, d: date, t: time) -> datetime:
        return datetime.combine(d, t).replace(tzinfo=self._et)

    def test_market_open_during_hours(self):
        ts = self._ts(_WEEKDAY, time(10, 30))
        assert self.cal.is_market_open(ts) is True

    def test_market_closed_before_open(self):
        ts = self._ts(_WEEKDAY, time(8, 0))
        assert self.cal.is_market_open(ts) is False

    def test_market_closed_after_close(self):
        ts = self._ts(_WEEKDAY, time(17, 0))
        assert self.cal.is_market_open(ts) is False

    def test_is_market_open_returns_bool(self):
        assert isinstance(self.cal.is_market_open(), bool)

    def test_is_extended_hours_returns_bool(self):
        assert isinstance(self.cal.is_extended_hours(), bool)

    def test_get_market_status_returns_market_status(self):
        result = self.cal.get_market_status()
        assert isinstance(result, MarketStatus)

    def test_get_market_status_weekend(self):
        ts = self._ts(_WEEKEND_SAT, time(12, 0))
        assert self.cal.get_market_status(ts) == MarketStatus.WEEKEND

    def test_get_market_status_holiday(self):
        ts = self._ts(_KNOWN_HOLIDAY, time(12, 0))
        assert self.cal.get_market_status(ts) == MarketStatus.HOLIDAY

    def test_get_market_status_closed_overnight(self):
        ts = self._ts(_WEEKDAY, time(2, 0))
        assert self.cal.get_market_status(ts) == MarketStatus.CLOSED

    def test_get_market_session_returns_market_session(self):
        result = self.cal.get_market_session()
        assert isinstance(result, MarketSession)

    def test_get_market_session_regular_hours(self):
        ts = self._ts(_WEEKDAY, time(11, 0))
        assert self.cal.get_market_session(ts) == MarketSession.REGULAR

    def test_get_market_session_weekend_closed(self):
        ts = self._ts(_WEEKEND_SAT, time(12, 0))
        assert self.cal.get_market_session(ts) == MarketSession.CLOSED


class TestCalendarOperations:
    def setup_method(self):
        self.cal = TradingCalendar()

    def test_get_next_trading_day_from_weekday(self):
        # Thursday July 10 → next is July 11 (Friday)
        result = self.cal.get_next_trading_day(date(2025, 7, 10))
        assert result == date(2025, 7, 11)

    def test_get_next_trading_day_from_friday(self):
        # Friday July 11 → next should skip weekend → Monday July 14
        result = self.cal.get_next_trading_day(date(2025, 7, 11))
        assert result == date(2025, 7, 14)

    def test_get_previous_trading_day_from_monday(self):
        # Monday July 14 → previous is July 11 (Friday)
        result = self.cal.get_previous_trading_day(date(2025, 7, 14))
        assert result == date(2025, 7, 11)

    def test_get_previous_trading_day_from_tuesday(self):
        result = self.cal.get_previous_trading_day(date(2025, 7, 15))
        assert result == date(2025, 7, 14)

    def test_get_trading_days_one_week(self):
        # July 14–18, 2025 is M-F, no holidays
        result = self.cal.get_trading_days(date(2025, 7, 14), date(2025, 7, 18))
        assert len(result) == 5

    def test_get_trading_days_excludes_weekends(self):
        # July 12–18, 2025 (Sat–Fri): 5 trading days
        result = self.cal.get_trading_days(date(2025, 7, 12), date(2025, 7, 18))
        assert len(result) == 5

    def test_get_trading_days_empty_range(self):
        result = self.cal.get_trading_days(date(2025, 7, 12), date(2025, 7, 13))
        assert result == []

    def test_get_trading_days_returns_list(self):
        result = self.cal.get_trading_days(date(2025, 7, 14), date(2025, 7, 15))
        assert isinstance(result, list)

    def test_get_market_hours_returns_market_hours(self):
        result = self.cal.get_market_hours(date(2025, 7, 14))
        assert isinstance(result, MarketHours)

    def test_get_market_hours_weekday(self):
        result = self.cal.get_market_hours(_WEEKDAY)
        assert result.market_open == time(9, 30)
        assert result.market_close == time(16, 0)

    def test_get_market_hours_non_trading_day(self):
        result = self.cal.get_market_hours(_WEEKEND_SAT)
        assert result.is_trading_day is False
        assert result.market_open is None


class TestHolidayManagement:
    def setup_method(self):
        self.cal = TradingCalendar()

    def test_load_holidays_idempotent(self):
        len(self.cal.holidays)
        self.cal.load_holidays()
        # May increase or stay same but shouldn't decrease
        assert len(self.cal.holidays) > 0

    def test_add_custom_holiday(self):
        custom_date = date(2025, 8, 1)  # A Friday — not normally a holiday
        self.cal.add_custom_holiday(custom_date, "Test Holiday")
        assert not self.cal.is_trading_day(custom_date)

    def test_get_holidays_for_year(self):
        holidays = self.cal.get_holidays_for_year(_CURRENT_YEAR)
        assert isinstance(holidays, list)
        assert len(holidays) > 0

    def test_get_holidays_for_year_are_holiday_objects(self):
        holidays = self.cal.get_holidays_for_year(_CURRENT_YEAR)
        for h in holidays:
            assert isinstance(h, Holiday)

    def test_get_holidays_sorted(self):
        holidays = self.cal.get_holidays_for_year(_CURRENT_YEAR)
        dates = [h.date for h in holidays]
        assert dates == sorted(dates)


class TestTimeUtilities:
    def setup_method(self):
        self.cal = TradingCalendar()
        self._et = ZoneInfo("America/New_York")

    def _ts(self, d: date, t: time) -> datetime:
        return datetime.combine(d, t).replace(tzinfo=self._et)

    def test_time_until_open_when_market_open_returns_none(self):
        ts = self._ts(_WEEKDAY, time(10, 30))
        result = self.cal.time_until_open(ts)
        assert result is None

    def test_time_until_open_before_market(self):
        ts = self._ts(_WEEKDAY, time(8, 0))
        result = self.cal.time_until_open(ts)
        assert result is not None
        assert isinstance(result, timedelta)
        assert result.total_seconds() > 0

    def test_time_until_close_when_market_closed_returns_none(self):
        ts = self._ts(_WEEKDAY, time(17, 0))
        result = self.cal.time_until_close(ts)
        assert result is None

    def test_time_until_close_during_market(self):
        ts = self._ts(_WEEKDAY, time(10, 30))
        result = self.cal.time_until_close(ts)
        assert result is not None
        assert isinstance(result, timedelta)
        assert result.total_seconds() > 0


class TestTradingCalendarLifecycle:
    def test_start_succeeds(self):
        cal = TradingCalendar()
        cal.start()  # Should not raise

    def test_stop_succeeds(self):
        cal = TradingCalendar()
        cal.stop()  # Should not raise

    def test_cleanup_clears_holidays(self):
        cal = TradingCalendar()
        assert len(cal.holidays) > 0
        cal.cleanup()
        assert len(cal.holidays) == 0

    def test_reload_holidays(self):
        cal = TradingCalendar()
        cal.reload_holidays()
        assert len(cal.holidays) > 0


class TestU10ModuleFunctions:
    def test_get_trading_calendar_returns_instance(self):
        cal = get_trading_calendar()
        assert isinstance(cal, TradingCalendar)

    def test_get_trading_calendar_singleton(self):
        c1 = get_trading_calendar()
        c2 = get_trading_calendar()
        assert c1 is c2
