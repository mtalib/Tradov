#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderU_Utilities
Purpose: Core Utilities

This package provides core utility functions and classes used throughout
the Spyder system.

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
    from .SpyderU02_ErrorHandler import SpyderErrorHandler, ErrorCategory, ErrorSeverity
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
    from .SpyderU04_Encryption import Encryption, encrypt, decrypt
    __all__.extend(["Encryption", "encrypt", "decrypt"])
except ImportError as e:
    print(f"Warning: SpyderU04_Encryption import failed: {e}")

# SpyderU05_NetworkUtils - NETWORK UTILITIES
try:
    from .SpyderU05_NetworkUtils import NetworkUtils, check_connection
    __all__.extend(["NetworkUtils", "check_connection"])
except ImportError as e:
    print(f"Warning: SpyderU05_NetworkUtils import failed: {e}")

# SpyderU06_MathUtils - MATHEMATICAL UTILITIES
try:
    from .SpyderU06_MathUtils import MathUtils, calculate_sharpe
    __all__.extend(["MathUtils", "calculate_sharpe"])
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
    from .SpyderU08_Validators import Validators, validate_order
    __all__.extend(["Validators", "validate_order"])
except ImportError as e:
    print(f"Warning: SpyderU08_Validators import failed: {e}")

# SpyderU09_DataTypes - DATA TYPE DEFINITIONS
try:
    from .SpyderU09_DataTypes import SpyderDataTypes
    __all__.extend(["SpyderDataTypes"])
except ImportError as e:
    print(f"Warning: SpyderU09_DataTypes import failed: {e}")

# SpyderU10_TradingCalendar - TRADING CALENDAR
try:
    from .SpyderU10_TradingCalendar import TradingCalendar as Calendar, get_trading_calendar
    __all__.extend(["Calendar", "get_trading_calendar"])
except ImportError as e:
    print(f"Warning: SpyderU10_TradingCalendar import failed: {e}")

# SpyderU11_FeatureFlags - FEATURE FLAG MANAGEMENT
try:
    from .SpyderU11_FeatureFlags import FeatureFlags, is_feature_enabled
    __all__.extend(["FeatureFlags", "is_feature_enabled"])
except ImportError as e:
    print(f"Warning: SpyderU11_FeatureFlags import failed: {e}")

# SpyderU13_TechnicalIndicators - TECHNICAL ANALYSIS
try:
    from .SpyderU13_TechnicalIndicators import TechnicalIndicators
    __all__.extend(["TechnicalIndicators"])
except ImportError as e:
    print(f"Warning: SpyderU13_TechnicalIndicators import failed: {e}")

# SpyderU14_OptionStrategies - OPTIONS STRATEGY UTILITIES
try:
    from .SpyderU14_OptionStrategies import OptionStrategies
    __all__.extend(["OptionStrategies"])
except ImportError as e:
    print(f"Warning: SpyderU14_OptionStrategies import failed: {e}")

# SpyderU15_PerformanceMetrics - PERFORMANCE CALCULATIONS
try:
    from .SpyderU15_PerformanceMetrics import PerformanceMetrics
    __all__.extend(["PerformanceMetrics"])
except ImportError as e:
    print(f"Warning: SpyderU15_PerformanceMetrics import failed: {e}")

# SpyderU16_TechnicalAnalysis - TECHNICAL ANALYSIS UTILITIES
try:
    from .SpyderU16_TechnicalAnalysis import TechnicalAnalysis
    __all__.extend(["TechnicalAnalysis"])
except ImportError as e:
    print(f"Warning: SpyderU16_TechnicalAnalysis import failed: {e}")

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderU_Utilities"
__description__ = "Core Utility Functions"
__version__ = "1.4.0"

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================
def get_available_modules():
    """Get list of successfully imported utility modules."""
    return __all__

def get_module_count():
    """Get count of available utility modules."""
    return len(__all__)

def check_module_availability(module_name: str) -> bool:
    """Check if a specific utility module is available."""
    return module_name in __all__

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
print(f"✅ SpyderU_Utilities: {len(__all__)} modules loaded successfully")
