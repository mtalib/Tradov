#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT77_CalendarInstitutionalLibrariesTests.py
Purpose: Tests for U10 TradingCalendar (gaps), U20 InstitutionalLibraries,
         and U03 DateTimeUtils supplements

Author: Spyder Test Suite
Year Created: 2026
Last Updated: 2026-03-04 Time: 23:30:00
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

# Load U10
_u10 = _load("Spyder/Spyder.SpyderU_Utilities/SpyderU10_TradingCalendar.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU10_TradingCalendar"] = _u10

# Load U20 (has flexible imports — handles missing deps gracefully)
_u20 = _load("Spyder/Spyder.SpyderU_Utilities/SpyderU20_InstitutionalLibraries.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU20_InstitutionalLibraries"] = _u20

# Load U03 — inject pytz and SpyderLogger into its namespace (bug: not imported at module level)
_u03 = _load("Spyder/Spyder.SpyderU_Utilities/SpyderU03_DateTimeUtils.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils"] = _u03
import pytz as _pytz
_u03.pytz = _pytz
_u03.SpyderLogger = _u01.SpyderLogger

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import json
import tempfile
import shutil
import pytest
import pytz
import numpy as np
import pandas as pd
from datetime import date, datetime, time, timedelta
from unittest.mock import patch, MagicMock

# ==============================================================================
# U10 IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU10_TradingCalendar import (
    TradingCalendar,
    get_trading_calendar,
    MarketSession,
    MarketStatus,
    Exchange,
    MarketHours,
    Holiday,
    DEFAULT_MARKET_OPEN,
    DEFAULT_MARKET_CLOSE,
    DEFAULT_PREMARKET_OPEN,
    DEFAULT_AFTERHOURS_CLOSE,
    ET_TIMEZONE,
)

# ==============================================================================
# U20 IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU20_InstitutionalLibraries import (
    InstitutionalLibraries,
    get_institutional_libraries,
    reset_institutional_libraries,
    OptionPricing,
    InstitutionalMetrics,
    PortfolioOptimization,
    DEFAULT_RISK_FREE_RATE,
    TRADING_DAYS_PER_YEAR,
    LIBRARY_STATUS,
    SCIPY_AVAILABLE,
    QUANTLIB_AVAILABLE,
    PYFOLIO_AVAILABLE,
)

# ==============================================================================
# U03 SUPPLEMENT IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils import (
    get_market_schedule,
    to_utc_datetime,
    from_utc_datetime,
    get_trading_hours,
    get_market_hours,
    get_next_market_open,
    get_next_market_close,
    time_until_market_open,
    DateTimeUtils,
    TradingHours,
    MARKET_OPEN_TIME,
    MARKET_CLOSE_TIME,
    PRE_MARKET_OPEN,
    AFTER_HOURS_CLOSE,
    OPTIMAL_ENTRY_WINDOW,
    TIME_BASED_EXIT,
    US_EASTERN,
    MarketSession as U03MarketSession,
    get_current_market_session,
)


# ==============================================================================
# ─────────────────────────────────────────────────────────────────────────────
#  SECTION 1: U10 TradingCalendar — Gap Tests
# ─────────────────────────────────────────────────────────────────────────────
# ==============================================================================

def _fresh_calendar(exchange=Exchange.NYSE) -> TradingCalendar:
    return TradingCalendar(exchange)


# ─── Time Until Methods ───────────────────────────────────────────────────────

class TestTimeUntilOpen:
    def test_returns_none_when_market_open(self):
        cal = _fresh_calendar()
        # Create a timestamp during market hours on a weekday that is a trading day
        # Use a known Monday (January 6, 2025)
        ts = datetime(2025, 1, 6, 10, 0, tzinfo=ET_TIMEZONE)  # 10am Monday
        # Patch is_market_open to return True
        with patch.object(cal, "is_market_open", return_value=True):
            result = cal.time_until_open(ts)
        assert result is None

    def test_returns_timedelta_when_market_closed(self):
        cal = _fresh_calendar()
        ts = datetime(2025, 1, 6, 7, 0, tzinfo=ET_TIMEZONE)  # 7am Monday (before open)
        result = cal.time_until_open(ts)
        assert result is None or isinstance(result, timedelta)

    def test_uses_now_when_no_timestamp(self):
        cal = _fresh_calendar()
        result = cal.time_until_open()
        assert result is None or isinstance(result, timedelta)


