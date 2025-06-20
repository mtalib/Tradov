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
from .SpyderB02_OrderManager import OrderManager, OrderRequest, OrderInfo, OrderStatus
from .SpyderB03_PositionTracker import PositionTracker, Position
from .SpyderB04_AccountManager import AccountManager, AccountBalance
from SpyderU_Utilities.SpyderU09_DataTypes import AccountData
from .SpyderB05_ConnectionManager import ConnectionManager
from .SpyderB06_ContractBuilder import ContractBuilder, OptionRight, OptionSpecification
from .SpyderB07_IBConnectionManager import IBConnectionManager
from .SpyderB08_IBGatewayConnection import SpyderIBConnection
from .SpyderB09_IBClientPortal import IBClientPortal
from .SpyderB10_IBDataTypes import (
    IBDataTypeManager, IBContract, IBOrder, IBPosition, IBTrade, IBMarketData,
    SecurityType, OrderAction, OrderType as IBOrderType, OrderStatus as IBOrderStatus,
    create_option_contract, create_stock_contract
)

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    # IB Client
    "IBClient",
    "get_ib_client",
    
    # Order management - Fixed to use correct class names
    "OrderManager",
    "OrderRequest",
    "OrderInfo",
    "OrderStatus",
    
    # Position tracking
    "PositionTracker",
    "Position",
    
    # Account management - Fixed to use correct class names
    "AccountManager",
    "AccountBalance",
    "AccountData",
    
    # Connection management
    "ConnectionManager",
    "IBConnectionManager",
    "SpyderIBConnection",
    "IBClientPortal",
    
    # Contract building - Fixed imports
    "ContractBuilder",
    "OptionRight",
    "OptionSpecification",
    "create_option_contract",
    
    # Data types - Fixed to use correct classes
    "IBDataTypeManager",
    "IBContract",
    "IBOrder",
    "IBPosition",
    "IBTrade",
    "IBMarketData",
    "SecurityType",
    "create_stock_contract",
]

# ==============================================================================
# CONVENIENCE ALIASES
# ==============================================================================
# For backward compatibility, create aliases
Order = OrderInfo
AccountInfo = AccountData  # Alias for compatibility
IBGatewayConnection = SpyderIBConnection  # Alias for compatibility
IBDataTypes = IBDataTypeManager  # Alias for compatibility
ContractDetails = IBContract  # Alias for compatibility

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderB_Broker"
__description__ = "Interactive Brokers Integration"
__version__ = "1.4.0"
