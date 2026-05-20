#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderD_Strategies
Module: SpyderD01_BaseStrategy.py
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
import threading
import uuid
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
from collections.abc import Callable  # noqa: F401

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderU_Utilities.SpyderU07_Constants import (MAX_DAILY_TRADES,

                                                MAX_PORTFOLIO_RISK)
from Spyder.SpyderA_Core.SpyderA05_EventManager import (
    EventManager,
    Event,
    EventType,
    get_event_manager,  # noqa: F401
)
import logging  # noqa: F401

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Strategy states
STRATEGY_INACTIVE = "inactive"
STRATEGY_INITIALIZING = "initializing"
STRATEGY_ACTIVE = "active"
STRATEGY_PAUSED = "paused"
STRATEGY_CLOSING = "closing"
STRATEGY_ERROR = "error"

# Position limits
DEFAULT_MAX_POSITIONS = 5
DEFAULT_POSITION_SIZE = 0.02  # 2% of portfolio
DEFAULT_MAX_LOSS_PER_TRADE = 0.01  # 1% max loss

# Time constants
SIGNAL_EXPIRY_SECONDS = 300  # 5 minutes
PERFORMANCE_WINDOW_DAYS = 30

# ==============================================================================
# ENUMS
# ==============================================================================


class SignalType(Enum):
    """Types of trading signals"""

    BUY = "buy"
    SELL = "sell"
    CLOSE = "close"
    ADJUST = "adjust"
    HOLD = "hold"


class SignalStrength(Enum):
    """Signal strength classification"""

    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    VERY_STRONG = "very_strong"


class PositionType(Enum):
    """Position types"""

    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


class PositionState(Enum):
    """Position lifecycle states"""

    PENDING = "pending"
    OPENING = "opening"
    OPEN = "open"
    ADJUSTING = "adjusting"
    CLOSING = "closing"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    ERROR = "error"


