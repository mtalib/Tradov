#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Remote TWS Connection Test Script v2.0
===============================================

Comprehensive testing suite for remote TWS connections with the latest fixes.
Tests network connectivity, TWS API functionality, and Spyder integration.

Features:
- Network connectivity validation
- TWS API handshake testing
- Account retrieval verification
- Performance metrics collection
- Integration with updated SpyderClient modules

Usage:
    python test_remote_tws_connection.py --windows-ip 192.168.1.100
    python test_remote_tws_connection.py --windows-ip 192.168.1.100 --port 7497
    python test_remote_tws_connection.py --windows-ip 192.168.1.100 --full-test
    python test_remote_tws_connection.py --scan-network

Author: Spyder Trading System
Date: 2025-01-15
Version: 2.0 (Updated with latest fixes)
"""

import asyncio
import sys
import time
import json
import socket
import subprocess
import platform
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple, Optional
import argparse
import logging
import traceback

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Add Spyder directory to path
sys.path.insert(0, str(Path(__file__).parent))


class RemoteTWSConnectionTester:
    """Comprehensive remote TWS connection tester"""

    def __init__(self, windows_ip: str, port: int = 7497, client_id: int = 1):
        self.windows_ip = windows_ip
        self.port = port
        self.client_id = client_id
        self.test_results = {}
        self.start_time = datetime.now()

        # Try to import Spyder modules
        self.spyder_available = self._check_spyder_modules()

    def _check_spyder_modules(self) -> bool:
        """Check if Spyder modules are available"""
        try:
            from SpyderB_Broker.SpyderB01_SpyderClient import (
                create_spyder_client,
                create_default_config,
                validate_dependencies,
            )
            from SpyderB_Broker.SpyderB06_RemoteTWSAdapter import (
                RemoteTWSAdapter,
                RemoteTWSConfig,
            )

            logger.info("✅ Spyder modules loaded successfully")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Spyder modules not available: {e}")
            return False

    def print_header(self):
        """Print test header"""
        print("\n" + "=" * 80)
        print("🚀 SPYDER REMOTE TWS CONNECTION TEST v2.0")
        print("=" * 80)
        print(f"📅 Test started: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🖥️ Target Windows IP: {self.windows_ip}")
        print(f"🔌 TWS Port: {self.port}")
        print(f"🆔 Client ID: {self.client_id}")
        print(
            f"📦 Spyder modules: {'Available' if self.spyder_available else 'Not Available'}"
        )
        print("=" * 80)

    def test_network_connectivity(self) -> Dict[str, Any]:
        """Test basic network connectivity"""
        print("\n📡 TESTING NETWORK CONNECTIVITY")
        print("-" * 50)

        results = {
            "ping_test": False,
            "ping_latency": None,
            "port_test": False,
            "port_latency": None,
            "error": None,
        }

        try:
            # Test 1: Ping test
            print(f"🏓 Testing ping to {self.windows_ip}...")
            ping_success, ping_latency = self._test_ping()
            results["ping_test"] = ping_success
            results["ping_latency"] = ping_latency

            if ping_success:
                print(f"   ✅ Ping successful: {ping_latency:.1f}ms")
            else:
                print(f"   ❌ Ping failed")

            # Test 2: Port connectivity
            print(f"🔌 Testing port {self.port} connectivity...")
            port_success, port_latency = self._test_port_connectivity()
            results["port_test"] = port_success
            results["port_latency"] = port_latency

            if port_success:
                print(f"   ✅ Port accessible: {port_latency:.1f}ms")
            else:
                print(f"   ❌ Port {self.port} not accessible")
                print(f"   💡 Make sure TWS is running and API is enabled")

        except Exception as e:
            results["error"] = str(e)
            print(f"   ❌ Network test error: {e}")

        self.test_results["network"] = results
        return results

    def _test_ping(self) -> Tuple[bool, Optional[float]]:
        """Test ping connectivity"""
        try:
            system = platform.system().lower()
            if system == "windows":
                cmd = ["ping", "-n", "1", self.windows_ip]
            else:
                cmd = ["ping", "-c", "1", self.windows_ip]

            start_time = time.time()
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            latency = (time.time() - start_time) * 1000

            return result.returncode == 0, latency
        except Exception:
            return False, None

    def _test_port_connectivity(self) -> Tuple[bool, Optional[float]]:
        """Test TCP port connectivity"""
        try:
            start_time = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10.0)

            result = sock.connect_ex((self.windows_ip, self.port))
            latency = (time.time() - start_time) * 1000
            sock.close()

            return result == 0, latency
        except Exception:
            return False, None

    async def test_tws_api_connection(self) -> Dict[str, Any]:
        """Test TWS API connection using SpyderClient"""
        print("\n🔗 TESTING TWS API CONNECTION")
        print("-" * 50)

        results = {
            "connection_test": False,
            "handshake_time": None,
            "accounts_retrieved": False,
            "accounts": [],
            "race_condition_fix_applied": False,
            "error": None,
        }

        if not self.spyder_available:
            results["error"] = "Spyder modules not available"
            print("   ❌ Cannot test TWS API - Spyder modules not loaded")
            self.test_results["tws_api"] = results
            return results

        try:
            # Import here since we know modules are available
            from SpyderB_Broker.SpyderB01_SpyderClient import (
                create_spyder_client,
                create_default_config,
            )

            print(f"🔧 Creating SpyderClient configuration...")
            config = create_default_config(
                host=self.windows_ip, port=self.port, client_id=self.client_id
            )

            print(f"🚀 Initializing SpyderClient...")
            client = create_spyder_client(config)

            print(f"🤝 Attempting TWS API connection...")
            start_time = time.time()

            # Test connection with proven race condition fix
            success = await client.connect()
            connection_time = time.time() - start_time

            results["handshake_time"] = connection_time
            results["connection_test"] = success

            if success:
                print(f"   ✅ TWS API connection successful!")
                print(f"   ⏱️ Connection time: {connection_time:.2f}s")

                # Check if race condition fix was applied
                status = client.get_connection_status()
                results["race_condition_fix_applied"] = status.get(
                    "race_condition_fix_applied", False
                )

                if results["race_condition_fix_applied"]:
                    print(f"   ✅ Race condition fix applied successfully")

                # Test account retrieval
                print(f"👤 Retrieving managed accounts...")
                accounts = client.get_managed_accounts()
                results["accounts"] = accounts
                results["accounts_retrieved"] = len(accounts) > 0

                if accounts:
                    print(f"   ✅ Accounts retrieved: {accounts}")
                else:
                    print(f"   ⚠️ No accounts returned (this might be normal)")

                # Disconnect
                print(f"🔌 Disconnecting...")
                client.disconnect()
                print(f"   ✅ Disconnected successfully")

            else:
                print(f"   ❌ TWS API connection failed")
                status = client.get_connection_status()
                if status.get("last_error"):
                    print(f"   💬 Error details: {status['last_error']}")

        except Exception as e:
            results["error"] = str(e)
            print(f"   ❌ TWS API test error: {e}")
            traceback.print_exc()

        self.test_results["tws_api"] = results
        return results

    def test_remote_tws_adapter(self) -> Dict[str, Any]:
        """Test RemoteTWSAdapter functionality"""
        print("\n🔄 TESTING REMOTE TWS ADAPTER")
        print("-" * 50)

        results = {
            "adapter_created": False,
            "network_test": False,
            "config_valid": False,
            "error": None,
        }

        if not self.spyder_available:
            results["error"] = "Spyder modules not available"
            print("   ❌ Cannot test RemoteTWSAdapter - Spyder modules not loaded")
            self.test_results["remote_adapter"] = results
            return results

        try:
            from SpyderB_Broker.SpyderB06_RemoteTWSAdapter import (
                RemoteTWSAdapter,
                RemoteTWSConfig,
            )

            print(f"⚙️ Creating RemoteTWSConfig...")
            config = RemoteTWSConfig(
                windows_ip=self.windows_ip,
                paper_port=self.port,
                client_id=self.client_id,
            )
            results["config_valid"] = True
            print(f"   ✅ Configuration created successfully")

            print(f"🔧 Initializing RemoteTWSAdapter...")
            adapter = RemoteTWSAdapter(config)
            results["adapter_created"] = True
            print(f"   ✅ Adapter created successfully")

            print(f"🌐 Testing network connectivity via adapter...")
            network_success, message, latency = adapter.test_network_connectivity()
            results["network_test"] = network_success

            if network_success:
                print(f"   ✅ {message}")
            else:
                print(f"   ❌ {message}")

        except Exception as e:
            results["error"] = str(e)
            print(f"   ❌ RemoteTWSAdapter test error: {e}")
            traceback.print_exc()

        self.test_results["remote_adapter"] = results
        return results

    def scan_network_for_tws(self) -> List[Dict[str, Any]]:
        """Scan network for potential TWS instances"""
        print("\n🔍 SCANNING NETWORK FOR TWS INSTANCES")
        print("-" * 50)

        # Common TWS ports
        tws_ports = [7496, 7497, 4001, 4002]

        # Get network range (assuming /24 subnet)
        ip_parts = self.windows_ip.split(".")
        if len(ip_parts) == 4:
            network_base = ".".join(ip_parts[:3])

            found_instances = []

            for i in range(1, 255):
                test_ip = f"{network_base}.{i}"
                print(f"🔍 Scanning {test_ip}...", end="\r")

                for port in tws_ports:
                    if self._quick_port_test(test_ip, port):
                        instance = {
                            "ip": test_ip,
                            "port": port,
                            "port_type": "Live" if port in [7496, 4001] else "Paper",
                        }
                        found_instances.append(instance)
                        print(
                            f"   ✅ Found TWS at {test_ip}:{port} ({instance['port_type']})"
                        )

            print(
                f"\n📊 Scan complete. Found {len(found_instances)} potential TWS instances."
            )
            return found_instances

        return []

    def _quick_port_test(self, ip: str, port: int, timeout: float = 1.0) -> bool:
        """Quick port connectivity test"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except Exception:
            return False

    def print_summary(self):
        """Print test summary"""
        end_time = datetime.now()
        duration = end_time - self.start_time

        print("\n" + "=" * 80)
        print("📋 TEST SUMMARY")
        print("=" * 80)
        print(f"⏱️ Total test duration: {duration.total_seconds():.1f} seconds")
        print(f"🖥️ Target: {self.windows_ip}:{self.port}")

        # Network results
        if "network" in self.test_results:
            net = self.test_results["network"]
            print(f"\n🌐 Network Connectivity:")
            print(
                f"   Ping: {'✅' if net['ping_test'] else '❌'} "
                f"({net['ping_latency']:.1f}ms)"
                if net["ping_latency"]
                else ""
            )
            print(
                f"   Port {self.port}: {'✅' if net['port_test'] else '❌'} "
                f"({net['port_latency']:.1f}ms)"
                if net["port_latency"]
                else ""
            )

        # TWS API results
        if "tws_api" in self.test_results:
            api = self.test_results["tws_api"]
            print(f"\n🔗 TWS API Connection:")
            print(f"   Connection: {'✅' if api['connection_test'] else '❌'}")
            if api["handshake_time"]:
                print(f"   Handshake time: {api['handshake_time']:.2f}s")
            print(
                f"   Race condition fix: {'✅' if api['race_condition_fix_applied'] else '❌'}"
            )
            print(
                f"   Accounts: {'✅' if api['accounts_retrieved'] else '❌'} "
                f"({len(api['accounts'])} found)"
                if api["accounts"]
                else ""
            )

        # Remote adapter results
        if "remote_adapter" in self.test_results:
            adapter = self.test_results["remote_adapter"]
            print(f"\n🔄 Remote TWS Adapter:")
            print(
                f"   Adapter creation: {'✅' if adapter['adapter_created'] else '❌'}"
            )
            print(f"   Network test: {'✅' if adapter['network_test'] else '❌'}")

        # Overall status
        overall_success = self._calculate_overall_success()
        print(
            f"\n🎯 Overall Status: {'✅ SUCCESS' if overall_success else '❌ ISSUES FOUND'}"
        )

        if not overall_success:
            print("\n💡 Troubleshooting Tips:")
            self._print_troubleshooting_tips()

        print("=" * 80)

    def _calculate_overall_success(self) -> bool:
        """Calculate overall test success"""
        if "network" in self.test_results:
            if not self.test_results["network"]["port_test"]:
                return False

        if "tws_api" in self.test_results:
            if not self.test_results["tws_api"]["connection_test"]:
                return False

        return True

    def _print_troubleshooting_tips(self):
        """Print troubleshooting tips based on test results"""
        if "network" in self.test_results:
            net = self.test_results["network"]
            if not net["ping_test"]:
                print("   • Check network connectivity to Windows computer")
                print("   • Verify Windows computer is powered on and connected")

            if not net["port_test"]:
                print(f"   • Ensure TWS is running on Windows computer")
                print(f"   • Check TWS API settings:")
                print(f"     - Enable 'ActiveX and Socket Clients'")
                print(f"     - Uncheck 'Allow connections from localhost only'")
                print(f"     - Add your Ubuntu IP to 'Trusted IPs'")
                print(f"     - Verify port is set to {self.port}")
                print(f"   • Check Windows Firewall settings")

        if "tws_api" in self.test_results:
            api = self.test_results["tws_api"]
            if not api["connection_test"]:
                print("   • Restart TWS after changing API settings")
                print("   • Try different client ID (1-32)")
                print("   • Check TWS login status")

    def save_results(self, filename: str = None):
        """Save test results to JSON file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"tws_test_results_{timestamp}.json"

        results = {
            "test_info": {
                "windows_ip": self.windows_ip,
                "port": self.port,
                "client_id": self.client_id,
                "test_time": self.start_time.isoformat(),
                "spyder_available": self.spyder_available,
            },
            "results": self.test_results,
        }

        with open(filename, "w") as f:
            json.dump(results, f, indent=2, default=str)

        print(f"📄 Test results saved to: {filename}")


async def main():
    """Main test function"""
    parser = argparse.ArgumentParser(description="Test Remote TWS Connection")
    parser.add_argument(
        "--windows-ip", required=True, help="Windows computer IP address"
    )
    parser.add_argument(
        "--port", type=int, default=7497, help="TWS port (default: 7497 for paper)"
    )
    parser.add_argument(
        "--client-id", type=int, default=1, help="Client ID (default: 1)"
    )
    parser.add_argument(
        "--full-test",
        action="store_true",
        help="Run all tests including remote adapter",
    )
    parser.add_argument(
        "--scan-network", action="store_true", help="Scan network for TWS instances"
    )
    parser.add_argument(
        "--save-results", action="store_true", help="Save results to JSON file"
    )

    args = parser.parse_args()

    # Create tester
    tester = RemoteTWSConnectionTester(args.windows_ip, args.port, args.client_id)
    tester.print_header()

    try:
        # Run tests
        if args.scan_network:
            tester.scan_network_for_tws()

        # Basic network test
        tester.test_network_connectivity()

        # TWS API test
        await tester.test_tws_api_connection()

        # Remote adapter test (if requested)
        if args.full_test:
            tester.test_remote_tws_adapter()

        # Print summary
        tester.print_summary()

        # Save results if requested
        if args.save_results:
            tester.save_results()

    except KeyboardInterrupt:
        print("\n\n⏹️ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    # Handle both sync and async execution
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Failed to run tests: {e}")
        sys.exit(1)
