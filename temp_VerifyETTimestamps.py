#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Module: temp_VerifyETTimestamps.py
Purpose: Verify that IBKR is indeed sending ET timestamps (not Zurich)
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-19 Time: 15:00:00  

Module Description:
    Based on IBKR documentation, real-time data should come with ET timestamps.
    This verifies the actual timezone of IBKR timestamps and tests if the issue
    is in Spyder's display/calculation logic rather than timezone conversion.
"""

import time
from datetime import datetime
import pytz
from ib_insync import *

class ETTimestampVerifier:
    """Verify IBKR timestamp format and timezone."""
    
    def __init__(self):
        self.ib = None
        self.et_tz = pytz.timezone('US/Eastern')
        self.lisbon_tz = pytz.timezone('Europe/Lisbon')
        self.utc_tz = pytz.UTC
        
    def verify_timestamps(self):
        """Verify IBKR timestamp format and timezone."""
        print("🕐 IBKR TIMESTAMP VERIFICATION")
        print("=" * 60)
        print("Testing if IBKR sends ET timestamps as documented")
        print()
        
        # Show current time references
        self._show_time_references()
        
        if not self._connect():
            return
        
        # Test real-time data timestamps
        print("\n2️⃣ Testing Real-Time Data Timestamps...")
        self._test_realtime_timestamps()
        
        # Monitor timestamp behavior
        print("\n3️⃣ Monitoring Timestamp Updates...")
        self._monitor_timestamp_updates()
        
        # Analyze the +0.00% display issue
        print("\n4️⃣ Analyzing Display Calculation Issue...")
        self._analyze_display_calculation()
        
        self._cleanup()
    
    def _show_time_references(self):
        """Show current time in key timezones."""
        print("1️⃣ Current Time References:")
        print("-" * 40)
        
        now_utc = datetime.now(self.utc_tz)
        now_et = now_utc.astimezone(self.et_tz)
        now_lisbon = now_utc.astimezone(self.lisbon_tz)
        
        print(f"   UTC Time:    {now_utc.strftime('%H:%M:%S %Z')}")
        print(f"   ET Time:     {now_et.strftime('%H:%M:%S %Z')} ← IBKR should send this")
        print(f"   Lisbon Time: {now_lisbon.strftime('%H:%M:%S %Z')} ← Your local time")
        
        # Market status
        market_hour = now_et.hour
        if 9 <= market_hour < 16:
            print(f"   📈 Market Status: OPEN (should see price changes)")
        else:
            print(f"   📊 Market Status: CLOSED (limited activity)")
    
    def _connect(self):
        """Connect to IBKR Gateway."""
        try:
            self.ib = IB()
            self.ib.connect('127.0.0.1', 4002, clientId=55)
            
            if self.ib.isConnected():
                print("✅ Connected to IB Gateway")
                return True
            else:
                print("❌ Connection failed")
                return False
                
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False
    
    def _test_realtime_timestamps(self):
        """Test if IBKR timestamps are indeed in ET."""
        print("   Testing SPY real-time data timestamps...")
        
        try:
            # Request real-time data (as per IBKR docs, no conversion needed)
            self.ib.reqMarketDataType(1)  # Real-time
            
            spy = Stock('SPY', 'SMART', 'USD')
            qualified = self.ib.qualifyContracts(spy)
            
            if not qualified:
                print("   ❌ SPY contract qualification failed")
                return
            
            ticker = self.ib.reqMktData(qualified[0], '', False, False)
            time.sleep(3)
            
            print(f"   📊 SPY Data:")
            print(f"      Last: ${ticker.last}")
            print(f"      Bid: ${ticker.bid}")
            print(f"      Ask: ${ticker.ask}")
            
            if ticker.time:
                print(f"      Raw Timestamp: {ticker.time}")
                print(f"      Timestamp Type: {type(ticker.time)}")
                print(f"      Has Timezone Info: {ticker.time.tzinfo is not None}")
                
                # Test if it's actually ET as documented
                if ticker.time.tzinfo:
                    print(f"      Timezone: {ticker.time.tzinfo}")
                    
                    # Convert to different timezones for comparison
                    if hasattr(ticker.time.tzinfo, 'zone'):
                        tz_name = ticker.time.tzinfo.zone
                        print(f"      Timezone Name: {tz_name}")
                    
                    # Check if it matches ET
                    et_now = datetime.now(self.et_tz)
                    time_diff = abs((ticker.time - et_now).total_seconds())
                    
                    if time_diff < 300:  # Within 5 minutes
                        print(f"      ✅ CONFIRMED: Timestamp is in ET (as documented)")
                    else:
                        print(f"      ⚠️  Timestamp differs from ET by {time_diff/60:.1f} minutes")
                
                else:
                    print(f"      ⚠️  No timezone info - assuming ET per IBKR docs")
                    # Assume it's ET and add timezone info
                    et_aware = self.et_tz.localize(ticker.time)
                    print(f"      As ET: {et_aware}")
                
                # Convert to your local time for display
                if ticker.time.tzinfo:
                    lisbon_time = ticker.time.astimezone(self.lisbon_tz)
                else:
                    et_aware = self.et_tz.localize(ticker.time)
                    lisbon_time = et_aware.astimezone(self.lisbon_tz)
                
                print(f"      Your Local Time: {lisbon_time}")
                
            else:
                print(f"      ❌ No timestamp available")
            
            self.spy_ticker = ticker  # Save for further testing
            
        except Exception as e:
            print(f"   ❌ Timestamp test error: {e}")
    
    def _monitor_timestamp_updates(self):
        """Monitor how timestamps update with new data."""
        print("   Monitoring timestamp updates for 20 seconds...")
        
        if not hasattr(self, 'spy_ticker'):
            print("   ❌ No ticker available for monitoring")
            return
        
        ticker = self.spy_ticker
        last_timestamp = ticker.time
        last_price = ticker.last
        
        changes_detected = []
        
        for i in range(20):
            time.sleep(1)
            
            # Check for timestamp changes
            if ticker.time != last_timestamp:
                if ticker.time:
                    print(f"      🕐 Timestamp updated: {ticker.time}")
                    last_timestamp = ticker.time
            
            # Check for price changes
            if ticker.last != last_price and ticker.last > 0:
                change = ticker.last - last_price
                change_pct = (change / last_price) * 100 if last_price > 0 else 0
                print(f"      💰 Price change: ${last_price} → ${ticker.last} ({change_pct:+.2f}%)")
                changes_detected.append((last_price, ticker.last, change_pct))
                last_price = ticker.last
        
        print(f"   📊 Monitoring Results:")
        if changes_detected:
            print(f"      ✅ {len(changes_detected)} price changes detected")
            for old_price, new_price, pct_change in changes_detected:
                print(f"         ${old_price} → ${new_price} ({pct_change:+.2f}%)")
        else:
            print(f"      ❌ No price changes during monitoring")
    
    def _analyze_display_calculation(self):
        """Analyze why Spyder might show +0.00%."""
        print("   Analyzing potential display calculation issues...")
        
        if not hasattr(self, 'spy_ticker'):
            print("   ❌ No ticker for analysis")
            return
        
        ticker = self.spy_ticker
        
        print(f"   📊 Current SPY Data:")
        print(f"      Last: ${ticker.last}")
        print(f"      Close: ${ticker.close}")
        print(f"      Open: ${ticker.open}")
        print(f"      High: ${ticker.high}")
        print(f"      Low: ${ticker.low}")
        
        # Calculate change from different baselines
        if ticker.last > 0 and ticker.close > 0:
            change_from_close = ticker.last - ticker.close
            pct_from_close = (change_from_close / ticker.close) * 100
            print(f"      Change from Close: ${change_from_close:.2f} ({pct_from_close:+.2f}%)")
        
        if ticker.last > 0 and ticker.open > 0:
            change_from_open = ticker.last - ticker.open
            pct_from_open = (change_from_open / ticker.open) * 100
            print(f"      Change from Open: ${change_from_open:.2f} ({pct_from_open:+.2f}%)")
        
        # Identify potential issues
        print(f"\n   🔍 Potential Issues:")
        
        if ticker.close == 0 or ticker.close == ticker.last:
            print(f"      ⚠️  Close price issue: Close=${ticker.close}, Last=${ticker.last}")
            print(f"         Spyder might be using wrong baseline for % calculation")
        
        if ticker.open == 0:
            print(f"      ⚠️  No open price data available")
        
        if all(x == 0 for x in [ticker.high, ticker.low, ticker.open, ticker.close]):
            print(f"      ❌ All OHLC data is zero - data quality issue")
        
        if ticker.last > 0 and ticker.close > 0 and abs(pct_from_close) < 0.01:
            print(f"      ℹ️  Very small change ({pct_from_close:+.4f}%) - might round to 0.00%")
        
        # Test manual percentage calculation
        print(f"\n   🧮 Manual Calculation Test:")
        if ticker.last > 0 and ticker.close > 0:
            manual_change = ((ticker.last - ticker.close) / ticker.close) * 100
            print(f"      Manual %: {manual_change:+.4f}%")
            if abs(manual_change) < 0.005:
                print(f"      💡 Change is real but very small - rounds to 0.00%")
            else:
                print(f"      💡 Significant change detected - Spyder display issue")
    
    def _cleanup(self):
        """Clean up connection."""
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
        print(f"\n🧹 Timestamp verification completed")

def main():
    """Run timestamp verification."""
    verifier = ETTimestampVerifier()
    verifier.verify_timestamps()

if __name__ == "__main__":
    main()