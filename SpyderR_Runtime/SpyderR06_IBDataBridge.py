#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderR_Runtime [Application Name] [Series Letter] [Series Name] 
Module: SpyderR06_IBDataBridge.py [Application Name][Series Letter] [Module Number]_[Purpose].py
Purpose: IB Gateway Data Bridge with ib_async integration for live market data injection
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-21 Time: 21:10:00  

Module Description:
    This module creates a proper bridge between IB Gateway and the Spyder 
    dashboard using ib_async for IB Gateway 10.37+ compatibility. It establishes 
    a real IB connection and injects live market data directly into the dashboard's 
    display elements, providing seamless integration between live market feeds 
    and the trading interface. Includes symbol subscription management, 
    real-time data updates, and fallback mechanisms.

Key Features:
    - ib_async integration for IB Gateway 10.37+ compatibility
    - Real-time market data injection into dashboard components
    - Comprehensive symbol subscription management (stocks, indices, futures)
    - Automatic connection monitoring and status reporting
    - Thread-safe data updates with PyQt6 signals
    - Graceful fallback to simulation mode on connection failure
    - Event loop management for async operations

Dependencies:
    - ib_async: Modern Interactive Brokers API client
    - PyQt6: GUI framework for dashboard integration
    - SpyderG_GUI: Dashboard components for data display

NOTE: This module was renumbered from R05 to R06 to resolve duplicate 
      module numbering conflicts in the Spyder system.

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

# Add Spyder to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer, QObject, pyqtSignal

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
# IB DATA BRIDGE CLASS
# ==============================================================================

