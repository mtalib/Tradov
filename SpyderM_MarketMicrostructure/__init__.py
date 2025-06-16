#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderM_MarketMicrostructure
Purpose: Order Flow Analysis

This package provides order flow analysis functionality for the Spyder trading system.

Author: Mohamed Talib
Date: 2025-06-14
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderM01_OrderBookAnalyzer import OrderBookAnalyzer
from .SpyderM02_SmartOrderRouter import SmartOrderRouter

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    "OrderBookAnalyzer",
    "SmartOrderRouter",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "{package_name}"
__description__ = "{description}"
__version__ = "1.4.0"
