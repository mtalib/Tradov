#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Tests
Module: temp_ib_gateway_startup_check.py
Purpose: IB Gateway startup verification with correct Master Client ID
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-09 Time: 12:00:00

Module Description:
    Step-by-step IB Gateway startup verification script specifically configured
    for the Spyder trading system. Uses Master Client ID = 2 as configured in
    the IB Gateway API settings. Provides comprehensive checks for Java, IB Gateway
    installation, running processes, API ports, and connection testing.

"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import subprocess
import time
import socket
import sys
from typing import Callable, Any, List, Optional, Tuple
from pathlib import Path

# ==============================================================================
# CONSTANTS
# ==============================================================================
MASTER_CLIENT_ID = 2  # Master Client ID for Spyder system
PAPER_TRADING_PORT = 4002
LIVE_TRADING_PORT = 4001
CONNECTION_TIMEOUT = 15  # seconds
DEFAULT_PORTS = [LIVE_TRADING_PORT, PAPER_TRADING_PORT]

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================
def check_step(step_num: int, description: str, check_func: Callable) -> bool:
    """
    Execute a verification step and report results.
    
    Args:
        step_num: Step number in the verification sequence
        description: Human-readable description of the step
        check_func: Function to execute for this step
        
    Returns:
        True if step passed, False otherwise
    """
    print(f"\n🔍 Step {step_num}: {description}")
    print("-" * 50)
    
    try:
        result = check_func()
        if result:
            print(f"✅ Step {step_num} PASSED")
            return True
        else:
            print(f"❌ Step {step_num} FAILED")
            return False
    except Exception as e:
        print(f"❌ Step {step_num} ERROR: {e}")
        return False

# ==============================================================================
# VERIFICATION STEPS
# ==============================================================================
def step1_check_java() -> bool:
    """
    Verify Java installation and version.
    
    Returns:
        True if Java is properly installed, False otherwise
    """
    try:
        result = subprocess.run(
            ['java', '-version'], 
            capture_output=True, 
            text=True, 
            timeout=10
        )
        
        if result.returncode == 0:
            version_line = result.stderr.split('\n')[0]
            print(f"Java found: {version_line}")
            
            # Check for minimum Java version (11+)
            if 'version "1.8' in result.stderr:
                print("⚠️  Java 8 detected. Consider upgrading to Java 11+ for better performance")
            
            return True
        else:
            print("Java not found or not working")
            print("Install Java: sudo apt update && sudo apt install openjdk-11-jdk")
            return False
            
    except subprocess.TimeoutExpired:
        print("Java check timed out")
        return False
    except FileNotFoundError:
        print("Java command not found in PATH")
        print("Install Java: sudo apt update && sudo apt install openjdk-11-jdk")
        return False
    except Exception as e:
        print(f"Java check failed: {e}")
        return False

def step2_find_ib_gateway() -> bool:
    """
    Locate IB Gateway installation in common directories.
    
    Returns:
        True if IB Gateway installation found, False otherwise
    """
    common_paths = [
        Path.home() / "IBJts" / "ibgateway",
        Path("/opt/IBJts/ibgateway"),
        Path.home() / "Jts" / "ibgateway",
        Path.home() / "IB" / "ibgateway",
        Path("/usr/local/IBJts/ibgateway")
    ]
    
    found_paths = []
    for path in common_paths:
        if path.exists():
            print(f"IB Gateway found at: {path}")
            found_paths.append(path)
            
            # Check for specific version 10.39
            version_path = path / "1039"
            if version_path.exists():
                print(f"✅ Version 10.39 found at: {version_path}")
    
    if found_paths:
        return True
    
    print("IB Gateway not found in common locations")
    print("Download from: https://www.interactivebrokers.com/en/index.php?f=16040")
    print("Or check if running in Docker container: gnzsnz/ib-gateway-docker:latest")
    return False

