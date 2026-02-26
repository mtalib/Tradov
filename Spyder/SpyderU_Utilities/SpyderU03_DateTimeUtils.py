#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderU_Utilities
Module: SpyderU03_DateTimeUtils.py
Purpose: SPYDER - Automated SPY Options Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    SPYDER - Automated SPY Options Trading System

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from enum import Enum
from datetime import time, datetime, timedelta, timezone, date
from typing import Set, List, Optional, Dict, Tuple, Any

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd

US_EASTERN = "US/Eastern"
UTC = "UTC"

# Market hours (Eastern Time)
MARKET_OPEN_TIME = time(9, 30)  # 9:30 AM ET
MARKET_CLOSE_TIME = time(16, 0)  # 4:00 PM ET
PRE_MARKET_OPEN = time(4, 0)  # 4:00 AM ET
AFTER_HOURS_CLOSE = time(20, 0)  # 8:00 PM ET

# Trading time windows (from research)
OPTIMAL_ENTRY_WINDOW = (time(10, 15), time(11, 40))  # 10:15 AM - 11:40 AM
TIME_BASED_EXIT = time(12, 0)  # 12:00 PM
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)

# Options specific
OPTIONS_OPEN = time(9, 30)  # 9:30 AM ET
OPTIONS_CLOSE = time(16, 0)  # 4:00 PM ET (most days)
OPTIONS_CLOSE_FRIDAY = time(16, 15)  # 4:15 PM ET (Fridays)
INDEX_OPTIONS_CLOSE = time(16, 15)  # 4:15 PM ET (SPX, SPY)

# Early close days
EARLY_CLOSE_TIME = time(13, 0)  # 1:00 PM ET

# ==============================================================================
# HOLIDAY DEFINITIONS
# ==============================================================================


def get_trading_holidays(year: int) -> Set[date]:
    """
    Get US market holidays for a given year.

    Args:
        year: Year to get holidays for

    Returns:
        Set of holiday dates
    """
    holidays = set()

    # New Year's Day (January 1)
    new_years = date(year, 1, 1)
    if new_years.weekday() == 5:  # Saturday
        holidays.add(date(year - 1, 12, 31))  # Friday before
    elif new_years.weekday() == 6:  # Sunday
        holidays.add(date(year, 1, 2))  # Monday after
    else:
        holidays.add(new_years)

    # Martin Luther King Jr. Day (3rd Monday in January)
    mlk_day = _get_nth_weekday_of_month(year, 1, 0, 3)
    holidays.add(mlk_day)

    # Presidents Day (3rd Monday in February)
    presidents_day = _get_nth_weekday_of_month(year, 2, 0, 3)
    holidays.add(presidents_day)

    # Good Friday (Friday before Easter)
    good_friday = _calculate_good_friday(year)
    holidays.add(good_friday)

    # Memorial Day (Last Monday in May)
    memorial_day = _get_last_weekday_of_month(year, 5, 0)
    holidays.add(memorial_day)

    # Juneteenth (June 19) - Added as federal holiday in 2021
    if year >= 2022:  # First observed as market holiday in 2022
        juneteenth = date(year, 6, 19)
        if juneteenth.weekday() == 5:  # Saturday
            holidays.add(date(year, 6, 18))  # Friday before
        elif juneteenth.weekday() == 6:  # Sunday
            holidays.add(date(year, 6, 20))  # Monday after
        else:
            holidays.add(juneteenth)

    # Independence Day (July 4)
    july_4th = date(year, 7, 4)
    if july_4th.weekday() == 5:  # Saturday
        holidays.add(date(year, 7, 3))  # Friday before
    elif july_4th.weekday() == 6:  # Sunday
        holidays.add(date(year, 7, 5))  # Monday after
    else:
        holidays.add(july_4th)

    # Labor Day (1st Monday in September)
    labor_day = _get_nth_weekday_of_month(year, 9, 0, 1)
    holidays.add(labor_day)

    # Thanksgiving (4th Thursday in November)
    thanksgiving = _get_nth_weekday_of_month(year, 11, 3, 4)
    holidays.add(thanksgiving)

    # Christmas (December 25)
    christmas = date(year, 12, 25)
    if christmas.weekday() == 5:  # Saturday
        holidays.add(date(year, 12, 24))  # Friday before
    elif christmas.weekday() == 6:  # Sunday
        holidays.add(date(year, 12, 26))  # Monday after
    else:
        holidays.add(christmas)

    return holidays


def _get_nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> date:
    """Get the nth occurrence of a weekday in a month."""
    first_day = date(year, month, 1)
    first_weekday = first_day.weekday()

    # Calculate days to add to get to the first occurrence of the desired weekday
    days_to_add = (weekday - first_weekday) % 7
    first_occurrence = first_day + timedelta(days=days_to_add)

    # Add weeks to get to the nth occurrence
    target_date = first_occurrence + timedelta(weeks=n - 1)

    return target_date


def _get_last_weekday_of_month(year: int, month: int, weekday: int) -> date:
    """Get the last occurrence of a weekday in a month."""
    # Get the last day of the month
    if month == 12:
        next_month_first = date(year + 1, 1, 1)
    else:
        next_month_first = date(year, month + 1, 1)

    last_day = next_month_first - timedelta(days=1)

    # Work backwards to find the last occurrence of the weekday
    while last_day.weekday() != weekday:
        last_day -= timedelta(days=1)

    return last_day


