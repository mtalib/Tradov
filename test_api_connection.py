#!/usr/bin/env python3
"""
Temporary API connection test - run this first
"""
import time
from ib_async import IB, Stock

def test_api_connection():
    """Test basic API connection with proper client ID."""
    print("Testing IB Gateway API connection...")
    print(f"Target: 127.0.0.1:4002")
    print(f"Client ID: 2 (Master)")
    
    try:
        ib = IB()
        print("Connecting...")
        ib.connect('127.0.0.1', 4002, clientId=2, timeout=15)
        
        if ib.isConnected():
            print("✓ Connected successfully!")
            
            # Test account data request
            print("Testing account data...")
            ib.reqAccountSummary(9001, 'All', 'NetLiquidation,BuyingPower')
            time.sleep(3)
            
            # Test market data request
            print("Testing market data...")
            spy = Stock('SPY', 'SMART', 'USD')
            ib.qualifyContracts(spy)
            ticker = ib.reqMktData(spy, '', False, False)
            time.sleep(3)
            
            if ticker.last:
                print(f"✓ Market data working: SPY = ${ticker.last}")
            else:
                print("✗ No market data received")
            
            ib.disconnect()
            print("✓ Test completed successfully")
            return True
        else:
            print("✗ Connection failed")
            return False
            
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

if __name__ == "__main__":
    success = test_api_connection()
    if success:
        print("\n→ API is working. You can now test the enhanced bridge.")
    else:
        print("\n→ Fix API settings first before testing enhanced bridge.")
