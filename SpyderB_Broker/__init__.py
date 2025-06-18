#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderB_Broker
Purpose: Interactive Brokers Integration

This package provides comprehensive integration with Interactive Brokers,
including client connections, order management, position tracking, and
smart order routing.

Author: Mohamed Talib
Date: 2025-06-18
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderB01_IBClient import IBClient, get_ib_client
from .SpyderB02_OrderManager import OrderManager, Order, OrderStatus
from .SpyderB03_PositionTracker import PositionTracker, Position
from .SpyderB04_AccountManager import AccountManager, AccountInfo
from .SpyderB05_ConnectionManager import ConnectionManager
from .SpyderB06_ContractBuilder import ContractBuilder, create_option_contract
from .SpyderB07_IBConnectionManager import IBConnectionManager
from .SpyderB08_IBGatewayConnection import IBGatewayConnection
from .SpyderB09_IBClientPortal import IBClientPortal
from .SpyderB10_IBDataTypes import IBDataTypes, ContractDetails

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    # IB Client
    "IBClient",
    "get_ib_client",
    
    # Order management
    "OrderManager",
    "Order",
    "OrderStatus",
    
    # Position tracking
    "PositionTracker",
    "Position",
    
    # Account management
    "AccountManager",
    "AccountInfo",
    
    # Connection management
    "ConnectionManager",
    "IBConnectionManager",
    "IBGatewayConnection",
    "IBClientPortal",
    
    # Contract building
    "ContractBuilder",
    "create_option_contract",
    
    # Data types
    "IBDataTypes",
    "ContractDetails",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderB_Broker"
__description__ = "Interactive Brokers Integration"
__version__ = "1.4.0"