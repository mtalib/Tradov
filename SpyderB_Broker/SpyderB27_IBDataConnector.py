#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB27_IBDataConnector.py
Purpose: Real-time market data connector for IB Gateway
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-01-23 Time: 00:00:00

Module Description:
    Direct market data connector for Interactive Brokers Gateway that handles
    real-time market data subscriptions, updates, and distribution to the
    dashboard. This module bridges the gap between IB Gateway connection
    detection and actual market data flow.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set
from enum import Enum

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    from ib_async import IB, Stock, Index, Future, Option, Contract, Ticker
    IB_ASYNC_AVAILABLE = True
except ImportError:
    print("❌ ib_async not installed. Please install: pip install ib_async")
    IB_ASYNC_AVAILABLE = False

from PySide6.QtCore import QObject, Signal, QTimer, Slot
from PySide6.QtCore import QThread

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Symbols to subscribe - matching your dashboard's MARKET_SYMBOLS
MARKET_SYMBOLS = {
    "S&P CORE": ["SPY", "SPX", "ES"],  # Removed /ES as it needs special handling
    "VOLATILITY": ["VIX", "UVXY"],  # VIX needs special handling as Index
    "MAJOR INDICES": ["DIA", "QQQ", "IWM"],
    "BONDS & CREDIT": ["TLT", "LQD"],
    "CORRELATIONS": ["DXY", "GLD"],
}

# Special handling for futures and indices
FUTURES_SYMBOLS = {
    "ES": ("ES", "CME", "USD", "202503"),  # March 2025 E-mini S&P 500
}

INDEX_SYMBOLS = {
    "SPX": ("SPX", "CBOE", "USD"),
    "VIX": ("VIX", "CBOE", "USD"),
    "DXY": ("DXY", "NYBOT", "USD"),
}

