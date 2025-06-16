#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderD01_BaseStrategy.py
Group: D (Trading Strategies)
Purpose: Abstract base strategy class

Description:
    This module provides the abstract base class for all trading strategies.
    It defines the interface that all strategies must implement and provides
    common functionality for position management, signal generation, and
    risk control.

Author: Mohamed Talib
Date: 2025-05-29
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import abc
from datetime import datetime, time
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum, auto
import threading
import uuid

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
from SpyderU_Utilities.SpyderU07_Constants import (
    OptionType, OrderAction, OrderType, OrderStatus,
    TimeInForce, PositionSide, SignalType
)
from SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType
from SpyderB_Broker.SpyderB06_ContractBuilder import Contract, OptionContract
from SpyderE_Risk.SpyderE01_RiskManager import RiskProfile
from SpyderF_Analysis.SpyderF01_Indicators import TechnicalIndicators

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Strategy states
STRATEGY_INACTIVE = "inactive"
STRATEGY_ACTIVE = "active"
STRATEGY_CLOSING = "closing"
STRATEGY_PAUSED = "paused"
STRATEGY_ERROR = "error"

# Position limits
MAX_POSITIONS_PER_STRATEGY = 10
MAX_ORDERS_PER_MINUTE = 20

# Performance thresholds
MIN_WIN_RATE = 0.40  # 40%
MAX_CONSECUTIVE_LOSSES = 5
MAX_DAILY_LOSS_PERCENT = 0.02  # 2%

# ==============================================================================
# ENUMS
# ==============================================================================
class StrategyState(Enum):
    """Strategy operational states"""
    INACTIVE = auto()
    INITIALIZING = auto()
    ACTIVE = auto()
    TRADING = auto()
    CLOSING_POSITIONS = auto()
    PAUSED = auto()
    ERROR = auto()
    STOPPED = auto()

class SignalStrength(Enum):
    """Trading signal strength levels"""
    WEAK = auto()
    MODERATE = auto()
    STRONG = auto()
    VERY_STRONG = auto()

class MarketRegime(Enum):
    """Market regime classification"""
    TRENDING_UP = auto()
    TRENDING_DOWN = auto()
    RANGING = auto()
    VOLATILE = auto()
    UNCERTAIN = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
class TradingSignal:
    """Trading signal data"""
    signal_id: str
    timestamp: datetime
    strategy_name: str
    signal_type: SignalType
    strength: SignalStrength
    contracts: List[Contract]
    entry_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    position_size: int = 1
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    expires_at: Optional[datetime] = None
    
    def is_valid(self) -> bool:
        """Check if signal is still valid"""
        if self.expires_at and datetime.now() > self.expires_at:
            return False
        return True

class StrategyPosition:
    """Strategy position tracking"""
    position_id: str
    strategy_name: str
    contracts: List[Contract]
    entry_time: datetime
    entry_price: float
    position_size: int
    side: PositionSide
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    fees: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def update_pnl(self, current_price: float) -> None:
        """Update P&L calculations"""
        self.current_price = current_price
        price_diff = current_price - self.entry_price
        if self.side == PositionSide.SHORT:
            price_diff = -price_diff
        self.unrealized_pnl = price_diff * self.position_size * 100  # SPY multiplier

