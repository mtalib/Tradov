#!/usr/bin/env python3
"""
SPYDER - TWS API Diagnostic Check
================================

Comprehensive diagnostic script to check TWS API connection status
and identify specific issues preventing handshake completion.

This script performs deep diagnostics to understand what's happening
during the API handshake process.
"""

import asyncio
import socket
import time
import sys
import json
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from ib_async import IB, util
    import logging

    print("✅ ib_async imported successfully")
except ImportError as e:
    print(f"❌ Failed to import ib_async: {e}")
    sys.exit(1)


class TWSDiagnosticChecker:
    """
    Comprehensive TWS API diagnostic checker
    """

    def __init__(self):
        self.host = "192.168.1.4"
        self.port = 7497
        self.linux_ip = self.get_linux_ip()
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "network_tests": {},
            "connection_attempts": {},
            "handshake_analysis": {},
            "recommendations": [],
        }

    def get_linux_ip(self):
        """Get Linux machine's IP address"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except:
            return "192.168.1.9"

    def print_header(self):
        """Print diagnostic header"""
        print("🕷️ SPYDER - TWS API DIAGNOSTIC CHECK")
        print("=" * 50)
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🎯 TWS Target: {self.host}:{self.port}")
        print(f"🖥️  Linux IP: {self.linux_ip}")
        print(f"🐍 Python: {sys.version.split()[0]}")
        print()

    def test_network_connectivity(self):
        """Test basic network connectivity"""
        print("🌐 Network Connectivity Tests")
        print("-" * 30)

        # Ping test
        try:
            import subprocess

            result = subprocess.run(
                ["ping", "-c", "3", "-W", "3", self.host],
                capture_output=True,
                text=True,
                timeout=10,
            )

            ping_success = result.returncode == 0
            print(f"   Ping Test: {'✅ SUCCESS' if ping_success else '❌ FAILED'}")

            if ping_success:
                # Extract ping time
                lines = result.stdout.split("\n")
                for line in lines:
                    if "min/avg/max" in line:
                        print(f"   Ping Stats: {line.strip()}")
                        break

            self.results["network_tests"]["ping"] = {
                "success": ping_success,
                "output": result.stdout if ping_success else result.stderr,
            }

        except Exception as e:
            print(f"   Ping Test: ❌ ERROR - {e}")
            self.results["network_tests"]["ping"] = {"success": False, "error": str(e)}

        # Port connectivity test
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            start_time = time.time()
            result = sock.connect_ex((self.host, self.port))
            connection_time = time.time() - start_time
            sock.close()

            port_success = result == 0
            print(
                f"   Port {self.port}: {'✅ ACCESSIBLE' if port_success else '❌ BLOCKED'}"
            )
            if port_success:
                print(f"   Connection Time: {connection_time:.3f}s")

            self.results["network_tests"]["port"] = {
                "success": port_success,
                "connection_time": connection_time,
                "error_code": result,
            }

        except Exception as e:
            print(f"   Port {self.port}: ❌ ERROR - {e}")
            self.results["network_tests"]["port"] = {"success": False, "error": str(e)}

        print()

    def test_raw_socket_communication(self):
        """Test raw socket communication with TWS"""
        print("🔌 Raw Socket Communication Test")
        print("-" * 35)

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)

            print(f"   Connecting to {self.host}:{self.port}...")
            start_time = time.time()
            sock.connect((self.host, self.port))
            connection_time = time.time() - start_time

            print(f"   ✅ Socket connected in {connection_time:.3f}s")

            # Try to send API handshake (basic version negotiation)
            print("   Attempting API handshake...")

            # Send API version request (simplified)
            # This is what ib_async sends during handshake
            handshake_msg = b"API\x00\x00\x00\x01"  # Simplified API handshake
            sock.send(handshake_msg)
            print("   📤 Sent handshake message")

            # Try to receive response
            sock.settimeout(5)
            try:
                response = sock.recv(1024)
                if response:
                    print(f"   📥 Received response: {len(response)} bytes")
                    print(f"   Response (hex): {response.hex()}")
                    self.results["network_tests"]["handshake"] = {
                        "success": True,
                        "response_length": len(response),
                        "response_hex": response.hex(),
                    }
                else:
                    print("   ❌ No response received")
                    self.results["network_tests"]["handshake"] = {
                        "success": False,
                        "error": "No response",
                    }
            except socket.timeout:
                print("   ⏰ Handshake response timeout (5s)")
                self.results["network_tests"]["handshake"] = {
                    "success": False,
                    "error": "Response timeout",
                }

            sock.close()
            print("   🔌 Socket closed cleanly")

        except Exception as e:
            print(f"   ❌ Raw socket test failed: {e}")
            self.results["network_tests"]["handshake"] = {
                "success": False,
                "error": str(e),
            }

        print()

    async def test_ib_async_detailed(self):
        """Detailed ib_async connection test with event monitoring"""
        print("🔍 Detailed ib_async Connection Analysis")
        print("-" * 40)

        # Setup detailed logging
        logging.basicConfig(level=logging.DEBUG)
        util.startLoop()
        util.logToConsole("DEBUG")

        ib = IB()
        ib.RequestTimeout = 20.0

        # Event tracking
        events_received = {
            "connected": False,
            "disconnected": False,
            "errors": [],
            "nextValidId": None,
            "managedAccounts": None,
        }

        # Event handlers
        def on_connected():
            events_received["connected"] = True
            print("   🔌 Connected event received")

        def on_disconnected():
            events_received["disconnected"] = True
            print("   🔌 Disconnected event received")

        def on_error(reqId, errorCode, errorString, contract):
            error_info = f"Error {errorCode}: {errorString}"
            events_received["errors"].append(error_info)
            print(f"   ❌ TWS Error: {error_info}")

        def on_next_valid_id(orderId):
            events_received["nextValidId"] = orderId
            print(f"   📋 NextValidId received: {orderId}")

        def on_managed_accounts(accounts):
            events_received["managedAccounts"] = accounts
            print(f"   💼 ManagedAccounts received: {accounts}")

        # Connect events
        ib.connectedEvent += on_connected
        ib.disconnectedEvent += on_disconnected
        ib.errorEvent += on_error

        # Override callback methods to capture critical handshake messages
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
            print(f"   🚀 Attempting connection (timeout: 20s)...")
            start_time = time.time()

            # Try connection with all optimizations
            await ib.connectAsync(
                host=self.host, port=self.port, clientId=1, timeout=20, readonly=True
            )

            connection_time = time.time() - start_time
            print(f"   ✅ Connection succeeded in {connection_time:.2f}s")

            # Test API calls
            if ib.isConnected():
                print("   🧪 Testing API functionality...")

                try:
                    server_time = await asyncio.wait_for(
                        ib.reqCurrentTimeAsync(), timeout=5
                    )
                    print(f"   ⏰ Server time: {server_time}")
                except Exception as e:
                    print(f"   ⚠️ Server time failed: {e}")

                # Keep connection alive briefly
                await asyncio.sleep(3)

            self.results["connection_attempts"]["ib_async_detailed"] = {
                "success": True,
                "connection_time": connection_time,
                "events": events_received,
            }

        except asyncio.TimeoutError:
            connection_time = time.time() - start_time
            print(f"   ❌ Connection timeout after {connection_time:.2f}s")
            print(f"   🔍 Events received during timeout: {events_received}")

            self.results["connection_attempts"]["ib_async_detailed"] = {
                "success": False,
                "error": "TimeoutError",
                "connection_time": connection_time,
                "events": events_received,
            }

        except Exception as e:
            connection_time = time.time() - start_time
            print(f"   ❌ Connection failed: {e}")

            self.results["connection_attempts"]["ib_async_detailed"] = {
                "success": False,
                "error": str(e),
                "connection_time": connection_time,
                "events": events_received,
            }

        finally:
            if ib.isConnected():
                ib.disconnect()
                print("   🔌 Disconnected cleanly")

        print()

        # Analyze what happened
        self.analyze_handshake_results(events_received)

    def analyze_handshake_results(self, events):
        """Analyze handshake results and provide specific recommendations"""
        print("🔍 Handshake Analysis")
        print("-" * 20)

        analysis = {
            "tcp_connection": events.get("connected", False),
            "api_errors": len(events.get("errors", [])),
            "nextValidId_received": events.get("nextValidId") is not None,
            "managedAccounts_received": events.get("managedAccounts") is not None,
            "diagnosis": "",
            "recommendations": [],
        }

        if events.get("connected"):
            print("   ✅ TCP connection established")
        else:
            print("   ❌ TCP connection failed")
            analysis["diagnosis"] = "TCP connection failure"
            analysis["recommendations"].append(
                "Check TWS is running and API is enabled"
            )

        if events.get("errors"):
            print(f"   ❌ {len(events['errors'])} API errors received:")
            for error in events["errors"]:
                print(f"      • {error}")
            analysis["diagnosis"] = "API errors during handshake"

        if events.get("nextValidId") is not None:
            print(f"   ✅ NextValidId received: {events['nextValidId']}")
        else:
            print("   ❌ NextValidId NOT received")
            analysis["recommendations"].append(
                "TWS not sending nextValidId - check API settings"
            )

        if events.get("managedAccounts"):
            print(f"   ✅ ManagedAccounts received: {events['managedAccounts']}")
        else:
            print("   ❌ ManagedAccounts NOT received")
            analysis["recommendations"].append(
                "TWS not sending managedAccounts - check account status"
            )

        # Determine root cause
        if (
            events.get("connected")
            and not events.get("nextValidId")
            and not events.get("managedAccounts")
        ):
            analysis["diagnosis"] = "TCP connects but TWS not completing API handshake"
            analysis["recommendations"].extend(
                [
                    "Verify TWS API settings: File → Global Configuration → API",
                    "Ensure Linux IP is in Trusted IPs",
                    "Disable any order download settings",
                    "Check TWS API logs for specific errors",
                    "Try restarting TWS completely",
                ]
            )
        elif not events.get("connected"):
            analysis["diagnosis"] = "Cannot establish TCP connection"
            analysis["recommendations"].extend(
                [
                    "Check TWS is running",
                    "Verify port 7497 is accessible",
                    "Check Windows firewall settings",
                ]
            )

        self.results["handshake_analysis"] = analysis

        # Print recommendations
        if analysis["recommendations"]:
            print(f"\n💡 Specific Recommendations:")
            for i, rec in enumerate(analysis["recommendations"], 1):
                print(f"   {i}. {rec}")

        print()

    def generate_diagnostic_report(self):
        """Generate comprehensive diagnostic report"""
        print("📊 DIAGNOSTIC SUMMARY")
        print("=" * 25)

        # Network summary
        network_ok = self.results["network_tests"].get("ping", {}).get(
            "success", False
        ) and self.results["network_tests"].get("port", {}).get("success", False)

        print(f"Network Connectivity: {'✅ GOOD' if network_ok else '❌ ISSUES'}")

        # Connection summary
        connection_ok = (
            self.results["connection_attempts"]
            .get("ib_async_detailed", {})
            .get("success", False)
        )
        print(f"API Connection: {'✅ SUCCESS' if connection_ok else '❌ FAILED'}")

        # Handshake analysis
        handshake = self.results.get("handshake_analysis", {})
        if handshake:
            nextValidId_ok = handshake.get("nextValidId_received", False)
            managedAccounts_ok = handshake.get("managedAccounts_received", False)

            print(f"NextValidId: {'✅ RECEIVED' if nextValidId_ok else '❌ MISSING'}")
            print(
                f"ManagedAccounts: {'✅ RECEIVED' if managedAccounts_ok else '❌ MISSING'}"
            )

        print()

        # Overall diagnosis
        if connection_ok:
            print("🎉 DIAGNOSIS: TWS API connection is working!")
            print("✅ All handshake messages received successfully")
        elif network_ok and not connection_ok:
            print("🔍 DIAGNOSIS: Network OK, but API handshake failing")
            print("❌ TWS is accessible but not completing handshake")
            print("\n🔧 LIKELY CAUSES:")
            print("   • TWS API not properly enabled")
            print("   • Linux IP not in TWS Trusted IPs")
            print("   • Order download settings causing timeout")
            print("   • TWS account/login issues")
        else:
            print("🔍 DIAGNOSIS: Network connectivity issues")
            print("❌ Cannot reach TWS or port is blocked")

        # Save results
        self.save_results()

    def save_results(self):
        """Save diagnostic results to file"""
        results_file = f"tws_diagnostic_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            with open(results_file, "w") as f:
                json.dump(self.results, f, indent=2)
            print(f"\n📁 Detailed results saved to: {results_file}")
        except Exception as e:
            print(f"\n⚠️ Could not save results: {e}")

    async def run_full_diagnostic(self):
        """Run complete diagnostic suite"""
        self.print_header()

        print("Running comprehensive TWS API diagnostics...")
        print("This will test network, socket, and API connectivity.\n")

        # Step 1: Network tests
        self.test_network_connectivity()

        # Step 2: Raw socket test
        self.test_raw_socket_communication()

        # Step 3: Detailed ib_async test
        await self.test_ib_async_detailed()

        # Step 4: Generate report
        self.generate_diagnostic_report()


async def main():
    """Main diagnostic function"""
    try:
        checker = TWSDiagnosticChecker()
        await checker.run_full_diagnostic()

    except KeyboardInterrupt:
        print("\n⚠️ Diagnostic interrupted by user")
    except Exception as e:
        print(f"\n💥 Diagnostic error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
