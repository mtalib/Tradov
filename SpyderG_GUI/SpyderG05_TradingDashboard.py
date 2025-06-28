#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderG05_TradingDashboard.py
Group: G (GUI/User Interface)
Purpose: Enhanced monitoring dashboard with real-time visualization

Description:
    This module provides a comprehensive monitoring dashboard for the SPYDER
    automated trading system. Features include:
    - System health monitoring
    - P&L tracking and performance metrics
    - Risk monitoring with Greeks display
    - Active positions management
    - Trading activity logs
    - Optional advanced visualizations with PyQtGraph
    - Optional ZeroMQ integration for real-time updates

Author: SPYDER Team
Date: 2025-06-28
Version: 3.0 - Complete Enhanced Dashboard
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from collections import deque
import json
import numpy as np
import logging

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QTextEdit, QGroupBox, QFrame, QSplitter, QHeaderView,
    QProgressBar, QTabWidget, QScrollArea, QMessageBox,
    QComboBox, QSpinBox, QDoubleSpinBox
)
from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, QThread, pyqtSlot, QSize
)
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QBrush, QShortcut, QKeySequence
)

# Optional imports
try:
    import pyqtgraph as pg
    PYQTGRAPH_AVAILABLE = True
except ImportError:
    PYQTGRAPH_AVAILABLE = False
    print("PyQtGraph not installed. Advanced visualizations disabled.")

try:
    import zmq
    ZEROMQ_AVAILABLE = True
except ImportError:
    ZEROMQ_AVAILABLE = False
    print("ZeroMQ not installed. Real-time updates disabled.")

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
except ImportError:
    class SpyderLogger:
        @staticmethod
        def get_logger(name):
            return logging.getLogger(name)

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Window settings
WINDOW_WIDTH = 1920
WINDOW_HEIGHT = 1080

# Update intervals
UPDATE_INTERVAL_MS = 1000
PNL_UPDATE_MS = 2000
RISK_UPDATE_MS = 5000

# Colors
COLOR_BACKGROUND = "#0a0a0a"
COLOR_PANEL = "#141414"
COLOR_BORDER = "#2a2a2a"
COLOR_TEXT = "#e0e0e0"
COLOR_POSITIVE = "#00ff41"
COLOR_NEGATIVE = "#ff1744"
COLOR_WARNING = "#ff9800"
COLOR_INFO = "#00bcd4"
COLOR_NEUTRAL = "#888888"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class SystemStatus:
    """System component status."""
    component: str
    status: str
    latency_ms: float
    last_update: datetime
    message: str

@dataclass
class PnLMetrics:
    """P&L tracking metrics."""
    daily_pnl: float
    daily_pnl_pct: float
    weekly_pnl: float
    monthly_pnl: float
    yearly_pnl: float
    realized_pnl: float
    unrealized_pnl: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown: float
    current_drawdown: float

@dataclass
class RiskMetrics:
    """Portfolio risk metrics."""
    portfolio_delta: float
    portfolio_gamma: float
    portfolio_theta: float
    portfolio_vega: float
    var_95: float
    margin_used: float
    margin_available: float
    buying_power: float
    leverage: float
    beta_to_spy: float
    correlation_to_spy: float
    max_loss_scenario: float

@dataclass
class TradingActivity:
    """Trading activity log entry."""
    timestamp: datetime
    activity_type: str
    strategy: str
    symbol: str
    description: str
    pnl_impact: Optional[float]
    severity: str

