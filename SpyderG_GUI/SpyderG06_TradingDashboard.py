#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System
Module: SpyderG06_TradingDashboard.py
Group: G (GUI/User Interface)
Purpose: PyQt5 trading dashboard for monitoring and control

Description:
This module provides a comprehensive PyQt5-based trading dashboard for the Spyder
trading system. It enables real-time monitoring of connection status, position
management, manual control of trading operations, and system logs display. The
dashboard features selective position closure, start/stop functionality, and
integrates seamlessly with the existing PyQt5 GUI framework.

Author: Mohamed Talib
Created: 2025-06-09
Version: 1.4
"""

# =============================================================================
# Standard Library Imports
# =============================================================================
import sys
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional

# =============================================================================
# Third-Party Imports
# =============================================================================
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QTextEdit, QGroupBox, QCheckBox, QDialog, QDialogButtonBox,
    QMessageBox, QProgressBar, QFrame, QScrollArea, QSplitter
)
from PyQt5.QtCore import (
    QTimer, pyqtSignal, QThread, pyqtSlot, Qt, QSize
)
from PyQt5.QtGui import (
    QFont, QPalette, QColor, QIcon, QPixmap, QPainter
)

# =============================================================================
# Local Application Imports
# =============================================================================
from SpyderB_Broker.SpyderB08_IBGatewayConnection import SpyderIBConnection
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# =============================================================================
# Constants
# =============================================================================
WINDOW_TITLE = "Spyder Trading Dashboard"
WINDOW_MIN_WIDTH = 1200
WINDOW_MIN_HEIGHT = 800
UPDATE_INTERVAL = 10000  # 10 seconds
LOG_UPDATE_INTERVAL = 30000  # 30 seconds
MAX_LOG_LINES = 100

# Status Colors
COLOR_CONNECTED = "#27ae60"
COLOR_DISCONNECTED = "#e74c3c"
COLOR_WARNING = "#f39c12"
COLOR_NEUTRAL = "#34495e"

# =============================================================================
# Custom Widgets
# =============================================================================
class StatusIndicator(QLabel):
    """Custom status indicator widget with colored circle."""
    
    def __init__(self, status: str = "disconnected", parent=None):
        super().__init__(parent)
        self.status = status
        self.setFixedSize(20, 20)
        self.update_status(status)
    
    def update_status(self, status: str):
        """Update the status indicator color."""
        self.status = status
        color_map = {
            "connected": COLOR_CONNECTED,
            "disconnected": COLOR_DISCONNECTED,
            "warning": COLOR_WARNING,
            "neutral": COLOR_NEUTRAL
        }
        color = color_map.get(status, COLOR_NEUTRAL)
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                border-radius: 10px;
                border: 2px solid {color};
            }}
        """)


class PositionTableWidget(QTableWidget):
    """Enhanced table widget for displaying positions."""
    
    position_selected = pyqtSignal(str, bool)  # symbol, selected
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_table()
        
    def setup_table(self):
        """Setup the position table."""
        headers = ["Select", "Symbol", "Position", "Market Value", "Unrealized P&L", "Actions"]
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)
        
        # Set column widths
        self.setColumnWidth(0, 60)   # Select
        self.setColumnWidth(1, 80)   # Symbol
        self.setColumnWidth(2, 100)  # Position
        self.setColumnWidth(3, 120)  # Market Value
        self.setColumnWidth(4, 140)  # Unrealized P&L
        self.setColumnWidth(5, 100)  # Actions
        
        # Style the table
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setStyleSheet("""
            QTableWidget {
                gridline-color: #bdc3c7;
                background-color: white;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QTableWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
        """)


