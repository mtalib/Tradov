#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovS_Signals
Module: TradovS04_BlackSwanScheduler.py
Purpose: Automated scheduler for Black Swan risk monitoring, alerting, and reporting

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-03-27 Time: 00:00:00

Description:
    Provides fully automated, time-driven scheduling of Black Swan risk checks
    for the TRAD options trading system. Orchestrates data collection (via
    BlackSwanDataCollector / TradovS06), risk calculation (via BlackSwanCalculator /
    TradovS07), alert dispatch, and daily report generation.

    When integrated with the Tradov system (TRADOV_INTEGRATION=True), all tasks are
    registered with TradovA04_Scheduler. In standalone mode, the `schedule` library
    drives a dedicated background daemon thread that polls every second.

Default Schedule (all times Eastern Time):
    04:00   Pre-market check       — overnight risk assessment before opening bell
    09:15   Pre-open check         — final snapshot 15 minutes before market open
    12:00   Mid-day check          — intraday monitoring
    15:45   Pre-close check        — late-session risk before closing orders
    16:30   Post-market check      — after-hours summary for overnight positions
    17:00   Daily report           — generate text / JSON / CSV summary report
    02:00   File cleanup           — purge reports older than `retention_days` (default 30)

    Default schedule times are defined in DEFAULT_SCHEDULE_TIMES and can be
    overridden via the `schedule_times` key in the config dictionary.

Interval Checks (optional):
    Additional interval-based checks can be registered via `add_interval_check(minutes)`.
    These fire only during US market hours (09:30–16:00 ET, Mon–Fri). Outside market
    hours the callback is skipped even if the timer fires.

Alert Logic:
    Alerts are dispatched when any of the following conditions are true:
        • Status is RED   and `alert_on_red`    is True (default True)
        • Status is YELLOW and `alert_on_yellow` is True (default True)
        • Score deteriorates by ≥ 1.0 points between two consecutive checks
          (rapid-deterioration trigger — fires regardless of status)

    Suppression:
        • 60-minute cooldown between repeat alerts of the same status level
          (configurable via `alert_cooldown_minutes`)
        • Maximum 10 alerts per calendar day (MAX_DAILY_ALERTS)

Notification Channels:
    LOG       Always available; writes a WARNING-level log entry via TradovLogger
    EMAIL     Via TradovJ02_EmailNotifier (Tradov mode) or direct SMTP (standalone)
    SLACK     Stub — logs "not yet implemented"; planned for future release
    TELEGRAM  Stub — logs "not yet implemented"; planned for future release

Report Generation:
    Daily report generation is disabled by default in the pair-trading deployment.
    The scheduler can still keep SWAN check history and emit alerts, but it will
    not write daily text / JSON / CSV report files unless
    `enable_daily_reports: True` is explicitly set in config.

Tradov Integration:
    When TRADOV_INTEGRATION=True the following Tradov modules are used:
        TradovA04_Scheduler         Task scheduling and cron management
        TradovJ01_AlertManager      Alert routing and deduplication
        TradovJ02_EmailNotifier     Email delivery
        TradovU10_TradingCalendar   Accurate market-hours and holiday detection
        TradovH01_DataAccessLayer   SQLite persistence of check results

Change Log:
    2026-03-27:
        - Expanded module header with scheduling, alert, and reporting detail
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import json
import time
import threading
from urllib.parse import urlencode, urlsplit, urlunsplit
from datetime import datetime, timedelta, UTC
from typing import Any
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
import logging
from pathlib import Path

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import schedule
import signal
import pandas as pd
import numpy as np
import pytz

try:
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from email.mime.base import MIMEBase
    from email import encoders
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger
    from Tradov.TradovU_Utilities.TradovU02_ErrorHandler import TradovErrorHandler
    from Tradov.TradovU_Utilities.TradovU03_DateTimeUtils import TradovDateTimeUtils
    from Tradov.TradovU_Utilities.TradovU10_TradingCalendar import TradovTradingCalendar
    from TradovA_Core.TradovA04_Scheduler import TradovScheduler
    from TradovJ_Alerts.TradovJ01_AlertManager import TradovAlertManager
    from TradovJ_Alerts.TradovJ02_EmailNotifier import TradovEmailNotifier
    from TradovH_Storage.TradovH01_DataAccessLayer import TradovDataAccess
    TRADOV_INTEGRATION = True
except ImportError:
    # Fallback for standalone operation
    TradovLogger = logging
    TradovErrorHandler = None
    TradovDateTimeUtils = None
    TradovTradingCalendar = None
    TradovScheduler = None
    TradovAlertManager = None
    TradovEmailNotifier = None
    TradovDataAccess = None
    TRADOV_INTEGRATION = False

# Import Black Swan modules (current implementation)
try:
    from TradovS_Signals.TradovS03_BlackSwanIndicator import (
        BlackSwanResult,
        RiskStatus,
        get_black_swan_indicator,
    )
except ImportError:
    from TradovS03_BlackSwanIndicator import (  # type: ignore[no-redef]
        BlackSwanResult,
        RiskStatus,
        get_black_swan_indicator,
    )

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Default schedule times (ET)
DEFAULT_SCHEDULE_TIMES = [
    "04:00",  # Pre-market check
    "09:15",  # Pre-open check
    "12:00",  # Mid-day check
    "15:45",  # Pre-close check
    "16:30"   # Post-market check
]

# Alert settings
ALERT_COOLDOWN_MINUTES = 60  # Minimum time between same alerts
MAX_DAILY_ALERTS = 10        # Maximum alerts per day

# Report settings
REPORT_OUTPUT_DIR = "black_swan_reports"
REPORT_RETENTION_DAYS = 30

# Email settings (defaults)
DEFAULT_SMTP_SERVER = "smtp.gmail.com"
DEFAULT_SMTP_PORT = 587
_ALLOWED_WEBHOOK_SCHEMES = frozenset({"https"})
_TELEGRAM_API_HOSTS = frozenset({"api.telegram.org"})


def _validated_https_url(
    url: str,
    *,
    allowed_hosts: set[str] | None = None,
) -> str | None:
    """Return a normalized HTTPS URL when it is safe to open."""
    normalized_url = str(url or "").strip()
    if not normalized_url:
        return None

    parsed = urlsplit(normalized_url)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme not in _ALLOWED_WEBHOOK_SCHEMES or not hostname:
        return None

    if allowed_hosts is not None and hostname not in allowed_hosts:
        return None

    return urlunsplit(parsed)


