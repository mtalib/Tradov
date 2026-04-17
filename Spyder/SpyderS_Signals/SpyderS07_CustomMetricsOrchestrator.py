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
import logging
import threading
import time
from datetime import datetime, timedelta
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
    from SpyderS_Signals.SpyderS05_GEXDEXCalculator import DataUnavailableError as GEXDataUnavailableError
    GEX_AVAILABLE = True
except ImportError:
    GEX_AVAILABLE = False
    GEXDataUnavailableError = Exception
    logging.info("⚠️ S05_GEXDEXCalculator not available")

try:
    from SpyderS_Signals.SpyderS06_SKEWCalculator import (
        SpyderS06_SKEWCalculator, get_skew_calculator)  # noqa: F401
    from SpyderS_Signals.SpyderS06_SKEWCalculator import DataUnavailableError as SKEWDataUnavailableError
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
    from SpyderS_Signals.SpyderS04_BlackSwanScheduler import BlackSwanScheduler as BlackSwanSchedulerCls
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
    timestamp: datetime = field(default_factory=datetime.now)
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
            "BREADTH_REGIME": "neutral",
        }

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
        self.last_frequency_change = datetime.now()

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
        self.logger.debug("⚠️ Regime detection functions removed - now handled by L09_UnifiedRegimeEngine")

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
        metrics = ['GEX', 'DEX', 'OGL', 'DIX', 'SWAN', 'SKEW', 'VEX', 'CHEX', 'FRED', 'SENTIMENT', 'BREADTH']

        for metric in metrics:
            self.metric_quality[metric] = MetricQuality(
                metric_name=metric,
                quality_score=1.0,  # Start with perfect score
                data_points=0,
                last_successful_update=datetime.now(),
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
                self.logger.debug("✅ S04_BlackSwanScheduler started (4:00 AM / 9:15 AM / 12:00 PM / 3:45 PM ET)")

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
                    self.logger.warning("⚠️ DIX scheduler init failed; skipping scheduled collection")
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

                # Update stored values
                self.current_metrics.update(updated_metrics)

                # Update quality tracking
                self._update_quality_metrics(updated_metrics, update_errors)

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
                    fred_success, sentiment_success, breadth_success,
                ])

                # Only log at INFO when key values change; use DEBUG for unchanged cycles.
                _summary = (
                    f"{success_count}/7 | "
                    f"GEX={updated_metrics.get('GEX', 0):.1f}B "
                    f"DIX={updated_metrics.get('DIX', 0):.1f}% "
                    f"SWAN={updated_metrics.get('SWAN', 1):.2f} "
                    f"SKEW={updated_metrics.get('SKEW', 100):.1f} "
                    f"TICK={updated_metrics.get('TICK', float('nan'))}"
                )
                _last = getattr(self, "_last_metrics_summary", None)
                _log = self.logger.info if _summary != _last else self.logger.debug
                _log(
                    f"📊 Metrics updated: {success_count}/7 sources successful "
                    f"(GEX={updated_metrics.get('GEX', 0):.1f}B, "
                    f"DIX={updated_metrics.get('DIX', 0):.1f}%, "
                    f"SWAN={updated_metrics.get('SWAN', 1):.2f}, "
                    f"SKEW={updated_metrics.get('SKEW', 100):.1f}, "
                    f"TICK={updated_metrics.get('TICK', float('nan'))}, "
                    f"10Y={updated_metrics.get('YIELD_10Y', float('nan')):.2f}%) "
                    f"[{calculation_time:.2f}s]"
                )
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
                updated_metrics["SWAN"] = max(1.0, min(5.0, current_swan + np.random.normal(0, 0.1)))
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
        try:
            if self.tv_client:
                snap = self.tv_client.get_snapshot()
                updated_metrics["TICK"] = snap.get("tick", float("nan"))
                updated_metrics["ADD"]  = snap.get("add",  float("nan"))
                updated_metrics["TRIN"] = snap.get("trin", float("nan"))
                updated_metrics["BREADTH_REGIME"] = snap.get("breadth_regime", "neutral")
                self.breadth_updated.emit(snap)
                return True
            else:
                for key in ("TICK", "ADD", "TRIN"):
                    updated_metrics[key] = self.current_metrics.get(key, float("nan"))
                updated_metrics["BREADTH_REGIME"] = self.current_metrics.get("BREADTH_REGIME", "neutral")
                return False
        except Exception as e:
            errors.append(f"Breadth update error: {e}")
            self.logger.error("Breadth update error: %s", e, exc_info=True)
            for key in ("TICK", "ADD", "TRIN"):
                updated_metrics[key] = self.current_metrics.get(key, float("nan"))
            updated_metrics["BREADTH_REGIME"] = self.current_metrics.get("BREADTH_REGIME", "neutral")
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
                    quality.last_successful_update = datetime.now()
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
            self.stress_history.append((datetime.now(), new_stress_level))
            self.stress_level_changed.emit(new_stress_level.value)

            self.logger.info("🎯 Market stress level changed to: %s", new_stress_level.value.upper())

        # Adjust update frequency if needed
        if new_interval != self.current_update_interval:
            self.current_update_interval = new_interval
            self.update_timer.setInterval(new_interval * 1000)
            self.last_frequency_change = datetime.now()

            self.logger.info("⚡ Update frequency adjusted to %ss (stress: %s)", new_interval, new_stress_level.value)

    def _format_metrics(self, metrics: dict) -> dict:
        """Format metrics for display with enhanced information"""
        timestamp = datetime.now()

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
            "BREADTH_REGIME": {
                "value": metrics.get("BREADTH_REGIME", "neutral"),
                "formatted": metrics.get("BREADTH_REGIME", "neutral").replace("_", " ").title(),
                "timestamp": timestamp,
                "quality": self.metric_quality['BREADTH'].quality_score
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
        cutoff_time = datetime.now() - timedelta(minutes=lookback_minutes)
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

    def get_current_market_conditions(self) -> dict[str, Any]:
        """
        Get current market conditions for integration with other modules.

        NOTE: This method provides data for L09_UnifiedRegimeEngine
        but does NOT perform regime detection itself.
        """
        with self._metrics_lock:
            return {
                'dix_score': self.current_metrics.get('DIX', 42.5),
                'gex_level': self.current_metrics.get('GEX', -2.5),
                'swan_score': self.current_metrics.get('SWAN', 1.85),
                'skew_level': self.current_metrics.get('SKEW', 125.5),
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
                'stress_level': self.current_stress_level.value,
                'update_frequency': self.current_update_interval,
                'timestamp': datetime.now(),
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