def step3_check_gateway_running() -> bool:
    """
    Check if IB Gateway processes are running.
    
    Returns:
        True if Gateway processes found, False otherwise
    """
    try:
        # Check for Java processes with gateway-related keywords
        result = subprocess.run(
            ['pgrep', '-f', 'java.*gateway|java.*ibgateway|java.*tws|java.*1039'], 
            capture_output=True, 
            text=True
        )
        
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            print(f"Found {len(pids)} IB Gateway Java process(es): {', '.join(pids)}")
            
            # Try to get more details about the processes
            for pid in pids[:3]:  # Check first 3 processes
                try:
                    cmd_result = subprocess.run(
                        ['ps', '-p', pid, '-o', 'cmd', '--no-headers'],
                        capture_output=True,
                        text=True
                    )
                    if cmd_result.returncode == 0:
                        cmd = cmd_result.stdout.strip()[:100]  # First 100 chars
                        print(f"  PID {pid}: {cmd}...")
                except:
                    pass
            
            return True
        else:
            print("No IB Gateway processes running")
            print("Start IB Gateway manually or check Docker container status")
            print("For Docker: docker ps | grep ib-gateway")
            return False
            
    except FileNotFoundError:
        print("pgrep command not found, trying alternative method...")
        
        # Alternative using ps
        try:
            result = subprocess.run(
                ['ps', 'aux'],
                capture_output=True,
                text=True
            )
            
            gateway_found = False
            for line in result.stdout.split('\n'):
                if 'java' in line and ('gateway' in line.lower() or 'tws' in line.lower()):
                    print(f"Found process: {line[:100]}...")
                    gateway_found = True
            
            return gateway_found
            
        except Exception as e:
            print(f"Alternative process check failed: {e}")
            return False
            
    except Exception as e:
        print(f"Process check failed: {e}")
        return False

def step4_check_api_ports() -> bool:
    """
    Verify API ports are listening and accessible.
    
    Returns:
        True if at least one API port is accessible, False otherwise
    """
    listening_ports = []
    
    for port in DEFAULT_PORTS:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        
        try:
            result = sock.connect_ex(('127.0.0.1', port))
            if result == 0:
                port_type = 'Live' if port == LIVE_TRADING_PORT else 'Paper'
                print(f"✅ Port {port} is open ({port_type} trading)")
                listening_ports.append(port)
            else:
                print(f"❌ Port {port} is not accessible (error code: {result})")
        except socket.timeout:
            print(f"❌ Port {port} connection timed out")
        except Exception as e:
            print(f"❌ Port {port} check failed: {e}")
        finally:
            sock.close()
    
    if listening_ports:
        print(f"\nAPI ports ready: {listening_ports}")
        print(f"Configured for Master Client ID: {MASTER_CLIENT_ID}")
        return True
    else:
        print("\nNo API ports are listening!")
        print("In IB Gateway: Configure -> Settings -> API -> Settings:")
        print(f"  1. Enable ActiveX and Socket Clients")
        print(f"  2. Set Socket port to {PAPER_TRADING_PORT} for paper trading")
        print(f"  3. Set Master Client ID to {MASTER_CLIENT_ID}")
        print(f"  4. Uncheck 'Read-Only API' for trading capabilities")
        print(f"  5. Add Trusted IP: 127.0.0.1")
        return False

