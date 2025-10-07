#!/usr/bin/env python3
"""
Focused Handshake Timeout Test for Gateway 10.37
Tests the specific handshake timeout issue that was affecting data flow
"""

import sys
import time
import socket
import threading
from datetime import datetime

sys.path.append("/home/adam/Projects/Spyder")

try:
    from ib_async import IB, util, Contract, Stock

    print("✅ Using ib_async 1.0.3 for Gateway 10.37 compatibility")
except ImportError as e:
    print(f"❌ Error importing ib_async: {e}")
    sys.exit(1)


class HandshakeTimeoutTester:
    """Test handshake timeouts specifically"""

    def __init__(self):
        self.connection_attempts = 0
        self.successful_connections = 0
        self.timeout_errors = 0
        self.handshake_times = []
        self.data_received = 0

    def test_single_connection(self, client_id, timeout_seconds=10):
        """Test a single connection with timeout monitoring"""
        print(f"\n🔄 Testing connection with client ID {client_id}")
        print(f"⏱️  Timeout set to {timeout_seconds} seconds")

        ib = IB()
        start_time = time.time()

        try:
            # Set shorter timeout to catch issues faster
            ib.client.setTimeout(timeout_seconds)

            print(f"   📡 Connecting to 127.0.0.1:4002...")
            ib.connect("127.0.0.1", 4002, clientId=client_id, timeout=timeout_seconds)

            connect_time = time.time() - start_time
            print(f"   ✅ Connected in {connect_time:.2f}s")

            # Test if we can get account info (this often fails with handshake issues)
            print(f"   🔍 Testing account retrieval...")
            accounts = ib.managedAccounts()
            account_time = time.time() - start_time
            print(f"   💼 Got accounts {accounts} in {account_time:.2f}s")

            # Try to request market data
            print(f"   📊 Testing market data request...")
            contract = Stock("SPY", "SMART", "USD")
            ticker = ib.reqMktData(contract, "", False, False)

            # Wait briefly for data
            print(f"   ⏳ Waiting 3 seconds for market data...")
            ib.sleep(3)

            data_time = time.time() - start_time

            if ticker.last != ticker.last or ticker.bid != ticker.bid:  # Check for NaN
                print(f"   ❌ No market data received")
            else:
                print(
                    f"   💰 Market data: Last=${ticker.last} Bid=${ticker.bid} Ask=${ticker.ask}"
                )
                self.data_received += 1

            total_time = time.time() - start_time

            ib.disconnect()
            print(f"   🔌 Disconnected after {total_time:.2f}s total")

            self.successful_connections += 1
            self.handshake_times.append(connect_time)
            return True

        except Exception as e:
            error_time = time.time() - start_time
            print(f"   ❌ Connection failed after {error_time:.2f}s: {str(e)}")

            if "TimeoutError" in str(e) or "timeout" in str(e).lower():
                self.timeout_errors += 1
                print(f"   ⚠️  TIMEOUT ERROR detected - this is the handshake issue!")

            try:
                ib.disconnect()
            except:
                pass
            return False
        finally:
            self.connection_attempts += 1


def run_handshake_timeout_test():
    """Run comprehensive handshake timeout testing"""
    print("🔬 HANDSHAKE TIMEOUT TEST FOR GATEWAY 10.37")
    print(f"📅 Started: {datetime.now()}")
    print("=" * 60)

    # First, verify Gateway is listening
    print("1️⃣ Verifying Gateway connectivity...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex(("127.0.0.1", 4002))
        sock.close()

        if result == 0:
            print("   ✅ Gateway is listening on port 4002")
        else:
            print("   ❌ Gateway not accessible - aborting test")
            return False
    except Exception as e:
        print(f"   ❌ Socket test failed: {e}")
        return False

    # Run multiple connection tests
    tester = HandshakeTimeoutTester()

    print("\n2️⃣ Running handshake timeout tests...")
    print("   Testing multiple connections with different client IDs")

    # Test with various client IDs and timeouts
    test_configs = [
        (100, 5),  # Client 100, 5s timeout
        (101, 10),  # Client 101, 10s timeout
        (102, 15),  # Client 102, 15s timeout
        (103, 20),  # Client 103, 20s timeout
        (104, 30),  # Client 104, 30s timeout
    ]

    for client_id, timeout in test_configs:
        success = tester.test_single_connection(client_id, timeout)
        if not success:
            print(f"   ⚠️  Connection {client_id} failed - continuing with next test")

        # Brief pause between connections
        time.sleep(2)

    # Generate results
    print("\n" + "=" * 60)
    print("📊 HANDSHAKE TIMEOUT TEST RESULTS")
    print("=" * 60)

    print(f"🔄 Total Attempts: {tester.connection_attempts}")
    print(f"✅ Successful Connections: {tester.successful_connections}")
    print(
        f"❌ Failed Connections: {tester.connection_attempts - tester.successful_connections}"
    )
    print(f"⏱️  Timeout Errors: {tester.timeout_errors}")
    print(f"📊 Market Data Received: {tester.data_received}")

    if tester.handshake_times:
        avg_handshake = sum(tester.handshake_times) / len(tester.handshake_times)
        print(f"⚡ Average Handshake Time: {avg_handshake:.2f}s")
        print(
            f"⚡ Handshake Range: {min(tester.handshake_times):.2f}s - {max(tester.handshake_times):.2f}s"
        )

    success_rate = (
        (tester.successful_connections / tester.connection_attempts) * 100
        if tester.connection_attempts > 0
        else 0
    )
    print(f"📈 Success Rate: {success_rate:.1f}%")

    # Assessment
    print(f"\n🎯 HANDSHAKE ASSESSMENT:")

    if tester.timeout_errors > 0:
        print("❌ HANDSHAKE TIMEOUT ISSUE DETECTED!")
        print("   This explains why data is not flowing in the dashboard")

        if tester.timeout_errors == tester.connection_attempts:
            print(
                "   🚨 ALL connections timed out - Gateway 10.37 may still have issues"
            )
        else:
            print("   ⚠️  PARTIAL timeouts - intermittent handshake problem")

        print("\n🔧 POSSIBLE SOLUTIONS:")
        print("   • Gateway may need manual configuration via GUI")
        print("   • API settings might not be properly enabled")
        print("   • Try restarting Gateway with different settings")
        print("   • Check if paper trading is properly configured")

    elif success_rate >= 80:
        print("✅ HANDSHAKE WORKING WELL!")
        print("   Gateway 10.37 handshake is functioning properly")
        if tester.data_received > 0:
            print("   📊 Market data is flowing - dashboard should work")
        else:
            print("   ⚠️  No market data - might be outside trading hours")

    else:
        print("⚠️  MIXED RESULTS")
        print("   Some connections work, others fail - needs investigation")

    print(f"\n📅 Test completed: {datetime.now()}")
    return success_rate >= 50


if __name__ == "__main__":
    print("Testing handshake timeouts that prevent data flow...")
    success = run_handshake_timeout_test()

    if success:
        print("\n✅ Handshake test indicates Gateway 10.37 is working")
    else:
        print("\n❌ Handshake issues detected - this explains dashboard data problems")
