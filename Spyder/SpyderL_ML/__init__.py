#!/usr/bin/env python3
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderL_ML
Purpose: Machine Learning Systems

This package provides machine learning systems functionality for the Spyder trading system.

Author: Mohamed Talib
Date: 2025-06-14
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
import logging as _logging

_logger = _logging.getLogger(__name__)

# Import modules with graceful fallbacks
try:
    from .SpyderL01_MLPredictor import MLPredictor
except Exception as _e:
    _logger.warning(f"SpyderL01_MLPredictor not available: {_e}")
    MLPredictor = None  # type: ignore

try:
    from .SpyderL07_PaperTradeLearner import PaperTradeLearner
except Exception as _e:
    _logger.warning(f"SpyderL07_PaperTradeLearner not available: {_e}")
    PaperTradeLearner = None  # type: ignore

try:
    from .SpyderL08_EntryOptimizer import EntryOptimizer
except Exception as _e:
    _logger.warning(f"SpyderL08_EntryOptimizer not available: {_e}")
    EntryOptimizer = None  # type: ignore

try:
    from .SpyderL09_UnifiedRegimeEngine import UnifiedRegimeEngine as RegimeClassifier
except Exception as _e:
    _logger.warning(f"SpyderL09_UnifiedRegimeEngine not available: {_e}")
    RegimeClassifier = None  # type: ignore

try:
    from .SpyderL10_FeatureEngineering import FeatureEngineer
except Exception as _e:
    _logger.warning(f"SpyderL10_FeatureEngineering not available: {_e}")
    FeatureEngineer = None  # type: ignore

try:
    from .SpyderL11_MLModelManager import MLModelManager
except Exception as _e:
    _logger.warning(f"SpyderL11_MLModelManager not available: {_e}")
    MLModelManager = None  # type: ignore

try:
    from .SpyderL12_RandomForestEnsemble import SpyderRandomForestEnsemble
except Exception as _e:
    _logger.warning(f"SpyderL12_RandomForestEnsemble not available: {_e}")
    SpyderRandomForestEnsemble = None  # type: ignore

try:
    from .SpyderL13_LSTMPricer import SpyderLSTMPricer
except Exception as _e:
    _logger.warning(f"SpyderL13_LSTMPricer not available: {_e}")
    SpyderLSTMPricer = None  # type: ignore

try:
    from .SpyderL14_RealTimePredictor import RealTimePredictor
except Exception as _e:
    _logger.warning(f"SpyderL14_RealTimePredictor not available: {_e}")
    RealTimePredictor = None  # type: ignore

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    "EntryOptimizer",
    "FeatureEngineer",
    "SpyderLSTMPricer",
    "MLModelManager",
    "MLPredictor",
    "PaperTradeLearner",
    "SpyderRandomForestEnsemble",
    "RealTimePredictor",
    "RegimeClassifier",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "{package_name}"
__description__ = "{description}"
__version__ = "1.4.0"
