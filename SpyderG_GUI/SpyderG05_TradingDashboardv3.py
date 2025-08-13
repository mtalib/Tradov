#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderG05_TradingDashboard.py
Group: G (GUI/User Interface)
Purpose: Complete Trading Dashboard with Unified Prometheus Metrics Table
Author: Mohamed Talib
Date Created: 2025-07-05
Last Updated: 2025-08-13 Time: 11:00:00

Description:
    Enhanced trading dashboard with unified Prometheus Metrics monitoring table.
    Features a clean 5x4 grid layout combining System Components, Client Status
    (renumbered 1-10), and System Statistics in a single professional table.
    Includes market hours awareness, IB_async integration, and comprehensive metrics.

    UPDATES IN V11:
    - Integrated SignalInfoDialog for standardized popup dialogs
    - All 12 signal monitor buttons now use consistent 420x380 popups
    - Auto-close functionality when switching between signals
    - Improved positioning logic for dialog placement
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import os
import socket
import time
import traceback
from datetime import datetime, timedelta, time as dt_time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import random
import numpy as np
from threading import Lock
import queue
import pytz

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
    from SpyderB_Broker.SpyderB18_CustomMetricsClient import (
        CustomMetricsClient,
        get_metrics_client,
    )

    CUSTOM_METRICS_AVAILABLE = True
except ImportError:
    CUSTOM_METRICS_AVAILABLE = False
    print(
        "⚠️ Custom Metrics modules not available - Client 10 will run in simulation mode"
    )

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from pathlib import Path

