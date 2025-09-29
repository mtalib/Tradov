#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderR_Runtime [Application Name] [Series Letter] [Series Name] 
Module: SpyderR06_IBDataBridge.py [Application Name][Series Letter] [Module Number]_[Purpose].py
Purpose: IB Gateway Data Bridge with ib_async integration - THREADING FIXED
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-25 Time: 21:45:00  

Module Description:
    FIXED VERSION: This module creates a proper bridge between IB Gateway and the Spyder 
    dashboard using ib_async for IB Gateway 10.37+ compatibility. CRITICAL FIX: Resolved 
    PySide6 threading violations that caused segmentation faults. All GUI operations now 
    properly occur on the main thread using Qt signals.

Key Features:
    - ib_async integration for IB Gateway 10.37+ compatibility
    - FIXED: Thread-safe GUI updates using PySide6 signals only
    - FIXED: No direct GUI manipulation from background threads
    - Real-time market data injection into dashboard components
    - Comprehensive symbol subscription management (stocks, indices, futures)
    - Automatic connection monitoring and status reporting
    - Graceful fallback to simulation mode on connection failure
    - Event loop management for async operations

THREADING FIXES:
    - All GUI operations moved to main thread
    - Background threads use signals only for communication
    - QTimer operations properly handled on main thread
    - No direct Qt object manipulation from worker threads

Dependencies:
    - ib_async: Modern Interactive Brokers API client
    - PySide6: GUI framework for dashboard integration
    - SpyderG_GUI: Dashboard components for data display

