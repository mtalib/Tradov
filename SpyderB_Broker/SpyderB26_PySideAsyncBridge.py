#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB26_PySideAsyncBridge.py
Purpose: PySide6 QtAsyncio integration for stable IB Gateway connectivity
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-01-22 Time: 10:45:00

Module Description:
    Advanced asynchronous bridge for Interactive Brokers Gateway using PySide6's
    native QtAsyncio integration. This module provides robust connection management,
    automatic reconnection, proper timeout handling, and seamless integration with
    Qt's event loop. Designed to eliminate timeout errors and connection instability
    issues experienced with traditional threading approaches.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Callable, Tuple
from enum import Enum
import json
from pathlib import Path

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    from PySide6.QtCore import QObject, Signal, QTimer, Qt
    from PySide6.QtAsyncio import QAsyncioEventLoopPolicy, QAsyncioEventLoop
    PYSIDE6_AVAILABLE = True
except ImportError:
    print("❌ PySide6 not installed. Please install: pip install PySide6")
    PYSIDE6_AVAILABLE = False

try:
    from ib_async import IB, Contract, Order, MarketOrder, LimitOrder, util
    from ib_async import IB as IBAsync
    IB_ASYNC_AVAILABLE = True
except ImportError:
    print("❌ ib_async not installed. Please install: pip install ib_async")
    IB_ASYNC_AVAILABLE = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
