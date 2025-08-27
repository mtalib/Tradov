#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IB GATEWAY API CONFIGURATION FIX

SPYDER - Autonomous Options Trading System v1.0

Module: temp_gateway_config_fix.py
Purpose: Diagnose and fix IB Gateway API configuration issues
Author: Mohamed Talib
Date Created: 2025-08-27
Last Updated: 2025-08-27 Time: 15:00:00

Module Description:
    This tool specifically addresses IB Gateway API configuration issues that
    cause connection timeouts. It provides step-by-step guidance to enable
    API access, configure ports, and verify Gateway settings.

"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import subprocess
import time
import os
import psutil
from typing import Dict, Any, List, Optional
from pathlib import Path
import socket
import threading

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    from ib_async import IB
    HAS_IB_ASYNC = True
except ImportError:
    print("❌ ib_async not available. Install with: pip install ib_async")
    HAS_IB_ASYNC = False

# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_HOST = "127.0.0.1"
PAPER_PORT = 4002
LIVE_PORT = 4001

# Gateway configuration files (common locations)
GATEWAY_CONFIG_PATHS = [
    Path.home() / "Jts",
    Path.home() / ".wine" / "drive_c" / "Jts",
    Path("/opt") / "ibc",
    Path("/usr/local") / "ibc",
    Path.home() / "IBJts",
    Path.home() / "Applications" / "IBJts"  # macOS
]

# ==============================================================================
# GATEWAY CONFIGURATION FUNCTIONS
# ==============================================================================

def check_port_connectivity(host: str, port: int, timeout: int = 5) -> Dict[str, Any]:
    """
    Test raw socket connectivity to Gateway port.
    
    Args:
        host: Gateway host
        port: Gateway port
        timeout: Connection timeout
        
    Returns:
        Port connectivity results
    """
    result = {
        'host': host,
        'port': port,
        'connectable': False,
        'error': None,
        'response_time': None
    }
    
    try:
        start_time = time.time()
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        
        conn_result = sock.connect_ex((host, port))
        
        if conn_result == 0:
            result['connectable'] = True
            result['response_time'] = time.time() - start_time
        else:
            result['error'] = f"Connection refused (code: {conn_result})"
            
        sock.close()
        
    except socket.timeout:
        result['error'] = "Socket timeout"
    except Exception as e:
        result['error'] = str(e)
    
    return result

def find_gateway_config_files() -> List[Dict[str, Any]]:
    """
    Find IB Gateway configuration files.
    
    Returns:
        List of found configuration files
    """
    config_files = []
    
    for base_path in GATEWAY_CONFIG_PATHS:
        if base_path.exists():
            # Look for jts.ini
            jts_ini = base_path / "jts.ini"
            if jts_ini.exists():
                try:
                    config_files.append({
                        'type': 'jts.ini',
                        'path': str(jts_ini),
                        'size': jts_ini.stat().st_size,
                        'modified': jts_ini.stat().st_mtime
                    })
                except Exception as e:
                    config_files.append({
                        'type': 'jts.ini',
                        'path': str(jts_ini),
                        'error': str(e)
                    })
            
            # Look for other config files
            for pattern in ["*.ini", "*.xml", "*.properties"]:
                for config_file in base_path.glob(pattern):
                    if config_file.name != "jts.ini":  # Already handled above
                        try:
                            config_files.append({
                                'type': config_file.suffix,
                                'path': str(config_file),
                                'name': config_file.name,
                                'size': config_file.stat().st_size,
                                'modified': config_file.stat().st_mtime
                            })
                        except Exception:
                            pass
    
    return config_files

