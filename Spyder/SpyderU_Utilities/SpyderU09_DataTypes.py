#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderU09_DataTypes.py
Group: U (Utilities)
Purpose: Core data type definitions and structures

Description:
    This module defines all core data types and structures used throughout
    the Spyder trading system. It includes market data structures, order
    definitions, position tracking, option contracts, and other fundamental
    data types that ensure type safety and consistency across the platform.

Author: Mohamed Talib
Date Created: 2025-07-18
Last Updated: 2025-07-18 Time: 11:45:00

"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, date
import json

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Market data constants
MARKET_DATA_FIELDS = [
    "bid", "ask", "last", "volume", "open", "high", "low", "close",
    "bid_size", "ask_size", "last_size", "open_interest"
]

# Option constants
OPTION_RIGHTS = ["CALL", "PUT"]
OPTION_STYLES = ["AMERICAN", "EUROPEAN"]

# Order constants
ORDER_TYPES = ["MKT", "LMT", "STP", "STP_LMT", "TRAIL", "TRAIL_LIMIT"]
ORDER_ACTIONS = ["BUY", "SELL"]
ORDER_STATUS = ["Submitted", "Filled", "Cancelled", "PendingSubmit", "PendingCancel"]

# ==============================================================================
# ENUMS
# ==============================================================================
class OptionRight(Enum):
    """Option contract right"""
    CALL = "CALL"
    PUT = "PUT"

class OptionStyle(Enum):
    """Option exercise style"""
    AMERICAN = "AMERICAN"
    EUROPEAN = "EUROPEAN"

class OrderType(Enum):
    """Order types"""
    MARKET = "MKT"
    LIMIT = "LMT"
    STOP = "STP"
    STOP_LIMIT = "STP_LMT"
    TRAILING_STOP = "TRAIL"
    TRAILING_LIMIT = "TRAIL_LIMIT"

class OrderAction(Enum):
    """Order actions"""
    BUY = "BUY"
    SELL = "SELL"

class OrderStatus(Enum):
    """Order status"""
    SUBMITTED = "Submitted"
    FILLED = "Filled"
    CANCELLED = "Cancelled"
    PENDING_SUBMIT = "PendingSubmit"
    PENDING_CANCEL = "PendingCancel"
    INACTIVE = "Inactive"
    PENDING_MODIFY = "PendingModify"

class PositionSide(Enum):
    """Position side"""
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"

class DataQuality(Enum):
    """Market data quality"""
    REAL_TIME = "real_time"
    DELAYED = "delayed"
    FROZEN = "frozen"
    HALTED = "halted"
    UNKNOWN = "unknown"

# ==============================================================================
# CORE DATA STRUCTURES
# ==============================================================================
@dataclass
class MarketData:
    """
    Core market data structure for all instruments.
    
    This is the primary data structure for market data throughout the
    Spyder system. It provides real-time and historical price information
    with timestamp tracking and data quality indicators.
    
    Attributes:
        symbol: Instrument symbol
        bid: Current bid price
        ask: Current ask price
        last: Last traded price
        volume: Trading volume
        bid_size: Bid quantity
        ask_size: Ask quantity
        last_size: Last trade size
        open: Opening price
        high: High price
        low: Low price
        close: Closing price
        timestamp: Data timestamp
        quality: Data quality indicator
    """
    symbol: str
    bid: float = 0.0
    ask: float = 0.0
    last: float = 0.0
    volume: int = 0
    bid_size: int = 0
    ask_size: int = 0
    last_size: int = 0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    quality: DataQuality = DataQuality.UNKNOWN
    
    def __post_init__(self):
        """Post-initialization validation."""
        if not self.symbol:
            raise ValueError("Symbol cannot be empty")
    
    @property
    def mid_price(self) -> float:
        """Calculate mid price from bid/ask."""
        if self.bid > 0 and self.ask > 0:
            return (self.bid + self.ask) / 2.0
        return self.last
    
    @property
    def spread(self) -> float:
        """Calculate bid-ask spread."""
        if self.bid > 0 and self.ask > 0:
            return self.ask - self.bid
        return 0.0
    
    @property
    def spread_percent(self) -> float:
        """Calculate spread as percentage of mid price."""
        mid = self.mid_price
        if mid > 0 and self.spread > 0:
            return (self.spread / mid) * 100.0
        return 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "bid": self.bid,
            "ask": self.ask,
            "last": self.last,
            "volume": self.volume,
            "bid_size": self.bid_size,
            "ask_size": self.ask_size,
            "last_size": self.last_size,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "timestamp": self.timestamp.isoformat(),
            "quality": self.quality.value,
            "mid_price": self.mid_price,
            "spread": self.spread
        }

