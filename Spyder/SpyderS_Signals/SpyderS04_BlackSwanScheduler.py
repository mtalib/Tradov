#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderS_Signals
Module: SpyderS04_BlackSwanScheduler.py
Purpose: Automated scheduler for Black Swan risk monitoring, alerting, and reporting

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-03-27 Time: 00:00:00

Description:
    Provides fully automated, time-driven scheduling of Black Swan risk checks
    for the SPY options trading system. Orchestrates data collection (via
    BlackSwanDataCollector / SpyderS06), risk calculation (via BlackSwanCalculator /
    SpyderS07), alert dispatch, and daily report generation.

    When integrated with the Spyder system (SPYDER_INTEGRATION=True), all tasks are
    registered with SpyderA04_Scheduler. In standalone mode, the `schedule` library
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
    LOG       Always available; writes a WARNING-level log entry via SpyderLogger
    EMAIL     Via SpyderJ02_EmailNotifier (Spyder mode) or direct SMTP (standalone)
    SLACK     Stub — logs "not yet implemented"; planned for future release
    TELEGRAM  Stub — logs "not yet implemented"; planned for future release

Report Generation (daily at 17:00 ET):
    Three files are written to the `report_dir` directory (default: black_swan_reports/):
        daily_report_YYYYMMDD.txt    Human-readable summary with status distribution
        daily_report_YYYYMMDD.json   Structured JSON for downstream processing
        black_swan_data_YYYYMMDD.csv Per-row time-series for quantitative analysis
    Reports can optionally be emailed (set `email_daily_report: True` in config).

Spyder Integration:
    When SPYDER_INTEGRATION=True the following Spyder modules are used:
        SpyderA04_Scheduler         Task scheduling and cron management
        SpyderJ01_AlertManager      Alert routing and deduplication
        SpyderJ02_EmailNotifier     Email delivery
        SpyderU10_TradingCalendar   Accurate market-hours and holiday detection
        SpyderH01_DataAccessLayer   SQLite persistence of check results

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
from datetime import datetime, timedelta
from typing import Any, Callable
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
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
    from SpyderU_Utilities.SpyderU03_DateTimeUtils import SpyderDateTimeUtils
    from SpyderU_Utilities.SpyderU10_TradingCalendar import SpyderTradingCalendar
    from SpyderA_Core.SpyderA04_Scheduler import SpyderScheduler
    from SpyderJ_Alerts.SpyderJ01_AlertManager import SpyderAlertManager
    from SpyderJ_Alerts.SpyderJ02_EmailNotifier import SpyderEmailNotifier
    from SpyderH_Storage.SpyderH01_DataAccessLayer import SpyderDataAccess
    SPYDER_INTEGRATION = True
except ImportError:
    # Fallback for standalone operation
    SpyderLogger = logging
    SpyderErrorHandler = None
    SpyderDateTimeUtils = None
    SpyderTradingCalendar = None
    SpyderScheduler = None
    SpyderAlertManager = None
    SpyderEmailNotifier = None
    SpyderDataAccess = None
    SPYDER_INTEGRATION = False

# Import Black Swan modules
try:
    from SpyderS_Signals.SpyderS06_BlackSwanDataCollector import BlackSwanDataCollector
    from SpyderS_Signals.SpyderS07_BlackSwanCalculator import (
        BlackSwanCalculator, BlackSwanIndicatorResult, RiskStatus
    )