def analyze_gateway_processes() -> Dict[str, Any]:
    """
    Analyze running Gateway processes in detail.
    
    Returns:
        Detailed process analysis
    """
    analysis = {
        'processes': [],
        'total_processes': 0,
        'memory_usage': 0,
        'listening_ports': []
    }
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'status', 'memory_info']):
        try:
            cmdline = ' '.join(proc.info['cmdline'] or [])
            
            # Check for IB Gateway/TWS
            if (('ibgateway' in proc.info['name'].lower() or 
                 'ibgateway' in cmdline.lower() or
                 ('java' in proc.info['name'].lower() and 'ibgateway' in cmdline.lower())) or
                ('tws' in proc.info['name'].lower() or 
                 ('java' in proc.info['name'].lower() and 'tws' in cmdline.lower()))):
                
                # Get memory info
                memory_mb = 0
                if proc.info['memory_info']:
                    memory_mb = proc.info['memory_info'].rss / 1024 / 1024
                
                # Get listening ports (create process object to get connections)
                listening_ports = []
                try:
                    p = psutil.Process(proc.info['pid'])
                    connections = p.connections()
                    for conn in connections:
                        if conn.status == 'LISTEN':
                            listening_ports.append(conn.laddr.port)
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    pass
                
                process_info = {
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'cmdline': cmdline,
                    'status': proc.info['status'],
                    'memory_mb': round(memory_mb, 1),
                    'listening_ports': listening_ports
                }
                
                analysis['processes'].append(process_info)
                analysis['memory_usage'] += memory_mb
                analysis['listening_ports'].extend(listening_ports)
                
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    analysis['total_processes'] = len(analysis['processes'])
    analysis['listening_ports'] = list(set(analysis['listening_ports']))  # Remove duplicates
    
    return analysis

async def quick_api_test(host: str, port: int, timeout: int = 10) -> Dict[str, Any]:
    """
    Quick API connection test with detailed error analysis.
    
    Args:
        host: Gateway host
        port: Gateway port
        timeout: Connection timeout
        
    Returns:
        API test results
    """
    result = {
        'success': False,
        'error': None,
        'error_type': 'unknown',
        'suggestions': []
    }
    
    if not HAS_IB_ASYNC:
        result['error'] = "ib_async not available"
        result['error_type'] = 'missing_library'
        result['suggestions'] = ["Install ib_async: pip install ib_async"]
        return result
    
    ib = IB()
    
    try:
        await ib.connectAsync(host, port, clientId=1, timeout=timeout)
        
        if ib.isConnected():
            result['success'] = True
            result['server_version'] = ib.serverVersion()
            ib.disconnect()
        else:
            result['error'] = "Connection failed without specific error"
            result['error_type'] = 'connection_failed'
            
    except asyncio.TimeoutError:
        result['error'] = "Connection timeout"
        result['error_type'] = 'timeout'
        result['suggestions'] = [
            "API may not be enabled in Gateway",
            "Gateway may not be fully logged in",
            "Check Gateway API configuration",
            "Verify port settings in Gateway"
        ]
        
    except ConnectionRefusedError:
        result['error'] = "Connection refused"
        result['error_type'] = 'refused'
        result['suggestions'] = [
            "Gateway may not be running",
            "Port may be incorrect",
            "Firewall may be blocking connection"
        ]
        
    except Exception as e:
        result['error'] = str(e)
        
        # Analyze error message
        error_msg = str(e).lower()
        if 'timeout' in error_msg:
            result['error_type'] = 'timeout'
            result['suggestions'] = [
                "Gateway API not enabled",
                "Gateway not fully initialized",
                "Authentication required in Gateway"
            ]
        elif 'refused' in error_msg:
            result['error_type'] = 'refused'
            result['suggestions'] = [
                "Check Gateway is running",
                "Verify correct port number",
                "Check firewall settings"
            ]
        elif 'clientid' in error_msg:
            result['error_type'] = 'client_id'
            result['suggestions'] = [
                "Try different client ID",
                "Check for existing connections"
            ]
    
    finally:
        if ib.isConnected():
            ib.disconnect()
    
    return result

# ==============================================================================
# MAIN DIAGNOSTIC CLASS
# ==============================================================================

