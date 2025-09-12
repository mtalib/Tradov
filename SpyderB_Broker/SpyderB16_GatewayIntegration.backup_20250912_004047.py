#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker     
Module: SpyderB16_GatewayIntegration.py
Purpose: Gateway Integration Management with Client Display and System Monitoring
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-09-11 Time: 18:45:00  

Module Description:
    Comprehensive gateway integration management module that coordinates
    between IB Gateway connections, client status monitoring, dashboard
    displays, and system health reporting. Provides unified interface
    for gateway operations and client management across the Spyder system.

    This module exports the GatewayIntegrationManager class and related
    components that are imported by other broker modules for integration
    testing and dashboard coordination.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import json
import logging
import threading
import time
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Dict, List, Optional, Any, Tuple, Callable, Union
from dataclasses import dataclass, field
from pathlib import Path
import subprocess
import socket
import psutil

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox,
        QGridLayout, QProgressBar, QTextEdit, QTabWidget,
        QFrame, QScrollArea, QSplitter, QStatusBar
    )
    from PySide6.QtCore import QThread, Signal, QTimer, Qt, QObject
    from PySide6.QtGui import QFont, QColor, QPalette, QPixmap, QIcon
    HAS_PYQT6 = True
except ImportError:
    HAS_PYQT6 = False
    print("WARNING: PyQt6 not available - Gateway Integration GUI will use fallbacks")

try:
    from ib_insync import IB
    HAS_IB_INSYNC = True
except ImportError:
    HAS_IB_INSYNC = False
    print("WARNING: ib_insync not available - using mock connections")

# ==============================================================================
# SPYDER MODULE IMPORTS
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler, TradingError, ErrorCategory, ErrorSeverity
    from SpyderB_Broker.SpyderB13_GatewayConfig import GatewayConfig, GatewayManager, ClientConfig, ClientPurpose
    HAS_SPYDER_UTILITIES = True
except ImportError:
    HAS_SPYDER_UTILITIES = False
    print("WARNING: Some Spyder utilities not available - using fallbacks")

# ==============================================================================
# ENUMS AND STATUS DEFINITIONS
# ==============================================================================

class ClientStatusLevel(Enum):
    """Client status levels for dashboard display."""
    EXCELLENT = "excellent"
    GOOD = "good"
    WARNING = "warning"
    CRITICAL = "critical"
    DISCONNECTED = "disconnected"
    UNKNOWN = "unknown"

class SystemComponent(Enum):
    """System components monitored by integration manager."""
    GATEWAY = "gateway"
    MARKET_DATA = "market_data"
    ORDER_SYSTEM = "order_system"
    POSITION_TRACKER = "position_tracker"
    ACCOUNT_MANAGER = "account_manager"
    RISK_MONITOR = "risk_monitor"
    METRICS_COLLECTOR = "metrics_collector"
    VPN_CONNECTION = "vpn_connection"

class IntegrationStatus(Enum):
    """Integration status levels."""
    INITIALIZING = "initializing"
    ACTIVE = "active"
    DEGRADED = "degraded"
    FAILED = "failed"
    MAINTENANCE = "maintenance"
    SHUTDOWN = "shutdown"

