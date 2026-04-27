#!/usr/bin/env python3
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderN_OptionsAnalytics
Purpose: Options Analytics

This package provides advanced options analytics including volatility analysis.

Author: Mohamed Talib
Date: 2025-06-18
Version: 1.4
"""
import logging

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
try:
    from .SpyderN08_VolatilitySurface import VolAnalytics, VolatilitySurface
except ImportError:
    VolAnalytics = None  # type: ignore[assignment]
    VolatilitySurface = None  # type: ignore[assignment]

try:
    from .SpyderN01_OptionsPricer import OptionsPricer
except ImportError:
    logging.info("Warning: SpyderN01_OptionsPricer not available")

try:
    from .SpyderN02_ImpliedVolatilityEngine import ImpliedVolatilityEngine
except ImportError:
    logging.info("Warning: SpyderN02_ImpliedVolatilityEngine not available")

try:
    from .SpyderN03_OptionsChainManager import OptionsChainManager
except ImportError:
    logging.info("Warning: SpyderN03_OptionsChainManager not available")

try:
    from .SpyderN04_OptionsGreeksCalculator import OptionsGreeksCalculator
except ImportError:
    logging.info("Warning: SpyderN04_OptionsGreeksCalculator not available")

try:
    from .SpyderN05_OptionsExpirationManager import OptionsExpirationManager
except ImportError:
    logging.info("Warning: SpyderN05_OptionsExpirationManager not available")

try:
    from .SpyderN06_VolatilitySurfaceBuilder import VolatilitySurfaceBuilder
except ImportError:
    logging.info("Warning: SpyderN06_VolatilitySurfaceBuilder not available")

try:
    from .SpyderN07_OptionsFlowTracker import OptionsFlowTracker
except ImportError:
    logging.info("Warning: SpyderN07_OptionsFlowTracker not available")

try:
    from .SpyderN07_OPRAGreeksHandler import OPRAGreeksHandler
except ImportError:
    logging.info("Warning: SpyderN07_OPRAGreeksHandler not available")

try:
    from .SpyderN09_GammaExposure import GammaExposureCalculator
except ImportError:
    logging.info("Warning: SpyderN09_GammaExposure not available")

try:
    from .SpyderN10_OptionsFlowAnalyzer import AdvancedOptionsFlowAnalyzer
except ImportError:
    logging.info("Warning: SpyderN10_OptionsFlowAnalyzer not available")

try:
    from .SpyderN11_OptionsGreeksFlow import OptionsGreeksFlowAnalyzer
except ImportError:
    logging.info("Warning: SpyderN11_OptionsGreeksFlow not available")

try:
    from .SpyderN12_VolatilitySurfaceAI import VolatilitySurfaceAI
except ImportError:
    logging.info("Warning: SpyderN12_VolatilitySurfaceAI not available")

try:
    from .SpyderN13_MarketImpactModel import MarketImpactModel
except ImportError:
    logging.info("Warning: SpyderN13_MarketImpactModel not available")

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    "VolatilitySurface",
    "VolAnalytics",
    "OptionsPricer",
    "ImpliedVolatilityEngine",
    "OptionsChainManager",
    "OptionsGreeksCalculator",
    "OptionsExpirationManager",
    "VolatilitySurfaceBuilder",
    "OptionsFlowTracker",
    "OPRAGreeksHandler",
    "GammaExposureCalculator",
    "AdvancedOptionsFlowAnalyzer",
    "OptionsGreeksFlowAnalyzer",
    "VolatilitySurfaceAI",
    "MarketImpactModel",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderN_OptionsAnalytics"
__description__ = "Advanced Options Analytics"
__version__ = "1.4.1"
