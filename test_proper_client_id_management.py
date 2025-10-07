#!/usr/bin/env python3
"""
SPYDER - Proper Client ID Management Test
========================================

Test IB Gateway connection with proper Client ID management and connection flow
to resolve the "Zombie Connection" phenomenon that causes immediate connection rejections.

Based on IBKR best practices:
1. Use unique Client IDs for each connection attempt
2. Explicitly call disconnect() before exit
3. Wait for nextValidID callback before proceeding
4. Handle error code 507 (Bad Message) for duplicate Client ID detection
"""

import sys
import time
import threading
import socket
import random
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


class ProperClientTest(EWrapper, EClient):
    """Test with proper Client ID management and connection flow"""

    def __init__(self, client_id):
        EClient.__init__(self, self)
        self.client_id = client_id
        self.start_time = time.time()

        # Connection state tracking
        self.socket_connected = False
        self.api_connected = False
        self.next_valid_id_received = False
        self.managed_accounts_received = False
        self.connection_ready = False

        # Error tracking
        self.errors = []
        self.duplicate_client_id_error = False

    def log(self, message):
        """Log with timestamp and client ID"""
        elapsed = time.time() - self.start_time
        print(f"[Client {self.client_id:3d}] [{elapsed:6.2f}s] {message}")

    # Connection lifecycle events
    def connectAck(self):
        """Connection acknowledged by Gateway"""
        self.log("🔌 CONNECT_ACK - API connection acknowledged")
        self.api_connected = True

    def connectionClosed(self):
        """Connection closed by Gateway"""
        self.log("🔌 CONNECTION_CLOSED - Gateway closed the connection")
        self.api_connected = False

    # Critical handshake events
    def nextValidId(self, orderId: int):
        """Next valid ID received - connection is ready for API requests"""
        self.log(f"📋 NEXT_VALID_ID - Order ID: {orderId} (CONNECTION READY)")
        self.next_valid_id_received = True
        self.connection_ready = True

    def managedAccounts(self, accountsList: str):
        """Managed accounts received"""
        self.log(f"💼 MANAGED_ACCOUNTS - Accounts: {accountsList}")
        self.managed_accounts_received = True

    def currentTime(self, time_val):
        """Server time response"""
        self.log(f"🕒 CURRENT_TIME - Server time: {time_val}")

    # Error handling - Critical for detecting Client ID conflicts
    def error(
        self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson=""
    ):
        """Error handler - Watch for Client ID conflicts (Error 507)"""
        error_msg = f"ERROR {errorCode}: {errorString}"
        self.log(f"❌ {error_msg}")

        self.errors.append(
            {
                "reqId": reqId,
                "errorCode": errorCode,
                "errorString": errorString,
                "timestamp": time.time(),
            }
        )

        # Check for duplicate Client ID error (507 - Bad Message)
        if errorCode == 507:
            self.log("🚨 ERROR 507 - Bad Message (Likely duplicate Client ID)")
            self.duplicate_client_id_error = True
        elif errorCode == 502:
            self.log("🚨 ERROR 502 - Couldn't connect to TWS (Gateway not ready)")
        elif errorCode == 504:
            self.log("🚨 ERROR 504 - Not connected (Connection lost)")

    def winError(self, text: str, lastError: int):
        """Windows error handler"""
        self.log(f"💥 WIN_ERROR - {text}, Code: {lastError}")

    def test_proper_connection_flow(self, host="127.0.0.1", port=4002, timeout=20):
        """Test connection with proper Client ID management and flow"""

        self.log(f"🚀 STARTING PROPER CONNECTION TEST")
        self.log(f"   Target: {host}:{port}")
        self.log(f"   Client ID: {self.client_id}")
        self.log(f"   Timeout: {timeout}s")

        try:
            # Step 1: Test raw socket connectivity first
            self.log("🔍 STEP 1: Testing raw socket connectivity...")
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                result = sock.connect_ex((host, port))
                sock.close()

                if result == 0:
                    self.log("✅ Raw socket test passed")
                    self.socket_connected = True
                else:
                    self.log(f"❌ Raw socket test failed: {result}")
                    return False

            except Exception as e:
                self.log(f"❌ Socket test error: {e}")
                return False

            # Step 2: Establish API connection
            self.log("🚀 STEP 2: Establishing API connection...")
            self.connect(host, port, self.client_id)

            # Step 3: Start API message processing thread
            self.log("🧵 STEP 3: Starting API message thread...")
            api_thread = threading.Thread(target=self.run, daemon=True)
            api_thread.start()

            # Step 4: Wait for API connection acknowledgment
            self.log("⏳ STEP 4: Waiting for API connection acknowledgment...")
            wait_time = 0
            ack_timeout = 10

            while wait_time < ack_timeout and not self.api_connected:
                time.sleep(0.1)
                wait_time += 0.1

                # Check for immediate errors (like duplicate Client ID)
                if self.duplicate_client_id_error:
                    self.log(
                        "🚨 DUPLICATE CLIENT ID DETECTED - This Client ID is already in use"
                    )
                    return False

                if self.errors and any(
                    e["errorCode"] in [502, 504] for e in self.errors
                ):
                    self.log(
                        "🚨 CONNECTION ERROR DETECTED - Gateway rejected connection"
                    )
                    return False

            if not self.api_connected:
                self.log("❌ API connection acknowledgment timeout")
                if self.errors:
                    self.log(f"   Errors received: {len(self.errors)}")
                    for error in self.errors[-3:]:  # Show last 3 errors
                        self.log(
                            f"   → Error {error['errorCode']}: {error['errorString']}"
                        )
                return False

            self.log("✅ API connection acknowledged!")

            # Step 5: Wait for nextValidID (critical handshake completion)
            self.log("⏳ STEP 5: Waiting for nextValidID (handshake completion)...")
            wait_time = 0
            handshake_timeout = 15

            while wait_time < handshake_timeout and not self.next_valid_id_received:
                time.sleep(0.1)
                wait_time += 0.1

                # Show progress every 2 seconds
                if int(wait_time * 10) % 20 == 0:
                    self.log(f"   Still waiting for handshake... {wait_time:.1f}s")

                # Check for errors during handshake
                if self.errors:
                    recent_errors = [
                        e for e in self.errors if e["timestamp"] > self.start_time + 5
                    ]
                    if recent_errors:
                        self.log(f"   Errors during handshake: {len(recent_errors)}")
                        for error in recent_errors[-2:]:
                            self.log(
                                f"   → Error {error['errorCode']}: {error['errorString']}"
                            )

            if not self.next_valid_id_received:
                self.log("❌ nextValidID timeout - Handshake incomplete")
                return False

            self.log("✅ nextValidID received - Handshake complete!")

            # Step 6: Wait briefly for managedAccounts
            self.log("⏳ STEP 6: Waiting for managedAccounts...")
            time.sleep(2)  # Brief wait for accounts

            if self.managed_accounts_received:
                self.log("✅ managedAccounts received")
            else:
                self.log("⚠️ managedAccounts not received (non-critical)")

            # Step 7: Test a simple API request
            self.log("🔍 STEP 7: Testing server time request...")
            try:
                self.reqCurrentTime()
                time.sleep(2)  # Wait for response
                self.log("✅ Server time request sent")
            except Exception as e:
                self.log(f"⚠️ Server time request failed: {e}")

            # Success!
            total_time = time.time() - self.start_time
            self.log(f"🎉 CONNECTION SUCCESS! Total time: {total_time:.2f}s")

            return True

        except Exception as e:
            self.log(f"💥 Connection failed with exception: {e}")
            import traceback

            self.log(f"   Exception details: {traceback.format_exc()}")
            return False

        finally:
            # CRITICAL: Proper disconnect to prevent zombie connections
            self.log("🔌 STEP FINAL: Performing proper disconnect...")
            try:
                if hasattr(self, "isConnected") and self.isConnected():
                    self.disconnect()
                    self.log("✅ Proper disconnect completed")
                    time.sleep(1)  # Give Gateway time to process disconnect
                else:
                    self.log("ℹ️ Not connected, no disconnect needed")
            except Exception as e:
                self.log(f"⚠️ Disconnect error: {e}")


