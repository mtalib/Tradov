#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG05_ConnectAPIStatus.py
Purpose: Connect API status display widget

Author: SPYDER Trading System
Year Created: 2025
Last Updated: 2025-10-20 Time: 22:15:00

Module Description:
    This module provides a GUI widget for displaying the status of the Connect API.
    It shows connection status, market data status, order status, and risk metrics.
    This widget replaces the IB Gateway/TWS API status display components.

Module Constants:
    STATUS_UPDATE_INTERVAL (int): Status update interval in milliseconds (default: 1000)
    STATUS_COLORS (Dict): Color mapping for different status levels

Change Log:
    2025-10-20 (v1.0.0):
        - Initial module creation
        - Implemented core status display functionality
        - Added integration with Connect API components
        - Implemented real-time status updates

    2025-10-15 (v0.9.0):
        - Beta version for testing
        - Basic status display structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import threading
import asyncio
import json
import uuid
import warnings
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Callable, Union, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
from enum import Enum, auto
from pathlib import Path
import copy
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from threading import Lock, Event as ThreadEvent, RLock

# GUI imports
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QFrame, QGroupBox, QTabWidget, QTableWidget, QTableWidgetItem,
    QProgressBar, QPushButton, QCheckBox, QComboBox, QSpinBox,
    QDoubleSpinBox, QTextEdit, QScrollArea, QSplitter, QSizePolicy
)
from PyQt5.QtCore import (
    Qt, QTimer, pyqtSignal, QThread, QObject, pyqtSlot, QPropertyAnimation
)
from PyQt5.QtGui import (
    QColor, QPalette, QFont, QPixmap, QPainter, QBrush, QPen, QLinearGradient
)

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# Import Connect API components
from Spyder.SpyderB_Broker.SpyderB01_ConnectAPI import ConnectAPI, ConnectionState
from Spyder.SpyderB_Broker.SpyderB02_OrderManager import OrderManager, OrderState
from Spyder.SpyderC_MarketData.SpyderC02_MarketDataFeed import MarketDataFeed, DataFeedState
from Spyder.SpyderE_Risk.SpyderE01_RiskManager import RiskManager, RiskLevel

# ==============================================================================
# CONSTANTS
# ==============================================================================
STATUS_UPDATE_INTERVAL = 1000  # milliseconds

STATUS_COLORS = {
    'CONNECTED': QColor(0, 200, 0),  # Green
    'DISCONNECTED': QColor(200, 0, 0),  # Red
    'CONNECTING': QColor(200, 200, 0),  # Yellow
    'AUTHENTICATED': QColor(0, 150, 200),  # Cyan
    'ERROR': QColor(200, 0, 100),  # Dark Red
    'RECONNECTING': QColor(150, 150, 0),  # Dark Yellow
    'LOW': QColor(0, 200, 0),  # Green
    'MEDIUM': QColor(200, 200, 0),  # Yellow
    'HIGH': QColor(200, 100, 0),  # Orange
    'CRITICAL': QColor(200, 0, 0),  # Red
}