@dataclass
class OptionContract:
    """Option contract specification."""
    symbol: str
    underlying: str
    expiry: date
    strike: float
    right: OptionRight
    style: OptionStyle = OptionStyle.AMERICAN
    multiplier: int = 100
    exchange: str = "SMART"
    currency: str = "USD"
    
    def __post_init__(self):
        """Post-initialization validation."""
        if self.strike <= 0:
            raise ValueError("Strike must be positive")
        if self.multiplier <= 0:
            raise ValueError("Multiplier must be positive")
    
    @property
    def option_symbol(self) -> str:
        """Generate option symbol."""
        expiry_str = self.expiry.strftime("%y%m%d")
        right_str = "C" if self.right == OptionRight.CALL else "P"
        strike_str = f"{int(self.strike * 1000):08d}"
        return f"{self.underlying}{expiry_str}{right_str}{strike_str}"
    
    @property
    def days_to_expiry(self) -> int:
        """Calculate days to expiry."""
        return (self.expiry - date.today()).days
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "underlying": self.underlying,
            "expiry": self.expiry.isoformat(),
            "strike": self.strike,
            "right": self.right.value,
            "style": self.style.value,
            "multiplier": self.multiplier,
            "exchange": self.exchange,
            "currency": self.currency,
            "option_symbol": self.option_symbol,
            "days_to_expiry": self.days_to_expiry
        }

@dataclass
class OrderData:
    """Order information structure."""
    order_id: int
    symbol: str
    action: OrderAction
    order_type: OrderType
    quantity: int
    price: float = 0.0
    aux_price: float = 0.0  # Stop price for stop orders
    status: OrderStatus = OrderStatus.SUBMITTED
    filled_quantity: int = 0
    remaining_quantity: int = 0
    avg_fill_price: float = 0.0
    commission: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    parent_id: Optional[int] = None
    oca_group: Optional[str] = None
    good_after_time: Optional[datetime] = None
    good_till_date: Optional[datetime] = None
    
    def __post_init__(self):
        """Post-initialization validation."""
        if self.quantity <= 0:
            raise ValueError("Quantity must be positive")
        self.remaining_quantity = self.quantity - self.filled_quantity
    
    @property
    def is_filled(self) -> bool:
        """Check if order is completely filled."""
        return self.filled_quantity >= self.quantity
    
    @property
    def is_active(self) -> bool:
        """Check if order is active."""
        return self.status in [OrderStatus.SUBMITTED, OrderStatus.PENDING_SUBMIT]
    
    @property
    def fill_percentage(self) -> float:
        """Calculate fill percentage."""
        return (self.filled_quantity / self.quantity) * 100.0 if self.quantity > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "action": self.action.value,
            "order_type": self.order_type.value,
            "quantity": self.quantity,
            "price": self.price,
            "aux_price": self.aux_price,
            "status": self.status.value,
            "filled_quantity": self.filled_quantity,
            "remaining_quantity": self.remaining_quantity,
            "avg_fill_price": self.avg_fill_price,
            "commission": self.commission,
            "timestamp": self.timestamp.isoformat(),
            "parent_id": self.parent_id,
            "oca_group": self.oca_group,
            "is_filled": self.is_filled,
            "is_active": self.is_active,
            "fill_percentage": self.fill_percentage
        }

