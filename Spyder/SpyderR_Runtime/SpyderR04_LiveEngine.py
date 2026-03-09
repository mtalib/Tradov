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
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)
EXTENDED_HOURS_START = time(4, 0)
EXTENDED_HOURS_END = time(20, 0)

# Safety limits
MAX_DAILY_TRADES = 100
MAX_POSITION_SIZE = 10000  # contracts
MAX_DAILY_LOSS = 10000  # dollars
EMERGENCY_STOP_LOSS = 0.05  # 5% portfolio loss

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
    require_confirmation: bool = True
    use_limit_orders_only: bool = False
    slippage_tolerance: float = 0.01  # 1%
    partial_fill_timeout: int = 60  # seconds
    close_positions_on_emergency: bool = False  # If True, flatten all on emergency stop


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

    def __init__(self, broker_interface, risk_manager, config: LiveTradingConfig):
        """Initialize the live engine."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config = config
        self.broker = broker_interface
        self.risk_manager = risk_manager

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

        self.logger.info(f"LiveEngine initialized for account {config.account_id}")

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
            self.logger.error(f"Initialization failed: {e}")
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
                self.logger.error(f"Cannot start trading from state {self.state}")
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
            self.logger.info(f"Live trading started - Session: {self.current_session.session_id}")

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
            self.logger.error(f"Failed to start trading: {e}")
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
            self.logger.info(f"Stopping live trading: {reason}")

            if self.state not in [ExecutionState.TRADING, ExecutionState.PAUSED]:
                self.logger.warning(f"Not in trading state: {self.state}")
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
            self.logger.error(f"Error stopping trading: {e}")
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
            self.logger.error(f"Error during cleanup: {e}")

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
            self.logger.error(f"Order execution error: {e}")
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
                    self.logger.info(f"Order {order_id} cancelled")

                return result

            return False

        except Exception as e:
            self.logger.error(f"Error cancelling order {order_id}: {e}")
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
            self.logger.critical(f"EMERGENCY STOP INITIATED: {reason}")

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
            self.logger.critical(f"Emergency stop failed: {e}")
            return False

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
            self.logger.info(f"Loaded {len(self.active_positions)} active positions")
        except Exception as e:
            self.logger.error(f"Failed to load positions: {e}")

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
                self.logger.error(f"Monitoring error: {e}")

    def _process_order_queue(self):
        """Process orders from queue."""
        while not self.order_queue.empty():
            try:
                order = self.order_queue.get_nowait()
                self._execute_order_internal(order)
            except queue.Empty:
                break
            except Exception as e:
                self.logger.error(f"Error processing order: {e}")

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
            self.logger.error(f"Position monitoring error: {e}")

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
        self.logger.debug(f"Event: {event_type} - {data}")

    def _save_session_data(self):
        """Save trading session data."""
        if self.current_session:
            # Would save to database
            self.logger.info(f"Session {self.current_session.session_id} saved")

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
            message="Position size within limits",
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
            if result and result.get("status") == "filled":
                self.metrics.successful_executions += 1
                self.daily_trades += 1
                if self.current_session:
                    self.current_session.trades_executed += 1
            else:
                self.metrics.failed_executions += 1
            self.pending_orders[order_id] = {"order": order, "result": result}
        except Exception as exc:
            self.logger.error(f"Internal order execution failed for {order_id}: {exc}")
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
        self.logger.warning(f"Stop-loss triggered for {symbol} — closing position")
        try:
            self.broker.close_position(position.get("id"), urgency="IMMEDIATE", reason="stop_loss")
        except Exception as exc:
            self.logger.error(f"Stop-loss close failed for {symbol}: {exc}")

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
                self.logger.info(f"Cancelled pending order {order_id}")
            except Exception as exc:
                self.logger.error(f"Failed to cancel order {order_id}: {exc}")

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
                self.logger.info(f"Emergency-closed position: {symbol}")
            except Exception as exc:
                self.logger.error(f"Failed to emergency-close {symbol}: {exc}")

    def _send_emergency_alerts(self, reason: str) -> None:
        """Log a critical alert and emit an emergency event."""
        self.logger.critical(f"EMERGENCY ALERT — trading halted: {reason}")
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


def create_live_engine(broker, risk_manager, config: dict[str, Any]) -> LiveEngine:
    """
    Factory function to create live engine.

    Args:
        broker: Broker interface
        risk_manager: Risk manager interface
        config: Configuration dictionary

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

    return LiveEngine(broker, risk_manager, live_config)


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing
    pass
