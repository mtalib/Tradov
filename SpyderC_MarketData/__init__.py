#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderC_MarketData
Purpose: Market Data Management

This package handles all market data operations including real-time feeds,
historical data, options chains, and market internals.

Author: Mohamed Talib
Date: 2025-06-18
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderC01_DataFeed import DataFeed, get_data_feed
from .SpyderC02_HistoricalData import HistoricalDataManager
from .SpyderC03_OptionChain import OptionChainManager, OptionChain
from .SpyderC04_MarketInternals import MarketInternals, Breadth
from .SpyderC05_VolumeProfile import VolumeProfile, VolumeAnalysis
from .SpyderC06_DataValidator import DataValidator
from .SpyderC07_OPRAFeed import OPRAFeed
from .SpyderC08_SPYFeed import SPYFeed

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    # Data feeds
    "DataFeed",
    "get_data_feed",
    "OPRAFeed",
    "SPYFeed",
    
    # Historical data
    "HistoricalDataManager",
    
    # Options data
    "OptionChainManager",
    "OptionChain",
    
    # Market internals
    "MarketInternals",
    "Breadth",
    
    # Volume analysis
    "VolumeProfile",
    "VolumeAnalysis",
    
    # Data validation
    "DataValidator",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderC_MarketData"
__description__ = "Market Data Management"
__version__ = "1.4.0"