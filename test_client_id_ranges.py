#!/usr/bin/env python3
"""
Test different client ID ranges to diagnose IB Gateway restrictions.

This script tests various client ID ranges to determine if IB Gateway
has specific restrictions on which client IDs can connect successfully.

The dashboard works with Client ID 0, but data clients (1-11) fail.
This test will help identify if certain client ID ranges work better.

Usage:
    python test_client_id_ranges.py

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
    from ib_async import IB

    IB_AVAILABLE = True
except ImportError:
    print("❌ ib_async not available")
    IB_AVAILABLE = False
    IB = None


async def test_single_client_id(client_id, timeout=15.0):
    """
    Test a single client ID to see if it can connect.

    Args:
        client_id: Client ID to test
        timeout: Connection timeout in seconds

    Returns:
        dict: Test results
    """
    result = {
        "client_id": client_id,
        "connected": False,
        "socket_connected": False,
        "handshake_success": False,
        "data_retrieved": False,
        "connection_time": None,
        "error": None,
        "duration": 0,
    }

    ib = None
    start_time = time.time()

    try:
        print(f"   Testing client ID {client_id}...", end=" ")

        ib = IB()

        # Try to connect
        await asyncio.wait_for(
            ib.connectAsync("127.0.0.1", 4002, clientId=client_id), timeout=timeout
        )

        connection_time = time.time() - start_time
        result["connection_time"] = connection_time
        result["socket_connected"] = True

        if ib.isConnected():
            result["connected"] = True
            result["handshake_success"] = True

            # Try to get some data to verify full functionality
            try:
                positions = ib.positions()
                result["data_retrieved"] = True
                print(
                    f"✅ SUCCESS ({connection_time:.2f}s, {len(positions)} positions)"
                )
            except Exception as e:
                print(f"⚠️ CONNECTED but no data ({connection_time:.2f}s): {e}")
        else:
            print(f"❌ NOT CONNECTED after {connection_time:.2f}s")

    except asyncio.TimeoutError:
        duration = time.time() - start_time
        result["duration"] = duration
        result["error"] = f"Timeout after {duration:.1f}s"
        print(f"⏰ TIMEOUT ({duration:.1f}s)")

    except Exception as e:
        duration = time.time() - start_time
        result["duration"] = duration
        result["error"] = str(e)
        print(f"❌ ERROR ({duration:.1f}s): {e}")

    finally:
        # Clean up
        if ib and ib.isConnected():
            try:
                ib.disconnect()
            except:
                pass

        result["duration"] = time.time() - start_time

    return result


async def test_client_id_range(start_id, end_id, test_name):
    """
    Test a range of client IDs.

    Args:
        start_id: Starting client ID
        end_id: Ending client ID (inclusive)
        test_name: Name for this test range

    Returns:
        list: Test results for all IDs in range
    """
    print(f"\n🔍 Testing {test_name} (IDs {start_id}-{end_id})")
    print("=" * 60)

    results = []

    for client_id in range(start_id, end_id + 1):
        result = await test_single_client_id(client_id)
        results.append(result)

        # Small delay between tests to avoid overwhelming IB Gateway
        await asyncio.sleep(0.5)

    # Summary for this range
    successful = [r for r in results if r["connected"]]
    data_success = [r for r in results if r["data_retrieved"]]

    print(f"\n📊 {test_name} Summary:")
    print(f"   Total tested: {len(results)}")
    print(f"   Connected: {len(successful)}")
    print(f"   Data retrieved: {len(data_success)}")
    print(f"   Success rate: {len(successful) / len(results) * 100:.1f}%")

    if successful:
        print(f"   ✅ Successful IDs: {[r['client_id'] for r in successful]}")
        avg_time = sum(r["connection_time"] for r in successful) / len(successful)
        print(f"   ⏱️ Average connection time: {avg_time:.2f}s")

    return results


async def test_concurrent_connections(client_ids, test_name):
    """
    Test multiple client IDs concurrently to see if IB Gateway
    allows multiple simultaneous connections.

    Args:
        client_ids: List of client IDs to test concurrently
        test_name: Name for this test

    Returns:
        list: Test results
    """
    print(f"\n🔄 Testing {test_name} - Concurrent Connections")
    print("=" * 60)
    print(f"Testing client IDs: {client_ids}")

    async def connect_client(client_id):
        """Connect a single client and hold connection."""
        result = {
            "client_id": client_id,
            "connected": False,
            "hold_duration": 0,
            "error": None,
        }

        ib = None
        start_time = time.time()

        try:
            print(f"   🔌 Client {client_id} connecting...")
            ib = IB()

            await asyncio.wait_for(
                ib.connectAsync("127.0.0.1", 4002, clientId=client_id), timeout=10.0
            )

            if ib.isConnected():
                result["connected"] = True
                print(f"   ✅ Client {client_id} connected")

                # Hold connection for 5 seconds
                await asyncio.sleep(5.0)
                result["hold_duration"] = 5.0

                print(f"   🔌 Client {client_id} holding connection...")

            else:
                print(f"   ❌ Client {client_id} failed to connect")

        except Exception as e:
            result["error"] = str(e)
            print(f"   ❌ Client {client_id} error: {e}")

        finally:
            if ib and ib.isConnected():
                try:
                    ib.disconnect()
                    print(f"   🔌 Client {client_id} disconnected")
                except:
                    pass

        return result

    # Start all connections concurrently
    tasks = [connect_client(client_id) for client_id in client_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    valid_results = [r for r in results if isinstance(r, dict)]
    successful = [r for r in valid_results if r["connected"]]

    print(f"\n📊 {test_name} Summary:")
    print(f"   Attempted: {len(client_ids)}")
    print(f"   Successful: {len(successful)}")
    print(f"   Concurrent success rate: {len(successful) / len(client_ids) * 100:.1f}%")

    if successful:
        print(
            f"   ✅ Successful concurrent IDs: {[r['client_id'] for r in successful]}"
        )

    return valid_results


async def main():
    """Main test runner."""
    print("🚀 IB GATEWAY CLIENT ID RANGE TESTING")
    print("=" * 60)
    print("This script tests different client ID ranges to diagnose")
    print("why the dashboard (ID 0) works but data clients (1-11) fail.")
    print()

    if not IB_AVAILABLE:
        print("❌ ib_async not available")
        return 1

    # Test different ranges
    test_ranges = [
        # Dashboard range (known to work)
        (0, 0, "Dashboard Range (ID 0)"),
        # Current data client range (known to fail)
        (1, 5, "Current Data Client Range (IDs 1-5)"),
        # Higher ranges
        (10, 15, "Higher Range (IDs 10-15)"),
        (100, 105, "Much Higher Range (IDs 100-105)"),
        # Common IB ranges
        (1000, 1005, "Common IB Range (IDs 1000-1005)"),
        # Random high range
        (5000, 5005, "High Range (IDs 5000-5005)"),
    ]

    all_results = []

    # Test each range sequentially
    for start_id, end_id, test_name in test_ranges:
        try:
            results = await test_client_id_range(start_id, end_id, test_name)
            all_results.extend(results)

            # Pause between ranges
            await asyncio.sleep(2.0)

        except Exception as e:
            print(f"❌ Failed to test {test_name}: {e}")

    # Test concurrent connections with successful IDs
    successful_ids = [r["client_id"] for r in all_results if r["connected"]]

    if len(successful_ids) >= 2:
        print(
            f"\n🔄 Found {len(successful_ids)} working IDs, testing concurrent connections..."
        )

        # Test first few successful IDs concurrently
        test_ids = successful_ids[: min(3, len(successful_ids))]
        concurrent_results = await test_concurrent_connections(
            test_ids, "Working IDs Concurrent Test"
        )

    # Final summary
    print("\n" + "=" * 60)
    print("📋 FINAL ANALYSIS")
    print("=" * 60)

    total_tested = len(all_results)
    total_successful = len([r for r in all_results if r["connected"]])
    data_successful = len([r for r in all_results if r["data_retrieved"]])

    print(f"Total client IDs tested: {total_tested}")
    print(f"Successfully connected: {total_successful}")
    print(f"Successfully retrieved data: {data_successful}")
    print(f"Overall success rate: {total_successful / total_tested * 100:.1f}%")

    if total_successful > 0:
        successful_ids = [r["client_id"] for r in all_results if r["connected"]]
        print(f"\n✅ Working client IDs: {successful_ids}")

        # Analyze patterns
        if 0 in successful_ids:
            print("🎯 Client ID 0 works (dashboard)")

        working_ranges = []
        for r in all_results:
            if r["connected"]:
                if r["client_id"] < 10:
                    working_ranges.append("Low (0-9)")
                elif r["client_id"] < 100:
                    working_ranges.append("Medium (10-99)")
                elif r["client_id"] < 1000:
                    working_ranges.append("High (100-999)")
                else:
                    working_ranges.append("Very High (1000+)")

        unique_ranges = list(set(working_ranges))
        if len(unique_ranges) == 1:
            print(f"📊 Pattern: Only {unique_ranges[0]} range works")
        else:
            print(f"📊 Pattern: Multiple ranges work: {unique_ranges}")

        print(f"\n💡 RECOMMENDATION:")
        if total_successful >= 5:
            print(
                "   ✅ Multiple client IDs work - use connection pooling with working IDs"
            )
            print(
                f"   🔧 Configure your data clients to use IDs: {successful_ids[:10]}"
            )
        elif 0 in successful_ids and len(successful_ids) == 1:
            print(
                "   ⚠️ Only client ID 0 works - IB Gateway may be configured for single client"
            )
            print("   🔧 Check IB Gateway API settings for concurrent client limits")
        else:
            print("   ⚠️ Limited client IDs work - investigate IB Gateway configuration")
    else:
        print("\n❌ NO CLIENT IDs WORK")
        print("   🔧 Check IB Gateway status and API settings")
        print("   🔧 Verify IB Gateway is logged in and API is enabled")

    # Timeout analysis
    timeout_results = [r for r in all_results if "Timeout" in str(r.get("error", ""))]
    if timeout_results:
        print(f"\n⏰ TIMEOUT ANALYSIS:")
        print(f"   {len(timeout_results)} client IDs timed out")
        avg_timeout = sum(r["duration"] for r in timeout_results) / len(timeout_results)
        print(f"   Average timeout duration: {avg_timeout:.1f}s")
        print("   This suggests handshake/authentication issues")

    return 0 if total_successful > 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