def _calculate_good_friday(year: int) -> date:
    """Calculate Good Friday for a given year using Gauss's Easter algorithm."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451

    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1

    easter = date(year, month, day)
    good_friday = easter - timedelta(days=2)

    return good_friday


# ==============================================================================
# TRADING HOURS CLASS
# ==============================================================================


class TradingHours:
    """
    Trading hours management for different markets and sessions.
    """

    def __init__(self, timezone: str = US_EASTERN):
        """
        Initialize trading hours.

        Args:
            timezone: Time zone for trading hours
        """
        self.timezone = timezone
        self.tz = pytz.timezone(timezone)
        self.logger = SpyderLogger.get_logger(__name__)
        self._holiday_cache = {}

    def is_regular_hours(self, dt: Optional[datetime] = None) -> bool:
        """
        Check if currently in regular trading hours.

        Args:
            dt: Datetime to check (None for current time)

        Returns:
            True if in regular trading hours
        """
        if dt is None:
            dt = datetime.now(self.tz)
        else:
            dt = self._ensure_timezone(dt)

        if not self.is_trading_day(dt.date()):
            return False

        current_time = dt.time()

        # Check for early close
        if self.is_early_close_day(dt.date()):
            return MARKET_OPEN_TIME <= current_time < EARLY_CLOSE_TIME

        return MARKET_OPEN_TIME <= current_time < MARKET_CLOSE_TIME

    def is_pre_market(self, dt: Optional[datetime] = None) -> bool:
        """
        Check if currently in pre-market hours.

        Args:
            dt: Datetime to check (None for current time)

        Returns:
            True if in pre-market hours
        """
        if dt is None:
            dt = datetime.now(self.tz)
        else:
            dt = self._ensure_timezone(dt)

        if not self.is_trading_day(dt.date()):
            return False

        current_time = dt.time()
        return PRE_MARKET_OPEN <= current_time < MARKET_OPEN_TIME

    def is_after_market(self, dt: Optional[datetime] = None) -> bool:
        """
        Check if currently in after-market hours.

        Args:
            dt: Datetime to check (None for current time)

        Returns:
            True if in after-market hours
        """
        if dt is None:
            dt = datetime.now(self.tz)
        else:
            dt = self._ensure_timezone(dt)

        if not self.is_trading_day(dt.date()):
            return False

        current_time = dt.time()
        close_time = EARLY_CLOSE_TIME if self.is_early_close_day(dt.date()) else MARKET_CLOSE_TIME

        return close_time <= current_time < AFTER_HOURS_CLOSE

    def is_extended_hours(self, dt: Optional[datetime] = None) -> bool:
        """
        Check if currently in extended trading hours (pre or after market).

        Args:
            dt: Datetime to check (None for current time)

        Returns:
            True if in extended trading hours
        """
        return self.is_pre_market(dt) or self.is_after_market(dt)

    def is_options_trading_hours(self, dt: Optional[datetime] = None, symbol: str = "SPY") -> bool:
        """
        Check if currently in options trading hours.

        Args:
            dt: Datetime to check (None for current time)
            symbol: Symbol to check (SPY has special hours)

        Returns:
            True if in options trading hours
        """
        if dt is None:
            dt = datetime.now(self.tz)
        else:
            dt = self._ensure_timezone(dt)

        if not self.is_trading_day(dt.date()):
            return False

        current_time = dt.time()

        # Special handling for index options (SPY, SPX)
        if symbol in ["SPY", "SPX", "QQQ", "IWM"]:
            if dt.weekday() == 4:  # Friday
                close_time = INDEX_OPTIONS_CLOSE
            else:
                close_time = MARKET_CLOSE_TIME
        else:
            close_time = OPTIONS_CLOSE

        return OPTIONS_OPEN <= current_time < close_time

    def is_trading_day(self, check_date: Optional[date] = None) -> bool:
        """
        Check if given date is a trading day.

        Args:
            check_date: Date to check (None for today)

        Returns:
            True if trading day
        """
        if check_date is None:
            check_date = date.today()

        # Check weekend
        if check_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False

        # Check holidays
        return not self.is_market_holiday(check_date)

    def is_market_holiday(self, check_date: Optional[date] = None) -> bool:
        """
        Check if given date is a market holiday.

        Args:
            check_date: Date to check (None for today)

        Returns:
            True if market holiday
        """
        if check_date is None:
            check_date = date.today()

        # Cache holidays by year
        year = check_date.year
        if year not in self._holiday_cache:
            self._holiday_cache[year] = get_trading_holidays(year)

        return check_date in self._holiday_cache[year]

    def is_early_close_day(self, check_date: Optional[date] = None) -> bool:
        """
        Check if market closes early on given date.

        Args:
            check_date: Date to check (None for today)

        Returns:
            True if early close day
        """
        if check_date is None:
            check_date = date.today()

        # Day after Thanksgiving
        thanksgiving = _get_nth_weekday_of_month(check_date.year, 11, 3, 4)
        if check_date == thanksgiving + timedelta(days=1):
            return True

        # Christmas Eve (if trading day)
        if check_date.month == 12 and check_date.day == 24:
            if self.is_trading_day(check_date):
                return True

        # July 3rd (if trading day and July 4th is not trading day)
        if check_date.month == 7 and check_date.day == 3:
            if self.is_trading_day(check_date) and not self.is_trading_day(
                check_date + timedelta(days=1)
            ):
                return True

        return False

    def get_market_hours(
        self, check_date: Optional[date] = None
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        """
        Get market open and close times for a given date.

        Args:
            check_date: Date to check (None for today)

        Returns:
            Tuple of (open_time, close_time) or (None, None) if not trading day
        """
        if check_date is None:
            check_date = date.today()

        if not self.is_trading_day(check_date):
            return None, None

        open_dt = self.tz.localize(datetime.combine(check_date, MARKET_OPEN_TIME))

        if self.is_early_close_day(check_date):
            close_dt = self.tz.localize(datetime.combine(check_date, EARLY_CLOSE_TIME))
        else:
            close_dt = self.tz.localize(datetime.combine(check_date, MARKET_CLOSE_TIME))

        return open_dt, close_dt

    def get_next_market_open(self, after_dt: Optional[datetime] = None) -> datetime:
        """
        Get next market open time.

        Args:
            after_dt: Get open after this datetime (None for now)

        Returns:
            Next market open datetime
        """
        if after_dt is None:
            after_dt = datetime.now(self.tz)
        else:
            after_dt = self._ensure_timezone(after_dt)

        # Check if market is currently open
        if self.is_regular_hours(after_dt):
            return after_dt

        # Check if we're before market open today
        check_date = after_dt.date()
        if self.is_trading_day(check_date):
            market_open = self.tz.localize(datetime.combine(check_date, MARKET_OPEN_TIME))
            if after_dt < market_open:
                return market_open

        # Find next trading day
        next_day = check_date + timedelta(days=1)
        while not self.is_trading_day(next_day):
            next_day += timedelta(days=1)

        return self.tz.localize(datetime.combine(next_day, MARKET_OPEN_TIME))

    def get_next_market_close(self, after_dt: Optional[datetime] = None) -> datetime:
        """
        Get next market close time.

        Args:
            after_dt: Get close after this datetime (None for now)

        Returns:
            Next market close datetime
        """
        if after_dt is None:
            after_dt = datetime.now(self.tz)
        else:
            after_dt = self._ensure_timezone(after_dt)

        # If market is currently open, return today's close
        if self.is_regular_hours(after_dt):
            check_date = after_dt.date()
            if self.is_early_close_day(check_date):
                return self.tz.localize(datetime.combine(check_date, EARLY_CLOSE_TIME))
            else:
                return self.tz.localize(datetime.combine(check_date, MARKET_CLOSE_TIME))

        # Get next market open, then its close
        next_open = self.get_next_market_open(after_dt)
        return self.get_next_market_close(next_open)

    def time_until_market_open(self, from_dt: Optional[datetime] = None) -> timedelta:
        """
        Get time until next market open.

        Args:
            from_dt: Calculate from this datetime (None for now)

        Returns:
            Time until market open
        """
        if from_dt is None:
            from_dt = datetime.now(self.tz)
        else:
            from_dt = self._ensure_timezone(from_dt)

        next_open = self.get_next_market_open(from_dt)
        return next_open - from_dt

    def time_until_market_close(self, from_dt: Optional[datetime] = None) -> Optional[timedelta]:
        """
        Get time until market close (None if market closed).

        Args:
            from_dt: Calculate from this datetime (None for now)

        Returns:
            Time until close or None
        """
        if from_dt is None:
            from_dt = datetime.now(self.tz)
        else:
            from_dt = self._ensure_timezone(from_dt)

        if not self.is_regular_hours(from_dt):
            return None

        close_time = self.get_next_market_close(from_dt)
        return close_time - from_dt

    def _ensure_timezone(self, dt: datetime) -> datetime:
        """Ensure datetime has timezone"""
        if dt.tzinfo is None:
            return self.tz.localize(dt)
        return dt.astimezone(self.tz)


# ==============================================================================
# DATE/TIME UTILITIES - ENHANCED WITH RESEARCH FINDINGS
# ==============================================================================


class DateTimeUtils:
    """
    General date and time utilities for trading with research-driven enhancements.
    """

    @staticmethod
    def get_current_trading_day() -> date:
        """
        Get current trading day (today or last trading day if closed).

        Returns:
            Current trading day
        """
        trading_hours = TradingHours()
        today = date.today()

        # If today is a trading day, return it
        if trading_hours.is_trading_day(today):
            return today

        # Otherwise, find the last trading day
        check_date = today - timedelta(days=1)
        while not trading_hours.is_trading_day(check_date):
            check_date -= timedelta(days=1)

        return check_date

    @staticmethod
    def get_next_trading_day(after_date: Optional[date] = None) -> date:
        """
        Get next trading day after given date.

        Args:
            after_date: Date to start from (None for today)

        Returns:
            Next trading day
        """
        if after_date is None:
            after_date = date.today()

        trading_hours = TradingHours()
        next_day = after_date + timedelta(days=1)

        while not trading_hours.is_trading_day(next_day):
            next_day += timedelta(days=1)

        return next_day

    @staticmethod
    def get_previous_trading_day(before_date: Optional[date] = None) -> date:
        """
        Get previous trading day before given date.

        Args:
            before_date: Date to start from (None for today)

        Returns:
            Previous trading day
        """
        if before_date is None:
            before_date = date.today()

        trading_hours = TradingHours()
        prev_day = before_date - timedelta(days=1)

        while not trading_hours.is_trading_day(prev_day):
            prev_day -= timedelta(days=1)

        return prev_day

    @staticmethod
    def get_trading_days_between(
        start_date: date, end_date: date, inclusive: bool = True
    ) -> List[date]:
        """
        Get list of trading days between two dates.

        Args:
            start_date: Start date
            end_date: End date
            inclusive: Include start and end dates

        Returns:
            List of trading days
        """
        trading_hours = TradingHours()
        trading_days = []

        current = start_date if inclusive else start_date + timedelta(days=1)
        end = end_date if inclusive else end_date - timedelta(days=1)

        while current <= end:
            if trading_hours.is_trading_day(current):
                trading_days.append(current)
            current += timedelta(days=1)

        return trading_days

    @staticmethod
    def count_trading_days(start_date: date, end_date: date, inclusive: bool = True) -> int:
        """
        Count trading days between two dates.

        Args:
            start_date: Start date
            end_date: End date
            inclusive: Include start and end dates

        Returns:
            Number of trading days
        """
        return len(DateTimeUtils.get_trading_days_between(start_date, end_date, inclusive))

    @staticmethod
    def add_trading_days(start_date: date, days: int) -> date:
        """
        Add trading days to a date.

        Args:
            start_date: Starting date
            days: Number of trading days to add (negative to subtract)

        Returns:
            Resulting date
        """
        trading_hours = TradingHours()
        current = start_date

        if days > 0:
            for _ in range(days):
                current = DateTimeUtils.get_next_trading_day(current)
        elif days < 0:
            for _ in range(abs(days)):
                current = DateTimeUtils.get_previous_trading_day(current)

        return current

    @staticmethod
    def to_eastern_time(dt: datetime) -> datetime:
        """
        Convert datetime to Eastern time.

        Args:
            dt: Datetime to convert

        Returns:
            Datetime in Eastern time
        """
        if dt.tzinfo is None:
            # Assume UTC if no timezone
            dt = pytz.UTC.localize(dt)

        return dt.astimezone(pytz.timezone(US_EASTERN))

    @staticmethod
    def to_utc(dt: datetime) -> datetime:
        """
        Convert datetime to UTC.

        Args:
            dt: Datetime to convert

        Returns:
            Datetime in UTC
        """
        if dt.tzinfo is None:
            # Assume Eastern time if no timezone
            et = pytz.timezone(US_EASTERN)
            dt = et.localize(dt)

        return dt.astimezone(pytz.UTC)

    @staticmethod
    def parse_time_string(time_str: str) -> time:
        """
        Parse time string in various formats.

        Args:
            time_str: Time string (e.g., "9:30", "09:30 AM", "1430")

        Returns:
            time object
        """
        # Remove spaces and convert to uppercase
        time_str = time_str.strip().upper()

        # Try different formats
        formats = [
            "%H:%M",  # 24-hour with colon
            "%I:%M %p",  # 12-hour with AM/PM
            "%I:%M%p",  # 12-hour with AM/PM no space
            "%H%M",  # 24-hour no colon
            "%H:%M:%S",  # With seconds
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(time_str, fmt)
                return dt.time()
            except ValueError:
                continue

        raise ValueError(f"Unable to parse time string: {time_str}")

    @staticmethod
    def get_option_expiry_dates(
        start_date: Optional[date] = None, weeks_ahead: int = 8
    ) -> List[date]:
        """
        Get upcoming option expiry dates (Fridays).

        Args:
            start_date: Start looking from this date (None for today)
            weeks_ahead: Number of weeks to look ahead

        Returns:
            List of option expiry dates
        """
        if start_date is None:
            start_date = date.today()

        trading_hours = TradingHours()
        expiry_dates = []

        # Find next Friday
        days_until_friday = (4 - start_date.weekday()) % 7
        if days_until_friday == 0 and start_date <= date.today():
            days_until_friday = 7

        next_friday = start_date + timedelta(days=days_until_friday)

        # Get weekly expiries
        for i in range(weeks_ahead):
            check_date = next_friday + timedelta(weeks=i)

            # If Friday is a holiday, expiry is Thursday
            if not trading_hours.is_trading_day(check_date):
                check_date -= timedelta(days=1)

            expiry_dates.append(check_date)

        return expiry_dates

    @staticmethod
    def get_monthly_option_expiry(year: int, month: int) -> date:
        """
        Get monthly option expiry date (3rd Friday of month).

        Args:
            year: Year
            month: Month (1-12)

        Returns:
            Monthly option expiry date
        """
        # Find third Friday
        third_friday = _get_nth_weekday_of_month(year, month, 4, 3)  # 4 = Friday

        # If holiday, move to Thursday
        trading_hours = TradingHours()
        if not trading_hours.is_trading_day(third_friday):
            third_friday -= timedelta(days=1)

        return third_friday

    @staticmethod
    def format_option_symbol(underlying: str, expiry: date, option_type: str, strike: float) -> str:
        """
        Format option symbol in OCC format.

        Args:
            underlying: Underlying symbol
            expiry: Expiration date
            option_type: 'C' for call, 'P' for put
            strike: Strike price

        Returns:
            Formatted option symbol
        """
        # Format: SYMBOL + YYMMDD + C/P + 00000000 (strike * 1000)
        date_str = expiry.strftime("%y%m%d")
        strike_str = f"{int(strike * 1000):08d}"

        return f"{underlying}{date_str}{option_type}{strike_str}"

    # ==========================================================================
    # RESEARCH-DRIVEN TIME WINDOW METHODS (NEW)
    # ==========================================================================
    @staticmethod
    def is_optimal_entry_time(current_time: Optional[datetime] = None) -> bool:
        """
        Check if current time is within optimal entry window (10:15 AM - 11:40 AM).

        Args:
            current_time: Time to check (default: now)

        Returns:
            bool: True if within optimal entry window
        """
        if current_time is None:
            current_time = datetime.now()

        time_only = current_time.time()
        return OPTIMAL_ENTRY_WINDOW[0] <= time_only <= OPTIMAL_ENTRY_WINDOW[1]

    @staticmethod
    def should_exit_by_time(current_time: Optional[datetime] = None) -> bool:
        """
        Check if positions should be exited based on time (12:00 PM).

        Args:
            current_time: Time to check (default: now)

        Returns:
            bool: True if past exit time
        """
        if current_time is None:
            current_time = datetime.now()

        return current_time.time() >= TIME_BASED_EXIT

    @staticmethod
    def get_time_until_entry_window() -> Optional[timedelta]:
        """
        Get time until optimal entry window opens.

        Returns:
            timedelta or None if already in window
        """
        current_time = datetime.now().time()

        if current_time < OPTIMAL_ENTRY_WINDOW[0]:
            # Before window - calculate time until open
            today = datetime.now().date()
            window_open = datetime.combine(today, OPTIMAL_ENTRY_WINDOW[0])
            return window_open - datetime.now()
        elif current_time <= OPTIMAL_ENTRY_WINDOW[1]:
            # In window
            return None
        else:
            # After window - calculate time until tomorrow's window
            tomorrow = datetime.now().date() + timedelta(days=1)
            window_open = datetime.combine(tomorrow, OPTIMAL_ENTRY_WINDOW[0])
            return window_open - datetime.now()

    @staticmethod
    def get_time_remaining_in_window() -> Optional[timedelta]:
        """
        Get time remaining in current entry window.

        Returns:
            timedelta or None if not in window
        """
        current_time = datetime.now()
        if DateTimeUtils.is_optimal_entry_time(current_time):
            today = current_time.date()
            window_close = datetime.combine(today, OPTIMAL_ENTRY_WINDOW[1])
            return window_close - current_time
        return None

    @staticmethod
    def get_trading_windows() -> Dict[str, Tuple[time, time]]:
        """
        Get all trading time windows.

        Returns:
            Dict of window names to (start, end) tuples
        """
        return {
            "market_hours": (MARKET_OPEN, MARKET_CLOSE),
            "optimal_entry": OPTIMAL_ENTRY_WINDOW,
            "morning_session": (MARKET_OPEN, TIME_BASED_EXIT),
            "afternoon_session": (TIME_BASED_EXIT, MARKET_CLOSE),
            "pre_market": (PRE_MARKET_OPEN, MARKET_OPEN),
            "after_hours": (MARKET_CLOSE, AFTER_HOURS_CLOSE),
        }

    @staticmethod
    def format_time_window(window: Tuple[time, time]) -> str:
        """
        Format time window as string.

        Args:
            window: Tuple of (start, end) times

        Returns:
            str: Formatted window string
        """
        return f"{window[0].strftime('%I:%M %p')} - {window[1].strftime('%I:%M %p')}"

    @staticmethod
    def is_end_of_session(minutes_before_close: int = 30) -> bool:
        """
        Check if near end of trading session.

        Args:
            minutes_before_close: Minutes threshold before close

        Returns:
            bool: True if within threshold of market close
        """
        current_time = datetime.now()
        today = current_time.date()
        market_close_time = datetime.combine(today, MARKET_CLOSE)

        time_until_close = market_close_time - current_time
        return 0 <= time_until_close.total_seconds() <= (minutes_before_close * 60)

    # ==========================================================================
    # DAY-OF-WEEK HELPER METHODS (NEW)
    # ==========================================================================
    @staticmethod
    def get_trading_day_name() -> str:
        """Get current trading day name with Monday emphasis"""
        day_names = {
            0: "Monday (Optimal)",
            1: "Tuesday",
            2: "Wednesday",
            3: "Thursday",
            4: "Friday",
        }
        return day_names.get(datetime.now().weekday(), "Weekend")

    @staticmethod
    def is_monday() -> bool:
        """Check if today is Monday"""
        return datetime.now().weekday() == 0

    @staticmethod
    def get_day_quality_score() -> float:
        """
        Get trading quality score for current day based on research.

        Returns:
            float: Quality score (0-1) with Monday = 1.0
        """
        day_scores = {
            0: 1.0,  # Monday - best
            1: 0.4,  # Tuesday
            2: 0.5,  # Wednesday
            3: 0.4,  # Thursday
            4: 0.3,  # Friday - worst
        }
        return day_scores.get(datetime.now().weekday(), 0.0)

    @staticmethod
    def get_trading_session_info() -> Dict[str, Any]:
        """
        Get comprehensive trading session information.

        Returns:
            Dict with current session details
        """
        current_time = datetime.now()
        current_date = current_time.date()
        trading_hours = TradingHours()

        # Basic info
        info = {
            "date": current_date,
            "day_name": DateTimeUtils.get_trading_day_name(),
            "is_trading_day": trading_hours.is_trading_day(current_date),
            "is_monday": DateTimeUtils.is_monday(),
            "day_quality_score": DateTimeUtils.get_day_quality_score(),
            "current_time": current_time.time(),
        }

        # Market status
        if info["is_trading_day"]:
            info["market_open"] = trading_hours.is_regular_hours(current_time)
            info["pre_market"] = trading_hours.is_pre_market(current_time)
            info["after_hours"] = trading_hours.is_after_market(current_time)

            # Time windows
            info["in_optimal_entry_window"] = DateTimeUtils.is_optimal_entry_time(current_time)
            info["past_exit_time"] = DateTimeUtils.should_exit_by_time(current_time)

            # Time until events
            if not info["in_optimal_entry_window"]:
                info["time_until_entry_window"] = DateTimeUtils.get_time_until_entry_window()
            else:
                info["time_remaining_in_window"] = DateTimeUtils.get_time_remaining_in_window()

            # Market hours
            open_time, close_time = trading_hours.get_market_hours(current_date)
            info["market_open_time"] = open_time.time() if open_time else None
            info["market_close_time"] = close_time.time() if close_time else None
            info["is_early_close"] = trading_hours.is_early_close_day(current_date)
        else:
            # Not a trading day
            info["reason"] = "Weekend" if current_date.weekday() >= 5 else "Holiday"
            info["next_trading_day"] = DateTimeUtils.get_next_trading_day(current_date)

        return info


# ==============================================================================
# MODULE FUNCTIONS - MAIN INTERFACE
# ==============================================================================


def is_market_open(check_time: Optional[datetime] = None, extended_hours: bool = False) -> bool:
    """
    Check if the US stock market is currently open.

    Args:
        check_time: Time to check (None for current time)
        extended_hours: Include extended trading hours

    Returns:
        True if market is open, False otherwise
    """
    trading_hours = TradingHours()

    if check_time is None:
        check_time = datetime.now(pytz.timezone(US_EASTERN))

    if extended_hours:
        return trading_hours.is_regular_hours(check_time) or trading_hours.is_extended_hours(
            check_time
        )
    else:
        return trading_hours.is_regular_hours(check_time)


def is_options_trading_time(check_time: Optional[datetime] = None, symbol: str = "SPY") -> bool:
    """
    Check if options are currently trading.

    Args:
        check_time: Time to check (None for current time)
        symbol: Option symbol (SPY has special hours)

    Returns:
        True if options trading is open
    """
    trading_hours = TradingHours()
    return trading_hours.is_options_trading_hours(check_time, symbol)


def get_market_schedule(date_range: Optional[Tuple[date, date]] = None) -> pd.DataFrame:
    """
    Get market schedule for a date range.

    Args:
        date_range: Tuple of (start_date, end_date), None for next 5 days

    Returns:
        DataFrame with market schedule
    """
    if date_range is None:
        start = date.today()
        end = start + timedelta(days=5)
    else:
        start, end = date_range

    trading_hours = TradingHours()
    schedule_data = []

    current = start
    while current <= end:
        if trading_hours.is_trading_day(current):
            open_time, close_time = trading_hours.get_market_hours(current)

            schedule_data.append(
                {
                    "date": current,
                    "day": current.strftime("%A"),
                    "open": open_time.time() if open_time else None,
                    "close": close_time.time() if close_time else None,
                    "early_close": trading_hours.is_early_close_day(current),
                    "trading_day": True,
                    "optimal_entry": DateTimeUtils.format_time_window(OPTIMAL_ENTRY_WINDOW),
                    "exit_time": TIME_BASED_EXIT,
                    "day_quality": (
                        DateTimeUtils.get_day_quality_score() if current == date.today() else None
                    ),
                }
            )
        else:
            reason = "Weekend" if current.weekday() >= 5 else "Holiday"
            schedule_data.append(
                {
                    "date": current,
                    "day": current.strftime("%A"),
                    "open": None,
                    "close": None,
                    "early_close": False,
                    "trading_day": False,
                    "reason": reason,
                    "optimal_entry": None,
                    "exit_time": None,
                    "day_quality": None,
                }
            )

        current += timedelta(days=1)

    return pd.DataFrame(schedule_data)


def to_utc_datetime(dt: datetime) -> datetime:
    """
    Convert datetime to UTC (wrapper for compatibility).

    Args:
        dt: Datetime to convert

    Returns:
        UTC datetime
    """
    return DateTimeUtils.to_utc(dt)


def from_utc_datetime(dt: datetime, target_tz: str = US_EASTERN) -> datetime:
    """
    Convert UTC datetime to target timezone.

    Args:
        dt: UTC datetime
        target_tz: Target timezone

    Returns:
        Datetime in target timezone
    """
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)

    return dt.astimezone(pytz.timezone(target_tz))


def is_trading_day(check_date: Optional[date] = None) -> bool:
    """
    Check if given date is a trading day (module-level wrapper).

    Args:
        check_date: Date to check (None for today)

    Returns:
        True if trading day
    """
    trading_hours = TradingHours()
    return trading_hours.is_trading_day(check_date)


def get_next_trading_day(after_date: Optional[date] = None) -> date:
    """
    Get next trading day after given date (module-level wrapper).

    Args:
        after_date: Date to start from (None for today)

    Returns:
        Next trading day
    """
    return DateTimeUtils.get_next_trading_day(after_date)


def get_previous_trading_day(before_date: Optional[date] = None) -> date:
    """
    Get previous trading day before given date (module-level wrapper).

    Args:
        before_date: Date to start from (None for today)

    Returns:
        Previous trading day
    """
    return DateTimeUtils.get_previous_trading_day(before_date)


def get_current_trading_day() -> date:
    """
    Get current trading day (module-level wrapper).

    Returns:
        Current trading day
    """
    return DateTimeUtils.get_current_trading_day()


def is_market_holiday(check_date: Optional[date] = None) -> bool:
    """
    Check if a given date is a US market holiday.

    Args:
        check_date: Date to check (None for today)

    Returns:
        True if market holiday, False otherwise
    """
    trading_hours = TradingHours()
    return trading_hours.is_market_holiday(check_date)


def get_trading_hours(check_date: Optional[date] = None) -> Dict[str, Any]:
    """
    Get trading hours information for a specific date.

    Args:
        check_date: Date to check (None for today)

    Returns:
        Dictionary with trading hours info
    """
    if check_date is None:
        check_date = date.today()

    trading_hours = TradingHours()

    # Base structure
    hours_info = {
        "date": check_date,
        "is_trading_day": trading_hours.is_trading_day(check_date),
        "pre_market_open": PRE_MARKET_OPEN,
        "after_market_close": AFTER_HOURS_CLOSE,
        "is_early_close": False,
        "options_close": OPTIONS_CLOSE,
        "optimal_entry_window": OPTIMAL_ENTRY_WINDOW,
        "time_based_exit": TIME_BASED_EXIT,
        "day_quality_score": (
            DateTimeUtils.get_day_quality_score() if check_date == date.today() else None
        ),
    }

    if hours_info["is_trading_day"]:
        # Get market hours
        open_time, close_time = trading_hours.get_market_hours(check_date)
        hours_info["market_open"] = MARKET_OPEN_TIME
        hours_info["is_early_close"] = trading_hours.is_early_close_day(check_date)

        if hours_info["is_early_close"]:
            hours_info["market_close"] = EARLY_CLOSE_TIME
        else:
            hours_info["market_close"] = MARKET_CLOSE_TIME

        # Special options close for Friday
        if check_date.weekday() == 4:  # Friday
            hours_info["options_close"] = OPTIONS_CLOSE_FRIDAY
    else:
        # Not a trading day
        hours_info["market_open"] = None
        hours_info["market_close"] = None
        hours_info["options_close"] = None

        # Determine reason
        if check_date.weekday() >= 5:
            hours_info["reason"] = "Weekend"
        else:
            hours_info["reason"] = "Holiday"

    return hours_info


def get_market_hours(
    check_date: Optional[date] = None,
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Get market open and close times for a given date (module-level wrapper).

    Args:
        check_date: Date to check (None for today)

    Returns:
        Tuple of (open_time, close_time) or (None, None) if not trading day
    """
    trading_hours = TradingHours()
    return trading_hours.get_market_hours(check_date)


