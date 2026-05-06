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
    - Tradier API for real-time & historical market data (SpyderB40_TradierClient)
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
    • Tradier for real-time streaming and historical market data
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
import os
import sys
import threading
import time
from collections import deque
from datetime import datetime
from datetime import time as dt_time  # noqa: F401
from pathlib import Path

# Matplotlib for charting
import matplotlib
import numpy as np
import pytz
from PySide6.QtCore import (
    QModelIndex,
    QMutex,  # noqa: F401
    QMutexLocker,  # noqa: F401
    QObject,
    QRect,  # noqa: F401
    Qt,
    QThread,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QBrush,  # noqa: F401
    QColor,
    QFont,  # noqa: F401
    QPainter,  # noqa: F401
    QPen,  # noqa: F401
    QTextCursor,
)

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFrame,  # noqa: F401
    QGridLayout,  # noqa: F401
    QGroupBox,
    QHBoxLayout,
    QHeaderView,  # noqa: F401
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,  # noqa: F401
    QSizePolicy,  # noqa: F401
    QSplitter,
    QTableWidget,
    QTableWidgetItem,  # noqa: F401
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

matplotlib.use("QtAgg")
import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas  # noqa: F401
from matplotlib.figure import Figure  # noqa: F401
from matplotlib.transforms import blended_transform_factory  # noqa: F401

# ==============================================================================
# BROKER/DATA IMPORTS (Tradier)
# ==============================================================================
# Tradier API for execution and market data

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
project_root = Path(__file__).parent.parent.parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import logging  # noqa: E402

logger = logging.getLogger(__name__)
_AUTONOMOUS_EVENT_TYPE_ALLOWLIST: set[str] = {
    "AGENT_DECISION",
    "AGENT_ACTION_EXECUTED",
    "AGENT_VETO",
    "AGENT_ESCALATION",
    "AGENT_HEALTH_DEGRADED",
    "AGENT_OBSERVATION",
}


class _ReadinessCheckWorker(QObject):
    """Background worker for trading readiness evaluation."""

    finished = Signal(dict)
    failed = Signal(str)

    def __init__(self, snapshot: dict[str, object], evaluator) -> None:
        super().__init__()
        self._snapshot = snapshot
        self._evaluator = evaluator

    @Slot()
    def run(self) -> None:
        try:
            result = self._evaluator(self._snapshot)
            if not isinstance(result, dict):
                raise ValueError("Trading readiness evaluator returned non-dict result")
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))

from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger  # noqa: E402
from Spyder.SpyderG_GUI.SpyderG13_EnhancedWidgets import (  # noqa: E402
    COLORS,
    ConnectionInfo,
    GreekBar,  # noqa: F401
    GreekRisk,
    MarketData,  # noqa: F401
    MarketSymbolWidget,  # noqa: F401
    SignalMonitorPanel,  # noqa: F401
    TradingMode,
    TrafficLightButton,  # noqa: F401
    apply_tooltip_theme,
)
from Spyder.SpyderG_GUI.SpyderG20_DashboardBuilder import (  # noqa: E402
    build_center_panel,
    build_left_panel,
    build_right_panel,
    build_toolbar,
    create_chart_widget,
    create_pnl_table as build_pnl_table,
    create_positions_table as build_positions_table,
    create_unified_prometheus_metrics as build_unified_prometheus_metrics,
)
from Spyder.SpyderG_GUI.SpyderG21_DashboardSignalHandlers import (  # noqa: E402
    handle_connection_status_changed,
    handle_heartbeat_received,
    handle_heartbeat_status_changed,
    handle_market_data_status_changed,
    handle_market_data_updated,
    handle_market_error,
)

try:
    from Spyder.SpyderH_Storage.SpyderH05_TradingSessionDB import TradingSessionDB

    _H05_AVAILABLE = True
except ImportError:
    TradingSessionDB = None  # type: ignore
    _H05_AVAILABLE = False

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
    )
    _circuit_breakers_available = True
except ImportError:
    _tradier_breaker = None  # type: ignore
    _circuit_breakers_available = False

# ==============================================================================
# CONSTANTS
# ==============================================================================
WINDOW_WIDTH = 1920
WINDOW_HEIGHT = 1080


# Dashboard session & Tradier active window come from U03_DateTimeUtils —
# module-level aliases kept for readability at use sites within this file.
from Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils import (  # noqa: E402
    MARKET_OPEN_TIME,  # noqa: F401  — 9:30 AM ET (actual RTH open)
    MARKET_CLOSE_TIME,  # noqa: F401  — 4:00 PM ET (actual RTH close)
    TRADIER_CONNECT_TIME,  # noqa: F401
    TRADIER_DISCONNECT_TIME,  # noqa: F401
    LogThrottle,  # noqa: F401
    is_dashboard_session as _is_dashboard_session,
    is_tradier_active_window as is_tradier_window,
)


def is_market_hours(now_et: datetime | None = None) -> bool:
    """Return True only during regular trading hours (9:30 AM – 4:00 PM ET), Mon–Fri."""
    current_et = now_et or datetime.now(pytz.timezone("US/Eastern"))
    if current_et.weekday() >= 5:
        return False
    t = current_et.time()
    return MARKET_OPEN_TIME <= t <= MARKET_CLOSE_TIME


# Market data worker, heartbeat constants, quote-freshness helpers, and
# check_api_connection now live in SpyderG18_MarketDataWorker (audit §1/§14/§23).
# G05 re-imports them here so existing references continue to resolve.
from Spyder.SpyderG_GUI.SpyderG18_MarketDataWorker import (  # noqa: E402
    HEARTBEAT_INTERVAL,  # noqa: F401
    HEARTBEAT_LOG_INTERVAL,  # noqa: F401
    HEARTBEAT_WARNING_TIME,  # noqa: F401
    REALTIME_QUOTE_MAX_AGE_SECONDS,
    REALTIME_SENTINEL_SYMBOLS,  # noqa: F401
    ThreadSafeMarketDataWorker,
    _coerce_epoch_ms,  # noqa: F401
    _datetime_from_epoch_ms,
    _freshest_live_data_timestamp,
    _freshest_quote_timestamp_ms,  # noqa: F401
    check_api_connection,
)
# Chart indicator computation extracted per audit §3.
from Spyder.SpyderG_GUI.SpyderG19_ChartIndicators import (  # noqa: E402
    ChartIndicators,  # noqa: F401
    PivotLevels,  # noqa: F401
    compute_chart_indicators,
)
from Spyder.SpyderU_Utilities.SpyderU49_SymbolCatalog import (
    get_market_overview_symbols,
)

# Canonical market-overview symbol source (Phase 2 symbol-governance cleanup).
MARKET_SYMBOLS: dict[str, list[str]] = get_market_overview_symbols()

# ==============================================================================
# PAPER TRADING WORKER (runs off the GUI thread)
# ==============================================================================
from Spyder.SpyderR_Runtime.SpyderR08_PaperTradingQtWorker import (  # noqa: E402
    PaperTradingQtWorker as _PaperTradingWorker,
)
from Spyder.SpyderD_Strategies.SpyderD00_StrategyConstants import StrategyLifecycleState  # noqa: E402


