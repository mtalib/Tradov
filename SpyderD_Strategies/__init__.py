#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderD_Strategies
Purpose: Trading Algorithms

This package provides trading algorithms functionality for the Spyder trading system.

Author: Mohamed Talib
Date: 2025-06-14
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderD01_BaseStrategy import BaseStrategy, TradingSignal, StrategySignal
from .SpyderD02_IronCondor import IronCondorStrategy
from .SpyderD03_CreditSpread import CreditSpreadStrategy
from .SpyderD04_ZeroDTE import ZeroDTEStrategy
from .SpyderD05_Straddle import StraddleStrategy
from .SpyderD06_StrategySelector import StrategySelector
from .SpyderD07_SignalGenerator import SignalGenerator
from .SpyderD08_StrategyManager import StrategyManager, get_strategy_manager
from .SpyderD06_BullPutSpread import BullPutSpreadStrategy
from .SpyderD07_BearCallSpread import BearCallSpreadStrategy
from .SpyderD12_StrategyOrchestrator import StrategyOrchestrator
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
    "BaseStrategy",
    "BearCallSpreadStrategy",
    "BullPutSpreadStrategy",
    "CreditSpreadStrategy",
    "GreeksBasedStrategy",
    "IronButterflyStrategy",
    "IronCondorStrategy",
    "MACrossoverStrategy",
    "OpeningRangeBreakoutStrategy",
    "RSIMeanReversionStrategy",
    "SignalGenerator",
    "SpecializedZeroDTEStrategy",
    "StraddleStrategy",
    "StrategyManager",
    "StrategyOrchestrator",
    "StrategySelector",
    "StrategySignal",
    "TradingSignal",
    "ZeroDTEStrategy",
    "get_strategy_manager",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "{package_name}"
__description__ = "{description}"
__version__ = "1.4.0"
