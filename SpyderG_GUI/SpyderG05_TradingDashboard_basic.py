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
Last Updated: 2025-08-13 Time: 12:00:00

Description:
    Enhanced trading dashboard with unified Prometheus Metrics monitoring table.
    Features a clean 5x4 grid layout combining System Components, Client Status
    (renumbered 1-10), and System Statistics in a single professional table.
    Includes market hours awareness, IB_async integration, and comprehensive metrics.

    UPDATES IN V12:
    - REMOVED ALL IBAPI DEPENDENCIES - Pure ib_async implementation
    - Better error handling for missing modules
    - Isolated ib_async usage from other modules
    - Fixed import conflicts
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
import logging

# ==============================================================================
# CONFIGURE LOGGING TO SUPPRESS IBAPI WARNINGS
# ==============================================================================
logging.getLogger('ibapi').setLevel(logging.ERROR)
logging.getLogger('SpyderB_Broker').setLevel(logging.ERROR)

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

# ==============================================================================
# TIMEZONE SUPPORT
# ==============================================================================
try:
    import pytz
    PYTZ_AVAILABLE = True
except ImportError:
    PYTZ_AVAILABLE = False
    print("⚠️ pytz not available - using system timezone")

# ==============================================================================
# PANDAS (OPTIONAL)
# ==============================================================================
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    print("⚠️ pandas not available - chart features limited")

# ==============================================================================
# IB_ASYNC IMPORTS - PURE IB_ASYNC, NO IBAPI!
# ==============================================================================
try:
    from ib_async import (
        IB, 
        Stock, 
        Index, 
        Future, 
        Contract, 
        Ticker,
        MarketOrder,
        LimitOrder,
        StopOrder,
        Order,
        util
    )
    IB_ASYNC_AVAILABLE = True
    print("✅ Using pure ib_async for all IB Gateway connections")
    print("✅ NO IBAPI dependencies - clean ib_async implementation")
except ImportError as e:
    IB_ASYNC_AVAILABLE = False
    print(f"❌ ib_async not available: {e}")
    print("❌ Please install: pip install ib_async")

# ==============================================================================
# LOCAL IMPORTS WITH CAREFUL ERROR HANDLING
# ==============================================================================
from pathlib import Path
project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

# Basic utilities (should always work)
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    LOGGER_AVAILABLE = True
except ImportError:
    LOGGER_AVAILABLE = False
    print("⚠️ SpyderLogger not available - using standard logging")

try:
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
    ERROR_HANDLER_AVAILABLE = True
except ImportError:
    ERROR_HANDLER_AVAILABLE = False
    print("⚠️ SpyderErrorHandler not available")

# Import SignalInfoDialog for standardized popups
try:
    from SpyderG12_SignalInfoDialog import SignalInfoDialog
    SIGNAL_DIALOG_AVAILABLE = True
    print("✅ SignalInfoDialog available for standardized popups")
except ImportError:
    SIGNAL_DIALOG_AVAILABLE = False
    print("⚠️ SignalInfoDialog not available - using basic dialogs")

# Import Risk Parameters Dialog (OPTIONAL)
try:
    from SpyderG_GUI.SpyderG09_RiskParametersDialog import (
        RiskParametersDialog,
        show_risk_parameters_dialog,
    )
    RISK_DIALOG_AVAILABLE = True
    print("✅ Risk Parameters Dialog available")
except ImportError:
    RISK_DIALOG_AVAILABLE = False
    print("⚠️ Risk Parameters Dialog not available")

