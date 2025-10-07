#!/usr/bin/env python3
"""
IB Gateway API Configuration Diagnostic Tool
===========================================

This script performs comprehensive diagnostics on IB Gateway API configuration
to identify why API connections are being rejected at the application level.

The script will:
1. Analyze jts.ini configuration file
2. Check XML configuration files for API settings
3. Verify port configurations and bindings
4. Test different connection approaches
5. Provide specific recommendations for API configuration fixes

Usage:
    python diagnose_ib_gateway_api_config.py
    python diagnose_ib_gateway_api_config.py --verbose
    python diagnose_ib_gateway_api_config.py --fix-config
"""

import os
import sys
import xml.etree.ElementTree as ET
import json
import subprocess
import socket
import time
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import argparse


class IBGatewayAPIConfigDiagnostic:
    """Comprehensive IB Gateway API configuration diagnostic"""

    def __init__(self, verbose=False, auto_fix=False):
        self.verbose = verbose
        self.auto_fix = auto_fix
        self.jts_path = None
        self.config_path = None
        self.findings = {}
        self.recommendations = []

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

    def log_debug(self, message: str):
        if self.verbose:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] 🔍 DEBUG: {message}")

    def find_ib_gateway_config(self) -> bool:
        """Find IB Gateway configuration files"""
        self.log_info("Searching for IB Gateway configuration files...")

        # Find jts.ini
        possible_jts_paths = [
            Path.home() / "Jts" / "jts.ini",
            Path.home() / ".wine" / "drive_c" / "Jts" / "jts.ini",
        ]

        # Search with find command
        try:
            result = subprocess.run(
                ["find", str(Path.home()), "-name", "jts.ini", "-type", "f"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line and "Trash" not in line and "Backup" not in line:
                        possible_jts_paths.append(Path(line))
        except:
            pass

        for path in possible_jts_paths:
            if path.exists():
                self.jts_path = path
                self.log_success(f"Found jts.ini: {path}")
                break

        if not self.jts_path:
            self.log_error("Could not locate jts.ini file")
            return False

        # Find configuration directory
        jts_dir = self.jts_path.parent
        for item in jts_dir.iterdir():
            if item.is_dir() and len(item.name) > 20:  # Long hash-like directory name
                xml_files = list(item.glob("*.xml"))
                if xml_files:
                    self.config_path = item
                    self.log_success(f"Found config directory: {item}")
                    break

        return True

    def analyze_jts_ini(self) -> Dict:
        """Analyze jts.ini configuration file"""
        self.log_info("Analyzing jts.ini configuration...")

        analysis = {
            "file_path": str(self.jts_path),
            "sections": {},
            "api_settings": {},
            "issues": [],
            "recommendations": [],
        }

        try:
            with open(self.jts_path, "r") as f:
                content = f.read()

            current_section = None
            for line_num, line in enumerate(content.split("\n"), 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # Section header
                if line.startswith("[") and line.endswith("]"):
                    current_section = line[1:-1]
                    analysis["sections"][current_section] = {}
                    continue

                # Key-value pair
                if "=" in line and current_section:
                    key, value = line.split("=", 1)
                    key, value = key.strip(), value.strip()
                    analysis["sections"][current_section][key] = value

                    # Track API-related settings
                    if key.lower() in [
                        "trustedips",
                        "localserverport",
                        "apionly",
                        "readonly",
                    ]:
                        analysis["api_settings"][key] = value

            # Analyze API settings
            self.log_debug(f"Found API settings: {analysis['api_settings']}")

            # Check TrustedIPs
            trusted_ips = analysis["api_settings"].get("TrustedIPs", "")
            system_ip = self.get_system_ip()

            if not trusted_ips:
                analysis["issues"].append("No TrustedIPs setting found")
                analysis["recommendations"].append(
                    "Add TrustedIPs setting with system IP"
                )
            elif system_ip not in trusted_ips:
                analysis["issues"].append(
                    f"System IP {system_ip} not in TrustedIPs ({trusted_ips})"
                )
                analysis["recommendations"].append(f"Add {system_ip} to TrustedIPs")
            else:
                self.log_success(f"System IP {system_ip} found in TrustedIPs")

            # Check LocalServerPort
            local_port = analysis["api_settings"].get("LocalServerPort", "")
            if local_port:
                self.log_info(f"LocalServerPort configured as: {local_port}")
            else:
                analysis["issues"].append("No LocalServerPort setting found")

            # Check ApiOnly setting
            api_only = analysis["api_settings"].get("ApiOnly", "")
            if api_only.lower() == "true":
                self.log_success("ApiOnly is enabled (good for headless operation)")
            else:
                self.log_info("ApiOnly is not set or false (GUI mode)")

            return analysis

        except Exception as e:
            self.log_error(f"Failed to analyze jts.ini: {e}")
            analysis["issues"].append(f"Failed to read file: {e}")
            return analysis

    def analyze_xml_config(self) -> Dict:
        """Analyze XML configuration files"""
        self.log_info("Analyzing XML configuration files...")

        analysis = {
            "config_path": str(self.config_path) if self.config_path else None,
            "xml_files": [],
            "api_settings": {},
            "issues": [],
            "recommendations": [],
        }

        if not self.config_path:
            analysis["issues"].append("No XML configuration directory found")
            return analysis

        try:
            xml_files = list(self.config_path.glob("*.xml"))
            self.log_debug(f"Found XML files: {[f.name for f in xml_files]}")

            for xml_file in xml_files:
                try:
                    tree = ET.parse(xml_file)
                    root = tree.getroot()

                    file_info = {
                        "file": xml_file.name,
                        "root_tag": root.tag,
                        "api_elements": [],
                    }

                    # Look for API-related elements
                    api_keywords = [
                        "api",
                        "socket",
                        "client",
                        "trusted",
                        "port",
                        "connection",
                    ]

                    def search_elements(element, path=""):
                        for child in element:
                            child_path = f"{path}/{child.tag}" if path else child.tag

                            # Check if element relates to API
                            element_text = (child.text or "").lower()
                            element_tag = child.tag.lower()

                            for keyword in api_keywords:
                                if keyword in element_tag or keyword in element_text:
                                    file_info["api_elements"].append(
                                        {
                                            "path": child_path,
                                            "tag": child.tag,
                                            "text": child.text,
                                            "attributes": dict(child.attrib),
                                        }
                                    )
                                    break

                            search_elements(child, child_path)

                    search_elements(root)
                    analysis["xml_files"].append(file_info)

                    self.log_debug(
                        f"XML {xml_file.name}: {len(file_info['api_elements'])} API-related elements"
                    )

                except Exception as e:
                    self.log_warning(f"Failed to parse {xml_file.name}: {e}")

            return analysis

        except Exception as e:
            self.log_error(f"Failed to analyze XML files: {e}")
            analysis["issues"].append(f"XML analysis failed: {e}")
            return analysis

    def check_port_configuration(self) -> Dict:
        """Check port configuration and actual listening status"""
        self.log_info("Checking port configuration...")

        analysis = {
            "configured_ports": [],
            "listening_ports": [],
            "port_issues": [],
            "recommendations": [],
        }

        try:
            # Get configured ports from jts.ini
            if hasattr(self, "findings") and "jts_ini" in self.findings:
                local_port = self.findings["jts_ini"]["api_settings"].get(
                    "LocalServerPort"
                )
                if local_port:
                    analysis["configured_ports"].append(int(local_port))

            # Standard IB ports
            standard_ports = [4001, 4002, 7496, 7497]

            # Check which ports are actually listening
            result = subprocess.run(
                ["netstat", "-tlnp"], capture_output=True, text=True, timeout=10
            )

            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    for port in standard_ports:
                        if f":{port}" in line and "LISTEN" in line:
                            # Extract process info
                            parts = line.split()
                            if len(parts) >= 7 and "/" in parts[6]:
                                pid_program = parts[6]
                                analysis["listening_ports"].append(
                                    {
                                        "port": port,
                                        "process": pid_program,
                                        "is_java": "java" in pid_program.lower(),
                                    }
                                )
                                self.log_success(
                                    f"Port {port} is listening (process: {pid_program})"
                                )

            # Check for port mismatches
            listening_port_nums = [p["port"] for p in analysis["listening_ports"]]

            if not listening_port_nums:
                analysis["port_issues"].append("No IB Gateway ports are listening")
                analysis["recommendations"].append(
                    "Start IB Gateway and verify it binds to API ports"
                )

            if analysis["configured_ports"] and not any(
                p in listening_port_nums for p in analysis["configured_ports"]
            ):
                analysis["port_issues"].append(
                    f"Configured port {analysis['configured_ports']} not listening"
                )
                analysis["recommendations"].append(
                    "Check port configuration or restart IB Gateway"
                )

            return analysis

        except Exception as e:
            self.log_error(f"Port configuration check failed: {e}")
            analysis["port_issues"].append(f"Port check failed: {e}")
            return analysis

    def test_api_connection_patterns(self) -> Dict:
        """Test different API connection patterns"""
        self.log_info("Testing API connection patterns...")

        analysis = {
            "connection_tests": [],
            "patterns_observed": [],
            "likely_causes": [],
        }

        # Get listening ports from previous check
        listening_ports = []
        if hasattr(self, "findings") and "ports" in self.findings:
            listening_ports = [
                p["port"] for p in self.findings["ports"]["listening_ports"]
            ]

        if not listening_ports:
            listening_ports = [4002]  # Default fallback

        for port in listening_ports:
            test_results = {
                "port": port,
                "tcp_connect": False,
                "immediate_close": False,
                "data_received": False,
                "connection_time_ms": None,
                "error_details": None,
            }

            try:
                self.log_debug(f"Testing connection to port {port}")

                start_time = time.time()
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5.0)

                result = sock.connect_ex(("localhost", port))
                end_time = time.time()

                if result == 0:
                    test_results["tcp_connect"] = True
                    test_results["connection_time_ms"] = round(
                        (end_time - start_time) * 1000, 2
                    )

                    # Try to receive data
                    try:
                        sock.settimeout(2.0)
                        data = sock.recv(1024)
                        if data:
                            test_results["data_received"] = True
                            self.log_debug(f"Port {port}: Received {len(data)} bytes")
                        else:
                            test_results["immediate_close"] = True
                            self.log_debug(
                                f"Port {port}: Connection established but no data"
                            )
                    except socket.timeout:
                        test_results["immediate_close"] = True
                        self.log_debug(f"Port {port}: Timeout waiting for data")
                    except ConnectionResetError:
                        test_results["immediate_close"] = True
                        test_results["error_details"] = "Connection reset by peer"
                        self.log_debug(f"Port {port}: Connection reset by peer")

                else:
                    test_results["error_details"] = f"Connection failed: {result}"
                    self.log_debug(f"Port {port}: Connection failed with code {result}")

                sock.close()

            except Exception as e:
                test_results["error_details"] = str(e)
                self.log_debug(f"Port {port}: Exception: {e}")

            analysis["connection_tests"].append(test_results)

        # Analyze patterns
        tcp_success_count = sum(
            1 for t in analysis["connection_tests"] if t["tcp_connect"]
        )
        immediate_close_count = sum(
            1 for t in analysis["connection_tests"] if t["immediate_close"]
        )

        if tcp_success_count > 0 and immediate_close_count > 0:
            analysis["patterns_observed"].append("TCP connects but immediately closes")
            analysis["likely_causes"].extend(
                [
                    "API authentication/authorization failure",
                    "Client IP not in trusted list",
                    "API not properly enabled in IB Gateway",
                    "Client ID conflicts or limits exceeded",
                ]
            )

        if tcp_success_count == 0:
            analysis["patterns_observed"].append("TCP connection failures")
            analysis["likely_causes"].extend(
                [
                    "IB Gateway not running or not listening",
                    "Port configuration mismatch",
                    "Firewall blocking connections",
                ]
            )

        return analysis

    def check_api_enablement_settings(self) -> Dict:
        """Check if API is properly enabled in IB Gateway settings"""
        self.log_info("Checking API enablement settings...")

        analysis = {"settings_found": {}, "missing_settings": [], "recommendations": []}

        # Check jts.ini for API settings
        jts_settings = self.findings.get("jts_ini", {}).get("api_settings", {})

        # Required API settings
        required_settings = {
            "ApiOnly": "Should be true for API-only operation",
            "TrustedIPs": "Must include client IP addresses",
            "LocalServerPort": "Should specify API port (4001/4002)",
        }

        for setting, description in required_settings.items():
            if setting in jts_settings:
                analysis["settings_found"][setting] = {
                    "value": jts_settings[setting],
                    "description": description,
                }
            else:
                analysis["missing_settings"].append(setting)
                analysis["recommendations"].append(
                    f"Add {setting} setting: {description}"
                )

        # Check for common API configuration issues
        trusted_ips = jts_settings.get("TrustedIPs", "")
        if trusted_ips:
            if trusted_ips == "127.0.0.1":
                analysis["recommendations"].append(
                    "TrustedIPs only includes localhost - add system IP for external connections"
                )
            elif "0.0.0.0" in trusted_ips:
                self.log_warning(
                    "TrustedIPs includes 0.0.0.0 (allows all IPs - security risk)"
                )

        # Check ApiOnly setting
        api_only = jts_settings.get("ApiOnly", "").lower()
        if api_only != "true":
            analysis["recommendations"].append(
                "Set ApiOnly=true for headless API operation"
            )

        return analysis

    def get_system_ip(self) -> str:
        """Get system's primary IP address"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except:
            return "127.0.0.1"

    def generate_fix_recommendations(self) -> List[str]:
        """Generate specific fix recommendations based on findings"""
        recommendations = []

        # Check for trusted IP issues
        jts_analysis = self.findings.get("jts_ini", {})
        if "System IP" in str(jts_analysis.get("issues", [])):
            system_ip = self.get_system_ip()
            recommendations.append(
                f"Add system IP ({system_ip}) to TrustedIPs in jts.ini"
            )

        # Check for missing API settings
        api_analysis = self.findings.get("api_settings", {})
        if api_analysis.get("missing_settings"):
            recommendations.append("Add missing API configuration settings to jts.ini")

        # Check for connection pattern issues
        connection_analysis = self.findings.get("connection_tests", {})
        if "TCP connects but immediately closes" in connection_analysis.get(
            "patterns_observed", []
        ):
            recommendations.extend(
                [
                    "Verify IB Gateway GUI API settings: 'Enable ActiveX and Socket Clients'",
                    "Check for client ID conflicts with other applications",
                    "Ensure correct trading mode (paper/live) is selected",
                    "Review IB Gateway logs for specific rejection reasons",
                ]
            )

        # Port configuration issues
        port_analysis = self.findings.get("ports", {})
        if port_analysis.get("port_issues"):
            recommendations.append("Restart IB Gateway to apply configuration changes")

        return recommendations

    def create_fixed_config(self) -> bool:
        """Create a fixed configuration file"""
        if not self.auto_fix:
            return False

        self.log_info("Creating fixed configuration...")

        try:
            # Backup original
            backup_path = (
                f"{self.jts_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )

            with open(self.jts_path, "r") as f:
                content = f.read()

            with open(backup_path, "w") as f:
                f.write(content)

            # Apply fixes
            system_ip = self.get_system_ip()

            # Update TrustedIPs
            if "TrustedIPs=" in content:
                content = re.sub(
                    r"TrustedIPs=.*$",
                    f"TrustedIPs=127.0.0.1,{system_ip}",
                    content,
                    flags=re.MULTILINE,
                )
            else:
                # Add to IBGateway section
                content = re.sub(
                    r"(\[IBGateway\])",
                    f"\\1\nTrustedIPs=127.0.0.1,{system_ip}",
                    content,
                )

            # Ensure ApiOnly is set
            if "ApiOnly=" not in content:
                content = re.sub(r"(\[IBGateway\])", f"\\1\nApiOnly=true", content)

            with open(self.jts_path, "w") as f:
                f.write(content)

            self.log_success(f"Configuration fixed. Backup saved to: {backup_path}")
            return True

        except Exception as e:
            self.log_error(f"Failed to fix configuration: {e}")
            return False

    def run_comprehensive_diagnosis(self) -> Dict:
        """Run complete diagnostic suite"""
        print("🔍 IB GATEWAY API CONFIGURATION DIAGNOSTIC")
        print("=" * 60)
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Mode: {'AUTO-FIX' if self.auto_fix else 'ANALYSIS ONLY'}")
        print("=" * 60)

        # Step 1: Find configuration files
        if not self.find_ib_gateway_config():
            return {"error": "Could not locate IB Gateway configuration files"}

        # Step 2: Analyze jts.ini
        print("\n📄 JTS.INI ANALYSIS")
        print("-" * 30)
        self.findings["jts_ini"] = self.analyze_jts_ini()

        # Step 3: Analyze XML configuration
        print("\n🔧 XML CONFIGURATION ANALYSIS")
        print("-" * 30)
        self.findings["xml_config"] = self.analyze_xml_config()

        # Step 4: Check port configuration
        print("\n🔌 PORT CONFIGURATION ANALYSIS")
        print("-" * 30)
        self.findings["ports"] = self.check_port_configuration()

        # Step 5: Test connection patterns
        print("\n🔗 CONNECTION PATTERN TESTING")
        print("-" * 30)
        self.findings["connection_tests"] = self.test_api_connection_patterns()

        # Step 6: Check API enablement
        print("\n⚙️  API ENABLEMENT CHECK")
        print("-" * 30)
        self.findings["api_settings"] = self.check_api_enablement_settings()

        # Step 7: Generate recommendations
        print("\n💡 GENERATING RECOMMENDATIONS")
        print("-" * 30)
        self.recommendations = self.generate_fix_recommendations()

        # Step 8: Auto-fix if requested
        if self.auto_fix:
            print("\n🛠️  APPLYING FIXES")
            print("-" * 30)
            self.create_fixed_config()

        # Display results
        self.display_results()

        return self.findings

    def display_results(self):
        """Display diagnostic results"""
        print("\n" + "=" * 60)
        print("📊 DIAGNOSTIC RESULTS")
        print("=" * 60)

        # Summary of issues found
        total_issues = 0
        for category, data in self.findings.items():
            if isinstance(data, dict):
                issues = (
                    data.get("issues", [])
                    + data.get("port_issues", [])
                    + data.get("missing_settings", [])
                )
                if issues:
                    print(f"\n🔴 {category.upper()} ISSUES:")
                    for issue in issues:
                        print(f"   • {issue}")
                    total_issues += len(issues)

        # Connection test results
        connection_tests = self.findings.get("connection_tests", {}).get(
            "connection_tests", []
        )
        if connection_tests:
            print(f"\n🔗 CONNECTION TEST RESULTS:")
            for test in connection_tests:
                port = test["port"]
                status = "✅ SUCCESS" if test["tcp_connect"] else "❌ FAILED"
                details = (
                    f"({test['connection_time_ms']}ms)"
                    if test["tcp_connect"]
                    else f"({test['error_details']})"
                )
                print(f"   Port {port}: {status} {details}")

        # Recommendations
        if self.recommendations:
            print(f"\n💡 RECOMMENDATIONS:")
            for i, rec in enumerate(self.recommendations, 1):
                print(f"   {i}. {rec}")

        # Final assessment
        print(f"\n" + "=" * 60)
        if total_issues == 0:
            print("✅ NO CONFIGURATION ISSUES FOUND")
            print("   IB Gateway API configuration appears correct")
        else:
            print(f"⚠️  {total_issues} CONFIGURATION ISSUES DETECTED")
            print("   Follow recommendations above to fix API configuration")

        print("\n🔄 NEXT STEPS:")
        print("   1. Apply recommended configuration changes")
        print("   2. Restart IB Gateway to load new settings")
        print("   3. Test API connections from your applications")
        print("   4. Monitor IB Gateway logs for connection details")


def main():
    parser = argparse.ArgumentParser(
        description="IB Gateway API Configuration Diagnostic Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python diagnose_ib_gateway_api_config.py                    # Basic diagnosis
  python diagnose_ib_gateway_api_config.py --verbose          # Detailed output
  python diagnose_ib_gateway_api_config.py --fix-config       # Auto-fix configuration
        """,
    )

    parser.add_argument(
        "--verbose", action="store_true", help="Enable verbose/debug output"
    )
    parser.add_argument(
        "--fix-config",
        action="store_true",
        help="Automatically fix configuration issues",
    )
    parser.add_argument(
        "--save-report", help="Save diagnostic report to specified JSON file"
    )

    args = parser.parse_args()

    try:
        diagnostic = IBGatewayAPIConfigDiagnostic(
            verbose=args.verbose, auto_fix=args.fix_config
        )

        results = diagnostic.run_comprehensive_diagnosis()

        # Save report if requested
        if args.save_report:
            with open(args.save_report, "w") as f:
                json.dump(results, f, indent=2, default=str)
            print(f"\n📄 Report saved to: {args.save_report}")

        # Exit with appropriate code
        has_issues = any(
            bool(
                data.get("issues", [])
                + data.get("port_issues", [])
                + data.get("missing_settings", [])
            )
            for data in results.values()
            if isinstance(data, dict)
        )

        sys.exit(1 if has_issues else 0)

    except KeyboardInterrupt:
        print("\n⚠️ Diagnostic interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Diagnostic failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
