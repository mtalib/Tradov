#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderG07_FullScreenDashboard.py
Group: G (GUI/User Interface)
Purpose: Full-screen 1920x1080 trading dashboard with comprehensive market view

Description:
    This module provides a full-screen trading dashboard optimized for 1920x1080
    resolution. It displays 14 key market symbols, real-time options positions,
    SPY chart, and comprehensive risk metrics for professional options trading.

Author: Mohamed Talib
Date: 2025-06-24
Version: 1.1 - Enhanced with window controls and keyboard shortcuts
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import threading
import json

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QTextEdit, QGroupBox, QFrame, QSplitter, QHeaderView,
    QProgressBar, QTabWidget, QScrollArea, QMessageBox
)
from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, QThread, pyqtSlot, QSize, QRect
)
from PyQt6.QtGui import (
    QFont, QPalette, QColor, QIcon, QPixmap, QPainter, QBrush, QShortcut, QKeySequence
)

# Matplotlib imports for charting
import matplotlib
matplotlib.use('QtAgg')  # PyQt6 backend
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Window dimensions
WINDOW_WIDTH = 1920
WINDOW_HEIGHT = 1080

# Market symbols
TICKER_SYMBOLS = [
    'SPY', 'SPX', 'VIX', 'IWM', 'QQQ', 'TLT', '/ES', 'DIA', 
    'GLD', 'UVXY', 'ES', 'MES', 'XSP', 'NANOS'
]

# Update intervals
TICKER_UPDATE_MS = 1000      # 1 second
POSITION_UPDATE_MS = 2000    # 2 seconds
CHART_UPDATE_MS = 5000       # 5 seconds

# Color scheme
COLOR_BACKGROUND = "#0a0a0a"
COLOR_PANEL = "#1a1a1a"
COLOR_BORDER = "#333333"
COLOR_TEXT = "#ffffff"
COLOR_POSITIVE = "#00ff41"
COLOR_NEGATIVE = "#ff1744"
COLOR_NEUTRAL = "#ffd700"
COLOR_WARNING = "#ff9800"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class TickerData:
    """Market ticker data structure."""
    symbol: str
    price: float
    change: float
    change_pct: float
    volume: int
    bid: float
    ask: float
    high: float
    low: float
    timestamp: datetime


@dataclass
class OptionPosition:
    """Options position data structure."""
    symbol: str
    strategy: str
    strikes: List[float]
    expiry: str
    contracts: int
    entry_price: float
    current_price: float
    pnl: float
    pnl_pct: float
    delta: float
    theta: float
    vega: float
    gamma: float
    iv: float
    time_remaining: str
    status: str  # 'staged', 'active', 'closed'


# ==============================================================================
# CUSTOM WIDGETS
# ==============================================================================
class TickerWidget(QFrame):
    """Individual ticker display widget."""
    
    def __init__(self, symbol: str):
        super().__init__()
        self.symbol = symbol
        self.setup_ui()
        
    def setup_ui(self):
        """Setup ticker widget UI."""
        self.setFrameStyle(QFrame.Shape.Box)  # Fixed for PyQt6
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_PANEL};
                border: 1px solid {COLOR_BORDER};
                border-radius: 5px;
            }}
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Symbol label
        self.symbol_label = QLabel(self.symbol)
        self.symbol_label.setStyleSheet(f"""
            QLabel {{
                color: {COLOR_TEXT};
                font-size: 14px;
                font-weight: bold;
            }}
        """)
        self.symbol_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Price label
        self.price_label = QLabel("---")
        self.price_label.setStyleSheet(f"""
            QLabel {{
                color: {COLOR_TEXT};
                font-size: 18px;
                font-weight: bold;
            }}
        """)
        self.price_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Change label
        self.change_label = QLabel("---")
        self.change_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(self.symbol_label)
        layout.addWidget(self.price_label)
        layout.addWidget(self.change_label)
        
        self.setLayout(layout)
        
    def update_data(self, data: TickerData):
        """Update ticker display with new data."""
        self.price_label.setText(f"${data.price:.2f}")
        
        # Update change with color
        change_text = f"{data.change:+.2f} ({data.change_pct:+.2f}%)"
        if data.change > 0:
            color = COLOR_POSITIVE
        elif data.change < 0:
            color = COLOR_NEGATIVE
        else:
            color = COLOR_NEUTRAL
            
        self.change_label.setText(change_text)
        self.change_label.setStyleSheet(f"QLabel {{ color: {color}; font-size: 12px; }}")


