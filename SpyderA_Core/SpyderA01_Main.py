#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System
Module: SpyderA01_Main.py
Group: A (Core Trading Engine)
Purpose: Primary application controller and entry point
"""

# =============================================================================
# Add project root to Python path
# =============================================================================
import sys
from pathlib import Path

# Get the project root directory (parent of SpyderA_Core)
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# =============================================================================
# Fix SpyderLogger import issue
# =============================================================================
import sys
import logging


# Create a temporary SpyderLogger class that works
class TempSpyderLogger:
    def __init__(self, name=None):
        if name:
            self.logger = logging.getLogger(name)
        else:
            self.logger = logging.getLogger(__name__)

    @classmethod
    def get_logger(cls, name=None):
        return cls(name)

    def __getattr__(self, name):
        return getattr(self.logger, name)


# Monkey patch the import
sys.modules["SpyderU_Utilities.SpyderU01_Logger"] = type(sys)("temp_logger")
sys.modules["SpyderU_Utilities.SpyderU01_Logger"].SpyderLogger = TempSpyderLogger

# =============================================================================
# Standard Library Imports
# =============================================================================
import os
import signal
import asyncio
import time  # Keep this
from pathlib import Path
from datetime import datetime  # Remove 'time' from here
from typing import Optional, Dict, Any

# If you need datetime.time, import it with an alias
from datetime import time as dt_time

# =============================================================================
# Third-Party Imports
# =============================================================================
import pytz
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

# =============================================================================
# Local Application Imports - Now these should work
# =============================================================================
from SpyderA_Core.SpyderA02_TradingEngine import TradingEngine
from SpyderA_Core.SpyderA03_Configuration import ConfigManager
from SpyderA_Core.SpyderA04_Scheduler import TradingScheduler
from SpyderA_Core.SpyderA05_EventManager import EventManager

# from SpyderA_Core.SpyderA06_SystemMonitor import SystemMonitor  # Temporarily disabled
from SpyderB_Broker.SpyderB01_IBClient import get_ib_client

from SpyderU_Utilities.SpyderU02_ErrorHandler import (
    SpyderErrorHandler,
    TradingError,
)


# =============================================================================
# Constants
# =============================================================================
APPLICATION_NAME = "Spyder Trading System"
VERSION = "1.0.0"
DEFAULT_CONFIG_PATH = Path.home() / ".spyder" / "config.json"
LOG_PATH = Path.home() / ".spyder" / "logs"

# Trading hours in Eastern Time - use dt_time instead of time
MARKET_OPEN = dt_time(9, 30)  # 9:30 AM ET
MARKET_CLOSE = dt_time(16, 0)  # 4:00 PM ET
TRADING_TIMEZONE = pytz.timezone("US/Eastern")


# =============================================================================
# Class Definitions
# =============================================================================
class SpyderApplication:
    """
    Main application class for Spyder that coordinates all trading components.

    This class manages the lifecycle of the trading system including:
    - Initializing core components (trading engine, IB client, GUI)
    - Managing trading schedules and market hours
    - Coordinating between strategies and risk management
    - Handling system events and notifications
    - Ensuring clean startup and shutdown procedures

    Attributes:
        config (ConfigManager): Configuration manager instance
        trading_engine (TradingEngine): Core trading engine
        ib_client (IBClient): Interactive Brokers API client
        scheduler (TradingScheduler): Trading schedule manager
        event_manager (EventManager): System event coordinator
        system_monitor (SystemMonitor): System health monitor
        gui_app (QApplication): PyQt application instance
        main_window (MainWindow): Main GUI window
        logger (SpyderLogger): Application logger
        is_running (bool): Application running state
    """

    def __init__(self):
        """Initialize the Spyder trading application."""
        # Temporary fix: Use standard logging
        import logging

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        self.logger = logging.getLogger(__name__)

        self.error_handler = SpyderErrorHandler()  # <-- CHANGED FROM ErrorHandler
        self.is_running = False

        # Initialize configuration first
        self._setup_environment()
        self.config = ConfigManager(DEFAULT_CONFIG_PATH)  # Direct instantiation

        # Initialize core components
        self.event_manager = EventManager()
        # self.system_monitor = SystemMonitor(self.event_manager)  # Temporarily disabled
        self.scheduler = TradingScheduler(
            self.config.get_config().trading_hours, self.event_manager
        )

        # Trading components will be initialized in setup
        self.trading_engine: Optional[TradingEngine] = None
        self.ib_client = None
        self.gui_app: Optional[QApplication] = None
        self.main_window = (
            None  # Remove the type hint that references non-existent class
        )

        # Register signal handlers for emergency shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        self.logger.info(f"{APPLICATION_NAME} v{VERSION} initialized")

    def _setup_environment(self) -> None:
        """Set up application environment including directories and logging."""
        try:
            # Create necessary directories
            directories = [
                Path.home() / ".spyder",
                Path.home() / ".spyder" / "logs",
                Path.home() / ".spyder" / "data",
                Path.home() / ".spyder" / "backups",
                Path.home() / ".spyder" / "reports",
            ]

            for directory in directories:
                directory.mkdir(parents=True, exist_ok=True)

            # Rotate log files
            self._rotate_logs()

        except Exception as e:
            logging.critical(f"Failed to setup environment: {str(e)}")
            raise TradingError(f"Environment setup failed: {str(e)}")

    def _rotate_logs(self) -> None:
        """Rotate log files to prevent excessive disk usage."""
        log_file = LOG_PATH / "spyder.log"
        if log_file.exists():
            # Create backup with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = log_file.with_name(f"spyder_{timestamp}.log")
            log_file.rename(backup_file)

            # Keep only the last 10 log files
            old_logs = sorted(
                LOG_PATH.glob("spyder_*.log"),
                key=lambda x: x.stat().st_mtime,
                reverse=True,
            )
            for old_log in old_logs[10:]:
                old_log.unlink()

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.critical(f"Received signal {signum}, initiating emergency shutdown")
        self.emergency_shutdown()
        sys.exit(0)

    def _setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum: int, frame: Any) -> None:
        """
        Handle system signals for graceful shutdown.

        Args:
            signum: Signal number
            frame: Current stack frame
        """
        self.logger.info(f"Received signal {signum}, initiating shutdown...")
        self.shutdown()

    def setup(self) -> bool:
        """Set up all trading components and connections."""
        try:
            self.logger.info("Setting up trading components...")

            # Get configuration data properly
            if hasattr(self.config, "get_config"):
                config_data = self.config.get_config()
            elif hasattr(self.config, "to_dict"):
                config_data = self.config.to_dict()
            elif hasattr(self.config, "config"):
                config_data = self.config.config
            else:
                # Fallback - use the config object directly if it's dict-like
                config_data = self.config

            # Initialize IB client with config
            from SpyderB_Broker.SpyderB01_IBClient import get_ib_client

            # FORCE DEBUG: Add environment variable debugging
            import os

            self.logger.info(
                f"🔍 Environment IB_AUTH_METHOD: {os.getenv('IB_AUTH_METHOD')}"
            )
            self.logger.info(
                f"🔍 Environment IB_USE_GATEWAY: {os.getenv('IB_USE_GATEWAY')}"
            )
            self.logger.info(f"🔍 Config data type: {type(config_data)}")

            # TEMPORARY FIX: Force Gateway client
            try:
                from SpyderB_Broker.SpyderB01_IBClient import IBGatewayClient

                self.ib_client = IBGatewayClient(config_data)
                self.logger.info(
                    f"✅ FORCED IBGatewayClient: {type(self.ib_client).__name__}"
                )
            except ImportError as e:
                self.logger.error(f"❌ IBGatewayClient import failed: {e}")
                self.logger.info("💡 Run: pip install ib_insync")
                # Fallback to factory
                self.ib_client = get_ib_client(config_data)
                self.logger.info(f"🔄 Fallback client: {type(self.ib_client).__name__}")
            except Exception as e:
                self.logger.error(f"❌ IBGatewayClient creation failed: {e}")
                # Fallback to factory
                self.ib_client = get_ib_client(config_data)
                self.logger.info(f"🔄 Fallback client: {type(self.ib_client).__name__}")

            # ADD EXPLICIT DEBUG LOG HERE
            self.logger.info(f"🔍 About to call _connect_to_ib()")

            if not self._connect_to_ib():
                self.logger.error("🔍 _connect_to_ib() returned False")
                return False
            else:
                self.logger.info("🔍 _connect_to_ib() returned True")

            # Initialize trading engine
            from SpyderA_Core.SpyderA02_TradingEngine import TradingEngine

            self.trading_engine = TradingEngine(
                config_data, self.ib_client, self.event_manager
            )

            # Initialize GUI - REQUIRED, no fallback
            try:
                from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel

                # Try to import the actual dashboard
                try:
                    from SpyderG_GUI.SpyderG06_TradingDashboard import TradingDashboard

                    dashboard_class = TradingDashboard
                except ImportError:
                    # Create a minimal fallback dashboard
                    class MinimalDashboard(QMainWindow):
                        def __init__(self, event_manager=None):
                            super().__init__()
                            self.setWindowTitle("Spyder Trading System")
                            self.setGeometry(100, 100, 800, 600)

                            # Add a simple label
                            label = QLabel(
                                "Spyder Trading System\nStarting up...", self
                            )
                            label.setGeometry(10, 10, 200, 50)

                        def show_critical_error(self, error_msg):
                            print(f"CRITICAL ERROR: {error_msg}")

                    dashboard_class = MinimalDashboard
                    self.logger.warning("Using minimal dashboard fallback")

                self.gui_app = QApplication(sys.argv)

                # Create the dashboard
                self.main_window = dashboard_class(event_manager=self.event_manager)

                self.logger.info("✅ GUI Dashboard initialized successfully")

            except Exception as e:
                self.logger.critical(f"❌ GUI initialization failed: {e}")
                self.logger.critical(
                    "❌ Spyder requires GUI Dashboard - cannot run in console mode"
                )
                return False  # FAIL SETUP if GUI doesn't work

            # Register event handlers
            self._register_event_handlers()

            self.logger.info("Trading components setup completed successfully")
            return True

        except Exception as e:
            self.logger.error(f"Setup failed: {str(e)}")
            if hasattr(self, "error_handler"):
                self.error_handler.handle_error(e, critical=True)
            return False

    def _connect_to_ib(self) -> bool:
        """Connect to Interactive Brokers Gateway."""
        try:
            self.logger.info("🔍 _connect_to_ib() method called")
            self.logger.info(f"🔍 IB client type: {type(self.ib_client).__name__}")
            self.logger.info(
                f"🔍 IB client has connect method: {hasattr(self.ib_client, 'connect')}"
            )

            self.logger.info("Connecting to IB Gateway...")

            # IB Gateway uses direct socket connection, not HTTP
            if self.ib_client.connect():
                self.logger.info("✅ Successfully connected to IB Gateway")

                # Gateway handles authentication automatically
                if self.ib_client.authenticate():
                    self.logger.info("✅ Authentication successful")
                    return True
                else:
                    self.logger.warning("⚠️ Authentication pending - check 2FA")
                    return True  # Connection is still valid
            else:
                self.logger.error("❌ Failed to connect to IB Gateway")
                self._print_gateway_instructions()
                return False

        except Exception as e:
            self.logger.error(f"🔍 _connect_to_ib() exception: {str(e)}")
            import traceback

            self.logger.error(f"🔍 Traceback: {traceback.format_exc()}")
            return False

    def _print_gateway_instructions(self):
        """Print IB Gateway setup instructions."""
        self.logger.info("=" * 60)
        self.logger.info("IB GATEWAY SETUP INSTRUCTIONS")
        self.logger.info("=" * 60)
        self.logger.info("1. Install IB Gateway:")
        self.logger.info(
            "   wget https://download2.interactivebrokers.com/installers/ibgateway/latest-standalone/ibgateway-latest-standalone-linux-x64.sh"
        )
        self.logger.info("   chmod +x ibgateway-latest-standalone-linux-x64.sh")
        self.logger.info("   ./ibgateway-latest-standalone-linux-x64.sh")
        self.logger.info("")
        self.logger.info("2. Start IB Gateway:")
        self.logger.info("   ~/Jts/ibgateway/*/ibgateway")
        self.logger.info("")
        self.logger.info("3. Configure API:")
        self.logger.info("   - Enable API connections")
        self.logger.info("   - Set socket port to 4001 (paper) or 4000 (live)")
        self.logger.info("   - Allow connections from localhost")
        self.logger.info("")
        self.logger.info("4. Approve 2FA on your mobile device")
        self.logger.info("=" * 60)

    def _register_event_handlers(self) -> None:
        """Register handlers for system events."""
        try:
            # Check if event manager is available
            if not hasattr(self, "event_manager") or not self.event_manager:
                self.logger.warning(
                    "Event manager not available, skipping event registration"
                )
                return

            # Register events using string constants with error handling
            event_registrations = [
                ("CRITICAL_ERROR", self._handle_critical_error),
                ("RISK_LIMIT_EXCEEDED", self._handle_risk_limit),
                ("CONNECTION_LOST", self._handle_connection_lost),
                ("MARKET_HOURS_CHANGED", self._handle_market_hours),
            ]

            successful_registrations = 0
            for event_type, handler in event_registrations:
                try:
                    # Check if handler method exists
                    handler_name = handler.__name__
                    if hasattr(self, handler_name):
                        # Call subscribe with proper positional arguments
                        success = self.event_manager.subscribe(
                            event_type,  # First argument: event_type
                            handler,  # Second argument: callback
                            f"main_{handler_name}",  # Third argument: subscriber_id (optional)
                        )
                        if success:
                            successful_registrations += 1
                            self.logger.debug(f"Registered handler for {event_type}")
                        else:
                            self.logger.warning(
                                f"Failed to register handler for {event_type}"
                            )
                    else:
                        self.logger.warning(f"Handler method {handler_name} not found")

                except Exception as e:
                    self.logger.error(f"Error registering {event_type}: {str(e)}")

            self.logger.info(
                f"Event handlers registered: {successful_registrations}/{len(event_registrations)}"
            )

        except Exception as e:
            self.logger.error(f"Failed to register event handlers: {str(e)}")
            # Don't fail application startup for event handler issues
            pass

    def _handle_critical_error(self, event):
        """Handle critical error events."""
        try:
            error_data = event if isinstance(event, dict) else {"error": str(event)}
            error_msg = error_data.get("error", "Unknown critical error")
            self.logger.critical(f"Critical error: {error_msg}")

            # Stop trading immediately
            if self.trading_engine:
                self.trading_engine.emergency_stop()

            # Notify user
            if self.main_window:
                self.main_window.show_critical_error(error_msg)
        except Exception as e:
            self.logger.error(f"Error handling critical error event: {str(e)}")

    def _handle_risk_limit(self, event):
        """Handle risk limit events."""
        try:
            event_data = (
                event if isinstance(event, dict) else {"limit_type": str(event)}
            )
            limit_type = event_data.get("limit_type", "Unknown")
            current_value = event_data.get("current_value", 0)
            limit_value = event_data.get("limit_value", 0)

            self.logger.warning(
                f"Risk limit exceeded: {limit_type} - "
                f"Current: {current_value}, Limit: {limit_value}"
            )

            # Pause trading
            if self.trading_engine:
                self.trading_engine.pause_trading()
        except Exception as e:
            self.logger.error(f"Error handling risk limit event: {str(e)}")

    def _handle_connection_lost(self, event):
        """Handle connection lost events."""
        try:
            self.logger.error("IB connection lost, attempting reconnection...")

            # Attempt to reconnect
            if self._connect_to_ib():
                self.logger.info("Successfully reconnected to IB")
                if self.trading_engine:
                    self.trading_engine.resume_trading()
            else:
                self.logger.error("Failed to reconnect to IB")
                self.shutdown()
        except Exception as e:
            self.logger.error(f"Error handling connection lost event: {str(e)}")

    def _handle_market_hours(self, event):
        """Handle market hours change events."""
        try:
            event_data = event if isinstance(event, dict) else {"is_open": False}
            is_open = event_data.get("is_open", False)

            if is_open:
                self.logger.info("Market opened, starting trading activities")
                if self.trading_engine:
                    self.trading_engine.start_trading()
            else:
                self.logger.info("Market closed, stopping trading activities")
                if self.trading_engine:
                    self.trading_engine.stop_trading()
        except Exception as e:
            self.logger.error(f"Error handling market hours event: {str(e)}")

    def run(self) -> None:
        """Main application loop with GUI support."""
        try:
            self.logger.info("Spyder Trading System started")
            self.is_running = True

            # If GUI is available, run GUI event loop
            if self.gui_app and self.main_window:
                self.logger.info("Starting GUI mode")
                self.main_window.show()  # Make sure window is visible

                # Run Qt event loop
                sys.exit(self.gui_app.exec_())
            else:
                # Run console mode
                self.logger.info("Running in console mode")
                while self.is_running:
                    time.sleep(1)

        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
            self.shutdown()
        except Exception as e:
            self.logger.error(f"Application error: {str(e)}")
            self.emergency_shutdown()
        finally:
            if self.is_running:
                self.shutdown()

    def _run_console_mode(self) -> None:
        """Run application in console mode without GUI."""
        self.logger.info("Running in console mode (no GUI)")

        try:
            # Keep running until shutdown signal
            while self.is_running:
                time.sleep(1)  # Changed from asyncio.sleep(1)

        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")

    def shutdown(self) -> None:
        """Perform clean shutdown of all components."""
        if not self.is_running:
            return

        self.logger.info("Initiating application shutdown...")
        self.is_running = False

        try:
            # Stop trading engine first
            if self.trading_engine:
                self.logger.info("Stopping trading engine...")
                self.trading_engine.stop()
                self.trading_engine.cleanup()
                self.logger.info("Trading engine stopped successfully")

            # Stop scheduler with proper error handling
            if self.scheduler:
                try:
                    self.scheduler.stop()
                    self.logger.info("Scheduler stopped")
                except Exception as e:
                    self.logger.warning(f"Scheduler stop warning: {e}")
                    # Don't fail shutdown for scheduler issues

            # Disconnect from IB Gateway
            if self.ib_client:
                try:
                    self.logger.info("Disconnecting from IB Gateway...")
                    self.ib_client.disconnect()
                    self.logger.info("IB Gateway disconnected")
                except Exception as e:
                    self.logger.warning(f"IB disconnect warning: {e}")

            # Close GUI
            if self.gui_app:
                try:
                    self.logger.info("Closing GUI...")
                    self.gui_app.quit()
                except Exception as e:
                    self.logger.warning(f"GUI close warning: {e}")

            # Save configuration (with proper method check)
            if (
                self.config
                and hasattr(self.config, "save")
                and callable(getattr(self.config, "save", None))
            ):
                try:
                    self.config.save()
                    self.logger.info("Configuration saved")
                except Exception as e:
                    self.logger.warning(f"Config save warning: {e}")

            self.logger.info(f"{APPLICATION_NAME} shutdown completed successfully")

        except Exception as e:
            self.logger.error(f"Error during shutdown: {str(e)}")
            # Don't force exit - let it complete gracefully

    def emergency_shutdown(self):
        """Emergency shutdown - force stop all components"""
        self.logger.critical("EMERGENCY SHUTDOWN INITIATED")

        try:
            # Force stop trading engine
            if self.trading_engine:
                self.trading_engine.emergency_stop()

            # Force disconnect IB
            if self.ib_client:
                try:
                    self.ib_client.disconnect()
                except:
                    pass

        except Exception as e:
            self.logger.error(f"Emergency shutdown error: {e}")
        finally:
            import os

            os._exit(0)  # Force exit


# =============================================================================
# Main Entry Point
# =============================================================================
def main():
    """Main entry point for the Spyder trading application."""
    try:
        # Create and setup application
        app = SpyderApplication()

        if not app.setup():
            print("❌ Application setup failed")
            return 1

        # Run the application
        app.run()

        return 0

    except Exception as e:
        print(f"❌ Fatal error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
