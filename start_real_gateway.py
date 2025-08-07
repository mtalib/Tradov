#!/usr/bin/env python3
"""Start Gateway Integration with REAL IB connection"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv
import asyncio
import logging
from ib_insync import IB, util  # <-- Added util import here

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add to path
sys.path.insert(0, '/home/adam/Projects/Spyder')

# Load environment
load_dotenv()

async def main():
    """Main entry point for real gateway connection"""
    
    # Import after path setup
    from SpyderB_Broker.SpyderB13_GatewayConfig import GatewayConfig, TradingMode
    from SpyderB_Broker.SpyderB14_MultiClientWatchdog import MultiClientWatchdog
    
    print("="*80)
    print("🚀 SPYDER IB GATEWAY - REAL CONNECTION MODE")
    print("="*80)
    print(f"📊 Mode: PAPER TRADING")
    print(f"🌐 Gateway: localhost:4002")
    print("="*80)
    
    # Create configuration
    config = GatewayConfig(
        trading_mode=TradingMode.PAPER,
        ib_gateway_host='127.0.0.1',
        ib_gateway_paper_port=4002
    )
    
    # Create watchdog
    watchdog = MultiClientWatchdog(config)
    
    # Test connection with Client 0 (Admin)
    print("\n🔌 Connecting Client 0 (Admin)...")
    ib_admin = IB()
    
    try:
        # Connect admin client
        await ib_admin.connectAsync('127.0.0.1', 4002, clientId=0)
        print("✅ Client 0 connected successfully!")
        
        # Get account info
        account = ib_admin.accountSummary()
        if account:
            print(f"📊 Account data: {len(account)} items received")
            
        # Test other clients
        print("\n🔌 Testing multi-client connections...")
        
        clients = {}
        for client_id in range(1, 9):
            try:
                print(f"  Connecting Client {client_id}...", end="")
                ib = IB()
                await ib.connectAsync('127.0.0.1', 4002, clientId=client_id)
                clients[client_id] = ib
                print(" ✅")
                await asyncio.sleep(0.5)  # Small delay between connections
            except Exception as e:
                print(f" ❌ Failed: {e}")
        
        print(f"\n✅ Successfully connected {len(clients) + 1} clients!")
        
        # Keep running for monitoring
        print("\n📊 System running. Press Ctrl+C to stop...")
        
        # Monitor loop
        while True:
            try:
                # Check connections
                active = sum(1 for ib in clients.values() if ib.isConnected())
                print(f"\r⚡ Active clients: {active + 1}/9 | Admin: {'✅' if ib_admin.isConnected() else '❌'}", end="")
                await asyncio.sleep(5)
            except KeyboardInterrupt:
                break
                
    except Exception as e:
        print(f"\n❌ Connection failed: {e}")
        print("\nTroubleshooting:")
        print("1. Check IB Gateway is running")
        print("2. Verify API is enabled in Gateway settings")
        print("3. Check Gateway logs for errors")
        print("4. Ensure port 4002 is correct")
        
    finally:
        # Disconnect all
        print("\n\n🔌 Disconnecting all clients...")
        if 'ib_admin' in locals() and ib_admin.isConnected():
            ib_admin.disconnect()
        if 'clients' in locals():
            for client_id, ib in clients.items():
                if ib.isConnected():
                    ib.disconnect()
        print("✅ All clients disconnected")

if __name__ == "__main__":
    # Start the event loop
    util.startLoop()
    asyncio.run(main())
