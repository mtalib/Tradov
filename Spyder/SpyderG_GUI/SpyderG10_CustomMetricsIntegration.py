#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderG10_CustomMetricsIntegration.py
Group: G (GUI/User Interface)
Purpose: [DEPRECATED] Dashboard integration for Client 10 (Custom Metrics)
Author: Mohamed Talib
Date Created: 2025-08-12
Last Updated: 2026-02-25 Time: 21:45:00

DEPRECATION NOTICE:
    This module is DEPRECATED as of the Tradier+Databento migration (Feb 2026).
    It was designed for Client 10 (Custom Metrics) from
    SpyderB19_Client10Configuration, which used the IB Gateway multi-client
    architecture. That architecture no longer exists.

    Custom metrics (GEX, DEX, OGL, DIX, SWAN) should now be sourced from:
    - SpyderC26_DatabentoClient for market data
    - SpyderN_OptionsAnalytics for options-derived metrics
    - SpyderF_Analysis for technical indicators

    This module is preserved for backward compatibility only.
"""

import warnings
warnings.warn(
    "SpyderG10_CustomMetricsIntegration is DEPRECATED. "
    "The system has migrated from IBKR Client 10 (SpyderB19_Client10Configuration) "
    "to Tradier API + Databento. Use SpyderN_OptionsAnalytics for custom metrics.",
    DeprecationWarning,
    stacklevel=2
)

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QGroupBox, QHBoxLayout, QLabel, QVBoxLayout,
                            QWidget)

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from SpyderB_Broker.SpyderB19_Client10Configuration import (
        Client10Configuration, create_default_config)
    from SpyderS_Signals.SpyderS07_CustomMetricsOrchestrator import (
        CustomMetricsOrchestrator, get_metrics_client)

    METRICS_CLIENT_AVAILABLE = True
except ImportError:
    METRICS_CLIENT_AVAILABLE = False
    logging.info("⚠️ Custom Metrics Client modules not available")

try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

    LOCAL_IMPORTS = True
except ImportError:
    LOCAL_IMPORTS = False

# ==============================================================================
# CONSTANTS
# ==============================================================================
COLORS = {
    "positive": "#00ff41",
    "negative": "#ff1744",
    "neutral": "#ffd700",
    "warning": "#ff9800",
    "text": "#ffffff",
    "text_dim": "#888888",
    "background": "#0a0a0a",
    "panel": "#1a1a1a",
}

# Metric display configurations
METRIC_DISPLAY = {
    "GEX": {
        "full_name": "Gamma Exposure",
        "tooltip": "Net gamma exposure in billions. Negative = dealers short gamma",
        "thresholds": {"positive": 0, "warning": -2, "negative": -4},
    },
    "DEX": {
        "full_name": "Delta Exposure",
        "tooltip": "Net delta exposure in millions. Shows directional positioning",
        "thresholds": {"positive": 0, "warning": -1000, "negative": -2000},
    },
    "OGL": {
        "full_name": "Zero Gamma Level",
        "tooltip": "Price level where gamma exposure equals zero. Key support/resistance",
        "thresholds": None,  # OGL uses special coloring
    },
    "DIX": {
        "full_name": "Dark Index",
        "tooltip": "Dark pool buying percentage. >45% bullish, <40% bearish",
        "thresholds": {"positive": 45, "warning": 42, "negative": 40},
    },
    "SWAN": {
        "full_name": "Black Swan Risk",
        "tooltip": "Tail risk indicator (1-5 scale). >2.5 elevated risk",
        "thresholds": {"positive": 2.0, "warning": 2.5, "negative": 3.5},
    },
}

# ==============================================================================
# CUSTOM METRICS INTEGRATION
# ==============================================================================


class CustomMetricsIntegration(QObject):
    """
    Main integration class for Custom Metrics (Client 10) with the dashboard.
    Manages the connection, data flow, and signal emission for GUI updates.
    """

    # Signals
    metrics_updated = Signal(dict)  # Emits formatted metrics for display
    connection_status_changed = Signal(bool)  # Connection status
    error_occurred = Signal(str)  # Error messages
    all_metrics_updated = Signal(dict)  # Complete metrics update

    def __init__(self, parent_dashboard=None):
        """
        Initialize Custom Metrics Integration

        Args:
            parent_dashboard: Reference to main dashboard (SpyderTradingDashboard)
        """
        super().__init__()

        # Logging
        if LOCAL_IMPORTS and SpyderLogger:
            self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        else:
            self.logger = logging.getLogger(self.__class__.__name__)

        # References
        self.dashboard = parent_dashboard
        self.config = create_default_config()

        # Metrics client
        self.metrics_client = None
        self.connected = False

        # Data storage
        self.current_metrics = {}
        self.previous_metrics = {}

        # Threading
        self.worker_thread = None
        self.stop_flag = threading.Event()

        # Update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._process_metrics_update)
        self.update_timer.setInterval(5000)  # Process every 5 seconds

        self.logger.info("CustomMetricsIntegration initialized")

    # ==========================================================================
    # CONNECTION MANAGEMENT
    # ==========================================================================

    def start(self):
        """Start the custom metrics integration"""
        try:
            if not METRICS_CLIENT_AVAILABLE:
                self.logger.warning("Metrics client not available - running in simulation mode")
                self._start_simulation_mode()
                return

            # Get or create metrics client
            port = self.config.paper_port if self.config.use_paper else self.config.live_port
            self.metrics_client = get_metrics_client(port)

            # Connect signals
            self.metrics_client.metrics_updated.connect(self._on_metrics_updated)
            self.metrics_client.connection_status_changed.connect(self._on_connection_changed)
            self.metrics_client.error_occurred.connect(self._on_error)

            # Connect to IB Gateway
            if self.metrics_client.connect():
                self.connected = True
                self.connection_status_changed.emit(True)
                self.update_timer.start()
                self.logger.info("✅ Client 10 integration started successfully")
            else:
                self.logger.warning("Failed to connect Client 10 - using simulation")
                self._start_simulation_mode()

        except Exception as e:
            self.logger.error(f"Failed to start integration: {e}")
            self.error_occurred.emit(str(e))
            self._start_simulation_mode()

    def stop(self):
        """Stop the custom metrics integration"""
        try:
            self.stop_flag.set()
            self.update_timer.stop()

            if self.metrics_client:
                self.metrics_client.disconnect()

            self.connected = False
            self.connection_status_changed.emit(False)

            self.logger.info("Client 10 integration stopped")

        except Exception as e:
            self.logger.error(f"Error stopping integration: {e}")

    def _start_simulation_mode(self):
        """Start simulation mode when IB connection not available"""
        self.connected = True  # Pretend connected for simulation
        self.connection_status_changed.emit(True)

        # Start simulation worker
        self.stop_flag.clear()
        self.worker_thread = threading.Thread(target=self._simulation_worker, daemon=True)
        self.worker_thread.start()

        self.update_timer.start()
        self.logger.info("Running in simulation mode")

    def _simulation_worker(self):
        """Worker thread for simulation mode"""
        import random

        import numpy as np

        # Initialize simulation values
        gex = -2.5
        dex = 850
        ogl = 585.5
        dix = 42.5
        swan = 1.85

        while not self.stop_flag.is_set():
            try:
                # Simulate random walk
                gex += np.random.normal(0, 0.3)
                gex = max(-10, min(10, gex))

                dex += np.random.normal(0, 50)
                dex = max(-3000, min(3000, dex))

                ogl = 585.5 + np.random.normal(0, 0.5)

                dix += np.random.normal(0, 0.5)
                dix = max(30, min(55, dix))

                # SWAN with occasional spikes
                if random.random() < 0.02:  # 2% chance
                    swan = min(5, swan + random.uniform(0.5, 1.5))
                else:
                    swan = max(1, swan * 0.98)

                # Create metrics dict
                metrics = {
                    "GEX": {
                        "value": gex,
                        "formatted_value": f"{gex:.1f}B",
                        "change": random.uniform(-0.5, 0.5),
                        "change_pct": random.uniform(-2, 2),
                        "timestamp": datetime.now(),
                    },
                    "DEX": {
                        "value": dex,
                        "formatted_value": f"{dex:.0f}M",
                        "change": random.uniform(-100, 100),
                        "change_pct": random.uniform(-2, 2),
                        "timestamp": datetime.now(),
                    },
                    "OGL": {
                        "value": ogl,
                        "formatted_value": f"{ogl:.2f}",
                        "change": random.uniform(-1, 1),
                        "change_pct": random.uniform(-0.2, 0.2),
                        "timestamp": datetime.now(),
                    },
                    "DIX": {
                        "value": dix,
                        "formatted_value": f"{dix:.1f}%",
                        "change": random.uniform(-1, 1),
                        "change_pct": random.uniform(-2, 2),
                        "timestamp": datetime.now(),
                    },
                    "SWAN": {
                        "value": swan,
                        "formatted_value": f"{swan:.2f}",
                        "change": random.uniform(-0.1, 0.1),
                        "change_pct": random.uniform(-5, 5),
                        "timestamp": datetime.now(),
                    },
                }

                # Store and emit
                self.current_metrics = metrics
                self.metrics_updated.emit(metrics)

                time.sleep(5)  # Update every 5 seconds

            except Exception as e:
                self.logger.error(f"Simulation error: {e}")
                time.sleep(1)

    # ==========================================================================
    # SIGNAL HANDLERS
    # ==========================================================================

    @Slot(dict)
    def _on_metrics_updated(self, metrics: dict):
        """Handle metrics update from client"""
        self.previous_metrics = self.current_metrics.copy()
        self.current_metrics = metrics

        # Calculate changes
        for metric_name in metrics:
            if metric_name in self.previous_metrics:
                old_val = self.previous_metrics[metric_name].get("value", 0)
                new_val = metrics[metric_name].get("value", 0)

                change = new_val - old_val
                change_pct = (change / old_val * 100) if old_val != 0 else 0

                metrics[metric_name]["change"] = change
                metrics[metric_name]["change_pct"] = change_pct

        self.metrics_updated.emit(metrics)
        self.all_metrics_updated.emit(metrics)

    @Slot(bool)
    def _on_connection_changed(self, connected: bool):
        """Handle connection status change"""
        self.connected = connected
        self.connection_status_changed.emit(connected)

        if connected:
            self.logger.info("Client 10 connected to IB Gateway")
        else:
            self.logger.warning("Client 10 disconnected from IB Gateway")

    @Slot(str)
    def _on_error(self, error: str):
        """Handle error from client"""
        self.logger.error(f"Client 10 error: {error}")
        self.error_occurred.emit(error)

    @Slot()
    def _process_metrics_update(self):
        """Process and format metrics for dashboard display"""
        if not self.current_metrics:
            return

        # Format for dashboard display
        formatted_metrics = self._format_metrics_for_display(self.current_metrics)

        # Emit for dashboard update
        self.all_metrics_updated.emit(formatted_metrics)

    # ==========================================================================
    # FORMATTING
    # ==========================================================================

    def _format_metrics_for_display(self, metrics: dict) -> dict:
        """
        Format metrics for dashboard display with colors and indicators

        Args:
            metrics: Raw metrics dictionary

        Returns:
            Formatted metrics with display properties
        """
        formatted = {}

        for metric_name, data in metrics.items():
            if metric_name not in METRIC_DISPLAY:
                continue

            config = METRIC_DISPLAY[metric_name]
            value = data.get("value", 0)

            # Determine color based on thresholds
            color = COLORS["neutral"]
            if config["thresholds"]:
                thresholds = config["thresholds"]

                if metric_name in ["GEX", "DEX"]:
                    # Negative is bad for these
                    if value >= thresholds["positive"]:
                        color = COLORS["positive"]
                    elif value >= thresholds["warning"]:
                        color = COLORS["warning"]
                    else:
                        color = COLORS["negative"]

                elif metric_name == "DIX":
                    # Higher is better
                    if value >= thresholds["positive"]:
                        color = COLORS["positive"]
                    elif value >= thresholds["warning"]:
                        color = COLORS["neutral"]
                    else:
                        color = COLORS["negative"]

                elif metric_name == "SWAN":
                    # Lower is better
                    if value <= thresholds["positive"]:
                        color = COLORS["positive"]
                    elif value <= thresholds["warning"]:
                        color = COLORS["warning"]
                    else:
                        color = COLORS["negative"]
            else:
                # OGL uses special coloring
                color = COLORS["warning"]

            # Add formatting
            formatted[metric_name] = {
                "value": value,
                "formatted_value": data.get("formatted_value", str(value)),
                "change": data.get("change", 0),
                "change_pct": data.get("change_pct", 0),
                "formatted_change": f"{data.get('change', 0):+.2f}",
                "color": color,
                "tooltip": config["tooltip"],
                "full_name": config["full_name"],
                "timestamp": data.get("timestamp", datetime.now()),
            }

        return formatted

    # ==========================================================================
    # PUBLIC API
    # ==========================================================================

    def get_current_metrics(self) -> dict:
        """Get current formatted metrics"""
        return self._format_metrics_for_display(self.current_metrics)

    def is_connected(self) -> bool:
        """Check if Client 10 is connected"""
        return self.connected

    def force_update(self):
        """Force an immediate metrics update"""
        if self.metrics_client:
            self.metrics_client.force_update()


# ==============================================================================
# DASHBOARD METRICS UPDATER
# ==============================================================================


class DashboardMetricsUpdater(QObject):
    """
    Helper class to update dashboard widgets with custom metrics.
    Bridges between CustomMetricsIntegration and dashboard widgets.
    """

    def __init__(self, dashboard, integration: CustomMetricsIntegration):
        """
        Initialize updater

        Args:
            dashboard: Main dashboard reference
            integration: CustomMetricsIntegration instance
        """
        super().__init__()

        self.dashboard = dashboard
        self.integration = integration

        # Connect to integration signals
        self.integration.all_metrics_updated.connect(self.update_dashboard_widgets)

        # Widget references (will be populated by dashboard)
        self.metric_widgets = {}

    @Slot(dict)
    def update_dashboard_widgets(self, metrics: dict):
        """
        Update dashboard widgets with new metrics

        Args:
            metrics: Formatted metrics dictionary
        """
        try:
            # Update Market Overview panel widgets
            for metric_name, data in metrics.items():
                if metric_name in self.dashboard.symbol_widgets:
                    widget = self.dashboard.symbol_widgets[metric_name]

                    # Update using the widget's update_data method
                    widget.update_data(
                        {
                            "last": data["value"],
                            "change": data["change"],
                            "change_pct": data["change_pct"],
                        }
                    )

            # Update Prometheus table Client 10 status
            if hasattr(self.dashboard, "client_indicators"):
                if "CLIENT 10" in self.dashboard.client_indicators:
                    indicator = self.dashboard.client_indicators["CLIENT 10"]
                    if self.integration.is_connected():
                        indicator.setStyleSheet(f"color: {COLORS['positive']}; font-size: 11px;")
                    else:
                        indicator.setStyleSheet(f"color: {COLORS['warning']}; font-size: 11px;")

            # Log update
            if hasattr(self.dashboard, "logger"):
                self.dashboard.logger.debug(f"Dashboard widgets updated with custom metrics")

        except Exception as e:
            if hasattr(self.dashboard, "logger"):
                self.dashboard.logger.error(f"Error updating dashboard widgets: {e}")


# ==============================================================================
# WIDGET FACTORY
# ==============================================================================


def create_metrics_display_widget() -> QWidget:
    """
    Create a standalone widget for displaying custom metrics

    Returns:
        QWidget containing custom metrics display
    """
    widget = QWidget()
    layout = QVBoxLayout()

    # Title
    title = QLabel("CUSTOM METRICS")
    title.setStyleSheet(f"color: {COLORS['text']}; font-size: 14px; font-weight: bold;")
    layout.addWidget(title)

    # Metrics grid
    metrics_layout = QHBoxLayout()

    for metric_name in ["GEX", "DEX", "OGL", "DIX", "SWAN"]:
        metric_widget = QGroupBox(metric_name)
        metric_widget.setStyleSheet(
            f"""
            QGroupBox {{
                color: {COLORS['text']};
                border: 1px solid {COLORS['text_dim']};
                border-radius: 3px;
                padding: 5px;
            }}
        """
        )

        metric_layout = QVBoxLayout()

        value_label = QLabel("--")
        value_label.setObjectName(f"{metric_name}_value")
        value_label.setStyleSheet(f"color: {COLORS['text']}; font-size: 16px;")

        change_label = QLabel("+0.00")
        change_label.setObjectName(f"{metric_name}_change")
        change_label.setStyleSheet(f"color: {COLORS['neutral']}; font-size: 12px;")

        metric_layout.addWidget(value_label)
        metric_layout.addWidget(change_label)

        metric_widget.setLayout(metric_layout)
        metrics_layout.addWidget(metric_widget)

    layout.addLayout(metrics_layout)
    widget.setLayout(layout)

    return widget


# ==============================================================================
# MODULE EXPORTS
# ==============================================================================
__all__ = [
    "CustomMetricsIntegration",
    "DashboardMetricsUpdater",
    "create_metrics_display_widget",
    "METRIC_DISPLAY",
    "COLORS",
]

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    import sys

    from PySide6.QtWidgets import QApplication, QMainWindow

    app = QApplication(sys.argv)

    # Test window
    window = QMainWindow()
    window.setWindowTitle("Custom Metrics Integration Test")
    window.setGeometry(100, 100, 800, 200)

    # Create and set widget
    metrics_widget = create_metrics_display_widget()
    window.setCentralWidget(metrics_widget)

    # Create integration
    integration = CustomMetricsIntegration()

    # Connect to update widget
    def update_test_widget(metrics):
        for metric_name, data in metrics.items():
            value_label = metrics_widget.findChild(QLabel, f"{metric_name}_value")
            change_label = metrics_widget.findChild(QLabel, f"{metric_name}_change")

            if value_label:
                value_label.setText(data.get("formatted_value", "--"))
            if change_label:
                change_label.setText(f"{data.get('change', 0):+.2f}")

                # Set color based on change
                if data.get("change", 0) >= 0:
                    change_label.setStyleSheet(f"color: {COLORS['positive']}; font-size: 12px;")
                else:
                    change_label.setStyleSheet(f"color: {COLORS['negative']}; font-size: 12px;")

    integration.metrics_updated.connect(update_test_widget)

    # Start integration
    integration.start()

    # Show window
    window.show()

    print("✅ Custom Metrics Integration test running")
    print("The widget should update with simulated metrics every 5 seconds")

    sys.exit(app.exec())
