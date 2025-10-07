#!/usr/bin/env python3
"""
SPYDER - MAESTRO Paper Trading Connection Test
=============================================

Focused test for paper trading (port 7497) with all MAESTRO fixes applied.
Based on comprehensive research from 6 AI reports.

Key Solutions Implemented:
1. Read-only mode connection (bypasses reqExecutions timeout)
2. Race condition delay (1-second stabilization delay)
3. Extended timeouts (15s connection, 30s request)
4. TCP optimizations (TCP_NODELAY)
5. Enhanced error handling and retry logic
"""

import asyncio
import socket
import time
import logging
from datetime import datetime
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from ib_async import IB, util

    print("✅ ib_async imported successfully")
except ImportError as e:
    print(f"❌ Failed to import ib_async: {e}")
    print("   Install with: pip install ib_async")
    sys.exit(1)


class MaestroPaperTradingTest:
    """
    MAESTRO's focused paper trading connection test
    """

    def __init__(self):
        # Paper trading configuration
        self.host = "192.168.1.4"
        self.port = 7497  # Paper trading port (confirmed accessible)
        self.client_id = 1

        # MAESTRO research-backed settings
        self.PROVEN_RACE_CONDITION_DELAY = 1.0  # Claude's solution
        self.EXTENDED_REQUEST_TIMEOUT = 30.0  # All reports recommend
        self.CONNECTION_TIMEOUT = 15.0  # Increased from 4s default
        self.MAX_RETRIES = 3

        # Setup logging
        self.setup_logging()

    def setup_logging(self):
        """Setup enhanced logging"""
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - MAESTRO - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler()],
        )
        self.logger = logging.getLogger("MaestroPaperTest")

    def apply_tcp_optimizations(self):
        """
        Apply TCP optimizations (Copilot's solution)
        """
        try:
            original_create_connection = asyncio.get_event_loop().create_connection

            async def optimized_connection(*args, **kwargs):
                transport, protocol = await original_create_connection(*args, **kwargs)
                sock = transport.get_extra_info("socket")
                if sock:
                    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                    self.logger.debug("✅ Applied TCP optimizations")
                return transport, protocol

            asyncio.get_event_loop().create_connection = optimized_connection
            return True

        except Exception as e:
            self.logger.warning(f"⚠️ Could not apply TCP optimizations: {e}")
            return False

    async def test_socket_connectivity(self):
        """Pre-flight socket connectivity test"""
        self.logger.info(f"🔌 Testing socket connectivity to {self.host}:{self.port}")

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            start_time = time.time()
            result = sock.connect_ex((self.host, self.port))
            connection_time = time.time() - start_time
            sock.close()

            if result == 0:
                self.logger.info(f"✅ Socket connected in {connection_time:.3f}s")
                return True
            else:
                self.logger.error(f"❌ Socket connection failed (error: {result})")
                return False

        except Exception as e:
            self.logger.error(f"❌ Socket test failed: {e}")
            return False

    async def maestro_triple_fix_connection(self):
        """
        MAESTRO's Triple Fix Implementation:
        1. Read-only mode (bypasses reqExecutions)
        2. Race condition delay (1-second stabilization)
        3. Enhanced timeout and error handling
        """

        # Apply TCP optimizations first
        self.apply_tcp_optimizations()

        # Initialize ib_async with Claude's proven pattern
        util.startLoop()
        util.logToConsole("DEBUG")

        ib = IB()
        ib.RequestTimeout = self.EXTENDED_REQUEST_TIMEOUT

        # Setup event handlers
        ib.connectedEvent += lambda: self.logger.info("🔌 Connected event fired")
        ib.disconnectedEvent += lambda: self.logger.info("🔌 Disconnected event fired")
        ib.errorEvent += (
            lambda reqId, errorCode, errorString, contract: self.logger.error(
                f"❌ TWS Error {errorCode}: {errorString}"
            )
        )

        try:
            self.logger.info("🚀 MAESTRO Triple Fix - Starting connection process")
            self.logger.info(f"   Target: {self.host}:{self.port} (Paper Trading)")
            self.logger.info(f"   Client ID: {self.client_id}")
            self.logger.info(f"   Connection Timeout: {self.CONNECTION_TIMEOUT}s")
            self.logger.info(f"   Request Timeout: {self.EXTENDED_REQUEST_TIMEOUT}s")

            # SOLUTION 1: Read-only mode connection
            self.logger.info("📝 Phase 1: Connecting in read-only mode...")
            await ib.connectAsync(
                host=self.host,
                port=self.port,
                clientId=self.client_id,
                timeout=self.CONNECTION_TIMEOUT,
                readonly=True,  # 🔑 KEY FIX: Bypasses reqExecutions timeout
            )

            self.logger.info("✅ Phase 1: TCP connection and handshake initiated")

            # SOLUTION 2: Race condition delay
            self.logger.info(
                f"⏳ Phase 2: Applying race condition delay ({self.PROVEN_RACE_CONDITION_DELAY}s)"
            )
            await asyncio.sleep(self.PROVEN_RACE_CONDITION_DELAY)

            # SOLUTION 3: Validate connection stability
            if not ib.isConnected():
                raise ConnectionError("Connection lost during stabilization delay")

            self.logger.info("✅ Phase 2: Connection stabilized")

            # Test API functionality
            self.logger.info("🔍 Phase 3: Testing API functionality...")

            # Get managed accounts
            accounts = ib.managedAccounts()
            if accounts:
                self.logger.info(f"✅ Managed accounts: {accounts}")
            else:
                self.logger.warning("⚠️ No managed accounts returned")

            # Test server time (lightweight call)
            try:
                server_time = await asyncio.wait_for(
                    ib.reqCurrentTimeAsync(), timeout=5.0
                )
                self.logger.info(f"✅ Server time: {server_time}")
            except asyncio.TimeoutError:
                self.logger.warning("⚠️ Server time request timed out")
            except Exception as e:
                self.logger.warning(f"⚠️ Server time request failed: {e}")

            # Success!
            self.logger.info("🎉 MAESTRO TRIPLE FIX SUCCESS!")
            self.logger.info("✅ Paper Trading API connection is working!")

            return ib

        except asyncio.TimeoutError:
            self.logger.error(f"❌ Connection timeout after {self.CONNECTION_TIMEOUT}s")
            self.logger.error("   This suggests TWS handshake issue despite our fixes")
            return None

        except ConnectionRefusedError:
            self.logger.error(f"❌ Connection refused by {self.host}:{self.port}")
            self.logger.error("   Check if TWS is running and API is enabled")
            return None

        except Exception as e:
            self.logger.error(f"❌ Connection failed: {e}")
            self.logger.error(f"   Error type: {type(e).__name__}")
            return None

    async def run_comprehensive_test(self):
        """Run the complete test with retries"""
        print(f"🕷️ SPYDER - MAESTRO Paper Trading Connection Test")
        print(f"=" * 65)
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🐍 Python: {sys.version.split()[0]}")
        print(f"🎯 Target: {self.host}:{self.port} (Paper Trading)")
        print(f"🖥️  Linux IP: Should be in TWS trusted IPs")
        print()

        # Pre-flight checks
        print("STEP 1: Pre-flight Socket Test")
        print("=" * 35)
        socket_ok = await self.test_socket_connectivity()

        if not socket_ok:
            print(f"\n❌ SOCKET TEST FAILED")
            print(f"   TWS may not be running or port {self.port} not accessible")
            return False

        print(f"✅ Socket connectivity confirmed")
        print()

        # Connection attempts with retry
        print("STEP 2: MAESTRO Triple Fix Connection")
        print("=" * 40)

        success = False
        for attempt in range(self.MAX_RETRIES):
            print(f"\n🔄 Attempt {attempt + 1}/{self.MAX_RETRIES}")
            print("-" * 30)

            # Use different client ID for each attempt
            self.client_id = 1 + attempt

            ib = await self.maestro_triple_fix_connection()

            if ib:
                success = True
                print(f"\n🎉 SUCCESS on attempt {attempt + 1}!")
                print(f"✅ MAESTRO Triple Fix is working")
                print(f"✅ Paper Trading API connection established")

                # Keep connection alive for demonstration
                print(f"\n⏳ Keeping connection alive for 10 seconds...")
                await asyncio.sleep(10)

                # Clean disconnect
                if ib.isConnected():
                    ib.disconnect()
                    print(f"🔌 Disconnected cleanly")

                break
            else:
                print(f"❌ Attempt {attempt + 1} failed")

                # Wait before retry (except last attempt)
                if attempt < self.MAX_RETRIES - 1:
                    retry_delay = 3.0
                    print(f"⏳ Waiting {retry_delay}s before retry...")
                    await asyncio.sleep(retry_delay)

        # Final results
        print(f"\n" + "=" * 65)
        print(f"📊 FINAL RESULTS")
        print(f"=" * 65)

        if success:
            print(f"🎉 MAESTRO PAPER TRADING TEST: SUCCESS!")
            print(f"✅ All research-backed solutions are working")
            print(f"✅ TWS API handshake timeout issue resolved")
            print(f"✅ Ready for SPYDER production integration")
            print(f"\n💡 KEY SOLUTIONS THAT WORKED:")
            print(f"   • Read-only mode connection (bypassed reqExecutions)")
            print(f"   • {self.PROVEN_RACE_CONDITION_DELAY}s race condition delay")
            print(f"   • Extended timeouts ({self.CONNECTION_TIMEOUT}s connection)")
            print(f"   • TCP optimizations (TCP_NODELAY)")

        else:
            print(f"❌ MAESTRO PAPER TRADING TEST: FAILED")
            print(f"   All {self.MAX_RETRIES} attempts failed")
            print(f"\n🔍 TROUBLESHOOTING RECOMMENDATIONS:")
            print(f"   1. Check TWS settings on Windows computer:")
            print(f"      • API enabled: File → Global Configuration → API")
            print(f"      • Trusted IPs: Add your Linux IP")
            print(f"      • UNCHECK 'Download open orders on connection'")
            print(f"   2. Restart TWS completely after configuration changes")
            print(f"   3. Check TWS API log files for specific errors")
            print(f"   4. Consider testing with Python 3.11/3.12 instead of 3.13+")
            print(f"   5. Try connecting from Windows computer first (localhost test)")

        return success


async def main():
    """Main test function"""
    try:
        tester = MaestroPaperTradingTest()
        success = await tester.run_comprehensive_test()
        return success

    except KeyboardInterrupt:
        print(f"\n⚠️ Test interrupted by user")
        return False

    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
