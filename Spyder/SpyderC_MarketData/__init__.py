#!/usr/bin/env python3
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderC_MarketData
Purpose: Market Data Management (Massive)

This package handles all market data operations including real-time feeds,
historical data, option chains, and market internals.

Primary Data Source: Massive (SpyderC27_MassiveClient — live and paper trading)

Author: Mohamed Talib
Date: 2025-06-24
Version: 5.0.0 - Provider Abstraction Layer
"""
import logging

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
    logging.info("Warning: SpyderC00_MarketDataProtocol not available: %s", e)

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
    logging.info("Warning: SpyderC01_DataFeed not fully available: %s", e)

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

# SPY Feed module
try:
    from .SpyderC08_SPYFeed import SPYDataFeed

    __all__.extend(["SPYDataFeed"])
except ImportError:
    logging.info("Warning: SpyderC08_SPYFeed not available")

# ==============================================================================
# MASSIVE MARKET DATA CLIENT (PRIMARY DATA SOURCE)
# ==============================================================================
try:
    from .SpyderC27_MassiveClient import (
        MassiveClient,
        MassiveQuoteUpdate,
        MassiveTradeUpdate,
        ConnectionStatus as MassiveConnectionStatus,
        create_massive_client_from_env,
    )
    __all__.extend([
        "MassiveClient",
        "MassiveQuoteUpdate",
        "MassiveTradeUpdate",
        "MassiveConnectionStatus",
        "create_massive_client_from_env",
    ])
except ImportError as e:
    logging.info("Warning: SpyderC27_MassiveClient not available: %s", e)

# SpyderC29 — DataProviderRouter
try:
    from .SpyderC29_DataProviderRouter import (
        DataProvider,
        DataProviderRouter,
        get_data_provider,
    )
    __all__.extend([
        "DataProvider",
        "DataProviderRouter",
        "get_data_provider",
    ])
except ImportError as e:
    logging.info("Warning: SpyderC29_DataProviderRouter not available: %s", e)

# C10–C19, C22–C24, C30, C35 — additional market data modules
try:
    from .SpyderC10_VIXAnalyzer import VIXAnalyzer
    __all__.extend(["VIXAnalyzer"])
except ImportError as e:
    logging.info("Warning: SpyderC10_VIXAnalyzer not available: %s", e)

try:
    from .SpyderC11_FuturesBasis import FuturesBasisAnalyzer
    __all__.extend(["FuturesBasisAnalyzer"])
except ImportError as e:
    logging.info("Warning: SpyderC11_FuturesBasis not available: %s", e)

try:
    from .SpyderC12_DarkPoolFlow import DarkPoolFlowAnalyzer
    __all__.extend(["DarkPoolFlowAnalyzer"])
except ImportError as e:
    logging.info("Warning: SpyderC12_DarkPoolFlow not available: %s", e)

try:
    from .SpyderC13_IndexComponents import IndexComponentAnalyzer
    __all__.extend(["IndexComponentAnalyzer"])
except ImportError as e:
    logging.info("Warning: SpyderC13_IndexComponents not available: %s", e)

try:
    from .SpyderC15_MicrostructureAnalyzer import MicrostructureAnalyzer
    __all__.extend(["MicrostructureAnalyzer"])
except ImportError as e:
    logging.info("Warning: SpyderC15_MicrostructureAnalyzer not available: %s", e)

try:
    from .SpyderC16_MarketDataCache import MarketDataCache
    __all__.extend(["MarketDataCache"])
except ImportError as e:
    logging.info("Warning: SpyderC16_MarketDataCache not available: %s", e)

try:
    from .SpyderC17_MarketConfigManager import MarketConfigManager
    __all__.extend(["MarketConfigManager"])
except ImportError as e:
    logging.info("Warning: SpyderC17_MarketConfigManager not available: %s", e)

try:
    from .SpyderC18_SKEWCalculator import SpyderS06_SKEWCalculator as SKEWCalculator
    __all__.extend(["SKEWCalculator"])
except ImportError as e:
    logging.info("Warning: SpyderC18_SKEWCalculator not available: %s", e)

try:
    from .SpyderC19_AfterHoursDataManager import AfterHoursDataManager
    __all__.extend(["AfterHoursDataManager"])
except ImportError as e:
    logging.info("Warning: SpyderC19_AfterHoursDataManager not available: %s", e)

try:
    from .SpyderC22_FactorDataProvider import FactorDataProvider
    __all__.extend(["FactorDataProvider"])
except ImportError as e:
    logging.info("Warning: SpyderC22_FactorDataProvider not available: %s", e)

try:
    from .SpyderC23_RealTimeDataOptimizer import RealTimeDataOptimizer
    __all__.extend(["RealTimeDataOptimizer"])
except ImportError as e:
    logging.info("Warning: SpyderC23_RealTimeDataOptimizer not available: %s", e)

try:
    from .SpyderC24_ModelDataPipeline import ModelDataPipeline
    __all__.extend(["ModelDataPipeline"])
except ImportError as e:
    logging.info("Warning: SpyderC24_ModelDataPipeline not available: %s", e)

try:
    from .SpyderC30_OrderFlowAnalyzer import OrderFlowAnalyzer
    __all__.extend(["OrderFlowAnalyzer"])
except ImportError as e:
    logging.info("Warning: SpyderC30_OrderFlowAnalyzer not available: %s", e)

try:
    from .SpyderC35_SentimentAnalyzer import SentimentAnalyzer
    __all__.extend(["SentimentAnalyzer"])
except ImportError as e:
    logging.info("Warning: SpyderC35_SentimentAnalyzer not available: %s", e)

try:
    from .SpyderC09_NewsManager import NewsManager
    __all__.extend(["NewsManager"])
except ImportError as e:
    logging.info("Warning: SpyderC09_NewsManager not available: %s", e)

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderC_MarketData"
__description__ = "Market Data Management — Provider Abstraction (Massive)"
__version__ = "4.0.0"
