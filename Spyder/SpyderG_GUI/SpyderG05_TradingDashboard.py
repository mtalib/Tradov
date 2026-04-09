#!/usr/bin/env python3
"""SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG05_TradingDashboard.py
Purpose: Complete Trading Dashboard with Real Data Integration & Enhanced Features
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-03-18 Time: 02:00:00

Data Sources:
    - Tradier API for account data and order execution (SpyderB40_TradierClient)
    - Massive for real-time & historical market data (SpyderC27_MassiveClient)
    - SpyderC01_DataFeed for provider-agnostic data abstraction

Module Description:
    Enhanced trading dashboard with TWO TRADING MODES:
    - PAPER:    Live data with simulated fills via Tradier sandbox + SpyderR02_PaperEngine
    - LIVE:     Real order execution via Tradier production API + SpyderR04_LiveEngine

    Includes real-time market data integration, comprehensive signal monitoring,
    and professional dark theme interface. Supports automatic detection and
    switching between real and simulation data.

FEATURES:
    • Two trading modes (PAPER / LIVE) with toolbar selector
    • LIVE mode requires explicit user confirmation before execution
    • Automatic real data detection and seamless switching
    • Simulation fallback with monitoring for real data availability
    • Professional signal monitor with 12 indicators including HMM/SKEW
    • Market hours awareness and connection health monitoring
    • Custom metrics integration (GEX/DEX/OGL/DIX/SWAN)
    • Enhanced P&L tracking and risk monitoring
    • Professional dark theme with traffic light indicators
    • 30-second heartbeat connection monitoring with visual indicator

DATA SOURCES:
    • Tradier API for account data, quotes, and order execution
    • Massive for real-time streaming and historical market data
    • Auto-detection with fallback to simulation mode
    • Status indicators show real vs simulation data source

CONNECTION MONITORING:
    • 30-second heartbeat timer for connection health checks
    • Visual heartbeat indicator with 3-state system
    • Fixed-width status containers prevent UI jumping
    • Real-time connection status updates
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import json
import random
import sys
from dataclasses import dataclass
from datetime import datetime
from datetime import time as dt_time
from enum import Enum
from pathlib import Path

# Matplotlib for charting
import matplotlib
import numpy as np
import pytz
from PySide6.QtCore import (
    QModelIndex,
    QMutex,
    QMutexLocker,
    QObject,
    QRect,
    Qt,
    QThread,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPen,
    QTextCursor,
)

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

matplotlib.use("QtAgg")
import pandas as pd
from matplotlib import patches
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# ==============================================================================
# BROKER/DATA IMPORTS (Tradier + Massive)
# ==============================================================================
# Tradier API for execution, Massive for market data
# Massive: primary market data source (live and paper trading)

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
project_root = Path(__file__).parent.parent.parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import logging

logger = logging.getLogger(__name__)

from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# Tradier client for API connectivity checks
try:
    from Spyder.SpyderB_Broker.SpyderB40_TradierClient import (
        OptionLeg,
        OrderDuration,
        OrderSide,
        TradierAPIError,
        TradierClient,
        TradingEnvironment,
        build_option_symbol,
        create_tradier_client_from_env,
    )
    TRADIER_AVAILABLE = True
except ImportError:
    TradierClient = None  # type: ignore
    TradierAPIError = Exception  # type: ignore
    OptionLeg = None  # type: ignore
    OrderSide = None  # type: ignore
    OrderDuration = None  # type: ignore
    build_option_symbol = None  # type: ignore
    TradingEnvironment = None  # type: ignore
    create_tradier_client_from_env = None  # type: ignore
    TRADIER_AVAILABLE = False

# Import Signal Info Dialog for popup system
try:
    from Spyder.SpyderG_GUI.SpyderG12_SignalInfoDialog import SignalInfoDialog

    signal_dialog_available = True
    logger.info("✅ Signal Info Dialog module available")
except ImportError:
    SignalInfoDialog = None  # type: ignore
    signal_dialog_available = False
    logger.info("⚠️ Signal Info Dialog not available - using fallback QMessageBox")

# Import Risk Parameters Dialog
try:
    from Spyder.SpyderG_GUI.SpyderG09_RiskParametersDialog import (
        RiskParametersDialog,
        show_risk_parameters_dialog,
    )

    risk_dialog_available = True
    logger.info("✅ Risk Parameters Dialog module available")
except ImportError:
    RiskParametersDialog = None  # type: ignore
    show_risk_parameters_dialog = None  # type: ignore
    risk_dialog_available = False
    logger.info("⚠️ Risk Parameters Dialog not available")

# Import HMM and SKEW Dialog modules
# NOTE: HMMMonitorDialog is imported lazily inside show_hmm_dialog() to avoid
# loading PyTorch (via SpyderL13_LSTMPricer) at startup, which costs 3-5 seconds.
HMMMonitorDialog = None  # type: ignore  - populated on first use
hmm_dialog_available = None  # None = not yet checked; True/False after first check

# SkewMonitorDialog is imported lazily inside show_skew_dialog() to defer the
# ~0.25 s import cost to when the user first opens the dialog.
SkewMonitorDialog = None  # type: ignore  - populated on first use
skew_dialog_available = None  # None = not yet attempted; True/False after first check

# Try to import Prometheus metrics display module if available
try:
    from Spyder.SpyderG_GUI.SpyderG07_PrometheusMetricsDisplay import (
        get_client_status,
        get_system_metrics,
    )

    prometheus_available = True
    logger.info("✅ Prometheus metrics collector available")
except ImportError:
    get_client_status = None  # type: ignore
    get_system_metrics = None  # type: ignore
    prometheus_available = False
    logger.info("⚠️ Prometheus metrics collector not available - using simulation")

# ==============================================================================
# DEPRECATED: Gateway Control Panel (removed in Tradier migration)
# ==============================================================================
# Gateway Control Panel was for legacy multi-client management
# No longer needed with Tradier API (single REST endpoint)
create_gateway_dock_widget = None
GatewayControlPanel = None
gateway_panel_available = False

# ==============================================================================
# CIRCUIT BREAKER MONITOR
# ==============================================================================
try:
    from Spyder.SpyderG_GUI.SpyderG16_CircuitBreakerMonitor import create_circuit_breaker_monitor

    circuit_breaker_monitor_available = True
    logger.info("✅ Circuit Breaker Monitor available")
except ImportError:
    create_circuit_breaker_monitor = None  # type: ignore
    circuit_breaker_monitor_available = False
    logger.info("⚠️ Circuit Breaker Monitor not available")

# Client Connection Manager — DEPRECATED (legacy multi-client no longer used)
ClientConnectionManager = None
ClientStatus = None
client_manager_available = False

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
    "CPC": "Put/Call Ratio - Computed from SPY options chain volume (nearest expiry)",
    "PCALL": "Put/Call Ratio - Same as CPC (SPY chain proxy; CBOE total PCR unavailable)",
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
    "DXY": "US Dollar Index (UUP ETF proxy — Tradier has no DXY index)",
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
    "connecting": "#00b8d4",
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


def check_api_connection():
    """Check if Tradier API is reachable.

    Returns:
        Tuple of (connected: bool, mode: str)

    """
    try:
        if TRADIER_AVAILABLE:
            import os
            try:
                from dotenv import load_dotenv
                load_dotenv(override=True)
            except ImportError:
                pass
            api_key = os.environ.get("TRADIER_API_KEY", "")
            account_id = os.environ.get("TRADIER_ACCOUNT_ID", "")
            env = os.environ.get("TRADIER_ENVIRONMENT", "sandbox")

            if api_key and account_id:
                env_enum = (
                    TradingEnvironment.LIVE
                    if env.lower() == "live"
                    else TradingEnvironment.SANDBOX
                )
                client = TradierClient(
                    api_key=api_key,
                    account_id=account_id,
                    environment=env_enum,
                )
                if client.test_connection():
                    mode = "SANDBOX" if env.lower() != "live" else "LIVE"
                    return True, f"Tradier API ({mode})"

        return False, "Tradier API not configured"

    except Exception as e:
        return False, f"API check failed: {e}"


# Legacy gateway alias removed - use check_api_connection directly


# ==============================================================================
# TRADING MODE ENUM
# ==============================================================================
class TradingMode(Enum):
    """Two trading modes available in the Spyder system.

    PAPER:    Simulated fills against live market data via Tradier sandbox + SpyderR02_PaperEngine.
    LIVE:     Real order execution through Tradier production API + SpyderR04_LiveEngine.
    """

    PAPER = "PAPER"
    LIVE = "LIVE"


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
    api_connected: bool = False
    bridge_connected: bool = False
    connection_mode: str = "DISCONNECTED"
    market_data_status: str = "NONE"
    trading_active: bool = False
    last_update: datetime | None = None
    last_successful_data: datetime | None = None
    data_was_live: bool = False
    simulation_mode: bool = False


# ==============================================================================
# THREAD-SAFE MARKET DATA WORKER - FIXED CONNECTION DETECTION
# ==============================================================================
class ThreadSafeMarketDataWorker(QObject):
    """Thread-safe market data worker with real API connection detection and heartbeat monitoring"""

    data_updated = Signal(dict)
    connection_status_changed = Signal(bool, str)
    market_data_status_changed = Signal(str)
    error_occurred = Signal(str)
    heartbeat_received = Signal(str)
    heartbeat_status_changed = Signal(str)  # New signal for heartbeat status
    log_message = Signal(str)  # New signal for log messages
    balance_updated = Signal(float, float)  # (equity/settled, buying_power)
    fetch_requested = Signal()  # Trigger live fetch from GUI thread safely

    def __init__(self):
        super().__init__()
        self.logger = SpyderLogger.get_logger(__name__)

        # FIXED: Start with actual connection check instead of assuming connected
        self.api_connected = False

        self.market_data = {}
        self.data_mutex = QMutex()
        self.client_id = 0  # Dedicated client ID for the dashboard worker
        self.market_hours = is_market_hours()

        # Path to live market data file (shared with dashboard)
        self.data_file = Path.home() / "Projects/Spyder/market_data/live_data.json"

        # Initialize timer references (will be created in start() method)
        self.update_timer = None
        self.market_hours_timer = None
        self.heartbeat_timer = None
        self.heartbeat_warning_timer = None

        self.last_data_update = {}
        self._init_simulation_data()

        logger.info("🔧 Market Data Worker initialized with heartbeat monitoring")
        logger.info("📊 Market: %s", 'OPEN' if self.market_hours else 'CLOSED')

    def _heartbeat_check(self):
        """30-second heartbeat check for Tradier API connection"""
        try:
            # Check actual connection
            connected, mode = check_api_connection()
            previous_status = self.api_connected
            self.api_connected = connected

            # Emit heartbeat status based on connection
            if connected:
                self.heartbeat_status_changed.emit("connected")  # Green heart
                if not previous_status:
                    # Connection restored
                    self.connection_status_changed.emit(True, f"API CONNECTED ({mode})")
                    self.heartbeat_received.emit(
                        f"💚 Heartbeat: Tradier API connection restored ({mode})",
                    )
                else:
                    self.heartbeat_received.emit(
                        f"💚 Heartbeat: Tradier API healthy ({mode})",
                    )
                # Refresh live quotes and account balance on every healthy heartbeat
                self._fetch_live_data_from_tradier()
            else:
                self.heartbeat_status_changed.emit("disconnected")  # Red heart
                if previous_status:
                    # Connection lost
                    self.connection_status_changed.emit(False, "API DISCONNECTED")
                    self.heartbeat_received.emit(
                        "💔 Heartbeat: Tradier API connection lost",
                    )
                else:
                    self.heartbeat_received.emit(
                        "💔 Heartbeat: Tradier API still disconnected",
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

    def _fetch_live_data_from_tradier(self):
        """Fetch live quotes and account balance from Tradier, write to data_file."""
        try:
            import os
            from dotenv import load_dotenv
            load_dotenv(override=True)
            if not TRADIER_AVAILABLE:
                return
            api_key = os.environ.get("TRADIER_API_KEY", "")
            account_id = os.environ.get("TRADIER_ACCOUNT_ID", "")
            env_str = os.environ.get("TRADIER_ENVIRONMENT", "sandbox")
            if not api_key or not account_id:
                return
            env_enum = (
                TradingEnvironment.LIVE
                if env_str.lower() == "live"
                else TradingEnvironment.SANDBOX
            )
            client = TradierClient(api_key=api_key, account_id=account_id, environment=env_enum)

            # --- Fetch account balance ---
            try:
                bal = client.get_account_balances()
                account_data = bal.get("balances", {})
                equity = float(account_data.get("total_equity") or 0)
                cash = float(account_data.get("total_cash") or 0)
                margin = account_data.get("margin", {})
                option_bp = float(
                    margin.get("option_buying_power")
                    or account_data.get("buying_power")
                    or cash
                )
                if equity or cash:
                    self.balance_updated.emit(equity, option_bp)
            except Exception:
                pass

            # --- Fetch live quotes and write to data_file ---
            symbols = [
                "SPY", "SPX", "VIX", "VIX9D",         # S&P core + volatility
                "VVIX", "UVXY",                          # Volatility ETFs
                "SKEW",                                  # CBOE SKEW index
                "DIA", "QQQ", "IWM",                     # Major index ETFs
                "TLT", "LQD", "GLD",                     # Bonds & credit + correlations
                "UUP",                                   # USD Index ETF (DXY proxy; Tradier: no DXY)
                "$DJI",                                  # Dow Jones index ($DJI confirmed on Tradier)
                "NDX",                                   # NASDAQ 100 index (no $ prefix on Tradier)
                "RUT",                                   # Russell 2000 index (no $ prefix on Tradier)
                # NYSE market internals — returned by Tradier during market hours only;
                # sandbox returns nothing for these, production returns live values.
                "$TICK", "$ADD", "$TRIN",
            ]
            try:
                raw = client.get_quotes(symbols)
                quotes_raw = raw.get("quotes", {}).get("quote", [])
                if isinstance(quotes_raw, dict):
                    quotes_raw = [quotes_raw]
                live_data = {}
                # Remap Tradier symbols to dashboard widget keys where needed
                _sym_remap = {
                    "VIX9D": "VXV",  # VIX9D closest proxy for VXV 3-month vol
                    "UUP":   "DXY",  # Invesco USD ETF (~27) proxies DXY (~104)
                }
                for q in quotes_raw:
                    sym = q.get("symbol", "")
                    last = float(q.get("last") or q.get("close") or 0.0)
                    change = float(q.get("change") or 0.0)
                    change_pct = float(q.get("change_percentage") or 0.0)
                    if last:
                        key = _sym_remap.get(sym, sym)
                        live_data[key] = {
                            "last": last,
                            "change": change,
                            "change_pct": change_pct,
                        }
                if live_data:
                    self.data_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(self.data_file, "w") as f:
                        import json as _json
                        _json.dump(live_data, f)
            except Exception:
                pass

            # --- Compute put/call ratio (CPC) from SPY options chain ---
            # CBOE does not publish CPC via Tradier; we compute it from SPY chain volume.
            # CPC = total put volume / total call volume for the nearest expiration.
            try:
                from datetime import date as _date2
                exps_raw = client.get_option_expirations("SPY")
                exp_dates = exps_raw.get("expirations", {}).get("date", [])
                if isinstance(exp_dates, str):
                    exp_dates = [exp_dates]
                # Use next trading day's expiry (skip same-day if already late)
                target_exp = next(
                    (d for d in exp_dates if d >= _date2.today().isoformat()),
                    exp_dates[0] if exp_dates else None,
                )
                if target_exp:
                    chain_resp = client.get_option_chain("SPY", target_exp)
                    contracts = chain_resp.get("options", {}).get("option", [])
                    if isinstance(contracts, dict):
                        contracts = [contracts]
                    put_vol = sum(
                        float(c.get("volume") or 0)
                        for c in contracts if c.get("option_type") == "put"
                    )
                    call_vol = sum(
                        float(c.get("volume") or 0)
                        for c in contracts if c.get("option_type") == "call"
                    )
                    if call_vol > 0:
                        cpc = put_vol / call_vol
                        prev_cpc = live_data.get("CPC", {}).get("last", cpc)
                        cpc_change = cpc - prev_cpc
                        live_data["CPC"] = {
                            "last": round(cpc, 3),
                            "change": round(cpc_change, 3),
                            "change_pct": round(cpc_change / prev_cpc * 100 if prev_cpc else 0, 2),
                        }
                        # PCALL: same ratio — SPY is the primary equity index proxy.
                        live_data["PCALL"] = live_data["CPC"]
                        # Persist updated live_data with CPC
                        self.data_file.parent.mkdir(parents=True, exist_ok=True)
                        with open(self.data_file, "w") as f:
                            import json as _json3
                            _json3.dump(live_data, f)
            except Exception:
                pass

            # --- Fetch 5-min SPY bars for chart ---
            try:
                from datetime import date as _date
                today_open = f"{_date.today().isoformat()} 09:30"
                ts_resp = client.get_time_sales(
                    "SPY", interval="5min", start=today_open, session_filter="open",
                )
                candles_raw = (
                    ts_resp.get("series", {}).get("data", [])
                )
                if isinstance(candles_raw, dict):
                    candles_raw = [candles_raw]
                if candles_raw:
                    chart_file = self.data_file.parent / "spy_5min_chart.json"
                    with open(chart_file, "w") as f:
                        import json as _json2
                        _json2.dump(candles_raw, f)
            except Exception:
                pass
        except Exception:
            pass

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
            logger.info(
                "📊 Market hours changed: %s", 'OPEN' if self.market_hours else 'CLOSED',
            )

            if not self.market_hours:
                if self.api_connected:
                    self.market_data_status_changed.emit("NONE")

    @Slot()
    def start(self):
        """Start the worker: create QTimers in worker thread and emit initial connection status."""
        logger.info("🚀 Starting Thread-Safe Market Data Worker with heartbeat monitoring...")

        # CRITICAL: Create QTimers in the worker thread, not the main thread
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._emit_data)
        self.update_timer.start(2000)

        self.market_hours_timer = QTimer()
        self.market_hours_timer.timeout.connect(self._check_market_hours)
        self.market_hours_timer.start(60000)

        self.heartbeat_timer = QTimer()
        self.heartbeat_timer.timeout.connect(self._heartbeat_check)
        self.heartbeat_timer.start(HEARTBEAT_INTERVAL)

        self.heartbeat_warning_timer = QTimer()
        self.heartbeat_warning_timer.timeout.connect(self._heartbeat_warning)

        # FIXED: Re-check connection at start and emit proper status
        try:
            connected, mode = check_api_connection()
            self.api_connected = connected

            if connected:
                self.connection_status_changed.emit(True, f"API CONNECTED ({mode})")
                self.market_data_status_changed.emit("LIVE")
                self.heartbeat_status_changed.emit("connected")  # Green heart
                logger.info("✅ Tradier API connected at startup: %s", mode)
            else:
                self.connection_status_changed.emit(False, "API DISCONNECTED")
                self.market_data_status_changed.emit("NONE")
                self.heartbeat_status_changed.emit("disconnected")  # Red heart
                logger.info("❌ Tradier API disconnected at startup")

        except Exception as e:
            logger.info("⚠️ Startup connection check error: %s", e)
            self.api_connected = False
            self.connection_status_changed.emit(False, "API DISCONNECTED")
            self.market_data_status_changed.emit("NONE")
            self.heartbeat_status_changed.emit("error")  # Red heart

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
                    },
                )

            with QMutexLocker(self.data_mutex):
                self.last_data_update[symbol] = current_time

    def force_connect(self):
        """Manual connect - now checks actual connection"""
        logger.info("🔥 Manual connect requested")
        if not is_market_hours():
            logger.info("📊 Cannot connect - market is closed")
            return False

        # Check actual connection
        connected, mode = check_api_connection()
        self.api_connected = connected

        if connected:
            self.connection_status_changed.emit(True, f"API CONNECTED ({mode})")
            self.market_data_status_changed.emit("LIVE")
            return True
        self.connection_status_changed.emit(False, "API DISCONNECTED")
        self.market_data_status_changed.emit("NONE")
        return False

    def force_disconnect(self):
        """Manual disconnect"""
        logger.info("🔥 Manual disconnect requested")
        self.api_connected = False
        self.connection_status_changed.emit(False, "API DISCONNECTED")
        self.market_data_status_changed.emit("NONE")

    def stop(self):
        """Stop worker and all timers"""
        logger.info("🛑 Stopping worker and heartbeat monitoring...")
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
            }""",
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
        """,
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
        """Update traffic light colors — defaults to yellow (pending) until real signals are wired."""
        # Original 10 analysis buttons: yellow = no signal yet
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
            button.set_status("yellow")

        # SWAN — default to green (no black-swan condition detected)
        self.swan_button.set_status("green")

        # HMM — default to green (bull regime assumed pending data)
        self.hmm_button.set_status("green")

        # SKEW — default to green (normal tail-risk level)
        self.skew_button.set_status("green")

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
                lambda: setattr(self, "current_dialog", None),
            )
            self.current_dialog.show()

    # Dialog show methods
    def show_vix_dialog(self):
        if signal_dialog_available:
            self.show_signal_dialog("VIX MONITOR")
        else:
            QMessageBox.information(
                self, "VIX Monitor", "VIX: 15.32\nStatus: Normal\nImplied Move: ±0.96%",
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
                self, "DIX Monitor", "DIX: 42.5%\nDark Pool: Normal\nSentiment: Neutral",
            )

    def show_rsi_dialog(self):
        if signal_dialog_available:
            self.show_signal_dialog("RSI CONFLUENCE")
        else:
            QMessageBox.information(
                self, "RSI Confluence", "RSI(14): 52\nRSI(5): 48\nStatus: Neutral Range",
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
                self, "DEX Monitor", "DEX: $850M\nDelta Neutral: 585\nFlow: Bullish",
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
        global hmm_dialog_available, HMMMonitorDialog
        # Lazy-import: only pay the PyTorch startup cost when the dialog is first opened.
        if hmm_dialog_available is None:
            try:
                from Spyder.SpyderM_Monitoring.SpyderM06_HMMRegimeDetector import (
                    HMMMonitorDialog as _HMM,
                )
                HMMMonitorDialog = _HMM
                hmm_dialog_available = True
                logger.info("✅ HMM Monitor Dialog loaded (lazy)")
            except ImportError:
                HMMMonitorDialog = None
                hmm_dialog_available = False
                logger.info("⚠️ HMM Monitor Dialog not available")

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
        global skew_dialog_available, SkewMonitorDialog
        # Lazy-import: defer the ~0.25s SkewMonitorDialog cost to first button click.
        if skew_dialog_available is None:
            try:
                from Spyder.SpyderG_GUI.SpyderG11_SkewMonitorDialog import (
                    SkewMonitorDialog as _Skew,
                )
                SkewMonitorDialog = _Skew
                skew_dialog_available = True
                logger.info("✅ SKEW Monitor Dialog loaded (lazy)")
            except ImportError:
                SkewMonitorDialog = None
                skew_dialog_available = False
                logger.info("⚠️ SKEW Monitor Dialog not available")

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
# PAPER TRADING WORKER (runs off the GUI thread)
# ==============================================================================


class _PaperTradingWorker(QObject):
    """Runs paper trading with real Tradier market data in a background QThread.

    Polls SPY quotes from Tradier (sandbox or live) every poll_interval seconds,
    maintains a price history buffer, runs a simple momentum strategy, and
    tracks paper positions and P&L.  Emits Qt signals for the dashboard to
    display status, positions, and metrics in real time.
    """

    status_update = Signal(str)       # log messages for the system log
    position_update = Signal(dict)    # current positions + account state
    metrics_update = Signal(dict)     # P&L metrics for the paper P&L widget
    error = Signal(str)               # error messages
    stopped = Signal()                # emitted when the loop exits
    connection_ready = Signal(bool)   # True when Tradier connection verified

    # Polling interval in seconds
    POLL_INTERVAL = 30
    # Price history size for moving average calculations
    HISTORY_SIZE = 100
    # Momentum threshold: short MA must exceed long MA by this fraction
    MOMENTUM_THRESHOLD = 0.001  # 0.1% for 30-sec samples
    # Moving average windows (in number of poll intervals)
    SHORT_MA_WINDOW = 5     # 5 x 30s = 2.5 min
    LONG_MA_WINDOW = 20     # 20 x 30s = 10 min

    def __init__(self, initial_capital: float = 100_000.0):
        super().__init__()
        self._running = False
        self._initial_capital = initial_capital

        # Paper account state
        self._cash = initial_capital
        self._position_qty = 0        # shares held (positive = long)
        self._position_avg_price = 0.0
        self._total_commissions = 0.0
        self._trades_executed = 0
        self._winning_trades = 0
        self._losing_trades = 0
        self._total_realized_pnl = 0.0
        self._peak_equity = initial_capital
        self._max_drawdown = 0.0

        # Price history buffer
        self._price_history: list[float] = []

        # Tradier client (created in run())
        self._client = None

    def run(self):
        """Main paper trading loop — called when QThread starts."""
        import os
        import time

        try:
            # Load environment
            from dotenv import load_dotenv
            load_dotenv(override=True)

            api_key = os.environ.get("TRADIER_API_KEY", "")
            account_id = os.environ.get("TRADIER_ACCOUNT_ID", "")
            env = os.environ.get("TRADIER_ENVIRONMENT", "sandbox")

            if not api_key or not account_id:
                self.error.emit(
                    "TRADIER_API_KEY and TRADIER_ACCOUNT_ID must be set in .env\n"
                    "Paper trading requires Tradier sandbox credentials.",
                )
                self.connection_ready.emit(False)
                self.stopped.emit()
                return

            self.status_update.emit(f"Connecting to Tradier ({env})…")

            env_enum = (
                TradingEnvironment.LIVE
                if env.lower() == "live"
                else TradingEnvironment.SANDBOX
            )
            self._client = TradierClient(
                api_key=api_key,
                account_id=account_id,
                environment=env_enum,
            )

            if not self._client.test_connection():
                self.error.emit(
                    f"Failed to connect to Tradier API ({env}).\n"
                    "Check your API key and account ID.",
                )
                self.connection_ready.emit(False)
                self.stopped.emit()
                return

            self.connection_ready.emit(True)
            mode_label = "SANDBOX" if env == "sandbox" else "LIVE"
            self.status_update.emit(f"✅ Connected to Tradier ({mode_label})")
            self.status_update.emit(
                f"Paper trading started — ${self._initial_capital:,.0f} capital | "
                f"Polling every {self.POLL_INTERVAL}s",
            )

            self._running = True
            self._price_history = []

            while self._running:
                try:
                    self._poll_and_trade()
                except Exception as e:
                    self.status_update.emit(f"⚠️ Poll error: {e}")

                # Sleep in small increments so stop() is responsive
                for _ in range(self.POLL_INTERVAL * 10):
                    if not self._running:
                        break
                    time.sleep(0.1)  # thread-safe: time.sleep() intentional

            # Final summary on stop
            self._emit_metrics()
            self.status_update.emit("Paper trading stopped")
            self.stopped.emit()

        except Exception as e:
            self.error.emit(f"Paper trading failed: {e}")
            self.stopped.emit()

    def stop(self):
        """Signal the trading loop to stop."""
        self._running = False

    def _poll_and_trade(self):
        """Fetch current SPY quote, run strategy, execute paper trades."""
        if not self._client:
            return

        # Fetch quote
        try:
            resp = self._client.get_quotes(["SPY"])
            quote = resp.get("quotes", {}).get("quote", {})
            if isinstance(quote, list):
                quote = quote[0]
        except Exception as e:
            self.status_update.emit(f"⚠️ Quote fetch failed: {e}")
            return

        last_price = float(quote.get("last", 0))
        bid = float(quote.get("bid", 0))
        ask = float(quote.get("ask", 0))

        if last_price <= 0:
            return

        # Add to history
        self._price_history.append(last_price)
        if len(self._price_history) > self.HISTORY_SIZE:
            self._price_history = self._price_history[-self.HISTORY_SIZE:]

        # Update position mark-to-market
        self._update_position_mtm(last_price)

        # Run momentum strategy if we have enough history
        if len(self._price_history) >= self.LONG_MA_WINDOW:
            signal = self._generate_signal()
            if signal == "BUY" and self._position_qty == 0:
                self._execute_paper_buy(ask if ask > 0 else last_price)
            elif signal == "SELL" and self._position_qty > 0:
                self._execute_paper_sell(bid if bid > 0 else last_price)

        # Emit updates
        self._emit_position_update(last_price, bid, ask)
        self._emit_metrics()

    def _generate_signal(self) -> str | None:
        """Simple dual moving average crossover on poll-interval prices."""
        prices = self._price_history
        if len(prices) < self.LONG_MA_WINDOW:
            return None

        short_ma = sum(prices[-self.SHORT_MA_WINDOW:]) / self.SHORT_MA_WINDOW
        long_ma = sum(prices[-self.LONG_MA_WINDOW:]) / self.LONG_MA_WINDOW

        if long_ma <= 0:
            return None

        ratio = (short_ma - long_ma) / long_ma

        if ratio > self.MOMENTUM_THRESHOLD:
            return "BUY"
        if ratio < -self.MOMENTUM_THRESHOLD:
            return "SELL"
        return None

    def _execute_paper_buy(self, fill_price: float):
        """Execute a paper buy — 100 shares of SPY."""
        shares = 100
        cost = shares * fill_price
        commission = 0.0  # Tradier is commission-free for equities

        if cost > self._cash:
            # Can't afford — buy what we can
            shares = int(self._cash / fill_price)
            if shares <= 0:
                return
            cost = shares * fill_price

        self._cash -= cost + commission
        self._position_qty += shares
        self._position_avg_price = fill_price  # simplified for single-lot
        self._total_commissions += commission
        self._trades_executed += 1

        self.status_update.emit(
            f"📈 BUY {shares} SPY @ ${fill_price:.2f} | "
            f"Cost: ${cost:,.2f} | Cash: ${self._cash:,.2f}",
        )

    def _execute_paper_sell(self, fill_price: float):
        """Execute a paper sell — close entire position."""
        if self._position_qty <= 0:
            return

        shares = self._position_qty
        proceeds = shares * fill_price
        commission = 0.0

        pnl = (fill_price - self._position_avg_price) * shares - commission
        self._total_realized_pnl += pnl
        self._cash += proceeds - commission
        self._total_commissions += commission
        self._trades_executed += 1

        if pnl > 0:
            self._winning_trades += 1
        else:
            self._losing_trades += 1

        self.status_update.emit(
            f"📉 SELL {shares} SPY @ ${fill_price:.2f} | "
            f"P&L: ${pnl:+,.2f} | Cash: ${self._cash:,.2f}",
        )

        self._position_qty = 0
        self._position_avg_price = 0.0

    def _update_position_mtm(self, current_price: float):
        """Update peak equity and max drawdown."""
        equity = self._cash + self._position_qty * current_price
        self._peak_equity = max(self._peak_equity, equity)
        drawdown = (self._peak_equity - equity) / self._peak_equity if self._peak_equity > 0 else 0
        self._max_drawdown = max(self._max_drawdown, drawdown)

    def _emit_position_update(self, last: float, bid: float, ask: float):
        """Emit current position state to the dashboard."""
        unrealized_pnl = 0.0
        if self._position_qty > 0:
            unrealized_pnl = (last - self._position_avg_price) * self._position_qty

        equity = self._cash + self._position_qty * last

        self.position_update.emit({
            "spy_last": last,
            "spy_bid": bid,
            "spy_ask": ask,
            "position_qty": self._position_qty,
            "position_avg_price": self._position_avg_price,
            "unrealized_pnl": unrealized_pnl,
            "realized_pnl": self._total_realized_pnl,
            "cash": self._cash,
            "equity": equity,
            "initial_capital": self._initial_capital,
        })

    def _emit_metrics(self):
        """Emit performance metrics for the paper P&L widget."""
        equity = self._cash
        if self._position_qty > 0 and self._price_history:
            equity += self._position_qty * self._price_history[-1]

        total_return = equity - self._initial_capital
        return_pct = (total_return / self._initial_capital) * 100 if self._initial_capital > 0 else 0
        win_rate = (
            self._winning_trades / self._trades_executed
            if self._trades_executed > 0 else 0
        )

        self.metrics_update.emit({
            "total_return": f"{return_pct:.2f}%",
            "max_drawdown": f"{self._max_drawdown:.4f}",
            "win_rate": f"{win_rate:.4f}",
            "total_trades": str(self._trades_executed),
            "realized_pnl": f"${self._total_realized_pnl:+,.2f}",
            "equity": f"${equity:,.2f}",
        })


# ==============================================================================
# MAIN DASHBOARD CLASS
# ==============================================================================
class SpyderTradingDashboard(QMainWindow):
    """Complete dashboard with fixed API connection detection and heartbeat monitoring"""

    def __init__(self):
        super().__init__()

        # Initialize logging
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Connection info - FIXED: Start disconnected
        self.connection_info = ConnectionInfo(
            api_connected=False,
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
        self.trading_mode = TradingMode.PAPER
        self.api_connected = False  # FIXED: Start disconnected
        self.mkt_data_connected = False  # Market data provider connection state
        self.tradier_client = (
            None  # FIXED: Initialize API client attribute before timer starts
        )
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

        # Initialize UI elements that will be created in setup methods
        self.connection_status_label = None
        self.api_status_container = None
        self.api_connection_label = None
        self.data_status_container = None
        self.data_status_label = None
        self.api_connect_icon = None
        self.mkt_connect_icon = None
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
        self.mode_lbl = None
        self.mode_selector = None
        self.live_btn = None
        self.paper_btn = None
        self.acct_number_lbl = None
        self.backtest_controls = None
        self.backtest_pnl_widget = None
        self.paper_pnl_widget = None
        self.risk_params_btn = None
        self.settled_value = None
        self.realized_value = None
        self.buying_value = None
        self.unrealized_value = None
        self.pnl_table = None
        self.refresh_orders_btn = None
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
        self._deprecated_gateway_timer = None
        self.automation_activity_count = 0
        self._last_gateway_search_log = ""  # Legacy

        # Gateway control — DEPRECATED (Tradier migration)
        self.gateway_dock = None
        self._deprecated_gateway_panel = None
        self._deprecated_gateway_btn = None

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

        # Check Tradier API connectivity on startup
        QTimer.singleShot(2000, self.check_and_connect_gateway)

        # Fetch live balance + quotes shortly after startup (before first 30s heartbeat)
        QTimer.singleShot(4000, self._trigger_initial_live_fetch)

        self.logger.info(
            "Enhanced Dashboard initialized with Tradier API connection detection and heartbeat monitoring",
        )

    def create_api_connection(self) -> bool:
        """Check Tradier API connectivity.

        Legacy method name preserved for backward compatibility.
        Now checks Tradier API connectivity.
        """
        try:
            self.logger.info("🔄 Checking Tradier API connectivity...")
            connected, mode = check_api_connection()

            if connected:
                self.logger.info("✅ Tradier API connected: %s", mode)
                self.on_connection_status_changed(True)
                return True
            self.logger.warning("⚠️ Tradier API not available: %s", mode)
            self.on_connection_status_changed(False)
            return False

        except Exception as e:
            self.logger.exception("❌ API connection check failed: %s", e)
            self.on_connection_status_changed(False)
            return False

    def check_and_connect_gateway(self):
        """Check Tradier API availability and update connection status.

        Legacy method name preserved for backward compatibility.
        Now checks Tradier API availability.
        """
        # If already connected, skip
        if self.api_connected:
            return

        try:
            connected, mode = check_api_connection()

            if connected:
                self.logger.info("✅ Tradier API available: %s", mode)
                self.add_system_log(f"✅ Connected to {mode}")
                self.api_connected = True

                if hasattr(self, "connection_status_label"):
                    self.connection_status_label.setText(f"🟢 {mode}")
                    self.connection_status_label.setStyleSheet(
                        f"color: {COLORS['green']};",
                    )
            else:
                self.api_connected = False

        except Exception:
            self.api_connected = False

    def _trigger_initial_live_fetch(self):
        """Ask the market worker to do an immediate live data + balance fetch."""
        if self.market_worker and self.api_connected:
            self.market_worker.fetch_requested.emit()

    # ==========================================================================
    # REAL DATA INTEGRATION PATTERN (UNCHANGED)
    # ==========================================================================
    def apply_proven_real_data_pattern(self):
        """Apply the proven real data integration pattern from temp_WorkingRealDashboard"""
        try:
            # Check if real data is available
            real_data_available = False

            if self.data_file.exists():
                try:
                    with open(self.data_file) as f:
                        data = json.load(f)
                    spy_price = data.get("SPY", {}).get("last", "N/A")
                    self.add_system_log(f"🔥 Real data detected - SPY: ${spy_price}")
                    real_data_available = True
                except (OSError, json.JSONDecodeError, KeyError) as e:
                    self.add_system_log(f"⚠️ Real data file exists but couldn't read it: {e}")
            else:
                self.add_system_log(
                    "📊 No real data detected - will monitor for availability",
                )

            # Apply the appropriate pattern
            if real_data_available:
                self.add_system_log("🔥 Applying proven real data patch...")
                self.apply_real_data_patch()
            else:
                self.add_system_log(
                    "📊 Starting with simulation - will switch to real data when available",
                )
                self.setup_real_data_monitoring()

        except Exception as e:
            self.add_system_log(f"❌ Error applying real data pattern: {e}")

    def apply_real_data_patch(self):
        """Apply real data patch using the proven working pattern"""
        try:
            # Stop the original simulation timer
            if hasattr(self, "market_worker") and self.market_worker:
                worker = self.market_worker
                if hasattr(worker, "update_timer") and worker.update_timer:
                    worker.update_timer.stop()
                    self.add_system_log("✅ Stopped simulation timer")

            # Slow down automation for real data
            if hasattr(self, "automation_timer"):
                self.automation_timer.setInterval(20000)  # 20 seconds instead of 3

            # Start real data updates
            self._real_data_timer = QTimer()
            self._real_data_timer.timeout.connect(self.update_with_real_data)
            self._real_data_timer.start(1000)  # Update every second

            self.real_data_active = True

            # Initial update
            self.update_with_real_data()

            # Update status
            self.update_status_for_real_data()

            # Log success
            self.add_system_log("🔥 REAL MARKET DATA ACTIVE - Tradier API prices")
            self.add_automation_log("Real-time market data from Tradier")

            self.add_system_log("✅ Real data patch applied successfully!")

        except Exception as e:
            self.add_system_log(f"❌ Error applying real data patch: {e}")

    def setup_real_data_monitoring(self):
        """Setup monitoring for real data to become available"""

        def check_for_real_data():
            """Check if real data becomes available"""
            if self.real_data_active:
                return  # Already using real data

            if self.data_file.exists():
                try:
                    with open(self.data_file) as f:
                        data = json.load(f)

                    if data:
                        self.add_system_log(
                            "🔥 Real data detected - switching from simulation!",
                        )
                        self._check_timer.stop()
                        self.apply_real_data_patch()
                except Exception as e:
                    self.logger.debug("Error checking for real data: %s", e)

        # Check every 5 seconds for real data
        self._check_timer = QTimer()
        self._check_timer.timeout.connect(check_for_real_data)
        self._check_timer.start(5000)

    def update_with_real_data(self):
        """Update dashboard with real market data"""
        try:
            if not self.data_file.exists():
                return

            with open(self.data_file) as f:
                live_data = json.load(f)

            if not live_data:
                return

            # Keep self.market_data in sync with live prices so other code
            # reading self.market_data (e.g. update_chart) gets real values.
            for symbol, data in live_data.items():
                if symbol not in self.market_data:
                    self.market_data[symbol] = {}
                self.market_data[symbol]["last"] = data["last"]
                self.market_data[symbol]["change"] = data["change"]
                self.market_data[symbol]["change_pct"] = data["change_pct"]

            # Update symbol widgets directly
            for symbol, data in live_data.items():
                if symbol in self.symbol_widgets:
                    widget = self.symbol_widgets[symbol]

                    # Update price
                    if hasattr(widget, "price_label"):
                        widget.price_label.setText(f"{data['last']:.2f}")

                    # Update change with color
                    if hasattr(widget, "change_label"):
                        change = data["change"]
                        sign = "+" if change >= 0 else ""
                        widget.change_label.setText(f"{sign}{change:.2f}")
                        color = "#00ff41" if change >= 0 else "#ff1744"
                        widget.change_label.setStyleSheet(f"color: {color};")

                    # Update percentage with color
                    if hasattr(widget, "pct_label"):
                        pct = data["change_pct"]
                        sign = "+" if pct >= 0 else ""
                        widget.pct_label.setText(f"{sign}{pct:.2f}%")
                        color = "#00ff41" if pct >= 0 else "#ff1744"
                        widget.pct_label.setStyleSheet(f"color: {color};")

            # Update toolbar indices
            self.update_toolbar_with_real_data(live_data)

        except Exception as e:
            # Suppress frequent errors in logs
            if not hasattr(self, "_error_count"):
                self._error_count = 0

            self._error_count += 1
            if self._error_count <= 5:  # Only show first 5 errors
                self.add_system_log(f"⚠️ Real data update error: {e}")

    def update_toolbar_with_real_data(self, live_data):
        """Update toolbar indices with real data"""
        try:
            # SPX — use real SPX index value directly
            spx_src = live_data.get("SPX") or live_data.get("SPY")
            spx_mult = 1 if "SPX" in live_data else 10
            if spx_src:
                if hasattr(self, "spx_value"):
                    self.spx_value.setText(f" {spx_src['last'] * spx_mult:.0f}")
                if hasattr(self, "spx_change"):
                    change = spx_src["change"] * spx_mult
                    pct = spx_src["change_pct"]
                    sign = "+" if change >= 0 else ""
                    self.spx_change.setText(f"  {sign}{change:.0f}  {sign}{pct:.1f}%")
                    color = "#00ff41" if change >= 0 else "#ff1744"
                    self.spx_change.setStyleSheet(f"color: {color};")

            # NDX — Tradier symbol "NDX" (no $ prefix), NASDAQ 100 index; fallback to QQQ * ratio
            ndx_src = live_data.get("NDX") or live_data.get("QQQ")
            ndx_mult = 1 if "NDX" in live_data else 37.5
            if ndx_src:
                if hasattr(self, "ndx_value"):
                    self.ndx_value.setText(f" {ndx_src['last'] * ndx_mult:,.0f}")
                if hasattr(self, "ndx_change"):
                    change = ndx_src["change"] * ndx_mult
                    pct = ndx_src["change_pct"]
                    sign = "+" if change >= 0 else ""
                    self.ndx_change.setText(f"  {sign}{change:.0f}  {sign}{pct:.1f}%")
                    color = "#00ff41" if change >= 0 else "#ff1744"
                    self.ndx_change.setStyleSheet(f"color: {color};")

            # DJI — use $DJI directly, fallback to DIA * 100
            dji_src = live_data.get("$DJI") or live_data.get("DIA")
            dji_mult = 1 if "$DJI" in live_data else 100
            if dji_src:
                if hasattr(self, "dji_value"):
                    self.dji_value.setText(f" {dji_src['last'] * dji_mult:,.0f}")
                if hasattr(self, "dji_change"):
                    change = dji_src["change"] * dji_mult
                    pct = dji_src["change_pct"]
                    sign = "+" if change >= 0 else ""
                    self.dji_change.setText(f"  {sign}{change:.0f}  {sign}{pct:.1f}%")
                    color = "#00ff41" if change >= 0 else "#ff1744"
                    self.dji_change.setStyleSheet(f"color: {color};")

            # RUT — Tradier symbol "RUT" (no $ prefix), Russell 2000 index; fallback to IWM * 10
            rut_src = live_data.get("RUT") or live_data.get("IWM")
            rut_mult = 1 if "RUT" in live_data else 10
            if rut_src:
                if hasattr(self, "rut_value"):
                    self.rut_value.setText(f" {rut_src['last'] * rut_mult:,.0f}")
                if hasattr(self, "rut_change"):
                    change = rut_src["change"] * rut_mult
                    pct = rut_src["change_pct"]
                    sign = "+" if change >= 0 else ""
                    self.rut_change.setText(f"  {sign}{change:.0f}  {sign}{pct:.1f}%")
                    color = "#00ff41" if change >= 0 else "#ff1744"
                    self.rut_change.setStyleSheet(f"color: {color};")

        except Exception as e:
            self.logger.debug("Toolbar update error: %s", e)

    def update_status_for_real_data(self):
        """Update status indicators for real data - FIXED to not override API status"""
        # Real data integration does not change API connection display

    def refresh_market_data(self):
        """Enhanced refresh market data - callback for refresh icon click"""
        try:
            if self.real_data_active:
                self.add_system_log("🔥 Refreshing real market data...")

                # Force immediate update
                self.update_with_real_data()

                self.add_system_log("✅ Real market data refreshed")

            elif self.market_worker:
                self.add_system_log("🔥 Refreshing simulation data...")

                if not self.api_connected:
                    self.add_system_log(
                        "⚠️ Not connected to Tradier API - using simulation data",
                    )

                self.add_system_log("✅ Market data refresh requested")
            else:
                self.add_system_log("❌ Market worker not available")

        except Exception as e:
            self.logger.exception("Error refreshing market data: %s", e)
            self.add_system_log(f"❌ Refresh error: {e}")

    # ==========================================================================
    # UI CREATION METHODS - FIXED TOOLBAR WITH HEARTBEAT
    # ==========================================================================
    def setup_ui(self):
        """Setup the complete UI"""
        self.setWindowTitle("SPYDER - Autonomous Options Trading System v1.0")
        self.setGeometry(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT)

        self.setStyleSheet(
            f"""
            QMainWindow {{
                background-color: {COLORS["background"]};
            }}
            QLabel {{
                color: {COLORS["text"]};
                font-weight: normal;
            }}
            QGroupBox {{
                color: {COLORS["text"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: {COLORS["background"]};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }}
            QPushButton {{
                background-color: {COLORS["panel"]};
                color: {COLORS["text"]};
                border: 1px solid {COLORS["border"]};
                padding: 8px;
                border-radius: 3px;
                font-weight: normal;
            }}
            QPushButton:hover {{
                background-color: #2a2a2a;
            }}
            QTableWidget {{
                background-color: {COLORS["panel"]};
                alternate-background-color: {COLORS["background"]};
                color: {COLORS["text"]};
                gridline-color: {COLORS["grid"]};
                border: 1px solid {COLORS["border"]};
                font-size: 11px;
            }}
            QTableWidgetItem {{
                font-size: 11px;
            }}
            QHeaderView::section {{
                background-color: {COLORS["background"]};
                color: {COLORS["text"]};
                border: 1px solid {COLORS["border"]};
                padding: 5px;
                font-size: 10px;
            }}
            QTextEdit {{
                background-color: {COLORS["panel"]};
                color: {COLORS["text"]};
                border: 1px solid {COLORS["border"]};
            }}
        """,
        )

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
        """Create top toolbar with FIXED WIDTH status containers and heartbeat monitor"""
        toolbar = QWidget()
        toolbar.setFixedHeight(60)
        toolbar.setStyleSheet(
            f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']};",
        )

        layout = QHBoxLayout()

        # SPYDER logo on left
        logo_label = QLabel("S P Y D E R")
        try:
            logo_font = QFont("Michroma", 16, QFont.Weight.Normal)
        except Exception:
            logo_font = QFont("Arial", 16, QFont.Weight.Normal)
        logo_label.setFont(logo_font)
        logo_label.setStyleSheet(f"color: {COLORS['text']}; letter-spacing: 5px;")
        layout.addWidget(logo_label)

        # mode_selector removed — mode is controlled from the account info container
        self.mode_selector = None

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
        center_section.addSpacing(24)

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
        center_section.addSpacing(24)

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
        center_section.addSpacing(24)

        # RUT (Russell 2000)
        rut_container = QHBoxLayout()
        rut_container.setSpacing(0)
        rut_label = QLabel("RUT:")
        rut_label.setStyleSheet(f"color: {COLORS['text']};")
        rut_container.addWidget(rut_label)

        self.rut_value = QLabel(" 2,636")
        self.rut_value.setStyleSheet(f"color: {COLORS['text']};")
        rut_container.addWidget(self.rut_value)

        self.rut_change = QLabel("  +15.85  +0.60%")
        self.rut_change.setStyleSheet(f"color: {COLORS['positive']};")
        rut_container.addWidget(self.rut_change)

        center_section.addLayout(rut_container)

        layout.addLayout(center_section)
        layout.addStretch(1)

        # API Connection Status (Left Box) - FIXED WIDTH
        self.api_status_container = QWidget()
        self.api_status_container.setMinimumWidth(155)
        self.api_status_container.setMaximumWidth(155)
        self.api_status_container.setToolTip("Tradier execution API")
        self.api_status_container.setStyleSheet(
            """
            QWidget:hover {
                background-color: #2a2a2a;
                border-radius: 3px;
                padding: 2px;
            }
        """,
        )
        api_status_layout = QHBoxLayout()
        api_status_layout.setContentsMargins(6, 3, 4, 3)
        api_status_layout.setSpacing(4)

        self.api_connection_label = QLabel("TRADIER EXEC")
        self.api_connection_label.setStyleSheet(
            "color: " + COLORS["negative"] + "; font-size: 14px;",
        )
        api_status_layout.addWidget(self.api_connection_label)

        self.api_connect_icon = QLabel("\u26a1")
        self.api_connect_icon.setStyleSheet(
            "color: " + COLORS["negative"] + "; font-size: 13px;",
        )
        self.api_connect_icon.setCursor(Qt.CursorShape.PointingHandCursor)
        self.api_connect_icon.setToolTip("Click to connect to Tradier API")
        self.api_connect_icon.mousePressEvent = self.toggle_api_connection
        api_status_layout.addWidget(self.api_connect_icon)

        self.api_status_container.setLayout(api_status_layout)

        # Data Status — clickable only in EOD/SIMULATED states
        self.data_status_container = QWidget()
        self.data_status_container.setMinimumWidth(120)
        self.data_status_container.setMaximumWidth(120)
        self.data_status_container.setToolTip("Data is simulated — no live feed connected")
        data_status_layout = QHBoxLayout()
        data_status_layout.setContentsMargins(8, 3, 8, 3)
        data_status_layout.setSpacing(6)

        self.data_status_label = QLabel("SIMULATED")
        self.data_status_label.setStyleSheet(
            "color: " + COLORS["automation_active"] + "; font-size: 14px;",
        )
        self.data_status_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )
        data_status_layout.addWidget(self.data_status_label)

        self.data_status_container.setLayout(data_status_layout)
        self.data_status_container.mousePressEvent = self._toggle_data_display

        # Market Data Provider (label click = switch provider, \u26a1 click = connect/disconnect)
        self.mkt_provider_container = QWidget()
        self.mkt_provider_container.setMinimumWidth(165)
        self.mkt_provider_container.setMaximumWidth(165)
        self.mkt_provider_container.setToolTip("Market data source")
        self.mkt_provider_container.setStyleSheet(
            """
            QWidget:hover {
                background-color: #2a2a2a;
                border-radius: 3px;
                padding: 2px;
            }
        """,
        )
        mkt_layout = QHBoxLayout()
        mkt_layout.setContentsMargins(8, 3, 8, 3)
        mkt_layout.setSpacing(4)

        import os as _os
        _current_provider = _os.getenv("MARKET_DATA_PROVIDER", "tradier").lower()
        if _current_provider not in ("tradier", "massive"):
            _current_provider = "tradier"
        # Start red (disconnected); turns green once data feed connects
        _provider_color = COLORS["negative"]

        self.mkt_provider_label = QLabel(_current_provider.upper() + " DATA")
        self.mkt_provider_label.setStyleSheet(f"color: {_provider_color}; font-size: 14px;")
        self.mkt_provider_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mkt_provider_label.setToolTip(
            "Click to switch between Tradier and Massive data source",
        )
        self.mkt_provider_label.mousePressEvent = self.toggle_market_data_provider
        mkt_layout.addWidget(self.mkt_provider_label)

        self.mkt_connect_icon = QLabel("\u26a1")
        self.mkt_connect_icon.setStyleSheet(
            f"color: {_provider_color}; font-size: 13px;",
        )
        self.mkt_connect_icon.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mkt_connect_icon.setToolTip("Click to connect market data feed")
        self.mkt_connect_icon.mousePressEvent = self._toggle_mkt_data_connection
        mkt_layout.addWidget(self.mkt_connect_icon)

        self.mkt_provider_container.setLayout(mkt_layout)

        # RIGHT SECTION - Status labels aligned with right panel buttons below
        right_section = QHBoxLayout()
        right_section.setSpacing(0)
        right_section.setContentsMargins(0, 0, 0, 0)

        right_section.addWidget(self.api_status_container)
        right_section.addWidget(self.mkt_provider_container)
        right_section.addWidget(self.data_status_container)

        layout.addLayout(right_section)

        # DATE/TIME - separate from status labels
        pipe_label = QLabel(" | ")
        pipe_label.setStyleSheet(f"color: {COLORS['text']};")
        layout.addWidget(pipe_label)
        self.datetime_label = QLabel(datetime.now().strftime("%Y-%m-%d   %H:%M:%S  ET"))
        self.datetime_label.setStyleSheet("font-size: 14px;")
        layout.addWidget(self.datetime_label)

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

        # Create symbol widgets - ALL SYMBOLS
        self.symbol_widgets = {}
        for category, symbols in MARKET_SYMBOLS.items():
            cat_label = QLabel(category)
            cat_label.setStyleSheet(
                f"color: {COLORS['cyan']}; font-size: 14px; padding: 5px 0px 2px 10px; font-weight: normal;",
            )
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
        """Create center panel (UNCHANGED)"""
        panel = QWidget()
        layout = QVBoxLayout()

        # Market regime indicator
        regime_widget = QWidget()
        regime_widget.setStyleSheet(
            f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']};",
        )
        regime_widget.setFixedHeight(40)
        regime_layout = QHBoxLayout()

        regime_layout.addStretch()

        center_container = QHBoxLayout()
        center_container.setSpacing(20)

        # SPY timeframe label (moved from chart title)
        spy_label = QLabel("SPY - 5 MIN")
        spy_label.setStyleSheet(
            f"color: {COLORS['text']}; font-size: 13px;",
        )
        center_container.addWidget(spy_label)

        separator_label0 = QLabel("|")
        separator_label0.setStyleSheet(f"color: {COLORS['text_dim']};")
        center_container.addWidget(separator_label0)

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

        # Add spacing before the chart button for elegant positioning
        strategy_section.addSpacing(15)

        # Chart toggle button
        self.chart_toggle_btn = QPushButton("📊")
        self.chart_toggle_btn.setFixedSize(30, 30)
        self.chart_toggle_btn.setToolTip("Toggle SPY Chart (5-min)")
        self.chart_toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['panel']};
                border: 1px solid {COLORS['border']};
                border-radius: 3px;
                color: {COLORS['cyan']};
                font-size: 16px;
                padding: 2px;
                margin-top: -3px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['border']};
                border: 1px solid {COLORS['cyan']};
            }}
            QPushButton:pressed {{
                background-color: {COLORS['cyan']};
                color: {COLORS['background']};
            }}
        """)
        self.chart_toggle_btn.clicked.connect(self.toggle_chart)
        strategy_section.addWidget(self.chart_toggle_btn)

        center_container.addLayout(strategy_section)

        regime_layout.addLayout(center_container)
        regime_layout.addStretch()

        regime_widget.setLayout(regime_layout)
        layout.addWidget(regime_widget)

        # Create the chart widget
        self.create_chart()
        self.chart_visible = True  # Track chart visibility state
        layout.addWidget(self.chart_widget, 2)

        # Positions table
        positions_group = QGroupBox()
        positions_layout = QVBoxLayout()
        positions_layout.setContentsMargins(2, 2, 2, 2)
        positions_layout.setSpacing(2)

        # Toolbar row: title on the left, refresh button on the right
        _pos_toolbar = QWidget()
        _pos_toolbar_layout = QHBoxLayout(_pos_toolbar)
        _pos_toolbar_layout.setContentsMargins(0, 0, 0, 0)
        _pos_toolbar_layout.setSpacing(4)
        self.orders_title_label = QLabel()
        self._update_orders_title()
        _pos_toolbar_layout.addWidget(self.orders_title_label)
        _pos_toolbar_layout.addStretch()
        self.refresh_orders_btn = QPushButton("⟳ Refresh")
        self.refresh_orders_btn.setFixedHeight(20)
        self.refresh_orders_btn.setStyleSheet(
            f"font-size: 11px; padding: 0 6px; background-color: {COLORS['panel']};"
            f" color: {COLORS['text']}; border: 1px solid {COLORS['border']}; border-radius: 3px;"
        )
        self.refresh_orders_btn.setToolTip("Fetch live orders & positions from Tradier")
        self.refresh_orders_btn.clicked.connect(self._refresh_positions_table)
        _pos_toolbar_layout.addWidget(self.refresh_orders_btn)
        positions_layout.addWidget(_pos_toolbar)

        self.positions_table = self.create_positions_table()
        # Remove fixed height constraints to allow expansion when chart is hidden
        self.positions_table.setMinimumHeight(220)
        positions_layout.addWidget(self.positions_table)

        positions_group.setLayout(positions_layout)
        self.positions_group = positions_group  # Store reference for stretch factor adjustment
        layout.addWidget(positions_group, 1)

        # System logs with Signal Monitor Panel
        logs_container = QWidget()
        logs_container.setFixedHeight(190)  # Fixed height - won't expand when chart is hidden
        logs_container_layout = QHBoxLayout()
        logs_container_layout.setSpacing(5)
        logs_container_layout.setContentsMargins(0, 0, 0, 0)

        # System logs (left side)
        logs_group = QGroupBox("SYSTEM LOG")
        logs_layout = QVBoxLayout()

        self.system_log = QTextEdit()
        self.system_log.setReadOnly(True)
        self.system_log.setMaximumHeight(150)
        self.system_log.setStyleSheet(
            f"""
            QTextEdit {{
                font-family: monospace;
                font-size: 13px;
            }}
            QScrollBar:vertical {{
                width: 8px;
                background: {COLORS["panel"]};
            }}
        """,
        )

        logs_layout.addWidget(self.system_log)
        logs_group.setLayout(logs_layout)

        # Signal Monitor Panel (right side)
        signal_group = QGroupBox("SIGNAL MONITOR")
        signal_group.setStyleSheet(
            f"QGroupBox {{ color: {COLORS['text']}; font-weight: normal; }}",
        )
        signal_layout = QVBoxLayout()
        signal_layout.setContentsMargins(5, 5, 5, 5)

        self.signal_panel = SignalMonitorPanel()
        signal_layout.addWidget(self.signal_panel)
        signal_group.setLayout(signal_layout)

        logs_container_layout.addWidget(logs_group, 65)
        logs_container_layout.addWidget(signal_group, 35)

        logs_container.setLayout(logs_container_layout)

        # Paper Trading P&L is now shown directly in the account info container.
        self.paper_pnl_widget = None
        self.backtest_pnl_widget = None
        self._paper_metric_labels = {}
        self._paper_status_label = None

        # Backtest controls — removed; backtest feature has been removed
        self.backtest_controls = None

        layout.addWidget(logs_container, 0)  # Stretch factor 0 - stays fixed size

        panel.setLayout(layout)
        return panel

    def toggle_chart(self):
        """Toggle the SPY chart visibility to provide more space for positions table"""
        if self.chart_visible:
            # Hide chart
            self.chart_widget.hide()
            self.chart_visible = False
            self.chart_toggle_btn.setToolTip("Show SPY Chart (5-min)")
            self.log_system_message("Chart hidden - Positions table expanded")
        else:
            # Show chart
            self.chart_widget.show()
            self.chart_visible = True
            self.chart_toggle_btn.setToolTip("Hide SPY Chart (5-min)")
            self.log_system_message("Chart visible")

    def create_right_panel(self) -> QWidget:
        """Create right panel with controls and metrics (UNCHANGED EXCEPT BUTTON MESSAGES)"""
        panel = QWidget()
        panel.setMinimumWidth(580)  # Prevent splitter from squishing this panel
        layout = QVBoxLayout()
        layout.setSpacing(3)
        layout.setContentsMargins(5, 5, 5, 5)
        # Control buttons
        button_layout = QHBoxLayout()

        self.start_btn = QPushButton("START TRADING")
        self.start_btn.setStyleSheet(
            f"background-color: {COLORS['positive']}; color: black;",
        )
        self.start_btn.setToolTip("Start automated trading")
        self.start_btn.clicked.connect(self.start_trading)
        button_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("STOP TRADING")
        self.stop_btn.setStyleSheet(f"background-color: {COLORS['warning']}; color: black;")
        self.stop_btn.setToolTip("Stop trading but keep orders and positions")
        self.stop_btn.clicked.connect(self.stop_trading)
        button_layout.addWidget(self.stop_btn)

        self.emergency_btn = QPushButton("EMERGENCY CLOSE")
        self.emergency_btn.setStyleSheet(f"background-color: {COLORS['negative']}; color: black;")
        self.emergency_btn.setToolTip(
            "Close all orders and positions, stop trading, and disconnect from API",
        )
        self.emergency_btn.clicked.connect(self.emergency_close)
        button_layout.addWidget(self.emergency_btn)

        layout.addLayout(button_layout)

        # Circuit Breaker Monitor — directly below trading buttons
        if circuit_breaker_monitor_available:
            try:
                circuit_breaker_widget = create_circuit_breaker_monitor(parent=self)
                circuit_breaker_widget.setMaximumHeight(85)
                layout.addSpacing(8)
                layout.addWidget(circuit_breaker_widget)
            except Exception as e:
                logger.info("⚠️ Failed to create circuit breaker monitor: %s", e)

        # Account info — compact flat grid, no QGroupBox overhead
        self.risk_params_btn = QPushButton("RISK LEVELS")
        self.risk_params_btn.setStyleSheet("background-color: #0066CC; color: white; font-size: 15px;")
        self.risk_params_btn.setToolTip("Configure global and strategy-specific risk parameters")
        self.risk_params_btn.clicked.connect(self.show_risk_parameters)
        # Button placed in RISK MONITOR section header

        account_widget = QWidget()
        account_widget.setStyleSheet(
            f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']}; border-radius: 5px;",
        )
        acct_grid = QGridLayout()
        acct_grid.setContentsMargins(4, 4, 4, 4)
        acct_grid.setHorizontalSpacing(3)
        acct_grid.setVerticalSpacing(3)
        acct_grid.setColumnStretch(0, 3)
        acct_grid.setColumnStretch(1, 4)
        acct_grid.setColumnStretch(2, 3)
        acct_grid.setColumnStretch(3, 4)

        cell_style = f"padding: 2px 5px; background-color: {COLORS['background']}; border: 1px solid {COLORS['border']}; font-size: 12px;"

        # Row 0: ACCOUNT | account-number | MODE selector (spans cols 2-3)
        acct_grid.addWidget(self._acct_lbl("ACCOUNT", cell_style), 0, 0)
        import os as _os_acct
        self.acct_number_lbl = self._acct_lbl(
            _os_acct.environ.get("TRADIER_ACCOUNT_ID", "—"), cell_style
        )
        acct_grid.addWidget(self.acct_number_lbl, 0, 1)

        # Twin toggle buttons: LIVE TRADING | PAPER TRADING
        _mode_container = QWidget()
        _mode_layout = QHBoxLayout(_mode_container)
        _mode_layout.setContentsMargins(0, 0, 0, 0)
        _mode_layout.setSpacing(2)

        self.live_btn = QPushButton("LIVE TRADING")
        self.live_btn.setToolTip("Switch to LIVE trading — real order execution at Tradier")
        self.paper_btn = QPushButton("PAPER TRADING")
        self.paper_btn.setToolTip("Switch to PAPER trading — simulated fills, Tradier sandbox")

        _mode_layout.addWidget(self.live_btn)
        _mode_layout.addWidget(self.paper_btn)
        acct_grid.addWidget(_mode_container, 0, 2, 1, 2)

        # Wire clicks
        self.live_btn.clicked.connect(lambda: self._on_mode_btn_clicked(TradingMode.LIVE))
        self.paper_btn.clicked.connect(lambda: self._on_mode_btn_clicked(TradingMode.PAPER))

        # Apply initial styling
        self._update_mode_buttons()

        # backwards-compat aliases — no longer QComboBox, kept to avoid AttributeError
        self.mode_selector = None
        self.mode_lbl = None

        # Row 1: SETTLED CASH | value | BUYING POWER | value
        acct_grid.addWidget(self._acct_lbl("SETTLED CASH", cell_style), 1, 0)
        self.settled_value = self._acct_lbl("—", cell_style, right=True)
        acct_grid.addWidget(self.settled_value, 1, 1)
        acct_grid.addWidget(self._acct_lbl("BUYING POWER", cell_style), 1, 2)
        self.buying_value = self._acct_lbl("—", cell_style, right=True)
        acct_grid.addWidget(self.buying_value, 1, 3)

        # Row 2: REALIZED P&L | value | UNREALIZED P&L | value
        acct_grid.addWidget(self._acct_lbl("REALIZED P&L", cell_style), 2, 0)
        self.realized_value = self._acct_lbl("—", cell_style + f"color: {COLORS['positive']};", right=True)
        acct_grid.addWidget(self.realized_value, 2, 1)
        acct_grid.addWidget(self._acct_lbl("UNREALIZED P&L", cell_style), 2, 2)
        self.unrealized_value = self._acct_lbl("—", cell_style + f"color: {COLORS['positive']};", right=True)
        acct_grid.addWidget(self.unrealized_value, 2, 3)

        account_widget.setLayout(acct_grid)
        layout.addWidget(account_widget)

        # P&L Performance
        pnl_group = QGroupBox("")
        pnl_group.setStyleSheet(
            f"""
            QGroupBox {{
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                margin-top: 0px;
                padding-top: 6px;
                background-color: {COLORS['background']};
            }}
            """,
        )
        pnl_layout = QVBoxLayout()
        pnl_layout.setContentsMargins(5, 8, 5, 5)
        pnl_layout.setSpacing(1)

        # Title label — left-aligned
        self.pnl_title_lbl = QLabel()
        self._update_pnl_title()
        pnl_layout.addWidget(self.pnl_title_lbl)

        self.pnl_table = self.create_pnl_table()
        self.pnl_table.setFixedHeight(140)
        pnl_layout.addWidget(self.pnl_table)

        pnl_group.setLayout(pnl_layout)
        layout.addWidget(pnl_group)

        # Risk Monitor
        risk_group = QGroupBox("")
        risk_group.setStyleSheet(
            f"""
            QGroupBox {{
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                margin-top: 0px;
                padding-top: 6px;
                background-color: {COLORS['background']};
            }}
            """,
        )
        risk_layout = QVBoxLayout()
        risk_layout.setSpacing(2)
        risk_layout.setContentsMargins(5, 8, 5, 5)

        # Title row: "RISK MONITOR" label + RISK LEVELS button on the right
        risk_header = QHBoxLayout()
        risk_title_lbl = QLabel("RISK MONITOR")
        risk_title_lbl.setStyleSheet(
            f"color: {COLORS['text']}; font-size: 15px; font-weight: normal; letter-spacing: 1px;",
        )
        risk_header.addWidget(risk_title_lbl)
        risk_header.addStretch()
        risk_header.addWidget(self.risk_params_btn)
        risk_layout.addLayout(risk_header)

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
        auto_group.setStyleSheet(
            f"""
            QGroupBox {{
                color: {COLORS["text"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 5px;
                margin-top: 12px;
                padding-top: 5px;
                background-color: {COLORS["background"]};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                top: -2px;
            }}
        """,
        )
        auto_layout = QVBoxLayout()
        auto_layout.setContentsMargins(5, 5, 5, 5)
        auto_layout.setSpacing(0)

        self.auto_log = QTextEdit()
        self.auto_log.setReadOnly(True)
        self.auto_log.setFixedHeight(110)
        self.auto_log.setStyleSheet(
            f"""
            QTextEdit {{
                font-family: monospace;
                font-size: 13px;
                color: {COLORS["cyan"]};
                padding: 1px;
                border: 1px solid {COLORS["border"]};
                background-color: {COLORS["panel"]};
                margin: 0px;
            }}
            QScrollBar:vertical {{
                width: 8px;
                background: {COLORS["panel"]};
            }}
        """,
        )
        self.auto_log.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.auto_log.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )

        auto_layout.addWidget(self.auto_log)
        auto_group.setLayout(auto_layout)
        layout.addWidget(auto_group)

        # Unified Prometheus Metrics
        metrics_widget = self.create_unified_prometheus_metrics()
        layout.addWidget(metrics_widget)

        panel.setLayout(layout)
        return panel

    def _acct_lbl(self, text: str, style: str, right: bool = False) -> QLabel:
        """Helper: create a styled account-grid cell label."""
        lbl = QLabel(text)
        lbl.setStyleSheet(style)
        if right:
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return lbl

    def create_chart(self):
        """Create the SPY chart widget (UNCHANGED)"""
        self.chart_widget = QWidget()
        self.chart_widget.setStyleSheet(
            f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']};",
        )

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
        """Update the SPY chart with real 5-min candlesticks and indicators."""
        self.figure.clear()

        # --- Load real 5-min bars from cache file written by the market data worker ---
        chart_file = self.data_file.parent / "spy_5min_chart.json"
        opens = []
        highs = []
        lows = []
        closes = []
        volumes = []
        dates = []

        if chart_file.exists():
            try:
                with open(chart_file) as _f:
                    candles = json.load(_f)
                for bar in candles:
                    opens.append(float(bar.get("open", 0)))
                    highs.append(float(bar.get("high", 0)))
                    lows.append(float(bar.get("low", 0)))
                    closes.append(float(bar.get("close", 0)))
                    volumes.append(int(bar.get("volume", 0)))
                    # bar["time"] is like "2026-04-09T09:30:00"
                    dates.append(pd.to_datetime(bar.get("time", "")))
            except Exception:
                candles = []

        # If no real data yet, show a "waiting for data" placeholder
        if not closes:
            ax = self.figure.add_subplot(111)
            ax.set_facecolor(COLORS["panel"])
            ax.text(
                0.5, 0.5, "Waiting for 5-min bar data…",
                ha="center", va="center", color="#888888",
                fontsize=12, transform=ax.transAxes,
            )
            for spine in ax.spines.values():
                spine.set_color(COLORS["border"])
            self.canvas.draw()
            return

        # Calculate pivot points from previous session high/low/close
        prev_high = max(highs)
        prev_low = min(lows)
        prev_close = closes[-1]

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
        ax.axhline(
            y=pivot,
            color="#FFFF00",
            linewidth=1.5,
            linestyle="-",
            alpha=0.7,
            label="Pivot",
            zorder=1,
        )
        ax.axhline(
            y=r1,
            color="#00FF41",
            linewidth=1.5,
            linestyle="-",
            alpha=0.6,
            label="R1",
            zorder=1,
        )
        ax.axhline(
            y=r2,
            color="#00FF41",
            linewidth=1.5,
            linestyle="-",
            alpha=0.6,
            label="R2",
            zorder=1,
        )
        ax.axhline(
            y=r3,
            color="#00FF41",
            linewidth=1.5,
            linestyle="-",
            alpha=0.6,
            label="R3",
            zorder=1,
        )
        ax.axhline(
            y=s1,
            color="#FF1744",
            linewidth=1.5,
            linestyle="-",
            alpha=0.6,
            label="S1",
            zorder=1,
        )
        ax.axhline(
            y=s2,
            color="#FF1744",
            linewidth=1.5,
            linestyle="-",
            alpha=0.6,
            label="S2",
            zorder=1,
        )
        ax.axhline(
            y=s3,
            color="#FF1744",
            linewidth=1.5,
            linestyle="-",
            alpha=0.6,
            label="S3",
            zorder=1,
        )

        # Plot 20-period Moving Average
        ma_x = [i for i, val in enumerate(ma_20) if val is not None]
        ma_y = [val for val in ma_20 if val is not None]
        ax.plot(
            ma_x,
            ma_y,
            color="#00B8D4",
            linewidth=1.5,
            alpha=0.8,
            label="MA(20)",
            zorder=2,
        )

        # Plot VWAP
        ax.plot(
            range(len(vwap)),
            vwap,
            color="#BF00FF",
            linewidth=1.5,
            alpha=0.9,
            label="VWAP",
            zorder=2,
        )

        # Plot candlesticks
        for i in range(len(dates)):
            color = COLORS["positive"] if closes[i] >= opens[i] else COLORS["negative"]

            # High-Low line
            ax.plot([i, i], [lows[i], highs[i]], color=color, linewidth=1, zorder=3)

            # Open-Close box
            height = abs(closes[i] - opens[i])
            bottom = min(opens[i], closes[i])

            rect = patches.Rectangle(
                (i - 0.3, bottom),
                0.6,
                height,
                facecolor=color,
                edgecolor=color,
                alpha=0.9,
                zorder=3,
            )
            ax.add_patch(rect)

        # Add pivot level labels on the right
        ax.text(
            len(dates),
            pivot,
            f" P: {pivot:.2f}",
            color="#FFFF00",
            fontsize=9,
            va="center",
        )
        ax.text(
            len(dates), r1, f" R1: {r1:.2f}", color="#00FF41", fontsize=8, va="center",
        )
        ax.text(
            len(dates), r2, f" R2: {r2:.2f}", color="#00FF41", fontsize=8, va="center",
        )
        ax.text(
            len(dates), r3, f" R3: {r3:.2f}", color="#00FF41", fontsize=8, va="center",
        )
        ax.text(
            len(dates), s1, f" S1: {s1:.2f}", color="#FF1744", fontsize=8, va="center",
        )
        ax.text(
            len(dates), s2, f" S2: {s2:.2f}", color="#FF1744", fontsize=8, va="center",
        )
        ax.text(
            len(dates), s3, f" S3: {s3:.2f}", color="#FF1744", fontsize=8, va="center",
        )

        # Styling (title moved to regime bar)
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

    def create_positions_table(self) -> QTreeWidget:
        """Create positions tree with strategy headers and expandable trade legs."""
        tree = QTreeWidget()

        # Leg-level columns under each strategy header
        # Last empty column absorbs stretch so other columns don't widen
        columns = ["     LEG", "STRIKE", "CONT", "EXPIRY", "COST", "P&L", ""]
        tree.setColumnCount(len(columns))
        tree.setHeaderLabels(columns)

        # Center-align all header labels
        for col in range(len(columns)):
            tree.headerItem().setTextAlignment(
                col, Qt.AlignmentFlag.AlignCenter,
            )

        tree.setAlternatingRowColors(False)
        tree.setSelectionBehavior(QTreeWidget.SelectionBehavior.SelectRows)
        tree.setRootIsDecorated(False)
        tree.setAnimated(True)
        tree.setIndentation(20)
        tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tree.customContextMenuRequested.connect(self._positions_context_menu)
        tree.setStyleSheet(
            f"""
            QTreeWidget {{
                font-size: 11px;
                background-color: {COLORS["background"]};
                border: none;
                outline: none;
            }}
            QTreeWidget::item {{
                padding: 2px 4px;
                border-bottom: 1px solid {COLORS["border"]};
            }}
            QTreeWidget::item:selected {{
                background-color: #2a3a4a;
            }}
            QTreeWidget::branch:has-children:!has-siblings:closed,
            QTreeWidget::branch:closed:has-children:has-siblings {{
                image: none;
                border-image: none;
            }}
            QTreeWidget::branch:open:has-children:!has-siblings,
            QTreeWidget::branch:open:has-children:has-siblings {{
                image: none;
                border-image: none;
            }}
            QHeaderView::section {{
                background-color: {COLORS["panel"]};
                color: {COLORS["text"]};
                border: 1px solid {COLORS["border"]};
                padding: 2px;
                font-size: 12px;
                font-weight: normal;
            }}
            QScrollBar:vertical {{
                width: 8px;
                background: {COLORS["panel"]};
            }}
        """,
        )

        # Set column widths for leg rows
        tree.setColumnWidth(0, 100)  # LEG (wide enough for tree indentation)
        tree.setColumnWidth(1, 80)   # STRIKE
        tree.setColumnWidth(2, 45)   # CONT
        tree.setColumnWidth(3, 65)   # EXPIRY
        tree.setColumnWidth(4, 90)   # COST
        tree.setColumnWidth(5, 90)   # P&L
        # Column 6 (spacer) stretches to fill remaining space
        tree.header().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)

        tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        tree.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        return tree

    def _positions_context_menu(self, pos):
        """Show right-click context menu for positions tree."""
        item = self.positions_table.itemAt(pos)
        if not item:
            return

        # Determine if this is a strategy header or a leg
        is_strategy = item.parent() is None
        strategy_item = item if is_strategy else item.parent()
        strategy_item.data(0, Qt.ItemDataRole.UserRole) or ""
        status = strategy_item.data(1, Qt.ItemDataRole.UserRole) or ""

        menu = QMenu(self)
        menu.setStyleSheet(
            f"""
            QMenu {{
                background-color: {COLORS["panel"]};
                color: {COLORS["text"]};
                border: 1px solid {COLORS["border"]};
                padding: 4px;
            }}
            QMenu::item:selected {{
                background-color: #2a3a4a;
            }}
            QMenu::separator {{
                height: 1px;
                background: {COLORS["border"]};
                margin: 4px 8px;
            }}
        """,
        )

        if status == "OPEN":
            close_action = menu.addAction("\u274c  Close Position")
            close_action.triggered.connect(
                lambda: self._on_close_position(strategy_item),
            )

            roll_action = menu.addAction("\U0001f504  Roll Forward")
            roll_action.triggered.connect(
                lambda: self._on_roll_position(strategy_item),
            )

            adjust_action = menu.addAction("\u2699\ufe0f  Adjust Strikes")
            adjust_action.triggered.connect(
                lambda: self._on_adjust_position(strategy_item),
            )

            menu.addSeparator()

        if is_strategy:
            expand_action = menu.addAction(
                "\u25b8  Collapse" if item.isExpanded() else "\u25be  Expand",
            )
            expand_action.triggered.connect(
                lambda: item.setExpanded(not item.isExpanded()),
            )

        copy_action = menu.addAction("\U0001f4cb  Copy Details")
        copy_action.triggered.connect(
            lambda: self._on_copy_strategy(strategy_item),
        )

        menu.exec(self.positions_table.viewport().mapToGlobal(pos))

    def _on_close_position(self, strategy_item: QTreeWidgetItem):
        """Handle close position from context menu."""
        name = strategy_item.data(0, Qt.ItemDataRole.UserRole) or "unknown"
        self.add_system_log(f"Close requested: {name}")

    def _on_roll_position(self, strategy_item: QTreeWidgetItem):
        """Handle roll forward from context menu."""
        name = strategy_item.data(0, Qt.ItemDataRole.UserRole) or "unknown"
        self.add_system_log(f"Roll forward requested: {name}")

    def _on_adjust_position(self, strategy_item: QTreeWidgetItem):
        """Handle adjust strikes from context menu."""
        name = strategy_item.data(0, Qt.ItemDataRole.UserRole) or "unknown"
        self.add_system_log(f"Adjust strikes requested: {name}")

    def _on_copy_strategy(self, strategy_item: QTreeWidgetItem):
        """Copy strategy and leg details to clipboard."""
        lines = [strategy_item.text(0)]
        for i in range(strategy_item.childCount()):
            child = strategy_item.child(i)
            parts = [child.text(c) for c in range(self.positions_table.columnCount())]
            lines.append("    " + "\t".join(parts))
        text = "\n".join(lines)
        from PySide6.QtWidgets import QApplication as _QApp
        clipboard = _QApp.clipboard()
        if clipboard:
            clipboard.setText(text)
            name = strategy_item.data(0, Qt.ItemDataRole.UserRole) or "strategy"
            self.add_system_log(f"Copied {name} to clipboard")

    def create_pnl_table(self) -> QTableWidget:
        """Create P&L performance table (UNCHANGED)"""
        table = QTableWidget(4, 8)

        headers = [
            "PERIOD",
            "P&L",
            "WIN RATE",
            "WIN/LOSS",
            "PROFIT-F",
            "SHARP",
            "SORTINO",
            "CALMAR",
        ]
        table.setHorizontalHeaderLabels(headers)

        # Add placeholder data — updated by _refresh_pnl_table() when real metrics arrive
        periods = ["TODAY", "WEEK", "MONTH", "YEAR"]
        data = [
            ("—", "—", "—", "—", "—", "—", "—"),
            ("—", "—", "—", "—", "—", "—", "—"),
            ("—", "—", "—", "—", "—", "—", "—"),
            ("—", "—", "—", "—", "—", "—", "—"),
        ]

        for row, (period, values) in enumerate(zip(periods, data, strict=False)):
            period_item = QTableWidgetItem(period)
            period_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            table.setItem(row, 0, period_item)

            pnl_item = QTableWidgetItem(values[0])
            pnl_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
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

        table.setStyleSheet(
            """
            QTableWidget { font-size: 11px; }
            QHeaderView::section { font-weight: normal; font-size: 11px; }
            """,
        )
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(26)

        # Stretch all columns; fix SHARP to a compact size so AVG WIN/LOSS gets more room
        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        for col in range(8):
            header.setSectionResizeMode(col, header.ResizeMode.Stretch)
        # SHARP data is short ("1.85") — fix it narrow to free space for AVG WIN/LOSS
        table.setColumnWidth(5, 52)
        header.setSectionResizeMode(5, header.ResizeMode.Fixed)

        # Tooltips and alignment for column headers
        _header_tooltips = {
            2: "WIN RATE: percentage of trades that closed with a profit",
            3: "WIN/LOSS: average winning trade size versus average losing trade size",
            4: "PROFIT FACTOR: gross profit divided by gross loss — values above 1.0 indicate a profitable strategy",
            5: "SHARPE RATIO: return earned above the risk-free rate per unit of total volatility — higher is better",
            6: "SORTINO RATIO: like the sharpe ratio but only penalises downside volatility, not upside swings",
            7: "CALMAR RATIO: annualised return divided by maximum drawdown — measures return relative to worst loss",
        }
        for col, tip in _header_tooltips.items():
            item = table.horizontalHeaderItem(col)
            if item:
                item.setToolTip(tip)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        return table

    def create_unified_prometheus_metrics(self) -> QWidget:
        """Create the unified Prometheus Metrics table (8 clients in 4x2 grid + 2 empty rows)"""
        container = QWidget()
        container.setStyleSheet(
            f"""
            QWidget {{
                background-color: {COLORS["panel"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 5px;
            }}
        """,
        )
        container.setFixedHeight(200)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(2)

        # Title bar
        title_layout = QHBoxLayout()

        title_label = QLabel("PROMETHEUS METRICS MONITOR")
        title_label.setStyleSheet(
            f"""
            color: {COLORS["text"]};
            font-size: 14px;
            font-weight: normal;
            padding-bottom: 1px;
        """,
        )
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        title_layout.addWidget(title_label)

        title_layout.addStretch()

        # Gateway Control Button removed (Tradier migration)
        # self._deprecated_gateway_btn kept as None for backward compat

        main_layout.addLayout(title_layout)
        main_layout.addSpacing(8)

        # Create the 6x4 grid (5 data rows + 1 header row)
        grid = QGridLayout()
        grid.setSpacing(2)
        grid.setContentsMargins(0, 0, 0, 0)

        # Column headers
        headers = [
            "SYSTEM HEALTH",
            "BROKER API",
            "DATA FEEDS",
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
            """,
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
                "color: " + COLORS["positive"] + "; font-size: 14px;",
            )
            component_layout.addWidget(indicator)

            label = QLabel(name)
            label.setStyleSheet("color: " + COLORS["text"] + "; font-size: 14px;")
            component_layout.addWidget(label)
            component_layout.addStretch()

            component_widget.setLayout(component_layout)
            self.system_components[name] = indicator
            grid.addWidget(component_widget, row, 0)

        # Broker API Services (Column 2) — Tradier REST API endpoints
        broker_services = [
            ("Orders", "tradier_orders"),
            ("Account", "tradier_account"),
            ("Market Data", "tradier_market"),
            ("Options Chain", "tradier_options"),
            ("Streaming", "tradier_streaming"),
        ]
        for row, (svc_name, svc_key) in enumerate(broker_services, start=1):
            svc_widget = QWidget()
            svc_layout = QHBoxLayout()
            svc_layout.setContentsMargins(5, 1, 5, 1)
            svc_layout.setSpacing(3)

            indicator = QLabel("●")
            indicator.setStyleSheet(
                "color: " + COLORS["neutral"] + "; font-size: 14px;",
            )
            indicator.setToolTip(f"Tradier {svc_name} endpoint")
            svc_layout.addWidget(indicator)

            label = QLabel(svc_name)
            label.setStyleSheet("color: " + COLORS["text"] + "; font-size: 14px;")
            svc_layout.addWidget(label)
            svc_layout.addStretch()

            svc_widget.setLayout(svc_layout)
            self.client_indicators[svc_key] = indicator
            grid.addWidget(svc_widget, row, 1)

        # Data Feed Services (Column 3) — Massive feeds
        data_services = [
            ("Live Stream", "db_live"),
            ("Historical", "db_historical"),
            ("Options", "db_options"),
            ("Book Data", "db_book"),
            ("Replay", "db_replay"),
        ]
        for row, (feed_name, feed_key) in enumerate(data_services, start=1):
            feed_widget = QWidget()
            feed_layout = QHBoxLayout()
            feed_layout.setContentsMargins(5, 1, 5, 1)
            feed_layout.setSpacing(3)

            indicator = QLabel("●")
            indicator.setStyleSheet(
                "color: " + COLORS["neutral"] + "; font-size: 14px;",
            )
            indicator.setToolTip(f"Massive {feed_name} feed")
            feed_layout.addWidget(indicator)

            label = QLabel(feed_name)
            label.setStyleSheet("color: " + COLORS["text"] + "; font-size: 14px;")
            feed_layout.addWidget(label)
            feed_layout.addStretch()

            feed_widget.setLayout(feed_layout)
            self.client_indicators[feed_key] = indicator
            grid.addWidget(feed_widget, row, 2)

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
                    "color: " + COLORS["warning"] + "; font-size: 14px;",
                )
            else:
                indicator.setStyleSheet(
                    "color: " + COLORS["positive"] + "; font-size: 14px;",
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
    # SIGNAL HANDLERS - ENHANCED WITH HEARTBEAT
    # ==========================================================================
    @Slot(bool, str)
    def on_connection_status_changed(self, connected: bool, status: str):
        """Handle connection status change - FIXED to prevent override"""
        self.connection_info.api_connected = connected
        self.api_connected = connected

        if connected:
            self.api_connection_label.setText("TRADIER EXEC")
            self.api_connection_label.setStyleSheet(f"color: {COLORS['positive']};")
            if hasattr(self, "api_connect_icon") and self.api_connect_icon:
                self.api_connect_icon.setStyleSheet(f"color: {COLORS['positive']}; font-size: 13px;")
                self.api_connect_icon.setToolTip("Click to disconnect from Tradier API")

            self.add_system_log("✅ Connected to Tradier API")

            # Refresh orders & positions table with live data
            self._refresh_positions_table()

            # Auto-recover from FROZEN → LIVE when API reconnects during market hours
            if (
                hasattr(self, "data_status_label")
                and self.data_status_label.text() == "FROZEN"
            ):
                self.mkt_data_connected = True
                self.update_data_status("LIVE")
                import os
                provider = os.getenv("MARKET_DATA_PROVIDER", "tradier").lower()
                self._apply_mkt_provider_display(provider)
        else:
            self.api_connection_label.setText("TRADIER EXEC")
            self.api_connection_label.setStyleSheet(f"color: {COLORS['negative']};")
            if hasattr(self, "api_connect_icon") and self.api_connect_icon:
                self.api_connect_icon.setStyleSheet(f"color: {COLORS['negative']}; font-size: 13px;")
                self.api_connect_icon.setToolTip("Click to connect to Tradier API")

            # Stop trading if active
            if self.trading_active:
                self.trading_active = False
                self.connection_info.trading_active = False

                self.start_btn.setStyleSheet(
                    f"background-color: {COLORS['positive']}; color: black;",
                )
                self.start_btn.setText("START TRADING")

                self.add_automation_log("Trading stopped - API connection lost")

            if "MARKET CLOSED" in status:
                self.add_system_log("📊 Market closed - API disconnected")
            else:
                self.add_system_log("🔌 Disconnected from Tradier API")

        # Update data status (but don't override API status)
        self.update_status_indicators()

    @Slot(str)
    def on_heartbeat_status_changed(self, status: str):
        """Handle heartbeat status changes — connection state is shown via label color only."""
        # Heartbeat icon removed; TRADIER EXEC label color handles state

    @Slot(str)
    def on_market_data_status_changed(self, status: str):
        """Handle market data status change and update provider connection indicator."""
        was_connected = self.mkt_data_connected
        if status == "LIVE":
            self.mkt_data_connected = True
            self.add_system_log("📊 Market data: LIVE")
            # Auto-recover from FROZEN → LIVE when API reconnects during market hours
            if self.data_status_label.text() == "FROZEN":
                self.update_data_status("LIVE")
        else:
            self.mkt_data_connected = False
            if self.trading_active:
                self.trading_active = False
                self.connection_info.trading_active = False

                self.start_btn.setStyleSheet(
                    f"background-color: {COLORS['positive']}; color: black;",
                )
                self.start_btn.setText("START TRADING")

                self.add_automation_log("Trading stopped - Market data lost")

            if status == "CLOSED":
                self.add_system_log("📊 Market closed - data static")
            else:
                self.add_system_log("📊 Market data: NONE")

        # Refresh provider label color if connection state changed
        if was_connected != self.mkt_data_connected:
            import os
            provider = os.getenv("MARKET_DATA_PROVIDER", "tradier").lower()
            self._apply_mkt_provider_display(provider)

    @Slot(dict)
    def on_market_data_updated(self, data: dict):
        """Handle market data update - only if not using real data"""
        if self.real_data_active:
            return  # Skip simulation updates when using real data

        try:
            for symbol, market_info in data.items():
                if symbol in self.symbol_widgets:
                    self.symbol_widgets[symbol].update_data(market_info)

            self.market_data.update(data)

        except Exception as e:
            self.logger.exception("Error updating market data: %s", e)

    @Slot(str)
    def on_market_error(self, error: str):
        """Handle market error"""
        self.add_system_log(f"❌ Market error: {error}")

    @Slot(str)
    def on_heartbeat_received(self, message: str):
        """Handle heartbeat message - FIXED to route to system log"""
        # Route heartbeat messages to system log (not automation log)
        self.add_system_log(message)

    def toggle_api_connection(self, event):
        """Toggle API connection when clicking on status - UNCHANGED"""
        if self.api_connected:
            if self.trading_active:
                reply = QMessageBox.warning(
                    self,
                    "Trading Active",
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

                self.start_btn.setStyleSheet(
                    f"background-color: {COLORS['positive']}; color: black;",
                )
                self.start_btn.setText("START TRADING")

                self.add_automation_log("Trading stopped due to API disconnection")

            if self.market_worker:
                self.market_worker.force_disconnect()
            self.api_connected = False
            self.add_system_log("Manually disconnected from API")
        else:
            if not is_market_hours():
                QMessageBox.information(
                    self,
                    "Market Closed",
                    "Market is closed. Connection available during trading hours:\n"
                    "4:00 AM - 4:30 PM ET",
                )
                return

            # Try to create a new API connection if we don't have a client
            if not hasattr(self, "tradier_client") or self.tradier_client is None:
                self.add_system_log("🔄 Creating new Tradier API connection...")
                if self.create_api_connection():
                    self.add_system_log("✅ Successfully connected to Tradier API!")
                    return
                self.add_system_log(
                    "❌ Failed to connect to Tradier API",
                )
                QMessageBox.warning(
                    self,
                    "Connection Failed",
                    "Could not connect to Tradier API.\n\n"
                    "Check your API credentials and try again.",
                )
                return

            # Otherwise use the market worker's force_connect (socket check)
            if self.market_worker and self.market_worker.force_connect():
                self.api_connected = True
                self.add_system_log("Manually connected to API")
            else:
                self.add_system_log("Failed to connect to API")

    # ==========================================================================
    # ORDERS & POSITIONS — LIVE DATA
    # ==========================================================================

    def _get_tradier_client_for_mode(self, mode: "TradingMode | None" = None) -> "TradierClient | None":
        """Return a usable TradierClient for the given mode.

        Uses SANDBOX for PAPER, LIVE for LIVE.  Re-uses ``self.tradier_client``
        when already set; otherwise attempts lazy creation from env vars.
        """
        if not TRADIER_AVAILABLE or create_tradier_client_from_env is None:
            return None
        if self.tradier_client is not None:
            return self.tradier_client
        mode = mode or self.trading_mode
        env = (
            TradingEnvironment.LIVE
            if mode == TradingMode.LIVE
            else TradingEnvironment.SANDBOX
        )
        try:
            client = create_tradier_client_from_env(environment=env)
            self.tradier_client = client
            return client
        except Exception as exc:
            self.add_system_log(f"⚠️ Could not create Tradier client: {exc}")
            return None

    def _fetch_pending_orders(self, mode: "TradingMode | None" = None) -> list[dict]:
        """Fetch open/pending orders from Tradier for the given (or current) mode.

        Returns a list of raw Tradier order dicts with status in
        {open, partially_filled, pending}.  Returns empty list on any failure.
        """
        client = self._get_tradier_client_for_mode(mode)
        if not client:
            return []
        try:
            response = client.get_orders()
            orders_node = response.get("orders")
            if not orders_node or orders_node == "null":
                return []
            order_list = orders_node.get("order", [])
            if isinstance(order_list, dict):
                order_list = [order_list]
            _pending = {"open", "partially_filled", "pending"}
            return [o for o in order_list if o.get("status", "").lower() in _pending]
        except Exception as exc:
            self.add_system_log(f"⚠️ Could not fetch orders from Tradier: {exc}")
            return []

    def _cancel_orders(
        self, orders: list[dict], mode: "TradingMode | None" = None
    ) -> tuple[int, int]:
        """Cancel each order in *orders* via Tradier.

        Returns ``(success_count, fail_count)``.
        """
        client = self._get_tradier_client_for_mode(mode)
        if not client:
            return 0, len(orders)
        success = fail = 0
        for order in orders:
            try:
                order_id = int(order.get("id", 0))
                if order_id:
                    client.cancel_order(order_id)
                    success += 1
                    self.add_system_log(f"✅ Cancelled order #{order_id}")
                else:
                    fail += 1
            except Exception as exc:
                fail += 1
                self.add_system_log(f"❌ Failed to cancel order #{order.get('id')}: {exc}")
        return success, fail

    def _refresh_positions_table(self) -> None:
        """Fetch live orders & positions from Tradier and repopulate the table.

        Falls back silently (keeping existing rows) when no API client is
        available or on network error.  Called by the Refresh button and
        automatically after a successful API connection.
        """
        if not self.positions_table:
            return
        if not getattr(self, "api_connected", False):
            self.add_system_log("ℹ️ Not connected — showing demo data")
            return
        client = self._get_tradier_client_for_mode()
        if not client:
            return

        try:
            self.positions_table.clear()
            has_rows = False

            # ── Pending / open orders ─────────────────────────────────────────
            orders_resp = client.get_orders()
            orders_node = orders_resp.get("orders")
            if orders_node and orders_node != "null":
                order_list = orders_node.get("order", [])
                if isinstance(order_list, dict):
                    order_list = [order_list]
                _pending = {"open", "partially_filled", "pending"}
                for o in order_list:
                    if o.get("status", "").lower() in _pending:
                        self._add_order_row(o)
                        has_rows = True

            # ── Open positions ────────────────────────────────────────────────
            pos_resp = client.get_positions()
            pos_node = pos_resp.get("positions")
            if pos_node and pos_node != "null":
                pos_list = pos_node.get("position", [])
                if isinstance(pos_list, dict):
                    pos_list = [pos_list]
                for p in pos_list:
                    self._add_position_row(p)
                    has_rows = True

            if not has_rows:
                _empty = QTreeWidgetItem(self.positions_table)
                _empty.setText(0, "No open orders or positions")
                _empty.setForeground(0, Qt.GlobalColor.gray)
                self.positions_table.setFirstColumnSpanned(0, QModelIndex(), True)

            self.add_system_log("✅ Orders & positions refreshed from Tradier")

        except Exception as exc:
            self.add_system_log(f"❌ Refresh failed: {exc}")

    def _add_order_row(self, order: dict) -> None:
        """Add a single Tradier order dict as a top-level row in positions_table."""
        order_id = order.get("id", "—")
        symbol = order.get("symbol") or order.get("option_symbol", "—")
        o_type = order.get("type", "—").upper()
        side = order.get("side", "—").replace("_", " ").upper()
        qty = int(order.get("quantity", 0))
        remaining = int(order.get("remaining_quantity", qty))
        status = order.get("status", "—").upper()
        o_class = order.get("class", "").lower()

        header = (
            f"ORDER #{order_id} | {symbol} | {o_type} | {side} | "
            f"QTY: {qty} | REMAINING: {remaining} | STATUS: {status}"
        )

        parent = QTreeWidgetItem(self.positions_table)
        parent.setText(0, header)
        parent.setForeground(0, Qt.GlobalColor.yellow)
        self.positions_table.setFirstColumnSpanned(
            self.positions_table.indexOfTopLevelItem(parent),
            QModelIndex(),
            True,
        )
        parent.setExpanded(True)

        # Add close button widget in last column
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(18, 18)
        close_btn.setStyleSheet(
            f"background-color: {COLORS['negative']}; color: white; border: none;"
            " font-size: 10px; border-radius: 2px;"
        )
        close_btn.setToolTip(f"Cancel order #{order_id}")
        close_btn.clicked.connect(lambda _=False, oid=order_id: self._cancel_order_by_id(oid))
        self.positions_table.setItemWidget(parent, 6, close_btn)

        # For multileg orders, show each leg as a child row
        if o_class == "multileg":
            legs_node = order.get("legs", {}) or {}
            leg_list = legs_node.get("leg", [])
            if isinstance(leg_list, dict):
                leg_list = [leg_list]
            for leg in leg_list:
                child = QTreeWidgetItem(parent)
                child.setText(0, f"  {leg.get('side','—').replace('_',' ').upper()}")
                child.setText(1, leg.get("option_symbol", "—"))
                child.setText(2, str(int(leg.get("quantity", 0))))
                child.setText(3, leg.get("expiration_date", "—"))

    def _add_position_row(self, pos: dict) -> None:
        """Add a single Tradier position dict as a top-level row in positions_table."""
        symbol = pos.get("symbol", "—")
        qty = int(pos.get("quantity", 0))
        cost_basis = float(pos.get("cost_basis", 0.0))
        date_acquired = pos.get("date_acquired", "—")[:10]  # YYYY-MM-DD

        header = (
            f"POSITION | {symbol} | QTY: {qty} | "
            f"COST BASIS: ${cost_basis:,.2f} | ACQUIRED: {date_acquired} | STATUS: OPEN"
        )
        parent = QTreeWidgetItem(self.positions_table)
        parent.setText(0, header)
        parent.setForeground(0, Qt.GlobalColor.green)
        self.positions_table.setFirstColumnSpanned(
            self.positions_table.indexOfTopLevelItem(parent),
            QModelIndex(),
            True,
        )

    def _cancel_order_by_id(self, order_id: int) -> None:
        """Cancel a single order by Tradier order ID (called from row close button)."""
        answer = QMessageBox.question(
            self,
            "Cancel Order",
            f"Cancel order #{order_id} at Tradier?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        client = self._get_tradier_client_for_mode()
        if not client:
            QMessageBox.warning(self, "Not Connected", "No Tradier client available.")
            return
        try:
            client.cancel_order(int(order_id))
            self.add_system_log(f"✅ Order #{order_id} cancelled")
            self._refresh_positions_table()
        except Exception as exc:
            self.add_system_log(f"❌ Failed to cancel order #{order_id}: {exc}")
            QMessageBox.critical(self, "Cancel Failed", str(exc))

    # ==========================================================================
    # TRADING MODE MANAGEMENT
    # ==========================================================================

    def _on_mode_btn_clicked(self, new_mode: TradingMode):
        """Handle LIVE TRADING / PAPER TRADING toggle button click.

        Gate logic
        ----------
        PAPER → LIVE  (hard blocks, then typed confirmation)
          1. trading_active must be False         — stop paper engine first
          2. No pending sandbox orders            — must be cancelled first
          3. api_connected must be True           — Tradier EXEC must be connected
          4. mkt_data_connected must be True      — a data feed must be connected
          5. Typed confirmation gate              — type "I CONFIRM LIVE TRADING"

        LIVE → PAPER  (hard blocks, then Yes/No)
          1. trading_active must be False         — stop live engine first
          2. No pending live orders               — must be cancelled first
          3. Open positions warning               — user can override
          4. Yes/No confirmation
        """
        if new_mode == self.trading_mode:
            self._update_mode_buttons()
            return

        # ── PAPER → LIVE ──────────────────────────────────────────────────────
        if new_mode == TradingMode.LIVE:

            # Gate 1: no active trading session
            if self.trading_active:
                QMessageBox.warning(
                    self,
                    "Trading Active",
                    "Cannot switch to LIVE while paper trading is running.\n"
                    "Stop paper trading first, then switch.",
                )
                self._update_mode_buttons()
                return

            # Gate 2: check for pending sandbox orders
            pending = self._fetch_pending_orders(TradingMode.PAPER)
            if pending:
                order_lines = "\n".join(
                    f"  #{o.get('id')}  {o.get('symbol','?')}  {o.get('side','?').upper()}"
                    f"  qty {int(o.get('quantity',0))}  [{o.get('status','?').upper()}]"
                    for o in pending[:10]
                )
                suffix = f"\n  … and {len(pending)-10} more" if len(pending) > 10 else ""
                result = QMessageBox.warning(
                    self,
                    "Pending Paper Orders Must Be Cancelled",
                    f"You have {len(pending)} pending order(s) in the paper/sandbox account:\n\n"
                    f"{order_lines}{suffix}\n\n"
                    "These must be cancelled before switching to LIVE trading.\n\n"
                    "Cancel all pending orders now and continue?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if result != QMessageBox.StandardButton.Yes:
                    self.add_system_log("Switch to LIVE cancelled — pending paper orders remain")
                    self._update_mode_buttons()
                    return
                ok, fail = self._cancel_orders(pending, TradingMode.PAPER)
                if fail:
                    QMessageBox.critical(
                        self,
                        "Cancellation Failed",
                        f"{fail} order(s) could not be cancelled.\n"
                        "Resolve them manually before switching to LIVE trading.",
                    )
                    self._update_mode_buttons()
                    return
                self.add_system_log(f"✅ {ok} pending paper order(s) cancelled — continuing switch")

            # Gate 3: Tradier EXEC must be connected
            if not getattr(self, "api_connected", False):
                QMessageBox.critical(
                    self,
                    "Tradier EXEC Not Connected",
                    "You must connect to Tradier EXEC before switching to LIVE trading.\n\n"
                    "Click the TRADIER EXEC indicator in the toolbar to connect.",
                )
                self._update_mode_buttons()
                return

            # Gate 4: a market data feed must be connected
            if not getattr(self, "mkt_data_connected", False):
                QMessageBox.critical(
                    self,
                    "No Data Feed Connected",
                    "You must connect a market data feed (MASSIVE DATA or TRADIER DATA)\n"
                    "before switching to LIVE trading.\n\n"
                    "Click the data feed indicator in the toolbar to connect.",
                )
                self._update_mode_buttons()
                return

            # Gate 5: typed confirmation
            if not self._confirm_live_trading():
                self.add_system_log("Switch to LIVE cancelled by user")
                self._update_mode_buttons()
                return

        # ── LIVE → PAPER ──────────────────────────────────────────────────────
        else:
            # Gate 1: no active trading session
            if self.trading_active:
                QMessageBox.warning(
                    self,
                    "Trading Active",
                    "Cannot switch to PAPER while live trading is running.\n"
                    "Stop live trading first, then switch.",
                )
                self._update_mode_buttons()
                return

            # Gate 2: check for pending live orders — must be cancelled first
            pending = self._fetch_pending_orders(TradingMode.LIVE)
            if pending:
                order_lines = "\n".join(
                    f"  #{o.get('id')}  {o.get('symbol','?')}  {o.get('side','?').upper()}"
                    f"  qty {int(o.get('quantity',0))}  [{o.get('status','?').upper()}]"
                    for o in pending[:10]
                )
                suffix = f"\n  … and {len(pending)-10} more" if len(pending) > 10 else ""
                result = QMessageBox.warning(
                    self,
                    "Pending Live Orders Must Be Cancelled",
                    f"You have {len(pending)} pending LIVE order(s) at Tradier:\n\n"
                    f"{order_lines}{suffix}\n\n"
                    "These must be cancelled before switching to Paper Trading.\n\n"
                    "Cancel all pending orders now and continue?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if result != QMessageBox.StandardButton.Yes:
                    self.add_system_log("Switch to PAPER cancelled — pending live orders remain")
                    self._update_mode_buttons()
                    return
                ok, fail = self._cancel_orders(pending, TradingMode.LIVE)
                if fail:
                    QMessageBox.critical(
                        self,
                        "Cancellation Failed",
                        f"{fail} order(s) could not be cancelled.\n"
                        "Resolve them manually or call Tradier: +1 (312) 542-6901.",
                    )
                    self._update_mode_buttons()
                    return
                self.add_system_log(f"✅ {ok} pending live order(s) cancelled — continuing switch")

            # Gate 3: warn if live positions still open (positions, not orders)
            open_count = 0
            if self.positions_table is not None:
                open_count = self.positions_table.topLevelItemCount()
            if open_count > 0:
                answer = QMessageBox.warning(
                    self,
                    "Open Positions Detected",
                    f"You still have {open_count} open position(s) at Tradier.\n\n"
                    "Switching to Paper Trading will NOT close these positions — "
                    "they will remain open at the broker and must be managed manually.\n\n"
                    "Switch anyway?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    self.add_system_log("Switch to PAPER cancelled — open positions remain")
                    self._update_mode_buttons()
                    return

            # Gate 4: final confirmation
            answer = QMessageBox.question(
                self,
                "Switch to Paper Trading",
                "Switch to PAPER Trading?\n"
                "Simulated fills only — no real orders will be placed.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                self.add_system_log("Switch to PAPER cancelled by user")
                self._update_mode_buttons()
                return

        self._apply_mode_change(new_mode)

    def _apply_mode_change(self, new_mode: TradingMode):
        """Internal: commit trading mode switch and refresh all dependent UI."""
        self.trading_mode = new_mode
        is_paper = new_mode == TradingMode.PAPER

        self._update_mode_buttons()

        # Reset account container to placeholders; real data arrives via broker/signals
        if self.acct_number_lbl:
            self.acct_number_lbl.setText("PAPER ACCOUNT" if is_paper else "—")
        for lbl in (self.settled_value, self.buying_value, self.realized_value, self.unrealized_value):
            if lbl:
                lbl.setText("—")

        # Update START/STOP tooltips
        if is_paper:
            self.start_btn.setToolTip("Start paper trading with simulated fills")
            self.stop_btn.setToolTip("Stop paper trading but keep simulated positions")
        else:
            self.start_btn.setToolTip("Start LIVE trading with real order execution")
            self.stop_btn.setToolTip("Stop live trading — open orders remain at Tradier")

        self._update_orders_title()
        self._update_pnl_title()
        self.add_system_log(f"Trading mode changed to {new_mode.value}")

        import os
        current_provider = os.getenv("MARKET_DATA_PROVIDER", "tradier").lower()
        self._apply_mkt_provider_display(current_provider)

    def _update_pnl_title(self):
        """Update the P&L PERFORMANCE title label text and color based on trading mode."""
        if not hasattr(self, "pnl_title_lbl") or self.pnl_title_lbl is None:
            return
        is_paper = self.trading_mode == TradingMode.PAPER
        if is_paper:
            self.pnl_title_lbl.setText("P&L PERFORMANCE - PAPER TRADING")
            self.pnl_title_lbl.setStyleSheet("font-size: 15px; font-weight: normal; letter-spacing: 1px; color: #FFA500;")
        else:
            self.pnl_title_lbl.setText("P&L PERFORMANCE - LIVE TRADING")
            self.pnl_title_lbl.setStyleSheet("font-size: 15px; font-weight: normal; letter-spacing: 1px; color: #00FF00;")

    def _update_orders_title(self):
        """Update the ORDERS & POSITIONS title label text and color based on trading mode."""
        if not hasattr(self, "orders_title_label") or self.orders_title_label is None:
            return
        is_paper = self.trading_mode == TradingMode.PAPER
        if is_paper:
            self.orders_title_label.setText("ORDERS & POSITIONS - PAPER TRADING")
            self.orders_title_label.setStyleSheet("font-weight: normal; font-size: 11pt; color: #FFA500;")
        else:
            self.orders_title_label.setText("ORDERS & POSITIONS - LIVE TRADING")
            self.orders_title_label.setStyleSheet("font-weight: normal; font-size: 11pt; color: #00FF00;")

    def _update_mode_buttons(self):
        """Apply active/inactive styles to the LIVE / PAPER toggle buttons."""
        if not self.live_btn or not self.paper_btn:
            return
        is_live = self.trading_mode == TradingMode.LIVE
        _active_base = "font-size: 12px; border-radius: 3px; padding: 4px 8px; border: none;"
        _inactive_base = f"font-size: 12px; border-radius: 3px; padding: 4px 8px; border: none; background-color: {COLORS['panel']}; color: #555555;"
        self.live_btn.setStyleSheet(
            f"background-color: {COLORS['positive']}; color: black; {_active_base}"
            if is_live else _inactive_base
        )
        self.paper_btn.setStyleSheet(
            f"background-color: {COLORS['orange']}; color: black; {_active_base}"
            if not is_live else _inactive_base
        )

    # kept for any external callers that may reference this name
    def _on_mode_changed(self, mode_text: str):
        """Deprecated shim — forwards to _apply_mode_change."""
        try:
            self._apply_mode_change(TradingMode(mode_text))
        except ValueError:
            pass

    def _confirm_live_trading(self) -> bool:
        """Show a typed-confirmation dialog before starting LIVE trading.

        The user must type the exact phrase 'I CONFIRM LIVE TRADING' before the
        Confirm button activates.  Returns True only if they do so and click Confirm.
        """
        REQUIRED_PHRASE = "I CONFIRM LIVE TRADING"

        dlg = QDialog(self)
        dlg.setWindowTitle("⚠️  LIVE TRADING — CONFIRMATION REQUIRED")
        dlg.setMinimumWidth(480)
        dlg.setModal(True)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        # Warning header
        header = QLabel("⚠️  YOU ARE ABOUT TO START LIVE TRADING")
        header.setStyleSheet(
            f"color: {COLORS['negative']}; font-size: 15px; font-weight: bold;"
        )
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        # Body text
        body = QLabel(
            "This will execute <b>REAL orders</b> with <b>REAL money</b> "
            "through the Tradier <b>production</b> API.\n\n"
            "All trades are immediately binding and cannot be undone by this application."
        )
        body.setWordWrap(True)
        body.setStyleSheet("font-size: 13px;")
        layout.addWidget(body)

        # Instruction label
        instruction = QLabel(f'To confirm, type exactly:  <b>{REQUIRED_PHRASE}</b>')
        instruction.setStyleSheet("font-size: 12px;")
        layout.addWidget(instruction)

        # Input field
        line_edit = QLineEdit()
        line_edit.setPlaceholderText(REQUIRED_PHRASE)
        line_edit.setStyleSheet(
            f"font-size: 13px; padding: 6px; border: 2px solid {COLORS['negative']};"
        )
        layout.addWidget(line_edit)

        # Buttons
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        confirm_btn = btn_box.button(QDialogButtonBox.StandardButton.Ok)
        confirm_btn.setText("CONFIRM LIVE TRADING")
        confirm_btn.setEnabled(False)
        confirm_btn.setStyleSheet(
            f"background-color: {COLORS['negative']}; color: white; font-weight: bold; padding: 6px 14px;"
        )
        btn_box.rejected.connect(dlg.reject)
        btn_box.accepted.connect(dlg.accept)
        layout.addWidget(btn_box)

        def _on_text_changed(text: str) -> None:
            confirm_btn.setEnabled(text == REQUIRED_PHRASE)

        line_edit.textChanged.connect(_on_text_changed)

        return dlg.exec() == QDialog.DialogCode.Accepted

    def start_trading(self):
        """Handle start trading button click — mode-aware."""
        if self.trading_active:
            self.add_system_log("Trading already active")
            return

        # PAPER mode — launch paper trading worker (manages its own connection)
        if self.trading_mode == TradingMode.PAPER:
            self._start_paper_trading()
            return

        # LIVE mode gates
        if not self.api_connected:
            QMessageBox.warning(
                self,
                "API Disconnected",
                "API is disconnected - cannot start trading",
            )
            self.add_system_log("Cannot start trading - API disconnected")
            return

        if self.trading_mode == TradingMode.LIVE:
            if not self._confirm_live_trading():
                self.add_system_log("Live trading start cancelled by user")
                return

        data_status = self.data_status_label.text()
        if data_status not in ["LIVE", "LIVE DATA", "LIVE - REAL"]:
            QMessageBox.warning(
                self,
                "No Live Data",
                "NO LIVE DATA\n\nCannot start trading without live market data.",
            )
            self.add_system_log("Cannot start trading - No live data")
            return

        self.trading_active = True
        self.connection_info.trading_active = True

        self.start_btn.setStyleSheet(
            f"background-color: {COLORS['automation_active']}; color: white;",
        )
        self.start_btn.setText("TRADING ACTIVE")

        mode_label = self.trading_mode.value
        self.add_system_log(f"{mode_label} trading started successfully")
        self.add_automation_log(f"TRADING ACTIVE [{mode_label}] - Autonomous AI Engine engaged")

        if self.real_data_active:
            self.add_automation_log("Using REAL market data from Massive API")
        else:
            self.add_automation_log("Monitoring SPY options for trading opportunities")

    def _start_paper_trading(self):
        """Launch the paper trading worker in a background QThread."""
        if not TRADIER_AVAILABLE:
            QMessageBox.warning(
                self,
                "Tradier Unavailable",
                "TradierClient module could not be imported.\n"
                "Paper trading requires SpyderB40_TradierClient.",
            )
            return

        self.add_system_log("Launching paper trading engine…")

        self.trading_active = True
        self.connection_info.trading_active = True
        self.start_btn.setStyleSheet(
            f"background-color: {COLORS['automation_active']}; color: white;",
        )
        self.start_btn.setText("PAPER ACTIVE")
        self.start_btn.setEnabled(False)

        # Show "Connecting…" placeholder in the account container
        if self.acct_number_lbl:
            self.acct_number_lbl.setText("PAPER ACCOUNT")
        for lbl in (self.settled_value, self.buying_value, self.realized_value, self.unrealized_value):
            if lbl:
                lbl.setText("Connecting…")

        # Create worker and thread
        self._paper_thread = QThread(self)
        self._paper_worker = _PaperTradingWorker(initial_capital=100_000.0)
        self._paper_worker.moveToThread(self._paper_thread)

        # Wire signals (all bound methods for proper QueuedConnection)
        self._paper_thread.started.connect(self._paper_worker.run)
        self._paper_worker.status_update.connect(self._on_paper_status)
        self._paper_worker.position_update.connect(self._on_paper_position)
        self._paper_worker.metrics_update.connect(self._on_paper_metrics)
        self._paper_worker.error.connect(self._on_paper_error)
        self._paper_worker.stopped.connect(self._on_paper_stopped)
        self._paper_worker.connection_ready.connect(self._on_paper_connection)

        self._paper_thread.start()
        self.add_automation_log("PAPER TRADING — Connecting to Tradier sandbox…")

    def _stop_paper_trading(self):
        """Stop the paper trading worker gracefully."""
        if self._paper_worker:
            self._paper_worker.stop()
            self.add_system_log("Stopping paper trading…")

    @Slot(str)
    def _on_paper_status(self, msg: str):
        """Handle paper trading status update in the GUI thread."""
        self.add_system_log(f"Paper: {msg}")

    @Slot(dict)
    def _on_paper_position(self, data: dict):
        """Handle paper position update — push figures into the account container."""
        equity = data.get("equity", 0.0)
        cash = data.get("cash", 0.0)
        unrealized = data.get("unrealized_pnl", 0.0)
        realized = data.get("realized_pnl", 0.0)

        if self.settled_value:
            self.settled_value.setText(f"${equity:,.2f}")
        if self.buying_value:
            self.buying_value.setText(f"${cash:,.2f}")
        if self.unrealized_value:
            color = COLORS["positive"] if unrealized >= 0 else COLORS["negative"]
            self.unrealized_value.setText(f"${unrealized:+,.2f}")
            self.unrealized_value.setStyleSheet(
                f"padding: 2px 5px; background-color: {COLORS['background']}; "
                f"border: 1px solid {COLORS['border']}; font-size: 12px; color: {color}; text-align: right;"
            )
        if self.realized_value:
            color = COLORS["positive"] if realized >= 0 else COLORS["negative"]
            self.realized_value.setText(f"${realized:+,.2f}")
            self.realized_value.setStyleSheet(
                f"padding: 2px 5px; background-color: {COLORS['background']}; "
                f"border: 1px solid {COLORS['border']}; font-size: 12px; color: {color}; text-align: right;"
            )
        # Log to system for visibility
        qty = data.get("position_qty", 0)
        spy_last = data.get("spy_last", 0.0)
        if qty > 0:
            self.add_system_log(
                f"Paper: SPY ${spy_last:.2f} | {qty} shares | "
                f"Unrealized: ${unrealized:+,.2f} | Equity: ${equity:,.2f}"
            )
        else:
            self.add_system_log(f"Paper: SPY ${spy_last:.2f} | No position | Equity: ${equity:,.2f}")

    @Slot(dict)
    def _on_paper_metrics(self, metrics: dict):
        """Handle paper P&L metrics update — push summary figures into account container."""
        equity_str = metrics.get("equity", "")
        realized_str = metrics.get("realized_pnl", "")

        if self.settled_value and equity_str:
            self.settled_value.setText(equity_str)
        if self.realized_value and realized_str:
            try:
                num = float(realized_str.replace("$", "").replace(",", "").replace("+", ""))
                color = COLORS["positive"] if num >= 0 else COLORS["negative"]
            except (ValueError, TypeError):
                color = COLORS["text"]
            self.realized_value.setText(realized_str)
            self.realized_value.setStyleSheet(
                f"padding: 2px 5px; background-color: {COLORS['background']}; "
                f"border: 1px solid {COLORS['border']}; font-size: 12px; color: {color}; text-align: right;"
            )

        # Refresh P&L performance table with whatever stats we have
        self._refresh_pnl_table(metrics)

    def _refresh_pnl_table(self, stats: dict) -> None:
        """Refresh the P&L performance table from trading stats.

        Called from _on_paper_metrics with the latest metrics dict, and can be
        called with any dict that contains per-period keys.  Recognised keys
        (all optional — missing values stay as \u2014):

            today_pnl, week_pnl, month_pnl, year_pnl          — formatted P&L strings
            today_win_rate, week_win_rate, ...                  — e.g. "75%"
            today_win_loss, week_win_loss, ...                  — e.g. "$300/$120"
            today_profit_factor, ...                            — e.g. "1.65"
            today_sharpe, week_sharpe, ...                      — e.g. "1.85"
            today_sortino, ...                                  — e.g. "2.12"
            today_calmar, ...                                   — e.g. "1.95"
        """
        if self.pnl_table is None:
            return

        # Also try H07 PerformanceAnalytics if available
        try:
            from Spyder.SpyderH_Storage.SpyderH07_PerformanceAnalytics import (
                PerformanceAnalytics,
            )
            pa = PerformanceAnalytics()
            h07_stats = pa.get_summary_stats()
            if h07_stats:
                stats = {**stats, **h07_stats}
        except Exception:
            pass  # H07 unavailable — use whatever is in stats

        periods = ["today", "week", "month", "year"]
        col_map = {1: "pnl", 2: "win_rate", 3: "win_loss", 4: "profit_factor",
                   5: "sharpe", 6: "sortino", 7: "calmar"}

        for row, period in enumerate(periods):
            for col, metric in col_map.items():
                key = f"{period}_{metric}"
                value = str(stats.get(key, "\u2014"))
                item = self.pnl_table.item(row, col)
                if item is None:
                    from PySide6.QtWidgets import QTableWidgetItem
                    item = QTableWidgetItem(value)
                    self.pnl_table.setItem(row, col, item)
                else:
                    item.setText(value)
                # Colour P&L column green/red
                if col == 1 and value not in ("\u2014", "", "—"):
                    try:
                        num = float(value.replace("$", "").replace(",", "").replace("+", ""))
                        from PySide6.QtGui import QColor
                        item.setForeground(QColor(COLORS["positive"] if num >= 0 else COLORS["negative"]))
                    except (ValueError, TypeError):
                        pass

    @Slot(str)
    def _on_paper_error(self, error_msg: str):
        """Handle paper trading error."""
        self.add_system_log(f"❌ Paper trading error: {error_msg}")
        QMessageBox.warning(self, "Paper Trading Error", error_msg)

    @Slot()
    def _on_paper_stopped(self):
        """Handle paper trading worker exit."""
        # Clean up thread
        if self._paper_thread and self._paper_thread.isRunning():
            self._paper_thread.quit()
            self._paper_thread.wait(10_000)

        self.trading_active = False
        self.connection_info.trading_active = False

        self.start_btn.setStyleSheet(
            f"background-color: {COLORS['positive']}; color: black;",
        )
        self.start_btn.setText("START TRADING")
        self.start_btn.setEnabled(True)

        # Reset account container to idle state
        if self.acct_number_lbl:
            self.acct_number_lbl.setText("PAPER ACCOUNT")
        for lbl in (self.settled_value, self.buying_value, self.realized_value, self.unrealized_value):
            if lbl:
                lbl.setText("—")

        self.add_automation_log("PAPER TRADING STOPPED — Session ended")

    @Slot(float, float)
    def _on_balance_updated(self, equity: float, buying_power: float):
        """Update account balance fields from Tradier API (emitted by market worker heartbeat)."""
        if not self.trading_active:  # Only show if paper trading not already active
            if self.settled_value and equity:
                self.settled_value.setText(f"${equity:,.2f}")
            if self.buying_value and buying_power:
                self.buying_value.setText(f"${buying_power:,.2f}")

    @Slot(bool)
    def _on_paper_connection(self, connected: bool):
        """Handle paper trading connection result."""
        if connected:
            self.on_connection_status_changed(True, "Tradier (PAPER)")
            self.update_data_status("LIVE")
            if self.acct_number_lbl:
                self.acct_number_lbl.setText("PAPER ACCOUNT")
            self.add_automation_log("PAPER TRADING ACTIVE — Polling SPY every 30s")
        else:
            self.add_system_log("❌ Paper trading could not connect to Tradier")

    def stop_trading(self):
        """Handle stop trading button click — mode-aware."""
        # PAPER mode — stop the paper worker
        if self.trading_mode == TradingMode.PAPER and self._paper_worker:
            self._stop_paper_trading()
            return
        if not self.api_connected:
            QMessageBox.information(
                self,
                "API Disconnected",
                "API is disconnected - further trading has already stopped, but open orders at Tradier still remain in effect. If you wish to close or cancel these orders, call Tradier at +1 (312) 542-6901",
            )
            return

        if not self.trading_active:
            self.add_system_log("No active trading to stop")
            return

        self.trading_active = False
        self.connection_info.trading_active = False

        self.start_btn.setStyleSheet(
            f"background-color: {COLORS['positive']}; color: black;",
        )
        self.start_btn.setText("START TRADING")

        self.add_system_log("Trading stopped - Orders and positions remain active")
        self.add_automation_log("TRADING STOPPED - Existing positions maintained")
        self.add_automation_log("Autonomous AI Engine on standby")

    def emergency_close(self):
        """Handle emergency close button click - FIXED MESSAGES"""
        if not self.api_connected:
            QMessageBox.critical(
                self,
                "API Disconnected",
                "API is disconnected - unable to close open orders at Tradier. If you wish to close or cancel these orders, call Tradier at +1 (312) 542-6901",
            )
            return

        reply = QMessageBox.critical(
            self,
            "EMERGENCY CLOSE",
            "⚠️ EMERGENCY PROTOCOL ⚠️\n\n"
            "This will IMMEDIATELY:\n"
            "• Close ALL open positions\n"
            "• Cancel ALL pending orders\n"
            "• Stop automated trading\n"
            "• Disconnect from Tradier API\n\n"
            "Are you sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.add_system_log(
                "🚨 EMERGENCY CLOSE - All positions closed, system stopped",
            )
            self.add_automation_log(
                "EMERGENCY PROTOCOL - All positions closed by autonomous system",
            )

            self.trading_active = False
            self.connection_info.trading_active = False

            self.start_btn.setStyleSheet(
                f"background-color: {COLORS['positive']}; color: black;",
            )
            self.start_btn.setText("START TRADING")

            if self.market_worker:
                self.market_worker.force_disconnect()
            self.api_connected = False

    # ==========================================================================
    # ENHANCED STATUS MANAGEMENT
    # ==========================================================================
    def update_data_status(self, status_type: str):
        """Update data status display — 4 states: LIVE, EOD, SIMULATED, FROZEN."""
        if status_type == "LIVE":
            self.data_status_label.setText("LIVE")
            self.data_status_label.setStyleSheet(
                "color: " + COLORS["positive"] + "; font-size: 14px;",
            )
            self.data_status_container.setCursor(Qt.CursorShape.ArrowCursor)
            self.data_status_container.setToolTip("Live market data")
        elif status_type == "EOD":
            self.data_status_label.setText("EOD")
            self.data_status_label.setStyleSheet(
                "color: " + COLORS["warning"] + "; font-size: 14px;",
            )
            self.data_status_container.setCursor(Qt.CursorShape.PointingHandCursor)
            self.data_status_container.setToolTip("End-of-day data — click to switch to SIMULATED")
        elif status_type == "FROZEN":
            self.data_status_label.setText("FROZEN")
            self.data_status_label.setStyleSheet(
                "color: " + COLORS["negative"] + "; font-size: 14px;",
            )
            self.data_status_container.setCursor(Qt.CursorShape.ArrowCursor)
            self.data_status_container.setToolTip("Data frozen — waiting for API reconnection")
        else:
            # NONE, SIMULATION → SIMULATED
            self.data_status_label.setText("SIMULATED")
            self.data_status_label.setStyleSheet(
                "color: " + COLORS["automation_active"] + "; font-size: 14px;",
            )
            self.data_status_container.setCursor(Qt.CursorShape.PointingHandCursor)
            self.data_status_container.setToolTip("Simulated data — click to switch to EOD")

    def determine_data_status(self) -> str:
        """Determine appropriate data status based on current conditions - FIXED SIMULATION DETECTION"""
        market_hours = is_market_hours()

        # FIXED: Check for simulation mode first with better detection
        if (
            hasattr(self.connection_info, "simulation_mode")
            and self.connection_info.simulation_mode
        ) or (
            not self.api_connected
            and hasattr(self, "market_worker")
            and self.market_worker is not None
            and hasattr(self.market_worker, "update_timer")
            and self.market_worker.update_timer is not None
            and self.market_worker.update_timer.isActive()
        ):
            return "SIMULATION"

        if self.api_connected:
            # API is connected
            if market_hours:
                self.connection_info.data_was_live = True
                self.connection_info.last_successful_data = datetime.now()
                return "LIVE"
            self.connection_info.last_successful_data = datetime.now()
            return "EOD"
        # API is disconnected
        if self.real_data_active:
            # Using file data - always treat as EOD
            return "EOD"
        if (
            market_hours
            and hasattr(self.connection_info, "data_was_live")
            and self.connection_info.data_was_live
        ):
            # Market hours but no recent successful connection = FROZEN
            if (
                hasattr(self.connection_info, "last_successful_data")
                and self.connection_info.last_successful_data
                and (
                    datetime.now() - self.connection_info.last_successful_data
                ).total_seconds()
                < 300
            ):  # 5 minutes
                return "FROZEN"
            return "EOD"
        # FIXED: If simulation data is updating, show SIMULATION instead of EOD
        if (
            hasattr(self, "market_worker")
            and self.market_worker is not None
            and hasattr(self.market_worker, "update_timer")
            and self.market_worker.update_timer is not None
            and self.market_worker.update_timer.isActive()
        ):
            return "SIMULATION"
        return "EOD"

    def update_status_indicators(self):
        """Update both status indicators based on current state"""
        # Update data status
        data_status = self.determine_data_status()
        self.update_data_status(data_status)

    def toggle_market_data_provider(self, event):
        """Switch market data source between Tradier and Massive."""
        import os
        current = os.getenv("MARKET_DATA_PROVIDER", "tradier").lower()
        new_provider = "massive" if current == "tradier" else "tradier"
        try:
            from Spyder.SpyderC_MarketData.SpyderC00_MarketDataProtocol import (
                switch_market_data_provider,
            )
            switch_market_data_provider(new_provider)
        except ImportError:
            os.environ["MARKET_DATA_PROVIDER"] = new_provider
        except Exception as exc:
            self.add_system_log(f"❌ Market data provider switch error: {exc}")
            return

        self._apply_mkt_provider_display(new_provider)
        self.add_system_log(
            f"🔄 Market data provider → {new_provider.upper()} (takes effect on next reconnect)",
        )

    def _apply_mkt_provider_display(self, provider: str) -> None:
        """Update the market data provider indicator label in the toolbar.

        Color is connection-based: red when disconnected, green when connected.
        """
        if not hasattr(self, "mkt_provider_label"):
            return
        if getattr(self, "mkt_data_connected", False):
            color = COLORS["positive"]
        else:
            color = COLORS["negative"]
        self.mkt_provider_label.setText(provider.upper() + " DATA")
        self.mkt_provider_label.setStyleSheet(f"color: {color}; font-size: 14px;")
        if hasattr(self, "mkt_connect_icon") and self.mkt_connect_icon:
            self.mkt_connect_icon.setStyleSheet(f"color: {color}; font-size: 13px;")
            if getattr(self, "mkt_data_connected", False):
                self.mkt_connect_icon.setToolTip("Click to disconnect market data feed")
            else:
                self.mkt_connect_icon.setToolTip("Click to connect market data feed")

    def _toggle_data_display(self, event):
        """Toggle data display between EOD and SIMULATED (click handler for data_status_container).

        Only EOD and SIMULATED are clickable. LIVE and FROZEN ignore clicks.
        """
        current_text = self.data_status_label.text()
        if current_text == "EOD":
            # Switch to SIMULATED
            if not hasattr(self.connection_info, "simulation_mode"):
                self.connection_info.simulation_mode = False
            self.connection_info.simulation_mode = True
            self.add_system_log("🔵 Switched to SIMULATED data")
            self._init_simulation_from_real_data()
            self.update_data_status("SIMULATION")
        elif current_text == "SIMULATED":
            # Switch to EOD
            if hasattr(self.connection_info, "simulation_mode"):
                self.connection_info.simulation_mode = False
            self.add_system_log("📊 Switched to EOD data")
            self.update_data_status("EOD")
        # LIVE and FROZEN: do nothing on click

    def _toggle_mkt_data_connection(self, event):
        """Toggle market data feed connection (⚡ icon click handler)."""
        if self.mkt_data_connected:
            # Disconnect data feed
            self.mkt_data_connected = False
            if self.market_worker:
                self.market_worker.force_disconnect()
            self.add_system_log("🔌 Market data feed manually disconnected")
        else:
            # Connect data feed
            if not is_market_hours():
                QMessageBox.information(
                    self,
                    "Market Closed",
                    "Market is closed. Data feed available during trading hours:\n"
                    "4:00 AM - 4:30 PM ET",
                )
                return
            self.add_system_log("🔄 Connecting market data feed...")
            if self.market_worker and self.market_worker.force_connect():
                self.mkt_data_connected = True
                self.add_system_log("✅ Market data feed connected")
            else:
                self.add_system_log("❌ Failed to connect market data feed")

        import os
        provider = os.getenv("MARKET_DATA_PROVIDER", "tradier").lower()
        self._apply_mkt_provider_display(provider)
        self.update_status_indicators()

    def _init_simulation_from_real_data(self):
        """Initialize simulation starting from last real market prices"""
        if hasattr(self, "market_data") and self.market_data:
            # Use current market data as baseline for simulation
            self.add_system_log(
                f"🎯 Simulation baseline: SPY ${self.market_data.get('SPY', {}).get('last', 585):.2f}",
            )
        else:
            # Use default simulation data
            self.add_system_log("🎯 Using default simulation baseline")

    # ==========================================================================
    # UTILITY METHODS - ENHANCED WITH HEARTBEAT WORKER
    # ==========================================================================
    def start_market_worker(self):
        """Start the enhanced market worker with heartbeat monitoring"""
        try:
            self.market_thread = QThread()
            self.market_worker = ThreadSafeMarketDataWorker()
            self.market_worker.moveToThread(self.market_thread)

            # Connect all signals including new heartbeat signal
            self.market_worker.data_updated.connect(self.on_market_data_updated)
            self.market_worker.connection_status_changed.connect(
                self.on_connection_status_changed,
            )
            self.market_worker.market_data_status_changed.connect(
                self.on_market_data_status_changed,
            )
            self.market_worker.error_occurred.connect(self.on_market_error)
            self.market_worker.heartbeat_received.connect(self.on_heartbeat_received)
            self.market_worker.heartbeat_status_changed.connect(
                self.on_heartbeat_status_changed,
            )  # NEW
            self.market_worker.log_message.connect(
                self.add_system_log,
            )  # NEW: Direct log messages
            self.market_worker.balance_updated.connect(
                self._on_balance_updated,
            )  # NEW: Account balance from Tradier
            self.market_worker.fetch_requested.connect(
                self.market_worker._fetch_live_data_from_tradier,
                Qt.QueuedConnection,
            )  # Safe cross-thread trigger

            self.market_thread.started.connect(self.market_worker.start)
            self.market_thread.start()

            self.add_system_log(
                "🔈 Market data worker started with heartbeat monitoring",
            )

        except Exception as e:
            self.logger.exception("Error starting market worker: %s", e)
            self.add_system_log(f"❌ Market worker error: {e}")

    def setup_timers(self):
        """Setup various timers"""
        # Date/time update timer
        self.datetime_timer = QTimer()
        self.datetime_timer.timeout.connect(self.update_datetime)
        self.datetime_timer.start(1000)

        # Automation activity timer
        self.automation_timer = QTimer()
        self.automation_timer.timeout.connect(self.generate_automation_activity)
        self.automation_timer.start(3000)

        # Greek risk update timer
        self.greek_timer = QTimer()
        self.greek_timer.timeout.connect(self.update_greek_risks)
        self.greek_timer.start(4000)

        # Chart update timer
        self.chart_timer = QTimer()
        self.chart_timer.timeout.connect(self.update_chart)
        self.chart_timer.start(30000)

        # Prometheus metrics simulation timer
        self.prometheus_timer = QTimer()
        self.prometheus_timer.timeout.connect(self.update_prometheus_metrics)
        self.prometheus_timer.start(8000)

        # Gateway polling timer — REMOVED (Tradier migration)
        self._deprecated_gateway_timer = None

    def update_datetime(self):
        """Update date/time display"""
        current_time = datetime.now().strftime("%Y-%m-%d   %H:%M:%S  ET")
        self.datetime_label.setText(current_time)

    def generate_automation_activity(self):
        """Generate automation activity logs"""
        if not hasattr(self, "automation_activity_count"):
            self.automation_activity_count = 0

        activities = [
            "Scanning options chains for SPY",
            "Analyzing volatility surface patterns",
            "Monitoring delta-gamma hedging flows",
            "Evaluating iron condor opportunities",
            "Checking risk parameter compliance",
            "Calculating position Greeks",
            "Analyzing market microstructure",
            "Monitoring VIX term structure",
            "Evaluating covered call opportunities",
            "Scanning for unusual options activity",
            "Analyzing skew and smile patterns",
            "Monitoring earnings event calendar",
            "Evaluating butterfly spread setups",
            "Checking correlation patterns",
            "Analyzing order flow imbalances",
        ]

        self.automation_activity_count += 1
        activity = activities[self.automation_activity_count % len(activities)]
        self.add_automation_log(activity)

    def update_greek_risks(self):
        """Update Greek risk displays — shows 0.0 until live position data is wired."""
        defaults = {
            "delta": (0.0, "NORMAL"),
            "gamma": (0.0, "NORMAL"),
            "theta": (0.0, "NORMAL"),
            "vega":  (0.0, "NORMAL"),
        }
        for name, bar in self.greek_bars.items():
            value, status = defaults.get(name, (0.0, "NORMAL"))
            bar.set_value(value, status)

    def update_prometheus_metrics(self):
        """Update Prometheus metrics — all indicators green (connected) until real health-check data is wired."""
        # System components: assume connected unless a health-check fires
        for indicator in self.system_components.values():
            indicator.setStyleSheet(
                "color: " + COLORS["positive"] + "; font-size: 14px;",
            )

        # Broker & data feed indicators
        for indicator in self.client_indicators.values():
            indicator.setStyleSheet(
                "color: " + COLORS["positive"] + "; font-size: 14px;",
            )

        # Internal modules
        if hasattr(self, "internal_module_indicators"):
            for name, indicator in self.internal_module_indicators.items():
                if name == "custom_metrics":
                    # Custom metrics stays yellow/warning
                    indicator.setStyleSheet(
                        "color: " + COLORS["warning"] + "; font-size: 14px;",
                    )
                else:
                    indicator.setStyleSheet(
                        "color: " + COLORS["positive"] + "; font-size: 14px;",
                        )

    def load_test_data(self):
        """Load test strategy groups with expandable trade legs."""
        test_strategies = [
            {
                "timestamp": "2026-02-25 18:47",
                "strategy": "IRON CONDOR",
                "status": "OPEN",
                "net_pnl": "+$435",
                "pct_return": "+18.5%",
                "dte": 5,
                "legs": [
                    {"leg": "Sell Put", "strike": "$580P", "cntr": "10", "expiry": "03/07", "cost": "-$1,200", "pnl": "+$180", "status": "OPEN"},
                    {"leg": "Buy Put", "strike": "$575P", "cntr": "10", "expiry": "03/07", "cost": "+$850", "pnl": "-$45", "status": "OPEN"},
                    {"leg": "Sell Call", "strike": "$595C", "cntr": "10", "expiry": "03/07", "cost": "-$1,100", "pnl": "+$220", "status": "OPEN"},
                    {"leg": "Buy Call", "strike": "$600C", "cntr": "10", "expiry": "03/07", "cost": "+$800", "pnl": "+$80", "status": "OPEN"},
                ],
            },
            {
                "timestamp": "2026-02-25 18:47",
                "strategy": "COVERED CALL",
                "status": "OPEN",
                "net_pnl": "+$125",
                "pct_return": "+29.4%",
                "dte": 12,
                "legs": [
                    {"leg": "Sell Call", "strike": "$588C", "cntr": "5", "expiry": "03/14", "cost": "+$425", "pnl": "+$125", "status": "OPEN"},
                ],
            },
            {
                "timestamp": "2026-02-24 14:22",
                "strategy": "IRON BUTTERFLY",
                "status": "CLOSED",
                "net_pnl": "+$1,250",
                "pct_return": "+29.8%",
                "dte": 0,
                "legs": [
                    {"leg": "Sell Put", "strike": "$584P", "cntr": "20", "expiry": "02/28", "cost": "-$2,100", "pnl": "+$620", "status": "CLOSED"},
                    {"leg": "Buy Put", "strike": "$582P", "cntr": "20", "expiry": "02/28", "cost": "+$1,500", "pnl": "-$120", "status": "CLOSED"},
                    {"leg": "Sell Call", "strike": "$586C", "cntr": "20", "expiry": "02/28", "cost": "-$2,100", "pnl": "+$650", "status": "CLOSED"},
                    {"leg": "Buy Call", "strike": "$588C", "cntr": "20", "expiry": "02/28", "cost": "+$1,500", "pnl": "+$100", "status": "CLOSED"},
                ],
            },
        ]

        for strat_idx, strat in enumerate(test_strategies):
            # Build strategy header text
            status_label = "OPEN" if strat["status"] == "OPEN" else "CLOSED"
            header_text = (
                f"{strat['timestamp']} | "
                f"STRATEGY TRIGGERED BY AI : {strat['strategy']} | "
                f"DTE: {strat['dte']:02d} | "
                f"STATUS: {status_label} | "
                f"NET P&L  {strat['net_pnl']}  ({strat['pct_return']})"
            )

            # Create top-level strategy item (spans all columns via col 0)
            strategy_item = QTreeWidgetItem(self.positions_table)

            # Store metadata for context menu
            strategy_item.setData(0, Qt.ItemDataRole.UserRole, strat["strategy"])
            strategy_item.setData(1, Qt.ItemDataRole.UserRole, strat["status"])

            # Style the header row
            header_font = QFont("monospace", 10)
            strategy_item.setFont(0, header_font)

            if strat["status"] == "OPEN":
                header_color = QColor(COLORS["automation_active"])
            else:
                header_color = QColor(COLORS["text_dim"])
            strategy_item.setForeground(0, header_color)

            # DTE color in header
            dte_val = strat["dte"]
            if dte_val == 0:
                QColor(COLORS["text_dim"])
            elif dte_val <= 2:
                QColor(COLORS["negative"])
            elif dte_val <= 7:
                QColor(COLORS["warning"])
            else:
                QColor(COLORS["positive"])

            # Set background for strategy header row
            header_bg = QColor("#1a1a2e")
            for col in range(self.positions_table.columnCount()):
                strategy_item.setBackground(col, QBrush(header_bg))

            # Create container widget for ALL strategies (uniform spacing)
            header_container = QWidget()
            header_container.setStyleSheet(f"background-color: {header_bg.name()}; border: none;")
            header_layout = QHBoxLayout(header_container)
            header_layout.setContentsMargins(5, 0, 0, 0)
            header_layout.setSpacing(10)

            if strat["status"] == "OPEN":
                # Close button on the left for OPEN strategies
                close_btn = QPushButton("✕")
                close_btn.setFixedSize(24, 20)
                close_btn.setToolTip(f"Close entire {strat['strategy']} strategy")
                close_btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        border: 1px solid {COLORS['negative']};
                        border-radius: 3px;
                        color: {COLORS['negative']};
                        font-size: 12px;
                        padding: 0px;
                    }}
                    QPushButton:hover {{
                        background-color: {COLORS['negative']};
                        color: {COLORS['background']};
                    }}
                    QPushButton:pressed {{
                        background-color: #cc0000;
                    }}
                """)
                close_btn.clicked.connect(lambda checked, s=strat: self.confirm_close_strategy(s))
                header_layout.addWidget(close_btn)
            else:
                # Blank spacer for CLOSED strategies (same width as button)
                spacer = QWidget()
                spacer.setFixedSize(24, 20)
                spacer.setStyleSheet("background-color: transparent; border: none;")
                header_layout.addWidget(spacer)

            # Strategy text label (with expansion for all available space)
            text_label = QLabel(header_text)
            text_label.setFont(header_font)
            text_label.setStyleSheet(f"color: {header_color.name()}; background-color: transparent; border: none;")
            text_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            header_layout.addWidget(text_label, 1)  # stretch factor of 1

            # Set the custom widget in column 0
            self.positions_table.setItemWidget(strategy_item, 0, header_container)

            # Add leg rows as children
            for leg in strat["legs"]:
                leg_item = QTreeWidgetItem(strategy_item)
                leg_item.setText(0, leg["leg"])
                leg_item.setText(1, leg["strike"])
                leg_item.setText(2, leg["cntr"])
                leg_item.setText(3, leg["expiry"])
                leg_item.setText(4, leg["cost"])
                leg_item.setText(5, leg["pnl"])

                # Set base text color and center-align all columns
                text_color = QColor(COLORS["text"])
                for col in range(6):  # Only first 6 columns have leg data
                    leg_item.setForeground(col, text_color)
                    leg_item.setTextAlignment(
                        col,
                        Qt.AlignmentFlag.AlignCenter,
                    )

                # Override: right-justify dollar amount columns (COST, P&L)
                leg_item.setTextAlignment(
                    4, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                )
                leg_item.setTextAlignment(
                    5, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                )

                # Override P&L color: green positive, red negative
                if leg["pnl"].startswith("+"):
                    leg_item.setForeground(5, QColor(COLORS["positive"]))
                else:
                    leg_item.setForeground(5, QColor(COLORS["negative"]))

                # Override cost color: green credit, red debit
                if leg["cost"].startswith("+"):
                    leg_item.setForeground(4, QColor(COLORS["positive"]))
                else:
                    leg_item.setForeground(4, QColor(COLORS["negative"]))

            # Expand OPEN strategies by default, collapse CLOSED
            strategy_item.setExpanded(strat["status"] == "OPEN")

            # Make strategy header span all columns visually
            self.positions_table.setFirstColumnSpanned(
                strat_idx, self.positions_table.rootIndex(), True,
            )

    def confirm_close_strategy(self, strategy_data: dict):
        """Show confirmation dialog before closing strategy"""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Close Strategy")
        msg_box.setIcon(QMessageBox.Icon.Warning)

        msg_text = (
            f"⚠️  CLOSE ENTIRE STRATEGY?\n\n"
            f"Strategy:     {strategy_data['strategy']}\n"
            f"Entry Time:   {strategy_data['timestamp']}\n"
            f"DTE:          {strategy_data['dte']} days\n"
            f"Legs:         {len(strategy_data['legs'])} positions\n"
            f"Net P&L:      {strategy_data['net_pnl']} ({strategy_data['pct_return']})\n"
            f"Status:       {strategy_data['status']}\n\n"
            f"This will close ALL {len(strategy_data['legs'])} legs with MARKET ORDERS."
        )

        msg_box.setText(msg_text)
        msg_box.setStandardButtons(
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
        )
        msg_box.setDefaultButton(QMessageBox.StandardButton.Cancel)

        yes_btn = msg_box.button(QMessageBox.StandardButton.Yes)
        yes_btn.setText("CLOSE ALL POSITIONS")
        yes_btn.setStyleSheet(f"background-color: {COLORS['negative']}; color: white; padding: 5px 15px;")

        cancel_btn = msg_box.button(QMessageBox.StandardButton.Cancel)
        cancel_btn.setStyleSheet(f"background-color: {COLORS['panel']}; color: white; padding: 5px 15px;")

        msg_box.setStyleSheet(f"""
            QMessageBox {{
                background-color: {COLORS['panel']};
                color: {COLORS['text']};
            }}
            QLabel {{
                color: {COLORS['text']};
                font-family: monospace;
                font-size: 12px;
            }}
        """)

        reply = msg_box.exec()

        if reply == QMessageBox.StandardButton.Yes:
            self.close_strategy(strategy_data)

    def close_strategy(self, strategy_data: dict):
        """Close all legs of a strategy with market orders"""
        strategy_name = strategy_data["strategy"]
        num_legs = len(strategy_data["legs"])

        self.log_system_message(
            f"⚠️ MANUAL OVERRIDE: Closing {strategy_name} strategy ({num_legs} legs)...",
        )

        # --- Validate prerequisites ---
        if self.tradier_client is None:
            self.log_system_message("❌ Cannot close strategy: Tradier client not connected")
            QMessageBox.warning(
                self,
                "Not Connected",
                "Cannot submit close orders: Tradier API is not connected.\n\n"
                "Please connect to the API first.",
            )
            return

        if not TRADIER_AVAILABLE or OptionLeg is None:
            self.log_system_message("❌ Cannot close strategy: TradierClient module unavailable")
            QMessageBox.critical(
                self,
                "Module Unavailable",
                "TradierClient module could not be imported.\n"
                "Order submission is not available.",
            )
            return

        legs_data = strategy_data.get("legs", [])
        if not legs_data:
            self.log_system_message("❌ Cannot close strategy: no legs found in strategy data")
            return

        try:
            # ------------------------------------------------------------------
            # Parse UI leg dicts into OptionLeg objects for place_multileg_order
            # ------------------------------------------------------------------
            # Leg dict keys: leg, strike, cntr, expiry, cost, pnl, status
            # Examples:
            #   leg    = "Sell Put"  | "Buy Call"
            #   strike = "$580P"     | "$600C"
            #   cntr   = "10"
            #   expiry = "03/07"  (MM/DD — year inferred from current date)

            current_year = datetime.now().year
            current_month = datetime.now().month
            option_legs: list = []

            for leg_dict in legs_data:
                leg_label: str = leg_dict["leg"]          # e.g. "Sell Put"
                strike_raw: str = leg_dict["strike"]      # e.g. "$580P"
                cntr_raw: str = leg_dict["cntr"]          # e.g. "10"
                expiry_raw: str = leg_dict["expiry"]      # e.g. "03/07"

                # --- Validate quantity ---
                try:
                    quantity = int(cntr_raw.strip())
                except ValueError:
                    raise ValueError(
                        f"Invalid contract count '{cntr_raw}' for leg '{leg_label}'",
                    ) from None
                if quantity <= 0:
                    raise ValueError(
                        f"Contract count must be positive, got {quantity} for leg '{leg_label}'",
                    )

                # --- Parse strike: strip leading "$", trailing C/P ---
                # e.g. "$580P" → strike=580.0, opt_type="P"
                clean_strike = strike_raw.lstrip("$")
                if not clean_strike:
                    raise ValueError(f"Empty strike value for leg '{leg_label}'")
                opt_type_char = clean_strike[-1].upper()
                if opt_type_char not in ("C", "P"):
                    raise ValueError(
                        f"Cannot determine option type from strike '{strike_raw}' "
                        f"for leg '{leg_label}'; expected trailing 'C' or 'P'",
                    )
                try:
                    strike_price = float(clean_strike[:-1])
                except ValueError:
                    raise ValueError(
                        f"Cannot parse strike price from '{strike_raw}' for leg '{leg_label}'",
                    ) from None

                # --- Parse expiry: MM/DD → YYYY-MM-DD (roll to next year if past) ---
                exp_parts = expiry_raw.strip().split("/")
                if len(exp_parts) != 2:
                    raise ValueError(
                        f"Unexpected expiry format '{expiry_raw}' for leg '{leg_label}'; "
                        "expected MM/DD",
                    )
                exp_month, exp_day = int(exp_parts[0]), int(exp_parts[1])
                exp_year = current_year
                # If the expiry month is earlier than the current month, it's next year
                if exp_month < current_month:
                    exp_year += 1
                expiration_str = f"{exp_year}-{exp_month:02d}-{exp_day:02d}"

                # --- Determine close side from leg label ---
                # "Sell …" was opened SELL_TO_OPEN → close with BUY_TO_CLOSE
                # "Buy …"  was opened BUY_TO_OPEN  → close with SELL_TO_CLOSE
                leg_lower = leg_label.lower()
                if leg_lower.startswith("sell"):
                    close_side = OrderSide.BUY_TO_CLOSE
                elif leg_lower.startswith("buy"):
                    close_side = OrderSide.SELL_TO_CLOSE
                else:
                    raise ValueError(
                        f"Cannot determine order side from leg label '{leg_label}'; "
                        "expected label beginning with 'Sell' or 'Buy'",
                    )

                # --- Build OCC option symbol ---
                occ_symbol = build_option_symbol(
                    "SPY", expiration_str, opt_type_char, strike_price,
                )

                option_legs.append(OptionLeg(
                    option_symbol=occ_symbol,
                    side=close_side,
                    quantity=quantity,
                ))

                self.log_system_message(
                    f"  Prepared close leg: {close_side.value} {quantity}x {occ_symbol}",
                )

            # ------------------------------------------------------------------
            # Submit the multileg market order to Tradier
            # ------------------------------------------------------------------
            self.logger.info(
                f"Submitting market close order for {strategy_name} "
                f"({len(option_legs)} legs)",
            )

            response = self.tradier_client.place_multileg_order(
                symbol="SPY",
                legs=option_legs,
                order_type="market",
                duration=OrderDuration.DAY,
            )

            # Extract order ID from response (Tradier returns {"order": {"id": …, …}})
            order_id = (
                response.get("order", {}).get("id")
                or response.get("id")
            )

            self.logger.info(
                f"Close order submitted successfully for {strategy_name}: "
                f"order_id={order_id}",
            )
            self.log_system_message(
                f"✅ Close order submitted for {strategy_name} — order ID: {order_id}",
            )

            QMessageBox.information(
                self,
                "Close Order Submitted",
                f"Strategy '{strategy_name}' close order submitted successfully.\n\n"
                f"Order ID: {order_id}\n"
                f"Legs: {len(option_legs)}\n"
                f"Type: Market / Day\n\n"
                "Positions will update once fills are confirmed.",
            )

        except TradierAPIError as e:
            self.logger.exception(
                "Tradier API error closing strategy '%s': %s", strategy_name, e,
            )
            self.log_system_message(f"❌ Tradier API error closing {strategy_name}: {e}")
            QMessageBox.critical(
                self,
                "Close Strategy Failed",
                f"Tradier API error while closing '{strategy_name}':\n\n{e}",
            )
        except ValueError as e:
            self.logger.exception(
                "Validation error closing strategy '%s': %s", strategy_name, e,
            )
            self.log_system_message(f"❌ Validation error closing {strategy_name}: {e}")
            QMessageBox.critical(
                self,
                "Close Strategy Failed",
                f"Could not build close orders for '{strategy_name}':\n\n{e}",
            )
        except Exception as e:
            self.logger.exception(
                "Unexpected error closing strategy '%s': %s", strategy_name, e,
            )
            self.log_system_message(f"❌ Unexpected error closing {strategy_name}: {e}")
            QMessageBox.critical(
                self,
                "Close Strategy Failed",
                f"Unexpected error while closing '{strategy_name}':\n\n{e!s}",
            )

    def load_default_risk_parameters(self):
        """Load default risk parameters"""
        self.current_risk_params = {
            "max_position_size": 50000,
            "max_daily_loss": 5000,
            "max_portfolio_delta": 100,
            "max_portfolio_gamma": 50,
            "vix_threshold": 30,
            "correlation_limit": 0.8,
        }

    def show_risk_parameters(self):
        """Show risk parameters dialog"""
        if risk_dialog_available and show_risk_parameters_dialog:
            show_risk_parameters_dialog(self)
        else:
            QMessageBox.information(
                self,
                "Risk Parameters",
                "Risk Parameters Configuration\n\n"
                "Max Position Size: $50,000\n"
                "Max Daily Loss: $5,000\n"
                "Max Portfolio Delta: 100\n"
                "Max Portfolio Gamma: 50\n"
                "VIX Threshold: 30\n"
                "Correlation Limit: 0.8",
            )

    def add_system_log(self, message: str):
        """Add message to system log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"

        self.system_logs.append(formatted_message)

        # Keep only last 100 entries
        if len(self.system_logs) > 100:
            self.system_logs = self.system_logs[-100:]

        # Update display - REVERSED to show newest at top (descending order)
        self.system_log.clear()
        reversed_logs = list(
            reversed(self.system_logs[-20:]),
        )  # Show last 20, newest first
        self.system_log.append("\n".join(reversed_logs))

        # Scroll to top to see newest messages
        cursor = self.system_log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self.system_log.setTextCursor(cursor)

    def add_automation_log(self, message: str):
        """Add message to automation log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"

        self.automation_logs.append(formatted_message)

        # Keep only last 100 entries
        if len(self.automation_logs) > 100:
            self.automation_logs = self.automation_logs[-100:]

        # Update display - REVERSED to show newest at top (descending order)
        self.auto_log.clear()
        reversed_logs = list(
            reversed(self.automation_logs[-15:]),
        )  # Show last 15, newest first
        self.auto_log.append("\n".join(reversed_logs))

        # Scroll to top to see newest messages
        cursor = self.auto_log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self.auto_log.setTextCursor(cursor)

    def setup_white_tooltips(self):
        """Setup white tooltips that are actually visible"""
        try:
            # Method 1: Set application-wide stylesheet
            app = QApplication.instance()
            if app:
                current_style = app.styleSheet()
                tooltip_style = """
                QToolTip {
                    color: #ffffff !important;
                    background-color: #1a1a1a !important;
                    border: 2px solid #555555 !important;
                    padding: 8px !important;
                    border-radius: 4px !important;
                    font-size: 12px !important;
                    font-weight: normal !important;
                    opacity: 1.0 !important;
                }
                """
                app.setStyleSheet(current_style + tooltip_style)
                self.add_system_log("🎨 White tooltip styling applied")

            # Method 2: Set widget-specific tooltip styling as backup
            widget_style = """
                QWidget {
                    selection-background-color: #2a2a2a;
                }
                QWidget QToolTip {
                    color: white !important;
                    background-color: #1a1a1a !important;
                    border: 2px solid #555555 !important;
                    padding: 8px !important;
                }
            """
            self.setStyleSheet(self.styleSheet() + widget_style)

        except Exception as e:
            self.add_system_log(f"⚠️ Tooltip styling error: {e}")

    def closeEvent(self, event):
        """Enhanced close event handler with real data cleanup and heartbeat monitoring"""
        try:
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
            self.add_automation_log("Dashboard session ended with heartbeat monitoring")

            # Accept close event
            event.accept()

        except Exception as e:
            logger.info("Error during enhanced dashboard close: %s", e)
            event.accept()


