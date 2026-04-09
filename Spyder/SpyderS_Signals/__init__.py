#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Package: SpyderS_Signals
Purpose: Trading signal generation and management
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-04-03

Package Description:
    The SpyderS_Signals package provides comprehensive trading signal generation,
    processing, and management capabilities. This includes technical analysis
    signals, custom indicators, signal filtering, and signal orchestration
    for automated trading decisions.
"""
import logging

__version__ = "1.0.1"
__author__ = "Mohamed Talib"
__email__ = "mohamed.talib@spyder.ai"

__all__ = []

# S01 — DIX Calculator
try:
    from .SpyderS01_DIXCalculator import DIXCalculator
    __all__.extend(["DIXCalculator"])
except ImportError as e:
    logging.info("Warning: SpyderS01_DIXCalculator not available: %s", e)

# S02 — DIX Scheduler
try:
    from .SpyderS02_DIXScheduler import SpyderDIXScheduler
    __all__.extend(["SpyderDIXScheduler"])
except ImportError as e:
    logging.info("Warning: SpyderS02_DIXScheduler not available: %s", e)

# S03 — Black Swan Indicator
try:
    from .SpyderS03_BlackSwanIndicator import BlackSwanIndicator
    __all__.extend(["BlackSwanIndicator"])
except ImportError as e:
    logging.info("Warning: SpyderS03_BlackSwanIndicator not available: %s", e)

# S04 — Black Swan Scheduler
try:
    from .SpyderS04_BlackSwanScheduler import BlackSwanScheduler
    __all__.extend(["BlackSwanScheduler"])
except ImportError as e:
    logging.info("Warning: SpyderS04_BlackSwanScheduler not available: %s", e)

# S06 — SKEW Calculator
try:
    from .SpyderS06_SKEWCalculator import SpyderS06_SKEWCalculator
    __all__.extend(["SpyderS06_SKEWCalculator"])
except ImportError as e:
    logging.info("Warning: SpyderS06_SKEWCalculator not available: %s", e)

# S07 — Custom Metrics Orchestrator
try:
    from .SpyderS07_CustomMetricsOrchestrator import CustomMetricsOrchestrator
    __all__.extend(["CustomMetricsOrchestrator"])
except ImportError as e:
    logging.info("Warning: SpyderS07_CustomMetricsOrchestrator not available: %s", e)

try:
    from .SpyderS05_GEXDEXCalculator import GEXDEXCalculator
    __all__.extend(["GEXDEXCalculator"])
except ImportError as e:
    logging.info("Warning: SpyderS05_GEXDEXCalculator not available: %s", e)

try:
    from .SpyderS08_ShortSqueezeDetector import ShortSqueezeDetector
    __all__.extend(["ShortSqueezeDetector"])
except ImportError as e:
    logging.info("Warning: SpyderS08_ShortSqueezeDetector not available: %s", e)


# Package configuration
SIGNALS_CONFIG = {
    "max_signals_per_minute": 100,
    "signal_retention_hours": 24,
    "enable_signal_validation": True,
    "default_signal_timeout": 300,  # seconds
}


def get_package_info():
    """Get package information"""
    return {
        "name": "SpyderS_Signals",
        "version": __version__,
        "author": __author__,
        "description": "Trading signal generation and management",
        "config": SIGNALS_CONFIG,
    }