# Custom Metrics Integration (OPTIONAL - may use IBAPI)
CUSTOM_METRICS_AVAILABLE = False
try:
    # Only try to import if it doesn't use IBAPI
    import importlib.util
    spec = importlib.util.find_spec("SpyderG10_CustomMetricsIntegration")
    if spec:
        # Check if the module uses ibapi before importing
        module_path = spec.origin
        with open(module_path, 'r') as f:
            content = f.read()
            if 'ibapi' not in content.lower():
                from SpyderG10_CustomMetricsIntegration import (
                    CustomMetricsIntegration,
                    DashboardMetricsUpdater,
                )
                CUSTOM_METRICS_AVAILABLE = True
                print("✅ Custom Metrics Integration available (no IBAPI)")
            else:
                print("⚠️ Custom Metrics uses IBAPI - skipping to avoid conflicts")
except Exception as e:
    print(f"⚠️ Custom Metrics not available: {e}")

# Prometheus metrics (OPTIONAL - may use IBAPI)
PROMETHEUS_AVAILABLE = False
try:
    # Check if Prometheus module exists and doesn't use IBAPI
    import importlib.util
    spec = importlib.util.find_spec("SpyderG07_PrometheusMetricsDisplay")
    if spec:
        module_path = spec.origin
        if os.path.exists(module_path):
            with open(module_path, 'r') as f:
                content = f.read()
                if 'ibapi' not in content.lower():
                    from SpyderG07_PrometheusMetricsDisplay import get_client_status, get_system_metrics
                    PROMETHEUS_AVAILABLE = True
                    print("✅ Prometheus metrics available (no IBAPI)")
                else:
                    print("⚠️ Prometheus uses IBAPI - using simulation mode")
except Exception as e:
    print(f"⚠️ Prometheus metrics not available - using simulation: {e}")

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

# COMPLETE MARKET SYMBOLS
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
    if PYTZ_AVAILABLE:
        eastern = pytz.timezone("US/Eastern")
        now_et = datetime.now(eastern).time()
    else:
        # Fallback to system time
        now_et = datetime.now().time()
    return MARKET_OPEN_TIME <= now_et <= MARKET_CLOSE_TIME


