#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderQ_QuantitativeModels
Purpose: Quantitative Models

This package provides quantitative models functionality for the Spyder trading system.

Author: Mohamed Talib
Date: 2025-06-14
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderQ01_HestonModel import HestonModel
from .SpyderQ02_CVaRCalculator import CVaRCalculator

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    "CVaRCalculator",
    "HestonModel",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "{package_name}"
__description__ = "{description}"
__version__ = "1.4.0"
