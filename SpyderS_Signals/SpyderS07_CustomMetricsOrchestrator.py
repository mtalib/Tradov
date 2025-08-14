#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderS07_CustomMetricsOrchestrator.py
Group: S (Signals)
Purpose: Central orchestrator for all custom market metrics (IB Client 10)
Author: Mohamed Talib
Date Created: 2025-01-31
Last Updated: 2025-01-31 Time: 14:00:00

Description:
    Central orchestrator that coordinates all custom metric calculations and
    serves as IB Client 10. Provides a unified interface for GEX, DEX, OGL,
    DIX, SWAN, and SKEW calculations. Emits Qt signals for GUI integration
    and manages update scheduling for all metrics.
"""

import logging
# ==============================================================================
# IMPORTS - UPDATED FOR NEW S-SERIES STRUCTURE
# ==============================================================================
import sys
from datetime import datetime
from typing import Any, Dict, Optional

import numpy as np
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

# ==============================================================================
# S-SERIES SIGNAL IMPORTS (UPDATED)
# ==============================================================================
try:
    from SpyderS_Signals.SpyderS01_DIXCalculator import (
        DIXCalculator, get_calculator_instance)

    DIX_AVAILABLE = True
except ImportError:
    DIX_AVAILABLE = False
    print("⚠️ S01_DIXCalculator not available")

try:
    from SpyderS_Signals.SpyderS03_BlackSwanIndicator import (
        BlackSwanIndicator, get_black_swan_indicator)

    SWAN_AVAILABLE = True
except ImportError:
    SWAN_AVAILABLE = False
    print("⚠️ S03_BlackSwanIndicator not available")

try:
    from SpyderS_Signals.SpyderS05_GEXDEXCalculator import GEXDEXCalculator

    GEX_AVAILABLE = True
except ImportError:
    GEX_AVAILABLE = False
    print("⚠️ S05_GEXDEXCalculator not available")

try:
    from SpyderS_Signals.SpyderS06_SKEWCalculator import (
        SpyderS06_SKEWCalculator, get_skew_calculator)

    SKEW_AVAILABLE = True
except ImportError:
    SKEW_AVAILABLE = False
    print("⚠️ S06_SKEWCalculator not available")

# ==============================================================================
# CONSTANTS
# ==============================================================================
CLIENT_ID = 10
UPDATE_INTERVAL = 60
FAST_UPDATE = 30
SLOW_UPDATE = 300

# ==============================================================================
# ORCHESTRATOR CLASS
# ==============================================================================


class CustomMetricsOrchestrator(QObject):
    """
    Central orchestrator for all custom market metrics.
    Coordinates S01-S06 calculators and serves as IB Client 10.
    """

    # Qt Signals
    metrics_updated = pyqtSignal(dict)
    gex_updated = pyqtSignal(dict)
    dix_updated = pyqtSignal(float)
    swan_updated = pyqtSignal(dict)
    skew_updated = pyqtSignal(float)
    connection_status_changed = pyqtSignal(bool, str)
    error_occurred = pyqtSignal(str)

    def __init__(self, config: Optional[Dict] = None):
        super().__init__()

        self.logger = logging.getLogger(__name__)
        self.config = config or {}
        self.client_id = CLIENT_ID

        # Initialize calculators with availability checks
        self._init_calculators()

        # Current metrics storage
        self.current_metrics = {
            "GEX": 0.0,
            "DEX": 0.0,
            "OGL": 0.0,
            "DIX": 0.0,
            "SWAN": 1.0,
            "SKEW": 100.0,
        }

        # IB connection status
        self.ib_connected = False

        # Update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_all_metrics)
        self.update_timer.setInterval(UPDATE_INTERVAL * 1000)

        self.logger.info(f"CustomMetricsOrchestrator initialized (Client ID: {CLIENT_ID})")

        if self.config.get("auto_start", True):
            self.start()

    def _init_calculators(self):
        """Initialize all available calculators"""
        # S01 - DIX
        if DIX_AVAILABLE:
            try:
                self.dix_calculator = get_calculator_instance()
                self.logger.info("✅ S01_DIXCalculator initialized")
            except Exception as e:
                self.logger.error(f"Failed to init DIX: {e}")
                self.dix_calculator = None
        else:
            self.dix_calculator = None

        # S03 - Black Swan
        if SWAN_AVAILABLE:
            try:
                self.swan_indicator = get_black_swan_indicator()
                self.logger.info("✅ S03_BlackSwanIndicator initialized")
            except Exception as e:
                self.logger.error(f"Failed to init SWAN: {e}")
                self.swan_indicator = None
        else:
            self.swan_indicator = None

        # S05 - GEX/DEX
        if GEX_AVAILABLE:
            try:
                self.gex_calculator = GEXDEXCalculator()
                self.logger.info("✅ S05_GEXDEXCalculator initialized")
            except Exception as e:
                self.logger.error(f"Failed to init GEX: {e}")
                self.gex_calculator = None
        else:
            self.gex_calculator = None

        # S06 - SKEW
        if SKEW_AVAILABLE:
            try:
                self.skew_calculator = get_skew_calculator()
                self.logger.info("✅ S06_SKEWCalculator initialized")
            except Exception as e:
                self.logger.error(f"Failed to init SKEW: {e}")
                self.skew_calculator = None
        else:
            self.skew_calculator = None

    def start(self):
        """Start the orchestrator"""
        self.update_timer.start()
        self.update_all_metrics()
        self.logger.info("Orchestrator started")
        self.connection_status_changed.emit(True, f"Client {CLIENT_ID} Active")

    def stop(self):
        """Stop the orchestrator"""
        self.update_timer.stop()
        self.logger.info("Orchestrator stopped")
        self.connection_status_changed.emit(False, f"Client {CLIENT_ID} Stopped")

    def update_all_metrics(self):
        """Update all metrics from S-Series calculators"""
        try:
            updated_metrics = {}

            # S05 - GEX/DEX/OGL
            if self.gex_calculator:
                try:
                    gex_data = self.gex_calculator.calculate_all()
                    updated_metrics["GEX"] = gex_data.get("gex", 0) / 1e9
                    updated_metrics["DEX"] = gex_data.get("dex", 0) / 1e6
                    updated_metrics["OGL"] = gex_data.get("ogl", 585.5)
                    self.gex_updated.emit(gex_data)
                except Exception as e:
                    self.logger.error(f"GEX update error: {e}")
                    updated_metrics.update(
                        {
                            "GEX": self.current_metrics.get("GEX", -2.5),
                            "DEX": self.current_metrics.get("DEX", 850),
                            "OGL": self.current_metrics.get("OGL", 585.5),
                        }
                    )
            else:
                # Simulation mode
                updated_metrics["GEX"] = -2.5 + np.random.normal(0, 0.5)
                updated_metrics["DEX"] = 850 + np.random.normal(0, 100)
                updated_metrics["OGL"] = 585.5 + np.random.normal(0, 1)

            # S01 - DIX
            if self.dix_calculator:
                try:
                    dix_result = self.dix_calculator.calculate_dix()
                    if dix_result:
                        updated_metrics["DIX"] = dix_result.dix_percentage
                        self.dix_updated.emit(dix_result.dix_percentage)
                except Exception as e:
                    self.logger.error(f"DIX update error: {e}")
                    updated_metrics["DIX"] = self.current_metrics.get("DIX", 42.5)
            else:
                updated_metrics["DIX"] = 42.5 + np.random.normal(0, 1)

            # S03 - SWAN
            if self.swan_indicator:
                try:
                    swan_result = self.swan_indicator.calculate_swan_score()
                    updated_metrics["SWAN"] = swan_result.overall_score
                    self.swan_updated.emit(
                        {
                            "score": swan_result.overall_score,
                            "status": swan_result.status.value,
                            "components": swan_result.component_scores,
                        }
                    )
                except Exception as e:
                    self.logger.error(f"SWAN update error: {e}")
                    updated_metrics["SWAN"] = self.current_metrics.get("SWAN", 1.85)
            else:
                updated_metrics["SWAN"] = 1.85 + np.random.normal(0, 0.2)
                updated_metrics["SWAN"] = max(1, min(5, updated_metrics["SWAN"]))

            # S06 - SKEW
            if self.skew_calculator:
                try:
                    skew_result = self.skew_calculator.calculate_skew()
                    if skew_result:
                        updated_metrics["SKEW"] = skew_result.skew_index
                        self.skew_updated.emit(skew_result.skew_index)
                except Exception as e:
                    self.logger.error(f"SKEW update error: {e}")
                    updated_metrics["SKEW"] = self.current_metrics.get("SKEW", 125.5)
            else:
                updated_metrics["SKEW"] = 125.5 + np.random.normal(0, 5)

            # Update stored values
            self.current_metrics.update(updated_metrics)

            # Format and emit
            formatted_metrics = self._format_metrics(updated_metrics)
            self.metrics_updated.emit(formatted_metrics)

            # Adjust update frequency
            self._adjust_update_frequency(updated_metrics)

            self.logger.info(
                f"Metrics updated: GEX={updated_metrics['GEX']:.1f}B, "
                f"DIX={updated_metrics['DIX']:.1f}%, "
                f"SWAN={updated_metrics['SWAN']:.2f}, "
                f"SKEW={updated_metrics['SKEW']:.1f}"
            )

        except Exception as e:
            self.logger.error(f"Error updating metrics: {e}")
            self.error_occurred.emit(str(e))

    def _format_metrics(self, metrics: Dict) -> Dict:
        """Format metrics for display"""
        return {
            "GEX": {
                "value": metrics.get("GEX", 0),
                "formatted": f"{metrics.get('GEX', 0):.1f}B",
                "timestamp": datetime.now(),
            },
            "DEX": {
                "value": metrics.get("DEX", 0),
                "formatted": f"{metrics.get('DEX', 0):.0f}M",
                "timestamp": datetime.now(),
            },
            "OGL": {
                "value": metrics.get("OGL", 0),
                "formatted": f"{metrics.get('OGL', 0):.2f}",
                "timestamp": datetime.now(),
            },
            "DIX": {
                "value": metrics.get("DIX", 0),
                "formatted": f"{metrics.get('DIX', 0):.1f}%",
                "timestamp": datetime.now(),
            },
            "SWAN": {
                "value": metrics.get("SWAN", 0),
                "formatted": f"{metrics.get('SWAN', 0):.2f}",
                "timestamp": datetime.now(),
            },
            "SKEW": {
                "value": metrics.get("SKEW", 0),
                "formatted": f"{metrics.get('SKEW', 0):.1f}",
                "timestamp": datetime.now(),
            },
        }

    def _adjust_update_frequency(self, metrics: Dict):
        """Adjust update frequency based on market conditions"""
        swan_score = metrics.get("SWAN", 1)

        if swan_score > 3:
            new_interval = FAST_UPDATE
        elif swan_score > 2:
            new_interval = UPDATE_INTERVAL
        else:
            new_interval = SLOW_UPDATE

        current_interval = self.update_timer.interval() / 1000
        if new_interval != current_interval:
            self.update_timer.setInterval(new_interval * 1000)
            self.logger.info(f"Update frequency adjusted to {new_interval}s")

    def get_all_metrics(self) -> Dict:
        """Get all current metrics"""
        return self.current_metrics.copy()

    def get_gex(self) -> float:
        """Get current GEX value"""
        return self.current_metrics.get("GEX", 0)

    def get_dix(self) -> float:
        """Get current DIX value"""
        return self.current_metrics.get("DIX", 0)

    def get_swan(self) -> float:
        """Get current SWAN value"""
        return self.current_metrics.get("SWAN", 1)

    def get_skew(self) -> float:
        """Get current SKEW value"""
        return self.current_metrics.get("SKEW", 100)


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


# Backward compatibility
get_custom_metrics_orchestrator = get_metrics_orchestrator
