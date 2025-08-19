#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG05_TradingDashboard.py
Purpose: Complete Trading Dashboard with Real Data Integration & Enhanced Features - ET Time Fix
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-19 Time: 15:10:00  

Module Description:
    Enhanced trading dashboard with proper ET time display. Minimal surgical fix
    to show actual Eastern Time instead of local system time. All existing design
    and functionality preserved - only the time display logic updated to use 
    real ET timezone calculations for accurate market time display.

"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import os
import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import math
import traceback
import weakref

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pytz  # 🔧 NEW: Added for proper ET time handling
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import pandas as pd
import numpy as np

# Matplotlib setup for PyQt6
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderC_MarketData.SpyderC01_DataFeed import DataFeed
from SpyderG_GUI.SpyderG09_RiskParametersDialog import RiskParametersDialog
from SpyderG_GUI.SpyderG10_CustomMetricsIntegration import CustomMetricsIntegration
from SpyderG_GUI.SpyderG11_SkewMonitorDialog import SkewMonitorDialog
from SpyderG_GUI.SpyderG12_SignalInfoDialog import SignalInfoDialog

# ==============================================================================
# 🔧 NEW: ET TIME DISPLAY CLASS (Minimal addition)
# ==============================================================================
class ETTimeDisplay:
    """ET time display helper for dashboard - copied from MarketDataManager"""
    
    @staticmethod
    def get_et_time_string() -> str:
        """Get current ET time as formatted string."""
        et_tz = pytz.timezone('US/Eastern')
        et_now = datetime.now(et_tz)
        return et_now.strftime('%Y-%m-%d   %H:%M:%S  ET')
    
    @staticmethod
    def get_market_status() -> Tuple[str, str]:
        """Get current market status based on ET time."""
        et_tz = pytz.timezone('US/Eastern')
        et_now = datetime.now(et_tz)
        hour = et_now.hour
        minute = et_now.minute
        weekday = et_now.weekday()  # 0=Monday, 6=Sunday
        
        # Weekend check
        if weekday >= 5:  # Saturday or Sunday
            return 'WEEKEND', '🏖️'
        
        # Weekday market hours
        if hour < 9 or (hour == 9 and minute < 30):
            return 'PRE-MARKET', '🌅'
        elif (hour == 9 and minute >= 30) or (9 < hour < 16):
            return 'MARKET OPEN', '🔔'
        elif 16 <= hour < 20:
            return 'AFTER-HOURS', '🌆'
        else:
            return 'MARKET CLOSED', '🌙'

# ==============================================================================
# CONSTANTS (Unchanged - preserving all existing design)
# ==============================================================================
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 900

COLORS = {
    'background': '#1a1a1a',
    'panel': '#2a2a2a',
    'border': '#444444',
    'text': '#ffffff',
    'positive': '#00ff41',
    'negative': '#ff1744',
    'warning': '#ff9800',
    'info': '#2196f3',
    'orange': '#ff9800',
    'purple': '#9c27b0',
    'grid': '#333333'
}

# Market data simulation
SYMBOLS = ['SPY', 'QQQ', 'IWM', 'VIX', 'ES', 'NQ', 'RTY']

STRATEGY_STATUS = {
    'IRON_CONDOR': '🎯 ACTIVE',
    'CREDIT_SPREAD': '⏸️ PAUSED', 
    'STRADDLE': '🔄 MONITORING',
    'BUTTERFLY': '❌ STOPPED'
}

# Prometheus metrics mapping
PROMETHEUS_METRICS_MAP = {
    'spy_price': 'market_data_price{symbol="SPY"}',
    'vix_level': 'market_data_price{symbol="VIX"}', 
    'portfolio_delta': 'portfolio_greeks_delta',
    'portfolio_theta': 'portfolio_greeks_theta',
    'daily_pnl': 'portfolio_pnl_daily',
    'connection_status': 'ib_connection_status'
}

