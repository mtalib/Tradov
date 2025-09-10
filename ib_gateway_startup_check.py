#!/usr/bin/env python3
"""
IB Gateway Startup Verification Script
Step-by-step guide to get IB Gateway working
"""

import os
import subprocess
import time
import socket
import sys

def check_step(step_num, description, check_func):
    """Helper function to run a check step"""
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

def step1_check_java():
    """Check if Java is installed"""
    try:
        result = subprocess.run(['java', '-version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version_line = result.stderr.split('\n')[0]
            print(f"Java found: {version_line}")
            return True
        else:
            print("Java not found or not working")
            print("Install Java: sudo apt update && sudo apt install openjdk-11-jdk")
            return False
    except Exception as e:
        print(f"Java check failed: {e}")
        return False

def step2_find_ib_gateway():
    """Look for IB Gateway installation"""
    common_paths = [
        os.path.expanduser("~/IBJts/ibgateway"),
        "/opt/IBJts/ibgateway",
        os.path.expanduser("~/Jts/ibgateway")
    ]
    
    for path in common_paths:
        if os.path.exists(path):
            print(f"IB Gateway found at: {path}")
            return True
    
    print("IB Gateway not found in common locations")
    print("Download from: https://www.interactivebrokers.com/en/index.php?f=16040")
    return False

def step3_check_gateway_running():
    """Check if IB Gateway is actually running"""
    try:
        # Check for java processes with gateway-related keywords
        result = subprocess.run(['pgrep', '-f', 'java.*gateway|java.*ibgateway|java.*tws'], 
                              capture_output=True, text=True)
        
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            print(f"Found {len(pids)} IB Gateway Java process(es): {', '.join(pids)}")
            return True
        else:
            print("No IB Gateway processes running")
            print("Start IB Gateway manually first!")
            return False
    except Exception as e:
        print(f"Process check failed: {e}")
        return False

def step4_check_api_ports():
    """Check if API ports are listening"""
    ports = [4001, 4002]  # Live and Paper trading ports
    listening_ports = []
    
    for port in ports:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        
        try:
            result = sock.connect_ex(('127.0.0.1', port))
            if result == 0:
                print(f"✅ Port {port} is open ({'Live' if port == 4001 else 'Paper'} trading)")
                listening_ports.append(port)
            else:
                print(f"❌ Port {port} is not accessible")
        except Exception as e:
            print(f"❌ Port {port} check failed: {e}")
        finally:
            sock.close()
    
    if listening_ports:
        print(f"API ports ready: {listening_ports}")
        return True
    else:
        print("No API ports are listening!")
        print("In IB Gateway: Configure -> Settings -> API -> Enable ActiveX and Socket Clients")
        return False

def step5_test_connection():
    """Test actual IB API connection"""
    try:
        import ib_async
        from ib_async import IB
        
        ib = IB()
        
        # Try connecting to paper trading port
        print("Attempting connection to paper trading port (4002)...")
        
        async def test_connect():
            try:
                await ib.connectAsync('127.0.0.1', 4002, clientId=1, timeout=15)
                return True
            except Exception as e:
                print(f"Connection failed: {e}")
                return False
        
        import asyncio
        success = asyncio.run(test_connect())
        
        if success:
            print("✅ Successfully connected to IB Gateway!")
            accounts = ib.managedAccounts()
            print(f"Managed accounts: {accounts}")
            ib.disconnect()
            return True
        else:
            return False
            
    except ImportError:
        print("ib_async not installed: pip install ib_async")
        return False
    except Exception as e:
        print(f"Connection test failed: {e}")
        return False

def main():
    print("🚀 IB Gateway Startup Verification")
    print("=" * 50)
    
    steps = [
        ("Check Java Installation", step1_check_java),
        ("Find IB Gateway Installation", step2_find_ib_gateway),
        ("Check IB Gateway Running", step3_check_gateway_running),
        ("Check API Ports", step4_check_api_ports),
        ("Test API Connection", step5_test_connection)
    ]
    
    passed_steps = 0
    
    for i, (description, check_func) in enumerate(steps, 1):
        if check_step(i, description, check_func):
            passed_steps += 1
        else:
            print(f"\n⏸️  Stopping at step {i}. Fix this issue before continuing.")
            break
    
    print(f"\n📊 Results: {passed_steps}/{len(steps)} steps passed")
    
    if passed_steps == len(steps):
        print("🎉 All checks passed! IB Gateway is ready for trading!")
    else:
        print("❌ Some issues need to be resolved.")
        print("\n📋 Common Solutions:")
        print("1. Make sure IB Gateway application is running and logged in")
        print("2. In IB Gateway: Configure -> Settings -> API -> Enable ActiveX and Socket Clients")
        print("3. Set Socket port to 4002 for paper trading")
        print("4. Uncheck 'Read-Only API' if you need to place orders")
        print("5. Click 'Apply' and restart Gateway if needed")

if __name__ == "__main__":
    main()