def _telegram_bot_api_url(token: str) -> str:
    """Build the canonical Telegram Bot API endpoint for sendMessage."""
    return urlunsplit(
        ("https", "api.telegram.org", f"/bot{token}/sendMessage", "", "")
    )

# ==============================================================================
# ENUMS
# ==============================================================================
class ScheduleType(Enum):
    """Types of scheduled tasks"""
    MARKET_CHECK = "market_check"
    DAILY_REPORT = "daily_report"
    ALERT_CHECK = "alert_check"
    OPTIMIZATION = "optimization"
    CLEANUP = "cleanup"

class NotificationChannel(Enum):
    """Available notification channels"""
    EMAIL = "email"
    SMS = "sms"
    SLACK = "slack"
    TELEGRAM = "telegram"
    LOG = "log"


class AlertLevel(Enum):
    """Backward-compatible alert levels derived from risk status."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class ScheduledTask:
    """Represents a scheduled task"""
    task_id: str
    task_type: ScheduleType
    schedule_time: str
    callback: Callable
    enabled: bool
    last_run: datetime | None
    next_run: datetime | None

@dataclass
class AlertRecord:
    """Record of sent alerts"""
    timestamp: datetime
    status: RiskStatus
    score: float
    message: str
    channels: list[NotificationChannel]

@dataclass
class DailyReport:
    """Daily report data"""
    date: datetime
    checks_performed: int
    average_score: float
    max_score: float
    status_distribution: dict[str, int]
    alerts_sent: int
    data_quality: str

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class BlackSwanScheduler:
    """
    Automated scheduler for Black Swan Indicator monitoring.

    This class provides comprehensive scheduling capabilities for automated
    Black Swan monitoring, including pre-market checks, real-time monitoring
    during market hours, alert management, and report generation. Integrates
    with Tradov's scheduling system when available.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        indicator: Black Swan indicator instance
        scheduled_tasks: Dictionary of scheduled tasks
        alert_history: Recent alert history
        running: Scheduler running state

    Example:
        >>> scheduler = BlackSwanScheduler()
        >>> scheduler.add_daily_check("04:00")
        >>> scheduler.start()
    """

    def __init__(self, config: dict | None = None):
        """
        Initialize the scheduler.

        Args:
            config: Optional configuration dictionary
        """
        # Setup logging
        if TRADOV_INTEGRATION:
            self.logger = TradovLogger.get_logger(__name__)
            self.error_handler = TradovErrorHandler()
        else:
            self.logger = logging.getLogger(__name__)
            self.error_handler = None

        # Configuration
        self.config = config or {}
        self._load_configuration()

        # Initialize indicator
        self.indicator = get_black_swan_indicator()

        # Tradov integration
        self.tradov_scheduler = None
        self.alert_manager = None
        self.email_notifier = None
        self.trading_calendar = None
        self.data_access = None

        if TRADOV_INTEGRATION:
            self._init_tradov_integration()

        # Scheduler state
        self.scheduled_tasks: dict[str, ScheduledTask] = {}
        self.alert_history: list[AlertRecord] = []
        self.daily_results: list[BlackSwanResult] = []
        self.latest_result: BlackSwanResult | None = None
        self._last_logged_check_status: RiskStatus | None = None
        self._restored_same_day_result = False
        self.running = False
        self.scheduler_thread: threading.Thread | None = None
        self._previous_signal_handlers: dict[int, Any] = {}

        # Create output directory
        self.report_dir = Path(self.config.get('report_dir', REPORT_OUTPUT_DIR))
        self.report_dir.mkdir(exist_ok=True)

        # Setup signal handlers
        self._install_signal_handlers()

        # Rehydrate the most recent same-day result before any catch-up logic
        # decides whether missed checks need to be replayed.
        self.load_latest_result_from_database()

        # Initialize default tasks
        self._setup_default_tasks()

        self.logger.debug("Black Swan Scheduler initialized")

    # ==========================================================================
    # PUBLIC METHODS - Task Management
    # ==========================================================================
    def add_daily_check(self, time_str: str, enabled: bool = True) -> str:
        """
        Add a daily market check at specified time.

        Args:
            time_str: Time in HH:MM format (ET)
            enabled: Whether task is enabled

        Returns:
            Task ID
        """
        task_id = f"daily_check_{time_str.replace(':', '')}"

        def check_callback():
            self._perform_market_check()

        task = ScheduledTask(
            task_id=task_id,
            task_type=ScheduleType.MARKET_CHECK,
            schedule_time=time_str,
            callback=check_callback,
            enabled=enabled,
            last_run=None,
            next_run=None
        )

        self.scheduled_tasks[task_id] = task

        # Schedule with appropriate system
        if self.tradov_scheduler and TRADOV_INTEGRATION:
            self.tradov_scheduler.schedule_daily(time_str, check_callback, task_id)
        else:
            schedule.every().day.at(time_str).do(check_callback).tag(task_id)

        self.logger.debug("Added daily check at %s", time_str)
        return task_id

    def add_interval_check(self, minutes: int, enabled: bool = True) -> str:
        """
        Add interval-based checking.

        Args:
            minutes: Check interval in minutes
            enabled: Whether task is enabled

        Returns:
            Task ID
        """
        task_id = f"interval_check_{minutes}min"

        def check_callback():
            if self._is_market_hours():
                self._perform_market_check()

        task = ScheduledTask(
            task_id=task_id,
            task_type=ScheduleType.MARKET_CHECK,
            schedule_time=f"every_{minutes}_minutes",
            callback=check_callback,
            enabled=enabled,
            last_run=None,
            next_run=None
        )

        self.scheduled_tasks[task_id] = task

        # Schedule
        schedule.every(minutes).minutes.do(check_callback).tag(task_id)

        self.logger.info("Added interval check every %s minutes", minutes)
        return task_id

    def add_daily_report(self, time_str: str = "17:00", enabled: bool = True) -> str:
        """
        Add daily report generation.

        Args:
            time_str: Report generation time
            enabled: Whether task is enabled

        Returns:
            Task ID
        """
        task_id = "daily_report"
        if not self.enable_daily_reports:
            self.logger.info("Daily Black Swan reports are disabled; not scheduling %s", task_id)
            return task_id

        def report_callback():
            self._generate_daily_report()

        task = ScheduledTask(
            task_id=task_id,
            task_type=ScheduleType.DAILY_REPORT,
            schedule_time=time_str,
            callback=report_callback,
            enabled=enabled,
            last_run=None,
            next_run=None
        )

        self.scheduled_tasks[task_id] = task

        # Schedule
        schedule.every().day.at(time_str).do(report_callback).tag(task_id)

        self.logger.debug("Added daily report at %s", time_str)
        return task_id

    def remove_task(self, task_id: str) -> bool:
        """
        Remove a scheduled task.

        Args:
            task_id: Task ID to remove

        Returns:
            True if removed successfully
        """
        if task_id in self.scheduled_tasks:
            # Clear from schedule
            schedule.clear(task_id)

            # Remove from Tradov scheduler if integrated
            if self.tradov_scheduler and TRADOV_INTEGRATION:
                try:
                    self.tradov_scheduler.remove_task(task_id)
                except Exception as e:
                    self.logger.debug("Failed to remove task %s from Tradov scheduler: %s", task_id, e)  # noqa: E501

            del self.scheduled_tasks[task_id]
            self.logger.info("Removed task: %s", task_id)
            return True

        return False

    def enable_task(self, task_id: str) -> bool:
        """Enable a scheduled task."""
        if task_id in self.scheduled_tasks:
            self.scheduled_tasks[task_id].enabled = True
            return True
        return False

    def disable_task(self, task_id: str) -> bool:
        """Disable a scheduled task."""
        if task_id in self.scheduled_tasks:
            self.scheduled_tasks[task_id].enabled = False
            return True
        return False

    # ==========================================================================
    # PUBLIC METHODS - Scheduler Control
    # ==========================================================================
    def start(self, daemon: bool = True):
        """
        Start the scheduler.

        Args:
            daemon: Run as daemon thread
        """
        if self.running:
            self.logger.warning("Scheduler already running")
            return

        self.running = True
        self.logger.debug("Starting Black Swan Scheduler")

        # If integrated with Tradov, let it handle scheduling
        if self.tradov_scheduler and TRADOV_INTEGRATION:
            self.logger.info("Using Tradov scheduler")
            # Tasks already registered with Tradov scheduler
        else:
            # Run standalone scheduler
            self.scheduler_thread = threading.Thread(target=self._run_scheduler)
            self.scheduler_thread.daemon = daemon
            self.scheduler_thread.start()

    def _install_signal_handlers(self) -> None:
        """Install scheduler-local signal handlers without stealing the process exit path."""
        if TRADOV_INTEGRATION:
            self.logger.debug("Skipping Black Swan signal handler install under Tradov integration")
            return
        for signum in (signal.SIGINT, signal.SIGTERM):
            try:
                self._previous_signal_handlers[signum] = signal.getsignal(signum)
                signal.signal(signum, self._signal_handler)
            except ValueError:
                self.logger.debug("Skipping signal handler install outside main thread: %s", signum)

    def _restore_signal_handlers(self) -> None:
        """Restore the process handlers that were present before scheduler startup."""
        for signum, previous_handler in list(self._previous_signal_handlers.items()):
            try:
                if signal.getsignal(signum) == self._signal_handler:
                    signal.signal(signum, previous_handler)
            except ValueError:
                self.logger.debug("Skipping signal handler restore outside main thread: %s", signum)
        self._previous_signal_handlers.clear()

    def stop(self):
        """Stop the scheduler."""
        self.logger.info("Stopping Black Swan Scheduler")
        self.running = False

        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)

        # Clear schedules
        schedule.clear()
        self._restore_signal_handlers()

        self.logger.info("Black Swan Scheduler stopped")

    def run_now(self, task_id: str) -> bool:
        """
        Run a specific task immediately.

        Args:
            task_id: Task ID to run

        Returns:
            True if task was run
        """
        if task_id in self.scheduled_tasks:
            task = self.scheduled_tasks[task_id]
            if task.enabled:
                try:
                    task.callback()
                    task.last_run = datetime.now(UTC)
                    return True
                except Exception as e:
                    self.logger.error("Error running task %s: %s", task_id, e)
                    if self.error_handler:
                        self.error_handler.handle_error(e)

        return False

    # ==========================================================================
    # PUBLIC METHODS - Alert Management
    # ==========================================================================
    def configure_alerts(self, channels: list[NotificationChannel],
                        recipients: dict[str, list[str]] | None = None):
        """
        Configure alert channels and recipients.

        Args:
            channels: List of notification channels to use
            recipients: Dictionary of channel -> recipient list
        """
        self.alert_channels = channels
        self.alert_recipients = recipients or {}

        # Validate email configuration if email channel is enabled
        if NotificationChannel.EMAIL in channels and EMAIL_AVAILABLE:
            if 'email' not in self.alert_recipients:
                self.logger.warning("Email channel enabled but no recipients configured")

        self.logger.info("Alert channels configured: %s", [c.value for c in channels])

    def test_alerts(self) -> dict[str, bool]:
        """
        Test all configured alert channels.

        Returns:
            Dictionary of channel -> success status
        """
        results = {}

        test_message = f"Black Swan Indicator test alert - {datetime.now(UTC)}"

        for channel in self.alert_channels:
            try:
                if channel == NotificationChannel.EMAIL:
                    success = self._send_email_alert("TEST", test_message, test=True)
                elif channel == NotificationChannel.LOG:
                    self.logger.info("TEST ALERT: %s", test_message)
                    success = True
                else:
                    success = False

                results[channel.value] = success

            except Exception as e:
                self.logger.error("Alert test failed for %s: %s", channel.value, e)
                results[channel.value] = False

        return results

    # ==========================================================================
    # PRIVATE METHODS - Core Operations
    # ==========================================================================
    def _perform_market_check(self):
        """Perform a market check and process results."""
        try:
            self.logger.debug("Performing scheduled market check")

            # Calculate indicator using the unified S03 implementation.
            result = self.indicator.calculate_swan_score()
            self._attach_alert_level(result)

            # Store result
            self.daily_results.append(result)
            self.latest_result = result
            self._restored_same_day_result = False

            # Log to database if available
            if self.data_access:
                self._log_to_database(result)

            # Check for alerts
            self._check_and_send_alerts(result)

            # Update last run time
            for task in self.scheduled_tasks.values():
                if task.task_type == ScheduleType.MARKET_CHECK:
                    task.last_run = datetime.now(UTC)

            score = float(result.overall_score)
            self.logger.debug(
                "Market check complete - Status: %s, Score: %.2f",
                result.status.value,
                score,
            )

            self._last_logged_check_status = result.status

        except Exception as e:
            self.logger.error("Error in market check: %s", e)
            if self.error_handler:
                self.error_handler.handle_error(e)

    def _check_and_send_alerts(self, result: BlackSwanResult):
        """Check if alerts should be sent based on result."""
        # Check if we should send an alert
        should_alert = False
        alert_reason = ""

        # Check status-based alerts
        if result.status == RiskStatus.RED and self.config.get('alert_on_red', True):
            should_alert = True
            alert_reason = "RED ALERT - High market stress detected"
        elif result.status == RiskStatus.YELLOW and self.config.get('alert_on_yellow', True):
            should_alert = True
            alert_reason = "YELLOW ALERT - Elevated market stress"

        # Check for rapid changes
        if len(self.daily_results) >= 2:
            prev_result = self.daily_results[-2]
            score_change = result.overall_score - prev_result.overall_score

            if score_change > 1.0:  # Rapid deterioration
                should_alert = True
                alert_reason = f"RAPID DETERIORATION - Score increased by {score_change:.2f}"

        if not should_alert:
            return

        # Check cooldown
        if self._is_in_cooldown(result.status):
            self.logger.info("Alert suppressed due to cooldown")
            return

        # Check daily limit
        today_alerts = sum(1 for alert in self.alert_history
                         if alert.timestamp.date() == datetime.now(UTC).date())
        if today_alerts >= MAX_DAILY_ALERTS:
            self.logger.warning("Daily alert limit reached")
            return

        # Send alerts
        self._send_alerts(result, alert_reason)

        # Record alert
        alert_record = AlertRecord(
            timestamp=datetime.now(UTC),
            status=result.status,
            score=result.overall_score,
            message=alert_reason,
            channels=self.alert_channels
        )
        self.alert_history.append(alert_record)

        # Trim history
        if len(self.alert_history) > 100:
            self.alert_history = self.alert_history[-100:]

    def _send_alerts(self, result: BlackSwanResult, reason: str):
        """Send alerts through configured channels."""
        # Build alert message
        message = self._build_alert_message(result, reason)

        for channel in self.alert_channels:
            try:
                if channel == NotificationChannel.EMAIL:
                    self._send_email_alert(result.status.value, message)

                elif channel == NotificationChannel.LOG:
                    self.logger.warning("BLACK SWAN ALERT: %s", message)

                elif channel == NotificationChannel.SLACK:
                    self._send_slack_alert(message)

                elif channel == NotificationChannel.TELEGRAM:
                    self._send_telegram_alert(message)

                # Add other channels as needed

            except Exception as e:
                self.logger.error("Failed to send alert via %s: %s", channel.value, e)

    def _build_alert_message(self, result: BlackSwanResult, reason: str) -> str:
        """Build detailed alert message."""
        message = f"""
