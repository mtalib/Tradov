#!/usr/bin/env python3
"""
Test connectAsync with 60 second timeout as suggested
"""

import sys
import asyncio
from datetime import datetime

sys.path.append("/home/adam/Projects/Spyder")

try:
    from ib_async import IB

    print("✅ Using ib_async 1.0.3")
except ImportError as e:
    print(f"❌ Error importing ib_async: {e}")
    sys.exit(1)


async def test_connectAsync_with_60s_timeout():
    """Test connectAsync with 60 second timeout"""
    print("🔌 TESTING connectAsync WITH 60s TIMEOUT")
    print(f"📅 {datetime.now()}")
    print("=" * 50)

    ib = IB()

    try:
        print("📡 Connecting with your suggested parameters...")
        print("   Host: 127.0.0.1")
        print("   Port: 4002")
        print("   Client ID: 1")
        print("   Timeout: 60 seconds")
        print("   Method: connectAsync (as you suggested)")

        start_time = datetime.now()

        await ib.connectAsync(
            host="127.0.0.1",
            port=4002,
            clientId=1,
            timeout=60,  # Your suggested timeout
        )

        end_time = datetime.now()
        connection_time = (end_time - start_time).total_seconds()

        print(f"\n🎉 SUCCESS! Connected in {connection_time:.2f} seconds!")

        # Test account access
        accounts = ib.managedAccounts()
        print(f"📊 Accounts: {accounts}")

        # Test if we can get basic info
        if accounts:
            print(f"✅ Account access working!")

        ib.disconnect()
        print(f"🔌 Disconnected cleanly")

        return True

    except Exception as e:
        print(f"❌ connectAsync failed: {str(e)}")
        try:
            ib.disconnect()
        except:
            pass
        return False


async def main():
    print("Testing your suggested connectAsync approach...")
    success = await test_connectAsync_with_60s_timeout()

    if success:
        print(f"\n🎯 YOUR SOLUTION WORKS!")
        print(f"✅ connectAsync with 60s timeout successful")
        print(f"💡 The issue was likely the 20s timeout was too short")
        print(f"🚀 SpyderA01_Main.py should work with this fix!")
    else:
        print(f"\n⚠️  Still having issues")
        print(f"💭 May need to investigate further")


if __name__ == "__main__":
    asyncio.run(main())
