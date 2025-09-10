"""
fixed_temp_test_market_data.py - Working IB Gateway market data flow test
"""
import asyncio
from datetime import datetime
from ib_async import IB, Stock, Index, Option, util

async def test_market_data():
    ib = IB()
    
    try:
        # Connect using port 4002 for paper trading
        print("Connecting to IB Gateway on port 4002...")
        await ib.connectAsync('127.0.0.1', 4002, clientId=99, timeout=30)
        print(f"✅ Connected! Managed accounts: {ib.managedAccounts()}")
        
        # Check connection details
        print(f"Server version: {ib.client.serverVersion}")
        print(f"Connection time: {ib.client.connectionTime}")
        
        # Check market data type (1=Live, 2=Frozen, 3=Delayed, 4=Delayed-Frozen)
        print(f"\n📊 Current Market Data Type: {ib.reqMarketDataType()}")
        
        # Test 1: SPY Stock
        print("\n1️⃣ Testing SPY stock data...")
        spy = Stock('SPY', 'SMART', 'USD')
        qualified_contracts = await ib.qualifyContractsAsync(spy)
        
        if not qualified_contracts:
            print("❌ Failed to qualify SPY contract")
            return False
            
        spy = qualified_contracts[0]  # Use the qualified contract
        print(f"✅ Contract qualified: {spy}")
        
        # Request market data (not snapshot for better results)
        print("Requesting market data...")
        ticker = ib.reqMktData(spy, '', snapshot=False)
        
        # Wait for data to arrive
        print("Waiting for market data...")
        await asyncio.sleep(10)  # Give more time for data
        
        print(f"SPY Last: ${ticker.last if ticker.last else 'N/A'}")
        print(f"SPY Bid: ${ticker.bid if ticker.bid else 'N/A'}")
        print(f"SPY Ask: ${ticker.ask if ticker.ask else 'N/A'}")
        print(f"SPY Close: ${ticker.close if ticker.close else 'N/A'}")
        print(f"SPY Volume: {ticker.volume if ticker.volume else 'N/A'}")
        print(f"Time: {ticker.time if ticker.time else 'N/A'}")
        
        # Test 2: Check different data types
        print("\n2️⃣ Testing delayed data...")
        ib.reqMarketDataType(3)  # Request delayed data
        await asyncio.sleep(2)
        print(f"Market data type now: {ib.reqMarketDataType()}")
        
        ticker2 = ib.reqMktData(spy, '', snapshot=False)
        await asyncio.sleep(8)
        print(f"Delayed data test - Last: ${ticker2.last if ticker2.last else 'N/A'}")
        
        # Cancel market data subscriptions
        ib.cancelMktData(ticker)
        ib.cancelMktData(ticker2)
        
        # Test 3: Historical data
        print("\n3️⃣ Testing historical data...")
        try:
            bars = await ib.reqHistoricalDataAsync(
                spy,
                endDateTime='',
                durationStr='1 D',
                barSizeSetting='1 hour',
                whatToShow='TRADES',
                useRTH=True
            )
            
            if bars:
                print(f"✅ Historical bars received: {len(bars)}")
                latest = bars[-1]
                print(f"Latest bar: {latest.date} OHLC=${latest.open}/{latest.high}/{latest.low}/{latest.close}")
            else:
                print("❌ No historical data received")
        except Exception as he:
            print(f"Historical data error: {he}")
        
        # Test 4: Account information
        print("\n4️⃣ Testing account data...")
        try:
            # Request account summary
            account_summary = ib.reqAccountSummary()
            if account_summary:
                print("✅ Account summary received:")
                for item in account_summary[:5]:  # Show first 5 items
                    print(f"  {item.tag}: {item.value} {item.currency}")
            else:
                print("⚠️  No account summary data")
                
            # Try account values instead
            account_values = ib.accountValues()
            if account_values:
                print("Account values sample:")
                for av in account_values[:3]:
                    print(f"  {av.tag}: {av.value}")
                    
        except Exception as ae:
            print(f"Account data error: {ae}")
        
        print("\n🎉 Market data test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        if ib.isConnected():
            print("Disconnecting...")
            ib.disconnect()
            await asyncio.sleep(1)  # Give time for clean disconnect

# Run the test
if __name__ == "__main__":
    print("🚀 Starting comprehensive IB Gateway market data test...")
    success = asyncio.run(test_market_data())
    
    if success:
        print("\n✅ ALL TESTS PASSED! Your IB Gateway connection and market data are working!")
    else:
        print("\n❌ Some tests failed. Check the output above for details.")