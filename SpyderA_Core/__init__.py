#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderA_Core
Purpose: Core Trading Engine

This package provides core trading engine functionality for the Spyder trading system.

Author: Mohamed Talib
Date: 2025-06-14
Version: 1.4
"""

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderA_Core"
__description__ = "Core Trading Engine for Spyder Automated SPY Options Trading System"
__version__ = "1.4.0"

# ==============================================================================
# MINIMAL IMPORTS TO AVOID CIRCULAR DEPENDENCIES
# ==============================================================================
# We don't import anything here to avoid circular dependencies
# Instead, users should import directly from the modules:
# from SpyderA_Core.SpyderA02_TradingEngine import TradingEngine
# from SpyderA_Core.SpyderA03_Configuration import ConfigManager
# etc.

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    # List module names only, not the classes
    "SpyderA01_Main",
    "SpyderA02_TradingEngine", 
    "SpyderA03_Configuration",
    "SpyderA04_Scheduler",
    "SpyderA05_EventManager",
    "SpyderA06_SystemMonitor",
]

# ==============================================================================
# PACKAGE INITIALIZATION
# ==============================================================================
# Initialize logger for the package
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    _logger = SpyderLogger.get_logger(__name__)
    _logger.info(f"Initialized {__package_name__} package v{__version__}")
except ImportError:
    # Logger not available yet, fail silently
    pass
