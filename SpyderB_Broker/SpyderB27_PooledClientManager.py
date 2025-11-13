#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB27_PooledClientManager.py
Purpose: Manage pooled IB Gateway client connections for distributed trading

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-10-08 Time: 12:00:00

Module Description:
    ⚠️ DEPRECATED - MIGRATION TO WEB API IN PROGRESS ⚠️

    This module provided pooled IB Gateway client connections via ib_async.
    It is being DEPRECATED as part of the migration to IBKR Web API (OAuth 2.0).

    The Web API does not require client connection pools - it uses:
    - Single session management with OAuth 2.0 (SpyderB09_ClientPortal_Session)
    - Rate limiting (SpyderB09_ClientPortal_RateLimiter)
    - WebSocket for streaming data (SpyderB09_ClientPortal_WebSocket)
    - REST API for operations (SpyderB09_ClientPortal_RESTClient)

    MIGRATION STATUS: This file should NOT be used in new code.
    Use ClientPortalAPI modules instead.

    Legacy Key Features (IB Gateway/TWS):
    - Multiple concurrent IB Gateway connections
    - Automatic client ID management
    - Connection health monitoring
    - Load balancing across connections
    - Graceful degradation and failover
    - Resource cleanup and management

Module Constants:
    MIN_CLIENT_ID (int): Minimum client ID (default: 1)
    MAX_CLIENT_ID (int): Maximum client ID (default: 99)
    DEFAULT_POOL_SIZE (int): Default number of pooled clients (default: 3)
    HEALTH_CHECK_INTERVAL (int): Seconds between health checks (default: 30)

Dependencies:
    - ib_async for IB connectivity (DEPRECATED)
    - SpyderB_Broker connection modules
    - SpyderU_Utilities for logging

Change Log:
    2025-11-12: Marked as DEPRECATED - migrating to Web API
    2025-10-08 (v1.0.0):
        - Initial production release
        - Converted from start_pooled_clients.py
        - Added comprehensive error handling
        - Implemented connection pooling patterns
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import asyncio
import time
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import threading
from queue import Queue, Empty

# ==============================================================================
# THIRD-PARTY IMPORTS - DEPRECATED
# ==============================================================================
# DEPRECATED: ib_async import for IB Gateway/TWS connection pooling
# This module is being phased out in favor of Web API
try:
    from ib_async import IB, util
    HAS_IB_ASYNC = True
    print("⚠️ WARNING: PooledClientManager is DEPRECATED. Use ClientPortalAPI instead.")
except ImportError:
    HAS_IB_ASYNC = False
    print("Warning: ib_async not available")

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger, get_logger
    HAS_LOGGER = True
except ImportError:
    HAS_LOGGER = False
    import logging
    get_logger = logging.getLogger

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Client ID Management
MIN_CLIENT_ID = 1
MAX_CLIENT_ID = 99
DEFAULT_POOL_SIZE = 3
MAX_POOL_SIZE = 10

# Connection Settings
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PAPER_PORT = 4002
DEFAULT_LIVE_PORT = 4001
CONNECTION_TIMEOUT = 30
RECONNECT_DELAY = 5

# Health Monitoring
HEALTH_CHECK_INTERVAL = 30
MAX_FAILED_HEALTH_CHECKS = 3

# Resource Limits
MAX_PENDING_REQUESTS = 100
REQUEST_TIMEOUT = 60

