#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module: SpyderB03_PositionTracker.py
Group: B (Broker Integration)
Purpose: Real-time position tracking

Description:
    This module tracks all open positions in real-time for the Spyder trading system.
    It monitors position changes, calculates P&L, tracks Greeks for options positions,
    and provides comprehensive position analytics. The tracker maintains synchronization
    with the broker and ensures accurate position reporting at all times.

Author: Mohamed Talib
Date: 2025-05-29
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import datetime
import time
import threading
from typing import Dict, List, Optional, Any, Tuple, Set, Type, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import json
import statistics
import pandas as pd
import uuid

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from ibapi.contract import Contract
from ibapi.order import Order

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU07_Constants import (
    PositionSide, TRADING_DAYS_PER_YEAR, OPTION_MULTIPLIER
)
from SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType, EventPriority
from SpyderB_Broker.SpyderB01_IBClient import IBClient, TickerId
from SpyderB_Broker.SpyderB10_IBDataTypes import IBContract, IBPosition

# Try to import Greeks calculator, but make it optional
try:
    from SpyderF_Analysis.SpyderF06_GreeksCalculator import GreeksCalculator
    GREEKS_AVAILABLE = True
except ImportError:
    GREEKS_AVAILABLE = False
    class GreeksCalculator:
        """Mock Greeks calculator when QuantLib not available"""
        pass

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Position monitoring intervals
POSITION_UPDATE_INTERVAL = 1.0  # seconds
PNL_UPDATE_INTERVAL = 5.0       # seconds
GREEKS_UPDATE_INTERVAL = 30.0   # seconds

# Position limits
MAX_POSITION_AGE_HOURS = 24    # Maximum age before warning
STALE_DATA_THRESHOLD = 300     # 5 minutes

# P&L thresholds
PROFIT_WARNING_THRESHOLD = 0.50  # 50% of max profit
LOSS_WARNING_THRESHOLD = 0.25    # 25% loss warning

# Use default if not found in constants
if 'OPTION_MULTIPLIER' not in locals():
    OPTION_MULTIPLIER = 100

# ==============================================================================
# ENUMS
# ==============================================================================
class PositionType(Enum):
    """Position types"""
    STOCK = "stock"
    OPTION = "option"
    SPREAD = "spread"
    FUTURE = "future"

class PositionStatus(Enum):
    """Position status"""
    OPEN = "open"
    CLOSING = "closing"
    CLOSED = "closed"
    EXPIRED = "expired"

class SpreadType(Enum):
    """Option spread types"""
    VERTICAL = "vertical"
    CALENDAR = "calendar"
    DIAGONAL = "diagonal"
    IRON_CONDOR = "iron_condor"
    IRON_BUTTERFLY = "iron_butterfly"
    STRADDLE = "straddle"
    STRANGLE = "strangle"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class Greeks:
    """Option Greeks data"""
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)