class RiskLevel(Enum):
    """Risk level classification"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================


@dataclass
class TradingSignal:
    """Trading signal data structure"""

    signal_id: str
    signal_type: SignalType
    symbol: str
    strength: SignalStrength
    confidence: float  # 0.0 to 1.0
    entry_price: float
    stop_loss: float
    take_profit: float
    position_size: int
    timestamp: datetime
    expires_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)
    # Quote at signal-generation time — used by D31 for mid-price walk execution
    bid: float = 0.0
    ask: float = 0.0
    option_symbol: str = ""  # OCC-format symbol for single-leg options

    def is_valid(self) -> bool:
        """Check if signal is still valid"""
        now = datetime.now(timezone.utc) if self.expires_at.tzinfo else datetime.now()
        return now < self.expires_at

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        metadata = self.metadata or {}
        strategy_id = (
            metadata.get("strategy_id")
            or metadata.get("strategy_type")
            or metadata.get("strategy")
            or metadata.get("strategy_tag")
            or ""
        )
        action = str(
            metadata.get("action")
            or metadata.get("side")
            or self.signal_type.value
        ).lower()
        return {
            "signal_id": self.signal_id,
            "signal_type": self.signal_type.value,
            "symbol": self.symbol,
            "strength": self.strength.value,
            "confidence": self.confidence,
            "entry_price": self.entry_price,
            "price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "position_size": self.position_size,
            "quantity": self.position_size,
            "action": action,
            "side": action,
            "strategy_id": strategy_id,
            "strategy_type": metadata.get("strategy_type") or strategy_id,
            "direction": metadata.get("direction", ""),
            "timestamp": self.timestamp.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "metadata": self.metadata,
            "bid": self.bid,
            "ask": self.ask,
            "option_symbol": self.option_symbol,
        }


@dataclass
class StrategyPosition:
    """Strategy position tracking"""

    position_id: str
    strategy_name: str
    symbol: str
    position_type: PositionType
    state: PositionState
    entry_time: datetime
    entry_price: float
    position_size: int
    stop_loss: float
    take_profit: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    exit_time: datetime | None = None
    exit_price: float | None = None
    exit_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def update_pnl(self, current_price: float) -> None:
        """Update P&L calculations"""
        self.current_price = current_price
        if self.position_type == PositionType.LONG:
            self.unrealized_pnl = (current_price - self.entry_price) * self.position_size
        else:  # SHORT
            self.unrealized_pnl = (self.entry_price - current_price) * self.position_size

    def close_position(self, exit_price: float, exit_reason: str) -> None:
        """Close position and finalize P&L"""
        self.exit_time = datetime.now(timezone.utc)
        self.exit_price = exit_price
        self.exit_reason = exit_reason
        self.state = PositionState.CLOSED

        if self.position_type == PositionType.LONG:
            self.realized_pnl = (exit_price - self.entry_price) * self.position_size
        else:  # SHORT
            self.realized_pnl = (self.entry_price - exit_price) * self.position_size

        self.unrealized_pnl = 0.0


@dataclass
class RiskProfile:
    """Risk management profile"""

    account_size: float
    max_position_size: float = DEFAULT_POSITION_SIZE
    max_portfolio_risk: float = MAX_PORTFOLIO_RISK
    max_loss_per_trade: float = DEFAULT_MAX_LOSS_PER_TRADE
    max_daily_loss: float = 0.03  # 3% daily loss limit
    max_positions: int = DEFAULT_MAX_POSITIONS
    risk_level: RiskLevel = RiskLevel.MEDIUM

    def calculate_position_size(self, signal_strength: SignalStrength) -> float:
        """Calculate position size based on signal strength"""
        base_size = self.account_size * self.max_position_size

        multipliers = {
            SignalStrength.WEAK: 0.5,
            SignalStrength.MODERATE: 0.75,
            SignalStrength.STRONG: 1.0,
            SignalStrength.VERY_STRONG: 1.25,
        }

        return base_size * multipliers.get(signal_strength, 0.75)


@dataclass
class PerformanceMetrics:
    """Strategy performance tracking"""

    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    average_win: float = 0.0
    average_loss: float = 0.0
    profit_factor: float = 0.0
    current_streak: int = 0
    max_win_streak: int = 0
    max_loss_streak: int = 0
    daily_pnl: dict[str, float] = field(default_factory=dict)

    def update(self, position: StrategyPosition) -> None:
        """Update metrics with closed position"""
        if position.state != PositionState.CLOSED:
            return

        self.total_trades += 1
        pnl = position.realized_pnl

        if pnl > 0:
            self.winning_trades += 1
            self.average_win = (
                self.average_win * (self.winning_trades - 1) + pnl
            ) / self.winning_trades
            if self.current_streak >= 0:
                self.current_streak += 1
            else:
                self.current_streak = 1
            self.max_win_streak = max(self.max_win_streak, self.current_streak)
        else:
            self.losing_trades += 1
            self.average_loss = (
                self.average_loss * (self.losing_trades - 1) + abs(pnl)
            ) / self.losing_trades
            if self.current_streak <= 0:
                self.current_streak -= 1
            else:
                self.current_streak = -1
            self.max_loss_streak = max(self.max_loss_streak, abs(self.current_streak))

        self.total_pnl += pnl
        self.win_rate = self.winning_trades / self.total_trades if self.total_trades > 0 else 0

        if self.average_loss > 0:
            self.profit_factor = (self.average_win * self.winning_trades) / (
                self.average_loss * self.losing_trades
            )

        # Update daily P&L
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.daily_pnl[today] = self.daily_pnl.get(today, 0) + pnl


# ==============================================================================
# BASE STRATEGY CLASS
# ==============================================================================


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.

    This class provides the foundational framework that all strategies must
    implement. It handles common functionality like position management,
    risk controls, performance tracking, and event handling.
    """

    def __init__(
        self,
        name: str,
        event_manager: EventManager,
        risk_profile: RiskProfile,
        config: dict[str, Any] | None,
        strategy_type: str | None = None,
    ):
        """
        Initialize base strategy.

        Args:
            name: Strategy name
            event_manager: Event management system
            risk_profile: Risk management profile
            config: Strategy-specific configuration
            strategy_type: Optional legacy strategy type identifier
        """
        # Core attributes
        self.name = name
        self.strategy_id = str(uuid.uuid4())
        self.event_manager = event_manager
        self.risk_profile = risk_profile
        self.config = config or {}
        self.strategy_type = strategy_type or self.name.lower().replace(" ", "_")

        # Logging and error handling
        self.logger = SpyderLogger.get_logger(f"Strategy.{name}")
        self.error_handler = SpyderErrorHandler()

        # State management
        self.state = STRATEGY_INACTIVE
        self.start_time: datetime | None = None
        self.last_update: datetime | None = None

        # Position tracking
        self.positions: dict[str, StrategyPosition] = {}
        self.position_history: list[StrategyPosition] = []
        self.max_positions = self.config.get("max_positions", DEFAULT_MAX_POSITIONS)

        # Signal management
        self.active_signals: dict[str, TradingSignal] = {}
        self.signal_history: list[TradingSignal] = []

        # Performance tracking
        self.performance = PerformanceMetrics()
        self.daily_trades = 0
        self.last_trade_date: datetime | None = None

        # Threading for async operations
        self.executor = ThreadPoolExecutor(max_workers=2)
        self._stop_event = threading.Event()

        # Subscribe to relevant events
        self._setup_event_subscriptions()

        self.logger.debug("Strategy %s initialized with ID %s", name, self.strategy_id)

    # ==========================================================================
    # ABSTRACT METHODS (Must be implemented by subclasses)
    # ==========================================================================

    @abstractmethod
    def generate_signals(self, market_data: pd.DataFrame) -> list[TradingSignal]:
        """
        Generate trading signals based on market data.

        Args:
            market_data: Current market data

        Returns:
            List of trading signals
        """
        pass

    @abstractmethod
    def validate_signal(self, signal: TradingSignal) -> bool:
        """
        Validate a trading signal before execution.

        Args:
            signal: Trading signal to validate

        Returns:
            True if signal is valid
        """
        pass

    @abstractmethod
    def calculate_position_size(self, signal: TradingSignal) -> int:
        """
        Calculate position size for a signal.

        Args:
            signal: Trading signal

        Returns:
            Position size in contracts
        """
        pass

    @abstractmethod
    def should_exit_position(
        self, position: StrategyPosition, market_data: pd.DataFrame
    ) -> tuple[bool, str]:
        """
        Determine if position should be exited.

        Args:
            position: Current position
            market_data: Current market data

        Returns:
            Tuple of (should_exit, reason)
        """
        pass

    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================

    def start(self) -> bool:
        """Start the strategy"""
        try:
            if self.state != STRATEGY_INACTIVE:
                self.logger.warning("Cannot start strategy in state %s", self.state)
                return False

            self.state = STRATEGY_INITIALIZING
            self.start_time = datetime.now(timezone.utc)

            # Perform initialization
            self._initialize_strategy()

            self.state = STRATEGY_ACTIVE
            self.logger.debug("Strategy %s started successfully", self.name)

            # Publish status event
            self._publish_status_event("Strategy started")

            return True

        except Exception as e:
            self.error_handler.handle_error(e, {"method": "start"})
            self.state = STRATEGY_ERROR
            return False

    def stop(self) -> bool:
        """Stop the strategy"""
        try:
            if self.state not in [STRATEGY_ACTIVE, STRATEGY_PAUSED]:
                self.logger.warning("Cannot stop strategy in state %s", self.state)
                return False

            self.state = STRATEGY_CLOSING
            self._stop_event.set()

            # Close all open positions
            self._close_all_positions("Strategy stopped")

            # Cleanup
            self.executor.shutdown(wait=True)

            self.state = STRATEGY_INACTIVE
            self.logger.info("Strategy %s stopped successfully", self.name)

            # Publish status event
            self._publish_status_event("Strategy stopped")

            return True

        except Exception as e:
            self.error_handler.handle_error(e, {"method": "stop"})
            return False

    def pause(self) -> bool:
        """Pause the strategy"""
        if self.state == STRATEGY_ACTIVE:
            self.state = STRATEGY_PAUSED
            self.logger.info("Strategy %s paused", self.name)
            self._publish_status_event("Strategy paused")
            return True
        return False

    def resume(self) -> bool:
        """Resume the strategy"""
        if self.state == STRATEGY_PAUSED:
            self.state = STRATEGY_ACTIVE
            self.logger.info("Strategy %s resumed", self.name)
            self._publish_status_event("Strategy resumed")
            return True
        return False

    # ==========================================================================
    # CORE METHODS
    # ==========================================================================

    def process_market_data(self, market_data: pd.DataFrame) -> None:
        """
        Process market data and manage positions.

        Args:
            market_data: Current market data
        """
        if self.state != STRATEGY_ACTIVE:
            return

        try:
            self.last_update = datetime.now(timezone.utc)

            # Update existing positions
            self._update_positions(market_data)

            # Check for exit conditions
            self._check_exit_conditions(market_data)

            # Generate new signals
            if self._can_trade():
                signals = self.generate_signals(market_data)
                for signal in signals:
                    self._process_signal(signal)

            # Update performance metrics
            self._update_performance_metrics()

        except Exception as e:
            self.error_handler.handle_error(
                e, {"method": "process_market_data", "strategy": self.name}
            )

    def add_position(self, signal: TradingSignal) -> StrategyPosition | None:
        """
        Add new position from signal.

        Args:
            signal: Trading signal

        Returns:
            Created position or None
        """
        try:
            # Validate signal
            if not self.validate_signal(signal):
                self.logger.warning("Invalid signal: %s", signal.signal_id)
                return None

            # Check position limits
            if len(self.positions) >= self.max_positions:
                self.logger.warning("Maximum positions reached")
                return None

            # Create position
            position = StrategyPosition(
                position_id=str(uuid.uuid4()),
                strategy_name=self.name,
                symbol=signal.symbol,
                position_type=(
                    PositionType.LONG
                    if signal.signal_type == SignalType.BUY
                    else PositionType.SHORT
                ),
                state=PositionState.PENDING,
                entry_time=datetime.now(timezone.utc),
                entry_price=signal.entry_price,
                position_size=signal.position_size,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit,
                metadata=signal.metadata,
            )

            # Add to tracking
            self.positions[position.position_id] = position

            # Publish event
            self.event_manager.emit(
                EventType.POSITION_OPENED,
                dict(position.__dict__),
                source=self.name,
            )

            self.logger.info("Position opened: %s", position.position_id)
            return position

        except Exception as e:
            self.error_handler.handle_error(
                e, {"method": "add_position", "signal": signal.signal_id}
            )
            return None

    def close_position(self, position_id: str, exit_price: float, reason: str = "Manual") -> bool:
        """
        Close a position.

        Args:
            position_id: Position ID to close
            exit_price: Exit price
            reason: Reason for closing

        Returns:
            Success status
        """
        try:
            position = self.positions.get(position_id)
            if not position:
                self.logger.warning("Position not found: %s", position_id)
                return False

            # Close position
            position.close_position(exit_price, reason)

            # Update performance
            self.performance.update(position)

            # Move to history
            self.position_history.append(position)
            del self.positions[position_id]

            # Publish event
            self.event_manager.emit(
                EventType.POSITION_CLOSED,
                dict(position.__dict__),
                source=self.name,
            )

            self.logger.info("Position closed: %s, PnL: %s", position_id, position.realized_pnl)
            return True

        except Exception as e:
            self.error_handler.handle_error(
                e, {"method": "close_position", "position_id": position_id}
            )
            return False

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================

    def get_state(self) -> dict[str, Any]:
        """Get current strategy state"""
        return {
            "strategy_id": self.strategy_id,
            "name": self.name,
            "state": self.state,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "open_positions": len(self.positions),
            "total_positions": len(self.position_history),
            "active_signals": len(self.active_signals),
            "performance": {
                "total_pnl": self.performance.total_pnl,
                "win_rate": self.performance.win_rate,
                "sharpe_ratio": self.performance.sharpe_ratio,
            },
        }

    def get_positions(self) -> list[StrategyPosition]:
        """Get all open positions"""
        return list(self.positions.values())

    def get_performance(self) -> PerformanceMetrics:
        """Get performance metrics"""
        return self.performance

    def get_signals(self) -> list[TradingSignal]:
        """Get active signals"""
        self._cleanup_expired_signals()
        return list(self.active_signals.values())

    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================

    def _initialize_strategy(self) -> None:  # noqa: B027
        """Initialize strategy components"""
        # Override in subclasses for custom initialization
        pass

    def _setup_event_subscriptions(self) -> None:
        """Setup event subscriptions"""
        # Subscribe to risk alerts from the shared event bus
        self.event_manager.subscribe(EventType.ALERT, self._handle_risk_alert)

    def _can_trade(self) -> bool:
        """Check if strategy can trade"""
        # Check daily trade limit
        today = datetime.now(timezone.utc).date()
        if self.last_trade_date != today:
            self.daily_trades = 0
            self.last_trade_date = today

        if self.daily_trades >= self.config.get("max_daily_trades", MAX_DAILY_TRADES):
            return False

        # Check account risk
        total_exposure = sum(p.position_size * p.entry_price for p in self.positions.values())
        return not total_exposure >= self.risk_profile.account_size * self.risk_profile.max_portfolio_risk  # noqa: E501

    def _process_signal(self, signal: TradingSignal) -> None:
        """Process a trading signal"""
        try:
            # Add to active signals
            self.active_signals[signal.signal_id] = signal

            # Calculate position size
            signal.position_size = self.calculate_position_size(signal)

            # Validate and emit on the shared bus so D31 StrategyOrchestrator receives it
            if self.validate_signal(signal):
                self.event_manager.emit(
                    EventType.STRATEGY_SIGNAL,
                    signal.to_dict(),
                    source=self.name,
                )

                # D01-B1: auto_execute is intentionally NOT supported.
                # Raise at construction time so misconfigured strategies fail fast
                # rather than silently dropping orders in production.
                if self.config.get("auto_execute", False):
                    raise ValueError(
                        "D01 auto_execute=True is not supported. "
                        "Wire a LiveEngine to D31 instead."
                    )

        except Exception as e:
            self.error_handler.handle_error(
                e, {"method": "_process_signal", "signal": signal.signal_id}
            )

    def _update_positions(self, market_data: pd.DataFrame) -> None:
        """Update position P&L"""
        for position in self.positions.values():
            if position.symbol in market_data.columns:
                current_price = market_data[position.symbol].iloc[-1]
                position.update_pnl(current_price)

    def _check_exit_conditions(self, market_data: pd.DataFrame) -> None:
        """Check exit conditions for all positions"""
        positions_to_close = []

        for position_id, position in self.positions.items():
            should_exit, reason = self.should_exit_position(position, market_data)

            if should_exit:
                positions_to_close.append((position_id, position.current_price, reason))

        # Close positions
        for position_id, exit_price, reason in positions_to_close:
            self.close_position(position_id, exit_price, reason)

    def check_exit(self, position: Any) -> Any:
        """C2 (v18): Determine whether a position should be closed by ExitMonitor.

        Called once per sweep cycle by ``SpyderR14_ExitMonitor._check_position``.
        The default implementation returns ``None`` (hold the position).
        Subclasses should override this method to implement strategy-specific
        profit-target and stop-loss logic without relying solely on E01/E03.

        Args:
            position: A ``_PositionView`` namedtuple supplied by ExitMonitor,
                with fields: symbol, quantity, avg_cost, current_price,
                unrealised_pnl, strategy_id.

        Returns:
            ``None`` to hold the position, or an ``ExitDecision`` object
            (or any truthy dict with ``{"action": "close", ...}``) to trigger
            an exit signal via the event bus.
        """
        return None  # Default: hold all positions

    def _close_all_positions(self, reason: str) -> None:
        """Close all open positions"""
        position_ids = list(self.positions.keys())
        for position_id in position_ids:
            position = self.positions[position_id]
            self.close_position(position_id, position.current_price, reason)

    def _cleanup_expired_signals(self) -> None:
        """Remove expired signals"""
        expired = []
        for signal_id, signal in self.active_signals.items():
            if not signal.is_valid():
                expired.append(signal_id)

        for signal_id in expired:
            del self.active_signals[signal_id]

    def _update_performance_metrics(self) -> None:
        """Update performance metrics"""
        # Calculate drawdown
        if self.position_history:
            cumulative_pnl = 0
            peak = 0
            max_dd = 0

            for position in sorted(self.position_history, key=lambda x: x.exit_time):
                cumulative_pnl += position.realized_pnl
                peak = max(peak, cumulative_pnl)
                drawdown = (peak - cumulative_pnl) / peak if peak > 0 else 0
                max_dd = max(max_dd, drawdown)

            self.performance.max_drawdown = max_dd

        # Calculate Sharpe ratio (simplified)
        if len(self.performance.daily_pnl) > 30:
            returns = list(self.performance.daily_pnl.values())
            if np.std(returns) > 0:
                self.performance.sharpe_ratio = (np.mean(returns) * 252) / (
                    np.std(returns) * np.sqrt(252)
                )

    def _publish_status_event(self, message: str) -> None:
        """Publish strategy status event"""
        self.event_manager.emit(
            EventType.ALERT,
            {"message": message, "state": self.state, "timestamp": datetime.now(timezone.utc).isoformat()},
            source=self.name,
        )

    def _handle_risk_alert(self, event: Event) -> None:
        """Handle risk alert events"""
        if event.data.get("severity") == "critical":
            self.logger.warning("Critical risk alert received: %s", event.data.get('message'))
            # Potentially pause strategy or close positions
            if self.config.get("pause_on_critical_risk", True):
                self.pause()


