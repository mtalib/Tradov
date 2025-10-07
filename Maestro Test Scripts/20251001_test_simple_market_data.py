#!/usr/bin/env python3
"""
IB Gateway 10.37 Market Data Flow Test - Simplified Version
Tests real-time market data streaming from the downgraded Gateway
"""

import sys
import time
import threading
from datetime import datetime
import traceback

# Add Spyder path
sys.path.append("/home/adam/Projects/Spyder")

try:
    from ibapi.client import EClient
    from ibapi.wrapper import EWrapper
    from ibapi.contract import Contract
except ImportError as e:
    print(f"❌ Error importing IB API: {e}")
    print("Please ensure ibapi is installed: pip install ibapi")
    sys.exit(1)


class SimpleMarketDataTester(EWrapper, EClient):
    """Simple test client for market data streaming"""

    def __init__(self):
        EClient.__init__(self, self)

        # Data tracking
        self.data_received = {}
        self.connection_status = "Disconnected"
        self.error_messages = []
        self.tick_count = 0

        # Test control
        self.next_req_id = 1
        self.test_symbols = ["SPY"]  # Start with just one symbol
        self.test_start_time = None
        self.test_duration = 15  # shorter test - 15 seconds

    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        """Handle error messages"""
        error_msg = f"Error {errorCode}: {errorString}"
        print(f"⚠️  {error_msg}")
        self.error_messages.append(error_msg)

        # Common error codes with explanations
        if errorCode == 502:
            print("   📡 Cannot connect to Gateway - check if it's running")
        elif errorCode == 200:
            print("   🔍 Security definition not found")
        elif errorCode == 354:
            print("   📊 Market data subscription issue")
        elif errorCode == 10167:
            print("   📈 Displaying delayed market data")
        elif errorCode == 2104:
            print("   🌐 Market data farm connection OK")
        elif errorCode == 2106:
            print("   📡 HMDS data farm connection OK")

    def connectAck(self):
        """Connection acknowledgment"""
        print("✅ Connection acknowledged by Gateway")
        self.connection_status = "Connected"

    def nextValidId(self, orderId):
        """Receive next valid order ID"""
        print(f"📝 Next valid order ID: {orderId}")
        self.next_req_id = orderId

        # Start market data tests after a short delay
        time.sleep(1)
        self.start_market_data_tests()

    def tickPrice(self, reqId, tickType, price, attrib):
        """Handle tick price data"""
        symbol = self.get_symbol_for_req_id(reqId)
        tick_name = self.get_tick_type_name(tickType)

        if symbol not in self.data_received:
            self.data_received[symbol] = {}

        self.data_received[symbol][f"{tick_name}_price"] = {
            "price": price,
            "timestamp": datetime.now(),
            "type": "price",
        }

        self.tick_count += 1
        print(f"📈 {symbol} {tick_name}: ${price:.2f}")

    def tickSize(self, reqId, tickType, size):
        """Handle tick size data"""
        symbol = self.get_symbol_for_req_id(reqId)
        tick_name = self.get_tick_type_name(tickType)

        if symbol not in self.data_received:
            self.data_received[symbol] = {}

        self.data_received[symbol][f"{tick_name}_size"] = {
            "size": size,
            "timestamp": datetime.now(),
            "type": "size",
        }

        self.tick_count += 1
        print(f"📊 {symbol} {tick_name}: {size}")

    def get_tick_type_name(self, tick_type):
        """Get human readable name for tick type"""
        tick_names = {
            1: "BID",
            2: "ASK",
            4: "LAST",
            6: "HIGH",
            7: "LOW",
            9: "CLOSE",
            0: "BID_SIZE",
            3: "ASK_SIZE",
            5: "LAST_SIZE",
            8: "VOLUME",
        }
        return tick_names.get(tick_type, f"TICK_{tick_type}")

    def get_symbol_for_req_id(self, req_id):
        """Get symbol name for request ID"""
        if req_id == 1:
            return "SPY"
        else:
            return f"REQ_{req_id}"

    def create_stock_contract(self, symbol):
        """Create a stock contract"""
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        return contract

    def start_market_data_tests(self):
        """Start requesting market data for test symbols"""
        print(f"\n🚀 Starting market data test for: {', '.join(self.test_symbols)}")
        self.test_start_time = datetime.now()

        for i, symbol in enumerate(self.test_symbols, 1):
            contract = self.create_stock_contract(symbol)
            print(f"📡 Requesting market data for {symbol}...")

            # Request market data (reqId, contract, genericTickList, snapshot, regulatorySnapshot, mktDataOptions)
            self.reqMktData(i, contract, "", False, False, [])

        print(f"⏱️  Will collect data for {self.test_duration} seconds...")


