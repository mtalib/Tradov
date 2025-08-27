#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ADVANCED IB GATEWAY CONNECTION TEST WITH EXPLICIT HANDSHAKE

SPYDER - Autonomous Options Trading System v1.0

Module: temp_advanced_connection_test.py  
Purpose: Advanced connection test with nest_asyncio and explicit handshake handling
Author: Mohamed Talib
Date Created: 2025-08-27
Last Updated: 2025-08-27 Time: 16:15:00

Module Description:
    This module uses nest_asyncio for better async handling and implements
    explicit handshake management for more reliable IB Gateway connections.
    It provides step-by-step connection diagnostics and manual handshake control.

"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import sys
import time
import socket
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime

# ==============================================================================
# THIRD-PARTY IMPORTS  
# ==============================================================================
try:
    import nest_asyncio
    nest_asyncio.apply()  # Allow nested event loops
    HAS_NEST_ASYNCIO = True
except ImportError:
    print("⚠️ nest_asyncio not available. Install with: pip install nest-asyncio")
    HAS_NEST_ASYNCIO = False

try:
    from ib_async import IB, util
    from ib_async.client import Client
    from ib_async.wrapper import Wrapper
    HAS_IB_ASYNC = True
except ImportError:
    print("❌ ib_async not available. Install with: pip install ib_async")
    HAS_IB_ASYNC = False
    sys.exit(1)

# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_HOST = "127.0.0.1"
PAPER_PORT = 4002
LIVE_PORT = 4001
CLIENT_ID_RANGE = range(1, 10)  # Test first 10 client IDs

# Connection timeouts (in seconds)
SOCKET_TIMEOUT = 10
HANDSHAKE_TIMEOUT = 15
API_TIMEOUT = 20

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==============================================================================
# EXPLICIT HANDSHAKE CONNECTION CLASS
# ==============================================================================

