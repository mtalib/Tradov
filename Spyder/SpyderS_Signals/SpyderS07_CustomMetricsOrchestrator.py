#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderS_Signals
Module: SpyderS07_CustomMetricsOrchestrator.py
Purpose: Central orchestrator for all custom market metrics (Updated - Regime Detection Removed)
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-04 Time: 14:30:00

Module Description:
    Central orchestrator that coordinates all custom metric calculations.
    Provides a unified interface for GEX, DEX, OGL,
    DIX, SWAN, and SKEW calculations. Emits Qt signals for GUI integration
    and manages update scheduling for all metrics.

CONSOLIDATION UPDATE:
    Regime detection functions have been REMOVED and consolidated into
    SpyderL09_UnifiedRegimeEngine.py. This module now focuses exclusively
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
import logging
import math
import threading
import time
import importlib
import pathlib
from datetime import datetime, timedelta, timezone
from typing import Any
from dataclasses import dataclass, field
from enum import Enum

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# S-SERIES SIGNAL IMPORTS
# ==============================================================================
try:
    from SpyderS_Signals.SpyderS01_DIXCalculator import (
        DIXCalculator, get_calculator_instance)  # noqa: F401
    DIX_AVAILABLE = True
except ImportError:
    DIX_AVAILABLE = False
    logging.info("⚠️ S01_DIXCalculator not available")

try:
    from SpyderS_Signals.SpyderS03_BlackSwanIndicator import (
        BlackSwanIndicator, get_black_swan_indicator)  # noqa: F401
    SWAN_AVAILABLE = True
except ImportError:
    SWAN_AVAILABLE = False
    logging.info("⚠️ S03_BlackSwanIndicator not available")

try:
    from SpyderS_Signals.SpyderS05_GEXDEXCalculator import GEXDEXCalculator
    from SpyderS_Signals.SpyderS05_GEXDEXCalculator import DataUnavailableError as GEXDataUnavailableError  # noqa: E501
    GEX_AVAILABLE = True
except ImportError:
    GEX_AVAILABLE = False
    GEXDataUnavailableError = Exception
    logging.info("⚠️ S05_GEXDEXCalculator not available")

try:
    from SpyderS_Signals.SpyderS06_SKEWCalculator import (
        SpyderS06_SKEWCalculator, get_skew_calculator)  # noqa: F401
    from SpyderS_Signals.SpyderS06_SKEWCalculator import DataUnavailableError as SKEWDataUnavailableError  # noqa: E501
    SKEW_AVAILABLE = True
except ImportError:
    SKEW_AVAILABLE = False
    SKEWDataUnavailableError = Exception
    logging.info("⚠️ S06_SKEWCalculator not available")

try:
    from SpyderS_Signals.SpyderS09_FREDClient import get_fred_client
    FRED_AVAILABLE = True
except ImportError:
    FRED_AVAILABLE = False
    logging.info("⚠️ S09_FREDClient not available")

try:
    from SpyderS_Signals.SpyderS10_SentimentScraper import get_sentiment_scraper
    SENTIMENT_AVAILABLE = True
except ImportError:
    SENTIMENT_AVAILABLE = False
    logging.info("⚠️ S10_SentimentScraper not available")

try:
    from SpyderS_Signals.SpyderS02_DIXScheduler import SpyderDIXScheduler
    DIX_SCHEDULER_AVAILABLE = True
except ImportError:
    DIX_SCHEDULER_AVAILABLE = False
    logging.info("⚠️ S02_DIXScheduler not available")

try:
    from SpyderS_Signals.SpyderS04_BlackSwanScheduler import BlackSwanScheduler as BlackSwanSchedulerCls  # noqa: E501
    SWAN_SCHEDULER_AVAILABLE = True
except ImportError:
    SWAN_SCHEDULER_AVAILABLE = False
    logging.info("⚠️ S04_BlackSwanScheduler not available")

try:
    from SpyderS_Signals.SpyderS11_TradingViewInternals import get_tv_internals_client
    TV_INTERNALS_AVAILABLE = True
