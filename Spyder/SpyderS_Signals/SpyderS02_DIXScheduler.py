#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderS_Signals
Module: SpyderS02_DIXScheduler.py
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
import json
import logging
import os
import time as time_module
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pytz
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

try:
    from SpyderS_Signals.SpyderS01_DIXCalculator import SpyderDIXCalculator
    from SpyderS_Signals.SpyderS02_DIXDemo import SpyderDIXDemo
    from SpyderS_Signals.SpyderS03_DIXVisualizer import SpyderDIXVisualizer
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
    from SpyderZ_Communication.SpyderZ01_EmailSender import SpyderEmailSender
except ImportError:
    # Fallback for standalone operation
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    SpyderLogger = logging

    class SpyderErrorHandler:
        def handle_error(self, error, code):
            logging.error(f"{code}: {error}")

    class SpyderEmailSender:
        def send_email(self, subject, body, attachments=None):
            logging.info(f"Email: {subject}\n{body}")


# ==============================================================================
# CONSTANTS
# ==============================================================================
# Scheduling Configuration
DAILY_CALCULATION_TIME = "18:30"  # 6:30 PM ET
MORNING_CHECK_TIME = "09:00"  # 9:00 AM ET
TIMEZONE = pytz.timezone("US/Eastern")

# Retry Configuration
MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 300  # 5 minutes

# Data Source Health Check
FINRA_CHECK_URL = "https://www.finra.org/finra-data/browse-catalog/short-sale-volume-data"
HEALTH_CHECK_TIMEOUT = 10

# Notification Settings
ALERT_EMAIL_RECIPIENTS = ["trader@example.com"]
ALERT_THRESHOLDS = {
    "extreme_bullish": 40.0,
    "bullish": 45.0,
    "bearish": 50.0,
    "extreme_bearish": 55.0,
}

# ==============================================================================
# ENUMS
# ==============================================================================


class SchedulerStatus(Enum):
    """Scheduler operational status"""

    IDLE = "idle"
    RUNNING = "running"
    ERROR = "error"
    RETRY = "retry"
    COMPLETED = "completed"


class DataFetchStatus(Enum):
    """Data fetching status"""

    PENDING = "pending"
    FETCHING = "fetching"
    SUCCESS = "success"
    FAILED = "failed"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================


@dataclass
class SchedulerConfig:
    """Configuration for DIX scheduler"""

    use_demo: bool
    enable_email_alerts: bool
    enable_visualizations: bool
    save_to_database: bool
    retry_on_failure: bool


@dataclass
class CalculationResult:
    """Result of scheduled calculation"""

    timestamp: datetime
    dix_value: float
    dix_percentage: float
    sentiment: str
    status: SchedulerStatus
    error_message: str | None
    execution_time: float


# ==============================================================================
# MAIN CLASS
# ==============================================================================


