#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderA_Core
Module: SpyderA01_Main.py
Purpose: Primary application controller and system coordinator
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-27 Time: 18:00:00

Module Description:
    This module serves as the main entry point and system coordinator for the
    Spyder autonomous trading system. It initializes all core components,
    manages the application lifecycle, coordinates subsystem interactions,
    and handles graceful startup/shutdown procedures. Includes simulation
    capabilities for development and testing when live Gateway connection
    is unavailable.

"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import argparse
import signal
import sys
import threading
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum, auto
import traceback

# ==============================================================================
# Add project root to Python path
# ==============================================================================
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    import pandas as pd
    import pytz
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QTimer
    HAS_GUI_SUPPORT = True
except ImportError as e:
    print(f"Warning: GUI dependencies not available: {e}")
    HAS_GUI_SUPPORT = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
    from SpyderU_Utilities.SpyderU10_TradingCalendar import TradingCalendar
    HAS_UTILITIES = True
except ImportError as e:
    print(f"Warning: Spyder utilities not available: {e}")
    HAS_UTILITIES = False

try:
    from SpyderA_Core.SpyderA03_Configuration import ConfigManager
    from SpyderA_Core.SpyderA05_EventManager import EventManager, EventType, Event
    HAS_CORE_MODULES = True
except ImportError:
    print("Warning: Core modules not available - using fallbacks")
    HAS_CORE_MODULES = False

try:
    from SpyderB_Broker.SpyderB05_ConnectionManager import get_connection_manager, ConnectionConfig
    from SpyderB_Broker.SpyderB01_SpyderClient import SpyderClient
    HAS_BROKER_MODULES = True
except ImportError:
    print("Warning: Broker modules not available - simulation mode only")
    HAS_BROKER_MODULES = False

# ==============================================================================
# CONSTANTS
# ==============================================================================
# System configuration
SPYDER_VERSION = "1.0"
SYSTEM_NAME = "Spyder Autonomous Options Trading System"

# Confirmed working connection parameters
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 4002
MASTER_CLIENT_ID = 2  # Master coordination client ID
ORDER_CLIENT_ID = 1   # Order execution client ID

# Application states
DEFAULT_CONFIG_PATH = Path.home() / ".spyder" / "config"
DEFAULT_LOG_PATH = Path.home() / ".spyder" / "logs"
DEFAULT_DATA_PATH = Path.home() / ".spyder" / "data"

# Market hours (EST)
MARKET_OPEN_TIME = "09:30"
MARKET_CLOSE_TIME = "16:00"
PRE_MARKET_START = "04:00"
AFTER_HOURS_END = "20:00"

# ==============================================================================
# ENUMS
# ==============================================================================
class SystemState(Enum):
    """System state enumeration"""
    INITIALIZING = "initializing"
    CONNECTING = "connecting"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"

class TradingMode(Enum):
    """Trading mode enumeration"""
    SIMULATION = "simulation"
    PAPER = "paper"
    LIVE = "live"

class ShutdownReason(Enum):
    """Shutdown reason enumeration"""
    USER_REQUEST = "user_request"
    MARKET_CLOSE = "market_close"
    ERROR = "error"
    SIGNAL = "signal"
    EMERGENCY = "emergency"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class SystemConfig:
    """System configuration parameters"""
    trading_mode: TradingMode = TradingMode.SIMULATION
    enable_gui: bool = True
    headless: bool = False
    
    # Connection settings
    ib_host: str = DEFAULT_HOST
    ib_port: int = DEFAULT_PORT
    master_client_id: int = MASTER_CLIENT_ID
    order_client_id: int = ORDER_CLIENT_ID
    connection_timeout: int = 30
    
    # Trading settings
    enable_trading: bool = False
    auto_start_trading: bool = False
    respect_market_hours: bool = True
    
    # Paths
    config_path: Path = DEFAULT_CONFIG_PATH
    log_path: Path = DEFAULT_LOG_PATH
    data_path: Path = DEFAULT_DATA_PATH
    
    # System settings
    max_positions: int = 10
    max_daily_loss: float = 1000.0
    enable_risk_management: bool = True

