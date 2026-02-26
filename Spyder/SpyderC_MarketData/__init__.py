#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderC_MarketData
Purpose: Market Data Management (Databento + Polygon.io Legacy)

This package handles all market data operations including real-time feeds,
historical data, option chains, and market internals.

Primary Data Source: Databento (OPRA.PILLAR dataset)
Legacy Data Source: Polygon.io WebSocket + REST API

Author: Mohamed Talib
Date: 2025-06-24
Version: 4.0.0 - Provider Abstraction Layer
"""

# ==============================================================================
# MODULE IMPORTS (DEFENSIVE)
# ==============================================================================
__all__ = []

# DataFeed module (provider-abstracted)
try:
    from .SpyderC01_DataFeed import (
        DataFeedManager,
        DataFeed,
        get_data_feed_manager,
        MarketTick,
        DataFeedConfig,
        DataFeedStatus,
        DataSource,
        MarketDataProvider,
        DatabentoProvider,
        PolygonProvider,
        create_provider,
        SYMBOL_GROUPS,
    )

    __all__.extend([
        "DataFeedManager",
        "DataFeed",
        "get_data_feed_manager",
        "MarketTick",
        "DataFeedConfig",
        "DataFeedStatus",
        "DataSource",
        "MarketDataProvider",
        "DatabentoProvider",
        "PolygonProvider",
        "create_provider",
        "SYMBOL_GROUPS",
    ])
except ImportError as e:
    print(f"Warning: SpyderC01_DataFeed not fully available: {e}")

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
# POLYGON.IO DATA HANDLER (LEGACY DATA SOURCE)
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
# DATABENTO DATA CLIENT (PRIMARY DATA SOURCE — REPLACING POLYGON.IO)
# ==============================================================================
try:
    from .SpyderC26_DatabentoClient import (
        DatabentoClient,
        MarketDataUpdate as DatabentoMarketUpdate,
        InstrumentDefinition,
        BandwidthTracker,
        ConnectionStatus as DatabentoConnectionStatus,
        DatabentoSchema,
        SymbolFormat,
        convert_symbol,
        databento_to_tradier,
        tradier_to_databento,
        is_option_symbol,
        create_databento_client_from_env,
        create_databento_qt_bridge,
    )
    __all__.extend([
        "DatabentoClient",
        "DatabentoMarketUpdate",
        "InstrumentDefinition",
        "BandwidthTracker",
        "DatabentoConnectionStatus",
        "DatabentoSchema",
        "SymbolFormat",
        "convert_symbol",
        "databento_to_tradier",
        "tradier_to_databento",
        "is_option_symbol",
        "create_databento_client_from_env",
        "create_databento_qt_bridge",
    ])
except ImportError as e:
    print(f"Warning: SpyderC26_DatabentoClient not available: {e}")

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderC_MarketData"
__description__ = "Market Data Management — Provider Abstraction (Databento + Polygon.io Legacy)"
__version__ = "4.0.0"
