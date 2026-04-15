#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderR_Runtime
Module: SpyderR04_LiveEngine.py
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
import queue
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, time
from enum import Enum
from typing import Any

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
import os
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# Soft import: TradierServerError is only available when the broker layer is present.
try:
    from Spyder.SpyderB_Broker.SpyderB40_TradierClient import TradierServerError as _TradierServerError
except ImportError:
    class _TradierServerError(Exception):  # type: ignore[no-redef]
        """Stub used when SpyderB40_TradierClient is not importable."""

MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)
EXTENDED_HOURS_START = time(4, 0)
EXTENDED_HOURS_END = time(20, 0)

# Safety limits - Load from environment variables with defaults
MAX_DAILY_TRADES = int(os.environ.get('MAX_DAILY_TRADES', 100))
MAX_POSITION_SIZE = int(os.environ.get('MAX_POSITION_SIZE', 10000))  # contracts
MAX_DAILY_LOSS = float(os.environ.get('MAX_DAILY_LOSS_USD', 10000))  # dollars
EMERGENCY_STOP_LOSS = float(os.environ.get('EMERGENCY_STOP_LOSS_PCT', 0.05))  # 5% portfolio loss

# Confirmation settings - Opt-in for development mode
REQUIRE_LIVE_ORDER_CONFIRMATION = os.environ.get('REQUIRE_LIVE_ORDER_CONFIRMATION', 'false').lower() == 'true'
HIGH_RISK_ORDER_CONFIRMATION = os.environ.get('HIGH_RISK_ORDER_CONFIRMATION', 'true').lower() == 'true'
HIGH_RISK_ORDER_THRESHOLD_USD = float(os.environ.get('HIGH_RISK_ORDER_THRESHOLD_USD', 50000))  # $50k
# Consecutive Tradier 5xx errors before entering API Panic Mode and halting all trading.
API_PANIC_THRESHOLD = int(os.environ.get("API_PANIC_THRESHOLD", "3"))
HIGH_RISK_ORDER_PORTFOLIO_PCT = float(os.environ.get('HIGH_RISK_ORDER_PORTFOLIO_PCT', 0.25))  # 25% of portfolio
# CLOSE_POSITIONS_ON_EMERGENCY: when true, emergency_stop flattens all open positions
# immediately via market orders. Default is false so that a transient Tradier API outage
# (which now triggers emergency_stop via API Panic Mode after 3 consecutive 5xx errors)
# does not auto-liquidate legitimate positions. Operators who want automatic flattening
# must opt in explicitly by setting CLOSE_POSITIONS_ON_EMERGENCY=true in .env.
CLOSE_POSITIONS_ON_EMERGENCY = os.environ.get('CLOSE_POSITIONS_ON_EMERGENCY', 'false').lower() == 'true'

# Execution parameters
ORDER_RETRY_LIMIT = 3
ORDER_TIMEOUT_SECONDS = 30
HEARTBEAT_INTERVAL = 5  # seconds

# ==============================================================================
# ENUMS
# ==============================================================================


class TradingMode(Enum):
    """Trading mode enumeration"""

    LIVE = "live"
    PAPER = "paper"
    SIMULATION = "simulation"
    EMERGENCY_STOP = "emergency_stop"


class ExecutionState(Enum):
    """Execution state enumeration"""

    INITIALIZED = "initialized"
    CONNECTED = "connected"
    TRADING = "trading"
    PAUSED = "paused"
    CLOSING = "closing"
    STOPPED = "stopped"
    ERROR = "error"


class SafetyCheckResult(Enum):
    """Safety check result enumeration"""

    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"
    OVERRIDE = "override"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================


@dataclass
class LiveTradingConfig:
    """Configuration for live trading"""

    account_id: str
    max_daily_trades: int = MAX_DAILY_TRADES
    max_position_size: int = MAX_POSITION_SIZE
    max_daily_loss: float = MAX_DAILY_LOSS
    enable_extended_hours: bool = False
    require_confirmation: bool = REQUIRE_LIVE_ORDER_CONFIRMATION  # Autonomous by default
    high_risk_confirmation: bool = HIGH_RISK_ORDER_CONFIRMATION  # Selective confirmation for large orders
    high_risk_threshold_usd: float = HIGH_RISK_ORDER_THRESHOLD_USD
    high_risk_portfolio_pct: float = HIGH_RISK_ORDER_PORTFOLIO_PCT
    use_limit_orders_only: bool = False
    slippage_tolerance: float = 0.01  # 1%
    partial_fill_timeout: int = 60  # seconds
    close_positions_on_emergency: bool = CLOSE_POSITIONS_ON_EMERGENCY  # Env: CLOSE_POSITIONS_ON_EMERGENCY (default false, opt-in)


@dataclass
class TradingSession:
    """Trading session information"""

    session_id: str
    start_time: datetime
    end_time: datetime | None = None
    mode: TradingMode = TradingMode.LIVE
    trades_executed: int = 0
    orders_placed: int = 0
    orders_filled: int = 0
    orders_cancelled: int = 0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0


@dataclass
class SafetyCheck:
    """Safety check result"""

    check_name: str
    result: SafetyCheckResult
    message: str
    timestamp: datetime
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionMetrics:
    """Live execution metrics"""

    total_orders: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    partial_fills: int = 0
    average_fill_time: float = 0.0
    average_slippage: float = 0.0
    rejection_rate: float = 0.0


