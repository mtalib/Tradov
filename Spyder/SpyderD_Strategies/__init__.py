import logging
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
    logging.debug("Optional strategy SpyderD01_BaseStrategy not fully available")

# Iron Condor Strategy
try:
    from .SpyderD02_IronCondor import IronCondorStrategy

    __all__.extend(["IronCondorStrategy"])
except ImportError:
    logging.debug("Optional strategy SpyderD02_IronCondor not available")

# Credit Spread Strategy
try:
    from .SpyderD03_CreditSpread import CreditSpreadStrategy

    __all__.extend(["CreditSpreadStrategy"])
except ImportError:
    logging.debug("Optional strategy SpyderD03_CreditSpread not available")

# Zero DTE Strategy
try:
    from .SpyderD04_ZeroDTE import ZeroDTEStrategy

    __all__.extend(["ZeroDTEStrategy"])
except ImportError:
    logging.debug("Optional strategy SpyderD04_ZeroDTE not available")

# Straddle Strategy
try:
    from .SpyderD05_Straddle import StraddleStrategy

    __all__.extend(["StraddleStrategy"])
except ImportError:
    logging.debug("Optional strategy SpyderD05_Straddle not available")

# Bull Put Spread Strategy
try:
    from .SpyderD06_BullPutSpread import BullPutSpreadStrategy

    __all__.extend(["BullPutSpreadStrategy"])
except ImportError:
    logging.debug("Optional strategy SpyderD06_BullPutSpread not available")

# Bear Call Spread Strategy
try:
    from .SpyderD07_BearCallSpread import BearCallSpreadStrategy

    __all__.extend(["BearCallSpreadStrategy"])
except ImportError:
    logging.debug("Optional strategy SpyderD07_BearCallSpread not available")

# Opening Range Breakout Strategy
try:
    from .SpyderD08_OpeningRangeBreakout import OpeningRangeBreakoutStrategy

    __all__.extend(["OpeningRangeBreakoutStrategy"])
except ImportError:
    logging.debug("Optional strategy SpyderD08_OpeningRangeBreakout not available")

# Greeks Based Strategy
try:
    from .SpyderD09_GreeksBasedStrategy import GreeksBasedStrategy

    __all__.extend(["GreeksBasedStrategy"])
except ImportError:
    logging.debug("Optional strategy SpyderD09_GreeksBasedStrategy not available")

# Iron Butterfly Strategy
try:
    from .SpyderD10_IronButterfly import IronButterflyStrategy

    __all__.extend(["IronButterflyStrategy"])
except ImportError:
    logging.debug("Optional strategy SpyderD10_IronButterfly not available")

# Additional strategies (if they exist)
try:
    from .SpyderD11_SpecializedZeroDTE import SpecializedZeroDTEStrategy

    __all__.extend(["SpecializedZeroDTEStrategy"])
except ImportError as e:
    logging.debug("Optional strategy SpyderD11 not available: %s", e)

try:
    from .SpyderD12_RSIMeanReversion import RSIMeanReversionStrategy

    __all__.extend(["RSIMeanReversionStrategy"])
except ImportError as e:
    logging.debug("Optional strategy SpyderD12 not available: %s", e)

try:
    from .SpyderD13_MACrossover import MACrossoverStrategy

    __all__.extend(["MACrossoverStrategy"])
except ImportError as e:
    logging.debug("Optional strategy SpyderD13 not available: %s", e)

# Renaissance Mean Reversion Strategy
try:
    from .SpyderD33_RenaissanceMeanReversion import (
        RenaissanceMeanReversionStrategy,
        OptionContract,
        OptionType,
        TradeAction,
        create_renaissance_strategy,
    )

    __all__.extend([
        "RenaissanceMeanReversionStrategy",
        "OptionContract",
        "OptionType",
        "TradeAction",
        "create_renaissance_strategy",
    ])
except ImportError as e:
    logging.info("Warning: SpyderD33_RenaissanceMeanReversion not available: %s", e)

# D00, D14–D22, D25–D28, D30–D32 — additional strategy modules
try:
    from .SpyderD00_StrategyConstants import StrategyType
    __all__.extend(["StrategyType"])
except ImportError as e:
    logging.info("Warning: SpyderD00_StrategyConstants not available: %s", e)

try:
    from .SpyderD14_CalendarSpread import CalendarSpreadStrategy
    __all__.extend(["CalendarSpreadStrategy"])
except ImportError as e:
    logging.info("Warning: SpyderD14_CalendarSpread not available: %s", e)

try:
    from .SpyderD15_StraddleStrangle import StraddleStrangleStrategy
    __all__.extend(["StraddleStrangleStrategy"])
except ImportError as e:
    logging.info("Warning: SpyderD15_StraddleStrangle not available: %s", e)

try:
    from .SpyderD16_RatioSpreads import RatioSpreadsStrategy
    __all__.extend(["RatioSpreadsStrategy"])
except ImportError as e:
    logging.info("Warning: SpyderD16_RatioSpreads not available: %s", e)

try:
    from .SpyderD17_DiagonalSpread import DiagonalSpreadStrategy
    __all__.extend(["DiagonalSpreadStrategy"])
