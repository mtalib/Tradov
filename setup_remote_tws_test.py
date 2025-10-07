#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Remote TWS Test Setup Script
====================================

This script helps prepare your system for remote TWS testing by:
- Checking all dependencies
- Validating network configuration
- Creating test configurations
- Providing setup guidance

Usage:
    python setup_remote_tws_test.py
    python setup_remote_tws_test.py --windows-ip 192.168.1.100
    python setup_remote_tws_test.py --check-only

Author: Spyder Trading System
Date: 2025-01-15
Version: 1.0
"""

import sys
import os
import subprocess
import socket
import platform
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import argparse
import json

# Add Spyder to path
sys.path.insert(0, str(Path(__file__).parent))


class RemoteTWSSetup:
    """Setup and validation for remote TWS testing"""

    def __init__(self):
        self.setup_results = {}
        self.recommendations = []

    def print_header(self):
        """Print setup header"""
        print("\n" + "=" * 70)
        print("🚀 SPYDER REMOTE TWS SETUP & VALIDATION")
        print("=" * 70)
        print("This script will help you prepare for remote TWS testing")
        print("=" * 70)

    def check_dependencies(self) -> Dict[str, bool]:
        """Check all required dependencies"""
        print("\n📦 CHECKING DEPENDENCIES")
        print("-" * 40)

        dependencies = {
            "python_version": False,
            "ib_async": False,
            "spyder_modules": False,
            "network_tools": False,
            "asyncio": False,
        }

        # Check Python version
        python_version = sys.version_info
        if python_version >= (3, 8):
            dependencies["python_version"] = True
            print(
                f"✅ Python {python_version.major}.{python_version.minor}.{python_version.micro}"
            )
        else:
            print(
                f"❌ Python {python_version.major}.{python_version.minor}.{python_version.micro} (requires 3.8+)"
            )
            self.recommendations.append("Upgrade to Python 3.8 or higher")

        # Check ib_async
        try:
            import ib_async

            dependencies["ib_async"] = True
            print(f"✅ ib_async library available")
        except ImportError:
            print(f"❌ ib_async library missing")
            self.recommendations.append("Install ib_async: pip install ib_async")

        # Check Spyder modules
        try:
            from SpyderB_Broker.SpyderB01_SpyderClient import create_spyder_client
            from SpyderB_Broker.SpyderB06_RemoteTWSAdapter import RemoteTWSAdapter

            dependencies["spyder_modules"] = True
            print(f"✅ Spyder modules available")
        except ImportError as e:
            print(f"❌ Spyder modules not found: {e}")
            self.recommendations.append(
                "Ensure you're running from the Spyder directory"
            )

        # Check network tools
        try:
            import socket
            import subprocess

            dependencies["network_tools"] = True
            print(f"✅ Network tools available")
        except ImportError:
            print(f"❌ Network tools missing")
            dependencies["network_tools"] = False

        # Check asyncio
        try:
            import asyncio

            dependencies["asyncio"] = True
            print(f"✅ Asyncio support available")
        except ImportError:
            print(f"❌ Asyncio not available")
            dependencies["asyncio"] = False

        self.setup_results["dependencies"] = dependencies
        return dependencies

    def check_network_configuration(self) -> Dict[str, any]:
        """Check network configuration"""
        print("\n🌐 CHECKING NETWORK CONFIGURATION")
        print("-" * 40)

        network_info = {
            "local_ip": None,
            "network_interface": None,
            "can_ping": False,
            "routing_table": [],
        }

        # Get local IP
        try:
            # Connect to a remote address to determine local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            network_info["local_ip"] = local_ip
            print(f"✅ Local IP address: {local_ip}")
        except Exception as e:
            print(f"⚠️ Could not determine local IP: {e}")

        # Check ping capability
        try:
            system = platform.system().lower()
            if system == "windows":
                cmd = ["ping", "-n", "1", "8.8.8.8"]
            else:
                cmd = ["ping", "-c", "1", "8.8.8.8"]

            result = subprocess.run(cmd, capture_output=True, timeout=10)
            network_info["can_ping"] = result.returncode == 0

            if network_info["can_ping"]:
                print(f"✅ Ping functionality working")
            else:
                print(f"❌ Ping not working")
                self.recommendations.append("Network connectivity issues detected")
        except Exception as e:
            print(f"⚠️ Could not test ping: {e}")

        self.setup_results["network"] = network_info
        return network_info

    def validate_windows_ip(self, windows_ip: str) -> Dict[str, any]:
        """Validate connection to Windows computer"""
        print(f"\n🖥️ VALIDATING WINDOWS COMPUTER: {windows_ip}")
        print("-" * 40)

        validation_results = {
            "ip_format_valid": False,
            "ping_successful": False,
            "ping_latency": None,
            "tws_ports_accessible": {},
            "recommendations": [],
        }

        # Validate IP format
        try:
            socket.inet_aton(windows_ip)
            validation_results["ip_format_valid"] = True
            print(f"✅ IP address format valid: {windows_ip}")
        except socket.error:
            print(f"❌ Invalid IP address format: {windows_ip}")
            validation_results["recommendations"].append(
                "Use valid IP address format (e.g., 192.168.1.100)"
            )
            return validation_results

        # Test ping
        try:
            system = platform.system().lower()
            if system == "windows":
                cmd = ["ping", "-n", "1", windows_ip]
            else:
                cmd = ["ping", "-c", "1", windows_ip]

            import time

            start_time = time.time()
            result = subprocess.run(cmd, capture_output=True, timeout=10)
            latency = (time.time() - start_time) * 1000

            validation_results["ping_successful"] = result.returncode == 0
            validation_results["ping_latency"] = latency

            if validation_results["ping_successful"]:
                print(f"✅ Ping successful: {latency:.1f}ms")
            else:
                print(f"❌ Ping failed to {windows_ip}")
                validation_results["recommendations"].append(
                    "Check Windows computer is on and network connected"
                )
        except Exception as e:
            print(f"⚠️ Could not ping {windows_ip}: {e}")

        # Test TWS ports
        tws_ports = {
            7496: "Live Trading",
            7497: "Paper Trading",
            4001: "Live (alt)",
            4002: "Paper (alt)",
        }

        print(f"\n🔌 Testing TWS ports...")
        for port, description in tws_ports.items():
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5.0)
                result = sock.connect_ex((windows_ip, port))
                sock.close()

                accessible = result == 0
                validation_results["tws_ports_accessible"][port] = accessible

                if accessible:
                    print(f"   ✅ Port {port} ({description}) - ACCESSIBLE")
                else:
                    print(f"   ❌ Port {port} ({description}) - not accessible")
            except Exception as e:
                print(f"   ⚠️ Port {port} test failed: {e}")
                validation_results["tws_ports_accessible"][port] = False

        # Generate recommendations
        accessible_ports = [
            p
            for p, accessible in validation_results["tws_ports_accessible"].items()
            if accessible
        ]

        if not accessible_ports:
            validation_results["recommendations"].extend(
                [
                    "No TWS ports accessible - ensure TWS is running on Windows",
                    "Check TWS API settings: Enable 'ActiveX and Socket Clients'",
                    "Check TWS API settings: Uncheck 'Allow connections from localhost only'",
                    f"Add your IP ({self.setup_results.get('network', {}).get('local_ip', 'unknown')}) to TWS Trusted IPs",
                    "Check Windows Firewall allows connections on TWS ports",
                    "Restart TWS after making configuration changes",
                ]
            )
        elif len(accessible_ports) < 2:
            validation_results["recommendations"].append(
                "Only some TWS ports accessible - check TWS configuration"
            )
        else:
            print(f"✅ TWS appears to be properly configured!")

        self.setup_results["windows_validation"] = validation_results
        return validation_results

    def create_test_configuration(self, windows_ip: str) -> str:
        """Create test configuration file"""
        print(f"\n⚙️ CREATING TEST CONFIGURATION")
        print("-" * 40)

        config = {
            "windows_computer": {
                "ip_address": windows_ip,
                "paper_port": 7497,
                "live_port": 7496,
                "client_id": 1,
            },
            "test_settings": {
                "connection_timeout": 30,
                "enable_race_condition_fix": True,
                "retry_attempts": 3,
            },
            "network_settings": {
                "ping_timeout": 5,
                "port_timeout": 10,
                "latency_test_samples": 5,
            },
        }

        config_file = "tws_test_config.json"

        try:
            with open(config_file, "w") as f:
                json.dump(config, f, indent=2)
            print(f"✅ Configuration saved to: {config_file}")
            return config_file
        except Exception as e:
            print(f"❌ Failed to save configuration: {e}")
            return None

    def print_setup_summary(self):
        """Print setup summary and recommendations"""
        print("\n" + "=" * 70)
        print("📋 SETUP SUMMARY")
        print("=" * 70)

        # Dependencies summary
        deps = self.setup_results.get("dependencies", {})
        print(f"\n📦 Dependencies:")
        for dep, status in deps.items():
            print(f"   {'✅' if status else '❌'} {dep.replace('_', ' ').title()}")

        # Network summary
        network = self.setup_results.get("network", {})
        if network.get("local_ip"):
            print(f"\n🌐 Network:")
            print(f"   Local IP: {network['local_ip']}")
            print(f"   Ping capability: {'✅' if network.get('can_ping') else '❌'}")

        # Windows validation summary
        windows = self.setup_results.get("windows_validation", {})
        if windows:
            print(f"\n🖥️ Windows Computer:")
            print(f"   IP format: {'✅' if windows.get('ip_format_valid') else '❌'}")
            print(f"   Ping: {'✅' if windows.get('ping_successful') else '❌'}")
            if windows.get("ping_latency"):
                print(f"   Latency: {windows['ping_latency']:.1f}ms")

            accessible_ports = sum(
                1
                for accessible in windows.get("tws_ports_accessible", {}).values()
                if accessible
            )
            total_ports = len(windows.get("tws_ports_accessible", {}))
            print(f"   TWS Ports: {accessible_ports}/{total_ports} accessible")

        # Overall readiness
        ready_for_testing = self._calculate_readiness()
        print(f"\n🎯 Ready for Testing: {'✅ YES' if ready_for_testing else '❌ NO'}")

        # Recommendations
        if self.recommendations:
            print(f"\n💡 Recommendations:")
            for i, rec in enumerate(self.recommendations, 1):
                print(f"   {i}. {rec}")

        # Next steps
        print(f"\n🚀 Next Steps:")
        if ready_for_testing:
            print(f"   1. Run the connection test:")
            if windows:
                ip = (
                    list(self.setup_results.get("windows_validation", {}).keys())[0]
                    if self.setup_results.get("windows_validation")
                    else "YOUR_WINDOWS_IP"
                )
                print(f"      python test_remote_tws_connection.py --windows-ip {ip}")
            else:
                print(
                    f"      python test_remote_tws_connection.py --windows-ip YOUR_WINDOWS_IP"
                )
            print(f"   2. If successful, integrate with your trading system")
        else:
            print(f"   1. Address the issues listed in recommendations")
            print(f"   2. Re-run this setup script")
            print(f"   3. Then proceed with connection testing")

        print("=" * 70)

    def _calculate_readiness(self) -> bool:
        """Calculate if system is ready for testing"""
        deps = self.setup_results.get("dependencies", {})
        required_deps = ["python_version", "ib_async", "spyder_modules", "asyncio"]

        if not all(deps.get(dep, False) for dep in required_deps):
            return False

        windows = self.setup_results.get("windows_validation", {})
        if windows:
            if not windows.get("ping_successful"):
                return False

            accessible_ports = sum(
                1
                for accessible in windows.get("tws_ports_accessible", {}).values()
                if accessible
            )
            if accessible_ports == 0:
                return False

        return True

    def save_results(self, filename: str = None):
        """Save setup results to file"""
        if not filename:
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"tws_setup_results_{timestamp}.json"

        results = {
            "setup_info": {
                "timestamp": datetime.now().isoformat(),
                "platform": platform.system(),
                "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            },
            "results": self.setup_results,
            "recommendations": self.recommendations,
            "ready_for_testing": self._calculate_readiness(),
        }

        try:
            with open(filename, "w") as f:
                json.dump(results, f, indent=2, default=str)
            print(f"\n📄 Setup results saved to: {filename}")
        except Exception as e:
            print(f"\n❌ Failed to save results: {e}")


def main():
    """Main setup function"""
    parser = argparse.ArgumentParser(description="Setup Remote TWS Testing Environment")
    parser.add_argument(
        "--windows-ip", help="IP address of Windows computer running TWS"
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check dependencies, don't validate Windows connection",
    )
    parser.add_argument(
        "--save-results", action="store_true", help="Save setup results to JSON file"
    )

    args = parser.parse_args()

    # Create setup instance
    setup = RemoteTWSSetup()
    setup.print_header()

    try:
        # Always check dependencies
        setup.check_dependencies()
        setup.check_network_configuration()

        # Check Windows connection if IP provided
        if args.windows_ip and not args.check_only:
            setup.validate_windows_ip(args.windows_ip)
            setup.create_test_configuration(args.windows_ip)
        elif not args.check_only and not args.windows_ip:
            print(
                f"\n💡 Tip: Use --windows-ip to test connection to your Windows computer"
            )

        # Print summary
        setup.print_setup_summary()

        # Save results if requested
        if args.save_results:
            setup.save_results()

    except KeyboardInterrupt:
        print(f"\n\n⏹️ Setup interrupted by user")
    except Exception as e:
        print(f"\n❌ Setup failed with error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
