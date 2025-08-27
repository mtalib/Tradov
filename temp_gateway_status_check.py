#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IB GATEWAY STATUS AND PORT CHECKER

SPYDER - Autonomous Options Trading System v1.0

Module: temp_gateway_status_check.py
Purpose: Check Gateway login status, port availability, and API readiness
Author: Mohamed Talib
Date Created: 2025-08-27
Last Updated: 2025-08-27 Time: 16:45:00

Module Description:
    This diagnostic checks if Gateway is logged in, which ports are actually
    being used, and whether the API is in a ready state to accept connections.
    Settings can be correct but Gateway may not be logged in or initialized.

"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import socket
import subprocess
import time
import sys
import os
from typing import Dict, Any, List, Optional
from pathlib import Path

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    import psutil
except ImportError:
    print("❌ psutil not available. Install with: pip install psutil")
    sys.exit(1)

# ==============================================================================
# CONSTANTS
# ==============================================================================
GATEWAY_PORTS = [4001, 4002, 7496, 7497, 4003, 4004]  # Common IB ports
GATEWAY_INSTALL_DIR = Path.home() / "Jts" / "ibgateway" / "1039"
LOG_PATTERNS = [
    "logged in",
    "login", 
    "connected to server",
    "api",
    "socket",
    "client",
    "error",
    "ready"
]

# ==============================================================================
# GATEWAY STATUS FUNCTIONS
# ==============================================================================

def scan_all_ports() -> Dict[int, Dict[str, Any]]:
    """
    Scan all potential IB Gateway ports.
    
    Returns:
        Port scan results with detailed information
    """
    port_results = {}
    
    print("🔍 Scanning IB Gateway ports...")
    print("-" * 40)
    
    for port in GATEWAY_PORTS:
        result = {
            'port': port,
            'open': False,
            'connectable': False,
            'response_time': None,
            'banner': None,
            'error': None
        }
        
        try:
            # Test if port is open
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            start_time = time.time()
            
            conn_result = sock.connect_ex(('127.0.0.1', port))
            
            if conn_result == 0:
                result['open'] = True
                result['connectable'] = True
                result['response_time'] = time.time() - start_time
                
                # Try to get banner/response
                try:
                    sock.settimeout(1)
                    sock.send(b'\x00\x00\x00\x01')  # Send a test byte
                    response = sock.recv(1024)
                    if response:
                        result['banner'] = response[:50].hex()  # First 50 bytes as hex
                except socket.timeout:
                    result['banner'] = "No response"
                except Exception as e:
                    result['banner'] = f"Error: {e}"
                    
                print(f"✅ Port {port}: OPEN ({result['response_time']:.3f}s)")
                if result['banner']:
                    print(f"   Response: {result['banner']}")
            else:
                result['error'] = f"Connection failed: {conn_result}"
                print(f"❌ Port {port}: CLOSED")
            
            sock.close()
            
        except Exception as e:
            result['error'] = str(e)
            print(f"❌ Port {port}: ERROR - {e}")
        
        port_results[port] = result
    
    return port_results

def check_gateway_processes_detailed() -> List[Dict[str, Any]]:
    """
    Get detailed information about Gateway processes.
    
    Returns:
        List of Gateway processes with detailed info
    """
    processes = []
    
    print("\n🔍 Gateway Process Analysis...")
    print("-" * 40)
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'status', 'memory_info', 'create_time']):
        try:
            cmdline = ' '.join(proc.info['cmdline'] or [])
            
            if ('ibgateway' in proc.info['name'].lower() or 
                'ibgateway' in cmdline.lower() or
                ('java' in proc.info['name'].lower() and 'ibgateway' in cmdline.lower())):
                
                # Get process details
                create_time = time.time() - proc.info['create_time']
                memory_mb = proc.info['memory_info'].rss / 1024 / 1024 if proc.info['memory_info'] else 0
                
                # Get network connections
                connections = []
                try:
                    p = psutil.Process(proc.info['pid'])
                    for conn in p.connections():
                        if conn.status == 'LISTEN':
                            connections.append({
                                'port': conn.laddr.port,
                                'status': conn.status,
                                'family': conn.family.name if hasattr(conn.family, 'name') else str(conn.family)
                            })
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    pass
                
                # Extract version info from command line
                version = "Unknown"
                if "fullVersion=" in cmdline:
                    version_start = cmdline.find("fullVersion=") + 12
                    version_end = cmdline.find(" ", version_start)
                    if version_end == -1:
                        version_end = len(cmdline)
                    version = cmdline[version_start:version_end]
                
                process_info = {
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'status': proc.info['status'],
                    'memory_mb': round(memory_mb, 1),
                    'uptime_minutes': round(create_time / 60, 1),
                    'version': version,
                    'connections': connections,
                    'cmdline': cmdline
                }
                
                processes.append(process_info)
                
                print(f"📊 PID {process_info['pid']}:")
                print(f"   Status: {process_info['status']}")
                print(f"   Memory: {process_info['memory_mb']} MB")
                print(f"   Uptime: {process_info['uptime_minutes']} minutes")
                print(f"   Version: {process_info['version']}")
                if connections:
                    print(f"   Listening ports: {[c['port'] for c in connections]}")
                else:
                    print(f"   ❌ No listening ports found!")
                
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    return processes

