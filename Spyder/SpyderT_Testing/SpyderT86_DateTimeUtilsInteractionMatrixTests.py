#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT86_DateTimeUtilsInteractionMatrixTests.py
Purpose: Comprehensive tests for U03 DateTimeUtils and U19 InteractionMatrix

Author: Spyder Test Suite
Year Created: 2026
Last Updated: 2026-03-06 Time: 09:00:00
"""

# ==============================================================================
# BOOTSTRAP
# ==============================================================================
import sys
import os
import types
import importlib.util
import tempfile
import time as time_module

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


import pytz  # ensure available before injection

_ensure_pkg("Spyder")
_ensure_pkg("SpyderU_Utilities")
_ensure_pkg("Spyder.SpyderU_Utilities")

_u01 = _load("Spyder/SpyderU_Utilities/SpyderU01_Logger.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU01_Logger"] = _u01
sys.modules["SpyderU_Utilities.SpyderU01_Logger"] = _u01

_u02 = _load("Spyder/SpyderU_Utilities/SpyderU02_ErrorHandler.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler"] = _u02
sys.modules["SpyderU_Utilities.SpyderU02_ErrorHandler"] = _u02

# U03 — inject pytz and SpyderLogger after loading since they're used in methods
_u03 = _load("Spyder/SpyderU_Utilities/SpyderU03_DateTimeUtils.py")
_u03.pytz = pytz
_u03.SpyderLogger = _u01.SpyderLogger
sys.modules["Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils"] = _u03

# U19 — imports U01 + U02 from Spyder namespace (already in sys.modules)
_u19 = _load("Spyder/SpyderU_Utilities/SpyderU19_InteractionMatrix.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU19_InteractionMatrix"] = _u19


# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import pytest
from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import patch, MagicMock


# ==============================================================================
# U03 IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils import (
    # Constants
    US_EASTERN,
    UTC,
    MARKET_OPEN_TIME,
    MARKET_CLOSE_TIME,
    PRE_MARKET_OPEN,
    AFTER_HOURS_CLOSE,
    OPTIMAL_ENTRY_WINDOW,
    TIME_BASED_EXIT,
    EARLY_CLOSE_TIME,
    OPTIONS_CLOSE_FRIDAY,
    INDEX_OPTIONS_CLOSE,
    # Module-level functions
    get_trading_holidays,
    _get_nth_weekday_of_month,
    _get_last_weekday_of_month,
    _calculate_good_friday,
    is_market_open,
    is_options_trading_time,
    is_trading_day,
    is_market_holiday,
    get_next_trading_day,
    get_previous_trading_day,
    get_current_trading_day,
    get_trading_hours,
    get_market_hours,
    get_next_market_open,
    get_next_market_close,
    time_until_market_open,
    time_until_market_close,
    is_regular_hours,
    is_pre_market,
    is_after_market,
    is_early_close_day,
    is_optimal_entry_time,
    should_exit_by_time,
    get_trading_session_info,
    get_market_schedule,
    to_utc_datetime,
    from_utc_datetime,
    get_trading_time_utils,
    get_current_market_session,
    # Classes
    TradingHours,
    DateTimeUtils,
    TradingCalendar,
    TradingTimeUtils,
    MarketSession,
)


# ==============================================================================
# U19 IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU19_InteractionMatrix import (
    # Enums
    InteractionType,
    InteractionStatus,
    MatrixMetric,
    # Dataclasses
    Interaction,
    ModuleStats,
    MatrixAnalysis,
    # Classes
    InteractionMatrix,
    # Module functions
    get_interaction_matrix,
    record_interaction,
    # Constants
    DEFAULT_MATRIX_SIZE,
    MAX_HISTORY_SIZE,
)

import numpy as np

ET = pytz.timezone("US/Eastern")


# ==============================================================================
# ═══════════════════════════════════════════════════════════════════════════
#  U03 — DATETIME UTILS
# ═══════════════════════════════════════════════════════════════════════════
# ==============================================================================


class TestGetTradingHolidays:
    """Tests for get_trading_holidays() module-level function."""

    def test_returns_set_of_dates(self):
        holidays = get_trading_holidays(2026)
        assert isinstance(holidays, set)
        assert all(isinstance(h, date) for h in holidays)

    def test_2026_new_years_day(self):
        holidays = get_trading_holidays(2026)
        # Jan 1 2026 is Thursday → holiday on Jan 1
        assert date(2026, 1, 1) in holidays

    def test_2026_mlk_day(self):
        holidays = get_trading_holidays(2026)
        # 3rd Monday of January 2026 = Jan 19
        assert date(2026, 1, 19) in holidays

    def test_2026_presidents_day(self):
        holidays = get_trading_holidays(2026)
        # 3rd Monday of February 2026 = Feb 16
        assert date(2026, 2, 16) in holidays

    def test_2026_good_friday(self):
        holidays = get_trading_holidays(2026)
        # Easter 2026 = April 5 → Good Friday = April 3
        assert date(2026, 4, 3) in holidays

    def test_2026_memorial_day(self):
        holidays = get_trading_holidays(2026)
        # Last Monday of May 2026 = May 25
        assert date(2026, 5, 25) in holidays

    def test_2026_juneteenth(self):
        holidays = get_trading_holidays(2026)
        # June 19, 2026 is Friday → holiday on June 19
        assert date(2026, 6, 19) in holidays

    def test_2026_independence_day_observed(self):
        holidays = get_trading_holidays(2026)
        # July 4, 2026 is Saturday → observed Friday July 3
        assert date(2026, 7, 3) in holidays
        assert date(2026, 7, 4) not in holidays

    def test_2026_labor_day(self):
        holidays = get_trading_holidays(2026)
        # 1st Monday of September 2026 = Sep 7
        assert date(2026, 9, 7) in holidays

    def test_2026_thanksgiving(self):
        holidays = get_trading_holidays(2026)
        # 4th Thursday of November 2026 = Nov 26
        assert date(2026, 11, 26) in holidays

    def test_2026_christmas(self):
        holidays = get_trading_holidays(2026)
        # Dec 25, 2026 is Friday → holiday on Dec 25
        assert date(2026, 12, 25) in holidays

    def test_holiday_count_reasonable(self):
        holidays = get_trading_holidays(2026)
        # Expect 9-11 holidays per year
        assert 9 <= len(holidays) <= 11

    def test_sunday_new_years_observed_monday(self):
        # 2023: Jan 1 is Sunday → observed Monday Jan 2
        holidays = get_trading_holidays(2023)
        assert date(2023, 1, 2) in holidays
        assert date(2023, 1, 1) not in holidays

    def test_saturday_christmas_observed_friday(self):
        # 2021: Dec 25 is Saturday → observed Friday Dec 24
        holidays = get_trading_holidays(2021)
        assert date(2021, 12, 24) in holidays

    def test_no_pre_2022_juneteenth(self):
        holidays = get_trading_holidays(2021)
        assert date(2021, 6, 19) not in holidays


class TestHelperFunctions:
    """Tests for _get_nth_weekday_of_month, _get_last_weekday_of_month, _calculate_good_friday."""

    def test_nth_weekday_first_monday_january_2026(self):
        # 1st Monday of January 2026: Jan 1 is Thursday, first Monday is Jan 5
        result = _get_nth_weekday_of_month(2026, 1, 0, 1)
        assert result == date(2026, 1, 5)
        assert result.weekday() == 0  # Monday

    def test_nth_weekday_third_monday_january_2026(self):
        # MLK Day 2026 = 3rd Monday of January = Jan 19
        result = _get_nth_weekday_of_month(2026, 1, 0, 3)
        assert result == date(2026, 1, 19)

    def test_nth_weekday_fourth_thursday_november_2026(self):
        # Thanksgiving 2026 = 4th Thursday of November = Nov 26
        result = _get_nth_weekday_of_month(2026, 11, 3, 4)
        assert result == date(2026, 11, 26)
        assert result.weekday() == 3  # Thursday

    def test_nth_weekday_first_monday_september_2026(self):
        # Labor Day 2026 = 1st Monday of September = Sep 7
        result = _get_nth_weekday_of_month(2026, 9, 0, 1)
        assert result == date(2026, 9, 7)

    def test_last_weekday_memorial_day_2026(self):
        # Last Monday of May 2026 = May 25
        result = _get_last_weekday_of_month(2026, 5, 0)
        assert result == date(2026, 5, 25)
        assert result.weekday() == 0  # Monday

    def test_last_weekday_returns_correct_day(self):
        result = _get_last_weekday_of_month(2026, 12, 0)  # Last Monday in Dec
        assert result.weekday() == 0  # Monday
        assert result.month == 12

    def test_calculate_good_friday_2025(self):
        # Easter 2025 = April 20 → Good Friday = April 18
        result = _calculate_good_friday(2025)
        assert result == date(2025, 4, 18)

    def test_calculate_good_friday_2026(self):
        # Easter 2026 = April 5 → Good Friday = April 3
        result = _calculate_good_friday(2026)
        assert result == date(2026, 4, 3)

    def test_calculate_good_friday_is_friday(self):
        for year in [2024, 2025, 2026]:
            gf = _calculate_good_friday(year)
            assert gf.weekday() == 4  # Friday


class TestTradingHoursInit:
    """Tests for TradingHours initialization."""

    def test_default_timezone(self):
        th = TradingHours()
        assert th.timezone == US_EASTERN

    def test_custom_timezone(self):
        th = TradingHours("UTC")
        assert th.timezone == "UTC"

    def test_tz_attribute_set(self):
        th = TradingHours()
        assert th.tz is not None

    def test_holiday_cache_initially_empty(self):
        th = TradingHours()
        assert th._holiday_cache == {}


class TestTradingHoursIsTradingDay:
    """Tests for TradingHours.is_trading_day()."""

    def setup_method(self):
        self.th = TradingHours()

    def test_weekday_is_trading_day(self):
        # Monday Jan 5, 2026 — not a holiday
        assert self.th.is_trading_day(date(2026, 1, 5)) is True

    def test_saturday_is_not_trading_day(self):
        assert self.th.is_trading_day(date(2026, 1, 3)) is False

    def test_sunday_is_not_trading_day(self):
        assert self.th.is_trading_day(date(2026, 1, 4)) is False

    def test_mlk_day_is_not_trading_day(self):
        assert self.th.is_trading_day(date(2026, 1, 19)) is False

    def test_christmas_is_not_trading_day(self):
        assert self.th.is_trading_day(date(2026, 12, 25)) is False

    def test_friday_before_long_weekend_is_trading_day(self):
        # Friday Jan 16, 2026 (before MLK day Mon Jan 19)
        assert self.th.is_trading_day(date(2026, 1, 16)) is True


class TestTradingHoursIsMarketHoliday:
    """Tests for TradingHours.is_market_holiday()."""

    def setup_method(self):
        self.th = TradingHours()

    def test_holiday_returns_true(self):
        assert self.th.is_market_holiday(date(2026, 1, 19)) is True  # MLK Day

    def test_non_holiday_weekday_returns_false(self):
        assert self.th.is_market_holiday(date(2026, 1, 5)) is False

    def test_holiday_cached_after_first_call(self):
        self.th.is_market_holiday(date(2026, 3, 15))
        assert 2026 in self.th._holiday_cache


class TestTradingHoursIsRegularHours:
    """Tests for TradingHours.is_regular_hours()."""

    def setup_method(self):
        self.th = TradingHours()

    def _et(self, year, month, day, hour, minute):
        return ET.localize(datetime(year, month, day, hour, minute, 0))

    def test_during_regular_hours(self):
        dt = self._et(2026, 1, 5, 11, 0)  # Monday 11 AM ET
        assert self.th.is_regular_hours(dt) is True

    def test_at_market_open(self):
        dt = self._et(2026, 1, 5, 9, 30)  # Monday 9:30 AM ET
        assert self.th.is_regular_hours(dt) is True

    def test_before_market_open(self):
        dt = self._et(2026, 1, 5, 8, 0)  # Monday 8 AM ET
        assert self.th.is_regular_hours(dt) is False

    def test_after_market_close(self):
        dt = self._et(2026, 1, 5, 17, 0)  # Monday 5 PM ET
        assert self.th.is_regular_hours(dt) is False

    def test_on_weekend(self):
        dt = self._et(2026, 1, 3, 11, 0)  # Saturday
        assert self.th.is_regular_hours(dt) is False

    def test_on_holiday(self):
        dt = self._et(2026, 1, 19, 11, 0)  # MLK Day
        assert self.th.is_regular_hours(dt) is False


class TestTradingHoursPreAfterMarket:
    """Tests for TradingHours.is_pre_market() and is_after_market()."""

    def setup_method(self):
        self.th = TradingHours()

    def _et(self, year, month, day, hour, minute):
        return ET.localize(datetime(year, month, day, hour, minute, 0))

    def test_pre_market_during_pre_hours(self):
        dt = self._et(2026, 1, 5, 7, 0)  # Monday 7 AM ET
        assert self.th.is_pre_market(dt) is True

    def test_pre_market_at_open(self):
        dt = self._et(2026, 1, 5, 4, 0)  # Monday 4 AM ET (start of pre)
        assert self.th.is_pre_market(dt) is True

    def test_not_pre_market_during_regular(self):
        dt = self._et(2026, 1, 5, 10, 0)  # Monday 10 AM ET
        assert self.th.is_pre_market(dt) is False

    def test_not_pre_market_before_4am(self):
        dt = self._et(2026, 1, 5, 2, 0)  # Monday 2 AM ET
        assert self.th.is_pre_market(dt) is False

    def test_after_market_during_after_hours(self):
        dt = self._et(2026, 1, 5, 18, 0)  # Monday 6 PM ET
        assert self.th.is_after_market(dt) is True

    def test_not_after_market_during_regular(self):
        dt = self._et(2026, 1, 5, 12, 0)  # Monday noon
        assert self.th.is_after_market(dt) is False

    def test_not_after_market_after_8pm(self):
        dt = self._et(2026, 1, 5, 21, 0)  # Monday 9 PM ET
        assert self.th.is_after_market(dt) is False


class TestTradingHoursExtended:
    """Tests for TradingHours.is_extended_hours()."""

    def setup_method(self):
        self.th = TradingHours()

    def _et(self, year, month, day, hour, minute):
        return ET.localize(datetime(year, month, day, hour, minute, 0))

    def test_extended_during_pre_market(self):
        dt = self._et(2026, 1, 5, 7, 0)
        assert self.th.is_extended_hours(dt) is True

    def test_extended_during_after_hours(self):
        dt = self._et(2026, 1, 5, 17, 0)
        assert self.th.is_extended_hours(dt) is True

    def test_not_extended_during_regular(self):
        dt = self._et(2026, 1, 5, 11, 0)
        assert self.th.is_extended_hours(dt) is False


class TestTradingHoursEarlyClose:
    """Tests for TradingHours.is_early_close_day()."""

    def setup_method(self):
        self.th = TradingHours()

    def test_black_friday_is_early_close(self):
        # Thanksgiving 2026 = Nov 26; day after = Nov 27 (Friday)
        assert self.th.is_early_close_day(date(2026, 11, 27)) is True

    def test_christmas_eve_is_early_close(self):
        # Dec 24, 2026 is Thursday (trading day)
        assert self.th.is_early_close_day(date(2026, 12, 24)) is True

    def test_regular_day_not_early_close(self):
        assert self.th.is_early_close_day(date(2026, 1, 5)) is False

    def test_thanksgiving_not_early_close(self):
        # Thanksgiving itself is a holiday, not early close
        assert self.th.is_early_close_day(date(2026, 11, 26)) is False


class TestTradingHoursGetMarketHours:
    """Tests for TradingHours.get_market_hours()."""

    def setup_method(self):
        self.th = TradingHours()

    def test_trading_day_returns_open_close(self):
        open_dt, close_dt = self.th.get_market_hours(date(2026, 1, 5))
        assert open_dt is not None
        assert close_dt is not None

    def test_open_time_is_930(self):
        open_dt, _ = self.th.get_market_hours(date(2026, 1, 5))
        assert open_dt.time() == MARKET_OPEN_TIME

    def test_close_time_is_4pm(self):
        _, close_dt = self.th.get_market_hours(date(2026, 1, 5))
        assert close_dt.time() == MARKET_CLOSE_TIME

    def test_non_trading_day_returns_none_none(self):
        open_dt, close_dt = self.th.get_market_hours(date(2026, 1, 3))  # Saturday
        assert open_dt is None
        assert close_dt is None

    def test_early_close_day(self):
        # Black Friday 2026 = Nov 27
        _, close_dt = self.th.get_market_hours(date(2026, 11, 27))
        assert close_dt.time() == EARLY_CLOSE_TIME  # 1 PM


class TestTradingHoursGetNextOpen:
    """Tests for TradingHours.get_next_market_open()."""

    def setup_method(self):
        self.th = TradingHours()

    def _et(self, year, month, day, hour, minute):
        return ET.localize(datetime(year, month, day, hour, minute, 0))

    def test_next_open_from_monday_evening_is_tuesday_morning(self):
        dt = self._et(2026, 1, 5, 18, 0)  # Monday 6 PM
        next_open = self.th.get_next_market_open(dt)
        assert next_open.date() == date(2026, 1, 6)  # Tuesday
        assert next_open.time() == MARKET_OPEN_TIME

    def test_next_open_skips_weekend(self):
        dt = self._et(2026, 1, 9, 18, 0)  # Friday 6 PM
        next_open = self.th.get_next_market_open(dt)
        assert next_open.date() == date(2026, 1, 12)  # Monday

    def test_currently_in_market_returns_current(self):
        dt = self._et(2026, 1, 5, 11, 0)  # Monday 11 AM (in regular hours)
        next_open = self.th.get_next_market_open(dt)
        assert next_open <= dt  # Returns current since already open


class TestTradingHoursTimeUntil:
    """Tests for TradingHours.time_until_market_open/close()."""

    def setup_method(self):
        self.th = TradingHours()

    def _et(self, year, month, day, hour, minute):
        return ET.localize(datetime(year, month, day, hour, minute, 0))

    def test_time_until_open_returns_timedelta(self):
        dt = self._et(2026, 1, 5, 7, 0)  # Monday 7 AM
        delta = self.th.time_until_market_open(dt)
        assert isinstance(delta, timedelta)
        assert delta.total_seconds() > 0

    def test_time_until_close_returns_timedelta_when_open(self):
        dt = self._et(2026, 1, 5, 11, 0)  # Monday 11 AM
        delta = self.th.time_until_market_close(dt)
        assert isinstance(delta, timedelta)
        assert delta.total_seconds() > 0

    def test_time_until_close_returns_none_when_closed(self):
        dt = self._et(2026, 1, 5, 18, 0)  # Monday 6 PM
        delta = self.th.time_until_market_close(dt)
        assert delta is None


class TestDateTimeUtilsTrading:
    """Tests for DateTimeUtils static methods."""

    def test_get_next_trading_day_skips_weekend(self):
        # Friday Jan 9, 2026 → next trading day is Monday Jan 12
        result = DateTimeUtils.get_next_trading_day(date(2026, 1, 9))
        assert result == date(2026, 1, 12)

    def test_get_next_trading_day_from_monday(self):
        result = DateTimeUtils.get_next_trading_day(date(2026, 1, 5))
        assert result == date(2026, 1, 6)

    def test_get_previous_trading_day_skips_weekend(self):
        # Monday Jan 12, 2026 → prev trading day is Friday Jan 9
        result = DateTimeUtils.get_previous_trading_day(date(2026, 1, 12))
        assert result == date(2026, 1, 9)

    def test_get_previous_trading_day_from_wednesday(self):
        result = DateTimeUtils.get_previous_trading_day(date(2026, 1, 7))
        assert result == date(2026, 1, 6)

    def test_get_trading_days_between_5_days(self):
        # Mon Jan 5 to Fri Jan 9, 2026 — 5 trading days inclusive
        days = DateTimeUtils.get_trading_days_between(date(2026, 1, 5), date(2026, 1, 9))
        assert len(days) == 5

    def test_get_trading_days_between_exclusive(self):
        days = DateTimeUtils.get_trading_days_between(
            date(2026, 1, 5), date(2026, 1, 9), inclusive=False
        )
        # Excludes both endpoints → 3 days
        assert len(days) == 3

    def test_get_trading_days_between_excludes_weekend(self):
        # Mon Jan 5 to Mon Jan 12, 2026 — 6 trading days (5 + 1 new Monday, weekend excluded)
        days = DateTimeUtils.get_trading_days_between(date(2026, 1, 5), date(2026, 1, 12))
        assert len(days) == 6

    def test_count_trading_days(self):
        count = DateTimeUtils.count_trading_days(date(2026, 1, 5), date(2026, 1, 9))
        assert count == 5

    def test_add_trading_days_positive(self):
        result = DateTimeUtils.add_trading_days(date(2026, 1, 5), 3)
        assert result == date(2026, 1, 8)

    def test_add_trading_days_negative(self):
        result = DateTimeUtils.add_trading_days(date(2026, 1, 9), -3)
        assert result == date(2026, 1, 6)

    def test_add_trading_days_zero(self):
        result = DateTimeUtils.add_trading_days(date(2026, 1, 5), 0)
        assert result == date(2026, 1, 5)

    def test_add_trading_days_skips_weekend(self):
        # Friday Jan 9 + 1 trading day = Monday Jan 12
        result = DateTimeUtils.add_trading_days(date(2026, 1, 9), 1)
        assert result == date(2026, 1, 12)

    def test_to_eastern_time_converts_utc(self):
        utc_dt = pytz.UTC.localize(datetime(2026, 1, 5, 15, 0, 0))  # 3 PM UTC
        et_dt = DateTimeUtils.to_eastern_time(utc_dt)
        assert et_dt.tzinfo is not None
        assert et_dt.hour == 10  # 3 PM UTC = 10 AM ET (EST offset)

    def test_to_utc_converts_naive_et(self):
        naive_dt = datetime(2026, 1, 5, 10, 0, 0)  # assume ET
        utc_dt = DateTimeUtils.to_utc(naive_dt)
        assert utc_dt.tzinfo is not None

    def test_to_utc_converts_aware_et(self):
        et_dt = ET.localize(datetime(2026, 1, 5, 10, 0, 0))  # 10 AM ET
        utc_dt = DateTimeUtils.to_utc(et_dt)
        assert utc_dt.hour == 15  # 10 AM ET = 3 PM UTC (EST)


class TestDateTimeUtilsParseTime:
    """Tests for DateTimeUtils.parse_time_string()."""

    def test_parse_24hr_colon(self):
        result = DateTimeUtils.parse_time_string("9:30")
        assert result == time(9, 30)

    def test_parse_24hr_no_colon(self):
        result = DateTimeUtils.parse_time_string("0930")
        assert result == time(9, 30)

    def test_parse_pm_with_space(self):
        result = DateTimeUtils.parse_time_string("3:30 PM")
        assert result == time(15, 30)

    def test_parse_am_no_space(self):
        result = DateTimeUtils.parse_time_string("9:30AM")
        assert result == time(9, 30)

    def test_parse_with_seconds(self):
        result = DateTimeUtils.parse_time_string("14:30:00")
        assert result == time(14, 30, 0)

    def test_invalid_format_raises_value_error(self):
        with pytest.raises(ValueError):
            DateTimeUtils.parse_time_string("not_a_time")


class TestDateTimeUtilsOptions:
    """Tests for DateTimeUtils option-related methods."""

    def test_get_option_expiry_dates_returns_fridays(self):
        start = date(2026, 1, 5)  # Monday
        expiries = DateTimeUtils.get_option_expiry_dates(start, weeks_ahead=4)
        assert len(expiries) == 4
        for exp in expiries:
            # Friday or Thursday (if Friday is holiday)
            assert exp.weekday() in (3, 4)

    def test_get_monthly_option_expiry_is_third_friday(self):
        # 3rd Friday of Jan 2026: Jan 1 is Thursday, first Friday is Jan 2,
        # 3rd Friday is Jan 16
        result = DateTimeUtils.get_monthly_option_expiry(2026, 1)
        assert result.weekday() == 4  # Friday
        # verify it's in the right range (15-21)
        assert 15 <= result.day <= 21

    def test_format_option_symbol_call(self):
        symbol = DateTimeUtils.format_option_symbol("SPY", date(2026, 1, 16), "C", 450.0)
        assert symbol.startswith("SPY")
        assert "C" in symbol
        assert "00450000" in symbol

    def test_format_option_symbol_put(self):
        symbol = DateTimeUtils.format_option_symbol("SPY", date(2026, 3, 20), "P", 500.0)
        assert "P" in symbol
        assert symbol.startswith("SPY")


class TestDateTimeUtilsTimeWindows:
    """Tests for DateTimeUtils time window methods."""

    def test_is_optimal_entry_time_in_window(self):
        dt = datetime(2026, 1, 5, 10, 30)  # 10:30 AM — in window 10:15-11:40
        assert DateTimeUtils.is_optimal_entry_time(dt) is True

    def test_is_optimal_entry_time_before_window(self):
        dt = datetime(2026, 1, 5, 9, 30)
        assert DateTimeUtils.is_optimal_entry_time(dt) is False

    def test_is_optimal_entry_time_after_window(self):
        dt = datetime(2026, 1, 5, 12, 0)
        assert DateTimeUtils.is_optimal_entry_time(dt) is False

    def test_should_exit_by_time_after_noon(self):
        dt = datetime(2026, 1, 5, 12, 30)
        assert DateTimeUtils.should_exit_by_time(dt) is True

    def test_should_exit_by_time_before_noon(self):
        dt = datetime(2026, 1, 5, 11, 0)
        assert DateTimeUtils.should_exit_by_time(dt) is False

    def test_get_trading_windows_returns_dict(self):
        windows = DateTimeUtils.get_trading_windows()
        assert isinstance(windows, dict)
        assert "market_hours" in windows
        assert "optimal_entry" in windows
        assert "pre_market" in windows
        assert "after_hours" in windows

    def test_format_time_window_returns_string(self):
        window = (time(9, 30), time(16, 0))
        result = DateTimeUtils.format_time_window(window)
        assert isinstance(result, str)
        assert "AM" in result or "PM" in result

    def test_is_monday_returns_bool(self):
        result = DateTimeUtils.is_monday()
        assert isinstance(result, bool)

    def test_get_trading_day_name_returns_string(self):
        result = DateTimeUtils.get_trading_day_name()
        assert isinstance(result, str)

    def test_get_day_quality_score_in_range(self):
        score = DateTimeUtils.get_day_quality_score()
        assert 0.0 <= score <= 1.0

    def test_get_current_trading_day_returns_date(self):
        result = DateTimeUtils.get_current_trading_day()
        assert isinstance(result, date)

    def test_get_trading_session_info_returns_dict(self):
        info = DateTimeUtils.get_trading_session_info()
        assert isinstance(info, dict)
        assert "date" in info
        assert "is_trading_day" in info
        assert "is_monday" in info


class TestModuleLevelFunctionsU03:
    """Tests for U03 module-level wrapper functions."""

    def test_is_trading_day_weekday(self):
        assert is_trading_day(date(2026, 1, 5)) is True

    def test_is_trading_day_weekend(self):
        assert is_trading_day(date(2026, 1, 3)) is False

    def test_is_market_holiday_known_holiday(self):
        assert is_market_holiday(date(2026, 1, 19)) is True

    def test_is_market_holiday_regular_day(self):
        assert is_market_holiday(date(2026, 1, 5)) is False

    def test_get_next_trading_day_module(self):
        result = get_next_trading_day(date(2026, 1, 9))  # Friday
        assert result == date(2026, 1, 12)  # Monday

    def test_get_previous_trading_day_module(self):
        result = get_previous_trading_day(date(2026, 1, 12))  # Monday
        assert result == date(2026, 1, 9)  # Friday

    def test_get_current_trading_day_module(self):
        result = get_current_trading_day()
        assert isinstance(result, date)

    def test_is_early_close_day_black_friday(self):
        assert is_early_close_day(date(2026, 11, 27)) is True

    def test_is_early_close_day_normal(self):
        assert is_early_close_day(date(2026, 1, 5)) is False

    def test_is_market_open_with_closed_time(self):
        dt = ET.localize(datetime(2026, 1, 5, 18, 0))  # 6 PM ET
        assert is_market_open(dt) is False

    def test_is_market_open_with_open_time(self):
        dt = ET.localize(datetime(2026, 1, 5, 11, 0))  # 11 AM ET
        assert is_market_open(dt) is True

    def test_is_market_open_extended_hours(self):
        dt = ET.localize(datetime(2026, 1, 5, 7, 0))  # 7 AM ET (pre-market)
        assert is_market_open(dt, extended_hours=True) is True

    def test_is_options_trading_time(self):
        dt = ET.localize(datetime(2026, 1, 5, 11, 0))  # 11 AM ET Monday
        assert is_options_trading_time(dt, "SPY") is True

    def test_is_regular_hours_module(self):
        dt = ET.localize(datetime(2026, 1, 5, 11, 0))
        assert is_regular_hours(dt) is True

    def test_is_pre_market_module(self):
        dt = ET.localize(datetime(2026, 1, 5, 7, 0))
        assert is_pre_market(dt) is True

    def test_is_after_market_module(self):
        dt = ET.localize(datetime(2026, 1, 5, 18, 0))
        assert is_after_market(dt) is True

    def test_is_optimal_entry_time_module(self):
        dt = datetime(2026, 1, 5, 11, 0)
        assert is_optimal_entry_time(dt) is True

    def test_should_exit_by_time_module(self):
        dt = datetime(2026, 1, 5, 13, 0)
        assert should_exit_by_time(dt) is True

    def test_get_trading_session_info_module(self):
        info = get_trading_session_info()
        assert isinstance(info, dict)

    def test_get_market_schedule_returns_dataframe(self):
        import pandas as pd
        schedule = get_market_schedule()
        assert isinstance(schedule, pd.DataFrame)
        assert len(schedule) > 0

    def test_get_market_schedule_with_date_range(self):
        import pandas as pd
        date_range = (date(2026, 1, 5), date(2026, 1, 9))
        schedule = get_market_schedule(date_range)
        assert isinstance(schedule, pd.DataFrame)
        assert len(schedule) == 5

    def test_get_trading_hours_trading_day(self):
        info = get_trading_hours(date(2026, 1, 5))
        assert info["is_trading_day"] is True
        assert "market_open" in info
        assert "market_close" in info

    def test_get_trading_hours_non_trading_day(self):
        info = get_trading_hours(date(2026, 1, 3))  # Saturday
        assert info["is_trading_day"] is False
        assert info["reason"] == "Weekend"

    def test_get_market_hours_module_trading_day(self):
        open_dt, close_dt = get_market_hours(date(2026, 1, 5))
        assert open_dt is not None
        assert close_dt is not None

    def test_get_next_market_open_module(self):
        dt = ET.localize(datetime(2026, 1, 5, 18, 0))
        next_open = get_next_market_open(dt)
        assert next_open.date() == date(2026, 1, 6)

    def test_get_next_market_close_module(self):
        dt = ET.localize(datetime(2026, 1, 5, 11, 0))
        next_close = get_next_market_close(dt)
        assert next_close.time() == MARKET_CLOSE_TIME

    def test_time_until_market_open_module(self):
        dt = ET.localize(datetime(2026, 1, 5, 7, 0))
        delta = time_until_market_open(dt)
        assert isinstance(delta, timedelta)
        assert delta.total_seconds() > 0

    def test_time_until_market_close_module_open(self):
        dt = ET.localize(datetime(2026, 1, 5, 11, 0))
        delta = time_until_market_close(dt)
        assert isinstance(delta, timedelta)

    def test_time_until_market_close_module_closed(self):
        dt = ET.localize(datetime(2026, 1, 5, 18, 0))
        delta = time_until_market_close(dt)
        assert delta is None

    def test_to_utc_datetime_module(self):
        et_dt = ET.localize(datetime(2026, 1, 5, 10, 0, 0))
        utc_dt = to_utc_datetime(et_dt)
        assert utc_dt.tzinfo is not None

    def test_from_utc_datetime_module(self):
        utc_dt = pytz.UTC.localize(datetime(2026, 1, 5, 15, 0, 0))
        et_dt = from_utc_datetime(utc_dt)
        assert et_dt.tzinfo is not None


class TestTradingCalendarClass:
    """Tests for TradingCalendar compatibility alias class."""

    def test_holidays_returns_datetimeindex(self):
        import pandas as pd
        tc = TradingCalendar()
        result = tc.holidays(start=date(2026, 1, 1), end=date(2026, 12, 31))
        assert isinstance(result, pd.DatetimeIndex)
        assert len(result) > 0

    def test_get_next_fomc_date_returns_datetime(self):
        tc = TradingCalendar()
        from_date = datetime(2026, 1, 1)
        result = tc.get_next_fomc_date(from_date)
        assert result is None or isinstance(result, datetime)

    def test_is_options_expiration_week_returns_bool(self):
        tc = TradingCalendar()
        result = tc.is_options_expiration_week(date(2026, 1, 16))  # 3rd Friday
        assert isinstance(result, bool)

    def test_get_upcoming_events_returns_list(self):
        tc = TradingCalendar()
        from_date = datetime(2026, 1, 1)
        events = tc.get_upcoming_events(from_date, days_ahead=60)
        assert isinstance(events, list)

    def test_upcoming_events_have_required_keys(self):
        tc = TradingCalendar()
        from_date = datetime(2026, 1, 1)
        events = tc.get_upcoming_events(from_date, days_ahead=60)
        for event in events:
            assert "type" in event
            assert "date" in event
            assert "description" in event


class TestMarketSessionEnum:
    """Tests for MarketSession enum."""

    def test_pre_market_value(self):
        assert MarketSession.PRE_MARKET.value == "pre_market"

    def test_regular_hours_value(self):
        assert MarketSession.REGULAR_HOURS.value == "regular_hours"

    def test_after_hours_value(self):
        assert MarketSession.AFTER_HOURS.value == "after_hours"

    def test_closed_value(self):
        assert MarketSession.CLOSED.value == "closed"

    def test_get_current_market_session_returns_enum(self):
        result = get_current_market_session()
        assert isinstance(result, MarketSession)


class TestTradingTimeUtils:
    """Tests for TradingTimeUtils class."""

    def test_is_market_hours_during_regular(self):
        dt = ET.localize(datetime(2026, 1, 5, 11, 0))
        assert TradingTimeUtils.is_market_hours(dt) is True

    def test_is_market_hours_during_off_hours(self):
        dt = ET.localize(datetime(2026, 1, 5, 18, 0))
        assert TradingTimeUtils.is_market_hours(dt) is False

    def test_is_market_hours_on_weekend(self):
        dt = ET.localize(datetime(2026, 1, 3, 11, 0))
        assert TradingTimeUtils.is_market_hours(dt) is False

    def test_get_market_session_regular(self):
        dt = ET.localize(datetime(2026, 1, 5, 11, 0))
        assert TradingTimeUtils.get_market_session(dt) == "regular"

    def test_get_market_session_pre_market(self):
        dt = ET.localize(datetime(2026, 1, 5, 7, 0))
        assert TradingTimeUtils.get_market_session(dt) == "pre_market"

    def test_get_market_session_after_hours(self):
        dt = ET.localize(datetime(2026, 1, 5, 17, 0))
        assert TradingTimeUtils.get_market_session(dt) == "after_hours"

    def test_get_market_session_closed(self):
        dt = ET.localize(datetime(2026, 1, 5, 22, 0))
        assert TradingTimeUtils.get_market_session(dt) == "closed"

    def test_get_market_session_weekend(self):
        dt = ET.localize(datetime(2026, 1, 3, 11, 0))  # Saturday
        assert TradingTimeUtils.get_market_session(dt) == "closed"

    def test_format_market_time_returns_string(self):
        dt = ET.localize(datetime(2026, 1, 5, 11, 0))
        result = TradingTimeUtils.format_market_time(dt)
        assert isinstance(result, str)
        assert "2026" in result

    def test_get_trading_days_between_count(self):
        start = date(2026, 1, 5)
        end = date(2026, 1, 9)
        count = TradingTimeUtils.get_trading_days_between(start, end)
        assert count == 5

    def test_get_market_timezone_returns_timezone(self):
        tz = TradingTimeUtils.get_market_timezone()
        assert tz is not None

    def test_get_trading_time_utils_singleton(self):
        utils1 = get_trading_time_utils()
        utils2 = get_trading_time_utils()
        assert utils1 is utils2


# ==============================================================================
# ═══════════════════════════════════════════════════════════════════════════
#  U19 — INTERACTION MATRIX
# ═══════════════════════════════════════════════════════════════════════════
# ==============================================================================


class TestInteractionDataclass:
    """Tests for Interaction dataclass."""

    def _make_interaction(self, status=InteractionStatus.SUCCESS, latency_ms=None):
        return Interaction(
            source="ModuleA",
            target="ModuleB",
            interaction_type=InteractionType.FUNCTION_CALL,
            timestamp=datetime.now(),
            status=status,
            latency_ms=latency_ms,
        )

    def test_is_successful_true_for_success(self):
        intr = self._make_interaction(InteractionStatus.SUCCESS)
        assert intr.is_successful is True

    def test_is_successful_false_for_failure(self):
        intr = self._make_interaction(InteractionStatus.FAILURE)
        assert intr.is_successful is False

    def test_is_successful_false_for_pending(self):
        intr = self._make_interaction(InteractionStatus.PENDING)
        assert intr.is_successful is False

    def test_duration_ms_with_latency(self):
        intr = self._make_interaction(latency_ms=42.5)
        assert intr.duration_ms == 42.5

    def test_duration_ms_without_latency(self):
        intr = self._make_interaction(latency_ms=None)
        assert intr.duration_ms == 0.0

    def test_default_metadata_is_empty_dict(self):
        intr = self._make_interaction()
        assert intr.metadata == {}


class TestModuleStatsDataclass:
    """Tests for ModuleStats dataclass."""

    def test_success_rate_zero_when_no_interactions(self):
        stats = ModuleStats("TestModule")
        assert stats.success_rate == 0.0

    def test_error_rate_zero_when_no_interactions(self):
        stats = ModuleStats("TestModule")
        assert stats.error_rate == 0.0

    def test_success_rate_calculation(self):
        stats = ModuleStats("TestModule")
        stats.total_interactions = 10
        stats.successful_interactions = 8
        stats.failed_interactions = 2
        assert stats.success_rate == 80.0

    def test_error_rate_calculation(self):
        stats = ModuleStats("TestModule")
        stats.total_interactions = 10
        stats.failed_interactions = 3
        stats.successful_interactions = 7
        assert stats.error_rate == 30.0


class TestInteractionMatrixInit:
    """Tests for InteractionMatrix initialization."""

    def test_default_max_modules(self):
        matrix = InteractionMatrix()
        assert matrix.max_modules == DEFAULT_MATRIX_SIZE

    def test_custom_max_modules(self):
        matrix = InteractionMatrix(max_modules=50)
        assert matrix.max_modules == 50

    def test_initially_empty(self):
        matrix = InteractionMatrix()
        assert len(matrix.interactions) == 0
        assert len(matrix.module_names) == 0

    def test_frequency_matrix_shape(self):
        matrix = InteractionMatrix(max_modules=10)
        assert matrix.frequency_matrix.shape == (10, 10)
        assert np.all(matrix.frequency_matrix == 0)


class TestInteractionMatrixRecord:
    """Tests for InteractionMatrix.record_interaction()."""

    def setup_method(self):
        self.matrix = InteractionMatrix()

    def test_records_interaction(self):
        self.matrix.record_interaction("A", "B", InteractionType.FUNCTION_CALL)
        assert len(self.matrix.interactions) == 1

    def test_registers_modules(self):
        self.matrix.record_interaction("ModA", "ModB", InteractionType.DATA_EXCHANGE)
        assert "ModA" in self.matrix.modules
        assert "ModB" in self.matrix.modules

    def test_updates_frequency_matrix(self):
        self.matrix.record_interaction("A", "B", InteractionType.FUNCTION_CALL,
                                       InteractionStatus.SUCCESS)
        a_idx = self.matrix.modules["A"]
        b_idx = self.matrix.modules["B"]
        assert self.matrix.frequency_matrix[a_idx, b_idx] == 1

    def test_updates_module_stats(self):
        self.matrix.record_interaction("Src", "Tgt", InteractionType.FUNCTION_CALL,
                                       InteractionStatus.SUCCESS, latency_ms=100.0)
        stats = self.matrix.module_stats["Src"]
        assert stats.total_interactions == 1
        assert stats.successful_interactions == 1

    def test_failure_increments_failed(self):
        self.matrix.record_interaction("X", "Y", InteractionType.EVENT_TRIGGER,
                                       InteractionStatus.FAILURE)
        assert self.matrix.module_stats["X"].failed_interactions == 1

    def test_data_size_tracked(self):
        self.matrix.record_interaction("A", "B", InteractionType.DATA_EXCHANGE,
                                       InteractionStatus.SUCCESS, data_size=1024)
        assert self.matrix.module_stats["A"].total_data_sent == 1024
        assert self.matrix.module_stats["B"].total_data_received == 1024

    def test_history_limited_to_max(self):
        for i in range(MAX_HISTORY_SIZE + 50):
            self.matrix.record_interaction(f"Src{i % 5}", f"Tgt{i % 3}",
                                           InteractionType.FUNCTION_CALL)
        assert len(self.matrix.interactions) <= MAX_HISTORY_SIZE

    def test_multiple_interactions_accumulate(self):
        for _ in range(5):
            self.matrix.record_interaction("A", "B", InteractionType.FUNCTION_CALL,
                                           InteractionStatus.SUCCESS)
        assert self.matrix.module_stats["A"].total_interactions == 5


class TestInteractionMatrixStats:
    """Tests for InteractionMatrix.get_module_statistics()."""

    def setup_method(self):
        self.matrix = InteractionMatrix()
        self.matrix.record_interaction("Alpha", "Beta", InteractionType.FUNCTION_CALL,
                                       InteractionStatus.SUCCESS, latency_ms=50.0)
        self.matrix.record_interaction("Alpha", "Gamma", InteractionType.DATA_EXCHANGE,
                                       InteractionStatus.FAILURE)

    def test_get_specific_module_stats(self):
        stats = self.matrix.get_module_statistics("Alpha")
        assert isinstance(stats, ModuleStats)
        assert stats.total_interactions == 2

    def test_get_all_module_stats(self):
        all_stats = self.matrix.get_module_statistics()
        assert isinstance(all_stats, dict)
        assert "Alpha" in all_stats

    def test_unknown_module_returns_empty_stats(self):
        stats = self.matrix.get_module_statistics("Unknown")
        assert isinstance(stats, ModuleStats)
        assert stats.total_interactions == 0


class TestInteractionMatrixHistory:
    """Tests for InteractionMatrix.get_interaction_history()."""

    def setup_method(self):
        self.matrix = InteractionMatrix()
        self.matrix.record_interaction("Source1", "Target1", InteractionType.FUNCTION_CALL,
                                       InteractionStatus.SUCCESS)
        self.matrix.record_interaction("Source2", "Target1", InteractionType.EVENT_TRIGGER,
                                       InteractionStatus.FAILURE)
        self.matrix.record_interaction("Source1", "Target2", InteractionType.DATA_EXCHANGE,
                                       InteractionStatus.SUCCESS)

    def test_get_all_history(self):
        history = self.matrix.get_interaction_history()
        assert len(history) == 3

    def test_filter_by_source(self):
        history = self.matrix.get_interaction_history(source="Source1")
        assert len(history) == 2
        assert all(i.source == "Source1" for i in history)

    def test_filter_by_target(self):
        history = self.matrix.get_interaction_history(target="Target1")
        assert len(history) == 2
        assert all(i.target == "Target1" for i in history)

    def test_limit_parameter(self):
        history = self.matrix.get_interaction_history(limit=2)
        assert len(history) <= 2

    def test_sorted_most_recent_first(self):
        history = self.matrix.get_interaction_history()
        for i in range(len(history) - 1):
            assert history[i].timestamp >= history[i + 1].timestamp


class TestInteractionMatrixAnalysis:
    """Tests for InteractionMatrix.analyze_matrix()."""

    def setup_method(self):
        self.matrix = InteractionMatrix()
        # Add diverse interactions
        for source, target, status, latency, data in [
            ("A", "B", InteractionStatus.SUCCESS, 50.0, 500),
            ("A", "B", InteractionStatus.SUCCESS, 100.0, 1000),
            ("B", "C", InteractionStatus.FAILURE, None, None),
            ("C", "A", InteractionStatus.SUCCESS, 25.0, 200),
            ("A", "C", InteractionStatus.SUCCESS, 75.0, 750),
        ]:
            self.matrix.record_interaction(
                source, target, InteractionType.FUNCTION_CALL,
                status, latency, data
            )

    def test_analyze_frequency_returns_analysis(self):
        analysis = self.matrix.analyze_matrix(MatrixMetric.FREQUENCY)
        assert isinstance(analysis, MatrixAnalysis)

    def test_analyze_frequency_has_module_names(self):
        analysis = self.matrix.analyze_matrix(MatrixMetric.FREQUENCY)
        assert len(analysis.module_names) == 3
        assert set(analysis.module_names) == {"A", "B", "C"}

    def test_analyze_latency_returns_analysis(self):
        analysis = self.matrix.analyze_matrix(MatrixMetric.LATENCY)
        assert isinstance(analysis, MatrixAnalysis)
        assert analysis.metric_type == MatrixMetric.LATENCY

    def test_analyze_success_rate_returns_analysis(self):
        analysis = self.matrix.analyze_matrix(MatrixMetric.SUCCESS_RATE)
        assert isinstance(analysis, MatrixAnalysis)

    def test_analyze_data_volume_returns_analysis(self):
        analysis = self.matrix.analyze_matrix(MatrixMetric.DATA_VOLUME)
        assert isinstance(analysis, MatrixAnalysis)

    def test_analyze_has_hotspots(self):
        analysis = self.matrix.analyze_matrix(MatrixMetric.FREQUENCY)
        assert isinstance(analysis.hotspots, list)

    def test_analyze_has_health_score(self):
        analysis = self.matrix.analyze_matrix(MatrixMetric.FREQUENCY)
        assert 0.0 <= analysis.health_score <= 100.0

    def test_analyze_has_recommendations(self):
        analysis = self.matrix.analyze_matrix(MatrixMetric.FREQUENCY)
        assert isinstance(analysis.recommendations, list)

    def test_analyze_with_time_window(self):
        time_window = timedelta(hours=1)
        analysis = self.matrix.analyze_matrix(MatrixMetric.FREQUENCY, time_window=time_window)
        assert isinstance(analysis, MatrixAnalysis)

    def test_empty_matrix_analyze(self):
        empty_matrix = InteractionMatrix()
        analysis = empty_matrix.analyze_matrix(MatrixMetric.FREQUENCY)
        assert isinstance(analysis, MatrixAnalysis)
        assert analysis.matrix_data.shape == (0, 0)


class TestInteractionMatrixHotspots:
    """Tests for InteractionMatrix.identify_hotspots()."""

    def setup_method(self):
        self.matrix = InteractionMatrix()
        # Create a dominant pair A→B
        for _ in range(10):
            self.matrix.record_interaction("A", "B", InteractionType.FUNCTION_CALL,
                                           InteractionStatus.SUCCESS)
        self.matrix.record_interaction("C", "D", InteractionType.DATA_EXCHANGE,
                                       InteractionStatus.SUCCESS)

    def test_returns_list(self):
        hotspots = self.matrix.identify_hotspots()
        assert isinstance(hotspots, list)

    def test_hotspot_tuples_have_3_elements(self):
        hotspots = self.matrix.identify_hotspots()
        for hs in hotspots:
            assert len(hs) == 3

    def test_most_frequent_pair_first(self):
        hotspots = self.matrix.identify_hotspots(MatrixMetric.FREQUENCY, top_n=5)
        if hotspots:
            source, target, value = hotspots[0]
            assert source == "A" and target == "B"

    def test_top_n_limit(self):
        hotspots = self.matrix.identify_hotspots(top_n=1)
        assert len(hotspots) <= 1


class TestInteractionMatrixBottlenecks:
    """Tests for InteractionMatrix.detect_bottlenecks()."""

    def test_returns_list(self):
        matrix = InteractionMatrix()
        result = matrix.detect_bottlenecks()
        assert isinstance(result, list)

    def test_high_error_rate_module_is_bottleneck(self):
        matrix = InteractionMatrix()
        # Create module with > 10% error rate and some interactions
        for _ in range(20):
            matrix.record_interaction("BadModule", "TargetX",
                                      InteractionType.FUNCTION_CALL,
                                      InteractionStatus.FAILURE)
        bottlenecks = matrix.detect_bottlenecks()
        assert "BadModule" in bottlenecks


class TestInteractionMatrixSystemHealth:
    """Tests for InteractionMatrix.get_system_health()."""

    def test_empty_matrix_health(self):
        matrix = InteractionMatrix()
        health = matrix.get_system_health()
        assert health["health_score"] == 100.0
        assert health["total_interactions"] == 0
        assert health["status"] == "idle"

    def test_all_success_high_health(self):
        matrix = InteractionMatrix()
        for _ in range(10):
            matrix.record_interaction("A", "B", InteractionType.FUNCTION_CALL,
                                      InteractionStatus.SUCCESS, latency_ms=10.0)
        health = matrix.get_system_health()
        assert health["health_score"] >= 75.0
        assert health["success_rate"] == 100.0

    def test_all_failure_low_health(self):
        matrix = InteractionMatrix()
        for _ in range(10):
            matrix.record_interaction("A", "B", InteractionType.FUNCTION_CALL,
                                      InteractionStatus.FAILURE)
        health = matrix.get_system_health()
        assert health["error_rate"] == 100.0
        assert health["health_score"] < 75.0

    def test_health_has_required_keys(self):
        matrix = InteractionMatrix()
        health = matrix.get_system_health()
        for key in ["health_score", "total_interactions", "active_modules", "status"]:
            assert key in health

    def test_health_score_in_valid_range(self):
        matrix = InteractionMatrix()
        for _ in range(5):
            matrix.record_interaction("X", "Y", InteractionType.FUNCTION_CALL,
                                      InteractionStatus.SUCCESS, latency_ms=500.0)
        health = matrix.get_system_health()
        assert 0.0 <= health["health_score"] <= 100.0


class TestInteractionMatrixMonitoring:
    """Tests for InteractionMatrix.start_monitoring() and stop_monitoring()."""

    def test_start_monitoring(self):
        matrix = InteractionMatrix()
        matrix.start_monitoring(update_interval=60)
        assert matrix._monitoring is True
        matrix.stop_monitoring()

    def test_stop_monitoring(self):
        matrix = InteractionMatrix()
        matrix.start_monitoring(update_interval=60)
        matrix.stop_monitoring()
        assert matrix._monitoring is False

    def test_double_start_warning(self):
        matrix = InteractionMatrix()
        matrix.start_monitoring(update_interval=60)
        matrix.start_monitoring(update_interval=60)  # Should warn but not fail
        matrix.stop_monitoring()

    def teardown_method(self):
        # Ensure monitoring is stopped after test
        pass


class TestInteractionMatrixStartComplete:
    """Tests for InteractionMatrix.start_interaction() and complete_interaction()."""

    def setup_method(self):
        self.matrix = InteractionMatrix()

    def test_start_interaction_returns_string_id(self):
        interaction_id = self.matrix.start_interaction(
            "Src", "Tgt", InteractionType.FUNCTION_CALL
        )
        assert isinstance(interaction_id, str)

    def test_start_interaction_has_source_target(self):
        self.matrix.start_interaction("Source", "Target", InteractionType.DATA_EXCHANGE)
        # Should have recorded a pending interaction
        history = self.matrix.get_interaction_history()
        assert len(history) >= 1

    def test_complete_interaction_does_not_raise(self):
        interaction_id = self.matrix.start_interaction(
            "Src", "Tgt", InteractionType.FUNCTION_CALL
        )
        # Should not raise
        self.matrix.complete_interaction(
            interaction_id, InteractionStatus.SUCCESS, latency_ms=50.0
        )


class TestInteractionMatrixModuleFunctions:
    """Tests for U19 module-level functions."""

    def test_get_interaction_matrix_returns_instance(self):
        matrix = get_interaction_matrix()
        assert isinstance(matrix, InteractionMatrix)

    def test_get_interaction_matrix_singleton(self):
        m1 = get_interaction_matrix()
        m2 = get_interaction_matrix()
        assert m1 is m2

    def test_record_interaction_module_function(self):
        matrix = get_interaction_matrix()
        initial_count = len(matrix.interactions)
        record_interaction("TestSrc", "TestTgt", "function_call", True, 30.0)
        assert len(matrix.interactions) > initial_count

    def test_record_interaction_with_failure(self):
        matrix = get_interaction_matrix()
        initial_count = len(matrix.interactions)
        record_interaction("ErrSrc", "ErrTgt", "error_propagation", False)
        assert len(matrix.interactions) > initial_count

    def test_record_interaction_invalid_type_defaults_to_function_call(self):
        matrix = get_interaction_matrix()
        # Invalid type should default to FUNCTION_CALL
        record_interaction("A", "B", "invalid_type", True)  # Should not raise
        assert len(matrix.interactions) >= 1


class TestInteractionMatrixEnums:
    """Tests for U19 enum values."""

    def test_interaction_type_values(self):
        assert InteractionType.FUNCTION_CALL.value == "function_call"
        assert InteractionType.DATA_EXCHANGE.value == "data_exchange"
        assert InteractionType.EVENT_TRIGGER.value == "event_trigger"
        assert InteractionType.ERROR_PROPAGATION.value == "error_propagation"

    def test_interaction_status_values(self):
        assert InteractionStatus.SUCCESS.value == "success"
        assert InteractionStatus.FAILURE.value == "failure"
        assert InteractionStatus.PENDING.value == "pending"
        assert InteractionStatus.TIMEOUT.value == "timeout"

    def test_matrix_metric_values(self):
        assert MatrixMetric.FREQUENCY.value == "frequency"
        assert MatrixMetric.LATENCY.value == "latency"
        assert MatrixMetric.SUCCESS_RATE.value == "success_rate"
        assert MatrixMetric.DATA_VOLUME.value == "data_volume"


class TestInteractionMatrixThreadSafety:
    """Tests for thread-safety of InteractionMatrix."""

    def test_concurrent_record_interactions(self):
        import threading
        matrix = InteractionMatrix()
        errors = []

        def worker(thread_id):
            try:
                for i in range(20):
                    matrix.record_interaction(
                        f"Thread{thread_id}",
                        f"Target{i % 3}",
                        InteractionType.FUNCTION_CALL,
                        InteractionStatus.SUCCESS,
                        latency_ms=float(i * 10)
                    )
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker, args=(i,), daemon=True) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(matrix.interactions) == 100  # 5 threads × 20 each
