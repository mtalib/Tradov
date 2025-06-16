#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module: SpyderA04_Scheduler.py
Group: A (Core Trading Engine)
Purpose: Trading schedule and time management

Description:
    This module manages trading schedules, market hours, and automated task execution
    for the Spyder options trading system. It handles market open/close times,
    trading windows, and scheduled strategy executions.

Author: Mohamed Talib
Date: 2025-06-01
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import datetime
import time
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import json
import pytz

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU10_TradingCalendar import get_trading_calendar
from SpyderA_Core.SpyderA05_EventManager import (
    get_event_manager,
    Event,
    EventType,
    EventPriority,
)

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Market timezone
MARKET_TIMEZONE = pytz.timezone("US/Eastern")

# Market hours (Eastern Time)
PRE_MARKET_START = datetime.time(4, 0)  # 4:00 AM ET
MARKET_OPEN = datetime.time(9, 30)  # 9:30 AM ET
MARKET_CLOSE = datetime.time(16, 0)  # 4:00 PM ET
AFTER_HOURS_END = datetime.time(20, 0)  # 8:00 PM ET

# SPY Options specific trading windows
ZERO_DTE_WINDOW_START = datetime.time(9, 45)  # Best for 0DTE after initial volatility
ZERO_DTE_WINDOW_END = datetime.time(15, 30)  # Close 0DTE before final hour
CREDIT_SPREAD_WINDOW = datetime.time(10, 0)  # Credit spreads after first 30 min


# ==============================================================================
# ENUMS
# ==============================================================================
class ScheduleType(Enum):
    """Types of scheduled tasks"""

    ONCE = "once"
    DAILY = "daily"
    INTERVAL = "interval"
    CRON = "cron"
    MARKET_OPEN = "market_open"
    MARKET_CLOSE = "market_close"
    CUSTOM = "custom"


class MarketSession(Enum):
    """Market session types"""

    CLOSED = "closed"
    PRE_MARKET = "pre_market"
    REGULAR = "regular"
    AFTER_HOURS = "after_hours"


