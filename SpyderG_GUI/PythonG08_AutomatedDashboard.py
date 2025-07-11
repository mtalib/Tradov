#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderG08_AutomatedDashboard.py
Group: G (GUI/User Interface)
Purpose: Fully automated trading dashboard - 1920x1080 optimized

Description:
    This module provides a monitoring-only dashboard for the fully automated
    Spyder trading system. It displays market data, positions, risk metrics,
    and system status without manual intervention controls. The interface is
    designed for occasional check-ins rather than active management.

Author: Claude
Date: 2024-12-30
Version: 1.0
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import random
import numpy as np

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
    QFont, QPalette, QColor, QIcon, QPixmap, QPainter, QBrush, 
    QShortcut, QKeySequence, QPen
)

# Matplotlib for charting
import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import mplfinance as mpf
import pandas as pd

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Window dimensions
WINDOW_WIDTH = 1920
WINDOW_HEIGHT = 1080

# Panel widths
LEFT_PANEL_WIDTH = 400
CENTER_PANEL_WIDTH = 920
RIGHT_PANEL_WIDTH = 600

# Market symbols organized by category
MARKET_SYMBOLS = {
    'S&P ETF & Indices': ['SPY', 'SPX', 'XSP', 'NANOS'],
    'S&P Futures': ['/SP', '/ES', '/MES'],
    'Volatility': ['VIX', 'VIX9D', 'VIX3M', 'VIX6M', 'VIX1Y', 'UVXY', 'CPC'],
    'Major ETFs': ['DIA', 'QQQ', 'IWM'],
    'Treasury/Bonds': ['TLT', 'IEF', 'HYG', 'DXY'],
    'Commodities': ['GLD', 'USO', 'DBC']
}

# Update intervals
FAST_UPDATE_MS = 1000   # SPY, ES - 1 second
SLOW_UPDATE_MS = 5000   # Other symbols - 5 seconds
CHART_UPDATE_MS = 2000  # Chart - 2 seconds

# Color scheme
COLORS = {
    'background': '#0a0a0a',
    'panel': '#1a1a1a',
    'border': '#333333',
    'text': '#ffffff',
    'text_dim': '#888888',
    'positive': '#00ff41',
    'negative': '#ff1744',
    'neutral': '#ffd700',
    'warning': '#ff9800',
    'automation_active': '#00b8d4',
    'grid': '#2a2a2a'
}

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class MarketData:
    """Market data for symbols"""
    symbol: str
    last: float
    change: float
    change_pct: float
    timestamp: datetime

@dataclass
class PositionData:
    """Position information"""
    date: str
    symbol: str
    contracts: int
    strikes: str
    expiry: str
    strategy: str
    status: str
    cost: float
    pnl: float
    auto_status: str  # Automation status

@dataclass
class GreekRisk:
    """Portfolio Greeks"""
    delta: float
    gamma: float
    theta: float
    vega: float
    
# ==============================================================================
# CUSTOM WIDGETS
# ==============================================================================
class MarketSymbolWidget(QWidget):
    """Widget for displaying a single market symbol"""
    
    def __init__(self, symbol: str, category: str):
        super().__init__()
        self.symbol = symbol
        self.category = category
        self.setup_ui()
        
    def setup_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)
        
        # Symbol label
        self.symbol_label = QLabel(self.symbol)
        self.symbol_label.setStyleSheet(f"color: {COLORS['text']}; font-weight: bold;")
        self.symbol_label.setFixedWidth(60)
        
        # Price label
        self.price_label = QLabel("---.--")
        self.price_label.setStyleSheet(f"color: {COLORS['text']};")
        self.price_label.setFixedWidth(80)
        self.price_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        
        # Change label
        self.change_label = QLabel("+0.00")
        self.change_label.setFixedWidth(60)
        self.change_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        
        # Percent label
        self.pct_label = QLabel("0.00%")
        self.pct_label.setFixedWidth(60)
        self.pct_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        
        layout.addWidget(self.symbol_label)
        layout.addWidget(self.price_label)
        layout.addWidget(self.change_label)
        layout.addWidget(self.pct_label)
        layout.addStretch()
        
        self.setLayout(layout)
        
    def update_data(self, data: MarketData):
        """Update display with new data"""
        self.price_label.setText(f"{data.last:.2f}")
        
        # Color based on change
        color = COLORS['positive'] if data.change >= 0 else COLORS['negative']
        sign = '+' if data.change >= 0 else ''
        
        self.change_label.setText(f"{sign}{data.change:.2f}")
        self.change_label.setStyleSheet(f"color: {color};")
        
        self.pct_label.setText(f"{sign}{data.change_pct:.2f}%")
        self.pct_label.setStyleSheet(f"color: {color};")

