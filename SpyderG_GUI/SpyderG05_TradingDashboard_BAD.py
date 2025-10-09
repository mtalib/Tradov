#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI [Application Name] [Group Letter] [Group Name]
Module: SpyderG05_TradingDashboard.py [Application Name][Group Letter] [Module Number]_[Purpose].py
Purpose: Complete Trading Dashboard with Real Data Integration & Enhanced Features + Gateway Control
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-10-09 Time: 14:30:00

Module Description:
    Enhanced trading dashboard that seamlessly integrates real market data from IB Gateway
    while maintaining full functionality in simulation mode. Features automatic detection
    and switching between real and simulation data, comprehensive signal monitoring,
    unified Prometheus metrics, and professional dark theme interface. Built on the
    proven real data integration pattern from temp_WorkingRealDashboard.py.
    
    NEW: Integrated with Gateway Control Panel (G14) and Client Connection Manager (G15)
    for automated IB Gateway startup and 8-client connection management.

FEATURES:
    • Automatic real data detection and seamless switching
    • Simulation fallback with monitoring for real data availability
    • Professional signal monitor with 12 indicators including HMM/SKEW
    • Unified Prometheus Metrics table (IB Clients 1-8 + Internal Modules)
    • Market hours awareness and connection health monitoring
    • Custom metrics integration (GEX/DEX/OGL/DIX/SWAN)
    • Enhanced P&L tracking and risk monitoring
    • Professional dark theme with traffic light indicators
    • 30-second heartbeat connection monitoring with visual indicator
    • Gateway Control Panel integration (dockable widget)
    • 8-client connection management with clickable reconnection

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

GATEWAY CONTROL (NEW):
    • Integrated Gateway Control Panel (dockable)
    • Automated Gateway startup via IBC
    • 8-client sequential connection with proper delays
    • Individual client reconnection (clickable indicators)
    • Connection progress tracking and status monitoring
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
from SpyderB_Broker.SpyderB29_EnhancedConnectionManager import (
    get_connection_manager,
    ConnectionConfig,
    TradingMode,
)

# Import Signal Info Dialog for popup system
try:
    from SpyderG_GUI.SpyderG12_SignalInfoDialog import SignalInfoDialog

    signal_dialog_available = True
    print("✅ Signal Info Dialog module available")
except ImportError:
    SignalInfoDialog = None  # type: ignore
    signal_dialog_available = False
    print("⚠️ Signal Info Dialog not available - using fallback QMessageBox")

# Import Risk Parameters Dialog
try:
    from SpyderG_GUI.SpyderG09_RiskParametersDialog import (
        RiskParametersDialog,
        show_risk_parameters_dialog,
    )

    risk_dialog_available = True
    print("✅ Risk Parameters Dialog module available")
except ImportError:
    RiskParametersDialog = None  # type: ignore
    show_risk_parameters_dialog = None  # type: ignore
    risk_dialog_available = False
    print("⚠️ Risk Parameters Dialog not available")

# Import HMM and SKEW Dialog modules
try:
    from SpyderM_Monitoring.SpyderM06_HMMRegimeDetector import HMMMonitorDialog

    hmm_dialog_available = True
    print("✅ HMM Monitor Dialog available")
except ImportError:
    HMMMonitorDialog = None  # type: ignore
    hmm_dialog_available = False
    print("⚠️ HMM Monitor Dialog not available")

try:
    from SpyderG_GUI.SpyderG11_SkewMonitorDialog import SkewMonitorDialog

    skew_dialog_available = True
    print("✅ SKEW Monitor Dialog available")
except ImportError:
    SkewMonitorDialog = None  # type: ignore
    skew_dialog_available = False
    print("⚠️ SKEW Monitor Dialog not available")

# Try to import Prometheus metrics display module if available
try:
    from SpyderG_GUI.SpyderG07_PrometheusMetricsDisplay import (
        get_client_status,
        get_system_metrics,
    )

    prometheus_available = True
    print("✅ Prometheus metrics collector available")
except ImportError:
    get_client_status = None  # type: ignore
    get_system_metrics = None  # type: ignore
    prometheus_available = False
    print("⚠️ Prometheus metrics collector not available - using simulation")

# ==============================================================================
# NEW IMPORTS FOR GATEWAY AUTOMATION
# ==============================================================================
try:
    from SpyderG_GUI.SpyderG14_GatewayControlPanel import (
        create_gateway_dock_widget,
        GatewayControlPanel
    )
    gateway_panel_available = True
    print("✅ Gateway Control Panel available")
except ImportError:
    gateway_panel_available = False
    print("⚠️ Gateway Control Panel not available")

try:
    from SpyderG_GUI.SpyderG15_ClientConnectionManager import (
        ClientConnectionManager,
        ClientStatus
    )
    client_manager_available = True
    print("✅ Client Connection Manager available")
except ImportError:
    client_manager_available = False
    print("⚠️ Client Connection Manager not available")

# ==============================================================================
# CONSTANTS
# ==============================================================================
WINDOW_WIDTH = 1920
WINDOW_HEIGHT = 1080


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


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================
def is_market_hours():
    """Check if current time is within market hours (4:00 AM - 4:30 PM ET)"""
    eastern = pytz.timezone("US/Eastern")
    now_et = datetime.now(eastern).time()
    return MARKET_OPEN_TIME <= now_et <= MARKET_CLOSE_TIME


def check_ib_gateway_connection():
    """Check if IB Gateway is running - ENHANCED WITH DEBUG"""
    try:
        # Check paper trading port first (4002)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)  # Increased timeout
        paper_result = sock.connect_ex(("127.0.0.1", 4002))
        sock.close()

        if paper_result == 0:
            print("✅ IB Gateway detected on port 4002 (PAPER)")
            return True, "PAPER (Port 4002)"

        # Check live trading port (4001)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)  # Increased timeout
        live_result = sock.connect_ex(("127.0.0.1", 4001))
        sock.close()

        if live_result == 0:
            print("✅ IB Gateway detected on port 4001 (LIVE)")
            return True, "LIVE (Port 4001)"

        print("❌ No IB Gateway detected on ports 4001 or 4002")
        return False, "No IB Gateway detected"

    except Exception as e:
        print(f"❌ IB Gateway connection check failed: {e}")
        return False, f"Check failed: {e}"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class MarketData:
    symbol: str
    last: float
    change: float
    change_pct: float
    timestamp: datetime


@dataclass
class GreekRisk:
    delta: float
    gamma: float
    theta: float
    vega: float


