#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB31_VPNManager.py
Purpose: VPN Management for IBKR Zurich Connectivity Bypass
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-28 Time: 02:00:00  

Module Description:
    Comprehensive VPN management system designed to bypass ISP/network blocking
    of IBKR Zurich servers. Provides automated VPN connection management with
    European endpoints, connectivity validation, failover mechanisms, and
    PyQt6 dashboard integration. Specifically addresses the ISP-level blocking
    discovered in SpyderB18_ZurichConnectivityDiagnostic.

Key Features:
    - European VPN endpoint management for optimal Zurich routing
    - Automated VPN connection/disconnection tied to trading sessions  
    - Real-time connectivity validation and failover
    - Integration with IBKR Gateway startup/shutdown
    - PyQt6 dashboard widgets with VPN status monitoring
    - Support for multiple VPN providers (OpenVPN, WireGuard)
    - Automatic IP geolocation verification
    - Trading-optimized VPN server selection
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum, auto
import threading
import tempfile
import shutil
import socket
import requests
from urllib.parse import urlparse

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import psutil
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QComboBox, QTextEdit, QProgressBar, 
                            QGroupBox, QCheckBox, QMessageBox, QListWidget,
                            QListWidgetItem, QTabWidget)
from PySide6.QtCore import QTimer, QThread, Signal, Qt, QProcess
from PySide6.QtGui import QFont, QColor, QIcon

# ==============================================================================
# SPYDER MODULE IMPORTS
# ==============================================================================
try:
    from SpyderB_Broker.SpyderB13_GatewayConfig import GatewayConfig, GatewayManager
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
except ImportError as e:
    print(f"Warning: Could not import Spyder modules: {e}")
    SpyderLogger = None
    SpyderErrorHandler = None

# ==============================================================================
# CONSTANTS AND CONFIGURATION
# ==============================================================================

# European VPN endpoints optimized for IBKR Zurich connectivity
OPTIMAL_VPN_ENDPOINTS = {
    # Switzerland - Closest to Zurich
    'zurich': {
        'country': 'Switzerland',
        'city': 'Zurich', 
        'priority': 1,
        'expected_latency': '5-15ms',
        'providers': ['ProtonVPN', 'Surfshark', 'NordVPN']
    },
    'geneva': {
        'country': 'Switzerland',
        'city': 'Geneva',
        'priority': 2, 
        'expected_latency': '10-20ms',
        'providers': ['ExpressVPN', 'CyberGhost', 'Surfshark']
    },
    
    # Germany - Frankfurt is major financial hub
    'frankfurt': {
        'country': 'Germany', 
        'city': 'Frankfurt',
        'priority': 3,
        'expected_latency': '15-25ms',
        'providers': ['NordVPN', 'ExpressVPN', 'ProtonVPN']
    },
    'munich': {
        'country': 'Germany',
        'city': 'Munich', 
        'priority': 4,
        'expected_latency': '20-30ms',
        'providers': ['Surfshark', 'CyberGhost']
    },
    
    # Netherlands - Amsterdam excellent connectivity
    'amsterdam': {
        'country': 'Netherlands',
        'city': 'Amsterdam',
        'priority': 5, 
        'expected_latency': '25-35ms',
        'providers': ['NordVPN', 'ExpressVPN', 'ProtonVPN', 'Surfshark']
    },
    
    # Austria - Close to Zurich
    'vienna': {
        'country': 'Austria',
        'city': 'Vienna',
        'priority': 6,
        'expected_latency': '20-30ms', 
        'providers': ['CyberGhost', 'Surfshark']
    }
}