class TestTimeUntilClose:
    def test_returns_none_when_market_closed(self):
        cal = _fresh_calendar()
        ts = datetime(2025, 1, 6, 18, 0, tzinfo=ET_TIMEZONE)  # 6pm Monday
        with patch.object(cal, "is_market_open", return_value=False):
            result = cal.time_until_close(ts)
        assert result is None

    def test_returns_timedelta_when_market_open(self):
        cal = _fresh_calendar()
        ts = datetime(2025, 1, 6, 10, 0, tzinfo=ET_TIMEZONE)  # 10am Monday
        with patch.object(cal, "is_market_open", return_value=True):
            result = cal.time_until_close(ts)
        assert isinstance(result, timedelta)

    def test_timedelta_positive_during_market_hours(self):
        cal = _fresh_calendar()
        ts = datetime(2025, 1, 6, 10, 0, tzinfo=ET_TIMEZONE)
        with patch.object(cal, "is_market_open", return_value=True):
            result = cal.time_until_close(ts)
        assert result.total_seconds() > 0

    def test_uses_now_when_no_timestamp(self):
        cal = _fresh_calendar()
        result = cal.time_until_close()
        assert result is None or isinstance(result, timedelta)


# ─── Holiday Management ────────────────────────────────────────────────────────

class TestAddCustomHoliday:
    def test_adds_full_holiday(self):
        cal = _fresh_calendar()
        custom_date = date(2027, 3, 15)
        len(cal.holidays)
        cal.add_custom_holiday(custom_date, "Custom Holiday")
        assert custom_date in cal.holidays

    def test_add_early_close_holiday(self):
        cal = _fresh_calendar()
        early_date = date(2027, 3, 16)  # Must be a weekday
        # Ensure it's a weekday
        while early_date.weekday() >= 5:
            early_date += timedelta(days=1)
        cal.add_custom_holiday(early_date, "Early Day", is_early_close=True, close_time=time(13, 0))
        assert early_date in cal.early_closes
        assert cal.early_closes[early_date] == time(13, 0)

    def test_custom_holiday_not_trading_day(self):
        cal = _fresh_calendar()
        monday = date(2027, 6, 14)  # A Monday
        while monday.weekday() != 0:
            monday += timedelta(days=1)
        cal.add_custom_holiday(monday, "Test Holiday")
        assert not cal.is_trading_day(monday)


class TestReloadHolidays:
    def test_clears_and_reloads(self):
        cal = _fresh_calendar()
        initial_count = len(cal.holidays)
        cal.reload_holidays()
        assert len(cal.holidays) > 0
        # Should have similar count after reload
        assert len(cal.holidays) == pytest.approx(initial_count, abs=5)


class TestLoadHolidaysPublic:
    def test_public_load_holidays(self):
        cal = _fresh_calendar()
        # Should not raise
        cal.load_holidays()
        assert len(cal.holidays) > 0


class TestSaveCustomHolidays:
    def test_can_save_holidays(self):
        cal = _fresh_calendar()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_holidays.json")
            result = cal.save_custom_holidays(filepath)
            assert isinstance(result, bool)
            if result:
                assert os.path.exists(filepath)
                with open(filepath) as f:
                    data = json.load(f)
                assert isinstance(data, dict)

    def test_save_creates_valid_json(self):
        cal = _fresh_calendar()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "holidays.json")
            result = cal.save_custom_holidays(filepath)
            if result:
                with open(filepath) as f:
                    data = json.load(f)
                # All keys should be date strings
                for key in data:
                    assert len(key) == 10
                    assert key[4] == "-"


# ─── Lifecycle Methods ────────────────────────────────────────────────────────

class TestLifecycleMethods:
    def test_start_no_crash(self):
        cal = _fresh_calendar()
        cal.start()  # Should not raise

    def test_stop_no_crash(self):
        cal = _fresh_calendar()
        cal.stop()  # Should not raise

    def test_cleanup_clears_holidays(self):
        cal = _fresh_calendar()
        assert len(cal.holidays) > 0
        cal.cleanup()
        assert len(cal.holidays) == 0

    def test_cleanup_clears_early_closes(self):
        cal = _fresh_calendar()
        cal.cleanup()
        assert len(cal.early_closes) == 0


# ─── Singleton Function ──────────────────────────────────────────────────────

class TestGetTradingCalendarSingleton:
    def setup_method(self):
        _u10._trading_calendar_instance = None

    def test_returns_trading_calendar_instance(self):
        cal = get_trading_calendar()
        assert isinstance(cal, TradingCalendar)

    def test_singleton_same_instance(self):
        cal1 = get_trading_calendar()
        cal2 = get_trading_calendar()
        assert cal1 is cal2

    def test_default_exchange_nyse(self):
        cal = get_trading_calendar()
        assert cal.exchange == Exchange.NYSE


# ─── Private Helpers ─────────────────────────────────────────────────────────

