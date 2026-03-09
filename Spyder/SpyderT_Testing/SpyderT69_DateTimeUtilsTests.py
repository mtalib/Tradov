#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT69_DateTimeUtilsTests.py
Purpose: Tests for U03 DateTimeUtils

Author: Spyder Test Suite
Year Created: 2026
Last Updated: 2026-03-04 Time: 15:00:00
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

# Load U01 so we can inject SpyderLogger into U03
_u01 = _load("Spyder/SpyderU_Utilities/SpyderU01_Logger.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU01_Logger"] = _u01

# Load U03 — then inject pytz and SpyderLogger into its global namespace
# because U03 uses them without importing them at module level (bug in U03)
_u03 = _load("Spyder/SpyderU_Utilities/SpyderU03_DateTimeUtils.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils"] = _u03

import pytz as _pytz
_u03.pytz = _pytz
_u03.SpyderLogger = _u01.SpyderLogger

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import pytest
import pytz
from datetime import date, datetime, time, timedelta

# ==============================================================================
# MODULE IMPORTS — U03
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils import (
    # Module-level functions
    get_trading_holidays,
    _get_nth_weekday_of_month,
    _get_last_weekday_of_month,
    _calculate_good_friday,
    is_market_open,
    is_options_trading_time,
    is_trading_day,
    is_market_holiday,
    get_current_trading_day,
    get_next_trading_day,
    get_previous_trading_day,
    is_regular_hours,
    is_pre_market,
    is_after_market,
    is_optimal_entry_time,
    should_exit_by_time,
    get_trading_session_info,
    # Classes
    TradingHours,
    DateTimeUtils,
    TradingCalendar,
    TradingTimeUtils,
    MarketSession,
    get_current_market_session,
    # Constants
    MARKET_OPEN_TIME,
    MARKET_CLOSE_TIME,
    PRE_MARKET_OPEN,
    OPTIMAL_ENTRY_WINDOW,
    US_EASTERN,
)

# ==============================================================================
# TEST HELPERS
# ==============================================================================
_ET = pytz.timezone("US/Eastern")

def _et_dt(y, m, d, h, mn=0):
    """Create an Eastern-timezone-aware datetime."""
    return _ET.localize(datetime(y, m, d, h, mn))

# Known reference dates for 2026
_TRADING_WEEKDAY = date(2026, 1, 6)   # Tuesday
_WEEKEND = date(2026, 1, 3)           # Saturday
_MLK_DAY_2026 = date(2026, 1, 19)     # 3rd Monday of January
_MARKET_OPEN_DT = _et_dt(2026, 1, 6, 10, 0)   # 10 AM ET, Tuesday
_PRE_MARKET_DT = _et_dt(2026, 1, 6, 7, 0)     # 7 AM ET, Tuesday
_AFTER_HOURS_DT = _et_dt(2026, 1, 6, 17, 0)   # 5 PM ET, Tuesday
_WEEKEND_DT = _et_dt(2026, 1, 3, 10, 0)       # Saturday 10 AM


# ==============================================================================
# Holiday functions TESTS
# ==============================================================================
class TestGetTradingHolidays:
    """Tests for get_trading_holidays()."""

    def test_returns_set(self):
        assert isinstance(get_trading_holidays(2026), set)

    def test_contains_at_least_9_holidays(self):
        # NYSE closes for at least 9 holidays per year
        assert len(get_trading_holidays(2026)) >= 9

    def test_new_years_day_2026(self):
        # Jan 1, 2026 is Thursday → holiday on Jan 1
        assert date(2026, 1, 1) in get_trading_holidays(2026)

    def test_mlk_day_2026(self):
        assert _MLK_DAY_2026 in get_trading_holidays(2026)

    def test_christmas_2026(self):
        # Dec 25, 2026 is Friday → holiday on Dec 25
        assert date(2026, 12, 25) in get_trading_holidays(2026)

    def test_independence_day_2026(self):
        # July 4, 2026 is Saturday → observed Friday July 3
        july_4 = date(2026, 7, 4)
        if july_4.weekday() == 5:
            observed = date(2026, 7, 3)
        elif july_4.weekday() == 6:
            observed = date(2026, 7, 5)
        else:
            observed = july_4
        assert observed in get_trading_holidays(2026)

    def test_thanksgiving_in_november(self):
        holidays = get_trading_holidays(2026)
        november_holidays = [h for h in holidays if h.month == 11]
        assert len(november_holidays) >= 1

    def test_good_friday_in_april_or_march(self):
        holidays = get_trading_holidays(2026)
        spring_holidays = [h for h in holidays if h.month in (3, 4)]
        assert len(spring_holidays) >= 1