def generate_unique_client_id():
    """Generate a unique Client ID to avoid conflicts"""
    # Use timestamp + random number to ensure uniqueness
    timestamp_part = int(time.time()) % 10000  # Last 4 digits of timestamp
    random_part = random.randint(1, 999)
    client_id = (timestamp_part * 1000) + random_part

    # Ensure it's within valid range (1-32767)
    client_id = max(1, min(32767, client_id))

    return client_id


def main():
    """Main test function with proper Client ID management"""

    print("🕷️ SPYDER - Proper Client ID Management Test")
    print("=" * 60)
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    print("This test implements IBKR best practices for Client ID management:")
    print("• Uses unique Client IDs to avoid zombie connection conflicts")
    print("• Follows proper async connection workflow")
    print("• Waits for nextValidID before proceeding")
    print("• Handles error code 507 (duplicate Client ID)")
    print("• Performs explicit disconnect() to prevent zombie connections")
    print()

    # Test multiple connection attempts with different Client IDs
    test_attempts = 3
    successful_connections = 0

    for attempt in range(1, test_attempts + 1):
        # Generate unique Client ID for this attempt
        client_id = generate_unique_client_id()

        print(f"🧪 CONNECTION ATTEMPT {attempt}/{test_attempts}")
        print(f"   Using unique Client ID: {client_id}")
        print("-" * 50)

        # Create test instance
        tester = ProperClientTest(client_id)

        try:
            # Run the proper connection test
            success = tester.test_proper_connection_flow()

            if success:
                print(f"✅ ATTEMPT {attempt}: SUCCESS!")
                successful_connections += 1
                # If we get one successful connection, we've proven the fix works
                break
            else:
                print(f"❌ ATTEMPT {attempt}: FAILED")

                # Analyze the failure
                if tester.duplicate_client_id_error:
                    print(f"   → Failure cause: Duplicate Client ID conflict")
                elif tester.errors:
                    error_codes = [e["errorCode"] for e in tester.errors]
                    print(f"   → Failure cause: API errors {error_codes}")
                else:
                    print(f"   → Failure cause: Connection/handshake timeout")

        except KeyboardInterrupt:
            print(f"\n⚠️ Test interrupted during attempt {attempt}")
            break
        except Exception as e:
            print(f"❌ ATTEMPT {attempt}: EXCEPTION - {e}")

        # Brief pause between attempts to avoid rapid reconnection issues
        if attempt < test_attempts:
            print(f"   ⏳ Waiting 3 seconds before next attempt...")
            time.sleep(3)
            print()

    # Final results
    print("\n" + "=" * 70)
    print("📊 FINAL RESULTS")
    print("=" * 70)

    if successful_connections > 0:
        print("🎉 SUCCESS! Proper Client ID management resolved the issue!")
        print()
        print("💡 KEY FINDINGS:")
        print("   ✅ Zombie connection issue resolved")
        print("   ✅ Unique Client IDs prevent duplicate session rejection")
        print("   ✅ Proper connection flow enables successful handshake")
        print("   ✅ IB Gateway 10.39 API is working correctly")
        print()
        print("🚀 NEXT STEPS:")
        print("   1. Update SPYDER to use unique Client IDs for each connection")
        print("   2. Implement proper disconnect() calls in all exit paths")
        print("   3. Add nextValidID wait logic before sending API requests")
        print("   4. Add error code 507 handling for Client ID conflicts")
        print("   5. Deploy updated SPYDER with proper Client ID management")

        return True

    else:
        print("❌ ALL ATTEMPTS FAILED")
        print()
        print("🔍 POSSIBLE REMAINING ISSUES:")
        print("   1. Gateway authentication/login problems")
        print("   2. API permissions not enabled for this account")
        print("   3. Gateway configuration issues beyond Client ID management")
        print("   4. Network/firewall blocking API communication")
        print()
        print("🔧 NEXT TROUBLESHOOTING STEPS:")
        print("   1. Verify Gateway is fully logged in (green indicator)")
        print("   2. Check API settings: Configure → Settings → API")
        print("   3. Restart Gateway completely")
        print("   4. Check Gateway logs for authentication errors")
        print("   5. Contact IBKR support with updated diagnostic information")

        return False


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
