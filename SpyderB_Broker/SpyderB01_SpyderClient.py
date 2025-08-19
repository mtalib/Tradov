#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB01_SpyderClient.py
Purpose: Enhanced SpyderClient with market data type support and fixed data handling
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-19 Time: 15:30:00  

Module Description:
    Enhanced SpyderClient that properly supports different market data types 
    (FROZEN/DELAYED) based on account permissions. Includes automatic detection
    of working data types, proper error handling, and integration with the fixed
    MarketDataManager. Resolves the NaN data issue by using appropriate data types.

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
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    from ib_insync import IB, Stock, Option, Future, Index, Contract, Ticker
    from ib_insync import MarketOrder, LimitOrder, OrderStatus
    IB_INSYNC_AVAILABLE = True
except ImportError:
    print("⚠️ ib_insync not available - running in simulation mode")
    IB_INSYNC_AVAILABLE = False
    # Mock classes for testing
    class IB:
        def connect(self, *args, **kwargs): return False
        def disconnect(self): pass
        def isConnected(self): return False
    class Stock: pass
    class Ticker: pass

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
MARKET_DATA_TYPE_DELAYED_FROZEN = 4 # ✅ Works! Delayed + frozen fallback

# Default configuration based on test results
DEFAULT_MARKET_DATA_TYPE = MARKET_DATA_TYPE_FROZEN
FALLBACK_DATA_TYPES = [MARKET_DATA_TYPE_FROZEN, MARKET_DATA_TYPE_DELAYED, MARKET_DATA_TYPE_DELAYED_FROZEN]

# Connection defaults
DEFAULT_HOST = '127.0.0.1'
DEFAULT_PAPER_PORT = 4002
DEFAULT_LIVE_PORT = 4001
DEFAULT_CLIENT_ID = 44  # Use working client ID from tests

# Timeouts and retries
CONNECTION_TIMEOUT = 10
MAX_CONNECTION_RETRIES = 3
DATA_VALIDATION_TIMEOUT = 5

# IB Gateway limits
IB_MARKET_DATA_LINES = 100  # Max concurrent market data subscriptions

# ==============================================================================
# ENUMS AND DATA CLASSES
# ==============================================================================
class MarketDataType(Enum):
    """Market data type options with test results"""
    REALTIME = MARKET_DATA_TYPE_REALTIME          # Type 1 - Requires permissions  
    FROZEN = MARKET_DATA_TYPE_FROZEN              # Type 2 - ✅ WORKS
    DELAYED = MARKET_DATA_TYPE_DELAYED            # Type 3 - ✅ WORKS
    DELAYED_FROZEN = MARKET_DATA_TYPE_DELAYED_FROZEN  # Type 4 - ✅ WORKS

class ConnectionStatus(Enum):
    """Connection status enumeration"""
    DISCONNECTED = auto()
    CONNECTING = auto() 
    CONNECTED = auto()
    ERROR = auto()

@dataclass
class IBConfig:
    """Interactive Brokers configuration"""
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PAPER_PORT
    client_id: int = DEFAULT_CLIENT_ID
    account: str = ""
    timeout: int = CONNECTION_TIMEOUT
    readonly: bool = True
    
    @classmethod
    def paper_trading(cls, client_id: int = DEFAULT_CLIENT_ID) -> 'IBConfig':
        """Create configuration for paper trading"""
        return cls(
            host=DEFAULT_HOST,
            port=DEFAULT_PAPER_PORT,
            client_id=client_id,
            readonly=False
        )
    
    @classmethod 
    def live_trading(cls, client_id: int = DEFAULT_CLIENT_ID) -> 'IBConfig':
        """Create configuration for live trading"""
        return cls(
            host=DEFAULT_HOST,
            port=DEFAULT_LIVE_PORT,
            client_id=client_id,
            readonly=False
        )

@dataclass
class MarketDataCapabilities:
    """Market data capabilities for the account"""
    realtime_available: bool = False
    frozen_available: bool = False
    delayed_available: bool = False
    delayed_frozen_available: bool = False
    preferred_type: Optional[MarketDataType] = None
    last_tested: Optional[datetime] = None

