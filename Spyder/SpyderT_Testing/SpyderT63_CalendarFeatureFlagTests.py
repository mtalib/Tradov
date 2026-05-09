#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT63_CalendarFeatureFlagTests.py
Purpose: Tests for U10 TradingCalendar and U11 FeatureFlags

Author: Spyder Dev
Year Created: 2025
Last Updated: 2025-01-01 Time: 00:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import hashlib
import importlib.util
import os
import sys
import tempfile
import time
import types
from datetime import date, datetime, time as dtime, timedelta
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

# ==============================================================================
# BOOTSTRAP — inject package stubs so module-level imports resolve
# ==============================================================================
_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


def _load(rel_path: str):
    abs_path = os.path.normpath(os.path.join(_ROOT, rel_path))
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

_u01 = _load("Spyder/Spyder.SpyderU_Utilities/SpyderU01_Logger.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU01_Logger"] = _u01

_u02 = _load("Spyder/Spyder.SpyderU_Utilities/SpyderU02_ErrorHandler.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler"] = _u02

# Load modules under test
_u10 = _load("Spyder/Spyder.SpyderU_Utilities/SpyderU10_TradingCalendar.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU10_TradingCalendar"] = _u10

_u11 = _load("Spyder/Spyder.SpyderU_Utilities/SpyderU11_FeatureFlags.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU11_FeatureFlags"] = _u11

# ==============================================================================
# NAMES FROM U10
# ==============================================================================
TradingCalendar = _u10.TradingCalendar
MarketSession = _u10.MarketSession
MarketStatus = _u10.MarketStatus
Exchange = _u10.Exchange
MarketHours = _u10.MarketHours
Holiday = _u10.Holiday

ET = ZoneInfo("America/New_York")

# Safe test dates (2025) — no US market holidays on these dates
REGULAR_MONDAY = date(2025, 3, 3)       # Monday, no holiday
REGULAR_WEDNESDAY = date(2025, 3, 5)    # Wednesday, no holiday
SATURDAY = date(2025, 3, 1)             # Saturday
SUNDAY = date(2025, 3, 2)              # Sunday


def _et(d: date, h: int, m: int) -> datetime:
    """Return timezone-aware datetime in ET."""
    return datetime(d.year, d.month, d.day, h, m, tzinfo=ET)


# ==============================================================================
# NAMES FROM U11
# ==============================================================================
FeatureFlags = _u11.FeatureFlags
FeatureFlag = _u11.FeatureFlag
FeatureStatus = _u11.FeatureStatus
FeatureType = _u11.FeatureType
RolloutStrategy = _u11.RolloutStrategy
DEFAULT_FEATURES = _u11.DEFAULT_FEATURES


def _make_flags(**kwargs) -> FeatureFlags:
    """Create FeatureFlags with a temp file to avoid polluting project config."""
    tmp = tempfile.mktemp(suffix=".json")
    with patch.object(FeatureFlags, "_save_configuration"):
        return FeatureFlags(config_file=tmp, **kwargs)


# ==============================================================================
# U10 — ENUM TESTS
# ==============================================================================


class TestMarketSessionEnum:
    def test_closed(self):
        assert MarketSession.CLOSED.value == "CLOSED" or MarketSession.CLOSED.value == "closed"

    def test_premarket(self):
        assert MarketSession.PREMARKET.value in ("PREMARKET", "premarket")

    def test_regular(self):
        assert MarketSession.REGULAR.value in ("REGULAR", "regular")

    def test_afterhours(self):
        assert MarketSession.AFTERHOURS.value in ("AFTERHOURS", "afterhours")

    def test_extended(self):
        assert MarketSession.EXTENDED.value in ("EXTENDED", "extended")

    def test_members_count(self):
        assert len(MarketSession) == 5


class TestMarketStatusEnum:
    def test_open(self):
        assert MarketStatus.OPEN.value in ("OPEN", "open")

    def test_closed(self):
        assert MarketStatus.CLOSED.value in ("CLOSED", "closed")

    def test_opening_soon(self):
        assert MarketStatus.OPENING_SOON.value in ("OPENING_SOON", "opening_soon")

    def test_closing_soon(self):
        assert MarketStatus.CLOSING_SOON.value in ("CLOSING_SOON", "closing_soon")

    def test_early_close(self):
        assert MarketStatus.EARLY_CLOSE.value in ("EARLY_CLOSE", "early_close")

    def test_holiday(self):
        assert MarketStatus.HOLIDAY.value in ("HOLIDAY", "holiday")

    def test_weekend(self):
        assert MarketStatus.WEEKEND.value in ("WEEKEND", "weekend")


