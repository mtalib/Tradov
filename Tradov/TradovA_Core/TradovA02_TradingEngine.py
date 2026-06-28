#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovA_Core
Module: TradovA02_TradingEngine.py
Purpose: Complete trading engine with strategy orchestration and execution

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-06-26 Time: 13:25:07

Module Description:
    This module serves as the core trading engine for the Tradov system. It manages
    strategy registration and lifecycle, coordinates order execution, handles position
    management, and integrates with risk management systems. The engine provides
    real-time monitoring, automated error recovery, and comprehensive performance
    tracking for all trading operations.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import json
import os
import time
import threading
import uuid
from datetime import datetime, timedelta, UTC
from typing import Any
from dataclasses import dataclass, field, asdict
from collections import deque
from enum import Enum, auto
from pathlib import Path
import queue
import joblib

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from threading import Lock, Event as ThreadEvent, RLock

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger
from Tradov.TradovU_Utilities.TradovU02_ErrorHandler import TradovErrorHandler

# Safe imports with fallbacks
try:
    from Tradov.TradovU_Utilities.TradovU07_Constants import (
        OrderAction, OrderType, OptionType, SignalType
    )
except ImportError:
    # Define basic enums if not available
    from enum import Enum

    class OrderAction(Enum):
        BUY = "BUY"
        SELL = "SELL"

    class OrderType(Enum):
        MARKET = "MARKET"
        LIMIT = "LIMIT"
        STOP = "STOP"

    class OptionType(Enum):
        CALL = "CALL"
        PUT = "PUT"

    class SignalType(Enum):
        ENTRY = "ENTRY"
        EXIT = "EXIT"

try:
    from TradovA_Core.TradovA05_EventManager import EventManager, Event, EventType
except ImportError:
    # Minimal EventManager if not available
    EventManager = None
    Event = None
    EventType = type('EventType', (), {
        'SYSTEM': 'SYSTEM',
        'ORDER_FILLED': 'ORDER_FILLED',
        'ORDER_CANCELLED': 'ORDER_CANCELLED',
        'POSITION_UPDATE': 'POSITION_UPDATE',
        'SYSTEM_ERROR': 'SYSTEM_ERROR',
        'SYSTEM_WARNING': 'SYSTEM_WARNING',
        'STRATEGY_SIGNAL': 'STRATEGY_SIGNAL',
        'CRITICAL_ERROR': 'CRITICAL_ERROR',
        'ALERT': 'ALERT',
        'RISK_ALERT': 'RISK_ALERT'
    })()

try:
    from TradovE_Risk.TradovE01_RiskManager import get_risk_manager, RiskProfile
    from TradovE_Risk.TradovE00_RiskProtocol import RiskValidationRequest, BoundarySignalType
except ImportError:
    get_risk_manager = None
    RiskProfile = None
    RiskValidationRequest = None  # type: ignore[assignment,misc]
    BoundarySignalType = None  # type: ignore[assignment,misc]

try:
    from TradovH_Storage.TradovH01_DataAccessLayer import get_data_access_layer
except ImportError:
    get_data_access_layer = None

# ==============================================================================
# CONSTANTS
# ==============================================================================
MAX_STRATEGIES = 20
MAX_ORDERS_PER_MINUTE = 100
MAX_POSITION_AGE_HOURS = 24
PERFORMANCE_WINDOW_SIZE = 1000
HEALTH_CHECK_INTERVAL = 60  # seconds
CLEANUP_INTERVAL = 300  # 5 minutes
STATE_SAVE_INTERVAL = 60  # seconds
MAX_ORDER_RETRIES = 3
ORDER_RETRY_DELAY = 1  # seconds
DEFAULT_PERMITTED_PIPELINE_STRATEGIES = (
    "iron_condor",
    "credit_spread",
    "iron_butterfly",
    "broken_wing_butterfly",
    "bull_put_spread",
)

# ==============================================================================
# ENUMS
# ==============================================================================
class EngineState(Enum):
    """Trading engine operational states"""
    INITIALIZING = auto()
    READY = auto()
    RUNNING = auto()
    PAUSED = auto()
    STOPPED = auto()
    ERROR = auto()
    RECOVERING = auto()

class StrategyState(Enum):
    """Strategy lifecycle states"""
    REGISTERED = auto()
    INITIALIZING = auto()
    ACTIVE = auto()
    PAUSED = auto()
    STOPPED = auto()
    ERROR = auto()
    DISABLED = auto()

class OrderState(Enum):
    """Order execution states"""
    PENDING = auto()
    SUBMITTED = auto()
    FILLED = auto()
    PARTIAL_FILL = auto()
    CANCELLED = auto()
    REJECTED = auto()
    ERROR = auto()

class CircuitBreakerState(Enum):
    """Circuit breaker states"""
    NORMAL = auto()
    WARNING = auto()
    TRIGGERED = auto()
    RECOVERING = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class StrategyInfo:
    """Strategy registration information"""
    strategy_id: str
    name: str
    class_instance: Any
    state: StrategyState = StrategyState.REGISTERED
    config: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_signal: datetime | None = None
    signal_count: int = 0
    order_count: int = 0
    pnl: float = 0.0
    error_count: int = 0
    last_error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class OrderInfo:
    """Order tracking information"""
    order_id: str
    strategy_id: str
    symbol: str
    action: OrderAction
    order_type: OrderType
    quantity: int
    price: float | None
    state: OrderState = OrderState.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    submitted_at: datetime | None = None
    filled_at: datetime | None = None
    fill_price: float | None = None
    commission: float = 0.0
    retry_count: int = 0
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class PositionInfo:
    """Position tracking information"""
    position_id: str
    strategy_id: str
    symbol: str
    quantity: int
    entry_price: float
    entry_time: datetime
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    high_water_mark: float = 0.0
    max_drawdown: float = 0.0
    holding_period: timedelta = timedelta()
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class PerformanceMetrics:
    """Engine performance metrics"""
    total_orders: int = 0
    successful_orders: int = 0
    failed_orders: int = 0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    uptime_seconds: float = 0.0
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))

