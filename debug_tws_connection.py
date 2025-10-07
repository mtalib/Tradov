#!/usr/bin/env python3
"""
TWS Connection Diagnostic Tool
=============================

This script provides comprehensive diagnostics for Remote TWS connectivity issues.
It tests multiple connection methods and provides detailed troubleshooting information.

Usage:
    python debug_tws_connection.py --ip 192.168.1.244 --port 7497
    python debug_tws_connection.py --ip 192.168.1.244 --port 7497 --full-test
    python debug_tws_connection.py --ip 192.168.1.244 --port 7497 --interactive
"""

import socket
import time
import threading
import argparse
import json
import sys
import os
from datetime import datetime
import subprocess


class TWSConnectionDiagnostic:
    def __init__(self, host, port, timeout=10):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "host": host,
            "port": port,
            "tests": {},
        }

    def log_info(self, message):
        print(f"ℹ️  {message}")

    def log_success(self, message):
        print(f"✅ {message}")

    def log_warning(self, message):
        print(f"⚠️  {message}")

    def log_error(self, message):
        print(f"❌ {message}")

    def test_ping(self):
        """Test basic network connectivity via ping"""
        self.log_info(f"Testing ping to {self.host}...")

        try:
            # Use ping command
            result = subprocess.run(
                ["ping", "-c", "3", self.host],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                # Extract timing info
                lines = result.stdout.split("\n")
                stats_line = [line for line in lines if "min/avg/max" in line]
                timing = stats_line[0].split("=")[1].strip() if stats_line else "N/A"

                self.log_success(f"Ping successful - Timing: {timing}")
                self.results["tests"]["ping"] = {
                    "status": "success",
                    "timing": timing,
                    "output": result.stdout,
                }
                return True
            else:
                self.log_warning(f"Ping failed - {result.stderr.strip()}")
                self.results["tests"]["ping"] = {
                    "status": "failed",
                    "error": result.stderr.strip(),
                }
                return False

        except Exception as e:
            self.log_error(f"Ping test failed: {e}")
            self.results["tests"]["ping"] = {"status": "error", "error": str(e)}
            return False

    def test_socket_connect(self):
        """Test basic socket connection"""
        self.log_info(f"Testing socket connection to {self.host}:{self.port}...")

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)

            start_time = time.time()
            result = sock.connect_ex((self.host, self.port))
            connect_time = time.time() - start_time

            sock.close()

            if result == 0:
                self.log_success(f"Socket connection successful ({connect_time:.3f}s)")
                self.results["tests"]["socket_connect"] = {
                    "status": "success",
                    "connect_time": connect_time,
                }
                return True
            else:
                self.log_error(f"Socket connection failed - Error code: {result}")
                self.results["tests"]["socket_connect"] = {
                    "status": "failed",
                    "error_code": result,
                    "connect_time": connect_time,
                }
                return False

        except Exception as e:
            self.log_error(f"Socket connection error: {e}")
            self.results["tests"]["socket_connect"] = {
                "status": "error",
                "error": str(e),
            }
            return False

    def test_telnet_like_connection(self):
        """Test telnet-like connection with data exchange"""
        self.log_info(f"Testing telnet-like connection to {self.host}:{self.port}...")

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)

            # Connect
            sock.connect((self.host, self.port))
            self.log_info("Connection established, testing data exchange...")

            # Try to send a simple message (this might get rejected by TWS)
            try:
                sock.send(b"test\n")
                time.sleep(1)

                # Try to receive data
                sock.settimeout(2)
                data = sock.recv(1024)

                if data:
                    self.log_success(f"Received data: {data[:50]}...")
                    self.results["tests"]["telnet_like"] = {
                        "status": "success",
                        "received_data": data.decode("utf-8", errors="ignore")[:100],
                    }
                else:
                    self.log_warning("Connected but no data received")
                    self.results["tests"]["telnet_like"] = {
                        "status": "connected_no_data"
                    }

            except socket.timeout:
                self.log_warning("Connected but timed out waiting for data")
                self.results["tests"]["telnet_like"] = {"status": "connected_timeout"}

            sock.close()
            return True

        except ConnectionRefusedError:
            self.log_error("Connection refused - TWS might not be listening")
            self.results["tests"]["telnet_like"] = {"status": "connection_refused"}
            return False

        except socket.timeout:
            self.log_error("Connection timed out")
            self.results["tests"]["telnet_like"] = {"status": "timeout"}
            return False

        except Exception as e:
            self.log_error(f"Telnet-like connection error: {e}")
            self.results["tests"]["telnet_like"] = {"status": "error", "error": str(e)}
            return False

    def test_ib_async_connection(self):
        """Test connection using ib_async library"""
        self.log_info("Testing ib_async connection...")

        try:
            # Import ib_async
            from ib_async import IB

            ib = IB()

            # Try to connect
            try:
                ib.connect(self.host, self.port, clientId=999, timeout=self.timeout)
                self.log_success("ib_async connection successful!")

                # Get connection info
                conn_state = ib.client.conn.connected

                self.results["tests"]["ib_async"] = {
                    "status": "success",
                    "connected": conn_state,
                }

                # Disconnect
                ib.disconnect()
                return True

            except Exception as e:
                self.log_error(f"ib_async connection failed: {e}")
                self.results["tests"]["ib_async"] = {
                    "status": "failed",
                    "error": str(e),
                }
                return False

        except ImportError:
            self.log_warning("ib_async not available - skipping test")
            self.results["tests"]["ib_async"] = {
                "status": "skipped",
                "reason": "ib_async not installed",
            }
            return None

    def test_port_scan(self):
        """Scan common TWS ports"""
        self.log_info(f"Scanning common TWS ports on {self.host}...")

        common_ports = [7496, 7497, 4001, 4002]
        open_ports = []

        for port in common_ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                result = sock.connect_ex((self.host, port))
                sock.close()

                if result == 0:
                    open_ports.append(port)
                    port_type = (
                        "Live"
                        if port == 7496
                        else "Paper"
                        if port == 7497
                        else "Gateway"
                    )
                    self.log_success(f"Port {port} is open ({port_type})")
                else:
                    self.log_info(f"Port {port} is closed")

            except Exception as e:
                self.log_error(f"Error testing port {port}: {e}")

        self.results["tests"]["port_scan"] = {
            "open_ports": open_ports,
            "tested_ports": common_ports,
        }

        if open_ports:
            self.log_success(f"Found {len(open_ports)} open TWS ports: {open_ports}")
            return True
        else:
            self.log_warning("No TWS ports found open")
            return False

    def check_system_info(self):
        """Gather system information for diagnostics"""
        self.log_info("Gathering system information...")

        try:
            # Get local IP
            local_ip = socket.gethostbyname(socket.gethostname())

            # Get network interfaces
            import netifaces

            interfaces = netifaces.interfaces()

            self.results["system_info"] = {
                "local_ip": local_ip,
                "interfaces": interfaces,
            }

            self.log_info(f"Local IP: {local_ip}")

        except ImportError:
            self.log_warning("netifaces not available - limited system info")
            self.results["system_info"] = {
                "local_ip": "unknown",
                "interfaces": "netifaces not available",
            }
        except Exception as e:
            self.log_error(f"Error gathering system info: {e}")
            self.results["system_info"] = {"error": str(e)}

    def run_comprehensive_test(self):
        """Run all diagnostic tests"""
        print("🔍 Starting comprehensive TWS connection diagnostics...")
        print(f"   Target: {self.host}:{self.port}")
        print(f"   Timeout: {self.timeout}s")
        print("=" * 60)

        # Run all tests
        tests = [
            ("ping", self.test_ping),
            ("port_scan", self.test_port_scan),
            ("socket_connect", self.test_socket_connect),
            ("telnet_like", self.test_telnet_like_connection),
            ("ib_async", self.test_ib_async_connection),
        ]

        results = {}
        for test_name, test_func in tests:
            print(f"\n🧪 Running {test_name} test...")
            try:
                results[test_name] = test_func()
                time.sleep(1)  # Brief pause between tests
            except Exception as e:
                self.log_error(f"Test {test_name} crashed: {e}")
                results[test_name] = False

        # Gather system info
        self.check_system_info()

        print("\n" + "=" * 60)
        print("📊 DIAGNOSTIC SUMMARY")
        print("=" * 60)

        # Summary
        passed = sum(1 for result in results.values() if result is True)
        failed = sum(1 for result in results.values() if result is False)
        skipped = sum(1 for result in results.values() if result is None)

        print(f"Tests passed: {passed}")
        print(f"Tests failed: {failed}")
        print(f"Tests skipped: {skipped}")

        # Recommendations
        print("\n🔧 RECOMMENDATIONS:")

        if not results.get("ping", False):
            print(
                "❌ Network connectivity issue - check if Windows computer is reachable"
            )

        if not results.get("port_scan", False):
            print("❌ No TWS ports found - ensure TWS is running and API is enabled")

        if results.get("socket_connect", False) and not results.get("ib_async", False):
            print("⚠️  Port is open but IB connection fails - check TWS API settings:")
            print("   • Ensure 'Enable ActiveX and Socket Clients' is checked")
            print("   • Ensure 'Read-Only API' is UNCHECKED")
            print("   • Add client IP to Trusted IPs list")
            print("   • Check client ID conflicts")

        if (
            results.get("port_scan", False)
            and self.port not in self.results["tests"]["port_scan"]["open_ports"]
        ):
            available_ports = self.results["tests"]["port_scan"]["open_ports"]
            print(
                f"⚠️  Port {self.port} is not open, but these ports are: {available_ports}"
            )
            print("   • Check your port configuration in TWS")

        return results

    def save_results(self, filename=None):
        """Save diagnostic results to file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"tws_diagnostic_{timestamp}.json"

        try:
            with open(filename, "w") as f:
                json.dump(self.results, f, indent=2)
            self.log_success(f"Results saved to {filename}")
        except Exception as e:
            self.log_error(f"Failed to save results: {e}")


def main():
    parser = argparse.ArgumentParser(description="TWS Connection Diagnostic Tool")
    parser.add_argument("--ip", required=True, help="TWS host IP address")
    parser.add_argument(
        "--port", type=int, default=7497, help="TWS port (default: 7497)"
    )
    parser.add_argument(
        "--timeout", type=int, default=10, help="Connection timeout in seconds"
    )
    parser.add_argument(
        "--full-test", action="store_true", help="Run comprehensive test suite"
    )
    parser.add_argument(
        "--save-results", action="store_true", help="Save results to JSON file"
    )
    parser.add_argument(
        "--interactive", action="store_true", help="Interactive mode with prompts"
    )

    args = parser.parse_args()

    # Interactive mode
    if args.interactive:
        print("🔍 TWS Connection Diagnostic Tool - Interactive Mode")
        print("=" * 50)

        ip = input(f"Enter TWS IP address [{args.ip}]: ").strip() or args.ip
        port_input = input(f"Enter TWS port [{args.port}]: ").strip()
        port = int(port_input) if port_input else args.port
        timeout_input = input(f"Enter timeout seconds [{args.timeout}]: ").strip()
        timeout = int(timeout_input) if timeout_input else args.timeout

        args.ip = ip
        args.port = port
        args.timeout = timeout
        args.full_test = True
        args.save_results = True

    # Create diagnostic instance
    diagnostic = TWSConnectionDiagnostic(args.ip, args.port, args.timeout)

    if args.full_test:
        # Run comprehensive test
        results = diagnostic.run_comprehensive_test()
    else:
        # Run basic tests
        print(f"🔍 Testing basic connection to {args.ip}:{args.port}...")
        results = {
            "ping": diagnostic.test_ping(),
            "socket_connect": diagnostic.test_socket_connect(),
        }

        if results["socket_connect"]:
            print("✅ Basic connection test passed")
        else:
            print("❌ Basic connection test failed")

    # Save results if requested
    if args.save_results:
        diagnostic.save_results()

    # Exit with appropriate code
    if any(result is False for result in results.values()):
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
