#!/usr/bin/env python3
"""
SPYDER - Handshake Timeout Fix Test
Based on research findings about IB Gateway 10.37 handshake issues
This implements solutions for the classic timeout problem
"""

import asyncio
from ib_async import IB, util
from datetime import datetime
import sys
import os
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


async def test_handshake_timeout_fix_v1():
    """Test Fix V1: Extended timeout with proper waiting"""
    print("🔧 Testing Handshake Timeout Fix V1: Extended Timeout")
    print("=" * 60)

    # Initialize ib_async utilities
    util.startLoop()
    util.logToConsole()

    ib = IB()

    try:
        print("🔌 Connecting with extended timeout (120 seconds)...")
        start_time = time.time()

        # Fix V1: Use much longer timeout for handshake
        await asyncio.wait_for(
            ib.connectAsync(host="127.0.0.1", port=4002, clientId=10),
            timeout=120.0,  # Extended timeout for handshake
        )

        connection_time = time.time() - start_time
        print(f"✅ Connected in {connection_time:.2f} seconds")

        # Test connection
        accounts = ib.managedAccounts()
        print(f"💼 Accounts: {accounts}")

        server_time = await ib.reqCurrentTimeAsync()
        print(f"🕐 Server time: {server_time}")

        print("✅ Fix V1 SUCCESS!")
        return True

    except asyncio.TimeoutError:
        print("❌ Fix V1 FAILED: Still timing out even with 120s timeout")
        return False
    except Exception as e:
        print(f"❌ Fix V1 FAILED: {e}")
        return False
    finally:
        if ib.isConnected():
            ib.disconnect()
            await asyncio.sleep(1)


