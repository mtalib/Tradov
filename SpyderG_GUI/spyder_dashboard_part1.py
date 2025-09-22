#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG05_TradingDashboard.py 
Purpose: Complete Trading Dashboard with Real Data Integration & Enhanced Features
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-24 Time: 12:00:00

Module Description:
    Enhanced trading dashboard that seamlessly integrates real market data from IB Gateway
    while maintaining full functionality in simulation mode. Features automatic detection
    and switching between real and simulation data, comprehensive signal monitoring,
    unified Prometheus metrics, and professional dark theme interface. Built on the
    proven real data integration pattern from temp_WorkingRealDashboard.py.

FEATURES:
    • Automatic real data detection and seamless switching
    • Simulation fallback with monitoring for real data availability
    • Professional signal monitor with 12 indicators including HMM/SKEW
    • Unified Prometheus Metrics table (IB Clients 1-10 + Internal Modules)
    • Market hours awareness and connection health monitoring
    • Custom metrics integration (GEX/DEX/OGL/DIX/SWAN)
    • Enhanced P&L tracking and risk monitoring
    • Professional dark theme with traffic light indicators
    • 30-second heartbeat connection monitoring with visual indicator

REAL DATA INTEGRATION:
    • Data Source: ~/Projects/Spyder/market_data/live_data.json
    • Auto-detection with fallback to simulation mode
    • Status indicators show real vs simulation data source
    • Enhanced refresh functionality for both data modes
    • Proven integration pattern from working test module

IB CONNECTION MONITORING:
    • 30-second heartbeat timer for connection health checks
    • Visual heartbeat indicator with 3-state system
    • Automatic FROZEN DATA detection during market hours
    • Fixed-width status containers prevent UI jumping
    • Real-time connection status updates
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import os
import socket
import time
import traceback
import json
from datetime import datetime, timedelta, time as dt_time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import random
import numpy as np
from threading import Lock
import queue
import pytz
from pathlib import Path

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QSplitter,
    QFrame,
    QScrollArea,
    QTextEdit,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QGroupBox,
    QTabWidget,
    QProgressBar,
    QSlider,
    QStyle,
    QMessageBox,
)
from PySide6.QtCore import (
    Qt,
    QTimer,
    Signal,
    QThread,
    Slot,
    QSize,
    QRect,
    QPoint,
    QObject,
    QMutex,
    QMutexLocker,
)
from PySide6.QtGui import (
    QFont,
    QPalette,
    QColor,
    QIcon,
    QPixmap,
    QPainter,
    QBrush,
    QShortcut,
    QKeySequence,
    QPen,
    QTextCursor,
    QAction,
)

# Matplotlib for charting
import matplotlib

matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import pandas as pd

# ==============================================================================
# IB_ASYNC IMPORTS
# ==============================================================================
try:
    from ib_async import IB, Stock, Index, Future, Contract, Ticker

    print("✅ Using ib_async for IB Gateway connection")
except ImportError:
    print("⚠️ ib_async not available - using simulation mode")

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# Import Signal Info Dialog for popup system
try:
    from SpyderG_GUI.SpyderG12_SignalInfoDialog import SignalInfoDialog

    SIGNAL_DIALOG_AVAILABLE = True
    print("✅ Signal Info Dialog module available")
except ImportError:
    SIGNAL_DIALOG_AVAILABLE = False
    print("⚠️ Signal Info Dialog not available - using fallback QMessageBox")

# Import Risk Parameters Dialog
try:
    from SpyderG_GUI.SpyderG09_RiskParametersDialog import (
        RiskParametersDialog,
        show_risk_parameters_dialog,
    )

    RISK_DIALOG_AVAILABLE = True
    print("✅ Risk Parameters Dialog module available")
except ImportError:
    RISK_DIALOG_AVAILABLE = False
    print("⚠️ Risk Parameters Dialog not available")

# Import HMM and SKEW Dialog modules
try:
    from SpyderM_Monitoring.SpyderM06_HMMRegimeDetector import HMMMonitorDialog

    HMM_DIALOG_AVAILABLE = True
    print("✅ HMM Monitor Dialog available")
except ImportError:
    HMM_DIALOG_AVAILABLE = False
    print("⚠️ HMM Monitor Dialog not available")

try:
    from SpyderG_GUI.SpyderG11_SkewMonitorDialog import SkewMonitorDialog

    SKEW_DIALOG_AVAILABLE = True
    print("✅ SKEW Monitor Dialog available")
except ImportError:
    SKEW_DIALOG_AVAILABLE = False
    print("⚠️ SKEW Monitor Dialog not available")

