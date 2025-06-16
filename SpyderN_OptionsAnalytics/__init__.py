#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderN_OptionsAnalytics
Purpose: Advanced Options Analysis

This package provides advanced options analysis functionality for the Spyder trading system.

Author: Mohamed Talib
Date: 2025-06-14
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderN01_VolatilitySmile import VolatilitySmileAnalyzer
from .SpyderN02_TermStructure import TermStructureAnalyzer
from .SpyderN03_SkewAnalyzer import SkewAnalyzer
from .SpyderN04_FlowAnalyzer import FlowAnalyzer
from .SpyderN05_OptionsFlowAnalyzer import OptionsFlowAnalyzer
from .SpyderN06_OptionsPricer import OptionsPricer
from .SpyderN07_OPRAGreeksHandler import OPRAGreeksHandler
from .SpyderN08_VolatilitySurface import VolatilitySurface

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    "FlowAnalyzer",
    "OPRAGreeksHandler",
    "OptionsFlowAnalyzer",
    "OptionsPricer",
    "SkewAnalyzer",
    "TermStructureAnalyzer",
    "VolatilitySmileAnalyzer",
    "VolatilitySurface",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "{package_name}"
__description__ = "{description}"
__version__ = "1.4.0"