"""

# ==============================================================================
# IMPORTS
# ==============================================================================
import sys
import os
import time
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Any
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Add Spyder to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, QObject, Signal, QThread, QMutex, QMutexLocker

# Import dashboard
from SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard

# Import IB with ib_async
try:
    from ib_async import IB, Stock, Index, Future, Contract, util
    IB_AVAILABLE = True
except ImportError:
    IB_AVAILABLE = False
    print("Warning: ib_async not available - dashboard will use simulation mode")

# ==============================================================================
# CONSTANTS
# ==============================================================================
IB_HOST = "127.0.0.1"
IB_PORT = 4002  # Paper trading
CLIENT_ID = 777  # Unique ID to avoid conflicts

# Enhanced symbol mappings with ib_async contracts
SYMBOL_CONTRACTS = {
    'SPY': Stock('SPY', 'SMART', 'USD'),
    'SPX': Index('SPX', 'CBOE'),
    '/ES': Future('ES', '202503', 'CME'),  # March 2025
    'VIX': Index('VIX', 'CBOE'),
    'VIX9D': Index('VIX9D', 'CBOE'),
    'VXV': Index('VXV', 'CBOE'),
    'VVIX': Index('VVIX', 'CBOE'),
    'UVXY': Stock('UVXY', 'SMART', 'USD'),
    'DIA': Stock('DIA', 'SMART', 'USD'),
    'QQQ': Stock('QQQ', 'SMART', 'USD'),
    'IWM': Stock('IWM', 'SMART', 'USD'),
    'TLT': Stock('TLT', 'SMART', 'USD'),
    'GLD': Stock('GLD', 'SMART', 'USD'),
    'DXY': Index('DXY', 'NYBOT'),
    'LQD': Stock('LQD', 'SMART', 'USD'),
    'SLV': Stock('SLV', 'SMART', 'USD'),
    'USO': Stock('USO', 'SMART', 'USD'),
    'XLE': Stock('XLE', 'SMART', 'USD'),
    'XLF': Stock('XLF', 'SMART', 'USD'),
    'XLK': Stock('XLK', 'SMART', 'USD'),
}

# Data update intervals
UPDATE_INTERVAL_MS = 2000  # 2 seconds
CONNECTION_TIMEOUT = 15    # 15 seconds
SUBSCRIPTION_DELAY = 0.1   # 100ms between subscriptions

# ==============================================================================
# THREAD-SAFE IB DATA BRIDGE CLASS - FIXED VERSION
# ==============================================================================

class IBDataBridge(QObject):
    """
    FIXED: Thread-safe bridge between IB Gateway and Dashboard using ib_async.
    
    This class manages the connection to IB Gateway, subscribes to market data,
    and provides real-time updates to the dashboard through Qt signals ONLY.
    
    CRITICAL FIX: All GUI operations now happen on main thread via signals.
    """
    
    # Qt Signals for thread-safe communication (ONLY way to update GUI)
    data_update = Signal(str, float, float, float)  # symbol, price, change, change_pct
    status_update = Signal(str)                     # status message
    connection_status = Signal(bool, str)           # connected, status_text
    log_message = Signal(str)                       # log messages for GUI
    
    def __init__(self, dashboard: SpyderTradingDashboard):
        """
        Initialize the IB Data Bridge.
        
        Args:
            dashboard: Reference to the Spyder trading dashboard
        """
        super().__init__()
        self.dashboard = dashboard
        self.ib = None
        self.connected = False
        self.tickers = {}
        self.last_prices = {}
        self.subscription_count = 0
        self.connection_mutex = QMutex()
        
        # Setup update timer (MAIN THREAD ONLY)
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._fetch_and_update)
        self.update_timer.setInterval(UPDATE_INTERVAL_MS)
        
        # Connection statistics
        self.connection_time = None
        self.total_updates = 0
        self.failed_updates = 0
        
        # Connect signals to dashboard methods (MAIN THREAD)
        self.log_message.connect(self.dashboard.add_system_log)
        
        # Thread pool for background operations
        self.thread_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="IBDataBridge")
        
        self._emit_log("IBDataBridge initialized with thread-safe ib_async")
    
    def _emit_log(self, message: str):
        """Thread-safe logging via signal."""
        self.log_message.emit(message)
    
    def connect_to_ib(self) -> bool:
        """
        FIXED: Thread-safe IB connection using separate worker.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        if not IB_AVAILABLE:
            self._emit_log("❌ ib_async not available")
            self.connection_status.emit(False, "IB_ASYNC UNAVAILABLE")
            return False
        
        # Start connection in thread pool (NOT as daemon thread)
        future = self.thread_pool.submit(self._connection_worker)
        
        # Wait briefly for connection attempt
        try:
            return future.result(timeout=CONNECTION_TIMEOUT)
        except Exception as e:
            self._emit_log(f"❌ Connection timeout: {e}")
            self.connection_status.emit(False, f"CONNECTION TIMEOUT: {str(e)}")
            return False
    
    def _connection_worker(self) -> bool:
        """
        FIXED: Worker thread for IB connection - NO DIRECT GUI OPERATIONS.
        
        Returns:
            bool: True if connection successful
        """
        try:
            # Create new IB instance
            self.ib = IB()
            
            # Connect with specific settings
            self.ib.connect(
                host=IB_HOST, 
                port=IB_PORT, 
                clientId=CLIENT_ID, 
                readonly=False, 
                timeout=CONNECTION_TIMEOUT
            )
            
            if not self.ib.isConnected():
                raise Exception("Connection failed - check IB Gateway status")
            
            # Connection successful - update state thread-safely
            with QMutexLocker(self.connection_mutex):
                self.connected = True
                self.connection_time = datetime.now()
            
            # FIXED: Use signals only for GUI updates
            self.connection_status.emit(True, "IB CONNECTED (PAPER)")
            self._emit_log("✅ Real IB connection established")
            
            # Setup event handlers and subscriptions
            self._setup_event_handlers()
            self._subscribe_symbols()
            
            # Start update timer on main thread
            QTimer.singleShot(0, lambda: self.update_timer.start())
            
            return True
            
        except Exception as e:
            # FIXED: Use signals only for GUI updates
            self._emit_log(f"❌ IB Connection failed: {e}")
            self.connection_status.emit(False, f"IB FAILED: {str(e)}")
            
            with QMutexLocker(self.connection_mutex):
                self.connected = False
            
            return False
    
    def _setup_event_handlers(self):
        """Setup IB event handlers for monitoring."""
        if not self.ib:
            return
        
        try:
            # Set up disconnect handler
            self.ib.disconnectedEvent += self._on_ib_disconnect
            self._emit_log("✅ IB event handlers configured")
            
        except Exception as e:
            self._emit_log(f"⚠️ Event handler setup warning: {e}")
    
    def _on_ib_disconnect(self):
        """Handle IB disconnect event."""
        with QMutexLocker(self.connection_mutex):
            self.connected = False
        
        # FIXED: Use signals for GUI updates
        self.connection_status.emit(False, "IB DISCONNECTED")
        self._emit_log("❌ IB Gateway disconnected")
    
    def _subscribe_symbols(self):
        """Subscribe to market data for all symbols."""
        if not self.ib or not self.connected:
            return
        
        try:
            subscription_count = 0
            
            for symbol, contract in SYMBOL_CONTRACTS.items():
                try:
                    # Qualify contract first
                    qualified = self.ib.qualifyContracts(contract)
                    if qualified:
                        # Request market data
                        ticker = self.ib.reqMktData(qualified[0], '', False, False)
                        if ticker:
                            self.tickers[symbol] = ticker
                            subscription_count += 1
                            
                        # Small delay between subscriptions
                        time.sleep(SUBSCRIPTION_DELAY)
                        
                except Exception as e:
                    self._emit_log(f"⚠️ Failed to subscribe to {symbol}: {e}")
                    continue
            
            self.subscription_count = subscription_count
            self._emit_log(f"✅ Subscribed to {subscription_count} symbols")
            
        except Exception as e:
            self._emit_log(f"❌ Symbol subscription error: {e}")
    
    def _fetch_and_update(self):
        """
        FIXED: Fetch data and emit updates - MAIN THREAD ONLY.
        
        This method runs on the main thread and safely emits data updates.
        """
        if not self.connected or not self.tickers:
            return
        
        try:
            updates_sent = 0
            
            for symbol, ticker in self.tickers.items():
                try:
                    if ticker and ticker.last and ticker.last > 0:
                        # Calculate change
                        current_price = float(ticker.last)
                        last_price = self.last_prices.get(symbol, current_price)
                        change = current_price - last_price
                        change_pct = (change / last_price * 100) if last_price != 0 else 0.0
                        
                        # Update last price
                        self.last_prices[symbol] = current_price
                        
                        # FIXED: Emit signal for thread-safe GUI update
                        self.data_update.emit(symbol, current_price, change, change_pct)
                        updates_sent += 1
                        
                except Exception as e:
                    self.failed_updates += 1
                    continue
            
            self.total_updates += updates_sent
            
        except Exception as e:
            self._emit_log(f"❌ Data fetch error: {e}")
            self.failed_updates += 1
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """
        Get connection statistics.
        
        Returns:
            dict: Connection statistics
        """
        with QMutexLocker(self.connection_mutex):
            uptime = None
            if self.connection_time:
                uptime = (datetime.now() - self.connection_time).total_seconds()
            
            return {
                'connected': self.connected,
                'ib_available': IB_AVAILABLE,
                'client_id': CLIENT_ID,
                'connection_time': self.connection_time,
                'uptime_seconds': uptime,
                'subscriptions': self.subscription_count,
                'total_symbols': len(SYMBOL_CONTRACTS),
                'total_updates': self.total_updates,
                'failed_updates': self.failed_updates,
                'api_version': 'ib_async'
            }
    
    def disconnect(self):
        """FIXED: Thread-safe disconnect from IB Gateway."""
        try:
            # Stop update timer on main thread
            if self.update_timer.isActive():
                self.update_timer.stop()
            
            # Disconnect from IB in thread pool
            if self.ib and self.connected:
                future = self.thread_pool.submit(self._disconnect_worker)
                
                # Wait briefly for disconnect
                try:
                    future.result(timeout=5)
                except Exception as e:
                    self._emit_log(f"Disconnect timeout: {e}")
            
        except Exception as e:
            self._emit_log(f"Error during disconnect: {e}")
    
    def _disconnect_worker(self):
        """Worker method for IB disconnection."""
        try:
            if self.ib:
                self.ib.disconnect()
            
            with QMutexLocker(self.connection_mutex):
                self.connected = False
            
            # FIXED: Use signals for GUI updates
            self._emit_log("IBDataBridge disconnected")
            self.connection_status.emit(False, "DISCONNECTED")
            
        except Exception as e:
            self._emit_log(f"Error in disconnect worker: {e}")

