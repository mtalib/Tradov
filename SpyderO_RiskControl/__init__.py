#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderO_RiskControl
Purpose: Professional Risk Controls

This package provides professional risk controls functionality for the Spyder trading system.

Author: Mohamed Talib
Date: 2025-06-14
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderO01_GreekLimitsManager import GreekLimitsManager
from .SpyderO02_CircuitBreakerProtocol import CircuitBreakerProtocol
from .SpyderO03_AutomaticRebalancer import AutomaticRebalancer

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    "AutomaticRebalancer",
    "CircuitBreakerProtocol",
    "GreekLimitsManager",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "{package_name}"
__description__ = "{description}"
__version__ = "1.4.0"
