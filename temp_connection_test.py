#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Tests
Module: temp_connection_test.py
Purpose: Basic IB Gateway connection test with IPv4/IPv6 support
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-09 Time: 13:00:00

Module Description:
    Lightweight connection test for IB Gateway that properly handles both
    IPv4 and IPv6 connections. Designed to test connectivity without
    interfering with existing Gateway processes. Uses the configured
    Master Client ID and provides clear diagnostic output for connection
    issues specific to Ubuntu 25.04 with Wayland.

"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import socket
import sys
import time
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
import subprocess

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    from ib_async import IB, Stock
    IB_ASYNC_AVAILABLE = True
except ImportError:
    IB_ASYNC_AVAILABLE = False
    print("❌ ib_async not installed. Install with: pip install ib_async")

# ==============================================================================
# CONSTANTS
# ==============================================================================
MASTER_CLIENT_ID = 2  # Master Client ID for Spyder system
PAPER_TRADING_PORT = 4002
LIVE_TRADING_PORT = 4001
CONNECTION_TIMEOUT = 30  # seconds

# ==============================================================================
# NETWORK DETECTION FUNCTIONS
# ==============================================================================
def detect_listening_addresses(port: int) -> Dict[str, bool]:
    """
    Detect which addresses (IPv4/IPv6) are listening on a port.
    
    Args:
        port: Port number to check
        
    Returns:
        Dictionary with IPv4/IPv6 listening status
    """
    result = {
        'ipv4': False,
        'ipv6': False,
        'ipv4_addr': '127.0.0.1',
        'ipv6_addr': '::1'
    }
    
    try:
        # Check netstat output
        netstat_output = subprocess.run(
            ['netstat', '-tln'], 
            capture_output=True, 
            text=True
        )
        
        if netstat_output.returncode == 0:
            lines = netstat_output.stdout.split('\n')
            for line in lines:
                if f':{port}' in line and 'LISTEN' in line:
                    if 'tcp ' in line and '127.0.0.1' in line:
                        result['ipv4'] = True
                        print(f"   ✅ IPv4 listening on 127.0.0.1:{port}")
                    elif 'tcp ' in line and '0.0.0.0' in line:
                        result['ipv4'] = True
                        print(f"   ✅ IPv4 listening on 0.0.0.0:{port} (all interfaces)")
                    elif 'tcp6' in line and ':::' in line:
                        result['ipv6'] = True
                        print(f"   ✅ IPv6 listening on :::{port} (all IPv6 interfaces)")
                    elif 'tcp6' in line and '::1' in line:
                        result['ipv6'] = True
                        print(f"   ✅ IPv6 listening on ::1:{port} (localhost IPv6)")
    except:
        # Fallback to ss command
        try:
            ss_output = subprocess.run(
                ['ss', '-tln'], 
                capture_output=True, 
                text=True
            )
            
            if ss_output.returncode == 0:
                lines = ss_output.stdout.split('\n')
                for line in lines:
                    if f':{port}' in line and 'LISTEN' in line:
                        if '127.0.0.1' in line or '0.0.0.0' in line:
                            result['ipv4'] = True
                        if '::1' in line or ':::' in line or '*:' in line:
                            result['ipv6'] = True
        except:
            pass
    
    # If IPv6 is listening on all interfaces, we can also connect via IPv4
    if result['ipv6'] and not result['ipv4']:
        print("   ℹ️  IPv6 listening on all interfaces - IPv4 connections may work via IPv6 socket")
    
    return result