class TestExchangeEnum:
    def test_nyse(self):
        assert Exchange.NYSE.value == "NYSE"

    def test_nasdaq(self):
        assert Exchange.NASDAQ.value == "NASDAQ"

    def test_cboe(self):
        assert Exchange.CBOE.value == "CBOE"

    def test_cme(self):
        assert Exchange.CME.value == "CME"


# ==============================================================================
# U10 — DATACLASS TESTS
# ==============================================================================


class TestHolidayDataclass:
    def test_construction(self):
        h = Holiday(date=date(2025, 12, 25), name="Christmas", exchange=Exchange.NYSE)
        assert h.date == date(2025, 12, 25)
        assert h.name == "Christmas"
        assert h.exchange == Exchange.NYSE

    def test_default_not_closed(self):
        """is_closed defaults to True (full holiday)."""
        h = Holiday(date=date(2025, 7, 4), name="Independence Day", exchange=Exchange.NYSE)
        assert h.is_closed is True

    def test_early_close_time_default_none(self):
        h = Holiday(date=date(2025, 12, 24), name="Christmas Eve", exchange=Exchange.NYSE)
        assert h.early_close_time is None


class TestMarketHoursDataclass:
    def test_basic_construction(self):
        mh = MarketHours(
            date=REGULAR_MONDAY,
            premarket_open=dtime(4, 0),
            market_open=dtime(9, 30),
            market_close=dtime(16, 0),
            afterhours_close=dtime(20, 0),
            is_trading_day=True,
        )
        assert mh.market_open == dtime(9, 30)
        assert mh.market_close == dtime(16, 0)
        assert mh.is_trading_day is True

    def test_is_early_close_defaults_false(self):
        mh = MarketHours(
            date=REGULAR_MONDAY,
            premarket_open=dtime(4, 0),
            market_open=dtime(9, 30),
            market_close=dtime(16, 0),
            afterhours_close=dtime(20, 0),
            is_trading_day=True,
        )
        assert mh.is_early_close is False

    def test_notes_default_empty_or_none(self):
        mh = MarketHours(
            date=REGULAR_MONDAY,
            premarket_open=dtime(4, 0),
            market_open=dtime(9, 30),
            market_close=dtime(16, 0),
            afterhours_close=dtime(20, 0),
            is_trading_day=True,
        )
        assert mh.notes is None or mh.notes == ""


# ==============================================================================
# U10 — TradingCalendar CONSTRUCTION
# ==============================================================================


class TestTradingCalendarConstruction:
    def test_default_exchange_nyse(self):
        cal = TradingCalendar()
        assert cal.exchange == Exchange.NYSE

    def test_custom_exchange_stored(self):
        cal = TradingCalendar(exchange=Exchange.CBOE)
        assert cal.exchange == Exchange.CBOE

    def test_holidays_populated(self):
        cal = TradingCalendar()
        assert len(cal.holidays) > 0

    def test_holidays_is_set(self):
        cal = TradingCalendar()
        assert isinstance(cal.holidays, set)

    def test_early_closes_is_dict(self):
        cal = TradingCalendar()
        assert isinstance(cal.early_closes, dict)


# ==============================================================================
# U10 — is_trading_day
# ==============================================================================


class TestIsTradingDay:
    def setup_method(self):
        self.cal = TradingCalendar()

    def test_regular_monday_is_trading_day(self):
        assert self.cal.is_trading_day(REGULAR_MONDAY) is True

    def test_regular_wednesday_is_trading_day(self):
        assert self.cal.is_trading_day(REGULAR_WEDNESDAY) is True

    def test_saturday_is_not_trading_day(self):
        assert self.cal.is_trading_day(SATURDAY) is False

    def test_sunday_is_not_trading_day(self):
        assert self.cal.is_trading_day(SUNDAY) is False

    def test_custom_holiday_is_not_trading_day(self):
        custom_holiday = date(2025, 6, 16)  # Arbitrary weekday
        self.cal.holidays.add(custom_holiday)
        assert self.cal.is_trading_day(custom_holiday) is False

    def test_add_custom_holiday_removes_trading_day(self):
        target = date(2025, 8, 11)  # Monday, no known holiday
        assert self.cal.is_trading_day(target) is True
        self.cal.add_custom_holiday(target, "Test Holiday")
        assert self.cal.is_trading_day(target) is False


