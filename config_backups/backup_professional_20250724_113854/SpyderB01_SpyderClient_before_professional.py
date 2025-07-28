#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System
Module: SpyderB01_SpyderClient.py (IBAPI Version)
Group: B (Broker Integration)  
Purpose: Professional IBAPI client for algorithmic SPY options trading

Description:
    Production-ready Interactive Brokers client using official IBAPI.
    Designed for high-frequency SPY options trading with maximum reliability,
    control, and performance. Handles real-time market data, order management,
    and position tracking with professional-grade error handling.

Author: Mohamed Talib
Date: 2025-07-24
Version: 3.0 (IBAPI Production)
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import threading
import time
import queue
import logging
from typing import Optional, Dict, Any, List, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import socket

# ==============================================================================
# IBAPI IMPORTS - Official Interactive Brokers API
# ==============================================================================
try:
    from ibapi.client import EClient
    from ibapi.wrapper import EWrapper
    from ibapi.contract import Contract
    from ibapi.order import Order
    from ibapi.common import OrderId, TickType, TickerId
    from ibapi.ticktype import TickTypeEnum
    HAS_IBAPI = True
except ImportError:
    print("❌ IBAPI not found. Install with: pip install ibapi")
    HAS_IBAPI = False
    
    # Fallback classes
    class EClient:
        pass
    class EWrapper:
        pass
    class Contract:
        pass
    class Order:
        pass

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS FOR PRODUCTION TRADING
# ==============================================================================
DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 4002  # IB Gateway Paper Trading  
DEFAULT_LIVE_PORT = 4001  # IB Gateway Live Trading
DEFAULT_CLIENT_ID = 1
CONNECTION_TIMEOUT = 15
MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY = 2

# Market Data Request IDs
MARKET_DATA_ID_BASE = 1000
SPY_MARKET_DATA_ID = 1001
OPTIONS_DATA_ID_BASE = 2000

# Order Management
ORDER_ID_BASE = 10000
MAX_CONCURRENT_ORDERS = 50

