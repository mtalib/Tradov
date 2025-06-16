#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderG02_Dashboard.py
Group: G (User Interface)
Purpose: Real-time trading dashboard with mode selection

Description:
    This module provides the main trading dashboard with three distinct modes:
    - Backtesting: Logic testing only with IB historical data
    - Paper Trading: Real market simulation with IB paper account
    - Live Trading: Real money trading with safety features

    The dashboard displays real-time positions, P&L, market data, and
    strategy performance with mode-specific features and warnings.

Author: Mohamed Talib
Date: 2025-05-31
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import datetime
import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import threading

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QSplitter,
    QGroupBox,
    QTabWidget,
    QTextEdit,
    QProgressBar,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QMessageBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QScrollArea,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot, QThread
from PyQt5.QtGui import QFont, QPalette, QColor, QIcon, QPixmap

import pandas as pd
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType
from SpyderG_GUI.SpyderG05_ChartWidget import ChartWidget

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Trading modes
TRADING_MODE_BACKTEST = "BACKTEST"
TRADING_MODE_PAPER = "PAPER"
TRADING_MODE_LIVE = "LIVE"

# Mode colors and warnings
MODE_COLORS = {
    TRADING_MODE_BACKTEST: "#FFE4B5",  # Moccasin
    TRADING_MODE_PAPER: "#90EE90",  # Light Green
    TRADING_MODE_LIVE: "#FFB6C1",  # Light Pink
}

MODE_WARNINGS = {
    TRADING_MODE_BACKTEST: "⚠️ BACKTESTING MODE - Logic Testing Only! Results NOT valid for performance estimation!",
    TRADING_MODE_PAPER: "📝 PAPER TRADING MODE - No real money at risk. Great for learning!",
    TRADING_MODE_LIVE: "💰 LIVE TRADING MODE - REAL MONEY AT RISK! Trade carefully!",
}

# Update intervals
FAST_UPDATE_MS = 1000  # 1 second
NORMAL_UPDATE_MS = 5000  # 5 seconds
SLOW_UPDATE_MS = 30000  # 30 seconds


