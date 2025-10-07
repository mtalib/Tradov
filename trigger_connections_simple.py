#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Simple Connection Trigger
Simple script to trigger connections using the existing connection manager correctly
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
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def trigger_connections():
    """Trigger connections using the existing SPYDER connection manager"""

    print("🕷️  SPYDER - Simple Connection Trigger")
    print("=" * 50)

    try:
        # Import the existing connection manager classes
        from SpyderB_Broker.SpyderB05_ConnectionManager import (
            ConnectionManager,
            ConnectionConfig,
            GatewayConfig,
            TradingMode,
            get_connection_manager,
        )

        print("✅ Successfully imported ConnectionManager")

        # Create proper configurations
        # GatewayConfig - for gateway settings (no host parameter)
        gateway_config = GatewayConfig()
        gateway_config.port = 4002  # Paper port
        gateway_config.trading_mode = TradingMode.PAPER

        # ConnectionConfig - for connection settings (has host parameter)
        connection_config = ConnectionConfig()
        connection_config.host = "127.0.0.1"  # Local Gateway
        connection_config.port = 4002  # Paper port
        connection_config.client_id = 999  # Test client ID
        connection_config.timeout = 15.0
        connection_config.readonly = False  # Need full access
        connection_config.reconnect_attempts = 3

        print(f"📋 Connection Configuration:")
        print(f"   Host: {connection_config.host}")
        print(f"   Port: {connection_config.port}")
        print(f"   Client ID: {connection_config.client_id}")
        print(f"   Trading Mode: {gateway_config.trading_mode}")

        # Method 1: Try to get existing singleton manager
        print(f"\n🔧 Method 1: Getting singleton connection manager...")

        try:
            manager = get_connection_manager()

            if manager:
                print("✅ Got existing connection manager")

                # Try manual connection
                print("🔌 Attempting manual connection...")
                result = manager.manual_connect()

                print(f"📋 Connection Result:")
                print(f"   Success: {result.get('success', False)}")
                print(f"   Message: {result.get('message', 'No message')}")

                if result.get("success"):
                    print("🎉 SUCCESS! Connection established")
                    print("✅ Client should now be visible in IB Gateway")

                    # Keep connection alive
                    print("⏳ Keeping connection alive for 10 seconds...")
                    time.sleep(10)

                    # Disconnect
                    print("🔌 Disconnecting...")
                    disconnect_result = manager.manual_disconnect()
                    print(f"   Disconnect: {disconnect_result.get('success', False)}")

                    return True

        except Exception as e:
            print(f"⚠️  Method 1 failed: {e}")

        # Method 2: Create new manager instance
        print(f"\n🔧 Method 2: Creating new connection manager...")

        try:
            # Create new manager with our configurations
            manager = ConnectionManager(
                connection_config=connection_config, gateway_config=gateway_config
            )

            print("✅ Created new ConnectionManager")

            # Start the manager
            print("🚀 Starting manager...")
            start_success = manager.start()

            if not start_success:
                print("❌ Failed to start manager")
                return False

            print("✅ Manager started")

            # Attempt connection (don't auto-start gateway since it's running)
            print("🔌 Connecting to IB Gateway...")
            connect_success = manager.connect(auto_start_gateway=False)

            if connect_success:
                print("🎉 SUCCESS! Connected to IB Gateway")
                print(f"✅ Client ID {connection_config.client_id} should be visible")

                # Check connection status
                if hasattr(manager, "is_connected") and manager.is_connected():
                    print("✅ Connection confirmed active")

                    # Get status if available
                    try:
                        status = manager.get_status()
                        print(f"📊 Status: {status}")
                    except:
                        pass

                # Keep alive
                print("⏳ Connection active for 10 seconds...")
                time.sleep(10)

                # Disconnect
                print("🔌 Disconnecting...")
                manager.disconnect()

                # Stop manager
                manager.stop()

                return True

            else:
                print("❌ Failed to connect to IB Gateway")
                print("💡 Check that IB Gateway API is enabled")

                # Stop manager
                manager.stop()
                return False

        except Exception as e:
            print(f"❌ Method 2 failed: {e}")

        # Method 3: Try direct ib_async connection
        print(f"\n🔧 Method 3: Direct ib_async connection...")

        try:
            from ib_async import IB

            print("✅ ib_async available")

            # Create IB instance
            ib = IB()

            print(f"🔌 Connecting directly...")
            ib.connect(
                host="127.0.0.1",
                port=4002,
                clientId=998,  # Different client ID
                timeout=15,
            )

            if ib.isConnected():
                print("🎉 SUCCESS! Direct ib_async connection works")
                print("✅ Client ID 998 should be visible in IB Gateway")

                # Keep alive
                print("⏳ Direct connection active for 10 seconds...")
                time.sleep(10)

                # Disconnect
                ib.disconnect()
                print("🔌 Direct connection disconnected")

                return True
            else:
                print("❌ Direct ib_async connection failed")

        except ImportError:
            print("❌ ib_async not available")
        except Exception as e:
            print(f"❌ Direct connection failed: {e}")

        return False

    except ImportError as e:
        print(f"❌ Failed to import SPYDER modules: {e}")
        print("💡 Make sure you're in the correct directory")
        return False

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def check_gateway_ready():
    """Check if IB Gateway is ready for connections"""

    print("\n🔍 Pre-flight Gateway Check:")
    print("-" * 30)

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
    except:
        print("⚠️  Could not check Gateway process")

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
        print(f"❌ Port check failed: {e}")
        return False


def main():
    """Main function"""

    print("🕷️  SPYDER - Connection Trigger")
    print("Attempting to establish client connections to IB Gateway")
    print("=" * 60)

    # Check if Gateway is ready
    if not check_gateway_ready():
        print("\n❌ IB Gateway is not ready")
        print("💡 Make sure IB Gateway is running with API enabled")
        return 1

    # Trigger connections
    success = trigger_connections()

    print(f"\n" + "=" * 60)
    print("📊 RESULTS")
    print("=" * 60)

    if success:
        print("🎉 SUCCESS!")
        print("✅ At least one connection method worked")
        print("✅ Clients should have appeared in IB Gateway")
        print("\n💡 Next steps:")
        print("   1. Verify connections appeared in IB Gateway interface")
        print("   2. Use the working connection method in your dashboard")
        print("   3. Launch your trading system")
        return 0
    else:
        print("❌ All connection methods failed")
        print("\n💡 Troubleshooting:")
        print("   1. Check IB Gateway API is enabled (Configure → Settings → API)")
        print("   2. Verify 'Enable ActiveX and Socket Clients' is checked")
        print("   3. Ensure socket port is set to 4002")
        print("   4. Add 127.0.0.1 to Trusted IP addresses")
        print("   5. Restart IB Gateway after making changes")
        return 1


if __name__ == "__main__":
    sys.exit(main())