class ConnectionState(Enum):
    """Connection state enumeration"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"

# Configuration
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PAPER_PORT = 4002
DEFAULT_LIVE_PORT = 4001
CONNECTION_TIMEOUT = 10.0
HEARTBEAT_INTERVAL = 5.0
RECONNECT_DELAY = 5.0
MAX_RECONNECT_ATTEMPTS = 10

# ==============================================================================
# ASYNC IB GATEWAY BRIDGE
# ==============================================================================
class AsyncIBGatewayBridge(QObject):
    """
    PySide6 QtAsyncio-based bridge for IB Gateway connection.
    Provides stable, async connection management with automatic recovery.
    """
    
    # Qt Signals for event notification
    connected = Signal()
    disconnected = Signal()
    connection_lost = Signal()
    error_occurred = Signal(str)
    market_data_received = Signal(dict)
    order_status_changed = Signal(dict)
    position_updated = Signal(dict)
    account_updated = Signal(dict)
    
    def __init__(self, paper_trading: bool = True):
        """
        Initialize the async IB Gateway bridge.
        
        Args:
            paper_trading: If True, connect to paper trading port
        """
        super().__init__()
        
        # Setup logging
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Connection configuration
        self.paper_trading = paper_trading
        self.host = DEFAULT_HOST
        self.port = DEFAULT_PAPER_PORT if paper_trading else DEFAULT_LIVE_PORT
        
        # IB client
        self.ib: Optional[IBAsync] = None
        self.loop: Optional[QAsyncioEventLoop] = None
        
        # Connection state
        self.state = ConnectionState.DISCONNECTED
        self.reconnect_attempts = 0
        self.last_heartbeat = datetime.now()
        
        # Tasks and timers
        self.connection_task: Optional[asyncio.Task] = None
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.reconnect_task: Optional[asyncio.Task] = None
        
        # Data storage
        self.subscriptions: Dict[int, Contract] = {}
        self.active_orders: Dict[int, Order] = {}
        self.positions: Dict[str, Dict] = {}
        self.account_values: Dict[str, Any] = {}
        
        # Performance metrics
        self.metrics = {
            'connection_time': 0,
            'messages_received': 0,
            'errors_count': 0,
            'reconnect_count': 0,
            'last_error': None
        }
        
        self.logger.info(f"✅ AsyncIBGatewayBridge initialized for {'PAPER' if paper_trading else 'LIVE'} trading")
    
    # ==========================================================================
    # INITIALIZATION
    # ==========================================================================
    def initialize_async_loop(self) -> bool:
        """
        Initialize the Qt asyncio event loop.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if not PYSIDE6_AVAILABLE:
                self.logger.error("❌ PySide6 not available")
                return False
            
            # Set Qt asyncio event loop policy
            asyncio.set_event_loop_policy(QAsyncioEventLoopPolicy())
            
            # Get or create event loop
            try:
                self.loop = asyncio.get_event_loop()
            except RuntimeError:
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)
            
            self.logger.info("✅ Qt asyncio event loop initialized")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize async loop: {e}")
            return False
    
    # ==========================================================================
    # CONNECTION MANAGEMENT
    # ==========================================================================
    async def connect_async(self, client_id: int = 1) -> bool:
        """
        Establish async connection to IB Gateway.
        
        Args:
            client_id: Unique client identifier
            
        Returns:
            True if connected successfully
        """
        try:
            self.state = ConnectionState.CONNECTING
            self.logger.info(f"🔄 Connecting to IB Gateway at {self.host}:{self.port}")
            
            # Create IB client instance
            if not self.ib:
                self.ib = IB()
                self._setup_event_handlers()
            
            # Connect with timeout
            start_time = datetime.now()
            await asyncio.wait_for(
                self.ib.connectAsync(
                    host=self.host,
                    port=self.port,
                    clientId=client_id,
                    timeout=CONNECTION_TIMEOUT
                ),
                timeout=CONNECTION_TIMEOUT
            )
            
            # Calculate connection time
            connection_time = (datetime.now() - start_time).total_seconds()
            self.metrics['connection_time'] = connection_time
            
            # Update state
            self.state = ConnectionState.CONNECTED
            self.reconnect_attempts = 0
            self.last_heartbeat = datetime.now()
            
            # Start heartbeat
            await self._start_heartbeat()
            
            # Emit connected signal
            self.connected.emit()
            
            self.logger.info(f"✅ Connected to IB Gateway in {connection_time:.2f}s")
            self.logger.info(f"   Server Version: {self.ib.serverVersion()}")
            self.logger.info(f"   Connection Time: {self.ib.connectionTime()}")
            
            return True
            
        except asyncio.TimeoutError:
            self.state = ConnectionState.ERROR
            self.metrics['errors_count'] += 1
            self.logger.error(f"⏱️ Connection timeout after {CONNECTION_TIMEOUT}s")
            self.error_occurred.emit("Connection timeout")
            await self._schedule_reconnect()
            return False
            
        except Exception as e:
            self.state = ConnectionState.ERROR
            self.metrics['errors_count'] += 1
            self.metrics['last_error'] = str(e)
            self.logger.error(f"❌ Connection failed: {e}")
            self.error_occurred.emit(str(e))
            await self._schedule_reconnect()
            return False
    
    async def disconnect_async(self) -> bool:
        """
        Gracefully disconnect from IB Gateway.
        
        Returns:
            True if disconnected successfully
        """
        try:
            self.logger.info("🔄 Disconnecting from IB Gateway...")
            
            # Cancel active tasks
            if self.heartbeat_task:
                self.heartbeat_task.cancel()
                self.heartbeat_task = None
            
            if self.reconnect_task:
                self.reconnect_task.cancel()
                self.reconnect_task = None
            
            # Disconnect IB client
            if self.ib and self.ib.isConnected():
                self.ib.disconnect()
            
            self.state = ConnectionState.DISCONNECTED
            self.disconnected.emit()
            
            self.logger.info("✅ Disconnected from IB Gateway")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error during disconnect: {e}")
            return False
    
    # ==========================================================================
    # RECONNECTION LOGIC
    # ==========================================================================
    async def _schedule_reconnect(self):
        """Schedule automatic reconnection attempt"""
        if self.reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
            self.logger.error(f"❌ Max reconnection attempts ({MAX_RECONNECT_ATTEMPTS}) reached")
            self.state = ConnectionState.ERROR
            return
        
        self.reconnect_attempts += 1
        self.state = ConnectionState.RECONNECTING
        
        self.logger.info(f"⏳ Scheduling reconnection attempt {self.reconnect_attempts}/{MAX_RECONNECT_ATTEMPTS} in {RECONNECT_DELAY}s")
        
        await asyncio.sleep(RECONNECT_DELAY)
        
        # Attempt reconnection
        success = await self.connect_async()
        if not success and self.reconnect_attempts < MAX_RECONNECT_ATTEMPTS:
            await self._schedule_reconnect()
    
    # ==========================================================================
    # HEARTBEAT MONITORING
    # ==========================================================================
    async def _start_heartbeat(self):
        """Start heartbeat monitoring task"""
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
        
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
    
    async def _heartbeat_loop(self):
        """Heartbeat monitoring loop"""
        while self.state == ConnectionState.CONNECTED:
            try:
                # Request current time from IB
                server_time = self.ib.reqCurrentTime()
                self.last_heartbeat = datetime.now()
                
                # Check connection health
                if not self.ib.isConnected():
                    self.logger.warning("⚠️ Connection lost during heartbeat")
                    self.connection_lost.emit()
                    await self._handle_connection_lost()
                    break
                
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"❌ Heartbeat error: {e}")
                await self._handle_connection_lost()
                break
    
    async def _handle_connection_lost(self):
        """Handle lost connection"""
        self.state = ConnectionState.DISCONNECTED
        self.connection_lost.emit()
        
        # Clear subscriptions
        self.subscriptions.clear()
        
        # Schedule reconnection
        await self._schedule_reconnect()
    
    # ==========================================================================
    # EVENT HANDLERS
    # ==========================================================================
    def _setup_event_handlers(self):
        """Setup IB event handlers"""
        if not self.ib:
            return
        
        # Connection events
        self.ib.connectedEvent += self._on_connected
        self.ib.disconnectedEvent += self._on_disconnected
        
        # Market data events
        self.ib.pendingTickersEvent += self._on_pending_tickers
        
        # Order events
        self.ib.orderStatusEvent += self._on_order_status
        self.ib.openOrderEvent += self._on_open_order
        
        # Position events
        self.ib.positionEvent += self._on_position
        
        # Account events
        self.ib.accountValueEvent += self._on_account_value
        
        # Error events
        self.ib.errorEvent += self._on_error
    
    def _on_connected(self):
        """Handle connected event"""
        self.logger.info("📡 Connected event received")
        self.metrics['messages_received'] += 1
    
    def _on_disconnected(self):
        """Handle disconnected event"""
        self.logger.warning("📡 Disconnected event received")
        asyncio.create_task(self._handle_connection_lost())
    
    def _on_pending_tickers(self, tickers):
        """Handle pending tickers event"""
        for ticker in tickers:
            data = {
                'symbol': ticker.contract.symbol,
                'bid': ticker.bid,
                'ask': ticker.ask,
                'last': ticker.last,
                'volume': ticker.volume,
                'timestamp': datetime.now().isoformat()
            }
            self.market_data_received.emit(data)
            self.metrics['messages_received'] += 1
    
    def _on_order_status(self, trade):
        """Handle order status event"""
        status_data = {
            'order_id': trade.order.orderId,
            'status': trade.orderStatus.status,
            'filled': trade.orderStatus.filled,
            'remaining': trade.orderStatus.remaining,
            'avg_fill_price': trade.orderStatus.avgFillPrice,
            'timestamp': datetime.now().isoformat()
        }
        self.order_status_changed.emit(status_data)
        self.metrics['messages_received'] += 1
    
    def _on_open_order(self, trade):
        """Handle open order event"""
        self.active_orders[trade.order.orderId] = trade.order
    
    def _on_position(self, position):
        """Handle position update"""
        pos_data = {
            'account': position.account,
            'symbol': position.contract.symbol,
            'position': position.position,
            'avg_cost': position.avgCost,
            'timestamp': datetime.now().isoformat()
        }
        self.positions[position.contract.symbol] = pos_data
        self.position_updated.emit(pos_data)
        self.metrics['messages_received'] += 1
    
    def _on_account_value(self, value):
        """Handle account value update"""
        acc_data = {
            'account': value.account,
            'tag': value.tag,
            'value': value.value,
            'currency': value.currency,
            'timestamp': datetime.now().isoformat()
        }
        self.account_values[value.tag] = value.value
        self.account_updated.emit(acc_data)
        self.metrics['messages_received'] += 1
    
    def _on_error(self, reqId, errorCode, errorString, contract):
        """Handle error event"""
        error_msg = f"Error {errorCode}: {errorString}"
        if contract:
            error_msg += f" for {contract.symbol}"
        
        self.logger.error(f"❌ IB Error: {error_msg}")
        self.error_occurred.emit(error_msg)
        self.metrics['errors_count'] += 1
        self.metrics['last_error'] = error_msg
    
    # ==========================================================================
    # MARKET DATA OPERATIONS
    # ==========================================================================
    async def subscribe_market_data(self, contract: Contract) -> int:
        """
        Subscribe to market data for a contract.
        
        Args:
            contract: IB Contract object
            
        Returns:
            Request ID for the subscription
        """
        try:
            if not self.ib or not self.ib.isConnected():
                self.logger.error("❌ Not connected to IB Gateway")
                return -1
            
            # Request market data
            ticker = self.ib.reqMktData(contract, '', False, False)
            req_id = id(ticker)
            
            # Store subscription
            self.subscriptions[req_id] = contract
            
            self.logger.info(f"✅ Subscribed to market data for {contract.symbol}")
            return req_id
            
        except Exception as e:
            self.logger.error(f"❌ Failed to subscribe market data: {e}")
            return -1
    
    async def unsubscribe_market_data(self, req_id: int) -> bool:
        """
        Unsubscribe from market data.
        
        Args:
            req_id: Request ID of the subscription
            
        Returns:
            True if unsubscribed successfully
        """
        try:
            if req_id in self.subscriptions:
                contract = self.subscriptions[req_id]
                # Cancel market data
                self.ib.cancelMktData(contract)
                del self.subscriptions[req_id]
                self.logger.info(f"✅ Unsubscribed from market data for request {req_id}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"❌ Failed to unsubscribe market data: {e}")
            return False
    
    # ==========================================================================
    # ORDER OPERATIONS
    # ==========================================================================
    async def place_order_async(self, contract: Contract, order: Order) -> int:
        """
        Place an order asynchronously.
        
        Args:
            contract: IB Contract object
            order: IB Order object
            
        Returns:
            Order ID if successful, -1 otherwise
        """
        try:
            if not self.ib or not self.ib.isConnected():
                self.logger.error("❌ Not connected to IB Gateway")
                return -1
            
            # Place order
            trade = self.ib.placeOrder(contract, order)
            order_id = order.orderId
            
            # Store active order
            self.active_orders[order_id] = order
            
            self.logger.info(f"✅ Order placed: {order_id} for {contract.symbol}")
            return order_id
            
        except Exception as e:
            self.logger.error(f"❌ Failed to place order: {e}")
            return -1
    
    async def cancel_order_async(self, order_id: int) -> bool:
        """
        Cancel an order asynchronously.
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            True if cancelled successfully
        """
        try:
            if order_id in self.active_orders:
                order = self.active_orders[order_id]
                self.ib.cancelOrder(order)
                del self.active_orders[order_id]
                self.logger.info(f"✅ Order cancelled: {order_id}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"❌ Failed to cancel order: {e}")
            return False
    
    # ==========================================================================
    # ACCOUNT OPERATIONS
    # ==========================================================================
    async def request_positions(self) -> List[Dict]:
        """
        Request current positions.
        
        Returns:
            List of position dictionaries
        """
        try:
            if not self.ib or not self.ib.isConnected():
                return []
            
            positions = self.ib.positions()
            
            pos_list = []
            for pos in positions:
                pos_data = {
                    'account': pos.account,
                    'symbol': pos.contract.symbol,
                    'position': pos.position,
                    'avg_cost': pos.avgCost
                }
                pos_list.append(pos_data)
                self.positions[pos.contract.symbol] = pos_data
            
            return pos_list
            
        except Exception as e:
            self.logger.error(f"❌ Failed to request positions: {e}")
            return []
    
    async def request_account_summary(self) -> Dict:
        """
        Request account summary.
        
        Returns:
            Dictionary of account values
        """
        try:
            if not self.ib or not self.ib.isConnected():
                return {}
            
            account_values = self.ib.accountValues()
            
            summary = {}
            for av in account_values:
                summary[av.tag] = {
                    'value': av.value,
                    'currency': av.currency,
                    'account': av.account
                }
                self.account_values[av.tag] = av.value
            
            return summary
            
        except Exception as e:
            self.logger.error(f"❌ Failed to request account summary: {e}")
            return {}
    
    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    def get_connection_state(self) -> str:
        """Get current connection state"""
        return self.state.value
    
    def get_metrics(self) -> Dict:
        """Get performance metrics"""
        return self.metrics.copy()
    
    def is_connected(self) -> bool:
        """Check if connected to IB Gateway"""
        return self.ib and self.ib.isConnected() and self.state == ConnectionState.CONNECTED
    
    async def test_connection(self) -> bool:
        """
        Test connection to IB Gateway.
        
        Returns:
            True if connection is healthy
        """
        try:
            if not self.is_connected():
                return False
            
            # Request server time as a test
            server_time = self.ib.reqCurrentTime()
            self.logger.info(f"✅ Connection test successful. Server time: {server_time}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Connection test failed: {e}")
            return False

# ==============================================================================
# STANDALONE TEST
# ==============================================================================
async def test_async_bridge():
    """Test the AsyncIBGatewayBridge"""
    
    print("\n" + "=" * 60)
    print("🧪 TESTING ASYNC IB GATEWAY BRIDGE")
    print("=" * 60)
    
    # Create bridge instance
    bridge = AsyncIBGatewayBridge(paper_trading=True)
    
    # Initialize async loop
    if not bridge.initialize_async_loop():
        print("❌ Failed to initialize async loop")
        return
    
    # Connect to IB Gateway
    print("\n📡 Attempting connection...")
    connected = await bridge.connect_async()
    
    if connected:
        print("✅ Successfully connected!")
        
        # Test connection
        print("\n🧪 Testing connection...")
        if await bridge.test_connection():
            print("✅ Connection test passed")
        
        # Create SPY contract
        spy_contract = Contract()
        spy_contract.symbol = "SPY"
        spy_contract.secType = "STK"
        spy_contract.exchange = "SMART"
        spy_contract.currency = "USD"
        
        # Subscribe to market data
        print("\n📊 Subscribing to SPY market data...")
        req_id = await bridge.subscribe_market_data(spy_contract)
        if req_id > 0:
            print(f"✅ Subscribed with request ID: {req_id}")
            
            # Wait for some data
            await asyncio.sleep(5)
            
            # Unsubscribe
            await bridge.unsubscribe_market_data(req_id)
        
        # Request positions
        print("\n📈 Requesting positions...")
        positions = await bridge.request_positions()
        print(f"Found {len(positions)} positions")
        
        # Request account summary
        print("\n💰 Requesting account summary...")
        summary = await bridge.request_account_summary()
        if 'NetLiquidation' in summary:
            print(f"Net Liquidation: {summary['NetLiquidation']}")
        
        # Get metrics
        print("\n📊 Performance Metrics:")
        metrics = bridge.get_metrics()
        for key, value in metrics.items():
            print(f"  • {key}: {value}")
        
        # Disconnect
        print("\n🔌 Disconnecting...")
        await bridge.disconnect_async()
        print("✅ Disconnected successfully")
    else:
        print("❌ Connection failed")

def main():
    """Main entry point for testing"""
    
    # Check dependencies
    if not PYSIDE6_AVAILABLE:
        print("❌ PySide6 not available. Please install: pip install PySide6")
        return 1
    
    if not IB_ASYNC_AVAILABLE:
        print("❌ ib_async not available. Please install: pip install ib_async")
        return 1
    
    # Run async test
    try:
        asyncio.run(test_async_bridge())
        return 0
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
        return 1
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
# Export alias for missing PySideAsyncBridge
if "AsyncIBGatewayBridge" in globals():
    PySideAsyncBridge = AsyncIBGatewayBridge
else:
    class PySideAsyncBridge:
        def __init__(self): pass

