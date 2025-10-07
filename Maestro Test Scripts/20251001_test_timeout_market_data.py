#!/usr/bin/env python3
"""
IB Gateway 10.37 Market Data Test - Non-Blocking Version
Quick test to see if we can get any market data without hanging
"""

import sys
import threading
import time
import signal
from datetime import datetime

# Add Spyder path
sys.path.append("/home/adam/Projects/Spyder")


class TimeoutHandler:
    """Handle timeouts for the test"""

    def __init__(self, timeout=20):
        self.timeout = timeout
        self.timed_out = False

    def timeout_handler(self, signum, frame):
        print(f"\n⏰ Test timed out after {self.timeout} seconds")
        self.timed_out = True
        raise TimeoutError("Test timeout")


def test_with_timeout():
    """Test market data with timeout protection"""
    timeout_handler = TimeoutHandler(20)  # 20 second timeout

    # Set up timeout signal
    signal.signal(signal.SIGALRM, timeout_handler.timeout_handler)
    signal.alarm(20)

    try:
        from ibapi.client import EClient
        from ibapi.wrapper import EWrapper
        from ibapi.contract import Contract

        class QuickTester(EWrapper, EClient):
            def __init__(self):
                EClient.__init__(self, self)
                self.connected = False
                self.data_count = 0
                self.start_time = time.time()

            def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
                print(f"📟 Gateway message {errorCode}: {errorString}")

            def connectAck(self):
                print("✅ Connected to Gateway!")
                self.connected = True

            def nextValidId(self, orderId):
                print(f"📝 Got order ID: {orderId}")
                # Try to request market data immediately
                contract = Contract()
                contract.symbol = "SPY"
                contract.secType = "STK"
                contract.exchange = "SMART"
                contract.currency = "USD"

                print("📡 Requesting SPY market data...")
                self.reqMktData(1, contract, "", False, False, [])

            def tickPrice(self, reqId, tickType, price, attrib):
                self.data_count += 1
                print(f"💰 SPY price update: ${price:.2f} (type {tickType})")

            def tickSize(self, reqId, tickType, size):
                self.data_count += 1
                print(f"📊 SPY size update: {size} (type {tickType})")

        print("🚀 Starting quick market data test...")
        print(f"📅 {datetime.now()}")

        app = QuickTester()

        print("🔌 Connecting to Gateway...")
        app.connect("127.0.0.1", 4002, clientId=125)

        # Run for a short time
        def run_client():
            app.run()

        client_thread = threading.Thread(target=run_client, daemon=True)
        client_thread.start()

        # Wait a bit and check results
        print("⏳ Waiting for data (max 15 seconds)...")

        for i in range(15):
            time.sleep(1)
            if app.data_count > 0:
                print(f"🎉 SUCCESS! Received {app.data_count} data updates!")
                break
            if i % 3 == 0:
                print(f"   Waiting... {15-i}s remaining")

        if app.data_count == 0:
            print("⚠️  No market data received")
            if app.connected:
                print(
                    "   Gateway connected but no data - might need login/subscription"
                )
            else:
                print("   Gateway connection issue")

        # Clean up
        try:
            app.cancelMktData(1)
            app.disconnect()
        except:
            pass

        signal.alarm(0)  # Cancel timeout

        return app.data_count > 0

    except TimeoutError:
        print("❌ Test timed out - Gateway might be waiting for user input")
        return False
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Test error: {e}")
        return False
    finally:
        signal.alarm(0)  # Make sure to cancel timeout


def main():
    """Main test function"""
    print("🧪 QUICK IB GATEWAY 10.37 MARKET DATA TEST")
    print("=" * 50)

    # First verify connection
    print("1️⃣ Testing basic connectivity...")
    try:
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex(("127.0.0.1", 4002))
        sock.close()

        if result != 0:
            print("❌ Gateway not accessible on port 4002")
            return False
        else:
            print("✅ Gateway is listening on port 4002")
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False

    # Now test market data
    print("\n2️⃣ Testing market data with timeout protection...")
    success = test_with_timeout()

    print("\n" + "=" * 50)
    print("📊 TEST RESULTS")
    print("=" * 50)

    if success:
        print("🎉 SUCCESS: Market data is flowing!")
        print("✅ IB Gateway 10.37 is working correctly")
        print("🚀 Ready for trading operations")
    else:
        print("⚠️  PARTIAL SUCCESS: Gateway accessible but no data")
        print("💡 Possible causes:")
        print("   • Gateway needs manual login (check GUI)")
        print("   • Paper trading account needs configuration")
        print("   • Market data subscriptions not active")
        print("   • Outside market hours (delayed data)")

    print(f"\n📅 Test completed: {datetime.now()}")
    return success


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
