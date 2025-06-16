#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderG_GUI
Purpose: Graphical User Interface

This package provides graphical user interface functionality for the Spyder trading system.

Author: Mohamed Talib
Date: 2025-06-14
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderG01_MainWindow import SpyderMainWindow
from .SpyderG02_Dashboard import TradingDashboard
from .SpyderG03_GUIEntry import GUISystemBridge
from .SpyderG04_OptionChainWidget import OptionChainWidget
from .SpyderG05_ChartWidget import ChartWidget
from .SpyderG06_TradingDashboard import TradingDashboard

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    "ChartWidget",
    "GUISystemBridge",
    "OptionChainWidget",
    "SpyderMainWindow",
    "TradingDashboard",
    "TradingDashboard",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "{package_name}"
__description__ = "{description}"
__version__ = "1.4.0"