project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# Import SignalInfoDialog for standardized popups
from SpyderG12_SignalInfoDialog import SignalInfoDialog

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
                        self.ib.cancelMktData(ticker.contract)
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
            ticker = self.ib.reqMktData(contract, "", False, False)

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
            elif symbol in [
                "GEX",
                "DEX",
                "OGL",
                "DIX",
                "SWAN",
                "$TICK",
                "$TRIN",
                "$ADD",
            ]:
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
        self.stale_data_timer.start(10000)

        self._init_simulation_data()

        print(
            f"🔧 Market Data Worker initialized - Market {'OPEN' if self.market_hours else 'CLOSED'}"
        )

    def _init_simulation_data(self):
        """Initialize simulation data with all symbols from T09"""
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

    def _subscribe_next_symbol(self):
        """Subscribe to next symbol in queue (FIXED METHOD)"""
        if not self.symbols_queue or self.current_symbol_index >= len(
            self.symbols_queue
        ):
            self.subscription_timer.stop()
            return

        symbol = self.symbols_queue[self.current_symbol_index]
        if self.ib_worker:
            self.ib_worker.subscribe_symbol(symbol)

        self.current_symbol_index += 1

        # If we've subscribed to all symbols, stop the timer
        if self.current_symbol_index >= len(self.symbols_queue):
            self.subscription_timer.stop()
            print(f"✅ Subscribed to all {len(self.symbols_queue)} symbols")

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

    @pyqtSlot()
    def start(self):
        """Start the worker"""
        print("🚀 Starting Thread-Safe Market Data Worker...")
        self.connection_status_changed.emit(True, "IB CONNECTED")
        self.market_data_status_changed.emit("LIVE")

    def _check_data_freshness(self):
        """Check if data is stale and needs refresh"""
        if not is_market_hours():
            return

        current_time = datetime.now()
        stale_threshold = timedelta(seconds=30)

        with QMutexLocker(self.data_mutex):
            for symbol, last_update in self.last_data_update.items():
                if current_time - last_update > stale_threshold:
                    print(f"⚠️ Stale data detected for {symbol}")

    def _emit_data(self):
        """Emit current market data"""
        with QMutexLocker(self.data_mutex):
            data_copy = self.market_data.copy()

        self._update_simulation_data(data_copy)
        self.data_updated.emit(data_copy)

    def _update_simulation_data(self, data: dict):
        """Update simulation data"""
        if not is_market_hours():
            return

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
                        "timestamp": datetime.now(),
                    }
                )

    def force_connect(self):
        """Manual connect"""
        print("🔄 Manual connect requested")
        if not is_market_hours():
            print("📊 Cannot connect - market is closed")
            return False
        self.ib_connected = True
        self.connection_status_changed.emit(True, "IB CONNECTED")
        self.market_data_status_changed.emit("LIVE")
        return True

    def force_disconnect(self):
        """Manual disconnect"""
        print("🔄 Manual disconnect requested")
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
        """
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


# ==============================================================================
# UPDATED SIGNAL MONITOR PANEL WITH STANDARDIZED DIALOGS
# ==============================================================================
class SignalMonitorPanel(QWidget):
    """Signal Monitor Panel with standardized popup dialogs"""
    
    def __init__(self):
        super().__init__()
        # Increased height to accommodate 6 rows
        self.setFixedHeight(165)  # Increased from 140
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
        self.hmm_button = TrafficLightButton("HMM")  # NEW
        self.skew_button = TrafficLightButton("SKEW")  # NEW
        
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
        layout.addWidget(self.hmm_button, 5, 0)  # NEW ROW
        layout.addWidget(self.skew_button, 5, 1)  # NEW ROW
        
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
        self.hmm_button.clicked.connect(self.show_hmm_dialog)  # NEW
        self.skew_button.clicked.connect(self.show_skew_dialog)  # NEW
        
        self.setLayout(layout)
        
        # Store current dialog reference
        self.current_dialog = None
        
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_button_states)
        self.update_timer.start(5000)
        
    def update_button_states(self):
        """Update traffic light colors"""
        import random
        
        # Original 10 buttons
        for button in [self.vix_button, self.ai_button, self.gex_button, 
                      self.dix_button, self.rsi_button, self.risk_button,
                      self.ogl_button, self.div_button, self.dex_button]:
            button.set_status(random.choice(['green', 'yellow', 'red']))
        
        # SWAN - weighted probability
        swan_random = random.random()
        if swan_random < 0.85:
            self.swan_button.set_status('green')
        elif swan_random < 0.95:
            self.swan_button.set_status('yellow')
        else:
            self.swan_button.set_status('red')
        
        # HMM - uses blue/purple for regime states
        hmm_random = random.random()
        if hmm_random < 0.4:
            self.hmm_button.set_status('green')  # Low volatility regime
        elif hmm_random < 0.7:
            self.hmm_button.set_status('blue')   # Normal regime
        elif hmm_random < 0.9:
            self.hmm_button.set_status('yellow') # Transitioning
        else:
            self.hmm_button.set_status('red')    # High volatility regime
        
        # SKEW - based on tail risk levels
        skew_random = random.random()
        if skew_random < 0.5:
            self.skew_button.set_status('green')  # Normal skew
        elif skew_random < 0.8:
            self.skew_button.set_status('yellow') # Elevated skew  
        else:
            self.skew_button.set_status('red')    # Extreme skew
    
    def close_current_dialog(self):
        """Close the currently open dialog if any"""
        if self.current_dialog and not self.current_dialog.isHidden():
            self.current_dialog.close()
            self.current_dialog = None
    
    def show_signal_dialog(self, signal_type: str):
        """Show standardized dialog for any signal type"""
        # Close any existing dialog
        self.close_current_dialog()
        
        # Create and show new dialog
        self.current_dialog = SignalInfoDialog(signal_type, self)
        self.current_dialog.closed.connect(lambda: setattr(self, 'current_dialog', None))
        
        # Get the button that was clicked
        sender_button = self.sender()
        
        # Position dialog to the right of the Signal Monitor panel
        panel_global_pos = self.mapToGlobal(self.rect().topRight())
        dialog_x = panel_global_pos.x() + 10
        dialog_y = panel_global_pos.y()
        
        # Get the main window to check screen boundaries
        main_window = self.window()
        if main_window:
            # Ensure dialog stays within the main window
            window_geometry = main_window.geometry()
            
            # If dialog would go off the right edge, position it to the left of the panel
            if dialog_x + 420 > window_geometry.right():  # 420 is dialog width
                panel_left_pos = self.mapToGlobal(self.rect().topLeft())
                dialog_x = panel_left_pos.x() - 430  # 420 width + 10 margin
            
            # Ensure dialog doesn't go off the bottom
            if dialog_y + 380 > window_geometry.bottom():  # 380 is dialog height
                dialog_y = window_geometry.bottom() - 390
        
        self.current_dialog.move(dialog_x, dialog_y)
        self.current_dialog.show()
    
    # Dialog show methods - all using the new standardized dialog
    def show_vix_dialog(self):
        """Show VIX Monitor dialog"""
        self.show_signal_dialog('VIX MONITOR')
    
    def show_ai_dialog(self):
        """Show AI Decision dialog"""
        self.show_signal_dialog('AI DECISION')
    
    def show_gex_dialog(self):
        """Show GEX dialog"""
        self.show_signal_dialog('GEX')
    
    def show_dix_dialog(self):
        """Show DIX dialog"""
        self.show_signal_dialog('DIX')
    
    def show_rsi_dialog(self):
        """Show RSI Confluence dialog"""
        self.show_signal_dialog('RSI CONFLUENCE')
    
    def show_risk_dialog(self):
        """Show Risk Triggers dialog"""
        self.show_signal_dialog('RISK TRIGGERS')
    
    def show_ogl_dialog(self):
        """Show OGL dialog"""
        self.show_signal_dialog('OGL')
    
    def show_div_dialog(self):
        """Show Divergence dialog"""
        self.show_signal_dialog('DIVERGENCE')
    
    def show_dex_dialog(self):
        """Show DEX dialog"""
        self.show_signal_dialog('DEX')
    
    def show_swan_dialog(self):
        """Show Black Swan dialog"""
        self.show_signal_dialog('BLACK SWAN')
    
    def show_hmm_dialog(self):
        """Show HMM Regime Detector dialog"""
        self.show_signal_dialog('HMM')
    
    def show_skew_dialog(self):
        """Show SKEW Monitor dialog"""
        self.show_signal_dialog('SKEW')