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
Version: 2.0.0 - Production Ready
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
from datetime import datetime, time as dt_time, timedelta
from typing import Optional, Dict, Any, List, Tuple
import argparse
import json
import threading
from enum import Enum, auto
import traceback

# =============================================================================
# Third-Party Imports
# =============================================================================
try:
    import pytz
    import pandas as pd
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QTimer
except ImportError as e:
    print(f"Warning: Missing required dependency: {e}")
    print("Please install requirements: pip install -r requirements.txt")
    sys.exit(1)

# =============================================================================
# Local Application Imports with Graceful Fallbacks
# =============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger, get_logger
    from SpyderA_Core.SpyderA02_TradingEngine import TradingEngine
    from SpyderA_Core.SpyderA03_Configuration import ConfigManager
    from SpyderH_Storage.SpyderH01_DataAccessLayer import DataAccessLayer, get_data_access_layer
    from SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType
    from SpyderB_Broker.SpyderB01_SpyderClient import SpyderClient
    from SpyderE_Risk.SpyderE01_RiskManager import RiskManager
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
    from SpyderU_Utilities.SpyderU10_TradingCalendar import TradingCalendar
except ImportError as e:
    print(f"Error importing Spyder modules: {e}")
    print("Make sure all required modules are in the correct location.")
    sys.exit(1)

# Try to import GUI with graceful fallback
try:
    from SpyderG_GUI.SpyderG01_MainWindow import SpyderMainWindow as MainWindow
    HAS_GUI = True
except (ImportError, NameError, SyntaxError) as e:
    print(f"Warning: GUI not available: {e}")
    MainWindow = None
    HAS_GUI = False

# =============================================================================
# Constants
# =============================================================================
APPLICATION_NAME = "Spyder Trading System"
VERSION = "2.0.0"
DEFAULT_CONFIG_PATH = Path.home() / ".spyder" / "config.yaml"
LOG_PATH = Path.home() / ".spyder" / "logs"
STATE_PATH = Path.home() / ".spyder" / "state"

# Trading hours in Eastern Time
MARKET_OPEN = dt_time(9, 30)   # 9:30 AM ET
MARKET_CLOSE = dt_time(16, 0)   # 4:00 PM ET
TRADING_TIMEZONE = pytz.timezone('US/Eastern')

# Application states
class AppState(Enum):
    """Application state enumeration"""
    INITIALIZING = auto()
    READY = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    TRADING = auto()
    PAUSED = auto()
    STOPPING = auto()
    STOPPED = auto()
    ERROR = auto()

