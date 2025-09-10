#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Tests
Module: temp_multi_client_test.py
Purpose: Test multi-client IB Gateway architecture with Master Client ID
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-09 Time: 14:00:00

Module Description:
    Specialized test for Spyder's multi-client architecture with 11 clients.
    Client 2 is the Master Client ID, Client 1 handles order execution, and
    Clients 3-11 handle various market data feeds. Tests proper connection
    sequence and validates multi-client configuration.

CLIENT ALLOCATION:
    - Client 1: Order Execution (Trading operations)
    - Client 2: Administrative Operations (Master Client - Account, System Control)
    - Client 3: Core Market Data (SPY, SPX, /ES, VIX, TICK-NYSE)
    - Client 4: SPY Options Chains (0DTE, 1DTE)
    - Client 5: Volatility Indicators (VIX9D, VXV, VXMT, VVIX, UVXY)
    - Client 6: Market Internals (TRIN, ADD, CPC, PCALL, SKEW, VUD)
    - Client 7: Major Indices (DIA, QQQ, IWM, 1DTE Options)
    - Client 8: Extended Assets (TLT, LQD, DXY, GLD, WEEKLY Options)
    - Client 9: Sector ETFs (XLF, XLK, XLE, XLV, XLI, XLY, XLP, XLU, XLRE, XLC, XLB)
    - Client 10: International Markets (FTLC, AUD.JPY, DAX, HSI, EWJ)

"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import sys
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    from ib_async import IB, Stock, util
    IB_ASYNC_AVAILABLE = True
except ImportError:
    IB_ASYNC_AVAILABLE = False
    print("❌ ib_async not installed. Install with: pip install ib_async")
    sys.exit(1)

# ==============================================================================
# CLIENT CONFIGURATION
# ==============================================================================
@dataclass
class ClientConfig:
    """Configuration for each client connection"""
    client_id: int
    name: str
    purpose: str
    priority: int  # 1 = highest priority
    update_frequency: str
    symbols: List[str]

# Define all clients
CLIENT_CONFIGS = {
    1: ClientConfig(1, "OrderExecution", "Order Execution", 1, "realtime", []),
    2: ClientConfig(2, "Master", "Administrative Operations (Master)", 2, "realtime", []),
    3: ClientConfig(3, "CoreMarket", "Core Market Data", 3, "1s", ["SPY", "SPX", "ES", "VIX", "TICK-NYSE"]),
    4: ClientConfig(4, "SPYOptions", "SPY Options Chains", 4, "1s", ["SPY Options"]),
    5: ClientConfig(5, "Volatility", "Volatility Indicators", 5, "5s", ["VIX9D", "VXV", "VXMT", "VVIX", "UVXY"]),
    6: ClientConfig(6, "Internals", "Market Internals", 6, "5s", ["TRIN", "ADD", "CPC", "PCALL", "SKEW", "VUD"]),
    7: ClientConfig(7, "Indices", "Major Indices", 7, "5s", ["DIA", "QQQ", "IWM"]),
    8: ClientConfig(8, "Extended", "Extended Assets", 8, "15-30s", ["TLT", "LQD", "DXY", "GLD"]),
    9: ClientConfig(9, "Sectors", "Sector ETFs", 9, "30-60s", ["XLF", "XLK", "XLE", "XLV", "XLI"]),
    10: ClientConfig(10, "International", "International Markets", 10, "30-60s", ["FTLC", "DAX", "EWJ"])
}

MASTER_CLIENT_ID = 2
PAPER_PORT = 4002
LIVE_PORT = 4001