def get_next_market_open(after_dt: Optional[datetime] = None) -> datetime:
    """
    Get next market open time (module-level wrapper).

    Args:
        after_dt: Get open after this datetime (None for now)

    Returns:
        Next market open datetime
    """
    trading_hours = TradingHours()
    return trading_hours.get_next_market_open(after_dt)


def get_next_market_close(after_dt: Optional[datetime] = None) -> datetime:
    """
    Get next market close time (module-level wrapper).

    Args:
        after_dt: Get close after this datetime (None for now)

    Returns:
        Next market close datetime
    """
    trading_hours = TradingHours()
    return trading_hours.get_next_market_close(after_dt)


def time_until_market_open(from_dt: Optional[datetime] = None) -> timedelta:
    """
    Get time until next market open (module-level wrapper).

    Args:
        from_dt: Calculate from this datetime (None for now)

    Returns:
        Time until market open
    """
    trading_hours = TradingHours()
    return trading_hours.time_until_market_open(from_dt)


def time_until_market_close(from_dt: Optional[datetime] = None) -> Optional[timedelta]:
    """
    Get time until market close (module-level wrapper).

    Args:
        from_dt: Calculate from this datetime (None for now)

    Returns:
        Time until close or None if market closed
    """
    trading_hours = TradingHours()
    return trading_hours.time_until_market_close(from_dt)


