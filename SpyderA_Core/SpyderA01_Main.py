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
    from SpyderA_Core.SpyderA04_DatabaseManager import DatabaseManager
    from SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType
    from SpyderB_Broker.SpyderB01_IBClient import IBClient
    from SpyderE_Risk.SpyderE01_RiskManager import RiskManager
    from SpyderG_UI.SpyderG01_MainWindow import MainWindow
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
DEFAULT_CONFIG_FILE = "config/spyder_config.json"
LOG_FILE = "logs/spyder_main.log"

# Trading session times
MARKET_OPEN = dt_time(9, 30)  # 9:30 AM ET
MARKET_CLOSE = dt_time(16, 0)  # 4:00 PM ET
PRE_MARKET_START = dt_time(4, 0)  # 4:00 AM ET
AFTER_HOURS_END = dt_time(20, 0)  # 8:00 PM ET

# =============================================================================
# Main Application Class
# =============================================================================
class SpyderApplication:
    """
    Main application controller for the Spyder trading system.
    
    This class manages the lifecycle of all system components and coordinates
    their interactions. It handles initialization, startup, monitoring, and
    shutdown procedures.
    
    Attributes:
        config: Configuration manager instance
        logger: Main application logger
        event_manager: Central event management system
        database: Database connection manager
        ib_client: Interactive Brokers client
        trading_engine: Core trading engine
        risk_manager: Risk management system
        ui: User interface (optional)
        running: Application state flag
    """
    
    def __init__(self, config_file: str = DEFAULT_CONFIG_FILE, 
                 headless: bool = False):
        """
        Initialize the Spyder application.
        
        Args:
            config_file: Path to configuration file
            headless: Run without GUI
        """
        self.config_file = config_file
        self.headless = headless
        self.running = False
        
        # Initialize logger first
        self.logger = get_logger(__name__)
        self.logger.info(f"Initializing {APPLICATION_NAME} v{VERSION}")
        
        # Initialize error handler
        self.error_handler = SpyderErrorHandler()
        
        # Initialize components (will be created in startup)
        self.config = None
        self.event_manager = None
        self.database = None
        self.ib_client = None
        self.trading_engine = None
        self.risk_manager = None
        self.ui = None
        self.qt_app = None
        
        # Signal handlers
        self._setup_signal_handlers()
        
    def _setup_signal_handlers(self):
        """Setup system signal handlers for graceful shutdown."""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        if hasattr(signal, 'SIGBREAK'):  # Windows
            signal.signal(signal.SIGBREAK, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle system signals for graceful shutdown."""
        self.logger.info(f"Received signal {signum}, initiating shutdown...")
        self.shutdown()
        
    # =========================================================================
    # Initialization Methods
    # =========================================================================
    
    def initialize(self) -> bool:
        """
        Initialize all system components.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            self.logger.info("Starting component initialization...")
            
            # Load configuration
            self.logger.info("Loading configuration...")
            self.config = ConfigManager(self.config_file)
            if not self.config.load():
                self.logger.error("Failed to load configuration")
                return False
            
            # Initialize event manager
            self.logger.info("Initializing event manager...")
            self.event_manager = EventManager()
            
            # Initialize database
            self.logger.info("Initializing database connection...")
            self.database = DatabaseManager(self.config.get_database_config())
            if not self.database.connect():
                self.logger.error("Failed to connect to database")
                return False
            
            # Initialize IB client
            self.logger.info("Initializing Interactive Brokers client...")
            self.ib_client = IBClient(
                host=self.config.get('ib.host', 'localhost'),
                port=self.config.get('ib.port', 7497),
                client_id=self.config.get('ib.client_id', 1)
            )
            
            # Initialize risk manager
            self.logger.info("Initializing risk manager...")
            self.risk_manager = RiskManager(
                self.config.get_risk_config(),
                self.event_manager
            )
            
            # Initialize trading engine
            self.logger.info("Initializing trading engine...")
            self.trading_engine = TradingEngine(
                self.config,
                self.event_manager,
                self.ib_client,
                self.risk_manager,
                self.database
            )
            
            # Initialize UI if not headless
            if not self.headless:
                self.logger.info("Initializing user interface...")
                self.qt_app = QApplication(sys.argv)
                self.ui = MainWindow(self)
            
            self.logger.info("All components initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize components: {str(e)}")
            self.error_handler.handle_error(e)
            return False
    
    # =========================================================================
    # Startup Methods
    # =========================================================================
    
    def startup(self) -> bool:
        """
        Start all system components.
        
        Returns:
            bool: True if startup successful
        """
        try:
            self.logger.info("Starting system components...")
            
            # Connect to IB
            self.logger.info("Connecting to Interactive Brokers...")
            if not self.ib_client.connect():
                self.logger.error("Failed to connect to Interactive Brokers")
                return False
            
            # Start event manager
            self.logger.info("Starting event manager...")
            self.event_manager.start()
            
            # Start trading engine
            self.logger.info("Starting trading engine...")
            self.trading_engine.start()
            
            # Start risk manager
            self.logger.info("Starting risk manager...")
            self.risk_manager.start()
            
            # Show UI if not headless
            if self.ui:
                self.logger.info("Showing user interface...")
                self.ui.show()
            
            self.running = True
            self.logger.info("System startup completed successfully")
            
            # Emit startup event
            self.event_manager.emit(Event(
                EventType.SYSTEM_STARTUP,
                {"timestamp": datetime.now(), "version": VERSION}
            ))
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start system: {str(e)}")
            self.error_handler.handle_error(e)
            return False
    
    # =========================================================================
    # Main Run Loop
    # =========================================================================
    
    def run(self):
        """Main application run loop."""
        if not self.running:
            self.logger.error("Cannot run - system not started")
            return
        
        self.logger.info(f"{APPLICATION_NAME} is running...")
        
        try:
            if self.headless:
                # Run in headless mode
                self._run_headless()
            else:
                # Run with Qt event loop
                self._run_with_ui()
                
        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
        except Exception as e:
            self.logger.error(f"Unexpected error in main loop: {str(e)}")
            self.error_handler.handle_error(e)
        finally:
            self.shutdown()
    
    def _run_headless(self):
        """Run application in headless mode."""
        self.logger.info("Running in headless mode...")
        
        # Simple event loop
        while self.running:
            try:
                time.sleep(1)
                
                # Check if within trading hours
                if self._is_trading_hours():
                    # Process any pending tasks
                    pass
                    
            except Exception as e:
                self.logger.error(f"Error in headless loop: {str(e)}")
                self.error_handler.handle_error(e)
    
    def _run_with_ui(self):
        """Run application with Qt UI."""
        self.logger.info("Running with user interface...")
        
        # Setup periodic tasks
        self._setup_periodic_tasks()
        
        # Run Qt event loop
        sys.exit(self.qt_app.exec_())
    
    def _setup_periodic_tasks(self):
        """Setup periodic tasks for the application."""
        # Health check timer
        self.health_timer = QTimer()
        self.health_timer.timeout.connect(self._perform_health_check)
        self.health_timer.start(60000)  # Every minute
        
        # Performance monitor timer
        self.perf_timer = QTimer()
        self.perf_timer.timeout.connect(self._monitor_performance)
        self.perf_timer.start(5000)  # Every 5 seconds
    
    # =========================================================================
    # Monitoring Methods
    # =========================================================================
    
    def _perform_health_check(self):
        """Perform system health check."""
        try:
            health_status = {
                "timestamp": datetime.now(),
                "ib_connected": self.ib_client.is_connected(),
                "database_connected": self.database.is_connected(),
                "trading_engine_active": self.trading_engine.is_active(),
                "risk_manager_active": self.risk_manager.is_active(),
            }
            
            # Log health status
            self.logger.debug(f"Health check: {health_status}")
            
            # Emit health check event
            self.event_manager.emit(Event(
                EventType.HEALTH_CHECK,
                health_status
            ))
            
            # Check for issues
            if not all([
                health_status["ib_connected"],
                health_status["database_connected"]
            ]):
                self.logger.warning("Health check detected issues")
                
        except Exception as e:
            self.logger.error(f"Error in health check: {str(e)}")
    
    def _monitor_performance(self):
        """Monitor system performance."""
        try:
            # Get performance metrics
            metrics = {
                "timestamp": datetime.now(),
                "active_positions": self.trading_engine.get_position_count(),
                "pending_orders": self.trading_engine.get_pending_order_count(),
                "memory_usage": self._get_memory_usage(),
                "cpu_usage": self._get_cpu_usage(),
            }
            
            # Emit performance event
            self.event_manager.emit(Event(
                EventType.PERFORMANCE_UPDATE,
                metrics
            ))
            
        except Exception as e:
            self.logger.error(f"Error monitoring performance: {str(e)}")
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def _is_trading_hours(self) -> bool:
        """Check if current time is within trading hours."""
        now = datetime.now(pytz.timezone('US/Eastern')).time()
        return MARKET_OPEN <= now <= MARKET_CLOSE
    
    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        import psutil
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024
    
    def _get_cpu_usage(self) -> float:
        """Get current CPU usage percentage."""
        import psutil
        return psutil.cpu_percent(interval=0.1)
    
    # =========================================================================
    # Shutdown Methods
    # =========================================================================
    
    def shutdown(self):
        """Perform graceful shutdown of all components."""
        if not self.running:
            return
        
        self.logger.info("Initiating system shutdown...")
        self.running = False
        
        try:
            # Emit shutdown event
            if self.event_manager:
                self.event_manager.emit(Event(
                    EventType.SYSTEM_SHUTDOWN,
                    {"timestamp": datetime.now()}
                ))
            
            # Stop components in reverse order
            if self.trading_engine:
                self.logger.info("Stopping trading engine...")
                self.trading_engine.stop()
            
            if self.risk_manager:
                self.logger.info("Stopping risk manager...")
                self.risk_manager.stop()
            
            if self.event_manager:
                self.logger.info("Stopping event manager...")
                self.event_manager.stop()
            
            if self.ib_client:
                self.logger.info("Disconnecting from Interactive Brokers...")
                self.ib_client.disconnect()
            
            if self.database:
                self.logger.info("Closing database connection...")
                self.database.disconnect()
            
            # Close UI
            if self.ui:
                self.ui.close()
            
            self.logger.info("System shutdown completed")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {str(e)}")
            self.error_handler.handle_error(e)


# =============================================================================
# Main Entry Point
# =============================================================================
def main():
    """Main entry point for the Spyder application."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description=f"{APPLICATION_NAME} v{VERSION}"
    )
    parser.add_argument(
        "--config", "-c",
        default=DEFAULT_CONFIG_FILE,
        help="Configuration file path"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without GUI"
    )
    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"{APPLICATION_NAME} v{VERSION}"
    )
    
    args = parser.parse_args()
    
    # Create and run application
    app = SpyderApplication(
        config_file=args.config,
        headless=args.headless
    )
    
    # Initialize
    if not app.initialize():
        print("Failed to initialize application")
        sys.exit(1)
    
    # Start
    if not app.startup():
        print("Failed to start application")
        sys.exit(1)
    
    # Run
    app.run()


if __name__ == "__main__":
    main()