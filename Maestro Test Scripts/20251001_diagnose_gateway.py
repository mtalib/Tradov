#!/usr/bin/env python3
"""
Quick diagnostic tool to test IB Gateway connection
"""
import sys
import asyncio
from ib_async import IB


async def test_connection():
    """Test basic IB connection"""
    ib = IB()

    print("🔍 Testing IB Gateway connection...")
    print(f"Target: 127.0.0.1:4002")
    print(f"Client ID: 999 (test)")
    print()

    try:
        print("⏳ Attempting to connect (30 second timeout)...")
        await asyncio.wait_for(
            ib.connectAsync("127.0.0.1", 4002, clientId=999, readonly=True), timeout=30
        )

        print("✅ CONNECTION SUCCESSFUL!")
        print(f"Connected: {ib.isConnected()}")
        print(f"Client ID: {ib.client.clientId if ib.client else 'N/A'}")

        # Try to get accounts
        await ib.reqAccountSummaryAsync()
        accounts = [acc.account for acc in ib.accountSummary()]
        print(f"Accounts: {accounts}")

        print("\n🎉 Gateway is working! Disconnecting test client...")
        ib.disconnect()
        return True

    except asyncio.TimeoutError:
        print("❌ CONNECTION TIMEOUT after 30 seconds")
        print("\n🔍 Possible causes:")
        print("1. Gateway API is not enabled (check Gateway settings)")
        print("2. Gateway is frozen/hung (needs restart)")
        print("3. Wrong port (try 7497 for paper, 7496 for live)")
        print("4. Firewall blocking connection")
        return False

    except Exception as e:
        print(f"❌ CONNECTION FAILED: {e}")
        print(f"Error type: {type(e).__name__}")
        return False

    finally:
        if ib.isConnected():
            ib.disconnect()


if __name__ == "__main__":
    print("=" * 70)
    print("IB GATEWAY CONNECTION DIAGNOSTIC")
    print("=" * 70)
    print()

    success = asyncio.run(test_connection())

    print()
    print("=" * 70)
    if success:
        print("✅ DIAGNOSIS: Gateway is working normally")
        print("   Your dashboard should be able to connect")
    else:
        print("❌ DIAGNOSIS: Gateway is not responding")
        print("   ACTION REQUIRED: Restart IB Gateway")
        print()
        print("   Steps:")
        print("   1. In IB Gateway: File → Exit")
        print("   2. Wait 15 seconds")
        print("   3. Restart IB Gateway")
        print("   4. Wait for 'Ready' status")
        print("   5. Run this diagnostic again")
    print("=" * 70)

    sys.exit(0 if success else 1)
