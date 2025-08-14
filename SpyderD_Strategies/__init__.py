#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderD_Strategies
Purpose: Trading Strategies

This package contains all trading strategy implementations including
various options strategies, entry/exit logic, and strategy management.

Author: Mohamed Talib
Date: 2025-06-24
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS (DEFENSIVE)
# ==============================================================================
__all__ = []

# Base Strategy module
try:
    from .SpyderD01_BaseStrategy import BaseStrategy, StrategySignal

    __all__.extend(["BaseStrategy", "StrategySignal"])
except ImportError:
    print("Warning: SpyderD01_BaseStrategy not fully available")

# Iron Condor Strategy
try:
    from .SpyderD02_IronCondor import IronCondorStrategy

    __all__.extend(["IronCondorStrategy"])
except ImportError:
    print("Warning: SpyderD02_IronCondor not available")

# Credit Spread Strategy
try:
    from .SpyderD03_CreditSpread import CreditSpreadStrategy

    __all__.extend(["CreditSpreadStrategy"])
except ImportError:
    print("Warning: SpyderD03_CreditSpread not available")

# Zero DTE Strategy
try:
    from .SpyderD04_ZeroDTE import ZeroDTEStrategy

    __all__.extend(["ZeroDTEStrategy"])
except ImportError:
    print("Warning: SpyderD04_ZeroDTE not available")

# Straddle Strategy
try:
    from .SpyderD05_Straddle import StraddleStrategy

    __all__.extend(["StraddleStrategy"])
except ImportError:
    print("Warning: SpyderD05_Straddle not available")

# Bull Put Spread Strategy
try:
    from .SpyderD06_BullPutSpread import BullPutSpreadStrategy

    __all__.extend(["BullPutSpreadStrategy"])
except ImportError:
    print("Warning: SpyderD06_BullPutSpread not available")

# Bear Call Spread Strategy
try:
    from .SpyderD07_BearCallSpread import BearCallSpreadStrategy

    __all__.extend(["BearCallSpreadStrategy"])
except ImportError:
    print("Warning: SpyderD07_BearCallSpread not available")

# Opening Range Breakout Strategy
try:
    from .SpyderD08_OpeningRangeBreakout import OpeningRangeBreakoutStrategy

    __all__.extend(["OpeningRangeBreakoutStrategy"])
except ImportError:
    print("Warning: SpyderD08_OpeningRangeBreakout not available")

# Greeks Based Strategy
try:
    from .SpyderD09_GreeksBasedStrategy import GreeksBasedStrategy

    __all__.extend(["GreeksBasedStrategy"])
except ImportError:
    print("Warning: SpyderD09_GreeksBasedStrategy not available")

# Iron Butterfly Strategy
try:
    from .SpyderD10_IronButterfly import IronButterflyStrategy

    __all__.extend(["IronButterflyStrategy"])
except ImportError:
    print("Warning: SpyderD10_IronButterfly not available")

# Additional strategies (if they exist)
try:
    from .SpyderD11_SpecializedZeroDTE import SpecializedZeroDTEStrategy

    __all__.extend(["SpecializedZeroDTEStrategy"])
except ImportError:
    pass  # Optional module

try:
    from .SpyderD12_RSIMeanReversion import RSIMeanReversionStrategy

    __all__.extend(["RSIMeanReversionStrategy"])
except ImportError:
    pass  # Optional module

try:
    from .SpyderD13_MACrossover import MACrossoverStrategy

    __all__.extend(["MACrossoverStrategy"])
except ImportError:
    pass  # Optional module

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderD_Strategies"
__description__ = "Trading Strategy Implementations"
__version__ = "1.4.0"