except ImportError as e:
    logging.info("Warning: SpyderD17_DiagonalSpread not available: %s", e)

try:
    from .SpyderD18_EvolvedCreditSpread import EvolvedCreditSpreadStrategy
    __all__.extend(["EvolvedCreditSpreadStrategy"])
except ImportError as e:
    logging.info("Warning: SpyderD18_EvolvedCreditSpread not available: %s", e)

try:
    from .SpyderD19_JadeLizard import JadeLizardStrategy
    __all__.extend(["JadeLizardStrategy"])
except ImportError as e:
    logging.info("Warning: SpyderD19_JadeLizard not available: %s", e)

try:
    from .SpyderD20_VerticalSpreadOptimizer import VerticalSpreadOptimizer
    __all__.extend(["VerticalSpreadOptimizer"])
except ImportError as e:
    logging.info("Warning: SpyderD20_VerticalSpreadOptimizer not available: %s", e)

try:
    from .SpyderD21_DoubleCalendar import DoubleCalendarStrategy
    __all__.extend(["DoubleCalendarStrategy"])
except ImportError as e:
    logging.info("Warning: SpyderD21_DoubleCalendar not available: %s", e)

try:
    from .SpyderD22_AdaptiveVolatility import AdaptiveVolatilityStrategy
    __all__.extend(["AdaptiveVolatilityStrategy"])
except ImportError as e:
    logging.info("Warning: SpyderD22_AdaptiveVolatility not available: %s", e)

try:
    from .SpyderD23_BrokenWingButterfly import BrokenWingButterflyStrategy
    __all__.extend(["BrokenWingButterflyStrategy"])
except ImportError as e:
    logging.info("Warning: SpyderD23_BrokenWingButterfly not available: %s", e)

try:
    from .SpyderD38_JadeLizardZero import JadeLizardZeroStrategy
    __all__.extend(["JadeLizardZeroStrategy"])
except ImportError as e:
    logging.info("Warning: SpyderD38_JadeLizardZero not available: %s", e)

try:
    from .SpyderD39_PutCreditSpread7 import PutCreditSpread7Strategy
    __all__.extend(["PutCreditSpread7Strategy"])
except ImportError as e:
    logging.info("Warning: SpyderD39_PutCreditSpread7 not available: %s", e)

try:
    from .SpyderD24_Butterfly import ButterflyStrategy
    __all__.extend(["ButterflyStrategy"])
except ImportError as e:
    logging.info("Warning: SpyderD24_Butterfly not available: %s", e)

try:
    from .SpyderD25_UnifiedCreditSpreadEngine import UnifiedCreditSpreadEngine
    __all__.extend(["UnifiedCreditSpreadEngine"])
except ImportError as e:
    logging.info("Warning: SpyderD25_UnifiedCreditSpreadEngine not available: %s", e)

try:
    from .SpyderD26_GammaScalper import GammaScalperStrategy
    __all__.extend(["GammaScalperStrategy"])
except ImportError as e:
    logging.info("Warning: SpyderD26_GammaScalper not available: %s", e)

try:
    from .SpyderD27_EarningsStrategy import EarningsStrategyHandler
    __all__.extend(["EarningsStrategyHandler"])
except ImportError as e:
    logging.info("Warning: SpyderD27_EarningsStrategy not available: %s", e)

try:
    from .SpyderD28_VIXHedging import VIXHedgingStrategy
    __all__.extend(["VIXHedgingStrategy"])
except ImportError as e:
    logging.info("Warning: SpyderD28_VIXHedging not available: %s", e)

try:
    from .SpyderD30_RegimeGatedSelector import RegimeGatedSelector
    __all__.extend(["RegimeGatedSelector"])
except ImportError as e:
    logging.info("Warning: SpyderD30_RegimeGatedSelector not available: %s", e)

try:
    from .SpyderD31_StrategyOrchestrator import StrategyOrchestrator
    __all__.extend(["StrategyOrchestrator"])
except ImportError as e:
    logging.info("Warning: SpyderD31_StrategyOrchestrator not available: %s", e)

try:
    from .SpyderD32_MultiLegStrategyCoordinator import MultiLegStrategyCoordinator
    __all__.extend(["MultiLegStrategyCoordinator"])
except ImportError as e:
    logging.info("Warning: SpyderD32_MultiLegStrategyCoordinator not available: %s", e)

try:
    from .SpyderD37_BullishStrangle import BullishStrangleStrategy
    __all__.extend(["BullishStrangleStrategy"])
except ImportError as e:
    logging.info("Warning: SpyderD37_BullishStrangle not available: %s", e)

try:
    from .SpyderD41_ZeroHFT import (
        ZERO_HFT_ALIAS,
        ZeroHFTStrategy,
        build_zero_hft_runtime_config,
        create_zero_hft_strategy,
    )
    __all__.extend([
        "ZERO_HFT_ALIAS",
        "ZeroHFTStrategy",
        "build_zero_hft_runtime_config",
        "create_zero_hft_strategy",
    ])
except ImportError as e:
    logging.info("Warning: SpyderD41_ZeroHFT not available: %s", e)

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderD_Strategies"
__description__ = "Trading Strategy Implementations"
__version__ = "1.4.0"
