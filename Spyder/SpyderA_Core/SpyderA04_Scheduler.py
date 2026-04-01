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
from datetime import datetime, time, timedelta, date
from typing import Callable, Any
from dataclasses import dataclass, field
from enum import Enum, auto
import logging
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
    created_at: datetime = field(default_factory=datetime.now)
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
            "new_years_eve": time(13, 0) if datetime.now().year >= 2025 else time(16, 0)
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

        # Market calendar
        self.market_calendar = MarketCalendar()

        # Task history database
        self.db_path = Path.home() / ".spyder" / "scheduler.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

        # Performance metrics
        self.metrics = {
            'tasks_executed': 0,
            'tasks_succeeded': 0,
            'tasks_failed': 0,
            'tasks_missed': 0,
            'total_execution_time_ms': 0
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
            self.logger.error(f"Database initialization failed: {e}")

    def _init_default_windows(self):
        """Initialize default trading windows"""
        # Regular market hours window
        self.trading_windows["regular_market"] = TradingWindow(
            name="Regular Market Hours",
            start_time=time(9, 30),
            end_time=time(16, 0),
            enabled=True
        )

        # Opening range window
        self.trading_windows["opening_range"] = TradingWindow(
            name="Opening Range",
            start_time=time(9, 30),
            end_time=time(10, 0),
            enabled=True
        )

        # Closing range window
        self.trading_windows["closing_range"] = TradingWindow(
            name="Closing Range",
            start_time=time(15, 30),
            end_time=time(16, 0),
            enabled=True
        )

        # Pre-market window
        self.trading_windows["premarket"] = TradingWindow(
            name="Pre-Market",
            start_time=time(7, 0),
            end_time=time(9, 30),
            enabled=False
        )

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

    def _schedule_default_tasks(self):
        """Schedule default system tasks"""
        # Market open/close events
        self.add_task(
            task_id="market_open",
            func=self._on_market_open,
            schedule_type=ScheduleType.CRON,
            hour=9,
            minute=30,
            day_of_week="mon-fri",
            description="Market open event"
        )

        self.add_task(
            task_id="market_close",
            func=self._on_market_close,
            schedule_type=ScheduleType.CRON,
            hour=16,
            minute=0,
            day_of_week="mon-fri",
            description="Market close event"
        )

        # Position check before close
        self.add_task(
            task_id="position_check_before_close",
            func=self._position_check_before_close,
            schedule_type=ScheduleType.CRON,
            hour=15,
            minute=45,
            day_of_week="mon-fri",
            description="Check positions before market close"
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
                    self.logger.warning(f"Task {task_id} already exists")
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
                        task.next_run = job.next_run_time

                # Store task
                self.tasks[task_id] = task

                self.logger.info(f"Task added: {task_id}")

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
            self.logger.error(f"Failed to add task {task_id}: {e}")
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
                    self.logger.warning(f"Task {task_id} not found")
                    return False

                # Remove from scheduler
                try:
                    self.scheduler.remove_job(task_id)
                except Exception as e:
                    self.logger.debug(f"Job {task_id} may not exist in scheduler: {e}")

                # Remove task
                del self.tasks[task_id]

                self.logger.info(f"Task removed: {task_id}")
                return True

        except Exception as e:
            self.logger.error(f"Failed to remove task {task_id}: {e}")
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
                        task.next_run = job.next_run_time
                else:
                    # Remove from scheduler
                    try:
                        self.scheduler.remove_job(task_id)
                    except Exception as e:
                        self.logger.debug(f"Failed to remove job {task_id} from scheduler: {e}")

                self.logger.info(f"Task {task_id} {'enabled' if enabled else 'disabled'}")
                return True

        except Exception as e:
            self.logger.error(f"Failed to set task enabled state: {e}")
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
                'next_run': job.next_run_time if job else None,
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
                self.logger.error(f"Unknown schedule type: {task.schedule_type}")
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
            self.logger.error(f"Failed to create job: {e}")
            return None

    def _wrap_task_function(self, task: ScheduledTask) -> Callable:
        """Wrap task function with error handling and metrics"""
        def wrapped():
            start_time = datetime.now()
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
                self.logger.error(f"Task {task.task_id} failed: {e}")
                self.logger.debug(traceback.format_exc())

            finally:
                # Calculate duration
                end_time = datetime.now()
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
                    self.tasks[task_id].next_run = job.next_run_time

            self.logger.debug(f"Job executed successfully: {task_id}")

        except Exception as e:
            self.logger.error(f"Error handling job execution event: {e}")

    def _on_job_error(self, event: JobEvent):
        """Handle job execution error"""
        try:
            task_id = event.job_id
            exception = getattr(event, 'exception', 'Unknown error')

            self.logger.error(f"Job failed: {task_id} - {exception}")

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
            self.logger.error(f"Error handling job error event: {e}")

    def _on_job_missed(self, event: JobEvent):
        """Handle missed job execution"""
        try:
            task_id = event.job_id

            self.logger.warning(f"Job missed: {task_id}")

            # Update metrics
            self.metrics['tasks_missed'] += 1

            # Record missed execution
            self._record_task_execution(task_id, TaskStatus.MISSED)

        except Exception as e:
            self.logger.error(f"Error handling job missed event: {e}")

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
                    'timestamp': datetime.now()
                }
            )

        except Exception as e:
            self.logger.error(f"Daily cleanup failed: {e}")

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

            self.logger.info(f"Trading window added: {name}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to add trading window: {e}")
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
        self.logger.info(f"Trading window {event_type}: {window_name}")

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
        """Schedule periodic data updates"""
        def update_data():
            self.event_manager.emit(
                EventType.SYSTEM,
                {
                    'type': 'data_update_request',
                    'timestamp': datetime.now()
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
        """Schedule periodic risk checks"""
        def check_risk():
            self.event_manager.emit(
                EventType.RISK,
                {
                    'type': 'periodic_risk_check',
                    'timestamp': datetime.now()
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
                    datetime.now(),
                    status.value,
                    duration_ms,
                    error_message
                ))

        except Exception as e:
            self.logger.error(f"Failed to record task execution: {e}")

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
            self.logger.error(f"Failed to get task history: {e}")
            return []

    def _clean_old_task_history(self, days_to_keep: int = 30):
        """Clean old task history records"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)

            with sqlite3.connect(self.db_path) as conn:
                result = conn.execute("""
                    DELETE FROM task_history
                    WHERE execution_time < ?
                """, (cutoff_date,))

                deleted = result.rowcount
                if deleted > 0:
                    self.logger.info(f"Cleaned {deleted} old task history records")

        except Exception as e:
            self.logger.error(f"Failed to clean task history: {e}")

    def get_task_statistics(self, task_id: str | None = None,
                          days: int = 7) -> dict[str, Any]:
        """Get task execution statistics"""
        try:
            since_date = datetime.now() - timedelta(days=days)

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
                    """
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
                    """
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
            self.logger.error(f"Failed to get task statistics: {e}")
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
                    'timestamp': datetime.now(),
                    'task_count': len(self.tasks)
                }
            )

            return True

        except Exception as e:
            self.logger.error(f"Failed to start scheduler: {e}")
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
                    'timestamp': datetime.now()
                }
            )

            return True

        except Exception as e:
            self.logger.error(f"Failed to stop scheduler: {e}")
            return False

    def pause(self) -> bool:
        """Pause all scheduled jobs"""
        try:
            self.scheduler.pause()
            self.logger.info("Scheduler paused")
            return True
        except Exception as e:
            self.logger.error(f"Failed to pause scheduler: {e}")
            return False

    def resume(self) -> bool:
        """Resume all scheduled jobs"""
        try:
            self.scheduler.resume()
            self.logger.info("Scheduler resumed")
            return True
        except Exception as e:
            self.logger.error(f"Failed to resume scheduler: {e}")
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
        self.logger.info(f"Daily task summary: {daily_metrics}")

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

        next_times = [job.next_run_time for job in jobs if job.next_run_time]
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
                logging.info(f"\nTask: {task.name}")
                logging.info(f"  ID: {job.id}")
                logging.info(f"  Type: {task.schedule_type.name}")
                logging.info(f"  Next Run: {job.next_run_time}")
                logging.info(f"  Enabled: {task.enabled}")
                logging.info(f"  Run Count: {task.run_count}")
                logging.info(f"  Error Count: {task.error_count}")

                if task.last_run:
                    logging.info(f"  Last Run: {task.last_run}")

        logging.info("\n" + "="*80)

    def export_schedule(self, output_path: Path) -> bool:
        """Export schedule to file"""
        try:
            schedule_data = {
                'export_time': datetime.now().isoformat(),
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
                    'next_run': job.next_run_time.isoformat() if job and job.next_run_time else None,
                    'last_run': task.last_run.isoformat() if task.last_run else None,
                    'run_count': task.run_count,
                    'error_count': task.error_count,
                    'metadata': task.metadata
                }

                schedule_data['tasks'].append(task_data)

            with open(output_path, 'w') as f:
                json.dump(schedule_data, f, indent=2)

            self.logger.info(f"Schedule exported to: {output_path}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to export schedule: {e}")
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

