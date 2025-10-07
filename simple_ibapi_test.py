#!/usr/bin/env python3
"""
SPYDER - Simple IBAPI Test (Non-Hanging Version)
===============================================

Simple test of native IBAPI that won't hang.
Uses timeouts and proper error handling to avoid infinite waits.
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
    print("   Install with: pip install ibapi")
    sys.exit(1)


class SimpleIBAPITest(EWrapper, EClient):
    """Simple IBAPI test that won't hang"""

    def __init__(self):
        EClient.__init__(self, self)
        self.connected = False
        self.nextValidId_received = False
        self.managedAccounts_received = False
        self.start_time = None

    def connectAck(self):
        """Connection acknowledged"""
        print("   🔌 Connection acknowledged")
        self.connected = True

    def nextValidId(self, orderId: int):
        """Next valid ID received"""
        print(f"   📋 NextValidId: {orderId}")
        self.nextValidId_received = True

    def managedAccounts(self, accountsList: str):
        """Managed accounts received"""
        print(f"   💼 Accounts: {accountsList}")
        self.managedAccounts_received = True

    def error(
        self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson=""
    ):
        """Error handler"""
        print(f"   ❌ Error {errorCode}: {errorString}")

    def test_connection(self, host, port, timeout=10):
        """Test connection with timeout"""
        print(f"🧪 Testing {host}:{port}")
        print("-" * 30)

        # Test socket first
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((host, port))
            sock.close()

            if result != 0:
                print(f"   ❌ Port not accessible")
                return False
            else:
                print(f"   ✅ Port accessible")
        except Exception as e:
            print(f"   ❌ Socket error: {e}")
            return False

        # Reset status
        self.connected = False
        self.nextValidId_received = False
        self.managedAccounts_received = False

        try:
            print(f"   🚀 Connecting with IBAPI...")
            self.start_time = time.time()

            # Connect
            self.connect(host, port, 1)

            # Start API thread with timeout protection
            api_thread = threading.Thread(target=self.run, daemon=True)
            api_thread.start()

            # Wait for connection with timeout
            wait_time = 0
            while wait_time < timeout and not self.connected:
                time.sleep(0.1)
                wait_time += 0.1

            if self.connected:
                connection_time = time.time() - self.start_time
                print(f"   ✅ Connected in {connection_time:.2f}s")

                # Wait for handshake data (with timeout)
                wait_time = 0
                while wait_time < 5 and not (
                    self.nextValidId_received and self.managedAccounts_received
                ):
                    time.sleep(0.1)
                    wait_time += 0.1

                # Report results
                total_time = time.time() - self.start_time
                print(f"   📊 Results after {total_time:.2f}s:")
                print(f"      Connected: {self.connected}")
                print(f"      NextValidId: {self.nextValidId_received}")
                print(f"      Accounts: {self.managedAccounts_received}")

                # Disconnect
                self.disconnect()

                # Success if we get basic connection + at least one callback
                success = self.connected and (
                    self.nextValidId_received or self.managedAccounts_received
                )

                if success:
                    print(f"   🎉 SUCCESS!")
                    return True
                else:
                    print(f"   ⚠️ PARTIAL - connected but missing handshake data")
                    return False

            else:
                print(f"   ❌ Connection timeout after {timeout}s")
                self.disconnect()
                return False

        except Exception as e:
            print(f"   ❌ Connection failed: {e}")
            try:
                self.disconnect()
            except:
                pass
            return False


def main():
    """Main test"""
    print("🕷️ SPYDER - Simple IBAPI Test")
    print("=" * 40)
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Test targets in order of likelihood
    targets = [
        ("127.0.0.1", 4002, "IB Gateway Paper"),
        ("127.0.0.1", 4001, "IB Gateway Live"),
        ("192.168.1.4", 7497, "Remote TWS Paper"),
        ("192.168.1.4", 7496, "Remote TWS Live"),
    ]

    tester = SimpleIBAPITest()
    working = []

    for host, port, name in targets:
        print(f"Testing {name}")
        success = tester.test_connection(host, port)

        if success:
            working.append((host, port, name))
            print(f"✅ {name}: WORKING")
        else:
            print(f"❌ {name}: FAILED")

        print()

        # Brief pause between tests
        time.sleep(1)

    # Results
    print("=" * 50)
    print("📊 FINAL RESULTS")
    print("=" * 50)

    if working:
        print("🎉 SUCCESS: Found working IBAPI connections!")
        for host, port, name in working:
            print(f"   ✅ {name}: {host}:{port}")

        print()
        print("💡 This proves:")
        print("   • Native IBAPI works (no timeout issues)")
        print("   • The problem was with ib_async library")
        print("   • SPYDER should migrate to native IBAPI")

    else:
        print("❌ No working connections found")
        print("   Check that TWS or Gateway is running")
        print("   and API is properly configured")

    return len(working) > 0


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted")
        sys.exit(1)
