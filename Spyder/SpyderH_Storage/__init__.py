import logging
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderH_Storage
Purpose: Data Storage and Management

This package handles all data storage operations including database
management, caching, and data persistence.

Author: Mohamed Talib
Date: 2025-06-24
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS (DEFENSIVE)
# ==============================================================================
__all__ = []

# Data Access Layer (main storage interface)
try:
    from .SpyderH01_DataAccessLayer import (DataAccessLayer,
                                            get_data_access_layer)

    __all__.extend(["DataAccessLayer", "get_data_access_layer"])
except ImportError:
    logging.info("Warning: SpyderH01_DataAccessLayer not available")

# Trade Repository
try:
    from .SpyderH04_TradeRepository import TradeRepository

    __all__.extend(["TradeRepository"])
except ImportError:
    logging.info("Warning: SpyderH04_TradeRepository not available")

# Market Data Cache
try:
    from .SpyderH03_MarketDataCache import MarketDataCache

    __all__.extend(["MarketDataCache"])
except ImportError:
    logging.info("Warning: SpyderH03_MarketDataCache not available")

# Performance Analytics Storage
try:
    from .SpyderH07_PerformanceAnalytics import PerformanceAnalytics

    __all__.extend(["PerformanceAnalytics"])
except ImportError:
    logging.info("Warning: SpyderH07_PerformanceAnalytics not available")

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderH_Storage"
__description__ = "Data Storage and Management"
__version__ = "1.4.0"
