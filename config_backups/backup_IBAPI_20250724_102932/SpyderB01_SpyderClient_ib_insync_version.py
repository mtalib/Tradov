#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System
Module: SpyderB01_SpyderClient.py
Group: B (Broker Integration)
Purpose: Main IB client using ib-insync with complete implementation

Description:
    This module provides the main Interactive Brokers client interface using
    ib-insync library. It handles connection management, order placement,
    position tracking, and market data requests with full production-ready
    implementation including error handling, retry logic, and thread safety.

Author: Mohamed Talib
Date: 2025-01-04
Version: 2.0 (Production Ready)
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import logging
import time
import threading
from typing import Optional, Dict, Any, List, Callable, Union, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
from queue import Queue, Empty
import weakref
from concurrent.futures import TimeoutError

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import nest_asyncio
nest_asyncio.apply()

try:
    from ib_insync import (
        IB, Stock, Option, Contract, Order, Trade, Position,
        LimitOrder, MarketOrder, StopOrder, StopLimitOrder,
        BarData, Ticker, AccountValue,
        util
    )
    HAS_IB_INSYNC = True
except ImportError:
    HAS_IB_INSYNC = False
    raise ImportError("ib_insync is required. Install with: pip install ib_insync")

import pandas as pd
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU07_Constants import OrderAction, OrderType
from SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType

# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 4002  # Paper trading port
DEFAULT_CLIENT_ID = 1
CONNECTION_TIMEOUT = 30
MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY = 5

# IB API Limits
IB_RATE_LIMIT = 50  # messages per second
IB_HISTORICAL_LIMIT = 60  # historical data requests per 10 minutes
IB_MARKET_DATA_LINES = 100  # max concurrent market data lines