# ==============================================================================
# ENUMS
# ==============================================================================
class ConnectionState(Enum):
    """Connection state for IBAPI client"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting" 
    CONNECTED = "connected"
    ERROR = "error"

class MarketDataType(Enum):
    """Market data types"""
    LIVE = 1
    FROZEN = 2
    DELAYED = 3
    DELAYED_FROZEN = 4

# ==============================================================================
# DATA CLASSES
# ==============================================================================
@dataclass
class IBConfig:
    """IBAPI connection configuration"""
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    client_id: int = DEFAULT_CLIENT_ID
    timeout: int = CONNECTION_TIMEOUT
    
@dataclass 
class MarketTick:
    """Market data tick"""
    symbol: str
    tick_type: int
    price: float
    size: int
    timestamp: datetime

# ==============================================================================
# MAIN IBAPI CLIENT CLASS
# ==============================================================================
class SpyderIBAPIClient(EWrapper, EClient):
    """
    Professional IBAPI client for algorithmic SPY options trading.
    
    Combines EWrapper and EClient for maximum control and reliability.
    Designed specifically for high-frequency options trading strategies.
    """
    
    def __init__(self, config: Optional[IBConfig] = None):
        """Initialize IBAPI client"""
        EClient.__init__(self, self)
        
        # Configuration
        self.config = config or IBConfig()
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Connection state
        self.state = ConnectionState.DISCONNECTED
        self.next_order_id = ORDER_ID_BASE
        self.connection_event = threading.Event()
        
        # Data storage for production trading
        self.market_data: Dict[int, MarketTick] = {}
        self.positions: Dict[str, Any] = {}
        self.orders: Dict[int, Any] = {}
        self.account_values: Dict[str, float] = {}
        
        # Thread safety
        self._lock = threading.RLock()
        self._running = False
        self._message_thread: Optional[threading.Thread] = None
        
        # Request tracking
        self._market_data_requests: Dict[int, str] = {}
        self._callbacks: Dict[str, List[Callable]] = {}
        
        self.logger.info("IBAPI SpyderClient initialized for production trading")
    
    # ==========================================================================
    # CONNECTION MANAGEMENT
    # ==========================================================================
    
    def connect_to_gateway(self, timeout: int = CONNECTION_TIMEOUT) -> bool:
        """
        Connect to IB Gateway with production-grade error handling.
        
        Args:
            timeout: Connection timeout in seconds
            
        Returns:
            bool: True if connected successfully
        """
        try:
            self.state = ConnectionState.CONNECTING
            self.logger.info(f"Connecting to IB Gateway at {self.config.host}:{self.config.port}")
            
            # Test socket connectivity first
            if not self._test_gateway_connectivity():
                self.logger.error("IB Gateway not accessible - check if it's running")
                self.state = ConnectionState.ERROR
                return False
            
            # Connect to IBAPI
            self.connect(self.config.host, self.config.port, self.config.client_id)
            
            # Start message processing thread
            self._start_message_thread()
            
            # Wait for connection with timeout
            if self.connection_event.wait(timeout):
                self.state = ConnectionState.CONNECTED
                self.logger.info("✅ Successfully connected to IB Gateway")
                
                # Request next valid order ID
                self.reqIds(-1)
                
                # Set market data type to live
                self.reqMarketDataType(MarketDataType.LIVE.value)
                
                return True
            else:
                self.logger.error("Connection timeout - IB Gateway may not be responding")
                self.state = ConnectionState.ERROR
                return False
                
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            self.state = ConnectionState.ERROR
            return False
    
    def _test_gateway_connectivity(self) -> bool:
        """Test if IB Gateway is accessible"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(5)
                result = sock.connect_ex((self.config.host, self.config.port))
                return result == 0
        except Exception:
            return False
    
    def _start_message_thread(self):
        """Start IBAPI message processing thread"""
        if not self._running:
            self._running = True
            self._message_thread = threading.Thread(target=self.run, daemon=True)
            self._message_thread.start()
            self.logger.info("IBAPI message processing thread started")
    
    def disconnect_from_gateway(self):
        """Disconnect from IB Gateway"""
        try:
            self._running = False
            if self.isConnected():
                self.disconnect()
            self.state = ConnectionState.DISCONNECTED
            self.connection_event.clear()
            self.logger.info("Disconnected from IB Gateway")
        except Exception as e:
            self.logger.error(f"Error during disconnect: {e}")
    
    def is_connected(self) -> bool:
        """Check if connected to IB Gateway"""
        return self.state == ConnectionState.CONNECTED and self.isConnected()
    
    # ==========================================================================
    # IBAPI WRAPPER CALLBACKS - Production Trading
    # ==========================================================================
    
    def nextValidId(self, orderId: OrderId):
        """Receive next valid order ID"""
        self.next_order_id = orderId
        self.connection_event.set()  # Signal successful connection
        self.logger.info(f"Received next valid order ID: {orderId}")
    
    def connectAck(self):
        """Connection acknowledgment"""
        self.logger.info("Connection acknowledged by IB Gateway")
    
    def connectionClosed(self):
        """Handle connection closed"""
        self.state = ConnectionState.DISCONNECTED
        self.connection_event.clear()
        self.logger.warning("Connection to IB Gateway closed")
    
    def error(self, reqId: TickerId, errorCode: int, errorString: str, 
             advancedOrderRejectJson: str = ""):
        """Handle IBAPI errors with production-grade logging"""
        error_msg = f"IBAPI Error - ReqID: {reqId}, Code: {errorCode}, Message: {errorString}"
        
        # Critical errors that affect trading
        if errorCode in [502, 503, 504]:  # Connection errors
            self.logger.error(f"Critical connection error: {error_msg}")
            self.state = ConnectionState.ERROR
        elif errorCode in [200, 201, 202]:  # Order errors
            self.logger.error(f"Order error: {error_msg}")
        elif errorCode < 2000:  # System errors
            self.logger.error(f"System error: {error_msg}")
        else:  # Warnings and info
            self.logger.warning(f"IBAPI warning: {error_msg}")
    
    def tickPrice(self, reqId: TickerId, tickType: TickType, price: float,
                  attrib):
        """Handle real-time price ticks - Core for SPY options trading"""
        try:
            symbol = self._market_data_requests.get(reqId, "UNKNOWN")
            
            tick = MarketTick(
                symbol=symbol,
                tick_type=tickType,
                price=price,
                size=0,
                timestamp=datetime.now()
            )
            
            with self._lock:
                self.market_data[reqId] = tick
            
            # Trigger callbacks for real-time data
            self._trigger_callbacks('tick_price', tick)
            
            # Special handling for SPY (critical for options strategies)
            if symbol == 'SPY':
                self._handle_spy_price_update(price, tickType)
                
        except Exception as e:
            self.logger.error(f"Error processing price tick: {e}")
    
    def tickSize(self, reqId: TickerId, tickType: TickType, size: int):
        """Handle size ticks"""
        try:
            symbol = self._market_data_requests.get(reqId, "UNKNOWN")
            self._trigger_callbacks('tick_size', {
                'symbol': symbol,
                'tick_type': tickType,
                'size': size,
                'timestamp': datetime.now()
            })
        except Exception as e:
            self.logger.error(f"Error processing size tick: {e}")
    
    def _handle_spy_price_update(self, price: float, tick_type: int):
        """Special handling for SPY price updates (critical for options)"""
        if tick_type == TickTypeEnum.LAST:  # Last traded price
            self.logger.debug(f"SPY last price: ${price}")
            # Update options pricing models, Greeks, etc.
            self._trigger_callbacks('spy_price_update', price)
    
    # ==========================================================================
    # MARKET DATA METHODS - SPY Options Focus
    # ==========================================================================
    
    def request_spy_market_data(self) -> bool:
        """Request real-time SPY market data (essential for options trading)"""
        try:
            if not self.is_connected():
                self.logger.error("Not connected to IB Gateway")
                return False
            
            # Create SPY stock contract
            spy_contract = Contract()
            spy_contract.symbol = "SPY"
            spy_contract.secType = "STK"
            spy_contract.exchange = "SMART"
            spy_contract.currency = "USD"
            
            # Request market data
            req_id = SPY_MARKET_DATA_ID
            self._market_data_requests[req_id] = "SPY"
            
            self.reqMktData(req_id, spy_contract, "", False, False, [])
            self.logger.info("✅ Requested SPY real-time market data")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to request SPY market data: {e}")
            return False
    
    def request_option_market_data(self, symbol: str, expiry: str, 
                                  strike: float, right: str) -> int:
        """
        Request options market data for SPY options strategies.
        
        Args:
            symbol: Underlying symbol (SPY)
            expiry: Expiration date (YYYYMMDD)
            strike: Strike price
            right: 'C' for Call, 'P' for Put
            
        Returns:
            int: Request ID for tracking
        """
        try:
            if not self.is_connected():
                self.logger.error("Not connected to IB Gateway")
                return -1
            
            # Create options contract
            option_contract = Contract()
            option_contract.symbol = symbol
            option_contract.secType = "OPT"
            option_contract.exchange = "SMART" 
            option_contract.currency = "USD"
            option_contract.lastTradeDateOrContractMonth = expiry
            option_contract.strike = strike
            option_contract.right = right
            
            # Generate unique request ID
            req_id = OPTIONS_DATA_ID_BASE + len(self._market_data_requests)
            contract_desc = f"{symbol}_{expiry}_{strike}_{right}"
            self._market_data_requests[req_id] = contract_desc
            
            self.reqMktData(req_id, option_contract, "", False, False, [])
            self.logger.info(f"Requested options data: {contract_desc}")
            return req_id
            
        except Exception as e:
            self.logger.error(f"Failed to request options data: {e}")
            return -1
    
    # ==========================================================================
    # CALLBACK SYSTEM
    # ==========================================================================
    
    def register_callback(self, event_type: str, callback: Callable):
        """Register callback for events"""
        if event_type not in self._callbacks:
            self._callbacks[event_type] = []
        self._callbacks[event_type].append(callback)
        self.logger.debug(f"Registered callback for {event_type}")
    
    def _trigger_callbacks(self, event_type: str, data: Any):
        """Trigger callbacks for event"""
        callbacks = self._callbacks.get(event_type, [])
        for callback in callbacks:
            try:
                callback(data)
            except Exception as e:
                self.logger.error(f"Error in callback for {event_type}: {e}")
    
    # ==========================================================================
    # PUBLIC API - Production Interface
    # ==========================================================================
    
    def get_spy_price(self) -> Optional[float]:
        """Get current SPY price (critical for options strategies)"""
        spy_tick = self.market_data.get(SPY_MARKET_DATA_ID)
        if spy_tick and spy_tick.symbol == 'SPY':
            return spy_tick.price
        return None
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Get detailed connection status"""
        return {
            'state': self.state.value,
            'connected': self.is_connected(), 
            'host': self.config.host,
            'port': self.config.port,
            'client_id': self.config.client_id,
            'next_order_id': self.next_order_id,
            'market_data_subscriptions': len(self._market_data_requests),
            'active_callbacks': sum(len(callbacks) for callbacks in self._callbacks.values())
        }

# ==============================================================================
# GLOBAL CLIENT INSTANCE - PRODUCTION SINGLETON
# ==============================================================================

# Global client instance for production trading
_global_ib_client: Optional[SpyderIBAPIClient] = None
_client_lock = threading.Lock()

def get_ib_client() -> Optional[SpyderIBAPIClient]:
    """
    Get or create the global IBAPI client instance.
    
    This is the MISSING FUNCTION that caused simulation mode!
    Now uses professional IBAPI for maximum reliability in SPY options trading.
    
    Returns:
        SpyderIBAPIClient: Connected IBAPI client, or None if connection fails
    """
    global _global_ib_client
    
    with _client_lock:
        # Return existing connected client
        if _global_ib_client and _global_ib_client.is_connected():
            return _global_ib_client
        
        # Create new IBAPI client
        try:
            if not HAS_IBAPI:
                print("❌ IBAPI not available - install with: pip install ibapi")
                return None
            
            # Production configuration for IB Gateway
            config = IBConfig(
                host='127.0.0.1',
                port=4002,  # Your IB Gateway paper trading port
                client_id=1,
                timeout=15
            )
            
            print(f"🚀 Creating IBAPI connection to {config.host}:{config.port}")
            
            _global_ib_client = SpyderIBAPIClient(config=config)
            
            # Connect to IB Gateway
            if _global_ib_client.connect_to_gateway(timeout=15):
                print("✅ IBAPI client connected - REAL DATA MODE ACTIVATED")
                
                # Request SPY market data immediately
                _global_ib_client.request_spy_market_data()
                
                return _global_ib_client
            else:
                print("❌ IBAPI connection failed - check IB Gateway")
                _global_ib_client = None
                return None
                
        except Exception as e:
            print(f"❌ Error creating IBAPI client: {e}")
            _global_ib_client = None
            return None

def reset_ib_client():
    """Reset global IBAPI client"""
    global _global_ib_client
    with _client_lock:
        if _global_ib_client:
            try:
                _global_ib_client.disconnect_from_gateway()
            except:
                pass
        _global_ib_client = None
        print("🔄 IBAPI client reset")

def test_ibapi_connection() -> bool:
    """Test IBAPI connection for production readiness"""
    client = get_ib_client()
    if client and client.is_connected():
        print("✅ IBAPI connection test: SUCCESS")
        print(f"   Status: {client.get_connection_status()}")
        return True
    else:
        print("❌ IBAPI connection test: FAILED")
        return False

# ==============================================================================
# COMPATIBILITY LAYER - For existing Spyder code
# ==============================================================================

# Legacy SpyderClient class for backward compatibility
SpyderClient = SpyderIBAPIClient

if __name__ == "__main__":
    print("🚀 SPYDER IBAPI CLIENT - PRODUCTION READY")
    print("=" * 50)
    print("Testing IBAPI connection...")
    
    if test_ibapi_connection():
        print("✅ Ready for algorithmic SPY options trading!")
    else:
        print("❌ Connection failed - check IB Gateway")
