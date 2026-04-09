#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderE_Risk
Module: SpyderE03_StopLossManager.py
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
import uuid
from datetime import datetime, timedelta
from typing import Any
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
import threading
from collections import defaultdict, deque

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np

try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
except ImportError:
    import logging
    SpyderLogger = type('SpyderLogger', (), {
        'get_logger': lambda name: logging.getLogger(name)
    })()

try:
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
except ImportError:
    SpyderErrorHandler = type('SpyderErrorHandler', (), {
        'handle_error': lambda self, e, context: logging.warning("Error in %s: %s", context, e)
    })

try:
    from SpyderU_Utilities.SpyderU07_Constants import OrderType, OrderAction, PositionSide
except ImportError:
    # Define minimal enums if not available
    class OrderType(Enum):
        MARKET = "MARKET"
        LIMIT = "LIMIT"
        STOP = "STOP"
        STOP_LIMIT = "STOP_LIMIT"

    class OrderAction(Enum):
        BUY = "BUY"
        SELL = "SELL"

    class PositionSide(Enum):
        LONG = "LONG"
        SHORT = "SHORT"

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Stop loss parameters
INITIAL_STOP_BUFFER = 0.002  # 0.2% buffer for initial stops
TRAILING_ACTIVATION = 0.01   # 1% profit to activate trailing
TRAILING_DISTANCE = 0.005    # 0.5% trailing distance
BREAKEVEN_THRESHOLD = 0.005  # 0.5% profit for breakeven stop

# ATR-based stops
ATR_MULTIPLIER_TIGHT = 1.5
ATR_MULTIPLIER_NORMAL = 2.0
ATR_MULTIPLIER_WIDE = 3.0

# Time-based stops
TIME_STOP_THRESHOLD = 0.30  # 30% of expected hold time
MAX_HOLD_TIME_MULTIPLIER = 2.0  # 2x expected hold time

# Volatility adjustments
HIGH_VOL_STOP_WIDENING = 1.5
LOW_VOL_STOP_TIGHTENING = 0.8

# Position-based adjustments
PARTIAL_CLOSE_THRESHOLD = 0.02  # 2% profit for partial close
SCALE_OUT_PERCENTAGES = [0.33, 0.50, 1.00]  # Scale out levels

# ==============================================================================
# ENUMS
# ==============================================================================
class StopType(Enum):
    """Types of stop losses."""
    FIXED = auto()
    TRAILING = auto()
    BREAKEVEN = auto()
    TIME_BASED = auto()
    VOLATILITY_BASED = auto()
    TECHNICAL = auto()
    PARTIAL = auto()

class StopStatus(Enum):
    """Stop order status."""
    PENDING = auto()
    ACTIVE = auto()
    TRIGGERED = auto()
    CANCELLED = auto()
    MODIFIED = auto()
    SUBMITTED = auto()  # Sent to broker
    REJECTED = auto()   # Broker rejected

class TrailingMethod(Enum):
    """Trailing stop methods."""
    PERCENTAGE = auto()
    ATR = auto()
    PARABOLIC_SAR = auto()
    CHANDELIER = auto()
    MOVING_AVERAGE = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class StopLossConfig:
    """Stop loss configuration."""
    stop_type: StopType = StopType.TRAILING
    initial_stop_method: str = "atr"  # 'atr', 'percentage', 'technical'
    trailing_method: TrailingMethod = TrailingMethod.PERCENTAGE
    use_breakeven: bool = True
    use_time_stops: bool = True
    use_partial_exits: bool = True
    atr_multiplier: float = ATR_MULTIPLIER_NORMAL
    trailing_activation_pct: float = TRAILING_ACTIVATION
    trailing_distance_pct: float = TRAILING_DISTANCE
    breakeven_threshold_pct: float = BREAKEVEN_THRESHOLD
    max_stop_width_pct: float = 0.05  # 5% maximum stop width
    partial_exit_levels: list[float] = field(default_factory=lambda: [0.02, 0.04, 0.06])
    scale_out_percentages: list[float] = field(default_factory=lambda: SCALE_OUT_PERCENTAGES.copy())

@dataclass
class StopOrder:
    """Stop order details."""
    order_id: str
    position_id: str
    stop_type: StopType
    stop_price: float
    original_stop: float
    activation_price: float | None
    quantity: int
    side: PositionSide
    status: StopStatus
    created_at: datetime
    last_updated: datetime
    broker_order_id: str | None = None
    triggered_at: datetime | None = None
    trigger_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class PositionStops:
    """All stops for a position."""
    position_id: str
    entry_price: float
    current_price: float
    position_side: PositionSide
    quantity: int
    initial_stop: StopOrder
    trailing_stop: StopOrder | None = None
    breakeven_stop: StopOrder | None = None
    time_stop: StopOrder | None = None
    partial_stops: list[StopOrder] = field(default_factory=list)
    stop_history: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_checked: datetime = field(default_factory=datetime.now)

