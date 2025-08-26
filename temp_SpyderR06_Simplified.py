#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SIMPLIFIED VERSION - Debug threading and connection issues
"""

import sys
import os
import time
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Any

# Add Spyder to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer, QObject, pyqtSignal, QThread

# Import dashboard
from SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard

# Import IB with ib_async
try:
    from ib_async import IB, Stock, util
    IB_AVAILABLE = True
except ImportError:
    IB_AVAILABLE = False
    print("Warning: ib_async not available")

# Constants
IB_HOST = "127.0.0.1"
IB_PORT = 4002
MASTER_CLIENT_ID = 2

class SimpleIBConnection(QThread):
    """Simple single-client connection in separate thread."""
    
    # Signals
    connected = pyqtSignal(bool, str)
    data_received = pyqtSignal(str, float)
    log_message = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.ib = None
        self.should_stop = False
        self.is_connected = False
    
    def run(self):
        """Thread execution - connect and maintain connection."""
        try:
            self.log_message.emit("🔗 Connecting single client (Master ID 2)...")
            
            self.ib = IB()
            self.ib.connect(IB_HOST, IB_PORT, clientId=MASTER_CLIENT_ID, timeout=15)
            
            if self.ib.isConnected():
                self.is_connected = True
                self.connected.emit(True, "MASTER CLIENT CONNECTED")
                self.log_message.emit("✅ Master Client connected successfully!")
                
                # Request account data
                self.ib.reqAccountSummary(9001, 'All', 'NetLiquidation,BuyingPower')
                
                # Subscribe to SPY for testing
                spy = Stock('SPY', 'SMART', 'USD')
                contracts = self.ib.qualifyContracts(spy)
                if contracts:
                    ticker = self.ib.reqMktData(contracts[0], '', False, False)
                    self.log_message.emit("📊 SPY data subscription active")
                
                # Keep connection alive
                while not self.should_stop and self.ib.isConnected():
                    self.ib.sleep(1)  # Process IB events
                    
            else:
                self.connected.emit(False, "CONNECTION FAILED")
                self.log_message.emit("❌ Connection failed")
                
        except Exception as e:
            self.connected.emit(False, f"ERROR: {str(e)}")
            self.log_message.emit(f"❌ Connection error: {e}")
        
        finally:
            if self.ib and self.ib.isConnected():
                self.ib.disconnect()
            self.is_connected = False
    
    def stop_connection(self):
        """Stop the connection thread."""
        self.should_stop = True
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()


class SimplifiedDashboard(SpyderTradingDashboard):
    """Simplified dashboard to test single client connection."""
    
    def __init__(self):
        super().__init__()
        
        # Stop simulation timer
        if hasattr(self, "timer"):
            self.timer.stop()
        
        # Create connection thread
        self.ib_connection = SimpleIBConnection()
        
        # Connect signals
        self.ib_connection.connected.connect(self._handle_connection_status)
        self.ib_connection.log_message.connect(self.add_system_log)
        
        self.add_system_log("Simplified Dashboard initialized")
        
        # Start connection after short delay
        QTimer.singleShot(2000, self._start_connection)
    
    def _start_connection(self):
        """Start the IB connection in separate thread."""
        self.add_system_log("🚀 Starting simplified IB connection...")
        self.ib_connection.start()
    
    def _handle_connection_status(self, connected: bool, status: str):
        """Handle connection status updates - MAIN THREAD."""
        if connected:
            self.add_automation_log(f"✅ {status}")
            self.setWindowTitle("Spyder Dashboard - LIVE (Single Client)")
        else:
            self.add_automation_log(f"❌ {status}")
            self.setWindowTitle("Spyder Dashboard - FAILED")
            
            # Fallback to simulation
            self.add_system_log("Falling back to simulation mode...")
            if hasattr(self, "timer"):
                QTimer.singleShot(3000, lambda: self.timer.start())
    
    def closeEvent(self, event):
        """Clean shutdown."""
        try:
            if hasattr(self, 'ib_connection'):
                self.ib_connection.stop_connection()
                self.ib_connection.wait(3000)  # Wait max 3 seconds
            
            super().closeEvent(event)
            
        except Exception as e:
            print(f"Error during close: {e}")
            event.accept()


def main():
    """Simplified main for testing."""
    print("=" * 60)
    print("SIMPLIFIED SPYDER DASHBOARD - SINGLE CLIENT TEST")
    print("=" * 60)
    print(f"ib_async available: {IB_AVAILABLE}")
    print(f"Target: {IB_HOST}:{IB_PORT}")
    print(f"Client ID: {MASTER_CLIENT_ID} (Master)")
    print("Testing single client connection only")
    print("=" * 60)
    
    if IB_AVAILABLE:
        try:
            util.startLoop()
            print("✅ ib_async event loop started")
        except Exception as e:
            print(f"⚠️ Event loop warning: {e}")
    
    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("Spyder Simplified Test")
    
    print("\n🚀 Launching simplified dashboard...")
    print("This will test:")
    print("1. Single client connection (ID 2)")
    print("2. Basic account data request")
    print("3. SPY market data subscription")
    print("4. Thread-safe GUI updates")
    print("=" * 60)
    
    # Create and show dashboard
    dashboard = SimplifiedDashboard()
    dashboard.show()
    
    # Run application
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
