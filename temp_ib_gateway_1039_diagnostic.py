#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Tests
Module: temp_ib_gateway_1039_diagnostic.py
Purpose: IB Gateway 10.39 specific diagnostic for API connection issues
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-09 Time: 15:00:00

Module Description:
    Specialized diagnostic for IB Gateway 10.39 where API is always enabled.
    Since v10.39 doesn't have an "Enable ActiveX" checkbox, this tests for
    other common issues: wrong trading mode, account permissions, rate limits,
    login issues, and configuration problems specific to this version.

"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import socket
import subprocess
import os
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    from ib_async import IB, util
    IB_ASYNC_AVAILABLE = True
except ImportError:
    IB_ASYNC_AVAILABLE = False
    print("⚠️  ib_async not available")

# ==============================================================================
# CONSTANTS
# ==============================================================================
MASTER_CLIENT_ID = 2
PAPER_PORT = 4002
LIVE_PORT = 4001
IB_GATEWAY_VERSION = "10.39"

# ==============================================================================
# GATEWAY 10.39 SPECIFIC CHECKS
# ==============================================================================
def check_gateway_logs():
    """Check IB Gateway logs for clues about connection issues"""
    print("\n📄 Checking IB Gateway Logs")
    print("=" * 50)
    
    # Common log locations
    log_paths = [
        Path.home() / "Jts" / "ibgateway.log",
        Path.home() / "Jts" / f"log.{datetime.now().strftime('%a')}.txt",
        Path.home() / "IBJts" / "ibgateway.log",
        Path("/tmp") / "ibgateway.log"
    ]
    
    found_logs = []
    for log_path in log_paths:
        if log_path.exists():
            found_logs.append(log_path)
            print(f"✅ Found log: {log_path}")
            
            # Read last few lines
            try:
                with open(log_path, 'r') as f:
                    lines = f.readlines()
                    recent_lines = lines[-20:] if len(lines) > 20 else lines
                    
                    # Look for API-related messages
                    api_messages = []
                    for line in recent_lines:
                        if any(keyword in line.lower() for keyword in 
                               ['api', 'client', 'connect', 'socket', 'port', 'trust', 'reject']):
                            api_messages.append(line.strip())
                    
                    if api_messages:
                        print("\n   Recent API-related log entries:")
                        for msg in api_messages[-5:]:  # Last 5 API messages
                            print(f"   → {msg[:100]}")
            except Exception as e:
                print(f"   ⚠️  Could not read log: {e}")
    
    if not found_logs:
        print("❌ No IB Gateway logs found")
        print("   Enable logging in Gateway settings for debugging")
    
    return found_logs

def check_gateway_config_files():
    """Check IB Gateway configuration files for v10.39"""
    print("\n⚙️  Checking Gateway 10.39 Configuration Files")
    print("=" * 50)
    
    config_paths = [
        Path.home() / "Jts" / "jts.ini",
        Path.home() / "Jts" / "ibg.xml",
        Path.home() / "IBJts" / "jts.ini",
    ]
    
    for config_path in config_paths:
        if config_path.exists():
            print(f"✅ Found config: {config_path}")
            
            # Check for specific settings
            try:
                with open(config_path, 'r') as f:
                    content = f.read()
                    
                    # Look for important settings
                    if 'jts.ini' in str(config_path):
                        if 'TrustedIPs' in content:
                            # Extract trusted IPs
                            for line in content.split('\n'):
                                if 'TrustedIPs' in line:
                                    print(f"   Trusted IPs config: {line.strip()}")
                        
                        if 'masterClientID' in content:
                            for line in content.split('\n'):
                                if 'masterClientID' in line:
                                    print(f"   Master Client ID config: {line.strip()}")
                        
                        if 'socketPort' in content:
                            for line in content.split('\n'):
                                if 'socketPort' in line:
                                    print(f"   Socket Port config: {line.strip()}")
                    
                    elif 'ibg.xml' in str(config_path):
                        # Check XML config
                        if 'masterClientID="2"' in content:
                            print("   ✅ Master Client ID 2 found in XML")
                        if '127.0.0.1' in content and '::1' in content:
                            print("   ✅ Both IPv4 and IPv6 IPs found in XML")
                        if 'socketPort="4002"' in content:
                            print("   ✅ Paper port 4002 configured in XML")
                            
            except Exception as e:
                print(f"   ⚠️  Could not read config: {e}")