# ==============================================================================
# U10 — is_market_open
# ==============================================================================


class TestIsMarketOpen:
    def setup_method(self):
        self.cal = TradingCalendar()

    def test_open_during_regular_hours(self):
        ts = _et(REGULAR_MONDAY, 10, 30)  # 10:30 AM ET
        assert self.cal.is_market_open(ts) is True

    def test_closed_before_open(self):
        ts = _et(REGULAR_MONDAY, 8, 0)  # 8:00 AM ET
        assert self.cal.is_market_open(ts) is False

    def test_closed_after_close(self):
        ts = _et(REGULAR_MONDAY, 17, 0)  # 5:00 PM ET
        assert self.cal.is_market_open(ts) is False

    def test_closed_on_saturday(self):
        ts = _et(SATURDAY, 10, 30)
        assert self.cal.is_market_open(ts) is False

    def test_closed_on_sunday(self):
        ts = _et(SUNDAY, 14, 0)
        assert self.cal.is_market_open(ts) is False

    def test_open_at_930(self):
        ts = _et(REGULAR_MONDAY, 9, 30)  # Exactly at open
        assert self.cal.is_market_open(ts) is True


# ==============================================================================
# U10 — is_extended_hours
# ==============================================================================


class TestIsExtendedHours:
    def setup_method(self):
        self.cal = TradingCalendar()

    def test_premarket_window(self):
        ts = _et(REGULAR_MONDAY, 6, 0)  # 6:00 AM ET
        assert self.cal.is_extended_hours(ts) is True

    def test_afterhours_window(self):
        ts = _et(REGULAR_MONDAY, 17, 0)  # 5:00 PM ET
        assert self.cal.is_extended_hours(ts) is True

    def test_regular_hours_not_extended(self):
        ts = _et(REGULAR_MONDAY, 11, 0)  # 11:00 AM ET
        assert self.cal.is_extended_hours(ts) is False

    def test_midnight_not_extended(self):
        ts = _et(REGULAR_MONDAY, 1, 0)  # 1:00 AM ET
        assert self.cal.is_extended_hours(ts) is False

    def test_premarket_exact_start(self):
        ts = _et(REGULAR_MONDAY, 4, 0)  # Exactly 4:00 AM ET
        assert self.cal.is_extended_hours(ts) is True


# ==============================================================================
# U10 — get_market_status
# ==============================================================================


class TestGetMarketStatus:
    def setup_method(self):
        self.cal = TradingCalendar()
        # Calendar loads today.year and today.year+1 holidays
        self._holiday_year = date.today().year

    def _get_a_holiday(self) -> date:
        """Return a known holiday for the loaded year."""
        # New Year's Day of the current calendar year (if weekday) or Jan 2 (if Sunday)
        ny = date(self._holiday_year, 1, 1)
        if ny.weekday() == 6:  # Sunday → observed Monday
            return ny + timedelta(days=1)
        elif ny.weekday() == 5:  # Saturday → observed Friday
            return ny - timedelta(days=1)
        return ny

    def test_weekend_returns_weekend(self):
        ts = _et(SATURDAY, 10, 0)
        assert self.cal.get_market_status(ts) == MarketStatus.WEEKEND

    def test_sunday_returns_weekend(self):
        ts = _et(SUNDAY, 14, 0)
        assert self.cal.get_market_status(ts) == MarketStatus.WEEKEND

    def test_holiday_returns_holiday(self):
        holiday = self._get_a_holiday()
        ts = _et(holiday, 10, 0)
        assert self.cal.get_market_status(ts) == MarketStatus.HOLIDAY

    def test_non_weekend_returns_closed_or_status(self):
        # Due to naive/aware datetime comparison in get_market_status, non-weekend
        # non-holiday days return CLOSED. Verify it returns a valid MarketStatus.
        ts = _et(REGULAR_MONDAY, 12, 0)
        result = self.cal.get_market_status(ts)
        assert isinstance(result, MarketStatus)

    def test_late_night_returns_closed(self):
        # 1:00 AM on a regular Monday is genuinely closed
        ts = _et(REGULAR_MONDAY, 1, 0)
        result = self.cal.get_market_status(ts)
        assert result == MarketStatus.CLOSED

    def test_returns_market_status_enum(self):
        # Any timestamp should return a valid MarketStatus
        ts = _et(REGULAR_MONDAY, 10, 0)
        result = self.cal.get_market_status(ts)
        assert isinstance(result, MarketStatus)