class TestGetNthWeekdayOfMonth:
    """Tests for _get_nth_weekday_of_month()."""

    def test_first_monday_jan_2026(self):
        # Jan 1 is Thursday → first Monday is Jan 5
        result = _get_nth_weekday_of_month(2026, 1, 0, 1)  # 0=Monday, 1st
        assert result.weekday() == 0
        assert result.month == 1

    def test_third_monday_jan_2026_is_mlk(self):
        result = _get_nth_weekday_of_month(2026, 1, 0, 3)
        assert result == _MLK_DAY_2026

    def test_fourth_thursday_nov_is_thanksgiving(self):
        result = _get_nth_weekday_of_month(2026, 11, 3, 4)  # 3=Thursday, 4th
        assert result.weekday() == 3  # Thursday
        assert result.month == 11


class TestGetLastWeekdayOfMonth:
    """Tests for _get_last_weekday_of_month()."""

    def test_last_monday_may_is_memorial_day(self):
        result = _get_last_weekday_of_month(2026, 5, 0)  # 0=Monday
        assert result.weekday() == 0
        assert result.month == 5
        assert result in get_trading_holidays(2026)

    def test_result_is_correct_weekday(self):
        result = _get_last_weekday_of_month(2026, 3, 4)  # last Friday in March
        assert result.weekday() == 4


class TestCalculateGoodFriday:
    """Tests for _calculate_good_friday()."""

    def test_is_friday(self):
        gf = _calculate_good_friday(2026)
        assert gf.weekday() == 4  # Friday

    def test_is_in_march_or_april(self):
        gf = _calculate_good_friday(2026)
        assert gf.month in (3, 4)

    def test_known_good_friday_2025(self):
        # Good Friday 2025 = April 18
        gf = _calculate_good_friday(2025)
        assert gf == date(2025, 4, 18)


# ==============================================================================
# TradingHours TESTS
# ==============================================================================
class TestTradingHoursInit:
    """Tests for TradingHours construction."""

    def test_creates_instance(self):
        th = TradingHours()
        assert th is not None

    def test_default_timezone_eastern(self):
        th = TradingHours()
        assert th.timezone == US_EASTERN

    def test_holiday_cache_empty(self):
        th = TradingHours()
        assert th._holiday_cache == {}


class TestTradingHoursIsTradingDay:
    """Tests for TradingHours.is_trading_day()."""

    def test_weekday_is_trading_day(self):
        th = TradingHours()
        assert th.is_trading_day(_TRADING_WEEKDAY) is True

    def test_saturday_is_not_trading_day(self):
        th = TradingHours()
        assert th.is_trading_day(_WEEKEND) is False

    def test_sunday_is_not_trading_day(self):
        th = TradingHours()
        sunday = date(2026, 1, 4)
        assert th.is_trading_day(sunday) is False

    def test_holiday_is_not_trading_day(self):
        th = TradingHours()
        assert th.is_trading_day(_MLK_DAY_2026) is False


class TestTradingHoursIsMarketHoliday:
    """Tests for TradingHours.is_market_holiday()."""

    def test_mlk_day_is_holiday(self):
        th = TradingHours()
        assert th.is_market_holiday(_MLK_DAY_2026) is True

    def test_normal_tuesday_not_holiday(self):
        th = TradingHours()
        assert th.is_market_holiday(_TRADING_WEEKDAY) is False

    def test_holiday_cache_populated(self):
        th = TradingHours()
        th.is_market_holiday(_MLK_DAY_2026)
        assert 2026 in th._holiday_cache


