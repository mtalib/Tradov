#!/usr/bin/env python3
"""
SPYDER - Minimal TWS API Connection Test
Simple test to verify TWS API handshake and basic functionality
"""

import asyncio
import sys
from datetime import datetime
import socket
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from ib_async import IB, util

    print("✅ ib_async imported successfully")
except ImportError as e:
    print(f"❌ Failed to import ib_async: {e}")
    print("   Install with: pip install ib_async")
    sys.exit(1)


def test_socket_connection(host, port):
    """Test raw socket connection to TWS"""
    print(f"🔌 Testing raw socket connection to {host}:{port}...")

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        start_time = time.time()
        result = sock.connect_ex((host, port))
        connection_time = time.time() - start_time
        sock.close()

        if result == 0:
            print(f"✅ Socket connected in {connection_time:.2f}s")
            return True
        else:
            print(f"❌ Socket connection failed (error: {result})")
            return False

    except Exception as e:
        print(f"❌ Socket test failed: {e}")
        return False


async def test_tws_api_minimal(host="192.168.1.4", port=7497, client_id=1):
    """Minimal TWS API connection test"""
    print(f"\n🕷️ SPYDER - Minimal TWS API Test")
    print(f"=" * 50)
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Client ID: {client_id}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Test socket first
    if not test_socket_connection(host, port):
        print("❌ Socket connection failed - TWS may not be running")
        return False

    # Initialize ib_async
    print(f"🔧 Initializing ib_async...")
    util.startLoop()
    util.logToConsole()
    print("✅ ib_async initialized")

    # Create IB instance
    ib = IB()
    print("✅ IB instance created")

    try:
        print(f"\n⏳ Attempting TWS API connection...")
        print(f"   Timeout: 10 seconds")

        start_time = time.time()

        # Try connection with shorter timeout
        await asyncio.wait_for(
            ib.connectAsync(host=host, port=port, clientId=client_id), timeout=10.0
        )

        connection_time = time.time() - start_time
        print(f"🎉 TWS API connected in {connection_time:.2f} seconds!")
        print(f"   Connection status: {ib.isConnected()}")

        # Test basic functionality
        print(f"\n🔍 Testing basic API functionality...")

        # Get server time
        try:
            server_time = await asyncio.wait_for(ib.reqCurrentTimeAsync(), timeout=5.0)
            print(f"✅ Server time: {server_time}")
        except asyncio.TimeoutError:
            print("⚠️ Server time request timed out")
        except Exception as e:
            print(f"⚠️ Server time request failed: {e}")

        # Get managed accounts
        try:
            accounts = ib.managedAccounts()
            if accounts:
                print(f"✅ Managed accounts: {accounts}")
            else:
                print("⚠️ No managed accounts returned")
        except Exception as e:
            print(f"⚠️ Failed to get accounts: {e}")

        # Keep connection alive briefly
        print(f"\n⏳ Keeping connection alive for 3 seconds...")
        await asyncio.sleep(3)

        print(f"\n🎉 SUCCESS! TWS API connection is working!")
        return True

    except asyncio.TimeoutError:
        print(f"❌ Connection TIMEOUT after 10 seconds")
        print(f"\n🔍 TROUBLESHOOTING:")
        print(f"   • TWS API may not be enabled")
        print(f"   • Client ID {client_id} may be in use")
        print(f"   • Linux IP (192.168.1.9) not in TWS trusted IPs")
        print(f"   • TWS may need restart after configuration")
        return False

    except ConnectionRefusedError:
        print(f"❌ Connection REFUSED")
        print(f"   • TWS is not running on {host}")
        print(f"   • Port {port} is not accessible")
        return False

    except Exception as e:
        print(f"❌ Connection FAILED: {e}")
        print(f"   Error type: {type(e).__name__}")

        # Specific error analysis
        error_str = str(e).lower()
        if "timeout" in error_str:
            print(f"\n💡 TIMEOUT ANALYSIS:")
            print(f"   • Most likely: TWS API not configured properly")
            print(f"   • Add 192.168.1.9 to TWS trusted IPs")
            print(f"   • Enable 'ActiveX and Socket Clients' in TWS")
            print(f"   • Restart TWS after configuration changes")
        elif "already connected" in error_str:
            print(f"\n💡 ALREADY CONNECTED:")
            print(f"   • Try different client ID (current: {client_id})")
        elif "permission denied" in error_str:
            print(f"\n💡 PERMISSION DENIED:")
            print(f"   • TWS API permissions not set correctly")
            print(f"   • Check TWS Global Configuration → API → Settings")

        return False

    finally:
        # Clean disconnect
        if ib.isConnected():
            print(f"\n🔌 Disconnecting from TWS...")
            ib.disconnect()
            print(f"✅ Disconnected cleanly")


