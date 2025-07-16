#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderS08_BlackSwanGUI.py
Group: S (Signals)
Purpose: PyQt6 GUI with traffic light visualization for Black Swan detection
Author: Mohamed Talib
Date Created: 2025-01-15 
Last Updated: 2025-01-15 Time: 11:00:00  

Description:
    This module provides a comprehensive PyQt6 desktop application for Black Swan
    risk monitoring. It features real-time traffic light visualization, detailed
    component breakdowns, historical charts, and alert management. The GUI can
    run standalone or integrate with Spyder's dashboard system as an embeddable
    widget.

"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import threading

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd

# PyQt6 imports
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QProgressBar, QPushButton, QTextEdit, QTabWidget,
    QGridLayout, QFrame, QScrollArea, QGroupBox, QSpacerItem,
    QSizePolicy, QMessageBox, QSystemTrayIcon, QMenu, QTableWidget,
    QTableWidgetItem, QHeaderView, QComboBox, QSpinBox, QCheckBox
)
from PyQt6.QtCore import (
    QTimer, QThread, pyqtSignal, Qt, QSize, QPropertyAnimation,
    QEasingCurve, QRect, QDateTime, QTime
)
from PyQt6.QtGui import (
    QFont, QColor, QPalette, QPixmap, QPainter, QBrush, 
    QLinearGradient, QIcon, QAction, QPen, QRadialGradient
)

try:
    import matplotlib
    matplotlib.use('Qt5Agg')
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
    from SpyderJ_Alerts.SpyderJ01_AlertManager import SpyderAlertManager
    from SpyderG_GUI.SpyderG01_MainWindow import SpyderBaseWidget
    SPYDER_INTEGRATION = True
except ImportError:
    # Fallback for standalone operation
    import logging
    SpyderLogger = logging
    SpyderErrorHandler = None
    SpyderAlertManager = None
    SpyderBaseWidget = QWidget
    SPYDER_INTEGRATION = False

# Import Black Swan modules
from SpyderS06_BlackSwanDataCollector import (
    BlackSwanDataCollector, MarketDataSet, DataQuality
)
from SpyderS07_BlackSwanCalculator import (
    BlackSwanCalculator, BlackSwanIndicatorResult, RiskStatus, AlertLevel
)

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Update intervals (milliseconds)
UPDATE_INTERVAL_FAST = 5000      # 5 seconds during high risk
UPDATE_INTERVAL_NORMAL = 30000   # 30 seconds normal
UPDATE_INTERVAL_SLOW = 60000     # 60 seconds when stable

# GUI Colors
COLOR_GREEN = QColor(46, 204, 113)    # Emerald
COLOR_YELLOW = QColor(241, 196, 15)  # Sun flower
COLOR_RED = QColor(231, 76, 60)      # Alizarin
COLOR_DARK_BG = QColor(44, 62, 80)   # Midnight blue
COLOR_LIGHT_BG = QColor(52, 73, 94)  # Wet asphalt
COLOR_TEXT = QColor(236, 240, 241)   # Clouds

# Window dimensions
DEFAULT_WIDTH = 1200
DEFAULT_HEIGHT = 800
MIN_WIDTH = 800
MIN_HEIGHT = 600

# Chart settings
HISTORY_HOURS = 24
MAX_CHART_POINTS = 288  # 24 hours * 12 (5-minute intervals)