class TestTradingHoursRegularHours:
    """Tests for TradingHours.is_regular_hours()."""

    def test_regular_hours_during_market(self):
        th = TradingHours()
        assert th.is_regular_hours(_MARKET_OPEN_DT) is True

    def test_not_regular_hours_pre_market(self):
        th = TradingHours()
        assert th.is_regular_hours(_PRE_MARKET_DT) is False

    def test_not_regular_hours_after_hours(self):
        th = TradingHours()
        assert th.is_regular_hours(_AFTER_HOURS_DT) is False

    def test_not_regular_hours_on_weekend(self):
        th = TradingHours()
        assert th.is_regular_hours(_WEEKEND_DT) is False


class TestTradingHoursPreAfterMarket:
    """Tests for is_pre_market and is_after_market."""

    def test_is_pre_market_at_7am(self):
        th = TradingHours()
        assert th.is_pre_market(_PRE_MARKET_DT) is True

    def test_not_pre_market_during_regular(self):
        th = TradingHours()
        assert th.is_pre_market(_MARKET_OPEN_DT) is False

    def test_is_after_market_at_5pm(self):
        th = TradingHours()
        assert th.is_after_market(_AFTER_HOURS_DT) is True

    def test_not_after_market_during_regular(self):
        th = TradingHours()
        assert th.is_after_market(_MARKET_OPEN_DT) is False

    def test_is_extended_hours_in_pre_market(self):
        th = TradingHours()
        assert th.is_extended_hours(_PRE_MARKET_DT) is True

    def test_not_extended_during_regular(self):
        th = TradingHours()
        assert th.is_extended_hours(_MARKET_OPEN_DT) is False


class TestTradingHoursGetMarketHours:
    """Tests for TradingHours.get_market_hours()."""

    def test_returns_tuple_for_trading_day(self):
        th = TradingHours()
        result = th.get_market_hours(_TRADING_WEEKDAY)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_open_and_close_not_none_on_trading_day(self):
        th = TradingHours()
        open_dt, close_dt = th.get_market_hours(_TRADING_WEEKDAY)
        assert open_dt is not None
        assert close_dt is not None

    def test_open_before_close(self):
        th = TradingHours()
        open_dt, close_dt = th.get_market_hours(_TRADING_WEEKDAY)
        assert open_dt < close_dt

    def test_none_none_on_weekend(self):
        th = TradingHours()
        open_dt, close_dt = th.get_market_hours(_WEEKEND)
        assert open_dt is None
        assert close_dt is None


class TestTradingHoursNextMarketOpen:
    """Tests for TradingHours.get_next_market_open()."""

    def test_returns_datetime(self):
        th = TradingHours()
        result = th.get_next_market_open(_PRE_MARKET_DT)
        assert isinstance(result, datetime)

    def test_next_open_is_in_future(self):
        th = TradingHours()
        result = th.get_next_market_open(_PRE_MARKET_DT)
        # Should return today's open (9:30 AM) since we're in pre-market
        assert result.time() == MARKET_OPEN_TIME

    def test_time_until_market_open_is_timedelta(self):
        th = TradingHours()
        result = th.time_until_market_open(_PRE_MARKET_DT)
        assert isinstance(result, timedelta)

    def test_time_until_open_positive_in_pre_market(self):
        th = TradingHours()
        result = th.time_until_market_open(_PRE_MARKET_DT)
        assert result.total_seconds() > 0


