#!/usr/bin/env python3
"""
SPYDER Automated Launcher with IBC Controller
One-shot launcher: Gateway + Auto-Login + SPYDER Dashboard

Usage:
    python3 spyder_launch.py [--clean-start] [--skip-gateway]
"""

import os
import sys
import time
import subprocess
import asyncio
from pathlib import Path
from datetime import datetime
import argparse

# Paths
SPYDER_HOME = Path.home() / "Projects" / "Spyder"
JTS_PATH = Path.home() / "Jts"
IBC_PATH = Path.home() / "ibc"

# Configuration from environment
IB_USERNAME = os.getenv("IB_USERNAME", "")
IB_PASSWORD = os.getenv("IB_PASSWORD", "")
IB_TRADING_MODE = os.getenv("IB_TRADING_MODE", "paper")
IB_PORT = int(os.getenv("IB_API_PORT_PAPER", "4002"))

def print_banner():
    """Print SPYDER launch banner"""
    print("\n" + "=" * 70)
    print("🕷️  SPYDER AUTOMATED LAUNCHER")
    print("=" * 70)
    print(f"Timestamp: {datetime.now()}")
    print(f"Trading Mode: {IB_TRADING_MODE.upper()}")
    print(f"API Port: {IB_PORT}")
    print("=" * 70 + "\n")

def check_credentials():
    """Check if IB credentials are configured"""
    print("🔐 Checking credentials...")
    
    if not IB_USERNAME or not IB_PASSWORD:
        print("❌ IB credentials not found in environment!")
        print()
        print("Please add to your ~/.bashrc:")
        print()
        print("  export IB_USERNAME='your_username'")
        print("  export IB_PASSWORD='your_password'")
        print("  export IB_TRADING_MODE='paper'")
        print()
        print("Then run: source ~/.bashrc")
        return False
    
    print(f"✅ Credentials found for user: {IB_USERNAME}")
    return True

def nuclear_restart_gateway():
    """Perform nuclear restart of Gateway"""
    print("\n" + "=" * 70)
    print("🔥 NUCLEAR RESTART: Cleaning Gateway State")
    print("=" * 70)
    
    # Kill all Gateway processes
    print("\n1️⃣  Killing all Gateway processes...")
    try:
        subprocess.run(['pkill', '-9', '-f', 'ibgateway'], 
                      capture_output=True, check=False)
        time.sleep(3)
        print("   ✅ Gateway processes terminated")
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    
    # Clear temp files
    print("\n2️⃣  Clearing temporary files...")
    temp_patterns = ["*.lck", "*.lock", ".ibgateway*", "ibgateway*.pid"]
    cleared = 0
    
    for pattern in temp_patterns:
        for file in JTS_PATH.glob(f"**/{pattern}"):
            try:
                file.unlink()
                cleared += 1
            except:
                pass
    
    if cleared:
        print(f"   ✅ Cleared {cleared} temporary files")
    else:
        print("   ✅ No temporary files to clear")
    
    # Verify port is free
    print("\n3️⃣  Checking port availability...")
    result = subprocess.run(['netstat', '-tlpn'], 
                          capture_output=True, text=True)
    
    if f':{IB_PORT}' in result.stdout:
        print(f"   ⚠️  Port {IB_PORT} still in use (will retry)")
    else:
        print(f"   ✅ Port {IB_PORT} is free")
    
    print("\n✅ Nuclear restart complete\n")

def check_gateway_running():
    """Check if Gateway is already running"""
    result = subprocess.run(['pgrep', '-f', 'ibgateway'], 
                          capture_output=True, text=True)
    return bool(result.stdout.strip())

def check_port_listening():
    """Check if API port is listening"""
    result = subprocess.run(['netstat', '-tlpn'], 
                          capture_output=True, text=True)
    return f':{IB_PORT}' in result.stdout

async def test_api_connection(timeout=10):
    """Test if API is responding"""
    try:
        from ib_async import IB
        
        ib = IB()
        try:
            await asyncio.wait_for(
                ib.connectAsync('127.0.0.1', IB_PORT, clientId=0),
                timeout=timeout
            )
            
            accounts = ib.managedAccounts()
            ib.disconnect()
            
            return bool(accounts), accounts
            
        except asyncio.TimeoutError:
            if ib.isConnected():
                ib.disconnect()
            return False, "Timeout"
        except Exception as e:
            if ib.isConnected():
                ib.disconnect()
            return False, str(e)
            
    except ImportError:
        return False, "ib_async not installed"

def launch_gateway_with_ibc():
    """Launch Gateway using IBC Controller"""
    print("\n" + "=" * 70)
    print("🚀 LAUNCHING IB GATEWAY WITH AUTO-LOGIN")
    print("=" * 70)
    
    # Check if IBC is installed
    ibc_script = IBC_PATH / "IBControllerStart.sh"
    if not ibc_script.exists():
        print(f"\n❌ IBC not found at: {ibc_script}")
        print("\nManual Gateway startup required:")
        print("  1. Launch IB Gateway from system menu")
        print("  2. Login with your credentials")
        print("  3. Wait for Gateway to be ready")
        print()
        input("Press Enter when Gateway is ready...")
        return True
    
    print(f"\n📋 IBC Configuration:")
    print(f"   Script: {ibc_script}")
    print(f"   Mode: {IB_TRADING_MODE.upper()}")
    print(f"   Port: {IB_PORT}")
    print()
    
    # Build IBC command
    cmd = [
        str(ibc_script),
        str(IB_PORT),
        IB_TRADING_MODE.upper(),
        IB_USERNAME,
        IB_PASSWORD
    ]
    
    print("🔄 Starting Gateway with IBC...")
    
    try:
        # Start IBC in background
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True
        )
        
        print(f"✅ IBC started (PID: {process.pid})")
        return True
        
    except Exception as e:
        print(f"❌ Failed to start IBC: {e}")
        return False