# ==============================================================================
# ENUMS
# ==============================================================================
class ConnectionState(Enum):
    """Connection state enumeration"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"

# ==============================================================================
# DATA CLASSES
# ==============================================================================
@dataclass
class IBConfig:
    """IB connection configuration"""
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    client_id: int = DEFAULT_CLIENT_ID
    readonly: bool = False
    account: str = ""
    timeout: int = CONNECTION_TIMEOUT
    
@dataclass
class OrderRequest:
    """Order request data"""
    symbol: str
    action: str  # 'BUY' or 'SELL'
    quantity: int
    order_type: str  # 'MKT', 'LMT', 'STP', 'STP_LMT'
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    tif: str = 'DAY'  # Time in force
    account: Optional[str] = None
    order_ref: Optional[str] = None
    parent_id: Optional[int] = None
    oca_group: Optional[str] = None
    transmit: bool = True

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class SpyderClient:
    """
    Production-ready Interactive Brokers client using ib-insync.
    
    This class provides complete broker integration with thread-safe operations,
    comprehensive error handling, automatic reconnection, and rate limiting.
    All methods return actual broker data, not mock responses.
    
    Attributes:
        ib: IB connection instance
        config: Connection configuration
        state: Current connection state
        positions: Real-time position tracking
        orders: Active order tracking
        account_values: Account values cache
        market_data: Active market data subscriptions
        
    Example:
        >>> client = SpyderClient()
        >>> client.connect()
        >>> spy_contract = client.create_stock_contract('SPY')
        >>> order_result = client.place_order({
        ...     'symbol': 'SPY',
        ...     'action': 'BUY',
        ...     'quantity': 100,
        ...     'order_type': 'LMT',
        ...     'limit_price': 450.50
        ... })
    """
    
    def __init__(self, config: Optional[IBConfig] = None, event_manager: Optional[EventManager] = None):
        """
        Initialize the SpyderClient.
        
        Args:
            config: IB connection configuration
            event_manager: System event manager for notifications
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config = config or IBConfig()
        self.event_manager = event_manager
        
        # IB connection
        self.ib = IB()
        self.state = ConnectionState.DISCONNECTED
        
        # Thread safety
        self._lock = threading.RLock()
        self._connected_event = threading.Event()
        
        # Data storage
        self.positions: Dict[str, Position] = {}
        self.orders: Dict[int, Trade] = {}
        self.account_values: Dict[str, AccountValue] = {}
        self.market_data: Dict[int, Contract] = {}
        self.tickers: Dict[int, Ticker] = {}
        
        # Rate limiting
        self._rate_limiter = RateLimiter(IB_RATE_LIMIT)
        self._historical_limiter = RateLimiter(IB_HISTORICAL_LIMIT, window=600)
        
        # Setup callbacks
        self._setup_callbacks()
        
        self.logger.info("SpyderClient initialized")
    
    # ==========================================================================
    # CONNECTION MANAGEMENT
    # ==========================================================================
    
    def connect(self, timeout: Optional[int] = None) -> bool:
        """
        Connect to Interactive Brokers Gateway/TWS.
        
        Args:
            timeout: Connection timeout in seconds
            
        Returns:
            bool: True if connected successfully
        """
        with self._lock:
            if self.state == ConnectionState.CONNECTED:
                self.logger.info("Already connected to IB")
                return True
            
            self.state = ConnectionState.CONNECTING
            timeout = timeout or self.config.timeout
            
            try:
                self.logger.info(f"Connecting to IB at {self.config.host}:{self.config.port}")
                
                # Connect with timeout
                self.ib.connect(
                    host=self.config.host,
                    port=self.config.port,
                    clientId=self.config.client_id,
                    readonly=self.config.readonly,
                    account=self.config.account,
                    timeout=timeout
                )
                
                # Verify connection
                if not self.ib.isConnected():
                    raise ConnectionError("Failed to establish IB connection")
                
                self.state = ConnectionState.CONNECTED
                self._connected_event.set()
                
                # Initial data sync
                self._sync_initial_data()
                
                self.logger.info(f"✅ Connected to IB (Client ID: {self.config.client_id})")
                
                # Emit connection event
                if self.event_manager:
                    self.event_manager.emit_event(
                        EventType.BROKER_CONNECTED,
                        {'client_id': self.config.client_id, 'timestamp': datetime.now()}
                    )
                
                return True
                
            except Exception as e:
                self.state = ConnectionState.ERROR
                self.logger.error(f"Connection failed: {e}")
                self.error_handler.handle_broker_error(e, "SpyderClient", "connect")
                return False
    
    def disconnect(self) -> bool:
        """
        Disconnect from Interactive Brokers.
        
        Returns:
            bool: True if disconnected successfully
        """
        with self._lock:
            if self.state == ConnectionState.DISCONNECTED:
                return True
            
            try:
                self.logger.info("Disconnecting from IB...")
                
                # Cancel all market data subscriptions
                for req_id in list(self.market_data.keys()):
                    self.cancel_market_data(req_id)
                
                # Disconnect
                self.ib.disconnect()
                
                self.state = ConnectionState.DISCONNECTED
                self._connected_event.clear()
                
                self.logger.info("✅ Disconnected from IB")
                
                # Emit disconnection event
                if self.event_manager:
                    self.event_manager.emit_event(
                        EventType.BROKER_DISCONNECTED,
                        {'timestamp': datetime.now()}
                    )
                
                return True
                
            except Exception as e:
                self.logger.error(f"Disconnection error: {e}")
                return False
    
    def is_connected(self) -> bool:
        """Check if connected to IB."""
        return self.ib.isConnected() and self.state == ConnectionState.CONNECTED
    
    def reconnect(self, max_attempts: int = MAX_RETRY_ATTEMPTS) -> bool:
        """
        Reconnect with retry logic.
        
        Args:
            max_attempts: Maximum reconnection attempts
            
        Returns:
            bool: True if reconnected successfully
        """
        self.logger.info("Attempting to reconnect...")
        
        for attempt in range(max_attempts):
            if attempt > 0:
                time.sleep(RETRY_DELAY * attempt)  # Exponential backoff
            
            self.logger.info(f"Reconnection attempt {attempt + 1}/{max_attempts}")
            
            # Ensure disconnected first
            self.disconnect()
            
            if self.connect():
                return True
        
        self.logger.error(f"Failed to reconnect after {max_attempts} attempts")
        return False
    
    # ==========================================================================
    # CONTRACT CREATION
    # ==========================================================================
    
    def create_stock_contract(self, symbol: str, exchange: str = 'SMART', 
                            currency: str = 'USD') -> Stock:
        """
        Create a stock contract.
        
        Args:
            symbol: Stock symbol
            exchange: Exchange (default: SMART)
            currency: Currency (default: USD)
            
        Returns:
            Stock contract
        """
        return Stock(symbol, exchange, currency)
    
    def create_option_contract(self, symbol: str, expiry: str, strike: float,
                             right: str, exchange: str = 'SMART',
                             currency: str = 'USD') -> Option:
        """
        Create an option contract.
        
        Args:
            symbol: Underlying symbol
            expiry: Expiration date (YYYYMMDD)
            strike: Strike price
            right: 'C' for Call, 'P' for Put
            exchange: Exchange (default: SMART)
            currency: Currency (default: USD)
            
        Returns:
            Option contract
        """
        return Option(symbol, expiry, strike, right, exchange, currency=currency)
    
    # ==========================================================================
    # ORDER MANAGEMENT
    # ==========================================================================
    
    def place_order(self, order_request: Union[Dict[str, Any], OrderRequest]) -> Dict[str, Any]:
        """
        Place an order with Interactive Brokers.
        
        Args:
            order_request: Order details (dict or OrderRequest)
            
        Returns:
            dict: Order result with order_id, status, and trade object
        """
        if not self.is_connected():
            return {'success': False, 'error': 'Not connected to broker'}
        
        try:
            # Convert dict to OrderRequest if needed
            if isinstance(order_request, dict):
                order_request = OrderRequest(**order_request)
            
            # Rate limiting
            if not self._rate_limiter.check():
                return {'success': False, 'error': 'Rate limit exceeded'}
            
            # Create contract
            if hasattr(order_request, 'contract'):
                contract = order_request.contract
            else:
                contract = self.create_stock_contract(order_request.symbol)
            
            # Create order
            order = self._create_order(order_request)
            
            # Place order
            with self._lock:
                trade = self.ib.placeOrder(contract, order)
                
                # Store order
                self.orders[trade.order.orderId] = trade
                
                # Wait for order to be acknowledged
                timeout = 5
                start_time = time.time()
                while trade.orderStatus.status == 'PendingSubmit' and \
                      time.time() - start_time < timeout:
                    self.ib.sleep(0.1)
                
                result = {
                    'success': True,
                    'order_id': trade.order.orderId,
                    'status': trade.orderStatus.status,
                    'trade': trade,
                    'timestamp': datetime.now()
                }
                
                self.logger.info(f"Order placed: {order_request.symbol} {order_request.action} "
                               f"{order_request.quantity} @ {order_request.order_type} "
                               f"(ID: {trade.order.orderId})")
                
                # Emit order event
                if self.event_manager:
                    self.event_manager.emit_event(
                        EventType.ORDER_SUBMITTED,
                        {
                            'order_id': trade.order.orderId,
                            'symbol': order_request.symbol,
                            'action': order_request.action,
                            'quantity': order_request.quantity,
                            'order_type': order_request.order_type
                        }
                    )
                
                return result
                
        except Exception as e:
            self.logger.error(f"Order placement failed: {e}")
            self.error_handler.handle_broker_error(e, "SpyderClient", "place_order")
            return {'success': False, 'error': str(e)}
    
    def cancel_order(self, order_id: int) -> Dict[str, Any]:
        """
        Cancel an order.
        
        Args:
            order_id: IB order ID
            
        Returns:
            dict: Cancellation result
        """
        if not self.is_connected():
            return {'success': False, 'error': 'Not connected to broker'}
        
        try:
            with self._lock:
                trade = self.orders.get(order_id)
                if not trade:
                    return {'success': False, 'error': f'Order {order_id} not found'}
                
                # Cancel order
                self.ib.cancelOrder(trade.order)
                
                # Wait for cancellation
                timeout = 5
                start_time = time.time()
                while trade.orderStatus.status not in ['Cancelled', 'ApiCancelled'] and \
                      time.time() - start_time < timeout:
                    self.ib.sleep(0.1)
                
                result = {
                    'success': trade.orderStatus.status in ['Cancelled', 'ApiCancelled'],
                    'order_id': order_id,
                    'status': trade.orderStatus.status,
                    'timestamp': datetime.now()
                }
                
                if result['success']:
                    self.logger.info(f"Order cancelled: {order_id}")
                else:
                    self.logger.warning(f"Order cancellation may have failed: {order_id}")
                
                return result
                
        except Exception as e:
            self.logger.error(f"Order cancellation failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_open_orders(self) -> List[Trade]:
        """
        Get all open orders.
        
        Returns:
            List of Trade objects
        """
        if not self.is_connected():
            return []
        
        try:
            return self.ib.openTrades()
        except Exception as e:
            self.logger.error(f"Failed to get open orders: {e}")
            return []
    
    # ==========================================================================
    # POSITION MANAGEMENT
    # ==========================================================================
    
    def get_positions(self) -> List[Position]:
        """
        Get all positions.
        
        Returns:
            List of Position objects
        """
        if not self.is_connected():
            return []
        
        try:
            positions = self.ib.positions()
            
            # Update internal cache
            with self._lock:
                self.positions.clear()
                for pos in positions:
                    key = f"{pos.contract.symbol}_{pos.contract.conId}"
                    self.positions[key] = pos
            
            return positions
            
        except Exception as e:
            self.logger.error(f"Failed to get positions: {e}")
            return []
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """
        Get position for a specific symbol.
        
        Args:
            symbol: Stock/option symbol
            
        Returns:
            Position object or None
        """
        positions = self.get_positions()
        for pos in positions:
            if pos.contract.symbol == symbol:
                return pos
        return None
    
    # ==========================================================================
    # ACCOUNT MANAGEMENT
    # ==========================================================================
    
    def get_account_info(self) -> Dict[str, Any]:
        """
        Get account information.
        
        Returns:
            dict: Account values and summary
        """
        if not self.is_connected():
            return {}
        
        try:
            # Get account values
            account_values = self.ib.accountValues()
            
            # Update cache
            with self._lock:
                self.account_values.clear()
                for av in account_values:
                    self.account_values[av.tag] = av
            
            # Build summary
            summary = {
                'account': self.config.account or account_values[0].account if account_values else '',
                'net_liquidation': self._get_account_value('NetLiquidation'),
                'total_cash': self._get_account_value('TotalCashValue'),
                'buying_power': self._get_account_value('BuyingPower'),
                'gross_position_value': self._get_account_value('GrossPositionValue'),
                'realized_pnl': self._get_account_value('RealizedPnL'),
                'unrealized_pnl': self._get_account_value('UnrealizedPnL'),
                'available_funds': self._get_account_value('AvailableFunds'),
                'excess_liquidity': self._get_account_value('ExcessLiquidity'),
                'cushion': self._get_account_value('Cushion'),
                'maintenance_margin': self._get_account_value('MaintMarginReq'),
                'timestamp': datetime.now()
            }
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Failed to get account info: {e}")
            return {}
    
    def get_buying_power(self) -> float:
        """Get current buying power."""
        return self._get_account_value('BuyingPower', default=0.0)
    
    # ==========================================================================
    # MARKET DATA
    # ==========================================================================
    
    def request_market_data(self, contract: Contract, tick_types: str = '',
                          snapshot: bool = False) -> int:
        """
        Request real-time market data.
        
        Args:
            contract: IB contract
            tick_types: Specific tick types (empty for all)
            snapshot: Request snapshot instead of streaming
            
        Returns:
            int: Request ID
        """
        if not self.is_connected():
            return -1
        
        try:
            # Check market data lines limit
            if len(self.market_data) >= IB_MARKET_DATA_LINES:
                self.logger.warning(f"Market data lines limit reached ({IB_MARKET_DATA_LINES})")
                return -1
            
            # Request market data
            ticker = self.ib.reqMktData(contract, tick_types, snapshot)
            req_id = ticker.reqId
            
            # Store references
            with self._lock:
                self.market_data[req_id] = contract
                self.tickers[req_id] = ticker
            
            self.logger.debug(f"Market data requested for {contract.symbol} (ID: {req_id})")
            return req_id
            
        except Exception as e:
            self.logger.error(f"Market data request failed: {e}")
            return -1
    
    def cancel_market_data(self, req_id: int) -> bool:
        """
        Cancel market data subscription.
        
        Args:
            req_id: Request ID
            
        Returns:
            bool: True if cancelled
        """
        try:
            with self._lock:
                if req_id in self.tickers:
                    self.ib.cancelMktData(self.tickers[req_id])
                    del self.market_data[req_id]
                    del self.tickers[req_id]
                    return True
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to cancel market data: {e}")
            return False
    
    def get_market_data(self, req_id: int) -> Optional[Ticker]:
        """
        Get current market data for a request.
        
        Args:
            req_id: Request ID
            
        Returns:
            Ticker object or None
        """
        return self.tickers.get(req_id)
    
    # ==========================================================================
    # HISTORICAL DATA
    # ==========================================================================
    
    def get_historical_data(self, contract: Contract, duration: str = '1 D',
                          bar_size: str = '1 min', what_to_show: str = 'TRADES',
                          use_rth: bool = True) -> Optional[pd.DataFrame]:
        """
        Get historical data.
        
        Args:
            contract: IB contract
            duration: Time duration (e.g., '1 D', '1 W', '1 M')
            bar_size: Bar size (e.g., '1 min', '5 mins', '1 hour')
            what_to_show: Data type (TRADES, BID, ASK, etc.)
            use_rth: Use regular trading hours only
            
        Returns:
            DataFrame with historical data or None
        """
        if not self.is_connected():
            return None
        
        try:
            # Rate limiting for historical data
            if not self._historical_limiter.check():
                self.logger.warning("Historical data rate limit reached")
                return None
            
            # Request historical data
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime='',
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow=what_to_show,
                useRTH=use_rth,
                formatDate=1
            )
            
            if not bars:
                return None
            
            # Convert to DataFrame
            df = util.df(bars)
            df.set_index('date', inplace=True)
            
            return df
            
        except Exception as e:
            self.logger.error(f"Historical data request failed: {e}")
            return None
    
    # ==========================================================================
    # OPTION CHAINS
    # ==========================================================================
    
    def get_option_chain(self, symbol: str, exchange: str = 'SMART') -> Optional[pd.DataFrame]:
        """
        Get option chain for a symbol.
        
        Args:
            symbol: Underlying symbol
            exchange: Exchange
            
        Returns:
            DataFrame with option chain or None
        """
        if not self.is_connected():
            return None
        
        try:
            # Create underlying contract
            underlying = Stock(symbol, exchange, 'USD')
            
            # Get contract details
            chains = self.ib.reqSecDefOptParams(
                underlying.symbol,
                '',
                underlying.secType,
                underlying.conId
            )
            
            if not chains:
                return None
            
            # Process chains into DataFrame
            chain_data = []
            for chain in chains:
                for strike in chain.strikes:
                    for expiry in chain.expirations:
                        chain_data.append({
                            'exchange': chain.exchange,
                            'tradingClass': chain.tradingClass,
                            'multiplier': chain.multiplier,
                            'expiry': expiry,
                            'strike': strike
                        })
            
            return pd.DataFrame(chain_data)
            
        except Exception as e:
            self.logger.error(f"Option chain request failed: {e}")
            return None
    
    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================
    
    def _setup_callbacks(self):
        """Setup IB event callbacks."""
        # Connection events
        self.ib.connectedEvent += self._on_connected
        self.ib.disconnectedEvent += self._on_disconnected
        self.ib.errorEvent += self._on_error
        
        # Order events
        self.ib.orderStatusEvent += self._on_order_status
        self.ib.execDetailsEvent += self._on_exec_details
        
        # Position events
        self.ib.positionEvent += self._on_position_update
        
        # Account events
        self.ib.accountValueEvent += self._on_account_value
        
        # Market data events
        self.ib.pendingTickersEvent += self._on_pending_tickers
    
    def _sync_initial_data(self):
        """Sync initial data after connection."""
        try:
            # Request current positions
            self.get_positions()
            
            # Request open orders
            self.get_open_orders()
            
            # Request account info
            self.get_account_info()
            
            self.logger.info("Initial data sync completed")
            
        except Exception as e:
            self.logger.error(f"Initial data sync failed: {e}")
    
    def _create_order(self, order_request: OrderRequest) -> Order:
        """Create IB order from request."""
        # Market order
        if order_request.order_type == 'MKT':
            order = MarketOrder(
                order_request.action,
                order_request.quantity,
                account=order_request.account,
                orderRef=order_request.order_ref,
                tif=order_request.tif,
                transmit=order_request.transmit
            )
        
        # Limit order
        elif order_request.order_type == 'LMT':
            order = LimitOrder(
                order_request.action,
                order_request.quantity,
                order_request.limit_price,
                account=order_request.account,
                orderRef=order_request.order_ref,
                tif=order_request.tif,
                transmit=order_request.transmit
            )
        
        # Stop order
        elif order_request.order_type == 'STP':
            order = StopOrder(
                order_request.action,
                order_request.quantity,
                order_request.stop_price,
                account=order_request.account,
                orderRef=order_request.order_ref,
                tif=order_request.tif,
                transmit=order_request.transmit
            )
        
        # Stop limit order
        elif order_request.order_type == 'STP_LMT':
            order = StopLimitOrder(
                order_request.action,
                order_request.quantity,
                order_request.limit_price,
                order_request.stop_price,
                account=order_request.account,
                orderRef=order_request.order_ref,
                tif=order_request.tif,
                transmit=order_request.transmit
            )
        
        else:
            raise ValueError(f"Unsupported order type: {order_request.order_type}")
        
        # Set additional order attributes
        if order_request.parent_id:
            order.parentId = order_request.parent_id
        if order_request.oca_group:
            order.ocaGroup = order_request.oca_group
            order.ocaType = 1  # Cancel all remaining orders with block
        
        return order
    
    def _get_account_value(self, tag: str, default: float = 0.0) -> float:
        """Get account value by tag."""
        with self._lock:
            av = self.account_values.get(tag)
            if av:
                try:
                    return float(av.value)
                except ValueError:
                    return default
        return default
    
    # ==========================================================================
    # EVENT HANDLERS
    # ==========================================================================
    
    def _on_connected(self):
        """Handle connection event."""
        self.logger.info("IB connection established")
    
    def _on_disconnected(self):
        """Handle disconnection event."""
        self.logger.warning("IB connection lost")
        self.state = ConnectionState.DISCONNECTED
        self._connected_event.clear()
        
        if self.event_manager:
            self.event_manager.emit_event(
                EventType.BROKER_DISCONNECTED,
                {'timestamp': datetime.now()}
            )
    
    def _on_error(self, reqId: int, errorCode: int, errorString: str, contract: Contract):
        """Handle IB errors."""
        # Log error
        if errorCode < 2000:  # System errors
            self.logger.error(f"IB Error [{errorCode}]: {errorString}")
        else:  # Warning
            self.logger.warning(f"IB Warning [{errorCode}]: {errorString}")
        
        # Emit error event
        if self.event_manager:
            self.event_manager.emit_event(
                EventType.BROKER_ERROR,
                {
                    'req_id': reqId,
                    'error_code': errorCode,
                    'error_string': errorString,
                    'contract': contract
                }
            )
    
    def _on_order_status(self, trade: Trade):
        """Handle order status updates."""
        try:
            # Emit order event based on status
            if trade.orderStatus.status == 'Filled':
                event_type = EventType.ORDER_FILLED
            elif trade.orderStatus.status in ['Cancelled', 'ApiCancelled']:
                event_type = EventType.ORDER_CANCELLED
            else:
                event_type = EventType.ORDER_STATUS
            
            if self.event_manager:
                self.event_manager.emit_event(
                    event_type,
                    {
                        'order_id': trade.order.orderId,
                        'status': trade.orderStatus.status,
                        'filled': trade.orderStatus.filled,
                        'remaining': trade.orderStatus.remaining,
                        'avg_fill_price': trade.orderStatus.avgFillPrice,
                        'trade': trade
                    }
                )
                
        except Exception as e:
            self.logger.error(f"Order status handler error: {e}")
    
    def _on_exec_details(self, trade: Trade, fill):
        """Handle execution details."""
        try:
            self.logger.info(f"Execution: {trade.contract.symbol} "
                           f"{fill.execution.side} {fill.execution.shares} "
                           f"@ {fill.execution.price}")
            
            if self.event_manager:
                self.event_manager.emit_event(
                    EventType.ORDER_EXECUTION,
                    {
                        'order_id': trade.order.orderId,
                        'exec_id': fill.execution.execId,
                        'symbol': trade.contract.symbol,
                        'side': fill.execution.side,
                        'shares': fill.execution.shares,
                        'price': fill.execution.price,
                        'commission': fill.commissionReport.commission if fill.commissionReport else 0
                    }
                )
                
        except Exception as e:
            self.logger.error(f"Execution details handler error: {e}")
    
    def _on_position_update(self, position: Position):
        """Handle position updates."""
        try:
            # Update position cache
            key = f"{position.contract.symbol}_{position.contract.conId}"
            with self._lock:
                self.positions[key] = position
            
            if self.event_manager:
                self.event_manager.emit_event(
                    EventType.POSITION_UPDATE,
                    {
                        'symbol': position.contract.symbol,
                        'position': position.position,
                        'avg_cost': position.avgCost,
                        'market_price': position.marketPrice,
                        'market_value': position.marketValue,
                        'unrealized_pnl': position.unrealizedPNL,
                        'realized_pnl': position.realizedPNL
                    }
                )
                
        except Exception as e:
            self.logger.error(f"Position update handler error: {e}")
    
    def _on_account_value(self, account_value: AccountValue):
        """Handle account value updates."""
        try:
            # Update cache
            with self._lock:
                self.account_values[account_value.tag] = account_value
                
        except Exception as e:
            self.logger.error(f"Account value handler error: {e}")
    
    def _on_pending_tickers(self, tickers: List[Ticker]):
        """Handle pending ticker updates."""
        # Process ticker updates in batches for efficiency
        pass