# ==============================================================================
# IB DATA CONNECTOR
# ==============================================================================
class IBDataConnector(QObject):
    """
    Real-time market data connector for IB Gateway.
    Handles subscriptions and data distribution.
    """
    
    # Signals
    data_received = Signal(dict)
    connection_status = Signal(bool, str)
    error_occurred = Signal(str)
    
    def __init__(self, client_id: int = 2):
        """Initialize the IB data connector"""
        super().__init__()
        
        self.logger = logging.getLogger(self.__class__.__name__)
        self.client_id = client_id
        
        # IB connection
        self.ib = None
        self.connected = False
        
        # Data storage
        self.subscriptions: Dict[str, Ticker] = {}
        self.contracts: Dict[str, Contract] = {}
        self.market_data: Dict[str, Dict] = {}
        
        # Update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.emit_market_data)
        self.update_timer.setInterval(1000)  # Emit every second
        
        self.logger.info("IBDataConnector initialized")
    
    async def connect_and_subscribe(self, host: str = "127.0.0.1", port: int = 4002) -> bool:
        """
        Connect to IB Gateway and subscribe to all market data.
        
        Args:
            host: IB Gateway host
            port: IB Gateway port (4002 for paper, 4001 for live)
            
        Returns:
            True if successful
        """
        try:
            # Create IB instance if needed
            if not self.ib:
                self.ib = IB()
            
            # Connect to IB Gateway
            self.logger.info(f"Connecting to IB Gateway at {host}:{port}")
            await self.ib.connectAsync(host, port, clientId=self.client_id)
            
            self.connected = True
            self.connection_status.emit(True, f"Connected to IB Gateway (Client {self.client_id})")
            
            # Get server info
            self.logger.info(f"Connected to IB - Server Version: {self.ib.serverVersion()}")
            
            # Subscribe to all symbols
            await self._subscribe_all_symbols()
            
            # Start update timer
            self.update_timer.start()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            self.error_occurred.emit(f"IB connection failed: {e}")
            self.connected = False
            return False
    
    async def _subscribe_all_symbols(self):
        """Subscribe to all market symbols"""
        subscription_count = 0
        
        # Subscribe to stocks
        for category, symbols in MARKET_SYMBOLS.items():
            for symbol in symbols:
                if symbol not in ["SPX", "VIX", "DXY", "ES"]:  # These need special handling
                    try:
                        contract = Stock(symbol, 'SMART', 'USD')
                        await self._subscribe_to_contract(symbol, contract)
                        subscription_count += 1
                    except Exception as e:
                        self.logger.error(f"Failed to subscribe to {symbol}: {e}")
        
        # Subscribe to indices
        for symbol, (index_symbol, exchange, currency) in INDEX_SYMBOLS.items():
            try:
                contract = Index(index_symbol, exchange, currency)
                await self._subscribe_to_contract(symbol, contract)
                subscription_count += 1
            except Exception as e:
                self.logger.error(f"Failed to subscribe to index {symbol}: {e}")
        
        # Subscribe to futures
        for symbol, (future_symbol, exchange, currency, expiry) in FUTURES_SYMBOLS.items():
            try:
                contract = Future(future_symbol, expiry, exchange, currency=currency)
                await self._subscribe_to_contract(symbol, contract)
                subscription_count += 1
            except Exception as e:
                self.logger.error(f"Failed to subscribe to future {symbol}: {e}")
        
        self.logger.info(f"Subscribed to {subscription_count} symbols")
    
    async def _subscribe_to_contract(self, symbol: str, contract: Contract):
        """
        Subscribe to market data for a specific contract.
        
        Args:
            symbol: Symbol identifier for our system
            contract: IB Contract object
        """
        try:
            # Request market data
            ticker = self.ib.reqMktData(
                contract,
                genericTickList='',
                snapshot=False,
                regulatorySnapshot=False
            )
            
            # Store subscription
            self.subscriptions[symbol] = ticker
            self.contracts[symbol] = contract
            
            # Set up event handler
            ticker.updateEvent += lambda ticker: self._on_ticker_update(symbol, ticker)
            
            self.logger.info(f"Subscribed to {symbol}")
            
        except Exception as e:
            self.logger.error(f"Subscription failed for {symbol}: {e}")
            raise
    
    def _on_ticker_update(self, symbol: str, ticker: Ticker):
        """
        Handle ticker updates from IB.
        
        Args:
            symbol: Symbol identifier
            ticker: IB Ticker object with updated data
        """
        try:
            # Extract data from ticker
            data = {
                'symbol': symbol,
                'last': float(ticker.last) if ticker.last and ticker.last > 0 else float(ticker.close) if ticker.close else 0,
                'bid': float(ticker.bid) if ticker.bid and ticker.bid > 0 else 0,
                'ask': float(ticker.ask) if ticker.ask and ticker.ask > 0 else 0,
                'volume': int(ticker.volume) if ticker.volume else 0,
                'high': float(ticker.high) if ticker.high else 0,
                'low': float(ticker.low) if ticker.low else 0,
                'close': float(ticker.close) if ticker.close else 0,
                'timestamp': datetime.now()
            }
            
            # Calculate change and change percentage
            if data['close'] > 0 and data['last'] > 0:
                data['change'] = data['last'] - data['close']
                data['change_pct'] = (data['change'] / data['close']) * 100
            else:
                data['change'] = 0
                data['change_pct'] = 0
            
            # Store in market data
            self.market_data[symbol] = data
            
        except Exception as e:
            self.logger.error(f"Error processing ticker update for {symbol}: {e}")
    
    @Slot()
    def emit_market_data(self):
        """Emit all current market data"""
        if self.market_data:
            # Make a copy to emit
            data_copy = self.market_data.copy()
            self.data_received.emit(data_copy)
    
    def disconnect(self):
        """Disconnect from IB Gateway"""
        try:
            if self.update_timer:
                self.update_timer.stop()
            
            if self.ib and self.ib.isConnected():
                # Cancel all subscriptions
                for symbol, ticker in self.subscriptions.items():
                    try:
                        self.ib.cancelMktData(self.contracts[symbol])
                    except:
                        pass
                
                # Disconnect
                self.ib.disconnect()
                self.logger.info("Disconnected from IB Gateway")
            
            self.connected = False
            self.connection_status.emit(False, "Disconnected from IB Gateway")
            
        except Exception as e:
            self.logger.error(f"Error during disconnect: {e}")
    
    def get_market_data(self, symbol: str) -> Optional[Dict]:
        """
        Get current market data for a symbol.
        
        Args:
            symbol: Symbol to get data for
            
        Returns:
            Market data dictionary or None
        """
        return self.market_data.get(symbol)
    
    def is_connected(self) -> bool:
        """Check if connected to IB Gateway"""
        return self.ib and self.ib.isConnected() if self.ib else False

