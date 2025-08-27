#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TEMPORARY CONNECTION DIAGNOSTICS AND FIX

SPYDER - Autonomous Options Trading System v1.0

Module: temp_connection_diagnostics.py
Purpose: Diagnose and fix IB Gateway connection issues  
Author: Mohamed Talib
Date Created: 2025-08-27
Last Updated: 2025-08-27 Time: 14:30:00

Module Description:
    This temporary module diagnoses IB Gateway connection issues and provides
    fixes for common problems like client ID conflicts, stale connections, and
    Gateway process management. It will help resolve the "clientId 2 already 
    in use" error and establish proper connectivity.

"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import subprocess
import time
import os
import signal
import psutil
from typing import List, Dict, Optional, Any
from pathlib import Path

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
# IB Gateway Settings
DEFAULT_HOST = "127.0.0.1"
PAPER_PORT = 4002
LIVE_PORT = 4001
CLIENT_ID_RANGE = range(1, 32)  # IB supports client IDs 1-31
CONNECTION_TIMEOUT = 60

# Process Names
GATEWAY_PROCESSES = ["ibgateway", "java"]
TWS_PROCESSES = ["tws", "java"]

# ==============================================================================
# DIAGNOSTIC FUNCTIONS
# ==============================================================================

def check_gateway_processes() -> List[Dict[str, Any]]:
    """
    Check for running IB Gateway/TWS processes.
    
    Returns:
        List of process information dictionaries
    """
    processes = []
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'status']):
        try:
            cmdline = ' '.join(proc.info['cmdline'] or [])
            
            # Check for IB Gateway
            if ('ibgateway' in proc.info['name'].lower() or 
                'ibgateway' in cmdline.lower() or
                ('java' in proc.info['name'].lower() and 'ibgateway' in cmdline.lower())):
                
                processes.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'cmdline': cmdline,
                    'status': proc.info['status'],
                    'type': 'Gateway'
                })
                
            # Check for TWS
            elif ('tws' in proc.info['name'].lower() or 
                  ('java' in proc.info['name'].lower() and 'tws' in cmdline.lower())):
                
                processes.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'cmdline': cmdline,
                    'status': proc.info['status'],
                    'type': 'TWS'
                })
                
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    return processes

def check_port_usage(port: int) -> Dict[str, Any]:
    """
    Check if a port is in use and by which process.
    
    Args:
        port: Port number to check
        
    Returns:
        Port usage information
    """
    result = {
        'port': port,
        'in_use': False,
        'process': None,
        'connections': []
    }
    
    try:
        for conn in psutil.net_connections():
            if conn.laddr.port == port:
                result['in_use'] = True
                result['connections'].append({
                    'status': conn.status,
                    'pid': conn.pid,
                    'family': conn.family.name if conn.family else None,
                    'type': conn.type.name if conn.type else None
                })
                
                if conn.pid:
                    try:
                        proc = psutil.Process(conn.pid)
                        result['process'] = {
                            'pid': conn.pid,
                            'name': proc.name(),
                            'cmdline': ' '.join(proc.cmdline())
                        }
                    except psutil.NoSuchProcess:
                        pass
                        
    except Exception as e:
        result['error'] = str(e)
    
    return result

async def test_client_id(host: str, port: int, client_id: int, timeout: int = 10) -> Dict[str, Any]:
    """
    Test connection with a specific client ID.
    
    Args:
        host: IB Gateway host
        port: IB Gateway port  
        client_id: Client ID to test
        timeout: Connection timeout
        
    Returns:
        Connection test result
    """
    result = {
        'client_id': client_id,
        'success': False,
        'error': None,
        'server_version': None,
        'connection_time': None
    }
    
    if not HAS_IB_ASYNC:
        result['error'] = "ib_async not available"
        return result
    
    ib = IB()
    
    try:
        # Attempt connection
        await ib.connectAsync(host, port, clientId=client_id, timeout=timeout)
        
        if ib.isConnected():
            result['success'] = True
            result['server_version'] = ib.serverVersion()
            result['connection_time'] = ib.reqCurrentTime()
            
            # Disconnect immediately
            ib.disconnect()
        else:
            result['error'] = "Connection failed but no exception raised"
            
    except Exception as e:
        result['error'] = str(e)
    
    finally:
        if ib.isConnected():
            ib.disconnect()
    
    return result

async def find_available_client_id(host: str, port: int, timeout: int = 10) -> Optional[int]:
    """
    Find an available client ID by testing each one.
    
    Args:
        host: IB Gateway host
        port: IB Gateway port
        timeout: Connection timeout per attempt
        
    Returns:
        Available client ID or None
    """
    print(f"🔍 Testing client IDs on {host}:{port}...")
    
    for client_id in CLIENT_ID_RANGE:
        print(f"Testing client ID {client_id}...", end=" ")
        
        result = await test_client_id(host, port, client_id, timeout)
        
        if result['success']:
            print(f"✅ Available")
            return client_id
        else:
            print(f"❌ {result['error']}")
    
    return None

