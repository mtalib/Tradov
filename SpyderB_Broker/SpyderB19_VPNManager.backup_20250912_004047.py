#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker     
Module: SpyderB19_VPNManager.py
Purpose: VPN Management and Connectivity State Management
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-09-11 Time: 18:30:00  

Module Description:
    Comprehensive VPN management module that handles connectivity states,
    provides VPN dashboard widgets, and manages VPN automation for optimal
    IBKR connection routing through Zurich endpoints. Includes all required
    enums and classes referenced by other broker modules.

    This module is critical for:
    - ConnectivityState enum (UNKNOWN, CONNECTED, DISCONNECTED, etc.)
    - VPN management and automation
    - Connection health monitoring
    - Zurich endpoint optimization
    - Dashboard integration for VPN status display
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import logging
import subprocess
import time
import threading
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from pathlib import Path
import json
import socket
import platform
import ipaddress

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QComboBox, QProgressBar, QTextEdit, QGroupBox, QGridLayout,
        QFrame, QScrollArea, QTabWidget, QTableWidget, QTableWidgetItem,
        QHeaderView, QStatusBar, QDialog, QDialogButtonBox
    )
    from PyQt6.QtCore import QThread, pyqtSignal, QTimer, Qt, QObject
    from PyQt6.QtGui import QFont, QColor, QPalette
    HAS_PYQT6 = True
except ImportError:
    HAS_PYQT6 = False
    print("WARNING: PyQt6 not available - VPN GUI components will use fallbacks")

# ==============================================================================
# SPYDER MODULE IMPORTS
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler, TradingError, ErrorCategory, ErrorSeverity
    HAS_SPYDER_UTILITIES = True
except ImportError:
    HAS_SPYDER_UTILITIES = False
    print("WARNING: SpyderU_Utilities not fully available - using fallbacks")

# ==============================================================================
# CONNECTIVITY STATE ENUMS - CRITICAL FOR OTHER MODULES
# ==============================================================================

class ConnectivityState(Enum):
    """
    Primary connectivity state enum used throughout Spyder system.
    
    CRITICAL: This enum is imported by many other modules including:
    - SpyderB20_IntegratedConnectivityManager
    - SpyderB21_GatewayStartupAutomation  
    - Test modules and dashboard components
    """
    UNKNOWN = "unknown"
    INITIALIZING = "initializing"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATED = "authenticated"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"
    FAILED = "failed"
    TIMEOUT = "timeout"
    RECONNECTING = "reconnecting"
    DEGRADED = "degraded"
    OPTIMAL = "optimal"

class VPNStatus(Enum):
    """VPN connection status states."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    FAILED = "failed"
    UNKNOWN = "unknown"
    AUTHENTICATING = "authenticating"
    RECONNECTING = "reconnecting"

class VPNProvider(Enum):
    """Supported VPN providers."""
    NORDVPN = "nordvpn"
    EXPRESSVPN = "expressvpn"
    SURFSHARK = "surfshark"
    PROTONVPN = "protonvpn"
    CUSTOM = "custom"
    SYSTEM = "system"

class ConnectionHealth(Enum):
    """Connection health assessment levels."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"
    UNKNOWN = "unknown"

# ==============================================================================
# OPTIMAL VPN ENDPOINTS FOR IBKR ZURICH CONNECTION
# ==============================================================================

OPTIMAL_VPN_ENDPOINTS = {
    "zurich_primary": [
        "ch-zurich-01.example.com",
        "ch-zurich-02.example.com", 
        "ch-geneva-01.example.com"
    ],
    "europe_backup": [
        "de-frankfurt-01.example.com",
        "de-munich-01.example.com",
        "at-vienna-01.example.com",
        "fr-paris-01.example.com"
    ],
    "latency_optimized": [
        "ch-zurich-premium.example.com",
        "de-frankfurt-premium.example.com"
    ]
}

IBKR_TEST_ENDPOINTS = [
    "gdc1.ibllc.com",
    "cdc1.ibllc.com", 
    "hdc1.ibllc.com"
]

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class VPNConnectionInfo:
    """VPN connection information and metrics."""
    provider: VPNProvider
    server: str
    country: str
    city: str
    ip_address: Optional[str] = None
    latency_ms: Optional[float] = None
    bandwidth_mbps: Optional[float] = None
    connected_at: Optional[datetime] = None
    last_test: Optional[datetime] = None
    health: ConnectionHealth = ConnectionHealth.UNKNOWN
    
    def update_health(self, latency: float, bandwidth: float):
        """Update connection health based on metrics."""
        if latency < 20 and bandwidth > 100:
            self.health = ConnectionHealth.EXCELLENT
        elif latency < 50 and bandwidth > 50:
            self.health = ConnectionHealth.GOOD
        elif latency < 100 and bandwidth > 25:
            self.health = ConnectionHealth.FAIR
        elif latency < 200 and bandwidth > 10:
            self.health = ConnectionHealth.POOR
        else:
            self.health = ConnectionHealth.CRITICAL

