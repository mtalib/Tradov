#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Tests
Module: temp_api_handshake_test.py
Purpose: Detailed IB Gateway API handshake diagnostics for multi-client architecture
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-09 Time: 14:30:00

Module Description:
    Advanced diagnostic tool to identify why IB Gateway accepts socket
    connections but doesn't complete API handshake. Tests the Spyder
    multi-client architecture with proper client allocation:
    - Client 1: Order Execution
    - Client 2: Master/Administrative (MASTER_CLIENT_ID)
    - Clients 3-10: Various market data feeds

"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import socket
import struct
import time
import sys
from typing import Optional, List, Tuple, Dict
from datetime import datetime

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    from ib_async import IB, util
    IB_ASYNC_AVAILABLE = True
except ImportError:
    IB_ASYNC_AVAILABLE = False
    print("⚠️  ib_async not available for full testing")

# ==============================================================================
# SPYDER CLIENT ARCHITECTURE CONSTANTS
# ==============================================================================
MASTER_CLIENT_ID = 2  # Administrative Operations Master

# Client allocation as per Spyder architecture
CLIENT_ALLOCATION = {
    1: "Order Execution (HIGHEST PRIORITY)",
    2: "Administrative Operations (MASTER)",
    3: "Core Market Data (SPY, SPX, /ES, VIX)",
    4: "SPY Options Chains (0DTE, 1DTE)",
    5: "Volatility Indicators (VIX9D, VXV, VXMT)",
    6: "Market Internals (TRIN, ADD, CPC)",
    7: "Major Indices (DIA, QQQ, IWM)",
    8: "Extended Assets (TLT, LQD, DXY, GLD)",
    9: "Sector ETFs (XLF, XLK, XLE, etc.)",
    10: "International Markets (FTLC, DAX, EWJ)"
}

# Test different client IDs in priority order
TEST_CLIENT_IDS = [2, 1, 3, 4, 5]  # Master first, then order, then data clients

PAPER_PORT = 4002
LIVE_PORT = 4001
MIN_CLIENT_VERSION = 100
MIN_SERVER_VERSION = 38

# ==============================================================================
# RAW API PROTOCOL TEST
# ==============================================================================
def test_raw_api_handshake(host: str, port: int) -> dict:
    """
    Test raw IB API handshake protocol.
    
    The IB API handshake sequence:
    1. Client sends: API version prefix
    2. Client sends: Client version
    3. Server responds with version info
    4. Client sends: Client ID and optional account
    
    Args:
        host: Host address (IPv4 or IPv6)
        port: Port number
        
    Returns:
        Dictionary with test results
    """
    print(f"\n🔬 Testing Raw API Handshake on {host}:{port}")
    print("=" * 50)
    
    result = {
        'socket_connected': False,
        'api_prefix_sent': False,
        'version_sent': False,
        'server_response': None,
        'handshake_complete': False,
        'error': None
    }
    
    try:
        # Determine address family
        addr_info = socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
        if not addr_info:
            result['error'] = "Cannot resolve address"
            return result
        
        family = addr_info[0][0]
        addr = addr_info[0][4]
        
        print(f"1. Creating socket ({family.name})...")
        sock = socket.socket(family, socket.SOCK_STREAM)
        sock.settimeout(10)
        
        print(f"2. Connecting to {addr}...")
        sock.connect(addr)
        result['socket_connected'] = True
        print("   ✅ Socket connected")
        
        # Step 1: Send API prefix
        print("3. Sending API version prefix...")
        
        # Try different protocol versions
        # Version 9 and 10 are common for newer IB Gateway versions
        versions_to_try = [
            (b"API\0", "Standard prefix"),
            (b"v9\0", "Version 9 prefix"),
            (b"v10\0", "Version 10 prefix"),
            (b"v%d..%d\0" % (MIN_CLIENT_VERSION, MIN_CLIENT_VERSION + 4), "Version range")
        ]
        
        for prefix, description in versions_to_try:
            print(f"   Trying: {description} - {prefix}")
            
            try:
                # Create new socket for each attempt
                sock.close()
                sock = socket.socket(family, socket.SOCK_STREAM)
                sock.settimeout(10)
                sock.connect(addr)
                
                # Send prefix
                sock.send(prefix)
                result['api_prefix_sent'] = True
                
                # Small delay
                time.sleep(0.5)
                
                # Try to receive response
                sock.settimeout(3)
                try:
                    response = sock.recv(1024)
                    if response:
                        print(f"   📨 Server responded: {response[:50]}")
                        result['server_response'] = response
                        
                        # Try to parse response
                        try:
                            # Response might be version info
                            if b'\0' in response:
                                parts = response.split(b'\0')
                                print(f"   Response parts: {[p for p in parts if p]}")
                        except:
                            pass
                        
                        result['handshake_complete'] = True
                        break
                except socket.timeout:
                    print(f"   ⏱️  No response within 3 seconds")
                except Exception as e:
                    print(f"   ❌ Receive error: {e}")
                    
            except Exception as e:
                print(f"   ❌ Error with {description}: {e}")
        
        sock.close()
        
    except socket.timeout:
        result['error'] = "Socket connection timeout"
        print("❌ Socket connection timed out")
    except ConnectionRefusedError:
        result['error'] = "Connection refused"
        print("❌ Connection refused")
    except Exception as e:
        result['error'] = str(e)
        print(f"❌ Error: {e}")
    
    return result