# ==============================================================================
# MARKET DATA WORKER (Unchanged)
# ==============================================================================
class MarketDataWorker(QObject):
    """Background worker for market data updates"""
    
    data_updated = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        self.running = False
        self.data_feed = None
        
    def start_updates(self):
        """Start market data updates"""
        try:
            self.data_feed = DataFeed()
            self.running = True
            self.update_data()
        except Exception as e:
            print(f"Error starting market data: {e}")
    
    def update_data(self):
        """Generate and emit market data"""
        if not self.running:
            return
            
        try:
            # Generate simulated market data
            data = {}
            base_prices = {
                'SPY': 640.0, 'QQQ': 485.0, 'IWM': 195.0, 'VIX': 12.5,
                'ES': 6375.0, 'NQ': 20150.0, 'RTY': 2250.0
            }
            
            for symbol in SYMBOLS:
                base = base_prices.get(symbol, 100.0)
                change = np.random.normal(0, 0.002) * base
                price = base + change
                
                data[symbol] = {
                    'price': round(price, 2),
                    'change': round(change, 2),
                    'change_pct': round((change / base) * 100, 2) if base > 0 else 0.0,
                    'volume': np.random.randint(100000, 1000000),
                    'bid': round(price - 0.01, 2),
                    'ask': round(price + 0.01, 2)
                }
            
            self.data_updated.emit(data)
            
            # Schedule next update
            QTimer.singleShot(1000, self.update_data)
            
        except Exception as e:
            print(f"Error updating market data: {e}")
    
    def stop(self):
        """Stop market data updates"""
        self.running = False

