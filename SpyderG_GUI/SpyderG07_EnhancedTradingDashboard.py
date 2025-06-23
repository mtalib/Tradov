#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System
Module: SpyderG07_EnhancedTradingDashboard.py
Group: G (GUI/User Interface)
Purpose: Enhanced PyQt6 trading dashboard with AsyncIO integration

Description:
This module provides a modern, responsive trading dashboard that implements the
proper PyQt6 + ib_insync architecture described in the attached document. It uses
the AsyncIOBridge to handle all broker communications in a separate thread while
maintaining a completely responsive GUI through Qt's signal-slot mechanism.

This solves the fundamental event loop conflict and provides institutional-grade
real-time monitoring and control capabilities.

Author: Mohamed Talib
Created: 2025-06-22
Version: 1.0
"""

# =============================================================================
# Standard Library Imports
# =============================================================================
import sys
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
import json

# Add project root to Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# =============================================================================
# Third-Party Imports
# =============================================================================
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QCheckBox, QGroupBox, QSplitter,
    QTableWidget, QTableWidgetItem, QTextEdit, QDialog, QMessageBox,
    QMenu, QStatusBar, QTabWidget, QProgressBar, QSpinBox, QDoubleSpinBox,
    QFormLayout, QGridLayout, QHeaderView, QFrame
)
from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, pyqtSlot, QThread, QObject,
    QDateTime, QDate, QTime, QSize
)
from PyQt6.QtGui import (
    QFont, QPalette, QColor, QIcon, QPixmap, QAction, QPainter,
    QBrush, QPen
)

# =============================================================================
# Local Application Imports
# =============================================================================
from SpyderB_Broker.SpyderB10_AsyncIOBridge import AsyncIOBridge, ConnectionState
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from ib_insync import Stock, Option, Contract

# =============================================================================
# Constants
# =============================================================================
WINDOW_TITLE = "🕷️ SPYDER v4 - Enhanced Trading Dashboard"
WINDOW_MIN_WIDTH = 1400
WINDOW_MIN_HEIGHT = 900
UPDATE_INTERVAL = 1000  # 1 second GUI updates
STATUS_UPDATE_INTERVAL = 5000  # 5 seconds status updates

# Colors
COLORS = {
    'connected': '#27ae60',
    'disconnected': '#e74c3c', 
    'connecting': '#f39c12',
    'warning': '#ff9800',
    'neutral': '#6c757d',
    'profit': '#28a745',
    'loss': '#dc3545',
    'background': '#f8f9fa',
    'panel': '#ffffff',
    'border': '#dee2e6'
}

# Fonts
FONTS = {
    'header': QFont('Arial', 12, QFont.Weight.Bold),
    'content': QFont('Arial', 10),
    'monospace': QFont('Courier New', 9),
    'small': QFont('Arial', 8)
}

# =============================================================================
# Custom Widgets
# =============================================================================
class StatusIndicator(QLabel):
    """Advanced status indicator with animated states."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(24, 24)
        self.current_state = "disconnected"
        self.setToolTip("Connection Status")
        self.update_status("disconnected")
        
        # Animation timer for connecting state
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._animate)
        self.animation_phase = 0
    
    def update_status(self, state: str):
        """Update the status indicator appearance."""
        self.current_state = state
        
        if state == "connecting":
            self.animation_timer.start(500)  # Animate every 500ms
        else:
            self.animation_timer.stop()
            
        self._update_appearance()
    
    def _animate(self):
        """Animate the connecting state."""
        self.animation_phase = (self.animation_phase + 1) % 3
        self._update_appearance()
    
    def _update_appearance(self):
        """Update the visual appearance."""
        if self.current_state == "connected":
            color = COLORS['connected']
            border_color = COLORS['connected']
        elif self.current_state == "disconnected":
            color = COLORS['disconnected']
            border_color = COLORS['disconnected']
        elif self.current_state == "connecting":
            # Animate between orange and yellow
            if self.animation_phase == 0:
                color = COLORS['connecting']
            else:
                color = '#ffeb3b'  # Brighter yellow
            border_color = COLORS['connecting']
        else:
            color = COLORS['neutral']
            border_color = COLORS['neutral']
        
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                border: 2px solid {border_color};
                border-radius: 12px;
            }}
        """)

class RealTimeTable(QTableWidget):
    """Enhanced table widget with real-time updates."""
    
    def __init__(self, headers: List[str], parent=None):
        super().__init__(parent)
        self.setup_table(headers)
        self.data_cache = {}
        
    def setup_table(self, headers: List[str]):
        """Setup the table with headers and styling."""
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)
        
        # Auto-resize columns
        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        
        # Style the table
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setStyleSheet("""
            QTableWidget {
                gridline-color: #ddd;
                background-color: white;
                border: 1px solid #ddd;
            }
            QTableWidget::item {
                padding: 8px;
                border: none;
            }
            QTableWidget::item:selected {
                background-color: #007bff;
                color: white;
            }
            QHeaderView::section {
                background-color: #f8f9fa;
                border: 1px solid #ddd;
                padding: 8px;
                font-weight: bold;
            }
        """)
    
    def update_row_data(self, key: str, data: Dict[str, Any]):
        """Update or add a row of data."""
        self.data_cache[key] = data
        self._refresh_display()
    
    def remove_row_data(self, key: str):
        """Remove a row of data."""
        if key in self.data_cache:
            del self.data_cache[key]
            self._refresh_display()
    
    def _refresh_display(self):
        """Refresh the table display."""
        self.setRowCount(len(self.data_cache))
        
        for row, (key, data) in enumerate(self.data_cache.items()):
            for col, header in enumerate([self.horizontalHeaderItem(i).text() 
                                        for i in range(self.columnCount())]):
                value = data.get(header.lower().replace(' ', '_'), '')
                
                item = QTableWidgetItem(str(value))
                
                # Color coding for P&L
                if 'pnl' in header.lower() or 'p&l' in header.lower():
                    try:
                        pnl_value = float(value) if value else 0
                        if pnl_value > 0:
                            item.setBackground(QColor(COLORS['profit']).lighter(180))
                        elif pnl_value < 0:
                            item.setBackground(QColor(COLORS['loss']).lighter(180))
                    except (ValueError, TypeError):
                        pass
                
                self.setItem(row, col, item)

class LogDisplay(QTextEdit):
    """Enhanced log display with filtering and search."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumHeight(200)
        self.setFont(FONTS['monospace'])
        self.max_lines = 1000
        self.current_lines = 0
        
        self.setStyleSheet("""
            QTextEdit {
                background-color: #2c3e50;
                color: #ecf0f1;
                border: 1px solid #34495e;
                padding: 5px;
            }
        """)
    
    def append_log(self, level: str, message: str, timestamp: datetime = None):
        """Append a log message with proper formatting."""
        if timestamp is None:
            timestamp = datetime.now()
        
        # Color coding by level
        color_map = {
            'ERROR': '#e74c3c',
            'WARNING': '#f39c12', 
            'INFO': '#3498db',
            'DEBUG': '#95a5a6',
            'SUCCESS': '#27ae60'
        }
        
        color = color_map.get(level.upper(), '#ecf0f1')
        time_str = timestamp.strftime('%H:%M:%S')
        
        formatted_message = f"""
        <span style="color: #bdc3c7;">[{time_str}]</span>
        <span style="color: {color}; font-weight: bold;">{level}</span>
        <span style="color: #ecf0f1;"> {message}</span>
        """
        
        self.append(formatted_message)
        
        # Limit lines to prevent memory bloat
        self.current_lines += 1
        if self.current_lines > self.max_lines:
            self._trim_old_lines()
    
    def _trim_old_lines(self):
        """Remove old lines to keep memory usage reasonable."""
        text = self.toPlainText()
        lines = text.split('\n')
        if len(lines) > self.max_lines:
            # Keep last 80% of lines
            keep_lines = int(self.max_lines * 0.8)
            new_text = '\n'.join(lines[-keep_lines:])
            self.clear()
            self.setPlainText(new_text)
            self.current_lines = keep_lines

