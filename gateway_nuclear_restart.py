#!/usr/bin/env python3
"""
Gateway Nuclear Restart & API Test
Completely restart Gateway and test if API starts responding
"""

import os
import sys
import time
import subprocess
from pathlib import Path
from datetime import datetime

JTS_PATH = Path.home() / "Jts"

def print_header(text):
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)

def kill_gateway():
    """Kill all Gateway processes"""
    print_header("🔥 KILLING ALL GATEWAY PROCESSES")
    
    try:
        # Kill Java processes related to Gateway
        result = subprocess.run(['pkill', '-9', '-f', 'ibgateway'], 
                              capture_output=True, text=True)
        
        print("✅ Sent kill signal to Gateway processes")
        
        # Wait and verify
        time.sleep(3)
        
        result = subprocess.run(['pgrep', '-f', 'ibgateway'], 
                              capture_output=True, text=True)
        
        if not result.stdout.strip():
            print("✅ All Gateway processes terminated")
            return True
        else:
            print(f"⚠️  Some processes still running: {result.stdout.strip()}")
            return False
            
    except Exception as e:
        print(f"❌ Error killing Gateway: {e}")
        return False

def clear_gateway_temp_files():
    """Clear Gateway temporary and lock files"""
    print_header("🧹 CLEARING GATEWAY TEMPORARY FILES")
    
    temp_patterns = [
        "*.lck",
        "*.lock",
        ".ibgateway*",
        "ibgateway*.pid"
    ]
    
    cleared = []
    
    for pattern in temp_patterns:
        for file in JTS_PATH.glob(f"**/{pattern}"):
            try:
                file.unlink()
                cleared.append(str(file))
                print(f"  Deleted: {file.name}")
            except Exception as e:
                print(f"  ⚠️  Could not delete {file.name}: {e}")
    
    if cleared:
        print(f"✅ Cleared {len(cleared)} temporary files")
    else:
        print("✅ No temporary files to clear")
    
    return True

def check_port_available():
    """Check if port 4002 is free"""
    print_header("🔍 CHECKING PORT AVAILABILITY")
    
    result = subprocess.run(['netstat', '-tlpn'], 
                          capture_output=True, text=True)
    
    if ':4002' in result.stdout:
        print("⚠️  Port 4002 is still in use!")
        for line in result.stdout.split('\n'):
            if ':4002' in line:
                print(f"  {line.strip()}")
        return False
    else:
        print("✅ Port 4002 is free and ready")
        return True

def wait_for_gateway_startup(max_wait=120):
    """Wait for Gateway to start and port to be listening"""
    print_header("⏳ WAITING FOR GATEWAY TO START")
    
    print(f"Waiting up to {max_wait} seconds for Gateway...")
    print("Please start Gateway now if not already started!")
    print()
    
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        # Check if Gateway process exists
        result = subprocess.run(['pgrep', '-f', 'ibgateway'], 
                              capture_output=True, text=True)
        
        if result.stdout.strip():
            # Process exists, check if port is listening
            result = subprocess.run(['netstat', '-tlpn'], 
                                  capture_output=True, text=True)
            
            if ':4002' in result.stdout:
                elapsed = time.time() - start_time
                print(f"\n✅ Gateway is running and port 4002 is listening!")
                print(f"   Startup time: {elapsed:.1f} seconds")
                return True
        
        # Show progress
        elapsed = int(time.time() - start_time)
        if elapsed % 10 == 0 and elapsed > 0:
            print(f"  Still waiting... ({elapsed}s elapsed)")
        
        time.sleep(1)
    
    print(f"\n❌ Timeout: Gateway did not start in {max_wait} seconds")
    return False

