#!/usr/bin/env python3
"""
SPYDER - Minimal Gateway Connection Test
========================================

Ultra-minimal test to diagnose Gateway handshake issues.
This script uses the most basic IBAPI connection with detailed logging.
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


class MinimalGatewayTest(EWrapper, EClient):
    """Minimal Gateway test with maximum logging"""

    def __init__(self):
        EClient.__init__(self, self)
        self.connected = False
        self.nextValidId_received = False
        self.managedAccounts_received = False
        self.error_received = False
        self.start_time = time.time()

    def log(self, message):
        """Log with timestamp"""
        elapsed = time.time() - self.start_time
        print(f"[{elapsed:6.2f}s] {message}")

    # Connection events
    def connectAck(self):
        self.log("🔌 CONNECTACK - Connection acknowledged by Gateway")
        self.connected = True

    def connectionClosed(self):
        self.log("🔌 CONNECTION CLOSED")

    # Handshake events
    def nextValidId(self, orderId: int):
        self.log(f"📋 NEXTVALIDID - Order ID: {orderId}")
        self.nextValidId_received = True

    def managedAccounts(self, accountsList: str):
        self.log(f"💼 MANAGEDACCOUNTS - Accounts: {accountsList}")
        self.managedAccounts_received = True

    def currentTime(self, time_val):
        self.log(f"🕒 CURRENTTIME - Server time: {time_val}")

    # Error handling
    def error(
        self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson=""
    ):
        self.log(f"❌ ERROR - ReqId: {reqId}, Code: {errorCode}, Msg: {errorString}")
        self.error_received = True

    def winError(self, text: str, lastError: int):
        self.log(f"💥 WIN_ERROR - {text}, Code: {lastError}")

    def test_connection_detailed(self):
        """Test connection with detailed step-by-step logging"""

        print("🕷️ SPYDER - Minimal Gateway Test")
        print("=" * 50)
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        host = "127.0.0.1"
        port = 4002
        client_id = 42  # Use a different client ID

        # Step 1: Test socket connectivity
        self.log("🔍 STEP 1: Testing socket connectivity...")
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((host, port))
            sock.close()

            if result == 0:
                self.log("✅ Socket connection successful")
            else:
                self.log(f"❌ Socket connection failed: {result}")
                return False
        except Exception as e:
            self.log(f"❌ Socket test error: {e}")
            return False

        # Step 2: Initialize IBAPI connection
        self.log(f"🚀 STEP 2: Connecting to {host}:{port} with client ID {client_id}")

        try:
            # Connect
            self.connect(host, port, client_id)

            # Start API message processing thread
            self.log("🧵 Starting API thread...")
            api_thread = threading.Thread(target=self.run, daemon=True)
            api_thread.start()

            # Step 3: Wait for connection acknowledgment
            self.log("⏳ STEP 3: Waiting for connection acknowledgment...")
            wait_time = 0
            timeout = 10

            while wait_time < timeout and not self.connected:
                time.sleep(0.1)
                wait_time += 0.1

            if self.connected:
                self.log("✅ Connection acknowledged!")
            else:
                self.log("❌ Connection acknowledgment timeout")
                return False

            # Step 4: Wait for nextValidId (critical handshake message)
            self.log("⏳ STEP 4: Waiting for nextValidId...")
            wait_time = 0
            timeout = 15

            while wait_time < timeout and not self.nextValidId_received:
                time.sleep(0.1)
                wait_time += 0.1

                # Show progress every 2 seconds
                if int(wait_time * 10) % 20 == 0:
                    self.log(f"   Still waiting... {wait_time:.1f}s")

            if self.nextValidId_received:
                self.log("✅ NextValidId received!")
            else:
                self.log("❌ NextValidId timeout - THIS IS THE HANDSHAKE BUG!")
                return False

            # Step 5: Wait for managedAccounts
            self.log("⏳ STEP 5: Waiting for managedAccounts...")
            wait_time = 0
            timeout = 5

            while wait_time < timeout and not self.managedAccounts_received:
                time.sleep(0.1)
                wait_time += 0.1

            if self.managedAccounts_received:
                self.log("✅ ManagedAccounts received!")
            else:
                self.log("⚠️ ManagedAccounts timeout (less critical)")

            # Step 6: Test a simple request
            self.log("🔍 STEP 6: Testing server time request...")
            try:
                self.reqCurrentTime()
                time.sleep(2)  # Give it time to respond
                self.log("✅ Server time request sent")
            except Exception as e:
                self.log(f"❌ Server time request failed: {e}")

            # Step 7: Summary
            total_time = time.time() - self.start_time
            self.log(f"📊 FINAL RESULTS after {total_time:.2f}s:")
            self.log(f"   Connected: {self.connected}")
            self.log(f"   NextValidId: {self.nextValidId_received}")
            self.log(f"   ManagedAccounts: {self.managedAccounts_received}")
            self.log(f"   Errors: {self.error_received}")

            # Disconnect cleanly
            self.log("🔌 Disconnecting...")
            self.disconnect()

            # Return success if we got the critical handshake messages
            success = self.connected and self.nextValidId_received

            if success:
                print()
                print("🎉 SUCCESS! Gateway API connection is working!")
                print("   The handshake timeout bug appears to be resolved.")
                return True
            else:
                print()
                print("❌ FAILED! Gateway handshake is still timing out.")
                print("   This suggests a configuration or authentication issue.")
                return False

        except Exception as e:
            self.log(f"💥 Connection failed with exception: {e}")
            import traceback

            traceback.print_exc()
            return False


def main():
    """Main test function"""
    try:
        tester = MinimalGatewayTest()
        success = tester.test_connection_detailed()

        if not success:
            print()
            print("🔧 TROUBLESHOOTING SUGGESTIONS:")
            print("1. Check Gateway GUI - is it logged in?")
            print("2. Gateway settings: Configure → Settings → API")
            print("3. Verify 'Enable ActiveX and Socket Clients' is checked")
            print("4. Check socket port is set to 4002")
            print("5. Verify account is logged in (not just connected)")
            print("6. Try restarting Gateway completely")
            print("7. Check for any error dialogs in Gateway GUI")

        return success

    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
        return False
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
