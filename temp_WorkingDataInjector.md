(.venv) adam@Captova:~/Projects/Spyder$ python temp_WorkingDataInjector.py
✅ ib_insync imported successfully

======================================================================
SPYDER WORKING LIVE DATA INJECTOR
======================================================================
This will inject REAL market data into your dashboard
Make sure your dashboard is running first!
======================================================================
======================================================================
SPYDER WORKING LIVE DATA INJECTOR
======================================================================
Client ID: 777
Target: 127.0.0.1:4002
Data Directory: /home/adam/Projects/Spyder/market_data
======================================================================

🔌 Connecting to IB Gateway...
   Host: 127.0.0.1
   Port: 4002
   Client ID: 777
✅ Connected to account: DU5361048
📊 Configured for delayed market data

📈 Subscribing to market data...
--------------------------------------------------
✅ SPY    - Subscribed successfully
✅ QQQ    - Subscribed successfully
✅ IWM    - Subscribed successfully
✅ VIX    - Subscribed successfully
✅ DIA    - Subscribed successfully
✅ TLT    - Subscribed successfully
✅ GLD    - Subscribed successfully
--------------------------------------------------
📊 Successfully subscribed to 7/7 symbols

🚀 Starting live data feed...
📊 Real market data will be saved to: /home/adam/Projects/Spyder/market_data/live_data.json
🔄 Dashboard should now display real prices!
======================================================================
Press Ctrl+C to stop...
======================================================================
#  10 | LIVE: SPY: $643.16 (+0.00%) | Updates: 5
#  20 | LIVE: SPY: $643.16 (+0.00%) | Updates: 5
#  30 | LIVE: SPY: $643.16 (+0.00%) | Updates: 5
#  40 | LIVE: SPY: $643.16 (+0.00%) | Updates: 5
^C
🛑 Shutdown signal received...

