#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Module: temp_ComprehensiveDataFix.py
Purpose: Fix the NaN data issue and implement ET time display
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-19 Time: 14:50:00  

Module Description:
    Addresses the critical issue where API calls return NaN while Spyder
    dashboard shows cached data. Also implements ET time display for the dashboard.
"""

import time
from datetime import datetime
import pytz
from ib_insync import *

class ComprehensiveDataFix:
    """Fix data flow issues and implement ET time display."""
    
    def __init__(self):
        self.ib = None
        self.et_tz = pytz.timezone('US/Eastern')
        self.working_configs = []
        
    def run_comprehensive_fix(self):
        """Run comprehensive data fix and ET time implementation."""
        print("🔧 COMPREHENSIVE DATA FIX & ET TIME DISPLAY")
        print("=" * 70)
        print("Fixing NaN data issue and implementing ET time display")
        print()
        
        # Show ET time implementation
        self._implement_et_time_display()
        
        # Fix the data flow issue
        print("\n1️⃣ Diagnosing Data Flow Issue...")
        self._diagnose_data_issue()
        
        if not self._connect():
            return
        
        # Test different approaches to get data
        print("\n2️⃣ Testing Different Data Request Methods...")
        self._test_data_request_methods()
        
        # Test account and permissions
        print("\n3️⃣ Testing Account Permissions...")
        self._test_account_permissions()
        
        # Generate fixes
        print("\n4️⃣ Generating Data Flow Fixes...")
        self._generate_data_fixes()
        
        self._cleanup()
    
    def _implement_et_time_display(self):
        """Implement ET time display for dashboard."""
        print("🕐 IMPLEMENTING ET TIME DISPLAY")
        print("-" * 50)
        
        # Create ET time helper
        et_time_helper = """
# ET Time Display Helper for Spyder Dashboard
import pytz
from datetime import datetime

class ETTimeDisplay:
    '''Display ET time on dashboard regardless of local timezone.'''
    
    def __init__(self):
        self.et_tz = pytz.timezone('US/Eastern')
        self.utc_tz = pytz.UTC
    
    def get_et_time_string(self):
        '''Get current ET time as formatted string.'''
        et_now = datetime.now(self.et_tz)
        return et_now.strftime('%H:%M:%S %Z')
    
    def get_market_status(self):
        '''Get current market status based on ET time.'''
        et_now = datetime.now(self.et_tz)
        hour = et_now.hour
        minute = et_now.minute
        weekday = et_now.weekday()  # 0=Monday, 6=Sunday
        
        # Weekend check
        if weekday >= 5:  # Saturday or Sunday
            return 'WEEKEND', '🏖️'
        
        # Weekday market hours
        if hour < 9 or (hour == 9 and minute < 30):
            return 'PRE-MARKET', '🌅'
        elif 9 <= hour < 16 or (hour == 9 and minute >= 30):
            return 'MARKET OPEN', '🔔'
        elif 16 <= hour < 20:
            return 'AFTER-HOURS', '🌆'
        else:
            return 'MARKET CLOSED', '🌙'
    
    def format_for_dashboard(self):
        '''Format ET time and market status for dashboard display.'''
        et_time = self.get_et_time_string()
        status, icon = self.get_market_status()
        return f"{icon} {et_time} | {status}"