# ==============================================================================
# STOP LOSS MANAGER CLASS
# ==============================================================================
class StopLossManager:
    """
    Manages stop loss orders and trailing stops.

    Provides comprehensive stop loss management including dynamic adjustment,
    multiple stop types, position-specific stop strategies, and broker integration.
    Thread-safe implementation with real-time monitoring.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        position_stops: Active stops by position ID

    Example:
        >>> manager = StopLossManager()
        >>> stops = manager.create_position_stops(
        ...     position_id="POS001",
        ...     entry_price=400.0,
        ...     position_side=PositionSide.LONG,
        ...     market_data=df,
        ...     strategy="momentum"
        ... )
        >>> manager.update_stops("POS001", 405.0, df)
    """

    def __init__(self, broker_client=None, event_manager=None):
        """
        Initialize stop loss manager.

        Args:
            broker_client: Optional broker client for order placement
            event_manager: Optional event manager for notifications
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # External integrations
        self.broker_client = broker_client
        self.event_manager = event_manager

        # Configuration
        self.default_config = StopLossConfig()
        self.strategy_configs: dict[str, StopLossConfig] = {}

        # State management with thread safety
        self._lock = threading.RLock()

        # Active stops
        self.position_stops: dict[str, PositionStops] = {}
        self.stop_orders: dict[str, StopOrder] = {}
        self.broker_order_map: dict[str, str] = {}  # broker_id -> our_id

        # Tracking
        self.triggered_stops: deque = deque(maxlen=1000)
        self.stop_performance: dict[str, list[float]] = {
            stop_type: [] for stop_type in StopType
        }

        # Market data cache
        self.market_data_cache: dict[str, pd.DataFrame] = {}
        self.atr_cache: dict[str, float] = {}

        # Monitoring
        self._monitoring_active = False
        self._monitor_thread: threading.Thread | None = None

        self.logger.info("StopLossManager initialized")

    # ==========================================================================
    # PUBLIC METHODS - STOP CREATION
    # ==========================================================================
    def create_position_stops(
        self,
        position_id: str,
        entry_price: float,
        position_side: PositionSide,
        quantity: int,
        market_data: pd.DataFrame,
        strategy: str,
        config: StopLossConfig | None = None
    ) -> PositionStops:
        """
        Create all stops for a new position.

        Args:
            position_id: Unique position identifier
            entry_price: Position entry price
            position_side: LONG or SHORT
            quantity: Position size
            market_data: Recent market data
            strategy: Strategy name for configuration
            config: Optional custom configuration

        Returns:
            PositionStops object with all configured stops
        """
        try:
            with self._lock:
                # Use strategy config or default
                config = config or self.strategy_configs.get(strategy, self.default_config)

                # Calculate initial stop
                initial_stop_price = self._calculate_initial_stop(
                    entry_price, position_side, market_data, config
                )

                # Validate stop price
                if not self._validate_stop_price(initial_stop_price, entry_price, position_side):
                    self.logger.error("Invalid stop price calculated: %s", initial_stop_price)
                    initial_stop_price = self._calculate_emergency_stop(entry_price, position_side)

                # Create initial stop order
                initial_stop = StopOrder(
                    order_id=f"{position_id}_initial_{uuid.uuid4().hex[:8]}",
                    position_id=position_id,
                    stop_type=StopType.FIXED,
                    stop_price=initial_stop_price,
                    original_stop=initial_stop_price,
                    activation_price=entry_price,
                    quantity=quantity,
                    side=position_side,
                    status=StopStatus.PENDING,
                    created_at=datetime.now(),
                    last_updated=datetime.now(),
                    metadata={
                        'strategy': strategy,
                        'method': config.initial_stop_method,
                        'atr_multiplier': config.atr_multiplier if config.initial_stop_method == 'atr' else None
                    }
                )

                # Create position stops object
                position_stops = PositionStops(
                    position_id=position_id,
                    entry_price=entry_price,
                    current_price=entry_price,
                    position_side=position_side,
                    quantity=quantity,
                    initial_stop=initial_stop
                )

                # Set up additional stops if configured
                if config.use_breakeven:
                    self._setup_breakeven_stop(position_stops, config)

                if config.use_time_stops:
                    self._setup_time_stop(position_stops, config, strategy)

                if config.use_partial_exits:
                    self._setup_partial_exits(position_stops, config)

                # Store position stops
                self.position_stops[position_id] = position_stops
                self.stop_orders[initial_stop.order_id] = initial_stop

                # Submit initial stop to broker
                self._submit_stop_to_broker(initial_stop)

                # Log creation
                self.logger.info(
                    f"Created stops for position {position_id}: "
                    f"initial stop at {initial_stop_price:.2f}"
                )

                return position_stops

        except Exception as e:
            self.logger.error("Error creating position stops: %s", e)
            self.error_handler.handle_error(e, {"method": "create_position_stops"})

            # Return minimal stop setup
            return self._create_emergency_position_stops(
                position_id, entry_price, position_side, quantity
            )

    def update_stops(
        self,
        position_id: str,
        current_price: float,
        market_data: pd.DataFrame
    ) -> list[StopOrder]:
        """
        Update stops for a position based on current price.

        Args:
            position_id: Position identifier
            current_price: Current market price
            market_data: Recent market data

        Returns:
            List of updated stop orders
        """
        if position_id not in self.position_stops:
            return []

        with self._lock:
            position_stops = self.position_stops[position_id]
            position_stops.current_price = current_price
            position_stops.last_checked = datetime.now()

            updated_stops = []

            try:
                # Cache market data
                self.market_data_cache[position_id] = market_data

                # Check for trailing stop activation
                if self._should_activate_trailing(position_stops):
                    trailing_stop = self._activate_trailing_stop(position_stops, market_data)
                    if trailing_stop:
                        updated_stops.append(trailing_stop)

                # Update trailing stop if active
                if position_stops.trailing_stop and position_stops.trailing_stop.status == StopStatus.ACTIVE:
                    if self._update_trailing_stop(position_stops, market_data):
                        updated_stops.append(position_stops.trailing_stop)

                # Check for breakeven stop
                if self._should_move_to_breakeven(position_stops):
                    breakeven_stop = self._move_to_breakeven(position_stops)
                    if breakeven_stop:
                        updated_stops.append(breakeven_stop)

                # Check time-based stops
                if position_stops.time_stop:
                    if self._check_time_stop(position_stops):
                        updated_stops.append(position_stops.time_stop)

                # Check for partial exit opportunities
                partial_exits = self._check_partial_exits(position_stops, current_price)
                updated_stops.extend(partial_exits)

                # Update stop history
                if updated_stops:
                    self._update_stop_history(position_stops, updated_stops)

                return updated_stops

            except Exception as e:
                self.logger.error("Error updating stops: %s", e)
                self.error_handler.handle_error(e, {"method": "update_stops"})
                return []

    def check_stop_hit(self, position_id: str, current_price: float) -> StopOrder | None:
        """
        Check if any stop has been hit.

        Args:
            position_id: Position identifier
            current_price: Current market price

        Returns:
            Triggered stop order if hit, None otherwise
        """
        if position_id not in self.position_stops:
            return None

        with self._lock:
            position_stops = self.position_stops[position_id]
            active_stop = self._get_active_stop(position_stops)

            if not active_stop:
                return None

            # Check if stop hit based on position side
            stop_hit = False
            if position_stops.position_side == PositionSide.LONG:
                stop_hit = current_price <= active_stop.stop_price
            else:  # SHORT
                stop_hit = current_price >= active_stop.stop_price

            if stop_hit:
                # Mark as triggered
                active_stop.status = StopStatus.TRIGGERED
                active_stop.triggered_at = datetime.now()
                active_stop.trigger_reason = f"Stop hit at {current_price:.2f}"

                # Add to triggered history
                self.triggered_stops.append({
                    'stop_order': asdict(active_stop),
                    'position_stops': {
                        'position_id': position_stops.position_id,
                        'entry_price': position_stops.entry_price,
                        'exit_price': current_price
                    },
                    'timestamp': datetime.now()
                })

                # Record performance
                self._record_stop_performance(position_stops, active_stop, current_price)

                # Notify
                if self.event_manager:
                    self._emit_stop_event('triggered', active_stop, position_stops)

                self.logger.warning(
                    f"Stop triggered for {position_id}: "
                    f"{active_stop.stop_type.name} at {current_price:.2f}"
                )

                return active_stop

            return None

    # ==========================================================================
    # PRIVATE METHODS - STOP CALCULATIONS
    # ==========================================================================
    def _calculate_initial_stop(
        self,
        entry_price: float,
        position_side: PositionSide,
        market_data: pd.DataFrame,
        config: StopLossConfig
    ) -> float:
        """Calculate initial stop price."""
        if config.initial_stop_method == "atr":
            return self._calculate_atr_stop(
                entry_price, position_side, market_data, config.atr_multiplier
            )
        elif config.initial_stop_method == "percentage":
            return self._calculate_percentage_stop(
                entry_price, position_side, config.max_stop_width_pct
            )
        elif config.initial_stop_method == "technical":
            return self._calculate_technical_stop(
                entry_price, position_side, market_data
            )
        else:
            # Default to percentage
            return self._calculate_percentage_stop(
                entry_price, position_side, 0.02  # 2% default
            )

    def _calculate_atr_stop(
        self,
        entry_price: float,
        position_side: PositionSide,
        market_data: pd.DataFrame,
        atr_multiplier: float
    ) -> float:
        """Calculate ATR-based stop price."""
        try:
            # Calculate ATR
            if len(market_data) < 14:
                # Not enough data, use percentage fallback
                return self._calculate_percentage_stop(entry_price, position_side, 0.02)

            # Calculate ATR
            high = market_data['high'].values
            low = market_data['low'].values
            close = market_data['close'].values

            # True Range
            tr = np.maximum(
                high - low,
                np.maximum(
                    np.abs(high - np.roll(close, 1)),
                    np.abs(low - np.roll(close, 1))
                )
            )

            # ATR (14-period)
            atr = np.mean(tr[-14:])

            # Cache ATR
            self.atr_cache[f"{entry_price}_{datetime.now().date()}"] = atr

            # Calculate stop
            stop_distance = atr * atr_multiplier

            if position_side == PositionSide.LONG:
                stop_price = entry_price - stop_distance
            else:  # SHORT
                stop_price = entry_price + stop_distance

            # Apply buffer
            if position_side == PositionSide.LONG:
                stop_price *= (1 - INITIAL_STOP_BUFFER)
            else:
                stop_price *= (1 + INITIAL_STOP_BUFFER)

            return round(stop_price, 2)

        except Exception as e:
            self.logger.error("ATR calculation error: %s", e)
            return self._calculate_percentage_stop(entry_price, position_side, 0.02)

    def _calculate_percentage_stop(
        self,
        entry_price: float,
        position_side: PositionSide,
        percentage: float
    ) -> float:
        """Calculate percentage-based stop price."""
        if position_side == PositionSide.LONG:
            stop_price = entry_price * (1 - percentage)
        else:  # SHORT
            stop_price = entry_price * (1 + percentage)

        return round(stop_price, 2)

    def _calculate_technical_stop(
        self,
        entry_price: float,
        position_side: PositionSide,
        market_data: pd.DataFrame
    ) -> float:
        """Calculate stop based on technical levels."""
        try:
            # Find recent support/resistance
            if len(market_data) < 20:
                return self._calculate_percentage_stop(entry_price, position_side, 0.02)

            # Simple support/resistance: recent lows/highs
            recent_lows = market_data['low'].rolling(5).min()
            recent_highs = market_data['high'].rolling(5).max()

            if position_side == PositionSide.LONG:
                # Use recent support
                support_levels = recent_lows.dropna().values
                if len(support_levels) > 0:
                    stop_price = support_levels[-1] * (1 - INITIAL_STOP_BUFFER)
                else:
                    stop_price = entry_price * 0.98
            else:  # SHORT
                # Use recent resistance
                resistance_levels = recent_highs.dropna().values
                if len(resistance_levels) > 0:
                    stop_price = resistance_levels[-1] * (1 + INITIAL_STOP_BUFFER)
                else:
                    stop_price = entry_price * 1.02

            return round(stop_price, 2)

        except Exception as e:
            self.logger.error("Technical stop calculation error: %s", e)
            return self._calculate_percentage_stop(entry_price, position_side, 0.02)

    def _calculate_emergency_stop(self, entry_price: float, position_side: PositionSide) -> float:
        """Calculate emergency stop when normal calculations fail."""
        # Use conservative 3% stop
        return self._calculate_percentage_stop(entry_price, position_side, 0.03)

    # ==========================================================================
    # PRIVATE METHODS - STOP MANAGEMENT
    # ==========================================================================
    def _should_activate_trailing(self, position_stops: PositionStops) -> bool:
        """Check if trailing stop should be activated."""
        # Already has trailing stop
        if position_stops.trailing_stop:
            return False

        # Check profit threshold
        entry_price = position_stops.entry_price
        current_price = position_stops.current_price

        if position_stops.position_side == PositionSide.LONG:
            profit_pct = (current_price - entry_price) / entry_price
        else:  # SHORT
            profit_pct = (entry_price - current_price) / entry_price

        config = self._get_position_config(position_stops)
        return profit_pct >= config.trailing_activation_pct

    def _activate_trailing_stop(
        self,
        position_stops: PositionStops,
        market_data: pd.DataFrame
    ) -> StopOrder | None:
        """Activate trailing stop."""
        config = self._get_position_config(position_stops)

        # Calculate trailing stop price
        if config.trailing_method == TrailingMethod.PERCENTAGE:
            if position_stops.position_side == PositionSide.LONG:
                stop_price = position_stops.current_price * (1 - config.trailing_distance_pct)
            else:  # SHORT
                stop_price = position_stops.current_price * (1 + config.trailing_distance_pct)
        elif config.trailing_method == TrailingMethod.ATR:
            stop_price = self._calculate_atr_stop(
                position_stops.current_price,
                position_stops.position_side,
                market_data,
                config.atr_multiplier * 0.75  # Tighter for trailing
            )
        else:
            # Default to percentage
            if position_stops.position_side == PositionSide.LONG:
                stop_price = position_stops.current_price * (1 - config.trailing_distance_pct)
            else:
                stop_price = position_stops.current_price * (1 + config.trailing_distance_pct)

        stop_price = round(stop_price, 2)

        # Create trailing stop
        trailing_stop = StopOrder(
            order_id=f"{position_stops.position_id}_trailing_{uuid.uuid4().hex[:8]}",
            position_id=position_stops.position_id,
            stop_type=StopType.TRAILING,
            stop_price=stop_price,
            original_stop=stop_price,
            activation_price=position_stops.current_price,
            quantity=position_stops.quantity,
            side=position_stops.position_side,
            status=StopStatus.PENDING,
            created_at=datetime.now(),
            last_updated=datetime.now(),
            metadata={
                'method': config.trailing_method.name,
                'distance': config.trailing_distance_pct
            }
        )

        # Cancel initial stop and activate trailing
        if position_stops.initial_stop.status == StopStatus.ACTIVE:
            self._cancel_stop_order(position_stops.initial_stop)

        position_stops.trailing_stop = trailing_stop
        self.stop_orders[trailing_stop.order_id] = trailing_stop

        # Submit to broker
        self._submit_stop_to_broker(trailing_stop)

        self.logger.info(
            f"Activated trailing stop for {position_stops.position_id} at {stop_price:.2f}"
        )

        return trailing_stop

    def _update_trailing_stop(
        self,
        position_stops: PositionStops,
        market_data: pd.DataFrame
    ) -> bool:
        """Update trailing stop price if needed."""
        trailing_stop = position_stops.trailing_stop
        if not trailing_stop or trailing_stop.status != StopStatus.ACTIVE:
            return False

        config = self._get_position_config(position_stops)
        old_stop = trailing_stop.stop_price

        # Calculate new stop price based on method
        if config.trailing_method == TrailingMethod.PERCENTAGE:
            if position_stops.position_side == PositionSide.LONG:
                new_stop = position_stops.current_price * (1 - config.trailing_distance_pct)
                # Only move up for longs
                if new_stop > old_stop:
                    trailing_stop.stop_price = round(new_stop, 2)
            else:  # SHORT
                new_stop = position_stops.current_price * (1 + config.trailing_distance_pct)
                # Only move down for shorts
                if new_stop < old_stop:
                    trailing_stop.stop_price = round(new_stop, 2)

        # Check if stop was updated
        if trailing_stop.stop_price != old_stop:
            trailing_stop.last_updated = datetime.now()

            # Update with broker
            self._modify_stop_with_broker(trailing_stop)

            self.logger.debug(
                f"Updated trailing stop for {position_stops.position_id}: "
                f"{old_stop:.2f} -> {trailing_stop.stop_price:.2f}"
            )

            return True

        return False

    def _should_move_to_breakeven(self, position_stops: PositionStops) -> bool:
        """Check if stop should move to breakeven."""
        # Already has breakeven stop or not configured
        if position_stops.breakeven_stop:
            return False

        config = self._get_position_config(position_stops)
        if not config.use_breakeven:
            return False

        # Check profit threshold
        entry_price = position_stops.entry_price
        current_price = position_stops.current_price

        if position_stops.position_side == PositionSide.LONG:
            profit_pct = (current_price - entry_price) / entry_price
        else:  # SHORT
            profit_pct = (entry_price - current_price) / entry_price

        return profit_pct >= config.breakeven_threshold_pct

    def _move_to_breakeven(self, position_stops: PositionStops) -> StopOrder | None:
        """Move stop to breakeven."""
        # Calculate breakeven price (entry + small buffer for costs)
        if position_stops.position_side == PositionSide.LONG:
            breakeven_price = position_stops.entry_price * 1.001  # 0.1% buffer
        else:  # SHORT
            breakeven_price = position_stops.entry_price * 0.999

        breakeven_price = round(breakeven_price, 2)

        # Create breakeven stop
        breakeven_stop = StopOrder(
            order_id=f"{position_stops.position_id}_breakeven_{uuid.uuid4().hex[:8]}",
            position_id=position_stops.position_id,
            stop_type=StopType.BREAKEVEN,
            stop_price=breakeven_price,
            original_stop=breakeven_price,
            activation_price=position_stops.current_price,
            quantity=position_stops.quantity,
            side=position_stops.position_side,
            status=StopStatus.PENDING,
            created_at=datetime.now(),
            last_updated=datetime.now(),
            metadata={'moved_at_price': position_stops.current_price}
        )

        # Update active stop
        active_stop = self._get_active_stop(position_stops)
        if active_stop:
            self._cancel_stop_order(active_stop)

        position_stops.breakeven_stop = breakeven_stop
        self.stop_orders[breakeven_stop.order_id] = breakeven_stop

        # Submit to broker
        self._submit_stop_to_broker(breakeven_stop)

        self.logger.info(
            f"Moved stop to breakeven for {position_stops.position_id} at {breakeven_price:.2f}"
        )

        return breakeven_stop

    # ==========================================================================
    # PRIVATE METHODS - BROKER INTEGRATION
    # ==========================================================================
    def _submit_stop_to_broker(self, stop_order: StopOrder) -> bool:
        """Submit stop order to broker."""
        if not self.broker_client:
            stop_order.status = StopStatus.ACTIVE  # Simulate activation
            return True

        try:
            # Prepare broker order
            broker_order = {
                'action': OrderAction.SELL if stop_order.side == PositionSide.LONG else OrderAction.BUY,
                'quantity': stop_order.quantity,
                'order_type': OrderType.STOP,
                'stop_price': stop_order.stop_price,
                'time_in_force': 'GTC',  # Good Till Cancelled
                'order_ref': stop_order.order_id
            }

            # Submit to broker
            broker_order_id = self.broker_client.place_order(broker_order)

            if broker_order_id:
                stop_order.broker_order_id = broker_order_id
                stop_order.status = StopStatus.SUBMITTED
                self.broker_order_map[broker_order_id] = stop_order.order_id

                self.logger.info("Stop order submitted to broker: %s", stop_order.order_id)
                return True
            else:
                stop_order.status = StopStatus.REJECTED
                self.logger.error("Broker rejected stop order: %s", stop_order.order_id)
                return False

        except Exception as e:
            self.logger.error("Error submitting stop to broker: %s", e)
            stop_order.status = StopStatus.ACTIVE  # Fallback to manual monitoring
            return False

    def _modify_stop_with_broker(self, stop_order: StopOrder) -> bool:
        """Modify existing stop order with broker."""
        if not self.broker_client or not stop_order.broker_order_id:
            return True  # Simulated success

        try:
            # Modify order
            success = self.broker_client.modify_order(
                stop_order.broker_order_id,
                {'stop_price': stop_order.stop_price}
            )

            if success:
                self.logger.debug("Stop order modified with broker: %s", stop_order.order_id)
                return True
            else:
                self.logger.error("Failed to modify stop order: %s", stop_order.order_id)
                return False

        except Exception as e:
            self.logger.error("Error modifying stop with broker: %s", e)
            return False

    def _cancel_stop_order(self, stop_order: StopOrder) -> bool:
        """Cancel stop order."""
        stop_order.status = StopStatus.CANCELLED

        if self.broker_client and stop_order.broker_order_id:
            try:
                self.broker_client.cancel_order(stop_order.broker_order_id)
                self.logger.debug("Stop order cancelled with broker: %s", stop_order.order_id)
            except Exception as e:
                self.logger.error("Error cancelling stop with broker: %s", e)

        return True

    # ==========================================================================
    # PRIVATE METHODS - PARTIAL EXITS
    # ==========================================================================
    def _setup_partial_exits(self, position_stops: PositionStops, config: StopLossConfig) -> None:
        """Set up partial exit levels."""
        if not config.use_partial_exits or not config.partial_exit_levels:
            return

        for i, exit_level in enumerate(config.partial_exit_levels):
            scale_pct = config.scale_out_percentages[i] if i < len(config.scale_out_percentages) else 1.0
            quantity = int(position_stops.quantity * scale_pct)

            if quantity > 0:
                partial_stop = StopOrder(
                    order_id=f"{position_stops.position_id}_partial_{i}_{uuid.uuid4().hex[:8]}",
                    position_id=position_stops.position_id,
                    stop_type=StopType.PARTIAL,
                    stop_price=0,  # Will be calculated when profit reached
                    original_stop=0,
                    activation_price=None,
                    quantity=quantity,
                    side=position_stops.position_side,
                    status=StopStatus.PENDING,
                    created_at=datetime.now(),
                    last_updated=datetime.now(),
                    metadata={
                        'exit_level': exit_level,
                        'scale_percentage': scale_pct,
                        'level_index': i
                    }
                )

                position_stops.partial_stops.append(partial_stop)
                self.stop_orders[partial_stop.order_id] = partial_stop

    def _check_partial_exits(self, position_stops: PositionStops, current_price: float) -> list[StopOrder]:
        """Check if any partial exit levels have been reached."""
        triggered_partials = []

        for partial_stop in position_stops.partial_stops:
            if partial_stop.status != StopStatus.PENDING:
                continue

            # Calculate profit percentage
            if position_stops.position_side == PositionSide.LONG:
                profit_pct = (current_price - position_stops.entry_price) / position_stops.entry_price
            else:
                profit_pct = (position_stops.entry_price - current_price) / position_stops.entry_price

            exit_level = partial_stop.metadata.get('exit_level', 0)

            if profit_pct >= exit_level:
                # Activate partial exit
                partial_stop.status = StopStatus.TRIGGERED
                partial_stop.triggered_at = datetime.now()
                partial_stop.stop_price = current_price
                partial_stop.trigger_reason = f"Partial exit at {profit_pct:.1%} profit"

                triggered_partials.append(partial_stop)

                self.logger.info(
                    f"Partial exit triggered for {position_stops.position_id}: "
                    f"{partial_stop.metadata['scale_percentage']:.0%} at {current_price:.2f}"
                )

        return triggered_partials

    # ==========================================================================
    # PRIVATE METHODS - TIME STOPS
    # ==========================================================================
    def _setup_time_stop(self, position_stops: PositionStops, config: StopLossConfig, strategy: str) -> None:
        """Set up time-based stop."""
        if not config.use_time_stops:
            return

        # Get expected hold time for strategy (would come from strategy config)
        expected_hold_hours = self._get_expected_hold_time(strategy)

        if expected_hold_hours <= 0:
            return

        # Calculate time stop trigger
        max_hold_time = timedelta(hours=expected_hold_hours * MAX_HOLD_TIME_MULTIPLIER)
        trigger_time = position_stops.created_at + max_hold_time

        time_stop = StopOrder(
            order_id=f"{position_stops.position_id}_time_{uuid.uuid4().hex[:8]}",
            position_id=position_stops.position_id,
            stop_type=StopType.TIME_BASED,
            stop_price=0,  # Will use market price when triggered
            original_stop=0,
            activation_price=None,
            quantity=position_stops.quantity,
            side=position_stops.position_side,
            status=StopStatus.PENDING,
            created_at=datetime.now(),
            last_updated=datetime.now(),
            metadata={
                'trigger_time': trigger_time.isoformat(),
                'expected_hold_hours': expected_hold_hours,
                'max_hold_hours': expected_hold_hours * MAX_HOLD_TIME_MULTIPLIER
            }
        )

        position_stops.time_stop = time_stop
        self.stop_orders[time_stop.order_id] = time_stop

    def _check_time_stop(self, position_stops: PositionStops) -> bool:
        """Check if time stop should be triggered."""
        time_stop = position_stops.time_stop
        if not time_stop or time_stop.status != StopStatus.PENDING:
            return False

        trigger_time = datetime.fromisoformat(time_stop.metadata['trigger_time'])

        if datetime.now() >= trigger_time:
            time_stop.status = StopStatus.TRIGGERED
            time_stop.triggered_at = datetime.now()
            time_stop.stop_price = position_stops.current_price
            time_stop.trigger_reason = "Maximum hold time exceeded"

            self.logger.warning(
                f"Time stop triggered for {position_stops.position_id} after "
                f"{time_stop.metadata['max_hold_hours']:.1f} hours"
            )

            return True

        return False

    def _get_expected_hold_time(self, strategy: str) -> float:
        """Get expected hold time for strategy in hours."""
        # Would come from strategy configuration
        strategy_hold_times = {
            'scalping': 0.5,      # 30 minutes
            'daytrading': 2.0,    # 2 hours
            'momentum': 4.0,      # 4 hours
            'swing': 48.0,        # 2 days
            'position': 168.0     # 1 week
        }

        return strategy_hold_times.get(strategy, 24.0)  # Default 1 day

    # ==========================================================================
    # PRIVATE METHODS - UTILITIES
    # ==========================================================================
    def _get_active_stop(self, position_stops: PositionStops) -> StopOrder | None:
        """Get the currently active stop order."""
        # Priority: Trailing > Breakeven > Initial
        if position_stops.trailing_stop and position_stops.trailing_stop.status == StopStatus.ACTIVE:
            return position_stops.trailing_stop
        elif position_stops.breakeven_stop and position_stops.breakeven_stop.status == StopStatus.ACTIVE:
            return position_stops.breakeven_stop
        elif position_stops.initial_stop.status == StopStatus.ACTIVE:
            return position_stops.initial_stop

        return None

    def _get_position_config(self, position_stops: PositionStops) -> StopLossConfig:
        """Get configuration for position."""
        strategy = position_stops.initial_stop.metadata.get('strategy', 'default')
        return self.strategy_configs.get(strategy, self.default_config)

    def _validate_stop_price(self, stop_price: float, entry_price: float,
                           position_side: PositionSide) -> bool:
        """Validate stop price is logical."""
        if stop_price <= 0:
            return False

        # Check stop is on correct side
        if position_side == PositionSide.LONG:
            return stop_price < entry_price
        else:  # SHORT
            return stop_price > entry_price

    def _create_emergency_position_stops(
        self,
        position_id: str,
        entry_price: float,
        position_side: PositionSide,
        quantity: int
    ) -> PositionStops:
        """Create emergency stops when normal creation fails."""
        # Simple 3% stop
        stop_price = self._calculate_emergency_stop(entry_price, position_side)

        emergency_stop = StopOrder(
            order_id=f"{position_id}_emergency_{uuid.uuid4().hex[:8]}",
            position_id=position_id,
            stop_type=StopType.FIXED,
            stop_price=stop_price,
            original_stop=stop_price,
            activation_price=entry_price,
            quantity=quantity,
            side=position_side,
            status=StopStatus.ACTIVE,
            created_at=datetime.now(),
            last_updated=datetime.now(),
            metadata={'emergency': True}
        )

        return PositionStops(
            position_id=position_id,
            entry_price=entry_price,
            current_price=entry_price,
            position_side=position_side,
            quantity=quantity,
            initial_stop=emergency_stop
        )

    def _update_stop_history(self, position_stops: PositionStops, updated_stops: list[StopOrder]) -> None:
        """Update stop history for position."""
        for stop in updated_stops:
            position_stops.stop_history.append({
                'timestamp': datetime.now().isoformat(),
                'stop_type': stop.stop_type.name,
                'stop_price': stop.stop_price,
                'action': 'updated' if stop.status == StopStatus.ACTIVE else stop.status.name,
                'metadata': stop.metadata
            })

    def _record_stop_performance(self, position_stops: PositionStops,
                               stop_order: StopOrder, exit_price: float) -> None:
        """Record stop performance for analysis."""
        # Calculate performance
        entry_price = position_stops.entry_price

        if position_stops.position_side == PositionSide.LONG:
            performance = (exit_price - entry_price) / entry_price
        else:  # SHORT
            performance = (entry_price - exit_price) / entry_price

        # Record by stop type
        self.stop_performance[stop_order.stop_type.name].append(performance)

    def _emit_stop_event(self, action: str, stop_order: StopOrder, position_stops: PositionStops) -> None:
        """Emit stop-related event."""
        if not self.event_manager:
            return

        event_data = {
            'action': f'stop_{action}',
            'stop_order': asdict(stop_order),
            'position': {
                'position_id': position_stops.position_id,
                'entry_price': position_stops.entry_price,
                'current_price': position_stops.current_price,
                'side': position_stops.position_side.name
            },
            'timestamp': datetime.now().isoformat()
        }

        self.event_manager.emit('STOP_EVENT', event_data)

    # ==========================================================================
    # PUBLIC METHODS - CONFIGURATION
    # ==========================================================================
    def configure_strategy_stops(self, strategy: str, config: StopLossConfig) -> None:
        """
        Configure stop loss settings for a strategy.

        Args:
            strategy: Strategy name
            config: Stop loss configuration
        """
        with self._lock:
            self.strategy_configs[strategy] = config
            self.logger.info("Configured stops for strategy %s", strategy)

    def get_position_stops(self, position_id: str) -> PositionStops | None:
        """Get stops for a position."""
        with self._lock:
            return self.position_stops.get(position_id)

    def get_active_stop_price(self, position_id: str) -> float | None:
        """Get current active stop price for position."""
        with self._lock:
            position_stops = self.position_stops.get(position_id)
            if not position_stops:
                return None

            active_stop = self._get_active_stop(position_stops)
            return active_stop.stop_price if active_stop else None

    def cancel_stops(self, position_id: str) -> None:
        """Cancel all stops for a position."""
        with self._lock:
            if position_id not in self.position_stops:
                return

            position_stops = self.position_stops[position_id]

            # Cancel all stops
            for stop in [position_stops.initial_stop, position_stops.trailing_stop,
                        position_stops.breakeven_stop, position_stops.time_stop]:
                if stop and stop.status in [StopStatus.ACTIVE, StopStatus.PENDING]:
                    self._cancel_stop_order(stop)

            # Cancel partial stops
            for partial_stop in position_stops.partial_stops:
                if partial_stop.status in [StopStatus.ACTIVE, StopStatus.PENDING]:
                    self._cancel_stop_order(partial_stop)

            self.logger.info("Cancelled all stops for position %s", position_id)

    def cleanup_position(self, position_id: str) -> None:
        """Clean up stops for closed position."""
        with self._lock:
            if position_id in self.position_stops:
                # Cancel any remaining stops
                self.cancel_stops(position_id)

                # Remove from tracking
                del self.position_stops[position_id]

                # Clean up stop orders
                self.stop_orders = {
                    oid: stop for oid, stop in self.stop_orders.items()
                    if stop.position_id != position_id
                }

                self.logger.info("Cleaned up stops for position %s", position_id)

    # ==========================================================================
    # PUBLIC METHODS - ANALYSIS
    # ==========================================================================
    def get_stop_performance_stats(self) -> dict[str, dict[str, float]]:
        """Get stop performance statistics."""
        stats = {}

        with self._lock:
            for stop_type, performances in self.stop_performance.items():
                if performances:
                    stats[stop_type] = {
                        'count': len(performances),
                        'avg_performance': np.mean(performances),
                        'median_performance': np.median(performances),
                        'best': max(performances),
                        'worst': min(performances),
                        'positive_rate': sum(1 for p in performances if p > 0) / len(performances),
                        'std_dev': np.std(performances)
                    }

        return stats

    def get_active_stops_summary(self) -> dict[str, Any]:
        """Get summary of all active stops."""
        with self._lock:
            active_positions = len(self.position_stops)

            stop_types = defaultdict(int)
            total_risk = 0

            for position_stops in self.position_stops.values():
                active_stop = self._get_active_stop(position_stops)
                if active_stop:
                    stop_types[active_stop.stop_type.name] += 1

                    # Calculate risk
                    if position_stops.position_side == PositionSide.LONG:
                        risk = position_stops.entry_price - active_stop.stop_price
                    else:
                        risk = active_stop.stop_price - position_stops.entry_price

                    total_risk += risk * position_stops.quantity

            return {
                'active_positions': active_positions,
                'stop_type_distribution': dict(stop_types),
                'total_risk_amount': total_risk,
                'triggered_stops_24h': sum(
                    1 for stop in self.triggered_stops
                    if datetime.now() - stop['timestamp'] <= timedelta(hours=24)
                )
            }

    # ==========================================================================
    # PUBLIC METHODS - MONITORING
    # ==========================================================================
    def start_monitoring(self) -> None:
        """Start stop monitoring thread."""
        if not self._monitoring_active:
            self._monitoring_active = True
            self._monitor_thread = threading.Thread(
                target=self._monitoring_loop,
                name="StopMonitor",
                daemon=True
            )
            self._monitor_thread.start()
            self.logger.info("Stop monitoring started")

    def stop_monitoring(self) -> None:
        """Stop monitoring thread."""
        if self._monitoring_active:
            self._monitoring_active = False
            if self._monitor_thread:
                self._monitor_thread.join(timeout=5)
            self.logger.info("Stop monitoring stopped")

    def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self._monitoring_active:
            try:
                with self._lock:
                    # Check all positions
                    for _position_id, position_stops in list(self.position_stops.items()):
                        # Check time stops
                        if position_stops.time_stop:
                            self._check_time_stop(position_stops)

                        # Check stop status with broker
                        if self.broker_client:
                            self._sync_broker_status(position_stops)

                # Sleep
                threading.Event().wait(10)  # Check every 10 seconds

            except Exception as e:
                self.logger.error("Monitoring error: %s", e)
                self.error_handler.handle_error(e, {"method": "_monitoring_loop"})

    def _sync_broker_status(self, position_stops: PositionStops) -> None:
        """Sync stop status with broker."""
        active_stop = self._get_active_stop(position_stops)
        if not active_stop or not active_stop.broker_order_id:
            return

        try:
            # Check order status with broker
            broker_status = self.broker_client.get_order_status(active_stop.broker_order_id)

            if broker_status == 'FILLED':
                active_stop.status = StopStatus.TRIGGERED
                active_stop.triggered_at = datetime.now()
                active_stop.trigger_reason = "Broker execution"

                self.logger.info("Stop executed by broker: %s", active_stop.order_id)

        except Exception as e:
            self.logger.error("Error syncing broker status: %s", e)

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
# Singleton instance
_stop_manager_instance: StopLossManager | None = None
_instance_lock = threading.Lock()

def get_stop_loss_manager(broker_client=None, event_manager=None) -> StopLossManager:
    """
    Get or create stop loss manager instance (singleton).

    Args:
        broker_client: Optional broker client
        event_manager: Optional event manager

    Returns:
        StopLossManager instance
    """
    global _stop_manager_instance

    if _stop_manager_instance is None:
        with _instance_lock:
            if _stop_manager_instance is None:
                _stop_manager_instance = StopLossManager(broker_client, event_manager)

    return _stop_manager_instance

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":

    # Initialize stop manager
    stop_mgr = get_stop_loss_manager()

    # Configure strategy stops
    momentum_config = StopLossConfig(
        stop_type=StopType.TRAILING,
        initial_stop_method="atr",
        trailing_method=TrailingMethod.PERCENTAGE,
        use_breakeven=True,
        use_partial_exits=True,
        atr_multiplier=2.0,
        trailing_activation_pct=0.01,
        trailing_distance_pct=0.005,
        partial_exit_levels=[0.02, 0.04, 0.06],
        scale_out_percentages=[0.33, 0.50, 1.00]
    )

    stop_mgr.configure_strategy_stops("momentum", momentum_config)

    # Create sample market data
    dates = pd.date_range(end=datetime.now(), periods=50, freq='5min')
    market_data = pd.DataFrame({
        'timestamp': dates,
        'open': 400 + np.random.randn(50).cumsum(),
        'high': 401 + np.random.randn(50).cumsum(),
        'low': 399 + np.random.randn(50).cumsum(),
        'close': 400 + np.random.randn(50).cumsum(),
        'volume': np.random.randint(1000000, 5000000, 50)
    })

    # Create position stops
    position_stops = stop_mgr.create_position_stops(
        position_id="TEST001",
        entry_price=400.0,
        position_side=PositionSide.LONG,
        quantity=100,
        market_data=market_data,
        strategy="momentum"
    )


    # Simulate price movement

    # Price goes up (profit)
    prices = [400, 402, 404, 403, 405, 407, 406, 408, 410]

    for _i, price in enumerate(prices):

        # Update market data
        new_data = market_data.copy()
        new_data.loc[len(new_data)-1, 'close'] = price

        # Update stops
        updated_stops = stop_mgr.update_stops("TEST001", price, new_data)

        # Get active stop
        active_stop_price = stop_mgr.get_active_stop_price("TEST001")

        if updated_stops:
            for _stop in updated_stops:
                pass

        # Check if stop hit
        triggered = stop_mgr.check_stop_hit("TEST001", price - 10)  # Simulate drop
        if triggered:
            pass

    # Get performance stats
    stats = stop_mgr.get_stop_performance_stats()
    for _stop_type, perf in stats.items():
        for _key, _value in perf.items():
            pass

    # Get active stops summary
    summary = stop_mgr.get_active_stops_summary()

    # Cleanup
    stop_mgr.cleanup_position("TEST001")