except ImportError:
    from SpyderS06_BlackSwanDataCollector import BlackSwanDataCollector
    from SpyderS07_BlackSwanCalculator import (
        BlackSwanCalculator, BlackSwanIndicatorResult, RiskStatus
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
    with Spyder's scheduling system when available.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        collector: Data collector instance
        calculator: Risk calculator instance
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
        if SPYDER_INTEGRATION:
            self.logger = SpyderLogger.get_logger(__name__)
            self.error_handler = SpyderErrorHandler()
        else:
            logging.basicConfig(level=logging.INFO)
            self.logger = logging.getLogger(__name__)
            self.error_handler = None

        # Configuration
        self.config = config or {}
        self._load_configuration()

        # Initialize components
        self.collector = BlackSwanDataCollector(self.config)
        self.calculator = BlackSwanCalculator(self.config)

        # Spyder integration
        self.spyder_scheduler = None
        self.alert_manager = None
        self.email_notifier = None
        self.trading_calendar = None
        self.data_access = None

        if SPYDER_INTEGRATION:
            self._init_spyder_integration()

        # Scheduler state
        self.scheduled_tasks: dict[str, ScheduledTask] = {}
        self.alert_history: list[AlertRecord] = []
        self.daily_results: list[BlackSwanIndicatorResult] = []
        self.running = False
        self.scheduler_thread: threading.Thread | None = None

        # Create output directory
        self.report_dir = Path(self.config.get('report_dir', REPORT_OUTPUT_DIR))
        self.report_dir.mkdir(exist_ok=True)

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Initialize default tasks
        self._setup_default_tasks()

        self.logger.info("Black Swan Scheduler initialized")

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
        if self.spyder_scheduler and SPYDER_INTEGRATION:
            self.spyder_scheduler.schedule_daily(time_str, check_callback, task_id)
        else:
            schedule.every().day.at(time_str).do(check_callback).tag(task_id)

        self.logger.info(f"Added daily check at {time_str}")
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

        self.logger.info(f"Added interval check every {minutes} minutes")
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

        self.logger.info(f"Added daily report at {time_str}")
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

            # Remove from Spyder scheduler if integrated
            if self.spyder_scheduler and SPYDER_INTEGRATION:
                try:
                    self.spyder_scheduler.remove_task(task_id)
                except Exception as e:
                    self.logger.debug(f"Failed to remove task {task_id} from Spyder scheduler: {e}")

            del self.scheduled_tasks[task_id]
            self.logger.info(f"Removed task: {task_id}")
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
        self.logger.info("Starting Black Swan Scheduler")

        # If integrated with Spyder, let it handle scheduling
        if self.spyder_scheduler and SPYDER_INTEGRATION:
            self.logger.info("Using Spyder scheduler")
            # Tasks already registered with Spyder scheduler
        else:
            # Run standalone scheduler
            self.scheduler_thread = threading.Thread(target=self._run_scheduler)
            self.scheduler_thread.daemon = daemon
            self.scheduler_thread.start()

    def stop(self):
        """Stop the scheduler."""
        self.logger.info("Stopping Black Swan Scheduler")
        self.running = False

        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)

        # Clear schedules
        schedule.clear()

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
                    task.last_run = datetime.now()
                    return True
                except Exception as e:
                    self.logger.error(f"Error running task {task_id}: {e}")
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

        self.logger.info(f"Alert channels configured: {[c.value for c in channels]}")

    def test_alerts(self) -> dict[str, bool]:
        """
        Test all configured alert channels.

        Returns:
            Dictionary of channel -> success status
        """
        results = {}

        test_message = f"Black Swan Indicator test alert - {datetime.now()}"

        for channel in self.alert_channels:
            try:
                if channel == NotificationChannel.EMAIL:
                    success = self._send_email_alert("TEST", test_message, test=True)
                elif channel == NotificationChannel.LOG:
                    self.logger.info(f"TEST ALERT: {test_message}")
                    success = True
                else:
                    success = False

                results[channel.value] = success

            except Exception as e:
                self.logger.error(f"Alert test failed for {channel.value}: {e}")
                results[channel.value] = False

        return results

    # ==========================================================================
    # PRIVATE METHODS - Core Operations
    # ==========================================================================
    def _perform_market_check(self):
        """Perform a market check and process results."""
        try:
            self.logger.info("Performing scheduled market check")

            # Collect data and calculate indicator
            market_data = self.collector.collect_all_data()
            result = self.calculator.calculate_indicator(market_data)

            # Store result
            self.daily_results.append(result)

            # Log to database if available
            if self.data_access:
                self._log_to_database(result)

            # Check for alerts
            self._check_and_send_alerts(result)

            # Update last run time
            for task in self.scheduled_tasks.values():
                if task.task_type == ScheduleType.MARKET_CHECK:
                    task.last_run = datetime.now()

            self.logger.info(f"Market check complete - Status: {result.status.value}, "
                           f"Score: {result.overall_score:.2f}")

        except Exception as e:
            self.logger.error(f"Error in market check: {e}")
            if self.error_handler:
                self.error_handler.handle_error(e)

    def _check_and_send_alerts(self, result: BlackSwanIndicatorResult):
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
                         if alert.timestamp.date() == datetime.now().date())
        if today_alerts >= MAX_DAILY_ALERTS:
            self.logger.warning("Daily alert limit reached")
            return

        # Send alerts
        self._send_alerts(result, alert_reason)

        # Record alert
        alert_record = AlertRecord(
            timestamp=datetime.now(),
            status=result.status,
            score=result.overall_score,
            message=alert_reason,
            channels=self.alert_channels
        )
        self.alert_history.append(alert_record)

        # Trim history
        if len(self.alert_history) > 100:
            self.alert_history = self.alert_history[-100:]

    def _send_alerts(self, result: BlackSwanIndicatorResult, reason: str):
        """Send alerts through configured channels."""
        # Build alert message
        message = self._build_alert_message(result, reason)

        for channel in self.alert_channels:
            try:
                if channel == NotificationChannel.EMAIL:
                    self._send_email_alert(result.status.value, message)

                elif channel == NotificationChannel.LOG:
                    self.logger.warning(f"BLACK SWAN ALERT: {message}")

                elif channel == NotificationChannel.SLACK:
                    self._send_slack_alert(message)

                elif channel == NotificationChannel.TELEGRAM:
                    self._send_telegram_alert(message)

                # Add other channels as needed

            except Exception as e:
                self.logger.error(f"Failed to send alert via {channel.value}: {e}")

    def _build_alert_message(self, result: BlackSwanIndicatorResult, reason: str) -> str:
        """Build detailed alert message."""
        message = f"""
BLACK SWAN INDICATOR ALERT
==========================
{reason}

Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}
Status: {result.status.value}
Overall Score: {result.overall_score:.2f}
Alert Level: {result.alert_level.name}

Component Breakdown:
"""

        for name, score in result.component_scores.items():
            message += f"- {name.replace('_', ' ').title()}: {score.raw_score:.2f} - {score.description}\n"

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

        # Use Spyder email notifier if available
        if self.email_notifier and SPYDER_INTEGRATION:
            try:
                return self.email_notifier.send_alert(
                    subject=f"Black Swan {level} Alert",
                    body=message,
                    recipients=self.alert_recipients.get('email', [])
                )
            except Exception as e:
                self.logger.error(f"Spyder email notifier failed: {e}")

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

            self.logger.info(f"Email alert sent to {len(recipients)} recipients")
            return True

        except Exception as e:
            self.logger.error(f"Failed to send email: {e}")
            return False

    def _send_slack_alert(self, message: str):
        """Send Slack alert.

        Preferred path: SpyderJ03_WebhookNotifier (Slack channel).
        Fallback: direct urllib POST to `slack_webhook_url` from config.
        """
        # ── Preferred path: use SpyderJ03_WebhookNotifier ─────────────────────
        try:
            from Spyder.SpyderJ_Alerts.SpyderJ03_WebhookNotifier import WebhookNotifier
            notifier = WebhookNotifier()
            notifier.send_slack(message=message)
            self.logger.info("Slack alert dispatched via SpyderJ03_WebhookNotifier")
            return
        except Exception:
            pass  # J03 unavailable or not configured — use direct fallback

        # ── Fallback: direct urllib POST ───────────────────────────────────────
        webhook_url = self.config.get("slack_webhook_url")
        if not webhook_url:
            self.logger.warning("Slack webhook URL not configured — skipping Slack alert")
            return
        try:
            import json as _json
            import urllib.request
            payload = _json.dumps({"text": message}).encode()
            req = urllib.request.Request(
                webhook_url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
                if resp.status == 200:
                    self.logger.info("Slack alert sent via direct webhook")
                else:
                    self.logger.warning(f"Slack webhook returned status {resp.status}")
        except Exception as e:
            self.logger.error(f"Failed to send Slack alert: {e}", exc_info=True)

    def _send_telegram_alert(self, message: str):
        """Send Telegram alert via SpyderJ05_TelegramBot.

        Falls back to a direct Bot API call when the Spyder integration is
        unavailable. Requires `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in
        the environment (read from .env by SpyderA03_Configuration).
        """
        # ── Preferred path: use SpyderJ05_TelegramBot ─────────────────────────
        try:
            from SpyderJ_Alerts.SpyderJ05_TelegramBot import TelegramBot
            bot = TelegramBot()
            last_status = getattr(self, "_last_alert_status", None)
            severity = "critical" if last_status and getattr(last_status, "value", "") == "RED" else "warning"
            bot.send_alert(title="Black Swan Alert", message=message, severity=severity)
            self.logger.info("Telegram alert dispatched via SpyderJ05_TelegramBot")
            return
        except Exception as e:
            self.logger.debug(f"SpyderJ05_TelegramBot unavailable, using fallback: {e}")

        # ── Fallback: direct Bot API call ─────────────────────────────────────
        import os
        import urllib.request
        import urllib.parse
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            self.logger.warning("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set — skipping")
            return
        try:
            params = urllib.parse.urlencode({"chat_id": chat_id, "text": message}).encode()
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            req = urllib.request.Request(url, data=params, method="POST")  # noqa: S310
            with urllib.request.urlopen(req, timeout=10):  # noqa: S310
                self.logger.info("Telegram alert sent via direct Bot API")
        except Exception as e:
            self.logger.error(f"Failed to send Telegram alert: {e}")

    # ==========================================================================
    # PRIVATE METHODS - Report Generation
    # ==========================================================================
    def _generate_daily_report(self):
        """Generate daily summary report."""
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
                date=datetime.now(),
                checks_performed=len(self.daily_results),
                average_score=np.mean(scores),
                max_score=np.max(scores),
                status_distribution={
                    status.value: count
                    for status, count in status_counts.items()
                },
                alerts_sent=len([a for a in self.alert_history
                               if a.timestamp.date() == datetime.now().date()]),
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
            self.logger.error(f"Error generating daily report: {e}")
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
            percentage = (count / report.checks_performed * 100) if report.checks_performed > 0 else 0
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
                       f"{result.alert_level.value:5} | ")

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
                    'alert_level': r.alert_level.value,
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

        filename = self.report_dir / f"black_swan_data_{datetime.now().strftime('%Y%m%d')}.csv"

        data = []
        for result in self.daily_results:
            row = {
                'timestamp': result.timestamp,
                'status': result.status.value,
                'overall_score': result.overall_score,
                'alert_level': result.alert_level.value,
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
            self.logger.error(f"Failed to email report: {e}")

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

    def _init_spyder_integration(self):
        """Initialize Spyder system integration."""
        # Scheduler integration
        if SpyderScheduler:
            try:
                self.spyder_scheduler = SpyderScheduler.get_instance()
                self.logger.info("Integrated with Spyder scheduler")
            except Exception as e:
                self.logger.warning(f"Could not integrate with Spyder scheduler: {e}")

        # Alert manager integration
        if SpyderAlertManager:
            try:
                self.alert_manager = SpyderAlertManager.get_instance()
                self.logger.info("Integrated with Spyder alert manager")
            except Exception as e:
                self.logger.warning(f"Could not integrate with alert manager: {e}")

        # Email notifier
        if SpyderEmailNotifier:
            try:
                self.email_notifier = SpyderEmailNotifier()
                self.logger.info("Integrated with Spyder email notifier")
            except Exception as e:
                self.logger.warning(f"Could not integrate with email notifier: {e}")

        # Trading calendar
        if SpyderTradingCalendar:
            try:
                self.trading_calendar = SpyderTradingCalendar()
                self.logger.info("Integrated with trading calendar")
            except Exception as e:
                self.logger.warning(f"Could not integrate with trading calendar: {e}")

        # Data access
        if SpyderDataAccess:
            try:
                self.data_access = SpyderDataAccess()
                self.logger.info("Integrated with data access layer")
            except Exception as e:
                self.logger.warning(f"Could not integrate with data access: {e}")

    def _setup_default_tasks(self):
        """Setup default scheduled tasks."""
        # Add default daily checks
        for time_str in self.schedule_times:
            self.add_daily_check(time_str)

        # Add daily report
        self.add_daily_report()

        # Add cleanup task
        self._add_cleanup_task()

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
            cutoff_date = datetime.now() - timedelta(days=self.report_retention)

            for file_path in self.report_dir.glob("*"):
                if file_path.is_file():
                    # Check file age
                    file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_time < cutoff_date:
                        file_path.unlink()
                        self.logger.info(f"Deleted old file: {file_path.name}")

        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

    def _is_market_hours(self) -> bool:
        """Check if current time is during market hours."""
        if self.trading_calendar and SPYDER_INTEGRATION:
            return self.trading_calendar.is_market_open()

        # Simple check for US market hours (9:30 AM - 4:00 PM ET)
        now = datetime.now()
        market_open = now.replace(hour=9, minute=30, second=0)
        market_close = now.replace(hour=16, minute=0, second=0)

        # Check if weekday
        if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False

        return market_open <= now <= market_close

    def _is_in_cooldown(self, status: RiskStatus) -> bool:
        """Check if alert is in cooldown period."""
        # Find last alert with same status
        cutoff_time = datetime.now() - timedelta(minutes=self.alert_cooldown)

        for alert in reversed(self.alert_history):
            if alert.status == status and alert.timestamp > cutoff_time:
                return True

        return False

    def _log_to_database(self, result: BlackSwanIndicatorResult):
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
                    getattr(result, "alert_level", None) and result.alert_level.value,
                    result.data_quality.value,
                    components_json,
                ),
            )
            self.logger.debug(f"Black Swan result logged to DB: score={result.overall_score:.2f}")

        except Exception as e:
            self.logger.error(f"Failed to log Black Swan result to database: {e}")

    def _run_scheduler(self):
        """Main scheduler loop."""
        self.logger.info("Scheduler thread started")

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
                self.logger.error(f"Scheduler error: {e}")
                if self.error_handler:
                    self.error_handler.handle_error(e)

        self.logger.info("Scheduler thread stopped")

    def _signal_handler(self, signum, frame):
        """Handle system signals."""
        self.logger.info(f"Received signal {signum}")
        self.stop()

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
                               if a.timestamp.date() == datetime.now().date()]),
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
        cutoff = datetime.now() - timedelta(days=days)

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
    print("Testing alert channels...")
    test_results = scheduler.test_alerts()
    for channel, success in test_results.items():
        icon = "\u2705" if success else "\u274c"
        print(f"  {icon} {channel}")

    # Show scheduled tasks
    status = scheduler.get_status()
    print(f"\nScheduled tasks ({len(status['tasks'])})")
    for task_id, task_info in status['tasks'].items():
        enabled = "enabled" if task_info['enabled'] else "disabled"
        print(f"  {task_id:<30} {task_info['schedule']:<25} [{enabled}]")

    # Run a manual check
    print("\nRunning manual check...")
    scheduler.run_now('daily_check_0900')

    # Show status
    status = scheduler.get_status()
    if status['last_result']:
        lr = status['last_result']
        print(f"Last result: {lr['status']}  score={lr['score']:.2f}  at {lr['timestamp']}")
    else:
        print("No check result available yet.")