@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration"""
    max_loss_per_minute: float = 1000.0
    max_orders_per_minute: int = 50
    max_errors_per_hour: int = 10
    max_daily_loss: float = 5000.0
    cooldown_minutes: int = 15
    recovery_threshold: float = 0.8  # 80% of limits

@dataclass
class EngineHealth:
    """Engine health status"""
    state: EngineState
    uptime: timedelta
    active_strategies: int
    open_orders: int
    open_positions: int
    circuit_breaker_state: CircuitBreakerState
    last_error: str | None
    error_rate: float
    order_success_rate: float
    memory_usage_mb: float
    cpu_usage_percent: float
    last_health_check: datetime

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class TradingEngine:
    """
    Core trading engine for strategy orchestration and execution.

    This class manages the complete lifecycle of trading strategies including
    registration, initialization, signal processing, order execution, position
    management, and performance tracking. It provides thread-safe operations,
    circuit breaker protection, and comprehensive error recovery.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling system
        event_manager: Event management system
        tradov_client: Broker client interface
        risk_manager: Risk management system
        dal: Data access layer
        state: Current engine state
        strategies: Registered trading strategies
        orders: Active order tracking
        positions: Open position tracking
        performance: Performance metrics
        circuit_breaker: Circuit breaker protection
    """

    def __init__(self, config: dict[str, Any], tradov_client, event_manager):
        """
        Initialize the trading engine.

        Args:
            config: Engine configuration
            tradov_client: Broker client instance
            event_manager: Event management system
        """
        # Core components
        self.logger = TradovLogger.get_logger(self.__class__.__name__)
        self.error_handler = TradovErrorHandler()
        self.event_manager = event_manager
        self.tradov_client = tradov_client
        self.dal = get_data_access_layer() if get_data_access_layer else None

        # Configuration
        self.config = config or {}
        self.max_strategies = self.config.get('max_strategies', MAX_STRATEGIES)
        self.max_orders_per_minute = self.config.get('max_orders_per_minute', MAX_ORDERS_PER_MINUTE)
        self.enable_circuit_breaker = self.config.get('enable_circuit_breaker', True)
        self.save_state_enabled = self.config.get('save_state', True)
        self.lean_mode = self._resolve_lean_mode()

        # State management
        self.state = EngineState.INITIALIZING
        self._state_lock = RLock()
        self._shutdown_event = ThreadEvent()

        # Strategy management
        self.strategies: dict[str, StrategyInfo] = {}
        self._strategy_lock = RLock()

        # Order management
        self.orders: dict[str, OrderInfo] = {}
        self.order_queue = queue.PriorityQueue()
        self._order_lock = RLock()
        self._order_processor_thread = None

        # Position management
        self.positions: dict[str, PositionInfo] = {}
        self._position_lock = RLock()

        # Performance tracking
        self.performance = PerformanceMetrics()
        self.performance_history = deque(maxlen=PERFORMANCE_WINDOW_SIZE)
        self._performance_lock = Lock()

        # Circuit breaker
        self.circuit_breaker_config = self._init_circuit_breaker_config()
        self.circuit_breaker_state = CircuitBreakerState.NORMAL
        self.circuit_breaker_metrics = {
            'loss_per_minute': 0.0,
            'orders_per_minute': 0,
            'errors_per_hour': 0,
            'daily_loss': 0.0,
            'triggered_at': None,
            'recovery_at': None
        }
        self._circuit_breaker_lock = Lock()

        # Risk management integration
        self.risk_manager = None
        self.has_risk_manager = False

        # Order manager integration
        self.order_manager = None
        self.has_order_manager = False

        # Position tracker integration
        self.position_tracker = None
        self.has_position_tracker = False

        # Entry trust gate (F09 + S07) is resolved lazily to avoid startup hard dependencies.
        self._entry_filter_gate: Any | None = None
        self._metrics_orchestrator: Any | None = None
        self._regime_policy: dict[str, Any] | None = None
        self._decision_flow_traces: deque[dict[str, Any]] = deque(maxlen=500)
        self.max_concurrent_strategies = int(
            self.config.get('max_concurrent_strategies', 2)
        )

        # Worker threads
        self._monitor_thread = None
        self._cleanup_thread = None
        self._state_save_thread = None

        # Timing
        self.start_time = None
        self.last_health_check = datetime.now(UTC)

        # State persistence
        self._state_file = Path.home() / ".tradov" / "engine_state.pkl"
        self._state_file.parent.mkdir(parents=True, exist_ok=True)

        self.logger.info("TradingEngine initialized with %s config parameters", len(self.config))

    def _init_circuit_breaker_config(self) -> CircuitBreakerConfig:
        """Initialize circuit breaker configuration"""
        cb_config = self.config.get('circuit_breaker', {})
        return CircuitBreakerConfig(
            max_loss_per_minute=cb_config.get('max_loss_per_minute', 1000.0),
            max_orders_per_minute=cb_config.get('max_orders_per_minute', 50),
            max_errors_per_hour=cb_config.get('max_errors_per_hour', 10),
            max_daily_loss=cb_config.get('max_daily_loss', 5000.0),
            cooldown_minutes=cb_config.get('cooldown_minutes', 15),
            recovery_threshold=cb_config.get('recovery_threshold', 0.8)
        )

    # ==========================================================================
    # RISK MANAGER INTEGRATION
    # ==========================================================================

    def set_risk_manager(self, risk_manager) -> bool:
        """
        Set the risk manager for the trading engine.

        Args:
            risk_manager: RiskManager instance

        Returns:
            bool: True if set successfully
        """
        try:
            self.risk_manager = risk_manager
            self.has_risk_manager = True

            # Register callbacks if risk manager supports them
            if hasattr(risk_manager, 'register_alert_callback'):
                risk_manager.register_alert_callback(self._on_risk_alert)

            if hasattr(risk_manager, 'register_mitigation_callback'):
                risk_manager.register_mitigation_callback(self._on_risk_mitigation)

            self.logger.info("Risk manager set successfully")

            # Emit event
            if self.event_manager:
                self.event_manager.emit(
                    EventType.SYSTEM,
                    {
                        'type': 'risk_manager_connected',
                        'timestamp': datetime.now(UTC)
                    }
                )

            return True

        except Exception as e:
            self.logger.error("Failed to set risk manager: %s", e)
            self.has_risk_manager = False
            return False

    def set_order_manager(self, order_manager) -> bool:
        """
        Set the order manager for the trading engine.

        Args:
            order_manager: OrderManager instance

        Returns:
            bool: True if set successfully
        """
        try:
            self.order_manager = order_manager
            self.has_order_manager = True

            self.logger.info("Order manager set successfully")

            return True

        except Exception as e:
            self.logger.error("Failed to set order manager: %s", e)
            self.has_order_manager = False
            return False

    def set_position_tracker(self, position_tracker) -> bool:
        """
        Set the position tracker for the trading engine.

        Args:
            position_tracker: PositionTracker instance

        Returns:
            bool: True if set successfully
        """
        try:
            self.position_tracker = position_tracker
            self.has_position_tracker = True

            self.logger.info("Position tracker set successfully")

            return True

        except Exception as e:
            self.logger.error("Failed to set position tracker: %s", e)
            self.has_position_tracker = False
            return False

    def _on_risk_alert(self, alert):
        """Handle risk alert from risk manager."""
        try:
            self.logger.warning("Risk alert received: %s", alert.message)

            # Emit risk alert event
            if self.event_manager:
                self.event_manager.emit(
                    EventType.RISK_ALERT,
                    {
                        'alert_id': alert.alert_id,
                        'severity': alert.severity.value,
                        'message': alert.message,
                        'timestamp': alert.timestamp
                    }
                )

            # Take action based on severity
            if alert.severity.value == 'critical':
                self.logger.critical("Critical risk alert: %s", alert.message)
                # Consider pausing trading
                if self.config.get('auto_pause_on_critical_risk', False):
                    self.pause(f"Critical risk alert: {alert.message}")

        except Exception as e:
            self.logger.error("Risk alert handler error: %s", e)

    def _on_risk_mitigation(self, alert):
        """Handle risk mitigation action from risk manager."""
        try:
            self.logger.warning("Risk mitigation triggered: %s", alert.recommended_action)

            # Take action based on mitigation type
            if alert.recommended_action.value == 'stop_trading':
                self.pause("Risk mitigation - stop trading")
            elif alert.recommended_action.value == 'close_position' and alert.position_id:
                # Implement position closing logic
                self._close_position_for_risk(alert.position_id)
            elif alert.recommended_action.value == 'reduce_position' and alert.position_id:
                # Implement position reduction logic
                self._reduce_position_for_risk(alert.position_id)

        except Exception as e:
            self.logger.error("Risk mitigation handler error: %s", e)

    def _close_position_for_risk(self, position_id: str):
        """Close a position due to risk mitigation."""
        try:
            position = self.positions.get(position_id)
            if position:
                # Create close order
                close_order = {
                    'symbol': position.symbol,
                    'action': OrderAction.SELL if position.quantity > 0 else OrderAction.BUY,
                    'quantity': abs(position.quantity),
                    'order_type': OrderType.MARKET,
                    'metadata': {'reason': 'risk_mitigation'}
                }

                # Submit order
                self.process_signal(position.strategy_id, close_order)

                self.logger.info("Closing position %s for risk mitigation", position_id)

        except Exception as e:
            self.logger.error("Failed to close position for risk: %s", e)

    def _reduce_position_for_risk(self, position_id: str):
        """Reduce a position due to risk mitigation."""
        try:
            position = self.positions.get(position_id)
            if position:
                # Reduce position by 50%
                reduce_quantity = abs(position.quantity) // 2

                if reduce_quantity > 0:
                    reduce_order = {
                        'symbol': position.symbol,
                        'action': OrderAction.SELL if position.quantity > 0 else OrderAction.BUY,
                        'quantity': reduce_quantity,
                        'order_type': OrderType.MARKET,
                        'metadata': {'reason': 'risk_reduction'}
                    }

                    # Submit order
                    self.process_signal(position.strategy_id, reduce_order)

                    self.logger.info("Reducing position %s by %s units", position_id, reduce_quantity)  # noqa: E501

        except Exception as e:
            self.logger.error("Failed to reduce position for risk: %s", e)

    # ==========================================================================
    # LIFECYCLE MANAGEMENT
    # ==========================================================================

    def initialize(self) -> bool:
        """
        Initialize the trading engine with all safety checks.

        Returns:
            bool: True if initialization successful
        """
        try:
            with self._state_lock:
                if self.state != EngineState.INITIALIZING:
                    self.logger.warning("Cannot initialize from state: %s", self.state)
                    return False

                self.logger.info("Initializing TradingEngine...")

                # Load saved state if available
                if self.save_state_enabled:
                    self._load_state()

                # Initialize risk management if available
                if get_risk_manager:
                    try:
                        portfolio_value = self.config.get('portfolio_value', 100000.0)
                        self.risk_manager = get_risk_manager(portfolio_value, self.config)
                        if self.risk_manager and self.risk_manager.initialize():
                            self.has_risk_manager = True
                            self.logger.info("Risk manager initialized")
                            # Wire Y03 RiskSentinelAgent veto channel if message bus is available
                            message_bus = getattr(self, 'message_bus', None)
                            if message_bus is not None and hasattr(self.risk_manager, 'wire_agent_bus'):  # noqa: E501
                                self.risk_manager.wire_agent_bus(message_bus)
                        else:
                            self.logger.warning("Risk manager not available")
                    except Exception as e:
                        self.logger.warning("Risk manager initialization failed: %s", e)

                # Set up event handlers
                self._setup_event_handlers()

                # Initialize performance tracking
                self._initialize_performance_tracking()

                # Validate configuration
                if not self._validate_configuration():
                    self.logger.error("Configuration validation failed")
                    return False

                self.state = EngineState.READY
                self.logger.info("TradingEngine initialization completed successfully")

                # Emit initialization event
                if self.event_manager:
                    self.event_manager.emit(
                        EventType.SYSTEM,
                        {
                            'type': 'engine_initialized',
                            'timestamp': datetime.now(UTC),
                            'state': self.state.value
                        }
                    )

                return True

        except Exception as e:
            self.logger.error("TradingEngine initialization failed: %s", e)
            self.error_handler.handle_error(e, "TradingEngine.initialize")
            self.state = EngineState.ERROR
            return False

    def start(self) -> bool:
        """
        Start the trading engine with all subsystems.

        Returns:
            bool: True if start successful
        """
        try:
            with self._state_lock:
                if self.state != EngineState.READY:
                    self.logger.warning("Cannot start from state: %s", self.state)
                    return False

                self.logger.info("Starting TradingEngine...")
                self.start_time = datetime.now(UTC)

                # Clear shutdown event
                self._shutdown_event.clear()

                # Start worker threads
                self._start_worker_threads()

                # Start monitoring systems
                self._start_monitoring()

                # Start risk monitoring if available
                if self.has_risk_manager and self.risk_manager:
                    self.risk_manager.start_monitoring()

                # Initialize circuit breaker metrics
                self._reset_circuit_breaker_metrics()

                self.state = EngineState.RUNNING
                self.logger.info("TradingEngine started successfully")

                # Emit start event
                if self.event_manager:
                    self.event_manager.emit(
                        EventType.SYSTEM,
                        {
                            'type': 'engine_started',
                            'timestamp': self.start_time,
                            'state': self.state.value
                        }
                    )

                return True

        except Exception as e:
            self.logger.error("TradingEngine start failed: %s", e)
            self.error_handler.handle_error(e, "TradingEngine.start")
            self.state = EngineState.ERROR
            return False

    def stop(self, reason: str = "Manual stop") -> bool:
        """
        Stop the trading engine gracefully.

        Args:
            reason: Reason for stopping

        Returns:
            bool: True if stop successful
        """
        try:
            with self._state_lock:
                if self.state not in [EngineState.RUNNING, EngineState.PAUSED, EngineState.ERROR]:
                    self.logger.warning("Cannot stop from state: %s", self.state)
                    return False

                self.logger.info("Stopping TradingEngine: %s", reason)

                # Signal shutdown
                self._shutdown_event.set()

                # Stop all strategies
                self._stop_all_strategies(reason)

                # Cancel pending orders
                self._cancel_all_pending_orders(reason)

                # Stop worker threads
                self._stop_worker_threads()

                # Save final state
                if self.save_state_enabled:
                    self._save_state()

                # Calculate session metrics
                session_duration = timedelta()
                if self.start_time:
                    session_duration = datetime.now(UTC) - self.start_time
                    self.performance.uptime_seconds = session_duration.total_seconds()

                self.state = EngineState.STOPPED
                self.logger.info("TradingEngine stopped successfully after %s", session_duration)

                # Emit stop event
                if self.event_manager:
                    self.event_manager.emit(
                        EventType.SYSTEM,
                        {
                            'type': 'engine_stopped',
                            'timestamp': datetime.now(UTC),
                            'reason': reason,
                            'session_duration': str(session_duration) if self.start_time else None
                        }
                    )

                return True

        except Exception as e:
            self.logger.error("TradingEngine stop failed: %s", e)
            self.error_handler.handle_error(e, "TradingEngine.stop")
            return False

    def pause(self, reason: str = "Manual pause") -> bool:
        """
        Pause trading operations without stopping the engine.

        Args:
            reason: Reason for pausing

        Returns:
            bool: True if pause successful
        """
        try:
            with self._state_lock:
                if self.state != EngineState.RUNNING:
                    self.logger.warning("Cannot pause from state: %s", self.state)
                    return False

                self.logger.info("Pausing TradingEngine: %s", reason)

                # Pause all active strategies
                for strategy_id in list(self.strategies.keys()):
                    self._pause_strategy(strategy_id)

                self.state = EngineState.PAUSED

                # Emit pause event
                if self.event_manager:
                    self.event_manager.emit(
                        EventType.SYSTEM,
                        {
                            'type': 'engine_paused',
                            'timestamp': datetime.now(UTC),
                            'reason': reason
                        }
                    )

                return True

        except Exception as e:
            self.logger.error("TradingEngine pause failed: %s", e)
            self.error_handler.handle_error(e, "TradingEngine.pause")
            return False

    def resume(self) -> bool:
        """
        Resume trading operations after pause.

        Returns:
            bool: True if resume successful
        """
        try:
            with self._state_lock:
                if self.state != EngineState.PAUSED:
                    self.logger.warning("Cannot resume from state: %s", self.state)
                    return False

                self.logger.info("Resuming TradingEngine...")

                # Check circuit breaker state
                if self.circuit_breaker_state == CircuitBreakerState.TRIGGERED:
                    self.logger.warning("Cannot resume - circuit breaker is triggered")
                    return False

                # Resume all paused strategies
                for strategy_id, strategy_info in self.strategies.items():
                    if strategy_info.state == StrategyState.PAUSED:
                        self._resume_strategy(strategy_id)

                self.state = EngineState.RUNNING

                # Emit resume event
                if self.event_manager:
                    self.event_manager.emit(
                        EventType.SYSTEM,
                        {
                            'type': 'engine_resumed',
                            'timestamp': datetime.now(UTC)
                        }
                    )

                return True

        except Exception as e:
            self.logger.error("TradingEngine resume failed: %s", e)
            self.error_handler.handle_error(e, "TradingEngine.resume")
            return False

    def shutdown(self) -> bool:
        """
        Perform complete shutdown with cleanup.

        Returns:
            bool: True if shutdown successful
        """
        try:
            self.logger.info("Shutting down TradingEngine...")

            # Stop if running
            if self.state in [EngineState.RUNNING, EngineState.PAUSED]:
                self.stop("Shutdown requested")

            # Clean up resources
            self._cleanup_resources()

            # Clear all data structures
            with self._strategy_lock:
                self.strategies.clear()

            with self._order_lock:
                self.orders.clear()

            with self._position_lock:
                self.positions.clear()

            self.logger.info("TradingEngine shutdown completed")
            return True

        except Exception as e:
            self.logger.error("TradingEngine shutdown failed: %s", e)
            return False

    # ==========================================================================
    # STRATEGY MANAGEMENT
    # ==========================================================================

    def register_strategy(self, strategy_id: str, strategy_instance: Any,
                         config: dict[str, Any] | None = None) -> bool:
        """
        Register a trading strategy with the engine.

        Args:
            strategy_id: Unique strategy identifier
            strategy_instance: Strategy class instance
            config: Strategy configuration

        Returns:
            bool: True if registration successful
        """
        try:
            with self._strategy_lock:
                # Check if already registered
                if strategy_id in self.strategies:
                    self.logger.warning("Strategy %s already registered", strategy_id)
                    return False

                # Check strategy limit
                if len(self.strategies) >= self.max_strategies:
                    self.logger.error("Maximum strategies (%s) reached", self.max_strategies)
                    return False

                # Validate strategy instance
                if not self._validate_strategy(strategy_instance):
                    self.logger.error("Strategy %s validation failed", strategy_id)
                    return False

                # Create strategy info
                strategy_info = StrategyInfo(
                    strategy_id=strategy_id,
                    name=getattr(strategy_instance, 'name', strategy_id),
                    class_instance=strategy_instance,
                    config=config or {},
                    state=StrategyState.REGISTERED
                )

                # Store strategy
                self.strategies[strategy_id] = strategy_info

                # Initialize strategy if engine is running
                if self.state == EngineState.RUNNING:
                    self._initialize_strategy(strategy_id)

                self.logger.info("Registered strategy: %s", strategy_id)

                # Emit registration event
                if self.event_manager:
                    self.event_manager.emit(
                        EventType.SYSTEM,
                        {
                            'type': 'strategy_registered',
                            'strategy_id': strategy_id,
                            'timestamp': datetime.now(UTC)
                        }
                    )

                return True

        except Exception as e:
            self.logger.error("Strategy registration failed: %s", e)
            self.error_handler.handle_error(e, f"register_strategy.{strategy_id}")
            return False

    def unregister_strategy(self, strategy_id: str, force: bool = False) -> bool:
        """
        Unregister a trading strategy.

        Args:
            strategy_id: Strategy identifier
            force: Force unregistration even with open positions

        Returns:
            bool: True if unregistration successful
        """
        try:
            with self._strategy_lock:
                if strategy_id not in self.strategies:
                    self.logger.warning("Strategy %s not found", strategy_id)
                    return False

                strategy_info = self.strategies[strategy_id]

                # Check for open positions
                open_positions = self._get_strategy_positions(strategy_id)
                if open_positions and not force:
                    self.logger.error("Cannot unregister strategy %s with %s open positions", strategy_id, len(open_positions))  # noqa: E501
                    return False

                # Stop strategy if active
                if strategy_info.state in [StrategyState.ACTIVE, StrategyState.PAUSED]:
                    self._stop_strategy(strategy_id, "Unregistration requested")

                # Clean up strategy resources
                self._cleanup_strategy(strategy_id)

                # Remove strategy
                del self.strategies[strategy_id]

                self.logger.info("Unregistered strategy: %s", strategy_id)

                # Emit unregistration event
                if self.event_manager:
                    self.event_manager.emit(
                        EventType.SYSTEM,
                        {
                            'type': 'strategy_unregistered',
                            'strategy_id': strategy_id,
                            'timestamp': datetime.now(UTC)
                        }
                    )

                return True

        except Exception as e:
            self.logger.error("Strategy unregistration failed: %s", e)
            self.error_handler.handle_error(e, f"unregister_strategy.{strategy_id}")
            return False

    def _validate_strategy(self, strategy_instance: Any) -> bool:
        """Validate strategy instance has required methods"""
        required_methods = ['initialize', 'generate_signals', 'on_position_update']

        for method in required_methods:
            if not hasattr(strategy_instance, method):
                self.logger.error("Strategy missing required method: %s", method)
                return False

        return True

    def _initialize_strategy(self, strategy_id: str) -> bool:
        """Initialize a registered strategy"""
        try:
            strategy_info = self.strategies.get(strategy_id)
            if not strategy_info:
                return False

            strategy_info.state = StrategyState.INITIALIZING

            # Call strategy initialization
            if hasattr(strategy_info.class_instance, 'initialize'):
                result = strategy_info.class_instance.initialize(strategy_info.config)
                if not result:
                    strategy_info.state = StrategyState.ERROR
                    strategy_info.last_error = "Initialization failed"
                    return False

            strategy_info.state = StrategyState.ACTIVE
            self.logger.info("Strategy %s initialized successfully", strategy_id)
            return True

        except Exception as e:
            self.logger.error("Strategy initialization failed: %s", e)
            if strategy_info:
                strategy_info.state = StrategyState.ERROR
                strategy_info.last_error = str(e)
            return False

    def _stop_strategy(self, strategy_id: str, reason: str) -> bool:
        """Stop a running strategy"""
        try:
            strategy_info = self.strategies.get(strategy_id)
            if not strategy_info:
                return False

            # Cancel strategy orders
            self._cancel_strategy_orders(strategy_id, reason)

            # Call strategy stop method if available
            if hasattr(strategy_info.class_instance, 'stop'):
                strategy_info.class_instance.stop(reason)

            strategy_info.state = StrategyState.STOPPED
            self.logger.info("Strategy %s stopped: %s", strategy_id, reason)
            return True

        except Exception as e:
            self.logger.error("Strategy stop failed: %s", e)
            return False

    def _pause_strategy(self, strategy_id: str) -> bool:
        """Pause a running strategy"""
        strategy_info = self.strategies.get(strategy_id)
        if strategy_info and strategy_info.state == StrategyState.ACTIVE:
            strategy_info.state = StrategyState.PAUSED
            self.logger.info("Strategy %s paused", strategy_id)
            return True
        return False

    def _resume_strategy(self, strategy_id: str) -> bool:
        """Resume a paused strategy"""
        strategy_info = self.strategies.get(strategy_id)
        if strategy_info and strategy_info.state == StrategyState.PAUSED:
            strategy_info.state = StrategyState.ACTIVE
            self.logger.info("Strategy %s resumed", strategy_id)
            return True
        return False

    def _cleanup_strategy(self, strategy_id: str):
        """Clean up strategy resources"""
        try:
            # Close any open positions (if forced)
            positions = self._get_strategy_positions(strategy_id)
            for position in positions:
                self.logger.warning("Force closing position %s", position.position_id)
                # Implement position closing logic

            # Remove strategy orders from history
            with self._order_lock:
                strategy_orders = [oid for oid, order in self.orders.items()
                                 if order.strategy_id == strategy_id]
                for order_id in strategy_orders:
                    del self.orders[order_id]

            # Call strategy cleanup if available
            strategy_info = self.strategies.get(strategy_id)
            if strategy_info and hasattr(strategy_info.class_instance, 'cleanup'):
                strategy_info.class_instance.cleanup()

        except Exception as e:
            self.logger.error("Strategy cleanup failed: %s", e)

    def _stop_all_strategies(self, reason: str):
        """Stop all active strategies"""
        for strategy_id in list(self.strategies.keys()):
            strategy_info = self.strategies[strategy_id]
            if strategy_info.state in [StrategyState.ACTIVE, StrategyState.PAUSED]:
                self._stop_strategy(strategy_id, reason)

    # ==========================================================================
    # SIGNAL PROCESSING
    # ==========================================================================

    def process_signal(self, strategy_id: str, signal: dict[str, Any]) -> bool:
        """
        Process a trading signal from a strategy.

        Args:
            strategy_id: Strategy identifier
            signal: Signal data dictionary

        Returns:
            bool: True if signal processed successfully
        """
        try:
            # Validate engine state
            if self.state != EngineState.RUNNING:
                self.logger.warning("Cannot process signal - engine state: %s", self.state)
                return False

            # Validate strategy
            strategy_info = self.strategies.get(strategy_id)
            if not strategy_info:
                self.logger.error("Strategy %s not found", strategy_id)
                return False

            if strategy_info.state != StrategyState.ACTIVE:
                self.logger.warning("Strategy %s not active: %s", strategy_id, strategy_info.state)
                return False

            # Check circuit breaker
            if self.circuit_breaker_state == CircuitBreakerState.TRIGGERED:
                self.logger.warning("Circuit breaker triggered - rejecting signal")
                return False

            # Validate signal
            if not self._validate_signal(signal):
                self.logger.error("Invalid signal from strategy %s", strategy_id)
                return False

            pipeline_ok, pipeline_reason = self._run_decision_flow_pipeline(strategy_id, signal)
            if not pipeline_ok:
                self.logger.warning(
                    "Signal rejected by decision flow pipeline (%s): %s",
                    strategy_id,
                    pipeline_reason,
                )
                return False

            # Update strategy metrics
            strategy_info.last_signal = datetime.now(UTC)
            strategy_info.signal_count += 1

            self.logger.info("Signal processed from %s: %s", strategy_id, signal.get('action', 'unknown'))  # noqa: E501

            # Emit signal event
            if self.event_manager:
                self.event_manager.emit(
                    EventType.STRATEGY_SIGNAL,
                    {
                        'strategy_id': strategy_id,
                        'signal': signal,
                        'order_id': None,
                        'timestamp': datetime.now(UTC)
                    }
                )

            return True

        except Exception as e:
            self.logger.error("Signal processing failed: %s", e)
            self.error_handler.handle_error(e, f"process_signal.{strategy_id}")
            self._increment_strategy_error(strategy_id, str(e))
            return False

    def _record_decision_flow_trace(self, trace: dict[str, Any]) -> None:
        """Store and publish decision-flow telemetry for auditability."""
        self._decision_flow_traces.append(trace)
        if not self.event_manager:
            return

        try:
            self.event_manager.emit(
                EventType.SYSTEM,
                {
                    'type': 'decision_flow_pipeline',
                    'payload': trace,
                    'timestamp': datetime.now(UTC),
                },
            )
        except Exception as exc:
            self.logger.debug("Decision flow telemetry emit failed: %s", exc)

    def _extract_signal_regime(
        self,
        signal: dict[str, Any],
        market_conditions: dict[str, Any],
    ) -> str:
        """Extract normalized regime label from signal metadata and market state."""
        metadata = signal.get('metadata') if isinstance(signal.get('metadata'), dict) else {}
        return str(
            signal.get('regime')
            or metadata.get('regime')
            or market_conditions.get('regime')
            or market_conditions.get('current_regime')
            or market_conditions.get('market_regime')
            or market_conditions.get('breadth_regime')
            or ''
        ).strip().lower()

    def _passes_data_gate(
        self,
        strategy_id: str,
        signal: dict[str, Any],
        market_conditions: dict[str, Any],
    ) -> tuple[bool, str]:
        """Gate 1: F09 data/market-structure checks."""
        entry_gate = self._get_entry_filter_gate()
        if entry_gate is None or not market_conditions:
            return True, ""

        metadata = signal.get('metadata') if isinstance(signal.get('metadata'), dict) else {}
        action = str(signal.get('action') or signal.get('side') or metadata.get('action') or '').strip().lower()  # noqa: E501
        params = {
            'strategy_type': signal.get('strategy_type') or metadata.get('strategy_type') or strategy_id,
            'position_type': signal.get('position_type') or metadata.get('position_type') or '',
            'direction': signal.get('direction') or metadata.get('direction') or signal.get('bias') or metadata.get('bias') or action,
            'action': action,
            'market_conditions': market_conditions,
            'event_clock_state': (
                signal.get('event_clock_state')
                or metadata.get('event_clock_state')
                or market_conditions.get('event_clock_state')
                or {}
            ),
            'current_time': datetime.now(UTC),
        }

        try:
            checks = []
            checks.extend(entry_gate._check_time_filters(params))
            checks.extend(entry_gate._check_data_quality_filter(params))
            checks.extend(entry_gate._check_vix_term_structure_filter())
            checks.extend(entry_gate._check_short_term_vol_stress_filter(params))
            if not self.lean_mode:
                checks.extend(entry_gate._check_vol_surface_structure_filter(params))
                checks.extend(entry_gate._check_dealer_flow_filter(params))
        except Exception as exc:
            self.logger.debug("A02: data gate failed open: %s", exc, exc_info=True)
            return True, ""

        failures = []
        for check in checks:
            result = getattr(check, 'result', None)
            if getattr(result, 'value', result) == 'fail':
                failures.append(str(getattr(check, 'message', 'data_gate_failed')))

        if failures:
            return False, '; '.join(failures)
        return True, ""

    def _passes_regime_gate(
        self,
        signal: dict[str, Any],
        market_conditions: dict[str, Any],
    ) -> tuple[bool, str]:
        """Gate 2: explicit crisis/event hard-halt + regime policy gate."""
        raw_regime = self._extract_signal_regime(signal, market_conditions)
        hard_halt_regimes = {'crisis', 'crisis_mode', 'event', 'event_transition'}
        if raw_regime in hard_halt_regimes:
            return False, f"regime_halt:{raw_regime}"
        return self._passes_regime_policy_gate(signal, market_conditions)

    def _passes_strategy_gate(self, strategy_id: str, signal: dict[str, Any]) -> tuple[bool, str]:
        """Gate 3: enforce permitted strategy set."""
        cfg = self.config.get('decision_flow', {})
        configured = cfg.get('permitted_strategies', []) if isinstance(cfg, dict) else []
        allowed_tokens = [
            str(token).strip().lower()
            for token in (configured or list(DEFAULT_PERMITTED_PIPELINE_STRATEGIES))
            if str(token).strip()
        ]
        if not allowed_tokens:
            return True, ""

        metadata = signal.get('metadata') if isinstance(signal.get('metadata'), dict) else {}
        strategy_name = str(
            signal.get('strategy_type')
            or signal.get('strategy_id')
            or metadata.get('strategy_type')
            or metadata.get('strategy_id')
            or strategy_id
        ).strip().lower()
        if not strategy_name:
            return False, "strategy_gate:missing_strategy"

        for token in allowed_tokens:
            if token in strategy_name:
                return True, ""
        return False, f"strategy_gate:not_permitted:{strategy_name}"

    def _passes_risk_gate(self, strategy_id: str, signal: dict[str, Any]) -> tuple[bool, str]:
        """Gate 4: max-concurrency + E01 risk validation + optional Greek caps."""
        active_strategies = [
            s for s in self.strategies.values()
            if s.state == StrategyState.ACTIVE
        ]
        if len(active_strategies) > self.max_concurrent_strategies:
            return (
                False,
                f"risk_gate:max_concurrent_strategies:{len(active_strategies)}/{self.max_concurrent_strategies}",
            )

        if self.has_risk_manager and not self._check_signal_risk(strategy_id, signal):
            return False, "risk_gate:risk_manager_reject"

        if self.has_risk_manager and hasattr(self.risk_manager, 'get_portfolio_greeks'):
            try:
                greeks = self.risk_manager.get_portfolio_greeks() or {}
            except Exception:
                greeks = {}

            greek_limits = self.config.get('portfolio_greek_limits', {})
            if isinstance(greek_limits, dict):
                for greek_name in ('delta', 'gamma', 'theta', 'vega'):
                    limit = greek_limits.get(greek_name)
                    greek_value = greeks.get(greek_name)
                    if limit is None or greek_value is None:
                        continue
                    if abs(float(greek_value)) > abs(float(limit)):
                        return False, f"risk_gate:greek_limit:{greek_name}:{greek_value}>{limit}"

        return True, ""

    def _queue_execution_from_signal(self, strategy_id: str, signal: dict[str, Any]) -> tuple[bool, str]:
        """Gate 5: enforce limit-order execution and enqueue the order."""
        execution_signal = dict(signal)
        execution_signal['order_type'] = signal.get('order_type', 'LIMIT')
        if str(execution_signal['order_type']).upper() != 'LIMIT':
            execution_signal['order_type'] = 'LIMIT'

        if execution_signal.get('price') is None:
            return False, 'execution_gate:missing_limit_price'

        order = self._create_order_from_signal(strategy_id, execution_signal)
        if not order:
            return False, 'execution_gate:order_create_failed'

        priority = 1 if signal.get('urgent', False) else 5
        self.order_queue.put((priority, order.order_id, order))
        return True, ""

    def _run_decision_flow_pipeline(
        self,
        strategy_id: str,
        signal: dict[str, Any],
        include_execution: bool = True,
    ) -> tuple[bool, str]:
        """Run strict gate order for each signal.

        When include_execution is False, only Data->Regime->Strategy->Risk
        gates are evaluated and no order is created/queued.
        """
        trace: dict[str, Any] = {
            'pipeline': 'decision_flow_v1',
            'strategy_id': strategy_id,
            'symbol': signal.get('symbol'),
            'timestamp': datetime.now(UTC).isoformat(),
            'gates': [],
        }

        market_conditions = self._get_current_market_conditions()

        gate_sequence = [
            ('data_gate', lambda: self._passes_data_gate(strategy_id, signal, market_conditions)),
            ('regime_gate', lambda: self._passes_regime_gate(signal, market_conditions)),
            ('strategy_gate', lambda: self._passes_strategy_gate(strategy_id, signal)),
            ('risk_gate', lambda: self._passes_risk_gate(strategy_id, signal)),
        ]
        if include_execution:
            gate_sequence.append(
                ('execution_gate', lambda: self._queue_execution_from_signal(strategy_id, signal))
            )

        for order, (gate_name, gate_fn) in enumerate(gate_sequence, start=1):
            gate_ok, gate_reason = gate_fn()
            trace['gates'].append(
                {
                    'order': order,
                    'name': gate_name,
                    'status': 'pass' if gate_ok else 'fail',
                    'reason': gate_reason,
                }
            )
            if not gate_ok:
                trace['result'] = 'halted'
                trace['halt_reason'] = f"{gate_name}:{gate_reason}"
                self._record_decision_flow_trace(trace)
                return False, trace['halt_reason']

        trace['result'] = 'executed' if include_execution else 'gates_passed'
        trace['halt_reason'] = ''
        self._record_decision_flow_trace(trace)
        return True, ""

    def _validate_signal(self, signal: dict[str, Any]) -> bool:
        """Validate signal has required fields"""
        required_fields = ['symbol', 'action', 'quantity']

        for field_name in required_fields:
            if field_name not in signal:
                self.logger.error("Signal missing required field: %s", field_name)
                return False

        # Validate action
        try:
            OrderAction(signal['action'])
        except (ValueError, KeyError):
            self.logger.error("Invalid order action: %s", signal['action'])
            return False

        # Validate quantity
        if not isinstance(signal['quantity'], (int, float)) or signal['quantity'] <= 0:
            self.logger.error("Invalid quantity: %s", signal['quantity'])
            return False

        return True

    def _check_signal_risk(self, strategy_id: str, signal: dict[str, Any]) -> bool:
        """Check signal against risk limits using the typed E00 Protocol boundary."""
        if not self.risk_manager:
            return True

        try:
            if RiskValidationRequest is not None and hasattr(self.risk_manager, 'validate_signal'):
                # Typed path: E00 Protocol boundary
                action_str = str(signal.get('action', 'BUY')).upper()
                signal_type = (
                    BoundarySignalType.SELL
                    if action_str in ('SELL', 'SELL_TO_OPEN', 'SELL_TO_CLOSE')
                    else BoundarySignalType.BUY
                )
                request = RiskValidationRequest(
                    symbol=signal['symbol'],
                    quantity=int(signal['quantity']),
                    signal_type=signal_type,
                    strategy_id=strategy_id,
                    entry_price=float(signal.get('price') or 0.0),
                    confidence=float(signal.get('confidence', 0.0)),
                    metadata={
                        **signal.get('metadata', {}),
                        'type': signal.get('type', 'stock'),
                        'value': signal.get('value', 0),
                        'existing_positions': len(self._get_strategy_positions(strategy_id)),
                    },
                )
                result = self.risk_manager.validate_signal(request)
                approved = bool(result.approved) if hasattr(result, 'approved') else bool(result.get('approved', False))  # noqa: E501
                if not approved:
                    reason = getattr(result, 'rejection_reason', None) or result.get('reason', 'Unknown')  # noqa: E501
                    self.logger.warning("Risk check failed: %s", reason)
                return approved
            else:
                # Fallback: legacy dict adapter for environments missing E00
                risk_check = {
                    'strategy_id': strategy_id,
                    'symbol': signal['symbol'],
                    'action': signal['action'],
                    'quantity': signal['quantity'],
                    'price': signal.get('price'),
                    'metadata': signal.get('metadata', {}),
                }
                result = self.risk_manager.check_trade(risk_check)
                if not result.get('approved', False):
                    self.logger.warning("Risk check failed: %s", result.get('reason', 'Unknown'))
                    return False
                return True

        except Exception as e:
            self.logger.error("Risk check error: %s", e)
            # Fail safe — reject on error
            return False

    def _get_entry_filter_gate(self) -> Any | None:
        """Lazily build the F09 gate used for market-structure trust checks."""
        if self._entry_filter_gate is not None:
            return self._entry_filter_gate

        try:
            from Tradov.TradovF_Analysis.TradovF09_EntryFilters import EntryFilters
        except ImportError:
            try:
                from TradovF_Analysis.TradovF09_EntryFilters import EntryFilters  # type: ignore[no-redef]
            except ImportError:
                self.logger.debug("A02: EntryFilters unavailable for trust gate")
                return None

        config_manager = None
        try:
            from Tradov.TradovA_Core.TradovA03_Configuration import get_config_manager
            config_manager = get_config_manager()
        except Exception:
            config_manager = None

        if config_manager is None:
            class _ConfigAdapter:
                def __init__(self, config: dict[str, Any]):
                    self._config = config or {}

                def get_config(self, key: str, default: Any = None) -> Any:
                    value: Any = self._config
                    for part in key.split('.'):
                        if not isinstance(value, dict) or part not in value:
                            return default
                        value = value[part]
                    return value

                def is_feature_enabled(self, key: str) -> bool:
                    features = self._config.get('features', {})
                    if isinstance(features, dict):
                        return bool(features.get(key, False))
                    return False

                def get(self, key: str, default: Any = None) -> Any:
                    return self.get_config(key, default)

            config_manager = _ConfigAdapter(self.config)

        try:
            self._entry_filter_gate = EntryFilters(config_manager)
        except Exception as exc:
            self.logger.debug("A02: failed to initialize EntryFilters trust gate: %s", exc)
            self._entry_filter_gate = None
        return self._entry_filter_gate

    def _get_current_market_conditions(self) -> dict[str, Any]:
        """Fetch the latest S07 market conditions for trust-policy gating."""
        if self._metrics_orchestrator is None:
            try:
                from Tradov.TradovS_Signals.TradovS07_CustomMetricsOrchestrator import get_metrics_orchestrator  # noqa: E501
            except ImportError:
                try:
                    from TradovS_Signals.TradovS07_CustomMetricsOrchestrator import get_metrics_orchestrator  # type: ignore[no-redef]  # noqa: E501
                except ImportError:
                    self.logger.debug("A02: S07 metrics orchestrator unavailable")
                    return {}

            try:
                self._metrics_orchestrator = get_metrics_orchestrator()
            except Exception as exc:
                self.logger.debug("A02: failed to get S07 metrics orchestrator: %s", exc)
                return {}

        try:
            conditions = self._metrics_orchestrator.get_current_market_conditions()
        except Exception as exc:
            self.logger.debug("A02: failed to read S07 market conditions: %s", exc)
            return {}

        return conditions if isinstance(conditions, dict) else {}

    def _passes_entry_trust_gate(self, strategy_id: str, signal: dict[str, Any]) -> tuple[bool, str]:  # noqa: E501
        """Apply F09 trust-policy checks to direct A02 signal processing."""
        entry_gate = self._get_entry_filter_gate()
        if entry_gate is None:
            return True, ""

        market_conditions = self._get_current_market_conditions()
        if not market_conditions:
            return True, ""

        metadata = signal.get('metadata') if isinstance(signal.get('metadata'), dict) else {}
        action = str(signal.get('action') or signal.get('side') or metadata.get('action') or '').strip().lower()  # noqa: E501
        params = {
            'strategy_type': signal.get('strategy_type') or metadata.get('strategy_type') or strategy_id,  # noqa: E501
            'position_type': signal.get('position_type') or metadata.get('position_type') or '',
            'direction': signal.get('direction') or metadata.get('direction') or signal.get('bias') or metadata.get('bias') or action,  # noqa: E501
            'action': action,
            'market_conditions': market_conditions,
            'event_clock_state': (
                signal.get('event_clock_state')
                or metadata.get('event_clock_state')
                or market_conditions.get('event_clock_state')
                or {}
            ),
            'current_time': datetime.now(UTC),
        }

        try:
            checks = []
            checks.extend(entry_gate._check_time_filters(params))
            if self.lean_mode:
                checks.extend(entry_gate._check_data_quality_filter(params))
                checks.extend(entry_gate._check_short_term_vol_stress_filter(params))
                checks.extend(entry_gate._check_vix_term_structure_filter())
            else:
                checks.extend(entry_gate._check_data_quality_filter(params))
                checks.extend(entry_gate._check_vol_surface_structure_filter(params))
                checks.extend(entry_gate._check_dealer_flow_filter(params))
                checks.extend(entry_gate._check_vix_term_structure_filter())
                checks.extend(entry_gate._check_short_term_vol_stress_filter(params))
        except Exception as exc:
            self.logger.debug("A02: trust gate failed open: %s", exc, exc_info=True)
            return True, ""

        failures = []
        for check in checks:
            result = getattr(check, 'result', None)
            if getattr(result, 'value', result) == 'fail':
                failures.append(check)

        if not failures:
            return self._passes_regime_policy_gate(signal, market_conditions)

        return False, '; '.join(str(check.message) for check in failures)

    def _resolve_lean_mode(self) -> bool:
        """Resolve lean-mode flag from env, local config, or A03 config manager."""
        env = os.environ.get("TRADOV_LEAN_MODE")
        if env is not None:
            return env.strip().lower() == "true"

        candidate = self.config.get("autonomous_readiness", {})
        if isinstance(candidate, dict) and "lean_mode" in candidate:
            return bool(candidate.get("lean_mode", True))
        if "lean_mode" in self.config:
            return bool(self.config.get("lean_mode", True))

        try:
            from Tradov.TradovA_Core.TradovA03_Configuration import get_config_manager
            cfg = get_config_manager()
            return bool(cfg.get("autonomous_readiness.lean_mode", True))
        except Exception:
            return True

    def _get_regime_policy(self) -> dict[str, Any]:
        """Load six-regime policy from config manager or repo config file."""
        if self._regime_policy is not None:
            return self._regime_policy

        policy: dict[str, Any] = {}

        # Prefer centralized config manager payload when available.
        try:
            from Tradov.TradovA_Core.TradovA03_Configuration import get_config_manager
            cfg = get_config_manager()
            candidate = cfg.get('autonomous_readiness.regime_policy', {})
            if isinstance(candidate, dict):
                policy = candidate
        except Exception:
            policy = {}

        # Fallback to repository policy file created for autonomous gating.
        if not policy:
            policy_path = Path(__file__).resolve().parents[2] / 'config' / 'regime_policy.json'
            try:
                policy = json.loads(policy_path.read_text(encoding='utf-8'))
            except Exception:
                policy = {}

        self._regime_policy = policy if isinstance(policy, dict) else {}
        return self._regime_policy

    def _passes_regime_policy_gate(
        self,
        signal: dict[str, Any],
        market_conditions: dict[str, Any],
    ) -> tuple[bool, str]:
        """Apply conservative regime-policy blocks (fail-open on missing context)."""
        policy = self._get_regime_policy()
        regimes = policy.get('regimes', {}) if isinstance(policy, dict) else {}
        if not isinstance(regimes, dict) or not regimes:
            return True, ""

        metadata = signal.get('metadata') if isinstance(signal.get('metadata'), dict) else {}
        raw_regime = str(
            signal.get('regime')
            or metadata.get('regime')
            or market_conditions.get('regime')
            or market_conditions.get('current_regime')
            or market_conditions.get('market_regime')
            or market_conditions.get('breadth_regime')
            or ''
        ).strip().lower()
        if not raw_regime:
            return True, ""

        regime_aliases = {
            'bull': 'bull_trend',
            'strong_bull': 'bull_trend',
            'bear': 'bear_trend',
            'strong_bear': 'bear_trend',
            'neutral': 'range_calm',
            'bull_low_vol': 'bull_trend',
            'bull_high_vol': 'high_vol_mean_reversion',
            'bear_low_vol': 'bear_trend',
            'bear_high_vol': 'crisis_turbulent',
            'sideways_low_vol': 'range_calm',
            'sideways_high_vol': 'high_vol_mean_reversion',
            'crisis': 'crisis_turbulent',
            'recovery': 'event_transition',
        }
        regime_key = raw_regime if raw_regime in regimes else regime_aliases.get(raw_regime, '')
        regime_cfg = regimes.get(regime_key, {}) if regime_key else {}
        if not isinstance(regime_cfg, dict) or not regime_cfg:
            return True, ""

        hard_blocks = regime_cfg.get('hard_blocks', {})
        if isinstance(hard_blocks, dict) and bool(hard_blocks.get('no_trade', False)):
            return False, f"regime_policy:no_trade:{regime_key}"

        strategy_name = str(
            signal.get('strategy_type')
            or signal.get('strategy_id')
            or metadata.get('strategy_type')
            or metadata.get('strategy_id')
            or ''
        ).strip().lower()

        allowed = regime_cfg.get('allowed_strategies', [])
        if isinstance(allowed, list) and allowed:
            if not strategy_name:
                return False, f"regime_policy:missing_strategy:{regime_key}"

            allow_match = False
            for token in allowed:
                token_str = str(token).strip().lower()
                if token_str and token_str in strategy_name:
                    allow_match = True
                    break
            if not allow_match:
                return False, f"regime_policy:not_allowed_strategy:{strategy_name}:{regime_key}"

        if strategy_name:
            blocked = regime_cfg.get('blocked_strategies', [])
            if isinstance(blocked, list):
                for token in blocked:
                    token_str = str(token).strip().lower()
                    if token_str and token_str in strategy_name:
                        return False, f"regime_policy:blocked_strategy:{token_str}:{regime_key}"

        return True, ""

    def _create_order_from_signal(self, strategy_id: str, signal: dict[str, Any]) -> OrderInfo | None:  # noqa: E501
        """Create order object from signal"""
        try:
            order_id = f"{strategy_id}_{uuid.uuid4().hex[:8]}"

            # Handle order type
            order_type_value = signal.get('order_type', 'MARKET')
            if isinstance(order_type_value, str):
                order_type = OrderType(order_type_value)
            else:
                order_type = order_type_value

            # Handle action
            action_value = signal['action']
            if isinstance(action_value, str):
                action = OrderAction(action_value)
            else:
                action = action_value

            order = OrderInfo(
                order_id=order_id,
                strategy_id=strategy_id,
                symbol=signal['symbol'],
                action=action,
                order_type=order_type,
                quantity=int(signal['quantity']),
                price=signal.get('price'),
                metadata=signal.get('metadata', {})
            )

            # Store order
            with self._order_lock:
                self.orders[order_id] = order

            return order

        except Exception as e:
            self.logger.error("Order creation failed: %s", e)
            return None

    # ==========================================================================
    # POSITION MANAGEMENT
    # ==========================================================================

    def _get_strategy_positions(self, strategy_id: str) -> list[PositionInfo]:
        """Get all positions for a strategy"""
        with self._position_lock:
            return [pos for pos in self.positions.values()
                   if pos.strategy_id == strategy_id]

    # ==========================================================================
    # CIRCUIT BREAKER
    # ==========================================================================

    def _reset_circuit_breaker_metrics(self):
        """Reset circuit breaker metrics"""
        with self._circuit_breaker_lock:
            self.circuit_breaker_metrics = {
                'loss_per_minute': 0.0,
                'orders_per_minute': 0,
                'errors_per_hour': 0,
                'daily_loss': 0.0,
                'triggered_at': None,
                'recovery_at': None,
                'last_reset': datetime.now(UTC)
            }

    # ==========================================================================
    # MONITORING AND HEALTH
    # ==========================================================================

    def _start_monitoring(self):
        """Start monitoring thread"""
        self._monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            name="EngineMonitor",
            daemon=True
        )
        self._monitor_thread.start()

    def _monitoring_loop(self):
        """Main monitoring loop"""
        self.logger.info("Engine monitor started")

        while not self._shutdown_event.is_set():
            try:
                # Perform health check
                if (datetime.now(UTC) - self.last_health_check).total_seconds() > HEALTH_CHECK_INTERVAL:  # noqa: E501
                    self._perform_health_check()
                    self.last_health_check = datetime.now(UTC)

                # Sleep
                self._shutdown_event.wait(10)

            except Exception as e:
                self.logger.error("Monitoring error: %s", e)
                self.error_handler.handle_error(e, "monitoring_loop")

    def _perform_health_check(self):
        """Perform comprehensive health check"""
        try:
            # Basic health metrics
            health_status = {
                'state': self.state.name,
                'active_strategies': len([s for s in self.strategies.values()
                                       if s.state == StrategyState.ACTIVE]),
                'open_orders': len([o for o in self.orders.values()
                                  if o.state in [OrderState.PENDING, OrderState.SUBMITTED]]),
                'open_positions': len(self.positions),
                'circuit_breaker': self.circuit_breaker_state.name
            }

            self.logger.info("Health check: %s", health_status)

        except Exception as e:
            self.logger.error("Health check failed: %s", e)

    def get_health_status(self) -> dict[str, Any]:
        """Get current health status"""
        try:
            return {
                'state': self.state.name,
                'uptime': str(datetime.now(UTC) - self.start_time) if self.start_time else None,
                'active_strategies': len([s for s in self.strategies.values()
                                       if s.state == StrategyState.ACTIVE]),
                'total_strategies': len(self.strategies),
                'open_orders': len([o for o in self.orders.values()
                                  if o.state in [OrderState.PENDING, OrderState.SUBMITTED]]),
                'open_positions': len(self.positions),
                'circuit_breaker': self.circuit_breaker_state.name,
                'has_risk_manager': self.has_risk_manager,
                'has_order_manager': self.has_order_manager,
                'has_position_tracker': self.has_position_tracker,
                'performance': {
                    'total_pnl': self.performance.total_pnl,
                    'win_rate': self.performance.win_rate,
                    'sharpe_ratio': self.performance.sharpe_ratio
                }
            }
        except Exception as e:
            self.logger.error("Error getting health status: %s", e)
            return {'error': str(e)}

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================

    def _validate_configuration(self) -> bool:
        """Validate engine configuration"""
        try:
            # Check required configuration
            if not self.config:
                self.logger.warning("No configuration provided, using defaults")

            # Validate numeric limits
            if self.max_strategies <= 0:
                self.logger.error("Invalid max_strategies")
                return False

            if self.max_orders_per_minute <= 0:
                self.logger.error("Invalid max_orders_per_minute")
                return False

            return True

        except Exception as e:
            self.logger.error("Configuration validation failed: %s", e)
            return False

    def _setup_event_handlers(self):
        """Set up event handlers"""
        try:
            if self.event_manager:
                # Order events
                self.event_manager.subscribe(EventType.ORDER_FILLED, self._on_order_filled)
                self.event_manager.subscribe(EventType.ORDER_CANCELLED, self._on_order_cancelled)

                # Position events
                self.event_manager.subscribe(EventType.POSITION_UPDATE, self._on_position_update)

                # System events
                self.event_manager.subscribe(EventType.SYSTEM_ERROR, self._on_system_error)

                self.logger.info("Event handlers registered")

        except Exception as e:
            self.logger.error("Event handler setup failed: %s", e)

    def _on_order_filled(self, event):
        """Handle order filled event"""
        try:
            if not event:
                return

            order_id = event.data.get('order_id') if hasattr(event, 'data') else event.get('order_id')  # noqa: E501

            order = self.orders.get(order_id)
            if order:
                order.state = OrderState.FILLED
                order.filled_at = datetime.now(UTC)

                # Update performance
                self.performance.successful_orders += 1

        except Exception as e:
            self.logger.error("Order filled handler error: %s", e)

    def _on_order_cancelled(self, event):
        """Handle order cancelled event"""
        try:
            if not event:
                return

            order_id = event.data.get('order_id') if hasattr(event, 'data') else event.get('order_id')  # noqa: E501

            order = self.orders.get(order_id)
            if order:
                order.state = OrderState.CANCELLED

        except Exception as e:
            self.logger.error("Order cancelled handler error: %s", e)

    def _on_position_update(self, event):
        """Handle position update event"""
        try:
            # Implementation depends on position tracking
            pass

        except Exception as e:
            self.logger.error("Position update handler error: %s", e)

    def _on_system_error(self, event):
        """Handle system error event"""
        try:
            # Update error metrics
            self.circuit_breaker_metrics['errors_per_hour'] += 1

        except Exception as e:
            self.logger.error("System error handler error: %s", e)

    def _initialize_performance_tracking(self):
        """Initialize performance tracking systems"""
        self.performance = PerformanceMetrics()
        self.performance_history.clear()

    def _increment_strategy_error(self, strategy_id: str, error: str):
        """Increment strategy error count"""
        if strategy_id in self.strategies:
            strategy = self.strategies[strategy_id]
            strategy.error_count += 1
            strategy.last_error = error

            # Check if strategy should be disabled
            if strategy.error_count > 10:
                self.logger.error("Strategy %s disabled due to excessive errors", strategy_id)
                strategy.state = StrategyState.ERROR

    def _start_worker_threads(self):
        """Start all worker threads"""
        self._start_order_processor()
        self._start_monitoring()

    def _start_order_processor(self):
        """Start order processing thread"""
        self._order_processor_thread = threading.Thread(
            target=self._order_processor_loop,
            name="OrderProcessor",
            daemon=True
        )
        self._order_processor_thread.start()

    def _order_processor_loop(self):
        """Main order processing loop — dequeues OrderInfo items and submits them to the broker."""
        self.logger.info("Order processor started")

        while not self._shutdown_event.is_set():
            try:
                # Get order from queue with timeout
                priority, order_id, order = self.order_queue.get(timeout=1.0)

                self.logger.info(
                    "Processing order %s: %s %d x %s",
                    order_id, order.action.value, order.quantity, order.symbol,
                )
                self._submit_order_to_broker(order)

            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error("Order processor error: %s", e, exc_info=True)

    def _submit_order_to_broker(self, order: "OrderInfo") -> None:
        """Convert an internal OrderInfo and submit it to the broker layer.

        Tries self.order_manager (B02 OrderManager) first; falls back to
        self.tradov_client (B40 TradierClient) if order_manager is unavailable.

        Args:
            order: The OrderInfo instance to submit.
        """
        try:
            # ------------------------------------------------------------------
            # Path 1: B02 OrderManager (preferred — wraps B40, handles retries)
            # ------------------------------------------------------------------
            if self.order_manager is not None and hasattr(self.order_manager, "submit_order"):
                try:
                    try:
                        from Tradov.TradovB_Broker.TradovB02_OrderManager import Order as B02Order
                    except ImportError:
                        from TradovB_Broker.TradovB02_OrderManager import Order as B02Order

                    b02_order = B02Order(
                        order_id=order.order_id,
                        symbol=order.symbol,
                        side=order.action.value.lower(),        # "buy" | "sell"
                        order_type=order.order_type.value.lower(),  # "market" | "limit" | "stop"
                        quantity=order.quantity,
                        price=order.price,
                        strategy_name=order.strategy_id,
                    )
                    result = self.order_manager.submit_order(b02_order)
                    if result.success:
                        self.logger.info(
                            "Order %s submitted — Tradier id=%s",
                            order.order_id, result.tradier_order_id,
                        )
                        order.state = OrderState.SUBMITTED
                        order.submitted_at = datetime.now(UTC)
                    else:
                        self.logger.error(
                            "Order %s rejected by broker: %s",
                            order.order_id, result.message,
                        )
                        order.state = OrderState.REJECTED
                        order.error_message = result.message
                    return
                except Exception as b02_exc:
                    self.logger.warning(
                        "B02 submission failed for %s — falling back to tradov_client: %s",
                        order.order_id, b02_exc,
                    )

            # ------------------------------------------------------------------
            # Path 2: B40 TradierClient direct (fallback)
            # ------------------------------------------------------------------
            if self.tradov_client is not None and hasattr(self.tradov_client, "place_order"):
                try:
                    try:
                        from Tradov.TradovB_Broker.TradovB40_TradierClient import (
                            OrderSide, OrderType as B40OrderType,
                        )
                    except ImportError:
                        from TradovB_Broker.TradovB40_TradierClient import (
                            OrderSide, OrderType as B40OrderType,
                        )

                    side_map = {
                        "BUY": OrderSide.BUY,
                        "SELL": OrderSide.SELL,
                    }
                    otype_map = {
                        "MARKET": B40OrderType.MARKET,
                        "LIMIT": B40OrderType.LIMIT,
                        "STOP": B40OrderType.STOP,
                    }
                    side = side_map.get(order.action.value, OrderSide.BUY)
                    otype = otype_map.get(order.order_type.value, B40OrderType.MARKET)
                    limit_price = (
                        order.price if order.order_type.value in ("LIMIT", "STOP_LIMIT") else None
                    )

                    response = self.tradov_client.place_order(
                        symbol=order.symbol,
                        side=side,
                        quantity=order.quantity,
                        order_type=otype,
                        limit_price=limit_price,
                    )
                    self.logger.info(
                        "Order %s submitted via B40: %s", order.order_id, response,
                    )
                    order.state = OrderState.SUBMITTED
                    order.submitted_at = datetime.now(UTC)
                    return
                except Exception as b40_exc:
                    self.logger.error(
                        "B40 direct submission failed for %s: %s",
                        order.order_id, b40_exc, exc_info=True,
                    )

            # ------------------------------------------------------------------
            # No broker client available
            # ------------------------------------------------------------------
            self.logger.error(
                "No broker client available — cannot submit order %s", order.order_id,
            )
            order.state = OrderState.ERROR
            order.error_message = "No broker client configured"

        except Exception as exc:
            self.logger.error(
                "Failed to submit order %s: %s", order.order_id, exc, exc_info=True,
            )
            order.state = OrderState.ERROR
            order.error_message = str(exc)

    def _stop_worker_threads(self):
        """Stop all worker threads"""
        self._shutdown_event.set()

        # Wait for threads to finish
        threads = [
            self._order_processor_thread,
            self._monitor_thread
        ]

        for thread in threads:
            if thread and thread.is_alive():
                thread.join(timeout=5)

    def _cancel_all_pending_orders(self, reason: str):
        """Cancel all pending orders"""
        with self._order_lock:
            pending_orders = [order for order in self.orders.values()
                            if order.state in [OrderState.PENDING, OrderState.SUBMITTED]]

        for order in pending_orders:
            self._cancel_order(order.order_id, reason)

    def _cancel_strategy_orders(self, strategy_id: str, reason: str):
        """Cancel all orders for a strategy"""
        with self._order_lock:
            strategy_orders = [order for order in self.orders.values()
                             if order.strategy_id == strategy_id and
                             order.state in [OrderState.PENDING, OrderState.SUBMITTED]]

        for order in strategy_orders:
            self._cancel_order(order.order_id, reason)

    def _cancel_order(self, order_id: str, reason: str) -> bool:
        """Cancel a specific order"""
        try:
            order = self.orders.get(order_id)
            if not order:
                return False

            if order.state not in [OrderState.PENDING, OrderState.SUBMITTED]:
                self.logger.warning("Cannot cancel order %s in state %s", order_id, order.state)
                return False

            # Update order state
            order.state = OrderState.CANCELLED
            order.metadata['cancel_reason'] = reason

            self.logger.info("Order %s cancelled: %s", order_id, reason)
            return True

        except Exception as e:
            self.logger.error("Order cancellation failed: %s", e)
            return False

    def _save_state(self):
        """Save engine state to disk"""
        try:
            state_data = {
                'version': '2.0',
                'timestamp': datetime.now(UTC),
                'engine_state': self.state.name,
                'performance': asdict(self.performance)
            }

            # Save to file
            joblib.dump(state_data, self._state_file)

            self.logger.debug("Engine state saved")

        except Exception as e:
            self.logger.error("State save failed: %s", e)

    def _load_state(self):
        """Load engine state from disk"""
        try:
            if not self._state_file.exists():
                return

            state_data = joblib.load(self._state_file)

            # Restore performance metrics
            if 'performance' in state_data:
                for key, value in state_data['performance'].items():
                    if hasattr(self.performance, key) and not key.startswith('_'):
                        setattr(self.performance, key, value)

            self.logger.info("Engine state loaded from disk")

        except Exception as e:
            self.logger.error("State load failed: %s", e)

    def _cleanup_resources(self):
        """Clean up all resources"""
        try:
            # Stop monitoring
            if self.has_risk_manager and self.risk_manager:
                self.risk_manager.stop_monitoring()

            # Clear queues
            while not self.order_queue.empty():
                try:
                    self.order_queue.get_nowait()
                except queue.Empty:
                    break

            self.logger.info("Resources cleaned up")

        except Exception as e:
            self.logger.error("Resource cleanup failed: %s", e)

    def get_state(self) -> dict[str, Any]:
        """Get current engine state for external persistence"""
        return {
            'state': self.state.name,
            'strategies': len(self.strategies),
            'active_strategies': len([s for s in self.strategies.values()
                                    if s.state == StrategyState.ACTIVE]),
            'open_orders': len([o for o in self.orders.values()
                              if o.state in [OrderState.PENDING, OrderState.SUBMITTED]]),
            'open_positions': len(self.positions),
            'total_pnl': self.performance.total_pnl,
            'circuit_breaker': self.circuit_breaker_state.name
        }


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_trading_engine(config: dict[str, Any], tradov_client, event_manager) -> TradingEngine:
    """
    Factory function to create a TradingEngine instance.

    Args:
        config: Engine configuration
        tradov_client: Broker client instance
        event_manager: Event management system

    Returns:
        TradingEngine instance
    """
    return TradingEngine(config, tradov_client, event_manager)


# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# Module-level singleton instance
_engine_instance: TradingEngine | None = None
_engine_lock = Lock()


def get_trading_engine(
    config: dict[str, Any] = None,
    tradov_client = None,
    event_manager = None
) -> TradingEngine:
    """
    Get singleton TradingEngine instance.

    Args:
        config: Engine configuration (required for first call)
        tradov_client: Broker client (required for first call)
        event_manager: Event manager (required for first call)

    Returns:
        TradingEngine instance
    """
    global _engine_instance

    with _engine_lock:
        if _engine_instance is None:
            if not all([config, tradov_client, event_manager]):
                raise ValueError("All parameters required for first engine creation")
            _engine_instance = TradingEngine(config, tradov_client, event_manager)

        return _engine_instance


def reset_trading_engine():
    """Reset the singleton engine instance (for testing)."""
    global _engine_instance
    with _engine_lock:
        if _engine_instance and _engine_instance.state == EngineState.RUNNING:
            _engine_instance.stop("Engine reset")
        _engine_instance = None


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code

    # Mock configuration
    test_config = {
        'max_strategies': 10,
        'max_orders_per_minute': 50,
        'enable_circuit_breaker': True,
        'portfolio_value': 100000.0,
        'circuit_breaker': {
            'max_loss_per_minute': 500,
            'max_daily_loss': 2000
        }
    }

    # Mock dependencies
    class MockTradovClient:
        def is_connected(self):
            return True

        def place_order(self, order):
            return {'order_id': f"MOCK_{uuid.uuid4().hex[:8]}"}

        def cancel_order(self, order_id):
            return True

    class MockEventManager:
        def emit(self, event_type, data):
            pass

        def subscribe(self, event_type, handler):
            pass

        def start(self):
            pass

        def stop(self):
            pass

    # Create test instances
    mock_client = MockTradovClient()
    mock_event_manager = MockEventManager()
    mock_event_manager.start()

    # Create engine
    engine = TradingEngine(test_config, mock_client, mock_event_manager)

    if engine.initialize():

        # Test risk manager integration
        if get_risk_manager:
            risk_mgr = get_risk_manager(100000.0, test_config)
            if risk_mgr.initialize():
                if engine.set_risk_manager(risk_mgr):
                    pass
                else:
                    pass

        # Test basic functionality
        status = engine.get_health_status()
        for _key, value in status.items():
            if isinstance(value, dict):
                for _k, _v in value.items():
                    pass
            else:
                pass

        if engine.start():

            # Let it run briefly
            time.sleep(2)

            # Test pause/resume
            if engine.pause("Test pause"):
                time.sleep(1)

                if engine.resume():
                    pass

            # Stop engine
            if engine.stop("Test completed"):
                pass
            else:
                pass
        else:
            pass

        # Shutdown
        engine.shutdown()
    else:
        pass

    # Stop event manager
    mock_event_manager.stop()

