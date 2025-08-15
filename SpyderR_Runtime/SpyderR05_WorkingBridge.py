#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderR05_WorkingBridge.py
Group: R (Runtime)
Purpose: Working IB Bridge with proper client IDs and fallback
Author: Mohamed Talib
Date Created: 2025-01-16
Last Updated: 2025-01-16 Time: 00:40:00

Description:
    This module provides a working bridge to IB Gateway using correct client IDs
    and includes proper fallback to simulation if IB connection fails. Tests
    multiple client IDs starting from 3 (as 0-2 are reserved by IB).
"""

# ==============================================================================
# IMPORTS
# ==============================================================================
import sys
import os
import socket
import time
import threading
from pathlib import Path
from datetime import datetime

# Add Spyder to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QTimer, QObject, pyqtSignal

# Import dashboard
from SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard

# Try importing IB
try:
    from ib_insync import IB, Stock, Index, Future, Contract, util
    IB_AVAILABLE = True
except ImportError:
    IB_AVAILABLE = False
    print("Warning: ib_insync not available")

# ==============================================================================
# CONSTANTS
# ==============================================================================
IB_HOST = "127.0.0.1"
IB_PORT = 4002  # Paper trading

# Client IDs - MUST be 3 or higher for custom applications
VALID_CLIENT_IDS = [3, 10, 123, 999, 1234]  # Start from 3!

# ==============================================================================
# CONNECTION TESTER
# ==============================================================================
class IBConnectionTester:
    """Test IB Gateway connection with multiple client IDs"""
    
    @staticmethod
    def check_port_open(port=IB_PORT):
        """Check if port is open"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((IB_HOST, port))
        sock.close()
        return result == 0
    
    @staticmethod
    def find_working_client_id():
        """Find a working client ID"""
        if not IB_AVAILABLE:
            return None
            
        print("Testing IB Gateway connection...")
        
        # First check if port is open
        if not IBConnectionTester.check_port_open():
            print("❌ Port 4002 is not open - IB Gateway not running")
            return None
        
        print("✅ Port 4002 is open")
        
        # Try each client ID
        for client_id in VALID_CLIENT_IDS:
            print(f"Testing client ID {client_id}...", end=" ")
            
            ib = IB()
            try:
                # Short timeout for testing
                ib.connect(IB_HOST, IB_PORT, clientId=client_id, readonly=False, timeout=5)
                
                if ib.isConnected():
                    print(f"✅ SUCCESS!")
                    ib.disconnect()
                    return client_id
                    
            except Exception as e:
                error_str = str(e)
                if "already in use" in error_str.lower():
                    print(f"❌ In use")
                elif "timeout" in error_str.lower():
                    print(f"❌ Timeout")
                else:
                    print(f"❌ Failed")
            
            finally:
                if ib.isConnected():
                    ib.disconnect()
            
            time.sleep(0.5)  # Small delay between attempts
        
        print("\n❌ No working client ID found")
        print("IB Gateway API is not responding properly")
        return None

# ==============================================================================
# SIMULATED DATA PROVIDER
# ==============================================================================
class SimulatedDataProvider(QObject):
    """Provides simulated market data when IB is not available"""
    
    data_update = pyqtSignal(str, float, float, float)
    
    def __init__(self):
        super().__init__()
        self.base_prices = {
            'SPY': 585.25,
            'SPX': 5850.75,
            '/ES': 5852.50,
            'VIX': 15.32,
            'VIX9D': 14.80,
            'VXV': 16.20,
            'VVIX': 82.45,
            'UVXY': 22.18,
            'QQQ': 485.92,
            'IWM': 225.18,
            'DIA': 425.33,
            'TLT': 92.45,
            'GLD': 195.82,
            'DXY': 103.25,
            'LQD': 105.12,
        }
        
        self.timer = QTimer()
        self.timer.timeout.connect(self._generate_update)
        self.timer.setInterval(3000)
        
    def start(self):
        """Start generating simulated data"""
        self.timer.start()
        # Initial update
        self._generate_update()
        
    def stop(self):
        """Stop generating data"""
        self.timer.stop()
        
    def _generate_update(self):
        """Generate simulated price updates"""
        import random
        
        for symbol, base_price in self.base_prices.items():
            # Random walk
            change_pct = random.uniform(-0.5, 0.5)
            change = base_price * (change_pct / 100)
            new_price = base_price + change
            
            self.data_update.emit(symbol, new_price, change, change_pct)

