#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovS_Signals
Module: TradovS07_CustomMetricsOrchestrator.py
Purpose: Central orchestrator for all custom market metrics (Updated - Regime Detection Removed)
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-06-26 Time: 13:25:07

Module Description:
    Central orchestrator that coordinates all custom metric calculations.
    Provides a unified interface for GEX, DEX, OGL,
    DIX, SWAN, and SKEW calculations. Emits Qt signals for GUI integration
    and manages update scheduling for all metrics.

CONSOLIDATION UPDATE:
    Regime detection functions have been REMOVED and consolidated into
    TradovL09_UnifiedRegimeEngine.py. This module now focuses exclusively
    on metric calculation, orchestration, and Qt signal emission.

Key Features:
    • Unified interface for all S-Series signal calculations (S01-S06)
    • Real-time metric updates with dynamic frequency adjustment
    • Qt signal emission for GUI integration
    • Connection management and status monitoring
    • Intelligent error handling and fallback values
    • Performance optimization with caching
    • Market stress-based update frequency adjustment

Removed Functions:
    • detect_market_regime() - Now handled by L09_UnifiedRegimeEngine
    • analyze_regime_signals() - Consolidated into unified regime system
    • All regime classification logic - Moved to dedicated engine
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import os
import json
import math
import threading
import time
import importlib
import pathlib
from datetime import datetime, timedelta, UTC
from typing import Any
from dataclasses import dataclass, field
from enum import Enum

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
from PySide6.QtCore import QObject, QTimer, Qt, Signal, Slot
from PySide6.QtWidgets import QApplication

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger
from Tradov.TradovU_Utilities.TradovU02_ErrorHandler import TradovErrorHandler

# ==============================================================================
# LAZY OPTIONAL IMPORTS
# ==============================================================================
GEXDataUnavailableError = Exception
SKEWDataUnavailableError = Exception


def _signal_module_variants(module_name: str) -> tuple[str, str]:
    """Return both import paths used across the Tradov package surfaces."""
    return (
        f"TradovS_Signals.{module_name}",
        f"Tradov.TradovS_Signals.{module_name}",
    )


def _import_optional_symbols(module_names: tuple[str, ...], *symbol_names: str) -> tuple[Any, ...]:
    """Import optional symbols lazily without penalizing dashboard first paint."""
    last_error: ImportError | None = None
    for module_name in module_names:
        try:
            module = importlib.import_module(module_name)
            return tuple(getattr(module, symbol_name) for symbol_name in symbol_names)
        except ImportError as exc:
            last_error = exc

    if last_error is not None:
        raise last_error

    raise ImportError(f"Could not import any of: {module_names!r}")

# ==============================================================================
# CONSTANTS
# ==============================================================================
CLIENT_ID = 10
UPDATE_INTERVAL = 60        # Standard update interval (seconds)
FAST_UPDATE = 30           # Fast update during high stress
SLOW_UPDATE = 300          # Slow update during calm periods

# Market stress thresholds for dynamic updates
SWAN_HIGH_STRESS = 3.0     # SWAN score indicating high stress
SWAN_MEDIUM_STRESS = 2.0   # SWAN score indicating medium stress
VIX_HIGH_STRESS = 30.0     # VIX level indicating high stress
VIX_MEDIUM_STRESS = 20.0   # VIX level indicating medium stress

# Cache settings
METRICS_CACHE_SIZE = 1000
CACHE_EXPIRY_SECONDS = 300

# ==============================================================================
# DATA CLASSES
# ==============================================================================
@dataclass
class MetricSnapshot:
    """Snapshot of all current metrics"""
    dix: float = 0.0
    swan: float = 1.0
    skew: float = 100.0
    yield_10y: float = float("nan")
    yield_slope: float = float("nan")
    aaii_bullish: float = float("nan")
    aaii_bearish: float = float("nan")
    naaim_exposure: float = float("nan")
    tick: float = float("nan")
    add: float = float("nan")
    trin: float = float("nan")
    nymo: float = float("nan")
    breadth_regime: str = "neutral"
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    update_frequency: int = UPDATE_INTERVAL

@dataclass
class MetricQuality:
    """Quality assessment of metric calculations"""
    metric_name: str
    quality_score: float  # 0.0 to 1.0
    data_points: int
    last_successful_update: datetime
    error_count: int = 0
    source_available: bool = True

