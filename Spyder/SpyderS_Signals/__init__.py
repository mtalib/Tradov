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
from importlib import import_module

__version__ = "1.0.1"
__author__ = "Mohamed Talib"
__email__ = "mohamed.talib@spyder.ai"

_LAZY_EXPORTS = {
    "DIXCalculator": ("SpyderS01_DIXCalculator", "DIXCalculator"),
    "SpyderDIXScheduler": ("SpyderS02_DIXScheduler", "SpyderDIXScheduler"),
    "BlackSwanIndicator": ("SpyderS03_BlackSwanIndicator", "BlackSwanIndicator"),
    "BlackSwanScheduler": ("SpyderS04_BlackSwanScheduler", "BlackSwanScheduler"),
    "SpyderS06_SKEWCalculator": (
        "SpyderS06_SKEWCalculator",
        "SpyderS06_SKEWCalculator",
    ),
    "CustomMetricsOrchestrator": (
        "SpyderS07_CustomMetricsOrchestrator",
        "CustomMetricsOrchestrator",
    ),
    "GEXDEXCalculator": ("SpyderS05_GEXDEXCalculator", "GEXDEXCalculator"),
    "ShortSqueezeDetector": (
        "SpyderS08_ShortSqueezeDetector",
        "ShortSqueezeDetector",
    ),
    "PCASignalEngine": ("SpyderS14_PCASignals", "PCASignalEngine"),
    "get_pca_signal_engine": ("SpyderS14_PCASignals", "get_pca_signal_engine"),
}

__all__: list[str] = []
__all__.extend(_LAZY_EXPORTS)


def __getattr__(name: str):
    """Lazily resolve signal exports on first access."""
    module_attr = _LAZY_EXPORTS.get(name)
    if module_attr is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attribute_name = module_attr
    try:
        module = import_module(f".{module_name}", __name__)
        value = getattr(module, attribute_name)
    except Exception as exc:
        logging.info("Warning: %s not available: %s", module_name, exc)
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Expose lazy signal exports for tooling and interactive inspection."""
    return sorted(set(globals()) | set(_LAZY_EXPORTS))


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

