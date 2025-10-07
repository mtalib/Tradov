#!/usr/bin/env python3
"""
SPYDER Gateway Startup Script
Ensures clean Gateway startup for reliable API connections
"""

import os
import sys
import time
import subprocess
from pathlib import Path
from datetime import datetime

JTS_PATH = Path.home() / "Jts"

def ensure_clean_gateway_start():
    """Ensure Gateway starts cleanly"""
    
    print("🕷️ SPYDER Gateway Startup")
    print("=" * 60)
    
    # Check if Gateway is already running
    result = subprocess.run(['pgrep', '-f', 'ibgateway'], 
                          capture_output=True, text=True)
    
    if result.stdout.strip():
        print("⚠️  Gateway is already running")
        print()
        print("Options:")
        print("  1. Use existing Gateway (if working)")
        print("  2. Restart Gateway for clean state")
        print()
        
        choice = input("Choice (1/2): ").strip()
        
        if choice == "2":
            print("\n🔄 Restarting Gateway...")
            subprocess.run(['pkill', '-9', '-f', 'ibgateway'], check=False)
            time.sleep(3)
            print("✅ Gateway stopped")
            return False  # Need to start manually
        else:
            print("\n✅ Using existing Gateway")
            return True
    
    print("ℹ️  Gateway not running")
    print()
    print("📋 Starting Gateway...")
    print()
    print("Please:")
    print("  1. Launch IB Gateway from your system menu")
    print("  2. Login to paper trading (DU5361048)")
    print("  3. Wait for Gateway to be fully ready")
    print()
    
    input("Press Enter when Gateway is ready...")
    
    # Wait for port to be listening
    print("\n⏳ Waiting for API port...")
    
    max_wait = 60
    start = time.time()
    
    while time.time() - start < max_wait:
        result = subprocess.run(['netstat', '-tlpn'], 
                              capture_output=True, text=True)
        
        if ':4002' in result.stdout:
            print("✅ Port 4002 is listening")
            return True
        
        time.sleep(1)
    
    print("❌ Timeout waiting for Gateway")
    return False

def test_api_connection():
    """Test if API is responding"""
    
    print("\n🧪 Testing API connection...")
    
    try:
        import asyncio
        from ib_async import IB
        
        async def test():
            ib = IB()
            try:
                await asyncio.wait_for(
                    ib.connectAsync('127.0.0.1', 4002, clientId=0),
                    timeout=10.0
                )
                
                accounts = ib.managedAccounts()
                ib.disconnect()
                
                return bool(accounts), accounts
                
            except Exception as e:
                if ib.isConnected():
                    ib.disconnect()
                return False, str(e)
        
        success, result = asyncio.run(test())
        
        if success:
            print(f"✅ API is working! Accounts: {result}")
            return True
        else:
            print(f"❌ API test failed: {result}")
            return False
            
    except Exception as e:
        print(f"❌ Test error: {e}")
        return False

def main():
    """Main execution"""
    
    # Ensure clean Gateway
    if not ensure_clean_gateway_start():
        print("\n❌ Gateway not ready")
        return False
    
    # Test API
    if not test_api_connection():
        print("\n❌ API not responding")
        print()
        print("Try:")
        print("  python3 gateway_nuclear_restart.py")
        return False
    
    # Ready to launch SPYDER
    print("\n" + "=" * 60)
    print("🎉 GATEWAY READY - LAUNCHING SPYDER")
    print("=" * 60)
    print()
    
    return True

if __name__ == "__main__":
    if main():
        print("✅ Ready to start SPYDER!")
        print()
        print("Run:")
        print("  python3 SpyderA_Core/SpyderA01_Main.py")
        sys.exit(0)
    else:
        print("\n❌ Gateway startup failed")
        sys.exit(1)
