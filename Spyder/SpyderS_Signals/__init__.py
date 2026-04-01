#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Package: SpyderS_Signals
Purpose: Trading signal generation and management
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-28

Package Description:
    The SpyderS_Signals package provides comprehensive trading signal generation,
    processing, and management capabilities. This includes technical analysis
    signals, custom indicators, signal filtering, and signal orchestration
    for automated trading decisions.

Modules Overview:
    • Signal generation and processing modules
    • Custom metrics orchestration
    • Signal validation and filtering
    • Real-time signal monitoring

Version: 1.0
License: Proprietary
"""

__version__ = "1.0.0"
__author__ = "Mohamed Talib"
__email__ = "mohamed.talib@spyder.ai"

# Package metadata
__all__ = [
    "SpyderS07_CustomMetricsOrchestrator",
    "SpyderS08_ShortSqueezeDetector",
]

# Module imports (when needed)
try:
    from . import SpyderS07_CustomMetricsOrchestrator
except ImportError:
    pass

try:
    from . import SpyderS08_ShortSqueezeDetector
except ImportError:
    pass

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