# ==============================================================================
# MONITORING WIDGETS
# ==============================================================================
class SystemHealthWidget(QGroupBox):
    """System health monitoring widget."""
    
    def __init__(self):
        super().__init__("System Health")
        self.components = {}
        self.setup_ui()
        
    def setup_ui(self):
        """Setup system health UI."""
        self.setStyleSheet(f"""
            QGroupBox {{
                color: {COLOR_TEXT};
                background-color: {COLOR_PANEL};
                border: 1px solid {COLOR_BORDER};
                border-radius: 5px;
                font-weight: bold;
                font-size: 12px;
                padding-top: 15px;
            }}
        """)
        
        layout = QGridLayout()
        layout.setSpacing(10)
        
        components = [
            ("IB Gateway", "Connection to Interactive Brokers"),
            ("Market Data", "Real-time data feeds"),
            ("Strategy Engine", "Automated strategy execution"),
            ("Risk Manager", "Risk monitoring and limits"),
            ("ML Models", "Machine learning predictions"),
            ("Database", "Data storage and retrieval")
        ]
        
        for i, (name, description) in enumerate(components):
            row = i // 2
            col = (i % 2) * 3
            
            name_label = QLabel(name)
            name_label.setStyleSheet(f"color: {COLOR_TEXT}; font-weight: bold;")
            
            status_indicator = QLabel("●")
            status_indicator.setStyleSheet(f"color: {COLOR_NEUTRAL}; font-size: 16px;")
            status_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            latency_label = QLabel("-- ms")
            latency_label.setStyleSheet(f"color: {COLOR_NEUTRAL}; font-size: 10px;")
            
            layout.addWidget(name_label, row, col)
            layout.addWidget(status_indicator, row, col + 1)
            layout.addWidget(latency_label, row, col + 2)
            
            self.components[name] = {
                'indicator': status_indicator,
                'latency': latency_label
            }
        
        self.setLayout(layout)
        
    def update_status(self, status: SystemStatus):
        """Update component status."""
        if status.component in self.components:
            color_map = {
                'healthy': COLOR_POSITIVE,
                'degraded': COLOR_WARNING,
                'critical': COLOR_NEGATIVE,
                'offline': COLOR_NEUTRAL
            }
            color = color_map.get(status.status, COLOR_NEUTRAL)
            
            self.components[status.component]['indicator'].setStyleSheet(
                f"color: {color}; font-size: 16px;"
            )
            self.components[status.component]['latency'].setText(
                f"{status.latency_ms:.0f} ms"
            )

