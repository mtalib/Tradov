#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderN_OptionsAnalytics
Purpose: Options Analytics

This package provides advanced options analytics including volatility analysis.

Author: Mohamed Talib
Date: 2025-06-18
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderN08_VolatilitySurface import VolatilitySurface, VolAnalytics

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    "VolatilitySurface",
    "VolAnalytics",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderN_OptionsAnalytics"
__description__ = "Advanced Options Analytics"
__version__ = "1.4.0"