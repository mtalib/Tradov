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
    GEX_AVAILABLE = True
except ImportError:
    GEX_AVAILABLE = False
    logging.info("⚠️ S05_GEXDEXCalculator not available")

try:
    from SpyderS_Signals.SpyderS06_SKEWCalculator import (
        SpyderS06_SKEWCalculator, get_skew_calculator)  # noqa: F401
    SKEW_AVAILABLE = True
except ImportError:
    SKEW_AVAILABLE = False
    logging.info("⚠️ S06_SKEWCalculator not available")

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
        self.update_timer.timeout.connect(self.update_all_metrics)
        self.update_timer.setInterval(self.current_update_interval * 1000)

        self.logger.info("CustomMetricsOrchestrator initialized (Client ID: %s)", CLIENT_ID)
        self.logger.info("⚠️ Regime detection functions removed - now handled by L09_UnifiedRegimeEngine")

        # Auto-start if configured
        if self.config.get("auto_start", True):
            self.start()

    def _init_calculators(self):
        """Initialize all available calculators"""
        # S01 - DIX Calculator
        if DIX_AVAILABLE:
            try:
                self.dix_calculator = get_calculator_instance()
                self.logger.info("✅ S01_DIXCalculator initialized")
            except Exception as e:
                self.logger.error("Failed to init DIX: %s", e, exc_info=True)
                self.dix_calculator = None
        else:
            self.dix_calculator = None

        # S03 - Black Swan Indicator
        if SWAN_AVAILABLE:
            try:
                self.swan_indicator = get_black_swan_indicator()
                self.logger.info("✅ S03_BlackSwanIndicator initialized")
            except Exception as e:
                self.logger.error("Failed to init SWAN: %s", e, exc_info=True)
                self.swan_indicator = None
        else:
            self.swan_indicator = None

        # S05 - GEX/DEX Calculator
        if GEX_AVAILABLE:
            try:
                self.gex_calculator = GEXDEXCalculator()
                self.logger.info("✅ S05_GEXDEXCalculator initialized")
            except Exception as e:
                self.logger.error("Failed to init GEX: %s", e, exc_info=True)
                self.gex_calculator = None
        else:
            self.gex_calculator = None

        # S06 - SKEW Calculator
        if SKEW_AVAILABLE:
            try:
                self.skew_calculator = get_skew_calculator()
                self.logger.info("✅ S06_SKEWCalculator initialized")
            except Exception as e:
                self.logger.error("Failed to init SKEW: %s", e, exc_info=True)
                self.skew_calculator = None
        else:
            self.skew_calculator = None

    def _init_quality_tracking(self):
        """Initialize quality tracking for all metrics"""
        metrics = ['GEX', 'DEX', 'OGL', 'DIX', 'SWAN', 'SKEW']

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
        """Start the orchestrator"""
        try:
            self.update_timer.start()
            self.update_all_metrics()  # Initial update
            self.ib_connected = True

            self.logger.info("✅ Orchestrator started successfully")
            self.connection_status_changed.emit(True, f"Client {CLIENT_ID} Active")

        except Exception as e:
            self.logger.error("Failed to start orchestrator: %s", e, exc_info=True)
            self.error_occurred.emit(f"Startup failed: {str(e)}")

    def stop(self):
        """Stop the orchestrator"""
        try:
            self.update_timer.stop()
            self.ib_connected = False

            self.logger.info("⏹️ Orchestrator stopped")
            self.connection_status_changed.emit(False, f"Client {CLIENT_ID} Stopped")

        except Exception as e:
            self.logger.error("Error stopping orchestrator: %s", e, exc_info=True)

    def update_all_metrics(self):
        """Update all metrics from S-Series calculators"""
        start_time = time.time()

        try:
            with self._metrics_lock:
                updated_metrics = {}
                update_errors = []

                # S05 - GEX/DEX/OGL Updates
                gex_success = self._update_gex_metrics(updated_metrics, update_errors)

                # S01 - DIX Updates
                dix_success = self._update_dix_metrics(updated_metrics, update_errors)

                # S03 - SWAN Updates
                swan_success = self._update_swan_metrics(updated_metrics, update_errors)

                # S06 - SKEW Updates
                skew_success = self._update_skew_metrics(updated_metrics, update_errors)

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
                success_count = sum([gex_success, dix_success, swan_success, skew_success])

                self.logger.info(
                    f"📊 Metrics updated: {success_count}/4 sources successful "
                    f"(GEX={updated_metrics.get('GEX', 0):.1f}B, "
                    f"DIX={updated_metrics.get('DIX', 0):.1f}%, "
                    f"SWAN={updated_metrics.get('SWAN', 1):.2f}, "
                    f"SKEW={updated_metrics.get('SKEW', 100):.1f}) "
                    f"[{calculation_time:.2f}s]"
                )

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
                self.gex_updated.emit(gex_data)
                return True
            else:
                # Fallback to simulation or cached values
                updated_metrics.update({
                    "GEX": self.current_metrics.get("GEX", -2.5) + np.random.normal(0, 0.1),
                    "DEX": self.current_metrics.get("DEX", 850) + np.random.normal(0, 50),
                    "OGL": self.current_metrics.get("OGL", 585.5) + np.random.normal(0, 1)
                })
                return False
        except Exception as e:
            errors.append(f"GEX update error: {e}")
            self.logger.error("GEX update error: %s", e, exc_info=True)
            # Use previous values
            updated_metrics.update({
                "GEX": self.current_metrics.get("GEX", -2.5),
                "DEX": self.current_metrics.get("DEX", 850),
                "OGL": self.current_metrics.get("OGL", 585.5)
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
        except Exception as e:
            errors.append(f"SKEW update error: {e}")
            self.logger.error("SKEW update error: %s", e, exc_info=True)
            updated_metrics["SKEW"] = self.current_metrics.get("SKEW", 125.5)
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