def test_raw_socket_connection(host: str, port: int, timeout: int = 5) -> bool:
    """
    Test raw socket connection to host:port.
    
    Args:
        host: Hostname or IP address
        port: Port number
        timeout: Connection timeout in seconds
        
    Returns:
        True if connection successful, False otherwise
    """
    # Determine address family
    try:
        addr_info = socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
        if not addr_info:
            return False
        
        family = addr_info[0][0]
        addr = addr_info[0][4]
        
        sock = socket.socket(family, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        
        try:
            result = sock.connect_ex(addr)
            if result == 0:
                print(f"   ✅ Raw socket connected to {host}:{port} ({family.name})")
                return True
            else:
                print(f"   ❌ Socket connection failed: error code {result}")
                return False
        finally:
            sock.close()
            
    except Exception as e:
        print(f"   ❌ Socket test failed: {e}")
        return False

# ==============================================================================
# IB GATEWAY CONNECTION TEST
# ==============================================================================
async def test_basic_connection() -> bool:
    """
    Test basic IB Gateway connection with IPv4/IPv6 support.
    
    Returns:
        True if connection successful, False otherwise
    """
    if not IB_ASYNC_AVAILABLE:
        print("❌ Cannot test - ib_async not installed")
        return False
    
    ib = IB()
    
    # Test configurations in order of preference
    test_configs = [
        ('127.0.0.1', PAPER_TRADING_PORT, 'IPv4 Paper Trading'),
        ('::1', PAPER_TRADING_PORT, 'IPv6 Paper Trading'),
        ('localhost', PAPER_TRADING_PORT, 'Localhost Paper Trading'),
        ('127.0.0.1', LIVE_TRADING_PORT, 'IPv4 Live Trading'),
        ('::1', LIVE_TRADING_PORT, 'IPv6 Live Trading'),
    ]
    
    for host, port, description in test_configs:
        print(f"\n🔌 Attempting connection to {host}:{port} ({description})...")
        print(f"   Client ID: {MASTER_CLIENT_ID}")
        
        try:
            await ib.connectAsync(
                host=host,
                port=port,
                clientId=MASTER_CLIENT_ID,
                timeout=CONNECTION_TIMEOUT
            )
            
            print(f"✅ Connection successful via {description}!")
            
            # Get connection details
            try:
                if hasattr(ib.client, 'serverVersion'):
                    print(f"   Server version: {ib.client.serverVersion}")
                
                print(f"   Connection state: {ib.isConnected()}")
                
                # Get managed accounts
                managed_accounts = ib.managedAccounts()
                print(f"   Managed accounts: {managed_accounts}")
                
                # Try to get next order ID
                if hasattr(ib.client, 'getReqId'):
                    print(f"   Next order ID: {ib.client.getReqId()}")
                
                # Wait for initial data
                await asyncio.sleep(2)
                
                # Test market data permissions
                print("\n📊 Testing market data permissions...")
                
                # Create SPY contract
                spy = Stock('SPY', 'SMART', 'USD')
                contracts = await ib.qualifyContractsAsync(spy)
                
                if contracts:
                    print(f"   ✅ Contract qualified: {contracts[0]}")
                    
                    # Request market data
                    ticker = ib.reqMktData(contracts[0], '', snapshot=True)
                    print(f"   Market data request sent for: {ticker.contract.symbol}")
                    
                    # Wait for data
                    await asyncio.sleep(5)
                    
                    # Check for data
                    if ticker.last and ticker.last > 0:
                        print(f"   ✅ Market data received: Last=${ticker.last}")
                    else:
                        data_status = []
                        if ticker.bid: data_status.append(f"bid=${ticker.bid}")
                        if ticker.ask: data_status.append(f"ask=${ticker.ask}")
                        if ticker.close: data_status.append(f"close=${ticker.close}")
                        
                        if data_status:
                            print(f"   ⚠️  Partial data: {', '.join(data_status)}")
                        else:
                            print(f"   ⚠️  No market data yet (may need subscriptions or market is closed)")
                    
                    # Cancel market data
                    ib.cancelMktData(ticker)
                else:
                    print("   ❌ Could not qualify SPY contract")
                
                return True
                
            except AttributeError as ae:
                print(f"   ⚠️  Some attributes not available: {ae}")
                print("   But connection is working!")
                return True
                
        except asyncio.TimeoutError:
            print(f"   ⏱️  Connection timed out after {CONNECTION_TIMEOUT} seconds")
            
        except ConnectionRefusedError:
            print(f"   🚫 Connection refused on {host}:{port}")
            
        except Exception as e:
            print(f"   ❌ Connection failed: {e}")
            
            # For specific error messages, provide guidance
            if "Couldn't connect to engine" in str(e):
                print("   ℹ️  Gateway may not be accepting connections on this address")
            elif "getaddrinfo failed" in str(e):
                print(f"   ℹ️  Cannot resolve {host} - network configuration issue")
        
        finally:
            if ib.isConnected():
                ib.disconnect()
                await asyncio.sleep(1)
    
    print("\n❌ All connection attempts failed")
    return False

# ==============================================================================
# PRE-CONNECTION DIAGNOSTICS
# ==============================================================================
def run_pre_connection_diagnostics():
    """Run diagnostics before attempting connection"""
    print("\n🔍 Pre-Connection Diagnostics")
    print("=" * 50)
    
    # Check if IB Gateway is running
    print("\n1. Checking for IB Gateway processes...")
    try:
        ps_result = subprocess.run(
            ['pgrep', '-f', 'ibgateway|tws|1039'],
            capture_output=True,
            text=True
        )
        
        if ps_result.returncode == 0 and ps_result.stdout.strip():
            pids = ps_result.stdout.strip().split('\n')
            print(f"   ✅ Found {len(pids)} IB Gateway process(es): PIDs {', '.join(pids)}")
        else:
            print("   ❌ No IB Gateway processes found")
            print("   Solution: Start IB Gateway first")
            return False
    except:
        pass
    
    # Check listening ports
    print("\n2. Checking listening ports...")
    
    paper_listening = detect_listening_addresses(PAPER_TRADING_PORT)
    live_listening = detect_listening_addresses(LIVE_TRADING_PORT)
    
    if not (paper_listening['ipv4'] or paper_listening['ipv6'] or 
            live_listening['ipv4'] or live_listening['ipv6']):
        print(f"   ❌ No ports listening on {PAPER_TRADING_PORT} or {LIVE_TRADING_PORT}")
        print("   Solution: Configure API settings in IB Gateway")
        return False
    
    # Test raw socket connections
    print("\n3. Testing raw socket connections...")
    
    if paper_listening['ipv6']:
        # Try IPv6 first if available
        if test_raw_socket_connection('::1', PAPER_TRADING_PORT):
            print("   ℹ️  IPv6 connection works - will try IPv6 for IB API")
        elif test_raw_socket_connection('127.0.0.1', PAPER_TRADING_PORT):
            print("   ℹ️  IPv4 connection works via IPv6 socket")
    elif paper_listening['ipv4']:
        if test_raw_socket_connection('127.0.0.1', PAPER_TRADING_PORT):
            print("   ℹ️  IPv4 connection works")
    
    return True

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
async def main():
    """Main test execution"""
    print("🚀 SPYDER IB Gateway Connection Test")
    print("=" * 50)
    print(f"Master Client ID: {MASTER_CLIENT_ID}")
    print(f"Primary Port: {PAPER_TRADING_PORT} (Paper Trading)")
    print(f"Secondary Port: {LIVE_TRADING_PORT} (Live Trading)")
    
    # Run pre-connection diagnostics
    if not run_pre_connection_diagnostics():
        print("\n❌ Pre-connection checks failed. Fix issues before continuing.")
        return False
    
    # Run connection test
    print("\n" + "=" * 50)
    print("🔌 Starting IB API Connection Test")
    print("=" * 50)
    
    success = await test_basic_connection()
    
    if success:
        print("\n" + "=" * 50)
        print("🎉 CONNECTION TEST PASSED!")
        print("=" * 50)
        print("\nYour IB Gateway connection is working correctly!")
        print(f"\nConnection Configuration:")
        print(f"  • Host: 127.0.0.1 or ::1 (IPv6)")
        print(f"  • Port: {PAPER_TRADING_PORT} (Paper) or {LIVE_TRADING_PORT} (Live)")
        print(f"  • Client ID: {MASTER_CLIENT_ID}")
        print(f"\nYou can now run the Spyder trading system!")
    else:
        print("\n" + "=" * 50)
        print("❌ CONNECTION TEST FAILED")
        print("=" * 50)
        print("\nTroubleshooting steps:")
        print("\n1. Check IB Gateway is running and logged in")
        print("\n2. Verify API Settings in IB Gateway:")
        print("   • Configure -> Settings -> API -> Settings")
        print("   • Enable ActiveX and Socket Clients: ✓")
        print(f"   • Socket port: {PAPER_TRADING_PORT}")
        print(f"   • Master Client ID: {MASTER_CLIENT_ID}")
        print("   • Read-Only API: ☐ (unchecked)")
        print("   • Trusted IP Addresses: 127.0.0.1")
        print("\n3. Apply and restart Gateway")
        print("\n4. Check firewall:")
        print("   • sudo ufw status")
        print(f"   • sudo ufw allow {PAPER_TRADING_PORT}/tcp")
        print("\n5. For IPv6 issues, try:")
        print("   • Edit /etc/hosts and ensure:")
        print("     127.0.0.1   localhost")
        print("     ::1         localhost ip6-localhost ip6-loopback")
    
    return success

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⏹️  Test cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)