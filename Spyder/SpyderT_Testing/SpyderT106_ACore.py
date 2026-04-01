#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Test: T106 — SpyderA_Core (A01-A08)
Purpose: Maximize coverage for all 7 A-Core modules:
    A01_Main, A02_TradingEngine, A03_Configuration, A04_Scheduler,
    A05_EventManager, A06_MasterController, A08_FSeriesOrchestrator
"""

# ==============================================================================
# BOOTSTRAP — must run before any Spyder imports
# ==============================================================================
import os
import sys
import types
import datetime
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _ensure_pkg(name):
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)


_ensure_pkg("Spyder")
_ensure_pkg("SpyderU_Utilities")
_ensure_pkg("Spyder.SpyderU_Utilities")
_ensure_pkg("Spyder.SpyderA_Core")
_ensure_pkg("SpyderA_Core")

# Logger stub
_logger_mod = types.ModuleType("Spyder.SpyderU_Utilities.SpyderU01_Logger")


class _FakeSpyderLogger:
    @staticmethod
    def get_logger(name):
        return MagicMock()

    @staticmethod
    def initialize_logging():
        pass


_logger_mod.SpyderLogger = _FakeSpyderLogger
_logger_mod.get_logger = MagicMock(return_value=MagicMock())
sys.modules["Spyder.SpyderU_Utilities.SpyderU01_Logger"] = _logger_mod
sys.modules["SpyderU_Utilities.SpyderU01_Logger"] = _logger_mod

# ErrorHandler stub
_err_mod = types.ModuleType("Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler")
_err_mod.SpyderErrorHandler = MagicMock
sys.modules["Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler"] = _err_mod
sys.modules["SpyderU_Utilities.SpyderU02_ErrorHandler"] = _err_mod


# ==============================================================================
# IMPORT MODULES UNDER TEST
# ==============================================================================

# --- A01 Main ---
import Spyder.SpyderA_Core.SpyderA01_Main as _a01
from Spyder.SpyderA_Core.SpyderA01_Main import SpyderConfig

# --- A02 TradingEngine ---
import Spyder.SpyderA_Core.SpyderA02_TradingEngine as _a02
from Spyder.SpyderA_Core.SpyderA02_TradingEngine import (
    EngineState,
    StrategyState,
    OrderState,
    CircuitBreakerState,
    StrategyInfo,
    OrderInfo,
    MAX_STRATEGIES,
    MAX_ORDERS_PER_MINUTE,
    MAX_POSITION_AGE_HOURS,
    MAX_ORDER_RETRIES,
    HEALTH_CHECK_INTERVAL,
)

# Register A02 in SpyderA_Core so A04 can import it
sys.modules["Spyder.SpyderA_Core.SpyderA02_TradingEngine"] = _a02

# --- A05 EventManager (import before A04 so it's cached) ---
import Spyder.SpyderA_Core.SpyderA05_EventManager as _a05
from Spyder.SpyderA_Core.SpyderA05_EventManager import (
    EventType,
    EventPriority,
    HandlerType,
    Event,
    HandlerInfo,
    EventMetrics,
    EventFilter,
    EventManager,
    EventBus,
    get_event_manager,
    reset_event_manager,
    DEFAULT_QUEUE_SIZE,
    PRIORITY_QUEUE_SIZE,
    MAX_WORKER_THREADS,
)

# Ensure A05 is cached under both paths so A04 import works
sys.modules["Spyder.SpyderA_Core.SpyderA05_EventManager"] = _a05
sys.modules["SpyderA_Core.SpyderA05_EventManager"] = _a05

# --- A03 Configuration ---
import Spyder.SpyderA_Core.SpyderA03_Configuration as _a03
from Spyder.SpyderA_Core.SpyderA03_Configuration import (
    ConfigSource,
    ConfigFormat,
    ValidationLevel,
    ConfigValue,
    ConfigChange,
    ConfigSchema,
    ConfigManager,
    DEFAULT_CONFIG_DIR,
    DEFAULT_ENV_PREFIX,
    CONFIG_SCHEMA_VERSION,
    SENSITIVE_KEY_PATTERNS,
    SUPPORTED_FORMATS,
)

# --- A04 Scheduler ---
import Spyder.SpyderA_Core.SpyderA04_Scheduler as _a04
from Spyder.SpyderA_Core.SpyderA04_Scheduler import (
    ScheduleType,
    TaskStatus,
    MarketSession,
    TradingDayType,
    ScheduledTask,
    TaskExecution,
    MarketHours,
    TradingWindow,
    MarketCalendar,
    EASTERN_TZ,
    DEFAULT_MARKET_OPEN,
    DEFAULT_MARKET_CLOSE,
    DEFAULT_PREMARKET_OPEN,
    DEFAULT_AFTERHOURS_CLOSE,
)

# --- A06 MasterController ---
import Spyder.SpyderA_Core.SpyderA06_MasterController as _a06
from Spyder.SpyderA_Core.SpyderA06_MasterController import (
    SystemStatus,
    ModuleStatus as A06ModuleStatus,
    MarketState,
    TradingMode,
    ModuleInfo as A06ModuleInfo,
    SystemConfig,
    HealthMetrics,
    StartupSequence,
    MasterController,
)

# --- A08 FSeriesOrchestrator ---
import Spyder.SpyderA_Core.SpyderA08_FSeriesOrchestrator as _a08
from Spyder.SpyderA_Core.SpyderA08_FSeriesOrchestrator import (
    ModulePriority,
    ResourceType,
    ModuleStatus as A08ModuleStatus,
    ExecutionMode,
    ResourceAllocation,
    ModuleTask,
    ModuleMetrics,
    SystemResources,
    OrchestrationConfig,
    FSeriesOrchestrator,
)

# ==============================================================================
# HELPERS
# ==============================================================================

def _make_order_action():
    """Get OrderAction from A02 module."""
    return _a02.OrderAction


def _reset_a05_singleton():
    reset_event_manager()


# ==============================================================================
# ============================================================
# A01 — SpyderConfig
# ============================================================
# ==============================================================================

class TestSpyderConfig:
    def test_creates_instance(self):
        cfg = SpyderConfig()
        assert isinstance(cfg, SpyderConfig)

    def test_default_app_name(self):
        cfg = SpyderConfig()
        assert cfg.app_name == "SPYDER"

    def test_default_version(self):
        cfg = SpyderConfig()
        assert cfg.version == "1.0"

    def test_debug_mode_is_false_by_default(self):
        cfg = SpyderConfig()
        assert cfg.debug_mode is False

    def test_gui_enabled_by_default(self):
        cfg = SpyderConfig()
        assert cfg.enable_gui is True

    def test_window_dimensions(self):
        cfg = SpyderConfig()
        assert cfg.window_width > 0
        assert cfg.window_height > 0

    def test_log_to_file(self):
        cfg = SpyderConfig()
        assert isinstance(cfg.log_to_file, bool)

    def test_simulation_mode_false(self):
        cfg = SpyderConfig()
        assert cfg.simulation_mode is False

    def test_headless_mode_false(self):
        cfg = SpyderConfig()
        assert cfg.headless_mode is False

    def test_connection_timeout_positive(self):
        cfg = SpyderConfig()
        assert cfg.connection_timeout > 0

    def test_attributes_mutable(self):
        cfg = SpyderConfig()
        cfg.debug_mode = True
        assert cfg.debug_mode is True


# ==============================================================================
# A02 — Enums and Constants
# ==============================================================================

class TestA02Constants:
    def test_max_strategies(self):
        assert MAX_STRATEGIES == 20

    def test_max_orders_per_minute(self):
        assert MAX_ORDERS_PER_MINUTE == 100

    def test_max_position_age_hours(self):
        assert MAX_POSITION_AGE_HOURS == 24

    def test_max_order_retries(self):
        assert MAX_ORDER_RETRIES == 3

    def test_health_check_interval(self):
        assert HEALTH_CHECK_INTERVAL == 60


class TestEngineStateEnum:
    def test_initializing(self):
        assert EngineState.INITIALIZING is not None

    def test_ready(self):
        assert EngineState.READY is not None

    def test_running(self):
        assert EngineState.RUNNING is not None

    def test_paused(self):
        assert EngineState.PAUSED is not None

    def test_stopped(self):
        assert EngineState.STOPPED is not None

    def test_error(self):
        assert EngineState.ERROR is not None

    def test_seven_states(self):
        assert len(EngineState) == 7


class TestStrategyStateEnum:
    def test_registered(self):
        assert StrategyState.REGISTERED is not None

    def test_active(self):
        assert StrategyState.ACTIVE is not None

    def test_stopped(self):
        assert StrategyState.STOPPED is not None

    def test_seven_states(self):
        assert len(StrategyState) == 7


class TestOrderStateEnum:
    def test_pending(self):
        assert OrderState.PENDING is not None

    def test_filled(self):
        assert OrderState.FILLED is not None

    def test_cancelled(self):
        assert OrderState.CANCELLED is not None

    def test_seven_states(self):
        assert len(OrderState) == 7


class TestCircuitBreakerStateEnum:
    def test_normal(self):
        assert CircuitBreakerState.NORMAL is not None

    def test_warning(self):
        assert CircuitBreakerState.WARNING is not None

    def test_triggered(self):
        assert CircuitBreakerState.TRIGGERED is not None

    def test_recovering(self):
        assert CircuitBreakerState.RECOVERING is not None

    def test_four_states(self):
        assert len(CircuitBreakerState) == 4


class TestStrategyInfoDataclass:
    def test_create(self):
        si = StrategyInfo(
            strategy_id="s1",
            name="TestStrategy",
            class_instance=MagicMock(),
        )
        assert isinstance(si, StrategyInfo)

    def test_default_state(self):
        si = StrategyInfo(
            strategy_id="s1", name="Test", class_instance=MagicMock()
        )
        assert si.state == StrategyState.REGISTERED

    def test_default_signal_count(self):
        si = StrategyInfo(
            strategy_id="s1", name="Test", class_instance=MagicMock()
        )
        assert si.signal_count == 0

    def test_default_pnl(self):
        si = StrategyInfo(
            strategy_id="s1", name="Test", class_instance=MagicMock()
        )
        assert si.pnl == 0.0

    def test_error_count_default(self):
        si = StrategyInfo(
            strategy_id="s1", name="Test", class_instance=MagicMock()
        )
        assert si.error_count == 0


# ==============================================================================
# A03 — Configuration
# ==============================================================================

class TestA03Constants:
    def test_env_prefix(self):
        assert DEFAULT_ENV_PREFIX == "SPYDER_"

    def test_schema_version(self):
        assert CONFIG_SCHEMA_VERSION == "2.0"

    def test_sensitive_patterns_list(self):
        assert isinstance(SENSITIVE_KEY_PATTERNS, list)
        assert len(SENSITIVE_KEY_PATTERNS) > 0

    def test_supported_formats(self):
        assert ".yaml" in SUPPORTED_FORMATS
        assert ".json" in SUPPORTED_FORMATS
        assert ".toml" in SUPPORTED_FORMATS

    def test_default_config_dir_is_path(self):
        assert isinstance(DEFAULT_CONFIG_DIR, Path)


class TestConfigSourceEnum:
    def test_default(self):
        assert ConfigSource.DEFAULT is not None

    def test_file(self):
        assert ConfigSource.FILE is not None

    def test_environment(self):
        assert ConfigSource.ENVIRONMENT is not None

    def test_runtime(self):
        assert ConfigSource.RUNTIME is not None

    def test_remote(self):
        assert ConfigSource.REMOTE is not None

    def test_five_sources(self):
        assert len(ConfigSource) == 5


class TestConfigFormatEnum:
    def test_json(self):
        assert ConfigFormat.JSON.value == "json"

    def test_yaml(self):
        assert ConfigFormat.YAML.value == "yaml"

    def test_toml(self):
        assert ConfigFormat.TOML.value == "toml"

    def test_ini(self):
        assert ConfigFormat.INI.value == "ini"

    def test_env(self):
        assert ConfigFormat.ENV.value == "env"


class TestValidationLevelEnum:
    def test_none(self):
        assert ValidationLevel.NONE is not None

    def test_basic(self):
        assert ValidationLevel.BASIC is not None

    def test_strict(self):
        assert ValidationLevel.STRICT is not None

    def test_custom(self):
        assert ValidationLevel.CUSTOM is not None

    def test_four_levels(self):
        assert len(ValidationLevel) == 4


class TestConfigValueDataclass:
    def test_create(self):
        cv = ConfigValue(
            key="test.key",
            value=42,
            source=ConfigSource.DEFAULT,
        )
        assert isinstance(cv, ConfigValue)

    def test_fields(self):
        cv = ConfigValue(
            key="broker.port",
            value=4002,
            source=ConfigSource.FILE,
        )
        assert cv.key == "broker.port"
        assert cv.value == 4002
        assert cv.source == ConfigSource.FILE

    def test_encrypted_default_false(self):
        cv = ConfigValue(key="k", value="v", source=ConfigSource.DEFAULT)
        assert cv.encrypted is False

    def test_timestamp_is_datetime(self):
        cv = ConfigValue(key="k", value="v", source=ConfigSource.DEFAULT)
        assert isinstance(cv.timestamp, datetime.datetime)


class TestConfigChangeDataclass:
    def test_create(self):
        cc = ConfigChange(
            timestamp=datetime.datetime.now(),
            key="risk.max_loss",
            old_value=500,
            new_value=600,
            source="runtime",
        )
        assert isinstance(cc, ConfigChange)

    def test_fields(self):
        now = datetime.datetime.now()
        cc = ConfigChange(
            timestamp=now,
            key="broker.port",
            old_value=4001,
            new_value=4002,
            source="file",
        )
        assert cc.key == "broker.port"
        assert cc.old_value == 4001
        assert cc.new_value == 4002
        assert cc.source == "file"


class TestConfigSchemaDataclass:
    def test_create(self):
        cs = ConfigSchema(
            version="2.0",
            properties={"port": {"type": "integer"}},
            required=["port"],
        )
        assert isinstance(cs, ConfigSchema)

    def test_additional_properties_default_false(self):
        cs = ConfigSchema(version="1.0", properties={}, required=[])
        assert cs.additional_properties is False


class TestConfigManagerInit:
    def test_creates_with_temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = ConfigManager(
                config_path=Path(tmpdir) / "config.yaml",
                auto_reload=False,
            )
            assert isinstance(cm, ConfigManager)

    def test_environment_stored(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = ConfigManager(
                config_path=Path(tmpdir) / "config.yaml",
                environment="testing",
                auto_reload=False,
            )
            assert cm.environment == "testing"

    def test_config_data_has_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = ConfigManager(
                config_path=Path(tmpdir) / "config.yaml",
                auto_reload=False,
            )
            assert isinstance(cm.config_data, dict)
            assert len(cm.config_data) > 0

    def test_application_defaults_loaded(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = ConfigManager(
                config_path=Path(tmpdir) / "config.yaml",
                auto_reload=False,
            )
            assert "application" in cm.config_data

    def test_no_file_observer_when_auto_reload_false(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = ConfigManager(
                config_path=Path(tmpdir) / "config.yaml",
                auto_reload=False,
            )
            # File observer should not be started
            assert cm.file_observer is None or not getattr(cm.file_observer, '_thread', None)

    def test_change_history_empty_on_init(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = ConfigManager(
                config_path=Path(tmpdir) / "config.yaml",
                auto_reload=False,
            )
            assert isinstance(cm.change_history, list)

    def test_get_compatible_method(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = ConfigManager(
                config_path=Path(tmpdir) / "config.yaml",
                auto_reload=False,
            )
            # ConfigManager inherits a get() method for compatibility
            # Check basic config_data access works
            assert "application" in cm.config_data


# ==============================================================================
# A04 — Scheduler
# ==============================================================================

class TestA04Constants:
    def test_eastern_tz(self):
        import pytz
        assert pytz.timezone("US/Eastern") == EASTERN_TZ

    def test_market_open(self):
        import datetime as dt
        assert dt.time(9, 30) == DEFAULT_MARKET_OPEN

    def test_market_close(self):
        import datetime as dt
        assert dt.time(16, 0) == DEFAULT_MARKET_CLOSE

    def test_premarket_open(self):
        import datetime as dt
        assert dt.time(4, 0) == DEFAULT_PREMARKET_OPEN

    def test_afterhours_close(self):
        import datetime as dt
        assert dt.time(20, 0) == DEFAULT_AFTERHOURS_CLOSE


class TestScheduleTypeEnum:
    def test_cron(self):
        assert ScheduleType.CRON is not None

    def test_interval(self):
        assert ScheduleType.INTERVAL is not None

    def test_date(self):
        assert ScheduleType.DATE is not None

    def test_market_based(self):
        assert ScheduleType.MARKET_BASED is not None

    def test_four_types(self):
        assert len(ScheduleType) == 4


class TestTaskStatusEnum:
    def test_pending(self):
        assert TaskStatus.PENDING.value == "pending"

    def test_running(self):
        assert TaskStatus.RUNNING.value == "running"

    def test_success(self):
        assert TaskStatus.SUCCESS.value == "success"

    def test_error(self):
        assert TaskStatus.ERROR.value == "error"

    def test_cancelled(self):
        assert TaskStatus.CANCELLED.value == "cancelled"

    def test_six_statuses(self):
        assert len(TaskStatus) == 6


class TestMarketSessionEnum:
    def test_premarket(self):
        assert MarketSession.PREMARKET.value == "premarket"

    def test_regular(self):
        assert MarketSession.REGULAR.value == "regular"

    def test_afterhours(self):
        assert MarketSession.AFTERHOURS.value == "afterhours"

    def test_closed(self):
        assert MarketSession.CLOSED.value == "closed"


class TestTradingDayTypeEnum:
    def test_regular(self):
        assert TradingDayType.REGULAR.value == "regular"

    def test_early_close(self):
        assert TradingDayType.EARLY_CLOSE.value == "early_close"

    def test_holiday(self):
        assert TradingDayType.HOLIDAY.value == "holiday"

    def test_weekend(self):
        assert TradingDayType.WEEKEND.value == "weekend"


class TestMarketHoursDataclass:
    def test_create_minimal(self):
        mh = MarketHours(date=datetime.date.today())
        assert isinstance(mh, MarketHours)

    def test_is_trading_day_default_true(self):
        mh = MarketHours(date=datetime.date.today())
        assert mh.is_trading_day is True

    def test_day_type_default_regular(self):
        mh = MarketHours(date=datetime.date.today())
        assert mh.day_type == TradingDayType.REGULAR

    def test_fields(self):
        d = datetime.date(2025, 1, 2)
        mh = MarketHours(date=d, is_trading_day=False, day_type=TradingDayType.HOLIDAY)
        assert mh.date == d
        assert mh.is_trading_day is False
        assert mh.day_type == TradingDayType.HOLIDAY


class TestTradingWindowDataclass:
    def test_create(self):
        tw = TradingWindow(
            name="Morning",
            start_time=datetime.time(9, 30),
            end_time=datetime.time(11, 30),
        )
        assert isinstance(tw, TradingWindow)

    def test_default_enabled(self):
        tw = TradingWindow(
            name="W",
            start_time=datetime.time(9, 30),
            end_time=datetime.time(11, 30),
        )
        assert tw.enabled is True

    def test_default_weekdays(self):
        tw = TradingWindow(
            name="W",
            start_time=datetime.time(9, 30),
            end_time=datetime.time(11, 30),
        )
        assert len(tw.days_of_week) == 5  # Mon-Fri


class TestScheduledTaskDataclass:
    def test_create(self):
        st = ScheduledTask(
            task_id="t1",
            name="TestTask",
            func=lambda: None,
            schedule_type=ScheduleType.INTERVAL,
            schedule_params={"minutes": 5},
        )
        assert isinstance(st, ScheduledTask)

    def test_enabled_default_true(self):
        st = ScheduledTask(
            task_id="t1",
            name="T",
            func=lambda: None,
            schedule_type=ScheduleType.CRON,
            schedule_params={},
        )
        assert st.enabled is True

    def test_run_count_default_zero(self):
        st = ScheduledTask(
            task_id="t1",
            name="T",
            func=lambda: None,
            schedule_type=ScheduleType.CRON,
            schedule_params={},
        )
        assert st.run_count == 0


class TestMarketCalendarInit:
    def test_creates_instance(self):
        mc = MarketCalendar()
        assert isinstance(mc, MarketCalendar)

    def test_has_nyse_calendar(self):
        mc = MarketCalendar()
        assert mc.nyse_calendar is not None

    def test_weekend_not_trading(self):
        mc = MarketCalendar()
        # Find a Saturday
        today = datetime.date.today()
        days_until_saturday = (5 - today.weekday()) % 7
        saturday = today + datetime.timedelta(days=days_until_saturday)
        hours = mc.get_market_hours(saturday)
        assert hours.is_trading_day is False
        assert hours.day_type == TradingDayType.WEEKEND

    def test_sunday_not_trading(self):
        mc = MarketCalendar()
        today = datetime.date.today()
        days_until_sunday = (6 - today.weekday()) % 7
        sunday = today + datetime.timedelta(days=days_until_sunday)
        hours = mc.get_market_hours(sunday)
        assert hours.is_trading_day is False

    def test_cache_works(self):
        mc = MarketCalendar()
        d = datetime.date(2025, 7, 4)  # Independence Day
        h1 = mc.get_market_hours(d)
        h2 = mc.get_market_hours(d)
        assert h1 is h2  # Same object from cache

    def test_us_holidays_has_entries(self):
        mc = MarketCalendar()
        assert len(mc.us_holidays) > 0

    def test_is_market_open_on_weekend(self):
        mc = MarketCalendar()
        import pytz
        # Create a datetime for a Saturday
        today = datetime.date.today()
        days_until_saturday = (5 - today.weekday()) % 7
        saturday = today + datetime.timedelta(days=days_until_saturday)
        dt = datetime.datetime.combine(saturday, datetime.time(12, 0))
        dt = pytz.timezone("US/Eastern").localize(dt)
        assert mc.is_market_open(dt) is False


# ==============================================================================
# A05 — EventManager
# ==============================================================================

class TestA05Constants:
    def test_default_queue_size(self):
        assert DEFAULT_QUEUE_SIZE == 10000

    def test_priority_queue_size(self):
        assert PRIORITY_QUEUE_SIZE == 1000

    def test_max_worker_threads(self):
        assert MAX_WORKER_THREADS == 10


class TestEventTypeEnum:
    def test_system(self):
        assert EventType.SYSTEM.value == "system"

    def test_system_start(self):
        assert EventType.SYSTEM_START.value == "system_start"

    def test_order_placed(self):
        assert EventType.ORDER_PLACED.value == "order_placed"

    def test_risk_limit_breach(self):
        assert EventType.RISK_LIMIT_BREACH.value == "risk_limit_breach"

    def test_strategy_signal(self):
        assert EventType.STRATEGY_SIGNAL.value == "strategy_signal"

    def test_shutdown(self):
        assert EventType.SHUTDOWN.value == "shutdown"

    def test_has_many_types(self):
        assert len(EventType) > 20


class TestEventPriorityEnum:
    def test_low_value(self):
        assert EventPriority.LOW.value == 1

    def test_normal_value(self):
        assert EventPriority.NORMAL.value == 2

    def test_high_value(self):
        assert EventPriority.HIGH.value == 3

    def test_critical_value(self):
        assert EventPriority.CRITICAL.value == 4

    def test_emergency_value(self):
        assert EventPriority.EMERGENCY.value == 5

    def test_ordering(self):
        assert EventPriority.LOW.value < EventPriority.NORMAL.value
        assert EventPriority.NORMAL.value < EventPriority.HIGH.value
        assert EventPriority.HIGH.value < EventPriority.CRITICAL.value


class TestHandlerTypeEnum:
    def test_sync(self):
        assert HandlerType.SYNC is not None

    def test_async(self):
        assert HandlerType.ASYNC is not None

    def test_threaded(self):
        assert HandlerType.THREADED is not None

    def test_three_types(self):
        assert len(HandlerType) == 3


class TestEventDataclass:
    def test_create_minimal(self):
        e = Event()
        assert isinstance(e, Event)

    def test_default_event_type(self):
        e = Event()
        assert e.event_type == EventType.SYSTEM

    def test_default_priority(self):
        e = Event()
        assert e.priority == EventPriority.NORMAL

    def test_event_id_generated(self):
        e = Event()
        assert e.event_id is not None
        assert len(e.event_id) > 0

    def test_two_events_have_different_ids(self):
        e1 = Event()
        e2 = Event()
        assert e1.event_id != e2.event_id

    def test_custom_event_type(self):
        e = Event(event_type=EventType.ORDER_PLACED, data={"symbol": "SPY"})
        assert e.event_type == EventType.ORDER_PLACED

    def test_data_stored(self):
        e = Event(data={"key": "value"})
        assert e.data["key"] == "value"

    def test_to_dict(self):
        e = Event(event_type=EventType.TRADE, data={"qty": 10})
        d = e.to_dict()
        assert isinstance(d, dict)
        assert "event_id" in d
        assert "event_type" in d
        assert d["event_type"] == "trade"

    def test_from_dict(self):
        e = Event(event_type=EventType.SYSTEM, data={"test": True})
        d = e.to_dict()
        e2 = Event.from_dict(d)
        assert e2.event_id == e.event_id
        assert e2.event_type == e.event_type

    def test_post_init_string_event_type(self):
        e = Event(event_type="system")  # type: ignore
        assert e.event_type == EventType.SYSTEM

    def test_post_init_invalid_event_type_fallback(self):
        e = Event(event_type="nonexistent_type_xyz")  # type: ignore
        assert e.event_type == EventType.SYSTEM

    def test_timestamp_is_datetime(self):
        e = Event()
        assert isinstance(e.timestamp, datetime.datetime)


class TestEventMetricsDataclass:
    def test_create(self):
        em = EventMetrics()
        assert isinstance(em, EventMetrics)

    def test_all_zeros_on_init(self):
        em = EventMetrics()
        assert em.events_published == 0
        assert em.events_processed == 0
        assert em.events_failed == 0
        assert em.handlers_registered == 0

    def test_incrementable(self):
        em = EventMetrics()
        em.events_published += 5
        assert em.events_published == 5


class TestEventFilter:
    def test_create(self):
        ef = EventFilter()
        assert isinstance(ef, EventFilter)

    def test_apply_passes_by_default(self):
        ef = EventFilter()
        e = Event()
        assert ef.apply(e) is True

    def test_exclude_type(self):
        ef = EventFilter()
        ef.exclude_type(EventType.HEARTBEAT)
        e = Event(event_type=EventType.HEARTBEAT)
        assert ef.apply(e) is False

    def test_exclude_type_allows_others(self):
        ef = EventFilter()
        ef.exclude_type(EventType.HEARTBEAT)
        e = Event(event_type=EventType.SYSTEM)
        assert ef.apply(e) is True

    def test_include_only_types(self):
        ef = EventFilter()
        ef.include_only_types([EventType.TRADE])
        e = Event(event_type=EventType.SYSTEM)
        assert ef.apply(e) is False

    def test_include_only_types_allows_included(self):
        ef = EventFilter()
        ef.include_only_types([EventType.TRADE])
        e = Event(event_type=EventType.TRADE)
        assert ef.apply(e) is True

    def test_priority_threshold(self):
        ef = EventFilter()
        ef.set_priority_threshold(EventPriority.HIGH)
        e_low = Event(priority=EventPriority.LOW)
        e_high = Event(priority=EventPriority.HIGH)
        assert ef.apply(e_low) is False
        assert ef.apply(e_high) is True

    def test_custom_filter(self):
        ef = EventFilter()
        ef.add_filter(lambda ev: ev.data.get("allow", False))
        e1 = Event(data={"allow": False})
        e2 = Event(data={"allow": True})
        assert ef.apply(e1) is False
        assert ef.apply(e2) is True

    def test_remove_filter(self):
        ef = EventFilter()
        def f(ev):
            return False
        ef.add_filter(f)
        ef.remove_filter(f)
        e = Event()
        assert ef.apply(e) is True

    def test_source_filter(self):
        ef = EventFilter()
        ef.filter_by_source(["StrategyEngine"])
        e_good = Event(source="StrategyEngine")
        e_bad = Event(source="OtherModule")
        assert ef.apply(e_good) is True
        assert ef.apply(e_bad) is False


class TestEventManagerInit:
    def setup_method(self):
        _reset_a05_singleton()

    def test_creates_instance(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            em = EventManager(persist_events=False, db_path=Path(tmpdir) / "test.db")
            assert isinstance(em, EventManager)

    def test_not_running_initially(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            em = EventManager(persist_events=False, db_path=Path(tmpdir) / "test.db")
            assert em.is_running is False

    def test_persist_events_setting(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            em = EventManager(persist_events=False, db_path=Path(tmpdir) / "test.db")
            assert em.persist_events is False

    def test_metrics_zeroed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            em = EventManager(persist_events=False, db_path=Path(tmpdir) / "test.db")
            assert em.metrics.events_published == 0

    def test_event_history_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            em = EventManager(persist_events=False, db_path=Path(tmpdir) / "test.db")
            assert len(em.event_history) == 0

    def test_dead_letter_queue_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            em = EventManager(persist_events=False, db_path=Path(tmpdir) / "test.db")
            assert len(em.dead_letter_queue) == 0

    def test_get_method_compatibility(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            em = EventManager(persist_events=False, db_path=Path(tmpdir) / "test.db")
            result = em.get("max_queue_size")
            assert result == DEFAULT_QUEUE_SIZE

    def test_get_method_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            em = EventManager(persist_events=False, db_path=Path(tmpdir) / "test.db")
            result = em.get("nonexistent_key", "fallback")
            assert result == "fallback"


class TestEventManagerLifecycle:
    """Test EventManager lifecycle state without starting threads (which hang on queue.join())"""

    def setup_method(self):
        _reset_a05_singleton()

    def _make_em(self):
        tmpdir = tempfile.mkdtemp()
        return EventManager(persist_events=False, db_path=Path(tmpdir) / "test.db")

    def test_not_running_before_start(self):
        em = self._make_em()
        assert em.is_running is False

    def test_shutdown_event_not_set_initially(self):
        em = self._make_em()
        assert not em._shutdown_event.is_set()

    def test_worker_threads_empty_before_start(self):
        em = self._make_em()
        assert len(em.worker_threads) == 0

    def test_event_queue_initially_empty(self):
        em = self._make_em()
        assert em.event_queue.empty()

    def test_priority_queue_initially_empty(self):
        em = self._make_em()
        assert em.priority_queue.empty()

    def test_stop_when_not_running_returns_true(self):
        em = self._make_em()
        result = em.stop()  # Not started — should return True immediately
        assert result is True

    def test_executor_created_on_init(self):
        em = self._make_em()
        import concurrent.futures
        assert isinstance(em.executor, concurrent.futures.ThreadPoolExecutor)


class TestEventManagerSubscribeEmit:
    def setup_method(self):
        _reset_a05_singleton()

    def _make_em(self):
        tmpdir = tempfile.mkdtemp()
        return EventManager(persist_events=False, db_path=Path(tmpdir) / "test.db")

    def test_subscribe_returns_handler_id(self):
        em = self._make_em()
        hid = em.subscribe(EventType.SYSTEM, lambda e: None)
        assert isinstance(hid, str)
        assert len(hid) > 0

    def test_subscribe_registers_handler(self):
        em = self._make_em()
        em.subscribe(EventType.TRADE, lambda e: None)
        assert EventType.TRADE in em.handlers
        assert len(em.handlers[EventType.TRADE]) == 1

    def test_subscribe_increments_metric(self):
        em = self._make_em()
        em.subscribe(EventType.SYSTEM, lambda e: None)
        assert em.metrics.handlers_registered == 1

    def test_unsubscribe_removes_handler(self):
        em = self._make_em()
        hid = em.subscribe(EventType.SYSTEM, lambda e: None)
        result = em.unsubscribe(hid)
        assert result is True
        assert len(em.handlers[EventType.SYSTEM]) == 0

    def test_unsubscribe_nonexistent_returns_false(self):
        em = self._make_em()
        result = em.unsubscribe("nonexistent-id")
        assert result is False

    def test_subscribe_all_adds_global_handler(self):
        em = self._make_em()
        em.subscribe_all(lambda e: None)
        assert len(em.global_handlers) == 1

    def test_emit_increments_published(self):
        em = self._make_em()
        em.emit(EventType.SYSTEM, {"msg": "test"})
        assert em.metrics.events_published == 1

    def test_emit_returns_bool(self):
        em = self._make_em()
        result = em.emit(EventType.SYSTEM, {"test": True})
        assert isinstance(result, bool)
        assert result is True

    def test_publish_event_returns_bool(self):
        em = self._make_em()
        e = Event(event_type=EventType.SYSTEM)
        result = em.publish(e)
        assert isinstance(result, bool)

    def test_high_priority_goes_to_priority_queue(self):
        em = self._make_em()
        em.emit(EventType.RISK_LIMIT_BREACH, {}, priority=EventPriority.HIGH)
        assert em.priority_queue.qsize() > 0

    def test_low_priority_goes_to_event_queue(self):
        em = self._make_em()
        em.emit(EventType.INFO, {}, priority=EventPriority.LOW)
        assert em.event_queue.qsize() > 0

    def test_create_event_without_publishing(self):
        em = self._make_em()
        e = em.create_event(EventType.TRADE, {"symbol": "SPY"})
        assert isinstance(e, Event)
        assert e.event_type == EventType.TRADE
        assert em.metrics.events_published == 0  # Not published

    def test_clear_handlers(self):
        em = self._make_em()
        em.subscribe(EventType.SYSTEM, lambda e: None)
        em.clear_handlers()
        assert len(em.handlers) == 0

    def test_clear_specific_handler_type(self):
        em = self._make_em()
        em.subscribe(EventType.SYSTEM, lambda e: None)
        em.subscribe(EventType.TRADE, lambda e: None)
        em.clear_handlers(EventType.SYSTEM)
        assert len(em.handlers[EventType.SYSTEM]) == 0
        assert len(em.handlers[EventType.TRADE]) == 1

    def test_get_metrics_returns_dict(self):
        em = self._make_em()
        metrics = em.get_metrics()
        assert isinstance(metrics, dict)
        assert "events_published" in metrics
        assert "events_processed" in metrics
        assert "handlers_registered" in metrics

    def test_get_handler_stats_returns_list(self):
        em = self._make_em()
        em.subscribe(EventType.SYSTEM, lambda e: None, name="TestH")
        stats = em.get_handler_stats()
        assert isinstance(stats, list)
        assert len(stats) == 1
        assert stats[0]["name"] == "TestH"

    def test_get_event_history_empty(self):
        em = self._make_em()
        history = em.get_event_history()
        assert isinstance(history, list)
        assert len(history) == 0

    def test_global_filter_excludes_type(self):
        em = self._make_em()
        ef = EventFilter()
        ef.exclude_type(EventType.HEARTBEAT)
        em.global_filter = ef
        result = em.emit(EventType.HEARTBEAT, {})
        assert result is False

    def test_add_global_filter(self):
        em = self._make_em()
        em.add_global_filter(lambda ev: False)
        result = em.emit(EventType.SYSTEM, {})
        assert result is False

    def test_remove_global_filter(self):
        em = self._make_em()
        def f(ev):
            return False
        em.add_global_filter(f)
        em.remove_global_filter(f)
        result = em.emit(EventType.SYSTEM, {})
        assert result is True  # Filter removed, passes now


class TestEventBus:
    def test_create(self):
        eb = EventBus()
        assert isinstance(eb, EventBus)

    def test_subscribe_and_publish(self):
        eb = EventBus()
        received = []
        eb.subscribe("trade", lambda data: received.append(data))
        eb.publish("trade", {"symbol": "SPY"})
        assert len(received) == 1
        assert received[0]["symbol"] == "SPY"

    def test_unsubscribe_clears_all(self):
        eb = EventBus()
        received = []
        eb.subscribe("trade", lambda data: received.append(data))
        eb.unsubscribe("trade")
        eb.publish("trade", {"symbol": "SPY"})
        assert len(received) == 0

    def test_unsubscribe_specific_callback(self):
        eb = EventBus()
        received = []
        def cb(data):
            return received.append(data)
        eb.subscribe("trade", cb)
        eb.unsubscribe("trade", cb)
        eb.publish("trade", {"k": "v"})
        assert len(received) == 0

    def test_publish_no_subscribers(self):
        eb = EventBus()
        eb.publish("unknown_event", {})  # Should not raise

    def test_multiple_subscribers(self):
        eb = EventBus()
        r1, r2 = [], []
        eb.subscribe("test", lambda d: r1.append(d))
        eb.subscribe("test", lambda d: r2.append(d))
        eb.publish("test", "data")
        assert len(r1) == 1
        assert len(r2) == 1


class TestEventManagerGlobalFunctions:
    def setup_method(self):
        _reset_a05_singleton()

    def test_get_event_manager_returns_instance(self):
        em = get_event_manager(persist_events=False)
        assert isinstance(em, EventManager)
        _reset_a05_singleton()

    def test_get_event_manager_singleton(self):
        em1 = get_event_manager(persist_events=False)
        em2 = get_event_manager(persist_events=False)
        assert em1 is em2
        _reset_a05_singleton()

    def test_reset_clears_singleton_module_state(self):
        get_event_manager(persist_events=False)
        _reset_a05_singleton()
        import Spyder.SpyderA_Core.SpyderA05_EventManager as a05_module
        assert a05_module._event_manager_instance is None

    def test_get_event_bus_returns_eventbus(self):
        from Spyder.SpyderA_Core.SpyderA05_EventManager import get_event_bus
        eb = get_event_bus()
        assert isinstance(eb, EventBus)


# ==============================================================================
# A06 — MasterController
# ==============================================================================

class TestA06Enums:
    def test_system_status_values(self):
        assert SystemStatus.INITIALIZING.value == "initializing"
        assert SystemStatus.RUNNING.value == "running"
        assert SystemStatus.STOPPED.value == "stopped"

    def test_system_status_count(self):
        assert len(SystemStatus) == 9

    def test_module_status_values(self):
        assert A06ModuleStatus.NOT_STARTED.value == "not_started"
        assert A06ModuleStatus.RUNNING.value == "running"
        assert A06ModuleStatus.ERROR.value == "error"

    def test_market_state_values(self):
        assert MarketState.MARKET_OPEN.value == "market_open"
        assert MarketState.MARKET_CLOSED.value == "market_closed"
        assert MarketState.HOLIDAY.value == "holiday"

    def test_trading_mode_values(self):
        assert TradingMode.PAPER.value == "paper"
        assert TradingMode.LIVE.value == "live"
        assert TradingMode.BACKTEST.value == "backtest"
        assert TradingMode.SIMULATION.value == "simulation"


class TestA06Dataclasses:
    def test_module_info_create(self):
        mi = A06ModuleInfo(
            module_id="U01",
            group="U",
            name="Logger",
            status=A06ModuleStatus.NOT_STARTED,
            dependencies=[],
            priority=1,
        )
        assert isinstance(mi, A06ModuleInfo)

    def test_module_info_fields(self):
        mi = A06ModuleInfo(
            module_id="U01",
            group="U",
            name="Logger",
            status=A06ModuleStatus.RUNNING,
            dependencies=["U02"],
            priority=2,
        )
        assert mi.module_id == "U01"
        assert mi.priority == 2
        assert mi.dependencies == ["U02"]

    def test_system_config_create(self):
        sc = SystemConfig(
            trading_mode=TradingMode.PAPER,
            environment="development",
            portfolio_value=1_000_000,
            max_daily_loss=50_000,
            max_positions=10,
            risk_limits={"max_var": 0.10},
            database={"type": "sqlite"},
            ml_models_path="./models",
            data_path="./data",
            logs_path="./logs",
            enable_alerts=True,
            enable_paper_trading=True,
            enable_ml_predictions=True,
            enable_risk_management=True,
        )
        assert isinstance(sc, SystemConfig)

    def test_system_config_trading_mode(self):
        sc = SystemConfig(
            trading_mode=TradingMode.LIVE,
            environment="production",
            portfolio_value=1_000_000,
            max_daily_loss=50_000,
            max_positions=10,
            risk_limits={},
            database={},
            ml_models_path="",
            data_path="",
            logs_path="",
            enable_alerts=False,
            enable_paper_trading=False,
            enable_ml_predictions=False,
            enable_risk_management=False,
        )
        assert sc.trading_mode == TradingMode.LIVE

    def test_startup_sequence_create(self):
        ss = StartupSequence(
            phase="Core",
            modules=["U01", "U02"],
            parallel=True,
            timeout=30,
            critical=True,
        )
        assert isinstance(ss, StartupSequence)
        assert ss.parallel is True
        assert ss.critical is True


class TestMasterControllerInit:
    def test_creates_with_nonexistent_config(self):
        # When config path doesn't exist, uses defaults
        mc = MasterController(config_path="nonexistent_config.yaml")
        assert isinstance(mc, MasterController)

    def test_initial_status_is_initializing(self):
        mc = MasterController(config_path="nonexistent_config.yaml")
        assert mc.status == SystemStatus.INITIALIZING

    def test_modules_registry_populated(self):
        mc = MasterController(config_path="nonexistent_config.yaml")
        assert len(mc.modules) > 0

    def test_config_uses_defaults(self):
        mc = MasterController(config_path="nonexistent_config.yaml")
        assert isinstance(mc.config, SystemConfig)

    def test_default_trading_mode_is_paper(self):
        mc = MasterController(config_path="nonexistent_config.yaml")
        assert mc.config.trading_mode == TradingMode.PAPER

    def test_trading_not_enabled_initially(self):
        mc = MasterController(config_path="nonexistent_config.yaml")
        assert mc.trading_enabled is False

    def test_market_state_is_closed_initially(self):
        mc = MasterController(config_path="nonexistent_config.yaml")
        assert mc.market_state == MarketState.MARKET_CLOSED

    def test_modules_have_correct_structure(self):
        mc = MasterController(config_path="nonexistent_config.yaml")
        for mod_id, mod_info in mc.modules.items():
            assert isinstance(mod_info, A06ModuleInfo)
            assert mod_info.module_id == mod_id

    def test_get_default_config(self):
        mc = MasterController(config_path="nonexistent_config.yaml")
        cfg = mc._get_default_config()
        assert isinstance(cfg, dict)
        assert "trading_mode" in cfg
        assert cfg["trading_mode"] == "paper"


# ==============================================================================
# A08 — FSeriesOrchestrator
# ==============================================================================

class TestA08Enums:
    def test_module_priority_critical(self):
        assert ModulePriority.CRITICAL.value == 1

    def test_module_priority_batch(self):
        assert ModulePriority.BATCH.value == 5

    def test_module_priority_ordering(self):
        assert ModulePriority.CRITICAL.value < ModulePriority.HIGH.value
        assert ModulePriority.HIGH.value < ModulePriority.MEDIUM.value

    def test_resource_type_values(self):
        assert ResourceType.CPU.value == "cpu"
        assert ResourceType.MEMORY.value == "memory"
        assert ResourceType.IO.value == "io"

    def test_a08_module_status_values(self):
        assert A08ModuleStatus.IDLE.value == "idle"
        assert A08ModuleStatus.RUNNING.value == "running"
        assert A08ModuleStatus.ERROR.value == "error"

    def test_execution_mode_values(self):
        assert ExecutionMode.SEQUENTIAL.value == "sequential"
        assert ExecutionMode.PARALLEL.value == "parallel"


class TestA08Dataclasses:
    def test_resource_allocation_defaults(self):
        ra = ResourceAllocation()
        assert ra.cpu_cores == 1
        assert ra.memory_mb == 512
        assert ra.io_priority == 3

    def test_resource_allocation_custom(self):
        ra = ResourceAllocation(cpu_cores=4, memory_mb=2048)
        assert ra.cpu_cores == 4
        assert ra.memory_mb == 2048

    def test_module_task_create(self):
        mt = ModuleTask(
            task_id="t1",
            module_name="F16",
            priority=ModulePriority.CRITICAL,
            function_name="run",
            parameters={"interval": 5},
        )
        assert isinstance(mt, ModuleTask)

    def test_module_task_defaults(self):
        mt = ModuleTask(
            task_id="t1",
            module_name="F14",
            priority=ModulePriority.HIGH,
            function_name="analyze",
            parameters={},
        )
        assert mt.status == A08ModuleStatus.QUEUED
        assert mt.retry_count == 0
        assert mt.execution_time_s == 0.0

    def test_module_metrics_create(self):
        mm = ModuleMetrics(module_name="F12")
        assert mm.tasks_completed == 0
        assert mm.health_score == 100.0
        assert mm.module_name == "F12"

    def test_system_resources_defaults(self):
        sr = SystemResources()
        assert sr.cpu_usage_percent == 0.0
        assert sr.memory_usage_percent == 0.0

    def test_orchestration_config_defaults(self):
        oc = OrchestrationConfig()
        assert oc.max_concurrent_tasks == 8
        assert oc.auto_scaling_enabled is True
        assert oc.failover_enabled is True
        assert oc.max_retry_attempts == 3


class TestFSeriesOrchestratorInit:
    def test_creates_with_defaults(self):
        orc = FSeriesOrchestrator()
        assert isinstance(orc, FSeriesOrchestrator)

    def test_creates_with_custom_config(self):
        cfg = OrchestrationConfig(max_concurrent_tasks=4)
        orc = FSeriesOrchestrator(config=cfg)
        assert orc.config.max_concurrent_tasks == 4

    def test_not_active_initially(self):
        orc = FSeriesOrchestrator()
        assert orc.orchestration_active is False

    def test_task_queues_initialized(self):
        orc = FSeriesOrchestrator()
        for priority in ModulePriority:
            assert priority in orc.task_queues

    def test_module_metrics_initialized(self):
        orc = FSeriesOrchestrator()
        for module in ["F12", "F13", "F14", "F15", "F16"]:
            assert module in orc.module_metrics
        for module in ["C21", "C22", "C23", "C24"]:
            assert module in orc.module_metrics

    def test_f_series_modules_empty_initially(self):
        orc = FSeriesOrchestrator()
        assert len(orc.f_series_modules) == 0

    def test_register_valid_f_series_module(self):
        orc = FSeriesOrchestrator()
        mock_module = MagicMock()
        result = orc.register_f_series_module("F12", mock_module)
        assert result is True
        assert "F12" in orc.f_series_modules

    def test_register_invalid_f_series_module(self):
        orc = FSeriesOrchestrator()
        result = orc.register_f_series_module("X99", MagicMock())
        assert result is False

    def test_register_valid_c_series_module(self):
        orc = FSeriesOrchestrator()
        result = orc.register_c_series_module("C21", MagicMock())
        assert result is True
        assert "C21" in orc.c_series_modules

    def test_register_invalid_c_series_module(self):
        orc = FSeriesOrchestrator()
        result = orc.register_c_series_module("C99", MagicMock())
        assert result is False

    def test_submit_task_returns_task_id(self):
        orc = FSeriesOrchestrator()
        task_id = orc.submit_task(
            module_name="F16",
            function_name="start_streaming",
            parameters={"interval": 1},
        )
        assert isinstance(task_id, str)
        assert "F16" in task_id

    def test_submit_task_uses_priority_map(self):
        orc = FSeriesOrchestrator()
        orc.submit_task("F16", "run", {})
        # F16 maps to CRITICAL priority
        assert not orc.task_queues[ModulePriority.CRITICAL].empty()

    def test_submitted_task_in_queue(self):
        orc = FSeriesOrchestrator()
        orc.submit_task("F12", "backtest", {})
        # F12 → BATCH priority
        assert not orc.task_queues[ModulePriority.BATCH].empty()

    def test_performance_history_empty_initially(self):
        orc = FSeriesOrchestrator()
        assert len(orc.performance_history) == 0

    def test_adaptive_parameters_set(self):
        orc = FSeriesOrchestrator()
        assert "cpu_threshold" in orc.adaptive_parameters
        assert orc.adaptive_parameters["cpu_threshold"] == 80.0