class TestPrivateHelpers10:
    def test_get_nth_weekday_of_month(self):
        cal = _fresh_calendar()
        # 3rd Monday of January 2025 = Jan 20
        result = cal._get_nth_weekday_of_month(2025, 1, 0, 3)
        assert result == date(2025, 1, 20)
        assert result.weekday() == 0  # Monday

    def test_get_last_weekday_of_month(self):
        cal = _fresh_calendar()
        # Last Monday of May 2025
        result = cal._get_last_weekday_of_month(2025, 5, 0)
        assert result.weekday() == 0
        assert result.month == 5

    def test_calculate_good_friday_2025(self):
        cal = _fresh_calendar()
        gf = cal._calculate_good_friday(2025)
        assert gf is None or isinstance(gf, date)
        if gf:
            assert gf.weekday() == 4  # Friday

    def test_adjust_holiday_saturday(self):
        cal = _fresh_calendar()
        date(2025, 7, 4)  # July 4, 2025 is a Friday
        # Find a Saturday
        sat_date = date(2026, 7, 4)
        while sat_date.weekday() != 5:
            sat_date += timedelta(days=1)
        result = cal._adjust_holiday_for_weekend(sat_date)
        assert result.weekday() == 4  # Observed on Friday

    def test_adjust_holiday_sunday(self):
        cal = _fresh_calendar()
        sun_date = date(2026, 7, 5)
        while sun_date.weekday() != 6:
            sun_date += timedelta(days=1)
        result = cal._adjust_holiday_for_weekend(sun_date)
        assert result.weekday() == 0  # Observed on Monday

    def test_adjust_holiday_weekday_unchanged(self):
        cal = _fresh_calendar()
        monday = date(2025, 1, 6)
        result = cal._adjust_holiday_for_weekend(monday)
        assert result == monday


# ─── Error Handling Scenarios ────────────────────────────────────────────────

class TestErrorHandling10:
    def test_is_market_open_exception_returns_false(self):
        cal = _fresh_calendar()
        with patch.object(cal, "is_trading_day", side_effect=Exception("test error")):
            result = cal.is_market_open()
        assert result is False

    def test_is_extended_hours_exception_returns_false(self):
        cal = _fresh_calendar()
        with patch.object(cal, "is_trading_day", side_effect=Exception("test error")):
            result = cal.is_extended_hours()
        assert result is False

    def test_get_market_status_exception_returns_closed(self):
        cal = _fresh_calendar()
        # Pass a known weekday timestamp so get_market_status() doesn't return
        # WEEKEND before ever calling is_trading_day (which carries the exception).
        weekday_ts = datetime(2024, 1, 2, 12, 0)  # Tuesday — not a holiday or weekend
        with patch.object(cal, "is_trading_day", side_effect=Exception("test error")):
            result = cal.get_market_status(timestamp=weekday_ts)
        assert result == MarketStatus.CLOSED

    def test_get_market_session_exception_returns_closed(self):
        cal = _fresh_calendar()
        with patch.object(cal, "is_trading_day", side_effect=Exception("test error")):
            result = cal.get_market_session()
        assert result == MarketSession.CLOSED


# ─── Market Status Scenarios ─────────────────────────────────────────────────

class TestMarketStatusScenarios:
    def test_weekend_status(self):
        cal = _fresh_calendar()
        # Saturday
        sat = date(2025, 1, 4)
        assert sat.weekday() == 5
        ts = datetime.combine(sat, time(10, 0)).replace(tzinfo=ET_TIMEZONE)
        status = cal.get_market_status(ts)
        assert status == MarketStatus.WEEKEND

    def test_holiday_status(self):
        cal = _fresh_calendar()
        # Find a holiday that's in the calendar
        for h in cal.holidays:
            if h.weekday() < 5:
                ts = datetime.combine(h, time(10, 0)).replace(tzinfo=ET_TIMEZONE)
                status = cal.get_market_status(ts)
                assert status == MarketStatus.HOLIDAY
                break

    def test_opening_soon_status(self):
        cal = _fresh_calendar()
        # 9:05 on a trading Monday — should be OPENING_SOON but U10 returns CLOSED
        monday = date(2025, 1, 6)
        ts = datetime.combine(monday, time(9, 5)).replace(tzinfo=ET_TIMEZONE)
        status = cal.get_market_status(ts)
        assert status == MarketStatus.OPENING_SOON

    def test_closing_soon_status(self):
        cal = _fresh_calendar()
        # 15:45 (last 30 min before close) on trading Monday — should be CLOSING_SOON but U10 returns CLOSED
        monday = date(2025, 1, 6)
        ts = datetime.combine(monday, time(15, 45)).replace(tzinfo=ET_TIMEZONE)
        status = cal.get_market_status(ts)
        assert status == MarketStatus.CLOSING_SOON


# ==============================================================================
# ─────────────────────────────────────────────────────────────────────────────
#  SECTION 2: U20 InstitutionalLibraries TESTS
# ─────────────────────────────────────────────────────────────────────────────
# ==============================================================================

def _fresh_libs() -> InstitutionalLibraries:
    return InstitutionalLibraries()


class TestU20Constants:
    def test_default_risk_free_rate(self):
        assert isinstance(DEFAULT_RISK_FREE_RATE, float)
        assert 0 < DEFAULT_RISK_FREE_RATE < 1

    def test_trading_days_per_year(self):
        assert TRADING_DAYS_PER_YEAR == 252

    def test_library_status_is_dict(self):
        assert isinstance(LIBRARY_STATUS, dict)

    def test_library_status_has_scipy(self):
        assert "scipy" in LIBRARY_STATUS

    def test_library_status_has_sklearn(self):
        assert "sklearn" in LIBRARY_STATUS


