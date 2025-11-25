#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderR_Runtime
Module: SpyderR02_PaperEngine.py
Purpose: Paper trading engine with modern ib_async integration
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-21 Time: 19:30:00

⚠️ DEPRECATION WARNING ⚠️
    This module uses DEPRECATED ib_async integration.

    Current Status:
    - ❌ IBKR integration via ib_async is legacy code
    - ✅ Recommended: Use Tradier sandbox mode for paper trading
    - 🔧 See: SpyderB40_TradierClient (supports sandbox mode)

    The Spyder system has migrated to:
    - Tradier API for order execution and paper trading
    - Polygon.io for market data

    This module remains for backward compatibility only.

Module Description:
    This module provides a comprehensive paper trading engine using the modern
    ib_async library for IB Gateway 10.37 compatibility. It simulates live trading
    operations with real market data while maintaining detailed records for strategy
    testing and validation. Features include realistic order filling, commission
    simulation, and performance tracking.

Key Features:
    • Modern ib_async integration for enhanced stability
    • Realistic paper trading simulation
    • Real market data integration
    • Commission and slippage simulation
    • Comprehensive position tracking
    • Performance analytics and reporting

Dependencies:
    • ib_async (modern IB API wrapper)
    • Standard Python libraries for data processing

Installation Note:
    pip install ib_async
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import time
import threading
import datetime
from typing import Dict, List, Optional, Any, Callable, Tuple
from enum import Enum, auto
from dataclasses import dataclass, field
from collections import defaultdict, deque
import uuid
import json
import asyncio

# ==============================================================================
# THIRD-PARTY IMPORTS - Modern ib_async (DEPRECATED)
# ==============================================================================
import pandas as pd
import numpy as np

# ⚠️ DEPRECATED: ib_async is no longer used by Spyder trading system
# For paper trading, use Tradier sandbox mode via SpyderB40_TradierClient
# This import remains for backward compatibility only.
try:
    from ib_async import Contract, Order, Trade, LimitOrder, MarketOrder
    from ib_async import Stock, Option, Future, IB, Ticker
    HAS_IB_ASYNC = True
except ImportError:
    print("⚠️ ib_async not available - running in simulation mode")
    print("For paper trading, use Tradier sandbox mode instead")
    print("See: SpyderB40_TradierClient.py")
    HAS_IB_ASYNC = False

    # Fallback classes for when ib_async is not available
    class Contract:
        def __init__(self):
            self.symbol = ""
            self.secType = ""
            self.exchange = ""
            self.currency = ""

    class Order:
        def __init__(self):
            self.action = ""
            self.totalQuantity = 0
            self.orderType = ""

    class LimitOrder:
        def __init__(self, action, totalQuantity, lmtPrice):
            self.action = action
            self.totalQuantity = totalQuantity
            self.lmtPrice = lmtPrice

    class MarketOrder:
        def __init__(self, action, totalQuantity):
            self.action = action
            self.totalQuantity = totalQuantity

    class IB:
        def connect(self, *args, **kwargs): return False
        def disconnect(self): pass
        def isConnected(self): return False

    class Ticker:
        def __init__(self):
            self.last = 0.0
            self.bid = 0.0
            self.ask = 0.0

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Order defaults
DEFAULT_TIF = "DAY"
DEFAULT_OUTSIDE_RTH = False

# Order status mapping for ib_async
ORDER_STATUS_MAPPING = {
    "Submitted": "SUBMITTED",
    "Filled": "FILLED", 
    "Cancelled": "CANCELLED",
    "Inactive": "INACTIVE",
    "PendingSubmit": "PENDING",
    "PreSubmitted": "PRESUBMITTED",
    "ApiCancelled": "CANCELLED",
}

# Commission and fees (paper trading simulation)
DEFAULT_STOCK_COMMISSION = 0.005  # $0.005 per share
DEFAULT_OPTION_COMMISSION = 0.65  # $0.65 per contract
DEFAULT_SLIPPAGE_BPS = 1  # 1 basis point slippage

# Paper trading account defaults
PAPER_INITIAL_BALANCE = 100000.0  # $100K starting balance
PAPER_BUYING_POWER_MULTIPLIER = 4  # 4:1 leverage for day trading

# ==============================================================================
# ENUMS
# ==============================================================================

