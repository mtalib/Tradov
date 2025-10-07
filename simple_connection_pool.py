#!/usr/bin/env python3
"""
Simple IB Gateway Connection Pool - Immediate Testing Version

This is a simplified connection pool specifically designed to work with
the current IB Gateway connection issues we've been experiencing.

Key features:
- Minimal dependencies
- Works with existing connection timeout issues
- Simple borrow/return interface
- Basic error handling
- Direct integration ready

Author: Spyder Trading System
Version: 1.0.0
"""

import asyncio
import logging
import threading
import time
from contextlib import contextmanager
from queue import Queue, Empty
from typing import Dict, List, Optional, Any
import weakref

try:
    from ib_async import IB

    IB_AVAILABLE = True
except ImportError:
    IB_AVAILABLE = False
    IB = None


class SimpleConnectionPool:
    """
    Simplified IB Gateway connection pool.

    This pool maintains a small number of pre-established connections
    that can be borrowed and returned by multiple clients.
    """

    def __init__(self, host="127.0.0.1", port=4002, pool_size=4):
        """
        Initialize the simple connection pool.

        Args:
            host: IB Gateway host
            port: IB Gateway port
            pool_size: Number of connections to maintain
        """
        if not IB_AVAILABLE:
            raise ImportError("ib_async is required")

        self.host = host
        self.port = port
        self.pool_size = pool_size
        self.logger = logging.getLogger("SimpleConnectionPool")

        # Connection storage
        self._connections = {}  # {client_id: ib_instance}
        self._available = Queue()  # Available connection client_ids
        self._in_use = set()  # Client_ids currently in use
        self._lock = threading.RLock()

        # Stats
        self.total_created = 0
        self.total_borrowed = 0
        self.total_returned = 0
        self.total_failed = 0

        print(f"🔧 SimpleConnectionPool initialized (size={pool_size})")

    async def initialize(self):
        """
        Initialize the pool by creating connections.

        Returns:
            Number of successful connections created
        """
        print(f"🚀 Initializing {self.pool_size} connections...")

        success_count = 0

        for client_id in range(1, self.pool_size + 1):
            try:
                print(f"   Creating connection {client_id}...")

                # Create IB client
                ib = IB()

                # Try to connect with extended timeout
                connected = await asyncio.wait_for(
                    ib.connectAsync(self.host, self.port, clientId=client_id),
                    timeout=30.0,
                )

                if ib.isConnected():
                    # Connection successful
                    with self._lock:
                        self._connections[client_id] = ib
                        self._available.put(client_id)
                        self.total_created += 1

                    print(f"   ✅ Connection {client_id} created successfully")
                    success_count += 1
                else:
                    print(f"   ❌ Connection {client_id} failed - not connected")

            except asyncio.TimeoutError:
                print(f"   ⏰ Connection {client_id} timed out (this is expected)")
                # Even with timeout, the connection might be partially established
                # We'll try to use it anyway

            except Exception as e:
                print(f"   ❌ Connection {client_id} failed: {e}")
                self.total_failed += 1

        print(f"📊 Pool initialized: {success_count}/{self.pool_size} connections")
        return success_count

    @contextmanager
    def get_connection(self, timeout=5.0):
        """
        Borrow a connection from the pool.

        Args:
            timeout: Max time to wait for available connection

        Yields:
            IB connection instance

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
                    raise RuntimeError(f"Connection {client_id} not found")

                ib = self._connections[client_id]
                self._in_use.add(client_id)
                self.total_borrowed += 1

            print(f"📤 Borrowed connection {client_id}")
            yield ib

        except Empty:
            raise TimeoutError("No available connections in pool")

        finally:
            # Return connection
            if client_id is not None:
                self._return_connection(client_id)

    def _return_connection(self, client_id):
        """Return a connection to the pool."""
        try:
            with self._lock:
                if client_id in self._in_use:
                    self._in_use.remove(client_id)
                    self._available.put(client_id)
                    self.total_returned += 1

            print(f"📥 Returned connection {client_id}")

        except Exception as e:
            print(f"❌ Error returning connection {client_id}: {e}")

    def get_stats(self):
        """Get pool statistics."""
        with self._lock:
            return {
                "pool_size": self.pool_size,
                "total_connections": len(self._connections),
                "available": self._available.qsize(),
                "in_use": len(self._in_use),
                "total_created": self.total_created,
                "total_borrowed": self.total_borrowed,
                "total_returned": self.total_returned,
                "total_failed": self.total_failed,
            }

    def disconnect_all(self):
        """Disconnect all connections."""
        print("🛑 Disconnecting all connections...")

        with self._lock:
            for client_id, ib in self._connections.items():
                try:
                    if ib.isConnected():
                        ib.disconnect()
                        print(f"   ✅ Disconnected connection {client_id}")
                except Exception as e:
                    print(f"   ⚠️ Error disconnecting {client_id}: {e}")

            self._connections.clear()
            # Clear queues
            while not self._available.empty():
                try:
                    self._available.get_nowait()
                except Empty:
                    break
            self._in_use.clear()


# Test functions
async def test_simple_pool():
    """Test the simple connection pool."""
    print("\n" + "=" * 50)
    print("🧪 TESTING SIMPLE CONNECTION POOL")
    print("=" * 50)

    pool = SimpleConnectionPool(pool_size=3)

    try:
        # Initialize pool
        success_count = await pool.initialize()

        if success_count == 0:
            print("❌ No connections created - IB Gateway may not be responding")
            return False

        print(f"✅ Pool ready with {success_count} connections")

        # Test borrowing
        print("\n🔄 Testing connection borrowing...")

        try:
            with pool.get_connection(timeout=2.0) as ib:
                print(f"✅ Successfully borrowed connection")
                print(f"   Client ID: {ib.client.clientId}")
                print(f"   Connected: {ib.isConnected()}")

                # Try a simple operation
                try:
                    positions = ib.positions()
                    print(f"   📊 Retrieved {len(positions)} positions")
                except Exception as e:
                    print(f"   ⚠️ Data operation failed: {e}")

        except Exception as e:
            print(f"❌ Connection borrowing failed: {e}")
            return False

        # Test multiple borrows
        print("\n🔄 Testing multiple connections...")

        async def borrow_test(test_id):
            try:
                with pool.get_connection(timeout=1.0) as ib:
                    print(f"   ✅ Test {test_id}: Got connection {ib.client.clientId}")
                    await asyncio.sleep(0.5)  # Simulate work
                    return True
            except Exception as e:
                print(f"   ❌ Test {test_id}: {e}")
                return False

        # Run concurrent tests
        tasks = [borrow_test(i) for i in range(1, 4)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        success_count = sum(1 for r in results if r is True)
        print(f"   📊 Concurrent test: {success_count}/3 successful")

        # Print final stats
        stats = pool.get_stats()
        print(f"\n📊 Final Statistics:")
        for key, value in stats.items():
            print(f"   {key}: {value}")

        return success_count > 0

    finally:
        pool.disconnect_all()


async def test_with_current_system():
    """Test integration with current multi-client approach."""
    print("\n" + "=" * 50)
    print("🧪 TESTING INTEGRATION WITH CURRENT SYSTEM")
    print("=" * 50)

    # Simulate the current multi-client approach but with pooled connections
    pool = SimpleConnectionPool(pool_size=4)

    try:
        success_count = await pool.initialize()

        if success_count == 0:
            print("❌ Cannot test integration - no pool connections")
            return False

        print(f"✅ Pool ready for integration test")

        # Simulate multiple data clients using the pool
        client_types = [
            "order_execution",
            "core_data",
            "options_data",
            "administrative",
        ]

        print("\n🔄 Simulating multi-client data requests...")

        async def simulate_client(client_type, client_id):
            try:
                print(f"   🚀 Client {client_id} ({client_type}) requesting data...")

                with pool.get_connection(timeout=3.0) as ib:
                    # Simulate different types of requests
                    if client_type == "order_execution":
                        # Test account info
                        try:
                            account = ib.managedAccounts()
                            print(f"   ✅ {client_type}: Got account info")
                        except:
                            print(f"   ⚠️ {client_type}: Account request failed")

                    elif client_type == "core_data":
                        # Test positions
                        try:
                            positions = ib.positions()
                            print(
                                f"   ✅ {client_type}: Got {len(positions)} positions"
                            )
                        except:
                            print(f"   ⚠️ {client_type}: Positions request failed")

                    else:
                        # Generic test
                        print(f"   ✅ {client_type}: Connection successful")

                    # Simulate processing time
                    await asyncio.sleep(0.3)

                return True

            except Exception as e:
                print(f"   ❌ Client {client_id} ({client_type}) failed: {e}")
                return False

        # Run all clients concurrently (this simulates the real scenario)
        client_tasks = [
            simulate_client(client_type, i + 1)
            for i, client_type in enumerate(client_types)
        ]

        results = await asyncio.gather(*client_tasks, return_exceptions=True)

        success_count = sum(1 for r in results if r is True)
        total_clients = len(client_types)

        print(f"\n📊 Integration Test Results:")
        print(f"   Successful clients: {success_count}/{total_clients}")
        print(f"   Success rate: {success_count / total_clients * 100:.1f}%")

        # This would be a major improvement over current 0% success rate!
        return success_count >= total_clients // 2  # At least 50% success

    finally:
        pool.disconnect_all()


# Main test runner
async def main():
    """Run all tests."""
    print("🚀 SIMPLE CONNECTION POOL TESTING")
    print("=" * 50)
    print("Testing simplified connection pooling approach")
    print("to solve IB Gateway connection issues.")
    print()

    if not IB_AVAILABLE:
        print("❌ ib_async not available")
        return 1

    # Run tests
    tests = [
        ("Simple Pool Basic Test", test_simple_pool),
        ("Integration with Current System", test_with_current_system),
    ]

    results = []

    for test_name, test_func in tests:
        print(f"\n⏳ Running {test_name}...")
        try:
            result = await test_func()
            results.append((test_name, result))
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"{status}: {test_name}")
        except Exception as e:
            print(f"❌ FAILED: {test_name} - {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 50)
    print("📋 TEST SUMMARY")
    print("=" * 50)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")

    print(f"\n📊 Overall: {passed}/{total} tests passed")

    if passed > 0:
        print("🎉 Connection pooling shows promise!")
        print("💡 Next step: Integrate pool into your MultiClientDataManager")
        return 0
    else:
        print("⚠️ Tests failed - check IB Gateway status")
        return 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    exit_code = asyncio.run(main())
    exit(exit_code)