# ==============================================================================
# STRATEGY CLASS UTILITY
# ==============================================================================


def is_strategy_class(cls: Any) -> bool:
    """Return True when *cls* is a concrete, instantiable strategy subclass.

    In test runs, modules can be reloaded under alternate package paths, which
    produces distinct ``BaseStrategy`` identity objects.  This helper prefers
    the strict ``issubclass`` check and falls back to duck-typing so that
    test-bootstrap shadowing does not silently drop valid strategy classes.

    Args:
        cls: Object to test.

    Returns:
        True if *cls* is a non-abstract class that is (or quacks like) a
        concrete ``BaseStrategy`` subclass; False otherwise.
    """
    import inspect as _inspect
    if not _inspect.isclass(cls) or _inspect.isabstract(cls):
        return False
    try:
        if issubclass(cls, BaseStrategy):
            return True
    except Exception:
        pass
    # Duck-type fallback: any class with generate_signal is treated as a
    # strategy even when BaseStrategy identity has drifted (test reloads).
    return callable(getattr(cls, "generate_signal", None))


# ==============================================================================
# STRATEGY FACTORY
# ==============================================================================


class StrategyFactory:
    """Factory for creating strategy instances"""

    _strategies: dict[str, type] = {}

    @classmethod
    def register(cls, name: str, strategy_class: type) -> None:
        """Register a strategy class"""
        if not is_strategy_class(strategy_class):
            raise ValueError(f"{strategy_class} must inherit from BaseStrategy")
        cls._strategies[name] = strategy_class

    @classmethod
    def create(
        cls,
        name: str,
        event_manager: EventManager,
        risk_profile: RiskProfile,
        config: dict[str, Any],
    ) -> BaseStrategy:
        """Create a strategy instance"""
        strategy_class = cls._strategies.get(name)
        if not strategy_class:
            raise ValueError(f"Unknown strategy: {name}")

        return strategy_class(name, event_manager, risk_profile, config)

    @classmethod
    def list_strategies(cls) -> list[str]:
        """List registered strategies"""
        return list(cls._strategies.keys())