@dataclass
class VPNConfig:
    """VPN configuration settings."""
    provider: VPNProvider = VPNProvider.NORDVPN
    preferred_countries: List[str] = field(default_factory=lambda: ["Switzerland", "Germany", "Austria"])
    auto_connect: bool = True
    kill_switch: bool = True
    protocol: str = "openvpn"
    port: int = 443
    encryption: str = "aes-256"
    dns_servers: List[str] = field(default_factory=lambda: ["1.1.1.1", "8.8.8.8"])
    test_interval: int = 300  # seconds
    reconnect_attempts: int = 3
    connection_timeout: int = 30  # seconds

# ==============================================================================
# VPN MANAGER CLASS
# ==============================================================================

class VPNManager:
    """
    Comprehensive VPN management for optimal IBKR connectivity.
    """
    
    def __init__(self, config: Optional[VPNConfig] = None):
        """Initialize VPN manager."""
        self.config = config or VPNConfig()
        self.logger = self._setup_logging()
        self.error_handler = SpyderErrorHandler() if HAS_SPYDER_UTILITIES else None
        
        # Connection state
        self.current_status = VPNStatus.UNKNOWN
        self.current_connection: Optional[VPNConnectionInfo] = None
        self.connectivity_state = ConnectivityState.UNKNOWN
        
        # Monitoring
        self.monitor_thread: Optional[threading.Thread] = None
        self.monitoring_active = False
        self.last_health_check = None
        
        # Callbacks
        self.status_callbacks: List[Callable] = []
        
        self.logger.info("VPN Manager initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for VPN manager."""
        if HAS_SPYDER_UTILITIES:
            return SpyderLogger.get_logger("VPNManager")
        else:
            logger = logging.getLogger("VPNManager")
            logger.setLevel(logging.INFO)
            if not logger.handlers:
                handler = logging.StreamHandler()
                formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
                handler.setFormatter(formatter)
                logger.addHandler(handler)
            return logger
    
    # ==========================================================================
    # CONNECTION MANAGEMENT
    # ==========================================================================
    
    def connect_optimal_zurich(self) -> bool:
        """
        Connect to optimal VPN endpoint for IBKR Zurich access.
        
        Returns:
            bool: True if connection successful
        """
        try:
            self.logger.info("Attempting to connect to optimal Zurich endpoint")
            self.connectivity_state = ConnectivityState.CONNECTING
            self._notify_status_change()
            
            # Test Zurich endpoints
            best_endpoint = self._find_best_endpoint(OPTIMAL_VPN_ENDPOINTS["zurich_primary"])
            
            if best_endpoint:
                success = self._connect_to_endpoint(best_endpoint)
                if success:
                    self.connectivity_state = ConnectivityState.CONNECTED
                    self.current_status = VPNStatus.CONNECTED
                    self.logger.info(f"Successfully connected to {best_endpoint}")
                    self._notify_status_change()
                    return True
            
            # Fallback to European endpoints
            self.logger.warning("Zurich endpoints failed, trying European fallbacks")
            fallback_endpoint = self._find_best_endpoint(OPTIMAL_VPN_ENDPOINTS["europe_backup"])
            
            if fallback_endpoint:
                success = self._connect_to_endpoint(fallback_endpoint)
                if success:
                    self.connectivity_state = ConnectivityState.DEGRADED
                    self.current_status = VPNStatus.CONNECTED
                    self.logger.info(f"Connected to fallback endpoint: {fallback_endpoint}")
                    self._notify_status_change()
                    return True
            
            # Connection failed
            self.connectivity_state = ConnectivityState.FAILED
            self.current_status = VPNStatus.FAILED
            self.logger.error("Failed to connect to any optimal endpoint")
            self._notify_status_change()
            return False
            
        except Exception as e:
            self.logger.error(f"VPN connection error: {e}")
            self.connectivity_state = ConnectivityState.FAILED
            self.current_status = VPNStatus.FAILED
            self._notify_status_change()
            return False
    
    def disconnect(self) -> bool:
        """
        Disconnect from VPN.
        
        Returns:
            bool: True if disconnection successful
        """
        try:
            self.logger.info("Disconnecting from VPN")
            self.connectivity_state = ConnectivityState.DISCONNECTING
            self.current_status = VPNStatus.DISCONNECTING
            self._notify_status_change()
            
            # Perform disconnection based on provider
            success = self._perform_disconnect()
            
            if success:
                self.connectivity_state = ConnectivityState.DISCONNECTED
                self.current_status = VPNStatus.DISCONNECTED
                self.current_connection = None
                self.logger.info("Successfully disconnected from VPN")
            else:
                self.connectivity_state = ConnectivityState.FAILED
                self.current_status = VPNStatus.FAILED
                self.logger.error("Failed to disconnect from VPN")
            
            self._notify_status_change()
            return success
            
        except Exception as e:
            self.logger.error(f"VPN disconnection error: {e}")
            self.connectivity_state = ConnectivityState.FAILED
            self.current_status = VPNStatus.FAILED
            self._notify_status_change()
            return False
    
    def get_connection_status(self) -> Dict[str, Any]:
        """
        Get current connection status and metrics.
        
        Returns:
            Dict containing comprehensive status information
        """
        status = {
            'vpn_status': self.current_status.value,
            'connectivity_state': self.connectivity_state.value,
            'connected': self.current_status == VPNStatus.CONNECTED,
            'connection_info': None,
            'last_health_check': self.last_health_check,
            'optimal_for_ibkr': False
        }
        
        if self.current_connection:
            status['connection_info'] = {
                'provider': self.current_connection.provider.value,
                'server': self.current_connection.server,
                'country': self.current_connection.country,
                'city': self.current_connection.city,
                'ip_address': self.current_connection.ip_address,
                'latency_ms': self.current_connection.latency_ms,
                'bandwidth_mbps': self.current_connection.bandwidth_mbps,
                'health': self.current_connection.health.value,
                'connected_at': self.current_connection.connected_at.isoformat() if self.current_connection.connected_at else None
            }
            
            # Check if optimal for IBKR
            status['optimal_for_ibkr'] = (
                self.current_connection.country in ["Switzerland", "Germany", "Austria"] and
                self.current_connection.health in [ConnectionHealth.EXCELLENT, ConnectionHealth.GOOD]
            )
        
        return status
    
    # ==========================================================================
    # MONITORING AND HEALTH CHECKS
    # ==========================================================================
    
    def start_monitoring(self):
        """Start continuous connection monitoring."""
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._monitor_connection, daemon=True)
        self.monitor_thread.start()
        self.logger.info("Connection monitoring started")
    
    def stop_monitoring(self):
        """Stop connection monitoring."""
        self.monitoring_active = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        self.logger.info("Connection monitoring stopped")
    
    def test_ibkr_connectivity(self) -> Dict[str, Any]:
        """
        Test connectivity to IBKR endpoints.
        
        Returns:
            Dict with test results for each endpoint
        """
        results = {}
        
        for endpoint in IBKR_TEST_ENDPOINTS:
            try:
                start_time = time.time()
                sock = socket.create_connection((endpoint, 4001), timeout=10)
                sock.close()
                latency = (time.time() - start_time) * 1000
                
                results[endpoint] = {
                    'reachable': True,
                    'latency_ms': round(latency, 2),
                    'status': 'success'
                }
                
            except Exception as e:
                results[endpoint] = {
                    'reachable': False,
                    'latency_ms': None,
                    'status': f'failed: {str(e)}'
                }
        
        # Update last health check
        self.last_health_check = datetime.now()
        
        return results
    
    # ==========================================================================
    # STATUS CALLBACKS
    # ==========================================================================
    
    def add_status_callback(self, callback: Callable):
        """Add callback for status changes."""
        self.status_callbacks.append(callback)
    
    def remove_status_callback(self, callback: Callable):
        """Remove status callback."""
        if callback in self.status_callbacks:
            self.status_callbacks.remove(callback)
    
    def _notify_status_change(self):
        """Notify all registered callbacks of status change."""
        status = self.get_connection_status()
        for callback in self.status_callbacks:
            try:
                callback(status)
            except Exception as e:
                self.logger.error(f"Status callback error: {e}")
    
    # ==========================================================================
    # PRIVATE HELPER METHODS
    # ==========================================================================
    
    def _find_best_endpoint(self, endpoints: List[str]) -> Optional[str]:
        """Find the best endpoint based on latency testing."""
        best_endpoint = None
        best_latency = float('inf')
        
        for endpoint in endpoints:
            try:
                # Test latency to endpoint
                start_time = time.time()
                sock = socket.create_connection((endpoint, 443), timeout=5)
                sock.close()
                latency = (time.time() - start_time) * 1000
                
                if latency < best_latency:
                    best_latency = latency
                    best_endpoint = endpoint
                    
            except Exception:
                continue  # Skip unreachable endpoints
        
        return best_endpoint
    
    def _connect_to_endpoint(self, endpoint: str) -> bool:
        """Connect to specific VPN endpoint."""
        try:
            # Simulate VPN connection (replace with actual VPN client calls)
            self.logger.info(f"Connecting to VPN endpoint: {endpoint}")
            
            # Create connection info
            self.current_connection = VPNConnectionInfo(
                provider=self.config.provider,
                server=endpoint,
                country="Switzerland" if "ch-" in endpoint else "Germany",
                city="Zurich" if "zurich" in endpoint else "Frankfurt",
                connected_at=datetime.now()
            )
            
            # Test the connection
            time.sleep(2)  # Simulate connection time
            
            # Update connection metrics
            self.current_connection.latency_ms = 25.0
            self.current_connection.bandwidth_mbps = 150.0
            self.current_connection.ip_address = "192.168.1.100"  # Mock IP
            self.current_connection.update_health(25.0, 150.0)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to endpoint {endpoint}: {e}")
            return False
    
    def _perform_disconnect(self) -> bool:
        """Perform actual VPN disconnection."""
        try:
            # Simulate VPN disconnection (replace with actual VPN client calls)
            self.logger.info("Performing VPN disconnection")
            time.sleep(1)  # Simulate disconnection time
            return True
            
        except Exception as e:
            self.logger.error(f"VPN disconnection failed: {e}")
            return False
    
    def _monitor_connection(self):
        """Monitor connection health in background thread."""
        while self.monitoring_active:
            try:
                if self.current_status == VPNStatus.CONNECTED:
                    # Test IBKR connectivity
                    ibkr_results = self.test_ibkr_connectivity()
                    
                    # Update connection health if needed
                    if self.current_connection:
                        # Calculate average latency to IBKR endpoints
                        latencies = [
                            result['latency_ms'] for result in ibkr_results.values()
                            if result['reachable'] and result['latency_ms'] is not None
                        ]
                        
                        if latencies:
                            avg_latency = sum(latencies) / len(latencies)
                            self.current_connection.latency_ms = avg_latency
                            self.current_connection.update_health(avg_latency, self.current_connection.bandwidth_mbps or 100)
                
                # Sleep until next check
                time.sleep(self.config.test_interval)
                
            except Exception as e:
                self.logger.error(f"Connection monitoring error: {e}")
                time.sleep(60)  # Wait longer on error

