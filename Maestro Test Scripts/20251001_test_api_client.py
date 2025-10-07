#!/usr/bin/env python3
"""
Quick API Client Connection Test
Test immediately after enabling API Client in Gateway GUI
"""

import sys
import time
from datetime import datetime

sys.path.append("/home/adam/Projects/Spyder")

try:
    from ib_async import IB

    print("✅ Using ib_async 1.0.3")
except ImportError as e:
    print(f"❌ Error importing ib_async: {e}")
    sys.exit(1)


def quick_api_test():
    """Quick test after API Client is enabled"""
    print("🚀 QUICK API CLIENT TEST")
    print(f"📅 {datetime.now()}")
    print("=" * 40)

    print("🔌 Testing API Client connection...")

    ib = IB()

    try:
        print("   📡 Connecting with client ID 999...")
        ib.connect("127.0.0.1", 4002, clientId=999)

        print("   ✅ Connected successfully!")

        # Test basic functionality
        accounts = ib.managedAccounts()
        print(f"   💼 Accounts: {accounts}")

        if accounts:
            print("   🎉 API CLIENT IS WORKING!")
            print("   ✅ Gateway API handshake successful")
            print("   🚀 Ready for dashboard data flow!")
        else:
            print("   ⚠️  Connected but no accounts")

        ib.disconnect()
        print("   🔌 Disconnected cleanly")
        return True

    except Exception as e:
        print(f"   ❌ Connection failed: {str(e)}")

        if "timeout" in str(e).lower():
            print("   🚨 Still getting timeouts - API Client may not be enabled")

        try:
            ib.disconnect()
        except:
            pass
        return False


if __name__ == "__main__":
    print("Run this test AFTER enabling API Client in Gateway GUI...")
    success = quick_api_test()

    if success:
        print("\n🎉 SUCCESS! API Client is working - dashboard should get data now!")
    else:
        print("\n❌ API Client still not working - check Gateway configuration")
        print("\n🔧 Make sure to:")
        print("   1. Configure → API → Enable ActiveX and Socket Clients")
        print("   2. Set Socket Port to 4002")
        print("   3. Apply settings and restart if needed")