def check_gateway_logs() -> Dict[str, Any]:
    """
    Check Gateway log files for status information.
    
    Returns:
        Log analysis results
    """
    log_results = {
        'log_files_found': [],
        'recent_entries': [],
        'status_indicators': {
            'logged_in': False,
            'api_ready': False,
            'errors_found': [],
            'last_activity': None
        }
    }
    
    print(f"\n🔍 Checking Gateway logs in {GATEWAY_INSTALL_DIR}...")
    print("-" * 40)
    
    # Look for log directories
    possible_log_dirs = [
        GATEWAY_INSTALL_DIR / "logs",
        GATEWAY_INSTALL_DIR / "log",
        Path.home() / "Jts" / "logs",
        Path.home() / ".ibkr" / "logs"
    ]
    
    for log_dir in possible_log_dirs:
        if log_dir.exists():
            print(f"📁 Found log directory: {log_dir}")
            
            # Find log files
            for log_file in log_dir.glob("*.log*"):
                try:
                    stat = log_file.stat()
                    log_info = {
                        'path': str(log_file),
                        'size': stat.st_size,
                        'modified': stat.st_mtime
                    }
                    log_results['log_files_found'].append(log_info)
                    print(f"   📄 {log_file.name} ({stat.st_size} bytes)")
                    
                    # Read recent entries (last 50 lines)
                    try:
                        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                            lines = f.readlines()
                            recent_lines = lines[-50:] if len(lines) > 50 else lines
                            
                            for line in recent_lines:
                                line_lower = line.lower()
                                
                                # Check for login status
                                if any(pattern in line_lower for pattern in ['logged in', 'login successful', 'connected to server']):
                                    log_results['status_indicators']['logged_in'] = True
                                    log_results['recent_entries'].append(f"✅ LOGIN: {line.strip()}")
                                
                                # Check for API readiness
                                elif any(pattern in line_lower for pattern in ['api', 'socket client', 'client connected']):
                                    if 'error' not in line_lower:
                                        log_results['status_indicators']['api_ready'] = True
                                    log_results['recent_entries'].append(f"🔌 API: {line.strip()}")
                                
                                # Check for errors
                                elif any(pattern in line_lower for pattern in ['error', 'failed', 'exception']):
                                    log_results['status_indicators']['errors_found'].append(line.strip())
                                    log_results['recent_entries'].append(f"❌ ERROR: {line.strip()}")
                                
                                # Track last activity
                                if line.strip():
                                    log_results['status_indicators']['last_activity'] = line.strip()
                    
                    except Exception as e:
                        print(f"   ⚠️ Could not read {log_file.name}: {e}")
                
                except Exception as e:
                    print(f"   ⚠️ Could not stat {log_file}: {e}")
        else:
            print(f"📁 Log directory not found: {log_dir}")
    
    return log_results

def test_direct_socket_communication(port: int) -> Dict[str, Any]:
    """
    Test direct socket communication to see what Gateway responds with.
    
    Args:
        port: Port to test
        
    Returns:
        Socket communication results
    """
    result = {
        'port': port,
        'connected': False,
        'sent_data': False,
        'received_response': False,
        'response_data': None,
        'error': None
    }
    
    try:
        print(f"\n🧪 Testing direct socket communication on port {port}...")
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        
        # Connect
        sock.connect(('127.0.0.1', port))
        result['connected'] = True
        print("   ✅ Socket connected")
        
        # Try sending some test data (basic IB API handshake start)
        test_messages = [
            b'\x00\x00\x00\x03API',  # Basic API prefix
            b'\x00\x00\x00\x0f\x00\x00\x00\x49\x00\x00\x00\x01',  # Version request
            b'API\x00',  # Simple API marker
        ]
        
        for i, msg in enumerate(test_messages):
            try:
                sock.send(msg)
                result['sent_data'] = True
                print(f"   📤 Sent test message {i+1}")
                
                # Try to receive response
                sock.settimeout(2)
                response = sock.recv(1024)
                if response:
                    result['received_response'] = True
                    result['response_data'] = response[:100].hex()  # First 100 bytes as hex
                    print(f"   📥 Received response: {result['response_data']}")
                    break
                else:
                    print(f"   📥 No response to message {i+1}")
                    
            except socket.timeout:
                print(f"   ⏱️ Timeout waiting for response to message {i+1}")
            except Exception as e:
                print(f"   ❌ Error with message {i+1}: {e}")
        
        sock.close()
        
    except Exception as e:
        result['error'] = str(e)
        print(f"   ❌ Socket communication failed: {e}")
    
    return result