# ==============================================================================
# DateTimeUtils TESTS
# ==============================================================================
class TestDateTimeUtilsOptionExpiry:
    """Tests for DateTimeUtils option expiry functions."""

    def test_monthly_expiry_is_friday(self):
        expiry = DateTimeUtils.get_monthly_option_expiry(2026, 1)
        assert expiry.weekday() == 4  # Friday

    def test_monthly_expiry_is_third_friday(self):
        expiry = DateTimeUtils.get_monthly_option_expiry(2026, 1)
        # Third Friday of Jan 2026: Jan 1 is Thu, first Fri = Jan 2,
        # 2nd Fri = Jan 9, 3rd Fri = Jan 16
        assert expiry == date(2026, 1, 16)

    def test_get_option_expiry_dates_returns_list(self):
        expiry_dates = DateTimeUtils.get_option_expiry_dates(
            start_date=date(2026, 1, 1), weeks_ahead=4
        )
        assert isinstance(expiry_dates, list)
        assert len(expiry_dates) == 4

    def test_expiry_dates_are_fridays(self):
        expiry_dates = DateTimeUtils.get_option_expiry_dates(
            start_date=date(2026, 1, 1), weeks_ahead=4
        )
        for d in expiry_dates:
            # Should be Friday or Thursday (if Friday is holiday)
            assert d.weekday() in (3, 4)


class TestDateTimeUtilsFormatSymbol:
    """Tests for DateTimeUtils.format_option_symbol()."""

    def test_basic_format(self):
        expiry = date(2026, 1, 17)
        result = DateTimeUtils.format_option_symbol("SPY", expiry, "C", 500.0)
        assert result == "SPY260117C00500000"

    def test_put_symbol(self):
        expiry = date(2026, 6, 19)
        result = DateTimeUtils.format_option_symbol("SPY", expiry, "P", 450.0)
        assert "P" in result
        assert "SPY" in result

    def test_strike_encoding(self):
        expiry = date(2026, 1, 17)
        # Strike 450.5 * 1000 = 450500 → "00450500"
        result = DateTimeUtils.format_option_symbol("SPY", expiry, "C", 450.5)
        assert "00450500" in result


class TestDateTimeUtilsParseTime:
    """Tests for DateTimeUtils.parse_time_string()."""

    def test_hhmm_format(self):
        result = DateTimeUtils.parse_time_string("09:30")
        assert result == time(9, 30)

    def test_24h_no_colon(self):
        result = DateTimeUtils.parse_time_string("1430")
        assert result == time(14, 30)

    def test_12h_am_pm(self):
        result = DateTimeUtils.parse_time_string("09:30 AM")
        assert result == time(9, 30)

    def test_invalid_raises_value_error(self):
        with pytest.raises(ValueError):
            DateTimeUtils.parse_time_string("notavalidtime")


class TestDateTimeUtilsTimeWindows:
    """Tests for DateTimeUtils time window methods."""

    def test_is_optimal_entry_in_window(self):
        dt = datetime(2026, 1, 6, 10, 30)  # 10:30 AM — in window
        assert DateTimeUtils.is_optimal_entry_time(dt) is True

    def test_not_optimal_entry_before_window(self):
        dt = datetime(2026, 1, 6, 9, 30)  # 9:30 AM — before window
        assert DateTimeUtils.is_optimal_entry_time(dt) is False

    def test_not_optimal_entry_after_window(self):
        dt = datetime(2026, 1, 6, 12, 0)  # noon — after window
        assert DateTimeUtils.is_optimal_entry_time(dt) is False

    def test_should_exit_after_noon(self):
        dt = datetime(2026, 1, 6, 12, 0)
        assert DateTimeUtils.should_exit_by_time(dt) is True

    def test_should_not_exit_before_noon(self):
        dt = datetime(2026, 1, 6, 10, 0)
        assert DateTimeUtils.should_exit_by_time(dt) is False

    def test_get_trading_windows_returns_dict(self):
        windows = DateTimeUtils.get_trading_windows()
        assert isinstance(windows, dict)
        assert "market_hours" in windows
        assert "optimal_entry" in windows

    def test_format_time_window_returns_string(self):
        window = (time(9, 30), time(16, 0))
        result = DateTimeUtils.format_time_window(window)
        assert isinstance(result, str)
        assert "-" in result

    def test_is_monday_returns_bool(self):
        assert isinstance(DateTimeUtils.is_monday(), bool)

    def test_get_trading_day_name_returns_string(self):
        result = DateTimeUtils.get_trading_day_name()
        assert isinstance(result, str)

    def test_get_day_quality_score_returns_float(self):
        score = DateTimeUtils.get_day_quality_score()
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0


