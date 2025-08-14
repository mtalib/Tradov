"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderA06_MasterController.py
Group: A (Core)
Purpose: Master control and orchestration for entire Spyder system
Author: Mohamed Talib
Date Created: 2025-01-08
Last Updated: 2025-01-08 Time: 15:00:00

Description:
    Master Control Module that orchestrates the entire Spyder trading system.
    Manages startup/shutdown sequences, module dependencies, health monitoring,
    state management, and coordinates all components including risk management
    (E-series), ML engine (L-series), portfolio management (P-series),
    trading strategies (D-series), and broker connections (B-series).
"""

import asyncio
import json
import logging
import os
import pickle
import signal
import sys
import threading
import time
import traceback
from collections import OrderedDict, defaultdict
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import asdict, dataclass, field
from datetime import datetime
from datetime import time as dt_time
from datetime import timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

import psutil
import yaml

# ==================================================================================
# LOGGING CONFIGURATION
# ==================================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
    handlers=[logging.FileHandler("spyder_master.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# ==================================================================================
# ENUMS AND CONSTANTS
# ==================================================================================


class SystemStatus(Enum):
    """System operational status"""

    INITIALIZING = "initializing"
    STARTING = "starting"
    RUNNING = "running"
    TRADING = "trading"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    EMERGENCY_STOP = "emergency_stop"


class ModuleStatus(Enum):
    """Individual module status"""

    NOT_STARTED = "not_started"
    STARTING = "starting"
    RUNNING = "running"
    HEALTHY = "healthy"
    WARNING = "warning"
    ERROR = "error"
    STOPPED = "stopped"
    RESTARTING = "restarting"


class MarketState(Enum):
    """Market state"""

    PRE_MARKET = "pre_market"
    MARKET_OPEN = "market_open"
    MARKET_CLOSED = "market_closed"
    AFTER_HOURS = "after_hours"
    WEEKEND = "weekend"
    HOLIDAY = "holiday"


class TradingMode(Enum):
    """Trading mode"""

    PAPER = "paper"
    LIVE = "live"
    BACKTEST = "backtest"
    SIMULATION = "simulation"


# ==================================================================================
# DATA CLASSES
# ==================================================================================


@dataclass
class ModuleInfo:
    """Information about a system module"""

    module_id: str
    group: str
    name: str
    status: ModuleStatus
    dependencies: List[str]
    priority: int  # Startup priority (lower = earlier)
    health_check: Optional[Callable] = None
    restart_attempts: int = 0
    last_restart: Optional[datetime] = None
    error_count: int = 0
    last_error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemConfig:
    """System configuration"""

    trading_mode: TradingMode
    environment: str  # 'development', 'testing', 'production'
    portfolio_value: float
    max_daily_loss: float
    max_positions: int
    risk_limits: Dict[str, float]
    ib_gateway: Dict[str, Any]
    database: Dict[str, Any]
    ml_models_path: str
    data_path: str
    logs_path: str
    enable_alerts: bool
    enable_paper_trading: bool
    enable_ml_predictions: bool
    enable_risk_management: bool


@dataclass
class HealthMetrics:
    """System health metrics"""

    timestamp: datetime
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    network_latency: float
    module_health: Dict[str, str]
    active_positions: int
    daily_pnl: float
    risk_utilization: float
    error_rate: float


@dataclass
class StartupSequence:
    """Startup sequence definition"""

    phase: str
    modules: List[str]
    parallel: bool
    timeout: int  # seconds
    critical: bool  # If True, failure stops startup


# ==================================================================================
# MASTER CONTROLLER
# ==================================================================================


class MasterController:
    """
    Master control system for Spyder autonomous trading
    """

    def __init__(self, config_path: str = "config/spyder_config.yaml"):
        """Initialize master controller"""

        # Load configuration
        self.config = self._load_configuration(config_path)

        # System state
        self.status = SystemStatus.INITIALIZING
        self.market_state = MarketState.MARKET_CLOSED
        self.trading_enabled = False

        # Module registry
        self.modules: Dict[str, ModuleInfo] = {}
        self._initialize_module_registry()

        # Component references
        self.components = {}

        # Threading and async
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.shutdown_event = threading.Event()
        self.health_monitor_thread = None

        # Metrics and monitoring
        self.health_metrics = []
        self.startup_time = None
        self.shutdown_time = None

        # Signal handlers
        self._setup_signal_handlers()

        logger.info(f"Master Controller initialized in {self.config.environment} environment")

    # ==================================================================================
    # CONFIGURATION
    # ==================================================================================

    def _load_configuration(self, config_path: str) -> SystemConfig:
        """Load system configuration"""

        # Try to load from file
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                config_data = yaml.safe_load(f)
        else:
            # Use default configuration
            config_data = self._get_default_config()

        return SystemConfig(
            trading_mode=TradingMode(config_data.get("trading_mode", "paper")),
            environment=config_data.get("environment", "development"),
            portfolio_value=config_data.get("portfolio_value", 1000000),
            max_daily_loss=config_data.get("max_daily_loss", 50000),
            max_positions=config_data.get("max_positions", 10),
            risk_limits=config_data.get(
                "risk_limits", {"max_var": 0.10, "max_drawdown": 0.20, "max_concentration": 0.25}
            ),
            ib_gateway=config_data.get(
                "ib_gateway", {"host": "127.0.0.1", "port": 7497, "client_id": 1}
            ),
            database=config_data.get("database", {"type": "sqlite", "path": "data/spyder.db"}),
            ml_models_path=config_data.get("ml_models_path", "./models"),
            data_path=config_data.get("data_path", "./data"),
            logs_path=config_data.get("logs_path", "./logs"),
            enable_alerts=config_data.get("enable_alerts", True),
            enable_paper_trading=config_data.get("enable_paper_trading", True),
            enable_ml_predictions=config_data.get("enable_ml_predictions", True),
            enable_risk_management=config_data.get("enable_risk_management", True),
        )

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            "trading_mode": "paper",
            "environment": "development",
            "portfolio_value": 1000000,
            "max_daily_loss": 50000,
            "max_positions": 10,
            "risk_limits": {"max_var": 0.10, "max_drawdown": 0.20, "max_concentration": 0.25},
            "ib_gateway": {"host": "127.0.0.1", "port": 7497, "client_id": 1},
            "database": {"type": "sqlite", "path": "data/spyder.db"},
            "ml_models_path": "./models",
            "data_path": "./data",
            "logs_path": "./logs",
            "enable_alerts": True,
            "enable_paper_trading": True,
            "enable_ml_predictions": True,
            "enable_risk_management": True,
        }

    # ==================================================================================
    # MODULE REGISTRY
    # ==================================================================================

    def _initialize_module_registry(self):
        """Initialize the module registry with all system modules"""

        # Define module dependencies and startup order
        module_definitions = [
            # Core Infrastructure (Priority 1)
            ("H02_DatabaseManager", "H", "Database Manager", [], 1),
            ("U01_Logger", "U", "Logger", [], 1),
            ("U02_ErrorHandler", "U", "Error Handler", ["U01_Logger"], 1),
            # Communication Layer (Priority 2)
            ("I06_AgentMessageBus", "I", "Message Bus", [], 2),
            ("Z01_ZeroMQIntegration", "Z", "ZeroMQ", [], 2),
            # Broker Connection (Priority 3)
            ("B05_ConnectionManager", "B", "IB Connection", [], 3),
            ("B16_GatewayIntegration", "B", "Gateway Integration", ["B05_ConnectionManager"], 3),
            ("B01_SpyderClient", "B", "Spyder Client", ["B05_ConnectionManager"], 3),
            # Market Data (Priority 4)
            ("C01_DataFeed", "C", "Data Feed", ["B01_SpyderClient"], 4),
            ("C07_MarketDataHub", "C", "Market Data Hub", ["C01_DataFeed"], 4),
            ("C03_OptionChain", "C", "Option Chain", ["C01_DataFeed"], 4),
            # Risk Management (Priority 5)
            ("E11_MaxLossProtection", "E", "Max Loss Protection", ["I06_AgentMessageBus"], 5),
            ("E12_PortfolioVaR", "E", "Portfolio VaR", ["I06_AgentMessageBus"], 5),
            ("E13_TailRiskManager", "E", "Tail Risk Manager", ["E12_PortfolioVaR"], 5),
            (
                "E01_RiskManager",
                "E",
                "Risk Manager",
                ["E11_MaxLossProtection", "E12_PortfolioVaR"],
                5,
            ),
            # Portfolio Management (Priority 6)
            ("P05_MultiStrategyAllocator", "P", "Strategy Allocator", ["E01_RiskManager"], 6),
            ("P06_StrategyRotation", "P", "Strategy Rotation", ["P05_MultiStrategyAllocator"], 6),
            ("P01_PortfolioManager", "P", "Portfolio Manager", ["P05_MultiStrategyAllocator"], 6),
            # ML Engine (Priority 7)
            ("L18_EnhancedMLIntegration", "L", "ML Engine", ["C07_MarketDataHub"], 7),
            ("L01_MLPredictor", "L", "ML Predictor", ["L18_EnhancedMLIntegration"], 7),
            ("L09_RegimeClassifier", "L", "Regime Classifier", ["L18_EnhancedMLIntegration"], 7),
            # AI Agents (Priority 8)
            ("X16_MetaCoordinator", "X", "Meta Coordinator", ["I06_AgentMessageBus"], 8),
            ("X01_GreeksAgent", "X", "Greeks Agent", ["X16_MetaCoordinator"], 8),
            ("X02_FlowAgent", "X", "Flow Agent", ["X16_MetaCoordinator"], 8),
            ("X03_StrategyDirectorAgent", "X", "Strategy Director", ["X16_MetaCoordinator"], 8),
            (
                "X04_RiskGuardianAgent",
                "X",
                "Risk Guardian",
                ["X16_MetaCoordinator", "E01_RiskManager"],
                8,
            ),
            # Trading Strategies (Priority 9)
            ("D01_BaseStrategy", "D", "Base Strategy", ["P01_PortfolioManager"], 9),
            ("D02_IronCondor", "D", "Iron Condor", ["D01_BaseStrategy"], 9),
            ("D04_ZeroDTE", "D", "Zero DTE", ["D01_BaseStrategy"], 9),
            ("D05_Straddle", "D", "Straddle", ["D01_BaseStrategy"], 9),
            # Order Management (Priority 10)
            ("B02_OrderManager", "B", "Order Manager", ["B01_SpyderClient", "E01_RiskManager"], 10),
            ("B03_PositionTracker", "B", "Position Tracker", ["B02_OrderManager"], 10),
            # Analytics & Reporting (Priority 11)
            (
                "K10_RealTimePerformanceAnalytics",
                "K",
                "Performance Analytics",
                ["B03_PositionTracker"],
                11,
            ),
            (
                "K01_ReportGenerator",
                "K",
                "Report Generator",
                ["K10_RealTimePerformanceAnalytics"],
                11,
            ),
            # Monitoring (Priority 12)
            ("M01_SystemMonitor", "M", "System Monitor", [], 12),
            ("M03_AIAgentMonitor", "M", "AI Agent Monitor", ["X16_MetaCoordinator"], 12),
            # GUI (Priority 13)
            (
                "G05_TradingDashboard",
                "G",
                "Trading Dashboard",
                ["K10_RealTimePerformanceAnalytics"],
                13,
            ),
            # Alert System (Priority 14)
            ("J01_AlertManager", "J", "Alert Manager", ["I06_AgentMessageBus"], 14),
        ]

        # Create module info objects
        for module_id, group, name, deps, priority in module_definitions:
            self.modules[module_id] = ModuleInfo(
                module_id=module_id,
                group=group,
                name=name,
                status=ModuleStatus.NOT_STARTED,
                dependencies=deps,
                priority=priority,
                health_check=None,
                metadata={},
            )

    # ==================================================================================
    # SYSTEM STARTUP
    # ==================================================================================

    def start_system(self) -> bool:
        """Start the entire Spyder system"""

        try:
            logger.info("=" * 80)
            logger.info("SPYDER SYSTEM STARTUP INITIATED")
            logger.info(f"Mode: {self.config.trading_mode.value}")
            logger.info(f"Environment: {self.config.environment}")
            logger.info("=" * 80)

            self.startup_time = datetime.now()
            self.status = SystemStatus.STARTING

            # Define startup sequence
            startup_sequence = self._get_startup_sequence()

            # Execute startup phases
            for phase in startup_sequence:
                if not self._execute_startup_phase(phase):
                    logger.error(f"Startup failed at phase: {phase.phase}")
                    self.status = SystemStatus.ERROR
                    return False

            # Start health monitoring
            self._start_health_monitor()

            # Check market state
            self._update_market_state()

            # Enable trading if market is open
            if self.market_state == MarketState.MARKET_OPEN:
                self._enable_trading()

            self.status = SystemStatus.RUNNING

            elapsed = (datetime.now() - self.startup_time).total_seconds()
            logger.info(f"SYSTEM STARTUP COMPLETE in {elapsed:.2f} seconds")

            # Generate startup report
            self._generate_startup_report()

            return True

        except Exception as e:
            logger.error(f"System startup failed: {e}")
            logger.error(traceback.format_exc())
            self._emergency_shutdown()
            return False

    def _get_startup_sequence(self) -> List[StartupSequence]:
        """Define the startup sequence"""

        return [
            StartupSequence(
                phase="Core Infrastructure",
                modules=["H02_DatabaseManager", "U01_Logger", "U02_ErrorHandler"],
                parallel=True,
                timeout=30,
                critical=True,
            ),
            StartupSequence(
                phase="Communication Layer",
                modules=["I06_AgentMessageBus", "Z01_ZeroMQIntegration"],
                parallel=True,
                timeout=20,
                critical=True,
            ),
            StartupSequence(
                phase="Broker Connection",
                modules=["B05_ConnectionManager", "B16_GatewayIntegration", "B01_SpyderClient"],
                parallel=False,  # Sequential for IB connection
                timeout=60,
                critical=True,
            ),
            StartupSequence(
                phase="Market Data",
                modules=["C01_DataFeed", "C07_MarketDataHub", "C03_OptionChain"],
                parallel=True,
                timeout=30,
                critical=True,
            ),
            StartupSequence(
                phase="Risk Management",
                modules=[
                    "E11_MaxLossProtection",
                    "E12_PortfolioVaR",
                    "E13_TailRiskManager",
                    "E01_RiskManager",
                ],
                parallel=False,  # Sequential for proper initialization
                timeout=30,
                critical=True,
            ),
            StartupSequence(
                phase="Portfolio Management",
                modules=[
                    "P05_MultiStrategyAllocator",
                    "P06_StrategyRotation",
                    "P01_PortfolioManager",
                ],
                parallel=False,
                timeout=30,
                critical=True,
            ),
            StartupSequence(
                phase="ML Engine",
                modules=["L18_EnhancedMLIntegration", "L01_MLPredictor", "L09_RegimeClassifier"],
                parallel=False,
                timeout=60,
                critical=False,  # ML can fail without stopping system
            ),
            StartupSequence(
                phase="AI Agents",
                modules=[
                    "X16_MetaCoordinator",
                    "X01_GreeksAgent",
                    "X02_FlowAgent",
                    "X03_StrategyDirectorAgent",
                    "X04_RiskGuardianAgent",
                ],
                parallel=False,
                timeout=45,
                critical=False,
            ),
            StartupSequence(
                phase="Trading Strategies",
                modules=["D01_BaseStrategy", "D02_IronCondor", "D04_ZeroDTE", "D05_Straddle"],
                parallel=True,
                timeout=30,
                critical=True,
            ),
            StartupSequence(
                phase="Order Management",
                modules=["B02_OrderManager", "B03_PositionTracker"],
                parallel=False,
                timeout=20,
                critical=True,
            ),
            StartupSequence(
                phase="Analytics",
                modules=["K10_RealTimePerformanceAnalytics", "K01_ReportGenerator"],
                parallel=True,
                timeout=20,
                critical=False,
            ),
            StartupSequence(
                phase="Monitoring",
                modules=["M01_SystemMonitor", "M03_AIAgentMonitor"],
                parallel=True,
                timeout=20,
                critical=False,
            ),
            StartupSequence(
                phase="User Interface",
                modules=["G05_TradingDashboard", "J01_AlertManager"],
                parallel=True,
                timeout=30,
                critical=False,
            ),
        ]

    def _execute_startup_phase(self, phase: StartupSequence) -> bool:
        """Execute a startup phase"""

        logger.info(f"Starting phase: {phase.phase}")

        try:
            if phase.parallel:
                # Start modules in parallel
                futures = []
                for module_id in phase.modules:
                    future = self.executor.submit(self._start_module, module_id)
                    futures.append((module_id, future))

                # Wait for completion with timeout
                for module_id, future in futures:
                    try:
                        result = future.result(timeout=phase.timeout)
                        if not result and phase.critical:
                            logger.error(f"Critical module {module_id} failed to start")
                            return False
                    except TimeoutError:
                        logger.error(f"Module {module_id} startup timeout")
                        if phase.critical:
                            return False
            else:
                # Start modules sequentially
                for module_id in phase.modules:
                    if not self._start_module(module_id):
                        if phase.critical:
                            logger.error(f"Critical module {module_id} failed to start")
                            return False

            logger.info(f"Phase completed: {phase.phase}")
            return True

        except Exception as e:
            logger.error(f"Phase {phase.phase} failed: {e}")
            return False if phase.critical else True

    def _start_module(self, module_id: str) -> bool:
        """Start an individual module"""

        if module_id not in self.modules:
            logger.warning(f"Module {module_id} not found in registry")
            return True  # Non-fatal

        module = self.modules[module_id]

        try:
            logger.debug(f"Starting module: {module_id}")

            # Check dependencies
            for dep_id in module.dependencies:
                if dep_id in self.modules:
                    dep_status = self.modules[dep_id].status
                    if dep_status not in [ModuleStatus.RUNNING, ModuleStatus.HEALTHY]:
                        logger.warning(f"Dependency {dep_id} not ready for {module_id}")
                        return False

            # Simulate module startup (replace with actual module initialization)
            module.status = ModuleStatus.STARTING

            # Import and initialize the actual module
            component = self._initialize_component(module_id)
            if component:
                self.components[module_id] = component
                module.status = ModuleStatus.RUNNING
                logger.info(f"✓ Module started: {module_id}")
                return True
            else:
                module.status = ModuleStatus.ERROR
                return False

        except Exception as e:
            logger.error(f"Failed to start module {module_id}: {e}")
            module.status = ModuleStatus.ERROR
            module.last_error = str(e)
            module.error_count += 1
            return False

    def _initialize_component(self, module_id: str) -> Optional[Any]:
        """Initialize actual component (placeholder for real implementation)"""

        # This is where you would actually import and initialize the module
        # For now, return a mock object

        module_initializers = {
            "H02_DatabaseManager": lambda: {"type": "database", "connected": True},
            "I06_AgentMessageBus": lambda: {"type": "message_bus", "running": True},
            # Would connect to IB
            "B01_SpyderClient": lambda: {"type": "ib_client", "connected": False},
            "E11_MaxLossProtection": lambda: {"type": "risk_manager", "limits_set": True},
            "L18_EnhancedMLIntegration": lambda: {"type": "ml_engine", "models_loaded": True},
            "X16_MetaCoordinator": lambda: {"type": "coordinator", "agents_ready": True},
            "K10_RealTimePerformanceAnalytics": lambda: {"type": "analytics", "tracking": True},
            "G05_TradingDashboard": lambda: {"type": "dashboard", "visible": False},  # GUI
        }

        if module_id in module_initializers:
            return module_initializers[module_id]()

        # Default mock component
        return {"type": "module", "id": module_id, "status": "initialized"}

    # ==================================================================================
    # SYSTEM SHUTDOWN
    # ==================================================================================

    def shutdown_system(self, reason: str = "User requested") -> bool:
        """Gracefully shutdown the system"""

        try:
            logger.info("=" * 80)
            logger.info(f"SYSTEM SHUTDOWN INITIATED - Reason: {reason}")
            logger.info("=" * 80)

            self.shutdown_time = datetime.now()
            self.status = SystemStatus.STOPPING

            # Disable trading first
            self._disable_trading()

            # Execute shutdown sequence (reverse order of startup)
            shutdown_sequence = self._get_shutdown_sequence()

            for phase in shutdown_sequence:
                logger.info(f"Shutting down: {phase['name']}")
                self._shutdown_phase(phase["modules"])

            # Stop health monitor
            self.shutdown_event.set()
            if self.health_monitor_thread:
                self.health_monitor_thread.join(timeout=5)

            # Shutdown executor
            self.executor.shutdown(wait=True, timeout=10)

            # Generate shutdown report
            self._generate_shutdown_report()

            self.status = SystemStatus.STOPPED

            elapsed = (datetime.now() - self.shutdown_time).total_seconds()
            logger.info(f"SYSTEM SHUTDOWN COMPLETE in {elapsed:.2f} seconds")

            return True

        except Exception as e:
            logger.error(f"Shutdown error: {e}")
            self._emergency_shutdown()
            return False

    def _get_shutdown_sequence(self) -> List[Dict[str, Any]]:
        """Get shutdown sequence (reverse of startup)"""

        return [
            {"name": "Trading & Orders", "modules": ["B02_OrderManager", "B03_PositionTracker"]},
            {"name": "Strategies", "modules": ["D02_IronCondor", "D04_ZeroDTE", "D05_Straddle"]},
            {
                "name": "AI Agents",
                "modules": ["X01_GreeksAgent", "X02_FlowAgent", "X16_MetaCoordinator"],
            },
            {"name": "ML Engine", "modules": ["L18_EnhancedMLIntegration", "L01_MLPredictor"]},
            {
                "name": "Analytics",
                "modules": ["K10_RealTimePerformanceAnalytics", "K01_ReportGenerator"],
            },
            {
                "name": "Risk Management",
                "modules": [
                    "E01_RiskManager",
                    "E13_TailRiskManager",
                    "E12_PortfolioVaR",
                    "E11_MaxLossProtection",
                ],
            },
            {
                "name": "Market Data",
                "modules": ["C03_OptionChain", "C07_MarketDataHub", "C01_DataFeed"],
            },
            {"name": "Broker Connection", "modules": ["B01_SpyderClient", "B05_ConnectionManager"]},
            {"name": "Communication", "modules": ["I06_AgentMessageBus", "Z01_ZeroMQIntegration"]},
            {
                "name": "Infrastructure",
                "modules": ["H02_DatabaseManager", "U02_ErrorHandler", "U01_Logger"],
            },
        ]

    def _shutdown_phase(self, module_ids: List[str]):
        """Shutdown a phase of modules"""

        for module_id in module_ids:
            try:
                if module_id in self.modules:
                    self._stop_module(module_id)
            except Exception as e:
                logger.error(f"Error stopping module {module_id}: {e}")

    def _stop_module(self, module_id: str):
        """Stop an individual module"""

        if module_id not in self.modules:
            return

        module = self.modules[module_id]

        try:
            # Stop the actual component
            if module_id in self.components:
                # Call cleanup method if available
                component = self.components[module_id]
                if hasattr(component, "shutdown"):
                    component.shutdown()
                del self.components[module_id]

            module.status = ModuleStatus.STOPPED
            logger.info(f"✓ Module stopped: {module_id}")

        except Exception as e:
            logger.error(f"Error stopping module {module_id}: {e}")

    def _emergency_shutdown(self):
        """Emergency shutdown procedure"""

        logger.critical("EMERGENCY SHUTDOWN ACTIVATED")
        self.status = SystemStatus.EMERGENCY_STOP

        try:
            # Close all positions immediately
            if "B02_OrderManager" in self.components:
                logger.info("Closing all positions...")
                # Would call actual position closing logic

            # Kill all threads
            self.shutdown_event.set()

            # Force stop all modules
            for module_id in self.modules:
                self.modules[module_id].status = ModuleStatus.STOPPED

            self.status = SystemStatus.STOPPED

        except Exception as e:
            logger.critical(f"Emergency shutdown error: {e}")

    # ==================================================================================
    # HEALTH MONITORING
    # ==================================================================================

    def _start_health_monitor(self):
        """Start health monitoring thread"""

        self.health_monitor_thread = threading.Thread(target=self._health_monitor_loop, daemon=True)
        self.health_monitor_thread.start()
        logger.info("Health monitoring started")

    def _health_monitor_loop(self):
        """Health monitoring loop"""

        while not self.shutdown_event.is_set():
            try:
                # Collect health metrics
                metrics = self._collect_health_metrics()
                self.health_metrics.append(metrics)

                # Check module health
                self._check_module_health()

                # Check system resources
                self._check_system_resources(metrics)

                # Check for stuck modules
                self._check_stuck_modules()

                # Restart failed modules if needed
                self._handle_failed_modules()

                # Sleep for monitoring interval
                time.sleep(10)  # Check every 10 seconds

            except Exception as e:
                logger.error(f"Health monitor error: {e}")

    def _collect_health_metrics(self) -> HealthMetrics:
        """Collect system health metrics"""

        # System resources
        cpu_usage = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        # Module health
        module_health = {}
        for module_id, module in self.modules.items():
            module_health[module_id] = module.status.value

        # Trading metrics (placeholder)
        active_positions = len(self.components.get("B03_PositionTracker", {}).get("positions", []))
        daily_pnl = 0  # Would get from position tracker
        risk_utilization = 0  # Would get from risk manager

        # Error rate
        total_errors = sum(m.error_count for m in self.modules.values())
        error_rate = total_errors / max(len(self.modules), 1)

        return HealthMetrics(
            timestamp=datetime.now(),
            cpu_usage=cpu_usage,
            memory_usage=memory.percent,
            disk_usage=disk.percent,
            network_latency=0,  # Would measure actual latency
            module_health=module_health,
            active_positions=active_positions,
            daily_pnl=daily_pnl,
            risk_utilization=risk_utilization,
            error_rate=error_rate,
        )

    def _check_module_health(self):
        """Check health of all modules"""

        for module_id, module in self.modules.items():
            if module.status == ModuleStatus.RUNNING:
                # Run health check if available
                if module.health_check:
                    try:
                        is_healthy = module.health_check()
                        module.status = ModuleStatus.HEALTHY if is_healthy else ModuleStatus.WARNING
                    except Exception as e:
                        logger.warning(f"Health check failed for {module_id}: {e}")
                        module.status = ModuleStatus.WARNING

    def _check_system_resources(self, metrics: HealthMetrics):
        """Check system resource usage"""

        # CPU warning
        if metrics.cpu_usage > 80:
            logger.warning(f"High CPU usage: {metrics.cpu_usage}%")

        # Memory warning
        if metrics.memory_usage > 85:
            logger.warning(f"High memory usage: {metrics.memory_usage}%")

        # Disk warning
        if metrics.disk_usage > 90:
            logger.critical(f"Critical disk usage: {metrics.disk_usage}%")

    def _check_stuck_modules(self):
        """Check for modules that might be stuck"""

        for module_id, module in self.modules.items():
            if module.status == ModuleStatus.STARTING:
                # Check if it's been starting for too long
                if module.metadata.get("start_time"):
                    elapsed = (datetime.now() - module.metadata["start_time"]).total_seconds()
                    if elapsed > 300:  # 5 minutes
                        logger.error(f"Module {module_id} stuck in STARTING state")
                        module.status = ModuleStatus.ERROR

    def _handle_failed_modules(self):
        """Handle failed modules with restart logic"""

        for module_id, module in self.modules.items():
            if module.status == ModuleStatus.ERROR:
                # Check restart policy
                if module.restart_attempts < 3:
                    # Check cooldown period
                    if module.last_restart:
                        cooldown = (datetime.now() - module.last_restart).total_seconds()
                        if cooldown < 60:  # 1 minute cooldown
                            continue

                    logger.info(f"Attempting to restart module {module_id}")
                    module.restart_attempts += 1
                    module.last_restart = datetime.now()
                    module.status = ModuleStatus.RESTARTING

                    # Attempt restart
                    self.executor.submit(self._restart_module, module_id)

    def _restart_module(self, module_id: str):
        """Restart a failed module"""

        try:
            # Stop the module first
            self._stop_module(module_id)
            time.sleep(2)

            # Start it again
            if self._start_module(module_id):
                logger.info(f"Module {module_id} restarted successfully")
                self.modules[module_id].restart_attempts = 0
            else:
                logger.error(f"Failed to restart module {module_id}")

        except Exception as e:
            logger.error(f"Error restarting module {module_id}: {e}")

    # ==================================================================================
    # MARKET STATE MANAGEMENT
    # ==================================================================================

    def _update_market_state(self):
        """Update current market state"""

        now = datetime.now()
        current_time = now.time()
        weekday = now.weekday()

        # Check if weekend
        if weekday >= 5:  # Saturday = 5, Sunday = 6
            self.market_state = MarketState.WEEKEND
            return

        # Define market hours (US Eastern Time)
        pre_market_start = dt_time(4, 0)
        market_open = dt_time(9, 30)
        market_close = dt_time(16, 0)
        after_hours_end = dt_time(20, 0)

        # Determine market state
        if current_time < pre_market_start:
            self.market_state = MarketState.MARKET_CLOSED
        elif current_time < market_open:
            self.market_state = MarketState.PRE_MARKET
        elif current_time < market_close:
            self.market_state = MarketState.MARKET_OPEN
        elif current_time < after_hours_end:
            self.market_state = MarketState.AFTER_HOURS
        else:
            self.market_state = MarketState.MARKET_CLOSED

        logger.info(f"Market state: {self.market_state.value}")

    def handle_market_open(self):
        """Handle market open transition"""

        logger.info("Market opening - transitioning to trading mode")

        try:
            # Update market state
            self.market_state = MarketState.MARKET_OPEN

            # Perform pre-market checks
            self._perform_premarket_checks()

            # Enable trading
            self._enable_trading()

            # Start real-time data feeds
            if "C01_DataFeed" in self.components:
                logger.info("Starting real-time data feeds")
                # Would start actual data feeds

            # Notify all modules
            self._broadcast_event("MARKET_OPEN", {})

            logger.info("Market open transition complete")

        except Exception as e:
            logger.error(f"Market open transition failed: {e}")

    def handle_market_close(self):
        """Handle market close transition"""

        logger.info("Market closing - transitioning to after-hours mode")

        try:
            # Update market state
            self.market_state = MarketState.MARKET_CLOSED

            # Disable new trades
            self._disable_trading()

            # Close expiring positions
            self._close_expiring_positions()

            # Generate end-of-day reports
            self._generate_eod_reports()

            # Backup data
            self._backup_system_data()

            # Notify all modules
            self._broadcast_event("MARKET_CLOSE", {})

            logger.info("Market close transition complete")

        except Exception as e:
            logger.error(f"Market close transition failed: {e}")

    def _perform_premarket_checks(self):
        """Perform pre-market system checks"""

        checks = [
            ("Database Connection", self._check_database),
            ("IB Gateway Connection", self._check_ib_connection),
            ("Risk Limits", self._check_risk_limits),
            ("ML Models", self._check_ml_models),
            ("Account Balance", self._check_account_balance),
        ]

        for check_name, check_func in checks:
            try:
                if check_func():
                    logger.info(f"✓ Pre-market check passed: {check_name}")
                else:
                    logger.warning(f"✗ Pre-market check failed: {check_name}")
            except Exception as e:
                logger.error(f"Pre-market check error ({check_name}): {e}")

    def _check_database(self) -> bool:
        """Check database connection"""
        return "H02_DatabaseManager" in self.components

    def _check_ib_connection(self) -> bool:
        """Check IB Gateway connection"""
        return "B01_SpyderClient" in self.components

    def _check_risk_limits(self) -> bool:
        """Check risk limits are set"""
        return "E01_RiskManager" in self.components

    def _check_ml_models(self) -> bool:
        """Check ML models are loaded"""
        return "L18_EnhancedMLIntegration" in self.components

    def _check_account_balance(self) -> bool:
        """Check account balance"""
        # Would check actual account balance
        return True

    # ==================================================================================
    # TRADING CONTROL
    # ==================================================================================

    def _enable_trading(self):
        """Enable trading"""

        if self.trading_enabled:
            logger.info("Trading already enabled")
            return

        logger.info("Enabling trading")

        # Enable order manager
        if "B02_OrderManager" in self.components:
            # Would enable actual order manager
            pass

        # Enable strategies
        for module_id in self.modules:
            if module_id.startswith("D"):  # Strategy modules
                # Would enable strategy
                pass

        self.trading_enabled = True
        self.status = SystemStatus.TRADING
        logger.info("Trading enabled")

    def _disable_trading(self):
        """Disable trading"""

        if not self.trading_enabled:
            return

        logger.info("Disabling trading")

        # Disable new orders
        if "B02_OrderManager" in self.components:
            # Would disable order manager
            pass

        # Disable strategies
        for module_id in self.modules:
            if module_id.startswith("D"):
                # Would disable strategy
                pass

        self.trading_enabled = False
        self.status = SystemStatus.RUNNING
        logger.info("Trading disabled")

    def _close_expiring_positions(self):
        """Close positions expiring today"""

        logger.info("Checking for expiring positions")

        if "B03_PositionTracker" in self.components:
            # Would check and close expiring positions
            pass

    # ==================================================================================
    # REPORTING
    # ==================================================================================

    def _generate_startup_report(self):
        """Generate system startup report"""

        report = {
            "timestamp": self.startup_time.isoformat(),
            "environment": self.config.environment,
            "trading_mode": self.config.trading_mode.value,
            "modules_started": sum(
                1
                for m in self.modules.values()
                if m.status in [ModuleStatus.RUNNING, ModuleStatus.HEALTHY]
            ),
            "modules_failed": sum(
                1 for m in self.modules.values() if m.status == ModuleStatus.ERROR
            ),
            "startup_duration": (datetime.now() - self.startup_time).total_seconds(),
        }

        logger.info("Startup Report:")
        for key, value in report.items():
            logger.info(f"  {key}: {value}")

    def _generate_shutdown_report(self):
        """Generate system shutdown report"""

        if not self.shutdown_time:
            return

        report = {
            "timestamp": self.shutdown_time.isoformat(),
            "uptime": (
                (self.shutdown_time - self.startup_time).total_seconds() if self.startup_time else 0
            ),
            "modules_stopped": sum(
                1 for m in self.modules.values() if m.status == ModuleStatus.STOPPED
            ),
            "shutdown_duration": (datetime.now() - self.shutdown_time).total_seconds(),
        }

        logger.info("Shutdown Report:")
        for key, value in report.items():
            logger.info(f"  {key}: {value}")

    def _generate_eod_reports(self):
        """Generate end-of-day reports"""

        logger.info("Generating end-of-day reports")

        if "K01_ReportGenerator" in self.components:
            # Would generate actual reports
            pass

    def _backup_system_data(self):
        """Backup system data"""

        logger.info("Backing up system data")

        # Backup database
        if "H02_DatabaseManager" in self.components:
            # Would backup database
            pass

        # Save ML models
        if "L18_EnhancedMLIntegration" in self.components:
            # Would save ML models
            pass

    # ==================================================================================
    # EVENT HANDLING
    # ==================================================================================

    def _broadcast_event(self, event_type: str, data: Dict[str, Any]):
        """Broadcast event to all modules"""

        if "I06_AgentMessageBus" in self.components:
            # Would broadcast via message bus
            logger.debug(f"Broadcasting event: {event_type}")

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""

        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}")
            self.shutdown_system("Signal received")
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    # ==================================================================================
    # PUBLIC API
    # ==================================================================================

    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status"""

        return {
            "status": self.status.value,
            "market_state": self.market_state.value,
            "trading_enabled": self.trading_enabled,
            "uptime": (
                (datetime.now() - self.startup_time).total_seconds() if self.startup_time else 0
            ),
            "modules": {
                "total": len(self.modules),
                "running": sum(
                    1
                    for m in self.modules.values()
                    if m.status in [ModuleStatus.RUNNING, ModuleStatus.HEALTHY]
                ),
                "warning": sum(
                    1 for m in self.modules.values() if m.status == ModuleStatus.WARNING
                ),
                "error": sum(1 for m in self.modules.values() if m.status == ModuleStatus.ERROR),
            },
        }

    def get_module_status(self, module_id: str) -> Optional[Dict[str, Any]]:
        """Get status of specific module"""

        if module_id not in self.modules:
            return None

        module = self.modules[module_id]
        return {
            "id": module.module_id,
            "name": module.name,
            "status": module.status.value,
            "error_count": module.error_count,
            "restart_attempts": module.restart_attempts,
            "last_error": module.last_error,
        }

    def restart_module(self, module_id: str) -> bool:
        """Manually restart a module"""

        if module_id not in self.modules:
            logger.error(f"Module {module_id} not found")
            return False

        logger.info(f"Manual restart requested for {module_id}")
        self._restart_module(module_id)
        return True

    def pause_trading(self):
        """Pause trading temporarily"""

        logger.info("Pausing trading")
        self._disable_trading()
        self.status = SystemStatus.PAUSED

    def resume_trading(self):
        """Resume trading"""

        if self.market_state != MarketState.MARKET_OPEN:
            logger.warning("Cannot resume trading - market is closed")
            return

        logger.info("Resuming trading")
        self._enable_trading()

    def emergency_stop(self):
        """Emergency stop - close all positions and shutdown"""

        logger.critical("EMERGENCY STOP INITIATED")
        self._emergency_shutdown()


