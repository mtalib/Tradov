#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Direct IB Gateway Connection Test
Test direct ib_async connection without complex timeout handling
"""

import sys
import time
import asyncio
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from ib_async import IB, util

    IB_ASYNC_AVAILABLE = True
    print("✅ ib_async imported successfully")
except ImportError as e:
    print(f"❌ ib_async import failed: {e}")
    IB_ASYNC_AVAILABLE = False
    sys.exit(1)


def test_direct_sync_connection():
    """Test synchronous connection to IB Gateway"""

    print("\n🔌 Testing Synchronous Connection")
    print("-" * 40)

    try:
        # Create IB instance
        ib = IB()

        # Set longer timeout
        ib.RequestTimeout = 60  # 60 seconds instead of default 4

        print(f"📋 Configuration:")
        print(f"   Host: 127.0.0.1")
        print(f"   Port: 4002")
        print(f"   Client ID: 997")
        print(f"   Timeout: {ib.RequestTimeout}s")

        # Connect
        print(f"\n🔌 Connecting...")
        ib.connect(
            host="127.0.0.1",
            port=4002,
            clientId=997,
            timeout=30,  # Connection timeout
            readonly=False,  # Full access
        )

        if ib.isConnected():
            print("🎉 SUCCESS! Connected to IB Gateway")
            print(f"✅ Client ID 997 should now be visible in IB Gateway")

            # Wait for initial messages
            print("⏳ Waiting for API initialization...")
            time.sleep(5)

            # Try to get account info
            print("📊 Testing API functionality...")
            try:
                accounts = ib.managedAccounts()
                if accounts:
                    print(f"✅ Managed accounts: {accounts}")
                else:
                    print("⚠️  No managed accounts received yet")
            except Exception as e:
                print(f"⚠️  Account info error: {e}")

            # Keep connection alive
            print("⏳ Keeping connection alive for 15 seconds...")
            for i in range(15):
                if ib.isConnected():
                    print(f"   Connected... {15 - i}s remaining")
                    time.sleep(1)
                else:
                    print("❌ Connection lost during test!")
                    break

            # Disconnect
            print("🔌 Disconnecting...")
            ib.disconnect()
            print("✅ Disconnected successfully")

            return True

        else:
            print("❌ Failed to connect")
            return False

    except Exception as e:
        print(f"❌ Connection error: {e}")
        try:
            ib.disconnect()
        except:
            pass
        return False


def test_direct_async_connection():
    """Test asynchronous connection to IB Gateway"""

    print("\n🔌 Testing Asynchronous Connection")
    print("-" * 40)

    async def async_connect():
        try:
            # Create IB instance
            ib = IB()

            # Set longer timeout
            ib.RequestTimeout = 60

            print(f"📋 Async Configuration:")
            print(f"   Host: 127.0.0.1")
            print(f"   Port: 4002")
            print(f"   Client ID: 996")
            print(f"   Timeout: {ib.RequestTimeout}s")

            # Connect asynchronously
            print(f"\n🔌 Connecting asynchronously...")
            await ib.connectAsync(
                host="127.0.0.1", port=4002, clientId=996, timeout=30, readonly=False
            )

            if ib.isConnected():
                print("🎉 SUCCESS! Async connection established")
                print(f"✅ Client ID 996 should now be visible in IB Gateway")

                # Wait for initialization
                print("⏳ Waiting for async API initialization...")
                await asyncio.sleep(5)

                # Try API calls
                print("📊 Testing async API functionality...")
                try:
                    accounts = ib.managedAccounts()
                    if accounts:
                        print(f"✅ Async managed accounts: {accounts}")
                    else:
                        print("⚠️  No async managed accounts received yet")
                except Exception as e:
                    print(f"⚠️  Async account info error: {e}")

                # Keep alive
                print("⏳ Keeping async connection alive for 15 seconds...")
                for i in range(15):
                    if ib.isConnected():
                        print(f"   Async connected... {15 - i}s remaining")
                        await asyncio.sleep(1)
                    else:
                        print("❌ Async connection lost during test!")
                        break

                # Disconnect
                print("🔌 Disconnecting async...")
                ib.disconnect()
                print("✅ Async disconnected successfully")

                return True

            else:
                print("❌ Async connection failed")
                return False

        except Exception as e:
            print(f"❌ Async connection error: {e}")
            try:
                ib.disconnect()
            except:
                pass
            return False

    # Run async function
    try:
        return asyncio.run(async_connect())
    except Exception as e:
        print(f"❌ Async runner error: {e}")
        return False


def test_multiple_clients():
    """Test multiple simultaneous connections"""

    print("\n🔌 Testing Multiple Client Connections")
    print("-" * 40)

    clients = []
    success_count = 0

    try:
        # Create 3 clients with different IDs
        for client_num in range(3):
            client_id = 994 + client_num  # 994, 995, 996

            print(f"\n🔌 Creating client {client_num + 1}/3 (ID: {client_id})")

            try:
                ib = IB()
                ib.RequestTimeout = 60

                ib.connect(
                    host="127.0.0.1",
                    port=4002,
                    clientId=client_id,
                    timeout=20,
                    readonly=False,
                )

                if ib.isConnected():
                    print(f"✅ Client {client_id} connected successfully")
                    clients.append((client_id, ib))
                    success_count += 1

                    # Small delay between connections
                    time.sleep(1)

                else:
                    print(f"❌ Client {client_id} failed to connect")

            except Exception as e:
                print(f"❌ Client {client_id} error: {e}")

        if success_count > 0:
            print(f"\n🎉 SUCCESS! {success_count}/3 clients connected")
            print(f"✅ You should see {success_count} clients in IB Gateway")

            # Keep all connections alive
            print("⏳ Keeping multiple connections alive for 10 seconds...")
            for i in range(10):
                active_count = sum(1 for _, ib in clients if ib.isConnected())
                print(
                    f"   Active clients: {active_count}/{success_count} ... {10 - i}s"
                )
                time.sleep(1)

            # Disconnect all
            print("🔌 Disconnecting all clients...")
            for client_id, ib in clients:
                try:
                    ib.disconnect()
                    print(f"✅ Client {client_id} disconnected")
                except Exception as e:
                    print(f"⚠️  Client {client_id} disconnect error: {e}")

            return True

        else:
            print("❌ No clients connected successfully")
            return False

    except Exception as e:
        print(f"❌ Multiple client test error: {e}")

        # Clean up any remaining connections
        for client_id, ib in clients:
            try:
                ib.disconnect()
            except:
                pass

        return False


def check_gateway_status():
    """Check IB Gateway status before testing"""

    print("🔍 Pre-test Gateway Check")
    print("-" * 40)

    import socket
    import subprocess

    # Check process
    try:
        result = subprocess.run(
            ["pgrep", "-f", "ibgateway"], capture_output=True, text=True
        )
        if result.returncode == 0:
            pids = result.stdout.strip().split("\n")
            print(f"✅ Gateway process running (PID: {', '.join(pids)})")
        else:
            print("❌ Gateway process not found")
            return False
    except Exception as e:
        print(f"⚠️  Process check error: {e}")

    # Check port
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex(("127.0.0.1", 4002))
        sock.close()

        if result == 0:
            print("✅ Gateway port 4002 is accessible")
            return True
        else:
            print("❌ Gateway port 4002 is not accessible")
            return False
    except Exception as e:
        print(f"❌ Port check error: {e}")
        return False


def main():
    """Main test function"""

    print("🕷️ SPYDER - Direct IB Gateway Connection Test")
    print("Testing direct ib_async connections without complex wrappers")
    print("=" * 60)

    if not IB_ASYNC_AVAILABLE:
        print("❌ ib_async not available")
        return 1

    # Pre-test check
    if not check_gateway_status():
        print("\n❌ Gateway not ready for testing")
        return 1

    results = []

    # Test 1: Synchronous connection
    print(f"\n{'=' * 20} TEST 1: SYNC CONNECTION {'=' * 20}")
    result1 = test_direct_sync_connection()
    results.append(("Synchronous Connection", result1))

    # Wait between tests
    time.sleep(2)

    # Test 2: Asynchronous connection
    print(f"\n{'=' * 20} TEST 2: ASYNC CONNECTION {'=' * 19}")
    result2 = test_direct_async_connection()
    results.append(("Asynchronous Connection", result2))

    # Wait between tests
    time.sleep(2)

    # Test 3: Multiple clients
    print(f"\n{'=' * 20} TEST 3: MULTIPLE CLIENTS {'=' * 19}")
    result3 = test_multiple_clients()
    results.append(("Multiple Clients", result3))

    # Results summary
    print(f"\n{'=' * 25} RESULTS {'=' * 28}")

    success_count = 0
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name}: {status}")
        if success:
            success_count += 1

    print(f"\nOverall: {success_count}/{len(results)} tests passed")

    if success_count > 0:
        print("\n🎉 SUCCESS! At least one connection method works!")
        print("💡 This means:")
        print("   ✅ IB Gateway API is properly enabled")
        print("   ✅ ib_async library is working")
        print("   ✅ Clients can connect and should be visible")
        print(
            "   ✅ The issue is likely in the SPYDER connection manager timeout handling"
        )

        print("\n🔧 Recommended fix:")
        print("   - Increase timeout values in ConnectionManager")
        print("   - Use direct ib_async connections in dashboard")
        print("   - Implement proper async/await patterns")

        return 0
    else:
        print("\n❌ All connection tests failed")
        print("💡 This indicates an IB Gateway configuration issue:")
        print("   - Check 'Enable ActiveX and Socket Clients' in Gateway")
        print("   - Verify socket port is set to 4002")
        print("   - Add 127.0.0.1 to Trusted IP addresses")
        print("   - Restart Gateway after configuration changes")

        return 1


if __name__ == "__main__":
    sys.exit(main())