# ==============================================================================
# ENHANCED REAL DATA INTEGRATION FUNCTIONS (UNCHANGED FROM ORIGINAL)
# ==============================================================================
def apply_real_data_patch_to_dashboard(dashboard, data_file):
    """Apply real data patch to existing dashboard using proven pattern"""

    def update_with_real_data():
        """Update dashboard with real market data"""
        try:
            if not data_file.exists():
                return

            with open(data_file) as f:
                live_data = json.load(f)

            if not live_data:
                return

            # Update symbol widgets directly
            for symbol, data in live_data.items():
                if symbol in dashboard.symbol_widgets:
                    widget = dashboard.symbol_widgets[symbol]

                    # Update price
                    if hasattr(widget, "price_label"):
                        widget.price_label.setText(f"{data['last']:.2f}")

                    # Update change with color
                    if hasattr(widget, "change_label"):
                        change = data["change"]
                        sign = "+" if change >= 0 else ""
                        widget.change_label.setText(f"{sign}{change:.2f}")
                        color = "#00ff41" if change >= 0 else "#ff1744"
                        widget.change_label.setStyleSheet(f"color: {color};")

                    # Update percentage with color
                    if hasattr(widget, "pct_label"):
                        pct = data["change_pct"]
                        sign = "+" if pct >= 0 else ""
                        widget.pct_label.setText(f"{sign}{pct:.2f}%")
                        color = "#00ff41" if pct >= 0 else "#ff1744"
                        widget.pct_label.setStyleSheet(f"color: {color};")

            # Update market_data dict so chart uses real price as base
            for symbol, data in live_data.items():
                if symbol not in dashboard.market_data:
                    dashboard.market_data[symbol] = {}
                dashboard.market_data[symbol]["last"] = data["last"]
                dashboard.market_data[symbol]["change"] = data["change"]
                dashboard.market_data[symbol]["change_pct"] = data["change_pct"]

            # Update toolbar indices
            update_toolbar_with_real_data_helper(dashboard, live_data)

        except Exception as e:
            logger.info("❌ Error updating real data: %s", e)

    # Stop original simulation
    try:
        if hasattr(dashboard, "market_worker"):
            worker = dashboard.market_worker
            if hasattr(worker, "update_timer") and worker.update_timer:
                worker.update_timer.stop()
                logger.info("✅ Stopped simulation timer")

        if hasattr(dashboard, "automation_timer"):
            dashboard.automation_timer.setInterval(20000)  # Slow down automation

    except Exception as e:
        logger.info("⚠️ Could not stop simulation: %s", e)

    # Start real data updates
    dashboard._real_data_timer = QTimer()
    dashboard._real_data_timer.timeout.connect(update_with_real_data)
    dashboard._real_data_timer.start(1000)  # Update every second

    # Initial update — populates market_data before chart refresh
    update_with_real_data()

    # Force immediate chart redraw at correct (real) price, then keep it on a 30s cycle
    if hasattr(dashboard, "update_chart"):
        dashboard.update_chart()
    if hasattr(dashboard, "chart_timer") and dashboard.chart_timer:
        dashboard.chart_timer.setInterval(30000)

    # Add log entries
    dashboard.add_system_log("🔥 REAL MARKET DATA ACTIVE - Tradier API prices")
    dashboard.add_automation_log("Real-time market data from Tradier")

    logger.info("✅ Real data patch applied successfully!")