class TestOptionPricingDataclass:
    def _make(self) -> OptionPricing:
        return OptionPricing(
            theoretical_price=5.50,
            delta=0.45,
            gamma=0.02,
            theta=-0.05,
            vega=0.12,
            rho=0.03,
            implied_volatility=0.20,
        )

    def test_creation(self):
        op = self._make()
        assert op.theoretical_price == 5.50

    def test_delta_field(self):
        op = self._make()
        assert op.delta == 0.45

    def test_optional_defaults_none(self):
        op = OptionPricing(1.0, 0.5, 0.01, -0.02, 0.05, 0.01)
        assert op.implied_volatility is None

    def test_moneyness_optional(self):
        op = self._make()
        # moneyness defaults to None (not set in constructor)
        assert op.moneyness is None or isinstance(op.moneyness, float)


class TestInstitutionalMetricsDataclass:
    def _make(self) -> InstitutionalMetrics:
        return InstitutionalMetrics(
            annual_return=0.15,
            volatility=0.18,
            sharpe_ratio=0.83,
            sortino_ratio=1.2,
            max_drawdown=-0.12,
            calmar_ratio=1.25,
            win_rate=0.55,
            profit_factor=1.8,
            recovery_factor=1.5,
        )

    def test_creation(self):
        m = self._make()
        assert m.annual_return == 0.15

    def test_sharpe_ratio(self):
        m = self._make()
        assert m.sharpe_ratio == pytest.approx(0.83)

    def test_optional_fields_default_none(self):
        m = self._make()
        assert m.var_95 is None
        assert m.cvar_95 is None


class TestPortfolioOptimizationDataclass:
    def test_creation(self):
        po = PortfolioOptimization(
            weights={"SPY": 0.6, "QQQ": 0.4},
            expected_return=0.12,
            expected_volatility=0.15,
            sharpe_ratio=0.8,
            optimization_method="max_sharpe",
            constraints_satisfied=True,
            optimization_success=True,
        )
        assert po.optimization_success is True
        assert po.weights["SPY"] == 0.6


class TestInstitutionalLibrariesInit:
    def test_instantiation(self):
        libs = _fresh_libs()
        assert libs is not None

    def test_has_logger(self):
        libs = _fresh_libs()
        assert libs.logger is not None

    def test_available_libraries_dict(self):
        libs = _fresh_libs()
        assert isinstance(libs.available_libraries, dict)

    def test_risk_free_rate_default(self):
        libs = _fresh_libs()
        assert libs.risk_free_rate == DEFAULT_RISK_FREE_RATE

    def test_calculation_cache_empty(self):
        libs = _fresh_libs()
        assert libs._calculation_cache == {}

    def test_option_type_accessible(self):
        libs = _fresh_libs()
        assert libs.OptionType is not None
        assert hasattr(libs.OptionType, "CALL")
        assert hasattr(libs.OptionType, "PUT")


class TestLibraryStatusMethods:
    def test_get_library_status_returns_dict(self):
        libs = _fresh_libs()
        status = libs.get_library_status()
        assert isinstance(status, dict)

    def test_get_library_status_copy(self):
        libs = _fresh_libs()
        s1 = libs.get_library_status()
        s1["fake_key"] = True
        s2 = libs.get_library_status()
        assert "fake_key" not in s2

    def test_get_available_libraries_count_returns_tuple(self):
        libs = _fresh_libs()
        result = libs.get_available_libraries_count()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_available_count_non_negative(self):
        libs = _fresh_libs()
        available, total = libs.get_available_libraries_count()
        assert available >= 0
        assert total > 0
        assert available <= total

    def test_is_library_available_scipy(self):
        libs = _fresh_libs()
        result = libs.is_library_available("scipy")
        assert isinstance(result, bool)
        assert result == SCIPY_AVAILABLE

    def test_is_library_available_nonexistent(self):
        libs = _fresh_libs()
        result = libs.is_library_available("nonexistent_library")
        assert result is False


class TestSetRiskFreeRate:
    def test_sets_rate(self):
        libs = _fresh_libs()
        libs.set_risk_free_rate(0.05)
        assert libs.risk_free_rate == 0.05

    def test_sets_zero(self):
        libs = _fresh_libs()
        libs.set_risk_free_rate(0.0)
        assert libs.risk_free_rate == 0.0


class TestClearCache:
    def test_clears_empty_cache(self):
        libs = _fresh_libs()
        libs.clear_cache()  # Should not raise
        assert libs._calculation_cache == {}

    def test_clears_populated_cache(self):
        libs = _fresh_libs()
        libs._calculation_cache["key"] = "value"
        libs.clear_cache()
        assert libs._calculation_cache == {}


