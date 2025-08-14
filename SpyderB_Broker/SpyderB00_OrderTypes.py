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
Last Updated: 2025-08-14 Time: 18:00:00

Description:
    This module provides common order-related data structures used across
    the broker integration modules. It defines OrderRequest, OrderAction,
    OrderType and other shared classes to ensure consistency.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, Optional

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
    TRAILING_STOP = "TRAIL"
    MARKET_ON_CLOSE = "MOC"
    LIMIT_ON_CLOSE = "LOC"

class OrderStatus(Enum):
    """Order status"""
    PENDING = "PendingSubmit"
    SUBMITTED = "Submitted"
    FILLED = "Filled"
    CANCELLED = "Cancelled"
    INACTIVE = "Inactive"
    ERROR = "Error"

# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class OrderRequest:
    """Order request structure"""
    symbol: str
    action: OrderAction
    quantity: int
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str = "DAY"
    outside_rth: bool = False
    transmit: bool = True
    account: Optional[str] = None
    order_ref: Optional[str] = None
    parent_id: Optional[int] = None
    oca_group: Optional[str] = None
    oca_type: Optional[int] = None
    trail_stop_price: Optional[float] = None
    trailing_percent: Optional[float] = None
    percent_offset: Optional[float] = None
    trigger_method: Optional[int] = None
    lmt_price_offset: Optional[float] = None
    aux_price: Optional[float] = None
    good_after_time: Optional[str] = None
    good_till_date: Optional[str] = None
    
    def validate(self) -> bool:
        """Validate order request"""
        if self.quantity <= 0:
            return False
        
        if self.order_type == OrderType.LIMIT and self.limit_price is None:
            return False
            
        if self.order_type == OrderType.STOP and self.stop_price is None:
            return False
            
        if self.order_type == OrderType.STOP_LIMIT:
            if self.limit_price is None or self.stop_price is None:
                return False
        
        return True

# ==============================================================================
# EXPORTS
# ==============================================================================

__all__ = [
    'OrderAction',
    'OrderType', 
    'OrderStatus',
    'OrderRequest'
]