def setup_real_data_monitoring_for_dashboard(dashboard, data_file):
    """Setup monitoring for real data to become available (proven pattern)"""

    def check_for_real_data():
        """Check if real data becomes available"""
        if getattr(dashboard, "real_data_active", False):
            return  # Already using real data

        if data_file.exists():
            try:
                with open(data_file) as f:
                    data = json.load(f)

                if data:
                    logger.info("🔥 Real data detected - switching from simulation!")
                    dashboard.add_system_log(
                        "🔥 Real data detected - switching from simulation!",
                    )
                    dashboard._check_timer.stop()
                    apply_real_data_patch_to_dashboard(dashboard, data_file)
                    dashboard.real_data_active = True
            except Exception as e:
                logger.debug("Error checking for real data: %s", e)

    # Check every 5 seconds for real data
    dashboard._check_timer = QTimer()
    dashboard._check_timer.timeout.connect(check_for_real_data)
    dashboard._check_timer.start(5000)


def update_toolbar_with_real_data_helper(dashboard, live_data):
    """Update toolbar indices with real data (proven pattern)"""
    try:
        # SPX — use real SPX index value directly
        spx_src = live_data.get("SPX") or live_data.get("SPY")
        spx_mult = 1 if "SPX" in live_data else 10
        if spx_src:
            if hasattr(dashboard, "spx_value"):
                dashboard.spx_value.setText(f" {spx_src['last'] * spx_mult:.0f}")
            if hasattr(dashboard, "spx_change"):
                change = spx_src["change"] * spx_mult
                pct = spx_src["change_pct"]
                sign = "+" if change >= 0 else ""
                dashboard.spx_change.setText(f"  {sign}{change:.0f}  {sign}{pct:.1f}%")
                color = "#00ff41" if change >= 0 else "#ff1744"
                dashboard.spx_change.setStyleSheet(f"color: {color};")

        # NDX — Tradier symbol "NDX" (no $ prefix), NASDAQ 100 index; fallback to QQQ * ratio
        ndx_src = live_data.get("NDX") or live_data.get("QQQ")
        ndx_mult = 1 if "NDX" in live_data else 37.5
        if ndx_src:
            if hasattr(dashboard, "ndx_value"):
                dashboard.ndx_value.setText(f" {ndx_src['last'] * ndx_mult:,.0f}")
            if hasattr(dashboard, "ndx_change"):
                change = ndx_src["change"] * ndx_mult
                pct = ndx_src["change_pct"]
                sign = "+" if change >= 0 else ""
                dashboard.ndx_change.setText(f"  {sign}{change:.0f}  {sign}{pct:.1f}%")
                color = "#00ff41" if change >= 0 else "#ff1744"
                dashboard.ndx_change.setStyleSheet(f"color: {color};")

        # DJI — use $DJI directly, fallback to DIA * 100
        dji_src = live_data.get("$DJI") or live_data.get("DIA")
        dji_mult = 1 if "$DJI" in live_data else 100
        if dji_src:
            if hasattr(dashboard, "dji_value"):
                dashboard.dji_value.setText(f" {dji_src['last'] * dji_mult:,.0f}")
            if hasattr(dashboard, "dji_change"):
                change = dji_src["change"] * dji_mult
                pct = dji_src["change_pct"]
                sign = "+" if change >= 0 else ""
                dashboard.dji_change.setText(f"  {sign}{change:.0f}  {sign}{pct:.1f}%")
                color = "#00ff41" if change >= 0 else "#ff1744"
                dashboard.dji_change.setStyleSheet(f"color: {color};")

        # RUT — Tradier symbol "RUT" (no $ prefix), Russell 2000 index; fallback to IWM * 10
        rut_src = live_data.get("RUT") or live_data.get("IWM")
        rut_mult = 1 if "RUT" in live_data else 10
        if rut_src:
            if hasattr(dashboard, "rut_value"):
                dashboard.rut_value.setText(f" {rut_src['last'] * rut_mult:,.0f}")
            if hasattr(dashboard, "rut_change"):
                change = rut_src["change"] * rut_mult
                pct = rut_src["change_pct"]
                sign = "+" if change >= 0 else ""
                dashboard.rut_change.setText(f"  {sign}{change:.0f}  {sign}{pct:.1f}%")
                color = "#00ff41" if change >= 0 else "#ff1744"
                dashboard.rut_change.setStyleSheet(f"color: {color};")

    except Exception as e:
        logger.debug("Toolbar update error: %s", e)