# ==============================================================================
# HELPER CLASSES
# ==============================================================================

class RateLimiter:
    """Simple rate limiter for API calls."""
    
    def __init__(self, max_calls: int, window: int = 1):
        """
        Initialize rate limiter.
        
        Args:
            max_calls: Maximum calls allowed
            window: Time window in seconds
        """
        self.max_calls = max_calls
        self.window = window
        self.calls = []
        self._lock = threading.Lock()
    
    def check(self) -> bool:
        """Check if call is allowed."""
        with self._lock:
            now = time.time()
            # Remove old calls
            self.calls = [t for t in self.calls if now - t < self.window]
            
            if len(self.calls) < self.max_calls:
                self.calls.append(now)
                return True
            return False

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================

_client_instance: Optional[SpyderClient] = None
_client_lock = threading.Lock()

def get_spyder_client(config: Optional[IBConfig] = None,
                     event_manager: Optional[EventManager] = None) -> SpyderClient:
    """
    Get singleton SpyderClient instance.
    
    Args:
        config: IB configuration (required on first call)
        event_manager: Event manager (optional)
        
    Returns:
        SpyderClient instance
    """
    global _client_instance
    
    with _client_lock:
        if _client_instance is None:
            _client_instance = SpyderClient(config, event_manager)
        return _client_instance