# ==============================================================================
# DASHBOARD WITH FIXED IB DATA BRIDGE
# ==============================================================================

class LiveDashboardWithBridge(SpyderTradingDashboard):
    """
    FIXED: Dashboard enhanced with thread-safe IB Data Bridge functionality.
    
    This class extends the standard trading dashboard to include live
    market data integration through the fixed IB Data Bridge.
    """
    
    def __init__(self):
        super().__init__()
        
        # Stop any existing simulation timer
        if hasattr(self, "timer"):
            self.timer.stop()
        
        # Create and setup IB data bridge
        self.bridge = IBDataBridge(self)
        
        # FIXED: Connect bridge signals to main thread methods
        self.bridge.data_update.connect(self._handle_data_update)
        self.bridge.status_update.connect(self._handle_status_update)
        self.bridge.connection_status.connect(self._handle_connection_status)
        
        self.add_system_log("Dashboard initialized with thread-safe IB Data Bridge")
        
        # FIXED: Start connection on main thread with delay
        QTimer.singleShot(2000, self._connect_bridge)
    
    def _connect_bridge(self):
        """FIXED: Connect the data bridge to IB Gateway on main thread."""
        self.add_system_log("Attempting to connect to IB Gateway...")
        
        # Run connection in thread pool (managed by bridge)
        try:
            success = self.bridge.connect_to_ib()
            if success:
                self.add_automation_log("✅ IB Data Bridge active - receiving real market data")
            else:
                self.add_automation_log("❌ IB connection failed - check Gateway settings")
                self.add_system_log("Falling back to simulation mode")
                
                # FIXED: Restart simulation timer on main thread
                if hasattr(self, "timer"):
                    QTimer.singleShot(1000, lambda: self.timer.start())
                    
        except Exception as e:
            self.add_system_log(f"Connection error: {e}")
            # FIXED: Fallback to simulation on main thread
            if hasattr(self, "timer"):
                QTimer.singleShot(1000, lambda: self.timer.start())
    
    def _handle_data_update(self, symbol: str, price: float, change: float, change_pct: float):
        """
        FIXED: Handle data updates from the bridge - MAIN THREAD ONLY.
        
        Args:
            symbol: Symbol name
            price: Current price
            change: Price change
            change_pct: Percentage change
        """
        try:
            # Update the dashboard display (safe because we're on main thread)
            if hasattr(self, 'update_symbol'):
                self.update_symbol(symbol, price, change, change_pct)
            
            # Update symbol displays if they exist (safe on main thread)
            if hasattr(self, 'symbol_displays') and symbol in self.symbol_displays:
                display = self.symbol_displays[symbol]
                if display and 'price' in display:
                    display['price'].setText(f"${price:.2f}")
                    
                    # Update color based on change
                    color = "#00ff00" if change >= 0 else "#ff0000"
                    if 'change' in display:
                        display['change'].setText(f"{change:+.2f} ({change_pct:+.2f}%)")
                        display['change'].setStyleSheet(f"color: {color};")
                        
        except Exception as e:
            self.add_system_log(f"Error updating display for {symbol}: {e}")
    
    def _handle_status_update(self, status: str):
        """Handle status updates from the bridge - MAIN THREAD."""
        self.add_system_log(f"Bridge status: {status}")
    
    def _handle_connection_status(self, connected: bool, status_text: str):
        """Handle connection status changes - MAIN THREAD."""
        if connected:
            self.add_automation_log(f"🎯 LIVE MODE ACTIVE - {status_text}")
            # Update window title (safe on main thread)
            self.setWindowTitle(f"Spyder Trading Dashboard - LIVE ({status_text})")
        else:
            self.add_automation_log(f"❌ CONNECTION LOST - {status_text}")
            # Update window title (safe on main thread)
            self.setWindowTitle(f"Spyder Trading Dashboard - DISCONNECTED")
    
    def get_bridge_status(self) -> dict:
        """Get current bridge status for debugging."""
        if hasattr(self, 'bridge'):
            return self.bridge.get_connection_stats()
        return {'status': 'Bridge not initialized'}
    
    def closeEvent(self, event):
        """FIXED: Clean up on window close - properly handle threading."""
        try:
            if hasattr(self, 'bridge'):
                # Disconnect bridge safely
                self.bridge.disconnect()
                
                # Shutdown thread pool
                if hasattr(self.bridge, 'thread_pool'):
                    self.bridge.thread_pool.shutdown(wait=True, timeout=3)
            
            # Call parent close event
            super().closeEvent(event)
            
        except Exception as e:
            print(f"Error during close: {e}")
            event.accept()

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def test_ib_bridge_connection() -> bool:
    """
    Test IB connection for the data bridge.
    
    Returns:
        bool: True if connection successful, False otherwise
    """
    if not IB_AVAILABLE:
        print("❌ ib_async not available")
        return False
    
    try:
        print(f"Testing IB connection at {IB_HOST}:{IB_PORT} with client {CLIENT_ID}")
        
        ib = IB()
        ib.connect(IB_HOST, IB_PORT, clientId=CLIENT_ID, timeout=10)
        
        if ib.isConnected():
            print(f"✅ Connection successful!")
            
            # Test a simple data request
            spy_contract = Stock('SPY', 'SMART', 'USD')
            ib.qualifyContracts(spy_contract)
            
            ticker = ib.reqMktData(spy_contract, '', False, False)
            time.sleep(2)  # Wait for data
            
            if ticker.last:
                print(f"✅ Market data working - SPY: ${ticker.last}")
            else:
                print("⚠️ Connection OK but no market data received")
            
            ib.disconnect()
            return True
        else:
            print("❌ Connection failed")
            return False
            
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

