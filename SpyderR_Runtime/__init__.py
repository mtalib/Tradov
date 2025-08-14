#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderR_Runtime
Purpose: Runtime Operations

This package contains runtime execution engines for backtesting, paper trading,
and live trading operations.

Author: Mohamed Talib
Date: 2025-06-18
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
# from .SpyderR01_BacktestEngine import BacktestEngine, BacktestResults
# from .SpyderR02_PaperEngine import PaperTradingEngine
# from .SpyderR03_PaperMonitor import PaperTradingMonitor
# from .SpyderR04_LiveEngine import LiveTradingEngine

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    # Backtesting
    "BacktestEngine",
    "BacktestResults",
    # Paper trading
    "PaperTradingEngine",
    "PaperTradingMonitor",
    # Live trading
    "LiveTradingEngine",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderR_Runtime"
__description__ = "Runtime Execution Engines"
__version__ = "1.4.0"
