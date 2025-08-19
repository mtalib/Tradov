#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Module: temp_TimeZoneDiagnosticFix.py
Purpose: Diagnose and fix timezone issues with IBKR Zurich server data
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-19 Time: 14:45:00  

Module Description:
    Diagnoses timezone issues when connected to IBKR Zurich server from Portugal.
    Market data timestamps need proper conversion to ensure real-time data detection.
    Implements IBKR's recommendation to convert all timestamps to UTC.
"""

import time
from datetime import datetime, timezone
import pytz
from ib_insync import *

class TimeZoneDiagnosticFix:
    """Diagnose and fix timezone issues with IBKR data."""
    
    def __init__(self):
        self.ib = None
        
        # Define key timezones
        self.timezones = {
            'UTC': pytz.UTC,
            'Portugal': pytz.timezone('Europe/Lisbon'),  # UTC+0/+1
            'Zurich': pytz.timezone('Europe/Zurich'),    # UTC+1/+2  
            'US_Eastern': pytz.timezone('US/Eastern'),   # UTC-5/-4
            'US_Market': pytz.timezone('America/New_York')  # Market timezone
        }
        
    def run_timezone_diagnostic(self):
        """Run comprehensive timezone diagnostic."""
        print("🌍 TIMEZONE DIAGNOSTIC & FIX")
        print("=" * 60)
        print("Diagnosing timezone issues with IBKR Zurich server")
        print()
        
        # Show current time situation
        self._show_current_times()
        
        # Check market hours in all timezones  
        self._check_market_status()
        
        if not self._connect():
            return
        
        # Test data with timezone analysis
        print("\n3️⃣ Testing Market Data with Timezone Analysis...")
        self._test_data_with_timezones()
        
        # Generate timezone fix recommendations
        self._generate_timezone_fix()
        
        self._cleanup()
    
    def _show_current_times(self):
        """Show current time in all relevant timezones."""
        print("1️⃣ Current Time Analysis:")
        print("-" * 40)
        
        now_utc = datetime.now(pytz.UTC)
        
        for name, tz in self.timezones.items():
            local_time = now_utc.astimezone(tz)
            print(f"   {name:12}: {local_time.strftime('%H:%M:%S %Z (%z)')}")
        
        # Calculate time differences
        print("\n   Time Differences from UTC:")
        for name, tz in self.timezones.items():
            if name != 'UTC':
                local_time = now_utc.astimezone(tz)
                offset = local_time.utcoffset().total_seconds() / 3600
                print(f"   {name:12}: UTC{offset:+.0f}")
    
    def _check_market_status(self):
        """Check market status in different timezones."""
        print("\n2️⃣ Market Hours Analysis:")
        print("-" * 40)
        
        now_utc = datetime.now(pytz.UTC)
        
        # US Market time (Eastern)
        market_time = now_utc.astimezone(self.timezones['US_Eastern'])
        market_hour = market_time.hour
        market_minute = market_time.minute
        
        print(f"   US Market Time: {market_time.strftime('%H:%M:%S %Z')}")
        
        # Determine market status
        if market_hour < 9 or (market_hour == 9 and market_minute < 30):
            status = "PRE-MARKET"
            next_event = "Market opens at 9:30 AM ET"
        elif 9 <= market_hour < 16 or (market_hour == 9 and market_minute >= 30):
            status = "🔔 MARKET OPEN"
            next_event = "Market closes at 4:00 PM ET"
        elif 16 <= market_hour < 20:
            status = "AFTER-HOURS"
            next_event = "After-hours until 8:00 PM ET"
        else:
            status = "MARKET CLOSED"
            next_event = "Market opens 9:30 AM ET tomorrow"
        
        print(f"   Market Status: {status}")
        print(f"   Next Event: {next_event}")
        
        # Your local time
        portugal_time = now_utc.astimezone(self.timezones['Portugal'])
        print(f"   Your Local Time: {portugal_time.strftime('%H:%M:%S %Z')}")
        
        # IBKR Server time
        zurich_time = now_utc.astimezone(self.timezones['Zurich'])
        print(f"   IBKR Zurich Time: {zurich_time.strftime('%H:%M:%S %Z')}")
        
        # Market expectation
        if status == "🔔 MARKET OPEN":
            print("   ✅ MARKET IS OPEN - Should see real-time data changes")
        else:
            print("   ⏰ Market not in main session - Limited activity expected")
    
    def _connect(self):
        """Connect to IBKR Gateway."""
        try:
            self.ib = IB()
            self.ib.connect('127.0.0.1', 4002, clientId=66)
            
            if self.ib.isConnected():
                print("✅ Connected to IB Gateway (Zurich server)")
                return True
            else:
                print("❌ Connection failed")
                return False
                
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False
    
    def _test_data_with_timezones(self):
        """Test market data and analyze timestamps in different timezones."""
        print("   Testing SPY data with timezone analysis...")
        
        try:
            # Set to real-time data
            self.ib.reqMarketDataType(1)
            
            spy = Stock('SPY', 'SMART', 'USD')
            qualified = self.ib.qualifyContracts(spy)
            
            if not qualified:
                print("   ❌ SPY contract qualification failed")
                return
            
            print("   📡 Requesting SPY market data...")
            ticker = self.ib.reqMktData(qualified[0], '', False, False)
            
            # Wait for data
            time.sleep(5)
            
            print(f"   📊 SPY Data Received:")
            print(f"      Last Price: ${ticker.last}")
            print(f"      Bid: ${ticker.bid}")
            print(f"      Ask: ${ticker.ask}")
            print(f"      Volume: {ticker.volume}")
            
            # Analyze timestamp
            if ticker.time:
                print(f"\n   🕐 Timestamp Analysis:")
                raw_timestamp = ticker.time
                print(f"      Raw Timestamp: {raw_timestamp}")
                
                # Convert to different timezones
                if raw_timestamp.tzinfo is None:
                    # Assume it's in Zurich time if no timezone info
                    print("      ⚠️  No timezone info - assuming Zurich time")
                    zurich_aware = self.timezones['Zurich'].localize(raw_timestamp)
                else:
                    zurich_aware = raw_timestamp
                
                # Convert to all relevant timezones
                conversions = {}
                for name, tz in self.timezones.items():
                    if name != 'Zurich':
                        converted = zurich_aware.astimezone(tz)
                        conversions[name] = converted
                        print(f"      {name:12}: {converted.strftime('%H:%M:%S %Z')}")
                
                # Calculate data age
                now_utc = datetime.now(pytz.UTC)
                if zurich_aware.tzinfo:
                    data_utc = zurich_aware.astimezone(pytz.UTC)
                    age_seconds = (now_utc - data_utc).total_seconds()
                    
                    if age_seconds < 60:
                        age_str = f"{age_seconds:.0f} seconds ago"
                        freshness = "✅ REAL-TIME"
                    elif age_seconds < 900:  # 15 minutes
                        age_str = f"{age_seconds/60:.0f} minutes ago"
                        freshness = "⚠️  DELAYED"
                    else:
                        age_str = f"{age_seconds/3600:.1f} hours ago"
                        freshness = "❌ STALE"
                    
                    print(f"      Data Age: {age_str} - {freshness}")
                
            else:
                print("   ❌ No timestamp available")
            
            # Monitor for changes (timezone-aware)
            print(f"\n   🔄 Monitoring for 15 seconds...")
            self._monitor_changes_timezone_aware(ticker)
            
            self.ib.cancelMktData(qualified[0])
            
        except Exception as e:
            print(f"   ❌ Data test error: {e}")
    
    def _monitor_changes_timezone_aware(self, ticker):
        """Monitor for price changes with timezone awareness."""
        initial_values = {
            'last': ticker.last,
            'bid': ticker.bid,
            'ask': ticker.ask,
            'time': ticker.time
        }
        
        changes_detected = []
        start_time = time.time()
        
        while time.time() - start_time < 15:
            time.sleep(1)
            
            # Check for changes
            current_values = {
                'last': ticker.last,
                'bid': ticker.bid,
                'ask': ticker.ask,
                'time': ticker.time
            }
            
            for field, value in current_values.items():
                if field != 'time' and value != initial_values[field] and value > 0:
                    change_msg = f"{field.upper()}: {initial_values[field]} → {value}"
                    if change_msg not in changes_detected:
                        changes_detected.append(change_msg)
                        
                        # Show timezone-aware timestamp
                        if current_values['time']:
                            timestamp_str = self._format_timezone_aware_time(current_values['time'])
                            print(f"      🔄 CHANGE: {change_msg} at {timestamp_str}")
                        else:
                            print(f"      🔄 CHANGE: {change_msg}")
                        
                        initial_values[field] = value
            
            # Timestamp changes
            if current_values['time'] != initial_values['time'] and current_values['time']:
                timestamp_str = self._format_timezone_aware_time(current_values['time'])
                print(f"      🕐 TIMESTAMP UPDATE: {timestamp_str}")
                initial_values['time'] = current_values['time']
        
        if changes_detected:
            print(f"      ✅ {len(changes_detected)} real-time changes detected")
        else:
            print(f"      ❌ No changes detected - possible timezone/staleness issue")
    
    def _format_timezone_aware_time(self, timestamp):
        """Format timestamp showing multiple timezones."""
        if not timestamp:
            return "No timestamp"
        
        if timestamp.tzinfo is None:
            # Assume Zurich time
            zurich_time = self.timezones['Zurich'].localize(timestamp)
        else:
            zurich_time = timestamp
        
        # Convert to key timezones
        utc_time = zurich_time.astimezone(pytz.UTC)
        et_time = zurich_time.astimezone(self.timezones['US_Eastern'])
        
        return f"UTC:{utc_time.strftime('%H:%M:%S')} | ET:{et_time.strftime('%H:%M:%S')} | Zurich:{zurich_time.strftime('%H:%M:%S')}"
    
    def _generate_timezone_fix(self):
        """Generate timezone fix recommendations."""
        print(f"\n🔧 TIMEZONE FIX RECOMMENDATIONS")
        print("=" * 60)
        
        print("📋 Issues Identified:")
        print("   1. IBKR Zurich server provides timestamps in local server time")
        print("   2. Your system expects US Eastern time for market data")
        print("   3. Portugal timezone adds another conversion layer")
        print("   4. Spyder may be misinterpreting timestamp freshness")
        
        print(f"\n💡 IMMEDIATE FIXES:")
        print("   1. Update Spyder timestamp handling:")
        print("      → Always convert IBKR timestamps to UTC first")
        print("      → Then convert UTC to desired display timezone")
        print("      → Use pytz for all timezone operations")
        
        print(f"\n   2. Market data processing fix:")
        print("      → Assume all IBKR timestamps are in server timezone (Zurich)")
        print("      → Convert: Zurich → UTC → US Eastern for display")
        print("      → Calculate data age using UTC timestamps")
        
        print(f"\n   3. Real-time detection fix:")
        print("      → Don't rely on timestamp comparison for freshness")
        print("      → Use price/volume changes to detect real-time data")
        print("      → Allow for timezone offset in age calculations")
        
        print(f"\n🔨 CODE FIXES NEEDED:")
        print("   1. In Spyder data processing modules:")
        print("      → Add timezone conversion wrapper")
        print("      → Standardize all timestamps to UTC")
        print("      → Fix staleness detection logic")
        
        print(f"\n   2. Display layer fixes:")
        print("      → Convert UTC timestamps to local time for display")
        print("      → Show 'as of' time in user's timezone")
        print("      → Indicate data freshness properly")
        
        # Create timezone conversion helper
        print(f"\n📝 Timezone Conversion Helper:")
        self._create_timezone_helper()
    
    def _create_timezone_helper(self):
        """Create a timezone conversion helper function."""
        helper_code = '''
# Timezone Helper for Spyder (add to utilities)
import pytz
from datetime import datetime

class SpyderTimezoneHelper:
    """Timezone conversion helper for IBKR data."""
    
    def __init__(self):
        self.server_tz = pytz.timezone('Europe/Zurich')  # IBKR server
        self.market_tz = pytz.timezone('US/Eastern')     # US market
        self.utc = pytz.UTC
    
    def ibkr_to_utc(self, timestamp):
        """Convert IBKR timestamp to UTC."""
        if timestamp.tzinfo is None:
            # Assume server timezone
            aware_ts = self.server_tz.localize(timestamp)
        else:
            aware_ts = timestamp
        return aware_ts.astimezone(self.utc)
    
    def utc_to_market_time(self, utc_timestamp):
        """Convert UTC to US market time."""
        return utc_timestamp.astimezone(self.market_tz)
    
    def is_data_fresh(self, timestamp, max_age_seconds=60):
        """Check if data is fresh (timezone-aware)."""
        utc_timestamp = self.ibkr_to_utc(timestamp)
        now_utc = datetime.now(self.utc)
        age = (now_utc - utc_timestamp).total_seconds()
        return age <= max_age_seconds
    
    def format_for_display(self, timestamp, local_tz='Europe/Lisbon'):
        """Format timestamp for display in user's timezone."""
        utc_ts = self.ibkr_to_utc(timestamp)
        local_tz_obj = pytz.timezone(local_tz)
        local_ts = utc_ts.astimezone(local_tz_obj)
        return local_ts.strftime('%H:%M:%S %Z')

# Usage example:
# tz_helper = SpyderTimezoneHelper()
# fresh_data = tz_helper.is_data_fresh(ticker.time)
# display_time = tz_helper.format_for_display(ticker.time)
'''
        
        with open('temp_SpyderTimezoneHelper.py', 'w') as f:
            f.write(helper_code)
        
        print("   ✅ Created temp_SpyderTimezoneHelper.py")
        print("   📋 Use this helper in your Spyder modules")
    
    def _cleanup(self):
        """Clean up connection."""
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
        print(f"\n🧹 Timezone diagnostic completed")

def main():
    """Run timezone diagnostic."""
    diagnostic = TimeZoneDiagnosticFix()
    diagnostic.run_timezone_diagnostic()

if __name__ == "__main__":
    main()