def kill_gateway_processes(force: bool = False) -> Dict[str, Any]:
    """
    Kill IB Gateway/TWS processes.
    
    Args:
        force: Use SIGKILL instead of SIGTERM
        
    Returns:
        Kill operation results
    """
    result = {
        'killed_processes': [],
        'errors': []
    }
    
    processes = check_gateway_processes()
    
    for proc_info in processes:
        try:
            proc = psutil.Process(proc_info['pid'])
            
            if force:
                proc.kill()  # SIGKILL
                signal_name = "SIGKILL"
            else:
                proc.terminate()  # SIGTERM
                signal_name = "SIGTERM"
            
            # Wait for process to die
            try:
                proc.wait(timeout=10)
                result['killed_processes'].append({
                    'pid': proc_info['pid'],
                    'name': proc_info['name'],
                    'signal': signal_name,
                    'success': True
                })
            except psutil.TimeoutExpired:
                if not force:
                    # Try force kill
                    proc.kill()
                    proc.wait(timeout=5)
                    result['killed_processes'].append({
                        'pid': proc_info['pid'],
                        'name': proc_info['name'],
                        'signal': "SIGKILL (after SIGTERM timeout)",
                        'success': True
                    })
                else:
                    result['errors'].append(f"Failed to kill PID {proc_info['pid']} with {signal_name}")
                    
        except psutil.NoSuchProcess:
            result['killed_processes'].append({
                'pid': proc_info['pid'],
                'name': proc_info['name'],
                'signal': "Already dead",
                'success': True
            })
        except Exception as e:
            result['errors'].append(f"Error killing PID {proc_info['pid']}: {str(e)}")
    
    return result

# ==============================================================================
# MAIN DIAGNOSTIC CLASS
# ==============================================================================

class IBConnectionDiagnostics:
    """
    Comprehensive IB Gateway connection diagnostics and fixes.
    
    This class provides methods to diagnose connection issues, clean up
    stale connections, find available client IDs, and establish proper
    connectivity with IB Gateway.
    """
    
    def __init__(self, host: str = DEFAULT_HOST, port: int = PAPER_PORT):
        """Initialize diagnostics."""
        self.host = host
        self.port = port
        self.available_client_id = None
        
    def run_full_diagnostics(self) -> Dict[str, Any]:
        """
        Run comprehensive connection diagnostics.
        
        Returns:
            Complete diagnostic report
        """
        print("🔧 Running IB Gateway Connection Diagnostics...")
        print("=" * 60)
        
        report = {
            'timestamp': time.time(),
            'host': self.host,
            'port': self.port,
            'gateway_processes': [],
            'port_usage': {},
            'client_id_tests': [],
            'recommendations': []
        }
        
        # 1. Check for running processes
        print("1️⃣ Checking IB Gateway/TWS processes...")
        report['gateway_processes'] = check_gateway_processes()
        
        if report['gateway_processes']:
            print(f"   Found {len(report['gateway_processes'])} IB processes:")
            for proc in report['gateway_processes']:
                print(f"   - PID {proc['pid']}: {proc['name']} ({proc['type']})")
        else:
            print("   ❌ No IB Gateway/TWS processes found")
            report['recommendations'].append("Start IB Gateway before connecting")
        
        # 2. Check port usage
        print(f"\n2️⃣ Checking port {self.port} usage...")
        report['port_usage'] = check_port_usage(self.port)
        
        if report['port_usage']['in_use']:
            print(f"   ✅ Port {self.port} is in use")
            if report['port_usage']['process']:
                proc = report['port_usage']['process']
                print(f"   Process: PID {proc['pid']}, {proc['name']}")
        else:
            print(f"   ❌ Port {self.port} not in use")
            report['recommendations'].append(f"Start IB Gateway on port {self.port}")
        
        return report
    
    async def test_all_client_ids(self) -> Dict[str, Any]:
        """
        Test all client IDs to find available ones.
        
        Returns:
            Client ID test results
        """
        print(f"\n3️⃣ Testing client IDs on {self.host}:{self.port}...")
        
        results = {
            'available_ids': [],
            'unavailable_ids': [],
            'errors': {}
        }
        
        for client_id in CLIENT_ID_RANGE:
            print(f"   Testing client ID {client_id}...", end=" ")
            
            test_result = await test_client_id(self.host, self.port, client_id, 5)
            
            if test_result['success']:
                print("✅ Available")
                results['available_ids'].append(client_id)
                if not self.available_client_id:
                    self.available_client_id = client_id
            else:
                print(f"❌ {test_result['error']}")
                results['unavailable_ids'].append(client_id)
                results['errors'][client_id] = test_result['error']
        
        return results
    
    def clean_connections(self, force: bool = False) -> Dict[str, Any]:
        """
        Clean up stale IB connections.
        
        Args:
            force: Force kill processes
            
        Returns:
            Cleanup results
        """
        print(f"\n4️⃣ Cleaning up stale connections (force={force})...")
        
        result = kill_gateway_processes(force)
        
        if result['killed_processes']:
            print(f"   Killed {len(result['killed_processes'])} processes")
            for proc in result['killed_processes']:
                print(f"   - PID {proc['pid']}: {proc['name']} ({proc['signal']})")
        
        if result['errors']:
            print(f"   ❌ {len(result['errors'])} errors:")
            for error in result['errors']:
                print(f"   - {error}")
        
        # Wait for cleanup
        print("   Waiting 3 seconds for cleanup...")
        time.sleep(3)
        
        return result
    
    async def fix_connection_issues(self, auto_clean: bool = True) -> Dict[str, Any]:
        """
        Automatically fix common connection issues.
        
        Args:
            auto_clean: Automatically clean stale connections
            
        Returns:
            Fix results and recommendations
        """
        print("\n🔧 ATTEMPTING AUTOMATIC FIXES...")
        print("=" * 60)
        
        fix_results = {
            'actions_taken': [],
            'available_client_id': None,
            'connection_ready': False,
            'recommendations': []
        }
        
        # Step 1: Clean stale connections if requested
        if auto_clean:
            processes = check_gateway_processes()
            if processes:
                print("Cleaning stale IB processes...")
                clean_result = self.clean_connections(force=False)
                fix_results['actions_taken'].append(f"Cleaned {len(clean_result['killed_processes'])} processes")
        
        # Step 2: Find available client ID
        print("Finding available client ID...")
        available_client_id = await find_available_client_id(self.host, self.port, 5)
        
        if available_client_id:
            fix_results['available_client_id'] = available_client_id
            fix_results['connection_ready'] = True
            fix_results['actions_taken'].append(f"Found available client ID: {available_client_id}")
            print(f"✅ Ready to connect with client ID {available_client_id}")
        else:
            fix_results['recommendations'].extend([
                "No available client IDs found",
                "Check if IB Gateway is running",
                f"Verify Gateway is listening on port {self.port}",
                "Try restarting IB Gateway"
            ])
            print("❌ No available client IDs found")
        
        return fix_results

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

