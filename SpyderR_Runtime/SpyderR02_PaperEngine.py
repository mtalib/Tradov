#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderR02_PaperEngine.py
Group: R (Runtime Operations)
Purpose: Real-time paper trading engine with IB API integration

Description:
    This module manages paper trading operations using Interactive Brokers'
    paper trading account. It provides real market conditions without risk,
    tracking all metrics needed for the learning algorithm to optimize
    based on actual market behavior rather than backtesting assumptions.

Author: Mohamed Talib
Date: 2025-05-31
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import datetime
import json
import threading
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import time

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np
from ibapi.contract import Contract
from ibapi.order import Order

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderB_Broker.SpyderB01_IBClient import IBClient as SpyderIBClient
from SpyderB_Broker.SpyderB02_OrderManager import OrderManager
from SpyderB_Broker.SpyderB03_PositionTracker import PositionTracker
from SpyderD_Strategies.SpyderD01_BaseStrategy import BaseStrategy, Signal
from SpyderE_Risk.SpyderE01_RiskManager import RiskManager
from SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Paper trading specific settings
PAPER_ACCOUNT_PREFIX = "DU"  # IB paper accounts start with DU
PAPER_MODE_WARNING = """
╔════════════════════════════════════════════════════════════════════════╗
║                        PAPER TRADING MODE ACTIVE                       ║
╠════════════════════════════════════════════════════════════════════════╣
║ • Using IB Paper Trading Account                                       ║
║ • Real market data and execution simulation                            ║
║ • No real money at risk                                                ║
║ • All trades and metrics are tracked for learning                      ║
║ • Minimum 4-8 weeks recommended before live trading                    ║
╚════════════════════════════════════════════════════════════════════════╝
"""

# Minimum paper trading requirements before live
MIN_PAPER_DAYS = 28  # 4 weeks minimum
MIN_PAPER_TRADES = 50  # Minimum number of trades
MIN_PAPER_WIN_RATE = 0.40  # Minimum 40% win rate

# ==============================================================================
# ENUMS
# ==============================================================================
class PaperTradingStatus(Enum):
    """Paper trading session status"""
    NOT_STARTED = "not_started"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    READY_FOR_LIVE = "ready_for_live"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
class PaperTradingSession:
    """Paper trading session information"""
    session_id: str
    start_date: datetime.datetime
    end_date: Optional[datetime.datetime] = None
    status: PaperTradingStatus = PaperTradingStatus.NOT_STARTED
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    initial_capital: float = 100000.0
    current_capital: float = 100000.0
    
    # Execution quality metrics
    avg_fill_time_ms: float = 0.0
    avg_slippage: float = 0.0
    rejected_orders: int = 0
    partial_fills: int = 0
    
    # Market condition tracking
    market_conditions: List[Dict[str, Any]] = field(default_factory=list)
    spread_history: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'session_id': self.session_id,
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'status': self.status.value,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'total_pnl': self.total_pnl,
            'initial_capital': self.initial_capital,
            'current_capital': self.current_capital,
            'avg_fill_time_ms': self.avg_fill_time_ms,
            'avg_slippage': self.avg_slippage,
            'rejected_orders': self.rejected_orders,
            'partial_fills': self.partial_fills,
            'duration_days': self.get_duration_days(),
            'win_rate': self.get_win_rate(),
            'is_ready_for_live': self.is_ready_for_live()
        }
    
    def get_duration_days(self) -> int:
        """Get session duration in days"""
        if self.end_date:
            return (self.end_date - self.start_date).days
        return (datetime.datetime.now() - self.start_date).days
    
    def get_win_rate(self) -> float:
        """Calculate win rate"""
        if self.total_trades == 0:
            return 0.0
        return self.winning_trades / self.total_trades
    
    def is_ready_for_live(self) -> bool:
        """Check if ready for live trading"""
        return (
            self.get_duration_days() >= MIN_PAPER_DAYS and
            self.total_trades >= MIN_PAPER_TRADES and
            self.get_win_rate() >= MIN_PAPER_WIN_RATE
        )