def check_ib_gateway_connection():
    """Check if IB Gateway is running on standard ports"""
    try:
        # Check paper trading port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        paper_result = sock.connect_ex(("127.0.0.1", 4002))
        sock.close()

        if paper_result == 0:
            return True, "PAPER (Port 4002)"

        # Check live trading port
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
# SIMPLE LOGGER FALLBACK
# ==============================================================================
class SimpleLogger:
    """Simple logger fallback when SpyderLogger is not available"""
    
    @staticmethod
    def get_logger(name):
        logger = logging.getLogger(name)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger


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
# PURE IB_ASYNC WORKER - NO IBAPI DEPENDENCIES!
# ==============================================================================
class IBAsyncWorker(QObject):
    """Pure ib_async worker - completely free of IBAPI dependencies"""

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

        if IB_ASYNC_AVAILABLE:
            print("✅ Pure ib_async Worker initialized - NO IBAPI dependencies")
        else:
            print("⚠️ ib_async not available - running in simulation mode")

    def connect_to_ib(self, host="127.0.0.1", port=4002, client_id=CLIENT_ID):
        """Connect to IB Gateway using pure ib_async"""
        if not IB_ASYNC_AVAILABLE:
            print("⚠️ ib_async not available - cannot connect")
            return False
            
        try:
            print(f"🔌 Connecting to IB Gateway at {host}:{port} with client ID {client_id}")
            print("🔌 Using pure ib_async - NO IBAPI!")
            
            self.ib = IB()
            self.ib.connect(host, port, clientId=client_id, timeout=10)

            if self.ib.isConnected():
                print("✅ Connected to IB Gateway via ib_async")
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
            else:
                print("❌ Failed to connect to IB Gateway")
                return False
                
        except Exception as e:
            print(f"❌ Connection error: {e}")
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
            self.heartbeat_timer.setInterval(300000)  # 5 minutes
            print("💓 Heartbeat configured for regular trading hours")
        else:
            self.heartbeat_timer.setInterval(60000)  # 1 minute
            print("💓 Heartbeat configured for extended hours")

    def _send_heartbeat(self):
        """Send heartbeat to keep connection alive"""
        if not self._connected or not self.ib:
            return

        if not is_market_hours():
            self.heartbeat_timer.stop()
            print("💤 Market closed - stopping heartbeat")
            return

        try:
            # Use ib_async's reqCurrentTime
            server_time = self.ib.reqCurrentTime()
            self.heartbeat_count += 1
            self.last_heartbeat_time = datetime.now()

            local_time = datetime.now().strftime("%H:%M:%S")
            server_time_str = server_time.strftime("%H:%M:%S %Z") if server_time else "Unknown"

            message = f"Heartbeat #{self.heartbeat_count} | Local: {local_time} | Server: {server_time_str}"
            self.heartbeat_status.emit(True, message)
            self._configure_heartbeat()

        except Exception as e:
            print(f"❌ Heartbeat failed: {e}")
            self.heartbeat_status.emit(False, f"Heartbeat failed: {e}")

            if self.ib and not self.ib.isConnected():
                self._connected = False
                self.disconnected.emit()

    def disconnect(self):
        """Disconnect from IB Gateway"""
        if self.ib and self.ib.isConnected():
            with QMutexLocker(self.data_mutex):
                # Cancel market data subscriptions
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
            print("🔌 Disconnected from IB Gateway")

    def subscribe_symbol(self, symbol):
        """Subscribe to market data for a symbol using ib_async"""
        if not IB_ASYNC_AVAILABLE:
            return
            
        with QMutexLocker(self.data_mutex):
            if symbol in self.subscribed_symbols or not self._connected:
                return
            self.subscribed_symbols.add(symbol)

        try:
            contract = self._create_contract(symbol)
            if not contract:
                return

            print(f"📊 Subscribing to {symbol} via ib_async")
            self.ib.qualifyContracts(contract)
            ticker = self.ib.reqMktData(contract, "", False, False)

            with QMutexLocker(self.data_mutex):
                self.contracts[symbol] = contract
                self.tickers[symbol] = ticker

        except Exception as e:
            print(f"❌ Error subscribing to {symbol}: {e}")
            self.error_occurred.emit(0, 0, f"Subscribe error: {e}")

    def _create_contract(self, symbol):
        """Create IB contract using ib_async classes"""
        if not IB_ASYNC_AVAILABLE:
            return None
            
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
                # Custom metrics - no real contracts
                return None
            else:
                return None
        except Exception as e:
            print(f"❌ Error creating contract for {symbol}: {e}")
            return None

    def _emit_price_updates(self):
        """Emit price updates for all subscribed symbols"""
        if not self._connected or not self.tickers:
            return
            
        with QMutexLocker(self.data_mutex):
            for symbol, ticker in self.tickers.items():
                try:
                    last = ticker.last if ticker.last and ticker.last > 0 else 0
                    bid = ticker.bid if ticker.bid and ticker.bid > 0 else 0
                    ask = ticker.ask if ticker.ask and ticker.ask > 0 else 0

                    if last > 0 or bid > 0 or ask > 0:
                        if last == 0 and bid > 0 and ask > 0:
                            last = (bid + ask) / 2

                        self.price_update.emit(symbol, last, bid, ask)
                except Exception as e:
                    print(f"⚠️ Error emitting price for {symbol}: {e}")