class StrategyPerformance:
    """Strategy performance metrics"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    consecutive_wins: int = 0
    consecutive_losses: int = 0
    daily_pnl: float = 0.0
    
    def update(self, trade_pnl: float) -> None:
        """Update performance metrics"""
        self.total_trades += 1
        if trade_pnl > 0:
            self.winning_trades += 1
            self.consecutive_wins += 1
            self.consecutive_losses = 0
        else:
            self.losing_trades += 1
            self.consecutive_losses += 1
            self.consecutive_wins = 0
        
        self.total_pnl += trade_pnl
        self.daily_pnl += trade_pnl
        
        if self.total_trades > 0:
            self.win_rate = self.winning_trades / self.total_trades

# ==============================================================================
# BASE STRATEGY CLASS
# ==============================================================================
class BaseStrategy(abc.ABC):
    """
    Abstract base class for all trading strategies.
    
    This class provides the framework for implementing trading strategies
    with common functionality for position management, signal generation,
    and risk control.
    """
    
    def __init__(
        self,
        name: str,
        event_manager: EventManager,
        risk_profile: RiskProfile,
        config: Dict[str, Any]
    ):
        """
        Initialize base strategy.
        
        Args:
            name: Strategy name
            event_manager: Event manager instance
            risk_profile: Risk profile
            config: Strategy configuration
        """
        self.name = name
        self.event_manager = event_manager
        self.risk_profile = risk_profile
        self.config = config
        
        # Logging and error handling
        self.logger = SpyderLogger.get_logger(f"{__name__}.{name}")
        self.error_handler = SpyderErrorHandler()
        
        # State management
        self.state = StrategyState.INACTIVE
        self._state_lock = threading.RLock()
        
        # Position tracking
        self.positions: Dict[str, StrategyPosition] = {}
        self.pending_signals: List[TradingSignal] = []
        self.order_count = 0
        self.last_order_time = datetime.now()
        
        # Performance tracking
        self.performance = StrategyPerformance()
        self.start_time = datetime.now()
        
        # Market data
        self.current_price = 0.0
        self.market_regime = MarketRegime.UNCERTAIN
        self.indicators = TechnicalIndicators()
        
        # Configuration
        self._load_config()
        
        # Register event handlers
        self._register_event_handlers()
        
        self.logger.info(f"Strategy {name} initialized")
    
    # ==========================================================================
    # ABSTRACT METHODS
    # ==========================================================================
    @abc.abstractmethod
    def generate_signals(self, market_data: pd.DataFrame) -> List[TradingSignal]:
        """
        Generate trading signals based on market data.
        
        Args:
            market_data: Market data DataFrame
            
        Returns:
            List of trading signals
        """
        pass
    
    @abc.abstractmethod
    def should_enter_position(self, signal: TradingSignal) -> bool:
        """
        Determine if position should be entered.
        
        Args:
            signal: Trading signal
            
        Returns:
            True if position should be entered
        """
        pass
    
    @abc.abstractmethod
    def should_exit_position(self, position: StrategyPosition) -> bool:
        """
        Determine if position should be exited.
        
        Args:
            position: Current position
            
        Returns:
            True if position should be exited
        """
        pass
    
    @abc.abstractmethod
    def calculate_position_size(self, signal: TradingSignal) -> int:
        """
        Calculate position size for signal.
        
        Args:
            signal: Trading signal
            
        Returns:
            Position size
        """
        pass
    
    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def start(self) -> None:
        """Start strategy"""
        with self._state_lock:
            if self.state != StrategyState.INACTIVE:
                self.logger.warning(f"Cannot start strategy in state {self.state}")
                return
            
            self.state = StrategyState.INITIALIZING
            
            try:
                # Initialize strategy
                self._initialize()
                
                # Validate configuration
                if not self._validate_config():
                    raise ValueError("Invalid strategy configuration")
                
                # Set active state
                self.state = StrategyState.ACTIVE
                
                # Emit start event
                self.event_manager.emit(Event(
                    EventType.STRATEGY,
                    {
                        'action': 'started',
                        'strategy': self.name,
                        'config': self.config
                    }
                ))
                
                self.logger.info(f"Strategy {self.name} started")
                
            except Exception as e:
                self.state = StrategyState.ERROR
                self.logger.error(f"Failed to start strategy: {e}")
                raise
    
    def stop(self) -> None:
        """Stop strategy"""
        with self._state_lock:
            if self.state == StrategyState.INACTIVE:
                return
            
            self.logger.info(f"Stopping strategy {self.name}")
            
            # Close all positions
            if self.positions:
                self.state = StrategyState.CLOSING_POSITIONS
                self._close_all_positions()
            
            # Set inactive state
            self.state = StrategyState.STOPPED
            
            # Emit stop event
            self.event_manager.emit(Event(
                EventType.STRATEGY,
                {
                    'action': 'stopped',
                    'strategy': self.name,
                    'performance': self._get_performance_summary()
                }
            ))
            
            self.logger.info(f"Strategy {self.name} stopped")
    
    def pause(self) -> None:
        """Pause strategy"""
        with self._state_lock:
            if self.state == StrategyState.ACTIVE:
                self.state = StrategyState.PAUSED
                self.logger.info(f"Strategy {self.name} paused")
    
    def resume(self) -> None:
        """Resume strategy"""
        with self._state_lock:
            if self.state == StrategyState.PAUSED:
                self.state = StrategyState.ACTIVE
                self.logger.info(f"Strategy {self.name} resumed")
    
    # ==========================================================================
    # TRADING METHODS
    # ==========================================================================
    def process_market_data(self, market_data: pd.DataFrame) -> None:
        """
        Process market data and generate signals.
        
        Args:
            market_data: Market data DataFrame
        """
        if self.state != StrategyState.ACTIVE:
            return
        
        try:
            # Update current price
            self.current_price = market_data['close'].iloc[-1]
            
            # Update market regime
            self._update_market_regime(market_data)
            
            # Check existing positions
            self._manage_positions()
            
            # Generate new signals
            signals = self.generate_signals(market_data)
            
            # Process signals
            for signal in signals:
                if self._validate_signal(signal):
                    self._process_signal(signal)
            
            # Update performance
            self._update_performance()
            
        except Exception as e:
            self.logger.error(f"Error processing market data: {e}")
            self.error_handler.handle_error(e, self.name)
    
    def _process_signal(self, signal: TradingSignal) -> None:
        """Process trading signal"""
        # Check risk limits
        if not self._check_risk_limits(signal):
            self.logger.warning(f"Signal rejected due to risk limits: {signal.signal_id}")
            return
        
        # Check if should enter
        if not self.should_enter_position(signal):
            self.logger.info(f"Signal rejected by entry logic: {signal.signal_id}")
            return
        
        # Calculate position size
        position_size = self.calculate_position_size(signal)
        if position_size <= 0:
            self.logger.warning(f"Invalid position size for signal: {signal.signal_id}")
            return
        
        signal.position_size = position_size
        
        # Add to pending signals
        self.pending_signals.append(signal)
        
        # Emit signal event
        self.event_manager.emit(Event(
            EventType.SIGNAL,
            {
                'strategy': self.name,
                'signal': signal,
                'action': 'generated'
            }
        ))
        
        self.logger.info(f"Signal generated: {signal.signal_type} {signal.strength}")
    
    def _manage_positions(self) -> None:
        """Manage existing positions"""
        for position_id, position in list(self.positions.items()):
            # Update P&L
            position.update_pnl(self.current_price)
            
            # Check exit conditions
            if self.should_exit_position(position):
                self._close_position(position_id)
            
            # Check stop loss
            elif position.stop_loss and self._check_stop_loss(position):
                self.logger.info(f"Stop loss triggered for position {position_id}")
                self._close_position(position_id)
            
            # Check take profit
            elif position.take_profit and self._check_take_profit(position):
                self.logger.info(f"Take profit triggered for position {position_id}")
                self._close_position(position_id)
    
    def _close_position(self, position_id: str) -> None:
        """Close a position"""
        if position_id not in self.positions:
            return
        
        position = self.positions[position_id]
        
        # Emit close event
        self.event_manager.emit(Event(
            EventType.STRATEGY,
            {
                'action': 'close_position',
                'strategy': self.name,
                'position': position,
                'reason': 'strategy_exit'
            }
        ))
        
        # Update performance
        self.performance.update(position.unrealized_pnl + position.realized_pnl)
        
        # Remove position
        del self.positions[position_id]
        
        self.logger.info(f"Position closed: {position_id}, P&L: {position.unrealized_pnl:.2f}")
    
    def _close_all_positions(self) -> None:
        """Close all positions"""
        position_ids = list(self.positions.keys())
        for position_id in position_ids:
            self._close_position(position_id)
    
    # ==========================================================================
    # RISK MANAGEMENT
    # ==========================================================================
    def _check_risk_limits(self, signal: TradingSignal) -> bool:
        """Check if signal meets risk limits"""
        # Check position limit
        if len(self.positions) >= MAX_POSITIONS_PER_STRATEGY:
            return False
        
        # Check order rate limit
        if self._check_order_rate_limit():
            return False
        
        # Check daily loss limit
        if self.performance.daily_pnl < -MAX_DAILY_LOSS_PERCENT * self.risk_profile.account_size:
            return False
        
        # Check consecutive losses
        if self.performance.consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
            return False
        
        return True
    
    def _check_order_rate_limit(self) -> bool:
        """Check order rate limit"""
        now = datetime.now()
        if (now - self.last_order_time).seconds < 3:  # 3 second minimum between orders
            return True
        
        # Reset counter if minute passed
        if (now - self.last_order_time).seconds >= 60:
            self.order_count = 0
            self.last_order_time = now
        
        return self.order_count >= MAX_ORDERS_PER_MINUTE
    
    def _check_stop_loss(self, position: StrategyPosition) -> bool:
        """Check if stop loss hit"""
        if not position.stop_loss:
            return False
        
        if position.side == PositionSide.LONG:
            return self.current_price <= position.stop_loss
        else:
            return self.current_price >= position.stop_loss
    
    def _check_take_profit(self, position: StrategyPosition) -> bool:
        """Check if take profit hit"""
        if not position.take_profit:
            return False
        
        if position.side == PositionSide.LONG:
            return self.current_price >= position.take_profit
        else:
            return self.current_price <= position.take_profit
    
    # ==========================================================================
    # MARKET ANALYSIS
    # ==========================================================================
    def _update_market_regime(self, market_data: pd.DataFrame) -> None:
        """Update market regime classification"""
        if len(market_data) < 50:
            return
        
        # Calculate trend
        sma_20 = market_data['close'].rolling(20).mean().iloc[-1]
        sma_50 = market_data['close'].rolling(50).mean().iloc[-1]
        
        # Calculate volatility
        returns = market_data['close'].pct_change()
        volatility = returns.rolling(20).std().iloc[-1]
        
        # Classify regime
        if sma_20 > sma_50 and volatility < 0.02:
            self.market_regime = MarketRegime.TRENDING_UP
        elif sma_20 < sma_50 and volatility < 0.02:
            self.market_regime = MarketRegime.TRENDING_DOWN
        elif volatility > 0.03:
            self.market_regime = MarketRegime.VOLATILE
        elif abs(sma_20 - sma_50) / sma_50 < 0.01:
            self.market_regime = MarketRegime.RANGING
        else:
            self.market_regime = MarketRegime.UNCERTAIN
    
    # ==========================================================================
    # CONFIGURATION
    # ==========================================================================
    def _load_config(self) -> None:
        """Load strategy configuration"""
        # Default configuration
        self.max_positions = self.config.get('max_positions', 5)
        self.position_size_pct = self.config.get('position_size_pct', 0.02)
        self.stop_loss_pct = self.config.get('stop_loss_pct', 0.02)
        self.take_profit_pct = self.config.get('take_profit_pct', 0.05)
        self.entry_filters = self.config.get('entry_filters', {})
        self.exit_filters = self.config.get('exit_filters', {})
    
    def _validate_config(self) -> bool:
        """Validate strategy configuration"""
        if self.max_positions <= 0 or self.max_positions > MAX_POSITIONS_PER_STRATEGY:
            return False
        
        if self.position_size_pct <= 0 or self.position_size_pct > 0.1:
            return False
        
        return True
    
    def update_config(self, new_config: Dict[str, Any]) -> None:
        """Update strategy configuration"""
        self.config.update(new_config)
        self._load_config()
        
        if self._validate_config():
            self.logger.info(f"Strategy configuration updated")
            
            # Emit config update event
            self.event_manager.emit(Event(
                EventType.STRATEGY,
                {
                    'action': 'config_updated',
                    'strategy': self.name,
                    'config': self.config
                }
            ))
        else:
            self.logger.error("Invalid configuration update rejected")
    
    # ==========================================================================
    # UTILITIES
    # ==========================================================================
    def _initialize(self) -> None:
        """Initialize strategy (can be overridden)"""
        pass
    
    def _validate_signal(self, signal: TradingSignal) -> bool:
        """Validate trading signal"""
        if not signal.is_valid():
            return False
        
        if signal.confidence < 0.5:
            return False
        
        if not signal.contracts:
            return False
        
        return True
    
    def _update_performance(self) -> None:
        """Update performance metrics"""
        # Calculate current metrics
        total_pnl = sum(p.unrealized_pnl + p.realized_pnl for p in self.positions.values())
        total_pnl += self.performance.total_pnl
        
        # Update max drawdown
        if total_pnl < 0:
            self.performance.max_drawdown = min(self.performance.max_drawdown, total_pnl)
    
    def _get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary"""
        return {
            'total_trades': self.performance.total_trades,
            'win_rate': self.performance.win_rate,
            'total_pnl': self.performance.total_pnl,
            'max_drawdown': self.performance.max_drawdown,
            'sharpe_ratio': self.performance.sharpe_ratio,
            'profit_factor': self.performance.profit_factor
        }
    
    def _register_event_handlers(self) -> None:
        """Register event handlers"""
        # Subscribe to relevant events
        self.event_manager.subscribe(
            self._handle_market_event,
            event_filter=lambda e: e.type == EventType.MARKET_DATA,
            subscriber_id=f"strategy_{self.name}"
        )
        
        self.event_manager.subscribe(
            self._handle_order_event,
            event_filter=lambda e: e.type == EventType.ORDER,
            subscriber_id=f"strategy_{self.name}_orders"
        )
    
    def _handle_market_event(self, event: Event) -> None:
        """Handle market data events"""
        if event.data.get('symbol') == 'SPY':
            market_data = event.data.get('data')
            if market_data is not None:
                self.process_market_data(market_data)
    
    def _handle_order_event(self, event: Event) -> None:
        """Handle order events"""
        if event.data.get('strategy') == self.name:
            action = event.data.get('action')
            if action == 'filled':
                self._handle_order_filled(event.data)
            elif action == 'rejected':
                self._handle_order_rejected(event.data)
    
    def _handle_order_filled(self, order_data: Dict[str, Any]) -> None:
        """Handle order filled event"""
        # Create position from filled order
        position = StrategyPosition(
            position_id=str(uuid.uuid4()),
            strategy_name=self.name,
            contracts=order_data['contracts'],
            entry_time=datetime.now(),
            entry_price=order_data['fill_price'],
            position_size=order_data['quantity'],
            side=PositionSide.LONG if order_data['action'] == OrderAction.BUY else PositionSide.SHORT,
            stop_loss=order_data.get('stop_loss'),
            take_profit=order_data.get('take_profit')
        )
        
        self.positions[position.position_id] = position
        self.order_count += 1
        
        self.logger.info(f"Position opened: {position.position_id}")
    
    def _handle_order_rejected(self, order_data: Dict[str, Any]) -> None:
        """Handle order rejected event"""
        self.logger.warning(f"Order rejected: {order_data.get('reason', 'Unknown')}")
    
    # ==========================================================================
    # PUBLIC INTERFACE
    # ==========================================================================
    def get_state(self) -> StrategyState:
        """Get current strategy state"""
        return self.state
    
    def get_positions(self) -> List[StrategyPosition]:
        """Get current positions"""
        return list(self.positions.values())
    
    def get_performance(self) -> StrategyPerformance:
        """Get performance metrics"""
        return self.performance
    
    def get_signals(self) -> List[TradingSignal]:
        """Get pending signals"""
        return [s for s in self.pending_signals if s.is_valid()]

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Example implementation of concrete strategy
    class ExampleStrategy(BaseStrategy):
        """Example strategy implementation"""
        
        def generate_signals(self, market_data: pd.DataFrame) -> List[TradingSignal]:
            """Generate example signals"""
            signals = []
            
            # Simple moving average crossover
            if len(market_data) >= 50:
                sma_20 = market_data['close'].rolling(20).mean()
                sma_50 = market_data['close'].rolling(50).mean()
                
                # Check for crossover
                if sma_20.iloc[-1] > sma_50.iloc[-1] and sma_20.iloc[-2] <= sma_50.iloc[-2]:
                    signal = TradingSignal(
                        signal_id=str(uuid.uuid4()),
                        timestamp=datetime.now(),
                        strategy_name=self.name,
                        signal_type=SignalType.BUY,
                        strength=SignalStrength.MODERATE,
                        contracts=[],  # Would be filled with actual contracts
                        entry_price=market_data['close'].iloc[-1],
                        confidence=0.7
                    )
                    signals.append(signal)
            
            return signals
        
        def should_enter_position(self, signal: TradingSignal) -> bool:
            """Check entry conditions"""
            # Add custom entry logic
            return signal.confidence >= 0.6
        
        def should_exit_position(self, position: StrategyPosition) -> bool:
            """Check exit conditions"""
            # Exit if 2% profit or 1% loss
            pnl_pct = position.unrealized_pnl / (position.entry_price * position.position_size * 100)
            return pnl_pct >= 0.02 or pnl_pct <= -0.01
        
        def calculate_position_size(self, signal: TradingSignal) -> int:
            """Calculate position size"""
            # Use 2% of account
            account_value = self.risk_profile.account_size
            position_value = account_value * self.position_size_pct
            contracts = int(position_value / (signal.entry_price * 100))
            return max(1, min(contracts, 10))
    
    # Test the strategy
    from SpyderA_Core.SpyderA05_EventManager import EventManager
    from SpyderE_Risk.SpyderE01_RiskManager import RiskProfile
    
    event_manager = EventManager()
    risk_profile = RiskProfile(
        account_size=100000,
        max_position_size=0.02,
        max_portfolio_risk=0.06,
        max_loss_per_trade=0.01
    )
    
    strategy = ExampleStrategy(
        name="example_strategy",
        event_manager=event_manager,
        risk_profile=risk_profile,
        config={
            'max_positions': 5,
            'position_size_pct': 0.02
        }
    )
    
    # Start strategy
    strategy.start()
    
    # Simulate market data
    dates = pd.date_range(end=datetime.now(), periods=100, freq='5min')
    prices = 100 + np.random.randn(100).cumsum()
    market_data = pd.DataFrame({
        'timestamp': dates,
        'open': prices + np.random.randn(100) * 0.1,
        'high': prices + abs(np.random.randn(100) * 0.2),
        'low': prices - abs(np.random.randn(100) * 0.2),
        'close': prices,
        'volume': np.random.randint(1000000, 5000000, 100)
    })
    
    # Process data
    strategy.process_market_data(market_data)
    
    # Print results
    print(f"Strategy State: {strategy.get_state()}")
    print(f"Positions: {len(strategy.get_positions())}")
    print(f"Signals: {len(strategy.get_signals())}")
    print(f"Performance: {strategy.get_performance()}")
    
    # Stop strategy
    strategy.stop()