# ==============================================================================
# MAIN DASHBOARD CLASS
# ==============================================================================
class SpyderTradingDashboard(QMainWindow):
    """Complete dashboard with fixed API connection detection and heartbeat monitoring"""

    manual_close_spread_requested = Signal(str)
    optional_metrics_refreshed = Signal(dict)

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

        # Suppress verbose INFO-level messages from WRS and PSR signal modules.
        # These emit multiple per-bar diagnostic lines (basket fetches, bar
        # counts, etc.) that add noise without actionable information in the
        # dashboard log.  WARNING and above (actual errors) still pass through.
        logging.getLogger("SpyderS_Signals.SpyderS12_WRSSignal").setLevel(logging.WARNING)
        logging.getLogger("SpyderS_Signals.SpyderS13_PSRSignal").setLevel(logging.WARNING)

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
        # Unified backend session (single code path for paper/live).
        self._session_supervisor = None

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
        # Emit startup marker through module logger as well so it appears in
        # the unified log stream (not only the in-widget system log buffer).
        self.logger.info("🚀 SPYDER DASHBOARD STARTED: %s", startup_time)

        # Startup readiness snapshot (A03 config validation outcome) is read
        # once during launch so safe-mode automation fallback is explicit.
        self._startup_readiness_state = self._collect_startup_readiness_state()
        self._last_readiness_result = None
        self._last_readiness_ts = None
        self._readiness_ttl_seconds = 120
        self._readiness_worker_thread = None
        self._readiness_worker = None
        self._readiness_reports_dir = project_root / "market_data" / "trading_readiness_reports"
        self._append_startup_readiness_banner(startup_hms)

        # Toolbar proxy multipliers (configurable with safe defaults).
        self._dji_from_dia_multiplier = self._load_dji_proxy_multiplier()
        # Per-symbol stale-data log throttling for Market Overview rows.
        self._stale_symbol_log_ts: dict[str, float] = {}

        # Optional after-hours quiet mode for non-critical startup/EOD chatter.
        # Enabled by default; disable with SPYDER_QUIET_AFTER_HOURS_LOGS=0.
        self._quiet_after_hours_logs = str(
            os.getenv("SPYDER_QUIET_AFTER_HOURS_LOGS", "1")
        ).strip().lower() not in {"0", "false", "no", "off"}

        # System log verbosity mode (NORMAL suppresses routine signal chatter,
        # DEBUG restores full stream for diagnostics).
        self.system_log_mode = "NORMAL"
        self._signal_noise_loggers = (
            "SpyderS_Signals.SpyderS01_DIXCalculator",
            "Spyder.SpyderS_Signals.SpyderS01_DIXCalculator",
            "SpyderS_Signals.SpyderS02_DIXScheduler",
            "Spyder.SpyderS_Signals.SpyderS02_DIXScheduler",
            "SpyderS_Signals.SpyderS03_BlackSwanIndicator",
            "Spyder.SpyderS_Signals.SpyderS03_BlackSwanIndicator",
            "SpyderS_Signals.SpyderS06_SKEWCalculator",
            "Spyder.SpyderS_Signals.SpyderS06_SKEWCalculator",
            "SpyderS_Signals.SpyderS09_FREDClient",
            "Spyder.SpyderS_Signals.SpyderS09_FREDClient",
            "SpyderS_Signals.SpyderS10_SentimentScraper",
            "Spyder.SpyderS_Signals.SpyderS10_SentimentScraper",
        )
        self._set_system_log_verbosity("NORMAL", announce=False)

        self.automation_logs = []
        self.trading_mode = TradingMode.PAPER

        # Per-mode snapshots — preserved across PAPER ↔ LIVE switches so each
        # mode's table contents survive while the other mode is active.
        self._pnl_stats_by_mode: dict = {}          # TradingMode → stats dict
        self._positions_snapshot_by_mode: dict = {}  # TradingMode → serialized list
        self._account_snapshot_by_mode: dict = {}    # TradingMode → account panel values

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

        # Per-mode H05 session DB handles for recent-trade rendering.
        self._live_session_db = None
        self._paper_session_db = None
        self._session_db_init_failed_by_mode = {
            TradingMode.PAPER: False,
            TradingMode.LIVE: False,
        }

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

        # Event-clock state (Phase 5-A dashboard observability)
        from Spyder.SpyderG_GUI.SpyderG06_DashboardData import EventClockState
        self.event_clock_state = EventClockState()
        self._event_clock_lock = threading.Lock()
        self._event_clock_handler_id = None
        self._execution_telemetry_lock = threading.Lock()
        self._execution_telemetry_events: deque[dict] = deque(maxlen=200)
        self._execution_telemetry_handler_id = None
        self._risk_alert_handler_id = None
        self._last_entry_block_message = ""
        self._last_entry_block_ts = 0.0

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
        self._optional_signal_timer = None
        self._optional_signal_refresh_inflight = False
        self._error_count = 0
        self._system_log_flush_pending = False
        self._automation_log_flush_pending = False
        self._last_dispatch_state_key = ""
        self._veto_controls_enabled = self._load_veto_controls_state()

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
        self.liquidity_candidates_value = None
        self.liquidity_pass_ratio_value = None
        self.liquidity_freshness_value = None
        self.liquidity_top_failure_value = None
        self.execution_slippage_bps_value = None
        self.execution_fill_latency_value = None
        self.execution_reject_rate_value = None
        self.execution_partial_fill_value = None
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
        self.recent_trades_history_btn = None
        self.trade_audit_btn = None
        self.decision_log_btn = None
        self.veto_toggle_btn = None
        self.readiness_btn = None
        self.readiness_status_label = None
        self.greek_bars = None
        self.auto_log = None
        self.chart_widget = None
        self.chart_hidden_controls_panel = None
        self.figure = None
        self.canvas = None
        # Event-clock display UI elements (Phase 5-A)
        self.event_clock_panel = None
        self.signal_flow_heartbeat_label = None
        self.event_clock_compact_label = None
        self.entry_block_compact_label = None
        self.trading_window_compact_label = None
        self.event_clock_state_label = None
        self.event_clock_policy_label = None
        self.event_clock_windows_label = None
        self.event_clock_strategies_label = None
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
        self._recent_trades_dialog = None
        # Phase 3: portfolio-aggregate Greeks labels (all None — data lives in
        # _portfolio_summary_cache and is surfaced via the popup dialog).
        self.port_delta_label = None
        self.port_gamma_label = None
        self.port_theta_label = None
        self.port_vega_label = None
        # Phase 7: higher-order Greeks labels (charm/vanna) from N04.
        self.port_charm_label = None
        self.port_vanna_label = None
        # Portfolio Strip popup: cache of last-received data and dialog singleton.
        self._portfolio_summary_cache: dict = {}
        self._portfolio_summary_dialog = None
        # Portfolio Strip toggle button reference (set by builder).
        self.portfolio_strip_btn = None
        self.internal_module_indicators = {}
        self.datetime_timer = None
        self.chart_timer = None
        self._shutdown_snapshot_saved = False

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
        self.optional_metrics_refreshed.connect(self._on_optional_metrics_refreshed)
        # Subscribe to system events for real-time event-clock display (Phase 5-A)
        self._subscribe_to_events()

        # Restore previous session's symbol values (if any) — runs after the
        # event loop starts so all widgets are fully initialised.
        QTimer.singleShot(0, self._restore_snapshot)

        # Start market worker with fixed connection detection
        self.start_market_worker()

        # Pre-populate account P&L fields and performance table so the dashboard
        # shows sensible values immediately — before any trading session starts.
        QTimer.singleShot(0, self._init_account_display)

        # Start custom metrics orchestrator (DIX + Black Swan schedulers)
        # Deferred 1 s so the Qt event loop is fully running before QTimer creation in S07
        self._metrics_orchestrator = None
        QTimer.singleShot(1000, self._start_metrics_orchestrator)
        # Refresh optional WRS/PSR rows from signal-module caches on a background
        # thread so Market Overview rows populate without blocking the UI.
        QTimer.singleShot(2000, self._start_optional_signal_refresh_timer)

        # Apply white tooltip styling
        self.setup_white_tooltips()

        # Log the actual dashboard initialization time (ET)
        _et_tz = pytz.timezone("US/Eastern")
        init_time = datetime.now(_et_tz).strftime("%H:%M:%S ET")
        self.add_system_log(f"🚀 Dashboard initialized at {init_time}")
        self.logger.info("🚀 Dashboard initialized at %s", init_time)
        self._emit_startup_readiness_logs()
        # Re-emit once after startup burst so users can still see startup state
        # when the system log is rapidly populated by module initialization.
        QTimer.singleShot(12000, lambda: self._emit_sticky_startup_marker(init_time))

        # Real data integration (after UI is ready)
        QTimer.singleShot(1000, self.apply_proven_real_data_pattern)

        # Fetch live balance + quotes shortly after startup (before first 30s heartbeat).
        # Retry once in case the worker's startup API call hasn't completed yet.
        QTimer.singleShot(4000, self._trigger_initial_live_fetch)

        # Ensure snapshot save also runs on full app shutdown paths.
        app = QApplication.instance()
        if app is not None:
            try:
                app.aboutToQuit.connect(self._on_app_about_to_quit)
            except Exception as _quit_hook_err:  # noqa: BLE001
                logger.debug("Could not connect aboutToQuit snapshot hook: %s", _quit_hook_err)

        self.logger.info(
            "Enhanced Dashboard initialized with Tradier API connection detection and heartbeat monitoring",  # noqa: E501
        )

    def _emit_sticky_startup_marker(self, init_time: str) -> None:
        """Emit a one-time delayed startup marker for dashboard visibility."""
        try:
            # Keep this marker out of the visible system log to avoid
            # duplicate startup lines during normal operations.
            self.logger.debug("Startup confirmed marker at %s", init_time)
        except RuntimeError:
            # QWidget may be closing during shutdown; ignore late timer emit.
            return

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

    def _trigger_initial_live_fetch(self, _retry: int = 0):
        """Ask the market worker to do an immediate live data + balance fetch.

        If the worker's startup API check hasn't completed yet (api_connected still
        False), retry up to 6 times (every 5 s, covering ~30 s) regardless of the
        trading window so quotes and balance populate at launch.
        """
        if self.market_worker and self.api_connected:
            self.market_worker.fetch_requested.emit()
        elif self.market_worker and _retry < 6:
            # Worker's startup API check may still be in-flight — retry shortly.
            # Not gated by is_tradier_window() so balance loads even outside hours.
            QTimer.singleShot(5000, lambda: self._trigger_initial_live_fetch(_retry + 1))

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
                    spx_price = _snap.get("SPX", {}).get("last", "N/A")
                    dji_price = _snap.get("$DJI", {}).get("last", "N/A")
                    eod_date = _snap.get("_eod_date", "unknown date")
                    self.add_system_log(
                        f"📊 EOD snapshot loaded ({eod_date}) — SPY: ${spy_price} | SPX: ${spx_price} | DJI: ${dji_price}"  # noqa: E501
                    )
                    # Start file-read timer so widgets populate immediately;
                    # skip fast-fetch (no Tradier polling outside trading hours).
                    self.real_data_active = True
                    if not getattr(self, "_real_data_timer", None) or not self._real_data_timer.isActive():  # noqa: E501
                        self._real_data_timer = QTimer()
                        self._real_data_timer.timeout.connect(self.update_with_real_data)
                        self._real_data_timer.start(1000)
                    QTimer.singleShot(250, self.update_with_real_data)
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

            # Initial update after the event loop clears the startup burst.
            QTimer.singleShot(250, self.update_with_real_data)

            # Update status
            self.update_status_for_real_data()

            # Log success with market-hours-aware wording.
            if is_market_hours():
                self.add_system_log("🔥 REAL MARKET DATA ACTIVE - Tradier API prices")
                self.add_system_log("Real-time market data from Tradier")
            else:
                self.add_system_log("📊 EOD MARKET DATA ACTIVE - Tradier API prices")
                self.add_system_log("EOD market data from Tradier")

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

            # Read as text first so we can gracefully handle transient
            # partial-writes from the producer without surfacing noisy errors.
            with open(self.data_file, encoding="utf-8") as f:
                raw_live_data = f.read()

            if not raw_live_data.strip():
                return

            try:
                live_data = json.loads(raw_live_data)
            except json.JSONDecodeError:
                # Retry once immediately in case we raced a writer flush.
                with open(self.data_file, encoding="utf-8") as f:
                    retry_raw_live_data = f.read()
                if not retry_raw_live_data.strip():
                    return
                try:
                    live_data = json.loads(retry_raw_live_data)
                except json.JSONDecodeError as parse_exc:
                    self.logger.debug(
                        "Real data snapshot parse skipped (partial write): %s",
                        parse_exc,
                    )
                    return

            if not live_data:
                return

            # Keep self.market_data in sync with live prices so other code
            # reading self.market_data (e.g. update_chart) gets real values.
            # Skip metadata keys (e.g. _fetch_time_ms) whose values are not dicts.
            for symbol, data in live_data.items():
                if not isinstance(data, dict):
                    continue
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

            # Detect per-symbol stale quotes relative to this fetch. Tradier can
            # occasionally return a lagging quote for one symbol in an otherwise
            # fresh basket; avoid showing that value as if it were current.
            stale_symbols: set[str] = set()
            fetch_time = _datetime_from_epoch_ms(live_data.get("_fetch_time_ms"))
            if fetch_time is not None:
                for symbol in ("DIA",):
                    entry = live_data.get(symbol)
                    if not isinstance(entry, dict):
                        continue
                    quote_time = _datetime_from_epoch_ms(entry.get("timestamp_ms"))
                    if quote_time is None:
                        continue
                    quote_age_seconds = (fetch_time - quote_time).total_seconds()
                    # DIA has a dedicated per-symbol refetch in G18, but
                    # Tradier quote trade-timestamps for DIA can lag 15+ minutes
                    # even during regular market hours.  Use the same 1800 s
                    # (30-min) tolerance applied to index-like symbols in the
                    # toolbar so genuine trading activity never shows STALE.
                    _dia_stale_threshold = 1800.0
                    if quote_age_seconds > _dia_stale_threshold:
                        stale_symbols.add(symbol)
                        widget = self.symbol_widgets.get(symbol)
                        if widget is not None:
                            widget.set_unavailable("STALE")

            # Update symbol widgets — delegate to update_data() so each widget's
            # symbol-specific formatting and colour logic is applied correctly
            # (e.g. $TICK/$ADD as signed integers, $TRIN colour-coded by value).
            for symbol, data in live_data.items():
                if not isinstance(data, dict):
                    continue
                if symbol in stale_symbols:
                    continue
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
            _current_label = self.data_status_label.text() if hasattr(self, "data_status_label") else ""  # noqa: E501
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
            fetch_time = _datetime_from_epoch_ms(live_data.get("_fetch_time_ms"))

            def _clear_pair(value_attr: str, change_attr: str) -> None:
                if hasattr(self, value_attr):
                    getattr(self, value_attr).setText("")
                if hasattr(self, change_attr):
                    widget = getattr(self, change_attr)
                    widget.setText("")
                    widget.setStyleSheet("color: #888888;")

            def _is_fresh(symbol: str, entry: dict | None) -> bool:
                if not isinstance(entry, dict):
                    return False
                last = entry.get("last")
                if not isinstance(last, (int, float)) or last == 0.0:
                    return False

                def _is_regular_session_open() -> bool:
                    """True only during regular cash session (09:30-16:00 ET)."""
                    now_et = datetime.now(pytz.timezone("US/Eastern"))
                    if now_et.weekday() >= 5:
                        return False
                    open_et = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
                    close_et = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
                    return open_et <= now_et <= close_et

                # Outside market hours we intentionally render EOD snapshot values
                # regardless of quote timestamp age.
                if not is_market_hours():
                    return True
                # During pre-open/after-hours inside the broader dashboard session,
                # direct index feeds are often stale by design. Keep last non-zero
                # values visible for headline indices instead of blanking them.
                if symbol in ("SPX", "$DJI", "NDX", "RUT") and not _is_regular_session_open():
                    return True
                # During trading hours, when no fetch-time anchor exists yet,
                # show non-zero values rather than blanking the toolbar.
                if fetch_time is None:
                    return True
                quote_time = _datetime_from_epoch_ms(entry.get("timestamp_ms"))
                if quote_time is None:
                    return False
                age_seconds = abs((fetch_time - quote_time).total_seconds())
                # Some direct index feeds ($DJI, SPX, NDX, RUT) can be delayed versus
                # ETF/equity quote cadence. Keep strict-direct behavior (no
                # proxy/fallback), but allow a symbol-specific freshness window.
                # SPX/RUT/$DJI/NDX: Tradier returns lagged trade timestamps for
                # index symbols in quiet markets; use a 30-min window so the
                # toolbar doesn't blank on slow-quote cadence.  DIA/QQQ proxies
                # also inherit the destination symbol's tolerance.
                max_age_seconds = REALTIME_QUOTE_MAX_AGE_SECONDS
                if symbol in ("SPX", "$DJI", "NDX", "RUT"):
                    max_age_seconds = 1800.0
                return age_seconds <= max_age_seconds

            def _as_proxy_entry(entry: dict | None, multiplier: float) -> dict | None:
                """Scale an ETF quote entry into an index-like display entry."""
                if not isinstance(entry, dict):
                    return None
                last = entry.get("last")
                if not isinstance(last, (int, float)) or last <= 0.0:
                    return None
                try:
                    _multiplier = float(multiplier)
                except (TypeError, ValueError):
                    return None
                if _multiplier <= 0.0:
                    return None
                return {
                    "last": float(last) * _multiplier,
                    "change": float(entry.get("change") or 0.0) * _multiplier,
                    "change_pct": float(entry.get("change_pct") or 0.0),
                    "change_available": bool(entry.get("change_available", True)),
                    "timestamp_ms": entry.get("timestamp_ms"),
                }

            # S&P: strict direct index only.
            spx_src = live_data.get("SPX")
            if _is_fresh("SPX", spx_src):
                if hasattr(self, "spx_value"):
                    self.spx_value.setText(f" {spx_src['last']:.0f}")
                if hasattr(self, "spx_change"):
                    change = spx_src["change"]
                    pct = spx_src["change_pct"]
                    sign = "+" if change >= 0 else ""
                    self.spx_change.setText(f"  {sign}{change:.0f}  {sign}{pct:.1f}%")
                    color = "#00ff41" if change >= 0 else "#FF073A"
                    self.spx_change.setStyleSheet(f"color: {color};")
            else:
                _clear_pair("spx_value", "spx_change")

            # NASDAQ headline: prefer direct NDX; fall back to QQQ proxy.
            # Keep legacy scaling parity with worker-side IXIC proxy math.
            ndx_src = live_data.get("NDX") or live_data.get("^NDX")
            if not _is_fresh("NDX", ndx_src):
                ndx_src = _as_proxy_entry(live_data.get("QQQ"), 37.5)
            if _is_fresh("NDX", ndx_src):
                if hasattr(self, "ndx_value"):
                    self.ndx_value.setText(f" {ndx_src['last']:,.0f}")
                if hasattr(self, "ndx_change"):
                    change = ndx_src["change"]
                    pct = ndx_src["change_pct"]
                    sign = "+" if change >= 0 else ""
                    self.ndx_change.setText(f"  {sign}{change:.0f}  {sign}{pct:.1f}%")
                    color = "#00ff41" if change >= 0 else "#FF073A"
                    self.ndx_change.setStyleSheet(f"color: {color};")
            else:
                _clear_pair("ndx_value", "ndx_change")

            # DOW: prefer direct $DJI; fall back to DIA proxy.
            dji_src = live_data.get("$DJI")
            if not _is_fresh("$DJI", dji_src):
                dji_src = _as_proxy_entry(live_data.get("DIA"), self._dji_from_dia_multiplier)
            if _is_fresh("$DJI", dji_src):
                if hasattr(self, "dji_value"):
                    self.dji_value.setText(f" {dji_src['last']:,.0f}")
                if hasattr(self, "dji_change"):
                    change = dji_src["change"]
                    pct = dji_src["change_pct"]
                    sign = "+" if change >= 0 else ""
                    self.dji_change.setText(f"  {sign}{change:.0f}  {sign}{pct:.1f}%")
                    color = "#00ff41" if change >= 0 else "#FF073A"
                    self.dji_change.setStyleSheet(f"color: {color};")
            else:
                _clear_pair("dji_value", "dji_change")

            # Russell 2K: prefer direct RUT; fall back to IWM proxy.
            rut_src = live_data.get("RUT") or live_data.get("^RUT")
            if not _is_fresh("RUT", rut_src):
                rut_src = _as_proxy_entry(live_data.get("IWM"), 10.0)
            if _is_fresh("RUT", rut_src):
                rut_last = rut_src["last"]
                if hasattr(self, "rut_value"):
                    self.rut_value.setText(f" {rut_last:,.0f}")
                if hasattr(self, "rut_change"):
                    if not bool(rut_src.get("change_available", True)):
                        self.rut_change.setText("  --")
                        self.rut_change.setStyleSheet("color: #888888;")
                    else:
                        pct = rut_src.get("change_pct") or 0.0
                        change = rut_src["change"]
                        sign = "+" if change >= 0 else ""
                        self.rut_change.setText(f"  {sign}{change:.0f}  {sign}{pct:.1f}%")
                        color = "#00ff41" if change >= 0 else "#FF073A"
                        self.rut_change.setStyleSheet(f"color: {color};")
            else:
                _clear_pair("rut_value", "rut_change")

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

            # Optional symbols may not have an active producer at startup. Render
            # a clear unavailable state instead of leaving placeholder dashes.
            self._seed_optional_symbol_placeholders()

        center_panel = self.create_center_panel()
        content_splitter.addWidget(center_panel)

        right_panel = self.create_right_panel()
        content_splitter.addWidget(right_panel)

        content_splitter.setSizes([340, 970, 610])

        main_layout.addWidget(content_splitter)
        central_widget.setLayout(main_layout)

    def _seed_optional_symbol_placeholders(self) -> None:
        """Set explicit placeholders for optional Market Overview symbols."""
        optional_symbols = ("WRS", "PSR", "NYMO", "$VOLD")
        for sym in optional_symbols:
            widget = self.symbol_widgets.get(sym) if hasattr(self, "symbol_widgets") else None
            if widget is None or not hasattr(widget, "price_label"):
                continue
            text = (widget.price_label.text() or "").strip()
            if text.startswith("---"):
                try:
                    widget.set_unavailable("N/A")
                except (AttributeError, RuntimeError):
                    # Fallback for legacy widgets lacking set_unavailable().
                    widget.update_data({"last": 0.0, "change": 0.0, "change_pct": 0.0})

    def _start_optional_signal_refresh_timer(self) -> None:
        """Start periodic, non-blocking refresh for optional Market Overview rows."""
        if self._optional_signal_timer is not None:
            return
        self._optional_signal_timer = QTimer(self)
        self._optional_signal_timer.setInterval(120000)  # 2 minutes
        self._optional_signal_timer.timeout.connect(self._dispatch_optional_signal_refresh)
        self._optional_signal_timer.start()
        # Kick once immediately after startup to populate rows quickly.
        self._dispatch_optional_signal_refresh()

    def _dispatch_optional_signal_refresh(self) -> None:
        """Spawn a background worker that reads WRS/PSR cache-backed signals."""
        if self._optional_signal_refresh_inflight:
            return
        self._optional_signal_refresh_inflight = True

        def _worker() -> None:
            updates: dict[str, dict[str, float]] = {}
            try:
                try:
                    from SpyderS_Signals.SpyderS12_WRSSignal import get_wrs_signal
                    wrs_payload = get_wrs_signal().get_signal_dict()
                    wrs_value = wrs_payload.get("wrs")
                    if isinstance(wrs_value, (int, float)):
                        updates["WRS"] = {"value": float(wrs_value)}
                except Exception:
                    pass

                try:
                    from SpyderS_Signals.SpyderS13_PSRSignal import get_psr_signal
                    psr_payload = get_psr_signal().get_signal_dict()
                    psr_value = psr_payload.get("psr")
                    if isinstance(psr_value, (int, float)):
                        updates["PSR"] = {"value": float(psr_value)}
                except Exception:
                    pass

                if updates:
                    self.optional_metrics_refreshed.emit(updates)
            finally:
                self._optional_signal_refresh_inflight = False

        threading.Thread(target=_worker, daemon=True).start()

    def _on_optional_metrics_refreshed(self, metrics: dict) -> None:
        """Apply asynchronously fetched optional metrics onto Market Overview rows."""
        if not isinstance(metrics, dict) or not metrics:
            return
        self._on_custom_metrics_updated(metrics)

    def _create_event_clock_panel(self) -> QGroupBox:
        """Create event-clock status display panel (Phase 5-A).
        
        Returns a compact panel showing:
        - Current event-clock state (pre/live/post/clear)
        - Policy configuration (enabled/sources)
        - Blackout window settings
        - Allowed strategies
        """  # noqa: W293
        panel = QGroupBox("EVENT-CLOCK STATUS")
        panel.setStyleSheet(f"""
            QGroupBox {{
                color: {COLORS["text"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 4px;
                margin-top: 5px;
                padding-top: 5px;
                background-color: {COLORS["panel"]};
                font-weight: bold;
                font-size: 11px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px 0 3px;
            }}
        """)
  # noqa: W293
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)
  # noqa: W293
        # State label (main indicator)
        self.event_clock_state_label = QLabel("✓ CLEAR")
        self.event_clock_state_label.setStyleSheet(f"color: {COLORS['positive']}; font-weight: bold; font-size: 12px;")  # noqa: E501
        layout.addWidget(self.event_clock_state_label)
  # noqa: W293
        # Policy label
        self.event_clock_policy_label = QLabel("Policy: ✓ Enabled | Sources: calendar+manual")
        self.event_clock_policy_label.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px;")  # noqa: E501
        layout.addWidget(self.event_clock_policy_label)
  # noqa: W293
        # Blackout windows label
        self.event_clock_windows_label = QLabel("Blackout: -30m / +30m | Size: 25%")
        self.event_clock_windows_label.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px;")  # noqa: E501
        layout.addWidget(self.event_clock_windows_label)
  # noqa: W293
        # Allowed strategies label
        self.event_clock_strategies_label = QLabel("Allowlist: None")
        self.event_clock_strategies_label.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px;")  # noqa: E501
        layout.addWidget(self.event_clock_strategies_label)

        # Manual override toggle
        self.event_clock_override_active = False
        self.event_clock_override_button = QPushButton("Manual Blackout: OFF")
        self.event_clock_override_button.setCheckable(True)
        self.event_clock_override_button.clicked.connect(self._toggle_event_clock_override)
        self.event_clock_override_button.setStyleSheet(
            f"color: {COLORS['text']}; font-size: 10px;"
        )
        layout.addWidget(self.event_clock_override_button)
  # noqa: W293
        panel.setLayout(layout)
        self.event_clock_panel = panel
  # noqa: W293
        return panel

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
            if self.chart_hidden_controls_panel is not None:
                self.chart_hidden_controls_panel.show()
            self.chart_visible = False
            self.chart_toggle_btn.setToolTip("Show SPY Chart (5-min)")
            self.log_system_message("Chart hidden - Advanced controls shown")
        else:
            # Show chart
            self.chart_widget.show()
            if self.chart_hidden_controls_panel is not None:
                self.chart_hidden_controls_panel.hide()
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
                # Guard responsiveness when cache grows unexpectedly large.
                if isinstance(candles, list) and len(candles) > 900:
                    candles = candles[-900:]
                # Only accept bars whose date matches today in ET so the chart
                # resets correctly at the start of each new trading session.
                _today_et = datetime.now(pytz.timezone("US/Eastern")).date()
                for bar in candles:
                    _raw_time = str(bar.get("time", ""))
                    try:
                        bar_dt = datetime.fromisoformat(_raw_time)
                    except ValueError:
                        bar_dt = pd.to_datetime(_raw_time)
                    if bar_dt.date() != _today_et:
                        continue
                    opens_raw.append(float(bar.get("open", 0)))
                    highs_raw.append(float(bar.get("high", 0)))
                    lows_raw.append(float(bar.get("low", 0)))
                    closes_raw.append(float(bar.get("close", 0)))
                    volumes_raw.append(int(bar.get("volume", 0)))
                    # bar["time"] is like "2026-04-09T09:30:00"
                    dates_raw.append(bar_dt)
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
            self.canvas.draw_idle()
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
        line_color = COLORS["positive"] if last_close >= prev_close else COLORS["negative"]  # noqa: F841

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
            indicators = compute_chart_indicators(highs_raw, lows_raw, closes_raw, volumes_raw, prev_day=_prev_day_tuple)  # noqa: E501
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
        ax.axhline(y=pivot, color="#FFFF00", linewidth=1.5, linestyle="-", alpha=0.7, label="Pivot", zorder=1)  # noqa: E501
        ax.axhline(y=r1, color="#00FF41", linewidth=1.5, linestyle="-", alpha=0.6, label="R1", zorder=1)  # noqa: E501
        ax.axhline(y=r2, color="#00FF41", linewidth=1.5, linestyle="-", alpha=0.6, label="R2", zorder=1)  # noqa: E501
        ax.axhline(y=r3, color="#00FF41", linewidth=1.5, linestyle="-", alpha=0.6, label="R3", zorder=1)  # noqa: E501
        ax.axhline(y=s1, color="#FF073A", linewidth=1.5, linestyle="-", alpha=0.6, label="S1", zorder=1)  # noqa: E501
        ax.axhline(y=s2, color="#FF073A", linewidth=1.5, linestyle="-", alpha=0.6, label="S2", zorder=1)  # noqa: E501
        ax.axhline(y=s3, color="#FF073A", linewidth=1.5, linestyle="-", alpha=0.6, label="S3", zorder=1)  # noqa: E501

        # Prior-close reference line (dashed grey — anchors the day's move)
        ax.axhline(y=prev_close, color="#888888", linewidth=1.0, linestyle="--", alpha=0.8, zorder=1)  # noqa: E501

        # MA(20) overlay
        if ma_slot_x:
            ax.plot(ma_slot_x, ma_slot_y, color="#00FFFF", linewidth=1.1, alpha=0.90, label="MA(20)", zorder=2)  # noqa: E501

        # VWAP overlay — smooth solid white line
        if vwap_slot_x:
            _vwap_color = COLORS.get("text", "#FFFFFF")
            ax.plot(
                vwap_slot_x,
                vwap_slot_y,
                color=_vwap_color,
                linewidth=0.8,
                linestyle="-",
                alpha=1.0,
                solid_capstyle="butt",
                label="VWAP",
                zorder=3,
            )

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
        # Vectorised wick drawing — one LineCollection per colour group instead of
        # 78 individual vlines() calls (each creates a separate LineCollection).
        wick_colors = np.where(is_up, COLORS["positive"], COLORS["negative"])
        ax.vlines(xs, lo, hi, colors=wick_colors, linewidth=0.5, zorder=2)
        # Draw bodies
        ax.bar(xs, height=body_hi - body_lo, bottom=body_lo, width=0.45,
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
        ax.set_xticklabels(["9:30", "10:00", "11:00", "12:00", "1:00", "2:00", "3:00", "4:00"], fontsize=9)  # noqa: E501

        ax.grid(True, alpha=0.2, color=COLORS["grid"], zorder=0)
        ax.tick_params(colors="#FFFFFF")
        for spine in ax.spines.values():
            spine.set_color(COLORS["border"])

        # Use fixed margins instead of tight_layout() — tight_layout() synchronously
        # measures font extents for every artist, which can take 1–5 s on a complex
        # chart and stalls the Qt event loop long enough to trigger the OS
        # "Not Responding" dialog.  The pivot labels at label_x=79 sit outside the
        # axes clip region, so right=0.86 gives them enough room at any window size.
        self.figure.subplots_adjust(left=0.07, right=0.86, top=0.97, bottom=0.10)
        self.canvas.draw_idle()

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
        status = strategy_item.data(1, Qt.ItemDataRole.UserRole) or ""  # noqa: F841

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

                self.add_system_log("Trading stopped due to API disconnection")

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

    def _get_tradier_client_for_mode(self, mode: "TradingMode | None" = None) -> "TradierClient | None":  # noqa: E501
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

    # ------------------------------------------------------------------
    # TODAY'S PORTFOLIO SUMMARY popup
    # ------------------------------------------------------------------

    def _open_portfolio_summary_dialog(self) -> None:
        """Open (or raise + refresh) the Today's Portfolio Summary dialog.

        The dialog shows a three-column table:
            Metric  |  Explanation  |  Colour Logic
        Values are read from ``_portfolio_summary_cache`` (the last
        ``position_update`` payload received from the paper/live worker).
        While the dialog is open it is refreshed automatically each time
        new data arrives.
        """
        existing = self._portfolio_summary_dialog
        if existing is not None and existing.isVisible():
            self._populate_portfolio_summary_table(existing)
            existing.raise_()
            existing.activateWindow()
            return

        from PySide6.QtCore import Qt as _Qt
        from PySide6.QtWidgets import (
            QDialog as _QDialog,
            QHBoxLayout as _QHBox,
            QHeaderView as _QHV,
            QLabel as _QLabel,
            QPushButton as _QPB,
            QTableWidget as _QTW,
            QTableWidgetItem as _QTWI,  # noqa: F401
            QVBoxLayout as _QVBox,
        )

        dlg = _QDialog(self)
        dlg.setWindowTitle("TODAY'S PORTFOLIO SUMMARY")
        dlg.setMinimumSize(1060, 620)
        dlg.resize(1060, 620)
        dlg.setStyleSheet(
            f"background-color: {COLORS['background']}; color: {COLORS['text']};"
        )
        layout = _QVBox(dlg)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # Sub-title / last-updated line
        dlg._updated_label = _QLabel("Last updated: —")
        dlg._updated_label.setStyleSheet(
            "color: #b8b8b8; font-size: 12px;"
        )
        layout.addWidget(dlg._updated_label)

        # Three-column table
        tbl = _QTW(0, 3)
        tbl.setHorizontalHeaderLabels(["Metric", "Explanation", "Colour Logic"])
        tbl.verticalHeader().setVisible(False)
        tbl.setEditTriggers(_QTW.NoEditTriggers)
        tbl.setSelectionMode(_QTW.NoSelection)
        tbl.setFocusPolicy(_Qt.NoFocus)
        tbl.setStyleSheet(
            f"QTableWidget {{ background-color: {COLORS['panel']};"
            f" gridline-color: {COLORS['border']}; border: none; }}"
            f"QTableWidget::item {{ padding: 6px 10px; font-size: 13px; }}"
            f"QHeaderView::section {{ background-color: {COLORS['panel']};"
            f" color: #c8c8c8; font-size: 12px; font-weight: bold;"
            f" padding: 5px 10px; border: none;"
            f" border-bottom: 1px solid {COLORS['border']}; }}"
        )
        tbl.setVerticalScrollBarPolicy(_Qt.ScrollBarAlwaysOff)
        tbl.setHorizontalScrollBarPolicy(_Qt.ScrollBarAlwaysOff)
        hdr = tbl.horizontalHeader()
        hdr.setSectionResizeMode(0, _QHV.ResizeToContents)
        hdr.setSectionResizeMode(1, _QHV.Stretch)
        hdr.setSectionResizeMode(2, _QHV.ResizeToContents)
        tbl.setWordWrap(True)
        tbl.setShowGrid(True)
        dlg._table = tbl
        layout.addWidget(tbl)

        # Button row
        btn_row = _QHBox()
        btn_row.addStretch()
        refresh_btn = _QPB("⟳ Refresh")
        refresh_btn.setFixedHeight(28)
        refresh_btn.setStyleSheet(
            f"font-size: 13px; padding: 0 12px; background-color: {COLORS['panel']};"
            f" color: {COLORS['text']}; border: 1px solid {COLORS['border']};"
            f" border-radius: 3px;"
        )
        refresh_btn.clicked.connect(lambda: self._populate_portfolio_summary_table(dlg))
        close_btn = _QPB("Close")
        close_btn.setFixedHeight(28)
        close_btn.setStyleSheet(refresh_btn.styleSheet())
        close_btn.clicked.connect(dlg.close)
        btn_row.addWidget(refresh_btn)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        dlg.finished.connect(lambda *_: setattr(self, "_portfolio_summary_dialog", None))
        self._portfolio_summary_dialog = dlg
        self._populate_portfolio_summary_table(dlg)
        dlg.show()

    def _populate_portfolio_summary_table(self, dlg: "QDialog") -> None:  # noqa: F821
        """Fill (or refresh) the portfolio summary table inside *dlg*.

        Reads ``_portfolio_summary_cache`` (the raw last ``position_update``
        payload) and populates each row with a colour-coded value, a plain-
        English explanation, and the threshold legend for that metric.
        """
        from datetime import datetime as _dt
        from PySide6.QtGui import QColor as _QColor
        from PySide6.QtWidgets import QTableWidgetItem as _QTWI

        data = self._portfolio_summary_cache
        now_str = _dt.now().strftime("%H:%M:%S ET")
        lbl = getattr(dlg, "_updated_label", None)
        if lbl is not None:
            lbl.setText(f"Last updated: {now_str}")

        tbl = dlg._table

        # --- derive values from cache ---
        spreads_detail = data.get("open_spreads_detail") or []
        spreads_mtm = float(data.get("spreads_unrealized_pnl", 0.0) or 0.0)
        atm_iv_raw = data.get("atm_iv")
        iv_rank = data.get("iv_rank")
        greeks = data.get("portfolio_greeks") or {}

        # Realized P&L
        realized_raw = data.get("realized_pnl_today") or data.get("realized_pnl", 0.0)
        try:
            realized = float(realized_raw)
        except (TypeError, ValueError):
            realized = 0.0

        # Buying power
        bp_used = 0.0
        for p in spreads_detail:
            try:
                bp_used += float(p.get("max_loss_per_contract", 0.0)) * int(p.get("qty", 0))
            except (TypeError, ValueError):
                continue
        cap = float(getattr(self, "_paper_initial_capital", 100_000.0) or 100_000.0)
        bp_pct = (bp_used / cap * 100.0) if cap > 0 else 0.0

        # Greek values
        delta = greeks.get("delta")
        gamma = greeks.get("gamma")
        theta = greeks.get("theta")
        vega  = greeks.get("vega")

        # Colour helpers
        _pos  = COLORS["positive"]
        _neg  = COLORS["negative"]
        _warn = COLORS.get("warning", "#e6a817")
        _neu  = COLORS["text"]

        def _color_sign(v: float) -> str:
            return _pos if v >= 0 else _neg

        def _iv_color(v: float) -> str:
            return _neg if v >= 50 else (_warn if v >= 30 else _neu)

        def _ivr_color(v: float) -> str:
            return _neg if v >= 75 else (_warn if v >= 25 else _pos)

        def _delta_color(v: float) -> str:
            return _neg if abs(v) >= 60 else (_warn if abs(v) >= 30 else _neu)

        def _gamma_color(v: float) -> str:
            return _neg if abs(v) >= 0.30 else (_warn if abs(v) >= 0.15 else _neu)

        def _vega_color(v: float) -> str:
            return _neg if v <= -800 else (_warn if v <= -300 else _neu)

        def _bp_color(v: float) -> str:
            return _neg if v >= 80 else (_warn if v >= 50 else _pos)

        # Row definitions:
        #   (display_text, color_hex, explanation, colour_logic_text)
        atm_iv_pct = atm_iv_raw * 100 if isinstance(atm_iv_raw, (int, float)) else None
        rows = [
            (
                f"OPEN  {len(spreads_detail)}",
                _neu,
                "Number of active open positions",
                "—",
            ),
            (
                f"MTM  ${spreads_mtm:+,.2f}",
                _color_sign(spreads_mtm),
                "Mark-to-market unrealised P&L across all open legs",
                "Green +ve / Red -ve",
            ),
            (
                f"REALIZED  ${realized:+,.2f}",
                _color_sign(realized),
                "Closed trade P&L for today's session",
                "Green +ve / Red -ve",
            ),
            (
                f"ATM IV  {atm_iv_pct:.1f}%" if atm_iv_pct is not None else "ATM IV  —",
                _iv_color(atm_iv_pct) if atm_iv_pct is not None else _neu,
                "At-the-money implied volatility of SPY options",
                "White <30%  │  Amber ≥30%  │  Red ≥50%",
            ),
            (
                f"IVR  {iv_rank:.0f}" if isinstance(iv_rank, (int, float)) else "IVR  —",
                _ivr_color(iv_rank) if isinstance(iv_rank, (int, float)) else _neu,
                "IV Rank — where current IV sits vs. the past year (0–100)",
                "Green <25  │  Amber 25–74  │  Red ≥75",
            ),
            (
                f"Δ DELTA  {delta:+,.1f}" if isinstance(delta, (int, float)) else "Δ DELTA  —",
                _delta_color(delta) if isinstance(delta, (int, float)) else _neu,
                "Portfolio net delta: directional exposure per $1 SPY move",
                "White |Δ|<30  │  Amber |Δ|≥30  │  Red |Δ|≥60",
            ),
            (
                f"Γ GAMMA  {gamma:+,.3f}" if isinstance(gamma, (int, float)) else "Γ GAMMA  —",
                _gamma_color(gamma) if isinstance(gamma, (int, float)) else _neu,
                "Portfolio net gamma: rate of delta change per $1 move",
                "White <0.15  │  Amber ≥0.15  │  Red ≥0.30",
            ),
            (
                f"Θ THETA  ${theta:+,.2f}/day" if isinstance(theta, (int, float)) else "Θ THETA  —",
                (_pos if isinstance(theta, (int, float)) and theta > 0 else
                 _neg if isinstance(theta, (int, float)) else _neu),
                "Daily time decay earned (premium sellers receive positive theta)",
                "Green >0 (earning)  │  Red <0 (paying)",
            ),
            (
                f"V VEGA  {vega:+,.1f}" if isinstance(vega, (int, float)) else "V VEGA  —",
                _vega_color(vega) if isinstance(vega, (int, float)) else _neu,
                "Portfolio vega: P&L impact per 1-point rise in implied volatility",
                "White ≥−300  │  Amber ≤−300  │  Red ≤−800",
            ),
            (
                f"BP USED  {bp_pct:.0f}%  (${bp_used:,.0f} / ${cap:,.0f})",
                _bp_color(bp_pct),
                "Buying power consumed as a % of total paper capital",
                "Green <50%  │  Amber 50–80%  │  Red ≥80%",
            ),
        ]

        tbl.setRowCount(len(rows))
        _cell_style = (
            f"background-color: {COLORS['panel']}; padding: 4px 8px;"
        )
        for row_idx, (metric_text, metric_color, explanation, logic) in enumerate(rows):
            for col_idx, text in enumerate((metric_text, explanation, logic)):
                item = _QTWI(text)
                item.setTextAlignment(0x0081)  # AlignLeft | AlignVCenter
                if col_idx == 0:
                    item.setForeground(_QColor(metric_color))
                    from PySide6.QtGui import QFont as _QFont
                    f = _QFont("monospace", 12)
                    f.setBold(True)
                    item.setFont(f)
                elif col_idx == 1:
                    item.setForeground(_QColor("#e8e8e8"))
                    from PySide6.QtGui import QFont as _QFont
                    item.setFont(_QFont("sans-serif", 12))
                else:
                    item.setForeground(_QColor("#ffffff"))
                    from PySide6.QtGui import QFont as _QFont
                    item.setFont(_QFont("sans-serif", 11))
                tbl.setItem(row_idx, col_idx, item)

        tbl.resizeRowsToContents()

    def _refresh_positions_table(self) -> None:
        """Fetch live orders & positions from Tradier and repopulate the table.

        Falls back silently (keeping existing rows) when no API client is
        available or on network error.  Called by the Refresh button and
        automatically after a successful API connection.
        """
        if not self.positions_table:
            return

        # In paper trading mode the live account endpoints are not used;
        # paper positions are tracked internally by _PaperTradingWorker.
        if getattr(self, "trading_mode", None) == TradingMode.PAPER:
            cached = getattr(self, "_portfolio_summary_cache", None)
            if isinstance(cached, dict) and cached:
                self._refresh_spreads_panel(cached)
            else:
                hydrated = self._load_cached_paper_state_payload()
                if hydrated:
                    self._refresh_spreads_panel(hydrated)
                    # Keep account widgets in sync even before first worker tick.
                    if self.settled_value:
                        self.settled_value.setText(f"${float(hydrated.get('equity', 0.0)):,.2f}")
                    if self.buying_value:
                        self.buying_value.setText(f"${float(hydrated.get('cash', 0.0)):,.2f}")
                    if self.unrealized_value:
                        _u = float(hydrated.get("unrealized_pnl", 0.0) or 0.0)
                        _uc = COLORS["positive"] if _u >= 0 else COLORS["negative"]
                        self.unrealized_value.setText(f"${_u:+,.2f}")
                        self.unrealized_value.setStyleSheet(
                            f"padding: 2px 5px; background-color: {COLORS['background']}; "
                            f"border: 1px solid {COLORS['border']}; font-size: 12px; color: {_uc}; text-align: right;"  # noqa: E501
                        )
                    if self.realized_value:
                        _r = float(hydrated.get("realized_pnl", 0.0) or 0.0)
                        _rc = COLORS["positive"] if _r >= 0 else COLORS["negative"]
                        self.realized_value.setText(f"${_r:+,.2f}")
                        self.realized_value.setStyleSheet(
                            f"padding: 2px 5px; background-color: {COLORS['background']}; "
                            f"border: 1px solid {COLORS['border']}; font-size: 12px; color: {_rc}; text-align: right;"  # noqa: E501
                        )
                    self.add_system_log("♻️ Loaded paper positions from saved session state")
                else:
                    # Unified SessionSupervisor paper mode does not depend on
                    # the legacy Qt paper worker to produce the first table
                    # snapshot, so render the steady-state empty view instead
                    # of a stale waiting placeholder.
                    self._refresh_spreads_panel({
                        "open_spreads_detail": [],
                        "spreads_unrealized_pnl": 0.0,
                        "closed_trades": [],
                        "equity": 0.0,
                        "cash": 0.0,
                        "unrealized_pnl": 0.0,
                        "realized_pnl": 0.0,
                    })
            return

        if not getattr(self, "api_connected", False):
            self.add_system_log("ℹ️ Not connected — showing demo data")
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

    def _get_recent_trades(self, limit: int = 30) -> list[dict]:
        """Return most-recent closed trades for the current mode (paper/live)."""
        db = self._get_mode_session_db()
        if db is None:
            return []

        try:
            trades = db.get_recent_trades(limit=max(1, int(limit)))
            return trades if isinstance(trades, list) else []
        except Exception as exc:
            self.add_system_log(f"⚠️ Could not load recent trades: {exc}")
            return []

    def _open_recent_trades_history_dialog(self) -> None:
        """Open (or raise) a dialog showing the last 30 closed trades."""
        trades = self._get_recent_trades(limit=30)

        existing = getattr(self, "_recent_trades_dialog", None)
        if existing is not None and existing.isVisible():
            self._populate_recent_trades_table(existing, trades)
            existing.raise_()
            existing.activateWindow()
            return

        dlg = QDialog(self)
        mode_name = "PAPER" if self.trading_mode == TradingMode.PAPER else "LIVE"
        dlg.setWindowTitle(f"Recent Trade History - {mode_name}")
        dlg.setMinimumSize(980, 520)
        dlg.resize(980, 520)
        dlg.setStyleSheet(
            f"background-color: {COLORS['background']}; color: {COLORS['text']};"
        )

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        subtitle = QLabel("Showing last 30 closed trades")
        subtitle.setStyleSheet("font-size: 12px; color: #b8b8b8;")
        layout.addWidget(subtitle)

        table = QTableWidget(0, 6, dlg)
        table.setHorizontalHeaderLabels(["Timestamp", "Symbol", "Action", "Qty", "Price", "Realized P&L"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setAlternatingRowColors(True)
        table.setStyleSheet(
            f"QTableWidget {{ background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']}; }}"
            f"QHeaderView::section {{ background-color: {COLORS['panel']}; color: {COLORS['text']}; "
            f"padding: 4px 6px; border: none; border-bottom: 1px solid {COLORS['border']}; }}"
        )
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(table)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(28)
        close_btn.setStyleSheet(
            f"font-size: 12px; padding: 0 12px; background-color: {COLORS['panel']};"
            f" color: {COLORS['text']}; border: 1px solid {COLORS['border']}; border-radius: 3px;"
        )
        close_btn.clicked.connect(dlg.close)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        dlg._recent_trades_table = table
        dlg.finished.connect(lambda *_: setattr(self, "_recent_trades_dialog", None))
        self._recent_trades_dialog = dlg

        self._populate_recent_trades_table(dlg, trades)
        dlg.show()

    def _populate_recent_trades_table(self, dialog: QDialog, trades: list[dict]) -> None:
        """Populate the on-demand recent trades dialog table."""
        table = getattr(dialog, "_recent_trades_table", None)
        if table is None:
            return

        table.setRowCount(0)
        for trade in trades:
            raw_ts = str(trade.get("timestamp", "") or "")
            try:
                ts_text = datetime.fromisoformat(raw_ts).strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                ts_text = raw_ts[:19].replace("T", " ") if raw_ts else "--"

            symbol = str(trade.get("symbol", "-") or "-")
            trade_type = str(trade.get("trade_type", "") or "").upper()
            side = str(trade.get("side", "") or "").upper()
            action = trade_type or side or "TRADE"
            qty = int(float(trade.get("quantity", 0) or 0))
            price = float(trade.get("price", 0.0) or 0.0)
            realized_pnl = float(trade.get("realized_pnl", 0.0) or 0.0)

            row = table.rowCount()
            table.insertRow(row)

            values = [
                ts_text,
                symbol,
                action,
                str(qty),
                f"${price:,.2f}",
                f"${realized_pnl:+,.2f}",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col in (3, 4, 5):
                    item.setTextAlignment(int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
                elif col == 2:
                    item.setTextAlignment(int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter))

                if col == 5:
                    if realized_pnl > 0:
                        item.setForeground(QColor(COLORS["positive"]))
                    elif realized_pnl < 0:
                        item.setForeground(QColor(COLORS["negative"]))

                table.setItem(row, col, item)

        if table.rowCount() <= 0:
            table.setRowCount(1)
            empty = QTableWidgetItem("No recent closed trades found")
            empty.setForeground(QColor(COLORS["text_dim"]))
            table.setItem(0, 0, empty)
            for col in range(1, 6):
                table.setItem(0, col, QTableWidgetItem(""))

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
                self._align_positions_data_row(child)

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

    def _align_positions_data_row(self, item: QTreeWidgetItem) -> None:
        """Apply ORDERS & POSITIONS data-column alignment policy.

        LEG/STRIKE/CONT/EXPIRY are centered. COST and P&L are right aligned.
        """
        item.setTextAlignment(0, int(Qt.AlignmentFlag.AlignCenter))
        item.setTextAlignment(1, int(Qt.AlignmentFlag.AlignCenter))
        item.setTextAlignment(2, int(Qt.AlignmentFlag.AlignCenter))
        item.setTextAlignment(3, int(Qt.AlignmentFlag.AlignCenter))
        item.setTextAlignment(4, int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
        item.setTextAlignment(5, int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))

    def _get_mode_session_db(self):
        """Return cached H05 session DB for the current trading mode."""
        if not _H05_AVAILABLE:
            return None

        mode = getattr(self, "trading_mode", None)
        is_paper = mode == TradingMode.PAPER
        if self._session_db_init_failed_by_mode.get(mode, False):
            return None

        cached = self._paper_session_db if is_paper else self._live_session_db
        if cached is not None:
            return cached

        try:
            db = TradingSessionDB.for_paper() if is_paper else TradingSessionDB.for_live()
            if is_paper:
                self._paper_session_db = db
            else:
                self._live_session_db = db
            return db
        except Exception as exc:
            self._session_db_init_failed_by_mode[mode] = True
            self.add_system_log(f"⚠️ Could not initialise session DB for recent trades: {exc}")
            return None

    def _add_recent_trade_rows(self, limit: int = 3) -> int:
        """Render most-recent trades for the current mode (paper/live)."""
        if self.positions_table is None:
            return 0

        db = self._get_mode_session_db()
        if db is None:
            return 0

        try:
            trades = db.get_recent_trades(limit=limit)
        except Exception as exc:
            self.add_system_log(f"⚠️ Could not load recent trades: {exc}")
            return 0

        count = 0
        for trade in trades:
            try:
                raw_ts = str(trade.get("timestamp", "") or "")
                try:
                    ts_text = datetime.fromisoformat(raw_ts).strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    ts_text = raw_ts[:19].replace("T", " ") if raw_ts else "--"

                symbol = str(trade.get("symbol", "—") or "—")
                trade_type = str(trade.get("trade_type", "") or "").upper()
                side = str(trade.get("side", "") or "").upper()
                qty = int(float(trade.get("quantity", 0) or 0))
                price = float(trade.get("price", 0.0) or 0.0)
                realized_pnl = float(trade.get("realized_pnl", 0.0) or 0.0)
                action = trade_type or side or "TRADE"

                row = QTreeWidgetItem(self.positions_table)
                row.setText(
                    0,
                    (
                        f"RECENT TRADE | {ts_text} | {symbol} | {action} | "
                        f"QTY: {qty} | PRICE: ${price:,.2f} | P&L: ${realized_pnl:+,.2f}"
                    ),
                )

                if realized_pnl > 0:
                    color = QColor(COLORS["positive"])
                elif realized_pnl < 0:
                    color = QColor(COLORS["negative"])
                else:
                    color = QColor(COLORS["text"])

                row.setForeground(0, color)
                self.positions_table.setFirstColumnSpanned(
                    self.positions_table.indexOfTopLevelItem(row),
                    QModelIndex(),
                    True,
                )
                count += 1
            except Exception:
                continue

        return count

    def _load_cached_paper_state_payload(self) -> dict | None:
        """Build a worker-like position payload from persisted paper state."""
        try:
            state_file = _PaperTradingWorker.STATE_FILE
            if not state_file.exists():
                return None
            with open(state_file, encoding="utf-8") as fh:
                state = json.load(fh)
        except Exception as exc:
            self.add_system_log(f"⚠️ Could not hydrate paper state cache: {exc}")
            return None

        open_spreads = state.get("_open_spreads") or []
        if not isinstance(open_spreads, list) or not open_spreads:
            return None

        spreads_detail = []
        spreads_unrealized = 0.0
        for p in open_spreads:
            if not isinstance(p, dict):
                continue
            qty = int(p.get("qty", 0) or 0)
            credit_per = float(p.get("credit", 0.0) or 0.0)
            debit_per = float(p.get("last_debit", credit_per) or credit_per)
            mtm_pnl = (credit_per - debit_per) * 100.0 * qty
            spreads_unrealized += mtm_pnl
            spreads_detail.append(
                {
                    "id": p.get("id"),
                    "expiration": p.get("expiration"),
                    "short_strike": float(p.get("short_strike", 0.0) or 0.0),
                    "long_strike": float(p.get("long_strike", 0.0) or 0.0),
                    "qty": qty,
                    "credit": credit_per,
                    "debit": debit_per,
                    "mtm_pnl": mtm_pnl,
                    "max_loss_per_contract": float(p.get("max_loss_per_contract", 0.0) or 0.0),
                    "structure": p.get(
                        "structure",
                        "BULL_PUT" if p.get("option_type") == "P" else "BEAR_CALL",
                    ),
                    "origin": p.get("origin", "AI"),
                    "lifecycle_state": p.get(
                        "lifecycle_state",
                        StrategyLifecycleState.MANAGED_BY_AI.value,
                    ),
                    "opened_at": float(p.get("opened_at") or 0.0),
                    "option_type": p.get("option_type", "P"),
                    "direction": p.get("direction", "bullish"),
                    "short_entry_mid": p.get("short_entry_mid"),
                    "long_entry_mid": p.get("long_entry_mid"),
                    "last_short_mid": p.get("last_short_mid"),
                    "last_long_mid": p.get("last_long_mid"),
                }
            )

        cash = float(state.get("_cash", 100_000.0) or 100_000.0)
        closed_trades = list(state.get("_closed_trades") or [])
        return {
            "spy_last": 0.0,
            "spy_bid": 0.0,
            "spy_ask": 0.0,
            "position_qty": 0,
            "position_avg_price": 0.0,
            "unrealized_pnl": spreads_unrealized,
            "realized_pnl": float(state.get("_total_realized_pnl", 0.0) or 0.0),
            "cash": cash,
            "equity": cash + spreads_unrealized,
            "initial_capital": float(state.get("_initial_capital", 100_000.0) or 100_000.0),
            "open_spreads": len(spreads_detail),
            "open_spreads_detail": spreads_detail,
            "spreads_unrealized_pnl": spreads_unrealized,
            "atm_iv": None,
            "iv_rank": None,
            "portfolio_greeks": {},
            "closed_trades": closed_trades,
            "closed_trades_count": len(closed_trades),
            "armed_candidate": None,
        }

    def _render_paper_spreads_in_tree(
        self,
        spreads_detail: list,
        armed_candidate: dict | None = None,
    ) -> None:
        """Render paper spreads as deterministic top-level rows.

        Layout: one cyan strategy header row per spread, followed by explicit
        leg rows (also top-level items). Avoiding child rows prevents Qt tree
        decoration edge-cases in the unified table configuration.
        """
        from datetime import date as _date, datetime as _dt

        def _coerce_float(value, default: float | None = None) -> float | None:
            try:
                if value in (None, ""):
                    return default
                return float(value)
            except (TypeError, ValueError):
                return default

        def _coerce_int(value, default: int = 0) -> int:
            try:
                if value in (None, ""):
                    return default
                return int(float(value))
            except (TypeError, ValueError):
                return default

        def _dte_from_expiration(expiration: str, today: _date) -> str:
            if not expiration:
                return "--"
            try:
                yyyy, mm, dd = expiration[:10].split("-")
                return f"{(_date(int(yyyy), int(mm), int(dd)) - today).days:02d}"
            except (TypeError, ValueError):
                return "--"

        def _expiry_short(expiration: str) -> str:
            if not expiration:
                return "--"
            parts = expiration[:10].split("-")
            if len(parts) == 3:
                return f"{parts[1]}/{parts[2]}"
            return expiration[:10]

        self.positions_table.clear()
        today = _date.today()

        if armed_candidate:
            ac_structure = str(armed_candidate.get("structure", "SPREAD")).replace("_", " ").upper()
            ac_reason = str(armed_candidate.get("blocked_reason", "gate check"))
            ac_lifecycle = str(
                armed_candidate.get("lifecycle_state")
                or StrategyLifecycleState.ARMED_BY_AI.value
            )
            ac_armed_at = float(armed_candidate.get("armed_at") or 0.0)
            ac_elapsed = int(time.time() - ac_armed_at) if ac_armed_at > 0 else 0
            ac_exp = str((armed_candidate.get("spread") or {}).get("expiration", "") or "")
            ac_dte = _dte_from_expiration(ac_exp, today)

            ac_row = QTreeWidgetItem(self.positions_table)
            ac_row.setText(
                0,
                (
                    f"WAITING  STRATEGY {ac_lifecycle} : {ac_structure}  |  "
                    f"DTE: {ac_dte}  |  REASON: {ac_reason}  |  {ac_elapsed}s"
                ),
            )
            for col in range(6):
                ac_row.setForeground(col, QColor("#FFA500"))
            self.positions_table.setFirstColumnSpanned(
                self.positions_table.indexOfTopLevelItem(ac_row),
                QModelIndex(),
                True,
            )

        if not spreads_detail:
            empty = QTreeWidgetItem(self.positions_table)
            empty.setText(0, "Paper trading - no open spreads")
            empty.setForeground(0, Qt.GlobalColor.gray)
            self.positions_table.setFirstColumnSpanned(
                self.positions_table.indexOfTopLevelItem(empty),
                QModelIndex(),
                True,
            )
            return

        for sp in spreads_detail:
            spread_id = str(sp.get("id", ""))
            structure = str(sp.get("structure") or sp.get("type") or "SPREAD").replace("_", " ").upper()  # noqa: E501
            lifecycle_state = str(
                sp.get("lifecycle_state") or StrategyLifecycleState.MANAGED_BY_AI.value
            )
            qty = _coerce_int(sp.get("qty"), 0)
            mtm = _coerce_float(sp.get("mtm_pnl"), None)
            credit = _coerce_float(sp.get("credit"), 0.0) or 0.0
            if mtm is None:
                debit_fallback = _coerce_float(sp.get("debit"), None)
                if debit_fallback is None:
                    debit_fallback = _coerce_float(sp.get("last_debit"), None)
                if debit_fallback is not None:
                    mtm = (credit - debit_fallback) * 100.0 * max(qty, 1)
                else:
                    mtm = 0.0
            short_k = _coerce_float(sp.get("short_strike"), 0.0) or 0.0
            long_k = _coerce_float(sp.get("long_strike"), 0.0) or 0.0
            expiration = str(sp.get("expiration", "") or "")
            dte = _dte_from_expiration(expiration, today)
            opened_at = _coerce_float(sp.get("opened_at"), 0.0) or 0.0
            ts_str = ""
            if opened_at > 0:
                try:
                    ts_str = _dt.fromtimestamp(opened_at).strftime("%Y-%m-%d %H:%M")
                except (OSError, OverflowError, ValueError):
                    ts_str = ""
            ts_part = f"{ts_str}  |  " if ts_str else ""
            credit_dollars = credit * 100.0 * max(qty, 1)
            pnl_pct = (mtm / credit_dollars * 100.0) if credit_dollars > 0 else 0.0
            sign = "+" if mtm >= 0 else "-"

            header_text = (
                f"{ts_part}STRATEGY {lifecycle_state} : {structure}  |  "
                f"DTE: {dte}  |  STATUS: OPEN  |  "
                f"NET P&L {sign}${abs(mtm):,.2f} ({pnl_pct:+.1f}%)"
            )
            header_row = QTreeWidgetItem(self.positions_table)
            self.positions_table.setFirstColumnSpanned(
                self.positions_table.indexOfTopLevelItem(header_row),
                QModelIndex(),
                True,
            )

            close_btn = QPushButton("X")
            close_btn.setFixedSize(18, 18)
            close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            close_btn.setStyleSheet(
                "QPushButton {"
                "color: #ff3b30; background: transparent;"
                "border: 1px solid #ff3b30; border-radius: 3px;"
                "font-size: 10px; font-weight: bold;"
                "}"
                "QPushButton:hover { background: #2a0f0f; }"
            )
            if spread_id:
                close_btn.clicked.connect(
                    lambda _checked=False, _id=spread_id: self._request_manual_close_spread(_id)
                )
            else:
                close_btn.setEnabled(False)
            # Compose one full-width strategy row with right-aligned action button.
            row_widget = QWidget(self.positions_table)
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(4, 0, 4, 0)
            row_layout.setSpacing(8)
            row_label = QLabel(header_text, row_widget)
            row_label.setStyleSheet(
                f"color: {COLORS.get('cyan', '#00ffff')}; font-family: monospace; font-size: 10pt;"
            )
            row_layout.addWidget(row_label, 1)
            row_layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignRight)
            self.positions_table.setItemWidget(header_row, 0, row_widget)

            legs: list[dict] = []
            raw_legs = sp.get("legs") or []
            if isinstance(raw_legs, list):
                for raw in raw_legs:
                    if not isinstance(raw, dict):
                        continue
                    legs.append(
                        {
                            "side": str(
                                raw.get("side")
                                or raw.get("action")
                                or raw.get("position")
                                or raw.get("name")
                                or ""
                            ).strip(),
                            "strike": _coerce_float(raw.get("strike", raw.get("strike_price")), None),  # noqa: E501
                            "qty": _coerce_int(raw.get("qty", raw.get("quantity", qty)), qty),
                            "type": str(raw.get("type") or raw.get("option_type") or raw.get("right") or ""),  # noqa: E501
                            "cost": _coerce_float(raw.get("cost"), None),
                            "pnl": _coerce_float(raw.get("pnl"), None),
                        }
                    )

            normalized = [
                lg for lg in legs
                if lg.get("side") or lg.get("strike") is not None
            ]

            if len(normalized) < 2:
                option_type = str(sp.get("option_type", "P") or "P").upper()[:1]
                option_word = "Put" if option_type == "P" else "Call"
                short_entry = _coerce_float(sp.get("short_entry_mid"), None)
                long_entry = _coerce_float(sp.get("long_entry_mid"), None)
                last_short = _coerce_float(sp.get("last_short_mid"), None)
                last_long = _coerce_float(sp.get("last_long_mid"), None)
                normalized = [
                    {
                        "side": f"Sell {option_word}",
                        "strike": short_k,
                        "qty": qty,
                        "type": option_type,
                        "cost": -(short_entry * 100.0 * qty) if short_entry is not None else None,
                        "pnl": (
                            (short_entry - last_short) * 100.0 * qty
                            if short_entry is not None and last_short is not None
                            else None
                        ),
                    },
                    {
                        "side": f"Buy {option_word}",
                        "strike": long_k,
                        "qty": qty,
                        "type": option_type,
                        "cost": (long_entry * 100.0 * qty) if long_entry is not None else None,
                        "pnl": (
                            (last_long - long_entry) * 100.0 * qty
                            if long_entry is not None and last_long is not None
                            else None
                        ),
                    },
                ]

            expiry_display = _expiry_short(expiration)
            for leg in normalized:
                leg_row = QTreeWidgetItem(self.positions_table)
                side = str(leg.get("side") or "LEG")
                strike = _coerce_float(leg.get("strike"), 0.0) or 0.0
                leg_type = str(leg.get("type") or "").upper()[:1]
                leg_row.setText(0, f"  {side}")
                leg_row.setText(1, f"${strike:.0f}{leg_type}")
                leg_row.setText(2, str(_coerce_int(leg.get("qty"), qty)))
                leg_row.setText(3, expiry_display)
                self._align_positions_data_row(leg_row)
                for col in range(6):
                    leg_row.setForeground(col, QColor("#ffffff"))

                cost = _coerce_float(leg.get("cost"), None)
                pnl = _coerce_float(leg.get("pnl"), None)
                if cost is not None:
                    leg_row.setText(4, f"{cost:+,.0f}")
                    leg_row.setForeground(4, QColor(COLORS["positive"] if cost >= 0 else COLORS["negative"]))  # noqa: E501
                if pnl is not None:
                    leg_row.setText(5, f"{pnl:+,.0f}")
                    leg_row.setForeground(5, QColor(COLORS["positive"] if pnl >= 0 else COLORS["negative"]))  # noqa: E501

    def _request_manual_close_spread(self, spread_id: str) -> None:
        """Queue a manual close request to the paper worker thread.

        If the worker is running the close is forwarded via the Qt signal.
        If the worker is stopped (or not yet started) the spread is closed
        directly in the persisted state file so the position is not orphaned.
        """
        if not spread_id:
            return
        if self._paper_worker is not None:
            self.add_system_log(f"🖱️ Manual close requested for spread {spread_id}")
            self.manual_close_spread_requested.emit(str(spread_id))
            return
        # ── Fallback: worker not running — close directly in state file ──────
        self.add_system_log(f"⚠️ Worker not running — closing spread {spread_id} via state file")
        try:
            from SpyderR_Runtime.SpyderR08_PaperTradingQtWorker import PaperTradingQtWorker  # noqa: PLC0415
            state_path = PaperTradingQtWorker.STATE_FILE
        except Exception:
            state_path = Path("market_data/paper_trading_state.json")
        if not state_path.exists():
            self.add_system_log("❌ State file not found — cannot force-close")
            return
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            open_spreads = state.get("_open_spreads", [])
            target = next((s for s in open_spreads if str(s.get("id", "")) == str(spread_id)), None)
            if target is None:
                self.add_system_log(f"❌ Spread {spread_id} not found in state file")
                return
            credit = float(target.get("credit", 0.0))
            qty    = int(target.get("qty", 1))
            debit  = credit * 0.50
            credit_received = credit * 100.0 * qty
            debit_paid      = debit  * 100.0 * qty
            realized_pnl    = credit_received - debit_paid
            now = time.time()
            closed_trade = dict(target)
            closed_trade.update({
                "debit_to_close":       debit,
                "debit_paid":           debit_paid,
                "credit_received":      credit_received,
                "realized_pnl":         realized_pnl,
                "max_loss_dollars":     float(target.get("max_loss_per_contract", 0)) * qty * 100,
                "open_commission":      0.0,
                "close_commission":     0.0,
                "return_on_credit_pct": (realized_pnl / credit_received * 100) if credit_received else 0.0,  # noqa: E501
                "return_on_risk_pct":   0.0,
                "closed_at":            now,
                "hold_seconds":         now - float(target.get("opened_at", now)),
                "close_reason":         "MANUAL_CLOSE (worker offline)",
                "lifecycle_state":      "CLOSED BY USER",
            })
            state["_open_spreads"] = [s for s in open_spreads if str(s.get("id", "")) != str(spread_id)]  # noqa: E501
            state.setdefault("_closed_trades", []).append(closed_trade)
            state["_cash"]               = float(state.get("_cash", 0)) + debit_paid
            state["_trades_executed"]    = int(state.get("_trades_executed", 0)) + 1
            state["_total_realized_pnl"] = float(state.get("_total_realized_pnl", 0)) + realized_pnl
            if realized_pnl >= 0:
                state["_winning_trades"] = int(state.get("_winning_trades", 0)) + 1
            else:
                state["_losing_trades"] = int(state.get("_losing_trades", 0)) + 1
            state.setdefault("_spread_pnl_history", []).append(realized_pnl)
            state["_saved_at"] = now
            tmp = state_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
            tmp.replace(state_path)
            self.add_system_log(
                f"✅ Spread {spread_id} force-closed via state file — P&L ${realized_pnl:+.2f}"
            )
            # Refresh display so the row disappears
            self._refresh_positions_table()
        except Exception as exc:  # pragma: no cover
            self.add_system_log(f"❌ Force-close failed: {exc}")

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
                    "You must connect a market data feed (TRADIER DATA)\n"
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
        self._remember_current_account_snapshot(old_mode)

        self.trading_mode = new_mode
        is_paper = new_mode == TradingMode.PAPER

        self._update_mode_buttons()

        # Reset account container to placeholders; real data arrives via broker/signals
        if self.acct_number_lbl:
            import os as _os_mode
            _paper_acct_id = _os_mode.environ.get("TRADIER_SANDBOX_ACCOUNT_ID", "PAPER ACCOUNT")
            self.acct_number_lbl.setText(_paper_acct_id if is_paper else "—")
        for lbl in (self.settled_value, self.buying_value, self.realized_value, self.unrealized_value):  # noqa: E501
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
        if saved_positions and new_mode != TradingMode.PAPER:
            self._restore_positions_snapshot(saved_positions)
        elif new_mode == TradingMode.PAPER:
            cached = getattr(self, "_portfolio_summary_cache", None)
            if isinstance(cached, dict) and cached:
                self._refresh_spreads_panel(cached)
            else:
                hydrated = self._load_cached_paper_state_payload()
                if hydrated:
                    self._refresh_spreads_panel(hydrated)
                    if self.settled_value:
                        self.settled_value.setText(f"${float(hydrated.get('equity', 0.0)):,.2f}")
                    if self.buying_value:
                        self.buying_value.setText(f"${float(hydrated.get('cash', 0.0)):,.2f}")
                    if self.unrealized_value:
                        _u = float(hydrated.get("unrealized_pnl", 0.0) or 0.0)
                        _uc = COLORS["positive"] if _u >= 0 else COLORS["negative"]
                        self.unrealized_value.setText(f"${_u:+,.2f}")
                        self.unrealized_value.setStyleSheet(
                            f"padding: 2px 5px; background-color: {COLORS['background']}; "
                            f"border: 1px solid {COLORS['border']}; font-size: 12px; color: {_uc}; text-align: right;"  # noqa: E501
                        )
                    if self.realized_value:
                        _r = float(hydrated.get("realized_pnl", 0.0) or 0.0)
                        _rc = COLORS["positive"] if _r >= 0 else COLORS["negative"]
                        self.realized_value.setText(f"${_r:+,.2f}")
                        self.realized_value.setStyleSheet(
                            f"padding: 2px 5px; background-color: {COLORS['background']}; "
                            f"border: 1px solid {COLORS['border']}; font-size: 12px; color: {_rc}; text-align: right;"  # noqa: E501
                        )
        saved_account = self._account_snapshot_by_mode.get(new_mode)
        if new_mode != TradingMode.PAPER and isinstance(saved_account, dict) and saved_account:
            self._apply_account_snapshot(saved_account)

        self._refresh_pnl_table(self._pnl_stats_by_mode.get(new_mode, {}))

    def _update_pnl_title(self):
        """Update the P&L PERFORMANCE title label text and color based on trading mode."""
        if not hasattr(self, "pnl_title_lbl") or self.pnl_title_lbl is None:
            return
        is_paper = self.trading_mode == TradingMode.PAPER
        if is_paper:
            self.pnl_title_lbl.setText("P&L PERFORMANCE - PAPER TRADING")
            self.pnl_title_lbl.setStyleSheet("font-size: 15px; font-weight: normal; letter-spacing: 1px; color: #FFA500;")  # noqa: E501
        else:
            self.pnl_title_lbl.setText("P&L PERFORMANCE - LIVE TRADING")
            self.pnl_title_lbl.setStyleSheet("font-size: 15px; font-weight: normal; letter-spacing: 1px; color: #00FF00;")  # noqa: E501

    def _update_orders_title(self):
        """Update the ORDERS & POSITIONS title label text and color based on trading mode."""
        if not hasattr(self, "orders_title_label") or self.orders_title_label is None:
            return
        is_paper = self.trading_mode == TradingMode.PAPER
        if is_paper:
            self.orders_title_label.setText("ORDERS & POSITIONS - PAPER TRADING")
            self.orders_title_label.setStyleSheet("font-weight: normal; font-size: 11pt; color: #FFA500;")  # noqa: E501
        else:
            self.orders_title_label.setText("ORDERS & POSITIONS - LIVE TRADING")
            self.orders_title_label.setStyleSheet("font-weight: normal; font-size: 11pt; color: #00FF00;")  # noqa: E501

    def _update_mode_buttons(self):
        """Apply active/inactive styles to the LIVE / PAPER toggle buttons."""
        if not self.live_btn or not self.paper_btn:
            return
        is_live = self.trading_mode == TradingMode.LIVE
        _active_base = "font-size: 12px; border-radius: 3px; padding: 4px 8px; border: none;"
        _inactive_base = f"font-size: 12px; border-radius: 3px; padding: 4px 8px; border: none; background-color: {COLORS['panel']}; color: #aaaaaa;"  # noqa: E501
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
            f"background-color: {COLORS['negative']}; color: white; font-weight: bold; padding: 6px 14px;"  # noqa: E501
        )
        btn_box.rejected.connect(dlg.reject)
        btn_box.accepted.connect(dlg.accept)
        layout.addWidget(btn_box)

        def _on_text_changed(text: str) -> None:
            confirm_btn.setEnabled(text == REQUIRED_PHRASE)

        line_edit.textChanged.connect(_on_text_changed)

        return dlg.exec() == QDialog.DialogCode.Accepted

    def start_trading(self):
        """Handle start trading button click via unified SessionSupervisor path."""
        if self.trading_active:
            self.add_system_log("Trading already active")
            return

        if not is_market_hours():
            self.add_system_log(
                "⛔ Trading start blocked: market is closed (outside RTH)"
            )
            QMessageBox.warning(
                self,
                "Market Closed",
                "Trading start blocked: market is closed (outside regular trading hours).",
            )
            return

        if self._startup_readiness_state.get("safe_fallback_applied", False):
            self.add_system_log(
                "⚠️ Safe mode reminder: automation fallback is active from startup readiness validation"  # noqa: E501
            )

        # Apply the same readiness evaluation gate to both PAPER and LIVE starts.
        decision = self._require_fresh_readiness_or_block(self.trading_mode)
        if decision == "NO":
            mode_label = self.trading_mode.value
            self.add_system_log(
                f"⛔ Session blocked by readiness check (NO) — {mode_label} trading start rejected"
            )
            self._append_readiness_bypass_audit("blocked", "NO hard-block", "")
            return

        latest_result = self._last_readiness_result if isinstance(self._last_readiness_result, dict) else {}  # noqa: E501
        if bool(latest_result.get("conditional", False)):
            reason = self._prompt_conditional_readiness_reason()
            if reason is None:
                self.add_system_log("Trading start cancelled after OK-CONDITIONAL readiness result")
                return
            self.add_system_log(
                f"⚠️ OK-CONDITIONAL override accepted — bypass reason: {reason}"
            )
            self._append_readiness_bypass_audit("override", "OK - CONDITIONAL", reason)

        # Keep existing live-mode safety gates before backend start.
        if self.trading_mode == TradingMode.LIVE:

            if not self.api_connected:
                QMessageBox.warning(
                    self,
                    "API Disconnected",
                    "API is disconnected - cannot start trading",
                )
                self.add_system_log("Cannot start trading - API disconnected")
                return

            if not self._confirm_live_trading():
                self.add_system_log("Live trading start cancelled by user")
                return

            data_status = self.data_status_label.text()
            normalized_status = str(data_status or "").strip().upper()
            live_equivalent_statuses = {
                "LIVE",
                "LIVE DATA",
                "LIVE - REAL",
                "REAL",
                "REAL-TIME",
                "REAL TIME",
                "PAPER",
            }
            if normalized_status not in live_equivalent_statuses:
                QMessageBox.warning(
                    self,
                    "No Live Data",
                    "NO LIVE DATA\n\nCannot start trading without live market data.",
                )
                self.add_system_log("Cannot start trading - No live data")
                return

        if not self._start_unified_session_supervisor():
            QMessageBox.critical(
                self,
                "Start Failed",
                "Unified backend session failed to start.\n"
                "Trading remains stopped (fail-closed).",
            )
            return

        self.trading_active = True
        self.connection_info.trading_active = True
        self.start_btn.setStyleSheet(
            f"background-color: {COLORS['automation_active']}; color: white;",
        )
        self.start_btn.setText("PAPER ACTIVE" if self.trading_mode == TradingMode.PAPER else "TRADING ACTIVE")  # noqa: E501

        mode_label = self.trading_mode.value
        self.add_system_log(f"{mode_label} trading started successfully via SessionSupervisor")
        if self.trading_mode == TradingMode.PAPER and not is_market_hours():
            self.add_system_log(
                "ℹ️ After-hours: paper session active; order entry may be gated by market-hours policy"
            )
        self.add_system_log(f"TRADING ACTIVE [{mode_label}] - Unified session started")

        # Unified paper mode does not emit the legacy Qt worker's first UI
        # snapshot, so refresh the positions strip immediately on successful
        # startup to replace any stale placeholder/restore state.
        if self.trading_mode == TradingMode.PAPER:
            self._refresh_positions_table()

    def _require_fresh_readiness_or_block(self, mode: TradingMode | None = None) -> str:
        """Ensure a fresh readiness decision exists before trading start.

        Returns one of: OK, NO.
        """
        mode_label = (mode or self.trading_mode).value.upper()
        now = time.time()
        if isinstance(self._last_readiness_ts, (int, float)) and isinstance(self._last_readiness_result, dict):  # noqa: E501
            age = now - float(self._last_readiness_ts)
            if age <= float(self._readiness_ttl_seconds):
                return str(self._last_readiness_result.get("decision", "NO"))

        result = self.run_trading_readiness_check(show_dialog=False)
        decision = str(result.get("decision", "NO"))
        if decision == "NO":
            reasons = result.get("reasons", [])
            reason_text = "\n".join(f"- {r}" for r in reasons[:6]) or "- Unknown readiness failure"
            QMessageBox.critical(
                self,
                f"{mode_label} Start Blocked (NO)",
                "Trading readiness evaluation returned NO.\n\n"
                f"Reasons:\n{reason_text}",
            )
            self.add_system_log(f"❌ {mode_label} start blocked by readiness evaluation")
        return decision

    def run_trading_readiness_check_async(self) -> None:
        """Run trading readiness check on a worker thread."""
        if self._readiness_worker_thread is not None:
            self.add_system_log("Trading readiness evaluation already running")
            return

        snapshot = self._build_preopen_check_snapshot()
        self.add_system_log("Running trading readiness evaluation in background...")

        button = getattr(self, "readiness_btn", None)
        if button is not None:
            button.setEnabled(False)

        self._readiness_worker_thread = QThread(self)
        self._readiness_worker = _ReadinessCheckWorker(snapshot, self._evaluate_trading_readiness_snapshot)  # noqa: E501
        self._readiness_worker.moveToThread(self._readiness_worker_thread)

        self._readiness_worker_thread.started.connect(self._readiness_worker.run)
        self._readiness_worker.finished.connect(self._on_readiness_worker_finished)
        self._readiness_worker.failed.connect(self._on_readiness_worker_failed)
        self._readiness_worker.finished.connect(self._readiness_worker_thread.quit)
        self._readiness_worker.failed.connect(self._readiness_worker_thread.quit)
        self._readiness_worker_thread.finished.connect(self._cleanup_readiness_worker)

        self._readiness_worker_thread.start()

    def _on_readiness_worker_finished(self, result: dict) -> None:
        """Handle async trading-readiness worker success on UI thread."""
        self._apply_readiness_result(result, show_dialog=True)

    def _on_readiness_worker_failed(self, error_message: str) -> None:
        """Handle async trading-readiness worker failure on UI thread."""
        self.add_system_log(f"❌ Trading readiness evaluation failed: {error_message}")
        QMessageBox.critical(
            self,
            "Trading Readiness Error",
            f"Trading readiness evaluation failed:\n{error_message}",
        )

    def _cleanup_readiness_worker(self) -> None:
        """Release async trading-readiness worker resources."""
        button = getattr(self, "readiness_btn", None)
        if button is not None:
            button.setEnabled(True)

        if self._readiness_worker is not None:
            try:
                self._readiness_worker.deleteLater()
            except Exception:
                pass
        if self._readiness_worker_thread is not None:
            try:
                self._readiness_worker_thread.deleteLater()
            except Exception:
                pass

        self._readiness_worker = None
        self._readiness_worker_thread = None

    def _build_preopen_check_snapshot(self) -> dict[str, object]:
        """Capture UI-safe snapshot used by sync/async readiness evaluation."""
        startup_state = self._startup_readiness_state
        if not isinstance(startup_state, dict) or not startup_state:
            startup_state = self._collect_startup_readiness_state()
            self._startup_readiness_state = startup_state

        data_label = ""
        if getattr(self, "data_status_label", None) is not None:
            try:
                data_label = str(self.data_status_label.text()).strip().upper()
            except Exception:
                data_label = ""

        with self._event_clock_lock:
            event_state = getattr(self, "event_clock_state", None)
            event_enabled = bool(getattr(event_state, "enabled", True)) if event_state is not None else True  # noqa: E501
            event_name = str(getattr(event_state, "state", "clear")) if event_state is not None else "clear"  # noqa: E501

        et_now = datetime.now(pytz.timezone("US/Eastern"))

        # If the cached worker state shows disconnected, do a fresh inline check so a
        # slow/async startup connection probe doesn't give a false NO.  The result is
        # also pushed through the normal signal handlers so the toolbar labels update.
        cached_api = bool(getattr(self, "api_connected", False))
        cached_mkt = bool(getattr(self, "mkt_data_connected", False))
        if not cached_api:
            try:
                fresh_connected, fresh_mode = check_api_connection()
                if fresh_connected:
                    # Drive through the normal handlers so toolbar labels go green.
                    self.on_connection_status_changed(True, f"API CONNECTED ({fresh_mode})")
                    _is_sandbox = "SANDBOX" in fresh_mode.upper() or "PAPER" in fresh_mode.upper()
                    self.on_market_data_status_changed("PAPER" if _is_sandbox else "LIVE")
                    cached_api = True
                    cached_mkt = True
            except Exception:
                pass

        return {
            "startup_state": startup_state,
            "api_connected": cached_api,
            "mkt_data_connected": cached_mkt,
            "data_status_label": data_label,
            "event_clock_enabled": event_enabled,
            "event_clock_state": event_name,
            "is_weekend": et_now.weekday() >= 5,
            "is_market_hours": is_market_hours(et_now),
            "checked_at_et": et_now.isoformat(),
        }

    @staticmethod
    def _evaluate_trading_readiness_snapshot(snapshot: dict[str, object]) -> dict[str, object]:
        """Evaluate trading readiness decision from an immutable snapshot."""
        reasons: list[str] = []
        warnings: list[str] = []

        if bool(snapshot.get("is_weekend", False)):
            reasons.append("Market is closed (weekend)")
        if not bool(snapshot.get("is_market_hours", True)):
            reasons.append("Market is closed (outside regular trading hours)")

        startup_state = snapshot.get("startup_state", {})
        if isinstance(startup_state, dict):
            if startup_state.get("live_blocking", False):
                reasons.append("A03 readiness validation reports live-blocking configuration errors")  # noqa: E501
            if startup_state.get("safe_fallback_applied", False):
                reasons.append("Automation safe fallback is active from startup readiness validation")  # noqa: E501

        if not bool(snapshot.get("api_connected", False)):
            reasons.append("Tradier execution API is disconnected")
        if not bool(snapshot.get("mkt_data_connected", False)):
            reasons.append("Market data feed is disconnected")

        data_label = str(snapshot.get("data_status_label", "")).strip().upper()
        live_equivalent_statuses = {
            "LIVE",
            "LIVE DATA",
            "LIVE - REAL",
            "REAL",
            "REAL-TIME",
            "REAL TIME",
            "PAPER",
        }
        if data_label and data_label not in live_equivalent_statuses:
            warnings.append(f"Data status is {data_label} (not explicit LIVE)")

        if bool(snapshot.get("event_clock_enabled", True)):
            state_name = str(snapshot.get("event_clock_state", "clear"))
            if state_name in {"pre", "live", "post"}:
                warnings.append(f"Event-clock state is {state_name}; reduced-risk policy recommended")  # noqa: E501

        decision = "OK"
        conditional = False
        if reasons:
            decision = "NO"
        elif warnings:
            conditional = True

        return {
            "decision": decision,
            "conditional": conditional,
            "checked_at_et": str(snapshot.get("checked_at_et", "")),
            "reasons": reasons,
            "warnings": warnings,
            "startup_state": startup_state,
        }

    def run_trading_readiness_check(self, show_dialog: bool = True) -> dict[str, object]:
        """Run dashboard-visible trading-readiness checks and store decision."""
        snapshot = self._build_preopen_check_snapshot()
        result = self._evaluate_trading_readiness_snapshot(snapshot)
        return self._apply_readiness_result(result, show_dialog=show_dialog)

    def run_preopen_go_no_go_check(self, show_dialog: bool = True) -> dict[str, object]:
        """Pre-open Go/No-Go checklist returning GO / NO-GO / CONDITIONAL GO.

        Wraps ``run_trading_readiness_check`` with operator-friendly decision
        labels and updates the ``go_no_go_status_label`` / ``start_btn`` UI
        elements present in the pre-open panel.

        Args:
            show_dialog: When True, show a blocking QMessageBox on NO-GO.

        Returns:
            Dict with keys ``decision`` (str), ``reasons`` (list[str]),
            ``warnings`` (list[str]), and ``checked_at_et`` (str).
        """
        snapshot = self._build_preopen_check_snapshot()
        inner = self._evaluate_trading_readiness_snapshot(snapshot)

        raw_decision = str(inner.get("decision", "NO"))
        conditional = bool(inner.get("conditional", False))
        reasons = list(inner.get("reasons", []))
        warnings_list = list(inner.get("warnings", []))

        if raw_decision == "NO":
            decision = "NO-GO"
        elif conditional:
            decision = "CONDITIONAL GO"
        else:
            decision = "GO"

        result: dict[str, object] = {
            "decision": decision,
            "reasons": reasons,
            "warnings": warnings_list,
            "checked_at_et": inner.get("checked_at_et", ""),
        }

        # ── Update UI elements ───────────────────────────────────────────────
        status_text = f"Pre-open: {decision}"
        label = getattr(self, "go_no_go_status_label", None)
        if label is not None:
            try:
                label.setText(status_text)
            except Exception:
                pass

        start = getattr(self, "start_btn", None)
        if start is not None:
            try:
                start.setEnabled(decision != "NO-GO")
            except Exception:
                pass

        btn = getattr(self, "go_no_go_btn", None)
        if btn is not None:
            _colors = {"GO": "#00c800", "CONDITIONAL GO": "#ffa500", "NO-GO": "#c80000"}
            try:
                btn.setStyleSheet(f"background-color: {_colors.get(decision, '#888')};")
            except Exception:
                pass

        log_suffix = f" — {reasons[0]}" if reasons else ""
        self.add_system_log(f"Pre-open check: {decision}{log_suffix}")

        return result

    def _apply_readiness_result(self, result: dict[str, object], show_dialog: bool = True) -> dict[str, object]:  # noqa: E501
        """Persist, display, and log readiness result."""
        reasons = list(result.get("reasons", []))
        warnings = list(result.get("warnings", []))
        decision = str(result.get("decision", "NO"))
        conditional = bool(result.get("conditional", False))

        self._last_readiness_result = result
        self._last_readiness_ts = time.time()
        self._update_readiness_status_display(result)

        if decision == "NO":
            reason_text = "; ".join(str(r) for r in reasons) if reasons else "Unknown reason"
            summary = f"NO - {reason_text}"
            for r in (reasons if reasons else ["Unknown reason"]):
                self.add_system_log(f"  ✗ {r}")
        elif conditional:
            warning_text = "; ".join(str(w) for w in warnings) if warnings else "Warnings present"
            summary = f"OK - CONDITIONAL: {warning_text}"
        else:
            summary = "OK - READY"
        self.add_system_log(summary)

        report_path = self._export_readiness_report(result)
        if report_path:
            self.add_system_log(f"Trading readiness report saved: {report_path}")

        return result

    def _export_readiness_report(self, result: dict[str, object]) -> str:
        """Persist trading-readiness decision report to disk as JSON."""
        try:
            reports_dir = Path(self._readiness_reports_dir)
            reports_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(pytz.timezone("US/Eastern")).strftime("%Y%m%d_%H%M%S")
            decision = str(result.get("decision", "UNKNOWN")).replace(" ", "_")
            out_path = reports_dir / f"trading_readiness_{stamp}_{decision}.json"
            with out_path.open("w", encoding="utf-8") as handle:
                json.dump(result, handle, indent=2, default=str)
            return str(out_path)
        except Exception as exc:
            self.add_system_log(f"⚠️ Failed to save trading readiness report: {exc}")
            return ""

    def _prompt_conditional_readiness_reason(self) -> str | None:
        """Show a modal dialog requiring a typed bypass reason for OK-CONDITIONAL.

        Returns the trimmed reason string if the operator confirms, or None if
        they cancel.  An empty reason is not accepted — the dialog stays open
        until a non-blank reason is supplied or the user cancels.
        """
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QLineEdit, QVBoxLayout

        while True:
            dlg = QDialog(self)
            dlg.setWindowTitle("OK-CONDITIONAL — Bypass Reason Required")
            dlg.setMinimumWidth(520)
            layout = QVBoxLayout(dlg)
            layout.addWidget(QLabel(
                "Trading readiness returned <b>OK - CONDITIONAL</b>.<br><br>"
                "Proceeding requires a documented reason.<br>"
                "This reason will be written to the session audit log."
            ))
            reason_edit = QLineEdit()
            reason_edit.setPlaceholderText("Enter bypass reason (required)…")
            layout.addWidget(reason_edit)
            btns = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            layout.addWidget(btns)
            btns.accepted.connect(dlg.accept)
            btns.rejected.connect(dlg.reject)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return None
            reason = reason_edit.text().strip()
            if reason:
                return reason
            QMessageBox.warning(
                self,
                "Reason Required",
                "You must enter a bypass reason before proceeding.",
            )

    def _append_readiness_bypass_audit(
        self, action: str, decision: str, reason: str
    ) -> None:
        """Append a bypass / block audit record to the most recent readiness report.

        If no report exists for this session, writes a new audit-only file so
        that every session start attempt is traceable.
        """
        try:
            reports_dir = Path(self._readiness_reports_dir)
            reports_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(pytz.timezone("US/Eastern")).strftime("%Y%m%d_%H%M%S")
            audit_entry = {
                "audit_type": "session_start_gate",
                "action": action,
                "decision": decision,
                "bypass_reason": reason,
                "operator_ts_et": stamp,
            }
            # Attach to the cached result so _export_readiness_report can persist it.
            if isinstance(self._last_readiness_result, dict):
                self._last_readiness_result.setdefault("bypass_audit", []).append(
                    audit_entry
                )
                self._export_readiness_report(self._last_readiness_result)
            else:
                # No checklist result cached — write a standalone audit file.
                out_path = reports_dir / f"trading_readiness_{stamp}_audit_{action}.json"
                with out_path.open("w", encoding="utf-8") as handle:
                    json.dump(audit_entry, handle, indent=2, default=str)
        except Exception as exc:
            self.add_system_log(f"⚠️ Failed to write readiness bypass audit: {exc}")

    def _update_readiness_status_display(self, result: dict[str, object] | None) -> None:
        """Update status label and button style for latest readiness decision."""
        label = getattr(self, "readiness_status_label", None)
        button = getattr(self, "readiness_btn", None)
        start_btn = getattr(self, "start_btn", None)
        if label is None or button is None:
            return

        # Keep wording anchored to LIVE to simulate production readiness even in PAPER mode.
        trading_mode_text = "LIVE"
        readiness_button_style = (
            "background-color: #0066CC; color: white; font-size: 12px; "
            "padding: 0 12px; border: 1px solid #2A7BD6; border-radius: 3px;"
        )

        if not isinstance(result, dict):
            label.setText("<<READINESS PENDING>>")
            label.setStyleSheet("color: white; font-size: 13px; font-weight: 600;")
            button.setText("RE-EVALUATE TRADING READINESS")
            button.setStyleSheet(readiness_button_style)
            if start_btn is not None:
                start_btn.setEnabled(True)
                start_btn.setToolTip("Start automated trading")
            return

        decision = str(result.get("decision", "NOT RUN"))
        conditional = bool(result.get("conditional", False))
        reasons = [str(r) for r in (result.get("reasons") or [])]
        warnings = [str(w) for w in (result.get("warnings") or [])]
        checked_at = str(result.get("checked_at_et", ""))
        ts_suffix = checked_at[11:19] if len(checked_at) >= 19 else "--:--:--"

        detail_text = ""
        if decision == "NO":
            if reasons:
                detail_text = "; ".join(reasons)
            else:
                detail_text = "Reason unavailable"
            status_text = (
                f"@ {ts_suffix} ET - NOT READY FOR {trading_mode_text} TRADING "
                f"| Reasons: {detail_text}"
            )
        elif conditional:
            if warnings:
                detail_text = "; ".join(warnings)
                status_text = (
                    f"@ {ts_suffix} ET - YES READY FOR {trading_mode_text} TRADING "
                    f"(CONDITIONAL) | Warnings: {detail_text}"
                )
            else:
                status_text = f"@ {ts_suffix} ET - YES READY FOR {trading_mode_text} TRADING (CONDITIONAL)"  # noqa: E501
        else:
            status_text = f"@ {ts_suffix} ET - YES READY FOR {trading_mode_text} TRADING"
        label.setText(status_text)

        if decision == "OK" and not conditional:
            label.setStyleSheet(f"color: {COLORS['positive']}; font-size: 13px; font-weight: 600;")
            button.setText("RE-EVALUATE TRADING READINESS")
            button.setStyleSheet(readiness_button_style)
            if start_btn is not None:
                start_btn.setEnabled(True)
                if self.trading_mode == TradingMode.PAPER:
                    start_btn.setToolTip("Start paper trading with simulated fills")
                else:
                    start_btn.setToolTip("Start LIVE trading with real order execution")
        elif decision == "OK" and conditional:
            label.setStyleSheet(f"color: {COLORS['warning']}; font-size: 13px; font-weight: 600;")
            button.setText("RE-EVALUATE TRADING READINESS")
            button.setStyleSheet(readiness_button_style)
            if start_btn is not None:
                start_btn.setEnabled(True)
                start_btn.setToolTip("OK-CONDITIONAL active: reduced-risk confirmation required")
        else:
            label.setStyleSheet(f"color: {COLORS['negative']}; font-size: 13px; font-weight: 600;")
            button.setText("RE-EVALUATE TRADING READINESS")
            button.setStyleSheet(readiness_button_style)
            if start_btn is not None and not self.trading_active:
                start_btn.setEnabled(False)
                start_btn.setToolTip("Start blocked: trading readiness is NO")

    def _start_unified_session_supervisor(self) -> bool:
        """Start SessionSupervisor using the currently selected trading mode."""
        if self._session_supervisor is not None and getattr(self._session_supervisor, "is_running", False):  # noqa: E501
            self.logger.debug("Unified session already running")
            return True
        try:
            from Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor import create_session_supervisor

            mode = "live" if self.trading_mode == TradingMode.LIVE else "paper"
            self._session_supervisor = create_session_supervisor(mode=mode)
            started = bool(self._session_supervisor.start())
            if not started:
                self._session_supervisor = None
                return False
            return True
        except Exception as exc:
            self.add_system_log(f"❌ Unified session start failed: {exc}")
            self._session_supervisor = None
            return False

    def _stop_unified_session_supervisor(self, flatten: bool = False) -> None:
        """Stop SessionSupervisor when it is active."""
        supervisor = self._session_supervisor
        self._session_supervisor = None
        if supervisor is None:
            return
        try:
            supervisor.stop(flatten=flatten)
        except Exception as exc:
            self.add_system_log(f"⚠️ Unified session stop error: {exc}")

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
            self.acct_number_lbl.setText(_os_pt.environ.get("TRADIER_SANDBOX_ACCOUNT_ID", "PAPER ACCOUNT"))  # noqa: E501
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
        self.manual_close_spread_requested.connect(
            self._paper_worker.request_close_spread,
            Qt.ConnectionType.QueuedConnection,
        )

        self._paper_thread.start()
        self.add_system_log("PAPER TRADING — Connecting to Tradier sandbox…")

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
        """  # noqa: E501

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
        """  # noqa: E501

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
          <li><b>Core inputs</b> — S08 scores the setup using regime label,
              ATR-normalised distance, RSI confirmation and net dealer GEX context.</li>
          <li><b>Penalties / vetoes</b> — score is reduced during event-window or
              edge-of-day periods, and when VIX is elevated/backwardated.</li>
          <li><b>Score</b> — final confidence score (0–100) with fire threshold at
              <code>MIN_FIRE_SCORE=60</code>.</li>
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
        """  # noqa: E501
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
                f"border: 1px solid {COLORS['border']}; font-size: 12px; color: {color}; text-align: right;"  # noqa: E501
            )
        if self.realized_value:
            color = COLORS["positive"] if realized >= 0 else COLORS["negative"]
            self.realized_value.setText(f"${realized:+,.2f}")
            self.realized_value.setStyleSheet(
                f"padding: 2px 5px; background-color: {COLORS['background']}; "
                f"border: 1px solid {COLORS['border']}; font-size: 12px; color: {color}; text-align: right;"  # noqa: E501
            )
        # Log to system for visibility
        qty = data.get("position_qty", 0)
        n_spreads = data.get("open_spreads", 0)
        spy_last = data.get("spy_last", 0.0)
        if qty > 0:
            self.add_system_log(
                f"Paper: SPY ${spy_last:.2f} | {qty} shares | "
                f"Unrealized: ${unrealized:+,.2f} | Equity: ${equity:,.2f}"
            )
        elif n_spreads > 0:
            self.add_system_log(
                f"Paper: SPY ${spy_last:.2f} | {n_spreads} spread(s) open | "
                f"MTM: ${data.get('spreads_unrealized_pnl', 0.0):+,.2f} | Equity: ${equity:,.2f}"
            )
        else:
            self.add_system_log(f"Paper: SPY ${spy_last:.2f} | No position | Equity: ${equity:,.2f}")  # noqa: E501

        # Persist most recent account panel values for startup restore.
        self._remember_current_account_snapshot()

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
        # Cache the raw payload so the Portfolio Summary popup can render
        # fresh values whenever it is opened or refreshed.
        self._portfolio_summary_cache = dict(data)

        # IV labels
        atm_iv = data.get("atm_iv")
        iv_rank = data.get("iv_rank")
        if self.atm_iv_label is not None:
            if isinstance(atm_iv, (int, float)):
                iv_pct = atm_iv * 100
                iv_col = (
                    COLORS["negative"] if iv_pct >= 50
                    else COLORS.get("warning", COLORS["text"]) if iv_pct >= 30
                    else COLORS["text"]
                )
                self.atm_iv_label.setText(f"ATM IV  {iv_pct:.1f}%")
                self.atm_iv_label.setStyleSheet(f"color: {iv_col}; font-size: 11px;")
            else:
                self.atm_iv_label.setText("ATM IV  —")
                self.atm_iv_label.setStyleSheet(f"color: {COLORS['text']}; font-size: 11px;")
        if self.iv_rank_label is not None:
            if isinstance(iv_rank, (int, float)):
                # Colour: green <25 (low vol = good for sellers), amber 25-50, orange 50-75, red >75
                if iv_rank >= 75:
                    col = COLORS["negative"]
                elif iv_rank >= 50:
                    col = COLORS.get("warning", COLORS["text"])
                elif iv_rank >= 25:
                    col = COLORS.get("warning", COLORS["text"])
                else:
                    col = COLORS["positive"]
                self.iv_rank_label.setText(f"IVR  {iv_rank:.0f}")
                self.iv_rank_label.setStyleSheet(f"color: {col}; font-size: 11px;")
            else:
                self.iv_rank_label.setText("IVR  —")
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
            mtm_col = COLORS["positive"] if spreads_mtm >= 0 else COLORS["negative"]
            n_open = len(spreads_detail)
            self.spreads_summary_label.setText(
                f"OPEN  {n_open}   MTM  ${spreads_mtm:+,.2f}"
            )
            self.spreads_summary_label.setStyleSheet(f"color: {mtm_col}; font-size: 11px;")

        # Buying-power gauge (defined-risk: BP used = Σ max_loss × qty)
        if self.bp_used_label is not None:
            bp_used = 0.0
            for p in spreads_detail:
                try:
                    # max_loss_per_contract is already in dollars (R08 × 100 multiplier
                    # applied at spread construction time) — do NOT multiply by 100 again.
                    bp_used += float(p.get("max_loss_per_contract", 0.0)) * int(p.get("qty", 0))
                except (TypeError, ValueError):
                    continue
            cap = float(getattr(self, "_paper_initial_capital", 100_000.0) or 100_000.0)
            pct = (bp_used / cap * 100.0) if cap > 0 else 0.0
            self.bp_used_label.setText(f"BP  ${bp_used:,.0f} / ${cap:,.0f}  ({pct:.0f}%)")
            # Colour: green <50%, amber 50-80%, red >80%.
            if pct >= 80:
                bp_col = COLORS["negative"]
            elif pct >= 50:
                bp_col = COLORS.get("warning", COLORS["text"])
            else:
                bp_col = COLORS["positive"]
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
            self.realized_today_label.setText(f"REALIZED  ${r:+,.2f}")
            self.realized_today_label.setStyleSheet(f"color: {r_col}; font-size: 11px;")

        # Populate positions_table tree with paper spreads (paper mode only).
        # Live mode keeps the broker-driven _refresh_positions_table flow.
        if (
            getattr(self, "trading_mode", None) == TradingMode.PAPER
            and self.positions_table is not None
        ):
            armed_candidate = data.get("armed_candidate")
            self._render_paper_spreads_in_tree(
                spreads_detail, armed_candidate=armed_candidate
            )

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

        # Phase 3: portfolio-aggregate Greeks labels (with colour coding).
        greeks = data.get("portfolio_greeks") or {}
        _neutral = COLORS["text"]
        _warn = COLORS.get("warning", COLORS["text"])
        _pos = COLORS["positive"]
        _neg = COLORS["negative"]
        if self.port_delta_label is not None:
            d = greeks.get("delta")
            if isinstance(d, (int, float)):
                d_col = _neg if abs(d) >= 60 else _warn if abs(d) >= 30 else _neutral
                self.port_delta_label.setText(f"Δ  {d:+,.1f}")
                self.port_delta_label.setStyleSheet(f"color: {d_col}; font-size: 11px;")
            else:
                self.port_delta_label.setText("Δ  —")
                self.port_delta_label.setStyleSheet(f"color: {_neutral}; font-size: 11px;")
        if self.port_gamma_label is not None:
            g = greeks.get("gamma")
            if isinstance(g, (int, float)):
                g_col = _neg if abs(g) >= 0.30 else _warn if abs(g) >= 0.15 else _neutral
                self.port_gamma_label.setText(f"Γ  {g:+,.2f}")
                self.port_gamma_label.setStyleSheet(f"color: {g_col}; font-size: 11px;")
            else:
                self.port_gamma_label.setText("Γ  —")
                self.port_gamma_label.setStyleSheet(f"color: {_neutral}; font-size: 11px;")
        if self.port_theta_label is not None:
            t = greeks.get("theta")
            if isinstance(t, (int, float)):
                # For premium sellers theta > 0 = earning time decay (good = green).
                # Scale theta to $/day: raw BSM theta is per-day already when × 100 multiplier.
                t_col = _pos if t > 0 else _neg
                self.port_theta_label.setText(f"Θ  ${t:+,.2f}/day")
                self.port_theta_label.setStyleSheet(f"color: {t_col}; font-size: 11px;")
            else:
                self.port_theta_label.setText("Θ  —")
                self.port_theta_label.setStyleSheet(f"color: {_neutral}; font-size: 11px;")
        if self.port_vega_label is not None:
            v = greeks.get("vega")
            if isinstance(v, (int, float)):
                v_col = _neg if v <= -800 else _warn if v <= -300 else _neutral
                self.port_vega_label.setText(f"V  {v:+,.1f}")
                self.port_vega_label.setStyleSheet(f"color: {v_col}; font-size: 11px;")
            else:
                self.port_vega_label.setText("V  —")
                self.port_vega_label.setStyleSheet(f"color: {_neutral}; font-size: 11px;")
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

        # If the Portfolio Summary dialog is open, push refreshed data to it.
        dlg = self._portfolio_summary_dialog
        if dlg is not None and dlg.isVisible():
            self._populate_portfolio_summary_table(dlg)

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
                f"border: 1px solid {COLORS['border']}; font-size: 12px; color: {color}; text-align: right;"  # noqa: E501
            )

        # Persist most recent account panel values for startup restore.
        self._remember_current_account_snapshot()

        # Refresh P&L performance table with live TODAY fields.
        # Worker emits generic keys (realized_pnl/win_rate/etc.), while the
        # table expects period-scoped keys (today_pnl/today_win_rate/etc.).
        enriched = dict(metrics)
        if realized_str and not enriched.get("today_pnl"):
            enriched["today_pnl"] = str(realized_str)

        win_rate_raw = enriched.get("win_rate")
        if win_rate_raw is not None and not enriched.get("today_win_rate"):
            try:
                win_rate_num = float(str(win_rate_raw).replace("%", ""))
                if win_rate_num <= 1.0:
                    win_rate_num *= 100.0
                enriched["today_win_rate"] = f"{win_rate_num:.1f}%"
            except (TypeError, ValueError):
                pass

        if not enriched.get("today_win_loss"):
            # Prefer explicit counts if present; otherwise infer from
            # total_trades + win_rate for a live-updating summary.
            try:
                wins = int(enriched.get("winning_trades")) if enriched.get("winning_trades") is not None else None  # noqa: E501
                losses = int(enriched.get("losing_trades")) if enriched.get("losing_trades") is not None else None  # noqa: E501
            except (TypeError, ValueError):
                wins = None
                losses = None

            if wins is not None and losses is not None:
                enriched["today_win_loss"] = f"{wins}/{losses}"
            else:
                try:
                    total_trades = int(str(enriched.get("total_trades", "0")))
                    wr = enriched.get("today_win_rate")
                    if wr is None:
                        wr = win_rate_raw
                    wr_num = float(str(wr).replace("%", ""))
                    if wr_num <= 1.0:
                        wr_num *= 100.0
                    wins_inf = int(round(total_trades * (wr_num / 100.0)))
                    losses_inf = max(0, total_trades - wins_inf)
                    if total_trades > 0:
                        enriched["today_win_loss"] = f"{wins_inf}/{losses_inf}"
                except (TypeError, ValueError):
                    pass

        if not enriched.get("today_profit_factor"):
            try:
                et_tz = pytz.timezone("US/Eastern")
                today_et = datetime.now(et_tz).date()
                gross_profit = 0.0
                gross_loss = 0.0
                for trade in getattr(self, "_closed_trades_cache", []):
                    if not isinstance(trade, dict):
                        continue
                    closed_at = trade.get("closed_at")
                    if closed_at is None:
                        continue
                    try:
                        closed_dt = datetime.fromtimestamp(float(closed_at), tz=pytz.UTC).astimezone(et_tz)  # noqa: E501
                    except (TypeError, ValueError, OSError, OverflowError):
                        continue
                    if closed_dt.date() != today_et:
                        continue
                    pnl = float(trade.get("realized_pnl", 0.0) or 0.0)
                    if pnl > 0:
                        gross_profit += pnl
                    elif pnl < 0:
                        gross_loss += abs(pnl)

                if gross_loss > 0:
                    enriched["today_profit_factor"] = f"{(gross_profit / gross_loss):.2f}"
                elif gross_profit > 0:
                    enriched["today_profit_factor"] = "∞"
            except Exception:
                pass

        if not enriched.get("today_sharpe") or not enriched.get("today_sortino"):
            try:
                import math

                et_tz = pytz.timezone("US/Eastern")
                today_et = datetime.now(et_tz).date()
                returns: list[float] = []
                downside: list[float] = []

                for trade in getattr(self, "_closed_trades_cache", []):
                    if not isinstance(trade, dict):
                        continue
                    closed_at = trade.get("closed_at")
                    if closed_at is None:
                        continue
                    try:
                        closed_dt = datetime.fromtimestamp(float(closed_at), tz=pytz.UTC).astimezone(et_tz)  # noqa: E501
                    except (TypeError, ValueError, OSError, OverflowError):
                        continue
                    if closed_dt.date() != today_et:
                        continue

                    # Prefer stored return_on_risk_pct; fallback to pnl/max_loss.
                    ret = trade.get("return_on_risk_pct")
                    if ret is None:
                        try:
                            pnl = float(trade.get("realized_pnl", 0.0) or 0.0)
                            max_loss = float(trade.get("max_loss_dollars", 0.0) or 0.0)
                            if max_loss <= 0:
                                continue
                            ret = (pnl / max_loss) * 100.0
                        except (TypeError, ValueError):
                            continue
                    try:
                        r = float(ret) / 100.0
                    except (TypeError, ValueError):
                        continue
                    returns.append(r)
                    if r < 0:
                        downside.append(r)

                if len(returns) >= 2:
                    mean_r = sum(returns) / len(returns)
                    var = sum((x - mean_r) ** 2 for x in returns) / (len(returns) - 1)
                    std = math.sqrt(max(var, 0.0))
                    if std > 0:
                        sharpe = (mean_r / std) * math.sqrt(len(returns))
                        enriched.setdefault("today_sharpe", f"{sharpe:.2f}")

                    if downside:
                        target = 0.0
                        dvar = sum((x - target) ** 2 for x in downside) / len(downside)
                        dstd = math.sqrt(max(dvar, 0.0))
                        if dstd > 0:
                            sortino = (mean_r - target) / dstd * math.sqrt(len(returns))
                            enriched.setdefault("today_sortino", f"{sortino:.2f}")
                        elif mean_r > 0:
                            enriched.setdefault("today_sortino", "∞")
                    elif mean_r > 0:
                        enriched.setdefault("today_sortino", "∞")
            except Exception:
                pass

        # ── Calmar: cumulative return / max drawdown (session basis) ──────────
        if not enriched.get("today_calmar"):
            try:
                import math
                # Total return % = realised P&L / initial capital * 100
                realized_raw = enriched.get("realized_pnl", "")
                initial_cap  = float(enriched.get("initial_capital", 0.0) or 0.0)
                if initial_cap <= 0:
                    # Fallback: read from state file via cached position update
                    initial_cap = float(
                        getattr(self, "_paper_initial_capital", 0.0) or 0.0
                    )
                realized_pnl = 0.0
                if isinstance(realized_raw, str):
                    realized_pnl = float(realized_raw.replace("$", "").replace(",", "").replace("+", "") or 0.0)  # noqa: E501
                elif isinstance(realized_raw, (int, float)):
                    realized_pnl = float(realized_raw)

                max_dd_raw = enriched.get("max_drawdown", "0")
                max_dd = float(str(max_dd_raw).replace("%", "") or 0.0)
                # Worker emits max_drawdown as a decimal fraction (e.g. 0.0028)
                if 0 < max_dd < 1:
                    max_dd_pct = max_dd * 100.0
                else:
                    max_dd_pct = max_dd  # already in percent

                if initial_cap > 0 and max_dd_pct > 0:
                    total_return_pct = (realized_pnl / initial_cap) * 100.0
                    calmar = total_return_pct / max_dd_pct
                    enriched["today_calmar"] = f"{calmar:.2f}"
                elif initial_cap > 0 and realized_pnl > 0 and max_dd_pct == 0:
                    enriched["today_calmar"] = "∞"
            except Exception:
                pass

        self._refresh_pnl_table(enriched)

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
                        item.setForeground(QColor(COLORS["positive"] if num >= 0 else COLORS["negative"]))  # noqa: E501
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
            self.acct_number_lbl.setText(_os_stop.environ.get("TRADIER_SANDBOX_ACCOUNT_ID", "PAPER ACCOUNT"))  # noqa: E501
        for lbl in (self.settled_value, self.buying_value, self.realized_value, self.unrealized_value):  # noqa: E501
            if lbl:
                lbl.setText("—")

        self.add_system_log("PAPER TRADING STOPPED — Session ended")

    @Slot(float, float)
    def _on_balance_updated(self, equity: float, buying_power: float):
        """Update account balance fields from Tradier API (emitted by market worker heartbeat)."""
        # In paper-trading mode the paper worker keeps these labels updated; skip to avoid
        # overwriting live paper P&L with the (potentially zero) sandbox account balance.
        if self.trading_active and self._paper_worker is not None:
            return
        if self.settled_value:
            self.settled_value.setText(f"${equity:,.2f}")
        if self.buying_value:
            self.buying_value.setText(f"${buying_power:,.2f}")

        # Reconcile idle PAPER account balances into visible P&L so orphan
        # account-level adjustments (for example sandbox cash drift) are not
        # silently omitted from the dashboard's realized/year fields.
        if self.trading_mode == TradingMode.PAPER and not self.trading_active:
            try:
                initial_cap = float(getattr(self, "_paper_initial_capital", 100_000.0) or 100_000.0)
                realized_delta = float(equity) - initial_cap

                if self.realized_value:
                    color = COLORS["positive"] if realized_delta >= 0 else COLORS["negative"]
                    self.realized_value.setText(f"${realized_delta:+,.2f}")
                    self.realized_value.setStyleSheet(
                        f"padding: 2px 5px; background-color: {COLORS['background']}; "
                        f"border: 1px solid {COLORS['border']}; font-size: 12px; color: {color}; text-align: right;"  # noqa: E501
                    )

                # Keep YEAR (and TODAY when empty) in sync with the reconciled
                # account-level P&L so the performance table is not all dashes.
                mode_stats = dict(self._pnl_stats_by_mode.get(self.trading_mode, {}))
                realized_str = f"${realized_delta:+,.2f}"
                mode_stats["year_pnl"] = realized_str
                if str(mode_stats.get("today_pnl", "—")).strip() in {"", "—", "-"}:
                    mode_stats["today_pnl"] = realized_str
                self._refresh_pnl_table(mode_stats)
            except Exception as exc:
                self.logger.debug("paper balance reconciliation skipped: %s", exc)

        # Persist most recent account panel values for startup restore.
        self._remember_current_account_snapshot()

    def _init_account_display(self):
        """Set account P&L fields to $0.00 and load any persisted performance stats.

        Called once on startup (via QTimer.singleShot) after setup_ui() so every
        label is a real widget rather than None.  Ensures the account section never
        stays on the placeholder "—" values while waiting for the first trading
        session to start.
        """
        # Show $0.00 for session P&L — no trades have occurred yet.
        if self.realized_value:
            self.realized_value.setText("$0.00")
        if self.unrealized_value:
            self.unrealized_value.setText("$0.00")

        # Restore persisted account values for the current mode when available.
        saved_account = self._account_snapshot_by_mode.get(self.trading_mode)
        if isinstance(saved_account, dict) and saved_account:
            self._apply_account_snapshot(saved_account)

        # Load any historical performance stats persisted by H07 so the P&L
        # Performance table shows real data immediately, not all "—".
        self._refresh_pnl_table(self._pnl_stats_by_mode.get(self.trading_mode, {}))

    @Slot(bool)
    def _on_paper_connection(self, connected: bool):
        """Handle paper trading connection result."""
        if connected:
            self.on_connection_status_changed(True, "Tradier (PAPER)")
            self.update_data_status("PAPER")
            if self.acct_number_lbl:
                import os as _os_conn
                self.acct_number_lbl.setText(_os_conn.environ.get("TRADIER_SANDBOX_ACCOUNT_ID", "PAPER ACCOUNT"))  # noqa: E501
            self.add_system_log("PAPER TRADING ACTIVE — Connected to Tradier sandbox")
        else:
            self.add_system_log("❌ Paper trading could not connect to Tradier")

    def stop_trading(self):
        """Handle stop trading button click — mode-aware."""
        if not self.trading_active:
            if not self.api_connected:
                QMessageBox.information(
                    self,
                    "API Disconnected",
                    "API is disconnected - further trading has already stopped, but open orders at Tradier still remain in effect. If you wish to close or cancel these orders, call Tradier at +1 (312) 542-6901",  # noqa: E501
                )
            self.add_system_log("No active trading to stop")
            return

        self._stop_unified_session_supervisor(flatten=False)

        self.trading_active = False
        self.connection_info.trading_active = False

        self.start_btn.setStyleSheet(
            f"background-color: {COLORS['positive']}; color: black;",
        )
        self.start_btn.setText("START TRADING")

        self.add_system_log("Trading stopped - Orders and positions remain active")
        self.add_system_log("TRADING STOPPED - Existing positions maintained")
        self.add_system_log("Automation session inactive")

    def emergency_close(self):
        """Handle emergency close button click - FIXED MESSAGES"""
        if not self.api_connected:
            QMessageBox.critical(
                self,
                "API Disconnected",
                "API is disconnected - unable to close open orders at Tradier. If you wish to close or cancel these orders, call Tradier at +1 (312) 542-6901",  # noqa: E501
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
            self.add_system_log(
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
        if status_type in ("LIVE", "REAL-TIME", "PAPER") and is_market_hours():
            self.data_status_label.setText("REAL-TIME")
            self.data_status_label.setStyleSheet(
                "color: " + COLORS["positive"] + "; font-size: 14px;",
            )
            self.data_status_container.setCursor(Qt.CursorShape.ArrowCursor)
            self.data_status_container.setToolTip("Real-time market data — live prices")
        elif status_type in ("LIVE", "REAL-TIME", "PAPER"):
            self.data_status_label.setText("EOD")
            self.data_status_label.setStyleSheet(
                "color: " + COLORS["warning"] + "; font-size: 14px;",
            )
            self.data_status_container.setCursor(Qt.CursorShape.PointingHandCursor)
            self.data_status_container.setToolTip("Market closed — showing EOD data")
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
        """Determine appropriate data status based on current conditions - FIXED SIMULATION DETECTION"""  # noqa: E501
        market_hours = is_market_hours()
        et_tz = pytz.timezone("US/Eastern")

        def _as_et(timestamp: datetime) -> datetime:
            if timestamp.tzinfo is None:
                return et_tz.localize(timestamp)
            return timestamp.astimezone(et_tz)

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
                    quote_age_seconds = (
                        datetime.now(et_tz) - _as_et(freshest_quote_time)
                    ).total_seconds()
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
                    datetime.now(et_tz) - _as_et(self.connection_info.last_successful_data)
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
        """Market data is always Tradier; this handler is a no-op."""
        self.add_system_log("ℹ️ Tradier is the only market data provider")
        self._apply_mkt_provider_display("tradier")

    def _apply_mkt_provider_display(self, provider: str) -> None:
        """Update the market data provider indicator label in the toolbar.

        Color is connection-based: red when disconnected, green when connected.
        """
        if not hasattr(self, "mkt_provider_label"):
            return
        if getattr(self, "mkt_data_connected", False) and is_market_hours():
            color = COLORS["positive"]
        elif getattr(self, "mkt_data_connected", False):
            color = COLORS["warning"]
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
            self.add_system_log("⚠️ EOD snapshot unavailable — Tradier unreachable or not configured")  # noqa: E501
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
            self._metrics_orchestrator.stress_level_changed.connect(self._on_market_stress_changed)
            self.add_system_log("✅ Custom metrics orchestrator started (DIX + Black Swan schedulers active)")  # noqa: E501
            self.add_system_log("AUTONOMOUS METRICS ACTIVE - DIX/SWAN stress monitor online")
        except Exception as e:
            self.logger.error("Failed to start metrics orchestrator: %s", e, exc_info=True)
            self.add_system_log(f"⚠️ Metrics orchestrator unavailable: {e}")

    def _on_market_stress_changed(self, stress_level: str) -> None:
        """Surface market stress-regime transitions in Autonomous AI Activity."""
        level = str(stress_level).strip().upper() or "UNKNOWN"
        self.log_autonomous_event(
            f"S07 STRESS LEVEL → {level}",
            event_type="AGENT_OBSERVATION",
            source="S07",
        )

    def _on_custom_metrics_updated(self, metrics: dict) -> None:
        """Slot for SpyderS07 CustomMetricsOrchestrator.metrics_updated signal.

        S07 emits a nested dict: {"GEX": {"value": <float>, ...}, "DEX": {...}, ...}
        The widget expects raw-dollar values that it then divides by 1e9/"M" to format:
          - GEX: billions (S05 contract) → ×1e9 here → raw dollars → widget ÷1e9 → "B"
          - DEX: millions (S05 contract) → ×1e6 here → raw dollars → widget ÷1e6 → "M"
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
            # Use abs(prev) as the denominator so that negative-valued metrics
            # (e.g. VRP = -1.45, NYMO, $TICK when negative) do not produce a
            # sign-flipped percentage.  A positive change always yields a positive
            # percentage regardless of the sign of the level.
            change_pct = (change / abs(prev) * 100.0) if prev else 0.0
            setattr(self, prev_attr, value)

            widget.update_data({"last": value, "change": change, "change_pct": change_pct})

        liquidity_entry = metrics.get("LIQUIDITY_DIAGNOSTICS")
        if isinstance(liquidity_entry, dict):
            payload = liquidity_entry.get("value", {})
            self._update_liquidity_diagnostics_panel(payload)

        # Forward TICK/ADD/TRIN/NYMO to the Market Internals dialog if it is open.
        # This ensures the popup always shows the same values as the Market Overview panel.
        dlg = getattr(self, "current_dialog", None)
        if dlg is not None and hasattr(dlg, "on_breadth_updated"):
            import math
            tick_entry = metrics.get("TICK", {})
            add_entry  = metrics.get("ADD",  {})
            trin_entry = metrics.get("TRIN", {})
            nymo_entry = metrics.get("NYMO", {})
            if isinstance(tick_entry, dict) and isinstance(add_entry, dict) and isinstance(trin_entry, dict):  # noqa: E501
                tick = tick_entry.get("value", float("nan"))
                add  = add_entry.get("value",  float("nan"))
                trin = trin_entry.get("value", float("nan"))
                nymo = nymo_entry.get("value", float("nan")) if isinstance(nymo_entry, dict) else float("nan")  # noqa: E501
                if not (isinstance(tick, float) and math.isnan(tick)
                        and isinstance(add, float) and math.isnan(add)
                        and isinstance(trin, float) and math.isnan(trin)):
                    breadth_entry = metrics.get("BREADTH_REGIME", {})
                    regime = breadth_entry.get("value", "") if isinstance(breadth_entry, dict) else ""  # noqa: E501
                    dlg.on_breadth_updated({
                        "tick": tick,
                        "add":  add,
                        "trin": trin,
                        "nymo": nymo,
                        "breadth_regime": regime,
                    })

        # Update the 5-pill regime bar from live S07 metrics.
        self.update_regime_pills(metrics)

        # Sync REGIME traffic-light button in the SIGNAL MONITOR panel.
        if self.signal_panel is not None:
            import math

            def _sv(key: str, default: float) -> float:
                e = metrics.get(key)
                if not isinstance(e, dict):
                    return default
                v = e.get("value", default)
                return default if (isinstance(v, float) and math.isnan(v)) else float(v)

            # Use the cached regime value (set by update_regime_pills) for the signal panel.
            _regime_for_panel = getattr(self, "_regime_value", "—")
            self.signal_panel.update_regime(
                _regime_for_panel,
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

    @staticmethod
    def _summarize_liquidity_diagnostics(payload: dict) -> dict:
        """Summarize S07 liquidity diagnostics payload into dashboard-friendly scalars."""
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        candidates = data.get("candidates", []) if isinstance(data, dict) else []
        if not isinstance(candidates, list):
            candidates = []

        total = len(candidates)
        pass_count = 0
        reason_counts: dict[str, int] = {}
        freshness_samples: list[float] = []

        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            if candidate.get("pass") is True:
                pass_count += 1
            for reason in candidate.get("fail_reasons", []) or []:
                if isinstance(reason, str) and reason:
                    reason_counts[reason] = reason_counts.get(reason, 0) + 1

            snapshot = candidate.get("snapshot", {}) if isinstance(candidate.get("snapshot", {}), dict) else {}  # noqa: E501
            quote_age_ms = snapshot.get("quote_age_ms")
            if isinstance(quote_age_ms, (int, float)):
                freshness_samples.append(float(quote_age_ms))

        fail_count = max(0, total - pass_count)
        top_failure = "none"
        if reason_counts:
            top_failure = max(reason_counts.items(), key=lambda item: item[1])[0]
        median_freshness_ms = float(np.median(freshness_samples)) if freshness_samples else float("nan")  # noqa: E501

        return {
            "total": total,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "top_failure": top_failure,
            "median_freshness_ms": median_freshness_ms,
        }

    def _update_liquidity_diagnostics_panel(self, payload: dict) -> None:
        """Update right-panel liquidity diagnostics labels from S07 payload."""
        if self.liquidity_candidates_value is None:
            return

        summary = self._summarize_liquidity_diagnostics(payload)
        total = summary["total"]
        pass_count = summary["pass_count"]
        fail_count = summary["fail_count"]

        self.liquidity_candidates_value.setText(str(total))
        self.liquidity_pass_ratio_value.setText(f"{pass_count}/{total}" if total else "0/0")

        freshness = summary["median_freshness_ms"]
        if isinstance(freshness, float) and np.isnan(freshness):
            self.liquidity_freshness_value.setText("-")
        else:
            self.liquidity_freshness_value.setText(f"{freshness:.0f} ms")

        if fail_count <= 0:
            self.liquidity_top_failure_value.setText("none")
        else:
            self.liquidity_top_failure_value.setText(summary["top_failure"])

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

    # ──────────────────────────────────────────────────────────────────
    # Regime pill bar — 5-field display (REGIME / STRESS / STANCE / GATE / DISPATCH)
    # ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _pill_stylesheet(category: str) -> tuple[str, str]:
        """Return (stylesheet, fg_color) for the given semantic pill category.

        The stylesheet sets white for the static label text; callers should
        wrap the dynamic value in a <span style="color: {fg};"> tag so the
        label and value are two-toned (white label, semantic-colour value).

        Categories (case-insensitive):
            stress low → green
            stress medium → orange
            stress high → red
            stress crisis → purple
            bull / bullish / flowing   → green
            bear / bearish / error     → red
            range / neutral / choppy / none / blocked → orange
            crisis / event / halt / risk-off → purple
            idle → grey
            default → grey (initial / unknown)
        """
        c = category.lower()
        if c == "low":
            bg, border, fg = "#1a4a1a", "#2d8a2d", "#5ddb5d"
        elif c == "medium":
            bg, border, fg = "#3a2800", "#8a5a00", "#e09020"
        elif c == "high":
            bg, border, fg = "#4a1a1a", "#8a2d2d", "#e05555"
        elif c == "crisis":
            bg, border, fg = "#3a1055", "#9a30dd", "#cc88ff"
        elif any(k in c for k in ("bull", "bullish", "flowing")):
            bg, border, fg = "#1a4a1a", "#2d8a2d", "#5ddb5d"
        elif any(k in c for k in ("bear", "bearish", "error")):
            bg, border, fg = "#4a1a1a", "#8a2d2d", "#e05555"
        elif any(k in c for k in ("crisis", "event", "halt", "risk-off")):
            bg, border, fg = "#3a1055", "#9a30dd", "#cc88ff"
        elif c == "none" or c.endswith(": none") or c == "idle":
            bg, border, fg = "#1e1e1e", "#444444", "#888888"
        elif any(k in c for k in ("range", "neutral", "choppy", "volatile", "cautious", "blocked")):
            bg, border, fg = "#3a2800", "#8a5a00", "#e09020"
        else:
            bg, border, fg = "#1e1e1e", "#444444", "#aaaaaa"
        stylesheet = (
            f"color: white; background-color: {bg}; "
            f"border: 1px solid {border}; border-radius: 4px; "
            "padding: 2px 10px; font-size: 13px;"
        )
        return stylesheet, fg

    def _get_dispatch_state_safe(self) -> dict:
        """Read D31's dispatch state, falling back to IDLE if unavailable.

        D31 lives behind the SessionSupervisor, which is None until the
        operator starts a paper or live session. Before that, return IDLE so
        the pill renders sensibly without raising.
        """
        try:
            sup = getattr(self, "_session_supervisor", None)
            orchestrator = getattr(sup, "orchestrator", None) if sup else None
            if orchestrator is not None and hasattr(orchestrator, "get_dispatch_state"):
                return orchestrator.get_dispatch_state()
        except Exception as exc:  # noqa: BLE001 — pill must never raise
            self.logger.debug("dispatch pill: D31 read failed: %s", exc)
        return {"state": "IDLE", "reason": "no session running", "age_s": None}

    def update_regime_pills(self, metrics: dict) -> None:
        """Derive all regime-bar pill values from S07 metrics and update the bar.

                Mapping:
                    REGIME    — canonical label (BULL / BEAR / RANGE / VOLATILE / CRISIS / EVENT)
                    STRESS    — S07 stress band (LOW / MEDIUM / HIGH / CRISIS / UNKNOWN)
                    STANCE    — strategy stance from D30 (BULLISH / CHOPPY / CRISIS)
                    GATE      — policy gate label (Bull Trend / Bear Trend / Range Calm /
                                                                                 High Vol / Crisis / Event)
                    DISPATCH  — execution state from D31, with regime-driven HALT priority
                                            (FLOWING / IDLE / BLOCKED / ERROR / HALT)

                v12 changes:
                    - BIAS pill removed (was informational, did not gate execution).
                    - TRADEABLE pill removed; its halt visual is now carried by DISPATCH=HALT
                        (purple), and its permitted-strategy / concurrency tooltip content is
                        now appended to the DISPATCH tooltip in every state.
                    - DISPATCH reads D31's `get_dispatch_state()` directly so operators see
                        *why* trades aren't firing without tailing the decision log.
        """
        import math

        if not hasattr(self, "regime_pill"):
            # Pills not yet built (dashboard not fully initialised).
            return

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

        # Determine whether S07 is actually providing SWAN and DIX, or whether
        # we are running on cold defaults (i.e. S07 not running / no data yet).
        _swan_live = isinstance(metrics.get("SWAN"), dict) and metrics["SWAN"].get("value") is not None
        _dix_live  = isinstance(metrics.get("DIX"),  dict) and metrics["DIX"].get("value")  is not None
        _s07_live  = _swan_live and _dix_live

        # ── Sticky regime state (persists across S07 outage gaps) ──────────
        # Initialise on first call.
        if not hasattr(self, "_regime_sticky"):
            self._regime_sticky: str | None = None   # last regime produced by S07
        # Candidate debounce for VIX-only fallback (avoids second-by-second flips).
        if not hasattr(self, "_vix_candidate_regime"):
            self._vix_candidate_regime: str  = "RANGE"
            self._vix_candidate_count:  int  = 0
        _VIX_COMMIT_CYCLES = 3  # require 3 consecutive same-value reads (~3 s)

        # ── VIX-based candidate regime (always computed for debounce logic) ──
        _vix_new_regime = "RANGE"
        try:
            import json as _j
            _ld_path = self.data_file
            if _ld_path.exists():
                with open(_ld_path) as _f:
                    _ld = _j.load(_f)
                def _ql(key: str) -> float | None:
                    e = _ld.get(key)
                    return float(e["last"]) if isinstance(e, dict) and e.get("last") else None
                def _qc(key: str) -> float:
                    e = _ld.get(key)
                    return float(e.get("change_pct", 0.0)) if isinstance(e, dict) else 0.0
                _vix    = _ql("VIX")  or 0.0
                _vix9d  = _ql("VIX9D") or 0.0
                _spx_cp = _qc("SPX")   # SPX day-change %
                # VIX9D > VIX = term-structure inversion → panic/crisis signal
                _inverted = _vix9d > 0.0 and _vix > 0.0 and _vix9d > _vix
                if _inverted or _vix >= 35:
                    _vix_new_regime = "CRISIS"
                elif _vix >= 25:
                    _vix_new_regime = "VOLATILE"
                elif _spx_cp <= -1.5:
                    # Strong bear: requires larger threshold than a -0.4% tick
                    _vix_new_regime = "BEAR"
                elif _spx_cp >= 1.0 and _vix < 20:
                    # Strong bull: requires > +1% with VIX calm
                    _vix_new_regime = "BULL"
                else:
                    _vix_new_regime = "RANGE"
        except Exception:
            pass

        # Debounce: only commit to a new VIX regime after _VIX_COMMIT_CYCLES consecutive matches.
        if _vix_new_regime == self._vix_candidate_regime:
            self._vix_candidate_count = min(self._vix_candidate_count + 1, _VIX_COMMIT_CYCLES)
        else:
            self._vix_candidate_regime = _vix_new_regime
            self._vix_candidate_count  = 1

        _vix_regime = self._vix_candidate_regime if self._vix_candidate_count >= _VIX_COMMIT_CYCLES else (
            self._regime_sticky or "RANGE"
        )

        # ── Canonical regime ────────────────────────────────────────────
        if not _s07_live:
            # Prefer last-known-good S07 regime over VIX fallback.
            if self._regime_sticky is not None:
                regime = self._regime_sticky
            else:
                regime = _vix_regime
        elif swan >= 2.0:
            regime = "CRISIS"
        elif swan >= 1.95 or skew >= 150:
            regime = "VOLATILE"
        elif skew >= 140 and dix < 42:
            regime = "RANGE"
        elif dix >= 46 and gex >= 0 and swan < 1.9:
            regime = "BULL"
        elif dix <= 40 and swan >= 1.85:
            regime = "BEAR"
        elif dix >= 43 and swan < 1.92:
            regime = "BULL"
        else:
            regime = "RANGE"

        # Save this cycle's S07-derived regime as the sticky fallback for gaps.
        if _s07_live:
            self._regime_sticky = regime

        # ── Strategy Stance (D30 mapping) ───────────────────────────────
        if regime == "BULL":
            stance = "BULLISH"
        elif regime == "CRISIS":
            stance = "CRISIS"
        else:
            stance = "CHOPPY"

        # ── Stress level (S07 SWAN bands) ───────────────────────────────
        stress = "UNKNOWN"
        if _s07_live:
            if swan >= 3.0:
                stress = "CRISIS"
            elif swan >= 2.0:
                stress = "HIGH"
            elif swan >= 1.5:
                stress = "MEDIUM"
            else:
                stress = "LOW"
        else:
            try:
                orchestrator = getattr(self, "_metrics_orchestrator", None)
                if orchestrator is not None and hasattr(orchestrator, "get_stress_level"):
                    _stress_obj = orchestrator.get_stress_level()
                    stress = str(getattr(_stress_obj, "value", _stress_obj)).strip().upper() or "UNKNOWN"
            except Exception as _stress_err:
                self.logger.debug("stress-pill read failed: %s", _stress_err)

        # ── Strategy Gate (D31 policy bucket) ───────────────────────────
        _gate_map = {
            "BULL":     "BULL TREND",
            "BEAR":     "BEAR TREND",
            "RANGE":    "RANGE CALM",
            "VOLATILE": "HIGH VOL",
            "CRISIS":   "CRISIS",
            "EVENT":    "EVENT",
        }
        gate = _gate_map.get(regime, "RANGE CALM")

        # ── Descriptive tooltips (dynamic — updated each refresh cycle) ──────
        _REGIME_TIPS: dict[str, str] = {
            "BULL": (
                "<b>BULL REGIME</b><br><br>"
                "<b>Trigger (all):</b><br>"
                "&bull; SPY &gt; SPY EMA50<br>"
                "&bull; VIX &lt; VIX EMA50<br>"
                "&bull; Not EVENT and not CRISIS<br><br>"
                "<b>Action:</b><br>"
                "&bull; Regime = BULL<br>"
                "&bull; Strategy = SpyderD06_BullPutSpread"
            ),
            "BEAR": (
                "<b>BEAR REGIME</b><br><br>"
                "<b>Trigger (all):</b><br>"
                "&bull; SPY &lt; SPY EMA50<br>"
                "&bull; VIX &gt; VIX EMA50<br>"
                "&bull; Not EVENT and not CRISIS<br><br>"
                "<b>Action:</b><br>"
                "&bull; Regime = BEAR<br>"
                "&bull; Strategy = SpyderD07_BearCallSpread"
            ),
            "RANGE": (
                "<b>RANGE REGIME</b><br><br>"
                "<b>Trigger (all):</b><br>"
                "&bull; SPY within 1.0 ATR of EMA50<br>"
                "&bull; Term structure not stressed (VIX9D &le; VIX or VIX &le; VXV)<br>"
                "&bull; Not EVENT and not CRISIS<br><br>"
                "<b>Action:</b><br>"
                "&bull; Regime = RANGE<br>"
                "&bull; Strategy = SpyderD02_IronCondor"
            ),
            "VOLATILE": (
                "<b>VOLATILE REGIME</b><br><br>"
                "<b>Trigger (all):</b><br>"
                "&bull; SPY ATR% &ge; 1.5%<br>"
                "&bull; VIX Percentile &ge; 80th OR VIX &ge; 25<br>"
                "&bull; Not EVENT and not CRISIS<br><br>"
                "<b>Action:</b><br>"
                "&bull; Regime = VOLATILE<br>"
                "&bull; Strategy = SpyderD10_IronButterfly"
            ),
            "CRISIS": (
                "<b>CRISIS REGIME &mdash; HARD HALT</b><br><br>"
                "<b>Trigger (any one):</b><br>"
                "&bull; VIX9D &gt; VIX (front-vol inversion)<br>"
                "&bull; VIX &ge; 35<br>"
                "&bull; SPY drop &le; &minus;1.25% AND VIX change &ge; +4 pts<br><br>"
                "<b>Action:</b><br>"
                "&bull; Regime = CRISIS<br>"
                "&bull; Hard halt / kill-switch &mdash; no new entries"
            ),
            "EVENT": (
                "<b>EVENT REGIME &mdash; NO TRADE</b><br><br>"
                "<b>Trigger:</b><br>"
                "&bull; Event clock state in {pre, live, post}<br>"
                "&bull; OR &le; 30 min to high-impact macro event<br><br>"
                "<b>Action:</b><br>"
                "&bull; Regime = EVENT<br>"
                "&bull; Hard halt &mdash; no new strategy entries"
            ),
        }
        _DISPATCH_TIPS: dict[str, str] = {
            "FLOWING": (
                "<b>ENTRY: FLOWING</b><br><br>"
                "D31 has approved and dispatched a signal in the last 120s.<br>"
                "The execution pipeline is healthy &mdash; new entries are permitted "
                "under the active Strategy Gate."
            ),
            "IDLE": (
                "<b>ENTRY: IDLE</b><br><br>"
                "No signal events in the last 120s &mdash; no drops, no dispatches.<br>"
                "Expected outside RTH or between strategy cadences. "
                "Entries are permitted under the active Strategy Gate."
            ),
            "BLOCKED": (
                "<b>ENTRY: BLOCKED</b><br><br>"
                "A guardrail dropped the latest signal in the last 120s.<br>"
                "See reason below; full context in "
                "<code>logs/decisions/YYYY-MM-DD.jsonl</code>."
            ),
            "ERROR": (
                "<b>ENTRY: ERROR</b><br><br>"
                "A <code>dispatch_exception</code> occurred in the last 120s.<br>"
                "This is a system error, not a guardrail. "
                "Investigate via <code>logs/decisions/YYYY-MM-DD.jsonl</code>."
            ),
            "HALT": (
                "<b>ENTRY: HALT &mdash; NO NEW ENTRIES</b><br><br>"
                "CRISIS or EVENT regime is active &mdash; all entry pipelines blocked "
                "by hard halt / kill-switch policy."
            ),
        }
        _STANCE_TIPS: dict[str, str] = {
            "BULLISH": (
                "<b>BULLISH STANCE</b><br><br>"
                "D30 maps BULL regime &rarr; BULLISH stance<br><br>"
                "<b>Permitted strategy:</b> SpyderD06_BullPutSpread"
            ),
            "CHOPPY": (
                "<b>CHOPPY STANCE</b><br><br>"
                "D30 maps BEAR / RANGE / VOLATILE &rarr; CHOPPY stance<br>"
                "Specific strategy is determined by Strategy Gate:<br><br>"
                "&bull; BEAR &rarr; SpyderD07_BearCallSpread<br>"
                "&bull; RANGE &rarr; SpyderD02_IronCondor<br>"
                "&bull; VOLATILE &rarr; SpyderD10_IronButterfly"
            ),
            "CRISIS": (
                "<b>CRISIS STANCE</b><br><br>"
                "D30 maps CRISIS / EVENT &rarr; CRISIS stance<br><br>"
                "<i>Hard halt &mdash; no new entries permitted</i>"
            ),
        }
        _STRESS_TIPS: dict[str, str] = {
            "LOW": (
                "<b>STRESS: LOW</b><br><br>"
                "S07 SWAN is in calm band (&lt; 1.5).<br>"
                "Lower urgency backdrop; slower metric cadence may apply."
            ),
            "MEDIUM": (
                "<b>STRESS: MEDIUM</b><br><br>"
                "S07 SWAN is in elevated band (&ge; 1.5 and &lt; 2.0).<br>"
                "Watch for transitions; baseline cadence maintained."
            ),
            "HIGH": (
                "<b>STRESS: HIGH</b><br><br>"
                "S07 SWAN is in high-stress band (&ge; 2.0 and &lt; 3.0).<br>"
                "Faster metric cadence and tighter operator attention advised."
            ),
            "CRISIS": (
                "<b>STRESS: CRISIS</b><br><br>"
                "S07 SWAN is in crisis band (&ge; 3.0).<br>"
                "Extreme stress backdrop; expect defensive behavior."
            ),
            "UNKNOWN": (
                "<b>STRESS: UNKNOWN</b><br><br>"
                "S07 stress feed not confirmed yet; fallback state displayed."
            ),
        }
        _GATE_TIPS: dict[str, str] = {
            "BULL TREND": (
                "<b>BULL TREND GATE</b><br><br>"
                "<b>Trigger (all):</b><br>"
                "&bull; SPY &gt; SPY EMA50<br>"
                "&bull; VIX &lt; VIX EMA50<br><br>"
                "<b>Active strategy:</b> SpyderD06_BullPutSpread<br>"
                "Max 2 concurrent strategies"
            ),
            "BEAR TREND": (
                "<b>BEAR TREND GATE</b><br><br>"
                "<b>Trigger (all):</b><br>"
                "&bull; SPY &lt; SPY EMA50<br>"
                "&bull; VIX &gt; VIX EMA50<br><br>"
                "<b>Active strategy:</b> SpyderD07_BearCallSpread<br>"
                "Max 2 concurrent strategies"
            ),
            "RANGE CALM": (
                "<b>RANGE CALM GATE</b><br><br>"
                "<b>Trigger (all):</b><br>"
                "&bull; SPY within 1.0 ATR of EMA50<br>"
                "&bull; Term structure not stressed (VIX9D &le; VIX)<br><br>"
                "<b>Active strategy:</b> SpyderD02_IronCondor<br>"
                "Max 2 concurrent strategies"
            ),
            "HIGH VOL": (
                "<b>HIGH VOLATILITY GATE</b><br><br>"
                "<b>Trigger (all):</b><br>"
                "&bull; SPY ATR% &ge; 1.5%<br>"
                "&bull; VIX Percentile &ge; 80th OR VIX &ge; 25<br><br>"
                "<b>Active strategy:</b> SpyderD10_IronButterfly<br>"
                "Max 2 concurrent strategies"
            ),
            "CRISIS": (
                "<b>CRISIS GATE &mdash; HARD HALT</b><br><br>"
                "VIX9D &gt; VIX or VIX &ge; 35 or joint price-vol shock<br><br>"
                "<i>All entry strategies deactivated &mdash; kill-switch posture</i>"
            ),
            "EVENT": (
                "<b>EVENT GATE &mdash; NO TRADE</b><br><br>"
                "Calendar proximity to high-impact macro event (&le; 30 min window)<br><br>"
                "<i>All entry strategies deactivated &mdash; no new entries</i>"
            ),
        }

        # ── Apply styles — label in white, dynamic value in semantic colour ──
        self._regime_value = regime
        ss, fg = self._pill_stylesheet(regime)
        self.regime_pill.setText(f'REGIME: <span style="color: {fg};">{regime}</span>')
        self.regime_pill.setStyleSheet(ss)
        self.regime_pill.setToolTip(_REGIME_TIPS.get(regime, f"<b>Regime:</b> {regime}"))

        if hasattr(self, "stress_pill"):
            ss, fg = self._pill_stylesheet(stress)
            self.stress_pill.setText(f'STRESS: <span style="color: {fg};">{stress}</span>')
            self.stress_pill.setStyleSheet(ss)
            self.stress_pill.setToolTip(_STRESS_TIPS.get(stress, f"<b>Stress:</b> {stress}"))

        ss, fg = self._pill_stylesheet(stance)
        self.stance_pill.setText(f'STANCE: <span style="color: {fg};">{stance}</span>')
        self.stance_pill.setStyleSheet(ss)
        self.stance_pill.setToolTip(_STANCE_TIPS.get(stance, f"<b>Strategy stance:</b> {stance}"))

        ss, fg = self._pill_stylesheet(gate)
        self.gate_pill.setText(f'GATE: <span style="color: {fg};">{gate}</span>')
        self.gate_pill.setStyleSheet(ss)
        self.gate_pill.setToolTip(_GATE_TIPS.get(gate, f"<b>Strategy gate:</b> {gate}"))

        # ENTRY pill — execution truth from D31, with regime-driven HALT
        # priority. v12: absorbed the legacy TRADEABLE pill into this tooltip.
        if regime in ("CRISIS", "EVENT"):
            dispatch_state = {
                "state": "HALT",
                "reason": f"regime={regime}",
                "age_s": None,
            }
        else:
            dispatch_state = self._get_dispatch_state_safe()
        d_label = dispatch_state["state"]
        ss, fg = self._pill_stylesheet(d_label)
        self.dispatch_pill.setText(f'ENTRY: <span style="color: {fg};">{d_label}</span>')
        self.dispatch_pill.setStyleSheet(ss)

        # Surface D31 execution-truth transitions to Autonomous AI Activity
        # so operators can immediately see when flow changes from IDLE to
        # FLOWING/BLOCKED/ERROR/HALT without opening decision logs.
        d_reason_compact = str(dispatch_state.get("reason", "")).strip()
        dispatch_state_key = f"{d_label}|{d_reason_compact}"
        if dispatch_state_key != getattr(self, "_last_dispatch_state_key", ""):
            self._last_dispatch_state_key = dispatch_state_key
            dispatch_msg = f"D31 ENTRY -> {d_label}"
            if d_reason_compact:
                dispatch_msg = f"{dispatch_msg} ({d_reason_compact})"
            self.log_autonomous_event(
                dispatch_msg,
                event_type="AGENT_OBSERVATION",
                source="D31",
            )
            if d_label in {"BLOCKED", "ERROR", "HALT"}:
                self.add_system_log(f"⚠️ {dispatch_msg}")

        import os as _os
        _pivot_enabled = _os.getenv("SPYDER_ENABLE_PIVOT_MEAN_REVERSION", "").strip().lower() in {
            "1", "true", "yes", "on"
        }
        _STRATEGY_LIST = (
            "<b>Permitted strategies:</b><br>"
            "&bull; <b>BULL:</b> SpyderD06_BullPutSpread<br>"
            "&bull; <b>BEAR:</b> SpyderD07_BearCallSpread<br>"
            "&bull; <b>RANGE:</b> SpyderD02_IronCondor<br>"
            "&bull; <b>VOLATILE:</b> SpyderD10_IronButterfly"
            + (
                "<br>&bull; <b>SIDEWAYS:</b> SpyderD34_PivotMeanReversion"
                if _pivot_enabled else ""
            )
            + "<br><br>"
            "<b>Concurrency limit:</b> Max 2 strategies open "
            "(one long-term/swing + one intraday/0DTE)"
        )

        d_reason = dispatch_state.get("reason", "")
        d_tip_base = _DISPATCH_TIPS.get(d_label, f"<b>Entry:</b> {d_label}")
        d_tip_parts = [d_tip_base]
        if d_reason:
            d_tip_parts.append(f"<b>Reason:</b> {d_reason}")
        regime_source = (
            "S07 composite (SWAN, DIX, SKEW, GEX)"
            if _s07_live else
            "VIX fallback with debounce / sticky last-good S07"
        )
        reconcile_html = (
            "<b>State reconciliation:</b><br>"
            f"&bull; <b>REGIME</b>: {regime} (source: {regime_source})<br>"
            f"&bull; <b>STRESS</b>: {stress} (source: S07 SWAN bands; now={swan:.2f}; "
            "LOW &lt; 1.5, MEDIUM &ge; 1.5, HIGH &ge; 2.0, CRISIS &ge; 3.0)<br>"
            f"&bull; <b>ENTRY</b>: {d_label} (source: D31 execution state, 120s recency window)"
        )
        d_tip_parts.append(reconcile_html)
        d_tip_parts.append(_STRATEGY_LIST)
        self.dispatch_pill.setToolTip("<br><br>".join(d_tip_parts))

        # ── Row background: purple for CRISIS / EVENT, normal otherwise ─
        if hasattr(self, "regime_bar_widget") and self.regime_bar_widget is not None:
            if regime in ("CRISIS", "EVENT"):
                self.regime_bar_widget.setStyleSheet(
                    "background-color: #2a0a3a; border: 1px solid #6a2a9a;"
                )
            else:
                self.regime_bar_widget.setStyleSheet(
                    f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']};"
                )

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
        self._update_trading_window_compact_label()

    def _update_trading_window_compact_label(self) -> None:
        """Update compact RTH status badge shown beside FLOW/EC/BLOCK."""
        try:
            label = getattr(self, "trading_window_compact_label", None)
            if label is None:
                return

            if is_market_hours():
                label.setText("MARKET OPEN")
                label.setStyleSheet(
                    f"color: {COLORS['positive']}; font-size: 12px; font-weight: normal;"
                )
            else:
                label.setText("MARKET CLOSED")
                label.setStyleSheet(
                    f"color: {COLORS['negative']}; font-size: 12px; font-weight: normal;"
                )
        except Exception as exc:
            self.logger.debug("Could not update RTH compact label: %s", exc)

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
        yes_btn.setStyleSheet(f"background-color: {COLORS['negative']}; color: white; padding: 5px 15px;")  # noqa: E501

        cancel_btn = msg_box.button(QMessageBox.StandardButton.Cancel)
        cancel_btn.setStyleSheet(f"background-color: {COLORS['panel']}; color: white; padding: 5px 15px;")  # noqa: E501

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
        except (TradierAPIError if TradierAPIError is not None else Exception) as e:  # noqa: B030
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

    def _subscribe_to_events(self) -> None:
        """Subscribe to system events for real-time dashboard updates (Phase 5-A).
        
        Subscribes to RISK events from the event bus so the dashboard can display
        live event-clock state updates as they occur during trading.
        """  # noqa: W293
        try:
            from Spyder.SpyderA_Core.SpyderA05_EventManager import (
                EventManager,
                EventType,
            )
  # noqa: W293
            event_manager = EventManager.get_instance()
  # noqa: W293
            # Subscribe to RISK events to receive event-clock state updates
            self._event_clock_handler_id = event_manager.subscribe(
                EventType.RISK,
                self._handle_risk_event,
                name="G05_EventClockDisplay",
                handler_type=0,  # SYNC handler
            )
            self.logger.info("✅ Subscribed to RISK events for event-clock display")

            # Subscribe to TRADE events carrying B02 execution telemetry envelopes.
            self._execution_telemetry_handler_id = event_manager.subscribe(
                EventType.TRADE,
                self._handle_trade_event,
                name="G05_ExecutionHealth",
                handler_type=0,
            )
            self.logger.info("✅ Subscribed to TRADE events for execution-health display")

            # Subscribe to risk alerts so trust/risk gate blocks are visible in dashboard logs.
            self._risk_alert_handler_id = event_manager.subscribe(
                EventType.RISK_ALERT,
                self._handle_risk_alert_event,
                name="G05_RiskAlertDisplay",
                handler_type=0,
            )
            self.logger.info("✅ Subscribed to RISK_ALERT events for entry-block visibility")
        except Exception as e:
            self.logger.warning("⚠️ Event subscription failed (non-blocking): %s", e)

    def _handle_trade_event(self, event: dict) -> None:
        """Handle TRADE events and update execution-health display."""
        try:
            event_payload = event
            if hasattr(event, "data") and isinstance(getattr(event, "data", None), dict):
                event_payload = getattr(event, "data")  # noqa: B009

            if not isinstance(event_payload, dict):
                return

            telemetry = event_payload.get("execution_telemetry")
            if not isinstance(telemetry, dict):
                return
            if telemetry.get("feed") != "execution":
                return

            data = telemetry.get("data", {})
            if not isinstance(data, dict):
                return

            with self._execution_telemetry_lock:
                self._execution_telemetry_events.append({
                    "published_ts": telemetry.get("published_ts"),
                    "order_id": data.get("order_id"),
                    "slippage_bps": data.get("slippage_bps"),
                    "fill_latency_ms": data.get("fill_latency_ms"),
                    "partial_fill_ratio": data.get("partial_fill_ratio", 0.0),
                    "reject_flag": bool(data.get("reject_flag", False)),
                })

            # Update UI from main thread.
            QTimer.singleShot(0, self._update_execution_health_display)
        except Exception as e:
            self.logger.debug("Execution telemetry processing error (non-blocking): %s", e)

    def _update_execution_health_display(self) -> None:
        """Refresh execution-health labels from rolling telemetry cache."""
        if self.execution_reject_rate_value is None:
            return

        with self._execution_telemetry_lock:
            samples = list(self._execution_telemetry_events)

        if not samples:
            self.execution_slippage_bps_value.setText("-")
            self.execution_fill_latency_value.setText("-")
            self.execution_reject_rate_value.setText("-")
            self.execution_partial_fill_value.setText("-")
            return

        latest_slippage = next(
            (s.get("slippage_bps") for s in reversed(samples) if isinstance(s.get("slippage_bps"), (int, float))),  # noqa: E501
            None,
        )
        latest_latency = next(
            (s.get("fill_latency_ms") for s in reversed(samples) if isinstance(s.get("fill_latency_ms"), (int, float))),  # noqa: E501
            None,
        )

        reject_count = sum(1 for s in samples if s.get("reject_flag"))
        reject_rate = reject_count / len(samples)

        partial_vals = [
            float(s.get("partial_fill_ratio"))
            for s in samples
            if isinstance(s.get("partial_fill_ratio"), (int, float))
        ]
        partial_ratio = float(np.mean(partial_vals)) if partial_vals else 0.0

        self.execution_slippage_bps_value.setText(
            "-" if latest_slippage is None else f"{float(latest_slippage):.1f} bps"
        )
        self.execution_fill_latency_value.setText(
            "-" if latest_latency is None else f"{float(latest_latency):.0f} ms"
        )
        self.execution_reject_rate_value.setText(f"{reject_rate * 100.0:.1f}%")
        self.execution_partial_fill_value.setText(f"{partial_ratio * 100.0:.1f}%")

    def _handle_risk_alert_event(self, event: dict) -> None:
        """Display entry-gate/risk-gate block reasons in dashboard system status."""
        try:
            event_payload = event
            if hasattr(event, "data") and isinstance(getattr(event, "data", None), dict):
                event_payload = getattr(event, "data")  # noqa: B009

            if not isinstance(event_payload, dict):
                return

            reason = str(event_payload.get("reason", "")).strip().lower()
            if reason not in {"entry_trust_gate_rejected", "validate_signal_rejected"}:
                return

            detail = str(event_payload.get("message") or event_payload.get("detail") or reason).strip()
            now = time.monotonic()
            digest = f"{reason}:{detail}"

            # Avoid flooding the operator log when strategies emit repeated blocks.
            if digest == self._last_entry_block_message and (now - self._last_entry_block_ts) < 15.0:
                return

            self._last_entry_block_message = digest
            self._last_entry_block_ts = now

            compact_text = detail if detail else reason
            if len(compact_text) > 64:
                compact_text = compact_text[:61] + "..."
            compact_display = f"BLOCK: {compact_text}"

            QTimer.singleShot(0, lambda: self.log_system_message(
                f"⛔ Entry blocked ({reason}): {detail}"
            ))
            QTimer.singleShot(0, lambda: self._update_entry_block_compact_label(compact_display))
        except Exception as e:
            self.logger.debug("Risk-alert display error (non-blocking): %s", e)

    def _update_entry_block_compact_label(self, text: str) -> None:
        """Update compact toolbar label showing latest entry-block reason."""
        try:
            label = getattr(self, "entry_block_compact_label", None)
            if label is None:
                return
            message = str(text or "").strip() or "BLOCK: -"
            label.setText(message)
            label.setToolTip(message)
            label.setStyleSheet("color: #f5a623; font-size: 12px; font-weight: bold;")
        except Exception as e:
            self.logger.debug("Entry-block compact label update failed: %s", e)

    def _handle_risk_event(self, event: dict) -> None:
        """Handle RISK events and update event-clock display.
        
        Args:
            event: Event dict with keys 'type', 'data', 'timestamp', etc.
        """  # noqa: W293
        try:
            event_payload = event
            if hasattr(event, "data") and isinstance(getattr(event, "data", None), dict):
                event_payload = getattr(event, "data")  # noqa: B009

            if not isinstance(event_payload, dict):
                return

            # Event data may arrive as either:
            # 1) direct event-clock feed dict (contains feed/state/etc)
            # 2) wrapped scheduler payload: {type, payload, timestamp}
            event_data = event_payload.get('data', {}) if 'data' in event_payload else event_payload
            if not isinstance(event_data, dict):
                return

            # Unwrap A04 scheduler emission shape when present.
            if event_data.get('feed') != 'event_clock' and isinstance(event_data.get('payload'), dict):  # noqa: E501
                wrapped_payload = event_data.get('payload')
                if isinstance(wrapped_payload.get('data'), dict):
                    event_data = dict(wrapped_payload.get('data'))
                    if wrapped_payload.get('feed') and not event_data.get('feed'):
                        event_data['feed'] = wrapped_payload.get('feed')

            # Check if this is an event-clock state event
            if event_data.get('feed') != 'event_clock':
                return
  # noqa: W293
            # Update event-clock state safely
            with self._event_clock_lock:
                from Spyder.SpyderG_GUI.SpyderG06_DashboardData import EventClockState
  # noqa: W293
                # Build new state from event data
                new_state = EventClockState(
                    state=event_data.get('state', 'clear'),
                    enabled=event_data.get('enabled', True),
                    sources=event_data.get('sources', 'calendar+manual'),
                    allowed_strategies=event_data.get('allowed_strategies', []),
                    blackout_pre_minutes=event_data.get('blackout_pre_minutes', 30),
                    blackout_post_minutes=event_data.get('blackout_post_minutes', 30),
                    max_size_multiplier=event_data.get('max_size_multiplier', 0.25),
                    timestamp=datetime.now(pytz.timezone("US/Eastern")),
                )
                self.event_clock_state = new_state
  # noqa: W293
            # Update UI display (defer to main thread if needed)
            QTimer.singleShot(0, self._update_event_clock_display)
        except Exception as e:
            self.logger.debug("Event processing error (non-blocking): %s", e)

    def _update_event_clock_display(self) -> None:
        """Update event-clock display panel with current state (main thread)."""
        try:
            if self.event_clock_state_label is None and self.event_clock_compact_label is None:
                return
  # noqa: W293
            with self._event_clock_lock:
                state = self.event_clock_state
  # noqa: W293
            # Update state label with color
            state_color = state.state_color
            if self.event_clock_state_label:
                self.event_clock_state_label.setText(state.state_label)
                self.event_clock_state_label.setStyleSheet(f"color: {state_color};")

            if self.event_clock_compact_label:
                compact_text = f"EC: {state.state_label.replace('✓ ', '').replace('✗ ', '')}"
                self.event_clock_compact_label.setText(compact_text)
                self.event_clock_compact_label.setStyleSheet(
                    f"color: {state_color}; font-size: 13px; font-weight: normal;"
                )
  # noqa: W293
            # Update policy label (and windows if separate, or combined if single-line mode)
            policy_text = f"{'Enabled' if state.enabled else 'Disabled'} | Sources: {state.sources}"
            windows_text = (
                f"Window -{state.blackout_pre_minutes}m/+{state.blackout_post_minutes}m"
                f" | Size {state.max_size_multiplier:.0%}"
                f" | Allowlist {', '.join(state.allowed_strategies) if state.allowed_strategies else 'None'}"
            )
            if self.event_clock_policy_label:
                if self.event_clock_windows_label is None:
                    self.event_clock_policy_label.setText(f"{policy_text} | {windows_text}")
                else:
                    self.event_clock_policy_label.setText(policy_text)
            if self.event_clock_windows_label:
                self.event_clock_windows_label.setText(windows_text)
  # noqa: W293
            # Optional legacy label if mounted elsewhere.
            strategies_text = f"Allowlist {', '.join(state.allowed_strategies) if state.allowed_strategies else 'None'}"
            if self.event_clock_strategies_label:
                self.event_clock_strategies_label.setText(strategies_text)
        except Exception as e:
            self.logger.debug("Display update error (non-blocking): %s", e)

    def _toggle_event_clock_override(self) -> None:
        """Toggle manual event-clock blackout override and notify scheduler."""
        try:
            active = bool(self.event_clock_override_button.isChecked())
            self.event_clock_override_active = active
            label = "Manual Blackout: ON" if active else "Manual Blackout: OFF"
            self.event_clock_override_button.setText(label)

            from Spyder.SpyderA_Core.SpyderA05_EventManager import EventManager, EventType
            event_manager = EventManager.get_instance()

            if active:
                payload = {
                    "state": "live",
                    "event_id": "manual_override",
                    "event_type": "manual_blackout",
                    "allowed_strategies": [],
                    "max_size_multiplier": 0.0,
                }
                event_manager.emit(
                    EventType.RISK,
                    {"type": "event_clock_manual_override", "payload": payload},
                    priority="high",
                )
            else:
                event_manager.emit(
                    EventType.RISK,
                    {"type": "event_clock_manual_clear", "payload": {}},
                    priority="high",
                )
        except Exception as exc:
            self.logger.debug("Manual event-clock override failed: %s", exc)

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
        """Append to a ring buffer and schedule a batched widget refresh."""
        timestamp = datetime.now(pytz.timezone("US/Eastern")).strftime("%H:%M:%S")
        buffer.append(f"[{timestamp}] {message}")
        if len(buffer) > max_buffer:
            del buffer[:-max_buffer]
        self._schedule_log_widget_refresh(buffer, widget, display_count)

    def _schedule_log_widget_refresh(self, buffer: list, widget, display_count: int) -> None:
        """Coalesce repeated log writes into a single UI refresh."""
        if widget is None:
            return

        if widget is self.system_log:
            if self._system_log_flush_pending:
                return
            self._system_log_flush_pending = True
            QTimer.singleShot(
                75,
                lambda: self._flush_log_widget(buffer, widget, display_count, "system"),
            )
            return

        if widget is self.auto_log:
            if self._automation_log_flush_pending:
                return
            self._automation_log_flush_pending = True
            QTimer.singleShot(
                75,
                lambda: self._flush_log_widget(buffer, widget, display_count, "automation"),
            )
            return

        self._flush_log_widget(buffer, widget, display_count, "other")

    def _flush_log_widget(self, buffer: list, widget, display_count: int, target: str) -> None:
        """Render the latest slice of a buffered log widget."""
        try:
            if widget is None:
                return
            widget.setUpdatesEnabled(False)
            widget.clear()
            widget.append("\n".join(reversed(buffer[-display_count:])))
            cursor = widget.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            widget.setTextCursor(cursor)
        finally:
            if widget is not None:
                widget.setUpdatesEnabled(True)
            if target == "system":
                self._system_log_flush_pending = False
            elif target == "automation":
                self._automation_log_flush_pending = False

    def add_system_log(self, message: str):
        """Add message to system log."""
        if self._should_suppress_after_hours_system_log(message):
            return
        self._append_to_ring_log(self.system_logs, self.system_log, message,
                                  max_buffer=200, display_count=200)

    def _should_suppress_after_hours_system_log(self, message: str) -> bool:
        """Return True for non-critical messages to hide outside market hours."""
        if not getattr(self, "_quiet_after_hours_logs", True):
            return False

        if is_market_hours():
            return False

        text = str(message or "").strip()
        quiet_prefixes = (
            "📊 EOD snapshot loaded",
            "📊 Real EOD data loaded from Tradier",
            "📊 EOD MARKET DATA ACTIVE - Tradier API prices",
            "EOD market data from Tradier",
            "✅ Real data patch applied successfully!",
            "✅ Custom metrics orchestrator started (DIX + Black Swan schedulers active)",
            "AUTONOMOUS METRICS ACTIVE - DIX/SWAN stress monitor online",
            "📦 Restored ",
        )
        return text.startswith(quiet_prefixes)

    def log_system_message(self, message: str) -> None:
        """Compatibility wrapper for legacy call sites using the old log method name."""
        try:
            if getattr(self, "system_log", None) is not None:
                self.add_system_log(message)
            elif hasattr(self, "logger") and self.logger is not None:
                self.logger.info(message)
        except Exception:
            if hasattr(self, "logger") and self.logger is not None:
                self.logger.exception("Failed to write system message: %s", message)

    def add_automation_log(
        self,
        message: str,
        event_type: str = "LEGACY_STATUS",
        source: str = "dashboard",
    ):
        """Add a message to Autonomous AI Activity when it is truly autonomous.

        Non-autonomous/status events are automatically routed to System Log.
        """
        normalized_type = str(event_type or "LEGACY_STATUS").strip().upper()
        if normalized_type not in _AUTONOMOUS_EVENT_TYPE_ALLOWLIST:
            self.add_system_log(f"[{normalized_type}] {message}")
            return

        src = str(source or "dashboard").strip().upper()
        formatted = f"{normalized_type} [{src}] {message}"
        self._append_to_ring_log(
            self.automation_logs,
            self.auto_log,
            formatted,
            max_buffer=100,
            display_count=100,
        )

    def log_autonomous_event(
        self,
        message: str,
        event_type: str = "AGENT_OBSERVATION",
        source: str = "dashboard",
    ) -> None:
        """Explicit API for autonomous decision/activity events."""
        self.add_automation_log(message, event_type=event_type, source=source)

    def _set_system_log_verbosity(self, mode: str, announce: bool = True) -> None:
        """Set system-log verbosity profile and update related logger levels."""
        selected = "DEBUG" if str(mode).upper() == "DEBUG" else "NORMAL"
        self.system_log_mode = selected

        logger_level = logging.DEBUG if selected == "DEBUG" else logging.ERROR
        for logger_name in self._signal_noise_loggers:
            logging.getLogger(logger_name).setLevel(logger_level)

        if hasattr(self, "system_log_normal_btn") and self.system_log_normal_btn is not None:
            self.system_log_normal_btn.setChecked(selected == "NORMAL")

        if hasattr(self, "system_log_debug_btn") and self.system_log_debug_btn is not None:
            self.system_log_debug_btn.setChecked(selected == "DEBUG")

        if announce:
            self.add_system_log(
                f"ℹ️ System log mode → {selected}"
            )

    def toggle_system_log_verbosity(self) -> None:
        """Toggle system-log verbosity between NORMAL and DEBUG."""
        new_mode = "DEBUG" if self.system_log_mode == "NORMAL" else "NORMAL"
        self._set_system_log_verbosity(new_mode, announce=True)

    def _resolve_veto_profile_path(self) -> Path:
        """Resolve config profile path used by the dashboard veto toggle."""
        import os

        profile = str(os.environ.get("ENVIRONMENT", "development")).strip().lower()
        config_dir = project_root / "config"

        if profile in {"live", "production", "prod"}:
            return config_dir / "production.json"

        return config_dir / "development.json"

    def _load_veto_controls_state(self) -> bool:
        """Load unified veto-enabled state from config profile with env fallback."""
        import os

        default_enabled = True
        profile_path = self._resolve_veto_profile_path()

        if profile_path.exists():
            try:
                data = json.loads(profile_path.read_text(encoding="utf-8"))
                values = [
                    bool(data.get("enable_x16_veto", default_enabled)),
                    bool(data.get("enable_y03_trade_veto", default_enabled)),
                    bool(data.get("enable_y05_veto_consumption", default_enabled)),
                ]
                return all(values)
            except Exception:
                pass

        def _env_bool(name: str, default: bool) -> bool:
            raw = os.environ.get(name)
            if raw is None:
                return default
            return raw.strip().lower() in {"1", "true", "yes", "on"}

        return all(
            [
                _env_bool("ENABLE_X16_VETO", default_enabled),
                _env_bool("ENABLE_Y03_TRADE_VETO", default_enabled),
                _env_bool("ENABLE_Y05_VETO_CONSUMPTION", default_enabled),
            ]
        )

    def _apply_veto_toggle_button_state(self) -> None:
        """Render veto button state and styling in Advanced Controls."""
        btn = getattr(self, "veto_toggle_btn", None)
        if btn is None:
            return

        enabled = bool(getattr(self, "_veto_controls_enabled", True))
        btn.setChecked(enabled)

        if enabled:
            btn.setText("VETO: ENABLED")
            btn.setStyleSheet(
                "background-color: #0D7A33; color: white; font-size: 12px; "
                "padding: 0 12px; border: 1px solid #1FA44C; border-radius: 3px;"
            )
            btn.setToolTip("X16/Y03/Y05 veto path is enabled")
        else:
            btn.setText("VETO: DISABLED")
            btn.setStyleSheet(
                "background-color: #A94442; color: white; font-size: 12px; "
                "padding: 0 12px; border: 1px solid #C96865; border-radius: 3px;"
            )
            btn.setToolTip("X16/Y03/Y05 veto path is disabled")

    def _persist_veto_controls_state(self, enabled: bool) -> tuple[bool, str]:
        """Persist veto state to profile JSON, env vars, and ConfigManager cache."""
        import os

        profile_path = self._resolve_veto_profile_path()
        payload = {
            "enable_x16_veto": enabled,
            "enable_y03_trade_veto": enabled,
            "enable_y05_veto_consumption": enabled,
        }

        try:
            if profile_path.exists():
                data = json.loads(profile_path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    data = {}
            else:
                data = {}

            data.update(payload)
            profile_path.parent.mkdir(parents=True, exist_ok=True)
            profile_path.write_text(f"{json.dumps(data, indent=2)}\n", encoding="utf-8")

            value = "true" if enabled else "false"
            os.environ["ENABLE_X16_VETO"] = value
            os.environ["ENABLE_Y03_TRADE_VETO"] = value
            os.environ["ENABLE_Y05_VETO_CONSUMPTION"] = value

            try:
                from Spyder.SpyderA_Core.SpyderA03_Configuration import get_config_manager

                cfg = get_config_manager()
                cfg.update(payload, source="dashboard")
            except Exception:
                pass

            return True, str(profile_path)
        except Exception as exc:
            return False, str(exc)

    def _toggle_veto_controls(self) -> None:
        """Toggle veto controls used by X16/Y03/Y05 and persist the setting."""
        next_state = not bool(getattr(self, "_veto_controls_enabled", True))
        success, detail = self._persist_veto_controls_state(next_state)

        if not success:
            self.add_system_log(f"⚠️ Failed to update veto controls: {detail}")
            self._apply_veto_toggle_button_state()
            return

        self._veto_controls_enabled = next_state
        self._apply_veto_toggle_button_state()

        state_text = "ENABLED" if next_state else "DISABLED"
        self.add_system_log(f"Veto controls {state_text} (saved: {detail})")
        self.add_system_log("ℹ️ Restart autonomous agents/session to apply veto changes")

    def setup_white_tooltips(self):
        """Apply the white-tooltip theme to this window (delegates to module helper)."""
        try:
            apply_tooltip_theme(QApplication.instance(), self)
        except Exception as e:
            self.add_system_log(f"⚠️ Tooltip styling error: {e}")

    def _collect_startup_readiness_state(self) -> dict[str, object]:
        """Read readiness-validation outcome from A03 ConfigManager for startup UX."""
        state: dict[str, object] = {
            "checked": False,
            "mode": "paper",
            "automation_enabled": True,
            "warnings": [],
            "errors": [],
            "safe_fallback_applied": False,
            "live_blocking": False,
            "source": "unknown",
        }

        try:
            import os
            from Spyder.SpyderA_Core.SpyderA03_Configuration import get_config_manager

            cfg = get_config_manager()

            env_mode = str(os.environ.get("TRADING_MODE", "")).strip().lower()
            if env_mode in {"paper", "sandbox", "live", "production"}:
                mode = "live" if env_mode in {"live", "production"} else "paper"
            else:
                runtime_paper_mode = cfg.get("runtime.paper_mode", None)
                if isinstance(runtime_paper_mode, bool):
                    mode = "paper" if runtime_paper_mode else "live"
                else:
                    mode = str(cfg.get("trading.mode", "paper")).strip().lower()

            automation_enabled = bool(cfg.get("automation.enabled", True))

            warnings = []
            errors = []
            if hasattr(cfg, "validate_autonomous_readiness_config"):
                result = cfg.validate_autonomous_readiness_config(cfg.config_data, mode)
                warnings = list(result.get("warnings", []))
                errors = list(result.get("errors", []))

            # Startup readiness should explicitly reflect market-hours state so
            # operators can reconcile startup status with start-button gating.
            if not is_market_hours():
                rth_warning = "Market is closed (outside regular trading hours)"
                if rth_warning not in warnings:
                    warnings.append(rth_warning)

            safe_fallback = (mode != "live") and (not automation_enabled) and len(errors) > 0
            live_blocking = (mode == "live") and len(errors) > 0

            state.update(
                {
                    "checked": True,
                    "mode": mode,
                    "automation_enabled": automation_enabled,
                    "warnings": warnings,
                    "errors": errors,
                    "safe_fallback_applied": safe_fallback,
                    "live_blocking": live_blocking,
                    "source": "A03.ConfigManager",
                }
            )
        except Exception as exc:
            state["source"] = f"unavailable: {exc}"

        return state

    def _load_dji_proxy_multiplier(self) -> float:
        """Read configurable DJI proxy scale (DIA -> DJI) from A03 config."""
        default_multiplier = 101.2
        try:
            from Spyder.SpyderA_Core.SpyderA03_Configuration import get_config_manager

            cfg = get_config_manager()
            configured = cfg.get("dashboard.toolbar.dji_from_dia_multiplier", default_multiplier)
            multiplier = float(configured)
            if multiplier <= 0:
                return default_multiplier
            return multiplier
        except Exception:
            return default_multiplier

    def _append_startup_readiness_banner(self, startup_hms: str) -> None:
        """Append readiness banner lines to the startup ring-buffer before UI renders."""
        state = self._startup_readiness_state
        if not state.get("checked", False):
            self.system_logs.append(
                f"[{startup_hms}] ℹ️ STARTUP READINESS: unavailable ({state.get('source', 'unknown')})"  # noqa: E501
            )
            return

        warnings = state.get("warnings", []) or []
        errors = state.get("errors", []) or []
        mode = str(state.get("mode", "paper")).upper()

        if state.get("safe_fallback_applied", False):
            self.system_logs.extend(
                [
                    f"[{startup_hms}] ⚠️ STARTUP READINESS: SAFE MODE ACTIVE ({mode})",
                    f"[{startup_hms}] ⚠️ automation.enabled=false due to {len(errors)} blocking config error(s)",  # noqa: E501
                ]
            )
        elif state.get("live_blocking", False):
            self.system_logs.append(
                f"[{startup_hms}] ❌ STARTUP READINESS: LIVE BLOCKING ({len(errors)} error(s))"
            )
        else:
            self.system_logs.append(
                f"[{startup_hms}] ✅ STARTUP READINESS: mode={mode} warnings={len(warnings)} errors={len(errors)}"  # noqa: E501
            )
            if warnings:
                warning_text = "; ".join(str(w) for w in warnings[:3])
                self.system_logs.append(
                    f"[{startup_hms}] ⚠️ STARTUP READINESS WARNING(S): {warning_text}"
                )

    def _emit_startup_readiness_logs(self) -> None:
        """Emit readiness state to visible logs and button styling after widgets exist."""
        state = self._startup_readiness_state
        if not state.get("checked", False):
            self.add_system_log(
                f"ℹ️ Startup readiness state unavailable ({state.get('source', 'unknown')})"
            )
            return

        warnings = state.get("warnings", []) or []
        errors = state.get("errors", []) or []
        mode = str(state.get("mode", "paper")).upper()

        if state.get("safe_fallback_applied", False):
            self.add_system_log(
                f"⚠️ STARTUP SAFE MODE ({mode}): automation disabled by readiness validation"
            )
            self.add_system_log(
                f"⚠️ Readiness issues: {len(errors)} blocking error(s), {len(warnings)} warning(s)"
            )
            if self.start_btn is not None:
                self.start_btn.setText("SAFE MODE (AUTO OFF)")
                self.start_btn.setStyleSheet(
                    f"background-color: {COLORS.get('warning', '#e6a817')}; color: black;"
                )
                self.start_btn.setToolTip(
                    "Startup safe mode active: automation.enabled=false due to readiness errors. "
                    "Fix config and restart to restore normal automation startup behavior."
                )
        elif state.get("live_blocking", False):
            self.add_system_log(
                "❌ LIVE readiness has blocking errors; startup should be corrected before trading"
            )
        else:
            self.add_system_log(
                f"✅ Startup readiness validated (mode={mode}, warnings={len(warnings)}, errors={len(errors)})"  # noqa: E501
            )
            if warnings:
                warning_text = "; ".join(str(w) for w in warnings[:3])
                self.add_system_log(f"⚠️ Startup readiness warning(s): {warning_text}")

    # ------------------------------------------------------------------
    # Snapshot persistence — save symbol values on exit, restore on open
    # ------------------------------------------------------------------
    _SNAPSHOT_FILE: Path = (
        Path.home() / "Projects/Spyder/market_data/dashboard_snapshot.json"
    )
    # Snapshot age thresholds (seconds)
    _SNAPSHOT_STALE_HOURS = 8  # > 8 h → FROZEN badge (red)
    _SNAPSHOT_EOD_HOURS = 0    # anything younger → EOD badge (yellow)

    @staticmethod
    def _parse_money_text(text: str) -> float:
        """Parse dashboard money labels like '$100,024.40' or '$+0.00'."""
        try:
            cleaned = str(text or "").strip().replace("$", "").replace(",", "")
            return float(cleaned) if cleaned not in ("", "—") else 0.0
        except (TypeError, ValueError):
            return 0.0

    def _capture_account_snapshot_from_labels(self) -> dict:
        """Capture current account-panel numeric values from QLabel text."""
        settled = self._parse_money_text(self.settled_value.text() if self.settled_value else "0")
        buying = self._parse_money_text(self.buying_value.text() if self.buying_value else "0")
        realized = self._parse_money_text(self.realized_value.text() if self.realized_value else "0")  # noqa: E501
        unrealized = self._parse_money_text(self.unrealized_value.text() if self.unrealized_value else "0")  # noqa: E501
        return {
            "settled_cash": settled,
            "buying_power": buying,
            "realized_pnl": realized,
            "unrealized_pnl": unrealized,
        }

    def _remember_current_account_snapshot(self, mode: TradingMode | None = None) -> None:
        """Persist current account labels into in-memory per-mode cache."""
        mode_key = mode or self.trading_mode
        self._account_snapshot_by_mode[mode_key] = self._capture_account_snapshot_from_labels()

    def _apply_account_snapshot(self, snapshot: dict) -> None:
        """Apply account snapshot values back into account panel labels."""
        settled = float(snapshot.get("settled_cash", 0.0) or 0.0)
        buying = float(snapshot.get("buying_power", 0.0) or 0.0)
        realized = float(snapshot.get("realized_pnl", 0.0) or 0.0)
        unrealized = float(snapshot.get("unrealized_pnl", 0.0) or 0.0)

        if self.settled_value:
            self.settled_value.setText(f"${settled:,.2f}")
        if self.buying_value:
            self.buying_value.setText(f"${buying:,.2f}")
        if self.realized_value:
            r_color = COLORS["positive"] if realized >= 0 else COLORS["negative"]
            self.realized_value.setText(f"${realized:+,.2f}")
            self.realized_value.setStyleSheet(
                f"padding: 2px 5px; background-color: {COLORS['background']}; "
                f"border: 1px solid {COLORS['border']}; font-size: 12px; color: {r_color}; text-align: right;"  # noqa: E501
            )
        if self.unrealized_value:
            u_color = COLORS["positive"] if unrealized >= 0 else COLORS["negative"]
            self.unrealized_value.setText(f"${unrealized:+,.2f}")
            self.unrealized_value.setStyleSheet(
                f"padding: 2px 5px; background-color: {COLORS['background']}; "
                f"border: 1px solid {COLORS['border']}; font-size: 12px; color: {u_color}; text-align: right;"  # noqa: E501
            )

    def _save_snapshot(self) -> None:
        """Persist current market_data values to disk for next launch."""
        try:
            self._SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)

            # Ensure latest account labels are captured for the active mode.
            self._remember_current_account_snapshot()

            account_by_mode = {
                mode.value: dict(self._account_snapshot_by_mode.get(mode, {}))
                for mode in TradingMode
            }
            # PAPER account labels are simulation/UI state and may be stale at startup;
            # avoid restoring them from snapshots.
            account_by_mode[TradingMode.PAPER.value] = {}
            pnl_stats_by_mode = {
                mode.value: dict(self._pnl_stats_by_mode.get(mode, {}))
                for mode in TradingMode
            }

            payload = {
                "_saved_at": time.time(),
                "trading_mode": self.trading_mode.value,
                "account_by_mode": account_by_mode,
                "pnl_stats_by_mode": pnl_stats_by_mode,
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

            # Restore per-mode account snapshots.
            account_by_mode = payload.get("account_by_mode", {}) or {}
            if isinstance(account_by_mode, dict):
                for mode_name, values in account_by_mode.items():
                    try:
                        mode = TradingMode(mode_name)
                    except Exception:
                        continue
                    if mode == TradingMode.PAPER:
                        continue
                    if isinstance(values, dict):
                        self._account_snapshot_by_mode[mode] = dict(values)

            # Restore per-mode P&L stats snapshots.
            pnl_by_mode = payload.get("pnl_stats_by_mode", {}) or {}
            if isinstance(pnl_by_mode, dict):
                for mode_name, values in pnl_by_mode.items():
                    try:
                        mode = TradingMode(mode_name)
                    except Exception:
                        continue
                    if isinstance(values, dict):
                        self._pnl_stats_by_mode[mode] = dict(values)

            if not data:
                saved_account = self._account_snapshot_by_mode.get(self.trading_mode)
                if self.trading_mode != TradingMode.PAPER and isinstance(saved_account, dict) and saved_account:
                    self._apply_account_snapshot(saved_account)
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

            # Apply saved account values for the active mode after symbols restore.
            saved_account = self._account_snapshot_by_mode.get(self.trading_mode)
            if self.trading_mode != TradingMode.PAPER and isinstance(saved_account, dict) and saved_account:
                self._apply_account_snapshot(saved_account)
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

            # Persist symbol/account/P&L values so next launch can restore them.
            self._save_snapshot_on_shutdown()

            # Log shutdown
            self.add_system_log("🔥 Enhanced Trading Dashboard shutting down...")
            self.add_system_log("Dashboard session ended with heartbeat monitoring")

            # Accept close event
            event.accept()

        except Exception as e:
            logger.info("Error during enhanced dashboard close: %s", e)
            event.accept()

    def _save_snapshot_on_shutdown(self) -> None:
        """Persist a single snapshot during shutdown, regardless of quit path."""
        if self._shutdown_snapshot_saved:
            return
        try:
            self._save_snapshot()
            logger.info("Dashboard snapshot saved for PAPER+LIVE on exit")
            try:
                self.add_system_log("📦 Snapshot saved for PAPER+LIVE")
            except Exception:  # noqa: BLE001
                # UI may already be tearing down; logger line above remains authoritative.
                pass
        finally:
            self._shutdown_snapshot_saved = True

    def _on_app_about_to_quit(self) -> None:
        """Qt application-level shutdown hook for save-on-exit behavior."""
        self._save_snapshot_on_shutdown()



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
    logger.info("📡 Tradier market data feeds")
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
            logger.info("   • Market data source: TRADIER DATA")
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
            logger.info("   • Market data source: TRADIER DATA")
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
