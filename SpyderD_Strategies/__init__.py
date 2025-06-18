#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderD_Strategies
Purpose: Trading Strategies

This package contains all trading strategy implementations including
various options strategies, entry/exit logic, and strategy management.

Author: Mohamed Talib
Date: 2025-06-18
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderD01_BaseStrategy import BaseStrategy, StrategySignal
from .SpyderD02_IronCondor import IronCondorStrategy
from .SpyderD03_CreditSpread import CreditSpreadStrategy
from .SpyderD04_ZeroDTE import ZeroDTEStrategy
from .SpyderD05_Straddle import StraddleStrategy
from .SpyderD06_BullPutSpread import BullPutSpreadStrategy
from .SpyderD07_BearCallSpread import BearCallSpreadStrategy
from .SpyderD08_OpeningRangeBreakout import OpeningRangeBreakoutStrategy
from .SpyderD09_GreeksBasedStrategy import GreeksBasedStrategy
from .SpyderD10_IronButterfly import IronButterflyStrategy
from .SpyderD11_SpecializedZeroDTE import SpecializedZeroDTEStrategy
from .SpyderD12_RSIMeanReversion import RSIMeanReversionStrategy
from .SpyderD13_MACrossover import MACrossoverStrategy

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    # Base strategy
    "BaseStrategy",
    "StrategySignal",
    
    # Options strategies
    "IronCondorStrategy",
    "CreditSpreadStrategy",
    "ZeroDTEStrategy",
    "StraddleStrategy",
    "BullPutSpreadStrategy",
    "BearCallSpreadStrategy",
    "IronButterflyStrategy",
    "SpecializedZeroDTEStrategy",
    
    # Technical strategies
    "OpeningRangeBreakoutStrategy",
    "GreeksBasedStrategy",
    "RSIMeanReversionStrategy",
    "MACrossoverStrategy",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderD_Strategies"
__description__ = "Trading Strategy Implementations"
__version__ = "1.4.0"