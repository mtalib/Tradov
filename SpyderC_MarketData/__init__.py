#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderC_MarketData
Purpose: Market Data Management (Polygon.io Integration)

This package handles all market data operations including real-time feeds,
historical data, option chains, and market internals.

Primary Data Source: Polygon.io WebSocket + REST API

Author: Mohamed Talib
Date: 2025-06-24
Version: 2.0 - Tradier/Polygon Migration
"""

# ==============================================================================
# MODULE IMPORTS (DEFENSIVE)
# ==============================================================================
__all__ = []

# DataFeed module
try:
    from .SpyderC01_DataFeed import DataFeedManager, get_data_feed_manager

    __all__.extend(["DataFeedManager", "get_data_feed_manager"])
except ImportError:
    print("Warning: SpyderC01_DataFeed not fully available")

# Historical Data module
try:
    from .SpyderC02_HistoricalData import HistoricalDataManager

    __all__.extend(["HistoricalDataManager"])
except ImportError:
    print("Warning: SpyderC02_HistoricalData not available")

# Option Chain module
try:
    from .SpyderC03_OptionChain import OptionChainManager

    __all__.extend(["OptionChainManager"])
except ImportError:
    print("Warning: SpyderC03_OptionChain not available")

# Market Internals module
try:
    from .SpyderC04_MarketInternals import MarketInternals

    __all__.extend(["MarketInternals"])
except ImportError:
    print("Warning: SpyderC04_MarketInternals not available")

# Volume Profile module
try:
    from .SpyderC05_VolumeProfile import VolumeProfileAnalyzer

    __all__.extend(["VolumeProfileAnalyzer"])
except ImportError:
    print("Warning: SpyderC05_VolumeProfile not available")

# Data Validator module
try:
    from .SpyderC06_DataValidator import DataValidator

    __all__.extend(["DataValidator"])
except ImportError:
    print("Warning: SpyderC06_DataValidator not available")

# OPRA Feed module
try:
    from .SpyderC07_OPRAFeed import OPRADataFeed

    __all__.extend(["OPRADataFeed"])
except ImportError:
    print("Warning: SpyderC07_OPRAFeed not available")

# SPY Feed module
try:
    from .SpyderC08_SPYFeed import SPYDataFeed

    __all__.extend(["SPYDataFeed"])
except ImportError:
    print("Warning: SpyderC08_SPYFeed not available")

# ==============================================================================
# POLYGON.IO DATA HANDLER (PRIMARY DATA SOURCE)
# ==============================================================================
try:
    from .SpyderC25_PolygonDataHandler import (
        PolygonDataHandler,
        MarketDataUpdate,
        ConnectionStatus,
        MessageType,
        create_polygon_handler_from_env,
    )
    __all__.extend([
        "PolygonDataHandler",
        "MarketDataUpdate",
        "ConnectionStatus",
        "MessageType",
        "create_polygon_handler_from_env",
    ])
except ImportError as e:
    print(f"Warning: SpyderC25_PolygonDataHandler not available: {e}")

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderC_MarketData"
__description__ = "Market Data Management (Polygon.io)"
__version__ = "2.0.0"