class PnLDisplayWidget(QGroupBox):
    """P&L display widget."""
    
    def __init__(self):
        super().__init__("P&L Performance")
        self.setup_ui()
        
    def setup_ui(self):
        """Setup P&L display UI."""
        self.setStyleSheet(f"""
            QGroupBox {{
                color: {COLOR_TEXT};
                background-color: {COLOR_PANEL};
                border: 1px solid {COLOR_BORDER};
                border-radius: 5px;
                font-weight: bold;
                font-size: 12px;
                padding-top: 15px;
            }}
        """)
        
        layout = QGridLayout()
        layout.setSpacing(10)
        
        # Daily P&L
        self.daily_pnl_label = QLabel("Daily P&L")
        self.daily_pnl_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.daily_pnl_value = QLabel("$0.00")
        self.daily_pnl_value.setStyleSheet(f"""
            font-size: 24px; 
            font-weight: bold; 
            color: {COLOR_NEUTRAL};
        """)
        self.daily_pnl_pct = QLabel("0.00%")
        self.daily_pnl_pct.setStyleSheet(f"font-size: 14px; color: {COLOR_NEUTRAL};")
        
        layout.addWidget(self.daily_pnl_label, 0, 0, 1, 2)
        layout.addWidget(self.daily_pnl_value, 1, 0, 1, 2)
        layout.addWidget(self.daily_pnl_pct, 2, 0, 1, 2)
        
        # Separator
        separator = QFrame()
        separator.setFrameStyle(QFrame.Shape.HLine)
        separator.setStyleSheet(f"background-color: {COLOR_BORDER};")
        layout.addWidget(separator, 3, 0, 1, 2)
        
        # Other metrics
        metrics = [
            ("Weekly", "$0.00"),
            ("Monthly", "$0.00"),
            ("Yearly", "$0.00"),
            ("Realized", "$0.00"),
            ("Unrealized", "$0.00"),
            ("Win Rate", "0.0%"),
            ("Profit Factor", "0.00"),
            ("Sharpe Ratio", "0.00")
        ]
        
        self.metric_labels = {}
        row = 4
        for i, (name, default) in enumerate(metrics):
            label = QLabel(f"{name}:")
            label.setStyleSheet("font-size: 11px;")
            value = QLabel(default)
            value.setStyleSheet(f"font-size: 11px; color: {COLOR_NEUTRAL};")
            
            col = (i % 2) * 2
            if i % 2 == 0 and i > 0:
                row += 1
                
            layout.addWidget(label, row, col)
            layout.addWidget(value, row, col + 1)
            
            self.metric_labels[name] = value
        
        self.setLayout(layout)
        
    def update_metrics(self, metrics: PnLMetrics):
        """Update P&L metrics display."""
        # Daily P&L
        self.daily_pnl_value.setText(f"${metrics.daily_pnl:,.2f}")
        self.daily_pnl_pct.setText(f"{metrics.daily_pnl_pct:+.2f}%")
        
        color = COLOR_POSITIVE if metrics.daily_pnl >= 0 else COLOR_NEGATIVE
        self.daily_pnl_value.setStyleSheet(f"""
            font-size: 24px; 
            font-weight: bold; 
            color: {color};
        """)
        self.daily_pnl_pct.setStyleSheet(f"font-size: 14px; color: {color};")
        
        # Update other metrics
        self.metric_labels["Weekly"].setText(f"${metrics.weekly_pnl:,.2f}")
        self.metric_labels["Monthly"].setText(f"${metrics.monthly_pnl:,.2f}")
        self.metric_labels["Yearly"].setText(f"${metrics.yearly_pnl:,.2f}")
        self.metric_labels["Realized"].setText(f"${metrics.realized_pnl:,.2f}")
        self.metric_labels["Unrealized"].setText(f"${metrics.unrealized_pnl:,.2f}")
        self.metric_labels["Win Rate"].setText(f"{metrics.win_rate:.1f}%")
        self.metric_labels["Profit Factor"].setText(f"{metrics.profit_factor:.2f}")
        self.metric_labels["Sharpe Ratio"].setText(f"{metrics.sharpe_ratio:.2f}")

