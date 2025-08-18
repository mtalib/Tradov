#!/usr/bin/env python3
"""Simple connection test without IBAutomater"""

from ib_insync import IB

print("Simple IB Gateway Connection Test")
print("=" * 40)

ib = IB()

try:
    # Connect to Gateway
    ib.connect('127.0.0.1', 4002, clientId=1)
    
    if ib.isConnected():
        print("✅ Connected successfully!")
        accounts = ib.managedAccounts()
        if accounts:
            print(f"Account: {accounts[0]}")
        
        # Get some info
        server_time = ib.reqCurrentTime()
        print(f"Server time: {server_time}")
        
        ib.disconnect()
        print("✅ Disconnected cleanly")
    else:
        print("❌ Connection failed")
        
except Exception as e:
    print(f"❌ Error: {e}")
    print("Make sure IB Gateway is running and you're logged in")
