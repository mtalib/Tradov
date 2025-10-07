#!/usr/bin/env python3
"""
SPYDER - Test Working Connection Pattern
Based on the exact working pattern from user's research
This implements the proven connection method that works with IB Gateway
"""

import asyncio
from ib_async import IB, util
from datetime import datetime
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


async def test_working_connection_pattern():
    """Test using the exact working pattern from research"""
    print("🕷️ SPYDER - Testing Working Connection Pattern")
    print("=" * 50)
    print(f"📅 Started: {datetime.now()}")
    print()

    # Enable logging for debugging (from working example)
    util.startLoop()  # Required for ib_async in non-asyncio environments
    util.logToConsole()  # Logs to stdout (optional, for debugging)
    print("✅ ib_async utilities initialized")

    # Create IB instance (from working example)
    ib = IB()
    print("✅ IB instance created")

    try:
        print("\n🔌 Connecting to IB Gateway...")
        print("   Host: 127.0.0.1")
        print("   Port: 4002 (Paper Trading)")
        print("   Client ID: 1")
        print("   Method: connectAsync")

        # Connect to Gateway: host='127.0.0.1', port=4002, clientId=1
        # Use unique clientId for each client (e.g., 1, 2, 3)
        start_time = datetime.now()
        await ib.connectAsync(host="127.0.0.1", port=4002, clientId=1)
        connection_time = (datetime.now() - start_time).total_seconds()

        print(f"✅ Connected to IB Gateway in {connection_time:.2f} seconds")
        print(f"   Connection status: {ib.isConnected()}")

        # Test connection by requesting server time (from working example)
        print("\n🕐 Testing connection with server time request...")
        server_time = await ib.reqCurrentTimeAsync()
        print(f"✅ Current IB server time: {server_time}")

        # Get managed accounts to verify connection
        print("\n💼 Getting managed accounts...")
        accounts = ib.managedAccounts()
        print(f"✅ Managed accounts: {accounts}")

        # Test basic market data request
        print("\n📊 Testing basic market data...")
        from ib_async import Stock

        spy_contract = Stock("SPY", "SMART", "USD")
        ib.qualifyContracts(spy_contract)
        print("✅ Contract qualified successfully")

        # Keep connection alive briefly for demo (from working example)
        print(f"\n⏳ Keeping connection alive for 10 seconds...")
        await asyncio.sleep(10)

        print("\n🎉 ALL TESTS PASSED!")
        print("✅ IB Gateway connection is working perfectly")
        print("✅ This pattern should work in your main application")

        return True

    except Exception as e:
        print(f"\n❌ Connection failed: {e}")
        print(f"   Error type: {type(e).__name__}")

        # Detailed error analysis
        if "timeout" in str(e).lower():
            print("\n🔍 TIMEOUT ERROR ANALYSIS:")
            print("   • IB Gateway may not be running")
            print("   • Port 4002 may not be accessible")
            print("   • Gateway may be in startup phase")
            print("   • Client ID may be in use")

        elif "connection refused" in str(e).lower():
            print("\n🔍 CONNECTION REFUSED ANALYSIS:")
            print("   • IB Gateway is not running")
            print("   • Wrong port (should be 4002 for paper)")
            print("   • Firewall blocking connection")

        elif "already connected" in str(e).lower():
            print("\n🔍 ALREADY CONNECTED ANALYSIS:")
            print("   • Client ID 1 is already in use")
            print("   • Try a different client ID")

        return False

    finally:
        # Clean disconnect (from working example)
        if ib.isConnected():
            ib.disconnect()
            print("\n🔌 Disconnected cleanly")