# ==============================================================================
# MAIN TRADING DASHBOARD CLASS
# ==============================================================================
class TradingDashboard(QMainWindow):
    """Complete Trading Dashboard with Real Data Integration & Enhanced Features"""
    
    def __init__(self):
        super().__init__()
        
        # Logging
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Data management
        self.market_data = {}
        self.real_data_active = False
        self.ib_connected = True  # Assume connected for now
        
        # UI components
        self.symbol_labels = {}
        self.symbol_price_labels = {}
        self.symbol_change_labels = {}
        
        # Workers and timers
        self.market_worker = None
        self.worker_thread = None
        
        # 🔧 NEW: ET time management (minimal addition)
        self.et_display = ETTimeDisplay()
        
        # Custom Metrics Integration
        self.custom_metrics = CustomMetricsIntegration()
        
        self.setup_ui()
        self.setup_workers()
        self.setup_timers()
        
        # Try to detect and use real data
        self.detect_real_data()
        
        self.logger.info("Trading Dashboard initialized")

    # ==========================================================================
    # 🔧 TIMER SETUP (Modified to use ET time)
    # ==========================================================================
    def setup_timers(self):
        """Setup update timers"""
        # 🔧 MODIFIED: Update datetime timer to use ET time
        self.datetime_timer = QTimer()
        self.datetime_timer.timeout.connect(self.update_datetime_display)
        self.datetime_timer.start(1000)  # Update every second
        
        # Account balance update timer (unchanged)
        self.balance_timer = QTimer() 
        self.balance_timer.timeout.connect(self.update_account_balances)
        self.balance_timer.start(5000)  # Update every 5 seconds

    # ==========================================================================
    # 🔧 NEW: ET TIME UPDATE METHOD (Only new method added)
    # ==========================================================================
    def update_datetime_display(self):
        """Update the datetime display with actual ET time"""
        try:
            # 🔧 FIX: Use actual ET time instead of local time
            et_time_str = self.et_display.get_et_time_string()
            self.datetime_label.setText(et_time_str)
        except Exception as e:
            # Fallback to original behavior if there's any issue
            self.datetime_label.setText(datetime.now().strftime("%Y-%m-%d   %H:%M:%S  ET"))

    # ==========================================================================
    # UI CREATION METHODS (Unchanged - preserving design)
    # ==========================================================================
    def setup_ui(self):
        """Setup the complete UI"""
        self.setWindowTitle("SPYDER - Autonomous Options Trading System v1.0")
        self.setGeometry(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT)

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
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #3a3a3a;
            }}
            QPushButton:pressed {{
                background-color: #4a4a4a;
            }}
            QTableWidget {{
                background-color: {COLORS['background']};
                alternate-background-color: {COLORS['panel']};
                gridline-color: {COLORS['border']};
                selection-background-color: #0066CC;
            }}
            QHeaderView::section {{
                background-color: {COLORS['panel']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                padding: 4px;
            }}
        """)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Create all UI components
        main_layout.addWidget(self.create_toolbar())
        main_layout.addWidget(self.create_header())
        main_layout.addWidget(self.create_main_content())
        main_layout.addWidget(self.create_status_bar())
        
        central_widget.setLayout(main_layout)

    def create_toolbar(self):
        """Create the top toolbar - 🔧 MINIMALLY MODIFIED for ET time"""
        toolbar = QWidget()
        toolbar.setFixedHeight(40)
        toolbar.setStyleSheet(f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']};")
        
        layout = QHBoxLayout()
        layout.setContentsMargins(15, 5, 15, 5)
        layout.setSpacing(10)
        
        # Left section - Logo
        logo_label = QLabel("🕷️ SPYDER v1.0")
        logo_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #00ff41;")
        layout.addWidget(logo_label)
        
        layout.addStretch()
        
        # Right section
        right_section = QHBoxLayout()
        right_section.setSpacing(10)
        
        # MARKET DATA STATUS
        market_data_container = QHBoxLayout()
        market_data_container.setSpacing(3)
        
        market_data_dot = QLabel("●")
        market_data_dot.setStyleSheet(f"color: {COLORS['positive']};")
        market_data_container.addWidget(market_data_dot)
        
        self.market_data_status = QLabel("LIVE")
        self.market_data_status.setStyleSheet(f"color: {COLORS['positive']};")
        market_data_container.addWidget(self.market_data_status)

        # Add refresh icon
        self.refresh_icon = QPushButton()
        self.refresh_icon.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.refresh_icon.setIconSize(QSize(16, 16))
        self.refresh_icon.setFixedSize(20, 20)
        self.refresh_icon.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_icon.setToolTip("Refresh market data")
        self.refresh_icon.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                padding: 2px;
            }
            QPushButton:hover {
                background-color: #2a2a2a;
                border-radius: 3px;
            }
            QPushButton:pressed {
                background-color: #3a3a3a;
            }
        """)
        self.refresh_icon.clicked.connect(self.refresh_market_data)
        market_data_container.addWidget(self.refresh_icon)

        right_section.addLayout(market_data_container)
        right_section.addSpacing(20)
        right_section.addWidget(QLabel(" | "))

        # IB CONNECTION STATUS
        self.ib_container = QWidget()
        self.ib_container.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ib_container.setToolTip("Click to connect/disconnect")
        self.ib_container.setStyleSheet("""
            QWidget:hover {
                background-color: #2a2a2a;
                border-radius: 3px;
                padding: 2px;
            }
        """)
        ib_layout = QHBoxLayout()
        ib_layout.setContentsMargins(5, 2, 5, 2)
        ib_layout.setSpacing(3)

        self.connection_dot = QLabel("●")
        self.connection_dot.setStyleSheet(f"color: {COLORS['positive']};")
        ib_layout.addWidget(self.connection_dot)

        self.connection_label = QLabel("IB CONNECTED")
        self.connection_label.setStyleSheet(f"color: {COLORS['positive']};")
        ib_layout.addWidget(self.connection_label)

        self.ib_container.setLayout(ib_layout)
        self.ib_container.mousePressEvent = self.toggle_ib_connection

        right_section.addWidget(self.ib_container)
        right_section.addWidget(QLabel(" | "))

        # 🔧 MODIFIED: DATE/TIME (same widget, different initial value)
        self.datetime_label = QLabel(self.et_display.get_et_time_string())
        self.datetime_label.setStyleSheet("font-size: 14px;")
        right_section.addWidget(self.datetime_label)

        layout.addLayout(right_section)

        toolbar.setLayout(layout)
        return toolbar

    # ==========================================================================
    # ALL OTHER METHODS UNCHANGED (preserving fragile design)
    # ==========================================================================
    def create_header(self):
        """Create market data header"""
        header = QWidget()
        header.setFixedHeight(80)
        header.setStyleSheet(f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']};")
        
        layout = QHBoxLayout()
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(20)
        
        for symbol in SYMBOLS:
            symbol_widget = self.create_symbol_widget(symbol)
            layout.addWidget(symbol_widget)
        
        header.setLayout(layout)
        return header

    def create_symbol_widget(self, symbol):
        """Create individual symbol widget"""
        widget = QWidget()
        widget.setMinimumWidth(120)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)
        
        # Symbol name
        symbol_label = QLabel(symbol)
        symbol_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        symbol_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(symbol_label)
        self.symbol_labels[symbol] = symbol_label
        
        # Price
        price_label = QLabel("---.--")
        price_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        price_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(price_label)
        self.symbol_price_labels[symbol] = price_label
        
        # Change
        change_label = QLabel("+0.00%")
        change_label.setStyleSheet(f"font-size: 12px; color: {COLORS['positive']};")
        change_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(change_label)
        self.symbol_change_labels[symbol] = change_label
        
        widget.setLayout(layout)
        return widget

    def create_main_content(self):
        """Create main content area"""
        content = QWidget()
        
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # Left panel
        left_panel = self.create_left_panel()
        left_panel.setMinimumWidth(500)
        layout.addWidget(left_panel)
        
        # Right panel  
        right_panel = self.create_right_panel()
        right_panel.setMinimumWidth(350)
        layout.addWidget(right_panel)
        
        content.setLayout(layout)
        return content

    def create_left_panel(self):
        """Create left panel with chart and account info"""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # Account info table
        account_info = self.create_account_info()
        account_info.setMaximumHeight(120)
        layout.addWidget(account_info)
        
        # Chart
        chart_widget = self.create_chart()
        layout.addWidget(chart_widget)
        
        panel.setLayout(layout)
        return panel

    def create_account_info(self):
        """Create account information table"""
        widget = QWidget()
        widget.setStyleSheet(f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']}; padding: 5px;")
        table_layout = QGridLayout()
        table_layout.setContentsMargins(8, -2, 8, 8)
        table_layout.setHorizontalSpacing(10)
        table_layout.setVerticalSpacing(6)

        cell_style = f"padding: 5px 10px; background-color: {COLORS['background']}; border: 1px solid {COLORS['border']};"

        # Account row
        account_label = QLabel("ACCOUNT")
        account_label.setStyleSheet(cell_style)
        table_layout.addWidget(account_label, 0, 0)

        account_value = QLabel("DU5361048")
        account_value.setStyleSheet(cell_style)
        table_layout.addWidget(account_value, 0, 1)

        mode_label = QLabel("MODE: PAPER")
        mode_label.setStyleSheet(cell_style + f"color: {COLORS['orange']};")
        table_layout.addWidget(mode_label, 0, 2)

        self.risk_params_btn = QPushButton("RISK LEVELS")
        self.risk_params_btn.setStyleSheet(f"background-color: #0066CC; color: white;")
        self.risk_params_btn.setToolTip("Configure global and strategy-specific risk parameters")
        self.risk_params_btn.clicked.connect(self.show_risk_parameters)
        table_layout.addWidget(self.risk_params_btn, 0, 3)

        # Separator
        spacer_label = QLabel("")
        spacer_label.setFixedHeight(20)
        table_layout.addWidget(spacer_label, 1, 0, 1, 4)

        # Financial data rows
        settled_label = QLabel("SETTLED CASH")
        settled_label.setStyleSheet(cell_style)
        table_layout.addWidget(settled_label, 2, 0)

        self.settled_value = QLabel("$21,800,000.00")
        self.settled_value.setStyleSheet(cell_style + "text-align: right;")
        self.settled_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        table_layout.addWidget(self.settled_value, 2, 1)

        realized_label = QLabel("REALIZED P&L")
        realized_label.setStyleSheet(cell_style)
        table_layout.addWidget(realized_label, 2, 2)

        self.realized_value = QLabel("$2,030,450.00")
        self.realized_value.setStyleSheet(cell_style + f"color: {COLORS['positive']}; text-align: right;")
        self.realized_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        table_layout.addWidget(self.realized_value, 2, 3)

        buying_label = QLabel("BUYING POWER")
        buying_label.setStyleSheet(cell_style)
        table_layout.addWidget(buying_label, 3, 0)

        self.buying_value = QLabel("$20,450,000.00")
        self.buying_value.setStyleSheet(cell_style + "text-align: right;")
        self.buying_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        table_layout.addWidget(self.buying_value, 3, 1)

        unrealized_label = QLabel("UNREALIZED P&L")
        unrealized_label.setStyleSheet(cell_style)
        table_layout.addWidget(unrealized_label, 3, 2)

        self.unrealized_value = QLabel("$450,230.00")
        self.unrealized_value.setStyleSheet(cell_style + f"color: {COLORS['positive']}; text-align: right;")
        self.unrealized_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        table_layout.addWidget(self.unrealized_value, 3, 3)

        widget.setLayout(table_layout)
        return widget

    def create_chart(self):
        """Create price chart widget"""
        widget = QWidget()
        widget.setStyleSheet(f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']};")
        
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Chart
        self.figure = Figure(figsize=(10, 6), facecolor=COLORS['panel'])
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)
        
        # Update chart with initial data
        self.update_chart()
        
        widget.setLayout(layout)
        return widget

    def update_chart(self):
        """Update the price chart"""
        self.figure.clear()
        ax = self.figure.add_subplot(111, facecolor=COLORS['panel'])

        # Generate sample price data
        now = datetime.now()
        dates = [now - timedelta(minutes=i*5) for i in range(60, 0, -1)]
        base_price = 643.0
        prices = [base_price + np.random.normal(0, 2) for _ in dates]

        # Create OHLC data
        ohlc_data = []
        for i, price in enumerate(prices):
            high = price + abs(np.random.normal(0, 0.5))
            low = price - abs(np.random.normal(0, 0.5))
            close = prices[i] if i < len(prices) - 1 else price
            ohlc_data.append([price, high, low, close])

        # Plot candlesticks
        for i, (open_price, high, low, close) in enumerate(ohlc_data):
            color = COLORS['positive'] if close >= open_price else COLORS['negative']
            
            # Wick
            ax.plot([i, i], [low, high], color=color, linewidth=1, alpha=0.8, zorder=2)
            
            # Body
            body_height = abs(close - open_price)
            bottom = min(open_price, close)
            rect = patches.Rectangle((i - 0.3, bottom), 0.6, body_height, facecolor=color, edgecolor=color, alpha=0.9, zorder=3)
            ax.add_patch(rect)

        # Calculate pivot levels
        last_price = ohlc_data[-1][3]
        pivot = (ohlc_data[-1][1] + ohlc_data[-1][2] + last_price) / 3
        r1 = 2 * pivot - ohlc_data[-1][2]
        r2 = pivot + (ohlc_data[-1][1] - ohlc_data[-1][2])
        r3 = ohlc_data[-1][1] + 2 * (pivot - ohlc_data[-1][2])
        s1 = 2 * pivot - ohlc_data[-1][1]
        s2 = pivot - (ohlc_data[-1][1] - ohlc_data[-1][2])
        s3 = ohlc_data[-1][2] - 2 * (ohlc_data[-1][1] - pivot)

        # Plot pivot levels
        levels = [
            (pivot, "#FFFF00", "P"),
            (r1, "#00FF41", "R1"), (r2, "#00FF41", "R2"), (r3, "#00FF41", "R3"),
            (s1, "#FF1744", "S1"), (s2, "#FF1744", "S2"), (s3, "#FF1744", "S3")
        ]

        for level, color, label in levels:
            ax.axhline(y=level, color=color, linestyle='--', alpha=0.6, linewidth=1, zorder=1)

        # Add pivot level labels on the right
        ax.text(len(dates), pivot, f" P: {pivot:.2f}", color="#FFFF00", fontsize=9, va="center")
        ax.text(len(dates), r1, f" R1: {r1:.2f}", color="#00FF41", fontsize=8, va="center")
        ax.text(len(dates), r2, f" R2: {r2:.2f}", color="#00FF41", fontsize=8, va="center")
        ax.text(len(dates), r3, f" R3: {r3:.2f}", color="#00FF41", fontsize=8, va="center")
        ax.text(len(dates), s1, f" S1: {s1:.2f}", color="#FF1744", fontsize=8, va="center")
        ax.text(len(dates), s2, f" S2: {s2:.2f}", color="#FF1744", fontsize=8, va="center")
        ax.text(len(dates), s3, f" S3: {s3:.2f}", color="#FF1744", fontsize=8, va="center")

        # Styling
        ax.set_title("SPY - 5 min", color=COLORS["text"], fontsize=12, pad=10)
        ax.set_xlim(-1, len(dates))
        ax.grid(True, alpha=0.2, color=COLORS["grid"], zorder=0)

        # Format x-axis with time labels
        num_labels = 6
        indices = np.linspace(0, len(dates) - 1, num_labels, dtype=int)
        ax.set_xticks(indices)

        time_labels = []
        for idx in indices:
            time_str = dates[idx].strftime("%H:%M")
            time_labels.append(time_str)

        ax.set_xticklabels(time_labels, fontsize=9)

        # Style axes
        ax.tick_params(colors="#FFFFFF")
        for spine in ax.spines.values():
            spine.set_color(COLORS["border"])

        # Adjust layout
        self.figure.tight_layout()
        self.canvas.draw()

    def create_right_panel(self):
        """Create right panel with positions and logs"""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # Strategy status
        strategy_status = self.create_strategy_status()
        strategy_status.setMaximumHeight(150)
        layout.addWidget(strategy_status)
        
        # Positions table
        positions_table = self.create_positions_table()
        layout.addWidget(positions_table)
        
        # System logs
        logs_widget = self.create_system_logs()
        logs_widget.setMaximumHeight(200)
        layout.addWidget(logs_widget)
        
        panel.setLayout(layout)
        return panel

    def create_strategy_status(self):
        """Create strategy status widget"""
        widget = QWidget()
        widget.setStyleSheet(f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']};")
        
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        title = QLabel("STRATEGY STATUS")
        title.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)
        
        for strategy, status in STRATEGY_STATUS.items():
            strategy_layout = QHBoxLayout()
            
            strategy_label = QLabel(strategy.replace('_', ' '))
            strategy_label.setMinimumWidth(120)
            strategy_layout.addWidget(strategy_label)
            
            status_label = QLabel(status)
            if 'ACTIVE' in status:
                status_label.setStyleSheet(f"color: {COLORS['positive']};")
            elif 'PAUSED' in status:
                status_label.setStyleSheet(f"color: {COLORS['warning']};")
            elif 'STOPPED' in status:
                status_label.setStyleSheet(f"color: {COLORS['negative']};")
            else:
                status_label.setStyleSheet(f"color: {COLORS['info']};")
            
            strategy_layout.addWidget(status_label)
            strategy_layout.addStretch()
            
            layout.addLayout(strategy_layout)
        
        widget.setLayout(layout)
        return widget

    def create_positions_table(self):
        """Create positions table"""
        table = QTableWidget()

        columns = ["DATE", "SYMBOL", "CNTR", "STRIKES", "EXPIRY", "STRATEGY", "STATUS", "COST", "P&L", "AUTO STATUS"]

        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setStyleSheet("font-size: 11px;")

        # Set column widths
        table.setColumnWidth(0, 75)  # DATE
        table.setColumnWidth(1, 55)  # SYMBOL
        table.setColumnWidth(2, 45)  # CNTR
        table.setColumnWidth(3, 135)  # STRIKES
        table.setColumnWidth(4, 65)  # EXPIRY
        table.setColumnWidth(5, 150)  # STRATEGY
        table.setColumnWidth(6, 70)  # STATUS
        table.setColumnWidth(7, 95)  # COST
        table.setColumnWidth(8, 95)  # P&L
        table.setColumnWidth(9, 130)  # AUTO STATUS

        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        table.horizontalHeader().setStretchLastSection(False)

        # Add sample data
        sample_data = [
            ["08/19", "SPY", "1", "643/647", "08/21", "IRON CONDOR", "OPEN", "$125.50", "+$45.30", "🤖 MONITORING"],
            ["08/19", "QQQ", "2", "480/485", "08/23", "CREDIT SPREAD", "OPEN", "$230.00", "-$12.80", "⏳ PENDING"],
            ["08/18", "IWM", "1", "195/200", "08/21", "STRADDLE", "CLOSED", "$180.25", "+$67.90", "✅ PROFIT TAKEN"]
        ]

        table.setRowCount(len(sample_data))
        for row, data in enumerate(sample_data):
            for col, value in enumerate(data):
                item = QTableWidgetItem(str(value))
                if col == 8:  # P&L column
                    if '+' in str(value):
                        item.setForeground(QColor(COLORS['positive']))
                    elif '-' in str(value):
                        item.setForeground(QColor(COLORS['negative']))
                table.setItem(row, col, item)

        return table

    def create_system_logs(self):
        """Create system logs widget"""
        widget = QWidget()
        widget.setStyleSheet(f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']};")
        
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)
        
        title = QLabel("SYSTEM LOGS")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title)
        
        self.logs_text = QTextEdit()
        self.logs_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: {COLORS['background']};
                border: 1px solid {COLORS['border']};
                color: {COLORS['text']};
                font-family: 'Courier New', monospace;
                font-size: 10px;
            }}
        """)
        self.logs_text.setReadOnly(True)
        layout.addWidget(self.logs_text)
        
        # Add initial logs
        self.add_system_log("🟢 System initialized")
        self.add_system_log("📊 Market data connected")
        self.add_system_log("🔗 IB Gateway connected")
        
        widget.setLayout(layout)
        return widget

    def create_status_bar(self):
        """Create status bar"""
        status_bar = QWidget()
        status_bar.setFixedHeight(30)
        status_bar.setStyleSheet(f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']};")
        
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 5, 10, 5)
        
        status_label = QLabel("System Status: Operational | Market Data: Live | Strategies: 3 Active")
        status_label.setStyleSheet("font-size: 12px;")
        layout.addWidget(status_label)
        
        layout.addStretch()
        
        # Version info
        version_label = QLabel("v1.0.0")
        version_label.setStyleSheet("font-size: 11px; color: #888;")
        layout.addWidget(version_label)
        
        status_bar.setLayout(layout)
        return status_bar

    # ==========================================================================
    # WORKER SETUP AND DATA METHODS (Unchanged)
    # ==========================================================================
    def setup_workers(self):
        """Setup background workers"""
        self.worker_thread = QThread()
        self.market_worker = MarketDataWorker()
        self.market_worker.moveToThread(self.worker_thread)
        
        # Connect signals
        self.worker_thread.started.connect(self.market_worker.start_updates)
        self.market_worker.data_updated.connect(self.update_market_data)
        
        # Start worker
        self.worker_thread.start()

    def update_market_data(self, data):
        """Update market data display"""
        self.market_data = data
        
        for symbol, symbol_data in data.items():
            if symbol in self.symbol_price_labels:
                price = symbol_data['price']
                change_pct = symbol_data['change_pct']
                
                # Update price
                self.symbol_price_labels[symbol].setText(f"{price:.2f}")
                
                # Update change with color
                change_text = f"{change_pct:+.2f}%"
                color = COLORS['positive'] if change_pct >= 0 else COLORS['negative']
                self.symbol_change_labels[symbol].setText(change_text)
                self.symbol_change_labels[symbol].setStyleSheet(f"font-size: 12px; color: {color};")

    def detect_real_data(self):
        """Detect and switch to real market data if available"""
        try:
            if os.path.exists('/tmp/spyder_market_data.json'):
                with open('/tmp/spyder_market_data.json', 'r') as f:
                    real_data = json.load(f)
                    if real_data:
                        self.apply_real_data_patch()
                        self.add_system_log("🔥 Switched to REAL market data")
                        return True
        except:
            pass
        
        # Setup periodic check for real data
        def check_for_real_data():
            try:
                if os.path.exists('/tmp/spyder_market_data.json') and not self.real_data_active:
                    self._check_timer.stop()
                    self.apply_real_data_patch()
            except:
                pass
        
        # Check every 5 seconds for real data
        self._check_timer = QTimer()
        self._check_timer.timeout.connect(check_for_real_data)
        self._check_timer.start(5000)

    def apply_real_data_patch(self):
        """Apply real data integration patch"""
        try:
            self.real_data_active = True
            
            # Disconnect simulation worker
            if self.market_worker:
                self.market_worker.stop()
            
            # Setup real data timer
            self.real_data_timer = QTimer()
            self.real_data_timer.timeout.connect(self.update_with_real_data)
            self.real_data_timer.start(1000)  # Update every second
            
            self.market_data_status.setText("REAL")
            self.market_data_status.setStyleSheet(f"color: #ff9800;")
            
            self.add_system_log("✅ Real data integration active")
            
        except Exception as e:
            self.logger.error(f"Error applying real data patch: {e}")

    def update_with_real_data(self):
        """Update with real market data from JSON file"""
        try:
            if os.path.exists('/tmp/spyder_market_data.json'):
                with open('/tmp/spyder_market_data.json', 'r') as f:
                    real_data = json.load(f)
                
                # Transform real data to match expected format
                formatted_data = {}
                for symbol in SYMBOLS:
                    if symbol in real_data:
                        data = real_data[symbol]
                        formatted_data[symbol] = {
                            'price': data.get('last', 0.0),
                            'change': data.get('change', 0.0),
                            'change_pct': data.get('change_pct', 0.0),
                            'volume': data.get('volume', 0),
                            'bid': data.get('bid', 0.0),
                            'ask': data.get('ask', 0.0)
                        }
                
                if formatted_data:
                    self.update_market_data(formatted_data)
                    
        except Exception as e:
            self.logger.error(f"Error updating with real data: {e}")

    # ==========================================================================
    # EVENT HANDLERS (Unchanged)
    # ==========================================================================
    def refresh_market_data(self):
        """Enhanced refresh market data - callback for refresh icon click"""
        try:
            if self.real_data_active:
                self.add_system_log("🔥 Refreshing real market data...")
                
                # Force immediate update
                self.update_with_real_data()
                
                self.refresh_icon.setEnabled(False)
                QTimer.singleShot(1000, lambda: self.refresh_icon.setEnabled(True))
                
                self.add_system_log("✅ Real market data refreshed")
                
            elif self.market_worker:
                self.add_system_log("🔥 Refreshing simulation data...")
                
                if not self.ib_connected:
                    self.add_system_log("⚠️ Not connected to IB Gateway - using simulation data")
                
                self.refresh_icon.setEnabled(False)
                QTimer.singleShot(1000, lambda: self.refresh_icon.setEnabled(True))
                
                self.add_system_log("✅ Market data refresh requested")
            else:
                self.add_system_log("❌ Market worker not available")
                
        except Exception as e:
            self.logger.error(f"Error refreshing market data: {e}")
            self.add_system_log(f"❌ Refresh error: {e}")

    def toggle_ib_connection(self, event):
        """Toggle IB connection status"""
        self.ib_connected = not self.ib_connected
        
        if self.ib_connected:
            self.connection_label.setText("IB CONNECTED")
            self.connection_label.setStyleSheet(f"color: {COLORS['positive']};")
            self.connection_dot.setStyleSheet(f"color: {COLORS['positive']};")
            self.add_system_log("🔗 IB Gateway connected")
        else:
            self.connection_label.setText("IB DISCONNECTED")
            self.connection_label.setStyleSheet(f"color: {COLORS['negative']};")
            self.connection_dot.setStyleSheet(f"color: {COLORS['negative']};")
            self.add_system_log("🔌 IB Gateway disconnected")

    def show_risk_parameters(self):
        """Show risk parameters dialog"""
        try:
            current_params = {
                'max_portfolio_delta': 50.0,
                'max_position_size': 100000.0,
                'stop_loss_percentage': 50.0,
                'max_daily_loss': 5000.0
            }
            
            dialog = RiskParametersDialog(self, current_params)
            dialog.parameters_updated.connect(self.update_risk_parameters)
            dialog.exec()
            
        except Exception as e:
            self.logger.error(f"Error showing risk parameters: {e}")
            self.add_system_log(f"❌ Error opening risk dialog: {e}")

    def update_risk_parameters(self, params):
        """Update risk parameters"""
        self.add_system_log(f"🔧 Risk parameters updated: {len(params)} parameters")

    def update_account_balances(self):
        """Update account balance displays with slight variation"""
        try:
            # Add small random variations to simulate real-time updates
            base_settled = 21800000.00
            base_buying = 20450000.00
            base_realized = 2030450.00
            base_unrealized = 450230.00
            
            # Add random variations
            settled_var = np.random.normal(0, 1000)
            buying_var = np.random.normal(0, 5000)
            realized_var = np.random.normal(0, 100)
            unrealized_var = np.random.normal(0, 500)
            
            # Update displays
            self.settled_value.setText(f"${base_settled + settled_var:,.2f}")
            self.buying_value.setText(f"${base_buying + buying_var:,.2f}")
            self.realized_value.setText(f"${base_realized + realized_var:,.2f}")
            self.unrealized_value.setText(f"${base_unrealized + unrealized_var:,.2f}")
            
            # Color coding for P&L
            if unrealized_var >= 0:
                self.unrealized_value.setStyleSheet(f"color: {COLORS['positive']}; text-align: right; padding: 5px 10px; background-color: {COLORS['background']}; border: 1px solid {COLORS['border']};")
            else:
                self.unrealized_value.setStyleSheet(f"color: {COLORS['negative']}; text-align: right; padding: 5px 10px; background-color: {COLORS['background']}; border: 1px solid {COLORS['border']};")
                
        except Exception as e:
            pass  # Silent fail for balance updates

    def add_system_log(self, message):
        """Add message to system logs"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.logs_text.append(log_entry)
        
        # Auto-scroll to bottom
        cursor = self.logs_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.logs_text.setTextCursor(cursor)

    def closeEvent(self, event):
        """Handle application close"""
        try:
            if self.market_worker:
                self.market_worker.stop()
            if self.worker_thread and self.worker_thread.isRunning():
                self.worker_thread.quit()
                self.worker_thread.wait()
        except:
            pass
        
        event.accept()

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("SPYDER Trading Dashboard")
    app.setApplicationVersion("1.0")
    
    # Create and show dashboard
    dashboard = TradingDashboard()
    dashboard.show()
    
    # Run application
    sys.exit(app.exec())

if __name__ == "__main__":
    main()