# Usage in Spyder Dashboard:
# et_display = ETTimeDisplay()
# dashboard_time_text = et_display.format_for_dashboard()
# # Result: "🔔 14:45:24 EDT | MARKET OPEN"
"""
        
        # Write to file
        with open('temp_ETTimeDisplay.py', 'w') as f:
            f.write(et_time_helper)
        
        print("✅ Created temp_ETTimeDisplay.py")
        
        # Show current ET time
        et_now = datetime.now(self.et_tz)
        print(f"📅 Current ET Time: {et_now.strftime('%H:%M:%S %Z')}")
        
        # Show market status
        hour = et_now.hour
        if 9 <= hour < 16:
            print(f"📈 Market Status: OPEN 🔔")
        else:
            print(f"📊 Market Status: CLOSED 🌙")
    
    def _diagnose_data_issue(self):
        """Diagnose why we're getting NaN data."""
        print("   Analyzing potential causes of NaN data...")
        print()
        print("   🔍 Possible Causes:")
        print("      1. Market data permissions not fully active")
        print("      2. Real-time subscription requires different setup") 
        print("      3. Paper trading account limitations")
        print("      4. Specific client ID or connection issues")
        print("      5. Market data type configuration")
        print("      6. Symbol contract specification issues")
        print()
    
    def _connect(self):
        """Connect to IBKR Gateway with enhanced diagnostics."""
        try:
            self.ib = IB()
            
            # Test different client IDs
            client_ids = [44, 1, 999, 100]
            
            for client_id in client_ids:
                try:
                    print(f"   Testing Client ID {client_id}...")
                    self.ib.connect('127.0.0.1', 4002, clientId=client_id, timeout=10)
                    
                    if self.ib.isConnected():
                        print(f"   ✅ Connected with Client ID {client_id}")
                        
                        # Test basic account info
                        try:
                            accounts = self.ib.managedAccounts()
                            print(f"      Accounts: {accounts}")
                            
                            if accounts:
                                # Try account summary
                                summary = self.ib.accountSummary()
                                print(f"      Account Summary: {len(summary)} items")
                                return True
                            
                        except Exception as e:
                            print(f"      ⚠️  Account access issue: {e}")
                            
                        return True
                        
                except Exception as e:
                    print(f"      ❌ Client ID {client_id} failed: {e}")
                    continue
            
            print("   ❌ All client ID attempts failed")
            return False
            
        except Exception as e:
            print(f"   ❌ Connection error: {e}")
            return False
    
    def _test_data_request_methods(self):
        """Test different methods to request market data."""
        print("   Testing various data request approaches...")
        
        # Test different market data types
        data_types = [
            (1, "Real-time"),
            (2, "Frozen"),  
            (3, "Delayed"),
            (4, "Delayed-Frozen")
        ]
        
        symbols_to_test = [
            ('SPY', Stock('SPY', 'SMART', 'USD')),
            ('SPY', Stock('SPY', 'ARCA', 'USD')),  # Try specific exchange
            ('AAPL', Stock('AAPL', 'SMART', 'USD')),  # Try different symbol
        ]
        
        for data_type, type_name in data_types:
            print(f"\n      Testing {type_name} (Type {data_type}):")
            
            try:
                self.ib.reqMarketDataType(data_type)
                time.sleep(2)
                
                for symbol_name, contract in symbols_to_test:
                    try:
                        print(f"         {symbol_name}...", end=" ")
                        
                        # Qualify contract
                        qualified = self.ib.qualifyContracts(contract)
                        if not qualified:
                            print("❌ No contract")
                            continue
                        
                        # Request data with different parameters
                        ticker = self.ib.reqMktData(
                            qualified[0], 
                            '',  # Generic tick list
                            False,  # Not snapshot
                            False,  # Not regulatory snapshot
                        )
                        
                        # Wait longer for data
                        time.sleep(5)
                        
                        # Check for any non-NaN data
                        if (ticker.last and not math.isnan(ticker.last)) or \
                           (ticker.bid and not math.isnan(ticker.bid)) or \
                           (ticker.ask and not math.isnan(ticker.ask)):
                            
                            print(f"✅ Data! Last=${ticker.last}, Bid=${ticker.bid}")
                            self.working_configs.append({
                                'data_type': data_type,
                                'type_name': type_name,
                                'symbol': symbol_name,
                                'contract': contract,
                                'last': ticker.last,
                                'bid': ticker.bid,
                                'ask': ticker.ask
                            })
                        else:
                            print("❌ Still NaN")
                        
                        # Cancel subscription
                        self.ib.cancelMktData(qualified[0])
                        
                    except Exception as e:
                        print(f"❌ Error: {e}")
                        
            except Exception as e:
                print(f"         ❌ Data type {data_type} error: {e}")
    
    def _test_account_permissions(self):
        """Test account permissions and capabilities."""
        print("   Testing account permissions...")
        
        try:
            # Test account summary
            print("      Account Summary...", end=" ")
            summary = self.ib.accountSummary()
            print(f"✅ {len(summary)} items")
            
            # Look for market data related permissions
            for item in summary:
                if 'MarketData' in item.tag or 'Data' in item.tag:
                    print(f"         {item.tag}: {item.value}")
            
            # Test positions
            print("      Positions...", end=" ")
            positions = self.ib.positions()
            print(f"✅ {len(positions)} positions")
            
            # Test open orders
            print("      Open Orders...", end=" ")
            orders = self.ib.openOrders()
            print(f"✅ {len(orders)} orders")
            
        except Exception as e:
            print(f"      ❌ Permission test error: {e}")
    
    def _generate_data_fixes(self):
        """Generate specific fixes for the data issue."""
        print("   Generating fix recommendations...")
        print()
        
        if self.working_configs:
            print("   🎉 GOOD NEWS: Found working configurations!")
            for config in self.working_configs:
                print(f"      ✅ {config['type_name']} - {config['symbol']}: ${config['last']}")
            
            print(f"\n   💡 SPYDER FIX:")
            best_config = self.working_configs[0]
            print(f"      1. Use Data Type {best_config['data_type']} ({best_config['type_name']})")
            print(f"      2. Update Spyder to use this configuration")
            print(f"      3. Restart Spyder with working data type")
            
        else:
            print("   🚨 NO WORKING CONFIGURATIONS FOUND")
            print()
            print("   🔧 EMERGENCY FIXES:")
            print("      1. Check IBKR Account Management:")
            print("         → Market Data Subscriptions")
            print("         → Ensure all subscriptions are 'Active'")
            print("      2. Try TWS instead of IB Gateway:")
            print("         → Close IB Gateway")
            print("         → Open Trader Workstation (TWS)")
            print("         → Use port 7497 (paper) or 7496 (live)")
            print("      3. Call IBKR Support:")
            print("         → 1-877-442-2757")
            print("         → Say: 'Market data API returning NaN values'")
            print("         → Account: DU5361048")
            print("      4. Check IB Gateway API Settings:")
            print("         → File → Global Configuration → API")
            print("         → Enable 'Create API message for new market data'")
            print("         → Enable 'ActiveX and Socket Clients'")
        
        # Create ET time display integration guide
        print(f"\n   🕐 ET TIME DISPLAY INTEGRATION:")
        print("      1. Add temp_ETTimeDisplay.py to your Spyder utilities")
        print("      2. Update dashboard to show ET time")
        print("      3. Display format: '🔔 14:45:24 EDT | MARKET OPEN'")
        print("      4. Updates automatically based on market hours")
    
    def _cleanup(self):
        """Clean up connection."""
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
        print(f"\n🧹 Comprehensive fix analysis completed")

def main():
    """Run comprehensive data fix."""
    fix = ComprehensiveDataFix()
    fix.run_comprehensive_fix()

if __name__ == "__main__":
    import math  # Add this import for math.isnan
    main()
