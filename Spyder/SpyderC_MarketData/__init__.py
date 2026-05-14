#!/usr/bin/env python3
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderC_MarketData
Purpose: Market Data Management (Tradier)

This package handles all market data operations including real-time feeds,
historical data, option chains, and market internals.

Primary Data Source: Tradier (SpyderB40_TradierClient — live and paper trading)

Author: Mohamed Talib
Date: 2025-06-24
Version: 5.0.0 - Provider Abstraction Layer
"""
import logging

# ==============================================================================
# MODULE IMPORTS (DEFENSIVE)
# ==============================================================================
__all__ = []

# Provider Protocol (Tradier ↔ Massive provider swap layer)
try:
    from .SpyderC00_MarketDataProtocol import (
        OptionsDataProvider,
        create_options_data_provider,
    )

    __all__.extend(["OptionsDataProvider", "create_options_data_provider"])
except ImportError as e:
    logging.debug("Optional module SpyderC00_MarketDataProtocol not available: %s", e)

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
        "create_provider",
        "SYMBOL_GROUPS",
    ])
except ImportError as e:
    logging.debug("Optional module SpyderC01_DataFeed not fully available: %s", e)

try:
    from . import SpyderC01_DataFeed as _spyder_c01_datafeed

    for _name in (
        "DataFeedManager",
        "DataFeed",
        "get_data_feed_manager",
        "MarketTick",
        "DataFeedConfig",
        "DataFeedStatus",
        "DataSource",
        "MarketDataProvider",
        "create_provider",
        "SYMBOL_GROUPS",
    ):
        if _name not in globals() and hasattr(_spyder_c01_datafeed, _name):
            globals()[_name] = getattr(_spyder_c01_datafeed, _name)
            if _name not in __all__:
                __all__.append(_name)
except ImportError as e:
    logging.debug("Optional C01 export backfill unavailable: %s", e)

# Historical Data module
try:
    from .SpyderC02_HistoricalData import HistoricalDataManager

    __all__.extend(["HistoricalDataManager"])
except ImportError:
    logging.debug("Optional module SpyderC02_HistoricalData not available")

# Option Chain module
try:
    from .SpyderC03_OptionChain import OptionChainManager

    __all__.extend(["OptionChainManager"])
except ImportError:
    logging.debug("Optional module SpyderC03_OptionChain not available")

# Market Internals module
try:
    from .SpyderC04_MarketInternals import MarketInternals

    __all__.extend(["MarketInternals"])
except ImportError:
    logging.debug("Optional module SpyderC04_MarketInternals not available")

# Volume Profile module
try:
    from .SpyderC05_VolumeProfile import VolumeProfileAnalyzer

    __all__.extend(["VolumeProfileAnalyzer"])
except ImportError:
    logging.debug("Optional module SpyderC05_VolumeProfile not available")

# Data Validator module
try:
    from .SpyderC06_DataValidator import DataValidator

    __all__.extend(["DataValidator"])
except ImportError:
    logging.debug("Optional module SpyderC06_DataValidator not available")

# SPY Feed module
try:
    from .SpyderC08_SPYFeed import SPYDataFeed

    __all__.extend(["SPYDataFeed"])
except ImportError:
    logging.debug("Optional module SpyderC08_SPYFeed not available")

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
    logging.debug("Optional module SpyderC29_DataProviderRouter not available: %s", e)

# C10–C19, C22–C24, C30, C35 — additional market data modules
try:
    from .SpyderC10_VIXAnalyzer import VIXAnalyzer
    __all__.extend(["VIXAnalyzer"])
except ImportError as e:
    logging.debug("Optional module SpyderC10_VIXAnalyzer not available: %s", e)

try:
    from .SpyderC12_DarkPoolFlow import DarkPoolFlowAnalyzer
    __all__.extend(["DarkPoolFlowAnalyzer"])
except ImportError as e:
    logging.debug("Optional module SpyderC12_DarkPoolFlow not available: %s", e)

try:
    from .SpyderC13_IndexComponents import IndexComponentAnalyzer
    __all__.extend(["IndexComponentAnalyzer"])
except ImportError as e:
    logging.debug("Optional module SpyderC13_IndexComponents not available: %s", e)

try:
    from .SpyderC15_MicrostructureAnalyzer import MicrostructureAnalyzer
    __all__.extend(["MicrostructureAnalyzer"])
except ImportError as e:
    logging.debug("Optional module SpyderC15_MicrostructureAnalyzer not available: %s", e)

try:
    from .SpyderC16_MarketDataCache import MarketDataCache
    __all__.extend(["MarketDataCache"])
except ImportError as e:
    logging.debug("Optional module SpyderC16_MarketDataCache not available: %s", e)

try:
    from .SpyderC17_MarketConfigManager import MarketConfigManager
    __all__.extend(["MarketConfigManager"])
except ImportError as e:
    logging.debug("Optional module SpyderC17_MarketConfigManager not available: %s", e)

try:
    from .SpyderC18_SKEWCalculator import SpyderS06_SKEWCalculator as SKEWCalculator
    __all__.extend(["SKEWCalculator"])
except ImportError as e:
    logging.debug("Optional module SpyderC18_SKEWCalculator not available: %s", e)

try:
    from .SpyderC19_AfterHoursDataManager import AfterHoursDataManager
    __all__.extend(["AfterHoursDataManager"])
except ImportError as e:
    logging.debug("Optional module SpyderC19_AfterHoursDataManager not available: %s", e)

try:
    from .SpyderC22_FactorDataProvider import FactorDataProvider
    __all__.extend(["FactorDataProvider"])
except ImportError as e:
    logging.debug("Optional module SpyderC22_FactorDataProvider not available: %s", e)

try:
    from .SpyderC23_RealTimeDataOptimizer import RealTimeDataOptimizer
    __all__.extend(["RealTimeDataOptimizer"])
except ImportError as e:
    logging.debug("Optional module SpyderC23_RealTimeDataOptimizer not available: %s", e)

try:
    from .SpyderC24_ModelDataPipeline import ModelDataPipeline
    __all__.extend(["ModelDataPipeline"])
except ImportError as e:
    logging.debug("Optional module SpyderC24_ModelDataPipeline not available: %s", e)

try:
    from .SpyderC30_OrderFlowAnalyzer import OrderFlowAnalyzer
    __all__.extend(["OrderFlowAnalyzer"])
except ImportError as e:
    logging.debug("Optional module SpyderC30_OrderFlowAnalyzer not available: %s", e)

try:
    from .SpyderC35_SentimentAnalyzer import SentimentAnalyzer
    __all__.extend(["SentimentAnalyzer"])
except ImportError as e:
    logging.debug("Optional module SpyderC35_SentimentAnalyzer not available: %s", e)

try:
    from .SpyderC09_NewsManager import NewsManager
    __all__.extend(["NewsManager"])
except ImportError as e:
    logging.debug("Optional module SpyderC09_NewsManager not available: %s", e)

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderC_MarketData"
__description__ = "Market Data Management — Provider Abstraction (Massive)"
__version__ = "4.0.0"