# ==============================================================================
# IB DATA PROVIDER
# ==============================================================================
class IBDataProvider(QObject):
    """Provides real market data from IB Gateway"""
    
    data_update = pyqtSignal(str, float, float, float)
    status_update = pyqtSignal(str)
    
    def __init__(self, client_id):
        super().__init__()
        self.client_id = client_id
        self.ib = IB()
        self.connected = False
        self.tickers = {}
        self.contracts = self._get_contracts()
        
        self.timer = QTimer()
        self.timer.timeout.connect(self._fetch_data)
        self.timer.setInterval(2000)
        
    def _get_contracts(self):
        """Get contract definitions"""
        return {
            'SPY': Stock('SPY', 'SMART', 'USD'),
            'SPX': Index('SPX', 'CBOE'),
            '/ES': Future('ES', '202503', 'CME'),
            'VIX': Index('VIX', 'CBOE'),
            'QQQ': Stock('QQQ', 'SMART', 'USD'),
            'IWM': Stock('IWM', 'SMART', 'USD'),
            'DIA': Stock('DIA', 'SMART', 'USD'),
            'TLT': Stock('TLT', 'SMART', 'USD'),
            'GLD': Stock('GLD', 'SMART', 'USD'),
        }
    
    def connect(self):
        """Connect to IB Gateway"""
        try:
            self.ib.connect(IB_HOST, IB_PORT, clientId=self.client_id, readonly=False, timeout=10)
            
            if self.ib.isConnected():
                self.connected = True
                self.status_update.emit(f"Connected with Client ID {self.client_id}")
                
                # Request delayed data
                self.ib.reqMarketDataType(3)
                
                # Subscribe to symbols
                self._subscribe()
                
                # Start updates
                self.timer.start()
                return True
                
        except Exception as e:
            self.status_update.emit(f"Connection failed: {str(e)}")
            return False
    
    def _subscribe(self):
        """Subscribe to market data"""
        for symbol, contract in self.contracts.items():
            try:
                self.ib.qualifyContracts(contract)
                ticker = self.ib.reqMktData(contract, '', False, False)
                self.tickers[symbol] = ticker
                print(f"  Subscribed to {symbol}")
            except:
                pass
    
    def _fetch_data(self):
        """Fetch and emit data updates"""
        if not self.connected:
            return
            
        for symbol, ticker in self.tickers.items():
            if ticker.last and ticker.last > 0:
                price = ticker.last
                change = 0
                change_pct = 0
                
                if ticker.close and ticker.close > 0:
                    change = price - ticker.close
                    change_pct = (change / ticker.close) * 100
                
                self.data_update.emit(symbol, price, change, change_pct)
    
    def disconnect(self):
        """Disconnect from IB"""
        self.timer.stop()
        if self.ib.isConnected():
            self.ib.disconnect()
        self.connected = False

# ==============================================================================
# ENHANCED DASHBOARD WITH SMART DATA PROVIDER
# ==============================================================================
class SmartDashboard(SpyderTradingDashboard):
    """Dashboard that automatically uses IB or simulation"""
    
    def __init__(self):
        super().__init__()
        
        # Stop default simulation
        if hasattr(self, "timer"):
            self.timer.stop()
        
        self.data_provider = None
        
        # Initialize after GUI is ready
        QTimer.singleShot(1000, self._initialize_data)
    
    def _initialize_data(self):
        """Initialize data provider (IB or simulation)"""
        self.add_system_log("Checking IB Gateway connection...")
        
        # Test IB connection
        working_client_id = IBConnectionTester.find_working_client_id()
        
        if working_client_id and IB_AVAILABLE:
            # Use real IB data
            self.add_system_log(f"✅ Found working Client ID: {working_client_id}")
            self.add_automation_log("Connecting to IB Gateway for real market data")
            
            self.data_provider = IBDataProvider(working_client_id)
            self.data_provider.data_update.connect(self._update_symbol_display)
            self.data_provider.status_update.connect(self.add_system_log)
            
            if self.data_provider.connect():
                self._update_connection_status(True, f"IB CONNECTED (Client {working_client_id})")
                self.add_automation_log("✅ Receiving real market data from IB Gateway")
            else:
                self._fallback_to_simulation()
        else:
            # Use simulation
            self._fallback_to_simulation()
    
    def _fallback_to_simulation(self):
        """Fall back to simulated data"""
        self.add_system_log("❌ IB Gateway not available")
        self.add_automation_log("Using simulated market data")
        
        self.data_provider = SimulatedDataProvider()
        self.data_provider.data_update.connect(self._update_symbol_display)
        self.data_provider.start()
        
        self._update_connection_status(False, "SIMULATION MODE")
    
    def _update_symbol_display(self, symbol, price, change, change_pct):
        """Update symbol in dashboard"""
        try:
            # Use dashboard's update method
            self.update_symbol(symbol, price, change, change_pct)
            
            # Also update displays directly
            if hasattr(self, 'symbol_displays') and symbol in self.symbol_displays:
                display = self.symbol_displays[symbol]
                if display:
                    display['price'].setText(f"${price:.2f}")
                    
                    color = "#00ff00" if change >= 0 else "#ff0000"
                    sign = "+" if change >= 0 else ""
                    
                    display['change'].setText(f"{sign}{change:.2f} {sign}{change_pct:.2f}%")
                    display['change'].setStyleSheet(f"color: {color};")
                    
        except Exception as e:
            print(f"Error updating {symbol}: {e}")
    
    def _update_connection_status(self, connected, text):
        """Update connection status display"""
        if hasattr(self, 'connection_label'):
            self.connection_label.setText(text)
            color = "#00ff00" if connected else "#ffaa00"  # Green or orange
            self.connection_label.setStyleSheet(f"color: {color};")
        
        if hasattr(self, 'connection_dot'):
            color = "#00ff00" if connected else "#ffaa00"
            self.connection_dot.setStyleSheet(f"color: {color};")
    
    def closeEvent(self, event):
        """Clean up on close"""
        if self.data_provider:
            if hasattr(self.data_provider, 'disconnect'):
                self.data_provider.disconnect()
            elif hasattr(self.data_provider, 'stop'):
                self.data_provider.stop()
        super().closeEvent(event)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Initialize IB event loop if available
    if IB_AVAILABLE:
        util.startLoop()
    
    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("Spyder Trading System")
    
    print("=" * 60)
    print("SPYDER SMART DASHBOARD")
    print("=" * 60)
    print("Features:")
    print("• Tests Client IDs 3+ (IB requirement)")
    print("• Automatically finds working connection")
    print("• Falls back to simulation if IB unavailable")
    print("• Shows real prices when connected")
    print("=" * 60)
    print()
    
    # Create and show dashboard
    dashboard = SmartDashboard()
    dashboard.show()
    
    print("Dashboard launched!")
    print("Testing IB Gateway connection...")
    print()
    
    # Run application
    sys.exit(app.exec())