# =============================================================================
# Worker Threads
# =============================================================================
class StatusUpdateThread(QThread):
    """Thread for updating status information."""
    
    status_updated = pyqtSignal(dict)
    
    def __init__(self, spyder_connection):
        super().__init__()
        self.spyder_connection = spyder_connection
        self.running = True
        
    def run(self):
        """Main thread execution."""
        while self.running:
            try:
                status = self.spyder_connection.get_status()
                
                # Add position information
                if self.spyder_connection.ib.isConnected():
                    positions = self.spyder_connection.ib.positions()
                    status['positions'] = [
                        {
                            'symbol': pos.contract.symbol,
                            'contract_id': pos.contract.conId,
                            'position': pos.position,
                            'market_price': pos.marketPrice,
                            'market_value': pos.marketValue,
                            'unrealized_pnl': pos.unrealizedPNL
                        } for pos in positions if pos.position != 0
                    ]
                    status['total_positions'] = len([p for p in positions if p.position != 0])
                else:
                    status['positions'] = []
                    status['total_positions'] = 0
                
                self.status_updated.emit(status)
                
            except Exception as e:
                print(f"Error in status update thread: {e}")
            
            self.msleep(UPDATE_INTERVAL)
    
    def stop(self):
        """Stop the thread."""
        self.running = False