# ==============================================================================
# CONNECTION MANAGER
# ==============================================================================
class MultiClientManager:
    """Manages multiple IB client connections"""
    
    def __init__(self):
        self.clients: Dict[int, IB] = {}
        self.connection_status: Dict[int, bool] = {}
        self.connection_errors: Dict[int, str] = {}
        
    async def connect_master(self, port: int = PAPER_PORT) -> bool:
        """
        Connect the Master Client first (Client 2).
        
        Args:
            port: Port to connect to
            
        Returns:
            True if master connected successfully
        """
        print(f"\n🔑 Connecting MASTER Client (ID: {MASTER_CLIENT_ID})")
        print("=" * 50)
        
        master_ib = IB()
        
        # Try different addresses
        for host in ['127.0.0.1', '::1', 'localhost']:
            try:
                print(f"Attempting connection to {host}:{port}...")
                
                await master_ib.connectAsync(
                    host=host,
                    port=port,
                    clientId=MASTER_CLIENT_ID,
                    timeout=30
                )
                
                print(f"✅ MASTER Client connected via {host}")
                
                # Store master client
                self.clients[MASTER_CLIENT_ID] = master_ib
                self.connection_status[MASTER_CLIENT_ID] = True
                
                # Get account info
                accounts = master_ib.managedAccounts()
                print(f"   Managed accounts: {accounts}")
                
                if hasattr(master_ib.client, 'serverVersion'):
                    print(f"   Server version: {master_ib.client.serverVersion}")
                
                return True
                
            except asyncio.TimeoutError:
                print(f"   ⏱️  Timeout on {host}")
                self.connection_errors[MASTER_CLIENT_ID] = f"Timeout on {host}"
                continue
                
            except Exception as e:
                print(f"   ❌ Error on {host}: {e}")
                self.connection_errors[MASTER_CLIENT_ID] = str(e)
                
                # Check for specific errors
                if "already in use" in str(e).lower():
                    print(f"   ⚠️  Master Client ID {MASTER_CLIENT_ID} is already in use!")
                    print("   Solution: Close other applications using this Client ID")
                    return False
                    
                continue
        
        print(f"❌ Failed to connect MASTER Client")
        self.connection_status[MASTER_CLIENT_ID] = False
        return False
    
    async def connect_client(self, client_id: int, port: int = PAPER_PORT) -> bool:
        """
        Connect a specific client.
        
        Args:
            client_id: Client ID to connect
            port: Port to connect to
            
        Returns:
            True if connected successfully
        """
        if client_id not in CLIENT_CONFIGS:
            print(f"❌ Unknown client ID: {client_id}")
            return False
        
        config = CLIENT_CONFIGS[client_id]
        print(f"\n🔌 Connecting Client {client_id}: {config.name}")
        
        client_ib = IB()
        
        # Use the same host that worked for master
        master_host = '127.0.0.1'  # Default
        if MASTER_CLIENT_ID in self.clients and self.clients[MASTER_CLIENT_ID].isConnected():
            # Try to use same host as master
            master_host = self.clients[MASTER_CLIENT_ID].client.host
        
        try:
            await client_ib.connectAsync(
                host=master_host,
                port=port,
                clientId=client_id,
                timeout=10
            )
            
            print(f"   ✅ Client {client_id} ({config.name}) connected")
            
            self.clients[client_id] = client_ib
            self.connection_status[client_id] = True
            
            return True
            
        except Exception as e:
            error_msg = str(e)
            print(f"   ❌ Client {client_id} failed: {error_msg[:50]}")
            
            self.connection_errors[client_id] = error_msg
            self.connection_status[client_id] = False
            
            if "already in use" in error_msg.lower():
                print(f"   ⚠️  Client ID {client_id} is already in use by another process")
            
            return False
    
    async def connect_all_sequential(self) -> Dict[int, bool]:
        """
        Connect all clients in sequence (Master first, then others).
        
        Returns:
            Dictionary of client_id -> success status
        """
        print("\n🚀 Starting Sequential Multi-Client Connection Test")
        print("=" * 60)
        
        # Step 1: Connect Master
        if not await self.connect_master():
            print("\n❌ Cannot proceed without Master Client")
            return self.connection_status
        
        # Small delay after master connects
        await asyncio.sleep(2)
        
        # Step 2: Connect Order Execution client (highest priority)
        await self.connect_client(1)
        await asyncio.sleep(1)
        
        # Step 3: Connect data clients in priority order
        for client_id in range(3, 11):
            await self.connect_client(client_id)
            await asyncio.sleep(0.5)  # Small delay between connections
        
        return self.connection_status
    
    async def test_client_functionality(self, client_id: int) -> bool:
        """
        Test basic functionality of a connected client.
        
        Args:
            client_id: Client ID to test
            
        Returns:
            True if client is functional
        """
        if client_id not in self.clients or not self.clients[client_id].isConnected():
            return False
        
        config = CLIENT_CONFIGS.get(client_id)
        if not config:
            return False
        
        print(f"\n🧪 Testing Client {client_id} ({config.name})...")
        
        ib = self.clients[client_id]
        
        try:
            # Test based on client purpose
            if client_id == 1:  # Order Execution
                print("   Testing order capabilities...")
                # Just check if we can create an order (not submit)
                from ib_async import MarketOrder
                test_order = MarketOrder('BUY', 100)
                print(f"   ✅ Order object created: {test_order}")
                
            elif client_id == 2:  # Master
                print("   Testing administrative functions...")
                accounts = ib.managedAccounts()
                print(f"   ✅ Can access accounts: {accounts}")
                
            elif client_id in [3, 4, 5, 6, 7, 8, 9, 10]:  # Data clients
                print(f"   Testing market data for {config.symbols[0] if config.symbols else 'SPY'}...")
                
                # Test with SPY as a standard contract
                spy = Stock('SPY', 'SMART', 'USD')
                qualified = await ib.qualifyContractsAsync(spy)
                
                if qualified:
                    print(f"   ✅ Can qualify contracts: {qualified[0]}")
                    
                    # Request snapshot
                    ticker = ib.reqMktData(qualified[0], '', snapshot=True)
                    await asyncio.sleep(2)
                    
                    if ticker.bid or ticker.ask or ticker.last:
                        print(f"   ✅ Can receive market data")
                    else:
                        print(f"   ⚠️  No market data (market may be closed)")
                    
                    ib.cancelMktData(ticker)
                else:
                    print(f"   ❌ Cannot qualify contracts")
                    return False
            
            return True
            
        except Exception as e:
            print(f"   ❌ Functionality test failed: {e}")
            return False
    
    async def disconnect_all(self):
        """Disconnect all clients"""
        print("\n🔌 Disconnecting all clients...")
        
        # Disconnect in reverse order (data clients first, master last)
        for client_id in sorted(self.clients.keys(), reverse=True):
            if self.clients[client_id].isConnected():
                print(f"   Disconnecting Client {client_id}...")
                self.clients[client_id].disconnect()
                await asyncio.sleep(0.5)
    
    def print_summary(self):
        """Print connection summary"""
        print("\n" + "=" * 60)
        print("📊 MULTI-CLIENT CONNECTION SUMMARY")
        print("=" * 60)
        
        connected = sum(1 for status in self.connection_status.values() if status)
        total = len(CLIENT_CONFIGS)
        
        print(f"Connected: {connected}/{total} clients")
        print()
        
        for client_id, config in CLIENT_CONFIGS.items():
            status = self.connection_status.get(client_id, False)
            icon = "✅" if status else "❌"
            
            print(f"{icon} Client {client_id:2d}: {config.name:15s} - {config.purpose}")
            
            if not status and client_id in self.connection_errors:
                print(f"            Error: {self.connection_errors[client_id][:60]}")
        
        return connected, total

