#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderA_Core
Purpose: Core Trading Engine

This package contains the core components of the Spyder trading system,
including the main application, trading engine, configuration, scheduling,
and event management.

Author: Mohamed Talib
Date: 2025-06-18
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS - Simplified to avoid circular imports
# ==============================================================================
# We'll import these directly when needed instead of at package level

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    # Modules available
    "SpyderA01_Main",
    "SpyderA02_TradingEngine",
    "SpyderA03_Configuration",
    "SpyderA04_Scheduler",
    "SpyderA05_EventManager",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderA_Core"
__description__ = "Core Trading Engine Components"
__version__ = "1.4.0"