def test_different_ports():
    """Test both paper and live ports"""
    print("\n🔌 Testing Different Ports")
    print("=" * 50)
    
    ports_status = {}
    
    for port, name in [(PAPER_PORT, "Paper"), (LIVE_PORT, "Live")]:
        print(f"\nTesting {name} Trading Port {port}:")
        
        # Test IPv4
        sock4 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock4.settimeout(3)
        try:
            result = sock4.connect_ex(('127.0.0.1', port))
            if result == 0:
                print(f"  ✅ IPv4 connection successful on port {port}")
                ports_status[f"{name}_IPv4"] = True
            else:
                print(f"  ❌ IPv4 connection failed on port {port}")
                ports_status[f"{name}_IPv4"] = False
        except:
            ports_status[f"{name}_IPv4"] = False
        finally:
            sock4.close()
        
        # Test IPv6
        sock6 = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        sock6.settimeout(3)
        try:
            result = sock6.connect_ex(('::1', port, 0, 0))
            if result == 0:
                print(f"  ✅ IPv6 connection successful on port {port}")
                ports_status[f"{name}_IPv6"] = True
            else:
                print(f"  ❌ IPv6 connection failed on port {port}")
                ports_status[f"{name}_IPv6"] = False
        except:
            ports_status[f"{name}_IPv6"] = False
        finally:
            sock6.close()
    
    return ports_status

def check_java_process_details():
    """Get detailed info about the Java process running IB Gateway"""
    print("\n☕ Java Process Analysis")
    print("=" * 50)
    
    try:
        # Find IB Gateway Java process
        result = subprocess.run(
            ['ps', 'aux'],
            capture_output=True,
            text=True
        )
        
        gateway_processes = []
        for line in result.stdout.split('\n'):
            if 'java' in line and ('ibgateway' in line.lower() or '1039' in line):
                gateway_processes.append(line)
        
        if gateway_processes:
            for proc in gateway_processes:
                parts = proc.split()
                if len(parts) > 10:
                    pid = parts[1]
                    print(f"Found IB Gateway process: PID {pid}")
                    
                    # Get more details about the process
                    try:
                        # Check open files/ports
                        lsof_result = subprocess.run(
                            ['lsof', '-p', pid, '-i', 'TCP'],
                            capture_output=True,
                            text=True
                        )
                        
                        if lsof_result.returncode == 0:
                            print("\n  Open TCP connections:")
                            for line in lsof_result.stdout.split('\n')[1:]:  # Skip header
                                if line and ('4001' in line or '4002' in line):
                                    parts = line.split()
                                    if len(parts) > 8:
                                        port_info = parts[8]
                                        state = parts[9] if len(parts) > 9 else ""
                                        print(f"    {port_info} {state}")
                    except:
                        print("  Could not get detailed port info (try with sudo)")
                    
                    # Check command line arguments
                    print("\n  Command line arguments:")
                    cmd_start = ' '.join(proc.split()[10:])[:200]
                    print(f"    {cmd_start}...")
                    
                    # Look for specific settings
                    if 'paper' in proc.lower():
                        print("    ✅ Paper trading mode detected")
                    if 'live' in proc.lower():
                        print("    ⚠️  Live trading mode detected")
                    if 'demo' in proc.lower():
                        print("    ℹ️  Demo mode detected")
        else:
            print("❌ No IB Gateway Java process found")
            
    except Exception as e:
        print(f"❌ Process analysis failed: {e}")

async def test_api_with_different_settings():
    """Test API connection with various client settings"""
    if not IB_ASYNC_AVAILABLE:
        print("⚠️  Skipping API tests - ib_async not available")
        return
    
    print("\n🧪 Testing API with Different Settings")
    print("=" * 50)
    
    test_configs = [
        {'clientId': 0, 'desc': 'Any Client (0)'},
        {'clientId': 1, 'desc': 'Order Client (1)'},
        {'clientId': 2, 'desc': 'Master Client (2)'},
        {'clientId': 999, 'desc': 'Test Client (999)'},
    ]
    
    for config in test_configs:
        print(f"\nTesting {config['desc']}:")
        ib = IB()
        
        try:
            # Try with explicit readonly setting
            await ib.connectAsync(
                '127.0.0.1',
                PAPER_PORT,
                clientId=config['clientId'],
                readonly=False,  # Explicitly set readonly to False
                timeout=5
            )
            
            print(f"  ✅ Connected with Client ID {config['clientId']}")
            accounts = ib.managedAccounts()
            print(f"  Accounts: {accounts}")
            
            ib.disconnect()
            return True  # If any connection works, API is functional
            
        except Exception as e:
            error_msg = str(e)
            if "already in use" in error_msg.lower():
                print(f"  ⚠️  Client ID {config['clientId']} already in use")
            elif "not logged in" in error_msg.lower():
                print(f"  ❌ Gateway not logged in!")
                return False
            else:
                print(f"  ❌ Failed: {error_msg[:60]}")
        
        finally:
            if ib.isConnected():
                ib.disconnect()
    
    return False