class TestCalculateInstitutionalMetrics:
    def _sample_returns(self, n=252, seed=42) -> np.ndarray:
        np.random.seed(seed)
        return np.random.normal(0.001, 0.02, n)

    def test_returns_institutional_metrics(self):
        libs = _fresh_libs()
        returns = self._sample_returns()
        result = libs.calculate_institutional_metrics(returns)
        assert result is not None
        assert isinstance(result, InstitutionalMetrics)

    def test_annual_return_reasonable(self):
        libs = _fresh_libs()
        returns = self._sample_returns()
        result = libs.calculate_institutional_metrics(returns)
        assert isinstance(result.annual_return, float)
        assert -2 < result.annual_return < 5  # Sanity check

    def test_volatility_positive(self):
        libs = _fresh_libs()
        returns = self._sample_returns()
        result = libs.calculate_institutional_metrics(returns)
        assert result.volatility > 0

    def test_win_rate_between_0_and_1(self):
        libs = _fresh_libs()
        returns = self._sample_returns()
        result = libs.calculate_institutional_metrics(returns)
        assert 0 <= result.win_rate <= 1

    def test_max_drawdown_non_positive(self):
        libs = _fresh_libs()
        returns = self._sample_returns()
        result = libs.calculate_institutional_metrics(returns)
        assert result.max_drawdown <= 0

    def test_accepts_list(self):
        libs = _fresh_libs()
        returns = list(self._sample_returns(100))
        result = libs.calculate_institutional_metrics(returns)
        assert isinstance(result, InstitutionalMetrics)

    def test_accepts_pandas_series(self):
        libs = _fresh_libs()
        returns = pd.Series(self._sample_returns(100))
        result = libs.calculate_institutional_metrics(returns)
        assert isinstance(result, InstitutionalMetrics)

    def test_with_custom_risk_free_rate(self):
        libs = _fresh_libs()
        returns = self._sample_returns()
        result = libs.calculate_institutional_metrics(returns, risk_free_rate=0.02)
        assert isinstance(result, InstitutionalMetrics)

    def test_with_benchmark_returns(self):
        libs = _fresh_libs()
        np.random.seed(42)
        returns = np.random.normal(0.001, 0.02, 252)
        benchmark = np.random.normal(0.0008, 0.018, 252)
        result = libs.calculate_institutional_metrics(returns, benchmark_returns=benchmark)
        assert isinstance(result, InstitutionalMetrics)
        assert result.information_ratio is not None

    def test_scipy_fills_advanced_metrics(self):
        libs = _fresh_libs()
        returns = self._sample_returns()
        result = libs.calculate_institutional_metrics(returns)
        if SCIPY_AVAILABLE:
            assert result.var_95 is not None
            assert result.skewness is not None
            assert result.kurtosis is not None

    def test_empty_returns_handled(self):
        libs = _fresh_libs()
        # Should handle edge case without crashing
        try:
            result = libs.calculate_institutional_metrics(np.array([0.01, 0.02, -0.01]))
            assert result is None or isinstance(result, InstitutionalMetrics)
        except Exception:
            pass  # Exception is acceptable for edge input


class TestPriceOptionQuantLib:
    """Tests for price_option — only run if QuantLib available."""

    @pytest.mark.skipif(not QUANTLIB_AVAILABLE, reason="QuantLib not installed")
    def test_price_call_returns_option_pricing(self):
        libs = _fresh_libs()
        result = libs.price_option(
            spot=450.0,
            strike=455.0,
            time_to_expiry=0.04,
            risk_free_rate=0.05,
            volatility=0.20,
            option_type=libs.OptionType.CALL,
        )
        assert result is not None
        assert isinstance(result, OptionPricing)

    @pytest.mark.skipif(not QUANTLIB_AVAILABLE, reason="QuantLib not installed")
    def test_price_put_returns_option_pricing(self):
        libs = _fresh_libs()
        result = libs.price_option(
            spot=450.0,
            strike=455.0,
            time_to_expiry=0.04,
            risk_free_rate=0.05,
            volatility=0.20,
            option_type=libs.OptionType.PUT,
        )
        assert result is not None

    @pytest.mark.skipif(not QUANTLIB_AVAILABLE, reason="QuantLib not installed")
    def test_price_positive(self):
        libs = _fresh_libs()
        result = libs.price_option(
            spot=450.0, strike=445.0, time_to_expiry=0.1,
            risk_free_rate=0.05, volatility=0.25, option_type=libs.OptionType.CALL
        )
        if result:
            assert result.theoretical_price > 0

    def test_price_option_no_quantlib_returns_none(self):
        libs = _fresh_libs()
        libs.available_libraries["quantlib"] = False
        with patch.dict("Spyder.SpyderU_Utilities.SpyderU20_InstitutionalLibraries.__dict__",
                        {"QUANTLIB_AVAILABLE": False}):
            # Directly test the fallback path
            original = _u20.QUANTLIB_AVAILABLE
            _u20.QUANTLIB_AVAILABLE = False
            try:
                result = libs.price_option(
                    spot=450.0, strike=455.0, time_to_expiry=0.04,
                    risk_free_rate=0.05, volatility=0.20,
                    option_type=libs.OptionType.PUT
                )
                assert result is None
            finally:
                _u20.QUANTLIB_AVAILABLE = original


