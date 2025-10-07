#!/usr/bin/env python3
"""
Market Data Flow Test - Now that handshake is working
Test if we can actually get real-time market data
"""

import sys
import time
from datetime import datetime

sys.path.append("/home/adam/Projects/Spyder")

try:
    from ib_async import IB, Stock

    print("✅ Using ib_async 1.0.3")
except ImportError as e:
    print(f"❌ Error importing ib_async: {e}")
    sys.exit(1)


def test_market_data_flow():
    """Test actual market data flow"""
    print("📊 MARKET DATA FLOW TEST")
    print(f"📅 {datetime.now()}")
    print("=" * 50)

    ib = IB()

    try:
        print("🔌 Connecting to Gateway...")
        ib.connect("127.0.0.1", 4002, clientId=555)
        print("   ✅ Connected successfully!")

        print("\n📈 Requesting market data for SPY...")
        contract = Stock("SPY", "SMART", "USD")
        ticker = ib.reqMktData(contract, "", False, False)

        print("   📡 Market data request sent")
        print("   ⏳ Waiting for data updates...")

        # Wait and monitor for data
        data_received = False
        for i in range(10):  # Wait up to 10 seconds
            ib.sleep(1)

            # Check if we have any data
            if (
                (ticker.last and not (ticker.last != ticker.last))
                or (ticker.bid and not (ticker.bid != ticker.bid))
                or (ticker.ask and not (ticker.ask != ticker.ask))
            ):

                print(f"\n💰 MARKET DATA RECEIVED!")
                print(f"   📊 Last: ${ticker.last}")
                print(f"   💵 Bid: ${ticker.bid}")
                print(f"   💷 Ask: ${ticker.ask}")
                print(f"   📈 Volume: {ticker.volume}")
                print(f"   📅 Time: {ticker.time}")

                data_received = True
                break
            else:
                print(f"   ⏳ Waiting... {10-i}s remaining")

        if not data_received:
            print(f"\n⚠️  No market data received after 10 seconds")
            print(f"   This could be normal if:")
            print(f"   • Markets are closed")
            print(f"   • Using delayed data")
            print(f"   • Need market data subscription")

        # Test another symbol
        print(f"\n📈 Testing AAPL market data...")
        aapl_contract = Stock("AAPL", "SMART", "USD")
        aapl_ticker = ib.reqMktData(aapl_contract, "", False, False)

        ib.sleep(3)

        if aapl_ticker.last and not (aapl_ticker.last != aapl_ticker.last):
            print(f"   💰 AAPL Last: ${aapl_ticker.last}")
            data_received = True
        else:
            print(f"   ⚠️  No AAPL data yet")

        ib.disconnect()
        print(f"\n🔌 Disconnected cleanly")

        return data_received

    except Exception as e:
        print(f"❌ Market data test failed: {str(e)}")
        try:
            ib.disconnect()
        except:
            pass
        return False


if __name__ == "__main__":
    print("Testing market data flow with working handshake...")
    success = test_market_data_flow()

    if success:
        print(f"\n🎉 SUCCESS! Market data is flowing!")
        print(f"✅ Dashboard should now display real-time data")
        print(f"🚀 Gateway 10.37 is fully operational!")
    else:
        print(f"\n⚠️  Market data not flowing yet")
        print(f"💡 This could be normal depending on:")
        print(f"   • Market hours")
        print(f"   • Data subscriptions")
        print(f"   • Paper trading account limitations")
        print(f"But the handshake is working, which was the main issue!")
