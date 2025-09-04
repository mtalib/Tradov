#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
from .SpyderL01_MLPredictor import MLPredictor
from .SpyderL07_PaperTradeLearner import PaperTradeLearner
from .SpyderL08_EntryOptimizer import EntryOptimizer
from .SpyderL09_UnifiedRegimeEngine import UnifiedRegimeEngine as RegimeClassifier
from .SpyderL10_FeatureEngineering import FeatureEngineer
from .SpyderL11_MLModelManager import MLModelManager
from .SpyderL12_RandomForestEnsemble import SpyderRandomForestEnsemble
from .SpyderL13_LSTMPricer import SpyderLSTMPricer
from .SpyderL14_RealTimePredictor import RealTimePredictor

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
