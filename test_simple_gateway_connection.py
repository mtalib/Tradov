#!/usr/bin/env python3
"""
Simple IB Gateway Connection Test
Test basic connectivity to IB Gateway to diagnose client visibility issues
"""

import time
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from ibapi.client import EClient
    from ibapi.wrapper import EWrapper
    from ibapi.contract import Contract
    import threading

    print("✅ IB API imports successful")
except ImportError as e:
    print(f"❌ Failed to import IB API: {e}")
    print("Installing ibapi...")
    import subprocess

    subprocess.check_call([sys.executable, "-m", "pip", "install", "ibapi"])
    from ibapi.client import EClient
    from ibapi.wrapper import EWrapper
    from ibapi.contract import Contract
    import threading


class SimpleTestWrapper(EWrapper):
    """Simple wrapper to handle IB API callbacks"""

    def __init__(self):
        EWrapper.__init__(self)
        self.connected = False
        self.next_order_id = None
        self.connection_time = None

    def connectAck(self):
        """Called when connection is acknowledged"""
        print("🔗 Connection acknowledged by IB Gateway")
        self.connected = True
        self.connection_time = time.time()

    def connectionClosed(self):
        """Called when connection is closed"""
        print("🔌 Connection closed")
        self.connected = False

    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        """Handle errors"""
        if errorCode == 2104:
            print(f"📡 Market data farm connection: {errorString}")
        elif errorCode == 2106:
            print(f"📡 HMDS data farm connection: {errorString}")
        elif errorCode == 2158:
            print(f"📊 Secure Gateway connection: {errorString}")
        elif errorCode in [2100, 2101, 2102, 2103]:
            print(f"ℹ️  System message: {errorString}")
        else:
            print(f"⚠️  Error {errorCode}: {errorString}")

    def nextValidId(self, orderId: int):
        """Receive next valid order ID"""
        print(f"🆔 Next valid order ID: {orderId}")
        self.next_order_id = orderId


class SimpleTestClient(EClient):
    """Simple client for testing IB Gateway connection"""

    def __init__(self, wrapper):
        EClient.__init__(self, wrapper)
        self.wrapper = wrapper


def test_gateway_connection():
    """Test connection to IB Gateway"""

    print("🕷️  SPYDER - Simple IB Gateway Connection Test")
    print("=" * 50)

    # Configuration
    host = "127.0.0.1"
    paper_port = 4002
    live_port = 4001
    client_id = 999  # High client ID to avoid conflicts

    # Test paper port first
    for port_name, port in [("Paper", paper_port), ("Live", live_port)]:
        print(f"\n🔍 Testing {port_name} connection...")
        print(f"   Host: {host}")
        print(f"   Port: {port}")
        print(f"   Client ID: {client_id}")

        # Create wrapper and client
        wrapper = SimpleTestWrapper()
        client = SimpleTestClient(wrapper)

        try:
            # Attempt connection
            print("🔌 Attempting to connect...")
            client.connect(host, port, client_id)

            # Start the socket in a separate thread
            api_thread = threading.Thread(target=client.run, daemon=True)
            api_thread.start()

            # Wait for connection
            timeout = 10
            start_time = time.time()

            while not wrapper.connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)

            if wrapper.connected:
                print(f"✅ Successfully connected to {port_name} port!")
                print(
                    f"⏱️  Connection established in {wrapper.connection_time - start_time:.2f}s"
                )

                # Wait a moment for initial messages
                time.sleep(2)

                # Check if we got next valid order ID
                if wrapper.next_order_id is not None:
                    print(f"✅ Received next valid order ID: {wrapper.next_order_id}")
                else:
                    print("⚠️  No next valid order ID received yet")

                # Disconnect cleanly
                print("🔌 Disconnecting...")
                client.disconnect()
                time.sleep(1)

                return True, port_name, port

            else:
                print(f"❌ Failed to connect to {port_name} port within {timeout}s")
                client.disconnect()

        except Exception as e:
            print(f"❌ Exception during {port_name} connection: {e}")
            try:
                client.disconnect()
            except:
                pass

        # Wait before trying next port
        time.sleep(1)

    return False, None, None


def check_gateway_process():
    """Check if IB Gateway is running"""
    import subprocess

    print("\n🔍 Checking IB Gateway process...")

    try:
        # Check for Java processes that look like IB Gateway
        result = subprocess.run(["ps", "aux"], capture_output=True, text=True)

        gateway_processes = []
        for line in result.stdout.split("\n"):
            if "java" in line.lower() and (
                "gateway" in line.lower() or "ibgateway" in line.lower()
            ):
                gateway_processes.append(line)

        if gateway_processes:
            print(f"✅ Found {len(gateway_processes)} IB Gateway process(es)")
            for i, process in enumerate(gateway_processes, 1):
                # Show just the relevant part of the command
                parts = process.split()
                if len(parts) > 10:
                    print(f"   Process {i}: ...{' '.join(parts[-3:])}")
                else:
                    print(f"   Process {i}: {' '.join(parts[1:6])}...")
            return True
        else:
            print("❌ No IB Gateway processes found")
            return False

    except Exception as e:
        print(f"⚠️  Could not check processes: {e}")
        return False


def check_ports():
    """Check if IB Gateway ports are accessible"""
    import socket

    print("\n🔍 Checking IB Gateway ports...")

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


def main():
    """Main test function"""

    print("🕷️  SPYDER - IB Gateway Diagnostic Test")
    print("=" * 50)
    print(f"⏰ Test started at: {datetime.now().strftime('%H:%M:%S')}")

    # Step 1: Check if Gateway process is running
    process_running = check_gateway_process()

    # Step 2: Check if ports are accessible
    check_ports()

    # Step 3: Test actual API connection
    if process_running:
        success, port_name, port = test_gateway_connection()

        if success:
            print(f"\n🎉 SUCCESS!")
            print(f"   ✅ IB Gateway is running and accessible")
            print(f"   ✅ Successfully connected to {port_name} port ({port})")
            print(f"   ✅ Client should be visible in IB Gateway")
            print(f"\n💡 Next steps:")
            print(f"   1. Check IB Gateway interface for active client connections")
            print(f"   2. Run SPYDER Universal 8-Client Data Manager")
            print(f"   3. Launch trading dashboard")
            return 0
        else:
            print(f"\n❌ CONNECTION FAILED")
            print(f"   ⚠️  IB Gateway is running but API connection failed")
            print(f"   💡 Possible causes:")
            print(f"      - IB Gateway API is not enabled")
            print(f"      - Socket port is not configured")
            print(f"      - Firewall blocking connections")
            print(f"      - IB Gateway is in wrong mode")
            return 1
    else:
        print(f"\n❌ IB GATEWAY NOT RUNNING")
        print(f"   💡 Please start IB Gateway first")
        return 1


if __name__ == "__main__":
    from datetime import datetime

    exit_code = main()
    print(f"\n⏰ Test completed at: {datetime.now().strftime('%H:%M:%S')}")
    sys.exit(exit_code)
