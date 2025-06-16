#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderB10_IBDataTypes.py
Group: B (Broker Integration)
Purpose: Interactive Brokers API data type definitions and structures

Description:
    This module provides standardized data type definitions and structures for
    the Interactive Brokers API integration. It defines contracts, orders,
    positions, trades, and market data structures that ensure consistent type
    usage across all broker integration modules. The module also includes utility
    functions for creating common contract and order types used in SPY options trading.

Author: Mohamed Talib
Date: 2025-06-14
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
# None required for this module

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Default values for IB contracts
DEFAULT_EXCHANGE = "SMART"
DEFAULT_CURRENCY = "USD"
OPTION_MULTIPLIER = "100"

# ==============================================================================
# ENUMS
# ==============================================================================
class SecurityType(Enum):
    """Security types for IB contracts"""
    STOCK = "STK"
    OPTION = "OPT"
    FUTURE = "FUT"
    FOREX = "CASH"
    INDEX = "IND"
    CFD = "CFD"

class OrderAction(Enum):
    """Order actions"""
    BUY = "BUY"
    SELL = "SELL"

class OrderType(Enum):
    """Order types"""
    MARKET = "MKT"
    LIMIT = "LMT"
    STOP = "STP"
    STOP_LIMIT = "STP LMT"

class OrderStatus(Enum):
    """Order status values"""
    PENDING_SUBMIT = "PendingSubmit"
    PENDING_CANCEL = "PendingCancel"
    PRE_SUBMITTED = "PreSubmitted"
    SUBMITTED = "Submitted"
    CANCELLED = "Cancelled"
    FILLED = "Filled"
    INACTIVE = "Inactive"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class IBContract:
    """
    IB Contract representation.
    
    Represents a financial instrument contract in the IB API system.
    Used for stocks, options, futures, and other security types.
    """
    symbol: str
    sec_type: SecurityType
    exchange: str = DEFAULT_EXCHANGE
    currency: str = DEFAULT_CURRENCY
    local_symbol: str = ""
    
    # Option-specific fields
    last_trade_date: Optional[str] = None
    strike: Optional[float] = None
    right: Optional[str] = None  # "C" for Call, "P" for Put
    
    # Additional fields
    con_id: Optional[int] = None
    multiplier: Optional[str] = None

@dataclass
class IBOrder:
    """
    IB Order representation.
    
    Represents an order to be placed through the IB API system.
    Contains all necessary order parameters and tracking information.
    """
    action: OrderAction
    total_quantity: int
    order_type: OrderType
    
    # Price fields
    lmt_price: Optional[float] = None
    aux_price: Optional[float] = None
    
    # Time in force
    tif: str = "DAY"
    
    # Order properties
    order_id: Optional[int] = None
    perm_id: Optional[int] = None
    client_id: Optional[int] = None
    
    # Status
    status: Optional[OrderStatus] = None
    
    # Additional fields
    account: Optional[str] = None
    order_ref: Optional[str] = None

@dataclass
class IBPosition:
    """
    IB Position representation.
    
    Represents an open position in the trading account with
    real-time P&L calculations and position metrics.
    """
    contract: IBContract
    position: float
    market_price: float
    market_value: float
    average_cost: float
    unrealized_pnl: float
    realized_pnl: float
    account: str

@dataclass
class IBTrade:
    """
    IB Trade execution representation.
    
    Represents a completed trade execution with all fill details
    and commission information.
    """
    contract: IBContract
    execution_id: str
    time: str
    account: str
    exchange: str
    side: str
    shares: float
    price: float
    perm_id: int
    client_id: int
    order_id: int
    liquidation: int
    cum_qty: float
    avg_price: float

@dataclass
class IBMarketData:
    """
    IB Market data representation.
    
    Contains real-time market data including prices, sizes, Greeks
    for options, and other market metrics.
    """
    contract: IBContract
    
    # Price fields
    bid: Optional[float] = None
    ask: Optional[float] = None
    last: Optional[float] = None
    close: Optional[float] = None
    
    # Size fields
    bid_size: Optional[int] = None
    ask_size: Optional[int] = None
    last_size: Optional[int] = None
    
    # Volume and other data
    volume: Optional[int] = None
    high: Optional[float] = None
    low: Optional[float] = None
    
    # Option-specific data
    implied_volatility: Optional[float] = None
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    
    # Timestamps
    last_timestamp: Optional[datetime] = None

