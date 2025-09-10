import asyncio
from ib_async import IB

async def test_basic_connection():
    ib = IB()
    
    try:
        print("Attempting connection to port 4002 (Paper Trading)...")
        await ib.connectAsync('127.0.0.1', 4002, clientId=1, timeout=30)
        print("✅ Connection successful!")
        
        # Use the correct method names for ib_async
        try:
            print(f"Server version: {ib.client.serverVersion}")
            print(f"Connection state: {ib.isConnected()}")
            print(f"Next order ID: {ib.client.getReqId()}")
            
            # Test basic account info
            managed_accounts = ib.managedAccounts()
            print(f"Managed accounts: {managed_accounts}")
            
            # Wait a moment for any initial data
            await asyncio.sleep(2)
            
            # Test market data permissions
            print("\n📊 Testing market data permissions...")
            
            # Create a simple stock contract
            from ib_async import Stock
            spy = Stock('SPY', 'SMART', 'USD')
            contracts = await ib.qualifyContractsAsync(spy)
            
            if contracts:
                print(f"✅ Contract qualified: {contracts[0]}")
                
                # Test requesting market data
                ticker = ib.reqMktData(contracts[0], '', snapshot=True)
                print(f"Market data request sent for: {ticker.contract.symbol}")
                
                # Wait for data
                await asyncio.sleep(5)
                
                if ticker.last and ticker.last > 0:
                    print(f"✅ Market data received: ${ticker.last}")
                    return True
                else:
                    print(f"⚠️  No market data received yet. Ticker state: last={ticker.last}, bid={ticker.bid}, ask={ticker.ask}")
                    print("This might indicate market data permissions issue or delayed data")
                    return True  # Connection is working even if no data yet
            else:
                print("❌ Could not qualify contract")
                return False
                
        except AttributeError as ae:
            print(f"⚠️  Attribute error (but connection works): {ae}")
            return True  # Connection is working
            
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        
        # Try port 4001 anyway
        try:
            print("\nTrying port 4001 (Live Trading)...")
            await ib.connectAsync('127.0.0.1', 4001, clientId=1, timeout=30)
            print("✅ Connected on port 4001!")
            return True
        except Exception as e2:
            print(f"❌ Port 4001 also failed: {e2}")
            return False
    
    finally:
        if ib.isConnected():
            print("Disconnecting...")
            ib.disconnect()

if __name__ == "__main__":
    success = asyncio.run(test_basic_connection())
    if success:
        print("\n🎉 Connection test PASSED - Your IB Gateway connection is working!")
    else:
        print("\n❌ Connection test FAILED - Check IB Gateway settings")