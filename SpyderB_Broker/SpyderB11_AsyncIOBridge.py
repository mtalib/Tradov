#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System
Module: SpyderB11_AsyncIOBridge.py
Group: B (Broker Integration)
Purpose: AsyncIO Bridge for ib_insync + PyQt6 Integration

Description:
This module implements the definitive solution for concurrent event loops as described
in the attached document. It creates a dedicated asyncio event loop running in a QThread
to handle all ib_insync operations while maintaining thread-safe communication with the
PyQt6 GUI through signals and slots.

This solves the fundamental conflict between PyQt6's QApplication.exec() and
asyncio's loop.run_forever() by running them in separate threads with proper
signal-slot communication.

Integration with SpyderB10_IBDataTypes:
This module leverages the standardized data types from SpyderB10 for consistent
contract and order handling throughout the SPYDER system.

Author: Mohamed Talib
Created: 2025-06-22
Version: 1.0
"""

# =============================================================================
# Standard Library Imports
# =============================================================================
import asyncio
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Union
import uuid
import traceback
from dataclasses import dataclass
from enum import Enum

# =============================================================================
# Third-Party Imports
# =============================================================================
from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot, QTimer
from ib_insync import IB, Stock, Option, Future, Contract, Order, Trade, Ticker, util
from ib_insync import LimitOrder, MarketOrder, StopOrder
import nest_asyncio
import pandas as pd

# =============================================================================
# Local Application Imports
# =============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler, TradingError

# Import standardized data types from SpyderB10
from SpyderB_Broker.SpyderB10_IBDataTypes import (
    # Data structures
    IBContract, IBOrder, IBPosition, IBMarketData, IBTrade,
    
    # Enums
    SecurityType, OrderAction, OrderType, OrderStatus,
    
    # Type aliases
    ContractId, OrderId, TickerId,
    
    # Utility functions
    create_stock_contract, create_option_contract,
    create_market_order, create_limit_order,
    get_data_type_manager
)

# =============================================================================
# Constants
# =============================================================================
DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 4002  # Paper trading port
DEFAULT_CLIENT_ID = 1
CONNECTION_TIMEOUT = 30  # seconds
HEARTBEAT_INTERVAL = 30  # seconds
RECONNECT_DELAY = 5  # seconds
MAX_RECONNECT_ATTEMPTS = 10

# Apply nest_asyncio for compatibility with existing event loops
nest_asyncio.apply()

# =============================================================================
# Enums and Data Classes
# =============================================================================
class ConnectionState(Enum):
    """Connection state enumeration for AsyncIO Bridge."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"

@dataclass
class MarketDataRequest:
    """Market data subscription request using SPYDER data types."""
    request_id: str
    contract: IBContract  # Using SpyderB10 data type
    tick_types: str
    snapshot: bool
    regulatory_snapshot: bool

@dataclass
class OrderRequest:
    """Order placement request using SPYDER data types."""
    request_id: str
    contract: IBContract  # Using SpyderB10 data type
    order: IBOrder  # Using SpyderB10 data type
    callback: Optional[Callable] = None

@dataclass
class ContractRequest:
    """Contract details request."""
    request_id: str
    contract: IBContract  # Using SpyderB10 data type

