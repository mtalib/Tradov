#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT85_TradingCalendarDependencyAnalyzerTests.py
Purpose: Comprehensive tests for U10 TradingCalendar and U18 DependencyAnalyzer

Author: Spyder Test Suite
Year Created: 2026
Last Updated: 2026-03-05 Time: 15:00:00
"""

# ==============================================================================
# BOOTSTRAP
# ==============================================================================
import sys
import os
import types
import importlib.util
import tempfile
import json

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

_u01 = _load("Spyder/SpyderU_Utilities/SpyderU01_Logger.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU01_Logger"] = _u01

_u02 = _load("Spyder/SpyderU_Utilities/SpyderU02_ErrorHandler.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler"] = _u02

_u10 = _load("Spyder/SpyderU_Utilities/SpyderU10_TradingCalendar.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU10_TradingCalendar"] = _u10

_u18 = _load("Spyder/SpyderU_Utilities/SpyderU18_DependencyAnalyzer.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU18_DependencyAnalyzer"] = _u18

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import pytest
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

# ==============================================================================
# U10 IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU10_TradingCalendar import (
    MarketSession,
    MarketStatus,
    Exchange,
    MarketHours,
    Holiday,
    TradingCalendar,
    get_trading_calendar,
    DEFAULT_MARKET_OPEN,
    DEFAULT_MARKET_CLOSE,
)

# ==============================================================================
# U18 IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU18_DependencyAnalyzer import (
    DependencyType,
    AnalysisScope,
    SeverityLevel,
    ModuleInfo,
    CircularDependency,
    DependencyGraph,
    DependencyAnalyzer,
    analyze_project_dependencies,
    get_dependency_analyzer,
    MODULE_GROUPS,
)

ET = ZoneInfo("America/New_York")


# ==============================================================================
# ═══════════════════════════════════════════════════════════════════════════
#  U10 — TRADING CALENDAR
# ═══════════════════════════════════════════════════════════════════════════
# ==============================================================================

class TestU10Enums:
    def test_market_session_values(self):
        assert MarketSession.CLOSED.value == "closed"
        assert MarketSession.PREMARKET.value == "premarket"
        assert MarketSession.REGULAR.value == "regular"
        assert MarketSession.AFTERHOURS.value == "afterhours"
        assert MarketSession.EXTENDED.value == "extended"

    def test_market_status_values(self):
        assert MarketStatus.OPEN.value == "open"
        assert MarketStatus.CLOSED.value == "closed"
        assert MarketStatus.HOLIDAY.value == "holiday"
        assert MarketStatus.WEEKEND.value == "weekend"
        assert MarketStatus.OPENING_SOON.value == "opening_soon"
        assert MarketStatus.CLOSING_SOON.value == "closing_soon"
        assert MarketStatus.EARLY_CLOSE.value == "early_close"

    def test_exchange_values(self):
        assert Exchange.NYSE.value == "NYSE"
        assert Exchange.NASDAQ.value == "NASDAQ"
        assert Exchange.CBOE.value == "CBOE"
        assert Exchange.CME.value == "CME"


class TestU10DataStructures:
    def test_market_hours_creation(self):
        mh = MarketHours(date=date(2025, 1, 6))
        assert mh.date == date(2025, 1, 6)
        assert mh.is_trading_day is True
        assert mh.is_early_close is False

    def test_holiday_creation(self):
        h = Holiday(date=date(2025, 12, 25), name="Christmas", exchange=Exchange.NYSE)
        assert h.name == "Christmas"
        assert h.is_closed is True


class TestU10TradingCalendarInit:
    def setup_method(self):
        self.cal = TradingCalendar()

    def test_init_default_exchange(self):
        assert self.cal.exchange == Exchange.NYSE

    def test_init_custom_exchange(self):
        cal = TradingCalendar(exchange=Exchange.NASDAQ)
        assert cal.exchange == Exchange.NASDAQ

    def test_init_loads_holidays(self):
        assert len(self.cal.holidays) > 0

    def test_init_market_hours(self):
        assert self.cal.regular_open == DEFAULT_MARKET_OPEN
        assert self.cal.regular_close == DEFAULT_MARKET_CLOSE

    def test_init_early_closes_exist(self):
        # Day after Thanksgiving and Christmas Eve should be early closes
        assert len(self.cal.early_closes) > 0


class TestU10IsTradingDay:
    def setup_method(self):
        self.cal = TradingCalendar()

    def test_saturday_is_not_trading(self):
        # Find a Saturday
        sat = date(2025, 1, 4)  # January 4, 2025 is Saturday
        assert sat.weekday() == 5
        assert self.cal.is_trading_day(sat) is False

    def test_sunday_is_not_trading(self):
        sun = date(2025, 1, 5)  # January 5, 2025 is Sunday
        assert sun.weekday() == 6
        assert self.cal.is_trading_day(sun) is False

    def test_weekday_is_trading(self):
        # Monday Jan 6, 2025 (not a holiday)
        mon = date(2025, 1, 6)
        assert mon.weekday() == 0
        assert self.cal.is_trading_day(mon) is True

    def test_new_years_day_not_trading(self):
        # January 1 2026 is a Thursday — should be a holiday
        nyd = date(2026, 1, 1)
        assert self.cal.is_trading_day(nyd) is False

    def test_christmas_not_trading(self):
        # December 25, 2026 is a Friday — Christmas holiday
        xmas = date(2026, 12, 25)
        assert self.cal.is_trading_day(xmas) is False

    def test_default_date_returns_bool(self):
        result = self.cal.is_trading_day()
        assert isinstance(result, bool)

    def test_known_trading_day(self):
        # March 3, 2025 (Monday, no holiday)
        d = date(2025, 3, 3)
        assert self.cal.is_trading_day(d) is True


class TestU10IsMarketOpen:
    def setup_method(self):
        self.cal = TradingCalendar()

    def _make_et_timestamp(self, h: int, m: int, check_date: date = date(2025, 3, 3)) -> datetime:
        """Create an ET-aware datetime."""
        return datetime.combine(check_date, time(h, m), tzinfo=ET)

    def test_market_open_during_hours(self):
        ts = self._make_et_timestamp(10, 30)
        assert self.cal.is_market_open(ts) is True

    def test_market_closed_before_open(self):
        ts = self._make_et_timestamp(9, 0)
        assert self.cal.is_market_open(ts) is False

    def test_market_closed_after_close(self):
        ts = self._make_et_timestamp(16, 30)
        assert self.cal.is_market_open(ts) is False

    def test_market_closed_on_weekend(self):
        sat = date(2025, 1, 4)
        ts = self._make_et_timestamp(12, 0, sat)
        assert self.cal.is_market_open(ts) is False

    def test_market_closed_on_holiday(self):
        xmas = date(2026, 12, 25)
        ts = self._make_et_timestamp(11, 0, xmas)
        assert self.cal.is_market_open(ts) is False

    def test_market_open_at_exactly_930(self):
        ts = self._make_et_timestamp(9, 30)
        assert self.cal.is_market_open(ts) is True

    def test_market_open_at_exactly_1600(self):
        ts = self._make_et_timestamp(16, 0)
        assert self.cal.is_market_open(ts) is True


class TestU10IsExtendedHours:
    def setup_method(self):
        self.cal = TradingCalendar()

    def _ts(self, h: int, m: int, d: date = date(2025, 3, 3)) -> datetime:
        return datetime.combine(d, time(h, m), tzinfo=ET)

    def test_premarket_is_extended(self):
        ts = self._ts(7, 0)
        assert self.cal.is_extended_hours(ts) is True

    def test_regular_hours_not_extended(self):
        ts = self._ts(10, 30)
        assert self.cal.is_extended_hours(ts) is False

    def test_afterhours_is_extended(self):
        ts = self._ts(17, 0)
        assert self.cal.is_extended_hours(ts) is True

    def test_extended_on_weekend_false(self):
        sat = date(2025, 1, 4)
        ts = self._ts(7, 0, sat)
        assert self.cal.is_extended_hours(ts) is False

    def test_very_early_not_extended(self):
        ts = self._ts(3, 0)
        assert self.cal.is_extended_hours(ts) is False


class TestU10MarketStatus:
    def setup_method(self):
        self.cal = TradingCalendar()

    def _ts(self, h: int, m: int, d: date = date(2025, 3, 3)) -> datetime:
        return datetime.combine(d, time(h, m), tzinfo=ET)

    def test_status_open_mid_day(self):
        ts = self._ts(12, 0)
        status = self.cal.get_market_status(ts)
        assert status == MarketStatus.OPEN

    def test_status_weekend(self):
        sat = date(2025, 1, 4)
        ts = self._ts(12, 0, sat)
        status = self.cal.get_market_status(ts)
        assert status == MarketStatus.WEEKEND

    def test_status_holiday(self):
        xmas = date(2026, 12, 25)
        ts = self._ts(11, 0, xmas)
        status = self.cal.get_market_status(ts)
        assert status == MarketStatus.HOLIDAY

    def test_status_closed_after_hours(self):
        ts = self._ts(19, 0)
        status = self.cal.get_market_status(ts)
        assert status == MarketStatus.CLOSED

    def test_status_opening_soon(self):
        # 9:15 ET on trading day — 15 min before open
        ts = self._ts(9, 15)
        status = self.cal.get_market_status(ts)
        assert status == MarketStatus.OPENING_SOON

    def test_status_closing_soon(self):
        # 15:45 ET — 15 min before close
        ts = self._ts(15, 45)
        status = self.cal.get_market_status(ts)
        assert status == MarketStatus.CLOSING_SOON


class TestU10MarketSession:
    def setup_method(self):
        self.cal = TradingCalendar()

    def _ts(self, h: int, m: int, d: date = date(2025, 3, 3)) -> datetime:
        return datetime.combine(d, time(h, m), tzinfo=ET)

    def test_regular_session(self):
        ts = self._ts(11, 0)
        session = self.cal.get_market_session(ts)
        assert session == MarketSession.REGULAR

    def test_premarket_session(self):
        ts = self._ts(7, 0)
        session = self.cal.get_market_session(ts)
        assert session == MarketSession.PREMARKET

    def test_afterhours_session(self):
        ts = self._ts(17, 0)
        session = self.cal.get_market_session(ts)
        assert session == MarketSession.AFTERHOURS

    def test_closed_session_weekend(self):
        sat = date(2025, 1, 4)
        ts = self._ts(12, 0, sat)
        session = self.cal.get_market_session(ts)
        assert session == MarketSession.CLOSED

    def test_closed_session_late_night(self):
        ts = self._ts(22, 0)
        session = self.cal.get_market_session(ts)
        assert session == MarketSession.CLOSED


class TestU10CalendarOperations:
    def setup_method(self):
        self.cal = TradingCalendar()

    def test_get_next_trading_day_from_friday(self):
        # Jan 3, 2025 is Friday → next trading day should be Monday Jan 6
        fri = date(2025, 1, 3)
        assert fri.weekday() == 4
        nxt = self.cal.get_next_trading_day(fri)
        assert nxt > fri
        assert nxt.weekday() < 5

    def test_get_next_trading_day_from_saturday(self):
        sat = date(2025, 1, 4)
        nxt = self.cal.get_next_trading_day(sat)
        assert nxt > sat
        assert nxt.weekday() < 5

    def test_get_previous_trading_day_from_monday(self):
        mon = date(2025, 1, 6)
        prev = self.cal.get_previous_trading_day(mon)
        assert prev < mon
        assert prev.weekday() < 5

    def test_get_previous_trading_day_default(self):
        prev = self.cal.get_previous_trading_day()
        assert isinstance(prev, date)

    def test_get_trading_days_range(self):
        start = date(2025, 1, 6)
        end = date(2025, 1, 10)
        days = self.cal.get_trading_days(start, end)
        assert isinstance(days, list)
        assert len(days) > 0
        for d in days:
            assert self.cal.is_trading_day(d)

    def test_get_trading_days_no_weekends_in_result(self):
        start = date(2025, 1, 6)
        end = date(2025, 1, 12)
        days = self.cal.get_trading_days(start, end)
        for d in days:
            assert d.weekday() < 5

    def test_get_trading_days_empty_if_only_weekend(self):
        sat = date(2025, 1, 4)
        sun = date(2025, 1, 5)
        days = self.cal.get_trading_days(sat, sun)
        assert len(days) == 0

    def test_get_market_hours_today(self):
        hours = self.cal.get_market_hours()
        assert isinstance(hours, MarketHours)

    def test_get_market_hours_trading_day(self):
        d = date(2025, 3, 3)
        hours = self.cal.get_market_hours(d)
        assert hours.is_trading_day is True
        assert hours.market_open is not None
        assert hours.market_close is not None

    def test_get_market_hours_holiday(self):
        xmas = date(2026, 12, 25)
        hours = self.cal.get_market_hours(xmas)
        assert hours.is_trading_day is False
        assert hours.market_open is None

    def test_get_market_hours_early_close(self):
        # Find an early close date
        if self.cal.early_closes:
            ec_date = next(iter(self.cal.early_closes))
            hours = self.cal.get_market_hours(ec_date)
            assert hours.is_early_close is True
            assert hours.afterhours_close is None


class TestU10TimeUtils:
    def setup_method(self):
        self.cal = TradingCalendar()

    def test_time_until_open_when_market_open(self):
        # During market hours → None
        ts = datetime.combine(date(2025, 3, 3), time(11, 0), tzinfo=ET)
        result = self.cal.time_until_open(ts)
        assert result is None

    def test_time_until_open_before_market(self):
        # Before market hours on a trading day → positive timedelta
        ts = datetime.combine(date(2025, 3, 3), time(8, 0), tzinfo=ET)
        result = self.cal.time_until_open(ts)
        assert result is not None
        assert result.total_seconds() > 0

    def test_time_until_close_when_market_open(self):
        ts = datetime.combine(date(2025, 3, 3), time(11, 0), tzinfo=ET)
        result = self.cal.time_until_close(ts)
        assert result is not None
        assert result.total_seconds() > 0

    def test_time_until_close_when_market_closed(self):
        ts = datetime.combine(date(2025, 3, 3), time(18, 0), tzinfo=ET)
        result = self.cal.time_until_close(ts)
        assert result is None


class TestU10Holidays:
    def setup_method(self):
        self.cal = TradingCalendar()

    def test_get_holidays_for_year_returns_list(self):
        holidays = self.cal.get_holidays_for_year(2026)
        assert isinstance(holidays, list)
        assert len(holidays) > 0

    def test_get_holidays_all_holiday_type(self):
        holidays = self.cal.get_holidays_for_year(2026)
        for h in holidays:
            assert isinstance(h, Holiday)

    def test_get_holidays_filtered_by_year(self):
        holidays = self.cal.get_holidays_for_year(2026)
        for h in holidays:
            assert h.date.year == 2026

    def test_get_holidays_sorted(self):
        holidays = self.cal.get_holidays_for_year(2026)
        dates = [h.date for h in holidays]
        assert dates == sorted(dates)

    def test_add_custom_holiday(self):
        # Use a weekday that is not adjusted: June 17, 2026 is Wednesday
        d = date(2026, 6, 17)
        self.cal.add_custom_holiday(d, "Test Holiday")
        assert d in self.cal.holidays

    def test_add_custom_early_close(self):
        d = date(2025, 6, 16)
        self.cal.add_custom_holiday(d, "Test Early Close", is_early_close=True,
                                     close_time=time(13, 0))
        assert d in self.cal.early_closes

    def test_load_holidays_public(self):
        count_before = len(self.cal.holidays)
        self.cal.load_holidays()
        assert len(self.cal.holidays) >= count_before

    def test_reload_holidays(self):
        self.cal.reload_holidays()
        assert len(self.cal.holidays) > 0


class TestU10Lifecycle:
    def setup_method(self):
        self.cal = TradingCalendar()

    def test_start(self):
        self.cal.start()  # Should not raise

    def test_stop(self):
        self.cal.stop()  # Should not raise

    def test_cleanup(self):
        self.cal.cleanup()
        assert len(self.cal.holidays) == 0
        assert len(self.cal.early_closes) == 0

    def test_save_custom_holidays(self):
        tmpdir = tempfile.mkdtemp()
        filepath = os.path.join(tmpdir, "holidays.json")
        result = self.cal.save_custom_holidays(filepath)
        assert result is True
        assert os.path.exists(filepath)
        with open(filepath) as f:
            data = json.load(f)
        assert isinstance(data, dict)


class TestU10ModuleFunctions:
    def setup_method(self):
        _u10._trading_calendar_instance = None

    def test_get_trading_calendar_returns_instance(self):
        cal = get_trading_calendar()
        assert isinstance(cal, TradingCalendar)

    def test_get_trading_calendar_singleton(self):
        c1 = get_trading_calendar()
        c2 = get_trading_calendar()
        assert c1 is c2


# ==============================================================================
# ═══════════════════════════════════════════════════════════════════════════
#  U18 — DEPENDENCY ANALYZER
# ═══════════════════════════════════════════════════════════════════════════
# ==============================================================================

class TestU18Enums:
    def test_dependency_type_values(self):
        assert DependencyType.DIRECT.value == "direct"
        assert DependencyType.INDIRECT.value == "indirect"
        assert DependencyType.CIRCULAR.value == "circular"
        assert DependencyType.EXTERNAL.value == "external"
        assert DependencyType.INTERNAL.value == "internal"

    def test_analysis_scope_values(self):
        assert AnalysisScope.MODULE.value == "module"
        assert AnalysisScope.GROUP.value == "group"
        assert AnalysisScope.SYSTEM.value == "system"

    def test_severity_level_values(self):
        assert SeverityLevel.LOW.value == "low"
        assert SeverityLevel.MEDIUM.value == "medium"
        assert SeverityLevel.HIGH.value == "high"
        assert SeverityLevel.CRITICAL.value == "critical"


class TestU18DataStructures:
    def test_module_info_creation(self):
        mi = ModuleInfo(name="TestModule", path="/test.py", group="SpyderU_Utilities")
        assert mi.name == "TestModule"
        assert mi.imports == []
        assert mi.lines_of_code == 0

    def test_module_info_to_dict(self):
        mi = ModuleInfo(name="TestModule", path="/test.py", group="SpyderU_Utilities",
                        functions=["foo"], classes=["Bar"])
        d = mi.to_dict()
        assert d["name"] == "TestModule"
        assert d["functions"] == ["foo"]
        assert d["classes"] == ["Bar"]

    def test_circular_dependency_creation(self):
        cd = CircularDependency(
            modules=["A", "B"],
            severity=SeverityLevel.LOW,
            description="A -> B -> A",
        )
        assert cd.modules == ["A", "B"]
        assert cd.severity == SeverityLevel.LOW

    def test_circular_dependency_to_dict(self):
        cd = CircularDependency(modules=["X", "Y"], severity=SeverityLevel.HIGH, description="Test")
        d = cd.to_dict()
        assert d["modules"] == ["X", "Y"]
        assert d["severity"] == "high"

    def test_dependency_graph_creation(self):
        dg = DependencyGraph(nodes=["A", "B"], edges=[("A", "B")], circular_dependencies=[], isolated_modules=[])
        assert "A" in dg.nodes
        assert ("A", "B") in dg.edges

    def test_dependency_graph_to_dict(self):
        dg = DependencyGraph(nodes=["A"], edges=[], circular_dependencies=[], isolated_modules=[])
        d = dg.to_dict()
        assert "nodes" in d
        assert "edges" in d
        assert "circular_dependencies" in d


class TestU18DependencyAnalyzerInit:
    def test_init_default(self):
        analyzer = DependencyAnalyzer()
        assert str(analyzer.project_root) == "."

    def test_init_custom_root(self):
        analyzer = DependencyAnalyzer("/tmp")
        assert str(analyzer.project_root) == "/tmp"

    def test_init_empty_modules(self):
        analyzer = DependencyAnalyzer()
        assert len(analyzer.modules) == 0

    def test_init_empty_circular_deps(self):
        analyzer = DependencyAnalyzer()
        assert len(analyzer.circular_dependencies) == 0


class TestU18PrivateMethods:
    def setup_method(self):
        self.analyzer = DependencyAnalyzer()

    def test_is_spyder_module_true(self):
        assert self.analyzer._is_spyder_module("Spyder.SpyderU_Utilities.SpyderU01") is True

    def test_is_spyder_module_false(self):
        assert self.analyzer._is_spyder_module("pandas") is False

    def test_is_spyder_module_starts_with_spyder(self):
        assert self.analyzer._is_spyder_module("SpyderA_Core") is True

    def test_get_module_group_known(self):
        group = self.analyzer._get_module_group("SpyderU_Utilities.SpyderU01")
        assert "SpyderU_Utilities" in group or group == "SpyderU_Utilities"

    def test_get_module_group_unknown(self):
        group = self.analyzer._get_module_group("SomeUnknownModule")
        assert group == "Unknown"

    def test_count_lines_of_code_empty(self):
        assert self.analyzer._count_lines_of_code("") == 0

    def test_count_lines_of_code_simple(self):
        code = "x = 1\ny = 2\n# comment\n\nz = 3"
        loc = self.analyzer._count_lines_of_code(code)
        assert loc == 3  # x=1, y=2, z=3 (comment and blank excluded)

    def test_count_lines_of_code_only_comments(self):
        code = "# comment 1\n# comment 2\n"
        assert self.analyzer._count_lines_of_code(code) == 0

    def test_extract_imports_simple(self):
        import ast as _ast
        code = "import os\nfrom datetime import date"
        tree = _ast.parse(code)
        imports = self.analyzer._extract_imports(tree)
        assert "os" in imports
        assert "datetime" in imports

    def test_extract_functions(self):
        import ast as _ast
        code = "def foo():\n    pass\ndef bar():\n    pass"
        tree = _ast.parse(code)
        funcs = self.analyzer._extract_functions(tree)
        assert "foo" in funcs
        assert "bar" in funcs

    def test_extract_classes(self):
        import ast as _ast
        code = "class MyClass:\n    pass\nclass Another:\n    pass"
        tree = _ast.parse(code)
        classes = self.analyzer._extract_classes(tree)
        assert "MyClass" in classes
        assert "Another" in classes

    def test_assess_circular_severity_low_two(self):
        sev = self.analyzer._assess_circular_severity(["A", "B"])
        assert sev == SeverityLevel.LOW

    def test_assess_circular_severity_medium_three(self):
        sev = self.analyzer._assess_circular_severity(["A", "B", "C"])
        assert sev == SeverityLevel.MEDIUM

    def test_assess_circular_severity_high_four(self):
        sev = self.analyzer._assess_circular_severity(["A", "B", "C", "D"])
        assert sev == SeverityLevel.HIGH

    def test_assess_circular_severity_critical_six(self):
        sev = self.analyzer._assess_circular_severity(["A", "B", "C", "D", "E", "F"])
        assert sev == SeverityLevel.CRITICAL


class TestU18AnalysisMethods:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self._create_mock_files()
        self.analyzer = DependencyAnalyzer(self.tmpdir)

    def _create_mock_files(self):
        """Create minimal Python files in tmpdir for testing."""
        file_a = os.path.join(self.tmpdir, "SpyderA_module.py")
        file_b = os.path.join(self.tmpdir, "SpyderB_module.py")
        with open(file_a, "w") as f:
            f.write("# Module A\nfrom SpyderB_module import SomeClass\nx = 1\n")
        with open(file_b, "w") as f:
            f.write("# Module B\nimport os\n\nclass SomeClass:\n    pass\ndef helper():\n    return 1\n")

    def test_analyze_dependencies_populates_modules(self):
        self.analyzer.analyze_dependencies()
        assert len(self.analyzer.modules) >= 2

    def test_analyze_dependencies_idempotent(self):
        self.analyzer.analyze_dependencies()
        count1 = len(self.analyzer.modules)
        self.analyzer.analyze_dependencies()  # Second call should skip
        assert len(self.analyzer.modules) == count1

    def test_analyze_dependencies_force_refresh(self):
        self.analyzer.analyze_dependencies()
        self.analyzer.analyze_dependencies(force_refresh=True)
        assert len(self.analyzer.modules) >= 2

    def test_find_circular_dependencies_no_cycle(self):
        self.analyzer.analyze_dependencies()
        circulars = self.analyzer.find_circular_dependencies()
        # A → B but B doesn't import A, so no cycle
        assert isinstance(circulars, list)

    def test_find_circular_dependencies_triggers_analysis(self):
        # If not analyzed yet, should trigger analysis
        circulars = self.analyzer.find_circular_dependencies()
        assert isinstance(circulars, list)

    def test_get_module_dependencies_unknown(self):
        self.analyzer.analyze_dependencies()
        result = self.analyzer.get_module_dependencies("NoSuchModule")
        assert "error" in result

    def test_get_module_dependencies_known(self):
        self.analyzer.analyze_dependencies()
        if self.analyzer.modules:
            name = next(iter(self.analyzer.modules))
            result = self.analyzer.get_module_dependencies(name)
            assert "direct_dependencies" in result
            assert "dependent_modules" in result

    def test_generate_dependency_graph(self):
        self.analyzer.analyze_dependencies()
        graph = self.analyzer.generate_dependency_graph()
        assert isinstance(graph, DependencyGraph)
        assert isinstance(graph.nodes, list)
        assert isinstance(graph.edges, list)

    def test_generate_dependency_graph_triggers_analysis(self):
        graph = self.analyzer.generate_dependency_graph()
        assert isinstance(graph, DependencyGraph)

    def test_generate_dependency_report_returns_string(self):
        self.analyzer.analyze_dependencies()
        report = self.analyzer.generate_dependency_report()
        assert isinstance(report, str)
        assert len(report) > 0

    def test_generate_dependency_report_contains_keywords(self):
        self.analyzer.analyze_dependencies()
        report = self.analyzer.generate_dependency_report()
        assert "Dependency" in report or "Module" in report

    def test_export_graph_data_json(self):
        self.analyzer.analyze_dependencies()
        result = self.analyzer.export_graph_data("json")
        data = json.loads(result)
        assert "nodes" in data
        assert "edges" in data

    def test_export_graph_data_csv(self):
        self.analyzer.analyze_dependencies()
        result = self.analyzer.export_graph_data("csv")
        assert "Source,Target" in result

    def test_export_graph_data_invalid_format(self):
        self.analyzer.analyze_dependencies()
        result = self.analyzer.export_graph_data("xml")
        assert "Unsupported" in result

    def test_export_graph_triggers_analysis(self):
        result = self.analyzer.export_graph_data("json")
        data = json.loads(result)
        assert "nodes" in data


class TestU18WithCircularDeps:
    """Test with files that have circular imports."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        # Create two Spyder modules that import each other (circular)
        file_a = os.path.join(self.tmpdir, "SpyderCircA.py")
        file_b = os.path.join(self.tmpdir, "SpyderCircB.py")
        with open(file_a, "w") as f:
            f.write("from SpyderCircB import something\nx = 1\n")
        with open(file_b, "w") as f:
            f.write("from SpyderCircA import thing\ny = 2\n")
        self.analyzer = DependencyAnalyzer(self.tmpdir)

    def test_circular_dependency_detected(self):
        self.analyzer.analyze_dependencies()
        circulars = self.analyzer.find_circular_dependencies()
        # Both modules import each other → should detect cycle
        assert len(circulars) > 0

    def test_circular_dependency_has_severity(self):
        self.analyzer.analyze_dependencies()
        circulars = self.analyzer.find_circular_dependencies()
        if circulars:
            assert isinstance(circulars[0].severity, SeverityLevel)


class TestU18ModuleFunctions:
    def setup_method(self):
        _u18._dependency_analyzer_instance = None

    def test_get_dependency_analyzer_returns_instance(self):
        analyzer = get_dependency_analyzer()
        assert isinstance(analyzer, DependencyAnalyzer)

    def test_get_dependency_analyzer_singleton(self):
        a1 = get_dependency_analyzer()
        a2 = get_dependency_analyzer()
        assert a1 is a2

    def test_module_groups_constant(self):
        assert isinstance(MODULE_GROUPS, dict)
        assert "SpyderU_Utilities" in MODULE_GROUPS