class RiskMonitorWidget(QGroupBox):
    """Risk monitoring widget."""
    
    def __init__(self):
        super().__init__("Risk Monitor")
        self.setup_ui()
        
    def setup_ui(self):
        """Setup risk monitor UI."""
        self.setStyleSheet(f"""
            QGroupBox {{
                color: {COLOR_TEXT};
                background-color: {COLOR_PANEL};
                border: 1px solid {COLOR_BORDER};
                border-radius: 5px;
                font-weight: bold;
                font-size: 12px;
                padding-top: 15px;
            }}
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(10)
        
        # Greeks display
        greeks_layout = QGridLayout()
        self.greek_bars = {}
        
        greeks = [
            ("Delta", -100, 100, 0),
            ("Gamma", -50, 50, 0),
            ("Theta", -500, 0, -100),
            ("Vega", -1000, 1000, 0)
        ]
        
        for i, (name, min_val, max_val, warn_val) in enumerate(greeks):
            label = QLabel(f"{name}:")
            value = QLabel("0.00")
            
            bar = QProgressBar()
            bar.setMinimum(min_val)
            bar.setMaximum(max_val)
            bar.setValue(0)
            bar.setTextVisible(False)
            bar.setMaximumHeight(10)
            bar.setStyleSheet(f"""
                QProgressBar {{
                    background-color: #1a1a1a;
                    border: 1px solid {COLOR_BORDER};
                    border-radius: 5px;
                }}
                QProgressBar::chunk {{
                    background-color: {COLOR_INFO};
                    border-radius: 5px;
                }}
            """)
            
            greeks_layout.addWidget(label, i, 0)
            greeks_layout.addWidget(value, i, 1)
            greeks_layout.addWidget(bar, i, 2)
            
            self.greek_bars[name] = {'value': value, 'bar': bar, 'warn': warn_val}
        
        # Risk metrics
        risk_layout = QGridLayout()
        self.risk_labels = {}
        
        risk_metrics = [
            ("Margin Used", "$0"),
            ("Buying Power", "$0"),
            ("VaR (95%)", "$0"),
            ("Max Drawdown", "0.0%"),
            ("Leverage", "0.0x"),
            ("Beta to SPY", "0.00")
        ]
        
        for i, (name, default) in enumerate(risk_metrics):
            label = QLabel(f"{name}:")
            value = QLabel(default)
            
            row = i // 2
            col = (i % 2) * 2
            
            risk_layout.addWidget(label, row, col)
            risk_layout.addWidget(value, row, col + 1)
            
            self.risk_labels[name] = value
        
        layout.addLayout(greeks_layout)
        
        separator = QFrame()
        separator.setFrameStyle(QFrame.Shape.HLine)
        separator.setStyleSheet(f"background-color: {COLOR_BORDER};")
        layout.addWidget(separator)
        
        layout.addLayout(risk_layout)
        self.setLayout(layout)
        
    def update_metrics(self, metrics: RiskMetrics):
        """Update risk metrics display."""
        # Update Greeks
        greeks = {
            "Delta": metrics.portfolio_delta,
            "Gamma": metrics.portfolio_gamma,
            "Theta": metrics.portfolio_theta,
            "Vega": metrics.portfolio_vega
        }
        
        for name, value in greeks.items():
            if name in self.greek_bars:
                self.greek_bars[name]['value'].setText(f"{value:.2f}")
                self.greek_bars[name]['bar'].setValue(int(value))
        
        # Update risk metrics
        self.risk_labels["Margin Used"].setText(f"${metrics.margin_used:,.0f}")
        self.risk_labels["Buying Power"].setText(f"${metrics.buying_power:,.0f}")
        self.risk_labels["VaR (95%)"].setText(f"${metrics.var_95:,.0f}")
        self.risk_labels["Max Drawdown"].setText(f"{metrics.max_loss_scenario:.1f}%")
        self.risk_labels["Leverage"].setText(f"{metrics.leverage:.1f}x")
        self.risk_labels["Beta to SPY"].setText(f"{metrics.beta_to_spy:.2f}")

class ActivityLogWidget(QGroupBox):
    """Trading activity log widget."""
    
    def __init__(self):
        super().__init__("Trading Activity")
        self.log_entries = deque(maxlen=100)
        self.setup_ui()
        
    def setup_ui(self):
        """Setup activity log UI."""
        self.setStyleSheet(f"""
            QGroupBox {{
                color: {COLOR_TEXT};
                background-color: {COLOR_PANEL};
                border: 1px solid {COLOR_BORDER};
                border-radius: 5px;
                font-weight: bold;
                font-size: 12px;
                padding-top: 15px;
            }}
        """)
        
        layout = QVBoxLayout()
        
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setMaximumHeight(200)
        self.log_display.setStyleSheet(f"""
            QTextEdit {{
                background-color: #0a0a0a;
                color: {COLOR_TEXT};
                border: 1px solid {COLOR_BORDER};
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 10px;
            }}
        """)
        
        layout.addWidget(self.log_display)
        self.setLayout(layout)
        
    def add_activity(self, activity: TradingActivity):
        """Add trading activity to log."""
        self.log_entries.append(activity)
        
        timestamp = activity.timestamp.strftime("%H:%M:%S")
        
        color_map = {
            'info': COLOR_INFO,
            'warning': COLOR_WARNING,
            'error': COLOR_NEGATIVE,
            'critical': COLOR_NEGATIVE
        }
        color = color_map.get(activity.severity, COLOR_TEXT)
        
        pnl_text = ""
        if activity.pnl_impact is not None:
            pnl_color = COLOR_POSITIVE if activity.pnl_impact >= 0 else COLOR_NEGATIVE
            pnl_text = f' <span style="color: {pnl_color};">[${activity.pnl_impact:+,.2f}]</span>'
        
        log_html = f'<span style="color: {color};">[{timestamp}] {activity.activity_type.upper()}: {activity.description}</span>{pnl_text}'
        
        self.log_display.append(log_html)
        
        cursor = self.log_display.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.log_display.setTextCursor(cursor)

class PositionsTableWidget(QTableWidget):
    """Active positions table."""
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
        
    def setup_ui(self):
        """Setup positions table UI."""
        headers = [
            'ID', 'Strategy', 'Symbol', 'Strikes', 'Expiry', 'DTE',
            'Contracts', 'Entry Cost', 'Current', 'Unreal P&L', 'Real P&L',
            'Delta', 'Theta', 'Status'
        ]
        
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)
        
        self.setStyleSheet(f"""
            QTableWidget {{
                background-color: {COLOR_PANEL};
                color: {COLOR_TEXT};
                border: 1px solid {COLOR_BORDER};
                gridline-color: {COLOR_BORDER};
            }}
            QHeaderView::section {{
                background-color: #1a1a1a;
                color: {COLOR_TEXT};
                border: 1px solid {COLOR_BORDER};
                padding: 5px;
                font-size: 11px;
            }}
            QTableWidget::item {{
                padding: 3px;
                font-size: 10px;
            }}
        """)
        
        self.setColumnWidth(0, 60)
        self.setColumnWidth(1, 100)
        self.setColumnWidth(2, 50)
        self.setColumnWidth(3, 100)
        self.setColumnWidth(4, 70)
        self.setColumnWidth(5, 40)
        
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)

# ==============================================================================
# MAIN DASHBOARD
# ==============================================================================
class SpyderEnhancedMonitoringDashboard(QMainWindow):
    """Enhanced monitoring dashboard for SPYDER automated trading system."""
    
    def __init__(self):
        """Initialize the dashboard."""
        super().__init__()
        self.logger = SpyderLogger.get_logger(__name__)
        
        # Setup UI
        self.setup_ui()
        self.setup_timers()
        self.setup_shortcuts()
        
        # Load initial data
        self.load_test_data()
        
    def setup_ui(self):
        """Setup the main UI."""
        self.setWindowTitle("SPYDER - Enhanced Automated Trading System Monitor")
        self.setGeometry(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT)
        
        # Apply dark theme
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {COLOR_BACKGROUND};
            }}
            QLabel {{
                color: {COLOR_TEXT};
            }}
            QGroupBox {{
                color: {COLOR_TEXT};
                background-color: {COLOR_PANEL};
                border: 1px solid {COLOR_BORDER};
                border-radius: 5px;
                margin-top: 10px;
                font-weight: bold;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 10px 0 10px;
            }}
            QPushButton {{
                background-color: #2a2a2a;
                color: {COLOR_TEXT};
                border: 1px solid {COLOR_BORDER};
                padding: 5px 15px;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                background-color: #3a3a3a;
            }}
            QTabWidget::pane {{
                background-color: {COLOR_PANEL};
                border: 1px solid {COLOR_BORDER};
            }}
            QTabBar::tab {{
                background-color: #1a1a1a;
                color: {COLOR_TEXT};
                padding: 8px 16px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background-color: #2a2a2a;
            }}
        """)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Header
        header = self.create_header()
        main_layout.addWidget(header)
        
        # Content tabs
        self.tab_widget = QTabWidget()
        
        # Overview tab
        overview_tab = self.create_overview_tab()
        self.tab_widget.addTab(overview_tab, "📊 Overview")
        
        # Add more tabs if PyQtGraph is available
        if PYQTGRAPH_AVAILABLE:
            options_tab = self.create_options_tab()
            self.tab_widget.addTab(options_tab, "📈 Options Analytics")
        
        main_layout.addWidget(self.tab_widget)
        
        # Status bar
        self.create_status_bar()
        
        central_widget.setLayout(main_layout)
        
    def create_header(self) -> QWidget:
        """Create header bar."""
        header = QWidget()
        header.setMaximumHeight(60)
        header.setStyleSheet(f"""
            QWidget {{
                background-color: {COLOR_PANEL};
                border-bottom: 2px solid {COLOR_BORDER};
            }}
        """)
        
        layout = QHBoxLayout()
        layout.setContentsMargins(20, 10, 20, 10)
        
        # Title
        title = QLabel("🕷️ SPYDER Automated Trading Monitor")
        title.setStyleSheet(f"""
            QLabel {{
                color: {COLOR_TEXT};
                font-size: 20px;
                font-weight: bold;
            }}
        """)
        
        # Time
        self.time_label = QLabel()
        self.time_label.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 14px;")
        
        # Emergency stop
        self.emergency_btn = QPushButton("🛑 EMERGENCY STOP")
        self.emergency_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_NEGATIVE};
                color: white;
                font-weight: bold;
                padding: 8px 20px;
                border: none;
                border-radius: 3px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: #d32f2f;
            }}
        """)
        self.emergency_btn.clicked.connect(self.emergency_stop)
        
        layout.addWidget(title)
        layout.addStretch()
        layout.addWidget(self.time_label)
        layout.addWidget(self.emergency_btn)
        
        header.setLayout(layout)
        return header
        
    def create_overview_tab(self) -> QWidget:
        """Create overview tab."""
        widget = QWidget()
        layout = QGridLayout()
        
        # System health
        self.system_health = SystemHealthWidget()
        layout.addWidget(self.system_health, 0, 0)
        
        # P&L display
        self.pnl_display = PnLDisplayWidget()
        layout.addWidget(self.pnl_display, 0, 1)
        
        # Risk monitor
        self.risk_monitor = RiskMonitorWidget()
        layout.addWidget(self.risk_monitor, 0, 2)
        
        # Positions table
        positions_group = QGroupBox("Active Positions")
        positions_layout = QVBoxLayout()
        self.positions_table = PositionsTableWidget()
        positions_layout.addWidget(self.positions_table)
        positions_group.setLayout(positions_layout)
        layout.addWidget(positions_group, 1, 0, 1, 2)
        
        # Activity log
        self.activity_log = ActivityLogWidget()
        layout.addWidget(self.activity_log, 1, 2)
        
        widget.setLayout(layout)
        return widget
        
    def create_options_tab(self) -> QWidget:
        """Create options analytics tab (if PyQtGraph available)."""
        widget = QWidget()
        layout = QVBoxLayout()
        
        label = QLabel("Advanced Options Analytics")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size: 16px; padding: 20px;")
        layout.addWidget(label)
        
        # Add PyQtGraph visualizations here
        
        widget.setLayout(layout)
        return widget
        
    def create_status_bar(self):
        """Create status bar."""
        self.status_bar = self.statusBar()
        self.status_bar.setStyleSheet(f"""
            QStatusBar {{
                background-color: {COLOR_PANEL};
                color: {COLOR_TEXT};
                border-top: 1px solid {COLOR_BORDER};
            }}
        """)
        
        # Status widgets
        self.status_bar.addPermanentWidget(QLabel("PyQtGraph: "))
        pyqtgraph_status = QLabel("Available" if PYQTGRAPH_AVAILABLE else "Not Installed")
        pyqtgraph_status.setStyleSheet(
            f"color: {COLOR_POSITIVE if PYQTGRAPH_AVAILABLE else COLOR_WARNING};"
        )
        self.status_bar.addPermanentWidget(pyqtgraph_status)
        
        self.status_bar.addPermanentWidget(QLabel(" | ZeroMQ: "))
        zmq_status = QLabel("Available" if ZEROMQ_AVAILABLE else "Not Installed")
        zmq_status.setStyleSheet(
            f"color: {COLOR_POSITIVE if ZEROMQ_AVAILABLE else COLOR_WARNING};"
        )
        self.status_bar.addPermanentWidget(zmq_status)
        
    def setup_timers(self):
        """Setup update timers."""
        # Time update
        self.time_timer = QTimer()
        self.time_timer.timeout.connect(self.update_time)
        self.time_timer.start(1000)
        
    def setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        # F11 - Fullscreen
        self.fullscreen_shortcut = QShortcut(QKeySequence("F11"), self)
        self.fullscreen_shortcut.activated.connect(self.toggle_fullscreen)
        
        # Ctrl+Q - Quit
        self.quit_shortcut = QShortcut(QKeySequence("Ctrl+Q"), self)
        self.quit_shortcut.activated.connect(self.close)
        
    def update_time(self):
        """Update current time."""
        self.time_label.setText(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        
    def toggle_fullscreen(self):
        """Toggle fullscreen mode."""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
            
    def emergency_stop(self):
        """Handle emergency stop."""
        reply = QMessageBox.critical(
            self,
            "Emergency Stop",
            "This will immediately close all positions and halt trading.\n\n"
            "Are you sure you want to execute EMERGENCY STOP?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.logger.critical("EMERGENCY STOP ACTIVATED")
            # In production, this would trigger actual emergency procedures
            
    def load_test_data(self):
        """Load test data for demonstration."""
        # System health
        components = ["IB Gateway", "Market Data", "Strategy Engine", 
                     "Risk Manager", "ML Models", "Database"]
        
        for component in components:
            status = SystemStatus(
                component=component,
                status="healthy",
                latency_ms=np.random.randint(5, 50),
                last_update=datetime.now(),
                message="Operating normally"
            )
            self.system_health.update_status(status)
            
        # P&L metrics
        metrics = PnLMetrics(
            daily_pnl=2450.00,
            daily_pnl_pct=2.45,
            weekly_pnl=8750.00,
            monthly_pnl=35200.00,
            yearly_pnl=125000.00,
            realized_pnl=22500.00,
            unrealized_pnl=2950.00,
            total_trades=145,
            winning_trades=98,
            losing_trades=47,
            win_rate=67.6,
            profit_factor=2.35,
            sharpe_ratio=1.85,
            max_drawdown=8.5,
            current_drawdown=2.1
        )
        self.pnl_display.update_metrics(metrics)
        
        # Risk metrics
        risk = RiskMetrics(
            portfolio_delta=45.5,
            portfolio_gamma=-2.3,
            portfolio_theta=-156.8,
            portfolio_vega=-245.2,
            var_95=3500.0,
            margin_used=45000.0,
            margin_available=155000.0,
            buying_power=200000.0,
            leverage=1.2,
            beta_to_spy=0.85,
            correlation_to_spy=0.78,
            max_loss_scenario=12.5
        )
        self.risk_monitor.update_metrics(risk)
        
        # Sample activities
        activities = [
            TradingActivity(
                timestamp=datetime.now() - timedelta(minutes=30),
                activity_type="order",
                strategy="Iron Condor",
                symbol="SPY",
                description="Opened 10x Iron Condor 440/445/455/460",
                pnl_impact=None,
                severity="info"
            ),
            TradingActivity(
                timestamp=datetime.now() - timedelta(minutes=15),
                activity_type="fill",
                strategy="Bull Put Spread",
                symbol="SPY",
                description="Filled 20x Bull Put Spread 445/447 @ $0.85",
                pnl_impact=None,
                severity="info"
            ),
            TradingActivity(
                timestamp=datetime.now() - timedelta(minutes=5),
                activity_type="adjustment",
                strategy="Iron Condor",
                symbol="SPY",
                description="Rolled put side up to 442/447",
                pnl_impact=-125.00,
                severity="warning"
            )
        ]
        
        for activity in activities:
            self.activity_log.add_activity(activity)

# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================
def main():
    """Main entry point for the dashboard."""
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    # Create and show dashboard
    dashboard = SpyderEnhancedMonitoringDashboard()
    dashboard.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()