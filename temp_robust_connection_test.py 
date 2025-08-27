#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROBUST IB GATEWAY CONNECTION TEST

SPYDER - Autonomous Options Trading System v1.0

Module: temp_robust_connection_test.py
Purpose: Robust IB Gateway connection testing with automatic client ID detection
Author: Mohamed Talib  
Date Created: 2025-08-27
Last Updated: 2025-08-27 Time: 14:45:00

Module Description:
    This script provides a robust method to connect to IB Gateway by automatically
    finding available client IDs, handling connection errors gracefully, and 
    providing detailed feedback about the connection process.

"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import time
import sys
from typing import Optional, List, Dict, Any

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    from ib_insync import IB
    HAS_IB_ASYNC = True
except ImportError:
    print("❌ ib_insync not available. Install with: pip install ib_insync")
    HAS_IB_ASYNC = False
    sys.exit(1)

# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_HOST = "127.0.0.1"
PAPER_PORT = 4002
LIVE_PORT = 4001
CLIENT_ID_RANGE = range(1, 32)  # IB supports 1-31
CONNECTION_TIMEOUT = 30

# ==============================================================================
# CONNECTION FUNCTIONS
# ==============================================================================

async def test_single_connection(host: str, port: int, client_id: int, timeout: int = 30) -> Dict[str, Any]:
    """
    Test connection with specific parameters.
    
    Args:
        host: Gateway host
        port: Gateway port
        client_id: Client ID to use
        timeout: Connection timeout
        
    Returns:
        Connection result details
    """
    result = {
        'client_id': client_id,
        'success': False,
        'error': None,
        'server_version': None,
        'connection_time': None,
        'account_summary': None
    }
    
    ib = IB()
    
    try:
        print(f"🔗 Attempting connection - Host: {host}, Port: {port}, Client ID: {client_id}")
        
        # Attempt connection
        await ib.connectAsync(host, port, clientId=client_id, timeout=timeout)
        
        if ib.isConnected():
            print("✅ Connection established!")
            
            result['success'] = True
            result['server_version'] = ib.serverVersion()
            result['connection_time'] = ib.reqCurrentTime()
            
            # Get basic account info
            try:
                account_summary = ib.reqAccountSummary(
                    1, "All", "$LEDGER:USD"
                )
                await asyncio.sleep(2)  # Wait for data
                
                if account_summary:
                    result['account_summary'] = {
                        'account': account_summary[0].account,
                        'currency': account_summary[0].currency,
                        'value': account_summary[0].value
                    }
            except Exception as e:
                print(f"⚠️ Could not get account summary: {e}")
            
            print(f"📊 Server Version: {result['server_version']}")
            print(f"🕒 Connection Time: {result['connection_time']}")
            
            if result['account_summary']:
                acc = result['account_summary']
                print(f"💰 Account: {acc['account']} ({acc['currency']})")
        else:
            result['error'] = "Connection failed without exception"
            print("❌ Connection failed without specific error")
            
    except Exception as e:
        result['error'] = str(e)
        print(f"❌ Connection failed: {e}")
    
    finally:
        if ib.isConnected():
            ib.disconnect()
            print("🔌 Disconnected")
    
    return result

async def find_and_connect(host: str, port: int, timeout: int = 30) -> Optional[Dict[str, Any]]:
    """
    Find available client ID and establish connection.
    
    Args:
        host: Gateway host
        port: Gateway port  
        timeout: Connection timeout
        
    Returns:
        Connection details if successful, None otherwise
    """
    print(f"🔍 Searching for available client ID on {host}:{port}")
    print("-" * 50)
    
    for client_id in CLIENT_ID_RANGE:
        print(f"\n🧪 Testing client ID {client_id}...")
        
        result = await test_single_connection(host, port, client_id, timeout)
        
        if result['success']:
            print(f"🎉 SUCCESS! Found working client ID: {client_id}")
            return result
        else:
            error_msg = result['error']
            
            # Classify error types
            if "clientId" in error_msg and "already in use" in error_msg:
                print(f"⚠️ Client ID {client_id} is already in use")
            elif "TimeoutError" in error_msg or "timeout" in error_msg.lower():
                print(f"⏱️ Connection timeout with client ID {client_id}")
            elif "refused" in error_msg.lower():
                print(f"🚫 Connection refused - Gateway might not be running")
                print("💡 Please start IB Gateway first")
                return None
            else:
                print(f"❌ Error with client ID {client_id}: {error_msg}")
    
    print("\n😞 No available client IDs found")
    return None