def is_regular_hours(dt: Optional[datetime] = None) -> bool:
    """
    Check if currently in regular trading hours (module-level wrapper).

    Args:
        dt: Datetime to check (None for current time)

    Returns:
        True if in regular trading hours
    """
    trading_hours = TradingHours()
    return trading_hours.is_regular_hours(dt)


def is_pre_market(dt: Optional[datetime] = None) -> bool:
    """
    Check if currently in pre-market hours (module-level wrapper).

    Args:
        dt: Datetime to check (None for current time)

    Returns:
        True if in pre-market hours
    """
    trading_hours = TradingHours()
    return trading_hours.is_pre_market(dt)


def is_after_market(dt: Optional[datetime] = None) -> bool:
    """
    Check if currently in after-market hours (module-level wrapper).

    Args:
        dt: Datetime to check (None for current time)

    Returns:
        True if in after-market hours
    """
    trading_hours = TradingHours()
    return trading_hours.is_after_market(dt)


def is_early_close_day(check_date: Optional[date] = None) -> bool:
    """
    Check if market closes early on given date (module-level wrapper).

    Args:
        check_date: Date to check (None for today)

    Returns:
        True if early close day
    """
    trading_hours = TradingHours()
    return trading_hours.is_early_close_day(check_date)


# Research-driven wrappers


