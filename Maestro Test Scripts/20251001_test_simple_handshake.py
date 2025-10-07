#!/usr/bin/env python3
"""
Simple Handshake Timeout Test for Gateway 10.37
Tests actual handshake without API method issues
"""

import sys
import time
from datetime import datetime

sys.path.append("/home/adam/Projects/Spyder")

try:
    from ib_async import IB, Stock

    print("✅ Using ib_async 1.0.3 for Gateway 10.37 compatibility")
except ImportError as e:
    print(f"❌ Error importing ib_async: {e}")
    sys.exit(1)


def test_simple_handshake():
    """Simple handshake test without complex API calls"""
    print("🔬 SIMPLE HANDSHAKE TEST FOR GATEWAY 10.37")
    print(f"📅 Started: {datetime.now()}")
    print("=" * 50)

    successes = 0
    failures = 0

    # Test 3 different client IDs
    for client_id in [200, 201, 202]:
        print(f"\n🔄 Testing Client ID {client_id}")

        ib = IB()
        start_time = time.time()

        try:
            print(f"   📡 Connecting to 127.0.0.1:4002...")

            # Use default timeout (should be around 20 seconds)
            ib.connect("127.0.0.1", 4002, clientId=client_id)

            connect_time = time.time() - start_time
            print(f"   ✅ Connected in {connect_time:.2f}s")

            # Just check if we're connected and get basic info
            print(f"   🔍 Testing basic functionality...")

            # Wait a moment for connection to stabilize
            ib.sleep(1)

            # Try to get accounts (this is usually the first thing that fails)
            accounts = ib.managedAccounts()
            if accounts:
                print(f"   💼 Accounts: {accounts}")
                print(f"   ✅ Handshake SUCCESSFUL!")
                successes += 1
            else:
                print(f"   ⚠️  Connected but no accounts retrieved")
                failures += 1

            ib.disconnect()
            print(f"   🔌 Disconnected cleanly")

        except Exception as e:
            error_time = time.time() - start_time
            print(f"   ❌ Failed after {error_time:.2f}s: {str(e)}")

            if "timeout" in str(e).lower() or "TimeoutError" in str(e):
                print(f"   🚨 TIMEOUT ERROR - handshake failed!")

            failures += 1

            try:
                ib.disconnect()
            except:
                pass

        # Brief pause between tests
        time.sleep(3)

    # Results
    print("\n" + "=" * 50)
    print("📊 HANDSHAKE TEST RESULTS")
    print("=" * 50)

    total = successes + failures
    success_rate = (successes / total) * 100 if total > 0 else 0

    print(f"✅ Successful Handshakes: {successes}")
    print(f"❌ Failed Handshakes: {failures}")
    print(f"📈 Success Rate: {success_rate:.1f}%")

    print(f"\n🎯 DIAGNOSIS:")

    if success_rate >= 67:  # 2 out of 3 or better
        print("✅ HANDSHAKE WORKING!")
        print("   Gateway 10.37 handshake is functioning properly")
        print("   Data flow issues may be due to other factors")
        return True
    elif success_rate > 0:
        print("⚠️  INTERMITTENT HANDSHAKE ISSUES")
        print("   Some connections work, others fail")
        print("   This could explain inconsistent data flow")
        return False
    else:
        print("❌ HANDSHAKE COMPLETELY BROKEN!")
        print("   No successful connections - this is the root cause")
        print("   Dashboard cannot get data without working handshake")
        return False


if __name__ == "__main__":
    print("Testing handshake functionality...")
    success = test_simple_handshake()

    print(f"\n📅 Test completed: {datetime.now()}")

    if success:
        print(
            "\n🔧 RECOMMENDATION: Handshake is working - check dashboard configuration"
        )
    else:
        print("\n🔧 RECOMMENDATION: Fix handshake issues first, then test dashboard")