BLACK SWAN INDICATOR ALERT
==========================
{reason}

Time: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S ET')}
Status: {result.status.value}
Overall Score: {result.overall_score:.2f}
Alert Level: {self._get_alert_level(result).name}

Component Breakdown:
"""

        for name, score in result.component_scores.items():
            message += f"- {name.replace('_', ' ').title()}: {score.raw_score:.2f} - {score.description}\n"  # noqa: E501

        message += f"""
Data Quality: {result.data_quality.value}

This is an automated alert from the Black Swan Indicator system.
Please review market conditions and adjust positions accordingly.
        """

        return message.strip()

    def _send_email_alert(self, level: str, message: str, test: bool = False) -> bool:
        """
        Send email alert.

        Args:
            level: Alert level
            message: Alert message
            test: Whether this is a test

        Returns:
            True if sent successfully
        """
        if not EMAIL_AVAILABLE:
            self.logger.warning("Email functionality not available")
            return False

        # Use Tradov email notifier if available
        if self.email_notifier and TRADOV_INTEGRATION:
            try:
                return self.email_notifier.send_alert(
                    subject=f"Black Swan {level} Alert",
                    body=message,
                    recipients=self.alert_recipients.get('email', [])
                )
            except Exception as e:
                self.logger.error("Tradov email notifier failed: %s", e)

        # Fallback to direct SMTP
        try:
            smtp_config = self.config.get('smtp', {})
            server = smtp_config.get('server', DEFAULT_SMTP_SERVER)
            port = smtp_config.get('port', DEFAULT_SMTP_PORT)
            username = smtp_config.get('username')
            password = smtp_config.get('password')

            if not username or not password:
                self.logger.error("SMTP credentials not configured")
                return False

            recipients = self.alert_recipients.get('email', [])
            if not recipients:
                self.logger.warning("No email recipients configured")
                return False

            # Create message
            msg = MIMEMultipart()
            msg['From'] = username
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = f"Black Swan {level} Alert {'[TEST]' if test else ''}"

            msg.attach(MIMEText(message, 'plain'))

            # Send email
            with smtplib.SMTP(server, port) as smtp:
                smtp.starttls()
                smtp.login(username, password)
                smtp.send_message(msg)

            self.logger.info("Email alert sent to %s recipients", len(recipients))
            return True

        except Exception as e:
            self.logger.error("Failed to send email: %s", e)
            return False

    def _send_slack_alert(self, message: str):
        """Send Slack alert.

        Preferred path: TradovJ03_WebhookNotifier (Slack channel).
        Fallback: direct urllib POST to `slack_webhook_url` from config.
        """
        # ── Preferred path: use TradovJ03_WebhookNotifier ─────────────────────
        try:
            from Tradov.TradovJ_Alerts.TradovJ03_WebhookNotifier import WebhookNotifier
            notifier = WebhookNotifier()
            notifier.send_slack(message=message)
            self.logger.info("Slack alert dispatched via TradovJ03_WebhookNotifier")
            return
        except Exception:
            pass  # J03 unavailable or not configured — use direct fallback

        # ── Fallback: direct urllib POST ───────────────────────────────────────
        webhook_url = self.config.get("slack_webhook_url")
        if not webhook_url:
            self.logger.warning("Slack webhook URL not configured — skipping Slack alert")
            return
        safe_webhook_url = _validated_https_url(str(webhook_url))
        if safe_webhook_url is None:
            self.logger.error("Slack webhook URL is invalid or not HTTPS — skipping Slack alert")
            return
        try:
            import json as _json
            import urllib.request
            payload = _json.dumps({"text": message}).encode()
            req = urllib.request.Request(
                safe_webhook_url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
                if resp.status == 200:
                    self.logger.info("Slack alert sent via direct webhook")
                else:
                    self.logger.warning("Slack webhook returned status %s", resp.status)
        except Exception as e:
            self.logger.error("Failed to send Slack alert: %s", e, exc_info=True)

    def _send_telegram_alert(self, message: str):
        """Send Telegram alert via TradovJ05_TelegramBot.

        Falls back to a direct Bot API call when the Tradov integration is
        unavailable. Requires `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in
        the environment (read from .env by TradovA03_Configuration).
        """
        # ── Preferred path: use TradovJ05_TelegramBot ─────────────────────────
        try:
            from TradovJ_Alerts.TradovJ05_TelegramBot import TelegramBot
            bot = TelegramBot()
            last_status = getattr(self, "_last_alert_status", None)
            severity = "critical" if last_status and getattr(last_status, "value", "") == "RED" else "warning"  # noqa: E501
            bot.send_alert(title="Black Swan Alert", message=message, severity=severity)
            self.logger.info("Telegram alert dispatched via TradovJ05_TelegramBot")
            return
        except Exception as e:
            self.logger.debug("TradovJ05_TelegramBot unavailable, using fallback: %s", e)

        # ── Fallback: direct Bot API call ─────────────────────────────────────
        import os
        import urllib.request
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            self.logger.warning("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set — skipping")
            return
        try:
            params = urlencode({"chat_id": chat_id, "text": message}).encode()
            safe_url = _validated_https_url(
                _telegram_bot_api_url(token),
                allowed_hosts=_TELEGRAM_API_HOSTS,
            )
            if safe_url is None:
                self.logger.error("Telegram Bot API URL is invalid — skipping")
                return
            req = urllib.request.Request(safe_url, data=params, method="POST")
            with urllib.request.urlopen(req, timeout=10):  # nosec B310
                self.logger.info("Telegram alert sent via direct Bot API")
        except Exception as e:
            self.logger.error("Failed to send Telegram alert: %s", e)

    # ==========================================================================
    # PRIVATE METHODS - Report Generation
    # ==========================================================================
    def _generate_daily_report(self):
        """Generate daily summary report."""
        if not self.enable_daily_reports:
            self.logger.debug("Daily Black Swan report generation skipped (disabled)")
            return
        try:
            self.logger.info("Generating daily report")

            # Calculate daily statistics
            if not self.daily_results:
                self.logger.warning("No data for daily report")
                return

            # Statistics
            scores = [r.overall_score for r in self.daily_results]
            status_counts = {
                RiskStatus.GREEN: 0,
                RiskStatus.YELLOW: 0,
                RiskStatus.RED: 0
            }

            for result in self.daily_results:
                status_counts[result.status] += 1

            # Data quality
            quality_counts = {}
            for result in self.daily_results:
                quality = result.data_quality.value
                quality_counts[quality] = quality_counts.get(quality, 0) + 1

            most_common_quality = max(quality_counts.items(), key=lambda x: x[1])[0]

            # Create report data
            report = DailyReport(
                date=datetime.now(UTC),
                checks_performed=len(self.daily_results),
                average_score=np.mean(scores),
                max_score=np.max(scores),
                status_distribution={
                    status.value: count
                    for status, count in status_counts.items()
                },
                alerts_sent=len([a for a in self.alert_history
                               if a.timestamp.date() == datetime.now(UTC).date()]),
                data_quality=most_common_quality
            )

            # Generate report files
            self._save_text_report(report)
            self._save_json_report(report)
            self._save_csv_data()

            # Send report if configured
            if self.config.get('email_daily_report', False):
                self._email_daily_report(report)

            # Clear daily results for next day
            self.daily_results = []

            self.logger.info("Daily report generated successfully")

        except Exception as e:
            self.logger.error("Error generating daily report: %s", e)
            if self.error_handler:
                self.error_handler.handle_error(e)

    def _save_text_report(self, report: DailyReport):
        """Save text format report."""
        filename = self.report_dir / f"daily_report_{report.date.strftime('%Y%m%d')}.txt"

        content = f"""
BLACK SWAN INDICATOR - DAILY REPORT
===================================
Date: {report.date.strftime('%Y-%m-%d')}

SUMMARY
-------
Checks Performed: {report.checks_performed}
Average Score: {report.average_score:.3f}
Maximum Score: {report.max_score:.3f}
Alerts Sent: {report.alerts_sent}
Data Quality: {report.data_quality}

STATUS DISTRIBUTION
------------------
"""

        for status, count in report.status_distribution.items():
            percentage = (count / report.checks_performed * 100) if report.checks_performed > 0 else 0  # noqa: E501
            content += f"{status:6}: {count:3d} ({percentage:5.1f}%)\n"

        # Add detailed results
        content += "\nDETAILED RESULTS\n"
        content += "----------------\n"
        content += f"{'Time':8} | {'Status':6} | {'Score':5} | {'Alert':5} | Components\n"
        content += "-" * 60 + "\n"

        for result in self.daily_results[-20:]:  # Last 20 entries
            content += (f"{result.timestamp.strftime('%H:%M:%S')} | "
                       f"{result.status.value:6} | "
                       f"{result.overall_score:5.2f} | "
                       f"{self._get_alert_level(result).value:5} | ")

            # Add component summary
            components = []
            for name, score in result.component_scores.items():
                if score.raw_score > 2.0:  # Only show elevated components
                    components.append(f"{name[:3]}:{score.raw_score:.1f}")
            content += ", ".join(components) + "\n"

        with open(filename, 'w') as f:
            f.write(content)

    def _save_json_report(self, report: DailyReport):
        """Save JSON format report."""
        filename = self.report_dir / f"daily_report_{report.date.strftime('%Y%m%d')}.json"

        data = {
            'date': report.date.isoformat(),
            'summary': {
                'checks_performed': report.checks_performed,
                'average_score': report.average_score,
                'max_score': report.max_score,
                'alerts_sent': report.alerts_sent,
                'data_quality': report.data_quality,
                'status_distribution': report.status_distribution
            },
            'results': [
                {
                    'timestamp': r.timestamp.isoformat(),
                    'status': r.status.value,
                    'score': r.overall_score,
                    'alert_level': self._get_alert_level(r).value,
                    'components': {
                        name: score.raw_score
                        for name, score in r.component_scores.items()
                    }
                }
                for r in self.daily_results
            ],
            'alerts': [
                {
                    'timestamp': a.timestamp.isoformat(),
                    'status': a.status.value,
                    'score': a.score,
                    'message': a.message
                }
                for a in self.alert_history
                if a.timestamp.date() == report.date.date()
            ]
        }

        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)

    def _save_csv_data(self):
        """Save results to CSV for analysis."""
        if not self.daily_results:
            return

        filename = self.report_dir / f"black_swan_data_{datetime.now(UTC).strftime('%Y%m%d')}.csv"

        data = []
        for result in self.daily_results:
            row = {
                'timestamp': result.timestamp,
                'status': result.status.value,
                'overall_score': result.overall_score,
                'alert_level': self._get_alert_level(result).value,
                'data_quality': result.data_quality.value
            }

            # Add component scores
            for name, score in result.component_scores.items():
                row[f'{name}_score'] = score.raw_score

            data.append(row)

        df = pd.DataFrame(data)
        df.to_csv(filename, index=False)

    def _email_daily_report(self, report: DailyReport):
        """Email the daily report."""
        subject = f"Black Swan Daily Report - {report.date.strftime('%Y-%m-%d')}"

        # Build summary
        body = f"""
Daily Black Swan Indicator Report

Date: {report.date.strftime('%Y-%m-%d')}
Checks: {report.checks_performed}
Average Score: {report.average_score:.3f}
Max Score: {report.max_score:.3f}
Alerts: {report.alerts_sent}

Status Distribution:
"""

        for status, count in report.status_distribution.items():
            body += f"  {status}: {count}\n"

        # Attach detailed report
        text_file = self.report_dir / f"daily_report_{report.date.strftime('%Y%m%d')}.txt"

        if EMAIL_AVAILABLE and text_file.exists():
            self._send_email_with_attachment(
                subject, body, str(text_file),
                self.alert_recipients.get('email', [])
            )

    def _send_email_with_attachment(self, subject: str, body: str,
                                  attachment_path: str, recipients: list[str]):
        """Send email with attachment."""
        try:
            smtp_config = self.config.get('smtp', {})

            msg = MIMEMultipart()
            msg['From'] = smtp_config.get('username')
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = subject

            msg.attach(MIMEText(body, 'plain'))

            # Attach file
            with open(attachment_path, 'rb') as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {os.path.basename(attachment_path)}'
                )
                msg.attach(part)

            # Send
            with smtplib.SMTP(smtp_config.get('server'), smtp_config.get('port')) as smtp:
                smtp.starttls()
                smtp.login(smtp_config.get('username'), smtp_config.get('password'))
                smtp.send_message(msg)

            self.logger.info("Daily report emailed successfully")

        except Exception as e:
            self.logger.error("Failed to email report: %s", e)

    # ==========================================================================
    # PRIVATE METHODS - Utilities
    # ==========================================================================
    def _load_configuration(self):
        """Load configuration settings."""
        # Schedule settings
        self.schedule_times = self.config.get('schedule_times', DEFAULT_SCHEDULE_TIMES)

        # Alert settings
        self.alert_channels = [
            NotificationChannel(ch) for ch in
            self.config.get('alert_channels', ['log'])
        ]
        self.alert_recipients = self.config.get('alert_recipients', {})
        self.alert_cooldown = self.config.get('alert_cooldown_minutes', ALERT_COOLDOWN_MINUTES)

        # Report settings
        self.report_dir = Path(self.config.get('report_dir', REPORT_OUTPUT_DIR))
        self.report_retention = self.config.get('report_retention_days', REPORT_RETENTION_DAYS)
        self.enable_daily_reports = bool(self.config.get('enable_daily_reports', False))

    def _init_tradov_integration(self):
        """Initialize Tradov system integration."""
        # Scheduler integration
        if TradovScheduler:
            try:
                self.tradov_scheduler = TradovScheduler.get_instance()
                self.logger.info("Integrated with Tradov scheduler")
            except Exception as e:
                self.logger.warning("Could not integrate with Tradov scheduler: %s", e)

        # Alert manager integration
        if TradovAlertManager:
            try:
                self.alert_manager = TradovAlertManager.get_instance()
                self.logger.info("Integrated with Tradov alert manager")
            except Exception as e:
                self.logger.warning("Could not integrate with alert manager: %s", e)

        # Email notifier
        if TradovEmailNotifier:
            try:
                self.email_notifier = TradovEmailNotifier()
                self.logger.info("Integrated with Tradov email notifier")
            except Exception as e:
                self.logger.warning("Could not integrate with email notifier: %s", e)

        # Trading calendar
        if TradovTradingCalendar:
            try:
                self.trading_calendar = TradovTradingCalendar()
                self.logger.info("Integrated with trading calendar")
            except Exception as e:
                self.logger.warning("Could not integrate with trading calendar: %s", e)

        # Data access
        if TradovDataAccess:
            try:
                self.data_access = TradovDataAccess()
                self.logger.info("Integrated with data access layer")
            except Exception as e:
                self.logger.warning("Could not integrate with data access: %s", e)

    def _setup_default_tasks(self):
        """Setup default scheduled tasks."""
        # Add default daily checks
        for time_str in self.schedule_times:
            self.add_daily_check(time_str)

        # Daily reports are disabled by default in the pair-trading deployment.
        self.add_daily_report()

        # Cleanup is only useful when daily report files are being created.
        if self.enable_daily_reports:
            self._add_cleanup_task()

        # Fire any check times that were already missed today (e.g. late startup)
        self._run_missed_startup_checks()

    def _run_missed_startup_checks(self) -> None:
        """
        Run any market-check tasks whose scheduled time has already passed today.

        Called once at startup so that a late start (e.g. 8 AM instead of 4 AM)
        still produces at least one risk snapshot before the first future check fires.
        Only MARKET_CHECK tasks are considered; report/cleanup tasks are skipped.
        """
        if self._restored_same_day_result:
            self.logger.debug("Startup cache restored; skipping Black Swan catch-up checks")
            return

        eastern_tz = pytz.timezone("US/Eastern")
        now = datetime.now(eastern_tz)
        today = now.date()

        missed: list[str] = []
        for task_id, task in self.scheduled_tasks.items():
            if task.task_type != ScheduleType.MARKET_CHECK:
                continue
            if not task.enabled:
                continue
            # schedule_time is "HH:MM" for daily checks; skip interval tasks
            try:
                scheduled_naive = datetime.strptime(
                    f"{today} {task.schedule_time}", "%Y-%m-%d %H:%M"
                )
                scheduled_dt = eastern_tz.localize(scheduled_naive)
            except ValueError:
                continue
            if scheduled_dt < now:
                missed.append(task_id)

        if not missed:
            return

        self.logger.debug(
            "Startup catch-up: running %d missed Black Swan check(s)",
            len(missed),
        )
        self.logger.debug("Startup catch-up task list: %s", missed)
        for task_id in missed:
            self.run_now(task_id)

    def _add_cleanup_task(self):
        """Add task to clean up old reports."""
        task_id = "cleanup_old_reports"

        def cleanup_callback():
            self._cleanup_old_files()

        task = ScheduledTask(
            task_id=task_id,
            task_type=ScheduleType.CLEANUP,
            schedule_time="02:00",  # 2 AM
            callback=cleanup_callback,
            enabled=True,
            last_run=None,
            next_run=None
        )

        self.scheduled_tasks[task_id] = task
        schedule.every().day.at("02:00").do(cleanup_callback).tag(task_id)

    def _cleanup_old_files(self):
        """Clean up old report files."""
        try:
            cutoff_date = datetime.now(UTC) - timedelta(days=self.report_retention)

            for file_path in self.report_dir.glob("*"):
                if file_path.is_file():
                    # Check file age
                    file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_time < cutoff_date:
                        file_path.unlink()
                        self.logger.info("Deleted old file: %s", file_path.name)

        except Exception as e:
            self.logger.error("Error during cleanup: %s", e)

    def _is_same_trading_day(self, timestamp: datetime) -> bool:
        """Return True when a timestamp falls on today's US/Eastern date."""
        eastern_tz = pytz.timezone("US/Eastern")
        now = datetime.now(eastern_tz)
        if timestamp.tzinfo is None:
            timestamp = eastern_tz.localize(timestamp)
        else:
            timestamp = timestamp.astimezone(eastern_tz)
        return timestamp.date() == now.date()

    def _is_market_hours(self) -> bool:
        """Check if current time is during market hours."""
        if self.trading_calendar and TRADOV_INTEGRATION:
            return self.trading_calendar.is_market_open()

        # Simple check for US market hours (9:30 AM - 4:00 PM ET)
        now = datetime.now(UTC)
        market_open = now.replace(hour=9, minute=30, second=0)
        market_close = now.replace(hour=16, minute=0, second=0)

        # Check if weekday
        if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False

        return market_open <= now <= market_close

    def _is_in_cooldown(self, status: RiskStatus) -> bool:
        """Check if alert is in cooldown period."""
        # Find last alert with same status
        cutoff_time = datetime.now(UTC) - timedelta(minutes=self.alert_cooldown)

        for alert in reversed(self.alert_history):
            if alert.status == status and alert.timestamp > cutoff_time:
                return True

        return False

    def _get_alert_level(self, result: BlackSwanResult) -> AlertLevel:
        """Derive an alert level from risk status (or use attached compatibility field)."""
        alert_level = getattr(result, "alert_level", None)
        if alert_level is not None:
            return alert_level

        if result.status == RiskStatus.RED:
            return AlertLevel.HIGH
        if result.status == RiskStatus.YELLOW:
            return AlertLevel.MEDIUM
        return AlertLevel.LOW

    def _attach_alert_level(self, result: BlackSwanResult) -> None:
        """Attach legacy alert_level attribute expected by report/alert code paths."""
        result.alert_level = self._get_alert_level(result)

    def _log_to_database(self, result: BlackSwanResult):
        """Persist a Black Swan check result to the SQLite database.

        Writes to the `black_swan_results` table (created on first write if absent).
        Component scores are serialised to JSON and stored in the `components` column.
        """
        if not self.data_access:
            return

        try:
            import json as _json

            # Ensure the table exists (idempotent)
            self.data_access.execute_write("""
                CREATE TABLE IF NOT EXISTS black_swan_results (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp   TEXT    NOT NULL,
                    status      TEXT    NOT NULL,
                    score       REAL    NOT NULL,
                    alert_level TEXT,
                    data_quality TEXT,
                    components  TEXT,
                    created_at  TEXT    DEFAULT (datetime('now'))
                )
            """)

            components_json = _json.dumps({
                name: {
                    "raw_score": score.raw_score,
                    "weighted_score": score.weighted_score,
                    "description": score.description,
                }
                for name, score in result.component_scores.items()
            })

            self.data_access.execute_write(
                """
                INSERT INTO black_swan_results
                    (timestamp, status, score, alert_level, data_quality, components)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    result.timestamp.isoformat(),
                    result.status.value,
                    result.overall_score,
                    self._get_alert_level(result).value,
                    result.data_quality.value,
                    components_json,
                ),
            )
            self.logger.debug(f"Black Swan result logged to DB: score={result.overall_score:.2f}")

        except Exception as e:
            self.logger.error("Failed to log Black Swan result to database: %s", e)

    def load_latest_result_from_database(self) -> BlackSwanResult | None:
        """Load the newest same-day Black Swan result from SQLite."""
        if not self.data_access:
            return None

        try:
            rows = self.data_access.execute_query(
                """
                SELECT timestamp, status, score, alert_level, data_quality, components
                FROM black_swan_results
                ORDER BY timestamp DESC
                LIMIT 1
                """
            )
            if not rows:
                return None

            row = rows[0]
            timestamp_raw = row["timestamp"]
            timestamp = datetime.fromisoformat(timestamp_raw)
            if not self._is_same_trading_day(timestamp):
                return None

            import json as _json

            component_payload = _json.loads(row["components"] or "{}")
            component_scores: dict[str, ComponentScore] = {}
            for name, payload in component_payload.items():
                if not isinstance(payload, dict):
                    continue
                component_scores[name] = ComponentScore(
                    name=name,
                    raw_score=float(payload.get("raw_score", 0.0)),
                    weight=float(getattr(self.indicator, "weights", {}).get(name, 0.0)),
                    weighted_score=float(payload.get("weighted_score", 0.0)),
                    description=str(payload.get("description", "")),
                )

            result = BlackSwanResult(
                timestamp=timestamp,
                overall_score=float(row["score"]),
                status=RiskStatus(row["status"]),
                component_scores=component_scores,
                data_quality=DataQuality(row["data_quality"]),
                calculation_time_ms=0.0,
                raw_data=None,
            )

            self.daily_results = [result]
            self.latest_result = result
            self._last_logged_check_status = result.status
            self._restored_same_day_result = True

            if hasattr(self.indicator, "score_history"):
                self.indicator.score_history = [(timestamp, result.overall_score)]

            self.logger.debug("Loaded cached Black Swan result from SQLite")
            return result

        except Exception as e:
            self.logger.debug("Could not load cached Black Swan result: %s", e)
            return None

    def get_latest_result(self, allow_calculation: bool = True) -> BlackSwanResult | None:
        """Return the latest same-day Black Swan result, if available."""
        if self.latest_result and self._is_same_trading_day(self.latest_result.timestamp):
            return self.latest_result

        cached_result = self.load_latest_result_from_database()
        if cached_result is not None or not allow_calculation:
            return cached_result

        return self._perform_market_check()

    def _run_scheduler(self):
        """Main scheduler loop."""
        self.logger.debug("Scheduler thread started")

        while self.running:
            try:
                # Run pending tasks
                schedule.run_pending()

                # Update next run times
                for task in self.scheduled_tasks.values():
                    if task.enabled:
                        jobs = schedule.get_jobs(task.task_id)
                        if jobs:
                            task.next_run = jobs[0].next_run

                # Sleep briefly
                time.sleep(1)  # thread-safe: time.sleep() intentional

            except Exception as e:
                self.logger.error("Scheduler error: %s", e)
                if self.error_handler:
                    self.error_handler.handle_error(e)

        self.logger.debug("Scheduler thread stopped")

    def _signal_handler(self, signum, frame):
        """Handle system signals."""
        previous_handler = self._previous_signal_handlers.get(signum)
        self.logger.info("Received signal %s", signum)
        self.stop()
        if TRADOV_INTEGRATION:
            return
        if previous_handler == signal.SIG_IGN:
            return
        if previous_handler == signal.SIG_DFL:
            signal.signal(signum, signal.SIG_DFL)
            os.kill(os.getpid(), signum)
            return
        if callable(previous_handler) and previous_handler is not self._signal_handler:
            previous_handler(signum, frame)

    # ==========================================================================
    # PUBLIC METHODS - Status and Reporting
    # ==========================================================================
    def get_status(self) -> dict[str, Any]:
        """
        Get current scheduler status.

        Returns:
            Dictionary with scheduler status
        """
        return {
            'running': self.running,
            'tasks': {
                task_id: {
                    'type': task.task_type.value,
                    'schedule': task.schedule_time,
                    'enabled': task.enabled,
                    'last_run': task.last_run.isoformat() if task.last_run else None,
                    'next_run': task.next_run.isoformat() if task.next_run else None
                }
                for task_id, task in self.scheduled_tasks.items()
            },
            'daily_checks': len(self.daily_results),
            'alerts_today': len([a for a in self.alert_history
                               if a.timestamp.date() == datetime.now(UTC).date()]),
            'last_result': {
                'status': self.daily_results[-1].status.value,
                'score': self.daily_results[-1].overall_score,
                'timestamp': self.daily_results[-1].timestamp.isoformat()
            } if self.daily_results else None
        }

    def get_alert_history(self, days: int = 7) -> list[dict[str, Any]]:
        """
        Get recent alert history.

        Args:
            days: Number of days of history

        Returns:
            List of alert records
        """
        cutoff = datetime.now(UTC) - timedelta(days=days)

        return [
            {
                'timestamp': alert.timestamp.isoformat(),
                'status': alert.status.value,
                'score': alert.score,
                'message': alert.message,
                'channels': [ch.value for ch in alert.channels]
            }
            for alert in self.alert_history
            if alert.timestamp >= cutoff
        ]

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_default_scheduler(config: dict | None = None) -> BlackSwanScheduler:
    """
    Create scheduler with default configuration.

    Args:
        config: Optional configuration overrides

    Returns:
        Configured scheduler instance
    """
    default_config = {
        'schedule_times': ['04:00', '09:15', '15:45'],
        'alert_channels': ['log', 'email'],
        'alert_on_yellow': True,
        'alert_on_red': True,
        'email_daily_report': True,
        'report_retention_days': 30
    }

    if config:
        default_config.update(config)

    return BlackSwanScheduler(default_config)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing

    # Create test configuration
    test_config = {
        'schedule_times': ['09:00', '12:00', '15:00'],
        'alert_channels': ['log'],
        'alert_on_yellow': True,
        'alert_on_red': True
    }

    # Initialize scheduler
    scheduler = BlackSwanScheduler(test_config)

    # Test alert channels
    print("Testing alert channels...")  # noqa: T201
    test_results = scheduler.test_alerts()
    for channel, success in test_results.items():
        icon = "\u2705" if success else "\u274c"
        print(f"  {icon} {channel}")  # noqa: T201

    # Show scheduled tasks
    status = scheduler.get_status()
    print(f"\nScheduled tasks ({len(status['tasks'])})")  # noqa: T201
    for task_id, task_info in status['tasks'].items():
        enabled = "enabled" if task_info['enabled'] else "disabled"
        print(f"  {task_id:<30} {task_info['schedule']:<25} [{enabled}]")  # noqa: T201

    # Run a manual check
    print("\nRunning manual check...")  # noqa: T201
    scheduler.run_now('daily_check_0900')

    # Show status
    status = scheduler.get_status()
    if status['last_result']:
        lr = status['last_result']
        print(f"Last result: {lr['status']}  score={lr['score']:.2f}  at {lr['timestamp']}")  # noqa: T201
    else:
        print("No check result available yet.")  # noqa: T201
