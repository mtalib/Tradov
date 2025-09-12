#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG05_TradingDashboard.py
Purpose: Main trading dashboard with PySide6 and async IB Gateway integration
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-01-22 Time: 11:00:00

Module Description:
    Advanced trading dashboard built with PySide6 featuring native asyncio integration
    for stable IB Gateway connectivity. This module provides the main user interface
    for the Spyder trading system, including real-time market data display, position
    monitoring, order management, and strategy controls. Migrated from PyQt6 to
    PySide6 for improved async support and connection stability.
    
    [Migrated from PyQt6 to PySide6 on 2025-01-22]
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import os
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import logging

# ==============================================================================
# THIRD-PARTY IMPORTS - PYSIDE6
# ==============================================================================
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QTabWidget,
    QGroupBox, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
    QTextEdit, QSplitter, QFrame, QHeaderView, QMessageBox,
    QApplication, QStyle, QProgressBar, QMenuBar, QMenu,
    QStatusBar, QToolBar, QDockWidget
)
from PySide6.QtCore import (
    Qt, QTimer, Signal, Slot, QThread, QObject,
    QDateTime, QTime, QSize, QRect, Property
)
from PySide6.QtGui import (
    QFont, QColor, QPalette, QBrush, QAction,
    QIcon, QPixmap, QPainter, QLinearGradient
)

# PySide6 Asyncio support
try:
    from PySide6.QtAsyncio import QAsyncioEventLoopPolicy
    ASYNC_SUPPORT = True
except ImportError:
    ASYNC_SUPPORT = False
    print("⚠️  QtAsyncio not available - running without async support")

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from SpyderB_Broker.SpyderB26_PySideAsyncBridge import AsyncIBGatewayBridge
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
    BRIDGE_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Some modules not available: {e}")
    BRIDGE_AVAILABLE = False

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Window settings
WINDOW_TITLE = "SPYDER Trading Dashboard - PySide6"
WINDOW_WIDTH = 1600
WINDOW_HEIGHT = 900

# Update intervals (ms)
MARKET_DATA_UPDATE = 1000
POSITION_UPDATE = 5000
ACCOUNT_UPDATE = 10000
CLOCK_UPDATE = 1000

# Color scheme
COLOR_BACKGROUND = "#1a1a1a"
COLOR_PANEL = "#252525"
COLOR_TEXT = "#e0e0e0"
COLOR_POSITIVE = "#00ff88"
COLOR_NEGATIVE = "#ff4444"
COLOR_NEUTRAL = "#ffaa00"
COLOR_BORDER = "#404040"

# ==============================================================================
# ASYNC WORKER THREAD
# ==============================================================================
class AsyncWorker(QThread):
    """
    Worker thread for handling async operations with IB Gateway.
    """
    
    # Signals
    data_received = Signal(dict)
    connection_status = Signal(bool)
    error_occurred = Signal(str)
    
    def __init__(self, bridge: Optional[AsyncIBGatewayBridge] = None):
        """Initialize async worker"""
        super().__init__()
        self.bridge = bridge
        self.running = False
        self.loop = None
        
    def run(self):
        """Run async event loop in thread"""
        if ASYNC_SUPPORT:
            # Set up async event loop
            asyncio.set_event_loop_policy(QAsyncioEventLoopPolicy())
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            # Run async tasks
            self.running = True
            self.loop.run_until_complete(self._async_main())
        else:
            # Fallback to synchronous operation
            self.running = True
            while self.running:
                self.msleep(100)
    
    async def _async_main(self):
        """Main async loop"""
        while self.running:
            try:
                # Check connection
                if self.bridge and self.bridge.is_connected():
                    self.connection_status.emit(True)
                    
                    # Fetch data asynchronously
                    positions = await self.bridge.request_positions()
                    if positions:
                        self.data_received.emit({'positions': positions})
                    
                    account = await self.bridge.request_account_summary()
                    if account:
                        self.data_received.emit({'account': account})
                else:
                    self.connection_status.emit(False)
                
                await asyncio.sleep(1)
                
            except Exception as e:
                self.error_occurred.emit(str(e))
                await asyncio.sleep(5)
    
    def stop(self):
        """Stop the worker thread"""
        self.running = False
        if self.loop:
            self.loop.stop()

