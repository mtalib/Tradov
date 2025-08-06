#!/usr/bin/env python3
"""
Working IB Gateway Watchdog
Handles datetime objects correctly
"""

import asyncio
from datetime import datetime
from ib_async import IB, util

class WorkingWatchdog:
    def __init__(self, port=4002, test_mode=True):
        self.ib = IB()
        self.port = port
        self.client_id = 999  # Dedicated watchdog client
        self.running = True
        self.test_mode = test_mode  # Start with frequent heartbeats
        self.heartbeat_count = 0
        
    async def connect(self):
        """Connect to IB Gateway"""
        try:
            await self.ib.connectAsync('127.0.0.1', self.port, clientId=self.client_id)
            if self.ib.isConnected():
                print(f"✅ Connected to IB Gateway on port {self.port}")
                accounts = self.ib.managedAccounts()
                print(f"📊 Account: {accounts[0] if accounts else 'None'}")
                return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
        return False
    
    async def send_heartbeat(self):
        """Send heartbeat and return success status"""
        try:
            # Request server time as heartbeat
            server_time = await self.ib.reqCurrentTimeAsync()
            self.heartbeat_count += 1
            
            # Extract time from datetime object
            server_time_str = server_time.strftime('%H:%M:%S %Z')
            local_time_str = datetime.now().strftime('%H:%M:%S')
            
            print(f"💓 Heartbeat #{self.heartbeat_count} | Local: {local_time_str} | Server: {server_time_str} | ✅ Connected")
            return True
            
        except Exception as e:
            print(f"❌ Heartbeat failed: {e}")
            return False
    
    async def heartbeat_loop(self):
        """Send heartbeats at regular intervals"""
        while self.running:
            try:
                if self.ib.isConnected():
                    success = await self.send_heartbeat()
                    if not success:
                        print("⚠️ Heartbeat failed - connection may be lost")
                else:
                    print("⚠️ Connection lost - attempting reconnect...")
                    await self.connect()
                
                # Determine interval
                if self.test_mode and self.heartbeat_count < 5:
                    interval = 10  # 10 seconds for testing
                    print(f"   Next heartbeat in {interval} seconds...")
                else:
                    if self.test_mode and self.heartbeat_count == 5:
                        print("   ✅ Test complete! Switching to 2-minute intervals")
                        self.test_mode = False
                    interval = 120  # 2 minutes normal operation
                    print(f"   Next heartbeat in {interval//60} minutes...")
                
                # Wait
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"❌ Loop error: {e}")
                await asyncio.sleep(10)
    
    async def run(self):
        """Run the watchdog"""
        print("\n" + "="*60)
        print("🐕 IB GATEWAY WATCHDOG")
        print("="*60)
        print(f"Port: {self.port} (Paper Trading)")
        print("Test Mode: First 5 heartbeats every 10 seconds")
        print("Normal Mode: Heartbeat every 2 minutes")
        print("Press Ctrl+C to stop")
        print("="*60 + "\n")
        
        # Connect
        connected = await self.connect()
        if not connected:
            print("Failed to connect. Please check IB Gateway is running.")
            return
        
        print("")  # Blank line for clarity
        
        # Start heartbeat
        try:
            await self.heartbeat_loop()
        except KeyboardInterrupt:
            print("\n🛑 Watchdog stopped by user")
        finally:
            self.running = False
            if self.ib.isConnected():
                self.ib.disconnect()
                print("✅ Disconnected from IB Gateway")

async def main():
    """Run the watchdog"""
    watchdog = WorkingWatchdog(port=4002, test_mode=True)
    await watchdog.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n✅ Watchdog shutdown complete")
