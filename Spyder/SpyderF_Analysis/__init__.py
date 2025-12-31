#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderF_Analysis
Purpose: Technical Analysis Engine

This package provides technical analysis engine functionality for the Spyder trading system.

Author: Mohamed Talib
Date: 2025-06-14
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderF01_Indicators import TechnicalIndicators
from .SpyderF02_PriceAction import PriceActionAnalyzer
from .SpyderF03_SupportResistance import SupportResistanceAnalyzer
from .SpyderF04_VolatilityAnalysis import VolatilityAnalyzer
from .SpyderF05_TrendDetection import TrendDetector
from .SpyderF06_GreeksCalculator import GreeksCalculator
from .SpyderF07_GapAnalyzer import GapAnalyzer
from .SpyderF08_VolatilityRegime import VolatilityRegimeAnalyzer
from .SpyderF09_EntryFilters import EntryFilters
from .SpyderF10_MarketRegimeDetector import MarketRegimeDetector

# Renaissance-style indicators
try:
    from .SpyderF21_RenaissanceIndicators import (
        RenaissanceStyleSignalGenerator,
        MeanReversionIndicators,
        VolatilityIndicators,
        MarketMicrostructureIndicators,
        OptionsGreeksIndicators,
        RenaissanceSignal,
        MeanReversionSignal,
        VolatilityRegime,
        create_renaissance_signal_generator,
    )
    RENAISSANCE_INDICATORS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: SpyderF21_RenaissanceIndicators not available: {e}")
    RENAISSANCE_INDICATORS_AVAILABLE = False

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    "EntryFilters",
    "GapAnalyzer",
    "GreeksCalculator",
    "MarketRegimeDetector",
    "PriceActionAnalyzer",
    "SupportResistanceAnalyzer",
    "TechnicalIndicators",
    "TrendDetector",
    "VolatilityAnalyzer",
    "VolatilityRegimeAnalyzer",
]

# Add Renaissance indicators if available
if RENAISSANCE_INDICATORS_AVAILABLE:
    __all__.extend([
        "RenaissanceStyleSignalGenerator",
        "MeanReversionIndicators",
        "VolatilityIndicators",
        "MarketMicrostructureIndicators",
        "OptionsGreeksIndicators",
        "RenaissanceSignal",
        "MeanReversionSignal",
        "VolatilityRegime",
        "create_renaissance_signal_generator",
    ])

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "{package_name}"
__description__ = "{description}"
__version__ = "1.4.0"