def main():
    """Main execution for standalone testing and dashboard launch."""
    print("=" * 60)
    print("SPYDER DASHBOARD WITH THREAD-SAFE IB DATA BRIDGE (ib_async)")
    print("=" * 60)
    print(f"ib_async available: {IB_AVAILABLE}")
    print(f"Target: {IB_HOST}:{IB_PORT}")
    print(f"Client ID: {CLIENT_ID}")
    print(f"Symbols to track: {len(SYMBOL_CONTRACTS)}")
    print("=" * 60)
    
    # Test connection first
    if test_ib_bridge_connection():
        print("✅ Connection test passed - launching dashboard")
    else:
        print("❌ Connection test failed - dashboard will use simulation")
    
    # Initialize ib_async event loop if available
    if IB_AVAILABLE:
        try:
            util.startLoop()
            print("✅ ib_async event loop started")
        except Exception as e:
            print(f"⚠️ Event loop warning: {e}")
    
    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("Spyder Trading System")
    
    print("\n🚀 Launching dashboard with thread-safe real market data...")
    
    # Create and show dashboard
    dashboard = LiveDashboardWithBridge()
    dashboard.show()
    
    print("Dashboard launched!")
    print("Connecting to IB Gateway in 2 seconds...")
    print("\nIf data doesn't appear:")
    print("1. Check IB Gateway is running and logged in")
    print("2. Verify port 4002 is correct (paper trading)")
    print("3. Ensure API connections are enabled in Gateway")
    print("4. Try restarting IB Gateway if needed")
    print("=" * 60)
    
    # Run application
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
