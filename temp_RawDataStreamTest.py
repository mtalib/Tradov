#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Module: temp_RawDataStreamTest.py
Purpose: Test raw data stream from IBKR to isolate data flow issues
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-19 Time: 15:50:00  

Module Description:
    Direct test of IBKR data stream to isolate whether the issue is with
    data delivery or Spyder's data processing pipeline.
"""

import time
from datetime import datetime
from ib_insync import *

class RawDataStreamTest:
    """Test raw data stream from IBKR."""
    
    def __init__(self):
        self.ib = None
        self.connected = False
        self.data_received = {}
        self.tick_count = 0
        
    def run_test(self):
        """Run comprehensive data stream test."""
        print("🔬 RAW DATA STREAM TEST")
        print("=" * 50)
        print(f"🕐 Test Time: {datetime.now().strftime('%H:%M:%S')}")
        
        # Step 1: Connect
        if not self._connect():
            return
        
        # Step 2: Test different market data types
        self._test_market_data_types()
        
        # Step 3: Subscribe to guaranteed working symbol
        self._test_spy_subscription()
        
        # Step 4: Monitor raw data stream
        self._monitor_raw_stream()
        
        # Step 5: Test callbacks
        self._test_callbacks()
        
        # Cleanup
        self._cleanup()
    
    def _connect(self):
        """Connect to IB Gateway."""
        try:
            self.ib = IB()
            self.ib.connect('127.0.0.1', 4002, clientId=777)
            
            if self.ib.isConnected():
                print("✅ Connected to IB Gateway")
                self.connected = True
                
                # Get account info
                account = self.ib.managedAccounts()
                if account:
                    print(f"📊 Account: {account[0]}")
                
                return True
            else:
                print("❌ Connection failed")
                return False
                
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False
    
    def _test_market_data_types(self):
        """Test different market data types."""
        print("\n🔧 Testing Market Data Types...")
        
        data_types = [
            (1, "Real-time"),
            (2, "Frozen"),
            (3, "Delayed"), 
            (4, "Delayed-Frozen")
        ]
        
        for data_type, name in data_types:
            try:
                print(f"   Testing {name} (Type {data_type})...")
                self.ib.reqMarketDataType(data_type)
                time.sleep(1)
                
                # Try a quick SPY subscription test
                spy = Stock('SPY', 'SMART', 'USD')
                qualified = self.ib.qualifyContracts(spy)
                
                if qualified:
                    ticker = self.ib.reqMktData(spy, '', False, False)
                    time.sleep(3)  # Wait for data
                    
                    if ticker.last > 0 or ticker.bid > 0 or ticker.ask > 0:
                        print(f"      ✅ {name}: WORKING! Last={ticker.last}, Bid={ticker.bid}, Ask={ticker.ask}")
                        self.working_data_type = data_type
                    else:
                        print(f"      ❌ {name}: No data")
                    
                    # Cancel subscription
                    self.ib.cancelMktData(spy)
                    
                else:
                    print(f"      ❌ {name}: Contract qualification failed")
                    
            except Exception as e:
                print(f"      ❌ {name}: Error - {e}")
        
        # Set back to best working type
        if hasattr(self, 'working_data_type'):
            self.ib.reqMarketDataType(self.working_data_type)
            print(f"✅ Set to working data type: {self.working_data_type}")
        else:
            self.ib.reqMarketDataType(3)  # Default to delayed
            print("⚠️  No working data type found, using delayed")
    
    def _test_spy_subscription(self):
        """Test SPY subscription in detail."""
        print("\n📈 Testing SPY Subscription in Detail...")
        
        try:
            # Create SPY contract
            spy = Stock('SPY', 'SMART', 'USD')
            print(f"   Contract: {spy}")
            
            # Qualify contract
            qualified = self.ib.qualifyContracts(spy)
            if not qualified:
                print("❌ SPY contract qualification failed")
                return
            
            print(f"✅ Qualified contract: {qualified[0]}")
            
            # Request market data with detailed tick types
            ticker = self.ib.reqMktData(
                qualified[0],
                '100,101,104,105,106,107,165,221,225,236',  # Detailed tick types
                False,  # Not snapshot
                False   # Not regulatory snapshot
            )
            
            print(f"✅ Requested market data for SPY")
            print(f"   Ticker object: {ticker}")
            
            # Store ticker for monitoring
            self.spy_ticker = ticker
            
        except Exception as e:
            print(f"❌ SPY subscription error: {e}")
    
    def _monitor_raw_stream(self):
        """Monitor raw data stream."""
        print("\n📊 Monitoring Raw Data Stream for 60 seconds...")
        print("   Watching for ANY price changes...")
        
        start_time = time.time()
        last_values = {}
        
        while time.time() - start_time < 60:
            try:
                # Check all tickers
                for ticker in self.ib.tickers():
                    symbol = ticker.contract.symbol
                    
                    current_values = {
                        'last': ticker.last,
                        'bid': ticker.bid,
                        'ask': ticker.ask,
                        'volume': ticker.volume,
                        'time': ticker.time
                    }
                    
                    # Check for any changes
                    if symbol not in last_values:
                        last_values[symbol] = current_values
                        if any(v > 0 for v in [ticker.last, ticker.bid, ticker.ask]):
                            print(f"📊 {symbol}: Initial data - Last={ticker.last}, Bid={ticker.bid}, Ask={ticker.ask}")
                            self.data_received[symbol] = current_values
                    else:
                        # Check for changes
                        for field, value in current_values.items():
                            if field != 'time' and value != last_values[symbol][field] and value > 0:
                                print(f"🔄 {symbol}: {field.upper()} changed: {last_values[symbol][field]} → {value}")
                                self.data_received[symbol] = current_values
                                self.tick_count += 1
                        
                        last_values[symbol] = current_values
                
                # Update every second
                time.sleep(1)
                print(".", end="", flush=True)
                
            except Exception as e:
                print(f"\n❌ Monitoring error: {e}")
                break
        
        print(f"\n\n📊 Monitoring Results:")
        print(f"   Total ticks received: {self.tick_count}")
        print(f"   Symbols with data: {len(self.data_received)}")
        
        if self.data_received:
            print("   Data received for:")
            for symbol, data in self.data_received.items():
                print(f"      {symbol}: {data}")
        else:
            print("   ❌ NO DATA RECEIVED AT ALL")
    
    def _test_callbacks(self):
        """Test if callbacks are working."""
        print("\n🔧 Testing Callback Functions...")
        
        # Set up callbacks
        def on_tick_price(ticker, field, price, size):
            print(f"📊 CALLBACK: {ticker.contract.symbol} - {field} = {price}")
            self.callback_received = True
        
        def on_tick_size(ticker, field, size):
            print(f"📊 CALLBACK: {ticker.contract.symbol} - {field} = {size}")
            self.callback_received = True
        
        # Subscribe to events
        if hasattr(self, 'spy_ticker'):
            self.callback_received = False
            self.spy_ticker.updateEvent += on_tick_price
            
            print("   Waiting 10 seconds for callbacks...")
            time.sleep(10)
            
            if hasattr(self, 'callback_received'):
                print("✅ Callbacks are working")
            else:
                print("❌ No callbacks received")
    
    def _cleanup(self):
        """Clean up connection."""
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
        print("🧹 Cleanup completed")

def main():
    """Run the raw data stream test."""
    test = RawDataStreamTest()
    test.run_test()

if __name__ == "__main__":
    main()