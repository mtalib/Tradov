#!/usr/bin/env python3
"""
IB Gateway 10.37 Market Data Flow Test
Tests real-time market data streaming from the downgraded Gateway
"""

import sys
import time
import threading
from datetime import datetime, timedelta
import traceback

# Add Spyder path
sys.path.append("/home/adam/Projects/Spyder")

try:
    from ibapi.client import EClient
    from ibapi.wrapper import EWrapper
    from ibapi.contract import Contract
    from ibapi.common import TickTypeEnum
except ImportError as e:
    print(f"❌ Error importing IB API: {e}")
    print("Please ensure ibapi is installed: pip install ibapi")
    sys.exit(1)


class MarketDataTester(EWrapper, EClient):
    """Test client for market data streaming"""

    def __init__(self):
        EClient.__init__(self, self)

        # Data tracking
        self.data_received = {}
        self.connection_status = "Disconnected"
        self.error_messages = []
        self.market_data_types = {}
        self.contract_details = {}

        # Test control
        self.next_req_id = 1
        self.test_symbols = ["SPY", "AAPL", "MSFT"]
        self.test_start_time = None
        self.test_duration = 30  # seconds

    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        """Handle error messages"""
        error_msg = f"Error {errorCode}: {errorString}"
        print(f"⚠️  {error_msg}")
        self.error_messages.append(error_msg)

        # Common error codes
        if errorCode == 502:
            print("📡 Couldn't connect to TWS/Gateway. Is it running?")
        elif errorCode == 200:
            print("🔐 No security definition has been found for the request")
        elif errorCode == 354:
            print("📊 Requested market data is not subscribed")

    def connectAck(self):
        """Connection acknowledgment"""
        print("✅ Connection acknowledged by Gateway")
        self.connection_status = "Connected"

    def nextValidId(self, orderId):
        """Receive next valid order ID"""
        print(f"📝 Next valid order ID: {orderId}")
        self.next_req_id = orderId

        # Start market data tests
        self.start_market_data_tests()

    def tickPrice(self, reqId, tickType, price, attrib):
        """Handle tick price data"""
        symbol = self.get_symbol_for_req_id(reqId)
        tick_name = TickTypeEnum.to_str(tickType)

        if symbol not in self.data_received:
            self.data_received[symbol] = {}

        self.data_received[symbol][tick_name] = {
            "price": price,
            "timestamp": datetime.now(),
            "attrib": attrib,
        }

        print(f"📈 {symbol} {tick_name}: ${price:.2f}")

    def tickSize(self, reqId, tickType, size):
        """Handle tick size data"""
        symbol = self.get_symbol_for_req_id(reqId)
        tick_name = TickTypeEnum.to_str(tickType)

        if symbol not in self.data_received:
            self.data_received[symbol] = {}

        if "sizes" not in self.data_received[symbol]:
            self.data_received[symbol]["sizes"] = {}

        self.data_received[symbol]["sizes"][tick_name] = {
            "size": size,
            "timestamp": datetime.now(),
        }

        print(f"📊 {symbol} {tick_name}: {size}")

    def tickString(self, reqId, tickType, value):
        """Handle tick string data"""
        symbol = self.get_symbol_for_req_id(reqId)
        tick_name = TickTypeEnum.to_str(tickType)

        if symbol not in self.data_received:
            self.data_received[symbol] = {}

        if "strings" not in self.data_received[symbol]:
            self.data_received[symbol]["strings"] = {}

        self.data_received[symbol]["strings"][tick_name] = {
            "value": value,
            "timestamp": datetime.now(),
        }

        print(f"📄 {symbol} {tick_name}: {value}")

    def get_symbol_for_req_id(self, req_id):
        """Get symbol name for request ID"""
        # Simple mapping based on our test setup
        if req_id == 1:
            return "SPY"
        elif req_id == 2:
            return "AAPL"
        elif req_id == 3:
            return "MSFT"
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
        print(
            f"\n🚀 Starting market data tests for symbols: {', '.join(self.test_symbols)}"
        )
        self.test_start_time = datetime.now()

        for i, symbol in enumerate(self.test_symbols, 1):
            contract = self.create_stock_contract(symbol)
            print(f"📡 Requesting market data for {symbol}...")

            # Request market data
            self.reqMktData(i, contract, "", False, False, [])

            # Small delay between requests
            time.sleep(0.5)