@dataclass
class Position:
    """Single position data"""
    position_id: str
    symbol: str
    contract: Contract
    position_type: PositionType
    side: PositionSide
    quantity: int
    entry_price: float
    current_price: float = 0.0
    market_price: float = 0.0
    
    # P&L tracking
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    commission: float = 0.0
    
    # Greeks (options only)
    greeks: Optional[Greeks] = None
    underlying_price: float = 0.0
    
    # Position metadata
    status: PositionStatus = PositionStatus.OPEN
    entry_time: datetime.datetime = field(default_factory=datetime.datetime.now)
    exit_time: Optional[datetime.datetime] = None
    strategy_id: Optional[str] = None
    order_id: Optional[str] = None
    
    # Risk metrics
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    max_profit: Optional[float] = None
    max_loss: Optional[float] = None
    
    # Market data
    bid: float = 0.0
    ask: float = 0.0
    last_update: datetime.datetime = field(default_factory=datetime.datetime.now)
    
    @property
    def position_value(self) -> float:
        """Calculate current position value"""
        multiplier = OPTION_MULTIPLIER if self.position_type == PositionType.OPTION else 1
        return self.quantity * self.current_price * multiplier
    
    @property
    def entry_value(self) -> float:
        """Calculate entry position value"""
        multiplier = OPTION_MULTIPLIER if self.position_type == PositionType.OPTION else 1
        return self.quantity * self.entry_price * multiplier
    
    def calculate_pnl(self) -> Tuple[float, float]:
        """Calculate unrealized and total P&L"""
        if self.side == PositionSide.LONG:
            self.unrealized_pnl = (self.current_price - self.entry_price) * self.quantity
        else:  # SHORT
            self.unrealized_pnl = (self.entry_price - self.current_price) * self.quantity
        
        # Apply multiplier for options
        if self.position_type == PositionType.OPTION:
            self.unrealized_pnl *= OPTION_MULTIPLIER
        
        total_pnl = self.unrealized_pnl + self.realized_pnl - self.commission
        return self.unrealized_pnl, total_pnl
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert position to dictionary"""
        return {
            'position_id': self.position_id,
            'symbol': self.symbol,
            'type': self.position_type.value,
            'side': self.side.value,
            'quantity': self.quantity,
            'entry_price': self.entry_price,
            'current_price': self.current_price,
            'unrealized_pnl': self.unrealized_pnl,
            'realized_pnl': self.realized_pnl,
            'status': self.status.value,
            'entry_time': self.entry_time.isoformat(),
            'strategy_id': self.strategy_id,
            'greeks': {
                'delta': self.greeks.delta if self.greeks else 0,
                'gamma': self.greeks.gamma if self.greeks else 0,
                'theta': self.greeks.theta if self.greeks else 0,
                'vega': self.greeks.vega if self.greeks else 0
            } if self.greeks else None
        }

@dataclass
class SpreadPosition:
    """Multi-leg spread position"""
    spread_id: str
    spread_type: SpreadType
    legs: List[Position] = field(default_factory=list)
    
    # Aggregate metrics
    net_delta: float = 0.0
    net_gamma: float = 0.0
    net_theta: float = 0.0
    net_vega: float = 0.0
    
    # P&L
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    max_profit: float = 0.0
    max_loss: float = 0.0
    breakeven_points: List[float] = field(default_factory=list)
    current_risk: float = 0.0
    
    def calculate_spread_metrics(self) -> None:
        """Calculate aggregate spread metrics"""
        self.net_delta = sum(leg.greeks.delta * leg.quantity for leg in self.legs if leg.greeks)
        self.net_gamma = sum(leg.greeks.gamma * leg.quantity for leg in self.legs if leg.greeks)
        self.net_theta = sum(leg.greeks.theta * leg.quantity for leg in self.legs if leg.greeks)
        self.net_vega = sum(leg.greeks.vega * leg.quantity for leg in self.legs if leg.greeks)
        
        # Calculate P&L
        self.unrealized_pnl = sum(leg.unrealized_pnl for leg in self.legs)
        self.realized_pnl = sum(leg.realized_pnl for leg in self.legs)

# ==============================================================================
# POSITION TRACKER CLASS
# ==============================================================================
class PositionTracker:
    """
    Tracks and manages all trading positions.
    
    Features:
    - Real-time position tracking
    - P&L calculation and monitoring
    - Greeks tracking for options
    - Spread position management
    - Position analytics and reporting
    - Risk metric calculation
    """
    
    def __init__(self, ib_client: IBClient = None, event_manager: EventManager = None):
        """
        Initialize position tracker.
        
        Args:
            ib_client: IB client instance (optional)
            event_manager: Event manager instance (optional)
        """
        self.ib_client = ib_client
        self.event_manager = event_manager
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Position storage
        self.positions: Dict[str, Position] = {}
        self.spreads: Dict[str, SpreadPosition] = {}
        self.position_by_symbol: Dict[str, List[str]] = defaultdict(list)
        self.position_by_strategy: Dict[str, List[str]] = defaultdict(list)
        
        # Market data
        self.market_data: Dict[str, Dict[str, float]] = {}
        self.ticker_to_position: Dict[int, str] = {}
        self._next_ticker_id = 10000
        
        # Greeks calculator
        if GREEKS_AVAILABLE:
            self.greeks_calculator = GreeksCalculator()
        else:
            self.greeks_calculator = None
        
        # P&L tracking
        self.daily_realized_pnl = 0.0
        self.daily_commission = 0.0
        self.position_history: List[Dict[str, Any]] = []
        
        # Monitoring
        self._monitor_thread: Optional[threading.Thread] = None
        self._pnl_thread: Optional[threading.Thread] = None
        self._running = False
        self._position_lock = threading.RLock()
        
        # IB callbacks
        if self.ib_client:
            self._register_ib_callbacks()
        
        # Risk limits
        self.position_limits = {
            'max_position_value': 100000,
            'max_single_position': 50,
            'max_total_positions': 20
        }
        
        self.logger.info("PositionTracker initialized")
    
    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def start(self) -> None:
        """Start position tracking"""
        if self._running:
            return
        
        self._running = True
        
        # Request initial positions from broker
        if self.ib_client:
            self._request_positions()
        
        # Start monitoring threads
        self._monitor_thread = threading.Thread(
            target=self._monitor_positions,
            daemon=True,
            name="PositionMonitor"
        )
        self._monitor_thread.start()
        
        self._pnl_thread = threading.Thread(
            target=self._update_pnl_loop,
            daemon=True,
            name="PnLUpdater"
        )
        self._pnl_thread.start()
        
        self.logger.info("Position tracking started")
    
    def stop(self) -> None:
        """Stop position tracking"""
        self._running = False
        
        # Cancel market data subscriptions
        if self.ib_client:
            self._cancel_all_market_data()
        
        # Wait for threads
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)
        if self._pnl_thread:
            self._pnl_thread.join(timeout=5.0)
        
        self.logger.info("Position tracking stopped")
    
    def shutdown(self) -> None:
        """Shutdown position tracker"""
        self.stop()
        self.positions.clear()
        self.spreads.clear()
        self.position_history.clear()
    
    # ==========================================================================
    # POSITION MANAGEMENT
    # ==========================================================================
    def add_position(
        self,
        contract: Contract,
        quantity: int,
        entry_price: float,
        side: PositionSide,
        order_id: Optional[str] = None,
        strategy_id: Optional[str] = None
    ) -> str:
        """
        Add a new position.
        
        Args:
            contract: IB contract
            quantity: Position size
            entry_price: Entry price
            side: LONG or SHORT
            order_id: Associated order ID
            strategy_id: Strategy identifier
            
        Returns:
            Position ID
        """
        try:
            position_id = str(uuid.uuid4())
            
            # Determine position type
            if contract.secType == "STK":
                position_type = PositionType.STOCK
            elif contract.secType == "OPT":
                position_type = PositionType.OPTION
            elif contract.secType == "FUT":
                position_type = PositionType.FUTURE
            else:
                position_type = PositionType.STOCK
            
            # Create position
            position = Position(
                position_id=position_id,
                symbol=contract.symbol,
                contract=contract,
                position_type=position_type,
                side=side,
                quantity=quantity,
                entry_price=entry_price,
                current_price=entry_price,
                order_id=order_id,
                strategy_id=strategy_id
            )
            
            with self._position_lock:
                self.positions[position_id] = position
                self.position_by_symbol[contract.symbol].append(position_id)
                if strategy_id:
                    self.position_by_strategy[strategy_id].append(position_id)
            
            # Subscribe to market data
            if self.ib_client:
                self._subscribe_market_data(position_id)
            
            # Emit position opened event
            if self.event_manager:
                self.event_manager.emit(Event(
                    EventType.POSITION_OPENED,
                    {
                        'position_id': position_id,
                        'symbol': contract.symbol,
                        'side': side.value,
                        'quantity': quantity,
                        'entry_price': entry_price
                    }
                ))
            
            self.logger.info(f"Position opened: {contract.symbol} {side.value} {quantity} @ {entry_price}")
            
            return position_id
            
        except Exception as e:
            self.logger.error(f"Error adding position: {e}")
            self.error_handler.handle_error(e, "add_position")
            return ""
    
    def close_position(self, position_id: str, exit_price: float, commission: float = 0.0) -> bool:
        """
        Close a position.
        
        Args:
            position_id: Position identifier
            exit_price: Exit price
            commission: Commission paid
            
        Returns:
            Success status
        """
        try:
            with self._position_lock:
                position = self.positions.get(position_id)
                if not position:
                    return False
                
                # Update position
                position.status = PositionStatus.CLOSED
                position.exit_time = datetime.datetime.now()
                position.current_price = exit_price
                position.commission = commission
                
                # Calculate final P&L
                unrealized, total = position.calculate_pnl()
                
                # Update daily P&L
                self.daily_realized_pnl += unrealized
                self.daily_commission += commission
                
                # Add to history
                self.position_history.append(position.to_dict())
                
                # Remove from active positions
                del self.positions[position_id]
                self.position_by_symbol[position.symbol].remove(position_id)
                if position.strategy_id:
                    self.position_by_strategy[position.strategy_id].remove(position_id)
            
            # Cancel market data
            if self.ib_client:
                self._cancel_market_data(position_id)
            
            # Emit position closed event
            if self.event_manager:
                self.event_manager.emit(Event(
                    EventType.POSITION_CLOSED,
                    {
                        'position_id': position_id,
                        'symbol': position.symbol,
                        'realized_pnl': unrealized,
                        'total_pnl': total
                    }
                ))
            
            self.logger.info(f"Position closed: {position.symbol} P&L: ${total:.2f}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error closing position: {e}")
            self.error_handler.handle_error(e, "close_position")
            return False
    
    # ==========================================================================
    # SPREAD MANAGEMENT
    # ==========================================================================
    def create_spread(self, spread_type: SpreadType, legs: List[str]) -> str:
        """
        Create a spread position from individual legs.
        
        Args:
            spread_type: Type of spread
            legs: List of position IDs
            
        Returns:
            Spread ID
        """
        try:
            spread_id = str(uuid.uuid4())
            
            with self._position_lock:
                # Gather leg positions
                spread_legs = []
                for leg_id in legs:
                    if leg_id in self.positions:
                        spread_legs.append(self.positions[leg_id])
                
                if len(spread_legs) != len(legs):
                    self.logger.error("Not all legs found for spread")
                    return ""
                
                # Create spread
                spread = SpreadPosition(
                    spread_id=spread_id,
                    spread_type=spread_type,
                    legs=spread_legs
                )
                
                # Calculate initial metrics
                spread.calculate_spread_metrics()
                
                self.spreads[spread_id] = spread
            
            self.logger.info(f"Spread created: {spread_type.value} with {len(legs)} legs")
            
            return spread_id
            
        except Exception as e:
            self.logger.error(f"Error creating spread: {e}")
            self.error_handler.handle_error(e, "create_spread")
            return ""
    
    # ==========================================================================
    # MARKET DATA AND UPDATES
    # ==========================================================================
    def _subscribe_market_data(self, position_id: str) -> None:
        """Subscribe to market data for a position"""
        if not self.ib_client:
            return
            
        position = self.positions.get(position_id)
        if not position:
            return
        
        ticker_id = self._next_ticker_id
        self._next_ticker_id += 1
        self.ticker_to_position[ticker_id] = position_id
        
        # Request market data
        self.ib_client.reqMktData(
            tickerId=ticker_id,
            contract=position.contract,
            genericTicks="",
            snapshot=False,
            regulatorySnapshot=False,
            mktDataOptions=[]
        )
    
    def _cancel_market_data(self, position_id: str) -> None:
        """Cancel market data subscription"""
        if not self.ib_client:
            return
            
        # Find ticker ID
        ticker_id = None
        for tid, pid in self.ticker_to_position.items():
            if pid == position_id:
                ticker_id = tid
                break
        
        if ticker_id:
            self.ib_client.cancelMktData(ticker_id)
            del self.ticker_to_position[ticker_id]
    
    def _cancel_all_market_data(self) -> None:
        """Cancel all market data subscriptions"""
        if not self.ib_client:
            return
            
        for ticker_id in list(self.ticker_to_position.keys()):
            self.ib_client.cancelMktData(ticker_id)
        
        self.ticker_to_position.clear()
    
    # ==========================================================================
    # MONITORING LOOPS
    # ==========================================================================
    def _monitor_positions(self) -> None:
        """Monitor positions for changes"""
        while self._running:
            try:
                with self._position_lock:
                    for position in list(self.positions.values()):
                        # Check for stale data
                        age = (datetime.datetime.now() - position.last_update).total_seconds()
                        if age > STALE_DATA_THRESHOLD:
                            self.logger.warning(f"Stale data for {position.symbol}")
                        
                        # Check stop loss/take profit
                        self._check_exit_conditions(position)
                
                time.sleep(POSITION_UPDATE_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"Error monitoring positions: {e}")
                time.sleep(5)
    
    def _update_pnl_loop(self) -> None:
        """Update P&L calculations"""
        while self._running:
            try:
                with self._position_lock:
                    total_unrealized = 0.0
                    total_value = 0.0
                    
                    for position in self.positions.values():
                        unrealized, total = position.calculate_pnl()
                        total_unrealized += unrealized
                        total_value += position.position_value
                    
                    # Update spreads
                    for spread in self.spreads.values():
                        spread.calculate_spread_metrics()
                
                # Emit P&L update event
                if self.event_manager:
                    self.event_manager.emit(Event(
                        EventType.PNL_UPDATE,
                        {
                            'unrealized_pnl': total_unrealized,
                            'realized_pnl': self.daily_realized_pnl,
                            'total_value': total_value,
                            'position_count': len(self.positions)
                        }
                    ))
                
                time.sleep(PNL_UPDATE_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"Error updating P&L: {e}")
                time.sleep(5)
    
    # ==========================================================================
    # RISK MANAGEMENT
    # ==========================================================================
    def _check_exit_conditions(self, position: Position) -> None:
        """Check if position should be exited"""
        if position.status != PositionStatus.OPEN:
            return
        
        # Check stop loss
        if position.stop_loss:
            if position.side == PositionSide.LONG and position.current_price <= position.stop_loss:
                self._trigger_exit(position, "STOP_LOSS")
            elif position.side == PositionSide.SHORT and position.current_price >= position.stop_loss:
                self._trigger_exit(position, "STOP_LOSS")
        
        # Check take profit
        if position.take_profit:
            if position.side == PositionSide.LONG and position.current_price >= position.take_profit:
                self._trigger_exit(position, "TAKE_PROFIT")
            elif position.side == PositionSide.SHORT and position.current_price <= position.take_profit:
                self._trigger_exit(position, "TAKE_PROFIT")
    
    def _trigger_exit(self, position: Position, reason: str) -> None:
        """Trigger position exit"""
        if self.event_manager:
            self.event_manager.emit(Event(
                EventType.EXIT_SIGNAL,
                {
                    'position_id': position.position_id,
                    'symbol': position.symbol,
                    'reason': reason,
                    'current_price': position.current_price
                },
                priority=EventPriority.HIGH
            ))
    
    def _check_risk_limits(self) -> None:
        """Check position risk limits"""
        with self._position_lock:
            # Total position value
            total_value = sum(pos.position_value for pos in self.positions.values())
            if total_value > self.position_limits['max_position_value']:
                if self.event_manager:
                    self.event_manager.emit(Event(
                        EventType.RISK_LIMIT,
                        {
                            'type': 'position_value_limit',
                            'current_value': total_value,
                            'limit': self.position_limits['max_position_value']
                        },
                        priority=EventPriority.CRITICAL
                    ))
            
            # Position count
            position_count = len(self.positions)
            if position_count > self.position_limits['max_total_positions']:
                if self.event_manager:
                    self.event_manager.emit(Event(
                        EventType.RISK_LIMIT,
                        {
                            'type': 'position_count_limit',
                            'current_count': position_count,
                            'limit': self.position_limits['max_total_positions']
                        },
                        priority=EventPriority.HIGH
                    ))
    
    # ==========================================================================
    # IB CALLBACKS
    # ==========================================================================
    def _register_ib_callbacks(self) -> None:
        """Register IB API callbacks"""
        if not self.ib_client:
            return
            
        # Register position update callback
        self.ib_client.register_callback('position', self._on_position_update)
        self.ib_client.register_callback('tickPrice', self._on_tick_price)
        self.ib_client.register_callback('tickSize', self._on_tick_size)
        self.ib_client.register_callback('tickOptionComputation', self._on_option_computation)
    
    def _on_position_update(self, account: str, contract: Contract, position: float,
                          avgCost: float) -> None:
        """Handle position update from IB"""
        # Implementation depends on IB API integration
        pass
    
    def _on_tick_price(self, tickerId: int, tickType: int, price: float, attrib) -> None:
        """Handle price tick"""
        position_id = self.ticker_to_position.get(tickerId)
        if not position_id:
            return
        
        with self._position_lock:
            position = self.positions.get(position_id)
            if position:
                if tickType == 1:  # BID
                    position.bid = price
                elif tickType == 2:  # ASK
                    position.ask = price
                elif tickType == 4:  # LAST
                    position.current_price = price
                    position.last_update = datetime.datetime.now()
    
    def _on_tick_size(self, tickerId: int, tickType: int, size: int) -> None:
        """Handle size tick"""
        # Could track bid/ask sizes if needed
        pass
    
    def _on_option_computation(self, tickerId: int, tickType: int, tickAsk: float,
                             impliedVol: float, delta: float, optPrice: float,
                             pvDividend: float, gamma: float, vega: float,
                             theta: float, undPrice: float) -> None:
        """Handle option Greeks update"""
        position_id = self.ticker_to_position.get(tickerId)
        if not position_id:
            return
        
        with self._position_lock:
            position = self.positions.get(position_id)
            if position and position.position_type == PositionType.OPTION:
                position.underlying_price = undPrice
                position.greeks = Greeks(
                    delta=delta * position.quantity,
                    gamma=gamma * position.quantity,
                    theta=theta * position.quantity,
                    vega=vega * position.quantity,
                    rho=0.0  # IB doesn't provide rho in this callback
                )
    
    # ==========================================================================
    # POSITION QUERIES
    # ==========================================================================
    def get_position(self, position_id: str) -> Optional[Position]:
        """Get position by ID"""
        with self._position_lock:
            return self.positions.get(position_id)
    
    def get_positions_by_symbol(self, symbol: str) -> List[Position]:
        """Get all positions for a symbol"""
        with self._position_lock:
            position_ids = self.position_by_symbol.get(symbol, [])
            return [self.positions[pid] for pid in position_ids if pid in self.positions]
    
    def get_positions_by_strategy(self, strategy_id: str) -> List[Position]:
        """Get all positions for a strategy"""
        with self._position_lock:
            position_ids = self.position_by_strategy.get(strategy_id, [])
            return [self.positions[pid] for pid in position_ids if pid in self.positions]
    
    def get_all_positions(self) -> List[Position]:
        """Get all open positions"""
        with self._position_lock:
            return list(self.positions.values())
    
    def get_position_summary(self) -> Dict[str, Any]:
        """Get position summary statistics"""
        with self._position_lock:
            positions = list(self.positions.values())
            
            if not positions:
                return {
                    'count': 0,
                    'total_value': 0.0,
                    'unrealized_pnl': 0.0,
                    'realized_pnl': self.daily_realized_pnl,
                    'commission': self.daily_commission
                }
            
            total_value = sum(p.position_value for p in positions)
            total_unrealized = sum(p.unrealized_pnl for p in positions)
            
            # Greeks aggregation
            total_delta = sum(p.greeks.delta for p in positions if p.greeks)
            total_gamma = sum(p.greeks.gamma for p in positions if p.greeks)
            total_theta = sum(p.greeks.theta for p in positions if p.greeks)
            total_vega = sum(p.greeks.vega for p in positions if p.greeks)
            
            return {
                'count': len(positions),
                'total_value': total_value,
                'unrealized_pnl': total_unrealized,
                'realized_pnl': self.daily_realized_pnl,
                'total_pnl': total_unrealized + self.daily_realized_pnl,
                'commission': self.daily_commission,
                'position_value': total_value,
                'greeks': {
                    'delta': total_delta,
                    'gamma': total_gamma,
                    'theta': total_theta,
                    'vega': total_vega
                }
            }
    
    def get_pnl_by_strategy(self) -> Dict[str, Dict[str, float]]:
        """Get P&L breakdown by strategy"""
        with self._position_lock:
            pnl_by_strategy = defaultdict(lambda: {
                'unrealized': 0.0,
                'realized': 0.0,
                'commission': 0.0,
                'positions': 0
            })
            
            for position in self.positions.values():
                strategy = position.strategy_id or 'unassigned'
                pnl_by_strategy[strategy]['unrealized'] += position.unrealized_pnl
                pnl_by_strategy[strategy]['realized'] += position.realized_pnl
                pnl_by_strategy[strategy]['commission'] += position.commission
                pnl_by_strategy[strategy]['positions'] += 1
            
            return dict(pnl_by_strategy)
    
    # ==========================================================================
    # UTILITIES
    # ==========================================================================
    def _request_positions(self) -> None:
        """Request current positions from broker"""
        if self.ib_client:
            self.ib_client.reqPositions()
    
    def reset_daily_pnl(self) -> None:
        """Reset daily P&L counters"""
        self.daily_realized_pnl = 0.0
        self.daily_commission = 0.0
        self.logger.info("Daily P&L counters reset")
    
    def export_positions(self) -> pd.DataFrame:
        """Export positions to DataFrame"""
        with self._position_lock:
            data = []
            for position in self.positions.values():
                data.append(position.to_dict())
            
            if data:
                return pd.DataFrame(data)
            else:
                return pd.DataFrame()
    
    def export_position_history(self) -> pd.DataFrame:
        """Export position history to DataFrame"""
        if self.position_history:
            return pd.DataFrame(self.position_history)
        else:
            return pd.DataFrame()
    
    def is_healthy(self) -> bool:
        """Check if position tracker is healthy"""
        return self._running

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
_position_tracker_instance: Optional[PositionTracker] = None

def get_position_tracker(ib_client=None, event_manager=None) -> PositionTracker:
    """Get singleton position tracker instance"""
    global _position_tracker_instance
    if _position_tracker_instance is None:
        _position_tracker_instance = PositionTracker(ib_client, event_manager)
    return _position_tracker_instance

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test position tracker
    from SpyderA_Core.SpyderA05_EventManager import EventManager
    
    # Mock IB client
    class MockIBClient:
        def __init__(self):
            self.callbacks = defaultdict(list)
        
        def register_callback(self, event, callback):
            self.callbacks[event].append(callback)
        
        def reqPositions(self):
            print("Requesting positions...")
        
        def reqMktData(self, tickerId, contract, genericTicks, snapshot, regulatorySnapshot, mktDataOptions):
            print(f"Requesting market data for ticker {tickerId}")
        
        def cancelMktData(self, tickerId):
            print(f"Cancelling market data for ticker {tickerId}")
    
    # Initialize
    event_manager = EventManager()
    ib_client = MockIBClient()
    tracker = PositionTracker(ib_client, event_manager)
    
    # Create test contract
    from ibapi.contract import Contract
    contract = Contract()
    contract.symbol = "SPY"
    contract.secType = "OPT"
    contract.strike = 450
    contract.right = "C"
    contract.lastTradeDateOrContractMonth = "20250620"
    contract.exchange = "SMART"
    contract.currency = "USD"
    
    # Add position
    position_id = tracker.add_position(
        contract=contract,
        quantity=10,
        entry_price=5.50,
        side=PositionSide.LONG,
        strategy_id="test_strategy"
    )
    print(f"Position added: {position_id}")
    
    # Simulate price update
    position = tracker.get_position(position_id)
    if position:
        position.current_price = 6.00
        position.underlying_price = 455.00
        unrealized, total = position.calculate_pnl()
        print(f"Unrealized P&L: ${unrealized:.2f}")
    
    # Get summary
    summary = tracker.get_position_summary()
    print(f"\nPosition Summary:")
    print(json.dumps(summary, indent=2))
    
    # Create a spread
    # Add another leg
    contract2 = Contract()
    contract2.symbol = "SPY"
    contract2.secType = "OPT"
    contract2.strike = 460
    contract2.right = "C"
    contract2.lastTradeDateOrContractMonth = "20250620"
    contract2.exchange = "SMART"
    contract2.currency = "USD"
    
    position_id2 = tracker.add_position(
        contract=contract2,
        quantity=10,
        entry_price=2.00,
        side=PositionSide.SHORT,
        strategy_id="test_strategy"
    )
    
    # Create vertical spread
    spread_id = tracker.create_spread(
        spread_type=SpreadType.VERTICAL,
        legs=[position_id, position_id2]
    )
    print(f"\nSpread created: {spread_id}")
    
    # Export positions
    df = tracker.export_positions()
    print(f"\nActive Positions:")
    print(df.to_string())
