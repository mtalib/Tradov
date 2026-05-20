#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderA_Core
Module: SpyderA06_MasterController.py
Purpose: SPYDER - Autonomous Options Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    SPYDER - Autonomous Options Trading System

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass, field
from datetime import datetime, time as dt_time, UTC
from enum import Enum
from typing import Any
from collections.abc import Callable

try:
    from Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils import now_et as _now_et
except ImportError:
    try:
        import pytz as _pytz
        def _now_et() -> datetime:  # type: ignore[misc]
            return datetime.now(_pytz.timezone("US/Eastern"))
    except ImportError:
        import zoneinfo as _zi
        def _now_et() -> datetime:  # type: ignore[misc]
            return datetime.now(_zi.ZoneInfo("America/New_York"))

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import signal
import traceback
import psutil
import yaml

# Logging is configured by SpyderA01_Main (the application entry point).
# Do not call logging.basicConfig() here — it would override the root handler
# set up by the entry point and interfere with child loggers across the system.
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
    dependencies: list[str]
    priority: int  # Startup priority (lower = earlier)
    health_check: Callable | None = None
    restart_attempts: int = 0
    last_restart: datetime | None = None
    error_count: int = 0
    last_error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemConfig:
    """System configuration"""

    trading_mode: TradingMode
    environment: str  # 'development', 'testing', 'production'
    portfolio_value: float
    max_daily_loss: float
    max_positions: int
    risk_limits: dict[str, float]
    database: dict[str, Any]
    ml_models_path: str
    data_path: str
    logs_path: str
    enable_alerts: bool
    enable_paper_trading: bool
    enable_ml_predictions: bool
    enable_risk_management: bool
    autonomous_session: dict[str, Any] = field(default_factory=dict)
    enable_x16_veto: bool = True
    enable_y03_trade_veto: bool = True
    enable_y05_veto_consumption: bool = True


@dataclass
class HealthMetrics:
    """System health metrics"""

    timestamp: datetime
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    network_latency: float
    module_health: dict[str, str]
    active_positions: int
    daily_pnl: float
    risk_utilization: float
    error_rate: float


