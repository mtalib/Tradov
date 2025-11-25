#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderR_Runtime [Application Name] [Series Letter] [Series Name]
Module: SpyderR05_WorkingBridge.py [Application Name][Series Letter] [Module Number]_[Purpose].py
Purpose: Working IB Bridge with proper client IDs and fallback using ib_async
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-21 Time: 21:05:00

⚠️ DEPRECATION WARNING ⚠️
    This module is DEPRECATED and no longer used.

    Migration Status:
    - ❌ IBKR Gateway integration via ib_async is legacy code
    - ✅ System migrated to Tradier API (no gateway needed)
    - 🔧 Dashboard connectivity now uses Tradier + Polygon.io

    The Spyder system has transitioned to:
    - Tradier API for broker integration (SpyderB40_TradierClient.py)
    - Polygon.io for real-time market data (SpyderC25_PolygonDataHandler.py)
    - No IB Gateway required for operations

    This module remains for historical reference only.

Module Description:
    This module provides a working bridge to IB Gateway using ib_async for
    IB Gateway 10.37+ compatibility. It includes proper client ID management,
    connection testing with multiple client IDs, and fallback to simulation
    if IB connection fails. Tests multiple client IDs starting from 3 as
    0-2 are reserved by IB Gateway.

Key Features:
    - ib_async integration for IB Gateway 10.37+ compatibility
    - Multiple client ID testing (3, 10, 123, 999, 1234)
    - Automatic fallback to simulation mode on connection failure
    - PySide6 integration for dashboard connectivity
    - Proper connection status monitoring and reporting
    - Thread-safe operation with event handling

Dependencies:
    - ib_async: Modern Interactive Brokers API client
    - PySide6: GUI framework for dashboard integration
    - SpyderG_GUI: Dashboard components

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

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QTimer, QObject, Signal

# Import dashboard
from SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard

# ⚠️ DEPRECATED: ib_async integration is legacy code
# The Spyder system no longer uses IB Gateway or ib_async
# For broker integration, use SpyderB40_TradierClient instead
try:
    from ib_async import IB, Stock, Index, Future, Contract, util
    IB_AVAILABLE = True
except ImportError:
    IB_AVAILABLE = False
    print("Warning: ib_async not available (module deprecated)")
    print("Use Tradier API via SpyderB40_TradierClient for broker integration")

# ==============================================================================
# CONSTANTS
# ==============================================================================
IB_HOST = "127.0.0.1"
IB_PORT = 4002  # Paper trading

# Client IDs - MUST be 3 or higher for custom applications
VALID_CLIENT_IDS = [3, 10, 123, 999, 1234]  # Start from 3!

# Connection settings
CONNECTION_TIMEOUT = 15
MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY = 2

# ==============================================================================
# WORKING BRIDGE CLASS
# ==============================================================================

