#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Risk Management Package

This package provides comprehensive risk management capabilities including
Greek limits, circuit breakers, and automatic rebalancing.
"""

# Module imports with error handling
try:
    from .SpyderE01_RiskManager import RiskManager, RiskProfile
except ImportError:
    print("Warning: Could not import RiskManager")

try:
    from .SpyderE03_GreekLimitsManager import GreekLimitsManager
except ImportError:
    print("Warning: Could not import GreekLimitsManager")

try:
    from .SpyderE04_CircuitBreakerProtocol import CircuitBreaker
except ImportError:
    print("Warning: Could not import CircuitBreaker")

try:
    from .SpyderE05_AutomaticRebalancer import AutomaticRebalancer
except ImportError:
    print("Warning: Could not import AutomaticRebalancer")

# Package exports
__all__ = [
    "RiskManager",
    "RiskProfile",
    "GreekLimitsManager",
    "CircuitBreaker",
    "AutomaticRebalancer",
]

__version__ = "1.0.0"
