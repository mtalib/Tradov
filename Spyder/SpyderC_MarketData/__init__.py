import logging
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderC_MarketData
Purpose: Market Data Management (Databento)

This package handles all market data operations including real-time feeds,
historical data, option chains, and market internals.

Primary Data Source: Databento (OPRA.PILLAR dataset)

Author: Mohamed Talib
Date: 2025-06-24
Version: 4.0.0 - Provider Abstraction Layer
"""

# ==============================================================================
# MODULE IMPORTS (DEFENSIVE)
# ==============================================================================
__all__ = []

# Provider Protocol (Tradier ↔ Databento swap layer)
try:
    from .SpyderC00_MarketDataProtocol import (
        OptionsDataProvider,
        create_options_data_provider,
    )

    __all__.extend(["OptionsDataProvider", "create_options_data_provider"])
except ImportError as e:
    logging.info(f"Warning: SpyderC00_MarketDataProtocol not available: {e}")

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
        "create_provider",
        "SYMBOL_GROUPS",
    ])
except ImportError as e:
    logging.info(f"Warning: SpyderC01_DataFeed not fully available: {e}")

# Historical Data module
try:
    from .SpyderC02_HistoricalData import HistoricalDataManager

    __all__.extend(["HistoricalDataManager"])
except ImportError:
    logging.info("Warning: SpyderC02_HistoricalData not available")

# Option Chain module
try:
    from .SpyderC03_OptionChain import OptionChainManager

    __all__.extend(["OptionChainManager"])
except ImportError:
    logging.info("Warning: SpyderC03_OptionChain not available")

# Market Internals module
try:
    from .SpyderC04_MarketInternals import MarketInternals

    __all__.extend(["MarketInternals"])
except ImportError:
    logging.info("Warning: SpyderC04_MarketInternals not available")

# Volume Profile module
try:
    from .SpyderC05_VolumeProfile import VolumeProfileAnalyzer

    __all__.extend(["VolumeProfileAnalyzer"])
except ImportError:
    logging.info("Warning: SpyderC05_VolumeProfile not available")

# Data Validator module
try:
    from .SpyderC06_DataValidator import DataValidator

    __all__.extend(["DataValidator"])
except ImportError:
    logging.info("Warning: SpyderC06_DataValidator not available")

# OPRA Feed module
try:
    from .SpyderC07_OPRAFeed import OPRADataFeed

    __all__.extend(["OPRADataFeed"])
except ImportError:
    logging.info("Warning: SpyderC07_OPRAFeed not available")

# SPY Feed module
try:
    from .SpyderC08_SPYFeed import SPYDataFeed

    __all__.extend(["SPYDataFeed"])
except ImportError:
    logging.info("Warning: SpyderC08_SPYFeed not available")

# ==============================================================================
# DATABENTO DATA CLIENT (PRIMARY DATA SOURCE)
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
    logging.info(f"Warning: SpyderC26_DatabentoClient not available: {e}")

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderC_MarketData"
__description__ = "Market Data Management — Provider Abstraction (Databento)"
__version__ = "4.0.0"