async def test_multiple_client_ids():
    """Test multiple client IDs to find available ones"""
    print("\n" + "=" * 50)
    print("🔍 Testing Multiple Client IDs")
    print("=" * 50)

    client_ids_to_test = [1, 2, 3, 10, 11, 12, 50, 51, 52]
    working_client_ids = []

    for client_id in client_ids_to_test:
        print(f"\n🔄 Testing Client ID: {client_id}")

        ib = IB()
        try:
            # Quick connection test with short timeout
            await asyncio.wait_for(
                ib.connectAsync(host="127.0.0.1", port=4002, clientId=client_id),
                timeout=10,
            )

            print(f"   ✅ Client ID {client_id} works!")
            working_client_ids.append(client_id)

            # Quick test
            accounts = ib.managedAccounts()
            print(f"   💼 Accounts: {accounts}")

        except asyncio.TimeoutError:
            print(f"   ⏱️ Client ID {client_id} timed out")
        except Exception as e:
            if "already connected" in str(e).lower():
                print(f"   🔄 Client ID {client_id} already in use")
            else:
                print(f"   ❌ Client ID {client_id} failed: {e}")
        finally:
            if ib.isConnected():
                ib.disconnect()
                await asyncio.sleep(0.5)  # Brief pause between tests

    print(f"\n📊 RESULTS:")
    print(f"✅ Working Client IDs: {working_client_ids}")
    print(f"📈 Success Rate: {len(working_client_ids)}/{len(client_ids_to_test)}")

    return working_client_ids


async def diagnose_gateway_status():
    """Diagnose IB Gateway status and configuration"""
    print("\n" + "=" * 50)
    print("🔍 IB Gateway Diagnostics")
    print("=" * 50)

    # Check if Gateway process is running
    import subprocess

    try:
        result = subprocess.run(
            ["pgrep", "-f", "ibgateway"], capture_output=True, text=True, timeout=5
        )
        if result.stdout.strip():
            print("✅ IB Gateway process is running")
            pids = result.stdout.strip().split("\n")
            print(f"   Process IDs: {pids}")
        else:
            print("❌ IB Gateway process not found")
            print("   Start Gateway with: ./launch_spyder_with_gateway.sh")
            return False
    except Exception as e:
        print(f"⚠️ Could not check Gateway process: {e}")

    # Check if port 4002 is accessible
    import socket

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex(("127.0.0.1", 4002))
        sock.close()

        if result == 0:
            print("✅ Port 4002 is accessible")
        else:
            print("❌ Port 4002 is not accessible")
            print("   Gateway may not be fully started")
            return False
    except Exception as e:
        print(f"⚠️ Could not test port 4002: {e}")
        return False

    # Check port 4001 (live trading) as well
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex(("127.0.0.1", 4001))
        sock.close()

        if result == 0:
            print("✅ Port 4001 (live trading) is also accessible")
        else:
            print("ℹ️ Port 4001 (live trading) not accessible (normal for paper setup)")
    except Exception as e:
        print(f"ℹ️ Could not test port 4001: {e}")

    return True


async def main():
    """Main test function"""
    print("🚀 Starting SPYDER Connection Pattern Tests")
    print(f"🐍 Python: {sys.version}")
    print(f"📅 Time: {datetime.now()}")
    print()

    # Step 1: Diagnose Gateway status
    gateway_ok = await diagnose_gateway_status()
    if not gateway_ok:
        print("\n❌ Gateway diagnostics failed")
        print("   Please start IB Gateway and try again")
        return

    # Step 2: Test the working connection pattern
    success = await test_working_connection_pattern()

    if success:
        print("\n🎉 SUCCESS! The working pattern is confirmed")
        print("✅ Your IB Gateway connection is working")
        print("✅ This exact pattern should work in SPYDER")

        # Step 3: Test multiple client IDs if main test worked
        working_ids = await test_multiple_client_ids()

        if working_ids:
            print(f"\n💡 RECOMMENDATIONS:")
            print(f"   • Use Client IDs: {working_ids[:3]} for your applications")
            print(f"   • Avoid Client IDs already in use")
            print(f"   • Use util.startLoop() before connecting")
            print(f"   • Use connectAsync() instead of connect()")
            print(f"   • Keep connections simple - avoid complex retry logic")
    else:
        print("\n❌ Connection pattern test failed")
        print("   Check the error analysis above")
        print("   Ensure IB Gateway is running and configured")


if __name__ == "__main__":
    try:
        # Run the tests
        asyncio.run(main())

    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback

        traceback.print_exc()