# ==============================================================================
# TYPE ALIASES
# ==============================================================================
ContractId = int
OrderId = int
TickerId = int

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class IBDataTypeManager:
    """
    Manager class for IB data types and conversions.
    
    This class provides validation and conversion utilities for IB data types,
    ensuring data integrity and proper formatting throughout the system.
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        
    Example:
        >>> manager = IBDataTypeManager()
        >>> contract = manager.create_stock_contract("SPY")
        >>> order = manager.create_limit_order(OrderAction.BUY, 10, 450.50)
    """
    
    def __init__(self):
        """Initialize the IB data type manager."""
        self.logger = SpyderLogger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        self.logger.info(f"{self.__class__.__name__} initialized")
    
    # ==========================================================================
    # PUBLIC METHODS - CONTRACT CREATION
    # ==========================================================================
    def create_stock_contract(
        self, 
        symbol: str, 
        exchange: str = DEFAULT_EXCHANGE, 
        currency: str = DEFAULT_CURRENCY
    ) -> IBContract:
        """
        Create a stock contract.
        
        Args:
            symbol: Stock symbol
            exchange: Exchange (default: SMART)
            currency: Currency (default: USD)
            
        Returns:
            IBContract for stock
        """
        try:
            contract = IBContract(
                symbol=symbol,
                sec_type=SecurityType.STOCK,
                exchange=exchange,
                currency=currency
            )
            
            self.logger.debug(f"Created stock contract for {symbol}")
            return contract
            
        except Exception as e:
            self.logger.error(f"Failed to create stock contract: {e}")
            raise
    
    def create_option_contract(
        self,
        symbol: str,
        last_trade_date: str,
        strike: float,
        right: str,
        exchange: str = DEFAULT_EXCHANGE,
        currency: str = DEFAULT_CURRENCY
    ) -> IBContract:
        """
        Create an option contract.
        
        Args:
            symbol: Underlying symbol
            last_trade_date: Expiration date (YYYYMMDD)
            strike: Strike price
            right: "C" for Call, "P" for Put
            exchange: Exchange (default: SMART)
            currency: Currency (default: USD)
            
        Returns:
            IBContract for option
        """
        try:
            contract = IBContract(
                symbol=symbol,
                sec_type=SecurityType.OPTION,
                exchange=exchange,
                currency=currency,
                last_trade_date=last_trade_date,
                strike=strike,
                right=right,
                multiplier=OPTION_MULTIPLIER
            )
            
            self.logger.debug(
                f"Created option contract: {symbol} {last_trade_date} {right}{strike}"
            )
            return contract
            
        except Exception as e:
            self.logger.error(f"Failed to create option contract: {e}")
            raise
    
    # ==========================================================================
    # PUBLIC METHODS - ORDER CREATION
    # ==========================================================================
    def create_market_order(
        self, 
        action: OrderAction, 
        quantity: int
    ) -> IBOrder:
        """
        Create a market order.
        
        Args:
            action: BUY or SELL
            quantity: Number of contracts/shares
            
        Returns:
            IBOrder for market order
        """
        try:
            order = IBOrder(
                action=action,
                total_quantity=quantity,
                order_type=OrderType.MARKET
            )
            
            self.logger.debug(f"Created market order: {action.value} {quantity}")
            return order
            
        except Exception as e:
            self.logger.error(f"Failed to create market order: {e}")
            raise
    
    def create_limit_order(
        self, 
        action: OrderAction, 
        quantity: int, 
        limit_price: float
    ) -> IBOrder:
        """
        Create a limit order.
        
        Args:
            action: BUY or SELL
            quantity: Number of contracts/shares
            limit_price: Limit price
            
        Returns:
            IBOrder for limit order
        """
        try:
            order = IBOrder(
                action=action,
                total_quantity=quantity,
                order_type=OrderType.LIMIT,
                lmt_price=limit_price
            )
            
            self.logger.debug(
                f"Created limit order: {action.value} {quantity} @ {limit_price}"
            )
            return order
            
        except Exception as e:
            self.logger.error(f"Failed to create limit order: {e}")
            raise
    
    # ==========================================================================
    # PUBLIC METHODS - VALIDATION
    # ==========================================================================
    def validate_contract(self, contract: IBContract) -> bool:
        """
        Validate contract data.
        
        Args:
            contract: Contract to validate
            
        Returns:
            bool: True if valid
        """
        try:
            # Basic validation
            if not contract.symbol:
                self.logger.error("Contract symbol is required")
                return False
            
            if contract.sec_type == SecurityType.OPTION:
                if not contract.strike or contract.strike <= 0:
                    self.logger.error("Invalid strike price for option")
                    return False
                
                if contract.right not in ["C", "P"]:
                    self.logger.error("Invalid option right (must be C or P)")
                    return False
                
                if not contract.last_trade_date:
                    self.logger.error("Expiration date required for option")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Contract validation error: {e}")
            return False
    
    def validate_order(self, order: IBOrder) -> bool:
        """
        Validate order data.
        
        Args:
            order: Order to validate
            
        Returns:
            bool: True if valid
        """
        try:
            # Basic validation
            if order.total_quantity <= 0:
                self.logger.error("Order quantity must be positive")
                return False
            
            if order.order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT]:
                if not order.lmt_price or order.lmt_price <= 0:
                    self.logger.error("Limit price required for limit orders")
                    return False
            
            if order.order_type in [OrderType.STOP, OrderType.STOP_LIMIT]:
                if not order.aux_price or order.aux_price <= 0:
                    self.logger.error("Stop price required for stop orders")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Order validation error: {e}")
            return False

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_stock_contract(
    symbol: str, 
    exchange: str = DEFAULT_EXCHANGE, 
    currency: str = DEFAULT_CURRENCY
) -> IBContract:
    """
    Module-level function to create a stock contract.
    
    Args:
        symbol: Stock symbol
        exchange: Exchange (default: SMART)
        currency: Currency (default: USD)
        
    Returns:
        IBContract for stock
    """
    return IBContract(
        symbol=symbol,
        sec_type=SecurityType.STOCK,
        exchange=exchange,
        currency=currency
    )

