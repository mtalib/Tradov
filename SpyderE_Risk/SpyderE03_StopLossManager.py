#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderE03_StopLossManager.py
Group: E (Risk Management)
Purpose: Stop loss and trailing stop management

Description:
    This module manages stop loss orders including initial stops, trailing stops,
    breakeven stops, and time-based stops. It provides dynamic stop adjustment
    based on market conditions and position performance.

Author: Mohamed Talib
Date: 2025-05-29
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
import math

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU07_Constants import OrderType, OrderAction, PositionSide
from SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType
from SpyderU_Utilities.SpyderU13_TechnicalIndicators import TechnicalIndicators
from SpyderF_Analysis.SpyderF04_VolatilityAnalysis import VolatilityAnalyzer

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Stop loss types
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
    """Types of stop losses"""
    FIXED = auto()
    TRAILING = auto()
    BREAKEVEN = auto()
    TIME_BASED = auto()
    VOLATILITY_BASED = auto()
    TECHNICAL = auto()
    PARTIAL = auto()

class StopStatus(Enum):
    """Stop order status"""
    PENDING = auto()
    ACTIVE = auto()
    TRIGGERED = auto()
    CANCELLED = auto()
    MODIFIED = auto()

class TrailingMethod(Enum):
    """Trailing stop methods"""
    PERCENTAGE = auto()
    ATR = auto()
    PARABOLIC_SAR = auto()
    CHANDELIER = auto()
    MOVING_AVERAGE = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
class StopLossConfig:
    """Stop loss configuration"""
    stop_type: StopType
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
    
class StopOrder:
    """Stop order details"""
    order_id: str
    position_id: str
    stop_type: StopType
    stop_price: float
    original_stop: float
    activation_price: Optional[float]
    quantity: int
    side: PositionSide
    status: StopStatus
    created_at: datetime
    last_updated: datetime
    triggered_at: Optional[datetime] = None
    trigger_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

class PositionStops:
    """All stops for a position"""
    position_id: str
    entry_price: float
    current_price: float
    position_side: PositionSide
    initial_stop: StopOrder
    trailing_stop: Optional[StopOrder] = None
    breakeven_stop: Optional[StopOrder] = None
    time_stop: Optional[StopOrder] = None
    partial_stops: List[StopOrder] = field(default_factory=list)
    stop_history: List[Dict[str, Any]] = field(default_factory=list)

