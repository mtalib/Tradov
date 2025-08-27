"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB20_ConnectionManager_v1039.py
Purpose: Enhanced Connection Manager for IB Gateway 10.39
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-26 Time: 10:15:00

Module Description:
    Production-ready connection manager optimized for IB Gateway 10.39 with
    comprehensive timeout handling, exponential backoff, automatic reconnection,
    and resolution for common TimeoutError issues. Implements best practices
    for stable, long-running connections to Interactive Brokers.
"""

import asyncio
import time
import random
import threading
import subprocess
import psutil
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
import logging
from contextlib import contextmanager

# IB API imports
try:
    from ib_async import IB, util, Contract, Order, Trade
    from ib_async import ConnectionStats, AccountValue, Position
    IB_ASYNC_AVAILABLE = True
except ImportError:
    print("⚠️ ib_async not available - install with: pip install ib_async")
    IB_ASYNC_AVAILABLE = False

# ==============================================================================
# CONSTANTS - OPTIMIZED FOR GATEWAY 10.39
# ==============================================================================

# Connection Configuration
CONNECTION_CONFIG = {
    "host": "127.0.0.1",
    "paper_port": 4002,
    "live_port": 4001,
    "timeout": 60,                    # Increased from default 4 seconds
    "initial_sync_timeout": 90,       # For initial data sync
    "request_timeout": 30,            
    "message_receive_timeout": 120,   
    "client_id_range": (1, 32),       # Valid client ID range
    "raise_sync_errors": False        # Better error handling
}

# Retry Configuration
RETRY_CONFIG = {
    "max_attempts": 5,
    "initial_delay": 2.0,
    "max_delay": 60.0,
    "exponential_base": 2.0,
    "jitter_range": (0.0, 0.3)       # Random jitter percentage
}

# Health Check Configuration
HEALTH_CHECK_CONFIG = {
    "interval": 30,                   # Seconds between health checks
    "timeout": 10,                    # Health check timeout
    "failure_threshold": 3,           # Failures before reconnect
    "success_threshold": 2            # Successes to mark healthy
}

# Rate Limiting
RATE_LIMITS = {
    "messages_per_second": 50,        # IB API rate limit
    "historical_data_per_10min": 60,  # Historical data limit
    "scanner_per_30s": 10             # Scanner subscription limit
}

# ==============================================================================
# ENUMS AND DATA CLASSES
# ==============================================================================

class ConnectionState(Enum):
    """Connection state enumeration"""
    DISCONNECTED = auto()
    CONNECTING = auto()
    AUTHENTICATING = auto()
    INITIALIZING = auto()
    SYNCING = auto()
    CONNECTED = auto()
    RECONNECTING = auto()
    ERROR = auto()
    SHUTDOWN = auto()

@dataclass
class ConnectionStats:
    """Connection statistics tracking"""
    connect_time: Optional[datetime] = None
    disconnect_time: Optional[datetime] = None
    total_connections: int = 0
    failed_connections: int = 0
    total_messages: int = 0
    errors_count: int = 0
    last_error: Optional[str] = None
    uptime_seconds: float = 0.0
    current_latency_ms: float = 0.0
    average_latency_ms: float = 0.0
    
    def get_uptime_str(self) -> str:
        """Get formatted uptime string"""
        if not self.connect_time:
            return "Not connected"
        
        uptime = datetime.now() - self.connect_time
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{uptime.days}d {hours}h {minutes}m {seconds}s"

@dataclass
class ReconnectStrategy:
    """Reconnection strategy configuration"""
    attempt: int = 0
    next_delay: float = RETRY_CONFIG["initial_delay"]
    total_elapsed: float = 0.0
    
    def calculate_next_delay(self) -> float:
        """Calculate next retry delay with exponential backoff and jitter"""
        base_delay = min(
            self.next_delay * RETRY_CONFIG["exponential_base"],
            RETRY_CONFIG["max_delay"]
        )
        
        # Add random jitter
        jitter_min, jitter_max = RETRY_CONFIG["jitter_range"]
        jitter = random.uniform(jitter_min, jitter_max)
        
        self.next_delay = base_delay * (1 + jitter)
        self.total_elapsed += self.next_delay
        self.attempt += 1
        
        return self.next_delay

# ==============================================================================
# CONNECTION MANAGER CLASS
# ==============================================================================

class IBConnectionManager:
    """
    Enhanced connection manager for IB Gateway 10.39.
    
    This manager provides:
    - Robust connection establishment with proper timeouts
    - Automatic reconnection with exponential backoff
    - Connection health monitoring and recovery
    - Client ID management to avoid conflicts
    - Comprehensive error handling and logging
    - Thread-safe operations for concurrent access
    
    Attributes:
        ib: IB connection instance
        state: Current connection state
        stats: Connection statistics
        config: Connection configuration
        callbacks: Event callback handlers
        health_checker: Health monitoring thread
    """
    
    def __init__(self, mode: str = "paper", client_id: Optional[int] = None):
        """
        Initialize connection manager.
        
        Args:
            mode: Trading mode ("paper" or "live")
            client_id: Specific client ID (auto-assigned if None)
        """
        self.logger = self._setup_logger()
        
        # Connection setup
        self.mode = mode
        self.port = CONNECTION_CONFIG[f"{mode}_port"]
        self.client_id = client_id or self._get_next_client_id()
        
        # State management
        self.state = ConnectionState.DISCONNECTED
        self.ib: Optional[IB] = None
        self.stats = ConnectionStats()
        self.reconnect_strategy = ReconnectStrategy()
        
        # Threading
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._connected_event = threading.Event()
        self._health_thread: Optional[threading.Thread] = None
        
        # Callbacks
        self.callbacks: Dict[str, List[Callable]] = {
            "connected": [],
            "disconnected": [],
            "error": [],
            "state_changed": []
        }
        
        # Health monitoring
        self.health_failures = 0
        self.health_successes = 0
        
        self.logger.info(f"Connection Manager initialized for {mode} mode on port {self.port}")
    
    def _setup_logger(self) -> logging.Logger:
        """Setup module logger"""
        logger = logging.getLogger(f"{__name__}.{id(self)}")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def _get_next_client_id(self) -> int:
        """Get next available client ID to avoid conflicts"""
        min_id, max_id = CONNECTION_CONFIG["client_id_range"]
        
        # Try to find unused client ID
        for client_id in range(min_id, max_id):
            if not self._is_client_id_in_use(client_id):
                return client_id
        
        # Fallback with random ID
        return random.randint(min_id, max_id)
    
    def _is_client_id_in_use(self, client_id: int) -> bool:
        """Check if client ID is already in use"""
        try:
            # Quick connection test
            test_ib = IB()
            test_ib.connect(
                CONNECTION_CONFIG["host"],
                self.port,
                clientId=client_id,
                timeout=2
            )
            test_ib.disconnect()
            return False
        except:
            return True
    
    # ==========================================================================
    # CONNECTION ESTABLISHMENT
    # ==========================================================================
    
    async def connect_async(self) -> bool:
        """
        Establish connection to IB Gateway (async version).
        
        Returns:
            bool: True if connection successful
        """
        with self._lock:
            if self.state == ConnectionState.CONNECTED:
                self.logger.info("Already connected")
                return True
            
            self._set_state(ConnectionState.CONNECTING)
        
        try:
            # Create new IB instance
            self.ib = IB()
            
            # Configure IB instance
            self.ib.RaiseRequestErrors = CONNECTION_CONFIG["raise_sync_errors"]
            
            # Setup event handlers
            self._setup_ib_handlers()
            
            # Connect with extended timeout
            self.logger.info(f"Connecting to IB Gateway on port {self.port} with client ID {self.client_id}")
            
            await asyncio.wait_for(
                self.ib.connectAsync(
                    CONNECTION_CONFIG["host"],
                    self.port,
                    clientId=self.client_id,
                    timeout=CONNECTION_CONFIG["timeout"]
                ),
                timeout=CONNECTION_CONFIG["timeout"] + 10
            )
            
            # Wait for initial authentication
            self._set_state(ConnectionState.AUTHENTICATING)
            await asyncio.sleep(2)
            
            # Initialize connection
            self._set_state(ConnectionState.INITIALIZING)
            await self._initialize_connection()
            
            # Sync initial data with extended timeout
            self._set_state(ConnectionState.SYNCING)
            await self._sync_initial_data()
            
            # Connection successful
            self._set_state(ConnectionState.CONNECTED)
            self._connected_event.set()
            
            # Update statistics
            self.stats.connect_time = datetime.now()
            self.stats.total_connections += 1
            
            # Start health monitoring
            self._start_health_monitor()
            
            # Trigger callbacks
            self._trigger_callbacks("connected", {"client_id": self.client_id})
            
            self.logger.info("✅ Successfully connected to IB Gateway")
            return True
            
        except asyncio.TimeoutError:
            self.logger.error(f"Connection timeout after {CONNECTION_CONFIG['timeout']} seconds")
            await self._handle_connection_failure("Timeout")
            return False
            
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            await self._handle_connection_failure(str(e))
            return False
    
    def connect(self) -> bool:
        """
        Establish connection to IB Gateway (sync version).
        
        Returns:
            bool: True if connection successful
        """
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self.connect_async())
            return result
        except Exception as e:
            self.logger.error(f"Sync connect failed: {e}")
            return False
    
    async def _initialize_connection(self):
        """Initialize connection settings and subscriptions"""
        try:
            # Set market data type
            self.ib.reqMarketDataType(4)  # Delayed data for paper trading
            
            # Request account updates
            if self.mode == "paper":
                self.ib.reqAccountUpdates(subscribe=True)
            
            # Small delay for initialization
            await asyncio.sleep(1)
            
        except Exception as e:
            self.logger.error(f"Initialization error: {e}")
            raise
    
    async def _sync_initial_data(self):
        """Sync initial data with proper timeout handling"""
        try:
            # Use longer timeout for initial sync
            timeout = CONNECTION_CONFIG["initial_sync_timeout"]
            
            # Request positions with timeout
            try:
                positions = await asyncio.wait_for(
                    self.ib.reqPositionsAsync(),
                    timeout=timeout/3
                )
                self.logger.info(f"Synced {len(positions)} positions")
            except asyncio.TimeoutError:
                self.logger.warning("Position sync timeout - continuing")
            
            # Request open orders with timeout
            try:
                orders = await asyncio.wait_for(
                    self.ib.reqAllOpenOrdersAsync(),
                    timeout=timeout/3
                )
                self.logger.info(f"Synced {len(orders)} open orders")
            except asyncio.TimeoutError:
                self.logger.warning("Order sync timeout - continuing")
            
            # Request executions with timeout (common timeout source)
            try:
                # Use reqExecutions instead of reqExecutionsAsync for better stability
                exec_filter = None  # Get all executions
                executions = await asyncio.wait_for(
                    self.ib.reqExecutionsAsync(exec_filter),
                    timeout=timeout/3
                )
                self.logger.info(f"Synced {len(executions)} executions")
            except asyncio.TimeoutError:
                self.logger.warning("Execution sync timeout - this is normal for accounts with no recent executions")
            except Exception as e:
                self.logger.warning(f"Execution sync error (non-critical): {e}")
            
        except Exception as e:
            self.logger.error(f"Initial data sync error: {e}")
            # Don't fail connection for sync errors
            self.logger.warning("Continuing despite sync errors")
    
    # ==========================================================================
    # CONNECTION MANAGEMENT
    # ==========================================================================
    
    async def disconnect_async(self):
        """Disconnect from IB Gateway (async)"""
        try:
            self.logger.info("Disconnecting from IB Gateway...")
            
            # Stop health monitor
            self._stop_event.set()
            
            # Update state
            self._set_state(ConnectionState.DISCONNECTED)
            
            # Disconnect IB
            if self.ib and self.ib.isConnected():
                self.ib.disconnect()
            
            # Update statistics
            self.stats.disconnect_time = datetime.now()
            if self.stats.connect_time:
                uptime = (self.stats.disconnect_time - self.stats.connect_time).total_seconds()
                self.stats.uptime_seconds += uptime
            
            # Clear events
            self._connected_event.clear()
            
            # Trigger callbacks
            self._trigger_callbacks("disconnected", {})
            
            self.logger.info("Disconnected from IB Gateway")
            
        except Exception as e:
            self.logger.error(f"Disconnect error: {e}")
    
    def disconnect(self):
        """Disconnect from IB Gateway (sync)"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.disconnect_async())
        except Exception as e:
            self.logger.error(f"Sync disconnect error: {e}")
    
    async def reconnect_async(self) -> bool:
        """
        Reconnect with exponential backoff.
        
        Returns:
            bool: True if reconnection successful
        """
        self._set_state(ConnectionState.RECONNECTING)
        self.reconnect_strategy = ReconnectStrategy()
        
        while self.reconnect_strategy.attempt < RETRY_CONFIG["max_attempts"]:
            delay = self.reconnect_strategy.calculate_next_delay()
            
            self.logger.info(
                f"Reconnection attempt {self.reconnect_strategy.attempt}/{RETRY_CONFIG['max_attempts']} "
                f"in {delay:.1f} seconds"
            )
            
            # Wait with backoff
            await asyncio.sleep(delay)
            
            # Try to reconnect
            if await self.connect_async():
                self.logger.info("✅ Reconnection successful")
                self.reconnect_strategy = ReconnectStrategy()
                return True
            
            # Check if we should stop
            if self._stop_event.is_set():
                self.logger.info("Reconnection cancelled")
                return False
        
        self.logger.error(f"Failed to reconnect after {RETRY_CONFIG['max_attempts']} attempts")
        self._set_state(ConnectionState.ERROR)
        return False
    
    def reconnect(self) -> bool:
        """Reconnect with exponential backoff (sync)"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(self.reconnect_async())
        except Exception as e:
            self.logger.error(f"Sync reconnect error: {e}")
            return False
    
    # ==========================================================================
    # HEALTH MONITORING
    # ==========================================================================
    
    def _start_health_monitor(self):
        """Start health monitoring thread"""
        if self._health_thread and self._health_thread.is_alive():
            return
        
        self._stop_event.clear()
        self._health_thread = threading.Thread(target=self._health_monitor_loop)
        self._health_thread.daemon = True
        self._health_thread.start()
        
        self.logger.info("Health monitor started")
    
    def _health_monitor_loop(self):
        """Health monitoring loop"""
        while not self._stop_event.is_set():
            try:
                # Wait for next check interval
                if self._stop_event.wait(HEALTH_CHECK_CONFIG["interval"]):
                    break
                
                # Perform health check
                if self.state == ConnectionState.CONNECTED:
                    is_healthy = self._perform_health_check()
                    
                    if is_healthy:
                        self.health_failures = 0
                        self.health_successes += 1
                    else:
                        self.health_failures += 1
                        self.health_successes = 0
                        
                        # Check failure threshold
                        if self.health_failures >= HEALTH_CHECK_CONFIG["failure_threshold"]:
                            self.logger.warning(
                                f"Health check failed {self.health_failures} times - reconnecting"
                            )
                            self.reconnect()
                
            except Exception as e:
                self.logger.error(f"Health monitor error: {e}")
    
    def _perform_health_check(self) -> bool:
        """
        Perform connection health check.
        
        Returns:
            bool: True if connection is healthy
        """
        try:
            if not self.ib or not self.ib.isConnected():
                return False
            
            # Measure latency
            start_time = time.time()
            
            # Simple health check - request current time
            server_time = self.ib.reqCurrentTime()
            
            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000
            self.stats.current_latency_ms = latency_ms
            
            # Update average
            if self.stats.average_latency_ms == 0:
                self.stats.average_latency_ms = latency_ms
            else:
                self.stats.average_latency_ms = (
                    0.9 * self.stats.average_latency_ms + 0.1 * latency_ms
                )
            
            # Check if latency is acceptable
            if latency_ms > 5000:  # 5 seconds
                self.logger.warning(f"High latency detected: {latency_ms:.1f}ms")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False
    
    # ==========================================================================
    # EVENT HANDLERS
    # ==========================================================================
    
    def _setup_ib_handlers(self):
        """Setup IB event handlers"""
        if not self.ib:
            return
        
        # Connection events
        self.ib.connectedEvent += self._on_connected
        self.ib.disconnectedEvent += self._on_disconnected
        
        # Error events
        self.ib.errorEvent += self._on_error
        
        # Data events
        self.ib.updateEvent += self._on_update
    
    def _on_connected(self):
        """Handle connection event"""
        self.logger.info("IB connection established")
    
    def _on_disconnected(self):
        """Handle disconnection event"""
        self.logger.warning("IB connection lost")
        
        if self.state == ConnectionState.CONNECTED:
            # Unexpected disconnection - try to reconnect
            asyncio.create_task(self.reconnect_async())
    
    def _on_error(self, reqId, errorCode, errorString, contract):
        """Handle error events"""
        self.stats.errors_count += 1
        self.stats.last_error = f"Code {errorCode}: {errorString}"
        
        # Log based on severity
        if errorCode in [1100, 1101, 1102]:  # Connection messages
            self.logger.info(f"Connection message {errorCode}: {errorString}")
        elif errorCode < 1000:  # System messages
            self.logger.info(f"System message {errorCode}: {errorString}")
        elif errorCode < 2000:  # Warning
            self.logger.warning(f"Warning {errorCode}: {errorString}")
        else:  # Error
            self.logger.error(f"Error {errorCode}: {errorString}")
            
        # Trigger error callback
        self._trigger_callbacks("error", {
            "reqId": reqId,
            "errorCode": errorCode,
            "errorString": errorString,
            "contract": contract
        })
    
    def _on_update(self):
        """Handle update events"""
        self.stats.total_messages += 1
    
    # ==========================================================================
    # STATE MANAGEMENT
    # ==========================================================================
    
    def _set_state(self, new_state: ConnectionState):
        """Update connection state"""
        with self._lock:
            old_state = self.state
            self.state = new_state
            
            self.logger.info(f"State transition: {old_state.name} → {new_state.name}")
            
            # Trigger state change callbacks
            self._trigger_callbacks("state_changed", {
                "old_state": old_state,
                "new_state": new_state
            })
    
    async def _handle_connection_failure(self, error: str):
        """Handle connection failure"""
        self.stats.failed_connections += 1
        self.stats.last_error = error
        
        self._set_state(ConnectionState.ERROR)
        
        # Cleanup
        if self.ib:
            try:
                self.ib.disconnect()
            except:
                pass
            self.ib = None
        
        # Trigger error callback
        self._trigger_callbacks("error", {"error": error})
    
    # ==========================================================================
    # CALLBACK MANAGEMENT
    # ==========================================================================
    
    def register_callback(self, event: str, callback: Callable):
        """Register event callback"""
        if event in self.callbacks:
            self.callbacks[event].append(callback)
            self.logger.debug(f"Registered callback for {event}")
    
    def _trigger_callbacks(self, event: str, data: Dict[str, Any]):
        """Trigger callbacks for event"""
        if event in self.callbacks:
            for callback in self.callbacks[event]:
                try:
                    callback(data)
                except Exception as e:
                    self.logger.error(f"Callback error for {event}: {e}")
    
    # ==========================================================================
    # PUBLIC API
    # ==========================================================================
    
    def is_connected(self) -> bool:
        """Check if connected"""
        return self.state == ConnectionState.CONNECTED and self.ib and self.ib.isConnected()
    
    def wait_for_connection(self, timeout: float = 30) -> bool:
        """
        Wait for connection to be established.
        
        Args:
            timeout: Maximum time to wait
            
        Returns:
            bool: True if connected within timeout
        """
        return self._connected_event.wait(timeout)
    
    def get_ib(self) -> Optional[IB]:
        """Get IB instance if connected"""
        if self.is_connected():
            return self.ib
        return None
    
    def get_stats(self) -> ConnectionStats:
        """Get connection statistics"""
        return self.stats
    
    def get_state(self) -> ConnectionState:
        """Get current connection state"""
        return self.state
    
    @contextmanager
    def ensure_connected(self):
        """Context manager to ensure connection"""
        if not self.is_connected():
            self.connect()
        
        try:
            yield self.ib
        finally:
            pass  # Keep connection open

# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================

def create_connection_manager(
    mode: str = "paper",
    client_id: Optional[int] = None,
    auto_connect: bool = False
) -> IBConnectionManager:
    """
    Create and optionally connect a connection manager.
    
    Args:
        mode: Trading mode ("paper" or "live")
        client_id: Specific client ID (auto-assigned if None)
        auto_connect: Automatically establish connection
        
    Returns:
        Configured connection manager
    """
    manager = IBConnectionManager(mode, client_id)
    
    if auto_connect:
        if manager.connect():
            print("✅ Connection established")
        else:
            print("❌ Connection failed")
    
    return manager

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    import sys
    
    print("🚀 Testing IB Gateway 10.39 Connection Manager")
    print("=" * 60)
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Create connection manager
    manager = create_connection_manager(mode="paper")
    
    # Register callbacks
    manager.register_callback("connected", lambda d: print(f"✅ CONNECTED: {d}"))
    manager.register_callback("disconnected", lambda d: print(f"🔌 DISCONNECTED: {d}"))
    manager.register_callback("error", lambda d: print(f"❌ ERROR: {d}"))
    manager.register_callback("state_changed", 
                            lambda d: print(f"🔄 STATE: {d['old_state'].name} → {d['new_state'].name}"))
    
    try:
        # Connect to Gateway
        print("\n📡 Connecting to IB Gateway...")
        if manager.connect():
            print("✅ Connection successful!")
            
            # Show statistics
            stats = manager.get_stats()
            print(f"\n📊 Connection Statistics:")
            print(f"   Uptime: {stats.get_uptime_str()}")
            print(f"   Latency: {stats.current_latency_ms:.1f}ms")
            print(f"   Messages: {stats.total_messages}")
            print(f"   Errors: {stats.errors_count}")
            
            # Keep running for testing
            print("\n⏳ Connection manager running... Press Ctrl+C to stop")
            while True:
                time.sleep(1)
                
        else:
            print("❌ Connection failed!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down...")
        manager.disconnect()
        print("✅ Shutdown complete")