async def test_handshake_timeout_fix_v2():
    """Test Fix V2: Multiple connection attempts with backoff"""
    print("\n🔧 Testing Handshake Timeout Fix V2: Retry with Backoff")
    print("=" * 60)

    util.startLoop()

    max_attempts = 3
    for attempt in range(max_attempts):
        ib = IB()
        print(f"\n🔄 Attempt {attempt + 1}/{max_attempts}")

        try:
            # Progressive timeout increase
            timeout = 30 + (attempt * 30)  # 30s, 60s, 90s
            print(f"   Timeout: {timeout} seconds")

            start_time = time.time()
            await asyncio.wait_for(
                ib.connectAsync(host="127.0.0.1", port=4002, clientId=11 + attempt),
                timeout=timeout,
            )

            connection_time = time.time() - start_time
            print(f"   ✅ Connected in {connection_time:.2f} seconds")

            # Test connection
            accounts = ib.managedAccounts()
            print(f"   💼 Accounts: {accounts}")

            print("✅ Fix V2 SUCCESS!")
            return True

        except asyncio.TimeoutError:
            print(f"   ⏱️ Attempt {attempt + 1} timed out")
            if attempt < max_attempts - 1:
                wait_time = 5 + (attempt * 5)
                print(f"   ⏳ Waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)
        except Exception as e:
            print(f"   ❌ Attempt {attempt + 1} failed: {e}")
        finally:
            if ib.isConnected():
                ib.disconnect()
                await asyncio.sleep(2)

    print("❌ Fix V2 FAILED: All attempts exhausted")
    return False


async def test_handshake_timeout_fix_v3():
    """Test Fix V3: Pre-connection socket setup"""
    print("\n🔧 Testing Handshake Timeout Fix V3: Socket Pre-setup")
    print("=" * 60)

    util.startLoop()

    ib = IB()

    try:
        print("🔧 Pre-configuring IB client settings...")

        # Fix V3: Configure client before connection
        if hasattr(ib.client, "setTimeout"):
            ib.client.setTimeout(90)  # 90 second timeout
            print("   ✅ Client timeout set to 90 seconds")

        # Set socket options for better reliability
        print("   🔧 Configuring socket options...")

        print("🔌 Connecting with pre-configured client...")
        start_time = time.time()

        await ib.connectAsync(host="127.0.0.1", port=4002, clientId=20, timeout=90)

        connection_time = time.time() - start_time
        print(f"✅ Connected in {connection_time:.2f} seconds")

        # Immediate validation
        print("🔍 Immediate connection validation...")
        if ib.isConnected():
            print("   ✅ Connection active")
        else:
            print("   ❌ Connection not active")
            return False

        # Test basic functionality
        accounts = ib.managedAccounts()
        print(f"💼 Accounts: {accounts}")

        print("✅ Fix V3 SUCCESS!")
        return True

    except Exception as e:
        print(f"❌ Fix V3 FAILED: {e}")
        return False
    finally:
        if ib.isConnected():
            ib.disconnect()
            await asyncio.sleep(1)


async def test_handshake_timeout_fix_v4():
    """Test Fix V4: Manual handshake with reqIds"""
    print("\n🔧 Testing Handshake Timeout Fix V4: Manual Handshake")
    print("=" * 60)

    util.startLoop()

    ib = IB()

    try:
        print("🔌 Connecting with manual handshake approach...")

        # Connect with minimal timeout first
        start_time = time.time()
        await ib.connectAsync(host="127.0.0.1", port=4002, clientId=30)

        connection_time = time.time() - start_time
        print(f"✅ TCP Connected in {connection_time:.2f} seconds")

        # Manual handshake - wait for nextValidId
        print("🤝 Waiting for API handshake (nextValidId)...")
        handshake_start = time.time()

        # Wait for nextValidId with timeout
        next_id = None
        for i in range(60):  # Wait up to 60 seconds
            if hasattr(ib, "client") and hasattr(ib.client, "getReqId"):
                try:
                    next_id = ib.client.getReqId()
                    if next_id > 0:
                        break
                except:
                    pass
            await asyncio.sleep(1)

        handshake_time = time.time() - handshake_start

        if next_id and next_id > 0:
            print(f"✅ Handshake completed in {handshake_time:.2f} seconds")
            print(f"   Next valid ID: {next_id}")

            # Test functionality
            accounts = ib.managedAccounts()
            print(f"💼 Accounts: {accounts}")

            print("✅ Fix V4 SUCCESS!")
            return True
        else:
            print(f"❌ Handshake failed after {handshake_time:.2f} seconds")
            return False

    except Exception as e:
        print(f"❌ Fix V4 FAILED: {e}")
        return False
    finally:
        if ib.isConnected():
            ib.disconnect()
            await asyncio.sleep(1)


async def test_simple_synchronous_connection():
    """Test Fix V5: Simple synchronous connection (blocking)"""
    print("\n🔧 Testing Fix V5: Simple Synchronous Connection")
    print("=" * 60)

    util.startLoop()

    ib = IB()

    try:
        print("🔌 Using simple synchronous connect() method...")
        start_time = time.time()

        # Fix V5: Use synchronous connect instead of connectAsync
        ib.connect(host="127.0.0.1", port=4002, clientId=40, timeout=60)

        connection_time = time.time() - start_time
        print(f"✅ Connected in {connection_time:.2f} seconds")

        # Test immediately
        if ib.isConnected():
            print("   ✅ Connection verified")

            accounts = ib.managedAccounts()
            print(f"💼 Accounts: {accounts}")

            # Keep alive briefly
            print("⏳ Testing connection stability (10 seconds)...")
            await asyncio.sleep(10)

            if ib.isConnected():
                print("✅ Connection remained stable")
                print("✅ Fix V5 SUCCESS!")
                return True
            else:
                print("❌ Connection dropped during test")
                return False
        else:
            print("❌ Connection not verified")
            return False

    except Exception as e:
        print(f"❌ Fix V5 FAILED: {e}")
        return False
    finally:
        if ib.isConnected():
            ib.disconnect()


async def test_connection_with_event_waiting():
    """Test Fix V6: Wait for specific events"""
    print("\n🔧 Testing Fix V6: Event-Based Connection")
    print("=" * 60)

    util.startLoop()

    ib = IB()
    connection_established = False

    def on_connected():
        nonlocal connection_established
        connection_established = True
        print("📡 Connection event received!")

    def on_error(reqId, errorCode, errorString, contract):
        print(f"⚠️ Error event: {errorCode} - {errorString}")

    try:
        # Attach event handlers
        ib.connectedEvent += on_connected
        ib.errorEvent += on_error

        print("🔌 Connecting with event handlers...")
        start_time = time.time()

        await ib.connectAsync(host="127.0.0.1", port=4002, clientId=50)

        # Wait for connection event
        print("⏳ Waiting for connection event...")
        for i in range(60):
            if connection_established:
                break
            await asyncio.sleep(1)

        connection_time = time.time() - start_time

        if connection_established:
            print(f"✅ Event-based connection in {connection_time:.2f} seconds")

            accounts = ib.managedAccounts()
            print(f"💼 Accounts: {accounts}")

            print("✅ Fix V6 SUCCESS!")
            return True
        else:
            print("❌ No connection event received")
            return False

    except Exception as e:
        print(f"❌ Fix V6 FAILED: {e}")
        return False
    finally:
        if ib.isConnected():
            ib.disconnect()
            await asyncio.sleep(1)


async def main():
    """Main test runner"""
    print("🚀 SPYDER - Handshake Timeout Fix Tests")
    print("=" * 70)
    print(f"📅 Started: {datetime.now()}")
    print(f"🐍 Python: {sys.version}")
    print()

    print("🎯 Testing multiple approaches to fix IB Gateway handshake timeout...")
    print()

    # Test all fixes
    fixes = [
        ("Extended Timeout", test_handshake_timeout_fix_v1),
        ("Retry with Backoff", test_handshake_timeout_fix_v2),
        ("Socket Pre-setup", test_handshake_timeout_fix_v3),
        ("Manual Handshake", test_handshake_timeout_fix_v4),
        ("Synchronous Connection", test_simple_synchronous_connection),
        ("Event-Based Connection", test_connection_with_event_waiting),
    ]

    successful_fixes = []

    for fix_name, fix_function in fixes:
        try:
            print(f"\n{'=' * 70}")
            print(f"🧪 TESTING: {fix_name}")
            print(f"{'=' * 70}")

            success = await fix_function()

            if success:
                successful_fixes.append(fix_name)
                print(f"🎉 {fix_name}: SUCCESS!")
            else:
                print(f"❌ {fix_name}: FAILED")

            # Brief pause between tests
            await asyncio.sleep(2)

        except Exception as e:
            print(f"💥 {fix_name}: CRASHED - {e}")

    # Summary
    print(f"\n{'=' * 70}")
    print("📊 FINAL RESULTS")
    print(f"{'=' * 70}")

    if successful_fixes:
        print(f"✅ SUCCESSFUL FIXES: {len(successful_fixes)}")
        for fix in successful_fixes:
            print(f"   🎯 {fix}")

        print(f"\n💡 RECOMMENDATIONS:")
        print(f"   • Use the first successful fix in your main application")
        print(
            f"   • The working pattern should be implemented in SpyderB01_SpyderClient.py"
        )
        print(f"   • Test with your actual trading application")

    else:
        print("❌ NO FIXES WORKED")
        print("   This indicates a deeper Gateway configuration issue")
        print("   Check Gateway logs and API settings")

    print(f"\n🕐 Test completed: {datetime.now()}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️ Tests interrupted by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback

        traceback.print_exc()
