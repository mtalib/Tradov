#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderR05_LiveDashboard.py
Group: R (Runtime)
Purpose: Live Dashboard launcher with proper IB connection
Author: Mohamed Talib
Date Created: 2025-01-10
Last Updated: 2025-01-16 Time: 11:00:00

Description:
    This module provides a runtime wrapper for the Trading Dashboard that
    automatically connects to IB Gateway on startup, checks for both paper
    and live trading ports, and switches from simulation to real market data.
    It maintains connection health and auto-reconnects if needed.
"""

# ==============================================================================
# IMPORTS
# ==============================================================================
import os
import sys
import socket
import threading
from datetime import datetime
from pathlib import Path

# Add Spyder directory to path
SPYDER_HOME = Path(__file__).parent.parent
sys.path.insert(0, str(SPYDER_HOME))

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QTimer, pyqtSignal, QObject

# Import the base dashboard
from SpyderG_GUI.SpyderG05_TradingDashboard import TradingDashboard

# Try to import ib_async for real connection
try:
    from ib_async import IB
    IB_ASYNC_AVAILABLE = True
except ImportError:
    IB_ASYNC_AVAILABLE = False
    print("Warning: ib_async not available, will use socket check only")

# ==============================================================================
# CONSTANTS
# ==============================================================================
IB_PAPER_PORT = 4002
IB_LIVE_PORT = 4001
IB_HOST = "127.0.0.1"
CLIENT_ID = 123  # Use standard client ID
CONNECTION_CHECK_INTERVAL = 5000  # 5 seconds
INITIAL_CONNECTION_DELAY = 1000  # 1 second

# ==============================================================================
# LIVE DASHBOARD CLASS
# ==============================================================================
class LiveDashboard(TradingDashboard):
    """Enhanced dashboard with automatic IB connection on startup"""
    
    def __init__(self):
        super().__init__()
        
        # Stop simulation timer immediately
        if hasattr(self, "timer"):
            self.timer.stop()
            
        # Connection state
        self.ib_port = None
        self.ib_mode = None
        self.connection_attempts = 0
        self.max_connection_attempts = 3
        
        # Set up connection check timer
        self.connection_check_timer = QTimer()
        self.connection_check_timer.timeout.connect(self._check_connection_health)
        self.connection_check_timer.setInterval(CONNECTION_CHECK_INTERVAL)
        
        # Update UI to show attempting connection
        self._update_connection_status(False, "Initializing...")
        
        # Attempt connection after GUI is ready
        QTimer.singleShot(INITIAL_CONNECTION_DELAY, self._attempt_ib_connection)
        
    def _check_ib_gateway_port(self):
        """Check which IB Gateway port is available"""
        # Check paper port first
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        
        if sock.connect_ex((IB_HOST, IB_PAPER_PORT)) == 0:
            sock.close()
            return IB_PAPER_PORT, "PAPER"
        sock.close()
        
        # Check live port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        
        if sock.connect_ex((IB_HOST, IB_LIVE_PORT)) == 0:
            sock.close()
            return IB_LIVE_PORT, "LIVE"
        sock.close()
        
        return None, None
    
    def _attempt_ib_connection(self):
        """Attempt to connect to IB Gateway"""
        self.connection_attempts += 1
        
        # Check which port is available
        port, mode = self._check_ib_gateway_port()
        
        if port is not None:
            self.ib_port = port
            self.ib_mode = mode
            
            # Connection successful
            self._on_ib_connected(port, mode)
            
            # Start health monitoring
            self.connection_check_timer.start()
            
        else:
            # No IB Gateway found
            self._on_ib_disconnected()
            
            if self.connection_attempts < self.max_connection_attempts:
                # Retry connection
                self.add_system_log(f"Connection attempt {self.connection_attempts} failed, retrying...")
                QTimer.singleShot(3000, self._attempt_ib_connection)
            else:
                # Show error after max attempts
                self._show_connection_error()
    
    def _on_ib_connected(self, port, mode):
        """Handle successful IB connection"""
        self.ib_connected = True
        self.connection_attempts = 0
        
        # Update UI
        self._update_connection_status(True, f"IB CONNECTED ({mode})")
        
        # Log connection
        self.add_system_log(f"✅ Connected to IB Gateway - {mode} mode on port {port}")
        self.add_automation_log(f"IB Gateway connection established - {mode} trading")
        
        # If we have the ib_async worker, trigger it
        if hasattr(self, 'ib_worker') and hasattr(self.ib_worker, 'connect_to_ib'):
            try:
                # Use the detected port
                self.ib_worker.connect_to_ib(IB_HOST, port, CLIENT_ID)
                self.add_system_log("Market data feed activated")
            except Exception as e:
                self.add_system_log(f"Warning: Could not activate data feed: {e}")
        
        # Request market data for key symbols
        self._request_initial_market_data()
        
    def _on_ib_disconnected(self):
        """Handle IB disconnection"""
        self.ib_connected = False
        
        # Update UI
        self._update_connection_status(False, "IB DISCONNECTED")
        
        # Log disconnection
        self.add_system_log("🔌 Disconnected from IB Gateway")
        
    def _update_connection_status(self, connected, status_text):
        """Update connection UI elements"""
        if hasattr(self, "connection_label"):
            self.connection_label.setText(status_text)
            if connected:
                self.connection_label.setStyleSheet("color: #00ff00;")
            else:
                self.connection_label.setStyleSheet("color: #ff0000;")
                
        if hasattr(self, "connection_dot"):
            if connected:
                self.connection_dot.setStyleSheet("color: #00ff00;")
            else:
                self.connection_dot.setStyleSheet("color: #ff0000;")
    
    def _check_connection_health(self):
        """Periodic connection health check"""
        if self.ib_port is None:
            return
            
        # Check if port is still open
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((IB_HOST, self.ib_port))
        sock.close()
        
        if result != 0:
            # Connection lost
            self._on_ib_disconnected()
            self.add_system_log("Connection lost - attempting to reconnect...")
            
            # Stop health check during reconnection
            self.connection_check_timer.stop()
            
            # Reset connection attempts and try again
            self.connection_attempts = 0
            QTimer.singleShot(3000, self._attempt_ib_connection)
    
    def _request_initial_market_data(self):
        """Request market data for key symbols"""
        # Request data for main symbols
        key_symbols = ["SPY", "VIX", "/ES"]
        
        for symbol in key_symbols:
            self.add_system_log(f"Requesting market data for {symbol}")
        
        # If market is closed, note that we'll get last traded data
        from datetime import datetime
        now = datetime.now()
        if now.weekday() >= 5 or now.hour >= 16 or now.hour < 9:
            self.add_automation_log("Market closed - displaying last traded data")
            self.add_automation_log("ES Futures provide 24/5 pricing reference")
    
    def _show_connection_error(self):
        """Show connection error dialog"""
        self.add_system_log("❌ Failed to connect to IB Gateway after multiple attempts")
        
        # Only show dialog once
        if not hasattr(self, "_error_dialog_shown"):
            self._error_dialog_shown = True
            
            QMessageBox.warning(
                self,
                "IB Gateway Connection Failed",
                "Could not connect to IB Gateway.\n\n"
                "Please ensure:\n"
                "1. IB Gateway is running\n"
                "2. You are logged in\n"
                "3. API connections are enabled\n"
                "4. 'Enable ActiveX and Socket Clients' is checked\n\n"
                "The dashboard will continue in simulation mode.\n"
                "Click START TRADING to retry connection."
            )
            
            # Allow manual retry via START button
            if hasattr(self, "start_btn"):
                # Override the start button to retry connection
                self.start_btn.clicked.disconnect()
                self.start_btn.clicked.connect(self._manual_connection_retry)
    
    def _manual_connection_retry(self):
        """Manual connection retry from START button"""
        self.add_system_log("Manual connection retry initiated...")
        self.connection_attempts = 0
        self._attempt_ib_connection()
    
    def closeEvent(self, event):
        """Handle window close event"""
        # Stop timers
        self.connection_check_timer.stop()
        
        # Disconnect from IB if connected
        if hasattr(self, 'ib_worker') and hasattr(self.ib_worker, 'disconnect'):
            self.ib_worker.disconnect()
        
        # Call parent close event
        super().closeEvent(event)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("Spyder Trading Dashboard")
    app.setOrganizationName("Spyder Trading System")
    
    # Create and show dashboard
    dashboard = LiveDashboard()
    dashboard.show()
    
    # Run application
    sys.exit(app.exec())