# =============================================================================
# Main Dashboard Implementation
# =============================================================================
class EnhancedTradingDashboard(QMainWindow):
    """
    Enhanced trading dashboard with proper AsyncIO integration.
    
    This implements the architecture described in the attached document,
    using the AsyncIOBridge to handle all broker communications while
    maintaining a completely responsive GUI.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the enhanced trading dashboard.
        
        Args:
            config: Configuration dictionary for IB connection
        """
        super().__init__()
        
        # Configuration
        self.config = config or {
            'ib': {
                'host': '127.0.0.1',
                'port': 4002,  # Paper trading
                'client_id': 1
            }
        }
        
        # Utilities
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Data storage
        self.market_data = {}
        self.positions_data = {}
        self.orders_data = {}
        self.account_data = {}
        
        # UI Components (will be initialized in setup_ui)
        self.connection_indicator = None
        self.status_label = None
        self.log_display = None
        self.positions_table = None
        self.orders_table = None
        self.market_data_table = None
        
        # Create the AsyncIO bridge
        self.setup_async_bridge()
        
        # Initialize UI
        self.setup_ui()
        self.setup_timers()
        self.setup_connections()
        
        # Start the async worker
        self.start_async_operations()
        
        self.logger.info("Enhanced Trading Dashboard initialized")
    
    def setup_async_bridge(self):
        """Setup the AsyncIO bridge with proper threading."""
        ib_config = self.config.get('ib', {})
        
        self.async_bridge = AsyncIOBridge(
            host=ib_config.get('host', '127.0.0.1'),
            port=ib_config.get('port', 4002),
            client_id=ib_config.get('client_id', 1)
        )
        
        # Move bridge to worker thread (proper Qt threading)
        self.bridge_thread = QThread()
        self.async_bridge.moveToThread(self.bridge_thread)
        
        # Connect thread lifecycle
        self.bridge_thread.started.connect(self.async_bridge.start_async_worker)
        self.bridge_thread.finished.connect(self.async_bridge.deleteLater)
    
    def setup_ui(self):
        """Setup the user interface with modern design."""
        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.resize(1600, 1000)
        
        # Central widget with main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout - horizontal split
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Create main splitter
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(main_splitter)
        
        # Left panel - Controls and Status
        left_panel = self.create_control_panel()
        main_splitter.addWidget(left_panel)
        
        # Center panel - Tables and Data
        center_panel = self.create_data_panel()
        main_splitter.addWidget(center_panel)
        
        # Right panel - Charts and Analysis (placeholder for now)
        right_panel = self.create_analysis_panel()
        main_splitter.addWidget(right_panel)
        
        # Set splitter proportions
        main_splitter.setSizes([300, 800, 300])
        
        # Status bar
        self.setup_status_bar()
        
        # Apply global styling
        self.apply_global_styling()
    
    def create_control_panel(self) -> QWidget:
        """Create the left control panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Connection section
        conn_group = QGroupBox("🔗 Connection")
        conn_layout = QVBoxLayout(conn_group)
        
        # Connection status
        status_layout = QHBoxLayout()
        self.connection_indicator = StatusIndicator()
        self.status_label = QLabel("Disconnected")
        self.status_label.setFont(FONTS['content'])
        status_layout.addWidget(self.connection_indicator)
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        conn_layout.addLayout(status_layout)
        
        # Connection controls
        self.connect_btn = QPushButton("🔌 Connect")
        self.disconnect_btn = QPushButton("🔌 Disconnect")
        self.disconnect_btn.setEnabled(False)
        
        conn_layout.addWidget(self.connect_btn)
        conn_layout.addWidget(self.disconnect_btn)
        
        layout.addWidget(conn_group)
        
        # Trading controls
        trading_group = QGroupBox("📊 Trading Controls")
        trading_layout = QVBoxLayout(trading_group)
        
        self.start_trading_btn = QPushButton("▶️ Start Trading")
        self.stop_trading_btn = QPushButton("⏹️ Stop Trading")
        self.emergency_stop_btn = QPushButton("🛑 EMERGENCY STOP")
        
        self.start_trading_btn.setEnabled(False)
        self.stop_trading_btn.setEnabled(False)
        
        # Style emergency stop button
        self.emergency_stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                font-weight: bold;
                border: none;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        
        trading_layout.addWidget(self.start_trading_btn)
        trading_layout.addWidget(self.stop_trading_btn)
        trading_layout.addWidget(self.emergency_stop_btn)
        
        layout.addWidget(trading_group)
        
        # Market data controls
        data_group = QGroupBox("📈 Market Data")
        data_layout = QVBoxLayout(data_group)
        
        # Symbol selection
        symbol_layout = QFormLayout()
        self.symbol_combo = QComboBox()
        self.symbol_combo.addItems(['SPY', 'QQQ', 'IWM', 'VIX'])
        self.symbol_combo.setCurrentText('SPY')
        symbol_layout.addRow("Symbol:", self.symbol_combo)
        
        # Data type selection
        self.data_type_combo = QComboBox()
        self.data_type_combo.addItems(['Stock', 'Options Chain', 'Both'])
        self.data_type_combo.setCurrentText('Both')
        symbol_layout.addRow("Data Type:", self.data_type_combo)
        
        data_layout.addLayout(symbol_layout)
        
        # Data control buttons
        self.request_data_btn = QPushButton("📊 Request Data")
        self.stop_data_btn = QPushButton("⏹️ Stop Data")
        self.request_data_btn.setEnabled(False)
        self.stop_data_btn.setEnabled(False)
        
        data_layout.addWidget(self.request_data_btn)
        data_layout.addWidget(self.stop_data_btn)
        
        layout.addWidget(data_group)
        
        # Account info
        account_group = QGroupBox("💰 Account Summary")
        account_layout = QFormLayout(account_group)
        
        self.net_liq_label = QLabel("$0.00")
        self.buying_power_label = QLabel("$0.00")
        self.day_pnl_label = QLabel("$0.00")
        
        account_layout.addRow("Net Liquidation:", self.net_liq_label)
        account_layout.addRow("Buying Power:", self.buying_power_label)
        account_layout.addRow("Day P&L:", self.day_pnl_label)
        
        layout.addWidget(account_group)
        
        # Stretch to push everything to top
        layout.addStretch()
        
        return panel
    
    def create_data_panel(self) -> QWidget:
        """Create the center data panel with tabs."""
        tab_widget = QTabWidget()
        
        # Positions tab
        positions_widget = QWidget()
        positions_layout = QVBoxLayout(positions_widget)
        
        positions_label = QLabel("💼 Current Positions")
        positions_label.setFont(FONTS['header'])
        positions_layout.addWidget(positions_label)
        
        self.positions_table = RealTimeTable([
            'Symbol', 'Type', 'Position', 'Market Price', 'Market Value', 
            'Avg Cost', 'Unrealized P&L', 'Realized P&L'
        ])
        positions_layout.addWidget(self.positions_table)
        
        tab_widget.addTab(positions_widget, "📊 Positions")
        
        # Orders tab
        orders_widget = QWidget()
        orders_layout = QVBoxLayout(orders_widget)
        
        orders_label = QLabel("📋 Active Orders")
        orders_label.setFont(FONTS['header'])
        orders_layout.addWidget(orders_label)
        
        self.orders_table = RealTimeTable([
            'Order ID', 'Symbol', 'Type', 'Action', 'Quantity', 
            'Price', 'Status', 'Filled', 'Remaining'
        ])
        orders_layout.addWidget(self.orders_table)
        
        tab_widget.addTab(orders_widget, "📋 Orders")
        
        # Market Data tab
        market_widget = QWidget()
        market_layout = QVBoxLayout(market_widget)
        
        market_label = QLabel("📈 Market Data")
        market_label.setFont(FONTS['header'])
        market_layout.addWidget(market_label)
        
        self.market_data_table = RealTimeTable([
            'Symbol', 'Type', 'Bid', 'Ask', 'Last', 'Volume', 'Change'
        ])
        market_layout.addWidget(self.market_data_table)
        
        tab_widget.addTab(market_widget, "📈 Market Data")
        
        # Logs tab
        logs_widget = QWidget()
        logs_layout = QVBoxLayout(logs_widget)
        
        logs_label = QLabel("📝 System Logs")
        logs_label.setFont(FONTS['header'])
        logs_layout.addWidget(logs_label)
        
        self.log_display = LogDisplay()
        logs_layout.addWidget(self.log_display)
        
        # Log controls
        log_controls = QHBoxLayout()
        clear_logs_btn = QPushButton("🗑️ Clear")
        export_logs_btn = QPushButton("💾 Export")
        log_controls.addWidget(clear_logs_btn)
        log_controls.addWidget(export_logs_btn)
        log_controls.addStretch()
        logs_layout.addLayout(log_controls)
        
        clear_logs_btn.clicked.connect(self.log_display.clear)
        
        tab_widget.addTab(logs_widget, "📝 Logs")
        
        return tab_widget
    
    def create_analysis_panel(self) -> QWidget:
        """Create the right analysis panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Risk metrics
        risk_group = QGroupBox("⚠️ Risk Metrics")
        risk_layout = QFormLayout(risk_group)
        
        self.portfolio_delta_label = QLabel("0.00")
        self.portfolio_gamma_label = QLabel("0.00")
        self.portfolio_theta_label = QLabel("0.00")
        self.portfolio_vega_label = QLabel("0.00")
        
        risk_layout.addRow("Portfolio Delta:", self.portfolio_delta_label)
        risk_layout.addRow("Portfolio Gamma:", self.portfolio_gamma_label)
        risk_layout.addRow("Portfolio Theta:", self.portfolio_theta_label)
        risk_layout.addRow("Portfolio Vega:", self.portfolio_vega_label)
        
        layout.addWidget(risk_group)
        
        # Performance metrics
        perf_group = QGroupBox("📊 Performance")
        perf_layout = QFormLayout(perf_group)
        
        self.total_pnl_label = QLabel("$0.00")
        self.day_pnl_percent_label = QLabel("0.00%")
        self.win_rate_label = QLabel("0.00%")
        self.sharpe_ratio_label = QLabel("0.00")
        
        perf_layout.addRow("Total P&L:", self.total_pnl_label)
        perf_layout.addRow("Day P&L %:", self.day_pnl_percent_label)
        perf_layout.addRow("Win Rate:", self.win_rate_label)
        perf_layout.addRow("Sharpe Ratio:", self.sharpe_ratio_label)
        
        layout.addWidget(perf_group)
        
        # System status
        system_group = QGroupBox("🖥️ System Status")
        system_layout = QFormLayout(system_group)
        
        self.cpu_usage_label = QLabel("0%")
        self.memory_usage_label = QLabel("0%")
        self.uptime_label = QLabel("00:00:00")
        self.last_update_label = QLabel("Never")
        
        system_layout.addRow("CPU Usage:", self.cpu_usage_label)
        system_layout.addRow("Memory Usage:", self.memory_usage_label)
        system_layout.addRow("Uptime:", self.uptime_label)
        system_layout.addRow("Last Update:", self.last_update_label)
        
        layout.addWidget(system_group)
        
        layout.addStretch()
        return panel
    
    def setup_status_bar(self):
        """Setup the status bar."""
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        
        # Connection status in status bar
        self.status_bar_label = QLabel("Ready")
        status_bar.addWidget(self.status_bar_label)
        
        # Progress bar for operations
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        status_bar.addPermanentWidget(self.progress_bar)
        
        # Clock
        self.clock_label = QLabel()
        self.clock_label.setFont(FONTS['monospace'])
        status_bar.addPermanentWidget(self.clock_label)
    
    def setup_timers(self):
        """Setup update timers."""
        # Main update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(UPDATE_INTERVAL)
        
        # Status update timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(STATUS_UPDATE_INTERVAL)
        
        # Clock timer
        self.clock_timer = QTimer()
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)  # Update every second
    
    def setup_connections(self):
        """Setup signal-slot connections."""
        # Button connections
        self.connect_btn.clicked.connect(self.connect_to_broker)
        self.disconnect_btn.clicked.connect(self.disconnect_from_broker)
        self.request_data_btn.clicked.connect(self.request_market_data)
        self.stop_data_btn.clicked.connect(self.stop_market_data)
        self.emergency_stop_btn.clicked.connect(self.emergency_stop)
        
        # AsyncIO bridge connections
        self.async_bridge.connection_status_changed.connect(self.on_connection_status_changed)
        self.async_bridge.market_data_received.connect(self.on_market_data_received)
        self.async_bridge.ticker_updated.connect(self.on_ticker_update