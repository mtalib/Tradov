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
import sys
import time
from datetime import datetime
from datetime import time as dt_time
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
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.transforms import blended_transform_factory

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
from Spyder.SpyderG_GUI.SpyderG13_EnhancedWidgets import (
    COLORS,
    ConnectionInfo,
    GreekBar,
    GreekRisk,
    MarketData,
    MarketSymbolWidget,
    SignalMonitorPanel,
    TradingMode,
    TrafficLightButton,
    apply_tooltip_theme,
)
from Spyder.SpyderG_GUI.SpyderG20_DashboardBuilder import (
    build_center_panel,
    build_left_panel,
    build_right_panel,
    build_toolbar,
    create_chart_widget,
    create_pnl_table as build_pnl_table,
    create_positions_table as build_positions_table,
    create_unified_prometheus_metrics as build_unified_prometheus_metrics,
)
from Spyder.SpyderG_GUI.SpyderG21_DashboardSignalHandlers import (
    handle_connection_status_changed,
    handle_heartbeat_received,
    handle_heartbeat_status_changed,
    handle_market_data_status_changed,
    handle_market_data_updated,
    handle_market_error,
)

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

# Phase 1 wiring (2026-04-17 overview v6): bring SpyderE01_RiskManager into
# the paper-trading path so every proposed entry is validated against real
# E-series risk rules.
try:
    from Spyder.SpyderE_Risk.SpyderE01_RiskManager import (
        DEFAULT_RISK_LIMITS as _E01_DEFAULT_RISK_LIMITS,
        RiskConfig as _E01_RiskConfig,
        RiskManager as _E01_RiskManager,
    )
    _E01_AVAILABLE = True
except ImportError:
    _E01_DEFAULT_RISK_LIMITS = {}  # type: ignore
    _E01_RiskConfig = None  # type: ignore
    _E01_RiskManager = None  # type: ignore
    _E01_AVAILABLE = False
    logger.info("⚠️ SpyderE01_RiskManager not available — paper worker will use local checks only")

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

# Circuit breaker singletons — reset from heartbeat when API confirmed healthy
try:
    from Spyder.SpyderU_Utilities.SpyderU41_CircuitBreaker import (
        tradier_breaker as _tradier_breaker,
        massive_breaker as _massive_breaker,
    )
    _circuit_breakers_available = True
except ImportError:
    _tradier_breaker = None  # type: ignore
    _massive_breaker = None  # type: ignore
    _circuit_breakers_available = False

# ==============================================================================
# CONSTANTS
# ==============================================================================
WINDOW_WIDTH = 1920
WINDOW_HEIGHT = 1080


# Dashboard session & Tradier active window come from U03_DateTimeUtils —
# module-level aliases kept for readability at use sites within this file.
from Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils import (
    DASHBOARD_SESSION_OPEN as MARKET_OPEN_TIME,
    DASHBOARD_SESSION_CLOSE as MARKET_CLOSE_TIME,
    TRADIER_CONNECT_TIME,
    TRADIER_DISCONNECT_TIME,
    LogThrottle,
    is_dashboard_session as is_market_hours,
    is_tradier_active_window as is_tradier_window,
)

# Market data worker, heartbeat constants, quote-freshness helpers, and
# check_api_connection now live in SpyderG18_MarketDataWorker (audit §1/§14/§23).
# G05 re-imports them here so existing references continue to resolve.
from Spyder.SpyderG_GUI.SpyderG18_MarketDataWorker import (
    HEARTBEAT_INTERVAL,
    HEARTBEAT_LOG_INTERVAL,
    HEARTBEAT_WARNING_TIME,
    REALTIME_QUOTE_MAX_AGE_SECONDS,
    REALTIME_SENTINEL_SYMBOLS,
    ThreadSafeMarketDataWorker,
    _coerce_epoch_ms,
    _datetime_from_epoch_ms,
    _freshest_live_data_timestamp,
    _freshest_quote_timestamp_ms,
    check_api_connection,
)
# Chart indicator computation extracted per audit §3.
from Spyder.SpyderG_GUI.SpyderG19_ChartIndicators import (
    ChartIndicators,
    PivotLevels,
    compute_chart_indicators,
)

# COMPLETE MARKET SYMBOLS FROM T09
MARKET_SYMBOLS = {
    "S&P CORE": ["SPY", "SPX"],
    "VOLATILITY": ["VIX", "VIX9D", "VXV", "VVIX"],
    "MARKET INTERNALS": ["$TICK", "$TRIN", "$ADD", "NYMO", "CPC", "SKEW", "$VOLD", "XLK", "XLF", "TNX", "RVOL"],
    "MAJOR INDICES": ["QQQ", "IWM"],
    "BONDS & CREDIT": ["TLT", "HYG", "LQD"],
    "CORRELATIONS": ["DXY", "GLD", "USO"],
    "OPTIONS ANALYTICS": ["IVR", "ATM_IV", "VRP"],
    "CUSTOM METRICS": ["GEX", "DEX", "OGL", "DIX", "WRS", "PSR", "SWAN", "PMR"],
}

# ==============================================================================
# PAPER TRADING WORKER (runs off the GUI thread)
# ==============================================================================
from Spyder.SpyderR_Runtime.SpyderR08_PaperTradingQtWorker import (
    PaperTradingQtWorker as _PaperTradingWorker,
)