# ==============================================================================
# CUSTOM WIDGETS
# ==============================================================================
class TrafficLightWidget(QWidget):
    """
    Custom traffic light visualization widget.
    
    Displays an animated traffic light with current risk status and score.
    Includes glow effects and smooth transitions between states.
    """
    
    def __init__(self, parent=None):
        """Initialize the traffic light widget."""
        super().__init__(parent)
        self.status = RiskStatus.GREEN
        self.score = 0.0
        self.setFixedSize(200, 400)
        
        # Animation for glow effect
        self.glow_animation = QPropertyAnimation(self, b"glow_radius")
        self.glow_animation.setDuration(1000)
        self.glow_animation.setLoopCount(-1)  # Infinite loop
        self.glow_animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._glow_radius = 50
        
    @property
    def glow_radius(self):
        """Get glow radius for animation."""
        return self._glow_radius
        
    @glow_radius.setter
    def glow_radius(self, value):
        """Set glow radius for animation."""
        self._glow_radius = value
        self.update()
        
    def set_status(self, status: RiskStatus, score: float):
        """
        Update the traffic light status.
        
        Args:
            status: Risk status
            score: Risk score
        """
        self.status = status
        self.score = score
        
        # Update animation based on status
        if status == RiskStatus.RED:
            self.glow_animation.setStartValue(50)
            self.glow_animation.setEndValue(80)
            self.glow_animation.start()
        elif status == RiskStatus.YELLOW:
            self.glow_animation.setStartValue(40)
            self.glow_animation.setEndValue(60)
            self.glow_animation.start()
        else:
            self.glow_animation.stop()
            self._glow_radius = 50
            
        self.update()
        
    def paintEvent(self, event):
        """Custom paint event for traffic light."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw background frame
        frame_rect = QRect(20, 20, 160, 360)
        painter.setBrush(QBrush(COLOR_DARK_BG))
        painter.setPen(QPen(COLOR_LIGHT_BG, 3))
        painter.drawRoundedRect(frame_rect, 20, 20)
        
        # Light positions and colors
        lights = [
            {'pos': (100, 80), 'color': 'red', 'active': self.status == RiskStatus.RED},
            {'pos': (100, 200), 'color': 'yellow', 'active': self.status == RiskStatus.YELLOW},
            {'pos': (100, 320), 'color': 'green', 'active': self.status == RiskStatus.GREEN}
        ]
        
        # Draw lights
        for light in lights:
            x, y = light['pos']
            
            if light['active']:
                # Active light with glow
                if light['color'] == 'red':
                    color = COLOR_RED
                elif light['color'] == 'yellow':
                    color = COLOR_YELLOW
                else:
                    color = COLOR_GREEN
                    
                # Draw glow effect
                if self.status != RiskStatus.GREEN:
                    glow_gradient = QRadialGradient(x, y, self._glow_radius)
                    glow_color = QColor(color)
                    glow_color.setAlpha(100)
                    glow_gradient.setColorAt(0, glow_color)
                    glow_gradient.setColorAt(1, Qt.GlobalColor.transparent)
                    painter.setBrush(QBrush(glow_gradient))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawEllipse(x - self._glow_radius, y - self._glow_radius,
                                      self._glow_radius * 2, self._glow_radius * 2)
                    
                # Draw main light
                painter.setBrush(QBrush(color))
                painter.setPen(QPen(color.darker(150), 2))
                painter.drawEllipse(x - 40, y - 40, 80, 80)
                
                # Inner highlight
                highlight = QRadialGradient(x - 10, y - 10, 30)
                highlight.setColorAt(0, color.lighter(150))
                highlight.setColorAt(1, color)
                painter.setBrush(QBrush(highlight))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(x - 35, y - 35, 70, 70)
            else:
                # Inactive light
                painter.setBrush(QBrush(QColor(80, 80, 80)))
                painter.setPen(QPen(QColor(60, 60, 60), 2))
                painter.drawEllipse(x - 40, y - 40, 80, 80)
                
        # Draw score text
        painter.setPen(QPen(COLOR_TEXT))
        painter.setFont(QFont('Arial', 14, QFont.Weight.Bold))
        score_text = f"Score: {self.score:.2f}"
        painter.drawText(frame_rect.adjusted(0, -30, 0, 0), 
                        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
                        score_text)

class ComponentWidget(QFrame):
    """
    Widget to display individual component information.
    
    Shows component name, score, progress bar, and description.
    """
    
    def __init__(self, component_name: str, parent=None):
        """Initialize component widget."""
        super().__init__(parent)
        self.component_name = component_name
        self.setFrameStyle(QFrame.Shape.Box)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_LIGHT_BG.name()};
                border: 1px solid {COLOR_DARK_BG.name()};
                border-radius: 10px;
                padding: 10px;
            }}
        """)
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the component UI."""
        layout = QVBoxLayout()
        layout.setSpacing(10)
        
        # Component title
        title = QLabel(self.component_name.replace('_', ' ').title())
        title.setFont(QFont('Arial', 12, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLOR_TEXT.name()};")
        layout.addWidget(title)
        
        # Score and weight info
        info_layout = QHBoxLayout()
        self.score_label = QLabel("Score: 0.00")
        self.score_label.setStyleSheet(f"color: {COLOR_TEXT.name()};")
        self.weight_label = QLabel("Weight: 0%")
        self.weight_label.setStyleSheet(f"color: {COLOR_TEXT.name()};")
        info_layout.addWidget(self.score_label)
        info_layout.addStretch()
        info_layout.addWidget(self.weight_label)
        layout.addLayout(info_layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 500)  # 0 to 5.0 scaled
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(20)
        layout.addWidget(self.progress_bar)
        
        # Description
        self.description_label = QLabel("No data")
        self.description_label.setStyleSheet(f"color: {COLOR_TEXT.name()};")
        self.description_label.setWordWrap(True)
        layout.addWidget(self.description_label)
        
        layout.addStretch()
        self.setLayout(layout)
        
    def update_component(self, score: float, weight: float, description: str):
        """
        Update component display.
        
        Args:
            score: Component score
            weight: Component weight
            description: Status description
        """
        self.score_label.setText(f"Score: {score:.2f}")
        self.weight_label.setText(f"Weight: {weight:.0%}")
        self.description_label.setText(description)
        
        # Update progress bar
        self.progress_bar.setValue(int(score * 100))
        
        # Update progress bar color based on score
        if score < 1.5:
            color = COLOR_GREEN
        elif score < 3.0:
            color = COLOR_YELLOW
        else:
            color = COLOR_RED
            
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 2px solid {COLOR_DARK_BG.name()};
                border-radius: 5px;
                text-align: center;
                background-color: {COLOR_DARK_BG.name()};
            }}
            QProgressBar::chunk {{
                background-color: {color.name()};
                border-radius: 3px;
            }}
        """)