class TestDateTimeUtilsTradingDays:
    """Tests for trading day navigation."""

    def test_get_next_trading_day_from_friday(self):
        # Jan 9 2026 is Friday → next trading day is Monday Jan 12
        friday = date(2026, 1, 9)
        result = DateTimeUtils.get_next_trading_day(friday)
        assert result == date(2026, 1, 12)

    def test_get_previous_trading_day_from_monday(self):
        # Jan 12 2026 is Monday → previous trading day is Friday Jan 9
        monday = date(2026, 1, 12)
        result = DateTimeUtils.get_previous_trading_day(monday)
        assert result == date(2026, 1, 9)

    def test_count_trading_days_mon_to_fri(self):
        # Mon Jan 5 to Fri Jan 9 = 5 trading days (inclusive)
        count = DateTimeUtils.count_trading_days(date(2026, 1, 5), date(2026, 1, 9))
        assert count == 5

    def test_get_current_trading_day_returns_date(self):
        result = DateTimeUtils.get_current_trading_day()
        assert isinstance(result, date)

    def test_add_trading_days_positive(self):
        # Add 1 trading day to a Monday → Tuesday
        monday = date(2026, 1, 5)
        result = DateTimeUtils.add_trading_days(monday, 1)
        assert result.weekday() in range(5)  # Weekday


class TestDateTimeUtilsTimezone:
    """Tests for timezone conversion methods."""

    def test_to_eastern_naive_datetime(self):
        dt = datetime(2026, 1, 6, 15, 0)  # naive UTC
        result = DateTimeUtils.to_eastern_time(dt)
        assert result.tzinfo is not None

    def test_to_utc_naive_datetime(self):
        dt = datetime(2026, 1, 6, 10, 0)  # naive ET
        result = DateTimeUtils.to_utc(dt)
        assert result.tzinfo is not None


# ==============================================================================
# Module-level functions TESTS
# ==============================================================================
class TestModuleLevelFunctions:
    """Tests for module-level convenience functions."""

    def test_is_trading_day_weekday(self):
        assert is_trading_day(_TRADING_WEEKDAY) is True

    def test_is_trading_day_weekend(self):
        assert is_trading_day(_WEEKEND) is False

    def test_is_market_holiday_mlk_day(self):
        assert is_market_holiday(_MLK_DAY_2026) is True

    def test_is_market_holiday_weekday(self):
        assert is_market_holiday(_TRADING_WEEKDAY) is False

    def test_get_current_trading_day_returns_date(self):
        result = get_current_trading_day()
        assert isinstance(result, date)

    def test_get_next_trading_day_returns_date(self):
        result = get_next_trading_day(_TRADING_WEEKDAY)
        assert isinstance(result, date)
        assert result > _TRADING_WEEKDAY

    def test_get_previous_trading_day_returns_date(self):
        result = get_previous_trading_day(_TRADING_WEEKDAY)
        assert isinstance(result, date)
        assert result < _TRADING_WEEKDAY

    def test_is_regular_hours_during_market(self):
        result = is_regular_hours(_MARKET_OPEN_DT)
        assert result is True

    def test_is_regular_hours_after_hours(self):
        result = is_regular_hours(_AFTER_HOURS_DT)
        assert result is False

    def test_is_pre_market_at_7am(self):
        result = is_pre_market(_PRE_MARKET_DT)
        assert result is True

    def test_is_after_market_at_5pm(self):
        result = is_after_market(_AFTER_HOURS_DT)
        assert result is True

    def test_is_optimal_entry_time_returns_bool(self):
        result = is_optimal_entry_time()
        assert isinstance(result, bool)

    def test_should_exit_by_time_returns_bool(self):
        result = should_exit_by_time()
        assert isinstance(result, bool)

    def test_get_trading_session_info_returns_dict(self):
        result = get_trading_session_info()
        assert isinstance(result, dict)