class SpyderDIXScheduler:
    """
    Automated DIX Calculation Scheduler.

    This class manages the automatic scheduling and execution of DIX
    calculations, including data fetching, error handling, and notifications.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        config: Scheduler configuration
        calculator: DIX calculator instance
        visualizer: DIX visualizer instance
        scheduler: APScheduler instance

    Example:
        >>> scheduler = SpyderDIXScheduler()
        >>> scheduler.initialize()
        >>> scheduler.start()
    """

    def __init__(self, config: SchedulerConfig | None = None):
        """
        Initialize the DIX Scheduler.

        Args:
            config: Optional scheduler configuration
        """
        self.logger = (
            SpyderLogger.get_logger(__name__)
            if hasattr(SpyderLogger, "get_logger")
            else logging.getLogger(__name__)
        )
        self.error_handler = SpyderErrorHandler()

        # Default configuration
        self.config = config or SchedulerConfig(
            use_demo=True,
            enable_email_alerts=True,
            enable_visualizations=True,
            save_to_database=True,
            retry_on_failure=True,
        )

        # Initialize components
        if self.config.use_demo:
            self.calculator = SpyderDIXDemo()
        else:
            self.calculator = SpyderDIXCalculator()

        self.visualizer = SpyderDIXVisualizer(use_demo=self.config.use_demo)
        self.email_sender = SpyderEmailSender()

        # Scheduler setup
        self.scheduler = BackgroundScheduler(timezone=TIMEZONE)

        # State tracking
        self.latest_result = None
        self.calculation_history = []
        self.status = SchedulerStatus.IDLE

        self.logger.info(f"{self.__class__.__name__} initialized")

    # ==========================================================================
    # PUBLIC METHODS - INITIALIZATION
    # ==========================================================================
    def initialize(self) -> bool:
        """
        Initialize scheduler components.

        Returns:
            bool: True if initialization successful
        """
        try:
            self.logger.info("Initializing DIX Scheduler...")

            # Initialize calculator
            if not self.calculator.initialize():
                raise Exception("Calculator initialization failed")

            # Initialize visualizer
            if self.config.enable_visualizations:
                if not self.visualizer.initialize():
                    raise Exception("Visualizer initialization failed")

            # Test data sources
            if not self._test_data_sources():
                raise Exception("Data source test failed")

            # Schedule jobs
            self._schedule_jobs()

            self.logger.info("DIX Scheduler initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Scheduler initialization failed: {e}")
            self.error_handler.handle_error(e, "SCHEDULER_INIT_ERROR")
            return False

    # ==========================================================================
    # PUBLIC METHODS - SCHEDULER CONTROL
    # ==========================================================================
    def start(self) -> None:
        """Start the scheduler."""
        try:
            self.scheduler.start()
            self.logger.info("DIX Scheduler started")

            # Run initial calculation
            self.logger.info("Running initial DIX calculation...")
            self.run_scheduled_calculation()

        except Exception as e:
            self.logger.error(f"Failed to start scheduler: {e}")
            self.error_handler.handle_error(e, "SCHEDULER_START_ERROR")

    def stop(self) -> None:
        """Stop the scheduler."""
        try:
            self.scheduler.shutdown(wait=True)
            self.logger.info("DIX Scheduler stopped")

        except Exception as e:
            self.logger.error(f"Error stopping scheduler: {e}")

    def run_scheduled_calculation(self) -> CalculationResult | None:
        """
        Run the scheduled DIX calculation with automatic data fetching.

        Returns:
            CalculationResult or None if failed
        """
        self.status = SchedulerStatus.RUNNING
        start_time = datetime.now()

        try:
            self.logger.info("=" * 60)
            self.logger.info(f"Starting scheduled DIX calculation at {start_time}")

            # Step 1: Check data availability
            if not self._wait_for_finra_data():
                raise Exception("FINRA data not available")

            # Step 2: Update S&P 500 constituents (weekly)
            if self._should_update_constituents():
                self._update_sp500_constituents()

            # Step 3: Calculate DIX
            results = self._calculate_with_retry()

            if not results:
                raise Exception("DIX calculation failed after retries")

            # Step 4: Process results
            calculation_result = self._process_results(results, start_time)

            # Step 5: Generate visualizations
            if self.config.enable_visualizations:
                self._generate_visualizations(results)

            # Step 6: Send notifications
            self._send_notifications(calculation_result)

            # Step 7: Save to database
            if self.config.save_to_database:
                self._save_to_database(calculation_result)

            self.status = SchedulerStatus.COMPLETED
            self.logger.info(
                f"DIX calculation completed successfully in "
                f"{calculation_result.execution_time:.1f} seconds"
            )

            return calculation_result

        except Exception as e:
            self.status = SchedulerStatus.ERROR
            self.logger.error(f"Scheduled calculation failed: {e}")
            self.error_handler.handle_error(e, "SCHEDULED_CALC_ERROR")

            # Send error notification
            if self.config.enable_email_alerts:
                self._send_error_notification(str(e))

            return None

    def get_latest_dix(self) -> dict | None:
        """
        Get the latest DIX calculation result.

        Returns:
            Dictionary with latest DIX data or None
        """
        if self.latest_result:
            age = datetime.now() - self.latest_result.timestamp

            # Return cached if less than 24 hours old
            if age.total_seconds() < 86400:
                return {
                    "dix_percentage": self.latest_result.dix_percentage,
                    "sentiment": self.latest_result.sentiment,
                    "timestamp": self.latest_result.timestamp,
                    "age_hours": age.total_seconds() / 3600,
                }

        # Try to calculate now
        self.logger.info("No recent DIX data, calculating now...")
        result = self.run_scheduled_calculation()

        if result:
            return {
                "dix_percentage": result.dix_percentage,
                "sentiment": result.sentiment,
                "timestamp": result.timestamp,
                "age_hours": 0,
            }

        return None

    # ==========================================================================
    # PRIVATE METHODS - SCHEDULING
    # ==========================================================================
    def _schedule_jobs(self) -> None:
        """Schedule all automated jobs."""

        # Daily DIX calculation at 6:30 PM ET
        self.scheduler.add_job(
            func=self.run_scheduled_calculation,
            trigger=CronTrigger(hour=18, minute=30, timezone=TIMEZONE),
            id="daily_dix_calculation",
            name="Daily DIX Calculation",
            misfire_grace_time=3600,  # 1 hour grace period
            coalesce=True,
            replace_existing=True,
        )

        # Morning check at 9:00 AM ET
        self.scheduler.add_job(
            func=self._morning_check,
            trigger=CronTrigger(hour=9, minute=0, timezone=TIMEZONE),
            id="morning_dix_check",
            name="Morning DIX Check",
            replace_existing=True,
        )

        # Weekly constituent update (Sundays at 10 PM ET)
        self.scheduler.add_job(
            func=self._update_sp500_constituents,
            trigger=CronTrigger(day_of_week="sun", hour=22, minute=0, timezone=TIMEZONE),
            id="weekly_constituent_update",
            name="Weekly S&P 500 Update",
            replace_existing=True,
        )

        self.logger.info("Scheduled jobs configured")

    def _morning_check(self) -> None:
        """Morning check using cached DIX data."""
        self.logger.info("Running morning DIX check...")

        dix_data = self.get_latest_dix()

        if dix_data:
            self.logger.info(
                f"Morning DIX: {dix_data['dix_percentage']:.2f}% "
                f"({dix_data['sentiment']}) - "
                f"Age: {dix_data['age_hours']:.1f} hours"
            )

            # Send morning update if requested
            if self.config.enable_email_alerts:
                self._send_morning_update(dix_data)

    # ==========================================================================
    # PRIVATE METHODS - DATA FETCHING
    # ==========================================================================
    def _wait_for_finra_data(self, max_wait_minutes: int = 30) -> bool:
        """
        Wait for FINRA data to become available.

        Args:
            max_wait_minutes: Maximum time to wait

        Returns:
            bool: True if data available
        """
        self.logger.info("Checking FINRA data availability...")

        # Get expected date
        expected_date = self._get_expected_finra_date()
        url = f"https://cdn.finra.org/equity/regsho/daily/CNMSshvol{expected_date}.txt"

        start_time = datetime.now()
        max_wait = timedelta(minutes=max_wait_minutes)

        while datetime.now() - start_time < max_wait:
            try:
                response = requests.head(url, timeout=HEALTH_CHECK_TIMEOUT)
                if response.status_code == 200:
                    self.logger.info("FINRA data is available")
                    return True

            except Exception as e:
                self.logger.debug(f"FINRA check failed: {e}")

            # Wait before retry
            self.logger.info("FINRA data not yet available, waiting...")
            time_module.sleep(60)  # Check every minute

        self.logger.error("FINRA data not available after timeout")
        return False

    def _calculate_with_retry(self) -> dict | None:
        """
        Calculate DIX with retry logic.

        Returns:
            Calculation results or None
        """
        for attempt in range(MAX_RETRY_ATTEMPTS):
            try:
                self.logger.info(f"DIX calculation attempt {attempt + 1}")

                # Run calculation
                results = self.calculator.run_calculation()

                if results:
                    return results

            except Exception as e:
                self.logger.error(f"Calculation attempt {attempt + 1} failed: {e}")

                if attempt < MAX_RETRY_ATTEMPTS - 1:
                    self.logger.info(f"Retrying in {RETRY_DELAY_SECONDS} seconds...")
                    time_module.sleep(RETRY_DELAY_SECONDS)

        return None

    def _update_sp500_constituents(self) -> None:
        """Update S&P 500 constituent list."""
        self.logger.info("Updating S&P 500 constituents...")

        try:
            # Force refresh of constituent list
            if hasattr(self.calculator, "_fetch_sp500_constituents"):
                self.calculator._fetch_sp500_constituents()
                self.logger.info("S&P 500 constituents updated successfully")

        except Exception as e:
            self.logger.error(f"Failed to update constituents: {e}")

    # ==========================================================================
    # PRIVATE METHODS - PROCESSING
    # ==========================================================================
    def _process_results(self, results: dict, start_time: datetime) -> CalculationResult:
        """Process calculation results."""

        dix_pct = results["dix_percentage"]

        # Determine sentiment
        if dix_pct < ALERT_THRESHOLDS["bullish"]:
            sentiment = "BULLISH"
        elif dix_pct > ALERT_THRESHOLDS["bearish"]:
            sentiment = "BEARISH"
        else:
            sentiment = "NEUTRAL"

        # Create result object
        calculation_result = CalculationResult(
            timestamp=datetime.now(),
            dix_value=results["dix"],
            dix_percentage=dix_pct,
            sentiment=sentiment,
            status=SchedulerStatus.COMPLETED,
            error_message=None,
            execution_time=(datetime.now() - start_time).total_seconds(),
        )

        # Update latest result
        self.latest_result = calculation_result
        self.calculation_history.append(calculation_result)

        # Keep only last 30 days of history
        if len(self.calculation_history) > 30:
            self.calculation_history = self.calculation_history[-30:]

        return calculation_result

    def _generate_visualizations(self, results: dict) -> None:
        """Generate DIX visualizations."""
        try:
            self.logger.info("Generating DIX visualizations...")

            # Create dashboard
            dashboard_path = self.visualizer.create_summary_dashboard(results)
            self.logger.info(f"Dashboard created: {dashboard_path}")

            # Create time series if enough history
            if len(self.calculation_history) >= 5:
                # Convert history to format expected by visualizer
                history_data = []
                for calc in self.calculation_history[-10:]:
                    history_data.append(
                        {
                            "date": calc.timestamp.strftime("%Y%m%d"),
                            "date_obj": calc.timestamp,
                            "dix_percentage": calc.dix_percentage,
                            "dix": calc.dix_value,
                        }
                    )

                ts_path = self.visualizer.create_time_series_chart(history_data)
                self.logger.info(f"Time series created: {ts_path}")

            # Generate report
            report_path = self.visualizer.generate_analysis_report(results)
            self.logger.info(f"Report generated: {report_path}")

        except Exception as e:
            self.logger.error(f"Visualization generation failed: {e}")

    # ==========================================================================
    # PRIVATE METHODS - NOTIFICATIONS
    # ==========================================================================
    def _send_notifications(self, result: CalculationResult) -> None:
        """Send notifications based on DIX results."""

        if not self.config.enable_email_alerts:
            return

        try:
            # Check for extreme values
            if result.dix_percentage < ALERT_THRESHOLDS["extreme_bullish"]:
                self._send_alert("DIX EXTREME BULLISH", result)
            elif result.dix_percentage > ALERT_THRESHOLDS["extreme_bearish"]:
                self._send_alert("DIX EXTREME BEARISH", result)

            # Check for threshold crossings
            if len(self.calculation_history) >= 2:
                prev = self.calculation_history[-2]
                curr = result

                # Bullish crossing
                if prev.dix_percentage >= 45 and curr.dix_percentage < 45:
                    self._send_alert("DIX BULLISH CROSSING", result)

                # Bearish crossing
                elif prev.dix_percentage <= 50 and curr.dix_percentage > 50:
                    self._send_alert("DIX BEARISH CROSSING", result)

            # Send daily summary
            self._send_daily_summary(result)

        except Exception as e:
            self.logger.error(f"Failed to send notifications: {e}")

    def _send_alert(self, alert_type: str, result: CalculationResult) -> None:
        """Send alert email."""

        subject = f"🚨 {alert_type} - DIX at {result.dix_percentage:.2f}%"

        body = f"""
DIX ALERT: {alert_type}

Current DIX: {result.dix_percentage:.2f}%
Sentiment: {result.sentiment}
Time: {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

Trading Implications:
"""

        if result.sentiment == "BULLISH":
            body += """
- Consider aggressive call positions
- Reduce or eliminate hedges
- Look for pullbacks to enter long positions
"""
        elif result.sentiment == "BEARISH":
            body += """
- Consider aggressive put positions
- Increase portfolio hedges
- Look for rallies to enter short positions
"""

        self.email_sender.send_email(subject=subject, body=body, recipients=ALERT_EMAIL_RECIPIENTS)

    def _send_daily_summary(self, result: CalculationResult) -> None:
        """Send daily DIX summary email."""

        subject = f"DIX Daily Summary - {result.dix_percentage:.2f}% ({result.sentiment})"

        body = f"""
DIX DAILY SUMMARY
================

Date: {result.timestamp.strftime('%Y-%m-%d')}
DIX Value: {result.dix_percentage:.2f}%
Sentiment: {result.sentiment}
Calculation Time: {result.execution_time:.1f} seconds

Market Outlook:
"""

        if result.dix_percentage < 42:
            body += "🟢 STRONG BULLISH - Aggressive long positioning recommended"
        elif result.dix_percentage < 45:
            body += "🟢 BULLISH - Favor call positions"
        elif result.dix_percentage > 53:
            body += "🔴 STRONG BEARISH - Aggressive hedging recommended"
        elif result.dix_percentage > 50:
            body += "🔴 BEARISH - Favor put positions"
        else:
            body += "🟡 NEUTRAL - Consider range-bound strategies"

        # Add historical context
        if len(self.calculation_history) >= 5:
            body += "\n\nLast 5 Days:\n"
            for calc in self.calculation_history[-5:]:
                body += f"{calc.timestamp.strftime('%Y-%m-%d')}: "
                body += f"{calc.dix_percentage:.2f}% ({calc.sentiment})\n"

        # Get report path
        report_path = f"/home/ubuntu/spyder_dix_charts/dix_analysis_report_{
            result.timestamp.strftime('%Y%m%d')}.md"

        self.email_sender.send_email(
            subject=subject,
            body=body,
            recipients=ALERT_EMAIL_RECIPIENTS,
            attachments=[report_path] if os.path.exists(report_path) else None,
        )

    def _send_error_notification(self, error_message: str) -> None:
        """Send error notification."""

        subject = "❌ DIX Calculation Error"
        body = f"""
DIX CALCULATION ERROR
====================

Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Error: {error_message}

The scheduled DIX calculation failed. Please check the system logs.

Last successful calculation:
"""

        if self.latest_result:
            body += f"""
Date: {self.latest_result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
DIX: {self.latest_result.dix_percentage:.2f}%
Age: {(datetime.now() - self.latest_result.timestamp).total_seconds() / 3600:.1f} hours
"""
        else:
            body += "No previous calculation available"

        self.email_sender.send_email(subject=subject, body=body, recipients=ALERT_EMAIL_RECIPIENTS)

    def _send_morning_update(self, dix_data: dict) -> None:
        """Send morning DIX update."""

        subject = f"DIX Morning Update - {dix_data['dix_percentage']:.2f}%"

        body = f"""
DIX MORNING UPDATE
==================

Current DIX: {dix_data['dix_percentage']:.2f}%
Sentiment: {dix_data['sentiment']}
Data Age: {dix_data['age_hours']:.1f} hours

Today's Trading Bias:
"""

        if dix_data["sentiment"] == "BULLISH":
            body += """
📈 BULLISH BIAS
- Favor call positions
- Look for dips to buy
- Consider reduced hedging
"""
        elif dix_data["sentiment"] == "BEARISH":
            body += """
📉 BEARISH BIAS
- Favor put positions
- Look for rallies to short
- Maintain full hedges
"""
        else:
            body += """
➡️ NEUTRAL BIAS
- No directional edge
- Focus on range trades
- Standard risk management
"""

        self.email_sender.send_email(subject=subject, body=body, recipients=ALERT_EMAIL_RECIPIENTS)

    # ==========================================================================
    # PRIVATE METHODS - DATABASE
    # ==========================================================================
    def _save_to_database(self, result: CalculationResult) -> None:
        """Save results to database."""
        try:
            # This would integrate with your database module
            # For now, we'll save to a JSON file
            data = {
                "timestamp": result.timestamp.isoformat(),
                "dix_value": result.dix_value,
                "dix_percentage": result.dix_percentage,
                "sentiment": result.sentiment,
                "execution_time": result.execution_time,
            }

            filename = f"/home/ubuntu/dix_history_{result.timestamp.strftime('%Y%m%d')}.json"
            with open(filename, "w") as f:
                json.dump(data, f, indent=2)

            self.logger.info(f"Results saved to {filename}")

        except Exception as e:
            self.logger.error(f"Failed to save to database: {e}")

    # ==========================================================================
    # PRIVATE METHODS - UTILITIES
    # ==========================================================================
    def _test_data_sources(self) -> bool:
        """Test all data sources are accessible."""

        self.logger.info("Testing data sources...")

        # Test FINRA
        try:
            response = requests.head(
                "https://www.finra.org/finra-data/browse-catalog/short-sale-volume-data",
                timeout=HEALTH_CHECK_TIMEOUT,
            )
            if response.status_code != 200:
                self.logger.warning("FINRA site returned non-200 status")
        except Exception as e:
            self.logger.error(f"FINRA test failed: {e}")
            return False

        self.logger.info("Data source tests passed")
        return True

    def _get_expected_finra_date(self) -> str:
        """Get expected FINRA data date."""

        now = datetime.now(TIMEZONE)

        # If before 6 PM ET, expect yesterday's data
        if now.hour < 18:
            target = now - timedelta(days=1)
        else:
            target = now

        # Skip weekends
        while target.weekday() >= 5:
            target -= timedelta(days=1)

        return target.strftime("%Y%m%d")

    def _should_update_constituents(self) -> bool:
        """Check if constituents should be updated."""

        # Update on Sundays or if never updated
        return datetime.now().weekday() == 6

    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def cleanup(self) -> None:
        """Clean up scheduler resources."""
        self.stop()
        self.logger.info("DIX Scheduler cleanup completed")


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================


def create_dix_scheduler(use_demo: bool = True) -> SpyderDIXScheduler:
    """
    Create and configure DIX scheduler.

    Args:
        use_demo: Use demo mode

    Returns:
        Configured scheduler instance
    """
    config = SchedulerConfig(
        use_demo=use_demo,
        enable_email_alerts=True,
        enable_visualizations=True,
        save_to_database=True,
        retry_on_failure=True,
    )

    scheduler = SpyderDIXScheduler(config)
    return scheduler


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code

    # Create scheduler
    scheduler = create_dix_scheduler(use_demo=True)

    if scheduler.initialize():

        # Run test calculation
        result = scheduler.run_scheduled_calculation()

        if result:
            pass

        # Show scheduled jobs
        for _job in scheduler.scheduler.get_jobs():
            pass

        # Test morning check
        scheduler._morning_check()

        # Run scheduler for demo (30 seconds)
        scheduler.start()
        time_module.sleep(30)
        scheduler.stop()

    else:
        pass