# ==============================================================================
# CONFIGURATION GUIDANCE
# ==============================================================================
def print_multi_client_configuration():
    """Print configuration guidance for multi-client setup"""
    print("\n" + "=" * 60)
    print("📋 IB GATEWAY MULTI-CLIENT CONFIGURATION")
    print("=" * 60)
    
    print("""
For Multi-Client Architecture:

1. IB Gateway API Settings (Configure -> Settings -> API -> Settings):
   
   ✅ Enable ActiveX and Socket Clients = CHECKED
   
   Socket port = 4002 (Paper) or 4001 (Live)
   
   Master Client ID = 2
   (This is your administrative client)
   
   ✅ Allow connections from localhost only = CHECKED
   
   Trusted IP Addresses (BOTH lines):
   127.0.0.1
   ::1
   
   ⬜ Read-Only API = UNCHECKED (for trading)

2. Important Notes:
   • Master Client (2) should connect FIRST
   • Other clients connect after Master is established
   • Each client ID must be unique across all applications
   • Maximum concurrent connections depends on your subscription

3. If Connection Fails:
   • Check no other application is using these Client IDs
   • Restart IB Gateway after configuration changes
   • Enable API message log to see connection attempts
   • Ensure you're logged into IB Gateway

4. Client ID Allocation:
   • Client 1: Order execution (critical)
   • Client 2: Master/Admin (must connect first)
   • Clients 3-10: Market data (can reconnect if needed)
""")

# ==============================================================================
# MAIN TEST EXECUTION
# ==============================================================================
async def main():
    """Main test execution"""
    print("🕷️ SPYDER Multi-Client Architecture Test")
    print("=" * 60)
    print(f"Master Client ID: {MASTER_CLIENT_ID}")
    print(f"Total Clients: {len(CLIENT_CONFIGS)}")
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Print client allocation
    print("\n📋 Client Allocation:")
    for client_id, config in CLIENT_CONFIGS.items():
        print(f"   Client {client_id:2d}: {config.purpose}")
    
    # Create manager
    manager = MultiClientManager()
    
    try:
        # Test sequential connection
        print("\n" + "=" * 60)
        print("TEST 1: Sequential Connection (Master First)")
        print("=" * 60)
        
        results = await manager.connect_all_sequential()
        
        # Print summary
        connected, total = manager.print_summary()
        
        # If master connected, test functionality
        if manager.connection_status.get(MASTER_CLIENT_ID, False):
            print("\n" + "=" * 60)
            print("TEST 2: Client Functionality Tests")
            print("=" * 60)
            
            for client_id in [2, 1, 3]:  # Test Master, Order, and one data client
                if client_id in manager.clients:
                    await manager.test_client_functionality(client_id)
        
        # Show configuration guidance if not all connected
        if connected < total:
            print_multi_client_configuration()
        
        # Final result
        print("\n" + "=" * 60)
        if connected == total:
            print("🎉 SUCCESS: All clients connected!")
            print("Your multi-client architecture is working correctly!")
        elif connected > 0:
            print(f"⚠️  PARTIAL SUCCESS: {connected}/{total} clients connected")
            print("Check configuration for failed clients")
        else:
            print("❌ FAILURE: No clients could connect")
            print("Check IB Gateway API configuration")
        print("=" * 60)
        
        return connected > 0
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Cleanup
        await manager.disconnect_all()

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⏹️  Test cancelled by user")
        sys.exit(1)