# ==============================================================================
# ENHANCED SPYDER CLIENT CLASS
# ==============================================================================
class SpyderClient:
    """
    Enhanced SpyderClient with Market Data Type Support
    
    🔧 ENHANCEMENTS APPLIED:
    - Automatic detection of working market data types  
    - Support for FROZEN/DELAYED data types that work with paper accounts
    - Proper error handling for data permissions
    - Integration with fixed MarketDataManager
    - Fallback mechanisms for different data types
    - Account capability detection
    """
    
    def __init__(self, config: IBConfig, event_manager: Optional[Any] = None):
        """
        Initialize enhanced SpyderClient.
        
        Args:
            config: IB configuration
            event_manager: Optional event manager
        """
        self.config = config
        self.event_manager = event_manager
        
        # Logging and error handling
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # IB components
        self.ib: Optional[IB] = None
        self.status = ConnectionStatus.DISCONNECTED
        
        # Market data management
        self.market_data: Dict[int, Contract] = {}  # req_id -> contract
        self.tickers: Dict[int, Ticker] = {}        # req_id -> ticker
        self.next_req_id = 1000
        
        # 🔧 NEW: Market data type management
        self.current_data_type = MarketDataType.FROZEN  # Start with known working type
        self.data_capabilities = MarketDataCapabilities()
        self.capabilities_tested = False
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Connection tracking
        self.connection_attempts = 0
        self.last_connection_time: Optional[datetime] = None
        
        self.logger.info(f"SpyderClient initialized with client_id={config.client_id}")
    
    # ==========================================================================
    # CONNECTION METHODS
    # ==========================================================================
    def connect(self) -> bool:
        """
        Connect to IB Gateway with enhanced error handling.
        
        Returns:
            bool: True if connected successfully
        """
        if not IB_INSYNC_AVAILABLE:
            self.logger.error("❌ ib_insync not available")
            return False
            
        try:
            self.logger.info(f"🔗 Connecting to IB Gateway at {self.config.host}:{self.config.port}")
            self.status = ConnectionStatus.CONNECTING
            
            # Create IB instance
            self.ib = IB()
            
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
                        
                        # 🔧 NEW: Initialize market data type
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
            if not self.is_connected():
                self.logger.info("Already disconnected")
                return True
                
            self.logger.info("🔌 Disconnecting from IB Gateway...")
            
            # Cancel all market data subscriptions
            self._cancel_all_market_data()
            
            # Disconnect
            if self.ib:
                self.ib.disconnect()
                
            self.status = ConnectionStatus.DISCONNECTED
            self.logger.info("✅ Disconnected from IB Gateway")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Disconnect error: {e}")
            return False
    
    def is_connected(self) -> bool:
        """
        Check if connected to IB Gateway.
        
        Returns:
            bool: True if connected
        """
        return self.ib and self.ib.isConnected()
    
    # ==========================================================================
    # 🔧 NEW: MARKET DATA TYPE MANAGEMENT
    # ==========================================================================
    def _initialize_market_data_type(self) -> None:
        """Initialize market data type based on account capabilities."""
        try:
            if not self.capabilities_tested:
                self.logger.info("🧪 Testing market data capabilities...")
                self._test_market_data_capabilities()
            
            # Set the preferred data type
            if self.data_capabilities.preferred_type:
                self._set_market_data_type(self.data_capabilities.preferred_type)
            else:
                # Use default FROZEN type
                self._set_market_data_type(MarketDataType.FROZEN)
                
        except Exception as e:
            self.logger.error(f"❌ Error initializing market data type: {e}")
            # Fallback to FROZEN
            self._set_market_data_type(MarketDataType.FROZEN)
    
    def _test_market_data_capabilities(self) -> None:
        """Test which market data types work with this account."""
        try:
            self.logger.info("📊 Testing market data type capabilities...")
            
            # Test each data type
            for data_type in MarketDataType:
                self.logger.info(f"Testing {data_type.name} (Type {data_type.value})...")
                
                if self._test_data_type(data_type):
                    self.logger.info(f"✅ {data_type.name} works!")
                    
                    # Set capability flags
                    if data_type == MarketDataType.REALTIME:
                        self.data_capabilities.realtime_available = True
                    elif data_type == MarketDataType.FROZEN:
                        self.data_capabilities.frozen_available = True
                    elif data_type == MarketDataType.DELAYED:
                        self.data_capabilities.delayed_available = True
                    elif data_type == MarketDataType.DELAYED_FROZEN:
                        self.data_capabilities.delayed_frozen_available = True
                    
                    # Set as preferred if not already set (prioritize real-time, then frozen)
                    if not self.data_capabilities.preferred_type:
                        self.data_capabilities.preferred_type = data_type
                        
                else:
                    self.logger.warning(f"❌ {data_type.name} does not work")
            
            self.capabilities_tested = True
            self.data_capabilities.last_tested = datetime.now()
            
            # Log summary
            preferred = self.data_capabilities.preferred_type
            if preferred:
                self.logger.info(f"🎯 Preferred data type: {preferred.name}")
            else:
                self.logger.warning("⚠️ No working data types found!")
                
        except Exception as e:
            self.logger.error(f"❌ Error testing capabilities: {e}")
    
    def _test_data_type(self, data_type: MarketDataType) -> bool:
        """
        Test if a specific data type returns valid data.
        
        Args:
            data_type: Market data type to test
            
        Returns:
            bool: True if data type works
        """
        try:
            # Set the data type
            self.ib.reqMarketDataType(data_type.value)
            time.sleep(1)  # Wait for setting to take effect
            
            # Create test contract (SPY)
            spy_contract = Stock('SPY', 'SMART', 'USD')
            
            # Request test data
            ticker = self.ib.reqMktData(spy_contract, '', False, False)
            time.sleep(DATA_VALIDATION_TIMEOUT)  # Wait for data
            
            # Check if we got valid data (not NaN)
            has_valid_data = (
                (ticker.last and not math.isnan(ticker.last)) or
                (ticker.bid and not math.isnan(ticker.bid)) or  
                (ticker.ask and not math.isnan(ticker.ask))
            )
            
            # Cancel test subscription
            self.ib.cancelMktData(spy_contract)
            
            if has_valid_data:
                self.logger.info(f"✅ {data_type.name}: SPY Last=${ticker.last}")
                return True
            else:
                self.logger.warning(f"❌ {data_type.name}: All values NaN")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error testing {data_type.name}: {e}")
            return False
    
    def set_market_data_type(self, data_type: MarketDataType) -> bool:
        """
        Set the market data type.
        
        Args:
            data_type: Market data type to set
            
        Returns:
            bool: True if set successfully
        """
        return self._set_market_data_type(data_type)
    
    def _set_market_data_type(self, data_type: MarketDataType) -> bool:
        """
        Internal method to set market data type.
        
        Args:
            data_type: Market data type to set
            
        Returns:
            bool: True if set successfully
        """
        try:
            if not self.is_connected():
                self.logger.error("❌ Not connected to IB Gateway")
                return False
                
            self.logger.info(f"📡 Setting market data type to {data_type.name} (Type {data_type.value})")
            
            # Call IB's reqMarketDataType
            self.ib.reqMarketDataType(data_type.value)
            time.sleep(1)  # Wait for setting to take effect
            
            self.current_data_type = data_type
            self.logger.info(f"✅ Market data type set to {data_type.name}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to set market data type {data_type.name}: {e}")
            return False
    
    def get_current_data_type(self) -> MarketDataType:
        """
        Get the current market data type.
        
        Returns:
            MarketDataType: Current data type
        """
        return self.current_data_type
    
    def get_data_capabilities(self) -> MarketDataCapabilities:
        """
        Get the account's market data capabilities.
        
        Returns:
            MarketDataCapabilities: Account capabilities
        """
        return self.data_capabilities
    
    # ==========================================================================
    # MARKET DATA METHODS (Enhanced)
    # ==========================================================================
    def request_market_data(self, contract: Contract, tick_types: str = '',
                          snapshot: bool = False) -> int:
        """
        Request market data with enhanced handling.
        
        Args:
            contract: IB contract
            tick_types: Specific tick types (empty for all)
            snapshot: Request snapshot instead of streaming
            
        Returns:
            int: Request ID, -1 if failed
        """
        if not self.is_connected():
            self.logger.error("❌ Not connected to IB Gateway")
            return -1
        
        try:
            # Check market data lines limit
            if len(self.market_data) >= IB_MARKET_DATA_LINES:
                self.logger.warning(f"⚠️ Market data lines limit reached ({IB_MARKET_DATA_LINES})")
                return -1
            
            # Request market data
            ticker = self.ib.reqMktData(contract, tick_types, snapshot)
            req_id = ticker.reqId
            
            # Store references
            with self._lock:
                self.market_data[req_id] = contract
                self.tickers[req_id] = ticker
            
            self.logger.debug(f"📊 Market data requested for {contract.symbol} (ID: {req_id})")
            return req_id
            
        except Exception as e:
            self.logger.error(f"❌ Market data request failed for {contract.symbol}: {e}")
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
                    contract = self.market_data.get(req_id)
                    symbol = contract.symbol if contract else req_id
                    
                    self.ib.cancelMktData(self.tickers[req_id])
                    del self.market_data[req_id]
                    del self.tickers[req_id]
                    
                    self.logger.debug(f"📊 Market data cancelled for {symbol}")
                    return True
            return False
            
        except Exception as e:
            self.logger.error(f"❌ Failed to cancel market data {req_id}: {e}")
            return False
    
    def get_market_data(self, req_id: int) -> Optional[Ticker]:
        """
        Get current market data for a request.
        
        Args:
            req_id: Request ID
            
        Returns:
            Ticker: Market data ticker or None
        """
        with self._lock:
            return self.tickers.get(req_id)
    
    def _cancel_all_market_data(self) -> None:
        """Cancel all active market data subscriptions."""
        try:
            with self._lock:
                req_ids = list(self.tickers.keys())
                
            for req_id in req_ids:
                self.cancel_market_data(req_id)
                
            self.logger.info(f"📊 Cancelled {len(req_ids)} market data subscriptions")
            
        except Exception as e:
            self.logger.error(f"❌ Error cancelling market data: {e}")
    
    # ==========================================================================
    # CONTRACT CREATION METHODS
    # ==========================================================================
    def create_stock_contract(self, symbol: str, exchange: str = 'SMART', 
                            currency: str = 'USD') -> Stock:
        """
        Create stock contract.
        
        Args:
            symbol: Stock symbol
            exchange: Exchange (default: SMART)
            currency: Currency (default: USD)
            
        Returns:
            Stock: IB stock contract
        """
        return Stock(symbol, exchange, currency)
    
    def create_option_contract(self, symbol: str, expiry: str, strike: float,
                             option_type: str, exchange: str = 'SMART',
                             currency: str = 'USD') -> Option:
        """
        Create option contract.
        
        Args:
            symbol: Underlying symbol
            expiry: Expiration date (YYYYMMDD)
            strike: Strike price
            option_type: 'C' for call, 'P' for put
            exchange: Exchange (default: SMART)
            currency: Currency (default: USD)
            
        Returns:
            Option: IB option contract
        """
        return Option(
            symbol=symbol,
            lastTradeDateOrContractMonth=expiry,
            strike=strike,
            right=option_type,
            exchange=exchange,
            currency=currency
        )
    
    def create_future_contract(self, symbol: str, exchange: str = 'CME',
                             currency: str = 'USD') -> Future:
        """
        Create future contract.
        
        Args:
            symbol: Future symbol
            exchange: Exchange (default: CME)
            currency: Currency (default: USD)
            
        Returns:
            Future: IB future contract
        """
        return Future(symbol, exchange, currency)
    
    # ==========================================================================
    # ACCOUNT METHODS
    # ==========================================================================
    def get_account_info(self) -> Dict[str, Any]:
        """
        Get account information.
        
        Returns:
            Dict: Account information
        """
        try:
            if not self.is_connected():
                return {}
            
            accounts = self.ib.managedAccounts()
            if not accounts:
                return {}
            
            account = accounts[0]
            summary = self.ib.accountSummary(account)
            
            account_info = {'account': account}
            for item in summary:
                account_info[item.tag] = item.value
                
            account_info['timestamp'] = datetime.now()
            return account_info
            
        except Exception as e:
            self.logger.error(f"❌ Error getting account info: {e}")
            return {}
    
    def get_positions(self) -> List[Any]:
        """
        Get current positions.
        
        Returns:
            List: Current positions
        """
        try:
            if not self.is_connected():
                return []
            
            return self.ib.positions()
            
        except Exception as e:
            self.logger.error(f"❌ Error getting positions: {e}")
            return []
    
    # ==========================================================================
    # STATUS AND DIAGNOSTICS
    # ==========================================================================
    def get_status(self) -> Dict[str, Any]:
        """
        Get client status and diagnostics.
        
        Returns:
            Dict: Status information
        """
        return {
            'status': self.status.name,
            'connected': self.is_connected(),
            'host': self.config.host,
            'port': self.config.port,
            'client_id': self.config.client_id,
            'current_data_type': self.current_data_type.name,
            'market_data_subscriptions': len(self.market_data),
            'connection_attempts': self.connection_attempts,
            'last_connection': self.last_connection_time.isoformat() if self.last_connection_time else None,
            'capabilities_tested': self.capabilities_tested,
            'data_capabilities': {
                'realtime': self.data_capabilities.realtime_available,
                'frozen': self.data_capabilities.frozen_available,
                'delayed': self.data_capabilities.delayed_available,
                'delayed_frozen': self.data_capabilities.delayed_frozen_available,
                'preferred': self.data_capabilities.preferred_type.name if self.data_capabilities.preferred_type else None
            }
        }
    
    # ==========================================================================
    # DIAGNOSTIC METHODS
    # ==========================================================================
    def test_connection(self) -> bool:
        """
        Test connection and capabilities.
        
        Returns:
            bool: True if test successful
        """
        try:
            if not self.is_connected():
                self.logger.error("❌ Not connected")
                return False
            
            # Test account access
            accounts = self.ib.managedAccounts()
            if not accounts:
                self.logger.error("❌ No managed accounts")
                return False
            
            # Test market data capabilities if not already tested
            if not self.capabilities_tested:
                self._test_market_data_capabilities()
            
            self.logger.info("✅ Connection test passed")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Connection test failed: {e}")
            return False