@dataclass
class ConnectionInfo:
    ib_connected: bool = False
    bridge_connected: bool = False
    connection_mode: str = "DISCONNECTED"
    market_data_status: str = "NONE"
    trading_active: bool = False
    last_update: Optional[datetime] = None
    last_successful_data: Optional[datetime] = None
    data_was_live: bool = False
    simulation_mode: bool = False


# ==============================================================================
# THREAD-SAFE MARKET DATA WORKER - FIXED CONNECTION DETECTION
# ==============================================================================
class ThreadSafeMarketDataWorker(QObject):
    """Thread-safe market data worker with real IB connection detection and heartbeat monitoring"""

    data_updated = Signal(dict)
    connection_status_changed = Signal(bool, str)
    market_data_status_changed = Signal(str)
    error_occurred = Signal(str)
    heartbeat_received = Signal(str)
    heartbeat_status_changed = Signal(str)  # New signal for heartbeat status
    log_message = Signal(str)  # New signal for log messages

    def __init__(self):
        super().__init__()
        self.logger = SpyderLogger.get_logger(__name__)

        # FIXED: Start with actual connection check instead of assuming connected
        self.ib_connected = False

        self.market_data = {}
        self.data_mutex = QMutex()
        self.client_id = 0  # Dedicated client ID for the dashboard worker
        self.market_hours = is_market_hours()

        # Initialize timer references (will be created in start() method)
        self.update_timer = None
        self.market_hours_timer = None
        self.heartbeat_timer = None
        self.heartbeat_warning_timer = None

        self.last_data_update = {}
        self._init_simulation_data()

        print(f"🔧 Market Data Worker initialized with heartbeat monitoring")
        print(f"📊 Market: {'OPEN' if self.market_hours else 'CLOSED'}")

    def start(self):
        """Start the worker - called when thread starts (runs in worker thread)"""
        # Check connection AFTER moving to thread
        self._check_initial_connection()

        # CRITICAL FIX: Create QTimers in the worker thread, not main thread
        # Data update timer (simulation)
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._emit_data)
        self.update_timer.start(2000)

        # Market hours check timer
        self.market_hours_timer = QTimer()
        self.market_hours_timer.timeout.connect(self._check_market_hours)
        self.market_hours_timer.start(60000)

        # HEARTBEAT MONITORING SYSTEM
        self.heartbeat_timer = QTimer()
        self.heartbeat_timer.timeout.connect(self._heartbeat_check)
        self.heartbeat_timer.start(HEARTBEAT_INTERVAL)  # 30 seconds

        # Heartbeat warning timer (blue heart indicator)
        self.heartbeat_warning_timer = QTimer()
        self.heartbeat_warning_timer.timeout.connect(self._heartbeat_warning)

        print("🚀 Starting Thread-Safe Market Data Worker with heartbeat monitoring...")
        print(
            f"📡 Initial IB Connection: {'CONNECTED' if self.ib_connected else 'DISCONNECTED'}"
        )

    def _check_initial_connection(self):
        """Check actual IB Gateway connection on startup - ENHANCED WITH DEBUG"""
        try:
            print("🔍 Checking initial IB Gateway connection...")
            connected, mode = check_ib_gateway_connection()
            self.ib_connected = connected

            if connected:
                print(f"✅ IB Gateway detected: {mode}")
                # Emit log message instead of error
                self.log_message.emit(f"✅ IB Gateway detected at startup: {mode}")
            else:
                print(f"❌ No IB Gateway connection detected")
                # Emit log message instead of error
                self.log_message.emit("❌ No IB Gateway connection detected at startup")

        except Exception as e:
            print(f"⚠️ Connection check error: {e}")
            # Emit log message instead of error
            self.log_message.emit(f"⚠️ Initial connection check error: {e}")
            self.ib_connected = False

    def _heartbeat_check(self):
        """30-second heartbeat check for IB Gateway connection"""
        try:
            # Check actual connection
            connected, mode = check_ib_gateway_connection()
            previous_status = self.ib_connected
            self.ib_connected = connected

            # Emit heartbeat status based on connection
            if connected:
                self.heartbeat_status_changed.emit("connected")  # Green heart
                if not previous_status:
                    # Connection restored
                    self.connection_status_changed.emit(True, f"IB CONNECTED ({mode})")
                    self.heartbeat_received.emit(
                        f"💚 Heartbeat: IB Gateway connection restored ({mode})"
                    )
                else:
                    self.heartbeat_received.emit(
                        f"💚 Heartbeat: IB Gateway healthy ({mode})"
                    )
            else:
                self.heartbeat_status_changed.emit("disconnected")  # Red heart
                if previous_status:
                    # Connection lost
                    self.connection_status_changed.emit(False, "IB DISCONNECTED")
                    self.heartbeat_received.emit(
                        "💔 Heartbeat: IB Gateway connection lost"
                    )
                else:
                    self.heartbeat_received.emit(
                        "💔 Heartbeat: IB Gateway still disconnected"
                    )

            # Start warning timer for blue heart (10 seconds before next check)
            if self.heartbeat_warning_timer:
                self.heartbeat_warning_timer.start(HEARTBEAT_WARNING_TIME)

        except Exception as e:
            self.heartbeat_status_changed.emit("error")  # Red heart
            self.heartbeat_received.emit(f"💔 Heartbeat error: {e}")

    def _heartbeat_warning(self):
        """Show blue heart 20 seconds before next heartbeat check"""
        self.heartbeat_status_changed.emit("warning")  # Blue heart
        if self.heartbeat_warning_timer:
            self.heartbeat_warning_timer.stop()

    def _init_simulation_data(self):
        """Initialize simulation data with all symbols"""
        base_prices = {
            "SPY": 585.25,
            "SPX": 5850.75,
            "/ES": 5852.50,
            "VIX": 15.32,
            "VIX9D": 14.8,
            "VXV": 16.2,
            "VXMT": 17.5,
            "VVIX": 82.45,
            "UVXY": 22.18,
            "$TICK": 234,
            "$TRIN": 0.85,
            "$ADD": 1245,
            "CPC": 0.95,
            "PCALL": 0.88,
            "SKEW": 125.5,
            "DIA": 425.33,
            "QQQ": 485.92,
            "IWM": 225.18,
            "TLT": 92.45,
            "LQD": 105.32,
            "DXY": 103.25,
            "GLD": 195.67,
            "GEX": -2500000000,
            "DEX": 850000000,
            "OGL": 585.50,
            "DIX": 42.5,
            "SWAN": 1.85,
        }

        with QMutexLocker(self.data_mutex):
            for symbol, price in base_prices.items():
                self.market_data[symbol] = {
                    "symbol": symbol,
                    "last": price,
                    "change": 0,
                    "change_pct": 0,
                    "timestamp": datetime.now(),
                }
                self.last_data_update[symbol] = datetime.now()

    def _check_market_hours(self):
        """Check if market hours status has changed"""
        current_market_hours = is_market_hours()

        if current_market_hours != self.market_hours:
            self.market_hours = current_market_hours
            print(
                f"📊 Market hours changed: {'OPEN' if self.market_hours else 'CLOSED'}"
            )

            if not self.market_hours:
                if self.ib_connected:
                    self.market_data_status_changed.emit("NONE")

    def _emit_data(self):
        """Emit current market data"""
        with QMutexLocker(self.data_mutex):
            data_copy = self.market_data.copy()

        self._update_simulation_data(data_copy)
        self.data_updated.emit(data_copy)

    def _update_simulation_data(self, data: dict):
        """Update simulation data with realistic market movements"""
        if not is_market_hours():
            return

        current_time = datetime.now()

        for symbol, market_info in data.items():
            if symbol not in ["GEX", "DEX", "OGL", "DIX", "SWAN"]:
                old_price = market_info["last"]
                change = random.uniform(-0.5, 0.5)
                new_price = old_price + change
                change_pct = (change / old_price * 100) if old_price != 0 else 0

                market_info.update(
                    {
                        "last": new_price,
                        "change": change,
                        "change_pct": change_pct,
                        "timestamp": current_time,
                    }
                )

            with QMutexLocker(self.data_mutex):
                self.last_data_update[symbol] = current_time

    def force_connect(self):
        """Manual connect - now checks actual connection"""
        print("🔥 Manual connect requested")
        if not is_market_hours():
            print("📊 Cannot connect - market is closed")
            return False

        # Check actual connection
        connected, mode = check_ib_gateway_connection()
        self.ib_connected = connected

        if connected:
            self.connection_status_changed.emit(True, f"IB CONNECTED ({mode})")
            self.market_data_status_changed.emit("LIVE")
            return True
        else:
            self.connection_status_changed.emit(False, "IB DISCONNECTED")
            self.market_data_status_changed.emit("NONE")
            return False

    def force_disconnect(self):
        """Manual disconnect"""
        print("🔥 Manual disconnect requested")
        self.ib_connected = False
        self.connection_status_changed.emit(False, "IB DISCONNECTED")
        self.market_data_status_changed.emit("NONE")

    def stop(self):
        """Stop worker and all timers"""
        print("🛑 Stopping worker and heartbeat monitoring...")
        if self.update_timer:
            self.update_timer.stop()
        if self.market_hours_timer:
            self.market_hours_timer.stop()
        if self.heartbeat_timer:
            self.heartbeat_timer.stop()
        if self.heartbeat_warning_timer:
            self.heartbeat_warning_timer.stop()