class WorkingIBBridge(QObject):
    """
    Working IB Bridge with ib_async integration.
    
    This class provides a robust connection to IB Gateway with automatic
    client ID testing, connection validation, and fallback handling.
    """
    
    # Signals for connection status
    connection_established = Signal(int)  # client_id
    connection_failed = Signal(str)       # error_message
    fallback_activated = Signal()         # simulation mode
    
    def __init__(self, dashboard: SpyderTradingDashboard):
        """
        Initialize the Working IB Bridge.
        
        Args:
            dashboard: Reference to the trading dashboard
        """
        super().__init__()
        self.dashboard = dashboard
        self.ib_client = None
        self.connected = False
        self.active_client_id = None
        self.connection_attempt = 0
        
        # Connection status tracking
        self.last_connection_attempt = None
        self.last_successful_connection = None
        self.total_connection_attempts = 0
        
        self.dashboard.add_system_log("WorkingIBBridge initialized with ib_async")
    
    def check_gateway_availability(self) -> bool:
        """
        Check if IB Gateway is available on the specified port.
        
        Returns:
            bool: True if Gateway is reachable, False otherwise
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((IB_HOST, IB_PORT))
            sock.close()
            
            if result == 0:
                self.dashboard.add_system_log(f"✅ IB Gateway detected on {IB_HOST}:{IB_PORT}")
                return True
            else:
                self.dashboard.add_system_log(f"❌ IB Gateway not reachable on {IB_HOST}:{IB_PORT}")
                return False
                
        except Exception as e:
            self.dashboard.add_system_log(f"❌ Gateway check failed: {e}")
            return False
    
    def test_client_id(self, client_id: int) -> bool:
        """
        Test connection with a specific client ID.
        
        Args:
            client_id: Client ID to test
            
        Returns:
            bool: True if connection successful, False otherwise
        """
        if not IB_AVAILABLE:
            self.dashboard.add_system_log("❌ ib_async not available")
            return False
        
        try:
            self.dashboard.add_system_log(f"Testing client ID {client_id}...")
            
            # Create IB instance
            test_ib = IB()
            
            # Attempt connection
            test_ib.connect(
                host=IB_HOST,
                port=IB_PORT,
                clientId=client_id,
                timeout=CONNECTION_TIMEOUT,
                readonly=True  # Read-only for testing
            )
            
            if test_ib.isConnected():
                self.dashboard.add_system_log(f"✅ Client ID {client_id} successful")
                
                # Store the working connection
                self.ib_client = test_ib
                self.active_client_id = client_id
                self.connected = True
                self.last_successful_connection = datetime.now()
                
                return True
            else:
                test_ib.disconnect()
                return False
                
        except Exception as e:
            self.dashboard.add_system_log(f"❌ Client ID {client_id} failed: {e}")
            try:
                test_ib.disconnect()
            except Exception as disconnect_error:
                # Log disconnect failure but don't propagate
                self.dashboard.add_system_log(f"⚠️ Disconnect failed: {disconnect_error}")
            return False
    
    def attempt_connection(self) -> bool:
        """
        Attempt to establish IB connection with multiple client IDs.
        
        Returns:
            bool: True if connection established, False otherwise
        """
        self.last_connection_attempt = datetime.now()
        self.total_connection_attempts += 1
        
        if not IB_AVAILABLE:
            self.dashboard.add_automation_log("❌ ib_async not available - using simulation")
            self.connection_failed.emit("ib_async not available")
            return False
        
        # Check if Gateway is available first
        if not self.check_gateway_availability():
            self.dashboard.add_automation_log("❌ IB Gateway not reachable - using simulation")
            self.connection_failed.emit("IB Gateway not reachable")
            return False
        
        # Test each client ID
        self.dashboard.add_automation_log("🔍 Testing IB client connections...")
        
        for attempt in range(MAX_RETRY_ATTEMPTS):
            if attempt > 0:
                self.dashboard.add_system_log(f"Retry attempt {attempt + 1}/{MAX_RETRY_ATTEMPTS}")
                time.sleep(RETRY_DELAY)
            
            for client_id in VALID_CLIENT_IDS:
                if self.test_client_id(client_id):
                    self.dashboard.add_automation_log(
                        f"✅ IB Bridge connected (Client {client_id}) - LIVE DATA ACTIVE"
                    )
                    self.connection_established.emit(client_id)
                    return True
                
                # Small delay between client ID tests
                time.sleep(0.5)
        
        # All attempts failed
        self.dashboard.add_automation_log("❌ All IB connection attempts failed - using simulation")
        self.connection_failed.emit("All client IDs failed")
        return False
    
    def setup_event_handlers(self):
        """Set up IB event handlers for monitoring."""
        if not self.ib_client:
            return
        
        def on_connected():
            self.dashboard.add_system_log(f"✅ IB connected with client {self.active_client_id}")
        
        def on_disconnected():
            self.connected = False
            self.dashboard.add_system_log("❌ IB disconnected")
            self.dashboard.add_automation_log("❌ IB connection lost - switching to simulation")
        
        def on_error(reqId, errorCode, errorString, contract):
            self.dashboard.add_system_log(f"IB Error {errorCode}: {errorString}")
        
        # Connect event handlers
        self.ib_client.connectedEvent += on_connected
        self.ib_client.disconnectedEvent += on_disconnected
        self.ib_client.errorEvent += on_error
    
    def get_connection_status(self) -> dict:
        """
        Get detailed connection status information.
        
        Returns:
            dict: Connection status details
        """
        return {
            'connected': self.connected,
            'ib_available': IB_AVAILABLE,
            'active_client_id': self.active_client_id,
            'last_connection_attempt': self.last_connection_attempt,
            'last_successful_connection': self.last_successful_connection,
            'total_attempts': self.total_connection_attempts,
            'gateway_host': IB_HOST,
            'gateway_port': IB_PORT,
            'api_version': 'ib_async'
        }
    
    def start_monitoring(self):
        """Start connection monitoring."""
        if self.connected and self.ib_client:
            self.setup_event_handlers()
            self.dashboard.add_system_log("✅ IB connection monitoring started")
    
    def disconnect(self):
        """Disconnect from IB Gateway."""
        if self.ib_client and self.connected:
            try:
                self.ib_client.disconnect()
                self.connected = False
                self.active_client_id = None
                self.dashboard.add_system_log("IB Bridge disconnected")
            except Exception as e:
                self.dashboard.add_system_log(f"Error disconnecting: {e}")

# ==============================================================================
# DASHBOARD WITH WORKING BRIDGE
# ==============================================================================

class DashboardWithWorkingBridge(SpyderTradingDashboard):
    """Dashboard enhanced with Working IB Bridge functionality."""
    
    def __init__(self):
        super().__init__()
        
        # Stop any existing simulation timer
        if hasattr(self, "timer"):
            self.timer.stop()
        
        # Create and setup working bridge
        self.working_bridge = WorkingIBBridge(self)
        
        # Connect bridge signals
        self.working_bridge.connection_established.connect(self._on_connection_established)
        self.working_bridge.connection_failed.connect(self._on_connection_failed)
        self.working_bridge.fallback_activated.connect(self._on_fallback_activated)
        
        self.add_system_log("Dashboard initialized with Working IB Bridge (ib_async)")
        
        # Start connection attempt after GUI is ready
        QTimer.singleShot(2000, self._initiate_connection)
    
    def _initiate_connection(self):
        """Initiate the IB connection process."""
        self.add_automation_log("🚀 Initiating IB Gateway connection...")
        
        # Run connection attempt in separate thread to avoid blocking GUI
        connection_thread = threading.Thread(
            target=self._connection_worker,
            name="IBConnectionWorker",
            daemon=True
        )
        connection_thread.start()
    
    def _connection_worker(self):
        """Worker thread for IB connection attempts."""
        try:
            success = self.working_bridge.attempt_connection()
            if success:
                # Connection successful - start monitoring
                self.working_bridge.start_monitoring()
            else:
                # Connection failed - emit fallback signal
                self.working_bridge.fallback_activated.emit()
        except Exception as e:
            self.add_system_log(f"Connection worker error: {e}")
            self.working_bridge.fallback_activated.emit()
    
    def _on_connection_established(self, client_id: int):
        """Handle successful IB connection."""
        self.add_automation_log(f"🎯 LIVE MODE ACTIVE - Client {client_id}")
        self.add_system_log(f"Real market data streaming via ib_async")
        
        # Update window title to show live status
        self.setWindowTitle(f"Spyder Trading Dashboard - LIVE (Client {client_id})")
        
        # Here you would typically:
        # 1. Start market data subscriptions
        # 2. Enable trading functionality  
        # 3. Update UI to show live status
        
    def _on_connection_failed(self, error_message: str):
        """Handle IB connection failure."""
        self.add_automation_log(f"❌ IB Connection Failed: {error_message}")
        # Fallback will be triggered separately
    
    def _on_fallback_activated(self):
        """Handle fallback to simulation mode."""
        self.add_automation_log("🔄 SIMULATION MODE ACTIVE")
        self.add_system_log("Using simulated market data")
        
        # Update window title to show simulation status
        self.setWindowTitle("Spyder Trading Dashboard - SIMULATION")
        
        # Restart simulation timer if it exists
        if hasattr(self, "timer"):
            self.timer.start()
    
    def get_bridge_status(self) -> dict:
        """Get current bridge status for debugging."""
        return self.working_bridge.get_connection_status()
    
    def closeEvent(self, event):
        """Clean up on window close."""
        try:
            if hasattr(self, 'working_bridge'):
                self.working_bridge.disconnect()
            super().closeEvent(event)
        except Exception as e:
            print(f"Error during close: {e}")
            event.accept()

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def test_ib_connection() -> bool:
    """
    Standalone function to test IB connection.
    
    Returns:
        bool: True if any client ID works, False otherwise
    """
    if not IB_AVAILABLE:
        print("❌ ib_async not available")
        return False
    
    print(f"Testing IB Gateway connection at {IB_HOST}:{IB_PORT}")
    
    for client_id in VALID_CLIENT_IDS:
        try:
            print(f"Testing client ID {client_id}...")
            
            ib = IB()
            ib.connect(IB_HOST, IB_PORT, clientId=client_id, timeout=10)
            
            if ib.isConnected():
                print(f"✅ Client ID {client_id} works!")
                ib.disconnect()
                return True
            else:
                ib.disconnect()
                
        except Exception as e:
            print(f"❌ Client ID {client_id} failed: {e}")
    
    print("❌ All client IDs failed")
    return False

def get_working_client_id() -> int:
    """
    Get the first working client ID.
    
    Returns:
        int: Working client ID, or -1 if none work
    """
    if not IB_AVAILABLE:
        return -1
    
    for client_id in VALID_CLIENT_IDS:
        try:
            ib = IB()
            ib.connect(IB_HOST, IB_PORT, clientId=client_id, timeout=5)

            if ib.isConnected():
                ib.disconnect()
                return client_id

        except Exception as e:
            # Log connection failure for this client ID
            print(f"⚠️ Client ID {client_id} connection failed: {e}")
            continue

    return -1

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

def main():
    """Main execution for standalone testing."""
    print("=" * 60)
    print("SPYDER WORKING IB BRIDGE WITH ib_async")
    print("=" * 60)
    print(f"ib_async available: {IB_AVAILABLE}")
    print(f"Target: {IB_HOST}:{IB_PORT}")
    print(f"Client IDs to test: {VALID_CLIENT_IDS}")
    print("=" * 60)
    
    # Test connection
    if test_ib_connection():
        working_id = get_working_client_id()
        print(f"✅ Connection successful with client ID {working_id}")
        
        # Launch dashboard with working bridge
        app = QApplication(sys.argv)
        app.setApplicationName("Spyder Trading Dashboard")
        
        dashboard = DashboardWithWorkingBridge()
        dashboard.show()
        
        print("🚀 Dashboard launched with Working IB Bridge")
        print("Monitor the dashboard for real-time connection status")
        
        sys.exit(app.exec())
        
    else:
        print("❌ No working IB connection found")
        print("\nTroubleshooting:")
        print("1. Ensure IB Gateway is running and logged in")
        print("2. Verify port 4002 is correct (paper trading)")
        print("3. Check that API connections are enabled in Gateway")
        print("4. Try restarting IB Gateway")

if __name__ == "__main__":
    main()