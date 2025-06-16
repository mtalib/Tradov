#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderH_Storage
Purpose: Data Persistence

This package provides data persistence functionality for the Spyder trading system.

Author: Mohamed Talib
Date: 2025-06-14
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderH01_DatabaseManager import DatabaseManager, get_database_manager
from .SpyderH02_TradeRepository import TradeRepository, get_trade_repository
from .SpyderH03_MarketDataCache import MarketDataCache
from .SpyderH07_PerformanceAnalytics import PerformanceAnalytics

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    "DatabaseManager",
    "MarketDataCache",
    "PerformanceAnalytics",
    "TradeRepository",
    "get_database_manager",
    "get_trade_repository",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "{package_name}"
__description__ = "{description}"
__version__ = "1.4.0"