if MATPLOTLIB_AVAILABLE:
    class HistoryChartWidget(FigureCanvas):
        """
        Chart widget for displaying historical Black Swan scores.
        
        Uses matplotlib to create an interactive chart with score history
        and status zones.
        """
        
        def __init__(self, parent=None):
            """Initialize the chart widget."""
            # Create figure with dark theme
            plt.style.use('dark_background')
            self.figure = Figure(figsize=(10, 4), dpi=100)
            self.figure.patch.set_facecolor(COLOR_DARK_BG.name())
            
            super().__init__(self.figure)
            self.setParent(parent)
            
            # Setup axes
            self.ax = self.figure.add_subplot(111)
            self.ax.set_facecolor(COLOR_LIGHT_BG.name())
            
            # Data storage
            self.timestamps = []
            self.scores = []
            
            # Initial plot
            self.update_chart()
            
        def add_data_point(self, timestamp: datetime, score: float):
            """
            Add a new data point to the chart.
            
            Args:
                timestamp: Data timestamp
                score: Risk score
            """
            self.timestamps.append(timestamp)
            self.scores.append(score)
            
            # Limit data points
            if len(self.timestamps) > MAX_CHART_POINTS:
                self.timestamps = self.timestamps[-MAX_CHART_POINTS:]
                self.scores = self.scores[-MAX_CHART_POINTS:]
                
            self.update_chart()
            
        def update_chart(self):
            """Update the chart display."""
            self.ax.clear()
            
            # Set labels and title
            self.ax.set_xlabel('Time', color=COLOR_TEXT.name())
            self.ax.set_ylabel('Risk Score', color=COLOR_TEXT.name())
            self.ax.set_title('Black Swan Risk History (24 Hours)', 
                            color=COLOR_TEXT.name(), fontsize=14, fontweight='bold')
            
            # Set y-axis limits
            self.ax.set_ylim(0, 5)
            
            # Draw risk zones
            self.ax.axhspan(0, 1.90, alpha=0.2, color=COLOR_GREEN.name(), label='Green Zone')
            self.ax.axhspan(1.90, 2.00, alpha=0.2, color=COLOR_YELLOW.name(), label='Yellow Zone')
            self.ax.axhspan(2.00, 5.0, alpha=0.2, color=COLOR_RED.name(), label='Red Zone')
            
            # Plot data if available
            if self.timestamps and self.scores:
                self.ax.plot(self.timestamps, self.scores, 
                           color=COLOR_TEXT.name(), linewidth=2, label='Risk Score')
                
                # Add markers for last point
                if len(self.scores) > 0:
                    last_score = self.scores[-1]
                    if last_score <= 1.90:
                        marker_color = COLOR_GREEN.name()
                    elif last_score <= 2.00:
                        marker_color = COLOR_YELLOW.name()
                    else:
                        marker_color = COLOR_RED.name()
                        
                    self.ax.scatter(self.timestamps[-1], self.scores[-1],
                                  color=marker_color, s=100, zorder=5)
                    
            # Format x-axis
            self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            self.ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
            self.figure.autofmt_xdate()
            
            # Style
            self.ax.grid(True, alpha=0.3, color=COLOR_TEXT.name())
            self.ax.tick_params(colors=COLOR_TEXT.name())
            for spine in self.ax.spines.values():
                spine.set_color(COLOR_TEXT.name())
                
            # Legend
            self.ax.legend(loc='upper left', framealpha=0.8)
            
            # Tight layout
            self.figure.tight_layout()
            self.draw()

# ==============================================================================
# DATA UPDATE THREAD
# ==============================================================================
class DataUpdateThread(QThread):
    """
    Background thread for data collection and calculation.
    
    Runs data collection and risk calculation in a separate thread to
    prevent UI blocking.
    """
    
    # Signals
    data_updated = pyqtSignal(BlackSwanIndicatorResult)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, parent=None):
        """Initialize the data update thread."""
        super().__init__(parent)
        self.collector = BlackSwanDataCollector()
        self.calculator = BlackSwanCalculator()
        self.running = True
        self.update_interval = UPDATE_INTERVAL_NORMAL / 1000  # Convert to seconds
        
    def run(self):
        """Main thread loop."""
        while self.running:
            try:
                # Collect market data
                market_data = self.collector.collect_all_data()
                
                # Calculate indicator
                result = self.calculator.calculate_indicator(market_data)
                
                # Emit update signal
                self.data_updated.emit(result)
                
            except Exception as e:
                self.error_occurred.emit(str(e))
                
            # Sleep for update interval
            for _ in range(int(self.update_interval)):
                if not self.running:
                    break
                time.sleep(1)
                
    def set_update_interval(self, interval_ms: int):
        """
        Set update interval.
        
        Args:
            interval_ms: Update interval in milliseconds
        """
        self.update_interval = interval_ms / 1000
        
    def stop(self):
        """Stop the thread."""
        self.running = False

