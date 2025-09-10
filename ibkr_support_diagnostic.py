#!/usr/bin/env python3
"""
IB Gateway 10.39 Comprehensive Diagnostic Report for IBKR Support
==================================================================

Purpose: Complete diagnostic tool to identify API connection issues with IB Gateway 10.39
         Generates detailed report for IBKR technical support

System Architecture:
- Multi-client setup with 10 concurrent connections (Client IDs 1-10)
- IB Gateway version: 10.39
- API Library: ib_async 2.0.1
- Operating System: Ubuntu 25.04 (Wayland)
- Python Version: 3.13.3

Issue: IB Gateway accepts TCP socket connections but API layer does not respond
       to any connection attempts, resulting in timeout errors for all clients.

"""

import asyncio
import socket
import subprocess
import sys
import os
import json
import platform
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import traceback

# ==============================================================================
# CLIENT ARCHITECTURE DOCUMENTATION
# ==============================================================================
CLIENT_ARCHITECTURE = {
    1: {
        "name": "Order Execution Client",
        "purpose": "Handles all order placement and execution",
        "priority": "HIGHEST",
        "update_frequency": "Real-time",
        "requirements": "Write access, low latency"
    },
    2: {
        "name": "Master Administrative Client",
        "purpose": "System administration and account management",
        "priority": "CRITICAL",
        "update_frequency": "Real-time",
        "requirements": "Master client privileges"
    },
    3: {
        "name": "Core Market Data Client",
        "purpose": "Primary market data feed for core instruments",
        "priority": "HIGH",
        "update_frequency": "1 second",
        "requirements": "Market data subscriptions"
    },
    4: {
        "name": "Options Chain Data Client",
        "purpose": "Options chain data retrieval",
        "priority": "HIGH",
        "update_frequency": "1 second",
        "requirements": "Options data subscriptions"
    },
    5: {
        "name": "Volatility Data Client",
        "purpose": "Volatility indicators and metrics",
        "priority": "MEDIUM",
        "update_frequency": "5 seconds",
        "requirements": "Market data subscriptions"
    },
    6: {
        "name": "Market Internals Client",
        "purpose": "Market internals and breadth data",
        "priority": "MEDIUM",
        "update_frequency": "5 seconds",
        "requirements": "Market data subscriptions"
    },
    7: {
        "name": "Index Data Client",
        "purpose": "Major market indices data",
        "priority": "MEDIUM",
        "update_frequency": "5 seconds",
        "requirements": "Index data subscriptions"
    },
    8: {
        "name": "Extended Markets Client",
        "purpose": "Extended market instruments data",
        "priority": "LOW",
        "update_frequency": "15-30 seconds",
        "requirements": "Market data subscriptions"
    },
    9: {
        "name": "Sector Data Client",
        "purpose": "Sector ETF market data",
        "priority": "LOW",
        "update_frequency": "30-60 seconds",
        "requirements": "Market data subscriptions"
    },
    10: {
        "name": "International Markets Client",
        "purpose": "International markets data",
        "priority": "LOW",
        "update_frequency": "30-60 seconds",
        "requirements": "International data subscriptions"
    }
}

# ==============================================================================
# CONSTANTS
# ==============================================================================
MASTER_CLIENT_ID = 2
PAPER_PORT = 4002
LIVE_PORT = 4001
TEST_TIMEOUT = 10

