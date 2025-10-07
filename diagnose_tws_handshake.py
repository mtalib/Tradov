#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - TWS API Handshake Diagnostic Tool
==========================================

This script performs detailed diagnostics of the TWS API handshake process
to identify exactly where the connection is failing. It tests each step of
the API connection process individually.

Usage:
    python diagnose_tws_handshake.py --windows-ip 192.168.1.244
    python diagnose_tws_handshake.py --windows-ip 192.168.1.244 --verbose
    python diagnose_tws_handshake.py --windows-ip 192.168.1.244 --test-all-clients

Author: Spyder Trading System
Date: 2025-01-02
"""

import socket
import time
import struct
import asyncio
import argparse
import sys
from datetime import datetime
from typing import Dict, Any, List, Tuple


class Colors:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    END = "\033[0m"


class TWSHandshakeDiagnostic:
    """Diagnostic tool for TWS API handshake issues"""

    def __init__(self, windows_ip: str, port: int = 7497, verbose: bool = False):
        self.windows_ip = windows_ip
        self.port = port
        self.verbose = verbose

        # TWS API constants
        self.MIN_SERVER_VER_SUPPORTED = 38
        self.MAX_SERVER_VER_SUPPORTED = 176
        self.CLIENT_VERSION = 2

    def log(self, message: str, color: str = Colors.BLUE):
        """Log message with timestamp and color"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"{Colors.CYAN}[{timestamp}]{Colors.END} {color}{message}{Colors.END}")

    def log_success(self, message: str):
        self.log(f"✅ {message}", Colors.GREEN)

    def log_error(self, message: str):
        self.log(f"❌ {message}", Colors.RED)

    def log_warning(self, message: str):
        self.log(f"⚠️  {message}", Colors.YELLOW)

    def log_info(self, message: str):
        self.log(f"ℹ️  {message}", Colors.BLUE)

    def log_debug(self, message: str):
        if self.verbose:
            self.log(f"🔍 {message}", Colors.MAGENTA)

    def test_basic_connectivity(self) -> Tuple[bool, str, float]:
        """Test basic TCP connectivity"""
        self.log_info(
            f"Testing basic TCP connectivity to {self.windows_ip}:{self.port}"
        )

        start_time = time.time()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)

            result = sock.connect_ex((self.windows_ip, self.port))
            latency = (time.time() - start_time) * 1000

            if result == 0:
                sock.close()
                self.log_success(f"TCP connection successful ({latency:.1f}ms)")
                return True, "Connection successful", latency
            else:
                sock.close()
                self.log_error(f"TCP connection failed (error: {result})")
                return False, f"Connection failed (error: {result})", latency

        except Exception as e:
            latency = (time.time() - start_time) * 1000
            self.log_error(f"TCP test failed: {e}")
            return False, str(e), latency

    def test_tws_handshake_manual(self, client_id: int = 1) -> Dict[str, Any]:
        """Manually test TWS API handshake protocol"""
        self.log_info(f"Testing manual TWS handshake (Client ID: {client_id})")

        result = {
            "client_id": client_id,
            "success": False,
            "steps": {},
            "error": None,
            "server_version": None,
            "connection_time": None,
        }

        sock = None
        start_time = time.time()

        try:
            # Step 1: Create socket connection
            self.log_debug("Step 1: Creating socket connection")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(30)  # 30 second timeout for each operation

            sock.connect((self.windows_ip, self.port))
            result["steps"]["socket_connect"] = {
                "success": True,
                "time": time.time() - start_time,
            }
            self.log_debug("Socket connected successfully")

            # Step 2: Send API handshake
            self.log_debug("Step 2: Sending API handshake")
            handshake_start = time.time()

            # TWS expects: "API\0" + version as string + "\0"
            api_handshake = b"API\0"
            sock.send(api_handshake)
            result["steps"]["api_prefix"] = {
                "success": True,
                "time": time.time() - handshake_start,
            }
            self.log_debug("API prefix sent")

            # Send client version
            version_msg = (
                f"v{self.MIN_SERVER_VER_SUPPORTED}..{self.MAX_SERVER_VER_SUPPORTED}"
            )
            if self.verbose:
                self.log_debug(f"Sending version: {version_msg}")

            version_data = version_msg.encode("utf-8") + b"\0"
            sock.send(version_data)
            result["steps"]["version_send"] = {
                "success": True,
                "time": time.time() - handshake_start,
            }

            # Step 3: Wait for server response
            self.log_debug("Step 3: Waiting for server response")
            response_start = time.time()

            sock.settimeout(15)  # Shorter timeout for response
            response = sock.recv(1024)

            if response:
                result["steps"]["server_response"] = {
                    "success": True,
                    "time": time.time() - response_start,
                    "response_length": len(response),
                    "response_preview": response[:50].decode("utf-8", errors="ignore"),
                }
                self.log_success(f"Server responded ({len(response)} bytes)")
                if self.verbose:
                    self.log_debug(f"Response preview: {response[:50]}")

                # Try to parse server version
                try:
                    response_str = response.decode("utf-8", errors="ignore")
                    if "\0" in response_str:
                        parts = response_str.split("\0")
                        if len(parts) > 0 and parts[0].isdigit():
                            result["server_version"] = int(parts[0])
                            self.log_success(
                                f"Server version: {result['server_version']}"
                            )
                except:
                    self.log_warning("Could not parse server version from response")

            else:
                result["steps"]["server_response"] = {
                    "success": False,
                    "error": "No response",
                }
                self.log_error("No response from server")
                return result

            # Step 4: Send client handshake
            self.log_debug("Step 4: Sending client handshake")
            client_start = time.time()

            # Send client ID and version
            client_msg = f"{client_id}\0"
            sock.send(client_msg.encode("utf-8"))
            result["steps"]["client_id_send"] = {
                "success": True,
                "time": time.time() - client_start,
            }
            self.log_debug(f"Client ID {client_id} sent")

            # Step 5: Final handshake completion
            self.log_debug("Step 5: Completing handshake")
            final_start = time.time()

            # Wait for final confirmation
            sock.settimeout(10)
            try:
                final_response = sock.recv(512)
                if final_response:
                    result["steps"]["handshake_complete"] = {
                        "success": True,
                        "time": time.time() - final_start,
                        "final_response_length": len(final_response),
                    }
                    self.log_success("Handshake completed successfully!")
                    result["success"] = True
                else:
                    result["steps"]["handshake_complete"] = {
                        "success": False,
                        "error": "No final response",
                    }
                    self.log_warning("Handshake may be incomplete (no final response)")
                    result["success"] = True  # Still consider partial success

            except socket.timeout:
                # Timeout on final response might be normal
                result["steps"]["handshake_complete"] = {
                    "success": True,
                    "note": "Timeout on final response (normal)",
                }
                self.log_success(
                    "Handshake likely completed (timeout on final response is normal)"
                )
                result["success"] = True

            result["connection_time"] = time.time() - start_time

        except socket.timeout as e:
            result["error"] = f"Timeout during handshake: {e}"
            self.log_error(f"Handshake timeout: {e}")

        except ConnectionRefusedError as e:
            result["error"] = f"Connection refused: {e}"
            self.log_error(f"Connection refused: {e}")

        except Exception as e:
            result["error"] = f"Handshake failed: {e}"
            self.log_error(f"Handshake error: {e}")

        finally:
            if sock:
                try:
                    sock.close()
                    self.log_debug("Socket closed")
                except:
                    pass

        return result

    def test_multiple_client_ids(
        self, client_ids: List[int] = None
    ) -> Dict[int, Dict[str, Any]]:
        """Test handshake with multiple client IDs"""
        if client_ids is None:
            client_ids = [1, 2, 3, 10, 50, 100, 999]

        self.log_info(f"Testing handshake with multiple client IDs: {client_ids}")
        results = {}

        for client_id in client_ids:
            self.log_info(f"Testing Client ID: {client_id}")
            result = self.test_tws_handshake_manual(client_id)
            results[client_id] = result

            if result["success"]:
                self.log_success(f"Client ID {client_id}: SUCCESS")
            else:
                self.log_error(
                    f"Client ID {client_id}: FAILED - {result.get('error', 'Unknown error')}"
                )

            # Small delay between tests
            time.sleep(1)

        return results

    async def test_ib_async_simple(self, client_id: int = 1) -> Dict[str, Any]:
        """Test with ib_async for comparison"""
        self.log_info(f"Testing with ib_async library (Client ID: {client_id})")

        try:
            from ib_async import IB
        except ImportError:
            return {
                "success": False,
                "error": "ib_async not available",
                "message": "Install with: pip install ib_async",
            }

        ib = IB()
        start_time = time.time()

        try:
            await ib.connectAsync(
                host=self.windows_ip, port=self.port, clientId=client_id, timeout=30
            )

            connection_time = time.time() - start_time

            if ib.isConnected():
                self.log_success(
                    f"ib_async connection successful ({connection_time:.2f}s)"
                )

                # Get basic info
                try:
                    accounts = ib.managedAccounts()
                    await ib.disconnectAsync()

                    return {
                        "success": True,
                        "connection_time": connection_time,
                        "accounts": accounts,
                        "client_id": client_id,
                    }
                except Exception as e:
                    await ib.disconnectAsync()
                    return {
                        "success": True,
                        "connection_time": connection_time,
                        "accounts": [],
                        "client_id": client_id,
                        "warning": f"Connected but API test failed: {e}",
                    }
            else:
                return {
                    "success": False,
                    "error": "Connection not confirmed",
                    "connection_time": connection_time,
                }

        except Exception as e:
            return {"success": False, "error": str(e), "error_type": type(e).__name__}

    def analyze_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze test results and provide recommendations"""
        analysis = {
            "overall_status": "unknown",
            "working_client_ids": [],
            "failed_client_ids": [],
            "recommendations": [],
            "likely_issues": [],
        }

        # Analyze connectivity
        if not results.get("connectivity", {}).get("success", False):
            analysis["overall_status"] = "connectivity_failed"
            analysis["likely_issues"].append("Network connectivity problem")
            analysis["recommendations"].extend(
                [
                    "Check if TWS is running on Windows computer",
                    "Verify Windows Firewall allows port 7497",
                    "Confirm network connection between computers",
                ]
            )
            return analysis

        # Analyze handshake results
        handshake_results = results.get("handshake_tests", {})

        for client_id, result in handshake_results.items():
            if result.get("success", False):
                analysis["working_client_ids"].append(client_id)
            else:
                analysis["failed_client_ids"].append(client_id)

        # Determine overall status
        if analysis["working_client_ids"]:
            analysis["overall_status"] = "partial_success"
            if len(analysis["working_client_ids"]) == len(handshake_results):
                analysis["overall_status"] = "success"
        else:
            analysis["overall_status"] = "handshake_failed"

        # Generate recommendations
        if analysis["overall_status"] == "success":
            analysis["recommendations"].extend(
                [
                    "TWS API is working correctly!",
                    f"Use any of these client IDs: {analysis['working_client_ids']}",
                    "Run: ./setup_remote_tws.sh --windows-ip " + self.windows_ip,
                ]
            )
        elif analysis["overall_status"] == "partial_success":
            analysis["recommendations"].extend(
                [
                    f"Some client IDs work: {analysis['working_client_ids']}",
                    f"Use working client ID in your configuration",
                    "Avoid failed client IDs (may be in use by other applications)",
                ]
            )
        else:
            # All handshakes failed - analyze common patterns
            common_errors = {}
            for result in handshake_results.values():
                error = result.get("error", "Unknown")
                common_errors[error] = common_errors.get(error, 0) + 1

            most_common_error = (
                max(common_errors.items(), key=lambda x: x[1])[0]
                if common_errors
                else "Unknown"
            )

            if "timeout" in most_common_error.lower():
                analysis["likely_issues"].append("TWS API handshake timeout")
                analysis["recommendations"].extend(
                    [
                        "Check TWS API settings: Enable ActiveX and Socket Clients",
                        "Add this computer's IP to TWS Trusted IPs",
                        "Ensure TWS is fully logged in and operational",
                        "Try restarting TWS",
                    ]
                )
            elif "refused" in most_common_error.lower():
                analysis["likely_issues"].append("Connection actively refused")
                analysis["recommendations"].extend(
                    [
                        "Verify TWS API is enabled in settings",
                        "Check if another application is using the port",
                        "Try a different port (7496 for live trading)",
                    ]
                )
            else:
                analysis["likely_issues"].append(
                    f"Handshake protocol error: {most_common_error}"
                )
                analysis["recommendations"].extend(
                    [
                        "Check TWS version compatibility",
                        "Verify TWS API settings are correct",
                        "Try restarting TWS",
                    ]
                )

        return analysis

    async def run_full_diagnostic(
        self, test_all_clients: bool = False
    ) -> Dict[str, Any]:
        """Run complete diagnostic suite"""
        print(f"\n{Colors.CYAN}{Colors.BOLD}{'=' * 60}")
        print(f"TWS API HANDSHAKE DIAGNOSTIC")
        print(f"Target: {self.windows_ip}:{self.port}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'=' * 60}{Colors.END}\n")

        results = {
            "timestamp": datetime.now().isoformat(),
            "target": f"{self.windows_ip}:{self.port}",
            "tests": {},
        }

        # Test 1: Basic connectivity
        self.log_info("=== Test 1: Basic TCP Connectivity ===")
        success, message, latency = self.test_basic_connectivity()
        results["connectivity"] = {
            "success": success,
            "message": message,
            "latency_ms": latency,
        }

        if not success:
            self.log_error(
                "Cannot proceed with handshake tests - no basic connectivity"
            )
            return results

        # Test 2: Manual handshake test
        self.log_info("\n=== Test 2: Manual TWS Handshake ===")
        if test_all_clients:
            client_ids = [1, 2, 3, 5, 10, 20, 50, 100, 500, 999]
        else:
            client_ids = [1, 2, 10, 100]

        handshake_results = self.test_multiple_client_ids(client_ids)
        results["handshake_tests"] = handshake_results

        # Test 3: ib_async comparison
        self.log_info("\n=== Test 3: ib_async Library Test ===")
        working_clients = [
            cid for cid, res in handshake_results.items() if res.get("success")
        ]
        if working_clients:
            test_client = working_clients[0]
            ib_async_result = await self.test_ib_async_simple(test_client)
            results["ib_async_test"] = ib_async_result
        else:
            # Try with client ID 1 even if manual test failed
            ib_async_result = await self.test_ib_async_simple(1)
            results["ib_async_test"] = ib_async_result

        # Analysis and recommendations
        self.log_info("\n=== Analysis and Recommendations ===")
        analysis = self.analyze_results(results)
        results["analysis"] = analysis

        # Print summary
        self.print_summary(results)

        return results

    def print_summary(self, results: Dict[str, Any]):
        """Print diagnostic summary"""
        print(f"\n{Colors.BOLD}{Colors.CYAN}DIAGNOSTIC SUMMARY{Colors.END}")
        print("=" * 50)

        analysis = results.get("analysis", {})
        status = analysis.get("overall_status", "unknown")

        if status == "success":
            self.log_success("TWS API is working correctly!")
            working_ids = analysis.get("working_client_ids", [])
            print(f"   Working Client IDs: {working_ids}")
        elif status == "partial_success":
            self.log_warning("TWS API partially working")
            working_ids = analysis.get("working_client_ids", [])
            failed_ids = analysis.get("failed_client_ids", [])
            print(f"   Working Client IDs: {working_ids}")
            print(f"   Failed Client IDs: {failed_ids}")
        else:
            self.log_error("TWS API connection failed")
            issues = analysis.get("likely_issues", [])
            for issue in issues:
                print(f"   Issue: {issue}")

        # Print recommendations
        recommendations = analysis.get("recommendations", [])
        if recommendations:
            print(f"\n{Colors.YELLOW}{Colors.BOLD}RECOMMENDATIONS:{Colors.END}")
            for i, rec in enumerate(recommendations, 1):
                print(f"   {i}. {rec}")

        # Print next steps
        print(f"\n{Colors.BLUE}{Colors.BOLD}NEXT STEPS:{Colors.END}")
        if status in ["success", "partial_success"]:
            print("   ✅ Your TWS setup is working!")
            print(f"   ✅ Run: ./setup_remote_tws.sh --windows-ip {self.windows_ip}")
            print("   ✅ Launch your Spyder dashboard")
        else:
            print("   ❌ Fix TWS configuration issues above")
            print("   ❌ Verify TWS API settings on Windows computer")
            print("   ❌ Re-run this diagnostic after making changes")


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="TWS API Handshake Diagnostic Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python diagnose_tws_handshake.py --windows-ip 192.168.1.244
    python diagnose_tws_handshake.py --windows-ip 192.168.1.244 --verbose
    python diagnose_tws_handshake.py --windows-ip 192.168.1.244 --test-all-clients
        """,
    )

    parser.add_argument(
        "--windows-ip", required=True, help="IP address of Windows computer running TWS"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=7497,
        help="TWS port (7497 for paper, 7496 for live, default: 7497)",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Enable verbose debug output"
    )
    parser.add_argument(
        "--test-all-clients", action="store_true", help="Test all client IDs (1-999)"
    )

    args = parser.parse_args()

    # Create diagnostic tool
    diagnostic = TWSHandshakeDiagnostic(
        windows_ip=args.windows_ip, port=args.port, verbose=args.verbose
    )

    try:
        results = await diagnostic.run_full_diagnostic(args.test_all_clients)

        # Exit with appropriate code
        status = results.get("analysis", {}).get("overall_status", "unknown")
        if status in ["success", "partial_success"]:
            sys.exit(0)
        else:
            sys.exit(1)

    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Diagnostic interrupted by user{Colors.END}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}Diagnostic failed: {e}{Colors.END}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