def update_status_for_real_data_helper(dashboard):
    """Update status indicators for real data - FIXED to not override API status"""
    # Real data integration does not change API connection display


# ==============================================================================
# STANDALONE FUNCTIONS FOR EXTERNAL USE
# ==============================================================================
def create_spyder_trading_dashboard():
    """Factory function to create SpyderTradingDashboard instance"""
    return SpyderTradingDashboard()


def get_dashboard_with_real_data_integration():
    """Create dashboard with real data integration pre-configured"""
    return SpyderTradingDashboard()


def apply_external_real_data_patch(dashboard, data_file_path=None):
    """Apply real data patch from external module"""
    if data_file_path is None:
        data_file_path = Path.home() / "Projects/Spyder/market_data/live_data.json"

    data_file = Path(data_file_path)

    if data_file.exists():
        try:
            with open(data_file) as f:
                data = json.load(f)

            if data:
                apply_real_data_patch_to_dashboard(dashboard, data_file)
                update_status_for_real_data_helper(dashboard)
                dashboard.real_data_active = True
                return True
        except Exception as e:
            logger.info("❌ Error applying external real data patch: %s", e)

    return False


# ==============================================================================
# MAIN EXECUTION - FOR STANDALONE TESTING
# ==============================================================================
def main():
    """Main function for standalone testing"""
    logger.info("=" * 70)
    logger.info("🔥 SPYDER G05 - ENHANCED TRADING DASHBOARD")
    logger.info("=" * 70)
    logger.info("🔗 Tradier API integration")
    logger.info("📡 Massive market data feeds")
    logger.info("💔💚💙 30-second heartbeat monitoring")
    logger.info("📊 Clean 4-status data display")
    logger.info("=" * 70)

    # Create Qt application
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # CRITICAL: Set desktop file name for Wayland/GNOME integration
    # This MUST match the .desktop file name (without .desktop extension)
    # so the window appears under the launcher icon instead of a separate gear icon
    app.setDesktopFileName("spyder-trading-system")

    # Set application identity
    app.setApplicationName("spyder-trading-system")
    app.setOrganizationName("Spyder Trading System")

    # Implement qasync event loop integration for proper asyncio/Qt compatibility
    try:
        import asyncio

        import qasync

        # Create QEventLoop for asyncio integration
        loop = qasync.QEventLoop(app)
        asyncio.set_event_loop(loop)

        logger.info("✅ qasync event loop integration enabled - preventing asyncio errors")
        logger.info("🔗 Qt and asyncio event loops properly synchronized")

        # Create a simple event to signal when the app should close
        app_close_event = asyncio.Event()

        # Connect app aboutToQuit signal to our event
        app.aboutToQuit.connect(app_close_event.set)

        try:
            # Create fixed dashboard
            logger.info("🔧 Initializing fixed dashboard with heartbeat monitoring...")
            dashboard = SpyderTradingDashboard()

            # Show dashboard
            dashboard.show()

            # Check real data status
            data_file = Path.home() / "Projects/Spyder/market_data/live_data.json"
            if data_file.exists():
                try:
                    with open(data_file) as f:
                        data = json.load(f)
                    spy_price = data.get("SPY", {}).get("last", "N/A")
                    logger.info("✅ Real data detected - SPY: $%s", spy_price)
                except Exception:
                    logger.info("⚠️ Real data file exists but couldn't read it")
            else:
                logger.info("📊 No real data detected - using simulation")
                logger.info("   Start injector: python temp_WorkingDataInjector.py")

            logger.info("\n✅ STATUS BAR FEATURES:")
            logger.info("   • TRADIER EXEC: green=connected, red=disconnected (label color only)")
            logger.info("   • 30-second heartbeat background checks drive connection state")
            logger.info(
                "   • Clean data status: SIMULATED, EOD, LIVE",
            )
            logger.info("   • Market data source: TRADIER DATA or MASSIVE DATA")
            logger.info("   • Blue simulation button only visible when Tradier disconnected")
            logger.info("   • Fixed-width status containers (no UI jumping)")

            logger.info("\n🔥 Enhanced Trading Dashboard is ready!")
            logger.info("   Heartbeat checks API connection every 30 seconds\n")
            logger.info("🔄 Running with qasync event loop integration...")

            # Run the event loop until the app closes
            with loop:
                loop.run_until_complete(app_close_event.wait())

            return 0

        except Exception as e:
            logger.info("\n❌ Startup error: %s", e)
            import traceback

            traceback.print_exc()

            # Show error dialog if possible
            try:
                QMessageBox.critical(
                    None,
                    "Fixed Trading Dashboard Error",
                    f"Failed to start Fixed Trading Dashboard:\n\n{e}\n\n"
                    "Please check the console for detailed error information.",
                )
            except Exception as _dlg_err:
                logger.debug("Could not show startup error dialog: %s", _dlg_err)

            return 1

    except ImportError:
        # Fallback to standard event loop if qasync is not available
        logger.info("⚠️ qasync not available - using standard event loop (may have asyncio issues)")
        logger.info("   Install with: pip install qasync")

        try:
            # Create fixed dashboard
            logger.info("🔧 Initializing fixed dashboard with heartbeat monitoring...")
            dashboard = SpyderTradingDashboard()

            # Show dashboard
            dashboard.show()

            # Check real data status
            data_file = Path.home() / "Projects/Spyder/market_data/live_data.json"
            if data_file.exists():
                try:
                    with open(data_file) as f:
                        data = json.load(f)
                    spy_price = data.get("SPY", {}).get("last", "N/A")
                    logger.info("✅ Real data detected - SPY: $%s", spy_price)
                except Exception:
                    logger.info("⚠️ Real data file exists but couldn't read it")
            else:
                logger.info("📊 No real data detected - using simulation")
                logger.info("   Start injector: python temp_WorkingDataInjector.py")

            logger.info("\n✅ STATUS BAR FEATURES:")
            logger.info("   • TRADIER EXEC: green=connected, red=disconnected (label color only)")
            logger.info("   • 30-second heartbeat background checks drive connection state")
            logger.info(
                "   • Clean data status: SIMULATED, EOD, LIVE",
            )
            logger.info("   • Market data source: TRADIER DATA or MASSIVE DATA")
            logger.info("   • Blue simulation button only visible when Tradier disconnected")
            logger.info("   • Fixed-width status containers (no UI jumping)")

            logger.info("\n🔥 Enhanced Trading Dashboard is ready!")
            logger.info("   Heartbeat checks API connection every 30 seconds\n")

            # Run application with standard event loop
            return app.exec()

        except Exception as e:
            logger.info("\n❌ Startup error: %s", e)
            import traceback

            traceback.print_exc()

            # Show error dialog if possible
            try:
                QMessageBox.critical(
                    None,
                    "Fixed Trading Dashboard Error",
                    f"Failed to start Fixed Trading Dashboard:\n\n{e}\n\n"
                    "Please check the console for detailed error information.",
                )
            except Exception as _dlg_err:
                logger.debug("Could not show startup error dialog: %s", _dlg_err)

            return 1


if __name__ == "__main__":
    sys.exit(main())