# ==============================================================================
# STOP LOSS MANAGER CLASS
# ==============================================================================
class StopLossManager:
    """
    Manages stop loss orders and trailing stops.
    
    Provides comprehensive stop loss management including dynamic adjustment,
    multiple stop types, and position-specific stop strategies.
    """
    
    def __init__(self, event_manager: EventManager):
        """
        Initialize stop loss manager.
        
        Args:
            event_manager: Event manager for stop events
        """
        self.event_manager = event_manager
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Components
        self.indicators = TechnicalIndicators()
        self.volatility_analyzer = VolatilityAnalyzer()
        
        # Configuration
        self.default_config = StopLossConfig()
        self.strategy_configs: Dict[str, StopLossConfig] = {}
        
        # Active stops
        self.position_stops: Dict[str, PositionStops] = {}
        self.stop_orders: Dict[str, StopOrder] = {}
        
        # Tracking
        self.triggered_stops: List[StopOrder] = []
        self.stop_performance: Dict[str, List[float]] = {
            stop_type: [] for stop_type in StopType
        }
        
        # Register event handlers
        self._register_event_handlers()
        
        self.logger.info("StopLossManager initialized")
    
    # ==========================================================================
    # STOP CREATION
    # ==========================================================================
    def create_position_stops(
        self,
        position_id: str,
        entry_price: float,
        position_side: PositionSide,
        market_data: pd.DataFrame,
        strategy: str,
        config: Optional[StopLossConfig] = None
    ) -> PositionStops:
        """
        Create all stops for a new position.
        
        Args:
            position_id: Position identifier
            entry_price: Entry price
            position_side: Long or short
            market_data: Current market data
            strategy: Strategy name
            config: Optional stop configuration
            
        Returns:
            Position stops object
        """
        try:
            # Use strategy config or default
            config = config or self.strategy_configs.get(strategy, self.default_config)
            
            # Calculate initial stop
            initial_stop_price = self._calculate_initial_stop(
                entry_price,
                position_side,
                market_data,
                config
            )
            
            # Create initial stop order
            initial_stop = StopOrder(
                order_id=f"{position_id}_initial_stop",
                position_id=position_id,
                stop_type=StopType.FIXED,
                stop_price=initial_stop_price,
                original_stop=initial_stop_price,
                activation_price=None,
                quantity=0,  # Will be set by order manager
                side=position_side,
                status=StopStatus.ACTIVE,
                created_at=datetime.now(),
                last_updated=datetime.now(),
                metadata={'method': config.initial_stop_method}
            )
            
            # Create position stops object
            position_stops = PositionStops(
                position_id=position_id,
                entry_price=entry_price,
                current_price=market_data['close'].iloc[-1],
                position_side=position_side,
                initial_stop=initial_stop
            )
            
            # Set up additional stops if configured
            if config.use_breakeven:
                self._setup_breakeven_stop(position_stops, config)
            
            if config.use_time_stops:
                self._setup_time_stop(position_stops, config)
            
            # Store position stops
            self.position_stops[position_id] = position_stops
            self.stop_orders[initial_stop.order_id] = initial_stop
            
            # Emit stop created event
            self._emit_stop_event('created', initial_stop, position_stops)
            
            self.logger.info(f"Created stops for position {position_id}: initial stop at {initial_stop_price:.2f}")
            
            return position_stops
            
        except Exception as e:
            self.logger.error(f"Error creating position stops: {e}")
            self.error_handler.handle_error(e, f"create_stops_{position_id}")
            
            # Return minimal stop setup
            return self._create_emergency_stops(position_id, entry_price, position_side)
    
    def _calculate_initial_stop(
        self,
        entry_price: float,
        position_side: PositionSide,
        market_data: pd.DataFrame,
        config: StopLossConfig
    ) -> float:
        """Calculate initial stop price"""
        if config.initial_stop_method == "atr":
            stop_price = self._calculate_atr_stop(
                entry_price,
                position_side,
                market_data,
                config.atr_multiplier
            )
        
        elif config.initial_stop_method == "percentage":
            if position_side == PositionSide.LONG:
                stop_price = entry_price * (1 - config.max_stop_width_pct)
            else:
                stop_price = entry_price * (1 + config.max_stop_width_pct)
        
        elif config.initial_stop_method == "technical":
            stop_price = self._calculate_technical_stop(
                entry_price,
                position_side,
                market_data
            )
        
        else:
            # Default percentage stop
            if position_side == PositionSide.LONG:
                stop_price = entry_price * 0.98  # 2% stop
            else:
                stop_price = entry_price * 1.02
        
        # Apply maximum stop width
        max_distance = entry_price * config.max_stop_width_pct
        if position_side == PositionSide.LONG:
            stop_price = max(stop_price, entry_price - max_distance)
        else:
            stop_price = min(stop_price, entry_price + max_distance)
        
        return stop_price
    
    def _calculate_atr_stop(
        self,
        entry_price: float,
        position_side: PositionSide,
        market_data: pd.DataFrame,
        multiplier: float
    ) -> float:
        """Calculate ATR-based stop"""
        atr = self.indicators.atr(
            market_data['high'],
            market_data['low'],
            market_data['close'],
            period=14
        ).iloc[-1]
        
        # Adjust for volatility regime
        volatility = self.volatility_analyzer.calculate_volatility(market_data)
        current_vol = volatility.get('current_volatility', 0.15)
        
        if current_vol > 0.25:  # High volatility
            multiplier *= HIGH_VOL_STOP_WIDENING
        elif current_vol < 0.10:  # Low volatility
            multiplier *= LOW_VOL_STOP_TIGHTENING
        
        # Calculate stop
        stop_distance = atr * multiplier
        
        if position_side == PositionSide.LONG:
            return entry_price - stop_distance
        else:
            return entry_price + stop_distance
    
    def _calculate_technical_stop(
        self,
        entry_price: float,
        position_side: PositionSide,
        market_data: pd.DataFrame
    ) -> float:
        """Calculate stop based on technical levels"""
        # Find recent swing points
        highs = market_data['high'].rolling(5).max()
        lows = market_data['low'].rolling(5).min()
        
        if position_side == PositionSide.LONG:
            # Use recent swing low
            recent_lows = lows.iloc[-20:]
            stop_price = recent_lows.min() * (1 - INITIAL_STOP_BUFFER)
        else:
            # Use recent swing high
            recent_highs = highs.iloc[-20:]
            stop_price = recent_highs.max() * (1 + INITIAL_STOP_BUFFER)
        
        return stop_price
    
    # ==========================================================================
    # STOP UPDATES
    # ==========================================================================
    def update_stops(
        self,
        position_id: str,
        current_price: float,
        market_data: pd.DataFrame
    ) -> List[StopOrder]:
        """
        Update all stops for a position.
        
        Args:
            position_id: Position identifier
            current_price: Current market price
            market_data: Current market data
            
        Returns:
            List of updated stop orders
        """
        if position_id not in self.position_stops:
            return []
        
        position_stops = self.position_stops[position_id]
        position_stops.current_price = current_price
        
        updated_stops = []
        
        try:
            # Check for trailing stop activation
            if self._should_activate_trailing(position_stops):
                trailing_stop = self._activate_trailing_stop(position_stops, market_data)
                if trailing_stop:
                    updated_stops.append(trailing_stop)
            
            # Update trailing stop if active
            if position_stops.trailing_stop and position_stops.trailing_stop.status == StopStatus.ACTIVE:
                updated = self._update_trailing_stop(position_stops, market_data)
                if updated:
                    updated_stops.append(position_stops.trailing_stop)
            
            # Check for breakeven stop
            if self._should_move_to_breakeven(position_stops):
                breakeven_stop = self._move_to_breakeven(position_stops)
                if breakeven_stop:
                    updated_stops.append(breakeven_stop)
            
            # Check time-based stops
            if position_stops.time_stop:
                time_check = self._check_time_stop(position_stops)
                if time_check:
                    updated_stops.append(position_stops.time_stop)
            
            # Check for partial exit opportunities
            partial_exits = self._check_partial_exits(position_stops, current_price)
            updated_stops.extend(partial_exits)
            
            # Update stop history
            if updated_stops:
                self._update_stop_history(position_stops, updated_stops)
            
        except Exception as e:
            self.logger.error(f"Error updating stops for {position_id}: {e}")
            self.error_handler.handle_error(e, f"update_stops_{position_id}")
        
        return updated_stops
    
    def _should_activate_trailing(self, position_stops: PositionStops) -> bool:
        """Check if trailing stop should be activated"""
        if position_stops.trailing_stop:
            return False  # Already active
        
        # Calculate profit
        if position_stops.position_side == PositionSide.LONG:
            profit_pct = (position_stops.current_price - position_stops.entry_price) / position_stops.entry_price
        else:
            profit_pct = (position_stops.entry_price - position_stops.current_price) / position_stops.entry_price
        
        return profit_pct >= TRAILING_ACTIVATION
    
    def _activate_trailing_stop(
        self,
        position_stops: PositionStops,
        market_data: pd.DataFrame
    ) -> Optional[StopOrder]:
        """Activate trailing stop"""
        config = self.default_config  # Or get position-specific config
        
        # Calculate initial trailing stop price
        if config.trailing_method == TrailingMethod.PERCENTAGE:
            if position_stops.position_side == PositionSide.LONG:
                stop_price = position_stops.current_price * (1 - config.trailing_distance_pct)
            else:
                stop_price = position_stops.current_price * (1 + config.trailing_distance_pct)
        
        elif config.trailing_method == TrailingMethod.ATR:
            stop_price = self._calculate_atr_trailing_stop(
                position_stops.current_price,
                position_stops.position_side,
                market_data
            )
        
        else:
            # Default percentage
            if position_stops.position_side == PositionSide.LONG:
                stop_price = position_stops.current_price * 0.995
            else:
                stop_price = position_stops.current_price * 1.005
        
        # Create trailing stop
        trailing_stop = StopOrder(
            order_id=f"{position_stops.position_id}_trailing",
            position_id=position_stops.position_id,
            stop_type=StopType.TRAILING,
            stop_price=stop_price,
            original_stop=stop_price,
            activation_price=position_stops.current_price,
            quantity=0,
            side=position_stops.position_side,
            status=StopStatus.ACTIVE,
            created_at=datetime.now(),
            last_updated=datetime.now(),
            metadata={'method': config.trailing_method.name}
        )
        
        # Cancel initial stop and activate trailing
        position_stops.initial_stop.status = StopStatus.CANCELLED
        position_stops.trailing_stop = trailing_stop
        self.stop_orders[trailing_stop.order_id] = trailing_stop
        
        self._emit_stop_event('trailing_activated', trailing_stop, position_stops)
        self.logger.info(f"Activated trailing stop for {position_stops.position_id} at {stop_price:.2f}")
        
        return trailing_stop
    
    def _update_trailing_stop(
        self,
        position_stops: PositionStops,
        market_data: pd.DataFrame
    ) -> bool:
        """Update trailing stop price"""
        trailing_stop = position_stops.trailing_stop
        if not trailing_stop:
            return False
        
        config = self.default_config
        old_stop = trailing_stop.stop_price
        
        # Calculate new stop price based on method
        if config.trailing_method == TrailingMethod.PERCENTAGE:
            if position_stops.position_side == PositionSide.LONG:
                new_stop = position_stops.current_price * (1 - config.trailing_distance_pct)
                # Only move up for longs
                if new_stop > old_stop:
                    trailing_stop.stop_price = new_stop
            else:
                new_stop = position_stops.current_price * (1 + config.trailing_distance_pct)
                # Only move down for shorts
                if new_stop < old_stop:
                    trailing_stop.stop_price = new_stop
        
        elif config.trailing_method == TrailingMethod.ATR:
            new_stop = self._calculate_atr_trailing_stop(
                position_stops.current_price,
                position_stops.position_side,
                market_data
            )
            
            if position_stops.position_side == PositionSide.LONG and new_stop > old_stop:
                trailing_stop.stop_price = new_stop
            elif position_stops.position_side == PositionSide.SHORT and new_stop < old_stop:
                trailing_stop.stop_price = new_stop
        
        elif config.trailing_method == TrailingMethod.PARABOLIC_SAR:
            sar = self._calculate_parabolic_sar(market_data)
            if sar is not None:
                trailing_stop.stop_price = sar
        
        # Update if changed
        if trailing_stop.stop_price != old_stop:
            trailing_stop.last_updated = datetime.now()
            self._emit_stop_event('updated', trailing_stop, position_stops)
            return True
        
        return False
    
    def _should_move_to_breakeven(self, position_stops: PositionStops) -> bool:
        """Check if should move stop to breakeven"""
        if position_stops.breakeven_stop:
            return False  # Already at breakeven
        
        # Calculate profit
        if position_stops.position_side == PositionSide.LONG:
            profit_pct = (position_stops.current_price - position_stops.entry_price) / position_stops.entry_price
        else:
            profit_pct = (position_stops.entry_price - position_stops.current_price) / position_stops.entry_price
        
        return profit_pct >= BREAKEVEN_THRESHOLD
    
    def _move_to_breakeven(self, position_stops: PositionStops) -> Optional[StopOrder]:
        """Move stop to breakeven"""
        # Set stop at entry price plus small buffer for fees
        buffer = position_stops.entry_price * 0.001  # 0.1% buffer
        
        if position_stops.position_side == PositionSide.LONG:
            stop_price = position_stops.entry_price + buffer
        else:
            stop_price = position_stops.entry_price - buffer
        
        # Create breakeven stop
        breakeven_stop = StopOrder(
            order_id=f"{position_stops.position_id}_breakeven",
            position_id=position_stops.position_id,
            stop_type=StopType.BREAKEVEN,
            stop_price=stop_price,
            original_stop=position_stops.initial_stop.original_stop,
            activation_price=position_stops.current_price,
            quantity=0,
            side=position_stops.position_side,
            status=StopStatus.ACTIVE,
            created_at=datetime.now(),
            last_updated=datetime.now()
        )
        
        # Update active stop
        if position_stops.trailing_stop:
            # Update trailing stop if it's worse than breakeven
            if (position_stops.position_side == PositionSide.LONG and 
                position_stops.trailing_stop.stop_price < stop_price):
                position_stops.trailing_stop.stop_price = stop_price
        else:
            # Update initial stop
            position_stops.initial_stop.stop_price = stop_price
        
        position_stops.breakeven_stop = breakeven_stop
        self.stop_orders[breakeven_stop.order_id] = breakeven_stop
        
        self._emit_stop_event('breakeven', breakeven_stop, position_stops)
        self.logger.info(f"Moved stop to breakeven for {position_stops.position_id}")
        
        return breakeven_stop
    
    # ==========================================================================
    # STOP CHECKING
    # ==========================================================================
    def check_stops(
        self,
        position_id: str,
        current_price: float,
        high_price: float,
        low_price: float
    ) -> Optional[StopOrder]:
        """
        Check if any stops are triggered.
        
        Args:
            position_id: Position identifier
            current_price: Current price
            high_price: High price since last check
            low_price: Low price since last check
            
        Returns:
            Triggered stop order if any
        """
        if position_id not in self.position_stops:
            return None
        
        position_stops = self.position_stops[position_id]
        
        # Get active stop
        active_stop = self._get_active_stop(position_stops)
        if not active_stop:
            return None
        
        # Check if stop is triggered
        triggered = False
        trigger_reason = ""
        
        if position_stops.position_side == PositionSide.LONG:
            if low_price <= active_stop.stop_price:
                triggered = True
                trigger_reason = f"Price hit stop at {active_stop.stop_price:.2f}"
        else:
            if high_price >= active_stop.stop_price:
                triggered = True
                trigger_reason = f"Price hit stop at {active_stop.stop_price:.2f}"
        
        if triggered:
            active_stop.status = StopStatus.TRIGGERED
            active_stop.triggered_at = datetime.now()
            active_stop.trigger_reason = trigger_reason
            
            self.triggered_stops.append(active_stop)
            self._track_stop_performance(active_stop, position_stops)
            self._emit_stop_event('triggered', active_stop, position_stops)
            
            self.logger.info(f"Stop triggered for {position_id}: {trigger_reason}")
            
            return active_stop
        
        return None
    
    def _get_active_stop(self, position_stops: PositionStops) -> Optional[StopOrder]:
        """Get currently active stop order"""
        # Priority: trailing > breakeven > initial
        if position_stops.trailing_stop and position_stops.trailing_stop.status == StopStatus.ACTIVE:
            return position_stops.trailing_stop
        elif position_stops.breakeven_stop and position_stops.breakeven_stop.status == StopStatus.ACTIVE:
            return position_stops.breakeven_stop
        elif position_stops.initial_stop.status == StopStatus.ACTIVE:
            return position_stops.initial_stop
        
        return None
    
    # ==========================================================================
    # PARTIAL EXITS
    # ==========================================================================
    def _check_partial_exits(
        self,
        position_stops: PositionStops,
        current_price: float
    ) -> List[StopOrder]:
        """Check for partial exit opportunities"""
        if not self.default_config.use_partial_exits:
            return []
        
        partial_exits = []
        
        # Calculate profit
        if position_stops.position_side == PositionSide.LONG:
            profit_pct = (current_price - position_stops.entry_price) / position_stops.entry_price
        else:
            profit_pct = (position_stops.entry_price - current_price) / position_stops.entry_price
        
        # Check scale-out levels
        for i, (scale_pct, exit_pct) in enumerate(zip(
            [0.01, 0.02, 0.03],  # Profit thresholds
            SCALE_OUT_PERCENTAGES
        )):
            if profit_pct >= scale_pct:
                # Check if this level already has a partial exit
                existing = any(
                    stop for stop in position_stops.partial_stops
                    if stop.metadata.get('level') == i
                )
                
                if not existing:
                    partial_stop = StopOrder(
                        order_id=f"{position_stops.position_id}_partial_{i}",
                        position_id=position_stops.position_id,
                        stop_type=StopType.PARTIAL,
                        stop_price=current_price * 0.999,  # Immediate exit
                        original_stop=current_price,
                        activation_price=current_price,
                        quantity=int(exit_pct * 100),  # Percentage as int
                        side=position_stops.position_side,
                        status=StopStatus.ACTIVE,
                        created_at=datetime.now(),
                        last_updated=datetime.now(),
                        metadata={'level': i, 'exit_percentage': exit_pct}
                    )
                    
                    position_stops.partial_stops.append(partial_stop)
                    self.stop_orders[partial_stop.order_id] = partial_stop
                    partial_exits.append(partial_stop)
        
        return partial_exits
    
    # ==========================================================================
    # UTILITIES
    # ==========================================================================
    def _calculate_atr_trailing_stop(
        self,
        current_price: float,
        position_side: PositionSide,
        market_data: pd.DataFrame
    ) -> float:
        """Calculate ATR-based trailing stop"""
        atr = self.indicators.atr(
            market_data['high'],
            market_data['low'],
            market_data['close'],
            period=14
        ).iloc[-1]
        
        # Tighter stop for trailing
        multiplier = 1.5
        
        if position_side == PositionSide.LONG:
            return current_price - (atr * multiplier)
        else:
            return current_price + (atr * multiplier)
    
    def _calculate_parabolic_sar(self, market_data: pd.DataFrame) -> Optional[float]:
        """Calculate Parabolic SAR stop"""
        # Simplified SAR calculation
        high = market_data['high']
        low = market_data['low']
        
        # Would implement full SAR calculation
        # For now, return None
        return None
    
    def _setup_breakeven_stop(
        self,
        position_stops: PositionStops,
        config: StopLossConfig
    ) -> None:
        """Set up breakeven stop configuration"""
        # Breakeven stop will be created when profit threshold is reached
        position_stops.stop_history.append({
            'timestamp': datetime.now(),
            'event': 'breakeven_configured',
            'threshold': config.breakeven_threshold_pct
        })
    
    def _setup_time_stop(
        self,
        position_stops: PositionStops,
        config: StopLossConfig
    ) -> None:
        """Set up time-based stop"""
        # Time stop will be activated based on expected hold time
        position_stops.stop_history.append({
            'timestamp': datetime.now(),
            'event': 'time_stop_configured',
            'max_hold_time': 'strategy_dependent'
        })
    
    def _check_time_stop(self, position_stops: PositionStops) -> Optional[StopOrder]:
        """Check time-based stop conditions"""
        # Would implement based on strategy-specific hold times
        return None
    
    def _create_emergency_stops(
        self,
        position_id: str,
        entry_price: float,
        position_side: PositionSide
    ) -> PositionStops:
        """Create emergency stop configuration"""
        # Simple percentage-based stop
        if position_side == PositionSide.LONG:
            stop_price = entry_price * 0.95  # 5% stop
        else:
            stop_price = entry_price * 1.05
        
        emergency_stop = StopOrder(
            order_id=f"{position_id}_emergency",
            position_id=position_id,
            stop_type=StopType.FIXED,
            stop_price=stop_price,
            original_stop=stop_price,
            activation_price=None,
            quantity=0,
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
            initial_stop=emergency_stop
        )
    
    def _update_stop_history(
        self,
        position_stops: PositionStops,
        updated_stops: List[StopOrder]
    ) -> None:
        """Update stop history"""
        for stop in updated_stops:
            position_stops.stop_history.append({
                'timestamp': datetime.now(),
                'event': 'stop_updated',
                'stop_type': stop.stop_type.name,
                'old_price': stop.original_stop,
                'new_price': stop.stop_price,
                'reason': stop.metadata.get('reason', 'price_movement')
            })
    
    def _track_stop_performance(
        self,
        triggered_stop: StopOrder,
        position_stops: PositionStops
    ) -> None:
        """Track stop performance for analysis"""
        # Calculate performance metrics
        if position_stops.position_side == PositionSide.LONG:
            stop_performance = (triggered_stop.stop_price - position_stops.entry_price) / position_stops.entry_price
        else:
            stop_performance = (position_stops.entry_price - triggered_stop.stop_price) / position_stops.entry_price
        
        self.stop_performance[triggered_stop.stop_type].append(stop_performance)
        
        # Limit history
        if len(self.stop_performance[triggered_stop.stop_type]) > 100:
            self.stop_performance[triggered_stop.stop_type] = self.stop_performance[triggered_stop.stop_type][-100:]
    
    # ==========================================================================
    # EVENT HANDLING
    # ==========================================================================
    def _register_event_handlers(self) -> None:
        """Register event handlers"""
        self.event_manager.subscribe(
            self._handle_price_event,
            event_filter=lambda e: e.type == EventType.MARKET_DATA,
            subscriber_id="stop_loss_manager"
        )
        
        self.event_manager.subscribe(
            self._handle_position_event,
            event_filter=lambda e: e.type == EventType.POSITION,
            subscriber_id="stop_loss_manager_positions"
        )
    
    def _handle_price_event(self, event: Event) -> None:
        """Handle price update events"""
        data = event.data
        symbol = data.get('symbol')
        
        if symbol != 'SPY':
            return
        
        # Check all positions for stop triggers
        for position_id, position_stops in self.position_stops.items():
            triggered = self.check_stops(
                position_id,
                data.get('close', 0),
                data.get('high', 0),
                data.get('low', 0)
            )
            
            if triggered:
                # Stop was triggered, handle accordingly
                pass
    
    def _handle_position_event(self, event: Event) -> None:
        """Handle position events"""
        action = event.data.get('action')
        position_id = event.data.get('position_id')
        
        if action == 'closed' and position_id in self.position_stops:
            # Clean up stops for closed position
            self._cleanup_position_stops(position_id)
    
    def _emit_stop_event(
        self,
        action: str,
        stop_order: StopOrder,
        position_stops: PositionStops
    ) -> None:
        """Emit stop-related event"""
        self.event_manager.emit(Event(
            EventType.RISK,
            {
                'action': f'stop_{action}',
                'stop_order': {
                    'order_id': stop_order.order_id,
                    'position_id': stop_order.position_id,
                    'stop_type': stop_order.stop_type.name,
                    'stop_price': stop_order.stop_price,
                    'status': stop_order.status.name
                },
                'position': {
                    'position_id': position_stops.position_id,
                    'entry_price': position_stops.entry_price,
                    'current_price': position_stops.current_price,
                    'side': position_stops.position_side.name
                }
            }
        ))
    
    def _cleanup_position_stops(self, position_id: str) -> None:
        """Clean up stops for closed position"""
        if position_id in self.position_stops:
            position_stops = self.position_stops[position_id]
            
            # Cancel all active stops
            for stop in [position_stops.initial_stop, position_stops.trailing_stop, 
                        position_stops.breakeven_stop, position_stops.time_stop]:
                if stop and stop.status == StopStatus.ACTIVE:
                    stop.status = StopStatus.CANCELLED
            
            # Remove from active tracking
            del self.position_stops[position_id]
            
            self.logger.info(f"Cleaned up stops for closed position {position_id}")
    
    # ==========================================================================
    # PUBLIC INTERFACE
    # ==========================================================================
    def configure_strategy_stops(
        self,
        strategy: str,
        config: StopLossConfig
    ) -> None:
        """
        Configure stop loss settings for a strategy.
        
        Args:
            strategy: Strategy name
            config: Stop loss configuration
        """
        self.strategy_configs[strategy] = config
        self.logger.info(f"Configured stops for strategy {strategy}")
    
    def get_position_stops(self, position_id: str) -> Optional[PositionStops]:
        """Get stops for a position"""
        return self.position_stops.get(position_id)
    
    def get_active_stop_price(self, position_id: str) -> Optional[float]:
        """Get current active stop price for position"""
        position_stops = self.position_stops.get(position_id)
        if not position_stops:
            return None
        
        active_stop = self._get_active_stop(position_stops)
        return active_stop.stop_price if active_stop else None
    
    def cancel_stops(self, position_id: str) -> None:
        """Cancel all stops for a position"""
        if position_id in self.position_stops:
            position_stops = self.position_stops[position_id]
            
            for stop in [position_stops.initial_stop, position_stops.trailing_stop,
                        position_stops.breakeven_stop, position_stops.time_stop]:
                if stop and stop.status == StopStatus.ACTIVE:
                    stop.status = StopStatus.CANCELLED
                    self._emit_stop_event('cancelled', stop, position_stops)
            
            self.logger.info(f"Cancelled all stops for position {position_id}")
    
    def get_stop_performance_stats(self) -> Dict[str, Dict[str, float]]:
        """Get stop performance statistics"""
        stats = {}
        
        for stop_type, performances in self.stop_performance.items():
            if performances:
                stats[stop_type.name] = {
                    'count': len(performances),
                    'avg_performance': sum(performances) / len(performances),
                    'best': max(performances),
                    'worst': min(performances),
                    'positive_rate': sum(1 for p in performances if p > 0) / len(performances)
                }
        
        return stats

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test stop loss manager
    from SpyderA_Core.SpyderA05_EventManager import EventManager
    
    # Initialize
    event_manager = EventManager()
    stop_manager = StopLossManager(event_manager)
    
    # Configure strategy stops
    momentum_config = StopLossConfig(
        stop_type=StopType.TRAILING,
        initial_stop_method="atr",
        trailing_method=TrailingMethod.ATR,
        use_breakeven=True,
        use_partial_exits=True,
        atr_multiplier=2.0,
        trailing_activation_pct=0.01,
        trailing_distance_pct=0.005
    )
    
    stop_manager.configure_strategy_stops("momentum", momentum_config)
    
    # Create sample market data
    dates = pd.date_range(end=datetime.now(), periods=100, freq='5min')
    prices = 450 + np.cumsum(np.random.randn(100) * 0.5)
    
    market_data = pd.DataFrame({
        'timestamp': dates,
        'open': prices + np.random.randn(100) * 0.1,
        'high': prices + abs(np.random.randn(100) * 0.3),
        'low': prices - abs(np.random.randn(100) * 0.3),
        'close': prices,
        'volume': np.random.randint(50000000, 150000000, 100)
    })
    
    # Test stop creation
    print("STOP LOSS MANAGER TEST")
    print("=" * 50)
    
    # Create position stops
    position_stops = stop_manager.create_position_stops(
        position_id="TEST_001",
        entry_price=450.00,
        position_side=PositionSide.LONG,
        market_data=market_data,
        strategy="momentum"
    )
    
    print(f"Position: {position_stops.position_id}")
    print(f"Entry Price: ${position_stops.entry_price:.2f}")
    print(f"Initial Stop: ${position_stops.initial_stop.stop_price:.2f}")
    print(f"Stop Distance: {abs(position_stops.initial_stop.stop_price - position_stops.entry_price):.2f}")
    print(f"Risk: {abs(position_stops.initial_stop.stop_price - position_stops.entry_price) / position_stops.entry_price:.1%}")
    
    # Simulate price movement and update stops
    print("\nSimulating price movement...")
    
    # Price moves up 2%
    new_price = 459.00  # 2% profit
    market_data.loc[market_data.index[-1], 'close'] = new_price
    
    updated_stops = stop_manager.update_stops(
        "TEST_001",
        new_price,
        market_data
    )
    
    print(f"\nPrice moved to ${new_price:.2f} (+2%)")
    for stop in updated_stops:
        print(f"Updated {stop.stop_type.name} stop to ${stop.stop_price:.2f}")
    
    # Check if trailing activated
    position_stops = stop_manager.get_position_stops("TEST_001")
    if position_stops.trailing_stop:
        print(f"Trailing stop activated at ${position_stops.trailing_stop.stop_price:.2f}")
    
    # Check stop trigger
    print("\nChecking stop trigger...")
    triggered = stop_manager.check_stops(
        "TEST_001",
        current_price=455.00,
        high_price=459.00,
        low_price=455.00  # Hit trailing stop
    )
    
    if triggered:
        print(f"Stop triggered: {triggered.trigger_reason}")
    else:
        print("No stops triggered")
    
    # Get performance stats
    print("\nStop Performance Stats:")
    stats = stop_manager.get_stop_performance_stats()
    for stop_type, perf in stats.items():
        print(f"\n{stop_type}:")
        for metric, value in perf.items():
            print(f"  {metric}: {value:.3f}")