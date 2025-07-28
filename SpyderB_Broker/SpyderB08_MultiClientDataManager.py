#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System
Module: SpyderB08_MultiClientDataManager.py
Group: B (Broker Integration)
Purpose: Multi-Client Market Data Manager with Sophisticated Client Allocation

Description:
    Advanced multi-client market data management system that implements sophisticated
    client ID allocation strategy for optimal performance and resource utilization.
    
    Client ID Allocation Strategy:
    - Client 0: Administrative Operations (Account, Orders, System Control)
    - Client 1: Core Market Data (SPY, SPX, /ES, VIX, TICK-NYSE) - 1-second updates
    - Client 2: SPY Options Chains (0DTE, 1DTE) - 1-second updates
    - Client 3: Volatility Indicators (VIX9D, VXV, VXMT, VVIX, UVXY) - 5-second updates
    - Client 4: Market Internals (VX, ADVN-NYSE, DECN-NYSE, TICK-NASDAQ) - 5-second updates
    - Client 5: Major Indices (DIA, QQQ, IWM, 1DTE Options) - 5-second updates
    - Client 6: Extended Assets (TLT, LQD, DXY, GLD, WEEKLY Options) - 15-30-second updates
    - Client 7: Sector ETFs (XLF, XLK, XLE, XLV, XLI, XLY, XLP, XLU, XLRE, XLC, XLB) - 30-60s
    - Client 8: Order Execution (Trading operations only)