# =============================================================================
# AsyncIO Bridge Implementation
# =============================================================================
class AsyncIOBridge(QObject):
    """
    Bridge between PyQt6 and asyncio for ib_insync integration.
    
    This class solves the fundamental event loop conflict by:
    1. Running asyncio in a dedicated thread
    2. Providing thread-safe communication via Qt signals
    3. Managing the asyncio event loop lifecycle
    4. Handling reconnection and error recovery
    5. Using standardized SPYDER data types from SpyderB10
    """
    
    # ==========================================================================
    # Qt Signals for Thread-Safe Communication
    # ==========================================================================
    connection_status_changed = pyqtSignal(str, str)  # state, message
    market_data_received = pyqtSignal(dict)  # market data
    order_status_updated = pyqtSignal(dict)  # order updates
    position_updated = pyqtSignal(dict)  # position changes
    account_data_updated = pyqtSignal(dict)  # account information
    error_occurred = pyqtSignal(int, str, str)  # error_code, message, context
    trade_executed = pyqtSignal(dict)  # trade execution details
    ticker_updated = pyqtSignal(dict)  # real-time ticker updates
    news_received = pyqtSignal(dict)  # news updates
    contract_details_received = pyqtSignal(str, list)  # request_id, details
    
    # Internal signals for async operations
    _async_request = pyqtSignal(str, object)  # operation_type, data
    
    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT, client_id=DEFAULT_CLIENT_ID):
        """
        Initialize the AsyncIO Bridge.
        
        Args:
            host: IB Gateway host address
            port: IB Gateway port number
            client_id: Unique client identifier
        """
        super().__init__()
        
        # Connection parameters
        self.host = host
        self.port = port
        self.client_id = client_id
        
        # State management
        self.connection_state = ConnectionState.DISCONNECTED
        self.is_running = False
        self.reconnect_count = 0
        
        # Asyncio components
        self.loop = None
        self.ib = None
        self.event_loop_thread = None
        
        # Threading synchronization
        self.connection_ready = threading.Event()
        self.shutdown_event = threading.Event()
        
        # Request tracking
        self.pending_requests: Dict[str, Any] = {}
        self.active_subscriptions: Dict[str, Ticker] = {}
        self.active_orders: Dict[int, Trade] = {}
        
        # Data type manager for validation
        self.data_manager = get_data_type_manager()
        
        # Utilities
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Connect internal signals
        self._async_request.connect(self._handle_async_request)
        
        self.logger.info(f"AsyncIOBridge initialized: {host}:{port} (Client {client_id})")
    
    # ==========================================================================
    # Public Interface Methods - Using SPYDER Data Types
    # ==========================================================================
    def start_async_worker(self) -> bool:
        """
        Start the asyncio event loop in a separate thread.
        
        Returns:
            bool: True if worker started successfully
        """
        if self.is_running:
            self.logger.warning("AsyncIO worker already running")
            return True
            
        try:
            self.is_running = True
            self.shutdown_event.clear()
            
            # Create and start the asyncio thread
            self.event_loop_thread = threading.Thread(
                target=self._run_asyncio_loop,
                name="SPYDER-AsyncIO-Bridge",
                daemon=True
            )
            self.event_loop_thread.start()
            
            self.logger.info("🚀 AsyncIO worker thread started")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start AsyncIO worker: {e}")
            self.error_handler.handle_error(e, context="AsyncIO Worker Startup")
            return False
    
    def stop_async_worker(self) -> None:
        """Stop the asyncio worker thread gracefully."""
        if not self.is_running:
            return
            
        self.logger.info("🛑 Stopping AsyncIO worker...")
        self.is_running = False
        self.shutdown_event.set()
        
        # Schedule shutdown in asyncio thread
        if self.loop and not self.loop.is_closed():
            try:
                # Use call_soon_threadsafe to schedule shutdown
                self.loop.call_soon_threadsafe(self._schedule_shutdown)
            except Exception as e:
                self.logger.error(f"Error scheduling shutdown: {e}")
        
        # Wait for thread to finish
        if self.event_loop_thread and self.event_loop_thread.is_alive():
            self.event_loop_thread.join(timeout=10)
            
        self.logger.info("✅ AsyncIO worker stopped")
    
    def request_market_data_for_stock(self, symbol: str, exchange: str = 'ARCA') -> str:
        """
        Request market data for a stock using SPYDER data types.
        
        Args:
            symbol: Stock symbol (e.g., 'SPY')
            exchange: Exchange (default: 'ARCA')
            
        Returns:
            str: Request ID for tracking
        """
        try:
            # Create standardized SPYDER contract
            spyder_contract = create_stock_contract(symbol, exchange)
            
            # Validate contract
            if not self.data_manager.validate_contract(spyder_contract):
                raise TradingError(f"Invalid contract for {symbol}")
            
            return self.request_market_data(spyder_contract)
            
        except Exception as e:
            self.logger.error(f"Error requesting stock data for {symbol}: {e}")
            self.error_handler.handle_error(e, context=f"Stock Data Request: {symbol}")
            return ""
    
    def request_market_data_for_option(self, symbol: str, expiry: str, strike: float, 
                                     right: str, exchange: str = 'SMART') -> str:
        """
        Request market data for an option using SPYDER data types.
        
        Args:
            symbol: Underlying symbol (e.g., 'SPY')
            expiry: Expiration date (YYYYMMDD format)
            strike: Strike price
            right: 'C' for Call, 'P' for Put
            exchange: Exchange (default: 'SMART')
            
        Returns:
            str: Request ID for tracking
        """
        try:
            # Create standardized SPYDER option contract
            spyder_contract = create_option_contract(symbol, expiry, strike, right, exchange)
            
            # Validate contract
            if not self.data_manager.validate_contract(spyder_contract):
                raise TradingError(f"Invalid option contract: {symbol} {expiry} {right}{strike}")
            
            return self.request_market_data(spyder_contract)
            
        except Exception as e:
            self.logger.error(f"Error requesting option data: {symbol} {expiry} {right}{strike}: {e}")
            self.error_handler.handle_error(e, context="Option Data Request")
            return ""
    
    def request_market_data(self, spyder_contract: IBContract, tick_types: str = '', 
                          snapshot: bool = False, regulatory_snapshot: bool = False) -> str:
        """
        Request market data for a SPYDER contract (thread-safe).
        
        Args:
            spyder_contract: SPYDER IBContract from SpyderB10
            tick_types: Specific tick types to request
            snapshot: Whether to request a snapshot
            regulatory_snapshot: Whether to request regulatory snapshot
            
        Returns:
            str: Request ID for tracking
        """
        try:
            # Validate the SPYDER contract
            if not self.data_manager.validate_contract(spyder_contract):
                raise TradingError("Invalid SPYDER contract provided")
            
            request_id = str(uuid.uuid4())
            
            request = MarketDataRequest(
                request_id=request_id,
                contract=spyder_contract,
                tick_types=tick_types,
                snapshot=snapshot,
                regulatory_snapshot=regulatory_snapshot
            )
            
            self._async_request.emit('market_data', request)
            self.logger.debug(f"Market data requested: {spyder_contract.symbol} ({request_id})")
            
            return request_id
            
        except Exception as e:
            self.logger.error(f"Error in market data request: {e}")
            self.error_handler.handle_error(e, context="Market Data Request")
            return ""
    
    def place_market_order(self, spyder_contract: IBContract, action: OrderAction, 
                          quantity: int, callback: Optional[Callable] = None) -> str:
        """
        Place a market order using SPYDER data types.
        
        Args:
            spyder_contract: SPYDER IBContract from SpyderB10
            action: BUY or SELL from SpyderB10
            quantity: Number of shares/contracts
            callback: Optional callback for order updates
            
        Returns:
            str: Request ID for tracking
        """
        try:
            # Create SPYDER market order
            spyder_order = create_market_order(action, quantity)
            
            # Validate order
            if not self.data_manager.validate_order(spyder_order):
                raise TradingError("Invalid market order")
            
            return self.place_order(spyder_contract, spyder_order, callback)
            
        except Exception as e:
            self.logger.error(f"Error placing market order: {e}")
            self.error_handler.handle_error(e, context="Market Order")
            return ""
    
    def place_limit_order(self, spyder_contract: IBContract, action: OrderAction, 
                         quantity: int, limit_price: float, 
                         callback: Optional[Callable] = None) -> str:
        """
        Place a limit order using SPYDER data types.
        
        Args:
            spyder_contract: SPYDER IBContract from SpyderB10
            action: BUY or SELL from SpyderB10
            quantity: Number of shares/contracts
            limit_price: Limit price
            callback: Optional callback for order updates
            
        Returns:
            str: Request ID for tracking
        """
        try:
            # Create SPYDER limit order
            spyder_order = create_limit_order(action, quantity, limit_price)
            
            # Validate order
            if not self.data_manager.validate_order(spyder_order):
                raise TradingError("Invalid limit order")
            
            return self.place_order(spyder_contract, spyder_order, callback)
            
        except Exception as e:
            self.logger.error(f"Error placing limit order: {e}")
            self.error_handler.handle_error(e, context="Limit Order")
            return ""
    
    def place_order(self, spyder_contract: IBContract, spyder_order: IBOrder, 
                   callback: Optional[Callable] = None) -> str:
        """
        Place an order using SPYDER data types (thread-safe).
        
        Args:
            spyder_contract: SPYDER IBContract from SpyderB10
            spyder_order: SPYDER IBOrder from SpyderB10
            callback: Optional callback for order updates
            
        Returns:
            str: Request ID for tracking
        """
        try:
            # Validate inputs
            if not self.data_manager.validate_contract(spyder_contract):
                raise TradingError("Invalid SPYDER contract for order")
            
            if not self.data_manager.validate_order(spyder_order):
                raise TradingError("Invalid SPYDER order")
            
            request_id = str(uuid.uuid4())
            
            order_request = OrderRequest(
                request_id=request_id,
                contract=spyder_contract,
                order=spyder_order,
                callback=callback
            )
            
            self._async_request.emit('place_order', order_request)
            self.logger.info(f"Order placement requested: {spyder_contract.symbol} "
                           f"{spyder_order.action.value} {spyder_order.total_quantity} ({request_id})")
            
            return request_id
            
        except Exception as e:
            self.logger.error(f"Error in order placement: {e}")
            self.error_handler.handle_error(e, context="Order Placement")
            return ""
    
    def request_contract_details(self, spyder_contract: IBContract) -> str:
        """
        Request contract details using SPYDER data types (thread-safe).
        
        Args:
            spyder_contract: SPYDER IBContract to get details for
            
        Returns:
            str: Request ID for tracking
        """
        try:
            if not self.data_manager.validate_contract(spyder_contract):
                raise TradingError("Invalid SPYDER contract for details request")
            
            request_id = str(uuid.uuid4())
            
            contract_request = ContractRequest(
                request_id=request_id,
                contract=spyder_contract
            )
            
            self._async_request.emit('contract_details', contract_request)
            return request_id
            
        except Exception as e:
            self.logger.error(f"Error requesting contract details: {e}")
            self.error_handler.handle_error(e, context="Contract Details")
            return ""
    
    def cancel_market_data(self, request_id: str) -> None:
        """Cancel market data subscription (thread-safe)."""
        self._async_request.emit('cancel_market_data', {'request_id': request_id})
    
    def get_connection_state(self) -> ConnectionState:
        """Get current connection state."""
        return self.connection_state
    
    def is_connected(self) -> bool:
        """Check if connected to IB Gateway."""
        return self.connection_state == ConnectionState.CONNECTED and self.ib and self.ib.isConnected()
    
    # ==========================================================================
    # Private AsyncIO Event Loop Management
    # ==========================================================================
    def _run_asyncio_loop(self) -> None:
        """Run the asyncio event loop in the dedicated thread."""
        try:
            # Create new event loop for this thread
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            # Initialize ib_insync client
            self.ib = IB()
            self._setup_ib_callbacks()
            
            # Run the main async logic
            self.loop.run_until_complete(self._async_main())
            
        except Exception as e:
            self.logger.error(f"AsyncIO loop error: {e}")
            self.logger.error(traceback.format_exc())
            self.error_occurred.emit(-1, str(e), "AsyncIO Loop")
        finally:
            self._cleanup_asyncio()
    
    async def _async_main(self) -> None:
        """Main async logic - connects and maintains the session."""
        try:
            # Connect to IB Gateway
            if await self._connect_with_retry():
                # Start continuous operations
                await asyncio.gather(
                    self._heartbeat_monitor(),
                    self._connection_monitor(),
                    self._data_processor(),
                    return_exceptions=True
                )
            
        except asyncio.CancelledError:
            self.logger.info("AsyncIO main task cancelled")
        except Exception as e:
            self.logger.error(f"Async main error: {e}")
            self.error_occurred.emit(-1, str(e), "Async Main")
    
    async def _connect_with_retry(self, max_retries: int = MAX_RECONNECT_ATTEMPTS) -> bool:
        """Connect to IB with exponential backoff retry."""
        self.reconnect_count = 0
        
        for attempt in range(max_retries):
            if self.shutdown_event.is_set():
                return False
                
            try:
                self._update_connection_state(ConnectionState.CONNECTING, 
                    f"Connecting to IB Gateway... (attempt {attempt + 1})")
                
                await self.ib.connectAsync(self.host, self.port, clientId=self.client_id)
                
                if self.ib.isConnected():
                    self._update_connection_state(ConnectionState.CONNECTED, 
                        "✅ Connected to IB Gateway")
                    self.connection_ready.set()
                    self.reconnect_count = 0
                    return True
                    
            except Exception as e:
                wait_time = min(2 ** attempt, 60)  # Exponential backoff, max 60s
                self.logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
                
                if attempt < max_retries - 1:
                    self._update_connection_state(ConnectionState.RECONNECTING, 
                        f"Retrying in {wait_time}s... ({attempt + 1}/{max_retries})")
                    await asyncio.sleep(wait_time)
                    
        self._update_connection_state(ConnectionState.ERROR, 
            "❌ Failed to connect after all retries")
        return False
    
    def _setup_ib_callbacks(self) -> None:
        """Setup ib_insync event callbacks with correct event names."""
        # Use the correct event names for ib_insync v0.9.86+
        self.ib.errorEvent += self._on_ib_error
        
        # Check if events exist before subscribing (defensive programming)
        if hasattr(self.ib, 'orderStatusEvent'):
            self.ib.orderStatusEvent += self._on_order_status
        else:
            self.logger.warning("orderStatusEvent not available in this ib_insync version")
            
        if hasattr(self.ib, 'positionEvent'):
            self.ib.positionEvent += self._on_position_update
        else:
            self.logger.warning("positionEvent not available in this ib_insync version")
            
        if hasattr(self.ib, 'accountValueEvent'):
            self.ib.accountValueEvent += self._on_account_update
        else:
            self.logger.warning("accountValueEvent not available in this ib_insync version")
            
        # The correct event for ticker updates in ib_insync is 'updateEvent' on individual tickers
        # We'll handle this when we subscribe to market data, not globally
        
        if hasattr(self.ib, 'execDetailsEvent'):
            self.ib.execDetailsEvent += self._on_execution
        else:
            self.logger.warning("execDetailsEvent not available in this ib_insync version")
            
        if hasattr(self.ib, 'disconnectedEvent'):
            self.ib.disconnectedEvent += self._on_disconnected
        else:
            self.logger.warning("disconnectedEvent not available in this ib_insync version")
            
        if hasattr(self.ib, 'contractDetailsEvent'):
            self.ib.contractDetailsEvent += self._on_contract_details
        else:
            self.logger.warning("contractDetailsEvent not available in this ib_insync version")
        
        # News events are optional
        if hasattr(self.ib, 'newsEvent'):
            self.ib.newsEvent += self._on_news_update
            
        self.logger.info("✅ IB event callbacks configured")
    
    # ==========================================================================
    # Event Handlers (Running in AsyncIO Thread)
    # ==========================================================================
    def _on_ib_error(self, reqId, errorCode, errorString, contract=None) -> None:
        """Handle IB errors - thread-safe emission to GUI."""
        try:
            context = f"ReqId: {reqId}"
            if contract:
                context += f", Contract: {contract.symbol}"
                
            # Check for critical errors
            if errorCode == 1100:  # Connection lost
                self.logger.critical("🔴 IB Connection lost")
                self._update_connection_state(ConnectionState.DISCONNECTED, "Connection lost")
                asyncio.create_task(self._handle_disconnection())
            elif errorCode in [2104, 2106, 2158]:  # Info messages
                self.logger.info(f"IB Info: {errorString}")
                return  # Don't emit info messages as errors
            else:
                self.logger.error(f"IB Error {errorCode}: {errorString}")
                
            self.error_occurred.emit(errorCode, errorString, context)
            
        except Exception as e:
            self.logger.error(f"Error handling IB error: {e}")
    
    def _on_ticker_update(self, ticker: Ticker) -> None:
        """Handle market data updates."""
        try:
            if not ticker.contract:
                return
                
            data = {
                'symbol': ticker.contract.symbol,
                'sec_type': ticker.contract.secType,
                'bid': ticker.bid if ticker.bid and ticker.bid != -1 else None,
                'ask': ticker.ask if ticker.ask and ticker.ask != -1 else None,
                'last': ticker.last if ticker.last and ticker.last != -1 else None,
                'volume': ticker.volume if ticker.volume and ticker.volume != -1 else None,
                'close': ticker.close if ticker.close and ticker.close != -1 else None,
                'timestamp': util.formatIBDatetime(ticker.time) if ticker.time else datetime.now().isoformat(),
                'request_id': getattr(ticker, '_request_id', None)
            }
            
            # Add option-specific data if available
            if ticker.contract.secType == 'OPT':
                if hasattr(ticker, 'modelGreeks') and ticker.modelGreeks:
                    data['greeks'] = {
                        'delta': ticker.modelGreeks.delta,
                        'gamma': ticker.modelGreeks.gamma,
                        'theta': ticker.modelGreeks.theta,
                        'vega': ticker.modelGreeks.vega,
                        'implied_vol': ticker.modelGreeks.impliedVol
                    }
                    
                # Add option-specific price data
                if hasattr(ticker, 'impliedVolatility') and ticker.impliedVolatility:
                    data['implied_volatility'] = ticker.impliedVolatility
                    
                if hasattr(ticker, 'optPrice') and ticker.optPrice:
                    data['option_price'] = ticker.optPrice
            
            self.ticker_updated.emit(data)
            
        except Exception as e:
            self.logger.error(f"Error processing ticker update: {e}")
    
    def _on_order_status(self, trade: Trade) -> None:
        """Handle order status updates."""
        try:
            order_data = {
                'order_id': trade.order.orderId,
                'client_id': trade.order.clientId,
                'perm_id': trade.order.permId,
                'status': trade.orderStatus.status,
                'filled': trade.orderStatus.filled,
                'remaining': trade.orderStatus.remaining,
                'avg_fill_price': trade.orderStatus.avgFillPrice,
                'last_fill_price': trade.orderStatus.lastFillPrice,
                'why_held': trade.orderStatus.whyHeld,
                'symbol': trade.contract.symbol if trade.contract else 'Unknown',
                'action': getattr(trade.order, 'action', 'Unknown'),
                'order_type': getattr(trade.order, 'orderType', 'Unknown'),
                'total_quantity': getattr(trade.order, 'totalQuantity', 0),
                'timestamp': datetime.now().isoformat()
            }
            
            # Track active orders
            if trade.order.orderId:
                self.active_orders[trade.order.orderId] = trade
            
            self.order_status_updated.emit(order_data)
            
        except Exception as e:
            self.logger.error(f"Error processing order status: {e}")
    
    def _on_position_update(self, position) -> None:
        """Handle position updates."""
        try:
            pos_data = {
                'symbol': position.contract.symbol,
                'sec_type': position.contract.secType,
                'position': position.position,
                'market_price': position.marketPrice,
                'market_value': position.marketValue,
                'average_cost': position.averageCost,
                'unrealized_pnl': position.unrealizedPNL,
                'realized_pnl': position.realizedPNL,
                'account': position.account,
                'contract_id': getattr(position.contract, 'conId', None),
                'exchange': getattr(position.contract, 'exchange', ''),
                'timestamp': datetime.now().isoformat()
            }
            
            # Add option-specific position data
            if position.contract.secType == 'OPT':
                pos_data.update({
                    'strike': getattr(position.contract, 'strike', None),
                    'right': getattr(position.contract, 'right', None),
                    'expiry': getattr(position.contract, 'lastTradeDateOrContractMonth', None)
                })
            
            self.position_updated.emit(pos_data)
            
        except Exception as e:
            self.logger.error(f"Error processing position update: {e}")
    
    def _on_account_update(self, account_value) -> None:
        """Handle account updates."""
        try:
            account_data = {
                'tag': account_value.tag,
                'value': account_value.value,
                'currency': account_value.currency,
                'account': account_value.account,
                'timestamp': datetime.now().isoformat()
            }
            
            self.account_data_updated.emit(account_data)
            
        except Exception as e:
            self.logger.error(f"Error processing account update: {e}")
    
    def _on_execution(self, trade, fill) -> None:
        """Handle trade executions."""
        try:
            execution_data = {
                'order_id': trade.order.orderId,
                'exec_id': fill.execution.execId,
                'symbol': fill.contract.symbol,
                'side': fill.execution.side,
                'shares': fill.execution.shares,
                'price': fill.execution.price,
                'commission': fill.commissionReport.commission if fill.commissionReport else 0,
                'timestamp': fill.execution.time,
                'exchange': fill.execution.exchange,
                'account': fill.execution.acctNumber,
                'perm_id': fill.execution.permId
            }
            
            self.trade_executed.emit(execution_data)
            
        except Exception as e:
            self.logger.error(f"Error processing execution: {e}")
    
    def _on_contract_details(self, reqId, contractDetails) -> None:
        """Handle contract details response."""
        try:
            # Store contract details by request ID
            if not hasattr(self, '_contract_details_cache'):
                self._contract_details_cache = {}
            
            if reqId not in self._contract_details_cache:
                self._contract_details_cache[reqId] = []
            
            self._contract_details_cache[reqId].append(contractDetails)
            
        except Exception as e:
            self.logger.error(f"Error processing contract details: {e}")
    
    def _on_news_update(self, news) -> None:
        """Handle news updates."""
        try:
            news_data = {
                'article_id': getattr(news, 'articleId', ''),
                'headline': getattr(news, 'headline', ''),
                'provider_code': getattr(news, 'providerCode', ''),
                'timestamp': getattr(news, 'time', datetime.now().isoformat()),
                'sentiment': getattr(news, 'sentiment', None)
            }
            
            self.news_received.emit(news_data)
            
        except Exception as e:
            self.logger.error(f"Error processing news update: {e}")
    
    def _on_disconnected(self) -> None:
        """Handle disconnection events."""
        self.logger.warning("🔌 IB Gateway disconnected")
        self._update_connection_state(ConnectionState.DISCONNECTED, "Disconnected from IB Gateway")
        self.connection_ready.clear()
        
        if self.is_running:
            asyncio.create_task(self._handle_disconnection())
    
    # ==========================================================================
    # Async Request Handlers
    # ==========================================================================
    @pyqtSlot(str, object)
    def _handle_async_request(self, operation_type: str, data: Any) -> None:
        """Handle async requests from the GUI thread."""
        if not self.loop or self.loop.is_closed():
            self.logger.error(f"Cannot handle {operation_type}: AsyncIO loop not running")
            return
            
        # Schedule the async operation in the asyncio thread
        asyncio.run_coroutine_threadsafe(
            self._process_async_request(operation_type, data),
            self.loop
        )
    
    async def _process_async_request(self, operation_type: str, data: Any) -> None:
        """Process async requests in the asyncio thread."""
        try:
            if operation_type == 'market_data':
                await self._handle_market_data_request(data)
            elif operation_type == 'place_order':
                await self._handle_order_request(data)
            elif operation_type == 'contract_details':
                await self._handle_contract_details_request(data)
            elif operation_type == 'cancel_market_data':
                await self._handle_cancel_market_data(data)
            else:
                self.logger.error(f"Unknown async operation: {operation_type}")
                
        except Exception as e:
            self.logger.error(f"Error processing {operation_type}: {e}")
            self.error_occurred.emit(-1, str(e), f"Async Request: {operation_type}")
    
    async def _handle_market_data_request(self, request: MarketDataRequest) -> None:
        """Handle market data subscription request."""
        try:
            if not self.ib.isConnected():
                raise TradingError("Not connected to IB Gateway")
            
            # Convert SPYDER contract to ib_insync contract
            ib_contract = self._convert_spyder_to_ib_contract(request.contract)
            
            # Qualify the contract first
            qualified_contracts = await self.ib.qualifyContractsAsync(ib_contract)
            if not qualified_contracts:
                raise TradingError(f"Could not qualify contract: {request.contract.symbol}")
            
            contract = qualified_contracts[0]
            
            # Subscribe to market data
            ticker = self.ib.reqMktData(
                contract,
                request.tick_types,
                request.snapshot,
                request.regulatory_snapshot
            )
            
            # Store request ID for tracking
            ticker._request_id = request.request_id
            self.active_subscriptions[request.request_id] = ticker
            
            # Set up individual ticker callback (this is how ib_insync works)
            ticker.updateEvent += lambda t=ticker: self._on_ticker_update(t)
            
            self.logger.debug(f"Market data subscription active: {contract.symbol}")
            
        except Exception as e:
            self.logger.error(f"Market data request failed: {e}")
            self.error_occurred.emit(-1, str(e), "Market Data Request")
    
    async def _handle_order_request(self, request: OrderRequest) -> None:
        """Handle order placement request."""
        try:
            if not self.ib.isConnected():
                raise TradingError("Not connected to IB Gateway")
            
            # Convert SPYDER contract to ib_insync contract
            ib_contract = self._convert_spyder_to_ib_contract(request.contract)
            
            # Qualify the contract
            qualified_contracts = await self.ib.qualifyContractsAsync(ib_contract)
            if not qualified_contracts:
                raise TradingError(f"Could not qualify contract: {request.contract.symbol}")
            
            contract = qualified_contracts[0]
            
            # Convert SPYDER order to ib_insync order
            ib_order = self._convert_spyder_to_ib_order(request.order)
            
            # Place the order
            trade = self.ib.placeOrder(contract, ib_order)
            
            # Track the order
            if ib_order.orderId:
                self.active_orders[ib_order.orderId] = trade
            self.pending_requests[request.request_id] = trade
            
            self.logger.info(f"Order placed: {contract.symbol} {ib_order.action} {ib_order.totalQuantity}")
            
        except Exception as e:
            self.logger.error(f"Order placement failed: {e}")
            self.error_occurred.emit(-1, str(e), "Order Placement")
    
    async def _handle_contract_details_request(self, request: ContractRequest) -> None:
        """Handle contract details request."""
        try:
            if not self.ib.isConnected():
                raise TradingError("Not connected to IB Gateway")
            
            # Convert SPYDER contract to ib_insync contract
            ib_contract = self._convert_spyder_to_ib_contract(request.contract)
            
            # Request contract details
            details = await self.ib.reqContractDetailsAsync(ib_contract)
            
            # Emit the results
            self.contract_details_received.emit(request.request_id, details)
            
        except Exception as e:
            self.logger.error(f"Contract details request failed: {e}")
            self.error_occurred.emit(-1, str(e), "Contract Details")
    
    async def _handle_cancel_market_data(self, data: Dict) -> None:
        """Handle market data cancellation."""
        try:
            request_id = data['request_id']
            
            if request_id in self.active_subscriptions:
                ticker = self.active_subscriptions[request_id]
                self.ib.cancelMktData(ticker.contract)
                del self.active_subscriptions[request_id]
                
                self.logger.debug(f"Market data cancelled: {request_id}")
                
        except Exception as e:
            self.logger.error(f"Cancel market data failed: {e}")
    
    # ==========================================================================
    # Contract and Order Conversion Methods
    # ==========================================================================
    def _convert_spyder_to_ib_contract(self, spyder_contract: IBContract) -> Contract:
        """Convert SPYDER IBContract to ib_insync Contract."""
        try:
            if spyder_contract.sec_type == SecurityType.STOCK:
                return Stock(
                    symbol=spyder_contract.symbol,
                    exchange=spyder_contract.exchange,
                    currency=spyder_contract.currency
                )
            elif spyder_contract.sec_type == SecurityType.OPTION:
                return Option(
                    symbol=spyder_contract.symbol,
                    lastTradeDateOrContractMonth=spyder_contract.last_trade_date,
                    strike=spyder_contract.strike,
                    right=spyder_contract.right,
                    exchange=spyder_contract.exchange,
                    currency=spyder_contract.currency
                )
            elif spyder_contract.sec_type == SecurityType.FUTURE:
                return Future(
                    symbol=spyder_contract.symbol,
                    lastTradeDateOrContractMonth=spyder_contract.last_trade_date,
                    exchange=spyder_contract.exchange,
                    currency=spyder_contract.currency
                )
            else:
                # Generic contract for other types
                contract = Contract()
                contract.symbol = spyder_contract.symbol
                contract.secType = spyder_contract.sec_type.value
                contract.exchange = spyder_contract.exchange
                contract.currency = spyder_contract.currency
                
                if spyder_contract.last_trade_date:
                    contract.lastTradeDateOrContractMonth = spyder_contract.last_trade_date
                if spyder_contract.strike:
                    contract.strike = spyder_contract.strike
                if spyder_contract.right:
                    contract.right = spyder_contract.right
                if spyder_contract.multiplier:
                    contract.multiplier = spyder_contract.multiplier
                    
                return contract
                
        except Exception as e:
            self.logger.error(f"Error converting SPYDER contract: {e}")
            raise TradingError(f"Contract conversion failed: {e}")
    
    def _convert_spyder_to_ib_order(self, spyder_order: IBOrder) -> Order:
        """Convert SPYDER IBOrder to ib_insync Order."""
        try:
            if spyder_order.order_type == OrderType.MARKET:
                ib_order = MarketOrder(
                    action=spyder_order.action.value,
                    totalQuantity=spyder_order.total_quantity
                )
            elif spyder_order.order_type == OrderType.LIMIT:
                ib_order = LimitOrder(
                    action=spyder_order.action.value,
                    totalQuantity=spyder_order.total_quantity,
                    lmtPrice=spyder_order.lmt_price
                )
            elif spyder_order.order_type == OrderType.STOP:
                ib_order = StopOrder(
                    action=spyder_order.action.value,
                    totalQuantity=spyder_order.total_quantity,
                    stopPrice=spyder_order.aux_price
                )
            else:
                # Generic order
                ib_order = Order()
                ib_order.action = spyder_order.action.value
                ib_order.totalQuantity = spyder_order.total_quantity
                ib_order.orderType = spyder_order.order_type.value
                
                if spyder_order.lmt_price:
                    ib_order.lmtPrice = spyder_order.lmt_price
                if spyder_order.aux_price:
                    ib_order.auxPrice = spyder_order.aux_price
            
            # Set common properties
            ib_order.tif = spyder_order.tif
            if spyder_order.order_id:
                ib_order.orderId = spyder_order.order_id
            if spyder_order.account:
                ib_order.account = spyder_order.account
            
            return ib_order
            
        except Exception as e:
            self.logger.error(f"Error converting SPYDER order: {e}")
            raise TradingError(f"Order conversion failed: {e}")
    
    # ==========================================================================
    # Monitoring and Maintenance
    # ==========================================================================
    async def _heartbeat_monitor(self) -> None:
        """Monitor connection health with periodic heartbeat."""
        while self.is_running:
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                
                if not self.shutdown_event.is_set() and self.ib.isConnected():
                    # Simple connectivity check - request current time
                    current_time = await self.ib.reqCurrentTimeAsync()
                    self.logger.debug(f"Heartbeat: IB time {current_time}")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.warning(f"Heartbeat check failed: {e}")
                if self.is_running:
                    await self._handle_disconnection()
                break
    
    async def _connection_monitor(self) -> None:
        """Monitor and handle disconnections."""
        while self.is_running:
            try:
                await asyncio.sleep(5)  # Check every 5 seconds
                
                if not self.shutdown_event.is_set() and not self.ib.isConnected() and self.is_running:
                    self.logger.warning("Connection lost - attempting reconnection")
                    await self._handle_disconnection()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Connection monitor error: {e}")
    
    async def _data_processor(self) -> None:
        """Process ongoing data operations."""
        while self.is_running:
            try:
                await asyncio.sleep(30)  # Every 30 seconds
                
                if not self.shutdown_event.is_set() and self.ib.isConnected():
                    # Periodic data refresh operations
                    await self._refresh_account_data()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Data processor error: {e}")
    
    async def _refresh_account_data(self) -> None:
        """Refresh account data periodically."""
        try:
            # Request fresh account summary
            account_summary = await self.ib.reqAccountSummaryAsync()
            
            for item in account_summary:
                self._on_account_update(item)
                
        except Exception as e:
            self.logger.debug(f"Account data refresh failed: {e}")
    
    async def _handle_disconnection(self) -> None:
        """Handle disconnection and attempt reconnection."""
        if self.reconnect_count >= MAX_RECONNECT_ATTEMPTS:
            self.logger.error("Maximum reconnection attempts reached")
            self._update_connection_state(ConnectionState.ERROR, "Max reconnection attempts reached")
            return
        
        self.reconnect_count += 1
        self._update_connection_state(ConnectionState.RECONNECTING, 
            f"Reconnecting... (attempt {self.reconnect_count})")
        
        await asyncio.sleep(RECONNECT_DELAY)
        
        if await self._connect_with_retry(MAX_RECONNECT_ATTEMPTS - self.reconnect_count):
            self.logger.info("✅ Reconnection successful")
            await self._restore_subscriptions()
        else:
            self.logger.error("❌ Reconnection failed")
    
    async def _restore_subscriptions(self) -> None:
        """Restore market data subscriptions after reconnection."""
        try:
            restored_count = 0
            
            for request_id, ticker in list(self.active_subscriptions.items()):
                try:
                    # Re-subscribe to market data
                    new_ticker = self.ib.reqMktData(ticker.contract, '', False, False)
                    new_ticker._request_id = request_id
                    
                    # Re-attach the callback
                    new_ticker.updateEvent += lambda t=new_ticker: self._on_ticker_update(t)
                    
                    self.active_subscriptions[request_id] = new_ticker
                    restored_count += 1
                    
                except Exception as e:
                    self.logger.error(f"Failed to restore subscription {request_id}: {e}")
                    del self.active_subscriptions[request_id]
            
            self.logger.info(f"Restored {restored_count} market data subscriptions")
            
        except Exception as e:
            self.logger.error(f"Error restoring subscriptions: {e}")
    
    # ==========================================================================
    # Utility Methods
    # ==========================================================================
    def _update_connection_state(self, state: ConnectionState, message: str) -> None:
        """Update connection state and emit signal."""
        self.connection_state = state
        self.connection_status_changed.emit(state.value, message)
        self.logger.info(f"Connection state: {state.value} - {message}")
    
    def _schedule_shutdown(self) -> None:
        """Schedule graceful shutdown in asyncio thread."""
        if self.loop and not self.loop.is_closed():
            for task in asyncio.all_tasks(self.loop):
                task.cancel()
    
    def _cleanup_asyncio(self) -> None:
        """Clean up asyncio resources."""
        try:
            if self.ib and self.ib.isConnected():
                self.ib.disconnect()
                
            if self.loop and not self.loop.is_closed():
                self.loop.close()
                
        except Exception as e:
            self.logger.error(f"Error during asyncio cleanup: {e}")
        finally:
            self.logger.info("AsyncIO resources cleaned up")