# ==============================================================================
# MAIN GUI CLASSES
# ==============================================================================
class BlackSwanMainWindow(QMainWindow):
    """
    Main Black Swan Indicator window.
    
    Provides standalone desktop application for Black Swan monitoring.
    """
    
    def __init__(self):
        """Initialize the main window."""
        super().__init__()
        
        # Setup logging
        if SPYDER_INTEGRATION:
            self.logger = SpyderLogger.get_logger(__name__)
            self.error_handler = SpyderErrorHandler()
        else:
            import logging
            logging.basicConfig(level=logging.INFO)
            self.logger = logging.getLogger(__name__)
            self.error_handler = None
            
        # Window setup
        self.setWindowTitle("Black Swan Indicator - Risk Monitor")
        self.setGeometry(100, 100, DEFAULT_WIDTH, DEFAULT_HEIGHT)
        self.setMinimumSize(MIN_WIDTH, MIN_HEIGHT)
        
        # Apply dark theme
        self._apply_dark_theme()
        
        # Create central widget
        self.black_swan_widget = BlackSwanWidget()
        self.setCentralWidget(self.black_swan_widget)
        
        # Setup menus
        self._setup_menus()
        
        # Setup system tray
        self._setup_system_tray()
        
        # Status bar
        self.statusBar().showMessage("Initializing...")
        
        self.logger.info("Black Swan GUI initialized")
        
    def _apply_dark_theme(self):
        """Apply dark theme to the application."""
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.ColorRole.Window, COLOR_DARK_BG)
        dark_palette.setColor(QPalette.ColorRole.WindowText, COLOR_TEXT)
        dark_palette.setColor(QPalette.ColorRole.Base, COLOR_LIGHT_BG)
        dark_palette.setColor(QPalette.ColorRole.AlternateBase, COLOR_DARK_BG)
        dark_palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
        dark_palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
        dark_palette.setColor(QPalette.ColorRole.Text, COLOR_TEXT)
        dark_palette.setColor(QPalette.ColorRole.Button, COLOR_LIGHT_BG)
        dark_palette.setColor(QPalette.ColorRole.ButtonText, COLOR_TEXT)
        dark_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        dark_palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
        self.setPalette(dark_palette)
        
    def _setup_menus(self):
        """Setup application menus."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('File')
        
        export_action = QAction('Export Data', self)
        export_action.triggered.connect(self.black_swan_widget.export_data)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction('Exit', self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # View menu
        view_menu = menubar.addMenu('View')
        
        refresh_action = QAction('Refresh Now', self)
        refresh_action.triggered.connect(self.black_swan_widget.manual_refresh)
        view_menu.addAction(refresh_action)
        
        # Settings menu
        settings_menu = menubar.addMenu('Settings')
        
        config_action = QAction('Configuration', self)
        config_action.triggered.connect(self.black_swan_widget.show_settings)
        settings_menu.addAction(config_action)
        
        # Help menu
        help_menu = menubar.addMenu('Help')
        
        about_action = QAction('About', self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
        
    def _setup_system_tray(self):
        """Setup system tray icon."""
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon = QSystemTrayIcon(self)
            
            # Create tray menu
            tray_menu = QMenu()
            
            show_action = QAction("Show", self)
            show_action.triggered.connect(self.show)
            tray_menu.addAction(show_action)
            
            refresh_action = QAction("Refresh", self)
            refresh_action.triggered.connect(self.black_swan_widget.manual_refresh)
            tray_menu.addAction(refresh_action)
            
            tray_menu.addSeparator()
            
            quit_action = QAction("Quit", self)
            quit_action.triggered.connect(QApplication.instance().quit)
            tray_menu.addAction(quit_action)
            
            self.tray_icon.setContextMenu(tray_menu)
            self.tray_icon.show()
            
            # Connect double-click
            self.tray_icon.activated.connect(self._tray_icon_activated)
            
    def _tray_icon_activated(self, reason):
        """Handle tray icon activation."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show()
            self.raise_()
            self.activateWindow()
            
    def _show_about(self):
        """Show about dialog."""
        QMessageBox.about(self, "About Black Swan Indicator",
            "Black Swan Indicator v1.0\n\n"
            "Market risk detection system for Spyder Trading Platform\n\n"
            "Monitors multiple market indicators to detect potential\n"
            "black swan events and provide early warning signals."
        )
        
    def closeEvent(self, event):
        """Handle window close event."""
        if hasattr(self, 'tray_icon') and self.tray_icon.isVisible():
            self.hide()
            event.ignore()
            self.tray_icon.showMessage(
                "Black Swan Indicator",
                "Application minimized to system tray",
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )
        else:
            event.accept()

