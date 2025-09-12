#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker     
Module: SpyderB05_ConnectionManager.py (FIXED VERSION)
Purpose: Connection Management with unified ConnectivityState enum
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-09-11 Time: 19:30:00  

Module Description:
    Fixed connection management module that exports the unified
    ConnectivityState enum with UNKNOWN attribute to resolve
    import conflicts with other broker modules.
"""

from enum import Enum
from typing import Optional, Any, Dict
from dataclasses import dataclass
from datetime import datetime
import logging

# Import the unified ConnectivityState from VPNManager
try:
    from .SpyderB19_VPNManager import ConnectivityState, ConnectionHealth
except ImportError:
    # Fallback definition
    class ConnectivityState(Enum):
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
    
    class ConnectionHealth(Enum):
        EXCELLENT = "excellent"
        GOOD = "good"
        FAIR = "fair"
        POOR = "poor"
        CRITICAL = "critical"
        UNKNOWN = "unknown"

# Legacy enums for backward compatibility
class ConnectionState(Enum):
    """Internal connection states for detailed tracking."""
    IDLE = "idle"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATING = "authenticating"
    READY = "ready"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    RETRYING = "retrying"

class ConnectionMode(Enum):
    """Connection mode types."""
    PAPER = "paper"
    LIVE = "live"
    SIMULATION = "simulation"

# ==============================================================================
# CONFIGURATION CLASSES
# ==============================================================================

@dataclass
class ConnectionConfig:
    """Configuration for IB Gateway connection."""
    host: str = "localhost"
    port: int = 4002
    client_id: int = 1
    mode: ConnectionMode = ConnectionMode.PAPER
    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 5.0
    auto_reconnect: bool = True

@dataclass
class ConnectionStatus:
    """Current connection status information."""
    state: ConnectionState = ConnectionState.IDLE
    connectivity_state: ConnectivityState = ConnectivityState.UNKNOWN
    connected_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    retry_count: int = 0
    last_error: Optional[str] = None

# ==============================================================================
# CONNECTION MANAGER CLASS
# ==============================================================================

class ConnectionManager:
    """Basic connection manager for testing and fallback functionality."""
    
    def __init__(self, config: Optional[ConnectionConfig] = None):
        """Initialize the connection manager."""
        self.config = config or ConnectionConfig()
        self.logger = logging.getLogger("ConnectionManager")
        self.status = ConnectionStatus()
        self.status.connectivity_state = ConnectivityState.UNKNOWN
    
    def connect(self) -> bool:
        """Connect to IB Gateway."""
        self.status.state = ConnectionState.CONNECTING
        self.status.connectivity_state = ConnectivityState.CONNECTING
        # Simulate connection
        self.status.state = ConnectionState.CONNECTED
        self.status.connectivity_state = ConnectivityState.CONNECTED
        self.status.connected_at = datetime.now()
        return True
    
    def disconnect(self):
        """Disconnect from IB Gateway."""
        self.status.state = ConnectionState.DISCONNECTING
        self.status.connectivity_state = ConnectivityState.DISCONNECTING
        self.status.state = ConnectionState.DISCONNECTED
        self.status.connectivity_state = ConnectivityState.DISCONNECTED
        self.status.connected_at = None
    
    def is_connected(self) -> bool:
        """Check if connected to IB Gateway."""
        return self.status.state == ConnectionState.CONNECTED
    
    def get_connectivity_state(self) -> ConnectivityState:
        """Get current connectivity state."""
        return self.status.connectivity_state
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Get comprehensive connection status."""
        return {
            'state': self.status.state.value,
            'connectivity_state': self.status.connectivity_state.value,
            'connected': self.is_connected(),
            'connected_at': self.status.connected_at.isoformat() if self.status.connected_at else None,
            'client_id': self.config.client_id,
            'host': self.config.host,
            'port': self.config.port,
            'mode': self.config.mode.value
        }

# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================

def get_connection_manager(config: Optional[ConnectionConfig] = None) -> ConnectionManager:
    """Factory function to get ConnectionManager instance."""
    return ConnectionManager(config)

def create_connection_config(
    mode: ConnectionMode = ConnectionMode.PAPER,
    client_id: int = 1,
    **kwargs
) -> ConnectionConfig:
    """Factory function to create connection configuration."""
    config = ConnectionConfig(mode=mode, client_id=client_id)
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)
    return config

# ==============================================================================
# TESTING
# ==============================================================================

if __name__ == "__main__":
    print("Testing ConnectionManager with ConnectivityState.UNKNOWN...")
    
    # Test the critical enum
    print(f"ConnectivityState.UNKNOWN = {ConnectivityState.UNKNOWN}")
    print(f"ConnectivityState.CONNECTED = {ConnectivityState.CONNECTED}")
    
    # Test connection manager
    manager = get_connection_manager()
    status = manager.get_connection_status()
    print(f"Connection Manager Status: {status['connectivity_state']}")
    
    print("✅ ConnectionManager module working correctly!")
