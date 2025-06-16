#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderI_Backtest
Purpose: Strategy Validation

This package provides strategy validation functionality for the Spyder trading system.

Author: Mohamed Talib
Date: 2025-06-14
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderI01_BacktestEngine import BacktestEngine
from .SpyderI02_DataSimulator import DataSimulator
from .SpyderI03_IBDataFetcher import IBDataFetcher
from .SpyderI04_BacktraderStrategy import BacktraderStrategy
from .SpyderI05_StrategyOptimizer import StrategyOptimizer
from .SpyderI06_BacktestMetrics import BacktestMetrics

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    "BacktestEngine",
    "BacktestMetrics",
    "BacktraderStrategy",
    "DataSimulator",
    "IBDataFetcher",
    "StrategyOptimizer",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "{package_name}"
__description__ = "{description}"
__version__ = "1.4.0"