class StressLevel(Enum):
    """Market stress level classifications"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRISIS = "crisis"

# ==============================================================================
# MAIN ORCHESTRATOR CLASS
# ==============================================================================
class CustomMetricsOrchestrator(QObject):
    """
    Central orchestrator for all custom market metrics.

    Coordinates S01-S06 calculators and provides a unified
    interface for metric calculations with dynamic
    update frequency based on market conditions.

    NOTE: Regime detection functionality removed - now handled by
    TradovL09_UnifiedRegimeEngine for consolidation.
    """

    # ==========================================================================
    # QT SIGNALS
    # ==========================================================================
    metrics_updated = Signal(dict)
    gex_updated = Signal(dict)
    dix_updated = Signal(float)
    swan_updated = Signal(dict)
    skew_updated = Signal(float)
    fred_updated = Signal(dict)
    sentiment_updated = Signal(dict)
    breadth_updated = Signal(dict)
    connection_status_changed = Signal(bool, str)
    error_occurred = Signal(str)
    stress_level_changed = Signal(str)  # New signal for stress level changes
    update_interval_change_requested = Signal(int)

    def __init__(self, config: dict | None = None):
        """Initialize custom metrics orchestrator"""
        super().__init__()

        self.logger = TradovLogger.get_logger(__name__)
        self.error_handler = TradovErrorHandler()
        self.config = config or {}
        self.client_id = CLIENT_ID
        self._shutdown_requested = False
        self._startup_thread: threading.Thread | None = None
        self._update_thread: threading.Thread | None = None
        self._update_running = False
        self._startup_join_timeout_seconds = float(
            self.config.get("startup_join_timeout_seconds", 12.0)
        )
        self._calculator_init_lock = threading.Lock()
        self._calculators_initialized = False
        self._has_published_metrics = False

        # Optional calculators are resolved lazily off the GUI thread so the
        # dashboard can finish painting before heavy import chains begin.
        self.dix_calculator = None
        self.swan_indicator = None
        self.gex_calculator = None
        self.skew_calculator = None
        self.fred_client = None
        self.sentiment_scraper = None
        self.dix_scheduler = None
        self.swan_scheduler = None
        self.tv_client = None
        self.pca_signal_engine = None
        self.market_intel_client = None
        self.snapshot_llm = None
        self.eco_calendar = None

        # Current metrics storage with thread-safe access
        self._metrics_lock = threading.RLock()
        self.current_metrics = {
            "DIX": float("nan"),
            "SWAN": float("nan"),
            "SKEW": float("nan"),
            "PCA-PROXY": 0.0,
            "PCA-IV": 0.0,
            "YIELD_10Y": float("nan"),
            "YIELD_SLOPE": float("nan"),
            "YIELD_INVERTED": False,
            "AAII_BULLISH": float("nan"),
            "AAII_BEARISH": float("nan"),
            "NAAIM_EXPOSURE": float("nan"),
            "TICK": float("nan"),
            "ADD": float("nan"),
            "TRIN": float("nan"),
            "NYMO": float("nan"),
            "VOLD": float("nan"),
            "BREADTH_REGIME": "neutral",
            "BREADTH_DEFENSIVE": float("nan"),
            "BREADTH_CYCLICAL": float("nan"),
            "BREADTH_SPREAD": float("nan"),
            "SECTOR_ADV_DEC": float("nan"),
            "SECTOR_MOMENTUM_DISPERSION": float("nan"),
            "PARTICIPATION_SCORE": float("nan"),
            "SECTOR_BREADTH": {},
            "TRAD_CHANGE_PCT": float("nan"),
            "QQQ_CHANGE_PCT": float("nan"),
            "IWM_CHANGE_PCT": float("nan"),
            "XLK_CHANGE_PCT": float("nan"),
            "XLF_CHANGE_PCT": float("nan"),
            "DATA_QUALITY_FEED": {},
            "PCA-PROXY_DETAILS": {},
            "PCA-IV_DETAILS": {},
            # S15 / S16 — market intelligence and LLM snapshot
            "ADANOS_SENTIMENT": {},
            "NEWS_FLOW_EQUITIES": float("nan"),
            "NEWS_FLOW_MACRO": float("nan"),
            "NEWS_FLOW_VERDICT": "neutral",
            "NEWS_FLOW_HEADLINE": "",
            "MARKET_SNAPSHOT_TEXT": "",
            # S18 — economic calendar stand-down
            "ECO_STAND_DOWN": False,
            "ECO_NEXT_EVENT_NAME": "",
            "ECO_NEXT_EVENT_MINUTES": float("nan"),
        }

        # HV20 daily cache — historical volatility changes at most once per
        # trading day, so we skip the expensive /v1/markets/history call on
        # every 60-second cycle and only refetch when the calendar date changes.
        self._hv20_cache: float | None = None
        self._hv20_cache_date: str = ""
        # Running EMA state for NYMO proxy (McClellan Oscillator approximation).
        # NYMO ≈ EMA(19) − EMA(39) of the NYSE A-D (ADD) series.
        self._nymo_ema_fast: float = float("nan")  # 19-bar EMA of ADD
        self._nymo_ema_slow: float = float("nan")  # 39-bar EMA of ADD
        _a19 = 2.0 / (19 + 1)
        _a39 = 2.0 / (39 + 1)
        self._nymo_alpha_fast: float = _a19
        self._nymo_alpha_slow: float = _a39
        # Restore persisted NYMO EMA state so the warm-up survives restarts.
        _nymo_cache_path = pathlib.Path("data/cache/nymo_ema_state.json")
        if _nymo_cache_path.exists():
            try:
                _nymo_state = json.loads(_nymo_cache_path.read_text())
                _f = _nymo_state.get("ema_fast")
                _s = _nymo_state.get("ema_slow")
                if isinstance(_f, (int, float)) and math.isfinite(_f):
                    self._nymo_ema_fast = float(_f)
                if isinstance(_s, (int, float)) and math.isfinite(_s):
                    self._nymo_ema_slow = float(_s)
            except Exception:
                pass

        # Metrics history for trend analysis
        self.metrics_history: list[MetricSnapshot] = []
        self.max_history_size = self.config.get('max_history_size', 1000)

        # Quality tracking
        self.metric_quality: dict[str, MetricQuality] = {}
        self._init_quality_tracking()

        # Stress level tracking
        self.current_stress_level = StressLevel.LOW
        self.stress_history: list[tuple[datetime, StressLevel]] = []

        # Update frequency management
        self.current_update_interval = UPDATE_INTERVAL
        self.last_frequency_change = datetime.now(UTC)
        self._last_metrics_info_log_ts: datetime | None = None
        self._metrics_info_heartbeat_seconds = int(
            self.config.get("metrics_info_heartbeat_seconds", 180)
        )
        self._last_liquidity_diag_log_ts: datetime | None = None
        self._last_liquidity_diag_message: str | None = None
        self._liquidity_diag_heartbeat_seconds = int(
            self.config.get("liquidity_diag_heartbeat_seconds", 300)
        )
        self._issue_log_heartbeat_seconds = int(
            self.config.get("issue_log_heartbeat_seconds", 300)
        )
        self._issue_log_state: dict[str, tuple[str, datetime]] = {}

        # Connection status
        self.ib_connected = False
        self.connection_attempts = 0
        self.last_connection_attempt = None

        # Update timer with dynamic frequency
        self.update_timer = QTimer()
        # IMPORTANT: connect to _dispatch_metrics_update, NOT update_all_metrics directly.
        # update_all_metrics makes blocking HTTP requests (FINRA, FRED, NAAIM, AAII) that
        # take 5-10 seconds and freeze the Qt main thread if called here.
        # The dispatcher spawns a daemon thread so the event loop is never stalled.
        self.update_timer.timeout.connect(self._dispatch_metrics_update)
        self.update_interval_change_requested.connect(
            self._apply_update_interval,
            Qt.ConnectionType.QueuedConnection,
        )
        self.update_timer.setInterval(self.current_update_interval * 1000)

        self.logger.debug("CustomMetricsOrchestrator initialized (Client ID: %s)", CLIENT_ID)
        self.logger.debug("⚠️ Regime detection functions removed - now handled by L09_UnifiedRegimeEngine")  # noqa: E501

        # Auto-start if configured
        if self.config.get("auto_start", True):
            self.start()

    def _init_calculators(self):
        """Initialize all available calculators"""
        global GEXDataUnavailableError, SKEWDataUnavailableError

        # S01 - DIX Calculator
        try:
            (get_calculator_instance,) = _import_optional_symbols(
                _signal_module_variants("TradovS01_DIXCalculator"),
                "get_calculator_instance",
            )
            self.dix_calculator = get_calculator_instance()
            self.logger.debug("✅ S01_DIXCalculator initialized")
        except ImportError as exc:
            self.dix_calculator = None
            self.logger.debug("S01_DIXCalculator unavailable: %s", exc)
        except Exception as e:
            self.logger.error("Failed to init DIX: %s", e, exc_info=True)
            self.dix_calculator = None

        # S03 - Black Swan Indicator
        try:
            (get_black_swan_indicator,) = _import_optional_symbols(
                _signal_module_variants("TradovS03_BlackSwanIndicator"),
                "get_black_swan_indicator",
            )
            self.swan_indicator = get_black_swan_indicator()
            self.logger.debug("✅ S03_BlackSwanIndicator initialized")
        except ImportError as exc:
            self.swan_indicator = None
            self.logger.debug("S03_BlackSwanIndicator unavailable: %s", exc)
        except Exception as e:
            self.logger.error("Failed to init SWAN: %s", e, exc_info=True)
            self.swan_indicator = None

        # S05 - GEX/DEX Calculator
        try:
            GEXDEXCalculator, GEXDataUnavailableError = _import_optional_symbols(
                _signal_module_variants("TradovS05_GEXDEXCalculator"),
                "GEXDEXCalculator",
                "DataUnavailableError",
            )
            self.gex_calculator = GEXDEXCalculator()
            self.logger.debug("✅ S05_GEXDEXCalculator initialized")
        except ImportError as exc:
            self.gex_calculator = None
            GEXDataUnavailableError = Exception
            self.logger.debug("S05_GEXDEXCalculator unavailable: %s", exc)
        except Exception as e:
            self.logger.error("Failed to init GEX: %s", e, exc_info=True)
            self.gex_calculator = None
            GEXDataUnavailableError = Exception

        # S06 - SKEW Calculator
        try:
            get_skew_calculator, SKEWDataUnavailableError = _import_optional_symbols(
                _signal_module_variants("TradovS06_SKEWCalculator"),
                "get_skew_calculator",
                "DataUnavailableError",
            )
            self.skew_calculator = get_skew_calculator()
            self.logger.debug("✅ S06_SKEWCalculator initialized")
        except ImportError as exc:
            self.skew_calculator = None
            SKEWDataUnavailableError = Exception
            self.logger.debug("S06_SKEWCalculator unavailable: %s", exc)
        except Exception as e:
            self.logger.error("Failed to init SKEW: %s", e, exc_info=True)
            self.skew_calculator = None
            SKEWDataUnavailableError = Exception

        # S09 - FRED Client (Treasury yields, DXY proxy, yield curve)
        try:
            (get_fred_client,) = _import_optional_symbols(
                _signal_module_variants("TradovS09_FREDClient"),
                "get_fred_client",
            )
            self.fred_client = get_fred_client()
            self.logger.debug("✅ S09_FREDClient initialized")
        except ImportError as exc:
            self.fred_client = None
            self.logger.debug("S09_FREDClient unavailable: %s", exc)
        except Exception as e:
            self.logger.error("Failed to init FRED: %s", e, exc_info=True)
            self.fred_client = None

        # S10 - Sentiment Scraper (AAII + NAAIM weekly surveys)
        try:
            (get_sentiment_scraper,) = _import_optional_symbols(
                _signal_module_variants("TradovS10_SentimentScraper"),
                "get_sentiment_scraper",
            )
            self.sentiment_scraper = get_sentiment_scraper()
            self.logger.debug("✅ S10_SentimentScraper initialized")
        except ImportError as exc:
            self.sentiment_scraper = None
            self.logger.debug("S10_SentimentScraper unavailable: %s", exc)
        except Exception as e:
            self.logger.error("Failed to init Sentiment: %s", e, exc_info=True)
            self.sentiment_scraper = None

        # S02 - DIX Scheduler (pre-market 9:00 AM + EOD 6:30 PM ET cron collection)
        try:
            (TradovDIXScheduler,) = _import_optional_symbols(
                _signal_module_variants("TradovS02_DIXScheduler"),
                "TradovDIXScheduler",
            )
            self.dix_scheduler = TradovDIXScheduler()
            self.logger.debug("✅ S02_DIXScheduler initialized")
        except ImportError as exc:
            self.dix_scheduler = None
            self.logger.debug("S02_DIXScheduler unavailable: %s", exc)
        except Exception as e:
            self.logger.error("Failed to init DIX scheduler: %s", e, exc_info=True)
            self.dix_scheduler = None

        # S04 - Black Swan Scheduler (4:00 AM / 9:15 AM / 12:00 PM / 3:45 PM / 4:30 PM ET)
        try:
            (BlackSwanSchedulerCls,) = _import_optional_symbols(
                _signal_module_variants("TradovS04_BlackSwanScheduler"),
                "BlackSwanScheduler",
            )
            self.swan_scheduler = BlackSwanSchedulerCls()
            self.logger.debug("✅ S04_BlackSwanScheduler initialized")
        except ImportError as exc:
            self.swan_scheduler = None
            self.logger.debug("S04_BlackSwanScheduler unavailable: %s", exc)
        except Exception as e:
            self.logger.error("Failed to init Black Swan scheduler: %s", e, exc_info=True)
            self.swan_scheduler = None

        # S11 - TradingView Breadth Internals (TICK, TRIN, ADD)
        try:
            (get_tv_internals_client,) = _import_optional_symbols(
                _signal_module_variants("TradovS11_TradingViewInternals"),
                "get_tv_internals_client",
            )
            self.tv_client = get_tv_internals_client()
            self.logger.debug("✅ S11_TradingViewInternals initialized")
        except ImportError as exc:
            self.tv_client = None
            self.logger.debug("S11_TradingViewInternals unavailable: %s", exc)
        except Exception as e:
            self.logger.error("Failed to init TradingView internals: %s", e, exc_info=True)
            self.tv_client = None

        try:
            (get_pca_signal_engine,) = _import_optional_symbols(
                _signal_module_variants("TradovS14_PCASignals"),
                "get_pca_signal_engine",
            )
            self.pca_signal_engine = get_pca_signal_engine()
            self.logger.debug("✅ S14_PCASignals initialized")
        except ImportError as exc:
            self.pca_signal_engine = None
            self.logger.debug("S14_PCASignals unavailable: %s", exc)
        except Exception as e:
            self.logger.error("Failed to init PCA signals: %s", e, exc_info=True)
            self.pca_signal_engine = None

        # S15 - Market Intelligence (Adanos social + Alpha Vantage macro news)
        try:
            (get_market_intel_client,) = _import_optional_symbols(
                _signal_module_variants("TradovS15_MarketIntelClient"),
                "get_market_intel_client",
            )
            self.market_intel_client = get_market_intel_client()
            self.logger.debug("✅ S15_MarketIntelClient initialized")
        except ImportError as exc:
            self.market_intel_client = None
            self.logger.debug("S15_MarketIntelClient unavailable: %s", exc)
        except Exception as e:
            self.logger.error("Failed to init MarketIntelClient: %s", e, exc_info=True)
            self.market_intel_client = None

        # S16 - LLM Market Snapshot (OpenRouter)
        try:
            (get_market_snapshot_llm,) = _import_optional_symbols(
                _signal_module_variants("TradovS16_MarketSnapshotLLM"),
                "get_market_snapshot_llm",
            )
            self.snapshot_llm = get_market_snapshot_llm()
            self.logger.debug("✅ S16_MarketSnapshotLLM initialized")
        except ImportError as exc:
            self.snapshot_llm = None
            self.logger.debug("S16_MarketSnapshotLLM unavailable: %s", exc)
        except Exception as e:
            self.logger.error("Failed to init MarketSnapshotLLM: %s", e, exc_info=True)
            self.snapshot_llm = None

        # S18 - Economic calendar stand-down gate
        try:
            (get_economic_calendar,) = _import_optional_symbols(
                _signal_module_variants("TradovS18_EconomicCalendar"),
                "get_economic_calendar",
            )
            self.eco_calendar = get_economic_calendar()
            self.logger.debug("✅ S18_EconomicCalendar initialized")
        except ImportError as exc:
            self.eco_calendar = None
            self.logger.debug("S18_EconomicCalendar unavailable: %s", exc)
        except Exception as e:
            self.logger.error("Failed to init EconomicCalendar: %s", e, exc_info=True)
            self.eco_calendar = None

    def _ensure_calculators_initialized(self) -> None:
        """Resolve optional calculators once, outside the GUI-thread constructor."""
        if self._calculators_initialized:
            return

        with self._calculator_init_lock:
            if self._calculators_initialized:
                return
            self._init_calculators()
            self._calculators_initialized = True

    def _init_quality_tracking(self):
        """Initialize quality tracking for all metrics"""
        metric_names = ['GEX', 'DEX', 'OGL', 'DIX', 'SWAN', 'SKEW', 'PCA-PROXY', 'PCA-IV', 'VEX', 'CHEX', 'FRED', 'SENTIMENT', 'BREADTH', 'SECTOR_BREADTH', 'OPTIONS', 'LIQUIDITY', 'VOL_SURFACE', 'DEALER_FLOW', 'MARKET_INTEL', 'ECO_CALENDAR']  # noqa: E501

        for metric in metric_names:
            self.metric_quality[metric] = MetricQuality(
                metric_name=metric,
                quality_score=1.0,  # Start with perfect score
                data_points=0,
                last_successful_update=datetime.now(UTC),
                error_count=0,
                source_available=True
            )

    # ==========================================================================
    # MAIN ORCHESTRATOR METHODS
    # ==========================================================================

    def start(self):
        """Start the orchestrator — non-blocking.

        The QTimer is started here on the main Qt thread (required). All network
        I/O (initial metric fetch + late-start Black Swan check) is deferred to a
        background daemon thread so that the Qt event loop is never blocked.
        """
        import threading
        try:
            self._shutdown_requested = False
            self.update_timer.start()
            self.ib_connected = True

            self.logger.debug("✅ Orchestrator started — background fetch beginning")
            self.connection_status_changed.emit(True, f"Client {CLIENT_ID} Active")

            # All blocking setup (optional imports, calculator init, DIX init,
            # metric fetch, Black Swan catch-up) runs in a background daemon
            # thread so the Qt event loop is never stalled during startup.
            self._startup_thread = threading.Thread(
                target=self._startup_fetch,
                name="S07-startup-fetch",
                daemon=True,
            )
            self._startup_thread.start()

        except Exception as e:
            self.logger.error("Failed to start orchestrator: %s", e, exc_info=True)
            self.error_occurred.emit(f"Startup failed: {str(e)}")

    def _startup_fetch(self):
        """Background startup: DIX init, initial metric fetch, late-start Black Swan check.

        Runs entirely off the Qt main thread — no GUI calls allowed here.
        """
        try:
            if self._shutdown_requested:
                return

            self._ensure_calculators_initialized()
            self._prime_persistent_indicator_caches()

            if self._shutdown_requested:
                return
            if self.swan_scheduler is not None:
                try:
                    self.swan_scheduler.start(daemon=True)
                    self.logger.debug("✅ S04_BlackSwanScheduler started (4:00 AM / 9:15 AM / 12:00 PM / 3:45 PM ET)")  # noqa: E501
                except Exception as e:
                    self.logger.error("Black Swan scheduler startup failed: %s", e)

            # S02 DIX Scheduler — initialize() hits FINRA over HTTP; must be off-thread
            if self.dix_scheduler is not None:
                try:
                    if self.dix_scheduler.initialize():
                        if self._shutdown_requested:
                            return
                        self.dix_scheduler.start(run_initial_calculation=False)
                        self.logger.debug("✅ S02_DIXScheduler started (9:00 AM + 6:30 PM ET)")
                    else:
                        self.logger.warning("⚠️ DIX scheduler init failed; skipping scheduled collection")  # noqa: E501
                except Exception as e:
                    self.logger.error("DIX scheduler startup failed: %s", e)

            # Full startup metrics fetch is deferred to the regular timer path.
            # The one-shot startup refresh was the main source of shutdown-time
            # stragglers because it fans out into multiple blocking network sources.

            # Late-start Black Swan catch-up check
            try:
                if self._shutdown_requested:
                    return
                if self.swan_scheduler is not None:
                    # Run the 9:15 AM check so late starts don't silently miss the
                    # pre-open window.
                    self.swan_scheduler.run_now("daily_check_0915")
            except Exception as e:
                self.logger.error("Startup Black Swan check failed: %s", e)
        finally:
            if self._startup_thread is threading.current_thread():
                self._startup_thread = None

    def _prime_persistent_indicator_caches(self) -> None:
        """Restore same-day indicator snapshots before the first live update."""
        if self.gex_calculator is not None:
            try:
                gex_snapshot = self.gex_calculator.get_last_snapshot()
                if gex_snapshot:
                    self.current_metrics["GEX"] = gex_snapshot.get("gex", self.current_metrics.get("GEX", -2.5))
                    self.current_metrics["DEX"] = gex_snapshot.get("dex", self.current_metrics.get("DEX", 850))
                    self.current_metrics["OGL"] = gex_snapshot.get("ogl", self.current_metrics.get("OGL", 585.5))
                    self.current_metrics["VEX"] = gex_snapshot.get("vex", self.current_metrics.get("VEX", 0.0))
                    self.current_metrics["CHEX"] = gex_snapshot.get("chex", self.current_metrics.get("CHEX", 0.0))
            except Exception as e:
                self.logger.debug("GEX cache hydration skipped: %s", e)

        if self.dix_scheduler is not None:
            try:
                dix_data = self.dix_scheduler.get_latest_dix(allow_calculation=False)
                if dix_data:
                    self.current_metrics["DIX"] = dix_data["dix_percentage"]
            except Exception as e:
                self.logger.debug("DIX cache hydration skipped: %s", e)

        if self.swan_scheduler is not None:
            try:
                swan_result = self.swan_scheduler.get_latest_result(allow_calculation=False)
                if swan_result:
                    self.current_metrics["SWAN"] = swan_result.overall_score
            except Exception as e:
                self.logger.debug("SWAN cache hydration skipped: %s", e)

        nymo_value = self._get_cached_nymo_value()
        if nymo_value is not None:
            self.current_metrics["NYMO"] = nymo_value

        self._prime_pca_snapshot_metrics()

    def _get_cached_nymo_value(self) -> float | None:
        """Return the persisted NYMO proxy value when the EMA warm state exists."""
        if math.isfinite(self._nymo_ema_fast) and math.isfinite(self._nymo_ema_slow):
            return round(self._nymo_ema_fast - self._nymo_ema_slow, 1)
        return None

    def _prime_pca_snapshot_metrics(self) -> None:
        """Restore cached PCA snapshots so the dashboard starts with recent state."""
        if self.pca_signal_engine is None:
            return

        try:
            proxy_snapshot = self.pca_signal_engine.get_proxy_snapshot()
            self.current_metrics["PCA-PROXY"] = float(proxy_snapshot.signal_value)
            self.current_metrics["PCA-PROXY_CHANGE"] = float(proxy_snapshot.change)
            self.current_metrics["PCA-PROXY_DETAILS"] = {
                "source": proxy_snapshot.source,
                "status": proxy_snapshot.status,
                "explained_variance": proxy_snapshot.explained_variance,
                "spectral_gap": proxy_snapshot.spectral_gap,
                "dispersion_score": proxy_snapshot.dispersion_score,
                "universe_size": proxy_snapshot.universe_size,
                "confidence": proxy_snapshot.confidence,
                "timestamp": proxy_snapshot.timestamp.isoformat(),
                "details": proxy_snapshot.details or {},
            }
        except Exception as e:
            self.logger.debug("PCA-PROXY cache hydration skipped: %s", e)

        try:
            iv_snapshot = self.pca_signal_engine.get_iv_snapshot()
            self.current_metrics["PCA-IV"] = float(iv_snapshot.signal_value)
            self.current_metrics["PCA-IV_CHANGE"] = float(iv_snapshot.change)
            self.current_metrics["PCA-IV_DETAILS"] = {
                "source": iv_snapshot.source,
                "status": iv_snapshot.status,
                "placeholder": iv_snapshot.placeholder,
                "explained_variance": iv_snapshot.explained_variance,
                "spectral_gap": iv_snapshot.spectral_gap,
                "dispersion_score": iv_snapshot.dispersion_score,
                "universe_size": iv_snapshot.universe_size,
                "confidence": iv_snapshot.confidence,
                "timestamp": iv_snapshot.timestamp.isoformat(),
                "details": iv_snapshot.details or {},
            }
        except Exception as e:
            self.logger.debug("PCA-IV cache hydration skipped: %s", e)

    def stop(self):
        """Stop the orchestrator"""
        try:
            self._shutdown_requested = True
            startup_thread = self._startup_thread
            update_thread = self._update_thread
            startup_thread_still_running = False
            update_thread_still_running = False
            startup_join_timeout = float(
                getattr(self, "_startup_join_timeout_seconds", 12.0)
            )

            # Stop data collection schedulers first
            if self.dix_scheduler is not None:
                self.dix_scheduler.stop()
            if self.swan_scheduler is not None:
                self.swan_scheduler.stop()

            if self.tv_client is not None and hasattr(self.tv_client, "close"):
                self.tv_client.close()
                self.tv_client = None

            self.update_timer.stop()
            self.ib_connected = False

            if (
                startup_thread is not None
                and startup_thread.is_alive()
                and startup_thread is not threading.current_thread()
            ):
                startup_thread.join(timeout=startup_join_timeout)
                startup_thread_still_running = startup_thread.is_alive()

            if (
                update_thread is not None
                and update_thread.is_alive()
                and update_thread is not threading.current_thread()
            ):
                update_thread.join(timeout=2.0)
                update_thread_still_running = update_thread.is_alive()

            if not startup_thread_still_running and self._startup_thread is startup_thread:
                self._startup_thread = None
            if not update_thread_still_running and self._update_thread is update_thread:
                self._update_thread = None
            self._update_running = False

            if startup_thread_still_running:
                self.logger.warning(
                    "S07 startup thread still active after %.1fs stop wait; leaving handle attached",
                    startup_join_timeout,
                )
            if update_thread_still_running:
                self.logger.warning(
                    "S07 update thread still active after 2.0s stop wait; leaving handle attached"
                )

            if startup_thread_still_running or update_thread_still_running:
                self.logger.info("⏹️ Orchestrator stop requested")
            else:
                self.logger.info("⏹️ Orchestrator stopped")
            self.connection_status_changed.emit(False, f"Client {CLIENT_ID} Stopped")

        except Exception as e:
            self.logger.error("Error stopping orchestrator: %s", e, exc_info=True)

    def _dispatch_metrics_update(self, include_breadth: bool = True) -> None:
        """Qt-thread-safe timer slot: run update_all_metrics in a daemon thread.

        Called by QTimer.timeout (main thread) every UPDATE_INTERVAL seconds.
        Spawns a background thread so the Qt event loop is never stalled by
        the blocking HTTP requests inside update_all_metrics (FINRA, FRED, NAAIM…).
        Guards against concurrent runs with a simple flag.
        """
        import threading
        if getattr(self, "_update_running", False):
            self.logger.debug("S07 update already in progress — skipping this tick")
            return
        self._update_running = True

        def _run():
            try:
                self.update_all_metrics(include_breadth=include_breadth)
            finally:
                self._update_running = False
                if self._update_thread is threading.current_thread():
                    self._update_thread = None

        self._update_thread = threading.Thread(
            target=_run,
            name="S07-metrics-update",
            daemon=True,
        )
        self._update_thread.start()

    def _shutdown_in_progress(self) -> bool:
        """Return True once orchestrator shutdown has begun."""
        return bool(getattr(self, "_shutdown_requested", False))

    def has_published_metrics_snapshot(self) -> bool:
        """Return True after at least one full metrics update has completed."""
        return bool(getattr(self, "_has_published_metrics", False))

    def update_all_metrics(self, include_breadth: bool = True):
        """Update all metrics from S-Series calculators"""
        if self._shutdown_in_progress():
            return

        self._ensure_calculators_initialized()

        start_time = time.time()

        try:
            with self._metrics_lock:
                if self._shutdown_in_progress():
                    return

                updated_metrics = {}
                update_errors = []

                # S05 - GEX/DEX/OGL/VEX/CHEX Updates
                gex_success = self._update_gex_metrics(updated_metrics, update_errors)

                # S01 - DIX Updates
                dix_success = self._update_dix_metrics(updated_metrics, update_errors)

                # S03 - SWAN Updates
                swan_success = self._update_swan_metrics(updated_metrics, update_errors)

                # S06 - SKEW Updates
                skew_success = self._update_skew_metrics(updated_metrics, update_errors)

                # S14 - PCA proxy and IV placeholder
                pca_success = self._update_pca_metrics(updated_metrics, update_errors)

                # S09 - FRED Macro Updates (Treasury yields, yield curve, DXY)
                fred_success = self._update_fred_metrics(updated_metrics, update_errors)

                # S10 - Sentiment Updates (AAII weekly surveys, NAAIM exposure)
                sentiment_success = self._update_sentiment_metrics(updated_metrics, update_errors)

                # S15 - Market Intelligence (Adanos social + AV macro news)
                market_intel_success = self._update_market_intel_metrics(updated_metrics, update_errors)  # noqa: E501

                # S18 - Economic calendar stand-down signals
                eco_calendar_success = self._update_eco_calendar_metrics(updated_metrics, update_errors)  # noqa: E501

                if self._shutdown_in_progress():
                    return

                # S11 - TradingView Breadth Internals (TICK, TRIN, ADD)
                if include_breadth:
                    breadth_success = self._update_tv_breadth_metrics(updated_metrics, update_errors)
                else:
                    breadth_success = True

                if self._shutdown_in_progress():
                    return

                # S16 - LLM market snapshot text (throttled via internal TTL cache)
                self._update_market_snapshot_text(updated_metrics)

                # Update stored values
                self.current_metrics.update(updated_metrics)

                # Update quality tracking
                self._update_quality_metrics(updated_metrics, update_errors)

                # Unified SLO/data-quality feed built after quality updates.
                updated_metrics["DATA_QUALITY_FEED"] = self._build_data_quality_feed(
                    updated_metrics,
                    update_errors,
                )
                self.current_metrics["DATA_QUALITY_FEED"] = updated_metrics["DATA_QUALITY_FEED"]

                # Create metrics snapshot for history
                snapshot = MetricSnapshot(
                    dix=updated_metrics.get('DIX', 0.0),
                    swan=updated_metrics.get('SWAN', 1.0),
                    skew=updated_metrics.get('SKEW', 100.0),
                    yield_10y=updated_metrics.get('YIELD_10Y', float('nan')),
                    yield_slope=updated_metrics.get('YIELD_SLOPE', float('nan')),
                    aaii_bullish=updated_metrics.get('AAII_BULLISH', float('nan')),
                    aaii_bearish=updated_metrics.get('AAII_BEARISH', float('nan')),
                    naaim_exposure=updated_metrics.get('NAAIM_EXPOSURE', float('nan')),
                    tick=updated_metrics.get('TICK', float('nan')),
                    add=updated_metrics.get('ADD', float('nan')),
                    trin=updated_metrics.get('TRIN', float('nan')),
                    nymo=updated_metrics.get('NYMO', float('nan')),
                    breadth_regime=updated_metrics.get('BREADTH_REGIME', 'neutral'),
                    update_frequency=self.current_update_interval
                )

                self._add_to_history(snapshot)

                # Analyze stress level and adjust frequency
                self._analyze_and_adjust_frequency(updated_metrics)

                # Format and emit signals
                formatted_metrics = self._format_metrics(updated_metrics)
                self._has_published_metrics = True
                self.metrics_updated.emit(formatted_metrics)

                # Log successful update
                calculation_time = time.time() - start_time
                success_count = sum([
                    gex_success, dix_success, swan_success, skew_success,
                    pca_success,
                    fred_success, sentiment_success, breadth_success,
                    market_intel_success,
                    eco_calendar_success,
                ])

                # Keep custom-metrics cycle summaries in DEBUG so NORMAL logs
                # remain focused on lifecycle, warnings, and errors.
                _summary = (
                    f"{success_count}/10 | "
                    f"GEX={updated_metrics.get('GEX', 0):.1f}B "
                    f"DIX={updated_metrics.get('DIX', 0):.1f}% "
                    f"SWAN={updated_metrics.get('SWAN', 1):.2f} "
                    f"PCA={updated_metrics.get('PCA-PROXY', 0):+.2f} "
                    f"SKEW={updated_metrics.get('SKEW', 100):.1f} "
                    f"TICK={updated_metrics.get('TICK', float('nan'))}"
                )
                _last = getattr(self, "_last_metrics_summary", None)
                _now = datetime.now(UTC)
                _heartbeat_due = (
                    self._last_metrics_info_log_ts is None
                    or (_now - self._last_metrics_info_log_ts).total_seconds()
                    >= self._metrics_info_heartbeat_seconds
                )
                self.logger.debug(
                    f"📊 Metrics updated: {success_count}/10 sources successful "
                    f"(GEX={updated_metrics.get('GEX', 0):.1f}B, "
                    f"DIX={updated_metrics.get('DIX', 0):.1f}%, "
                    f"SWAN={updated_metrics.get('SWAN', 1):.2f}, "
                    f"SKEW={updated_metrics.get('SKEW', 100):.1f}, "
                    f"TICK={updated_metrics.get('TICK', float('nan'))}, "
                    f"10Y={updated_metrics.get('YIELD_10Y', float('nan')):.2f}%) "
                    f"[{calculation_time:.2f}s]"
                )
                if _heartbeat_due:
                    self._last_metrics_info_log_ts = _now
                self._last_metrics_summary = _summary

                self._emit_update_error_summary(update_errors, success_count)

        except Exception as e:
            self.logger.error("Critical error updating metrics: %s", e, exc_info=True)
            self.error_occurred.emit(str(e))

    def _log_deduped_issue(
        self,
        channel: str,
        message: str,
        *,
        level: str = "warning",
        emit_error: bool = False,
    ) -> None:
        """Log issue messages once per change/heartbeat to suppress repetitive noise."""
        now = datetime.now(UTC)
        last = self._issue_log_state.get(channel)
        changed = last is None or last[0] != message
        heartbeat_due = (
            last is None
            or (now - last[1]).total_seconds() >= self._issue_log_heartbeat_seconds
        )
        if not (changed or heartbeat_due):
            return

        if level == "error":
            self.logger.error(message)
        elif level == "debug":
            self.logger.debug(message)
        elif level == "info":
            self.logger.info(message)
        else:
            self.logger.warning(message)

        self._issue_log_state[channel] = (message, now)
        if emit_error:
            self.error_occurred.emit(message)

    @staticmethod
    def _error_key(error_message: str) -> str:
        """Extract stable error key for compact cycle summaries."""
        if not error_message:
            return "unknown"
        return error_message.split(":", 1)[0].strip().lower()

    def _emit_update_error_summary(self, update_errors: list[str], success_count: int) -> None:
        """Emit a compact warning summary for update-cycle failures."""
        if not update_errors:
            return

        keys = sorted({self._error_key(err) for err in update_errors})
        summary = ", ".join(keys)
        benign_keys = {
            "options analytics update failed",
            "vol surface update failed",
        }
        only_benign = bool(keys) and all(key in benign_keys for key in keys)
        self._log_deduped_issue(
            channel="update_cycle_info" if only_benign else "update_cycle_errors",
            message=(
                "S07 update-cycle issues: "
                f"{len(update_errors)} issue(s), "
                f"{success_count}/10 sources successful, keys=[{summary}]"
            ),
            level="debug" if only_benign else "warning",
            emit_error=not only_benign,
        )

    def _update_gex_metrics(self, updated_metrics: dict, errors: list) -> bool:
        """Update GEX, DEX, OGL metrics"""
        try:
            if self.gex_calculator:
                gex_data = self.gex_calculator.calculate_all()
                updated_metrics["GEX"] = gex_data.get("gex", 0)   # S05 returns billions already
                updated_metrics["DEX"] = gex_data.get("dex", 0)   # S05 returns millions already
                updated_metrics["OGL"] = gex_data.get("ogl", 585.5)
                updated_metrics["VEX"] = gex_data.get("vex", 0.0)   # Vanna Exposure ($M/vol-pt)
                updated_metrics["CHEX"] = gex_data.get("chex", 0.0)  # Charm Exposure (Δ/day)
                self.gex_updated.emit(gex_data)
                return True
            else:
                # Fallback to simulation or cached values
                updated_metrics.update({
                    "GEX": self.current_metrics.get("GEX", -2.5) + np.random.normal(0, 0.1),
                    "DEX": self.current_metrics.get("DEX", 850) + np.random.normal(0, 50),
                    "OGL": self.current_metrics.get("OGL", 585.5) + np.random.normal(0, 1),
                    "VEX": self.current_metrics.get("VEX", 0.0),
                    "CHEX": self.current_metrics.get("CHEX", 0.0),
                })
                return False
        except GEXDataUnavailableError as e:
            # Expected when options chain is not yet available — log quietly
            errors.append(f"GEX update error: {e}")
            self._log_deduped_issue(
                channel="gex_data_unavailable",
                message=f"GEX data unavailable (options chain not ready): {e}",
                level="warning",
            )
            updated_metrics.update({
                "GEX": self.current_metrics.get("GEX", -2.5),
                "DEX": self.current_metrics.get("DEX", 850),
                "OGL": self.current_metrics.get("OGL", 585.5),
                "VEX": self.current_metrics.get("VEX", 0.0),
                "CHEX": self.current_metrics.get("CHEX", 0.0),
            })
            return False
        except Exception as e:
            errors.append(f"GEX update error: {e}")
            self._log_deduped_issue(
                channel="gex_update_error",
                message=f"GEX update error: {e}",
                level="error",
                emit_error=True,
            )
            updated_metrics.update({
                "GEX": self.current_metrics.get("GEX", -2.5),
                "DEX": self.current_metrics.get("DEX", 850),
                "OGL": self.current_metrics.get("OGL", 585.5),
                "VEX": self.current_metrics.get("VEX", 0.0),
                "CHEX": self.current_metrics.get("CHEX", 0.0),
            })
            return False

    def _update_dix_metrics(self, updated_metrics: dict, errors: list) -> bool:
        """Update DIX metrics"""
        try:
            if self.dix_scheduler is not None:
                dix_data = self.dix_scheduler.get_latest_dix(allow_calculation=False)
                if dix_data:
                    updated_metrics["DIX"] = dix_data["dix_percentage"]
                    self.dix_updated.emit(dix_data["dix_percentage"])
                    return True

            if self.dix_calculator:
                dix_result = self.dix_calculator.calculate_dix()
                if dix_result:
                    updated_metrics["DIX"] = dix_result.dix_percentage
                    self.dix_updated.emit(dix_result.dix_percentage)
                    return True
                updated_metrics["DIX"] = self.current_metrics.get("DIX", 42.5)
                return False
            else:
                # Simulation fallback
                updated_metrics["DIX"] = 42.5 + np.random.normal(0, 2.0)
                return False
        except Exception as e:
            errors.append(f"DIX update error: {e}")
            self._log_deduped_issue(
                channel="dix_update_error",
                message=f"DIX update error: {e}",
                level="error",
                emit_error=True,
            )
            updated_metrics["DIX"] = self.current_metrics.get("DIX", 42.5)
            return False

    def _update_swan_metrics(self, updated_metrics: dict, errors: list) -> bool:
        """Update SWAN metrics"""
        try:
            if self.swan_scheduler is not None:
                swan_result = self.swan_scheduler.get_latest_result(allow_calculation=False)
                if swan_result:
                    updated_metrics["SWAN"] = swan_result.overall_score
                    self.swan_updated.emit({
                        "score": swan_result.overall_score,
                        "status": swan_result.status.value,
                        "components": swan_result.component_scores,
                    })
                    return True

            if self.swan_indicator:
                # Pass live TICK/ADD/TRIN breadth data into the SWAN internals
                # component so the score reflects current market breadth.
                _mi: dict[str, float] = {}
                for _k in ("TICK", "ADD", "TRIN"):
                    _v = updated_metrics.get(_k)
                    if isinstance(_v, (int, float)) and math.isfinite(_v):
                        _mi[_k.lower()] = float(_v)
                swan_result = self.swan_indicator.calculate_swan_score(
                    market_internals_override=_mi or None
                )
                updated_metrics["SWAN"] = swan_result.overall_score

                # Emit detailed SWAN signal
                self.swan_updated.emit({
                    "score": swan_result.overall_score,
                    "status": swan_result.status.value,
                    "components": swan_result.component_scores,
                })
                return True

            # Simulation fallback
            current_swan = self.current_metrics.get("SWAN", 1.85)
            updated_metrics["SWAN"] = max(1.0, min(5.0, current_swan + np.random.normal(0, 0.1)))  # noqa: E501
            return False
        except Exception as e:
            errors.append(f"SWAN update error: {e}")
            self._log_deduped_issue(
                channel="swan_update_error",
                message=f"SWAN update error: {e}",
                level="error",
                emit_error=True,
            )
            updated_metrics["SWAN"] = self.current_metrics.get("SWAN", 1.85)
            return False

    def _update_skew_metrics(self, updated_metrics: dict, errors: list) -> bool:
        """Update SKEW metrics"""
        try:
            if self.skew_calculator:
                skew_result = self.skew_calculator.calculate_skew()
                if skew_result:
                    updated_metrics["SKEW"] = skew_result.skew_index
                    self.skew_updated.emit(skew_result.skew_index)
                    return True
                else:
                    updated_metrics["SKEW"] = self.current_metrics.get("SKEW", 125.5)
                    return False
            else:
                # Simulation fallback
                updated_metrics["SKEW"] = 125.5 + np.random.normal(0, 3.0)
                return False
        except SKEWDataUnavailableError as e:
            # Expected when options chain is not yet available — log quietly
            errors.append(f"SKEW update error: {e}")
            self._log_deduped_issue(
                channel="skew_data_unavailable",
                message=f"SKEW data unavailable (options chain not ready): {e}",
                level="warning",
            )
            updated_metrics["SKEW"] = self.current_metrics.get("SKEW", 125.5)
            return False
        except Exception as e:
            errors.append(f"SKEW update error: {e}")
            self._log_deduped_issue(
                channel="skew_update_error",
                message=f"SKEW update error: {e}",
                level="error",
                emit_error=True,
            )
            updated_metrics["SKEW"] = self.current_metrics.get("SKEW", 125.5)
            return False

    def _update_pca_metrics(self, updated_metrics: dict, errors: list) -> bool:
        """Update PCA proxy and IV-surface metrics."""
        proxy_success = False
        iv_success = False

        try:
            if self.pca_signal_engine is None:
                raise RuntimeError("PCA signal engine unavailable")

            proxy_snapshot = self.pca_signal_engine.get_proxy_snapshot()
            updated_metrics["PCA-PROXY"] = float(proxy_snapshot.signal_value)
            updated_metrics["PCA-PROXY_CHANGE"] = float(proxy_snapshot.change)
            updated_metrics["PCA-PROXY_DETAILS"] = {
                "source": proxy_snapshot.source,
                "status": proxy_snapshot.status,
                "explained_variance": proxy_snapshot.explained_variance,
                "spectral_gap": proxy_snapshot.spectral_gap,
                "dispersion_score": proxy_snapshot.dispersion_score,
                "universe_size": proxy_snapshot.universe_size,
                "confidence": proxy_snapshot.confidence,
                "timestamp": proxy_snapshot.timestamp.isoformat(),
                "details": proxy_snapshot.details or {},
            }
            proxy_success = proxy_snapshot.status == "live"
        except Exception as e:
            errors.append(f"PCA-PROXY update error: {e}")
            self._log_deduped_issue(
                channel="pca_proxy_update_error",
                message=f"PCA-PROXY update error: {e}",
                level="warning",
            )
            updated_metrics["PCA-PROXY"] = self.current_metrics.get("PCA-PROXY", 0.0)
            updated_metrics["PCA-PROXY_CHANGE"] = 0.0
            updated_metrics["PCA-PROXY_DETAILS"] = self.current_metrics.get("PCA-PROXY_DETAILS", {})

        try:
            if self.pca_signal_engine is None:
                raise RuntimeError("PCA signal engine unavailable")

            iv_snapshot = self.pca_signal_engine.get_iv_snapshot()
            updated_metrics["PCA-IV"] = float(iv_snapshot.signal_value)
            updated_metrics["PCA-IV_CHANGE"] = float(iv_snapshot.change)
            updated_metrics["PCA-IV_DETAILS"] = {
                "source": iv_snapshot.source,
                "status": iv_snapshot.status,
                "placeholder": iv_snapshot.placeholder,
                "explained_variance": iv_snapshot.explained_variance,
                "spectral_gap": iv_snapshot.spectral_gap,
                "dispersion_score": iv_snapshot.dispersion_score,
                "universe_size": iv_snapshot.universe_size,
                "confidence": iv_snapshot.confidence,
                "timestamp": iv_snapshot.timestamp.isoformat(),
                "details": iv_snapshot.details or {},
            }
            iv_success = iv_snapshot.status == "live"
        except Exception as e:
            errors.append(f"PCA-IV update error: {e}")
            self._log_deduped_issue(
                channel="pca_iv_update_error",
                message=f"PCA-IV update error: {e}",
                level="warning",
            )
            updated_metrics["PCA-IV"] = self.current_metrics.get("PCA-IV", 0.0)
            updated_metrics["PCA-IV_CHANGE"] = 0.0
            updated_metrics["PCA-IV_DETAILS"] = self.current_metrics.get("PCA-IV_DETAILS", {})

        return proxy_success or iv_success

    def _update_fred_metrics(self, updated_metrics: dict, errors: list) -> bool:
        """Update FRED macro metrics (10Y yield, yield curve slope, yield curve inversion flag)"""
        try:
            if self.fred_client:
                snap = self.fred_client.get_snapshot()
                updated_metrics["YIELD_10Y"]      = snap.get("yield_10y", float("nan"))
                updated_metrics["YIELD_10Y_PREV"] = snap.get("yield_10y_prev", float("nan"))
                updated_metrics["YIELD_SLOPE"]    = snap.get("spread_10y_2y", float("nan"))
                updated_metrics["YIELD_INVERTED"]  = snap.get("yield_curve_inverted", False)
                self.fred_updated.emit(snap)
                if "FRED" in self.metric_quality:
                    q = self.metric_quality["FRED"]
                    q.last_successful_update = datetime.now(UTC)
                    q.data_points += 1
                    q.quality_score = min(1.0, q.quality_score + 0.01)
                return True
            else:
                for key in ("YIELD_10Y", "YIELD_SLOPE", "YIELD_INVERTED"):
                    updated_metrics[key] = self.current_metrics.get(key, float("nan"))
                return False
        except Exception as e:
            errors.append(f"FRED update error: {e}")
            self._log_deduped_issue(
                channel="fred_update_error",
                message=f"FRED update error: {e}",
                level="error",
                emit_error=True,
            )
            for key in ("YIELD_10Y", "YIELD_SLOPE", "YIELD_INVERTED"):
                updated_metrics[key] = self.current_metrics.get(key, float("nan"))
            return False

    def _update_sentiment_metrics(self, updated_metrics: dict, errors: list) -> bool:
        """Update AAII and NAAIM investor sentiment metrics"""
        try:
            if self.sentiment_scraper:
                snap = self.sentiment_scraper.get_snapshot()
                updated_metrics["AAII_BULLISH"]    = snap.get("aaii_bullish",    float("nan"))
                updated_metrics["AAII_BEARISH"]    = snap.get("aaii_bearish",    float("nan"))
                updated_metrics["NAAIM_EXPOSURE"]  = snap.get("naaim_exposure",  float("nan"))
                self.sentiment_updated.emit(snap)
                if "SENTIMENT" in self.metric_quality:
                    q = self.metric_quality["SENTIMENT"]
                    q.last_successful_update = datetime.now(UTC)
                    q.data_points += 1
                    q.quality_score = min(1.0, q.quality_score + 0.01)
                return True
            else:
                for key in ("AAII_BULLISH", "AAII_BEARISH", "NAAIM_EXPOSURE"):
                    updated_metrics[key] = self.current_metrics.get(key, float("nan"))
                return False
        except Exception as e:
            errors.append(f"Sentiment update error: {e}")
            self._log_deduped_issue(
                channel="sentiment_update_error",
                message=f"Sentiment update error: {e}",
                level="error",
                emit_error=True,
            )
            for key in ("AAII_BULLISH", "AAII_BEARISH", "NAAIM_EXPOSURE"):
                updated_metrics[key] = self.current_metrics.get(key, float("nan"))
            return False

    def _update_market_intel_metrics(self, updated_metrics: dict, errors: list) -> bool:
        """Update S15 market-intelligence metrics: Adanos social + AV macro news."""
        from Tradov.TradovS_Signals.TradovS15_MarketIntelClient import (
            ADANOS_SENTIMENT,
            NEWS_FLOW_EQUITIES,
            NEWS_FLOW_MACRO,
            NEWS_FLOW_VERDICT,
            NEWS_FLOW_HEADLINE,
        )
        _defaults = {
            ADANOS_SENTIMENT: self.current_metrics.get(ADANOS_SENTIMENT, {}),
            NEWS_FLOW_EQUITIES: self.current_metrics.get(NEWS_FLOW_EQUITIES, float("nan")),
            NEWS_FLOW_MACRO: self.current_metrics.get(NEWS_FLOW_MACRO, float("nan")),
            NEWS_FLOW_VERDICT: self.current_metrics.get(NEWS_FLOW_VERDICT, "neutral"),
            NEWS_FLOW_HEADLINE: self.current_metrics.get(NEWS_FLOW_HEADLINE, ""),
        }
        try:
            if self.market_intel_client is None:
                updated_metrics.update(_defaults)
                return False
            snap = self.market_intel_client.get_snapshot()
            updated_metrics[ADANOS_SENTIMENT] = snap.get(ADANOS_SENTIMENT, {})
            updated_metrics[NEWS_FLOW_EQUITIES] = snap.get(NEWS_FLOW_EQUITIES, float("nan"))
            updated_metrics[NEWS_FLOW_MACRO] = snap.get(NEWS_FLOW_MACRO, float("nan"))
            updated_metrics[NEWS_FLOW_VERDICT] = snap.get(NEWS_FLOW_VERDICT, "neutral")
            updated_metrics[NEWS_FLOW_HEADLINE] = snap.get(NEWS_FLOW_HEADLINE, "")
            if "MARKET_INTEL" in self.metric_quality:
                q = self.metric_quality["MARKET_INTEL"]
                q.last_successful_update = datetime.now(UTC)
                q.data_points += 1
                q.quality_score = min(1.0, q.quality_score + 0.01)
            return True
        except Exception as e:
            errors.append(f"Market intel update error: {e}")
            self._log_deduped_issue(
                channel="market_intel_update_error",
                message=f"Market intel update error: {e}",
                level="warning",
            )
            updated_metrics.update(_defaults)
            return False

    def _update_market_snapshot_text(self, updated_metrics: dict) -> None:
        """Refresh S16 LLM market snapshot text (no-op if TTL not expired)."""
        try:
            if self.snapshot_llm is None:
                updated_metrics["MARKET_SNAPSHOT_TEXT"] = self.current_metrics.get(
                    "MARKET_SNAPSHOT_TEXT", ""
                )
                return
            # Pass the partially-built updated_metrics merged with current so
            # the LLM has access to regime + market-intel keys populated above.
            merged: dict = {**self.current_metrics, **updated_metrics}
            text = self.snapshot_llm.get_snapshot_text(merged)
            updated_metrics["MARKET_SNAPSHOT_TEXT"] = text
        except Exception as e:
            self._log_deduped_issue(
                channel="snapshot_llm_error",
                message=f"LLM snapshot error: {e}",
                level="warning",
            )
            updated_metrics["MARKET_SNAPSHOT_TEXT"] = self.current_metrics.get(
                "MARKET_SNAPSHOT_TEXT", ""
            )

    def _update_eco_calendar_metrics(self, updated_metrics: dict, errors: list) -> bool:
        """Update S18 economic calendar stand-down signals."""
        from Tradov.TradovS_Signals.TradovS18_EconomicCalendar import (
            ECO_STAND_DOWN,
            ECO_NEXT_EVENT_NAME,
            ECO_NEXT_EVENT_MINUTES,
        )
        _defaults = {
            ECO_STAND_DOWN: self.current_metrics.get(ECO_STAND_DOWN, False),
            ECO_NEXT_EVENT_NAME: self.current_metrics.get(ECO_NEXT_EVENT_NAME, ""),
            ECO_NEXT_EVENT_MINUTES: self.current_metrics.get(ECO_NEXT_EVENT_MINUTES, float("nan")),
        }
        try:
            if self.eco_calendar is None:
                updated_metrics.update(_defaults)
                return False
            snap = self.eco_calendar.get_snapshot()
            updated_metrics[ECO_STAND_DOWN] = snap.get(ECO_STAND_DOWN, False)
            updated_metrics[ECO_NEXT_EVENT_NAME] = snap.get(ECO_NEXT_EVENT_NAME, "")
            updated_metrics[ECO_NEXT_EVENT_MINUTES] = snap.get(ECO_NEXT_EVENT_MINUTES, float("nan"))
            if "ECO_CALENDAR" in self.metric_quality:
                q = self.metric_quality["ECO_CALENDAR"]
                q.last_successful_update = datetime.now(UTC)
                q.data_points += 1
                q.quality_score = min(1.0, q.quality_score + 0.01)
            return True
        except Exception as e:
            errors.append(f"Economic calendar update error: {e}")
            self._log_deduped_issue(
                channel="eco_calendar_update_error",
                message=f"Economic calendar update error: {e}",
                level="warning",
            )
            updated_metrics.update(_defaults)
            return False

    def _update_tv_breadth_metrics(self, updated_metrics: dict, errors: list) -> bool:
        """Update TICK, TRIN, ADD breadth internals from TradingView."""
        if self._shutdown_in_progress():
            return False

        def _coerce_float(value: Any, default: float = float("nan")) -> float:
            try:
                if value is None:
                    return default
                return float(value)
            except (TypeError, ValueError):
                return default

        def _first_from(snapshot: dict[str, Any], keys: tuple[str, ...], default: float = float("nan")) -> float:  # noqa: E501
            for key in keys:
                if key in snapshot and snapshot.get(key) is not None:
                    return _coerce_float(snapshot.get(key), default)
            return default

        # Keep the expanded sector breadth keys stable on failures.
        sector_defaults = {
            "BREADTH_DEFENSIVE": self.current_metrics.get("BREADTH_DEFENSIVE", float("nan")),
            "BREADTH_CYCLICAL": self.current_metrics.get("BREADTH_CYCLICAL", float("nan")),
            "BREADTH_SPREAD": self.current_metrics.get("BREADTH_SPREAD", float("nan")),
            "SECTOR_ADV_DEC": self.current_metrics.get("SECTOR_ADV_DEC", float("nan")),
            "SECTOR_MOMENTUM_DISPERSION": self.current_metrics.get("SECTOR_MOMENTUM_DISPERSION", float("nan")),  # noqa: E501
            "PARTICIPATION_SCORE": self.current_metrics.get("PARTICIPATION_SCORE", float("nan")),
        }
        for key, value in sector_defaults.items():
            updated_metrics.setdefault(key, value)
        updated_metrics.setdefault("SECTOR_BREADTH", self.current_metrics.get("SECTOR_BREADTH", {}))

        try:
            if self.tv_client:
                snap = self.tv_client.get_snapshot()
                updated_metrics["TICK"] = snap.get("tick", float("nan"))
                updated_metrics["ADD"]  = snap.get("add",  float("nan"))
                updated_metrics["TRIN"] = snap.get("trin", float("nan"))
                updated_metrics["VOLD"] = snap.get("vold", float("nan"))
                updated_metrics["BREADTH_REGIME"] = snap.get("breadth_regime", "neutral")

                # NYMO proxy: EMA(19) − EMA(39) of ADD (McClellan Oscillator approximation)
                _add_val = updated_metrics["ADD"]
                if not math.isnan(_add_val):
                    if math.isnan(self._nymo_ema_fast):
                        self._nymo_ema_fast = _add_val
                        self._nymo_ema_slow = _add_val
                    else:
                        self._nymo_ema_fast = (
                            self._nymo_alpha_fast * _add_val
                            + (1.0 - self._nymo_alpha_fast) * self._nymo_ema_fast
                        )
                        self._nymo_ema_slow = (
                            self._nymo_alpha_slow * _add_val
                            + (1.0 - self._nymo_alpha_slow) * self._nymo_ema_slow
                        )
                    updated_metrics["NYMO"] = round(
                        self._nymo_ema_fast - self._nymo_ema_slow, 1
                    )
                    # Persist EMA state so the NYMO warm-up survives process restarts.
                    try:
                        _nymo_save = pathlib.Path("data/cache/nymo_ema_state.json")
                        _nymo_save.parent.mkdir(parents=True, exist_ok=True)
                        _nymo_save.write_text(json.dumps({
                            "ema_fast": self._nymo_ema_fast,
                            "ema_slow": self._nymo_ema_slow,
                        }))
                    except Exception:
                        pass
                else:
                    updated_metrics["NYMO"] = self.current_metrics.get("NYMO", float("nan"))

                defensive = _first_from(
                    snap,
                    (
                        "breadth_defensive",
                        "sector_defensive_breadth",
                        "defensive_breadth",
                        "defensive_score",
                    ),
                    updated_metrics["BREADTH_DEFENSIVE"],
                )
                cyclical = _first_from(
                    snap,
                    (
                        "breadth_cyclical",
                        "sector_cyclical_breadth",
                        "cyclical_breadth",
                        "cyclical_score",
                    ),
                    updated_metrics["BREADTH_CYCLICAL"],
                )
                spread = cyclical - defensive
                adv_dec = _first_from(
                    snap,
                    ("sector_adv_dec", "adv_dec", "sector_ad_line", "add"),
                    _coerce_float(updated_metrics.get("ADD", float("nan"))),
                )
                momentum_dispersion = _first_from(
                    snap,
                    ("sector_momentum_dispersion", "breadth_dispersion", "dispersion"),
                    abs(spread) if not math.isnan(spread) else float("nan"),
                )
                participation = _first_from(
                    snap,
                    ("participation_score", "breadth_participation", "sector_participation"),
                    float("nan"),
                )
                if math.isnan(participation):
                    tick = _coerce_float(updated_metrics.get("TICK", float("nan")))
                    trin = _coerce_float(updated_metrics.get("TRIN", float("nan")))
                    if not math.isnan(tick) and not math.isnan(trin):
                        participation = max(0.0, min(100.0, 50.0 + (tick / 40.0) - (trin - 1.0) * 20.0))  # noqa: E501

                updated_metrics["BREADTH_DEFENSIVE"] = defensive
                updated_metrics["BREADTH_CYCLICAL"] = cyclical
                updated_metrics["BREADTH_SPREAD"] = spread
                updated_metrics["SECTOR_ADV_DEC"] = adv_dec
                updated_metrics["SECTOR_MOMENTUM_DISPERSION"] = momentum_dispersion
                updated_metrics["PARTICIPATION_SCORE"] = participation
                updated_metrics["SECTOR_BREADTH"] = {
                    "defensive": defensive,
                    "cyclical": cyclical,
                    "spread": spread,
                    "adv_dec": adv_dec,
                    "momentum_dispersion": momentum_dispersion,
                    "participation_score": participation,
                    "breadth_regime": updated_metrics["BREADTH_REGIME"],
                    "snapshot_ts": snap.get("snapshot_ts") or datetime.now(UTC).isoformat(),
                    "source": "TradovS11_TradingViewInternals",
                }

                if "SECTOR_BREADTH" in self.metric_quality:
                    q = self.metric_quality["SECTOR_BREADTH"]
                    q.last_successful_update = datetime.now(UTC)
                    q.data_points += 1
                    q.quality_score = min(1.0, q.quality_score + 0.01)
                if "BREADTH" in self.metric_quality:
                    q = self.metric_quality["BREADTH"]
                    q.last_successful_update = datetime.now(UTC)
                    q.data_points += 1
                    q.quality_score = min(1.0, q.quality_score + 0.01)
                self.breadth_updated.emit(snap)
                return True
            else:
                for key in ("TICK", "ADD", "TRIN", "NYMO", "VOLD"):
                    updated_metrics[key] = self.current_metrics.get(key, float("nan"))
                updated_metrics["BREADTH_REGIME"] = self.current_metrics.get("BREADTH_REGIME", "neutral")  # noqa: E501
                updated_metrics["SECTOR_BREADTH"] = self.current_metrics.get("SECTOR_BREADTH", {})
                return False
        except Exception as e:
            errors.append(f"Breadth update error: {e}")
            self._log_deduped_issue(
                channel="breadth_update_error",
                message=f"Breadth update error: {e}",
                level="error",
                emit_error=True,
            )
            for key in ("TICK", "ADD", "TRIN", "NYMO", "VOLD"):
                updated_metrics[key] = self.current_metrics.get(key, float("nan"))
            updated_metrics["BREADTH_REGIME"] = self.current_metrics.get("BREADTH_REGIME", "neutral")  # noqa: E501
            updated_metrics["SECTOR_BREADTH"] = self.current_metrics.get("SECTOR_BREADTH", {})
            return False

    def _build_data_quality_feed(self, updated_metrics: dict[str, Any], errors: list[str]) -> dict[str, Any]:  # noqa: E501
        """Build a normalized data-quality/SLO envelope for downstream consumers."""
        now = datetime.now(UTC)
        stale_threshold_sec = int(self.config.get("data_quality", {}).get("stale_after_sec", 180))
        buckets: dict[str, dict[str, Any]] = {}
        stale_count = 0

        for name, quality in self.metric_quality.items():
            last_successful_update = quality.last_successful_update
            if last_successful_update.tzinfo is None:
                age_sec = (datetime.now() - last_successful_update).total_seconds()  # tradov: naive-ok
            else:
                age_sec = (now - last_successful_update.astimezone(UTC)).total_seconds()
            stale = age_sec > stale_threshold_sec
            if stale:
                stale_count += 1
            buckets[name] = {
                "quality_score": quality.quality_score,
                "data_points": quality.data_points,
                "error_count": quality.error_count,
                "last_successful_update": quality.last_successful_update.isoformat(),
                "age_sec": round(age_sec, 1),
                "source_available": quality.source_available,
                "stale": stale,
            }

        overall_quality = float(np.mean([q.quality_score for q in self.metric_quality.values()])) if self.metric_quality else 0.0  # noqa: E501
        total_buckets = len(buckets)
        freshness_score = 1.0 if total_buckets == 0 else max(0.0, 1.0 - (stale_count / total_buckets))  # noqa: E501

        slo_targets = {
            "overall_quality_min": float(self.config.get("data_quality", {}).get("overall_quality_min", 0.75)),  # noqa: E501
            "freshness_min": float(self.config.get("data_quality", {}).get("freshness_min", 0.70)),
        }
        slo_status = {
            "overall_quality_ok": overall_quality >= slo_targets["overall_quality_min"],
            "freshness_ok": freshness_score >= slo_targets["freshness_min"],
        }
        slo_status["all_ok"] = all(slo_status.values())

        return {
            "feed": "data_quality",
            "version": "1.0",
            "published_ts": now.isoformat(),
            "data": {
                "overall_quality": overall_quality,
                "freshness_score": freshness_score,
                "stale_bucket_count": stale_count,
                "total_bucket_count": total_buckets,
                "error_count": len(errors),
                "slo_targets": slo_targets,
                "slo_status": slo_status,
                "quality_buckets": buckets,
                "last_update_interval_sec": self.current_update_interval,
                "update_keys": sorted(updated_metrics.keys()),
            },
        }

    def _update_quality_metrics(self, updated_metrics: dict, errors: list):
        """Update quality tracking for all metrics"""
        for metric_name, _value in updated_metrics.items():
            if metric_name in self.metric_quality:
                quality = self.metric_quality[metric_name]

                # Check if this metric had errors
                metric_had_error = any(metric_name.lower() in error.lower() for error in errors)

                if metric_had_error:
                    quality.error_count += 1
                    quality.quality_score = max(0.0, quality.quality_score - 0.1)
                else:
                    quality.last_successful_update = datetime.now(UTC)
                    quality.data_points += 1
                    # Gradually improve quality score on successful updates
                    quality.quality_score = min(1.0, quality.quality_score + 0.01)

    def _analyze_and_adjust_frequency(self, metrics: dict):
        """Analyze market stress and adjust update frequency"""
        swan_score = metrics.get("SWAN", 1.0)

        # Determine stress level
        if swan_score >= SWAN_HIGH_STRESS:
            new_stress_level = StressLevel.CRISIS
            new_interval = FAST_UPDATE
        elif swan_score >= SWAN_MEDIUM_STRESS:
            new_stress_level = StressLevel.HIGH
            new_interval = FAST_UPDATE
        elif swan_score >= 1.5:
            new_stress_level = StressLevel.MEDIUM
            new_interval = UPDATE_INTERVAL
        else:
            new_stress_level = StressLevel.LOW
            new_interval = SLOW_UPDATE

        # Update stress level if changed
        if new_stress_level != self.current_stress_level:
            self.current_stress_level = new_stress_level
            self.stress_history.append((datetime.now(UTC), new_stress_level))
            self.stress_level_changed.emit(new_stress_level.value)

            self.logger.debug("🎯 Market stress level changed to: %s", new_stress_level.value.upper())  # noqa: E501

        # Adjust update frequency if needed
        if new_interval != self.current_update_interval:
            self.current_update_interval = new_interval
            self.update_interval_change_requested.emit(int(new_interval))
            self.last_frequency_change = datetime.now(UTC)

            self.logger.debug("⚡ Update frequency adjusted to %ss (stress: %s)", new_interval, new_stress_level.value)  # noqa: E501

    @Slot(int)
    def _apply_update_interval(self, new_interval: int) -> None:
        """Apply the update timer interval on the orchestrator's Qt thread."""
        self.update_timer.setInterval(int(new_interval) * 1000)

    def _format_metrics(self, metrics: dict) -> dict:
        """Format metrics for display with enhanced information"""
        timestamp = datetime.now(UTC)

        def _is_nan(value: Any) -> bool:
            return isinstance(value, float) and math.isnan(value)

        def _format_ivr(value: Any) -> str:
            return "---" if _is_nan(value) else f"{float(value):.0f}"

        def _format_atm_iv(value: Any) -> str:
            return "---" if _is_nan(value) else f"{float(value):.1f}%"

        def _format_vrp(value: Any) -> str:
            return "---" if _is_nan(value) else f"{float(value):+.1f}"

        def _format_signed_float(value: Any, digits: int = 2) -> str:
            return "---" if _is_nan(value) else f"{float(value):+.{digits}f}"

        pca_iv_details = metrics.get("PCA-IV_DETAILS", {})
        if not isinstance(pca_iv_details, dict):
            pca_iv_details = {}
        pca_iv_nested = pca_iv_details.get("details", {})
        if not isinstance(pca_iv_nested, dict):
            pca_iv_nested = {}
        pca_iv_status = str(pca_iv_details.get("status") or "").lower()
        pca_iv_phase = str(pca_iv_nested.get("phase") or "").lower()
        if pca_iv_status == "live":
            pca_iv_formatted = _format_signed_float(metrics.get("PCA-IV", float("nan")))
        elif pca_iv_phase == "history-seeding":
            pca_iv_formatted = "SEED"
        elif pca_iv_status == "fallback":
            pca_iv_formatted = "HOLD"
        else:
            pca_iv_formatted = "PEND"

        def _format_float(value: Any, digits: int = 2, suffix: str = "") -> str:
            return "---" if _is_nan(value) else f"{float(value):.{digits}f}{suffix}"

        def _resolve_quality_bucket_state(bucket_name: str) -> dict[str, Any] | None:
            feed = metrics.get("DATA_QUALITY_FEED", {})
            if isinstance(feed, dict):
                feed_data = feed.get("data", {})
                if isinstance(feed_data, dict):
                    quality_buckets = feed_data.get("quality_buckets", {})
                    if isinstance(quality_buckets, dict):
                        bucket_state = quality_buckets.get(bucket_name)
                        if isinstance(bucket_state, dict):
                            return bucket_state

            quality = self.metric_quality.get(bucket_name)
            if quality is None:
                return None

            stale_threshold_sec = int(self.config.get("data_quality", {}).get("stale_after_sec", 180))
            now_utc = datetime.now(UTC)
            last_successful_update = quality.last_successful_update
            if last_successful_update.tzinfo is None:
                age_sec = (datetime.now() - last_successful_update).total_seconds()  # tradov: naive-ok
            else:
                age_sec = (now_utc - last_successful_update.astimezone(UTC)).total_seconds()

            return {
                "quality_score": quality.quality_score,
                "stale": age_sec > stale_threshold_sec,
            }

        formatted_metrics = {
            "GEX": {
                "value": metrics.get("GEX", 0),
                "formatted": f"{metrics.get('GEX', 0):.1f}B",
                "timestamp": timestamp,
                "quality": self.metric_quality['GEX'].quality_score
            },
            "DEX": {
                "value": metrics.get("DEX", 0),
                "formatted": f"{metrics.get('DEX', 0):.0f}M",
                "timestamp": timestamp,
                "quality": self.metric_quality['DEX'].quality_score
            },
            "OGL": {
                "value": metrics.get("OGL", 0),
                "formatted": f"{metrics.get('OGL', 0):.2f}",
                "timestamp": timestamp,
                "quality": self.metric_quality['OGL'].quality_score
            },
            "DIX": {
                "value": metrics.get("DIX", 0),
                "formatted": f"{metrics.get('DIX', 0):.1f}%",
                "timestamp": timestamp,
                "quality": self.metric_quality['DIX'].quality_score
            },
            "SWAN": {
                "value": metrics.get("SWAN", 0),
                "formatted": f"{metrics.get('SWAN', 0):.2f}",
                "timestamp": timestamp,
                "quality": self.metric_quality['SWAN'].quality_score
            },
            "SKEW": {
                "value": metrics.get("SKEW", 0),
                "formatted": f"{metrics.get('SKEW', 0):.1f}",
                "timestamp": timestamp,
                "quality": self.metric_quality['SKEW'].quality_score
            },
            "PCA-PROXY": {
                "value": metrics.get("PCA-PROXY", 0.0),
                "formatted": _format_float(metrics.get("PCA-PROXY", 0.0), 2),
                "timestamp": timestamp,
                "quality": self.metric_quality['PCA-PROXY'].quality_score,
                "change": metrics.get("PCA-PROXY_CHANGE", 0.0),
                "details": metrics.get("PCA-PROXY_DETAILS", {}),
            },
            "PCA-IV": {
                "value": metrics.get("PCA-IV", 0.0),
                "formatted": pca_iv_formatted,
                "timestamp": timestamp,
                "quality": self.metric_quality['PCA-IV'].quality_score,
                "change": metrics.get("PCA-IV_CHANGE", 0.0),
                "details": metrics.get("PCA-IV_DETAILS", {}),
            },
            "VEX": {
                "value": metrics.get("VEX", 0),
                "formatted": f"{metrics.get('VEX', 0):.1f}M",
                "timestamp": timestamp,
                "quality": self.metric_quality['VEX'].quality_score
            },
            "CHEX": {
                "value": metrics.get("CHEX", 0),
                "formatted": f"{metrics.get('CHEX', 0):.2f}",
                "timestamp": timestamp,
                "quality": self.metric_quality['CHEX'].quality_score
            },
            "YIELD_10Y": {
                "value": metrics.get("YIELD_10Y", float("nan")),
                "formatted": f"{metrics.get('YIELD_10Y', float('nan')):.2f}%",
                "timestamp": timestamp,
                "quality": self.metric_quality['FRED'].quality_score,
                # Day-over-day change from FRED's two most-recent GS10 observations.
                # Included so G05 can display a real change instead of always +0.00.
                "change": (
                    float(metrics.get("YIELD_10Y", float("nan")))
                    - float(metrics.get("YIELD_10Y_PREV", float("nan")))
                    if not (math.isnan(float(metrics.get("YIELD_10Y", float("nan"))))
                            or math.isnan(float(metrics.get("YIELD_10Y_PREV", float("nan")))))
                    else float("nan")
                ),
            },
            "YIELD_SLOPE": {
                "value": metrics.get("YIELD_SLOPE", float("nan")),
                "formatted": f"{metrics.get('YIELD_SLOPE', float('nan')):.2f}",
                "timestamp": timestamp,
                "quality": self.metric_quality['FRED'].quality_score
            },
            "AAII_BULLISH": {
                "value": metrics.get("AAII_BULLISH", float("nan")),
                "formatted": f"{metrics.get('AAII_BULLISH', float('nan')):.1f}%",
                "timestamp": timestamp,
                "quality": self.metric_quality['SENTIMENT'].quality_score
            },
            "NAAIM_EXPOSURE": {
                "value": metrics.get("NAAIM_EXPOSURE", float("nan")),
                "formatted": f"{metrics.get('NAAIM_EXPOSURE', float('nan')):.1f}",
                "timestamp": timestamp,
                "quality": self.metric_quality['SENTIMENT'].quality_score
            },
            "TICK": {
                "value": metrics.get("TICK", float("nan")),
                "formatted": f"{metrics.get('TICK', float('nan')):.0f}",
                "timestamp": timestamp,
                "quality": self.metric_quality['BREADTH'].quality_score
            },
            "ADD": {
                "value": metrics.get("ADD", float("nan")),
                "formatted": f"{metrics.get('ADD', float('nan')):.0f}",
                "timestamp": timestamp,
                "quality": self.metric_quality['BREADTH'].quality_score
            },
            "TRIN": {
                "value": metrics.get("TRIN", float("nan")),
                "formatted": f"{metrics.get('TRIN', float('nan')):.2f}",
                "timestamp": timestamp,
                "quality": self.metric_quality['BREADTH'].quality_score
            },
            "NYMO": {
                "value": metrics.get("NYMO", float("nan")),
                "formatted": f"{metrics.get('NYMO', float('nan')):.1f}",
                "timestamp": timestamp,
                "quality": self.metric_quality['BREADTH'].quality_score
            },
            "VOLD": {
                "value": metrics.get("VOLD", float("nan")),
                "formatted": f"{metrics.get('VOLD', float('nan')):.0f}",
                "timestamp": timestamp,
                "quality": self.metric_quality['BREADTH'].quality_score
            },
            "BREADTH_REGIME": {
                "value": metrics.get("BREADTH_REGIME", "neutral"),
                "formatted": metrics.get("BREADTH_REGIME", "neutral").replace("_", " ").title(),
                "timestamp": timestamp,
                "quality": self.metric_quality['BREADTH'].quality_score
            },
            "BREADTH_DEFENSIVE": {
                "value": metrics.get("BREADTH_DEFENSIVE", float("nan")),
                "formatted": _format_float(metrics.get("BREADTH_DEFENSIVE", float("nan")), 1),
                "timestamp": timestamp,
                "quality": self.metric_quality['SECTOR_BREADTH'].quality_score
            },
            "BREADTH_CYCLICAL": {
                "value": metrics.get("BREADTH_CYCLICAL", float("nan")),
                "formatted": _format_float(metrics.get("BREADTH_CYCLICAL", float("nan")), 1),
                "timestamp": timestamp,
                "quality": self.metric_quality['SECTOR_BREADTH'].quality_score
            },
            "BREADTH_SPREAD": {
                "value": metrics.get("BREADTH_SPREAD", float("nan")),
                "formatted": _format_float(metrics.get("BREADTH_SPREAD", float("nan")), 1),
                "timestamp": timestamp,
                "quality": self.metric_quality['SECTOR_BREADTH'].quality_score
            },
            "SECTOR_ADV_DEC": {
                "value": metrics.get("SECTOR_ADV_DEC", float("nan")),
                "formatted": _format_float(metrics.get("SECTOR_ADV_DEC", float("nan")), 0),
                "timestamp": timestamp,
                "quality": self.metric_quality['SECTOR_BREADTH'].quality_score
            },
            "SECTOR_MOMENTUM_DISPERSION": {
                "value": metrics.get("SECTOR_MOMENTUM_DISPERSION", float("nan")),
                "formatted": _format_float(metrics.get("SECTOR_MOMENTUM_DISPERSION", float("nan")), 2),  # noqa: E501
                "timestamp": timestamp,
                "quality": self.metric_quality['SECTOR_BREADTH'].quality_score
            },
            "PARTICIPATION_SCORE": {
                "value": metrics.get("PARTICIPATION_SCORE", float("nan")),
                "formatted": _format_float(metrics.get("PARTICIPATION_SCORE", float("nan")), 1),
                "timestamp": timestamp,
                "quality": self.metric_quality['SECTOR_BREADTH'].quality_score
            },
            "SECTOR_BREADTH": {
                "value": metrics.get("SECTOR_BREADTH", {}),
                "formatted": str(metrics.get("SECTOR_BREADTH", {}).get("breadth_regime", "---")),
                "timestamp": timestamp,
                "quality": self.metric_quality['SECTOR_BREADTH'].quality_score
            },
            "IVR": {
                "value": metrics.get("IVR", float("nan")),
                "formatted": _format_ivr(metrics.get("IVR", float("nan"))),
                "timestamp": timestamp,
                "quality": self.metric_quality['OPTIONS'].quality_score
            },
            "ATM_IV": {
                "value": metrics.get("ATM_IV", float("nan")),
                "formatted": _format_atm_iv(metrics.get("ATM_IV", float("nan"))),
                "timestamp": timestamp,
                "quality": self.metric_quality['OPTIONS'].quality_score
            },
            "VRP": {
                "value": metrics.get("VRP", float("nan")),
                "formatted": _format_vrp(metrics.get("VRP", float("nan"))),
                "timestamp": timestamp,
                "quality": self.metric_quality['OPTIONS'].quality_score
            },
            "ATM_IV_0DTE": {
                "value": metrics.get("ATM_IV_0DTE", float("nan")),
                "formatted": _format_atm_iv(metrics.get("ATM_IV_0DTE", float("nan"))),
                "timestamp": timestamp,
                "quality": self.metric_quality['VOL_SURFACE'].quality_score
            },
            "ATM_IV_1DTE": {
                "value": metrics.get("ATM_IV_1DTE", float("nan")),
                "formatted": _format_atm_iv(metrics.get("ATM_IV_1DTE", float("nan"))),
                "timestamp": timestamp,
                "quality": self.metric_quality['VOL_SURFACE'].quality_score
            },
            "ATM_IV_7DTE": {
                "value": metrics.get("ATM_IV_7DTE", float("nan")),
                "formatted": _format_atm_iv(metrics.get("ATM_IV_7DTE", float("nan"))),
                "timestamp": timestamp,
                "quality": self.metric_quality['VOL_SURFACE'].quality_score
            },
            "ATM_IV_30DTE": {
                "value": metrics.get("ATM_IV_30DTE", float("nan")),
                "formatted": _format_atm_iv(metrics.get("ATM_IV_30DTE", float("nan"))),
                "timestamp": timestamp,
                "quality": self.metric_quality['VOL_SURFACE'].quality_score
            },
            "TERM_SLOPE_0_7": {
                "value": metrics.get("TERM_SLOPE_0_7", float("nan")),
                "formatted": _format_float(metrics.get("TERM_SLOPE_0_7", float("nan")), 2),
                "timestamp": timestamp,
                "quality": self.metric_quality['VOL_SURFACE'].quality_score
            },
            "TERM_SLOPE_7_30": {
                "value": metrics.get("TERM_SLOPE_7_30", float("nan")),
                "formatted": _format_float(metrics.get("TERM_SLOPE_7_30", float("nan")), 2),
                "timestamp": timestamp,
                "quality": self.metric_quality['VOL_SURFACE'].quality_score
            },
            "RR_25D": {
                "value": metrics.get("RR_25D", float("nan")),
                "formatted": _format_float(metrics.get("RR_25D", float("nan")), 3),
                "timestamp": timestamp,
                "quality": self.metric_quality['VOL_SURFACE'].quality_score
            },
            "FLY_25D": {
                "value": metrics.get("FLY_25D", float("nan")),
                "formatted": _format_float(metrics.get("FLY_25D", float("nan")), 3),
                "timestamp": timestamp,
                "quality": self.metric_quality['VOL_SURFACE'].quality_score
            },
            "SURFACE_CONFIDENCE": {
                "value": metrics.get("SURFACE_CONFIDENCE", float("nan")),
                "formatted": _format_float(metrics.get("SURFACE_CONFIDENCE", float("nan")), 2),
                "timestamp": timestamp,
                "quality": self.metric_quality['VOL_SURFACE'].quality_score
            },
            "ZERO_GAMMA": {
                "value": metrics.get("ZERO_GAMMA", float("nan")),
                "formatted": _format_float(metrics.get("ZERO_GAMMA", float("nan")), 2, ""),
                "timestamp": timestamp,
                "quality": self.metric_quality['DEALER_FLOW'].quality_score
            },
            "WALL_CONFIDENCE": {
                "value": metrics.get("WALL_CONFIDENCE", float("nan")),
                "formatted": _format_float(metrics.get("WALL_CONFIDENCE", float("nan")), 2),
                "timestamp": timestamp,
                "quality": self.metric_quality['DEALER_FLOW'].quality_score
            },
            "VANNA_PRESSURE": {
                "value": metrics.get("VANNA_PRESSURE", float("nan")),
                "formatted": _format_float(metrics.get("VANNA_PRESSURE", float("nan")), 0),
                "timestamp": timestamp,
                "quality": self.metric_quality['DEALER_FLOW'].quality_score
            },
            "CHARM_PRESSURE": {
                "value": metrics.get("CHARM_PRESSURE", float("nan")),
                "formatted": _format_float(metrics.get("CHARM_PRESSURE", float("nan")), 0),
                "timestamp": timestamp,
                "quality": self.metric_quality['DEALER_FLOW'].quality_score
            },
            "FLOW_IMBALANCE": {
                "value": metrics.get("FLOW_IMBALANCE", float("nan")),
                "formatted": _format_float(metrics.get("FLOW_IMBALANCE", float("nan")), 3),
                "timestamp": timestamp,
                "quality": self.metric_quality['DEALER_FLOW'].quality_score
            },
            "DEALER_FLOW": {
                "value": metrics.get("DEALER_FLOW", {}),
                "formatted": metrics.get("DEALER_FLOW", {}).get("dealer_position", "---"),
                "timestamp": timestamp,
                "quality": self.metric_quality['DEALER_FLOW'].quality_score
            },
            "LIQUIDITY_DIAGNOSTICS": {
                "value": metrics.get("LIQUIDITY_DIAGNOSTICS", {}),
                "formatted": f"{len(metrics.get('LIQUIDITY_DIAGNOSTICS', {}).get('data', {}).get('candidates', []))} candidates",  # noqa: E501
                "timestamp": timestamp,
                "quality": self.metric_quality['LIQUIDITY'].quality_score
            },
            "DATA_QUALITY_FEED": {
                "value": metrics.get("DATA_QUALITY_FEED", {}),
                "formatted": f"{(metrics.get('DATA_QUALITY_FEED', {}).get('data', {}).get('overall_quality', float('nan')) * 100.0):.0f}% healthy",  # noqa: E501
                "timestamp": timestamp,
                "quality": 1.0
            },
            # S15 - Market Intelligence
            "ADANOS_SENTIMENT": {
                "value": metrics.get("ADANOS_SENTIMENT", {}),
                "formatted": (metrics.get("ADANOS_SENTIMENT") or {}).get("trend", "neutral"),
                "timestamp": timestamp,
                "quality": self.metric_quality["MARKET_INTEL"].quality_score,
            },
            "NEWS_FLOW_EQUITIES": {
                "value": metrics.get("NEWS_FLOW_EQUITIES", float("nan")),
                "formatted": _format_float(metrics.get("NEWS_FLOW_EQUITIES", float("nan")), 3),
                "timestamp": timestamp,
                "quality": self.metric_quality["MARKET_INTEL"].quality_score,
            },
            "NEWS_FLOW_MACRO": {
                "value": metrics.get("NEWS_FLOW_MACRO", float("nan")),
                "formatted": _format_float(metrics.get("NEWS_FLOW_MACRO", float("nan")), 3),
                "timestamp": timestamp,
                "quality": self.metric_quality["MARKET_INTEL"].quality_score,
            },
            "NEWS_FLOW_VERDICT": {
                "value": metrics.get("NEWS_FLOW_VERDICT", "neutral"),
                "formatted": str(metrics.get("NEWS_FLOW_VERDICT", "neutral")).capitalize(),
                "timestamp": timestamp,
                "quality": self.metric_quality["MARKET_INTEL"].quality_score,
            },
            "NEWS_FLOW_HEADLINE": {
                "value": metrics.get("NEWS_FLOW_HEADLINE", ""),
                "formatted": str(metrics.get("NEWS_FLOW_HEADLINE", "")),
                "timestamp": timestamp,
                "quality": self.metric_quality["MARKET_INTEL"].quality_score,
            },
            # S16 - LLM market snapshot
            "MARKET_SNAPSHOT_TEXT": {
                "value": metrics.get("MARKET_SNAPSHOT_TEXT", ""),
                "formatted": str(metrics.get("MARKET_SNAPSHOT_TEXT", "")),
                "timestamp": timestamp,
                "quality": 1.0,
            },
            # S17 - Kalshi prediction markets
            # S18 - Economic calendar
            "ECO_STAND_DOWN": {
                "value": metrics.get("ECO_STAND_DOWN", False),
                "formatted": "STAND-DOWN" if metrics.get("ECO_STAND_DOWN", False) else "clear",
                "timestamp": timestamp,
                "quality": self.metric_quality["ECO_CALENDAR"].quality_score,
            },
            "ECO_NEXT_EVENT_NAME": {
                "value": metrics.get("ECO_NEXT_EVENT_NAME", ""),
                "formatted": str(metrics.get("ECO_NEXT_EVENT_NAME", "")),
                "timestamp": timestamp,
                "quality": self.metric_quality["ECO_CALENDAR"].quality_score,
            },
            "ECO_NEXT_EVENT_MINUTES": {
                "value": metrics.get("ECO_NEXT_EVENT_MINUTES", float("nan")),
                "formatted": _format_float(
                    metrics.get("ECO_NEXT_EVENT_MINUTES", float("nan")), 0
                ),
                "timestamp": timestamp,
                "quality": self.metric_quality["ECO_CALENDAR"].quality_score,
            },
            "meta": {
                "update_frequency": self.current_update_interval,
                "stress_level": self.current_stress_level.value,
                "connection_status": self.ib_connected,
                "last_update": timestamp.isoformat()
            }
        }

        quality_bucket_by_metric = {
            "GEX": "GEX",
            "DEX": "DEX",
            "OGL": "OGL",
            "DIX": "DIX",
            "SWAN": "SWAN",
            "SKEW": "SKEW",
            "PCA-PROXY": "PCA-PROXY",
            "PCA-IV": "PCA-IV",
            "VEX": "VEX",
            "CHEX": "CHEX",
            "YIELD_10Y": "FRED",
            "YIELD_SLOPE": "FRED",
            "AAII_BULLISH": "SENTIMENT",
            "NAAIM_EXPOSURE": "SENTIMENT",
            "TICK": "BREADTH",
            "ADD": "BREADTH",
            "TRIN": "BREADTH",
            "NYMO": "BREADTH",
            "VOLD": "BREADTH",
            "BREADTH_REGIME": "BREADTH",
            "BREADTH_DEFENSIVE": "SECTOR_BREADTH",
            "BREADTH_CYCLICAL": "SECTOR_BREADTH",
            "BREADTH_SPREAD": "SECTOR_BREADTH",
            "SECTOR_ADV_DEC": "SECTOR_BREADTH",
            "SECTOR_MOMENTUM_DISPERSION": "SECTOR_BREADTH",
            "PARTICIPATION_SCORE": "SECTOR_BREADTH",
            "SECTOR_BREADTH": "SECTOR_BREADTH",
            "IVR": "OPTIONS",
            "ATM_IV": "OPTIONS",
            "VRP": "OPTIONS",
            "ATM_IV_0DTE": "VOL_SURFACE",
            "ATM_IV_1DTE": "VOL_SURFACE",
            "ATM_IV_7DTE": "VOL_SURFACE",
            "ATM_IV_30DTE": "VOL_SURFACE",
            "TERM_SLOPE_0_7": "VOL_SURFACE",
            "TERM_SLOPE_7_30": "VOL_SURFACE",
            "RR_25D": "VOL_SURFACE",
            "FLY_25D": "VOL_SURFACE",
            "SURFACE_CONFIDENCE": "VOL_SURFACE",
            "ZERO_GAMMA": "DEALER_FLOW",
            "WALL_CONFIDENCE": "DEALER_FLOW",
            "VANNA_PRESSURE": "DEALER_FLOW",
            "CHARM_PRESSURE": "DEALER_FLOW",
            "FLOW_IMBALANCE": "DEALER_FLOW",
            "DEALER_FLOW": "DEALER_FLOW",
            "LIQUIDITY_DIAGNOSTICS": "LIQUIDITY",
            "ADANOS_SENTIMENT": "MARKET_INTEL",
            "NEWS_FLOW_EQUITIES": "MARKET_INTEL",
            "NEWS_FLOW_MACRO": "MARKET_INTEL",
            "NEWS_FLOW_VERDICT": "MARKET_INTEL",
            "NEWS_FLOW_HEADLINE": "MARKET_INTEL",
            "ECO_STAND_DOWN": "ECO_CALENDAR",
            "ECO_NEXT_EVENT_NAME": "ECO_CALENDAR",
            "ECO_NEXT_EVENT_MINUTES": "ECO_CALENDAR",
        }

        for metric_name, bucket_name in quality_bucket_by_metric.items():
            entry = formatted_metrics.get(metric_name)
            if not isinstance(entry, dict):
                continue

            bucket_state = _resolve_quality_bucket_state(bucket_name)
            if not isinstance(bucket_state, dict):
                continue

            entry["quality_bucket"] = bucket_name
            entry["stale"] = bool(bucket_state.get("stale", False))

            bucket_quality = bucket_state.get("quality_score")
            if isinstance(bucket_quality, (int, float)) and math.isfinite(float(bucket_quality)):
                entry["quality"] = float(bucket_quality)

        return formatted_metrics

    def _add_to_history(self, snapshot: MetricSnapshot):
        """Add snapshot to history with size management"""
        self.metrics_history.append(snapshot)

        # Trim history if too large
        if len(self.metrics_history) > self.max_history_size:
            self.metrics_history = self.metrics_history[-self.max_history_size:]

    # ==========================================================================
    # PUBLIC ACCESS METHODS
    # ==========================================================================

    def get_all_metrics(self) -> dict:
        """Get all current metrics thread-safely"""
        with self._metrics_lock:
            return self.current_metrics.copy()

    def get_gex(self) -> float:
        """Get current GEX value"""
        with self._metrics_lock:
            return self.current_metrics.get("GEX", 0)

    def get_dex(self) -> float:
        """Get current DEX value"""
        with self._metrics_lock:
            return self.current_metrics.get("DEX", 0)

    def get_dix(self) -> float:
        """Get current DIX value"""
        with self._metrics_lock:
            return self.current_metrics.get("DIX", float("nan"))

    def get_swan(self) -> float:
        """Get current SWAN value"""
        with self._metrics_lock:
            return self.current_metrics.get("SWAN", float("nan"))

    def get_skew(self) -> float:
        """Get current SKEW value"""
        with self._metrics_lock:
            return self.current_metrics.get("SKEW", float("nan"))

    def get_stress_level(self) -> StressLevel:
        """Get current market stress level"""
        return self.current_stress_level

    def get_metrics_history(self, lookback_minutes: int = 60) -> list[MetricSnapshot]:
        """Get metrics history for specified lookback period"""
        cutoff_time = datetime.now(UTC) - timedelta(minutes=lookback_minutes)
        return [s for s in self.metrics_history if s.timestamp >= cutoff_time]

    def get_quality_report(self) -> dict[str, Any]:
        """Get comprehensive quality report for all metrics"""
        return {
            'overall_quality': np.mean([q.quality_score for q in self.metric_quality.values()]),
            'metric_qualities': {
                name: {
                    'score': quality.quality_score,
                    'data_points': quality.data_points,
                    'last_update': quality.last_successful_update.isoformat(),
                    'error_count': quality.error_count,
                    'source_available': quality.source_available
                }
                for name, quality in self.metric_quality.items()
            },
            'system_status': {
                'current_stress': self.current_stress_level.value,
                'update_frequency': self.current_update_interval,
                'connection_status': self.ib_connected,
                'history_points': len(self.metrics_history)
            }
        }

    # ==========================================================================
    # INTEGRATION METHODS (For other modules)
    # ==========================================================================

    def _load_index_confirmation_snapshot(self) -> dict[str, float]:
        """Load cross-index and sector change-percent context from persisted market snapshots."""
        market_data_dir = pathlib.Path(__file__).resolve().parents[2] / "market_data"
        snapshot_paths = [
            market_data_dir / "live_data.json",
            market_data_dir / "eod_snapshot.json",
        ]

        for snapshot_path in snapshot_paths:
            try:
                payload = json.loads(snapshot_path.read_text())
            except (FileNotFoundError, OSError, json.JSONDecodeError):
                continue

            if not isinstance(payload, dict):
                continue

            def _extract_change_pct(symbol: str, _payload: dict[str, Any] = payload) -> float:
                entry = _payload.get(symbol)
                if not isinstance(entry, dict):
                    return float("nan")
                try:
                    return float(entry.get("change_pct", float("nan")))
                except (TypeError, ValueError):
                    return float("nan")

            snapshot = {
                "spy_change_pct": _extract_change_pct("TRAD"),
                "qqq_change_pct": _extract_change_pct("QQQ"),
                "iwm_change_pct": _extract_change_pct("IWM"),
                "xlk_change_pct": _extract_change_pct("XLK"),
                "xlf_change_pct": _extract_change_pct("XLF"),
            }
            if any(math.isfinite(value) for value in snapshot.values()):
                return snapshot

        return {
            "spy_change_pct": float("nan"),
            "qqq_change_pct": float("nan"),
            "iwm_change_pct": float("nan"),
            "xlk_change_pct": float("nan"),
            "xlf_change_pct": float("nan"),
        }

    def get_current_market_conditions(self) -> dict[str, Any]:
        """
        Get current market conditions for integration with other modules.

        NOTE: This method provides data for L09_UnifiedRegimeEngine
        but does NOT perform regime detection itself.
        """
        with self._metrics_lock:
            index_snapshot = self._load_index_confirmation_snapshot()
            now = datetime.now(UTC)

            def _metric_value(name: str) -> float:
                value = self.current_metrics.get(name, float("nan"))
                try:
                    numeric = float(value)
                except (TypeError, ValueError):
                    return float("nan")
                return numeric if math.isfinite(numeric) else float("nan")

            def _metric_health(name: str) -> dict[str, Any]:
                quality = self.metric_quality.get(name)
                value = _metric_value(name)
                last_update = getattr(quality, "last_successful_update", None)
                age_seconds = None
                if isinstance(last_update, datetime):
                    age_seconds = max(0.0, (now - last_update).total_seconds())
                available = (
                    math.isfinite(value)
                    and bool(getattr(quality, "source_available", True))
                    and (
                        quality is None
                        or float(getattr(quality, "quality_score", 0.0) or 0.0) > 0.0
                    )
                )
                return {
                    "value": value,
                    "available": available,
                    "fresh": available and (age_seconds is None or age_seconds <= CACHE_EXPIRY_SECONDS),
                    "age_seconds": age_seconds,
                    "source_available": bool(getattr(quality, "source_available", available)),
                    "quality": float(getattr(quality, "quality_score", 1.0 if available else 0.0) or 0.0),
                }

            metric_health = {
                "DIX": _metric_health("DIX"),
                "SWAN": _metric_health("SWAN"),
                "SKEW": _metric_health("SKEW"),
            }
            market_conditions_available = all(
                item["available"] and item["fresh"] for item in metric_health.values()
            )
            return {
                'dix_score': metric_health["DIX"]["value"],
                'swan_score': metric_health["SWAN"]["value"],
                'skew_level': metric_health["SKEW"]["value"],
                'market_conditions_available': market_conditions_available,
                'metric_health': metric_health,
                # Lowercase aliases consumed directly by F09 trust-gate filters.
                'vix': self.current_metrics.get('VIX', float('nan')),
                'vix9d': self.current_metrics.get('VIX9D', float('nan')),
                'vxv': self.current_metrics.get('VXV', float('nan')),
                'vvix': self.current_metrics.get('VVIX', float('nan')),
                'cpc': self.current_metrics.get('CPC', float('nan')),
                'rvol': self.current_metrics.get('RVOL', float('nan')),
                'yield_10y': self.current_metrics.get('YIELD_10Y', float('nan')),
                'yield_slope': self.current_metrics.get('YIELD_SLOPE', float('nan')),
                'yield_inverted': self.current_metrics.get('YIELD_INVERTED', False),
                'aaii_bullish': self.current_metrics.get('AAII_BULLISH', float('nan')),
                'aaii_bearish': self.current_metrics.get('AAII_BEARISH', float('nan')),
                'naaim_exposure': self.current_metrics.get('NAAIM_EXPOSURE', float('nan')),
                'tick': self.current_metrics.get('TICK', float('nan')),
                'add': self.current_metrics.get('ADD', float('nan')),
                'trin': self.current_metrics.get('TRIN', float('nan')),
                'nymo': self.current_metrics.get('NYMO', float('nan')),
                'breadth_regime': self.current_metrics.get('BREADTH_REGIME', 'neutral'),
                'breadth_defensive': self.current_metrics.get('BREADTH_DEFENSIVE', float('nan')),
                'breadth_cyclical': self.current_metrics.get('BREADTH_CYCLICAL', float('nan')),
                'breadth_spread': self.current_metrics.get('BREADTH_SPREAD', float('nan')),
                'sector_adv_dec': self.current_metrics.get('SECTOR_ADV_DEC', float('nan')),
                'sector_momentum_dispersion': self.current_metrics.get('SECTOR_MOMENTUM_DISPERSION', float('nan')),  # noqa: E501
                'participation_score': self.current_metrics.get('PARTICIPATION_SCORE', float('nan')),  # noqa: E501
                'sector_breadth': self.current_metrics.get('SECTOR_BREADTH', {}),
                'spy_change_pct': index_snapshot.get('spy_change_pct', self.current_metrics.get('TRAD_CHANGE_PCT', float('nan'))),
                'qqq_change_pct': index_snapshot.get('qqq_change_pct', self.current_metrics.get('QQQ_CHANGE_PCT', float('nan'))),
                'iwm_change_pct': index_snapshot.get('iwm_change_pct', self.current_metrics.get('IWM_CHANGE_PCT', float('nan'))),
                'xlk_change_pct': index_snapshot.get('xlk_change_pct', self.current_metrics.get('XLK_CHANGE_PCT', float('nan'))),
                'xlf_change_pct': index_snapshot.get('xlf_change_pct', self.current_metrics.get('XLF_CHANGE_PCT', float('nan'))),
                'stress_level': self.current_stress_level.value,
                'update_frequency': self.current_update_interval,
                'timestamp': datetime.now(UTC),
                'data_quality_feed': self.current_metrics.get('DATA_QUALITY_FEED', {}),
                'data_quality': {
                    name: quality.quality_score
                    for name, quality in self.metric_quality.items()
                }
            }


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
_orchestrator_instance = None