# ==============================================================================
# ASYNC WORKER FOR THREAD SAFETY
# ==============================================================================
class IBDataWorkerThread(QThread):
    """
    Worker thread to run IB data connector asynchronously.
    """
    
    # Signals
    data_ready = Signal(dict)
    status_changed = Signal(bool, str)
    error = Signal(str)
    
    def __init__(self, host: str = "127.0.0.1", port: int = 4002, client_id: int = 2):
        super().__init__()
        self.host = host
        self.port = port
        self.client_id = client_id
        self.connector = None
        self.running = False
        
    def run(self):
        """Run the async event loop in thread"""
        self.running = True
        
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Create connector
            self.connector = IBDataConnector(self.client_id)
            
            # Connect signals
            self.connector.data_received.connect(self.data_ready.emit)
            self.connector.connection_status.connect(self.status_changed.emit)
            self.connector.error_occurred.connect(self.error.emit)
            
            # Connect and subscribe
            loop.run_until_complete(
                self.connector.connect_and_subscribe(self.host, self.port)
            )
            
            # Keep running until stopped
            while self.running and self.connector.is_connected():
                loop.run_until_complete(asyncio.sleep(0.1))
                
        except Exception as e:
            self.error.emit(f"Worker thread error: {e}")
        finally:
            if self.connector:
                self.connector.disconnect()
            loop.close()
    
    def stop(self):
        """Stop the worker thread"""
        self.running = False
        if self.connector:
            self.connector.disconnect()

# ==============================================================================
# INTEGRATION PATCH FOR DASHBOARD
# ==============================================================================
def patch_dashboard_with_ib_data(dashboard):
    """
    Patch existing dashboard to use real IB data.
    
    Args:
        dashboard: SpyderTradingDashboard instance
    """
    
    # Create IB data worker thread
    ib_worker = IBDataWorkerThread(port=4002, client_id=2)
    
    # Connect to dashboard's market data handler
    def handle_ib_data(data):
        """Handle real IB market data"""
        # Update dashboard's symbol widgets
        for symbol, market_info in data.items():
            if symbol in dashboard.symbol_widgets:
                dashboard.symbol_widgets[symbol].update_data(market_info)
        
        # Update dashboard's market data storage
        dashboard.market_data.update(data)
        
        # Log first data receipt
        if not hasattr(dashboard, '_first_ib_data_logged'):
            dashboard.add_system_log(f"📊 Receiving real IB market data - {len(data)} symbols")
            dashboard._first_ib_data_logged = True
    
    # Connect signals
    ib_worker.data_ready.connect(handle_ib_data)
    ib_worker.status_changed.connect(
        lambda connected, msg: dashboard.add_system_log(f"🔌 IB Data: {msg}")
    )
    ib_worker.error.connect(
        lambda err: dashboard.add_system_log(f"❌ IB Data Error: {err}")
    )
    
    # Store reference and start
    dashboard.ib_data_worker = ib_worker
    ib_worker.start()
    
    dashboard.add_system_log("🚀 IB market data connector started")
    
    # Override the original force_connect to use real IB data
    original_force_connect = dashboard.market_worker.force_connect
    
    def enhanced_force_connect():
        """Enhanced connect that starts real IB data"""
        result = original_force_connect()
        if result and not ib_worker.isRunning():
            ib_worker.start()
        return result
    
    dashboard.market_worker.force_connect = enhanced_force_connect
    
    return dashboard

# ==============================================================================
# STANDALONE TEST
# ==============================================================================
async def test_ib_data():
    """Test IB data connection standalone"""
    print("\n" + "="*60)
    print("🧪 TESTING IB DATA CONNECTOR")
    print("="*60)
    
    connector = IBDataConnector()
    
    # Connect
    success = await connector.connect_and_subscribe()
    
    if success:
        print("✅ Connected successfully!")
        
        # Wait for data
        print("\n📊 Waiting for market data...")
        await asyncio.sleep(5)
        
        # Display data
        print("\n📈 Current Market Data:")
        for symbol, data in connector.market_data.items():
            print(f"{symbol}: ${data['last']:.2f} ({data['change']:+.2f} {data['change_pct']:+.2f}%)")
        
        # Disconnect
        connector.disconnect()
    else:
        print("❌ Connection failed")

if __name__ == "__main__":
    asyncio.run(test_ib_data())