class IBDataBridge(QObject):
    """
    Bridge between IB Gateway and Dashboard using ib_async.
    
    This class manages the connection to IB Gateway, subscribes to market data,
    and provides real-time updates to the dashboard through Qt signals.
    """
    
    # Qt Signals for data updates
    data_update = pyqtSignal(str, float, float, float)  # symbol, price, change, change_pct
    status_update = pyqtSignal(str)                     # status message
    connection_status = pyqtSignal(bool, str)           # connected, status_text
    
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
        
        # Setup update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._fetch_and_update)
        self.update_timer.setInterval(UPDATE_INTERVAL_MS)
        
        # Connection statistics
        self.connection_time = None
        self.total_updates = 0
        self.failed_updates = 0
        
        self.dashboard.add_system_log("IBDataBridge initialized with ib_async")
    
    def connect_to_ib(self) -> bool:
        """
        Establish IB connection using ib_async.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        if not IB_AVAILABLE:
            self.dashboard.add_system_log("❌ ib_async not available")
            self.connection_status.emit(False, "IB_ASYNC UNAVAILABLE")
            return False
        
        try:
            # Create new IB instance
            self.ib = IB()
            
            # Connect with specific settings
            self.dashboard.add_system_log(f"Connecting to IB Gateway at {IB_HOST}:{IB_PORT}...")
            self.ib.connect(
                host=IB_HOST, 
                port=IB_PORT, 
                clientId=CLIENT_ID, 
                readonly=False, 
                timeout=CONNECTION_TIMEOUT
            )
            
            if not self.ib.isConnected():
                raise Exception("Connection failed - check IB Gateway status")
            
            # Connection successful
            self.connected = True
            self.connection_time = datetime.now()
            
            # Update dashboard status
            self._update_dashboard_status(True, "IB CONNECTED (PAPER)")
            self.dashboard.add_system_log("✅ Real IB connection established")
            self.connection_status.emit(True, f"IB CONNECTED (Client {CLIENT_ID})")
            
            # Setup event handlers
            self._setup_event_handlers()
            
            # Start subscribing to symbols
            self._subscribe_symbols()
            
            # Start update timer
            self.update_timer.start()
            
            return True
            
        except Exception as e:
            self.dashboard.add_system_log(f"❌ IB Connection failed: {e}")
            self._update_dashboard_status(False, "IB DISCONNECTED")
            self.connection_status.emit(False, f"IB FAILED: {str(e)}")
            return False
    
    def _setup_event_handlers(self):
        """Setup IB event handlers for monitoring."""
        if not self.ib:
            return
        
        def on_connected():
            self.dashboard.add_system_log(f"✅ IB connected event - Client {CLIENT_ID}")
        
        def on_disconnected():
            self.connected = False
            self.dashboard.add_system_log("❌ IB disconnected event")
            self.connection_status.emit(False, "IB DISCONNECTED")
            self._update_dashboard_status(False, "IB DISCONNECTED")
            
            # Stop update timer
            if self.update_timer.isActive():
                self.update_timer.stop()
        
        def on_error(reqId, errorCode, errorString, contract):
            self.dashboard.add_system_log(f"IB Error {errorCode}: {errorString}")
            if errorCode in [1100, 1102]:  # Connection lost/restored
                self.connected = False
        
        # Connect event handlers
        self.ib.connectedEvent += on_connected
        self.ib.disconnectedEvent += on_disconnected
        self.ib.errorEvent += on_error
    
    def _subscribe_symbols(self):
        """Subscribe to market data for all symbols using ib_async."""
        if not self.ib or not self.connected:
            return
        
        self.dashboard.add_system_log("Subscribing to market data...")
        
        # Request delayed data if real-time not available
        self.ib.reqMarketDataType(3)  # 3 = delayed data
        
        successful_subscriptions = 0
        
        for symbol, contract in SYMBOL_CONTRACTS.items():
            try:
                # Qualify contract first
                self.ib.qualifyContracts(contract)
                
                # Request market data
                ticker = self.ib.reqMktData(contract, '', False, False)
                self.tickers[symbol] = ticker
                
                successful_subscriptions += 1
                self.dashboard.add_system_log(f"  ✓ Subscribed to {symbol}")
                
                # Small delay to avoid overwhelming API
                time.sleep(SUBSCRIPTION_DELAY)
                
            except Exception as e:
                self.dashboard.add_system_log(f"  ✗ Failed to subscribe to {symbol}: {e}")
        
        self.subscription_count = successful_subscriptions
        self.dashboard.add_system_log(
            f"✅ Subscribed to {successful_subscriptions}/{len(SYMBOL_CONTRACTS)} symbols"
        )
    
    def _fetch_and_update(self):
        """Fetch latest prices and update dashboard."""
        if not self.connected or not self.ib.isConnected():
            return
        
        updates_made = 0
        
        for symbol, ticker in self.tickers.items():
            try:
                # Get current price
                if ticker.last and ticker.last > 0:
                    current_price = float(ticker.last)
                elif ticker.marketPrice() and ticker.marketPrice() > 0:
                    current_price = float(ticker.marketPrice())
                elif ticker.close and ticker.close > 0:
                    current_price = float(ticker.close)
                else:
                    continue  # Skip if no valid price
                
                # Calculate change
                if symbol in self.last_prices:
                    previous_price = self.last_prices[symbol]
                    change = current_price - previous_price
                    change_pct = (change / previous_price) * 100 if previous_price > 0 else 0
                else:
                    # First time - use ticker's change if available
                    change = float(ticker.change) if ticker.change else 0
                    change_pct = ((change / current_price) * 100) if current_price > 0 else 0
                
                # Store current price
                self.last_prices[symbol] = current_price
                
                # Emit data update signal
                self.data_update.emit(symbol, current_price, change, change_pct)
                updates_made += 1
                
            except Exception as e:
                self.failed_updates += 1
                # Don't spam logs with every failed update
                if self.failed_updates % 10 == 0:
                    self.dashboard.add_system_log(f"Data update error for {symbol}: {e}")
        
        self.total_updates += updates_made
        
        # Update status periodically
        if self.total_updates % 50 == 0:
            self.dashboard.add_system_log(
                f"Data updates: {self.total_updates} total, {updates_made} this cycle"
            )
    
    def _update_dashboard_status(self, connected: bool, status_text: str):
        """Update dashboard connection status."""
        try:
            # This would typically call a method on the dashboard to update status
            # The exact method depends on the dashboard implementation
            if hasattr(self.dashboard, 'update_connection_status'):
                self.dashboard.update_connection_status(connected, status_text)
            
            # Also emit status signal
            self.status_update.emit(status_text)
            
        except Exception as e:
            self.dashboard.add_system_log(f"Error updating dashboard status: {e}")
    
    def get_connection_stats(self) -> dict:
        """
        Get connection statistics.
        
        Returns:
            dict: Connection statistics
        """
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
        """Disconnect from IB Gateway."""
        try:
            # Stop update timer
            if self.update_timer.isActive():
                self.update_timer.stop()
            
            # Disconnect from IB
            if self.ib and self.connected:
                self.ib.disconnect()
                self.connected = False
                self.dashboard.add_system_log("IBDataBridge disconnected")
                self.connection_status.emit(False, "DISCONNECTED")
            
        except Exception as e:
            self.dashboard.add_system_log(f"Error disconnecting: {e}")

# ==============================================================================
# DASHBOARD WITH IB DATA BRIDGE
# ==============================================================================

class LiveDashboardWithBridge(SpyderTradingDashboard):
    """
    Dashboard enhanced with IB Data Bridge functionality.
    
    This class extends the standard trading dashboard to include live
    market data integration through the IB Data Bridge.
    """
    
    def __init__(self):
        super().__init__()
        
        # Stop any existing simulation timer
        if hasattr(self, "timer"):
            self.timer.stop()
        
        # Create and setup IB data bridge
        self.bridge = IBDataBridge(self)
        
        # Connect bridge signals
        self.bridge.data_update.connect(self._handle_data_update)
        self.bridge.status_update.connect(self._handle_status_update)
        self.bridge.connection_status.connect(self._handle_connection_status)
        
        self.add_system_log("Dashboard initialized with IB Data Bridge (ib_async)")
        
        # Start connection attempt after GUI is ready
        QTimer.singleShot(2000, self._connect_bridge)
    
    def _connect_bridge(self):
        """Connect the data bridge to IB Gateway."""
        self.add_system_log("Attempting to connect to IB Gateway...")
        
        # Run connection in separate thread to avoid blocking GUI
        connection_thread = threading.Thread(
            target=self._connection_worker,
            name="IBDataBridgeWorker",
            daemon=True
        )
        connection_thread.start()
    
    def _connection_worker(self):
        """Worker thread for IB connection."""
        try:
            success = self.bridge.connect_to_ib()
            if success:
                self.add_automation_log("✅ IB Data Bridge active - receiving real market data")
            else:
                self.add_automation_log("❌ IB connection failed - check Gateway settings")
                self.add_system_log("Falling back to simulation mode")
                
                # Restart simulation timer if available
                if hasattr(self, "timer"):
                    QTimer.singleShot(1000, lambda: self.timer.start())
                    
        except Exception as e:
            self.add_system_log(f"Connection worker error: {e}")
            # Fallback to simulation
            if hasattr(self, "timer"):
                QTimer.singleShot(1000, lambda: self.timer.start())
    
    def _handle_data_update(self, symbol: str, price: float, change: float, change_pct: float):
        """
        Handle data updates from the bridge.
        
        Args:
            symbol: Symbol name
            price: Current price
            change: Price change
            change_pct: Percentage change
        """
        try:
            # Update the dashboard display
            self.update_symbol(symbol, price, change, change_pct)
            
            # Update symbol displays if they exist
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
        """Handle status updates from the bridge."""
        self.add_system_log(f"Bridge status: {status}")
    
    def _handle_connection_status(self, connected: bool, status_text: str):
        """Handle connection status changes."""
        if connected:
            self.add_automation_log(f"🎯 LIVE MODE ACTIVE - {status_text}")
            # Update window title to show live status
            self.setWindowTitle(f"Spyder Trading Dashboard - LIVE ({status_text})")
        else:
            self.add_automation_log(f"❌ CONNECTION LOST - {status_text}")
            # Update window title to show disconnected status
            self.setWindowTitle(f"Spyder Trading Dashboard - DISCONNECTED")
    
    def get_bridge_status(self) -> dict:
        """Get current bridge status for debugging."""
        if hasattr(self, 'bridge'):
            return self.bridge.get_connection_stats()
        return {'status': 'Bridge not initialized'}
    
    def closeEvent(self, event):
        """Clean up on window close."""
        try:
            if hasattr(self, 'bridge'):
                self.bridge.disconnect()
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
    print("SPYDER DASHBOARD WITH IB DATA BRIDGE (ib_async)")
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
    
    print("\n🚀 Launching dashboard with real market data...")
    
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