# ==============================================================================
# GLOBAL CLIENT INSTANCE (Singleton Pattern)
# ==============================================================================
_client_instance: Optional[SpyderClient] = None
_client_lock = threading.Lock()

def get_spyder_client(config: Optional[IBConfig] = None, 
                     event_manager: Optional[Any] = None) -> SpyderClient:
    """
    Get or create the SpyderClient singleton instance.
    
    Args:
        config: IB configuration (required on first call)
        event_manager: Event manager (optional)
        
    Returns:
        SpyderClient instance
    """
    global _client_instance
    
    with _client_lock:
        if _client_instance is None:
            if config is None:
                config = IBConfig.paper_trading()  # Default to paper trading
            _client_instance = SpyderClient(config, event_manager)
        return _client_instance

def reset_spyder_client() -> None:
    """Reset the singleton client (for testing)."""
    global _client_instance
    with _client_lock:
        if _client_instance and _client_instance.is_connected():
            _client_instance.disconnect()
        _client_instance = None

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Test the enhanced SpyderClient
    import sys
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    print("🚀 Testing Enhanced SpyderClient")
    print("=" * 50)
    
    try:
        # Create client with working configuration
        config = IBConfig.paper_trading(client_id=44)  # Use working client ID
        client = SpyderClient(config)
        
        # Connect
        if client.connect():
            print("✅ Connected to Interactive Brokers")
            
            # Get status
            status = client.get_status()
            print(f"\n📊 Client Status:")
            print(f"   Status: {status['status']}")
            print(f"   Data Type: {status['current_data_type']}")
            print(f"   Subscriptions: {status['market_data_subscriptions']}")
            
            # Show capabilities
            caps = status['data_capabilities']
            print(f"\n🧪 Data Capabilities:")
            print(f"   Real-time: {caps['realtime']}")
            print(f"   Frozen: {caps['frozen']}")
            print(f"   Delayed: {caps['delayed']}")
            print(f"   Preferred: {caps['preferred']}")
            
            # Test market data request
            print(f"\n📈 Testing Market Data Request:")
            spy_contract = client.create_stock_contract('SPY')
            req_id = client.request_market_data(spy_contract)
            
            if req_id > 0:
                print(f"✅ Market data requested for SPY (ID: {req_id})")
                
                # Wait for data
                time.sleep(3)
                
                # Get ticker
                ticker = client.get_market_data(req_id)
                if ticker:
                    print(f"📊 SPY Data: Last=${ticker.last}, Bid=${ticker.bid}, Ask=${ticker.ask}")
                else:
                    print("❌ No ticker data available")
                
                # Cancel market data
                client.cancel_market_data(req_id)
                print("✅ Market data cancelled")
            else:
                print("❌ Failed to request market data")
            
            # Disconnect
            client.disconnect()
            print("\n✅ Disconnected successfully")
            
        else:
            print("❌ Failed to connect to Interactive Brokers")
            
    except Exception as e:
        print(f"❌ Error testing client: {e}")
        import traceback
        traceback.print_exc()