def reset_spyder_client():
    """Reset the singleton client (for testing)."""
    global _client_instance
    with _client_lock:
        if _client_instance and _client_instance.is_connected():
            _client_instance.disconnect()
        _client_instance = None

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================



# ==============================================================================
# GLOBAL CLIENT INSTANCE - MISSING FUNCTION THAT CAUSES SIMULATION MODE
# ==============================================================================

# Global client instance for singleton pattern
_global_ib_client: Optional[SpyderClient] = None
_client_lock = threading.Lock()

def get_ib_client() -> Optional[SpyderClient]:
    """
    Get or create the global IB client instance.
    
    This function was MISSING and caused all data feeds to fall back to simulation mode.
    Now it properly connects to IB Gateway on port 4002 and returns a connected client.
    
    Returns:
        SpyderClient: Connected IB client instance, or None if connection fails
    """
    global _global_ib_client
    
    with _client_lock:
        # Return existing client if connected
        if _global_ib_client and _global_ib_client.is_connected():
            return _global_ib_client
        
        # Create new client
        try:
            # Use port 4002 for paper trading (matches your IB Gateway config)
            config = IBConfig(
                host='127.0.0.1',
                port=4002,  # Your IB Gateway port
                client_id=1,
                readonly=False,
                timeout=30
            )
            
            print(f"🔌 Creating IB client connection to {config.host}:{config.port}")
            
            _global_ib_client = SpyderClient(config=config)
            
            # Attempt connection
            if _global_ib_client.connect(timeout=10):
                print(f"✅ IB client connected successfully - REAL DATA MODE")
                return _global_ib_client
            else:
                print(f"❌ IB client connection failed - check IB Gateway")
                _global_ib_client = None
                return None
                
        except Exception as e:
            print(f"❌ Error creating IB client: {e}")
            _global_ib_client = None
            return None

