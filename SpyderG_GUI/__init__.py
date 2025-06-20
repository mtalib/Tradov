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
from .SpyderG01_MainWindow import SpyderMainWindow
from .SpyderG02_Dashboard import TradingDashboard as G02_TradingDashboard
from .SpyderG03_GUIEntry import main as start_gui, SpyderGUIApplication
from .SpyderG04_OptionChainWidget import OptionChainWidget
from .SpyderG05_ChartWidget import ChartWidget
from .SpyderG06_TradingDashboard import SpyderTradingDashboard as TradingDashboard

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    # Main window
    "SpyderMainWindow",
    "MainWindow",  # Alias for backward compatibility
    
    # Dashboard
    "TradingDashboard",
    "Dashboard",  # Alias for backward compatibility
    "DashboardWidget",  # Alias for backward compatibility
    
    # GUI entry
    "start_gui",
    "SpyderGUI",  # Alias
    "SpyderGUIApplication",
    
    # Widgets
    "OptionChainWidget",
    "ChartWidget",
]

# Create aliases for backward compatibility
MainWindow = SpyderMainWindow
Dashboard = G02_TradingDashboard
DashboardWidget = G02_TradingDashboard
SpyderGUI = SpyderGUIApplication

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderG_GUI"
__description__ = "Graphical User Interface"
__version__ = "1.4.0"