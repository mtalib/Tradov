#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System
Module: SpyderB01_SpyderClient.py
Group: B (Broker Integration)
Purpose: Main IB client using ib-insync (NO IBAPI)

Description:
    This module provides the main Interactive Brokers client interface using
    ib-insync library. It handles connection management, order placement,
    position tracking, and market data requests. This version is completely
    free of ibapi dependencies.

Author: Mohamed Talib
Date: 2025-06-23
Version: 1.5 (IBAPI-FREE)
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
import time
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
import random

# ==============================================================================
# THIRD-PARTY IMPORTS (IB-INSYNC ONLY)
# ==============================================================================
import nest_asyncio
nest_asyncio.apply()

try:
    from ib_insync import IB, Stock, Option, Contract, Order, Trade
    from ib_insync import LimitOrder, MarketOrder, util
    HAS_IB_INSYNC = True
except ImportError:
    HAS_IB_INSYNC = False
    print("WARNING: ib_insync not found. Running in DEMO mode.")

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 4002  # Paper trading port
DEFAULT_CLIENT_ID = 1

# ==============================================================================
# MAIN SPYDER CLIENT CLASS (IBAPI-FREE)
# ==============================================================================
class SpyderClient:
    """
    Spyder client for IB Gateway connection using ib-insync only.
    
    This class provides a clean interface to Interactive Brokers using
    the ib-insync library, completely eliminating ibapi dependencies.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize SpyderClient with ib-insync."""
        self.config = config
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # IB configuration
        ib_config = config.get('ib', {})
        self.client_id = ib_config.get('client_id', DEFAULT_CLIENT_ID)
        self.host = ib_config.get('host', DEFAULT_HOST)
        self.port = ib_config.get('port', DEFAULT_PORT)
        
        # Connection state
        self.connected = False
        self.demo_mode = not HAS_IB_INSYNC or config.get('demo_mode', False)
        
        # Data storage
        self.account_data = {}
        self.positions = []
        self.orders = {}
        self.trades = []
        
        # IB-insync instance
        self.ib = None
        
        self.logger.info(f"SpyderClient initialized: Mode={'DEMO' if self.demo_mode else 'LIVE'}, "
                        f"Host={self.host}, Port={self.port}")
    
    def connect(self) -> bool:
        """Connect to IB Gateway using ib-insync."""
        if self.connected:
            self.logger.info("Already connected")
            return True
            
        try:
            if self.demo_mode:
                return self._connect_demo()
            else:
                return self._connect_ib_insync()
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            self.logger.info("Falling back to DEMO mode")
            self.demo_mode = True
            return self._connect_demo()
    
    async def connect_async(self) -> bool:
        """
        Async version of connect method.
        
        Returns:
            True if connection successful, False otherwise
        """
        # For now, just call the sync version
        # In a full implementation, this would use proper async IB connection
        return self.connect()
    
    def _connect_demo(self) -> bool:
        """Demo mode connection."""
        self.logger.info("🎭 Running in DEMO mode")
        time.sleep(0.5)  # Simulate connection delay
        self.connected = True
        self._initialize_demo_data()
        return True
    
    def _connect_ib_insync(self) -> bool:
        """Connect using ib-insync library."""
        try:
            if self.ib:
                self.ib.disconnect()
                
            self.ib = IB()
            self.logger.info(f"🔌 Connecting to IB Gateway: {self.host}:{self.port}")
            
            # Connect synchronously
            self.ib.connect(self.host, self.port, clientId=self.client_id)
            
            if self.ib.isConnected():
                self.connected = True
                self.logger.info("✅ Connected to IB Gateway successfully!")
                self._setup_event_handlers()
                return True
            else:
                raise Exception("Connection failed - not connected")
                
        except Exception as e:
            self.logger.error(f"❌ IB connection error: {e}")
            if self.ib:
                try:
                    self.ib.disconnect()
                except:
                    pass
            return False
    
    def _setup_event_handlers(self):
        """Setup ib-insync event handlers."""
        if not self.ib:
            return
            
        # Set up event callbacks
        self.ib.connectedEvent += self._on_connected
        self.ib.disconnectedEvent += self._on_disconnected
        self.ib.errorEvent += self._on_error
        
        self.logger.info("Event handlers configured")
    
    def _on_connected(self):
        """Handle connection event."""
        self.logger.info("🎯 IB connection established")
        self.connected = True
    
    def _on_disconnected(self):
        """Handle disconnection event."""
        self.logger.warning("🔌 IB connection lost")
        self.connected = False
    
    def _on_error(self, reqId, errorCode, errorString, contract):
        """Handle IB errors."""
        self.logger.error(f"IB Error {errorCode}: {errorString}")
        self.error_handler.handle_error(
            f"IB_ERROR_{errorCode}", 
            errorString, 
            {"reqId": reqId, "contract": contract}
        )
    
    def disconnect(self):
        """Disconnect from IB."""
        if self.ib and self.connected:
            try:
                self.ib.disconnect()
                self.logger.info("🔌 Disconnected from IB Gateway")
            except Exception as e:
                self.logger.error(f"Disconnect error: {e}")
        self.connected = False
    
    def is_connected(self) -> bool:
        """Check connection status."""
        if self.demo_mode:
            return self.connected
        return self.ib and self.ib.isConnected()
    
    def is_demo_mode(self) -> bool:
        """Check if running in demo mode."""
        return self.demo_mode
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Get detailed connection status."""
        return {
            'connected': self.connected,
            'demo_mode': self.demo_mode,
            'host': self.host,
            'port': self.port,
            'client_id': self.client_id
        }
    
    def get_account_summary(self) -> Dict[str, Any]:
        """Get account information."""
        if not self.connected:
            raise Exception("Not connected to IB")
            
        if self.demo_mode:
            return self.account_data
            
        # Get account summary using ib-insync
        if self.ib:
            try:
                account_values = self.ib.accountSummary()
                self.account_data = {av.tag: av.value for av in account_values}
                return self.account_data
            except Exception as e:
                self.logger.error(f"Account summary error: {e}")
                return {}
        
        return {}
    
    def get_positions(self) -> List[Dict[str, Any]]:
        """Get current positions."""
        if not self.connected:
            raise Exception("Not connected to IB")
            
        if self.demo_mode:
            return self.positions
            
        if self.ib:
            try:
                positions = self.ib.positions()
                self.positions = [
                    {
                        'symbol': pos.contract.symbol,
                        'position': pos.position,
                        'market_price': pos.marketPrice,
                        'market_value': pos.marketValue,
                        'avg_cost': pos.avgCost
                    }
                    for pos in positions
                ]
                return self.positions
            except Exception as e:
                self.logger.error(f"Positions error: {e}")
                return []
        
        return []
    
    def place_order(self, symbol: str, quantity: int, action: str, 
                   order_type: str = "MKT", limit_price: Optional[float] = None) -> Optional[Trade]:
        """Place order using ib-insync."""
        if not self.connected:
            raise Exception("Not connected to IB")
        
        if self.demo_mode:
            return self._place_demo_order(symbol, quantity, action, order_type, limit_price)
        
        if not self.ib:
            raise Exception("IB client not initialized")
        
        try:
            # Create contract (simplified - assumes stock)
            contract = Stock(symbol, 'SMART', 'USD')
            
            # Create order
            if order_type == "MKT":
                order = MarketOrder(action, quantity)
            elif order_type == "LMT" and limit_price:
                order = LimitOrder(action, quantity, limit_price)
            else:
                raise ValueError(f"Unsupported order type: {order_type}")
            
            # Place order
            trade = self.ib.placeOrder(contract, order)
            self.logger.info(f"📊 Order placed: {symbol} {action} {quantity} @ {order_type}")
            
            return trade
            
        except Exception as e:
            self.logger.error(f"Order placement error: {e}")
            self.error_handler.handle_error("ORDER_ERROR", str(e), 
                                          {"symbol": symbol, "quantity": quantity})
            return None
    
    def _place_demo_order(self, symbol: str, quantity: int, action: str, 
                         order_type: str, limit_price: Optional[float]) -> Dict[str, Any]:
        """Place demo order."""
        order_id = random.randint(1000, 9999)
        demo_order = {
            'order_id': order_id,
            'symbol': symbol,
            'quantity': quantity,
            'action': action,
            'order_type': order_type,
            'limit_price': limit_price,
            'status': 'FILLED',
            'timestamp': datetime.now().isoformat()
        }
        
        self.orders[order_id] = demo_order
        self.logger.info(f"🎭 DEMO Order: {symbol} {action} {quantity}")
        
        return demo_order
    
    async def request_account_updates(self) -> bool:
        """
        Request account updates from IB.
        
        Returns:
            True if successful, False otherwise
        """
        if not self.connected:
            self.logger.error("Not connected to IB")
            return False
        
        if self.demo_mode:
            self.logger.info("📊 Account updates (DEMO mode)")
            # Update demo account data
            self.account_data.update({
                'UpdateTime': datetime.now().isoformat(),
                'Status': 'Active'
            })
            return True
        
        if self.ib:
            try:
                # Request account updates using ib-insync
                account_values = self.ib.accountSummary()
                self.account_data = {av.tag: av.value for av in account_values}
                self.logger.info("📊 Account updates received")
                return True
            except Exception as e:
                self.logger.error(f"Account updates error: {e}")
                return False
        
        return False
    
    async def request_positions(self) -> bool:
        """
        Request position updates from IB.
        
        Returns:
            True if successful, False otherwise
        """
        if not self.connected:
            self.logger.error("Not connected to IB")
            return False
        
        if self.demo_mode:
            self.logger.info("📊 Position updates (DEMO mode)")
            return True
        
        if self.ib:
            try:
                positions = self.ib.positions()
                self.positions = [
                    {
                        'symbol': pos.contract.symbol,
                        'position': pos.position,
                        'market_price': pos.marketPrice,
                        'market_value': pos.marketValue,
                        'avg_cost': pos.avgCost
                    }
                    for pos in positions
                ]
                self.logger.info(f"📊 Received {len(self.positions)} positions")
                return True
            except Exception as e:
                self.logger.error(f"Position updates error: {e}")
                return False
        
        return False
    
    def get_account_value(self, key: str) -> float:
        """
        Get specific account value.
        
        Args:
            key: Account value key (e.g., 'NetLiquidation', 'BuyingPower')
            
        Returns:
            Account value as float
        """
        value = self.account_data.get(key, '0.0')
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0
    
    def get_buying_power(self) -> float:
        """Get buying power."""
        return self.get_account_value('BuyingPower')
    
    def get_net_liquidation(self) -> float:
        """Get net liquidation value."""
        return self.get_account_value('NetLiquidation')
    
    def _initialize_demo_data(self):
        """Initialize demo account data."""
        self.account_data = {
            'NetLiquidation': '100000.00',
            'BuyingPower': '200000.00',
            'TotalCashValue': '50000.00',
            'GrossPositionValue': '50000.00'
        }
        
        self.positions = [
            {
                'symbol': 'SPY',
                'position': 100,
                'market_price': 450.0,
                'market_value': 45000.0,
                'avg_cost': 445.0
            }
        ]
        
        self.logger.info("🎭 Demo data initialized")

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def get_spyder_client(config: Dict[str, Any]) -> SpyderClient:
    """
    Get SpyderClient instance (factory function).
    
    Args:
        config: Configuration dictionary
        
    Returns:
        SpyderClient instance
    """
    return SpyderClient(config)

# ==============================================================================
# EXPORTS
# ==============================================================================
__all__ = ['SpyderClient', 'get_spyder_client']
