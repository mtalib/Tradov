#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderG_GUI
Purpose: Graphical User Interface

This package provides the graphical user interface components for the
Spyder trading system.

Author: Mohamed Talib
Date: 2025-06-18
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderG01_MainWindow import MainWindow
from .SpyderG02_Dashboard import Dashboard, DashboardWidget
from .SpyderG03_GUIEntry import start_gui, SpyderGUI
from .SpyderG04_OptionChainWidget import OptionChainWidget
from .SpyderG05_ChartWidget import ChartWidget
from .SpyderG06_TradingDashboard import TradingDashboard

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    # Main window
    "MainWindow",
    
    # Dashboard
    "Dashboard",
    "DashboardWidget",
    "TradingDashboard",
    
    # GUI entry
    "start_gui",
    "SpyderGUI",
    
    # Widgets
    "OptionChainWidget",
    "ChartWidget",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderG_GUI"
__description__ = "Graphical User Interface"
__version__ = "1.4.0"