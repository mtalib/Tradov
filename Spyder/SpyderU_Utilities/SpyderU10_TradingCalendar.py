#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderU_Utilities
Module: SpyderU10_TradingCalendar.py
Purpose: Trading calendar and market hours management with holiday support

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-01-24 Time: 10:30:00

Module Description:
    This module manages trading calendars, market hours, and holiday schedules
    for the Spyder trading system. It provides functionality to determine
    trading days, market hours, early closures, and special trading sessions.
    The module supports multiple exchanges and handles time zone conversions
    for global markets.
"""

import json
# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import Enum
from zoneinfo import ZoneInfo

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Default market hours (Eastern Time)
DEFAULT_MARKET_OPEN = time(9, 30)
DEFAULT_MARKET_CLOSE = time(16, 0)
DEFAULT_PREMARKET_OPEN = time(4, 0)
DEFAULT_AFTERHOURS_CLOSE = time(20, 0)

# Time zones
ET_TIMEZONE = ZoneInfo("America/New_York")
UTC_TIMEZONE = ZoneInfo("UTC")

# Calendar cache settings
CACHE_DAYS = 365  # Cache holidays for one year
HOLIDAY_FILE = "market_holidays.json"

# ==============================================================================
# ENUMS
# ==============================================================================


class MarketSession(Enum):
    """Market session types"""

    CLOSED = "closed"
    PREMARKET = "premarket"
    REGULAR = "regular"
    AFTERHOURS = "afterhours"
    EXTENDED = "extended"


class MarketStatus(Enum):
    """Current market status"""

    OPEN = "open"
    CLOSED = "closed"
    OPENING_SOON = "opening_soon"
    CLOSING_SOON = "closing_soon"
    EARLY_CLOSE = "early_close"
    HOLIDAY = "holiday"
    WEEKEND = "weekend"


class Exchange(Enum):
    """Supported exchanges"""

    NYSE = "NYSE"
    NASDAQ = "NASDAQ"
    CBOE = "CBOE"
    CME = "CME"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================


@dataclass
class MarketHours:
    """Market hours for a specific date"""

    date: date
    premarket_open: time | None = None
    market_open: time | None = None
    market_close: time | None = None
    afterhours_close: time | None = None
    is_trading_day: bool = True
    is_early_close: bool = False
    notes: str = ""


@dataclass
class Holiday:
    """Market holiday information"""

    date: date
    name: str
    exchange: Exchange
    is_closed: bool = True
    early_close_time: time | None = None


# ==============================================================================
# MAIN CLASS
# ==============================================================================


class TradingCalendar:
    """
    Trading calendar for market hours and holiday management.

    This class provides comprehensive calendar functionality including
    trading day determination, market hours management, holiday handling,
    and time zone conversions. It supports multiple exchanges and
    handles special trading sessions.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        holidays: Set of holiday dates
        early_closes: Dictionary of early close dates and times
        exchange: Primary exchange for calendar

    Example:
        >>> calendar = TradingCalendar()
        >>> calendar.is_trading_day(date.today())
        >>> calendar.is_market_open()
    """

    def __init__(self, exchange: Exchange = Exchange.NYSE):
        """Initialize the trading calendar."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Exchange and timezone
        self.exchange = exchange
        self.timezone = ET_TIMEZONE

        # Holiday management
        self.holidays: set[date] = set()
        self.early_closes: dict[date, time] = {}
        self.holiday_names: dict[date, str] = {}

        # Market hours
        self.regular_open = DEFAULT_MARKET_OPEN
        self.regular_close = DEFAULT_MARKET_CLOSE
        self.premarket_open = DEFAULT_PREMARKET_OPEN
        self.afterhours_close = DEFAULT_AFTERHOURS_CLOSE

        # Initialize holidays automatically
        self._load_holidays()

        self.logger.info("%s initialized for %s", self.__class__.__name__, exchange.value)

    # ==========================================================================
    # PUBLIC METHODS - HOLIDAY MANAGEMENT
    # ==========================================================================

    def load_holidays(self) -> None:
        """
        Public method to load/reload holidays.
        This is a wrapper for the private _load_holidays method.
        Required by SpyderA01_Main for initialization.
        """
        try:
            self._load_holidays()
            self.logger.info("Holidays loaded: %s holidays", len(self.holidays))
        except Exception as e:
            self.logger.error("Error loading holidays: %s", e)
            self.error_handler.handle_error(e, "load_holidays")

    def reload_holidays(self) -> None:
        """
        Reload holidays (alias for load_holidays).
        Clears existing holidays and reloads from scratch.
        """
        self.holidays.clear()
        self.early_closes.clear()
        self.holiday_names.clear()
        self.load_holidays()

    def add_custom_holiday(self, holiday_date: date, name: str,
                          is_early_close: bool = False,
                          close_time: time | None = None) -> None:
        """
        Add a custom holiday or early close day.

        Args:
            holiday_date: Date of the holiday
            name: Name of the holiday
            is_early_close: Whether it's an early close day
            close_time: Early close time if applicable
        """
        if is_early_close and close_time:
            self._add_early_close(holiday_date, close_time, name)
        else:
            self._add_holiday(holiday_date, name)

        self.logger.info("Added custom holiday: %s on %s", name, holiday_date)

    # ==========================================================================
    # PUBLIC METHODS - TRADING DAY CHECKS
    # ==========================================================================
    def is_trading_day(self, check_date: date | None = None) -> bool:
        """
        Check if a given date is a trading day.

        Args:
            check_date: The date to check (default: today)

        Returns:
            bool: True if it's a trading day
        """
        if check_date is None:
            check_date = date.today()

        # Check if weekend (Saturday=5, Sunday=6)
        if check_date.weekday() >= 5:
            return False

        # Check if holiday
        return check_date not in self.holidays

    def is_market_open(self, timestamp: datetime | None = None) -> bool:
        """
        Check if the market is open at the given timestamp.

        Args:
            timestamp: The timestamp to check (default: now)

        Returns:
            bool: True if market is open
        """
        try:
            if timestamp is None:
                timestamp = datetime.now(self.timezone)
            else:
                # Ensure timezone aware
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=self.timezone)

            # Check if trading day
            if not self.is_trading_day(timestamp.date()):
                return False

            # Get market hours for the date
            hours = self.get_market_hours(timestamp.date())

            # Check if within regular trading hours
            current_time = timestamp.time()
            return hours.market_open <= current_time <= hours.market_close

        except Exception as e:
            self.logger.error("Error checking market status: %s", e)
            return False

    def is_extended_hours(self, timestamp: datetime | None = None) -> bool:
        """
        Check if in extended trading hours.

        Args:
            timestamp: The timestamp to check

        Returns:
            bool: True if in premarket or afterhours
        """
        try:
            if timestamp is None:
                timestamp = datetime.now(self.timezone)
            else:
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=self.timezone)

            if not self.is_trading_day(timestamp.date()):
                return False

            hours = self.get_market_hours(timestamp.date())
            current_time = timestamp.time()

            # Check premarket
            if (
                hours.premarket_open
                and current_time >= hours.premarket_open
                and current_time < hours.market_open
            ):
                return True

            # Check afterhours
            return bool(hours.afterhours_close and current_time > hours.market_close and current_time <= hours.afterhours_close)

        except Exception as e:
            self.logger.error("Error checking extended hours: %s", e)
            return False

    # ==========================================================================
    # PUBLIC METHODS - MARKET STATUS
    # ==========================================================================
    def get_market_status(self, timestamp: datetime | None = None) -> MarketStatus:
        """
        Get current market status.

        Args:
            timestamp: Timestamp to check

        Returns:
            MarketStatus enum value
        """
        try:
            if timestamp is None:
                timestamp = datetime.now(self.timezone)
            else:
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=self.timezone)

            check_date = timestamp.date()
            timestamp.time()

            # Check weekend
            if check_date.weekday() >= 5:
                return MarketStatus.WEEKEND

            # Check holiday
            if check_date in self.holidays:
                return MarketStatus.HOLIDAY

            # Get market hours
            hours = self.get_market_hours(check_date)

            # Check if market is open
            if self.is_market_open(timestamp):
                # Check if closing soon (last 30 minutes)
                closing_time = datetime.combine(check_date, hours.market_close).replace(
                    tzinfo=self.timezone
                )
                if timestamp >= closing_time - timedelta(minutes=30):
                    return MarketStatus.CLOSING_SOON
                return MarketStatus.OPEN

            # Check if opening soon (30 minutes before open)
            opening_time = datetime.combine(check_date, hours.market_open).replace(
                tzinfo=self.timezone
            )
            if timestamp >= opening_time - timedelta(minutes=30) and timestamp < opening_time:
                return MarketStatus.OPENING_SOON

            # Check for early close
            if hours.is_early_close:
                return MarketStatus.EARLY_CLOSE

            return MarketStatus.CLOSED

        except Exception as e:
            self.logger.error("Error getting market status: %s", e)
            return MarketStatus.CLOSED

    def get_market_session(self, timestamp: datetime | None = None) -> MarketSession:
        """
        Get current market session type.

        Args:
            timestamp: Timestamp to check

        Returns:
            MarketSession enum value
        """
        try:
            if timestamp is None:
                timestamp = datetime.now(self.timezone)
            else:
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=self.timezone)

            if not self.is_trading_day(timestamp.date()):
                return MarketSession.CLOSED

            hours = self.get_market_hours(timestamp.date())
            current_time = timestamp.time()

            # Check sessions in order
            if current_time >= hours.market_open and current_time <= hours.market_close:
                return MarketSession.REGULAR
            elif (
                hours.premarket_open
                and current_time >= hours.premarket_open
                and current_time < hours.market_open
            ):
                return MarketSession.PREMARKET
            elif (
                hours.afterhours_close
                and current_time > hours.market_close
                and current_time <= hours.afterhours_close
            ):
                return MarketSession.AFTERHOURS
            else:
                return MarketSession.CLOSED

        except Exception as e:
            self.logger.error("Error getting market session: %s", e)
            return MarketSession.CLOSED

    # ==========================================================================
    # PUBLIC METHODS - CALENDAR OPERATIONS
    # ==========================================================================
    def get_next_trading_day(self, from_date: date | None = None) -> date:
        """
        Get the next trading day after the given date.

        Args:
            from_date: Starting date (default: today)

        Returns:
            Next trading day
        """
        if from_date is None:
            from_date = date.today()

        next_date = from_date
        max_days = 10  # Safety limit

        for _ in range(max_days):
            next_date = next_date + timedelta(days=1)
            if self.is_trading_day(next_date):
                return next_date

        # Fallback
        self.logger.warning("Could not find next trading day within %s days", max_days)
        return next_date

    def get_previous_trading_day(self, from_date: date | None = None) -> date:
        """
        Get the previous trading day before the given date.

        Args:
            from_date: Starting date (default: today)

        Returns:
            Previous trading day
        """
        if from_date is None:
            from_date = date.today()

        prev_date = from_date
        max_days = 10  # Safety limit

        for _ in range(max_days):
            prev_date = prev_date - timedelta(days=1)
            if self.is_trading_day(prev_date):
                return prev_date

        # Fallback
        self.logger.warning("Could not find previous trading day within %s days", max_days)
        return prev_date

    def get_trading_days(self, start_date: date, end_date: date) -> list[date]:
        """
        Get list of trading days between two dates.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            List of trading days
        """
        trading_days = []
        current_date = start_date

        while current_date <= end_date:
            if self.is_trading_day(current_date):
                trading_days.append(current_date)
            current_date += timedelta(days=1)

        return trading_days

    def get_market_hours(self, for_date: date | None = None) -> MarketHours:
        """
        Get market hours for a specific date.

        Args:
            for_date: Date to get hours for

        Returns:
            MarketHours object
        """
        if for_date is None:
            for_date = date.today()

        # Default hours
        hours = MarketHours(
            date=for_date,
            premarket_open=self.premarket_open,
            market_open=self.regular_open,
            market_close=self.regular_close,
            afterhours_close=self.afterhours_close,
            is_trading_day=self.is_trading_day(for_date),
        )

        # Check for early close
        if for_date in self.early_closes:
            hours.market_close = self.early_closes[for_date]
            hours.is_early_close = True
            hours.afterhours_close = None  # No afterhours on early close days

        # No hours for non-trading days
        if not hours.is_trading_day:
            hours.premarket_open = None
            hours.market_open = None
            hours.market_close = None
            hours.afterhours_close = None

            if for_date in self.holiday_names:
                hours.notes = self.holiday_names[for_date]

        return hours

    # ==========================================================================
    # PUBLIC METHODS - TIME UTILITIES
    # ==========================================================================
    def time_until_open(self, timestamp: datetime | None = None) -> timedelta | None:
        """
        Get time until market opens.

        Args:
            timestamp: Current timestamp

        Returns:
            timedelta until open, or None if market is open
        """
        if timestamp is None:
            timestamp = datetime.now(self.timezone)

        if self.is_market_open(timestamp):
            return None

        # Find next market open
        current_date = timestamp.date()
        for days_ahead in range(7):  # Check up to a week ahead
            check_date = current_date + timedelta(days=days_ahead)

            if self.is_trading_day(check_date):
                hours = self.get_market_hours(check_date)
                open_time = datetime.combine(check_date, hours.market_open)
                open_time = open_time.replace(tzinfo=self.timezone)

                if open_time > timestamp:
                    return open_time - timestamp

        return None

    def time_until_close(self, timestamp: datetime | None = None) -> timedelta | None:
        """
        Get time until market closes.

        Args:
            timestamp: Current timestamp

        Returns:
            timedelta until close, or None if market is closed
        """
        if timestamp is None:
            timestamp = datetime.now(self.timezone)

        if not self.is_market_open(timestamp):
            return None

        hours = self.get_market_hours(timestamp.date())
        close_time = datetime.combine(timestamp.date(), hours.market_close)
        close_time = close_time.replace(tzinfo=self.timezone)

        return close_time - timestamp

    def get_holidays_for_year(self, year: int) -> list[Holiday]:
        """
        Get all holidays for a specific year.

        Args:
            year: Year to get holidays for

        Returns:
            List of Holiday objects
        """
        holidays_list = []
        for holiday_date in self.holidays:
            if holiday_date.year == year:
                holiday_name = self.holiday_names.get(holiday_date, "Unknown Holiday")
                holidays_list.append(
                    Holiday(
                        date=holiday_date,
                        name=holiday_name,
                        exchange=self.exchange
                    )
                )

        return sorted(holidays_list, key=lambda h: h.date)

    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================
    def _load_holidays(self):
        """Load market holidays for the current and next year."""
        current_year = date.today().year

        # US Market Holidays for 2025 (and pattern for other years)
        self._add_fixed_holidays(current_year)
        self._add_fixed_holidays(current_year + 1)

        # Load custom holidays from file if exists
        self._load_custom_holidays()

        self.logger.info("Loaded %s holidays", len(self.holidays))

    def _add_fixed_holidays(self, year: int):
        """Add fixed US market holidays for a given year."""
        # New Year's Day
        self._add_holiday(date(year, 1, 1), "New Year's Day")

        # Martin Luther King Jr. Day (3rd Monday in January)
        self._add_holiday(
            self._get_nth_weekday_of_month(year, 1, 0, 3), "Martin Luther King Jr. Day"
        )

        # Presidents Day (3rd Monday in February)
        self._add_holiday(self._get_nth_weekday_of_month(year, 2, 0, 3), "Presidents Day")

        # Good Friday (calculated based on Easter)
        good_friday = self._calculate_good_friday(year)
        if good_friday:
            self._add_holiday(good_friday, "Good Friday")

        # Memorial Day (Last Monday in May)
        self._add_holiday(self._get_last_weekday_of_month(year, 5, 0), "Memorial Day")

        # Juneteenth (June 19)
        self._add_holiday(date(year, 6, 19), "Juneteenth")

        # Independence Day (July 4)
        self._add_holiday(date(year, 7, 4), "Independence Day")

        # Labor Day (1st Monday in September)
        self._add_holiday(self._get_nth_weekday_of_month(year, 9, 0, 1), "Labor Day")

        # Thanksgiving (4th Thursday in November)
        thanksgiving = self._get_nth_weekday_of_month(year, 11, 3, 4)
        self._add_holiday(thanksgiving, "Thanksgiving")

        # Day after Thanksgiving (Early close)
        day_after_thanksgiving = thanksgiving + timedelta(days=1)
        self._add_early_close(day_after_thanksgiving, time(13, 0), "Day after Thanksgiving")

        # Christmas (December 25)
        self._add_holiday(date(year, 12, 25), "Christmas")

        # Christmas Eve (Early close if not weekend)
        christmas_eve = date(year, 12, 24)
        if christmas_eve.weekday() < 5:
            self._add_early_close(christmas_eve, time(13, 0), "Christmas Eve")

    def _add_holiday(self, holiday_date: date, name: str):
        """Add a holiday to the calendar."""
        # Adjust for weekends
        adjusted_date = self._adjust_holiday_for_weekend(holiday_date)
        self.holidays.add(adjusted_date)
        self.holiday_names[adjusted_date] = name

    def _add_early_close(self, close_date: date, close_time: time, name: str):
        """Add an early close day."""
        if close_date.weekday() < 5:  # Only if weekday
            self.early_closes[close_date] = close_time
            self.holiday_names[close_date] = f"{name} (Early Close)"

    def _adjust_holiday_for_weekend(self, holiday_date: date) -> date:
        """Adjust holiday if it falls on weekend."""
        # If Saturday, observe on Friday
        if holiday_date.weekday() == 5:
            return holiday_date - timedelta(days=1)
        # If Sunday, observe on Monday
        elif holiday_date.weekday() == 6:
            return holiday_date + timedelta(days=1)
        else:
            return holiday_date

    def _get_nth_weekday_of_month(self, year: int, month: int, weekday: int, n: int) -> date:
        """Get the nth occurrence of a weekday in a month."""
        first_day = date(year, month, 1)
        first_weekday = first_day.weekday()

        # Calculate days until the first occurrence of the target weekday
        days_until_weekday = (weekday - first_weekday) % 7
        first_occurrence = first_day + timedelta(days=days_until_weekday)

        # Add weeks to get to the nth occurrence
        target_date = first_occurrence + timedelta(weeks=n - 1)

        return target_date

    def _get_last_weekday_of_month(self, year: int, month: int, weekday: int) -> date:
        """Get the last occurrence of a weekday in a month."""
        # Start from the last day of the month
        if month == 12:
            last_day = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = date(year, month + 1, 1) - timedelta(days=1)

        # Work backwards to find the last occurrence
        while last_day.weekday() != weekday:
            last_day -= timedelta(days=1)

        return last_day

    def _calculate_good_friday(self, year: int) -> date | None:
        """Calculate Good Friday date (2 days before Easter)."""
        # Simplified calculation - would use more complex algorithm in production
        # This is approximate for demonstration
        try:
            # Easter calculation (Western Christianity)
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
            easter_l = (32 + 2 * e + 2 * i - h - k) % 7
            m = (a + 11 * h + 22 * easter_l) // 451
            month = (h + easter_l - 7 * m + 114) // 31
            day = ((h + easter_l - 7 * m + 114) % 31) + 1

            easter = date(year, month, day)
            good_friday = easter - timedelta(days=2)

            return good_friday

        except Exception as e:
            self.logger.error("Error calculating Good Friday for %s: %s", year, e)
            return None

    def _load_custom_holidays(self):
        """Load custom holidays from file."""
        try:
            if os.path.exists(HOLIDAY_FILE):
                with open(HOLIDAY_FILE) as f:
                    custom_holidays = json.load(f)

                for holiday_str, name in custom_holidays.items():
                    holiday_date = datetime.strptime(holiday_str, "%Y-%m-%d").date()
                    self._add_holiday(holiday_date, name)

                self.logger.info("Loaded %s custom holidays", len(custom_holidays))

        except Exception as e:
            self.logger.debug("No custom holidays loaded: %s", e)

    def save_custom_holidays(self, filepath: str | None = None) -> bool:
        """
        Save current holidays to a JSON file.

        Args:
            filepath: Path to save file (default: HOLIDAY_FILE)

        Returns:
            bool: True if saved successfully
        """
        try:
            save_path = filepath or HOLIDAY_FILE
            holidays_dict = {
                date_obj.strftime("%Y-%m-%d"): name
                for date_obj, name in self.holiday_names.items()
            }

            with open(save_path, "w") as f:
                json.dump(holidays_dict, f, indent=2)

            self.logger.info("Saved %s holidays to %s", len(holidays_dict), save_path)
            return True

        except Exception as e:
            self.logger.error("Error saving holidays: %s", e)
            return False

    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def start(self) -> None:
        """Start the trading calendar (compatibility method)."""
        self.logger.info("Trading calendar started")

    def stop(self) -> None:
        """Stop the trading calendar (compatibility method)."""
        self.logger.info("Trading calendar stopped")

    def cleanup(self) -> None:
        """Clean up calendar resources."""
        self.holidays.clear()
        self.early_closes.clear()
        self.holiday_names.clear()
        self.logger.info("Trading calendar cleanup completed")


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
# Global instance
_trading_calendar_instance: TradingCalendar | None = None


def get_trading_calendar(exchange: Exchange = Exchange.NYSE) -> TradingCalendar:
    """
    Get singleton trading calendar instance.

    Args:
        exchange: Exchange for calendar

    Returns:
        TradingCalendar instance
    """
    global _trading_calendar_instance
    if _trading_calendar_instance is None:
        _trading_calendar_instance = TradingCalendar(exchange)
    return _trading_calendar_instance


# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# For backward compatibility
__all__ = [
    "TradingCalendar",
    "get_trading_calendar",
    "MarketSession",
    "MarketStatus",
    "Exchange",
    "MarketHours",
    "Holiday",
]

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code
    calendar = TradingCalendar()


    # Test current status

    # Test the public load_holidays method
    calendar.load_holidays()

    # Test next/previous trading days

    # Test market hours
    hours = calendar.get_market_hours()

    # Test time calculations
    time_to_open = calendar.time_until_open()
    if time_to_open:
        pass

    time_to_close = calendar.time_until_close()
    if time_to_close:
        pass

    # Test holiday retrieval
    holidays_2025 = calendar.get_holidays_for_year(2025)
    for _holiday in holidays_2025[:5]:  # Show first 5
        pass

    # Cleanup
    calendar.cleanup()