class GatewayConfigurationDiagnostic:
    """
    IB Gateway API configuration diagnostic and fix tool.
    
    This class provides comprehensive diagnostics for IB Gateway API
    configuration issues and step-by-step guidance to resolve them.
    """
    
    def __init__(self, host: str = DEFAULT_HOST, port: int = PAPER_PORT):
        """Initialize diagnostic."""
        self.host = host
        self.port = port
    
    async def run_full_diagnostic(self) -> Dict[str, Any]:
        """
        Run complete Gateway configuration diagnostic.
        
        Returns:
            Comprehensive diagnostic report
        """
        print("🔧 IB Gateway API Configuration Diagnostic")
        print("=" * 60)
        
        report = {
            'timestamp': time.time(),
            'host': self.host,
            'port': self.port,
            'socket_test': {},
            'api_test': {},
            'process_analysis': {},
            'config_files': [],
            'recommendations': []
        }
        
        # 1. Test raw socket connectivity
        print("1️⃣ Testing socket connectivity...")
        report['socket_test'] = check_port_connectivity(self.host, self.port, 5)
        
        if report['socket_test']['connectable']:
            print(f"   ✅ Port {self.port} is reachable ({report['socket_test']['response_time']:.3f}s)")
        else:
            print(f"   ❌ Port {self.port} not reachable: {report['socket_test']['error']}")
            report['recommendations'].append("Gateway process may not be running correctly")
        
        # 2. Test API connectivity
        print("\n2️⃣ Testing API connectivity...")
        report['api_test'] = await quick_api_test(self.host, self.port, 8)
        
        if report['api_test']['success']:
            print("   ✅ API connection successful!")
            print(f"   Server version: {report['api_test']['server_version']}")
        else:
            print(f"   ❌ API connection failed: {report['api_test']['error']}")
            print(f"   Error type: {report['api_test']['error_type']}")
            if report['api_test']['suggestions']:
                for suggestion in report['api_test']['suggestions']:
                    print(f"   💡 {suggestion}")
                    report['recommendations'].append(suggestion)
        
        # 3. Analyze Gateway processes
        print("\n3️⃣ Analyzing Gateway processes...")
        report['process_analysis'] = analyze_gateway_processes()
        
        analysis = report['process_analysis']
        if analysis['total_processes'] > 0:
            print(f"   Found {analysis['total_processes']} Gateway processes")
            print(f"   Total memory usage: {analysis['memory_usage']:.1f} MB")
            print(f"   Listening on ports: {analysis['listening_ports']}")
            
            for proc in analysis['processes']:
                print(f"   - PID {proc['pid']}: {proc['name']} ({proc['memory_mb']} MB)")
                if proc['listening_ports']:
                    print(f"     Ports: {proc['listening_ports']}")
        else:
            print("   ❌ No Gateway processes found")
            report['recommendations'].append("Start IB Gateway")
        
        # 4. Find configuration files
        print("\n4️⃣ Looking for configuration files...")
        report['config_files'] = find_gateway_config_files()
        
        if report['config_files']:
            print(f"   Found {len(report['config_files'])} configuration files:")
            for config in report['config_files']:
                if 'error' not in config:
                    print(f"   - {config['type']}: {config['path']}")
                else:
                    print(f"   - {config['path']}: {config['error']}")
        else:
            print("   ⚠️ No configuration files found")
            report['recommendations'].append("Check Gateway installation directory")
        
        return report
    
    def provide_configuration_guide(self, diagnostic_report: Dict[str, Any]) -> None:
        """
        Provide step-by-step configuration guidance based on diagnostic results.
        
        Args:
            diagnostic_report: Results from diagnostic
        """
        print("\n" + "=" * 60)
        print("🛠️ GATEWAY CONFIGURATION GUIDE")
        print("=" * 60)
        
        api_test = diagnostic_report.get('api_test', {})
        socket_test = diagnostic_report.get('socket_test', {})
        
        # Determine primary issue
        if not socket_test.get('connectable', False):
            print("🚨 PRIMARY ISSUE: Gateway not responding on port")
            self._guide_port_issues()
            
        elif api_test.get('error_type') == 'timeout':
            print("🚨 PRIMARY ISSUE: API not enabled or not authenticated")
            self._guide_api_enable()
            
        elif api_test.get('error_type') == 'refused':
            print("🚨 PRIMARY ISSUE: Connection refused")
            self._guide_connection_refused()
            
        else:
            print("🚨 ISSUE: General configuration problem")
            self._guide_general_config()
        
        # Always provide general verification steps
        print("\n" + "=" * 60)
        print("✅ VERIFICATION STEPS")
        print("=" * 60)
        self._provide_verification_steps()
    
    def _guide_api_enable(self) -> None:
        """Guide user through enabling API in Gateway."""
        print("\n📋 STEPS TO ENABLE API IN IB GATEWAY:")
        print("-" * 40)
        print("1. 🖥️ Open IB Gateway interface")
        print("   - Look for Gateway window or system tray icon")
        print("   - If no interface visible, Gateway may be running headless")
        
        print("\n2. ⚙️ Configure API Settings:")
        print("   - Go to Gateway menu → Configure → API")
        print("   - OR right-click Gateway system tray icon → Configure")
        print("   - OR look for 'API' or 'Settings' in Gateway interface")
        
        print("\n3. 🔧 Enable API Access:")
        print("   ✅ Enable ActiveX and Socket Clients")
        print("   ✅ Socket port: 4002 (paper trading) or 4001 (live)")
        print("   ✅ Master API client ID: 0 (or leave blank)")
        print("   ✅ Read-Only API: ❌ (unchecked for trading)")
        print("   ✅ Download open orders on connection: ✅")
        
        print("\n4. 🔐 Authentication (if required):")
        print("   - Enter your IBKR username and password")
        print("   - Complete any 2FA if prompted")
        print("   - Wait for 'Logged in' status")
        
        print("\n5. 💾 Apply and Restart:")
        print("   - Click 'OK' or 'Apply' to save settings")
        print("   - Restart Gateway for changes to take effect")
    
    def _guide_port_issues(self) -> None:
        """Guide user through port configuration issues."""
        print("\n📋 STEPS TO FIX PORT ISSUES:")
        print("-" * 40)
        print("1. 🔍 Check Gateway Process:")
        print("   - Verify IB Gateway is actually running")
        print("   - Check system processes for 'java' or 'ibgateway'")
        
        print("\n2. 🔧 Verify Port Configuration:")
        print("   - Paper Trading: Port 4002")
        print("   - Live Trading: Port 4001")
        print("   - Check Gateway settings match your connection attempt")
        
        print("\n3. 🔥 Check Firewall:")
        print("   - Temporarily disable firewall to test")
        print("   - Add exception for IB Gateway if needed")
        print("   - Allow localhost connections on IB ports")
        
        print("\n4. 🔄 Restart Gateway:")
        print("   - Close Gateway completely")
        print("   - Wait 30 seconds")
        print("   - Start Gateway again")
        print("   - Wait for full initialization (1-2 minutes)")
    
    def _guide_connection_refused(self) -> None:
        """Guide user through connection refused issues."""
        print("\n📋 STEPS TO FIX CONNECTION REFUSED:")
        print("-" * 40)
        print("1. 🖥️ Verify Gateway is Running:")
        print("   - Check for Gateway process in task manager")
        print("   - Look for Gateway icon in system tray")
        
        print("\n2. 🔌 Check Port Binding:")
        print("   - Gateway must be listening on the correct port")
        print("   - Use 'netstat -an | grep 4002' to verify")
        
        print("\n3. 🛡️ Security Settings:")
        print("   - Check if Gateway has security restrictions")
        print("   - Verify localhost connections are allowed")
        print("   - Check for IP whitelisting in Gateway settings")
    
    def _guide_general_config(self) -> None:
        """Provide general configuration guidance."""
        print("\n📋 GENERAL CONFIGURATION CHECKLIST:")
        print("-" * 40)
        print("✅ IB Gateway is running and fully logged in")
        print("✅ API is enabled in Gateway settings")
        print("✅ Correct port configured (4002 for paper, 4001 for live)")
        print("✅ Socket clients are enabled")
        print("✅ No firewall blocking localhost connections")
        print("✅ Gateway has completed initialization")
        print("✅ Account is properly authenticated")
    
    def _provide_verification_steps(self) -> None:
        """Provide verification steps after configuration."""
        print("1. 🔍 Test socket connection:")
        print(f"   telnet {self.host} {self.port}")
        print("   (Should connect without timeout)")
        
        print("\n2. 🧪 Test with our diagnostic tool:")
        print("   python temp_gateway_config_fix.py")
        
        print("\n3. 🚀 Test with Spyder connection:")
        print("   python temp_robust_connection_test.py --quick")
        
        print("\n4. 📊 Verify in Gateway logs:")
        print("   - Check Gateway log files for API connection attempts")
        print("   - Look for authentication or configuration errors")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

async def main():
    """Main execution function."""
    print("🕷️ SPYDER Gateway Configuration Diagnostic")
    print("Based on your timeout errors, this will help fix API access")
    print()
    
    # Check if ib_async is available
    if not HAS_IB_ASYNC:
        print("❌ ib_async not available. Install it first:")
        print("   pip install ib_async")
        return
    
    # Run diagnostic for paper trading port
    diagnostic = GatewayConfigurationDiagnostic(DEFAULT_HOST, PAPER_PORT)
    report = await diagnostic.run_full_diagnostic()
    
    # Provide configuration guidance
    diagnostic.provide_configuration_guide(report)
    
    print("\n" + "=" * 60)
    print("🎯 NEXT STEPS:")
    print("-" * 20)
    print("1. Follow the configuration guide above")
    print("2. Restart IB Gateway after making changes") 
    print("3. Run this diagnostic again to verify fixes")
    print("4. Once API is working, proceed with Spyder module development")

if __name__ == "__main__":
    asyncio.run(main())
