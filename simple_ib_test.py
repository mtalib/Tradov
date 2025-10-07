#!/usr/bin/env python3
"""
Simple IB Connection Test
========================

This script tests IB connection with various parameters to diagnose TWS connectivity issues.
It tries different client IDs, connection timeouts, and provides detailed error information.

Usage:
    python simple_ib_test.py
    python simple_ib_test.py --ip 192.168.1.244 --port 7497
"""

import sys
import time
import argparse
from datetime import datetime

try:
    from ib_async import IB, util

    IB_ASYNC_AVAILABLE = True
except ImportError:
    print("❌ ib_async not available. Install with: pip install ib_async")
    IB_ASYNC_AVAILABLE = False
    sys.exit(1)


class SimpleIBTest:
    def __init__(self, host="127.0.0.1", port=7497):
        self.host = host
        self.port = port
        self.ib = None

    def log_info(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] ℹ️  {message}")

    def log_success(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] ✅ {message}")

    def log_warning(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] ⚠️  {message}")

    def log_error(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] ❌ {message}")

    def test_connection(self, client_id=1, timeout=10, readonly=False):
        """Test IB connection with specific parameters"""

        self.log_info(f"Testing connection to {self.host}:{self.port}")
        self.log_info(f"  Client ID: {client_id}")
        self.log_info(f"  Timeout: {timeout}s")
        self.log_info(f"  Read-only: {readonly}")

        try:
            # Create IB instance
            self.ib = IB()

            # Set up event handlers for debugging
            def onConnected():
                self.log_success("Connected to TWS!")

            def onDisconnected():
                self.log_warning("Disconnected from TWS")

            def onError(reqId, errorCode, errorString, contract):
                self.log_error(f"Error {errorCode}: {errorString}")

            def onTimeout():
                self.log_error("Connection timeout!")

            # Attach event handlers
            self.ib.connectedEvent += onConnected
            self.ib.disconnectedEvent += onDisconnected
            self.ib.errorEvent += onError
            self.ib.timeoutEvent += onTimeout

            # Attempt connection
            self.log_info("Attempting to connect...")

            self.ib.connect(
                host=self.host,
                port=self.port,
                clientId=client_id,
                timeout=timeout,
                readonly=readonly,
            )

            if self.ib.isConnected():
                self.log_success("✅ CONNECTION SUCCESSFUL!")

                # Get some basic info to verify connection
                try:
                    # Request account summary
                    self.log_info("Testing account data request...")
                    accounts = self.ib.managedAccounts()
                    if accounts:
                        self.log_success(f"Found accounts: {accounts}")
                    else:
                        self.log_warning(
                            "No accounts found - this might be normal for paper trading"
                        )

                    # Test market data request
                    self.log_info("Testing market data request...")
                    from ib_async import Stock

                    contract = Stock("AAPL", "SMART", "USD")
                    self.ib.qualifyContracts(contract)
                    self.log_success("Market data test successful")

                except Exception as e:
                    self.log_warning(
                        f"Data requests failed (connection still valid): {e}"
                    )

                # Keep connection alive briefly
                self.log_info("Keeping connection alive for 5 seconds...")
                time.sleep(5)

                # Disconnect
                self.ib.disconnect()
                self.log_success("Disconnected cleanly")
                return True

            else:
                self.log_error("Connection failed - not connected")
                return False

        except Exception as e:
            self.log_error(f"Connection failed with exception: {e}")
            self.log_error(f"Exception type: {type(e).__name__}")

            # Try to disconnect if needed
            if self.ib and self.ib.isConnected():
                try:
                    self.ib.disconnect()
                except:
                    pass

            return False

    def run_comprehensive_test(self):
        """Run multiple connection tests with different parameters"""

        print("🔍 COMPREHENSIVE IB CONNECTION TEST")
        print("=" * 50)
        print(f"Target: {self.host}:{self.port}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)

        # Test scenarios
        test_scenarios = [
            {
                "client_id": 1,
                "timeout": 30,
                "readonly": False,
                "name": "Standard Connection",
            },
            {
                "client_id": 2,
                "timeout": 30,
                "readonly": False,
                "name": "Alternative Client ID",
            },
            {
                "client_id": 999,
                "timeout": 30,
                "readonly": False,
                "name": "High Client ID",
            },
            {
                "client_id": 1,
                "timeout": 60,
                "readonly": False,
                "name": "Extended Timeout",
            },
            {"client_id": 1, "timeout": 30, "readonly": True, "name": "Read-Only Mode"},
        ]

        results = []

        for i, scenario in enumerate(test_scenarios, 1):
            print(f"\n🧪 Test {i}/5: {scenario['name']}")
            print("-" * 30)

            success = self.test_connection(
                client_id=scenario["client_id"],
                timeout=scenario["timeout"],
                readonly=scenario["readonly"],
            )

            results.append(
                {"name": scenario["name"], "success": success, "params": scenario}
            )

            # Wait between tests
            if i < len(test_scenarios):
                self.log_info("Waiting 3 seconds before next test...")
                time.sleep(3)

        # Summary
        print("\n" + "=" * 50)
        print("📊 TEST RESULTS SUMMARY")
        print("=" * 50)

        successful_tests = [r for r in results if r["success"]]
        failed_tests = [r for r in results if not r["success"]]

        print(f"✅ Successful: {len(successful_tests)}/{len(results)}")
        print(f"❌ Failed: {len(failed_tests)}/{len(results)}")

        if successful_tests:
            print("\n✅ SUCCESSFUL CONFIGURATIONS:")
            for result in successful_tests:
                params = result["params"]
                print(
                    f"  • {result['name']}: Client ID {params['client_id']}, "
                    f"Timeout {params['timeout']}s, Read-only: {params['readonly']}"
                )

        if failed_tests:
            print("\n❌ FAILED CONFIGURATIONS:")
            for result in failed_tests:
                params = result["params"]
                print(
                    f"  • {result['name']}: Client ID {params['client_id']}, "
                    f"Timeout {params['timeout']}s, Read-only: {params['readonly']}"
                )

        print("\n🔧 TROUBLESHOOTING TIPS:")

        if len(successful_tests) == 0:
            print("❌ ALL TESTS FAILED - Check TWS configuration:")
            print("  1. TWS is running and logged in")
            print(
                "  2. API > Settings > 'Enable ActiveX and Socket Clients' is ✅ checked"
            )
            print("  3. API > Settings > 'Read-Only API' is ❌ UNCHECKED")
            print("  4. Your client IP (192.168.1.9) is in TWS 'Trusted IPs'")
            print("  5. No firewall blocking the connection")
            print("  6. TWS is not overloaded with other connections")

        elif len(successful_tests) < len(results):
            print("⚠️  PARTIAL SUCCESS - Some configurations work:")
            print("  • Use the successful configuration for your setup")
            print(
                "  • Failed tests might indicate client ID conflicts or timeout issues"
            )

        else:
            print("✅ ALL TESTS PASSED - Your TWS setup is working correctly!")
            print("  • You can use any of the tested configurations")
            print("  • Consider using Client ID 1 with 30s timeout for standard use")

        return len(successful_tests) > 0


def main():
    parser = argparse.ArgumentParser(description="Simple IB Connection Test")
    parser.add_argument("--ip", default="127.0.0.1", help="TWS IP address")
    parser.add_argument("--port", type=int, default=7497, help="TWS port")
    parser.add_argument("--client-id", type=int, default=1, help="Client ID to use")
    parser.add_argument("--timeout", type=int, default=30, help="Connection timeout")
    parser.add_argument(
        "--readonly", action="store_true", help="Use read-only connection"
    )
    parser.add_argument(
        "--comprehensive", action="store_true", help="Run comprehensive test suite"
    )

    args = parser.parse_args()

    if not IB_ASYNC_AVAILABLE:
        print("❌ Cannot run test - ib_async not available")
        sys.exit(1)

    # Create test instance
    test = SimpleIBTest(args.ip, args.port)

    if args.comprehensive:
        # Run comprehensive test
        success = test.run_comprehensive_test()
    else:
        # Run single test
        print(f"🔍 Testing IB connection to {args.ip}:{args.port}")
        print(
            f"Client ID: {args.client_id}, Timeout: {args.timeout}s, Read-only: {args.readonly}"
        )
        print("-" * 50)

        success = test.test_connection(
            client_id=args.client_id, timeout=args.timeout, readonly=args.readonly
        )

    # Exit with appropriate code
    if success:
        print("\n🎉 Test completed successfully!")
        sys.exit(0)
    else:
        print("\n💥 Test failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
