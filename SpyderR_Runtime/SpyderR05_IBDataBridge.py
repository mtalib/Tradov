#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderR05_IBDataBridge.py
Group: R (Runtime)
Purpose: IB Gateway Data Bridge - Properly fetches and injects real market data
Author: Mohamed Talib
Date Created: 2025-01-16
Last Updated: 2025-01-16 Time: 00:10:00

Description:
    This module creates a proper bridge between IB Gateway and the Spyder dashboard.
    It establishes a real IB connection using ib_insync and injects live market data
    directly into the dashboard's display elements, bypassing the connection issues.
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

# Import IB
from ib_insync import IB, Stock, Index, Future, Contract, util

# ==============================================================================
# CONSTANTS
# ==============================================================================
IB_HOST = "127.0.0.1"
IB_PORT = 4002  # Paper trading
CLIENT_ID = 777  # Unique ID to avoid conflicts

# Symbol mappings
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
}

# ==============================================================================
# IB DATA BRIDGE
# ==============================================================================
class IBDataBridge(QObject):
    """Bridge between IB Gateway and Dashboard"""
    
    data_update = pyqtSignal(str, float, float, float)  # symbol, price, change, change_pct
    status_update = pyqtSignal(str)
    
    def __init__(self, dashboard):
        super().__init__()
        self.dashboard = dashboard
        self.ib = None
        self.connected = False
        self.tickers = {}
        self.last_prices = {}
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._fetch_and_update)
        self.update_timer.setInterval(2000)  # 2 seconds
        
    def connect_to_ib(self):
        """Establish IB connection"""
        try:
            # Create new IB instance
            self.ib = IB()
            
            # Connect with specific settings
            print(f"Connecting to IB Gateway at {IB_HOST}:{IB_PORT}...")
            self.ib.connect(IB_HOST, IB_PORT, clientId=CLIENT_ID, readonly=False, timeout=15)
            
            if not self.ib.isConnected():
                raise Exception("Connection failed")
            
            print("✅ Connected to IB Gateway!")
            self.connected = True
            
            # Update dashboard status
            self._update_dashboard_status(True, "IB CONNECTED (PAPER)")
            self.dashboard.add_system_log("✅ Real IB connection established")
            
            # Start subscribing to symbols
            self._subscribe_symbols()
            
            # Start update timer
            self.update_timer.start()
            
            return True
            
        except Exception as e:
            print(f"❌ IB Connection failed: {e}")
            self._update_dashboard_status(False, "IB DISCONNECTED")
            self.dashboard.add_system_log(f"❌ IB connection failed: {str(e)}")
            return False
    
    def _subscribe_symbols(self):
        """Subscribe to market data for all symbols"""
        print("Subscribing to market data...")
        
        # Request delayed data if real-time not available
        self.ib.reqMarketDataType(3)  # 3 = delayed data
        
        for symbol, contract in SYMBOL_CONTRACTS.items():
            try:
                # Qualify contract
                self.ib.qualifyContracts(contract)
                
                # Request market data
                ticker = self.ib.reqMktData(contract, '', False, False)
                self.tickers[symbol] = ticker
                
                print(f"  ✓ Subscribed to {symbol}")
                self.dashboard.add_system_log(f"Subscribed to {symbol}")
                
                # Small delay to avoid overwhelming API
                time.sleep(0.1)
                
            except Exception as e:
                print(f"  ✗ Failed to subscribe to {symbol}: {e}")
    
    def _fetch_and_update(self):
        """Fetch latest prices and update dashboard"""
        if not self.connected or not self.ib.isConnected():
            return
        
        updates_made = 0
        
        for symbol, ticker in self.tickers.items():
            try:
                # Get price (try multiple fields)
                price = None
                if ticker.last and ticker.last > 0:
                    price = ticker.last
                elif ticker.close and ticker.close > 0:
                    price = ticker.close
                elif ticker.bid and ticker.bid > 0:
                    price = ticker.bid
                else:
                    continue
                
                # Calculate change
                if ticker.close and ticker.close > 0:
                    change = price - ticker.close
                    change_pct = (change / ticker.close) * 100
                elif symbol in self.last_prices:
                    change = price - self.last_prices[symbol]
                    change_pct = (change / self.last_prices[symbol]) * 100
                else:
                    change = 0
                    change_pct = 0
                
                # Store last price
                self.last_prices[symbol] = price
                
                # Update dashboard
                self._update_dashboard_symbol(symbol, price, change, change_pct)
                updates_made += 1
                
            except Exception as e:
                pass  # Silent fail for individual symbols
        
        if updates_made > 0:
            print(f"Updated {updates_made} symbols")
    
    def _update_dashboard_symbol(self, symbol, price, change, change_pct):
        """Update symbol in dashboard display"""
        try:
            # Update using dashboard's method
            self.dashboard.update_symbol(symbol, price, change, change_pct)
            
            # Also update the symbol_displays directly if they exist
            if hasattr(self.dashboard, 'symbol_displays'):
                if symbol in self.dashboard.symbol_displays:
                    display = self.dashboard.symbol_displays[symbol]
                    if display:
                        # Update price
                        display['price'].setText(f"${price:.2f}")
                        
                        # Update change with color
                        if change >= 0:
                            color = "#00ff00"
                            sign = "+"
                        else:
                            color = "#ff0000"
                            sign = ""
                        
                        change_text = f"{sign}{change:.2f} {sign}{change_pct:.2f}%"
                        display['change'].setText(change_text)
                        display['change'].setStyleSheet(f"color: {color};")
                        
        except Exception as e:
            print(f"Error updating {symbol}: {e}")
    
    def _update_dashboard_status(self, connected, text):
        """Update connection status in dashboard"""
        if hasattr(self.dashboard, 'connection_label'):
            self.dashboard.connection_label.setText(text)
            if connected:
                self.dashboard.connection_label.setStyleSheet("color: #00ff00;")
            else:
                self.dashboard.connection_label.setStyleSheet("color: #ff0000;")
        
        if hasattr(self.dashboard, 'connection_dot'):
            if connected:
                self.dashboard.connection_dot.setStyleSheet("color: #00ff00;")
            else:
                self.dashboard.connection_dot.setStyleSheet("color: #ff0000;")
    
    def disconnect(self):
        """Disconnect from IB"""
        self.update_timer.stop()
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
        self.connected = False