# ==============================================================================
# TRADING SCHEDULER CLASS
# ==============================================================================
class TradingScheduler:
    """
    Main scheduler class for managing trading schedules and automated tasks.

    Features:
    - Market hours and trading sessions
    - Strategy execution scheduling
    - Periodic system tasks
    - Event-driven scheduling
    - Holiday calendar integration
    """

    def __init__(self, config: Dict[str, Any], event_manager: Any):
        """
        Initialize the scheduler.

        Args:
            config: Configuration dictionary
            event_manager: Event manager instance
        """
        self.config = config
        self.event_manager = event_manager
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Initialize scheduler
        self.scheduler = BackgroundScheduler(
            timezone=MARKET_TIMEZONE,
            job_defaults={
                "coalesce": True,
                "max_instances": 1,
                "misfire_grace_time": 30,
            },
        )

        # Trading calendar
        self.trading_calendar = get_trading_calendar()

        # Task registry
        self.scheduled_tasks: Dict[str, Dict] = {}
        self.task_history: List[Dict] = []

        # Session tracking
        self.current_session = MarketSession.CLOSED
        self.session_start_time: Optional[datetime.datetime] = None

        # Initialize locks
        self._lock = threading.RLock()

        # Setup event listeners
        self._setup_event_listeners()

        self.logger.info("TradingScheduler initialized")

    # ==========================================================================
    # INITIALIZATION METHODS
    # ==========================================================================
    def _setup_event_listeners(self) -> None:
        """Setup scheduler event listeners"""
        self.scheduler.add_listener(self._on_job_executed, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(self._on_job_error, EVENT_JOB_ERROR)

    def start(self) -> None:
        """Start the scheduler"""
        try:
            self.scheduler.start()
            self._schedule_core_tasks()
            self._update_market_session()
            self.logger.info("Scheduler started successfully")

            # Emit scheduler started event
            event = self.event_manager.create_event(
                EventType.SYSTEM, {"message": "Scheduler started"}, source="scheduler"
            )
            self.event_manager.publish(event)
        except Exception as e:
            self.logger.error(f"Error starting scheduler: {e}")
            self.error_handler.handle_error(e)
            raise

    def stop(self):
        """Stop the scheduler."""
        try:
            if hasattr(self, "scheduler") and self.scheduler and self.scheduler.running:
                self.logger.info("Stopping scheduler...")
                self.scheduler.shutdown(wait=False)
                self.logger.info("Scheduler stopped successfully")
            else:
                self.logger.debug("Scheduler was not running")
        except Exception as e:
            self.logger.error(f"Error stopping scheduler: {e}")
            self.error_handler.handle_error(e)

    # ==========================================================================
    # CORE SCHEDULING METHODS
    # ==========================================================================
    def _schedule_core_tasks(self) -> None:
        """Schedule core system tasks"""
        # Market session updates
        self.add_task(
            task_id="market_session_update",
            func=self._update_market_session,
            schedule_type=ScheduleType.INTERVAL,
            minutes=1,
            description="Update market session status",
        )

        # Daily market open tasks
        self.add_task(
            task_id="market_open_tasks",
            func=self._on_market_open,
            schedule_type=ScheduleType.CRON,
            hour=9,
            minute=30,
            day_of_week="mon-fri",
            description="Market open initialization",
        )

        # Daily market close tasks
        self.add_task(
            task_id="market_close_tasks",
            func=self._on_market_close,
            schedule_type=ScheduleType.CRON,
            hour=16,
            minute=0,
            day_of_week="mon-fri",
            description="Market close cleanup",
        )

        # Strategy scheduling windows
        self.add_task(
            task_id="zero_dte_window_open",
            func=lambda: self._strategy_window_event("0DTE", "open"),
            schedule_type=ScheduleType.CRON,
            hour=9,
            minute=45,
            day_of_week="mon-fri",
            description="0DTE trading window open",
        )

        self.add_task(
            task_id="zero_dte_window_close",
            func=lambda: self._strategy_window_event("0DTE", "close"),
            schedule_type=ScheduleType.CRON,
            hour=15,
            minute=30,
            day_of_week="mon-fri",
            description="0DTE trading window close",
        )

        # Position check before close
        self.add_task(
            task_id="position_check_before_close",
            func=self._position_check_before_close,
            schedule_type=ScheduleType.CRON,
            hour=15,
            minute=45,
            day_of_week="mon-fri",
            description="Check positions before market close",
        )

    def add_task(
        self,
        task_id: str,
        func: Callable,
        schedule_type: ScheduleType,
        description: str = "",
        **kwargs,
    ) -> bool:
        """
        Add a scheduled task.

        Args:
            task_id: Unique task identifier
            func: Function to execute
            schedule_type: Type of schedule
            description: Task description
            **kwargs: Schedule-specific parameters

        Returns:
            bool: Success status
        """
        with self._lock:
            try:
                # Remove existing task if it exists
                if task_id in self.scheduled_tasks:
                    self.remove_task(task_id)

                job = None

                if schedule_type == ScheduleType.ONCE:
                    run_date = kwargs.get(
                        "run_date",
                        datetime.datetime.now() + datetime.timedelta(seconds=1),
                    )
                    job = self.scheduler.add_job(
                        func, "date", run_date=run_date, id=task_id
                    )

                elif schedule_type == ScheduleType.DAILY:
                    hour = kwargs.get("hour", 9)
                    minute = kwargs.get("minute", 30)
                    job = self.scheduler.add_job(
                        func,
                        "cron",
                        hour=hour,
                        minute=minute,
                        id=task_id,
                        day_of_week="mon-fri",
                    )

                elif schedule_type == ScheduleType.INTERVAL:
                    interval_kwargs = {
                        k: v
                        for k, v in kwargs.items()
                        if k in ["weeks", "days", "hours", "minutes", "seconds"]
                    }
                    job = self.scheduler.add_job(
                        func, "interval", id=task_id, **interval_kwargs
                    )

                elif schedule_type == ScheduleType.CRON:
                    cron_kwargs = {
                        k: v
                        for k, v in kwargs.items()
                        if k
                        in [
                            "year",
                            "month",
                            "day",
                            "week",
                            "day_of_week",
                            "hour",
                            "minute",
                            "second",
                        ]
                    }
                    job = self.scheduler.add_job(
                        func, "cron", id=task_id, **cron_kwargs
                    )

                elif schedule_type == ScheduleType.MARKET_OPEN:
                    job = self.scheduler.add_job(
                        func,
                        "cron",
                        hour=9,
                        minute=30,
                        id=task_id,
                        day_of_week="mon-fri",
                    )

                elif schedule_type == ScheduleType.MARKET_CLOSE:
                    job = self.scheduler.add_job(
                        func,
                        "cron",
                        hour=16,
                        minute=0,
                        id=task_id,
                        day_of_week="mon-fri",
                    )

                if job:
                    self.scheduled_tasks[task_id] = {
                        "job": job,
                        "func": func,
                        "schedule_type": schedule_type,
                        "description": description,
                        "created": datetime.datetime.now(),
                        "kwargs": kwargs,
                    }

                    self.logger.info(f"Added scheduled task: {task_id}")
                    return True

            except Exception as e:
                self.logger.error(f"Error adding task {task_id}: {e}")
                self.error_handler.handle_error(e)

            return False

    def remove_task(self, task_id: str) -> bool:
        """
        Remove a scheduled task.

        Args:
            task_id: Task identifier

        Returns:
            bool: Success status
        """
        with self._lock:
            try:
                if task_id in self.scheduled_tasks:
                    self.scheduler.remove_job(task_id)
                    del self.scheduled_tasks[task_id]
                    self.logger.info(f"Removed scheduled task: {task_id}")
                    return True
            except Exception as e:
                self.logger.error(f"Error removing task {task_id}: {e}")
                self.error_handler.handle_error(e)

            return False

    def pause_task(self, task_id: str) -> bool:
        """Pause a scheduled task"""
        try:
            self.scheduler.pause_job(task_id)
            self.logger.info(f"Paused task: {task_id}")
            return True
        except Exception as e:
            self.logger.error(f"Error pausing task {task_id}: {e}")
            self.error_handler.handle_error(e)
            return False

    def resume_task(self, task_id: str) -> bool:
        """Resume a paused task"""
        try:
            self.scheduler.resume_job(task_id)
            self.logger.info(f"Resumed task: {task_id}")
            return True
        except Exception as e:
            self.logger.error(f"Error resuming task {task_id}: {e}")
            self.error_handler.handle_error(e)
            return False

    # ==========================================================================
    # MARKET SESSION METHODS
    # ==========================================================================
    def _update_market_session(self) -> None:
        """Update current market session status"""
        now = datetime.datetime.now(MARKET_TIMEZONE)
        current_time = now.time()

        # Check if market is open today
        if not self.trading_calendar.is_trading_day(now.date()):
            new_session = MarketSession.CLOSED
        elif current_time < PRE_MARKET_START:
            new_session = MarketSession.CLOSED
        elif PRE_MARKET_START <= current_time < MARKET_OPEN:
            new_session = MarketSession.PRE_MARKET
        elif MARKET_OPEN <= current_time < MARKET_CLOSE:
            new_session = MarketSession.REGULAR
        elif MARKET_CLOSE <= current_time < AFTER_HOURS_END:
            new_session = MarketSession.AFTER_HOURS
        else:
            new_session = MarketSession.CLOSED

        # Check for session change
        if new_session != self.current_session:
            old_session = self.current_session
            self.current_session = new_session
            self.session_start_time = now

            # Emit session change event - USE EXISTING EventType
            event = self.event_manager.create_event(
                EventType.SYSTEM,  # ← CHANGE from EventType.MARKET
                {
                    "type": "session_change",
                    "old_session": old_session.value,
                    "new_session": new_session.value,
                },
                source="scheduler",
            )
            self.event_manager.publish(event)

            self.logger.info(
                f"Market session changed: {old_session.value} -> {new_session.value}"
            )

    def get_current_session(self) -> MarketSession:
        """Get current market session"""
        return self.current_session

    def is_market_open(self) -> bool:
        """Check if market is currently open for regular trading"""
        return self.current_session == MarketSession.REGULAR

    def is_trading_day(self, date: Optional[datetime.date] = None) -> bool:
        """Check if given date is a trading day"""
        if date is None:
            date = datetime.date.today()
        return self.trading_calendar.is_trading_day(date)

    def get_next_market_open(self) -> Optional[datetime.datetime]:
        """Get next market open time"""
        now = datetime.datetime.now(MARKET_TIMEZONE)

        # If market is open now, return None
        if self.is_market_open():
            return None

        # Find next trading day
        next_day = now.date()
        for _ in range(10):  # Look up to 10 days ahead
            next_day += datetime.timedelta(days=1)
            if self.trading_calendar.is_market_open(next_day):
                return MARKET_TIMEZONE.localize(
                    datetime.datetime.combine(next_day, MARKET_OPEN)
                )

        return None

    def get_trading_hours_remaining(self) -> Optional[datetime.timedelta]:
        """Get time remaining until market close"""
        if not self.is_market_open():
            return None

        now = datetime.datetime.now(MARKET_TIMEZONE)
        close_time = now.replace(hour=16, minute=0, second=0, microsecond=0)

        return close_time - now

    # ==========================================================================
    # EVENT HANDLERS
    # ==========================================================================
    def _on_market_open(self) -> None:
        """Handle market open event"""
        self.logger.info("Market opened - executing market open tasks")

        # Emit market open event - USE EXISTING EventType
        event = self.event_manager.create_event(
            EventType.SYSTEM,  # ← CHANGE from EventType.MARKET
            {"type": "market_open"},
            source="scheduler",
        )
        self.event_manager.publish(event)

        # Record in task history
        self._record_task_execution("market_open", "success")

    def _on_market_close(self) -> None:
        """Handle market close event"""
        self.logger.info("Market closed - executing market close tasks")

        # Emit market close event - USE EXISTING EventType
        event = self.event_manager.create_event(
            EventType.SYSTEM,  # ← CHANGE from EventType.MARKET
            {"type": "market_close"},
            source="scheduler",
        )
        self.event_manager.publish(event)

        # Record in task history
        self._record_task_execution("market_close", "success")

    def _strategy_window_event(self, strategy: str, action: str) -> None:
        """Handle strategy trading window events"""
        self.logger.info(f"Strategy window {action} for {strategy}")

        # Emit strategy window event - USE EXISTING EventType
        event = self.event_manager.create_event(
            EventType.TRADING,  # ← CHANGE from EventType.STRATEGY
            {"type": f"window_{action}", "strategy": strategy},
            source="scheduler",
        )
        self.event_manager.publish(event)

    def _position_check_before_close(self) -> None:
        """Check positions before market close"""
        self.logger.info("Checking positions before market close")

        # Emit position check event - USE EXISTING EventType
        event = self.event_manager.create_event(
            EventType.RISK,  # ← KEEP as EventType.RISK (this one exists)
            {"type": "position_check", "reason": "market_close"},
            source="scheduler",
        )
        self.event_manager.publish(event)

    def schedule_strategy_execution(
        self,
        strategy_name: str,
        execution_time: datetime.time,
        days_of_week: str = "mon-fri",
    ) -> bool:
        """Schedule a strategy to run at specific time."""
        task_id = f"strategy_{strategy_name}"

        def execute_strategy():
            event = self.event_manager.create_event(
                EventType.TRADING,  # ← CHANGE from EventType.STRATEGY
                {"type": "execute", "strategy": strategy_name},
                source="scheduler",
            )
            self.event_manager.publish(event)

        return self.add_task(
            task_id=task_id,
            func=execute_strategy,
            schedule_type=ScheduleType.CRON,
            hour=execution_time.hour,
            minute=execution_time.minute,
            day_of_week=days_of_week,
            description=f"Execute {strategy_name} strategy",
        )

    def schedule_data_update(self, interval_minutes: int = 5) -> bool:
        """
        Schedule periodic data updates.

        Args:
            interval_minutes: Update interval in minutes

        Returns:
            bool: Success status
        """

        def update_data():
            event = self.event_manager.create_event(
                EventType.DATA, {"type": "update_request"}, source="scheduler"
            )
            self.event_manager.publish(event)

        return self.add_task(
            task_id="data_update",
            func=update_data,
            schedule_type=ScheduleType.INTERVAL,
            minutes=interval_minutes,
            description="Periodic data update",
        )

    def schedule_risk_check(self, interval_minutes: int = 15) -> bool:
        """
        Schedule periodic risk checks.

        Args:
            interval_minutes: Check interval in minutes

        Returns:
            bool: Success status
        """

        def check_risk():
            event = self.event_manager.create_event(
                EventType.RISK, {"type": "periodic_check"}, source="scheduler"
            )
            self.event_manager.publish(event)

        return self.add_task(
            task_id="risk_check",
            func=check_risk,
            schedule_type=ScheduleType.INTERVAL,
            minutes=interval_minutes,
            description="Periodic risk check",
        )

    # ==========================================================================
    # EVENT HANDLERS (ADD THESE MISSING METHODS)
    # ==========================================================================
    def _on_job_executed(self, event):
        """Handle job execution event"""
        try:
            job_id = event.job_id
            self.logger.debug(f"Job executed successfully: {job_id}")

            # Record successful execution
            self._record_task_execution(job_id, "success")

        except Exception as e:
            self.logger.error(f"Error handling job execution event: {e}")

    def _on_job_error(self, event):
        """Handle job error event"""
        try:
            job_id = event.job_id
            exception = getattr(event, "exception", "Unknown error")

            self.logger.error(f"Job failed: {job_id} - {exception}")

            # Record failed execution
            self._record_task_execution(job_id, "error", str(exception))

            # Emit error event
            error_event = self.event_manager.create_event(
                EventType.ERROR,
                {"type": "job_error", "job_id": job_id, "error": str(exception)},
                source="scheduler",
            )
            self.event_manager.publish(error_event)

        except Exception as e:
            self.logger.error(f"Error handling job error event: {e}")

    def _record_task_execution(self, task_id: str, status: str, error: str = None):
        """Record task execution in history"""
        try:
            execution_record = {
                "task_id": task_id,
                "timestamp": datetime.datetime.now(),
                "status": status,
                "error": error,
            }

            self.task_history.append(execution_record)

            # Keep only last 1000 records
            if len(self.task_history) > 1000:
                self.task_history = self.task_history[-1000:]

        except Exception as e:
            self.logger.error(f"Error recording task execution: {e}")

    def get_schedule_summary(self) -> Dict[str, Any]:
        """Get summary of scheduled tasks"""
        try:
            with self._lock:
                return {
                    "total_tasks": len(self.scheduled_tasks),
                    "current_session": self.current_session.value,
                    "scheduler_running": self.scheduler.running,
                    "tasks": {
                        task_id: {
                            "description": task_info["description"],
                            "schedule_type": task_info["schedule_type"].value,
                            "created": task_info["created"].isoformat(),
                        }
                        for task_id, task_info in self.scheduled_tasks.items()
                    },
                }
        except Exception as e:
            self.logger.error(f"Error getting schedule summary: {e}")
            return {}

    def get_task_history(self, count: int = 50) -> List[Dict]:
        """Get recent task execution history"""
        try:
            return self.task_history[-count:] if self.task_history else []
        except Exception as e:
            self.logger.error(f"Error getting task history: {e}")
            return []


# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Example configuration
    config = {
        "timezone": "US/Eastern",
        "enable_pre_market": True,
        "enable_after_hours": False,
    }

    # Create event manager
    event_manager = get_event_manager()

    # Create scheduler
    scheduler = TradingScheduler(config, event_manager)

    # Start scheduler
    scheduler.start()

    # Add custom task
    scheduler.add_task(
        task_id="custom_analysis",
        func=lambda: print("Running custom analysis"),
        schedule_type=ScheduleType.INTERVAL,
        minutes=30,
        description="Run analysis every 30 minutes",
    )

    # Schedule a strategy
    scheduler.schedule_strategy_execution(
        "iron_condor", datetime.time(10, 0), "mon-fri"
    )

    # Get schedule summary
    print("Schedule Summary:")
    summary = scheduler.get_schedule_summary()
    for key, value in summary.items():
        if key != "tasks":
            print(f"  {key}: {value}")

    print("\nScheduled Tasks:")
    for task_id, task_info in summary["tasks"].items():
        print(f"  {task_id}: {task_info['description']}")

    # Keep running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        scheduler.stop()
        print("\nScheduler stopped")