class OrderStatus(Enum):
    """Order status enumeration"""
    PENDING = auto()
    SUBMITTED = auto()
    FILLED = auto()
    CANCELLED = auto()
    REJECTED = auto()
    EXPIRED = auto()

class PositionType(Enum):
    """Position type enumeration"""
    LONG = auto()
    SHORT = auto()
    FLAT = auto()

class ExecutionMode(Enum):
    """Execution mode enumeration"""
    PAPER = auto()
    LIVE = auto()
    BACKTEST = auto()

# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class PaperAccount:
    """Paper trading account information"""
    account_id: str = "PAPER001"
    initial_balance: float = PAPER_INITIAL_BALANCE
    cash_balance: float = PAPER_INITIAL_BALANCE
    buying_power: float = PAPER_INITIAL_BALANCE * PAPER_BUYING_POWER_MULTIPLIER
    net_liquidation: float = PAPER_INITIAL_BALANCE
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    total_commissions: float = 0.0
    positions: Dict[str, Any] = field(default_factory=dict)
    orders: Dict[str, Any] = field(default_factory=dict)

@dataclass 
class PaperPosition:
    """Paper trading position"""
    symbol: str
    quantity: int
    avg_price: float
    market_price: float = 0.0
    unrealized_pnl: float = 0.0
    position_value: float = 0.0
    contract: Optional[Contract] = None

@dataclass
class PaperOrder:
    """Paper trading order"""
    order_id: str
    symbol: str
    action: str  # BUY/SELL
    quantity: int
    order_type: str  # MKT/LMT/STP
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: int = 0
    avg_fill_price: float = 0.0
    commission: float = 0.0
    created_time: datetime.datetime = field(default_factory=datetime.datetime.now)
    filled_time: Optional[datetime.datetime] = None

@dataclass
class PaperFill:
    """Paper trading fill/execution"""
    fill_id: str
    order_id: str
    symbol: str
    quantity: int
    price: float
    commission: float
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)

# ==============================================================================
# MAIN PAPER ENGINE CLASS
# ==============================================================================