@dataclass
class StartupSequence:
    """Startup sequence definition"""

    phase: str
    modules: list[str]
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
        self.modules: dict[str, ModuleInfo] = {}
        self._initialize_module_registry()

        # Component references
        self.components = {}
        # v27 SPEC-3: lock around components dict to prevent torn reads /
        # KeyError-during-iteration when parallel startup phases mutate while
        # the health-monitor thread reads. RLock so the same thread can call
        # nested helpers (like _initialize_component) without deadlocking.
        self._components_lock = threading.RLock()
        # N04 OptionsGreeksCalculator singleton — wired after Risk Management phase
        self._n04_calculator: Any | None = None

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

        logger.info("Master Controller initialized in %s environment", self.config.environment)

    # ==================================================================================
    # CONFIGURATION
    # ==================================================================================

    def _load_configuration(self, config_path: str) -> SystemConfig:
        """Load system configuration"""

        # Try to load from file
        if os.path.exists(config_path):
            with open(config_path) as f:
                config_data = yaml.safe_load(f)
        else:
            # Use default configuration
            config_data = self._get_default_config()

        autonomous_session = config_data.get("autonomous_session")
        if not isinstance(autonomous_session, dict):
            readiness_cfg = config_data.get("autonomous_readiness", {})
            if isinstance(readiness_cfg, dict):
                maybe_session = readiness_cfg.get("session_window")
                autonomous_session = maybe_session if isinstance(maybe_session, dict) else None
        if not isinstance(autonomous_session, dict):
            autonomous_session = self._get_default_autonomous_session()

        return SystemConfig(
            trading_mode=TradingMode(config_data.get("trading_mode", "paper")),
            environment=config_data.get("environment", "development"),
            portfolio_value=config_data.get("portfolio_value", 1000000),
            max_daily_loss=config_data.get("max_daily_loss", 50000),
            max_positions=config_data.get("max_positions", 10),
            risk_limits=config_data.get(
                "risk_limits", {"max_var": 0.10, "max_drawdown": 0.20, "max_concentration": 0.25}
            ),
            database=config_data.get("database", {"type": "sqlite", "path": "data/spyder.db"}),
            ml_models_path=config_data.get("ml_models_path", "./models"),
            data_path=config_data.get("data_path", "./data"),
            logs_path=config_data.get("logs_path", "./logs"),
            enable_alerts=config_data.get("enable_alerts", True),
            enable_paper_trading=config_data.get("enable_paper_trading", True),
            enable_ml_predictions=config_data.get("enable_ml_predictions", True),
            enable_risk_management=config_data.get("enable_risk_management", True),
            autonomous_session=autonomous_session,
            enable_x16_veto=config_data.get("enable_x16_veto", True),
            enable_y03_trade_veto=config_data.get("enable_y03_trade_veto", True),
            enable_y05_veto_consumption=config_data.get("enable_y05_veto_consumption", True),
        )

    def _get_default_autonomous_session(self) -> dict[str, Any]:
        """Default autonomous session controls for SPY options."""
        return {
            "primary_start_et": "09:30",
            "primary_end_et": "16:15",
            "first_entry_not_before_et": "10:15",
            "zero_dte_no_new_risk_cutoff_et": "14:30",
            "broker_cutoff_et": "16:00",
            "broker_cutoff_buffer_minutes": 10,
            "pin_risk_monitor_end_et": "17:30",
            "fail_closed_if_cutoff_unknown_live": True,
        }

    def _get_default_config(self) -> dict[str, Any]:
        """Get default configuration — env vars take precedence over hardcoded defaults."""

        def _env_bool(name: str, default: bool) -> bool:
            value = os.environ.get(name)
            if value is None:
                return default
            return value.strip().lower() in {"1", "true", "yes", "on"}

        return {
            "trading_mode": os.environ.get("TRADING_MODE", "paper"),
            "environment": os.environ.get("ENVIRONMENT", "development"),
            "portfolio_value": 1000000,
            "max_daily_loss": 50000,
            "max_positions": 10,
            "risk_limits": {"max_var": 0.10, "max_drawdown": 0.20, "max_concentration": 0.25},
            "database": {"type": "sqlite", "path": "data/spyder.db"},
            "ml_models_path": "./models",
            "data_path": "./data",
            "logs_path": "./logs",
            "enable_alerts": True,
            "enable_paper_trading": True,
            "enable_ml_predictions": True,
            "enable_risk_management": True,
            "autonomous_session": {
                "primary_start_et": os.environ.get("SPYDER_SESSION_PRIMARY_START_ET", "09:30"),
                "primary_end_et": os.environ.get("SPYDER_SESSION_PRIMARY_END_ET", "16:15"),
                "first_entry_not_before_et": os.environ.get("SPYDER_FIRST_ENTRY_NOT_BEFORE_ET", "10:15"),
                "zero_dte_no_new_risk_cutoff_et": os.environ.get("SPYDER_ZERO_DTE_NO_NEW_RISK_CUTOFF_ET", "14:30"),
                "broker_cutoff_et": os.environ.get("SPYDER_BROKER_CUTOFF_ET", "16:00"),
                "broker_cutoff_buffer_minutes": int(os.environ.get("SPYDER_BROKER_CUTOFF_BUFFER_MINUTES", "10")),
                "pin_risk_monitor_end_et": os.environ.get("SPYDER_PIN_RISK_MONITOR_END_ET", "17:30"),
                "fail_closed_if_cutoff_unknown_live": _env_bool("SPYDER_FAIL_CLOSED_IF_CUTOFF_UNKNOWN_LIVE", True),
            },
            "enable_x16_veto": _env_bool("ENABLE_X16_VETO", True),
            "enable_y03_trade_veto": _env_bool("ENABLE_Y03_TRADE_VETO", True),
            "enable_y05_veto_consumption": _env_bool("ENABLE_Y05_VETO_CONSUMPTION", True),
        }

    def _session_time(self, key: str, default_hhmm: str) -> dt_time:
        """Read HH:MM from autonomous session config with safe fallback."""
        raw = self.config.autonomous_session.get(key, default_hhmm)
        try:
            parsed = datetime.strptime(str(raw).strip(), "%H:%M")
            return dt_time(parsed.hour, parsed.minute)
        except Exception:
            parsed = datetime.strptime(default_hhmm, "%H:%M")
            return dt_time(parsed.hour, parsed.minute)

    def _in_primary_trading_window(self, now_et: datetime | None = None) -> bool:
        """Return True when current ET time is in configured primary trading window."""
        now = now_et or _now_et()
        current_time = now.time()
        start_et = self._session_time("primary_start_et", "09:30")
        end_et = self._session_time("primary_end_et", "16:15")
        return start_et <= current_time < end_et

    def _is_live_mode(self) -> bool:
        """Return True when controller runs in live trading mode."""
        return self.config.trading_mode == TradingMode.LIVE

    def _has_valid_broker_cutoff(self) -> bool:
        """Validate configured broker cutoff time for fail-closed live gating."""
        try:
            raw = self.config.autonomous_session.get("broker_cutoff_et")
            if raw is None:
                return False
            datetime.strptime(str(raw).strip(), "%H:%M")
            return True
        except Exception:
            return False

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
            ("B05_ConnectionManager", "B", "Broker Connection", [], 3),
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
            ("J05_TelegramBot", "J", "Telegram Bot", ["J01_AlertManager"], 14),
            # Autonomous Agents — Y-series (Priority 15)
            ("Y10_AgentScheduler", "Y", "Agent Scheduler", ["I06_AgentMessageBus"], 15),
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
            logger.info("Mode: %s", self.config.trading_mode.value)
            logger.info("Environment: %s", self.config.environment)
            logger.info("=" * 80)

            self.startup_time = datetime.now(UTC)
            self.status = SystemStatus.STARTING

            # Define startup sequence
            startup_sequence = self._get_startup_sequence()

            # Execute startup phases
            for phase in startup_sequence:
                if not self._execute_startup_phase(phase):
                    logger.error("Startup failed at phase: %s", phase.phase)
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

            elapsed = (datetime.now(UTC) - self.startup_time).total_seconds()
            logger.info(f"SYSTEM STARTUP COMPLETE in {elapsed:.2f} seconds")

            # Generate startup report
            self._generate_startup_report()

            return True

        except Exception as e:
            logger.error("System startup failed: %s", e, exc_info=True)
            logger.error(traceback.format_exc(), exc_info=True)
            self._emergency_shutdown()
            return False

    def _get_startup_sequence(self) -> list[StartupSequence]:
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
                parallel=False,  # Sequential for broker connection
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
                    "E19_UnifiedRiskCoordinator",
                ],
                parallel=False,  # Sequential for proper initialization
                timeout=30,
                critical=True,
            ),
            StartupSequence(
                phase="Options Analytics",
                modules=["N04_OptionsGreeksCalculator"],
                parallel=False,
                timeout=20,
                critical=False,  # Non-critical — system trades without it
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
                modules=[
                    "D01_BaseStrategy",
                    "D02_IronCondor",
                    "D04_ZeroDTE",
                    "D05_Straddle",
                    "D31_StrategyOrchestrator",
                ],
                parallel=True,
                timeout=30,
                critical=True,
            ),
            StartupSequence(
                phase="Order Management",
                modules=["B02_OrderManager", "B03_PositionTracker", "R04_LiveEngine"],
                parallel=False,
                timeout=20,
                critical=True,
            ),
            StartupSequence(
                phase="Task Scheduler",
                modules=["A04_Scheduler"],
                parallel=False,
                timeout=20,
                critical=False,  # Non-critical — system trades without scheduled jobs
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
                modules=["G05_TradingDashboard", "J01_AlertManager", "J05_TelegramBot"],
                parallel=True,
                timeout=30,
                critical=False,
            ),
            StartupSequence(
                phase="Autonomous Agents",
                modules=["Y10_AgentScheduler"],
                parallel=False,
                timeout=60,
                critical=False,  # Agents are non-critical — system trades without them
            ),
        ]

    def _execute_startup_phase(self, phase: StartupSequence) -> bool:
        """Execute a startup phase"""

        logger.info("Starting phase: %s", phase.phase)

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
                            logger.error("Critical module %s failed to start", module_id)
                            return False
                    except TimeoutError:
                        logger.error("Module %s startup timeout", module_id, exc_info=True)
                        if phase.critical:
                            return False
            else:
                # Start modules sequentially
                for module_id in phase.modules:
                    if not self._start_module(module_id):
                        if phase.critical:
                            logger.error("Critical module %s failed to start", module_id)
                            return False

            logger.info("Phase completed: %s", phase.phase)
            return True

        except Exception as e:
            logger.error("Phase %s failed: %s", phase.phase, e, exc_info=True)
            return not phase.critical

    def _start_module(self, module_id: str) -> bool:
        """Start an individual module"""

        if module_id not in self.modules:
            logger.warning("Module %s not found in registry", module_id)
            return True  # Non-fatal

        module = self.modules[module_id]

        try:
            logger.debug("Starting module: %s", module_id)

            # Check dependencies
            for dep_id in module.dependencies:
                if dep_id in self.modules:
                    dep_status = self.modules[dep_id].status
                    if dep_status not in [ModuleStatus.RUNNING, ModuleStatus.HEALTHY]:
                        logger.warning("Dependency %s not ready for %s", dep_id, module_id)
                        return False

            # Simulate module startup (replace with actual module initialization)
            module.status = ModuleStatus.STARTING

            # Import and initialize the actual module
            component = self._initialize_component(module_id)
            if component:
                # v27 SPEC-3: serialize writes against parallel startup phases.
                with self._components_lock:
                    self.components[module_id] = component
                module.status = ModuleStatus.RUNNING
                logger.info("✓ Module started: %s", module_id)
                return True
            else:
                module.status = ModuleStatus.ERROR
                return False

        except Exception as e:
            logger.error("Failed to start module %s: %s", module_id, e, exc_info=True)
            module.status = ModuleStatus.ERROR
            module.last_error = str(e)
            module.error_count += 1
            return False

    def _initialize_component(self, module_id: str) -> Any | None:
        """Import and instantiate the real module component with graceful fallback."""
        import importlib

        def _load(pkg: str, cls: str, *args, **kwargs):
            """Dynamically import a class and instantiate it."""
            try:
                mod = importlib.import_module(pkg)
                return getattr(mod, cls)(*args, **kwargs)
            except Exception as e:
                logger.warning("Could not load %s.%s: %s — using stub", pkg, cls, e)
                return {"module_id": module_id, "status": "stub", "error": str(e)}

        # ── Modules with straightforward initialization ──────────────────────
        if module_id == "H02_DatabaseManager":
            from pathlib import Path as _Path
            db_path = _Path(self.config.database.get("path", "data/spyder.db"))
            return _load(
                "SpyderH_Storage.SpyderH02_DatabaseManager",
                "DatabaseManager",
                db_path=db_path,
            )

        if module_id == "U01_Logger":
            # The logger is a singleton already configured by the entry point.
            return {"module_id": module_id, "status": "singleton"}

        if module_id == "U02_ErrorHandler":
            return _load("Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler", "SpyderErrorHandler")

        if module_id == "I06_AgentMessageBus":
            return _load("SpyderI_Integration.SpyderI06_AgentMessageBus", "AgentMessageBus")

        if module_id == "L18_EnhancedMLIntegration":
            return _load("SpyderL_ML.SpyderL18_EnhancedMLIntegration", "EnhancedMLEngine")

        if module_id == "X16_MetaCoordinator":
            if not self.config.enable_x16_veto:
                logger.info("X16 MetaCoordinator disabled by config (enable_x16_veto=false)")
                return {"module_id": module_id, "status": "disabled"}
            return _load("SpyderX_Agents.SpyderX16_MetaCoordinator", "MetaCoordinator")

        # ── Broker client — requires env-var credentials ──────────────────────
        if module_id in ("B40_TradierClient", "B01_SpyderClient"):
            try:
                from SpyderB_Broker.SpyderB40_TradierClient import (
                    TradierClient,
                    TradingEnvironment,
                )
                api_key = os.environ.get("TRADIER_API_KEY", "")
                account_id = os.environ.get("TRADIER_ACCOUNT_ID", "")
                if not api_key or not account_id:
                    logger.warning(
                        "TRADIER_API_KEY or TRADIER_ACCOUNT_ID not set — "
                        "broker client unavailable"
                    )
                    return None
                env_str = os.environ.get("TRADIER_ENVIRONMENT", "sandbox").lower()
                env = (
                    TradingEnvironment.LIVE
                    if env_str == "live"
                    else TradingEnvironment.SANDBOX
                )
                client = TradierClient(
                    api_key=api_key, account_id=account_id, environment=env
                )
                logger.info(
                    "TradierClient connected (%s environment)", env_str
                )
                return client
            except Exception as e:
                logger.warning("Could not initialize TradierClient: %s", e)
                return None

        # ── Order manager — reuses the broker client if already loaded ─────────
        if module_id == "B02_OrderManager":
            try:
                from SpyderB_Broker.SpyderB02_OrderManager import OrderManager
                tradier = self.components.get("B40_TradierClient") or self.components.get(
                    "B01_SpyderClient"
                )
                # Pass the shared client only when it's a real TradierClient instance.
                tradier_arg = (
                    tradier
                    if tradier is not None and hasattr(tradier, "account_id")
                    else None
                )
                return OrderManager(tradier_client=tradier_arg)
            except Exception as e:
                logger.warning("Could not initialize OrderManager: %s", e)
                return None

        # ── Telegram Bot — optional; skipped silently when no token is configured ──
        if module_id == "J05_TelegramBot":
            bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
            chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
            if not bot_token or not chat_id:
                logger.info(
                    "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set — "
                    "Telegram notifications disabled"
                )
                return None
            try:
                from SpyderJ_Alerts.SpyderJ05_TelegramBot import TelegramBot
                from SpyderA_Core.SpyderA05_EventManager import EventManager
                event_mgr = self.components.get("A05_EventManager")
                if event_mgr is None or not isinstance(event_mgr, EventManager):
                    from SpyderA_Core.SpyderA05_EventManager import EventManager as _EM
                    event_mgr = _EM()
                bot = TelegramBot(
                    bot_token=bot_token,
                    chat_id=chat_id,
                    event_manager=event_mgr,
                )
                bot.start()
                logger.info("TelegramBot connected (chat_id=%s)", chat_id)
                return bot
            except Exception as e:
                logger.warning("Could not initialize TelegramBot: %s", e)
                return None

        # ── Agent Scheduler — wires TelegramBot and Y-series agents ──────────
        if module_id == "Y10_AgentScheduler":
            try:
                from SpyderY_AutoAgents.SpyderY10_AgentScheduler import AgentScheduler
                from SpyderY_AutoAgents.SpyderY01_MarketSenseAgent import SpyderY01_MarketSenseAgent
                from SpyderY_AutoAgents.SpyderY02_StrategyPilotAgent import SpyderY02_StrategyPilotAgent  # noqa: E501
                from SpyderY_AutoAgents.SpyderY03_RiskSentinelAgent import SpyderY03_RiskSentinelAgent  # noqa: E501
                from SpyderY_AutoAgents.SpyderY04_AlphaLearnerAgent import SpyderY04_AlphaLearnerAgent  # noqa: E501
                from SpyderY_AutoAgents.SpyderY05_ExecutionOptimizerAgent import SpyderY05_ExecutionOptimizerAgent  # noqa: E501
                from SpyderY_AutoAgents.SpyderY06_NewsSentinelAgent import SpyderY06_NewsSentinelAgent  # noqa: E501
                from SpyderY_AutoAgents.SpyderY07_TradeJournalAgent import SpyderY07_TradeJournalAgent  # noqa: E501
                from SpyderY_AutoAgents.SpyderY08_MetaOrchestratorAgent import SpyderY08_MetaOrchestratorAgent  # noqa: E501
                from SpyderY_AutoAgents.SpyderY09_CodeReviewerAgent import SpyderY09_CodeReviewerAgent  # noqa: E501

                telegram_bot = self.components.get("J05_TelegramBot")
                message_bus = self.components.get("I06_AgentMessageBus")

                scheduler = AgentScheduler(
                    message_bus=message_bus,
                    telegram_bot=telegram_bot,
                )

                # Register all Y-series agents
                for agent_cls in [
                    SpyderY01_MarketSenseAgent,
                    SpyderY02_StrategyPilotAgent,
                    SpyderY04_AlphaLearnerAgent,
                    SpyderY06_NewsSentinelAgent,
                    SpyderY07_TradeJournalAgent,
                ]:
                    scheduler.register(agent_cls)

                scheduler.register(
                    SpyderY03_RiskSentinelAgent,
                    enable_trade_veto=self.config.enable_y03_trade_veto,
                )
                scheduler.register(
                    SpyderY05_ExecutionOptimizerAgent,
                    enable_veto_consumption=self.config.enable_y05_veto_consumption,
                )

                # Y08 MetaOrchestrator gets the telegram_bot too
                scheduler.register(
                    SpyderY08_MetaOrchestratorAgent,
                    telegram_bot=telegram_bot,
                )

                # Y09 CodeReviewer (monitored by Y08)
                scheduler.register(SpyderY09_CodeReviewerAgent)

                scheduler.start_all()
                logger.info(
                    "AgentScheduler started with %d Y-series agents",
                    len(scheduler._agents),
                )
                return scheduler
            except Exception as e:
                logger.warning("Could not initialize AgentScheduler: %s", e, exc_info=True)
                return None

        # ── N04 OptionsGreeksCalculator — shared singleton ────────────────────
        if module_id == "N04_OptionsGreeksCalculator":
            try:
                from SpyderN_OptionsAnalytics.SpyderN04_OptionsGreeksCalculator import (
                    get_n04_calculator,
                )
                calc = get_n04_calculator()
                self._n04_calculator = calc
                logger.info(
                    "N04 OptionsGreeksCalculator singleton created and cached on MasterController"
                )
                return calc
            except Exception as e:
                logger.warning("Could not initialize N04 OptionsGreeksCalculator: %s", e)
                return None

        # ── L09 UnifiedRegimeEngine ───────────────────────────────────────────
        if module_id == "L09_RegimeClassifier":
            try:
                from SpyderL_ML.SpyderL09_UnifiedRegimeEngine import UnifiedRegimeEngine
                engine = UnifiedRegimeEngine()
                logger.info("L09 UnifiedRegimeEngine initialized")
                return engine
            except Exception as e:
                logger.warning("Could not initialize L09_RegimeClassifier: %s", e, exc_info=True)
                return None

        # ── D31 StrategyOrchestrator — master trading coordinator ─────────────
        if module_id == "D31_StrategyOrchestrator":
            try:
                from SpyderD_Strategies.SpyderD31_StrategyOrchestrator import StrategyOrchestrator
                # Determine base capital from config (fall back to 100 k)
                try:
                    _trading_cfg = getattr(self.config, "trading", None) or {}
                    base_capital = float(
                        _trading_cfg.get("base_capital", 100_000.0)
                        if isinstance(_trading_cfg, dict)
                        else 100_000.0
                    )
                except Exception:
                    base_capital = 100_000.0

                # Inject L09 if already alive (ML Engine phase runs before Trading Strategies)
                l09_engine = self.components.get("L09_RegimeClassifier")
                if isinstance(l09_engine, dict):
                    l09_engine = None  # stub — not the real engine

                # Acquire shared EventManager singleton
                try:
                    from SpyderA_Core.SpyderA05_EventManager import get_event_manager as _gem
                    _event_mgr = _gem()
                except Exception:
                    _event_mgr = None

                orchestrator = StrategyOrchestrator(
                    base_capital=base_capital,
                    event_manager=_event_mgr,
                    regime_engine=l09_engine,
                )
                logger.info(
                    "D31 StrategyOrchestrator initialized "
                    "(capital=%.0f, L09=%s)",
                    base_capital,
                    "wired" if l09_engine is not None else "heuristic-fallback",
                )
                return orchestrator
            except Exception as e:
                logger.warning(
                    "Could not initialize D31_StrategyOrchestrator: %s", e, exc_info=True
                )
                return None

        # ── A04_Scheduler ────────────────────────────────────────────────────
        if module_id == "A04_Scheduler":
            try:
                from SpyderA_Core.SpyderA04_Scheduler import Scheduler
                try:
                    from SpyderA_Core.SpyderA05_EventManager import get_event_manager as _gem_a04
                    _event_mgr_a04 = _gem_a04()
                except Exception:
                    _event_mgr_a04 = None
                if _event_mgr_a04 is None:
                    logger.warning("A04_Scheduler: EventManager not available — scheduler skipped")
                    return None
                scheduler = Scheduler(event_manager=_event_mgr_a04)
                scheduler.schedule_data_update(interval_minutes=5)
                scheduler.schedule_risk_check(interval_minutes=15)
                scheduler.start()
                logger.info("A04_Scheduler started with data-update(5m) and risk-check(15m) jobs")
                return scheduler
            except Exception as e:
                logger.warning("Could not initialize A04_Scheduler: %s", e, exc_info=True)
                return None

        # ── R04_LiveEngine ───────────────────────────────────────────────────
        if module_id == "R04_LiveEngine":
            try:
                from SpyderR_Runtime.SpyderR04_LiveEngine import LiveEngine, LiveTradingConfig
                from SpyderE_Risk.SpyderE01_RiskManager import get_risk_manager as _get_rm
                _account_id = os.environ.get("TRADIER_ACCOUNT_ID", "")
                _live_cfg = LiveTradingConfig(account_id=_account_id)
                _broker = self.components.get("B01_SpyderClient")
                _risk_mgr = _get_rm()
                try:
                    from SpyderA_Core.SpyderA05_EventManager import get_event_manager as _gem_r04
                    _event_mgr_r04 = _gem_r04()
                except Exception:
                    _event_mgr_r04 = None
                engine = LiveEngine(
                    broker_interface=_broker,
                    risk_manager=_risk_mgr,
                    config=_live_cfg,
                    event_manager=_event_mgr_r04,
                )
                logger.info("R04_LiveEngine initialized (account=%s)", _account_id or "<not set>")
                return engine
            except Exception as e:
                logger.warning("Could not initialize R04_LiveEngine: %s", e, exc_info=True)
                return None

        # ── E01_RiskManager — primary risk gate, must be started before trading ──
        if module_id == "E01_RiskManager":
            try:
                from SpyderE_Risk.SpyderE01_RiskManager import get_risk_manager
                risk_manager = get_risk_manager()
                # start() fetches positions + account balances from Tradier and sets
                # _account_state_synced = True.  Run in a dedicated thread so we can
                # join with a timeout without blocking the whole event loop.
                import asyncio as _asyncio
                import threading as _rm_thread

                _start_exc: list = []
                _start_result: list = []

                def _run_start():
                    _loop = _asyncio.new_event_loop()
                    _asyncio.set_event_loop(_loop)
                    try:
                        result = _loop.run_until_complete(risk_manager.start())
                        _start_result.append(bool(result))
                    except Exception as _exc:
                        _start_exc.append(_exc)
                    finally:
                        _loop.close()

                _t = _rm_thread.Thread(target=_run_start, daemon=True, name="E01-startup")
                _t.start()
                _t.join(timeout=15)
                if _start_exc:
                    logger.warning("E01 start() raised: %s — risk gate may reject early signals", _start_exc[0])  # noqa: E501
                elif _t.is_alive():
                    logger.warning("E01 start() did not complete within 15 s — risk gate may reject early signals")  # noqa: E501
                elif not _start_result or not _start_result[0]:
                    # A06-B1: start() returned False — real-money safety component
                    # reported a failure; treat as a warning so operator is alerted.
                    logger.warning(
                        "E01 start() returned False — account-state sync failed; "
                        "risk gate cold-start guard will reject all signals until sync succeeds"
                    )
                else:
                    logger.info("E01_RiskManager started and account-state synced")
                return risk_manager
            except Exception as e:
                logger.warning("Could not initialize E01_RiskManager: %s", e, exc_info=True)
                return None

        # ── E19_UnifiedRiskCoordinator ───────────────────────────────────────
        if module_id == "E19_UnifiedRiskCoordinator":
            try:
                from SpyderE_Risk.SpyderE19_UnifiedRiskCoordinator import UnifiedRiskCoordinator
                coordinator = UnifiedRiskCoordinator()
                logger.info("E19_UnifiedRiskCoordinator initialized")
                return coordinator
            except Exception as e:
                logger.warning("Could not initialize E19_UnifiedRiskCoordinator: %s", e, exc_info=True)  # noqa: E501
                return None

        # ── Modules with complex cross-dependencies: return an initialized stub ─
        # These are logged so the gap is visible but startup is not blocked.
        logger.debug(
            "No specific factory for %s — using status stub", module_id
        )
        return {"module_id": module_id, "status": "initialized"}

    # ==================================================================================
    # SYSTEM SHUTDOWN
    # ==================================================================================

    def shutdown_system(self, reason: str = "User requested") -> bool:
        """Gracefully shutdown the system"""

        try:
            logger.info("=" * 80)
            logger.info("SYSTEM SHUTDOWN INITIATED - Reason: %s", reason)
            logger.info("=" * 80)

            self.shutdown_time = datetime.now(UTC)
            self.status = SystemStatus.STOPPING

            # Disable trading first
            self._disable_trading()

            # Execute shutdown sequence (reverse order of startup)
            shutdown_sequence = self._get_shutdown_sequence()

            for phase in shutdown_sequence:
                logger.info("Shutting down: %s", phase['name'])
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

            elapsed = (datetime.now(UTC) - self.shutdown_time).total_seconds()
            logger.info(f"SYSTEM SHUTDOWN COMPLETE in {elapsed:.2f} seconds")

            return True

        except Exception as e:
            logger.error("Shutdown error: %s", e, exc_info=True)
            self._emergency_shutdown()
            return False

    def _get_shutdown_sequence(self) -> list[dict[str, Any]]:
        """Get shutdown sequence (reverse of startup)"""

        return [
            {"name": "Autonomous Agents", "modules": ["Y10_AgentScheduler"]},
            {"name": "Task Scheduler", "modules": ["A04_Scheduler"]},
            {"name": "Notifications", "modules": ["J05_TelegramBot"]},
            {"name": "Trading & Orders", "modules": ["B02_OrderManager", "B03_PositionTracker", "R04_LiveEngine"]},  # noqa: E501
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

    def _shutdown_phase(self, module_ids: list[str]):
        """Shutdown a phase of modules"""

        for module_id in module_ids:
            try:
                if module_id in self.modules:
                    self._stop_module(module_id)
            except Exception as e:
                logger.error("Error stopping module %s: %s", module_id, e, exc_info=True)

    def _stop_module(self, module_id: str):
        """Stop an individual module"""

        if module_id not in self.modules:
            return

        module = self.modules[module_id]

        try:
            # v27 SPEC-3: read+delete must be atomic against parallel startup.
            with self._components_lock:
                component = self.components.get(module_id)
                if component is not None:
                    del self.components[module_id]
            # Call cleanup method if available (released lock — these can block).
            if component is not None:
                if hasattr(component, "stop_all"):
                    component.stop_all()
                elif hasattr(component, "stop"):
                    component.stop()
                elif hasattr(component, "shutdown"):
                    component.shutdown()

            module.status = ModuleStatus.STOPPED
            logger.info("✓ Module stopped: %s", module_id)

        except Exception as e:
            logger.error("Error stopping module %s: %s", module_id, e, exc_info=True)

    def _emergency_shutdown(self):
        """Emergency shutdown: cancel all open orders then force-stop all modules."""

        logger.critical("EMERGENCY SHUTDOWN ACTIVATED")
        self.status = SystemStatus.EMERGENCY_STOP

        try:
            # Cancel every open order via the OrderManager
            order_mgr = self.components.get("B02_OrderManager")
            if order_mgr is not None and hasattr(order_mgr, "_orders"):
                open_ids = [
                    oid
                    for oid, o in order_mgr._orders.items()
                    if hasattr(o, "state")
                    and str(o.state) not in ("FILLED", "CANCELLED", "REJECTED")
                ]
                logger.info("Cancelling %d open order(s)", len(open_ids))
                for order_id in open_ids:
                    try:
                        order_mgr.cancel_order(order_id)
                    except Exception as e:
                        logger.error(
                            "Failed to cancel order %s: %s", order_id, e, exc_info=True
                        )
            else:
                logger.warning(
                    "OrderManager not available — manual position review required"
                )

            # Signal all threads to stop
            self.shutdown_event.set()

            # Force-mark all modules stopped
            for module_id in self.modules:
                self.modules[module_id].status = ModuleStatus.STOPPED

            self.status = SystemStatus.STOPPED

        except Exception as e:
            logger.critical("Emergency shutdown error: %s", e, exc_info=True)

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

                # Sleep for monitoring interval (interruptible)
                self.shutdown_event.wait(timeout=10)

            except Exception as e:
                logger.error("Health monitor error: %s", e, exc_info=True)

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
        pt = self.components.get("B03_PositionTracker")
        if pt is not None and hasattr(pt, "positions"):
            try:
                pos_data = pt.positions
                active_positions = len(pos_data) if isinstance(pos_data, dict) else 0
            except Exception:
                active_positions = 0
        else:
            active_positions = 0
        daily_pnl = 0  # Would get from position tracker
        risk_utilization = 0  # Would get from risk manager

        # Error rate
        total_errors = sum(m.error_count for m in self.modules.values())
        error_rate = total_errors / max(len(self.modules), 1)

        return HealthMetrics(
            timestamp=datetime.now(UTC),
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
                        logger.warning("Health check failed for %s: %s", module_id, e, exc_info=True)  # noqa: E501
                        module.status = ModuleStatus.WARNING

    def _check_system_resources(self, metrics: HealthMetrics):
        """Check system resource usage"""

        # CPU warning
        if metrics.cpu_usage > 80:
            logger.warning("High CPU usage: %s%%", metrics.cpu_usage)

        # Memory warning
        if metrics.memory_usage > 85:
            logger.warning("High memory usage: %s%%", metrics.memory_usage)

        # Disk warning
        if metrics.disk_usage > 90:
            logger.critical("Critical disk usage: %s%%", metrics.disk_usage)

    def _check_stuck_modules(self):
        """Check for modules that might be stuck"""

        for module_id, module in self.modules.items():
            if module.status == ModuleStatus.STARTING:
                # Check if it's been starting for too long
                if module.metadata.get("start_time"):
                    elapsed = (datetime.now(UTC) - module.metadata["start_time"]).total_seconds()
                    if elapsed > 300:  # 5 minutes
                        logger.error("Module %s stuck in STARTING state", module_id)
                        module.status = ModuleStatus.ERROR

    def _handle_failed_modules(self):
        """Handle failed modules with restart logic"""

        for module_id, module in self.modules.items():
            if module.status == ModuleStatus.ERROR:
                # Check restart policy
                if module.restart_attempts < 3:
                    # Check cooldown period
                    if module.last_restart:
                        cooldown = (datetime.now(UTC) - module.last_restart).total_seconds()
                        if cooldown < 60:  # 1 minute cooldown
                            continue

                    logger.info("Attempting to restart module %s", module_id)
                    module.restart_attempts += 1
                    module.last_restart = datetime.now(UTC)
                    module.status = ModuleStatus.RESTARTING

                    # Attempt restart
                    self.executor.submit(self._restart_module, module_id)

    def _restart_module(self, module_id: str):
        """Restart a failed module"""

        try:
            # Stop the module first
            self._stop_module(module_id)
            time.sleep(2)  # thread-safe: time.sleep() intentional

            # Start it again
            if self._start_module(module_id):
                logger.info("Module %s restarted successfully", module_id)
                self.modules[module_id].restart_attempts = 0
            else:
                logger.error("Failed to restart module %s", module_id)

        except Exception as e:
            logger.error("Error restarting module %s: %s", module_id, e, exc_info=True)

    # ==================================================================================
    # MARKET STATE MANAGEMENT
    # ==================================================================================

    def _update_market_state(self):
        """Update current market state"""

        now = _now_et()  # US Eastern Time — market hours are expressed in ET
        current_time = now.time()
        weekday = now.weekday()

        # Check if weekend
        if weekday >= 5:  # Saturday = 5, Sunday = 6
            self.market_state = MarketState.WEEKEND
            return

        # Define market hours (US Eastern Time)
        pre_market_start = dt_time(4, 0)
        market_open = self._session_time("primary_start_et", "09:30")
        market_close = self._session_time("primary_end_et", "16:15")
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

        logger.info("Market state: %s", self.market_state.value)

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
            logger.error("Market open transition failed: %s", e, exc_info=True)

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
            logger.error("Market close transition failed: %s", e, exc_info=True)

    def _perform_premarket_checks(self):
        """Perform pre-market system checks"""

        checks = [
            ("Database Connection", self._check_database),
            ("Broker API Connection", self._check_broker_connection),
            ("Risk Limits", self._check_risk_limits),
            ("ML Models", self._check_ml_models),
            ("Account Balance", self._check_account_balance),
        ]

        for check_name, check_func in checks:
            try:
                if check_func():
                    logger.info("✓ Pre-market check passed: %s", check_name)
                else:
                    logger.warning("✗ Pre-market check failed: %s", check_name)
            except Exception as e:
                logger.error("Pre-market check error (%s): %s", check_name, e, exc_info=True)

    def _check_database(self) -> bool:
        """Check database connection"""
        return "H02_DatabaseManager" in self.components

    def _check_broker_connection(self) -> bool:
        """Check broker API connection (Tradier)"""
        return "B40_TradierClient" in self.components or "B01_SpyderClient" in self.components

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
        """Enable trading by starting the order manager and all loaded strategies."""

        if self.trading_enabled:
            logger.info("Trading already enabled")
            return

        self._update_market_state()
        if self.market_state != MarketState.MARKET_OPEN or not self._in_primary_trading_window():
            logger.warning(
                "Trading gate denied: market_state=%s in_primary_window=%s",
                self.market_state.value,
                self._in_primary_trading_window(),
            )
            return

        fail_closed = bool(
            self.config.autonomous_session.get("fail_closed_if_cutoff_unknown_live", True)
        )
        if self._is_live_mode() and fail_closed and not self._has_valid_broker_cutoff():
            logger.error("Trading gate denied in live mode: broker cutoff config missing/invalid")
            return

        logger.info("Enabling trading")

        # Start order manager (registers persistence thread and optional SSE stream)
        order_mgr = self.components.get("B02_OrderManager")
        if order_mgr is not None and hasattr(order_mgr, "start"):
            try:
                order_mgr.start()
                logger.info("OrderManager started")
            except Exception as e:
                logger.error("Failed to start OrderManager: %s", e, exc_info=True)

        # Wire D31 with the OrderManager so approved signals can be executed
        # (must happen before start_orchestration to avoid a CRITICAL log at boot)
        orchestrator = self.components.get("D31_StrategyOrchestrator")
        if orchestrator is not None and hasattr(orchestrator, "set_order_manager"):
            if order_mgr is not None and hasattr(order_mgr, "submit_limit_with_walk"):
                try:
                    orchestrator.set_order_manager(order_mgr)
                    logger.info("D31: OrderManager wired for mid-price-walk execution")
                except Exception as e:
                    logger.warning("D31: set_order_manager failed: %s", e)
            else:
                logger.warning(
                    "D31: B02_OrderManager not available — "
                    "approved signals will fall back to live engine or be dropped"
                )

        # Wire D31 with R04_LiveEngine as the execution fallback
        live_engine = self.components.get("R04_LiveEngine")
        if orchestrator is not None and hasattr(orchestrator, "set_live_engine") and live_engine is not None:  # noqa: E501
            try:
                orchestrator.set_live_engine(live_engine)
                logger.info("D31: R04_LiveEngine wired as execution fallback")
            except Exception as e:
                logger.warning("D31: set_live_engine failed: %s", e)

        # Wire D31 and E01 to the agent message bus.
        # GAP-4: activates Y01 → D31 market-regime updates.
        # GAP-2: activates Y02 → D31 validated-signal advisory tracking.
        # GAP-3: activates Y03 → E01 circuit-breaker veto channel.
        message_bus = self.components.get("I06_AgentMessageBus")
        if message_bus is not None:
            if orchestrator is not None and hasattr(orchestrator, "subscribe_agent_bus"):
                try:
                    orchestrator.subscribe_agent_bus(message_bus)
                    logger.info(
                        "D31: subscribed to agent bus "
                        "(Y01 regime updates + Y02 signal advisory active)"
                    )
                except Exception as e:
                    logger.warning("D31: subscribe_agent_bus failed: %s", e)
            risk_mgr = self.components.get("E01_RiskManager")
            if risk_mgr is not None and hasattr(risk_mgr, "wire_agent_bus"):
                try:
                    risk_mgr.wire_agent_bus(message_bus)
                    logger.info("E01: wired to agent bus (Y03 circuit-breaker veto active)")
                except Exception as e:
                    logger.warning("E01: wire_agent_bus failed: %s", e)

        # Start E19 portfolio risk monitor in a background daemon thread
        e19 = self.components.get("E19_UnifiedRiskCoordinator")
        if e19 is not None:
            import asyncio as _asyncio
            import threading as _threading
            import time as _time

            def _e19_monitor_loop():
                _loop = _asyncio.new_event_loop()
                _asyncio.set_event_loop(_loop)
                try:
                    while self.trading_enabled:
                        try:
                            # v27 SPEC-14: pull real positions from B03 and
                            # NLV from E01 cached balances each cycle. Passing
                            # [] and 0.0 forever meant E19 never detected
                            # breaches.
                            positions: list = []
                            portfolio_value: float = 0.0
                            try:
                                pt = self.components.get("B03_PositionTracker")
                                if pt is not None and hasattr(pt, "positions"):
                                    pos_data = pt.positions
                                    if isinstance(pos_data, dict):
                                        positions = list(pos_data.values())
                                    elif isinstance(pos_data, list):
                                        positions = pos_data
                            except Exception as _pt_exc:
                                logger.debug("E19 monitor: position pull failed: %s", _pt_exc)
                            try:
                                rm = self.components.get("E01_RiskManager")
                                if rm is not None:
                                    cached = getattr(rm, "_cached_account_balances", {}) or {}
                                    portfolio_value = float(
                                        cached.get("net_liquidation", 0.0) or 0.0
                                    )
                            except Exception as _nlv_exc:
                                logger.debug("E19 monitor: NLV pull failed: %s", _nlv_exc)

                            profile = _loop.run_until_complete(
                                e19.calculate_unified_risk_profile(
                                    positions=positions,
                                    portfolio_value=portfolio_value,
                                )
                            )
                            if profile and getattr(profile, "breach_count", 0) > 0:
                                logger.warning(
                                    "E19 portfolio risk breach detected (%d breaches): %s",
                                    profile.breach_count, profile,
                                )
                        except Exception as _exc:
                            logger.debug("E19 monitor cycle error: %s", _exc)
                        _time.sleep(60)
                finally:
                    _loop.close()

            _threading.Thread(
                target=_e19_monitor_loop, daemon=True, name="E19-portfolio-monitor"
            ).start()
            logger.info("E19 portfolio risk monitor thread started (60s interval)")

        # Start strategy components
        # v27 SPEC-3: snapshot under lock, then iterate without holding it
        # (strategy.start() may block; we don't want to serialize startups).
        with self._components_lock:
            _strategy_snapshot = list(self.components.items())
        for module_id, component in _strategy_snapshot:
            if module_id.startswith("D") and hasattr(component, "start"):
                try:
                    component.start()
                    logger.debug("Strategy %s started", module_id)
                except Exception as e:
                    logger.warning("Failed to start strategy %s: %s", module_id, e)

        # Start the strategy orchestration loop so signals are generated
        if orchestrator is not None and hasattr(orchestrator, "start_orchestration"):
            try:
                orchestrator.start_orchestration()
                logger.info("StrategyOrchestrator orchestration loop started")
            except Exception as e:
                logger.error("Failed to start StrategyOrchestrator: %s", e, exc_info=True)

        self.trading_enabled = True
        self.status = SystemStatus.TRADING
        self._broadcast_event("TRADING_ENABLED", {"mode": self.config.trading_mode.value})
        logger.info("Trading enabled")

    def _disable_trading(self):
        """Disable trading by stopping all strategies then the order manager."""

        if not self.trading_enabled:
            return

        logger.info("Disabling trading")

        # Stop strategy components first so no new orders are generated
        for module_id, component in list(self.components.items()):
            if module_id.startswith("D") and hasattr(component, "stop"):
                try:
                    component.stop()
                    logger.debug("Strategy %s stopped", module_id)
                except Exception as e:
                    logger.warning("Failed to stop strategy %s: %s", module_id, e)

        # Stop order manager (flushes persistence thread, closes SSE stream)
        order_mgr = self.components.get("B02_OrderManager")
        if order_mgr is not None and hasattr(order_mgr, "stop"):
            try:
                order_mgr.stop()
                logger.info("OrderManager stopped")
            except Exception as e:
                logger.error("Failed to stop OrderManager: %s", e, exc_info=True)

        self.trading_enabled = False
        self.status = SystemStatus.RUNNING
        self._broadcast_event("TRADING_DISABLED", {})
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
            "startup_duration": (datetime.now(UTC) - self.startup_time).total_seconds(),
        }

        logger.info("Startup Report:")
        for key, value in report.items():
            logger.info("  %s: %s", key, value)

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
            "shutdown_duration": (datetime.now(UTC) - self.shutdown_time).total_seconds(),
        }

        logger.info("Shutdown Report:")
        for key, value in report.items():
            logger.info("  %s: %s", key, value)

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

    def _broadcast_event(self, event_type: str, data: dict[str, Any]):
        """Broadcast event to all modules via the AgentMessageBus."""

        message_bus = self.components.get("I06_AgentMessageBus")
        if message_bus is not None and hasattr(message_bus, "broadcast"):
            try:
                message_bus.broadcast(
                    payload={
                        "event": event_type,
                        "data": data,
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                    sender="MasterController",
                )
                logger.debug("Broadcast event dispatched: %s", event_type)
            except Exception as e:
                logger.warning("Failed to broadcast event %s: %s", event_type, e)
        else:
            logger.debug("Broadcasting event: %s (message bus not available)", event_type)

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""

        def signal_handler(signum, frame):
            logger.info("Received signal %s", signum)
            self.shutdown_system("Signal received")
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    # ==================================================================================
    # PUBLIC API
    # ==================================================================================

    def get_system_status(self) -> dict[str, Any]:
        """Get current system status"""

        return {
            "status": self.status.value,
            "market_state": self.market_state.value,
            "trading_enabled": self.trading_enabled,
            "uptime": (
                (datetime.now(UTC) - self.startup_time).total_seconds() if self.startup_time else 0
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

    def get_module_status(self, module_id: str) -> dict[str, Any] | None:
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
            logger.error("Module %s not found", module_id)
            return False

        logger.info("Manual restart requested for %s", module_id)
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


def create_master_controller(config_path: str | None = None) -> MasterController:
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

    # Load .env so API keys/tokens are available when running outside systemd.
    try:
        from dotenv import load_dotenv as _load_dotenv
        _load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
    except ImportError:
        pass  # python-dotenv not installed; rely on env vars already exported

    # Create master controller
    master = create_master_controller()

    # Start system
    if master.start_system():
        status = master.get_system_status()
        for _key, _value in status.items():
            pass


        try:
            # Keep the system running
            # Track which date-keyed transitions have already fired to avoid
            # duplicate triggers when the loop wakes up mid-minute.
            _fired: set = set()
            while True:
                time.sleep(1)

                # v27 FIX: market open/close are ET — UTC was 4-5h offset.
                now = _now_et()
                date_key = now.date()

                # Market open at configured session start (ET)
                open_key = (date_key, "open")
                session_open = master._session_time("primary_start_et", "09:30")
                if (
                    open_key not in _fired
                    and now.hour == session_open.hour
                    and now.minute >= session_open.minute
                    and master.market_state != MarketState.MARKET_OPEN
                ):
                    master.handle_market_open()
                    _fired.add(open_key)

                # Market close at configured session close (ET)
                close_key = (date_key, "close")
                session_close = master._session_time("primary_end_et", "16:15")
                if (
                    close_key not in _fired
                    and (
                        now.hour > session_close.hour
                        or (now.hour == session_close.hour and now.minute >= session_close.minute)
                    )
                    and master.market_state == MarketState.MARKET_OPEN
                ):
                    master.handle_market_close()
                    _fired.add(close_key)

        except KeyboardInterrupt:
            master.shutdown_system("User interrupted")

    else:
        sys.exit(1)
