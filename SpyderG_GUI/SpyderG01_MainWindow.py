#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System
Module: SpyderG01_MainWindow.py
Group: G (GUI)
Purpose: Main application window

Description:
The main GUI window for the Spyder trading system. Provides real-time
display of positions, trades, market data, and system status.
"""

# =============================================================================
# Standard Library Imports
# =============================================================================
import logging
import sys
from datetime import datetime

# =============================================================================
# Third-Party Imports
# =============================================================================
try:
    from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                                 QLabel, QMessageBox, QTableWidget, QTableWidgetItem,
                                 QTabWidget, QTextEdit, QPushButton, QGroupBox,
                                 QSplitter, QStatusBar)
    from PyQt5.QtCore import Qt, QTimer, pyqtSignal
    from PyQt5.QtGui import QFont, QPalette, QColor
except ImportError:
    print("PyQt5 not installed. GUI features will be unavailable.")
    sys.exit(1)

# =============================================================================
# Main Window Class
# =============================================================================
class SpyderMainWindow(QMainWindow):
    """
    Main application window for the Spyder trading system.
    
    Provides a comprehensive interface for monitoring and controlling
    the automated trading system.
    """
    
    # Signals
    start_trading_signal = pyqtSignal()
    stop_trading_signal = pyqtSignal()
    
    def __init__(self, trading_engine=None, spyder_client=None, 
                 event_manager=None, config=None, **kwargs):
        """
        Initialize the main window.
        
        Args:
            trading_engine: Trading engine instance
            spyder_client: Spyder client instance (connects to IB Gateway)
            event_manager: Event manager instance
            config: Configuration manager instance
            **kwargs: Additional keyword arguments
        """
        super().__init__()
        
        # Store references
        self.trading_engine = trading_engine
        self.spyder_client = spyder_client
        self.event_manager = event_manager
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize UI
        self.init_ui()
        self.setup_timers()
        
        self.logger.info("SpyderMainWindow initialized successfully")
    
    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Spyder Trading System")
        self.setGeometry(100, 100, 1400, 900)
        
        # Set application style
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QLabel {
                color: #ffffff;
            }
            QPushButton {
                background-color: #2e2e2e;
                color: #ffffff;
                border: 1px solid #555;
                padding: 5px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #3e3e3e;
            }
            QPushButton:pressed {
                background-color: #1e1e1e;
            }
            QTableWidget {
                background-color: #2e2e2e;
                color: #ffffff;
                gridline-color: #555;
            }
            QTableWidget::item:selected {
                background-color: #0d47a1;
            }
            QTabWidget::pane {
                border: 1px solid #555;
                background-color: #2e2e2e;
            }
            QTextEdit {
                background-color: #2e2e2e;
                color: #ffffff;
                border: 1px solid #555;
            }
        """)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        
        # Add components
        self.create_header()
        self.create_main_content()
        self.create_status_bar()
        
        main_layout.addWidget(self.header_widget)
        main_layout.addWidget(self.main_content)
        
    def create_header(self):
        """Create header section with controls."""
        self.header_widget = QWidget()
        header_layout = QHBoxLayout(self.header_widget)
        
        # Title
        title = QLabel("SPYDER TRADING SYSTEM")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Control buttons
        self.start_button = QPushButton("Start Trading")
        self.start_button.setStyleSheet("background-color: #2e7d32;")
        self.start_button.clicked.connect(self.on_start_trading)
        
        self.stop_button = QPushButton("Stop Trading")
        self.stop_button.setStyleSheet("background-color: #c62828;")
        self.stop_button.clicked.connect(self.on_stop_trading)
        self.stop_button.setEnabled(False)
        
        header_layout.addWidget(self.start_button)
        header_layout.addWidget(self.stop_button)
    
    def create_main_content(self):
        """Create main content area."""
        self.main_content = QTabWidget()
        
        # Dashboard tab
        self.dashboard_tab = self.create_dashboard_tab()
        self.main_content.addTab(self.dashboard_tab, "Dashboard")
        
        # Positions tab
        self.positions_tab = self.create_positions_tab()
        self.main_content.addTab(self.positions_tab, "Positions")
        
        # Trades tab
        self.trades_tab = self.create_trades_tab()
        self.main_content.addTab(self.trades_tab, "Trades")
        
        # Logs tab
        self.logs_tab = self.create_logs_tab()
        self.main_content.addTab(self.logs_tab, "Logs")
    
    def create_dashboard_tab(self):
        """Create dashboard tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Summary section
        summary_group = QGroupBox("Account Summary")
        summary_layout = QHBoxLayout(summary_group)
        
        self.balance_label = QLabel("Balance: $0.00")
        self.buying_power_label = QLabel("Buying Power: $0.00")
        self.positions_count_label = QLabel("Open Positions: 0")
        
        summary_layout.addWidget(self.balance_label)
        summary_layout.addWidget(self.buying_power_label)
        summary_layout.addWidget(self.positions_count_label)
        
        layout.addWidget(summary_group)
        layout.addStretch()
        
        return widget
    
    def create_positions_tab(self):
        """Create positions tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.positions_table = QTableWidget()
        self.positions_table.setColumnCount(7)
        self.positions_table.setHorizontalHeaderLabels([
            "Symbol", "Quantity", "Avg Cost", "Current Price", 
            "P&L", "P&L %", "Value"
        ])
        
        layout.addWidget(self.positions_table)
        return widget
    
    def create_trades_tab(self):
        """Create trades tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.trades_table = QTableWidget()
        self.trades_table.setColumnCount(6)
        self.trades_table.setHorizontalHeaderLabels([
            "Time", "Symbol", "Side", "Quantity", "Price", "Status"
        ])
        
        layout.addWidget(self.trades_table)
        return widget
    
    def create_logs_tab(self):
        """Create logs tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        
        layout.addWidget(self.log_text)
        return widget
    
    def create_status_bar(self):
        """Create status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
    
    def setup_timers(self):
        """Setup update timers."""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(1000)  # Update every second
    
    def update_display(self):
        """Update display with latest data."""
        # Update timestamp
        current_time = datetime.now().strftime("%H:%M:%S")
        self.status_bar.showMessage(f"Connected | {current_time}")
    
    def on_start_trading(self):
        """Handle start trading button."""
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.start_trading_signal.emit()
        self.log_message("Trading started")
    
    def on_stop_trading(self):
        """Handle stop trading button."""
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.stop_trading_signal.emit()
        self.log_message("Trading stopped")
    
    def log_message(self, message):
        """Add message to log."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
    
    def show_error(self, message):
        """Show error dialog."""
        QMessageBox.critical(self, "Error", str(message))
        self.log_message(f"ERROR: {message}")
    
    def show_warning(self, message):
        """Show warning dialog."""
        QMessageBox.warning(self, "Warning", str(message))
        self.log_message(f"WARNING: {message}")
    
    def show_critical_alert(self, message):
        """Show critical alert dialog."""
        QMessageBox.critical(self, "Critical Alert", str(message))
        self.log_message(f"CRITICAL: {message}")
    
    def update_trades(self, trade_data):
        """Update trades table."""
        # Add trade to table
        row = self.trades_table.rowCount()
        self.trades_table.insertRow(row)
        
        # Add trade data
        self.trades_table.setItem(row, 0, QTableWidgetItem(str(trade_data.get('time', ''))))
        self.trades_table.setItem(row, 1, QTableWidgetItem(str(trade_data.get('symbol', ''))))
        self.trades_table.setItem(row, 2, QTableWidgetItem(str(trade_data.get('side', ''))))
        self.trades_table.setItem(row, 3, QTableWidgetItem(str(trade_data.get('quantity', ''))))
        self.trades_table.setItem(row, 4, QTableWidgetItem(str(trade_data.get('price', ''))))
        self.trades_table.setItem(row, 5, QTableWidgetItem(str(trade_data.get('status', ''))))
        
        self.log_message(f"Trade executed: {trade_data}")
    
    def update_positions(self, position_data):
        """Update positions table."""
        self.log_message(f"Position updated: {position_data}")
        # TODO: Implement position table update
    
    def closeEvent(self, event):
        """Handle window close event."""
        reply = QMessageBox.question(self, 'Exit',
                                   'Are you sure you want to exit?',
                                   QMessageBox.Yes | QMessageBox.No,
                                   QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()