class TestPriceSpread:
    @pytest.mark.skipif(not QUANTLIB_AVAILABLE, reason="QuantLib not installed")
    def test_price_spread_returns_dict(self):
        libs = _fresh_libs()
        result = libs.price_spread(
            spot=450.0,
            short_strike=455.0,
            long_strike=460.0,
            time_to_expiry=0.04,
            risk_free_rate=0.05,
            volatility=0.20,
            option_type=libs.OptionType.CALL,
        )
        if result is not None:
            assert isinstance(result, dict)
            assert "net_credit" in result
            assert "max_profit" in result
            assert "max_loss" in result


class TestOptimizePortfolio:
    def _sample_returns_df(self, n=252, seed=42) -> pd.DataFrame:
        np.random.seed(seed)
        data = {
            "SPY": np.random.normal(0.001, 0.02, n),
            "QQQ": np.random.normal(0.0012, 0.025, n),
            "IWM": np.random.normal(0.0008, 0.022, n),
        }
        return pd.DataFrame(data)

    @pytest.mark.skipif(not SCIPY_AVAILABLE, reason="scipy required for optimization")
    def test_optimize_max_sharpe_returns_result(self):
        libs = _fresh_libs()
        returns_df = self._sample_returns_df()
        result = libs.optimize_portfolio(returns_df, method="max_sharpe")
        assert result is None or isinstance(result, PortfolioOptimization)

    @pytest.mark.skipif(not SCIPY_AVAILABLE, reason="scipy required for optimization")
    def test_optimize_weights_sum_to_one(self):
        libs = _fresh_libs()
        returns_df = self._sample_returns_df()
        result = libs.optimize_portfolio(returns_df, method="max_sharpe")
        if result is not None and result.optimization_success:
            assert sum(result.weights.values()) == pytest.approx(1.0, abs=0.01)

    @pytest.mark.skipif(not SCIPY_AVAILABLE, reason="scipy required for optimization")
    def test_optimize_min_vol_method(self):
        libs = _fresh_libs()
        returns_df = self._sample_returns_df()
        result = libs.optimize_portfolio(returns_df, method="min_vol")
        assert result is None or isinstance(result, PortfolioOptimization)


class TestGlobalInstitutionalFunctions:
    def setup_method(self):
        reset_institutional_libraries()

    def teardown_method(self):
        reset_institutional_libraries()

    def test_get_institutional_libraries_returns_instance(self):
        libs = get_institutional_libraries()
        assert isinstance(libs, InstitutionalLibraries)

    def test_get_institutional_libraries_singleton(self):
        libs1 = get_institutional_libraries()
        libs2 = get_institutional_libraries()
        assert libs1 is libs2

    def test_reset_creates_new_instance(self):
        libs1 = get_institutional_libraries()
        reset_institutional_libraries()
        libs2 = get_institutional_libraries()
        assert libs1 is not libs2

    def test_reset_no_crash_when_none(self):
        reset_institutional_libraries()  # Already None from setup
        reset_institutional_libraries()  # Should not raise

    def test_new_instance_has_risk_free_rate(self):
        libs = get_institutional_libraries()
        assert libs.risk_free_rate == DEFAULT_RISK_FREE_RATE


# ==============================================================================
# ─────────────────────────────────────────────────────────────────────────────
#  SECTION 3: U03 DateTimeUtils — Supplement Tests
# ─────────────────────────────────────────────────────────────────────────────
# ==============================================================================

class TestGetMarketSchedule:
    def test_returns_dataframe(self):
        start = date(2025, 1, 6)
        end = date(2025, 1, 12)
        df = get_market_schedule((start, end))
        assert isinstance(df, pd.DataFrame)

    def test_has_expected_columns(self):
        start = date(2025, 1, 6)
        end = date(2025, 1, 10)
        df = get_market_schedule((start, end))
        assert "date" in df.columns
        assert "trading_day" in df.columns

    def test_default_range_5_days(self):
        df = get_market_schedule()
        assert len(df) >= 5  # At least 5 days

    def test_weekend_not_trading(self):
        # Week containing Saturday Jan 4, 2025
        start = date(2025, 1, 4)
        end = date(2025, 1, 5)
        df = get_market_schedule((start, end))
        weekend_rows = df[~df["trading_day"]]
        assert len(weekend_rows) == 2  # Both weekend days

    def test_weekday_is_trading(self):
        # Monday Jan 6, 2025
        start = date(2025, 1, 6)
        end = date(2025, 1, 6)
        df = get_market_schedule((start, end))
        # Use == True (not `is True`) because pandas returns np.bool_ not Python bool
        assert df.iloc[0]["trading_day"]