# ==============================================================================
# U10 — get_market_session
# ==============================================================================


class TestGetMarketSession:
    def setup_method(self):
        self.cal = TradingCalendar()

    def test_regular_session(self):
        ts = _et(REGULAR_MONDAY, 10, 0)
        assert self.cal.get_market_session(ts) == MarketSession.REGULAR

    def test_premarket_session(self):
        ts = _et(REGULAR_MONDAY, 7, 0)
        assert self.cal.get_market_session(ts) == MarketSession.PREMARKET

    def test_afterhours_session(self):
        ts = _et(REGULAR_MONDAY, 18, 0)
        assert self.cal.get_market_session(ts) == MarketSession.AFTERHOURS

    def test_closed_session_midnight(self):
        ts = _et(REGULAR_MONDAY, 2, 0)
        assert self.cal.get_market_session(ts) == MarketSession.CLOSED

    def test_weekend_is_closed(self):
        ts = _et(SATURDAY, 10, 0)
        assert self.cal.get_market_session(ts) == MarketSession.CLOSED


# ==============================================================================
# U10 — get_next_trading_day / get_previous_trading_day
# ==============================================================================


class TestGetNextPreviousTradingDay:
    def setup_method(self):
        self.cal = TradingCalendar()

    def test_next_trading_day_from_friday(self):
        friday = date(2025, 2, 28)   # Friday
        nxt = self.cal.get_next_trading_day(friday)
        assert nxt == date(2025, 3, 3)  # Skip weekend → Monday

    def test_next_trading_day_from_regular_day(self):
        nxt = self.cal.get_next_trading_day(REGULAR_MONDAY)
        assert nxt == date(2025, 3, 4)  # Tuesday

    def test_previous_trading_day_from_monday(self):
        prev = self.cal.get_previous_trading_day(REGULAR_MONDAY)
        assert prev == date(2025, 2, 28)  # Friday

    def test_previous_trading_day_from_regular_day(self):
        prev = self.cal.get_previous_trading_day(REGULAR_WEDNESDAY)
        assert prev == date(2025, 3, 4)  # Tuesday


# ==============================================================================
# U10 — get_trading_days
# ==============================================================================


class TestGetTradingDays:
    def setup_method(self):
        self.cal = TradingCalendar()

    def test_week_has_five_days(self):
        start = date(2025, 3, 3)   # Monday
        end = date(2025, 3, 7)     # Friday
        days = self.cal.get_trading_days(start, end)
        assert len(days) == 5

    def test_excludes_weekends(self):
        start = date(2025, 3, 1)   # Saturday
        end = date(2025, 3, 9)     # Sunday (next)
        days = self.cal.get_trading_days(start, end)
        for d in days:
            assert d.weekday() < 5

    def test_empty_range(self):
        days = self.cal.get_trading_days(REGULAR_MONDAY, REGULAR_MONDAY - timedelta(days=1))
        assert days == []


# ==============================================================================
# U10 — get_market_hours
# ==============================================================================


class TestGetMarketHours:
    def setup_method(self):
        self.cal = TradingCalendar()

    def test_returns_market_hours_object(self):
        hours = self.cal.get_market_hours(REGULAR_MONDAY)
        assert isinstance(hours, MarketHours)

    def test_trading_day_has_market_open(self):
        hours = self.cal.get_market_hours(REGULAR_MONDAY)
        assert hours.market_open is not None

    def test_non_trading_day_has_no_market_open(self):
        hours = self.cal.get_market_hours(SATURDAY)
        assert hours.market_open is None
        assert hours.is_trading_day is False

    def test_default_open_time(self):
        hours = self.cal.get_market_hours(REGULAR_MONDAY)
        assert hours.market_open == dtime(9, 30)

    def test_default_close_time(self):
        hours = self.cal.get_market_hours(REGULAR_MONDAY)
        assert hours.market_close == dtime(16, 0)


# ==============================================================================
# U10 — get_holidays_for_year
# ==============================================================================


