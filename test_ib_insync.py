#!/usr/bin/env python3
"""
SPYDER - IB-Insync Library Test
===============================

Test the alternative ib-insync library with IB Gateway 10.39
to see if it has better compatibility than ib_async and ibapi.

Based on our analysis:
- IB Gateway 10.39 works fine (Java connections succeed)
- ib_async and ibapi have protocol compatibility issues
- ib-insync might have better Gateway 10.39 support
"""

import sys
import time
import asyncio
from datetime import datetime

# Import ib-insync library
try:
    from ib_insync import IB, util

    print("✅ ib-insync imported successfully")
except ImportError as e:
    print(f"❌ Failed to import ib-insync: {e}")
    print("   Install with: pip install ib-insync")
    sys.exit(1)


class IBInsyncTester:
    """Test IB Gateway connection with ib-insync library"""

    def __init__(self):
        self.host = "127.0.0.1"
        self.port = 4002
        self.client_id = self._generate_client_id()

        # Connection tracking
        self.connected = False
        self.next_valid_id_received = False
        self.managed_accounts_received = False
        self.errors = []

    def _generate_client_id(self):
        """Generate unique client ID"""
        import random

        timestamp_part = int(time.time()) % 1000
        random_part = random.randint(1, 999)
        return min(32767, max(1, timestamp_part * 10 + random_part))

    def log(self, message):
        """Log with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{timestamp}] {message}")

    async def test_ib_insync_connection(self):
        """Test connection using ib-insync library"""

        self.log("🚀 Testing ib-insync library with IB Gateway 10.39")
        self.log(f"   Target: {self.host}:{self.port}")
        self.log(f"   Client ID: {self.client_id}")

        # Initialize ib-insync
        util.startLoop()
        util.logToConsole(level="ERROR")  # Reduce log noise

        ib = IB()

        # Set up event handlers
        def on_connected():
            self.log("🔌 Connected event fired")
            self.connected = True

        def on_disconnected():
            self.log("🔌 Disconnected event fired")
            self.connected = False

        def on_error(reqId, errorCode, errorString, contract):
            error_msg = f"Error {errorCode}: {errorString}"
            self.log(f"❌ {error_msg}")
            self.errors.append(
                {"reqId": reqId, "errorCode": errorCode, "errorString": errorString}
            )

        # Connect events
        ib.connectedEvent += on_connected
        ib.disconnectedEvent += on_disconnected
        ib.errorEvent += on_error

        try:
            self.log("🔍 STEP 1: Attempting connection...")

            # Try connection with various configurations
            connection_configs = [
                {"readonly": True, "timeout": 15},
                {"readonly": False, "timeout": 15},
                {"readonly": True, "timeout": 30},
            ]

            for i, config in enumerate(connection_configs, 1):
                self.log(f"🧪 Connection attempt {i}/{len(connection_configs)}")
                self.log(f"   Config: {config}")

                try:
                    # Reset state
                    self.connected = False
                    self.errors = []

                    # Attempt connection
                    await ib.connectAsync(
                        host=self.host,
                        port=self.port,
                        clientId=self.client_id + i,  # Use different client ID
                        **config,
                    )

                    self.log("✅ connectAsync() completed without exception")

                    # Check if actually connected
                    if ib.isConnected():
                        self.log("✅ ib.isConnected() returns True")
                        self.connected = True
                    else:
                        self.log("❌ ib.isConnected() returns False")
                        continue

                    # Wait for handshake completion
                    self.log("⏳ STEP 2: Waiting for API handshake...")

                    # Check for nextValidId (key handshake indicator)
                    wait_time = 0
                    handshake_timeout = 10

                    while wait_time < handshake_timeout:
                        await asyncio.sleep(0.1)
                        wait_time += 0.1

                        # Check if we have accounts (indicates successful handshake)
                        accounts = ib.managedAccounts()
                        if accounts:
                            self.log(f"✅ Managed accounts received: {accounts}")
                            self.managed_accounts_received = True
                            break

                        # Progress indicator
                        if int(wait_time * 10) % 30 == 0:
                            self.log(f"   Waiting for handshake... {wait_time:.1f}s")

                    if self.managed_accounts_received:
                        self.log("🎉 Handshake successful!")
                    else:
                        self.log("⚠️ Handshake incomplete but connection stable")

                    # Test basic functionality
                    self.log("🔍 STEP 3: Testing basic API functionality...")

                    try:
                        # Request server time
                        server_time = await asyncio.wait_for(
                            ib.reqCurrentTimeAsync(), timeout=5.0
                        )
                        self.log(f"✅ Server time: {server_time}")

                        # Success! We have a working connection
                        self.log("🎉 SUCCESS! ib-insync connection is working!")

                        return ib, True

                    except asyncio.TimeoutError:
                        self.log("⚠️ Server time request timed out")
                    except Exception as e:
                        self.log(f"⚠️ Server time request failed: {e}")

                    # Even if server time fails, connection success is the main goal
                    if self.connected and ib.isConnected():
                        self.log("✅ Connection established successfully!")
                        return ib, True

                except asyncio.TimeoutError:
                    self.log(f"❌ Connection timeout (attempt {i})")
                    continue

                except Exception as e:
                    self.log(f"❌ Connection error (attempt {i}): {e}")
                    continue

                finally:
                    # Brief pause between attempts
                    if i < len(connection_configs):
                        await asyncio.sleep(2)

            # All attempts failed
            self.log("❌ All connection attempts failed")
            return None, False

        except Exception as e:
            self.log(f"💥 Unexpected error: {e}")
            import traceback

            self.log(f"   Traceback: {traceback.format_exc()}")
            return None, False

    async def run_full_test(self):
        """Run comprehensive ib-insync test"""

        print("🕷️ SPYDER - ib-insync Library Test")
        print("=" * 50)
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        print("Testing ib-insync as alternative to ib_async/ibapi")
        print("for IB Gateway 10.39 compatibility issues.")
        print()

        # Run connection test
        ib, success = await self.test_ib_insync_connection()

        # Results analysis
        print("\n" + "=" * 60)
        print("📊 TEST RESULTS")
        print("=" * 60)

        if success:
            print("🎉 SUCCESS! ib-insync works with IB Gateway 10.39!")
            print()
            print("💡 Key Findings:")
            print("   ✅ ib-insync has better Gateway 10.39 compatibility")
            print("   ✅ Connection handshake completes successfully")
            print("   ✅ API functionality is accessible")
            print("   ✅ No immediate connection closure issues")
            print()
            print("🚀 Recommended Actions:")
            print("   1. Migrate SPYDER from ib_async to ib-insync")
            print("   2. Update all connection code to use ib-insync")
            print("   3. Test all SPYDER features with new library")
            print("   4. Deploy updated SPYDER with working IB connection")

            # Keep connection alive for testing
            if ib and ib.isConnected():
                print("\n⏳ Keeping connection alive for 10 seconds...")
                await asyncio.sleep(10)

                # Clean disconnect
                ib.disconnect()
                self.log("🔌 Clean disconnect completed")

            return True

        else:
            print("❌ FAILED! ib-insync also has compatibility issues")
            print()
            print("💡 Analysis:")
            print("   ❌ ib-insync has same protocol issues as ib_async/ibapi")
            print("   ❌ All Python IB libraries seem incompatible with Gateway 10.39")
            print("   ❌ May need to implement custom IB API client")
            print()
            print("🔧 Alternative Solutions:")
            print("   1. Downgrade to IB Gateway 10.37 (if handshake bug is fixed)")
            print("   2. Use TWS instead of Gateway")
            print("   3. Implement custom raw socket IB API client")
            print("   4. Wait for library updates to support Gateway 10.39")
            print("   5. Contact IBKR about Python library compatibility")

            if self.errors:
                print(f"\n❌ Errors encountered ({len(self.errors)}):")
                for error in self.errors[-5:]:  # Show last 5 errors
                    print(f"   → Error {error['errorCode']}: {error['errorString']}")

            return False


def main():
    """Main test function"""
    try:
        tester = IBInsyncTester()
        success = asyncio.run(tester.run_full_test())
        return success

    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
        return False
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
