#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB01_SpyderClient.py
Purpose: Enhanced SpyderClient with market data type support and modern ib_async integration
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-01-21 Time: 16:00:00  

Module Description:
    Enhanced SpyderClient that properly supports different market data types 
    (FROZEN/DELAYED) based on account permissions. Uses modern ib_async library
    for optimal IB Gateway 10.37 compatibility. Includes automatic detection
    of working data types, proper error handling, and integration with the fixed
    MarketDataManager. Resolves the NaN data issue by using appropriate data types.

Key Improvements:
    • Modern ib_async integration for enhanced stability
    • Better IB Gateway 10.37 compatibility
    • Improved error handling and connection management
    • Enhanced market data type detection
    • Automatic fallback to working data types

Dependencies:
    • ib_async (modern IB API wrapper)
    • Standard Python threading and logging libraries

Installation Note:
    pip install ib_async
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import time
import threading
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum, auto
import logging

# ==============================================================================
# THIRD-PARTY IMPORTS - Modern ib_async
# ==============================================================================
try:
    from ib_async import IB, Stock, Option, Future, Index, Contract, Ticker
    from ib_async import MarketOrder, LimitOrder, OrderStatus
    IB_ASYNC_AVAILABLE = True
except ImportError:
    print("⚠️ ib_async not available - running in simulation mode")
    print("Install with: pip install ib_async")
    IB_ASYNC_AVAILABLE = False
    # Mock classes for testing
    class IB:
        def connect(self, *args, **kwargs): return False
        def disconnect(self): pass
        def isConnected(self): return False
    class Stock: pass
    class Ticker: pass
    class Contract: pass
    class MarketOrder: pass
    class LimitOrder: pass

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Market Data Types (from comprehensive testing)
MARKET_DATA_TYPE_REALTIME = 1      # ❌ Returns NaN (requires special permissions)
MARKET_DATA_TYPE_FROZEN = 2        # ✅ Works! Best option for most accounts
MARKET_DATA_TYPE_DELAYED = 3       # ✅ Works! 15-minute delayed
MARKET_DATA_TYPE_DELAYED_FROZEN = 4 # ✅ Works!

# Connection Constants
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 4002  # Paper trading port
DEFAULT_CLIENT_ID = 1
DEFAULT_TIMEOUT = 30
MAX_CONNECTION_RETRIES = 3

# Market Data Constants
DEFAULT_MARKET_DATA_TYPE = MARKET_DATA_TYPE_FROZEN  # Best working option
MARKET_DATA_TIMEOUT = 10  # Seconds to wait for market data

# ==============================================================================
# ENUMS
# ==============================================================================

class ConnectionStatus(Enum):
    """Connection status enumeration"""
    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    ERROR = auto()

class MarketDataType(Enum):
    """Market data type enumeration"""
    REALTIME = MARKET_DATA_TYPE_REALTIME
    FROZEN = MARKET_DATA_TYPE_FROZEN
    DELAYED = MARKET_DATA_TYPE_DELAYED
    DELAYED_FROZEN = MARKET_DATA_TYPE_DELAYED_FROZEN

# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class IBConfig:
    """Configuration for IB connection"""
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    client_id: int = DEFAULT_CLIENT_ID
    timeout: float = DEFAULT_TIMEOUT
    market_data_type: int = DEFAULT_MARKET_DATA_TYPE
    readonly: bool = True

@dataclass
class MarketDataInfo:
    """Market data information"""
    symbol: str
    price: float
    bid: float = 0.0
    ask: float = 0.0
    volume: int = 0
    timestamp: Optional[datetime] = None
    market_data_type: int = DEFAULT_MARKET_DATA_TYPE

# ==============================================================================
# MAIN CLIENT CLASS
# ==============================================================================

