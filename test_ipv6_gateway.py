#!/usr/bin/env python3
"""
SPYDER - IPv6 Gateway Connection Test
====================================

Test Gateway connection using both IPv4 and IPv6 addresses.
The Gateway might be listening on IPv6 only.
"""

import sys
import time
import threading
import socket
from datetime import datetime

# Import native IBAPI
try:
    from ibapi.client import EClient
    from ibapi.wrapper import EWrapper

    print("✅ Native IBAPI imported successfully")
except ImportError as e:
    print(f"❌ Failed to import IBAPI: {e}")
    sys.exit(1)


class IPv6GatewayTest(EWrapper, EClient):
    """Gateway test for both IPv4 and IPv6"""

    def __init__(self):
        EClient.__init__(self, self)
        self.connected = False
        self.nextValidId_received = False
        self.managedAccounts_received = False
        self.start_time = time.time()

    def log(self, message):
        """Log with timestamp"""
        elapsed = time.time() - self.start_time
        print(f"[{elapsed:6.2f}s] {message}")

    # Connection events
    def connectAck(self):
        self.log("🔌 CONNECTACK - Connection acknowledged")
        self.connected = True

    def nextValidId(self, orderId: int):
        self.log(f"📋 NEXTVALIDID - Order ID: {orderId}")
        self.nextValidId_received = True

    def managedAccounts(self, accountsList: str):
        self.log(f"💼 MANAGEDACCOUNTS - Accounts: {accountsList}")
        self.managedAccounts_received = True

    def error(
        self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson=""
    ):
        self.log(f"❌ ERROR - ReqId: {reqId}, Code: {errorCode}, Msg: {errorString}")

    def test_socket_connection(self, host, port):
        """Test raw socket connection"""
        try:
            # Determine address family
            if ":" in host:
                family = socket.AF_INET6
                self.log(f"🔍 Testing IPv6 socket to {host}:{port}")
            else:
                family = socket.AF_INET
                self.log(f"🔍 Testing IPv4 socket to {host}:{port}")

            sock = socket.socket(family, socket.SOCK_STREAM)
            sock.settimeout(3)

            start_time = time.time()
            result = sock.connect_ex((host, port))
            connect_time = time.time() - start_time

            sock.close()

            if result == 0:
                self.log(f"✅ Socket connection successful ({connect_time:.3f}s)")
                return True
            else:
                self.log(f"❌ Socket connection failed: error {result}")
                return False
        except Exception as e:
            self.log(f"❌ Socket test error: {e}")
            return False

    def test_api_connection(self, host, port, client_id, timeout=10):
        """Test API connection with timeout"""
        self.log(f"🚀 Testing API connection to {host}:{port}")

        # Reset state
        self.connected = False
        self.nextValidId_received = False
        self.managedAccounts_received = False

        try:
            # Connect
            self.connect(host, port, client_id)

            # Start API thread
            api_thread = threading.Thread(target=self.run, daemon=True)
            api_thread.start()

            # Wait for connection with timeout
            wait_time = 0
            while wait_time < timeout and not self.connected:
                time.sleep(0.1)
                wait_time += 0.1

            if not self.connected:
                self.log("❌ Connection timeout")
                self.disconnect()
                return False

            self.log("✅ Connected! Waiting for handshake...")

            # Wait for handshake (nextValidId)
            wait_time = 0
            handshake_timeout = 15

            while wait_time < handshake_timeout and not self.nextValidId_received:
                time.sleep(0.1)
                wait_time += 0.1

                # Progress indicator
                if int(wait_time * 10) % 30 == 0:
                    self.log(f"   Waiting for handshake... {wait_time:.1f}s")

            if self.nextValidId_received:
                self.log("✅ Handshake successful!")

                # Wait briefly for managedAccounts
                time.sleep(2)

                success = True
            else:
                self.log("❌ Handshake timeout!")
                success = False

            # Clean disconnect
            self.disconnect()
            time.sleep(1)

            return success

        except Exception as e:
            self.log(f"❌ API connection failed: {e}")
            try:
                self.disconnect()
            except:
                pass
            return False


def main():
    """Main test function"""
    print("🕷️ SPYDER - IPv6 Gateway Test")
    print("=" * 40)
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Test targets - IPv4 and IPv6
    targets = [
        ("127.0.0.1", 4002, "IPv4 Localhost", 50),
        ("::1", 4002, "IPv6 Localhost", 51),
        ("localhost", 4002, "Hostname Localhost", 52),
    ]

    tester = IPv6GatewayTest()
    working_connections = []

    for host, port, description, client_id in targets:
        print(f"\n📡 Testing {description} ({host}:{port})")
        print("-" * 50)

        # Test socket first
        if not tester.test_socket_connection(host, port):
            print(f"❌ {description}: Socket connection failed")
            continue

        # Test API connection
        if tester.test_api_connection(host, port, client_id):
            print(f"✅ {description}: API connection successful!")
            working_connections.append((host, port, description))
            # Success! We can stop here
            break
        else:
            print(f"❌ {description}: API handshake failed")

    # Results
    print("\n" + "=" * 60)
    print("📊 FINAL RESULTS")
    print("=" * 60)

    if working_connections:
        print("🎉 SUCCESS! Found working Gateway connection:")
        for host, port, desc in working_connections:
            print(f"   ✅ {desc}: {host}:{port}")

        print("\n💡 SOLUTION FOUND:")
        print("   • The handshake timeout issue is resolved!")
        print("   • IB Gateway 10.39 is working correctly")
        print("   • Use the working host/port combination above")

        return True
    else:
        print("❌ ALL CONNECTIONS FAILED")
        print("\n🔧 TROUBLESHOOTING:")
        print("   1. Verify Gateway is fully logged in")
        print("   2. Check API settings are properly configured")
        print("   3. Ensure no firewall is blocking connections")
        print("   4. Try restarting Gateway completely")
        print("   5. Check Gateway logs for authentication errors")

        return False


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted")
        sys.exit(1)