# Try to import Prometheus metrics display module if available
try:
    from SpyderG07_PrometheusMetricsDisplay import get_client_status, get_system_metrics

    PROMETHEUS_AVAILABLE = True
    print("✅ Prometheus metrics collector available")
except ImportError:
    PROMETHEUS_AVAILABLE = False
    print("⚠️ Prometheus metrics collector not available - using simulation")

# ==============================================================================
# CONSTANTS
# ==============================================================================
WINDOW_WIDTH = 1920
WINDOW_HEIGHT = 1080

# Use the proven working client ID
CLIENT_ID = 2

# Market hours (Eastern Time)
MARKET_OPEN_TIME = dt_time(4, 0)  # 4:00 AM ET
MARKET_CLOSE_TIME = dt_time(16, 30)  # 4:30 PM ET

# Heartbeat and connection monitoring
HEARTBEAT_INTERVAL = 30000  # 30 seconds in milliseconds
HEARTBEAT_WARNING_TIME = 20000  # 20 seconds before next check (blue heart)

# COMPLETE MARKET SYMBOLS FROM T09
MARKET_SYMBOLS = {
    "S&P CORE": ["SPY", "SPX", "/ES"],
    "VOLATILITY": ["VIX", "VXV", "VXMT", "VVIX", "UVXY"],
    "MARKET INTERNALS": ["$TICK", "$TRIN", "$ADD", "CPC", "PCALL", "SKEW", "VUD"],
    "MAJOR INDICES": ["DIA", "QQQ", "IWM"],
    "BONDS & CREDIT": ["TLT", "LQD"],
    "CORRELATIONS": ["DXY", "GLD"],
    "CUSTOM METRICS": ["GEX", "DEX", "OGL", "DIX", "SWAN"],
}

# Symbol descriptions for tooltips
SYMBOL_DESCRIPTIONS = {
    # S&P Core
    "SPY": "SPDR S&P 500 ETF - Most liquid S&P 500 ETF",
    "SPX": "S&P 500 Index - Cash index value",
    "/ES": "E-mini S&P 500 Futures - 24/5 trading",
    # Volatility
    "VIX": "CBOE Volatility Index - 30-day implied volatility",
    "VIX9D": "CBOE 9-Day Volatility Index - Short-term volatility",
    "VXV": "CBOE 3-Month Volatility Index - 93-day implied volatility",
    "VXMT": "CBOE Mid-Term Volatility Index - 6-month volatility",
    "VVIX": "VIX of VIX - Volatility of volatility index",
    "UVXY": "ProShares Ultra VIX Short-Term Futures ETF",
    # Market Internals
    "$TICK": "NYSE Tick Index - Upticks minus downticks",
    "$TRIN": "Arms Index - Advance/Decline volume ratio",
    "$ADD": "Advance-Decline Line - Net advancing issues",
    "CPC": "CBOE Put/Call Ratio - Equity options only",
    "PCALL": "Total Put/Call Ratio - All options",
    "SKEW": "CBOE Skew Index - Tail risk measure",
    "VUD": "Put/Call Volume Ratio - Options sentiment indicator",
    # Major Indices
    "DIA": "SPDR Dow Jones Industrial Average ETF",
    "QQQ": "Invesco QQQ Trust - NASDAQ 100 ETF",
    "IWM": "iShares Russell 2000 ETF - Small caps",
    # Bonds & Credit
    "TLT": "iShares 20+ Year Treasury Bond ETF",
    "LQD": "iShares Investment Grade Corporate Bond ETF",
    # Correlations
    "DXY": "US Dollar Index - Dollar strength",
    "GLD": "SPDR Gold Trust ETF - Gold proxy",
    # Custom Metrics
    "GEX": "Gamma Exposure - Market maker hedging pressure",
    "DEX": "Delta Exposure - Directional hedging flow",
    "OGL": "Zero Gamma Level - Key support/resistance",
    "DIX": "Dark Index - Dark pool buying percentage",
    "SWAN": "Black Swan Risk Indicator - Tail risk monitor",
}

COLORS = {
    "background": "#0a0a0a",
    "panel": "#1a1a1a",
    "border": "#333333",
    "text": "#ffffff",
    "text_dim": "#888888",
    "positive": "#00ff41",
    "negative": "#ff1744",
    "neutral": "#ffd700",
    "warning": "#ff9800",
    "automation_active": "#00b8d4",
    "grid": "#2a2a2a",
    "orange": "#ff9800",
    "red": "#ff0000",
    "cyan": "#00ffff",
    "yellow": "#ffff00",
    "blue": "#4169E1",
    "purple": "#9370DB",
}