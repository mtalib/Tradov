#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderG05_TradingDashboard.py
Group: G (GUI/User Interface)
Purpose: Complete Trading Dashboard with Real Data Integration & Unified Prometheus Metrics
Author: Mohamed Talib
Date Created: 2025-07-05
Last Updated: 2025-08-18 Time: 22:30:00

Module Description:
    Enhanced trading dashboard with integrated real market data detection and switching.
    Automatically detects live IB Gateway data from JSON file and switches from simulation
    to real-time market data seamlessly. Features unified Prometheus Metrics monitoring,
    comprehensive signal popups, and robust error handling with graceful fallbacks.

FEATURES:
    • Real-time IB Gateway data integration with automatic detection
    • Simulation fallback when real data unavailable
    • Unified Prometheus Metrics table (IB Clients 1-10 + Internal Modules)
    • Advanced Signal Monitor with popup dialogs (12 signals including HMM/SKEW)
    • Market hours awareness and connection health monitoring
    • Custom metrics integration (GEX/DEX/OGL/DIX/SWAN)
    • Professional dark theme with traffic light indicators

REAL DATA INTEGRATION:
    • Data Source: ~/Projects/Spyder/market_data/live_data.json
    • Auto-detection every 5 seconds when in simulation mode
    • Post-initialization patching for seamless switching
    • Status indicators: "LIVE - REAL" and "IB CONNECTED - REAL DATA"
    • Graceful error handling with simulation fallback
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
from PyQt6.QtWidgets import (
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
from PyQt6.QtCore import (
    Qt,
    QTimer,
    pyqtSignal,
    QThread,
    pyqtSlot,
    QSize,
    QRect,
    QPoint,
    QObject,
    QMutex,
    QMutexLocker,
)
from PyQt6.QtGui import (
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
# IB_ASYNC IMPORTS (NO IBAPI!)
# ==============================================================================
from ib_async import IB, Stock, Index, Future, Contract, Ticker

print("✅ Using ib_async for IB Gateway connection")

# ==============================================================================
# CUSTOM METRICS INTEGRATION IMPORTS
# ==============================================================================
try:
    from SpyderG10_CustomMetricsIntegration import (
        CustomMetricsIntegration,
        DashboardMetricsUpdater,
    )
    from SpyderS_Signals.SpyderS07_CustomMetricsOrchestrator import (
        CustomMetricsOrchestrator,
        get_metrics_client,
    )
    CUSTOM_METRICS_AVAILABLE = True
except ImportError:
    CUSTOM_METRICS_AVAILABLE = False
    print("⚠️ Custom Metrics modules not available - Client 10 will run in simulation mode")

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
CLIENT_ID = 123

# Market hours (Eastern Time)
MARKET_OPEN_TIME = dt_time(4, 0)  # 4:00 AM ET
MARKET_CLOSE_TIME = dt_time(16, 30)  # 4:30 PM ET

# Phased symbol loading to prevent overload
PHASE_1_SYMBOLS = ["SPY", "VIX", "QQQ"]
PHASE_2_SYMBOLS = ["IWM", "DIA", "SPX"]
PHASE_3_SYMBOLS = ["TLT", "GLD"]
SUBSCRIPTION_DELAY_MS = 1000

# COMPLETE MARKET SYMBOLS FROM T09
MARKET_SYMBOLS = {
    "S&P CORE": ["SPY", "SPX", "/ES"],
    "VOLATILITY": ["VIX", "VIX9D", "VXV", "VXMT", "VVIX", "UVXY"],
    "MARKET INTERNALS": ["$TICK", "$TRIN", "$ADD", "CPC", "PCALL", "SKEW"],
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
    """Check if IB Gateway is running"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        paper_result = sock.connect_ex(("127.0.0.1", 4002))
        sock.close()

        if paper_result == 0:
            return True, "PAPER (Port 4002)"

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        live_result = sock.connect_ex(("127.0.0.1", 4001))
        sock.close()

        if live_result == 0:
            return True, "LIVE (Port 4001)"

        return False, "No IB Gateway detected"

    except Exception as e:
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

# ==============================================================================
# IB_ASYNC WORKER (using only ib_async, no IBAPI)
# ==============================================================================
class IBAsyncWorker(QObject):
    """ib_async-based worker with heartbeat for reliable IB Gateway connection"""

    # Signals for thread-safe communication
    connected = pyqtSignal(bool)
    disconnected = pyqtSignal()
    market_data_ready = pyqtSignal()
    error_occurred = pyqtSignal(int, int, str)
    price_update = pyqtSignal(str, float, float, float)
    heartbeat_status = pyqtSignal(bool, str)

    def __init__(self):
        super().__init__()
        self.ib = None
        self.tickers = {}
        self.contracts = {}
        self.subscribed_symbols = set()
        self.data_mutex = QMutex()
        self._connected = False
        self.heartbeat_count = 0
        self.last_heartbeat_time = None

        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._emit_price_updates)
        self.update_timer.setInterval(500)

        self.heartbeat_timer = QTimer()
        self.heartbeat_timer.timeout.connect(self._send_heartbeat)

        print("ib_async Worker with market hours awareness initialized")

    def connect_to_ib(self, host="127.0.0.1", port=4002, client_id=CLIENT_ID):
        """Connect to IB Gateway"""
        try:
            print(f"Connecting to {host}:{port} with client ID {client_id}")
            self.ib = IB()
            self.ib.connect(host, port, clientId=client_id, timeout=10)

            if self.ib.isConnected():
                print("Connected to IB Gateway")
                self._connected = True
                self.connected.emit(True)
                self.update_timer.start()

                if is_market_hours():
                    self._configure_heartbeat()
                    self.heartbeat_timer.start()
                else:
                    print("💤 After market hours - heartbeat disabled")

                QTimer.singleShot(1000, self.market_data_ready.emit)
                return True
            return False
        except Exception as e:
            print(f"Connection error: {e}")
            self.error_occurred.emit(0, 0, str(e))
            return False

    def _configure_heartbeat(self):
        """Configure heartbeat based on market hours"""
        if not is_market_hours():
            self.heartbeat_timer.stop()
            print("💤 Market closed - heartbeat stopped")
            return

        current_time = datetime.now()
        market_open = current_time.replace(hour=9, minute=30, second=0)
        market_close = current_time.replace(hour=16, minute=0, second=0)

        if market_open <= current_time <= market_close:
            self.heartbeat_timer.setInterval(300000)
            print("💓 Heartbeat configured for regular trading hours (5 min intervals)")
        else:
            self.heartbeat_timer.setInterval(60000)
            print("💓 Heartbeat configured for extended hours (60 sec intervals)")

    def _send_heartbeat(self):
        """Send heartbeat to keep connection alive"""
        if not self._connected or not self.ib:
            return

        if not is_market_hours():
            self.heartbeat_timer.stop()
            print("💤 Market closed - stopping heartbeat")
            return

        try:
            server_time = self.ib.reqCurrentTime()
            self.heartbeat_count += 1
            self.last_heartbeat_time = datetime.now()

            local_time = datetime.now().strftime("%H:%M:%S")
            server_time_str = server_time.strftime("%H:%M:%S %Z")

            message = f"Heartbeat #{self.heartbeat_count} | Local: {local_time} | Server: {server_time_str}"
            self.heartbeat_status.emit(True, message)
            self._configure_heartbeat()

        except Exception as e:
            print(f"❌ Heartbeat failed: {e}")
            self.heartbeat_status.emit(False, f"Heartbeat failed: {e}")

            if not self.ib.isConnected():
                self._connected = False
                self.disconnected.emit()

    def disconnect(self):
        """Disconnect from IB Gateway"""
        if self.ib and self.ib.isConnected():
            with QMutexLocker(self.data_mutex):
                for ticker in self.tickers.values():
                    try:
                        self.ib.cancelMktData(ticker)
                    except:
                        pass
                self.tickers.clear()
                self.contracts.clear()
                self.subscribed_symbols.clear()

            self.update_timer.stop()
            self.heartbeat_timer.stop()
            self.ib.disconnect()
            self.ib = None
            self._connected = False
            self.heartbeat_count = 0
            self.disconnected.emit()

    def subscribe_symbol(self, symbol):
        """Subscribe to market data for a symbol"""
        with QMutexLocker(self.data_mutex):
            if symbol in self.subscribed_symbols or not self._connected:
                return
            self.subscribed_symbols.add(symbol)

        try:
            contract = self._create_contract(symbol)
            if not contract:
                return

            print(f"Subscribing to {symbol}")
            self.ib.qualifyContracts(contract)
            ticker = self.ib.reqMktData(contract)

            with QMutexLocker(self.data_mutex):
                self.contracts[symbol] = contract
                self.tickers[symbol] = ticker

        except Exception as e:
            print(f"Error subscribing to {symbol}: {e}")
            self.error_occurred.emit(0, 0, f"Subscribe error: {e}")

    def _create_contract(self, symbol):
        """Create IB contract based on symbol"""
        try:
            if symbol in ["SPY", "DIA", "QQQ", "IWM", "TLT", "GLD", "LQD", "UVXY"]:
                return Stock(symbol, "SMART", "USD")
            elif symbol in ["SPX", "VIX", "VIX9D", "VXV", "VXMT", "VVIX"]:
                return Index(symbol, "CBOE")
            elif symbol == "/ES":
                return Future("ES", "CME")
            elif symbol == "DXY":
                return Index("DXY", "ICE")
            elif symbol in ["CPC", "PCALL", "SKEW"]:
                return Index(symbol, "CBOE")
            elif symbol in ["GEX", "DEX", "OGL", "DIX", "SWAN", "$TICK", "$TRIN", "$ADD"]:
                return None
            else:
                return None
        except Exception as e:
            print(f"Error creating contract for {symbol}: {e}")
            return None

    def _emit_price_updates(self):
        """Emit price updates for all subscribed symbols"""
        with QMutexLocker(self.data_mutex):
            for symbol, ticker in self.tickers.items():
                last = ticker.last if ticker.last and ticker.last > 0 else 0
                bid = ticker.bid if ticker.bid and ticker.bid > 0 else 0
                ask = ticker.ask if ticker.ask and ticker.ask > 0 else 0

                if last > 0 or bid > 0 or ask > 0:
                    if last == 0 and bid > 0 and ask > 0:
                        last = (bid + ask) / 2

                    self.price_update.emit(symbol, last, bid, ask)

# ==============================================================================
# THREAD-SAFE MARKET DATA WORKER (FIXED)
# ==============================================================================
class ThreadSafeMarketDataWorker(QObject):
    """Thread-safe market data worker using ib_async with market hours awareness"""

    data_updated = pyqtSignal(dict)
    connection_status_changed = pyqtSignal(bool, str)
    market_data_status_changed = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    heartbeat_received = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.logger = SpyderLogger.get_logger(__name__)
        self.ib_worker = None
        self.ib_connected = True
        self.market_data = {}
        self.data_mutex = QMutex()
        self.client_id = CLIENT_ID
        self.market_hours = is_market_hours()

        self.symbols_queue = []
        self.current_symbol_index = 0
        self.subscription_timer = QTimer()
        self.subscription_timer.timeout.connect(self._subscribe_next_symbol)

        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._emit_data)
        self.update_timer.start(2000)

        self.market_hours_timer = QTimer()
        self.market_hours_timer.timeout.connect(self._check_market_hours)
        self.market_hours_timer.start(60000)

        self.last_data_update = {}
        self.stale_data_timer = QTimer()
        self.stale_data_timer.timeout.connect(self._check_data_freshness)
        self.stale_data_timer.start(30000)

        self._init_simulation_data()

        print(f"🔧 Market Data Worker initialized - Market {'OPEN' if self.market_hours else 'CLOSED'}")

    def _init_simulation_data(self):
        """Initialize simulation data with all symbols from T09"""
        base_prices = {
            "SPY": 585.25, "SPX": 5850.75, "/ES": 5852.50,
            "VIX": 15.32, "VIX9D": 14.8, "VXV": 16.2, "VXMT": 17.5, "VVIX": 82.45, "UVXY": 22.18,
            "$TICK": 234, "$TRIN": 0.85, "$ADD": 1245, "CPC": 0.95, "PCALL": 0.88, "SKEW": 125.5,
            "DIA": 425.33, "QQQ": 485.92, "IWM": 225.18,
            "TLT": 92.45, "LQD": 105.32,
            "DXY": 103.25, "GLD": 195.67,
            "GEX": -2500000000, "DEX": 850000000, "OGL": 585.50, "DIX": 42.5, "SWAN": 1.85,
        }

        with QMutexLocker(self.data_mutex):
            for symbol, price in base_prices.items():
                self.market_data[symbol] = {
                    "symbol": symbol, "last": price, "change": 0, "change_pct": 0, "timestamp": datetime.now(),
                }
                self.last_data_update[symbol] = datetime.now()

    def _subscribe_next_symbol(self):
        """Subscribe to next symbol in queue (FIXED METHOD)"""
        if not self.symbols_queue or self.current_symbol_index >= len(self.symbols_queue):
            self.subscription_timer.stop()
            return

        symbol = self.symbols_queue[self.current_symbol_index]
        if self.ib_worker:
            self.ib_worker.subscribe_symbol(symbol)

        self.current_symbol_index += 1

        if self.current_symbol_index >= len(self.symbols_queue):
            self.subscription_timer.stop()
            print(f"✅ Subscribed to all {len(self.symbols_queue)} symbols")

    def _check_market_hours(self):
        """Check if market hours status has changed"""
        current_market_hours = is_market_hours()

        if current_market_hours != self.market_hours:
            self.market_hours = current_market_hours
            print(f"📊 Market hours changed: {'OPEN' if self.market_hours else 'CLOSED'}")

            if not self.market_hours:
                if self.ib_connected:
                    self.market_data_status_changed.emit("NONE")

    @pyqtSlot()
    def start(self):
        """Start the worker"""
        print("🚀 Starting Thread-Safe Market Data Worker...")
        self.connection_status_changed.emit(True, "IB CONNECTED")
        self.market_data_status_changed.emit("LIVE")

    def _check_data_freshness(self):
        """Check if data is stale and needs refresh - with warning suppression"""
        if not is_market_hours():
            return

        if not hasattr(self, "stale_warning_count"):
            self.stale_warning_count = 0
            self.stale_warning_shown = False

        current_time = datetime.now()
        stale_threshold = timedelta(seconds=30)
        stale_symbols = []

        with QMutexLocker(self.data_mutex):
            for symbol, last_update in self.last_data_update.items():
                if current_time - last_update > stale_threshold:
                    stale_symbols.append(symbol)
                    self.last_data_update[symbol] = current_time

        if stale_symbols:
            if self.stale_warning_count < 5:
                for symbol in stale_symbols[:5]:
                    self.logger.debug(f"⚠️ Stale data detected for {symbol}")
                self.stale_warning_count += len(stale_symbols)
            elif not self.stale_warning_shown:
                self.logger.debug(f"⚠️ Stale data detected for {len(stale_symbols)} symbols (warnings suppressed)")
                self.stale_warning_shown = True
                QTimer.singleShot(60000, self._reset_stale_warnings)

    def _reset_stale_warnings(self):
        """Reset stale warning counters"""
        self.stale_warning_count = 0
        self.stale_warning_shown = False

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

                market_info.update({
                    "last": new_price, "change": change, "change_pct": change_pct, "timestamp": current_time,
                })

            with QMutexLocker(self.data_mutex):
                self.last_data_update[symbol] = current_time

    def force_connect(self):
        """Manual connect"""
        print("🔥 Manual connect requested")
        if not is_market_hours():
            print("📊 Cannot connect - market is closed")
            return False
        self.ib_connected = True
        self.connection_status_changed.emit(True, "IB CONNECTED")
        self.market_data_status_changed.emit("LIVE")
        return True

    def force_disconnect(self):
        """Manual disconnect"""
        print("🔥 Manual disconnect requested")
        if self.ib_worker:
            self.ib_worker.disconnect()
        self.ib_connected = False
        self.connection_status_changed.emit(False, "IB DISCONNECTED")
        self.market_data_status_changed.emit("NONE")

    def stop(self):
        """Stop worker"""
        print("🛑 Stopping worker...")
        if self.ib_worker:
            self.ib_worker.disconnect()
        self.subscription_timer.stop()
        self.update_timer.stop()
        self.stale_data_timer.stop()
        self.market_hours_timer.stop()

# ==============================================================================
# WIDGET CLASSES (keeping existing implementations)
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
        self.setStyleSheet("""
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
        """)
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
    """Updated Signal Monitor Panel with integrated popup dialogs"""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(165)
        self.setMinimumWidth(280)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS['panel']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
            }}
        """)

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
        for button in [self.vix_button, self.ai_button, self.gex_button, self.dix_button,
                      self.rsi_button, self.risk_button, self.ogl_button, self.div_button, self.dex_button]:
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
        if (self.current_dialog and hasattr(self.current_dialog, "isVisible") and self.current_dialog.isVisible()):
            self.current_dialog.close()
            self.current_dialog = None

    def show_signal_dialog(self, signal_type: str):
        """Generic method to show signal dialog with auto-close functionality"""
        self.close_current_dialog()
        self.current_dialog = SignalInfoDialog(signal_type, self)

        # Position the dialog to the right of the signal panel
        parent_pos = self.mapToGlobal(self.rect().topRight())
        self.current_dialog.move(parent_pos.x() + 10, parent_pos.y())

        # Connect the closed signal to clear the reference
        self.current_dialog.closed.connect(lambda: setattr(self, "current_dialog", None))
        self.current_dialog.show()

    # Updated dialog show methods to use the new SignalInfoDialog
    def show_vix_dialog(self):
        """Show VIX Monitor dialog"""
        if SIGNAL_DIALOG_AVAILABLE:
            self.show_signal_dialog("VIX MONITOR")
        else:
            QMessageBox.information(self, "VIX Monitor", "VIX: 15.32\nStatus: Normal\nImplied Move: ±0.96%")

    def show_ai_dialog(self):
        """Show AI Decision dialog"""
        if SIGNAL_DIALOG_AVAILABLE:
            self.show_signal_dialog("AI DECISION")
        else:
            QMessageBox.information(self, "AI Decision", "Current Signal: NEUTRAL\nConfidence: 72%\nNext Decision: 5 min")

    def show_gex_dialog(self):
        """Show GEX dialog"""
        if SIGNAL_DIALOG_AVAILABLE:
            self.show_signal_dialog("GEX")
        else:
            QMessageBox.information(self, "GEX Monitor", "GEX: -$2.5B\nGamma Flip: 590\nRegime: Negative Gamma")

    def show_dix_dialog(self):
        """Show DIX dialog"""
        if SIGNAL_DIALOG_AVAILABLE:
            self.show_signal_dialog("DIX")
        else:
            QMessageBox.information(self, "DIX Monitor", "DIX: 42.5%\nDark Pool: Normal\nSentiment: Neutral")

    def show_rsi_dialog(self):
        """Show RSI Confluence dialog"""
        if SIGNAL_DIALOG_AVAILABLE:
            self.show_signal_dialog("RSI CONFLUENCE")
        else:
            QMessageBox.information(self, "RSI Confluence", "RSI(14): 52\nRSI(5): 48\nStatus: Neutral Range")

    def show_risk_dialog(self):
        """Show Risk Triggers dialog"""
        if SIGNAL_DIALOG_AVAILABLE:
            self.show_signal_dialog("RISK TRIGGERS")
        else:
            QMessageBox.information(self, "Risk Triggers", "Active Triggers: 0\nRisk Level: LOW\nMax Loss Today: -$125")

    def show_ogl_dialog(self):
        """Show OGL dialog"""
        if SIGNAL_DIALOG_AVAILABLE:
            self.show_signal_dialog("OGL")
        else:
            QMessageBox.information(self, "OGL Monitor", "OGL: 585.50\nCurrent SPY: 585.39\nPosition: Below OGL")

    def show_div_dialog(self):
        """Show Divergence dialog"""
        if SIGNAL_DIALOG_AVAILABLE:
            self.show_signal_dialog("DIVERGENCE")
        else:
            QMessageBox.information(self, "Divergence Monitor", "Price/RSI: None\nPrice/MACD: None\nStatus: No Divergence")

    def show_dex_dialog(self):
        """Show DEX dialog"""
        if SIGNAL_DIALOG_AVAILABLE:
            self.show_signal_dialog("DEX")
        else:
            QMessageBox.information(self, "DEX Monitor", "DEX: $850M\nDelta Neutral: 585\nFlow: Bullish")

    def show_swan_dialog(self):
        """Show Black Swan dialog"""
        if SIGNAL_DIALOG_AVAILABLE:
            self.show_signal_dialog("BLACK SWAN")
        else:
            QMessageBox.information(self, "BLACK SWAN Monitor", "SWAN Score: 1.85\nRisk Level: LOW\nTail Risk: Minimal")

    def show_hmm_dialog(self):
        """Show HMM Regime Detector dialog"""
        if HMM_DIALOG_AVAILABLE:
            self.close_current_dialog()
            self.current_dialog = HMMMonitorDialog(self)
            self.current_dialog.show()
        elif SIGNAL_DIALOG_AVAILABLE:
            self.show_signal_dialog("HMM")
        else:
            QMessageBox.information(self, "HMM Regime Detector", 
                "Current Regime: NORMAL\nProbability: 0.75\nTransition Risk: LOW\n\n"
                "Regime History:\n- Low Vol: 45%\n- Normal: 40%\n- High Vol: 15%")

    def show_skew_dialog(self):
        """Show SKEW Monitor dialog"""
        if SKEW_DIALOG_AVAILABLE:
            self.close_current_dialog()
            self.current_dialog = SkewMonitorDialog(self)
            self.current_dialog.show()
        elif SIGNAL_DIALOG_AVAILABLE:
            self.show_signal_dialog("SKEW")
        else:
            QMessageBox.information(self, "SKEW Monitor", 
                "CBOE SKEW Index: 125.5\nStatus: NORMAL\nTail Risk: Moderate\n\n"
                "Strategy Impact:\n- Puts: Fairly priced\n- Calls: Normal premium\n- Recommended: Iron Condors")

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
        painter.drawText(status_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, self.status)

# ==============================================================================
# MAIN DASHBOARD CLASS - WITH REAL DATA INTEGRATION
# ==============================================================================
class SpyderTradingDashboard(QMainWindow):
    """Complete dashboard with real data integration and unified Prometheus metrics"""

    def __init__(self):
        super().__init__()
        global CUSTOM_METRICS_AVAILABLE

        # Initialize logging
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Connection info
        self.connection_info = ConnectionInfo(
            ib_connected=True, connection_mode="PAPER", market_data_status="LIVE", trading_active=False,
        )
        self.market_worker = None
        self.market_thread = None

        # Dashboard data
        self.market_data = {}
        self.positions = []
        self.greek_risks = GreekRisk(45.5, -2.3, -156.8, -245.2)
        self.system_logs = []
        self.automation_logs = []
        self.account_mode = "PAPER"
        self.ib_connected = False
        self.trading_active = False
        self.es_update_timer = None
        self.auto_connect_attempts = 0

        # Risk parameters
        self.current_risk_params = None
        self.risk_monitoring_active = False

        # Widget storage
        self.symbol_widgets = {}

        # Prometheus metrics attributes - renumbered 1-10
        self.system_components = {}
        self.client_indicators = {}
        self.system_stats = {}
        self.prometheus_timer = None

        # Custom Metrics Integration (Internal Module)
        self.custom_metrics_integration = None
        self.custom_metrics_updater = None
        self.custom_metrics_widgets = {}

        # =======================================================================
        # REAL DATA INTEGRATION ATTRIBUTES
        # =======================================================================
        self.real_data_active = False
        self.real_data_timer = None
        self.data_file = Path.home() / "Projects/Spyder/market_data/live_data.json"
        self._check_timer = None
        self._error_count = 0

        # Try to connect to real Prometheus collector if available
        if PROMETHEUS_AVAILABLE:
            self.get_client_status = get_client_status
            self.get_system_metrics = get_system_metrics
        else:
            self.get_client_status = None
            self.get_system_metrics = None

        # Initialize UI
        self.setup_ui()
        self.setup_timers()
        self.load_test_data()
        self.load_default_risk_parameters()

        # Initialize Custom Metrics if available
        if CUSTOM_METRICS_AVAILABLE:
            try:
                self.custom_metrics_integration = CustomMetricsIntegration(self)
                self.custom_metrics_updater = DashboardMetricsUpdater(self, self.custom_metrics_integration)
                self.custom_metrics_integration.start()

                # Connect status signals
                self.custom_metrics_integration.connection_status_changed.connect(
                    lambda connected: self.add_system_log(f"Custom Metrics Engine {'active' if connected else 'inactive'}")
                )
                self.logger.info("✅ Custom Metrics Integration (Internal Module) initialized")
            except Exception as e:
                self.logger.error(f"Failed to initialize Custom Metrics: {e}")
                CUSTOM_METRICS_AVAILABLE = False

        # Start market worker with ib_async
        self.start_market_worker()

        # =======================================================================
        # REAL DATA INTEGRATION - AUTO-DETECT AFTER UI IS READY
        # =======================================================================
        QTimer.singleShot(2000, self.check_and_apply_real_data)

        self.logger.info("Dashboard initialized with real data integration")

    # ==========================================================================
    # REAL DATA INTEGRATION METHODS
    # ==========================================================================
    def check_and_apply_real_data(self):
        """Check for real data and apply patch if available"""
        try:
            if self.data_file.exists():
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                
                if data:
                    spy_price = data.get('SPY', {}).get('last', 'N/A')
                    self.add_system_log(f"🔥 Real data detected - SPY: ${spy_price}")
                    self.apply_real_data_patch()
                    return True
            
            # No real data found - setup monitoring
            self.add_system_log("📊 No real data detected - will monitor for availability")
            self.setup_real_data_monitoring()
            return False
            
        except Exception as e:
            self.add_system_log(f"⚠️ Error checking real data: {e}")
            return False

    def apply_real_data_patch(self):
        """Apply real data patch to existing dashboard"""
        try:
            self.add_system_log("🔥 Applying real data patch...")
            
            # Stop the simulation timer in market worker
            if hasattr(self, 'market_worker'):
                worker = self.market_worker
                if hasattr(worker, 'update_timer') and worker.update_timer:
                    worker.update_timer.stop()
                    self.add_system_log("✅ Stopped simulation timer")
            
            # Slow down automation for real data
            if hasattr(self, 'automation_timer'):
                self.automation_timer.setInterval(20000)  # 20 seconds instead of 3
            
            # Start real data updates
            self.real_data_timer = QTimer()
            self.real_data_timer.timeout.connect(self.update_with_real_data)
            self.real_data_timer.start(1000)  # Update every second
            
            self.real_data_active = True
            
            # Update status immediately
            self.update_real_data_status()
            
            # Log success
            self.add_system_log("🔥 REAL MARKET DATA ACTIVE - IB Gateway prices")
            self.add_automation_log("Real-time market data from Interactive Brokers")
            
        except Exception as e:
            self.add_system_log(f"❌ Error applying real data patch: {e}")

    def update_with_real_data(self):
        """Update dashboard with real market data"""
        try:
            if not self.data_file.exists():
                return
            
            with open(self.data_file, 'r') as f:
                live_data = json.load(f)
            
            if not live_data:
                return
            
            # Update symbol widgets directly
            for symbol, data in live_data.items():
                if symbol in self.symbol_widgets:
                    widget = self.symbol_widgets[symbol]
                    
                    # Update price
                    if hasattr(widget, 'price_label'):
                        widget.price_label.setText(f"{data['last']:.2f}")
                    
                    # Update change with color
                    if hasattr(widget, 'change_label'):
                        change = data['change']
                        sign = "+" if change >= 0 else ""
                        widget.change_label.setText(f"{sign}{change:.2f}")
                        color = "#00ff41" if change >= 0 else "#ff1744"
                        widget.change_label.setStyleSheet(f"color: {color};")
                    
                    # Update percentage with color
                    if hasattr(widget, 'pct_label'):
                        pct = data['change_pct']
                        sign = "+" if pct >= 0 else ""
                        widget.pct_label.setText(f"{sign}{pct:.2f}%")
                        color = "#00ff41" if pct >= 0 else "#ff1744"
                        widget.pct_label.setStyleSheet(f"color: {color};")
            
            # Update toolbar indices
            self.update_toolbar_with_real_data(live_data)
            
        except Exception as e:
            # Suppress frequent errors in logs
            if not hasattr(self, '_error_count'):
                self._error_count = 0
            
            self._error_count += 1
            if self._error_count <= 5:  # Only show first 5 errors
                self.add_system_log(f"⚠️ Real data update error: {e}")

    def update_toolbar_with_real_data(self, live_data):
        """Update toolbar indices with real data"""
        try:
            # Update SPX from SPY (SPY * 10)
            if 'SPY' in live_data:
                spy_data = live_data['SPY']
                
                if hasattr(self, 'spx_value'):
                    self.spx_value.setText(f" {spy_data['last'] * 10:.0f}")
                
                if hasattr(self, 'spx_change'):
                    change = spy_data['change'] * 10
                    pct = spy_data['change_pct']
                    sign = "+" if change >= 0 else ""
                    self.spx_change.setText(f"  {sign}{change:.0f}  {sign}{pct:.1f}%")
                    color = "#00ff41" if change >= 0 else "#ff1744"
                    self.spx_change.setStyleSheet(f"color: {color};")
            
            # Update NDX from QQQ (QQQ * 35)
            if 'QQQ' in live_data:
                qqq_data = live_data['QQQ']
                
                if hasattr(self, 'ndx_value'):
                    self.ndx_value.setText(f" {qqq_data['last'] * 35:.0f}")
                
                if hasattr(self, 'ndx_change'):
                    change = qqq_data['change'] * 35
                    pct = qqq_data['change_pct']
                    sign = "+" if change >= 0 else ""
                    self.ndx_change.setText(f"  {sign}{change:.0f}  {sign}{pct:.1f}%")
                    color = "#00ff41" if change >= 0 else "#ff1744"
                    self.ndx_change.setStyleSheet(f"color: {color};")
            
            # Update DJI from DIA (DIA * 98)
            if 'DIA' in live_data:
                dia_data = live_data['DIA']
                
                if hasattr(self, 'dji_value'):
                    self.dji_value.setText(f" {dia_data['last'] * 98:.0f}")
                
                if hasattr(self, 'dji_change'):
                    change = dia_data['change'] * 98
                    pct = dia_data['change_pct']
                    sign = "+" if change >= 0 else ""
                    self.dji_change.setText(f"  {sign}{change:.0f}  {sign}{pct:.1f}%")
                    color = "#00ff41" if change >= 0 else "#ff1744"
                    self.dji_change.setStyleSheet(f"color: {color};")
        
        except Exception as e:
            pass  # Suppress toolbar update errors

    def update_real_data_status(self):
        """Update status indicators for real data"""
        try:
            # Update market data status
            if hasattr(self, 'market_data_status'):
                self.market_data_status.setText("LIVE - REAL")
                self.market_data_status.setStyleSheet("color: #00ff41;")
            
            # Update connection status
            if hasattr(self, 'connection_label'):
                self.connection_label.setText("IB CONNECTED - REAL DATA")
                self.connection_label.setStyleSheet("color: #00ff41;")
            
            if hasattr(self, 'connection_dot'):
                self.connection_dot.setStyleSheet("color: #00ff41;")
            
        except Exception as e:
            pass  # Not critical

    def setup_real_data_monitoring(self):
        """Setup monitoring for real data to become available"""
        def check_for_real_data():
            """Check if real data becomes available"""
            if self.real_data_active:
                return  # Already using real data
            
            if self.data_file.exists():
                try:
                    with open(self.data_file, 'r') as f:
                        data = json.load(f)
                    
                    if data:
                        self.add_system_log("🔥 Real data detected - switching from simulation!")
                        self._check_timer.stop()
                        self.apply_real_data_patch()
                except:
                    pass
        
        # Check every 5 seconds for real data
        self._check_timer = QTimer()
        self._check_timer.timeout.connect(check_for_real_data)
        self._check_timer.start(5000)

    def refresh_market_data(self):
        """Enhanced refresh market data - callback for refresh icon click"""
        try:
            if self.real_data_active:
                self.add_system_log("🔥 Refreshing real market data...")
                
                # Force immediate update
                self.update_with_real_data()
                
                self.refresh_icon.setEnabled(False)
                QTimer.singleShot(1000, lambda: self.refresh_icon.setEnabled(True))
                
                self.add_system_log("✅ Real market data refreshed")
                
            elif self.market_worker:
                self.add_system_log("🔥 Refreshing simulation data...")
                
                if not self.ib_connected:
                    self.add_system_log("⚠️ Not connected to IB Gateway - using simulation data")
                
                self.refresh_icon.setEnabled(False)
                QTimer.singleShot(1000, lambda: self.refresh_icon.setEnabled(True))
                
                self.add_system_log("✅ Market data refresh requested")
            else:
                self.add_system_log("❌ Market worker not available")
                
        except Exception as e:
            self.logger.error(f"Error refreshing market data: {e}")
            self.add_system_log(f"❌ Refresh error: {e}")

    # ==========================================================================
    # UI CREATION METHODS
    # ==========================================================================
    def setup_ui(self):
        """Setup the complete UI"""
        self.setWindowTitle("SPYDER - Autonomous Options Trading System v1.0")
        self.setGeometry(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT)

        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {COLORS['background']};
            }}
            QLabel {{
                color: {COLORS['text']};
                font-weight: normal;
            }}
            QGroupBox {{
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: {COLORS['background']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }}
            QPushButton {{
                background-color: {COLORS['panel']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                padding: 8px;
                border-radius: 3px;
                font-weight: normal;
            }}
            QPushButton:hover {{
                background-color: #2a2a2a;
            }}
            QTableWidget {{
                background-color: {COLORS['panel']};
                alternate-background-color: {COLORS['background']};
                color: {COLORS['text']};
                gridline-color: {COLORS['grid']};
                border: 1px solid {COLORS['border']};
                font-size: 11px;
            }}
            QTableWidgetItem {{
                font-size: 11px;
            }}
            QHeaderView::section {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                padding: 5px;
                font-size: 10px;
            }}
            QTextEdit {{
                background-color: {COLORS['panel']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
            }}
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(3, 3, 3, 3)
        main_layout.setSpacing(3)

        toolbar = self.create_toolbar()
        main_layout.addWidget(toolbar)

        content_splitter = QSplitter(Qt.Orientation.Horizontal)

        left_panel = self.create_left_panel()
        content_splitter.addWidget(left_panel)

        center_panel = self.create_center_panel()
        content_splitter.addWidget(center_panel)

        right_panel = self.create_right_panel()
        content_splitter.addWidget(right_panel)

        content_splitter.setSizes([340, 970, 610])

        main_layout.addWidget(content_splitter)
        central_widget.setLayout(main_layout)

    def create_toolbar(self) -> QWidget:
        """Create top toolbar"""
        toolbar = QWidget()
        toolbar.setFixedHeight(60)
        toolbar.setStyleSheet(f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']};")

        layout = QHBoxLayout()

        # SPYDER logo on left
        logo_label = QLabel("S P Y D E R")
        try:
            logo_font = QFont("Michroma", 16, QFont.Weight.Normal)
        except:
            logo_font = QFont("Arial", 16, QFont.Weight.Normal)
        logo_label.setFont(logo_font)
        logo_label.setStyleSheet(f"color: {COLORS['text']}; letter-spacing: 5px;")
        layout.addWidget(logo_label)

        layout.addStretch(7)

        # Center section with market indices
        center_section = QHBoxLayout()
        center_section.setSpacing(15)

        # DJI
        dji_container = QHBoxLayout()
        dji_container.setSpacing(0)
        dji_label = QLabel("DJI:")
        dji_label.setStyleSheet(f"color: {COLORS['text']};")
        dji_container.addWidget(dji_label)

        self.dji_value = QLabel(" 43,900.42")
        self.dji_value.setStyleSheet(f"color: {COLORS['text']};")
        dji_container.addWidget(self.dji_value)

        self.dji_change = QLabel("  +350.35  +2.3%")
        self.dji_change.setStyleSheet(f"color: {COLORS['positive']};")
        dji_container.addWidget(self.dji_change)

        center_section.addLayout(dji_container)
        center_section.addWidget(QLabel("  ||  "))

        # SPX
        spx_container = QHBoxLayout()
        spx_container.setSpacing(0)
        spx_label = QLabel("SPX:")
        spx_label.setStyleSheet(f"color: {COLORS['text']};")
        spx_container.addWidget(spx_label)

        self.spx_value = QLabel(" 6,876.23")
        self.spx_value.setStyleSheet(f"color: {COLORS['text']};")
        spx_container.addWidget(self.spx_value)

        self.spx_change = QLabel("  +45.43  +1.2%")
        self.spx_change.setStyleSheet(f"color: {COLORS['positive']};")
        spx_container.addWidget(self.spx_change)

        center_section.addLayout(spx_container)
        center_section.addWidget(QLabel("  ||  "))

        # NDX
        ndx_container = QHBoxLayout()
        ndx_container.setSpacing(0)
        ndx_label = QLabel("NDX:")
        ndx_label.setStyleSheet(f"color: {COLORS['text']};")
        ndx_container.addWidget(ndx_label)

        self.ndx_value = QLabel(" 20,275.62")
        self.ndx_value.setStyleSheet(f"color: {COLORS['text']};")
        ndx_container.addWidget(self.ndx_value)

        self.ndx_change = QLabel("  +45.23  +0.78%")
        self.ndx_change.setStyleSheet(f"color: {COLORS['positive']};")
        ndx_container.addWidget(self.ndx_change)

        center_section.addLayout(ndx_container)

        layout.addLayout(center_section)
        layout.addStretch(3)

        # RIGHT SECTION
        right_section = QHBoxLayout()
        right_section.setSpacing(10)

        # Market data status with refresh icon
        market_data_container = QHBoxLayout()
        market_data_container.setSpacing(5)

        self.market_data_label = QLabel("MARKET DATA:")
        self.market_data_label.setStyleSheet(f"color: {COLORS['text']};")
        market_data_container.addWidget(self.market_data_label)

        self.market_data_status = QLabel("LIVE")
        self.market_data_status.setStyleSheet(f"color: {COLORS['positive']};")
        market_data_container.addWidget(self.market_data_status)

        # Add refresh icon
        self.refresh_icon = QPushButton()
        self.refresh_icon.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.refresh_icon.setIconSize(QSize(16, 16))
        self.refresh_icon.setFixedSize(20, 20)
        self.refresh_icon.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_icon.setToolTip("Refresh market data")
        self.refresh_icon.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                padding: 2px;
            }
            QPushButton:hover {
                background-color: #2a2a2a;
                border-radius: 3px;
            }
            QPushButton:pressed {
                background-color: #3a3a3a;
            }
        """)
        self.refresh_icon.clicked.connect(self.refresh_market_data)
        market_data_container.addWidget(self.refresh_icon)

        right_section.addLayout(market_data_container)
        right_section.addSpacing(20)
        right_section.addWidget(QLabel(" | "))

        # IB CONNECTION STATUS
        self.ib_container = QWidget()
        self.ib_container.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ib_container.setToolTip("Click to connect/disconnect")
        self.ib_container.setStyleSheet("""
            QWidget:hover {
                background-color: #2a2a2a;
                border-radius: 3px;
                padding: 2px;
            }
        """)
        ib_layout = QHBoxLayout()
        ib_layout.setContentsMargins(5, 2, 5, 2)
        ib_layout.setSpacing(3)

        self.connection_dot = QLabel("●")
        self.connection_dot.setStyleSheet(f"color: {COLORS['positive']};")
        ib_layout.addWidget(self.connection_dot)

        self.connection_label = QLabel("IB CONNECTED")
        self.connection_label.setStyleSheet(f"color: {COLORS['positive']};")
        ib_layout.addWidget(self.connection_label)

        self.ib_container.setLayout(ib_layout)
        self.ib_container.mousePressEvent = self.toggle_ib_connection

        right_section.addWidget(self.ib_container)
        right_section.addWidget(QLabel(" | "))

        # DATE/TIME
        self.datetime_label = QLabel(datetime.now().strftime("%Y-%m-%d   %H:%M:%S  ET"))
        self.datetime_label.setStyleSheet("font-size: 14px;")
        right_section.addWidget(self.datetime_label)

        layout.addLayout(right_section)

        toolbar.setLayout(layout)
        return toolbar

    def create_left_panel(self) -> QWidget:
        """Create left panel with market overview"""
        panel = QGroupBox("MARKET OVERVIEW")
        panel.setStyleSheet(f"background-color: {COLORS['background']};")
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 10, 0, 0)

        # Header
        header = QWidget()
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(10, 0, 5, 0)

        symbol_header = QLabel("SYMBOL")
        symbol_header.setFixedWidth(60)
        symbol_header.setStyleSheet(f"color: {COLORS['cyan']}; font-weight: normal;")

        last_header = QLabel("LAST")
        last_header.setFixedWidth(70)
        last_header.setAlignment(Qt.AlignmentFlag.AlignRight)
        last_header.setStyleSheet(f"color: {COLORS['cyan']}; font-weight: normal;")

        chg_header = QLabel("CHG")
        chg_header.setFixedWidth(55)
        chg_header.setAlignment(Qt.AlignmentFlag.AlignRight)
        chg_header.setStyleSheet(f"color: {COLORS['cyan']}; font-weight: normal;")

        chg_pct_header = QLabel("CHG%")
        chg_pct_header.setFixedWidth(55)
        chg_pct_header.setAlignment(Qt.AlignmentFlag.AlignRight)
        chg_pct_header.setStyleSheet(f"color: {COLORS['cyan']}; font-weight: normal;")

        header_layout.addWidget(symbol_header)
        header_layout.addWidget(last_header)
        header_layout.addWidget(chg_header)
        header_layout.addWidget(chg_pct_header)
        header.setLayout(header_layout)

        layout.addWidget(header)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"color: {COLORS['border']};")
        layout.addWidget(separator)

        # Scroll area for symbols
        scroll_area = QScrollArea()
        scroll_area.setStyleSheet(f"background-color: {COLORS['background']};")
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet(f"background-color: {COLORS['background']};")
        scroll_layout = QVBoxLayout()
        scroll_layout.setSpacing(1)

        # Create symbol widgets - ALL SYMBOLS FROM T09
        self.symbol_widgets = {}
        for category, symbols in MARKET_SYMBOLS.items():
            cat_label = QLabel(category)
            cat_label.setStyleSheet(f"color: {COLORS['cyan']}; font-size: 12px; padding: 5px 0px 2px 10px; font-weight: normal;")
            scroll_layout.addWidget(cat_label)

            for symbol in symbols:
                widget = MarketSymbolWidget(symbol, category)
                widget.setStyleSheet(f"background-color: {COLORS['background']};")
                self.symbol_widgets[symbol] = widget
                scroll_layout.addWidget(widget)

        scroll_layout.addStretch()
        scroll_widget.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)

        layout.addWidget(scroll_area)
        panel.setLayout(layout)
        return panel

    def create_center_panel(self) -> QWidget:
        """Create center panel"""
        panel = QWidget()
        layout = QVBoxLayout()

        # Market regime indicator
        regime_widget = QWidget()
        regime_widget.setStyleSheet(f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']};")
        regime_widget.setFixedHeight(40)
        regime_layout = QHBoxLayout()

        regime_layout.addStretch()

        center_container = QHBoxLayout()
        center_container.setSpacing(20)

        regime_section = QHBoxLayout()
        regime_section.setSpacing(5)
        regime_label = QLabel("MARKET REGIME: ")
        regime_label.setStyleSheet(f"color: {COLORS['text']};")
        regime_section.addWidget(regime_label)

        regime_value = QLabel("Low Volatility - Range Bound")
        regime_value.setStyleSheet(f"color: {COLORS['cyan']};")
        regime_section.addWidget(regime_value)

        center_container.addLayout(regime_section)

        separator_label = QLabel("|")
        separator_label.setStyleSheet(f"color: {COLORS['text_dim']};")
        center_container.addWidget(separator_label)

        strategy_section = QHBoxLayout()
        strategy_section.setSpacing(5)
        strategy_label = QLabel("CURRENT ACTIVE STRATEGY: ")
        strategy_label.setStyleSheet(f"color: {COLORS['text']};")
        strategy_section.addWidget(strategy_label)

        strategy_value = QLabel("Iron Condor")
        strategy_value.setStyleSheet(f"color: {COLORS['cyan']};")
        strategy_section.addWidget(strategy_value)

        center_container.addLayout(strategy_section)

        regime_layout.addLayout(center_container)
        regime_layout.addStretch()

        regime_widget.setLayout(regime_layout)
        layout.addWidget(regime_widget)

        # Create the chart widget
        self.create_chart()
        layout.addWidget(self.chart_widget, 2)

        # Positions table
        positions_group = QGroupBox("ORDERS & POSITIONS")
        positions_layout = QVBoxLayout()

        self.positions_table = self.create_positions_table()
        self.positions_table.setMaximumHeight(190)
        self.positions_table.setMinimumHeight(190)
        positions_layout.addWidget(self.positions_table)

        positions_group.setLayout(positions_layout)
        layout.addWidget(positions_group, 1)

        # System logs with Signal Monitor Panel
        logs_container = QWidget()
        logs_container_layout = QHBoxLayout()
        logs_container_layout.setSpacing(5)
        logs_container_layout.setContentsMargins(0, 0, 0, 0)

        # System logs (left side)
        logs_group = QGroupBox("SYSTEM LOG")
        logs_layout = QVBoxLayout()

        self.system_log = QTextEdit()
        self.system_log.setReadOnly(True)
        self.system_log.setMaximumHeight(150)
        self.system_log.setStyleSheet(f"font-family: monospace; font-size: 13px;")

        logs_layout.addWidget(self.system_log)
        logs_group.setLayout(logs_layout)

        # Signal Monitor Panel (right side)
        signal_group = QGroupBox("SIGNAL MONITOR")
        signal_group.setStyleSheet(f"QGroupBox {{ color: {COLORS['text']}; font-weight: normal; }}")
        signal_layout = QVBoxLayout()
        signal_layout.setContentsMargins(5, 5, 5, 5)

        self.signal_panel = SignalMonitorPanel()
        signal_layout.addWidget(self.signal_panel)
        signal_group.setLayout(signal_layout)

        logs_container_layout.addWidget(logs_group, 65)
        logs_container_layout.addWidget(signal_group, 35)

        logs_container.setLayout(logs_container_layout)
        layout.addWidget(logs_container, 1)

        panel.setLayout(layout)
        return panel

    def create_right_panel(self) -> QWidget:
        """Create right panel with controls and metrics"""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(3)
        layout.setContentsMargins(5, 5, 5, 5)

        # Control buttons
        button_layout = QHBoxLayout()

        self.start_btn = QPushButton("START TRADING")
        self.start_btn.setStyleSheet(f"background-color: {COLORS['positive']}; color: black;")
        self.start_btn.setToolTip("Start automated trading")
        self.start_btn.clicked.connect(self.start_trading)
        button_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("STOP TRADING")
        self.stop_btn.setStyleSheet(f"background-color: {COLORS['warning']};")
        self.stop_btn.setToolTip("Stop trading but keep orders and positions")
        self.stop_btn.clicked.connect(self.stop_trading)
        button_layout.addWidget(self.stop_btn)

        self.emergency_btn = QPushButton("EMERGENCY CLOSE")
        self.emergency_btn.setStyleSheet(f"background-color: {COLORS['negative']};")
        self.emergency_btn.setToolTip("Close all orders and positions, stop trading, and disconnect from IB")
        self.emergency_btn.clicked.connect(self.emergency_close)
        button_layout.addWidget(self.emergency_btn)

        layout.addLayout(button_layout)

        # Account info
        account_group = QGroupBox("")
        account_layout = QVBoxLayout()

        table_widget = QWidget()
        table_widget.setStyleSheet(f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']}; padding: 5px;")
        table_layout = QGridLayout()
        table_layout.setContentsMargins(8, -2, 8, 8)
        table_layout.setHorizontalSpacing(10)
        table_layout.setVerticalSpacing(6)

        cell_style = f"padding: 5px 10px; background-color: {COLORS['background']}; border: 1px solid {COLORS['border']};"

        # Account row
        account_label = QLabel("ACCOUNT")
        account_label.setStyleSheet(cell_style)
        table_layout.addWidget(account_label, 0, 0)

        account_value = QLabel("DU5361048")
        account_value.setStyleSheet(cell_style)
        table_layout.addWidget(account_value, 0, 1)

        mode_label = QLabel("MODE: PAPER")
        mode_label.setStyleSheet(cell_style + f"color: {COLORS['orange']};")
        table_layout.addWidget(mode_label, 0, 2)

        self.risk_params_btn = QPushButton("RISK LEVELS")
        self.risk_params_btn.setStyleSheet(f"background-color: #0066CC; color: white;")
        self.risk_params_btn.setToolTip("Configure global and strategy-specific risk parameters")
        self.risk_params_btn.clicked.connect(self.show_risk_parameters)
        table_layout.addWidget(self.risk_params_btn, 0, 3)

        # Separator
        spacer_label = QLabel("")
        spacer_label.setFixedHeight(20)
        table_layout.addWidget(spacer_label, 1, 0, 1, 4)

        # Financial data rows
        settled_label = QLabel("SETTLED CASH")
        settled_label.setStyleSheet(cell_style)
        table_layout.addWidget(settled_label, 2, 0)

        self.settled_value = QLabel("$21,800,000.00")
        self.settled_value.setStyleSheet(cell_style + "text-align: right;")
        self.settled_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        table_layout.addWidget(self.settled_value, 2, 1)

        realized_label = QLabel("REALIZED P&L")
        realized_label.setStyleSheet(cell_style)
        table_layout.addWidget(realized_label, 2, 2)

        self.realized_value = QLabel("$2,030,450.00")
        self.realized_value.setStyleSheet(cell_style + f"color: {COLORS['positive']}; text-align: right;")
        self.realized_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        table_layout.addWidget(self.realized_value, 2, 3)

        buying_label = QLabel("BUYING POWER")
        buying_label.setStyleSheet(cell_style)
        table_layout.addWidget(buying_label, 3, 0)

        self.buying_value = QLabel("$20,450,000.00")
        self.buying_value.setStyleSheet(cell_style + "text-align: right;")
        self.buying_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        table_layout.addWidget(self.buying_value, 3, 1)

        unrealized_label = QLabel("UNREALIZED P&L")
        unrealized_label.setStyleSheet(cell_style)
        table_layout.addWidget(unrealized_label, 3, 2)

        self.unrealized_value = QLabel("$1,385,000.00")
        self.unrealized_value.setStyleSheet(cell_style + f"color: {COLORS['positive']}; text-align: right;")
        self.unrealized_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        table_layout.addWidget(self.unrealized_value, 3, 3)

        table_widget.setLayout(table_layout)
        account_layout.addWidget(table_widget)
        account_group.setLayout(account_layout)
        layout.addWidget(account_group)

        # P&L Performance
        pnl_group = QGroupBox("P&L PERFORMANCE")
        pnl_layout = QVBoxLayout()
        pnl_layout.setContentsMargins(5, 1, 5, 1)
        pnl_layout.setSpacing(1)

        self.pnl_table = self.create_pnl_table()
        self.pnl_table.setFixedHeight(122)
        pnl_layout.addWidget(self.pnl_table)

        pnl_group.setLayout(pnl_layout)
        layout.addWidget(pnl_group)

        # Risk Monitor
        risk_group = QGroupBox("RISK MONITOR")
        risk_layout = QVBoxLayout()
        risk_layout.setSpacing(2)

        self.greek_bars = {
            "delta": GreekBar("Delta", -100, 100),
            "gamma": GreekBar("Gamma", -10, 10),
            "theta": GreekBar("Theta", -400, 0),
            "vega": GreekBar("Vega", -600, 0),
        }

        for bar in self.greek_bars.values():
            risk_layout.addWidget(bar)

        risk_group.setLayout(risk_layout)
        layout.addWidget(risk_group)

        # Autonomous AI Activity
        auto_group = QGroupBox("AUTONOMOUS AI ACTIVITY")
        auto_group.setStyleSheet(f"""
            QGroupBox {{
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                margin-top: 12px;
                padding-top: 5px;
                background-color: {COLORS['background']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                top: -2px;
            }}
        """)
        auto_layout = QVBoxLayout()
        auto_layout.setContentsMargins(5, 5, 5, 5)
        auto_layout.setSpacing(0)

        self.auto_log = QTextEdit()
        self.auto_log.setReadOnly(True)
        self.auto_log.setFixedHeight(140)
        self.auto_log.setStyleSheet(f"""
            QTextEdit {{
                font-family: monospace;
                font-size: 13px;
                color: {COLORS['cyan']};
                padding: 1px;
                border: 1px solid {COLORS['border']};
                background-color: {COLORS['panel']};
                margin: 0px;
            }}
        """)
        self.auto_log.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.auto_log.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        auto_layout.addWidget(self.auto_log)
        auto_group.setLayout(auto_layout)
        layout.addWidget(auto_group)

        # Unified Prometheus Metrics
        metrics_widget = self.create_unified_prometheus_metrics()
        layout.addWidget(metrics_widget)

        panel.setLayout(layout)
        return panel

    def create_chart(self):
        """Create the SPY chart widget"""
        self.chart_widget = QWidget()
        self.chart_widget.setStyleSheet(f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']};")

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Create matplotlib figure
        self.figure = Figure(figsize=(10, 6), dpi=100)
        self.figure.patch.set_facecolor(COLORS["panel"])

        self.canvas = FigureCanvas(self.figure)
        self.canvas.setStyleSheet("background-color: transparent;")
        layout.addWidget(self.canvas)

        self.chart_widget.setLayout(layout)

        # Draw initial chart
        self.update_chart()

    def update_chart(self):
        """Update the SPY chart with candlesticks and indicators"""
        self.figure.clear()

        # Create sample OHLC data
        periods = 100
        dates = pd.date_range(end=datetime.now(), periods=periods, freq="5min")

        # Generate realistic OHLC data
        spy_price = self.market_data["SPY"]["last"] if "SPY" in self.market_data else 585

        opens = []
        highs = []
        lows = []
        closes = []
        volumes = []

        current_price = spy_price - 2

        for _ in range(periods):
            # Random walk
            change = random.random() * 0.5 - 0.25
            current_price += change

            # OHLC
            open_price = current_price
            high = current_price + random.random() * 0.3
            low = current_price - random.random() * 0.3
            close = low + random.random() * (high - low)
            volume = random.randint(1000000, 5000000)

            opens.append(open_price)
            highs.append(high)
            lows.append(low)
            closes.append(close)
            volumes.append(volume)

            current_price = close

        # Calculate indicators
        prev_high = max(highs) + random.uniform(0.5, 1.5)
        prev_low = min(lows) - random.uniform(0.5, 1.5)
        prev_close = closes[-1] + random.uniform(-1, 1)

        # Fibonacci Daily Pivot Points
        pivot = (prev_high + prev_low + prev_close) / 3
        r1 = (2 * pivot) - prev_low
        r2 = pivot + (prev_high - prev_low)
        r3 = prev_high + 2 * (pivot - prev_low)
        s1 = (2 * pivot) - prev_high
        s2 = pivot - (prev_high - prev_low)
        s3 = prev_low - 2 * (pivot - prev_low)

        # 20-period Moving Average
        ma_20 = []
        for i in range(len(closes)):
            if i < 19:
                ma_20.append(None)
            else:
                ma_20.append(sum(closes[i - 19 : i + 1]) / 20)

        # VWAP
        vwap = []
        cumulative_pv = 0
        cumulative_volume = 0
        for i in range(len(closes)):
            typical_price = (highs[i] + lows[i] + closes[i]) / 3
            cumulative_pv += typical_price * volumes[i]
            cumulative_volume += volumes[i]
            vwap.append(cumulative_pv / cumulative_volume)

        # Create plot
        ax = self.figure.add_subplot(111)
        ax.yaxis.tick_left()
        ax.yaxis.set_label_position("left")

        # Set background color
        ax.set_facecolor(COLORS["panel"])

        # Plot Fibonacci Daily Pivot Points
        ax.axhline(y=pivot, color="#FFFF00", linewidth=1.5, linestyle="-", alpha=0.7, label="Pivot", zorder=1)
        ax.axhline(y=r1, color="#00FF41", linewidth=1.5, linestyle="-", alpha=0.6, label="R1", zorder=1)
        ax.axhline(y=r2, color="#00FF41", linewidth=1.5, linestyle="-", alpha=0.6, label="R2", zorder=1)
        ax.axhline(y=r3, color="#00FF41", linewidth=1.5, linestyle="-", alpha=0.6, label="R3", zorder=1)
        ax.axhline(y=s1, color="#FF1744", linewidth=1.5, linestyle="-", alpha=0.6, label="S1", zorder=1)
        ax.axhline(y=s2, color="#FF1744", linewidth=1.5, linestyle="-", alpha=0.6, label="S2", zorder=1)
        ax.axhline(y=s3, color="#FF1744", linewidth=1.5, linestyle="-", alpha=0.6, label="S3", zorder=1)

        # Plot 20-period Moving Average
        ma_x = [i for i, val in enumerate(ma_20) if val is not None]
        ma_y = [val for val in ma_20 if val is not None]
        ax.plot(ma_x, ma_y, color="#00B8D4", linewidth=1.5, alpha=0.8, label="MA(20)", zorder=2)

        # Plot VWAP
        ax.plot(range(len(vwap)), vwap, color="#BF00FF", linewidth=1.5, alpha=0.9, label="VWAP", zorder=2)

        # Plot candlesticks
        for i in range(len(dates)):
            color = COLORS["positive"] if closes[i] >= opens[i] else COLORS["negative"]

            # High-Low line
            ax.plot([i, i], [lows[i], highs[i]], color=color, linewidth=1, zorder=3)

            # Open-Close box
            height = abs(closes[i] - opens[i])
            bottom = min(opens[i], closes[i])

            rect = patches.Rectangle((i - 0.3, bottom), 0.6, height, facecolor=color, edgecolor=color, alpha=0.9, zorder=3)
            ax.add_patch(rect)

        # Add pivot level labels on the right
        ax.text(len(dates), pivot, f" P: {pivot:.2f}", color="#FFFF00", fontsize=9, va="center")
        ax.text(len(dates), r1, f" R1: {r1:.2f}", color="#00FF41", fontsize=8, va="center")
        ax.text(len(dates), r2, f" R2: {r2:.2f}", color="#00FF41", fontsize=8, va="center")
        ax.text(len(dates), r3, f" R3: {r3:.2f}", color="#00FF41", fontsize=8, va="center")
        ax.text(len(dates), s1, f" S1: {s1:.2f}", color="#FF1744", fontsize=8, va="center")
        ax.text(len(dates), s2, f" S2: {s2:.2f}", color="#FF1744", fontsize=8, va="center")
        ax.text(len(dates), s3, f" S3: {s3:.2f}", color="#FF1744", fontsize=8, va="center")

        # Styling
        ax.set_title("SPY - 5 min", color=COLORS["text"], fontsize=12, pad=10)
        ax.set_xlim(-1, len(dates))
        ax.grid(True, alpha=0.2, color=COLORS["grid"], zorder=0)

        # Format x-axis with time labels
        num_labels = 6
        indices = np.linspace(0, len(dates) - 1, num_labels, dtype=int)
        ax.set_xticks(indices)

        time_labels = []
        for idx in indices:
            time_str = dates[idx].strftime("%H:%M")
            time_labels.append(time_str)

        ax.set_xticklabels(time_labels, fontsize=9)

        # Style axes
        ax.tick_params(colors="#FFFFFF")
        for spine in ax.spines.values():
            spine.set_color(COLORS["border"])

        # Adjust layout
        self.figure.tight_layout()
        self.canvas.draw()

    def create_positions_table(self) -> QTableWidget:
        """Create positions table"""
        table = QTableWidget()

        columns = ["DATE", "SYMBOL", "CNTR", "STRIKES", "EXPIRY", "STRATEGY", "STATUS", "COST", "P&L", "AUTO STATUS"]

        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setStyleSheet("font-size: 11px;")

        # Set column widths
        table.setColumnWidth(0, 75)  # DATE
        table.setColumnWidth(1, 55)  # SYMBOL
        table.setColumnWidth(2, 45)  # CNTR
        table.setColumnWidth(3, 135)  # STRIKES
        table.setColumnWidth(4, 65)  # EXPIRY
        table.setColumnWidth(5, 150)  # STRATEGY
        table.setColumnWidth(6, 70)  # STATUS
        table.setColumnWidth(7, 95)  # COST
        table.setColumnWidth(8, 95)  # P&L
        table.setColumnWidth(9, 130)  # AUTO STATUS

        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        table.verticalHeader().setDefaultSectionSize(22)
        table.setMinimumHeight(190)
        table.setMaximumHeight(190)

        return table

    def create_pnl_table(self) -> QTableWidget:
        """Create P&L performance table"""
        table = QTableWidget(4, 8)

        headers = ["PERIOD", "PROFIT & LOSS", "WIN RATE", "AVG WIN/LOSS", "PROFIT-F", "SHARP", "SORTINO", "CALMAR"]
        table.setHorizontalHeaderLabels(headers)

        # Add sample data
        periods = ["TODAY", "WEEK", "MONTH", "YEAR"]
        data = [
            ("+$850.00", "75%", "$425/$120", "1.65", "1.85", "2.12", "1.95"),
            ("+$3,200.00", "68%", "$380/$150", "1.52", "1.92", "2.05", "2.18"),
            ("+$12,500.00", "72%", "$450/$180", "1.78", "2.15", "2.35", "2.62"),
            ("+$240,000,000.00", "70%", "$500/$200", "1.85", "2.35", "2.58", "3.15"),
        ]

        for row, (period, values) in enumerate(zip(periods, data)):
            table.setItem(row, 0, QTableWidgetItem(period))

            pnl_item = QTableWidgetItem(values[0])
            pnl_item.setTextAlignment(Qt.AlignmentFlag.AlignRight)
            pnl_item.setForeground(QColor(COLORS["positive"]))
            table.setItem(row, 1, pnl_item)

            win_rate_item = QTableWidgetItem(values[1])
            win_rate_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 2, win_rate_item)

            avg_item = QTableWidgetItem(values[2])
            avg_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 3, avg_item)

            profit_factor_item = QTableWidgetItem(values[3])
            profit_factor_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 4, profit_factor_item)

            sharp_ratio_item = QTableWidgetItem(values[4])
            sharp_ratio_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 5, sharp_ratio_item)

            sortino_ratio_item = QTableWidgetItem(values[5])
            sortino_ratio_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 6, sortino_ratio_item)

            calmar_ratio_item = QTableWidgetItem(values[6])
            calmar_ratio_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 7, calmar_ratio_item)

        table.setStyleSheet("font-size: 13px;")
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(22)

        # Set column widths
        table.setColumnWidth(0, 60)  # PERIOD
        table.setColumnWidth(1, 120)  # P&L
        table.setColumnWidth(2, 60)  # WIN RATE
        table.setColumnWidth(3, 120)  # AVG WIN/LOSS
        table.setColumnWidth(4, 65)  # PROFIT-F
        table.setColumnWidth(5, 55)  # SHARP
        table.setColumnWidth(6, 65)  # SORTINO
        table.setColumnWidth(7, 65)  # CALMAR

        table.setFixedWidth(610)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        return table

    def create_unified_prometheus_metrics(self) -> QWidget:
        """Create the unified Prometheus Metrics table (6x4 grid)"""
        container = QWidget()
        container.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS['panel']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
            }}
        """)
        container.setFixedHeight(200)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(2)

        # Title
        title_label = QLabel("PROMETHEUS METRICS MONITOR")
        title_label.setStyleSheet(f"""
            color: {COLORS['text']};
            font-size: 14px;
            font-weight: normal;
            padding-bottom: 1px;
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        main_layout.addWidget(title_label)

        main_layout.addSpacing(8)

        # Create the 6x4 grid
        grid = QGridLayout()
        grid.setSpacing(2)
        grid.setContentsMargins(0, 0, 0, 0)

        # Column headers
        headers = ["SYSTEM HEALTH", "IB CLIENTS 1-5", "IB CLIENTS 6-10", "INTERNAL MODULES"]
        for col, header in enumerate(headers):
            header_label = QLabel(header)
            header_label.setStyleSheet(f"""
                color: {COLORS['cyan']};
                font-size: 13px;
                font-weight: normal;
                padding: 2px;
                border-bottom: 1px solid {COLORS['border']};
            """)
            header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(header_label, 0, col)

        # System Components (Column 1)
        components = [("RISK MANAGER", "●"), ("MARKET DATA", "●"), ("STRATEGY ENGINE", "●"), ("ML MODELS", "●"), ("DATABASE", "●")]

        for row, (name, status) in enumerate(components, start=1):
            component_widget = QWidget()
            component_layout = QHBoxLayout()
            component_layout.setContentsMargins(5, 1, 5, 1)
            component_layout.setSpacing(3)

            indicator = QLabel(status)
            indicator.setStyleSheet(f"color: {COLORS['positive']}; font-size: 12px;")
            component_layout.addWidget(indicator)

            label = QLabel(name)
            label.setStyleSheet(f"color: {COLORS['text']}; font-size: 12px;")
            component_layout.addWidget(label)
            component_layout.addStretch()

            component_widget.setLayout(component_layout)
            self.system_components[name] = indicator
            grid.addWidget(component_widget, row, 0)

        # IB Clients 1-5 (Column 2)
        client_1_5_types = ["Admin", "Orders", "Core", "Options", "Volatility"]
        for row in range(1, 6):
            client_widget = QWidget()
            client_layout = QHBoxLayout()
            client_layout.setContentsMargins(5, 1, 5, 1)
            client_layout.setSpacing(3)

            indicator = QLabel("●")
            indicator.setStyleSheet(f"color: {COLORS['positive']}; font-size: 12px;")
            client_layout.addWidget(indicator)

            label = QLabel(f"CLIENT {row}: {client_1_5_types[row-1]}")
            label.setStyleSheet(f"color: {COLORS['text']}; font-size: 12px;")
            client_layout.addWidget(label)
            client_layout.addStretch()

            client_widget.setLayout(client_layout)
            self.client_indicators[f"CLIENT {row}"] = indicator
            grid.addWidget(client_widget, row, 1)

        # IB Clients 6-10 (Column 3)
        client_6_10_types = ["Internals", "Major ETFs", "Extended", "Sector ETFs", "International"]
        for row in range(1, 6):
            client_num = row + 5
            client_widget = QWidget()
            client_layout = QHBoxLayout()
            client_layout.setContentsMargins(5, 1, 5, 1)
            client_layout.setSpacing(3)

            indicator = QLabel("●")
            indicator.setStyleSheet(f"color: {COLORS['positive']}; font-size: 12px;")
            client_layout.addWidget(indicator)

            label = QLabel(f"CLIENT {client_num}: {client_6_10_types[row-1]}")
            label.setStyleSheet(f"color: {COLORS['text']}; font-size: 12px;")
            client_layout.addWidget(label)
            client_layout.addStretch()

            client_widget.setLayout(client_layout)
            self.client_indicators[f"CLIENT {client_num}"] = indicator
            grid.addWidget(client_widget, row, 2)

        # Internal Modules (Column 4)
        internal_modules = [("Custom Metrics", "custom_metrics"), ("Risk Calculator", "risk_calc"), 
                           ("ML Engine", "ml_engine"), ("Options Analyzer", "options"), ("Performance", "performance")]

        for row, (module_name, module_key) in enumerate(internal_modules, start=1):
            module_widget = QWidget()
            module_layout = QHBoxLayout()
            module_layout.setContentsMargins(5, 1, 5, 1)
            module_layout.setSpacing(3)

            indicator = QLabel("●")
            if module_key == "custom_metrics":
                indicator.setStyleSheet(f"color: {COLORS['warning']}; font-size: 12px;")
            else:
                indicator.setStyleSheet(f"color: {COLORS['positive']}; font-size: 12px;")
            module_layout.addWidget(indicator)

            label = QLabel(module_name)
            label.setStyleSheet(f"color: {COLORS['text']}; font-size: 12px;")
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
    # SIGNAL HANDLERS - ALL THREAD-SAFE
    # ==========================================================================
    @pyqtSlot(bool, str)
    def on_connection_status_changed(self, connected: bool, status: str):
        """Handle connection status change"""
        self.connection_info.ib_connected = connected
        self.ib_connected = connected

        if connected:
            self.connection_dot.setStyleSheet(f"color: {COLORS['positive']};")
            self.connection_label.setText("IB CONNECTED")
            self.connection_label.setStyleSheet(f"color: {COLORS['positive']};")
            self.add_system_log("✅ Connected to IB Gateway")
        else:
            self.connection_dot.setStyleSheet(f"color: {COLORS['negative']};")
            self.connection_label.setText("IB DISCONNECTED")
            self.connection_label.setStyleSheet(f"color: {COLORS['negative']};")

            if self.trading_active:
                self.trading_active = False
                self.connection_info.trading_active = False

                self.start_btn.setStyleSheet(f"background-color: {COLORS['positive']}; color: black;")
                self.start_btn.setText("START TRADING")

                self.add_automation_log("Trading stopped - IB connection lost")

            if "MARKET CLOSED" in status:
                self.add_system_log("📊 Market closed - IB disconnected")
            else:
                self.add_system_log("🔌 Disconnected from IB Gateway")

    @pyqtSlot(str)
    def on_market_data_status_changed(self, status: str):
        """Handle market data status change"""
        self.connection_info.market_data_status = status

        if status == "LIVE":
            self.market_data_status.setText("LIVE")
            self.market_data_status.setStyleSheet(f"color: {COLORS['positive']};")
            self.add_system_log("📊 Market data: LIVE")
        else:
            self.market_data_status.setText("NONE")
            self.market_data_status.setStyleSheet(f"color: {COLORS['negative']};")

            if self.trading_active:
                self.trading_active = False
                self.connection_info.trading_active = False

                self.start_btn.setStyleSheet(f"background-color: {COLORS['positive']}; color: black;")
                self.start_btn.setText("START TRADING")

                self.add_automation_log("Trading stopped - Market data lost")

            if status == "CLOSED":
                self.add_system_log("📊 Market closed - data static")
            else:
                self.add_system_log("📊 Market data: NONE")

    @pyqtSlot(dict)
    def on_market_data_updated(self, data: dict):
        """Handle market data update"""
        try:
            for symbol, market_info in data.items():
                if symbol in self.symbol_widgets:
                    self.symbol_widgets[symbol].update_data(market_info)

            self.market_data.update(data)

        except Exception as e:
            self.logger.error(f"Error updating market data: {e}")

    @pyqtSlot(str)
    def on_market_error(self, error: str):
        """Handle market error"""
        self.add_system_log(f"❌ Market error: {error}")

    @pyqtSlot(str)
    def on_heartbeat_received(self, message: str):
        """Handle heartbeat message"""
        self.add_system_log(message)

    def toggle_ib_connection(self, event):
        """Toggle IB connection when clicking on status"""
        if self.ib_connected:
            if self.trading_active:
                reply = QMessageBox.warning(
                    self, "Trading Active",
                    "Trading is currently active.\n\n"
                    "Disconnecting will stop all trading activities.\n"
                    "Do you want to continue?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )

                if reply != QMessageBox.StandardButton.Yes:
                    return

                self.trading_active = False
                self.connection_info.trading_active = False

                self.start_btn.setStyleSheet(f"background-color: {COLORS['positive']}; color: black;")
                self.start_btn.setText("START TRADING")

                self.add_automation_log("Trading stopped due to IB disconnection")

            if self.market_worker:
                self.market_worker.force_disconnect()
            self.ib_connected = False
            self.add_system_log("Manually disconnected from IB")
        else:
            if not is_market_hours():
                QMessageBox.information(
                    self, "Market Closed",
                    "Market is closed. Connection available during trading hours:\n"
                    "4:00 AM - 4:30 PM ET",
                )
                return

            if self.market_worker and self.market_worker.force_connect():
                self.ib_connected = True
                self.add_system_log("Manually connected to IB")
            else:
                self.add_system_log("Failed to connect to IB")

    def start_trading(self):
        """Handle start trading button click"""
        if not self.ib_connected:
            QMessageBox.warning(
                self, "Not Connected",
                "CONNECT IB FIRST\n\n"
                "Please connect to IB Gateway before starting trading.",
            )
            self.add_system_log("Cannot start trading - IB not connected")
            return

        if self.market_data_status.text() not in ["LIVE", "LIVE - REAL"]:
            QMessageBox.warning(
                self, "No Live Data",
                "NO LIVE DATA\n\n" "Cannot start trading without live market data.",
            )
            self.add_system_log("Cannot start trading - No live data")
            return

        if self.trading_active:
            self.add_system_log("Trading already active")
            return

        self.trading_active = True
        self.connection_info.trading_active = True

        self.start_btn.setStyleSheet(f"background-color: {COLORS['automation_active']}; color: white;")
        self.start_btn.setText("TRADING ACTIVE")

        self.add_system_log("Trading started successfully")
        self.add_automation_log("TRADING ACTIVE - Autonomous AI Engine engaged")
        self.add_automation_log("Monitoring SPY options for trading opportunities")

    def stop_trading(self):
        """Handle stop trading button click"""
        if not self.ib_connected:
            QMessageBox.information(
                self, "Not Connected",
                "There is no trading in progress as IB is disconnected.",
            )
            return

        if not self.trading_active:
            self.add_system_log("No active trading to stop")
            return

        self.trading_active = False
        self.connection_info.trading_active = False

        self.start_btn.setStyleSheet(f"background-color: {COLORS['positive']}; color: black;")
        self.start_btn.setText("START TRADING")

        self.add_system_log("Trading stopped - Orders and positions remain active")
        self.add_automation_log("TRADING STOPPED - Existing positions maintained")
        self.add_automation_log("Autonomous AI Engine on standby")

    def emergency_close(self):
        """Handle emergency close button click"""
        if not self.ib_connected:
            QMessageBox.critical(
                self, "IB Disconnected",
                "IB is disconnected, please reconnect or call Interactive Brokers:\n\n"
                "🇺🇸 US Toll-Free: +1 (877) 442-2757\n"
                "🌎 International: +1 (312) 542-6901\n\n"
                "to close positions and orders.",
            )
            return

        reply = QMessageBox.critical(
            self, "EMERGENCY CLOSE",
            "⚠️ EMERGENCY PROTOCOL ⚠️\n\n"
            "This will IMMEDIATELY:\n"
            "• Close ALL open positions\n"
            "• Cancel ALL pending orders\n"
            "• Stop automated trading\n"
            "• Disconnect from IB Gateway\n\n"
            "Are you sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.add_system_log("🚨 EMERGENCY CLOSE - All positions closed, system stopped")
            self.add_automation_log("EMERGENCY PROTOCOL - All positions closed by autonomous system")

            self.trading_active = False
            self.connection_info.trading_active = False

            self.start_btn.setStyleSheet(f"background-color: {COLORS['positive']}; color: black;")
            self.start_btn.setText("START TRADING")

            if self.market_worker:
                self.market_worker.force_disconnect()
            self.ib_connected = False

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    def start_market_worker(self):
        """Start the thread-safe market worker with market hours awareness"""
        try:
            self.market_thread = QThread()
            self.market_worker = ThreadSafeMarketDataWorker()
            self.market_worker.moveToThread(self.market_thread)

            self.market_worker.data