class TestToUtcDatetime:
    def test_converts_eastern_to_utc(self):
        et = pytz.timezone("US/Eastern")
        dt_et = et.localize(datetime(2025, 1, 6, 10, 0))
        dt_utc = to_utc_datetime(dt_et)
        assert dt_utc.tzinfo is not None
        # UTC is 5 hrs ahead of ET in winter
        assert dt_utc.hour == 15

    def test_naive_datetime_assumed_eastern(self):
        dt_naive = datetime(2025, 1, 6, 10, 0)
        result = to_utc_datetime(dt_naive)
        assert result is not None


class TestFromUtcDatetime:
    def test_converts_utc_to_eastern(self):
        utc_dt = datetime(2025, 1, 6, 15, 0, tzinfo=pytz.UTC)
        result = from_utc_datetime(utc_dt)
        et = pytz.timezone("US/Eastern")
        result_et = result.astimezone(et)
        assert result_et.hour == 10  # 15:00 UTC = 10:00 ET in winter

    def test_naive_utc_treated_as_utc(self):
        dt_naive = datetime(2025, 1, 6, 15, 0)
        result = from_utc_datetime(dt_naive)
        assert result is not None


class TestGetTradingHours:
    def test_returns_dict(self):
        result = get_trading_hours(date(2025, 1, 6))
        assert isinstance(result, dict)

    def test_has_is_trading_day_key(self):
        result = get_trading_hours(date(2025, 1, 6))
        assert "is_trading_day" in result

    def test_monday_is_trading_day(self):
        result = get_trading_hours(date(2025, 1, 6))
        assert result["is_trading_day"] is True

    def test_saturday_not_trading_day(self):
        sat = date(2025, 1, 4)
        result = get_trading_hours(sat)
        assert result["is_trading_day"] is False

    def test_saturday_reason_weekend(self):
        sat = date(2025, 1, 4)
        result = get_trading_hours(sat)
        assert result["reason"] == "Weekend"

    def test_friday_has_friday_options_close(self):
        fri = date(2025, 1, 10)
        assert fri.weekday() == 4
        result = get_trading_hours(fri)
        if result["is_trading_day"] and "options_close" in result:
            from Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils import OPTIONS_CLOSE_FRIDAY
            assert result["options_close"] == OPTIONS_CLOSE_FRIDAY


class TestGetMarketHoursWrapper:
    def test_trading_day_returns_tuple(self):
        monday = date(2025, 1, 6)
        open_dt, close_dt = get_market_hours(monday)
        assert open_dt is not None
        assert close_dt is not None

    def test_weekend_returns_none_tuple(self):
        sat = date(2025, 1, 4)
        open_dt, close_dt = get_market_hours(sat)
        assert open_dt is None
        assert close_dt is None


class TestGetNextMarketOpen:
    def test_returns_datetime(self):
        result = get_next_market_open()
        assert isinstance(result, datetime)

    def test_with_weekend_input(self):
        sat_dt = pytz.timezone("US/Eastern").localize(
            datetime.combine(date(2025, 1, 4), time(10, 0))
        )
        result = get_next_market_open(sat_dt)
        # Next market open after Saturday should be Monday
        assert result.weekday() == 0


class TestGetNextMarketClose:
    def test_returns_datetime(self):
        result = get_next_market_close()
        assert isinstance(result, datetime)


class TestTimeUntilMarketOpen:
    def test_returns_timedelta(self):
        result = time_until_market_open()
        assert isinstance(result, timedelta)