def is_optimal_entry_time(current_time: Optional[datetime] = None) -> bool:
    """
    Check if current time is within optimal entry window (module-level wrapper).

    Args:
        current_time: Time to check (None for current time)

    Returns:
        True if within optimal entry window
    """
    return DateTimeUtils.is_optimal_entry_time(current_time)


def should_exit_by_time(current_time: Optional[datetime] = None) -> bool:
    """
    Check if positions should be exited based on time (module-level wrapper).

    Args:
        current_time: Time to check (None for current time)

    Returns:
        True if past exit time
    """
    return DateTimeUtils.should_exit_by_time(current_time)


def get_trading_session_info() -> Dict[str, Any]:
    """
    Get comprehensive trading session information (module-level wrapper).

    Returns:
        Dict with current session details
    """
    return DateTimeUtils.get_trading_session_info()


# ==============================================================================
# ALIASES FOR COMPATIBILITY - ENHANCED VERSION
# ==============================================================================


class TradingCalendar:
    """Trading calendar for compatibility with enhanced FOMC and options functionality"""

    @staticmethod
    def holidays(start=None, end=None, return_name=True):
        """Get holidays in date range"""
        if start is None:
            start = date.today()
        if end is None:
            end = start + timedelta(days=365)

        holidays = []
        for year in range(start.year, end.year + 1):
            year_holidays = get_trading_holidays(year)
            for holiday in year_holidays:
                if start <= holiday <= end:
                    holidays.append(holiday)

        return pd.DatetimeIndex(holidays)

    @staticmethod
    def get_next_fomc_date(from_date: Optional[datetime] = None) -> Optional[datetime]:
        """
        Get next FOMC meeting date.

        Args:
            from_date: Start looking from this date (None for current time)

        Returns:
            Next FOMC meeting date or None if none found in near future
        """
        if from_date is None:
            from_date = datetime.now()

        # FOMC meetings are typically held 8 times per year
        # Generally: Late January/Early February, March, May, June, July, September, November, December
        # This is a simplified approximation - in practice you'd use the actual Fed calendar

        current_year = from_date.year
        fomc_months = [2, 3, 5, 6, 7, 9, 11, 12]  # Typical FOMC months

        # Look for next FOMC date in current and next year
        for year in [current_year, current_year + 1]:
            for month in fomc_months:
                # FOMC meetings typically happen around the 3rd Tuesday-Wednesday of the month
                # For simplicity, we'll use the 3rd Wednesday
                try:
                    third_wednesday = _get_nth_weekday_of_month(year, month, 2, 3)  # 2 = Wednesday
                    fomc_date = datetime.combine(
                        third_wednesday, time(14, 0)
                    )  # 2 PM typical announcement

                    if fomc_date > from_date:
                        return fomc_date
                except BaseException:
                    continue

        return None

    @staticmethod
    def is_options_expiration_week(check_date: Optional[date] = None) -> bool:
        """
        Check if given date is in options expiration week.

        Args:
            check_date: Date to check (None for today)

        Returns:
            True if in options expiration week
        """
        if check_date is None:
            check_date = date.today()

        # Monthly options expire on the 3rd Friday of the month
        try:
            third_friday = DateTimeUtils.get_monthly_option_expiry(
                check_date.year, check_date.month
            )

            # Check if the date is in the same week as the third Friday
            # Week starts on Monday (weekday 0)
            week_start = third_friday - timedelta(days=third_friday.weekday())
            week_end = week_start + timedelta(days=6)

            return week_start <= check_date <= week_end
        except BaseException:
            return False

    @staticmethod
    def get_upcoming_events(
        from_date: Optional[datetime] = None, days_ahead: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get upcoming market events.

        Args:
            from_date: Start looking from this date (None for current time)
            days_ahead: How many days ahead to look

        Returns:
            List of market events
        """
        if from_date is None:
            from_date = datetime.now()

        events = []

        # Add FOMC meeting
        next_fomc = TradingCalendar.get_next_fomc_date(from_date)
        if next_fomc and (next_fomc - from_date).days <= days_ahead:
            events.append(
                {"type": "FOMC", "date": next_fomc, "description": "FOMC Meeting", "impact": "high"}
            )

        # Add options expirations
        end_date = from_date + timedelta(days=days_ahead)
        current = from_date.date()

        while current <= end_date.date():
            if TradingCalendar.is_options_expiration_week(current):
                # Find the actual expiry date (3rd Friday)
                expiry_date = DateTimeUtils.get_monthly_option_expiry(current.year, current.month)
                if expiry_date >= from_date.date():
                    events.append(
                        {
                            "type": "OPTIONS_EXPIRY",
                            "date": datetime.combine(expiry_date, time(16, 0)),
                            "description": "Monthly Options Expiration",
                            "impact": "medium",
                        }
                    )
                    # Skip to next month
                    if current.month == 12:
                        current = date(current.year + 1, 1, 1)
                    else:
                        current = date(current.year, current.month + 1, 1)
                else:
                    current += timedelta(days=1)
            else:
                current += timedelta(days=1)

        # Sort by date
        events.sort(key=lambda x: x["date"])

        return events


SPYTradingCalendar = TradingCalendar
TradingCalendarUtils = DateTimeUtils

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test the utilities with research enhancements
    print("Testing DateTime Utilities with Research Enhancements...")
    print("=" * 60)

    # Get comprehensive session info
    session_info = get_trading_session_info()
    print("\nCurrent Trading Session Info:")
    for key, value in session_info.items():
        print(f"  {key}: {value}")

    # Test optimal entry window
    print(f"\nOptimal Entry Window: {DateTimeUtils.format_time_window(OPTIMAL_ENTRY_WINDOW)}")
    print(f"Currently in window? {is_optimal_entry_time()}")
    if not is_optimal_entry_time():
        print(f"Time until window: {DateTimeUtils.get_time_until_entry_window()}")
    else:
        print(f"Time remaining: {DateTimeUtils.get_time_remaining_in_window()}")

    # Test time-based exit
    print(f"\nTime-Based Exit: {TIME_BASED_EXIT}")
    print(f"Should exit now? {should_exit_by_time()}")

    # Test day quality
    print(f"\nDay Quality Analysis:")
    print(f"Current day: {DateTimeUtils.get_trading_day_name()}")
    print(f"Is Monday? {DateTimeUtils.is_monday()}")
    print(f"Day quality score: {DateTimeUtils.get_day_quality_score():.1f}")

    # Get market schedule with research info
    print("\nMarket Schedule (Next 5 days):")
    schedule = get_market_schedule()
    print(
        schedule[
            ["date", "day", "trading_day", "optimal_entry", "exit_time", "day_quality"]
        ].to_string()
    )

    # Test all time windows
    print("\nAll Trading Time Windows:")
    windows = DateTimeUtils.get_trading_windows()
    for name, window in windows.items():
        print(f"  {name}: {DateTimeUtils.format_time_window(window)}")

    # Test TradingCalendar enhancements
    print("\nTradingCalendar Enhancements:")
    tc = TradingCalendar()

    # Test FOMC date
    next_fomc = tc.get_next_fomc_date()
    if next_fomc:
        print(f"Next FOMC meeting: {next_fomc.strftime('%Y-%m-%d %H:%M')}")
    else:
        print("No FOMC meeting found in near future")

    # Test options expiration week
    print(f"Is options expiration week? {tc.is_options_expiration_week()}")

    # Test upcoming events
    print("\nUpcoming market events:")
    events = tc.get_upcoming_events(days_ahead=60)
    for event in events:
        print(
            f"  {event['date'].strftime('%Y-%m-%d')}: {event['description']} ({event['impact']} impact)"
        )


# ==============================================================================
# TRADING TIME UTILITIES CLASS
# ==============================================================================
class TradingTimeUtils:
    """
    Enhanced trading time utilities for market operations.

    This class provides comprehensive time-related utilities for trading operations
    including market hours, session detection, and timezone conversions.
    """

    def __init__(self):
        """Initialize trading time utilities."""
        self.logger = None
        try:
            from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger

            self.logger = SpyderLogger.get_logger(__name__)
        except ImportError:
            pass

    @staticmethod
    def get_market_timezone():
        """Get market timezone (Eastern Time)."""
        import pytz

        return pytz.timezone("US/Eastern")

    @staticmethod
    def is_market_hours(dt=None):
        """Check if given datetime is during market hours."""
        if dt is None:
            dt = datetime.now()

        # Convert to market timezone
        market_tz = TradingTimeUtils.get_market_timezone()
        if dt.tzinfo is None:
            dt = market_tz.localize(dt)
        else:
            dt = dt.astimezone(market_tz)

        # Check if weekday (0=Monday, 6=Sunday)
        if dt.weekday() >= 5:  # Saturday or Sunday
            return False

        # Check market hours (9:30 AM - 4:00 PM ET)
        market_open = dt.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = dt.replace(hour=16, minute=0, second=0, microsecond=0)

        return market_open <= dt <= market_close

    @staticmethod
    def get_next_market_open(dt=None):
        """Get next market open datetime."""
        if dt is None:
            dt = datetime.now()

        market_tz = TradingTimeUtils.get_market_timezone()
        if dt.tzinfo is None:
            dt = market_tz.localize(dt)
        else:
            dt = dt.astimezone(market_tz)

        # Start with next day if after market close or weekend
        next_open = dt.replace(hour=9, minute=30, second=0, microsecond=0)

        if dt.time() >= datetime.time(16, 0) or dt.weekday() >= 5:
            next_open += timedelta(days=1)

        # Skip weekends
        while next_open.weekday() >= 5:
            next_open += timedelta(days=1)

        return next_open

    @staticmethod
    def get_market_session(dt=None):
        """Get current market session type."""
        if dt is None:
            dt = datetime.now()

        market_tz = TradingTimeUtils.get_market_timezone()
        if dt.tzinfo is None:
            dt = market_tz.localize(dt)
        else:
            dt = dt.astimezone(market_tz)

        # Weekend
        if dt.weekday() >= 5:
            return "closed"

        current_time = dt.time()

        # Market sessions
        if datetime.time(4, 0) <= current_time < datetime.time(9, 30):
            return "pre_market"
        elif datetime.time(9, 30) <= current_time <= datetime.time(16, 0):
            return "regular"
        elif datetime.time(16, 0) < current_time <= datetime.time(20, 0):
            return "after_hours"
        else:
            return "closed"

    @staticmethod
    def format_market_time(dt=None):
        """Format datetime for market display."""
        if dt is None:
            dt = datetime.now()

        market_tz = TradingTimeUtils.get_market_timezone()
        if dt.tzinfo is None:
            dt = market_tz.localize(dt)
        else:
            dt = dt.astimezone(market_tz)

        return dt.strftime("%Y-%m-%d %H:%M:%S %Z")

    @staticmethod
    def get_trading_days_between(start_date, end_date):
        """Get number of trading days between two dates."""
        current = start_date
        trading_days = 0

        while current <= end_date:
            if current.weekday() < 5:  # Monday to Friday
                trading_days += 1
            current += timedelta(days=1)

        return trading_days


# Create singleton instance
_trading_time_utils = None


def get_trading_time_utils():
    """Get singleton TradingTimeUtils instance."""
    global _trading_time_utils
    if _trading_time_utils is None:
        _trading_time_utils = TradingTimeUtils()
    return _trading_time_utils

class MarketSession(Enum):
    """Market trading session enumeration"""
    PRE_MARKET = "pre_market"
    REGULAR_HOURS = "regular_hours" 
    AFTER_HOURS = "after_hours"
    EXTENDED_HOURS = "extended_hours"
    CLOSED = "closed"
    HOLIDAY = "holiday"
    WEEKEND = "weekend"
    UNKNOWN = "unknown"

def get_current_market_session() -> MarketSession:
    """Get current market session based on time"""
    # Simplified logic - would normally check actual market hours
    from datetime import datetime
    now = datetime.now()
    hour = now.hour
    
    if 4 <= hour < 9:
        return MarketSession.PRE_MARKET
    elif 9 <= hour < 16:
        return MarketSession.REGULAR_HOURS
    elif 16 <= hour < 20:
        return MarketSession.AFTER_HOURS
    else:
        return MarketSession.CLOSED