# ==============================================================================
# ENUMS
# ==============================================================================
class ClientState(Enum):
    """Client connection state"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    RECONNECTING = "reconnecting"

class PooledClientMode(Enum):
    """Pooled client operating mode"""
    PAPER = "paper"
    LIVE = "live"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class PooledClientConfig:
    """Configuration for pooled client"""
    client_id: int
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PAPER_PORT
    mode: PooledClientMode = PooledClientMode.PAPER
    auto_reconnect: bool = True
    max_reconnect_attempts: int = 3

@dataclass
class ClientMetrics:
    """Metrics for a pooled client"""
    client_id: int
    connection_time: Optional[datetime] = None
    last_request_time: Optional[datetime] = None
    total_requests: int = 0
    failed_requests: int = 0
    health_check_failures: int = 0
    current_load: int = 0
    is_healthy: bool = True

@dataclass
class PooledClient:
    """Pooled IB client wrapper"""
    config: PooledClientConfig
    ib_client: Optional[IB] = None
    state: ClientState = ClientState.DISCONNECTED
    metrics: ClientMetrics = field(default_factory=lambda: None)
    last_error: Optional[str] = None
    reconnect_attempts: int = 0
    
    def __post_init__(self):
        if self.metrics is None:
            self.metrics = ClientMetrics(client_id=self.config.client_id)

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class PooledClientManager:
    """
    Manager for pooled IB Gateway client connections.
    
    Manages multiple IB client connections, providing load balancing,
    failover, and health monitoring capabilities.
    """
    
    def __init__(
        self, 
        pool_size: int = DEFAULT_POOL_SIZE,
        host: str = DEFAULT_HOST,
        port: Optional[int] = None,
        mode: PooledClientMode = PooledClientMode.PAPER,
        start_client_id: int = MIN_CLIENT_ID
    ):
        """
        Initialize the pooled client manager.
        
        Args:
            pool_size: Number of clients in the pool
            host: IB Gateway host address
            port: IB Gateway port (auto-detected if None)
            mode: Trading mode (paper or live)
            start_client_id: Starting client ID for the pool
        """
        # Setup logging
        if HAS_LOGGER:
            self.logger = get_logger(self.__class__.__name__)
        else:
            self.logger = logging.getLogger(self.__class__.__name__)
            
        self.logger.info("Initializing Pooled Client Manager")
        
        # Validate parameters
        if pool_size < 1 or pool_size > MAX_POOL_SIZE:
            raise ValueError(f"Pool size must be between 1 and {MAX_POOL_SIZE}")
            
        if start_client_id + pool_size > MAX_CLIENT_ID:
            raise ValueError(f"Client ID range exceeds maximum ({MAX_CLIENT_ID})")
            
        # Configuration
        self.pool_size = pool_size
        self.host = host
        self.port = port or (DEFAULT_PAPER_PORT if mode == PooledClientMode.PAPER else DEFAULT_LIVE_PORT)
        self.mode = mode
        self.start_client_id = start_client_id
        
        # Client pool
        self.clients: Dict[int, PooledClient] = {}
        self.available_clients: Queue = Queue()
        self.used_client_ids: Set[int] = set()
        
        # State management
        self.is_running = False
        self.health_monitor_thread: Optional[threading.Thread] = None
        
        # Statistics
        self.total_requests = 0
        self.failed_requests = 0
        self.pool_start_time: Optional[datetime] = None
        
        self.logger.info(f"Pool configured: size={pool_size}, mode={mode.value}, port={self.port}")
        
    def initialize_pool(self) -> bool:
        """
        Initialize the client pool.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.logger.info("Initializing client pool")
            
            if not HAS_IB_ASYNC:
                self.logger.error("ib_async not available - cannot initialize pool")
                return False
                
            # Create pooled clients
            for i in range(self.pool_size):
                client_id = self.start_client_id + i
                
                config = PooledClientConfig(
                    client_id=client_id,
                    host=self.host,
                    port=self.port,
                    mode=self.mode
                )
                
                client = PooledClient(config=config)
                self.clients[client_id] = client
                self.used_client_ids.add(client_id)
                
                self.logger.info(f"Created pooled client {client_id}")
                
            self.pool_start_time = datetime.now()
            self.logger.info(f"Client pool initialized with {len(self.clients)} clients")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize pool: {e}")
            return False
            
    async def connect_all(self) -> bool:
        """
        Connect all clients in the pool.
        
        Returns:
            True if all connections successful, False otherwise
        """
        try:
            self.logger.info("Connecting all pool clients")
            
            tasks = []
            for client in self.clients.values():
                tasks.append(self._connect_client(client))
                
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Check results
            successful = sum(1 for r in results if r is True)
            failed = len(results) - successful
            
            self.logger.info(f"Connection results: {successful} successful, {failed} failed")
            
            # Add successfully connected clients to available queue
            for client in self.clients.values():
                if client.state == ClientState.CONNECTED:
                    self.available_clients.put(client.config.client_id)
                    
            return successful > 0
            
        except Exception as e:
            self.logger.error(f"Failed to connect clients: {e}")
            return False
            
    async def _connect_client(self, client: PooledClient) -> bool:
        """
        Connect a single client.
        
        Args:
            client: PooledClient to connect
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.logger.info(f"Connecting client {client.config.client_id}")
            client.state = ClientState.CONNECTING
            
            # Create IB client
            client.ib_client = IB()
            
            # Connect with timeout
            await asyncio.wait_for(
                client.ib_client.connectAsync(
                    self.host,
                    self.port,
                    clientId=client.config.client_id
                ),
                timeout=CONNECTION_TIMEOUT
            )
            
            client.state = ClientState.CONNECTED
            client.metrics.connection_time = datetime.now()
            client.reconnect_attempts = 0
            
            self.logger.info(f"Client {client.config.client_id} connected successfully")
            return True
            
        except asyncio.TimeoutError:
            self.logger.error(f"Connection timeout for client {client.config.client_id}")
            client.state = ClientState.ERROR
            client.last_error = "Connection timeout"
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to connect client {client.config.client_id}: {e}")
            client.state = ClientState.ERROR
            client.last_error = str(e)
            return False
            
    def get_available_client(self, timeout: int = 5) -> Optional[PooledClient]:
        """
        Get an available client from the pool.
        
        Args:
            timeout: Seconds to wait for available client
            
        Returns:
            PooledClient if available, None otherwise
        """
        try:
            client_id = self.available_clients.get(timeout=timeout)
            client = self.clients.get(client_id)
            
            if client and client.state == ClientState.CONNECTED:
                client.metrics.current_load += 1
                client.metrics.last_request_time = datetime.now()
                self.total_requests += 1
                return client
            else:
                # Client not ready, return to pool
                if client:
                    self.available_clients.put(client_id)
                return None
                
        except Empty:
            self.logger.warning("No available clients in pool")
            return None
            
    def release_client(self, client: PooledClient) -> None:
        """
        Release a client back to the pool.
        
        Args:
            client: PooledClient to release
        """
        if client:
            client.metrics.current_load = max(0, client.metrics.current_load - 1)
            client.metrics.total_requests += 1
            self.available_clients.put(client.config.client_id)
            
    def get_pool_statistics(self) -> Dict:
        """
        Get pool statistics.
        
        Returns:
            Dictionary containing pool statistics
        """
        connected = sum(1 for c in self.clients.values() if c.state == ClientState.CONNECTED)
        healthy = sum(1 for c in self.clients.values() if c.metrics.is_healthy)
        total_load = sum(c.metrics.current_load for c in self.clients.values())
        
        return {
            "pool_size": self.pool_size,
            "connected_clients": connected,
            "healthy_clients": healthy,
            "total_load": total_load,
            "total_requests": self.total_requests,
            "failed_requests": self.failed_requests,
            "uptime": (datetime.now() - self.pool_start_time).total_seconds() if self.pool_start_time else 0,
            "mode": self.mode.value,
            "host": self.host,
            "port": self.port
        }
        
    async def disconnect_all(self) -> None:
        """Disconnect all clients in the pool"""
        self.logger.info("Disconnecting all pool clients")
        self.is_running = False
        
        for client in self.clients.values():
            if client.ib_client and client.state == ClientState.CONNECTED:
                try:
                    client.ib_client.disconnect()
                    client.state = ClientState.DISCONNECTED
                except Exception as e:
                    self.logger.error(f"Error disconnecting client {client.config.client_id}: {e}")
            
        self.logger.info("All clients disconnected")

# ==============================================================================
# CONVENIENCE FUNCTIONS
# ==============================================================================
async def create_client_pool(
    pool_size: int = DEFAULT_POOL_SIZE,
    mode: str = "paper",
    host: str = DEFAULT_HOST,
    port: Optional[int] = None
) -> Optional[PooledClientManager]:
    """
    Create and initialize a client pool.
    
    Args:
        pool_size: Number of clients in pool
        mode: Trading mode ("paper" or "live")
        host: Gateway host address
        port: Gateway port (auto-detected if None)
        
    Returns:
        Initialized PooledClientManager or None on failure
    """
    try:
        pool_mode = PooledClientMode.LIVE if mode.lower() == "live" else PooledClientMode.PAPER
        
        manager = PooledClientManager(
            pool_size=pool_size,
            host=host,
            port=port,
            mode=pool_mode
        )
        
        if not manager.initialize_pool():
            return None
            
        if not await manager.connect_all():
            return None
            
        return manager
        
    except Exception as e:
        print(f"Failed to create client pool: {e}")
        return None

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
async def main():
    """Main entry point for testing"""
    print("=" * 70)
    print("SPYDER Pooled Client Manager - Test Mode")
    print("=" * 70)
    
    # Create pool
    print("\nCreating client pool...")
    manager = await create_client_pool(pool_size=3, mode="paper")
    
    if not manager:
        print("❌ Failed to create client pool")
        return
        
    print("✅ Client pool created successfully")
    
    # Display statistics
    stats = manager.get_pool_statistics()
    print("\nPool Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
        
    # Keep running for a bit
    print("\nMonitoring pool (press Ctrl+C to stop)...")
    try:
        await asyncio.sleep(60)
    except KeyboardInterrupt:
        print("\nShutting down...")
        
    # Cleanup
    await manager.disconnect_all()
    print("✅ Pool shutdown complete")

if __name__ == "__main__":
    asyncio.run(main())