def create_option_contract(
    symbol: str,
    last_trade_date: str,
    strike: float,
    right: str,
    exchange: str = DEFAULT_EXCHANGE,
    currency: str = DEFAULT_CURRENCY
) -> IBContract:
    """
    Module-level function to create an option contract.
    
    Args:
        symbol: Underlying symbol
        last_trade_date: Expiration date (YYYYMMDD)
        strike: Strike price
        right: "C" for Call, "P" for Put
        exchange: Exchange (default: SMART)
        currency: Currency (default: USD)
        
    Returns:
        IBContract for option
    """
    return IBContract(
        symbol=symbol,
        sec_type=SecurityType.OPTION,
        exchange=exchange,
        currency=currency,
        last_trade_date=last_trade_date,
        strike=strike,
        right=right,
        multiplier=OPTION_MULTIPLIER
    )

def create_market_order(action: OrderAction, quantity: int) -> IBOrder:
    """
    Module-level function to create a market order.
    
    Args:
        action: BUY or SELL
        quantity: Number of contracts/shares
        
    Returns:
        IBOrder for market order
    """
    return IBOrder(
        action=action,
        total_quantity=quantity,
        order_type=OrderType.MARKET
    )

def create_limit_order(
    action: OrderAction, 
    quantity: int, 
    limit_price: float
) -> IBOrder:
    """
    Module-level function to create a limit order.
    
    Args:
        action: BUY or SELL
        quantity: Number of contracts/shares
        limit_price: Limit price
        
    Returns:
        IBOrder for limit order
    """
    return IBOrder(
        action=action,
        total_quantity=quantity,
        order_type=OrderType.LIMIT,
        lmt_price=limit_price
    )

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# Create singleton instance for module-level access
_data_type_manager: Optional[IBDataTypeManager] = None

def get_data_type_manager() -> IBDataTypeManager:
    """
    Get singleton instance of the data type manager.
    
    Returns:
        IBDataTypeManager instance
    """
    global _data_type_manager
    if _data_type_manager is None:
        _data_type_manager = IBDataTypeManager()
    return _data_type_manager

# ==============================================================================
# MODULE EXPORTS
# ==============================================================================
__all__ = [
    # Enums
    "SecurityType",
    "OrderAction", 
    "OrderType",
    "OrderStatus",
    
    # Data structures
    "IBContract",
    "IBOrder",
    "IBPosition", 
    "IBTrade",
    "IBMarketData",
    
    # Type aliases
    "ContractId",
    "OrderId",
    "TickerId",
    
    # Manager class
    "IBDataTypeManager",
    
    # Module functions
    "create_stock_contract",
    "create_option_contract",
    "create_market_order",
    "create_limit_order",
    "get_data_type_manager"
]

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code
    manager = IBDataTypeManager()
    
    print("Testing IB Data Types Module")
    print("=" * 50)
    
    # Test stock contract creation
    spy_stock = manager.create_stock_contract("SPY")
    print(f"✅ Created stock contract: {spy_stock.symbol} ({spy_stock.sec_type.value})")
    
    # Test option contract creation
    spy_option = manager.create_option_contract(
        symbol="SPY",
        last_trade_date="20250620",
        strike=450.0,
        right="C"
    )
    print(f"✅ Created option contract: {spy_option.symbol} {spy_option.last_trade_date} "
          f"{spy_option.right}{spy_option.strike}")
    
    # Test order creation
    buy_order = manager.create_limit_order(OrderAction.BUY, 10, 5.50)
    print(f"✅ Created limit order: {buy_order.action.value} {buy_order.total_quantity} "
          f"@ ${buy_order.lmt_price}")
    
    # Test validation
    if manager.validate_contract(spy_stock):
        print("✅ Stock contract validation passed")
    
    if manager.validate_contract(spy_option):
        print("✅ Option contract validation passed")
    
    if manager.validate_order(buy_order):
        print("✅ Order validation passed")
    
    print("\n✅ All tests passed!")