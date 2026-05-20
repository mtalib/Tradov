#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderA_Core
Module: SpyderA04_Scheduler.py
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
import threading
from datetime import datetime, time, timedelta, date, UTC
from typing import Any
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto
import logging
import os
from pathlib import Path
import json

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pytz
import sqlite3
import traceback
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.job import Job
from apscheduler.events import (

    EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, EVENT_JOB_MISSED,
    JobExecutionEvent, JobEvent
)
import pandas_market_calendars as mcal
import holidays

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderA_Core.SpyderA05_EventManager import EventManager, EventType

# ==============================================================================
# CONSTANTS
# ==============================================================================
EASTERN_TZ = pytz.timezone("US/Eastern")
UTC_TZ = pytz.UTC

# Default market hours (ET)
DEFAULT_MARKET_OPEN = time(9, 30)
DEFAULT_MARKET_CLOSE = time(16, 0)
DEFAULT_PREMARKET_OPEN = time(4, 0)
DEFAULT_AFTERHOURS_CLOSE = time(20, 0)

# Task execution windows
POSITION_CHECK_BEFORE_CLOSE_MINUTES = 15
STRATEGY_WINDOW_BUFFER_MINUTES = 5

# Database schema
TASK_HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS task_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    execution_time TIMESTAMP NOT NULL,
    status TEXT NOT NULL,
    duration_ms INTEGER,
    error_message TEXT,
    metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_task_id ON task_history(task_id);
CREATE INDEX IF NOT EXISTS idx_execution_time ON task_history(execution_time);
CREATE INDEX IF NOT EXISTS idx_status ON task_history(status);
"""

# ==============================================================================
# ENUMS
# ==============================================================================
class ScheduleType(Enum):
    """Types of scheduling"""
    CRON = auto()
    INTERVAL = auto()
    DATE = auto()
    MARKET_BASED = auto()

class TaskStatus(Enum):
    """Task execution status"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    MISSED = "missed"
    CANCELLED = "cancelled"

class MarketSession(Enum):
    """Market session types"""
    PREMARKET = "premarket"
    REGULAR = "regular"
    AFTERHOURS = "afterhours"
    CLOSED = "closed"

class TradingDayType(Enum):
    """Types of trading days"""
    REGULAR = "regular"
    EARLY_CLOSE = "early_close"
    HOLIDAY = "holiday"
    WEEKEND = "weekend"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class ScheduledTask:
    """Scheduled task information"""
    task_id: str
    name: str
    func: Callable
    schedule_type: ScheduleType
    schedule_params: dict[str, Any]
    enabled: bool = True
    max_instances: int = 1
    misfire_grace_time: int = 30  # seconds
    coalesce: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_run: datetime | None = None
    next_run: datetime | None = None
    run_count: int = 0
    error_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class TaskExecution:
    """Task execution record"""
    task_id: str
    execution_time: datetime
    status: TaskStatus
    duration_ms: int | None = None
    error_message: str | None = None
    result: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class MarketHours:
    """Market hours for a specific date"""
    date: date
    market_open: datetime | None = None
    market_close: datetime | None = None
    premarket_open: datetime | None = None
    afterhours_close: datetime | None = None
    is_trading_day: bool = True
    day_type: TradingDayType = TradingDayType.REGULAR
    notes: str | None = None

@dataclass
class TradingWindow:
    """Trading window definition"""
    name: str
    start_time: time
    end_time: time
    days_of_week: list[int] = field(default_factory=lambda: list(range(5)))  # Mon-Fri
    enabled: bool = True
    strategies: list[str] = field(default_factory=list)