# ==============================================================================
# ENUMS
# ==============================================================================
class StatusLevel(Enum):
    """Status levels"""
    GOOD = auto()
    WARNING = auto()
    ERROR = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class StatusConfig:
    """Configuration for status display"""
    update_interval: int = STATUS_UPDATE_INTERVAL
    show_detailed_metrics: bool = True
    show_risk_metrics: bool = True
    show_order_status: bool = True
    show_market_data_status: bool = True
    enable_notifications: bool = True
    notification_threshold: StatusLevel = StatusLevel.WARNING

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class ConnectAPIStatusWidget(QWidget):
    """
    Connect API status display widget.

    This widget displays the status of the Connect API, including connection status,
    market data status, order status, and risk metrics. It replaces the IB Gateway/TWS
    API status display components.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling system
        config: Status display configuration
        connect_api: Connect API instance
        order_manager: Order manager instance
        market_data_feed: Market data feed instance
        risk_manager: Risk manager instance
        _status_timer: Timer for status updates
        _status_lock: Thread lock for status operations
    """

    # Signals
    status_changed = pyqtSignal(str, str)  # component, status

    def __init__(
        self,
        config: StatusConfig,
        connect_api: ConnectAPI,
        order_manager: Optional[OrderManager] = None,
        market_data_feed: Optional[MarketDataFeed] = None,
        risk_manager: Optional[RiskManager] = None,
        parent=None
    ):
        """
        Initialize the Connect API status widget.

        Args:
            config: Status display configuration
            connect_api: Connect API instance
            order_manager: Order manager instance
            market_data_feed: Market data feed instance
            risk_manager: Risk manager instance
            parent: Parent widget
        """
        super().__init__(parent)

        # Core components
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()

        # Configuration
        self.config = config

        # Connect API components
        self.connect_api = connect_api
        self.order_manager = order_manager
        self.market_data_feed = market_data_feed
        self.risk_manager = risk_manager

        # Status management
        self._status_lock = RLock()
        self._status_timer = QTimer()
        self._status_timer.timeout.connect(self._update_status)

        # Initialize UI
        self._init_ui()

        # Start status updates
        self._status_timer.start(self.config.update_interval)

        self.logger.info("ConnectAPIStatusWidget initialized")

    def _init_ui(self):
        """Initialize the user interface"""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # Create connection status group
        self._create_connection_status_group(main_layout)

        # Create detailed status tabs
        self._create_status_tabs(main_layout)

        # Set layout
        self.setLayout(main_layout)

    def _create_connection_status_group(self, parent_layout):
        """Create connection status group"""
        # Group box
        group_box = QGroupBox("Connection Status")
        group_box.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #cccccc;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)

        # Layout
        layout = QHBoxLayout(group_box)
        layout.setContentsMargins(10, 5, 10, 5)

        # Connection status label
        self.connection_status_label = QLabel("Disconnected")
        self.connection_status_label.setAlignment(Qt.AlignCenter)
        self.connection_status_label.setMinimumHeight(30)
        self._update_status_label(self.connection_status_label, "DISCONNECTED")

        # Session ID label
        self.session_id_label = QLabel("Session ID: N/A")
        self.session_id_label.setAlignment(Qt.AlignCenter)

        # Uptime label
        self.uptime_label = QLabel("Uptime: 00:00:00")
        self.uptime_label.setAlignment(Qt.AlignCenter)

        # Add to layout
        layout.addWidget(self.connection_status_label)
        layout.addWidget(self.session_id_label)
        layout.addWidget(self.uptime_label)

        # Add to parent layout
        parent_layout.addWidget(group_box)

    def _create_status_tabs(self, parent_layout):
        """Create status tabs"""
        # Tab widget
        self.status_tabs = QTabWidget()

        # Market data status tab
        if self.config.show_market_data_status:
            self._create_market_data_tab()

        # Order status tab
        if self.config.show_order_status:
            self._create_order_status_tab()

        # Risk metrics tab
        if self.config.show_risk_metrics:
            self._create_risk_metrics_tab()

        # Detailed metrics tab
        if self.config.show_detailed_metrics:
            self._create_detailed_metrics_tab()

        # Add to parent layout
        parent_layout.addWidget(self.status_tabs)

    def _create_market_data_tab(self):
        """Create market data status tab"""
        # Widget
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Status label
        self.market_data_status_label = QLabel("Status: Unknown")
        self._update_status_label(self.market_data_status_label, "UNKNOWN")
        layout.addWidget(self.market_data_status_label)

        # Symbols table
        symbols_group = QGroupBox("Subscribed Symbols")
        symbols_layout = QVBoxLayout(symbols_group)

        self.symbols_table = QTableWidget()
        self.symbols_table.setColumnCount(4)
        self.symbols_table.setHorizontalHeaderLabels(["Symbol", "Last Price", "Bid/Ask", "Update Time"])
        self.symbols_table.horizontalHeader().setStretchLastSection(True)
        self.symbols_table.setMinimumHeight(200)

        symbols_layout.addWidget(self.symbols_table)
        layout.addWidget(symbols_group)

        # Add tab
        self.status_tabs.addTab(widget, "Market Data")

    def _create_order_status_tab(self):
        """Create order status tab"""
        # Widget
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Status label
        self.order_status_label = QLabel("Status: Unknown")
        self._update_status_label(self.order_status_label, "UNKNOWN")
        layout.addWidget(self.order_status_label)

        # Orders table
        orders_group = QGroupBox("Active Orders")
        orders_layout = QVBoxLayout(orders_group)

        self.orders_table = QTableWidget()
        self.orders_table.setColumnCount(6)
        self.orders_table.setHorizontalHeaderLabels(["Order ID", "Symbol", "Side", "Type", "Quantity", "Status"])
        self.orders_table.horizontalHeader().setStretchLastSection(True)
        self.orders_table.setMinimumHeight(200)

        orders_layout.addWidget(self.orders_table)
        layout.addWidget(orders_group)

        # Add tab
        self.status_tabs.addTab(widget, "Orders")

    def _create_risk_metrics_tab(self):
        """Create risk metrics tab"""
        # Widget
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Risk level label
        self.risk_level_label = QLabel("Risk Level: Unknown")
        self._update_status_label(self.risk_level_label, "UNKNOWN")
        layout.addWidget(self.risk_level_label)

        # Risk metrics
        metrics_group = QGroupBox("Risk Metrics")
        metrics_layout = QGridLayout(metrics_group)

        # Create metric labels
        self.total_exposure_label = QLabel("Total Exposure: $0.00")
        self.daily_pnl_label = QLabel("Daily P&L: $0.00")
        self.margin_usage_label = QLabel("Margin Usage: 0.00%")
        self.concentration_label = QLabel("Max Concentration: 0.00%")
        self.warnings_label = QLabel("Warnings: 0")

        # Add to layout
        metrics_layout.addWidget(self.total_exposure_label, 0, 0, 1, 2)
        metrics_layout.addWidget(self.daily_pnl_label, 1, 0, 1, 2)
        metrics_layout.addWidget(self.margin_usage_label, 2, 0, 1, 2)
        metrics_layout.addWidget(self.concentration_label, 3, 0, 1, 2)
        metrics_layout.addWidget(self.warnings_label, 4, 0, 1, 2)

        layout.addWidget(metrics_group)

        # Positions table
        positions_group = QGroupBox("Current Positions")
        positions_layout = QVBoxLayout(positions_group)

        self.positions_table = QTableWidget()
        self.positions_table.setColumnCount(5)
        self.positions_table.setHorizontalHeaderLabels(["Symbol", "Quantity", "Market Value", "Unrealized P&L", "% of Portfolio"])
        self.positions_table.horizontalHeader().setStretchLastSection(True)
        self.positions_table.setMinimumHeight(200)

        positions_layout.addWidget(self.positions_table)
        layout.addWidget(positions_group)

        # Add tab
        self.status_tabs.addTab(widget, "Risk")

    def _create_detailed_metrics_tab(self):
        """Create detailed metrics tab"""
        # Widget
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Connect API metrics
        connect_group = QGroupBox("Connect API Metrics")
        connect_layout = QGridLayout(connect_group)

        self.messages_sent_label = QLabel("Messages Sent: 0")
        self.messages_received_label = QLabel("Messages Received: 0")
        self.message_rate_label = QLabel("Message Rate: 0.00/s")
        self.reconnections_label = QLabel("Reconnections: 0")

        connect_layout.addWidget(self.messages_sent_label, 0, 0)
        connect_layout.addWidget(self.messages_received_label, 0, 1)
        connect_layout.addWidget(self.message_rate_label, 1, 0)
        connect_layout.addWidget(self.reconnections_label, 1, 1)

        layout.addWidget(connect_group)

        # Order manager metrics
        if self.order_manager:
            order_group = QGroupBox("Order Manager Metrics")
            order_layout = QGridLayout(order_group)

            order_metrics = self.order_manager.get_metrics()

            self.orders_submitted_label = QLabel(f"Orders Submitted: {order_metrics['orders_submitted']}")
            self.orders_filled_label = QLabel(f"Orders Filled: {order_metrics['orders_filled']}")
            self.orders_cancelled_label = QLabel(f"Orders Cancelled: {order_metrics['orders_cancelled']}")
            self.success_rate_label = QLabel(f"Success Rate: {order_metrics['success_rate']:.2f}%")

            order_layout.addWidget(self.orders_submitted_label, 0, 0)
            order_layout.addWidget(self.orders_filled_label, 0, 1)
            order_layout.addWidget(self.orders_cancelled_label, 1, 0)
            order_layout.addWidget(self.success_rate_label, 1, 1)

            layout.addWidget(order_group)

        # Market data feed metrics
        if self.market_data_feed:
            data_group = QGroupBox("Market Data Metrics")
            data_layout = QGridLayout(data_group)

            data_metrics = self.market_data_feed.get_metrics()

            self.data_updates_label = QLabel(f"Data Updates: {data_metrics['data_updates']}")
            self.data_gaps_label = QLabel(f"Data Gaps: {data_metrics['data_gaps']}")
            self.data_reconnections_label = QLabel(f"Reconnections: {data_metrics['reconnections']}")

            data_layout.addWidget(self.data_updates_label, 0, 0)
            data_layout.addWidget(self.data_gaps_label, 0, 1)
            data_layout.addWidget(self.data_reconnections_label, 1, 0)

            layout.addWidget(data_group)

        # Add tab
        self.status_tabs.addTab(widget, "Metrics")

    def _update_status_label(self, label, status):
        """Update status label with color"""
        # Get color
        color = STATUS_COLORS.get(status, QColor(100, 100, 100))

        # Set style
        label.setStyleSheet(f"""
            QLabel {{
                background-color: {color.name()};
                color: white;
                font-weight: bold;
                border-radius: 5px;
                padding: 5px;
            }}
        """)

        # Set text
        if label.text().count(":") > 0:
            parts = label.text().split(":", 1)
            label.setText(f"{parts[0]}: {status}")
        else:
            label.setText(status)

    @pyqtSlot()
    def _update_status(self):
        """Update status displays"""
        try:
            # Update connection status
            self._update_connection_status()

            # Update market data status
            if self.config.show_market_data_status and self.market_data_feed:
                self._update_market_data_status()

            # Update order status
            if self.config.show_order_status and self.order_manager:
                self._update_order_status()

            # Update risk metrics
            if self.config.show_risk_metrics and self.risk_manager:
                self._update_risk_metrics()

            # Update detailed metrics
            if self.config.show_detailed_metrics:
                self._update_detailed_metrics()

        except Exception as e:
            self.logger.error(f"Error updating status: {e}")
            self.error_handler.handle_error(e, "_update_status")

    def _update_connection_status(self):
        """Update connection status"""
        try:
            # Get status
            status = self.connect_api.get_status()

            # Update connection status label
            self._update_status_label(self.connection_status_label, status['state'])

            # Update session ID label
            session_id = status.get('session_id', 'N/A')
            self.session_id_label.setText(f"Session ID: {session_id}")

            # Update uptime label
            if status.get('connection_time_seconds'):
                hours, remainder = divmod(int(status['connection_time_seconds']), 3600)
                minutes, seconds = divmod(remainder, 60)
                self.uptime_label.setText(f"Uptime: {hours:02d}:{minutes:02d}:{seconds:02d}")

            # Emit signal
            self.status_changed.emit("connection", status['state'])

        except Exception as e:
            self.logger.error(f"Error updating connection status: {e}")
            self.error_handler.handle_error(e, "_update_connection_status")

    def _update_market_data_status(self):
        """Update market data status"""
        try:
            # Get status
            status = self.market_data_feed.get_status()

            # Update status label
            self._update_status_label(self.market_data_status_label, status['state'])

            # Update symbols table
            self._update_symbols_table()

            # Emit signal
            self.status_changed.emit("market_data", status['state'])

        except Exception as e:
            self.logger.error(f"Error updating market data status: {e}")
            self.error_handler.handle_error(e, "_update_market_data_status")

    def _update_order_status(self):
        """Update order status"""
        try:
            # Get active orders
            orders = self.order_manager.get_orders_by_state(OrderState.SUBMITTED)
            orders.extend(self.order_manager.get_orders_by_state(OrderState.ACKNOWLEDGED))
            orders.extend(self.order_manager.get_orders_by_state(OrderState.PARTIALLY_FILLED))

            # Update status label
            if orders:
                self._update_status_label(self.order_status_label, "ACTIVE")
            else:
                self._update_status_label(self.order_status_label, "NO_ORDERS")

            # Update orders table
            self._update_orders_table(orders)

            # Emit signal
            self.status_changed.emit("orders", "ACTIVE" if orders else "NO_ORDERS")

        except Exception as e:
            self.logger.error(f"Error updating order status: {e}")
            self.error_handler.handle_error(e, "_update_order_status")

    def _update_risk_metrics(self):
        """Update risk metrics"""
        try:
            # Get risk metrics
            risk_metrics = self.risk_manager.get_risk_metrics()

            if risk_metrics:
                # Update risk level label
                self._update_status_label(self.risk_level_label, risk_metrics.risk_level.name)

                # Update metric labels
                self.total_exposure_label.setText(f"Total Exposure: ${risk_metrics.total_exposure:,.2f}")
                self.daily_pnl_label.setText(f"Daily P&L: ${risk_metrics.daily_pnl:,.2f}")

                # Calculate margin usage
                margin_total = risk_metrics.margin_used + risk_metrics.margin_available
                margin_usage = (risk_metrics.margin_used / margin_total * 100) if margin_total > 0 else 0
                self.margin_usage_label.setText(f"Margin Usage: {margin_usage:.2f}%")

                self.concentration_label.setText(f"Max Concentration: {risk_metrics.max_concentration:.2%}")
                self.warnings_label.setText(f"Warnings: {len(risk_metrics.warnings)}")

                # Update positions table
                self._update_positions_table()

                # Emit signal
                self.status_changed.emit("risk", risk_metrics.risk_level.name)

        except Exception as e:
            self.logger.error(f"Error updating risk metrics: {e}")
            self.error_handler.handle_error(e, "_update_risk_metrics")

    def _update_detailed_metrics(self):
        """Update detailed metrics"""
        try:
            # Update Connect API metrics
            metrics = self.connect_api.get_metrics()
            self.messages_sent_label.setText(f"Messages Sent: {metrics['messages_sent']}")
            self.messages_received_label.setText(f"Messages Received: {metrics['messages_received']}")
            self.message_rate_label.setText(f"Message Rate: {metrics['message_rate']:.2f}/s")
            self.reconnections_label.setText(f"Reconnections: {metrics['reconnections']}")

            # Update order manager metrics
            if self.order_manager:
                order_metrics = self.order_manager.get_metrics()
                self.orders_submitted_label.setText(f"Orders Submitted: {order_metrics['orders_submitted']}")
                self.orders_filled_label.setText(f"Orders Filled: {order_metrics['orders_filled']}")
                self.orders_cancelled_label.setText(f"Orders Cancelled: {order_metrics['orders_cancelled']}")
                self.success_rate_label.setText(f"Success Rate: {order_metrics['success_rate']:.2f}%")

            # Update market data feed metrics
            if self.market_data_feed:
                data_metrics = self.market_data_feed.get_metrics()
                self.data_updates_label.setText(f"Data Updates: {data_metrics['data_updates']}")
                self.data_gaps_label.setText(f"Data Gaps: {data_metrics['data_gaps']}")
                self.data_reconnections_label.setText(f"Reconnections: {data_metrics['reconnections']}")

        except Exception as e:
            self.logger.error(f"Error updating detailed metrics: {e}")
            self.error_handler.handle_error(e, "_update_detailed_metrics")

    def _update_symbols_table(self):
        """Update symbols table"""
        try:
            # Get symbols
            symbols = self.config.symbols if hasattr(self.config, 'symbols') else []

            # Set row count
            self.symbols_table.setRowCount(len(symbols))

            # Update table
            for i, symbol in enumerate(symbols):
                # Get latest data
                data = self.market_data_feed.get_latest_data(symbol) if self.market_data_feed else None

                if data:
                    # Symbol
                    self.symbols_table.setItem(i, 0, QTableWidgetItem(symbol))

                    # Last price
                    self.symbols_table.setItem(i, 1, QTableWidgetItem(f"{data.last_price:.2f}"))

                    # Bid/Ask
                    bid_ask = ""
                    if data.bid_price and data.ask_price:
                        bid_ask = f"{data.bid_price:.2f}/{data.ask_price:.2f}"
                    self.symbols_table.setItem(i, 2, QTableWidgetItem(bid_ask))

                    # Update time
                    update_time = data.timestamp.strftime("%H:%M:%S")
                    self.symbols_table.setItem(i, 3, QTableWidgetItem(update_time))
                else:
                    # Symbol
                    self.symbols_table.setItem(i, 0, QTableWidgetItem(symbol))

                    # No data
                    self.symbols_table.setItem(i, 1, QTableWidgetItem("N/A"))
                    self.symbols_table.setItem(i, 2, QTableWidgetItem("N/A"))
                    self.symbols_table.setItem(i, 3, QTableWidgetItem("N/A"))

        except Exception as e:
            self.logger.error(f"Error updating symbols table: {e}")
            self.error_handler.handle_error(e, "_update_symbols_table")

    def _update_orders_table(self, orders):
        """Update orders table"""
        try:
            # Set row count
            self.orders_table.setRowCount(len(orders))

            # Update table
            for i, order in enumerate(orders):
                # Order ID
                self.orders_table.setItem(i, 0, QTableWidgetItem(order.order_id))

                # Symbol
                self.orders_table.setItem(i, 1, QTableWidgetItem(order.symbol))

                # Side
                self.orders_table.setItem(i, 2, QTableWidgetItem(order.side.value))

                # Type
                self.orders_table.setItem(i, 3, QTableWidgetItem(order.order_type.value))

                # Quantity
                self.orders_table.setItem(i, 4, QTableWidgetItem(str(order.quantity)))

                # Status
                self.orders_table.setItem(i, 5, QTableWidgetItem(order.state.name))

        except Exception as e:
            self.logger.error(f"Error updating orders table: {e}")
            self.error_handler.handle_error(e, "_update_orders_table")

    def _update_positions_table(self):
        """Update positions table"""
        try:
            # Get positions
            positions = self.risk_manager.get_positions()

            # Calculate total value
            total_value = sum(abs(pos.market_value) for pos in positions.values())

            # Set row count
            self.positions_table.setRowCount(len(positions))

            # Update table
            for i, (symbol, position) in enumerate(positions.items()):
                # Symbol
                self.positions_table.setItem(i, 0, QTableWidgetItem(symbol))

                # Quantity
                self.positions_table.setItem(i, 1, QTableWidgetItem(str(position.quantity)))

                # Market value
                self.positions_table.setItem(i, 2, QTableWidgetItem(f"${position.market_value:,.2f}"))

                # Unrealized P&L
                self.positions_table.setItem(i, 3, QTableWidgetItem(f"${position.unrealized_pnl:,.2f}"))

                # % of portfolio
                portfolio_pct = (abs(position.market_value) / total_value * 100) if total_value > 0 else 0
                self.positions_table.setItem(i, 4, QTableWidgetItem(f"{portfolio_pct:.2f}%"))

        except Exception as e:
            self.logger.error(f"Error updating positions table: {e}")
            self.error_handler.handle_error(e, "_update_positions_table")

    def stop(self):
        """Stop the status widget"""
        try:
            self.logger.info("Stopping ConnectAPIStatusWidget...")

            # Stop status timer
            self._status_timer.stop()

            self.logger.info("ConnectAPIStatusWidget stopped")

        except Exception as e:
            self.logger.error(f"Error stopping status widget: {e}")
            self.error_handler.handle_error(e, "stop")


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_status_widget(
    config: StatusConfig,
    connect_api: ConnectAPI,
    order_manager: Optional[OrderManager] = None,
    market_data_feed: Optional[MarketDataFeed] = None,
    risk_manager: Optional[RiskManager] = None,
    parent=None
) -> ConnectAPIStatusWidget:
    """
    Factory function to create a status widget instance.

    Args:
        config: Status display configuration
        connect_api: Connect API instance
        order_manager: Order manager instance
        market_data_feed: Market data feed instance
        risk_manager: Risk manager instance
        parent: Parent widget

    Returns:
        ConnectAPIStatusWidget instance
    """
    return ConnectAPIStatusWidget(
        config, connect_api, order_manager, market_data_feed, risk_manager, parent
    )


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code
    print("="*80)
    print("SPYDER Connect API Status Widget Test")
    print("="*80)

    # This would require actual GUI and Connect API to test
    print("Status widget module loaded successfully")

    print("\n" + "="*80)
    print("Module testing completed.")
    print("="*80)