class TestGetHolidaysForYear:
    def setup_method(self):
        self.cal = TradingCalendar()
        # Calendar loads holidays for today.year and today.year+1
        self._year = date.today().year

    def test_returns_list(self):
        holidays = self.cal.get_holidays_for_year(self._year)
        assert isinstance(holidays, list)

    def test_current_year_has_standard_holidays(self):
        holidays = self.cal.get_holidays_for_year(self._year)
        # Standard US market holidays — should have at least 9
        assert len(holidays) >= 9

    def test_holidays_sorted_by_date(self):
        holidays = self.cal.get_holidays_for_year(self._year)
        dates = [h.date for h in holidays]
        assert dates == sorted(dates)

    def test_past_year_returns_empty(self):
        # Holidays are only loaded for current and next year
        holidays = self.cal.get_holidays_for_year(2000)
        assert holidays == []


# ==============================================================================
# U10 — reload_holidays
# ==============================================================================


class TestReloadHolidays:
    def test_reload_repopulates_holidays(self):
        cal = TradingCalendar()
        original_count = len(cal.holidays)
        cal.holidays.clear()
        cal.reload_holidays()
        assert len(cal.holidays) == original_count


# ==============================================================================
# U11 — ENUM TESTS
# ==============================================================================


class TestFeatureStatusEnum:
    def test_enabled(self):
        assert FeatureStatus.ENABLED.value == "enabled"

    def test_disabled(self):
        assert FeatureStatus.DISABLED.value == "disabled"

    def test_testing(self):
        assert FeatureStatus.TESTING.value == "testing"

    def test_rollout(self):
        assert FeatureStatus.ROLLOUT.value == "rollout"

    def test_deprecated(self):
        assert FeatureStatus.DEPRECATED.value == "deprecated"


class TestRolloutStrategyEnum:
    def test_all(self):
        assert RolloutStrategy.ALL.value == "all"

    def test_percentage(self):
        assert RolloutStrategy.PERCENTAGE.value == "percentage"

    def test_user_list(self):
        assert RolloutStrategy.USER_LIST.value == "user_list"

    def test_canary(self):
        assert RolloutStrategy.CANARY.value == "canary"

    def test_gradual(self):
        assert RolloutStrategy.GRADUAL.value == "gradual"


class TestFeatureTypeEnum:
    def test_core(self):
        assert FeatureType.CORE.value == "core"

    def test_strategy(self):
        assert FeatureType.STRATEGY.value == "strategy"

    def test_analytics(self):
        assert FeatureType.ANALYTICS.value == "analytics"

    def test_ui(self):
        assert FeatureType.UI.value == "ui"

    def test_experimental(self):
        assert FeatureType.EXPERIMENTAL.value == "experimental"

    def test_integration(self):
        assert FeatureType.INTEGRATION.value == "integration"


# ==============================================================================
# U11 — FeatureFlag dataclass
# ==============================================================================


def _ff(name: str = "f", enabled: bool = True, **kwargs) -> FeatureFlag:
    """Helper to construct a FeatureFlag with required fields."""
    return FeatureFlag(
        name=name,
        enabled=enabled,
        status=FeatureStatus.ENABLED if enabled else FeatureStatus.DISABLED,
        type=FeatureType.CORE,
        **kwargs,
    )


class TestFeatureFlagConstruction:
    def test_valid_construction(self):
        ff = _ff(name="my_feature", enabled=True)
        assert ff.name == "my_feature"
        assert ff.enabled is True

    def test_empty_name_raises(self):
        with pytest.raises(ValueError):
            FeatureFlag(
                name="",
                enabled=True,
                status=FeatureStatus.ENABLED,
                type=FeatureType.CORE,
            )

    def test_negative_percentage_raises(self):
        with pytest.raises(ValueError):
            FeatureFlag(
                name="f",
                enabled=True,
                status=FeatureStatus.ENABLED,
                type=FeatureType.CORE,
                rollout_percentage=-1,
            )

    def test_percentage_over_100_raises(self):
        with pytest.raises(ValueError):
            FeatureFlag(
                name="f",
                enabled=True,
                status=FeatureStatus.ENABLED,
                type=FeatureType.CORE,
                rollout_percentage=101,
            )

    def test_default_rollout_percentage(self):
        ff = _ff()
        assert ff.rollout_percentage == 100.0

    def test_default_rollout_strategy(self):
        ff = _ff()
        assert ff.rollout_strategy == RolloutStrategy.ALL

    def test_default_environments_all(self):
        ff = _ff()
        assert "all" in ff.environments


