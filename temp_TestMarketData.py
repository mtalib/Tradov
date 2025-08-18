#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Quick Market Data Test

Purpose: Test if we can get real market data from IB Gateway
"""

from ib_insync import IB, Stock
import time

def test_market_data():
    """Quick test of market data access"""
    
    print("=" * 60)
    print("TESTING IB GATEWAY MARKET DATA")
    print("=" * 60)
    
    ib = IB()
    
    try:
        # Connect
        print("\n1. Connecting to IB Gateway...")
        ib.connect('127.0.0.1', 4002, clientId=777)
        print(f"   ✅ Connected to account: {ib.managedAccounts()[0]}")
        
        # Request delayed data (free)
        print("\n2. Requesting delayed market data...")
        ib.reqMarketDataType(3)  # 3 = delayed
        
        # Test SPY
        print("\n3. Testing SPY market data...")
        spy = Stock('SPY', 'SMART', 'USD')
        ib.qualifyContracts(spy)
        
        # Request market data
        ticker = ib.reqMktData(spy, '', False, False)
        
        # Wait for data
        print("   Waiting for data...")
        for i in range(10):
            ib.sleep(1)
            if ticker.last:
                print(f"\n   ✅ SPY LIVE DATA RECEIVED!")
                print(f"   Last: ${ticker.last:.2f}")
                print(f"   Bid:  ${ticker.bid:.2f}" if ticker.bid else "   Bid:  N/A")
                print(f"   Ask:  ${ticker.ask:.2f}" if ticker.ask else "   Ask:  N/A")
                print(f"   Volume: {ticker.volume:,}" if ticker.volume else "   Volume: N/A")
                break
            print(f"   Attempt {i+1}/10...")
        else:
            print("   ❌ No data received - check market data subscriptions")
        
        # Test account balance
        print("\n4. Testing account data...")
        account = ib.accountSummary()
        if account:
            for item in account[:3]:  # Show first 3 items
                print(f"   {item.tag}: {item.value}")
        
        print("\n✅ TEST COMPLETE!")
        
        # Check if data is real or simulated
        if ticker.last:
            print("\n📊 DATA STATUS: REAL (from IB Gateway)")
        else:
            print("\n⚠️ DATA STATUS: No data received")
            print("   Possible issues:")
            print("   - Market is closed (try during market hours)")
            print("   - No market data subscription")
            print("   - Need to accept delayed data agreement in TWS/Gateway")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("\nTroubleshooting:")
        print("1. Is IB Gateway running?")
        print("2. Are you logged in?")
        print("3. Is port 4002 correct?")
        
    finally:
        if ib.isConnected():
            ib.disconnect()
            print("\nDisconnected from IB Gateway")

if __name__ == "__main__":
    test_market_data()