class PaperTradeRecord:
    """Detailed paper trade record for learning"""
    trade_id: str
    timestamp: datetime.datetime
    strategy: str
    signal: Signal
    
    # Order details
    order_type: str
    limit_price: Optional[float]
    
    # Execution details
    requested_price: float
    fill_price: float
    slippage: float
    fill_time_ms: float
    bid_at_entry: float
    ask_at_entry: float
    spread_at_entry: float
    
    # Position details
    quantity: int
    commission: float
    
    # Exit details
    exit_time: Optional[datetime.datetime] = None
    exit_price: Optional[float] = None
    exit_bid: Optional[float] = None
    exit_ask: Optional[float] = None
    exit_spread: Optional[float] = None
    
    # Results
    pnl: float = 0.0
    pnl_percent: float = 0.0
    held_minutes: float = 0.0
    
    # Market conditions
    vix_at_entry: float = 0.0
    spy_volume_at_entry: int = 0
    market_trend: str = ""
    
    # Greeks at entry (for learning)
    delta_at_entry: float = 0.0
    gamma_at_entry: float = 0.0
    theta_at_entry: float = 0.0
    vega_at_entry: float = 0.0
    iv_at_entry: float = 0.0

# ==============================================================================
# PAPER TRADING ENGINE CLASS
# ==============================================================================
class PaperTradingEngine:
    """
    Paper trading engine using IB paper account.
    
    Features:
    - Real market data and execution
    - Comprehensive trade tracking
    - Execution quality metrics
    - Market condition recording
    - Learning data collection
    """
    
    def __init__(
        self,
        ib_client: SpyderIBClient,
        event_manager: EventManager,
        strategies: List[BaseStrategy],
        initial_capital: float = 100000.0
    ):
        """
        Initialize paper trading engine.
        
        Args:
            ib_client: IB client connection
            event_manager: Event manager
            strategies: List of strategies to paper trade
            initial_capital: Starting capital for paper trading
        """
        self.ib_client = ib_client
        self.event_manager = event_manager
        self.strategies = strategies
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Validate paper account
        self._validate_paper_account()
        
        # Initialize components
        self.order_manager = OrderManager(ib_client, event_manager)
        self.position_tracker = PositionTracker(ib_client, event_manager)
        self.risk_manager = RiskManager(event_manager, {})
        
        # Paper trading session
        self.session = PaperTradingSession(
            session_id=f"PAPER_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}",
            start_date=datetime.datetime.now(),
            initial_capital=initial_capital,
            current_capital=initial_capital
        )
        
        # Trade tracking
        self.active_trades: Dict[str, PaperTradeRecord] = {}
        self.completed_trades: List[PaperTradeRecord] = []
        self.trade_lock = threading.RLock()
        
        # Execution tracking
        self.order_timestamps: Dict[int, datetime.datetime] = {}
        self.fill_times: List[float] = []
        self.slippage_history: List[float] = []
        
        # Market data cache
        self.market_data_cache: Dict[str, Any] = {}
        self.spread_cache: Dict[str, Tuple[float, float]] = {}
        
        # Learning data collection
        self.learning_data: List[Dict[str, Any]] = []
        
        # Print warning
        print(PAPER_MODE_WARNING)
        self.logger.info(f"Paper trading engine initialized - Session: {self.session.session_id}")
        
        # Register event handlers
        self._register_event_handlers()
    
    # ==========================================================================
    # INITIALIZATION AND VALIDATION
    # ==========================================================================
    def _validate_paper_account(self) -> None:
        """Validate that we're connected to a paper account"""
        account_id = self.ib_client.account_id
        
        if not account_id or not account_id.startswith(PAPER_ACCOUNT_PREFIX):
            raise ValueError(
                f"Not connected to paper account! Account ID: {account_id}\n"
                "Paper accounts should start with 'DU'. Please connect to your paper account."
            )
        
        self.logger.info(f"Connected to paper account: {account_id}")
    
    def _register_event_handlers(self) -> None:
        """Register event handlers for paper trading"""
        # Market data events
        self.event_manager.subscribe(
            self._handle_market_data,
            event_type=EventType.MARKET_DATA,
            subscriber_id="paper_engine_market"
        )
        
        # Order events
        self.event_manager.subscribe(
            self._handle_order_event,
            event_type=EventType.ORDER,
            subscriber_id="paper_engine_order"
        )
        
        # Fill events
        self.event_manager.subscribe(
            self._handle_fill_event,
            event_type=EventType.FILL,
            subscriber_id="paper_engine_fill"
        )
    
    # ==========================================================================
    # MAIN TRADING LOOP
    # ==========================================================================
    def start(self) -> None:
        """Start paper trading session"""
        self.session.status = PaperTradingStatus.ACTIVE
        self.logger.info("Paper trading session started")
        
        # Start position tracker
        self.position_tracker.start_tracking()
        
        # Emit session start event
        self.event_manager.emit(Event(
            EventType.SYSTEM,
            {
                'type': 'paper_session_start',
                'session_id': self.session.session_id,
                'initial_capital': self.session.initial_capital
            }
        ))
    
    def stop(self) -> None:
        """Stop paper trading session"""
        self.session.status = PaperTradingStatus.PAUSED
        self.session.end_date = datetime.datetime.now()
        
        # Stop components
        self.position_tracker.stop_tracking()
        
        # Save session data
        self._save_session_data()
        
        # Print summary
        self._print_session_summary()
        
        self.logger.info("Paper trading session stopped")
    
    def process_market_data(self, market_data: Dict[str, Any]) -> None:
        """
        Process market data and generate signals.
        
        Args:
            market_data: Current market data
        """
        if self.session.status != PaperTradingStatus.ACTIVE:
            return
        
        # Update market data cache
        self._update_market_cache(market_data)
        
        # Check each strategy
        for strategy in self.strategies:
            try:
                # Generate signal
                signal = strategy.generate_signal(market_data)
                
                if signal:
                    # Validate with risk manager
                    if self._validate_signal(signal):
                        # Execute paper trade
                        self._execute_paper_trade(signal)
                
            except Exception as e:
                self.logger.error(f"Error processing strategy {strategy.__class__.__name__}: {e}")
                self.error_handler.handle_error(e)
    
    # ==========================================================================
    # TRADE EXECUTION
    # ==========================================================================
    def _execute_paper_trade(self, signal: Signal) -> None:
        """Execute paper trade with full tracking"""
        try:
            # Record pre-trade market conditions
            market_snapshot = self._capture_market_snapshot(signal.symbol)
            
            # Create contract
            contract = self._create_option_contract(signal)
            
            # Get current bid-ask
            bid, ask = self._get_current_bid_ask(contract)
            spread = ask - bid
            
            # Determine execution price (realistic)
            if signal.order_type == 'MARKET':
                # Market orders fill at ask for buys, bid for sells
                requested_price = ask if signal.signal_type == 'BUY' else bid
            else:
                # Limit orders
                requested_price = signal.limit_price or ((bid + ask) / 2)
            
            # Create order
            order = self._create_order(signal)
            
            # Record order timestamp
            order_time = datetime.datetime.now()
            self.order_timestamps[order.orderId] = order_time
            
            # Create trade record
            trade_record = PaperTradeRecord(
                trade_id=f"PT_{order.orderId}",
                timestamp=order_time,
                strategy=signal.strategy,
                signal=signal,
                order_type=signal.order_type,
                limit_price=signal.limit_price,
                requested_price=requested_price,
                fill_price=0.0,  # Updated on fill
                slippage=0.0,    # Updated on fill
                fill_time_ms=0.0, # Updated on fill
                bid_at_entry=bid,
                ask_at_entry=ask,
                spread_at_entry=spread,
                quantity=signal.quantity,
                commission=0.65 * signal.quantity,  # IB commission
                vix_at_entry=market_snapshot.get('vix', 0),
                spy_volume_at_entry=market_snapshot.get('volume', 0),
                market_trend=market_snapshot.get('trend', ''),
                delta_at_entry=market_snapshot.get('delta', 0),
                gamma_at_entry=market_snapshot.get('gamma', 0),
                theta_at_entry=market_snapshot.get('theta', 0),
                vega_at_entry=market_snapshot.get('vega', 0),
                iv_at_entry=market_snapshot.get('iv', 0)
            )
            
            # Store trade record
            with self.trade_lock:
                self.active_trades[trade_record.trade_id] = trade_record
            
            # Place order through IB
            self.order_manager.place_order(contract, order)
            
            # Log execution
            self.logger.info(
                f"Paper trade placed: {signal.signal_type} {signal.quantity} "
                f"{signal.symbol} @ {requested_price:.2f} (spread: ${spread:.2f})"
            )
            
        except Exception as e:
            self.logger.error(f"Error executing paper trade: {e}")
            self.error_handler.handle_error(e)
            self.session.rejected_orders += 1
    
    def _validate_signal(self, signal: Signal) -> bool:
        """Validate signal with risk management"""
        # Check position limits
        current_positions = len(self.active_trades)
        if current_positions >= 5:  # Max 5 concurrent positions
            self.logger.debug(f"Position limit reached: {current_positions}")
            return False
        
        # Check capital allocation
        position_value = signal.quantity * 100 * signal.limit_price if signal.limit_price else 0
        if position_value > self.session.current_capital * 0.1:  # Max 10% per position
            self.logger.debug(f"Position too large: ${position_value:.2f}")
            return False
        
        # Additional risk checks
        return self.risk_manager.validate_signal(signal)
    
    # ==========================================================================
    # EVENT HANDLERS
    # ==========================================================================
    def _handle_market_data(self, event: Event) -> None:
        """Handle market data events"""
        self.process_market_data(event.data)
    
    def _handle_order_event(self, event: Event) -> None:
        """Handle order status events"""
        order_id = event.data.get('order_id')
        status = event.data.get('status')
        
        if status == 'Cancelled' or status == 'ApiCancelled':
            # Order rejected
            self.session.rejected_orders += 1
            self.logger.warning(f"Order {order_id} rejected: {status}")
    
    def _handle_fill_event(self, event: Event) -> None:
        """Handle order fill events"""
        order_id = event.data.get('order_id')
        fill_price = event.data.get('fill_price')
        fill_time = event.data.get('timestamp')
        
        # Find corresponding trade
        trade_id = f"PT_{order_id}"
        
        with self.trade_lock:
            if trade_id in self.active_trades:
                trade = self.active_trades[trade_id]
                
                # Update fill information
                trade.fill_price = fill_price
                
                # Calculate fill time
                if order_id in self.order_timestamps:
                    fill_duration = (fill_time - self.order_timestamps[order_id]).total_seconds() * 1000
                    trade.fill_time_ms = fill_duration
                    self.fill_times.append(fill_duration)
                
                # Calculate slippage
                trade.slippage = abs(fill_price - trade.requested_price)
                self.slippage_history.append(trade.slippage)
                
                # Update session metrics
                if len(self.fill_times) > 0:
                    self.session.avg_fill_time_ms = np.mean(self.fill_times)
                if len(self.slippage_history) > 0:
                    self.session.avg_slippage = np.mean(self.slippage_history)
                
                self.logger.info(
                    f"Paper trade filled: {trade_id} @ {fill_price:.2f} "
                    f"(slippage: ${trade.slippage:.2f}, fill time: {trade.fill_time_ms:.0f}ms)"
                )
    
    # ==========================================================================
    # POSITION MANAGEMENT
    # ==========================================================================
    def check_exit_conditions(self) -> None:
        """Check exit conditions for all positions"""
        with self.trade_lock:
            for trade_id, trade in list(self.active_trades.items()):
                if self._should_exit_position(trade):
                    self._exit_paper_position(trade)
    
    def _should_exit_position(self, trade: PaperTradeRecord) -> bool:
        """Check if position should be exited"""
        # Time-based exit
        if trade.signal.metadata.get('exit_time'):
            if datetime.datetime.now() >= trade.signal.metadata['exit_time']:
                return True
        
        # Stop loss / take profit
        current_price = self._get_current_price(trade.signal.symbol)
        if current_price:
            # Calculate P&L
            pnl_percent = (current_price - trade.fill_price) / trade.fill_price
            
            if trade.signal.stop_loss and pnl_percent <= -trade.signal.stop_loss:
                return True
            
            if trade.signal.take_profit and pnl_percent >= trade.signal.take_profit:
                return True
        
        return False
    
    def _exit_paper_position(self, trade: PaperTradeRecord) -> None:
        """Exit paper position with tracking"""
        try:
            # Get current market data
            contract = self._create_option_contract(trade.signal)
            bid, ask = self._get_current_bid_ask(contract)
            
            # Determine exit price (realistic)
            if trade.signal.signal_type == 'BUY':
                # Closing long position - sell at bid
                exit_price = bid
            else:
                # Closing short position - buy at ask
                exit_price = ask
            
            # Update trade record
            trade.exit_time = datetime.datetime.now()
            trade.exit_price = exit_price
            trade.exit_bid = bid
            trade.exit_ask = ask
            trade.exit_spread = ask - bid
            
            # Calculate results
            if trade.signal.signal_type == 'BUY':
                trade.pnl = (exit_price - trade.fill_price) * trade.quantity * 100
            else:
                trade.pnl = (trade.fill_price - exit_price) * trade.quantity * 100
            
            trade.pnl -= trade.commission * 2  # Entry and exit commissions
            trade.pnl_percent = trade.pnl / (trade.fill_price * trade.quantity * 100)
            trade.held_minutes = (trade.exit_time - trade.timestamp).total_seconds() / 60
            
            # Update session stats
            self.session.total_trades += 1
            if trade.pnl > 0:
                self.session.winning_trades += 1
            else:
                self.session.losing_trades += 1
            
            self.session.total_pnl += trade.pnl
            self.session.current_capital += trade.pnl
            
            # Move to completed trades
            self.completed_trades.append(trade)
            del self.active_trades[trade.trade_id]
            
            # Add to learning data
            self._add_to_learning_data(trade)
            
            self.logger.info(
                f"Paper position closed: {trade.trade_id} "
                f"P&L: ${trade.pnl:.2f} ({trade.pnl_percent:.1%}) "
                f"Held: {trade.held_minutes:.0f} minutes"
            )
            
        except Exception as e:
            self.logger.error(f"Error exiting paper position: {e}")
            self.error_handler.handle_error(e)
    
    # ==========================================================================
    # MARKET DATA HELPERS
    # ==========================================================================
    def _update_market_cache(self, market_data: Dict[str, Any]) -> None:
        """Update market data cache"""
        symbol = market_data.get('symbol')
        if symbol:
            self.market_data_cache[symbol] = market_data
            
            # Update spread cache if bid/ask available
            if 'bid' in market_data and 'ask' in market_data:
                self.spread_cache[symbol] = (market_data['bid'], market_data['ask'])
    
    def _capture_market_snapshot(self, symbol: str) -> Dict[str, Any]:
        """Capture current market conditions"""
        snapshot = {
            'timestamp': datetime.datetime.now(),
            'symbol': symbol
        }
        
        # Get cached market data
        if symbol in self.market_data_cache:
            data = self.market_data_cache[symbol]
            snapshot.update({
                'price': data.get('last', 0),
                'volume': data.get('volume', 0),
                'bid': data.get('bid', 0),
                'ask': data.get('ask', 0),
                'iv': data.get('implied_volatility', 0),
                'delta': data.get('delta', 0),
                'gamma': data.get('gamma', 0),
                'theta': data.get('theta', 0),
                'vega': data.get('vega', 0)
            })
        
        # Add market internals
        snapshot['vix'] = self.market_data_cache.get('VIX', {}).get('last', 0)
        
        # Determine trend
        spy_data = self.market_data_cache.get('SPY', {})
        if 'last' in spy_data and 'open' in spy_data:
            change = (spy_data['last'] - spy_data['open']) / spy_data['open']
            if change > 0.005:
                snapshot['trend'] = 'bullish'
            elif change < -0.005:
                snapshot['trend'] = 'bearish'
            else:
                snapshot['trend'] = 'neutral'
        
        return snapshot
    
    def _get_current_bid_ask(self, contract: Contract) -> Tuple[float, float]:
        """Get current bid-ask for contract"""
        symbol = f"{contract.symbol}_{contract.lastTradeDateOrContractMonth}_{contract.strike}_{contract.right}"
        
        if symbol in self.spread_cache:
            return self.spread_cache[symbol]
        
        # Default spreads based on moneyness (realistic)
        # This is more realistic than perfect mid prices
        if contract.strike:
            spy_price = self.market_data_cache.get('SPY', {}).get('last', 400)
            moneyness = abs(contract.strike - spy_price) / spy_price
            
            if moneyness < 0.01:  # ATM
                spread = 0.10
            elif moneyness < 0.02:  # Near ATM
                spread = 0.15
            elif moneyness < 0.05:  # OTM
                spread = 0.25
            else:  # Far OTM
                spread = 0.40
            
            mid_price = 1.00  # Placeholder
            return (mid_price - spread/2, mid_price + spread/2)
        
        return (1.00, 1.10)  # Default wide spread
    
    def _get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for symbol"""
        if symbol in self.market_data_cache:
            return self.market_data_cache[symbol].get('last')
        return None
    
    # ==========================================================================
    # LEARNING DATA COLLECTION
    # ==========================================================================
    def _add_to_learning_data(self, trade: PaperTradeRecord) -> None:
        """Add completed trade to learning dataset"""
        learning_record = {
            # Trade identification
            'trade_id': trade.trade_id,
            'timestamp': trade.timestamp.isoformat(),
            'strategy': trade.strategy,
            
            # Entry conditions
            'entry_price': trade.fill_price,
            'entry_bid': trade.bid_at_entry,
            'entry_ask': trade.ask_at_entry,
            'entry_spread': trade.spread_at_entry,
            'entry_spread_percent': trade.spread_at_entry / trade.fill_price,
            
            # Market conditions at entry
            'vix': trade.vix_at_entry,
            'volume': trade.spy_volume_at_entry,
            'trend': trade.market_trend,
            
            # Greeks at entry
            'delta': trade.delta_at_entry,
            'gamma': trade.gamma_at_entry,
            'theta': trade.theta_at_entry,
            'vega': trade.vega_at_entry,
            'iv': trade.iv_at_entry,
            
            # Execution quality
            'fill_time_ms': trade.fill_time_ms,
            'slippage': trade.slippage,
            'slippage_percent': trade.slippage / trade.requested_price,
            
            # Exit conditions
            'exit_price': trade.exit_price,
            'exit_spread': trade.exit_spread,
            'held_minutes': trade.held_minutes,
            
            # Results
            'pnl': trade.pnl,
            'pnl_percent': trade.pnl_percent,
            'commission_impact': (trade.commission * 2) / abs(trade.pnl) if trade.pnl != 0 else 0,
            
            # Signal parameters (for optimization)
            'signal_strength': trade.signal.strength,
            'stop_loss': trade.signal.stop_loss,
            'take_profit': trade.signal.take_profit,
            **trade.signal.metadata  # Include all strategy-specific parameters
        }
        
        self.learning_data.append(learning_record)
        
        # Emit learning data event
        self.event_manager.emit(Event(
            EventType.SYSTEM,
            {
                'type': 'paper_trade_complete',
                'learning_data': learning_record
            }
        ))
    
    # ==========================================================================
    # SESSION MANAGEMENT
    # ==========================================================================
    def _save_session_data(self) -> None:
        """Save session data for analysis"""
        session_data = {
            'session': self.session.to_dict(),
            'completed_trades': [
                {
                    'trade_id': t.trade_id,
                    'strategy': t.strategy,
                    'entry_time': t.timestamp.isoformat(),
                    'exit_time': t.exit_time.isoformat() if t.exit_time else None,
                    'entry_price': t.fill_price,
                    'exit_price': t.exit_price,
                    'pnl': t.pnl,
                    'pnl_percent': t.pnl_percent,
                    'held_minutes': t.held_minutes,
                    'entry_spread': t.spread_at_entry,
                    'exit_spread': t.exit_spread,
                    'slippage': t.slippage,
                    'fill_time_ms': t.fill_time_ms
                }
                for t in self.completed_trades
            ],
            'learning_data': self.learning_data,
            'execution_metrics': {
                'avg_fill_time_ms': self.session.avg_fill_time_ms,
                'avg_slippage': self.session.avg_slippage,
                'rejected_orders': self.session.rejected_orders,
                'partial_fills': self.session.partial_fills
            }
        }
        
        # Save to file
        filename = f"paper_session_{self.session.session_id}.json"
        with open(filename, 'w') as f:
            json.dump(session_data, f, indent=2)
        
        self.logger.info(f"Session data saved to {filename}")
    
    def _print_session_summary(self) -> None:
        """Print paper trading session summary"""
        print("\n" + "="*80)
        print("PAPER TRADING SESSION SUMMARY")
        print("="*80)
        
        print(f"\nSession ID: {self.session.session_id}")
        print(f"Duration: {self.session.get_duration_days()} days")
        print(f"Status: {self.session.status.value}")
        
        print(f"\nTrade Statistics:")
        print(f"  Total Trades: {self.session.total_trades}")
        print(f"  Win Rate: {self.session.get_win_rate():.1%}")
        print(f"  Total P&L: ${self.session.total_pnl:.2f}")
        print(f"  Final Capital: ${self.session.current_capital:.2f}")
        
        print(f"\nExecution Quality:")
        print(f"  Avg Fill Time: {self.session.avg_fill_time_ms:.0f}ms")
        print(f"  Avg Slippage: ${self.session.avg_slippage:.3f}")
        print(f"  Rejected Orders: {self.session.rejected_orders}")
        
        if self.session.is_ready_for_live():
            print("\n✅ READY FOR LIVE TRADING")
            print("  - Minimum duration met")
            print("  - Sufficient trade count")
            print("  - Acceptable win rate")
        else:
            print("\n❌ NOT YET READY FOR LIVE TRADING")
            if self.session.get_duration_days() < MIN_PAPER_DAYS:
                print(f"  - Need {MIN_PAPER_DAYS - self.session.get_duration_days()} more days")
            if self.session.total_trades < MIN_PAPER_TRADES:
                print(f"  - Need {MIN_PAPER_TRADES - self.session.total_trades} more trades")
            if self.session.get_win_rate() < MIN_PAPER_WIN_RATE:
                print(f"  - Win rate below {MIN_PAPER_WIN_RATE:.0%}")
        
        print("="*80 + "\n")
    
    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    def _create_option_contract(self, signal: Signal) -> Contract:
        """Create option contract from signal"""
        contract = Contract()
        contract.symbol = "SPY"
        contract.secType = "OPT"
        contract.exchange = "SMART"
        contract.currency = "USD"
        
        # Parse option symbol (simplified)
        # Format: SPY_20250531_425_C
        parts = signal.symbol.split('_')
        if len(parts) >= 4:
            contract.lastTradeDateOrContractMonth = parts[1]
            contract.strike = float(parts[2])
            contract.right = parts[3]
        
        return contract
    
    def _create_order(self, signal: Signal) -> Order:
        """Create order from signal"""
        order = Order()
        order.action = signal.signal_type
        order.totalQuantity = signal.quantity
        order.orderType = signal.order_type
        
        if signal.limit_price:
            order.lmtPrice = signal.limit_price
        
        return order
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get current session statistics"""
        return self.session.to_dict()
    
    def export_learning_data(self) -> pd.DataFrame:
        """Export learning data as DataFrame"""
        if not self.learning_data:
            return pd.DataFrame()
        
        return pd.DataFrame(self.learning_data)

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    print("PaperTradingEngine module")
    print("This module manages paper trading using IB's paper account")
    print("Use this for 4-8 weeks before moving to live trading")