except ImportError:
    TV_INTERNALS_AVAILABLE = False
    logging.info("⚠️ S11_TradingViewInternals not available")

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
    gex: float = 0.0
    dex: float = 0.0
    ogl: float = 0.0
    dix: float = 0.0
    swan: float = 1.0
    skew: float = 100.0
    vex: float = 0.0
    chex: float = 0.0
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
    ivr: float = float("nan")
    atm_iv: float = float("nan")
    vrp: float = float("nan")
    atm_iv_0dte: float = float("nan")
    atm_iv_1dte: float = float("nan")
    atm_iv_7dte: float = float("nan")
    atm_iv_30dte: float = float("nan")
    term_slope_0_7: float = float("nan")
    term_slope_7_30: float = float("nan")
    rr_25d: float = float("nan")
    fly_25d: float = float("nan")
    surface_confidence: float = float("nan")
    surface_age_ms: float = float("nan")
    zero_gamma: float = float("nan")
    wall_confidence: float = float("nan")
    vanna_pressure: float = float("nan")
    charm_pressure: float = float("nan")
    flow_imbalance: float = float("nan")
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
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
    SpyderL09_UnifiedRegimeEngine for consolidation.
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

    def __init__(self, config: dict | None = None):
        """Initialize custom metrics orchestrator"""
        super().__init__()

        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config = config or {}
        self.client_id = CLIENT_ID

        # Initialize calculators with availability checks
        self._init_calculators()

        # Current metrics storage with thread-safe access
        self._metrics_lock = threading.RLock()
        self.current_metrics = {
            "GEX": 0.0,
            "DEX": 0.0,
            "OGL": 0.0,
            "DIX": 0.0,
            "SWAN": 1.0,
            "SKEW": 100.0,
            "VEX": 0.0,
            "CHEX": 0.0,
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
            "IVR": float("nan"),
            "ATM_IV": float("nan"),
            "VRP": float("nan"),
            "ATM_IV_0DTE": float("nan"),
            "ATM_IV_1DTE": float("nan"),
            "ATM_IV_7DTE": float("nan"),
            "ATM_IV_30DTE": float("nan"),
            "TERM_SLOPE_0_7": float("nan"),
            "TERM_SLOPE_7_30": float("nan"),
            "RR_25D": float("nan"),
            "FLY_25D": float("nan"),
            "SURFACE_CONFIDENCE": float("nan"),
            "SURFACE_AGE_MS": float("nan"),
            "ZERO_GAMMA": float("nan"),
            "WALL_CONFIDENCE": float("nan"),
            "VANNA_PRESSURE": float("nan"),
            "CHARM_PRESSURE": float("nan"),
            "FLOW_IMBALANCE": float("nan"),
            "DEALER_FLOW": {},
            "SPY_CHANGE_PCT": float("nan"),
            "QQQ_CHANGE_PCT": float("nan"),
            "IWM_CHANGE_PCT": float("nan"),
            "XLK_CHANGE_PCT": float("nan"),
            "XLF_CHANGE_PCT": float("nan"),
            "LIQUIDITY_DIAGNOSTICS": {},
            "DATA_QUALITY_FEED": {},
        }

        self._options_tradier_client = None
        self._options_tradier_env = None
        self._vol_surface_builder = None
        self._n09_gex_analyzer = None
        self._n11_flow_analyzer = None
        # Running EMA state for NYMO proxy (McClellan Oscillator approximation).
        # NYMO ≈ EMA(19) − EMA(39) of the NYSE A-D (ADD) series.
        self._nymo_ema_fast: float = float("nan")  # 19-bar EMA of ADD
        self._nymo_ema_slow: float = float("nan")  # 39-bar EMA of ADD
        _a19 = 2.0 / (19 + 1)
        _a39 = 2.0 / (39 + 1)
        self._nymo_alpha_fast: float = _a19
        self._nymo_alpha_slow: float = _a39

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
        self.last_frequency_change = datetime.now(timezone.utc)
        self._last_metrics_info_log_ts: datetime | None = None
        self._metrics_info_heartbeat_seconds = int(
            self.config.get("metrics_info_heartbeat_seconds", 180)
        )
        self._last_liquidity_diag_log_ts: datetime | None = None
        self._last_liquidity_diag_message: str | None = None
        self._liquidity_diag_heartbeat_seconds = int(
            self.config.get("liquidity_diag_heartbeat_seconds", 300)
        )

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
        self.update_timer.setInterval(self.current_update_interval * 1000)

        self.logger.debug("CustomMetricsOrchestrator initialized (Client ID: %s)", CLIENT_ID)
        self.logger.debug("⚠️ Regime detection functions removed - now handled by L09_UnifiedRegimeEngine")  # noqa: E501

        # Auto-start if configured
        if self.config.get("auto_start", True):
            self.start()

    def _init_calculators(self):
        """Initialize all available calculators"""
        # S01 - DIX Calculator
        if DIX_AVAILABLE:
            try:
                self.dix_calculator = get_calculator_instance()
                self.logger.debug("✅ S01_DIXCalculator initialized")
            except Exception as e:
                self.logger.error("Failed to init DIX: %s", e, exc_info=True)
                self.dix_calculator = None
        else:
            self.dix_calculator = None

        # S03 - Black Swan Indicator
        if SWAN_AVAILABLE:
            try:
                self.swan_indicator = get_black_swan_indicator()
                self.logger.debug("✅ S03_BlackSwanIndicator initialized")
            except Exception as e:
                self.logger.error("Failed to init SWAN: %s", e, exc_info=True)
                self.swan_indicator = None
        else:
            self.swan_indicator = None

        # S05 - GEX/DEX Calculator
        if GEX_AVAILABLE:
            try:
                self.gex_calculator = GEXDEXCalculator()
                self.logger.debug("✅ S05_GEXDEXCalculator initialized")
            except Exception as e:
                self.logger.error("Failed to init GEX: %s", e, exc_info=True)
                self.gex_calculator = None
        else:
            self.gex_calculator = None

        # S06 - SKEW Calculator
        if SKEW_AVAILABLE:
            try:
                self.skew_calculator = get_skew_calculator()
                self.logger.debug("✅ S06_SKEWCalculator initialized")
            except Exception as e:
                self.logger.error("Failed to init SKEW: %s", e, exc_info=True)
                self.skew_calculator = None
        else:
            self.skew_calculator = None

        # S09 - FRED Client (Treasury yields, DXY proxy, yield curve)
        if FRED_AVAILABLE:
            try:
                self.fred_client = get_fred_client()
                self.logger.debug("✅ S09_FREDClient initialized")
            except Exception as e:
                self.logger.error("Failed to init FRED: %s", e, exc_info=True)
                self.fred_client = None
        else:
            self.fred_client = None

        # S10 - Sentiment Scraper (AAII + NAAIM weekly surveys)
        if SENTIMENT_AVAILABLE:
            try:
                self.sentiment_scraper = get_sentiment_scraper()
                self.logger.debug("✅ S10_SentimentScraper initialized")
            except Exception as e:
                self.logger.error("Failed to init Sentiment: %s", e, exc_info=True)
                self.sentiment_scraper = None
        else:
            self.sentiment_scraper = None

        # S02 - DIX Scheduler (pre-market 9:00 AM + EOD 6:30 PM ET cron collection)
        if DIX_SCHEDULER_AVAILABLE:
            try:
                self.dix_scheduler = SpyderDIXScheduler()
                self.logger.debug("✅ S02_DIXScheduler initialized")
            except Exception as e:
                self.logger.error("Failed to init DIX scheduler: %s", e, exc_info=True)
                self.dix_scheduler = None
        else:
            self.dix_scheduler = None

        # S04 - Black Swan Scheduler (4:00 AM / 9:15 AM / 12:00 PM / 3:45 PM / 4:30 PM ET)
        if SWAN_SCHEDULER_AVAILABLE:
            try:
                self.swan_scheduler = BlackSwanSchedulerCls()
                self.logger.debug("✅ S04_BlackSwanScheduler initialized")
            except Exception as e:
                self.logger.error("Failed to init Black Swan scheduler: %s", e, exc_info=True)
                self.swan_scheduler = None
        else:
            self.swan_scheduler = None

        # S11 - TradingView Breadth Internals (TICK, TRIN, ADD)
        if TV_INTERNALS_AVAILABLE:
            try:
                self.tv_client = get_tv_internals_client()
                self.logger.debug("✅ S11_TradingViewInternals initialized")
            except Exception as e:
                self.logger.error("Failed to init TradingView internals: %s", e, exc_info=True)
                self.tv_client = None
        else:
            self.tv_client = None

    def _init_quality_tracking(self):
        """Initialize quality tracking for all metrics"""
        metrics = ['GEX', 'DEX', 'OGL', 'DIX', 'SWAN', 'SKEW', 'VEX', 'CHEX', 'FRED', 'SENTIMENT', 'BREADTH', 'SECTOR_BREADTH', 'OPTIONS', 'LIQUIDITY', 'VOL_SURFACE', 'DEALER_FLOW']  # noqa: E501

        for metric in metrics:
            self.metric_quality[metric] = MetricQuality(
                metric_name=metric,
                quality_score=1.0,  # Start with perfect score
                data_points=0,
                last_successful_update=datetime.now(timezone.utc),
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
            self.update_timer.start()
            self.ib_connected = True

            # swan_scheduler.start() only spawns a thread — safe on main thread.
            # dix_scheduler.initialize() makes a live HTTP request, so it belongs
            # in the background thread below.
            if self.swan_scheduler is not None:
                self.swan_scheduler.start(daemon=True)
                self.logger.debug("✅ S04_BlackSwanScheduler started (4:00 AM / 9:15 AM / 12:00 PM / 3:45 PM ET)")  # noqa: E501

            self.logger.debug("✅ Orchestrator started — background fetch beginning")
            self.connection_status_changed.emit(True, f"Client {CLIENT_ID} Active")

            # All blocking network I/O (DIX init + metric fetch + Black Swan
            # catch-up) runs in a background daemon thread so the Qt event loop
            # is never stalled during startup.
            threading.Thread(
                target=self._startup_fetch,
                name="S07-startup-fetch",
                daemon=True,
            ).start()

        except Exception as e:
            self.logger.error("Failed to start orchestrator: %s", e, exc_info=True)
            self.error_occurred.emit(f"Startup failed: {str(e)}")

    def _startup_fetch(self):
        """Background startup: DIX init, initial metric fetch, late-start Black Swan check.

        Runs entirely off the Qt main thread — no GUI calls allowed here.
        """
        # S02 DIX Scheduler — initialize() hits FINRA over HTTP; must be off-thread
        if self.dix_scheduler is not None:
            try:
                if self.dix_scheduler.initialize():
                    self.dix_scheduler.start()
                    self.logger.debug("✅ S02_DIXScheduler started (9:00 AM + 6:30 PM ET)")
                else:
                    self.logger.warning("⚠️ DIX scheduler init failed; skipping scheduled collection")  # noqa: E501
            except Exception as e:
                self.logger.error("DIX scheduler startup failed: %s", e)

        # Initial metric fetch across all S-Series sources
        try:
            self.update_all_metrics()
        except Exception as e:
            self.logger.error("Startup metric fetch failed: %s", e)

        # Late-start Black Swan catch-up check
        try:
            if self.swan_scheduler is not None:
                # Run the 9:15 AM check so late starts don't silently miss the
                # pre-open window.
                self.swan_scheduler.run_now("daily_check_0915")
        except Exception as e:
            self.logger.error("Startup Black Swan check failed: %s", e)

    def stop(self):
        """Stop the orchestrator"""
        try:
            # Stop data collection schedulers first
            if self.dix_scheduler is not None:
                self.dix_scheduler.stop()
            if self.swan_scheduler is not None:
                self.swan_scheduler.stop()

            self.update_timer.stop()
            self.ib_connected = False

            self.logger.info("⏹️ Orchestrator stopped")
            self.connection_status_changed.emit(False, f"Client {CLIENT_ID} Stopped")

        except Exception as e:
            self.logger.error("Error stopping orchestrator: %s", e, exc_info=True)

    def _dispatch_metrics_update(self) -> None:
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
                self.update_all_metrics()
            finally:
                self._update_running = False

        threading.Thread(
            target=_run,
            name="S07-metrics-update",
            daemon=True,
        ).start()

    def update_all_metrics(self):
        """Update all metrics from S-Series calculators"""
        start_time = time.time()

        try:
            with self._metrics_lock:
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

                # S09 - FRED Macro Updates (Treasury yields, yield curve, DXY)
                fred_success = self._update_fred_metrics(updated_metrics, update_errors)

                # S10 - Sentiment Updates (AAII weekly surveys, NAAIM exposure)
                sentiment_success = self._update_sentiment_metrics(updated_metrics, update_errors)

                # S11 - TradingView Breadth Internals (TICK, TRIN, ADD)
                breadth_success = self._update_tv_breadth_metrics(updated_metrics, update_errors)

                # Options analytics metrics (ATM IV, IV rank, volatility risk premium)
                options_success = self._update_options_analytics_metrics(updated_metrics, update_errors)  # noqa: E501

                # Volatility surface term-structure metrics
                vol_surface_success = self._update_vol_surface_metrics(updated_metrics, update_errors)  # noqa: E501

                # Dealer-flow structure: N09 gamma walls + N11 vanna/charm pressure
                dealer_flow_success = self._update_dealer_flow_metrics(updated_metrics, update_errors)  # noqa: E501

                # Observe-only liquidity diagnostics for candidate contracts
                liquidity_success = self._update_liquidity_diagnostics_metrics(updated_metrics, update_errors)  # noqa: E501

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
                    gex=updated_metrics.get('GEX', 0.0),
                    dex=updated_metrics.get('DEX', 0.0),
                    ogl=updated_metrics.get('OGL', 0.0),
                    dix=updated_metrics.get('DIX', 0.0),
                    swan=updated_metrics.get('SWAN', 1.0),
                    skew=updated_metrics.get('SKEW', 100.0),
                    vex=updated_metrics.get('VEX', 0.0),
                    chex=updated_metrics.get('CHEX', 0.0),
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
                    ivr=updated_metrics.get('IVR', float('nan')),
                    atm_iv=updated_metrics.get('ATM_IV', float('nan')),
                    vrp=updated_metrics.get('VRP', float('nan')),
                    atm_iv_0dte=updated_metrics.get('ATM_IV_0DTE', float('nan')),
                    atm_iv_1dte=updated_metrics.get('ATM_IV_1DTE', float('nan')),
                    atm_iv_7dte=updated_metrics.get('ATM_IV_7DTE', float('nan')),
                    atm_iv_30dte=updated_metrics.get('ATM_IV_30DTE', float('nan')),
                    term_slope_0_7=updated_metrics.get('TERM_SLOPE_0_7', float('nan')),
                    term_slope_7_30=updated_metrics.get('TERM_SLOPE_7_30', float('nan')),
                    rr_25d=updated_metrics.get('RR_25D', float('nan')),
                    fly_25d=updated_metrics.get('FLY_25D', float('nan')),
                    surface_confidence=updated_metrics.get('SURFACE_CONFIDENCE', float('nan')),
                    surface_age_ms=updated_metrics.get('SURFACE_AGE_MS', float('nan')),
                    zero_gamma=updated_metrics.get('ZERO_GAMMA', float('nan')),
                    wall_confidence=updated_metrics.get('WALL_CONFIDENCE', float('nan')),
                    vanna_pressure=updated_metrics.get('VANNA_PRESSURE', float('nan')),
                    charm_pressure=updated_metrics.get('CHARM_PRESSURE', float('nan')),
                    flow_imbalance=updated_metrics.get('FLOW_IMBALANCE', float('nan')),
                    update_frequency=self.current_update_interval
                )

                self._add_to_history(snapshot)

                # Analyze stress level and adjust frequency
                self._analyze_and_adjust_frequency(updated_metrics)

                # Format and emit signals
                formatted_metrics = self._format_metrics(updated_metrics)
                self.metrics_updated.emit(formatted_metrics)

                # Log successful update
                calculation_time = time.time() - start_time
                success_count = sum([
                    gex_success, dix_success, swan_success, skew_success,
                    fred_success, sentiment_success, breadth_success, options_success,
                    vol_surface_success,
                    dealer_flow_success,
                    liquidity_success,
                ])

                # Only log at INFO when key values change or on periodic heartbeat;
                # use DEBUG for unchanged cycles to reduce startup/runtime chatter.
                _summary = (
                    f"{success_count}/12 | "
                    f"GEX={updated_metrics.get('GEX', 0):.1f}B "
                    f"DIX={updated_metrics.get('DIX', 0):.1f}% "
                    f"SWAN={updated_metrics.get('SWAN', 1):.2f} "
                    f"SKEW={updated_metrics.get('SKEW', 100):.1f} "
                    f"TICK={updated_metrics.get('TICK', float('nan'))}"
                )
                _last = getattr(self, "_last_metrics_summary", None)
                _now = datetime.now(timezone.utc)
                _heartbeat_due = (
                    self._last_metrics_info_log_ts is None
                    or (_now - self._last_metrics_info_log_ts).total_seconds()
                    >= self._metrics_info_heartbeat_seconds
                )
                _use_info = (_summary != _last) or _heartbeat_due
                _log = self.logger.info if _use_info else self.logger.debug
                _log(
                    f"📊 Metrics updated: {success_count}/12 sources successful "
                    f"(GEX={updated_metrics.get('GEX', 0):.1f}B, "
                    f"DIX={updated_metrics.get('DIX', 0):.1f}%, "
                    f"SWAN={updated_metrics.get('SWAN', 1):.2f}, "
                    f"SKEW={updated_metrics.get('SKEW', 100):.1f}, "
                    f"TICK={updated_metrics.get('TICK', float('nan'))}, "
                    f"10Y={updated_metrics.get('YIELD_10Y', float('nan')):.2f}%) "
                    f"[{calculation_time:.2f}s]"
                )
                if _use_info:
                    self._last_metrics_info_log_ts = _now
                self._last_metrics_summary = _summary

        except Exception as e:
            self.logger.error("Critical error updating metrics: %s", e, exc_info=True)
            self.error_occurred.emit(str(e))

    def _update_gex_metrics(self, updated_metrics: dict, errors: list) -> bool:
        """Update GEX, DEX, OGL metrics"""
        try:
            if self.gex_calculator:
                gex_data = self.gex_calculator.calculate_all()
                updated_metrics["GEX"] = gex_data.get("gex", 0) / 1e9  # Convert to billions
                updated_metrics["DEX"] = gex_data.get("dex", 0) / 1e6  # Convert to millions
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
            self.logger.warning("GEX data unavailable (options chain not ready): %s", e)
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
            self.logger.error("GEX update error: %s", e, exc_info=True)
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
            if self.dix_calculator:
                dix_result = self.dix_calculator.calculate_dix()
                if dix_result:
                    updated_metrics["DIX"] = dix_result.dix_percentage
                    self.dix_updated.emit(dix_result.dix_percentage)
                    return True
                else:
                    updated_metrics["DIX"] = self.current_metrics.get("DIX", 42.5)
                    return False
            else:
                # Simulation fallback
                updated_metrics["DIX"] = 42.5 + np.random.normal(0, 2.0)
                return False
        except Exception as e:
            errors.append(f"DIX update error: {e}")
            self.logger.error("DIX update error: %s", e, exc_info=True)
            updated_metrics["DIX"] = self.current_metrics.get("DIX", 42.5)
            return False

    def _update_swan_metrics(self, updated_metrics: dict, errors: list) -> bool:
        """Update SWAN metrics"""
        try:
            if self.swan_indicator:
                swan_result = self.swan_indicator.calculate_swan_score()
                updated_metrics["SWAN"] = swan_result.overall_score

                # Emit detailed SWAN signal
                self.swan_updated.emit({
                    "score": swan_result.overall_score,
                    "status": swan_result.status.value,
                    "components": swan_result.component_scores,
                })
                return True
            else:
                # Simulation fallback
                current_swan = self.current_metrics.get("SWAN", 1.85)
                updated_metrics["SWAN"] = max(1.0, min(5.0, current_swan + np.random.normal(0, 0.1)))  # noqa: E501
                return False
        except Exception as e:
            errors.append(f"SWAN update error: {e}")
            self.logger.error("SWAN update error: %s", e, exc_info=True)
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
            self.logger.warning("SKEW data unavailable (options chain not ready): %s", e)
            updated_metrics["SKEW"] = self.current_metrics.get("SKEW", 125.5)
            return False
        except Exception as e:
            errors.append(f"SKEW update error: {e}")
            self.logger.error("SKEW update error: %s", e, exc_info=True)
            updated_metrics["SKEW"] = self.current_metrics.get("SKEW", 125.5)
            return False

    def _update_fred_metrics(self, updated_metrics: dict, errors: list) -> bool:
        """Update FRED macro metrics (10Y yield, yield curve slope, yield curve inversion flag)"""
        try:
            if self.fred_client:
                snap = self.fred_client.get_snapshot()
                updated_metrics["YIELD_10Y"]     = snap.get("yield_10y", float("nan"))
                updated_metrics["YIELD_SLOPE"]   = snap.get("spread_10y_2y", float("nan"))
                updated_metrics["YIELD_INVERTED"] = snap.get("yield_curve_inverted", False)
                self.fred_updated.emit(snap)
                return True
            else:
                for key in ("YIELD_10Y", "YIELD_SLOPE", "YIELD_INVERTED"):
                    updated_metrics[key] = self.current_metrics.get(key, float("nan"))
                return False
        except Exception as e:
            errors.append(f"FRED update error: {e}")
            self.logger.error("FRED update error: %s", e, exc_info=True)
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
                return True
            else:
                for key in ("AAII_BULLISH", "AAII_BEARISH", "NAAIM_EXPOSURE"):
                    updated_metrics[key] = self.current_metrics.get(key, float("nan"))
                return False
        except Exception as e:
            errors.append(f"Sentiment update error: {e}")
            self.logger.error("Sentiment update error: %s", e, exc_info=True)
            for key in ("AAII_BULLISH", "AAII_BEARISH", "NAAIM_EXPOSURE"):
                updated_metrics[key] = self.current_metrics.get(key, float("nan"))
            return False

    def _update_tv_breadth_metrics(self, updated_metrics: dict, errors: list) -> bool:
        """Update TICK, TRIN, ADD breadth internals from TradingView."""
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
                    "snapshot_ts": snap.get("snapshot_ts") or datetime.now(timezone.utc).isoformat(),
                    "source": "SpyderS11_TradingViewInternals",
                }

                if "SECTOR_BREADTH" in self.metric_quality:
                    q = self.metric_quality["SECTOR_BREADTH"]
                    q.last_successful_update = datetime.now(timezone.utc)
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
            self.logger.error("Breadth update error: %s", e, exc_info=True)
            for key in ("TICK", "ADD", "TRIN", "NYMO", "VOLD"):
                updated_metrics[key] = self.current_metrics.get(key, float("nan"))
            updated_metrics["BREADTH_REGIME"] = self.current_metrics.get("BREADTH_REGIME", "neutral")  # noqa: E501
            updated_metrics["SECTOR_BREADTH"] = self.current_metrics.get("SECTOR_BREADTH", {})
            return False

    def _build_data_quality_feed(self, updated_metrics: dict[str, Any], errors: list[str]) -> dict[str, Any]:  # noqa: E501
        """Build a normalized data-quality/SLO envelope for downstream consumers."""
        now = datetime.now(timezone.utc)
        stale_threshold_sec = int(self.config.get("data_quality", {}).get("stale_after_sec", 180))
        buckets: dict[str, dict[str, Any]] = {}
        stale_count = 0

        for name, quality in self.metric_quality.items():
            last_successful_update = quality.last_successful_update
            if last_successful_update.tzinfo is None:
                age_sec = (datetime.now() - last_successful_update).total_seconds()  # spyder: naive-ok
            else:
                age_sec = (now - last_successful_update.astimezone(timezone.utc)).total_seconds()
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

    def _get_spy_spot(self) -> float | None:
        """Return the best available SPY spot estimate."""
        spot = self.current_metrics.get("OGL")
        if isinstance(spot, (int, float)) and spot > 0:
            return float(spot)
        return None

    def _get_liquidity_thresholds(self) -> dict[str, float]:
        """Return the configured liquidity gate thresholds."""
        liquidity_cfg = self.config.get("autonomous_readiness", {}).get("liquidity", {})
        return {
            "max_spread_pct": float(liquidity_cfg.get("max_spread_pct", 0.12)),
            "max_spread_abs": float(liquidity_cfg.get("max_spread_abs", 0.20)),
            "max_quote_age_ms": int(liquidity_cfg.get("max_quote_age_ms", 1500)),
            "min_top_of_book_size": int(liquidity_cfg.get("min_top_of_book_size", 10)),
            "min_open_interest": int(liquidity_cfg.get("min_open_interest", 500)),
            "min_volume": int(liquidity_cfg.get("min_volume", 50)),
            "min_oi_change_pct": float(liquidity_cfg.get("min_oi_change_pct", -0.20)),
        }

    def _evaluate_liquidity_snapshot(self, snapshot: dict[str, Any], thresholds: dict[str, float]) -> list[str]:  # noqa: E501
        """Evaluate a liquidity snapshot using the same contract as F09/B02."""
        reasons: list[str] = []

        spread_pct = snapshot.get("spread_pct")
        if isinstance(spread_pct, (int, float)) and float(spread_pct) > thresholds["max_spread_pct"]:  # noqa: E501
            reasons.append(
                f"spread_pct {float(spread_pct):.4f} > max_spread_pct {thresholds['max_spread_pct']:.4f}"  # noqa: E501
            )

        spread_abs = snapshot.get("spread_abs")
        if isinstance(spread_abs, (int, float)) and float(spread_abs) > thresholds["max_spread_abs"]:  # noqa: E501
            reasons.append(
                f"spread_abs {float(spread_abs):.4f} > max_spread_abs {thresholds['max_spread_abs']:.4f}"  # noqa: E501
            )

        quote_age_ms = snapshot.get("quote_age_ms")
        if isinstance(quote_age_ms, (int, float)) and float(quote_age_ms) > thresholds["max_quote_age_ms"]:  # noqa: E501
            reasons.append(
                f"quote_age_ms {float(quote_age_ms):.0f} > max_quote_age_ms {thresholds['max_quote_age_ms']:.0f}"  # noqa: E501
            )

        top_of_book_size = snapshot.get("top_of_book_size")
        if isinstance(top_of_book_size, (int, float)) and float(top_of_book_size) < thresholds["min_top_of_book_size"]:  # noqa: E501
            reasons.append(
                f"top_of_book_size {float(top_of_book_size):.0f} < min_top_of_book_size {thresholds['min_top_of_book_size']:.0f}"  # noqa: E501
            )

        open_interest = snapshot.get("open_interest")
        if isinstance(open_interest, (int, float)) and float(open_interest) < thresholds["min_open_interest"]:  # noqa: E501
            reasons.append(
                f"open_interest {float(open_interest):.0f} < min_open_interest {thresholds['min_open_interest']:.0f}"  # noqa: E501
            )

        volume = snapshot.get("volume")
        if isinstance(volume, (int, float)) and float(volume) < thresholds["min_volume"]:
            reasons.append(f"volume {float(volume):.0f} < min_volume {thresholds['min_volume']:.0f}")  # noqa: E501

        oi_change_pct = snapshot.get("oi_change_pct")
        if isinstance(oi_change_pct, (int, float)) and float(oi_change_pct) < thresholds["min_oi_change_pct"]:  # noqa: E501
            reasons.append(
                f"oi_change_pct {float(oi_change_pct):.4f} < min_oi_change_pct {thresholds['min_oi_change_pct']:.4f}"  # noqa: E501
            )

        return reasons

    def _load_options_chain_dataframe(self):
        """Load the live SPY options chain as a DataFrame from the nearest owner."""
        try:
            chain_module = importlib.import_module("Spyder.SpyderN_OptionsAnalytics.SpyderN03_OptionsChainManager")  # noqa: E501
        except ImportError:
            chain_module = importlib.import_module("SpyderN_OptionsAnalytics.SpyderN03_OptionsChainManager")  # noqa: E501

        chain_manager = chain_module.OptionsChainManager()
        return chain_manager.get_chain("SPY")

    def _build_liquidity_candidate(self, row: Any, now: datetime, thresholds: dict[str, float]) -> dict[str, Any]:  # noqa: E501
        """Convert one option-chain row into an observe-mode liquidity payload."""
        bid = float(row.get("bid") or 0.0)
        ask = float(row.get("ask") or 0.0)
        mid_price = float(row.get("mid_price") or 0.0)
        if mid_price <= 0 and bid > 0 and ask > 0:
            mid_price = (bid + ask) / 2.0
        spread_abs = float(row.get("spread") or max(0.0, ask - bid))
        spread_pct = (spread_abs / mid_price) if mid_price > 0 else None

        quote_ts = row.get("timestamp")
        if hasattr(quote_ts, "to_pydatetime"):
            quote_ts = quote_ts.to_pydatetime()
        if not isinstance(quote_ts, datetime):
            quote_ts = now

        if quote_ts.tzinfo is None:
            now_for_age = now.replace(tzinfo=None) if now.tzinfo is not None else now
            quote_age_ms = max(0, int((now_for_age - quote_ts).total_seconds() * 1000))
        else:
            now_for_age = now.astimezone(timezone.utc) if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)  # noqa: E501
            quote_age_ms = max(0, int((now_for_age - quote_ts.astimezone(timezone.utc)).total_seconds() * 1000))  # noqa: E501

        bid_size = row.get("bid_size")
        ask_size = row.get("ask_size")
        if bid_size is not None and ask_size is not None:
            try:
                top_of_book_size = min(int(bid_size), int(ask_size))
            except (TypeError, ValueError):
                top_of_book_size = None
        else:
            top_of_book_size = None

        snapshot = {
            "spread_abs": spread_abs,
            "spread_pct": spread_pct,
            "quote_age_ms": quote_age_ms,
            "bid_size": int(bid_size) if isinstance(bid_size, (int, float)) else None,
            "ask_size": int(ask_size) if isinstance(ask_size, (int, float)) else None,
            "top_of_book_size": top_of_book_size,
            "open_interest": int(row.get("open_interest") or 0),
            "volume": int(row.get("volume") or 0),
            "oi_change_pct": row.get("oi_change_pct"),
            "snapshot_ts": quote_ts.isoformat(),
        }
        reasons = self._evaluate_liquidity_snapshot(snapshot, thresholds)

        return {
            "symbol": row.get("symbol", "SPY"),
            "strike": float(row.get("strike") or 0.0),
            "expiry": row.get("expiry").isoformat() if isinstance(row.get("expiry"), datetime) else str(row.get("expiry")),  # noqa: E501
            "option_type": str(row.get("option_type", "")).lower(),
            "snapshot": snapshot,
            "gate_passed": len(reasons) == 0,
            "reasons": reasons,
        }

    def _update_liquidity_diagnostics_metrics(self, updated_metrics: dict, errors: list) -> bool:
        """Publish observe-mode liquidity diagnostics for nearby SPY option candidates."""
        updated_metrics.setdefault("LIQUIDITY_DIAGNOSTICS", self.current_metrics.get("LIQUIDITY_DIAGNOSTICS", {}))  # noqa: E501

        try:
            chain_df = self._load_options_chain_dataframe()
            if chain_df is None or chain_df.empty:
                raise ValueError("SPY options chain unavailable")

            anchor = self.current_metrics.get("OGL")
            if not isinstance(anchor, (int, float)) or anchor <= 0:
                spot = self._get_spy_spot()
                anchor = spot if spot is not None else float(chain_df["strike"].median())

            now = datetime.now(timezone.utc)
            candidate_df = chain_df.copy()
            candidate_df["_distance"] = (candidate_df["strike"].astype(float) - float(anchor)).abs()
            candidate_df = candidate_df.sort_values(["_distance", "expiry", "option_type"]).head(6)

            thresholds = self._get_liquidity_thresholds()
            candidates = [
                self._build_liquidity_candidate(row, now, thresholds)
                for _, row in candidate_df.iterrows()
            ]

            updated_metrics["LIQUIDITY_DIAGNOSTICS"] = {
                "feed": "liquidity_diagnostics",
                "version": "1.0",
                "mode": "observe",
                "session_id": f"s07-{self.client_id}",
                "published_ts": now.isoformat(),
                "data": {
                    "symbol": "SPY",
                    "source": "SpyderN03_OptionsChainManager",
                    "anchor_strike": float(anchor),
                    "candidate_count": len(candidates),
                    "candidates": candidates,
                },
            }
            return True
        except Exception as e:
            errors.append(f"liquidity diagnostics update failed: {e}")
            # Observe-mode diagnostics are optional; keep startup/runtime logs low-noise.
            _now = datetime.now(timezone.utc)
            _msg = str(e)
            _msg_changed = _msg != self._last_liquidity_diag_message
            _heartbeat_due = (
                self._last_liquidity_diag_log_ts is None
                or (_now - self._last_liquidity_diag_log_ts).total_seconds()
                >= self._liquidity_diag_heartbeat_seconds
            )
            _log = self.logger.info if (_msg_changed or _heartbeat_due) else self.logger.debug
            _log("Liquidity diagnostics unavailable: %s", e)
            if _msg_changed or _heartbeat_due:
                self._last_liquidity_diag_log_ts = _now
                self._last_liquidity_diag_message = _msg
            updated_metrics["LIQUIDITY_DIAGNOSTICS"] = {}
            return False

    def _compute_atm_iv(self, contracts: list, spot: float) -> float | None:
        """Compute ATM implied volatility as a percent using the nearest strikes."""
        if not contracts or spot <= 0:
            return None

        candidates: list[tuple[float, float]] = []
        for contract in contracts:
            strike = getattr(contract, "strike", None)
            iv = getattr(contract, "iv", None)
            if strike is None or iv is None or iv <= 0:
                continue
            candidates.append((abs(float(strike) - spot), float(iv)))

        if not candidates:
            return None

        nearest_ivs = [iv for _distance, iv in sorted(candidates, key=lambda item: item[0])[:6]]
        if not nearest_ivs:
            return None

        return float(np.mean(nearest_ivs) * 100.0)

    def _compute_ivr(self, current_iv: float) -> float:
        """Compute IV rank from the persisted SPY IV history."""
        cache_path = pathlib.Path("data/cache/spy_iv_history.json")
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        history: list[dict[str, Any]] = []
        if cache_path.exists():
            try:
                history = json.loads(cache_path.read_text())
            except Exception:
                history = []

        history.append({
            "date": datetime.now(timezone.utc).date().isoformat(),
            "iv": float(current_iv),
        })
        history = history[-252:]
        cache_path.write_text(json.dumps(history))

        iv_values = [float(entry["iv"]) for entry in history if entry.get("iv") is not None]
        if len(iv_values) < 5:
            return float("nan")

        low_iv = min(iv_values)
        high_iv = max(iv_values)
        if math.isclose(high_iv, low_iv):
            return 100.0 if math.isclose(current_iv, high_iv) else float("nan")

        return max(0.0, min(100.0, ((current_iv - low_iv) / (high_iv - low_iv)) * 100.0))

    def _compute_hv20(self, tradier_client: Any) -> float | None:
        """Compute 20-day historical volatility as an annualized percent."""
        try:
            end_date = datetime.now(timezone.utc).date()
            start_date = end_date - timedelta(days=40)
            response = tradier_client.get_historical_quotes(
                "SPY",
                interval="daily",
                start=start_date.isoformat(),
                end=end_date.isoformat(),
            )
        except Exception:
            return None

        days = response.get("history", {}).get("day", [])
        closes = []
        for day in days:
            close = day.get("close")
            if close is None or close <= 0:
                continue
            closes.append(float(close))

        if len(closes) < 20:
            return None

        log_returns = np.diff(np.log(np.asarray(closes, dtype=float)))
        if log_returns.size == 0:
            return None

        return float(np.std(log_returns, ddof=0) * np.sqrt(252) * 100.0)

    def _get_options_tradier_client(self):
        """Return a cached Tradier client for options analytics calls."""
        api_key = os.getenv("TRADIER_API_KEY", "").strip()
        account_id = os.getenv("TRADIER_ACCOUNT_ID", "").strip()
        environment_name = os.getenv("TRADIER_ENVIRONMENT", "sandbox").strip().lower() or "sandbox"

        if not api_key or not account_id:
            return None

        if self._options_tradier_client is not None:
            if self._options_tradier_env is None:
                self._options_tradier_env = environment_name
                return self._options_tradier_client
            if self._options_tradier_env == environment_name:
                return self._options_tradier_client

        try:
            tradier_module = importlib.import_module("Spyder.SpyderB_Broker.SpyderB40_TradierClient")  # noqa: E501
        except ImportError:
            tradier_module = importlib.import_module("SpyderB_Broker.SpyderB40_TradierClient")

        environment_enum = getattr(tradier_module.TradingEnvironment, environment_name.upper(), None)  # noqa: E501
        if environment_enum is None:
            environment_enum = tradier_module.TradingEnvironment.SANDBOX

        self._options_tradier_client = tradier_module.TradierClient(
            api_key=api_key,
            account_id=account_id,
            environment=environment_enum,
        )
        self._options_tradier_env = environment_name
        return self._options_tradier_client

    def _get_vol_surface_builder(self):
        """Return a cached volatility surface builder."""
        if self._vol_surface_builder is not None:
            return self._vol_surface_builder

        try:
            vol_module = importlib.import_module("Spyder.SpyderN_OptionsAnalytics.SpyderN06_VolatilitySurfaceBuilder")  # noqa: E501
        except ImportError:
            vol_module = importlib.import_module("SpyderN_OptionsAnalytics.SpyderN06_VolatilitySurfaceBuilder")  # noqa: E501

        self._vol_surface_builder = vol_module.VolatilitySurfaceBuilder(config={"smoothing": 0.0})
        return self._vol_surface_builder

    def _get_n09_gex_analyzer(self):
        """Return a cached N09 GammaExposureCalculator instance."""
        if self._n09_gex_analyzer is not None:
            return self._n09_gex_analyzer
        try:
            mod = importlib.import_module("Spyder.SpyderN_OptionsAnalytics.SpyderN09_GammaExposure")
        except ImportError:
            mod = importlib.import_module("SpyderN_OptionsAnalytics.SpyderN09_GammaExposure")
        self._n09_gex_analyzer = mod.GammaExposureCalculator()
        return self._n09_gex_analyzer

    def _get_n11_flow_analyzer(self):
        """Return a cached N11 OptionsGreeksFlowAnalyzer instance."""
        if self._n11_flow_analyzer is not None:
            return self._n11_flow_analyzer
        try:
            mod = importlib.import_module("Spyder.SpyderN_OptionsAnalytics.SpyderN11_OptionsGreeksFlow")  # noqa: E501
        except ImportError:
            mod = importlib.import_module("SpyderN_OptionsAnalytics.SpyderN11_OptionsGreeksFlow")
        self._n11_flow_analyzer = mod.OptionsGreeksFlowAnalyzer()
        return self._n11_flow_analyzer

    def _update_dealer_flow_metrics(self, updated_metrics: dict, errors: list) -> bool:
        """Update dealer-flow structure metrics from N09 (gamma walls) and N11 (vanna/charm)."""
        # Seed keys with existing cached values as defaults
        scalar_defaults = {
            "ZERO_GAMMA": self.current_metrics.get("ZERO_GAMMA", float("nan")),
            "WALL_CONFIDENCE": self.current_metrics.get("WALL_CONFIDENCE", float("nan")),
            "VANNA_PRESSURE": self.current_metrics.get("VANNA_PRESSURE", float("nan")),
            "CHARM_PRESSURE": self.current_metrics.get("CHARM_PRESSURE", float("nan")),
            "FLOW_IMBALANCE": self.current_metrics.get("FLOW_IMBALANCE", float("nan")),
        }
        for key, val in scalar_defaults.items():
            updated_metrics.setdefault(key, val)
        updated_metrics.setdefault("DEALER_FLOW", self.current_metrics.get("DEALER_FLOW", {}))

        ok_n09 = False
        ok_n11 = False

        # --- N09: gamma walls + zero-gamma level ---
        try:
            gex = self._get_n09_gex_analyzer()
            walls = gex.get_dealer_walls_snapshot()
            updated_metrics["ZERO_GAMMA"] = float(walls.get("zero_gamma_level", float("nan")))
            updated_metrics["WALL_CONFIDENCE"] = float(walls.get("wall_confidence", float("nan")))
            updated_metrics.setdefault("DEALER_FLOW", {})
            updated_metrics["DEALER_FLOW"].update({
                "zero_gamma_level": walls.get("zero_gamma_level"),
                "spot_to_zero_gamma_pct": walls.get("spot_to_zero_gamma_pct"),
                "call_wall_levels": walls.get("call_wall_levels", []),
                "put_wall_levels": walls.get("put_wall_levels", []),
                "wall_confidence": walls.get("wall_confidence"),
                "net_gex": walls.get("net_gex"),
                "regime": walls.get("regime"),
                "walls_snapshot_ts": walls.get("snapshot_ts"),
            })
            ok_n09 = True
        except Exception as e:
            errors.append(f"dealer walls update failed: {e}")

        # --- N11: vanna/charm pressure ---
        try:
            flow = self._get_n11_flow_analyzer()
            vc = flow.get_vanna_charm_snapshot()
            updated_metrics["VANNA_PRESSURE"] = float(vc.get("vanna_pressure", float("nan")))
            updated_metrics["CHARM_PRESSURE"] = float(vc.get("charm_pressure", float("nan")))
            updated_metrics["FLOW_IMBALANCE"] = float(vc.get("flow_imbalance_score", float("nan")))
            updated_metrics.setdefault("DEALER_FLOW", {})
            updated_metrics["DEALER_FLOW"].update({
                "vanna_pressure": vc.get("vanna_pressure"),
                "charm_pressure": vc.get("charm_pressure"),
                "flow_imbalance_score": vc.get("flow_imbalance_score"),
                "dealer_position": vc.get("dealer_position"),
                "flow_snapshot_ts": vc.get("snapshot_ts"),
            })
            ok_n11 = True
        except Exception as e:
            errors.append(f"vanna charm update failed: {e}")

        # Update quality bucket
        if ok_n09 or ok_n11:
            if "DEALER_FLOW" in self.metric_quality:
                q = self.metric_quality["DEALER_FLOW"]
                q.last_successful_update = datetime.now(timezone.utc)
                q.data_points += 1
                q.quality_score = min(1.0, q.quality_score + 0.01)

        return ok_n09 and ok_n11

    def _update_options_analytics_metrics(self, updated_metrics: dict, errors: list) -> bool:
        """Update ATM IV, IV rank, and volatility risk premium metrics."""
        updated_metrics.setdefault("IVR", self.current_metrics.get("IVR", float("nan")))
        updated_metrics.setdefault("ATM_IV", self.current_metrics.get("ATM_IV", float("nan")))
        updated_metrics.setdefault("VRP", self.current_metrics.get("VRP", float("nan")))

        client = self._get_options_tradier_client()
        if client is None:
            return False

        try:
            spot = self._get_spy_spot()
            if spot is None or spot <= 0:
                raise ValueError("SPY spot unavailable for options analytics")

            expirations_response = client.get_option_expirations("SPY")
            expirations = expirations_response.get("expirations", {}).get("date", [])
            if not expirations:
                raise ValueError("No SPY option expirations available")

            contracts = client.get_option_chain_with_greeks("SPY", expirations[0])
            atm_iv = self._compute_atm_iv(contracts, spot)
            if atm_iv is None:
                raise ValueError("ATM IV unavailable from option chain")

            hv20 = self._compute_hv20(client)
            updated_metrics["ATM_IV"] = atm_iv
            updated_metrics["IVR"] = self._compute_ivr(atm_iv)
            updated_metrics["VRP"] = atm_iv - hv20 if hv20 is not None else float("nan")
            return True
        except Exception as e:
            errors.append(f"options analytics update failed: {e}")
            return False

    def _update_vol_surface_metrics(self, updated_metrics: dict, errors: list) -> bool:
        """Update volatility-surface term nodes and smile structure metrics."""
        metric_defaults = {
            "ATM_IV_0DTE": self.current_metrics.get("ATM_IV_0DTE", float("nan")),
            "ATM_IV_1DTE": self.current_metrics.get("ATM_IV_1DTE", float("nan")),
            "ATM_IV_7DTE": self.current_metrics.get("ATM_IV_7DTE", float("nan")),
            "ATM_IV_30DTE": self.current_metrics.get("ATM_IV_30DTE", float("nan")),
            "TERM_SLOPE_0_7": self.current_metrics.get("TERM_SLOPE_0_7", float("nan")),
            "TERM_SLOPE_7_30": self.current_metrics.get("TERM_SLOPE_7_30", float("nan")),
            "RR_25D": self.current_metrics.get("RR_25D", float("nan")),
            "FLY_25D": self.current_metrics.get("FLY_25D", float("nan")),
            "SURFACE_CONFIDENCE": self.current_metrics.get("SURFACE_CONFIDENCE", float("nan")),
            "SURFACE_AGE_MS": self.current_metrics.get("SURFACE_AGE_MS", float("nan")),
        }
        updated_metrics.update({key: updated_metrics.get(key, value) for key, value in metric_defaults.items()})  # noqa: E501

        try:
            builder = self._get_vol_surface_builder()
            snapshot = builder.get_term_structure_snapshot("SPY")
            updated_metrics["ATM_IV_0DTE"] = float(snapshot.get("atm_iv_0dte", float("nan")))
            updated_metrics["ATM_IV_1DTE"] = float(snapshot.get("atm_iv_1dte", float("nan")))
            updated_metrics["ATM_IV_7DTE"] = float(snapshot.get("atm_iv_7dte", float("nan")))
            updated_metrics["ATM_IV_30DTE"] = float(snapshot.get("atm_iv_30dte", float("nan")))
            updated_metrics["TERM_SLOPE_0_7"] = float(snapshot.get("term_slope_0_7", float("nan")))
            updated_metrics["TERM_SLOPE_7_30"] = float(snapshot.get("term_slope_7_30", float("nan")))  # noqa: E501
            updated_metrics["RR_25D"] = float(snapshot.get("rr_25d", float("nan")))
            updated_metrics["FLY_25D"] = float(snapshot.get("fly_25d", float("nan")))
            updated_metrics["SURFACE_CONFIDENCE"] = float(snapshot.get("surface_confidence", float("nan")))  # noqa: E501
            updated_metrics["SURFACE_AGE_MS"] = float(snapshot.get("surface_age_ms", float("nan")))
            return True
        except Exception as e:
            errors.append(f"vol surface update failed: {e}")
            return False

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
                    quality.last_successful_update = datetime.now(timezone.utc)
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
            self.stress_history.append((datetime.now(timezone.utc), new_stress_level))
            self.stress_level_changed.emit(new_stress_level.value)

            self.logger.info("🎯 Market stress level changed to: %s", new_stress_level.value.upper())  # noqa: E501

        # Adjust update frequency if needed
        if new_interval != self.current_update_interval:
            self.current_update_interval = new_interval
            self.update_timer.setInterval(new_interval * 1000)
            self.last_frequency_change = datetime.now(timezone.utc)

            self.logger.info("⚡ Update frequency adjusted to %ss (stress: %s)", new_interval, new_stress_level.value)  # noqa: E501

    def _format_metrics(self, metrics: dict) -> dict:
        """Format metrics for display with enhanced information"""
        timestamp = datetime.now(timezone.utc)

        def _is_nan(value: Any) -> bool:
            return isinstance(value, float) and math.isnan(value)

        def _format_ivr(value: Any) -> str:
            return "---" if _is_nan(value) else f"{float(value):.0f}"

        def _format_atm_iv(value: Any) -> str:
            return "---" if _is_nan(value) else f"{float(value):.1f}%"

        def _format_vrp(value: Any) -> str:
            return "---" if _is_nan(value) else f"{float(value):+.1f}"

        def _format_float(value: Any, digits: int = 2, suffix: str = "") -> str:
            return "---" if _is_nan(value) else f"{float(value):.{digits}f}{suffix}"

        return {
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
                "quality": self.metric_quality['FRED'].quality_score
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
            "meta": {
                "update_frequency": self.current_update_interval,
                "stress_level": self.current_stress_level.value,
                "connection_status": self.ib_connected,
                "last_update": timestamp.isoformat()
            }
        }

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
            return self.current_metrics.get("DIX", 0)

    def get_swan(self) -> float:
        """Get current SWAN value"""
        with self._metrics_lock:
            return self.current_metrics.get("SWAN", 1)

    def get_skew(self) -> float:
        """Get current SKEW value"""
        with self._metrics_lock:
            return self.current_metrics.get("SKEW", 100)

    def get_stress_level(self) -> StressLevel:
        """Get current market stress level"""
        return self.current_stress_level

    def get_metrics_history(self, lookback_minutes: int = 60) -> list[MetricSnapshot]:
        """Get metrics history for specified lookback period"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)
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

            def _extract_change_pct(symbol: str) -> float:
                entry = payload.get(symbol)
                if not isinstance(entry, dict):
                    return float("nan")
                try:
                    return float(entry.get("change_pct", float("nan")))
                except (TypeError, ValueError):
                    return float("nan")

            snapshot = {
                "spy_change_pct": _extract_change_pct("SPY"),
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
            return {
                'dix_score': self.current_metrics.get('DIX', 42.5),
                'gex_level': self.current_metrics.get('GEX', -2.5),
                'swan_score': self.current_metrics.get('SWAN', 1.85),
                'skew_level': self.current_metrics.get('SKEW', 125.5),
                # Lowercase aliases consumed directly by F09 trust-gate filters.
                'vix': self.current_metrics.get('VIX', float('nan')),
                'vix9d': self.current_metrics.get('VIX9D', float('nan')),
                'vxv': self.current_metrics.get('VXV', float('nan')),
                'vvix': self.current_metrics.get('VVIX', float('nan')),
                'cpc': self.current_metrics.get('CPC', float('nan')),
                'rvol': self.current_metrics.get('RVOL', float('nan')),
                'dex_level': self.current_metrics.get('DEX', 850),
                'ogl_level': self.current_metrics.get('OGL', 585.5),
                'vex': self.current_metrics.get('VEX', 0.0),
                'chex': self.current_metrics.get('CHEX', 0.0),
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
                'ivr': self.current_metrics.get('IVR', float('nan')),
                'atm_iv': self.current_metrics.get('ATM_IV', float('nan')),
                'vrp': self.current_metrics.get('VRP', float('nan')),
                'atm_iv_0dte': self.current_metrics.get('ATM_IV_0DTE', float('nan')),
                'atm_iv_1dte': self.current_metrics.get('ATM_IV_1DTE', float('nan')),
                'atm_iv_7dte': self.current_metrics.get('ATM_IV_7DTE', float('nan')),
                'atm_iv_30dte': self.current_metrics.get('ATM_IV_30DTE', float('nan')),
                'term_slope_0_7': self.current_metrics.get('TERM_SLOPE_0_7', float('nan')),
                'term_slope_7_30': self.current_metrics.get('TERM_SLOPE_7_30', float('nan')),
                'rr_25d': self.current_metrics.get('RR_25D', float('nan')),
                'fly_25d': self.current_metrics.get('FLY_25D', float('nan')),
                'surface_confidence': self.current_metrics.get('SURFACE_CONFIDENCE', float('nan')),
                'surface_age_ms': self.current_metrics.get('SURFACE_AGE_MS', float('nan')),
                'zero_gamma': self.current_metrics.get('ZERO_GAMMA', float('nan')),
                'wall_confidence': self.current_metrics.get('WALL_CONFIDENCE', float('nan')),
                'vanna_pressure': self.current_metrics.get('VANNA_PRESSURE', float('nan')),
                'charm_pressure': self.current_metrics.get('CHARM_PRESSURE', float('nan')),
                'flow_imbalance': self.current_metrics.get('FLOW_IMBALANCE', float('nan')),
                'dealer_flow': self.current_metrics.get('DEALER_FLOW', {}),
                'spy_change_pct': index_snapshot.get('spy_change_pct', self.current_metrics.get('SPY_CHANGE_PCT', float('nan'))),
                'qqq_change_pct': index_snapshot.get('qqq_change_pct', self.current_metrics.get('QQQ_CHANGE_PCT', float('nan'))),
                'iwm_change_pct': index_snapshot.get('iwm_change_pct', self.current_metrics.get('IWM_CHANGE_PCT', float('nan'))),
                'xlk_change_pct': index_snapshot.get('xlk_change_pct', self.current_metrics.get('XLK_CHANGE_PCT', float('nan'))),
                'xlf_change_pct': index_snapshot.get('xlf_change_pct', self.current_metrics.get('XLF_CHANGE_PCT', float('nan'))),
                'stress_level': self.current_stress_level.value,
                'update_frequency': self.current_update_interval,
                'timestamp': datetime.now(timezone.utc),
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