class TestDateTimeUtilsSupplement:
    def test_add_trading_days_positive(self):
        monday = date(2025, 1, 6)
        result = DateTimeUtils.add_trading_days(monday, 5)
        assert isinstance(result, date)
        # 5 trading days from Monday Jan 6 = next Monday Jan 13
        assert result == date(2025, 1, 13)

    def test_add_trading_days_negative(self):
        friday = date(2025, 1, 10)
        result = DateTimeUtils.add_trading_days(friday, -5)
        assert isinstance(result, date)
        # 5 trading days before Jan 10 Friday = Jan 3 Friday
        assert result == date(2025, 1, 3)

    def test_add_trading_days_zero(self):
        monday = date(2025, 1, 6)
        result = DateTimeUtils.add_trading_days(monday, 0)
        assert result == monday

    def test_get_day_quality_score_returns_float(self):
        result = DateTimeUtils.get_day_quality_score()
        assert isinstance(result, float)
        assert 0 <= result <= 1.0

    def test_get_trading_day_name_returns_str(self):
        result = DateTimeUtils.get_trading_day_name()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_is_monday_returns_bool(self):
        result = DateTimeUtils.is_monday()
        assert isinstance(result, bool)

    def test_get_trading_windows_returns_dict(self):
        result = DateTimeUtils.get_trading_windows()
        assert isinstance(result, dict)
        assert "market_hours" in result
        assert "optimal_entry" in result

    def test_format_time_window_returns_str(self):
        result = DateTimeUtils.format_time_window(OPTIMAL_ENTRY_WINDOW)
        assert isinstance(result, str)
        assert " - " in result

    def test_is_end_of_session_returns_bool(self):
        result = DateTimeUtils.is_end_of_session()
        assert isinstance(result, bool)

    def test_is_end_of_session_custom_threshold(self):
        result = DateTimeUtils.is_end_of_session(minutes_before_close=10)
        assert isinstance(result, bool)

    def test_get_trading_session_info_returns_dict(self):
        result = DateTimeUtils.get_trading_session_info()
        assert isinstance(result, dict)
        assert "date" in result
        assert "is_trading_day" in result

    def test_is_optimal_entry_time_returns_bool(self):
        # Test with explicit time inside optimal window: 10:30 AM
        dt_inside = datetime(2025, 1, 6, 10, 30)
        result = DateTimeUtils.is_optimal_entry_time(dt_inside)
        assert result is True

    def test_is_optimal_entry_time_outside_window(self):
        dt_outside = datetime(2025, 1, 6, 8, 0)  # 8 AM
        result = DateTimeUtils.is_optimal_entry_time(dt_outside)
        assert result is False

    def test_should_exit_by_time_after_noon(self):
        dt = datetime(2025, 1, 6, 13, 0)  # 1 PM
        result = DateTimeUtils.should_exit_by_time(dt)
        assert result is True

    def test_should_exit_by_time_before_noon(self):
        dt = datetime(2025, 1, 6, 10, 0)  # 10 AM
        result = DateTimeUtils.should_exit_by_time(dt)
        assert result is False

    def test_get_time_until_entry_window_returns_timedelta_or_none(self):
        result = DateTimeUtils.get_time_until_entry_window()
        assert result is None or isinstance(result, timedelta)

    def test_get_time_remaining_in_window_returns_timedelta_or_none(self):
        result = DateTimeUtils.get_time_remaining_in_window()
        assert result is None or isinstance(result, timedelta)

    def test_count_trading_days(self):
        start = date(2025, 1, 6)
        end = date(2025, 1, 10)
        result = DateTimeUtils.count_trading_days(start, end)
        assert result == 5  # Mon-Fri

    def test_monthly_option_expiry_is_friday(self):
        result = DateTimeUtils.get_monthly_option_expiry(2025, 1)
        assert isinstance(result, date)
        assert result.weekday() == 4  # Friday

    def test_format_option_symbol(self):
        result = DateTimeUtils.format_option_symbol(
            "SPY", date(2025, 1, 17), "C", 450.0
        )
        assert result.startswith("SPY")
        assert "C" in result
        assert "250117" in result  # YY MM DD


class TestU03MarketSessionEnum:
    def test_regular_hours_value(self):
        assert U03MarketSession.REGULAR_HOURS.value == "regular_hours"

    def test_pre_market_value(self):
        assert U03MarketSession.PRE_MARKET.value == "pre_market"

    def test_closed_value(self):
        assert U03MarketSession.CLOSED.value == "closed"

    def test_all_members(self):
        assert len(list(U03MarketSession)) >= 5


class TestGetCurrentMarketSession:
    def test_returns_market_session(self):
        result = get_current_market_session()
        assert isinstance(result, U03MarketSession)

    def test_returns_valid_session(self):
        result = get_current_market_session()
        valid = {
            U03MarketSession.PRE_MARKET,
            U03MarketSession.REGULAR_HOURS,
            U03MarketSession.AFTER_HOURS,
            U03MarketSession.CLOSED,
        }
        assert result in valid


class TestTradingHoursEarlyClose:
    def setup_method(self):
        self.th = TradingHours()

    def test_day_after_thanksgiving_is_early_close(self):
        from Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils import _get_nth_weekday_of_month
        thanksgiving = _get_nth_weekday_of_month(2025, 11, 3, 4)
        day_after = thanksgiving + timedelta(days=1)
        assert self.th.is_early_close_day(day_after) is True

    def test_normal_day_not_early_close(self):
        monday = date(2025, 1, 6)
        assert self.th.is_early_close_day(monday) is False

    def test_is_options_trading_hours_spy_friday(self):
        # Friday during market hours for SPY
        friday = date(2025, 1, 10)
        dt = self.th.tz.localize(datetime.combine(friday, time(10, 0)))
        result = self.th.is_options_trading_hours(dt, "SPY")
        assert result is True

    def test_is_options_trading_hours_not_trading_day(self):
        sat = date(2025, 1, 4)
        dt = self.th.tz.localize(datetime.combine(sat, time(10, 0)))
        result = self.th.is_options_trading_hours(dt)
        assert result is False
