#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test IB Gateway Connection
Simple script to test IB Gateway connectivity before running the full dashboard
"""

import socket
import time
from datetime import datetime
import pytz

def is_market_hours():
    """Check if current time is within market hours (4:00 AM - 4:30 PM ET)"""
    from datetime import time as dt_time
    
    MARKET_OPEN_TIME = dt_time(4, 0)  # 4:00 AM ET
    MARKET_CLOSE_TIME = dt_time(16, 30)  # 4:30 PM ET
    
    eastern = pytz.timezone("US/Eastern")
    now_et = datetime.now(eastern).time()
    return MARKET_OPEN_TIME <= now_et <= MARKET_CLOSE_TIME

def test_port_connection(host, port, port_name):
    """Test connection to a specific port"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print(f"✅ {port_name} (Port {port}): CONNECTED")
            return True
        else:
            print(f"❌ {port_name} (Port {port}): NOT CONNECTED")
            return False
    except Exception as e:
        print(f"❌ {port_name} (Port {port}): ERROR - {e}")
        return False

def main():
    print("=" * 60)
    print("🔍 IB GATEWAY CONNECTION TEST")
    print("=" * 60)
    
    # Check market hours
    market_open = is_market_hours()
    eastern = pytz.timezone("US/Eastern")
    current_time = datetime.now(eastern).strftime("%Y-%m-%d %H:%M:%S ET")
    
    print(f"Current Time: {current_time}")
    print(f"Market Status: {'🟢 OPEN' if market_open else '🔴 CLOSED'}")
    print()
    
    # Test both ports
    print("Testing IB Gateway Ports:")
    print("-" * 30)
    
    paper_connected = test_port_connection("127.0.0.1", 4002, "PAPER TRADING")
    live_connected = test_port_connection("127.0.0.1", 4001, "LIVE TRADING")
    
    print()
    
    # Summary
    if paper_connected or live_connected:
        print("🎯 RESULT: IB Gateway is running and accessible")
        if paper_connected:
            print("   📝 Paper trading available on port 4002")
        if live_connected:
            print("   💰 Live trading available on port 4001")
    else:
        print("❌ RESULT: IB Gateway is not running or not accessible")
        print("\n🔧 Troubleshooting steps:")
        print("   1. Start IB Gateway application")
        print("   2. Ensure it's logged in and connected")
        print("   3. Check that socket connections are enabled")
        print("   4. Verify the correct ports (4001/4002) are configured")
    
    print()
    
    # Test with ib_async if available
    try:
        print("Testing ib_async connection...")
        from ib_async import IB
        
        ib = IB()
        
        # Try paper trading port first
        if paper_connected:
            try:
                ib.connect('127.0.0.1', 4002, clientId=1)
                print("✅ ib_async: Successfully connected to paper trading!")
                print(f"   Account: {ib.accountValues()}")
                ib.disconnect()
            except Exception as e:
                print(f"❌ ib_async paper connection failed: {e}")
        
        # Try live port if paper failed
        elif live_connected:
            try:
                ib.connect('127.0.0.1', 4001, clientId=1)
                print("✅ ib_async: Successfully connected to live trading!")
                ib.disconnect()
            except Exception as e:
                print(f"❌ ib_async live connection failed: {e}")
        
    except ImportError:
        print("⚠️ ib_async not available - install with: pip install ib_async")
    except Exception as e:
        print(f"❌ ib_async test failed: {e}")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