def step5_test_connection() -> bool:
    """
    Test actual IB API connection using ib_async with Master Client ID.
    
    Returns:
        True if connection successful, False otherwise
    """
    try:
        import ib_async
        from ib_async import IB
        
        print(f"ib_async version: {ib_async.__version__}")
        
        ib = IB()
        
        # Try connecting to paper trading port with Master Client ID
        print(f"\nAttempting connection to paper trading port ({PAPER_TRADING_PORT})...")
        print(f"Using Master Client ID: {MASTER_CLIENT_ID}")
        
        async def test_connect() -> bool:
            try:
                await ib.connectAsync(
                    '127.0.0.1', 
                    PAPER_TRADING_PORT, 
                    clientId=MASTER_CLIENT_ID, 
                    timeout=CONNECTION_TIMEOUT
                )
                return True
            except Exception as e:
                print(f"Connection failed: {e}")
                
                # Try with live port as fallback
                print(f"\nTrying live trading port ({LIVE_TRADING_PORT})...")
                try:
                    await ib.connectAsync(
                        '127.0.0.1', 
                        LIVE_TRADING_PORT, 
                        clientId=MASTER_CLIENT_ID, 
                        timeout=CONNECTION_TIMEOUT
                    )
                    print("⚠️  Connected to LIVE trading port - be careful!")
                    return True
                except Exception as e2:
                    print(f"Live port also failed: {e2}")
                    return False
        
        import asyncio
        success = asyncio.run(test_connect())
        
        if success:
            print("✅ Successfully connected to IB Gateway!")
            
            # Get connection details
            accounts = ib.managedAccounts()
            print(f"Managed accounts: {accounts}")
            
            # Check server version
            if hasattr(ib.client, 'serverVersion'):
                print(f"Server version: {ib.client.serverVersion}")
            
            # Check connection time
            if hasattr(ib.client, 'connectionTime'):
                print(f"Connection time: {ib.client.connectionTime}")
            
            ib.disconnect()
            return True
        else:
            return False
            
    except ImportError:
        print("ib_async not installed!")
        print("Install: pip install ib_async")
        return False
    except Exception as e:
        print(f"Connection test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
def main():
    """
    Main execution function for IB Gateway startup verification.
    """
    print("🚀 SPYDER IB Gateway Startup Verification")
    print("=" * 50)
    print(f"Master Client ID: {MASTER_CLIENT_ID}")
    print(f"Target Gateway Version: 10.39 (TWS_MAJOR_VRSN='1039')")
    print()
    
    steps = [
        ("Check Java Installation", step1_check_java),
        ("Find IB Gateway Installation", step2_find_ib_gateway),
        ("Check IB Gateway Running", step3_check_gateway_running),
        ("Check API Ports", step4_check_api_ports),
        ("Test API Connection", step5_test_connection)
    ]
    
    passed_steps = 0
    failed_step = None
    
    for i, (description, check_func) in enumerate(steps, 1):
        if check_step(i, description, check_func):
            passed_steps += 1
        else:
            failed_step = i
            print(f"\n⏸️  Stopping at step {i}. Fix this issue before continuing.")
            break
    
    # ==============================================================================
    # RESULTS SUMMARY
    # ==============================================================================
    print(f"\n{'=' * 50}")
    print(f"📊 Results: {passed_steps}/{len(steps)} steps passed")
    print(f"{'=' * 50}")
    
    if passed_steps == len(steps):
        print("🎉 All checks passed! IB Gateway is ready for Spyder trading!")
        print(f"\nConnection Configuration:")
        print(f"  • Host: 127.0.0.1")
        print(f"  • Port: {PAPER_TRADING_PORT} (Paper) or {LIVE_TRADING_PORT} (Live)")
        print(f"  • Client ID: {MASTER_CLIENT_ID}")
        print(f"  • Gateway Version: 10.39")
    else:
        print("❌ Some issues need to be resolved.")
        print("\n📋 Common Solutions:")
        
        if failed_step == 1:
            print("\n1. Install Java:")
            print("   sudo apt update")
            print("   sudo apt install openjdk-11-jdk")
            
        elif failed_step == 2:
            print("\n1. Download IB Gateway from:")
            print("   https://www.interactivebrokers.com/en/index.php?f=16040")
            print("\n2. Or use Docker:")
            print("   docker run -d --name ib_gateway gnzsnz/ib-gateway-docker:latest")
            
        elif failed_step == 3:
            print("\n1. Start IB Gateway application")
            print("2. Login to your IB account")
            print("3. Or check Docker container:")
            print("   docker start ib_gateway")
            
        elif failed_step == 4 or failed_step == 5:
            print("\n1. In IB Gateway: Configure -> Settings -> API -> Settings")
            print(f"2. Enable ActiveX and Socket Clients")
            print(f"3. Set Socket port to {PAPER_TRADING_PORT} (paper) or {LIVE_TRADING_PORT} (live)")
            print(f"4. Set Master Client ID to {MASTER_CLIENT_ID}")
            print(f"5. Uncheck 'Read-Only API' if you need to place orders")
            print(f"6. Add Trusted IP: 127.0.0.1")
            print(f"7. Click 'Apply' and restart Gateway if needed")
            
        print("\n📚 Documentation:")
        print("   https://interactivebrokers.github.io/tws-api/")

if __name__ == "__main__":
    main()