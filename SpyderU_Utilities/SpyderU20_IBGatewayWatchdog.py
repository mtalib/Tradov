#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderU20_IBGatewayWatchdog.py
Group: U (Utilities)
Purpose: Monitor IB Gateway connection health and maintain stability
Author: Mohamed Talib
Date Created: 2025-07-30
Last Updated: 2025-07-30 Time: 17:00:00

Description:
    This module provides a watchdog service for IB Gateway to prevent
    disconnections, monitor connection health, and optionally restart
    the gateway if it becomes unresponsive. Uses heartbeat pings to
    keep the connection alive and prevent idle timeouts.
"""

# ==============================================================================
# IMPORTS
# ==============================================================================
import asyncio
import logging
import time
import subprocess
import os
from datetime import datetime, timedelta
from typing import Optional, Callable, Dict, Any
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

# Third-party imports
from ib_async import IB, util

# Local imports
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
except ImportError:
    # Fallback logger
    logging.basicConfig(level=logging.INFO)
    SpyderLogger = logging

# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_PORT = 4002  # Paper trading port
DEFAULT_CLIENT_ID = 999  # Dedicated watchdog client ID
HEARTBEAT_INTERVAL = 120  # Send heartbeat every 2 minutes
CHECK_INTERVAL = 30  # Check connection every 30 seconds
RECONNECT_DELAY = 10  # Wait 10 seconds before reconnecting
MAX_RECONNECT_ATTEMPTS = 3
GATEWAY_RESTART_DELAY = 30  # Wait 30 seconds after restarting gateway

# ==============================================================================
# WATCHDOG CLASS
# ==============================================================================
class IBGatewayWatchdog:
    """
    Monitors IB Gateway connection and maintains stability
    """
    
    def __init__(self, 
                 host: str = "127.0.0.1",
                 port: int = DEFAULT_PORT,
                 client_id: int = DEFAULT_CLIENT_ID,
                 auto_restart_gateway: bool = False,
                 gateway_start_cmd: Optional[str] = None,
                 on_disconnect_callback: Optional[Callable] = None,
                 on_reconnect_callback: Optional[Callable] = None):
        """
        Initialize the watchdog
        
        Args:
            host: IB Gateway host
            port: IB Gateway port (4002 for paper, 4001 for live)
            client_id: Client ID for watchdog connection
            auto_restart_gateway: Whether to auto-restart IB Gateway
            gateway_start_cmd: Command to start IB Gateway
            on_disconnect_callback: Callback when disconnected
            on_reconnect_callback: Callback when reconnected
        """
        self.host = host
        self.port = port
        self.client_id = client_id
        self.auto_restart_gateway = auto_restart_gateway
        self.gateway_start_cmd = gateway_start_cmd
        self.on_disconnect_callback = on_disconnect_callback
        self.on_reconnect_callback = on_reconnect_callback
        
        # IB connection
        self.ib = None
        self.connected = False
        self.last_heartbeat = None
        self.reconnect_attempts = 0
        
        # Logging
        self.logger = SpyderLogger.get_logger(__name__) if hasattr(SpyderLogger, 'get_logger') else logging.getLogger(__name__)
        
        # Stats
        self.stats = {
            'start_time': datetime.now(),
            'total_disconnects': 0,
            'total_reconnects': 0,
            'gateway_restarts': 0,
            'last_disconnect': None,
            'uptime_percentage': 100.0
        }
        
        # Tasks
        self.monitor_task = None
        self.heartbeat_task = None
        self.running = False
        
    # ==========================================================================
    # CONNECTION METHODS
    # ==========================================================================
    
    async def connect(self) -> bool:
        """
        Connect to IB Gateway
        
        Returns:
            bool: True if connected successfully
        """
        try:
            self.ib = IB()
            await self.ib.connectAsync(self.host, self.port, clientId=self.client_id)
            
            if self.ib.isConnected():
                self.connected = True
                self.reconnect_attempts = 0
                self.logger.info(f"✅ Watchdog connected to IB Gateway at {self.host}:{self.port}")
                
                # Request initial data to verify connection
                server_time = await self.ib.reqCurrentTimeAsync()
                self.logger.info(f"📡 IB Server time: {datetime.fromtimestamp(server_time)}")
                
                if self.on_reconnect_callback:
                    self.on_reconnect_callback()
                    
                return True
            else:
                self.logger.error("❌ Failed to connect to IB Gateway")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Connection error: {e}")
            self.connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from IB Gateway"""
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
            self.connected = False
            self.logger.info("🔌 Watchdog disconnected from IB Gateway")
    
    # ==========================================================================
    # HEARTBEAT METHODS
    # ==========================================================================
    
    async def send_heartbeat(self) -> bool:
        """
        Send heartbeat ping to keep connection alive
        
        Returns:
            bool: True if heartbeat successful
        """
        if not self.ib or not self.ib.isConnected():
            return False
            
        try:
            # Request current time as heartbeat
            server_time = await self.ib.reqCurrentTimeAsync()
            self.last_heartbeat = datetime.now()
            
            self.logger.debug(f"💓 Heartbeat sent - Server time: {datetime.fromtimestamp(server_time)}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Heartbeat failed: {e}")
            return False
    
    async def heartbeat_loop(self):
        """Continuous heartbeat loop"""
        while self.running:
            try:
                if self.connected:
                    success = await self.send_heartbeat()
                    if not success:
                        self.logger.warning("⚠️ Heartbeat failed - connection may be lost")
                        
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"❌ Heartbeat loop error: {e}")
                await asyncio.sleep(HEARTBEAT_INTERVAL)
    
    # ==========================================================================
    # MONITORING METHODS
    # ==========================================================================
    
    async def check_connection(self) -> bool:
        """
        Check if connection is healthy
        
        Returns:
            bool: True if connection is healthy
        """
        if not self.ib:
            return False
            
        # Check basic connection
        if not self.ib.isConnected():
            return False
            
        # Check if we can get data
        try:
            server_time = await asyncio.wait_for(
                self.ib.reqCurrentTimeAsync(), 
                timeout=5.0
            )
            return True
        except (asyncio.TimeoutError, Exception) as e:
            self.logger.error(f"❌ Connection check failed: {e}")
            return False
    
    async def handle_disconnect(self):
        """Handle disconnection"""
        self.connected = False
        self.stats['total_disconnects'] += 1
        self.stats['last_disconnect'] = datetime.now()
        
        self.logger.warning("🔴 IB Gateway disconnected!")
        
        if self.on_disconnect_callback:
            self.on_disconnect_callback()
    
    async def attempt_reconnect(self) -> bool:
        """
        Attempt to reconnect to IB Gateway
        
        Returns:
            bool: True if reconnected successfully
        """
        self.reconnect_attempts += 1
        self.logger.info(f"🔄 Attempting reconnect ({self.reconnect_attempts}/{MAX_RECONNECT_ATTEMPTS})...")
        
        # Disconnect cleanly first
        await self.disconnect()
        await asyncio.sleep(RECONNECT_DELAY)
        
        # Try to reconnect
        success = await self.connect()
        
        if success:
            self.stats['total_reconnects'] += 1
            self.logger.info("✅ Reconnected successfully!")
            return True
        else:
            if self.reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
                self.logger.error("❌ Max reconnection attempts reached")
                if self.auto_restart_gateway:
                    await self.restart_gateway()
            return False
    
    async def restart_gateway(self):
        """Restart IB Gateway (if configured)"""
        if not self.gateway_start_cmd:
            self.logger.error("❌ No gateway start command configured")
            return
            
        self.logger.warning("🔄 Restarting IB Gateway...")
        self.stats['gateway_restarts'] += 1
        
        try:
            # Kill existing gateway
            subprocess.run(['pkill', '-f', 'ibgateway'], check=False)
            await asyncio.sleep(5)
            
            # Start new gateway
            subprocess.Popen(self.gateway_start_cmd, shell=True)
            await asyncio.sleep(GATEWAY_RESTART_DELAY)
            
            # Reset reconnect attempts and try connecting
            self.reconnect_attempts = 0
            await self.connect()
            
        except Exception as e:
            self.logger.error(f"❌ Failed to restart gateway: {e}")
    
    async def monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                # Check connection health
                is_healthy = await self.check_connection()
                
                if is_healthy and not self.connected:
                    # Connection restored
                    self.connected = True
                    self.logger.info("✅ Connection restored")
                    
                elif not is_healthy and self.connected:
                    # Connection lost
                    await self.handle_disconnect()
                    
                elif not is_healthy and not self.connected:
                    # Try to reconnect
                    await self.attempt_reconnect()
                
                # Update stats
                self._update_stats()
                
                await asyncio.sleep(CHECK_INTERVAL)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"❌ Monitor loop error: {e}")
                await asyncio.sleep(CHECK_INTERVAL)
    
    # ==========================================================================
    # CONTROL METHODS
    # ==========================================================================
    
    async def start(self):
        """Start the watchdog"""
        self.logger.info("🐕 Starting IB Gateway Watchdog...")
        self.running = True
        
        # Initial connection
        await self.connect()
        
        # Start monitoring tasks
        self.monitor_task = asyncio.create_task(self.monitor_loop())
        self.heartbeat_task = asyncio.create_task(self.heartbeat_loop())
        
        self.logger.info("✅ Watchdog started")
    
    async def stop(self):
        """Stop the watchdog"""
        self.logger.info("🛑 Stopping watchdog...")
        self.running = False
        
        # Cancel tasks
        if self.monitor_task:
            self.monitor_task.cancel()
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            
        # Disconnect
        await self.disconnect()
        
        # Print final stats
        self._print_stats()
        
        self.logger.info("✅ Watchdog stopped")
    
    # ==========================================================================
    # STATS METHODS
    # ==========================================================================
    
    def _update_stats(self):
        """Update statistics"""
        if self.stats['start_time']:
            total_time = (datetime.now() - self.stats['start_time']).total_seconds()
            if self.stats['last_disconnect']:
                downtime = (datetime.now() - self.stats['last_disconnect']).total_seconds()
                if not self.connected:
                    self.stats['uptime_percentage'] = ((total_time - downtime) / total_time) * 100
    
    def _print_stats(self):
        """Print watchdog statistics"""
        self.logger.info("="*60)
        self.logger.info("📊 WATCHDOG STATISTICS")
        self.logger.info("="*60)
        self.logger.info(f"Start Time: {self.stats['start_time']}")
        self.logger.info(f"Total Disconnects: {self.stats['total_disconnects']}")
        self.logger.info(f"Total Reconnects: {self.stats['total_reconnects']}")
        self.logger.info(f"Gateway Restarts: {self.stats['gateway_restarts']}")
        self.logger.info(f"Uptime: {self.stats['uptime_percentage']:.2f}%")
        self.logger.info("="*60)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics"""
        return self.stats.copy()

# ==============================================================================
# STANDALONE USAGE
# ==============================================================================
async def main():
    """Run watchdog standalone"""
    print("\n" + "="*60)
    print("IB GATEWAY WATCHDOG")
    print("="*60)
    print("🐕 Monitoring IB Gateway connection...")
    print("💓 Heartbeat interval: 2 minutes")
    print("🔍 Check interval: 30 seconds")
    print("="*60 + "\n")
    
    # Create watchdog
    watchdog = IBGatewayWatchdog(
        port=4002,  # Paper trading
        client_id=999,  # Dedicated watchdog ID
        auto_restart_gateway=False  # Set to True if you want auto-restart
    )
    
    try:
        # Start watchdog
        await watchdog.start()
        
        # Keep running
        while True:
            await asyncio.sleep(60)
            
    except KeyboardInterrupt:
        print("\n⚠️ Watchdog interrupted by user")
    finally:
        await watchdog.stop()

if __name__ == "__main__":
    asyncio.run(main())
