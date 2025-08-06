#!/usr/bin/env python3
"""
Simple IB Gateway Watchdog with Heartbeat (Fixed)
Keeps your IB Gateway connection alive
"""

import asyncio
from datetime import datetime
from ib_async import IB, util

class SimpleWatchdog:
    def __init__(self, port=4002):
        self.ib = IB()
        self.port = port
        self.client_id = 999  # Dedicated watchdog client
        self.running = True
        
    async def connect(self):
        """Connect to IB Gateway"""
        try:
            await self.ib.connectAsync('127.0.0.1', self.port, clientId=self.client_id)
            if self.ib.isConnected():
                print(f"✅ Connected to IB Gateway on port {self.port}")
                return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
        return False
    
    async def heartbeat(self):
        """Send heartbeat to keep connection alive"""
        while self.running:
            try:
                if self.ib.isConnected():
                    # Request server time as heartbeat
                    server_time = await self.ib.reqCurrentTimeAsync()
                    
                    # Handle both datetime and timestamp formats
                    if isinstance(server_time, datetime):
                        server_time_str = server_time.strftime('%H:%M:%S')
                    else:
                        # If it's a timestamp
                        server_time_str = datetime.fromtimestamp(server_time).strftime('%H:%M:%S')
                    
                    print(f"💓 Heartbeat at {datetime.now().strftime('%H:%M:%S')} - Server time: {server_time_str}")
                else:
                    print("⚠️ Connection lost - attempting reconnect...")
                    await self.connect()
                    
                # Wait 2 minutes before next heartbeat
                await asyncio.sleep(120)
                
            except asyncio.CancelledError:
                # Clean exit on Ctrl+C
                break
            except Exception as e:
                print(f"❌ Heartbeat error: {e}")
                await asyncio.sleep(10)
    
    async def run(self):
        """Run the watchdog"""
        print("\n" + "="*60)
        print("🐕 IB GATEWAY WATCHDOG STARTED")
        print("="*60)
        print(f"Port: {self.port} (Paper Trading)")
        print("Heartbeat: Every 2 minutes")
        print("Press Ctrl+C to stop")
        print("="*60 + "\n")
        
        # Connect
        connected = await self.connect()
        if not connected:
            print("Failed to connect. Please check IB Gateway is running.")
            return
        
        # Start heartbeat
        try:
            await self.heartbeat()
        except KeyboardInterrupt:
            print("\n🛑 Watchdog stopped by user")
        finally:
            self.running = False
            if self.ib.isConnected():
                self.ib.disconnect()
            print("✅ Watchdog shutdown complete")

# Run the watchdog
if __name__ == "__main__":
    watchdog = SimpleWatchdog(port=4002)
    try:
        asyncio.run(watchdog.run())
    except KeyboardInterrupt:
        print("\nShutdown initiated...")