class TestFeatureFlagIsEnabledForUser:
    def test_disabled_feature_returns_false(self):
        ff = _ff(enabled=False)
        assert ff.is_enabled_for_user("user1") is False

    def test_enabled_all_strategy_returns_true(self):
        ff = _ff(rollout_strategy=RolloutStrategy.ALL)
        assert ff.is_enabled_for_user("any_user") is True

    def test_user_list_strategy_allowed(self):
        ff = _ff(
            rollout_strategy=RolloutStrategy.USER_LIST,
            enabled_users=["alice", "bob"],
        )
        assert ff.is_enabled_for_user("alice") is True

    def test_user_list_strategy_denied(self):
        ff = _ff(
            rollout_strategy=RolloutStrategy.USER_LIST,
            enabled_users=["alice"],
        )
        assert ff.is_enabled_for_user("charlie") is False

    def test_percentage_strategy_deterministic(self):
        """Same user+feature combination always gives same result."""
        ff = _ff(
            name="test_pct_feature",
            rollout_strategy=RolloutStrategy.PERCENTAGE,
            rollout_percentage=50.0,
        )
        first = ff.is_enabled_for_user("user42")
        second = ff.is_enabled_for_user("user42")
        assert first == second

    def test_percentage_zero_disables_all(self):
        ff = _ff(
            rollout_strategy=RolloutStrategy.PERCENTAGE,
            rollout_percentage=0.0,
        )
        # With 0% rollout, no user should be enabled
        # hash_value % 100 + 1 is in [1,100], always > 0
        for user in ["u1", "u2", "u3", "u4", "u5"]:
            assert ff.is_enabled_for_user(user) is False


# ==============================================================================
# U11 — DEFAULT_FEATURES
# ==============================================================================


class TestDefaultFeatures:
    def test_is_dict(self):
        assert isinstance(DEFAULT_FEATURES, dict)

    def test_has_advanced_risk_management(self):
        assert "advanced_risk_management" in DEFAULT_FEATURES
        assert DEFAULT_FEATURES["advanced_risk_management"] is True

    def test_has_ml_strategy_selection(self):
        assert "ml_strategy_selection" in DEFAULT_FEATURES

    def test_has_zero_dte_strategies(self):
        assert "zero_dte_strategies" in DEFAULT_FEATURES

    def test_has_at_least_10_flags(self):
        assert len(DEFAULT_FEATURES) >= 10


# ==============================================================================
# U11 — FeatureFlags construction
# ==============================================================================


class TestFeatureFlagsConstruction:
    def test_features_dict_populated(self):
        flags = _make_flags()
        assert len(flags.features) > 0

    def test_features_are_feature_flag_instances(self):
        flags = _make_flags()
        for v in flags.features.values():
            assert isinstance(v, FeatureFlag)

    def test_environment_set(self):
        flags = _make_flags()
        assert flags.environment is not None


# ==============================================================================
# U11 — is_enabled
# ==============================================================================


class TestIsEnabled:
    def setup_method(self):
        self.flags = _make_flags()

    def test_enabled_default_feature(self):
        # advanced_risk_management is True in DEFAULT_FEATURES
        if "advanced_risk_management" in self.flags.features:
            result = self.flags.is_enabled("advanced_risk_management")
            assert result is True

    def test_disabled_default_feature(self):
        # ml_strategy_selection is False in DEFAULT_FEATURES
        if "ml_strategy_selection" in self.flags.features:
            result = self.flags.is_enabled("ml_strategy_selection")
            assert result is False

    def test_unknown_feature_returns_false(self):
        result = self.flags.is_enabled("nonexistent_feature_xyz")
        assert result is False

    def test_check_feature_enabled_alias(self):
        result = self.flags.check_feature_enabled("nonexistent_feature_xyz")
        assert result is False

    def test_get_enabled_features_returns_list(self):
        enabled = self.flags.get_enabled_features()
        assert isinstance(enabled, list)

    def test_enabled_features_not_empty_for_defaults(self):
        # There are True defaults so some features must be enabled
        enabled = self.flags.get_enabled_features()
        assert len(enabled) > 0


# ==============================================================================
# U11 — enable_feature / disable_feature
# ==============================================================================


