#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System
SpyderB_Broker Package

This package handles all broker interactions, primarily with Interactive Brokers Gateway.
Uses ib-insync library (NO IBAPI dependencies).
"""

# Version
__version__ = '1.5.0'

# Main imports
try:
    from .SpyderB01_SpyderClient import SpyderClient, get_spyder_client
    HAS_SPYDER_CLIENT = True
except ImportError:
    print("WARNING: SpyderClient not available")
    HAS_SPYDER_CLIENT = False

# Connection Manager (merged from B07)
try:
    from .SpyderB05_ConnectionManager import ConnectionManager, get_connection_manager, ConnectionConfig
    HAS_CONNECTION_MANAGER = True
except ImportError:
    print("WARNING: ConnectionManager not available")
    HAS_CONNECTION_MANAGER = False

# Order Manager
try:
    from .SpyderB02_OrderManager import OrderManager, create_order_manager
    HAS_ORDER_MANAGER = True
except ImportError:
    HAS_ORDER_MANAGER = False

# Position Tracker
try:
    from .SpyderB03_PositionTracker import PositionTracker
    HAS_POSITION_TRACKER = True
except ImportError:
    HAS_POSITION_TRACKER = False

# Account Manager
try:
    from .SpyderB04_AccountManager import AccountManager, create_account_manager
    HAS_ACCOUNT_MANAGER = True
except ImportError:
    HAS_ACCOUNT_MANAGER = False

# Contract Builder
try:
    from .SpyderB06_ContractBuilder import ContractBuilder
    HAS_CONTRACT_BUILDER = True
except ImportError:
    HAS_CONTRACT_BUILDER = False

# Gateway Automation
try:
    from .SpyderB12_GatewayAutomation import GatewayAutomation, create_gateway_automation, GatewayConfig
    HAS_GATEWAY_AUTOMATION = True
except ImportError:
    HAS_GATEWAY_AUTOMATION = False

# Type aliases
TickerId = int

# Public API
__all__ = [
    'SpyderClient',
    'get_spyder_client',
    'ConnectionManager',
    'get_connection_manager',
    'ConnectionConfig',
    'OrderManager',
    'create_order_manager',
    'PositionTracker',
    'AccountManager',
    'create_account_manager',
    'ContractBuilder',
    'GatewayAutomation',
    'create_gateway_automation',
    'GatewayConfig',
    'TickerId',
]

# Conditional exports
if HAS_SPYDER_CLIENT:
    __all__.extend(['HAS_SPYDER_CLIENT'])
if HAS_CONNECTION_MANAGER:
    __all__.extend(['HAS_CONNECTION_MANAGER'])
if HAS_ORDER_MANAGER:
    __all__.extend(['HAS_ORDER_MANAGER'])
if HAS_POSITION_TRACKER:
    __all__.extend(['HAS_POSITION_TRACKER'])
if HAS_ACCOUNT_MANAGER:
    __all__.extend(['HAS_ACCOUNT_MANAGER'])
if HAS_CONTRACT_BUILDER:
    __all__.extend(['HAS_CONTRACT_BUILDER'])
if HAS_GATEWAY_AUTOMATION:
    __all__.extend(['HAS_GATEWAY_AUTOMATION'])