def wait_for_gateway_ready(max_wait=120):
    """Wait for Gateway to be fully ready"""
    print("\n" + "=" * 70)
    print("⏳ WAITING FOR GATEWAY TO BE READY")
    print("=" * 70)
    print(f"\nWaiting up to {max_wait} seconds...")
    print("(Gateway startup + login + API initialization)")
    print()
    
    start_time = time.time()
    last_status = None
    
    while time.time() - start_time < max_wait:
        elapsed = int(time.time() - start_time)
        
        # Check process
        is_running = check_gateway_running()
        
        # Check port
        is_listening = check_port_listening()
        
        # Determine status
        if not is_running:
            status = "Starting..."
        elif not is_listening:
            status = "Logging in..."
        else:
            status = "Initializing API..."
        
        # Print status update every 5 seconds
        if status != last_status or elapsed % 5 == 0:
            print(f"  [{elapsed:3d}s] {status}")
            last_status = status
        
        # If port is listening, give it time to fully initialize
        if is_listening:
            print(f"\n✅ Port {IB_PORT} is listening!")
            print("   Waiting 10 seconds for API to fully initialize...")
            
            for i in range(10, 0, -1):
                print(f"   {i}...", end='\r', flush=True)
                time.sleep(1)
            
            print("\n")
            return True
        
        time.sleep(1)
    
    print(f"\n❌ Timeout after {max_wait} seconds")
    return False

async def verify_api_working():
    """Verify API is working"""
    print("=" * 70)
    print("🧪 VERIFYING API CONNECTION")
    print("=" * 70)
    print()
    
    success, result = await test_api_connection(timeout=10)
    
    if success:
        print(f"✅ API CONNECTION SUCCESSFUL!")
        print(f"   Accounts: {result}")
        print()
        return True
    else:
        print(f"❌ API connection failed: {result}")
        print()
        return False

def launch_spyder_dashboard():
    """Launch SPYDER Dashboard"""
    print("=" * 70)
    print("🕷️  LAUNCHING SPYDER DASHBOARD")
    print("=" * 70)
    print()
    
    dashboard_script = SPYDER_HOME / "SpyderG_GUI" / "SpyderG02_GUIEntry.py"
    
    if not dashboard_script.exists():
        # Try alternative: Main system
        dashboard_script = SPYDER_HOME / "SpyderA_Core" / "SpyderA01_Main.py"
    
    if not dashboard_script.exists():
        print(f"❌ Dashboard script not found!")
        print(f"   Expected: {dashboard_script}")
        return False
    
    print(f"📊 Dashboard: {dashboard_script.name}")
    print()
    print("🚀 Starting SPYDER...")
    print()
    
    try:
        # Launch dashboard
        os.chdir(SPYDER_HOME)
        
        # Use subprocess to launch but let it run independently
        subprocess.Popen([sys.executable, str(dashboard_script)])
        
        print("✅ SPYDER Dashboard launched!")
        print()
        print("=" * 70)
        print("🎉 SPYDER IS NOW OPERATIONAL!")
        print("=" * 70)
        print()
        print("📋 System Status:")
        print("   ✅ IB Gateway running")
        print("   ✅ API connected")
        print(f"   ✅ Trading mode: {IB_TRADING_MODE.upper()}")
        print("   ✅ Dashboard active")
        print()
        print("Happy Trading! 🕷️💰")
        print()
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to launch dashboard: {e}")
        return False

async def main():
    """Main launch sequence"""
    
    parser = argparse.ArgumentParser(description='SPYDER Auto-Launcher')
    parser.add_argument('--clean-start', action='store_true',
                       help='Force nuclear restart before launch')
    parser.add_argument('--skip-gateway', action='store_true',
                       help='Skip Gateway launch (use existing)')
    args = parser.parse_args()
    
    # Print banner
    print_banner()
    
    # Check credentials
    if not check_credentials():
        return False
    
    # Check if Gateway is already running
    already_running = check_gateway_running()
    port_listening = check_port_listening()
    
    if already_running and port_listening and not args.clean_start:
        print("\n✅ Gateway is already running and port is listening")
        print()
        print("Options:")
        print("  1. Use existing Gateway")
        print("  2. Restart Gateway (clean start)")
        print()
        
        choice = input("Choice (1/2): ").strip()
        
        if choice == "2":
            args.clean_start = True
        else:
            print("\n✅ Using existing Gateway")
            args.skip_gateway = True
    
    # Nuclear restart if requested
    if args.clean_start:
        nuclear_restart_gateway()
        args.skip_gateway = False
    
    # Launch Gateway
    if not args.skip_gateway:
        if not launch_gateway_with_ibc():
            return False
        
        if not wait_for_gateway_ready():
            print("\n❌ Gateway failed to start properly")
            print("\nTroubleshooting:")
            print("  1. Check Gateway logs: ~/Jts/ibgateway/1039/logs/")
            print("  2. Verify credentials in ~/.bashrc")
            print("  3. Try manual Gateway launch")
            return False
    
    # Verify API
    if not await verify_api_working():
        print("\n⚠️  API not responding")
        print("\nOptions:")
        print("  1. Wait longer and retry")
        print("  2. Do nuclear restart: python3 gateway_nuclear_restart.py")
        return False
    
    # Launch SPYDER
    if not launch_spyder_dashboard():
        return False
    
    return True

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Launch interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Launch error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
