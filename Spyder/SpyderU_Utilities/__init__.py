#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderU_Utilities/__init__.py
Purpose: Utility functions and classes package initialization

Description:
    This package provides various utility modules for the Spyder trading system,
    including logging, error handling, date/time utilities, validation, and more.

Author: Mohamed Talib
Date: 2025-06-24
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS (DEFENSIVE - ACTUAL EXISTING MODULES)
# ==============================================================================
__all__ = []

# SpyderU01_Logger - ALWAYS AVAILABLE
try:
    from .SpyderU01_Logger import SpyderLogger, get_logger

    __all__.extend(["SpyderLogger", "get_logger"])
except ImportError as e:
    print(f"Critical: SpyderU01_Logger import failed: {e}")

# SpyderU02_ErrorHandler - COMPREHENSIVE LEAN VERSION
try:
    from .SpyderU02_ErrorHandler import (ErrorCategory, ErrorSeverity,
                                        SpyderErrorHandler)

    __all__.extend(["SpyderErrorHandler", "ErrorCategory", "ErrorSeverity"])
except ImportError as e:
    print(f"Warning: SpyderU02_ErrorHandler import failed: {e}")

# SpyderU03_DateTimeUtils - DATE/TIME UTILITIES
try:
    from .SpyderU03_DateTimeUtils import DateTimeUtils, TradingCalendar

    __all__.extend(["DateTimeUtils", "TradingCalendar"])
except ImportError as e:
    print(f"Warning: SpyderU03_DateTimeUtils import failed: {e}")

# SpyderU04_Encryption - SECURITY UTILITIES
try:
    from .SpyderU04_Encryption import (EncryptionManager, decrypt_data,
                                    encrypt_data)

    __all__.extend(["EncryptionManager", "encrypt_data", "decrypt_data"])
except ImportError as e:
    print(f"Warning: SpyderU04_Encryption import failed: {e}")

# SpyderU05_NetworkUtils - NETWORK UTILITIES
try:
    from .SpyderU05_NetworkUtils import NetworkUtils, check_internet_connection

    __all__.extend(["NetworkUtils", "check_internet_connection"])
except ImportError as e:
    print(f"Warning: SpyderU05_NetworkUtils import failed: {e}")

# SpyderU06_MathUtils - MATHEMATICAL UTILITIES
try:
    from .SpyderU06_MathUtils import MathUtils, calculate_sharpe_ratio

    __all__.extend(["MathUtils", "calculate_sharpe_ratio"])
except ImportError as e:
    print(f"Warning: SpyderU06_MathUtils import failed: {e}")

# SpyderU07_Constants - SYSTEM CONSTANTS
try:
    from .SpyderU07_Constants import *  # Import all constants

    # Note: Constants are typically imported with * to make them globally available
except ImportError as e:
    print(f"Warning: SpyderU07_Constants import failed: {e}")

# SpyderU08_Validators - DATA VALIDATION
try:
    from .SpyderU08_Validators import DataValidators, validate_order_data

    __all__.extend(["DataValidators", "validate_order_data"])
except ImportError as e:
    print(f"Warning: SpyderU08_Validators import failed: {e}")

# SpyderU09_DataTypes - DATA TYPE DEFINITIONS
try:
    from .SpyderU09_DataTypes import MarketData, OrderData, PositionData

    __all__.extend(["MarketData", "OrderData", "PositionData"])
except ImportError as e:
    print(f"Warning: SpyderU09_DataTypes import failed: {e}")

# SpyderU10_TradingCalendar - TRADING CALENDAR
try:
    from .SpyderU10_TradingCalendar import TradingCalendar as Calendar
    from .SpyderU10_TradingCalendar import get_trading_calendar

    __all__.extend(["Calendar", "get_trading_calendar"])
except ImportError as e:
    print(f"Warning: SpyderU10_TradingCalendar import failed: {e}")

# SpyderU11_FeatureFlags - FEATURE FLAG MANAGEMENT
try:
    from .SpyderU11_FeatureFlags import FeatureFlags, check_feature_enabled

    __all__.extend(["FeatureFlags", "check_feature_enabled"])
except ImportError as e:
    print(f"Warning: SpyderU11_FeatureFlags import failed: {e}")

# SpyderU13_TechnicalIndicators - TECHNICAL ANALYSIS INDICATORS
try:
    from .SpyderU13_TechnicalIndicators import (TechnicalIndicators,
                                                calculate_macd, calculate_rsi)

    __all__.extend(["TechnicalIndicators", "calculate_rsi", "calculate_macd"])
