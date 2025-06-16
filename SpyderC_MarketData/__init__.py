#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderC_MarketData
Purpose: Real-time Data Feeds

This package provides real-time data feeds functionality for the Spyder trading system.

Author: Mohamed Talib
Date: 2025-06-14
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderC01_DataFeed import DataFeedManager, MarketDataFeed
from .SpyderC02_HistoricalData import HistoricalDataManager
from .SpyderC03_OptionChain import OptionChainManager, OptionData
from .SpyderC04_MarketInternals import MarketInternals
from .SpyderC05_VolumeProfile import VolumeProfileAnalyzer
from .SpyderC06_DataValidator import DataValidator
from .SpyderC07_OPRAFeed import OPRAFeedHandler
from .SpyderC08_SPYFeed import SPYFeedHandler

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    "DataFeedManager",
    "DataValidator",
    "HistoricalDataManager",
    "MarketDataFeed",
    "MarketInternals",
    "OPRAFeedHandler",
    "OptionChainManager",
    "OptionData",
    "SPYFeedHandler",
    "VolumeProfileAnalyzer",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "{package_name}"
__description__ = "{description}"
__version__ = "1.4.0"
