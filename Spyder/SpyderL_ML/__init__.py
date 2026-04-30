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
    _logger.warning("SpyderL01_MLPredictor not available: %s", _e)
    MLPredictor = None  # type: ignore

try:
    from .SpyderL07_PaperTradeLearner import PaperTradeLearner
except Exception as _e:
    _logger.warning("SpyderL07_PaperTradeLearner not available: %s", _e)
    PaperTradeLearner = None  # type: ignore

try:
    from .SpyderL08_EntryOptimizer import EntryOptimizer
except Exception as _e:
    _logger.warning("SpyderL08_EntryOptimizer not available: %s", _e)
    EntryOptimizer = None  # type: ignore

try:
    from .SpyderL09_UnifiedRegimeEngine import UnifiedRegimeEngine as RegimeClassifier
except Exception as _e:
    _logger.warning("SpyderL09_UnifiedRegimeEngine not available: %s", _e)
    RegimeClassifier = None  # type: ignore

try:
    from .SpyderL10_FeatureEngineering import FeatureEngineer
except Exception as _e:
    _logger.warning("SpyderL10_FeatureEngineering not available: %s", _e)
    FeatureEngineer = None  # type: ignore

try:
    from .SpyderL11_MLModelManager import MLModelManager
except Exception as _e:
    _logger.warning("SpyderL11_MLModelManager not available: %s", _e)
    MLModelManager = None  # type: ignore

try:
    from .SpyderL12_RandomForestEnsemble import SpyderRandomForestEnsemble
except Exception as _e:
    _logger.debug("Optional module SpyderL12_RandomForestEnsemble not available: %s", _e)
    SpyderRandomForestEnsemble = None  # type: ignore

# SpyderL13_LSTMPricer imports PyTorch which takes 3-5 seconds on cold start.
# It is NOT imported eagerly here — import it directly when you need it:
#   from Spyder.SpyderL_ML.SpyderL13_LSTMPricer import SpyderLSTMPricer
SpyderLSTMPricer = None  # type: ignore  — lazy; import SpyderL13 directly when needed

try:
    from .SpyderL14_RealTimePredictor import RealTimePredictor
except Exception as _e:
    _logger.warning("SpyderL14_RealTimePredictor not available: %s", _e)
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
# L15–L19 — additional ML modules
try:
    from .SpyderL15_MomentPredictor import MOmentPredictor as MomentPredictor
    __all__.extend(["MomentPredictor"])
except Exception as _e:
    MomentPredictor = None  # type: ignore

try:
    from .SpyderL16_OptionsAdjustmentRL import OptionsAdjustmentRL, SPYOptionsEnvironment
    __all__.extend(["OptionsAdjustmentRL", "SPYOptionsEnvironment"])
except Exception as _e:
    OptionsAdjustmentRL = None  # type: ignore
    SPYOptionsEnvironment = None  # type: ignore

try:
    from .SpyderL17_FederatedLearning import FederatedLearningManager
    __all__.extend(["FederatedLearningManager"])
except Exception as _e:
    FederatedLearningManager = None  # type: ignore

try:
    from .SpyderL18_EnhancedMLIntegration import EnhancedMLEngine
    __all__.extend(["EnhancedMLEngine"])
except Exception as _e:
    EnhancedMLEngine = None  # type: ignore

try:
    from .SpyderL19_RLTrainingPipeline import RLTrainingPipeline
    __all__.extend(["RLTrainingPipeline"])
except Exception as _e:
    RLTrainingPipeline = None  # type: ignore

try:
    from .SpyderL13_LSTMPricer import SpyderLSTMPricer
    __all__.extend(["SpyderLSTMPricer"])
except Exception as _e:
    SpyderLSTMPricer = None  # type: ignore

# PACKAGE METADATA
# ==============================================================================
__package_name__ = "{package_name}"
__description__ = "{description}"
__version__ = "1.4.0"
