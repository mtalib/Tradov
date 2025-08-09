#!/usr/bin/env python3
"""
Production IB Gateway Watchdog
Minimal, reliable heartbeat service
"""

import asyncio
import logging
from datetime import datetime
from ib_async import IB

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ib_watchdog.log'),
        logging.StreamHandler()
    ]
)

class IBGatewayWatchdog:
    def __init__(self, port=4002, client_id=999, heartbeat_interval=120):
        self.ib = IB()
        self.port = port
        self.client_id = client_id
        self.heartbeat_interval = heartbeat_interval
        self.running = True
        self.logger = logging.getLogger(__name__)
        
    async def start(self):
        """Start watchdog service"""
        self.logger.info(f"Starting IB Gateway Watchdog on port {self.port}")
        
        while self.running:
            try:
                # Ensure connection
                if not self.ib.isConnected():
                    await self._connect()
                
                # Send heartbeat
                if self.ib.isConnected():
                    await self._heartbeat()
                
                # Wait before next cycle
                await asyncio.sleep(self.heartbeat_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Watchdog error: {e}")
                await asyncio.sleep(30)  # Wait before retry
    
    async def _connect(self):
        """Connect to IB Gateway"""
        try:
            self.logger.info("Connecting to IB Gateway...")
            await self.ib.connectAsync('127.0.0.1', self.port, clientId=self.client_id)
            
            if self.ib.isConnected():
                self.logger.info(f"Connected successfully. Account: {self.ib.managedAccounts()}")
            else:
                self.logger.error("Connection failed")
                
        except Exception as e:
            self.logger.error(f"Connection error: {e}")
    
    async def _heartbeat(self):
        """Send heartbeat ping"""
        try:
            server_time = await self.ib.reqCurrentTimeAsync()
            self.logger.info(f"Heartbeat sent - Server time: {server_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        except Exception as e:
            self.logger.error(f"Heartbeat failed: {e}")
            # Force reconnection on next cycle
            if self.ib.isConnected():
                self.ib.disconnect()
    
    def stop(self):
        """Stop watchdog service"""
        self.logger.info("Stopping watchdog...")
        self.running = False
        if self.ib.isConnected():
            self.ib.disconnect()

async def main():
    """Run as standalone service"""
    watchdog = IBGatewayWatchdog(
        port=4002,  # Paper trading
        client_id=999,
        heartbeat_interval=120  # 2 minutes
    )
    
    try:
        await watchdog.start()
    except KeyboardInterrupt:
        watchdog.stop()
        print("\nWatchdog stopped")

if __name__ == "__main__":
    asyncio.run(main())
