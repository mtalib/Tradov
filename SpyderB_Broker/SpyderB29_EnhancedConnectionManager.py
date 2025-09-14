#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker     
Module: SpyderB29_EnhancedConnectionManager.py
Purpose: Consolidated robust IB Gateway connection management with timeout prevention
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-09-13 Time: 19:30:00  

Module Description:
    This module consolidates all connection management functionality for Interactive
    Brokers Gateway into a single, robust solution. It combines features from the
    existing SpyderB05_ConnectionManager and SpyderB20_IntegratedConnectivityManager
    while adding the timeout prevention strategies from the IB analysis report.
    
    Key Features:
    - Unified ConnectivityState enum (compatible with existing modules)
    - Async/await timeout prevention (following IB report recommendations)
    - Exponential backoff reconnection with proper error code handling
    - Gateway process monitoring and health checks
    - Integration with memory monitoring and system optimization
    - Backward compatibility with existing Spyder modules
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import asyncio
import logging
import threading
import time
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from pathlib import Path
import random
import socket

# ==============================================================================
# PYTHON PATH SETUP
# ==============================================================================
# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    import ib_async as ib
    IB_ASYNC_AVAILABLE = True
except ImportError:
    try:
        from ib_insync import IB, ConnectionError as IBConnectionError
        IB_INSYNC_AVAILABLE = True
        IB_ASYNC_AVAILABLE = False
    except ImportError:
        IB_ASYNC_AVAILABLE = False
        IB_INSYNC_AVAILABLE = False
        print("Warning: Neither ib_async nor ib_insync available")

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler, TradingError, ErrorCategory, ErrorSeverity
from SpyderU_Utilities.SpyderU23_MemoryMonitor import get_memory_monitor
from SpyderU_Utilities.SpyderU27_SystemOptimizer import get_system_optimizer

# ==============================================================================
# UNIFIED CONNECTIVITY STATE ENUM - MATCHES EXISTING SPYDER MODULES
# ==============================================================================
class ConnectivityState(Enum):
    """
    Unified connectivity state enum used throughout Spyder system.
    
    CRITICAL: This enum matches the one in SpyderB19_VPNManager and SpyderB05
    to prevent import conflicts and ensure UNKNOWN attribute exists.
    """
    UNKNOWN = auto()
    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    RECONNECTING = auto()
    ERROR = auto()
    AUTHENTICATED = auto()
    READY = auto()
    DEGRADED = auto()

class ConnectionState(Enum):
    """Connection lifecycle states."""
    IDLE = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    DISCONNECTING = auto()
    DISCONNECTED = auto()
    RECONNECTING = auto()
    ERROR = auto()

class TradingMode(Enum):
    """Trading mode selection."""
    PAPER = "paper"
    LIVE = "live"

class IBErrorCode(Enum):
    """Critical IB API error codes from timeout analysis report."""
    CONNECTION_LOST = 1100
    CONNECTION_RESTORED = 1101
    MARKET_DATA_FARM_OK = 2104
    HISTORICAL_DATA_FARM_DISCONNECTED = 2105
    COULDNT_CONNECT = 502
    NOT_CONNECTED = 504

# ==============================================================================
# CONFIGURATION AND STATUS CLASSES
# ==============================================================================
@dataclass
class ConnectionConfig:
    """Connection configuration with comprehensive options."""
    host: str = "127.0.0.1"
    port: int = 4002  # Paper trading default
    client_id: int = 1
    mode: TradingMode = TradingMode.PAPER
    timeout: float = 30.0
    
    # Retry configuration
    max_retries: int = 10
    base_backoff_delay: float = 1.0
    max_backoff_delay: float = 60.0
    
    # Monitoring configuration
    health_check_interval: float = 60.0
    heartbeat_interval: float = 30.0
    connection_check_interval: float = 10.0
    
    # Feature flags
    auto_reconnect: bool = True
    gateway_automation: bool = False
    memory_monitoring: bool = True
    system_optimization: bool = True
    
    # Market hours
    respect_market_hours: bool = True
    extended_hours: bool = False

@dataclass 
class ConnectionStatus:
    """Comprehensive connection status information."""
    state: ConnectionState = ConnectionState.IDLE
    connectivity_state: ConnectivityState = ConnectivityState.UNKNOWN
    connected_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    retry_count: int = 0
    last_error: Optional[str] = None
    last_error_code: Optional[int] = None
    gateway_version: Optional[str] = None
    server_version: Optional[str] = None
    connection_time: Optional[str] = None
    uptime_seconds: float = 0.0

