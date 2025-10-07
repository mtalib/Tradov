#!/usr/bin/env python3
"""
Simple IB Gateway Connection Test
This will create a visible client connection in IB Gateway
"""

import time
from ib_async import IB, util

print("=" * 60)
print("🔌 IB Gateway Connection Test")
print("=" * 60)

# Create IB instance
ib = IB()

# Connect to Gateway
print("\n📡 Connecting to IB Gateway...")
print("   Host: 127.0.0.1")
print("   Port: 4002 (Paper Trading)")
print("   Client ID: 10")

try:
    ib.connect("127.0.0.1", 4002, clientId=10, timeout=20)
    print("\n✅ CONNECTED!")
    print(f"   Connection status: {ib.isConnected()}")
    print(f"   Account: {ib.managedAccounts()}")

    print("\n👀 You should now see Client ID 10 in IB Gateway!")
    print("\n⏳ Keeping connection alive for 30 seconds...")
    print("   (Check IB Gateway console - you should see the client)")

    # Keep connection alive
    for i in range(30):
        print(f"   ... {30-i} seconds remaining", end="\r")
        time.sleep(1)

    print("\n\n🔌 Disconnecting...")
    ib.disconnect()
    print("✅ Disconnected cleanly")

except Exception as e:
    print(f"\n❌ Connection failed: {e}")
    print("\nTroubleshooting:")
    print("   1. Is IB Gateway running?")
    print("   2. Is it showing all green connections?")
    print("   3. Are you using Paper Trading (port 4002)?")

finally:
    if ib.isConnected():
        ib.disconnect()

print("\n" + "=" * 60)
print("Test complete")
print("=" * 60)