class BlackSwanWidget(SpyderBaseWidget):
    """
    Main Black Swan indicator widget.
    
    Can be used standalone or embedded in Spyder dashboards.
    """
    
    # Signals
    status_changed = pyqtSignal(str, float)  # status, score
    alert_triggered = pyqtSignal(str, str)   # level, message
    
    def __init__(self, parent=None):
        """Initialize the widget."""
        super().__init__(parent)
        
        # Setup logging
        if SPYDER_INTEGRATION:
            self.logger = SpyderLogger.get_logger(__name__)
            self.error_handler = SpyderErrorHandler()
            self.alert_manager = SpyderAlertManager.get_instance() if SpyderAlertManager else None
        else:
            import logging
            logging.basicConfig(level=logging.INFO)
            self.logger = logging.getLogger(__name__)
            self.error_handler = None
            self.alert_manager = None
            
        # State
        self.current_result: Optional[BlackSwanIndicatorResult] = None
        self.last_status: Optional[RiskStatus] = None
        
        # Setup UI
        self.setup_ui()
        
        # Start data updates
        self.start_data_updates()
        
    def setup_ui(self):
        """Setup the widget UI."""
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Header
        header = self._create_header()
        main_layout.addWidget(header)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {COLOR_LIGHT_BG.name()};
                background-color: {COLOR_DARK_BG.name()};
            }}
            QTabBar::tab {{
                background-color: {COLOR_LIGHT_BG.name()};
                color: {COLOR_TEXT.name()};
                padding: 8px 16px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background-color: {COLOR_DARK_BG.name()};
                border-bottom: 2px solid {COLOR_TEXT.name()};
            }}
        """)
        
        # Dashboard tab
        self.dashboard_tab = self._create_dashboard_tab()
        self.tab_widget.addTab(self.dashboard_tab, "Dashboard")
        
        # Details tab
        self.details_tab = self._create_details_tab()
        self.tab_widget.addTab(self.details_tab, "Component Details")
        
        # History tab
        self.history_tab = self._create_history_tab()
        self.tab_widget.addTab(self.history_tab, "History")
        
        # Settings tab
        self.settings_tab = self._create_settings_tab()
        self.tab_widget.addTab(self.settings_tab, "Settings")
        
        main_layout.addWidget(self.tab_widget)
        
        self.setLayout(main_layout)
        
    def _create_header(self) -> QWidget:
        """Create header widget."""
        header = QWidget()
        layout = QHBoxLayout()
        
        # Title
        title = QLabel("Black Swan Risk Monitor")
        title.setFont(QFont('Arial', 18, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLOR_TEXT.name()};")
        layout.addWidget(title)
        
        layout.addStretch()
        
        # Update time
        self.update_time_label = QLabel("Last Update: Never")
        self.update_time_label.setStyleSheet(f"color: {COLOR_TEXT.name()};")
        layout.addWidget(self.update_time_label)
        
        # Refresh button
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.manual_refresh)
        self.refresh_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_LIGHT_BG.name()};
                color: {COLOR_TEXT.name()};
                border: 1px solid {COLOR_TEXT.name()};
                padding: 5px 15px;
                border-radius: 5px;
            }}
            QPushButton:hover {{
                background-color: {COLOR_TEXT.name()};
                color: {COLOR_DARK_BG.name()};
            }}
        """)
        layout.addWidget(self.refresh_button)
        
        header.setLayout(layout)
        return header
        
    def _create_dashboard_tab(self) -> QWidget:
        """Create main dashboard tab."""
        widget = QWidget()
        layout = QHBoxLayout()
        
        # Left side - Traffic light
        left_panel = QVBoxLayout()
        
        # Traffic light widget
        self.traffic_light = TrafficLightWidget()
        left_panel.addWidget(self.traffic_light, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Status message
        self.status_message = QLabel("Initializing...")
        self.status_message.setFont(QFont('Arial', 14, QFont.Weight.Bold))
        self.status_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_message.setWordWrap(True)
        self.status_message.setStyleSheet(f"""
            QLabel {{
                color: {COLOR_TEXT.name()};
                padding: 20px;
                background-color: {COLOR_LIGHT_BG.name()};
                border-radius: 10px;
            }}
        """)
        left_panel.addWidget(self.status_message)
        
        left_panel.addStretch()
        
        left_widget = QWidget()
        left_widget.setLayout(left_panel)
        left_widget.setMaximumWidth(300)
        layout.addWidget(left_widget)
        
        # Right side - Components
        right_panel = QVBoxLayout()
        
        # Components title
        comp_title = QLabel("Risk Components")
        comp_title.setFont(QFont('Arial', 16, QFont.Weight.Bold))
        comp_title.setStyleSheet(f"color: {COLOR_TEXT.name()};")
        right_panel.addWidget(comp_title)
        
        # Component widgets grid
        comp_grid = QGridLayout()
        self.component_widgets = {}
        
        components = [
            ('volatility', 0, 0),
            ('market_performance', 0, 1),
            ('credit_stress', 1, 0),
            ('liquidity_stress', 1, 1),
            ('options_activity', 2, 0)
        ]
        
        for comp_name, row, col in components:
            widget = ComponentWidget(comp_name)
            self.component_widgets[comp_name] = widget
            comp_grid.addWidget(widget, row, col)
            
        right_panel.addLayout(comp_grid)
        right_panel.addStretch()
        
        right_widget = QWidget()
        right_widget.setLayout(right_panel)
        layout.addWidget(right_widget)
        
        widget.setLayout(layout)
        return widget
        
    def _create_details_tab(self) -> QWidget:
        """Create detailed components tab."""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Details text area
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setFont(QFont('Courier', 10))
        self.details_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: {COLOR_LIGHT_BG.name()};
                color: {COLOR_TEXT.name()};
                border: 1px solid {COLOR_DARK_BG.name()};
            }}
        """)
        
        layout.addWidget(self.details_text)
        widget.setLayout(layout)
        return widget
        
    def _create_history_tab(self) -> QWidget:
        """Create history tab."""
        widget = QWidget()
        layout = QVBoxLayout()
        
        if MATPLOTLIB_AVAILABLE:
            # Chart widget
            self.history_chart = HistoryChartWidget()
            layout.addWidget(self.history_chart)
        else:
            # Fallback text display
            self.history_text = QTextEdit()
            self.history_text.setReadOnly(True)
            self.history_text.setPlainText("Matplotlib not available - Install matplotlib for charts")
            layout.addWidget(self.history_text)
            
        # History table
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(5)
        self.history_table.setHorizontalHeaderLabels(
            ['Time', 'Status', 'Score', 'Alert Level', 'Message']
        )
        self.history_table.horizontalHeader().setStretchLastSection(True)
        self.history_table.setMaximumHeight(200)
        layout.addWidget(self.history_table)
        
        widget.setLayout(layout)
        return widget
        
    def _create_settings_tab(self) -> QWidget:
        """Create settings tab."""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Update interval
        interval_group = QGroupBox("Update Interval")
        interval_layout = QHBoxLayout()
        
        self.interval_combo = QComboBox()
        self.interval_combo.addItems(['5 seconds', '30 seconds', '60 seconds', '5 minutes'])
        self.interval_combo.setCurrentIndex(1)  # Default 30 seconds
        self.interval_combo.currentIndexChanged.connect(self._update_interval_changed)
        interval_layout.addWidget(QLabel("Update every:"))
        interval_layout.addWidget(self.interval_combo)
        interval_layout.addStretch()
        
        interval_group.setLayout(interval_layout)
        layout.addWidget(interval_group)
        
        # Thresholds
        threshold_group = QGroupBox("Risk Thresholds")
        threshold_layout = QGridLayout()
        
        # Green threshold
        threshold_layout.addWidget(QLabel("Green Maximum:"), 0, 0)
        self.green_spin = QSpinBox()
        self.green_spin.setRange(0, 500)
        self.green_spin.setValue(190)  # 1.90
        self.green_spin.setSuffix(" (x0.01)")
        threshold_layout.addWidget(self.green_spin, 0, 1)
        
        # Yellow threshold
        threshold_layout.addWidget(QLabel("Yellow Maximum:"), 1, 0)
        self.yellow_spin = QSpinBox()
        self.yellow_spin.setRange(0, 500)
        self.yellow_spin.setValue(200)  # 2.00
        self.yellow_spin.setSuffix(" (x0.01)")
        threshold_layout.addWidget(self.yellow_spin, 1, 1)
        
        # Apply button
        self.apply_threshold_btn = QPushButton("Apply Thresholds")
        self.apply_threshold_btn.clicked.connect(self._apply_thresholds)
        threshold_layout.addWidget(self.apply_threshold_btn, 2, 0, 1, 2)
        
        threshold_group.setLayout(threshold_layout)
        layout.addWidget(threshold_group)
        
        # Alerts
        alert_group = QGroupBox("Alert Settings")
        alert_layout = QVBoxLayout()
        
        self.yellow_alert_check = QCheckBox("Alert on Yellow Status")
        self.yellow_alert_check.setChecked(True)
        alert_layout.addWidget(self.yellow_alert_check)
        
        self.red_alert_check = QCheckBox("Alert on Red Status")
        self.red_alert_check.setChecked(True)
        alert_layout.addWidget(self.red_alert_check)
        
        self.sound_alert_check = QCheckBox("Sound Alerts")
        self.sound_alert_check.setChecked(False)
        alert_layout.addWidget(self.sound_alert_check)
        
        alert_group.setLayout(alert_layout)
        layout.addWidget(alert_group)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
        
    def start_data_updates(self):
        """Start the data update thread."""
        self.data_thread = DataUpdateThread()
        self.data_thread.data_updated.connect(self.update_display)
        self.data_thread.error_occurred.connect(self.handle_error)
        self.data_thread.start()
        
        self.logger.info("Data updates started")
        
    def update_display(self, result: BlackSwanIndicatorResult):
        """
        Update the display with new data.
        
        Args:
            result: Black Swan calculation result
        """
        self.current_result = result
        
        # Update traffic light
        self.traffic_light.set_status(result.status, result.overall_score)
        
        # Update status message
        self.status_message.setText(result.status_message)
        
        # Update status message color
        if result.status == RiskStatus.GREEN:
            color = COLOR_GREEN
        elif result.status == RiskStatus.YELLOW:
            color = COLOR_YELLOW
        else:
            color = COLOR_RED
            
        self.status_message.setStyleSheet(f"""
            QLabel {{
                color: {COLOR_TEXT.name()};
                padding: 20px;
                background-color: {COLOR_LIGHT_BG.name()};
                border: 2px solid {color.name()};
                border-radius: 10px;
            }}
        """)
        
        # Update time
        self.update_time_label.setText(f"Last Update: {datetime.now().strftime('%H:%M:%S')}")
        
        # Update components
        for comp_name, widget in self.component_widgets.items():
            if comp_name in result.component_scores:
                comp_score = result.component_scores[comp_name]
                widget.update_component(
                    comp_score.raw_score,
                    comp_score.weight,
                    comp_score.description
                )
                
        # Update details
        self._update_details_display(result)
        
        # Update history
        self._update_history_display(result)
        
        # Check for alerts
        self._check_alerts(result)
        
        # Update status bar
        if self.parent() and hasattr(self.parent(), 'statusBar'):
            self.parent().statusBar().showMessage(
                f"Status: {result.status.value} | Score: {result.overall_score:.2f} | "
                f"Quality: {result.data_quality.value}"
            )
            
        # Emit signal
        self.status_changed.emit(result.status.value, result.overall_score)
        
        # Adjust update interval based on status
        if result.status == RiskStatus.RED:
            self.data_thread.set_update_interval(UPDATE_INTERVAL_FAST)
        elif result.status == RiskStatus.YELLOW:
            self.data_thread.set_update_interval(UPDATE_INTERVAL_NORMAL)
        else:
            self.data_thread.set_update_interval(UPDATE_INTERVAL_SLOW)
            
    def _update_details_display(self, result: BlackSwanIndicatorResult):
        """Update detailed components display."""
        details_text = f"""