# =============================================================================
# Dialog Classes
# =============================================================================
class StopSpyderDialog(QDialog):
    """Dialog for stopping Spyder with position management options."""
    
    def __init__(self, positions: List[Dict], parent=None):
        super().__init__(parent)
        self.positions = positions
        self.selected_positions = []
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the dialog UI."""
        self.setWindowTitle("Stop Spyder - Position Management")
        self.setModal(True)
        self.resize(600, 400)
        
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel(f"🛑 You have {len(self.positions)} open positions")
        header.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(header)
        
        # Position table
        self.position_table = QTableWidget()
        self.setup_position_table()
        layout.addWidget(self.position_table)
        
        # Selection summary
        self.selection_label = QLabel("Selected to close: 0 positions")
        self.selection_label.setStyleSheet("QLabel { background-color: #e8f4f8; padding: 10px; border-radius: 5px; }")
        layout.addWidget(self.selection_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.close_selected_btn = QPushButton("🎯 Close Selected & Stop")
        self.close_selected_btn.clicked.connect(self.close_selected)
        
        self.keep_all_btn = QPushButton("🔒 Keep All Positions")
        self.keep_all_btn.clicked.connect(self.keep_all)
        
        self.close_all_btn = QPushButton("❌ Close All Positions")
        self.close_all_btn.clicked.connect(self.close_all)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(self.close_selected_btn)
        button_layout.addWidget(self.keep_all_btn)
        button_layout.addWidget(self.close_all_btn)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
    def setup_position_table(self):
        """Setup the position selection table."""
        headers = ["Select", "Symbol", "Position", "P&L"]
        self.position_table.setColumnCount(len(headers))
        self.position_table.setHorizontalHeaderLabels(headers)
        self.position_table.setRowCount(len(self.positions))
        
        for row, pos in enumerate(self.positions):
            # Checkbox
            checkbox = QCheckBox()
            checkbox.stateChanged.connect(self.update_selection)
            self.position_table.setCellWidget(row, 0, checkbox)
            
            # Symbol
            self.position_table.setItem(row, 1, QTableWidgetItem(pos['symbol']))
            
            # Position
            self.position_table.setItem(row, 2, QTableWidgetItem(str(pos['position'])))
            
            # P&L
            pnl = pos.get('unrealized_pnl', 0)
            pnl_item = QTableWidgetItem(f"${pnl:.2f}")
            if pnl >= 0:
                pnl_item.setBackground(QColor(COLOR_CONNECTED))
            else:
                pnl_item.setBackground(QColor(COLOR_DISCONNECTED))
            self.position_table.setItem(row, 3, pnl_item)
    
    def update_selection(self):
        """Update the selection summary."""
        selected_count = 0
        selected_symbols = []
        
        for row in range(self.position_table.rowCount()):
            checkbox = self.position_table.cellWidget(row, 0)
            if checkbox.isChecked():
                selected_count += 1
                symbol = self.position_table.item(row, 1).text()
                selected_symbols.append(symbol)
        
        self.selected_positions = selected_symbols
        summary = f"Selected to close: {selected_count} positions"
        if selected_symbols:
            summary += f" ({', '.join(selected_symbols)})"
        self.selection_label.setText(summary)
    
    def close_selected(self):
        """Close selected positions and stop."""
        if not self.selected_positions:
            QMessageBox.warning(self, "Warning", "Please select at least one position to close")
            return
        self.done(1)  # Return code 1 for selective close
    
    def keep_all(self):
        """Keep all positions and stop."""
        self.done(2)  # Return code 2 for keep all
    
    def close_all(self):
        """Close all positions and stop."""
        self.done(3)  # Return code 3 for close all


# =============================================================================
# Main Dashboard Class
# =============================================================================
class SpyderTradingDashboard(QMainWindow):
    """Main trading dashboard window."""
    
    def __init__(self):
        super().__init__()
        self.spyder_connection = SpyderIBConnection()
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.status_thread = None
        
        self.setup_ui()
        self.setup_timers()
        self.start_status_updates()
        
        # Start Spyder connection manager
        self.spyder_connection.start()
        
    def setup_ui(self):
        """Setup the main UI."""
        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        
        # Create splitter for resizable sections
        splitter = QSplitter(Qt.Vertical)
        main_layout.addWidget(splitter)
        
        # Top section - Status and Controls
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        
        # Status section
        self.status_group = self.create_status_section()
        top_layout.addWidget(self.status_group)
        
        # Control section
        self.control_group = self.create_control_section()
        top_layout.addWidget(self.control_group)
        
        splitter.addWidget(top_widget)
        
        # Middle section - Positions
        self.positions_group = self.create_positions_section()
        splitter.addWidget(self.positions_group)
        
        # Bottom section - Logs
        self.logs_group = self.create_logs_section()
        splitter.addWidget(self.logs_group)
        
        # Set splitter proportions
        splitter.setSizes([200, 300, 200])
        
        # Apply stylesheet
        self.apply_stylesheet()
        
    def create_status_section(self) -> QGroupBox:
        """Create the status monitoring section."""
        group = QGroupBox("📊 System Status")
        layout = QVBoxLayout(group)
        
        # Connection status
        conn_layout = QHBoxLayout()
        conn_layout.addWidget(QLabel("Spyder Status:"))
        self.connection_indicator = StatusIndicator("disconnected")
        self.connection_status_label = QLabel("Stopped")
        conn_layout.addWidget(self.connection_indicator)
        conn_layout.addWidget(self.connection_status_label)
        conn_layout.addStretch()
        layout.addLayout(conn_layout)
        
        # Current time
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("Current Time:"))
        self.time_label = QLabel("--:--:-- EST")
        time_layout.addWidget(self.time_label)
        time_layout.addStretch()
        layout.addLayout(time_layout)
        
        # Position count
        pos_layout = QHBoxLayout()
        pos_layout.addWidget(QLabel("Open Positions:"))
        self.positions_count_label = QLabel("0")
        pos_layout.addWidget(self.positions_count_label)
        pos_layout.addStretch()
        layout.addLayout(pos_layout)
        
        # News gathering
        news_layout = QHBoxLayout()
        news_layout.addWidget(QLabel("News Gathering:"))
        self.news_indicator = StatusIndicator("disconnected")
        self.news_status_label = QLabel("Inactive")
        news_layout.addWidget(self.news_indicator)
        news_layout.addWidget(self.news_status_label)
        news_layout.addStretch()
        layout.addLayout(news_layout)
        
        # Schedule info
        schedule_label = QLabel("📅 Schedule: Connect 1:00 PM EST | Disconnect 4:30 PM EST")
        schedule_label.setStyleSheet("QLabel { background-color: #8e44ad; color: white; padding: 10px; border-radius: 5px; }")
        layout.addWidget(schedule_label)
        
        return group
        
    def create_control_section(self) -> QGroupBox:
        """Create the control buttons section."""
        group = QGroupBox("🎮 Spyder Controls")
        layout = QVBoxLayout(group)
        
        # Start button
        self.start_btn = QPushButton("🚀 Start Spyder")
        self.start_btn.setMinimumHeight(50)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #27ae60, stop:1 #2ecc71);
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #229954, stop:1 #27ae60);
            }
            QPushButton:disabled {
                background: #bdc3c7;
            }
        """)
        self.start_btn.clicked.connect(self.start_spyder)
        layout.addWidget(self.start_btn)
        
        # Stop button
        self.stop_btn = QPushButton("🛑 Stop Spyder")
        self.stop_btn.setMinimumHeight(50)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #e74c3c, stop:1 #c0392b);
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #cb4335, stop:1 #a93226);
            }
            QPushButton:disabled {
                background: #bdc3c7;
            }
        """)
        self.stop_btn.clicked.connect(self.stop_spyder)
        layout.addWidget(self.stop_btn)
        
        # Status message
        self.status_message = QLabel("")
        self.status_message.setWordWrap(True)
        self.status_message.setMaximumHeight(60)
        layout.addWidget(self.status_message)
        
        # Mobile 2FA info
        info_label = QLabel("📱 Mobile 2FA Required\nYou'll need to approve the connection on your mobile device when starting Spyder")
        info_label.setStyleSheet("QLabel { background-color: #fff3cd; padding: 10px; border-radius: 5px; }")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        return group
        
    def create_positions_section(self) -> QGroupBox:
        """Create the positions management section."""
        group = QGroupBox("💼 Current Positions")
        layout = QVBoxLayout(group)
        
        # Position table
        self.position_table = PositionTableWidget()
        layout.addWidget(self.position_table)
        
        return group
        
    def create_logs_section(self) -> QGroupBox:
        """Create the system logs section."""
        group = QGroupBox("📋 System Logs")
        layout = QVBoxLayout(group)
        
        # Log display
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setMaximumHeight(200)
        self.log_display.setStyleSheet("""
            QTextEdit {
                background-color: #2c3e50;
                color: #ecf0f1;
                font-family: 'Courier New', monospace;
                font-size: 10px;
            }
        """)
        layout.addWidget(self.log_display)
        
        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh Logs")
        refresh_btn.clicked.connect(self.refresh_logs)
        layout.addWidget(refresh_btn)
        
        return group
        
    def apply_stylesheet(self):
        """Apply the main stylesheet."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #ecf0f1;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #bdc3c7;
                border-radius: 8px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
        """)
        
    def setup_timers(self):
        """Setup update timers."""
        # Status update timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_display)
        self.status_timer.start(UPDATE_INTERVAL)
        
        # Log update timer
        self.log_timer = QTimer()
        self.log_timer.timeout.connect(self.refresh_logs)
        self.log_timer.start(LOG_UPDATE_INTERVAL)
        
    def start_status_updates(self):
        """Start the status update thread."""
        if self.status_thread:
            self.status_thread.stop()
            self.status_thread.wait()
            
        self.status_thread = StatusUpdateThread(self.spyder_connection)
        self.status_thread.status_updated.connect(self.update_status_display)
        self.status_thread.start()
        
    @pyqtSlot(dict)
    def update_status_display(self, status: Dict[str, Any]):
        """Update the status display with new data."""
        try:
            # Connection status
            connected = status.get('connected', False)
            if connected:
                self.connection_indicator.update_status("connected")
                self.connection_status_label.setText("Running")
                self.start_btn.setEnabled(False)
                self.start_btn.setText("✅ Spyder Running")
                self.stop_btn.setEnabled(True)
                self.stop_btn.setText("🛑 Stop Spyder")
            else:
                self.connection_indicator.update_status("disconnected")
                self.connection_status_label.setText("Stopped")
                self.start_btn.setEnabled(True)
                self.start_btn.setText("🚀 Start Spyder")
                self.stop_btn.setEnabled(False)
                self.stop_btn.setText("⚫ Spyder Stopped")
            
            # Time
            self.time_label.setText(status.get('current_time', '--:--:-- EST'))
            
            # Position count
            position_count = status.get('total_positions', 0)
            self.positions_count_label.setText(str(position_count))
            
            # News gathering
            news_active = status.get('news_gathering', False)
            if news_active:
                self.news_indicator.update_status("connected")
                self.news_status_label.setText("Active")
            else:
                self.news_indicator.update_status("disconnected")
                self.news_status_label.setText("Inactive")
            
            # Update position table
            self.update_position_table(status.get('positions', []))
            
        except Exception as e:
            self.logger.error(f"Error updating status display: {e}")
            
    def update_position_table(self, positions: List[Dict[str, Any]]):
        """Update the position table."""
        try:
            self.position_table.setRowCount(len(positions))
            
            for row, pos in enumerate(positions):
                # Checkbox
                checkbox = QCheckBox()
                self.position_table.setCellWidget(row, 0, checkbox)
                
                # Symbol
                self.position_table.setItem(row, 1, QTableWidgetItem(pos['symbol']))
                
                # Position
                self.position_table.setItem(row, 2, QTableWidgetItem(str(pos['position'])))
                
                # Market Value
                market_value = pos.get('market_value', 0)
                self.position_table.setItem(row, 3, QTableWidgetItem(f"${market_value:.2f}"))
                
                # Unrealized P&L
                pnl = pos.get('unrealized_pnl', 0)
                pnl_item = QTableWidgetItem(f"${pnl:.2f}")
                if pnl >= 0:
                    pnl_item.setForeground(QColor(COLOR_CONNECTED))
                else:
                    pnl_item.setForeground(QColor(COLOR_DISCONNECTED))
                self.position_table.setItem(row, 4, pnl_item)
                
                # Actions button
                action_btn = QPushButton("Manage")
                action_btn.clicked.connect(lambda checked, symbol=pos['symbol']: self.manage_position(symbol))
                self.position_table.setCellWidget(row, 5, action_btn)
                
        except Exception as e:
            self.logger.error(f"Error updating position table: {e}")
    
    def start_spyder(self):
        """Start Spyder trading system."""
        try:
            if self.spyder_connection.ib.isConnected():
                self.show_message("Spyder is already running", "warning")
                return
            
            self.logger.info("Manual Spyder start requested via dashboard")
            self.show_message("🚀 Spyder starting up! Please approve the connection on your mobile device.", "info")
            
            # Start connection in background thread
            def connect_async():
                success = self.spyder_connection.connect_ib()
                if success:
                    self.show_message("✅ Spyder started successfully!", "success")
                else:
                    self.show_message("❌ Failed to start Spyder. Check logs for details.", "error")
            
            thread = threading.Thread(target=connect_async, daemon=True)
            thread.start()
            
        except Exception as e:
            self.logger.error(f"Error starting Spyder: {e}")
            self.error_handler.handle_error(e, context="Start Spyder")
            self.show_message(f"Error starting Spyder: {str(e)}", "error")
    
    def stop_spyder(self):
        """Stop Spyder with position management."""
        try:
            if not self.spyder_connection.ib.isConnected():
                self.show_message("Spyder is not currently running", "warning")
                return
            
            # Check for open positions
            positions = self.spyder_connection.ib.positions()
            active_positions = [pos for pos in positions if pos.position != 0]
            
            if not active_positions:
                # No positions, safe to disconnect
                self.spyder_connection.disconnect_ib()
                self.show_message("🛑 Spyder stopped. No open positions found.", "success")
                return
            
            # Show position management dialog
            position_data = []
            for pos in active_positions:
                position_data.append({
                    'symbol': pos.contract.symbol,
                    'position': pos.position,
                    'market_value': pos.marketValue,
                    'unrealized_pnl': pos.unrealizedPNL
                })
            
            dialog = StopSpyderDialog(position_data, self)
            result = dialog.exec_()
            
            if result == 1:  # Close selected
                self.close_selected_positions(dialog.selected_positions)
            elif result == 2:  # Keep all
                self.spyder_connection.disconnect_ib()
                self.show_message("🛑 Spyder stopped. Positions remain open with existing stop losses.", "success")
            elif result == 3:  # Close all
                self.close_all_positions()
            
        except Exception as e:
            self.logger.error(f"Error stopping Spyder: {e}")
            self.error_handler.handle_error(e, context="Stop Spyder")
            self.show_message(f"Error stopping Spyder: {str(e)}", "error")
    
    def close_selected_positions(self, symbols: List[str]):
        """Close selected positions and disconnect."""
        try:
            closed_count = 0
            failed_positions = []
            
            for symbol in symbols:
                success = self.spyder_connection.close_specific_position(symbol)
                if success:
                    closed_count += 1
                else:
                    failed_positions.append(symbol)
            
            self.spyder_connection.disconnect_ib()
            
            if failed_positions:
                message = f"🛑 Spyder stopped. Closed {closed_count} positions. Failed to close: {', '.join(failed_positions)}"
                self.show_message(message, "warning")
            else:
                message = f"🛑 Spyder stopped. Successfully closed {closed_count} selected positions."
                self.show_message(message, "success")
                
        except Exception as e:
            self.logger.error(f"Error closing selected positions: {e}")
            self.error_handler.handle_error(e, context="Close Selected Positions")
    
    def close_all_positions(self):
        """Close all positions and disconnect."""
        try:
            # Implementation would call the close_all_positions method
            # This is a placeholder for the actual implementation
            self.spyder_connection.disconnect_ib()
            self.show_message("🛑 Spyder stopped. All positions have been closed.", "success")
            
        except Exception as e:
            self.logger.error(f"Error closing all positions: {e}")
            self.error_handler.handle_error(e, context="Close All Positions")
    
    def manage_position(self, symbol: str):
        """Manage individual position."""
        try:
            reply = QMessageBox.question(
                self, 
                "Manage Position", 
                f"Do you want to close the {symbol} position?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                success = self.spyder_connection.close_specific_position(symbol)
                if success:
                    self.show_message(f"✅ {symbol} position closed successfully", "success")
                else:
                    self.show_message(f"❌ Failed to close {symbol} position", "error")
                    
        except Exception as e:
            self.logger.error(f"Error managing position {symbol}: {e}")
            self.error_handler.handle_error(e, context=f"Manage Position - {symbol}")
    
    def refresh_logs(self):
        """Refresh the log display."""
        try:
            log_file_path = "spyder_ib.log"
            with open(log_file_path, 'r') as f:
                lines = f.readlines()
                recent_logs = lines[-MAX_LOG_LINES:] if len(lines) > MAX_LOG_LINES else lines
                self.log_display.setPlainText(''.join(recent_logs))
                
                # Scroll to bottom
                cursor = self.log_display.textCursor()
                cursor.movePosition(cursor.End)
                self.log_display.setTextCursor(cursor)
                
        except FileNotFoundError:
            self.log_display.setPlainText("Log file not found - system may be starting up")
        except Exception as e:
            self.log_display.setPlainText(f"Error reading logs: {str(e)}")
    
    def show_message(self, message: str, message_type: str = "info"):
        """Show status message."""
        color_map = {
            "success": "#d4edda",
            "error": "#f8d7da", 
            "warning": "#fff3cd",
            "info": "#d1ecf1"
        }
        
        bg_color = color_map.get(message_type, "#d1ecf1")
        self.status_message.setStyleSheet(f"QLabel {{ background-color: {bg_color}; padding: 10px; border-radius: 5px; }}")
        self.status_message.setText(message)
        
        # Auto-clear message after 10 seconds
        QTimer.singleShot(10000, lambda: self.status_message.setText(""))
    
    def update_display(self):
        """Periodic display update."""
        # This method can be used for any periodic updates that don't require thread communication
        pass
    
    def closeEvent(self, event):
        """Handle window close event."""
        try:
            if self.status_thread:
                self.status_thread.stop()
                self.status_thread.wait()
            
            self.spyder_connection.stop()
            event.accept()
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
            event.accept()


# =============================================================================
# Main Execution
# =============================================================================
def main():
    """Main function to run the dashboard."""
    app = QApplication(sys.argv)
    app.setApplicationName(WINDOW_TITLE)
    
    # Create and show the dashboard
    dashboard = SpyderTradingDashboard()
    dashboard.show()
    
    # Start the event loop
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