# ==============================================================================
# SPYDER CLIENT ID TESTING
# ==============================================================================
async def test_spyder_clients() -> List[Tuple[int, bool, str]]:
    """
    Test connection with Spyder's multi-client architecture.
    
    Returns:
        List of (client_id, success, message) tuples
    """
    if not IB_ASYNC_AVAILABLE:
        print("⚠️  ib_async not available, skipping client ID tests")
        return []
    
    print("\n🔢 Testing Spyder Client Architecture")
    print("=" * 50)
    print("Client Allocation:")
    for cid, purpose in CLIENT_ALLOCATION.items():
        if cid <= 5:  # Show first 5 for brevity
            print(f"  Client {cid:2d}: {purpose}")
    
    results = []
    
    # Test in priority order: Master first, then others
    for client_id in TEST_CLIENT_IDS:
        purpose = CLIENT_ALLOCATION.get(client_id, "Unknown")
        print(f"\nTesting Client ID {client_id}: {purpose}")
        
        ib = IB()
        
        # Try different host addresses
        for host in ['127.0.0.1', '::1', 'localhost']:
            try:
                print(f"  Trying {host}:{PAPER_PORT}...", end=" ")
                
                await ib.connectAsync(
                    host=host,
                    port=PAPER_PORT,
                    clientId=client_id,
                    timeout=10
                )
                
                print(f"✅ Connected!")
                
                # Get connection info
                accounts = ib.managedAccounts()
                server_version = getattr(ib.client, 'serverVersion', 'Unknown')
                
                message = f"Connected via {host}, accounts: {accounts}, server: v{server_version}"
                results.append((client_id, True, message))
                
                # Test specific functionality based on client type
                if client_id == MASTER_CLIENT_ID:
                    print(f"     Master client verified - can manage accounts")
                elif client_id == 1:
                    print(f"     Order client verified - ready for trading")
                else:
                    print(f"     Data client verified - ready for market data")
                
                ib.disconnect()
                await asyncio.sleep(1)
                break
                
            except asyncio.TimeoutError:
                print(f"⏱️  Timeout")
                continue
            except Exception as e:
                error_msg = str(e)
                print(f"❌ {error_msg[:50]}")
                
                # Check for specific error messages
                if "already in use" in error_msg.lower():
                    results.append((client_id, False, f"Client ID {client_id} already in use"))
                    break
                elif "invalid" in error_msg.lower():
                    results.append((client_id, False, f"Client ID {client_id} invalid"))
                    break
                elif "not logged in" in error_msg.lower():
                    results.append((client_id, False, "Gateway not logged in"))
                    break
                continue
        else:
            # No successful connection with any host
            results.append((client_id, False, "Connection failed on all addresses"))
        
        if ib.isConnected():
            ib.disconnect()
            await asyncio.sleep(1)
    
    return results

# ==============================================================================
# GATEWAY CONFIGURATION CHECK FOR MULTI-CLIENT
# ==============================================================================
def check_multi_client_config():
    """
    Provide configuration guidance for Spyder's multi-client setup.
    """
    print("\n📋 Multi-Client Configuration Requirements")
    print("=" * 50)
    
    print("""
SPYDER MULTI-CLIENT ARCHITECTURE REQUIREMENTS:

In IB Gateway (Configure -> Settings -> API -> Settings):

1. ✓ Enable ActiveX and Socket Clients
   Status: MUST BE CHECKED (Currently appears UNCHECKED!)
   
2. Socket Port: 4002
   Status: Must match for paper trading
   
3. Master Client ID: 2
   Status: This is your administrative client
   Note: Can also set to 0 to allow any client
   
4. ✓ Allow connections from localhost only
   Status: CHECKED for security
   
5. Trusted IP Addresses (BOTH required):
   127.0.0.1
   ::1
   
6. ☐ Read-Only API
   Status: MUST BE UNCHECKED (Client 1 needs trading)
   
7. ✓ Create API message log file
   Status: CHECK to debug connection attempts
   
8. Maximum Client Connections:
   Your subscription must support 10+ simultaneous connections

CRITICAL ISSUE DETECTED:
========================
❌ API appears to be DISABLED!

The "Enable ActiveX and Socket Clients" checkbox is likely UNCHECKED.
This MUST be checked for ANY API connection to work.

IMMEDIATE ACTION REQUIRED:
1. Open IB Gateway
2. Configure -> Settings -> API -> Settings
3. CHECK "Enable ActiveX and Socket Clients" ✓
4. Add both IPs to Trusted list (127.0.0.1 and ::1)
5. Click Apply
6. RESTART IB Gateway completely

CLIENT CONNECTION SEQUENCE:
===========================
After fixing settings, connect in this order:
1. Client 2 (Master) - MUST connect first
2. Client 1 (Orders) - Critical for trading
3. Clients 3-10 (Data) - Can connect in any order

TROUBLESHOOTING:
===============
• If Master (Client 2) fails: Check no other app uses Client ID 2
• If all fail: API is disabled - check the checkbox!
• If some work: Check subscription limits
• Enable API log file to see exact errors
""")