BLACK SWAN INDICATOR - DETAILED ANALYSIS
========================================
Timestamp: {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
Overall Score: {result.overall_score:.3f}
Status: {result.status.value}
Alert Level: {result.alert_level.value}
Data Quality: {result.data_quality.value}

COMPONENT BREAKDOWN:
"""
        
        for comp_name, comp_score in result.component_scores.items():
            details_text += f"""
{comp_name.upper().replace('_', ' ')}:
  Raw Score: {comp_score.raw_score:.3f}
  Weight: {comp_score.weight:.1%}
  Weighted Score: {comp_score.weighted_score:.3f}
  Description: {comp_score.description}
"""
            
            # Add specific details
            for key, value in comp_score.details.items():
                if isinstance(value, (int, float)):
                    details_text += f"  {key}: {value:.3f}\n"
                else:
                    details_text += f"  {key}: {value}\n"
                    
        # Add momentum adjustments
        details_text += f"""
MOMENTUM ADJUSTMENTS:
  Rapid Deterioration: {result.momentum_adjustments.rapid_deterioration:+.3f}
  Sustained Stress: {result.momentum_adjustments.sustained_stress:+.3f}
  Recovery Momentum: {result.momentum_adjustments.recovery_momentum:+.3f}
  Total Adjustment: {result.momentum_adjustments.total_adjustment:+.3f}
  
  Base Score: {result.base_score:.3f}
  Final Score: {result.overall_score:.3f}
"""
        
        self.details_text.setPlainText(details_text)
        
    def _update_history_display(self, result: BlackSwanIndicatorResult):
        """Update history display."""
        # Update chart if available
        if MATPLOTLIB_AVAILABLE and hasattr(self, 'history_chart'):
            self.history_chart.add_data_point(result.timestamp, result.overall_score)
            
        # Update table
        row_count = self.history_table.rowCount()
        self.history_table.insertRow(0)  # Insert at top
        
        # Add data
        self.history_table.setItem(0, 0, QTableWidgetItem(
            result.timestamp.strftime('%H:%M:%S')
        ))
        
        status_item = QTableWidgetItem(result.status.value)
        if result.status == RiskStatus.GREEN:
            status_item.setForeground(COLOR_GREEN)
        elif result.status == RiskStatus.YELLOW:
            status_item.setForeground(COLOR_YELLOW)
        else:
            status_item.setForeground(COLOR_RED)
        self.history_table.setItem(0, 1, status_item)
        
        self.history_table.setItem(0, 2, QTableWidgetItem(f"{result.overall_score:.2f}"))
        self.history_table.setItem(0, 3, QTableWidgetItem(str(result.alert_level.value)))
        self.history_table.setItem(0, 4, QTableWidgetItem(result.status_message))
        
        # Limit rows
        if self.history_table.rowCount() > 100:
            self.history_table.removeRow(100)
            
    def _check_alerts(self, result: BlackSwanIndicatorResult):
        """Check and trigger alerts if needed."""
        # Check for status change
        if self.last_status and self.last_status != result.status:
            # Status changed
            if result.status == RiskStatus.YELLOW and self.yellow_alert_check.isChecked():
                self._trigger_alert("YELLOW", result.status_message)
            elif result.status == RiskStatus.RED and self.red_alert_check.isChecked():
                self._trigger_alert("RED", result.status_message)
                
        self.last_status = result.status
        
    def _trigger_alert(self, level: str, message: str):
        """Trigger an alert."""
        self.alert_triggered.emit(level, message)
        
        # System tray notification
        if hasattr(self.parent(), 'tray_icon'):
            icon = QSystemTrayIcon.MessageIcon.Warning
            if level == "RED":
                icon = QSystemTrayIcon.MessageIcon.Critical
                
            self.parent().tray_icon.showMessage(
                f"Black Swan Alert - {level}",
                message,
                icon,
                5000
            )
            
        # Spyder alert manager
        if self.alert_manager:
            try:
                self.alert_manager.send_alert(
                    alert_type=f"BLACK_SWAN_{level}",
                    message=message,
                    severity=level
                )
            except Exception as e:
                self.logger.error(f"Error sending alert: {e}")
                
        # Log alert
        self.logger.warning(f"BLACK SWAN ALERT [{level}]: {message}")
        
    def handle_error(self, error_message: str):
        """
        Handle errors from data thread.
        
        Args:
            error_message: Error description
        """
        self.logger.error(f"Data update error: {error_message}")
        
        if self.parent() and hasattr(self.parent(), 'statusBar'):
            self.parent().statusBar().showMessage(f"Error: {error_message}")
            
    def manual_refresh(self):
        """Manually trigger a data refresh."""
        self.logger.info("Manual refresh requested")
        
        # Force immediate update
        if hasattr(self, 'data_thread'):
            # Restart thread to force update
            self.data_thread.stop()
            self.data_thread.wait()
            self.start_data_updates()
            
    def export_data(self):
        """Export current data to JSON."""
        if not self.current_result:
            QMessageBox.warning(self, "No Data", "No data available to export")
            return
            
        try:
            filename = f"black_swan_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            export_data = self.current_result.to_dict()
            
            with open(filename, 'w') as f:
                json.dump(export_data, f, indent=2)
                
            QMessageBox.information(self, "Export Successful", 
                                  f"Data exported to {filename}")
            self.logger.info(f"Data exported to {filename}")
            
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Error: {str(e)}")
            self.logger.error(f"Export failed: {e}")
            
    def show_settings(self):
        """Show settings tab."""
        self.tab_widget.setCurrentWidget(self.settings_tab)
        
    def _update_interval_changed(self, index: int):
        """Handle update interval change."""
        intervals = [5000, 30000, 60000, 300000]  # milliseconds
        if 0 <= index < len(intervals):
            self.data_thread.set_update_interval(intervals[index])
            self.logger.info(f"Update interval changed to {intervals[index]}ms")
            
    def _apply_thresholds(self):
        """Apply new threshold settings."""
        try:
            green_max = self.green_spin.value() / 100.0
            yellow_max = self.yellow_spin.value() / 100.0
            
            if green_max >= yellow_max:
                QMessageBox.warning(self, "Invalid Thresholds", 
                                  "Green threshold must be less than yellow threshold")
                return
                
            # Get calculator instance
            from SpyderS07_BlackSwanCalculator import get_calculator
            calculator = get_calculator()
            
            new_thresholds = {
                'green_max': green_max,
                'yellow_max': yellow_max,
                'red_max': 5.0
            }
            
            if calculator.set_thresholds(new_thresholds):
                QMessageBox.information(self, "Success", "Thresholds updated successfully")
                self.logger.info(f"Thresholds updated: {new_thresholds}")
            else:
                QMessageBox.warning(self, "Failed", "Failed to update thresholds")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error applying thresholds: {str(e)}")
            self.logger.error(f"Error applying thresholds: {e}")
            
    def closeEvent(self, event):
        """Handle widget close."""
        if hasattr(self, 'data_thread'):
            self.data_thread.stop()
            self.data_thread.wait()
            
        super().closeEvent(event)

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def launch_black_swan_gui():
    """Launch the Black Swan GUI application."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
        
    # Set application properties
    app.setApplicationName("Black Swan Indicator")
    app.setOrganizationName("Spyder Trading System")
    
    # Create and show main window
    window = BlackSwanMainWindow()
    window.show()
    
    return app, window

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Launch GUI
    app, window = launch_black_swan_gui()
    
    # Run application
    sys.exit(app.exec())