def test_api_connection():
    """Quick API connection test"""
    print_header("🧪 TESTING API CONNECTION")
    
    print("Testing with ib_async library...")
    print("This test will timeout in 10 seconds if API doesn't respond")
    print()
    
    try:
        import asyncio
        from ib_async import IB
        
        async def quick_test():
            ib = IB()
            try:
                print("📡 Attempting connection...")
                await asyncio.wait_for(
                    ib.connectAsync('127.0.0.1', 4002, clientId=999),
                    timeout=10.0
                )
                
                print("✅ Socket connected!")
                
                # Try to get accounts
                accounts = ib.managedAccounts()
                
                if accounts:
                    print(f"✅ API WORKING! Accounts: {accounts}")
                    ib.disconnect()
                    return True
                else:
                    print("⚠️  Connected but no accounts")
                    ib.disconnect()
                    return False
                    
            except asyncio.TimeoutError:
                print("❌ Connection timeout - API not responding")
                if ib.isConnected():
                    ib.disconnect()
                return False
            except Exception as e:
                print(f"❌ Connection error: {e}")
                if ib.isConnected():
                    ib.disconnect()
                return False
        
        success = asyncio.run(quick_test())
        return success
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def check_gateway_logs():
    """Check Gateway logs for errors"""
    print_header("📋 CHECKING GATEWAY LOGS")
    
    log_dir = JTS_PATH / "ibgateway" / "1039" / "logs"
    
    if not log_dir.exists():
        print(f"⚠️  Log directory not found: {log_dir}")
        return
    
    # Find latest log file
    log_files = sorted(log_dir.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
    
    if not log_files:
        print("⚠️  No log files found")
        return
    
    latest_log = log_files[0]
    print(f"📄 Latest log: {latest_log.name}")
    print(f"   Modified: {datetime.fromtimestamp(latest_log.stat().st_mtime)}")
    print()
    
    # Check for errors
    print("🔍 Checking for errors in last 50 lines...")
    
    try:
        with open(latest_log, 'r', errors='ignore') as f:
            lines = f.readlines()[-50:]  # Last 50 lines
        
        error_keywords = ['error', 'exception', 'fail', 'api', 'timeout']
        found_errors = []
        
        for line in lines:
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in error_keywords):
                found_errors.append(line.strip())
        
        if found_errors:
            print(f"⚠️  Found {len(found_errors)} potential issues:")
            for error in found_errors[-10:]:  # Show last 10
                print(f"  • {error[:100]}")
        else:
            print("✅ No obvious errors in recent logs")
            
    except Exception as e:
        print(f"⚠️  Could not read log: {e}")

def main():
    """Main execution"""
    print("=" * 70)
    print("🔥 GATEWAY NUCLEAR RESTART & API TEST")
    print("=" * 70)
    print(f"Timestamp: {datetime.now()}")
    print()
    print("This script will:")
    print("  1. Kill all Gateway processes")
    print("  2. Clear temporary files")
    print("  3. Wait for you to restart Gateway")
    print("  4. Test if API is responding")
    print()
    
    response = input("Continue? (y/n): ")
    if response.lower() != 'y':
        print("Aborted")
        return False
    
    # Step 1: Kill Gateway
    kill_gateway()
    time.sleep(2)
    
    # Step 2: Clear temp files
    clear_gateway_temp_files()
    time.sleep(1)
    
    # Step 3: Check port is free
    check_port_available()
    
    # Step 4: Check logs for clues
    check_gateway_logs()
    
    # Step 5: Wait for Gateway restart
    print()
    print("=" * 70)
    print("🚀 PLEASE START IB GATEWAY NOW")
    print("=" * 70)
    print()
    print("Instructions:")
    print("  1. Launch IB Gateway from your system menu")
    print("  2. Login to your paper trading account")
    print("  3. Wait for Gateway to be fully ready")
    print("  4. This script will detect when it's ready")
    print()
    
    if not wait_for_gateway_startup():
        return False
    
    # Step 6: Give Gateway time to fully initialize
    print("\n⏳ Waiting 10 seconds for Gateway to fully initialize API...")
    for i in range(10, 0, -1):
        print(f"   {i}...", end='\r')
        time.sleep(1)
    print()
    
    # Step 7: Test API
    success = test_api_connection()
    
    # Final report
    print_header("📊 FINAL REPORT")
    
    if success:
        print("🎉 SUCCESS!")
        print()
        print("✅ Gateway is running")
        print("✅ API is responding")
        print("✅ Can retrieve accounts")
        print()
        print("Your Gateway API is now working correctly!")
        print("You can now run SPYDER.")
    else:
        print("❌ API STILL NOT RESPONDING")
        print()
        print("Even after a fresh restart, the API is not working.")
        print()
        print("🔍 This suggests:")
        print()
        print("1. **Gateway 10.39 Bug**: Known issue on Linux/Ubuntu 25.04")
        print("   Solution: Downgrade to Gateway 10.25 or 10.37")
        print()
        print("2. **Java Version Issue**: Gateway 10.39 may need specific Java")
        print("   Check: java -version")
        print("   Gateway 10.39 works best with Java 11 or 17")
        print()
        print("3. **Wayland Display Issues**: Ubuntu 25.04 uses Wayland")
        print("   Try: Launch Gateway with X11 instead")
        print()
        print("4. **Corrupted Gateway Installation**")
        print("   Solution: Reinstall Gateway from IBKR website")
        print()
        print("5. **Try TWS instead of Gateway**")
        print("   TWS is more stable on Linux")
        print()
        print("🔧 Recommended Next Steps:")
        print("  1. Check Gateway logs: ~/Jts/ibgateway/1039/logs/")
        print("  2. Try: export DISPLAY=:0 before starting Gateway")
        print("  3. Consider using dockerized Gateway")
        print("  4. Contact IBKR support with Gateway version and OS details")
    
    print("=" * 70)
    
    return success

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