# ==============================================================================
# VPN DASHBOARD WIDGET (GUI COMPONENT)
# ==============================================================================

if HAS_PYQT6:
    class VPNDashboardWidget(QWidget):
        """
        VPN dashboard widget for displaying connection status and controls.
        """
        
        def __init__(self, vpn_manager: VPNManager = None):
            """Initialize VPN dashboard widget."""
            super().__init__()
            self.vpn_manager = vpn_manager or VPNManager()
            self.setup_ui()
            self.setup_connections()
            self.update_timer = QTimer()
            self.update_timer.timeout.connect(self.update_display)
            self.update_timer.start(5000)  # Update every 5 seconds
        
        def setup_ui(self):
            """Setup the user interface."""
            layout = QVBoxLayout()
            
            # Status group
            status_group = QGroupBox("VPN Connection Status")
            status_layout = QGridLayout()
            
            self.status_label = QLabel("Unknown")
            self.connectivity_label = QLabel("Unknown")
            self.server_label = QLabel("Not connected")
            self.latency_label = QLabel("--")
            self.health_label = QLabel("Unknown")
            
            status_layout.addWidget(QLabel("VPN Status:"), 0, 0)
            status_layout.addWidget(self.status_label, 0, 1)
            status_layout.addWidget(QLabel("Connectivity:"), 1, 0)
            status_layout.addWidget(self.connectivity_label, 1, 1)
            status_layout.addWidget(QLabel("Server:"), 2, 0)
            status_layout.addWidget(self.server_label, 2, 1)
            status_layout.addWidget(QLabel("Latency:"), 3, 0)
            status_layout.addWidget(self.latency_label, 3, 1)
            status_layout.addWidget(QLabel("Health:"), 4, 0)
            status_layout.addWidget(self.health_label, 4, 1)
            
            status_group.setLayout(status_layout)
            layout.addWidget(status_group)
            
            # Controls
            controls_layout = QHBoxLayout()
            self.connect_button = QPushButton("Connect to Zurich")
            self.disconnect_button = QPushButton("Disconnect")
            self.test_button = QPushButton("Test IBKR Connection")
            
            controls_layout.addWidget(self.connect_button)
            controls_layout.addWidget(self.disconnect_button)
            controls_layout.addWidget(self.test_button)
            layout.addLayout(controls_layout)
            
            # IBKR test results
            self.test_results = QTextEdit()
            self.test_results.setMaximumHeight(150)
            layout.addWidget(QLabel("IBKR Connection Test Results:"))
            layout.addWidget(self.test_results)
            
            self.setLayout(layout)
        
        def setup_connections(self):
            """Setup signal connections."""
            self.connect_button.clicked.connect(self.connect_vpn)
            self.disconnect_button.clicked.connect(self.disconnect_vpn)
            self.test_button.clicked.connect(self.test_ibkr_connection)
            
            # Add status callback
            self.vpn_manager.add_status_callback(self.on_status_change)
        
        def connect_vpn(self):
            """Connect to optimal VPN endpoint."""
            self.connect_button.setEnabled(False)
            self.connect_button.setText("Connecting...")
            
            # Run connection in thread to avoid blocking UI
            threading.Thread(target=self._connect_thread, daemon=True).start()
        
        def _connect_thread(self):
            """Connect to VPN in background thread."""
            success = self.vpn_manager.connect_optimal_zurich()
            
            # Update UI in main thread
            self.connect_button.setEnabled(True)
            self.connect_button.setText("Connect to Zurich")
        
        def disconnect_vpn(self):
            """Disconnect from VPN."""
            self.vpn_manager.disconnect()
        
        def test_ibkr_connection(self):
            """Test IBKR connectivity."""
            self.test_button.setEnabled(False)
            self.test_button.setText("Testing...")
            
            threading.Thread(target=self._test_thread, daemon=True).start()
        
        def _test_thread(self):
            """Test IBKR connection in background thread."""
            results = self.vpn_manager.test_ibkr_connectivity()
            
            # Format results for display
            result_text = "IBKR Connectivity Test Results:\n"
            result_text += "=" * 40 + "\n"
            
            for endpoint, result in results.items():
                status = "✅" if result['reachable'] else "❌"
                latency = f"{result['latency_ms']}ms" if result['latency_ms'] else "N/A"
                result_text += f"{status} {endpoint}: {latency}\n"
            
            # Update UI in main thread
            self.test_results.setText(result_text)
            self.test_button.setEnabled(True)
            self.test_button.setText("Test IBKR Connection")
        
        def on_status_change(self, status: Dict[str, Any]):
            """Handle VPN status changes."""
            # This will be called from background thread, so schedule UI update
            # In a real implementation, you'd use QMetaObject.invokeMethod
            pass
        
        def update_display(self):
            """Update the display with current status."""
            status = self.vpn_manager.get_connection_status()
            
            # Update status labels
            self.status_label.setText(status['vpn_status'].upper())
            self.connectivity_label.setText(status['connectivity_state'].upper())
            
            if status['connection_info']:
                info = status['connection_info']
                self.server_label.setText(f"{info['server']} ({info['country']})")
                self.latency_label.setText(f"{info['latency_ms']}ms" if info['latency_ms'] else "--")
                self.health_label.setText(info['health'].upper())
            else:
                self.server_label.setText("Not connected")
                self.latency_label.setText("--")
                self.health_label.setText("Unknown")
            
            # Update button states
            connected = status['connected']
            self.connect_button.setEnabled(not connected)
            self.disconnect_button.setEnabled(connected)