# VPN Provider Configuration Templates
VPN_PROVIDERS = {
    'nordvpn': {
        'name': 'NordVPN',
        'binary': 'nordvpn',
        'connect_cmd': 'nordvpn connect {server}',
        'disconnect_cmd': 'nordvpn disconnect',
        'status_cmd': 'nordvpn status',
        'install_url': 'https://repo.nordvpn.com/deb/nordvpn/debian/pool/main/nordvpn-release_1.0.0_all.deb'
    },
    'expressvpn': {
        'name': 'ExpressVPN',
        'binary': 'expressvpn',
        'connect_cmd': 'expressvpn connect {server}',
        'disconnect_cmd': 'expressvpn disconnect',
        'status_cmd': 'expressvpn status'
    },
    'protonvpn': {
        'name': 'ProtonVPN',
        'binary': 'protonvpn',
        'connect_cmd': 'protonvpn connect {server}',
        'disconnect_cmd': 'protonvpn disconnect', 
        'status_cmd': 'protonvpn status'
    },
    'surfshark': {
        'name': 'Surfshark',
        'binary': 'surfshark',
        'connect_cmd': 'surfshark-vpn attack {server}',
        'disconnect_cmd': 'surfshark-vpn down',
        'status_cmd': 'surfshark-vpn status'
    }
}

# VPN connection timeouts
VPN_CONNECT_TIMEOUT = 30
VPN_DISCONNECT_TIMEOUT = 15
CONNECTIVITY_TEST_TIMEOUT = 10

