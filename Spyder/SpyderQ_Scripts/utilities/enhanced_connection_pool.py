#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderX_Unknown
Module: enhanced_connection_pool.py
Purpose: Enhanced Connection Pool using EnhancedConnectionManager

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    Enhanced Connection Pool using EnhancedConnectionManager

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import logging
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from queue import Queue, Empty
from typing import Dict, List, Optional, Any

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import weakref

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderB_Broker.SpyderB29_EnhancedConnectionManager import (

    get_connection_manager,
    ConnectionConfig,
    TradingMode,
)
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler


@dataclass
class PooledConnection:
    """Information about a pooled connection"""

    client_id: int
    connection_manager: Any  # EnhancedConnectionManager instance
    created_at: float
    last_used: float
    use_count: int
    is_borrowed: bool
    borrower_info: Optional[str] = None


class EnhancedConnectionPool:
    """
    Connection pool using EnhancedConnectionManager.

    This pool creates and manages multiple EnhancedConnectionManager instances,
    using the same proven connection method that works for the dashboard.
    """

    def __init__(
        self,
        pool_size: int = 6,
        host: str = "127.0.0.1",
        port: int = 4002,
        trading_mode: TradingMode = TradingMode.PAPER,
    ):
        """
        Initialize the enhanced connection pool.

        Args:
            pool_size: Number of connections to maintain
            host: IB Gateway host
            port: IB Gateway port
            trading_mode: Trading mode (PAPER or LIVE)
        """
        self.pool_size = pool_size
        self.host = host
        self.port = port
        self.trading_mode = trading_mode

        # Thread safety
        self._lock = threading.RLock()
        self._available = Queue()
        self._connections: Dict[int, PooledConnection] = {}
        self._in_use: set = set()

        # Error handling
        self.error_handler = SpyderErrorHandler()
        self.logger = logging.getLogger("EnhancedConnectionPool")

        # Statistics
        self.stats = {
            "total_created": 0,
            "total_borrowed": 0,
            "total_returned": 0,
            "total_failed": 0,
            "current_available": 0,
            "current_in_use": 0,
        }

        self.logger.info(f"Enhanced connection pool initialized (size={pool_size})")

    def initialize(self) -> int:
        """
        Initialize the pool by creating connections.

        Returns:
            Number of successful connections created
        """
        self.logger.info(f"🚀 Initializing {self.pool_size} enhanced connections...")

        success_count = 0

        for client_id in range(1, self.pool_size + 1):
            if self._create_connection(client_id):
                success_count += 1
            else:
                self.logger.warning(f"Failed to create connection {client_id}")

        self.logger.info(
            f"📊 Pool initialized: {success_count}/{self.pool_size} connections"
        )
        return success_count

    def _create_connection(self, client_id: int) -> bool:
        """
        Create a single connection using EnhancedConnectionManager.

        Args:
            client_id: Client ID for this connection

        Returns:
            True if connection created successfully
        """
        try:
            self.logger.debug(f"Creating enhanced connection {client_id}...")

            # Create connection config (same as dashboard)
            config = ConnectionConfig(
                port=self.port,
                mode=self.trading_mode,
                client_id=client_id,
            )

            # Get connection manager instance (factory pattern)
            conn_mgr = get_connection_manager(config=config, client_id=client_id)

            # Attempt to connect using the proven method
            if conn_mgr.connect():
                # Create pooled connection info
                pooled_conn = PooledConnection(
                    client_id=client_id,
                    connection_manager=conn_mgr,
                    created_at=time.time(),
                    last_used=time.time(),
                    use_count=0,
                    is_borrowed=False,
                )

                # Add to pool
                with self._lock:
                    self._connections[client_id] = pooled_conn
                    self._available.put(client_id)
                    self.stats["total_created"] += 1
                    self.stats["current_available"] += 1

                self.logger.info(
                    f"✅ Enhanced connection {client_id} created successfully"
                )
                return True
            else:
                self.logger.error(
                    f"❌ Enhanced connection {client_id} failed to connect"
                )
                return False

        except Exception as e:
            self.logger.error(f"❌ Exception creating connection {client_id}: {e}")
            self.error_handler.handle_error(
                e, f"Connection creation failed for client {client_id}"
            )
            self.stats["total_failed"] += 1
            return False

    @contextmanager
    def get_connection(self, borrower_info: str = "unknown", timeout: float = 5.0):
        """
        Borrow a connection from the pool.

        Args:
            borrower_info: Information about who is borrowing
            timeout: Maximum time to wait for available connection

        Yields:
            IB client instance from the connection manager

        Raises:
            TimeoutError: No connection available
            RuntimeError: Connection issues
        """
        client_id = None

        try:
            # Get available connection
            client_id = self._available.get(timeout=timeout)

            with self._lock:
                if client_id not in self._connections:
                    raise RuntimeError(f"Connection {client_id} not found in pool")

                pooled_conn = self._connections[client_id]

                if pooled_conn.is_borrowed:
                    raise RuntimeError(f"Connection {client_id} is already borrowed")

                # Check if connection is still healthy
                if not pooled_conn.connection_manager.is_connected():
                    self.logger.warning(
                        f"Connection {client_id} is not healthy, attempting reconnect..."
                    )
                    if not pooled_conn.connection_manager.connect():
                        raise RuntimeError(
                            f"Connection {client_id} failed to reconnect"
                        )

                # Mark as borrowed
                pooled_conn.is_borrowed = True
                pooled_conn.borrower_info = borrower_info
                pooled_conn.last_used = time.time()
                pooled_conn.use_count += 1

                self._in_use.add(client_id)
                self.stats["total_borrowed"] += 1
                self.stats["current_available"] -= 1
                self.stats["current_in_use"] += 1

                # Get the actual IB client from the connection manager
                ib_client = pooled_conn.connection_manager.ib_client

            self.logger.debug(f"📤 Connection {client_id} borrowed by {borrower_info}")
            yield ib_client

        except Empty:
            raise TimeoutError(f"No available connections in pool (timeout={timeout}s)")
        except Exception as e:
            self.logger.error(f"❌ Error borrowing connection: {e}")
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
                    self.logger.warning(f"Returning unknown connection {client_id}")
                    return

                pooled_conn = self._connections[client_id]

                if not pooled_conn.is_borrowed:
                    self.logger.warning(f"Connection {client_id} was not borrowed")
                    return

                # Mark as available
                pooled_conn.is_borrowed = False
                pooled_conn.borrower_info = None

                if client_id in self._in_use:
                    self._in_use.remove(client_id)

                self._available.put(client_id)
                self.stats["total_returned"] += 1
                self.stats["current_available"] += 1
                self.stats["current_in_use"] -= 1

            self.logger.debug(f"📥 Connection {client_id} returned to pool")

        except Exception as e:
            self.logger.error(f"❌ Error returning connection {client_id}: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        with self._lock:
            stats = self.stats.copy()
            stats.update(
                {
                    "pool_size": self.pool_size,
                    "total_connections": len(self._connections),
                    "available_count": self._available.qsize(),
                    "in_use_count": len(self._in_use),
                }
            )

            # Connection health info
            healthy_connections = 0
            for pooled_conn in self._connections.values():
                if pooled_conn.connection_manager.is_connected():
                    healthy_connections += 1

            stats["healthy_connections"] = healthy_connections
            stats["unhealthy_connections"] = (
                len(self._connections) - healthy_connections
            )

        return stats

    def health_check(self) -> Dict[str, Any]:
        """Perform health check on all connections."""
        health_info = {
            "timestamp": time.time(),
            "total_connections": len(self._connections),
            "healthy": [],
            "unhealthy": [],
            "reconnected": [],
            "failed": [],
        }

        with self._lock:
            for client_id, pooled_conn in self._connections.items():
                if pooled_conn.connection_manager.is_connected():
                    health_info["healthy"].append(client_id)
                else:
                    health_info["unhealthy"].append(client_id)

                    # Try to reconnect unhealthy connections that aren't in use
                    if not pooled_conn.is_borrowed:
                        try:
                            if pooled_conn.connection_manager.connect():
                                health_info["reconnected"].append(client_id)
                                self.logger.info(
                                    f"✅ Reconnected unhealthy connection {client_id}"
                                )
                            else:
                                health_info["failed"].append(client_id)
                                self.logger.warning(
                                    f"⚠️ Failed to reconnect connection {client_id}"
                                )
                        except Exception as e:
                            health_info["failed"].append(client_id)
                            self.logger.error(f"❌ Error reconnecting {client_id}: {e}")

        return health_info

    def shutdown(self):
        """Shutdown the connection pool."""
        self.logger.info("🛑 Shutting down enhanced connection pool...")

        with self._lock:
            for client_id, pooled_conn in self._connections.items():
                try:
                    if pooled_conn.connection_manager.is_connected():
                        pooled_conn.connection_manager.disconnect()
                        self.logger.debug(f"Disconnected connection {client_id}")
                except Exception as e:
                    self.logger.warning(f"Error disconnecting {client_id}: {e}")

            self._connections.clear()

            # Clear queues
            while not self._available.empty():
                try:
                    self._available.get_nowait()
                except Empty:
                    break

            self._in_use.clear()

        self.logger.info("✅ Enhanced connection pool shutdown complete")


# Test and example usage
async def test_enhanced_pool():
    """Test the enhanced connection pool."""
    print("🧪 Testing Enhanced Connection Pool")
    print("=" * 50)

    pool = EnhancedConnectionPool(pool_size=3)

    try:
        # Initialize pool
        success_count = pool.initialize()

        if success_count == 0:
            print("❌ No connections created")
            return False

        print(f"✅ Pool ready with {success_count} connections")

        # Test borrowing connections
        print("\n🔄 Testing connection borrowing...")

        try:
            with pool.get_connection("TestClient1") as ib:
                print(f"✅ Borrowed connection: Client ID {ib.client.clientId}")
                print(f"   Connected: {ib.isConnected()}")

                # Try to get positions
                try:
                    positions = ib.positions()
                    print(f"   📊 Retrieved {len(positions)} positions")
                except Exception as e:
                    print(f"   ⚠️ Data request failed: {e}")

        except Exception as e:
            print(f"❌ Connection test failed: {e}")
            return False

        # Test concurrent connections
        print("\n🔄 Testing concurrent connections...")

        async def test_concurrent_connection(test_id):
            try:
                with pool.get_connection(f"ConcurrentTest{test_id}") as ib:
                    print(f"   ✅ Test {test_id}: Got connection {ib.client.clientId}")
                    await asyncio.sleep(0.5)  # Simulate work
                    return True
            except Exception as e:
                print(f"   ❌ Test {test_id}: {e}")
                return False

        # Run concurrent tests
        tasks = [test_concurrent_connection(i) for i in range(1, 4)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        success_count = sum(1 for r in results if r is True)
        print(f"   📊 Concurrent test: {success_count}/3 successful")

        # Health check
        health = pool.health_check()
        print(
            f"\n📊 Health check: {len(health['healthy'])} healthy, {len(health['unhealthy'])} unhealthy"
        )

        # Final stats
        stats = pool.get_stats()
        print(f"\n📊 Final Statistics:")
        for key, value in stats.items():
            print(f"   {key}: {value}")

        return success_count > 0

    finally:
        pool.shutdown()


if __name__ == "__main__":
    # Run test
    import asyncio

    logging.basicConfig(level=logging.INFO)
    success = asyncio.run(test_enhanced_pool())

    if success:
        print("\n🎉 Enhanced connection pool test successful!")
        print("💡 This pool uses the same method that works for the dashboard")
    else:
        print("\n⚠️ Test failed - check IB Gateway status")