# ==============================================================================
# ENHANCED DASHBOARD
# ==============================================================================
class LiveDashboardWithBridge(SpyderTradingDashboard):
    """Dashboard with IB Data Bridge"""
    
    def __init__(self):
        super().__init__()
        
        # Stop simulation timer
        if hasattr(self, "timer"):
            self.timer.stop()
        
        # Create and connect bridge
        self.bridge = IBDataBridge(self)
        
        # Add menu item or button to manually connect
        self.add_system_log("Initializing IB Data Bridge...")
        
        # Connect after GUI is ready
        QTimer.singleShot(2000, self._connect_bridge)
    
    def _connect_bridge(self):
        """Connect the data bridge"""
        self.add_system_log("Attempting to connect to IB Gateway...")
        
        if self.bridge.connect_to_ib():
            self.add_automation_log("IB Data Bridge active - receiving real market data")
        else:
            self.add_automation_log("IB connection failed - check Gateway settings")
            self.add_system_log("Running in simulation mode")
            
            # Restart simulation
            if hasattr(self, "timer"):
                self.timer.start()
    
    def closeEvent(self, event):
        """Clean up on close"""
        if hasattr(self, 'bridge'):
            self.bridge.disconnect()
        super().closeEvent(event)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Initialize ib_insync event loop
    util.startLoop()
    
    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("Spyder Trading System")
    
    print("=" * 60)
    print("SPYDER DASHBOARD WITH IB DATA BRIDGE")
    print("=" * 60)
    print("Launching dashboard with real market data...")
    print()
    
    # Create and show dashboard
    dashboard = LiveDashboardWithBridge()
    dashboard.show()
    
    print("Dashboard launched!")
    print("Connecting to IB Gateway in 2 seconds...")
    print()
    print("If data doesn't appear:")
    print("1. Check IB Gateway is logged in")
    print("2. Verify port 4002 is correct")
    print("3. Try different client ID if needed")
    print("=" * 60)
    
    # Run application
    sys.exit(app.exec())