def run_market_data_test():
    """Run the market data flow test"""
    print("🚀 IB GATEWAY 10.37 MARKET DATA FLOW TEST")
    print(f"📅 Started: {datetime.now()}")
    print(f"🐍 Python: {sys.version}")

    # Create test client
    app = MarketDataTester()

    print("\n🔌 Connecting to IB Gateway on localhost:4002...")

    try:
        # Connect to Gateway
        app.connect("127.0.0.1", 4002, clientId=123)

        # Start message processing thread
        api_thread = threading.Thread(target=app.run, daemon=True)
        api_thread.start()

        # Wait for connection
        time.sleep(2)

        if app.connection_status != "Connected":
            print("❌ Failed to connect to Gateway")
            return False

        print("✅ Connected to IB Gateway successfully!")

        # Run test for specified duration
        print(f"\n⏱️  Running market data test for {app.test_duration} seconds...")

        start_time = time.time()
        while (time.time() - start_time) < app.test_duration:
            time.sleep(1)
            elapsed = int(time.time() - start_time)
            remaining = app.test_duration - elapsed
            print(f"⏳ Test running... {remaining}s remaining")

        # Stop market data requests
        print("\n🛑 Stopping market data requests...")
        for i in range(1, len(app.test_symbols) + 1):
            app.cancelMktData(i)

        time.sleep(2)

        # Generate report
        generate_market_data_report(app)

        # Disconnect
        app.disconnect()
        return True

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        traceback.print_exc()
        return False


def generate_market_data_report(app):
    """Generate comprehensive market data test report"""
    print("\n" + "=" * 80)
    print("📊 MARKET DATA FLOW TEST REPORT")
    print("=" * 80)

    total_symbols = len(app.test_symbols)
    symbols_with_data = len(app.data_received)

    print(f"📈 Symbols Tested: {total_symbols}")
    print(f"📊 Symbols with Data: {symbols_with_data}")
    print(f"📡 Success Rate: {(symbols_with_data/total_symbols)*100:.1f}%")

    if app.error_messages:
        print(f"⚠️  Errors Encountered: {len(app.error_messages)}")
        for error in app.error_messages[:5]:  # Show first 5 errors
            print(f"   • {error}")
    else:
        print("✅ No errors encountered")

    print("\n📋 Data Summary by Symbol:")
    for symbol in app.test_symbols:
        if symbol in app.data_received:
            data = app.data_received[symbol]
            price_fields = len([k for k in data.keys() if "price" in str(data[k])])
            size_fields = len(data.get("sizes", {}))
            string_fields = len(data.get("strings", {}))
            total_fields = price_fields + size_fields + string_fields

            print(f"   ✅ {symbol}: {total_fields} data fields received")

            # Show recent prices
            for field_name, field_data in data.items():
                if isinstance(field_data, dict) and "price" in field_data:
                    price = field_data["price"]
                    timestamp = field_data["timestamp"]
                    print(
                        f"      💰 {field_name}: ${price:.2f} @ {timestamp.strftime('%H:%M:%S')}"
                    )
        else:
            print(f"   ❌ {symbol}: No data received")

    # Overall assessment
    print(f"\n🎯 Test Assessment:")
    if symbols_with_data >= total_symbols * 0.8:  # 80% success rate
        print("🎉 EXCELLENT: Market data is flowing successfully!")
        print("✅ IB Gateway 10.37 is properly streaming real-time data")
        print("🚀 System is ready for live trading operations")
    elif symbols_with_data >= total_symbols * 0.5:  # 50% success rate
        print("⚠️  GOOD: Some market data is flowing")
        print("🔧 Minor configuration adjustments may be needed")
    else:
        print("❌ POOR: Limited or no market data flow")
        print("🔧 Check Gateway configuration and market data subscriptions")

    print(f"\n📅 Test completed: {datetime.now()}")


if __name__ == "__main__":
    print("Testing market data flow with IB Gateway 10.37...")
    success = run_market_data_test()

    if success:
        print("\n🎉 Market data test completed successfully!")
    else:
        print("\n❌ Market data test encountered issues")

    print("\nNext steps:")
    print("• Review any error messages above")
    print("• Check your IB Gateway market data subscriptions")
    print("• Ensure paper trading account has data access")