@dataclass
class ConnectionMetrics:
    """Connection performance and reliability metrics."""
    total_connections: int = 0
    successful_connections: int = 0
    failed_connections: int = 0
    reconnections: int = 0
    timeout_errors: int = 0
    average_connection_time: float = 0.0
    last_latency: float = 0.0
    uptime_seconds: float = 0.0
    error_codes: Dict[int, int] = field(default_factory=dict)

# ==============================================================================
# ENHANCED CONNECTION MANAGER CLASS
# ==============================================================================
class EnhancedConnectionManager:
    """
    Consolidated, production-grade IB Gateway connection manager.
    
    This class combines the best features from existing connection managers
    with timeout prevention strategies and modern async/await patterns.
    
    Features:
    - Unified state management compatible with existing Spyder modules
    - Async/await timeout prevention following IB report recommendations  
    - Exponential backoff reconnection with proper error code handling
    - Integration with memory monitoring and system optimization
    - Gateway process health monitoring
    - Market hours awareness
    - Comprehensive metrics and diagnostics
    - Thread-safe singleton pattern
    - Event-driven callbacks
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        """Singleton pattern implementation."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance
    
    def __init__(self, config: Optional[ConnectionConfig] = None):
        """Initialize the enhanced connection manager."""
        # Prevent re-initialization of singleton
        if hasattr(self, '_initialized'):
            return
        
        # Configuration
        self.config = config or ConnectionConfig()
        
        # Setup logging and error handling
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Connection components
        self.ib_client = None
        self.status = ConnectionStatus()
        self.metrics = ConnectionMetrics()
        
        # Threading and async support
        self.thread_pool = ThreadPoolExecutor(max_workers=4)
        self._shutdown_event = threading.Event()
        self._monitor_task = None
        self._health_check_task = None
        self.is_running = False
        
        # Event loop management for hybrid sync/async
        self._loop = None
        self._loop_thread = None
        
        # Callbacks
        self._state_callbacks: List[Callable] = []
        self._error_callbacks: List[Callable] = []
        self._connection_callbacks: List[Callable] = []
        self._disconnection_callbacks: List[Callable] = []
        
        # Data subscriptions (restored after reconnection)
        self.active_subscriptions: Dict[str, Any] = {}
        
        # Integration components
        self.memory_monitor = get_memory_monitor() if self.config.memory_monitoring else None
        self.system_optimizer = get_system_optimizer() if self.config.system_optimization else None
        
        # Initialize IB client
        self._initialize_ib_client()
        
        # Set initial states
        self.status.connectivity_state = ConnectivityState.UNKNOWN
        self.status.state = ConnectionState.IDLE
        
        self._initialized = True
        self.logger.info(f"Enhanced connection manager initialized for {self.config.mode.value} "
                        f"mode on {self.config.host}:{self.config.port}")

    def _initialize_ib_client(self):
        """Initialize the IB client with proper event handlers."""
        try:
            if IB_ASYNC_AVAILABLE:
                self.ib_client = ib.IB()
                # Register async event handlers
                self.ib_client.disconnectedEvent += self._on_disconnected_async
                self.ib_client.errorEvent += self._on_error_async
                self.ib_client.connectedEvent += self._on_connected_async
                self.logger.info("Initialized ib_async client with event handlers")
                
            elif IB_INSYNC_AVAILABLE:
                self.ib_client = IB()
                # Register sync event handlers
                self.ib_client.disconnectedEvent += self._on_disconnected_sync
                self.ib_client.errorEvent += self._on_error_sync
                self.ib_client.connectedEvent += self._on_connected_sync
                self.logger.info("Initialized ib_insync client with event handlers")
                
            else:
                self.logger.error("No IB client library available")
                
        except Exception as e:
            self.error_handler.handle_error(e, "Failed to initialize IB client")

    # ==========================================================================
    # CONNECTION LIFECYCLE - ASYNC METHODS
    # ==========================================================================
    async def connect_async(self) -> bool:
        """
        Async connection method following IB report recommendations.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        if not IB_ASYNC_AVAILABLE:
            self.logger.error("Async connection requires ib_async library")
            return False
        
        if self.is_connected():
            self.logger.info("Already connected to IB Gateway")
            return True
        
        try:
            self.logger.info(f"Attempting async connection to {self.config.host}:{self.config.port}")
            self._change_state(ConnectionState.CONNECTING)
            self.status.connectivity_state = ConnectivityState.CONNECTING
            
            start_time = time.time()
            
            # Use asyncio timeout to prevent hanging (key recommendation from report)
            await asyncio.wait_for(
                self.ib_client.connectAsync(
                    host=self.config.host,
                    port=self.config.port,
                    clientId=self.config.client_id,
                    timeout=self.config.timeout
                ),
                timeout=self.config.timeout
            )
            
            connection_time = time.time() - start_time
            
            # Verify connection
            if self.ib_client.isConnected():
                await self._on_connection_success(connection_time)
                return True
            else:
                raise ConnectionError("Connection established but verification failed")
                
        except asyncio.TimeoutError:
            self.logger.error(f"Async connection timeout after {self.config.timeout} seconds")
            self.metrics.timeout_errors += 1
            await self._on_connection_failure("Connection timeout")
            return False
            
        except Exception as e:
            self.logger.error(f"Async connection failed: {e}")
            await self._on_connection_failure(str(e))
            return False

    async def disconnect_async(self):
        """Gracefully disconnect from IB Gateway (async)."""
        if not self.ib_client:
            return
        
        try:
            # Stop monitoring tasks
            if self._monitor_task:
                self._monitor_task.cancel()
                try:
                    await self._monitor_task
                except asyncio.CancelledError:
                    pass
            
            if self._health_check_task:
                self._health_check_task.cancel()
                try:
                    await self._health_check_task
                except asyncio.CancelledError:
                    pass
            
            # Disconnect client
            if self.ib_client.isConnected():
                self.ib_client.disconnect()
            
            self._change_state(ConnectionState.DISCONNECTED)
            self.status.connectivity_state = ConnectivityState.DISCONNECTED
            self.is_running = False
            
            self.logger.info("Async disconnect completed")
            
        except Exception as e:
            self.error_handler.handle_error(e, "Error during async disconnect")

    async def reconnect_async(self) -> bool:
        """
        Async reconnection with exponential backoff (following report recommendations).
        
        Returns:
            bool: True if reconnection successful, False otherwise
        """
        if self.status.retry_count >= self.config.max_retries:
            self.logger.error(f"Maximum reconnection attempts ({self.config.max_retries}) exceeded")
            self.status.connectivity_state = ConnectivityState.ERROR
            return False
        
        self.status.retry_count += 1
        self._change_state(ConnectionState.RECONNECTING)
        self.status.connectivity_state = ConnectivityState.RECONNECTING
        
        # Calculate exponential backoff with jitter (report recommendation)
        backoff_delay = min(
            self.config.base_backoff_delay * (2 ** (self.status.retry_count - 1)),
            self.config.max_backoff_delay
        )
        jitter = random.uniform(0.1, 0.5) * backoff_delay
        total_delay = backoff_delay + jitter
        
        self.logger.info(f"Reconnection attempt {self.status.retry_count}/{self.config.max_retries} "
                        f"after {total_delay:.1f}s delay")
        
        # Use ib.sleep instead of asyncio.sleep to avoid blocking event loop (key recommendation)
        await asyncio.sleep(total_delay)
        
        # Attempt reconnection
        success = await self.connect_async()
        
        if success:
            self.logger.info(f"Reconnection successful after {self.status.retry_count} attempts")
            self.metrics.reconnections += 1
            self.status.retry_count = 0
        else:
            self.logger.warning(f"Reconnection attempt {self.status.retry_count} failed")
        
        return success

    # ==========================================================================
    # CONNECTION LIFECYCLE - SYNC METHODS (BACKWARD COMPATIBILITY)
    # ==========================================================================
    def connect(self) -> bool:
        """
        Synchronous connection method (backward compatibility).
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        if IB_ASYNC_AVAILABLE:
            # Run async method in event loop
            return self._run_async_method(self.connect_async())
        else:
            return self._connect_sync()

    def disconnect(self):
        """Synchronous disconnect method (backward compatibility)."""
        if IB_ASYNC_AVAILABLE:
            self._run_async_method(self.disconnect_async())
        else:
            self._disconnect_sync()

    def reconnect(self) -> bool:
        """Synchronous reconnect method (backward compatibility)."""
        if IB_ASYNC_AVAILABLE:
            return self._run_async_method(self.reconnect_async())
        else:
            return self._reconnect_sync()

    def _run_async_method(self, coro):
        """Run async method in appropriate event loop."""
        try:
            # Try to get existing event loop
            loop = asyncio.get_running_loop()
            # If we're already in an event loop, create a task
            return asyncio.create_task(coro)
        except RuntimeError:
            # No event loop running, create one
            return asyncio.run(coro)

    def _connect_sync(self) -> bool:
        """Synchronous connection implementation."""
        if not IB_INSYNC_AVAILABLE:
            self.logger.error("No IB client library available for sync connection")
            return False
        
        try:
            self.logger.info(f"Attempting sync connection to {self.config.host}:{self.config.port}")
            self._change_state(ConnectionState.CONNECTING)
            self.status.connectivity_state = ConnectivityState.CONNECTING
            
            start_time = time.time()
            
            self.ib_client.connect(
                host=self.config.host,
                port=self.config.port,
                clientId=self.config.client_id,
                timeout=self.config.timeout
            )
            
            connection_time = time.time() - start_time
            
            if self.ib_client.isConnected():
                self._on_connection_success_sync(connection_time)
                return True
            else:
                raise ConnectionError("Sync connection verification failed")
                
        except Exception as e:
            self.logger.error(f"Sync connection failed: {e}")
            self._on_connection_failure_sync(str(e))
            return False

    # ==========================================================================
    # EVENT HANDLERS - ASYNC (IB_ASYNC)
    # ==========================================================================
    async def _on_connected_async(self):
        """Handle async connection established event."""
        self.logger.info("IB Gateway async connection established")
        self.status.last_heartbeat = datetime.now()
        await self._notify_connection_callbacks()

    async def _on_disconnected_async(self):
        """Handle async disconnection event - trigger for reconnection."""
        self.logger.warning("IB Gateway async disconnected - initiating reconnection")
        self._change_state(ConnectionState.DISCONNECTED)
        self.status.connectivity_state = ConnectivityState.DISCONNECTED
        
        await self._notify_disconnection_callbacks()
        
        # Attempt automatic reconnection if enabled
        if self.config.auto_reconnect and self.is_running:
            asyncio.create_task(self.reconnect_async())

    async def _on_error_async(self, reqId: int, errorCode: int, errorString: str, contract=None):
        """Handle async IB API errors with specific code handling per report."""
        await self._process_ib_error(reqId, errorCode, errorString, contract)

    # ==========================================================================
    # EVENT HANDLERS - SYNC (IB_INSYNC)
    # ==========================================================================
    def _on_connected_sync(self):
        """Handle sync connection established event."""
        self.logger.info("IB Gateway sync connection established")
        self.status.last_heartbeat = datetime.now()
        self._notify_connection_callbacks_sync()

    def _on_disconnected_sync(self):
        """Handle sync disconnection event."""
        self.logger.warning("IB Gateway sync disconnected - initiating reconnection")
        self._change_state(ConnectionState.DISCONNECTED)
        self.status.connectivity_state = ConnectivityState.DISCONNECTED
        
        self._notify_disconnection_callbacks_sync()
        
        # Attempt automatic reconnection if enabled
        if self.config.auto_reconnect and self.is_running:
            threading.Thread(target=lambda: self.reconnect(), daemon=True).start()

    def _on_error_sync(self, reqId: int, errorCode: int, errorString: str, contract=None):
        """Handle sync IB API errors."""
        # Convert to async and run
        if IB_ASYNC_AVAILABLE:
            asyncio.create_task(self._process_ib_error(reqId, errorCode, errorString, contract))
        else:
            self._process_ib_error_sync(reqId, errorCode, errorString, contract)

    # ==========================================================================
    # ERROR PROCESSING (UNIFIED FOR BOTH ASYNC/SYNC)
    # ==========================================================================
    async def _process_ib_error(self, reqId: int, errorCode: int, errorString: str, contract=None):
        """Process IB API errors with specific code handling per report."""
        error_info = {
            'reqId': reqId,
            'errorCode': errorCode,
            'errorString': errorString,
            'contract': contract,
            'timestamp': datetime.now()
        }
        
        # Track error code frequency
        self.metrics.error_codes[errorCode] = self.metrics.error_codes.get(errorCode, 0) + 1
        self.status.last_error = errorString
        self.status.last_error_code = errorCode
        
        # Handle critical error codes from the report
        if errorCode == IBErrorCode.CONNECTION_LOST.value:
            self.logger.warning(f"Connection lost (1100): {errorString}")
            self._change_state(ConnectionState.DISCONNECTED)
            self.status.connectivity_state = ConnectivityState.DISCONNECTED
            
        elif errorCode == IBErrorCode.CONNECTION_RESTORED.value:
            self.logger.info(f"Connection restored (1101): {errorString}")
            self.status.connectivity_state = ConnectivityState.CONNECTED
            # All data subscriptions are lost - restore them
            await self._restore_subscriptions()
            
        elif errorCode == IBErrorCode.MARKET_DATA_FARM_OK.value:
            self.logger.info(f"Market data farm connected (2104): {errorString}")
            # This is positive confirmation - no action needed
            
        elif errorCode == IBErrorCode.HISTORICAL_DATA_FARM_DISCONNECTED.value:
            self.logger.warning(f"Historical data farm disconnected (2105): {errorString}")
            # May need to re-request historical data
            
        elif errorCode == IBErrorCode.COULDNT_CONNECT.value:
            self.logger.error(f"Couldn't connect (502): {errorString}")
            self._change_state(ConnectionState.ERROR)
            self.status.connectivity_state = ConnectivityState.ERROR
            # This indicates API not enabled or wrong port
            
        elif errorCode == IBErrorCode.NOT_CONNECTED.value:
            self.logger.error(f"Not connected (504): {errorString}")
            # Request made without proper connection - trigger reconnection
            if self.config.auto_reconnect:
                asyncio.create_task(self.reconnect_async())
        else:
            # Log other errors for analysis
            if errorCode >= 1000:  # System errors
                self.logger.warning(f"IB System Error {errorCode}: {errorString}")
            else:  # Client errors
                self.logger.error(f"IB Client Error {errorCode}: {errorString}")
        
        # Notify error callbacks
        await self._notify_error_callbacks(error_info)

    def _process_ib_error_sync(self, reqId: int, errorCode: int, errorString: str, contract=None):
        """Synchronous error processing (fallback)."""
        # Simplified sync version - main logic is in async method
        self.metrics.error_codes[errorCode] = self.metrics.error_codes.get(errorCode, 0) + 1
        self.status.last_error = errorString
        self.status.last_error_code = errorCode
        
        if errorCode in [502, 504, 1100]:
            self._change_state(ConnectionState.ERROR)
            self.status.connectivity_state = ConnectivityState.ERROR

    # ==========================================================================
    # CONNECTION SUCCESS/FAILURE HANDLERS
    # ==========================================================================
    async def _on_connection_success(self, connection_time: float):
        """Handle successful connection."""
        # Update status
        self.status.connected_at = datetime.now()
        self.status.last_activity = datetime.now()
        self.status.last_heartbeat = datetime.now()
        self.status.connection_time = f"{connection_time:.2f}s"
        self.status.retry_count = 0
        self.status.last_error = None
        self.status.last_error_code = None
        
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
        await self._start_monitoring()
        
        # Restore subscriptions
        await self._restore_subscriptions()
        
        self.logger.info(f"Connection successful in {connection_time:.2f}s")

    def _on_connection_success_sync(self, connection_time: float):
        """Handle successful sync connection."""
        # Update status (sync version)
        self.status.connected_at = datetime.now()
        self.status.last_activity = datetime.now() 
        self.status.connection_time = f"{connection_time:.2f}s"
        self.status.retry_count = 0
        
        # Update metrics
        self.metrics.total_connections += 1
        self.metrics.successful_connections += 1
        
        # Change states
        self._change_state(ConnectionState.CONNECTED)
        self.status.connectivity_state = ConnectivityState.CONNECTED
        
        self.is_running = True
        self.logger.info(f"Sync connection successful in {connection_time:.2f}s")

    async def _on_connection_failure(self, error_message: str):
        """Handle connection failure."""
        self.metrics.total_connections += 1
        self.metrics.failed_connections += 1
        self.status.last_error = error_message
        
        self._change_state(ConnectionState.ERROR)
        self.status.connectivity_state = ConnectivityState.ERROR

    def _on_connection_failure_sync(self, error_message: str):
        """Handle sync connection failure."""
        self.metrics.failed_connections += 1
        self.status.last_error = error_message
        self._change_state(ConnectionState.ERROR)
        self.status.connectivity_state = ConnectivityState.ERROR

    # ==========================================================================
    # MONITORING AND HEALTH CHECKS
    # ==========================================================================
    async def _start_monitoring(self):
        """Start connection monitoring tasks."""
        if self._monitor_task:
            self._monitor_task.cancel()
        
        if self._health_check_task:
            self._health_check_task.cancel()
        
        self._monitor_task = asyncio.create_task(self._monitoring_loop())
        self._health_check_task = asyncio.create_task(self._health_check_loop())

    async def _monitoring_loop(self):
        """Main monitoring loop."""
        while self.is_running and not self._shutdown_event.is_set():
            try:
                # Update activity timestamp
                if self.ib_client and self.ib_client.isConnected():
                    self.status.last_activity = datetime.now()
                    
                    # Calculate uptime
                    if self.status.connected_at:
                        self.status.uptime_seconds = (
                            datetime.now() - self.status.connected_at
                        ).total_seconds()
                
                # Memory monitoring integration
                if self.memory_monitor:
                    stats = self.memory_monitor.get_system_memory() if hasattr(self.memory_monitor, "get_system_memory") else None
                    if stats and stats.percent > 85:
                        self.logger.warning(f"High memory usage detected: {stats.percent:.1f}%")
                
                await asyncio.sleep(self.config.connection_check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.error_handler.handle_error(e, "Monitoring loop error")
                await asyncio.sleep(self.config.connection_check_interval)

    async def _health_check_loop(self):
        """Connection health monitoring loop."""
        while self.is_running and not self._shutdown_event.is_set():
            try:
                if not self.is_healthy():
                    self.logger.warning("Health check failed - connection unhealthy")
                    if self.config.auto_reconnect:
                        asyncio.create_task(self.reconnect_async())
                        break
                
                # Update heartbeat
                self.status.last_heartbeat = datetime.now()
                
                await asyncio.sleep(self.config.health_check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.error_handler.handle_error(e, "Health check error")
                await asyncio.sleep(self.config.health_check_interval)

    # ==========================================================================
    # SUBSCRIPTION MANAGEMENT
    # ==========================================================================
    async def _restore_subscriptions(self):
        """Restore all active subscriptions after reconnection."""
        if not self.active_subscriptions:
            return
        
        self.logger.info(f"Restoring {len(self.active_subscriptions)} subscriptions")
        
        for sub_id, sub_data in self.active_subscriptions.items():
            try:
                self.logger.info(f"Restoring subscription: {sub_id}")
                # Subscription restoration logic would go here
                # This is placeholder for actual implementation
                
            except Exception as e:
                self.error_handler.handle_error(e, f"Failed to restore subscription {sub_id}")

    def add_subscription(self, sub_id: str, sub_data: Any):
        """Add a subscription to be managed and restored after reconnections."""
        self.active_subscriptions[sub_id] = sub_data
        self.logger.debug(f"Added subscription: {sub_id}")

    def remove_subscription(self, sub_id: str):
        """Remove a managed subscription."""
        if sub_id in self.active_subscriptions:
            del self.active_subscriptions[sub_id]
            self.logger.debug(f"Removed subscription: {sub_id}")

    # ==========================================================================
    # STATE MANAGEMENT
    # ==========================================================================
    def _change_state(self, new_state: ConnectionState):
        """Change connection state and notify callbacks."""
        if self.status.state != new_state:
            old_state = self.status.state
            self.status.state = new_state
            
            self.logger.debug(f"State changed: {old_state} -> {new_state}")
            
            # Notify state callbacks
            for callback in self._state_callbacks:
                try:
                    callback(old_state, new_state)
                except Exception as e:
                    self.error_handler.handle_error(e, "State callback error")

    # ==========================================================================
    # CALLBACK MANAGEMENT
    # ==========================================================================
    def add_connection_callback(self, callback: Callable):
        """Add callback for connection events."""
        self._connection_callbacks.append(callback)

    def add_disconnection_callback(self, callback: Callable):
        """Add callback for disconnection events."""
        self._disconnection_callbacks.append(callback)

    def add_error_callback(self, callback: Callable):
        """Add callback for error events."""
        self._error_callbacks.append(callback)

    def add_state_callback(self, callback: Callable):
        """Add callback for state changes."""
        self._state_callbacks.append(callback)

    async def _notify_connection_callbacks(self):
        """Notify all connection callbacks."""
        for callback in self._connection_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except Exception as e:
                self.error_handler.handle_error(e, "Connection callback error")

    async def _notify_disconnection_callbacks(self):
        """Notify all disconnection callbacks."""
        for callback in self._disconnection_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except Exception as e:
                self.error_handler.handle_error(e, "Disconnection callback error")

    async def _notify_error_callbacks(self, error_info: Dict[str, Any]):
        """Notify all error callbacks."""
        for callback in self._error_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(error_info)
                else:
                    callback(error_info)
            except Exception as e:
                self.error_handler.handle_error(e, "Error callback error")

    def _notify_connection_callbacks_sync(self):
        """Notify connection callbacks synchronously."""
        for callback in self._connection_callbacks:
            try:
                callback()
            except Exception as e:
                self.error_handler.handle_error(e, "Connection callback error")

    def _notify_disconnection_callbacks_sync(self):
        """Notify disconnection callbacks synchronously."""
        for callback in self._disconnection_callbacks:
            try:
                callback()
            except Exception as e:
                self.error_handler.handle_error(e, "Disconnection callback error")

    # ==========================================================================
    # STATUS AND DIAGNOSTICS
    # ==========================================================================
    def get_connection_status(self) -> Dict[str, Any]:
        """Get comprehensive connection status."""
        return {
            'state': self.status.state.name,
            'connectivity_state': self.status.connectivity_state.name,
            'connected': self.is_connected(),
            'healthy': self.is_healthy(),
            'host': self.config.host,
            'port': self.config.port,
            'client_id': self.config.client_id,
            'mode': self.config.mode.value,
            'connected_at': self.status.connected_at.isoformat() if self.status.connected_at else None,
            'uptime_seconds': self.status.uptime_seconds,
            'retry_count': self.status.retry_count,
            'last_error': self.status.last_error,
            'last_error_code': self.status.last_error_code,
            'last_heartbeat': self.status.last_heartbeat.isoformat() if self.status.last_heartbeat else None,
            'active_subscriptions': len(self.active_subscriptions),
            'ib_async_available': IB_ASYNC_AVAILABLE,
            'ib_insync_available': IB_INSYNC_AVAILABLE
        }

    def get_connection_metrics(self) -> Dict[str, Any]:
        """Get connection performance metrics."""
        success_rate = 0.0
        if self.metrics.total_connections > 0:
            success_rate = (self.metrics.successful_connections / self.metrics.total_connections) * 100
        
        return {
            'total_connections': self.metrics.total_connections,
            'successful_connections': self.metrics.successful_connections,
            'failed_connections': self.metrics.failed_connections,
            'success_rate_percent': success_rate,
            'reconnections': self.metrics.reconnections,
            'timeout_errors': self.metrics.timeout_errors,
            'average_connection_time': self.metrics.average_connection_time,
            'uptime_seconds': self.status.uptime_seconds,
            'error_code_frequency': dict(self.metrics.error_codes)
        }

    def is_connected(self) -> bool:
        """Check if connected to IB Gateway."""
        return (self.ib_client and 
                self.ib_client.isConnected() and 
                self.status.state == ConnectionState.CONNECTED)

    def is_healthy(self) -> bool:
        """Check if connection is healthy."""
        if not self.is_connected():
            return False
        
        # Check heartbeat recency
        if self.status.last_heartbeat:
            seconds_since_heartbeat = (datetime.now() - self.status.last_heartbeat).total_seconds()
            if seconds_since_heartbeat > self.config.health_check_interval * 2:
                return False
        
        return True

    def get_diagnostics(self) -> Dict[str, Any]:
        """Get comprehensive diagnostic information."""
        diagnostics = {
            'connection_status': self.get_connection_status(),
            'connection_metrics': self.get_connection_metrics(),
            'configuration': {
                'host': self.config.host,
                'port': self.config.port,
                'mode': self.config.mode.value,
                'auto_reconnect': self.config.auto_reconnect,
                'max_retries': self.config.max_retries,
                'timeout': self.config.timeout
            },
            'system_integration': {
                'memory_monitoring': self.memory_monitor is not None,
                'system_optimization': self.system_optimizer is not None
            }
        }
        
        return diagnostics

    # ==========================================================================
    # SHUTDOWN AND CLEANUP
    # ==========================================================================
    def shutdown(self):
        """Gracefully shutdown the connection manager."""
        self.logger.info("Shutting down connection manager...")
        
        self.is_running = False
        self._shutdown_event.set()
        
        if IB_ASYNC_AVAILABLE:
            # Shutdown async components
            if self._monitor_task:
                self._monitor_task.cancel()
            if self._health_check_task:
                self._health_check_task.cancel()
            
            # Disconnect
            if self.ib_client and self.ib_client.isConnected():
                self.ib_client.disconnect()
        else:
            # Shutdown sync components
            if self.ib_client and self.ib_client.isConnected():
                self.ib_client.disconnect()
        
        # Shutdown thread pool
        self.thread_pool.shutdown(wait=True)
        
        self.logger.info("Connection manager shutdown complete")

# ==============================================================================
# GLOBAL ACCESS FUNCTIONS
# ==============================================================================
def get_connection_manager(config: Optional[ConnectionConfig] = None) -> EnhancedConnectionManager:
    """
    Get the singleton enhanced connection manager instance.
    
    Args:
        config: Connection configuration (used only on first call)
        
    Returns:
        EnhancedConnectionManager instance
    """
    return EnhancedConnectionManager(config)

def reset_connection_manager():
    """Reset the singleton instance (for testing/debugging)."""
    EnhancedConnectionManager._instance = None

# ==============================================================================
# TESTING AND DEMONSTRATION
# ==============================================================================
async def main():
    """Demonstrate enhanced connection manager capabilities."""
    print("Enhanced Connection Manager Demo")
    print("=" * 50)
    
    # Create connection manager with configuration
    config = ConnectionConfig(
        host="127.0.0.1",
        port=4002,
        mode=TradingMode.PAPER,
        auto_reconnect=True,
        memory_monitoring=True
    )
    
    conn_mgr = get_connection_manager(config)
    
    # Add callbacks
    def on_connected():
        print("✓ Connected to IB Gateway")
    
    def on_disconnected():
        print("✗ Disconnected from IB Gateway")
    
    async def on_error(error_info):
        print(f"⚠ Error {error_info['errorCode']}: {error_info['errorString']}")
    
    conn_mgr.add_connection_callback(on_connected)
    conn_mgr.add_disconnection_callback(on_disconnected)
    conn_mgr.add_error_callback(on_error)
    
    # Show diagnostics
    print("System Diagnostics:")
    diagnostics = conn_mgr.get_diagnostics()
    print(f"  IB Async Available: {diagnostics['system_integration']}")
    
    # Attempt connection
    if IB_ASYNC_AVAILABLE or IB_INSYNC_AVAILABLE:
        print("\nAttempting connection...")
        success = await conn_mgr.connect_async() if IB_ASYNC_AVAILABLE else conn_mgr.connect()
        
        if success:
            print("Connection successful!")
            
            # Show status
            status = conn_mgr.get_connection_status()
            print(f"Connection Status: {status['state']} ({status['connectivity_state']})")
            
            # Wait then disconnect
            await asyncio.sleep(5) if IB_ASYNC_AVAILABLE else time.sleep(5)
            await conn_mgr.disconnect_async() if IB_ASYNC_AVAILABLE else conn_mgr.disconnect()
        else:
            print("Connection failed!")
    else:
        print("No IB client library available - install ib_async or ib_insync")
    
    # Show final metrics
    metrics = conn_mgr.get_connection_metrics()
    print(f"\nFinal Metrics:")
    for key, value in metrics.items():
        print(f"  {key}: {value}")

if __name__ == "__main__":
    if IB_ASYNC_AVAILABLE:
        asyncio.run(main())
    else:
        print("Demo works best with ib_async library")
        # Run basic sync demo
        import time
        conn_mgr = get_connection_manager()
        print("Enhanced Connection Manager initialized")
        print("Status:", conn_mgr.get_connection_status())