#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Module: temp_MarketDataTypeFixer.py
Purpose: Fix market data type and symbol specifications for real-time data
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-19 Time: 15:25:00  

Module Description:
    Quick fix for market data type configuration and symbol specifications
    to enable real-time data flow in Spyder system.
"""

import time
from ib_insync import *

class MarketDataFixer:
    """Fix market data configuration for real-time data."""
    
    def __init__(self):
        self.ib = None
        self.connected = False
        
    def connect_and_fix(self):
        """Connect to IB and fix market data settings."""
        print("🔧 SPYDER MARKET DATA FIXER")
        print("=" * 50)
        
        # Connect
        if not self._connect():
            return False
            
        # Fix market data type
        self._fix_market_data_type()
        
        # Test corrected symbols
        self._test_corrected_symbols()
        
        # Keep connection alive for testing
        print("\n📊 Testing data flow for 30 seconds...")
        self._monitor_data_flow()
        
        # Cleanup
        self._cleanup()
        
    def _connect(self):
        """Connect to IB Gateway."""
        try:
            self.ib = IB()
            
            # Try Gateway Paper (most likely working)
            print("🔌 Connecting to IB Gateway...")
            self.ib.connect('127.0.0.1', 4002, clientId=888)
            
            if self.ib.isConnected():
                print("✅ Connected to IB Gateway (Paper)")
                self.connected = True
                return True
            else:
                print("❌ Connection failed")
                return False
                
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False
    
    def _fix_market_data_type(self):
        """Fix market data type setting."""
        print("\n🔧 Fixing Market Data Type...")
        
        # Try real-time first (Type 1)
        try:
            self.ib.reqMarketDataType(1)  # Real-time
            print("✅ Set to Real-time market data (Type 1)")
            time.sleep(2)
        except Exception as e:
            print(f"⚠️  Real-time failed: {e}")
            
            # Fall back to delayed (Type 3)  
            try:
                self.ib.reqMarketDataType(3)  # Delayed
                print("✅ Set to Delayed market data (Type 3)")
                time.sleep(2)
            except Exception as e:
                print(f"❌ Delayed also failed: {e}")
    
    def _test_corrected_symbols(self):
        """Test symbols with corrected specifications."""
        print("\n🧪 Testing Corrected Symbol Specifications...")
        
        # Corrected symbol specifications
        corrected_symbols = {
            # VXV might be VXVCLS or not available - try both
            'VXV': [
                Index('VXV', 'CBOE', 'USD'),
                Index('VXVCLS', 'CBOE', 'USD'),
            ],
            # ADD-NYSE variations
            'ADD': [
                Index('ADD-NYSE', 'NYSE', 'USD'),
                Index('$ADD', 'NYSE', 'USD'),
                Index('ADD', 'NYSE', 'USD'),
            ],
            # Test working symbols
            'SPY': [Stock('SPY', 'SMART', 'USD')],
            'VIX': [Index('VIX', 'CBOE', 'USD')],
        }
        
        working_symbols = {}
        
        for symbol_group, contracts in corrected_symbols.items():
            print(f"\n   Testing {symbol_group}:")
            
            for contract in contracts:
                try:
                    # Qualify contract
                    qualified = self.ib.qualifyContracts(contract)
                    if qualified:
                        # Request data
                        ticker = self.ib.reqMktData(contract, '', False, False)
                        working_symbols[symbol_group] = contract
                        print(f"      ✅ {contract.symbol} - Working")
                        break
                    else:
                        print(f"      ❌ {contract.symbol} - Not found")
                        
                except Exception as e:
                    print(f"      ❌ {contract.symbol} - Error: {e}")
        
        self.working_symbols = working_symbols
        print(f"\n📊 Working Symbols: {list(working_symbols.keys())}")
    
    def _monitor_data_flow(self):
        """Monitor data flow for a short period."""
        start_time = time.time()
        data_received = {}
        
        while time.time() - start_time < 30:
            for ticker in self.ib.tickers():
                symbol = ticker.contract.symbol
                
                # Check for any price data
                if ticker.last > 0 or ticker.bid > 0 or ticker.ask > 0:
                    if symbol not in data_received:
                        data_received[symbol] = ticker
                        print(f"📊 {symbol}: Last={ticker.last}, Bid={ticker.bid}, Ask={ticker.ask}")
            
            time.sleep(1)
            print(".", end="", flush=True)
        
        print(f"\n\n✅ Data received for {len(data_received)} symbols")
        
        if len(data_received) == 0:
            print("🚨 NO DATA RECEIVED - Issue with subscriptions or market data permissions")
            print("💡 Check IBKR Account Management → Market Data Subscriptions")
        else:
            print("🎉 Data flow is working!")
    
    def _cleanup(self):
        """Clean up connection."""
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
        print("🧹 Cleanup completed")

def main():
    """Run the market data fixer."""
    fixer = MarketDataFixer()
    fixer.connect_and_fix()

if __name__ == "__main__":
    main()