def get_metrics_orchestrator() -> CustomMetricsOrchestrator:
    """Get singleton instance of metrics orchestrator"""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = CustomMetricsOrchestrator()
    return _orchestrator_instance


def create_metrics_orchestrator(config: dict | None = None) -> CustomMetricsOrchestrator:
    """Create new instance of metrics orchestrator with config"""
    return CustomMetricsOrchestrator(config)


# Backward compatibility
get_custom_metrics_orchestrator = get_metrics_orchestrator


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing and demonstration

    # Test configuration
    test_config = {
        'auto_start': True,
        'max_history_size': 500
    }

    # Create Qt application for signal testing
    import sys
    app = QApplication(sys.argv) if not QApplication.instance() else QApplication.instance()

    # Create orchestrator
    orchestrator = create_metrics_orchestrator(test_config)



    # Wait for initial update
    QTimer.singleShot(2000, lambda: None)
    app.processEvents()

    # Show current metrics
    metrics = orchestrator.get_all_metrics()
    for name, _value in metrics.items():
        unit = {'GEX': 'B', 'DEX': 'M', 'DIX': '%', 'SWAN': '', 'SKEW': '', 'OGL': ''}[name]

    # Show market conditions for integration
    conditions = orchestrator.get_current_market_conditions()

    # Show quality report
    quality_report = orchestrator.get_quality_report()