# ==================================================================================
# FACTORY FUNCTION
# ==================================================================================


def create_master_controller(config_path: Optional[str] = None) -> MasterController:
    """Factory function to create master controller"""

    if config_path:
        return MasterController(config_path)
    else:
        return MasterController()


# ==================================================================================
# MAIN EXECUTION
# ==================================================================================


if __name__ == "__main__":
    """
    Main entry point for Spyder Autonomous Trading System
    """

    print(
        """
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║         🕷️  SPYDER AUTONOMOUS TRADING SYSTEM 🕷️              ║
    ║                                                              ║
    ║                     Version 1.0                              ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    )

    # Create master controller
    master = create_master_controller()

    # Start system
    if master.start_system():
        print("\n✅ System started successfully!")
        print("\nSystem Status:")
        status = master.get_system_status()
        for key, value in status.items():
            print(f"  {key}: {value}")

        print("\n📊 Commands:")
        print("  - Press Ctrl+C to shutdown")
        print("  - Check logs at: ./logs/spyder_master.log")
        print("  - Dashboard at: http://localhost:8080 (if GUI enabled)")

        try:
            # Keep the system running
            while True:
                time.sleep(1)

                # Check market transitions
                current_hour = datetime.now().hour
                current_minute = datetime.now().minute

                # Market open at 9:30 AM
                if current_hour == 9 and current_minute == 30:
                    if master.market_state != MarketState.MARKET_OPEN:
                        master.handle_market_open()

                # Market close at 4:00 PM
                elif current_hour == 16 and current_minute == 0:
                    if master.market_state == MarketState.MARKET_OPEN:
                        master.handle_market_close()

        except KeyboardInterrupt:
            print("\n\nShutdown requested...")
            master.shutdown_system("User interrupted")

    else:
        print("\n❌ System failed to start. Check logs for details.")
        sys.exit(1)
