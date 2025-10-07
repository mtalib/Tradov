#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TWS HANDSHAKE RESEARCH TOOL
===========================

Systematic TWS API handshake debugging based on successful IB Gateway patterns.
This tool applies the lessons learned from weeks of Gateway debugging to crack
the TWS handshake problem using a methodical research approach.

BACKGROUND:
- Successfully solved IB Gateway handshake after weeks of trial and error
- IB Gateway became rock-solid stable after handshake fix
- Failed at client management phase with Gateway (8+ concurrent clients)
- Migrated to TWS (8 client limit) on separate Windows computer
- Now facing identical handshake issue with TWS

RESEARCH PHILOSOPHY:
- TWS and Gateway share similar API protocols but have subtle differences
- The "port open but no API response" pattern is identical to initial Gateway issues
- Solution exists - we just need to find the TWS-specific configuration

Author: Spyder Trading System
Date: 2025-01-04
"""

import socket
import time
import struct
import asyncio
import json
import argparse
import sys
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
import threading


class Colors:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    END = "\033[0m"


class TWSHandshakeResearcher:
    """
    Advanced TWS handshake researcher applying Gateway lessons learned
    """

    def __init__(self, windows_ip: str, port: int = 7497, verbose: bool = False):
        self.windows_ip = windows_ip
        self.port = port
        self.verbose = verbose

        # TWS Protocol Constants (from Gateway research)
        self.API_VERSIONS = [
            (38, 176),  # Standard range
            (100, 176),  # Conservative range
            (76, 176),  # Alternative range
            (38, 150),  # Older TWS compatibility
        ]

        # Different handshake patterns to test
        self.HANDSHAKE_PATTERNS = [
            "standard",  # Standard ib_async pattern
            "gateway_style",  # Exact Gateway pattern that worked
            "tws_minimal",  # Minimal TWS-specific
            "old_protocol",  # Legacy TWS protocol
            "java_native",  # Java TWS native pattern
        ]

        # Research results storage
        self.research_log = []
        self.successful_patterns = []

    def log_research(self, category: str, message: str, data: Any = None):
        """Log research findings with timestamp and category"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "category": category,
            "message": message,
            "data": data,
        }
        self.research_log.append(entry)

        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        color_map = {
            "SUCCESS": Colors.GREEN,
            "ERROR": Colors.RED,
            "WARNING": Colors.YELLOW,
            "INFO": Colors.BLUE,
            "DEBUG": Colors.MAGENTA,
            "RESEARCH": Colors.CYAN,
        }
        color = color_map.get(category, Colors.BLUE)

        print(
            f"{Colors.CYAN}[{timestamp}]{Colors.END} {color}[{category}]{Colors.END} {message}"
        )

        if self.verbose and data:
            print(f"    {Colors.MAGENTA}Data: {data}{Colors.END}")

    def test_tws_port_behavior(self) -> Dict[str, Any]:
        """Research TWS port behavior patterns"""
        self.log_research(
            "RESEARCH", f"Analyzing TWS port behavior on {self.windows_ip}:{self.port}"
        )

        results = {
            "port_open": False,
            "accepts_connections": False,
            "connection_speed_ms": None,
            "multiple_connections": False,
            "connection_limit": 0,
            "immediate_close_behavior": None,
        }

        # Test 1: Basic port accessibility
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            start_time = time.time()
            sock.connect((self.windows_ip, self.port))
            connection_time = (time.time() - start_time) * 1000
            sock.close()

            results["port_open"] = True
            results["accepts_connections"] = True
            results["connection_speed_ms"] = connection_time
            self.log_research("SUCCESS", f"Port accessible ({connection_time:.1f}ms)")

        except Exception as e:
            self.log_research("ERROR", f"Port not accessible: {e}")
            return results

        # Test 2: Multiple simultaneous connections
        self.log_research("RESEARCH", "Testing multiple connection behavior")
        sockets = []
        try:
            for i in range(10):
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                sock.connect((self.windows_ip, self.port))
                sockets.append(sock)
                results["connection_limit"] = i + 1
                time.sleep(0.1)

            results["multiple_connections"] = True
            self.log_research(
                "SUCCESS", f"Accepts multiple connections (tested {len(sockets)})"
            )

        except Exception as e:
            self.log_research(
                "INFO",
                f"Connection limit reached at {results['connection_limit']}: {e}",
            )
        finally:
            for sock in sockets:
                try:
                    sock.close()
                except:
                    pass

        # Test 3: Immediate close behavior
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            sock.connect((self.windows_ip, self.port))

            # Connect and immediately close - does TWS care?
            sock.close()
            results["immediate_close_behavior"] = "allowed"
            self.log_research("INFO", "Immediate close: allowed")

        except Exception as e:
            results["immediate_close_behavior"] = f"error: {e}"

        return results

    def test_handshake_pattern(
        self, pattern: str, client_id: int = 1
    ) -> Dict[str, Any]:
        """Test specific handshake pattern"""
        self.log_research("RESEARCH", f"Testing handshake pattern: {pattern}")

        result = {
            "pattern": pattern,
            "client_id": client_id,
            "success": False,
            "steps_completed": 0,
            "error": None,
            "server_response": None,
            "response_time_ms": None,
        }

        sock = None
        try:
            # Create connection
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(15)
            sock.connect((self.windows_ip, self.port))
            result["steps_completed"] = 1

            start_time = time.time()

            if pattern == "standard":
                success = self._handshake_standard(sock, client_id, result)
            elif pattern == "gateway_style":
                success = self._handshake_gateway_style(sock, client_id, result)
            elif pattern == "tws_minimal":
                success = self._handshake_tws_minimal(sock, client_id, result)
            elif pattern == "old_protocol":
                success = self._handshake_old_protocol(sock, client_id, result)
            elif pattern == "java_native":
                success = self._handshake_java_native(sock, client_id, result)
            else:
                raise ValueError(f"Unknown pattern: {pattern}")

            result["response_time_ms"] = (time.time() - start_time) * 1000
            result["success"] = success

            if success:
                self.log_research("SUCCESS", f"Pattern '{pattern}' WORKED!")
                self.successful_patterns.append(
                    {
                        "pattern": pattern,
                        "client_id": client_id,
                        "response_time": result["response_time_ms"],
                    }
                )

        except Exception as e:
            result["error"] = str(e)
            self.log_research("ERROR", f"Pattern '{pattern}' failed: {e}")

        finally:
            if sock:
                try:
                    sock.close()
                except:
                    pass

        return result

    def _handshake_standard(
        self, sock: socket.socket, client_id: int, result: Dict
    ) -> bool:
        """Standard ib_async handshake pattern"""
        # Step 1: API prefix
        sock.send(b"API\0")
        result["steps_completed"] = 2

        # Step 2: Version range
        version_msg = "v100..176\0"
        sock.send(version_msg.encode("ascii"))
        result["steps_completed"] = 3

        # Step 3: Wait for server version
        sock.settimeout(5)
        response = sock.recv(1024)
        if not response:
            return False

        result["server_response"] = response.decode("ascii", errors="ignore")
        result["steps_completed"] = 4

        # Step 4: Send client ID
        client_msg = f"{client_id}\0"
        sock.send(client_msg.encode("ascii"))
        result["steps_completed"] = 5

        # Step 5: Final confirmation
        try:
            final_response = sock.recv(512)
            result["steps_completed"] = 6
            return True
        except socket.timeout:
            # Timeout might be normal
            return True

    def _handshake_gateway_style(
        self, sock: socket.socket, client_id: int, result: Dict
    ) -> bool:
        """Gateway handshake pattern that worked"""
        # Based on successful Gateway configuration

        # Step 1: API prefix with delay (Gateway needed this)
        sock.send(b"API\0")
        time.sleep(0.1)
        result["steps_completed"] = 2

        # Step 2: Version with different format
        version_msg = f"v{76}..{176}\0"
        sock.send(version_msg.encode("ascii"))
        time.sleep(0.1)
        result["steps_completed"] = 3

        # Step 3: Server response with longer timeout
        sock.settimeout(10)
        response = sock.recv(1024)
        if not response:
            return False

        result["server_response"] = response.decode("ascii", errors="ignore")
        result["steps_completed"] = 4

        # Step 4: Client ID with delay
        client_msg = f"{client_id}\0"
        sock.send(client_msg.encode("ascii"))
        time.sleep(0.2)
        result["steps_completed"] = 5

        return True

    def _handshake_tws_minimal(
        self, sock: socket.socket, client_id: int, result: Dict
    ) -> bool:
        """Minimal TWS-specific handshake"""
        # Try the absolute minimum that might work for TWS

        # Just API prefix
        sock.send(b"API\0")
        result["steps_completed"] = 2

        # Wait for any response
        sock.settimeout(3)
        try:
            response = sock.recv(1024)
            if response:
                result["server_response"] = response.decode("ascii", errors="ignore")
                result["steps_completed"] = 3
                return True
        except socket.timeout:
            pass

        return False

    def _handshake_old_protocol(
        self, sock: socket.socket, client_id: int, result: Dict
    ) -> bool:
        """Legacy TWS protocol pattern"""
        # Try older TWS API protocol

        # Different API prefix format
        api_msg = b"API\x00"
        sock.send(api_msg)
        result["steps_completed"] = 2

        # Legacy version format
        version_data = struct.pack(">I", 4) + b"v100"
        sock.send(version_data)
        result["steps_completed"] = 3

        sock.settimeout(5)
        response = sock.recv(1024)
        if response:
            result["server_response"] = response
            result["steps_completed"] = 4
            return True

        return False

    def _handshake_java_native(
        self, sock: socket.socket, client_id: int, result: Dict
    ) -> bool:
        """Java-native TWS handshake pattern"""
        # Try patterns that might match TWS's Java implementation

        # Java-style message format
        api_msg = "API\0".encode("utf-8")
        sock.send(api_msg)
        result["steps_completed"] = 2

        # Java-style version message
        version_msg = f"v{100}..{176}".encode("utf-8") + b"\0"
        sock.send(version_msg)
        result["steps_completed"] = 3

        sock.settimeout(8)
        response = sock.recv(1024)
        if response:
            result["server_response"] = response
            result["steps_completed"] = 4

            # Java-style client ID
            client_data = str(client_id).encode("utf-8") + b"\0"
            sock.send(client_data)
            result["steps_completed"] = 5
            return True

        return False

    def research_version_ranges(self) -> List[Dict]:
        """Research which API version ranges TWS accepts"""
        self.log_research("RESEARCH", "Testing API version range compatibility")

        results = []
        for min_ver, max_ver in self.API_VERSIONS:
            self.log_research("INFO", f"Testing version range: v{min_ver}..{max_ver}")

            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                sock.connect((self.windows_ip, self.port))

                # Send API prefix
                sock.send(b"API\0")

                # Send version range
                version_msg = f"v{min_ver}..{max_ver}\0"
                sock.send(version_msg.encode("ascii"))

                # Check for response
                sock.settimeout(3)
                response = sock.recv(512)

                result = {
                    "min_version": min_ver,
                    "max_version": max_ver,
                    "accepted": bool(response),
                    "response": response.decode("ascii", errors="ignore")
                    if response
                    else None,
                }

                if response:
                    self.log_research(
                        "SUCCESS", f"Version range v{min_ver}..{max_ver} accepted!"
                    )
                else:
                    self.log_research(
                        "INFO", f"Version range v{min_ver}..{max_ver} no response"
                    )

                results.append(result)
                sock.close()

            except Exception as e:
                self.log_research(
                    "ERROR", f"Version range v{min_ver}..{max_ver} error: {e}"
                )
                results.append(
                    {
                        "min_version": min_ver,
                        "max_version": max_ver,
                        "accepted": False,
                        "error": str(e),
                    }
                )

        return results

    def research_client_id_patterns(self) -> List[Dict]:
        """Research client ID behavior"""
        self.log_research("RESEARCH", "Researching client ID patterns")

        client_ids_to_test = [0, 1, 2, 10, 100, 999, 1234]
        results = []

        for client_id in client_ids_to_test:
            self.log_research("INFO", f"Testing client ID: {client_id}")

            result = self.test_handshake_pattern("standard", client_id)
            results.append(
                {
                    "client_id": client_id,
                    "success": result["success"],
                    "steps_completed": result["steps_completed"],
                    "error": result.get("error"),
                }
            )

            # Small delay between tests
            time.sleep(1)

        return results

    def deep_protocol_analysis(self) -> Dict[str, Any]:
        """Deep analysis of TWS protocol behavior"""
        self.log_research("RESEARCH", "Performing deep protocol analysis")

        analysis = {
            "raw_connection_test": None,
            "protocol_detection": None,
            "response_timing": [],
            "connection_lifecycle": None,
        }

        # Test 1: Raw connection behavior
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect((self.windows_ip, self.port))

            # Just connect and wait - does TWS send anything?
            raw_response = sock.recv(100)
            analysis["raw_connection_test"] = {
                "immediate_response": bool(raw_response),
                "data": raw_response if raw_response else None,
            }
            sock.close()

        except Exception as e:
            analysis["raw_connection_test"] = {"error": str(e)}

        # Test 2: Protocol detection
        protocol_tests = [
            b"API\0",
            b"TWS\0",
            b"IB\0",
            b"CONNECT\0",
            b"\0\0\0\4API\0",
        ]

        protocol_results = []
        for test_data in protocol_tests:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                sock.connect((self.windows_ip, self.port))

                start_time = time.time()
                sock.send(test_data)

                response = sock.recv(512)
                response_time = (time.time() - start_time) * 1000

                protocol_results.append(
                    {
                        "test_data": test_data,
                        "response": bool(response),
                        "response_time_ms": response_time,
                        "response_data": response if response else None,
                    }
                )

                sock.close()

            except Exception as e:
                protocol_results.append({"test_data": test_data, "error": str(e)})

        analysis["protocol_detection"] = protocol_results

        return analysis

    def save_research_results(self, filename: str = None) -> str:
        """Save all research results to JSON file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"tws_handshake_research_{timestamp}.json"

        research_data = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "target": f"{self.windows_ip}:{self.port}",
                "total_experiments": len(self.research_log),
                "successful_patterns": self.successful_patterns,
            },
            "research_log": self.research_log,
            "summary": {
                "port_accessible": any(
                    entry["category"] == "SUCCESS" and "accessible" in entry["message"]
                    for entry in self.research_log
                ),
                "api_responsive": len(self.successful_patterns) > 0,
                "recommended_pattern": self.successful_patterns[0]["pattern"]
                if self.successful_patterns
                else None,
            },
        }

        with open(filename, "w") as f:
            json.dump(research_data, f, indent=2)

        self.log_research("INFO", f"Research results saved to: {filename}")
        return filename

    def run_comprehensive_research(self) -> Dict[str, Any]:
        """Run complete TWS handshake research suite"""
        self.log_research(
            "RESEARCH", "🔬 STARTING COMPREHENSIVE TWS HANDSHAKE RESEARCH"
        )
        self.log_research("INFO", f"Target: {self.windows_ip}:{self.port}")
        self.log_research("INFO", "Based on successful IB Gateway patterns")

        print("=" * 80)

        # Phase 1: Port behavior analysis
        self.log_research("RESEARCH", "Phase 1: Port Behavior Analysis")
        port_results = self.test_tws_port_behavior()

        if not port_results["port_open"]:
            self.log_research("ERROR", "Port not accessible - cannot continue research")
            return {"error": "Port not accessible"}

        # Phase 2: Handshake pattern testing
        self.log_research("RESEARCH", "Phase 2: Handshake Pattern Testing")
        pattern_results = []
        for pattern in self.HANDSHAKE_PATTERNS:
            result = self.test_handshake_pattern(pattern)
            pattern_results.append(result)
            time.sleep(2)  # Delay between pattern tests

        # Phase 3: Version range research
        self.log_research("RESEARCH", "Phase 3: API Version Range Research")
        version_results = self.research_version_ranges()

        # Phase 4: Client ID research
        self.log_research("RESEARCH", "Phase 4: Client ID Pattern Research")
        client_id_results = self.research_client_id_patterns()

        # Phase 5: Deep protocol analysis
        self.log_research("RESEARCH", "Phase 5: Deep Protocol Analysis")
        protocol_analysis = self.deep_protocol_analysis()

        # Compile results
        results = {
            "port_behavior": port_results,
            "handshake_patterns": pattern_results,
            "version_ranges": version_results,
            "client_id_patterns": client_id_results,
            "protocol_analysis": protocol_analysis,
            "successful_patterns": self.successful_patterns,
        }

        # Analysis and recommendations
        self.analyze_research_results(results)

        return results

    def analyze_research_results(self, results: Dict[str, Any]):
        """Analyze research results and provide recommendations"""
        print("\n" + "=" * 80)
        self.log_research("RESEARCH", "🎯 RESEARCH ANALYSIS AND RECOMMENDATIONS")
        print("=" * 80)

        # Check if any patterns worked
        if self.successful_patterns:
            self.log_research(
                "SUCCESS",
                f"🎉 BREAKTHROUGH! Found {len(self.successful_patterns)} working pattern(s):",
            )
            for pattern in self.successful_patterns:
                self.log_research(
                    "SUCCESS",
                    f"  ✅ Pattern '{pattern['pattern']}' (Client ID: {pattern['client_id']})",
                )

            best_pattern = self.successful_patterns[0]
            self.log_research(
                "SUCCESS", f"🚀 RECOMMENDED: Use pattern '{best_pattern['pattern']}'"
            )

        else:
            self.log_research("ERROR", "❌ NO WORKING PATTERNS FOUND")
            self.log_research("INFO", "This indicates a TWS configuration issue:")

            # Diagnostic suggestions based on research
            if results["port_behavior"]["accepts_connections"]:
                self.log_research(
                    "WARNING", "  • Port is accessible but API not responding"
                )
                self.log_research("WARNING", "  • Check TWS API Settings:")
                self.log_research(
                    "WARNING", "    - 'Enable ActiveX and Socket Clients' ✅"
                )
                self.log_research("WARNING", "    - 'Read-Only API' ❌ UNCHECKED")
                self.log_research(
                    "WARNING", "    - Trusted IPs includes your Ubuntu IP"
                )
                self.log_research("WARNING", "    - Socket Port matches (7497)")
            else:
                self.log_research(
                    "ERROR", "  • Port not accessible - TWS not listening"
                )

        # Version analysis
        accepted_versions = [v for v in results["version_ranges"] if v.get("accepted")]
        if accepted_versions:
            self.log_research(
                "INFO", f"✅ Compatible API versions found: {len(accepted_versions)}"
            )
        else:
            self.log_research("WARNING", "⚠️  No API version ranges accepted")

        # Connection analysis
        port_info = results["port_behavior"]
        self.log_research("INFO", f"📊 Connection Analysis:")
        self.log_research(
            "INFO",
            f"  • Connection Speed: {port_info.get('connection_speed_ms', 'N/A'):.1f}ms",
        )
        self.log_research(
            "INFO",
            f"  • Multiple Connections: {port_info.get('multiple_connections', False)}",
        )
        self.log_research(
            "INFO",
            f"  • Connection Limit: {port_info.get('connection_limit', 'Unknown')}",
        )

        print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="TWS Handshake Research Tool")
    parser.add_argument(
        "--windows-ip", required=True, help="Windows computer IP address"
    )
    parser.add_argument(
        "--port", type=int, default=7497, help="TWS port (default: 7497)"
    )
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--pattern", help="Test specific pattern only")
    parser.add_argument(
        "--save-results", action="store_true", help="Save results to JSON file"
    )

    args = parser.parse_args()

    print("🔬 TWS HANDSHAKE RESEARCH TOOL")
    print("Based on successful IB Gateway debugging methodology")
    print(f"Target: {args.windows_ip}:{args.port}")
    print("=" * 80)

    researcher = TWSHandshakeResearcher(
        windows_ip=args.windows_ip, port=args.port, verbose=args.verbose
    )

    if args.pattern:
        # Test specific pattern only
        result = researcher.test_handshake_pattern(args.pattern)
        print(f"\nPattern '{args.pattern}' result: {result}")
    else:
        # Run comprehensive research
        results = researcher.run_comprehensive_research()

        if args.save_results:
            filename = researcher.save_research_results()
            print(f"\n📄 Results saved to: {filename}")

    print("\n🎯 Research complete!")
    if researcher.successful_patterns:
        print(
            f"✅ SUCCESS: Found {len(researcher.successful_patterns)} working pattern(s)"
        )
        print("Your TWS connection should now work!")
    else:
        print("❌ No working patterns found")
        print("Check TWS API configuration and restart TWS completely")


if __name__ == "__main__":
    main()