# =============================================================================
# Signal Handlers
# =============================================================================
def signal_handler(signum, frame):
    """Handle system signals for graceful shutdown."""
    signal_name = signal.Signals(signum).name
    print(f"\nReceived signal {signal_name}. Initiating graceful shutdown...")
    if hasattr(signal_handler, 'app'):
        asyncio.create_task(signal_handler.app.shutdown())
    else:
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
        dal (DataAccessLayer): Data access layer
        event_manager (EventManager): System event coordinator
        risk_manager (RiskManager): Risk management system
        trading_calendar (TradingCalendar): Market calendar
        gui_app (QApplication): PyQt application instance
        main_window (MainWindow): Main GUI window
        logger (SpyderLogger): Application logger
        error_handler (SpyderErrorHandler): Error handling system
        state (AppState): Current application state
        is_running (bool): Application running state
    """

    def __init__(self, config_path: Optional[Path] = None, headless: bool = False):
        """
        Initialize the Spyder trading application.

        Args:
            config_path: Path to configuration file
            headless: Run without GUI if True
        """
        # Initialize state
        self.state = AppState.INITIALIZING
        self.is_running = False
        self.headless = headless
        self.start_time = None
        self._shutdown_event = threading.Event()
        self._state_lock = threading.RLock()
        
        # Initialize paths
        self._init_paths()
        
        # Initialize logger first
        self.logger = get_logger(__name__)
        self.logger.info(f"Initializing {APPLICATION_NAME} v{VERSION}")
        
        # Initialize error handler
        self.error_handler = SpyderErrorHandler()
        
        # Initialize configuration
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self.config = ConfigManager(self.config_path)
        
        # Component references (initialized later)
        self.event_manager = None
        self.dal = None
        self.trading_engine = None
        self.spyder_client = None
        self.risk_manager = None
        self.trading_calendar = None
        self.gui_app = None
        self.main_window = None
        
        # Component status tracking
        self.component_status = {
            'config': False,
            'event_manager': False,
            'database': False,
            'trading_engine': False,
            'broker_client': False,
            'risk_manager': False,
            'trading_calendar': False,
            'gui': False
        }
        
        # Register signal handlers
        signal_handler.app = self
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        self.logger.info("Application initialized in headless mode" if headless else "Application initialized with GUI")

    def _init_paths(self):
        """Initialize application paths"""
        paths = [LOG_PATH, STATE_PATH]
        for path in paths:
            path.mkdir(parents=True, exist_ok=True)

    def _transition_state(self, new_state: AppState) -> bool:
        """
        Safely transition application state
        
        Args:
            new_state: Target state
            
        Returns:
            bool: True if transition successful
        """
        allowed_transitions = {
            AppState.INITIALIZING: [AppState.READY, AppState.ERROR],
            AppState.READY: [AppState.CONNECTING, AppState.STOPPING, AppState.ERROR],
            AppState.CONNECTING: [AppState.CONNECTED, AppState.READY, AppState.ERROR],
            AppState.CONNECTED: [AppState.TRADING, AppState.READY, AppState.STOPPING, AppState.ERROR],
            AppState.TRADING: [AppState.PAUSED, AppState.CONNECTED, AppState.STOPPING, AppState.ERROR],
            AppState.PAUSED: [AppState.TRADING, AppState.STOPPING, AppState.ERROR],
            AppState.STOPPING: [AppState.STOPPED],
            AppState.ERROR: [AppState.STOPPING, AppState.STOPPED],
            AppState.STOPPED: []
        }
        
        with self._state_lock:
            if new_state in allowed_transitions.get(self.state, []):
                old_state = self.state
                self.state = new_state
                self.logger.info(f"State transition: {old_state.name} -> {new_state.name}")
                
                # Emit state change event
                if self.event_manager:
                    self.event_manager.emit(
                        EventType.SYSTEM,
                        {
                            'type': 'state_change',
                            'old_state': old_state.name,
                            'new_state': new_state.name
                        }
                    )
                return True
            else:
                self.logger.warning(f"Invalid state transition: {self.state.name} -> {new_state.name}")
                return False

    async def initialize_components(self):
        """Initialize all application components with proper error handling."""
        self.logger.info("Initializing components...")
        
        try:
            # Initialize components in order
            components = [
                ('config', self._init_config),
                ('event_manager', self._init_event_manager),
                ('database', self._init_database),
                ('trading_calendar', self._init_trading_calendar),
                ('risk_manager', self._init_risk_manager),
                ('trading_engine', self._init_trading_engine),
                ('broker_client', self._init_broker_client),
            ]
            
            if not self.headless:
                components.append(('gui', self._init_gui))
            
            for name, init_func in components:
                try:
                    self.logger.info(f"Initializing {name}...")
                    if await init_func():
                        self.component_status[name] = True
                        self.logger.info(f"✓ {name} initialized successfully")
                    else:
                        self.logger.error(f"✗ {name} initialization failed")
                        # Decide if this is fatal based on component
                        if name in ['config', 'event_manager', 'database']:
                            raise RuntimeError(f"Critical component {name} failed to initialize")
                except Exception as e:
                    self.logger.error(f"Error initializing {name}: {e}")
                    self.error_handler.handle_error(e, f"initialize_{name}")
                    if name in ['config', 'event_manager', 'database']:
                        raise
            
            # Verify minimum required components
            required = ['config', 'event_manager', 'database']
            if not all(self.component_status[comp] for comp in required):
                raise RuntimeError("Failed to initialize required components")
            
            self._transition_state(AppState.READY)
            self.logger.info("All components initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Component initialization failed: {e}")
            self._transition_state(AppState.ERROR)
            raise

    async def _init_config(self) -> bool:
        """Initialize configuration manager"""
        try:
            # Reload configuration
            if not self.config.load():
                self.logger.warning("Using default configuration")
            
            # Validate configuration
            validation_errors = self.config.validate()
            if validation_errors:
                self.logger.error(f"Configuration validation errors: {validation_errors}")
                return False
            
            return True
        except Exception as e:
            self.logger.error(f"Config initialization error: {e}")
            return False

    async def _init_event_manager(self) -> bool:
        """Initialize event management system"""
        try:
            self.event_manager = EventManager()
            self.event_manager.start()
            
            # Register application event handlers
            self.event_manager.subscribe(EventType.SYSTEM_ERROR, self._on_system_error)
            self.event_manager.subscribe(EventType.CRITICAL_ERROR, self._on_critical_error)
            
            return True
        except Exception as e:
            self.logger.error(f"Event manager initialization error: {e}")
            return False

    async def _init_database(self) -> bool:
        """Initialize database access layer"""
        try:
            self.dal = get_data_access_layer(self.config.get('database', {}))
            
            # Verify database connection
            if not self.dal.test_connection():
                self.logger.error("Database connection test failed")
                return False
            
            # Run any pending migrations
            if not self.dal.run_migrations():
                self.logger.warning("Database migrations failed - continuing anyway")
            
            return True
        except Exception as e:
            self.logger.error(f"Database initialization error: {e}")
            return False

    async def _init_trading_calendar(self) -> bool:
        """Initialize trading calendar"""
        try:
            self.trading_calendar = TradingCalendar()
            
            # Load market holidays
            if not self.trading_calendar.load_holidays():
                self.logger.warning("Failed to load market holidays - using defaults")
            
            return True
        except Exception as e:
            self.logger.error(f"Trading calendar initialization error: {e}")
            return False

    async def _init_risk_manager(self) -> bool:
        """Initialize risk management system"""
        try:
            risk_config = self.config.get('risk', {})
            self.risk_manager = RiskManager(risk_config, self.event_manager)
            
            if not self.risk_manager.initialize():
                return False
            
            # Register risk event handlers
            self.event_manager.subscribe(EventType.RISK_LIMIT_EXCEEDED, self._on_risk_limit_exceeded)
            
            return True
        except Exception as e:
            self.logger.error(f"Risk manager initialization error: {e}")
            return False

    async def _init_trading_engine(self) -> bool:
        """Initialize trading engine"""
        try:
            engine_config = self.config.get('trading_engine', {})
            self.trading_engine = TradingEngine(
                engine_config,
                self.spyder_client,
                self.event_manager
            )
            
            if not self.trading_engine.initialize():
                return False
            
            # Set risk manager
            self.trading_engine.set_risk_manager(self.risk_manager)
            
            return True
        except Exception as e:
            self.logger.error(f"Trading engine initialization error: {e}")
            return False

    async def _init_broker_client(self) -> bool:
        """Initialize broker client (can run in degraded mode)"""
        try:
            ib_config = self.config.get('ib', {})
            self.spyder_client = SpyderClient(ib_config)
            
            # Don't fail if broker not available - can run in simulation mode
            return True
        except Exception as e:
            self.logger.warning(f"Broker client initialization error: {e}")
            self.logger.info("Running in simulation mode")
            return True

    async def _init_gui(self) -> bool:
        """Initialize GUI components"""
        if not HAS_GUI:
            return False
            
        try:
            self.gui_app = QApplication.instance() or QApplication(sys.argv)
            self.main_window = MainWindow(self)
            self.main_window.show()
            return True
        except Exception as e:
            self.logger.error(f"GUI initialization error: {e}")
            return False

    async def connect_broker(self) -> bool:
        """Connect to Interactive Brokers with retry logic."""
        if not self.spyder_client:
            self.logger.error("Broker client not initialized")
            return False
            
        self._transition_state(AppState.CONNECTING)
        
        max_retries = 3
        retry_delay = 5
        
        for attempt in range(max_retries):
            try:
                self.logger.info(f"Connecting to Interactive Brokers (attempt {attempt + 1}/{max_retries})")
                
                # Connect with timeout
                connected = await asyncio.wait_for(
                    self.spyder_client.connect_async(),
                    timeout=30
                )
                
                if connected:
                    self.logger.info("Successfully connected to Interactive Brokers")
                    self._transition_state(AppState.CONNECTED)
                    
                    # Subscribe to connection events
                    self.event_manager.subscribe(
                        EventType.CONNECTION_LOST,
                        self._on_connection_lost
                    )
                    
                    return True
                    
            except asyncio.TimeoutError:
                self.logger.error("Connection timeout")
            except Exception as e:
                self.logger.error(f"Connection error: {e}")
            
            if attempt < max_retries - 1:
                self.logger.info(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
        
        self.logger.error("Failed to connect after all retries")
        self._transition_state(AppState.READY)
        return False

    def start_trading(self):
        """Start trading operations with safety checks."""
        try:
            if self.state != AppState.CONNECTED:
                self.logger.error(f"Cannot start trading from state {self.state.name}")
                return False
            
            # Verify market hours
            if not self.is_market_open():
                self.logger.warning("Market is closed")
                if not self.config.get('allow_after_hours', False):
                    return False
            
            # Verify risk manager ready
            if not self.risk_manager or not self.risk_manager.is_ready():
                self.logger.error("Risk manager not ready")
                return False
            
            # Start trading engine
            if not self.trading_engine.start():
                self.logger.error("Failed to start trading engine")
                return False
            
            self.is_running = True
            self._transition_state(AppState.TRADING)
            self.start_time = datetime.now()
            
            self.logger.info("Trading started successfully")
            
            # Emit trading started event
            self.event_manager.emit(
                EventType.SYSTEM,
                {
                    'type': 'trading_started',
                    'timestamp': self.start_time,
                    'market_open': self.is_market_open()
                }
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting trading: {e}")
            self.error_handler.handle_error(e, "start_trading")
            return False

    def stop_trading(self):
        """Stop trading operations gracefully."""
        try:
            if self.state not in [AppState.TRADING, AppState.PAUSED]:
                self.logger.warning(f"Not trading (state: {self.state.name})")
                return
            
            self.logger.info("Stopping trading operations...")
            
            # Stop trading engine
            if self.trading_engine:
                self.trading_engine.stop("User requested")
            
            self.is_running = False
            self._transition_state(AppState.CONNECTED)
            
            # Calculate session duration
            if self.start_time:
                duration = datetime.now() - self.start_time
                self.logger.info(f"Trading session duration: {duration}")
            
            # Emit trading stopped event
            self.event_manager.emit(
                EventType.SYSTEM,
                {
                    'type': 'trading_stopped',
                    'timestamp': datetime.now(),
                    'duration': str(duration) if self.start_time else None
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error stopping trading: {e}")
            self.error_handler.handle_error(e, "stop_trading")

    def is_market_open(self) -> bool:
        """
        Check if market is currently open using trading calendar.
        
        Returns:
            bool: True if market is open
        """
        if self.trading_calendar:
            return self.trading_calendar.is_market_open()
        
        # Fallback to simple time check
        now = datetime.now(TRADING_TIMEZONE)
        current_time = now.time()
        
        # Check if it's a weekday
        if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
        
        # Check market hours
        return MARKET_OPEN <= current_time <= MARKET_CLOSE

    async def run(self):
        """Main application run loop with proper error handling."""
        try:
            # Initialize components
            await self.initialize_components()
            
            # Connect to broker if configured
            if self.config.get('auto_connect', True):
                if not await self.connect_broker():
                    self.logger.warning("Running without broker connection")
            
            # Auto-start trading if configured
            if self.config.get('auto_start', False) and self.is_market_open():
                self.start_trading()
            
            # Run GUI event loop if not headless
            if not self.headless and self.gui_app:
                self.gui_app.exec()
            else:
                # Keep running until shutdown signal
                while not self._shutdown_event.is_set():
                    await asyncio.sleep(1)
                    
                    # Periodic health check
                    if int(time.time()) % 60 == 0:
                        await self._health_check()
        
        except KeyboardInterrupt:
            self.logger.info("Received keyboard interrupt")
        except Exception as e:
            self.logger.error(f"Application error: {e}")
            self.error_handler.handle_error(e, "main_run_loop")
            raise
        finally:
            # Always perform cleanup
            await self._cleanup_resources()

    async def _health_check(self):
        """Perform periodic health check"""
        try:
            health_status = {
                'timestamp': datetime.now().isoformat(),
                'state': self.state.name,
                'components': self.component_status.copy(),
                'uptime': str(datetime.now() - self.start_time) if self.start_time else None
            }
            
            # Check component health
            if self.trading_engine:
                health_status['trading_engine'] = self.trading_engine.get_health_status()
            
            if self.spyder_client and self.spyder_client.is_connected():
                health_status['broker_connected'] = True
            
            # Log health status
            self.logger.debug(f"Health check: {health_status}")
            
            # Emit health event
            self.event_manager.emit(
                EventType.SYSTEM,
                {
                    'type': 'health_check',
                    'status': health_status
                }
            )
            
        except Exception as e:
            self.logger.error(f"Health check error: {e}")

    async def _cleanup_resources(self):
        """Clean up all resources properly"""
        self.logger.info("Cleaning up resources...")
        
        try:
            # Save application state
            await self._save_state()
            
            # Stop components in reverse order
            cleanup_tasks = []
            
            if self.trading_engine and self.is_running:
                cleanup_tasks.append(self._cleanup_component("trading_engine", self.trading_engine.shutdown))
            
            if self.risk_manager:
                cleanup_tasks.append(self._cleanup_component("risk_manager", self.risk_manager.shutdown))
            
            if self.spyder_client and self.spyder_client.is_connected():
                cleanup_tasks.append(self._cleanup_component("broker_client", self.spyder_client.disconnect))
            
            if self.dal:
                cleanup_tasks.append(self._cleanup_component("database", self.dal.close_all_connections))
            
            if self.event_manager:
                cleanup_tasks.append(self._cleanup_component("event_manager", self.event_manager.stop))
            
            # Run cleanup tasks concurrently with timeout
            if cleanup_tasks:
                await asyncio.gather(*cleanup_tasks, return_exceptions=True)
            
            # Close GUI
            if self.gui_app:
                self.gui_app.quit()
            
            self.logger.info("Resource cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
            # Don't re-raise in cleanup

    async def _cleanup_component(self, name: str, cleanup_func):
        """Clean up a single component with timeout"""
        try:
            self.logger.info(f"Cleaning up {name}...")
            
            # Handle both sync and async cleanup functions
            if asyncio.iscoroutinefunction(cleanup_func):
                await asyncio.wait_for(cleanup_func(), timeout=10)
            else:
                await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(None, cleanup_func),
                    timeout=10
                )
            
            self.logger.info(f"✓ {name} cleaned up")
            
        except asyncio.TimeoutError:
            self.logger.error(f"Timeout cleaning up {name}")
        except Exception as e:
            self.logger.error(f"Error cleaning up {name}: {e}")

    async def _save_state(self):
        """Save application state to disk"""
        try:
            state_file = STATE_PATH / "app_state.json"
            
            state_data = {
                'version': VERSION,
                'shutdown_time': datetime.now().isoformat(),
                'last_state': self.state.name,
                'component_status': self.component_status,
                'session_duration': str(datetime.now() - self.start_time) if self.start_time else None,
                'config_checksum': self.config.get_checksum()
            }
            
            # Add trading engine state if available
            if self.trading_engine:
                state_data['trading_engine'] = self.trading_engine.get_state()
            
            # Write state file
            with open(state_file, 'w') as f:
                json.dump(state_data, f, indent=2)
            
            self.logger.info(f"Application state saved to {state_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to save state: {e}")

    async def shutdown(self):
        """Perform graceful shutdown with proper state transitions."""
        if self.state == AppState.STOPPED:
            return
            
        self.logger.info("Initiating graceful shutdown...")
        self._transition_state(AppState.STOPPING)
        
        try:
            # Signal shutdown
            self._shutdown_event.set()
            
            # Stop trading if active
            if self.is_running:
                self.stop_trading()
            
            # Disconnect from broker
            if self.spyder_client and self.spyder_client.is_connected():
                self.logger.info("Disconnecting from Interactive Brokers...")
                await self.spyder_client.disconnect_async()
            
            # Transition to stopped state
            self._transition_state(AppState.STOPPED)
            
            self.logger.info("Shutdown completed successfully")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
            self.error_handler.handle_error(e, "shutdown")

    # =============================================================================
    # Event Handlers
    # =============================================================================
    def _on_system_error(self, event: Event):
        """Handle system error events"""
        self.logger.error(f"System error: {event.data}")
        
        # Determine if error is recoverable
        if event.data.get('severity') == 'critical':
            self._transition_state(AppState.ERROR)
            asyncio.create_task(self.shutdown())

    def _on_critical_error(self, event: Event):
        """Handle critical error events"""
        self.logger.critical(f"Critical error: {event.data}")
        self._transition_state(AppState.ERROR)
        
        # Immediate shutdown for critical errors
        asyncio.create_task(self.shutdown())

    def _on_risk_limit_exceeded(self, event: Event):
        """Handle risk limit exceeded events"""
        self.logger.warning(f"Risk limit exceeded: {event.data}")
        
        # Pause trading on risk limit breach
        if self.state == AppState.TRADING:
            self._transition_state(AppState.PAUSED)
            if self.trading_engine:
                self.trading_engine.pause("Risk limit exceeded")

    def _on_connection_lost(self, event: Event):
        """Handle broker connection lost events"""
        self.logger.error("Broker connection lost")
        
        if self.state == AppState.TRADING:
            self.stop_trading()
        
        self._transition_state(AppState.READY)
        
        # Attempt reconnection if configured
        if self.config.get('auto_reconnect', True):
            asyncio.create_task(self._attempt_reconnection())

    async def _attempt_reconnection(self):
        """Attempt to reconnect to broker"""
        await asyncio.sleep(30)  # Wait before reconnecting
        
        if self.state == AppState.READY:
            self.logger.info("Attempting to reconnect to broker...")
            if await self.connect_broker():
                self.logger.info("Reconnection successful")
                
                # Resume trading if configured
                if self.config.get('auto_resume', False) and self.is_market_open():
                    self.start_trading()

# =============================================================================
# Main Entry Point
# =============================================================================
async def main():
    """Main entry point for the application."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description=f"{APPLICATION_NAME} v{VERSION}")
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to configuration file",
        default=DEFAULT_CONFIG_PATH
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without GUI"
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{APPLICATION_NAME} v{VERSION}"
    )
    
    args = parser.parse_args()
    
    # Create and run application
    app = SpyderApplication(
        config_path=args.config,
        headless=args.headless
    )
    
    try:
        await app.run()
    except Exception as e:
        print(f"Fatal error: {e}")
        traceback.print_exc()
        sys.exit(1)
    finally:
        await app.shutdown()

if __name__ == "__main__":
    # Run the application
    asyncio.run(main())