except ImportError as e:
    print(f"Warning: SpyderU13_TechnicalIndicators import failed: {e}")

# SpyderU14_OptionStrategies - OPTION STRATEGY UTILITIES
try:
    from .SpyderU14_OptionStrategies import (OptionStrategy,
                                            calculate_option_payoff)

    __all__.extend(["OptionStrategy", "calculate_option_payoff"])
except ImportError as e:
    print(f"Warning: SpyderU14_OptionStrategies import failed: {e}")

# SpyderU15_PerformanceMetrics - PERFORMANCE CALCULATION
try:
    from .SpyderU15_PerformanceMetrics import (PerformanceCalculator,
                                            calculate_metrics)

    __all__.extend(["PerformanceCalculator", "calculate_metrics"])
except ImportError as e:
    print(f"Warning: SpyderU15_PerformanceMetrics import failed: {e}")

# SpyderU16_TechnicalAnalysis - ADVANCED TECHNICAL ANALYSIS
try:
    
    __all__.extend(["TechnicalAnalysis", ])
except ImportError as e:
    print(f"Warning: SpyderU16_TechnicalAnalysis import failed: {e}")

# SpyderU18_DependencyAnalyzer - DEPENDENCY ANALYSIS
try:
    from .SpyderU18_DependencyAnalyzer import DependencyAnalyzer

    __all__.extend(["DependencyAnalyzer"])
except ImportError as e:
    print(f"Warning: SpyderU18_DependencyAnalyzer import failed: {e}")

# SpyderU19_InteractionMatrix - MODULE INTERACTION MATRIX
try:
    from .SpyderU19_InteractionMatrix import InteractionMatrix

    __all__.extend(["InteractionMatrix"])
except ImportError as e:
    print(f"Warning: SpyderU19_InteractionMatrix import failed: {e}")

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================


def get_version():
    """Get utilities package version."""
    return "1.4.0"


def list_available_utilities():
    """List all available utility modules."""
    available = []
    for module in __all__:
        try:
            # Check if the module/class is actually available
            if module in globals():
                available.append(module)
        except BaseException:
            pass
    return available


# ==============================================================================
# INITIALIZATION
# ==============================================================================
# Count successfully loaded modules
loaded_modules = len([m for m in __all__ if m in globals()])
print(f"✅ SpyderU_Utilities: {loaded_modules} modules loaded successfully")

# ==============================================================================
# BACKWARDS COMPATIBILITY ALIASES
# ==============================================================================
# Add aliases for commonly used but renamed classes
try:
    # Alias for Validators -> DataValidators
    from .SpyderU08_Validators import DataValidators as Validators

    __all__.append("Validators")
except BaseException:
    pass

try:
    # Alias for validate_order -> validate_order_data
    from .SpyderU08_Validators import validate_order_data as validate_order

    __all__.append("validate_order")
except BaseException:
    pass

try:
    # Other common aliases
    from .SpyderU04_Encryption import EncryptionManager as Encryption

    __all__.append("Encryption")

    from .SpyderU04_Encryption import encrypt_data as encrypt

    __all__.append("encrypt")

    from .SpyderU04_Encryption import decrypt_data as decrypt

    __all__.append("decrypt")
except BaseException:
    pass

try:
    from .SpyderU05_NetworkUtils import \
        check_internet_connection as check_connection

    __all__.append("check_connection")
except BaseException:
    pass

try:
    from .SpyderU06_MathUtils import calculate_sharpe_ratio as calculate_sharpe

    __all__.append("calculate_sharpe")
except BaseException:
    pass

try:
    from .SpyderU09_DataTypes import MarketData as SpyderDataTypes

    __all__.append("SpyderDataTypes")
except BaseException:
    pass

try:
    from .SpyderU11_FeatureFlags import \
        check_feature_enabled as is_feature_enabled

    __all__.append("is_feature_enabled")
except BaseException:
    pass

try:
    from .SpyderU14_OptionStrategies import OptionStrategy as OptionStrategies

    __all__.append("OptionStrategies")
except BaseException:
    pass

try:
    from .SpyderU15_PerformanceMetrics import \
        PerformanceCalculator as PerformanceMetrics

    __all__.append("PerformanceMetrics")
except BaseException:
    pass

# ==============================================================================
# PACKAGE INFO
# ==============================================================================
__version__ = "1.4.0"
__author__ = "Mohamed Talib"
__description__ = "Utility functions and classes for Spyder trading system"