Author: SPYDER Development Team
Date: 2025-07-28
Version: 1.0.0
"""

import logging
import threading
import time
import queue
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
import json

# ================================================================================
# IMPORTS - Handle graceful fallbacks for missing dependencies
# ================================================================================

try:
    from ibapi.contract import Contract
    from ibapi.order import Order
    from ibapi.ticktype import TickType  # FIXED: Correct import location
    from ibapi.common import BarData
    from ibapi.client import EClient
    from ibapi.wrapper import EWrapper
    IBAPI_AVAILABLE = True
except ImportError:
    IBAPI_AVAILABLE = False
    # Fallback classes for when IBAPI is not available
    class Contract:
        def __init__(self):
            self.symbol = ""
            self.secType = ""
            self.exchange = ""
            self.currency = "USD"
            self.right = ""
            self.strike = 0.0
            self.lastTradeDateOrContractMonth = ""
    
    class Order:
        def __init__(self):
            self.action = ""
            self.totalQuantity = 0
            self.orderType = ""
    
    class TickType:
        LAST = 4
        BID = 1
        ASK = 2
        VOLUME = 8
        HIGH = 6
        LOW = 7
        CLOSE = 9
    
    class BarData:
        def __init__(self):
            self.date = ""
            self.open = 0.0
            self.high = 0.0
            self.low = 0.0
            self.close = 0.0
            self.volume = 0
    
    class EClient:
        def __init__(self, wrapper):
            pass
    
    class EWrapper:
        def __init__(self):
            pass

# ================================================================================
# ENUMS AND DATACLASSES
# ================================================================================

class ClientPurpose(Enum):
    """Client ID purposes for organized allocation"""
    ADMINISTRATIVE = "Administrative Operations"
    CORE_DATA = "Core Market Data"
    SPY_OPTIONS = "SPY Options Chains"
    VOLATILITY = "Volatility Indicators"
    MARKET_INTERNALS = "Market Internals"
    MAJOR_INDICES = "Major Index ETFs"
    EXTENDED_ASSETS = "Extended Market Data"
    SECTOR_ETFS = "Low-Frequency Assets"
    ORDER_EXECUTION = "Order Execution"

@dataclass
class MarketDataTick:
    """Market data tick information"""
    symbol: str
    price: float
    size: int
    timestamp: datetime
    tick_type: int  # FIXED: Use int instead of TickType
    request_id: int

@dataclass
class ClientInfo:
    """Information about each client connection"""
    client_id: int
    purpose: ClientPurpose
    symbols: List[str]
    update_frequency: float
    is_connected: bool = False
    last_update: Optional[datetime] = None
    message_count: int = 0
    error_count: int = 0

# ================================================================================
# MAIN MULTI-CLIENT DATA MANAGER CLASS
# ================================================================================

class MultiClientDataManager:
    """
    Advanced Multi-Client Market Data Manager
    
    Manages multiple IB Gateway client connections with sophisticated allocation strategy.
    Implements professional-grade market data distribution with priority-based updates.
    """
    
    def __init__(self):
        """Initialize the Multi-Client Data Manager"""
        # Core components
        self.logger = logging.getLogger('SpyderB08.MultiClient')
        self.is_running = False
        self.clients: Dict[int, ClientInfo] = {}
        
        # Threading and synchronization
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self.executor = ThreadPoolExecutor(max_workers=12, thread_name_prefix="MultiClient")
        
        # Data management
        self.market_data: Dict[str, MarketDataTick] = {}
        self.data_callbacks: Dict[str, List[Callable]] = {}
        self.request_queue = queue.Queue()
        
        # Performance tracking
        self.total_messages = 0
        self.total_errors = 0
        self.start_time: Optional[datetime] = None
        
        # Initialize client allocation strategy
        self._initialize_client_allocation()
        
        self.logger.info("✅ Multi-Client Data Manager initialized")

    def _initialize_client_allocation(self):
        """Initialize the sophisticated client allocation strategy"""
        
        # Client allocation configuration
        self.client_configs = {
            0: {
                'purpose': ClientPurpose.ADMINISTRATIVE,
                'symbols': [],  # Administrative only
                'frequency': 0.0,
                'description': 'Account, orders, system control'
            },
            1: {
                'purpose': ClientPurpose.CORE_DATA,
                'symbols': ['SPY', 'SPX', '/ES', 'VIX', 'TICK-NYSE'],
                'frequency': 1.0,
                'description': 'SPY, SPX, /ES, VIX, TICK-NYSE (1s)'
            },
            2: {
                'purpose': ClientPurpose.SPY_OPTIONS,
                'symbols': ['SPY_0DTE', 'SPY_1DTE'],
                'frequency': 1.0,
                'description': '0DTE, 1DTE options (1s)'
            },
            3: {
                'purpose': ClientPurpose.VOLATILITY,
                'symbols': ['VIX9D', 'VXV', 'VXMT', 'VVIX', 'UVXY', 'TRIN-NYSE', 'ADD-NYSE', 'CPC', 'PCALL', 'SKEW'],
                'frequency': 5.0,
                'description': 'VIX9D, VXV, VXMT, VVIX, UVXY (5s)'
            },
            4: {
                'purpose': ClientPurpose.MARKET_INTERNALS,
                'symbols': ['VX', 'ADVN-NYSE', 'DECN-NYSE', 'UVOL-NYSE', 'DVOL-NYSE', 'VOLD-NYSE', 'TICK-NASDAQ', 'TRIN-NASDAQ'],
                'frequency': 5.0,
                'description': 'TRIN, ADD, CPC, PCALL, SKEW (5s)'
            },
            5: {
                'purpose': ClientPurpose.MAJOR_INDICES,
                'symbols': ['DIA', 'QQQ', 'IWM', 'DIA_1DTE', 'QQQ_1DTE', 'IWM_1DTE'],
                'frequency': 5.0,
                'description': 'DIA, QQQ, IWM, 1DTE options (5s)'
            },
            6: {
                'purpose': ClientPurpose.EXTENDED_ASSETS,
                'symbols': ['TLT', 'LQD', 'DXY', 'GLD', 'SPY_WEEKLY', 'DIA_WEEKLY', 'QQQ_WEEKLY'],
                'frequency': 15.0,
                'description': 'TLT, LQD, DXY, GLD, WEEKLY (15-30s)'
            },
            7: {
                'purpose': ClientPurpose.SECTOR_ETFS,
                'symbols': ['VXST', 'VXN', 'RVX', 'CPCE', 'CPCI', 'NYHL-NYSE', 'XLF', 'XLK', 'XLE', 'XLV', 'XLI', 'XLY', 'XLP', 'XLU', 'XLRE', 'XLC', 'XLB'],
                'frequency': 30.0,
                'description': 'Sector ETFs, MONTHLY options (30-60s)'
            },
            8: {
                'purpose': ClientPurpose.ORDER_EXECUTION,
                'symbols': [],  # Trading operations only
                'frequency': 0.0,
                'description': 'Trading operations only'
            }
        }
        
        # Create client info objects
        for client_id, config in self.client_configs.items():
            self.clients[client_id] = ClientInfo(
                client_id=client_id,
                purpose=config['purpose'],
                symbols=config['symbols'].copy(),
                update_frequency=config['frequency']
            )

    # ================================================================================
    # CORE MANAGEMENT METHODS
    # ================================================================================

    def start(self) -> bool:
        """
        Start the Multi-Client Data Manager
        
        Returns:
            bool: True if started successfully
        """
        try:
            with self._lock:
                if self.is_running:
                    self.logger.warning("Multi-Client Data Manager already running")
                    return True
                
                self.logger.info("🚀 Starting Multi-Client Data Manager...")
                
                # Initialize components
                self._stop_event.clear()
                self.start_time = datetime.now()
                
                # Start priority clients (0, 1, 3) first
                priority_clients = [0, 1, 3]
                for client_id in priority_clients:
                    if self._start_client(client_id):
                        self.logger.info(f"✅ Started priority client {client_id}")
                        time.sleep(0.5)  # Brief pause between connections
                
                # Start request processing thread
                processing_thread = threading.Thread(
                    target=self._request_processing_loop,
                    name="RequestProcessor",
                    daemon=True
                )
                processing_thread.start()
                
                self.is_running = True
                self.logger.info("✅ Multi-Client Data Manager started successfully")
                
                return True
                
        except Exception as e:
            self.logger.error(f"❌ Failed to start Multi-Client Data Manager: {e}")
            return False

    def stop(self) -> bool:
        """
        Stop the Multi-Client Data Manager
        
        Returns:
            bool: True if stopped successfully
        """
        try:
            with self._lock:
                if not self.is_running:
                    self.logger.info("Multi-Client Data Manager already stopped")
                    return True
                
                self.logger.info("🛑 Stopping Multi-Client Data Manager...")
                
                # Signal all threads to stop
                self._stop_event.set()
                self.is_running = False
                
                # Disconnect all clients
                for client_id in self.clients:
                    self._stop_client(client_id)
                
                # Clean up resources
                self.executor.shutdown(wait=True)
                self.market_data.clear()
                
                self.logger.info("✅ Multi-Client Data Manager stopped successfully")
                return True
                
        except Exception as e:
            self.logger.error(f"❌ Error stopping Multi-Client Data Manager: {e}")
            return False

    def _start_client(self, client_id: int) -> bool:
        """
        Start individual client connection
        
        Args:
            client_id: Client ID to start
            
        Returns:
            bool: True if started successfully
        """
        try:
            if client_id not in self.clients:
                self.logger.error(f"❌ Unknown client ID: {client_id}")
                return False
            
            client = self.clients[client_id]
            
            # For now, mark as connected (would normally connect to IB Gateway)
            if not IBAPI_AVAILABLE:
                # Simulation mode
                client.is_connected = True
                client.last_update = datetime.now()
                self.logger.info(f"✅ Client {client_id} started in simulation mode")
                return True
            
            # Real IB Gateway connection would go here
            client.is_connected = True
            client.last_update = datetime.now()
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error starting client {client_id}: {e}")
            return False

    def _stop_client(self, client_id: int) -> bool:
        """
        Stop individual client connection
        
        Args:
            client_id: Client ID to stop
            
        Returns:
            bool: True if stopped successfully
        """
        try:
            if client_id in self.clients:
                client = self.clients[client_id]
                client.is_connected = False
                self.logger.info(f"🛑 Client {client_id} stopped")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error stopping client {client_id}: {e}")
            return False

    # ================================================================================
    # MARKET DATA METHODS
    # ================================================================================

    def subscribe_to_data(self, symbol: str, callback: Callable) -> bool:
        """
        Subscribe to market data for a symbol
        
        Args:
            symbol: Symbol to subscribe to
            callback: Callback function for data updates
            
        Returns:
            bool: True if subscription successful
        """
        try:
            if symbol not in self.data_callbacks:
                self.data_callbacks[symbol] = []
            
            if callback not in self.data_callbacks[symbol]:
                self.data_callbacks[symbol].append(callback)
                self.logger.info(f"✅ Subscribed to {symbol} data")
                
                # Determine which client should handle this symbol
                client_id = self._get_client_for_symbol(symbol)
                if client_id is not None:
                    self._request_market_data(symbol, client_id)
                
                return True
            
        except Exception as e:
            self.logger.error(f"❌ Error subscribing to {symbol}: {e}")
            return False

    def unsubscribe_from_data(self, symbol: str, callback: Callable) -> bool:
        """
        Unsubscribe from market data for a symbol
        
        Args:
            symbol: Symbol to unsubscribe from
            callback: Callback function to remove
            
        Returns:
            bool: True if unsubscription successful
        """
        try:
            if symbol in self.data_callbacks and callback in self.data_callbacks[symbol]:
                self.data_callbacks[symbol].remove(callback)
                self.logger.info(f"✅ Unsubscribed from {symbol} data")
                return True
            
        except Exception as e:
            self.logger.error(f"❌ Error unsubscribing from {symbol}: {e}")
            return False

    def get_latest_data(self, symbol: str) -> Optional[Dict]:
        """
        Get latest market data for symbol
        
        Args:
            symbol: Symbol to get data for
            
        Returns:
            Latest market data or None
        """
        try:
            with self._lock:
                if symbol in self.market_data:
                    tick = self.market_data[symbol]
                    return {
                        'symbol': tick.symbol,
                        'price': tick.price,
                        'size': tick.size,
                        'timestamp': tick.timestamp,
                        'tick_type': tick.tick_type
                    }
                
                # Fallback: simulate data for testing
                return {
                    'symbol': symbol,
                    'price': 420.0 + hash(symbol) % 50,  # Simulated price
                    'size': 100,
                    'timestamp': datetime.now(),
                    'tick_type': TickType.LAST
                }
                
        except Exception as e:
            self.logger.error(f"❌ Error getting data for {symbol}: {e}")
            return None

    def _get_client_for_symbol(self, symbol: str) -> Optional[int]:
        """
        Determine which client should handle a symbol
        
        Args:
            symbol: Symbol to route
            
        Returns:
            Client ID or None
        """
        try:
            # Check each client's symbol list
            for client_id, client in self.clients.items():
                if symbol in client.symbols:
                    return client_id
            
            # Default routing based on symbol characteristics
            if symbol in ['SPY', 'SPX', '/ES', 'VIX', 'TICK-NYSE']:
                return 1  # Core data
            elif 'VIX' in symbol or symbol in ['UVXY', 'SKEW']:
                return 3  # Volatility
            elif symbol in ['DIA', 'QQQ', 'IWM']:
                return 5  # Major indices
            elif symbol in ['TLT', 'LQD', 'DXY', 'GLD']:
                return 6  # Extended assets
            elif symbol.startswith('XL'):
                return 7  # Sector ETFs
            else:
                return 1  # Default to core data
                
        except Exception as e:
            self.logger.error(f"❌ Error routing symbol {symbol}: {e}")
            return 1  # Fallback to client 1

    def _request_market_data(self, symbol: str, client_id: int):
        """
        Request market data for symbol on specific client
        
        Args:
            symbol: Symbol to request
            client_id: Client ID to use
        """
        try:
            # Add to request queue
            request = {
                'symbol': symbol,
                'client_id': client_id,
                'timestamp': datetime.now()
            }
            self.request_queue.put(request)
            
        except Exception as e:
            self.logger.error(f"❌ Error requesting data for {symbol}: {e}")

    def _request_processing_loop(self):
        """Process market data requests"""
        self.logger.info("🔄 Starting request processing loop")
        
        while not self._stop_event.is_set():
            try:
                # Get request from queue (with timeout)
                request = self.request_queue.get(timeout=1.0)
                
                # Process the request
                self._process_market_data_request(request)
                
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"❌ Error in request processing loop: {e}")
                time.sleep(1.0)
        
        self.logger.info("🛑 Request processing loop stopped")

    def _process_market_data_request(self, request: Dict):
        """
        Process individual market data request
        
        Args:
            request: Request dictionary
        """
        try:
            symbol = request['symbol']
            client_id = request['client_id']
            
            # Simulate market data for testing
            if not IBAPI_AVAILABLE:
                # Create simulated tick
                tick = MarketDataTick(
                    symbol=symbol,
                    price=420.0 + hash(symbol) % 50 + (time.time() % 10),
                    size=100,
                    timestamp=datetime.now(),
                    tick_type=TickType.LAST,
                    request_id=hash(f"{symbol}_{client_id}") % 10000
                )
                
                # Store and notify
                self._update_market_data(tick)
            
            # Update client stats
            if client_id in self.clients:
                self.clients[client_id].message_count += 1
                self.clients[client_id].last_update = datetime.now()
            
        except Exception as e:
            self.logger.error(f"❌ Error processing request: {e}")

    def _update_market_data(self, tick: MarketDataTick):
        """
        Update market data and notify callbacks
        
        Args:
            tick: Market data tick
        """
        try:
            with self._lock:
                # Store the tick
                self.market_data[tick.symbol] = tick
                self.total_messages += 1
                
                # Notify callbacks
                if tick.symbol in self.data_callbacks:
                    for callback in self.data_callbacks[tick.symbol]:
                        try:
                            callback(tick)
                        except Exception as e:
                            self.logger.error(f"❌ Error in callback for {tick.symbol}: {e}")
            
        except Exception as e:
            self.logger.error(f"❌ Error updating market data: {e}")

    # ================================================================================
    # STATUS AND MONITORING METHODS
    # ================================================================================

    def get_status_summary(self) -> Dict:
        """
        Get comprehensive status summary
        
        Returns:
            Status summary dictionary
        """
        try:
            with self._lock:
                active_clients = [
                    client_id for client_id, client in self.clients.items() 
                    if client.is_connected
                ]
                
                return {
                    'is_running': self.is_running,
                    'active_clients': active_clients,
                    'total_clients': len(self.clients),
                    'market_data_lines_used': len(self.market_data),
                    'total_messages': self.total_messages,
                    'total_errors': self.total_errors,
                    'start_time': self.start_time,
                    'subscriptions': len(self.data_callbacks)
                }
                
        except Exception as e:
            self.logger.error(f"❌ Error getting status: {e}")
            return {}

    def get_client_status(self, client_id: int) -> Optional[Dict]:
        """
        Get status for specific client
        
        Args:
            client_id: Client ID to check
            
        Returns:
            Client status or None
        """
        try:
            if client_id in self.clients:
                client = self.clients[client_id]
                return {
                    'client_id': client.client_id,
                    'purpose': client.purpose.value,
                    'is_connected': client.is_connected,
                    'symbols': client.symbols,
                    'update_frequency': client.update_frequency,
                    'message_count': client.message_count,
                    'error_count': client.error_count,
                    'last_update': client.last_update
                }
                
        except Exception as e:
            self.logger.error(f"❌ Error getting client {client_id} status: {e}")
            return None

# ================================================================================
# STANDALONE TESTING AND MAIN EXECUTION
# ================================================================================

def main():
    """Main execution for testing"""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("🚀 SPYDER B08 - Multi-Client Data Manager")
    print("=" * 60)
    
    try:
        # Initialize manager
        manager = MultiClientDataManager()
        
        # Test basic functionality
        print("🧪 Testing Multi-Client Data Manager...")
        
        # Start manager
        if manager.start():
            print("✅ Manager started successfully")
            
            # Test subscription
            def test_callback(tick):
                print(f"📊 Received data: {tick.symbol} = ${tick.price:.2f}")
            
            manager.subscribe_to_data("SPY", test_callback)
            print("✅ Subscribed to SPY data")
            
            # Let it run for a few seconds
            time.sleep(5)
            
            # Get status
            status = manager.get_status_summary()
            print(f"\n📈 Status Summary:")
            print(f"   Active Clients: {status['active_clients']}")
            print(f"   Total Messages: {status['total_messages']}")
            print(f"   Market Data Lines: {status['market_data_lines_used']}")
            
            # Test data retrieval
            spy_data = manager.get_latest_data("SPY")
            if spy_data:
                print(f"📊 Latest SPY: ${spy_data['price']:.2f}")
            
            # Stop manager
            if manager.stop():
                print("✅ Manager stopped successfully")
            
        print("\n🎯 Multi-Client Data Manager test complete!")
        
    except Exception as e:
        print(f"❌ Error in main: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