def check_environment_variables():
    """Check environment variables that might affect IB Gateway"""
    print("\n🌍 Environment Variables Check")
    print("=" * 50)
    
    important_vars = [
        'TWS_MAJOR_VRSN',
        'IB_GATEWAY_HOST',
        'IB_GATEWAY_PORT',
        'JAVA_HOME',
        'PATH'
    ]
    
    for var in important_vars:
        value = os.environ.get(var)
        if value:
            if var == 'PATH':
                # Just show if java is in PATH
                if 'java' in value.lower():
                    print(f"✅ {var}: Contains Java")
            elif var == 'TWS_MAJOR_VRSN':
                if value == '1039':
                    print(f"✅ {var}: {value} (Correct for v10.39)")
                else:
                    print(f"⚠️  {var}: {value} (Expected 1039)")
            else:
                print(f"  {var}: {value}")

# ==============================================================================
# MAIN DIAGNOSTIC
# ==============================================================================
async def main():
    """Run comprehensive IB Gateway 10.39 diagnostics"""
    print("🔬 IB Gateway 10.39 Specific Diagnostics")
    print("=" * 50)
    print(f"Version: {IB_GATEWAY_VERSION}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nNote: v10.39 has API always enabled (no checkbox needed)")
    print("Configured with:")
    print(f"  • Master Client ID: {MASTER_CLIENT_ID}")
    print(f"  • Trusted IPs: 127.0.0.1, ::1")
    
    # Run all checks
    print("\n" + "=" * 50)
    check_environment_variables()
    
    print("\n" + "=" * 50)
    check_java_process_details()
    
    print("\n" + "=" * 50)
    ports = test_different_ports()
    
    print("\n" + "=" * 50)
    check_gateway_config_files()
    
    print("\n" + "=" * 50)
    check_gateway_logs()
    
    print("\n" + "=" * 50)
    if IB_ASYNC_AVAILABLE:
        api_works = await test_api_with_different_settings()
    else:
        api_works = False
    
    # Diagnosis
    print("\n" + "=" * 60)
    print("🔍 DIAGNOSIS FOR IB GATEWAY 10.39")
    print("=" * 60)
    
    # Check which port is actually listening
    paper_works = ports.get('Paper_IPv4', False) or ports.get('Paper_IPv6', False)
    live_works = ports.get('Live_IPv4', False) or ports.get('Live_IPv6', False)
    
    if not paper_works and not live_works:
        print("""
❌ NO PORTS LISTENING

IB Gateway is not listening on any expected ports.

POSSIBLE CAUSES:
1. Gateway not running or crashed
2. Gateway still starting up (wait 30 seconds)
3. Wrong Gateway version running

SOLUTION:
1. Restart IB Gateway
2. Ensure you're running version 10.39
3. Check Gateway didn't crash during startup
""")
    elif live_works and not paper_works:
        print("""
⚠️  WRONG TRADING MODE

Gateway is listening on LIVE port (4001) not PAPER port (4002).

SOLUTION:
1. You're connected to LIVE trading account
2. Either:
   a) Switch to paper trading account in Gateway login
   b) Update your code to use port 4001 (CAREFUL - LIVE TRADING!)
   c) Login with paper trading credentials
""")
    elif paper_works and not api_works:
        print("""
❌ API NOT RESPONDING - LIKELY LOGIN OR PERMISSION ISSUE

Socket connects but API doesn't respond. For v10.39, this usually means:

MOST LIKELY CAUSES:
1. NOT LOGGED IN: Gateway running but not logged into account
2. ACCOUNT LOCKED: Too many failed login attempts
3. API PERMISSION: Account doesn't have API trading enabled
4. RATE LIMIT: Too many connection attempts - wait 1 minute

SOLUTIONS:
1. Check IB Gateway window - are you logged in?
   - If login screen showing: Enter credentials
   - If "No Trading Permission": Wrong account type

2. Check account status at IBKR website:
   - Verify API trading is enabled for your account
   - Check no security locks

3. Wait 60 seconds and try again (rate limit reset)

4. Restart Gateway with fresh login:
   - File → Exit
   - Start Gateway
   - Login with PAPER trading username (not live!)
   - Wait for "Connected" status
   - Then run tests

5. Check the Gateway window for any error dialogs
""")
    else:
        print("""
✅ Connectivity looks good!

If you still can't connect:
1. Check no other application is using the client IDs
2. Verify you're logged into Gateway
3. Try with Client ID 0 first
""")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  Diagnostics cancelled")
    except Exception as e:
        print(f"\n❌ Diagnostics failed: {e}")
        import traceback
        traceback.print_exc()