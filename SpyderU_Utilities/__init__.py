#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderU_Utilities
Purpose: Core Utilities

This package provides core utility functions and classes used throughout
the Spyder system.

Author: Mohamed Talib
Date: 2025-06-18
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
# Import from logger module
from .SpyderU01_Logger import SpyderLogger, get_logger

# Import from other modules (commented out for now as they don't exist yet)
# from .SpyderU02_ErrorHandler import SpyderErrorHandler, ErrorType
# from .SpyderU03_DateTimeUtils import DateTimeUtils, TradingCalendar
# from .SpyderU04_Encryption import Encryption, encrypt, decrypt
# from .SpyderU05_NetworkUtils import NetworkUtils, check_connection
# from .SpyderU06_MathUtils import MathUtils, calculate_sharpe
# from .SpyderU07_Constants import *  # Import all constants
# from .SpyderU08_Validators import Validators, validate_order
# from .SpyderU09_DataTypes import SpyderDataTypes
# from .SpyderU10_TradingCalendar import TradingCalendar as Calendar
# from .SpyderU11_FeatureFlags import FeatureFlags, is_feature_enabled
# from .SpyderU12_AgentIntegration import AIAgentManager, AgentStatus
# from .SpyderU13_TechnicalIndicators import TechnicalIndicators

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    # Logging
    "SpyderLogger",
    "get_logger",
    
    # Error handling (commented out for now)
    # "SpyderErrorHandler",
    # "ErrorType",
    
    # Date/Time utilities (commented out for now)
    # "DateTimeUtils",
    # "TradingCalendar",
    # "Calendar",
    
    # Encryption (commented out for now)
    # "Encryption",
    # "encrypt",
    # "decrypt",
    
    # Network utilities (commented out for now)
    # "NetworkUtils",
    # "check_connection",
    
    # Math utilities (commented out for now)
    # "MathUtils",
    # "calculate_sharpe",
    
    # Validation (commented out for now)
    # "Validators",
    # "validate_order",
    
    # Data types (commented out for now)
    # "SpyderDataTypes",
    
    # Feature flags (commented out for now)
    # "FeatureFlags",
    # "is_feature_enabled",
    
    # AI Integration (commented out for now)
    # "AIAgentManager",
    # "AgentStatus",
    
    # Technical indicators (commented out for now)
    # "TechnicalIndicators",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderU_Utilities"
__description__ = "Core Utility Functions"
__version__ = "1.4.0"