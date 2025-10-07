#!/usr/bin/env python3
"""
Test script for IB Gateway connection pooling approach.

This script tests the connection pooling solution to resolve the IB Gateway
connection timeout and handshake issues we've been experiencing.

Usage:
    python test_pooled_clients.py

Author: Spyder Trading System
Version: 1.0.0
"""

import asyncio
import sys
import time
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from ib_async import IB, Stock
    from SpyderB_Broker.SpyderB30_IBConnectionPool import IBConnectionPool
    from SpyderB_Broker.SpyderB31_PooledMultiClientManager import (
        PooledMultiClientManager,
        ClientType,
    )

    IB_AVAILABLE = True
except ImportError as e:
    print(f"❌ Import error: {e}")
    IB_AVAILABLE = False


async def test_basic_connection_pool():
    """Test basic connection pool functionality."""
    print("\n" + "=" * 60)
    print("🧪 TESTING BASIC CONNECTION POOL")
    print("=" * 60)

    pool = IBConnectionPool(
        host="127.0.0.1",
        port=4002,  # Paper trading port
        min_connections=2,
        max_connections=4,
        connection_timeout=20.0,
    )

    try:
        # Initialize pool
        print("🔧 Initializing connection pool...")
        if not await pool.initialize():
            print("❌ Failed to initialize connection pool")
            return False

        print("✅ Connection pool initialized successfully")

        # Test borrowing connections
        print("\n🔄 Testing connection borrowing...")

        # Test single connection
        try:
            with pool.get_connection("TestClient1", timeout=5.0) as ib:
                print(f"✅ Borrowed connection: Client ID {ib.client.clientId}")
                print(f"   Connected: {ib.isConnected()}")

                if ib.isConnected():
                    # Try to get some basic data
                    try:
                        positions = ib.positions()
                        print(f"   📊 Retrieved {len(positions)} positions")
                    except Exception as e:
                        print(f"   ⚠️ Data request failed: {e}")

        except Exception as e:
            print(f"❌ Single connection test failed: {e}")
            return False

        # Test concurrent connections
        print("\n🔄 Testing concurrent connections...")

        async def borrow_connection(client_name, delay=0):
            if delay:
                await asyncio.sleep(delay)

            try:
                with pool.get_connection(client_name, timeout=5.0) as ib:
                    client_id = ib.client.clientId
                    print(f"   ✅ {client_name} borrowed connection {client_id}")

                    # Simulate some work
                    await asyncio.sleep(1)

                    return f"{client_name}:success:{client_id}"
            except Exception as e:
                print(f"   ❌ {client_name} failed: {e}")
                return f"{client_name}:failed:{e}"

        # Start multiple concurrent borrows
        tasks = [
            borrow_connection("Client1"),
            borrow_connection("Client2", 0.5),
            borrow_connection("Client3", 1.0),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        success_count = sum(1 for r in results if isinstance(r, str) and "success" in r)
        print(f"   📊 Concurrent test: {success_count}/3 successful")

        # Print pool statistics
        stats = pool.get_stats()
        print(f"\n📊 Pool Statistics:")
        for key, value in stats.items():
            print(f"   {key}: {value}")

        return True

    except Exception as e:
        print(f"❌ Pool test failed: {e}")
        return False

    finally:
        print("\n🛑 Shutting down connection pool...")
        await pool.shutdown()
        print("✅ Pool shutdown complete")


async def test_pooled_multi_client():
    """Test pooled multi-client manager."""
    print("\n" + "=" * 60)
    print("🧪 TESTING POOLED MULTI-CLIENT MANAGER")
    print("=" * 60)

    # Create manager with subset of client types for testing
    manager = PooledMultiClientManager(
        host="127.0.0.1",
        port=4002,
        pool_size=4,
        client_types=[
            ClientType.CORE_DATA,
            ClientType.OPTIONS_DATA,
            ClientType.MARKET_INTERNALS,
            ClientType.ADMINISTRATIVE,
        ],
        connection_timeout=20.0,
        request_timeout=10.0,
    )

    try:
        # Start manager
        print("🔧 Starting pooled multi-client manager...")
        if not await manager.start():
            print("❌ Failed to start manager")
            return False

        print("✅ Manager started successfully")

        # Get list of active clients
        active_clients = manager.list_active_clients()
        print(f"📋 Active clients: {active_clients}")

        # Test market data requests
        print("\n🔄 Testing market data requests...")
        spy_contract = Stock("SPY", "SMART", "USD")

        for client_id in active_clients[:2]:  # Test first 2 clients
            try:
                print(f"   📡 Client {client_id} requesting SPY market data...")
                ticker = await manager.request_market_data(
                    client_id, spy_contract, snapshot=True
                )

                if ticker:
                    print(
                        f"   ✅ Client {client_id} got ticker for {ticker.contract.symbol}"
                    )
                    if hasattr(ticker, "last") and ticker.last:
                        print(f"      Last price: ${ticker.last}")
                else:
                    print(f"   ❌ Client {client_id} failed to get market data")

            except Exception as e:
                print(f"   ❌ Client {client_id} market data error: {e}")

        # Test positions requests
        print("\n🔄 Testing positions requests...")
        for client_id in active_clients[:2]:
            try:
                print(f"   📊 Client {client_id} requesting positions...")
                positions = await manager.get_positions(client_id)

                if positions is not None:
                    print(f"   ✅ Client {client_id} got {len(positions)} positions")
                else:
                    print(f"   ❌ Client {client_id} failed to get positions")

            except Exception as e:
                print(f"   ❌ Client {client_id} positions error: {e}")

        # Test concurrent requests
        print("\n🔄 Testing concurrent requests...")

        async def make_request(client_id, request_type):
            try:
                if request_type == "positions":
                    result = await manager.get_positions(client_id)
                    return f"Client{client_id}:positions:{'success' if result is not None else 'failed'}"
                elif request_type == "account":
                    result = await manager.get_account_summary(client_id)
                    return f"Client{client_id}:account:{'success' if result is not None else 'failed'}"
                else:
                    return f"Client{client_id}:unknown:failed"
            except Exception as e:
                return f"Client{client_id}:{request_type}:error:{e}"

        # Create concurrent requests
        concurrent_tasks = []
        for i, client_id in enumerate(active_clients):
            request_type = "positions" if i % 2 == 0 else "account"
            task = make_request(client_id, request_type)
            concurrent_tasks.append(task)

        if concurrent_tasks:
            concurrent_results = await asyncio.gather(
                *concurrent_tasks, return_exceptions=True
            )

            success_count = sum(
                1 for r in concurrent_results if isinstance(r, str) and "success" in r
            )
            print(
                f"   📊 Concurrent requests: {success_count}/{len(concurrent_tasks)} successful"
            )

            for result in concurrent_results:
                if isinstance(result, str):
                    parts = result.split(":")
                    status = "✅" if "success" in result else "❌"
                    print(f"      {status} {parts[0]} {parts[1]} -> {parts[2]}")

        # Print detailed statistics
        stats = manager.get_stats()
        print(f"\n📊 Manager Statistics:")
        for key, value in stats.items():
            print(f"   {key}: {value}")

        return True

    except Exception as e:
        print(f"❌ Manager test failed: {e}")
        return False

    finally:
        print("\n🛑 Stopping manager...")
        await manager.stop()
        print("✅ Manager stopped")


async def test_stress_scenario():
    """Test stress scenario with rapid requests."""
    print("\n" + "=" * 60)
    print("🧪 TESTING STRESS SCENARIO")
    print("=" * 60)

    pool = IBConnectionPool(
        host="127.0.0.1",
        port=4002,
        min_connections=3,
        max_connections=6,
        connection_timeout=15.0,
    )

    try:
        if not await pool.initialize():
            print("❌ Failed to initialize pool for stress test")
            return False

        print("✅ Stress test pool initialized")

        # Rapid fire connection requests
        print("🔥 Starting rapid connection requests (20 requests in 5 seconds)...")

        async def rapid_request(request_id):
            try:
                with pool.get_connection(
                    f"StressClient{request_id}", timeout=2.0
                ) as ib:
                    if ib.isConnected():
                        # Quick operation
                        await asyncio.sleep(0.1)
                        return f"Request{request_id}:success"
                    else:
                        return f"Request{request_id}:not_connected"
            except Exception as e:
                return f"Request{request_id}:error:{type(e).__name__}"

        # Create 20 rapid requests
        stress_tasks = [rapid_request(i) for i in range(1, 21)]

        start_time = time.time()
        stress_results = await asyncio.gather(*stress_tasks, return_exceptions=True)
        end_time = time.time()

        duration = end_time - start_time
        success_count = sum(
            1 for r in stress_results if isinstance(r, str) and "success" in r
        )

        print(f"   📊 Stress test completed in {duration:.2f} seconds")
        print(
            f"   📊 Success rate: {success_count}/20 ({success_count / 20 * 100:.1f}%)"
        )

        # Analyze results
        error_types = {}
        for result in stress_results:
            if isinstance(result, str) and "error:" in result:
                error_type = result.split("error:")[-1]
                error_types[error_type] = error_types.get(error_type, 0) + 1

        if error_types:
            print("   ⚠️ Error breakdown:")
            for error_type, count in error_types.items():
                print(f"      {error_type}: {count}")

        final_stats = pool.get_stats()
        print(f"   📊 Final pool stats: {final_stats}")

        return success_count >= 15  # 75% success rate acceptable

    except Exception as e:
        print(f"❌ Stress test failed: {e}")
        return False

    finally:
        await pool.shutdown()


async def main():
    """Main test runner."""
    print("🚀 IB GATEWAY CONNECTION POOL TESTING")
    print("=" * 60)
    print("This script tests the connection pooling solution for IB Gateway")
    print("connection issues including timeouts and handshake failures.")
    print()

    if not IB_AVAILABLE:
        print("❌ Required dependencies not available")
        print("   Please ensure ib_async is installed and IB Gateway is running")
        return 1

    # Check if we can connect at all
    print("🔍 Pre-flight check: Testing basic IB Gateway connectivity...")
    try:
        test_ib = IB()
        await asyncio.wait_for(
            test_ib.connectAsync("127.0.0.1", 4002, clientId=999), timeout=10.0
        )

        if test_ib.isConnected():
            print("✅ IB Gateway is reachable")
            test_ib.disconnect()
        else:
            print("❌ IB Gateway connection failed")
            return 1

    except Exception as e:
        print(f"❌ IB Gateway pre-flight check failed: {e}")
        print("   Please ensure IB Gateway is running on port 4002")
        return 1

    # Run tests
    tests = [
        ("Basic Connection Pool", test_basic_connection_pool),
        ("Pooled Multi-Client Manager", test_pooled_multi_client),
        ("Stress Scenario", test_stress_scenario),
    ]

    results = []

    for test_name, test_func in tests:
        print(f"\n⏳ Running {test_name}...")
        try:
            result = await test_func()
            results.append((test_name, result))
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"   {status}: {test_name}")
        except Exception as e:
            print(f"   ❌ FAILED: {test_name} - {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 60)
    print("📋 TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")

    print(f"\n📊 Overall: {passed}/{total} tests passed ({passed / total * 100:.1f}%)")

    if passed == total:
        print("🎉 All tests passed! Connection pooling is working correctly.")
        return 0
    else:
        print("⚠️ Some tests failed. Check IB Gateway settings and connection.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