class MarketInternalsWidget(QGroupBox):
    """Market internals display widget."""
    
    def __init__(self):
        super().__init__("Market Internals")
        self.setup_ui()
        
    def setup_ui(self):
        """Setup market internals UI."""
        self.setStyleSheet(f"""
            QGroupBox {{
                color: {COLOR_TEXT};
                background-color: {COLOR_PANEL};
                border: 1px solid {COLOR_BORDER};
                border-radius: 5px;
                font-weight: bold;
                padding-top: 10px;
            }}
        """)
        
        layout = QGridLayout()
        
        # TICK
        self.tick_label = QLabel("TICK:")
        self.tick_value = QLabel("---")
        self.tick_label.setStyleSheet(f"color: {COLOR_TEXT};")
        layout.addWidget(self.tick_label, 0, 0)
        layout.addWidget(self.tick_value, 0, 1)
        
        # ADD
        self.add_label = QLabel("ADD:")
        self.add_value = QLabel("---")
        self.add_label.setStyleSheet(f"color: {COLOR_TEXT};")
        layout.addWidget(self.add_label, 1, 0)
        layout.addWidget(self.add_value, 1, 1)
        
        # VOLD
        self.vold_label = QLabel("VOLD:")
        self.vold_value = QLabel("---")
        self.vold_label.setStyleSheet(f"color: {COLOR_TEXT};")
        layout.addWidget(self.vold_label, 2, 0)
        layout.addWidget(self.vold_value, 2, 1)
        
        # VIX Level
        self.vix_label = QLabel("VIX Level:")
        self.vix_indicator = QLabel("---")
        layout.addWidget(self.vix_label, 3, 0)
        layout.addWidget(self.vix_indicator, 3, 1)
        
        self.setLayout(layout)


class PositionsTableWidget(QTableWidget):
    """Options positions table widget."""
    
    def __init__(self, position_type: str):
        super().__init__()
        self.position_type = position_type
        self.setup_ui()
        
    def setup_ui(self):
        """Setup positions table UI."""
        # Table configuration
        headers = [
            'Strategy', 'Symbol', 'Strikes', 'Expiry', 'Contracts',
            'Entry', 'Current', 'P&L', 'P&L%', 'Delta', 'Theta',
            'IV', 'Time Left', 'Action'
        ]
        
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)
        
        # Styling
        self.setStyleSheet(f"""
            QTableWidget {{
                background-color: {COLOR_PANEL};
                color: {COLOR_TEXT};
                border: 1px solid {COLOR_BORDER};
                gridline-color: {COLOR_BORDER};
            }}
            QHeaderView::section {{
                background-color: #2a2a2a;
                color: {COLOR_TEXT};
                border: 1px solid {COLOR_BORDER};
                padding: 3px;
            }}
        """)
        
        # Column widths
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setVisible(False)
        
        # Enable sorting
        self.setSortingEnabled(True)


