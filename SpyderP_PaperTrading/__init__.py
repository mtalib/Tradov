#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderP_PaperTrading
Purpose: Virtual Trading Environment

This package provides virtual trading environment functionality for the Spyder trading system.

Author: Mohamed Talib
Date: 2025-06-14
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderP01_PaperEngine import PaperEngine
from .SpyderP02_PaperMonitor import PaperMonitor

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    "PaperEngine",
    "PaperMonitor",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "{package_name}"
__description__ = "{description}"
__version__ = "1.4.0"
