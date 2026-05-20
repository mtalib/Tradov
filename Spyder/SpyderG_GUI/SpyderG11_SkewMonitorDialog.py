#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderG11_SkewMonitorDialog.py
Group: G (GUI)
Purpose: SKEW Index Monitor Dialog with Detailed Analysis
Author: Mohamed Talib
Date Created: 2025-08-12
Last Updated: 2025-08-12 Time: 16:30:00

Description:
    This module implements a comprehensive SKEW monitoring dialog that provides
    detailed analysis of the CBOE SKEW Index. It displays real-time SKEW values,
    historical charts, regime analysis, and strategy recommendations based on
    tail risk levels. The dialog integrates with the main trading dashboard
    and provides actionable insights for options trading strategies.
"""

# ==============================================================================
# IMPORTS
# ==============================================================================

import logging
# Standard library imports
import sys
from collections import deque
from dataclasses import dataclass
from datetime import datetime, UTC

import numpy as np
from PySide6.QtCore import Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import (QFont)
# PyQt6 imports
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog,
                            QFrame, QGridLayout, QGroupBox, QHBoxLayout,
                            QLabel, QProgressBar, QPushButton,
                            QSpinBox, QTableWidget, QTableWidgetItem, QTabWidget,
                            QTextEdit, QVBoxLayout, QWidget)

# PyQtGraph for charts
try:
    import pyqtgraph as pg

    pg.setConfigOptions(antialias=True)
    PYQTGRAPH_AVAILABLE = True
except ImportError:
    PYQTGRAPH_AVAILABLE = False
    logging.info("Warning: PyQtGraph not available. Charts will be disabled.")

# Internal imports
try:
    from SpyderS_Signals.SpyderS06_SKEWCalculator import (SKEWCalculation,  # noqa: F401
                                                        SKEWComponents,  # noqa: F401
                                                        get_skew_calculator)

    SKEW_CALCULATOR_AVAILABLE = True
except ImportError:
    SKEW_CALCULATOR_AVAILABLE = False
    logging.info("Warning: SKEW Calculator not available. Using mock data.")

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# SKEW Thresholds
SKEW_EXTREME_HIGH = 135  # Extreme put demand (crash fear)
SKEW_HIGH = 125  # High put demand
SKEW_NORMAL_HIGH = 115  # Normal range upper
SKEW_NORMAL_LOW = 105  # Normal range lower
SKEW_LOW = 95  # Low put demand (complacency)

# Historical SKEW Statistics
SKEW_HISTORICAL_MEAN = 118
SKEW_HISTORICAL_STD = 8
SKEW_ALL_TIME_HIGH = 153.66  # October 2018
SKEW_ALL_TIME_LOW = 101.09  # March 2020

# Update Intervals
UPDATE_INTERVAL_FAST = 1000  # 1 second for active trading
UPDATE_INTERVAL_NORMAL = 5000  # 5 seconds normal
UPDATE_INTERVAL_SLOW = 30000  # 30 seconds after hours

# Alert Thresholds
SKEW_ALERT_CHANGE = 3.0  # Alert on 3-point change
SKEW_ALERT_EXTREME = 140  # Alert on extreme levels
SKEW_ALERT_LOW = 100  # Alert on extreme complacency

# Chart Settings
CHART_HISTORY_DAYS = 30
CHART_INTRADAY_PERIODS = 78  # 5-minute bars in trading day
CHART_UPDATE_INTERVAL = 60000  # Update charts every minute

# ==============================================================================
# LOGGER SETUP
# ==============================================================================

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# ==============================================================================
# DATA CLASSES
# ==============================================================================


@dataclass
class SkewData:
    """Container for SKEW display data"""

    value: float
    timestamp: datetime
    change_1d: float = 0.0
    change_5d: float = 0.0
    change_20d: float = 0.0
    percentile: float = 50.0
    z_score: float = 0.0
    vix_correlation: float = 0.0
    spy_correlation: float = 0.0
    gex_correlation: float = 0.0
    regime: str = "NORMAL"
    signal: str = "NEUTRAL"
    confidence: float = 0.0


@dataclass
class SkewAlert:
    """SKEW alert information"""

    level: str  # "INFO", "WARNING", "CRITICAL"
    message: str
    timestamp: datetime
    value: float
    action: str | None = None


# ==============================================================================
# SKEW DATA THREAD
# ==============================================================================


class SkewDataThread(QThread):
    """Background thread for fetching SKEW data"""

    data_updated = Signal(SkewData)
    error_occurred = Signal(str)

    def __init__(self):
        super().__init__()
        self.running = True
        self.update_interval = UPDATE_INTERVAL_NORMAL

    def run(self):
        """Main thread loop"""
        while self.running:
            try:
                # Fetch SKEW data
                data = self.fetch_skew_data()
                if data:
                    self.data_updated.emit(data)
            except Exception as e:
                self.error_occurred.emit(str(e))

            # Sleep for update interval
            self.msleep(self.update_interval)

    def fetch_skew_data(self) -> SkewData | None:
        """Fetch latest SKEW data"""
        try:
            if SKEW_CALCULATOR_AVAILABLE:
                calculator = get_skew_calculator()

                # Get latest calculation
                calc = calculator.get_last_calculation()
                if not calc:
                    # Trigger new calculation
                    calc = calculator.calculate_skew()

                if calc:
                    # Get statistics
                    stats = calculator.get_statistics()

                    # Create SkewData
                    return SkewData(
                        value=calc.skew_index,
                        timestamp=calc.timestamp,
                        change_1d=self.calculate_change(calculator, 1),
                        change_5d=self.calculate_change(calculator, 5),
                        change_20d=self.calculate_change(calculator, 20),
                        percentile=stats.get("percentile", 50),
                        z_score=stats.get("z_score", 0),
                        regime=self.determine_regime(calc.skew_index),
                        signal=self.determine_signal(calc.skew_index),
                        confidence=calc.confidence,
                    )
            else:
                # Mock data for testing
                import random

                value = SKEW_HISTORICAL_MEAN + random.gauss(0, SKEW_HISTORICAL_STD)
                return SkewData(
                    value=value,
                    timestamp=datetime.now(UTC),
                    change_1d=random.uniform(-3, 3),
                    change_5d=random.uniform(-5, 5),
                    change_20d=random.uniform(-10, 10),
                    percentile=50 + random.gauss(0, 20),
                    z_score=(value - SKEW_HISTORICAL_MEAN) / SKEW_HISTORICAL_STD,
                    regime=self.determine_regime(value),
                    signal=self.determine_signal(value),
                    confidence=0.8 + random.random() * 0.2,
                )
        except Exception as e:
            logger.error("Error fetching SKEW data: %s", e)
            return None

    def calculate_change(self, calculator, days: int) -> float:
        """Calculate change over specified days"""
        try:
            history = calculator.get_history(days * 78)  # Approximate intraday periods
            if len(history) >= 2:
                old_value = history[0].skew_index
                new_value = history[-1].skew_index
                return new_value - old_value
            return 0.0
        except Exception:
            return 0.0

    def determine_regime(self, skew_value: float) -> str:
        """Determine market regime based on SKEW"""
        if skew_value >= SKEW_EXTREME_HIGH:
            return "EXTREME_FEAR"
        elif skew_value >= SKEW_HIGH:
            return "HIGH_FEAR"
        elif skew_value >= SKEW_NORMAL_HIGH:
            return "ELEVATED_CAUTION"
        elif skew_value >= SKEW_NORMAL_LOW:
            return "NORMAL"
        else:
            return "COMPLACENCY"

    def determine_signal(self, skew_value: float) -> str:
        """Determine trading signal based on SKEW"""
        if skew_value >= SKEW_EXTREME_HIGH:
            return "SELL_PUTS"
        elif skew_value >= SKEW_HIGH:
            return "NEUTRAL_CAUTIOUS"
        elif skew_value <= SKEW_LOW:
            return "BUY_PROTECTION"
        else:
            return "NEUTRAL"

    def stop(self):
        """Stop the thread"""
        self.running = False


# ==============================================================================
# MAIN SKEW MONITOR DIALOG
# ==============================================================================


class SkewMonitorDialog(QDialog):
    """
    Comprehensive SKEW monitoring dialog with charts and analysis.
    """

    # Signals
    alert_triggered = Signal(SkewAlert)
    strategy_updated = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)

        # Window setup
        self.setWindowTitle("SKEW Index Monitor - Tail Risk Dashboard")
        self.setMinimumSize(1000, 700)
        self.resize(1200, 800)

        # Data management
        self.current_skew_data = None
        self.skew_history = deque(maxlen=CHART_INTRADAY_PERIODS * CHART_HISTORY_DAYS)
        self.alert_history = deque(maxlen=50)

        # Threads and timers
        self.data_thread = SkewDataThread()
        self.chart_timer = QTimer()

        # Setup UI
        self.setup_ui()
        self.setup_connections()
        self.apply_theme()

        # Start data collection
        self.start_monitoring()

        logger.info("SKEW Monitor Dialog initialized")

    # ==========================================================================
    # UI SETUP METHODS
    # ==========================================================================

    def setup_ui(self):
        """Setup the main UI layout"""
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # Create tab widget for organized display
        self.tab_widget = QTabWidget()

        # Tab 1: Overview
        self.overview_tab = self.create_overview_tab()
        self.tab_widget.addTab(self.overview_tab, "Overview")

        # Tab 2: Charts
        self.charts_tab = self.create_charts_tab()
        self.tab_widget.addTab(self.charts_tab, "Charts")

        # Tab 3: Strategies
        self.strategies_tab = self.create_strategies_tab()
        self.tab_widget.addTab(self.strategies_tab, "Strategies")

        # Tab 4: Analysis
        self.analysis_tab = self.create_analysis_tab()
        self.tab_widget.addTab(self.analysis_tab, "Analysis")

        # Tab 5: Settings
        self.settings_tab = self.create_settings_tab()
        self.tab_widget.addTab(self.settings_tab, "Settings")

        layout.addWidget(self.tab_widget)

        # Bottom status bar
        self.status_bar = self.create_status_bar()
        layout.addWidget(self.status_bar)

        self.setLayout(layout)

    def create_overview_tab(self) -> QWidget:
        """Create overview tab with main SKEW display"""
        widget = QWidget()
        layout = QVBoxLayout()

        # Top section - Current SKEW
        top_section = QHBoxLayout()

        # SKEW Value Display
        skew_group = QGroupBox("Current SKEW")
        skew_layout = QVBoxLayout()

        self.skew_value_label = QLabel("---.--")
        self.skew_value_label.setAlignment(Qt.AlignCenter)
        font = QFont("Arial", 36)
        self.skew_value_label.setFont(font)

        self.skew_timestamp_label = QLabel("Last Update: --:--:--")
        self.skew_timestamp_label.setAlignment(Qt.AlignCenter)

        skew_layout.addWidget(self.skew_value_label)
        skew_layout.addWidget(self.skew_timestamp_label)
        skew_group.setLayout(skew_layout)
        top_section.addWidget(skew_group)

        # Changes Display
        changes_group = QGroupBox("Changes")
        changes_layout = QGridLayout()

        self.change_1d_label = QLabel("1D: --.-%")
        self.change_5d_label = QLabel("5D: --.-%")
        self.change_20d_label = QLabel("20D: --.-%")

        changes_layout.addWidget(QLabel("1 Day:"), 0, 0)
        changes_layout.addWidget(self.change_1d_label, 0, 1)
        changes_layout.addWidget(QLabel("5 Days:"), 1, 0)
        changes_layout.addWidget(self.change_5d_label, 1, 1)
        changes_layout.addWidget(QLabel("20 Days:"), 2, 0)
        changes_layout.addWidget(self.change_20d_label, 2, 1)

        changes_group.setLayout(changes_layout)
        top_section.addWidget(changes_group)

        # Statistics Display
        stats_group = QGroupBox("Statistics")
        stats_layout = QGridLayout()

        self.percentile_label = QLabel("Percentile: --%")
        self.z_score_label = QLabel("Z-Score: -.-")
        self.confidence_label = QLabel("Confidence: --%")

        self.percentile_bar = QProgressBar()
        self.percentile_bar.setRange(0, 100)
        self.percentile_bar.setTextVisible(True)

        stats_layout.addWidget(QLabel("Percentile:"), 0, 0)
        stats_layout.addWidget(self.percentile_bar, 0, 1)
        stats_layout.addWidget(QLabel("Z-Score:"), 1, 0)
        stats_layout.addWidget(self.z_score_label, 1, 1)
        stats_layout.addWidget(QLabel("Confidence:"), 2, 0)
        stats_layout.addWidget(self.confidence_label, 2, 1)

        stats_group.setLayout(stats_layout)
        top_section.addWidget(stats_group)

        layout.addLayout(top_section)

        # Middle section - Regime and Signal
        middle_section = QHBoxLayout()

        # Regime Display
        regime_group = QGroupBox("Market Regime")
        regime_layout = QVBoxLayout()

        self.regime_label = QLabel("ANALYZING...")
        self.regime_label.setAlignment(Qt.AlignCenter)
        regime_font = QFont("Arial", 16)
        self.regime_label.setFont(regime_font)

        self.regime_description = QTextEdit()
        self.regime_description.setReadOnly(True)
        self.regime_description.setMaximumHeight(60)

        regime_layout.addWidget(self.regime_label)
        regime_layout.addWidget(self.regime_description)
        regime_group.setLayout(regime_layout)
        middle_section.addWidget(regime_group)

        # Signal Display
        signal_group = QGroupBox("Trading Signal")
        signal_layout = QVBoxLayout()

        self.signal_label = QLabel("NEUTRAL")
        self.signal_label.setAlignment(Qt.AlignCenter)
        signal_font = QFont("Arial", 16)
        self.signal_label.setFont(signal_font)

        self.signal_description = QTextEdit()
        self.signal_description.setReadOnly(True)
        self.signal_description.setMaximumHeight(60)

        signal_layout.addWidget(self.signal_label)
        signal_layout.addWidget(self.signal_description)
        signal_group.setLayout(signal_layout)
        middle_section.addWidget(signal_group)

        layout.addLayout(middle_section)

        # Bottom section - Correlations and Alerts
        bottom_section = QHBoxLayout()

        # Correlations
        corr_group = QGroupBox("Correlations")
        corr_layout = QGridLayout()

        self.vix_corr_label = QLabel("VIX: -.--%")
        self.spy_corr_label = QLabel("SPY: -.--%")
        self.gex_corr_label = QLabel("GEX: -.--%")

        corr_layout.addWidget(QLabel("VIX:"), 0, 0)
        corr_layout.addWidget(self.vix_corr_label, 0, 1)
        corr_layout.addWidget(QLabel("SPY:"), 1, 0)
        corr_layout.addWidget(self.spy_corr_label, 1, 1)
        corr_layout.addWidget(QLabel("GEX:"), 2, 0)
        corr_layout.addWidget(self.gex_corr_label, 2, 1)

        corr_group.setLayout(corr_layout)
        bottom_section.addWidget(corr_group)

        # Recent Alerts
        alerts_group = QGroupBox("Recent Alerts")
        alerts_layout = QVBoxLayout()

        self.alerts_list = QTextEdit()
        self.alerts_list.setReadOnly(True)
        self.alerts_list.setMaximumHeight(100)

        alerts_layout.addWidget(self.alerts_list)
        alerts_group.setLayout(alerts_layout)
        bottom_section.addWidget(alerts_group)

        layout.addLayout(bottom_section)

        widget.setLayout(layout)
        return widget

    def create_charts_tab(self) -> QWidget:
        """Create charts tab with SKEW visualizations"""
        widget = QWidget()
        layout = QVBoxLayout()

        if PYQTGRAPH_AVAILABLE:
            # Time series chart
            self.skew_chart = pg.PlotWidget(title="SKEW Index Time Series")
            self.skew_chart.setLabel("left", "SKEW Index")
            self.skew_chart.setLabel("bottom", "Time")
            self.skew_chart.showGrid(x=True, y=True, alpha=0.3)
            self.skew_chart.setMinimumHeight(300)

            # Add reference lines
            self.skew_chart.addLine(
                y=SKEW_EXTREME_HIGH, pen=pg.mkPen("r", width=1, style=Qt.PenStyle.DashLine)
            )
            self.skew_chart.addLine(
                y=SKEW_HIGH, pen=pg.mkPen("orange", width=1, style=Qt.PenStyle.DashLine)
            )
            self.skew_chart.addLine(y=SKEW_HISTORICAL_MEAN, pen=pg.mkPen("yellow", width=2))
            self.skew_chart.addLine(
                y=SKEW_LOW, pen=pg.mkPen("g", width=1, style=Qt.PenStyle.DashLine)
            )

            # Initialize plot data
            self.skew_plot = self.skew_chart.plot([], [], pen="w", symbol="o", symbolSize=5)

            layout.addWidget(self.skew_chart)

            # Distribution histogram
            self.hist_chart = pg.PlotWidget(title="SKEW Distribution (30 Days)")
            self.hist_chart.setLabel("left", "Frequency")
            self.hist_chart.setLabel("bottom", "SKEW Value")
            self.hist_chart.showGrid(x=True, y=True, alpha=0.3)
            self.hist_chart.setMinimumHeight(200)

            layout.addWidget(self.hist_chart)
        else:
            # Fallback if PyQtGraph not available
            no_chart_label = QLabel("Charts require PyQtGraph installation")
            no_chart_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(no_chart_label)

        widget.setLayout(layout)
        return widget

    def create_strategies_tab(self) -> QWidget:
        """Create strategies tab with recommendations"""
        widget = QWidget()
        layout = QVBoxLayout()

        # Strategy recommendations table
        strategies_group = QGroupBox("Recommended Options Strategies")
        strategies_layout = QVBoxLayout()

        self.strategies_table = QTableWidget(5, 4)
        self.strategies_table.setHorizontalHeaderLabels(
            ["Strategy", "Rating", "Risk/Reward", "Reason"]
        )
        self.strategies_table.horizontalHeader().setStretchLastSection(True)
        self.strategies_table.setMinimumHeight(200)

        strategies_layout.addWidget(self.strategies_table)
        strategies_group.setLayout(strategies_layout)
        layout.addWidget(strategies_group)

        # Position sizing recommendations
        sizing_group = QGroupBox("Position Sizing")
        sizing_layout = QGridLayout()

        self.position_size_label = QLabel("Recommended Size: Normal")
        self.max_risk_label = QLabel("Max Risk per Trade: 2%")
        self.kelly_criterion_label = QLabel("Kelly Criterion: 15%")

        sizing_layout.addWidget(QLabel("Position Size:"), 0, 0)
        sizing_layout.addWidget(self.position_size_label, 0, 1)
        sizing_layout.addWidget(QLabel("Max Risk:"), 1, 0)
        sizing_layout.addWidget(self.max_risk_label, 1, 1)
        sizing_layout.addWidget(QLabel("Kelly Criterion:"), 2, 0)
        sizing_layout.addWidget(self.kelly_criterion_label, 2, 1)

        sizing_group.setLayout(sizing_layout)
        layout.addWidget(sizing_group)

        # Risk parameters
        risk_group = QGroupBox("Risk Adjustments")
        risk_layout = QVBoxLayout()

        self.risk_text = QTextEdit()
        self.risk_text.setReadOnly(True)
        self.risk_text.setMaximumHeight(100)

        risk_layout.addWidget(self.risk_text)
        risk_group.setLayout(risk_layout)
        layout.addWidget(risk_group)

        # Action items
        actions_group = QGroupBox("Recommended Actions")
        actions_layout = QVBoxLayout()

        self.actions_text = QTextEdit()
        self.actions_text.setReadOnly(True)
        self.actions_text.setMaximumHeight(100)

        actions_layout.addWidget(self.actions_text)
        actions_group.setLayout(actions_layout)
        layout.addWidget(actions_group)

        widget.setLayout(layout)
        return widget

    def create_analysis_tab(self) -> QWidget:
        """Create analysis tab with detailed metrics"""
        widget = QWidget()
        layout = QVBoxLayout()

        # Historical analysis
        hist_group = QGroupBox("Historical Analysis")
        hist_layout = QGridLayout()

        self.mean_label = QLabel(f"Historical Mean: {SKEW_HISTORICAL_MEAN}")
        self.std_label = QLabel(f"Historical Std Dev: {SKEW_HISTORICAL_STD}")
        self.high_label = QLabel(f"All-Time High: {SKEW_ALL_TIME_HIGH}")
        self.low_label = QLabel(f"All-Time Low: {SKEW_ALL_TIME_LOW}")

        hist_layout.addWidget(self.mean_label, 0, 0)
        hist_layout.addWidget(self.std_label, 0, 1)
        hist_layout.addWidget(self.high_label, 1, 0)
        hist_layout.addWidget(self.low_label, 1, 1)

        hist_group.setLayout(hist_layout)
        layout.addWidget(hist_group)

        # Component breakdown
        components_group = QGroupBox("SKEW Components")
        components_layout = QVBoxLayout()

        self.components_text = QTextEdit()
        self.components_text.setReadOnly(True)
        self.components_text.setMaximumHeight(150)

        components_layout.addWidget(self.components_text)
        components_group.setLayout(components_layout)
        layout.addWidget(components_group)

        # Market interpretation
        interp_group = QGroupBox("Market Interpretation")
        interp_layout = QVBoxLayout()

        self.interpretation_text = QTextEdit()
        self.interpretation_text.setReadOnly(True)

        interp_layout.addWidget(self.interpretation_text)
        interp_group.setLayout(interp_layout)
        layout.addWidget(interp_group)

        widget.setLayout(layout)
        return widget

    def create_settings_tab(self) -> QWidget:
        """Create settings tab for configuration"""
        widget = QWidget()
        layout = QVBoxLayout()

        # Update settings
        update_group = QGroupBox("Update Settings")
        update_layout = QGridLayout()

        self.update_interval_combo = QComboBox()
        self.update_interval_combo.addItems(["Fast (1s)", "Normal (5s)", "Slow (30s)"])
        self.update_interval_combo.setCurrentIndex(1)

        self.auto_update_check = QCheckBox("Auto Update")
        self.auto_update_check.setChecked(True)

        update_layout.addWidget(QLabel("Update Interval:"), 0, 0)
        update_layout.addWidget(self.update_interval_combo, 0, 1)
        update_layout.addWidget(self.auto_update_check, 1, 0, 1, 2)

        update_group.setLayout(update_layout)
        layout.addWidget(update_group)

        # Alert settings
        alert_group = QGroupBox("Alert Settings")
        alert_layout = QGridLayout()

        self.alert_extreme_spin = QSpinBox()
        self.alert_extreme_spin.setRange(130, 150)
        self.alert_extreme_spin.setValue(SKEW_ALERT_EXTREME)

        self.alert_low_spin = QSpinBox()
        self.alert_low_spin.setRange(95, 110)
        self.alert_low_spin.setValue(SKEW_ALERT_LOW)

        self.alert_change_spin = QSpinBox()
        self.alert_change_spin.setRange(1, 10)
        self.alert_change_spin.setValue(int(SKEW_ALERT_CHANGE))

        self.alert_enabled_check = QCheckBox("Enable Alerts")
        self.alert_enabled_check.setChecked(True)

        alert_layout.addWidget(QLabel("Extreme High:"), 0, 0)
        alert_layout.addWidget(self.alert_extreme_spin, 0, 1)
        alert_layout.addWidget(QLabel("Extreme Low:"), 1, 0)
        alert_layout.addWidget(self.alert_low_spin, 1, 1)
        alert_layout.addWidget(QLabel("Rapid Change:"), 2, 0)
        alert_layout.addWidget(self.alert_change_spin, 2, 1)
        alert_layout.addWidget(self.alert_enabled_check, 3, 0, 1, 2)

        alert_group.setLayout(alert_layout)
        layout.addWidget(alert_group)

        # Display settings
        display_group = QGroupBox("Display Settings")
        display_layout = QGridLayout()

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark", "Light", "Auto"])

        self.chart_periods_spin = QSpinBox()
        self.chart_periods_spin.setRange(10, 100)
        self.chart_periods_spin.setValue(CHART_HISTORY_DAYS)

        display_layout.addWidget(QLabel("Theme:"), 0, 0)
        display_layout.addWidget(self.theme_combo, 0, 1)
        display_layout.addWidget(QLabel("Chart Days:"), 1, 0)
        display_layout.addWidget(self.chart_periods_spin, 1, 1)

        display_group.setLayout(display_layout)
        layout.addWidget(display_group)

        # Apply button
        self.apply_settings_btn = QPushButton("Apply Settings")
        self.apply_settings_btn.clicked.connect(self.apply_settings)
        layout.addWidget(self.apply_settings_btn)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_status_bar(self) -> QWidget:
        """Create status bar at bottom"""
        widget = QFrame()
        widget.setFrameStyle(QFrame.Shape.Box)
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)

        # Connection status
        self.connection_label = QLabel("● Connected")
        self.connection_label.setStyleSheet("color: green;")
        layout.addWidget(self.connection_label)

        layout.addStretch()

        # Last update time
        self.last_update_label = QLabel("Last Update: --:--:--")
        layout.addWidget(self.last_update_label)

        layout.addStretch()

        # Data source
        self.source_label = QLabel("Source: CBOE")
        layout.addWidget(self.source_label)

        widget.setLayout(layout)
        return widget

    # ==========================================================================
    # CONNECTION SETUP
    # ==========================================================================

    def setup_connections(self):
        """Setup signal/slot connections"""
        # Data thread connections
        self.data_thread.data_updated.connect(self.on_data_updated)
        self.data_thread.error_occurred.connect(self.on_error)

        # Chart timer
        self.chart_timer.timeout.connect(self.update_charts)

        # Settings connections
        self.update_interval_combo.currentIndexChanged.connect(self.on_update_interval_changed)
        self.auto_update_check.toggled.connect(self.on_auto_update_toggled)

    # ==========================================================================
    # DATA UPDATE METHODS
    # ==========================================================================

    @Slot(SkewData)
    def on_data_updated(self, data: SkewData):
        """Handle new SKEW data"""
        self.current_skew_data = data
        self.skew_history.append(data)

        # Update displays
        self.update_overview_display(data)
        self.update_strategies_display(data)
        self.update_analysis_display(data)

        # Check for alerts
        self.check_alerts(data)

        # Update last update time
        self.last_update_label.setText(f"Last Update: {datetime.now(UTC).strftime('%H:%M:%S')}")

    def update_overview_display(self, data: SkewData):
        """Update overview tab display"""
        # Update SKEW value
        self.skew_value_label.setText(f"{data.value:.2f}")
        self.skew_value_label.setStyleSheet(f"color: {self.get_skew_color(data.value)};")

        # Update timestamp
        self.skew_timestamp_label.setText(f"Last Update: {data.timestamp.strftime('%H:%M:%S')}")

        # Update changes
        self.update_change_label(self.change_1d_label, data.change_1d, "1D")
        self.update_change_label(self.change_5d_label, data.change_5d, "5D")
        self.update_change_label(self.change_20d_label, data.change_20d, "20D")

        # Update statistics
        self.percentile_bar.setValue(int(data.percentile))
        self.z_score_label.setText(f"Z-Score: {data.z_score:.2f}")
        self.confidence_label.setText(f"Confidence: {data.confidence:.1%}")

        # Update regime
        self.regime_label.setText(data.regime.replace("_", " "))
        self.regime_label.setStyleSheet(
            f"background-color: {self.get_regime_color(data.regime)}; color: white; padding: 5px; border-radius: 3px;"  # noqa: E501
        )
        self.regime_description.setText(self.get_regime_description(data.regime))

        # Update signal
        self.signal_label.setText(data.signal.replace("_", " "))
        self.signal_label.setStyleSheet(
            f"background-color: {self.get_signal_color(data.signal)}; color: white; padding: 5px; border-radius: 3px;"  # noqa: E501
        )
        self.signal_description.setText(self.get_signal_description(data.signal))

        # Update correlations (mock data for now)
        self.vix_corr_label.setText(f"VIX: {data.vix_correlation:.1%}")
        self.spy_corr_label.setText(f"SPY: {data.spy_correlation:.1%}")
        self.gex_corr_label.setText(f"GEX: {data.gex_correlation:.1%}")

    def update_strategies_display(self, data: SkewData):
        """Update strategies tab display"""
        # Clear table
        self.strategies_table.clearContents()

        # Get strategies based on SKEW
        strategies = self.get_strategy_recommendations(data.value)

        # Populate table
        for i, strategy in enumerate(strategies[:5]):
            self.strategies_table.setItem(i, 0, QTableWidgetItem(strategy["name"]))
            self.strategies_table.setItem(i, 1, QTableWidgetItem(strategy["rating"]))
            self.strategies_table.setItem(i, 2, QTableWidgetItem(strategy["risk_reward"]))
            self.strategies_table.setItem(i, 3, QTableWidgetItem(strategy["reason"]))

        # Update position sizing
        position_size = self.get_position_sizing(data.value)
        self.position_size_label.setText(f"Recommended Size: {position_size}")

        max_risk = self.get_max_risk(data.value)
        self.max_risk_label.setText(f"Max Risk per Trade: {max_risk}")

        # Update risk text
        risk_text = self.get_risk_adjustments(data)
        self.risk_text.setText(risk_text)

        # Update actions
        actions = self.get_action_items(data)
        self.actions_text.setText("\n".join(actions))

    def update_analysis_display(self, data: SkewData):
        """Update analysis tab display"""
        # Update components if available
        if SKEW_CALCULATOR_AVAILABLE:
            calculator = get_skew_calculator()
            components = calculator.get_components()
            if components:
                comp_text = f"Forward Price: ${components.forward:.2f}\n"
                comp_text += f"ATM Volatility: {components.atm_volatility:.2%}\n"
                comp_text += f"Risk-Neutral Skew: {components.risk_neutral_skew:.4f}\n"
                comp_text += f"Risk-Neutral Kurtosis: {components.risk_neutral_kurtosis:.4f}\n"
                comp_text += f"Interpolation Quality: {components.interpolation_quality:.2%}"
                self.components_text.setText(comp_text)

        # Update interpretation
        interpretation = self.get_market_interpretation(data)
        self.interpretation_text.setText(interpretation)

    def update_charts(self):
        """Update chart displays"""
        if not PYQTGRAPH_AVAILABLE or not self.skew_history:
            return

        try:
            # Prepare data
            times = [d.timestamp.timestamp() for d in self.skew_history]
            values = [d.value for d in self.skew_history]

            # Update time series
            self.skew_plot.setData(times, values)

            # Update histogram
            if len(values) > 10:
                hist, bins = np.histogram(values, bins=20)
                self.hist_chart.clear()
                self.hist_chart.plot(bins, hist, stepMode=True, fillLevel=0, brush="y")

        except Exception as e:
            logger.error("Error updating charts: %s", e)

    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================

    def get_skew_color(self, value: float) -> str:
        """Get color for SKEW value"""
        if value >= SKEW_EXTREME_HIGH:
            return "#8B0000"  # Dark Red
        elif value >= SKEW_HIGH:
            return "#FF4500"  # Orange Red
        elif value >= SKEW_NORMAL_HIGH:
            return "#FFD700"  # Gold
        elif value >= SKEW_NORMAL_LOW:
            return "#90EE90"  # Light Green
        else:
            return "#00FF00"  # Bright Green

    def get_regime_color(self, regime: str) -> str:
        """Get color for regime"""
        colors = {
            "EXTREME_FEAR": "#8B0000",
            "HIGH_FEAR": "#FF4500",
            "ELEVATED_CAUTION": "#FFD700",
            "NORMAL": "#4169E1",
            "COMPLACENCY": "#00FF00",
        }
        return colors.get(regime, "#808080")

    def get_signal_color(self, signal: str) -> str:
        """Get color for signal"""
        colors = {
            "SELL_PUTS": "#00FF00",
            "NEUTRAL_CAUTIOUS": "#FFD700",
            "NEUTRAL": "#4169E1",
            "BUY_PROTECTION": "#FF4500",
        }
        return colors.get(signal, "#808080")

    def update_change_label(self, label: QLabel, change: float, period: str):
        """Update change label with color"""
        symbol = "↑" if change > 0 else "↓" if change < 0 else "→"
        color = "green" if change > 0 else "red" if change < 0 else "gray"
        label.setText(f"{period}: {change:+.1f}% {symbol}")
        label.setStyleSheet(f"color: {color};")

    def get_regime_description(self, regime: str) -> str:
        """Get description for regime"""
        descriptions = {
            "EXTREME_FEAR": "Market pricing extreme tail risk. Put skew at historical highs.",
            "HIGH_FEAR": "Elevated put demand. Market hedging aggressively.",
            "ELEVATED_CAUTION": "Above-normal tail risk pricing. Some concern present.",
            "NORMAL": "Typical risk pricing. Balanced put/call demand.",
            "COMPLACENCY": "Low tail risk pricing. Opportunity for cheap hedges.",
        }
        return descriptions.get(regime, "")

    def get_signal_description(self, signal: str) -> str:
        """Get description for signal"""
        descriptions = {
            "SELL_PUTS": "Put premiums expensive. Consider selling put spreads.",
            "NEUTRAL_CAUTIOUS": "Elevated risk. Maintain balanced approach.",
            "NEUTRAL": "No strong directional bias. Standard strategies.",
            "BUY_PROTECTION": "Cheap protection available. Consider protective puts.",
        }
        return descriptions.get(signal, "")

    def get_strategy_recommendations(self, skew_value: float) -> list[dict]:
        """Get strategy recommendations based on SKEW"""
        if skew_value >= SKEW_EXTREME_HIGH:
            return [
                {
                    "name": "Sell Put Spreads",
                    "rating": "★★★★★",
                    "risk_reward": "High/High",
                    "reason": "Expensive put premiums",
                },
                {
                    "name": "Buy Call Spreads",
                    "rating": "★★★★",
                    "risk_reward": "Med/High",
                    "reason": "Relatively cheap calls",
                },
                {
                    "name": "Jade Lizard",
                    "rating": "★★★",
                    "risk_reward": "Med/Med",
                    "reason": "Collect high put premium",
                },
                {
                    "name": "Iron Condor",
                    "rating": "★★",
                    "risk_reward": "Low/Med",
                    "reason": "High put skew risk",
                },
                {
                    "name": "Long Straddle",
                    "rating": "★",
                    "risk_reward": "High/Low",
                    "reason": "Expensive volatility",
                },
            ]
        elif skew_value <= SKEW_LOW:
            return [
                {
                    "name": "Buy Protective Puts",
                    "rating": "★★★★★",
                    "risk_reward": "Low/High",
                    "reason": "Cheap tail protection",
                },
                {
                    "name": "Long Volatility",
                    "rating": "★★★★",
                    "risk_reward": "Med/High",
                    "reason": "Low risk pricing",
                },
                {
                    "name": "Put Backspread",
                    "rating": "★★★",
                    "risk_reward": "Low/High",
                    "reason": "Cheap downside exposure",
                },
                {
                    "name": "Calendar Spreads",
                    "rating": "★★★",
                    "risk_reward": "Low/Med",
                    "reason": "Vol expansion likely",
                },
                {
                    "name": "Naked Puts",
                    "rating": "★",
                    "risk_reward": "High/Low",
                    "reason": "Complacency risk",
                },
            ]
        else:
            return [
                {
                    "name": "Iron Condor",
                    "rating": "★★★★",
                    "risk_reward": "Med/Med",
                    "reason": "Balanced risk/reward",
                },
                {
                    "name": "Calendar Spreads",
                    "rating": "★★★",
                    "risk_reward": "Low/Med",
                    "reason": "Normal volatility",
                },
                {
                    "name": "Credit Spreads",
                    "rating": "★★★",
                    "risk_reward": "Med/Med",
                    "reason": "Standard premium",
                },
                {
                    "name": "Butterfly",
                    "rating": "★★★",
                    "risk_reward": "Low/High",
                    "reason": "Range-bound market",
                },
                {
                    "name": "Diagonal Spreads",
                    "rating": "★★",
                    "risk_reward": "Med/Med",
                    "reason": "Time decay play",
                },
            ]

    def get_position_sizing(self, skew: float) -> str:
        """Get position sizing recommendation"""
        if skew >= SKEW_EXTREME_HIGH:
            return "Reduce to 50% normal"
        elif skew >= SKEW_HIGH:
            return "Reduce to 75% normal"
        elif skew <= SKEW_LOW:
            return "Can increase to 125%"
        else:
            return "Normal sizing (100%)"

    def get_max_risk(self, skew: float) -> str:
        """Get max risk recommendation"""
        if skew >= SKEW_EXTREME_HIGH:
            return "1% per trade"
        elif skew >= SKEW_HIGH:
            return "1.5% per trade"
        elif skew <= SKEW_LOW:
            return "2.5% per trade"
        else:
            return "2% per trade"

    def get_risk_adjustments(self, data: SkewData) -> str:
        """Get risk adjustment text"""
        adjustments = []

        if data.value >= SKEW_HIGH:
            adjustments.append("• Reduce position sizes by 25-50%")
            adjustments.append("• Tighten stop losses to 1-2%")
            adjustments.append("• Avoid naked short puts")
            adjustments.append("• Consider portfolio hedges")
        elif data.value <= SKEW_LOW:
            adjustments.append("• Opportunity for larger positions")
            adjustments.append("• Consider buying cheap protection")
            adjustments.append("• Review bullish exposure")
        else:
            adjustments.append("• Maintain normal position sizing")
            adjustments.append("• Standard stop loss levels (2-3%)")
            adjustments.append("• Balanced portfolio approach")

        return "\n".join(adjustments)

    def get_action_items(self, data: SkewData) -> list[str]:
        """Get action items based on SKEW"""
        actions = []

        if data.value >= SKEW_EXTREME_HIGH:
            actions.append("⚠️ Review all short put positions immediately")
            actions.append("🛡️ Consider buying protective puts")
            actions.append("📉 Reduce leverage and overall exposure")
            actions.append("💰 Take profits on winning positions")
        elif data.value >= SKEW_HIGH:
            actions.append("👀 Monitor put positions closely")
            actions.append("🔄 Prepare hedge adjustments")
            actions.append("📊 Review risk limits")
        elif data.value <= SKEW_LOW:
            actions.append("✅ Opportunity to buy cheap protection")
            actions.append("📈 Review bullish positions")
            actions.append("🎯 Consider tail risk hedges")
        else:
            actions.append("➡️ Maintain current strategy")
            actions.append("📊 Monitor for regime changes")
            actions.append("✓ Standard risk management")

        return actions

    def get_market_interpretation(self, data: SkewData) -> str:
        """Get detailed market interpretation"""
        interp = f"SKEW Index at {data.value:.2f} ({data.percentile:.0f} percentile)\n\n"

        if data.value >= SKEW_EXTREME_HIGH:
            interp += "EXTREME TAIL RISK PRICING\n"
            interp += "The market is pricing in significant downside risk. "
            interp += "Institutional investors are aggressively hedging portfolios. "
            interp += "This often occurs before major events or during heightened uncertainty. "
            interp += "While crashes rarely materialize, the cost of protection is very high.\n\n"
            interp += "Historical Context: Similar levels seen before Brexit, 2018 Q4 selloff.\n\n"
            interp += "Implications: Expensive to hedge, opportunities in selling volatility to sophisticated buyers."  # noqa: E501

        elif data.value >= SKEW_HIGH:
            interp += "ELEVATED TAIL RISK CONCERN\n"
            interp += "Above-normal demand for downside protection. "
            interp += "Market participants are cautious but not panicking. "
            interp += "Often seen during earnings seasons or ahead of Fed decisions.\n\n"
            interp += (
                "Implications: Moderate hedging costs, balanced risk/reward in premium selling."
            )

        elif data.value <= SKEW_LOW:
            interp += "MARKET COMPLACENCY\n"
            interp += "Very low tail risk pricing suggests market complacency. "
            interp += (
                "Investors are not hedging aggressively, possibly due to recent calm periods. "
            )
            interp += "This creates opportunities for cheap portfolio protection.\n\n"
            interp += "Historical Context: Often seen during extended bull runs.\n\n"
            interp += "Warning: Complacency can precede volatility expansions."

        else:
            interp += "NORMAL RISK PRICING\n"
            interp += "Balanced supply and demand for options protection. "
            interp += "No extreme positioning in either direction. "
            interp += "Standard option strategies should perform as expected.\n\n"
            interp += "Implications: Focus on directional views and volatility assessment."

        return interp

    def check_alerts(self, data: SkewData):
        """Check for alert conditions"""
        if not self.alert_enabled_check.isChecked():
            return

        alerts = []

        # Check extreme levels
        if data.value >= self.alert_extreme_spin.value():
            alert = SkewAlert(
                level="CRITICAL",
                message=f"SKEW at extreme high: {data.value:.1f}",
                timestamp=datetime.now(UTC),
                value=data.value,
                action="Review risk exposure immediately",
            )
            alerts.append(alert)

        elif data.value <= self.alert_low_spin.value():
            alert = SkewAlert(
                level="WARNING",
                message=f"SKEW at extreme low: {data.value:.1f}",
                timestamp=datetime.now(UTC),
                value=data.value,
                action="Consider buying protection",
            )
            alerts.append(alert)

        # Check rapid changes
        if abs(data.change_1d) >= self.alert_change_spin.value():
            alert = SkewAlert(
                level="WARNING",
                message=f"SKEW rapid change: {data.change_1d:+.1f}",
                timestamp=datetime.now(UTC),
                value=data.value,
                action="Review positions for tail risk",
            )
            alerts.append(alert)

        # Process alerts
        for alert in alerts:
            self.alert_history.append(alert)
            self.alert_triggered.emit(alert)
            self.display_alert(alert)

    def display_alert(self, alert: SkewAlert):
        """Display alert in UI"""
        alert_text = f"[{alert.timestamp.strftime('%H:%M')}] "
        alert_text += f"{alert.level}: {alert.message}"
        if alert.action:
            alert_text += f" - {alert.action}"

        current_text = self.alerts_list.toPlainText()
        new_text = alert_text + "\n" + current_text
        self.alerts_list.setText(new_text[:500])  # Limit text length

    # ==========================================================================
    # SETTINGS METHODS
    # ==========================================================================

    def apply_settings(self):
        """Apply settings changes"""
        # Update interval
        intervals = [UPDATE_INTERVAL_FAST, UPDATE_INTERVAL_NORMAL, UPDATE_INTERVAL_SLOW]
        self.data_thread.update_interval = intervals[self.update_interval_combo.currentIndex()]

        # Theme
        self.apply_theme()

        logger.info("Settings applied")

    def apply_theme(self):
        """Apply UI theme"""
        # Dark theme by default
        dark_style = """
        QDialog {
            background-color: #1e1e1e;
            color: #ffffff;
        }
        QGroupBox {
            border: 1px solid #444;
            border-radius: 5px;
            margin-top: 10px;
            font-weight: normal;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
        }
        QTextEdit {
            background-color: #2d2d2d;
            border: 1px solid #444;
            color: #ffffff;
        }
        QTableWidget {
            background-color: #2d2d2d;
            alternate-background-color: #3d3d3d;
            gridline-color: #444;
        }
        QPushButton {
            background-color: #0d7377;
            color: white;
            border: none;
            padding: 5px;
            border-radius: 3px;
        }
        QPushButton:hover {
            background-color: #14a085;
        }
        """

        if self.theme_combo.currentIndex() == 0:  # Dark
            self.setStyleSheet(dark_style)

    def on_update_interval_changed(self, index: int):
        """Handle update interval change"""
        intervals = [UPDATE_INTERVAL_FAST, UPDATE_INTERVAL_NORMAL, UPDATE_INTERVAL_SLOW]
        self.data_thread.update_interval = intervals[index]
        logger.info("Update interval changed to %sms", intervals[index])

    def on_auto_update_toggled(self, checked: bool):
        """Handle auto update toggle"""
        if checked:
            self.start_monitoring()
        else:
            self.stop_monitoring()

    @Slot(str)
    def on_error(self, error_msg: str):
        """Handle errors from data thread"""
        logger.error("Data thread error: %s", error_msg)
        self.connection_label.setText("● Error")
        self.connection_label.setStyleSheet("color: red;")

    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================

    def start_monitoring(self):
        """Start SKEW monitoring"""
        self.data_thread.start()
        self.chart_timer.start(CHART_UPDATE_INTERVAL)
        logger.info("SKEW monitoring started")

    def stop_monitoring(self):
        """Stop SKEW monitoring"""
        self.data_thread.stop()
        self.chart_timer.stop()
        logger.info("SKEW monitoring stopped")

    def closeEvent(self, event):
        """Handle dialog close"""
        self.stop_monitoring()
        self.data_thread.wait()
        event.accept()


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================


def create_skew_monitor_dialog(parent=None) -> SkewMonitorDialog:
    """
    Factory function to create SKEW Monitor Dialog.

    Args:
        parent: Parent widget

    Returns:
        SkewMonitorDialog instance
    """
    return SkewMonitorDialog(parent)


# ==============================================================================
# TEST SECTION
# ==============================================================================


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # Create and show dialog
    dialog = create_skew_monitor_dialog()
    dialog.show()

    sys.exit(app.exec())