class SpyderClient:
    """
    Enhanced SpyderClient with modern ib_async integration.
    
    This class provides the main Interactive Brokers client interface using
    the modern ib_async library for optimal IB Gateway 10.37 compatibility.
    Handles connection management, order placement, position tracking, and 
    market data requests with enhanced error handling and stability.
    
    Key features:
    - Modern ib_async integration
    - Automatic market data type detection
    - Enhanced error handling and recovery
    - Thread-safe operations
    - Comprehensive logging
    """

    def __init__(self, config: IBConfig, event_manager=None):
        """
        Initialize SpyderClient with modern ib_async.
        
        Args:
            config: IBConfig object with connection parameters
            event_manager: Optional event manager for notifications
        """
        self.config = config
        self.event_manager = event_manager
        
        # Core components
        self.ib: Optional[IB] = None
        self.status = ConnectionStatus.DISCONNECTED
        
        # Logging and error handling
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Connection tracking
        self.connection_attempts = 0
        self.last_connection_time: Optional[datetime] = None
        self.connection_lock = threading.Lock()
        
        # Market data management
        self.market_data_subscriptions: Dict[int, str] = {}
        self.market_data_cache: Dict[str, MarketDataInfo] = {}
        self.next_req_id = 1
        self.req_id_lock = threading.Lock()
        
        # Market data type tracking
        self.current_market_data_type = config.market_data_type
        self.tested_data_types: Set[int] = set()
        
        self.logger.info("SpyderClient initialized with modern ib_async")

    # ==========================================================================
    # CONNECTION MANAGEMENT
    # ==========================================================================

    def connect(self) -> bool:
        """
        Connect to IB Gateway using modern ib_async.
        
        Returns:
            bool: True if connected successfully
        """
        if not IB_ASYNC_AVAILABLE:
            self.logger.error("❌ ib_async not available")
            return False
            
        try:
            self.logger.info(f"🔗 Connecting to IB Gateway at {self.config.host}:{self.config.port}")
            self.status = ConnectionStatus.CONNECTING
            
            # Create IB instance
            self.ib = IB()
            
            # Setup event handlers
            self._setup_event_handlers()
            
            # Attempt connection with retries
            for attempt in range(MAX_CONNECTION_RETRIES):
                try:
                    self.logger.info(f"Connection attempt {attempt + 1}/{MAX_CONNECTION_RETRIES}")
                    
                    self.ib.connect(
                        host=self.config.host,
                        port=self.config.port,
                        clientId=self.config.client_id,
                        timeout=self.config.timeout
                    )
                    
                    if self.ib.isConnected():
                        self.status = ConnectionStatus.CONNECTED
                        self.connection_attempts = attempt + 1
                        self.last_connection_time = datetime.now()
                        
                        # Initialize market data type
                        self._initialize_market_data_type()
                        
                        self.logger.info(f"✅ Connected to IB Gateway (attempt {attempt + 1})")
                        return True
                        
                except Exception as e:
                    self.logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
                    if attempt < MAX_CONNECTION_RETRIES - 1:
                        time.sleep(2)  # Wait before retry
                        
            self.status = ConnectionStatus.ERROR
            self.logger.error("❌ All connection attempts failed")
            return False
            
        except Exception as e:
            self.logger.error(f"❌ Connection error: {e}")
            self.error_handler.handle_error(e)
            self.status = ConnectionStatus.ERROR
            return False

    def disconnect(self) -> bool:
        """
        Disconnect from IB Gateway.
        
        Returns:
            bool: True if disconnected successfully
        """
        try:
            if self.ib and self.ib.isConnected():
                self.logger.info("🔌 Disconnecting from IB Gateway...")
                
                # Cancel all market data subscriptions
                self._cancel_all_subscriptions()
                
                # Disconnect
                self.ib.disconnect()
                
                self.status = ConnectionStatus.DISCONNECTED
                self.logger.info("✅ Disconnected from IB Gateway")
                return True
            else:
                self.logger.info("Already disconnected")
                return True
                
        except Exception as e:
            self.logger.error(f"❌ Disconnection error: {e}")
            self.error_handler.handle_error(e)
            return False

    def is_connected(self) -> bool:
        """Check if connected to IB Gateway."""
        return self.ib is not None and self.ib.isConnected()

    # ==========================================================================
    # EVENT HANDLERS
    # ==========================================================================

    def _setup_event_handlers(self):
        """Setup ib_async event handlers."""
        if not self.ib:
            return
            
        try:
            # Connection events
            self.ib.connectedEvent += self._on_connected
            self.ib.disconnectedEvent += self._on_disconnected
            self.ib.errorEvent += self._on_error
            
            # Market data events
            self.ib.pendingTickersEvent += self._on_ticker_update
            
        except Exception as e:
            self.logger.error(f"Error setting up event handlers: {e}")

    def _on_connected(self):
        """Handle connection established event."""
        self.logger.info("🔗 IB connection established")
        self.status = ConnectionStatus.CONNECTED

    def _on_disconnected(self):
        """Handle disconnection event."""
        self.logger.warning("🔌 IB connection lost")
        self.status = ConnectionStatus.DISCONNECTED

    def _on_error(self, reqId, errorCode, errorString, contract):
        """Handle IB error events."""
        error_msg = f"IB Error {errorCode}: {errorString}"
        
        # Log appropriate level based on error code
        if errorCode in [2104, 2106, 2158]:  # Informational
            self.logger.debug(error_msg)
        elif errorCode in [162, 200]:  # Market data issues
            self.logger.warning(f"{error_msg} - May need different market data type")
            self._try_different_market_data_type()
        else:
            self.logger.error(error_msg)

    def _on_ticker_update(self, tickers):
        """Handle ticker updates."""
        for ticker in tickers:
            try:
                if ticker.contract and ticker.contract.symbol:
                    symbol = ticker.contract.symbol
                    
                    # Update market data cache
                    self.market_data_cache[symbol] = MarketDataInfo(
                        symbol=symbol,
                        price=ticker.last if ticker.last and not math.isnan(ticker.last) else 0.0,
                        bid=ticker.bid if ticker.bid and not math.isnan(ticker.bid) else 0.0,
                        ask=ticker.ask if ticker.ask and not math.isnan(ticker.ask) else 0.0,
                        volume=ticker.volume if ticker.volume else 0,
                        timestamp=datetime.now(),
                        market_data_type=self.current_market_data_type
                    )
                    
            except Exception as e:
                self.logger.error(f"Error processing ticker update: {e}")

    # ==========================================================================
    # MARKET DATA TYPE MANAGEMENT
    # ==========================================================================

    def _initialize_market_data_type(self):
        """Initialize market data type for optimal compatibility."""
        try:
            if self.ib and self.ib.isConnected():
                self.ib.reqMarketDataType(self.current_market_data_type)
                self.tested_data_types.add(self.current_market_data_type)
                self.logger.info(f"📊 Market data type set to: {self.current_market_data_type}")
                
        except Exception as e:
            self.logger.error(f"Error setting market data type: {e}")

    def _try_different_market_data_type(self):
        """Try a different market data type if current one fails."""
        try:
            # Try data types in order of preference
            preferred_types = [
                MARKET_DATA_TYPE_FROZEN,
                MARKET_DATA_TYPE_DELAYED,
                MARKET_DATA_TYPE_DELAYED_FROZEN
            ]
            
            for data_type in preferred_types:
                if data_type not in self.tested_data_types:
                    self.logger.info(f"🔄 Trying market data type: {data_type}")
                    self.current_market_data_type = data_type
                    self.tested_data_types.add(data_type)
                    
                    if self.ib and self.ib.isConnected():
                        self.ib.reqMarketDataType(data_type)
                    break
                    
        except Exception as e:
            self.logger.error(f"Error changing market data type: {e}")

    # ==========================================================================
    # CONTRACT CREATION
    # ==========================================================================

    def create_stock_contract(self, symbol: str, exchange: str = "SMART", currency: str = "USD") -> Contract:
        """Create stock contract using ib_async."""
        try:
            if not IB_ASYNC_AVAILABLE:
                # Return mock contract for testing
                mock_contract = type('MockContract', (), {})()
                mock_contract.symbol = symbol
                mock_contract.secType = 'STK'
                mock_contract.exchange = exchange
                mock_contract.currency = currency
                return mock_contract
                
            contract = Stock(symbol, exchange, currency)
            self.logger.debug(f"Created stock contract: {symbol}")
            return contract
            
        except Exception as e:
            self.logger.error(f"Error creating stock contract for {symbol}: {e}")
            raise

    def create_option_contract(self, symbol: str, expiry: str, strike: float, 
                             right: str, exchange: str = "SMART", currency: str = "USD") -> Contract:
        """Create option contract using ib_async."""
        try:
            if not IB_ASYNC_AVAILABLE:
                # Return mock contract for testing
                mock_contract = type('MockContract', (), {})()
                mock_contract.symbol = symbol
                mock_contract.secType = 'OPT'
                mock_contract.lastTradeDateOrContractMonth = expiry
                mock_contract.strike = strike
                mock_contract.right = right
                mock_contract.exchange = exchange
                mock_contract.currency = currency
                return mock_contract
                
            contract = Option(symbol, expiry, strike, right, exchange, currency)
            self.logger.debug(f"Created option contract: {symbol} {expiry} {strike} {right}")
            return contract
            
        except Exception as e:
            self.logger.error(f"Error creating option contract: {e}")
            raise

    # ==========================================================================
    # MARKET DATA REQUESTS
    # ==========================================================================

    def request_market_data(self, contract: Contract, snapshot: bool = False) -> int:
        """
        Request market data using ib_async.
        
        Args:
            contract: Contract to request data for
            snapshot: Whether to request snapshot data
            
        Returns:
            int: Request ID or -1 if failed
        """
        try:
            if not self.is_connected():
                self.logger.error("Not connected to IB Gateway")
                return -1
                
            with self.req_id_lock:
                req_id = self.next_req_id
                self.next_req_id += 1
            
            ticker = self.ib.reqMktData(contract, '', snapshot, False)
            
            if ticker:
                self.market_data_subscriptions[req_id] = contract.symbol
                self.logger.debug(f"Requested market data for {contract.symbol} (req_id: {req_id})")
                return req_id
            else:
                self.logger.error(f"Failed to request market data for {contract.symbol}")
                return -1
                
        except Exception as e:
            self.logger.error(f"Error requesting market data: {e}")
            return -1

    def cancel_market_data(self, req_id: int) -> bool:
        """Cancel market data subscription."""
        try:
            if req_id in self.market_data_subscriptions:
                symbol = self.market_data_subscriptions[req_id]
                
                # Find ticker and cancel
                for ticker in self.ib.tickers():
                    if ticker.contract and ticker.contract.symbol == symbol:
                        self.ib.cancelMktData(ticker)
                        break
                
                del self.market_data_subscriptions[req_id]
                self.logger.debug(f"Cancelled market data for {symbol} (req_id: {req_id})")
                return True
            else:
                self.logger.warning(f"Request ID {req_id} not found")
                return False
                
        except Exception as e:
            self.logger.error(f"Error cancelling market data: {e}")
            return False

    def get_market_data(self, req_id: int) -> Optional[MarketDataInfo]:
        """Get market data for request ID."""
        try:
            if req_id in self.market_data_subscriptions:
                symbol = self.market_data_subscriptions[req_id]
                return self.market_data_cache.get(symbol)
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting market data: {e}")
            return None

    def _cancel_all_subscriptions(self):
        """Cancel all market data subscriptions."""
        try:
            for req_id in list(self.market_data_subscriptions.keys()):
                self.cancel_market_data(req_id)
                
        except Exception as e:
            self.logger.error(f"Error cancelling subscriptions: {e}")

    # ==========================================================================
    # ACCOUNT AND POSITION INFORMATION
    # ==========================================================================

    def get_account_info(self) -> Dict[str, Any]:
        """Get account information."""
        try:
            if not self.is_connected():
                return {
                    'net_liquidation': 100000.0,  # Mock data
                    'buying_power': 200000.0,
                    'available_funds': 100000.0
                }
                
            # Get account values
            account_values = self.ib.accountValues()
            
            account_info = {}
            for av in account_values:
                if av.tag == 'NetLiquidation':
                    account_info['net_liquidation'] = float(av.value)
                elif av.tag == 'BuyingPower':
                    account_info['buying_power'] = float(av.value)
                elif av.tag == 'AvailableFunds':
                    account_info['available_funds'] = float(av.value)
            
            return account_info
            
        except Exception as e:
            self.logger.error(f"Error getting account info: {e}")
            return {}

    def get_buying_power(self) -> float:
        """Get buying power."""
        account_info = self.get_account_info()
        return account_info.get('buying_power', 0.0)

    def get_positions(self) -> List[Any]:
        """Get current positions."""
        try:
            if not self.is_connected():
                return []  # Mock empty positions
                
            return self.ib.positions()
            
        except Exception as e:
            self.logger.error(f"Error getting positions: {e}")
            return []

    # ==========================================================================
    # ORDER MANAGEMENT
    # ==========================================================================

    def place_order(self, contract: Contract, order: Any) -> Optional[Any]:
        """Place order using ib_async."""
        try:
            if not self.is_connected():
                self.logger.error("Not connected to IB Gateway")
                return None
                
            trade = self.ib.placeOrder(contract, order)
            self.logger.info(f"Order placed: {order.action} {order.totalQuantity} {contract.symbol}")
            return trade
            
        except Exception as e:
            self.logger.error(f"Error placing order: {e}")
            return None

    def create_market_order(self, action: str, quantity: int) -> Any:
        """Create market order."""
        try:
            if not IB_ASYNC_AVAILABLE:
                # Return mock order
                mock_order = type('MockOrder', (), {})()
                mock_order.action = action
                mock_order.totalQuantity = quantity
                mock_order.orderType = 'MKT'
                return mock_order
                
            return MarketOrder(action, quantity)
            
        except Exception as e:
            self.logger.error(f"Error creating market order: {e}")
            raise

    def create_limit_order(self, action: str, quantity: int, limit_price: float) -> Any:
        """Create limit order."""
        try:
            if not IB_ASYNC_AVAILABLE:
                # Return mock order
                mock_order = type('MockOrder', (), {})()
                mock_order.action = action
                mock_order.totalQuantity = quantity
                mock_order.orderType = 'LMT'
                mock_order.lmtPrice = limit_price
                return mock_order
                
            return LimitOrder(action, quantity, limit_price)
            
        except Exception as e:
            self.logger.error(f"Error creating limit order: {e}")
            raise

    # ==========================================================================
    # STATUS AND DIAGNOSTICS
    # ==========================================================================

    def get_status(self) -> Dict[str, Any]:
        """Get client status information."""
        return {
            'connected': self.is_connected(),
            'status': self.status.name,
            'library': 'ib_async (modern)',
            'host': self.config.host,
            'port': self.config.port,
            'client_id': self.config.client_id,
            'market_data_type': self.current_market_data_type,
            'connection_attempts': self.connection_attempts,
            'last_connection': self.last_connection_time,
            'subscriptions': len(self.market_data_subscriptions),
            'cached_symbols': len(self.market_data_cache)
        }

    def get_connection_quality(self) -> str:
        """Get connection quality assessment."""
        if not self.is_connected():
            return "DISCONNECTED"
        elif len(self.market_data_cache) > 0:
            return "EXCELLENT"
        elif self.current_market_data_type == MARKET_DATA_TYPE_FROZEN:
            return "GOOD"
        else:
            return "FAIR"


# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================

def create_spyder_client(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, 
                        client_id: int = DEFAULT_CLIENT_ID) -> SpyderClient:
    """
    Create SpyderClient with default configuration.
    
    Args:
        host: IB Gateway host
        port: IB Gateway port  
        client_id: Client ID
        
    Returns:
        SpyderClient instance
    """
    config = IBConfig(host=host, port=port, client_id=client_id)
    return SpyderClient(config)

def get_spyder_client() -> SpyderClient:
    """Get SpyderClient with default paper trading configuration."""
    return create_spyder_client()

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    # Example usage and testing
    import sys
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    logger.info("SpyderClient - Enhanced with ib_async")
    logger.info("=" * 50)
    
    try:
        # Create client
        client = get_spyder_client()
        
        # Test connection
        if client.connect():
            logger.info("✅ Connected successfully")
            
            # Show status
            status = client.get_status()
            logger.info(f"📊 Status: {status}")
            
            # Test contract creation
            spy_stock = client.create_stock_contract('SPY')
            logger.info(f"📄 Created contract: {spy_stock.symbol}")
            
            # Test account info
            account = client.get_account_info()
            logger.info(f"💰 Account: ${account.get('net_liquidation', 0):,.2f}")
            
            # Disconnect
            client.disconnect()
            logger.info("✅ Disconnected successfully")
            
        else:
            logger.error("❌ Connection failed")
            
    except Exception as e:
        logger.error(f"Error in main: {e}")
        
    logger.info(f"\n🎉 SpyderClient ready with ib_async!")
    logger.info(f"Library available: {IB_ASYNC_AVAILABLE}")
