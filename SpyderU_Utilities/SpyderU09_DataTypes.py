#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderU09_DataTypes.py
Group: U (Utilities)
Purpose: Common data type definitions for market data, orders, and positions

Description:
    This module defines common data structures used throughout the Spyder system
    for market data representation, order management, position tracking, and
    account information. These data types serve as the foundation for 
    communication between different modules.

Author: Mohamed Talib
Date: 2025-01-27
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
# None required for this module

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
# None - this is a foundational module

# ==============================================================================
# ENUMS
# ==============================================================================
class BarType(Enum):
    """Bar data types for different timeframes"""
    TICK = "TICK"
    SECOND = "1S"
    MINUTE = "1M"
    MINUTE_5 = "5M"
    MINUTE_15 = "15M"
    HOUR = "1H"
    DAILY = "1D"

class OrderType(Enum):
    """Order types supported by the system"""
    MARKET = "MKT"
    LIMIT = "LMT"
    STOP = "STP"
    STOP_LIMIT = "STP_LMT"

class OrderStatus(Enum):
    """Order status states"""
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    PARTIAL = "PARTIAL"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"

class OptionRight(Enum):
    """Option contract rights"""
    CALL = "CALL"
    PUT = "PUT"

class SecurityType(Enum):
    """Security types"""
    STOCK = "STK"
    OPTION = "OPT"
    FUTURE = "FUT"
    FOREX = "CASH"
    INDEX = "IND"

# ==============================================================================
# DATA CLASSES
# ==============================================================================
class BarData:
    """
    Bar data for candlestick representation.
    
    Attributes:
        symbol: Trading symbol
        timestamp: Bar timestamp
        open: Opening price
        high: Highest price
        low: Lowest price
        close: Closing price
        volume: Volume traded
        bar_type: Type of bar (1M, 5M, etc.)
        vwap: Volume weighted average price
        count: Number of trades
    """
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    bar_type: BarType = BarType.MINUTE
    vwap: Optional[float] = None
    count: Optional[int] = None
    
    def __post_init__(self):
        """Validate bar data"""
        if self.high < self.low:
            raise ValueError(f"High {self.high} cannot be less than low {self.low}")
        if self.open < self.low or self.open > self.high:
            raise ValueError(f"Open {self.open} outside of high/low range")
        if self.close < self.low or self.close > self.high:
            raise ValueError(f"Close {self.close} outside of high/low range")

class TickData:
    """
    Tick data for real-time updates.
    
    Attributes:
        symbol: Trading symbol
        timestamp: Tick timestamp
        price: Last traded price
        size: Trade size
        bid: Best bid price
        ask: Best ask price
        bid_size: Bid size
        ask_size: Ask size
        volume: Cumulative volume
    """
    symbol: str
    timestamp: datetime
    price: float
    size: int = 0
    bid: Optional[float] = None
    ask: Optional[float] = None
    bid_size: Optional[int] = None
    ask_size: Optional[int] = None
    volume: Optional[int] = None
    
    @property
    def spread(self) -> Optional[float]:
        """Calculate bid-ask spread"""
        if self.bid is not None and self.ask is not None:
            return self.ask - self.bid
        return None

class OrderData:
    """
    Order information.
    
    Attributes:
        order_id: Unique order identifier
        symbol: Trading symbol
        order_type: Type of order
        action: BUY or SELL
        quantity: Number of contracts
        limit_price: Limit price (for limit orders)
        stop_price: Stop price (for stop orders)
        status: Order status
        filled_quantity: Quantity filled
        average_fill_price: Average fill price
        timestamp: Order creation time
        metadata: Additional order data
    """
    order_id: str
    symbol: str
    order_type: OrderType
    action: str  # BUY or SELL
    quantity: int
    status: OrderStatus = OrderStatus.PENDING
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    filled_quantity: int = 0
    average_fill_price: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_filled(self) -> bool:
        """Check if order is completely filled"""
        return self.status == OrderStatus.FILLED
    
    @property
    def is_active(self) -> bool:
        """Check if order is still active"""
        return self.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIAL]

class PositionData:
    """
    Position information.
    
    Attributes:
        symbol: Trading symbol
        quantity: Position size (positive for long, negative for short)
        average_cost: Average entry price
        current_price: Current market price
        unrealized_pnl: Unrealized profit/loss
        realized_pnl: Realized profit/loss
        timestamp: Last update time
    """
    symbol: str
    quantity: int
    average_cost: float
    current_price: Optional[float] = None
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def market_value(self) -> float:
        """Calculate current market value"""
        if self.current_price:
            return self.quantity * self.current_price * 100  # SPY multiplier
        return self.quantity * self.average_cost * 100
    
    @property
    def is_long(self) -> bool:
        """Check if position is long"""
        return self.quantity > 0
    
    @property
    def is_short(self) -> bool:
        """Check if position is short"""
        return self.quantity < 0

class AccountData:
    """
    Account information.
    
    Attributes:
        account_id: Account identifier
        balance: Account balance
        buying_power: Available buying power
        positions: List of positions
        timestamp: Last update time
    """
    account_id: str
    balance: float
    buying_power: float
    positions: List[PositionData] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def total_market_value(self) -> float:
        """Calculate total market value of all positions"""
        return sum(pos.market_value for pos in self.positions)
    
    @property
    def total_unrealized_pnl(self) -> float:
        """Calculate total unrealized P&L"""
        return sum(pos.unrealized_pnl for pos in self.positions)