class VPNStatus(Enum):
    """VPN connection status"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    ERROR = "error"
    UNKNOWN = "unknown"

class VPNProvider(Enum):
    """Supported VPN providers"""
    NORDVPN = "nordvpn"
    EXPRESSVPN = "expressvpn" 
    PROTONVPN = "protonvpn"
    SURFSHARK = "surfshark"
    MANUAL = "manual"

# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class VPNEndpoint:
    """VPN endpoint configuration"""
    name: str
    country: str
    city: str
    provider: str
    server_id: str
    priority: int = 5
    expected_latency: str = "unknown"
    last_tested: Optional[datetime] = None
    test_latency: float = -1.0
    success_rate: float = 0.0
    
@dataclass
class VPNConnectionInfo:
    """Current VPN connection information"""
    status: VPNStatus
    provider: Optional[str] = None
    endpoint: Optional[str] = None
    server_ip: Optional[str] = None
    public_ip: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    connection_time: Optional[datetime] = None
    last_check: datetime = field(default_factory=datetime.now)

@dataclass
class ConnectivityTestResult:
    """Result of IBKR connectivity test through VPN"""
    zurich_reachable: bool = False
    backup_servers_reachable: int = 0
    average_latency: float = -1.0
    test_timestamp: datetime = field(default_factory=datetime.now)
    errors: List[str] = field(default_factory=list)

# ==============================================================================
# VPN MANAGER CORE ENGINE
# ==============================================================================

class VPNManager:
    """Core VPN management engine"""
    
    def __init__(self, config: Optional[GatewayConfig] = None):
        self.config = config or GatewayConfig()
        
        # Setup logging
        if SpyderLogger:
            self.logger = SpyderLogger.get_logger(__name__)
        else:
            self.logger = logging.getLogger(__name__)
            
        self.current_connection = VPNConnectionInfo(status=VPNStatus.DISCONNECTED)
        self.available_endpoints = []
        self.preferred_provider = None
        self.auto_connect_enabled = False
        
        # Initialize
        self._detect_available_providers()
        self._load_optimal_endpoints()
        
    def _detect_available_providers(self) -> List[VPNProvider]:
        """Detect which VPN providers are installed"""
        available = []
        
        for provider_key, provider_config in VPN_PROVIDERS.items():
            binary = provider_config['binary']
            
            try:
                result = subprocess.run(['which', binary], capture_output=True)
                if result.returncode == 0:
                    available.append(VPNProvider(provider_key))
                    self.logger.info(f"Detected VPN provider: {provider_config['name']}")
                    
            except Exception as e:
                self.logger.debug(f"Provider {binary} not available: {e}")
                
        if not available:
            self.logger.warning("No VPN providers detected - manual configuration required")
            
        return available
        
    def _load_optimal_endpoints(self):
        """Load and prioritize optimal endpoints for IBKR trading"""
        self.available_endpoints = []
        
        # Create endpoints based on available providers
        for location, config in OPTIMAL_VPN_ENDPOINTS.items():
            for provider_name in config['providers']:
                provider_key = provider_name.lower().replace(' ', '')
                
                # Skip if provider not available
                if provider_key not in [p.value for p in self._detect_available_providers()]:
                    continue
                    
                endpoint = VPNEndpoint(
                    name=f"{location}_{provider_key}",
                    country=config['country'],
                    city=config['city'], 
                    provider=provider_key,
                    server_id=location,  # Will be refined per provider
                    priority=config['priority'],
                    expected_latency=config['expected_latency']
                )
                
                self.available_endpoints.append(endpoint)
                
        # Sort by priority
        self.available_endpoints.sort(key=lambda x: x.priority)
        
        self.logger.info(f"Loaded {len(self.available_endpoints)} optimal VPN endpoints")
        
    def get_connection_status(self) -> VPNConnectionInfo:
        """Get current VPN connection status"""
        try:
            # Try to detect status from available providers
            for provider in self._detect_available_providers():
                status_info = self._check_provider_status(provider)
                if status_info and status_info.status == VPNStatus.CONNECTED:
                    self.current_connection = status_info
                    return status_info
                    
            # If no active connection detected
            self.current_connection.status = VPNStatus.DISCONNECTED
            self.current_connection.last_check = datetime.now()
            
        except Exception as e:
            self.logger.error(f"Error checking VPN status: {e}")
            self.current_connection.status = VPNStatus.ERROR
            
        return self.current_connection
        
    def _check_provider_status(self, provider: VPNProvider) -> Optional[VPNConnectionInfo]:
        """Check status for specific VPN provider"""
        try:
            provider_config = VPN_PROVIDERS[provider.value]
            status_cmd = provider_config['status_cmd']
            
            result = subprocess.run(
                status_cmd.split(),
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                # Parse provider-specific output
                return self._parse_provider_status(provider, result.stdout)
                
        except Exception as e:
            self.logger.debug(f"Could not check {provider.value} status: {e}")
            
        return None
        
    def _parse_provider_status(self, provider: VPNProvider, output: str) -> VPNConnectionInfo:
        """Parse VPN provider status output"""
        info = VPNConnectionInfo(status=VPNStatus.UNKNOWN, provider=provider.value)
        
        # Generic parsing - can be refined per provider
        if "Connected" in output or "connected" in output:
            info.status = VPNStatus.CONNECTED
        elif "Disconnected" in output or "disconnected" in output:
            info.status = VPNStatus.DISCONNECTED
        elif "Connecting" in output:
            info.status = VPNStatus.CONNECTING
            
        return info
        
    def connect_to_optimal_endpoint(self) -> Tuple[bool, str]:
        """Connect to the optimal VPN endpoint for IBKR trading"""
        if not self.available_endpoints:
            return False, "No VPN endpoints available"
            
        # Try endpoints in priority order
        for endpoint in self.available_endpoints:
            self.logger.info(f"Attempting connection to {endpoint.name}")
            
            success, message = self._connect_to_endpoint(endpoint)
            if success:
                # Verify IBKR connectivity through VPN
                if self._verify_ibkr_connectivity():
                    self.logger.info(f"Successfully connected via {endpoint.name}")
                    return True, f"Connected to {endpoint.city}, {endpoint.country}"
                else:
                    self.logger.warning(f"Connected to {endpoint.name} but IBKR still unreachable")
                    # Continue trying next endpoint
                    self.disconnect()
            else:
                self.logger.warning(f"Failed to connect to {endpoint.name}: {message}")
                
        return False, "All optimal endpoints failed - manual VPN configuration may be required"
        
    def _connect_to_endpoint(self, endpoint: VPNEndpoint) -> Tuple[bool, str]:
        """Connect to specific VPN endpoint"""
        try:
            provider_config = VPN_PROVIDERS[endpoint.provider]
            connect_cmd = provider_config['connect_cmd'].format(server=endpoint.server_id)
            
            self.current_connection.status = VPNStatus.CONNECTING
            
            result = subprocess.run(
                connect_cmd.split(),
                capture_output=True,
                text=True,
                timeout=VPN_CONNECT_TIMEOUT
            )
            
            if result.returncode == 0:
                # Wait a moment for connection to establish
                time.sleep(3)
                
                # Verify connection
                status = self.get_connection_status()
                if status.status == VPNStatus.CONNECTED:
                    return True, "Connection established"
                    
            return False, f"Connection failed: {result.stderr}"
            
        except subprocess.TimeoutExpired:
            return False, "Connection timeout"
        except Exception as e:
            return False, f"Connection error: {e}"
            
    def disconnect(self) -> Tuple[bool, str]:
        """Disconnect from current VPN"""
        if self.current_connection.status == VPNStatus.DISCONNECTED:
            return True, "Already disconnected"
            
        try:
            # Try all providers to ensure disconnection
            for provider in self._detect_available_providers():
                provider_config = VPN_PROVIDERS[provider.value]
                disconnect_cmd = provider_config['disconnect_cmd']
                
                try:
                    subprocess.run(
                        disconnect_cmd.split(),
                        capture_output=True,
                        timeout=VPN_DISCONNECT_TIMEOUT
                    )
                except:
                    pass  # Continue with other providers
                    
            # Update status
            self.current_connection.status = VPNStatus.DISCONNECTED
            self.current_connection.connection_time = None
            
            return True, "Disconnected successfully"
            
        except Exception as e:
            return False, f"Disconnection error: {e}"
            
    def _verify_ibkr_connectivity(self) -> bool:
        """Verify IBKR Zurich servers are reachable through VPN"""
        try:
            # Test connection to primary Zurich server
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(CONNECTIVITY_TEST_TIMEOUT)
            
            result = sock.connect_ex(('zdc1.ibllc.com', 4001))
            sock.close()
            
            return result == 0
            
        except Exception as e:
            self.logger.debug(f"IBKR connectivity test failed: {e}")
            return False
            
    def get_current_public_ip(self) -> Tuple[Optional[str], Optional[str]]:
        """Get current public IP and location"""
        try:
            # Use multiple IP detection services for reliability
            services = [
                'https://ipapi.co/json/',
                'https://ip-api.com/json/',
                'https://ipinfo.io/json'
            ]
            
            for service in services:
                try:
                    response = requests.get(service, timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        
                        # Extract IP and country (format varies by service)
                        ip = data.get('ip') or data.get('query')
                        country = data.get('country_name') or data.get('country') 
                        
                        if ip:
                            return ip, country
                            
                except:
                    continue
                    
        except Exception as e:
            self.logger.debug(f"IP detection failed: {e}")
            
        return None, None
        
    def test_endpoint_performance(self, endpoint: VPNEndpoint) -> ConnectivityTestResult:
        """Test connectivity performance through specific endpoint"""
        # This would connect to the endpoint and test IBKR connectivity
        # Implementation depends on VPN provider
        pass

# ==============================================================================
# VPN AUTOMATION ENGINE
# ==============================================================================

class VPNAutomation:
    """Automated VPN management tied to trading sessions"""
    
    def __init__(self, vpn_manager: VPNManager, config: Optional[GatewayConfig] = None):
        self.vpn_manager = vpn_manager
        self.config = config or GatewayConfig()
        self.logger = logging.getLogger(__name__)
        
        self.auto_connect_on_gateway_start = True
        self.auto_disconnect_on_gateway_stop = True
        self.monitoring_enabled = False
        
    def enable_automation(self):
        """Enable automated VPN management"""
        self.monitoring_enabled = True
        self.logger.info("VPN automation enabled")
        
    def disable_automation(self):
        """Disable automated VPN management"""  
        self.monitoring_enabled = False
        self.logger.info("VPN automation disabled")
        
    def on_gateway_starting(self) -> bool:
        """Called when IB Gateway is starting"""
        if not self.auto_connect_on_gateway_start:
            return True
            
        self.logger.info("Gateway starting - establishing VPN connection")
        success, message = self.vpn_manager.connect_to_optimal_endpoint()
        
        if success:
            self.logger.info(f"VPN connected for trading session: {message}")
            return True
        else:
            self.logger.error(f"Failed to establish VPN for trading: {message}")
            return False
            
    def on_gateway_stopping(self) -> bool:
        """Called when IB Gateway is stopping"""
        if not self.auto_disconnect_on_gateway_stop:
            return True
            
        self.logger.info("Gateway stopping - disconnecting VPN")
        success, message = self.vpn_manager.disconnect()
        
        if success:
            self.logger.info("VPN disconnected after trading session")
        else:
            self.logger.warning(f"VPN disconnection issue: {message}")
            
        return success

# ==============================================================================
# PYQT6 VPN DASHBOARD WIDGET
# ==============================================================================

class VPNDashboardWidget(QWidget):
    """PyQt6 widget for VPN management dashboard"""
    
    def __init__(self, config: Optional[GatewayConfig] = None):
        super().__init__()
        self.config = config or GatewayConfig()
        self.vpn_manager = VPNManager(config)
        self.automation = VPNAutomation(self.vpn_manager, config)
        
        self.setup_ui()
        self.setup_monitoring()
        
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("🌐 VPN Manager - IBKR Zurich Bypass")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(14)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Status display
        self.status_label = QLabel("🔄 Checking VPN status...")
        layout.addWidget(self.status_label)
        
        # Current IP info
        self.ip_label = QLabel("")
        layout.addWidget(self.ip_label)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.connect_btn = QPushButton("🔗 Connect Optimal")
        self.connect_btn.clicked.connect(self.connect_optimal)
        button_layout.addWidget(self.connect_btn)
        
        self.disconnect_btn = QPushButton("❌ Disconnect")
        self.disconnect_btn.clicked.connect(self.disconnect_vpn)
        button_layout.addWidget(self.disconnect_btn)
        
        self.test_btn = QPushButton("🧪 Test IBKR")
        self.test_btn.clicked.connect(self.test_ibkr_connectivity)
        button_layout.addWidget(self.test_btn)
        
        layout.addLayout(button_layout)
        
        # Endpoint selection
        endpoints_group = QGroupBox("Available VPN Endpoints")
        endpoints_layout = QVBoxLayout()
        
        self.endpoints_list = QListWidget()
        self.populate_endpoints_list()
        endpoints_layout.addWidget(self.endpoints_list)
        
        endpoints_group.setLayout(endpoints_layout)
        layout.addWidget(endpoints_group)
        
        # Automation settings
        automation_group = QGroupBox("Automation Settings")
        automation_layout = QVBoxLayout()
        
        self.auto_connect_cb = QCheckBox("Auto-connect when Gateway starts")
        self.auto_connect_cb.setChecked(True)
        automation_layout.addWidget(self.auto_connect_cb)
        
        self.auto_disconnect_cb = QCheckBox("Auto-disconnect when Gateway stops")
        self.auto_disconnect_cb.setChecked(True)
        automation_layout.addWidget(self.auto_disconnect_cb)
        
        automation_group.setLayout(automation_layout)
        layout.addWidget(automation_group)
        
        # Log output
        logs_group = QGroupBox("VPN Logs")
        logs_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(150)
        self.log_text.setFont(QFont("Courier", 9))
        logs_layout.addWidget(self.log_text)
        
        logs_group.setLayout(logs_layout)
        layout.addWidget(logs_group)
        
        self.setLayout(layout)
        
    def setup_monitoring(self):
        """Setup background monitoring"""
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(5000)  # Update every 5 seconds
        
        # Initial status update
        self.update_status()
        
    def populate_endpoints_list(self):
        """Populate the endpoints list"""
        self.endpoints_list.clear()
        
        for endpoint in self.vpn_manager.available_endpoints:
            item_text = f"🇨🇭 {endpoint.city}, {endpoint.country} ({endpoint.provider}) - Priority {endpoint.priority}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, endpoint)
            self.endpoints_list.addItem(item)
            
    def update_status(self):
        """Update VPN status display"""
        status = self.vpn_manager.get_connection_status()
        
        # Status display
        status_colors = {
            VPNStatus.CONNECTED: 'green',
            VPNStatus.CONNECTING: 'orange', 
            VPNStatus.DISCONNECTED: 'gray',
            VPNStatus.ERROR: 'red'
        }
        
        status_emojis = {
            VPNStatus.CONNECTED: '✅',
            VPNStatus.CONNECTING: '🔄',
            VPNStatus.DISCONNECTED: '❌',
            VPNStatus.ERROR: '⚠️'
        }
        
        color = status_colors.get(status.status, 'gray')
        emoji = status_emojis.get(status.status, '❓')
        
        status_text = f"<b><font color='{color}'>{emoji} VPN Status:</font></b> {status.status.value.upper()}"
        
        if status.status == VPNStatus.CONNECTED:
            if status.endpoint:
                status_text += f"<br><b>📍 Endpoint:</b> {status.endpoint}"
            if status.country:
                status_text += f"<br><b>🌍 Location:</b> {status.country}"
                
        self.status_label.setText(status_text)
        
        # Update IP information
        self.update_ip_info()
        
    def update_ip_info(self):
        """Update public IP information"""
        ip, country = self.vpn_manager.get_current_public_ip()
        
        if ip and country:
            # Check if we're in Europe (good for IBKR)
            european_countries = ['Switzerland', 'Germany', 'Netherlands', 'Austria', 'France', 'United Kingdom']
            is_european = any(eu_country in country for eu_country in european_countries)
            
            color = 'green' if is_european else 'orange'
            emoji = '🇪🇺' if is_european else '🌍'
            
            ip_text = f"<b>{emoji} Public IP:</b> <font color='{color}'>{ip}</font> ({country})"
        else:
            ip_text = "<b>🔍 Public IP:</b> Checking..."
            
        self.ip_label.setText(ip_text)
        
    def connect_optimal(self):
        """Connect to optimal VPN endpoint"""
        self.connect_btn.setEnabled(False)
        self.log_message("🔄 Connecting to optimal VPN endpoint...")
        
        # Use QThread for connection to avoid UI blocking
        self.connect_thread = VPNConnectWorker(self.vpn_manager)
        self.connect_thread.finished.connect(self.connection_completed)
        self.connect_thread.log_message.connect(self.log_message)
        self.connect_thread.start()
        
    def connection_completed(self, success: bool, message: str):
        """Handle connection completion"""
        self.connect_btn.setEnabled(True)
        
        if success:
            self.log_message(f"✅ {message}")
        else:
            self.log_message(f"❌ {message}")
            
        self.update_status()
        
    def disconnect_vpn(self):
        """Disconnect from VPN"""
        success, message = self.vpn_manager.disconnect()
        
        if success:
            self.log_message(f"✅ Disconnected: {message}")
        else:
            self.log_message(f"❌ Disconnect failed: {message}")
            
        self.update_status()
        
    def test_ibkr_connectivity(self):
        """Test IBKR connectivity through current connection"""
        self.log_message("🧪 Testing IBKR connectivity...")
        
        # Run the temp diagnostic we created earlier
        try:
            result = subprocess.run(
                [sys.executable, 'temp_zurich_diagnostic.py'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                # Parse key results
                output = result.stdout
                if "✅ EXCELLENT" in output:
                    self.log_message("✅ IBKR connectivity: EXCELLENT")
                elif "⚠️ FAIR" in output:
                    self.log_message("⚠️ IBKR connectivity: FAIR - some servers reachable")
                elif "❌" in output:
                    self.log_message("❌ IBKR connectivity: FAILED - servers still blocked")
                else:
                    self.log_message("📊 IBKR connectivity test completed - check full results")
            else:
                self.log_message("❌ Connectivity test failed")
                
        except Exception as e:
            self.log_message(f"❌ Test error: {e}")
            
    def log_message(self, message: str):
        """Add message to log display"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        
        # Auto-scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

