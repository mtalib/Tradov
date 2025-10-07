#!/usr/bin/env python3
"""
Layer 4 IB Gateway Network Diagnostic Tool
==========================================

This script performs comprehensive Layer 4 (TCP) network diagnostics for IB Gateway
to confirm that application-level rejection (not network/firewall issues) is the
root cause of connection failures.

Key diagnostic areas:
1. Firewall rules verification (iptables/firewalld)
2. Port binding and listening status
3. TCP connection establishment testing
4. Socket behavior analysis
5. Network interface verification
6. Process ownership confirmation

Usage:
    python layer4_ib_gateway_diagnostic.py
    python layer4_ib_gateway_diagnostic.py --port 4001 --live-mode
"""

import subprocess
import socket
import time
import json
import sys
import os
import signal
import select
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import argparse


class Layer4IBGatewayDiagnostic:
    """Comprehensive Layer 4 network diagnostic for IB Gateway"""

    def __init__(self, target_port: int = 4002, host: str = "localhost"):
        self.target_port = target_port
        self.host = host
        self.mode = "Paper Trading" if target_port == 4002 else "Live Trading"
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "target": f"{host}:{target_port}",
            "mode": self.mode,
            "diagnostics": {},
        }

    def log_info(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] ℹ️  {message}")

    def log_success(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] ✅ {message}")

    def log_warning(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] ⚠️  {message}")

    def log_error(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] ❌ {message}")

    def run_command(self, cmd: List[str], timeout: int = 10) -> Tuple[bool, str, str]:
        """Run system command and return success, stdout, stderr"""
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout, check=False
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out"
        except Exception as e:
            return False, "", str(e)

    def check_firewall_iptables(self) -> Dict:
        """Check iptables firewall configuration"""
        self.log_info("Checking iptables firewall rules...")

        firewall_info = {
            "type": "iptables",
            "accessible": False,
            "input_policy": "UNKNOWN",
            "rules_blocking_port": [],
            "rules_allowing_port": [],
            "overall_assessment": "UNKNOWN",
        }

        # Check if we can access iptables
        success, stdout, stderr = self.run_command(
            ["sudo", "-n", "iptables", "-L", "-n"]
        )

        if not success:
            self.log_warning("Cannot access iptables without password prompt")
            firewall_info["accessible"] = False
            firewall_info["error"] = "Requires sudo password"
            return firewall_info

        firewall_info["accessible"] = True

        # Parse INPUT chain policy
        lines = stdout.split("\n")
        for line in lines:
            if line.startswith("Chain INPUT"):
                if "policy ACCEPT" in line:
                    firewall_info["input_policy"] = "ACCEPT"
                    self.log_success(
                        "iptables INPUT policy: ACCEPT (allows incoming connections)"
                    )
                elif "policy DROP" in line:
                    firewall_info["input_policy"] = "DROP"
                    self.log_warning(
                        "iptables INPUT policy: DROP (blocks incoming by default)"
                    )
                elif "policy REJECT" in line:
                    firewall_info["input_policy"] = "REJECT"
                    self.log_warning(
                        "iptables INPUT policy: REJECT (rejects incoming by default)"
                    )
                break

        # Look for specific rules affecting our port
        port_str = str(self.target_port)
        for line in lines:
            if port_str in line:
                if "ACCEPT" in line:
                    firewall_info["rules_allowing_port"].append(line.strip())
                elif "DROP" in line or "REJECT" in line:
                    firewall_info["rules_blocking_port"].append(line.strip())

        # Overall assessment
        if (
            firewall_info["input_policy"] == "ACCEPT"
            and not firewall_info["rules_blocking_port"]
        ):
            firewall_info["overall_assessment"] = "ALLOWS_CONNECTION"
            self.log_success(f"Firewall allows connections to port {self.target_port}")
        elif firewall_info["rules_blocking_port"]:
            firewall_info["overall_assessment"] = "BLOCKS_CONNECTION"
            self.log_error(f"Firewall has blocking rules for port {self.target_port}")
        else:
            firewall_info["overall_assessment"] = "LIKELY_ALLOWS"
            self.log_info(
                f"Firewall likely allows connections to port {self.target_port}"
            )

        return firewall_info

    def check_firewall_firewalld(self) -> Optional[Dict]:
        """Check firewalld configuration if available"""
        self.log_info("Checking for firewalld...")

        success, stdout, stderr = self.run_command(
            ["systemctl", "is-active", "firewalld"]
        )

        if not success:
            self.log_info("firewalld is not active or not installed")
            return None

        self.log_info("firewalld is active - checking configuration...")

        firewalld_info = {
            "type": "firewalld",
            "active": True,
            "default_zone": "UNKNOWN",
            "port_allowed": False,
        }

        # Get default zone
        success, stdout, stderr = self.run_command(
            ["firewall-cmd", "--get-default-zone"]
        )
        if success:
            firewalld_info["default_zone"] = stdout.strip()

        # Check if port is allowed
        success, stdout, stderr = self.run_command(
            [
                "firewall-cmd",
                "--zone",
                firewalld_info["default_zone"],
                "--query-port",
                f"{self.target_port}/tcp",
            ]
        )

        firewalld_info["port_allowed"] = success

        if success:
            self.log_success(f"firewalld allows port {self.target_port}/tcp")
        else:
            self.log_warning(
                f"firewalld does not explicitly allow port {self.target_port}/tcp"
            )

        return firewalld_info

    def check_port_listening(self) -> Dict:
        """Check if target port is listening and get process information"""
        self.log_info(f"Checking if port {self.target_port} is listening...")

        listening_info = {
            "is_listening": False,
            "process_info": None,
            "bind_interface": "UNKNOWN",
            "socket_state": "NOT_FOUND",
        }

        # Use netstat to check listening ports
        success, stdout, stderr = self.run_command(["netstat", "-tlnp"])

        if success:
            for line in stdout.split("\n"):
                if f":{self.target_port}" in line and "LISTEN" in line:
                    listening_info["is_listening"] = True
                    listening_info["socket_state"] = "LISTEN"

                    # Parse bind interface
                    parts = line.split()
                    if len(parts) >= 4:
                        local_address = parts[3]
                        if local_address.startswith(
                            "0.0.0.0:"
                        ) or local_address.startswith(":::"):
                            listening_info["bind_interface"] = "ALL_INTERFACES"
                            self.log_success(
                                f"Port {self.target_port} listening on all interfaces"
                            )
                        elif local_address.startswith(
                            "127.0.0.1:"
                        ) or local_address.startswith("::1:"):
                            listening_info["bind_interface"] = "LOCALHOST_ONLY"
                            self.log_warning(
                                f"Port {self.target_port} listening on localhost only"
                            )
                        else:
                            listening_info["bind_interface"] = local_address

                    # Extract process info if available
                    if len(parts) >= 7 and "/" in parts[6]:
                        pid_program = parts[6]
                        listening_info["process_info"] = pid_program
                        self.log_info(f"Process: {pid_program}")

                    break

        if not listening_info["is_listening"]:
            self.log_error(f"Port {self.target_port} is not listening!")

        return listening_info

    def get_detailed_process_info(self, process_info: str) -> Dict:
        """Get detailed information about the process owning the port"""
        if not process_info or "/" not in process_info:
            return {"error": "No process information available"}

        try:
            pid = process_info.split("/")[0]

            # Get process details with ps
            success, stdout, stderr = self.run_command(
                ["ps", "-p", pid, "-o", "pid,ppid,user,cmd"]
            )

            if success:
                lines = stdout.strip().split("\n")
                if len(lines) >= 2:
                    header = lines[0]
                    data = lines[1]

                    return {
                        "pid": pid,
                        "command_line": data,
                        "is_java": "java" in data.lower(),
                        "is_ibgateway": "ibgateway" in data.lower()
                        or "gwclient" in data.lower(),
                    }
        except Exception as e:
            return {"error": str(e)}

        return {"error": "Could not retrieve process information"}

    def test_tcp_connection_basic(self) -> Dict:
        """Test basic TCP connection establishment"""
        self.log_info(f"Testing TCP connection to {self.host}:{self.target_port}...")

        connection_test = {
            "can_connect": False,
            "connection_time_ms": None,
            "socket_behavior": "UNKNOWN",
            "error_details": None,
        }

        try:
            start_time = time.time()

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)

            result = sock.connect_ex((self.host, self.target_port))

            end_time = time.time()
            connection_time = (end_time - start_time) * 1000

            if result == 0:
                connection_test["can_connect"] = True
                connection_test["connection_time_ms"] = round(connection_time, 2)
                self.log_success(
                    f"TCP connection established in {connection_time:.2f}ms"
                )

                # Test socket behavior after connection
                try:
                    # Try to receive data with a short timeout
                    sock.settimeout(2.0)
                    data = sock.recv(1024)

                    if data:
                        connection_test["socket_behavior"] = "DATA_RECEIVED"
                        self.log_info(f"Received {len(data)} bytes of data")
                    else:
                        connection_test["socket_behavior"] = "NO_DATA_RECEIVED"
                        self.log_info("No data received")

                except socket.timeout:
                    connection_test["socket_behavior"] = "TIMEOUT_WAITING_FOR_DATA"
                    self.log_info(
                        "Timeout waiting for data (normal for immediate closure)"
                    )

                except ConnectionResetError:
                    connection_test["socket_behavior"] = "CONNECTION_RESET"
                    self.log_warning("Connection reset by peer (application rejected)")

                except Exception as e:
                    connection_test["socket_behavior"] = f"RECV_ERROR: {str(e)}"

            else:
                connection_test["can_connect"] = False
                connection_test["error_details"] = f"connect_ex returned {result}"
                self.log_error(f"TCP connection failed with error code {result}")

            sock.close()

        except Exception as e:
            connection_test["error_details"] = str(e)
            self.log_error(f"Connection test failed: {e}")

        return connection_test

    def test_tcp_connection_telnet_style(self) -> Dict:
        """Test connection using telnet-style approach"""
        self.log_info("Testing telnet-style connection...")

        telnet_test = {
            "command_used": [
                "timeout",
                "3",
                "telnet",
                self.host,
                str(self.target_port),
            ],
            "connection_successful": False,
            "output": "",
            "behavior_pattern": "UNKNOWN",
        }

        success, stdout, stderr = self.run_command(telnet_test["command_used"])

        telnet_test["output"] = stdout + stderr

        # Analyze telnet output patterns
        combined_output = stdout.lower() + stderr.lower()

        if "connected" in combined_output:
            telnet_test["connection_successful"] = True

            if "connection closed by foreign host" in combined_output:
                telnet_test["behavior_pattern"] = "IMMEDIATE_CLOSURE_BY_SERVER"
                self.log_warning("Telnet: Connected but immediately closed by server")
            elif "escape character" in combined_output:
                telnet_test["behavior_pattern"] = "CONNECTION_ESTABLISHED_WAITING"
                self.log_success("Telnet: Connection established and waiting")
            else:
                telnet_test["behavior_pattern"] = "CONNECTED_UNKNOWN_STATE"

        elif "connection refused" in combined_output:
            telnet_test["behavior_pattern"] = "CONNECTION_REFUSED"
            self.log_error("Telnet: Connection refused (TCP RST)")

        elif "timeout" in combined_output or "timed out" in combined_output:
            telnet_test["behavior_pattern"] = "CONNECTION_TIMEOUT"
            self.log_error("Telnet: Connection timeout")

        else:
            telnet_test["behavior_pattern"] = "UNKNOWN_FAILURE"
            self.log_warning("Telnet: Unknown connection failure")

        return telnet_test

    def check_socket_states(self) -> Dict:
        """Check current socket states for the target port"""
        self.log_info("Checking socket states...")

        socket_states = {
            "active_connections": [],
            "listening_sockets": [],
            "close_wait_connections": [],
        }

        # Use ss command for detailed socket information
        success, stdout, stderr = self.run_command(["ss", "-tulpn"])

        if success:
            for line in stdout.split("\n"):
                if f":{self.target_port}" in line:
                    parts = line.split()
                    if len(parts) >= 6:
                        state = parts[0]
                        local_addr = parts[4] if len(parts) > 4 else ""
                        remote_addr = parts[5] if len(parts) > 5 else ""

                        socket_info = {
                            "state": state,
                            "local_address": local_addr,
                            "remote_address": remote_addr,
                            "line": line.strip(),
                        }

                        if state == "LISTEN":
                            socket_states["listening_sockets"].append(socket_info)
                        elif state in ["ESTABLISHED", "SYN-SENT", "SYN-RECV"]:
                            socket_states["active_connections"].append(socket_info)
                        elif state == "CLOSE-WAIT":
                            socket_states["close_wait_connections"].append(socket_info)
                            self.log_warning(
                                f"Found CLOSE-WAIT connection: {remote_addr}"
                            )

        # Also use lsof for additional information
        success, stdout, stderr = self.run_command(
            ["lsof", "-i", f":{self.target_port}"]
        )

        if success:
            self.log_info("lsof output for port analysis:")
            for line in stdout.split("\n")[1:]:  # Skip header
                if line.strip():
                    self.log_info(f"  {line}")

        return socket_states

    def analyze_layer4_behavior(self) -> Dict:
        """Analyze Layer 4 behavior patterns to determine root cause"""

        analysis = {
            "root_cause_category": "UNKNOWN",
            "confidence_level": "LOW",
            "evidence": [],
            "recommendations": [],
        }

        # Get previous test results
        firewall_result = self.results["diagnostics"].get("firewall")
        listening_result = self.results["diagnostics"].get("port_listening")
        connection_result = self.results["diagnostics"].get("tcp_connection_basic")
        telnet_result = self.results["diagnostics"].get("tcp_connection_telnet")
        socket_states = self.results["diagnostics"].get("socket_states")

        # Analyze patterns

        # Pattern 1: Firewall blocking (would cause connection refused or timeout)
        if (
            firewall_result
            and firewall_result.get("overall_assessment") == "BLOCKS_CONNECTION"
        ):
            analysis["root_cause_category"] = "FIREWALL_BLOCKING"
            analysis["confidence_level"] = "HIGH"
            analysis["evidence"].append(
                "Firewall rules explicitly block the target port"
            )
            analysis["recommendations"].append(
                "Configure firewall to allow connections to the port"
            )

        # Pattern 2: Port not listening (would cause connection refused)
        elif listening_result and not listening_result.get("is_listening"):
            analysis["root_cause_category"] = "SERVICE_NOT_RUNNING"
            analysis["confidence_level"] = "HIGH"
            analysis["evidence"].append("Target port is not in LISTEN state")
            analysis["recommendations"].append(
                "Start IB Gateway and ensure it binds to the correct port"
            )

        # Pattern 3: Application-level rejection (TCP connects but immediately closes)
        elif (
            connection_result
            and connection_result.get("can_connect")
            and telnet_result
            and telnet_result.get("behavior_pattern") == "IMMEDIATE_CLOSURE_BY_SERVER"
        ):
            analysis["root_cause_category"] = "APPLICATION_LEVEL_REJECTION"
            analysis["confidence_level"] = "HIGH"
            analysis["evidence"].extend(
                [
                    "TCP connection establishes successfully",
                    "Server immediately closes the connection",
                    "Pattern consistent with application-level rejection",
                ]
            )

            # Check for CLOSE-WAIT sockets as additional evidence
            if socket_states and socket_states.get("close_wait_connections"):
                analysis["evidence"].append(
                    "CLOSE-WAIT sockets found (server-initiated closure)"
                )
                analysis["confidence_level"] = "VERY_HIGH"

            analysis["recommendations"].extend(
                [
                    "Check IB Gateway API configuration and authentication",
                    "Verify client ID conflicts with other connections",
                    "Review IB Gateway trusted IP settings",
                    "Check for application-specific connection limits",
                    "Examine IB Gateway logs for rejection reasons",
                ]
            )

        # Pattern 4: Network connectivity issues (connection timeout)
        elif connection_result and not connection_result.get("can_connect"):
            error_details = connection_result.get("error_details", "")

            if "timeout" in error_details.lower():
                analysis["root_cause_category"] = "NETWORK_TIMEOUT"
                analysis["confidence_level"] = "MEDIUM"
                analysis["evidence"].append("TCP connection attempts time out")
                analysis["recommendations"].extend(
                    [
                        "Check network routing and connectivity",
                        "Verify target host is reachable",
                        "Check for network firewalls or NAT issues",
                    ]
                )
            else:
                analysis["root_cause_category"] = "CONNECTION_REFUSED"
                analysis["confidence_level"] = "MEDIUM"
                analysis["evidence"].append("TCP connection actively refused")
                analysis["recommendations"].extend(
                    [
                        "Verify service is running and listening",
                        "Check host-based firewall rules",
                        "Confirm correct port number",
                    ]
                )

        return analysis

    def run_full_diagnostic(self) -> Dict:
        """Run complete Layer 4 diagnostic suite"""

        print("🔍 LAYER 4 IB GATEWAY NETWORK DIAGNOSTIC")
        print("=" * 60)
        print(f"Target: {self.host}:{self.target_port} ({self.mode})")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        # 1. Firewall Analysis
        print(f"\n🛡️  FIREWALL ANALYSIS")
        print("-" * 30)

        firewall_info = self.check_firewall_iptables()
        self.results["diagnostics"]["firewall"] = firewall_info

        firewalld_info = self.check_firewall_firewalld()
        if firewalld_info:
            self.results["diagnostics"]["firewalld"] = firewalld_info

        # 2. Port Listening Analysis
        print(f"\n🔌 PORT LISTENING ANALYSIS")
        print("-" * 30)

        listening_info = self.check_port_listening()
        self.results["diagnostics"]["port_listening"] = listening_info

        if listening_info["process_info"]:
            process_details = self.get_detailed_process_info(
                listening_info["process_info"]
            )
            self.results["diagnostics"]["process_details"] = process_details

            if process_details.get("is_ibgateway"):
                self.log_success("Confirmed: Process is IB Gateway")
            elif process_details.get("is_java"):
                self.log_info("Process is Java-based (likely IB Gateway)")
            else:
                self.log_warning("Process may not be IB Gateway")

        # 3. TCP Connection Tests
        print(f"\n🔗 TCP CONNECTION TESTS")
        print("-" * 30)

        connection_info = self.test_tcp_connection_basic()
        self.results["diagnostics"]["tcp_connection_basic"] = connection_info

        telnet_info = self.test_tcp_connection_telnet_style()
        self.results["diagnostics"]["tcp_connection_telnet"] = telnet_info

        # 4. Socket State Analysis
        print(f"\n🔌 SOCKET STATE ANALYSIS")
        print("-" * 30)

        socket_info = self.check_socket_states()
        self.results["diagnostics"]["socket_states"] = socket_info

        # 5. Root Cause Analysis
        print(f"\n🎯 ROOT CAUSE ANALYSIS")
        print("-" * 30)

        analysis = self.analyze_layer4_behavior()
        self.results["diagnostics"]["analysis"] = analysis

        # Display analysis results
        self.log_info(f"Root cause category: {analysis['root_cause_category']}")
        self.log_info(f"Confidence level: {analysis['confidence_level']}")

        if analysis["evidence"]:
            print(f"\n📋 Evidence:")
            for evidence in analysis["evidence"]:
                print(f"   • {evidence}")

        if analysis["recommendations"]:
            print(f"\n💡 Recommendations:")
            for i, rec in enumerate(analysis["recommendations"], 1):
                print(f"   {i}. {rec}")

        # 6. Summary
        print(f"\n" + "=" * 60)
        print("📊 DIAGNOSTIC SUMMARY")
        print("=" * 60)

        if analysis["root_cause_category"] == "APPLICATION_LEVEL_REJECTION":
            print("🎯 CONCLUSION: Application-level rejection confirmed")
            print("   • Layer 4 (TCP) connectivity is working correctly")
            print(
                "   • IB Gateway accepts TCP connections but rejects at application level"
            )
            print(
                "   • Focus troubleshooting on IB API configuration, not network/firewall"
            )

        elif analysis["root_cause_category"] == "FIREWALL_BLOCKING":
            print("🛡️  CONCLUSION: Firewall blocking detected")
            print("   • Network firewall is preventing TCP connections")
            print("   • Configure firewall rules to allow the target port")

        elif analysis["root_cause_category"] == "SERVICE_NOT_RUNNING":
            print("🔌 CONCLUSION: Service not running or not listening")
            print("   • IB Gateway is not listening on the target port")
            print("   • Start IB Gateway and verify port configuration")

        else:
            print("❓ CONCLUSION: Root cause unclear")
            print("   • Review diagnostic details above")
            print("   • May require additional investigation")

        print(f"\n📄 Full diagnostic results saved to: layer4_diagnostic_report.json")

        return self.results

    def save_report(self, filename: str = None):
        """Save diagnostic report to JSON file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"layer4_diagnostic_report_{timestamp}.json"

        with open(filename, "w") as f:
            json.dump(self.results, f, indent=2, default=str)

        self.log_success(f"Report saved to: {filename}")


def main():
    parser = argparse.ArgumentParser(
        description="Layer 4 IB Gateway Network Diagnostic Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python layer4_ib_gateway_diagnostic.py                    # Test paper trading port (4002)
  python layer4_ib_gateway_diagnostic.py --port 4001 --live-mode  # Test live trading port
  python layer4_ib_gateway_diagnostic.py --host 192.168.1.100     # Test remote host
        """,
    )

    parser.add_argument(
        "--port",
        type=int,
        default=4002,
        help="IB Gateway port to test (default: 4002 for paper trading)",
    )
    parser.add_argument(
        "--host", default="localhost", help="Host to test (default: localhost)"
    )
    parser.add_argument(
        "--live-mode",
        action="store_true",
        help="Test live trading port (4001) instead of paper (4002)",
    )
    parser.add_argument("--save-report", help="Save report to specific filename")

    args = parser.parse_args()

    # Override port if live mode specified
    if args.live_mode:
        args.port = 4001

    try:
        # Create diagnostic instance
        diagnostic = Layer4IBGatewayDiagnostic(args.port, args.host)

        # Run full diagnostic
        results = diagnostic.run_full_diagnostic()

        # Save report
        diagnostic.save_report(args.save_report)

        # Exit with appropriate code based on analysis
        analysis = results["diagnostics"].get("analysis", {})
        if analysis.get("root_cause_category") == "APPLICATION_LEVEL_REJECTION":
            # This is actually the expected result - Layer 4 works, application rejects
            print(f"\n✅ Layer 4 diagnostic completed successfully")
            print(
                f"   Network stack is working correctly - focus on application-level issues"
            )
            sys.exit(0)
        else:
            print(f"\n⚠️  Network-level issues detected")
            sys.exit(1)

    except KeyboardInterrupt:
        print(f"\n⚠️ Diagnostic interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Diagnostic failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