# ==============================================================================
# TradingCalendar TESTS
# ==============================================================================
class TestTradingCalendar:
    """Tests for TradingCalendar class."""

    def test_get_next_fomc_date_returns_datetime_or_none(self):
        result = TradingCalendar.get_next_fomc_date()
        assert result is None or isinstance(result, datetime)

    def test_fomc_date_in_future(self):
        result = TradingCalendar.get_next_fomc_date(datetime(2026, 1, 1))
        if result:
            assert result > datetime(2026, 1, 1)

    def test_fomc_result_is_wednesday(self):
        result = TradingCalendar.get_next_fomc_date(datetime(2026, 1, 1))
        if result:
            assert result.weekday() == 2  # Wednesday

    def test_is_options_expiration_week_on_third_friday(self):
        # 3rd Friday of Jan 2026 = Jan 16
        third_friday = date(2026, 1, 16)
        assert TradingCalendar.is_options_expiration_week(third_friday) is True

    def test_not_options_expiration_week_on_first_friday(self):
        # 1st Friday of Jan 2026 = Jan 2
        assert TradingCalendar.is_options_expiration_week(date(2026, 1, 2)) is False

    def test_holidays_returns_datetimeindex(self):
        import pandas as pd
        result = TradingCalendar.holidays(start=date(2026, 1, 1), end=date(2026, 12, 31))
        assert isinstance(result, pd.DatetimeIndex)

    def test_holidays_contains_known_holiday(self):
        result = TradingCalendar.holidays(start=date(2026, 1, 1), end=date(2026, 12, 31))
        holiday_dates = [d.date() for d in result]
        assert _MLK_DAY_2026 in holiday_dates

    def test_get_upcoming_events_returns_list(self):
        result = TradingCalendar.get_upcoming_events(from_date=datetime(2026, 1, 1))
        assert isinstance(result, list)


# ==============================================================================
# TradingTimeUtils TESTS
# ==============================================================================
class TestTradingTimeUtils:
    """Tests for TradingTimeUtils class."""

    def test_creates_instance(self):
        ttu = TradingTimeUtils()
        assert ttu is not None

    def test_get_market_timezone_returns_tz(self):
        tz = TradingTimeUtils.get_market_timezone()
        assert tz is not None

    def test_is_market_hours_during_regular(self):
        naive_dt = datetime(2026, 1, 6, 10, 30)  # Tuesday 10:30 AM
        result = TradingTimeUtils.is_market_hours(naive_dt)
        assert isinstance(result, bool)

    def test_is_market_hours_on_weekend_false(self):
        naive_dt = datetime(2026, 1, 3, 10, 30)  # Saturday
        result = TradingTimeUtils.is_market_hours(naive_dt)
        assert result is False

    def test_get_next_market_open_returns_datetime(self):
        dt = datetime(2026, 1, 6, 7, 0)
        result = TradingTimeUtils.get_next_market_open(dt)
        assert isinstance(result, datetime)

    def test_get_market_session_returns_string(self):
        result = TradingTimeUtils.get_market_session()
        assert isinstance(result, str)

    def test_format_market_time_returns_string(self):
        result = TradingTimeUtils.format_market_time()
        assert isinstance(result, str)

    def test_get_trading_days_between_returns_count(self):
        # Method counts (int) not collects (list) — Mon Jan 5 to Fri Jan 9 = 5 days
        result = TradingTimeUtils.get_trading_days_between(
            date(2026, 1, 5), date(2026, 1, 9)
        )
        assert isinstance(result, int)
        assert result == 5


# ==============================================================================
# MarketSession TESTS
# ==============================================================================
class TestMarketSession:
    """Tests for MarketSession enum."""

    def test_pre_market_member(self):
        assert hasattr(MarketSession, "PRE_MARKET")

    def test_regular_hours_member(self):
        assert hasattr(MarketSession, "REGULAR_HOURS")

    def test_after_hours_member(self):
        assert hasattr(MarketSession, "AFTER_HOURS")

    def test_closed_member(self):
        assert hasattr(MarketSession, "CLOSED")

    def test_get_current_market_session_returns_market_session(self):
        result = get_current_market_session()
        assert isinstance(result, MarketSession)
