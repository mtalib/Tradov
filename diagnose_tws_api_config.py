#!/usr/bin/env python3
"""
TWS API Configuration Diagnostic Tool
====================================

This script helps diagnose TWS API configuration issues on the Windows computer.
It provides step-by-step verification and troubleshooting guidance.

Author: Spyder Trading System
Version: 1.0
Date: 2025-10-04
"""

import socket
import time
import argparse
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class TWSAPIConfigDiagnostic:
    """Comprehensive TWS API configuration diagnostic tool."""

    def __init__(self, windows_ip: str, port: int = 7497):
        self.windows_ip = windows_ip
        self.port = port
        self.results = {}
        self.start_time = datetime.now()

    def print_header(self):
        """Print diagnostic header."""
        print("=" * 80)
        print("🔧 TWS API CONFIGURATION DIAGNOSTIC TOOL v1.0")
        print("=" * 80)
        print(f"📅 Started: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🖥️ Target Windows IP: {self.windows_ip}")
        print(f"🔌 TWS Port: {self.port}")
        print("=" * 80)
        print()

    def test_basic_connectivity(self) -> Dict:
        """Test basic network connectivity."""
        print("🌐 TESTING BASIC CONNECTIVITY")
        print("-" * 50)

        results = {
            "ping_success": False,
            "ping_time": None,
            "port_accessible": False,
            "port_time": None,
            "socket_connect": False,
            "socket_time": None,
        }

        # Test ping
        print(f"🏓 Testing ping to {self.windows_ip}...")
        try:
            import subprocess

            result = subprocess.run(
                ["ping", "-c", "1", self.windows_ip],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                # Extract ping time from output
                lines = result.stdout.split("\n")
                for line in lines:
                    if "time=" in line:
                        time_str = line.split("time=")[1].split(" ")[0]
                        results["ping_time"] = float(time_str)
                        break
                results["ping_success"] = True
                print(f"   ✅ Ping successful: {results['ping_time']}ms")
            else:
                print("   ❌ Ping failed")
        except Exception as e:
            print(f"   ❌ Ping error: {e}")

        # Test port accessibility
        print(f"🔌 Testing port {self.port} accessibility...")
        try:
            start_time = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((self.windows_ip, self.port))
            end_time = time.time()
            sock.close()

            if result == 0:
                results["port_accessible"] = True
                results["port_time"] = (end_time - start_time) * 1000
                print(f"   ✅ Port accessible: {results['port_time']:.1f}ms")
            else:
                print(f"   ❌ Port not accessible (error code: {result})")
        except Exception as e:
            print(f"   ❌ Port test error: {e}")

        # Test socket connection (more detailed)
        print(f"🔗 Testing socket connection to {self.windows_ip}:{self.port}...")
        try:
            start_time = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((self.windows_ip, self.port))
            end_time = time.time()

            results["socket_connect"] = True
            results["socket_time"] = (end_time - start_time) * 1000
            print(f"   ✅ Socket connection successful: {results['socket_time']:.1f}ms")

            # Try to send some data to see if TWS responds
            print("📡 Testing TWS API handshake...")
            try:
                # Send a minimal TWS API handshake
                handshake_msg = b"API\x00\x00\x00\x02\x00\x00\x00\x01"
                sock.send(handshake_msg)
                sock.settimeout(5)
                response = sock.recv(1024)
                if response:
                    print(f"   ✅ TWS responded with {len(response)} bytes")
                    results["tws_responds"] = True
                    results["response_size"] = len(response)
                else:
                    print("   ❌ TWS did not respond to handshake")
                    results["tws_responds"] = False
            except socket.timeout:
                print("   ❌ TWS handshake timeout (API likely not enabled)")
                results["tws_responds"] = False
                results["handshake_timeout"] = True
            except Exception as e:
                print(f"   ❌ TWS handshake error: {e}")
                results["tws_responds"] = False

            sock.close()

        except socket.timeout:
            print("   ❌ Socket connection timeout")
        except ConnectionRefusedError:
            print("   ❌ Connection refused (TWS not running or port closed)")
        except Exception as e:
            print(f"   ❌ Socket connection error: {e}")

        print()
        self.results["connectivity"] = results
        return results

    def analyze_handshake_behavior(self) -> Dict:
        """Analyze TWS handshake behavior in detail."""
        print("🤝 ANALYZING TWS HANDSHAKE BEHAVIOR")
        print("-" * 50)

        results = {
            "handshake_attempts": [],
            "consistent_timeout": True,
            "timeout_duration": None,
        }

        for attempt in range(3):
            print(f"🔄 Handshake attempt {attempt + 1}/3...")

            attempt_result = {
                "attempt": attempt + 1,
                "connected": False,
                "handshake_success": False,
                "timeout": False,
                "error": None,
                "duration": None,
            }

            try:
                start_time = time.time()
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(15)  # 15 second timeout for detailed analysis

                # Connect
                sock.connect((self.windows_ip, self.port))
                attempt_result["connected"] = True
                print(f"   ✅ Socket connected")

                # Send TWS API handshake
                handshake_msg = b"API\x00\x00\x00\x02\x00\x00\x00\x01"
                sock.send(handshake_msg)
                print(f"   📤 Sent handshake message")

                # Wait for response
                try:
                    response = sock.recv(1024)
                    end_time = time.time()
                    attempt_result["duration"] = end_time - start_time

                    if response:
                        attempt_result["handshake_success"] = True
                        print(
                            f"   ✅ Handshake successful ({len(response)} bytes in {attempt_result['duration']:.1f}s)"
                        )
                    else:
                        print(
                            f"   ❌ Empty response after {attempt_result['duration']:.1f}s"
                        )

                except socket.timeout:
                    end_time = time.time()
                    attempt_result["timeout"] = True
                    attempt_result["duration"] = end_time - start_time
                    print(
                        f"   ⏰ Handshake timeout after {attempt_result['duration']:.1f}s"
                    )

                sock.close()

            except Exception as e:
                end_time = time.time()
                attempt_result["error"] = str(e)
                attempt_result["duration"] = end_time - start_time
                print(f"   ❌ Error: {e}")

            results["handshake_attempts"].append(attempt_result)

            # Wait between attempts
            if attempt < 2:
                print("   ⏳ Waiting 3 seconds...")
                time.sleep(3)

        # Analyze consistency
        timeouts = [a for a in results["handshake_attempts"] if a.get("timeout")]
        if len(timeouts) == len(results["handshake_attempts"]):
            results["consistent_timeout"] = True
            avg_timeout = sum(a["duration"] for a in timeouts) / len(timeouts)
            results["timeout_duration"] = avg_timeout
            print(
                f"🔍 Analysis: Consistent timeout pattern ({avg_timeout:.1f}s average)"
            )
        else:
            results["consistent_timeout"] = False
            print("🔍 Analysis: Inconsistent behavior detected")

        print()
        self.results["handshake"] = results
        return results

    def check_common_ports(self) -> Dict:
        """Check other common TWS ports."""
        print("🔍 CHECKING COMMON TWS PORTS")
        print("-" * 50)

        common_ports = [
            7496,
            7497,
            4001,
            4002,
        ]  # Live, Paper, Gateway Live, Gateway Paper
        results = {}

        for port in common_ports:
            print(f"🔌 Testing port {port}...")
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                result = sock.connect_ex((self.windows_ip, port))
                sock.close()

                if result == 0:
                    results[port] = {
                        "accessible": True,
                        "description": self._get_port_description(port),
                    }
                    print(
                        f"   ✅ Port {port} accessible ({self._get_port_description(port)})"
                    )
                else:
                    results[port] = {
                        "accessible": False,
                        "description": self._get_port_description(port),
                    }
                    print(
                        f"   ❌ Port {port} not accessible ({self._get_port_description(port)})"
                    )

            except Exception as e:
                results[port] = {"accessible": False, "error": str(e)}
                print(f"   ❌ Port {port} error: {e}")

        print()
        self.results["ports"] = results
        return results

    def _get_port_description(self, port: int) -> str:
        """Get description for common TWS ports."""
        descriptions = {
            7496: "TWS Live Trading",
            7497: "TWS Paper Trading",
            4001: "IB Gateway Live Trading",
            4002: "IB Gateway Paper Trading",
        }
        return descriptions.get(port, "Unknown")

    def generate_configuration_guide(self) -> str:
        """Generate step-by-step TWS configuration guide."""
        guide = """
🛠️ TWS API CONFIGURATION GUIDE
================================

Based on the diagnostic results, here's how to configure TWS API:

📋 STEP-BY-STEP CONFIGURATION:

1. 🚀 START TWS
   - Launch TWS on your Windows computer (192.168.1.250)
   - Log in with your Interactive Brokers credentials
   - Wait for TWS to fully load (market data should be visible)

2. ⚙️ OPEN API SETTINGS
   - In TWS, go to: File → Global Configuration → API → Settings
   - Or use the gear icon → Configure → API → Settings

3. 🔧 CONFIGURE API SETTINGS
   - ✅ Check "Enable ActiveX and Socket Clients"
   - ✅ Check "Allow connections from localhost only" (UNCHECK THIS!)
   - ✅ Set "Socket port" to 7497 (for paper trading) or 7496 (for live)
   - ✅ Add "192.168.1.9" to "Trusted IPs" list
   - ✅ Set "Master API client ID" to 0 (or leave default)
   - ✅ Check "Read-Only API" if you only need market data

4. 💾 SAVE AND RESTART
   - Click "OK" to save settings
   - Completely close TWS (File → Exit)
   - Restart TWS and log in again
   - Wait for TWS to fully initialize

5. 🔍 VERIFY SETTINGS
   - Go back to API settings to confirm all changes are saved
   - Check that the socket port shows your chosen port (7497/7496)
   - Verify "192.168.1.9" is in the Trusted IPs list

6. 🧪 TEST CONNECTION
   - Run: python test_remote_tws_connection.py --windows-ip 192.168.1.250
   - Connection should now succeed

⚠️ COMMON ISSUES:
   - Settings not saved: Make sure to click "OK", not just close the window
   - Port conflicts: If 7497 doesn't work, try 7496
   - Firewall: Windows Firewall might block the connection
   - TWS version: Older TWS versions have different menu layouts

🔥 TROUBLESHOOTING:
   - If still failing: Restart Windows computer
   - Check Windows Firewall settings for TWS
   - Try connecting from Windows computer to itself first (localhost test)
   - Verify TWS is not in "offline" mode

📞 CLIENT ID RANGES:
   - Spyder uses client IDs 1-32
   - Each connection needs a unique client ID
   - If client ID conflicts occur, TWS will reject the connection
"""
        return guide

    def print_summary(self):
        """Print comprehensive diagnostic summary."""
        print("=" * 80)
        print("📋 DIAGNOSTIC SUMMARY")
        print("=" * 80)

        duration = (datetime.now() - self.start_time).total_seconds()
        print(f"⏱️ Total diagnostic time: {duration:.1f} seconds")
        print(f"🖥️ Target: {self.windows_ip}:{self.port}")
        print()

        # Network connectivity summary
        if "connectivity" in self.results:
            conn = self.results["connectivity"]
            print("🌐 Network Connectivity:")
            ping_status = "✅" if conn.get("ping_success") else "❌"
            port_status = "✅" if conn.get("port_accessible") else "❌"
            socket_status = "✅" if conn.get("socket_connect") else "❌"

            print(f"   Ping: {ping_status}")
            print(f"   Port {self.port}: {port_status}")
            print(f"   Socket: {socket_status}")

            if conn.get("tws_responds"):
                print(f"   TWS Response: ✅ ({conn.get('response_size', 0)} bytes)")
            elif conn.get("handshake_timeout"):
                print("   TWS Response: ❌ (API likely not enabled)")
            else:
                print("   TWS Response: ❌ (No response)")

        print()

        # Handshake analysis summary
        if "handshake" in self.results:
            hs = self.results["handshake"]
            print("🤝 TWS API Handshake:")
            successful = sum(
                1 for a in hs["handshake_attempts"] if a.get("handshake_success")
            )
            total = len(hs["handshake_attempts"])
            print(f"   Success rate: {successful}/{total}")

            if hs.get("consistent_timeout"):
                print(
                    f"   Consistent timeout: ✅ ({hs.get('timeout_duration', 0):.1f}s avg)"
                )
                print("   🔍 This suggests TWS API is not enabled")
            else:
                print("   Behavior: ❌ Inconsistent")

        print()

        # Available ports summary
        if "ports" in self.results:
            print("🔌 Available Ports:")
            for port, info in self.results["ports"].items():
                status = "✅" if info.get("accessible") else "❌"
                desc = info.get("description", "Unknown")
                print(f"   Port {port}: {status} ({desc})")

        print()

        # Overall diagnosis
        network_ok = self.results.get("connectivity", {}).get("socket_connect", False)
        api_ok = any(
            a.get("handshake_success")
            for a in self.results.get("handshake", {}).get("handshake_attempts", [])
        )

        print("🎯 Overall Diagnosis:")
        if network_ok and api_ok:
            print("   ✅ TWS API is properly configured and working")
        elif network_ok and not api_ok:
            print("   ⚠️ Network OK, but TWS API not responding")
            print("   💡 Solution: Configure TWS API settings (see guide below)")
        else:
            print("   ❌ Network connectivity issues")
            print("   💡 Solution: Check network configuration and TWS status")

        print("=" * 80)

        # Show configuration guide
        print(self.generate_configuration_guide())

    def save_results(self, filename: Optional[str] = None):
        """Save diagnostic results to JSON file."""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"tws_api_diagnostic_{timestamp}.json"

        self.results["diagnostic_info"] = {
            "windows_ip": self.windows_ip,
            "port": self.port,
            "start_time": self.start_time.isoformat(),
            "end_time": datetime.now().isoformat(),
            "duration_seconds": (datetime.now() - self.start_time).total_seconds(),
        }

        try:
            with open(filename, "w") as f:
                json.dump(self.results, f, indent=2, default=str)
            print(f"💾 Results saved to: {filename}")
        except Exception as e:
            print(f"❌ Failed to save results: {e}")


def main():
    """Main diagnostic function."""
    parser = argparse.ArgumentParser(
        description="TWS API Configuration Diagnostic Tool"
    )
    parser.add_argument(
        "--windows-ip", required=True, help="IP address of Windows computer running TWS"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=7497,
        help="TWS port (default: 7497 for paper trading)",
    )
    parser.add_argument(
        "--save-results", action="store_true", help="Save results to JSON file"
    )

    args = parser.parse_args()

    # Create diagnostic tool
    diagnostic = TWSAPIConfigDiagnostic(args.windows_ip, args.port)

    try:
        # Run diagnostics
        diagnostic.print_header()
        diagnostic.test_basic_connectivity()
        diagnostic.analyze_handshake_behavior()
        diagnostic.check_common_ports()
        diagnostic.print_summary()

        # Save results if requested
        if args.save_results:
            diagnostic.save_results()

    except KeyboardInterrupt:
        print("\n\n⏹️ Diagnostic interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Diagnostic error: {e}")
        logger.exception("Diagnostic failed")


if __name__ == "__main__":
    main()