# ==============================================================================
# WIDGET CLASSES (UNCHANGED)
# ==============================================================================
class TrafficLightButton(QPushButton):
    """Custom button that looks like a traffic light with label"""

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.label = label
        self.status = "green"
        self.setFixedHeight(24)
        self.setMinimumWidth(120)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            """
            QPushButton {
                background-color: transparent;
                border: none;
                text-align: left;
                padding-left: 25px;
                color: #ffffff;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #2a2a2a;
                border-radius: 3px;
            }

            QToolTip {
                color: white;
                background-color: #2a2a2a;
                border: 1px solid #555;
                padding: 5px;
                border-radius: 3px;
                font-size: 12px;
            }"""
        )
        self.setText(label)

    def set_status(self, status: str):
        """Set traffic light status: green, yellow, red, blue, purple"""
        self.status = status
        self.update()

    def paintEvent(self, event):
        """Custom paint for traffic light indicator"""
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        circle_rect = self.rect().adjusted(5, 5, -self.width() + 19, -5)

        if self.status == "green":
            color = QColor(COLORS["positive"])
        elif self.status == "yellow":
            color = QColor(COLORS["warning"])
        elif self.status == "red":
            color = QColor(COLORS["negative"])
        elif self.status == "blue":
            color = QColor(COLORS["blue"])
        elif self.status == "purple":
            color = QColor(COLORS["purple"])
        else:
            color = QColor(COLORS["neutral"])

        painter.setBrush(QBrush(color))
        painter.setPen(QPen(color.darker(150), 1))
        painter.drawEllipse(circle_rect)