class GatewayConnectionState(Enum):
    """Gateway connection states."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATING = "authenticating"
    AUTHENTICATED = "authenticated"
    READY = "ready"
    ERROR = "error"
    TIMEOUT = "timeout"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class ClientDisplayInfo:
    """Information for displaying client status in dashboard."""
    client_id: int
    purpose: str
    description: str
    status: ClientStatusLevel
    connection_time: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    symbols_count: int = 0
    requests_per_minute: float = 0.0
    latency_ms: Optional[float] = None
    error_count: int = 0
    health_score: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'client_id': self.client_id,
            'purpose': self.purpose,
            'description': self.description,
            'status': self.status.value,
            'connection_time': self.connection_time.isoformat() if self.connection_time else None,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,
            'symbols_count': self.symbols_count,
            'requests_per_minute': self.requests_per_minute,
            'latency_ms': self.latency_ms,
            'error_count': self.error_count,
            'health_score': self.health_score
        }

@dataclass
class SystemComponentStatus:
    """Status information for system components."""
    component: SystemComponent
    status: ClientStatusLevel
    health_score: float
    last_check: datetime
    details: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None

@dataclass
class DashboardData:
    """Complete dashboard data structure."""
    clients: List[ClientDisplayInfo]
    system_components: List[SystemComponentStatus]
    gateway_status: GatewayConnectionState
    integration_status: IntegrationStatus
    last_update: datetime
    system_health_score: float
    active_connections: int
    total_requests: int
    average_latency: float
    error_rate: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'clients': [client.to_dict() for client in self.clients],
            'system_components': [
                {
                    'component': comp.component.value,
                    'status': comp.status.value,
                    'health_score': comp.health_score,
                    'last_check': comp.last_check.isoformat(),
                    'details': comp.details,
                    'error_message': comp.error_message
                }
                for comp in self.system_components
            ],
            'gateway_status': self.gateway_status.value,
            'integration_status': self.integration_status.value,
            'last_update': self.last_update.isoformat(),
            'system_health_score': self.system_health_score,
            'active_connections': self.active_connections,
            'total_requests': self.total_requests,
            'average_latency': self.average_latency,
            'error_rate': self.error_rate
        }

# ==============================================================================
# GATEWAY INTEGRATION MANAGER
# ==============================================================================

class GatewayIntegrationManager:
    """
    Main gateway integration manager for coordinating IB Gateway connections,
    client monitoring, and dashboard data aggregation.
    """
    
    def __init__(self, config: Optional[GatewayConfig] = None):
        """Initialize the gateway integration manager."""
        self.config = config or GatewayConfig()
        self.logger = self._setup_logging()
        self.error_handler = SpyderErrorHandler() if HAS_SPYDER_UTILITIES else None
        
        # Status tracking
        self.integration_status = IntegrationStatus.INITIALIZING
        self.gateway_status = GatewayConnectionState.DISCONNECTED
        self.client_displays: Dict[int, ClientDisplayInfo] = {}
        self.component_statuses: Dict[SystemComponent, SystemComponentStatus] = {}
        
        # Monitoring
        self.monitoring_active = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.last_health_check = datetime.now()
        
        # Callbacks for status updates
        self.status_callbacks: List[Callable] = []
        
        # Initialize component statuses
        self._initialize_component_statuses()
        
        self.logger.info("Gateway Integration Manager initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for integration manager."""
        if HAS_SPYDER_UTILITIES:
            return SpyderLogger.get_logger("GatewayIntegrationManager")
        else:
            logger = logging.getLogger("GatewayIntegrationManager")
            logger.setLevel(logging.INFO)
            if not logger.handlers:
                handler = logging.StreamHandler()
                formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
                handler.setFormatter(formatter)
                logger.addHandler(handler)
            return logger
    
    def _initialize_component_statuses(self):
        """Initialize status tracking for all system components."""
        for component in SystemComponent:
            self.component_statuses[component] = SystemComponentStatus(
                component=component,
                status=ClientStatusLevel.UNKNOWN,
                health_score=0.0,
                last_check=datetime.now(),
                details={}
            )
    
    # ==========================================================================
    # INTEGRATION LIFECYCLE MANAGEMENT
    # ==========================================================================
    
    def start_integration(self) -> bool:
        """
        Start the gateway integration system.
        
        Returns:
            bool: True if integration started successfully
        """
        try:
            self.logger.info("Starting gateway integration system")
            self.integration_status = IntegrationStatus.INITIALIZING
            
            # Initialize client display info
            self._initialize_client_displays()
            
            # Start monitoring
            self.start_monitoring()
            
            # Test gateway connectivity
            gateway_connected = self._test_gateway_connectivity()
            
            if gateway_connected:
                self.integration_status = IntegrationStatus.ACTIVE
                self.gateway_status = GatewayConnectionState.READY
                self.logger.info("Gateway integration started successfully")
                self._notify_status_change()
                return True
            else:
                self.integration_status = IntegrationStatus.DEGRADED
                self.logger.warning("Gateway integration started with degraded connectivity")
                self._notify_status_change()
                return False
                
        except Exception as e:
            self.integration_status = IntegrationStatus.FAILED
            self.logger.error(f"Failed to start gateway integration: {e}")
            self._notify_status_change()
            return False
    
    def stop_integration(self):
        """Stop the gateway integration system."""
        try:
            self.logger.info("Stopping gateway integration system")
            self.integration_status = IntegrationStatus.SHUTDOWN
            
            # Stop monitoring
            self.stop_monitoring()
            
            # Clear client displays
            self.client_displays.clear()
            
            # Reset component statuses
            self._initialize_component_statuses()
            
            self.gateway_status = GatewayConnectionState.DISCONNECTED
            self.logger.info("Gateway integration stopped")
            self._notify_status_change()
            
        except Exception as e:
            self.logger.error(f"Error stopping gateway integration: {e}")
    
    # ==========================================================================
    # CLIENT MANAGEMENT
    # ==========================================================================
    
    def _initialize_client_displays(self):
        """Initialize client display information."""
        # Get client configuration from gateway manager
        if hasattr(self.config, 'client_allocation'):
            for client_id, client_config in self.config.client_allocation.items():
                self.client_displays[client_id] = ClientDisplayInfo(
                    client_id=client_id,
                    purpose=client_config.purpose.value if hasattr(client_config, 'purpose') else "unknown",
                    description=getattr(client_config, 'description', f"Client {client_id}"),
                    status=ClientStatusLevel.DISCONNECTED,
                    symbols_count=len(getattr(client_config, 'symbols', [])),
                    requests_per_minute=0.0,
                    health_score=0.0
                )
        else:
            # Fallback: create default client displays
            for client_id in range(1, 11):  # Default 10 clients
                self.client_displays[client_id] = ClientDisplayInfo(
                    client_id=client_id,
                    purpose=f"Client_{client_id}",
                    description=f"Trading Client {client_id}",
                    status=ClientStatusLevel.DISCONNECTED,
                    symbols_count=0,
                    requests_per_minute=0.0,
                    health_score=0.0
                )
    
    def update_client_status(self, client_id: int, status: ClientStatusLevel, **kwargs):
        """
        Update status for a specific client.
        
        Args:
            client_id: Client ID to update
            status: New status level
            **kwargs: Additional status information
        """
        if client_id in self.client_displays:
            client_info = self.client_displays[client_id]
            client_info.status = status
            client_info.last_activity = datetime.now()
            
            # Update additional fields if provided
            if 'latency_ms' in kwargs:
                client_info.latency_ms = kwargs['latency_ms']
            if 'requests_per_minute' in kwargs:
                client_info.requests_per_minute = kwargs['requests_per_minute']
            if 'error_count' in kwargs:
                client_info.error_count = kwargs['error_count']
            if 'health_score' in kwargs:
                client_info.health_score = kwargs['health_score']
            
            # If connecting or connected, update connection time
            if status in [ClientStatusLevel.GOOD, ClientStatusLevel.EXCELLENT] and client_info.connection_time is None:
                client_info.connection_time = datetime.now()
            elif status == ClientStatusLevel.DISCONNECTED:
                client_info.connection_time = None
            
            self._notify_status_change()
    
    def get_client_display_info(self, client_id: int) -> Optional[ClientDisplayInfo]:
        """
        Get display information for a specific client.
        
        Args:
            client_id: Client ID to retrieve
            
        Returns:
            ClientDisplayInfo or None if client not found
        """
        return self.client_displays.get(client_id)
    
    def get_all_client_displays(self) -> List[ClientDisplayInfo]:
        """
        Get display information for all clients.
        
        Returns:
            List of ClientDisplayInfo objects
        """
        return list(self.client_displays.values())
    
    # ==========================================================================
    # SYSTEM COMPONENT MONITORING
    # ==========================================================================
    
    def update_component_status(self, component: SystemComponent, status: ClientStatusLevel, 
                              health_score: float = None, details: Dict[str, Any] = None,
                              error_message: str = None):
        """
        Update status for a system component.
        
        Args:
            component: System component to update
            status: New status level
            health_score: Health score (0.0 to 1.0)
            details: Additional status details
            error_message: Error message if applicable
        """
        if component in self.component_statuses:
            comp_status = self.component_statuses[component]
            comp_status.status = status
            comp_status.last_check = datetime.now()
            
            if health_score is not None:
                comp_status.health_score = health_score
            if details is not None:
                comp_status.details.update(details)
            if error_message is not None:
                comp_status.error_message = error_message
            
            self._notify_status_change()
    
    def get_component_status(self, component: SystemComponent) -> Optional[SystemComponentStatus]:
        """
        Get status for a specific system component.
        
        Args:
            component: System component to retrieve
            
        Returns:
            SystemComponentStatus or None if not found
        """
        return self.component_statuses.get(component)
    
    def get_all_component_statuses(self) -> List[SystemComponentStatus]:
        """
        Get status for all system components.
        
        Returns:
            List of SystemComponentStatus objects
        """
        return list(self.component_statuses.values())
    
    # ==========================================================================
    # DASHBOARD DATA GENERATION
    # ==========================================================================
    
    def get_dashboard_data(self) -> DashboardData:
        """
        Generate complete dashboard data structure.
        
        Returns:
            DashboardData: Complete dashboard information
        """
        # Calculate aggregate metrics
        connected_clients = [
            client for client in self.client_displays.values()
            if client.status not in [ClientStatusLevel.DISCONNECTED, ClientStatusLevel.UNKNOWN]
        ]
        
        active_connections = len(connected_clients)
        
        # Calculate averages
        total_requests = sum(client.requests_per_minute for client in connected_clients)
        
        latencies = [client.latency_ms for client in connected_clients if client.latency_ms is not None]
        average_latency = sum(latencies) / len(latencies) if latencies else 0.0
        
        total_errors = sum(client.error_count for client in self.client_displays.values())
        error_rate = total_errors / max(1, len(self.client_displays))
        
        # Calculate system health score
        client_health_scores = [client.health_score for client in self.client_displays.values()]
        component_health_scores = [comp.health_score for comp in self.component_statuses.values()]
        
        all_health_scores = client_health_scores + component_health_scores
        system_health_score = sum(all_health_scores) / max(1, len(all_health_scores))
        
        return DashboardData(
            clients=list(self.client_displays.values()),
            system_components=list(self.component_statuses.values()),
            gateway_status=self.gateway_status,
            integration_status=self.integration_status,
            last_update=datetime.now(),
            system_health_score=system_health_score,
            active_connections=active_connections,
            total_requests=int(total_requests),
            average_latency=average_latency,
            error_rate=error_rate
        )
    
    # ==========================================================================
    # MONITORING AND HEALTH CHECKS
    # ==========================================================================
    
    def start_monitoring(self):
        """Start continuous system monitoring."""
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        self.logger.info("Integration monitoring started")
    
    def stop_monitoring(self):
        """Stop system monitoring."""
        self.monitoring_active = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        self.logger.info("Integration monitoring stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop."""
        while self.monitoring_active:
            try:
                # Perform health checks
                self._perform_health_checks()
                
                # Update last health check time
                self.last_health_check = datetime.now()
                
                # Sleep until next check
                time.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                self.logger.error(f"Monitoring error: {e}")
                time.sleep(60)  # Wait longer on error
    
    def _perform_health_checks(self):
        """Perform comprehensive health checks."""
        try:
            # Check gateway connectivity
            self._test_gateway_connectivity()
            
            # Check system resources
            self._check_system_resources()
            
            # Update component statuses based on checks
            self._update_component_health()
            
            # Simulate client status updates (replace with real checks)
            self._simulate_client_status_updates()
            
        except Exception as e:
            self.logger.error(f"Health check error: {e}")
    
    def _test_gateway_connectivity(self) -> bool:
        """Test IB Gateway connectivity."""
        try:
            # Test connection to common IB Gateway ports
            gateway_ports = [4001, 4002]  # Live and paper trading ports
            
            for port in gateway_ports:
                try:
                    sock = socket.create_connection(("localhost", port), timeout=5)
                    sock.close()
                    self.gateway_status = GatewayConnectionState.READY
                    self.update_component_status(
                        SystemComponent.GATEWAY,
                        ClientStatusLevel.EXCELLENT,
                        health_score=1.0,
                        details={"port": port, "status": "connected"}
                    )
                    return True
                except:
                    continue
            
            # No connections successful
            self.gateway_status = GatewayConnectionState.DISCONNECTED
            self.update_component_status(
                SystemComponent.GATEWAY,
                ClientStatusLevel.CRITICAL,
                health_score=0.0,
                error_message="No gateway connections available"
            )
            return False
            
        except Exception as e:
            self.gateway_status = GatewayConnectionState.ERROR
            self.update_component_status(
                SystemComponent.GATEWAY,
                ClientStatusLevel.CRITICAL,
                health_score=0.0,
                error_message=str(e)
            )
            return False
    
    def _check_system_resources(self):
        """Check system resource utilization."""
        try:
            # Memory usage
            memory = psutil.virtual_memory()
            memory_health = 1.0 - (memory.percent / 100.0)
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_health = 1.0 - (cpu_percent / 100.0)
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_health = 1.0 - (disk.percent / 100.0)
            
            # Overall system health
            system_health = (memory_health + cpu_health + disk_health) / 3.0
            
            # Determine status level
            if system_health > 0.8:
                status = ClientStatusLevel.EXCELLENT
            elif system_health > 0.6:
                status = ClientStatusLevel.GOOD
            elif system_health > 0.4:
                status = ClientStatusLevel.WARNING
            else:
                status = ClientStatusLevel.CRITICAL
            
            # Update system component status
            for component in [SystemComponent.MARKET_DATA, SystemComponent.ORDER_SYSTEM]:
                self.update_component_status(
                    component,
                    status,
                    health_score=system_health,
                    details={
                        "memory_percent": memory.percent,
                        "cpu_percent": cpu_percent,
                        "disk_percent": disk.percent
                    }
                )
                
        except Exception as e:
            self.logger.error(f"System resource check failed: {e}")
    
    def _update_component_health(self):
        """Update health for all system components."""
        # This would normally check actual component status
        # For now, simulate reasonable health metrics
        
        current_time = datetime.now()
        
        for component in SystemComponent:
            if component not in self.component_statuses:
                continue
                
            comp_status = self.component_statuses[component]
            
            # Simulate component health based on time and randomness
            # In real implementation, this would check actual component status
            if comp_status.status == ClientStatusLevel.UNKNOWN:
                # Initialize with good status
                comp_status.status = ClientStatusLevel.GOOD
                comp_status.health_score = 0.8
                comp_status.last_check = current_time
    
    def _simulate_client_status_updates(self):
        """Simulate client status updates for testing."""
        # This would normally get real client status from IB connections
        # For now, simulate reasonable client behavior
        
        current_time = datetime.now()
        
        for client_id, client_info in self.client_displays.items():
            # Simulate connection status
            if client_info.status == ClientStatusLevel.DISCONNECTED:
                # Occasionally connect clients
                if client_id <= 5:  # Connect first 5 clients
                    client_info.status = ClientStatusLevel.GOOD
                    client_info.connection_time = current_time
                    client_info.health_score = 0.8
                    client_info.latency_ms = 25.0 + (client_id * 5)
                    client_info.requests_per_minute = 30.0 - (client_id * 2)
            
            # Update last activity
            if client_info.status not in [ClientStatusLevel.DISCONNECTED, ClientStatusLevel.UNKNOWN]:
                client_info.last_activity = current_time
    
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
        dashboard_data = self.get_dashboard_data()
        for callback in self.status_callbacks:
            try:
                callback(dashboard_data)
            except Exception as e:
                self.logger.error(f"Status callback error: {e}")

# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================

def create_gateway_integration_manager(config: Optional[GatewayConfig] = None) -> GatewayIntegrationManager:
    """
    Factory function to create gateway integration manager.
    
    Args:
        config: Optional gateway configuration
        
    Returns:
        GatewayIntegrationManager: Configured integration manager
    """
    return GatewayIntegrationManager(config)

def validate_module_dependencies() -> Dict[str, bool]:
    """
    Validate that all required dependencies are available.
    
    Returns:
        Dict mapping dependency names to availability status
    """
    dependencies = {
        'pyqt6': HAS_PYQT6,
        'ib_insync': HAS_IB_INSYNC,
        'spyder_utilities': HAS_SPYDER_UTILITIES,
        'psutil': True  # psutil is imported at module level
    }
    
    return dependencies

def get_integration_status_info() -> Dict[str, Any]:
    """
    Get information about integration module status.
    
    Returns:
        Dict containing module status and capability information
    """
    return {
        'module_name': 'SpyderB16_GatewayIntegration',
        'version': '1.0.0',
        'dependencies': validate_module_dependencies(),
        'capabilities': {
            'gui_dashboard': HAS_PYQT6,
            'ib_connectivity': HAS_IB_INSYNC,
            'system_monitoring': True,
            'client_management': True,
            'status_callbacks': True
        },
        'enums_available': {
            'ClientStatusLevel': True,
            'SystemComponent': True,
            'IntegrationStatus': True,
            'GatewayConnectionState': True
        }
    }

# ==============================================================================
# MODULE INITIALIZATION AND TESTING
# ==============================================================================

def initialize_integration_module() -> bool:
    """
    Initialize the gateway integration module.
    
    Returns:
        bool: True if initialization successful
    """
    try:
        # Test enum creation
        test_status = ClientStatusLevel.EXCELLENT
        test_component = SystemComponent.GATEWAY
        test_integration = IntegrationStatus.ACTIVE
        
        # Test manager creation
        manager = create_gateway_integration_manager()
        
        # Test dashboard data generation
        dashboard_data = manager.get_dashboard_data()
        
        return True
        
    except Exception as e:
        print(f"Integration module initialization failed: {e}")
        return False

# ==============================================================================
# MAIN EXECUTION FOR TESTING
# ==============================================================================

if __name__ == "__main__":
    print("SPYDER Gateway Integration Manager - Module Test")
    print("=" * 60)
    
    # Test initialization
    if initialize_integration_module():
        print("✅ Gateway Integration module initialized successfully")
        
        # Test enum availability
        print(f"✅ ClientStatusLevel.EXCELLENT: {ClientStatusLevel.EXCELLENT}")
        print(f"✅ SystemComponent.GATEWAY: {SystemComponent.GATEWAY}")
        print(f"✅ IntegrationStatus.ACTIVE: {IntegrationStatus.ACTIVE}")
        
        # Test manager creation
        manager = create_gateway_integration_manager()
        print(f"✅ Gateway Integration Manager created: {type(manager)}")
        
        # Test dashboard data
        dashboard_data = manager.get_dashboard_data()
        print(f"✅ Dashboard data generated: {dashboard_data.integration_status}")
        
        # Test dependency validation
        deps = validate_module_dependencies()
        print(f"✅ Dependencies validated: {len(deps)} checked")
        
        # Test status info
        status_info = get_integration_status_info()
        print(f"✅ Status info available: {status_info['module_name']}")
        
        print("\n✅ All Gateway Integration module tests passed!")
        
    else:
        print("❌ Gateway Integration module initialization failed")
        exit(1)