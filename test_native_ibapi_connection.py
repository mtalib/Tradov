#!/usr/bin/env python3
"""
Native IBAPI Connection Test Script
==================================

This script tests TWS API connection using the native ibapi library instead of ib_async.
Research shows native ibapi has 85% success rate where ib_async fails.

Based on research findings from:
- Claude-TWS-API-Research.md
- Gemini-TWS API Handshake Troubleshooting Research.md
- Perplexity TWS API research

Usage:
    python test_native_ibapi_connection.py --windows-ip 192.168.1.250 --port 7497

Author: Spyder Trading System
Version: 1.0
Date: 2025-10-04
"""

import argparse
import time
import threading
from datetime import datetime
from typing import Optional

try:
    from ibapi.client import EClient
    from ibapi.wrapper import EWrapper
    from ibapi.contract import Contract
except ImportError:
    print("❌ Native ibapi library not installed!")
    print("Install with: pip install ibapi")
    exit(1)


class SpyderIBApp(EWrapper, EClient):
    """
    Native IBAPI test application combining EWrapper and EClient.

    This approach bypasses ib_async timing issues and provides direct
    control over the API connection and message handling.
    """

    def __init__(self):
        EClient.__init__(self, self)

        # Connection state tracking
        self.connected = False
        self.next_valid_id = None
        self.managed_accounts = []
        self.connection_time = None
        self.errors = []

        # Test results
        self.handshake_successful = False
        self.api_ready = False

    def error(
        self,
        reqId: int,
        errorCode: int,
        errorString: str,
        advancedOrderRejectJson: str = "",
    ):
        """Handle API errors and warnings."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        error_msg = f"[{timestamp}] Error {errorCode}: {errorString}"

        if reqId != -1:
            error_msg += f" (ReqId: {reqId})"

        print(f"   ⚠️ {error_msg}")
        self.errors.append(
            {
                "timestamp": timestamp,
                "reqId": reqId,
                "errorCode": errorCode,
                "errorString": errorString,
            }
        )

        # Critical errors that indicate connection failure
        critical_errors = [502, 503, 504, 1100, 1101, 1102]
        if errorCode in critical_errors:
            print(f"   🚨 Critical error detected: {errorCode}")
            self.connected = False

    def connectAck(self):
        """Called when connection is acknowledged by TWS."""
        self.connection_time = datetime.now()
        print(
            f"   ✅ Connection acknowledged at {self.connection_time.strftime('%H:%M:%S')}"
        )
        self.handshake_successful = True

    def nextValidId(self, orderId: int):
        """Called when TWS sends the next valid order ID - indicates API is ready."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"   ✅ API Ready! Next valid order ID: {orderId} at {timestamp}")

        self.connected = True
        self.next_valid_id = orderId
        self.api_ready = True

        # Calculate connection time if handshake was successful
        if self.connection_time:
            duration = (datetime.now() - self.connection_time).total_seconds()
            print(f"   ⏱️ Full API initialization took {duration:.2f} seconds")

    def managedAccounts(self, accountsList: str):
        """Called when TWS sends managed accounts list."""
        accounts = accountsList.split(",") if accountsList else []
        self.managed_accounts = [acc.strip() for acc in accounts if acc.strip()]

        print(f"   📋 Managed accounts received: {len(self.managed_accounts)} accounts")
        for i, account in enumerate(self.managed_accounts, 1):
            print(f"      {i}. {account}")

    def connectionClosed(self):
        """Called when connection is closed."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"   🔌 Connection closed at {timestamp}")
        self.connected = False
        self.api_ready = False

    def currentTime(self, time: int):
        """Called when TWS sends current time - used for connectivity test."""
        readable_time = datetime.fromtimestamp(time).strftime("%Y-%m-%d %H:%M:%S")
        print(f"   🕐 TWS Server Time: {readable_time}")


class NativeIBAPITester:
    """
    Comprehensive native ibapi connection tester.

    Tests all aspects of TWS API connection using the native library
    to bypass known ib_async issues.
    """

    def __init__(self, host: str, port: int, client_id: int = 1):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.app = SpyderIBApp()
        self.api_thread: Optional[threading.Thread] = None
        self.start_time = datetime.now()

    def print_header(self):
        """Print test header with configuration details."""
        print("=" * 80)
        print("🚀 NATIVE IBAPI CONNECTION TEST")
        print("=" * 80)
        print(f"📅 Started: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🖥️ Target: {self.host}:{self.port}")
        print(f"🆔 Client ID: {self.client_id}")
        print(f"📚 Using native ibapi library (not ib_async)")
        print("=" * 80)
        print()

    def test_connection(self, timeout: int = 60) -> bool:
        """
        Test connection to TWS using native ibapi.

        Args:
            timeout: Maximum time to wait for connection

        Returns:
            True if connection successful, False otherwise
        """
        print("🔗 TESTING NATIVE IBAPI CONNECTION")
        print("-" * 50)

        try:
            # Step 1: Initiate connection
            print(
                f"🤝 Connecting to {self.host}:{self.port} with clientId {self.client_id}..."
            )
            start_time = time.time()

            self.app.connect(self.host, self.port, self.client_id)

            # Step 2: Start API message processing thread
            print("🧵 Starting API message processing thread...")
            self.api_thread = threading.Thread(target=self.app.run, daemon=True)
            self.api_thread.start()

            # Step 3: Wait for connection establishment
            print(f"⏳ Waiting for API connection (timeout: {timeout}s)...")

            elapsed = 0
            while not self.app.api_ready and elapsed < timeout:
                time.sleep(0.1)
                elapsed = time.time() - start_time

                # Show progress every 5 seconds
                if int(elapsed) % 5 == 0 and elapsed > 0:
                    print(f"   ⏱️ Elapsed: {elapsed:.0f}s - Still waiting...")

            # Step 4: Evaluate results
            total_time = time.time() - start_time

            if self.app.api_ready:
                print(f"   ✅ Connection successful in {total_time:.2f} seconds!")
                return True
            else:
                print(f"   ❌ Connection failed after {total_time:.2f} seconds")
                return False

        except Exception as e:
            print(f"   🚨 Connection exception: {e}")
            return False

    def test_basic_functionality(self) -> bool:
        """
        Test basic API functionality after connection.

        Returns:
            True if basic functions work, False otherwise
        """
        if not self.app.connected:
            print("❌ Cannot test functionality - not connected")
            return False

        print("\n🧪 TESTING BASIC API FUNCTIONALITY")
        print("-" * 50)

        try:
            # Test 1: Request current time
            print("🕐 Requesting server time...")
            self.app.reqCurrentTime()
            time.sleep(2)  # Give time for response

            # Test 2: Request managed accounts (already received during connection)
            if self.app.managed_accounts:
                print(
                    f"✅ Account access confirmed: {len(self.app.managed_accounts)} accounts"
                )
            else:
                print("⚠️ No managed accounts received")

            # Test 3: Check next valid order ID
            if self.app.next_valid_id:
                print(f"✅ Order management ready: Next ID = {self.app.next_valid_id}")
            else:
                print("⚠️ No valid order ID received")

            print("✅ Basic functionality test completed")
            return True

        except Exception as e:
            print(f"❌ Functionality test failed: {e}")
            return False

    def disconnect(self):
        """Clean disconnection from TWS."""
        print("\n🔌 DISCONNECTING FROM TWS")
        print("-" * 30)

        try:
            if self.app.isConnected():
                self.app.disconnect()
                print("✅ Disconnected successfully")
            else:
                print("ℹ️ Already disconnected")
        except Exception as e:
            print(f"⚠️ Disconnect error: {e}")

    def print_summary(self):
        """Print comprehensive test summary."""
        print("\n" + "=" * 80)
        print("📋 NATIVE IBAPI TEST SUMMARY")
        print("=" * 80)

        duration = (datetime.now() - self.start_time).total_seconds()
        print(f"⏱️ Total test duration: {duration:.1f} seconds")
        print(f"🖥️ Target: {self.host}:{self.port}")
        print(f"🆔 Client ID: {self.client_id}")
        print()

        # Connection results
        print("🔗 Connection Results:")
        if self.app.handshake_successful:
            print("   Handshake: ✅ Successful")
        else:
            print("   Handshake: ❌ Failed")

        if self.app.api_ready:
            print("   API Ready: ✅ Yes")
        else:
            print("   API Ready: ❌ No")

        if self.app.next_valid_id:
            print(f"   Next Order ID: ✅ {self.app.next_valid_id}")
        else:
            print("   Next Order ID: ❌ Not received")

        print(
            f"   Managed Accounts: {'✅' if self.app.managed_accounts else '❌'} {len(self.app.managed_accounts)} accounts"
        )

        # Error summary
        if self.app.errors:
            print(f"\n⚠️ Errors Encountered ({len(self.app.errors)}):")
            for error in self.app.errors[-5:]:  # Show last 5 errors
                print(
                    f"   [{error['timestamp']}] {error['errorCode']}: {error['errorString']}"
                )
            if len(self.app.errors) > 5:
                print(f"   ... and {len(self.app.errors) - 5} more errors")
        else:
            print("\n✅ No errors encountered")

        # Overall assessment
        print(f"\n🎯 Overall Result:")
        if self.app.api_ready:
            print("   ✅ SUCCESS - Native ibapi connection working!")
            print("   🚀 Ready to migrate Spyder system to native ibapi")
        else:
            print("   ❌ FAILED - Native ibapi also experiencing issues")
            print("   🔍 Problem may be deeper than library choice")

        print("=" * 80)


def main():
    """Main test function."""
    parser = argparse.ArgumentParser(description="Native IBAPI Connection Test")
    parser.add_argument(
        "--windows-ip", required=True, help="IP address of Windows computer running TWS"
    )
    parser.add_argument(
        "--port", type=int, default=7497, help="TWS port (default: 7497)"
    )
    parser.add_argument(
        "--client-id", type=int, default=1, help="Client ID (default: 1)"
    )
    parser.add_argument(
        "--timeout", type=int, default=60, help="Connection timeout in seconds"
    )
    parser.add_argument(
        "--test-functionality",
        action="store_true",
        help="Test basic API functionality after connection",
    )

    args = parser.parse_args()

    # Create tester
    tester = NativeIBAPITester(args.windows_ip, args.port, args.client_id)

    try:
        # Run tests
        tester.print_header()

        # Main connection test
        connection_success = tester.test_connection(args.timeout)

        # Optional functionality test
        if connection_success and args.test_functionality:
            tester.test_basic_functionality()

        # Always print summary
        tester.print_summary()

        # Clean disconnect
        tester.disconnect()

        # Exit with appropriate code
        exit(0 if connection_success else 1)

    except KeyboardInterrupt:
        print("\n\n⏹️ Test interrupted by user")
        tester.disconnect()
        exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        tester.disconnect()
        exit(1)


if __name__ == "__main__":
    main()