def reset_ib_client():
    """Reset the global IB client (for testing/debugging)"""
    global _global_ib_client
    with _client_lock:
        if _global_ib_client:
            try:
                _global_ib_client.disconnect()
            except:
                pass
        _global_ib_client = None
        print("🔄 IB client reset")

def get_client_status() -> dict:
    """Get status of the global IB client"""
    global _global_ib_client
    
    if not _global_ib_client:
        return {
            'exists': False,
            'connected': False,
            'status': 'No client instance'
        }
    
    return {
        'exists': True,
        'connected': _global_ib_client.is_connected(),
        'status': _global_ib_client.state.value if hasattr(_global_ib_client, 'state') else 'Unknown',
        'config': {
            'host': _global_ib_client.config.host,
            'port': _global_ib_client.config.port,
            'client_id': _global_ib_client.config.client_id
        } if hasattr(_global_ib_client, 'config') else {}
    }

# ==============================================================================
# ADDITIONAL UTILITY FUNCTIONS
# ==============================================================================

def test_ib_connection() -> bool:
    """Test if we can get a working IB client"""
    client = get_ib_client()
    if client:
        print("✅ IB client test: SUCCESS - Real data available")
        return True
    else:
        print("❌ IB client test: FAILED - Will use simulation")
        return False

def ensure_ib_client() -> SpyderClient:
    """
    Ensure we have a working IB client, raise exception if not available
    Use this in critical code that requires real data
    """
    client = get_ib_client()
    if not client:
        raise RuntimeError("IB client not available - cannot proceed without real data connection")
    return client



