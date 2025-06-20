#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System
SpyderB_Broker Package

This package handles all broker interactions, primarily with Interactive Brokers Gateway.
"""

# Version
__version__ = '1.0.0'

# Package imports
from .SpyderB01_SpyderClient import SpyderClient, get_spyder_client, TickerId
from .SpyderB02_OrderManager import OrderManager
from .SpyderB03_PositionTracker import PositionTracker
from .SpyderB04_AccountManager import AccountManager
from .SpyderB05_ConnectionManager import ConnectionManager
from .SpyderB06_ContractBuilder import ContractBuilder
from .SpyderB09_IBClientPortal import SpyderClientPortal

# Public API
__all__ = [
    'SpyderClient',
    'get_spyder_client',
    'TickerId',
    'OrderManager',
    'PositionTracker',
    'AccountManager',
    'ConnectionManager',
    'ContractBuilder',
]