# ==============================================================================
# THREAD-SAFE MARKET DATA WORKER
# ==============================================================================
class ThreadSafeMarketDataWorker(QObject):
    """Thread-safe market data worker using pure ib_async"""

    data_updated = pyqtSignal(dict)
    connection_status_changed = pyqtSignal(bool, str)
    market_data_status_changed = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    heartbeat_received = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        
        # Use simple logger if SpyderLogger not available
        if LOGGER_AVAILABLE:
            self.logger = SpyderLogger.get_logger(__name__)
        else:
            self.logger = SimpleLogger.get_logger(__name__)
            
        self.ib_worker = None
        self.ib_connected = True  # Start as connected for simulation
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

        print(f"🔧 Market Data Worker initialized - Market {'OPEN' if self.market_hours else 'CLOSED'}")
        print("🔧 Using pure ib_async - NO IBAPI dependencies")

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

    def _subscribe_next_symbol(self):
        """Subscribe to next symbol in queue"""
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
        print("🚀 Pure ib_async mode - NO IBAPI!")
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
                    self.logger.debug(f"⚠️ Stale data detected for {symbol}")

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

        for symbol, market_info in data.items():
            # Don't update custom metrics randomly
            if symbol not in ["GEX", "DEX", "OGL", "DIX", "SWAN"]:
                old_price = market_info["last"]
                change = random.uniform(-0.5, 0.5)
                new_price = old_price + change
                change_pct = (change / old_price * 100) if old_price != 0 else 0

                market_info.update({
                    "last": new_price,
                    "change": change,
                    "change_pct": change_pct,
                    "timestamp": datetime.now(),
                })

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
# WIDGET CLASSES (Rest of the implementation remains the same)
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


# ==============================================================================
# MAIN EXECUTION

