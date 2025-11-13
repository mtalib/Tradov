#!/usr/bin/env python3
"""
IB Gateway Connection Pool for Efficient Connection Management

⚠️ DEPRECATED - MIGRATION TO WEB API IN PROGRESS ⚠️

This module provided connection pooling for IB Gateway/TWS via ib_async.
It is being DEPRECATED as part of the migration to IBKR Web API (OAuth 2.0).

The Web API does not require connection pooling - it uses:
- REST API calls with rate limiting (SpyderB09_ClientPortal_RateLimiter)
- WebSocket connections for streaming (SpyderB09_ClientPortal_WebSocket)
- Session management with OAuth 2.0 (SpyderB09_ClientPortal_Session)

MIGRATION STATUS: This file should NOT be used in new code.
Use ClientPortalAPI modules instead.

Legacy Key Features (IB Gateway/TWS):
- Pre-established persistent connections
- Thread-safe connection borrowing/returning
- Health monitoring and auto-recovery
- Integration with existing Spyder error handling
- Configurable pool size and timeouts
- Graceful shutdown and cleanup

Author: Spyder Trading System
Version: 1.0.0 (DEPRECATED)
"""

import asyncio
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from queue import Queue, Empty
from typing import Optional, List, Dict, Any, Callable
import weakref

# DEPRECATED: ib_async import for IB Gateway/TWS connection pooling
# This module is being phased out in favor of Web API
try:
    from ib_async import IB

    IB_ASYNC_AVAILABLE = True
except ImportError:
    IB_ASYNC_AVAILABLE = False
    IB = None
    print("⚠️ WARNING: IBConnectionPool is DEPRECATED. Use ClientPortalAPI instead.")

# Spyder imports
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU23_MemoryMonitor import SpyderMemoryMonitor


class ConnectionState(Enum):
    """Connection state enumeration"""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    RETIRED = "retired"


@dataclass
class ConnectionInfo:
    """Information about a pooled connection"""

    client_id: int
    ib_client: Any  # IB instance
    state: ConnectionState
    created_at: float
    last_used: float
    use_count: int
    error_count: int
    is_borrowed: bool
    borrower_info: Optional[str] = None