async def comprehensive_connection_test() -> None:
    """Run comprehensive connection testing."""
    print("🕷️ SPYDER - IB Gateway Robust Connection Test")
    print("=" * 60)
    
    # Test paper trading first (port 4002)
    print("\n📝 Testing Paper Trading Connection (Port 4002)")
    paper_result = await find_and_connect(DEFAULT_HOST, PAPER_PORT)
    
    if paper_result:
        print(f"\n✅ PAPER TRADING CONNECTION SUCCESSFUL")
        print(f"🔧 Use these settings for your Spyder configuration:")
        print(f"   Host: {DEFAULT_HOST}")
        print(f"   Port: {PAPER_PORT}")  
        print(f"   Client ID: {paper_result['client_id']}")
        print(f"   Server Version: {paper_result['server_version']}")
        
        # Generate configuration code
        print(f"\n📝 Python connection code:")
        print(f"""
from ib_async import IB
import asyncio

async def connect_to_ib():
    ib = IB()
    try:
        await ib.connectAsync('{DEFAULT_HOST}', {PAPER_PORT}, clientId={paper_result['client_id']}, timeout=60)
        print("✅ Connected to IB Gateway")
        return ib
    except Exception as e:
        print(f"❌ Connection failed: {{e}}")
        return None

# Usage
ib = asyncio.run(connect_to_ib())
""")
        
        return
    
    # If paper trading failed, test live trading (port 4001)
    print("\n📈 Paper trading failed, testing Live Trading Connection (Port 4001)")
    live_result = await find_and_connect(DEFAULT_HOST, LIVE_PORT)
    
    if live_result:
        print(f"\n✅ LIVE TRADING CONNECTION SUCCESSFUL")
        print(f"🔧 Use these settings for your Spyder configuration:")
        print(f"   Host: {DEFAULT_HOST}")
        print(f"   Port: {LIVE_PORT}")
        print(f"   Client ID: {live_result['client_id']}")
        print(f"   Server Version: {live_result['server_version']}")
        
        print(f"\n⚠️  WARNING: This is connecting to LIVE trading!")
        print(f"   Make sure you want to use live trading before proceeding.")
        
    else:
        # Both failed - provide troubleshooting
        print("\n❌ BOTH CONNECTIONS FAILED")
        print("\n🔧 TROUBLESHOOTING STEPS:")
        print("1. Check if IB Gateway is running:")
        print("   - Look for 'IB Gateway' in your system processes")
        print("   - Check system tray for Gateway icon")
        
        print("\n2. Verify Gateway Configuration:")
        print("   - API should be enabled")
        print("   - Socket port should be 4002 (paper) or 4001 (live)")
        print("   - 'Create API message log file' can be helpful for debugging")
        
        print("\n3. Check firewall/network:")
        print("   - Ensure localhost connections are allowed")
        print("   - Try disabling firewall temporarily")
        
        print("\n4. Gateway restart:")
        print("   - Close IB Gateway completely")
        print("   - Wait 30 seconds")
        print("   - Restart Gateway")
        print("   - Wait for full startup (1-2 minutes)")
        
        print("\n5. Run diagnostics:")
        print("   - Run temp_connection_diagnostics.py for detailed analysis")

# ==============================================================================
# QUICK TEST FUNCTIONS  
# ==============================================================================

async def quick_test(client_id: int = None) -> bool:
    """
    Quick connection test with specific or auto-detected client ID.
    
    Args:
        client_id: Specific client ID to test, None for auto-detect
        
    Returns:
        True if connection successful
    """
    print("⚡ Quick Connection Test")
    print("-" * 30)
    
    if client_id:
        print(f"Testing specific client ID: {client_id}")
        result = await test_single_connection(DEFAULT_HOST, PAPER_PORT, client_id)
        return result['success']
    else:
        print("Auto-detecting client ID...")
        result = await find_and_connect(DEFAULT_HOST, PAPER_PORT, 15)
        return result is not None

async def batch_test_client_ids(client_ids: List[int]) -> Dict[int, bool]:
    """
    Test multiple client IDs quickly.
    
    Args:
        client_ids: List of client IDs to test
        
    Returns:
        Dictionary mapping client ID to success status
    """
    results = {}
    
    print(f"🧪 Testing {len(client_ids)} client IDs...")
    
    for client_id in client_ids:
        print(f"Testing {client_id}...", end=" ")
        result = await test_single_connection(DEFAULT_HOST, PAPER_PORT, client_id, 10)
        results[client_id] = result['success']
        print("✅" if result['success'] else "❌")
    
    return results

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Robust IB Gateway Connection Test")
    parser.add_argument("--client-id", type=int, help="Test specific client ID")
    parser.add_argument("--quick", action="store_true", help="Quick test mode")
    parser.add_argument("--batch", nargs="+", type=int, help="Test multiple client IDs")
    
    args = parser.parse_args()
    
    if args.quick:
        # Quick test mode
        success = asyncio.run(quick_test(args.client_id))
        sys.exit(0 if success else 1)
        
    elif args.batch:
        # Batch test mode
        results = asyncio.run(batch_test_client_ids(args.batch))
        successful = [cid for cid, success in results.items() if success]
        
        print(f"\n✅ Successful client IDs: {successful}")
        print(f"❌ Failed client IDs: {[cid for cid, success in results.items() if not success]}")
        
        sys.exit(0 if successful else 1)
        
    else:
        # Full comprehensive test
        asyncio.run(comprehensive_connection_test())