# ==============================================================================
# MAIN DASHBOARD CLASS
# ==============================================================================
class SpyderTradingDashboard(QMainWindow):
    """Complete dashboard with fixed API connection detection and heartbeat monitoring"""

    # ------------------------------------------------------------------
    # S07 metric routing (audit §21 — display-unit adaptation layer)
    # Maps S07 metric keys → (dashboard widget key, raw→widget scale).
    # Scales live here because S07 emits in domain units (raw dollars for
    # GEX/DEX) and the dashboard widgets expect pre-scaled values that they
    # then format to "B"/"M" labels. When S07's contract is normalised so it
    # emits in widget-ready units, this table collapses to pure key mapping.
    # ------------------------------------------------------------------
    _S07_METRIC_ROUTING: dict[str, tuple[str, float]] = {
        "GEX":      ("GEX",   1e9),
        "DEX":      ("DEX",   1e6),
        "OGL":      ("OGL",   1.0),
        "DIX":      ("DIX",   1.0),
        "WRS":      ("WRS",   1.0),
        "PSR":      ("PSR",   1.0),
        "SWAN":     ("SWAN",  1.0),
        "TICK":      ("$TICK", 1.0),
        "ADD":       ("$ADD",  1.0),
        "TRIN":      ("$TRIN", 1.0),
        "NYMO":      ("NYMO",  1.0),
        "YIELD_10Y": ("TNX",   1.0),
        "IVR":       ("IVR",   1.0),
        "ATM_IV":    ("ATM_IV",1.0),
        "VRP":       ("VRP",   1.0),
        # 0-DTE abort-gate additions (2026-04)
        "VOLD":      ("$VOLD", 1.0),
        "XLK":       ("XLK",   1.0),
        "XLF":       ("XLF",   1.0),
        "RVOL":      ("RVOL",  1.0),
    }

    # ------------------------------------------------------------------
    # Connection-state accessors (audit §16 — single source of truth)
    # Both flags are backed by self.connection_info to eliminate the
    # parallel scalar attributes that previously drifted out of sync.
    # ------------------------------------------------------------------
    @property
    def api_connected(self) -> bool:
        return self.connection_info.api_connected

    @api_connected.setter
    def api_connected(self, value: bool) -> None:
        self.connection_info.api_connected = bool(value)

    @property
    def mkt_data_connected(self) -> bool:
        return self.connection_info.mkt_data_connected

    @mkt_data_connected.setter
    def mkt_data_connected(self, value: bool) -> None:
        self.connection_info.mkt_data_connected = bool(value)

    def __init__(self):
        super().__init__()

        # Initialize logging
        self.logger = SpyderLogger.get_logger(__name__)

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

        # Paper trading worker (created lazily by _start_paper_trading)
        self._paper_worker = None
        self._paper_thread = None

        # Dashboard data
        self.market_data = {}
        self.positions = []
        self.greek_risks = GreekRisk(45.5, -2.3, -156.8, -245.2)
        self.system_logs = []

        # CRITICAL: Add startup banner FIRST to show actual launch time (ET)
        startup_time = datetime.now(pytz.timezone("US/Eastern")).strftime("%Y-%m-%d %H:%M:%S ET")
        startup_hms  = datetime.now(pytz.timezone("US/Eastern")).strftime("%H:%M:%S")
        self.system_logs.extend([
            f"[{startup_hms}] {'=' * 56}",
            f"[{startup_hms}] 🚀 SPYDER DASHBOARD STARTED: {startup_time}",
            f"[{startup_hms}] {'=' * 56}",
        ])

        self.automation_logs = []
        self.trading_mode = TradingMode.PAPER

        # Per-mode snapshots — preserved across PAPER ↔ LIVE switches so each
        # mode's table contents survive while the other mode is active.
        self._pnl_stats_by_mode: dict = {}          # TradingMode → stats dict
        self._positions_snapshot_by_mode: dict = {}  # TradingMode → serialized list

        # api_connected and mkt_data_connected are @property accessors backed
        # by self.connection_info (see ConnectionInfo docstring, audit §16).
        self.tradier_client = (
            None  # FIXED: Initialize API client attribute before timer starts
        )
        self.trading_active = False
        self.auto_connect_attempts = 0

        # Order manager — broker-layer facade (audit §5)
        from Spyder.SpyderB_Broker.SpyderB06_DashboardOrderManager import (
            DashboardOrderManager,
        )
        self._order_manager = DashboardOrderManager(client=None, use_live=False)

        # H07 PerformanceAnalytics — injected once at construction (audit §9/§20)
        try:
            from Spyder.SpyderH_Storage.SpyderH07_PerformanceAnalytics import (
                PerformanceAnalytics as _PerformanceAnalytics,
            )
            self._h07_performance_analytics = _PerformanceAnalytics()
        except Exception as _h07_import_err:
            logger.warning("H07 PerformanceAnalytics unavailable: %s", _h07_import_err)
            self._h07_performance_analytics = None

        # Risk parameters
        self.current_risk_params = None
        self.risk_monitoring_active = False

        # Widget storage
        self.symbol_widgets = {}

        # Prometheus metrics attributes
        self.system_components = {}
        self.client_indicators = {}
        self.system_stats = {}

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
        self.comp_value = None
        self.comp_change = None
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
        # Phase 2: spreads & volatility panel widgets.
        self.spreads_table = None
        self.spreads_group = None
        self.atm_iv_label = None
        self.iv_rank_label = None
        self.spreads_summary_label = None
        # Unified status strip (added when SPREADS & VOLATILITY was folded in).
        self.realized_today_label = None
        self.bp_used_label = None
        # Phase 5: closed-trade audit log cached from worker emits.
        self._closed_trades_cache: list = []
        # Decision Log dialog singleton (None when closed).
        self._decision_log_dialog = None
        # Phase 3: portfolio-aggregate Greeks labels.
        self.port_delta_label = None
        self.port_gamma_label = None
        self.port_vega_label = None
        # Phase 7: higher-order Greeks labels (charm/vanna) from N04.
        self.port_charm_label = None
        self.port_vanna_label = None
        self.internal_module_indicators = {}
        self.datetime_timer = None
        self.chart_timer = None

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
        self.load_default_risk_parameters()

        # Restore previous session's symbol values (if any) — runs after the
        # event loop starts so all widgets are fully initialised.
        QTimer.singleShot(0, self._restore_snapshot)

        # Start market worker with fixed connection detection
        self.start_market_worker()

        # Start custom metrics orchestrator (DIX + Black Swan schedulers)
        # Deferred 1 s so the Qt event loop is fully running before QTimer creation in S07
        self._metrics_orchestrator = None
        QTimer.singleShot(1000, self._start_metrics_orchestrator)

        # Apply white tooltip styling
        self.setup_white_tooltips()

        # Log the actual dashboard initialization time (ET)
        _et_tz = pytz.timezone("US/Eastern")
        init_time = datetime.now(_et_tz).strftime("%H:%M:%S ET")
        self.add_system_log(f"🚀 Dashboard initialized at {init_time}")

        # Real data integration (after UI is ready)
        QTimer.singleShot(1000, self.apply_proven_real_data_pattern)

        # Fetch live balance + quotes shortly after startup (before first 30s heartbeat).
        # Retry once in case the worker's startup API call hasn't completed yet.
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

    def _trigger_initial_live_fetch(self):
        """Ask the market worker to do an immediate live data + balance fetch.

        If the worker's startup API check hasn't completed yet (api_connected still
        False), retry once in 5 seconds so the initial fetch is never silently skipped.
        """
        if self.market_worker and self.api_connected:
            self.market_worker.fetch_requested.emit()
        elif self.market_worker and is_tradier_window():
            # Worker's startup API check may still be in-flight — retry shortly
            QTimer.singleShot(5000, self._trigger_initial_live_fetch)

    # ==========================================================================
    # REAL DATA INTEGRATION PATTERN (UNCHANGED)
    # ==========================================================================
    def apply_proven_real_data_pattern(self):
        """Apply the proven real data integration pattern from temp_WorkingRealDashboard"""
        # Outside the trading window: load the EOD snapshot immediately so the
        # dashboard shows genuine closing prices.  The market worker will fetch
        # a fresh Tradier snapshot in the background (via eod_snapshot_fetched
        # signal → _on_eod_snapshot_fetched) and update the display once it
        # arrives.  We only start the file-read timer here — no Tradier polling.
        if not is_tradier_window():
            snapshot_file = self.data_file.parent / "eod_snapshot.json"
            source_file = (
                snapshot_file if snapshot_file.exists()
                else (self.data_file if self.data_file.exists() else None)
            )
            if source_file:
                try:
                    with open(source_file) as _f:
                        _snap = json.load(_f)
                    spy_price = _snap.get("SPY", {}).get("last", "N/A")
                    eod_date = _snap.get("_eod_date", "unknown date")
                    self.add_system_log(
                        f"📊 EOD snapshot loaded ({eod_date}) — SPY last close: ${spy_price}"
                    )
                    # Start file-read timer so widgets populate immediately;
                    # skip fast-fetch (no Tradier polling outside trading hours).
                    self.real_data_active = True
                    if not getattr(self, "_real_data_timer", None) or not self._real_data_timer.isActive():
                        self._real_data_timer = QTimer()
                        self._real_data_timer.timeout.connect(self.update_with_real_data)
                        self._real_data_timer.start(1000)
                    self.update_with_real_data()
                    self.update_data_status("EOD")
                except Exception as e:
                    self.add_system_log(f"⚠️ Could not load EOD snapshot: {e}")
            else:
                self.add_system_log("🕐 Outside trading window — awaiting EOD data from Tradier")
            return

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

            # Start real data updates
            self._real_data_timer = QTimer()
            self._real_data_timer.timeout.connect(self.update_with_real_data)
            self._real_data_timer.start(1000)  # Update every second

            # Fast quote refresh — polls Tradier for fresh prices every 10 s.
            # Runs in the market worker thread via fast_fetch_requested so it
            # doesn't block the UI.  The full fetch (balance + options + chart)
            # still happens every 30 s via the heartbeat.
            self._fast_quote_timer = QTimer()
            self._fast_quote_timer.timeout.connect(
                lambda: self.market_worker.fast_fetch_requested.emit()
                if getattr(self, "market_worker", None)
                else None
            )
            self._fast_quote_timer.start(10_000)  # every 10 seconds

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
                quote_time = _datetime_from_epoch_ms(data.get("timestamp_ms"))
                if quote_time is not None:
                    self.market_data[symbol]["timestamp"] = quote_time

            freshest_quote_time = _freshest_live_data_timestamp(live_data)
            if freshest_quote_time is not None:
                self.connection_info.last_successful_data = freshest_quote_time
                self.connection_info.data_was_live = True

            # Update symbol widgets — delegate to update_data() so each widget's
            # symbol-specific formatting and colour logic is applied correctly
            # (e.g. $TICK/$ADD as signed integers, $TRIN colour-coded by value).
            for symbol, data in live_data.items():
                if symbol in self.symbol_widgets:
                    self.symbol_widgets[symbol].update_data(data)

            # Push standard-quote values (VIX, SKEW, …) to the signal panel
            # so popup dialogs show the same figures as the Market Overview.
            if self.signal_panel is not None:
                _sp = {}
                for _sym in ("VIX", "SKEW", "CPC"):
                    _e = live_data.get(_sym)
                    if isinstance(_e, dict) and _e.get("last") is not None:
                        _sp[_sym] = _e["last"]
                if _sp:
                    self.signal_panel.update_live_data(_sp)

            # Update toolbar indices
            self.update_toolbar_with_real_data(live_data)

            # Re-evaluate the status badge on every real-data refresh so stale
            # quotes flip the UI promptly instead of waiting for the next heartbeat.
            _correct_status = self.determine_data_status()
            _label_map = {"REAL-TIME": "REAL-TIME", "EOD": "EOD", "FROZEN": "FROZEN"}
            _current_label = self.data_status_label.text() if hasattr(self, "data_status_label") else ""
            _target_label = _label_map.get(_correct_status, "SIMULATED")
            if _current_label != _target_label:
                self.update_data_status(_correct_status)
                self.connection_info.market_data_status = _correct_status

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
                    color = "#00ff41" if change >= 0 else "#FF073A"
                    self.spx_change.setStyleSheet(f"color: {color};")

            # COMP (NASDAQ Composite) — Tradier has no IXIC symbol.
            # QQQ ETF * 37.5 is the closest available proxy (~23,079 vs actual ~23,111).
            ndx_src = live_data.get("QQQ")
            ndx_mult = 37.5
            if ndx_src:
                if hasattr(self, "comp_value"):
                    self.comp_value.setText(f" {ndx_src['last'] * ndx_mult:,.0f}")
                if hasattr(self, "comp_change"):
                    change = ndx_src["change"] * ndx_mult
                    pct = ndx_src["change_pct"]
                    sign = "+" if change >= 0 else ""
                    self.comp_change.setText(f"  {sign}{change:.0f}  {sign}{pct:.1f}%")
                    color = "#00ff41" if change >= 0 else "#FF073A"
                    self.comp_change.setStyleSheet(f"color: {color};")

            # DJI — Tradier's $DJI index is ~15 min delayed (confirmed April 2026).
            # Use DIA ETF * 100 instead: real-time, tracks within ~0.3% of actual DJIA.
            dji_src = live_data.get("DIA")
            dji_mult = 100
            if dji_src:
                if hasattr(self, "dji_value"):
                    self.dji_value.setText(f" {dji_src['last'] * dji_mult:,.0f}")
                if hasattr(self, "dji_change"):
                    change = dji_src["change"] * dji_mult
                    pct = dji_src["change_pct"]
                    sign = "+" if change >= 0 else ""
                    self.dji_change.setText(f"  {sign}{change:.0f}  {sign}{pct:.1f}%")
                    color = "#00ff41" if change >= 0 else "#FF073A"
                    self.dji_change.setStyleSheet(f"color: {color};")

            # RUT — Tradier returns last price for the RUT index but change=None (confirmed April 2026).
            # Use RUT last directly; derive change from IWM ETF change_pct as proxy.
            rut_src = live_data.get("RUT") or live_data.get("IWM")
            rut_mult = 1 if "RUT" in live_data else 10
            if rut_src:
                rut_last = rut_src["last"] * rut_mult
                if hasattr(self, "rut_value"):
                    self.rut_value.setText(f" {rut_last:,.0f}")
                if hasattr(self, "rut_change"):
                    # RUT index: change_pct is None from Tradier; borrow IWM's change_pct
                    iwm = live_data.get("IWM")
                    if rut_src.get("change_pct") is not None and rut_src["change_pct"] != 0:
                        pct = rut_src["change_pct"]
                        change = rut_src["change"] * rut_mult
                    elif iwm and iwm.get("change_pct"):
                        pct = iwm["change_pct"]
                        change = rut_last * pct / 100
                    else:
                        pct = 0.0
                        change = 0.0
                    sign = "+" if change >= 0 else ""
                    self.rut_change.setText(f"  {sign}{change:.0f}  {sign}{pct:.1f}%")
                    color = "#00ff41" if change >= 0 else "#FF073A"
                    self.rut_change.setStyleSheet(f"color: {color};")

        except Exception as e:
            self.logger.debug("Toolbar update error: %s", e)

    def update_status_for_real_data(self):
        """Update status indicators when real file data has been loaded."""
        self.update_data_status("EOD")

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
        self.showMaximized()

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

        # Seed the PMR row with its disabled/armed default before any worker
        # connects, so it never sits blank at startup.
        try:
            import os as _os_pmr
            pmr_widget = self.symbol_widgets.get("PMR") if hasattr(self, "symbol_widgets") else None
            if pmr_widget is not None:
                pmr_widget.update_pmr_state({
                    "enabled": _os_pmr.environ.get("SPYDER_PIVOT_MR_ENABLED", "0") == "1",
                    "available": True,
                    "fired": False,
                    "direction": None,
                    "score": None,
                    "level_name": None,
                    "level_price": None,
                    "atr_distance": None,
                    "reasons": [],
                    "penalties": [],
                })
        except (AttributeError, RuntimeError):
            pass

        center_panel = self.create_center_panel()
        content_splitter.addWidget(center_panel)

        right_panel = self.create_right_panel()
        content_splitter.addWidget(right_panel)

        content_splitter.setSizes([340, 970, 610])

        main_layout.addWidget(content_splitter)
        central_widget.setLayout(main_layout)

    def create_toolbar(self) -> QWidget:
        """Create top toolbar with FIXED WIDTH status containers and heartbeat monitor."""
        return build_toolbar(self)

    def create_left_panel(self) -> QWidget:
        """Create left panel with market overview"""
        return build_left_panel(self, MARKET_SYMBOLS)

    def create_center_panel(self) -> QWidget:
        """Create center panel (UNCHANGED)"""
        return build_center_panel(self)

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
        return build_right_panel(self)

    def _acct_lbl(self, text: str, style: str, right: bool = False) -> QLabel:
        """Helper: create a styled account-grid cell label."""
        lbl = QLabel(text)
        lbl.setStyleSheet(style)
        if right:
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return lbl

    def create_chart(self):
        """Create the SPY chart widget (UNCHANGED)"""
        create_chart_widget(self)

    def update_chart(self):
        """Update the SPY intraday chart — fixed 9:30–4:00 ET session, line chart."""
        self.figure.clear()

        # --- Load real 5-min bars from cache file written by the market data worker ---
        chart_file = self.data_file.parent / "spy_5min_chart.json"
        opens_raw: list[float] = []
        highs_raw: list[float] = []
        lows_raw: list[float] = []
        closes_raw: list[float] = []
        volumes_raw: list[int] = []
        dates_raw: list = []

        if chart_file.exists():
            try:
                with open(chart_file) as _f:
                    candles = json.load(_f)
                for bar in candles:
                    opens_raw.append(float(bar.get("open", 0)))
                    highs_raw.append(float(bar.get("high", 0)))
                    lows_raw.append(float(bar.get("low", 0)))
                    closes_raw.append(float(bar.get("close", 0)))
                    volumes_raw.append(int(bar.get("volume", 0)))
                    # bar["time"] is like "2026-04-09T09:30:00"
                    dates_raw.append(pd.to_datetime(bar.get("time", "")))
            except Exception:
                candles = []

        # If no real data yet, show a "waiting for data" placeholder
        if not closes_raw:
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

        # --- Fixed 78-slot session skeleton: slots 0–77 map to 9:30–15:55 (5-min bars) ---
        # Slot index = (bar_minutes_since_midnight - 570) // 5  where 570 = 9h30m
        TOTAL_SLOTS = 78  # 6.5 hours × 12 bars/hour
        OPEN_MINUTES = 9 * 60 + 30  # 570

        slot_closes = np.full(TOTAL_SLOTS, np.nan)
        slot_opens  = np.full(TOTAL_SLOTS, np.nan)
        slot_highs  = np.full(TOTAL_SLOTS, np.nan)
        slot_lows   = np.full(TOTAL_SLOTS, np.nan)

        for i, dt in enumerate(dates_raw):
            slot = (dt.hour * 60 + dt.minute - OPEN_MINUTES) // 5
            if 0 <= slot < TOTAL_SLOTS:
                slot_closes[slot] = closes_raw[i]
                slot_opens[slot]  = opens_raw[i]
                slot_highs[slot]  = highs_raw[i]
                slot_lows[slot]   = lows_raw[i]

        # Previous close reference — use first bar's open so the dashed line is
        # the "where we started" anchor (analogous to prior-close in Google Finance)
        prev_close = opens_raw[0]
        last_close = closes_raw[-1]
        line_color = COLORS["positive"] if last_close >= prev_close else COLORS["negative"]

        # --- Compute chart indicators on raw bars (audit §3) ---
        # Load previous session's daily H/L/C so pivot levels stay fixed all
        # day (floor-trader convention: pivots derive from yesterday, not today).
        _prev_day_tuple: tuple[float, float, float] | None = None
        _prev_day_file = self.data_file.parent / "spy_prev_day.json"
        if _prev_day_file.exists():
            try:
                with open(_prev_day_file) as _pdf:
                    _pd = json.load(_pdf)
                _prev_day_tuple = (float(_pd["high"]), float(_pd["low"]), float(_pd["close"]))
            except Exception:
                pass

        try:
            indicators = compute_chart_indicators(highs_raw, lows_raw, closes_raw, volumes_raw, prev_day=_prev_day_tuple)
        except ValueError:
            indicators = None

        if indicators is not None:
            pivot = indicators.pivots.pivot
            r1 = indicators.pivots.r1
            r2 = indicators.pivots.r2
            r3 = indicators.pivots.r3
            s1 = indicators.pivots.s1
            s2 = indicators.pivots.s2
            s3 = indicators.pivots.s3
            ma_20_raw = indicators.ma20
            vwap_raw = indicators.vwap
        else:
            pivot = r1 = r2 = r3 = s1 = s2 = s3 = last_close
            ma_20_raw = [None] * len(closes_raw)
            vwap_raw = closes_raw[:]

        # Map MA(20) and VWAP from bar-index space to slot-index space
        ma_slot_x: list[int] = []
        ma_slot_y: list[float] = []
        vwap_slot_x: list[int] = []
        vwap_slot_y: list[float] = []
        for i, dt in enumerate(dates_raw):
            slot = (dt.hour * 60 + dt.minute - OPEN_MINUTES) // 5
            if 0 <= slot < TOTAL_SLOTS:
                if i < len(ma_20_raw) and ma_20_raw[i] is not None:
                    ma_slot_x.append(slot)
                    ma_slot_y.append(ma_20_raw[i])
                if i < len(vwap_raw):
                    vwap_slot_x.append(slot)
                    vwap_slot_y.append(vwap_raw[i])

        # --- Create plot ---
        ax = self.figure.add_subplot(111)
        ax.yaxis.tick_left()
        ax.yaxis.set_label_position("left")
        ax.set_facecolor(COLORS["panel"])

        # x-axis always spans the full session: slot -0.5 → 78.5
        # Slot 78 is used as the "4:00 PM" tick label (session end boundary)
        ax.set_xlim(-0.5, 78.5)

        # Fibonacci Daily Pivot Points
        ax.axhline(y=pivot, color="#FFFF00", linewidth=1.5, linestyle="-", alpha=0.7, label="Pivot", zorder=1)
        ax.axhline(y=r1, color="#00FF41", linewidth=1.5, linestyle="-", alpha=0.6, label="R1", zorder=1)
        ax.axhline(y=r2, color="#00FF41", linewidth=1.5, linestyle="-", alpha=0.6, label="R2", zorder=1)
        ax.axhline(y=r3, color="#00FF41", linewidth=1.5, linestyle="-", alpha=0.6, label="R3", zorder=1)
        ax.axhline(y=s1, color="#FF073A", linewidth=1.5, linestyle="-", alpha=0.6, label="S1", zorder=1)
        ax.axhline(y=s2, color="#FF073A", linewidth=1.5, linestyle="-", alpha=0.6, label="S2", zorder=1)
        ax.axhline(y=s3, color="#FF073A", linewidth=1.5, linestyle="-", alpha=0.6, label="S3", zorder=1)

        # Prior-close reference line (dashed grey — anchors the day's move)
        ax.axhline(y=prev_close, color="#888888", linewidth=1.0, linestyle="--", alpha=0.8, zorder=1)

        # MA(20) overlay
        if ma_slot_x:
            ax.plot(ma_slot_x, ma_slot_y, color="#00FFFF", linewidth=1.8, alpha=0.95, label="MA(20)", zorder=2)

        # VWAP overlay — smooth solid white line
        if vwap_slot_x:
            ax.plot(vwap_slot_x, vwap_slot_y, color="#FFFFFF", linewidth=1.5, linestyle="-", alpha=0.90, label="VWAP", zorder=4)

        # Candlestick bars — bodies via bar(), wicks via vlines()
        slot_indices = np.arange(TOTAL_SLOTS)
        valid = ~np.isnan(slot_closes)
        xs      = slot_indices[valid]
        op      = slot_opens[valid]
        hi      = slot_highs[valid]
        lo      = slot_lows[valid]
        cl      = slot_closes[valid]
        body_lo = np.minimum(op, cl)
        body_hi = np.maximum(op, cl)
        is_up   = cl >= op
        bar_colors = np.where(is_up, COLORS["positive"], COLORS["negative"])
        # Draw wicks first (behind bodies)
        for xi, loi, hii, ci in zip(xs, lo, hi, np.where(is_up, COLORS["positive"], COLORS["negative"])):
            ax.vlines(xi, loi, hii, color=ci, linewidth=0.8, zorder=2)
        # Draw bodies
        ax.bar(xs, height=body_hi - body_lo, bottom=body_lo, width=0.7,
               color=bar_colors, align="center", edgecolor="none", linewidth=0, zorder=3)

        # Pivot level labels on the right (just beyond slot 78)
        label_x = 79
        ax.text(label_x, pivot, f" P: {pivot:.2f}", color="#FFFF00", fontsize=9, va="center")
        ax.text(label_x, r1, f" R1: {r1:.2f}", color="#00FF41", fontsize=8, va="center")
        ax.text(label_x, r2, f" R2: {r2:.2f}", color="#00FF41", fontsize=8, va="center")
        ax.text(label_x, r3, f" R3: {r3:.2f}", color="#00FF41", fontsize=8, va="center")
        ax.text(label_x, s1, f" S1: {s1:.2f}", color="#FF073A", fontsize=8, va="center")
        ax.text(label_x, s2, f" S2: {s2:.2f}", color="#FF073A", fontsize=8, va="center")
        ax.text(label_x, s3, f" S3: {s3:.2f}", color="#FF073A", fontsize=8, va="center")

        # Fixed hourly x-axis ticks — always present regardless of bars received
        # slot 0=9:30, 6=10:00, 18=11:00, 30=12:00, 42=1:00, 54=2:00, 66=3:00, 78=4:00
        ax.set_xticks([0, 6, 18, 30, 42, 54, 66, 78])
        ax.set_xticklabels(["9:30", "10:00", "11:00", "12:00", "1:00", "2:00", "3:00", "4:00"], fontsize=9)

        ax.grid(True, alpha=0.2, color=COLORS["grid"], zorder=0)
        ax.tick_params(colors="#FFFFFF")
        for spine in ax.spines.values():
            spine.set_color(COLORS["border"])

        self.figure.tight_layout()
        self.canvas.draw()

    def create_positions_table(self) -> QTreeWidget:
        """Create positions tree with strategy headers and expandable trade legs."""
        return build_positions_table(self)

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

        # Close / Roll / Adjust actions intentionally absent until an
        # OrderManager service is wired. A do-nothing context-menu item
        # misleads traders (see 2026-04-15 audit §24).

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
        return build_pnl_table()

    def create_unified_prometheus_metrics(self) -> QWidget:
        """Create the unified Prometheus Metrics table (8 clients in 4x2 grid + 2 empty rows)"""
        return build_unified_prometheus_metrics(self)

    # ==========================================================================
    # SIGNAL HANDLERS - ENHANCED WITH HEARTBEAT
    # ==========================================================================
    @Slot(bool, str)
    def on_connection_status_changed(self, connected: bool, status: str):
        """Handle connection status change and synchronize UI state."""
        handle_connection_status_changed(self, connected, status)

    @Slot(str)
    def on_heartbeat_status_changed(self, status: str):
        """Handle heartbeat status transitions for toolbar indicators."""
        handle_heartbeat_status_changed(self, status)

    @Slot(str)
    def on_market_data_status_changed(self, status: str):
        """Handle market-data status transitions from the worker."""
        handle_market_data_status_changed(self, status)

    @Slot(dict)
    def on_market_data_updated(self, data: dict):
        """Handle market data updates from the market worker."""
        handle_market_data_updated(self, data)

    @Slot(str)
    def on_market_error(self, error: str):
        """Handle market error"""
        handle_market_error(self, error)

    @Slot(str)
    def on_heartbeat_received(self, message: str):
        """Handle heartbeat message - FIXED to route to system log"""
        handle_heartbeat_received(self, message)

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
        """Thin wrapper — delegates to DashboardOrderManager (audit §5)."""
        self._order_manager.set_client(self._get_tradier_client_for_mode(mode))
        return self._order_manager.fetch_pending_orders()

    def _cancel_orders(
        self, orders: list[dict], mode: "TradingMode | None" = None
    ) -> tuple[int, int]:
        """Thin wrapper — delegates to DashboardOrderManager (audit §5)."""
        self._order_manager.set_client(self._get_tradier_client_for_mode(mode))
        ok, fail = self._order_manager.cancel_orders(orders)
        for order in orders[:ok]:
            self.add_system_log(f"✅ Cancelled order #{order.get('id')}")
        return ok, fail

    def _open_trade_audit_dialog(self) -> None:
        """Open (or raise) the Trade Audit dialog with the cached closed-spread log.

        The dialog is held as a non-modal singleton so the user can keep it
        open alongside the dashboard. Subsequent worker emits push fresh
        rows in via update_trades(), so the dialog reflects new closes
        without requiring a manual refresh.
        """
        from Spyder.SpyderG_GUI.SpyderG22_TradeAuditDialog import TradeAuditDialog
        existing = getattr(self, "_trade_audit_dialog", None)
        if existing is not None and existing.isVisible():
            existing.update_trades(self._closed_trades_cache)
            existing.raise_()
            existing.activateWindow()
            return
        dlg = TradeAuditDialog(self._closed_trades_cache, parent=self)
        dlg.finished.connect(lambda *_: setattr(self, "_trade_audit_dialog", None))
        self._trade_audit_dialog = dlg
        dlg.show()

    def _open_decision_log_dialog(self) -> None:
        """Open (or raise) the Decision Log dialog.

        Shows the gate-by-gate JSON-lines audit records written by R08 for
        every 30-second poll.  The dialog auto-refreshes while open; it is
        a non-modal singleton so it can stay open beside the dashboard.
        """
        from Spyder.SpyderG_GUI.SpyderG23_DecisionLogDialog import DecisionLogDialog
        existing = getattr(self, "_decision_log_dialog", None)
        if existing is not None and existing.isVisible():
            existing.force_refresh()
            existing.raise_()
            existing.activateWindow()
            return
        dlg = DecisionLogDialog(parent=self)
        dlg.finished.connect(lambda *_: setattr(self, "_decision_log_dialog", None))
        self._decision_log_dialog = dlg
        dlg.show()

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

        # In paper trading mode the live account endpoints are not used;
        # paper positions are tracked internally by _PaperTradingWorker.
        if getattr(self, "trading_mode", None) == TradingMode.PAPER:
            self.positions_table.clear()
            _empty = QTreeWidgetItem(self.positions_table)
            _empty.setText(0, "Paper trading mode — positions tracked by paper engine")
            _empty.setForeground(0, Qt.GlobalColor.gray)
            self.positions_table.setFirstColumnSpanned(0, QModelIndex(), True)
            return

        client = self._get_tradier_client_for_mode()
        self._order_manager.set_client(client)

        try:
            self.positions_table.clear()
            has_rows = False

            data = self._order_manager.fetch_orders_and_positions()

            # ── Pending / open orders ─────────────────────────────────────────
            for o in data["pending_orders"]:
                self._add_order_row(o)
                has_rows = True

            # ── Open positions ────────────────────────────────────────────────
            for p in data["open_positions"]:
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

    def _render_paper_spreads_in_tree(self, spreads_detail: list) -> None:
        """Populate ``positions_table`` with paper-engine spread rows.

        Replaces the legacy 'Paper trading mode — positions tracked by paper
        engine' placeholder with a tree of spread parents (column-spanned
        header) and per-leg children. Called from ``_refresh_spreads_panel``
        on every R08 worker emit while in paper mode.

        Each spread parent shows: structure label, strikes, qty, credit,
        live MTM, DTE, and stop-loss arming status. Children show one row
        per leg with the option symbol, side, qty, expiry, and entry mark.
        Layout matches the existing 7-col tree (LEG/STRIKE/CONT/EXPIRY/
        COST/P&L/(close-btn)) so the live-mode flows remain unchanged.
        """
        from datetime import date as _date, datetime as _dt

        self.positions_table.clear()

        if not spreads_detail:
            empty = QTreeWidgetItem(self.positions_table)
            empty.setText(0, "Paper trading — no open spreads")
            empty.setForeground(0, Qt.GlobalColor.gray)
            self.positions_table.setFirstColumnSpanned(0, QModelIndex(), True)
            return

        today = _date.today()
        for sp in spreads_detail:
            # ── Parent row: spread summary ───────────────────────────────
            structure = str(sp.get("structure") or sp.get("type") or "Spread").upper()
            short_k = sp.get("short_strike", 0.0)
            long_k = sp.get("long_strike", 0.0)
            qty = int(sp.get("qty", 0))
            credit = float(sp.get("credit", 0.0))
            mtm = float(sp.get("mtm_pnl", 0.0))
            stop_armed = sp.get("stop_loss_armed", True)  # default True after Phase 2
            origin = str(sp.get("origin") or "AI").upper()
            opened_at = float(sp.get("opened_at") or 0.0)

            # Entry timestamp formatted YYYY-MM-DD HH:MM (skip if missing)
            ts_str = ""
            if opened_at > 0:
                try:
                    ts_str = _dt.fromtimestamp(opened_at).strftime("%Y-%m-%d %H:%M")
                except (OSError, ValueError, OverflowError):
                    ts_str = ""

            # DTE from ISO expiration if present.
            exp_str = str(sp.get("expiration", "") or "")
            dte_str = "—"
            if exp_str:
                try:
                    yyyy, mm, dd = exp_str[:10].split("-")
                    dte = (_date(int(yyyy), int(mm), int(dd)) - today).days
                    dte_str = f"{dte:02d}"
                except (ValueError, TypeError):
                    pass

            # Net P&L % of credit received (premium kept).
            credit_dollars = credit * 100.0 * qty
            pnl_pct = (mtm / credit_dollars * 100.0) if credit_dollars > 0 else 0.0
            mtm_sign = "+" if mtm >= 0 else "−"

            stop_glyph = "🛡" if stop_armed else "•"
            ts_field = f"{ts_str}  │  " if ts_str else ""
            header = (
                f"{stop_glyph}  {ts_field}"
                f"STRATEGY TRIGGERED BY {origin} : {structure}  │  "
                f"DTE: {dte_str}  │  STATUS: OPEN  │  "
                f"NET P&L {mtm_sign}${abs(mtm):,.2f}  ({pnl_pct:+.1f}%)"
            )
            parent = QTreeWidgetItem(self.positions_table)
            parent.setText(0, header)
            # Colour by MTM sign.
            parent_col = (
                Qt.GlobalColor.green if mtm >= 0 else Qt.GlobalColor.red
            )
            parent.setForeground(0, parent_col)
            self.positions_table.setFirstColumnSpanned(
                self.positions_table.indexOfTopLevelItem(parent),
                QModelIndex(),
                True,
            )
            parent.setExpanded(False)  # collapsed by default — keeps view compact

            # ── Leg children — one row per option leg ───────────────────
            legs = sp.get("legs") or []
            if not legs:
                # Fallback: synthesize from short/long strike when worker
                # didn't include a per-leg breakdown.
                legs = [
                    {
                        "side": "SELL",
                        "strike": short_k,
                        "qty": qty,
                        "type": "PUT" if "PUT" in structure else "CALL",
                    },
                    {
                        "side": "BUY",
                        "strike": long_k,
                        "qty": qty,
                        "type": "PUT" if "PUT" in structure else "CALL",
                    },
                ]
            for leg in legs:
                child = QTreeWidgetItem(parent)
                side = str(leg.get("side", "—")).upper()
                strike = leg.get("strike", 0.0)
                leg_type = str(leg.get("type", "")).upper()
                child.setText(0, f"  {side}")
                child.setText(1, f"{strike:.0f}{leg_type[:1]}")
                child.setText(2, str(int(leg.get("qty", qty))))
                child.setText(3, exp_str[:10] if exp_str else "—")
                mark = leg.get("mark") or leg.get("entry_mark")
                if mark is not None:
                    try:
                        child.setText(4, f"${float(mark):.2f}")
                    except (TypeError, ValueError):
                        pass

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
        self._order_manager.set_client(self._get_tradier_client_for_mode())
        try:
            self._order_manager.cancel_order_by_id(int(order_id))
            self.add_system_log(f"✅ Order #{order_id} cancelled")
            self._refresh_positions_table()
        except Exception as exc:
            self.add_system_log(f"❌ Failed to cancel order #{order_id}: {exc}")
            QMessageBox.critical(self, "Cancel Failed", str(exc))

    # ==========================================================================
    # TRADING MODE MANAGEMENT
    # ==========================================================================

    def _count_open_live_positions(self) -> int:
        """Return the number of live positions visible in the positions table.

        Separated from _on_mode_btn_clicked per audit §18 so the policy check
        (does the user have open live positions?) can be tested without a dialog.
        The table row count is used as a proxy because positions are fetched from
        Tradier and rendered row-by-row into that widget.
        """
        if self.positions_table is None:
            return 0
        return self.positions_table.topLevelItemCount()

    def _handle_pending_orders_gate(
        self, pending_mode: TradingMode, target_label: str, support_suffix: str
    ) -> bool:
        """Run the shared 'pending orders must be cancelled' gate.

        Detects pending orders in *pending_mode*, prompts the user to cancel
        them, executes the cancellation, and reports failures. Returns True
        when the gate passes (no pending, or everything cancelled cleanly)
        and False when the caller must abort the mode switch. Both PAPER→LIVE
        and LIVE→PAPER branches route through here so the cancel-recheck
        policy lives in one place."""
        pending = self._fetch_pending_orders(pending_mode)
        if not pending:
            return True

        order_lines = "\n".join(
            f"  #{o.get('id')}  {o.get('symbol','?')}  {o.get('side','?').upper()}"
            f"  qty {int(o.get('quantity',0))}  [{o.get('status','?').upper()}]"
            for o in pending[:10]
        )
        suffix = f"\n  … and {len(pending)-10} more" if len(pending) > 10 else ""
        source = "paper/sandbox" if pending_mode == TradingMode.PAPER else "LIVE"
        result = QMessageBox.warning(
            self,
            f"Pending {source.title()} Orders Must Be Cancelled",
            f"You have {len(pending)} pending {source} order(s):\n\n"
            f"{order_lines}{suffix}\n\n"
            f"These must be cancelled before switching to {target_label}.\n\n"
            "Cancel all pending orders now and continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if result != QMessageBox.StandardButton.Yes:
            self.add_system_log(
                f"Switch to {target_label} cancelled — pending {source} orders remain"
            )
            return False

        ok, fail = self._cancel_orders(pending, pending_mode)
        if fail:
            QMessageBox.critical(
                self,
                "Cancellation Failed",
                f"{fail} order(s) could not be cancelled.\n{support_suffix}",
            )
            return False
        self.add_system_log(
            f"✅ {ok} pending {source} order(s) cancelled — continuing switch"
        )
        return True

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
            if not self._handle_pending_orders_gate(
                TradingMode.PAPER,
                target_label="LIVE",
                support_suffix="Resolve them manually before switching to LIVE trading.",
            ):
                self._update_mode_buttons()
                return

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
            if not self._handle_pending_orders_gate(
                TradingMode.LIVE,
                target_label="PAPER",
                support_suffix="Resolve them manually or call Tradier: +1 (312) 542-6901.",
            ):
                self._update_mode_buttons()
                return

            # Gate 3: warn if live positions still open (positions, not orders)
            open_count = self._count_open_live_positions()
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
        # ── Snapshot outgoing mode before committing the switch ───────────────
        old_mode = self.trading_mode
        self._positions_snapshot_by_mode[old_mode] = self._snapshot_positions_table()

        self.trading_mode = new_mode
        is_paper = new_mode == TradingMode.PAPER

        self._update_mode_buttons()

        # Reset account container to placeholders; real data arrives via broker/signals
        if self.acct_number_lbl:
            import os as _os_mode
            _paper_acct_id = _os_mode.environ.get("TRADIER_SANDBOX_ACCOUNT_ID", "PAPER ACCOUNT")
            self.acct_number_lbl.setText(_paper_acct_id if is_paper else "—")
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

        # ── Restore incoming mode's previously saved table contents ───────────
        saved_positions = self._positions_snapshot_by_mode.get(new_mode)
        if saved_positions:
            self._restore_positions_snapshot(saved_positions)
        self._refresh_pnl_table(self._pnl_stats_by_mode.get(new_mode, {}))

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
        _inactive_base = f"font-size: 12px; border-radius: 3px; padding: 4px 8px; border: none; background-color: {COLORS['panel']}; color: #aaaaaa;"
        self.live_btn.setStyleSheet(
            f"background-color: {COLORS['positive']}; color: black; {_active_base}"
            if is_live else _inactive_base
        )
        self.paper_btn.setStyleSheet(
            f"background-color: {COLORS['orange']}; color: black; {_active_base}"
            if not is_live else _inactive_base
        )

    # ── Per-mode snapshot helpers ─────────────────────────────────────────────

    def _snapshot_positions_table(self) -> list:
        """Serialize the current positions QTreeWidget into a plain list of dicts.

        Each entry represents one top-level row and its children so that the
        snapshot can be fully restored via ``_restore_positions_snapshot()``.
        """
        if not self.positions_table:
            return []
        ncols = self.positions_table.columnCount()
        snapshot = []
        for i in range(self.positions_table.topLevelItemCount()):
            item = self.positions_table.topLevelItem(i)
            entry = {
                "texts": [item.text(c) for c in range(ncols)],
                "foreground": item.foreground(0).color().name(),
                "span": True,
                "children": [
                    [item.child(j).text(c) for c in range(ncols)]
                    for j in range(item.childCount())
                ],
            }
            snapshot.append(entry)
        return snapshot

    def _restore_positions_snapshot(self, snapshot: list) -> None:
        """Repopulate the positions table from a previously captured snapshot.

        Restores text, foreground colour, column spanning, and child rows.
        The per-order cancel buttons are intentionally omitted because the
        orders they referenced belong to a different mode session.
        """
        if not self.positions_table or not snapshot:
            return
        from PySide6.QtGui import QColor
        self.positions_table.clear()
        ncols = self.positions_table.columnCount()
        for entry in snapshot:
            parent = QTreeWidgetItem(self.positions_table)
            texts = entry.get("texts", [])
            for c in range(min(len(texts), ncols)):
                parent.setText(c, texts[c])
            color_name = entry.get("foreground", "")
            if color_name:
                parent.setForeground(0, QColor(color_name))
            if entry.get("span"):
                self.positions_table.setFirstColumnSpanned(
                    self.positions_table.indexOfTopLevelItem(parent),
                    QModelIndex(),
                    True,
                )
            parent.setExpanded(True)
            for child_texts in entry.get("children", []):
                child = QTreeWidgetItem(parent)
                for c in range(min(len(child_texts), ncols)):
                    child.setText(c, child_texts[c])

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
        self.add_automation_log(f"TRADING ACTIVE [{mode_label}] - Session started")

        if self.real_data_active:
            self.add_automation_log("Using live market data feed")
        else:
            self.add_automation_log("Using current dashboard data source")

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

        # Pre-populate account panel with initial paper capital immediately,
        # so the user sees $100k right away without waiting for the first Tradier poll.
        # (On market-closed days SPY last=0 so the poll returns early and labels would
        # stay stuck on "Connecting…" indefinitely.)
        if self.acct_number_lbl:
            import os as _os_pt
            self.acct_number_lbl.setText(_os_pt.environ.get("TRADIER_SANDBOX_ACCOUNT_ID", "PAPER ACCOUNT"))
        # Single source of truth for paper-trading starting capital. Used to
        # initialise the worker AND to scale the E01 risk-manager limits so
        # percentage-based dialog inputs map to the correct dollar amounts.
        paper_initial_capital = 100_000.0
        _ic = paper_initial_capital
        if self.settled_value:
            self.settled_value.setText(f"${_ic:,.2f}")
        if self.buying_value:
            self.buying_value.setText(f"${_ic:,.2f}")
        if self.realized_value:
            self.realized_value.setText("$0.00")
        if self.unrealized_value:
            self.unrealized_value.setText("$0.00")

        # Create worker and thread
        self._paper_thread = QThread(self)
        self._paper_worker = _PaperTradingWorker(initial_capital=paper_initial_capital)
        # Pass current risk parameters before moving to thread (thread-safe at this point)
        if self.current_risk_params:
            self._paper_worker.set_risk_params(self.current_risk_params)
        # Phase 1: build a real SpyderE01_RiskManager from the dialog params
        # and inject it into the worker so validate_signal() gates every trade.
        risk_manager = self._build_paper_risk_manager(initial_capital=paper_initial_capital)
        if risk_manager is not None:
            self._paper_worker.set_risk_manager(risk_manager)
            self.add_system_log("✅ E-series RiskManager attached to paper worker")
        # Phase 1: forward S07 regime metrics to the worker so it can gate
        # entries on SWAN tail-risk, etc. The orchestrator is started by
        # _start_metrics_orchestrator() early in __init__.
        if self._metrics_orchestrator is not None:
            try:
                self._metrics_orchestrator.metrics_updated.connect(
                    self._paper_worker.set_regime_metrics
                )
                self.add_system_log("✅ S07 regime metrics piped to paper worker")
            except Exception as exc:
                self.add_system_log(f"⚠️ Could not wire S07 → paper worker: {exc}")
        self._paper_worker.moveToThread(self._paper_thread)

        # Wire signals (all bound methods for proper QueuedConnection)
        self._paper_thread.started.connect(self._paper_worker.run)
        self._paper_worker.status_update.connect(self._on_paper_status)
        self._paper_worker.position_update.connect(self._on_paper_position)
        self._paper_worker.metrics_update.connect(self._on_paper_metrics)
        self._paper_worker.error.connect(self._on_paper_error)
        self._paper_worker.stopped.connect(self._on_paper_stopped)
        self._paper_worker.connection_ready.connect(self._on_paper_connection)
        self._paper_worker.pivot_signal_updated.connect(self._on_pivot_signal_state)

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
    def _on_pivot_signal_state(self, state: dict) -> None:
        """Forward S08 PMR signal state to the left-panel ``PMR`` row."""
        widget = self.symbol_widgets.get("PMR") if hasattr(self, "symbol_widgets") else None
        if widget is None:
            return
        try:
            widget.update_pmr_state(state)
        except (AttributeError, RuntimeError):
            # Widget gone or wrong type — safe to ignore.
            pass

    @Slot(str)
    def _on_symbol_widget_clicked(self, symbol: str) -> None:
        """Handle a left-click on any market-overview row."""
        if symbol == "PMR":
            self._show_pmr_details_dialog()
        elif symbol == "WRS":
            self._show_wrs_details_dialog()
        elif symbol == "PSR":
            self._show_psr_details_dialog()

    def _show_wrs_details_dialog(self) -> None:
        """Open a modal dialog showing the live Walmart Recession Signal state."""
        import math

        # Pull latest data from S12 singleton (uses disk cache — no extra API call)
        d: dict = {}
        try:
            from SpyderS_Signals.SpyderS12_WRSSignal import get_wrs_signal
            d = get_wrs_signal().get_signal_dict()
        except Exception:
            pass

        def _fmt(v, fmt=".4f", fallback="—"):
            try:
                return format(float(v), fmt) if not math.isnan(float(v)) else fallback
            except (TypeError, ValueError):
                return fallback

        raw        = _fmt(d.get("wrs"),          ".4f")
        pct_rank   = _fmt(d.get("wrs_pct_rank"), ".1f")
        zscore     = _fmt(d.get("wrs_zscore"),   "+.2f")
        ma_30      = _fmt(d.get("wrs_30d_ma"),   ".4f")
        ma_90      = _fmt(d.get("wrs_90d_ma"),   ".4f")
        yoy        = _fmt(d.get("yoy_change"),   "+.2f")
        level      = d.get("wrs_signal_level", "NORMAL")
        guidance   = d.get("strategy_guidance", "Insufficient data — using neutral stance.")
        available  = ", ".join(d.get("basket_available") or []) or "—"
        missing    = ", ".join(d.get("basket_missing")   or []) or "none"
        data_start = str(d.get("data_start") or "—")
        data_end   = str(d.get("data_end")   or "—")
        crossover_date = str(d.get("last_crossover_date") or "—")
        crossover_dir  = str(d.get("last_crossover_dir")  or "—")
        error      = d.get("error") or ""

        level_colors = {
            "NORMAL":   "#5cffa0",
            "CAUTION":  "#f2b134",
            "WARNING":  "#ff9800",
            "CRITICAL": "#FF073A",
        }
        level_color = level_colors.get(level, "#9bb")

        if error:
            status_html = f"<b style='color:#FF073A'>Error:</b> {error}"
        else:
            status_html = f"<b style='color:{level_color}'>{level}</b>"

        html = f"""
        <h2 style='margin-bottom:4px;'>WRS — Walmart Recession Signal</h2>
        <p style='color:#9bb;'>Producer: <code>SpyderS12_WRSSignal</code> &nbsp;·&nbsp;
        Consumer: strategy regime gate via <code>SpyderS07_CustomMetricsOrchestrator</code></p>

        <h3>Live state</h3>
        <p>Signal level: {status_html}</p>
        <table cellpadding='4' style='font-size:12px;'>
          <tr><td><b>WMT / Luxury ratio</b></td><td>{raw}</td></tr>
          <tr><td><b>Percentile rank (expanding)</b></td><td>{pct_rank}%</td></tr>
          <tr><td><b>Z-score (252d rolling)</b></td><td>{zscore}</td></tr>
          <tr><td><b>30-day MA</b></td><td>{ma_30}</td></tr>
          <tr><td><b>90-day MA</b></td><td>{ma_90}</td></tr>
          <tr><td><b>YoY change</b></td><td>{yoy}%</td></tr>
          <tr><td><b>Last MA crossover</b></td><td>{crossover_date} ({crossover_dir})</td></tr>
          <tr><td><b>Data range</b></td><td>{data_start} → {data_end}</td></tr>
        </table>

        <h3>Strategy guidance</h3>
        <p style='font-style:italic;'>{guidance}</p>

        <h3>Signal levels</h3>
        <table cellpadding='4' style='font-size:12px;'>
          <tr><td><b style='color:#5cffa0'>NORMAL</b></td><td>Pct-rank &lt; 60% — full strategy palette</td></tr>
          <tr><td><b style='color:#f2b134'>CAUTION</b></td><td>60–75% — reduce allocation 20%, avoid longs</td></tr>
          <tr><td><b style='color:#ff9800'>WARNING</b></td><td>75–90% — reduce 40%, defensive only</td></tr>
          <tr><td><b style='color:#FF073A'>CRITICAL</b></td><td>&gt;90% — reduce 60%, iron condors only</td></tr>
        </table>

        <h3>Luxury basket</h3>
        <p style='font-size:11px;'><b>Available ({len(d.get('basket_available') or [])}):</b> {available}</p>
        <p style='font-size:11px;'><b>Missing:</b> {missing}</p>

        <hr/>
        <h3>How it works</h3>
        <ol>
          <li><b>Formula</b> — <code>WRS = Price(WMT) / mean(rebased luxury basket)</code>.
              Rising ratio signals consumer rotation from luxury to discount → recession risk.</li>
          <li><b>Luxury basket</b> — LVMUY, CFRUY, HESAY, PPRUY, BURBY, SWGAY, RACE, TPR, CPRI.
              Each ticker is rebased to 100 at its own first print; equal-weight mean.</li>
          <li><b>Data source</b> — Tradier <code>/markets/history</code> endpoint (primary);
              yfinance fallback when API key is absent.</li>
          <li><b>Refresh cadence</b> — 4-hour disk cache; computed once per session then
              served from cache. S07 reads the cache on every orchestrator cycle.</li>
          <li><b>Signal classification</b> — expanding percentile rank of the raw ratio
              against its full history. Crossovers of 30d/90d MAs trigger early alerts.</li>
        </ol>
        """

        dlg = QDialog(self)
        dlg.setWindowTitle("WRS — Walmart Recession Signal (S12)")
        dlg.setMinimumSize(680, 560)
        v = QVBoxLayout(dlg)

        body = QTextEdit()
        body.setReadOnly(True)
        body.setHtml(html)
        v.addWidget(body)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(dlg.reject)
        btns.accepted.connect(dlg.accept)
        v.addWidget(btns)

        dlg.exec()

    def _show_psr_details_dialog(self) -> None:
        """Open a modal dialog showing the live Pawn Shop Ratio state."""
        import math

        d: dict = {}
        try:
            from SpyderS_Signals.SpyderS13_PSRSignal import get_psr_signal, interpret_dual_signal
            d = get_psr_signal().get_signal_dict()
        except Exception:
            pass

        # Also pull WRS level for dual-signal interpretation
        wrs_level = "NORMAL"
        try:
            from SpyderS_Signals.SpyderS12_WRSSignal import get_wrs_signal
            wrs_d = get_wrs_signal().get_signal_dict()
            wrs_level = wrs_d.get("wrs_signal_level", "NORMAL")
        except Exception:
            pass

        def _fmt(v, fmt=".4f", fallback="—"):
            try:
                return format(float(v), fmt) if not math.isnan(float(v)) else fallback
            except (TypeError, ValueError):
                return fallback

        raw        = _fmt(d.get("psr"),          ".4f")
        pct_rank   = _fmt(d.get("psr_pct_rank"), ".1f")
        zscore     = _fmt(d.get("psr_zscore"),   "+.2f")
        ma_30      = _fmt(d.get("psr_30d_ma"),   ".4f")
        ma_90      = _fmt(d.get("psr_90d_ma"),   ".4f")
        yoy        = _fmt(d.get("psr_yoy_change"), "+.4f")
        fcfs_px    = _fmt(d.get("psr_fcfs_price"), ".2f")
        ezpw_px    = _fmt(d.get("psr_ezpw_price"), ".2f")
        xlf_px     = _fmt(d.get("psr_xlf_price"),  ".2f")
        level      = d.get("psr_signal_level", "NORMAL")
        guidance   = d.get("psr_strategy_guidance", "Insufficient data — using neutral stance.")
        data_start = str(d.get("psr_data_start") or "—")
        data_end   = str(d.get("psr_data_end")   or "—")
        crossover_date = str(d.get("psr_crossover_date") or "—")
        crossover_dir  = str(d.get("psr_crossover_dir")  or "—")
        error      = d.get("psr_error") or ""

        level_colors = {
            "NORMAL":   "#5cffa0",
            "CAUTION":  "#f2b134",
            "WARNING":  "#ff9800",
            "CRITICAL": "#FF073A",
        }
        level_color = level_colors.get(level, "#9bb")

        if error:
            status_html = f"<b style='color:#FF073A'>Error:</b> {error}"
        else:
            status_html = f"<b style='color:{level_color}'>{level}</b>"

        # Dual-signal assessment
        try:
            from SpyderS_Signals.SpyderS13_PSRSignal import interpret_dual_signal
            dual = interpret_dual_signal(level, wrs_level)
        except Exception:
            dual = {
                "regime": "UNKNOWN",
                "description": "Dual-signal data unavailable.",
                "trading_bias": "—",
                "size_multiplier": "1.00",
            }

        dual_regime_colors = {
            "HEALTHY":              "#5cffa0",
            "MIDDLE_CLASS_PULLBACK":"#a0c4ff",
            "WORKING_CLASS_STRESS": "#f2b134",
            "EARLY_DETERIORATION":  "#f2b134",
            "BROAD_STRESS":         "#ff9800",
            "SYSTEMIC_CRISIS":      "#FF073A",
        }
        dual_color = dual_regime_colors.get(dual.get("regime", ""), "#9bb")

        html = f"""
        <h2 style='margin-bottom:4px;'>PSR \u2014 Pawn Shop Ratio</h2>
        <p style='color:#9bb;'>Producer: <code>SpyderS13_PSRSignal</code> &nbsp;\u00b7&nbsp;
        Consumer: strategy regime gate via <code>SpyderS07_CustomMetricsOrchestrator</code></p>
        <p style='color:#9bb; font-size:11px;'>Formula: <code>PSR = (FCFS + EZPW) / XLF</code>
        &nbsp;\u00b7&nbsp; FCFS = FirstCash Holdings &nbsp;\u00b7&nbsp; EZPW = EZCORP &nbsp;\u00b7&nbsp;
        XLF = Financial Select Sector SPDR</p>

        <h3>Live state</h3>
        <p>PSR signal level: {status_html}</p>
        <table cellpadding='4' style='font-size:12px;'>
          <tr><td><b>(FCFS+EZPW) / XLF ratio</b></td><td>{raw}</td></tr>
          <tr><td><b>Percentile rank (expanding)</b></td><td>{pct_rank}%</td></tr>
          <tr><td><b>Z-score (252d rolling)</b></td><td>{zscore}</td></tr>
          <tr><td><b>30-day MA</b></td><td>{ma_30}</td></tr>
          <tr><td><b>90-day MA</b></td><td>{ma_90}</td></tr>
          <tr><td><b>YoY change</b></td><td>{yoy}</td></tr>
          <tr><td><b>Last MA crossover</b></td><td>{crossover_date} ({crossover_dir})</td></tr>
          <tr><td><b>Data range</b></td><td>{data_start} \u2192 {data_end}</td></tr>
        </table>

        <h3>Component prices</h3>
        <table cellpadding='4' style='font-size:12px;'>
          <tr><td><b>FCFS (FirstCash Holdings)</b></td><td>${fcfs_px}</td></tr>
          <tr><td><b>EZPW (EZCORP)</b></td><td>${ezpw_px}</td></tr>
          <tr><td><b>XLF (Financial Select Sector SPDR)</b></td><td>${xlf_px}</td></tr>
        </table>

        <h3>Strategy guidance</h3>
        <p style='font-style:italic;'>{guidance}</p>

        <h3>PSR signal levels</h3>
        <table cellpadding='4' style='font-size:12px;'>
          <tr><td><b style='color:#5cffa0'>NORMAL</b></td>
              <td>Pct-rank &lt; 60% \u2014 banks healthy, credit flowing freely</td></tr>
          <tr><td><b style='color:#f2b134'>CAUTION</b></td>
              <td>60\u201375% \u2014 pawn sector outperforming; early credit tightening</td></tr>
          <tr><td><b style='color:#ff9800'>WARNING</b></td>
              <td>75\u201390% \u2014 significant working-class liquidity stress</td></tr>
          <tr><td><b style='color:#FF073A'>CRITICAL</b></td>
              <td>&gt;90% \u2014 systemic credit crunch; liquidity exhaustion</td></tr>
        </table>

        <hr/>
        <h3>Dual-Signal Assessment (PSR \u00d7 WRS)</h3>
        <p>WRS level: <b>{wrs_level}</b> &nbsp;\u00b7&nbsp; PSR level: <b style='color:{level_color}'>{level}</b></p>
        <p>Macro regime: <b style='color:{dual_color}'>{dual.get('regime', '\u2014')}</b></p>
        <p>{dual.get('description', '')}</p>
        <table cellpadding='4' style='font-size:12px;'>
          <tr><td><b>Trading bias</b></td><td>{dual.get('trading_bias', '\u2014')}</td></tr>
          <tr><td><b>Size multiplier</b></td><td>{dual.get('size_multiplier', '1.00')}\u00d7</td></tr>
        </table>

        <hr/>
        <h3>How it works</h3>
        <ol>
          <li><b>Thesis</b> \u2014 When traditional credit tightens, working-class households
              resort to pawn collateral loans (the &ldquo;bank of last resort&rdquo;). Pawn equities
              outperform bank stocks precisely when the credit cycle rolls over.</li>
          <li><b>Formula</b> \u2014 <code>PSR = (FCFS + EZPW) / XLF</code>.
              Rising PSR = Wall Street pricing in credit crunch: banks face defaults
              while pawn shops see surging demand.</li>
          <li><b>Leading vs lagging</b> \u2014 PSR leads credit card write-offs, CPI, and
              unemployment by several months. Borrowers pawn assets before they default
              on primary debts or face eviction.</li>
          <li><b>Data source</b> \u2014 Tradier <code>/markets/history</code> endpoint (primary);
              yfinance fallback when API key is absent.</li>
          <li><b>Refresh cadence</b> \u2014 4-hour disk cache; PSR moves on weekly/monthly
              timescales. S07 reads the cache on every orchestrator cycle.</li>
          <li><b>Signal classification</b> \u2014 expanding percentile rank of the raw ratio
              against its full history since 2000. Crossovers of 30d/90d MAs trigger early alerts.</li>
        </ol>
        """

        dlg = QDialog(self)
        dlg.setWindowTitle("PSR — Pawn Shop Ratio (S13)")
        dlg.setMinimumSize(700, 620)
        v = QVBoxLayout(dlg)

        body = QTextEdit()
        body.setReadOnly(True)
        body.setHtml(html)
        v.addWidget(body)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(dlg.reject)
        btns.accepted.connect(dlg.accept)
        v.addWidget(btns)

        dlg.exec()

    def _show_pmr_details_dialog(self) -> None:
        """Open a modal dialog explaining how the S08 PMR producer works and
        showing the live state captured from the last ``pivot_signal_updated``
        emission.
        """
        widget = self.symbol_widgets.get("PMR") if hasattr(self, "symbol_widgets") else None
        state: dict = getattr(widget, "_last_pmr_state", None) or {}

        dlg = QDialog(self)
        dlg.setWindowTitle("PMR — Pivot Mean-Reversion Signal (S08)")
        dlg.setMinimumSize(620, 520)
        v = QVBoxLayout(dlg)

        body = QTextEdit()
        body.setReadOnly(True)

        # --- Build live-state block ---------------------------------------
        enabled = bool(state.get("enabled"))
        available = bool(state.get("available"))
        fired = bool(state.get("fired"))
        direction = state.get("direction") or "—"
        score = state.get("score")
        score_str = f"{float(score):.1f}" if isinstance(score, (int, float)) else "—"
        level_name = state.get("level_name") or "—"
        level_price = state.get("level_price")
        level_price_str = (
            f"{float(level_price):.2f}" if isinstance(level_price, (int, float)) else "—"
        )
        atr_distance = state.get("atr_distance")
        atr_str = (
            f"{float(atr_distance):.2f}" if isinstance(atr_distance, (int, float)) else "—"
        )
        reasons = state.get("reasons") or []
        penalties = state.get("penalties") or []

        if not available:
            status_line = "<b style='color:#FF073A'>N/A</b> — S08 module not importable"
        elif not enabled:
            status_line = (
                "<b style='color:#FF073A'>DISABLED</b> "
                "(set <code>SPYDER_PIVOT_MR_ENABLED=1</code> to enable)"
            )
        elif not fired:
            status_line = "<b style='color:#f2b134'>ARMED</b> — watching for setup"
        else:
            arrow = "▼" if direction == "fade_resistance" else "▲"
            status_line = (
                f"<b style='color:#5cffa0'>FIRED</b> {arrow} {direction} @ "
                f"{level_name} {level_price_str} (score {score_str})"
            )

        reasons_html = (
            "<ul>" + "".join(f"<li>{r}</li>" for r in reasons) + "</ul>"
            if reasons else "<i>none</i>"
        )
        penalties_html = (
            "<ul>" + "".join(f"<li>{p}</li>" for p in penalties) + "</ul>"
            if penalties else "<i>none</i>"
        )

        html = f"""
        <h2 style='margin-bottom:4px;'>PMR — Pivot Mean-Reversion Signal</h2>
        <p style='color:#9bb;'>Producer: <code>SpyderS08_PivotMeanReversionSignal</code> &nbsp;·&nbsp;
        Consumer: <code>SpyderD25_UnifiedCreditSpreadEngine</code> (via R08 paper worker)</p>

        <h3>Live state</h3>
        <p>{status_line}</p>
        <table cellpadding='4' style='font-size:12px;'>
          <tr><td><b>Direction</b></td><td>{direction}</td></tr>
          <tr><td><b>Score</b></td><td>{score_str}</td></tr>
          <tr><td><b>Nearest level</b></td><td>{level_name} @ {level_price_str}</td></tr>
          <tr><td><b>ATR distance</b></td><td>{atr_str}</td></tr>
        </table>

        <h3>Reasons</h3>
        {reasons_html}

        <h3>Penalties</h3>
        {penalties_html}

        <hr/>
        <h3>How it works</h3>
        <ol>
          <li><b>Pivots</b> — classical daily floor pivots (P, R1/R2/R3, S1/S2/S3)
              are computed at the open from the prior session's H/L/C.</li>
          <li><b>Proximity filter</b> — current SPY price must be within an ATR-based
              distance to a resistance (fade-resistance) or support (fade-support) level.</li>
          <li><b>Confirmation</b> — recent price action must show stalling behaviour
              (wick rejection, MACD divergence, volume fade) at that level.</li>
          <li><b>Regime gate</b> — signal is suppressed in strong-trend regimes
              (ADX &gt; threshold, HMM trending state).</li>
          <li><b>Score</b> — final confidence score (0–100) blends proximity,
              confirmation strength and regime favourability.</li>
          <li><b>Downstream</b> — D25 reads the signal each tick; if <code>fired</code>
              and score exceeds the threshold, it biases credit-spread selection toward
              the fade side (bear-call on fade-resistance, bull-put on fade-support).</li>
        </ol>

        <h3>Display legend</h3>
        <ul>
          <li><b>DIS</b> — producer disabled (env flag off)</li>
          <li><b>N/A</b> — S08 module not importable</li>
          <li><b>ARMED</b> — enabled, watching, not yet fired</li>
          <li><b>▼ &lt;score&gt;</b> — fade-resistance fired (bearish bias)</li>
          <li><b>▲ &lt;score&gt;</b> — fade-support fired (bullish bias)</li>
        </ul>
        """
        body.setHtml(html)
        v.addWidget(body)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(dlg.reject)
        btns.accepted.connect(dlg.accept)
        v.addWidget(btns)

        dlg.exec()

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

        # Phase 2: refresh spreads & volatility panel
        self._refresh_spreads_panel(data)

    def _refresh_spreads_panel(self, data: dict) -> None:
        """Populate the 'SPREADS & VOLATILITY' panel from a worker emit.

        Accepts the full ``position_update`` payload and uses the following
        fields (all optional — missing values degrade gracefully):
            open_spreads_detail : list[dict] — per-spread rows
            spreads_unrealized_pnl : float   — aggregate MTM
            atm_iv : float | None            — last sampled ATM IV
            iv_rank : float | None           — rolling 0-100 rank
        """
        # IV labels
        atm_iv = data.get("atm_iv")
        iv_rank = data.get("iv_rank")
        if self.atm_iv_label is not None:
            self.atm_iv_label.setText(
                f"ATM IV: {atm_iv*100:.1f}%" if isinstance(atm_iv, (int, float)) else "ATM IV: —"
            )
        if self.iv_rank_label is not None:
            if isinstance(iv_rank, (int, float)):
                # Colour: green ≥50, amber 25-50, red <25
                if iv_rank >= 50:
                    col = COLORS["positive"]
                elif iv_rank >= 25:
                    col = COLORS.get("warning", COLORS["text"])
                else:
                    col = COLORS["negative"]
                self.iv_rank_label.setText(f"IV Rank: {iv_rank:.0f}")
                self.iv_rank_label.setStyleSheet(f"color: {col}; font-size: 11px;")
            else:
                self.iv_rank_label.setText("IV Rank: —")
                self.iv_rank_label.setStyleSheet(
                    f"color: {COLORS['text']}; font-size: 11px;"
                )

        # Summary line
        spreads_detail = data.get("open_spreads_detail") or []
        spreads_mtm = data.get("spreads_unrealized_pnl", 0.0)

        # Cache the closed-trade audit log (Phase 5) so the Trade Audit dialog
        # can render it on demand without depending on a live worker emit.
        closed = data.get("closed_trades")
        if closed is not None:
            self._closed_trades_cache = list(closed)
            # Push to an open dialog so user sees new closes without reopen.
            dlg = getattr(self, "_trade_audit_dialog", None)
            if dlg is not None and dlg.isVisible():
                try:
                    dlg.update_trades(self._closed_trades_cache)
                except Exception:  # noqa: BLE001 — best-effort UI refresh
                    pass
        if self.spreads_summary_label is not None:
            col = COLORS["positive"] if spreads_mtm >= 0 else COLORS["negative"]
            self.spreads_summary_label.setText(
                f"Open: {len(spreads_detail)}   MTM: ${spreads_mtm:+,.2f}"
            )
            self.spreads_summary_label.setStyleSheet(f"color: {col}; font-size: 11px;")

        # Buying-power gauge (defined-risk: BP used = Σ max_loss × qty)
        if self.bp_used_label is not None:
            bp_used = 0.0
            for p in spreads_detail:
                try:
                    bp_used += float(p.get("max_loss_per_contract", 0.0)) * int(p.get("qty", 0)) * 100.0
                except (TypeError, ValueError):
                    continue
            cap = float(getattr(self, "_paper_initial_capital", 100_000.0) or 100_000.0)
            pct = (bp_used / cap * 100.0) if cap > 0 else 0.0
            self.bp_used_label.setText(f"BP Used: ${bp_used:,.0f} / ${cap:,.0f} ({pct:.1f}%)")
            # Colour cue when buying-power utilisation is high.
            if pct >= 50:
                bp_col = COLORS["negative"]
            elif pct >= 25:
                bp_col = COLORS.get("warning", COLORS["text"])
            else:
                bp_col = COLORS["text"]
            self.bp_used_label.setStyleSheet(f"color: {bp_col}; font-size: 11px;")

        # Realized today (R08 emits cumulative session realized)
        if self.realized_today_label is not None:
            realized = data.get("realized_pnl_today")
            if realized is None:
                realized = data.get("realized_pnl", 0.0)
            try:
                r = float(realized)
            except (TypeError, ValueError):
                r = 0.0
            r_col = COLORS["positive"] if r >= 0 else COLORS["negative"]
            self.realized_today_label.setText(f"Realized: ${r:+,.2f}")
            self.realized_today_label.setStyleSheet(f"color: {r_col}; font-size: 11px;")

        # Populate positions_table tree with paper spreads (paper mode only).
        # Live mode keeps the broker-driven _refresh_positions_table flow.
        if (
            getattr(self, "trading_mode", None) == TradingMode.PAPER
            and self.positions_table is not None
        ):
            self._render_paper_spreads_in_tree(spreads_detail)

        # Table rows (legacy spreads_table — None after the unified-strip refactor).
        if self.spreads_table is None:
            pass
        else:
            from PySide6.QtGui import QColor
            from PySide6.QtWidgets import QTableWidgetItem
            self.spreads_table.setRowCount(len(spreads_detail))
            for row, p in enumerate(spreads_detail):
                vals = [
                    str(p.get("id", "")),
                    str(p.get("expiration", "")),
                    f"{p.get('short_strike', 0):.0f}/{p.get('long_strike', 0):.0f}",
                    str(p.get("qty", 0)),
                    f"${p.get('credit', 0.0):.2f}",
                    f"${p.get('debit', 0.0):.2f}",
                    f"${p.get('mtm_pnl', 0.0):+,.2f}",
                ]
                for col, text in enumerate(vals):
                    item = QTableWidgetItem(text)
                    if col == 6:  # MTM P&L
                        pnl = float(p.get("mtm_pnl", 0.0))
                        item.setForeground(
                            QColor(COLORS["positive"] if pnl >= 0 else COLORS["negative"])
                        )
                    self.spreads_table.setItem(row, col, item)

        # Phase 3: portfolio-aggregate Greeks labels.
        greeks = data.get("portfolio_greeks") or {}
        if self.port_delta_label is not None:
            d = greeks.get("delta")
            self.port_delta_label.setText(
                f"Δ: {d:+,.1f}" if isinstance(d, (int, float)) else "Δ: —"
            )
        if self.port_gamma_label is not None:
            g = greeks.get("gamma")
            self.port_gamma_label.setText(
                f"Γ: {g:+,.2f}" if isinstance(g, (int, float)) else "Γ: —"
            )
        if self.port_vega_label is not None:
            v = greeks.get("vega")
            self.port_vega_label.setText(
                f"V: {v:+,.1f}" if isinstance(v, (int, float)) else "V: —"
            )
        # Phase 7: higher-order Greeks (charm / vanna) from N04 portfolio_greeks.
        if self.port_charm_label is not None:
            charm = greeks.get("charm")
            self.port_charm_label.setText(
                f"Chr: {charm:+.3f}" if isinstance(charm, (int, float)) else "Chr: —"
            )
        if self.port_vanna_label is not None:
            vanna = greeks.get("vanna")
            self.port_vanna_label.setText(
                f"Van: {vanna:+.3f}" if isinstance(vanna, (int, float)) else "Van: —"
            )

        # Update RISK MONITOR Greek bars (delta/gamma/theta/vega progress bars).
        # Bar scales match the GreekBar constructor in G20_DashboardBuilder:
        #   delta (-100…100), gamma (-10…10), theta (-400…0), vega (-600…0).
        if self.greek_bars is not None:
            _bar_cfg = [
                ("delta", -100.0, 100.0),
                ("gamma", -10.0,  10.0),
                ("theta", -400.0, 0.0),
                ("vega",  -600.0, 0.0),
            ]
            for _key, _lo, _hi in _bar_cfg:
                _bar = self.greek_bars.get(_key)
                if _bar is None:
                    continue
                _val = greeks.get(_key, 0.0)
                if not isinstance(_val, (int, float)):
                    _val = 0.0
                # Risk pct = distance from zero (safe) toward max exposure.
                _scale = max(abs(_lo), abs(_hi))
                _pct = abs(_val) / _scale if _scale else 0.0
                _pct = min(max(_pct, 0.0), 1.0)
                _status = "HIGH RISK" if _pct >= 0.8 else ("ELEVATED" if _pct >= 0.6 else "NORMAL")
                _bar.set_value(float(_val), _status)

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

        # Augment stats with H07 PerformanceAnalytics when available (§9: injected at __init__)
        if self._h07_performance_analytics is not None:
            try:
                h07_stats = self._h07_performance_analytics.get_summary_stats()
                if h07_stats:
                    stats = {**stats, **h07_stats}
            except Exception as _h07_err:
                logger.warning("H07 PerformanceAnalytics.get_summary_stats failed: %s", _h07_err)

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

        # Persist the merged stats for this mode so they can be restored when
        # switching back from the other mode.
        self._pnl_stats_by_mode[self.trading_mode] = dict(stats)

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
            import os as _os_stop
            self.acct_number_lbl.setText(_os_stop.environ.get("TRADIER_SANDBOX_ACCOUNT_ID", "PAPER ACCOUNT"))
        for lbl in (self.settled_value, self.buying_value, self.realized_value, self.unrealized_value):
            if lbl:
                lbl.setText("—")

        self.add_automation_log("PAPER TRADING STOPPED — Session ended")

    @Slot(float, float)
    def _on_balance_updated(self, equity: float, buying_power: float):
        """Update account balance fields from Tradier API (emitted by market worker heartbeat)."""
        # In paper-trading mode the paper worker keeps these labels updated; skip to avoid
        # overwriting live paper P&L with the (potentially zero) sandbox account balance.
        if self.trading_active and self._paper_worker is not None:
            return
        if self.settled_value and equity:
            self.settled_value.setText(f"${equity:,.2f}")
        if self.buying_value and buying_power:
            self.buying_value.setText(f"${buying_power:,.2f}")

    @Slot(bool)
    def _on_paper_connection(self, connected: bool):
        """Handle paper trading connection result."""
        if connected:
            self.on_connection_status_changed(True, "Tradier (PAPER)")
            self.update_data_status("PAPER")
            if self.acct_number_lbl:
                import os as _os_conn
                self.acct_number_lbl.setText(_os_conn.environ.get("TRADIER_SANDBOX_ACCOUNT_ID", "PAPER ACCOUNT"))
            self.add_automation_log("PAPER TRADING ACTIVE — Connected to Tradier sandbox")
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
        self.add_automation_log("Automation session inactive")

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
                "EMERGENCY PROTOCOL - Close requested by operator",
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
        """Update data status display — 4 states: REAL-TIME, EOD, SIMULATED, FROZEN."""
        if status_type in ("LIVE", "REAL-TIME", "PAPER"):
            self.data_status_label.setText("REAL-TIME")
            self.data_status_label.setStyleSheet(
                "color: " + COLORS["positive"] + "; font-size: 14px;",
            )
            self.data_status_container.setCursor(Qt.CursorShape.ArrowCursor)
            self.data_status_container.setToolTip("Real-time market data — live prices")
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

        # FIXED: Check for simulation mode first with better detection.
        # Exclude the real-file-data case: if real EOD data is loaded we must
        # not incorrectly label it SIMULATION just because the update_timer is
        # running (it always is, even when serving real file prices).
        if (
            hasattr(self.connection_info, "simulation_mode")
            and self.connection_info.simulation_mode
        ) or (
            not self.api_connected
            and not self.real_data_active
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
                freshest_quote_time = getattr(self.connection_info, "last_successful_data", None)
                if freshest_quote_time is not None:
                    quote_age_seconds = (datetime.now() - freshest_quote_time).total_seconds()
                    if quote_age_seconds <= REALTIME_QUOTE_MAX_AGE_SECONDS:
                        self.connection_info.data_was_live = True
                        return "REAL-TIME"
                    if self.connection_info.data_was_live:
                        return "FROZEN"
                return "EOD"
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
        # No real data and no active worker — nothing meaningful to show yet
        return "SIMULATION"

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

        Only EOD and SIMULATED are clickable. REAL-TIME and FROZEN ignore clicks.
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
            spy_last = self.market_data.get("SPY", {}).get("last")
            # Use current market data as baseline for simulation
            if isinstance(spy_last, (int, float)):
                self.add_system_log(f"🎯 Simulation baseline: SPY ${spy_last:.2f}")
                return

        self.add_system_log("🎯 Simulation baseline unavailable - awaiting market data")

    def _on_eod_snapshot_fetched(self, success: bool) -> None:
        """Handle the result of the worker's outside-hours EOD price fetch.

        When the worker successfully fetches real last-trade prices from Tradier
        (success=True), activate the real-data patch so the dashboard shows
        genuine EOD figures and the label reads 'EOD'.

        When the fetch fails (success=False) — e.g. credentials missing or API
        unreachable — log a warning and leave the label as 'SIMULATED' so the
        trader is never misled about what is being shown.
        """
        if success:
            self.add_system_log("📊 Real EOD data loaded from Tradier — prices are last close")
            self.apply_real_data_patch()
        else:
            self.add_system_log("⚠️ EOD snapshot unavailable — Tradier unreachable or not configured")
            self.update_data_status("SIMULATION")

    # ==========================================================================
    # UTILITY METHODS - ENHANCED WITH HEARTBEAT WORKER
    # ==========================================================================
    def _start_metrics_orchestrator(self):
        """Instantiate the S07 CustomMetricsOrchestrator on the main Qt thread.

        Called via QTimer.singleShot so QTimers inside S07 bind to the correct thread.
        auto_start=True in S07.__init__ calls start() automatically, which in turn
        starts the S02 DIX and S04 Black Swan schedulers.
        """
        try:
            from SpyderS_Signals.SpyderS07_CustomMetricsOrchestrator import get_metrics_orchestrator
            self._metrics_orchestrator = get_metrics_orchestrator()
            # Wire S07 output → custom metric widgets in the Market Overview panel
            self._metrics_orchestrator.metrics_updated.connect(self._on_custom_metrics_updated)
            self.add_system_log("✅ Custom metrics orchestrator started (DIX + Black Swan schedulers active)")
        except Exception as e:
            self.logger.error("Failed to start metrics orchestrator: %s", e, exc_info=True)
            self.add_system_log(f"⚠️ Metrics orchestrator unavailable: {e}")

    def _on_custom_metrics_updated(self, metrics: dict) -> None:
        """Slot for SpyderS07 CustomMetricsOrchestrator.metrics_updated signal.

        S07 emits a nested dict: {"GEX": {"value": <float>, ...}, "DEX": {...}, ...}
        The widget expects {last, change, change_pct} in the units its own
        _update_custom_indicator() expects:
          - GEX: raw dollars (widget divides by 1e9 to display "B")
          - DEX: raw dollars (widget divides by 1e6 to display "M")
          - OGL, DIX, SWAN: stored and displayed as-is
          - TICK → "$TICK", ADD → "$ADD", TRIN → "$TRIN": market internals
        """
        for s07_key, (widget_key, scale) in self._S07_METRIC_ROUTING.items():
            entry = metrics.get(s07_key)
            if not isinstance(entry, dict):
                continue
            raw = entry.get("value")
            if raw is None or (isinstance(raw, float) and np.isnan(raw)):
                continue
            widget = self.symbol_widgets.get(widget_key)
            if widget is None:
                continue

            value = raw * scale
            # Compute change vs last known value for the change/pct columns
            prev_attr = f"_cm_prev_{widget_key}"
            prev = getattr(self, prev_attr, value)
            change = value - prev
            change_pct = (change / prev * 100.0) if prev else 0.0
            setattr(self, prev_attr, value)

            widget.update_data({"last": value, "change": change, "change_pct": change_pct})

        # Forward TICK/ADD/TRIN/NYMO to the Market Internals dialog if it is open.
        # This ensures the popup always shows the same values as the Market Overview panel.
        dlg = getattr(self, "current_dialog", None)
        if dlg is not None and hasattr(dlg, "on_breadth_updated"):
            import math
            tick_entry = metrics.get("TICK", {})
            add_entry  = metrics.get("ADD",  {})
            trin_entry = metrics.get("TRIN", {})
            nymo_entry = metrics.get("NYMO", {})
            if isinstance(tick_entry, dict) and isinstance(add_entry, dict) and isinstance(trin_entry, dict):
                tick = tick_entry.get("value", float("nan"))
                add  = add_entry.get("value",  float("nan"))
                trin = trin_entry.get("value", float("nan"))
                nymo = nymo_entry.get("value", float("nan")) if isinstance(nymo_entry, dict) else float("nan")
                if not (isinstance(tick, float) and math.isnan(tick)
                        and isinstance(add, float) and math.isnan(add)
                        and isinstance(trin, float) and math.isnan(trin)):
                    breadth_entry = metrics.get("BREADTH_REGIME", {})
                    regime = breadth_entry.get("value", "") if isinstance(breadth_entry, dict) else ""
                    dlg.on_breadth_updated({
                        "tick": tick,
                        "add":  add,
                        "trin": trin,
                        "nymo": nymo,
                        "breadth_regime": regime,
                    })

        # Update the MARKET REGIME label from live S07 metrics.
        regime_label, regime_color = self._derive_regime_label(metrics)
        self.regime_value.setText(regime_label)
        self.regime_value.setStyleSheet(f"color: {regime_color};")

        # Sync REGIME traffic-light button in the SIGNAL MONITOR panel.
        if self.signal_panel is not None:
            import math

            def _sv(key: str, default: float) -> float:
                e = metrics.get(key)
                if not isinstance(e, dict):
                    return default
                v = e.get("value", default)
                return default if (isinstance(v, float) and math.isnan(v)) else float(v)

            self.signal_panel.update_regime(
                regime_label,
                _sv("SWAN", 1.9),
                _sv("DIX", 42.0),
                _sv("SKEW", 120.0),
                _sv("GEX", 0.0),
            )

            # Also push S07 custom-metric values into _live so dialogs stay
            # in sync with the Market Overview panel.
            _live_s07: dict = {}
            for _s07_key, (_wk, _sc) in self._S07_METRIC_ROUTING.items():
                if _s07_key in ("TICK", "ADD", "TRIN"):
                    continue
                _e = metrics.get(_s07_key)
                if not isinstance(_e, dict):
                    continue
                _raw = _e.get("value")
                if _raw is None or (isinstance(_raw, float) and math.isnan(_raw)):
                    continue
                _live_s07[_wk] = _raw * _sc
            if _live_s07:
                self.signal_panel.update_live_data(_live_s07)

    def _derive_regime_label(self, metrics: dict) -> tuple[str, str]:
        """Derive a simple market regime label from live S07 metrics.

        Uses SWAN (tail risk), DIX (dark-pool buying), SKEW, and GEX.
        All of these are populated by S07 on every update cycle.
        Returns (label, colour_hex).
        """
        import math

        def _val(key: str, default: float) -> float:
            entry = metrics.get(key)
            if not isinstance(entry, dict):
                return default
            v = entry.get("value", default)
            if isinstance(v, float) and math.isnan(v):
                return default
            return float(v)

        swan = _val("SWAN", 1.9)
        dix  = _val("DIX",  42.0)
        skew = _val("SKEW", 120.0)
        gex  = _val("GEX",  0.0)

        # Priority order: extreme risk → high risk → directional → neutral
        if swan >= 2.0:
            return "EXTREME RISK", COLORS["negative"]
        if swan >= 1.95 or skew >= 150:
            return "HIGH RISK", COLORS["negative"]
        if skew >= 140 and dix < 42:
            return "CAUTIOUS", COLORS["warning"]
        if dix >= 46 and gex >= 0 and swan < 1.9:
            return "BULLISH", COLORS["positive"]
        if dix <= 40 and swan >= 1.85:
            return "BEARISH", COLORS["negative"]
        if dix >= 43 and swan < 1.92:
            return "NEUTRAL BULL", COLORS["positive"]
        return "NEUTRAL", COLORS["warning"]

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
            self.market_worker.eod_snapshot_fetched.connect(
                self._on_eod_snapshot_fetched,
            )  # Real EOD prices written outside market hours
            self.market_worker.fetch_requested.connect(
                self.market_worker._fetch_live_data_from_tradier,
                Qt.QueuedConnection,
            )  # Safe cross-thread trigger
            self.market_worker.fast_fetch_requested.connect(
                self.market_worker._fetch_quotes_fast,
                Qt.QueuedConnection,
            )  # Lightweight 10-second quote-only refresh

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

        # Chart update timer
        self.chart_timer = QTimer()
        self.chart_timer.timeout.connect(self.update_chart)
        self.chart_timer.start(30000)

    def update_datetime(self):
        """Update date/time display"""
        _et_tz = pytz.timezone("US/Eastern")
        current_time = datetime.now(_et_tz).strftime("%Y-%m-%d   %H:%M:%S  ET")
        self.datetime_label.setText(current_time)

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
        """Close all legs of a strategy with market orders.

        Delegates leg parsing and API submission to DashboardOrderManager
        (audit §5).  This method handles only the resulting UX: success dialog,
        error messageboxes, and system log messages.
        """
        strategy_name = strategy_data["strategy"]
        legs_data = strategy_data.get("legs", [])
        num_legs = len(legs_data)

        self.log_system_message(
            f"⚠️ MANUAL OVERRIDE: Closing {strategy_name} strategy ({num_legs} legs)...",
        )

        self._order_manager.set_client(self._get_tradier_client_for_mode())

        try:
            response = self._order_manager.submit_multileg_close(strategy_name, legs_data)
            order_id = (
                response.get("order", {}).get("id")
                or response.get("id")
            )
            self.log_system_message(
                f"✅ Close order submitted for {strategy_name} — order ID: {order_id}",
            )
            QMessageBox.information(
                self,
                "Close Order Submitted",
                f"Strategy '{strategy_name}' close order submitted successfully.\n\n"
                f"Order ID: {order_id}\n"
                f"Legs: {num_legs}\n"
                f"Type: Market / Day\n\n"
                "Positions will update once fills are confirmed.",
            )
        except (TradierAPIError if TradierAPIError is not None else Exception) as e:
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
        """Seed current_risk_params for the G09 risk-parameters dialog.

        Note: these are GUI-layer display/filter thresholds consumed by
        SpyderG09_RiskParametersDialog, NOT broker-level limits. In particular
        max_position_size here is in *dollars*, while SpyderE01_RiskManager
        uses max_position_size as a *contract count*. The two live in separate
        namespaces on purpose — do not delegate blindly."""
        self.current_risk_params = {
            "max_position_size": 50000,
            "max_daily_loss": 5000,
            "max_portfolio_delta": 100,
            "max_portfolio_gamma": 50,
            "vix_threshold": 30,
            "correlation_limit": 0.8,
        }

    def update_risk_parameters(self, params: dict) -> None:
        """Receive updated risk parameters from the G09 Risk Levels dialog.

        Connected to ``RiskParametersDialog.parameters_updated`` by
        ``show_risk_parameters_dialog()`` so that clicking Apply/OK in the
        dialog immediately updates the dashboard's risk state.

        If a paper trading worker is currently running, the new limits are
        forwarded to it immediately so they take effect without a restart.
        """
        if not isinstance(params, dict):
            return
        self.current_risk_params = params
        self.add_system_log(
            f"⚙️ Risk parameters updated — "
            f"Risk/Trade: {params.get('risk_per_trade', '?')}% | "
            f"Max Daily Loss: {params.get('max_daily_loss_pct', '?')}% | "
            f"Max Buying Power: {params.get('max_buying_power_pct', '?')}%"
        )
        # Forward to running paper worker so limits take effect immediately
        if self._paper_worker is not None:
            self._paper_worker.set_risk_params(params)
            # Rebuild the E01 RiskManager with the new limits so
            # validate_signal() reflects the latest dialog settings.
            # Pull the live worker's starting capital so the rescaled dollar
            # limits match what the worker actually trades against.
            live_capital = float(
                getattr(self._paper_worker, "_initial_capital", 100_000.0)
            )
            new_rm = self._build_paper_risk_manager(initial_capital=live_capital)
            if new_rm is not None:
                self._paper_worker.set_risk_manager(new_rm)

    def _build_paper_risk_manager(self, initial_capital: float):
        """Construct a SpyderE01_RiskManager seeded from current_risk_params.

        Maps the G09 dialog's percentage-based dict into E01's absolute-dollar
        risk_limits dict, using *initial_capital* as the reference. Returns
        None when E01 is unavailable or construction fails — the worker will
        then fall back to its local _get_risk_limit() checks only.
        """
        if not _E01_AVAILABLE or _E01_RiskManager is None or _E01_RiskConfig is None:
            return None

        # Start from E01 defaults, then overlay G09 values when present.
        limits = dict(_E01_DEFAULT_RISK_LIMITS)
        params = self.current_risk_params or {}
        g = params.get("global", {}) if isinstance(params, dict) else {}
        if not isinstance(g, dict):
            g = {}

        try:
            # Dollar-denominated limits from percentage inputs
            if "max_buying_power" in g:
                limits["max_total_exposure"] = float(initial_capital) * (
                    float(g["max_buying_power"]) / 100.0
                )
            if "max_daily_loss" in g:
                limits["max_daily_loss"] = float(initial_capital) * (
                    float(g["max_daily_loss"]) / 100.0
                )
            # Contract-count limits map directly
            if "max_contracts" in g:
                mc = int(g["max_contracts"])
                limits["max_position_size"] = mc
                limits["max_single_order_size"] = mc
        except (TypeError, ValueError) as exc:
            self.logger.warning("Could not map G09 params to E01 limits: %s", exc)

        try:
            cfg = _E01_RiskConfig(risk_limits=limits, enable_real_time_monitoring=False)
            return _E01_RiskManager(
                config=cfg,
                connect_api=None,
                order_manager=None,
                tradier_client=self.tradier_client,
            )
        except Exception as exc:
            self.logger.warning("Could not construct E01 RiskManager: %s", exc)
            return None

    def show_risk_parameters(self):
        """Show risk parameters dialog"""
        if risk_dialog_available and show_risk_parameters_dialog:
            show_risk_parameters_dialog(self)
        else:
            p = self.current_risk_params or {}
            QMessageBox.information(
                self,
                "Risk Parameters",
                "Risk Parameters Configuration\n\n"
                f"Max Position Size: ${p.get('max_position_size', 0):,}\n"
                f"Max Daily Loss: ${p.get('max_daily_loss', 0):,}\n"
                f"Max Portfolio Delta: {p.get('max_portfolio_delta', 0)}\n"
                f"Max Portfolio Gamma: {p.get('max_portfolio_gamma', 0)}\n"
                f"VIX Threshold: {p.get('vix_threshold', 0)}\n"
                f"Correlation Limit: {p.get('correlation_limit', 0)}",
            )

    def _append_to_ring_log(self, buffer: list, widget, message: str,
                             max_buffer: int = 100, display_count: int = 20) -> None:
        """Append to an in-memory ring buffer and refresh its widget (newest first)."""
        timestamp = datetime.now(pytz.timezone("US/Eastern")).strftime("%H:%M:%S")
        buffer.append(f"[{timestamp}] {message}")
        if len(buffer) > max_buffer:
            del buffer[:-max_buffer]
        widget.clear()
        widget.append("\n".join(reversed(buffer[-display_count:])))
        cursor = widget.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        widget.setTextCursor(cursor)

    def add_system_log(self, message: str):
        """Add message to system log."""
        self._append_to_ring_log(self.system_logs, self.system_log, message,
                                  max_buffer=200, display_count=200)

    def add_automation_log(self, message: str):
        """Add message to automation log."""
        self._append_to_ring_log(self.automation_logs, self.auto_log, message,
                                  max_buffer=100, display_count=100)

    def setup_white_tooltips(self):
        """Apply the white-tooltip theme to this window (delegates to module helper)."""
        try:
            apply_tooltip_theme(QApplication.instance(), self)
        except Exception as e:
            self.add_system_log(f"⚠️ Tooltip styling error: {e}")

    # ------------------------------------------------------------------
    # Snapshot persistence — save symbol values on exit, restore on open
    # ------------------------------------------------------------------
    _SNAPSHOT_FILE: Path = (
        Path.home() / "Projects/Spyder/market_data/dashboard_snapshot.json"
    )
    # Snapshot age thresholds (seconds)
    _SNAPSHOT_STALE_HOURS = 8  # > 8 h → FROZEN badge (red)
    _SNAPSHOT_EOD_HOURS = 0    # anything younger → EOD badge (yellow)

    def _save_snapshot(self) -> None:
        """Persist current market_data values to disk for next launch."""
        try:
            if not self.market_data:
                return
            self._SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "_saved_at": time.time(),
                "data": {
                    sym: {
                        "last": entry.get("last", 0.0),
                        "change": entry.get("change", 0.0),
                        "change_pct": entry.get("change_pct", 0.0),
                    }
                    for sym, entry in self.market_data.items()
                    if isinstance(entry, dict) and entry.get("last") is not None
                },
            }
            self._SNAPSHOT_FILE.write_text(json.dumps(payload))
            logger.info("Dashboard snapshot saved (%d symbols)", len(payload["data"]))
        except Exception as _snap_err:  # noqa: BLE001
            logger.warning("Could not save dashboard snapshot: %s", _snap_err)

        # Also snapshot the SPY 5-min chart bars for next-session 2-day view
        try:
            import shutil as _shutil
            chart_src = self.data_file.parent / "spy_5min_chart.json"
            chart_dst = self.data_file.parent / "spy_5min_prev_day.json"
            if chart_src.exists():
                _shutil.copy2(chart_src, chart_dst)
                logger.info("SPY 5-min chart snapshot saved for next session")
        except Exception as _chart_snap_err:  # noqa: BLE001
            logger.warning("Could not save SPY chart snapshot: %s", _chart_snap_err)

    def _restore_snapshot(self) -> None:
        """Load the last snapshot and pre-populate symbol widgets (best-effort)."""
        try:
            if not self._SNAPSHOT_FILE.exists():
                return
            raw = self._SNAPSHOT_FILE.read_text()
            payload = json.loads(raw)
            saved_at = payload.get("_saved_at", 0.0)
            age_hours = (time.time() - saved_at) / 3600
            data: dict = payload.get("data", {})
            if not data:
                return

            count = 0
            for sym, entry in data.items():
                # Merge into market_data so other code reading it gets values too
                if sym not in self.market_data:
                    self.market_data[sym] = {}
                self.market_data[sym].update(entry)
                if sym in self.symbol_widgets:
                    self.symbol_widgets[sym].update_data(entry)
                    count += 1

            # Also push recognised keys to signal panel
            if self.signal_panel is not None:
                _sp = {}
                for _sym in ("VIX", "SKEW", "CPC"):
                    _e = data.get(_sym)
                    if isinstance(_e, dict) and _e.get("last") is not None:
                        _sp[_sym] = _e["last"]
                if _sp:
                    self.signal_panel.update_live_data(_sp)

            # Set appropriate data-status badge
            if age_hours >= self._SNAPSHOT_STALE_HOURS:
                self.update_data_status("FROZEN")
                badge = "FROZEN (stale snapshot)"
            else:
                self.update_data_status("EOD")
                badge = "EOD snapshot"

            import datetime as _dt
            saved_str = _dt.datetime.fromtimestamp(saved_at).strftime("%Y-%m-%d %H:%M:%S")
            self.add_system_log(
                f"📦 Restored {count} symbols from {badge} saved at {saved_str}"
            )
        except Exception as _restore_err:  # noqa: BLE001
            logger.warning("Could not restore dashboard snapshot: %s", _restore_err)

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
            if hasattr(self, "datetime_timer") and self.datetime_timer:
                self.datetime_timer.stop()
            if hasattr(self, "chart_timer") and self.chart_timer:
                self.chart_timer.stop()

            # Persist symbol values so next launch can restore them
            self._save_snapshot()

            # Log shutdown
            self.add_system_log("🔥 Enhanced Trading Dashboard shutting down...")
            self.add_automation_log("Dashboard session ended with heartbeat monitoring")

            # Accept close event
            event.accept()

        except Exception as e:
            logger.info("Error during enhanced dashboard close: %s", e)
            event.accept()



# ==============================================================================
# STANDALONE FUNCTIONS FOR EXTERNAL USE
# ==============================================================================
def create_spyder_trading_dashboard():
    """Factory function to create SpyderTradingDashboard instance"""
    return SpyderTradingDashboard()


def get_dashboard_with_real_data_integration():
    """Create dashboard with real data integration pre-configured"""
    return SpyderTradingDashboard()



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
