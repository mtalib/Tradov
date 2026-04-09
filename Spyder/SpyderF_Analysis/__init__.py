#!/usr/bin/env python3
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
import logging

# F00 — Protocol contracts (F↔X series boundary)
try:
    from .SpyderF00_AnalysisProtocol import (
        IndicatorSnapshot,
        RegimeSnapshot,
        AnalyticsProviderProtocol,
        RegimeAwareAgentProtocol,
    )
    F00_AVAILABLE = True
except ImportError:
    F00_AVAILABLE = False

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
    logging.info("Warning: SpyderF21_RenaissanceIndicators not available: %s", e)
    RENAISSANCE_INDICATORS_AVAILABLE = False

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    # F00 — Protocol contracts
    "IndicatorSnapshot",
    "RegimeSnapshot",
    "AnalyticsProviderProtocol",
    "RegimeAwareAgentProtocol",
    # Core analysis
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

# F11–F19 — additional analysis modules
try:
    from .SpyderF11_GreeksAggregator import GreeksAggregator
    __all__.extend(["GreeksAggregator"])
except ImportError as e:
    logging.info("Warning: SpyderF11_GreeksAggregator not available: %s", e)

try:
    from .SpyderF13_ModelValidation import ModelValidationEngine
    __all__.extend(["ModelValidationEngine"])
except ImportError as e:
    logging.info("Warning: SpyderF13_ModelValidation not available: %s", e)

try:
    from .SpyderF14_MarketMicrostructure import MarketMicrostructureEngine
    __all__.extend(["MarketMicrostructureEngine"])
except ImportError as e:
    logging.info("Warning: SpyderF14_MarketMicrostructure not available: %s", e)

try:
    from .SpyderF16_RealTimeAnalytics import RealTimeAnalyticsEngine
    __all__.extend(["RealTimeAnalyticsEngine"])
except ImportError as e:
    logging.info("Warning: SpyderF16_RealTimeAnalytics not available: %s", e)

try:
    from .SpyderF17_UnifiedPerformanceEngine import UnifiedPerformanceEngine
    __all__.extend(["UnifiedPerformanceEngine"])
except ImportError as e:
    logging.info("Warning: SpyderF17_UnifiedPerformanceEngine not available: %s", e)

try:
    from .SpyderF18_MaxPainCalculator import MaxPainCalculator
    __all__.extend(["MaxPainCalculator"])
except ImportError as e:
    logging.info("Warning: SpyderF18_MaxPainCalculator not available: %s", e)

try:
    from .SpyderF19_AnchoredVWAP import AnchoredVWAPCalculator
    __all__.extend(["AnchoredVWAPCalculator"])
except ImportError as e:
    logging.info("Warning: SpyderF19_AnchoredVWAP not available: %s", e)

try:
    from .SpyderF20_Indicators import SMA, EMA, RSI, MACD, BBANDS, ATR
    __all__.extend(["SMA", "EMA", "RSI", "MACD", "BBANDS", "ATR"])
except ImportError as e:
    logging.info("Warning: SpyderF20_Indicators not available: %s", e)

try:
    from .SpyderF22_MLPrediction import MLPredictionEngine
    __all__.extend(["MLPredictionEngine"])
except ImportError as e:
    logging.info("Warning: SpyderF22_MLPrediction not available: %s", e)

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderF_Analysis"
__description__ = "Technical Analysis Engine"
__version__ = "1.4.1"