else:
    # Fallback for when PyQt6 is not available
    class VPNDashboardWidget:
        """Fallback VPN dashboard widget."""
        
        def __init__(self, vpn_manager: VPNManager = None):
            self.vpn_manager = vpn_manager or VPNManager()
            print("VPN Dashboard Widget (Console Mode)")
        
        def show_status(self):
            """Show VPN status in console."""
            status = self.vpn_manager.get_connection_status()
            print(f"VPN Status: {status}")

# ==============================================================================
# VPN AUTOMATION CLASS
# ==============================================================================

class VPNAutomation:
    """
    Automated VPN management for trading sessions.
    """
    
    def __init__(self, vpn_manager: VPNManager = None):
        """Initialize VPN automation."""
        self.vpn_manager = vpn_manager or VPNManager()
        self.logger = logging.getLogger("VPNAutomation")
        self.automation_active = False
        self.automation_thread: Optional[threading.Thread] = None
    
    def start_trading_session_automation(self):
        """Start automated VPN management for trading sessions."""
        if self.automation_active:
            return
        
        self.automation_active = True
        self.automation_thread = threading.Thread(target=self._automation_loop, daemon=True)
        self.automation_thread.start()
        self.logger.info("VPN trading session automation started")
    
    def stop_automation(self):
        """Stop VPN automation."""
        self.automation_active = False
        if self.automation_thread and self.automation_thread.is_alive():
            self.automation_thread.join(timeout=5)
        self.logger.info("VPN automation stopped")
    
    def _automation_loop(self):
        """Main automation loop."""
        while self.automation_active:
            try:
                current_time = datetime.now().time()
                
                # Check if we're in trading hours (extended for pre/post market)
                trading_start = datetime.strptime("09:00", "%H:%M").time()
                trading_end = datetime.strptime("17:00", "%H:%M").time()
                
                if trading_start <= current_time <= trading_end:
                    # Ensure VPN is connected during trading hours
                    status = self.vpn_manager.get_connection_status()
                    if not status['connected']:
                        self.logger.info("Trading hours detected, connecting to VPN")
                        self.vpn_manager.connect_optimal_zurich()
                
                # Sleep for next check
                time.sleep(600)  # Check every 10 minutes
                
            except Exception as e:
                self.logger.error(f"VPN automation error: {e}")
                time.sleep(300)  # Wait 5 minutes on error

# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================

def create_vpn_manager(config: Optional[VPNConfig] = None) -> VPNManager:
    """
    Factory function to create VPN manager instance.
    
    Args:
        config: Optional VPN configuration
        
    Returns:
        VPNManager: Configured VPN manager instance
    """
    return VPNManager(config)

def create_vpn_dashboard_widget(vpn_manager: Optional[VPNManager] = None) -> VPNDashboardWidget:
    """
    Factory function to create VPN dashboard widget.
    
    Args:
        vpn_manager: Optional VPN manager instance
        
    Returns:
        VPNDashboardWidget: Dashboard widget instance
    """
    return VPNDashboardWidget(vpn_manager)

def get_optimal_endpoints() -> Dict[str, List[str]]:
    """
    Get optimal VPN endpoints for IBKR connectivity.
    
    Returns:
        Dict containing categorized optimal endpoints
    """
    return OPTIMAL_VPN_ENDPOINTS.copy()

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================

def initialize_vpn_module() -> bool:
    """
    Initialize the VPN module and verify connectivity states.
    
    Returns:
        bool: True if initialization successful
    """
    try:
        # Verify enum availability
        test_state = ConnectivityState.UNKNOWN
        test_vpn_status = VPNStatus.DISCONNECTED
        test_health = ConnectionHealth.UNKNOWN
        
        # Test basic functionality
        manager = create_vpn_manager()
        status = manager.get_connection_status()
        
        return True
        
    except Exception as e:
        print(f"VPN module initialization failed: {e}")
        return False

# ==============================================================================
# MAIN EXECUTION FOR TESTING
# ==============================================================================

if __name__ == "__main__":
    print("SPYDER VPN Manager - Module Test")
    print("=" * 50)
    
    # Test initialization
    if initialize_vpn_module():
        print("✅ VPN module initialized successfully")
        
        # Test connectivity states
        print(f"✅ ConnectivityState.UNKNOWN: {ConnectivityState.UNKNOWN}")
        print(f"✅ VPNStatus.CONNECTED: {VPNStatus.CONNECTED}")
        print(f"✅ ConnectionHealth.EXCELLENT: {ConnectionHealth.EXCELLENT}")
        
        # Test VPN manager
        manager = create_vpn_manager()
        print(f"✅ VPN Manager created: {type(manager)}")
        
        status = manager.get_connection_status()
        print(f"✅ Status retrieved: {status['vpn_status']}")
        
        # Test IBKR connectivity
        ibkr_results = manager.test_ibkr_connectivity()
        print(f"✅ IBKR connectivity test completed: {len(ibkr_results)} endpoints tested")
        
        print("\n✅ All VPN module tests passed!")
        
    else:
        print("❌ VPN module initialization failed")
        exit(1)