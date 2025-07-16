#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Test Dashboard Standalone (Version 26)
Updated with optimized market symbols and tooltip support
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
    QProgressBar, QTabWidget, QScrollArea, QMessageBox, QLineEdit,
    QToolTip
)
from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, QThread, pyqtSlot, QSize, QRect, QPoint
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

# Panel widths
LEFT_PANEL_WIDTH = 340
CENTER_PANEL_WIDTH = 970
RIGHT_PANEL_WIDTH = 610

# Market symbols organized by category - UPDATED WITH OPTIMIZED LIST
MARKET_SYMBOLS = {
    'S&P CORE': ['SPY', 'SPX', '/ES'],
    'VOLATILITY': ['VIX', 'VIX9D', 'VXV', 'VXMT', 'VVIX', 'UVXY'],
    'MARKET INTERNALS': ['$TICK', '$TRIN', '$ADD', 'CPC', 'PCALL', 'SKEW'],
    'MAJOR INDICES': ['DIA', 'QQQ', 'IWM'],
    'BONDS & CREDIT': ['TLT', 'LQD'],
    'CORRELATIONS': ['DXY', 'GLD'],
    'CUSTOM METRICS': ['GEX', 'DEX', 'OGL', 'DIX', 'SWAN']
}

# Symbol descriptions for tooltips
SYMBOL_DESCRIPTIONS = {
    # S&P Core
    'SPY': 'SPDR S&P 500 ETF - Most liquid S&P 500 ETF',
    'SPX': 'S&P 500 Index - Cash index value',
    '/ES': 'E-mini S&P 500 Futures - 24/5 trading',
    
    # Volatility
    'VIX': 'CBOE Volatility Index - 30-day implied volatility',
    'VIX9D': 'CBOE 9-Day Volatility Index - Short-term volatility',
    'VXV': 'CBOE 3-Month Volatility Index - 93-day implied volatility',
    'VXMT': 'CBOE Mid-Term Volatility Index - 6-month volatility',
    'VVIX': 'VIX of VIX - Volatility of volatility index',
    'UVXY': 'ProShares Ultra VIX Short-Term Futures ETF',
    
    # Market Internals
    '$TICK': 'NYSE Tick Index - Upticks minus downticks',
    '$TRIN': 'Arms Index - Advance/Decline volume ratio',
    '$ADD': 'Advance-Decline Line - Net advancing issues',
    'CPC': 'CBOE Put/Call Ratio - Equity options only',
    'PCALL': 'Total Put/Call Ratio - All options',
    'SKEW': 'CBOE Skew Index - Tail risk measure',
    
    # Major Indices
    'DIA': 'SPDR Dow Jones Industrial Average ETF',
    'QQQ': 'Invesco QQQ Trust - NASDAQ 100 ETF',
    'IWM': 'iShares Russell 2000 ETF - Small caps',
    
    # Bonds & Credit
    'TLT': 'iShares 20+ Year Treasury Bond ETF',
    'LQD': 'iShares Investment Grade Corporate Bond ETF',
    
    # Correlations
    'DXY': 'US Dollar Index - Dollar strength',
    'GLD': 'SPDR Gold Trust ETF - Gold proxy',
    
    # Custom Metrics
    'GEX': 'Gamma Exposure - Market maker hedging pressure',
    'DEX': 'Delta Exposure - Directional hedging flow',
    'OGL': 'Zero Gamma Level - Key support/resistance',
    'DIX': 'Dark Index - Dark pool buying percentage',
    'SWAN': 'Black Swan Risk Indicator - Tail risk monitor'
}

# Update intervals
FAST_UPDATE_MS = 1000   # SPY, SPX, /ES, VIX, $TICK, SWAN (when critical)
MEDIUM_UPDATE_MS = 5000   # Other volatility, internals, indices
SLOW_UPDATE_MS = 15000  # Bonds, correlations (DXY, GLD), custom metrics

# Symbol update categories
FAST_UPDATE_SYMBOLS = ['SPY', 'SPX', '/ES', 'VIX', '$TICK']
MEDIUM_UPDATE_SYMBOLS = ['VIX9D', 'VXV', 'VXMT', 'VVIX', 'UVXY', '$TRIN', '$ADD', 
                        'CPC', 'PCALL', 'SKEW', 'DIA', 'QQQ', 'IWM']