# ==============================================================================
# MAIN DIAGNOSTIC FUNCTION
# ==============================================================================

def comprehensive_gateway_status_check() -> Dict[str, Any]:
    """
    Run comprehensive Gateway status check.
    
    Returns:
        Complete status report
    """
    print("🕷️ SPYDER Gateway Status Diagnostic")
    print("🔧 Checking Gateway login status and API readiness")
    print("=" * 70)
    
    report = {
        'timestamp': time.time(),
        'port_scan': {},
        'processes': [],
        'logs': {},
        'socket_tests': {},
        'recommendations': []
    }
    
    # 1. Scan ports
    report['port_scan'] = scan_all_ports()
    
    # 2. Check processes
    report['processes'] = check_gateway_processes_detailed()
    
    # 3. Check logs
    report['logs'] = check_gateway_logs()
    
    # 4. Test socket communication on open ports
    open_ports = [port for port, info in report['port_scan'].items() if info['open']]
    for port in open_ports:
        report['socket_tests'][port] = test_direct_socket_communication(port)
    
    # 5. Generate recommendations
    print("\n" + "=" * 70)
    print("📊 DIAGNOSTIC SUMMARY")
    print("=" * 70)
    
    # Check if Gateway is logged in
    if report['logs']['status_indicators']['logged_in']:
        print("✅ Gateway appears to be logged in")
    else:
        print("❌ No evidence of Gateway login found")
        report['recommendations'].append("Check Gateway login status in GUI")
    
    # Check API readiness
    if report['logs']['status_indicators']['api_ready']:
        print("✅ API appears to be ready")
    else:
        print("❌ No evidence of API readiness found")
        report['recommendations'].append("Verify API configuration and restart Gateway")
    
    # Check listening ports
    if open_ports:
        print(f"✅ Gateway listening on ports: {open_ports}")
        if 4002 in open_ports:
            print("✅ Port 4002 (paper trading) is active")
        else:
            print("❌ Port 4002 (paper trading) not found")
            report['recommendations'].append("Check Gateway port configuration")
    else:
        print("❌ No Gateway ports found listening")
        report['recommendations'].append("Gateway may not be running or configured correctly")
    
    # Check for errors
    if report['logs']['status_indicators']['errors_found']:
        print(f"⚠️ Found {len(report['logs']['status_indicators']['errors_found'])} errors in logs")
        for error in report['logs']['status_indicators']['errors_found'][:3]:  # Show first 3
            print(f"   {error}")
        report['recommendations'].append("Check Gateway logs for error details")
    
    print(f"\n💡 RECOMMENDATIONS ({len(report['recommendations'])}):")
    for i, rec in enumerate(report['recommendations'], 1):
        print(f"   {i}. {rec}")
    
    return report

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    try:
        report = comprehensive_gateway_status_check()
        
        # Final recommendation
        print("\n" + "=" * 70)
        print("🎯 NEXT STEPS:")
        print("-" * 20)
        
        if report['port_scan'].get(4002, {}).get('open', False):
            if report['logs']['status_indicators']['logged_in']:
                print("✅ Port 4002 open AND Gateway appears logged in")
                print("🔧 Try restarting Gateway completely and test again")
                print("🔧 Or try different client IDs (1-10)")
            else:
                print("⚠️ Port 4002 open but Gateway may not be logged in")
                print("🔧 Check Gateway GUI - ensure you're logged in to IBKR")
                print("🔧 Look for 'Logged in' or 'Connected' status in Gateway")
        else:
            print("❌ Port 4002 not open")
            print("🔧 Check Gateway port configuration")
            print("🔧 Restart Gateway with correct settings")
            
    except KeyboardInterrupt:
        print("\n🛑 Diagnostic interrupted by user")