# ==============================================================================
# TELNET CONNECTION TEST
# ==============================================================================
def test_telnet_connection(host: str, port: int):
    """
    Test if we can telnet to the port.
    """
    print(f"\n🔌 Testing telnet-like connection to {host}:{port}")
    
    try:
        import subprocess
        result = subprocess.run(
            ['timeout', '5', 'telnet', host, str(port)],
            capture_output=True,
            text=True
        )
        
        if "Connected" in result.stdout or "Escape character" in result.stdout:
            print("✅ Telnet connection successful")
            print("   Gateway is accepting TCP connections")
            print("   But API layer is not responding - API likely disabled")
        else:
            print("❌ Telnet connection failed")
            
    except:
        print("⚠️  Telnet test skipped (telnet not available)")

# ==============================================================================
# MAIN DIAGNOSTIC FUNCTION
# ==============================================================================
async def main():
    """
    Run comprehensive API handshake diagnostics for Spyder architecture.
    """
    print("🔬 SPYDER Multi-Client API Handshake Diagnostics")
    print("=" * 50)
    print(f"Target Port: {PAPER_PORT}")
    print(f"Master Client ID: {MASTER_CLIENT_ID}")
    print(f"Total Clients: 10 (IDs 1-10)")
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test raw API handshake on both IPv4 and IPv6
    print("\n" + "=" * 50)
    print("PHASE 1: Raw Socket Tests")
    print("=" * 50)
    
    ipv4_result = test_raw_api_handshake('127.0.0.1', PAPER_PORT)
    ipv6_result = test_raw_api_handshake('::1', PAPER_PORT)
    
    # Test telnet
    test_telnet_connection('::1', PAPER_PORT)
    
    # Test Spyder client architecture
    print("\n" + "=" * 50)
    print("PHASE 2: Spyder Client Tests")
    print("=" * 50)
    
    if IB_ASYNC_AVAILABLE:
        client_results = await test_spyder_clients()
        
        print("\n📊 Spyder Client Test Summary:")
        for client_id, success, message in client_results:
            status = "✅" if success else "❌"
            purpose = CLIENT_ALLOCATION.get(client_id, "Unknown")[:30]
            print(f"  {status} Client {client_id:2d} ({purpose}): {message}")
    
    # Show configuration requirements
    print("\n" + "=" * 50)
    print("PHASE 3: Configuration Analysis")
    print("=" * 50)
    
    check_multi_client_config()
    
    # Final diagnosis
    print("\n" + "=" * 50)
    print("🔍 DIAGNOSIS")
    print("=" * 50)
    
    api_responds = ipv6_result.get('server_response') or ipv4_result.get('server_response')
    socket_connects = ipv6_result['socket_connected'] or ipv4_result['socket_connected']
    
    if socket_connects and not api_responds:
        print("""
❌ CRITICAL PROBLEM: API IS DISABLED!

TCP socket connects but IB Gateway API layer doesn't respond.

This means: "Enable ActiveX and Socket Clients" is UNCHECKED

SOLUTION:
1. Open IB Gateway NOW
2. Configure -> Settings -> API -> Settings
3. CHECK "Enable ActiveX and Socket Clients" ✓
4. Add BOTH to Trusted IPs:
   127.0.0.1
   ::1
5. Set Master Client ID to 2
6. Click Apply
7. RESTART IB Gateway

After this, ALL 10 clients should connect successfully.
""")
    elif api_responds:
        print("""
✅ API is responding at protocol level!

If clients still can't connect:
1. Check Client IDs aren't already in use
2. Verify Master Client ID setting (should be 2)
3. Check account login status
4. Review API message log for specific errors
""")
    else:
        print("""
⚠️  No connectivity detected

Gateway may not be running or port is blocked.
1. Verify IB Gateway is running and logged in
2. Check firewall isn't blocking port 4002
3. Ensure Gateway is configured for paper trading
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