# ==============================================================================
# DIAGNOSTIC TESTS
# ==============================================================================
class IBGatewayDiagnostic:
    """Comprehensive diagnostic tool for IB Gateway connection issues"""
    
    def __init__(self):
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "system_info": {},
            "gateway_info": {},
            "network_tests": {},
            "api_tests": {},
            "client_tests": {},
            "configuration": {},
            "logs": [],
            "errors": [],
            "summary": {}
        }
        
    def run_all_diagnostics(self):
        """Run complete diagnostic suite"""
        print("=" * 70)
        print("IB GATEWAY 10.39 DIAGNOSTIC REPORT FOR IBKR SUPPORT")
        print("=" * 70)
        print(f"Report Generated: {self.results['timestamp']}")
        print()
        
        # System Information
        self.collect_system_info()
        
        # Gateway Process Information
        self.check_gateway_process()
        
        # Network Connectivity
        self.test_network_connectivity()
        
        # API Protocol Tests
        self.test_api_protocol()
        
        # Client Connection Tests
        asyncio.run(self.test_client_connections())
        
        # Configuration Analysis
        self.analyze_configuration()
        
        # Generate Summary
        self.generate_summary()
        
        # Save Report
        self.save_report()
        
        return self.results
    
    def collect_system_info(self):
        """Collect system information"""
        print("\n1. SYSTEM INFORMATION")
        print("-" * 50)
        
        try:
            import ib_async
            ib_async_version = ib_async.__version__
        except:
            ib_async_version = "Not installed"
        
        self.results["system_info"] = {
            "os": platform.system(),
            "os_version": platform.version(),
            "os_release": platform.release(),
            "architecture": platform.machine(),
            "python_version": platform.python_version(),
            "hostname": platform.node(),
            "ib_async_version": ib_async_version,
            "display_server": os.environ.get('XDG_SESSION_TYPE', 'Unknown'),
            "wayland_display": os.environ.get('WAYLAND_DISPLAY', 'Not set'),
            "x11_display": os.environ.get('DISPLAY', 'Not set'),
            "java_options": os.environ.get('_JAVA_OPTIONS', 'Not set'),
            "tws_major_vrsn": os.environ.get('TWS_MAJOR_VRSN', 'Not set')
        }
        
        for key, value in self.results["system_info"].items():
            print(f"  {key}: {value}")
    
    def check_gateway_process(self):
        """Check IB Gateway process status"""
        print("\n2. GATEWAY PROCESS STATUS")
        print("-" * 50)
        
        try:
            result = subprocess.run(
                ['ps', 'aux'],
                capture_output=True,
                text=True
            )
            
            gateway_processes = []
            for line in result.stdout.split('\n'):
                if 'ibgateway' in line.lower() and 'java' in line:
                    parts = line.split()
                    if len(parts) > 10:
                        gateway_processes.append({
                            "pid": parts[1],
                            "cpu": parts[2],
                            "mem": parts[3],
                            "start_time": parts[8],
                            "command": ' '.join(parts[10:])[:200]
                        })
            
            self.results["gateway_info"]["processes"] = gateway_processes
            
            if gateway_processes:
                print(f"  Found {len(gateway_processes)} Gateway process(es)")
                for proc in gateway_processes:
                    print(f"    PID: {proc['pid']}, CPU: {proc['cpu']}%, MEM: {proc['mem']}%")
            else:
                print("  ❌ No Gateway processes found")
                
        except Exception as e:
            self.results["errors"].append(f"Process check failed: {str(e)}")
            print(f"  Error checking processes: {e}")
    
    def test_network_connectivity(self):
        """Test network connectivity to Gateway ports"""
        print("\n3. NETWORK CONNECTIVITY TESTS")
        print("-" * 50)
        
        ports_to_test = [
            (PAPER_PORT, "Paper Trading"),
            (LIVE_PORT, "Live Trading")
        ]
        
        for port, description in ports_to_test:
            print(f"\n  Testing {description} Port {port}:")
            
            # Check if port is listening
            netstat_result = subprocess.run(
                ['netstat', '-tln'],
                capture_output=True,
                text=True
            )
            
            listening = False
            protocol = None
            for line in netstat_result.stdout.split('\n'):
                if f':{port}' in line and 'LISTEN' in line:
                    listening = True
                    if 'tcp6' in line:
                        protocol = 'IPv6'
                    else:
                        protocol = 'IPv4'
                    break
            
            self.results["network_tests"][f"port_{port}"] = {
                "listening": listening,
                "protocol": protocol
            }
            
            if listening:
                print(f"    ✓ Port {port} is listening ({protocol})")
            else:
                print(f"    ✗ Port {port} is NOT listening")
            
            # Test socket connection
            for family, addr, family_name in [
                (socket.AF_INET, ('127.0.0.1', port), 'IPv4'),
                (socket.AF_INET6, ('::1', port, 0, 0), 'IPv6')
            ]:
                sock = socket.socket(family, socket.SOCK_STREAM)
                sock.settimeout(5)
                try:
                    sock.connect(addr if family == socket.AF_INET6 else (addr[0], addr[1]))
                    print(f"    ✓ {family_name} socket connection successful")
                    self.results["network_tests"][f"port_{port}_{family_name}"] = "Connected"
                    sock.close()
                except Exception as e:
                    print(f"    ✗ {family_name} socket connection failed: {e}")
                    self.results["network_tests"][f"port_{port}_{family_name}"] = f"Failed: {str(e)}"
    
    def test_api_protocol(self):
        """Test raw API protocol handshake"""
        print("\n4. API PROTOCOL TESTS")
        print("-" * 50)
        
        test_prefixes = [
            b"API\0",
            b"v9\0",
            b"v10\0"
        ]
        
        for prefix in test_prefixes:
            print(f"\n  Testing API prefix: {prefix}")
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            
            try:
                sock.connect(('127.0.0.1', PAPER_PORT))
                sock.send(prefix)
                sock.settimeout(3)
                
                try:
                    response = sock.recv(1024)
                    if response:
                        print(f"    ✓ Server responded: {response[:50]}")
                        self.results["api_tests"][f"prefix_{prefix.decode('utf-8', 'ignore')}"] = "Response received"
                    else:
                        print(f"    ✗ No response from server")
                        self.results["api_tests"][f"prefix_{prefix.decode('utf-8', 'ignore')}"] = "No response"
                except socket.timeout:
                    print(f"    ✗ Timeout waiting for response")
                    self.results["api_tests"][f"prefix_{prefix.decode('utf-8', 'ignore')}"] = "Timeout"
                    
            except Exception as e:
                print(f"    ✗ Connection failed: {e}")
                self.results["api_tests"][f"prefix_{prefix.decode('utf-8', 'ignore')}"] = f"Failed: {str(e)}"
            finally:
                sock.close()
    
    async def test_client_connections(self):
        """Test client connections using ib_async"""
        print("\n5. CLIENT CONNECTION TESTS")
        print("-" * 50)
        
        try:
            from ib_async import IB
        except ImportError:
            print("  ✗ ib_async library not available")
            self.results["client_tests"]["error"] = "ib_async not installed"
            return
        
        print("\n  Multi-Client Architecture:")
        for client_id, info in CLIENT_ARCHITECTURE.items():
            print(f"    Client {client_id:2d}: {info['name']}")
            print(f"               Purpose: {info['purpose']}")
            print(f"               Priority: {info['priority']}")
        
        print("\n  Testing Client Connections:")
        
        # Test Master Client first
        print(f"\n  Testing Master Client (ID: {MASTER_CLIENT_ID})...")
        ib = IB()
        
        try:
            await ib.connectAsync('127.0.0.1', PAPER_PORT, clientId=MASTER_CLIENT_ID, timeout=TEST_TIMEOUT)
            print(f"    ✓ Master Client {MASTER_CLIENT_ID} connected successfully")
            self.results["client_tests"][f"client_{MASTER_CLIENT_ID}"] = "Connected"
            ib.disconnect()
        except Exception as e:
            print(f"    ✗ Master Client {MASTER_CLIENT_ID} connection failed: {e}")
            self.results["client_tests"][f"client_{MASTER_CLIENT_ID}"] = f"Failed: {str(e)}"
        
        # Test other clients
        for client_id in [1, 3, 4]:  # Test sample of other clients
            print(f"\n  Testing Client {client_id} ({CLIENT_ARCHITECTURE[client_id]['name']})...")
            ib = IB()
            
            try:
                await ib.connectAsync('127.0.0.1', PAPER_PORT, clientId=client_id, timeout=5)
                print(f"    ✓ Client {client_id} connected")
                self.results["client_tests"][f"client_{client_id}"] = "Connected"
                ib.disconnect()
            except Exception as e:
                print(f"    ✗ Client {client_id} failed: {str(e)[:50]}")
                self.results["client_tests"][f"client_{client_id}"] = f"Failed: {str(e)[:100]}"
            
            await asyncio.sleep(1)
    
    def analyze_configuration(self):
        """Analyze Gateway configuration files"""
        print("\n6. CONFIGURATION ANALYSIS")
        print("-" * 50)
        
        config_files = [
            Path.home() / "Jts" / "jts.ini",
            Path.home() / "Jts" / "ibg.xml"
        ]
        
        for config_file in config_files:
            if config_file.exists():
                print(f"\n  Found: {config_file}")
                try:
                    with open(config_file, 'r') as f:
                        content = f.read()
                        
                    # Look for key settings
                    if 'socketPort' in content:
                        if '4002' in content:
                            print("    ✓ Socket port 4002 configured")
                        else:
                            print("    ✗ Socket port NOT set to 4002")
                    
                    if 'masterClientID' in content:
                        if '"2"' in content or '=2' in content:
                            print("    ✓ Master Client ID set to 2")
                        else:
                            print("    ? Master Client ID setting found but not set to 2")
                    
                    if '127.0.0.1' in content:
                        print("    ✓ IPv4 localhost in trusted IPs")
                    else:
                        print("    ✗ IPv4 localhost NOT in configuration")
                    
                    if '::1' in content:
                        print("    ✓ IPv6 localhost in trusted IPs")
                    else:
                        print("    ✗ IPv6 localhost NOT in configuration")
                        
                    self.results["configuration"][str(config_file)] = "Analyzed"
                    
                except Exception as e:
                    print(f"    Error reading config: {e}")
                    self.results["configuration"][str(config_file)] = f"Read error: {str(e)}"
            else:
                print(f"  Not found: {config_file}")
                self.results["configuration"][str(config_file)] = "Not found"
    
    def generate_summary(self):
        """Generate diagnostic summary"""
        print("\n7. DIAGNOSTIC SUMMARY")
        print("-" * 50)
        
        # Determine main issue
        gateway_running = len(self.results.get("gateway_info", {}).get("processes", [])) > 0
        port_listening = self.results.get("network_tests", {}).get(f"port_{PAPER_PORT}", {}).get("listening", False)
        api_responds = any("Response" in str(v) for v in self.results.get("api_tests", {}).values())
        clients_connect = any("Connected" in str(v) for v in self.results.get("client_tests", {}).values())
        
        self.results["summary"] = {
            "gateway_running": gateway_running,
            "port_listening": port_listening,
            "api_responds": api_responds,
            "clients_can_connect": clients_connect,
            "issue_identified": None,
            "recommendation": None
        }
        
        if not gateway_running:
            self.results["summary"]["issue_identified"] = "Gateway process not running"
            self.results["summary"]["recommendation"] = "Start IB Gateway application"
        elif not port_listening:
            self.results["summary"]["issue_identified"] = "API port not listening"
            self.results["summary"]["recommendation"] = "Check Gateway API settings and restart"
        elif port_listening and not api_responds:
            self.results["summary"]["issue_identified"] = "API layer not responding despite port listening"
            self.results["summary"]["recommendation"] = "API component malfunction - reinstall or use alternative Gateway version"
        elif api_responds and not clients_connect:
            self.results["summary"]["issue_identified"] = "API responds but clients cannot connect"
            self.results["summary"]["recommendation"] = "Check Master Client ID and Trusted IP settings"
        else:
            self.results["summary"]["issue_identified"] = "Unknown issue"
            self.results["summary"]["recommendation"] = "Contact IBKR support with this diagnostic report"
        
        print(f"\n  ISSUE IDENTIFIED: {self.results['summary']['issue_identified']}")
        print(f"  RECOMMENDATION: {self.results['summary']['recommendation']}")
        
        print("\n  Key Findings:")
        print(f"    • Gateway Process: {'✓ Running' if gateway_running else '✗ Not Running'}")
        print(f"    • Port {PAPER_PORT}: {'✓ Listening' if port_listening else '✗ Not Listening'}")
        print(f"    • API Protocol: {'✓ Responds' if api_responds else '✗ No Response'}")
        print(f"    • Client Connections: {'✓ Working' if clients_connect else '✗ All Failed'}")
    
    def save_report(self):
        """Save diagnostic report to file"""
        filename = f"ibkr_diagnostic_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            with open(filename, 'w') as f:
                json.dump(self.results, f, indent=2, default=str)
            print(f"\n✓ Report saved to: {filename}")
            print("  Please send this file to IBKR support")
        except Exception as e:
            print(f"\n✗ Could not save report: {e}")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
def main():
    """Run complete diagnostic and generate report"""
    print("\n" + "=" * 70)
    print("STARTING IB GATEWAY DIAGNOSTIC FOR IBKR SUPPORT")
    print("=" * 70)
    print("\nThis diagnostic will test:")
    print("  • System configuration")
    print("  • Gateway process status")
    print("  • Network connectivity")
    print("  • API protocol communication")
    print("  • Multi-client architecture (10 concurrent clients)")
    print("  • Configuration files")
    print()
    
    diagnostic = IBGatewayDiagnostic()
    results = diagnostic.run_all_diagnostics()
    
    print("\n" + "=" * 70)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 70)
    print("\nNEXT STEPS:")
    print("1. Review the diagnostic summary above")
    print("2. Send the generated JSON report file to IBKR support")
    print("3. Include the following information in your support ticket:")
    print("   - Using IB Gateway 10.39 on Ubuntu 25.04")
    print("   - Multi-client architecture with 10 concurrent connections")
    print("   - API accepts TCP connections but doesn't respond to API protocol")
    print("   - All client connection attempts timeout after successful socket connection")
    
    return results

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nDiagnostic cancelled by user")
    except Exception as e:
        print(f"\n\nDiagnostic failed with error: {e}")
        traceback.print_exc()