class SignalMonitorPanel(QWidget):
    """Enhanced Signal Monitor Panel with integrated popup dialogs"""

    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent)
        self.setFixedHeight(165)
        self.setMinimumWidth(280)
        self.setStyleSheet(
            f"""
            QWidget {{
                background-color: {COLORS["panel"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 5px;
            }}
        """
        )

        layout = QGridLayout()
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(3)

        # Create all 12 buttons (2x6 grid)
        self.vix_button = TrafficLightButton("VIX MONITOR")
        self.ai_button = TrafficLightButton("AI DECISION")
        self.gex_button = TrafficLightButton("GEX")
        self.dix_button = TrafficLightButton("DIX")
        self.rsi_button = TrafficLightButton("RSI CONFLUENCE")
        self.risk_button = TrafficLightButton("RISK TRIGGERS")
        self.ogl_button = TrafficLightButton("OGL")
        self.div_button = TrafficLightButton("DIVERGENCE")
        self.dex_button = TrafficLightButton("DEX")
        self.swan_button = TrafficLightButton("BLACK SWAN")
        self.hmm_button = TrafficLightButton("HMM")
        self.skew_button = TrafficLightButton("SKEW")

        # Add buttons to grid (6 rows, 2 columns)
        layout.addWidget(self.vix_button, 0, 0)
        layout.addWidget(self.ai_button, 0, 1)
        layout.addWidget(self.gex_button, 1, 0)
        layout.addWidget(self.dix_button, 1, 1)
        layout.addWidget(self.rsi_button, 2, 0)
        layout.addWidget(self.risk_button, 2, 1)
        layout.addWidget(self.ogl_button, 3, 0)
        layout.addWidget(self.div_button, 3, 1)
        layout.addWidget(self.dex_button, 4, 0)
        layout.addWidget(self.swan_button, 4, 1)
        layout.addWidget(self.hmm_button, 5, 0)
        layout.addWidget(self.skew_button, 5, 1)

        # Connect buttons to their dialog methods
        self.vix_button.clicked.connect(self.show_vix_dialog)
        self.ai_button.clicked.connect(self.show_ai_dialog)
        self.gex_button.clicked.connect(self.show_gex_dialog)
        self.dix_button.clicked.connect(self.show_dix_dialog)
        self.rsi_button.clicked.connect(self.show_rsi_dialog)
        self.risk_button.clicked.connect(self.show_risk_dialog)
        self.ogl_button.clicked.connect(self.show_ogl_dialog)
        self.div_button.clicked.connect(self.show_div_dialog)
        self.dex_button.clicked.connect(self.show_dex_dialog)
        self.swan_button.clicked.connect(self.show_swan_dialog)
        self.hmm_button.clicked.connect(self.show_hmm_dialog)
        self.skew_button.clicked.connect(self.show_skew_dialog)

        self.setLayout(layout)

        # Store current dialog reference for auto-close functionality
        self.current_dialog = None

        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_button_states)
        self.update_timer.start(5000)

    def update_button_states(self):
        """Update traffic light colors"""
        import random

        # Original 10 buttons
        for button in [
            self.vix_button,
            self.ai_button,
            self.gex_button,
            self.dix_button,
            self.rsi_button,
            self.risk_button,
            self.ogl_button,
            self.div_button,
            self.dex_button,
        ]:
            button.set_status(random.choice(["green", "yellow", "red"]))

        # SWAN - weighted probability
        swan_random = random.random()
        if swan_random < 0.85:
            self.swan_button.set_status("green")
        elif swan_random < 0.95:
            self.swan_button.set_status("yellow")
        else:
            self.swan_button.set_status("red")

        # HMM - uses blue/purple for regime states
        hmm_random = random.random()
        if hmm_random < 0.4:
            self.hmm_button.set_status("green")
        elif hmm_random < 0.7:
            self.hmm_button.set_status("blue")
        elif hmm_random < 0.9:
            self.hmm_button.set_status("yellow")
        else:
            self.hmm_button.set_status("red")

        # SKEW - based on tail risk levels
        skew_random = random.random()
        if skew_random < 0.5:
            self.skew_button.set_status("green")
        elif skew_random < 0.8:
            self.skew_button.set_status("yellow")
        else:
            self.skew_button.set_status("red")

    def close_current_dialog(self):
        """Close the currently open dialog if any"""
        if (
            self.current_dialog
            and hasattr(self.current_dialog, "isVisible")
            and self.current_dialog.isVisible()
        ):
            self.current_dialog.close()
            self.current_dialog = None

    def show_signal_dialog(self, signal_type: str):
        """Generic method to show signal dialog with auto-close functionality"""
        self.close_current_dialog()

        if signal_dialog_available and SignalInfoDialog:
            self.current_dialog = SignalInfoDialog(signal_type, self)
            # Position the dialog to the right of the signal panel
            parent_pos = self.mapToGlobal(self.rect().topRight())
            self.current_dialog.move(parent_pos.x() + 10, parent_pos.y())
            # Connect the closed signal to clear the reference
            self.current_dialog.closed.connect(
                lambda: setattr(self, "current_dialog", None)
            )
            self.current_dialog.show()

    # Dialog show methods
    def show_vix_dialog(self):
        if signal_dialog_available:
            self.show_signal_dialog("VIX MONITOR")
        else:
            QMessageBox.information(
                self, "VIX Monitor", "VIX: 15.32\nStatus: Normal\nImplied Move: ±0.96%"
            )

    def show_ai_dialog(self):
        if signal_dialog_available:
            self.show_signal_dialog("AI DECISION")
        else:
            QMessageBox.information(
                self,
                "AI Decision",
                "Current Signal: NEUTRAL\nConfidence: 72%\nNext Decision: 5 min",
            )

    def show_gex_dialog(self):
        if signal_dialog_available:
            self.show_signal_dialog("GEX")
        else:
            QMessageBox.information(
                self,
                "GEX Monitor",
                "GEX: -$2.5B\nGamma Flip: 590\nRegime: Negative Gamma",
            )

    def show_dix_dialog(self):
        if signal_dialog_available:
            self.show_signal_dialog("DIX")
        else:
            QMessageBox.information(
                self, "DIX Monitor", "DIX: 42.5%\nDark Pool: Normal\nSentiment: Neutral"
            )

    def show_rsi_dialog(self):
        if signal_dialog_available:
            self.show_signal_dialog("RSI CONFLUENCE")
        else:
            QMessageBox.information(
                self, "RSI Confluence", "RSI(14): 52\nRSI(5): 48\nStatus: Neutral Range"
            )

    def show_risk_dialog(self):
        if signal_dialog_available:
            self.show_signal_dialog("RISK TRIGGERS")
        else:
            QMessageBox.information(
                self,
                "Risk Triggers",
                "Active Triggers: 0\nRisk Level: LOW\nMax Loss Today: -$125",
            )

    def show_ogl_dialog(self):
        if signal_dialog_available:
            self.show_signal_dialog("OGL")
        else:
            QMessageBox.information(
                self,
                "OGL Monitor",
                "OGL: 585.50\nCurrent SPY: 585.39\nPosition: Below OGL",
            )

    def show_div_dialog(self):
        if signal_dialog_available:
            self.show_signal_dialog("DIVERGENCE")
        else:
            QMessageBox.information(
                self,
                "Divergence Monitor",
                "Price/RSI: None\nPrice/MACD: None\nStatus: No Divergence",
            )

    def show_dex_dialog(self):
        if signal_dialog_available:
            self.show_signal_dialog("DEX")
        else:
            QMessageBox.information(
                self, "DEX Monitor", "DEX: $850M\nDelta Neutral: 585\nFlow: Bullish"
            )

    def show_swan_dialog(self):
        if signal_dialog_available:
            self.show_signal_dialog("BLACK SWAN")
        else:
            QMessageBox.information(
                self,
                "BLACK SWAN Monitor",
                "SWAN Score: 1.85\nRisk Level: LOW\nTail Risk: Minimal",
            )

    def show_hmm_dialog(self):
        if hmm_dialog_available and HMMMonitorDialog:
            self.close_current_dialog()
            self.current_dialog = HMMMonitorDialog(self)
            self.current_dialog.show()
        elif signal_dialog_available:
            self.show_signal_dialog("HMM REGIME")
        else:
            QMessageBox.information(
                self,
                "HMM Regime Detector",
                "Current Regime: NORMAL\nProbability: 0.75\nTransition Risk: LOW\n\n"
                "Regime History:\n- Low Vol: 45%\n- Normal: 40%\n- High Vol: 15%",
            )

    def show_skew_dialog(self):
        if skew_dialog_available and SkewMonitorDialog:
            self.close_current_dialog()
            self.current_dialog = SkewMonitorDialog(self)
            self.current_dialog.show()
        elif signal_dialog_available:
            self.show_signal_dialog("SKEW")
        else:
            QMessageBox.information(
                self,
                "SKEW Monitor",
                "CBOE SKEW Index: 125.5\nStatus: NORMAL\nTail Risk: Moderate\n\n"
                "Strategy Impact:\n- Puts: Fairly priced\n- Calls: Normal premium\n- Recommended: Iron Condors",
            )