# ==============================================================================
# TRADING MODE SELECTOR DIALOG
# ==============================================================================
class TradingModeSelectorDialog(QDialog):
    """Dialog for selecting trading mode with detailed warnings"""

    def __init__(self, parent=None, current_mode=None):
        super().__init__(parent)
        self.selected_mode = current_mode
        self.paper_stats = self._load_paper_stats()
        self.setup_ui()

    def setup_ui(self):
        """Setup the mode selector UI"""
        self.setWindowTitle("Select Trading Mode")
        self.setMinimumSize(800, 600)

        layout = QVBoxLayout()

        # Title
        title = QLabel("Select Trading Mode")
        title.setAlignment(Qt.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Mode buttons
        self.mode_buttons = []

        # Backtesting mode
        backtest_group = self._create_mode_group(
            TRADING_MODE_BACKTEST,
            "📊 Backtesting Mode",
            "Test strategy logic with historical data",
            [
                "✅ Test strategy entry/exit logic",
                "✅ Debug code functionality",
                "✅ Find parameter boundaries",
                "✅ Uses real IB historical data",
                "❌ NOT for performance validation",
                "❌ Cannot simulate realistic fills",
                "❌ Ignores bid-ask spreads",
                "❌ No assignment risk modeling",
            ],
            MODE_COLORS[TRADING_MODE_BACKTEST],
        )
        layout.addWidget(backtest_group)

        # Paper trading mode
        paper_group = self._create_mode_group(
            TRADING_MODE_PAPER,
            "📝 Paper Trading Mode",
            "Practice with real market conditions",
            [
                "✅ Real market data",
                "✅ Actual bid-ask spreads",
                "✅ Realistic execution",
                "✅ No money at risk",
                "✅ Perfect for learning",
                "✅ Tracks all metrics",
                "📋 4-8 weeks recommended",
                "📋 Minimum 50 trades suggested",
            ],
            MODE_COLORS[TRADING_MODE_PAPER],
        )
        layout.addWidget(paper_group)

        # Add paper trading stats
        if self.paper_stats:
            stats_label = QLabel(
                f"Paper Trading Progress: {self.paper_stats['days']} days, "
                f"{self.paper_stats['trades']} trades, "
                f"{self.paper_stats['win_rate']:.1%} win rate"
            )
            stats_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(stats_label)

        # Live trading mode
        live_warnings = [
            "💰 REAL MONEY AT RISK",
            "⚠️ Losses are permanent",
            "⚠️ Requires experience",
            "✅ Start with 1-2 contracts",
            "✅ Use strict risk management",
            "✅ Monitor continuously",
        ]

        # Add requirements if not met
        if not self._check_live_requirements():
            live_warnings.extend(
                [
                    "❌ Requires 28+ days paper trading",
                    "❌ Requires 50+ paper trades",
                    "❌ Requires 40%+ paper win rate",
                ]
            )

        live_group = self._create_mode_group(
            TRADING_MODE_LIVE,
            "💰 Live Trading Mode",
            "Trade with real money",
            live_warnings,
            MODE_COLORS[TRADING_MODE_LIVE],
        )
        layout.addWidget(live_group)

        # Buttons
        button_layout = QHBoxLayout()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        button_layout.addStretch()

        select_btn = QPushButton("Select Mode")
        select_btn.clicked.connect(self.accept_selection)
        select_btn.setEnabled(False)
        self.select_btn = select_btn
        button_layout.addWidget(select_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def _create_mode_group(self, mode, title, description, features, color):
        """Create a mode selection group"""
        group = QGroupBox()
        group.setStyleSheet(
            f"""
            QGroupBox {{
                background-color: {color};
                border: 2px solid #ccc;
                border-radius: 10px;
                padding: 10px;
                margin: 5px;
            }}
            QGroupBox:hover {{
                border: 3px solid #666;
            }}
        """
        )

        layout = QVBoxLayout()

        # Title and description
        title_label = QLabel(title)
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Features
        features_text = "\n".join(features)
        features_label = QLabel(features_text)
        features_label.setWordWrap(True)
        layout.addWidget(features_label)

        # Select button
        select_btn = QPushButton(f"Choose {title}")
        select_btn.clicked.connect(lambda: self._select_mode(mode))
        layout.addWidget(select_btn)

        group.setLayout(layout)
        return group

    def _select_mode(self, mode):
        """Select a trading mode"""
        self.selected_mode = mode
        self.select_btn.setEnabled(True)
        self.select_btn.setText(f"Start {mode} Mode")

    def accept_selection(self):
        """Accept the selected mode with confirmation"""
        if not self.selected_mode:
            return

        # Extra confirmation for live mode
        if self.selected_mode == TRADING_MODE_LIVE:
            # Check requirements
            if not self._check_live_requirements():
                QMessageBox.warning(
                    self,
                    "Not Ready for Live Trading",
                    "You must complete the following before live trading:\n\n"
                    "• 28+ days of paper trading\n"
                    "• 50+ paper trades\n"
                    "• 40%+ win rate in paper trading\n\n"
                    "Please continue paper trading.",
                )
                return

            # Triple confirmation
            reply = QMessageBox.question(
                self,
                "Confirm Live Trading",
                "Are you SURE you want to trade with REAL MONEY?\n\n"
                "• Real losses are possible\n"
                "• Start with small positions\n"
                "• Monitor continuously\n\n"
                "Continue to live trading?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )

            if reply != QMessageBox.Yes:
                return

        self.accept()

    def _load_paper_stats(self):
        """Load paper trading statistics"""
        try:
            # Look for most recent paper session
            import glob

            sessions = glob.glob("paper_session_*.json")
            if not sessions:
                return None

            # Load most recent
            latest = max(sessions)
            with open(latest, "r") as f:
                data = json.load(f)
                session = data.get("session", {})

                return {
                    "days": session.get("duration_days", 0),
                    "trades": session.get("total_trades", 0),
                    "win_rate": session.get("win_rate", 0),
                }
        except:
            return None

    def _check_live_requirements(self):
        """Check if requirements are met for live trading"""
        if not self.paper_stats:
            return False

        return (
            self.paper_stats["days"] >= 28
            and self.paper_stats["trades"] >= 50
            and self.paper_stats["win_rate"] >= 0.40
        )


# ==============================================================================
# MAIN DASHBOARD CLASS
# ==============================================================================
class TradingDashboard(QMainWindow):
    """
    Main trading dashboard with three-mode system.

    Features:
    - Mode selection (Backtest/Paper/Live)
    - Real-time position monitoring
    - Strategy performance tracking
    - Risk management display
    - Mode-specific warnings and features
    """

    # Signals
    mode_changed = pyqtSignal(str)

    def __init__(self, event_manager: EventManager):
        """
        Initialize the trading dashboard.

        Args:
            event_manager: Event manager for system communication
        """
        super().__init__()
        self.event_manager = event_manager
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Trading mode
        self.trading_mode = None

        # Data storage
        self.positions = {}
        self.orders = {}
        self.market_data = {}
        self.strategy_stats = {}
        self.account_info = {
            "balance": 100000,
            "buying_power": 100000,
            "daily_pnl": 0,
            "total_pnl": 0,
        }

        # UI components
        self.position_table = None
        self.order_table = None
        self.strategy_table = None
        self.chart_widget = None
        self.log_widget = None
        self.mode_banner = None

        # Timers
        self.update_timers = []

        # Setup UI
        self.setup_ui()

        # Register event handlers
        self._register_event_handlers()

        # Show mode selector on startup
        QTimer.singleShot(100, self.select_trading_mode)

        self.logger.info("Trading dashboard initialized")

    # ==========================================================================
    # UI SETUP
    # ==========================================================================
    def setup_ui(self):
        """Setup the main UI"""
        self.setWindowTitle("SPYDER Trading System")
        self.setGeometry(100, 100, 1600, 900)

        # Set dark theme
        self.setStyleSheet(
            """
            QMainWindow {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
            }
            QTableWidget {
                background-color: #2d2d2d;
                color: #ffffff;
                gridline-color: #3d3d3d;
            }
            QGroupBox {
                border: 1px solid #3d3d3d;
                border-radius: 5px;
                margin-top: 10px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QPushButton {
                background-color: #3d3d3d;
                color: #ffffff;
                border: 1px solid #4d4d4d;
                padding: 5px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
            }
            QPushButton:pressed {
                background-color: #2d2d2d;
            }
        """
        )

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout()

        # Mode banner (will be updated based on selected mode)
        self.mode_banner = QLabel("No Mode Selected")
        self.mode_banner.setAlignment(Qt.AlignCenter)
        self.mode_banner.setStyleSheet(
            """
            QLabel {
                font-size: 16px;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
        """
        )
        main_layout.addWidget(self.mode_banner)

        # Control panel
        control_panel = self._create_control_panel()
        main_layout.addWidget(control_panel)

        # Main content splitter
        content_splitter = QSplitter(Qt.Horizontal)

        # Left panel - Positions and Orders
        left_panel = self._create_left_panel()
        content_splitter.addWidget(left_panel)

        # Center panel - Chart and Market Data
        center_panel = self._create_center_panel()
        content_splitter.addWidget(center_panel)

        # Right panel - Strategy and Account Info
        right_panel = self._create_right_panel()
        content_splitter.addWidget(right_panel)

        # Set splitter sizes
        content_splitter.setSizes([500, 700, 400])

        main_layout.addWidget(content_splitter)

        # Status bar
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Initializing...")

        central_widget.setLayout(main_layout)

        # Setup timers
        self._setup_timers()

    def _create_control_panel(self):
        """Create the control panel"""
        panel = QGroupBox("Controls")
        layout = QHBoxLayout()

        # Mode selector button
        self.mode_btn = QPushButton("Change Mode")
        self.mode_btn.clicked.connect(self.select_trading_mode)
        layout.addWidget(self.mode_btn)

        # Emergency stop (for live mode)
        self.emergency_stop_btn = QPushButton("🛑 EMERGENCY STOP")
        self.emergency_stop_btn.clicked.connect(self.emergency_stop)
        self.emergency_stop_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #ff4444;
                font-weight: bold;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #ff6666;
            }
        """
        )
        self.emergency_stop_btn.setVisible(False)  # Hidden until live mode
        layout.addWidget(self.emergency_stop_btn)

        layout.addStretch()

        # Strategy controls
        self.start_btn = QPushButton("▶ Start Trading")
        self.start_btn.clicked.connect(self.start_trading)
        layout.addWidget(self.start_btn)

        self.pause_btn = QPushButton("⏸ Pause Trading")
        self.pause_btn.clicked.connect(self.pause_trading)
        self.pause_btn.setEnabled(False)
        layout.addWidget(self.pause_btn)

        self.stop_btn = QPushButton("⏹ Stop Trading")
        self.stop_btn.clicked.connect(self.stop_trading)
        self.stop_btn.setEnabled(False)
        layout.addWidget(self.stop_btn)

        panel.setLayout(layout)
        return panel

    def _create_left_panel(self):
        """Create left panel with positions and orders"""
        panel = QWidget()
        layout = QVBoxLayout()

        # Positions
        positions_group = QGroupBox("Open Positions")
        positions_layout = QVBoxLayout()

        self.position_table = QTableWidget()
        self.position_table.setColumnCount(8)
        self.position_table.setHorizontalHeaderLabels(
            ["Symbol", "Qty", "Entry", "Current", "P&L", "P&L %", "Time", "Action"]
        )
        self.position_table.horizontalHeader().setStretchLastSection(True)
        positions_layout.addWidget(self.position_table)

        positions_group.setLayout(positions_layout)
        layout.addWidget(positions_group)

        # Orders
        orders_group = QGroupBox("Active Orders")
        orders_layout = QVBoxLayout()

        self.order_table = QTableWidget()
        self.order_table.setColumnCount(6)
        self.order_table.setHorizontalHeaderLabels(
            ["ID", "Symbol", "Side", "Qty", "Price", "Status"]
        )
        self.order_table.horizontalHeader().setStretchLastSection(True)
        orders_layout.addWidget(self.order_table)

        orders_group.setLayout(orders_layout)
        layout.addWidget(orders_group)

        panel.setLayout(layout)
        return panel

    def _create_center_panel(self):
        """Create center panel with chart and market data"""
        panel = QWidget()
        layout = QVBoxLayout()

        # Chart
        chart_group = QGroupBox("SPY Price Chart")
        chart_layout = QVBoxLayout()

        self.chart_widget = ChartWidget()
        chart_layout.addWidget(self.chart_widget)

        chart_group.setLayout(chart_layout)
        layout.addWidget(chart_group)

        # Market internals
        internals_group = QGroupBox("Market Internals")
        internals_layout = QGridLayout()

        self.vix_label = QLabel("VIX: --")
        self.add_label = QLabel("ADD: --")
        self.tick_label = QLabel("TICK: --")
        self.volume_label = QLabel("Volume: --")

        internals_layout.addWidget(self.vix_label, 0, 0)
        internals_layout.addWidget(self.add_label, 0, 1)
        internals_layout.addWidget(self.tick_label, 1, 0)
        internals_layout.addWidget(self.volume_label, 1, 1)

        internals_group.setLayout(internals_layout)
        layout.addWidget(internals_group)

        panel.setLayout(layout)
        return panel

    def _create_right_panel(self):
        """Create right panel with strategy and account info"""
        panel = QWidget()
        layout = QVBoxLayout()

        # Account info
        account_group = QGroupBox("Account Information")
        account_layout = QGridLayout()

        self.balance_label = QLabel("Balance: $100,000")
        self.buying_power_label = QLabel("Buying Power: $100,000")
        self.daily_pnl_label = QLabel("Daily P&L: $0")
        self.total_pnl_label = QLabel("Total P&L: $0")

        account_layout.addWidget(self.balance_label, 0, 0)
        account_layout.addWidget(self.buying_power_label, 0, 1)
        account_layout.addWidget(self.daily_pnl_label, 1, 0)
        account_layout.addWidget(self.total_pnl_label, 1, 1)

        account_group.setLayout(account_layout)
        layout.addWidget(account_group)

        # Strategy performance
        strategy_group = QGroupBox("Strategy Performance")
        strategy_layout = QVBoxLayout()

        self.strategy_table = QTableWidget()
        self.strategy_table.setColumnCount(5)
        self.strategy_table.setHorizontalHeaderLabels(
            ["Strategy", "Trades", "Win %", "P&L", "Status"]
        )
        self.strategy_table.horizontalHeader().setStretchLastSection(True)
        strategy_layout.addWidget(self.strategy_table)

        strategy_group.setLayout(strategy_layout)
        layout.addWidget(strategy_group)

        # Log
        log_group = QGroupBox("Trading Log")
        log_layout = QVBoxLayout()

        self.log_widget = QTextEdit()
        self.log_widget.setReadOnly(True)
        self.log_widget.setMaximumHeight(200)
        log_layout.addWidget(self.log_widget)

        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        panel.setLayout(layout)
        return panel

    # ==========================================================================
    # MODE MANAGEMENT
    # ==========================================================================
    def select_trading_mode(self):
        """Show mode selector dialog"""
        dialog = TradingModeSelectorDialog(self, self.trading_mode)

        if dialog.exec_():
            new_mode = dialog.selected_mode
            if new_mode != self.trading_mode:
                self.change_trading_mode(new_mode)

    def change_trading_mode(self, new_mode: str):
        """Change the trading mode"""
        # Confirm if switching from live
        if self.trading_mode == TRADING_MODE_LIVE and new_mode != TRADING_MODE_LIVE:
            reply = QMessageBox.question(
                self,
                "Exit Live Trading",
                "Are you sure you want to exit live trading mode?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )

            if reply != QMessageBox.Yes:
                return

        # Stop current operations
        if self.trading_mode:
            self.stop_trading()

        # Change mode
        old_mode = self.trading_mode
        self.trading_mode = new_mode

        # Update UI
        self._update_mode_ui()

        # Emit signal
        self.mode_changed.emit(new_mode)

        # Log
        self.log_message(f"Switched from {old_mode} to {new_mode} mode")
        self.logger.info(f"Trading mode changed to {new_mode}")

        # Show mode-specific message
        if new_mode == TRADING_MODE_BACKTEST:
            QMessageBox.information(
                self,
                "Backtesting Mode",
                "You are now in BACKTESTING mode.\n\n"
                "• Use this for testing strategy logic only\n"
                "• Results are NOT realistic for trading\n"
                "• Perfect for debugging and development",
            )
        elif new_mode == TRADING_MODE_PAPER:
            QMessageBox.information(
                self,
                "Paper Trading Mode",
                "You are now in PAPER TRADING mode.\n\n"
                "• Real market data with IB paper account\n"
                "• No real money at risk\n"
                "• Trade for 4-8 weeks before going live\n"
                "• All metrics are tracked for learning",
            )
        elif new_mode == TRADING_MODE_LIVE:
            QMessageBox.warning(
                self,
                "Live Trading Mode",
                "⚠️ You are now in LIVE TRADING mode! ⚠️\n\n"
                "• REAL MONEY IS AT RISK\n"
                "• Start with small positions (1-2 contracts)\n"
                "• Monitor continuously\n"
                "• Use the emergency stop if needed\n\n"
                "Trade responsibly!",
            )

    def _update_mode_ui(self):
        """Update UI based on current mode"""
        if not self.trading_mode:
            return

        # Update banner
        self.mode_banner.setText(MODE_WARNINGS[self.trading_mode])
        self.mode_banner.setStyleSheet(
            f"""
            QLabel {{
                font-size: 16px;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
                background-color: {MODE_COLORS[self.trading_mode]};
                color: #000000;
            }}
        """
        )

        # Update mode button
        self.mode_btn.setText(f"Mode: {self.trading_mode}")

        # Show/hide emergency stop
        self.emergency_stop_btn.setVisible(self.trading_mode == TRADING_MODE_LIVE)

        # Update window title
        self.setWindowTitle(f"SPYDER Trading System - {self.trading_mode} Mode")

        # Update status bar
        self.status_bar.showMessage(f"{self.trading_mode} Mode Active")

    # ==========================================================================
    # TRADING CONTROLS
    # ==========================================================================
    def start_trading(self):
        """Start trading in current mode"""
        if not self.trading_mode:
            QMessageBox.warning(
                self, "No Mode Selected", "Please select a trading mode first."
            )
            return

        # Mode-specific confirmation
        if self.trading_mode == TRADING_MODE_LIVE:
            reply = QMessageBox.question(
                self,
                "Start Live Trading",
                "Are you ready to start LIVE TRADING with REAL MONEY?\n\n"
                "Make sure you have:\n"
                "• Checked all strategies\n"
                "• Set appropriate position sizes\n"
                "• Reviewed risk parameters\n\n"
                "Continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )

            if reply != QMessageBox.Yes:
                return

        # Emit start event
        self.event_manager.emit(
            Event(
                EventType.SYSTEM, {"type": "trading_start", "mode": self.trading_mode}
            )
        )

        # Update buttons
        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)

        self.log_message(f"Started {self.trading_mode} trading")

    def pause_trading(self):
        """Pause trading"""
        self.event_manager.emit(
            Event(
                EventType.SYSTEM, {"type": "trading_pause", "mode": self.trading_mode}
            )
        )

        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)

        self.log_message("Trading paused")

    def stop_trading(self):
        """Stop trading"""
        # Confirm if in live mode
        if self.trading_mode == TRADING_MODE_LIVE:
            reply = QMessageBox.question(
                self,
                "Stop Live Trading",
                "Are you sure you want to stop live trading?\n\n"
                "• All strategies will be halted\n"
                "• Open positions will remain open\n"
                "• No new trades will be placed",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )

            if reply != QMessageBox.Yes:
                return

        self.event_manager.emit(
            Event(EventType.SYSTEM, {"type": "trading_stop", "mode": self.trading_mode})
        )

        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)

        self.log_message("Trading stopped")

    def emergency_stop(self):
        """Emergency stop - close all positions immediately"""
        reply = QMessageBox.critical(
            self,
            "EMERGENCY STOP",
            "⚠️ EMERGENCY STOP ⚠️\n\n"
            "This will:\n"
            "• IMMEDIATELY stop all trading\n"
            "• Close ALL open positions at MARKET\n"
            "• Cancel ALL pending orders\n\n"
            "This may result in significant losses!\n\n"
            "Are you SURE?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            # Double confirmation
            second_reply = QMessageBox.critical(
                self,
                "CONFIRM EMERGENCY STOP",
                "This is your FINAL confirmation.\n\n"
                "Click Yes to execute EMERGENCY STOP.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )

            if second_reply == QMessageBox.Yes:
                self.event_manager.emit(
                    Event(
                        EventType.SYSTEM,
                        {"type": "emergency_stop", "mode": self.trading_mode},
                    )
                )

                self.log_message("🛑 EMERGENCY STOP EXECUTED! 🛑")
                self.stop_trading()

    # ==========================================================================
    # DATA UPDATES
    # ==========================================================================
    def _setup_timers(self):
        """Setup update timers"""
        # Fast updates (positions, orders)
        fast_timer = QTimer()
        fast_timer.timeout.connect(self._update_fast)
        fast_timer.start(FAST_UPDATE_MS)
        self.update_timers.append(fast_timer)

        # Normal updates (account, strategy)
        normal_timer = QTimer()
        normal_timer.timeout.connect(self._update_normal)
        normal_timer.start(NORMAL_UPDATE_MS)
        self.update_timers.append(normal_timer)

        # Slow updates (charts)
        slow_timer = QTimer()
        slow_timer.timeout.connect(self._update_slow)
        slow_timer.start(SLOW_UPDATE_MS)
        self.update_timers.append(slow_timer)

    @pyqtSlot()
    def _update_fast(self):
        """Fast updates - positions and orders"""
        self._update_positions()
        self._update_orders()
        self._update_market_internals()

    @pyqtSlot()
    def _update_normal(self):
        """Normal updates - account and strategy"""
        self._update_account_info()
        self._update_strategy_performance()

    @pyqtSlot()
    def _update_slow(self):
        """Slow updates - charts"""
        self._update_charts()

    def _update_positions(self):
        """Update positions table"""
        # Mode-specific behavior
        if self.trading_mode == TRADING_MODE_BACKTEST:
            # Show simulated positions
            self._add_mode_indicator("SIMULATED", self.position_table)

        # Update table
        self.position_table.setRowCount(len(self.positions))

        for row, (symbol, position) in enumerate(self.positions.items()):
            self.position_table.setItem(row, 0, QTableWidgetItem(symbol))
            self.position_table.setItem(
                row, 1, QTableWidgetItem(str(position.get("quantity", 0)))
            )
            self.position_table.setItem(
                row, 2, QTableWidgetItem(f"${position.get('entry_price', 0):.2f}")
            )
            self.position_table.setItem(
                row, 3, QTableWidgetItem(f"${position.get('current_price', 0):.2f}")
            )

            # P&L coloring
            pnl = position.get("pnl", 0)
            pnl_item = QTableWidgetItem(f"${pnl:.2f}")
            pnl_item.setForeground(QColor("green" if pnl >= 0 else "red"))
            self.position_table.setItem(row, 4, pnl_item)

            pnl_pct = position.get("pnl_percent", 0)
            pnl_pct_item = QTableWidgetItem(f"{pnl_pct:.1f}%")
            pnl_pct_item.setForeground(QColor("green" if pnl_pct >= 0 else "red"))
            self.position_table.setItem(row, 5, pnl_pct_item)

            self.position_table.setItem(
                row, 6, QTableWidgetItem(position.get("time", ""))
            )

            # Action button
            if self.trading_mode == TRADING_MODE_LIVE:
                close_btn = QPushButton("Close")
                close_btn.clicked.connect(lambda _, s=symbol: self._close_position(s))
                self.position_table.setCellWidget(row, 7, close_btn)

    def _update_orders(self):
        """Update orders table"""
        # Mode-specific behavior
        if self.trading_mode == TRADING_MODE_BACKTEST:
            self._add_mode_indicator("SIMULATED", self.order_table)

        self.order_table.setRowCount(len(self.orders))

        for row, (order_id, order) in enumerate(self.orders.items()):
            self.order_table.setItem(row, 0, QTableWidgetItem(str(order_id)))
            self.order_table.setItem(row, 1, QTableWidgetItem(order.get("symbol", "")))
            self.order_table.setItem(row, 2, QTableWidgetItem(order.get("side", "")))
            self.order_table.setItem(
                row, 3, QTableWidgetItem(str(order.get("quantity", 0)))
            )
            self.order_table.setItem(
                row, 4, QTableWidgetItem(f"${order.get('price', 0):.2f}")
            )
            self.order_table.setItem(row, 5, QTableWidgetItem(order.get("status", "")))

    def _update_account_info(self):
        """Update account information"""
        # Mode-specific labeling
        prefix = ""
        if self.trading_mode == TRADING_MODE_BACKTEST:
            prefix = "[SIMULATED] "
        elif self.trading_mode == TRADING_MODE_PAPER:
            prefix = "[PAPER] "

        self.balance_label.setText(
            f"{prefix}Balance: ${self.account_info['balance']:,.2f}"
        )
        self.buying_power_label.setText(
            f"{prefix}Buying Power: ${self.account_info['buying_power']:,.2f}"
        )

        # Color code P&L
        daily_pnl = self.account_info["daily_pnl"]
        self.daily_pnl_label.setText(f"{prefix}Daily P&L: ${daily_pnl:,.2f}")
        self.daily_pnl_label.setStyleSheet(
            f"color: {'green' if daily_pnl >= 0 else 'red'}"
        )

        total_pnl = self.account_info["total_pnl"]
        self.total_pnl_label.setText(f"{prefix}Total P&L: ${total_pnl:,.2f}")
        self.total_pnl_label.setStyleSheet(
            f"color: {'green' if total_pnl >= 0 else 'red'}"
        )

    def _update_strategy_performance(self):
        """Update strategy performance table"""
        self.strategy_table.setRowCount(len(self.strategy_stats))

        for row, (strategy, stats) in enumerate(self.strategy_stats.items()):
            self.strategy_table.setItem(row, 0, QTableWidgetItem(strategy))
            self.strategy_table.setItem(
                row, 1, QTableWidgetItem(str(stats.get("trades", 0)))
            )

            win_rate = stats.get("win_rate", 0)
            win_item = QTableWidgetItem(f"{win_rate:.1f}%")
            win_item.setForeground(QColor("green" if win_rate >= 50 else "red"))
            self.strategy_table.setItem(row, 2, win_item)

            pnl = stats.get("pnl", 0)
            pnl_item = QTableWidgetItem(f"${pnl:.2f}")
            pnl_item.setForeground(QColor("green" if pnl >= 0 else "red"))
            self.strategy_table.setItem(row, 3, pnl_item)

            self.strategy_table.setItem(
                row, 4, QTableWidgetItem(stats.get("status", "Active"))
            )

    def _update_market_internals(self):
        """Update market internals display"""
        vix = self.market_data.get("VIX", {}).get("last", 0)
        self.vix_label.setText(f"VIX: {vix:.2f}")
        self.vix_label.setStyleSheet(f"color: {'red' if vix > 20 else 'green'}")

        add = self.market_data.get("ADD", {}).get("value", 0)
        self.add_label.setText(f"ADD: {add:+.0f}")
        self.add_label.setStyleSheet(f"color: {'green' if add > 0 else 'red'}")

        tick = self.market_data.get("TICK", {}).get("value", 0)
        self.tick_label.setText(f"TICK: {tick:+.0f}")
        self.tick_label.setStyleSheet(f"color: {'green' if tick > 0 else 'red'}")

        volume = self.market_data.get("SPY", {}).get("volume", 0)
        self.volume_label.setText(f"Volume: {volume:,.0f}")

    def _update_charts(self):
        """Update price charts"""
        # Get SPY data
        spy_data = self.market_data.get("SPY", {})
        if spy_data and hasattr(self.chart_widget, "update_data"):
            self.chart_widget.update_data(spy_data)

    def _add_mode_indicator(self, text: str, widget: QTableWidget):
        """Add mode indicator to table"""
        if widget.rowCount() == 0:
            widget.insertRow(0)
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignCenter)
            widget.setItem(0, 0, item)
            widget.setSpan(0, 0, 1, widget.columnCount())

    # ==========================================================================
    # EVENT HANDLERS
    # ==========================================================================
    def _register_event_handlers(self):
        """Register event handlers"""
        # Position updates
        self.event_manager.subscribe(
            self._handle_position_update,
            event_type=EventType.POSITION,
            subscriber_id="dashboard_position",
        )

        # Order updates
        self.event_manager.subscribe(
            self._handle_order_update,
            event_type=EventType.ORDER,
            subscriber_id="dashboard_order",
        )

        # Market data
        self.event_manager.subscribe(
            self._handle_market_data,
            event_type=EventType.MARKET_DATA,
            subscriber_id="dashboard_market",
        )

        # Account updates
        self.event_manager.subscribe(
            self._handle_account_update,
            event_type=EventType.ACCOUNT,
            subscriber_id="dashboard_account",
        )

        # System events
        self.event_manager.subscribe(
            self._handle_system_event,
            event_type=EventType.SYSTEM,
            subscriber_id="dashboard_system",
        )

        # New event subscriptions
        self._setup_event_subscriptions()

    def _setup_event_subscriptions(self):
        """Subscribe to relevant events."""
        try:
            if self.event_manager:
                # Subscribe to events with proper method checks
                if hasattr(self, "_handle_position_update"):
                    self.event_manager.subscribe(
                        "POSITION_UPDATED", self._handle_position_update
                    )
                if hasattr(self, "_handle_portfolio_update"):
                    self.event_manager.subscribe(
                        "PORTFOLIO_UPDATED", self._handle_portfolio_update
                    )
                if hasattr(self, "_handle_account_update"):
                    self.event_manager.subscribe(
                        "ACCOUNT_UPDATE", self._handle_account_update
                    )
                if hasattr(self, "_handle_trade_update"):
                    self.event_manager.subscribe(
                        "TRADE_EXECUTED", self._handle_trade_update
                    )
                if hasattr(self, "_handle_market_data"):
                    self.event_manager.subscribe(
                        "MARKET_DATA", self._handle_market_data
                    )

                self.logger.debug("Event subscriptions set up successfully")

        except Exception as e:
            self.logger.error(f"Failed to set up event subscriptions: {str(e)}")

    def _handle_position_update(self, event):
        """Handle position update events."""
        try:
            position_data = event.get("data", {})
            self.logger.debug(f"Position update received: {position_data}")
            # Update position display
            if hasattr(self, "position_widget"):
                self.position_widget.update_positions(position_data)
        except Exception as e:
            self.logger.error(f"Error handling position update: {e}")

    def _handle_portfolio_update(self, event):
        """Handle portfolio update events."""
        try:
            portfolio_data = event.get("data", {})
            self.logger.debug(f"Portfolio update received: {portfolio_data}")
            # Update portfolio display
            if hasattr(self, "portfolio_widget"):
                self.portfolio_widget.update_portfolio(portfolio_data)
        except Exception as e:
            self.logger.error(f"Error handling portfolio update: {e}")

    def _handle_account_update(self, event):
        """Handle account update events."""
        try:
            account_data = event.get("data", {})
            self.logger.debug(f"Account update received: {account_data}")
            # Update account display
            if hasattr(self, "account_widget"):
                self.account_widget.update_account(account_data)
        except Exception as e:
            self.logger.error(f"Error handling account update: {e}")

    def _handle_trade_update(self, event):
        """Handle trade execution events."""
        try:
            trade_data = event.get("data", {})
            self.logger.debug(f"Trade update received: {trade_data}")
            # Update trade display
            if hasattr(self, "trade_widget"):
                self.trade_widget.add_trade(trade_data)
        except Exception as e:
            self.logger.error(f"Error handling trade update: {e}")

    def _handle_market_data(self, event):
        """Handle market data events."""
        try:
            market_data = event.get("data", {})
            symbol = market_data.get("symbol", "")
            price = market_data.get("last", 0)

            self.logger.debug(f"Market data received: {symbol} - {price}")

            # Update price displays
            if hasattr(self, "price_widget"):
                self.price_widget.update_price(symbol, price)

        except Exception as e:
            self.logger.error(f"Error handling market data: {e}")