class PaperTradingEngine:
    """
    Comprehensive paper trading engine with modern ib_async integration.
    
    This class provides a realistic paper trading environment that simulates
    live trading operations using real market data from Interactive Brokers.
    Features include realistic order fills, commission calculations, position
    tracking, and comprehensive performance analytics.
    
    Key Features:
    - Modern ib_async integration
    - Real market data simulation
    - Realistic order filling with slippage
    - Commission and fee simulation
    - Comprehensive position tracking
    - Performance metrics and reporting
    """

    def __init__(self, ib_client=None, config: Dict[str, Any] = None):
        """
        Initialize the paper trading engine.
        
        Args:
            ib_client: Optional IB client connection
            config: Configuration dictionary
        """
        # Core components
        self.ib_client = ib_client
        self.config = config or {}
        
        # Logging and error handling
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Paper trading account
        self.account = PaperAccount()
        
        # Order and position tracking
        self.orders: Dict[str, PaperOrder] = {}
        self.positions: Dict[str, PaperPosition] = {}
        self.fills: List[PaperFill] = []
        
        # Market data cache
        self.market_data: Dict[str, Ticker] = {}
        self.price_lock = threading.Lock()
        
        # Engine state
        self.is_running = False
        self.execution_mode = ExecutionMode.PAPER
        self.order_counter = 0
        self.order_lock = threading.Lock()
        
        # Performance tracking
        self.trades_executed = 0
        self.total_pnl = 0.0
        self.start_time: Optional[datetime.datetime] = None
        
        self.logger.info("PaperTradingEngine initialized with ib_async")

    # ==========================================================================
    # ENGINE LIFECYCLE
    # ==========================================================================

    def start(self) -> bool:
        """
        Start the paper trading engine.
        
        Returns:
            bool: True if started successfully
        """
        try:
            if self.is_running:
                self.logger.warning("Paper trading engine already running")
                return True
                
            self.logger.info("🚀 Starting paper trading engine...")
            
            # Initialize market data connection if available
            if self.ib_client and HAS_IB_ASYNC:
                self._setup_market_data()
            
            self.is_running = True
            self.start_time = datetime.datetime.now()
            
            self.logger.info("✅ Paper trading engine started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to start paper trading engine: {e}")
            self.error_handler.handle_error(e)
            return False

    def stop(self) -> bool:
        """
        Stop the paper trading engine.
        
        Returns:
            bool: True if stopped successfully
        """
        try:
            if not self.is_running:
                self.logger.warning("Paper trading engine not running")
                return True
                
            self.logger.info("🛑 Stopping paper trading engine...")
            
            # Cancel all pending orders
            self._cancel_all_orders()
            
            # Cleanup market data subscriptions
            if self.ib_client and HAS_IB_ASYNC:
                self._cleanup_market_data()
            
            self.is_running = False
            
            self.logger.info("✅ Paper trading engine stopped successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to stop paper trading engine: {e}")
            self.error_handler.handle_error(e)
            return False

    # ==========================================================================
    # ORDER MANAGEMENT
    # ==========================================================================

    def place_order(self, contract: Contract, order: Order) -> str:
        """
        Place a paper trading order.
        
        Args:
            contract: Contract object
            order: Order object
            
        Returns:
            str: Order ID
        """
        try:
            with self.order_lock:
                self.order_counter += 1
                order_id = f"PAPER_{self.order_counter:06d}"
            
            # Create paper order
            paper_order = PaperOrder(
                order_id=order_id,
                symbol=contract.symbol,
                action=order.action,
                quantity=order.totalQuantity,
                order_type=order.orderType,
                limit_price=getattr(order, 'lmtPrice', None),
                stop_price=getattr(order, 'auxPrice', None),
                status=OrderStatus.SUBMITTED
            )
            
            # Store order
            self.orders[order_id] = paper_order
            
            # Try to fill immediately for market orders
            if order.orderType == "MKT":
                self._attempt_fill(order_id)
            elif order.orderType == "LMT":
                self._check_limit_order(order_id)
            
            self.logger.info(f"📝 Paper order placed: {order_id} - {order.action} {order.totalQuantity} {contract.symbol}")
            return order_id
            
        except Exception as e:
            self.logger.error(f"❌ Failed to place paper order: {e}")
            self.error_handler.handle_error(e)
            return ""

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a paper trading order.
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            bool: True if cancelled successfully
        """
        try:
            if order_id not in self.orders:
                self.logger.warning(f"Order {order_id} not found")
                return False
                
            order = self.orders[order_id]
            
            if order.status in [OrderStatus.FILLED, OrderStatus.CANCELLED]:
                self.logger.warning(f"Order {order_id} already {order.status.name}")
                return False
                
            order.status = OrderStatus.CANCELLED
            
            self.logger.info(f"❌ Paper order cancelled: {order_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to cancel paper order {order_id}: {e}")
            self.error_handler.handle_error(e)
            return False

    def _attempt_fill(self, order_id: str) -> bool:
        """
        Attempt to fill a paper order.
        
        Args:
            order_id: Order ID to fill
            
        Returns:
            bool: True if filled successfully
        """
        try:
            if order_id not in self.orders:
                return False
                
            order = self.orders[order_id]
            
            if order.status != OrderStatus.SUBMITTED:
                return False
            
            # Get market price
            market_price = self._get_market_price(order.symbol, order.action)
            
            if market_price <= 0:
                self.logger.warning(f"No market price available for {order.symbol}")
                return False
            
            # Apply slippage for realism
            fill_price = self._apply_slippage(market_price, order.action)
            
            # Calculate commission
            commission = self._calculate_commission(order.symbol, order.quantity)
            
            # Fill the order
            fill_id = f"FILL_{uuid.uuid4().hex[:8]}"
            fill = PaperFill(
                fill_id=fill_id,
                order_id=order_id,
                symbol=order.symbol,
                quantity=order.quantity,
                price=fill_price,
                commission=commission
            )
            
            # Update order
            order.status = OrderStatus.FILLED
            order.filled_quantity = order.quantity
            order.avg_fill_price = fill_price
            order.commission = commission
            order.filled_time = datetime.datetime.now()
            
            # Update position
            self._update_position(order.symbol, order.action, order.quantity, fill_price)
            
            # Update account
            self._update_account(order, fill)
            
            # Store fill
            self.fills.append(fill)
            self.trades_executed += 1
            
            self.logger.info(f"✅ Paper order filled: {order_id} - {order.quantity} @ ${fill_price:.2f}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to fill paper order {order_id}: {e}")
            self.error_handler.handle_error(e)
            return False

    def _check_limit_order(self, order_id: str) -> bool:
        """
        Check if a limit order can be filled.
        
        Args:
            order_id: Order ID to check
            
        Returns:
            bool: True if limit order conditions are met
        """
        try:
            if order_id not in self.orders:
                return False
                
            order = self.orders[order_id]
            
            if order.status != OrderStatus.SUBMITTED or order.limit_price is None:
                return False
            
            market_price = self._get_market_price(order.symbol, order.action)
            
            if market_price <= 0:
                return False
            
            # Check if limit order can be filled
            can_fill = False
            if order.action == "BUY" and market_price <= order.limit_price:
                can_fill = True
            elif order.action == "SELL" and market_price >= order.limit_price:
                can_fill = True
            
            if can_fill:
                return self._attempt_fill(order_id)
                
            return False
            
        except Exception as e:
            self.logger.error(f"❌ Failed to check limit order {order_id}: {e}")
            return False

    # ==========================================================================
    # POSITION MANAGEMENT
    # ==========================================================================

    def _update_position(self, symbol: str, action: str, quantity: int, price: float):
        """Update position after trade execution."""
        try:
            if symbol not in self.positions:
                self.positions[symbol] = PaperPosition(
                    symbol=symbol,
                    quantity=0,
                    avg_price=0.0
                )
            
            position = self.positions[symbol]
            
            # Calculate new position
            if action == "BUY":
                new_quantity = position.quantity + quantity
                if new_quantity != 0:
                    new_avg_price = ((position.quantity * position.avg_price) + 
                                   (quantity * price)) / new_quantity
                else:
                    new_avg_price = price
            else:  # SELL
                new_quantity = position.quantity - quantity
                if new_quantity == 0:
                    new_avg_price = 0.0
                else:
                    new_avg_price = position.avg_price  # Keep existing average
            
            position.quantity = new_quantity
            position.avg_price = new_avg_price
            
            # Update market value
            market_price = self._get_market_price(symbol, "MID")
            if market_price > 0:
                position.market_price = market_price
                position.position_value = position.quantity * market_price
                position.unrealized_pnl = (market_price - position.avg_price) * position.quantity
            
            self.logger.debug(f"📊 Position updated: {symbol} - {position.quantity} @ ${position.avg_price:.2f}")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to update position for {symbol}: {e}")

    def get_positions(self) -> Dict[str, PaperPosition]:
        """Get current positions."""
        return self.positions.copy()

    def get_position(self, symbol: str) -> Optional[PaperPosition]:
        """Get position for specific symbol."""
        return self.positions.get(symbol)

    # ==========================================================================
    # ACCOUNT MANAGEMENT
    # ==========================================================================

    def _update_account(self, order: PaperOrder, fill: PaperFill):
        """Update account after trade execution."""
        try:
            # Update cash balance
            if order.action == "BUY":
                cash_impact = -(fill.quantity * fill.price + fill.commission)
            else:  # SELL
                cash_impact = (fill.quantity * fill.price - fill.commission)
            
            self.account.cash_balance += cash_impact
            self.account.total_commissions += fill.commission
            
            # Calculate realized P&L for closing trades
            if order.action == "SELL" and order.symbol in self.positions:
                position = self.positions[order.symbol]
                if position.quantity > 0:  # Closing long position
                    realized_pnl = (fill.price - position.avg_price) * min(fill.quantity, position.quantity)
                    self.account.realized_pnl += realized_pnl
            
            # Update net liquidation value
            self._update_net_liquidation()
            
            self.logger.debug(f"💰 Account updated: Cash=${self.account.cash_balance:.2f}, NetLiq=${self.account.net_liquidation:.2f}")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to update account: {e}")

    def _update_net_liquidation(self):
        """Update net liquidation value."""
        try:
            # Start with cash
            net_liq = self.account.cash_balance
            
            # Add position values
            for position in self.positions.values():
                if position.quantity != 0:
                    market_price = self._get_market_price(position.symbol, "MID")
                    if market_price > 0:
                        net_liq += position.quantity * market_price
            
            self.account.net_liquidation = net_liq
            
            # Update unrealized P&L
            self.account.unrealized_pnl = sum(pos.unrealized_pnl for pos in self.positions.values())
            
        except Exception as e:
            self.logger.error(f"❌ Failed to update net liquidation: {e}")

    def get_account_info(self) -> PaperAccount:
        """Get current account information."""
        self._update_net_liquidation()
        return self.account

    # ==========================================================================
    # MARKET DATA MANAGEMENT
    # ==========================================================================

    def _setup_market_data(self):
        """Setup market data subscriptions."""
        try:
            if not self.ib_client or not HAS_IB_ASYNC:
                return
                
            # Setup event handlers for market data
            self.ib_client.pendingTickersEvent += self._on_ticker_update
            
            self.logger.info("📡 Market data setup complete")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to setup market data: {e}")

    def _cleanup_market_data(self):
        """Cleanup market data subscriptions."""
        try:
            if not self.ib_client or not HAS_IB_ASYNC:
                return
                
            # Remove event handlers
            self.ib_client.pendingTickersEvent -= self._on_ticker_update
            
            self.logger.info("📡 Market data cleanup complete")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to cleanup market data: {e}")

    def _on_ticker_update(self, tickers):
        """Handle ticker updates."""
        try:
            with self.price_lock:
                for ticker in tickers:
                    if ticker.contract and ticker.contract.symbol:
                        self.market_data[ticker.contract.symbol] = ticker
                        
                        # Update position market values
                        if ticker.contract.symbol in self.positions:
                            position = self.positions[ticker.contract.symbol]
                            if ticker.last and not np.isnan(ticker.last):
                                position.market_price = ticker.last
                                position.position_value = position.quantity * ticker.last
                                position.unrealized_pnl = (ticker.last - position.avg_price) * position.quantity
            
        except Exception as e:
            self.logger.error(f"❌ Error processing ticker update: {e}")

    def _get_market_price(self, symbol: str, side: str = "MID") -> float:
        """
        Get market price for symbol.
        
        Args:
            symbol: Symbol to get price for
            side: BUY/SELL/MID
            
        Returns:
            float: Market price or 0.0 if not available
        """
        try:
            with self.price_lock:
                if symbol not in self.market_data:
                    # Mock price if no real data available
                    return 400.0 if symbol == "SPY" else 100.0
                
                ticker = self.market_data[symbol]
                
                if side == "BUY":
                    return ticker.ask if ticker.ask and not np.isnan(ticker.ask) else ticker.last
                elif side == "SELL":
                    return ticker.bid if ticker.bid and not np.isnan(ticker.bid) else ticker.last
                else:  # MID
                    if ticker.bid and ticker.ask and not np.isnan(ticker.bid) and not np.isnan(ticker.ask):
                        return (ticker.bid + ticker.ask) / 2
                    else:
                        return ticker.last if ticker.last and not np.isnan(ticker.last) else 0.0
                        
        except Exception as e:
            self.logger.error(f"❌ Failed to get market price for {symbol}: {e}")
            return 0.0

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================

    def _apply_slippage(self, price: float, action: str) -> float:
        """Apply realistic slippage to order fills."""
        try:
            slippage_factor = DEFAULT_SLIPPAGE_BPS / 10000.0  # Convert basis points
            
            if action == "BUY":
                return price * (1 + slippage_factor)  # Pay slightly more
            else:  # SELL
                return price * (1 - slippage_factor)  # Receive slightly less
                
        except Exception as e:
            self.logger.error(f"❌ Failed to apply slippage: {e}")
            return price

    def _calculate_commission(self, symbol: str, quantity: int) -> float:
        """Calculate commission for trade."""
        try:
            # Simple commission structure
            if any(opt in symbol for opt in ['SPY', 'QQQ', 'IWM']):  # Assume options
                return quantity * DEFAULT_OPTION_COMMISSION
            else:  # Stocks
                return quantity * DEFAULT_STOCK_COMMISSION
                
        except Exception as e:
            self.logger.error(f"❌ Failed to calculate commission: {e}")
            return 0.0

    def _cancel_all_orders(self):
        """Cancel all pending orders."""
        try:
            pending_orders = [oid for oid, order in self.orders.items() 
                            if order.status == OrderStatus.SUBMITTED]
            
            for order_id in pending_orders:
                self.cancel_order(order_id)
                
            self.logger.info(f"❌ Cancelled {len(pending_orders)} pending orders")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to cancel all orders: {e}")

    # ==========================================================================
    # REPORTING AND ANALYTICS
    # ==========================================================================

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        try:
            self._update_net_liquidation()
            
            total_return = self.account.net_liquidation - self.account.initial_balance
            return_pct = (total_return / self.account.initial_balance) * 100
            
            runtime = (datetime.datetime.now() - self.start_time).total_seconds() / 3600 if self.start_time else 0
            
            return {
                'initial_balance': self.account.initial_balance,
                'current_balance': self.account.net_liquidation,
                'total_return': total_return,
                'return_percentage': return_pct,
                'realized_pnl': self.account.realized_pnl,
                'unrealized_pnl': self.account.unrealized_pnl,
                'total_commissions': self.account.total_commissions,
                'trades_executed': self.trades_executed,
                'runtime_hours': runtime,
                'positions_count': len([p for p in self.positions.values() if p.quantity != 0])
            }
            
        except Exception as e:
            self.logger.error(f"❌ Failed to generate performance summary: {e}")
            return {}

    def get_open_orders(self) -> Dict[str, PaperOrder]:
        """Get open orders."""
        return {oid: order for oid, order in self.orders.items() 
                if order.status == OrderStatus.SUBMITTED}

    def get_order_history(self) -> Dict[str, PaperOrder]:
        """Get order history."""
        return self.orders.copy()

    def get_fill_history(self) -> List[PaperFill]:
        """Get fill history."""
        return self.fills.copy()

    # ==========================================================================
    # STATUS AND DIAGNOSTICS
    # ==========================================================================

    def get_status(self) -> Dict[str, Any]:
        """Get engine status."""
        return {
            'running': self.is_running,
            'mode': self.execution_mode.name,
            'library': 'ib_async (modern)',
            'has_ib_connection': self.ib_client is not None and HAS_IB_ASYNC,
            'orders_count': len(self.orders),
            'positions_count': len([p for p in self.positions.values() if p.quantity != 0]),
            'trades_executed': self.trades_executed,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'market_data_symbols': len(self.market_data)
        }

    def is_market_hours(self) -> bool:
        """Check if currently in market hours."""
        try:
            now = datetime.datetime.now()
            market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
            market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
            
            return (now.weekday() < 5 and  # Monday-Friday
                   market_open <= now <= market_close)
                   
        except Exception as e:
            self.logger.error(f"❌ Failed to check market hours: {e}")
            return False


# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================

def create_paper_engine(ib_client=None, config: Dict[str, Any] = None) -> PaperTradingEngine:
    """
    Create paper trading engine with default configuration.
    
    Args:
        ib_client: Optional IB client connection
        config: Configuration dictionary
        
    Returns:
        PaperTradingEngine instance
    """
    return PaperTradingEngine(ib_client=ib_client, config=config)

def get_paper_engine() -> PaperTradingEngine:
    """Get paper trading engine with default configuration."""
    return create_paper_engine()

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    # Example usage and testing
    import sys
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    logger.info("PaperTradingEngine - Enhanced with ib_async")
    logger.info("=" * 50)
    
    try:
        # Create paper engine
        engine = get_paper_engine()
        
        # Start engine
        if engine.start():
            logger.info("✅ Paper engine started successfully")
            
            # Show status
            status = engine.get_status()
            logger.info(f"📊 Status: {status}")
            
            # Test contract creation and order placement
            if HAS_IB_ASYNC:
                spy_contract = Stock('SPY', 'SMART', 'USD')
                market_order = MarketOrder('BUY', 100)
                
                order_id = engine.place_order(spy_contract, market_order)
                logger.info(f"📝 Test order placed: {order_id}")
            
            # Show account info
            account = engine.get_account_info()
            logger.info(f"💰 Account: ${account.net_liquidation:,.2f}")
            
            # Show performance
            performance = engine.get_performance_summary()
            logger.info(f"📈 Performance: {performance}")
            
            # Stop engine
            engine.stop()
            logger.info("✅ Paper engine stopped successfully")
            
        else:
            logger.error("❌ Failed to start paper engine")
            
    except Exception as e:
        logger.error(f"Error in main: {e}")
        
    logger.info(f"\n🎉 PaperTradingEngine ready with ib_async!")
    logger.info(f"Library available: {HAS_IB_ASYNC}")
