#!/usr/bin/env python3
"""
Test connecting to IB Gateway via IPv6 directly
Since Gateway is listening on tcp6 :::4002
"""

import asyncio
import socket
from ib_async import IB

async def test_ipv6_connection():
    print("IB Gateway IPv6 Connection Test")
    print("=" * 50)
    print("Gateway is listening on: tcp6 :::4002 (IPv6 all interfaces)")
    print()
    
    # Test raw socket first
    print("1. Testing raw IPv6 socket connection...")
    sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    sock.settimeout(5)
    try:
        # Connect to IPv6 localhost
        result = sock.connect_ex(('::1', 4002, 0, 0))
        if result == 0:
            print("   ✅ IPv6 socket connected successfully")
        else:
            print(f"   ❌ IPv6 socket failed: error {result}")
            
            # Try IPv6 any address
            sock.close()
            sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex(('::', 4002, 0, 0))
            if result == 0:
                print("   ✅ Connected via :: (any IPv6)")
            else:
                print(f"   ❌ Cannot connect via IPv6")
    finally:
        sock.close()
    
    print("\n2. Testing IPv4-mapped-IPv6 address...")
    sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    sock.settimeout(5)
    try:
        # Try IPv4-mapped IPv6 address
        result = sock.connect_ex(('::ffff:127.0.0.1', 4002, 0, 0))
        if result == 0:
            print("   ✅ IPv4-mapped-IPv6 connected")
        else:
            print(f"   ❌ IPv4-mapped failed: error {result}")
    finally:
        sock.close()
    
    print("\n3. Testing IB API connections...")
    
    # Test configurations in order
    test_configs = [
        ('::1', 'IPv6 localhost'),
        ('localhost', 'localhost (should resolve to ::1)'),
        ('127.0.0.1', 'IPv4 localhost'),
        ('::ffff:127.0.0.1', 'IPv4-mapped-IPv6'),
    ]
    
    for host, description in test_configs:
        print(f"\n   Trying {description} ({host})...")
        
        for client_id in [0, 2]:
            ib = IB()
            try:
                print(f"      Client ID {client_id}: ", end="")
                
                await ib.connectAsync(
                    host=host,
                    port=4002,
                    clientId=client_id,
                    timeout=5
                )
                
                print(f"✅ CONNECTED!")
                print(f"         Server: v{ib.client.serverVersion()}")
                print(f"         Accounts: {ib.managedAccounts()}")
                
                ib.disconnect()
                return True
                
            except Exception as e:
                error = str(e)
                if "Couldn't connect" in error:
                    print("Timeout")
                elif "already in use" in error:
                    print("Already in use")
                else:
                    print(f"Failed: {error[:40]}")
            finally:
                if ib.isConnected():
                    ib.disconnect()
            
            await asyncio.sleep(0.5)
    
    return False

async def test_force_ipv4():
    """Try to force IPv4 connection"""
    print("\n4. Attempting to force IPv4...")
    
    # Check if we can make Gateway listen on IPv4
    print("   Checking sysctl settings...")
    import subprocess
    try:
        result = subprocess.run(['sysctl', 'net.ipv6.bindv6only'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print(f"   {result.stdout.strip()}")
            if "bindv6only = 1" in result.stdout:
                print("   ⚠️  System is configured for IPv6-only binding")
                print("   This prevents IPv4 connections to IPv6 sockets")
    except:
        pass
    
    return False

if __name__ == "__main__":
    success = asyncio.run(test_ipv6_connection())
    
    if not success:
        asyncio.run(test_force_ipv4())
        
        print("\n" + "=" * 50)
        print("SOLUTION OPTIONS:")
        print("=" * 50)
        print("""
Your Gateway is listening on IPv6-only. Here are solutions:

1. RESTART GATEWAY WITH IPv4 PREFERENCE:
   a) Close IB Gateway (File → Exit)
   b) Set environment variable before starting:
      export _JAVA_OPTIONS="-Djava.net.preferIPv4Stack=true"
   c) Start IB Gateway again
   d) Login with paper credentials

2. MODIFY SYSTEM IPv6 BINDING (temporary):
   sudo sysctl net.ipv6.bindv6only=0
   # This allows IPv6 sockets to accept IPv4 connections
   # Then restart Gateway

3. FORCE GATEWAY TO USE IPv4 PORT:
   In Gateway: Configure → Settings → API → Settings
   - Change Socket port from 4002 to another port (e.g., 4003)
   - Apply
   - Change back to 4002
   - Apply again
   - This sometimes forces it to bind correctly

4. USE DOCKER GATEWAY INSTEAD:
   docker run -d \\
     --name ib_gateway \\
     -p 4002:4002 \\
     -e TRADING_MODE=paper \\
     -e TWS_USERID=YOUR_USER \\
     -e TWS_PASSWORD=YOUR_PASS \\
     gnzsnz/ib-gateway-docker:latest

The issue is that Gateway bound to IPv6-only (:::4002) and isn't 
accepting IPv4 connections properly. This is a known issue with 
Java applications on some Linux configurations.
""")