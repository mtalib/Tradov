from ib_async import IB, Stock

ib = IB()
try:
    ib.connect('127.0.0.1', 4002, clientId=1)
    print(f"✅ Connected! Server version: {ib.client.serverVersion()}")
    
    # Request SPY data
    spy = Stock('SPY', 'SMART', 'USD')
    ticker = ib.reqMktData(spy)
    ib.sleep(2)  # Wait for data
    
    print(f"SPY Last: {ticker.last}")
    print(f"SPY Bid: {ticker.bid}")
    print(f"SPY Ask: {ticker.ask}")
    
    ib.disconnect()
except Exception as e:
    print(f"❌ Error: {e}")
