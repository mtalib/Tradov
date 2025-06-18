#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderU_Utilities
Purpose: Core Utilities

This package provides core utilities functionality for the Spyder trading system.

Author: Mohamed Talib
Date: 2025-06-14
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderU01_Logger import SpyderLogger
from .SpyderU02_ErrorHandler import SpyderErrorHandler
from .SpyderU03_DateTimeUtils import DateTimeUtils, TradingTimeUtils
from .SpyderU04_Encryption import CredentialManager
from .SpyderU05_NetworkUtils import NetworkUtils
from .SpyderU06_MathUtils import MathUtils
from .SpyderU07_Constants import TradingConstants
from .SpyderU08_Validators import DataValidators
from .SpyderU09_DataTypes import OptionData, FeatureSet
from .SpyderU10_TradingCalendar import TradingCalendar, get_trading_calendar
from .SpyderU11_FeatureFlags import FeatureFlags, get_feature_flags
from .SpyderU13_TechnicalIndicators import TechnicalIndicators

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    "CredentialManager",
    "DataValidators",
    "DateTimeUtils",
    "FeatureFlags",
    "FeatureSet",
    "MathUtils",
    "NetworkUtils",
    "OptionData",
    "SpyderErrorHandler",
    "SpyderLogger",
    "TradingCalendar",
    "TradingConstants",
    "TradingTimeUtils",
    "get_feature_flags",
    "get_trading_calendar",
    "TechnicalIndicators",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "{package_name}"
__description__ = "{description}"
__version__ = "1.4.0"

# ==============================================================================
# UTILITIES PACKAGE INITIALIZATION
# ==============================================================================
# Set up default logging configuration
try:
    _logger = SpyderLogger.get_logger(__name__)
    _logger.info(f"Initialized {__package_name__} package")
except Exception:
    pass  # Handle gracefully if logger not available