async def test_multiple_client_ids(host="192.168.1.4", port=7497):
    """Test different client IDs to find an available one"""
    print(f"\n🔍 Testing multiple client IDs...")

    client_ids = [1, 2, 3, 10, 100]

    for client_id in client_ids:
        print(f"\n📝 Trying client ID: {client_id}")
        success = await test_tws_api_minimal(host, port, client_id)

        if success:
            print(f"🎉 SUCCESS with client ID {client_id}!")
            return client_id

        # Brief pause between attempts
        await asyncio.sleep(2)

    print(f"❌ No working client IDs found")
    return None


def print_configuration_help():
    """Print TWS configuration instructions"""
    print(f"\n" + "=" * 60)
    print(f"📋 TWS API CONFIGURATION INSTRUCTIONS")
    print(f"=" * 60)
    print(f"")
    print(f"On your Windows TWS computer (192.168.1.4):")
    print(f"")
    print(f"1. Open TWS (Trader Workstation)")
    print(f"")
    print(f"2. Go to API Settings:")
    print(f"   File → Global Configuration → API → Settings")
    print(f"")
    print(f"3. Enable API:")
    print(f"   ✅ Check 'Enable ActiveX and Socket Clients'")
    print(f"   ✅ Socket Port: 7497 (Paper Trading)")
    print(f"   ✅ Socket Port: 7496 (Live Trading) - optional")
    print(f"")
    print(f"4. Add Trusted IP:")
    print(f"   ✅ Trusted IPs: 192.168.1.9")
    print(f"   (This is your Linux machine's IP address)")
    print(f"")
    print(f"5. Optional Settings:")
    print(f"   ✅ 'Download open orders on connection'")
    print(f"   ⚪ 'Read-Only API' (if you only want market data)")
    print(f"")
    print(f"6. Apply and Restart:")
    print(f"   ✅ Click Apply → OK")
    print(f"   ✅ Restart TWS completely")
    print(f"")
    print(f"7. Re-run this test:")
    print(f"   python test_tws_minimal.py")
    print(f"")
    print(f"=" * 60)


async def main():
    """Main test function"""
    print(f"🚀 SPYDER - Minimal TWS API Connection Test")
    print(f"=" * 60)
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🐍 Python: {sys.version.split()[0]}")
    print()

    # Configuration
    tws_host = "192.168.1.4"
    tws_port = 7497  # Paper Trading

    print(f"🎯 Target: {tws_host}:{tws_port} (Paper Trading)")
    print(f"🖥️  Linux IP: 192.168.1.9 (should be in TWS trusted IPs)")
    print()

    # Test with default client ID first
    print(f"STEP 1: Test with Client ID 1")
    print(f"=" * 30)
    success = await test_tws_api_minimal(tws_host, tws_port, 1)

    if success:
        print(f"\n🎉 TWS API CONNECTION SUCCESSFUL!")
        print(f"✅ Your TWS is properly configured")
        print(f"✅ SPYDER can now connect to TWS")
        return

    # If failed, try multiple client IDs
    print(f"\nSTEP 2: Try Multiple Client IDs")
    print(f"=" * 30)
    working_client_id = await test_multiple_client_ids(tws_host, tws_port)

    if working_client_id:
        print(f"\n🎉 TWS API CONNECTION SUCCESSFUL!")
        print(f"✅ Use client ID {working_client_id} for SPYDER")
        return

    # If all failed, show configuration help
    print(f"\n❌ ALL CONNECTION ATTEMPTS FAILED")
    print_configuration_help()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback

        traceback.print_exc()