@dataclass
class Position:
    """Position tracking structure."""
    symbol: str
    quantity: int
    avg_cost: float
    market_price: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Calculate derived values."""
        self.update_market_values()
    
    @property
    def side(self) -> PositionSide:
        """Get position side."""
        if self.quantity > 0:
            return PositionSide.LONG
        elif self.quantity < 0:
            return PositionSide.SHORT
        else:
            return PositionSide.FLAT
    
    @property
    def total_pnl(self) -> float:
        """Calculate total P&L."""
        return self.realized_pnl + self.unrealized_pnl
    
    def update_market_values(self) -> None:
        """Update market values based on current price."""
        if self.market_price > 0:
            self.market_value = self.quantity * self.market_price
            self.unrealized_pnl = (self.market_price - self.avg_cost) * self.quantity
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "avg_cost": self.avg_cost,
            "market_price": self.market_price,
            "market_value": self.market_value,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "total_pnl": self.total_pnl,
            "side": self.side.value,
            "timestamp": self.timestamp.isoformat()
        }

@dataclass
class GreeksData:
    """Option Greeks data structure."""
    symbol: str
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0
    implied_volatility: float = 0.0
    underlying_price: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "delta": self.delta,
            "gamma": self.gamma,
            "theta": self.theta,
            "vega": self.vega,
            "rho": self.rho,
            "implied_volatility": self.implied_volatility,
            "underlying_price": self.underlying_price,
            "timestamp": self.timestamp.isoformat()
        }

@dataclass
class TradeExecution:
    """Trade execution record."""
    execution_id: str
    order_id: int
    symbol: str
    side: str
    quantity: int
    price: float
    commission: float
    timestamp: datetime
    exchange: str = ""
    
    @property
    def notional_value(self) -> float:
        """Calculate notional value."""
        return abs(self.quantity * self.price)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "execution_id": self.execution_id,
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "commission": self.commission,
            "timestamp": self.timestamp.isoformat(),
            "exchange": self.exchange,
            "notional_value": self.notional_value
        }

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class SpyderDataTypes:
    """
    Data types manager and factory.
    
    This class provides utilities for creating, validating, and managing
    all data types used in the Spyder system. It includes factory methods
    for common data structures and validation utilities.
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        
    Example:
        >>> data_types = SpyderDataTypes()
        >>> market_data = data_types.create_market_data("SPY", 450.0, 450.1)
        >>> option = data_types.create_option_contract("SPY", "2024-12-20", 450.0, "CALL")
    """
    
    def __init__(self):
        """Initialize the data types manager."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        self.logger.info(f"{self.__class__.__name__} initialized")
    
    # ==========================================================================
    # FACTORY METHODS
    # ==========================================================================
    def create_market_data(self, symbol: str, bid: float = 0.0, ask: float = 0.0, 
                          last: float = 0.0, volume: int = 0) -> MarketData:
        """
        Create MarketData instance.
        
        Args:
            symbol: Instrument symbol
            bid: Bid price
            ask: Ask price
            last: Last price
            volume: Volume
            
        Returns:
            MarketData instance
        """
        try:
            return MarketData(
                symbol=symbol,
                bid=bid,
                ask=ask,
                last=last,
                volume=volume,
                timestamp=datetime.now()
            )
        except Exception as e:
            self.logger.error(f"Failed to create MarketData: {e}")
            raise
    
    def create_option_contract(self, underlying: str, expiry: str, strike: float, 
                              right: str) -> OptionContract:
        """
        Create OptionContract instance.
        
        Args:
            underlying: Underlying symbol
            expiry: Expiry date (YYYY-MM-DD)
            strike: Strike price
            right: CALL or PUT
            
        Returns:
            OptionContract instance
        """
        try:
            expiry_date = datetime.strptime(expiry, "%Y-%m-%d").date()
            option_right = OptionRight(right.upper())
            
            # Generate option symbol
            symbol = f"{underlying}_{expiry}_{strike}_{right}"
            
            return OptionContract(
                symbol=symbol,
                underlying=underlying,
                expiry=expiry_date,
                strike=strike,
                right=option_right
            )
        except Exception as e:
            self.logger.error(f"Failed to create OptionContract: {e}")
            raise
    
    def create_order(self, symbol: str, action: str, order_type: str, 
                    quantity: int, price: float = 0.0) -> OrderData:
        """
        Create OrderData instance.
        
        Args:
            symbol: Symbol to trade
            action: BUY or SELL
            order_type: Order type
            quantity: Order quantity
            price: Order price (for limit orders)
            
        Returns:
            OrderData instance
        """
        try:
            return OrderData(
                order_id=0,  # Will be set by order manager
                symbol=symbol,
                action=OrderAction(action.upper()),
                order_type=OrderType(order_type.upper()),
                quantity=quantity,
                price=price
            )
        except Exception as e:
            self.logger.error(f"Failed to create OrderData: {e}")
            raise
    
    # ==========================================================================
    # VALIDATION METHODS
    # ==========================================================================
    def validate_market_data(self, data: MarketData) -> bool:
        """
        Validate MarketData instance.
        
        Args:
            data: MarketData to validate
            
        Returns:
            bool: True if valid
        """
        try:
            if not data.symbol:
                return False
            
            # Check for negative prices
            if any(price < 0 for price in [data.bid, data.ask, data.last]):
                return False
            
            # Check bid/ask consistency
            if data.bid > 0 and data.ask > 0 and data.bid >= data.ask:
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"MarketData validation failed: {e}")
            return False
    
    def validate_option_contract(self, contract: OptionContract) -> bool:
        """
        Validate OptionContract instance.
        
        Args:
            contract: OptionContract to validate
            
        Returns:
            bool: True if valid
        """
        try:
            if not contract.symbol or not contract.underlying:
                return False
            
            if contract.strike <= 0:
                return False
            
            if contract.expiry <= date.today():
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"OptionContract validation failed: {e}")
            return False

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_market_data(symbol: str, **kwargs) -> MarketData:
    """
    Factory function for MarketData.
    
    Args:
        symbol: Instrument symbol
        **kwargs: Additional market data fields
        
    Returns:
        MarketData instance
    """
    data_types = SpyderDataTypes()
    return data_types.create_market_data(symbol, **kwargs)

