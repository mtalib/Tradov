#!/usr/bin/env python3
"""
Minimal test to identify connection issue with IB Gateway 10.39
"""

import asyncio
import socket
from ib_async import IB

async def test_minimal():
    """Bare minimum connection test"""
    
    # First, verify port is open
    print("1. Testing raw socket to 127.0.0.1:4002...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    try:
        result = sock.connect_ex(('127.0.0.1', 4002))
        if result == 0:
            print("   ✅ Socket connected to port 4002")
        else:
            print(f"   ❌ Port 4002 not open, trying 4001...")
            sock.close()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex(('127.0.0.1', 4001))
            if result == 0:
                print("   ✅ Socket connected to port 4001 (LIVE!)")
                PORT = 4001
            else:
                print("   ❌ Neither port 4001 nor 4002 responding")
                return
        PORT = 4002
    finally:
        sock.close()
    
    print(f"\n2. Testing IB API connection on port {PORT}...")
    
    ib = IB()
    
    # Test with different client IDs
    for client_id in [0, 1, 2, 999]:
        print(f"\n   Testing Client ID {client_id}...")
        try:
            # Try with minimal parameters
            await ib.connectAsync(
                host='127.0.0.1',
                port=PORT,
                clientId=client_id,
                timeout=10
            )
            
            print(f"   ✅ SUCCESS! Connected with Client ID {client_id}")
            print(f"      Server version: {ib.client.serverVersion()}")
            print(f"      Connection time: {ib.client.connectionTime}")
            print(f"      Accounts: {ib.managedAccounts()}")
            
            ib.disconnect()
            return True
            
        except Exception as e:
            error = str(e)
            if "Couldn't connect" in error:
                print(f"      ❌ Timeout - API not responding")
            elif "already in use" in error:
                print(f"      ⚠️  Client ID {client_id} already in use")
            elif "invalid" in error:
                print(f"      ❌ Client ID {client_id} rejected as invalid")
            else:
                print(f"      ❌ Error: {error[:80]}")
        
        finally:
            if ib.isConnected():
                ib.disconnect()
        
        await asyncio.sleep(1)
    
    print("\n❌ All client IDs failed")
    
    # Try port 4001 if 4002 failed
    if PORT == 4002:
        print("\n3. Trying LIVE port 4001 as fallback...")
        ib = IB()
        try:
            await ib.connectAsync('127.0.0.1', 4001, clientId=0, timeout=5)
            print("   ⚠️  Connected on LIVE port 4001!")
            print("   Your Gateway is in LIVE mode, not PAPER mode")
            ib.disconnect()
            return True
        except:
            print("   ❌ Port 4001 also failed")
    
    return False

if __name__ == "__main__":
    print("IB Gateway 10.39 Minimal Connection Test")
    print("=" * 50)
    
    success = asyncio.run(test_minimal())
    
    if not success:
        print("\n" + "=" * 50)
        print("TROUBLESHOOTING:")
        print("=" * 50)
        print("""
Since Gateway IS running (logs show it's connected to IB servers):

1. CHECK GATEWAY WINDOW:
   - Is it showing "Paper Trading" or "Live Trading"?
   - Any error dialogs?
   - Status bar message?

2. CHECK FIREWALL:
   sudo ufw status
   # If active, allow the port:
   sudo ufw allow 4002/tcp

3. CHECK WHICH PORT IS LISTENING:
   netstat -tln | grep 400
   # or
   lsof -i :4002

4. TRY GATEWAY RESTART:
   - File → Exit in Gateway
   - Start Gateway
   - Login with PAPER credentials
   - Wait for "Connected" status
   - Run this test again

5. CHECK API SETTINGS AGAIN:
   Configure → Settings → API → Settings
   - Socket port: Should be 4002 for paper
   - Trusted IPs: Must have both 127.0.0.1 and ::1
   - Master Client ID: Set to 0 (allow any) temporarily

6. IF STILL FAILING:
   The issue might be ib_async compatibility with Gateway 10.39.
   Try downgrading: pip install ib_async==2.0.0
""")