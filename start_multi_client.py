#!/usr/bin/env python3
"""Start Multi-Client IB Gateway Connections"""

import sys
import os
import asyncio
import logging
from ib_insync import IB, Stock, util
from datetime import datetime
import time

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add to path
sys.path.insert(0, '/home/adam/Projects/Spyder')

# Client configuration
CLIENT_CONFIG = [
    (0, "Admin", "CRITICAL"),
    (1, "Orders", "CRITICAL"),
    (2, "Core Data", "CRITICAL"),
    (3, "SPY Options", "CRITICAL"),
    (4, "Volatility", "HIGH"),
    (5, "Internals", "HIGH"),
    (6, "Indices", "HIGH"),
    (7, "Extended", "MEDIUM"),
    (8, "Sectors", "LOW")
]

async def main():
    """Main entry point for multi-client connection"""
    
    print("="*80)
    print("🚀 SPYDER MULTI-CLIENT IB GATEWAY CONNECTION")
    print("="*80)
    print(f"📅 {datetime.now()}")
    print(f"📊 Mode: PAPER TRADING")
    print(f"🌐 Gateway: localhost:4002")
    print("="*80)
    
    clients = {}
    
    # Connect all clients
    print("\n🔌 Connecting clients...")
    for client_id, name, priority in CLIENT_CONFIG:
        try:
            print(f"  Client {client_id} ({name:12}) [{priority:8}]...", end="")
            ib = IB()
            await ib.connectAsync('127.0.0.1', 4002, clientId=client_id)
            clients[client_id] = {'ib': ib, 'name': name, 'priority': priority}
            print(" ✅")
            
            # Small delay between connections
            await asyncio.sleep(0.5)
            
        except Exception as e:
            print(f" ❌ Failed: {e}")
    
    print(f"\n✅ Successfully connected {len(clients)}/{len(CLIENT_CONFIG)} clients!")
    
    # Show connected clients
    print("\n📊 Connected Clients:")
    for client_id, info in clients.items():
        if info['ib'].isConnected():
            print(f"  ✅ Client {client_id}: {info['name']}")
    
    # Test data subscriptions
    print("\n📈 Testing market data subscriptions...")
    
    # Client 2 (Core Data) subscribes to SPY
    if 2 in clients:
        try:
            spy = Stock('SPY', 'SMART', 'USD')
            await clients[2]['ib'].qualifyContractsAsync(spy)
            ticker = clients[2]['ib'].reqMktData(spy)
            await asyncio.sleep(2)
            print(f"  SPY (Client 2): Bid={ticker.bid}, Ask={ticker.ask}, Last={ticker.last}")
        except Exception as e:
            print(f"  SPY data error: {e}")
    
    # Keep running and monitor
    print("\n📊 System running. Press Ctrl+C to stop...")
    print("⚡ Monitoring connections...\n")
    
    try:
        while True:
            # Check connections
            active = sum(1 for c in clients.values() if c['ib'].isConnected())
            status_line = f"⚡ Active: {active}/{len(CLIENT_CONFIG)} |"
            
            # Show status for each client
            for client_id in range(9):
                if client_id in clients and clients[client_id]['ib'].isConnected():
                    status_line += f" {client_id}:✅"
                else:
                    status_line += f" {client_id}:❌"
            
            print(f"\r{status_line}", end="")
            await asyncio.sleep(5)
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Shutting down...")
        
    finally:
        # Disconnect all clients
        print("\n🔌 Disconnecting all clients...")
        for client_id, info in clients.items():
            if info['ib'].isConnected():
                info['ib'].disconnect()
                print(f"  Client {client_id} ({info['name']}) disconnected")
        print("✅ All clients disconnected")

if __name__ == "__main__":
    util.startLoop()
    asyncio.run(main())