@dataclass
class SystemStatus:
    """Current system status"""
    state: SystemState
    trading_mode: TradingMode
    start_time: Optional[datetime] = None
    connection_status: str = "disconnected"
    active_strategies: int = 0
    open_positions: int = 0
    daily_pnl: float = 0.0
    total_pnl: float = 0.0
    last_update: Optional[datetime] = None

@dataclass
class SubsystemStatus:
    """Individual subsystem status"""
    name: str
    initialized: bool = False
    healthy: bool = False
    last_heartbeat: Optional[datetime] = None
    error_count: int = 0
    last_error: Optional[str] = None

# ==============================================================================
# MAIN APPLICATION CLASS
# ==============================================================================
class SpyderApplication:
    """
    Primary application controller and system coordinator for Spyder.
    
    This class manages the complete lifecycle of the autonomous trading system,
    including initialization, coordination between subsystems, trading
    execution, risk management, and graceful shutdown procedures. It supports
    both live trading with IB Gateway and simulation mode for development.
    
    Attributes:
        config: System configuration
        state: Current system state
        status: System status information
        logger: Application logger
        event_manager: System event coordinator
        connection_manager: IB Gateway connection manager
        
    Example:
        >>> app = SpyderApplication()
        >>> await app.initialize()
        >>> await app.run()
    """
    
    def __init__(self, config: Optional[SystemConfig] = None):
        """Initialize the Spyder application."""
        
        # Configuration
        self.config = config or SystemConfig()
        
        # Core state
        self.state = SystemState.INITIALIZING
        self.status = SystemStatus(
            state=self.state,
            trading_mode=self.config.trading_mode
        )
        
        # Initialize logging
        self._setup_logging()
        
        # Core components
        self.event_manager: Optional[EventManager] = None
        self.connection_manager = None
        self.spyder_client = None
        self.trading_engine = None
        self.risk_manager = None
        
        # GUI components
        self.qt_app: Optional[QApplication] = None
        self.main_window = None
        
        # System management
        self._running = False
        self._shutdown_requested = False
        self._shutdown_reason: Optional[ShutdownReason] = None
        self._subsystems: Dict[str, SubsystemStatus] = {}
        self._background_tasks: List[asyncio.Task] = []
        
        # Threading
        self._main_thread = threading.current_thread()
        self._shutdown_event = threading.Event()
        self._heartbeat_task: Optional[asyncio.Task] = None
        
        # Performance tracking
        self._start_time: Optional[datetime] = None
        self._metrics = {
            'uptime': 0.0,
            'trades_executed': 0,
            'errors_handled': 0,
            'connections_established': 0
        }
        
        self.logger.info(f"SpyderApplication initialized in {self.config.trading_mode.value} mode")

    # ==========================================================================
    # INITIALIZATION AND SETUP
    # ==========================================================================
    
    def _setup_logging(self):
        """Setup application logging."""
        if HAS_UTILITIES:
            self.logger = SpyderLogger.get_logger(__name__)
            self.error_handler = SpyderErrorHandler()
        else:
            # Fallback logging
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            self.logger = logging.getLogger(__name__)
            self.error_handler = None
        
        # Ensure log directory exists
        self.config.log_path.mkdir(parents=True, exist_ok=True)
    
    async def initialize(self) -> bool:
        """
        Initialize all system components.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            self.logger.info("=" * 60)
            self.logger.info(f"INITIALIZING {SYSTEM_NAME}")
            self.logger.info(f"Version: {SPYDER_VERSION}")
            self.logger.info(f"Mode: {self.config.trading_mode.value}")
            self.logger.info("=" * 60)
            
            self._start_time = datetime.now()
            self.status.start_time = self._start_time
            
            # Initialize core directories
            self._setup_directories()
            
            # Initialize core components
            if not await self._initialize_core_components():
                self.logger.error("Core component initialization failed")
                return False
            
            # Initialize trading components
            if not await self._initialize_trading_components():
                self.logger.error("Trading component initialization failed")
                return False
            
            # Initialize GUI if enabled
            if self.config.enable_gui and not self.config.headless and HAS_GUI_SUPPORT:
                if not self._initialize_gui():
                    self.logger.warning("GUI initialization failed - continuing in headless mode")
                    self.config.enable_gui = False
            
            # Setup signal handlers
            self._setup_signal_handlers()
            
            # Start background tasks
            await self._start_background_tasks()
            
            self.state = SystemState.READY
            self.status.state = self.state
            
            self.logger.info("System initialization completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"System initialization failed: {e}")
            self.logger.error(traceback.format_exc())
            self.state = SystemState.ERROR
            return False
    
    def _setup_directories(self):
        """Setup required directories."""
        for path in [self.config.config_path, self.config.log_path, self.config.data_path]:
            path.mkdir(parents=True, exist_ok=True)
    
    async def _initialize_core_components(self) -> bool:
        """Initialize core system components."""
        try:
            self.logger.info("Initializing core components...")
            
            # Event manager
            if HAS_CORE_MODULES:
                self.event_manager = EventManager()
                self._register_subsystem("event_manager", True, True)
            else:
                self.logger.warning("Event manager not available - using simple event handling")
            
            # Configuration manager
            if HAS_CORE_MODULES:
                self.config_manager = ConfigManager()
                self._register_subsystem("config_manager", True, True)
            
            # Trading calendar
            if HAS_UTILITIES:
                self.trading_calendar = TradingCalendar()
                self._register_subsystem("trading_calendar", True, True)
            
            self.logger.info("Core components initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Core component initialization error: {e}")
            return False
    
    async def _initialize_trading_components(self) -> bool:
        """Initialize trading-related components."""
        try:
            self.logger.info("Initializing trading components...")
            
            # Connection manager (with simulation fallback)
            if self.config.trading_mode != TradingMode.SIMULATION:
                success = await self._initialize_broker_connection()
                if not success and self.config.trading_mode != TradingMode.SIMULATION:
                    self.logger.warning("Broker connection failed - switching to simulation mode")
                    self.config.trading_mode = TradingMode.SIMULATION
                    self.status.trading_mode = TradingMode.SIMULATION
            
            if self.config.trading_mode == TradingMode.SIMULATION:
                self.logger.info("Running in simulation mode - using mock trading components")
                self._initialize_simulation_mode()
            
            self.logger.info("Trading components initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Trading component initialization error: {e}")
            return False
    
    async def _initialize_broker_connection(self) -> bool:
        """Initialize broker connection with confirmed parameters."""
        if not HAS_BROKER_MODULES:
            self.logger.warning("Broker modules not available")
            return False
        
        try:
            self.logger.info("Initializing broker connection...")
            
            # Create connection configuration with confirmed working parameters
            connection_config = ConnectionConfig()
            connection_config.client_id = self.config.master_client_id
            connection_config.host = self.config.ib_host
            connection_config.port = self.config.ib_port
            connection_config.timeout = self.config.connection_timeout
            connection_config.readonly = False  # Allow trading operations
            
            # Get connection manager
            self.connection_manager = get_connection_manager(connection_config)
            
            # Start connection manager
            self.connection_manager.start()
            
            # Attempt connection with timeout handling
            self.logger.info(f"Connecting to IB Gateway: {self.config.ib_host}:{self.config.ib_port}")
            self.logger.info(f"Using master client ID: {self.config.master_client_id}")
            
            # Try connection with proper error handling
            connection_success = await asyncio.wait_for(
                asyncio.to_thread(self.connection_manager.connect),
                timeout=self.config.connection_timeout
            )
            
            if connection_success:
                self.logger.info("Broker connection established successfully")
                self.status.connection_status = "connected"
                self._register_subsystem("connection_manager", True, True)
                self._metrics['connections_established'] += 1
                return True
            else:
                self.logger.warning("Broker connection failed")
                self.status.connection_status = "failed"
                return False
                
        except asyncio.TimeoutError:
            self.logger.warning("Broker connection timeout - this is the known API handshake issue")
            self.status.connection_status = "timeout"
            return False
        except Exception as e:
            self.logger.error(f"Broker connection error: {e}")
            self.status.connection_status = f"error: {str(e)}"
            return False
    
    def _initialize_simulation_mode(self):
        """Initialize simulation mode components."""
        self.logger.info("Initializing simulation mode...")
        
        # Create mock trading components
        self.simulation_client = MockSpyderClient()
        self.simulation_data_feed = MockDataFeed()
        
        self._register_subsystem("simulation_client", True, True)
        self._register_subsystem("simulation_data_feed", True, True)
        
        self.logger.info("Simulation mode initialized")
    
    def _initialize_gui(self) -> bool:
        """Initialize GUI components."""
        try:
            if not HAS_GUI_SUPPORT:
                return False
            
            self.logger.info("Initializing GUI...")
            
            # Create Qt application if not exists
            if QApplication.instance() is None:
                self.qt_app = QApplication(sys.argv)
                self.qt_app.setApplicationName("Spyder Trading System")
                self.qt_app.setApplicationVersion(SPYDER_VERSION)
            else:
                self.qt_app = QApplication.instance()
            
            # Initialize main window (when GUI modules are available)
            # For now, just setup for future integration
            self._register_subsystem("gui", True, True)
            
            self.logger.info("GUI initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"GUI initialization error: {e}")
            return False

    # ==========================================================================
    # SYSTEM LIFECYCLE
    # ==========================================================================
    
    async def run(self) -> int:
        """
        Main application run loop.
        
        Returns:
            int: Exit code (0 for success)
        """
        try:
            if self.state != SystemState.READY:
                self.logger.error("System not properly initialized")
                return 1
            
            self.logger.info("Starting main application loop...")
            self.state = SystemState.RUNNING
            self.status.state = self.state
            self._running = True
            
            # Start heartbeat monitoring
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            
            # Main application loop
            while self._running and not self._shutdown_requested:
                try:
                    # Update system status
                    await self._update_system_status()
                    
                    # Process events if available
                    if self.event_manager:
                        await self._process_events()
                    
                    # Health check subsystems
                    await self._health_check()
                    
                    # Trading operations
                    if self.config.enable_trading:
                        await self._trading_cycle()
                    
                    # Brief pause to prevent CPU spinning
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    self.logger.error(f"Error in main loop: {e}")
                    self._metrics['errors_handled'] += 1
                    
                    if self.error_handler:
                        self.error_handler.handle_exception(e)
            
            # Shutdown sequence
            await self._shutdown()
            
            self.logger.info("Application shutdown completed")
            return 0
            
        except KeyboardInterrupt:
            self.logger.info("Received keyboard interrupt")
            self._shutdown_reason = ShutdownReason.SIGNAL
            await self._shutdown()
            return 0
        except Exception as e:
            self.logger.error(f"Critical error in main loop: {e}")
            self.logger.error(traceback.format_exc())
            await self._emergency_shutdown()
            return 1
    
    async def _trading_cycle(self):
        """Execute one trading cycle."""
        try:
            # Market hours check
            if self.config.respect_market_hours and hasattr(self, 'trading_calendar'):
                if not self.trading_calendar.is_market_open():
                    return
            
            # Trading logic placeholder
            # This will be implemented when strategies are integrated
            pass
            
        except Exception as e:
            self.logger.error(f"Trading cycle error: {e}")
    
    async def _update_system_status(self):
        """Update system status information."""
        try:
            now = datetime.now()
            
            # Update basic status
            self.status.last_update = now
            
            if self._start_time:
                self._metrics['uptime'] = (now - self._start_time).total_seconds()
            
            # Update connection status
            if self.connection_manager and hasattr(self.connection_manager, 'is_connected'):
                if self.connection_manager.is_connected():
                    self.status.connection_status = "connected"
                else:
                    self.status.connection_status = "disconnected"
            
        except Exception as e:
            self.logger.error(f"Status update error: {e}")

    # ==========================================================================
    # BACKGROUND TASKS
    # ==========================================================================
    
    async def _start_background_tasks(self):
        """Start background monitoring tasks."""
        try:
            # System monitoring task
            task = asyncio.create_task(self._system_monitor())
            self._background_tasks.append(task)
            
            self.logger.info("Background tasks started")
            
        except Exception as e:
            self.logger.error(f"Background task startup error: {e}")
    
    async def _heartbeat_loop(self):
        """System heartbeat loop."""
        while self._running and not self._shutdown_requested:
            try:
                # Update subsystem heartbeats
                for name, status in self._subsystems.items():
                    status.last_heartbeat = datetime.now()
                
                # Log periodic status
                if hasattr(self, '_start_time') and self._start_time:
                    uptime = datetime.now() - self._start_time
                    if uptime.total_seconds() % 300 == 0:  # Every 5 minutes
                        self.logger.info(f"System running - uptime: {uptime}")
                
                await asyncio.sleep(30)  # 30 second heartbeat
                
            except Exception as e:
                self.logger.error(f"Heartbeat error: {e}")
                await asyncio.sleep(30)
    
    async def _system_monitor(self):
        """Background system monitoring."""
        while self._running and not self._shutdown_requested:
            try:
                # Monitor memory usage, CPU, disk space, etc.
                # Placeholder for system resource monitoring
                
                await asyncio.sleep(60)  # Monitor every minute
                
            except Exception as e:
                self.logger.error(f"System monitor error: {e}")
                await asyncio.sleep(60)
    
    async def _process_events(self):
        """Process pending system events."""
        try:
            if self.event_manager and hasattr(self.event_manager, 'get_pending_events'):
                events = self.event_manager.get_pending_events()
                
                for event in events:
                    await self._handle_event(event)
                    
        except Exception as e:
            self.logger.error(f"Event processing error: {e}")
    
    async def _handle_event(self, event):
        """Handle individual system event."""
        try:
            # Event handling logic placeholder
            self.logger.debug(f"Processing event: {event}")
            
        except Exception as e:
            self.logger.error(f"Event handling error: {e}")
    
    async def _health_check(self):
        """Perform system health checks."""
        try:
            unhealthy_subsystems = []
            
            for name, status in self._subsystems.items():
                if status.last_heartbeat:
                    time_since_heartbeat = datetime.now() - status.last_heartbeat
                    if time_since_heartbeat.total_seconds() > 120:  # 2 minutes
                        status.healthy = False
                        unhealthy_subsystems.append(name)
                    else:
                        status.healthy = True
            
            if unhealthy_subsystems:
                self.logger.warning(f"Unhealthy subsystems: {unhealthy_subsystems}")
                
        except Exception as e:
            self.logger.error(f"Health check error: {e}")

    # ==========================================================================
    # SYSTEM MANAGEMENT
    # ==========================================================================
    
    def _register_subsystem(self, name: str, initialized: bool = False, healthy: bool = False):
        """Register a subsystem for monitoring."""
        self._subsystems[name] = SubsystemStatus(
            name=name,
            initialized=initialized,
            healthy=healthy,
            last_heartbeat=datetime.now()
        )
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}")
            self._shutdown_reason = ShutdownReason.SIGNAL
            self._shutdown_requested = True
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def _shutdown(self):
        """Perform graceful system shutdown."""
        try:
            self.logger.info("Initiating graceful shutdown...")
            self.state = SystemState.STOPPING
            self.status.state = self.state
            
            # Stop background tasks
            for task in self._background_tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            
            # Stop heartbeat
            if self._heartbeat_task and not self._heartbeat_task.done():
                self._heartbeat_task.cancel()
                try:
                    await self._heartbeat_task
                except asyncio.CancelledError:
                    pass
            
            # Disconnect from broker
            if self.connection_manager:
                try:
                    self.connection_manager.stop()
                    self.logger.info("Broker connection closed")
                except Exception as e:
                    self.logger.error(f"Error closing broker connection: {e}")
            
            # Close GUI
            if self.qt_app:
                self.qt_app.quit()
            
            self._running = False
            self.state = SystemState.STOPPED
            self.status.state = self.state
            
            # Log final status
            if self._start_time:
                uptime = datetime.now() - self._start_time
                self.logger.info(f"System uptime: {uptime}")
                self.logger.info(f"Metrics: {self._metrics}")
            
            self.logger.info("Graceful shutdown completed")
            
        except Exception as e:
            self.logger.error(f"Shutdown error: {e}")
            await self._emergency_shutdown()
    
    async def _emergency_shutdown(self):
        """Emergency shutdown procedure."""
        try:
            self.logger.error("Performing emergency shutdown...")
            self.state = SystemState.ERROR
            
            # Force close connections
            if self.connection_manager:
                try:
                    self.connection_manager.stop()
                except:
                    pass
            
            # Force close GUI
            if self.qt_app:
                try:
                    self.qt_app.exit(1)
                except:
                    pass
            
            self._running = False
            self.logger.error("Emergency shutdown completed")
            
        except Exception as e:
            self.logger.error(f"Emergency shutdown error: {e}")

    # ==========================================================================
    # PUBLIC API
    # ==========================================================================
    
    def get_status(self) -> SystemStatus:
        """Get current system status."""
        return self.status
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get system metrics."""
        return self._metrics.copy()
    
    def is_running(self) -> bool:
        """Check if system is running."""
        return self._running and self.state == SystemState.RUNNING
    
    def request_shutdown(self, reason: ShutdownReason = ShutdownReason.USER_REQUEST):
        """Request graceful shutdown."""
        self._shutdown_reason = reason
        self._shutdown_requested = True
        self.logger.info(f"Shutdown requested: {reason.value}")

