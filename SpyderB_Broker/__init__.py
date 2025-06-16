#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderB_Broker
Purpose: Interactive Brokers Integration

This package provides interactive brokers integration functionality for the Spyder trading system.

Author: Mohamed Talib
Date: 2025-06-14
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderB01_IBClient import IBClient, get_ib_client
from .SpyderB02_OrderManager import OrderManager
from .SpyderB03_PositionTracker import PositionTracker
from .SpyderB04_AccountManager import AccountManager
from .SpyderB05_ConnectionManager import ConnectionManager
from .SpyderB06_ContractBuilder import ContractBuilder, OptionContract
from .SpyderB07_IBConnectionManager import IBConnectionManager
from .SpyderB08_IBGatewayConnection import SpyderIBConnection  # Correct class name
from .SpyderB09_IBClientPortal import IBClientPortal, get_client_portal_client
from .SpyderB10_IBDataTypes import IBContract, IBOrder, IBPosition, IBTrade, IBMarketData

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    "AccountManager",
    "ConnectionManager",
    "ContractBuilder",
    "IBClient",
    "IBClientPortal",
    "IBConnectionManager",
    "IBContract",
    "SpyderIBConnection",  # Correct class name in exports
    "IBMarketData",
    "IBOrder",
    "IBPosition",
    "IBTrade",
    "OptionContract",
    "OrderManager",
    "PositionTracker",
    "get_client_portal_client",
    "get_ib_client",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderB_Broker"
__description__ = "Interactive Brokers Integration"
__version__ = "1.4.0"