# =============================================================================
# Module Utility Functions
# =============================================================================
def create_spy_async_bridge(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, 
                           client_id: int = DEFAULT_CLIENT_ID) -> AsyncIOBridge:
    """
    Factory function to create a configured AsyncIO bridge for SPY trading.
    
    Args:
        host: IB Gateway host
        port: IB Gateway port
        client_id: Client ID
        
    Returns:
        Configured AsyncIOBridge instance
    """
    return AsyncIOBridge(host, port, client_id)

# =============================================================================
# Example Usage and Testing
# =============================================================================
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    
    # Example of how to use the AsyncIOBridge with SPYDER data types
    app = QApplication(sys.argv)
    
    # Create the bridge
    bridge = AsyncIOBridge()
    
    # Connect to signals for testing
    bridge.connection_status_changed.connect(
        lambda state, msg: print(f"Connection: {state} - {msg}")
    )
    bridge.ticker_updated.connect(
        lambda data: print(f"Market Data: {data}")
    )
    bridge.error_occurred.connect(
        lambda code, msg, ctx: print(f"Error {code}: {msg} ({ctx})")
    )
    
    # Start the worker
    bridge.start_async_worker()
    
    # Example: Request SPY market data using SPYDER data types
    def request_spy_data():
        # Use SPYDER data types
        request_id = bridge.request_market_data_for_stock('SPY', 'ARCA')
        print(f"SPY market data requested: {request_id}")
    
    QTimer.singleShot(2000, request_spy_data)
    
    # Example: Stop after 30 seconds
    QTimer.singleShot(30000, lambda: (bridge.stop_async_worker(), app.quit()))
    
    print("🕷️ SPYDER AsyncIO Bridge Test - Starting...")
    print("📊 Using standardized SPYDER data types from SpyderB10")
    print("🌉 Concurrent event loops architecture active")
    app.exec()