# ==============================================================================
# MARKET CALENDAR
# ==============================================================================
class MarketCalendar:
    """Enhanced market calendar with holiday support"""

    def __init__(self):
        self.logger = SpyderLogger.get_logger(__name__)

        # Initialize market calendars
        self.nyse_calendar = mcal.get_calendar('NYSE')
        self.us_holidays = holidays.US(years=range(2020, 2030))

        # Cache for market hours
        self._hours_cache: dict[date, MarketHours] = {}
        self._cache_lock = threading.Lock()

        # Special trading days (early closes)
        self.early_close_days = {
            "day_before_independence": time(13, 0),
            "day_after_thanksgiving": time(13, 0),
            "christmas_eve": time(13, 0),
            "new_years_eve": time(13, 0) if datetime.now(UTC).year >= 2025 else time(16, 0)
        }

        self.logger.info("MarketCalendar initialized")

    def get_market_hours(self, date: date) -> MarketHours:
        """Get market hours for a specific date"""
        with self._cache_lock:
            # Check cache
            if date in self._hours_cache:
                return self._hours_cache[date]

            # Calculate market hours
            hours = self._calculate_market_hours(date)

            # Cache result
            self._hours_cache[date] = hours

            return hours

    def _calculate_market_hours(self, date: date) -> MarketHours:
        """Calculate market hours for a date"""
        # Check if weekend
        if date.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return MarketHours(
                date=date,
                is_trading_day=False,
                day_type=TradingDayType.WEEKEND
            )

        # Check if holiday
        if date in self.us_holidays:
            return MarketHours(
                date=date,
                is_trading_day=False,
                day_type=TradingDayType.HOLIDAY,
                notes=self.us_holidays.get(date)
            )

        # Get NYSE schedule
        schedule = self.nyse_calendar.schedule(
            start_date=date,
            end_date=date
        )

        if schedule.empty:
            return MarketHours(
                date=date,
                is_trading_day=False,
                day_type=TradingDayType.HOLIDAY
            )

        # Regular trading day
        market_open = schedule.iloc[0]['market_open'].tz_convert(EASTERN_TZ)
        market_close = schedule.iloc[0]['market_close'].tz_convert(EASTERN_TZ)

        # Check for early close
        day_type = TradingDayType.REGULAR
        if market_close.time() < DEFAULT_MARKET_CLOSE:
            day_type = TradingDayType.EARLY_CLOSE

        # Calculate extended hours
        premarket_open = market_open.replace(hour=4, minute=0)
        afterhours_close = market_close.replace(hour=20, minute=0)

        return MarketHours(
            date=date,
            market_open=market_open,
            market_close=market_close,
            premarket_open=premarket_open,
            afterhours_close=afterhours_close,
            is_trading_day=True,
            day_type=day_type
        )

    def is_market_open(self, dt: datetime | None = None) -> bool:
        """Check if market is currently open"""
        if dt is None:
            dt = datetime.now(EASTERN_TZ)
        else:
            dt = dt.astimezone(EASTERN_TZ)

        hours = self.get_market_hours(dt.date())

        if not hours.is_trading_day:
            return False

        return hours.market_open <= dt <= hours.market_close

    def get_next_trading_day(self, after_date: date | None = None) -> date:
        """Get next trading day"""
        if after_date is None:
            after_date = date.today()

        current = after_date
        while True:
            current = current + timedelta(days=1)
            hours = self.get_market_hours(current)
            if hours.is_trading_day:
                return current

            # Safety check
            if current > after_date + timedelta(days=30):
                raise ValueError("No trading day found within 30 days")

    def get_trading_days(self, start_date: date, end_date: date) -> list[date]:
        """Get list of trading days in date range"""
        trading_days = []
        current = start_date

        while current <= end_date:
            hours = self.get_market_hours(current)
            if hours.is_trading_day:
                trading_days.append(current)
            current = current + timedelta(days=1)

        return trading_days

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class Scheduler:
    """
    Advanced scheduler for trading operations.

    This class manages all scheduled tasks including market-based events,
    strategy executions, data updates, and system maintenance. It provides
    flexible scheduling options, task persistence, error recovery, and
    integration with market calendars.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling system
        event_manager: Event management system
        scheduler: APScheduler instance
        market_calendar: Market calendar instance
        tasks: Dictionary of scheduled tasks
        trading_windows: Defined trading windows
        task_history: Task execution history
    """

    def __init__(self, event_manager: EventManager, use_async: bool = False):
        """
        Initialize the scheduler.

        Args:
            event_manager: Event management system
            use_async: Use async scheduler (for asyncio environments)
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.event_manager = event_manager

        # Initialize scheduler
        if use_async:
            self.scheduler = AsyncIOScheduler(timezone=EASTERN_TZ)
        else:
            self.scheduler = BackgroundScheduler(timezone=EASTERN_TZ)

        # Task management
        self.tasks: dict[str, ScheduledTask] = {}
        self._task_lock = threading.RLock()

        # Trading windows
        self.trading_windows: dict[str, TradingWindow] = {}
        self._init_default_windows()
        self.session_window_config: dict[str, Any] = {
            "primary_start_et": "09:30",
            "primary_end_et": "16:15",
            "first_entry_not_before_et": "10:15",
            "zero_dte_no_new_risk_cutoff_et": "14:30",
            "broker_cutoff_et": "16:00",
            "broker_cutoff_buffer_minutes": 10,
            "pin_risk_monitor_end_et": "17:30",
            "fail_closed_if_cutoff_unknown_live": True,
        }
        self._load_session_window_config()

        # Market calendar
        self.market_calendar = MarketCalendar()

        # Task history database
        self.db_path = Path.home() / ".spyder" / "scheduler.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

        # Read configurable intervals from SCHEDULER_CONFIG (with fallback defaults)
        try:
            from config.config import SCHEDULER_CONFIG
            self._data_update_interval: int = SCHEDULER_CONFIG.get("data_update_interval_minutes", 5)  # noqa: E501
            self._risk_check_interval: int = SCHEDULER_CONFIG.get("risk_check_interval_minutes", 15)
        except Exception:
            self._data_update_interval = 5
            self._risk_check_interval = 15

        # Event-clock configuration (P0-3): blackout pre/post windows around
        # high-impact events with a periodic feed-state publication.
        self.event_clock_config = {
            'enabled': True,
            'sources': 'calendar+manual',
            'high_impact_only': True,
            'blackout_pre_minutes': 30,
            'blackout_post_minutes': 30,
            'allowlist_strategies': [],
            'max_size_multiplier': 0.25,
        }
        self._event_calendar_events: list[dict[str, Any]] = []
        self._event_clock_manual_state: dict[str, Any] | None = None
        self._last_event_clock_state: str | None = None
        self._load_event_clock_config()
        self._event_clock_handler_id: str | None = None
        self._register_event_clock_handlers()

        # Performance metrics
        self.metrics = {
            'tasks_executed': 0,
            'tasks_succeeded': 0,
            'tasks_failed': 0,
            'tasks_missed': 0,
            'total_execution_time_ms': 0,
            'last_heartbeat': None,
        }

        # Register scheduler event handlers
        self._register_scheduler_handlers()

        # Schedule default tasks
        self._schedule_default_tasks()

        self.logger.info("Scheduler initialized")

    def _init_database(self):
        """Initialize task history database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.executescript(TASK_HISTORY_SCHEMA)
            self.logger.info("Task history database initialized")
        except Exception as e:
            self.logger.error("Database initialization failed: %s", e)

    def _init_default_windows(self):
        """Initialize default trading windows"""
        # Regular market hours window
        self.trading_windows["regular_market"] = TradingWindow(
            name="Regular Market Hours",
            start_time=time(9, 30),
            end_time=time(16, 15),
            enabled=True
        )

        # Opening range window
        self.trading_windows["opening_range"] = TradingWindow(
            name="Opening Range",
            start_time=time(9, 30),
            end_time=time(9, 45),
            enabled=True
        )

        self.trading_windows["post_open_fade"] = TradingWindow(
            name="Post-Open Fade",
            start_time=time(9, 45),
            end_time=time(10, 15),
            enabled=True
        )

        self.trading_windows["primary_session"] = TradingWindow(
            name="Primary Session",
            start_time=time(10, 15),
            end_time=time(11, 30),
            enabled=True
        )

        self.trading_windows["lunch_drift"] = TradingWindow(
            name="Lunch Drift",
            start_time=time(11, 30),
            end_time=time(13, 0),
            enabled=True
        )

        self.trading_windows["afternoon_continuation"] = TradingWindow(
            name="Afternoon Continuation",
            start_time=time(13, 0),
            end_time=time(14, 30),
            enabled=True
        )

        self.trading_windows["pre_moc"] = TradingWindow(
            name="Pre-MOC",
            start_time=time(14, 30),
            end_time=time(15, 0),
            enabled=True
        )

        self.trading_windows["moc_close"] = TradingWindow(
            name="MOC / Close",
            start_time=time(15, 0),
            end_time=time(16, 0),
            enabled=True
        )

        # Closing range window
        self.trading_windows["closing_range"] = TradingWindow(
            name="Closing Range",
            start_time=time(15, 45),
            end_time=time(16, 15),
            enabled=True
        )

        # Pre-market window
        self.trading_windows["premarket"] = TradingWindow(
            name="Pre-Market",
            start_time=time(7, 0),
            end_time=time(9, 30),
            enabled=False
        )

    def _load_session_window_config(self) -> None:
        """Load autonomous session-window policy from A03 readiness config."""
        try:
            from Spyder.SpyderA_Core.SpyderA03_Configuration import get_config_manager

            cm = get_config_manager()
            mode = str(cm.get("trading.mode", "paper") or "paper")
            base_config = cm.config_data if isinstance(getattr(cm, "config_data", None), dict) else {}
            readiness = cm.validate_autonomous_readiness_config(base_config, mode)
            session_cfg = (
                readiness.get("effective", {})
                .get("autonomous_readiness", {})
                .get("session_window", {})
            )

            if isinstance(session_cfg, dict):
                merged_cfg = dict(self.session_window_config)
                merged_cfg.update(session_cfg)
                self.session_window_config = merged_cfg

                start_time = self._time_from_hhmm(str(merged_cfg.get("primary_start_et", "09:30")), time(9, 30))
                end_time = self._time_from_hhmm(str(merged_cfg.get("primary_end_et", "16:15")), time(16, 15))
                close_start = self._minutes_before(end_time, 30)

                self.trading_windows["regular_market"].start_time = start_time
                self.trading_windows["regular_market"].end_time = end_time
                self.trading_windows["closing_range"].start_time = close_start
                self.trading_windows["closing_range"].end_time = end_time

                self.logger.info(
                    "Loaded session_window config: start=%s end=%s cutoff=%s",
                    merged_cfg.get("primary_start_et"),
                    merged_cfg.get("primary_end_et"),
                    merged_cfg.get("zero_dte_no_new_risk_cutoff_et"),
                )
        except Exception as e:
            self.logger.warning("Session-window config load skipped; using defaults: %s", e)

    def _time_from_hhmm(self, value: str, fallback: time) -> time:
        """Parse HH:MM into a time object with fallback on parse errors."""
        try:
            parsed = datetime.strptime(value.strip(), "%H:%M")
            return time(parsed.hour, parsed.minute)
        except Exception:
            return fallback

    def _minutes_before(self, ref: time, minutes: int) -> time:
        """Return a clock time that is N minutes before ref time."""
        dt_ref = datetime.combine(date.today(), ref)
        dt_new = dt_ref - timedelta(minutes=max(0, int(minutes)))
        return dt_new.time()

    def _load_event_clock_config(self):
        """Load event-clock policy from validated A03 autonomous readiness config."""
        try:
            from Spyder.SpyderA_Core.SpyderA03_Configuration import get_config_manager

            cm = get_config_manager()
            mode = "paper"
            try:
                mode = str(cm.get("trading.mode", "paper") or "paper")
            except Exception:
                mode = "paper"

            base_config = cm.config_data if isinstance(getattr(cm, "config_data", None), dict) else {}  # noqa: E501
            readiness = cm.validate_autonomous_readiness_config(base_config, mode)
            event_cfg = (
                readiness.get("effective", {})
                .get("autonomous_readiness", {})
                .get("event_clock", {})
            )

            if not isinstance(event_cfg, dict):
                return

            allowlist = event_cfg.get("allowlist_strategies", [])
            if not isinstance(allowlist, list):
                allowlist = []

            self.event_clock_config.update({
                "enabled": bool(event_cfg.get("enabled", self.event_clock_config["enabled"])),
                "sources": str(event_cfg.get("sources", self.event_clock_config["sources"])),
                "high_impact_only": bool(event_cfg.get("high_impact_only", self.event_clock_config["high_impact_only"])),  # noqa: E501
                "blackout_pre_minutes": int(event_cfg.get("blackout_pre_minutes", self.event_clock_config["blackout_pre_minutes"])),  # noqa: E501
                "blackout_post_minutes": int(event_cfg.get("blackout_post_minutes", self.event_clock_config["blackout_post_minutes"])),  # noqa: E501
                "allowlist_strategies": [
                    s.strip() for s in allowlist if isinstance(s, str) and s.strip()
                ],
                "max_size_multiplier": float(
                    event_cfg.get(
                        "max_size_multiplier_during_event",
                        self.event_clock_config["max_size_multiplier"],
                    )
                ),
            })
            calendar_path = (
                event_cfg.get("calendar_path")
                or event_cfg.get("calendar_file")
                or os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                    "config",
                    "event_clock_calendar.json",
                )
            )
            self._load_event_calendar_file(calendar_path)
            self.logger.info("Event-clock config loaded from A03 validation")
        except Exception as e:
            self.logger.warning("Event-clock config load skipped; using defaults: %s", e)

    def _register_scheduler_handlers(self):
        """Register APScheduler event handlers"""
        self.scheduler.add_listener(
            self._on_job_executed,
            EVENT_JOB_EXECUTED
        )
        self.scheduler.add_listener(
            self._on_job_error,
            EVENT_JOB_ERROR
        )
        self.scheduler.add_listener(
            self._on_job_missed,
            EVENT_JOB_MISSED
        )

    def _register_event_clock_handlers(self) -> None:
        """Subscribe to event-clock manual override events."""
        try:
            if self.event_manager is None:
                return
            self._event_clock_handler_id = self.event_manager.subscribe(
                EventType.RISK,
                self._handle_event_clock_event,
                name="A04_EventClockOverride",
                handler_type=0,
            )
        except Exception as exc:
            self.logger.debug("Event-clock handler registration failed: %s", exc)

    def _handle_event_clock_event(self, event: Any) -> None:
        """Handle manual event-clock override requests from the UI."""
        try:
            payload = getattr(event, "data", None) or {}
            if not isinstance(payload, dict):
                return
            event_type = str(payload.get("type", "")).strip().lower()
            if event_type == "event_clock_manual_override":
                override = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
                self.set_event_clock_manual_state(override)
                self.publish_event_clock_state(force_emit=True)
            elif event_type == "event_clock_manual_clear":
                self.set_event_clock_manual_state(None)
                self.publish_event_clock_state(force_emit=True)
        except Exception as exc:
            self.logger.debug("Event-clock override handling failed: %s", exc)

    def _schedule_default_tasks(self):
        """Schedule default system tasks"""
        regular_window = self.trading_windows.get("regular_market")
        market_open_time = regular_window.start_time if regular_window else time(9, 30)
        market_close_time = regular_window.end_time if regular_window else time(16, 15)
        position_check_time = self._minutes_before(market_close_time, POSITION_CHECK_BEFORE_CLOSE_MINUTES)
        broker_cutoff_time = self._time_from_hhmm(
            str(self.session_window_config.get("broker_cutoff_et", "16:00")),
            time(16, 0),
        )
        broker_cutoff_buffer = int(self.session_window_config.get("broker_cutoff_buffer_minutes", 10) or 10)
        flatten_guard_time = self._minutes_before(broker_cutoff_time, broker_cutoff_buffer)

        # Market open/close events
        self.add_task(
            task_id="market_open",
            func=self._on_market_open,
            schedule_type=ScheduleType.CRON,
            hour=market_open_time.hour,
            minute=market_open_time.minute,
            day_of_week="mon-fri",
            description="Market open event"
        )

        self.add_task(
            task_id="market_close",
            func=self._on_market_close,
            schedule_type=ScheduleType.CRON,
            hour=market_close_time.hour,
            minute=market_close_time.minute,
            day_of_week="mon-fri",
            description="Market close event"
        )

        # Position check before close
        self.add_task(
            task_id="position_check_before_close",
            func=self._position_check_before_close,
            schedule_type=ScheduleType.CRON,
            hour=position_check_time.hour,
            minute=position_check_time.minute,
            day_of_week="mon-fri",
            description="Check positions before market close"
        )

        # Broker cutoff guard: flatten at-risk short options before broker cutoff.
        self.add_task(
            task_id="broker_cutoff_flatten_guard",
            func=self._on_broker_cutoff_flatten_guard,
            schedule_type=ScheduleType.CRON,
            hour=flatten_guard_time.hour,
            minute=flatten_guard_time.minute,
            day_of_week="mon-fri",
            description="Flatten at-risk short options before broker cutoff"
        )

        # Daily cleanup
        self.add_task(
            task_id="daily_cleanup",
            func=self._daily_cleanup,
            schedule_type=ScheduleType.CRON,
            hour=22,
            minute=0,
            description="Daily cleanup tasks"
        )

        # Event-clock state feed cadence (1 minute) for blackout transitions.
        self.add_task(
            task_id="event_clock_tick",
            func=self._on_event_clock_tick,
            schedule_type=ScheduleType.INTERVAL,
            minutes=1,
            description="Event-clock state publication",
        )

        # Pre-market data warmup — primes data pipeline 30 min before open
        self.add_task(
            task_id="premarket_warmup",
            func=self._on_premarket_warmup,
            schedule_type=ScheduleType.CRON,
            hour=9,
            minute=0,
            day_of_week="mon-fri",
            description="Pre-market data warmup — primes data pipeline 30 min before open"
        )

        # Pre-flight health check — broker/API/risk validation 15 min before open
        self.add_task(
            task_id="preflight_health_check",
            func=self._on_preflight_health_check,
            schedule_type=ScheduleType.CRON,
            hour=8,
            minute=55,
            day_of_week="mon-fri",
            description="Pre-flight health check — broker/API/risk validation before open"
        )

        # Escalated risk checks every 5 min during closing range (3:30–3:55 PM)
        self.add_task(
            task_id="closing_range_risk_check",
            func=self._on_closing_range_risk_check,
            schedule_type=ScheduleType.CRON,
            hour=15,
            minute="45,50,55",
            day_of_week="mon-fri",
            description="Escalated risk check during closing range (3:30–4:00 PM ET)"
        )

        self.add_task(
            task_id="closing_range_risk_check_late",
            func=self._on_closing_range_risk_check,
            schedule_type=ScheduleType.CRON,
            hour=16,
            minute="0,5,10",
            day_of_week="mon-fri",
            description="Escalated risk check during SPY options close window (4:00–4:15 PM ET)"
        )

        # EOD report trigger — fires after fills settle post-close
        self.add_task(
            task_id="eod_report",
            func=self._on_eod_report,
            schedule_type=ScheduleType.CRON,
            hour=16,
            minute=16,
            day_of_week="mon-fri",
            description="End-of-day report generation trigger"
        )

        # EOW summary — Friday 16:20 ET primary dispatch
        self.add_task(
            task_id="eow_report_friday",
            func=self._on_eow_report,
            schedule_type=ScheduleType.CRON,
            hour=16,
            minute=20,
            day_of_week="fri",
            description="End-of-week P/L summary and weekly ops report (Friday primary)"
        )

        # EOW summary fallback — Saturday 08:00 ET in case Friday run missed
        self.add_task(
            task_id="eow_report_saturday_fallback",
            func=self._on_eow_report,
            schedule_type=ScheduleType.CRON,
            hour=8,
            minute=0,
            day_of_week="sat",
            description="End-of-week P/L summary fallback (Saturday 08:00 ET)"
        )

        # Scheduler heartbeat — continuous liveness signal (every 1 min)
        self.add_task(
            task_id="scheduler_heartbeat",
            func=self._on_heartbeat,
            schedule_type=ScheduleType.INTERVAL,
            minutes=1,
            description="Scheduler liveness heartbeat"
        )

        # Interval-based data updates and risk checks (market-hours gated)
        self.schedule_data_update(self._data_update_interval)
        self.schedule_risk_check(self._risk_check_interval)

    # ==========================================================================
    # TASK MANAGEMENT
    # ==========================================================================
    def add_task(self, task_id: str, func: Callable,
                 schedule_type: ScheduleType,
                 name: str | None = None,
                 description: str | None = None,
                 enabled: bool = True,
                 **schedule_params) -> bool:
        """
        Add a scheduled task.

        Args:
            task_id: Unique task identifier
            func: Function to execute
            schedule_type: Type of scheduling
            name: Human-readable task name
            description: Task description
            enabled: Whether task is enabled
            **schedule_params: Schedule-specific parameters

        Returns:
            bool: True if task added successfully
        """
        try:
            with self._task_lock:
                # Check if task already exists
                if task_id in self.tasks:
                    self.logger.warning("Task %s already exists", task_id)
                    return False

                # Create task
                task = ScheduledTask(
                    task_id=task_id,
                    name=name or task_id,
                    func=func,
                    schedule_type=schedule_type,
                    schedule_params=schedule_params,
                    enabled=enabled,
                    metadata={'description': description}
                )

                # Add to scheduler if enabled
                if enabled:
                    job = self._create_job(task)
                    if job:
                        task.next_run = getattr(job, 'next_run_time', None)

                # Store task
                self.tasks[task_id] = task

                self.logger.info("Task added: %s", task_id)

                # Emit event
                self.event_manager.emit(
                    EventType.SYSTEM,
                    {
                        'type': 'task_added',
                        'task_id': task_id,
                        'schedule_type': schedule_type.name
                    }
                )

                return True

        except Exception as e:
            self.logger.error("Failed to add task %s: %s", task_id, e)
            self.error_handler.handle_error(e, f"add_task.{task_id}")
            return False

    def remove_task(self, task_id: str) -> bool:
        """
        Remove a scheduled task.

        Args:
            task_id: Task identifier

        Returns:
            bool: True if removed successfully
        """
        try:
            with self._task_lock:
                if task_id not in self.tasks:
                    self.logger.warning("Task %s not found", task_id)
                    return False

                # Remove from scheduler
                try:
                    self.scheduler.remove_job(task_id)
                except Exception as e:
                    self.logger.debug("Job %s may not exist in scheduler: %s", task_id, e)

                # Remove task
                del self.tasks[task_id]

                self.logger.info("Task removed: %s", task_id)
                return True

        except Exception as e:
            self.logger.error("Failed to remove task %s: %s", task_id, e)
            return False

    def enable_task(self, task_id: str) -> bool:
        """Enable a disabled task"""
        return self._set_task_enabled(task_id, True)

    def disable_task(self, task_id: str) -> bool:
        """Disable an enabled task"""
        return self._set_task_enabled(task_id, False)

    def _set_task_enabled(self, task_id: str, enabled: bool) -> bool:
        """Set task enabled state"""
        try:
            with self._task_lock:
                if task_id not in self.tasks:
                    return False

                task = self.tasks[task_id]

                if task.enabled == enabled:
                    return True  # Already in desired state

                task.enabled = enabled

                if enabled:
                    # Add to scheduler
                    job = self._create_job(task)
                    if job:
                        task.next_run = getattr(job, 'next_run_time', None)
                else:
                    # Remove from scheduler
                    try:
                        self.scheduler.remove_job(task_id)
                    except Exception as e:
                        self.logger.debug("Failed to remove job %s from scheduler: %s", task_id, e)

                self.logger.info("Task %s %s", task_id, 'enabled' if enabled else 'disabled')
                return True

        except Exception as e:
            self.logger.error("Failed to set task enabled state: %s", e)
            return False

    def get_task_status(self, task_id: str) -> dict[str, Any] | None:
        """Get task status information"""
        with self._task_lock:
            task = self.tasks.get(task_id)
            if not task:
                return None

            job = self.scheduler.get_job(task_id)

            return {
                'task_id': task_id,
                'name': task.name,
                'enabled': task.enabled,
                'schedule_type': task.schedule_type.name,
                'last_run': task.last_run,
                'next_run': getattr(job, 'next_run_time', None) if job else None,
                'run_count': task.run_count,
                'error_count': task.error_count,
                'is_running': job and job.pending
            }

    def list_tasks(self) -> list[dict[str, Any]]:
        """List all scheduled tasks"""
        with self._task_lock:
            return [
                self.get_task_status(task_id)
                for task_id in self.tasks
            ]

    # ==========================================================================
    # JOB CREATION
    # ==========================================================================
    def _create_job(self, task: ScheduledTask) -> Job | None:
        """Create APScheduler job from task"""
        try:
            # Wrap function for error handling
            wrapped_func = self._wrap_task_function(task)

            # Create trigger based on schedule type
            if task.schedule_type == ScheduleType.CRON:
                trigger = self._create_cron_trigger(task.schedule_params)
            elif task.schedule_type == ScheduleType.INTERVAL:
                trigger = self._create_interval_trigger(task.schedule_params)
            elif task.schedule_type == ScheduleType.DATE:
                trigger = self._create_date_trigger(task.schedule_params)
            elif task.schedule_type == ScheduleType.MARKET_BASED:
                trigger = self._create_market_trigger(task.schedule_params)
            else:
                self.logger.error("Unknown schedule type: %s", task.schedule_type)
                return None

            # Add job to scheduler
            job = self.scheduler.add_job(
                wrapped_func,
                trigger=trigger,
                id=task.task_id,
                name=task.name,
                max_instances=task.max_instances,
                misfire_grace_time=task.misfire_grace_time,
                coalesce=task.coalesce
            )

            return job

        except Exception as e:
            self.logger.error("Failed to create job: %s", e)
            return None

    def _wrap_task_function(self, task: ScheduledTask) -> Callable:
        """Wrap task function with error handling and metrics"""
        def wrapped():
            start_time = datetime.now(UTC)
            execution = TaskExecution(
                task_id=task.task_id,
                execution_time=start_time,
                status=TaskStatus.RUNNING
            )

            try:
                # Update task
                task.last_run = start_time
                task.run_count += 1

                # Execute function
                result = task.func()

                # Success
                execution.status = TaskStatus.SUCCESS
                execution.result = result

                # Update metrics
                self.metrics['tasks_executed'] += 1
                self.metrics['tasks_succeeded'] += 1

            except Exception as e:
                # Error
                execution.status = TaskStatus.ERROR
                execution.error_message = str(e)
                task.error_count += 1

                # Update metrics
                self.metrics['tasks_executed'] += 1
                self.metrics['tasks_failed'] += 1

                # Log error
                self.logger.error("Task %s failed: %s", task.task_id, e)
                self.logger.debug(traceback.format_exc())

            finally:
                # Calculate duration
                end_time = datetime.now(UTC)
                execution.duration_ms = int((end_time - start_time).total_seconds() * 1000)
                self.metrics['total_execution_time_ms'] += execution.duration_ms

                # Record execution
                self._record_task_execution(task.task_id, execution.status,
                                          execution.error_message, execution.duration_ms)

        return wrapped

    def _create_cron_trigger(self, params: dict[str, Any]) -> CronTrigger:
        """Create cron trigger from parameters"""
        return CronTrigger(**params, timezone=EASTERN_TZ)

    def _create_interval_trigger(self, params: dict[str, Any]) -> IntervalTrigger:
        """Create interval trigger from parameters"""
        return IntervalTrigger(**params, timezone=EASTERN_TZ)

    def _create_date_trigger(self, params: dict[str, Any]) -> DateTrigger:
        """Create date trigger from parameters"""
        run_date = params.get('run_date')
        if isinstance(run_date, str):
            run_date = datetime.fromisoformat(run_date)
        return DateTrigger(run_date=run_date, timezone=EASTERN_TZ)

    def _create_market_trigger(self, params: dict[str, Any]) -> CronTrigger | None:
        """Create market-based trigger"""
        # This is a simplified version - could be enhanced
        market_event = params.get('event', 'open')

        if market_event == 'open':
            return CronTrigger(hour=9, minute=30, day_of_week='mon-fri', timezone=EASTERN_TZ)
        elif market_event == 'close':
            return CronTrigger(hour=16, minute=0, day_of_week='mon-fri', timezone=EASTERN_TZ)
        else:
            return None

    # ==========================================================================
    # SCHEDULER EVENT HANDLERS
    # ==========================================================================
    def _on_job_executed(self, event: JobExecutionEvent):
        """Handle successful job execution"""
        try:
            task_id = event.job_id

            if task_id in self.tasks:
                # Update next run time
                job = self.scheduler.get_job(task_id)
                if job:
                    self.tasks[task_id].next_run = getattr(job, 'next_run_time', None)

            self.logger.debug("Job executed successfully: %s", task_id)

        except Exception as e:
            self.logger.error("Error handling job execution event: %s", e)

    def _on_job_error(self, event: JobEvent):
        """Handle job execution error"""
        try:
            task_id = event.job_id
            exception = getattr(event, 'exception', 'Unknown error')

            self.logger.error("Job failed: %s - %s", task_id, exception)

            # Emit error event
            self.event_manager.emit(
                EventType.SYSTEM_ERROR,
                {
                    'type': 'scheduled_task_error',
                    'task_id': task_id,
                    'error': str(exception)
                }
            )

        except Exception as e:
            self.logger.error("Error handling job error event: %s", e)

    def _on_job_missed(self, event: JobEvent):
        """Handle missed job execution"""
        try:
            task_id = event.job_id

            self.logger.warning("Job missed: %s", task_id)

            # Update metrics
            self.metrics['tasks_missed'] += 1

            # Record missed execution
            self._record_task_execution(task_id, TaskStatus.MISSED)

        except Exception as e:
            self.logger.error("Error handling job missed event: %s", e)

    # ==========================================================================
    # DEFAULT TASK HANDLERS
    # ==========================================================================
    def _on_market_open(self):
        """Handle market open event"""
        self.logger.info("Market opened - executing market open tasks")

        # Check if actually a trading day
        if not self.market_calendar.is_market_open():
            self.logger.warning("Market open event fired but market is closed")
            return

        # Emit market open event
        self.event_manager.emit(
            EventType.SYSTEM,
            {
                'type': 'market_open',
                'timestamp': datetime.now(EASTERN_TZ)
            }
        )

    def _on_market_close(self):
        """Handle market close event"""
        self.logger.info("Market closed - executing market close tasks")

        # Emit market close event
        self.event_manager.emit(
            EventType.SYSTEM,
            {
                'type': 'market_close',
                'timestamp': datetime.now(EASTERN_TZ)
            }
        )

    def _position_check_before_close(self):
        """Check positions before market close"""
        self.logger.info("Checking positions before market close")

        # Emit position check event
        self.event_manager.emit(
            EventType.RISK,
            {
                'type': 'position_check',
                'reason': 'market_close',
                'timestamp': datetime.now(EASTERN_TZ)
            }
        )

    def _on_broker_cutoff_flatten_guard(self):
        """Emit flatten request before broker at-risk cutoff with configured buffer."""
        now_et = datetime.now(EASTERN_TZ)
        self.logger.warning("Broker cutoff flatten guard triggered at %s", now_et.isoformat())

        self.event_manager.emit(
            EventType.FLATTEN_REQUEST,
            {
                'type': 'broker_cutoff_flatten_guard',
                'reason': 'broker_cutoff_protection',
                'timestamp': now_et,
                'details': {
                    'broker_cutoff_et': self.session_window_config.get('broker_cutoff_et', '16:00'),
                    'buffer_minutes': int(self.session_window_config.get('broker_cutoff_buffer_minutes', 10) or 10),
                },
            }
        )

    def _on_premarket_warmup(self):
        """Warm up data pipeline 30 minutes before market open"""
        self.logger.info("Pre-market data warmup triggered")
        self.event_manager.emit(
            EventType.SYSTEM,
            {
                'type': 'data_warmup_request',
                'timestamp': datetime.now(EASTERN_TZ)
            }
        )

    def _on_preflight_health_check(self):
        """Broker/API/risk validation 15 minutes before market open.

        Publishes a SYSTEM event and dispatches a preflight summary to
        Telegram so operators are notified of system readiness before the
        session starts.
        """
        self.logger.info("Pre-flight health check triggered")
        now_et = datetime.now(EASTERN_TZ)
        self.event_manager.emit(
            EventType.SYSTEM,
            {
                'type': 'preflight_health_check',
                'timestamp': now_et,
            }
        )
        # Dispatch Go/No-Go result to Telegram (best-effort; no crash on failure).
        try:
            self._dispatch_preflight_telegram(now_et)
        except Exception as exc:
            self.logger.warning("Preflight Telegram dispatch failed: %s", exc)

    def _dispatch_preflight_telegram(self, now_et: datetime) -> None:
        """Attempt to read the latest Go/No-Go result and send it via Telegram."""
        import json as _json
        from pathlib import Path as _Path

        project_root = _Path(__file__).resolve().parent.parent.parent
        reports_dir = project_root / "market_data" / "go_no_go_reports"
        date_str = now_et.strftime("%Y-%m-%d")

        go_no_go_status = "UNKNOWN"
        go_no_go_detail = "No Go/No-Go report found for today."

        if reports_dir.exists():
            day_reports = sorted(reports_dir.glob(f"go_no_go_{date_str}*.json"))
            if day_reports:
                try:
                    data = _json.loads(day_reports[-1].read_text(encoding="utf-8"))
                    go_no_go_status = str(data.get("status", "UNKNOWN")).upper()
                    checks = data.get("checks", {})
                    failed = [k for k, v in checks.items() if isinstance(v, dict) and not v.get("passed", True)]
                    go_no_go_detail = (
                        f"Checks passed: {len(checks) - len(failed)}/{len(checks)}"
                        + (f"\nFailed: {', '.join(failed)}" if failed else "")
                    )
                except Exception as exc:
                    self.logger.debug("Preflight Go/No-Go report parse error: %s", exc)

        icon = {"GO": "✅", "NO-GO": "🚫", "CONDITIONAL-GO": "⚠️"}.get(go_no_go_status, "🔔")
        msg = (
            f"{icon} <b>PREFLIGHT CHECK ({go_no_go_status})</b>\n"
            f"Time (ET): {now_et.strftime('%Y-%m-%d %H:%M')}\n"
            f"{go_no_go_detail}\n"
            "Session opens at 09:30 ET."
        )

        # Reach Telegram bot via event bus so we don't create a hard import cycle.
        self.event_manager.emit(
            EventType.SYSTEM,
            {
                "type": "telegram_send",
                "text": msg,
                "message": msg,
                "priority": "high",
                "source": "preflight_health_check",
            },
        )

    def _on_closing_range_risk_check(self):
        """Escalated risk check during the 3:30–4:00 PM closing range"""
        if not self.is_in_trading_window("closing_range"):
            return
        self.logger.info("Closing range risk check triggered")
        self.event_manager.emit(
            EventType.RISK,
            {
                'type': 'periodic_risk_check',
                'reason': 'closing_range',
                'timestamp': datetime.now(EASTERN_TZ)
            }
        )

    def _on_eod_report(self):
        """Trigger end-of-day report generation after fills settle post-close"""
        self.logger.info("EOD report generation triggered")
        self.event_manager.emit(
            EventType.SYSTEM,
            {
                'type': 'eod_report_request',
                'timestamp': datetime.now(EASTERN_TZ)
            }
        )
        # Stage 4 — also generate the structured EOD review (rejects, slippage,
        # policy blocks, overrides) so operators always have an auditable record.
        self._on_eod_review()

    def _on_eod_review(self) -> None:
        """Stage 4 — generate structured EOD review artifact via K02.

        Collects order rejects, slippage, policy blocks, and Go/No-Go overrides
        for the current trading day and persists to
        ``market_data/eod_reviews/eod_{date}.json``.
        """
        try:
            from Spyder.SpyderK_Reports.SpyderK02_DailyTradingReport import (
                create_daily_report_generator,
            )
            generator = create_daily_report_generator()
            review = generator.generate_eod_review()
            self.logger.info(
                "EOD review generated: rejects=%d slippage_avg=%.4f "
                "policy_blocks=%d overrides=%d",
                review.get("rejects", {}).get("count", 0),
                review.get("slippage", {}).get("avg_slippage", 0.0),
                len(review.get("policy_blocks", [])),
                len(review.get("overrides", [])),
            )
        except Exception as exc:
            self.logger.error("EOD review generation failed: %s", exc)

        # Generate supplementary daily artifacts.
        self._write_session_summary_artifact()
        self._write_pnl_drawdown_artifact()

    def _write_session_summary_artifact(self) -> None:
        """Write `market_data/session_summary_{date}.json` for the trading day."""
        import json as _json
        import tempfile
        from pathlib import Path as _Path

        now_et = datetime.now(EASTERN_TZ)
        date_str = now_et.strftime("%Y-%m-%d")
        project_root = _Path(__file__).resolve().parent.parent.parent
        out_dir = project_root / "market_data"
        out_path = out_dir / f"session_summary_{date_str}.json"

        try:
            from Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor import (
                get_session_supervisor,
            )
            supervisor = get_session_supervisor()
        except Exception:
            supervisor = None

        mode = os.environ.get("TRADING_MODE", "paper").upper()
        is_running = bool(supervisor and getattr(supervisor, "is_running", False))
        active_strategies: list[str] = []
        try:
            orchestrator = getattr(supervisor, "strategy_orchestrator", None) if supervisor else None
            if orchestrator and hasattr(orchestrator, "get_active_strategies"):
                active_strategies = list(orchestrator.get_active_strategies() or [])
        except Exception:
            pass

        payload = {
            "date": date_str,
            "mode": mode,
            "session_running": is_running,
            "active_strategies": active_strategies,
            "generated_at": now_et.isoformat(),
        }
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=out_dir, suffix=".tmp", delete=False
            ) as tmp:
                _json.dump(payload, tmp, indent=2)
                tmp_path = _Path(tmp.name)
            tmp_path.replace(out_path)
            self.logger.info("Session summary artifact saved: %s", out_path)
        except Exception as exc:
            self.logger.error("Failed to write session summary artifact: %s", exc)

    def _write_pnl_drawdown_artifact(self) -> None:
        """Write `market_data/pnl_and_drawdown_{date}.json` at EOD."""
        import json as _json
        import tempfile
        from pathlib import Path as _Path

        now_et = datetime.now(EASTERN_TZ)
        date_str = now_et.strftime("%Y-%m-%d")
        project_root = _Path(__file__).resolve().parent.parent.parent
        out_dir = project_root / "market_data"
        out_path = out_dir / f"pnl_and_drawdown_{date_str}.json"

        realized_pl = 0.0
        unrealized_pl = 0.0
        max_drawdown = 0.0
        try:
            from Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor import (
                get_session_supervisor,
            )
            supervisor = get_session_supervisor()
            risk = getattr(supervisor, "risk", None) if supervisor else None
            if risk is not None:
                realized_pl = float(getattr(risk, "daily_pnl", 0.0) or 0.0)
                max_drawdown = float(getattr(risk, "max_intraday_drawdown", 0.0) or 0.0)
        except Exception:
            pass

        payload = {
            "date": date_str,
            "realized_pl_day": realized_pl,
            "unrealized_carry": unrealized_pl,
            "net_pl_day": realized_pl + unrealized_pl,
            "max_intraday_drawdown": max_drawdown,
            "generated_at": now_et.isoformat(),
        }
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=out_dir, suffix=".tmp", delete=False
            ) as tmp:
                _json.dump(payload, tmp, indent=2)
                tmp_path = _Path(tmp.name)
            tmp_path.replace(out_path)
            self.logger.info("P&L+drawdown artifact saved: %s", out_path)
        except Exception as exc:
            self.logger.error("Failed to write P&L/drawdown artifact: %s", exc)

    def _on_eow_report(self) -> None:
        """End-of-week summary: trigger Telegram EOW dispatch + weekly ops report."""
        self.logger.info("EOW report task triggered")
        now_et = datetime.now(EASTERN_TZ)

        # Emit event so Telegram bot (listening for telegram_send or eow events)
        # can also trigger from an external scheduler if needed.
        week_key = now_et.strftime("%G-W%V")
        self.event_manager.emit(
            EventType.SYSTEM,
            {
                "type": "eow_report_request",
                "week_key": week_key,
                "timestamp": now_et,
            },
        )

        # Generate the weekly ops report Markdown artifact.
        try:
            from Spyder.SpyderK_Reports.SpyderK02_DailyTradingReport import (
                create_daily_report_generator,
            )
            generator = create_daily_report_generator()
            generator.generate_weekly_ops_report(week_key)
        except Exception as exc:
            self.logger.error("Weekly ops report generation failed: %s", exc)

    def _on_heartbeat(self):
        """Scheduler liveness heartbeat — runs every minute for external monitoring"""
        self.logger.debug("Scheduler heartbeat")
        self.metrics['last_heartbeat'] = datetime.now(EASTERN_TZ).isoformat()

    def _on_event_clock_tick(self):
        """Periodic event-clock state publication for blackout enforcement."""
        try:
            if not self.event_clock_config.get('enabled', True):
                return
            self.publish_event_clock_state()
        except Exception as e:
            self.logger.error("Event-clock tick failed: %s", e)

    def _daily_cleanup(self):
        """Perform daily cleanup tasks"""
        self.logger.info("Running daily cleanup")

        try:
            # Clean old task history
            self._clean_old_task_history()

            # Reset daily metrics
            self._reset_daily_metrics()

            # Emit cleanup event
            self.event_manager.emit(
                EventType.SYSTEM,
                {
                    'type': 'daily_cleanup',
                    'timestamp': datetime.now(UTC)
                }
            )

        except Exception as e:
            self.logger.error("Daily cleanup failed: %s", e)

    # ==========================================================================
    # TRADING WINDOW MANAGEMENT
    # ==========================================================================
    def add_trading_window(self, name: str, start_time: time,
                          end_time: time, **kwargs) -> bool:
        """Add a trading window"""
        try:
            window = TradingWindow(
                name=name,
                start_time=start_time,
                end_time=end_time,
                **kwargs
            )

            self.trading_windows[name] = window

            # Schedule window events
            self._schedule_window_events(name)

            self.logger.info("Trading window added: %s", name)
            return True

        except Exception as e:
            self.logger.error("Failed to add trading window: %s", e)
            return False

    def _schedule_window_events(self, window_name: str):
        """Schedule events for trading window"""
        window = self.trading_windows.get(window_name)
        if not window or not window.enabled:
            return

        # Schedule window open
        self.add_task(
            task_id=f"window_open_{window_name}",
            func=lambda: self._on_window_event(window_name, "open"),
            schedule_type=ScheduleType.CRON,
            hour=window.start_time.hour,
            minute=window.start_time.minute,
            day_of_week='mon-fri',
            description=f"Trading window open: {window_name}"
        )

        # Schedule window close
        self.add_task(
            task_id=f"window_close_{window_name}",
            func=lambda: self._on_window_event(window_name, "close"),
            schedule_type=ScheduleType.CRON,
            hour=window.end_time.hour,
            minute=window.end_time.minute,
            day_of_week='mon-fri',
            description=f"Trading window close: {window_name}"
        )

    def _on_window_event(self, window_name: str, event_type: str):
        """Handle trading window event"""
        self.logger.info("Trading window %s: %s", event_type, window_name)

        window = self.trading_windows.get(window_name)
        if not window:
            return

        # Emit window event
        self.event_manager.emit(
            EventType.TRADING,
            {
                'type': f'trading_window_{event_type}',
                'window': window_name,
                'strategies': window.strategies,
                'timestamp': datetime.now(EASTERN_TZ)
            }
        )

    def is_in_trading_window(self, window_name: str,
                           dt: datetime | None = None) -> bool:
        """Check if currently in trading window"""
        window = self.trading_windows.get(window_name)
        if not window or not window.enabled:
            return False

        if dt is None:
            dt = datetime.now(EASTERN_TZ)
        else:
            dt = dt.astimezone(EASTERN_TZ)

        # Check day of week
        if dt.weekday() not in window.days_of_week:
            return False

        # Check time
        current_time = dt.time()
        return window.start_time <= current_time <= window.end_time

    # ==========================================================================
    # CONVENIENCE METHODS
    # ==========================================================================
    def schedule_strategy_execution(self, strategy_name: str,
                                  execution_time: time,
                                  days_of_week: str = "mon-fri") -> bool:
        """Schedule a strategy to run at specific time"""
        task_id = f"strategy_{strategy_name}"

        def execute_strategy():
            self.event_manager.emit(
                EventType.TRADING,
                {
                    'type': 'execute_strategy',
                    'strategy': strategy_name,
                    'timestamp': datetime.now(EASTERN_TZ)
                }
            )

        return self.add_task(
            task_id=task_id,
            func=execute_strategy,
            schedule_type=ScheduleType.CRON,
            hour=execution_time.hour,
            minute=execution_time.minute,
            day_of_week=days_of_week,
            description=f"Execute {strategy_name} strategy"
        )

    def schedule_data_update(self, interval_minutes: int = 5) -> bool:
        """Schedule periodic data updates (only fires during regular market hours)"""
        def update_data():
            if not self.is_in_trading_window("regular_market"):
                return
            self.event_manager.emit(
                EventType.SYSTEM,
                {
                    'type': 'data_update_request',
                    'timestamp': datetime.now(UTC)
                }
            )

        return self.add_task(
            task_id="data_update",
            func=update_data,
            schedule_type=ScheduleType.INTERVAL,
            minutes=interval_minutes,
            description="Periodic data update"
        )

    def schedule_risk_check(self, interval_minutes: int = 15) -> bool:
        """Schedule periodic risk checks (only fires during regular market hours)"""
        def check_risk():
            if not self.is_in_trading_window("regular_market"):
                return
            self.event_manager.emit(
                EventType.RISK,
                {
                    'type': 'periodic_risk_check',
                    'timestamp': datetime.now(UTC)
                }
            )

        return self.add_task(
            task_id="risk_check",
            func=check_risk,
            schedule_type=ScheduleType.INTERVAL,
            minutes=interval_minutes,
            description="Periodic risk check"
        )

    # ==========================================================================
    # EVENT CLOCK (P0-3)
    # ==========================================================================
    def _load_event_calendar_file(self, calendar_path: str | None) -> None:
        """Load a static event-calendar file for blackout enforcement."""
        if not calendar_path:
            return

        path = Path(calendar_path)
        if not path.is_absolute():
            path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))) / path

        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
            events = data.get("events") if isinstance(data, dict) else data
            if isinstance(events, list):
                self.set_event_clock_events(events)
        except Exception as exc:
            self.logger.warning("Event-clock calendar load failed (%s): %s", path, exc)
    def set_event_clock_events(self, events: list[dict[str, Any]]) -> None:
        """Set high-impact calendar events used by event-clock state logic.

        Event item schema:
            {
                "event_id": str,
                "event_type": str,
                "importance": "high|medium|low",
                "event_time_et": datetime | ISO string,
                "source": str,
            }
        """
        normalized: list[dict[str, Any]] = []
        for raw in events:
            item = dict(raw)
            event_time = item.get('event_time_et')
            if isinstance(event_time, str):
                try:
                    parsed = datetime.fromisoformat(event_time)
                    if parsed.tzinfo is None:
                        parsed = EASTERN_TZ.localize(parsed)
                    else:
                        parsed = parsed.astimezone(EASTERN_TZ)
                    item['event_time_et'] = parsed
                except Exception:
                    continue
            elif isinstance(event_time, datetime):
                if event_time.tzinfo is None:
                    item['event_time_et'] = EASTERN_TZ.localize(event_time)
                else:
                    item['event_time_et'] = event_time.astimezone(EASTERN_TZ)
            else:
                continue
            normalized.append(item)

        self._event_calendar_events = normalized
        self.logger.info("Event-clock calendar loaded: %s events", len(normalized))

    def set_event_clock_manual_state(self, state_payload: dict[str, Any] | None) -> None:
        """Set an optional manual event-clock override payload.

        Expected payload keys:
            {
                "state": "pre|live|post|clear",
                "event_id": str,
                "event_type": str,
                "allowed_strategies": list[str],
                "max_size_multiplier": float,
            }
        """
        if not state_payload:
            self._event_clock_manual_state = None
            return

        state = str(state_payload.get("state", "clear")).lower()
        if state not in {"pre", "live", "post", "clear"}:
            state = "clear"

        allowlist = state_payload.get("allowed_strategies", [])
        if not isinstance(allowlist, list):
            allowlist = []

        max_mult = state_payload.get(
            "max_size_multiplier",
            self.event_clock_config.get("max_size_multiplier", 0.25),
        )

        self._event_clock_manual_state = {
            "state": state,
            "event_id": state_payload.get("event_id"),
            "event_type": state_payload.get("event_type"),
            "allowed_strategies": [
                s.strip() for s in allowlist if isinstance(s, str) and s.strip()
            ],
            "max_size_multiplier": float(max_mult),
            "source": "manual",
        }

    def _evaluate_event_clock_state(self, now_et: datetime) -> dict[str, Any]:
        """Evaluate pre/live/post blackout state against configured events."""
        if not bool(self.event_clock_config.get("enabled", True)):
            return {
                "state": "clear",
                "event": None,
                "blackout_pre_minutes": int(self.event_clock_config.get("blackout_pre_minutes", 30)),  # noqa: E501
                "blackout_post_minutes": int(self.event_clock_config.get("blackout_post_minutes", 30)),  # noqa: E501
                "allowlist_strategies": list(self.event_clock_config.get("allowlist_strategies", [])),  # noqa: E501
                "max_size_multiplier": float(self.event_clock_config.get("max_size_multiplier", 0.25)),  # noqa: E501
                "source": "disabled",
            }

        pre_mins = int(self.event_clock_config.get('blackout_pre_minutes', 30))
        post_mins = int(self.event_clock_config.get('blackout_post_minutes', 30))
        high_only = bool(self.event_clock_config.get('high_impact_only', True))
        sources = str(self.event_clock_config.get("sources", "calendar+manual")).lower()
        use_calendar = "calendar" in sources
        use_manual = "manual" in sources

        if use_manual and isinstance(self._event_clock_manual_state, dict):
            manual_state = str(self._event_clock_manual_state.get("state", "clear")).lower()
            if manual_state in {"pre", "live", "post"}:
                return {
                    "state": manual_state,
                    "event": {
                        "event_id": self._event_clock_manual_state.get("event_id"),
                        "event_type": self._event_clock_manual_state.get("event_type"),
                        "importance": "manual",
                        "source": "manual",
                        "event_time_et": now_et,
                    },
                    "blackout_pre_minutes": pre_mins,
                    "blackout_post_minutes": post_mins,
                    "allowlist_strategies": list(self._event_clock_manual_state.get("allowed_strategies", [])),  # noqa: E501
                    "max_size_multiplier": float(
                        self._event_clock_manual_state.get(
                            "max_size_multiplier",
                            self.event_clock_config.get("max_size_multiplier", 0.25),
                        )
                    ),
                    "source": "manual",
                }

        active_state = 'clear'
        active_event: dict[str, Any] | None = None

        if use_calendar:
            for item in self._event_calendar_events:
                if high_only and str(item.get('importance', 'high')).lower() != 'high':
                    continue
                evt_time = item.get('event_time_et')
                if not isinstance(evt_time, datetime):
                    continue

                pre_start = evt_time - timedelta(minutes=pre_mins)
                post_end = evt_time + timedelta(minutes=post_mins)

                if pre_start <= now_et < evt_time:
                    active_state = 'pre'
                    active_event = item
                    break
                if now_et == evt_time:
                    active_state = 'live'
                    active_event = item
                    break
                if evt_time <= now_et <= post_end:
                    active_state = 'post'
                    active_event = item
                    break

        return {
            'state': active_state,
            'event': active_event,
            'blackout_pre_minutes': pre_mins,
            'blackout_post_minutes': post_mins,
            'allowlist_strategies': list(self.event_clock_config.get('allowlist_strategies', [])),
            'max_size_multiplier': float(self.event_clock_config.get('max_size_multiplier', 0.25)),
            'source': 'calendar' if use_calendar else 'manual',
        }

    def publish_event_clock_state(self, now: datetime | None = None, force_emit: bool = False) -> dict[str, Any]:  # noqa: E501
        """Publish unified event-clock feed envelope and return it."""
        now_et = (now or datetime.now(EASTERN_TZ)).astimezone(EASTERN_TZ)
        state = self._evaluate_event_clock_state(now_et)

        event = state.get('event') or {}
        payload = {
            'feed': 'event_clock',
            'version': '1.0',
            'mode': 'scheduler',
            'session_id': 'scheduler',
            'published_ts': now_et.isoformat(),
            'data': {
                'event_id': event.get('event_id'),
                'event_type': event.get('event_type'),
                'importance': event.get('importance'),
                'source': event.get('source', 'calendar'),
                'event_time_et': event.get('event_time_et').isoformat() if isinstance(event.get('event_time_et'), datetime) else None,  # noqa: E501
                'blackout_pre_minutes': state['blackout_pre_minutes'],
                'blackout_post_minutes': state['blackout_post_minutes'],
                'state': state['state'],
                'enabled': bool(self.event_clock_config.get('enabled', True)),
                'sources': str(self.event_clock_config.get('sources', 'calendar+manual')),
                'allowed_strategies': state['allowlist_strategies'],
                'max_size_multiplier': state['max_size_multiplier'],
                'published_ts': now_et.isoformat(),
            },
        }

        should_emit = force_emit or (state['state'] != self._last_event_clock_state)
        if should_emit:
            self.event_manager.emit(
                EventType.RISK,
                {
                    'type': 'event_clock_state',
                    'payload': payload,
                    'timestamp': now_et,
                },
            )
            self._last_event_clock_state = state['state']

        return payload

    # ==========================================================================
    # TASK HISTORY
    # ==========================================================================
    def _record_task_execution(self, task_id: str, status: TaskStatus,
                             error_message: str | None = None,
                             duration_ms: int | None = None):
        """Record task execution in database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO task_history
                    (task_id, execution_time, status, duration_ms, error_message)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    task_id,
                    datetime.now(UTC),
                    status.value,
                    duration_ms,
                    error_message
                ))

        except Exception as e:
            self.logger.error("Failed to record task execution: %s", e)

    def get_task_history(self, task_id: str | None = None,
                        limit: int = 100) -> list[TaskExecution]:
        """Get task execution history"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if task_id:
                    query = """
                        SELECT task_id, execution_time, status, duration_ms, error_message
                        FROM task_history
                        WHERE task_id = ?
                        ORDER BY execution_time DESC
                        LIMIT ?
                    """
                    params = (task_id, limit)
                else:
                    query = """
                        SELECT task_id, execution_time, status, duration_ms, error_message
                        FROM task_history
                        ORDER BY execution_time DESC
                        LIMIT ?
                    """
                    params = (limit,)

                cursor = conn.execute(query, params)

                history = []
                for row in cursor:
                    history.append(TaskExecution(
                        task_id=row[0],
                        execution_time=datetime.fromisoformat(row[1]),
                        status=TaskStatus(row[2]),
                        duration_ms=row[3],
                        error_message=row[4]
                    ))

                return history

        except Exception as e:
            self.logger.error("Failed to get task history: %s", e)
            return []

    def _clean_old_task_history(self, days_to_keep: int = 30):
        """Clean old task history records"""
        try:
            cutoff_date = datetime.now(UTC) - timedelta(days=days_to_keep)

            with sqlite3.connect(self.db_path) as conn:
                result = conn.execute("""
                    DELETE FROM task_history
                    WHERE execution_time < ?
                """, (cutoff_date,))

                deleted = result.rowcount
                if deleted > 0:
                    self.logger.info("Cleaned %s old task history records", deleted)

        except Exception as e:
            self.logger.error("Failed to clean task history: %s", e)

    def get_task_statistics(self, task_id: str | None = None,
                          days: int = 7) -> dict[str, Any]:
        """Get task execution statistics"""
        try:
            since_date = datetime.now(UTC) - timedelta(days=days)

            with sqlite3.connect(self.db_path) as conn:
                if task_id:
                    query = """
                        SELECT
                            COUNT(*) as total,
                            SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success,
                            SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as error,
                            SUM(CASE WHEN status = 'missed' THEN 1 ELSE 0 END) as missed,
                            AVG(CASE WHEN duration_ms IS NOT NULL THEN duration_ms ELSE NULL END) as avg_duration,
                            MAX(duration_ms) as max_duration,
                            MIN(duration_ms) as min_duration
                        FROM task_history
                        WHERE task_id = ? AND execution_time >= ?
                    """  # noqa: E501
                    params = (task_id, since_date)
                else:
                    query = """
                        SELECT
                            COUNT(*) as total,
                            SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success,
                            SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as error,
                            SUM(CASE WHEN status = 'missed' THEN 1 ELSE 0 END) as missed,
                            AVG(CASE WHEN duration_ms IS NOT NULL THEN duration_ms ELSE NULL END) as avg_duration,
                            MAX(duration_ms) as max_duration,
                            MIN(duration_ms) as min_duration
                        FROM task_history
                        WHERE execution_time >= ?
                    """  # noqa: E501
                    params = (since_date,)

                cursor = conn.execute(query, params)
                row = cursor.fetchone()

                return {
                    'total_executions': row[0] or 0,
                    'successful': row[1] or 0,
                    'errors': row[2] or 0,
                    'missed': row[3] or 0,
                    'success_rate': (row[1] / row[0] * 100) if row[0] > 0 else 0,
                    'avg_duration_ms': row[4] or 0,
                    'max_duration_ms': row[5] or 0,
                    'min_duration_ms': row[6] or 0,
                    'period_days': days
                }

        except Exception as e:
            self.logger.error("Failed to get task statistics: %s", e)
            return {}

    # ==========================================================================
    # LIFECYCLE MANAGEMENT
    # ==========================================================================
    def start(self) -> bool:
        """Start the scheduler"""
        try:
            if self.scheduler.running:
                self.logger.warning("Scheduler already running")
                return True

            self.scheduler.start()
            self.logger.info("Scheduler started")

            # Emit start event
            self.event_manager.emit(
                EventType.SYSTEM,
                {
                    'type': 'scheduler_started',
                    'timestamp': datetime.now(UTC),
                    'task_count': len(self.tasks)
                }
            )

            return True

        except Exception as e:
            self.logger.error("Failed to start scheduler: %s", e)
            self.error_handler.handle_error(e, "scheduler_start")
            return False

    def stop(self, wait: bool = True) -> bool:
        """
        Stop the scheduler.

        Args:
            wait: Wait for running jobs to complete

        Returns:
            bool: True if stopped successfully
        """
        try:
            if not self.scheduler.running:
                self.logger.warning("Scheduler not running")
                return True

            self.scheduler.shutdown(wait=wait)
            self.logger.info("Scheduler stopped")

            # Emit stop event
            self.event_manager.emit(
                EventType.SYSTEM,
                {
                    'type': 'scheduler_stopped',
                    'timestamp': datetime.now(UTC)
                }
            )

            return True

        except Exception as e:
            self.logger.error("Failed to stop scheduler: %s", e)
            return False

    def pause(self) -> bool:
        """Pause all scheduled jobs"""
        try:
            self.scheduler.pause()
            self.logger.info("Scheduler paused")
            return True
        except Exception as e:
            self.logger.error("Failed to pause scheduler: %s", e)
            return False

    def resume(self) -> bool:
        """Resume all scheduled jobs"""
        try:
            self.scheduler.resume()
            self.logger.info("Scheduler resumed")
            return True
        except Exception as e:
            self.logger.error("Failed to resume scheduler: %s", e)
            return False

    def is_running(self) -> bool:
        """Check if scheduler is running"""
        return self.scheduler.running

    # ==========================================================================
    # UTILITIES
    # ==========================================================================
    def _reset_daily_metrics(self):
        """Reset daily performance metrics"""
        # This could be enhanced to store historical metrics
        daily_metrics = {
            'date': date.today(),
            'tasks_executed': self.metrics['tasks_executed'],
            'tasks_succeeded': self.metrics['tasks_succeeded'],
            'tasks_failed': self.metrics['tasks_failed'],
            'tasks_missed': self.metrics['tasks_missed'],
            'avg_execution_time_ms': (
                self.metrics['total_execution_time_ms'] / self.metrics['tasks_executed']
                if self.metrics['tasks_executed'] > 0 else 0
            )
        }

        # Log daily summary
        self.logger.info("Daily task summary: %s", daily_metrics)

        # Reset counters
        self.metrics = {
            'tasks_executed': 0,
            'tasks_succeeded': 0,
            'tasks_failed': 0,
            'tasks_missed': 0,
            'total_execution_time_ms': 0
        }

    def get_metrics(self) -> dict[str, Any]:
        """Get current scheduler metrics"""
        return {
            'is_running': self.scheduler.running,
            'total_tasks': len(self.tasks),
            'enabled_tasks': len([t for t in self.tasks.values() if t.enabled]),
            'running_jobs': len(self.scheduler.get_jobs()),
            'performance': self.metrics.copy(),
            'next_scheduled': self._get_next_scheduled_time()
        }

    def _get_next_scheduled_time(self) -> datetime | None:
        """Get time of next scheduled job"""
        jobs = self.scheduler.get_jobs()
        if not jobs:
            return None

        next_times = [getattr(job, 'next_run_time', None) for job in jobs if getattr(job, 'next_run_time', None)]  # noqa: E501
        return min(next_times) if next_times else None

    def print_schedule(self):
        """Print current schedule to console"""
        logging.info("\n" + "="*80)
        logging.info("SCHEDULED TASKS")
        logging.info("="*80)

        jobs = sorted(self.scheduler.get_jobs(), key=lambda x: x.next_run_time or datetime.max)

        for job in jobs:
            task = self.tasks.get(job.id)
            if task:
                logging.info("\nTask: %s", task.name)
                logging.info("  ID: %s", job.id)
                logging.info("  Type: %s", task.schedule_type.name)
                logging.info("  Next Run: %s", getattr(job, 'next_run_time', None))
                logging.info("  Enabled: %s", task.enabled)
                logging.info("  Run Count: %s", task.run_count)
                logging.info("  Error Count: %s", task.error_count)

                if task.last_run:
                    logging.info("  Last Run: %s", task.last_run)

        logging.info("\n" + "="*80)

    def export_schedule(self, output_path: Path) -> bool:
        """Export schedule to file"""
        try:
            schedule_data = {
                'export_time': datetime.now(UTC).isoformat(),
                'scheduler_running': self.scheduler.running,
                'tasks': []
            }

            for task_id, task in self.tasks.items():
                job = self.scheduler.get_job(task_id)

                task_data = {
                    'task_id': task_id,
                    'name': task.name,
                    'schedule_type': task.schedule_type.name,
                    'schedule_params': task.schedule_params,
                    'enabled': task.enabled,
                    'next_run': getattr(job, 'next_run_time', None).isoformat() if job and getattr(job, 'next_run_time', None) else None,  # noqa: E501
                    'last_run': task.last_run.isoformat() if task.last_run else None,
                    'run_count': task.run_count,
                    'error_count': task.error_count,
                    'metadata': task.metadata
                }

                schedule_data['tasks'].append(task_data)

            with open(output_path, 'w') as f:
                json.dump(schedule_data, f, indent=2)

            self.logger.info("Schedule exported to: %s", output_path)
            return True

        except Exception as e:
            self.logger.error("Failed to export schedule: %s", e)
            return False

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
_scheduler_instance: Scheduler | None = None
_scheduler_lock = threading.Lock()