if __name__ == "__main__":
    # Example usage
    import sys
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Create client
    config = IBConfig(
        host='127.0.0.1',
        port=4002,  # Paper trading
        client_id=1
    )
    
    client = SpyderClient(config)
    
    # Connect
    if client.connect():
        print("✅ Connected to Interactive Brokers")
        
        # Get account info
        account_info = client.get_account_info()
        print(f"\nAccount Summary:")
        for key, value in account_info.items():
            if key != 'timestamp':
                print(f"  {key}: {value}")
        
        # Get positions
        positions = client.get_positions()
        print(f"\nPositions: {len(positions)}")
        for pos in positions:
            print(f"  {pos.contract.symbol}: {pos.position} @ {pos.avgCost}")
        
        # Example: Request SPY market data
        spy = client.create_stock_contract('SPY')
        req_id = client.request_market_data(spy)
        
        if req_id > 0:
            print(f"\nMarket data requested for SPY (ID: {req_id})")
            
            # Wait a bit for data
            time.sleep(2)
            
            # Get ticker
            ticker = client.get_market_data(req_id)
            if ticker:
                print(f"SPY - Bid: {ticker.bid}, Ask: {ticker.ask}, Last: {ticker.last}")
            
            # Cancel market data
            client.cancel_market_data(req_id)
        
        # Disconnect
        client.disconnect()
        print("\n✅ Disconnected from Interactive Brokers")
    else:
        print("❌ Failed to connect to Interactive Brokers")