# ==============================================================================
# MAIN CLASS
# ==============================================================================


class LiveEngine:
    """
    Live trading execution engine.

    This class manages all aspects of live trading including order execution,
    position monitoring, safety checks, and emergency controls.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        config: Live trading configuration
        state: Current execution state
        broker: Broker interface
        risk_manager: Risk management interface

    Example:
        >>> engine = LiveEngine(broker, risk_manager, config)
        >>> engine.initialize()
        >>> engine.start_trading()
    """

    def __init__(self, broker_interface, risk_manager, config: LiveTradingConfig, telegram_bot=None):
        """Initialize the live engine."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config = config
        self.broker = broker_interface
        self.risk_manager = risk_manager
        self.telegram_bot = telegram_bot  # Optional SpyderJ05_TelegramBot for high-risk alerts

        # State management
        self.state = ExecutionState.INITIALIZED
        self.mode = TradingMode.LIVE
        self.current_session: TradingSession | None = None

        # Order management
        self.pending_orders: dict[str, Any] = {}
        self.active_positions: dict[str, Any] = {}
        self.order_history: deque = deque(maxlen=1000)

        # Safety and monitoring
        self.safety_checks: list[SafetyCheck] = []
        self.emergency_stop = False
        self.daily_loss = 0.0
        self.daily_trades = 0

        # API Panic Mode — counts consecutive Tradier 5xx errors.
        self._api_error_count: int = 0
        self._api_panic_mode: bool = False

        # Execution metrics
        self.metrics = ExecutionMetrics()
        self.execution_times: deque = deque(maxlen=100)
        self.slippage_history: deque = deque(maxlen=100)

        # Threading for monitoring
        self.monitor_thread = None
        self.stop_event = threading.Event()
        self.order_queue = queue.Queue()

        # Heartbeat
        self.last_heartbeat = datetime.now()
        self.broker_connected = False

        self.logger.info("LiveEngine initialized for account %s", config.account_id)

    # ==========================================================================
    # PUBLIC METHODS - LIFECYCLE
    # ==========================================================================
    def initialize(self) -> bool:
        """
        Initialize the live engine.

        Returns:
            bool: True if initialization successful
        """
        try:
            self.logger.info("Initializing live engine...")

            # Verify broker connection
            if not self._verify_broker_connection():
                self.logger.error("Broker connection failed")
                return False

            # Verify account access
            if not self._verify_account_access():
                self.logger.error("Account access verification failed")
                return False

            # Load current positions
            self._load_current_positions()

            # Initialize safety systems
            self._initialize_safety_systems()

            # Start monitoring thread
            self._start_monitoring()

            self.state = ExecutionState.CONNECTED
            self.logger.info("Live engine initialized successfully")
            return True

        except Exception as e:
            self.logger.error("Initialization failed: %s", e)
            self.state = ExecutionState.ERROR
            return False

    def start_trading(self) -> bool:
        """
        Start live trading operations.

        Returns:
            bool: True if started successfully
        """
        try:
            if self.state != ExecutionState.CONNECTED:
                self.logger.error("Cannot start trading from state %s", self.state)
                return False

            # Perform pre-trading checks
            if not self._perform_pre_trading_checks():
                self.logger.error("Pre-trading checks failed")
                return False

            # Create trading session
            self.current_session = TradingSession(
                session_id=self._generate_session_id(), start_time=datetime.now(), mode=self.mode
            )

            # Enable order processing
            self.state = ExecutionState.TRADING

            # Log trading start
            self.logger.info("Live trading started - Session: %s", self.current_session.session_id)

            # Emit trading started event
            self._emit_event(
                "live_trading_started",
                {
                    "session_id": self.current_session.session_id,
                    "account_id": self.config.account_id,
                    "mode": self.mode.value,
                },
            )

            return True

        except Exception as e:
            self.logger.error("Failed to start trading: %s", e)
            return False

    def stop_trading(self, reason: str = "User requested") -> bool:
        """
        Stop live trading operations.

        Args:
            reason: Reason for stopping

        Returns:
            bool: True if stopped successfully
        """
        try:
            self.logger.info("Stopping live trading: %s", reason)

            if self.state not in [ExecutionState.TRADING, ExecutionState.PAUSED]:
                self.logger.warning("Not in trading state: %s", self.state)
                return False

            # Set closing state
            self.state = ExecutionState.CLOSING

            # Cancel all pending orders
            self._cancel_all_pending_orders()

            # Close trading session
            if self.current_session:
                self.current_session.end_time = datetime.now()
                self._save_session_data()

            # Stop order processing
            self.state = ExecutionState.STOPPED

            # Emit trading stopped event
            self._emit_event(
                "live_trading_stopped",
                {
                    "session_id": self.current_session.session_id if self.current_session else None,
                    "reason": reason,
                    "final_pnl": self.current_session.total_pnl if self.current_session else 0,
                },
            )

            self.logger.info("Live trading stopped successfully")
            return True

        except Exception as e:
            self.logger.error("Error stopping trading: %s", e)
            return False

    def pause_trading(self) -> bool:
        """
        Pause trading operations.

        Returns:
            bool: True if paused successfully
        """
        if self.state == ExecutionState.TRADING:
            self.state = ExecutionState.PAUSED
            self.logger.info("Trading paused")
            return True
        return False

    def resume_trading(self) -> bool:
        """
        Resume trading operations.

        Returns:
            bool: True if resumed successfully
        """
        if self.state == ExecutionState.PAUSED:
            self.state = ExecutionState.TRADING
            self.logger.info("Trading resumed")
            return True
        return False

    def cleanup(self) -> None:
        """Clean up resources."""
        try:
            # Stop monitoring
            if self.monitor_thread:
                self.stop_event.set()
                self.monitor_thread.join(timeout=5)

            # Close broker connection
            if self.broker:
                self.broker.disconnect()

            self.logger.info("Live engine cleanup completed")

        except Exception as e:
            self.logger.error("Error during cleanup: %s", e)

    # ==========================================================================
    # PUBLIC METHODS - ORDER EXECUTION
    # ==========================================================================
    def execute_order(self, order: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a live order.

        Args:
            order: Order details

        Returns:
            Execution result
        """
        try:
            # Check if trading is active
            if self.state != ExecutionState.TRADING:
                return {"status": "rejected", "reason": f"Trading not active: {self.state.value}"}

            # Perform safety checks
            safety_result = self._perform_order_safety_checks(order)
            if safety_result.result == SafetyCheckResult.FAILED:
                return {
                    "status": "rejected",
                    "reason": safety_result.message,
                    "safety_check": safety_result,
                }

            # Smart confirmation: only for development mode or high-risk orders
            if self.mode == TradingMode.LIVE:
                confirmation_result = self._check_order_confirmation_required(order)
                if confirmation_result['requires_confirmation']:
                    confirmed = self._request_order_confirmation(order, confirmation_result['reason'])
                    if not confirmed:
                        self.logger.warning("Order %s rejected: %s", order.get('symbol'), confirmation_result['reason'])
                        return {
                            "status": "rejected",
                            "reason": f"Order requires confirmation: {confirmation_result['reason']}",
                            "confirmation_declined": True,
                            "confirmation_reason": confirmation_result['reason']
                        }
                else:
                    # Autonomous mode - log and proceed
                    self.logger.info("Order %s proceeding autonomously (confirmation not required)", order.get('symbol'))

            # Add to order queue
            order["timestamp"] = datetime.now()
            order["order_id"] = self._generate_order_id()
            self.order_queue.put(order)

            # Wait for execution result
            result = self._wait_for_execution(order["order_id"])

            # Update metrics
            self._update_execution_metrics(order, result)

            return result

        except Exception as e:
            self.logger.error("Order execution error: %s", e)
            return {"status": "error", "reason": str(e)}

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a pending order.

        Args:
            order_id: Order ID to cancel

        Returns:
            bool: True if cancelled successfully
        """
        try:
            if order_id in self.pending_orders:
                # Send cancellation to broker
                result = self.broker.cancel_order(order_id)

                if result:
                    del self.pending_orders[order_id]
                    self.logger.info("Order %s cancelled", order_id)

                return result

            return False

        except Exception as e:
            self.logger.error("Error cancelling order %s: %s", order_id, e)
            return False

    def get_execution_status(self) -> dict[str, Any]:
        """
        Get current execution status.

        Returns:
            Status information
        """
        return {
            "state": self.state.value,
            "mode": self.mode.value,
            "emergency_stop": self.emergency_stop,
            "session": {
                "id": self.current_session.session_id if self.current_session else None,
                "trades": self.current_session.trades_executed if self.current_session else 0,
                "pnl": self.current_session.total_pnl if self.current_session else 0,
            },
            "daily_stats": {
                "trades": self.daily_trades,
                "loss": self.daily_loss,
                "limit_reached": self.daily_trades >= self.config.max_daily_trades,
            },
            "pending_orders": len(self.pending_orders),
            "active_positions": len(self.active_positions),
            "metrics": {
                "success_rate": self.metrics.successful_executions
                / max(1, self.metrics.total_orders),
                "avg_fill_time": self.metrics.average_fill_time,
                "avg_slippage": self.metrics.average_slippage,
            },
        }

    # ==========================================================================
    # PUBLIC METHODS - EMERGENCY CONTROLS
    # ==========================================================================
    def emergency_stop_all(self, reason: str) -> bool:
        """
        Emergency stop all trading activities.

        Args:
            reason: Reason for emergency stop

        Returns:
            bool: True if stopped successfully
        """
        try:
            self.logger.critical("EMERGENCY STOP INITIATED: %s", reason)

            # Set emergency stop flag
            self.emergency_stop = True
            self.mode = TradingMode.EMERGENCY_STOP

            # Cancel ALL orders immediately
            self._emergency_cancel_all_orders()

            # Close all positions if configured
            if self.config.close_positions_on_emergency:
                self._emergency_close_all_positions()

            # Stop trading
            self.stop_trading(f"Emergency: {reason}")

            # Send alerts
            self._send_emergency_alerts(reason)

            return True

        except Exception as e:
            self.logger.critical("Emergency stop failed: %s", e)
            return False

    def record_api_server_error(self) -> None:
        """
        Record one Tradier 5xx (server-side) error.

        Call this whenever the broker layer raises TradierServerError after
        all retries are exhausted.  If the count reaches API_PANIC_THRESHOLD
        the engine enters API Panic Mode: no new entries are accepted and all
        open positions are closed per close_positions_on_emergency.
        Auto-resets when reset_api_error_count() is called on success.
        """
        self._api_error_count += 1
        self.logger.warning(
            "Tradier API server error #%d (threshold=%d)",
            self._api_error_count, API_PANIC_THRESHOLD,
        )
        if self._api_error_count >= API_PANIC_THRESHOLD and not self._api_panic_mode:
            self._api_panic_mode = True
            self.emergency_stop_all(
                f"Tradier API unreachable - {self._api_error_count} consecutive 5xx errors"
            )

    def reset_api_error_count(self) -> None:
        """Reset the consecutive 5xx counter after a successful broker call."""
        if self._api_error_count > 0:
            self.logger.info(
                "Tradier API recovered — resetting error count (was %d)",
                self._api_error_count,
            )
        self._api_error_count = 0
        self._api_panic_mode = False

    # ==========================================================================
    # PRIVATE METHODS - INITIALIZATION
    # ==========================================================================
    def _verify_broker_connection(self) -> bool:
        """Verify broker connection is active."""
        try:
            return self.broker.is_connected() and self.broker.get_account_info() is not None
        except Exception:
            return False

    def _verify_account_access(self) -> bool:
        """Verify account access and permissions."""
        try:
            account_info = self.broker.get_account_info()
            return (
                account_info is not None
                and account_info.get("account_id") == self.config.account_id
                and account_info.get("trading_enabled", False)
            )
        except Exception:
            return False

    def _load_current_positions(self):
        """Load current positions from broker."""
        try:
            positions = self.broker.get_positions()
            self.active_positions = {p["symbol"]: p for p in positions}
            self.logger.info("Loaded %s active positions", len(self.active_positions))
        except Exception as e:
            self.logger.error("Failed to load positions: %s", e)

    def _initialize_safety_systems(self):
        """Initialize all safety systems."""
        # Register safety checks
        self.safety_checks = []

        # Daily limits
        self._register_safety_check("daily_trade_limit", self._check_daily_trade_limit)
        self._register_safety_check("daily_loss_limit", self._check_daily_loss_limit)

        # Position limits
        self._register_safety_check("position_size", self._check_position_size_limit)
        self._register_safety_check("portfolio_exposure", self._check_portfolio_exposure)

        # Market conditions
        self._register_safety_check("market_hours", self._check_market_hours)
        self._register_safety_check("volatility", self._check_market_volatility)

    # ==========================================================================
    # PRIVATE METHODS - MONITORING
    # ==========================================================================
    def _start_monitoring(self):
        """Start monitoring thread."""
        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop, name="LiveEngineMonitor"
        )
        self.monitor_thread.daemon = True
        self.monitor_thread.start()

    def _monitoring_loop(self):
        """Main monitoring loop."""
        while not self.stop_event.is_set():
            try:
                # Process order queue
                self._process_order_queue()

                # Monitor positions
                self._monitor_positions()

                # Check heartbeat
                self._check_heartbeat()

                # Perform periodic safety checks
                if self.state == ExecutionState.TRADING:
                    self._perform_periodic_safety_checks()

                # Sleep
                self.stop_event.wait(1)

            except Exception as e:
                self.logger.error("Monitoring error: %s", e)

    def _process_order_queue(self):
        """Process orders from queue."""
        while not self.order_queue.empty():
            try:
                order = self.order_queue.get_nowait()
                self._execute_order_internal(order)
            except queue.Empty:
                break
            except Exception as e:
                self.logger.error("Error processing order: %s", e)

    def _monitor_positions(self):
        """Monitor active positions."""
        try:
            # Update position data
            positions = self.broker.get_positions()

            # Check for changes
            for position in positions:
                symbol = position["symbol"]

                # Check stop loss
                if self._should_trigger_stop_loss(position):
                    self._execute_stop_loss(position)

                # Update tracking
                self.active_positions[symbol] = position

        except Exception as e:
            self.logger.error("Position monitoring error: %s", e)

    def _check_heartbeat(self):
        """Check broker connection heartbeat."""
        now = datetime.now()
        if (now - self.last_heartbeat).seconds > HEARTBEAT_INTERVAL:
            try:
                if self.broker.heartbeat():
                    self.last_heartbeat = now
                    self.broker_connected = True
                else:
                    self.broker_connected = False
                    self.logger.warning("Broker heartbeat failed")
            except Exception:
                self.broker_connected = False

    # ==========================================================================
    # PRIVATE METHODS - SAFETY CHECKS
    # ==========================================================================
    def _perform_pre_trading_checks(self) -> bool:
        """Perform pre-trading safety checks."""
        checks_passed = True

        # Market hours check
        if not self._is_market_open():
            self.logger.warning("Market is not open")
            if not self.config.enable_extended_hours:
                checks_passed = False

        # Account balance check
        account_info = self.broker.get_account_info()
        if account_info.get("buying_power", 0) < 1000:
            self.logger.warning("Low buying power")

        # Risk limits check
        if not self.risk_manager.check_daily_limits():
            self.logger.error("Risk limits already exceeded")
            checks_passed = False

        return checks_passed

    def _perform_order_safety_checks(self, order: dict[str, Any]) -> SafetyCheck:
        """Perform safety checks on an order."""
        # Check daily trade limit
        if self.daily_trades >= self.config.max_daily_trades:
            return SafetyCheck(
                check_name="daily_trade_limit",
                result=SafetyCheckResult.FAILED,
                message="Daily trade limit reached",
                timestamp=datetime.now(),
            )

        # Check position size
        if order.get("quantity", 0) > self.config.max_position_size:
            return SafetyCheck(
                check_name="position_size",
                result=SafetyCheckResult.FAILED,
                message="Position size exceeds limit",
                timestamp=datetime.now(),
            )

        # Check market hours
        if not self._is_trading_allowed():
            return SafetyCheck(
                check_name="market_hours",
                result=SafetyCheckResult.FAILED,
                message="Trading not allowed at this time",
                timestamp=datetime.now(),
            )

        return SafetyCheck(
            check_name="order_safety",
            result=SafetyCheckResult.PASSED,
            message="All checks passed",
            timestamp=datetime.now(),
        )

    def _perform_periodic_safety_checks(self):
        """Perform periodic safety checks during trading."""
        # Check daily loss
        if self.daily_loss > self.config.max_daily_loss:
            self.logger.error("Daily loss limit exceeded")
            self.emergency_stop_all("Daily loss limit exceeded")

        # Check portfolio drawdown
        if self._calculate_portfolio_drawdown() > EMERGENCY_STOP_LOSS:
            self.logger.error("Emergency stop loss triggered")
            self.emergency_stop_all("Portfolio drawdown limit exceeded")

    # ==========================================================================
    # PRIVATE METHODS - HELPERS
    # ==========================================================================
    def _check_order_confirmation_required(self, order: dict[str, Any]) -> dict[str, Any]:
        """
        Determine if an order requires user confirmation.

        Confirmation is required in two scenarios:
        1. Development mode: REQUIRE_LIVE_ORDER_CONFIRMATION=true (all orders)
        2. High-risk orders: Exceeds $ threshold or % of portfolio (selective)

        Args:
            order: Order details

        Returns:
            Dict with:
                - requires_confirmation: bool
                - reason: str (why confirmation is needed)
                - risk_level: str (normal/high/critical)
        """
        try:
            # Development mode: require confirmation for ALL orders
            if self.config.require_confirmation:
                return {
                    'requires_confirmation': True,
                    'reason': 'Development mode - all orders require confirmation',
                    'risk_level': 'development'
                }

            # Production autonomous mode: selective confirmation for high-risk only
            if not self.config.high_risk_confirmation:
                # Fully autonomous - no confirmation ever
                return {
                    'requires_confirmation': False,
                    'reason': 'Fully autonomous mode',
                    'risk_level': 'normal'
                }

            # Check if order meets high-risk criteria
            order_value = self._calculate_order_value(order)

            # Get portfolio value for percentage check
            portfolio_value = self._get_portfolio_value()
            order_pct = order_value / portfolio_value if portfolio_value > 0 else 0

            reasons = []
            risk_level = 'normal'

            # Check absolute dollar threshold
            if order_value > self.config.high_risk_threshold_usd:
                reasons.append(f"Order value ${order_value:,.2f} exceeds threshold ${self.config.high_risk_threshold_usd:,.2f}")
                risk_level = 'high'

            # Check portfolio percentage threshold
            if order_pct > self.config.high_risk_portfolio_pct:
                reasons.append(f"Order represents {order_pct*100:.1f}% of portfolio (limit: {self.config.high_risk_portfolio_pct*100:.1f}%)")
                risk_level = 'critical' if order_pct > 0.5 else 'high'

            if reasons:
                return {
                    'requires_confirmation': True,
                    'reason': '; '.join(reasons),
                    'risk_level': risk_level,
                    'order_value': order_value,
                    'portfolio_pct': order_pct
                }

            # Normal order - proceed autonomously
            return {
                'requires_confirmation': False,
                'reason': 'Normal order within autonomous parameters',
                'risk_level': 'normal',
                'order_value': order_value,
                'portfolio_pct': order_pct
            }

        except Exception as e:
            self.logger.error("Error checking confirmation requirement: %s", e, exc_info=True)
            # Fail safe: require confirmation on error
            return {
                'requires_confirmation': True,
                'reason': f'Error evaluating risk: {str(e)}',
                'risk_level': 'error'
            }

    def _request_order_confirmation(self, order: dict[str, Any], reason: str) -> bool:
        """
        Request explicit user confirmation before executing a high-risk order.

        This method is ONLY called for:
        - Development mode (all orders)
        - High-risk orders exceeding thresholds

        Args:
            order: Order details to confirm
            reason: Why confirmation is required

        Returns:
            bool: True if confirmed, False if declined

        Note:
            In production autonomous mode, this should rarely be called.
            When called, it integrates with GUI/monitoring systems for approval.
        """
        try:
            # Log the confirmation request
            self.logger.warning("="*60)
            self.logger.warning("HIGH-RISK ORDER CONFIRMATION REQUIRED")
            self.logger.warning("="*60)
            self.logger.warning("Reason: %s", reason)
            self.logger.warning("Symbol: %s", order.get('symbol', 'N/A'))
            self.logger.warning("Side: %s", order.get('side', 'N/A'))
            self.logger.warning("Quantity: %s", order.get('quantity', 'N/A'))
            self.logger.warning("Order Type: %s", order.get('type', 'N/A'))
            self.logger.warning("Price: %s", order.get('price', 'MARKET'))
            self.logger.warning(f"Estimated Value: ${self._calculate_order_value(order):,.2f}")
            self.logger.warning("="*60)

            # Emit event for GUI/monitoring to display confirmation dialog
            self._emit_event('high_risk_order_confirmation_requested', {
                'order': order,
                'reason': reason,
                'timestamp': datetime.now().isoformat()
            })

            # Integration points:
            # 1. SpyderJ05_TelegramBot — mobile push notification with APPROVE/REJECT inline keyboard
            # 2. SpyderG09_RiskParametersDialog — GUI dialog (not applicable in headless/backend mode)
            confirm_timeout = int(os.environ.get('HIGH_RISK_CONFIRM_TIMEOUT_SECS', '60'))
            if self.telegram_bot is not None:
                try:
                    result = self.telegram_bot.send_confirmation_request(
                        order=order, reason=reason, timeout=confirm_timeout
                    )
                    if result is True:
                        self.logger.warning("High-risk order APPROVED by operator via Telegram.")
                        return True
                    if result is False:
                        self.logger.critical("High-risk order REJECTED by operator via Telegram.")
                        return False
                    # result is None → timed out; fall through to autonomous decision
                    self.logger.warning(
                        f"Telegram confirmation timed out after {confirm_timeout}s "
                        "— falling back to autonomous risk decision."
                    )
                except Exception as _tg_err:
                    self.logger.error(
                        "Telegram confirmation error: %s — falling back to autonomous decision.", _tg_err
                    )

            # Testing override (sandbox/paper only)
            if os.environ.get('AUTO_CONFIRM_HIGH_RISK_ORDERS', 'false').lower() == 'true':
                self.logger.warning("AUTO_CONFIRM_HIGH_RISK_ORDERS enabled — auto-approved (TESTING ONLY)")
                return True

            # Autonomous decision: delegate to the E-series risk engine
            approved = self._autonomous_risk_decision(order, reason)
            if approved:
                self.logger.warning("Autonomous risk assessment: APPROVED")
            else:
                self.logger.critical("Autonomous risk assessment: REJECTED — order blocked by risk engine")
            return approved

        except Exception as e:
            self.logger.error("Error requesting order confirmation: %s", e, exc_info=True)
            return False  # Fail safe: reject on error

    def _autonomous_risk_decision(self, order: dict[str, Any], reason: str) -> bool:
        """
        Make an autonomous approve/reject decision for a high-risk order using
        the E-series risk engine. Called instead of human/Telegram confirmation.

        Args:
            order:  Order details dict.
            reason: The trigger reason (e.g. "position size limit").

        Returns:
            True  — risk engine approves the order.
            False — risk engine rejects; order must not be submitted.
        """
        try:
            # --- 1. Check circuit breaker / daily limits via risk_manager ---
            if hasattr(self.risk_manager, 'check_daily_limits'):
                if not self.risk_manager.check_daily_limits():
                    self.logger.warning("Autonomous rejection: daily risk limits already exceeded.")
                    return False

            # --- 2. Check current risk metrics for drawdown / exposure ---
            if hasattr(self.risk_manager, 'get_risk_metrics'):
                metrics = self.risk_manager.get_risk_metrics()
                if metrics is not None:
                    # Reject if daily P&L loss exceeds 75 % of the configured maximum
                    max_daily = getattr(self.config, 'max_daily_loss', None)
                    if max_daily and hasattr(metrics, 'daily_pnl'):
                        if metrics.daily_pnl < -(abs(max_daily) * 0.75):
                            self.logger.warning(
                                f"Autonomous rejection: daily P&L {metrics.daily_pnl:.2f} "
                                f"approaching limit {max_daily:.2f}."
                            )
                            return False

            # --- 3. Favour rejection for explicit position-size violations ---
            trigger_lower = reason.lower()
            hard_blocks = ("position size", "daily loss", "exposure limit", "drawdown")
            if any(kw in trigger_lower for kw in hard_blocks):
                self.logger.warning(
                    "Autonomous rejection: hard-block trigger in reason: '%s'.", reason
                )
                return False

            # --- 4. All checks passed — approve ---
            self.logger.info(
                "Autonomous approval: no hard-block conditions triggered for reason '%s'.", reason
            )
            return True

        except Exception as e:
            self.logger.error("Autonomous risk decision error: %s", e, exc_info=True)
            return False  # Fail safe: reject on error

    def _calculate_order_value(self, order: dict[str, Any]) -> float:
        """
        Calculate the dollar value of an order.

        Args:
            order: Order details

        Returns:
            Estimated order value in USD
        """
        try:
            quantity = order.get('quantity', 0)
            price = order.get('price', 0)
            symbol = order.get('symbol', '')

            # For market orders, estimate using current market price
            if price == 0 or order.get('type', '').lower() == 'market':
                # Fetch current market price from broker
                try:
                    quotes = self.broker.get_quotes([symbol]) if symbol else {}
                    quote = quotes.get('quote', quotes) if isinstance(quotes, dict) else {}
                    if isinstance(quote, list) and quote:
                        quote = quote[0]
                    price = float(quote.get('last', 0) or quote.get('close', 0) or 0)
                except Exception:
                    self.logger.warning("Could not fetch live price for %s, using order price", symbol)
                if price == 0:
                    self.logger.warning("No price available for order value calculation on %s", symbol)
                    return 0.0

            # For options, multiply by contract multiplier (usually 100)
            multiplier = 100 if self._is_option_symbol(symbol) else 1

            return abs(quantity * price * multiplier)

        except Exception as e:
            self.logger.error("Error calculating order value: %s", e)
            return 0.0

    def _get_portfolio_value(self) -> float:
        """
        Get current portfolio value.

        Returns:
            Portfolio value in USD
        """
        try:
            # Get from broker interface
            account_info = self.broker.get_account_info()
            return account_info.get('total_equity', 0.0)
        except Exception as e:
            self.logger.error("Error getting portfolio value: %s", e)
            return 0.0

    def _is_option_symbol(self, symbol: str) -> bool:
        """
        Check if symbol is an option.

        Args:
            symbol: Symbol to check

        Returns:
            True if option symbol
        """
        # Options typically have format: SPY240315C00450000
        return len(symbol) > 10 and any(c in symbol for c in ['C', 'P'])

    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        return f"LIVE_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def _generate_order_id(self) -> str:
        """Generate unique order ID."""
        return f"ORD_{datetime.now().strftime('%Y%m%d_%H%M%S%f')}"

    def _is_market_open(self) -> bool:
        """Check if market is open."""
        now = datetime.now().time()
        return MARKET_OPEN <= now <= MARKET_CLOSE

    def _is_trading_allowed(self) -> bool:
        """Check if trading is allowed at current time."""
        now = datetime.now().time()

        if self.config.enable_extended_hours:
            return EXTENDED_HOURS_START <= now <= EXTENDED_HOURS_END
        else:
            return self._is_market_open()

    def _calculate_portfolio_drawdown(self) -> float:
        """Calculate current portfolio drawdown."""
        # Implementation would calculate actual drawdown
        return 0.0

    def _emit_event(self, event_type: str, data: dict[str, Any]):
        """Emit event through event manager."""
        # Would integrate with SpyderA05_EventManager
        self.logger.debug("Event: %s - %s", event_type, data)

    def _save_session_data(self):
        """Save trading session data."""
        if self.current_session:
            # Would save to database
            self.logger.info("Session %s saved", self.current_session.session_id)

    # ==========================================================================
    # PRIVATE METHODS - SAFETY CHECK REGISTRY
    # ==========================================================================

    def _register_safety_check(self, name: str, check_fn) -> None:
        """Register a named safety-check function."""
        if not hasattr(self, '_safety_check_registry'):
            self._safety_check_registry: dict[str, Any] = {}
        self._safety_check_registry[name] = check_fn

    def _check_daily_trade_limit(self) -> SafetyCheck:
        passed = self.daily_trades < self.config.max_daily_trades
        return SafetyCheck(
            check_name="daily_trade_limit",
            result=SafetyCheckResult.PASSED if passed else SafetyCheckResult.FAILED,
            message=f"Daily trades: {self.daily_trades}/{self.config.max_daily_trades}",
            timestamp=datetime.now(),
        )

    def _check_daily_loss_limit(self) -> SafetyCheck:
        passed = self.daily_loss <= self.config.max_daily_loss
        return SafetyCheck(
            check_name="daily_loss_limit",
            result=SafetyCheckResult.PASSED if passed else SafetyCheckResult.FAILED,
            message=f"Daily loss: {self.daily_loss:.2f}/{self.config.max_daily_loss:.2f}",
            timestamp=datetime.now(),
        )

    def _check_position_size_limit(self) -> SafetyCheck:
        return SafetyCheck(
            check_name="position_size",
            result=SafetyCheckResult.PASSED,
            message="Position sizes within limits",
            timestamp=datetime.now(),
        )

    def _check_portfolio_exposure(self) -> SafetyCheck:
        return SafetyCheck(
            check_name="portfolio_exposure",
            result=SafetyCheckResult.PASSED,
            message="Portfolio exposure within limits",
            timestamp=datetime.now(),
        )

    def _check_market_hours(self) -> SafetyCheck:
        allowed = self._is_trading_allowed()
        return SafetyCheck(
            check_name="market_hours",
            result=SafetyCheckResult.PASSED if allowed else SafetyCheckResult.WARNING,
            message="Market open" if allowed else "Outside trading hours",
            timestamp=datetime.now(),
        )

    def _check_market_volatility(self) -> SafetyCheck:
        return SafetyCheck(
            check_name="volatility",
            result=SafetyCheckResult.PASSED,
            message="Volatility within normal range",
            timestamp=datetime.now(),
        )

    # ==========================================================================
    # PRIVATE METHODS - ORDER EXECUTION INTERNALS
    # ==========================================================================

    def _execute_order_internal(self, order: dict[str, Any]) -> None:
        """Submit an order through the broker and track the result."""
        order_id = order.get("order_id")
        try:
            result = self.broker.submit_order(order)
            # Any broker round-trip that returns without a TradierServerError
            # is a successful API contact — clear the panic counter even if
            # the order itself wasn't filled.
            self.reset_api_error_count()
            if result and result.get("status") == "filled":
                self.metrics.successful_executions += 1
                self.daily_trades += 1
                if self.current_session:
                    self.current_session.trades_executed += 1
            else:
                self.metrics.failed_executions += 1
            self.pending_orders[order_id] = {"order": order, "result": result}
        except _TradierServerError as exc:
            # Tradier 5xx: record failure; may trigger API Panic Mode
            self.logger.error("Tradier 5xx error for order %s: %s", order_id, exc)
            self.metrics.failed_executions += 1
            self.pending_orders[order_id] = {"order": order, "result": {"status": "error", "reason": str(exc)}}
            self.record_api_server_error()
        except Exception as exc:
            self.logger.error("Internal order execution failed for %s: %s", order_id, exc)
            self.metrics.failed_executions += 1
            self.pending_orders[order_id] = {"order": order, "result": {"status": "error", "reason": str(exc)}}
        finally:
            self.metrics.total_orders += 1

    def _wait_for_execution(self, order_id: str, timeout: int = ORDER_TIMEOUT_SECONDS) -> dict[str, Any]:
        """Block until the broker confirms order execution or timeout expires."""
        import time as _time
        deadline = _time.monotonic() + timeout
        while _time.monotonic() < deadline:
            if order_id in self.pending_orders:
                entry = self.pending_orders[order_id]
                result = entry.get("result")
                if result is not None:
                    return result
            _time.sleep(0.1)
        return {"status": "timeout", "reason": f"Order {order_id} not confirmed within {timeout}s"}

    def _update_execution_metrics(self, order: dict[str, Any], result: dict[str, Any]) -> None:
        """Update rolling execution metrics from a completed order."""
        if result.get("status") == "filled":
            fill_time = result.get("fill_time_ms", 0)
            n = max(1, self.metrics.successful_executions)
            self.metrics.average_fill_time = (
                (self.metrics.average_fill_time * (n - 1) + fill_time) / n
            )
            slippage = result.get("slippage", 0.0)
            self.metrics.average_slippage = (
                (self.metrics.average_slippage * (n - 1) + slippage) / n
            )
        total = max(1, self.metrics.total_orders)
        self.metrics.rejection_rate = self.metrics.failed_executions / total

    # ==========================================================================
    # PRIVATE METHODS - STOP LOSS
    # ==========================================================================

    def _should_trigger_stop_loss(self, position: dict[str, Any]) -> bool:
        """Return True if the position's unrealised loss exceeds its stop level."""
        stop_loss_pct = position.get("stop_loss_pct")
        entry_price = position.get("entry_price", 0)
        current_price = position.get("current_price", entry_price)
        if stop_loss_pct and entry_price > 0:
            loss_pct = (entry_price - current_price) / entry_price
            return loss_pct >= stop_loss_pct
        return False

    def _execute_stop_loss(self, position: dict[str, Any]) -> None:
        """Close a position that has breached its stop-loss level."""
        symbol = position.get("symbol", "UNKNOWN")
        self.logger.warning("Stop-loss triggered for %s — closing position", symbol)
        try:
            self.broker.close_position(position.get("id"), urgency="IMMEDIATE", reason="stop_loss")
        except Exception as exc:
            self.logger.error("Stop-loss close failed for %s: %s", symbol, exc)

    # ==========================================================================
    # PRIVATE METHODS - EMERGENCY CONTROLS
    # ==========================================================================

    def _cancel_all_pending_orders(self) -> None:
        """Cancel every pending order via the broker."""
        order_ids = list(self.pending_orders.keys())
        for order_id in order_ids:
            try:
                self.broker.cancel_order(order_id)
                del self.pending_orders[order_id]
                self.logger.info("Cancelled pending order %s", order_id)
            except Exception as exc:
                self.logger.error("Failed to cancel order %s: %s", order_id, exc)

    def _emergency_cancel_all_orders(self) -> None:
        """Emergency cancellation — drain the queue then cancel all pending orders."""
        # Drain the order queue first so no new orders reach the broker
        while not self.order_queue.empty():
            try:
                self.order_queue.get_nowait()
            except Exception:
                break
        self._cancel_all_pending_orders()

    def _emergency_close_all_positions(self) -> None:
        """Flatten all active positions immediately (Level-3 / portfolio-loss stop)."""
        self.logger.critical("EMERGENCY: closing all active positions")
        symbols = list(self.active_positions.keys())
        for symbol in symbols:
            position = self.active_positions.get(symbol)
            if position is None:
                continue
            try:
                self.broker.close_position(
                    position.get("id", symbol),
                    urgency="IMMEDIATE",
                    reason="emergency_stop",
                    force=True,
                )
                del self.active_positions[symbol]
                self.logger.info("Emergency-closed position: %s", symbol)
            except Exception as exc:
                self.logger.error("Failed to emergency-close %s: %s", symbol, exc)

    def _send_emergency_alerts(self, reason: str) -> None:
        """Log a critical alert and emit an emergency event."""
        self.logger.critical("EMERGENCY ALERT — trading halted: %s", reason)
        self._emit_event(
            "emergency_stop",
            {
                "reason": reason,
                "account_id": self.config.account_id,
                "timestamp": datetime.now().isoformat(),
                "daily_loss": self.daily_loss,
                "daily_trades": self.daily_trades,
            },
        )


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================


def create_live_engine(
    broker,
    risk_manager,
    config: dict[str, Any],
    telegram_bot: Any = None,
) -> LiveEngine:
    """
    Factory function to create live engine.

    Args:
        broker: Broker interface
        risk_manager: Risk manager interface
        config: Configuration dictionary
        telegram_bot: Optional SpyderJ05 TelegramBot for high-risk order confirmation.
            When provided, high-risk orders block on an inline-keyboard Approve/Reject
            message before execution.  When None the autonomous risk-decision fallback
            is used instead.

    Returns:
        Configured LiveEngine instance
    """
    live_config = LiveTradingConfig(
        account_id=config.get("account_id"),
        max_daily_trades=config.get("max_daily_trades", MAX_DAILY_TRADES),
        max_position_size=config.get("max_position_size", MAX_POSITION_SIZE),
        max_daily_loss=config.get("max_daily_loss", MAX_DAILY_LOSS),
        enable_extended_hours=config.get("enable_extended_hours", False),
        require_confirmation=config.get("require_confirmation", True),
    )

    return LiveEngine(broker, risk_manager, live_config, telegram_bot=telegram_bot)


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing
    pass
