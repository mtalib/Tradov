#!/usr/bin/env python3
"""Simple IB connection test"""

from ib_insync import IB, Stock

# Create IB instance
ib = IB()

print("🔌 Attempting to connect to IB Gateway...")
print("   Host: localhost")
print("   Port: 4002 (paper trading)")
print("   Client ID: 999")

try:
    # Connect
    ib.connect('127.0.0.1', 4002, clientId=999)
    print("✅ Connected successfully!")
    
    # Get account info
    account = ib.accountSummary()
    print(f"📊 Account items: {len(account)}")
    
    # Test SPY contract
    spy = Stock('SPY', 'SMART', 'USD')
    ib.qualifyContracts(spy)
    print(f"✅ SPY contract qualified: {spy}")
    
    # Disconnect
    ib.disconnect()
    print("✅ Disconnected successfully")
    
except Exception as e:
    print(f"❌ Error: {e}")
    print("\nPossible issues:")
    print("1. IB Gateway not running")
    print("2. API not enabled in Gateway")
    print("3. Wrong port (should be 4002 for paper)")
    print("4. Client ID already in use")