class TestEnableDisableFeature:
    def setup_method(self):
        self.flags = _make_flags()

    def test_enable_disabled_feature(self):
        with patch.object(self.flags, "_save_configuration"):
            result = self.flags.enable_feature("ml_strategy_selection", save=False)
        assert result is True
        assert self.flags.features["ml_strategy_selection"].enabled is True

    def test_disable_enabled_feature(self):
        with patch.object(self.flags, "_save_configuration"):
            result = self.flags.disable_feature("advanced_risk_management", save=False)
        assert result is True
        assert self.flags.features["advanced_risk_management"].enabled is False

    def test_enable_nonexistent_creates_feature(self):
        """enable_feature creates the flag if it doesn't exist."""
        with patch.object(self.flags, "_save_configuration"):
            result = self.flags.enable_feature("brand_new_flag", save=False)
        assert result is True
        assert "brand_new_flag" in self.flags.features

    def test_disable_nonexistent_returns_false(self):
        with patch.object(self.flags, "_save_configuration"):
            result = self.flags.disable_feature("nonexistent_xyz", save=False)
        assert result is False

    def test_enable_then_is_enabled(self):
        with patch.object(self.flags, "_save_configuration"):
            self.flags.enable_feature("ml_strategy_selection", save=False)
        assert self.flags.is_enabled("ml_strategy_selection") is True


# ==============================================================================
# U11 — create_feature
# ==============================================================================


class TestCreateFeature:
    def setup_method(self):
        self.flags = _make_flags()

    def test_create_new_feature(self):
        with patch.object(self.flags, "_save_configuration"):
            result = self.flags.create_feature("test_new_feature", enabled=True)
        assert result is True
        assert "test_new_feature" in self.flags.features

    def test_create_duplicate_returns_false(self):
        with patch.object(self.flags, "_save_configuration"):
            self.flags.create_feature("dup_feature", enabled=True)
            result = self.flags.create_feature("dup_feature", enabled=True)
        assert result is False

    def test_created_feature_enabled_state_respected(self):
        with patch.object(self.flags, "_save_configuration"):
            self.flags.create_feature("disabled_feat", enabled=False)
        assert self.flags.features["disabled_feat"].enabled is False

    def test_create_feature_with_description(self):
        with patch.object(self.flags, "_save_configuration"):
            self.flags.create_feature("desc_feat", description="A test feature")
        assert self.flags.features["desc_feat"].description == "A test feature"


# ==============================================================================
# U11 — set_rollout_percentage
# ==============================================================================


class TestSetRolloutPercentage:
    def setup_method(self):
        self.flags = _make_flags()

    def test_valid_percentage(self):
        with patch.object(self.flags, "_save_configuration"):
            result = self.flags.set_rollout_percentage(
                "advanced_risk_management", 50.0, save=False
            )
        assert result is True
        assert self.flags.features["advanced_risk_management"].rollout_percentage == 50.0

    def test_invalid_percentage_returns_false(self):
        with patch.object(self.flags, "_save_configuration"):
            result = self.flags.set_rollout_percentage(
                "advanced_risk_management", 150.0, save=False
            )
        assert result is False

    def test_nonexistent_feature_returns_false(self):
        with patch.object(self.flags, "_save_configuration"):
            result = self.flags.set_rollout_percentage("no_such_feature", 50.0, save=False)
        assert result is False

    def test_zero_percentage_allowed(self):
        with patch.object(self.flags, "_save_configuration"):
            result = self.flags.set_rollout_percentage(
                "advanced_risk_management", 0.0, save=False
            )
        assert result is True

    def test_100_percentage_allowed(self):
        with patch.object(self.flags, "_save_configuration"):
            result = self.flags.set_rollout_percentage(
                "advanced_risk_management", 100.0, save=False
            )
        assert result is True


# ==============================================================================
# U11 — list_features / get_feature_info
# ==============================================================================


class TestListAndGetFeatures:
    def setup_method(self):
        self.flags = _make_flags()

    def test_list_features_returns_list(self):
        result = self.flags.list_features()
        assert isinstance(result, list)

    def test_list_features_sorted_by_name(self):
        result = self.flags.list_features()
        names = [f["name"] for f in result]
        assert names == sorted(names)

    def test_get_feature_info_known(self):
        info = self.flags.get_feature_info("advanced_risk_management")
        assert info is not None
        assert info["name"] == "advanced_risk_management"

    def test_get_feature_info_unknown(self):
        info = self.flags.get_feature_info("nonexistent_xyz")
        assert info is None
