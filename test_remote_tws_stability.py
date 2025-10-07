#!/usr/bin/env python3
"""
Remote TWS Stability Test - Based on Proven Gateway Patterns
===========================================================

This script applies the stability patterns proven successful with IB Gateway
to test and validate remote TWS connections. Based on comprehensive stability
research from Gateway 10.37 optimization work.

Key Patterns Applied:
- Professional client ID allocation (1-10)
- Event-driven connection handling
- Exponential backoff reconnection
- API flood protection principles
- Connection timeout optimization
- Proper cleanup patterns

Author: Mohamed Talib
Based on: Gateway Stability Achievement Reports (Oct 2025)
"""

import asyncio
import logging
import socket
import struct
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add Spyder to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from ib_async import IB, util

    IB_ASYNC_AVAILABLE = True
except ImportError:
    IB_ASYNC_AVAILABLE = False
    print("❌ ib_async not available. Install with: pip install ib_async")

# Import configuration
try:
    from config.config import IB_CONFIG
except ImportError:
    # Fallback configuration
    IB_CONFIG = {
        "gateway": {
            "paper": {"host": "192.168.1.244", "port": 7497},
            "live": {"host": "192.168.1.244", "port": 7496},
        }
    }


class TWSStabilityTester:
    """
    TWS Stability Tester using proven Gateway patterns

    This class implements the stability patterns that were successful
    with IB Gateway 10.37 and adapts them for remote TWS testing.
    """

    def __init__(self, host: str = None, port: int = None):
        # Use configured values or defaults
        self.host = host or IB_CONFIG.get("gateway", {}).get("paper", {}).get(
            "host", "192.168.1.244"
        )
        self.port = port or IB_CONFIG.get("gateway", {}).get("paper", {}).get(
            "port", 7497
        )

        # Professional client ID allocation (learned from Gateway work)
        self.client_ids = {
            "test": 1,  # Primary test client
            "monitor": 2,  # Monitoring/health checks
            "market_data": 3,  # Market data subscriptions
            "backup": 4,  # Backup/failover client
        }

        # Connection stability parameters (from Gateway research)
        self.connection_timeout = 30  # Increased from default 10s
        self.max_reconnect_attempts = 5
        self.inter_client_delay = 2.0  # Delay between client connections

        # Rate limiting (API flood protection)
        self.max_requests_per_second = 10  # Conservative for TWS
        self.request_timestamps = []

        # Test results storage
        self.test_results = {
            "timestamp": datetime.now().isoformat(),
            "target": f"{self.host}:{self.port}",
            "tests": {},
            "summary": {},
        }

        # Setup logging
        self.setup_logging()

    def setup_logging(self):
        """Setup logging with ERROR-only production pattern"""
        logging.basicConfig(
            level=logging.ERROR,  # ERROR-only like proven Gateway pattern
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler("tws_stability_test.log"),
            ],
        )
        self.logger = logging.getLogger(__name__)

    def log_info(self, message: str):
        """Console info logging (not saved to file)"""
        print(f"ℹ️  {message}")

    def log_success(self, message: str):
        """Console success logging"""
        print(f"✅ {message}")

    def log_warning(self, message: str):
        """Console warning logging"""
        print(f"⚠️  {message}")

    def log_error(self, message: str):
        """Console and file error logging"""
        print(f"❌ {message}")
        self.logger.error(message)

    def log_debug(self, message: str):
        """Debug logging"""
        print(f"🔍 {message}")

    def calculate_backoff(self, attempt: int) -> int:
        """Exponential backoff with max 60s (from Gateway patterns)"""
        return min(2**attempt, 60)

    def check_rate_limit(self) -> bool:
        """API flood protection (from Gateway work)"""
        now = time.time()
        # Clean old timestamps
        self.request_timestamps = [
            ts for ts in self.request_timestamps if now - ts < 1.0
        ]

        if len(self.request_timestamps) >= self.max_requests_per_second:
            return False

        self.request_timestamps.append(now)
        return True

    def test_socket_connectivity(self) -> Dict:
        """Test basic socket connectivity (Gateway pattern: socket-only tests)"""
        self.log_info(f"Testing socket connectivity to {self.host}:{self.port}")

        test_result = {
            "test_name": "socket_connectivity",
            "success": False,
            "response_time_ms": None,
            "error": None,
            "details": {},
        }

        try:
            start_time = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)

            result = sock.connect_ex((self.host, self.port))
            response_time = (time.time() - start_time) * 1000

            sock.close()

            if result == 0:
                test_result["success"] = True
                test_result["response_time_ms"] = round(response_time, 2)
                self.log_success(f"Socket connectivity OK ({response_time:.1f}ms)")
            else:
                test_result["error"] = f"Socket connection failed with code {result}"
                self.log_error(f"Socket connection failed: {result}")

        except Exception as e:
            test_result["error"] = str(e)
            self.log_error(f"Socket test exception: {e}")

        return test_result

    def test_port_stability(self) -> Dict:
        """Test port stability with multiple connections (Gateway pattern)"""
        self.log_info("Testing port stability (5 consecutive connections)")

        test_result = {
            "test_name": "port_stability",
            "success": False,
            "connections_successful": 0,
            "connections_total": 5,
            "response_times": [],
            "error": None,
        }

        successful_connections = 0
        response_times = []

        for i in range(5):
            try:
                start_time = time.time()
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)

                result = sock.connect_ex((self.host, self.port))
                response_time = (time.time() - start_time) * 1000

                sock.close()

                if result == 0:
                    successful_connections += 1
                    response_times.append(round(response_time, 2))
                    self.log_debug(f"Connection {i + 1}/5: OK ({response_time:.1f}ms)")
                else:
                    self.log_debug(f"Connection {i + 1}/5: FAILED ({result})")

                time.sleep(0.5)  # Brief delay between tests

            except Exception as e:
                self.log_debug(f"Connection {i + 1}/5: ERROR ({e})")

        test_result["connections_successful"] = successful_connections
        test_result["response_times"] = response_times
        test_result["success"] = successful_connections == 5

        if test_result["success"]:
            avg_time = sum(response_times) / len(response_times)
            self.log_success(
                f"Port stability OK (5/5 connections, avg {avg_time:.1f}ms)"
            )
        else:
            test_result["error"] = (
                f"Only {successful_connections}/5 connections successful"
            )
            self.log_warning(
                f"Port stability issue: {successful_connections}/5 connections"
            )

        return test_result

    def test_api_handshake(self, client_id: int = 1) -> Dict:
        """Test TWS API handshake (from Gateway research)"""
        self.log_info(f"Testing API handshake with client ID {client_id}")

        test_result = {
            "test_name": "api_handshake",
            "client_id": client_id,
            "success": False,
            "handshake_time_ms": None,
            "response_received": False,
            "response_length": 0,
            "error": None,
        }

        try:
            start_time = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)

            # Connect
            sock.connect((self.host, self.port))

            # Send API prefix
            sock.send(b"API\0")

            # Send version info (TWS API v38, min version 176)
            version_msg = f"v{38}..{176}"
            version_bytes = version_msg.encode("utf-8")
            version_length = len(version_bytes)
            length_header = struct.pack(">I", version_length)
            sock.send(length_header + version_bytes)

            # Send client ID
            client_msg = str(client_id)
            client_bytes = client_msg.encode("utf-8")
            client_length = len(client_bytes)
            client_header = struct.pack(">I", client_length)
            sock.send(client_header + client_bytes)

            # Wait for response
            sock.settimeout(5)
            response = sock.recv(1024)

            handshake_time = (time.time() - start_time) * 1000

            if response:
                test_result["success"] = True
                test_result["handshake_time_ms"] = round(handshake_time, 2)
                test_result["response_received"] = True
                test_result["response_length"] = len(response)
                self.log_success(
                    f"API handshake successful ({handshake_time:.1f}ms, {len(response)} bytes)"
                )
            else:
                test_result["error"] = "No response from TWS"
                self.log_error("API handshake failed: No response")

            sock.close()

        except socket.timeout:
            test_result["error"] = "Handshake timeout"
            self.log_error("API handshake timeout")
        except Exception as e:
            test_result["error"] = str(e)
            self.log_error(f"API handshake error: {e}")

        return test_result

    async def test_ib_async_connection(self, client_id: int = 1) -> Dict:
        """Test ib_async connection with proven patterns"""
        self.log_info(f"Testing ib_async connection (Client ID {client_id})")

        test_result = {
            "test_name": "ib_async_connection",
            "client_id": client_id,
            "success": False,
            "connection_time_ms": None,
            "account_info": None,
            "error": None,
        }

        if not IB_ASYNC_AVAILABLE:
            test_result["error"] = "ib_async not available"
            self.log_error("ib_async not available for testing")
            return test_result

        ib = IB()

        try:
            # Event-driven pattern (from Gateway work)
            connected_event = asyncio.Event()
            error_messages = []

            def on_connected():
                self.log_debug("ib_async connected event received")
                connected_event.set()

            def on_disconnected():
                self.log_debug("ib_async disconnected event received")

            def on_error(reqId, errorCode, errorString, contract):
                error_msg = f"Error {errorCode}: {errorString}"
                error_messages.append(error_msg)
                self.log_debug(f"ib_async error: {error_msg}")

            # Attach event handlers BEFORE connecting (Gateway pattern)
            ib.connectedEvent += on_connected
            ib.disconnectedEvent += on_disconnected
            ib.errorEvent += on_error

            # Connection with timeout (increased from Gateway research)
            start_time = time.time()
            await ib.connectAsync(
                host=self.host,
                port=self.port,
                clientId=client_id,
                timeout=self.connection_timeout,
            )

            # Wait for connected event
            await asyncio.wait_for(connected_event.wait(), timeout=5)

            connection_time = (time.time() - start_time) * 1000

            if ib.isConnected():
                test_result["success"] = True
                test_result["connection_time_ms"] = round(connection_time, 2)

                # Get account info
                try:
                    accounts = ib.managedAccounts()
                    test_result["account_info"] = accounts
                    self.log_success(
                        f"ib_async connection OK ({connection_time:.1f}ms)"
                    )
                    if accounts:
                        self.log_info(f"Managed accounts: {accounts}")
                except Exception as e:
                    self.log_debug(f"Could not get account info: {e}")
            else:
                test_result["error"] = "Connected but isConnected() returned False"

        except asyncio.TimeoutError:
            test_result["error"] = "Connection timeout"
            self.log_error(f"ib_async connection timeout ({self.connection_timeout}s)")
        except Exception as e:
            test_result["error"] = str(e)
            self.log_error(f"ib_async connection error: {e}")
        finally:
            # Proper cleanup (from Gateway patterns)
            if ib.isConnected():
                ib.disconnect()
                await asyncio.sleep(0.5)  # Brief delay for cleanup

        return test_result

    def test_multiple_client_ids(self) -> Dict:
        """Test multiple client IDs (professional allocation pattern)"""
        self.log_info("Testing multiple client ID allocation")

        test_result = {
            "test_name": "multiple_client_ids",
            "clients_tested": [],
            "clients_successful": [],
            "clients_failed": [],
            "success": False,
            "error": None,
        }

        for client_name, client_id in self.client_ids.items():
            self.log_debug(f"Testing {client_name} (Client ID {client_id})")

            handshake_result = self.test_api_handshake(client_id)
            test_result["clients_tested"].append(
                {
                    "name": client_name,
                    "client_id": client_id,
                    "success": handshake_result["success"],
                }
            )

            if handshake_result["success"]:
                test_result["clients_successful"].append(client_id)
            else:
                test_result["clients_failed"].append(client_id)

            # Inter-client delay (from Gateway research)
            time.sleep(self.inter_client_delay)

        success_count = len(test_result["clients_successful"])
        total_count = len(test_result["clients_tested"])

        test_result["success"] = success_count > 0

        if success_count == total_count:
            self.log_success(
                f"All client IDs successful ({success_count}/{total_count})"
            )
        elif success_count > 0:
            self.log_warning(
                f"Partial success ({success_count}/{total_count} client IDs)"
            )
        else:
            test_result["error"] = "No client IDs successful"
            self.log_error("All client IDs failed")

        return test_result

    async def run_comprehensive_test(self) -> Dict:
        """Run comprehensive stability test suite"""
        self.log_info("Starting comprehensive TWS stability test")
        self.log_info(f"Target: {self.host}:{self.port}")
        self.log_info(f"Using patterns from Gateway stability research")
        print("=" * 60)

        # Test 1: Socket connectivity
        print("\n🧪 Test 1: Socket Connectivity")
        socket_result = self.test_socket_connectivity()
        self.test_results["tests"]["socket_connectivity"] = socket_result

        if not socket_result["success"]:
            self.log_error("Socket connectivity failed - aborting further tests")
            self.test_results["summary"]["overall_success"] = False
            self.test_results["summary"]["critical_error"] = (
                "Socket connectivity failed"
            )
            return self.test_results

        # Test 2: Port stability
        print("\n🧪 Test 2: Port Stability")
        stability_result = self.test_port_stability()
        self.test_results["tests"]["port_stability"] = stability_result

        # Test 3: API handshake (single client)
        print("\n🧪 Test 3: API Handshake (Client ID 1)")
        handshake_result = self.test_api_handshake(1)
        self.test_results["tests"]["api_handshake"] = handshake_result

        # Test 4: Multiple client IDs
        print("\n🧪 Test 4: Multiple Client ID Allocation")
        multi_client_result = self.test_multiple_client_ids()
        self.test_results["tests"]["multiple_client_ids"] = multi_client_result

        # Test 5: ib_async connection
        if IB_ASYNC_AVAILABLE:
            print("\n🧪 Test 5: ib_async Connection")
            ib_async_result = await self.test_ib_async_connection(1)
            self.test_results["tests"]["ib_async_connection"] = ib_async_result
        else:
            self.log_warning("Skipping ib_async test - library not available")

        # Generate summary
        self.generate_summary()

        return self.test_results

    def generate_summary(self):
        """Generate test summary and recommendations"""
        tests = self.test_results["tests"]

        # Count successes
        successful_tests = [
            name for name, result in tests.items() if result.get("success", False)
        ]
        total_tests = len(tests)

        # Overall assessment
        critical_tests = ["socket_connectivity", "api_handshake"]
        critical_success = all(
            tests.get(test, {}).get("success", False)
            for test in critical_tests
            if test in tests
        )

        self.test_results["summary"] = {
            "total_tests": total_tests,
            "successful_tests": len(successful_tests),
            "success_rate": len(successful_tests) / total_tests
            if total_tests > 0
            else 0,
            "overall_success": critical_success,
            "successful_test_names": successful_tests,
        }

        # Generate recommendations
        recommendations = []

        if not tests.get("socket_connectivity", {}).get("success", False):
            recommendations.append("Check network connectivity and firewall settings")

        if not tests.get("api_handshake", {}).get("success", False):
            recommendations.extend(
                [
                    "Verify TWS API settings: 'Enable ActiveX and Socket Clients' must be checked",
                    "Verify TWS API settings: 'Read-Only API' must be UNCHECKED",
                    "Add your IP (192.168.1.9) to TWS 'Trusted IPs'",
                    "Restart TWS completely after configuration changes",
                ]
            )

        if tests.get("ib_async_connection", {}).get("success", False):
            recommendations.append(
                "TWS API is working - your connection should be stable"
            )
        elif "ib_async_connection" in tests:
            recommendations.append(
                "Consider increasing connection timeout or checking client ID conflicts"
            )

        self.test_results["summary"]["recommendations"] = recommendations

    def print_results(self):
        """Print formatted test results"""
        print("\n" + "=" * 60)
        print("📊 TWS STABILITY TEST RESULTS")
        print("=" * 60)

        summary = self.test_results["summary"]

        # Overall status
        if summary.get("overall_success", False):
            print("✅ Overall Status: TWS CONNECTION WORKING")
            print("   Your remote TWS setup should be stable!")
        else:
            print("❌ Overall Status: TWS CONNECTION ISSUES DETECTED")
            print("   Configuration changes needed on Windows computer")

        print(
            f"\n📈 Test Results: {summary['successful_tests']}/{summary['total_tests']} passed"
        )
        print(f"   Success Rate: {summary['success_rate'] * 100:.1f}%")

        # Individual test results
        print("\n🔍 Individual Test Results:")
        for test_name, result in self.test_results["tests"].items():
            status = "✅" if result.get("success", False) else "❌"
            print(f"   {status} {test_name}")
            if result.get("error"):
                print(f"      Error: {result['error']}")

        # Recommendations
        if summary.get("recommendations"):
            print("\n🔧 Recommendations:")
            for i, rec in enumerate(summary["recommendations"], 1):
                print(f"   {i}. {rec}")

        # Key metrics
        print("\n📊 Key Metrics:")
        if "socket_connectivity" in self.test_results["tests"]:
            socket_test = self.test_results["tests"]["socket_connectivity"]
            if socket_test.get("response_time_ms"):
                print(f"   Network Latency: {socket_test['response_time_ms']}ms")

        if "api_handshake" in self.test_results["tests"]:
            api_test = self.test_results["tests"]["api_handshake"]
            if api_test.get("handshake_time_ms"):
                print(f"   API Handshake: {api_test['handshake_time_ms']}ms")

        if "ib_async_connection" in self.test_results["tests"]:
            ib_test = self.test_results["tests"]["ib_async_connection"]
            if ib_test.get("connection_time_ms"):
                print(f"   ib_async Connection: {ib_test['connection_time_ms']}ms")
            if ib_test.get("account_info"):
                print(f"   Accounts: {ib_test['account_info']}")

        print("\n" + "=" * 60)

    def save_results(self, filename: str = None):
        """Save test results to JSON file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"tws_stability_test_{timestamp}.json"

        try:
            import json

            with open(filename, "w") as f:
                json.dump(self.test_results, f, indent=2)
            self.log_success(f"Results saved to {filename}")
        except Exception as e:
            self.log_error(f"Failed to save results: {e}")


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="TWS Stability Test - Based on Gateway Patterns"
    )
    parser.add_argument("--host", default=None, help="TWS host IP address")
    parser.add_argument("--port", type=int, default=None, help="TWS port")
    parser.add_argument(
        "--save-results", action="store_true", help="Save results to JSON file"
    )
    parser.add_argument(
        "--client-id", type=int, default=1, help="Client ID for single tests"
    )

    args = parser.parse_args()

    # Create tester
    tester = TWSStabilityTester(host=args.host, port=args.port)

    print("🔬 TWS STABILITY TESTER")
    print("Based on proven IB Gateway stability patterns")
    print(f"Target: {tester.host}:{tester.port}")
    print("This test applies lessons learned from Gateway 10.37 optimization")

    # Run comprehensive test
    try:
        results = await tester.run_comprehensive_test()

        # Print results
        tester.print_results()

        # Save if requested
        if args.save_results:
            tester.save_results()

        # Exit with appropriate code
        overall_success = results["summary"].get("overall_success", False)
        sys.exit(0 if overall_success else 1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed with exception: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