class IBConnectionPool:
    """
    Thread-safe IB Gateway connection pool with health monitoring.

    This pool maintains a set of pre-established IB Gateway connections
    that can be borrowed and returned by different components of the
    Spyder trading system.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 4002,
        min_connections: int = 3,
        max_connections: int = 8,
        connection_timeout: float = 30.0,
        health_check_interval: float = 60.0,
        max_idle_time: float = 300.0,
        max_errors_per_connection: int = 5,
    ):
        """
        Initialize the connection pool.

        Args:
            host: IB Gateway host address
            port: IB Gateway port (4002 for paper, 4001 for live)
            min_connections: Minimum connections to maintain
            max_connections: Maximum connections allowed
            connection_timeout: Timeout for individual connections
            health_check_interval: How often to check connection health
            max_idle_time: Max time a connection can be idle
            max_errors_per_connection: Max errors before retiring connection
        """
        if not IB_ASYNC_AVAILABLE:
            raise ImportError("ib_async is required for IBConnectionPool")

        self.host = host
        self.port = port
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.connection_timeout = connection_timeout
        self.health_check_interval = health_check_interval
        self.max_idle_time = max_idle_time
        self.max_errors_per_connection = max_errors_per_connection

        # Thread safety
        self._lock = threading.RLock()
        self._available_queue = Queue()
        self._shutdown_event = threading.Event()

        # Connection tracking
        self._connections: Dict[int, ConnectionInfo] = {}
        self._next_client_id = 1
        self._is_initialized = False

        # Monitoring and health
        self._health_monitor_thread: Optional[threading.Thread] = None
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="IBPool")

        # Error handling and logging
        self.error_handler = SpyderErrorHandler()
        self.memory_monitor = SpyderMemoryMonitor()
        self.logger = logging.getLogger(f"{__name__}.IBConnectionPool")

        # Statistics
        self._stats = {
            "total_created": 0,
            "total_borrowed": 0,
            "total_returned": 0,
            "total_errors": 0,
            "current_active": 0,
            "current_available": 0,
        }

        # Callbacks
        self._connection_callbacks: List[Callable] = []
        self._error_callbacks: List[Callable] = []

        self.logger.info(
            f"IBConnectionPool initialized: {min_connections}-{max_connections} connections"
        )

    async def initialize(self) -> bool:
        """
        Initialize the connection pool with minimum connections.

        Returns:
            True if successfully initialized
        """
        if self._is_initialized:
            self.logger.warning("Connection pool already initialized")
            return True

        self.logger.info(
            f"Initializing connection pool with {self.min_connections} connections..."
        )

        try:
            # Create initial connections
            success_count = 0
            for _ in range(self.min_connections):
                if await self._create_connection():
                    success_count += 1
                else:
                    self.logger.warning("Failed to create initial connection")

            if success_count == 0:
                self.logger.error("Failed to create any initial connections")
                return False

            # Start health monitoring
            self._start_health_monitor()

            self._is_initialized = True
            self.logger.info(
                f"Connection pool initialized with {success_count}/{self.min_connections} connections"
            )
            return True

        except Exception as e:
            self.error_handler.handle_error(e, "Connection pool initialization failed")
            return False

    async def _create_connection(self) -> bool:
        """
        Create a new connection and add it to the pool.

        Returns:
            True if connection created successfully
        """
        client_id = self._get_next_client_id()

        try:
            self.logger.debug(f"Creating connection with client ID {client_id}")

            # Create IB client
            ib_client = IB()

            # Connect with timeout
            connected = await asyncio.wait_for(
                ib_client.connectAsync(self.host, self.port, clientId=client_id),
                timeout=self.connection_timeout,
            )

            if not ib_client.isConnected():
                self.logger.error(f"Client {client_id} failed to connect")
                return False

            # Create connection info
            conn_info = ConnectionInfo(
                client_id=client_id,
                ib_client=ib_client,
                state=ConnectionState.CONNECTED,
                created_at=time.time(),
                last_used=time.time(),
                use_count=0,
                error_count=0,
                is_borrowed=False,
            )

            # Add to pool
            with self._lock:
                self._connections[client_id] = conn_info
                self._available_queue.put(client_id)
                self._stats["total_created"] += 1
                self._stats["current_available"] += 1

            # Set up error handling
            ib_client.errorEvent += self._on_connection_error

            self.logger.info(f"✅ Connection {client_id} created and added to pool")
            self._notify_connection_callbacks("created", conn_info)

            return True

        except asyncio.TimeoutError:
            self.logger.error(f"Connection timeout for client ID {client_id}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to create connection {client_id}: {e}")
            self.error_handler.handle_error(
                e, f"Connection creation failed for client {client_id}"
            )
            return False

    @contextmanager
    def get_connection(self, borrower_info: str = "unknown", timeout: float = 10.0):
        """
        Context manager to borrow a connection from the pool.

        Args:
            borrower_info: Information about who is borrowing the connection
            timeout: Maximum time to wait for available connection

        Yields:
            IB client instance

        Example:
            with pool.get_connection("DataClient1") as ib:
                # Use ib client
                positions = ib.positions()
        """
        connection = None
        client_id = None

        try:
            # Get available connection
            client_id = self._available_queue.get(timeout=timeout)

            with self._lock:
                if client_id not in self._connections:
                    raise RuntimeError(f"Connection {client_id} not found in pool")

                conn_info = self._connections[client_id]

                if conn_info.is_borrowed:
                    raise RuntimeError(f"Connection {client_id} is already borrowed")

                # Mark as borrowed
                conn_info.is_borrowed = True
                conn_info.borrower_info = borrower_info
                conn_info.last_used = time.time()
                conn_info.use_count += 1

                self._stats["total_borrowed"] += 1
                self._stats["current_available"] -= 1
                self._stats["current_active"] += 1

                connection = conn_info.ib_client

            self.logger.debug(f"Connection {client_id} borrowed by {borrower_info}")
            yield connection

        except Empty:
            self.logger.warning(f"No available connections (timeout={timeout}s)")
            raise TimeoutError("No available connections in pool")

        except Exception as e:
            self.logger.error(f"Error borrowing connection: {e}")
            raise

        finally:
            # Return connection to pool
            if client_id is not None:
                self._return_connection(client_id)

    def _return_connection(self, client_id: int):
        """Return a connection to the pool."""
        try:
            with self._lock:
                if client_id not in self._connections:
                    self.logger.warning(
                        f"Attempting to return unknown connection {client_id}"
                    )
                    return

                conn_info = self._connections[client_id]

                if not conn_info.is_borrowed:
                    self.logger.warning(f"Connection {client_id} was not borrowed")
                    return

                # Check if connection is still healthy
                if not conn_info.ib_client.isConnected():
                    self.logger.warning(
                        f"Connection {client_id} is no longer connected, retiring"
                    )
                    self._retire_connection(client_id)
                    return

                # Mark as available
                conn_info.is_borrowed = False
                conn_info.borrower_info = None

                self._available_queue.put(client_id)
                self._stats["total_returned"] += 1
                self._stats["current_available"] += 1
                self._stats["current_active"] -= 1

            self.logger.debug(f"Connection {client_id} returned to pool")

        except Exception as e:
            self.logger.error(f"Error returning connection {client_id}: {e}")
            self.error_handler.handle_error(
                e, f"Failed to return connection {client_id}"
            )

    def _retire_connection(self, client_id: int):
        """Retire a connection due to errors or health issues."""
        try:
            with self._lock:
                if client_id not in self._connections:
                    return

                conn_info = self._connections[client_id]
                conn_info.state = ConnectionState.RETIRED

                # Disconnect if still connected
                if conn_info.ib_client.isConnected():
                    try:
                        conn_info.ib_client.disconnect()
                    except Exception as e:
                        self.logger.warning(
                            f"Error disconnecting retired connection {client_id}: {e}"
                        )

                # Remove from pool
                del self._connections[client_id]

                # Adjust stats
                if not conn_info.is_borrowed:
                    self._stats["current_available"] -= 1
                else:
                    self._stats["current_active"] -= 1

            self.logger.info(f"Connection {client_id} retired")

            # Try to create replacement connection if below minimum
            if len(self._connections) < self.min_connections:
                asyncio.create_task(self._create_connection())

        except Exception as e:
            self.logger.error(f"Error retiring connection {client_id}: {e}")

    def _on_connection_error(
        self, reqId: int, errorCode: int, errorString: str, contract=None
    ):
        """Handle IB client errors."""
        # Find which connection had the error
        with self._lock:
            for conn_info in self._connections.values():
                if (
                    hasattr(conn_info.ib_client, "reqId")
                    and conn_info.ib_client.reqId == reqId
                ):
                    conn_info.error_count += 1
                    self._stats["total_errors"] += 1

                    self.logger.warning(
                        f"Connection {conn_info.client_id} error: {errorCode} - {errorString}"
                    )

                    # Retire connection if too many errors
                    if conn_info.error_count >= self.max_errors_per_connection:
                        self.logger.error(
                            f"Connection {conn_info.client_id} exceeded error limit, retiring"
                        )
                        self._retire_connection(conn_info.client_id)

                    break

    def _start_health_monitor(self):
        """Start the health monitoring thread."""
        if self._health_monitor_thread is not None:
            return

        self._health_monitor_thread = threading.Thread(
            target=self._health_monitor_loop, name="IBPool-HealthMonitor", daemon=True
        )
        self._health_monitor_thread.start()

    def _health_monitor_loop(self):
        """Health monitoring loop."""
        self.logger.info("Health monitor started")

        while not self._shutdown_event.is_set():
            try:
                self._check_connection_health()

                # Wait for next check
                if self._shutdown_event.wait(self.health_check_interval):
                    break

            except Exception as e:
                self.logger.error(f"Health monitor error: {e}")
                self.error_handler.handle_error(e, "Health monitor error")

        self.logger.info("Health monitor stopped")

    def _check_connection_health(self):
        """Check health of all connections."""
        current_time = time.time()
        connections_to_retire = []

        with self._lock:
            for client_id, conn_info in self._connections.items():
                # Check if connection is still alive
                if not conn_info.ib_client.isConnected():
                    self.logger.warning(f"Connection {client_id} is disconnected")
                    connections_to_retire.append(client_id)
                    continue

                # Check idle time
                idle_time = current_time - conn_info.last_used
                if not conn_info.is_borrowed and idle_time > self.max_idle_time:
                    self.logger.info(
                        f"Connection {client_id} idle for {idle_time:.1f}s, retiring"
                    )
                    connections_to_retire.append(client_id)
                    continue

        # Retire unhealthy connections
        for client_id in connections_to_retire:
            self._retire_connection(client_id)

        # Ensure minimum connections
        current_count = len(self._connections)
        if current_count < self.min_connections:
            needed = self.min_connections - current_count
            self.logger.info(f"Creating {needed} connections to maintain minimum")

            for _ in range(needed):
                asyncio.create_task(self._create_connection())

    def _get_next_client_id(self) -> int:
        """Get the next available client ID."""
        with self._lock:
            while self._next_client_id in self._connections:
                self._next_client_id += 1
                if self._next_client_id > 999:  # IB has limits
                    self._next_client_id = 1

            client_id = self._next_client_id
            self._next_client_id += 1
            return client_id

    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        with self._lock:
            stats = self._stats.copy()
            stats["total_connections"] = len(self._connections)
            stats["connections_by_state"] = {}

            for conn_info in self._connections.values():
                state = conn_info.state.value
                stats["connections_by_state"][state] = (
                    stats["connections_by_state"].get(state, 0) + 1
                )

        return stats

    def add_connection_callback(self, callback: Callable):
        """Add callback for connection events."""
        self._connection_callbacks.append(callback)

    def add_error_callback(self, callback: Callable):
        """Add callback for error events."""
        self._error_callbacks.append(callback)

    def _notify_connection_callbacks(self, event: str, conn_info: ConnectionInfo):
        """Notify connection event callbacks."""
        for callback in self._connection_callbacks:
            try:
                callback(event, conn_info)
            except Exception as e:
                self.logger.error(f"Error in connection callback: {e}")

    async def shutdown(self):
        """Gracefully shutdown the connection pool."""
        self.logger.info("Shutting down connection pool...")

        # Signal shutdown
        self._shutdown_event.set()

        # Wait for health monitor to stop
        if self._health_monitor_thread:
            self._health_monitor_thread.join(timeout=5.0)

        # Disconnect all connections
        with self._lock:
            for client_id, conn_info in self._connections.items():
                try:
                    if conn_info.ib_client.isConnected():
                        conn_info.ib_client.disconnect()
                        self.logger.debug(f"Disconnected connection {client_id}")
                except Exception as e:
                    self.logger.warning(f"Error disconnecting {client_id}: {e}")

            self._connections.clear()

        # Shutdown executor
        self._executor.shutdown(wait=True)

        self.logger.info("Connection pool shutdown complete")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        asyncio.create_task(self.shutdown())


# Example usage and testing
if __name__ == "__main__":

    async def test_connection_pool():
        """Test the connection pool functionality."""
        pool = IBConnectionPool(
            host="127.0.0.1",
            port=4002,  # Paper trading
            min_connections=2,
            max_connections=5,
        )

        # Initialize pool
        if not await pool.initialize():
            print("❌ Failed to initialize connection pool")
            return

        print("✅ Connection pool initialized")

        # Test borrowing connections
        try:
            with pool.get_connection("TestClient1") as ib1:
                print(f"✅ Borrowed connection: {ib1.client.clientId}")
                print(f"Connected: {ib1.isConnected()}")

                # Test concurrent borrowing
                with pool.get_connection("TestClient2") as ib2:
                    print(f"✅ Borrowed second connection: {ib2.client.clientId}")

                    # Get some data
                    positions = ib1.positions()
                    print(f"Positions from client 1: {len(positions)}")

        except Exception as e:
            print(f"❌ Test error: {e}")

        # Print stats
        stats = pool.get_stats()
        print(f"📊 Pool stats: {stats}")

        # Shutdown
        await pool.shutdown()
        print("✅ Pool shutdown complete")

    # Run test
    if IB_ASYNC_AVAILABLE:
        asyncio.run(test_connection_pool())
    else:
        print("❌ ib_async not available for testing")
