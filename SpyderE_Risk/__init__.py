#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Risk Management Package (Simplified)

This package provides risk management functionality for the Spyder trading system.
Simplified to avoid circular import issues during development.
"""

__version__ = '1.0.0'

# Only import the main RiskManager to avoid circular imports
try:
    from .SpyderE01_RiskManager import RiskManager, RiskProfile
    __all__ = ['RiskManager', 'RiskProfile']
except ImportError as e:
    print(f"Warning: Could not import RiskManager: {e}")
    __all__ = []