SLOW_UPDATE_SYMBOLS = ['TLT', 'LQD', 'DXY', 'GLD', 'GEX', 'DEX', 'OGL', 'DIX', 'SWAN']

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
    'cyan': '#00ffff',
    'yellow': '#ffff00'
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
    auto_status: str

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
    """Widget for displaying a single market symbol with tooltip support"""
    
    def __init__(self, symbol: str, category: str):
        super().__init__()
        self.symbol = symbol
        self.category = category
        self.setup_ui()
        
        # Set tooltip if available
        if symbol in SYMBOL_DESCRIPTIONS:
            self.setToolTip(SYMBOL_DESCRIPTIONS[symbol])
        
    def setup_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 2, 5, 2)
        
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
        # Format based on symbol type
        if self.symbol in ['GEX', 'DEX', 'OGL', 'DIX', 'SWAN']:
            self._update_custom_indicator(data)
        else:
            self._update_standard_symbol(data)
    
    def _update_standard_symbol(self, data: MarketData):
        """Update standard market symbols"""
        self.price_label.setText(f"{data.last:.2f}")
        
        # Color based on change
        color = COLORS['positive'] if data.change >= 0 else COLORS['negative']
        sign = '+' if data.change >= 0 else ''
        
        self.change_label.setText(f"{sign}{data.change:.2f}")
        self.change_label.setStyleSheet(f"color: {color};")
        
        self.pct_label.setText(f"{sign}{data.change_pct:.2f}%")
        self.pct_label.setStyleSheet(f"color: {color};")
    
    def _update_custom_indicator(self, data: MarketData):
        """Update custom indicators with special formatting"""
        # Format last value based on indicator type
        if self.symbol == 'GEX':
            # Format in billions
            value_b = data.last / 1_000_000_000
            self.price_label.setText(f"{value_b:.1f}B")
            # Color: positive = green (stable), negative = red (volatile)
            color = COLORS['positive'] if data.last > 0 else COLORS['negative']
            
        elif self.symbol == 'DEX':
            # Format in millions
            value_m = data.last / 1_000_000
            self.price_label.setText(f"{value_m:.0f}M")
            color = COLORS['positive'] if data.change >= 0 else COLORS['negative']
            
        elif self.symbol == 'OGL':
            # Price level format
            self.price_label.setText(f"{data.last:.2f}")
            # Yellow if SPY is near this level
            spy_price = 585.25  # Would get from actual SPY data
            if abs(spy_price - data.last) < 2:
                color = COLORS['warning']
            else:
                color = COLORS['text_dim']
                
        elif self.symbol == 'DIX':
            # Percentage format
            self.price_label.setText(f"{data.last:.1f}%")
            # Color based on bullish/bearish threshold
            if data.last > 45:
                color = COLORS['positive']
            elif data.last < 40:
                color = COLORS['negative']
            else:
                color = COLORS['neutral']
                
        elif self.symbol == 'SWAN':
            # Value with status
            self.price_label.setText(f"{data.last:.2f}")
            # Traffic light colors
            if data.last < 1.9:
                color = COLORS['positive']  # Green
                status = "🟢"
            elif data.last < 2.0:
                color = COLORS['warning']   # Yellow
                status = "🟡"
            else:
                color = COLORS['negative']  # Red
                status = "🔴"
            # Add status emoji to symbol
            self.symbol_label.setText(f"{self.symbol} {status}")
        
        # Update change and percentage
        sign = '+' if data.change >= 0 else ''
        
        # Format change based on indicator
        if self.symbol == 'GEX':
            change_b = data.change / 1_000_000_000
            self.change_label.setText(f"{sign}{change_b:.1f}B")
        elif self.symbol == 'DEX':
            change_m = data.change / 1_000_000
            self.change_label.setText(f"{sign}{change_m:.0f}M")
        elif self.symbol == 'DIX':
            self.change_label.setText(f"{sign}{data.change:.1f}%")
        else:
            self.change_label.setText(f"{sign}{data.change:.2f}")
        
        self.change_label.setStyleSheet(f"color: {color};")
        self.pct_label.setText(f"{sign}{data.change_pct:.2f}%")
        self.pct_label.setStyleSheet(f"color: {color};")

    def enterEvent(self, event):
        """Show tooltip on hover"""
        if self.symbol in SYMBOL_DESCRIPTIONS:
            QToolTip.showText(QPoint(self.mapToGlobal(self.rect().center())), 
                            SYMBOL_DESCRIPTIONS[self.symbol])
        super().enterEvent(event)

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
        self.setFixedHeight(22)
        
    def set_value(self, value: float, status: str = "NORMAL"):
        """Update Greek value and status"""
        self.current_val = value
        self.percentage = abs(value - self.min_val) / (self.max_val - self.min_val)
        self.percentage = min(max(self.percentage, 0), 1)
        self.status = status
        self.update()
        
    def paintEvent(self, event):
        """Custom paint for the Greek bar"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Background
        painter.fillRect(self.rect(), QColor(COLORS['background']))
        
        # Bar background
        bar_rect = QRect(110, 6, self.width() - 300, 10)
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
        font.setPointSize(10)
        painter.setFont(font)
        
        # Greek name and value (left side)
        text = f"{self.name}: {self.current_val:.2f}"
        painter.drawText(10, 16, text)
        
        # Status text (right side)
        painter.setPen(QColor(COLORS['text']))
        painter.setFont(font)
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
        self.system_logs = []
        self.account_mode = "PAPER"
        self.ib_connected = True
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
            QToolTip {{
                background-color: {COLORS['panel']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                padding: 5px;
            }}
        """)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(3, 3, 3, 3)
        main_layout.setSpacing(3)
        
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
        
        # Add stretch to push indices toward center
        layout.addStretch(1)
        layout.addSpacing(25)
        
        # Center section with market indices
        center_section = QHBoxLayout()
        center_section.setSpacing(15)
        
        # DJI
        dji_container = QHBoxLayout()
        dji_container.setSpacing(0)
        dji_label = QLabel("DJI:")
        dji_label.setStyleSheet(f"color: {COLORS['text']};")
        dji_container.addWidget(dji_label)
        
        self.dji_value = QLabel(" 43,900.42")
        self.dji_value.setStyleSheet(f"color: {COLORS['text']};")
        dji_container.addWidget(self.dji_value)
        
        self.dji_change = QLabel("  +350.35  +2.3%")
        self.dji_change.setStyleSheet(f"color: {COLORS['positive']};")
        dji_container.addWidget(self.dji_change)
        
        center_section.addLayout(dji_container)
        center_section.addWidget(QLabel("  ||  "))
        
        # SPX
        spx_container = QHBoxLayout()
        spx_container.setSpacing(0)
        spx_label = QLabel("SPX:")
        spx_label.setStyleSheet(f"color: {COLORS['text']};")
        spx_container.addWidget(spx_label)
        
        self.spx_value = QLabel(" 6,876.23")
        self.spx_value.setStyleSheet(f"color: {COLORS['text']};")
        spx_container.addWidget(self.spx_value)
        
        self.spx_change = QLabel("  +45.43  +1.2%")
        self.spx_change.setStyleSheet(f"color: {COLORS['positive']};")
        spx_container.addWidget(self.spx_change)
        
        center_section.addLayout(spx_container)
        center_section.addWidget(QLabel("  ||  "))
        
        # NDX
        ndx_container = QHBoxLayout()
        ndx_container.setSpacing(0)
        ndx_label = QLabel("NDX:")
        ndx_label.setStyleSheet(f"color: {COLORS['text']};")
        ndx_container.addWidget(ndx_label)
        
        self.ndx_value = QLabel(" 20,275.62")
        self.ndx_value.setStyleSheet(f"color: {COLORS['text']};")
        ndx_container.addWidget(self.ndx_value)
        
        self.ndx_change = QLabel("  +45.23  +0.78%")
        self.ndx_change.setStyleSheet(f"color: {COLORS['positive']};")
        ndx_container.addWidget(self.ndx_change)
        
        center_section.addLayout(ndx_container)
        
        layout.addLayout(center_section)
        
        # Add another stretch to balance the centering
        layout.addStretch(2)
        
        # Right section with IB Connection and Date/Time
        right_section = QHBoxLayout()
        right_section.setSpacing(15)
        
        # IB Connection status
        self.connection_label = QLabel("IB CONNECTED   ")
        self.connection_label.setStyleSheet(f"color: {COLORS['positive']};")
        self.connection_label.setFixedWidth(150)
        right_section.addWidget(self.connection_label)
        
        # Date/Time
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
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet(f"background-color: {COLORS['background']};")
        scroll_layout = QVBoxLayout()
        scroll_layout.setSpacing(1)
        
        # Create symbol widgets
        self.symbol_widgets = {}
        for category, symbols in MARKET_SYMBOLS.items():
            # Category header - cyan, uppercase, unbold
            cat_label = QLabel(category)
            cat_label.setStyleSheet(f"color: {COLORS['cyan']}; font-size: 12px; padding: 5px 0px 2px 10px; font-weight: normal;")
            scroll_layout.addWidget(cat_label)
            
            # Symbol widgets
            for symbol in symbols:
                widget = MarketSymbolWidget(symbol, category)
                widget.setStyleSheet(f"background-color: {COLORS['background']};")
                self.symbol_widgets[symbol] = widget
                scroll_layout.addWidget(widget)
                
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
        center_container.setSpacing(20)
        
        # Market Regime section
        regime_section = QHBoxLayout()
        regime_section.setSpacing(5)
        regime_label = QLabel("MARKET REGIME: ")
        regime_label.setStyleSheet(f"color: {COLORS['text']};")
        regime_section.addWidget(regime_label)
        
        regime_value = QLabel("Low Volatility - Range Bound")
        regime_value.setStyleSheet(f"color: {COLORS['cyan']};")
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
        strategy_value.setStyleSheet(f"color: {COLORS['cyan']};")
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
        positions_group = QGroupBox("ORDERS && POSITIONS")
        positions_layout = QVBoxLayout()
        
        self.positions_table = self.create_positions_table()
        self.positions_table.setMaximumHeight(190)
        self.positions_table.setMinimumHeight(190)
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
        self.system_logs.insert(0, log_entry)
        
        # Update display - show most recent first
        self.system_log.clear()
        for log in self.system_logs[:20]:
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
        table.setStyleSheet("font-size: 11px;")
        
        # Set column widths
        table.setColumnWidth(0, 75)   # DATE
        table.setColumnWidth(1, 55)   # SYMBOL
        table.setColumnWidth(2, 45)   # CONS
        table.setColumnWidth(3, 135)  # STRIKES
        table.setColumnWidth(4, 65)   # EXPIRY
        table.setColumnWidth(5, 150)  # STRATEGY
        table.setColumnWidth(6, 70)   # STATUS
        table.setColumnWidth(7, 95)   # COST
        table.setColumnWidth(8, 95)   # P&L
        table.setColumnWidth(9, 130)  # AUTO STATUS
        
        # Set horizontal scrollbar policy
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Set vertical scrollbar policy 
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        
        # Set row height
        table.verticalHeader().setDefaultSectionSize(22)
        table.setMinimumHeight(190)
        table.setMaximumHeight(190)
        
        return table
        
    def create_right_panel(self) -> QWidget:
        """Create right panel with account info and risk metrics"""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(3)
        layout.setContentsMargins(5, 5, 5, 5)
        
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
        account_group = QGroupBox("")
        account_layout = QVBoxLayout()
        
        # Create table widget
        table_widget = QWidget()
        table_widget.setStyleSheet(f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']}; padding: 5px;")
        table_layout = QGridLayout()
        table_layout.setContentsMargins(8, 8, 8, 8)
        table_layout.setHorizontalSpacing(10)
        table_layout.setVerticalSpacing(6)
        
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
        
        # RISK LIMITS button
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
        pnl_group = QGroupBox("P&&L PERFORMANCE")
        pnl_layout = QVBoxLayout()
        
        self.pnl_table = self.create_pnl_table()
        self.pnl_table.setFixedHeight(110)
        pnl_layout.addWidget(self.pnl_table)
        
        # Performance metrics
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
        risk_layout.setSpacing(2)
        
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
        auto_layout.setContentsMargins(5, 10, 5, 5)
        auto_layout.setSpacing(1)
        
        self.auto_log = QTextEdit()
        self.auto_log.setReadOnly(True)
        self.auto_log.setFixedHeight(35)
        self.auto_log.setPlainText("Automation status will be displayed here...")
        
        auto_layout.addWidget(self.auto_log)
        auto_group.setLayout(auto_layout)
        layout.addWidget(auto_group)
        
        # System Health
        health_group = QGroupBox("SYSTEM HEALTH")
        health_layout = QVBoxLayout()
        health_layout.setSpacing(2)
        
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
        table = QTableWidget(4, 4)
        table.setHorizontalHeaderLabels(["PERIOD", "P&L", "WIN RATE%", "AVG WIN/LOSS"])
        table.setStyleSheet("font-size: 11px;")
        
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
        table.verticalHeader().setDefaultSectionSize(20)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        # Remove scrollbars
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        return table
        
    def setup_timers(self):
        """Setup update timers with different intervals"""
        # Fast timer (1 second) for critical symbols
        self.fast_timer = QTimer()
        self.fast_timer.timeout.connect(self.update_fast_symbols)
        self.fast_timer.start(FAST_UPDATE_MS)
        
        # Medium timer (5 seconds)
        self.medium_timer = QTimer()
        self.medium_timer.timeout.connect(self.update_medium_symbols)
        self.medium_timer.start(MEDIUM_UPDATE_MS)
        
        # Slow timer (15 seconds)
        self.slow_timer = QTimer()
        self.slow_timer.timeout.connect(self.update_slow_symbols)
        self.slow_timer.start(SLOW_UPDATE_MS)
        
        # Chart timer
        self.chart_timer = QTimer()
        self.chart_timer.timeout.connect(self.update_chart)
        self.chart_timer.start(2000)
        
        # Position timer
        self.position_timer = QTimer()
        self.position_timer.timeout.connect(self.update_positions)
        self.position_timer.start(2000)
        
        # System log timer
        self.log_timer = QTimer()
        self.log_timer.timeout.connect(self.update_system_log)
        self.log_timer.start(10000)
        
        # DateTime timer
        self.datetime_timer = QTimer()
        self.datetime_timer.timeout.connect(self.update_datetime)
        self.datetime_timer.start(1000)
        
    def update_datetime(self):
        """Update the date/time display"""
        self.datetime_label.setText(datetime.now().strftime("%Y-%m-%d   %H:%M:%S  ET"))
        
    def load_test_data(self):
        """Load test data for demonstration"""
        # Initialize market data with realistic values
        base_prices = {
            # S&P Core
            'SPY': 585.25, 'SPX': 5850.75, '/ES': 5852.50,
            
            # Volatility
            'VIX': 15.32, 'VIX9D': 14.8, 'VXV': 16.2, 'VXMT': 17.5,
            'VVIX': 82.45, 'UVXY': 22.18,
            
            # Market Internals
            '$TICK': 234, '$TRIN': 0.85, '$ADD': 1245,
            'CPC': 0.95, 'PCALL': 0.88, 'SKEW': 125.5,
            
            # Major Indices
            'DIA': 425.33, 'QQQ': 485.92, 'IWM': 225.18,
            
            # Bonds & Credit
            'TLT': 92.45, 'LQD': 105.32,
            
            # Correlations
            'DXY': 103.25, 'GLD': 195.67,
            
            # Custom Metrics
            'GEX': -2500000000,  # -2.5B
            'DEX': 850000000,    # 850M
            'OGL': 585.50,       # Price level
            'DIX': 42.5,         # Percentage
            'SWAN': 1.85         # Risk level
        }
        
        for symbol, price in base_prices.items():
            if symbol.startswith('$'):
                # Market internals can be positive or negative
                change = random.uniform(-50, 50) if symbol == '$TICK' else random.uniform(-0.1, 0.1)
            elif symbol in ['GEX', 'DEX']:
                # Large numbers for exposure metrics
                change = random.uniform(-500000000, 500000000)
            elif symbol == 'DIX':
                # Percentage changes
                change = random.uniform(-2, 2)
            else:
                change = price * (random.random() * 0.04 - 0.02)
                
            self.market_data[symbol] = MarketData(
                symbol=symbol,
                last=price,
                change=change,
                change_pct=(change/price) * 100 if price != 0 else 0,
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
        """Add test positions"""
        test_positions = [
            PositionData(
                date="16JAN25",
                symbol="SPY",
                contracts=10,
                strikes="580/582/588/590",
                expiry="17JAN25",
                strategy="Iron Condor",
                status="ACTIVE",
                cost=1250.00,
                pnl=350.00,
                auto_status="MONITORING"
            ),
            PositionData(
                date="16JAN25",
                symbol="SPY",
                contracts=20,
                strikes="582/584",
                expiry="17JAN25",
                strategy="Bull Put Spread",
                status="ACTIVE",
                cost=1700.00,
                pnl=860.00,
                auto_status="THETA HARVEST"
            ),
            PositionData(
                date="16JAN25",
                symbol="SPY",
                contracts=5,
                strikes="590/592/594/596",
                expiry="21JAN25",
                strategy="Iron Condor",
                status="STAGED",
                cost=0.00,
                pnl=0.00,
                auto_status="PENDING FILL"
            ),
        ]
        
        self.positions = test_positions
        self.update_positions()
        
    def update_fast_symbols(self):
        """Update fast symbols every second"""
        for symbol in FAST_UPDATE_SYMBOLS:
            if symbol in self.market_data:
                self._update_symbol_price(symbol)
                
    def update_medium_symbols(self):
        """Update medium symbols every 5 seconds"""
        for symbol in MEDIUM_UPDATE_SYMBOLS:
            if symbol in self.market_data:
                self._update_symbol_price(symbol)
                
    def update_slow_symbols(self):
        """Update slow symbols every 15 seconds"""
        for symbol in SLOW_UPDATE_SYMBOLS:
            if symbol in self.market_data:
                self._update_symbol_price(symbol)
                
    def _update_symbol_price(self, symbol: str):
        """Update individual symbol price with realistic movement"""
        data = self.market_data[symbol]
        
        # Different movement patterns for different symbol types
        if symbol.startswith('$'):
            # Market internals - more volatile
            if symbol == '$TICK':
                movement = random.uniform(-100, 100)
            else:
                movement = random.uniform(-0.05, 0.05)
        elif symbol in ['GEX', 'DEX']:
            # Exposure metrics - larger moves
            movement = random.uniform(-100000000, 100000000)
        elif symbol == 'DIX':
            # Percentage - smaller moves
            movement = random.uniform(-0.5, 0.5)
        elif symbol == 'SWAN':
            # Risk indicator - gradual changes
            movement = random.uniform(-0.05, 0.05)
            # Keep within bounds
            data.last = max(0, min(5, data.last + movement))
            movement = 0  # Recalculate below
        else:
            # Regular symbols - normal market movement
            movement = random.random() * 0.2 - 0.1
            
        data.last += movement
        data.change += movement
        data.change_pct = (data.change / (data.last - data.change)) * 100 if (data.last - data.change) != 0 else 0
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
            
            status_item = QTableWidgetItem(position.status)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.positions_table.setItem(row, 6, status_item)
            
            cost_item = QTableWidgetItem(f"${position.cost:,.2f}")
            cost_item.setTextAlignment(Qt.AlignmentFlag.AlignRight)
            self.positions_table.setItem(row, 7, cost_item)
            
            # P&L with color
            pnl_item = QTableWidgetItem(f"${position.pnl:+,.2f}")
            if position.pnl > 0:
                pnl_item.setForeground(QColor(COLORS['positive']))
            elif position.pnl < 0:
                pnl_item.setForeground(QColor(COLORS['negative']))
            pnl_item.setTextAlignment(Qt.AlignmentFlag.AlignRight)
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
            "Correlation matrix updated",
            "SWAN indicator checked",
            "GEX levels calculated",
            "Dark pool activity monitored"
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
    
    print("Spyder Dashboard v26 running with optimized market symbols.")
    print("Hover over symbols to see descriptions.")
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
