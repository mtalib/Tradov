#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Test Existing Connection Manager with Local IB Gateway

This script tests the existing SpyderB05_ConnectionManager to establish
connections to the local IB Gateway that is currently running.
"""

import sys
import time
import logging
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_existing_connection_manager():
    """Test the existing SpyderB05_ConnectionManager"""

    print("🕷️  SPYDER - Testing Existing Connection Manager")
    print("=" * 60)

    try:
        # Import the existing connection manager
        from SpyderB_Broker.SpyderB05_ConnectionManager import (
            ConnectionManager,
            ConnectionConfig,
            GatewayConfig,
            TradingMode,
        )

        print("✅ Successfully imported SpyderB05_ConnectionManager")

        # Create configuration for LOCAL IB Gateway (not remote TWS)
        gateway_config = GatewayConfig(
            host="127.0.0.1",  # LOCAL Gateway
            port=4002,  # Paper port
            trading_mode=TradingMode.PAPER,
            auto_start=False,  # Don't auto-start since it's already running
        )

        connection_config = ConnectionConfig(
            host="127.0.0.1",  # LOCAL Gateway
            port=4002,  # Paper port
            client_id=999,  # Test client ID
            timeout=15,  # Connection timeout
            readonly=False,  # We need full access
            reconnect_attempts=3,  # Retry attempts
        )

        print(f"📋 Configuration:")
        print(f"   Host: {connection_config.host}")
        print(f"   Port: {connection_config.port}")
        print(f"   Client ID: {connection_config.client_id}")
        print(f"   Trading Mode: {gateway_config.trading_mode}")

        # Create connection manager
        print(f"\n🔧 Creating ConnectionManager...")
        manager = ConnectionManager(
            connection_config=connection_config, gateway_config=gateway_config
        )

        print("✅ ConnectionManager created successfully")

        # Start the manager
        print(f"\n🚀 Starting ConnectionManager...")
        start_success = manager.start()

        if not start_success:
            print("❌ Failed to start ConnectionManager")
            return False

        print("✅ ConnectionManager started successfully")

        # Test connection
        print(f"\n🔌 Testing connection to IB Gateway...")
        connect_success = manager.connect(
            auto_start_gateway=False
        )  # Don't start Gateway

        if connect_success:
            print("🎉 SUCCESS!")
            print("✅ Connected to IB Gateway successfully")
            print(f"✅ Connection should now be visible in IB Gateway")

            # Get status
            status = manager.get_status()
            print(f"\n📊 Connection Status:")
            print(f"   State: {status.get('state', 'Unknown')}")
            print(f"   Quality: {status.get('quality', 'Unknown')}")
            print(f"   Connected: {status.get('connected', False)}")

            # Keep connection alive for a moment
            print(f"\n⏳ Keeping connection alive for 10 seconds...")
            print(
                f"   Check IB Gateway interface - you should see Client ID {connection_config.client_id}"
            )

            time.sleep(10)

            # Disconnect
            print(f"\n🔌 Disconnecting...")
            disconnect_success = manager.disconnect()

            if disconnect_success:
                print("✅ Disconnected successfully")
            else:
                print("⚠️  Disconnect may have issues")

        else:
            print("❌ FAILED to connect to IB Gateway")
            print("💡 Possible causes:")
            print("   - IB Gateway API not enabled")
            print("   - Wrong host/port configuration")
            print("   - Gateway not accepting connections")
            print("   - Client ID already in use")

            return False

        # Stop manager
        print(f"\n🛑 Stopping ConnectionManager...")
        manager.stop()
        print("✅ ConnectionManager stopped")

        return True

    except ImportError as e:
        print(f"❌ Failed to import ConnectionManager: {e}")
        print("💡 Make sure you're in the correct directory")
        return False

    except Exception as e:
        print(f"❌ Error during connection test: {e}")
        return False


def test_manual_connection():
    """Test manual connection using the existing manager"""

    print(f"\n" + "=" * 60)
    print("🔧 Testing Manual Connection Method")
    print("=" * 60)

    try:
        from SpyderB_Broker.SpyderB05_ConnectionManager import get_connection_manager

        # Get the singleton connection manager
        manager = get_connection_manager()

        if not manager:
            print("❌ Could not get connection manager instance")
            return False

        print("✅ Got connection manager instance")

        # Test manual connect
        print("🔌 Testing manual_connect()...")
        result = manager.manual_connect()

        print(f"📋 Manual connect result:")
        print(f"   Success: {result.get('success', False)}")
        print(f"   Message: {result.get('message', 'No message')}")

        if result.get("success"):
            print("🎉 Manual connection succeeded!")

            # Keep alive briefly
            time.sleep(5)

            # Test manual disconnect
            print("🔌 Testing manual_disconnect()...")
            disconnect_result = manager.manual_disconnect()

            print(f"📋 Manual disconnect result:")
            print(f"   Success: {disconnect_result.get('success', False)}")
            print(f"   Message: {disconnect_result.get('message', 'No message')}")

        return result.get("success", False)

    except Exception as e:
        print(f"❌ Error in manual connection test: {e}")
        return False


def check_ib_gateway_status():
    """Check if IB Gateway is accessible"""

    print(f"\n" + "=" * 60)
    print("🔍 Pre-flight Check: IB Gateway Status")
    print("=" * 60)

    import socket
    import subprocess

    # Check if Gateway process is running
    try:
        result = subprocess.run(
            ["pgrep", "-f", "ibgateway"], capture_output=True, text=True
        )

        if result.returncode == 0:
            pids = result.stdout.strip().split("\n")
            print(f"✅ IB Gateway process running (PID: {', '.join(pids)})")
        else:
            print("❌ IB Gateway process not found")
            return False

    except Exception as e:
        print(f"⚠️  Could not check Gateway process: {e}")

    # Check if ports are accessible
    for port_name, port in [("Paper", 4002), ("Live", 4001)]:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex(("127.0.0.1", port))
            sock.close()

            if result == 0:
                print(f"✅ {port_name} port ({port}) is accessible")
            else:
                print(f"❌ {port_name} port ({port}) is not accessible")

        except Exception as e:
            print(f"⚠️  Error checking {port_name} port: {e}")

    return True


def main():
    """Main test function"""

    print("🕷️  SPYDER - Connection Manager Test Suite")
    print("Testing connection to LOCAL IB Gateway")
    print("=" * 60)

    # Pre-flight checks
    gateway_ok = check_ib_gateway_status()

    if not gateway_ok:
        print("\n❌ Pre-flight checks failed")
        print("💡 Make sure IB Gateway is running with API enabled")
        return 1

    # Test 1: Full connection manager test
    print(f"\n" + "🧪" + " TEST 1: Full Connection Manager")
    success1 = test_existing_connection_manager()

    # Test 2: Manual connection methods
    print(f"\n" + "🧪" + " TEST 2: Manual Connection Methods")
    success2 = test_manual_connection()

    # Results
    print(f"\n" + "=" * 60)
    print("📊 TEST RESULTS")
    print("=" * 60)
    print(f"Test 1 (Full Manager): {'✅ PASS' if success1 else '❌ FAIL'}")
    print(f"Test 2 (Manual Methods): {'✅ PASS' if success2 else '❌ FAIL'}")

    if success1 or success2:
        print(f"\n🎉 SUCCESS! At least one connection method worked")
        print(f"💡 You should have seen Client ID 999 appear in IB Gateway")
        print(f"💡 Now you can use this connection manager in your dashboard")
        return 0
    else:
        print(f"\n❌ All connection tests failed")
        print(f"💡 Check IB Gateway API settings and try again")
        return 1


if __name__ == "__main__":
    sys.exit(main())