class GreekBar(QWidget):
    """Custom widget for Greek risk display with automation status"""
    
    def __init__(self, name: str, min_val: float, max_val: float):
        super().__init__()
        self.name = name
        self.min_val = min_val
        self.max_val = max_val
        self.current_val = 0
        self.percentage = 0
        self.status = "NORMAL"
        self.setFixedHeight(40)
        
    def set_value(self, value: float, status: str = "NORMAL"):
        """Update Greek value and status"""
        self.current_val = value
        self.percentage = abs(value - self.min_val) / (self.max_val - self.min_val)
        self.percentage = min(max(self.percentage, 0), 1)  # Clamp to 0-1
        self.status = status
        self.update()
        
    def paintEvent(self, event):
        """Custom paint for the Greek bar"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Background
        painter.fillRect(self.rect(), QColor(COLORS['panel']))
        
        # Bar background
        bar_rect = QRect(10, 10, self.width() - 100, 20)
        painter.fillRect(bar_rect, QColor(COLORS['background']))
        
        # Determine color based on percentage
        if self.percentage < 0.6:
            color = QColor(COLORS['positive'])
        elif self.percentage < 0.8:
            color = QColor(COLORS['warning'])
        else:
            color = QColor(COLORS['negative'])
            
        # Fill bar
        fill_width = int(bar_rect.width() * self.percentage)
        fill_rect = QRect(bar_rect.x(), bar_rect.y(), fill_width, bar_rect.height())
        painter.fillRect(fill_rect, color)
        
        # Draw border
        painter.setPen(QPen(QColor(COLORS['border']), 1))
        painter.drawRect(bar_rect)
        
        # Draw text
        painter.setPen(QColor(COLORS['text']))
        font = QFont()
        font.setPointSize(10)
        painter.setFont(font)
        
        # Greek name and value
        text = f"{self.name}: {self.current_val:.2f}"
        painter.drawText(15, 35, text)
        
        # Status text
        painter.setPen(QColor(COLORS['automation_active']))
        painter.drawText(self.width() - 200, 25, f"[{self.status}]")

# ==============================================================================
# MAIN DASHBOARD
# ==============================================================================
class AutomatedTradingDashboard(QMainWindow):
    """Main automated trading dashboard window"""
    
    def __init__(self):
        super().__init__()
        self.market_data = {}
        self.positions = []
        self.greek_risks = GreekRisk(45.5, -2.3, -156.8, -245.2)
        self.setup_ui()
        self.setup_timers()
        self.load_test_data()
        
    def setup_ui(self):
        """Setup the user interface"""
        self.setWindowTitle("SPYDER - Automated Trading Dashboard")
        self.setGeometry(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT)
        
        # Set dark theme
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {COLORS['background']};
            }}
            QLabel {{
                color: {COLORS['text']};
            }}
            QGroupBox {{
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }}
            QPushButton {{
                background-color: {COLORS['panel']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                padding: 8px;
                border-radius: 3px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #2a2a2a;
            }}
            QTableWidget {{
                background-color: {COLORS['panel']};
                alternate-background-color: {COLORS['background']};
                color: {COLORS['text']};
                gridline-color: {COLORS['grid']};
                border: 1px solid {COLORS['border']};
            }}
            QHeaderView::section {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                padding: 5px;
            }}
            QTextEdit {{
                background-color: {COLORS['panel']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
            }}
        """)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # Top toolbar
        toolbar = self.create_toolbar()
        main_layout.addWidget(toolbar)
        
        # Main content splitter
        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel - Market Overview
        left_panel = self.create_left_panel()
        content_splitter.addWidget(left_panel)
        
        # Center panel - Trading Focus
        center_panel = self.create_center_panel()
        content_splitter.addWidget(center_panel)
        
        # Right panel - Account & Risk
        right_panel = self.create_right_panel()
        content_splitter.addWidget(right_panel)
        
        # Set panel sizes
        content_splitter.setSizes([LEFT_PANEL_WIDTH, CENTER_PANEL_WIDTH, RIGHT_PANEL_WIDTH])
        
        main_layout.addWidget(content_splitter)
        
        central_widget.setLayout(main_layout)
        
    def create_toolbar(self) -> QWidget:
        """Create top toolbar with system controls"""
        toolbar = QWidget()
        toolbar.setFixedHeight(60)
        toolbar.setStyleSheet(f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']};")
        
        layout = QHBoxLayout()
        
        # System info
        info_label = QLabel("SPYDER 2024-12-30 13:30:45 EST")
        info_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(info_label)
        
        # Connection status
        self.connection_label = QLabel("IB CONNECTED")
        self.connection_label.setStyleSheet(f"color: {COLORS['positive']}; font-weight: bold;")
        layout.addWidget(self.connection_label)
        
        # Market indices
        self.dow_label = QLabel("DOW +2.3% 43,900.42 +350.35")
        self.dow_label.setStyleSheet(f"color: {COLORS['positive']};")
        layout.addWidget(self.dow_label)
        
        self.sp_label = QLabel("S&P 500 +1.2% 6,876.23 +45.43")
        self.sp_label.setStyleSheet(f"color: {COLORS['positive']};")
        layout.addWidget(self.sp_label)
        
        self.nasdaq_label = QLabel("NASDAQ +0.78% 20,275.62 +45.23")
        self.nasdaq_label.setStyleSheet(f"color: {COLORS['positive']};")
        layout.addWidget(self.nasdaq_label)
        
        layout.addStretch()
        
        # System controls
        self.start_btn = QPushButton("START SYSTEM")
        self.start_btn.setStyleSheet(f"background-color: {COLORS['positive']}; color: black;")
        self.start_btn.setFixedWidth(120)
        layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("STOP SYSTEM")
        self.stop_btn.setFixedWidth(120)
        layout.addWidget(self.stop_btn)
        
        self.emergency_btn = QPushButton("EMERGENCY CLOSE ALL")
        self.emergency_btn.setStyleSheet(f"background-color: {COLORS['negative']};")
        self.emergency_btn.setFixedWidth(150)
        layout.addWidget(self.emergency_btn)
        
        toolbar.setLayout(layout)
        return toolbar
        
    def create_left_panel(self) -> QWidget:
        """Create left panel with market overview"""
        panel = QGroupBox("MARKET OVERVIEW")
        layout = QVBoxLayout()
        
        # Header
        header = QWidget()
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(5, 0, 5, 0)
        
        # Column headers
        header_layout.addWidget(QLabel("SYMBOL"))
        header_layout.addWidget(QLabel("LAST"))
        header_layout.addWidget(QLabel("CHG"))
        header_layout.addWidget(QLabel("CHG%"))
        header.setLayout(header_layout)
        
        # Style headers
        for i in range(header_layout.count()):
            widget = header_layout.itemAt(i).widget()
            if widget:
                widget.setStyleSheet(f"color: {COLORS['text_dim']}; font-weight: bold;")
                if i == 0:
                    widget.setFixedWidth(60)
                elif i == 1:
                    widget.setFixedWidth(80)
                    widget.setAlignment(Qt.AlignmentFlag.AlignRight)
                else:
                    widget.setFixedWidth(60)
                    widget.setAlignment(Qt.AlignmentFlag.AlignRight)
        
        layout.addWidget(header)
        
        # Add separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"color: {COLORS['border']};")
        layout.addWidget(separator)
        
        # Scroll area for symbols
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()
        scroll_layout.setSpacing(1)
        
        # Create symbol widgets
        self.symbol_widgets = {}
        for category, symbols in MARKET_SYMBOLS.items():
            # Category header
            cat_label = QLabel(category)
            cat_label.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px; padding: 5px 0px 2px 0px;")
            scroll_layout.addWidget(cat_label)
            
            # Symbol widgets
            for symbol in symbols:
                widget = MarketSymbolWidget(symbol, category)
                self.symbol_widgets[symbol] = widget
                scroll_layout.addWidget(widget)
                
        scroll_layout.addStretch()
        scroll_widget.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; }")
        
        layout.addWidget(scroll_area)
        panel.setLayout(layout)
        return panel
        
    def create_center_panel(self) -> QWidget:
        """Create center panel with chart and positions"""
        panel = QWidget()
        layout = QVBoxLayout()
        
        # Market regime indicator
        regime_widget = QWidget()
        regime_widget.setStyleSheet(f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']};")
        regime_widget.setFixedHeight(40)
        regime_layout = QHBoxLayout()
        
        regime_label = QLabel("MARKET REGIME: Low Volatility - Range Bound")
        regime_label.setStyleSheet("font-weight: bold;")
        regime_layout.addWidget(regime_label)
        
        strategy_label = QLabel("CURRENT ACTIVE STRATEGY: Iron Condor")
        strategy_label.setStyleSheet(f"color: {COLORS['automation_active']}; font-weight: bold;")
        regime_layout.addWidget(strategy_label)
        
        regime_widget.setLayout(regime_layout)
        layout.addWidget(regime_widget)
        
        # Chart
        self.create_chart()
        layout.addWidget(self.chart_widget, 3)  # 60% of space
        
        # Positions table
        positions_group = QGroupBox("ORDERS & POSITIONS: STAGED-ACTIVE-CLOSED")
        positions_layout = QVBoxLayout()
        
        self.positions_table = self.create_positions_table()
        positions_layout.addWidget(self.positions_table)
        
        positions_group.setLayout(positions_layout)
        layout.addWidget(positions_group, 2)  # 40% of space
        
        panel.setLayout(layout)
        return panel
        
    def create_chart(self):
        """Create the SPY chart widget"""
        self.chart_widget = QWidget()
        self.chart_widget.setStyleSheet(f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']};")
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create matplotlib figure
        self.figure = Figure(figsize=(10, 6), dpi=100)
        self.figure.patch.set_facecolor(COLORS['panel'])
        
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setStyleSheet("background-color: transparent;")
        layout.addWidget(self.canvas)
        
        self.chart_widget.setLayout(layout)
        
        # Initial empty chart
        self.update_chart()
        
    def create_positions_table(self) -> QTableWidget:
        """Create positions table"""
        table = QTableWidget()
        
        # Columns
        columns = ["DATE", "SYMBOL", "CONTRACTS", "STRIKES", "EXPIRY", 
                  "STRATEGY", "STATUS", "COST", "P&L", "AUTO STATUS"]
        
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(columns)
        
        # Configure table
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        header = table.horizontalHeader()
        header.setStretchLastSection(True)
        
        # Set column widths
        table.setColumnWidth(0, 80)   # DATE
        table.setColumnWidth(1, 60)   # SYMBOL
        table.setColumnWidth(2, 80)   # CONTRACTS
        table.setColumnWidth(3, 120)  # STRIKES
        table.setColumnWidth(4, 80)   # EXPIRY
        table.setColumnWidth(5, 120)  # STRATEGY
        table.setColumnWidth(6, 80)   # STATUS
        table.setColumnWidth(7, 80)   # COST
        table.setColumnWidth(8, 80)   # P&L
        table.setColumnWidth(9, 120)  # AUTO STATUS
        
        # Set row height
        table.verticalHeader().setDefaultSectionSize(25)
        
        return table
        
    def create_right_panel(self) -> QWidget:
        """Create right panel with account info and risk metrics"""
        panel = QWidget()
        layout = QVBoxLayout()
        
        # Account info
        account_group = QGroupBox("ACCOUNT: DU5361048 MODE: PAPER")
        account_layout = QVBoxLayout()
        
        # Account metrics
        metrics_widget = QWidget()
        metrics_layout = QGridLayout()
        
        self.account_labels = {
            'settled_cash': QLabel("Settled Cash: $100,000"),
            'unrealized_pnl': QLabel("Unrealized P&L: +$2,450"),
            'realized_pnl': QLabel("Realized P&L: +$5,320"),
            'buying_power': QLabel("Buying Power: $85,000")
        }
        
        # Style and add labels
        row = 0
        for key, label in self.account_labels.items():
            if 'pnl' in key:
                label.setStyleSheet(f"color: {COLORS['positive']};")
            metrics_layout.addWidget(label, row // 2, row % 2)
            row += 1
            
        metrics_widget.setLayout(metrics_layout)
        account_layout.addWidget(metrics_widget)
        
        account_group.setLayout(account_layout)
        layout.addWidget(account_group)
        
        # P&L Performance
        pnl_group = QGroupBox("P&L PERFORMANCE")
        pnl_layout = QVBoxLayout()
        
        self.pnl_table = self.create_pnl_table()
        pnl_layout.addWidget(self.pnl_table)
        
        # Performance metrics
        perf_widget = QWidget()
        perf_layout = QHBoxLayout()
        
        self.profit_factor_label = QLabel("PROFIT FACTOR: 1.85")
        self.sharpe_label = QLabel("SHARPE RATIO: 2.35")
        
        perf_layout.addWidget(self.profit_factor_label)
        perf_layout.addWidget(self.sharpe_label)
        perf_widget.setLayout(perf_layout)
        
        pnl_layout.addWidget(perf_widget)
        pnl_group.setLayout(pnl_layout)
        layout.addWidget(pnl_group)
        
        # Risk Monitor
        risk_group = QGroupBox("PORTFOLIO RISK MONITOR")
        risk_layout = QVBoxLayout()
        
        # Greek bars
        self.greek_bars = {
            'delta': GreekBar("Delta", -100, 100),
            'gamma': GreekBar("Gamma", -10, 10),
            'theta': GreekBar("Theta", -400, 0),
            'vega': GreekBar("Vega", -600, 0)
        }
        
        for bar in self.greek_bars.values():
            risk_layout.addWidget(bar)
            
        risk_group.setLayout(risk_layout)
        layout.addWidget(risk_group)
        
        # Automation Status
        auto_group = QGroupBox("AUTOMATION STATUS")
        auto_layout = QVBoxLayout()
        
        self.auto_log = QTextEdit()
        self.auto_log.setReadOnly(True)
        self.auto_log.setMaximumHeight(100)
        
        # Add sample automation logs
        self.add_auto_log("Position Monitor: ✅ ACTIVE (checking every 30s)")
        self.add_auto_log("Orphan Detector: ✅ NO ISSUES")
        self.add_auto_log("Strategy Health: ✅ ALL STRATEGIES INTACT")
        self.add_auto_log("14:32 - Delta reached 72, hedged with 2 /MES contracts")
        self.add_auto_log("15:45 - Gamma spike detected, closed nearest ATM positions")
        
        auto_layout.addWidget(self.auto_log)
        auto_group.setLayout(auto_layout)
        layout.addWidget(auto_group)
        
        # System Health
        health_group = QGroupBox("SYSTEM HEALTH")
        health_layout = QVBoxLayout()
        
        self.health_indicators = {
            'risk_manager': QLabel("● RISK MANAGER"),
            'market_data': QLabel("● MARKET DATA"),
            'strategy_engine': QLabel("● STRATEGY ENGINE"),
            'ml_models': QLabel("● ML MODELS"),
            'database': QLabel("● DATABASE")
        }
        
        for indicator in self.health_indicators.values():
            indicator.setStyleSheet(f"color: {COLORS['positive']};")
            health_layout.addWidget(indicator)
            
        health_group.setLayout(health_layout)
        layout.addWidget(health_group)
        
        layout.addStretch()
        panel.setLayout(layout)
        return panel
        
    def create_pnl_table(self) -> QTableWidget:
        """Create P&L performance table"""
        table = QTableWidget(5, 4)
        table.setHorizontalHeaderLabels(["PERIOD", "P&L", "WIN RATE%", "AVG WIN/LOSS"])
        
        # Sample data
        periods = ["TODAY", "WEEK", "MONTH", "YEAR", "ALL TIME"]
        data = [
            ("+$850", "75%", "$425 / $120"),
            ("+$3,200", "68%", "$380 / $150"),
            ("+$12,500", "72%", "$450 / $180"),
            ("+$45,000", "70%", "$500 / $200"),
            ("+$125,000", "71%", "$480 / $190")
        ]
        
        for row, (period, values) in enumerate(zip(periods, data)):
            table.setItem(row, 0, QTableWidgetItem(period))
            table.setItem(row, 1, QTableWidgetItem(values[0]))
            table.setItem(row, 2, QTableWidgetItem(values[1]))
            table.setItem(row, 3, QTableWidgetItem(values[2]))
            
            # Color P&L
            pnl_item = table.item(row, 1)
            pnl_item.setForeground(QColor(COLORS['positive']))
            
        # Configure table
        table.verticalHeader().setVisible(False)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setMaximumHeight(150)
        
        return table
        
    def setup_timers(self):
        """Setup update timers"""
        # Fast timer for SPY/ES
        self.fast_timer = QTimer()
        self.fast_timer.timeout.connect(self.update_fast_symbols)
        self.fast_timer.start(FAST_UPDATE_MS)
        
        # Slow timer for other symbols
        self.slow_timer = QTimer()
        self.slow_timer.timeout.connect(self.update_slow_symbols)
        self.slow_timer.start(SLOW_UPDATE_MS)
        
        # Chart timer
        self.chart_timer = QTimer()
        self.chart_timer.timeout.connect(self.update_chart)
        self.chart_timer.start(CHART_UPDATE_MS)
        
        # Position timer
        self.position_timer = QTimer()
        self.position_timer.timeout.connect(self.update_positions)
        self.position_timer.start(2000)
        
    def load_test_data(self):
        """Load test data for demonstration"""
        # Initialize market data
        base_prices = {
            'SPY': 585.25, 'SPX': 5850.75, 'XSP': 585.25, 'NANOS': 20.45,
            '/SP': 5852.00, '/ES': 5852.50, '/MES': 5852.50,
            'VIX': 15.32, 'VIX9D': 14.8, 'VIX3M': 16.2, 'VIX6M': 17.5,
            'VIX1Y': 18.2, 'UVXY': 22.18, 'CPC': 0.85,
            'DIA': 425.33, 'QQQ': 485.92, 'IWM': 225.18,
            'TLT': 92.45, 'IEF': 105.32, 'HYG': 75.83, 'DXY': 103.25,
            'GLD': 195.67, 'USO': 72.15, 'DBC': 22.34
        }
        
        for symbol, price in base_prices.items():
            change = price * (random.random() * 0.04 - 0.02)  # +/- 2%
            self.market_data[symbol] = MarketData(
                symbol=symbol,
                last=price,
                change=change,
                change_pct=(change/price) * 100,
                timestamp=datetime.now()
            )
            
        # Initialize positions
        self.add_test_positions()
        
        # Update initial displays
        self.update_all_symbols()
        self.update_greeks()
        
    def add_test_positions(self):
        """Add test positions"""
        test_positions = [
            PositionData(
                date="12/30",
                symbol="SPY",
                contracts=10,
                strikes="580/582/588/590",
                expiry="31DEC24",
                strategy="Iron Condor",
                status="ACTIVE",
                cost=1250.00,
                pnl=350.00,
                auto_status="MONITORING"
            ),
            PositionData(
                date="12/30",
                symbol="SPY",
                contracts=20,
                strikes="582/584",
                expiry="31DEC24",
                strategy="Bull Put Spread",
                status="ACTIVE",
                cost=1700.00,
                pnl=860.00,
                auto_status="THETA HARVEST"
            ),
            PositionData(
                date="12/30",
                symbol="SPY",
                contracts=5,
                strikes="590/592/594/596",
                expiry="03JAN25",
                strategy="Iron Condor",
                status="STAGED",
                cost=0.00,
                pnl=0.00,
                auto_status="PENDING FILL"
            )
        ]
        
        self.positions = test_positions
        self.update_positions()
        
    def update_fast_symbols(self):
        """Update SPY and ES every second"""
        fast_symbols = ['SPY', '/ES']
        for symbol in fast_symbols:
            if symbol in self.market_data:
                # Simulate price movement
                data = self.market_data[symbol]
                movement = random.random() * 0.2 - 0.1
                data.last += movement
                data.change += movement
                data.change_pct = (data.change / (data.last - data.change)) * 100
                data.timestamp = datetime.now()
                
                # Update widget
                if symbol in self.symbol_widgets:
                    self.symbol_widgets[symbol].update_data(data)
                    
    def update_slow_symbols(self):
        """Update other symbols every 5 seconds"""
        for symbol, data in self.market_data.items():
            if symbol not in ['SPY', '/ES']:
                # Simulate price movement
                movement = random.random() * 0.4 - 0.2
                data.last += movement
                data.change += movement
                data.change_pct = (data.change / (data.last - data.change)) * 100
                data.timestamp = datetime.now()
                
                # Update widget
                if symbol in self.symbol_widgets:
                    self.symbol_widgets[symbol].update_data(data)
                    
    def update_all_symbols(self):
        """Update all symbol displays"""
        for symbol, widget in self.symbol_widgets.items():
            if symbol in self.market_data:
                widget.update_data(self.market_data[symbol])
                
    def update_chart(self):
        """Update the SPY chart"""
        self.figure.clear()
        
        # Create sample OHLC data
        periods = 100
        dates = pd.date_range(end=datetime.now(), periods=periods, freq='5min')
        
        # Generate realistic OHLC data around current SPY price
        spy_price = self.market_data['SPY'].last if 'SPY' in self.market_data else 585
        
        data = []
        current_price = spy_price - 2
        
        for date in dates:
            # Random walk
            change = random.random() * 0.5 - 0.25
            current_price += change
            
            # OHLC
            open_price = current_price
            high = current_price + random.random() * 0.3
            low = current_price - random.random() * 0.3
            close = low + random.random() * (high - low)
            volume = random.randint(1000000, 5000000)
            
            data.append([date, open_price, high, low, close, volume])
            current_price = close
            
        # Create DataFrame
        df = pd.DataFrame(data, columns=['Date', 'Open', 'High', 'Low', 'Close', 'Volume'])
        df.set_index('Date', inplace=True)
        
        # Create subplot with shared x-axis
        ax = self.figure.add_subplot(111)
        
        # Style configuration
        mc = mpf.make_marketcolors(
            up='#00ff41',
            down='#ff1744',
            edge='inherit',
            wick={'up': '#00ff41', 'down': '#ff1744'},
            volume='inherit'
        )
        
        s = mpf.make_mpf_style(
            marketcolors=mc,
            gridstyle='',
            y_on_right=True,
            facecolor=COLORS['panel'],
            edgecolor=COLORS['border'],
            figcolor=COLORS['panel'],
            gridcolor=COLORS['grid']
        )
        
        # Plot candlesticks with volume
        mpf.plot(
            df,
            type='candle',
            style=s,
            volume=True,
            ax=ax,
            volume_panel=1,
            panel_ratios=(3, 1)
        )
        
        # Update title
        ax.set_title('SPY - 5 min', color=COLORS['text'], fontsize=12, pad=10)
        
        # Style axes
        ax.tick_params(colors=COLORS['text'])
        ax.spines['top'].set_color(COLORS['border'])
        ax.spines['bottom'].set_color(COLORS['border'])
        ax.spines['left'].set_color(COLORS['border'])
        ax.spines['right'].set_color(COLORS['border'])
        
        self.canvas.draw()
        
    def update_positions(self):
        """Update positions table"""
        self.positions_table.setRowCount(len(self.positions))
        
        for row, position in enumerate(self.positions):
            # Set items
            self.positions_table.setItem(row, 0, QTableWidgetItem(position.date))
            self.positions_table.setItem(row, 1, QTableWidgetItem(position.symbol))
            self.positions_table.setItem(row, 2, QTableWidgetItem(str(position.contracts)))
            self.positions_table.setItem(row, 3, QTableWidgetItem(position.strikes))
            self.positions_table.setItem(row, 4, QTableWidgetItem(position.expiry))
            self.positions_table.setItem(row, 5, QTableWidgetItem(position.strategy))
            self.positions_table.setItem(row, 6, QTableWidgetItem(position.status))
            self.positions_table.setItem(row, 7, QTableWidgetItem(f"${position.cost:,.2f}"))
            
            # P&L with color
            pnl_item = QTableWidgetItem(f"${position.pnl:+,.2f}")
            if position.pnl > 0:
                pnl_item.setForeground(QColor(COLORS['positive']))
            elif position.pnl < 0:
                pnl_item.setForeground(QColor(COLORS['negative']))
            self.positions_table.setItem(row, 8, pnl_item)
            
            # Auto status with color
            auto_item = QTableWidgetItem(position.auto_status)
            auto_item.setForeground(QColor(COLORS['automation_active']))
            self.positions_table.setItem(row, 9, auto_item)
            
            # Color row based on status
            if position.status == "STAGED":
                for col in range(self.positions_table.columnCount()):
                    item = self.positions_table.item(row, col)
                    if item:
                        item.setBackground(QColor(40, 40, 40))
                        
    def update_greeks(self):
        """Update Greek risk displays"""
        # Set values with automation status
        self.greek_bars['delta'].set_value(self.greek_risks.delta, "AUTO-HEDGING OFF")
        self.greek_bars['gamma'].set_value(self.greek_risks.gamma, "NORMAL")
        self.greek_bars['theta'].set_value(self.greek_risks.theta, "HARVESTING TIME")
        self.greek_bars['vega'].set_value(self.greek_risks.vega, "NORMAL")
        
        # Simulate changes
        self.greek_risks.delta += random.uniform(-2, 2)
        self.greek_risks.gamma += random.uniform(-0.1, 0.1)
        self.greek_risks.theta += random.uniform(-5, 5)
        self.greek_risks.vega += random.uniform(-10, 10)
        
    def add_auto_log(self, message: str):
        """Add entry to automation log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.auto_log.append(f"{timestamp} - {message}")
        
        # Keep only last 100 lines
        cursor = self.auto_log.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        cursor.movePosition(cursor.MoveOperation.Down, cursor.MoveMode.MoveAnchor, 
                          self.auto_log.document().blockCount() - 100)
        cursor.movePosition(cursor.MoveOperation.End, cursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        
# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================
def main():
    """Main entry point"""
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    # Create and show dashboard
    dashboard = AutomatedTradingDashboard()
    dashboard.show()
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