class ExplicitIBConnection:
    """
    IB Connection with explicit handshake handling.
    
    This class provides manual control over the IB API connection process,
    including socket connection, handshake, and authentication phases.
    """
    
    def __init__(self, host: str = DEFAULT_HOST, port: int = PAPER_PORT):
        """Initialize connection manager."""
        self.host = host
        self.port = port
        self.ib = None
        self.client = None
        self.wrapper = None
        self.connected = False
        
    async def test_socket_connectivity(self) -> Dict[str, Any]:
        """
        Test raw socket connectivity before attempting API connection.
        
        Returns:
            Socket test results
        """
        result = {
            'success': False,
            'error': None,
            'response_time': None
        }
        
        try:
            start_time = time.time()
            
            # Create socket connection
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(SOCKET_TIMEOUT)
            
            # Test connection
            conn_result = sock.connect_ex((self.host, self.port))
            
            if conn_result == 0:
                result['success'] = True
                result['response_time'] = time.time() - start_time
                
                # Try to send/receive basic data
                try:
                    # Send a simple test byte
                    sock.send(b'\x00')
                    sock.settimeout(1)  # Short timeout for response
                    response = sock.recv(1024)
                    result['response_data'] = len(response)
                except socket.timeout:
                    result['response_data'] = 0  # No response but connection works
                except Exception as e:
                    result['socket_error'] = str(e)
            else:
                result['error'] = f"Connection refused (code: {conn_result})"
            
            sock.close()
            
        except socket.timeout:
            result['error'] = "Socket timeout"
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    async def connect_with_explicit_handshake(self, client_id: int, timeout: int = API_TIMEOUT) -> Dict[str, Any]:
        """
        Connect to IB Gateway with explicit handshake handling.
        
        Args:
            client_id: Client ID for connection
            timeout: Total connection timeout
            
        Returns:
            Connection attempt results
        """
        result = {
            'client_id': client_id,
            'success': False,
            'error': None,
            'phases': {},
            'server_version': None,
            'connection_time': None
        }
        
        try:
            logger.info(f"🔗 Starting explicit handshake for client ID {client_id}")
            
            # Phase 1: Socket connectivity test
            logger.info("📡 Phase 1: Testing socket connectivity...")
            socket_test = await self.test_socket_connectivity()
            result['phases']['socket_test'] = socket_test
            
            if not socket_test['success']:
                result['error'] = f"Socket test failed: {socket_test['error']}"
                return result
            
            logger.info(f"✅ Socket connectivity OK ({socket_test['response_time']:.3f}s)")
            
            # Phase 2: Create IB instance with custom settings
            logger.info("🤖 Phase 2: Creating IB instance...")
            self.ib = IB()
            
            # Set more permissive timeout settings
            if hasattr(self.ib, 'setTimeout'):
                self.ib.setTimeout(timeout)
            
            result['phases']['ib_created'] = True
            
            # Phase 3: Attempt connection with detailed error handling
            logger.info(f"🔌 Phase 3: Attempting API connection (timeout: {timeout}s)...")
            
            # Use asyncio.wait_for for better timeout control
            try:
                connection_task = self.ib.connectAsync(
                    host=self.host, 
                    port=self.port, 
                    clientId=client_id,
                    timeout=timeout
                )
                
                await asyncio.wait_for(connection_task, timeout=timeout)
                result['phases']['connection_attempted'] = True
                
            except asyncio.TimeoutError:
                result['error'] = f"API connection timeout after {timeout}s"
                result['phases']['connection_timeout'] = True
                return result
            
            # Phase 4: Verify connection and get server info
            logger.info("✅ Phase 4: Verifying connection...")
            
            if self.ib.isConnected():
                self.connected = True
                result['success'] = True
                
                # Get server information
                try:
                    result['server_version'] = self.ib.serverVersion()
                    result['connection_time'] = self.ib.reqCurrentTime()
                    result['phases']['server_info_obtained'] = True
                    
                    logger.info(f"📊 Server version: {result['server_version']}")
                    logger.info(f"🕒 Server time: {result['connection_time']}")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Could not get server info: {e}")
                    result['phases']['server_info_error'] = str(e)
                
                # Test basic API functionality
                try:
                    # Request managed accounts (should work for any account)
                    accounts = self.ib.managedAccounts()
                    result['managed_accounts'] = accounts
                    result['phases']['api_test_passed'] = True
                    logger.info(f"👤 Managed accounts: {accounts}")
                    
                except Exception as e:
                    logger.warning(f"⚠️ API test failed: {e}")
                    result['phases']['api_test_error'] = str(e)
                
            else:
                result['error'] = "Connection established but isConnected() returns False"
                result['phases']['connection_verification_failed'] = True
                
        except Exception as e:
            result['error'] = str(e)
            result['phases']['exception'] = str(e)
            logger.error(f"❌ Connection exception: {e}")
        
        return result
    
    def disconnect(self) -> bool:
        """Disconnect from IB Gateway."""
        try:
            if self.ib and self.ib.isConnected():
                self.ib.disconnect()
                logger.info("🔌 Disconnected from IB Gateway")
                
            self.connected = False
            return True
            
        except Exception as e:
            logger.error(f"❌ Disconnect error: {e}")
            return False

# ==============================================================================
# CONNECTION TESTING FUNCTIONS
# ==============================================================================

async def comprehensive_connection_test() -> Optional[int]:
    """
    Run comprehensive connection test with explicit handshake.
    
    Returns:
        Working client ID or None if all fail
    """
    print("🕷️ SPYDER Advanced IB Gateway Connection Test")
    print("🔧 Using nest_asyncio and explicit handshake handling")
    print("=" * 70)
    
    if not HAS_NEST_ASYNCIO:
        print("⚠️ nest_asyncio not available - may have event loop issues")
    else:
        print("✅ nest_asyncio enabled - nested event loops supported")
    
    connection = ExplicitIBConnection(DEFAULT_HOST, PAPER_PORT)
    
    print(f"\n🎯 Testing connection to {DEFAULT_HOST}:{PAPER_PORT}")
    print("-" * 50)
    
    for client_id in CLIENT_ID_RANGE:
        print(f"\n🧪 Testing Client ID {client_id}")
        print("=" * 30)
        
        result = await connection.connect_with_explicit_handshake(client_id, HANDSHAKE_TIMEOUT)
        
        if result['success']:
            print("🎉 SUCCESS! Connection established")
            print(f"📊 Server Version: {result['server_version']}")
            print(f"🕒 Connection Time: {result['connection_time']}")
            
            if 'managed_accounts' in result:
                print(f"👤 Managed Accounts: {result['managed_accounts']}")
            
            # Disconnect
            connection.disconnect()
            
            print(f"\n✅ WORKING CLIENT ID FOUND: {client_id}")
            print("🎯 Use this client ID for your Spyder configuration!")
            
            return client_id
        
        else:
            print(f"❌ Failed: {result['error']}")
            
            # Show detailed phase information
            phases = result.get('phases', {})
            for phase, status in phases.items():
                if isinstance(status, bool) and status:
                    print(f"   ✅ {phase}")
                elif isinstance(status, str):
                    print(f"   ⚠️ {phase}: {status}")
                else:
                    print(f"   ❌ {phase}")
            
            # Disconnect in case of partial connection
            connection.disconnect()
    
    print("\n😞 No working client IDs found")
    print("\n💡 TROUBLESHOOTING RECOMMENDATIONS:")
    print("1. Ensure IB Gateway API is enabled (Configure → API)")
    print("2. Check Gateway is fully logged in and initialized")
    print("3. Verify socket port is 4002 for paper trading")
    print("4. Restart Gateway after configuration changes")
    
    return None