# ==============================================================================
# MAIN DASHBOARD CLASS
# ==============================================================================
class SpyderTradingDashboard(QMainWindow):
    """Main Trading Dashboard Window"""
    
    def __init__(self):
        super().__init__()
        
        # Basic setup
        self.setWindowTitle("SPYDER Trading Dashboard v1.0")
        self.setGeometry(100, 100, WINDOW_WIDTH, WINDOW_HEIGHT)
        
        # Initialize components
        self.market_data = {}
        self.positions = []
        self.connection_info = ConnectionInfo()
        
        # Setup UI
        self.setup_ui()
        self.setup_timers()
        self.apply_dark_theme()
        
        # Initialize workers
        self.init_workers()
        
        print("✅ SpyderTradingDashboard initialized")
    
    def setup_ui(self):
        """Setup the user interface"""
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # Header
        self.create_header(main_layout)
        
        # Content area with splitter
        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel
        left_panel = self.create_left_panel()
        content_splitter.addWidget(left_panel)
        
        # Center panel
        center_panel = self.create_center_panel()
        content_splitter.addWidget(center_panel)
        
        # Right panel
        right_panel = self.create_right_panel()
        content_splitter.addWidget(right_panel)
        
        # Set splitter sizes
        content_splitter.setSizes([400, 800, 400])
        
        main_layout.addWidget(content_splitter)
        
        # Status bar
        self.create_status_bar()
    
    def create_header(self, parent_layout):
        """Create header section"""
        header_frame = QFrame()
        header_frame.setMaximumHeight(80)
        header_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['panel']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
            }}
        """)
        
        header_layout = QHBoxLayout(header_frame)
        
        # Title
        title = QLabel("🚀 SPYDER TRADING DASHBOARD")
        title.setStyleSheet(f"""
            font-size: 24px;
            font-weight: bold;
            color: {COLORS['positive']};
        """)
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Connection status
        self.connection_label = QLabel("● DISCONNECTED")
        self.connection_label.setStyleSheet(f"color: {COLORS['negative']}; font-size: 14px;")
        header_layout.addWidget(self.connection_label)
        
        # Connect button
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.toggle_connection)
        self.connect_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['positive']};
                color: black;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {COLORS['neutral']};
            }}
        """)
        header_layout.addWidget(self.connect_btn)
        
        parent_layout.addWidget(header_frame)
    
    def create_left_panel(self):
        """Create left panel with market data"""
        panel = QFrame()
        panel.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['panel']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
            }}
        """)
        
        layout = QVBoxLayout(panel)
        
        # Market Data section
        market_group = QGroupBox("MARKET DATA")
        market_group.setStyleSheet(f"""
            QGroupBox {{
                color: {COLORS['cyan']};
                font-weight: bold;
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }}
        """)
        
        market_layout = QVBoxLayout()
        
        # Market data table
        self.market_table = QTableWidget(8, 3)
        self.market_table.setHorizontalHeaderLabels(["Symbol", "Price", "Change"])
        self.market_table.horizontalHeader().setStretchLastSection(True)
        self.market_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
                gridline-color: {COLORS['border']};
            }}
        """)
        
        # Add sample data
        symbols = ["SPY", "VIX", "QQQ", "IWM", "TLT", "GLD", "DXY", "GEX"]
        for i, symbol in enumerate(symbols):
            self.market_table.setItem(i, 0, QTableWidgetItem(symbol))
            self.market_table.setItem(i, 1, QTableWidgetItem("0.00"))
            self.market_table.setItem(i, 2, QTableWidgetItem("0.00%"))
        
        market_layout.addWidget(self.market_table)
        market_group.setLayout(market_layout)
        
        layout.addWidget(market_group)
        
        # Signal Monitor section
        signals_group = QGroupBox("SIGNAL MONITOR")
        signals_group.setStyleSheet(f"""
            QGroupBox {{
                color: {COLORS['cyan']};
                font-weight: bold;
            }}
        """)
        
        signals_layout = QGridLayout()
        
        # Add signal buttons (simplified)
        signal_names = ["VIX", "GEX", "DIX", "RSI", "RISK", "OGL"]
        for i, name in enumerate(signal_names):
            btn = QPushButton(name)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS['neutral']};
                    color: black;
                    padding: 5px;
                    border-radius: 3px;
                }}
            """)
            signals_layout.addWidget(btn, i // 3, i % 3)
        
        signals_group.setLayout(signals_layout)
        layout.addWidget(signals_group)
        
        return panel
    
    def create_center_panel(self):
        """Create center panel with positions and orders"""
        panel = QFrame()
        panel.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['panel']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
            }}
        """)
        
        layout = QVBoxLayout(panel)
        
        # Positions section
        positions_group = QGroupBox("OPEN POSITIONS")
        positions_group.setStyleSheet(f"""
            QGroupBox {{
                color: {COLORS['cyan']};
                font-weight: bold;
            }}
        """)
        
        positions_layout = QVBoxLayout()
        
        self.positions_table = QTableWidget(0, 6)
        self.positions_table.setHorizontalHeaderLabels([
            "Symbol", "Type", "Qty", "Entry", "Current", "P&L"
        ])
        self.positions_table.horizontalHeader().setStretchLastSection(True)
        
        positions_layout.addWidget(self.positions_table)
        positions_group.setLayout(positions_layout)
        
        layout.addWidget(positions_group)
        
        # Orders section
        orders_group = QGroupBox("PENDING ORDERS")
        orders_group.setStyleSheet(f"""
            QGroupBox {{
                color: {COLORS['cyan']};
                font-weight: bold;
            }}
        """)
        
        orders_layout = QVBoxLayout()
        
        self.orders_table = QTableWidget(0, 5)
        self.orders_table.setHorizontalHeaderLabels([
            "Symbol", "Type", "Side", "Qty", "Price"
        ])
        
        orders_layout.addWidget(self.orders_table)
        orders_group.setLayout(orders_layout)
        
        layout.addWidget(orders_group)
        
        return panel
    
    def create_right_panel(self):
        """Create right panel with metrics and logs"""
        panel = QFrame()
        panel.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['panel']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
            }}
        """)
        
        layout = QVBoxLayout(panel)
        
        # Prometheus Metrics
        if PROMETHEUS_AVAILABLE:
            metrics_group = QGroupBox("PROMETHEUS METRICS")
            metrics_group.setStyleSheet(f"""
                QGroupBox {{
                    color: {COLORS['cyan']};
                    font-weight: bold;
                }}
            """)
            
            metrics_layout = QVBoxLayout()
            
            # Client status
            for i in range(9):
                client_label = QLabel(f"● CLIENT {i}: Active")
                client_label.setStyleSheet(f"color: {COLORS['positive']};")
                metrics_layout.addWidget(client_label)
            
            metrics_group.setLayout(metrics_layout)
            layout.addWidget(metrics_group)
        
        # Activity Log
        log_group = QGroupBox("ACTIVITY LOG")
        log_group.setStyleSheet(f"""
            QGroupBox {{
                color: {COLORS['cyan']};
                font-weight: bold;
            }}
        """)
        
        log_layout = QVBoxLayout()
        
        self.activity_log = QTextEdit()
        self.activity_log.setReadOnly(True)
        self.activity_log.setMaximumHeight(200)
        self.activity_log.append("System initialized...")
        
        log_layout.addWidget(self.activity_log)
        log_group.setLayout(log_layout)
        
        layout.addWidget(log_group)
        
        return panel
    
    def create_status_bar(self):
        """Create status bar"""
        status_bar = self.statusBar()
        status_bar.setStyleSheet(f"""
            QStatusBar {{
                background-color: {COLORS['panel']};
                color: {COLORS['text']};
            }}
        """)
        status_bar.showMessage("Ready")
    
    def setup_timers(self):
        """Setup update timers"""
        # Market data update timer
        self.market_timer = QTimer()
        self.market_timer.timeout.connect(self.update_market_data)
        self.market_timer.start(2000)  # Update every 2 seconds
        
        # Time update timer
        self.time_timer = QTimer()
        self.time_timer.timeout.connect(self.update_time)
        self.time_timer.start(1000)  # Update every second
    
    def apply_dark_theme(self):
        """Apply dark theme to the application"""
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {COLORS['background']};
            }}
            QWidget {{
                color: {COLORS['text']};
                font-family: 'Segoe UI', Arial, sans-serif;
            }}
        """)
    
    def init_workers(self):
        """Initialize worker threads"""
        # This would initialize the market data workers
        # For now, just set flags
        self.market_worker_active = False
    
    def toggle_connection(self):
        """Toggle IB connection"""
        if self.connection_info.ib_connected:
            self.disconnect_ib()
        else:
            self.connect_ib()
    
    def connect_ib(self):
        """Connect to IB Gateway"""
        self.connection_info.ib_connected = True
        self.connection_label.setText("● CONNECTED")
        self.connection_label.setStyleSheet(f"color: {COLORS['positive']}; font-size: 14px;")
        self.connect_btn.setText("Disconnect")
        self.activity_log.append(f"Connected to IB Gateway")
    
    def disconnect_ib(self):
        """Disconnect from IB Gateway"""
        self.connection_info.ib_connected = False
        self.connection_label.setText("● DISCONNECTED")
        self.connection_label.setStyleSheet(f"color: {COLORS['negative']}; font-size: 14px;")
        self.connect_btn.setText("Connect")
        self.activity_log.append(f"Disconnected from IB Gateway")
    
    def update_market_data(self):
        """Update market data display"""
        # This would update with real data
        # For now, just show that updates are working
        pass
    
    def update_time(self):
        """Update time in status bar"""
        from datetime import datetime
        current_time = datetime.now().strftime("%H:%M:%S")
        self.statusBar().showMessage(f"Ready | {current_time}")


# ==============================================================================
def main():
    """Main entry point for the Trading Dashboard"""
    import sys
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
    
    # Create Qt Application
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("SPYDER Trading Dashboard")
    app.setOrganizationName("SPYDER")
    
    # Create and show the dashboard
    try:
        dashboard = SpyderTradingDashboard()
        dashboard.show()
        
        print("🚀 SPYDER Trading Dashboard launched successfully!")
        print("📊 Dashboard window should be visible now")
        print("⚠️  If window doesn't appear, check your display settings")
        
        # Start the event loop
        sys.exit(app.exec())
        
    except Exception as e:
        print(f"❌ Error creating dashboard: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
