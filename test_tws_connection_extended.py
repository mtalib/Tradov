#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Extended TWS Connection Test
===================================

Test TWS connection with extended timeout and detailed diagnostics.
This script helps troubleshoot TWS API handshake timeouts by using
longer timeouts and providing step-by-step connection diagnostics.

Usage:
    python test_tws_connection_extended.py --windows-ip 192.168.1.244
    python test_tws_connection_extended.py --windows-ip 192.168.1.244 --timeout 60
    python test_tws_connection_extended.py --windows-ip 192.168.1.244 --client-id 1

Author: Spyder Trading System
Date: 2025-01-02
"""

import asyncio
import sys
import time
import socket
import argparse
from datetime import datetime
from typing import Dict, Any, Optional


class Colors:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    END = "\033[0m"


def print_step(step: int, text: str):
    """Print a numbered step"""
    print(f"\n{Colors.CYAN}{Colors.BOLD}Step {step}: {text}{Colors.END}")


def print_success(text: str):
    """Print success message"""
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")


def print_warning(text: str):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")


def print_error(text: str):
    """Print error message"""
    print(f"{Colors.RED}❌ {text}{Colors.END}")


def print_info(text: str):
    """Print info message"""
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.END}")


class ExtendedTWSConnectionTest:
    """Extended TWS connection test with detailed diagnostics"""

    def __init__(self, windows_ip: str, port: int = 7497, client_id: int = 1):
        self.windows_ip = windows_ip
        self.port = port
        self.client_id = client_id
        self.ib = None

    def test_socket_connectivity(self) -> Dict[str, Any]:
        """Test raw TCP socket connectivity"""
        print_step(
            1, f"Testing TCP socket connectivity to {self.windows_ip}:{self.port}"
        )

        try:
            start_time = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)

            # Test connection
            result = sock.connect_ex((self.windows_ip, self.port))

            if result == 0:
                print_success(f"TCP socket connection successful")

                # Test if we can send/receive basic data
                try:
                    # Send a simple test message
                    sock.send(b"test\n")
                    sock.settimeout(3)
                    response = sock.recv(1024)
                    print_info(f"Socket response received: {len(response)} bytes")
                except socket.timeout:
                    print_warning(
                        "Socket connected but no response to test message (normal for TWS)"
                    )
                except Exception as e:
                    print_warning(f"Socket send/receive test failed: {e}")

                sock.close()
                latency = (time.time() - start_time) * 1000

                return {
                    "success": True,
                    "latency_ms": latency,
                    "message": f"Socket connectivity OK ({latency:.1f}ms)",
                }
            else:
                sock.close()
                return {
                    "success": False,
                    "error_code": result,
                    "message": f"Socket connection failed (error: {result})",
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Socket test error: {str(e)}",
            }

    async def test_ib_async_connection(self, timeout: int = 60) -> Dict[str, Any]:
        """Test ib_async connection with extended timeout"""
        print_step(2, f"Testing ib_async connection (timeout: {timeout}s)")

        try:
            # Import ib_async
            from ib_async import IB

            print_info("ib_async imported successfully")
        except ImportError:
            return {
                "success": False,
                "error": "ib_async_not_available",
                "message": "ib_async not installed. Run: pip install ib_async",
            }

        try:
            self.ib = IB()

            # Configure client timeout
            self.ib.client.setTimeout(timeout)
            print_info(f"Client timeout set to {timeout} seconds")

            print_info(
                f"Attempting connection to {self.windows_ip}:{self.port} (Client ID: {self.client_id})"
            )
            start_time = time.time()

            # Use connectAsync with extended timeout
            await self.ib.connectAsync(
                host=self.windows_ip,
                port=self.port,
                clientId=self.client_id,
                timeout=timeout,
            )

            connection_time = time.time() - start_time
            print_success(f"Connection established in {connection_time:.2f} seconds")

            # Verify connection
            if self.ib.isConnected():
                print_success("Connection verified as active")

                # Test basic API functionality
                try:
                    print_info("Testing account information retrieval...")
                    accounts = self.ib.managedAccounts()
                    print_success(f"Account info retrieved: {accounts}")

                    # Test market data request
                    print_info("Testing market data request...")
                    from ib_async import Stock

                    spy_contract = Stock("SPY", "SMART", "USD")

                    # Request market data (don't wait for response, just test if request works)
                    ticker = self.ib.reqMktData(spy_contract, "", False, False)
                    print_success("Market data request sent successfully")

                    return {
                        "success": True,
                        "connection_time": connection_time,
                        "accounts": accounts,
                        "client_id": self.client_id,
                        "message": f"Full connection test successful ({connection_time:.2f}s)",
                        "market_data_request": "success",
                    }

                except Exception as api_error:
                    print_warning(f"API functionality test failed: {api_error}")
                    return {
                        "success": True,
                        "connection_time": connection_time,
                        "accounts": [],
                        "client_id": self.client_id,
                        "message": f"Connected but API test failed: {str(api_error)}",
                        "api_error": str(api_error),
                    }
            else:
                return {
                    "success": False,
                    "error": "connection_not_verified",
                    "message": "Connection completed but verification failed",
                }

        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "timeout",
                "message": f"Connection timeout after {timeout} seconds",
                "timeout_used": timeout,
            }
        except ConnectionRefusedError:
            return {
                "success": False,
                "error": "connection_refused",
                "message": "Connection refused - check if TWS is running and API is enabled",
            }
        except Exception as e:
            error_type = type(e).__name__
            return {
                "success": False,
                "error": error_type,
                "message": f"Connection failed: {str(e)}",
                "exception_type": error_type,
            }

    async def disconnect(self):
        """Safely disconnect from TWS"""
        if self.ib and self.ib.isConnected():
            try:
                print_info("Disconnecting from TWS...")
                await self.ib.disconnectAsync()
                print_success("Disconnected successfully")
            except Exception as e:
                print_warning(f"Disconnection error: {e}")

    def test_different_client_ids(self) -> Dict[str, Any]:
        """Test multiple client IDs to find working ones"""
        print_step(3, "Testing different client IDs for conflicts")

        working_ids = []
        failed_ids = []

        test_ids = [1, 2, 3, 10, 50, 100, 999]

        for test_id in test_ids:
            print_info(f"Testing client ID: {test_id}")

            try:
                # Quick socket test with this client ID concept
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex((self.windows_ip, self.port))
                sock.close()

                if result == 0:
                    working_ids.append(test_id)
                    print_success(f"Client ID {test_id}: Socket accessible")
                else:
                    failed_ids.append(test_id)
                    print_warning(f"Client ID {test_id}: Socket not accessible")

            except Exception as e:
                failed_ids.append(test_id)
                print_error(f"Client ID {test_id}: Error - {e}")

        return {
            "working_ids": working_ids,
            "failed_ids": failed_ids,
            "message": f"Found {len(working_ids)} potentially working client IDs",
        }

    async def run_comprehensive_test(self, timeout: int = 60) -> Dict[str, Any]:
        """Run comprehensive connection test"""
        print(f"\n{Colors.CYAN}{Colors.BOLD}{'=' * 60}")
        print(f"EXTENDED TWS CONNECTION TEST")
        print(f"Target: {self.windows_ip}:{self.port} (Client ID: {self.client_id})")
        print(f"Timeout: {timeout} seconds")
        print(f"{'=' * 60}{Colors.END}")

        results = {
            "timestamp": datetime.now().isoformat(),
            "target": f"{self.windows_ip}:{self.port}",
            "client_id": self.client_id,
            "timeout": timeout,
            "tests": {},
        }

        try:
            # Test 1: Socket connectivity
            socket_result = self.test_socket_connectivity()
            results["tests"]["socket"] = socket_result

            if not socket_result["success"]:
                print_error(
                    "Socket connectivity failed - cannot proceed with TWS API test"
                )
                return results

            # Test 2: Client ID availability
            client_id_result = self.test_different_client_ids()
            results["tests"]["client_ids"] = client_id_result

            # Test 3: TWS API connection
            tws_result = await self.test_ib_async_connection(timeout)
            results["tests"]["tws_api"] = tws_result

            # Test 4: Connection stability (if connected)
            if tws_result["success"]:
                print_step(4, "Testing connection stability")

                # Keep connection alive for a few seconds to test stability
                print_info("Maintaining connection for 10 seconds to test stability...")
                await asyncio.sleep(10)

                if self.ib and self.ib.isConnected():
                    print_success("Connection remained stable")
                    results["tests"]["stability"] = {
                        "success": True,
                        "message": "Connection stable for 10 seconds",
                    }
                else:
                    print_warning("Connection dropped during stability test")
                    results["tests"]["stability"] = {
                        "success": False,
                        "message": "Connection dropped",
                    }

            # Always disconnect at the end
            await self.disconnect()

            # Generate summary
            self._generate_summary(results)

            return results

        except KeyboardInterrupt:
            print_warning("Test interrupted by user")
            await self.disconnect()
            return results
        except Exception as e:
            print_error(f"Test suite failed: {e}")
            await self.disconnect()
            results["tests"]["suite_error"] = {"error": str(e)}
            return results

    def _generate_summary(self, results: Dict[str, Any]):
        """Generate test summary"""
        print(f"\n{Colors.CYAN}{Colors.BOLD}{'=' * 60}")
        print("TEST SUMMARY")
        print(f"{'=' * 60}{Colors.END}")

        tests = results["tests"]

        # Socket test
        if tests.get("socket", {}).get("success"):
            print_success("Socket connectivity: PASS")
        else:
            print_error("Socket connectivity: FAIL")

        # TWS API test
        tws_test = tests.get("tws_api", {})
        if tws_test.get("success"):
            conn_time = tws_test.get("connection_time", 0)
            print_success(f"TWS API connection: PASS ({conn_time:.2f}s)")

            accounts = tws_test.get("accounts", [])
            if accounts:
                print_info(f"Accounts found: {accounts}")
        else:
            print_error(
                f"TWS API connection: FAIL - {tws_test.get('message', 'Unknown error')}"
            )

        # Stability test
        stability = tests.get("stability", {})
        if stability.get("success"):
            print_success("Connection stability: PASS")
        elif "stability" in tests:
            print_warning("Connection stability: DEGRADED")

        # Recommendations
        print(f"\n{Colors.YELLOW}{Colors.BOLD}RECOMMENDATIONS:{Colors.END}")

        if not tests.get("socket", {}).get("success"):
            print_warning("• Check TWS is running on Windows computer")
            print_warning("• Verify Windows Firewall allows TWS ports")
            print_warning("• Confirm network connectivity between computers")

        elif not tests.get("tws_api", {}).get("success"):
            error = tests.get("tws_api", {}).get("error", "")
            if error == "timeout":
                print_warning("• Try increasing timeout (current: 60s)")
                print_warning(
                    "• Check TWS API settings (Enable ActiveX and Socket Clients)"
                )
                print_warning("• Add Ubuntu IP to TWS Trusted IPs")
                print_warning("• Try different client ID")
            elif error == "connection_refused":
                print_warning("• Verify TWS API is enabled in settings")
                print_warning("• Check TWS is logged in and fully loaded")
            else:
                print_warning(f"• Investigate specific error: {error}")

        if tests.get("tws_api", {}).get("success"):
            print_success(
                "• Setup is working! You can proceed with Spyder configuration"
            )
            print_info("• Run: ./setup_remote_tws.sh --windows-ip " + self.windows_ip)


async def main():
    """Main test function"""
    parser = argparse.ArgumentParser(
        description="Extended TWS Connection Test with detailed diagnostics"
    )

    parser.add_argument(
        "--windows-ip", required=True, help="IP address of Windows computer running TWS"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=7497,
        help="TWS port (7497 for paper, 7496 for live)",
    )
    parser.add_argument(
        "--client-id", type=int, default=1, help="Client ID to use for connection"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Connection timeout in seconds (default: 60)",
    )

    args = parser.parse_args()

    # Create and run test
    tester = ExtendedTWSConnectionTest(
        windows_ip=args.windows_ip, port=args.port, client_id=args.client_id
    )

    try:
        results = await tester.run_comprehensive_test(args.timeout)

        # Exit with appropriate code
        tws_success = results.get("tests", {}).get("tws_api", {}).get("success", False)
        sys.exit(0 if tws_success else 1)

    except KeyboardInterrupt:
        print_warning("Test interrupted")
        sys.exit(1)
    except Exception as e:
        print_error(f"Test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