async def quick_test(client_id: int = 1) -> bool:
    """
    Quick connection test with specific client ID.
    
    Args:
        client_id: Client ID to test
        
    Returns:
        True if successful
    """
    print(f"⚡ Quick Connection Test - Client ID {client_id}")
    print("-" * 40)
    
    connection = ExplicitIBConnection()
    result = await connection.connect_with_explicit_handshake(client_id, 10)
    
    if result['success']:
        print(f"✅ SUCCESS with client ID {client_id}")
        connection.disconnect()
        return True
    else:
        print(f"❌ FAILED: {result['error']}")
        connection.disconnect()
        return False

def generate_working_connection_code(client_id: int) -> str:
    """Generate ready-to-use connection code."""
    return f'''
# WORKING IB GATEWAY CONNECTION CODE FOR SPYDER
# Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

import asyncio
import nest_asyncio
from ib_async import IB

# Enable nested event loops
nest_asyncio.apply()

async def connect_to_ib_gateway():
    """Connect to IB Gateway with working settings."""
    ib = IB()
    
    try:
        # Use the working client ID found by diagnostic
        await ib.connectAsync('127.0.0.1', 4002, clientId={client_id}, timeout=30)
        
        if ib.isConnected():
            print("✅ Connected to IB Gateway")
            print(f"📊 Server version: {{ib.serverVersion()}}")
            print(f"🕒 Connection time: {{ib.reqCurrentTime()}}")
            return ib
        else:
            print("❌ Connection failed")
            return None
            
    except Exception as e:
        print(f"❌ Connection error: {{e}}")
        return None

# Usage example
if __name__ == "__main__":
    ib = asyncio.run(connect_to_ib_gateway())
    
    if ib:
        # Your Spyder code here
        print("🕷️ Ready for Spyder integration!")
        
        # Remember to disconnect when done
        ib.disconnect()
'''

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

async def main():
    """Main execution function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Advanced IB Gateway Connection Test")
    parser.add_argument("--quick", action="store_true", help="Quick test with client ID 1")
    parser.add_argument("--client-id", type=int, help="Test specific client ID")
    
    args = parser.parse_args()
    
    if args.quick or args.client_id:
        # Quick test mode
        client_id = args.client_id or 1
        success = await quick_test(client_id)
        
        if success:
            print("\n" + "=" * 50)
            print("📝 READY-TO-USE CONNECTION CODE:")
            print("=" * 50)
            print(generate_working_connection_code(client_id))
            
        sys.exit(0 if success else 1)
    else:
        # Comprehensive test
        working_client_id = await comprehensive_connection_test()
        
        if working_client_id:
            print("\n" + "=" * 70)
            print("🎉 CONNECTION SUCCESSFUL!")
            print("=" * 70)
            print(generate_working_connection_code(working_client_id))
            
            sys.exit(0)
        else:
            sys.exit(1)

if __name__ == "__main__":
    # Ensure nest_asyncio is applied
    if HAS_NEST_ASYNCIO:
        nest_asyncio.apply()
    
    # Run the main function
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
        sys.exit(1)