# ==============================================================================
# WORKER THREADS
# ==============================================================================

class VPNConnectWorker(QThread):
    """Background worker for VPN connection"""
    
    finished = Signal(bool, str)  # success, message
    log_message = Signal(str)     # log message
    
    def __init__(self, vpn_manager: VPNManager):
        super().__init__()
        self.vpn_manager = vpn_manager
        
    def run(self):
        """Run the connection process"""
        try:
            success, message = self.vpn_manager.connect_to_optimal_endpoint()
            self.finished.emit(success, message)
            
        except Exception as e:
            self.finished.emit(False, f"Connection error: {e}")

# ==============================================================================
# VPN PROVIDER INSTALLATION HELPERS
# ==============================================================================

class VPNInstaller:
    """Helper class for installing VPN providers"""
    
    @staticmethod
    def install_nordvpn() -> Tuple[bool, str]:
        """Install NordVPN CLI client"""
        try:
            # Download and install NordVPN package
            commands = [
                "wget -qnc https://repo.nordvpn.com/deb/nordvpn/debian/pool/main/nordvpn-release_1.0.0_all.deb",
                "sudo dpkg -i nordvpn-release_1.0.0_all.deb",
                "sudo apt update",
                "sudo apt install nordvpn -y"
            ]
            
            for cmd in commands:
                result = subprocess.run(cmd.split(), check=True)
                
            return True, "NordVPN installed successfully"
            
        except subprocess.CalledProcessError as e:
            return False, f"Installation failed: {e}"
            
    @staticmethod
    def get_installation_instructions() -> Dict[str, str]:
        """Get installation instructions for VPN providers"""
        return {
            'nordvpn': """
# NordVPN Installation:
wget -qnc https://repo.nordvpn.com/deb/nordvpn/debian/pool/main/nordvpn-release_1.0.0_all.deb
sudo dpkg -i nordvpn-release_1.0.0_all.deb
sudo apt update && sudo apt install nordvpn -y
nordvpn login
            """,
            'expressvpn': """
# ExpressVPN Installation:
# Download from: https://www.expressvpn.com/setup#manual
sudo dpkg -i expressvpn_*_amd64.deb
expressvpn activate
            """,
            'protonvpn': """
# ProtonVPN Installation:
pip install protonvpn-cli
protonvpn init
            """
        }