def create_option_contract(underlying: str, expiry: str, strike: float, right: str) -> OptionContract:
    """
    Factory function for OptionContract.
    
    Args:
        underlying: Underlying symbol
        expiry: Expiry date string
        strike: Strike price
        right: CALL or PUT
        
    Returns:
        OptionContract instance
    """
    data_types = SpyderDataTypes()
    return data_types.create_option_contract(underlying, expiry, strike, right)

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# Module-level initialization code
_data_types_instance: Optional[SpyderDataTypes] = None

def get_data_types() -> SpyderDataTypes:
    """
    Get singleton instance of data types manager.
    
    Returns:
        SpyderDataTypes instance
    """
    global _data_types_instance
    if _data_types_instance is None:
        _data_types_instance = SpyderDataTypes()
    return _data_types_instance

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code
    print("=" * 80)
    print("SPYDER U09 - Data Types Test")
    print("=" * 80)
    
    data_types = SpyderDataTypes()
    
    # Test MarketData
    print("\n1. Testing MarketData...")
    market_data = data_types.create_market_data("SPY", 450.0, 450.1, 450.05, 1000)
    print(f"   Created: {market_data.symbol}")
    print(f"   Mid Price: ${market_data.mid_price:.2f}")
    print(f"   Spread: ${market_data.spread:.2f}")
    print(f"   Valid: {data_types.validate_market_data(market_data)}")
    
    # Test OptionContract
    print("\n2. Testing OptionContract...")
    option = data_types.create_option_contract("SPY", "2024-12-20", 450.0, "CALL")
    print(f"   Created: {option.symbol}")
    print(f"   Option Symbol: {option.option_symbol}")
    print(f"   Days to Expiry: {option.days_to_expiry}")
    print(f"   Valid: {data_types.validate_option_contract(option)}")
    
    # Test OrderData
    print("\n3. Testing OrderData...")
    order = data_types.create_order("SPY", "BUY", "LMT", 100, 450.0)
    print(f"   Created: {order.symbol} {order.action.value}")
    print(f"   Type: {order.order_type.value}")
    print(f"   Quantity: {order.quantity}")
    print(f"   Price: ${order.price:.2f}")
    
    # Test Position
    print("\n4. Testing Position...")
    position = Position("SPY", 100, 445.0, 450.0)
    print(f"   Symbol: {position.symbol}")
    print(f"   Side: {position.side.value}")
    print(f"   Unrealized P&L: ${position.unrealized_pnl:.2f}")
    
    print("\n" + "=" * 80)
    print("✅ Data Types test completed!")

# Add at the end of the file
class PositionData:
    """Data structure for position information"""
    def __init__(self):
        self.symbol = ""
        self.quantity = 0
        self.entry_price = 0.0
        self.current_price = 0.0
        self.pnl = 0.0


@dataclass
class OptionData:
    """
    Option contract data structure
    """
    symbol: str
    expiration: datetime
    strike: float
    option_type: str  # 'call' or 'put'
    bid: float = 0.0
    ask: float = 0.0
    last: float = 0.0
    volume: int = 0
    open_interest: int = 0
    implied_volatility: float = 0.0
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

class MarketDataType(Enum):
    """Market data type enumeration"""
    QUOTE = "quote"
    TRADE = "trade" 
    BAR = "bar"
    TICK = "tick"
    LEVEL2 = "level2"
    OPTIONS_CHAIN = "options_chain"
    GREEKS = "greeks"
    VOLATILITY = "volatility"
    NEWS = "news"
    FUNDAMENTAL = "fundamental"
    UNKNOWN = "unknown"