🛑 Stopping data injector...
cancelMktData: No reqId found for contract Ticker(contract=Stock(conId=756733, symbol='SPY', exchange='SMART', primaryExchange='ARCA', currency='USD', localSymbol='SPY', tradingClass='SPY'), time=datetime.datetime(2025, 8, 18, 20, 30, 0, 608384, tzinfo=datetime.timezone.utc), minTick=0.01, bid=643.15, bidSize=12900.0, bidExchange='ABCJKPTXYZU', ask=643.17, askSize=700.0, askExchange='P', last=643.16, lastSize=100.0, lastExchange='P', prevBidSize=13200.0, prevAsk=643.18, prevAskSize=1400.0, volume=435077.0, open=642.86, high=644.0, low=642.18, close=643.44, halted=0.0, ticks=[TickData(time=datetime.datetime(2025, 8, 18, 20, 30, 0, 608384, tzinfo=datetime.timezone.utc), tickType=2, price=643.17, size=700.0)], bboExchange='a60001', snapshotPermissions=3)
cancelMktData: No reqId found for contract Ticker(contract=Stock(conId=320227571, symbol='QQQ', exchange='SMART', primaryExchange='NASDAQ', currency='USD', localSymbol='QQQ', tradingClass='NMS'), time=datetime.datetime(2025, 8, 18, 20, 30, 0, 608384, tzinfo=datetime.timezone.utc), minTick=0.01, bid=576.96, bidSize=400.0, bidExchange='P', ask=576.99, askSize=2600.0, askExchange='KPQXZU', last=576.97, lastSize=200.0, lastExchange='X', prevBidSize=2000.0, prevAsk=577.0, prevAskSize=700.0, volume=295226.0, open=576.42, high=577.77, low=575.24, close=577.34, halted=0.0, ticks=[TickData(time=datetime.datetime(2025, 8, 18, 20, 30, 0, 608384, tzinfo=datetime.timezone.utc), tickType=0, price=576.96, size=400.0), TickData(time=datetime.datetime(2025, 8, 18, 20, 30, 0, 608384, tzinfo=datetime.timezone.utc), tickType=3, price=576.99, size=2600.0)], bboExchange='9c0001', snapshotPermissions=3)
cancelMktData: No reqId found for contract Ticker(contract=Stock(conId=9579970, symbol='IWM', exchange='SMART', primaryExchange='ARCA', currency='USD', localSymbol='IWM', tradingClass='IWM'), time=datetime.datetime(2025, 8, 18, 20, 30, 0, 392077, tzinfo=datetime.timezone.utc), minTick=0.01, bid=228.02, bidSize=4300.0, bidExchange='JKPTXZU', ask=228.03, askSize=800.0, askExchange='PT', last=228.02, lastSize=200.0, lastExchange='T', prevAskSize=900.0, volume=198359.0, open=227.23, high=228.46, low=226.94, close=227.13, halted=0.0, bboExchange='a60001', snapshotPermissions=3)
cancelMktData: No reqId found for contract Ticker(contract=Index(conId=13455763, symbol='VIX', exchange='CBOE', currency='USD', localSymbol='VIX'), time=datetime.datetime(2025, 8, 18, 20, 29, 59, 619065, tzinfo=datetime.timezone.utc), minTick=0.01, last=14.99, lastSize=0.0, open=15.73, high=15.95, low=14.95, close=15.09)
cancelMktData: No reqId found for contract Ticker(contract=Stock(conId=73128548, symbol='DIA', exchange='SMART', primaryExchange='ARCA', currency='USD', localSymbol='DIA', tradingClass='DIA'), time=datetime.datetime(2025, 8, 18, 20, 30, 0, 167660, tzinfo=datetime.timezone.utc), minTick=0.01, bid=449.0, bidSize=2000.0, bidExchange='KPTZUH', ask=449.03, askSize=2100.0, askExchange='AJPTUH', last=449.01, lastSize=200.0, lastExchange='P', prevBid=449.01, prevBidSize=1500.0, prevAsk=449.04, prevAskSize=700.0, volume=36843.0, open=449.36, high=449.97, low=448.63, close=449.53, bboExchange='a60001', snapshotPermissions=3)
cancelMktData: No reqId found for contract Ticker(contract=Stock(conId=15547841, symbol='TLT', exchange='SMART', primaryExchange='NASDAQ', currency='USD', localSymbol='TLT', tradingClass='NMS'), time=datetime.datetime(2025, 8, 18, 20, 30, 0, 608384, tzinfo=datetime.timezone.utc), minTick=0.01, bid=86.2, bidSize=700.0, bidExchange='PZ', ask=86.21, askSize=300.0, askExchange='P', last=86.21, lastSize=200.0, lastExchange='Q', prevBidSize=800.0, prevAsk=86.22, prevAskSize=400.0, volume=257166.0, open=86.49, high=86.54, low=85.99, close=86.4, ticks=[TickData(time=datetime.datetime(2025, 8, 18, 20, 30, 0, 608384, tzinfo=datetime.timezone.utc), tickType=1, price=86.2, size=800.0), TickData(time=datetime.datetime(2025, 8, 18, 20, 30, 0, 608384, tzinfo=datetime.timezone.utc), tickType=2, price=86.22, size=400.0), TickData(time=datetime.datetime(2025, 8, 18, 20, 30, 0, 608384, tzinfo=datetime.timezone.utc), tickType=4, price=86.21, size=200.0), TickData(time=datetime.datetime(2025, 8, 18, 20, 30, 0, 608384, tzinfo=datetime.timezone.utc), tickType=5, price=86.21, size=200.0), TickData(time=datetime.datetime(2025, 8, 18, 20, 30, 0, 608384, tzinfo=datetime.timezone.utc), tickType=8, price=-1.0, size=257166.0), TickData(time=datetime.datetime(2025, 8, 18, 20, 30, 0, 608384, tzinfo=datetime.timezone.utc), tickType=6, price=86.54, size=0.0), TickData(time=datetime.datetime(2025, 8, 18, 20, 30, 0, 608384, tzinfo=datetime.timezone.utc), tickType=7, price=85.99, size=0.0), TickData(time=datetime.datetime(2025, 8, 18, 20, 30, 0, 608384, tzinfo=datetime.timezone.utc), tickType=9, price=86.4, size=0.0), TickData(time=datetime.datetime(2025, 8, 18, 20, 30, 0, 608384, tzinfo=datetime.timezone.utc), tickType=14, price=86.49, size=0.0), TickData(time=datetime.datetime(2025, 8, 18, 20, 30, 0, 608384, tzinfo=datetime.timezone.utc), tickType=2, price=86.21, size=300.0), TickData(time=datetime.datetime(2025, 8, 18, 20, 30, 0, 608384, tzinfo=datetime.timezone.utc), tickType=0, price=86.2, size=700.0)], bboExchange='9c0001', snapshotPermissions=3)
cancelMktData: No reqId found for contract Ticker(contract=Stock(conId=51529211, symbol='GLD', exchange='SMART', primaryExchange='ARCA', currency='USD', localSymbol='GLD', tradingClass='GLD'))
✅ Disconnected from IB Gateway
✅ Data injector stopped

🛑 Stopping data injector...
✅ Data injector stopped

🛑 Stopping data injector...
✅ Data injector stopped
(.venv) adam@Captova:~/Projects/Spyder