class MarketSymbolWidget(QWidget):
    """Widget for displaying a single market symbol"""

    def __init__(self, symbol: str, category: str):
        super().__init__()
        self.symbol = symbol
        self.category = category
        self.setup_ui()

        if symbol in SYMBOL_DESCRIPTIONS:
            self.setToolTip(SYMBOL_DESCRIPTIONS[symbol])

    def setup_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 2, 5, 2)

        self.symbol_label = QLabel(self.symbol)
        self.symbol_label.setStyleSheet(f"color: {COLORS['text']};")
        self.symbol_label.setFixedWidth(60)

        self.price_label = QLabel("---.--")
        self.price_label.setStyleSheet(f"color: {COLORS['text']};")
        self.price_label.setFixedWidth(70)
        self.price_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.change_label = QLabel("+0.00")
        self.change_label.setFixedWidth(55)
        self.change_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.pct_label = QLabel("0.00%")
        self.pct_label.setFixedWidth(55)
        self.pct_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        layout.addWidget(self.symbol_label)
        layout.addWidget(self.price_label)
        layout.addWidget(self.change_label)
        layout.addWidget(self.pct_label)

        self.setLayout(layout)

    def update_data(self, data):
        """Update display with new data"""
        if isinstance(data, dict):
            last = data.get("last", 0.0)
            change = data.get("change", 0.0)
            change_pct = data.get("change_pct", 0.0)
        else:
            last = data.last
            change = data.change
            change_pct = data.change_pct

        if self.symbol in ["GEX", "DEX", "OGL", "DIX", "SWAN"]:
            self._update_custom_indicator(last, change, change_pct)
        else:
            self._update_standard_symbol(last, change, change_pct)

    def _update_standard_symbol(self, last, change, change_pct):
        """Update standard market symbols"""
        if self.symbol.startswith("$"):
            if self.symbol == "$TICK":
                self.price_label.setText(f"{last:+.0f}")
            else:
                self.price_label.setText(f"{last:.2f}")
        elif self.symbol in ["SPX", "/ES"]:
            self.price_label.setText(f"{last:.2f}")
        else:
            self.price_label.setText(f"{last:.2f}")

        color = COLORS["positive"] if change >= 0 else COLORS["negative"]
        sign = "+" if change >= 0 else ""

        self.change_label.setText(f"{sign}{change:.2f}")
        self.change_label.setStyleSheet(f"color: {color};")

        self.pct_label.setText(f"{sign}{change_pct:.2f}%")
        self.pct_label.setStyleSheet(f"color: {color};")

    def _update_custom_indicator(self, last, change, change_pct):
        """Update custom indicators with special formatting"""
        color = COLORS["neutral"]  # Default color
        if self.symbol == "GEX":
            value_b = last / 1_000_000_000
            self.price_label.setText(f"{value_b:.1f}B")
            color = COLORS["positive"] if last > 0 else COLORS["negative"]
        elif self.symbol == "DEX":
            value_m = last / 1_000_000
            self.price_label.setText(f"{value_m:.0f}M")
            color = COLORS["positive"] if change >= 0 else COLORS["negative"]
        elif self.symbol == "OGL":
            self.price_label.setText(f"{last:.2f}")
            color = COLORS["warning"]
        elif self.symbol == "DIX":
            self.price_label.setText(f"{last:.1f}%")
            if last > 45:
                color = COLORS["positive"]
            elif last < 40:
                color = COLORS["negative"]
            else:
                color = COLORS["neutral"]
        elif self.symbol == "SWAN":
            self.price_label.setText(f"{last:.2f}")
            if last < 1.9:
                color = COLORS["positive"]
            elif last < 2.0:
                color = COLORS["warning"]
            else:
                color = COLORS["negative"]
            self.symbol_label.setText("BSWAN")

        sign = "+" if change >= 0 else ""
        self.change_label.setText(f"{sign}{change:.2f}")
        self.change_label.setStyleSheet(f"color: {color};")
        self.pct_label.setText(f"{sign}{change_pct:.2f}%")
        self.pct_label.setStyleSheet(f"color: {color};")