# ==============================================================================
# COMMAND LINE INTERFACE
# ==============================================================================

def run_cli_vpn_manager():
    """Command line interface for VPN management"""
    print("🌐 SPYDER VPN Manager - IBKR Zurich Bypass")
    print("=" * 50)
    
    vpn_manager = VPNManager()
    
    print("📊 Current Status:")
    status = vpn_manager.get_connection_status()
    print(f"  VPN Status: {status.status.value}")
    
    if status.status == VPNStatus.CONNECTED:
        print(f"  Provider: {status.provider}")
        print(f"  Endpoint: {status.endpoint}")
        
    ip, country = vpn_manager.get_current_public_ip()
    if ip:
        print(f"  Public IP: {ip} ({country})")
        
    print(f"\n🎯 Available Endpoints: {len(vpn_manager.available_endpoints)}")
    for endpoint in vpn_manager.available_endpoints[:5]:  # Show top 5
        print(f"  {endpoint.priority}. {endpoint.city}, {endpoint.country} ({endpoint.provider})")
        
    # Test optimal connection
    print(f"\n🔄 Testing optimal connection...")
    success, message = vpn_manager.connect_to_optimal_endpoint()
    
    if success:
        print(f"✅ {message}")
        print("🧪 Testing IBKR connectivity through VPN...")
        
        # Quick IBKR test
        ibkr_reachable = vpn_manager._verify_ibkr_connectivity()
        print(f"🎯 IBKR Zurich reachable: {'✅ YES' if ibkr_reachable else '❌ NO'}")
        
    else:
        print(f"❌ {message}")
        print("\n💡 Recommendations:")
        print("  • Install a supported VPN provider")
        print("  • Configure VPN credentials")
        print("  • Try manual VPN connection")
        
        # Show installation instructions
        instructions = VPNInstaller.get_installation_instructions()
        print(f"\n🛠️  Installation Instructions:")
        for provider, instruction in instructions.items():
            print(f"\n--- {provider.upper()} ---")
            print(instruction)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

def main():
    """Main execution function for testing and demonstration"""
    print("🚀 SPYDER B19 - VPN Manager")
    print("=" * 40)
    
    try:
        # Test VPN manager
        vpn_manager = VPNManager()
        print(f"✅ VPN Manager initialized")
        print(f"📊 Available endpoints: {len(vpn_manager.available_endpoints)}")
        
        # Test status detection
        status = vpn_manager.get_connection_status()
        print(f"📡 Current VPN status: {status.status.value}")
        
        # Test IP detection
        ip, country = vpn_manager.get_current_public_ip()
        if ip:
            print(f"🌐 Current IP: {ip} ({country})")
            
        print(f"\n✅ VPN Manager test completed!")
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        return False
        
    return True

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        run_cli_vpn_manager()
    else:
        main()
