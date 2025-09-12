#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker     
Module: SpyderB05_ConnectionManager.py
Purpose: IB Connection Management with unified ConnectivityState enum
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-09-11 Time: 19:30:00  

Module Description:
    Connection management module for Interactive Brokers Gateway with
    unified ConnectivityState enum that includes UNKNOWN state and
    all other states needed by the broader Spyder system.
    
    CRITICAL FIX: This module now exports the same ConnectivityState
    enum as SpyderB19_VPNManager to prevent import conflicts.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import logging
import threading
import time
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import socket

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    from ib_insync import IB, ConnectionError as IBConnectionError
    HAS_IB_INSYNC = True
except ImportError:
    HAS_IB_INSYNC = False
    print("WARNING: ib_insync not available for ConnectionManager")

# ==============================================================================
# SPYDER MODULE IMPORTS
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler, TradingError, ErrorCategory, ErrorSeverity
    HAS_SPYDER_UTILITIES = True
except ImportError:
    HAS_SPYDER_UTILITIES = False
    print("WARNING: SpyderU_Utilities not available for ConnectionManager")

# ==============================================================================
# UNIFIED CONNECTIVITY STATE ENUM - MATCHES SpyderB19_VPNManager
# ==============================================================================

class ConnectivityState(Enum):
    """
    Unified connectivity state enum used throughout Spyder system.
    
    CRITICAL: This enum must match the one in SpyderB19_VPNManager
    to prevent import conflicts and ensure UNKNOWN attribute exists.
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
    
    # Legacy states for backward compatibility
    ERROR = "failed"  # Alias for FAILED

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
    port: int = 4002  # Paper trading port by default
    client_id: int = 1
    mode: ConnectionMode = ConnectionMode.PAPER
    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 5.0
    auto_reconnect: bool = True
    backoff_multiplier: float = 2.0
    max_retry_delay: float = 60.0
    heartbeat_interval: float = 30.0
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.mode == ConnectionMode.LIVE:
            self.port = 4001  # Live trading port
        elif self.mode == ConnectionMode.PAPER:
            self.port = 4002  # Paper trading port

@dataclass
class ConnectionStatus:
    """Current connection status information."""
    state: ConnectionState = ConnectionState.IDLE
    connectivity_state: ConnectivityState = ConnectivityState.UNKNOWN
    connected_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    retry_count: int = 0
    last_error: Optional[str] = None
    gateway_version: Optional[str] = None
    server_version: Optional[str] = None
    connection_time: Optional[str] = None

@dataclass
class ConnectionMetrics:
    """Connection performance metrics."""
    total_connections: int = 0
    successful_connections: int = 0
    failed_connections: int = 0
    reconnections: int = 0
    average_connection_time: float = 0.0
    last_latency: float = 0.0
    uptime_seconds: float = 0.0

# ==============================================================================
# CONNECTION MANAGER CLASS
# ==============================================================================

class ConnectionManager:
    """
    Manages connections to Interactive Brokers Gateway with comprehensive
    error handling, retry logic, and status monitoring.
    """
    
    def __init__(self, config: Optional[ConnectionConfig] = None):
        """Initialize the connection manager."""
        self.config = config or ConnectionConfig()
        self.logger = self._setup_logging()
        self.error_handler = SpyderErrorHandler() if HAS_SPYDER_UTILITIES else None
        
        # Connection components
        self.ib: Optional[IB] = None
        self.status = ConnectionStatus()
        self.metrics = ConnectionMetrics()
        
        # Threading
        self.thread_pool = ThreadPoolExecutor(max_workers=4)
        self._shutdown_event = threading.Event()
        self._monitor_thread: Optional[threading.Thread] = None
        self.is_running = False
        
        # Callbacks
        self._state_callbacks: List[Callable] = []
        self._error_callbacks: List[Callable] = []
        
        # Set initial connectivity state
        self.status.connectivity_state = ConnectivityState.UNKNOWN
        
        self.logger.info(f"ConnectionManager initialized for {config.mode.value} mode on port {config.port}")
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for connection manager."""
        if HAS_SPYDER_UTILITIES:
            return SpyderLogger.get_logger("ConnectionManager")
        else:
            logger = logging.getLogger("ConnectionManager")
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
    # CONNECTION LIFECYCLE
    # ==========================================================================
    
    def connect(self) -> bool:
        """
        Connect to IB Gateway.
        
        Returns:
            bool: True if connection successful
        """
        try:
            self.logger.info(f"Connecting to IB Gateway at {self.config.host}:{self.config.port}")
            self._change_state(ConnectionState.CONNECTING)
            self.status.connectivity_state = ConnectivityState.CONNECTING
            
            # Initialize IB connection if available
            if HAS_IB_INSYNC:
                self.ib = IB()
                
                # Attempt connection with timeout
                start_time = time.time()
                
                try:
                    self.ib.connect(
                        host=self.config.host,
                        port=self.config.port,
                        clientId=self.config.client_id,
                        timeout=self.config.timeout
                    )
                    
                    connection_time = time.time() - start_time
                    
                    # Update status
                    self.status.connected_at = datetime.now()
                    self.status.last_activity = datetime.now()
                    self.status.connection_time = f"{connection_time:.2f}s"
                    self.status.retry_count = 0
                    self.status.last_error = None
                    
                    # Update metrics
                    self.metrics.total_connections += 1
                    self.metrics.successful_connections += 1
                    self.metrics.average_connection_time = (
                        (self.metrics.average_connection_time * (self.metrics.successful_connections - 1) + connection_time)
                        / self.metrics.successful_connections
                    )
                    
                    # Change states
                    self._change_state(ConnectionState.CONNECTED)
                    self.status.connectivity_state = ConnectivityState.CONNECTED
                    
                    # Start monitoring
                    self.is_running = True
                    self._start_monitoring()
                    
                    self.logger.info(f"Successfully connected to IB Gateway in {connection_time:.2f}s")
                    return True
                    
                except Exception as e:
                    self._handle_connection_failure(str(e))
                    return False
            else:
                # Simulate connection for testing
                self.logger.info("Simulating IB Gateway connection (ib_insync not available)")
                self.status.connected_at = datetime.now()
                self.status.last_activity = datetime.now()
                self.status.connection_time = "0.50s"
                self._change_state(ConnectionState.CONNECTED)
                self.status.connectivity_state = ConnectivityState.CONNECTED
                self.is_running = True
                return True
                
        except Exception as e:
            self.logger.error(f"Connection error: {e}")
            self._handle_connection_failure(str(e))
            return False
    
    def disconnect(self):
        """Disconnect from IB Gateway."""
        try:
            self.logger.info("Disconnecting from IB Gateway")
            self._change_state(ConnectionState.DISCONNECTING)
            self.status.connectivity_state = ConnectivityState.DISCONNECTING
            
            # Stop monitoring
            self.is_running = False
            self._shutdown_event.set()
            
            # Disconnect IB
            if self.ib and HAS_IB_INSYNC:
                self.ib.disconnect()
                self.ib = None
            
            # Update status
            self._change_state(ConnectionState.DISCONNECTED)
            self.status.connectivity_state = ConnectivityState.DISCONNECTED
            self.status.connected_at = None
            self.status.last_activity = None
            
            self.logger.info("Disconnected from IB Gateway")
            
        except Exception as e:
            self.logger.error(f"Disconnection error: {e}")
            self._change_state(ConnectionState.ERROR)
            self.status.connectivity_state = ConnectivityState.FAILED
    
    def reconnect(self) -> bool:
        """
        Reconnect to IB Gateway.
        
        Returns:
            bool: True if reconnection successful
        """
        self.logger.info("Attempting to reconnect to IB Gateway")
        self.metrics.reconnections += 1
        
        # Disconnect first
        self.disconnect()
        
        # Wait a moment
        time.sleep(2)
        
        # Reconnect
        return self.connect()
    
    # ==========================================================================
    # STATUS AND MONITORING
    # ==========================================================================
    
    def is_connected(self) -> bool:
        """
        Check if connected to IB Gateway.
        
        Returns:
            bool: True if connected
        """
        if HAS_IB_INSYNC and self.ib:
            return self.ib.isConnected()
        else:
            return self.status.state == ConnectionState.CONNECTED
    
    def get_connectivity_state(self) -> ConnectivityState:
        """
        Get current connectivity state.
        
        Returns:
            ConnectivityState: Current connectivity state
        """
        return self.status.connectivity_state
    
    def get_connection_status(self) -> Dict[str, Any]:
        """
        Get comprehensive connection status.
        
        Returns:
            Dict containing detailed status information
        """
        return {
            'state': self.status.state.value,
            'connectivity_state': self.status.connectivity_state.value,
            'connected': self.is_connected(),
            'connected_at': self.status.connected_at.isoformat() if self.status.connected_at else None,
            'last_activity': self.status.last_activity.isoformat() if self.status.last_activity else None,
            'retry_count': self.status.retry_count,
            'last_error': self.status.last_error,
            'connection_time': self.status.connection_time,
            'client_id': self.config.client_id,
            'host': self.config.host,
            'port': self.config.port,
            'mode': self.config.mode.value,
            'metrics': {
                'total_connections': self.metrics.total_connections,
                'successful_connections': self.metrics.successful_connections,
                'failed_connections': self.metrics.failed_connections,
                'reconnections': self.metrics.reconnections,
                'average_connection_time': self.metrics.average_connection_time,
                'uptime_seconds': self.metrics.uptime_seconds
            }
        }
    
    def test_connectivity(self) -> bool:
        """
        Test connectivity to IB Gateway without connecting.
        
        Returns:
            bool: True if gateway is reachable
        """
        try:
            sock = socket.create_connection((self.config.host, self.config.port), timeout=5)
            sock.close()
            return True
        except Exception:
            return False
    
    # ==========================================================================
    # MONITORING AND HEALTH CHECKS
    # ==========================================================================
    
    def _start_monitoring(self):
        """Start connection monitoring thread."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return
        
        self._monitor_thread = threading.Thread(target=self._monitor_connection, daemon=True)
        self._monitor_thread.start()
        self.logger.debug("Connection monitoring started")
    
    def _monitor_connection(self):
        """Monitor connection health in background thread."""
        while self.is_running and not self._shutdown_event.is_set():
            try:
                # Update uptime
                if self.status.connected_at:
                    self.metrics.uptime_seconds = (datetime.now() - self.status.connected_at).total_seconds()
                
                # Check connection health
                if self.is_connected():
                    self.status.last_activity = datetime.now()
                    
                    # Update connectivity state based on connection quality
                    if self._is_connection_healthy():
                        self.status.connectivity_state = ConnectivityState.OPTIMAL
                    else:
                        self.status.connectivity_state = ConnectivityState.DEGRADED
                else:
                    # Connection lost
                    self.logger.warning("Connection lost during monitoring")
                    self.status.connectivity_state = ConnectivityState.DISCONNECTED
                    
                    if self.config.auto_reconnect:
                        self.logger.info("Attempting automatic reconnection")
                        if self.reconnect():
                            self.logger.info("Automatic reconnection successful")
                        else:
                            self.logger.error("Automatic reconnection failed")
                
                # Sleep until next check
                self._shutdown_event.wait(self.config.heartbeat_interval)
                
            except Exception as e:
                self.logger.error(f"Connection monitoring error: {e}")
                self._shutdown_event.wait(60)  # Wait longer on error
    
    def _is_connection_healthy(self) -> bool:
        """Check if connection is healthy."""
        if not self.is_connected():
            return False
        
        # Add more health checks here as needed
        # For now, just check if we're connected
        return True
    
    # ==========================================================================
    # ERROR HANDLING
    # ==========================================================================
    
    def _handle_connection_failure(self, error_msg: str):
        """Handle connection failure with retry logic."""
        self.status.retry_count += 1
        self.status.last_error = error_msg
        self.metrics.failed_connections += 1
        
        self.logger.error(f"Connection failed (attempt {self.status.retry_count}): {error_msg}")
        
        # Update connectivity state
        self.status.connectivity_state = ConnectivityState.FAILED
        
        # Check if we should retry
        if (self.config.auto_reconnect and 
            self.status.retry_count < self.config.max_retries):
            
            # Calculate retry delay with exponential backoff
            delay = min(
                self.config.retry_delay * (self.config.backoff_multiplier ** (self.status.retry_count - 1)),
                self.config.max_retry_delay
            )
            
            self.logger.info(f"Retrying connection in {delay:.1f} seconds...")
            self._change_state(ConnectionState.RETRYING)
            self.status.connectivity_state = ConnectivityState.RECONNECTING
            
            # Schedule retry
            def retry_connection():
                time.sleep(delay)
                if self.is_running and not self._shutdown_event.is_set():
                    self.connect()
            
            self.thread_pool.submit(retry_connection)
            
        else:
            # Max retries reached or auto-reconnect disabled
            self._change_state(ConnectionState.ERROR)
            self.status.connectivity_state = ConnectivityState.FAILED
    
    # ==========================================================================
    # STATE MANAGEMENT
    # ==========================================================================
    
    def _change_state(self, new_state: ConnectionState):
        """Change connection state and notify callbacks."""
        old_state = self.status.state
        
        if old_state != new_state:
            self.status.state = new_state
            
            self.logger.debug(f"State changed: {old_state.value} -> {new_state.value}")
            
            # Notify callbacks
            for callback in self._state_callbacks:
                try:
                    callback(old_state, new_state)
                except Exception as e:
                    self.logger.error(f"State callback error: {e}")
    
    # ==========================================================================
    # CALLBACK MANAGEMENT
    # ==========================================================================
    
    def add_state_callback(self, callback: Callable):
        """Add callback for state changes."""
        self._state_callbacks.append(callback)
    
    def remove_state_callback(self, callback: Callable):
        """Remove state callback."""
        if callback in self._state_callbacks:
            self._state_callbacks.remove(callback)
    
    def add_error_callback(self, callback: Callable):
        """Add callback for errors."""
        self._error_callbacks.append(callback)
    
    def remove_error_callback(self, callback: Callable):
        """Remove error callback."""
        if callback in self._error_callbacks:
            self._error_callbacks.remove(callback)
    
    # ==========================================================================
    # CLEANUP
    # ==========================================================================
    
    def shutdown(self):
        """Shutdown connection manager cleanly."""
        self.logger.info("Shutting down ConnectionManager")
        
        # Stop monitoring
        self.is_running = False
        self._shutdown_event.set()
        
        # Disconnect
        self.disconnect()
        
        # Shutdown thread pool
        self.thread_pool.shutdown(wait=True)
        
        self.logger.info("ConnectionManager shutdown complete")

# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================

def get_connection_manager(config: Optional[ConnectionConfig] = None) -> ConnectionManager:
    """
    Factory function to get ConnectionManager instance.
    
    Args:
        config: Optional connection configuration
        
    Returns:
        ConnectionManager: Configured connection manager
    """
    return ConnectionManager(config)

def create_connection_config(
    mode: ConnectionMode = ConnectionMode.PAPER,
    client_id: int = 1,
    **kwargs
) -> ConnectionConfig:
    """
    Factory function to create connection configuration.
    
    Args:
        mode: Connection mode (PAPER or LIVE)
        client_id: Client ID for connection
        **kwargs: Additional configuration options
        
    Returns:
        ConnectionConfig: Configured connection config
    """
    config = ConnectionConfig(mode=mode, client_id=client_id)
    
    # Update with any additional kwargs
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)
    
    return config

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================

def initialize_connection_module() -> bool:
    """
    Initialize the connection module.
    
    Returns:
        bool: True if initialization successful
    """
    try:
        # Test enum availability
        test_connectivity = ConnectivityState.UNKNOWN
        test_connection = ConnectionState.IDLE
        
        # Test manager creation
        manager = get_connection_manager()
        
        return True
        
    except Exception as e:
        print(f"Connection module initialization failed: {e}")
        return False

# ==============================================================================
# MAIN EXECUTION FOR TESTING
# ==============================================================================

if __name__ == "__main__":
    print("SPYDER Connection Manager - Module Test")
    print("=" * 50)
    
    # Test initialization
    if initialize_connection_module():
        print("✅ Connection module initialized successfully")
        
        # Test connectivity states
        print(f"✅ ConnectivityState.UNKNOWN: {ConnectivityState.UNKNOWN}")
        print(f"✅ ConnectivityState.CONNECTED: {ConnectivityState.CONNECTED}")
        print(f"✅ ConnectionState.IDLE: {ConnectionState.IDLE}")
        
        # Test manager
        config = create_connection_config(mode=ConnectionMode.PAPER, client_id=1)
        manager = get_connection_manager(config)
        print(f"✅ Connection Manager created: {type(manager)}")
        
        status = manager.get_connection_status()
        print(f"✅ Status retrieved: {status['connectivity_state']}")
        
        print("\n✅ All Connection Manager tests passed!")
        
    else:
        print("❌ Connection module initialization failed")
        exit(1)
        
def create_contract_builder(cache_size=1000):
    """Factory function for __init__.py compatibility."""
    return get_contract_builder()


# Export list for proper module imports
__all__ = [
    'ContractBuilder',
    'get_contract_builder', 
    'create_contract_builder',
    'build_spy_stock',
    'build_spy_option'
]
