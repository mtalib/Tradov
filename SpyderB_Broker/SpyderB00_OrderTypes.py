#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderB00_OrderTypes.py
Group: B (Broker Integration)
Purpose: Common order data structures for broker modules
Author: Mohamed Talib
Date Created: 2025-01-27
Last Updated: 2025-01-27 Time: 14:00:00

Description:
    This module provides common order-related data structures used across
    the broker integration modules. It defines OrderRequest, OrderAction,
    OrderType and other shared classes to ensure consistency.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Dict, Any
from datetime import datetime

# ==============================================================================
# ENUMS
# ==============================================================================
class OrderAction(Enum):
    """Order action types"""
    BUY = "BUY"
    SELL = "SELL"
    
class OrderType(Enum):
    """Order types"""
    MARKET = "MKT"
    LIMIT = "LMT"
    STOP = "STP"
    STOP_LIMIT = "STP LMT"
    
class OrderStatus(Enum):
    """Order status"""
    PENDING = "PendingSubmit"
    SUBMITTED = "Submitted"
    FILLED = "Filled"
    CANCELLED = "Cancelled"
    REJECTED = "Rejected"
    PARTIAL = "PartiallyFilled"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class OrderRequest:
    """Order request data structure for OrderManager"""
    symbol: str
    action: OrderAction
    quantity: int
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str = "DAY"
    account: Optional[str] = None
    strategy_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> bool:
        """Validate order request."""
        if self.quantity <= 0:
            return False
        if self.order_type == OrderType.LIMIT and self.limit_price is None:
            return False
        if self.order_type == OrderType.STOP and self.stop_price is None:
            return False
        return True

@dataclass
class OrderResponse:
    """Order response from broker"""
    order_id: str
    status: OrderStatus
    filled_quantity: int = 0
    avg_fill_price: float = 0.0
    commission: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

# ==============================================================================
# EXPORTS
# ==============================================================================
__all__ = [
    'OrderAction',
    'OrderType', 
    'OrderStatus',
    'OrderRequest',
    'OrderResponse'
]