# ==============================================================================
# MARKET DATA WIDGET
# ==============================================================================
class MarketDataWidget(QWidget):
    """Widget for displaying real-time market data"""
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the UI"""
        layout = QGridLayout()
        
        # Title
        title = QLabel("Market Data")
        title.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 16px; font-weight: bold;")
        layout.addWidget(title, 0, 0, 1, 4)
        
        # Headers
        headers = ["Symbol", "Last", "Change", "Volume"]
        for i, header in enumerate(headers):
            label = QLabel(header)
            label.setStyleSheet(f"color: {COLOR_TEXT}; font-weight: bold;")
            layout.addWidget(label, 1, i)
        
        # SPY data
        self.spy_symbol = QLabel("SPY")
        self.spy_last = QLabel("0.00")
        self.spy_change = QLabel("0.00 (0.00%)")
        self.spy_volume = QLabel("0")
        
        layout.addWidget(self.spy_symbol, 2, 0)
        layout.addWidget(self.spy_last, 2, 1)
        layout.addWidget(self.spy_change, 2, 2)
        layout.addWidget(self.spy_volume, 2, 3)
        
        # Style
        for label in [self.spy_symbol, self.spy_last, self.spy_change, self.spy_volume]:
            label.setStyleSheet(f"color: {COLOR_TEXT};")
        
        self.setLayout(layout)
    
    @Slot(dict)
    def update_data(self, data: Dict):
        """Update market data display"""
        if 'SPY' in data:
            spy_data = data['SPY']
            self.spy_last.setText(f"{spy_data.get('last', 0):.2f}")
            
            change = spy_data.get('change', 0)
            change_pct = spy_data.get('change_pct', 0)
            self.spy_change.setText(f"{change:.2f} ({change_pct:.2f}%)")
            
            # Color based on change
            color = COLOR_POSITIVE if change >= 0 else COLOR_NEGATIVE
            self.spy_change.setStyleSheet(f"color: {color};")
            
            self.spy_volume.setText(f"{spy_data.get('volume', 0):,}")

# ==============================================================================
# POSITION WIDGET
# ==============================================================================
class PositionWidget(QWidget):
    """Widget for displaying current positions"""
    
    # Signals
    close_position = Signal(str)
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the UI"""
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Open Positions")
        title.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 16px; font-weight: bold;")
        layout.addWidget(title)
        
        # Position table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Symbol", "Type", "Qty", "Entry", "Current", "P&L", "P&L %", "Action"
        ])
        
        # Style
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {COLOR_PANEL};
                color: {COLOR_TEXT};
                border: 1px solid {COLOR_BORDER};
            }}
            QHeaderView::section {{
                background-color: {COLOR_BACKGROUND};
                color: {COLOR_TEXT};
                border: 1px solid {COLOR_BORDER};
            }}
        """)
        
        layout.addWidget(self.table)
        self.setLayout(layout)
    
    @Slot(list)
    def update_positions(self, positions: List[Dict]):
        """Update position display"""
        self.table.setRowCount(len(positions))
        
        for row, pos in enumerate(positions):
            # Symbol
            self.table.setItem(row, 0, QTableWidgetItem(pos.get('symbol', '')))
            
            # Type
            pos_type = "Long" if pos.get('position', 0) > 0 else "Short"
            self.table.setItem(row, 1, QTableWidgetItem(pos_type))
            
            # Quantity
            self.table.setItem(row, 2, QTableWidgetItem(str(abs(pos.get('position', 0)))))
            
            # Entry price
            self.table.setItem(row, 3, QTableWidgetItem(f"{pos.get('avg_cost', 0):.2f}"))
            
            # Current price (placeholder)
            current = pos.get('current', pos.get('avg_cost', 0))
            self.table.setItem(row, 4, QTableWidgetItem(f"{current:.2f}"))
            
            # P&L calculation
            qty = pos.get('position', 0)
            entry = pos.get('avg_cost', 0)
            pnl = (current - entry) * qty
            pnl_pct = ((current / entry - 1) * 100) if entry != 0 else 0
            
            pnl_item = QTableWidgetItem(f"{pnl:.2f}")
            pnl_item.setForeground(QBrush(QColor(COLOR_POSITIVE if pnl >= 0 else COLOR_NEGATIVE)))
            self.table.setItem(row, 5, pnl_item)
            
            pnl_pct_item = QTableWidgetItem(f"{pnl_pct:.2f}%")
            pnl_pct_item.setForeground(QBrush(QColor(COLOR_POSITIVE if pnl_pct >= 0 else COLOR_NEGATIVE)))
            self.table.setItem(row, 6, pnl_pct_item)
            
            # Action button
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(lambda _, s=pos.get('symbol'): self.close_position.emit(s))
            self.table.setCellWidget(row, 7, close_btn)

# ==============================================================================
# MAIN TRADING DASHBOARD
# ==============================================================================
class TradingDashboard(QMainWindow):
    """
    Main trading dashboard window with PySide6 and async support.
    """
    
    def __init__(self):
        """Initialize the trading dashboard"""
        super().__init__()
        
        # Setup logging
        self.logger = SpyderLogger.get_logger(self.__class__.__name__) if 'SpyderLogger' in globals() else logging.getLogger(__name__)
        
        # IB Gateway bridge
        self.bridge = None
        self.async_worker = None
        
        # UI components
        self.market_widget = None
        self.position_widget = None
        self.status_label = None
        
        # Timers
        self.clock_timer = QTimer()
        self.update_timer = QTimer()
        
        # Setup
        self.setup_ui()
        self.setup_connections()
        self.setup_timers()
        
        # Initialize async if available
        if ASYNC_SUPPORT and BRIDGE_AVAILABLE:
            self.initialize_async_bridge()
        
        self.logger.info("✅ Trading Dashboard initialized with PySide6")
    
    # ==========================================================================
    # UI SETUP
    # ==========================================================================
    def setup_ui(self):
        """Setup the main UI"""
        self.setWindowTitle(WINDOW_TITLE)
        self.setGeometry(100, 100, WINDOW_WIDTH, WINDOW_HEIGHT)
        
        # Set dark theme
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {COLOR_BACKGROUND};
            }}
            QWidget {{
                background-color: {COLOR_BACKGROUND};
                color: {COLOR_TEXT};
            }}
            QPushButton {{
                background-color: {COLOR_PANEL};
                color: {COLOR_TEXT};
                border: 1px solid {COLOR_BORDER};
                padding: 5px;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                background-color: {COLOR_BORDER};
            }}
        """)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Header
        header = self.create_header()
        main_layout.addWidget(header)
        
        # Content area with splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel - Market data and controls
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)
        
        # Right panel - Positions and orders
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)
        
        splitter.setSizes([WINDOW_WIDTH // 2, WINDOW_WIDTH // 2])
        main_layout.addWidget(splitter)
        
        # Status bar
        self.create_status_bar()
        
        # Menu bar
        self.create_menu_bar()
        
        # Toolbar
        self.create_toolbar()
    
    def create_header(self) -> QWidget:
        """Create header widget"""
        header = QWidget()
        header.setFixedHeight(60)
        header.setStyleSheet(f"background-color: {COLOR_PANEL}; border-bottom: 2px solid {COLOR_BORDER};")
        
        layout = QHBoxLayout()
        
        # Logo/Title
        title = QLabel("SPYDER")
        title.setStyleSheet(f"""
            color: {COLOR_POSITIVE};
            font-size: 24px;
            font-weight: bold;
            padding: 10px;
        """)
        layout.addWidget(title)
        
        # System status
        self.system_status = QLabel("System: Initializing")
        self.system_status.setStyleSheet(f"color: {COLOR_NEUTRAL};")
        layout.addWidget(self.system_status)
        
        layout.addStretch()
        
        # Clock
        self.clock_label = QLabel()
        self.clock_label.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 14px; padding: 10px;")
        layout.addWidget(self.clock_label)
        
        # Connection status
        self.connection_status = QLabel("IB Gateway: Disconnected")
        self.connection_status.setStyleSheet(f"color: {COLOR_NEGATIVE}; padding: 10px;")
        layout.addWidget(self.connection_status)
        
        header.setLayout(layout)
        return header
    
    def create_left_panel(self) -> QWidget:
        """Create left panel with market data and controls"""
        panel = QWidget()
        layout = QVBoxLayout()
        
        # Market data widget
        self.market_widget = MarketDataWidget()
        layout.addWidget(self.market_widget)
        
        # Strategy controls
        strategy_group = QGroupBox("Strategy Controls")
        strategy_group.setStyleSheet(f"""
            QGroupBox {{
                color: {COLOR_TEXT};
                border: 1px solid {COLOR_BORDER};
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }}
        """)
        
        strategy_layout = QVBoxLayout()
        
        # Strategy selector
        strategy_row = QHBoxLayout()
        strategy_row.addWidget(QLabel("Strategy:"))
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems(["Iron Condor", "Credit Spread", "Straddle", "Strangle"])
        strategy_row.addWidget(self.strategy_combo)
        strategy_layout.addLayout(strategy_row)
        
        # Action buttons
        button_row = QHBoxLayout()
        
        self.start_btn = QPushButton("Start Trading")
        self.start_btn.setStyleSheet(f"background-color: {COLOR_POSITIVE}; color: black;")
        self.start_btn.clicked.connect(self.start_trading)
        button_row.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("Stop Trading")
        self.stop_btn.setStyleSheet(f"background-color: {COLOR_NEGATIVE};")
        self.stop_btn.clicked.connect(self.stop_trading)
        self.stop_btn.setEnabled(False)
        button_row.addWidget(self.stop_btn)
        
        strategy_layout.addLayout(button_row)
        strategy_group.setLayout(strategy_layout)
        
        layout.addWidget(strategy_group)
        layout.addStretch()
        
        panel.setLayout(layout)
        return panel
    
    def create_right_panel(self) -> QWidget:
        """Create right panel with positions and orders"""
        panel = QWidget()
        layout = QVBoxLayout()
        
        # Tab widget
        tabs = QTabWidget()
        tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {COLOR_BORDER};
                background-color: {COLOR_PANEL};
            }}
            QTabBar::tab {{
                background-color: {COLOR_BACKGROUND};
                color: {COLOR_TEXT};
                padding: 8px;
            }}
            QTabBar::tab:selected {{
                background-color: {COLOR_PANEL};
                border-bottom: 2px solid {COLOR_POSITIVE};
            }}
        """)
        
        # Positions tab
        self.position_widget = PositionWidget()
        tabs.addTab(self.position_widget, "Positions")
        
        # Orders tab
        orders_widget = QWidget()
        orders_layout = QVBoxLayout()
        orders_layout.addWidget(QLabel("Order Management"))
        orders_widget.setLayout(orders_layout)
        tabs.addTab(orders_widget, "Orders")
        
        # Logs tab
        self.log_widget = QTextEdit()
        self.log_widget.setReadOnly(True)
        self.log_widget.setStyleSheet(f"""
            background-color: {COLOR_BACKGROUND};
            color: {COLOR_TEXT};
            font-family: 'Consolas', 'Monaco', monospace;
        """)
        tabs.addTab(self.log_widget, "Logs")
        
        layout.addWidget(tabs)
        panel.setLayout(layout)
        return panel
    
    def create_status_bar(self):
        """Create status bar"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Add permanent widgets
        self.status_label = QLabel("Ready")
        self.status_bar.addPermanentWidget(self.status_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)
    
    def create_menu_bar(self):
        """Create menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        connect_action = QAction("Connect to IB", self)
        connect_action.triggered.connect(self.connect_to_ib)
        file_menu.addAction(connect_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Tools menu
        tools_menu = menubar.addMenu("Tools")
        
        settings_action = QAction("Settings", self)
        tools_menu.addAction(settings_action)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def create_toolbar(self):
        """Create toolbar"""
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        
        # Connect button
        connect_action = QAction("Connect", self)
        connect_action.triggered.connect(self.connect_to_ib)
        toolbar.addAction(connect_action)
        
        toolbar.addSeparator()
        
        # Trading controls
        start_action = QAction("Start", self)
        start_action.triggered.connect(self.start_trading)
        toolbar.addAction(start_action)
        
        stop_action = QAction("Stop", self)
        stop_action.triggered.connect(self.stop_trading)
        toolbar.addAction(stop_action)
    
    # ==========================================================================
    # CONNECTIONS
    # ==========================================================================
    def setup_connections(self):
        """Setup signal/slot connections"""
        if self.position_widget:
            self.position_widget.close_position.connect(self.handle_close_position)
    
    def setup_timers(self):
        """Setup update timers"""
        # Clock timer
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(CLOCK_UPDATE)
        
        # Update timer for data refresh
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(MARKET_DATA_UPDATE)
    
    # ==========================================================================
    # ASYNC BRIDGE
    # ==========================================================================
    def initialize_async_bridge(self):
        """Initialize async IB Gateway bridge"""
        try:
            # Create bridge
            self.bridge = AsyncIBGatewayBridge(paper_trading=True)
            
            # Connect signals
            self.bridge.connected.connect(self.on_ib_connected)
            self.bridge.disconnected.connect(self.on_ib_disconnected)
            self.bridge.error_occurred.connect(self.on_ib_error)
            self.bridge.market_data_received.connect(self.on_market_data)
            self.bridge.position_updated.connect(self.on_position_update)
            
            # Create async worker
            self.async_worker = AsyncWorker(self.bridge)
            self.async_worker.data_received.connect(self.on_async_data)
            self.async_worker.connection_status.connect(self.on_connection_status)
            self.async_worker.error_occurred.connect(self.on_async_error)
            
            self.log_message("✅ Async bridge initialized with PySide6")
            
        except Exception as e:
            self.log_message(f"❌ Failed to initialize async bridge: {e}")
    
    # ==========================================================================
    # SLOTS
    # ==========================================================================
    @Slot()
    def connect_to_ib(self):
        """Connect to IB Gateway"""
        self.log_message("🔄 Connecting to IB Gateway...")
        self.connection_status.setText("IB Gateway: Connecting...")
        self.connection_status.setStyleSheet(f"color: {COLOR_NEUTRAL}; padding: 10px;")
        
        if self.bridge:
            # Initialize async loop
            if self.bridge.initialize_async_loop():
                # Start async connection
                asyncio.create_task(self.bridge.connect_async())
                
                # Start worker thread
                if self.async_worker and not self.async_worker.isRunning():
                    self.async_worker.start()
    
    @Slot()
    def start_trading(self):
        """Start trading"""
        strategy = self.strategy_combo.currentText()
        self.log_message(f"▶️ Starting {strategy} strategy")
        
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.system_status.setText(f"System: Trading - {strategy}")
        self.system_status.setStyleSheet(f"color: {COLOR_POSITIVE};")
    
    @Slot()
    def stop_trading(self):
        """Stop trading"""
        self.log_message("⏸️ Stopping trading")
        
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.system_status.setText("System: Stopped")
        self.system_status.setStyleSheet(f"color: {COLOR_NEGATIVE};")
    
    @Slot()
    def on_ib_connected(self):
        """Handle IB connection"""
        self.connection_status.setText("IB Gateway: Connected")
        self.connection_status.setStyleSheet(f"color: {COLOR_POSITIVE}; padding: 10px;")
        self.log_message("✅ Connected to IB Gateway")
    
    @Slot()
    def on_ib_disconnected(self):
        """Handle IB disconnection"""
        self.connection_status.setText("IB Gateway: Disconnected")
        self.connection_status.setStyleSheet(f"color: {COLOR_NEGATIVE}; padding: 10px;")
        self.log_message("🔌 Disconnected from IB Gateway")
    
    @Slot(str)
    def on_ib_error(self, error: str):
        """Handle IB error"""
        self.log_message(f"❌ IB Error: {error}")
    
    @Slot(dict)
    def on_market_data(self, data: Dict):
        """Handle market data update"""
        if self.market_widget:
            self.market_widget.update_data({'SPY': data})
    
    @Slot(dict)
    def on_position_update(self, data: Dict):
        """Handle position update"""
        # Update position display
        pass
    
    @Slot(dict)
    def on_async_data(self, data: Dict):
        """Handle async data from worker"""
        if 'positions' in data and self.position_widget:
            self.position_widget.update_positions(data['positions'])
        
        if 'account' in data:
            # Update account display
            pass
    
    @Slot(bool)
    def on_connection_status(self, connected: bool):
        """Handle connection status update"""
        if connected:
            self.connection_status.setText("IB Gateway: Connected")
            self.connection_status.setStyleSheet(f"color: {COLOR_POSITIVE}; padding: 10px;")
        else:
            self.connection_status.setText("IB Gateway: Disconnected")
            self.connection_status.setStyleSheet(f"color: {COLOR_NEGATIVE}; padding: 10px;")
    
    @Slot(str)
    def on_async_error(self, error: str):
        """Handle async error"""
        self.log_message(f"⚠️ Async Error: {error}")
    
    @Slot(str)
    def handle_close_position(self, symbol: str):
        """Handle close position request"""
        self.log_message(f"📉 Closing position: {symbol}")
        
        reply = QMessageBox.question(
            self,
            "Confirm Close",
            f"Close position for {symbol}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Close position logic here
            self.log_message(f"✅ Position closed: {symbol}")
    
    @Slot()
    def update_clock(self):
        """Update clock display"""
        current_time = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
        self.clock_label.setText(current_time)
    
    @Slot()
    def update_display(self):
        """Update display"""
        # Periodic updates
        pass
    
    @Slot()
    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            "About SPYDER",
            "SPYDER - Autonomous Options Trading System\n"
            "Version 1.0\n"
            "Built with PySide6 and QtAsyncio\n\n"
            "Author: Mohamed Talib\n"
            "© 2025"
        )
    
    # ==========================================================================
    # UTILITIES
    # ==========================================================================
    def log_message(self, message: str):
        """Add message to log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        if self.log_widget:
            self.log_widget.append(formatted_message)
        
        # Also log to file
        self.logger.info(message)
    
    # ==========================================================================
    # CLEANUP
    # ==========================================================================
    def closeEvent(self, event):
        """Handle window close event"""
        reply = QMessageBox.question(
            self,
            "Confirm Exit",
            "Are you sure you want to exit?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Stop async worker
            if self.async_worker and self.async_worker.isRunning():
                self.async_worker.stop()
                self.async_worker.wait()
            
            # Disconnect from IB
            if self.bridge and self.bridge.is_connected():
                asyncio.create_task(self.bridge.disconnect_async())
            
            event.accept()
        else:
            event.ignore()

# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================
def main():
    """Main entry point"""
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle("Fusion")
    
    # Create and show dashboard
    dashboard = TradingDashboard()
    dashboard.show()
    
    # Run event loop
    sys.exit(app.exec())

if __name__ == "__main__":
    main()