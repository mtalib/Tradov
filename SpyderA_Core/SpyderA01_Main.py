#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System
Module: SpyderA01_Main.py
Group: A (Core Trading Engine)
Purpose: Primary application controller and entry point

Description:
This module serves as the main entry point for the Spyder automated trading system.
It initializes all core components, manages the application lifecycle, and coordinates
the interaction between various subsystems. The module handles graceful startup,
shutdown procedures, and provides the primary command-line interface.

Author: Mohamed Talib
Created: 2025-01-27
Version: 1.4
"""

# =============================================================================
# Add project root to Python path
# =============================================================================
import sys
from pathlib import Path
import logging

# Get the project root directory (parent of SpyderA_Core)
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# =============================================================================
# Standard Library Imports
# =============================================================================
import os
import signal
import asyncio
import time
from pathlib import Path
from datetime import datetime, time as dt_time
from typing import Optional, Dict, Any
import argparse
import json

# =============================================================================
# Third-Party Imports
# =============================================================================
try:
    import pytz
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QTimer
except ImportError as e:
    print(f"Warning: Missing required dependency: {e}")
    print("Please install requirements: pip install -r requirements.txt")
    sys.exit(1)

# =============================================================================
# Local Application Imports
# =============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger, get_logger
    from SpyderA_Core.SpyderA02_TradingEngine import TradingEngine
    from SpyderA_Core.SpyderA03_Configuration import ConfigManager
    # FIXED: DatabaseManager has been replaced by DataAccessLayer
    from SpyderH_Storage.SpyderH01_DataAccessLayer import DataAccessLayer, get_data_access_layer
    from SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType
    from SpyderB_Broker.SpyderB01_SpyderClient import SpyderClient
    from SpyderE_Risk.SpyderE01_RiskManager import RiskManager
    from SpyderG_GUI.SpyderG01_MainWindow import SpyderMainWindow as MainWindow
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
except ImportError as e:
    print(f"Error importing Spyder modules: {e}")
    print("Make sure all required modules are in the correct location.")
    sys.exit(1)

# =============================================================================
# Constants
# =============================================================================
APPLICATION_NAME = "Spyder Trading System"
VERSION = "1.4.0"
DEFAULT_CONFIG_PATH = Path.home() / ".spyder" / "config.yaml"
LOG_PATH = Path.home() / ".spyder" / "logs"

# Trading hours in Eastern Time
MARKET_OPEN = dt_time(9, 30)   # 9:30 AM ET
MARKET_CLOSE = dt_time(16, 0)   # 4:00 PM ET
TRADING_TIMEZONE = pytz.timezone('US/Eastern')

# =============================================================================
# Signal Handlers
# =============================================================================
def signal_handler(signum, frame):
    """Handle system signals for graceful shutdown."""
    print(f"\nReceived signal {signum}. Initiating graceful shutdown...")
    if hasattr(signal_handler, 'app'):
        signal_handler.app.shutdown()
    sys.exit(0)

# =============================================================================
# Main Application Class
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
        spyder_client (SpyderClient): Interactive Brokers API client
        dal (DataAccessLayer): Data access layer (replaced DatabaseManager)
        event_manager (EventManager): System event coordinator
        risk_manager (RiskManager): Risk management system
        gui_app (QApplication): PyQt application instance
        main_window (MainWindow): Main GUI window
        logger (SpyderLogger): Application logger
        is_running (bool): Application running state
    """

    def __init__(self, config_path: Optional[Path] = None, headless: bool = False):
        """
        Initialize the Spyder trading application.

        Args:
            config_path: Path to configuration file
            headless: Run without GUI
        """
        self.logger = get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.headless = headless
        self.is_running = False

        # Store reference for signal handler
        signal_handler.app = self

        # Initialize configuration
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self.config = ConfigManager(str(self.config_path))

        # Initialize core components
        self.event_manager = EventManager()
        self.dal = get_data_access_layer()  # FIXED: Using get_data_access_layer instead of get_dal
        self.trading_engine = None
        self.spyder_client = None
        self.risk_manager = None
        self.gui_app = None
        self.main_window = None

        # Setup logging
        self._setup_logging()

        self.logger.info(f"Initializing {APPLICATION_NAME} v{VERSION}")



    def _setup_logging(self):
        """Configure application logging."""
        log_config = self.config.get('logging', {})
        log_level = log_config.get('level', 'INFO')
        log_file = log_config.get('file', str(LOG_PATH / 'spyder.log'))

        # Ensure log directory exists
        LOG_PATH.mkdir(parents=True, exist_ok=True)

        # Configure logger
        self.logger.setLevel(log_level)
        # Fixed: Using standard logging API
        if log_file:
            file_handler = logging.FileHandler(log_file)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    async def initialize_components(self):
        """Initialize all trading system components."""
        try:
            self.logger.info("Initializing trading system components...")

            # Initialize database
            self.logger.info("Initializing data access layer...")
            # The DataAccessLayer verifies its own database on initialization
            # No need to call verify_database separately

            # Initialize IB client
            self.logger.info("Initializing Interactive Brokers client...")
            # SpyderClient expects the entire config object
            self.spyder_client = SpyderClient(self.config)



            # Initialize risk manager
            self.logger.info("Initializing risk manager...")
            self.risk_manager = RiskManager(self.config.get('risk', {}))

            # Initialize trading engine
            self.logger.info("Initializing trading engine...")
            self.trading_engine = TradingEngine(
                config=self.config,
                spyder_client=self.spyder_client,
                event_manager=self.event_manager
            )

            # Register event handlers
            self._register_event_handlers()

            # Initialize GUI if not headless
            if not self.headless:
                self.logger.info("Initializing GUI...")
                self._initialize_gui()

            self.logger.info("All components initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize components: {str(e)}")
            raise

    def _initialize_gui(self):
        """Initialize the GUI components."""
        if self.headless:
            return

        # Create PyQt application
        self.gui_app = QApplication(sys.argv)
        self.gui_app.setApplicationName(APPLICATION_NAME)

        # Create main window
        self.main_window = MainWindow(
            trading_engine=self.trading_engine,
            spyder_client=self.spyder_client,
            event_manager=self.event_manager,
            config=self.config
        )

        # Setup window
        self.main_window.setWindowTitle(f"{APPLICATION_NAME} v{VERSION}")
        self.main_window.show()



    def _register_event_handlers(self):
        """Register event handlers for system events."""
        # System events
        self.event_manager.register_handler(EventType.SYSTEM_ERROR, self._handle_system_error)
        self.event_manager.register_handler(EventType.SYSTEM_WARNING, self._handle_system_warning)

        # Trading events
        self.event_manager.register_handler(EventType.TRADE_EXECUTED, self._handle_trade_executed)
        self.event_manager.register_handler(EventType.POSITION_UPDATED, self._handle_position_updated)

        # Market events
        self.event_manager.register_handler(EventType.MARKET_DATA_RECEIVED, self._handle_market_data)

        # Risk events
        self.event_manager.register_handler(EventType.RISK_LIMIT_EXCEEDED, self._handle_risk_limit)



    def _handle_system_error(self, event: Event):
        """Handle system error events."""
        self.logger.error(f"System error: {event.data}")
        if not self.headless and self.main_window:
            self.main_window.show_error(str(event.data))



    def _handle_system_warning(self, event: Event):
        """Handle system warning events."""
        self.logger.warning(f"System warning: {event.data}")
        if not self.headless and self.main_window:
            self.main_window.show_warning(str(event.data))



    def _handle_trade_executed(self, event: Event):
        """Handle trade execution events."""
        trade_data = event.data
        self.logger.info(f"Trade executed: {trade_data}")

        # Store trade in database
        self.dal.trades.save_trade(trade_data)

        # Update GUI if available
        if not self.headless and self.main_window:
            self.main_window.update_trades(trade_data)



    def _handle_position_updated(self, event: Event):
        """Handle position update events."""
        position_data = event.data
        self.logger.info(f"Position updated: {position_data}")

        # Update database
        self.dal.positions.update_position(position_data)

        # Update GUI if available
        if not self.headless and self.main_window:
            self.main_window.update_positions(position_data)



    def _handle_market_data(self, event: Event):
        """Handle market data events."""
        # Cache market data
        self.dal.market_data.cache_quote(event.data)



    def _handle_risk_limit(self, event: Event):
        """Handle risk limit exceeded events."""
        self.logger.error(f"Risk limit exceeded: {event.data}")

        # Halt trading
        self.trading_engine.halt_trading()

        # Alert user
        if not self.headless and self.main_window:
            self.main_window.show_critical_alert("Risk limit exceeded! Trading halted.")

    async def connect_broker(self):
        """Connect to Interactive Brokers."""
        self.logger.info("Connecting to Interactive Brokers...")

        max_retries = 3
        retry_delay = 5

        for attempt in range(max_retries):
            try:
                await self.spyder_client.connect_async()
                self.logger.info("Successfully connected to Interactive Brokers")

                # Request initial data
                await self.spyder_client.request_account_updates()
                await self.spyder_client.request_positions()

                return True

            except Exception as e:
                self.logger.error(f"Connection attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    self.logger.info(f"Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                else:
                    self.logger.error("Failed to connect to Interactive Brokers")
                    return False

    def start_trading(self):
        """Start the trading system."""
        if self.is_running:
            self.logger.warning("Trading system is already running")
            return

        self.logger.info("Starting trading system...")

        # Check market hours
        if not self._is_market_open() and not self.config.get('trading.allow_after_hours', False):
            self.logger.warning("Market is closed. Trading will start when market opens.")

        # Start trading engine
        self.trading_engine.start()
        self.is_running = True

        self.logger.info("Trading system started successfully")



    def stop_trading(self):
        """Stop the trading system."""
        if not self.is_running:
            self.logger.warning("Trading system is not running")
            return

        self.logger.info("Stopping trading system...")

        # Stop trading engine
        self.trading_engine.stop()

        # Close all positions if configured
        if self.config.get('trading.close_positions_on_stop', False):
            self.logger.info("Closing all open positions...")
            self.trading_engine.close_all_positions()

        self.is_running = False
        self.logger.info("Trading system stopped")



    def _is_market_open(self) -> bool:
        """Check if market is currently open."""
        now = datetime.now(TRADING_TIMEZONE)
        current_time = now.time()

        # Check if it's a weekday
        if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False

        # Check market hours
        return MARKET_OPEN <= current_time <= MARKET_CLOSE

    async def run(self):
        """Main application run loop."""
        try:
            # Initialize components
            await self.initialize_components()

            # Connect to broker
            if not await self.connect_broker():
                raise RuntimeError("Failed to connect to broker")

            # Start trading
            self.start_trading()

            # Run GUI event loop if not headless
            if not self.headless:
                self.gui_app.exec_()
            else:
                # Keep running until interrupted
                while self.is_running:
                    await asyncio.sleep(1)

        except KeyboardInterrupt:
            self.logger.info("Received keyboard interrupt")
        except Exception as e:
            self.logger.error("Application error: %s", str(e))
            raise
        finally:
            pass  # Add proper indentation here - this block should be indented under 'finally'

    def save_state_legacy(self):
        """[DEPRECATED] Save application state (legacy placeholder)."""
        try:
            self.logger.info("Saving application state (legacy)...")
            # TODO: Implement actual state saving
            return True
        except (OSError, ValueError) as e:
            self.logger.error("Failed to save state: %s", e)
            return False

    async def shutdown(self):
        """Perform graceful shutdown."""
        self.logger.info("Initiating graceful shutdown...")

        try:
            # Stop trading
            if self.is_running:
                self.stop_trading()

            # Disconnect from broker
            if self.spyder_client and self.spyder_client.is_connected:
                self.logger.info("Disconnecting from Interactive Brokers...")
                self.spyder_client.disconnect()

            # Save state
            self.logger.info("Saving application state...")
            self.save_state()

            # Close database connections
            if self.dal:
                self.dal.close_all_connections()

            # Quit GUI
            if self.gui_app:
                self.gui_app.quit()

            self.logger.info("Shutdown complete")

        except Exception as e:
            self.logger.error(f"Error during shutdown: {str(e)}")



    def save_state(self):
        """Save application state to disk."""
        state = {
            'version': VERSION,
            'timestamp': datetime.now().isoformat(),
            'config_path': str(self.config_path),
            'is_running': self.is_running,
            'positions': self.trading_engine.get_positions() if self.trading_engine else [],
            'settings': self.config.get_all()
        }

        state_file = Path.home() / '.spyder' / 'state.json'
        state_file.parent.mkdir(parents=True, exist_ok=True)

        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2)

# =============================================================================
# Entry Point
# =============================================================================
def main():
    """Main entry point for the Spyder trading application."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description=f"{APPLICATION_NAME} v{VERSION}")
    parser.add_argument('--config', type=Path, help='Path to configuration file')
    parser.add_argument('--headless', action='store_true', help='Run without GUI')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create and run application
    app = SpyderApplication(config_path=args.config, headless=args.headless)

    # Enable debug logging if requested
    if args.debug:
        app.logger.set_level('DEBUG')

    # Run the application
    try:
        asyncio.run(app.run())
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