# ==============================================================================
# MOCK CLASSES FOR SIMULATION MODE
# ==============================================================================

class MockSpyderClient:
    """Mock Spyder client for simulation mode."""
    
    def __init__(self):
        self.connected = True
        self.account = "DU123456"
    
    def is_connected(self):
        return self.connected
    
    def get_managed_accounts(self):
        return [self.account]

class MockDataFeed:
    """Mock data feed for simulation mode."""
    
    def __init__(self):
        self.subscriptions = []
    
    def subscribe(self, symbol: str):
        if symbol not in self.subscriptions:
            self.subscriptions.append(symbol)
    
    def get_quote(self, symbol: str):
        # Return mock quote data
        return {
            'symbol': symbol,
            'bid': 400.0,
            'ask': 400.1,
            'last': 400.05,
            'timestamp': datetime.now()
        }

# ==============================================================================
# COMMAND LINE INTERFACE
# ==============================================================================

def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description=f"{SYSTEM_NAME} v{SPYDER_VERSION}",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Mode selection
    parser.add_argument(
        "--mode", 
        choices=["simulation", "paper", "live"],
        default="simulation",
        help="Trading mode"
    )
    
    # Connection settings
    parser.add_argument("--host", default=DEFAULT_HOST, help="IB Gateway host")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="IB Gateway port")
    parser.add_argument("--client-id", type=int, default=MASTER_CLIENT_ID, help="Master client ID")
    
    # System settings
    parser.add_argument("--no-gui", action="store_true", help="Run in headless mode")
    parser.add_argument("--enable-trading", action="store_true", help="Enable live trading")
    parser.add_argument("--config", type=Path, help="Configuration file path")
    
    # Logging
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], 
                       default="INFO", help="Logging level")
    
    return parser.parse_args()

def create_config_from_args(args: argparse.Namespace) -> SystemConfig:
    """Create system configuration from command line arguments."""
    config = SystemConfig()
    
    # Mode
    config.trading_mode = TradingMode(args.mode)
    
    # Connection
    config.ib_host = args.host
    config.ib_port = args.port
    config.master_client_id = args.client_id
    
    # System
    config.enable_gui = not args.no_gui
    config.headless = args.no_gui
    config.enable_trading = args.enable_trading
    
    # Paths
    if args.config:
        config.config_path = args.config
    
    return config

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

async def main() -> int:
    """Main application entry point."""
    try:
        # Parse command line arguments
        args = parse_arguments()
        
        # Create configuration
        config = create_config_from_args(args)
        
        # Set logging level
        if HAS_UTILITIES:
            logging.getLogger().setLevel(getattr(logging, args.log_level))
        
        # Create and initialize application
        app = SpyderApplication(config)
        
        # Initialize system
        if not await app.initialize():
            print("System initialization failed")
            return 1
        
        # Run application
        return await app.run()
        
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
        return 0
    except Exception as e:
        print(f"Critical error: {e}")
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    # Run the application
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nGoodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)
