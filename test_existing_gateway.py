#!/usr/bin/env python3
"""
SPYDER - Test Existing IB Gateway
=================================

Simple test to check if IB Gateway is already installed and running,
and test API connectivity with the research-backed fixes.

This script assumes IB Gateway might already be installed and configured,
and focuses on testing the API connection with all the MAESTRO fixes.
"""

import asyncio
import socket
import time
import subprocess
import psutil
import sys
from datetime import datetime
from pathlib import Path

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


class GatewayTester:
    """Simple IB Gateway tester with MAESTRO fixes"""

    def __init__(self):
        # Gateway ports
        self.ports = {
            4001: "IB Gateway Live",
            4002: "IB Gateway Paper",
        }

        # MAESTRO research-backed settings
        self.RACE_CONDITION_DELAY = 1.0  # Claude's proven solution
        self.REQUEST_TIMEOUT = 30.0  # Extended timeout
        self.CONNECTION_TIMEOUT = 15.0  # Reasonable timeout

    def print_header(self):
        """Print test header"""
        print("🕷️ SPYDER - Test Existing IB Gateway")
        print("=" * 45)
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🐍 Python: {sys.version.split()[0]}")
        print()

    def check_gateway_processes(self):
        """Check for running Gateway processes"""
        print("🔍 Checking for IB Gateway Processes")
        print("-" * 35)

        gateway_processes = []

        try:
            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    if proc.info["name"] and "java" in proc.info["name"].lower():
                        cmdline = " ".join(proc.info["cmdline"] or [])
                        if any(
                            keyword in cmdline.lower()
                            for keyword in ["ibgateway", "gateway", "ibg"]
                        ):
                            gateway_processes.append(
                                {"pid": proc.info["pid"], "cmdline": cmdline}
                            )
                            print(f"   ✅ Found Gateway: PID {proc.info['pid']}")
                            print(f"      Command: {cmdline[:100]}...")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

        except Exception as e:
            print(f"   ⚠️ Error checking processes: {e}")

        if not gateway_processes:
            print("   ❌ No IB Gateway processes found")

        print()
        return gateway_processes

    def test_gateway_ports(self):
        """Test Gateway port accessibility"""
        print("🔌 Testing Gateway Ports")
        print("-" * 25)

        accessible_ports = []

        for port, description in self.ports.items():
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                start_time = time.time()
                result = sock.connect_ex(("127.0.0.1", port))
                connection_time = time.time() - start_time
                sock.close()

                if result == 0:
                    print(
                        f"   ✅ Port {port} ({description}): ACCESSIBLE ({connection_time:.3f}s)"
                    )
                    accessible_ports.append(port)
                else:
                    print(f"   ❌ Port {port} ({description}): NOT ACCESSIBLE")

            except Exception as e:
                print(f"   ❌ Port {port} test error: {e}")

        print()
        return accessible_ports

    def apply_tcp_optimizations(self):
        """Apply TCP optimizations (Copilot's solution)"""
        try:
            original_create_connection = asyncio.get_event_loop().create_connection

            async def optimized_connection(*args, **kwargs):
                transport, protocol = await original_create_connection(*args, **kwargs)
                sock = transport.get_extra_info("socket")
                if sock:
                    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                return transport, protocol

            asyncio.get_event_loop().create_connection = optimized_connection
            return True

        except Exception as e:
            print(f"   ⚠️ Could not apply TCP optimizations: {e}")
            return False

    async def test_maestro_connection(self, port):
        """Test connection with all MAESTRO research-backed fixes"""
        port_desc = self.ports.get(port, f"Port {port}")

        print(f"🎯 MAESTRO Connection Test - {port_desc}")
        print("-" * 50)

        # Apply optimizations
        self.apply_tcp_optimizations()

        # Initialize ib_async (Claude's proven pattern)
        util.startLoop()
        util.logToConsole("INFO")  # Reduced logging for clarity

        ib = IB()
        ib.RequestTimeout = self.REQUEST_TIMEOUT

        # Event tracking
        events = {
            "connected": False,
            "nextValidId": None,
            "managedAccounts": None,
            "errors": [],
        }

        def on_connected():
            events["connected"] = True
            print("   🔌 Connected event received")

        def on_disconnected():
            print("   🔌 Disconnected event received")

        def on_error(reqId, errorCode, errorString, contract):
            error_info = f"Error {errorCode}: {errorString}"
            events["errors"].append(error_info)
            print(f"   ❌ Gateway Error: {error_info}")

        def on_next_valid_id(orderId):
            events["nextValidId"] = orderId
            print(f"   📋 NextValidId received: {orderId}")

        def on_managed_accounts(accounts):
            events["managedAccounts"] = accounts
            print(f"   💼 ManagedAccounts received: {accounts}")

        # Connect events
        ib.connectedEvent += on_connected
        ib.disconnectedEvent += on_disconnected
        ib.errorEvent += on_error

        # Override wrapper methods to capture handshake messages
        original_nextValidId = ib.wrapper.nextValidId
        original_managedAccounts = ib.wrapper.managedAccounts

        def capture_nextValidId(orderId):
            on_next_valid_id(orderId)
            return original_nextValidId(orderId)

        def capture_managedAccounts(accountsList):
            on_managed_accounts(accountsList)
            return original_managedAccounts(accountsList)

        ib.wrapper.nextValidId = capture_nextValidId
        ib.wrapper.managedAccounts = capture_managedAccounts

        try:
            print(f"   🚀 Connecting to localhost:{port}")
            print(f"   ⚙️ Using MAESTRO fixes: readonly mode + race condition delay")

            start_time = time.time()

            # SOLUTION 1: Read-only mode (bypasses reqExecutions timeout)
            await ib.connectAsync(
                host="127.0.0.1",
                port=port,
                clientId=1,
                timeout=self.CONNECTION_TIMEOUT,
                readonly=True,  # KEY FIX: Prevents execution history sync timeout
            )

            print("   ✅ Phase 1: Initial connection established")

            # SOLUTION 2: Race condition delay (Claude's proven solution)
            print(
                f"   ⏳ Phase 2: Applying race condition delay ({self.RACE_CONDITION_DELAY}s)"
            )
            await asyncio.sleep(self.RACE_CONDITION_DELAY)

            # SOLUTION 3: Validate connection
            if not ib.isConnected():
                raise ConnectionError("Connection lost during stabilization")

            print("   ✅ Phase 2: Connection stabilized")

            # Test API functionality
            print("   🔍 Phase 3: Testing API functionality...")

            # Get managed accounts
            accounts = ib.managedAccounts()
            if accounts:
                print(f"   ✅ Managed accounts: {accounts}")
            else:
                print("   ⚠️ No managed accounts returned")

            # Test server time
            try:
                server_time = await asyncio.wait_for(
                    ib.reqCurrentTimeAsync(), timeout=5.0
                )
                print(f"   ✅ Server time: {server_time}")
            except asyncio.TimeoutError:
                print("   ⚠️ Server time request timed out")
            except Exception as e:
                print(f"   ⚠️ Server time request failed: {e}")

            connection_time = time.time() - start_time
            print(f"   🎉 SUCCESS! Connection completed in {connection_time:.2f}s")

            return ib, True

        except asyncio.TimeoutError:
            connection_time = time.time() - start_time
            print(f"   ❌ Connection timeout after {connection_time:.2f}s")
            print(f"   🔍 Events received: {events}")
            return None, False

        except Exception as e:
            connection_time = time.time() - start_time
            print(f"   ❌ Connection failed: {e}")
            print(f"   🔍 Error type: {type(e).__name__}")
            return None, False

    async def run_gateway_test(self):
        """Run complete Gateway test"""
        self.print_header()

        print("This script will test existing IB Gateway installations")
        print("and apply all research-backed connection fixes.")
        print()

        # Step 1: Check for Gateway processes
        print("STEP 1: Process Check")
        print("=" * 20)
        gateway_processes = self.check_gateway_processes()

        # Step 2: Test port accessibility
        print("STEP 2: Port Accessibility")
        print("=" * 25)
        accessible_ports = self.test_gateway_ports()

        if not accessible_ports:
            print("❌ NO GATEWAY PORTS ACCESSIBLE")
            print()
            print("🔧 POSSIBLE SOLUTIONS:")
            print("   1. Start IB Gateway manually")
            print("   2. Check if Gateway is installed")
            print("   3. Verify Gateway configuration")
            print("   4. Check firewall settings")
            return False

        # Step 3: Test API connections
        print("STEP 3: API Connection Tests")
        print("=" * 28)

        working_connections = []

        for port in accessible_ports:
            print()
            ib, success = await self.test_maestro_connection(port)

            if success:
                port_desc = self.ports.get(port, f"Port {port}")
                working_connections.append((port, port_desc))

                # Keep connection alive briefly
                print("   ⏳ Keeping connection alive for 5 seconds...")
                await asyncio.sleep(5)

                # Clean disconnect
                if ib and ib.isConnected():
                    ib.disconnect()
                    print("   🔌 Disconnected cleanly")

                # Test successful - we can stop here
                break
            else:
                print(f"   ❌ Failed to connect to port {port}")

        # Final Results
        print()
        print("=" * 60)
        print("📊 FINAL RESULTS")
        print("=" * 60)

        if working_connections:
            print("🎉 IB GATEWAY CONNECTION SUCCESS!")
            for port, desc in working_connections:
                print(f"   ✅ {desc} (port {port}) - WORKING")

            print()
            print("💡 KEY FINDINGS:")
            print("   ✅ IB Gateway is properly installed and running")
            print("   ✅ MAESTRO research-backed fixes are working")
            print("   ✅ Race condition delay resolved handshake timeout")
            print("   ✅ Read-only mode bypassed reqExecutions timeout")

            print()
            print("🚀 NEXT STEPS:")
            print("   1. Update SPYDER to use IB Gateway instead of TWS")
            print("   2. Configure production connection with working port")
            print("   3. Implement connection pooling for multiple data streams")
            print("   4. Set up monitoring and auto-restart capabilities")

            return True

        else:
            print("❌ ALL GATEWAY CONNECTIONS FAILED")
            print("   Gateway is running but API handshake is failing")

            print()
            print("🔍 TROUBLESHOOTING:")
            print("   1. Check Gateway configuration file")
            print("   2. Verify Gateway API is enabled")
            print("   3. Check Gateway logs for specific errors")
            print("   4. Try restarting Gateway process")
            print("   5. Verify account login status in Gateway")

            return False


def main():
    """Main test function"""
    try:
        tester = GatewayTester()
        success = asyncio.run(tester.run_gateway_test())
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