class GreekBar(QWidget):
    """Custom widget for Greek risk display"""

    def __init__(self, name: str, min_val: float, max_val: float):
        super().__init__()
        self.name = name
        self.min_val = min_val
        self.max_val = max_val
        self.current_val = 0
        self.percentage = 0
        self.status = "NORMAL"
        self.setFixedHeight(22)

    def set_value(self, value: float, status: str = "NORMAL"):
        """Update Greek value and status"""
        self.current_val = value
        self.percentage = abs(value - self.min_val) / (self.max_val - self.min_val)
        self.percentage = min(max(self.percentage, 0), 1)
        self.status = status
        self.update()

    def paintEvent(self, event):
        """Custom paint for the Greek bar"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.fillRect(self.rect(), QColor(COLORS["background"]))

        bar_rect = QRect(110, 6, self.width() - 300, 10)
        painter.fillRect(bar_rect, QColor(COLORS["panel"]))

        if self.percentage < 0.6:
            color = QColor(COLORS["positive"])
        elif self.percentage < 0.8:
            color = QColor(COLORS["warning"])
        else:
            color = QColor(COLORS["negative"])

        fill_width = int(bar_rect.width() * self.percentage)
        fill_rect = QRect(bar_rect.x(), bar_rect.y(), fill_width, bar_rect.height())
        painter.fillRect(fill_rect, color)

        painter.setPen(QPen(QColor(COLORS["border"]), 1))
        painter.drawRect(bar_rect)

        painter.setPen(QColor(COLORS["text"]))
        font = QFont()
        font.setPointSize(10)
        painter.setFont(font)

        text = f"{self.name}: {self.current_val:.2f}"
        painter.drawText(10, 16, text)

        status_rect = QRect(self.width() - 190, 0, 180, 22)
        painter.drawText(
            status_rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
            self.status,
        )


# ==============================================================================
# MAIN DASHBOARD CLASS - WITH GATEWAY CONTROL INTEGRATION
# ==============================================================================
class SpyderTradingDashboard(QMainWindow):
    """Complete dashboard with Gateway Control integration"""

    def __init__(self):
        super().__init__()

        # Initialize logging
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Connection info - FIXED: Start disconnected
        self.connection_info = ConnectionInfo(
            ib_connected=False,
            connection_mode="DISCONNECTED",
            market_data_status="NONE",
            trading_active=False,
            simulation_mode=False,
        )
        self.market_worker = None
        self.market_thread = None

        # Dashboard data
        self.market_data = {}
        self.positions = []
        self.greek_risks = GreekRisk(45.5, -2.3, -156.8, -245.2)
        self.system_logs = []

        # CRITICAL: Add startup banner FIRST to show actual launch time
        startup_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        startup_banner = (
            f"{'=' * 60}\n🚀 SPYDER DASHBOARD STARTED: {startup_time}\n{'=' * 60}"
        )
        self.system_logs.append(startup_banner)

        self.automation_logs = []
        self.account_mode = "PAPER"
        self.ib_connected = False  # FIXED: Start disconnected
        self.ib_client = None
        self.trading_active = False
        self.auto_connect_attempts = 0

        # Risk parameters
        self.current_risk_params = None
        self.risk_monitoring_active = False

        # Widget storage
        self.symbol_widgets = {}

        # Prometheus metrics attributes
        self.system_components = {}
        self.client_indicators = {}
        self.system_stats = {}
        self.prometheus_timer = None

        # Real data integration attributes
        self.real_data_active = False
        self.data_file = Path.home() / "Projects/Spyder/market_data/live_data.json"
        self._real_data_timer = None
        self._check_timer = None
        self._error_count = 0

        # NEW: Gateway control integration
        self.gateway_dock = None
        self.gateway_panel = None
        self.client_manager = None
        self.gateway_control_enabled = False
        self.gateway_control_btn = None

        # Initialize UI elements that will be created in setup methods
        self.connection_status_label = None
        self.ib_status_container = None
        self.ib_connection_dot = None
        self.ib_connection_label = None
        self.heartbeat_container = None
        self.heartbeat_icon = None
        self.data_status_container = None
        self.data_status_dot = None
        self.data_status_label = None
        self.simulation_toggle = None
        self.datetime_label = None
        self.dji_value = None
        self.dji_change = None
        self.spx_value = None
        self.spx_change = None
        self.ndx_value = None
        self.ndx_change = None
        self.positions_table = None
        self.system_log = None
        self.signal_panel = None
        self.start_btn = None
        self.stop_btn = None
        self.emergency_btn = None
        self.risk_params_btn = None
        self.settled_value = None
        self.realized_value = None
        self.buying_value = None
        self.unrealized_value = None
        self.pnl_table = None
        self.greek_bars = None
        self.auto_log = None
        self.chart_widget = None
        self.figure = None
        self.canvas = None
        self.internal_module_indicators = {}
        self.datetime_timer = None
        self.automation_timer = None
        self.greek_timer = None
        self.chart_timer = None
        self.gateway_polling_timer = None
        self.automation_activity_count = 0
        self._last_gateway_search_log = ""

        # Try to connect to real Prometheus collector if available
        if prometheus_available:
            self.get_client_status = get_client_status
            self.get_system_metrics = get_system_metrics
        else:
            # Use simulation functions
            self.get_client_status = None
            self.get_system_metrics = None

        # Initialize UI
        self.setup_ui()
        self.setup_timers()
        self.load_test_data()
        self.load_default_risk_parameters()

        # Start market worker with fixed connection detection
        self.start_market_worker()

        # Apply white tooltip styling
        self.setup_white_tooltips()

        # Log the actual dashboard initialization time
        init_time = datetime.now().strftime("%H:%M:%S")
        self.add_system_log(f"🚀 Dashboard initialized at {init_time}")

        # Real data integration (after UI is ready)
        QTimer.singleShot(1000, self.apply_proven_real_data_pattern)

        self.logger.info(
            "Enhanced Dashboard initialized with Gateway Control integration"
        )

    # NOTE: All existing methods from the original file continue here...
    # I'll continue with the key methods that need updates or are new

    def create_unified_prometheus_metrics(self) -> QWidget:
        """Create the unified Prometheus Metrics table (8 clients in 4x2 grid + 2 empty rows) - UPDATED"""
        container = QWidget()
        container.setStyleSheet(
            f"""
            QWidget {{
                background-color: {COLORS["panel"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 5px;
            }}
        """
        )
        container.setFixedHeight(200)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(2)

        # Title with Gateway button
        title_layout = QHBoxLayout()
        
        title_label = QLabel("PROMETHEUS METRICS MONITOR")
        title_label.setStyleSheet(
            f"""
            color: {COLORS["text"]};
            font-size: 14px;
            font-weight: normal;
            padding-bottom: 1px;
        """
        )
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        
        # Gateway Control Button
        self.gateway_control_btn = QPushButton("🔧")
        self.gateway_control_btn.setFixedSize(30, 30)
        self.gateway_control_btn.setToolTip("Show/Hide Gateway Control Panel")
        self.gateway_control_btn.clicked.connect(self.toggle_gateway_control)
        title_layout.addWidget(self.gateway_control_btn)
        
        main_layout.addLayout(title_layout)
        main_layout.addSpacing(8)

        # Create the 6x4 grid (5 data rows + 1 header row)
        grid = QGridLayout()
        grid.setSpacing(2)
        grid.setContentsMargins(0, 0, 0, 0)

        # Column headers
        headers = [
            "SYSTEM HEALTH",
            "IB CLIENTS 1-4",
            "IB CLIENTS 5-8",
            "INTERNAL MODULES",
        ]
        for col, header in enumerate(headers):
            header_label = QLabel(header)
            header_label.setStyleSheet(
                f"""
                color: {COLORS["cyan"]};
                font-size: 13px;
                font-weight: normal;
                padding: 2px;
                border-bottom: 1px solid {COLORS["border"]};
            """
            )
            header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(header_label, 0, col)

        # System Components (Column 1)
        components = [
            ("RISK MANAGER", "●"),
            ("MARKET DATA", "●"),
            ("STRATEGY ENGINE", "●"),
            ("ML MODELS", "●"),
            ("DATABASE", "●"),
        ]

        for row, (name, status) in enumerate(components, start=1):
            component_widget = QWidget()
            component_layout = QHBoxLayout()
            component_layout.setContentsMargins(5, 1, 5, 1)
            component_layout.setSpacing(3)

            indicator = QLabel(status)
            indicator.setStyleSheet(
                "color: " + COLORS["positive"] + f"; font-size: 14px;"
            )
            component_layout.addWidget(indicator)

            label = QLabel(name)
            label.setStyleSheet("color: " + COLORS["text"] + "; font-size: 14px;")
            component_layout.addWidget(label)
            component_layout.addStretch()

            component_widget.setLayout(component_layout)
            self.system_components[name] = indicator
            grid.addWidget(component_widget, row, 0)

        # IB Clients 1-4 (Column 2) - UPDATED TO 4 CLIENTS + 1 EMPTY
        client_1_4_types = ["Orders", "Admin", "Core", "Options"]
        for row in range(1, 6):  # 5 rows total
            if row <= 4:  # First 4 rows are clients
                client_widget = QWidget()
                client_layout = QHBoxLayout()
                client_layout.setContentsMargins(5, 1, 5, 1)
                client_layout.setSpacing(3)

                indicator = QLabel("●")
                indicator.setStyleSheet(
                    "color: " + COLORS["neutral"] + f"; font-size: 14px;"
                )
                indicator.setCursor(Qt.CursorShape.PointingHandCursor)
                indicator.setToolTip(f"Click to connect Client {row}")
                client_layout.addWidget(indicator)

                label = QLabel(f"CLIENT {row}: {client_1_4_types[row - 1]}")
                label.setStyleSheet("color: " + COLORS["text"] + "; font-size: 14px;")
                client_layout.addWidget(label)
                client_layout.addStretch()

                client_widget.setLayout(client_layout)
                
                # Store indicator for status updates
                self.client_indicators[f"CLIENT {row}"] = indicator
                
                # Make clickable for reconnection
                indicator.mousePressEvent = lambda e, cid=row: self.reconnect_client(cid)
                
                grid.addWidget(client_widget, row, 1)
            else:
                # Row 5 is empty
                empty_widget = QWidget()
                grid.addWidget(empty_widget, row, 1)

        # IB Clients 5-8 (Column 3) - UPDATED TO 4 CLIENTS + 1 EMPTY
        client_5_8_types = ["Volatility", "Major ETFs", "Extended", "International"]
        for row in range(1, 6):  # 5 rows total
            if row <= 4:  # First 4 rows are clients
                client_num = row + 4  # Client 5, 6, 7, 8
                client_widget = QWidget()
                client_layout = QHBoxLayout()
                client_layout.setContentsMargins(5, 1, 5, 1)
                client_layout.setSpacing(3)

                indicator = QLabel("●")
                indicator.setStyleSheet(
                    "color: " + COLORS["neutral"] + f"; font-size: 14px;"
                )
                indicator.setCursor(Qt.CursorShape.PointingHandCursor)
                indicator.setToolTip(f"Click to connect Client {client_num}")
                client_layout.addWidget(indicator)

                label = QLabel(f"CLIENT {client_num}: {client_5_8_types[row - 1]}")
                label.setStyleSheet("color: " + COLORS["text"] + "; font-size: 14px;")
                client_layout.addWidget(label)
                client_layout.addStretch()

                client_widget.setLayout(client_layout)
                
                # Store indicator for status updates
                self.client_indicators[f"CLIENT {client_num}"] = indicator
                
                # Make clickable for reconnection
                indicator.mousePressEvent = lambda e, cid=client_num: self.reconnect_client(cid)
                
                grid.addWidget(client_widget, row, 2)
            else:
                # Row 5 is empty
                empty_widget = QWidget()
                grid.addWidget(empty_widget, row, 2)

        # Internal Modules (Column 4) - UNCHANGED
        internal_modules = [
            ("Custom Metrics", "custom_metrics"),
            ("Risk Calculator", "risk_calc"),
            ("ML Engine", "ml_engine"),
            ("Options Analyzer", "options"),
            ("Performance", "performance"),
        ]

        for row, (module_name, module_key) in enumerate(internal_modules, start=1):
            module_widget = QWidget()
            module_layout = QHBoxLayout()
            module_layout.setContentsMargins(5, 1, 5, 1)
            module_layout.setSpacing(3)

            indicator = QLabel("●")
            if module_key == "custom_metrics":
                indicator.setStyleSheet(
                    "color: " + COLORS["warning"] + f"; font-size: 14px;"
                )
            else:
                indicator.setStyleSheet(
                    "color: " + COLORS["positive"] + f"; font-size: 14px;"
                )
            module_layout.addWidget(indicator)

            label = QLabel(module_name)
            label.setStyleSheet("color: " + COLORS["text"] + "; font-size: 14px;")
            module_layout.addWidget(label)
            module_layout.addStretch()

            module_widget.setLayout(module_layout)
            if not hasattr(self, "internal_module_indicators"):
                self.internal_module_indicators = {}
            self.internal_module_indicators[module_key] = indicator
            grid.addWidget(module_widget, row, 3)

        # Set equal column stretch
        for col in range(4):
            grid.setColumnStretch(col, 1)

        # Set row heights
        for row in range(1, 6):
            grid.setRowMinimumHeight(row, 24)

        main_layout.addLayout(grid)
        main_layout.addStretch()

        container.setLayout(main_layout)
        return container

    # ==========================================================================
    # GATEWAY CONTROL INTEGRATION (NEW METHODS)
    # ==========================================================================

    def toggle_gateway_control(self):
        """Toggle Gateway Control Panel visibility"""
        if not gateway_panel_available:
            QMessageBox.information(
                self,
                "Gateway Control",
                "Gateway Control Panel is not available.\n\n"
                "This feature requires SpyderG14_GatewayControlPanel module."
            )
            return
        
        if self.gateway_dock is None:
            # Create dock widget
            self.gateway_dock = create_gateway_dock_widget(self)
            self.gateway_panel = self.gateway_dock.widget()
            
            # Connect signals
            self.gateway_panel.clients_connected.connect(self.on_gateway_clients_connected)
            
            # Add to main window
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.gateway_dock)
            
            self.add_system_log("🔧 Gateway Control Panel opened")
        else:
            # Toggle visibility
            if self.gateway_dock.isVisible():
                self.gateway_dock.hide()
                self.add_system_log("🔧 Gateway Control Panel hidden")
            else:
                self.gateway_dock.show()
                self.add_system_log("🔧 Gateway Control Panel shown")

    @Slot(int)
    def on_gateway_clients_connected(self, count: int):
        """Handle clients connected signal from Gateway panel"""
        self.add_system_log(f"✅ {count}/8 clients connected via Gateway panel")
        
        # Update client indicators in Prometheus table
        if self.gateway_panel and self.gateway_panel.client_thread:
            manager = self.gateway_panel.client_thread.manager
            if manager:
                for client_id in range(1, 9):
                    status = manager.get_client_status(client_id)
                    if status:
                        self.update_client_indicator(client_id, status.status)

    def update_client_indicator(self, client_id: int, status):
        """Update client indicator in Prometheus table"""
        indicator_key = f"CLIENT {client_id}"
        
        if indicator_key in self.client_indicators:
            indicator = self.client_indicators[indicator_key]
            
            if status == ClientStatus.CONNECTED:
                indicator.setStyleSheet(f"color: {COLORS['positive']}; font-size: 14px;")
                indicator.setToolTip(f"Client {client_id}: Connected")
            elif status == ClientStatus.CONNECTING:
                indicator.setStyleSheet(f"color: {COLORS['automation_active']}; font-size: 14px;")
                indicator.setToolTip(f"Client {client_id}: Connecting...")
            elif status == ClientStatus.ERROR:
                indicator.setStyleSheet(f"color: {COLORS['negative']}; font-size: 14px;")
                indicator.setToolTip(f"Client {client_id}: Error")
            else:  # DISCONNECTED
                indicator.setStyleSheet(f"color: {COLORS['neutral']}; font-size: 14px;")
                indicator.setToolTip(f"Client {client_id}: Click to connect")

    def reconnect_client(self, client_id: int):
        """Reconnect a specific client when indicator is clicked"""
        if not gateway_panel_available or not self.gateway_panel:
            self.add_system_log(f"⚠️ Gateway panel not available to reconnect Client {client_id}")
            return
        
        if not self.gateway_panel.gateway_running:
            QMessageBox.warning(
                self,
                "Gateway Not Running",
                "Please start Gateway first before connecting clients."
            )
            return
        
        self.add_system_log(f"🔄 Reconnecting Client {client_id}...")
        
        # Use the client manager from gateway panel
        if self.gateway_panel.client_thread and self.gateway_panel.client_thread.manager:
            manager = self.gateway_panel.client_thread.manager
            
            # Update indicator to connecting
            self.update_client_indicator(client_id, ClientStatus.CONNECTING)
            
            # Reconnect in background
            import threading
            def reconnect_thread():
                success = manager.reconnect_client(client_id)
                if success:
                    self.add_system_log(f"✅ Client {client_id} reconnected")
                else:
                    self.add_system_log(f"❌ Client {client_id} reconnection failed")
            
            thread = threading.Thread(target=reconnect_thread, daemon=True)
            thread.start()

    def closeEvent(self, event):
        """Enhanced close event handler with Gateway control cleanup"""
        try:
            # NEW: Cleanup Gateway control
            if self.gateway_panel:
                if self.gateway_panel.client_thread:
                    self.gateway_panel.client_thread.stop()
                    self.gateway_panel.client_thread.wait(2000)
                
                if self.gateway_panel.gateway_thread:
                    self.gateway_panel.gateway_thread.stop()
                    self.gateway_panel.gateway_thread.wait(2000)
            
            # Stop real data timer if active
            if hasattr(self, "_real_data_timer") and self._real_data_timer:
                self._real_data_timer.stop()

            # Stop monitoring timer if active
            if hasattr(self, "_check_timer") and self._check_timer:
                self._check_timer.stop()

            # Stop market worker and heartbeat monitoring
            if self.market_worker and hasattr(self.market_worker, "stop"):
                self.market_worker.stop()

            # Stop market thread
            if self.market_thread and self.market_thread.isRunning():
                self.market_thread.quit()
                self.market_thread.wait(3000)

            # Stop all timers
            if hasattr(self, "datetime_timer"):
                self.datetime_timer.stop()
            if hasattr(self, "automation_timer"):
                self.automation_timer.stop()
            if hasattr(self, "greek_timer"):
                self.greek_timer.stop()
            if hasattr(self, "chart_timer"):
                self.chart_timer.stop()
            if hasattr(self, "prometheus_timer"):
                self.prometheus_timer.stop()

            # Log shutdown
            self.add_system_log("🔥 Enhanced Trading Dashboard shutting down...")
            self.add_automation_log("Dashboard session ended with Gateway Control")

            # Accept close event
            event.accept()

        except Exception as e:
            print(f"Error during enhanced dashboard close: {e}")
            event.accept()


# NOTE: Due to length constraints, I'm providing the critical new/updated methods.
# ALL OTHER EXISTING METHODS from your original file remain unchanged and should be preserved.
# This includes:
# - setup_ui()
# - create_toolbar()
# - create_left_panel()
# - create_center_panel()
# - create_right_panel()
# - create_chart()
# - create_positions_table()
# - create_pnl_table()
# - All signal handlers
# - All data update methods
# - All helper methods
# - main() function

# ==============================================================================
# MAIN EXECUTION - FOR STANDALONE TESTING
# ==============================================================================

def main():
    """Main function for standalone testing"""
    print("=" * 70)
    print("🔥 SPYDER G05 - WITH GATEWAY CONTROL INTEGRATION")
    print("=" * 70)
    print("🔧 NEW: Gateway Control Panel (click 🔧 button)")
    print("🔗 NEW: 8-client connection management")
    print("🎯 NEW: Clickable client indicators for reconnection")
    print("📊 UPDATED: Prometheus Metrics (8 clients in 4+4 layout)")
    print("💚 PRESERVED: All existing dashboard features")
    print("=" * 70)

    # Create Qt application
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # CRITICAL: Set desktop file name for Wayland/GNOME integration
    app.setDesktopFileName("spyder-trading-system")
    app.setApplicationName("spyder-trading-system")
    app.setOrganizationName("Spyder Trading System")

    try:
        # Create dashboard with Gateway Control
        print("🔧 Initializing dashboard with Gateway Control...")
        dashboard = SpyderTradingDashboard()

        # Show dashboard
        dashboard.show()

        print("\n🎯 NEW FEATURES:")
        print("   • Click 🔧 button in Prometheus Metrics to open Gateway Control")
        print("   • Gateway Control Panel: Start Gateway + Connect 8 clients")
        print("   • Click individual client indicators (●) to reconnect")
        print("   • Client colors: Gray=Disconnected, Cyan=Connecting, Green=Connected, Red=Error")

        print("\n🔥 Enhanced Trading Dashboard is ready!")
        print("   All existing features preserved + Gateway automation added\n")

        # Run application
        return app.exec()

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())