# ==============================================================================
# MAIN DASHBOARD
# ==============================================================================
class SpyderFullScreenDashboard(QMainWindow):
    """Full-screen trading dashboard for Spyder system."""
    
    # Signals
    position_closed = pyqtSignal(str)  # position_id
    strategy_changed = pyqtSignal(str)  # strategy_name
    
    def __init__(self):
        """Initialize the dashboard."""
        super().__init__()
        # Use the get_logger method from SpyderLogger
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()  # No logger parameter needed
        
        # Data storage
        self.ticker_data: Dict[str, TickerData] = {}
        self.positions: Dict[str, List[OptionPosition]] = {
            'staged': [],
            'active': [],
            'closed': []
        }
        self.test_prices = {}  # Store original prices for reference
        
        # UI components
        self.ticker_widgets: Dict[str, TickerWidget] = {}
        
        # Setup
        self.setup_ui()
        self.setup_timers()
        self.setup_shortcuts()
        
        # Initialize with test data
        self.load_test_data()
        
    def setup_ui(self):
        """Setup the main UI."""
        self.setWindowTitle("SPYDER Trading Dashboard - Full Screen")
        self.setGeometry(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT)
        
        # Allow window to be closed and minimized even in fullscreen
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        
        # Set dark theme
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {COLOR_BACKGROUND};
            }}
            QLabel {{
                color: {COLOR_TEXT};
            }}
            QPushButton {{
                background-color: #2a2a2a;
                color: {COLOR_TEXT};
                border: 1px solid {COLOR_BORDER};
                padding: 5px;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                background-color: #3a3a3a;
            }}
        """)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # Top panel - Ticker ribbon and controls
        top_panel = self.create_top_panel()
        main_layout.addWidget(top_panel, 1)  # 10% height
        
        # Middle section - Main content
        middle_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel - Positions
        left_panel = self.create_left_panel()
        middle_splitter.addWidget(left_panel)
        
        # Center panel - Chart
        center_panel = self.create_center_panel()
        middle_splitter.addWidget(center_panel)
        
        # Right panel - Strategy & Risk
        right_panel = self.create_right_panel()
        middle_splitter.addWidget(right_panel)
        
        # Set splitter sizes (30%, 45%, 25%)
        middle_splitter.setSizes([576, 864, 480])
        
        main_layout.addWidget(middle_splitter, 8)  # 80% height
        
        # Bottom panel - System status and logs
        bottom_panel = self.create_bottom_panel()
        main_layout.addWidget(bottom_panel, 1)  # 10% height
        
        central_widget.setLayout(main_layout)
        
    def create_top_panel(self) -> QWidget:
        """Create top panel with tickers, market internals, and window controls."""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        # Window controls bar
        controls_bar = QWidget()
        controls_bar.setMaximumHeight(30)
        controls_bar.setStyleSheet(f"""
            QWidget {{
                background-color: #1a1a1a;
                border-bottom: 1px solid {COLOR_BORDER};
            }}
        """)
        
        controls_layout = QHBoxLayout(controls_bar)
        controls_layout.setContentsMargins(10, 2, 10, 2)
        
        # Left side - Title
        title_label = QLabel("SPYDER Trading Dashboard")
        title_label.setStyleSheet(f"""
            QLabel {{
                color: {COLOR_TEXT};
                font-weight: bold;
                font-size: 12px;
            }}
        """)
        
        # Right side - Window controls
        window_controls = QWidget()
        controls_btn_layout = QHBoxLayout(window_controls)
        controls_btn_layout.setContentsMargins(0, 0, 0, 0)
        controls_btn_layout.setSpacing(5)
        
        # Toggle fullscreen button
        self.fullscreen_btn = QPushButton("⛶")
        self.fullscreen_btn.setMaximumSize(25, 25)
        self.fullscreen_btn.setToolTip("Toggle Fullscreen (F11)")
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        self.fullscreen_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                border: 1px solid #555;
                border-radius: 3px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
        """)
        
        # Minimize button
        minimize_btn = QPushButton("−")
        minimize_btn.setMaximumSize(25, 25)
        minimize_btn.setToolTip("Minimize")
        minimize_btn.clicked.connect(self.showMinimized)
        minimize_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                border: 1px solid #555;
                border-radius: 3px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
        """)
        
        # Close button
        close_btn = QPushButton("×")
        close_btn.setMaximumSize(25, 25)
        close_btn.setToolTip("Close Application (Ctrl+Q)")
        close_btn.clicked.connect(self.close_application)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #d32f2f;
                border: 1px solid #b71c1c;
                border-radius: 3px;
                color: white;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f44336;
            }
        """)
        
        controls_btn_layout.addWidget(self.fullscreen_btn)
        controls_btn_layout.addWidget(minimize_btn)
        controls_btn_layout.addWidget(close_btn)
        
        controls_layout.addWidget(title_label)
        controls_layout.addStretch()
        controls_layout.addWidget(window_controls)
        
        # Main ticker and internals layout
        main_content = QWidget()
        content_layout = QHBoxLayout(main_content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Ticker ribbon
        ticker_layout = QHBoxLayout()
        ticker_layout.setSpacing(5)
        
        for symbol in TICKER_SYMBOLS:
            ticker_widget = TickerWidget(symbol)
            self.ticker_widgets[symbol] = ticker_widget
            ticker_layout.addWidget(ticker_widget)
            
        ticker_container = QWidget()
        ticker_container.setLayout(ticker_layout)
        
        # Market internals
        self.market_internals = MarketInternalsWidget()
        
        # Add to content layout
        content_layout.addWidget(ticker_container, 4)
        content_layout.addWidget(self.market_internals, 1)
        
        # Add to main panel layout
        layout.addWidget(controls_bar)
        layout.addWidget(main_content)
        
        panel.setLayout(layout)
        return panel
        
    def create_left_panel(self) -> QWidget:
        """Create left panel with positions tables."""
        panel = QTabWidget()
        panel.setStyleSheet(f"""
            QTabWidget::pane {{
                background-color: {COLOR_PANEL};
                border: 1px solid {COLOR_BORDER};
            }}
            QTabBar::tab {{
                background-color: #2a2a2a;
                color: {COLOR_TEXT};
                padding: 8px 16px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background-color: #3a3a3a;
            }}
        """)
        
        # Staged positions
        self.staged_table = PositionsTableWidget('staged')
        panel.addTab(self.staged_table, "📋 Staged")
        
        # Active positions
        self.active_table = PositionsTableWidget('active')
        panel.addTab(self.active_table, "📈 Active")
        
        # Closed positions
        self.closed_table = PositionsTableWidget('closed')
        panel.addTab(self.closed_table, "✅ Closed")
        
        return panel
        
    def create_center_panel(self) -> QWidget:
        """Create center panel with SPY chart."""
        panel = QGroupBox("SPY 5-Minute Chart")
        panel.setStyleSheet(f"""
            QGroupBox {{
                color: {COLOR_TEXT};
                background-color: {COLOR_PANEL};
                border: 1px solid {COLOR_BORDER};
                border-radius: 5px;
                font-weight: bold;
                font-size: 14px;
                padding-top: 10px;
            }}
        """)
        
        layout = QVBoxLayout()
        
        # Chart controls
        controls_layout = QHBoxLayout()
        
        # Indicator buttons
        self.vwap_btn = QPushButton("VWAP")
        self.vwap_btn.setCheckable(True)
        self.vwap_btn.setChecked(True)
        
        self.ema20_btn = QPushButton("EMA 20")
        self.ema20_btn.setCheckable(True)
        self.ema20_btn.setChecked(True)
        
        self.ema50_btn = QPushButton("EMA 50")
        self.ema50_btn.setCheckable(True)
        self.ema50_btn.setChecked(True)
        
        self.volume_btn = QPushButton("Volume Profile")
        self.volume_btn.setCheckable(True)
        
        controls_layout.addWidget(QLabel("Indicators:"))
        controls_layout.addWidget(self.vwap_btn)
        controls_layout.addWidget(self.ema20_btn)
        controls_layout.addWidget(self.ema50_btn)
        controls_layout.addWidget(self.volume_btn)
        controls_layout.addStretch()
        
        # Chart setup with matplotlib
        self.figure = Figure(figsize=(10, 6), facecolor=COLOR_PANEL)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setStyleSheet(f"background-color: {COLOR_PANEL};")
        
        # Setup the chart
        self.setup_chart()
        
        layout.addLayout(controls_layout)
        layout.addWidget(self.canvas)
        
        panel.setLayout(layout)
        return panel
        
    def create_right_panel(self) -> QWidget:
        """Create right panel with strategy and risk metrics."""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(5)
        
        # Active strategy
        strategy_group = QGroupBox("Active Strategy")
        strategy_group.setStyleSheet(f"""
            QGroupBox {{
                color: {COLOR_TEXT};
                background-color: {COLOR_PANEL};
                border: 1px solid {COLOR_BORDER};
                border-radius: 5px;
                font-weight: bold;
                padding-top: 10px;
            }}
        """)
        
        strategy_layout = QVBoxLayout()
        self.strategy_label = QLabel("Iron Condor - Range Bound")
        self.strategy_label.setStyleSheet("font-size: 16px; color: #00ff41;")
        self.regime_label = QLabel("Market Regime: Low Volatility")
        strategy_layout.addWidget(self.strategy_label)
        strategy_layout.addWidget(self.regime_label)
        strategy_group.setLayout(strategy_layout)
        
        # Risk gauges
        risk_group = QGroupBox("Risk Metrics")
        risk_group.setStyleSheet(f"""
            QGroupBox {{
                color: {COLOR_TEXT};
                background-color: {COLOR_PANEL};
                border: 1px solid {COLOR_BORDER};
                border-radius: 5px;
                font-weight: bold;
                padding-top: 10px;
            }}
        """)
        
        risk_layout = QGridLayout()
        
        # Portfolio Greeks
        self.delta_gauge = self.create_risk_gauge("Portfolio Delta", 0.15, -1, 1)
        self.theta_gauge = self.create_risk_gauge("Theta Decay", -45.5, -100, 0)
        self.vega_gauge = self.create_risk_gauge("Vega Risk", -125, -500, 500)
        self.max_loss_gauge = self.create_risk_gauge("Max Loss", -2500, -5000, 0)
        
        risk_layout.addWidget(self.delta_gauge, 0, 0)
        risk_layout.addWidget(self.theta_gauge, 1, 0)
        risk_layout.addWidget(self.vega_gauge, 2, 0)
        risk_layout.addWidget(self.max_loss_gauge, 3, 0)
        
        risk_group.setLayout(risk_layout)
        
        # Performance metrics
        perf_group = QGroupBox("Today's Performance")
        perf_group.setStyleSheet(f"""
            QGroupBox {{
                color: {COLOR_TEXT};
                background-color: {COLOR_PANEL};
                border: 1px solid {COLOR_BORDER};
                border-radius: 5px;
                font-weight: bold;
                padding-top: 10px;
            }}
        """)
        
        perf_layout = QGridLayout()
        
        self.total_pnl_label = QLabel("Total P&L:")
        self.total_pnl_value = QLabel("$1,245.00")
        self.total_pnl_value.setStyleSheet(f"color: {COLOR_POSITIVE}; font-size: 18px; font-weight: bold;")
        
        self.win_rate_label = QLabel("Win Rate:")
        self.win_rate_value = QLabel("75% (6/8)")
        
        self.avg_win_label = QLabel("Avg Win:")
        self.avg_win_value = QLabel("$287.50")
        self.avg_win_value.setStyleSheet(f"color: {COLOR_POSITIVE};")
        
        self.avg_loss_label = QLabel("Avg Loss:")
        self.avg_loss_value = QLabel("$125.00")
        self.avg_loss_value.setStyleSheet(f"color: {COLOR_NEGATIVE};")
        
        perf_layout.addWidget(self.total_pnl_label, 0, 0)
        perf_layout.addWidget(self.total_pnl_value, 0, 1)
        perf_layout.addWidget(self.win_rate_label, 1, 0)
        perf_layout.addWidget(self.win_rate_value, 1, 1)
        perf_layout.addWidget(self.avg_win_label, 2, 0)
        perf_layout.addWidget(self.avg_win_value, 2, 1)
        perf_layout.addWidget(self.avg_loss_label, 3, 0)
        perf_layout.addWidget(self.avg_loss_value, 3, 1)
        
        perf_group.setLayout(perf_layout)
        
        # Add all groups
        layout.addWidget(strategy_group)
        layout.addWidget(risk_group)
        layout.addWidget(perf_group)
        layout.addStretch()
        
        panel.setLayout(layout)
        return panel
        
    def create_bottom_panel(self) -> QWidget:
        """Create bottom panel with system status and logs."""
        panel = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # System status
        status_group = QGroupBox("System Status")
        status_group.setStyleSheet(f"""
            QGroupBox {{
                color: {COLOR_TEXT};
                background-color: {COLOR_PANEL};
                border: 1px solid {COLOR_BORDER};
                border-radius: 5px;
                font-weight: bold;
                padding-top: 10px;
            }}
        """)
        
        status_layout = QHBoxLayout()
        
        # Connection indicators
        self.ib_status = QLabel("IB Gateway: Connected")
        self.ib_status.setStyleSheet(f"color: {COLOR_POSITIVE};")
        
        self.data_status = QLabel("Market Data: Live")
        self.data_status.setStyleSheet(f"color: {COLOR_POSITIVE};")
        
        self.strategy_status = QLabel("Strategy: Running")
        self.strategy_status.setStyleSheet(f"color: {COLOR_POSITIVE};")
        
        status_layout.addWidget(self.ib_status)
        status_layout.addWidget(QLabel("|"))
        status_layout.addWidget(self.data_status)
        status_layout.addWidget(QLabel("|"))
        status_layout.addWidget(self.strategy_status)
        status_layout.addStretch()
        
        status_group.setLayout(status_layout)
        
        # Logs
        logs_group = QGroupBox("System Logs")
        logs_group.setStyleSheet(f"""
            QGroupBox {{
                color: {COLOR_TEXT};
                background-color: {COLOR_PANEL};
                border: 1px solid {COLOR_BORDER};
                border-radius: 5px;
                font-weight: bold;
                padding-top: 10px;
            }}
        """)
        
        logs_layout = QVBoxLayout()
        
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setMaximumHeight(100)
        self.log_display.setStyleSheet(f"""
            QTextEdit {{
                background-color: #0a0a0a;
                color: {COLOR_TEXT};
                border: 1px solid {COLOR_BORDER};
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11px;
            }}
        """)
        
        # Add sample logs
        self.add_log("System initialized successfully", "INFO")
        self.add_log("Connected to IB Gateway", "SUCCESS")
        self.add_log("Market data feed active", "SUCCESS")
        self.add_log("Iron Condor strategy activated", "INFO")
        
        logs_layout.addWidget(self.log_display)
        logs_group.setLayout(logs_layout)
        
        # Add to main layout
        layout.addWidget(status_group, 1)
        layout.addWidget(logs_group, 2)
        
        panel.setLayout(layout)
        return panel
        
    def create_risk_gauge(self, label: str, value: float, min_val: float, max_val: float) -> QWidget:
        """Create a risk gauge widget."""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Label
        label_widget = QLabel(label)
        label_widget.setStyleSheet(f"color: {COLOR_TEXT}; font-weight: bold;")
        
        # Value
        value_widget = QLabel(f"{value:+.1f}")
        if value > 0:
            color = COLOR_POSITIVE if "Theta" not in label else COLOR_NEGATIVE
        else:
            color = COLOR_NEGATIVE if "Theta" not in label else COLOR_POSITIVE
        value_widget.setStyleSheet(f"color: {color}; font-size: 16px; font-weight: bold;")
        
        # Progress bar
        progress = QProgressBar()
        progress.setMinimum(int(min_val * 100))
        progress.setMaximum(int(max_val * 100))
        progress.setValue(int(value * 100))
        progress.setTextVisible(False)
        progress.setMaximumHeight(10)
        progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: #2a2a2a;
                border: 1px solid {COLOR_BORDER};
                border-radius: 5px;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 5px;
            }}
        """)
        
        layout.addWidget(label_widget)
        layout.addWidget(value_widget)
        layout.addWidget(progress)
        layout.setSpacing(2)
        
        widget.setLayout(layout)
        return widget
        
    def setup_chart(self):
        """Setup the SPY chart with matplotlib."""
        self.figure.clear()
        
        # Create subplot with dark background
        self.ax = self.figure.add_subplot(111)
        self.ax.set_facecolor('#0a0a0a')
        self.figure.patch.set_facecolor(COLOR_PANEL)
        
        # Style the chart
        self.ax.spines['bottom'].set_color(COLOR_TEXT)
        self.ax.spines['top'].set_color(COLOR_TEXT)
        self.ax.spines['left'].set_color(COLOR_TEXT)
        self.ax.spines['right'].set_color(COLOR_TEXT)
        self.ax.tick_params(colors=COLOR_TEXT)
        self.ax.xaxis.label.set_color(COLOR_TEXT)
        self.ax.yaxis.label.set_color(COLOR_TEXT)
        
        # Generate test candlestick data
        times = []
        opens = []
        highs = []
        lows = []
        closes = []
        
        base_price = 585.0
        current_time = datetime.now()
        
        for i in range(78):  # 78 5-minute candles
            time_point = current_time - timedelta(minutes=(78-i)*5)
            times.append(time_point)
            
            # Generate OHLC
            open_price = base_price + (i % 5) * 0.1
            high_price = open_price + 0.3
            low_price = open_price - 0.2
            close_price = open_price + 0.1
            
            opens.append(open_price)
            highs.append(high_price)
            lows.append(low_price)
            closes.append(close_price)
            
            base_price = close_price
        
        # Plot candlesticks
        for i in range(len(times)):
            color = COLOR_POSITIVE if closes[i] >= opens[i] else COLOR_NEGATIVE
            # High-Low line
            self.ax.plot([times[i], times[i]], [lows[i], highs[i]], 
                        color=color, linewidth=1)
            # Body
            height = abs(closes[i] - opens[i])
            bottom = min(closes[i], opens[i])
            rect = Rectangle((mdates.date2num(times[i]) - 0.0005, bottom), 
                           0.001, height, facecolor=color, edgecolor=color)
            self.ax.add_patch(rect)
        
        # Add VWAP line (simulated)
        vwap = [sum(closes[:i+1])/(i+1) for i in range(len(closes))]
        self.ax.plot(times, vwap, color='#00ffff', linewidth=2, label='VWAP')
        
        # Add EMA lines (simulated)
        self.ax.plot(times, [base_price - 0.5] * len(times), 
                    color='#ffff00', linewidth=1, label='EMA 20')
        self.ax.plot(times, [base_price - 1.0] * len(times), 
                    color='#ff00ff', linewidth=1, label='EMA 50')
        
        # Format x-axis
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        self.ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=30))
        self.figure.autofmt_xdate()
        
        # Labels and legend
        self.ax.set_xlabel('Time', color=COLOR_TEXT)
        self.ax.set_ylabel('Price ($)', color=COLOR_TEXT)
        self.ax.set_title('SPY 5-Minute Chart', color=COLOR_TEXT, fontsize=14)
        self.ax.legend(loc='upper left', facecolor=COLOR_PANEL, edgecolor=COLOR_BORDER)
        self.ax.grid(True, alpha=0.2, color=COLOR_BORDER)
        
        self.figure.tight_layout()
        self.canvas.draw()
        
    def setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        # F11 - Toggle fullscreen
        self.fullscreen_shortcut = QShortcut(QKeySequence("F11"), self)
        self.fullscreen_shortcut.activated.connect(self.toggle_fullscreen)
        
        # ESC - Exit fullscreen (not close app)
        self.escape_shortcut = QShortcut(QKeySequence("Escape"), self)
        self.escape_shortcut.activated.connect(self.exit_fullscreen)
        
        # Ctrl+Q - Close application
        self.quit_shortcut = QShortcut(QKeySequence("Ctrl+Q"), self)
        self.quit_shortcut.activated.connect(self.close_application)
        
        # Alt+F4 - Close application (Windows standard)
        self.alt_f4_shortcut = QShortcut(QKeySequence("Alt+F4"), self)
        self.alt_f4_shortcut.activated.connect(self.close_application)
        
    def toggle_fullscreen(self):
        """Toggle between fullscreen and windowed mode."""
        if self.isFullScreen():
            self.showNormal()
            self.fullscreen_btn.setText("⛶")
            self.fullscreen_btn.setToolTip("Enter Fullscreen (F11)")
            self.add_log("Exited fullscreen mode", "INFO")
        else:
            self.showFullScreen()
            self.fullscreen_btn.setText("⛷")
            self.fullscreen_btn.setToolTip("Exit Fullscreen (F11)")
            self.add_log("Entered fullscreen mode", "INFO")
            
    def exit_fullscreen(self):
        """Exit fullscreen mode (ESC key behavior)."""
        if self.isFullScreen():
            self.showNormal()
            self.fullscreen_btn.setText("⛶")
            self.fullscreen_btn.setToolTip("Enter Fullscreen (F11)")
            self.add_log("Exited fullscreen mode", "INFO")
            
    def close_application(self):
        """Close the application with confirmation."""
        reply = QMessageBox.question(
            self,
            'Confirm Exit',
            'Are you sure you want to exit SPYDER Dashboard?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.add_log("Closing SPYDER Dashboard", "INFO")
            self.close()
        
    def setup_timers(self):
        """Setup update timers."""
        # Ticker updates
        self.ticker_timer = QTimer()
        self.ticker_timer.timeout.connect(self.update_tickers)
        self.ticker_timer.start(TICKER_UPDATE_MS)
        
        # Position updates
        self.position_timer = QTimer()
        self.position_timer.timeout.connect(self.update_positions)
        self.position_timer.start(POSITION_UPDATE_MS)
        
        # Chart updates
        self.chart_timer = QTimer()
        self.chart_timer.timeout.connect(self.update_chart)
        self.chart_timer.start(CHART_UPDATE_MS)
        
    def load_test_data(self):
        """Load test data for demonstration."""
        # Initialize ticker data
        self.test_prices = {
            'SPY': 585.25, 'SPX': 5850.75, 'VIX': 15.32, 'IWM': 225.18,
            'QQQ': 485.92, 'TLT': 92.45, '/ES': 5852.50, 'DIA': 425.33,
            'GLD': 195.67, 'UVXY': 22.18, 'ES': 5852.50, 'MES': 5852.50,
            'XSP': 585.25, 'NANOS': 20.45
        }
        
        for symbol, price in self.test_prices.items():
            change = (price * 0.01) * (1 if hash(symbol) % 2 == 0 else -1)
            self.ticker_data[symbol] = TickerData(
                symbol=symbol,
                price=price,
                change=change,
                change_pct=(change / price) * 100,
                volume=1000000,
                bid=price - 0.01,
                ask=price + 0.01,
                high=price + 1,
                low=price - 1,
                timestamp=datetime.now()
            )
            
        # Add test positions
        self.add_test_positions()
        
    def add_test_positions(self):
        """Add test option positions."""
        # Staged position
        staged = OptionPosition(
            symbol="SPY",
            strategy="Iron Condor",
            strikes=[580, 582, 588, 590],
            expiry="26JUN24",
            contracts=10,
            entry_price=1.25,
            current_price=1.25,
            pnl=0,
            pnl_pct=0,
            delta=0.02,
            theta=-25.5,
            vega=-85.2,
            gamma=-0.001,
            iv=15.8,
            time_remaining="2d 5h",
            status="staged"
        )
        self.positions['staged'].append(staged)
        
        # Active positions
        active1 = OptionPosition(
            symbol="SPY",
            strategy="Bull Put Spread",
            strikes=[582, 584],
            expiry="24JUN24",
            contracts=20,
            entry_price=0.85,
            current_price=0.42,
            pnl=860,
            pnl_pct=50.6,
            delta=0.15,
            theta=-18.2,
            vega=-42.5,
            gamma=-0.003,
            iv=14.2,
            time_remaining="5h 30m",
            status="active"
        )
        self.positions['active'].append(active1)
        
        # Update tables
        self.update_positions()
        
    def update_tickers(self):
        """Update ticker displays."""
        for symbol, widget in self.ticker_widgets.items():
            if symbol in self.ticker_data:
                # Simulate price movement
                data = self.ticker_data[symbol]
                data.price += (0.01 if hash(str(datetime.now())) % 2 == 0 else -0.01)
                data.change = data.price - self.test_prices.get(symbol, data.price)
                data.change_pct = (data.change / self.test_prices.get(symbol, data.price)) * 100
                widget.update_data(data)
                
    def update_positions(self):
        """Update position tables."""
        # Update each table
        for position_type, table in [
            ('staged', self.staged_table),
            ('active', self.active_table),
            ('closed', self.closed_table)
        ]:
            positions = self.positions.get(position_type, [])
            table.setRowCount(len(positions))
            
            for row, pos in enumerate(positions):
                # Strategy
                table.setItem(row, 0, QTableWidgetItem(pos.strategy))
                
                # Symbol
                table.setItem(row, 1, QTableWidgetItem(pos.symbol))
                
                # Strikes
                strikes_str = "/".join([str(s) for s in pos.strikes])
                table.setItem(row, 2, QTableWidgetItem(strikes_str))
                
                # Expiry
                table.setItem(row, 3, QTableWidgetItem(pos.expiry))
                
                # Contracts
                table.setItem(row, 4, QTableWidgetItem(str(pos.contracts)))
                
                # Entry price
                table.setItem(row, 5, QTableWidgetItem(f"${pos.entry_price:.2f}"))
                
                # Current price
                table.setItem(row, 6, QTableWidgetItem(f"${pos.current_price:.2f}"))
                
                # P&L
                pnl_item = QTableWidgetItem(f"${pos.pnl:+.2f}")
                pnl_item.setForeground(QBrush(QColor(COLOR_POSITIVE if pos.pnl > 0 else COLOR_NEGATIVE)))
                table.setItem(row, 7, pnl_item)
                
                # P&L %
                pnl_pct_item = QTableWidgetItem(f"{pos.pnl_pct:+.1f}%")
                pnl_pct_item.setForeground(QBrush(QColor(COLOR_POSITIVE if pos.pnl_pct > 0 else COLOR_NEGATIVE)))
                table.setItem(row, 8, pnl_pct_item)
                
                # Greeks
                table.setItem(row, 9, QTableWidgetItem(f"{pos.delta:.3f}"))
                table.setItem(row, 10, QTableWidgetItem(f"{pos.theta:.2f}"))
                
                # IV
                table.setItem(row, 11, QTableWidgetItem(f"{pos.iv:.1f}%"))
                
                # Time remaining
                table.setItem(row, 12, QTableWidgetItem(pos.time_remaining))
                
                # Action button
                if position_type == 'active':
                    close_btn = QPushButton("Close")
                    close_btn.clicked.connect(lambda checked, r=row: self.close_position(r))
                    table.setCellWidget(row, 13, close_btn)
                    
    def update_chart(self):
        """Update chart data."""
        # In production, this would fetch real-time data
        pass
        
    def close_position(self, position_id: int):
        """Close a position."""
        self.logger.info(f"Closing position {position_id}")
        # Implementation would close the actual position
        
    def add_log(self, message: str, level: str = "INFO"):
        """Add a log entry."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Color based on level
        if level == "SUCCESS":
            color = COLOR_POSITIVE
        elif level == "ERROR":
            color = COLOR_NEGATIVE
        elif level == "WARNING":
            color = COLOR_WARNING
        else:
            color = COLOR_TEXT
            
        log_html = f'<span style="color: {color};">[{timestamp}] {message}</span>'
        self.log_display.append(log_html)
        
        # Keep only last 100 lines
        cursor = self.log_display.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.log_display.setTextCursor(cursor)


# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================
def main():
    """Main entry point for the dashboard."""
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    # Create and show dashboard
    dashboard = SpyderFullScreenDashboard()
    dashboard.showFullScreen()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