def run_simple_market_data_test():
    """Run the simplified market data flow test"""
    print("🚀 IB GATEWAY 10.37 MARKET DATA FLOW TEST")
    print(f"📅 Started: {datetime.now()}")
    print(f"🐍 Python: {sys.version}")

    # Create test client
    app = SimpleMarketDataTester()

    print("\n🔌 Connecting to IB Gateway on localhost:4002...")

    try:
        # Connect to Gateway
        app.connect("127.0.0.1", 4002, clientId=124)

        # Start message processing thread
        api_thread = threading.Thread(target=app.run, daemon=True)
        api_thread.start()

        # Wait for connection and initial setup
        print("⏳ Waiting for connection...")
        time.sleep(3)

        if app.connection_status != "Connected":
            print("❌ Failed to connect to Gateway")
            if app.error_messages:
                print("Errors encountered:")
                for error in app.error_messages:
                    print(f"   • {error}")
            return False

        print("✅ Connected to IB Gateway successfully!")

        # Run test for specified duration
        print(f"\n⏱️  Running market data test for {app.test_duration} seconds...")

        start_time = time.time()
        last_tick_count = 0

        while (time.time() - start_time) < app.test_duration:
            time.sleep(2)
            elapsed = int(time.time() - start_time)
            remaining = app.test_duration - elapsed

            # Show progress with tick count
            new_ticks = app.tick_count - last_tick_count
            last_tick_count = app.tick_count

            print(
                f"⏳ Test running... {remaining}s remaining | Total ticks: {app.tick_count} (+{new_ticks})"
            )

        # Stop market data requests
        print("\n🛑 Stopping market data requests...")
        for i in range(1, len(app.test_symbols) + 1):
            app.cancelMktData(i)

        time.sleep(1)

        # Generate report
        generate_simple_report(app)

        # Disconnect
        app.disconnect()
        return True

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        traceback.print_exc()
        return False


def generate_simple_report(app):
    """Generate simple market data test report"""
    print("\n" + "=" * 60)
    print("📊 MARKET DATA FLOW TEST REPORT")
    print("=" * 60)

    total_symbols = len(app.test_symbols)
    symbols_with_data = len(app.data_received)

    print(f"📈 Symbols Tested: {total_symbols}")
    print(f"📊 Symbols with Data: {symbols_with_data}")
    print(f"🎯 Total Ticks Received: {app.tick_count}")
    print(f"📡 Success Rate: {(symbols_with_data/total_symbols)*100:.1f}%")

    if app.error_messages:
        print(f"\n⚠️  Errors/Messages: {len(app.error_messages)}")
        for error in app.error_messages:
            print(f"   • {error}")
    else:
        print("\n✅ No errors encountered")

    print("\n📋 Data Summary:")
    for symbol in app.test_symbols:
        if symbol in app.data_received:
            data = app.data_received[symbol]
            data_fields = len(data)

            print(f"   ✅ {symbol}: {data_fields} data types received")

            # Show some sample data
            for field_name, field_data in list(data.items())[:3]:  # Show first 3 fields
                if field_data["type"] == "price":
                    value = f"${field_data['price']:.2f}"
                else:
                    value = str(field_data["size"])
                timestamp = field_data["timestamp"].strftime("%H:%M:%S")
                print(f"      📊 {field_name}: {value} @ {timestamp}")

        else:
            print(f"   ❌ {symbol}: No data received")

    # Overall assessment
    print(f"\n🎯 Test Assessment:")
    if app.tick_count > 10:
        print("🎉 EXCELLENT: Market data is flowing successfully!")
        print("✅ IB Gateway 10.37 is streaming real-time data")
        print("🚀 System is ready for trading operations")
    elif app.tick_count > 0:
        print("⚠️  GOOD: Some market data received")
        print("🔧 Data flow is working but may be limited")
    else:
        print("❌ POOR: No market data received")
        print("🔧 Check Gateway configuration and data subscriptions")

    print(f"\n📅 Test completed: {datetime.now()}")


if __name__ == "__main__":
    print("Testing market data flow with IB Gateway 10.37...")
    success = run_simple_market_data_test()

    if success:
        print("\n🎉 Market data test completed!")
    else:
        print("\n❌ Market data test had issues")

    print("\nNext steps:")
    print("• If no data: Check paper trading account data permissions")
    print("• If errors: Review Gateway logs and configuration")
    print("• For live trading: Switch to port 4001 and live account")