async def main():
    """Main diagnostic routine."""
    print("🕷️ SPYDER IB Gateway Connection Diagnostics")
    print("=" * 60)
    
    # Check environment
    if not HAS_IB_ASYNC:
        print("❌ ib_async not available. Please install:")
        print("   pip install ib_async")
        return
    
    # Initialize diagnostics
    diagnostics = IBConnectionDiagnostics()
    
    # Run diagnostics
    report = diagnostics.run_full_diagnostics()
    
    # Test client IDs if Gateway is running
    port_usage = report['port_usage']
    if port_usage['in_use']:
        client_results = await diagnostics.test_all_client_ids()
        
        # Attempt automatic fix
        print("\n" + "=" * 60)
        fix_results = await diagnostics.fix_connection_issues(auto_clean=True)
        
        # Provide final recommendations
        print("\n🎯 FINAL RECOMMENDATIONS:")
        print("-" * 30)
        
        if fix_results['connection_ready']:
            client_id = fix_results['available_client_id']
            print(f"✅ Use client ID {client_id} for your connection")
            print("\n📝 Updated test connection code:")
            print(f"""
from ib_async import IB
import asyncio

async def test_connection():
    ib = IB()
    try:
        await ib.connectAsync('127.0.0.1', {diagnostics.port}, clientId={client_id}, timeout=60)
        print(f"Connected! Server version: {{ib.serverVersion()}}")
        print(f"Connection time: {{ib.reqCurrentTime()}}")
        ib.disconnect()
        print("Disconnected successfully")
    except Exception as e:
        print(f"Connection failed: {{e}}")

asyncio.run(test_connection())
""")
        else:
            for rec in fix_results['recommendations']:
                print(f"❌ {rec}")
            
            print("\n🔧 Manual steps to try:")
            print("1. Start IB Gateway manually")
            print("2. Check Gateway configuration")  
            print("3. Verify API is enabled in Gateway settings")
            print(f"4. Confirm Gateway is listening on port {diagnostics.port}")
    
    else:
        print(f"\n❌ IB Gateway not responding on port {diagnostics.port}")
        print("🔧 Start IB Gateway first, then run this diagnostic again")

if __name__ == "__main__":
    asyncio.run(main())