class ContractData:
    """
    Contract specifications.
    
    Attributes:
        symbol: Trading symbol
        security_type: Security type (STK, OPT, etc.)
        exchange: Exchange
        currency: Currency
        multiplier: Contract multiplier
        expiry: Expiration date (for options)
        strike: Strike price (for options)
        right: PUT or CALL (for options)
    """
    symbol: str
    security_type: str = "STK"
    exchange: str = "SMART"
    currency: str = "USD"
    multiplier: int = 100
    expiry: Optional[datetime] = None
    strike: Optional[float] = None
    right: Optional[str] = None  # PUT or CALL
    
    @property
    def is_option(self) -> bool:
        """Check if contract is an option"""
        return self.security_type == "OPT"
    
    @property
    def is_expired(self) -> bool:
        """Check if option is expired"""
        if self.expiry:
            return datetime.now() > self.expiry
        return False

class OptionData:
    """
    Option-specific data with Greeks.
    
    Attributes:
        contract: Contract specifications
        bid: Bid price
        ask: Ask price
        last: Last traded price
        volume: Volume
        open_interest: Open interest
        implied_volatility: Implied volatility
        delta: Option delta
        gamma: Option gamma
        theta: Option theta
        vega: Option vega
        timestamp: Data timestamp
    """
    contract: ContractData
    bid: float
    ask: float
    last: float
    volume: int = 0
    open_interest: int = 0
    implied_volatility: Optional[float] = None
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def mid_price(self) -> float:
        """Calculate mid price"""
        return (self.bid + self.ask) / 2
    
    @property
    def spread(self) -> float:
        """Calculate bid-ask spread"""
        return self.ask - self.bid
    
    @property
    def spread_percentage(self) -> float:
        """Calculate spread as percentage of mid price"""
        if self.mid_price > 0:
            return (self.spread / self.mid_price) * 100
        return 0.0

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================
def create_bar_from_ticks(ticks: List[TickData], bar_type: BarType) -> Optional[BarData]:
    """
    Create a bar from a list of ticks.
    
    Args:
        ticks: List of tick data
        bar_type: Type of bar to create
        
    Returns:
        BarData object or None if no ticks
    """
    if not ticks:
        return None
    
    first_tick = ticks[0]
    last_tick = ticks[-1]
    
    # Calculate VWAP
    total_value = sum(t.price * t.size for t in ticks if t.size > 0)
    total_volume = sum(t.size for t in ticks if t.size > 0)
    vwap = total_value / total_volume if total_volume > 0 else last_tick.price
    
    return BarData(
        symbol=first_tick.symbol,
        timestamp=first_tick.timestamp,
        open=first_tick.price,
        high=max(t.price for t in ticks),
        low=min(t.price for t in ticks),
        close=last_tick.price,
        volume=total_volume,
        bar_type=bar_type,
        vwap=vwap,
        count=len(ticks)
    )

def create_option_contract(
    symbol: str,
    expiry: datetime,
    strike: float,
    right: str,
    exchange: str = "SMART"
) -> ContractData:
    """
    Create an option contract.
    
    Args:
        symbol: Underlying symbol
        expiry: Expiration date
        strike: Strike price
        right: PUT or CALL
        exchange: Exchange (default: SMART)
        
    Returns:
        ContractData object for option
    """
    return ContractData(
        symbol=symbol,
        security_type="OPT",
        exchange=exchange,
        currency="USD",
        multiplier=100,
        expiry=expiry,
        strike=strike,
        right=right
    )

def calculate_position_pnl(
    position: PositionData,
    current_price: float
) -> tuple[float, float]:
    """
    Calculate position P&L.
    
    Args:
        position: Position data
        current_price: Current market price
        
    Returns:
        Tuple of (unrealized_pnl, total_pnl)
    """
    # Update position with current price
    position.current_price = current_price
    
    # Calculate unrealized P&L
    if position.quantity != 0:
        position.unrealized_pnl = (
            (current_price - position.average_cost) * position.quantity * 100
        )
    else:
        position.unrealized_pnl = 0.0
    
    # Total P&L
    total_pnl = position.unrealized_pnl + position.realized_pnl
    
    return position.unrealized_pnl, total_pnl

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test data structures
    import json
    
    # Test BarData
    bar = BarData(
        symbol="SPY",
        timestamp=datetime.now(),
        open=450.00,
        high=451.50,
        low=449.50,
        close=451.00,
        volume=1000000,
        bar_type=BarType.MINUTE
    )
    print(f"Bar Data: {bar}")
    
    # Test TickData
    tick = TickData(
        symbol="SPY",
        timestamp=datetime.now(),
        price=450.50,
        size=100,
        bid=450.45,
        ask=450.55
    )
    print(f"Tick Spread: ${tick.spread:.2f}")
    
    # Test OrderData
    order = OrderData(
        order_id="ORD123",
        symbol="SPY",
        order_type=OrderType.LIMIT,
        action="BUY",
        quantity=10,
        limit_price=450.00
    )
    print(f"Order Active: {order.is_active}")
    
    # Test create_option_contract
    option_contract = create_option_contract(
        symbol="SPY",
        expiry=datetime(2025, 2, 21),
        strike=450.0,
        right="CALL"
    )
    print(f"Option Contract: {option_contract.symbol} {option_contract.strike} {option_contract.right}")

# FeatureSet for ML features
from dataclasses import dataclass
from typing import Dict, Any, Optional

@dataclass
class FeatureSet:
    features: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None