# ==============================================================================
# MODULE TESTING
# ==============================================================================
if __name__ == "__main__":
    # Example implementation of a concrete strategy
    class SimpleMovingAverageStrategy(BaseStrategy):
        """Simple MA crossover strategy for testing"""

        def __init__(
            self,
            name: str,
            event_manager: EventManager,
            risk_profile: RiskProfile,
            config: dict[str, Any],
        ):
            super().__init__(name, event_manager, risk_profile, config)
            self.fast_period = config.get("fast_period", 10)
            self.slow_period = config.get("slow_period", 20)

        def generate_signals(self, market_data: pd.DataFrame) -> list[TradingSignal]:
            signals = []

            if len(market_data) < self.slow_period:
                return signals

            # Calculate moving averages
            fast_ma = market_data["close"].rolling(self.fast_period).mean()
            slow_ma = market_data["close"].rolling(self.slow_period).mean()

            # Check for crossover
            if fast_ma.iloc[-1] > slow_ma.iloc[-1] and fast_ma.iloc[-2] <= slow_ma.iloc[-2]:
                signal = TradingSignal(
                    signal_id=str(uuid.uuid4()),
                    signal_type=SignalType.BUY,
                    symbol="SPY",
                    strength=SignalStrength.MODERATE,
                    confidence=0.7,
                    entry_price=market_data["close"].iloc[-1],
                    stop_loss=market_data["close"].iloc[-1] * 0.98,
                    take_profit=market_data["close"].iloc[-1] * 1.02,
                    position_size=1,
                    timestamp=datetime.now(timezone.utc),
                    expires_at=datetime.now(timezone.utc) + timedelta(seconds=SIGNAL_EXPIRY_SECONDS),
                )
                signals.append(signal)

            return signals

        def validate_signal(self, signal: TradingSignal) -> bool:
            return signal.confidence >= 0.6

        def calculate_position_size(self, signal: TradingSignal) -> int:
            base_size = self.risk_profile.calculate_position_size(signal.strength)
            return max(1, int(base_size / (signal.entry_price * 100)))

        def should_exit_position(
            self, position: StrategyPosition, market_data: pd.DataFrame
        ) -> tuple[bool, str]:
            current_price = position.current_price

            # Check stop loss
            if position.position_type == PositionType.LONG:
                if current_price <= position.stop_loss:
                    return True, "Stop loss hit"
                if current_price >= position.take_profit:
                    return True, "Take profit hit"
            else:  # SHORT
                if current_price >= position.stop_loss:
                    return True, "Stop loss hit"
                if current_price <= position.take_profit:
                    return True, "Take profit hit"

            return False, ""

    # Test the base strategy

    # Create components
    event_manager = EventManager()
    risk_profile = RiskProfile(
        account_size=100000,
        max_position_size=0.02,
        max_portfolio_risk=0.06,
        max_loss_per_trade=0.01,
    )

    config = {"fast_period": 10, "slow_period": 20, "max_positions": 3, "auto_execute": False}

    # Create strategy
    strategy = SimpleMovingAverageStrategy("SMA_Test", event_manager, risk_profile, config)

    # Test lifecycle

    # Start strategy
    if strategy.start():
        pass

    # Create sample market data
    dates = pd.date_range(end=datetime.now(timezone.utc), periods=50, freq="5min")
    prices = 450 + np.cumsum(np.random.randn(50) * 0.5)
    market_data = pd.DataFrame(
        {
            "timestamp": dates,
            "open": prices + np.random.randn(50) * 0.1,
            "high": prices + abs(np.random.randn(50) * 0.2),
            "low": prices - abs(np.random.randn(50) * 0.2),
            "close": prices,
            "volume": np.random.randint(1000000, 5000000, 50),
        }
    )

    # Process market data
    strategy.process_market_data(market_data)

    # Check for signals
    signals = strategy.get_signals()

    # Create a test position
    if signals:
        position = strategy.add_position(signals[0])
        if position:
            pass

    # Get strategy state
    state = strategy.get_state()

    # Stop strategy
    if strategy.stop():
        pass

