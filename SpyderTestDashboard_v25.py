#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Test Dashboard Standalone (Updated Version)
Quick test version without dependencies on other Spyder modules
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
    QProgressBar, QTabWidget, QScrollArea, QMessageBox, QLineEdit
)
from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, QThread, pyqtSlot, QSize, QRect
)
from PyQt6.QtGui import (
    QFont, QPalette, QColor, QIcon, QPixmap, QPainter, QBrush, 
    QShortcut, QKeySequence, QPen, QTextCursor
)

# Matplotlib for charting
import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import pandas as pd

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Window dimensions
WINDOW_WIDTH = 1920
WINDOW_HEIGHT = 1080

# Panel widths - keep center panel intact
LEFT_PANEL_WIDTH = 340  # Slightly reduced
CENTER_PANEL_WIDTH = 970  # Keep original width
RIGHT_PANEL_WIDTH = 610  # Slightly increased

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
    'grid': '#2a2a2a',
    'orange': '#ff9800',
    'red': '#ff0000',
    'cyan': '#00ffff'
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
        layout.setContentsMargins(10, 2, 5, 2)  # Added left margin
        
        # Symbol label
        self.symbol_label = QLabel(self.symbol)
        self.symbol_label.setStyleSheet(f"color: {COLORS['text']};")
        self.symbol_label.setFixedWidth(60)
        
        # Price label
        self.price_label = QLabel("---.--")
        self.price_label.setStyleSheet(f"color: {COLORS['text']};")
        self.price_label.setFixedWidth(70)
        self.price_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        
        # Change label
        self.change_label = QLabel("+0.00")
        self.change_label.setFixedWidth(55)
        self.change_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        
        # Percent label
        self.pct_label = QLabel("0.00%")
        self.pct_label.setFixedWidth(55)
        self.pct_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        
        layout.addWidget(self.symbol_label)
        layout.addWidget(self.price_label)
        layout.addWidget(self.change_label)
        layout.addWidget(self.pct_label)
        
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
        self.setFixedHeight(22)  # Slightly increased for better text fit
        
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
        painter.fillRect(self.rect(), QColor(COLORS['background']))
        
        # Bar background - moved further right to avoid overlap
        bar_rect = QRect(110, 6, self.width() - 300, 10)  # Moved from 100 to 110
        painter.fillRect(bar_rect, QColor(COLORS['panel']))
        
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
        font.setPointSize(10)  # Same size for all text
        painter.setFont(font)
        
        # Greek name and value (left side)
        text = f"{self.name}: {self.current_val:.2f}"
        painter.drawText(10, 16, text)
        
        # Status text (right side) - white, same size as Greeks
        painter.setPen(QColor(COLORS['text']))
        painter.setFont(font)  # Use same font size
        status_rect = QRect(self.width() - 190, 0, 180, 22)
        painter.drawText(status_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, self.status)

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
        self.system_logs = []  # Store logs for descending order
        self.account_mode = "PAPER"  # Default mode
        self.ib_connected = True  # Track connection status
        self.setup_ui()
        self.setup_timers()
        self.load_test_data()
        
    def setup_ui(self):
        """Setup the user interface"""
        self.setWindowTitle("SPYDER - AI Options Trading System")
        self.setGeometry(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT)
        
        # Set dark theme
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {COLORS['background']};
            }}
            QLabel {{
                color: {COLORS['text']};
                font-weight: normal;
            }}
            QGroupBox {{
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: {COLORS['background']};
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
                font-weight: normal;
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
                font-size: 11px;
            }}
            QTableWidgetItem {{
                font-size: 11px;
            }}
            QHeaderView::section {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                padding: 5px;
                font-size: 10px;
            }}
            QTextEdit {{
                background-color: {COLORS['panel']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
            }}
            QScrollArea {{
                background-color: {COLORS['background']};
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: {COLORS['background']};
                width: 10px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {COLORS['border']};
                border-radius: 5px;
            }}
            QLineEdit {{
                background-color: {COLORS['panel']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                padding: 5px;
                border-radius: 3px;
            }}
        """)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(3, 3, 3, 3)  # Reduced margins
        main_layout.setSpacing(3)  # Reduced spacing
        
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
        """Create top toolbar with centered market indices"""
        toolbar = QWidget()
        toolbar.setFixedHeight(60)
        toolbar.setStyleSheet(f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']};")
        
        layout = QHBoxLayout()
        
        # SPYDER logo on left
        logo_label = QLabel("S P Y D E R")
        try:
            logo_font = QFont("Michroma", 16, QFont.Weight.Bold)
        except:
            logo_font = QFont("Arial", 16, QFont.Weight.Bold)
        logo_label.setFont(logo_font)
        logo_label.setStyleSheet(f"color: {COLORS['text']}; letter-spacing: 5px;")
        layout.addWidget(logo_label)
        
        # Add stretch to push indices toward center - reduced to move indices left
        layout.addStretch(1)
        layout.addSpacing(25)
        
        # Center section with market indices
        center_section = QHBoxLayout()
        center_section.setSpacing(15)
        
        # DOW
        dow_container = QHBoxLayout()
        dow_container.setSpacing(0)
        dow_label = QLabel("DOW:")
        dow_label.setStyleSheet(f"color: {COLORS['text']};")
        dow_container.addWidget(dow_label)
        
        self.dow_value = QLabel(" 43,900.42")
        self.dow_value.setStyleSheet(f"color: {COLORS['text']};")  # Changed to white
        dow_container.addWidget(self.dow_value)
        
        self.dow_change = QLabel("  +350.35  +2.3%")
        self.dow_change.setStyleSheet(f"color: {COLORS['positive']};")
        dow_container.addWidget(self.dow_change)
        
        center_section.addLayout(dow_container)
        center_section.addWidget(QLabel("  ||  "))
        
        # S&P 500
        sp_container = QHBoxLayout()
        sp_container.setSpacing(0)
        sp_label = QLabel("S&P 500:")
        sp_label.setStyleSheet(f"color: {COLORS['text']};")
        sp_container.addWidget(sp_label)
        
        self.sp_value = QLabel(" 6,876.23")
        self.sp_value.setStyleSheet(f"color: {COLORS['text']};")  # Changed to white
        sp_container.addWidget(self.sp_value)
        
        self.sp_change = QLabel("  +45.43  +1.2%")
        self.sp_change.setStyleSheet(f"color: {COLORS['positive']};")
        sp_container.addWidget(self.sp_change)
        
        center_section.addLayout(sp_container)
        center_section.addWidget(QLabel("  ||  "))
        
        # NASDAQ
        nasdaq_container = QHBoxLayout()
        nasdaq_container.setSpacing(0)
        nasdaq_label = QLabel("NASDAQ:")
        nasdaq_label.setStyleSheet(f"color: {COLORS['text']};")
        nasdaq_container.addWidget(nasdaq_label)
        
        self.nasdaq_value = QLabel(" 20,275.62")
        self.nasdaq_value.setStyleSheet(f"color: {COLORS['text']};")  # Changed to white
        nasdaq_container.addWidget(self.nasdaq_value)
        
        self.nasdaq_change = QLabel("  +45.23  +0.78%")
        self.nasdaq_change.setStyleSheet(f"color: {COLORS['positive']};")
        nasdaq_container.addWidget(self.nasdaq_change)
        
        center_section.addLayout(nasdaq_container)
        
        layout.addLayout(center_section)
        
        # Add another stretch to balance the centering - increased to push left
        layout.addStretch(2)
        
        # Right section with IB Connection and Date/Time
        right_section = QHBoxLayout()
        right_section.setSpacing(15)
        
        # IB Connection status (with extra space for DISCONNECTED)
        self.connection_label = QLabel("IB CONNECTED   ")  # Extra spaces for DISCONNECTED
        self.connection_label.setStyleSheet(f"color: {COLORS['positive']};")
        self.connection_label.setFixedWidth(150)  # Fixed width to accommodate both states
        right_section.addWidget(self.connection_label)
        
        # Date/Time with 2 spaces before ET
        self.datetime_label = QLabel(datetime.now().strftime("%Y-%m-%d   %H:%M:%S  ET"))
        self.datetime_label.setStyleSheet("font-size: 14px;")
        right_section.addWidget(self.datetime_label)
        
        layout.addLayout(right_section)
        
        toolbar.setLayout(layout)
        return toolbar
        
    def create_left_panel(self) -> QWidget:
        """Create left panel with black background and cyan headers"""
        panel = QGroupBox("MARKET OVERVIEW")
        panel.setStyleSheet(f"background-color: {COLORS['background']};")
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 10, 0, 0)
        
        # Header
        header = QWidget()
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(10, 0, 5, 0)
        
        # Column headers - cyan and properly aligned
        symbol_header = QLabel("SYMBOL")
        symbol_header.setFixedWidth(60)
        symbol_header.setStyleSheet(f"color: {COLORS['cyan']}; font-weight: normal;")
        
        last_header = QLabel("LAST")
        last_header.setFixedWidth(70)
        last_header.setAlignment(Qt.AlignmentFlag.AlignRight)
        last_header.setStyleSheet(f"color: {COLORS['cyan']}; font-weight: normal;")
        
        chg_header = QLabel("CHG")
        chg_header.setFixedWidth(55)
        chg_header.setAlignment(Qt.AlignmentFlag.AlignRight)
        chg_header.setStyleSheet(f"color: {COLORS['cyan']}; font-weight: normal;")
        
        chg_pct_header = QLabel("CHG%")
        chg_pct_header.setFixedWidth(55)
        chg_pct_header.setAlignment(Qt.AlignmentFlag.AlignRight)
        chg_pct_header.setStyleSheet(f"color: {COLORS['cyan']}; font-weight: normal;")
        
        header_layout.addWidget(symbol_header)
        header_layout.addWidget(last_header)
        header_layout.addWidget(chg_header)
        header_layout.addWidget(chg_pct_header)
        header.setLayout(header_layout)
        
        layout.addWidget(header)
        
        # Add separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"color: {COLORS['border']};")
        layout.addWidget(separator)
        
        # Scroll area for symbols
        scroll_area = QScrollArea()
        scroll_area.setStyleSheet(f"background-color: {COLORS['background']};")
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)  # Hide vertical scrollbar
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet(f"background-color: {COLORS['background']};")
        scroll_layout = QVBoxLayout()
        scroll_layout.setSpacing(1)
        
        # Create symbol widgets
        self.symbol_widgets = {}
        for category, symbols in MARKET_SYMBOLS.items():
            # Category header - cyan, uppercase, unbold
            cat_label = QLabel(category.upper())
            cat_label.setStyleSheet(f"color: {COLORS['cyan']}; font-size: 12px; padding: 5px 0px 2px 10px; font-weight: normal;")
            scroll_layout.addWidget(cat_label)
            
            # Symbol widgets
            for symbol in symbols:
                widget = MarketSymbolWidget(symbol, category)
                widget.setStyleSheet(f"background-color: {COLORS['background']};")
                self.symbol_widgets[symbol] = widget
                scroll_layout.addWidget(widget)
        
        # Add Market Breadth section
        breadth_label = QLabel("MARKET BREADTH")
        breadth_label.setStyleSheet(f"color: {COLORS['cyan']}; font-size: 12px; padding: 10px 0px 2px 10px; font-weight: normal;")
        scroll_layout.addWidget(breadth_label)
        
        # Market breadth symbols
        breadth_symbols = {
            '$TICK': 'NYSE Buying/Selling',
            '$TRIN': 'Price/Volume Breadth',
            '$ADD': 'Advance/Decline Line',
            '$VOLD': 'Volume Difference A/D'
        }
        
        for symbol, desc in breadth_symbols.items():
            widget = MarketSymbolWidget(symbol, 'Market Breadth')
            widget.setStyleSheet(f"background-color: {COLORS['background']};")
            self.symbol_widgets[symbol] = widget
            scroll_layout.addWidget(widget)
            
            # Initialize with sample data
            self.market_data[symbol] = MarketData(
                symbol=symbol,
                last=random.uniform(-500, 500),
                change=random.uniform(-50, 50),
                change_pct=random.uniform(-5, 5),
                timestamp=datetime.now()
            )
                
        scroll_layout.addStretch()
        scroll_widget.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        
        layout.addWidget(scroll_area)
        panel.setLayout(layout)
        return panel
        
    def create_center_panel(self) -> QWidget:
        """Create center panel with chart and positions"""
        panel = QWidget()
        layout = QVBoxLayout()
        
        # Market regime indicator with red text - now centered
        regime_widget = QWidget()
        regime_widget.setStyleSheet(f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']};")
        regime_widget.setFixedHeight(40)
        regime_layout = QHBoxLayout()
        
        # Add stretch to center the content
        regime_layout.addStretch()
        
        # Create a container for the centered content
        center_container = QHBoxLayout()
        center_container.setSpacing(20)  # Space between the two sections
        
        # Market Regime section
        regime_section = QHBoxLayout()
        regime_section.setSpacing(5)
        regime_label = QLabel("MARKET REGIME: ")
        regime_label.setStyleSheet(f"color: {COLORS['text']};")
        regime_section.addWidget(regime_label)
        
        regime_value = QLabel("Low Volatility - Range Bound")
        regime_value.setStyleSheet(f"color: {COLORS['cyan']};")  # Changed to cyan
        regime_section.addWidget(regime_value)
        
        center_container.addLayout(regime_section)
        
        # Separator
        separator_label = QLabel("|")
        separator_label.setStyleSheet(f"color: {COLORS['text_dim']};")
        center_container.addWidget(separator_label)
        
        # Active Strategy section
        strategy_section = QHBoxLayout()
        strategy_section.setSpacing(5)
        strategy_label = QLabel("CURRENT ACTIVE STRATEGY: ")
        strategy_label.setStyleSheet(f"color: {COLORS['text']};")
        strategy_section.addWidget(strategy_label)
        
        strategy_value = QLabel("Iron Condor")
        strategy_value.setStyleSheet(f"color: {COLORS['cyan']};")  # Changed to cyan
        strategy_section.addWidget(strategy_value)
        
        center_container.addLayout(strategy_section)
        
        regime_layout.addLayout(center_container)
        regime_layout.addStretch()
        
        regime_widget.setLayout(regime_layout)
        layout.addWidget(regime_widget)
        
        # Chart
        self.create_chart()
        layout.addWidget(self.chart_widget, 2)
        
        # Positions table
        positions_group = QGroupBox("ORDERS && POSITIONS")  # Double ampersand to display correctly
        positions_layout = QVBoxLayout()
        
        self.positions_table = self.create_positions_table()
        self.positions_table.setMaximumHeight(190)
        self.positions_table.setMinimumHeight(190)  # Force fixed height
        positions_layout.addWidget(self.positions_table)
        
        positions_group.setLayout(positions_layout)
        layout.addWidget(positions_group, 1)
        
        # System logs
        logs_group = QGroupBox("SYSTEM LOG")
        logs_layout = QVBoxLayout()
        
        self.system_log = QTextEdit()
        self.system_log.setReadOnly(True)
        self.system_log.setMaximumHeight(150)
        self.system_log.setStyleSheet(f"font-family: monospace; font-size: 11px;")
        
        logs_layout.addWidget(self.system_log)
        logs_group.setLayout(logs_layout)
        layout.addWidget(logs_group, 1)
        
        panel.setLayout(layout)
        return panel
        
    def add_system_log(self, message: str):
        """Add entry to system log with date/time in descending order"""
        timestamp = datetime.now().strftime("%d%b%y %H:%M:%S").upper()
        log_entry = f"{timestamp} - {message}"
        self.system_logs.insert(0, log_entry)  # Add to beginning
        
        # Update display - show most recent first
        self.system_log.clear()
        for log in self.system_logs[:20]:  # Show last 20 logs
            self.system_log.append(log)
        
        # Auto-scroll to top to show newest message
        cursor = self.system_log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self.system_log.setTextCursor(cursor)
        
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
        
    def create_positions_table(self) -> QTableWidget:
        """Create positions table without row numbers"""
        table = QTableWidget()
        
        # Columns (no row numbers)
        columns = ["DATE", "SYMBOL", "CONS", "STRIKES", "EXPIRY", 
                  "STRATEGY", "STATUS", "COST", "P&L", "AUTO STATUS"]
        
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(columns)
        
        # Hide row numbers
        table.verticalHeader().setVisible(False)
        
        # Configure table
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setStyleSheet("font-size: 11px;")  # Set smaller font size
        
        # Set column widths - adjusted to prevent clipping
        table.setColumnWidth(0, 75)   # DATE
        table.setColumnWidth(1, 55)   # SYMBOL
        table.setColumnWidth(2, 45)   # CONS (reduced)
        table.setColumnWidth(3, 135)  # STRIKES
        table.setColumnWidth(4, 65)   # EXPIRY (reduced)
        table.setColumnWidth(5, 150)  # STRATEGY (increased)
        table.setColumnWidth(6, 70)   # STATUS
        table.setColumnWidth(7, 95)   # COST
        table.setColumnWidth(8, 95)   # P&L
        table.setColumnWidth(9, 130)  # AUTO STATUS (reduced to prevent clipping)
        
        # Set horizontal scrollbar policy
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Set vertical scrollbar policy 
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        
        # Set row height
        table.verticalHeader().setDefaultSectionSize(22)  # Slightly smaller for smaller font
        table.setMinimumHeight(190)
        table.setMaximumHeight(190)  # Fixed height for 7 visible rows + header + padding
        
        return table
        
    def create_right_panel(self) -> QWidget:
        """Create right panel with account info and risk metrics"""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(3)  # Reduce spacing to fit everything
        layout.setContentsMargins(5, 5, 5, 5)  # Add margins
        
        # System control buttons with tooltips
        button_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("START SYSTEM")
        self.start_btn.setStyleSheet(f"background-color: {COLORS['positive']}; color: black;")
        self.start_btn.setToolTip("Connect to IB and start trading")
        self.start_btn.clicked.connect(self.start_system)
        button_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("STOP SYSTEM")
        self.stop_btn.setStyleSheet(f"background-color: {COLORS['warning']};")
        self.stop_btn.setToolTip("Disconnect from IB, but let the orders and positions remain")
        self.stop_btn.clicked.connect(self.stop_system)
        button_layout.addWidget(self.stop_btn)
        
        self.emergency_btn = QPushButton("EMERGENCY CLOSE")
        self.emergency_btn.setStyleSheet(f"background-color: {COLORS['negative']};")
        self.emergency_btn.setToolTip("Close all orders and positions, stop trading, and disconnect from IB")
        self.emergency_btn.clicked.connect(self.emergency_close)
        button_layout.addWidget(self.emergency_btn)
        
        layout.addLayout(button_layout)
        
        # Account info group - table layout
        account_group = QGroupBox("")  # Remove title to save space
        account_layout = QVBoxLayout()
        
        # Create table widget
        table_widget = QWidget()
        table_widget.setStyleSheet(f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']}; padding: 5px;")
        table_layout = QGridLayout()
        table_layout.setContentsMargins(8, 8, 8, 8)  # Reduced margins
        table_layout.setHorizontalSpacing(10)  # Reduced spacing
        table_layout.setVerticalSpacing(6)  # Reduced spacing
        
        # Define cell style
        cell_style = f"""
            padding: 5px 10px;
            background-color: {COLORS['background']};
            border: 1px solid {COLORS['border']};
        """
        
        # Row 1: ACCOUNT | DU5361048 | MODE: PAPER | RISK PARAMETERS
        account_label = QLabel("ACCOUNT")
        account_label.setStyleSheet(cell_style)
        table_layout.addWidget(account_label, 0, 0)
        
        account_value = QLabel("DU5361048")
        account_value.setStyleSheet(cell_style)
        table_layout.addWidget(account_value, 0, 1)
        
        mode_label = QLabel("MODE: PAPER")
        mode_label.setStyleSheet(cell_style + f"color: {COLORS['orange']};")
        table_layout.addWidget(mode_label, 0, 2)
        
        # RISK LIMITS button - same style as EMERGENCY CLOSE
        self.risk_params_btn = QPushButton("RISK PARAMETERS")
        self.risk_params_btn.setStyleSheet(f"background-color: {COLORS['negative']};")
        self.risk_params_btn.setToolTip("Configure global and strategy-specific risk parameters")
        self.risk_params_btn.clicked.connect(self.show_risk_parameters)
        table_layout.addWidget(self.risk_params_btn, 0, 3)
        
        # Row 2: SETTLED CASH | $21,800,000.00 | REALIZED P&L | $2,030,450.00
        settled_label = QLabel("SETTLED CASH")
        settled_label.setStyleSheet(cell_style)
        table_layout.addWidget(settled_label, 1, 0)
        
        self.settled_value = QLabel("$21,800,000.00")
        self.settled_value.setStyleSheet(cell_style + "text-align: right;")
        self.settled_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        table_layout.addWidget(self.settled_value, 1, 1)
        
        realized_label = QLabel("REALIZED P&L")
        realized_label.setStyleSheet(cell_style)
        table_layout.addWidget(realized_label, 1, 2)
        
        self.realized_value = QLabel("$2,030,450.00")
        self.realized_value.setStyleSheet(cell_style + f"color: {COLORS['positive']}; text-align: right;")
        self.realized_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        table_layout.addWidget(self.realized_value, 1, 3)
        
        # Row 3: BUYING POWER | $20,450,000.00 | UNREALIZED P&L | $1,385,000.00
        buying_label = QLabel("BUYING POWER")
        buying_label.setStyleSheet(cell_style)
        table_layout.addWidget(buying_label, 2, 0)
        
        self.buying_value = QLabel("$20,450,000.00")
        self.buying_value.setStyleSheet(cell_style + "text-align: right;")
        self.buying_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        table_layout.addWidget(self.buying_value, 2, 1)
        
        unrealized_label = QLabel("UNREALIZED P&L")
        unrealized_label.setStyleSheet(cell_style)
        table_layout.addWidget(unrealized_label, 2, 2)
        
        self.unrealized_value = QLabel("$1,385,000.00")
        self.unrealized_value.setStyleSheet(cell_style + f"color: {COLORS['positive']}; text-align: right;")
        self.unrealized_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        table_layout.addWidget(self.unrealized_value, 2, 3)
        
        # Store references for updates
        self.account_labels = {
            'settled_cash': self.settled_value,
            'unrealized_pnl': self.unrealized_value,
            'realized_pnl': self.realized_value,
            'buying_power': self.buying_value
        }
        
        table_widget.setLayout(table_layout)
        account_layout.addWidget(table_widget)
        
        account_group.setLayout(account_layout)
        layout.addWidget(account_group)
        
        # P&L Performance
        pnl_group = QGroupBox("P&&L PERFORMANCE")  # Double ampersand to display correctly
        pnl_layout = QVBoxLayout()
        
        self.pnl_table = self.create_pnl_table()
        self.pnl_table.setFixedHeight(110)  # Reduced height for smaller font
        pnl_layout.addWidget(self.pnl_table)
        
        # Performance metrics - updated format
        perf_widget = QWidget()
        perf_layout = QHBoxLayout()
        perf_layout.setContentsMargins(5, 0, 5, 0)
        
        perf_label = QLabel("YEAR-TO-DATE PROFIT FACTOR: 1.85   ||  SHARPE RATIO: 2.35")
        perf_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        perf_layout.addWidget(perf_label)
        perf_widget.setLayout(perf_layout)
        
        pnl_layout.addWidget(perf_widget)
        pnl_group.setLayout(pnl_layout)
        layout.addWidget(pnl_group)
        
        # Risk Monitor
        risk_group = QGroupBox("RISK MONITOR")
        risk_layout = QVBoxLayout()
        risk_layout.setSpacing(2)  # Reduce spacing between Greek bars
        
        # Greek bars - reduced height
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
        auto_layout.setContentsMargins(5, 10, 5, 5)  # Reduce top margin more
        auto_layout.setSpacing(1)  # Reduce spacing even more
        
        self.auto_log = QTextEdit()
        self.auto_log.setReadOnly(True)
        self.auto_log.setFixedHeight(35)  # Further reduced height
        self.auto_log.setPlainText("Automation status will be displayed here...")
        
        auto_layout.addWidget(self.auto_log)
        auto_group.setLayout(auto_layout)
        layout.addWidget(auto_group)
        
        # System Health
        health_group = QGroupBox("SYSTEM HEALTH")
        health_layout = QVBoxLayout()
        health_layout.setSpacing(2)  # Reduce spacing
        
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
        
        panel.setLayout(layout)
        return panel
        
    def start_system(self):
        """Handle start system button click"""
        self.ib_connected = True
        self.update_connection_status()
        self.add_system_log("System started - Connected to IB Gateway")
        print("Starting IB Gateway connection...")
        
    def stop_system(self):
        """Handle stop system button click"""
        self.ib_connected = False
        self.update_connection_status()
        self.add_system_log("System stopped - Disconnected from IB")
        print("Stopping IB Gateway connection...")
        
    def emergency_close(self):
        """Handle emergency close button click"""
        self.ib_connected = False
        self.update_connection_status()
        self.add_system_log("EMERGENCY CLOSE - All positions closed, system stopped")
        print("EMERGENCY: Closing all positions and stopping!")
        
    def update_connection_status(self):
        """Update IB connection status display"""
        if self.ib_connected:
            self.connection_label.setText("IB CONNECTED   ")
            self.connection_label.setStyleSheet(f"color: {COLORS['positive']};")
        else:
            self.connection_label.setText("IB DISCONNECTED")
            self.connection_label.setStyleSheet(f"color: {COLORS['negative']};")
            
    def show_risk_parameters(self):
        """Show risk parameters dialog (placeholder)"""
        QMessageBox.information(self, "Risk Parameters", 
                              "Risk Parameters dialog will be implemented here.\n\n"
                              "This will allow configuration of:\n"
                              "• Global risk limits\n"
                              "• Strategy-specific overrides\n"
                              "• Dynamic market adjustments\n"
                              "• Execution controls")
        
    def create_pnl_table(self) -> QTableWidget:
        """Create P&L performance table with only 4 periods"""
        table = QTableWidget(4, 4)  # Reduced to 4 rows
        table.setHorizontalHeaderLabels(["PERIOD", "P&L", "WIN RATE%", "AVG WIN/LOSS"])
        table.setStyleSheet("font-size: 11px;")  # Set smaller font size
        
        # Sample data - only 4 periods
        periods = ["TODAY", "WEEK", "MONTH", "YEAR"]
        data = [
            ("+$850.00", "75%", "$425.00 / $120.00"),
            ("+$3,200.00", "68%", "$380.00 / $150.00"),
            ("+$12,500.00", "72%", "$450.00 / $180.00"),
            ("+$45,000.00", "70%", "$500.00 / $200.00")
        ]
        
        for row, (period, values) in enumerate(zip(periods, data)):
            # Period
            table.setItem(row, 0, QTableWidgetItem(period))
            
            # P&L - right aligned
            pnl_item = QTableWidgetItem(values[0])
            pnl_item.setTextAlignment(Qt.AlignmentFlag.AlignRight)
            pnl_item.setForeground(QColor(COLORS['positive']))
            table.setItem(row, 1, pnl_item)
            
            # Win Rate - centered
            win_rate_item = QTableWidgetItem(values[1])
            win_rate_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 2, win_rate_item)
            
            # Avg Win/Loss - centered
            avg_item = QTableWidgetItem(values[2])
            avg_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 3, avg_item)
            
        # Configure table
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(20)  # Smaller row height for smaller font
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        # Remove scrollbars
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
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
        
        # System log timer
        self.log_timer = QTimer()
        self.log_timer.timeout.connect(self.update_system_log)
        self.log_timer.start(10000)  # Every 10 seconds
        
        # DateTime timer
        self.datetime_timer = QTimer()
        self.datetime_timer.timeout.connect(self.update_datetime)
        self.datetime_timer.start(1000)  # Every second
        
    def update_datetime(self):
        """Update the date/time display with 2 spaces before ET"""
        self.datetime_label.setText(datetime.now().strftime("%Y-%m-%d   %H:%M:%S  ET"))
        
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
        
        # Add initial system logs
        self.add_system_log("System initialized successfully")
        self.add_system_log("Connected to IB Gateway")
        self.add_system_log("Market data subscription active")
        self.add_system_log("Strategy engine started")
        self.add_system_log("Risk manager active")
        self.add_system_log("Monitoring SPY options chain")
        
        # Update initial displays
        self.update_all_symbols()
        self.update_greeks()
        self.update_chart()
        
    def add_test_positions(self):
        """Add test positions with updated date format"""
        test_positions = [
            PositionData(
                date="30DEC24",
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
                date="30DEC24",
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
                date="30DEC24",
                symbol="SPY",
                contracts=5,
                strikes="590/592/594/596",
                expiry="03JAN25",
                strategy="Iron Condor",
                status="STAGED",
                cost=0.00,
                pnl=0.00,
                auto_status="PENDING FILL"
            ),
            PositionData(
                date="30DEC24",
                symbol="SPY",
                contracts=15,
                strikes="578/580",
                expiry="31DEC24",
                strategy="Put Credit Spread",
                status="CLOSED",
                cost=1200.00,
                pnl=1200.00,
                auto_status="COMPLETED"
            ),
            PositionData(
                date="29DEC24",
                symbol="SPY",
                contracts=10,
                strikes="585",
                expiry="31DEC24",
                strategy="Short Put",
                status="ACTIVE",
                cost=850.00,
                pnl=-125.00,
                auto_status="MONITORING"
            ),
            PositionData(
                date="29DEC24",
                symbol="SPY",
                contracts=25,
                strikes="586/588",
                expiry="02JAN25",
                strategy="Call Credit Spread",
                status="ACTIVE",
                cost=2250.00,
                pnl=425.00,
                auto_status="MONITORING"
            ),
            PositionData(
                date="29DEC24",
                symbol="SPY",
                contracts=8,
                strikes="575/577/593/595",
                expiry="03JAN25",
                strategy="Iron Butterfly",
                status="ACTIVE",
                cost=960.00,
                pnl=-85.00,
                auto_status="DELTA WATCH"
            ),
            PositionData(
                date="28DEC24",
                symbol="SPY",
                contracts=12,
                strikes="584/586",
                expiry="31DEC24",
                strategy="Bear Call Spread",
                status="STAGED",
                cost=0.00,
                pnl=0.00,
                auto_status="PENDING FILL"
            ),
            PositionData(
                date="28DEC24",
                symbol="SPY",
                contracts=30,
                strikes="590",
                expiry="03JAN25",
                strategy="Short Call",
                status="ACTIVE",
                cost=3600.00,
                pnl=-275.00,
                auto_status="MONITORING"
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
                if symbol.startswith('$'):  # Market breadth symbols
                    # These can be positive or negative
                    movement = random.uniform(-50, 50)
                    data.last += movement
                    data.change = movement
                    data.change_pct = random.uniform(-5, 5)
                else:
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
        
        # Generate realistic OHLC data
        spy_price = self.market_data['SPY'].last if 'SPY' in self.market_data else 585
        
        opens = []
        highs = []
        lows = []
        closes = []
        
        current_price = spy_price - 2
        
        for _ in range(periods):
            # Random walk
            change = random.random() * 0.5 - 0.25
            current_price += change
            
            # OHLC
            open_price = current_price
            high = current_price + random.random() * 0.3
            low = current_price - random.random() * 0.3
            close = low + random.random() * (high - low)
            
            opens.append(open_price)
            highs.append(high)
            lows.append(low)
            closes.append(close)
            
            current_price = close
        
        # Create plot
        ax = self.figure.add_subplot(111)
        ax.yaxis.tick_right()
        ax.yaxis.set_label_position('right')
        
        # Plot candlesticks
        for i in range(len(dates)):
            color = COLORS['positive'] if closes[i] >= opens[i] else COLORS['negative']
            
            # High-Low line
            ax.plot([i, i], [lows[i], highs[i]], color=color, linewidth=1)
            
            # Open-Close box
            height = abs(closes[i] - opens[i])
            bottom = min(opens[i], closes[i])
            
            rect = plt.Rectangle((i - 0.3, bottom), 0.6, height,
                               facecolor=color,
                               edgecolor=color,
                               alpha=0.8)
            ax.add_patch(rect)
        
        # Styling
        ax.set_title('SPY - 5 min', color=COLORS['text'], fontsize=12, pad=10)
        ax.set_xlim(-1, len(dates))
        ax.grid(True, alpha=0.3, color=COLORS['grid'])
        
        # Format x-axis with time labels
        num_labels = 6
        indices = np.linspace(0, len(dates)-1, num_labels, dtype=int)
        ax.set_xticks(indices)
        
        time_labels = []
        for idx in indices:
            time_str = dates[idx].strftime('%H:%M')
            time_labels.append(time_str)
        
        ax.set_xticklabels(time_labels, fontsize=9)
        
        # Set background color
        ax.set_facecolor(COLORS['panel'])
        
        # Style axes
        ax.tick_params(colors=COLORS['text'])
        for spine in ax.spines.values():
            spine.set_color(COLORS['border'])
        
        # Adjust layout
        self.figure.tight_layout()
        self.canvas.draw()
        
    def update_positions(self):
        """Update positions table"""
        self.positions_table.setRowCount(len(self.positions))
        
        for row, position in enumerate(self.positions):
            # Set items with proper alignment
            date_item = QTableWidgetItem(position.date)
            date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.positions_table.setItem(row, 0, date_item)
            
            symbol_item = QTableWidgetItem(position.symbol)
            symbol_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.positions_table.setItem(row, 1, symbol_item)
            
            # Contract - center aligned for consistency
            contract_item = QTableWidgetItem(str(position.contracts))
            contract_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.positions_table.setItem(row, 2, contract_item)
            
            strikes_item = QTableWidgetItem(position.strikes)
            strikes_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.positions_table.setItem(row, 3, strikes_item)
            
            expiry_item = QTableWidgetItem(position.expiry)
            expiry_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.positions_table.setItem(row, 4, expiry_item)
            self.positions_table.setItem(row, 5, QTableWidgetItem(position.strategy))
            
            # Status - center aligned
            status_item = QTableWidgetItem(position.status)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.positions_table.setItem(row, 6, status_item)
            
            # Cost - right aligned
            cost_item = QTableWidgetItem(f"${position.cost:,.2f}")
            cost_item.setTextAlignment(Qt.AlignmentFlag.AlignRight)
            self.positions_table.setItem(row, 7, cost_item)
            
            # P&L with color
            pnl_item = QTableWidgetItem(f"${position.pnl:+,.2f}")
            if position.pnl > 0:
                pnl_item.setForeground(QColor(COLORS['positive']))
            elif position.pnl < 0:
                pnl_item.setForeground(QColor(COLORS['negative']))
            pnl_item.setTextAlignment(Qt.AlignmentFlag.AlignRight)  # Right align P&L
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
                        item.setBackground(QColor(30, 30, 30))
            elif position.status == "CLOSED":
                for col in range(self.positions_table.columnCount()):
                    item = self.positions_table.item(row, col)
                    if item:
                        item.setForeground(QColor(COLORS['text_dim']))
                        
    def update_greeks(self):
        """Update Greek risk displays"""
        # Set values with automation status (no brackets)
        self.greek_bars['delta'].set_value(self.greek_risks.delta, "AUTO-HEDGING OFF")
        self.greek_bars['gamma'].set_value(self.greek_risks.gamma, "NORMAL")
        self.greek_bars['theta'].set_value(self.greek_risks.theta, "HARVESTING TIME")
        self.greek_bars['vega'].set_value(self.greek_risks.vega, "NORMAL")
        
        # Simulate changes
        self.greek_risks.delta += random.uniform(-2, 2)
        self.greek_risks.gamma += random.uniform(-0.1, 0.1)
        self.greek_risks.theta += random.uniform(-5, 5)
        self.greek_risks.vega += random.uniform(-10, 10)
        
    def update_system_log(self):
        """Add periodic system log entries"""
        log_messages = [
            "Option chain updated",
            "Risk parameters checked",
            "Position delta hedged",
            "Market regime analysis complete",
            "Greeks recalculated",
            "Strategy signals evaluated",
            "Order routing verified",
            "System health check passed",
            "Data feed active",
            "ML models updated",
            "Volatility surface refreshed",
            "Correlation matrix updated"
        ]
        
        message = random.choice(log_messages)
        self.add_system_log(message)
        
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
    
    print("Updated Dashboard is running. Close the window to exit.")
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