def get_scheduler(event_manager: EventManager = None) -> Scheduler:
    """
    Get singleton Scheduler instance.

    Args:
        event_manager: Event manager (required for first call)

    Returns:
        Scheduler instance
    """
    global _scheduler_instance

    with _scheduler_lock:
        if _scheduler_instance is None:
            if not event_manager:
                raise ValueError("Event manager required for first scheduler creation")
            _scheduler_instance = Scheduler(event_manager)

        return _scheduler_instance

def reset_scheduler():
    """Reset the singleton instance (for testing)"""
    global _scheduler_instance
    with _scheduler_lock:
        if _scheduler_instance and _scheduler_instance.is_running():
            _scheduler_instance.stop()
        _scheduler_instance = None

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing

    # Create event manager
    from SpyderA_Core.SpyderA05_EventManager import EventManager
    event_manager = EventManager()
    event_manager.start()

    # Create scheduler
    scheduler = Scheduler(event_manager)

    # Test task addition

    # Add interval task
    def test_interval_task():
        pass

    scheduler.add_task(
        task_id="test_interval",
        func=test_interval_task,
        schedule_type=ScheduleType.INTERVAL,
        seconds=10,
        description="Test interval task"
    )

    # Add cron task
    def test_cron_task():
        pass

    scheduler.add_task(
        task_id="test_cron",
        func=test_cron_task,
        schedule_type=ScheduleType.CRON,
        second="*/30",  # Every 30 seconds
        description="Test cron task"
    )

    # Start scheduler
    if scheduler.start():

        # Print schedule
        scheduler.print_schedule()

        # Get metrics
        metrics = scheduler.get_metrics()

        # Test market calendar
        calendar = scheduler.market_calendar

        today = date.today()

        next_trading = calendar.get_next_trading_day()

        # Test trading windows
        for name, _window in scheduler.trading_windows.items():
            in_window = scheduler.is_in_trading_window(name)

        # Run for a bit
        import time
        time.sleep(30)

        # Get task history
        history = scheduler.get_task_history(limit=10)
        for _execution in history:
            pass

        # Stop scheduler
        if scheduler.stop():
            pass
    else:
        pass

    # Stop event manager
    event_manager.stop()

