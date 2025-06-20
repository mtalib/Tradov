#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System
Module: SpyderB01_SpyderClient.py
"""

import logging
import time
from typing import Optional, Dict, Any, List
from datetime import datetime
import random
import asyncio
import nest_asyncio

# Apply nest_asyncio to allow nested event loops
nest_asyncio.apply()

try:
    from ib_insync import IB, Stock, util
    HAS_IB_INSYNC = True
except ImportError:
    HAS_IB_INSYNC = False
    print("WARNING: ib_insync not found. Running in DEMO mode.")

TickerId = int

class SpyderClient:
    """Spyder client for IB Gateway connection."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        ib_config = config.get('ib', {})
        self.client_id = ib_config.get('client_id', 1)
        self.host = ib_config.get('host', '127.0.0.1')
        self.port = ib_config.get('port', 4002)
        
        self.connected = False
        self.demo_mode = not HAS_IB_INSYNC or config.get('demo_mode', False)
        
        self.account_data = {}
        self.positions = []
        self.orders = {}
        self.ib = None
        
        self.logger.info(f"SpyderClient: Mode={'DEMO' if self.demo_mode else 'LIVE'}, "
                        f"Host={self.host}, Port={self.port}")
    
    def connect(self) -> bool:
        """Connect to IB Gateway."""
        if self.connected:
            return True
            
        try:
            if self.demo_mode:
                return self._connect_demo()
            else:
                return self._connect_ib()
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            self.logger.info("Falling back to DEMO mode")
            self.demo_mode = True
            return self._connect_demo()
    
    def _connect_demo(self) -> bool:
        """Demo mode connection."""
        self.logger.info("Running in DEMO mode")
        time.sleep(0.5)
        self.connected = True
        self._initialize_demo_data()
        return True
    
    def _connect_ib(self) -> bool:
        """Connect to IB Gateway."""
        try:
            if self.ib:
                self.ib.disconnect()
                
            self.ib = IB()
            self.logger.info(f"Connecting to IB Gateway at {self.host}:{self.port}...")
            
            # Use util.run for synchronous connection in async environment
            util.run(self.ib.connectAsync(self.host, self.port, clientId=self.client_id))
            
            if self.ib.isConnected():
                self.connected = True
                self.logger.info("Connected to IB Gateway!")
                return True
            else:
                raise Exception("Connection failed")
                
        except Exception as e:
            self.logger.error(f"IB connection error: {e}")
            if self.ib:
                try:
                    self.ib.disconnect()
                except:
                    pass
            return False
    
    async def connect_async(self) -> bool:
        """Async connect wrapper."""
        return self.connect()
    
    def disconnect(self):
        """Disconnect from IB."""
        if self.ib and self.connected:
            try:
                self.ib.disconnect()
            except:
                pass
        self.connected = False
        
    async def disconnect_async(self):
        """Async disconnect."""
        self.disconnect()
    
    def is_connected(self) -> bool:
        """Check connection status."""
        if self.demo_mode:
            return self.connected
        return self.ib and self.ib.isConnected()
    
    async def request_account_updates(self) -> Dict[str, Any]:
        """Get account data."""
        if not self.connected:
            raise Exception("Not connected")
            
        if self.demo_mode:
            return self.account_data
            
        # Real IB account data
        if self.ib:
            account_values = util.run(self.ib.accountValuesAsync())
            self.account_data = {av.tag: av.value for av in account_values}
            
        return self.account_data
    
    async def request_positions(self) -> List[Dict[str, Any]]:
        """Get positions."""
        if not self.connected:
            raise Exception("Not connected")
        return self.positions
    
    def _initialize_demo_data(self):
        """Setup demo data."""
        self.account_data = {
            'NetLiquidation': 100000.00,
            'BuyingPower': 200000.00,
            'TotalCashValue': 50000.00
        }
        self.positions = []
        
    def place_order(self, symbol: str, quantity: int, order_type: str,
                   side: str, limit_price: Optional[float] = None):
        """Place order."""
        order_id = len(self.orders) + 1000
        order = {
            'orderId': order_id,
            'symbol': symbol,
            'quantity': quantity,
            'orderType': order_type,
            'side': side,
            'status': 'Submitted'
        }
        self.orders[order_id] = order
        return order
        
    def get_account_value(self, key: str) -> float:
        """Get account value."""
        return float(self.account_data.get(key, 0.0))
        
    def get_positions(self):
        """Get positions."""
        return self.positions

def get_spyder_client(config: Dict[str, Any]) -> SpyderClient:
    """Get SpyderClient instance."""
    return SpyderClient(config)
