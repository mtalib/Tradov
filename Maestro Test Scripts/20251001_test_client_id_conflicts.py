#!/usr/bin/env python3
"""
Client ID Conflict & Connection Cleanup Diagnostic
Check if multiple clients are causing Gateway instability
"""

import sys
import time
import asyncio
from datetime import datetime

sys.path.append("/home/adam/Projects/Spyder")

try:
    from ib_async import IB

    print("✅ Using ib_async 1.0.3")
except ImportError as e:
    print(f"❌ Error importing ib_async: {e}")
    sys.exit(1)


async def test_client_id_conflicts():
    """Test if client ID conflicts are causing instability"""
    print("🔍 CLIENT ID CONFLICT DIAGNOSTIC")
    print(f"📅 {datetime.now()}")
    print("=" * 50)

    # Test multiple client IDs sequentially
    test_client_ids = [1, 2, 100, 328, 738, 616, 953, 999]  # Some from dashboard logs

    results = []

    for client_id in test_client_ids:
        print(f"\n🔌 Testing Client ID: {client_id}")
        ib = IB()

        try:
            # Quick connection test with short timeout
            start_time = time.time()
            await ib.connectAsync(
                host="127.0.0.1",
                port=4002,
                clientId=client_id,
                timeout=10,  # Short timeout for quick test
            )

            connection_time = time.time() - start_time

            # Test basic functionality
            accounts = ib.managedAccounts()

            print(f"   ✅ SUCCESS in {connection_time:.2f}s - Accounts: {accounts}")
            results.append(
                {
                    "client_id": client_id,
                    "status": "SUCCESS",
                    "connection_time": connection_time,
                    "accounts": accounts,
                }
            )

            # Clean disconnect
            ib.disconnect()
            await asyncio.sleep(0.5)  # Brief pause between tests

        except Exception as e:
            connection_time = time.time() - start_time
            error_msg = str(e)

            print(f"   ❌ FAILED in {connection_time:.2f}s - Error: {error_msg}")
            results.append(
                {
                    "client_id": client_id,
                    "status": "FAILED",
                    "connection_time": connection_time,
                    "error": error_msg,
                }
            )

            try:
                ib.disconnect()
            except:
                pass

    # Analysis
    print(f"\n" + "=" * 50)
    print(f"📊 CLIENT ID TEST RESULTS")
    print(f"=" * 50)

    successful_ids = [r for r in results if r["status"] == "SUCCESS"]
    failed_ids = [r for r in results if r["status"] == "FAILED"]

    print(f"✅ Successful connections: {len(successful_ids)}")
    print(f"❌ Failed connections: {len(failed_ids)}")

    if successful_ids:
        avg_time = sum(r["connection_time"] for r in successful_ids) / len(
            successful_ids
        )
        print(f"⏱️  Average successful connection time: {avg_time:.2f}s")

        print(f"\n✅ Working Client IDs:")
        for result in successful_ids:
            print(f"   Client {result['client_id']}: {result['connection_time']:.2f}s")

    if failed_ids:
        print(f"\n❌ Failed Client IDs:")
        for result in failed_ids:
            print(f"   Client {result['client_id']}: {result['error']}")

    # Recommendations
    print(f"\n💡 RECOMMENDATIONS:")
    if len(successful_ids) == len(test_client_ids):
        print(f"   ✅ No client ID conflicts detected")
        print(f"   💭 Issue likely NOT client ID related")
        print(f"   🔍 Focus on threading or heartbeat issues")
    elif len(successful_ids) > 0:
        print(f"   ⚠️  Some client IDs work, others don't")
        print(
            f"   💡 Use working client IDs: {[r['client_id'] for r in successful_ids]}"
        )
        print(f"   🚫 Avoid failing client IDs: {[r['client_id'] for r in failed_ids]}")
    else:
        print(f"   💀 ALL client IDs failing - Gateway may be overloaded")
        print(f"   🔄 Consider Gateway restart")


async def test_concurrent_connections():
    """Test if concurrent connections cause issues"""
    print(f"\n🔀 CONCURRENT CONNECTION TEST")
    print("=" * 50)

    # Try to create multiple simultaneous connections
    client_ids = [1001, 1002, 1003]
    connections = []

    try:
        print(f"🔌 Creating {len(client_ids)} concurrent connections...")

        # Create connections concurrently
        tasks = []
        for client_id in client_ids:
            ib = IB()
            connections.append(ib)
            task = ib.connectAsync("127.0.0.1", 4002, client_id, timeout=10)
            tasks.append(task)

        # Wait for all connections
        await asyncio.gather(*tasks)

        print(f"✅ All {len(client_ids)} connections established")

        # Test if they all work
        for i, ib in enumerate(connections):
            accounts = ib.managedAccounts()
            print(f"   Client {client_ids[i]}: {accounts}")

        # Keep connections alive for a few seconds
        print(f"⏳ Keeping connections alive for 10 seconds...")
        await asyncio.sleep(10)

        print(f"✅ Concurrent connections survived 10 seconds")

    except Exception as e:
        print(f"❌ Concurrent connection test failed: {e}")

    finally:
        # Clean up all connections
        for ib in connections:
            try:
                ib.disconnect()
            except:
                pass


async def main():
    """Run client ID diagnostics"""
    await test_client_id_conflicts()
    await test_concurrent_connections()

    print(f"\n🎯 SUMMARY:")
    print(f"This diagnostic helps identify if your Gateway 'death' is caused by:")
    print(f"• Client ID conflicts between dashboard and other connections")
    print(f"• Gateway overload from too many simultaneous connections")
    print(f"• Specific client IDs that trigger instability")


if __name__ == "__main__":
    asyncio.run(main())
