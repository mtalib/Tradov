#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderG01_MainWindow.py
Group: G (User Interface)
Purpose: Main application window

Description:
    This module provides the main PyQt5 application window for the Spyder
    trading system. It serves as the central hub for all GUI components,
    managing the menu system, toolbar, status bar, and docking areas for
    various trading widgets. The window provides a professional trading
    interface with real-time updates and responsive design.

Author: Mohamed Talib
Date: 2025-06-08
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Any

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QMenuBar,
    QMenu,
    QAction,
    QToolBar,
    QStatusBar,
    QDockWidget,
    QTabWidget,
    QSplitter,
    QMessageBox,
    QProgressBar,
    QLabel,
    QDesktopWidget,
    QStyleFactory,
    QMdiArea,
    QMdiSubWindow,
)
from PyQt5.QtCore import (
    Qt,
    QTimer,
    QSettings,
    QSize,
    QPoint,
    pyqtSignal,
    pyqtSlot,
    QThread,
    QPropertyAnimation,
    QRect,
)
from PyQt5.QtGui import QIcon, QKeySequence, QCloseEvent, QPalette, QColor, QFont

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderA_Core.SpyderA02_TradingEngine import TradingEngine
from SpyderA_Core.SpyderA03_Configuration import get_config_manager
from SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType, Event
from SpyderB_Broker.SpyderB01_IBClient import IBClient
from SpyderB_Broker.SpyderB05_ConnectionManager import ConnectionManager
from SpyderG_GUI.SpyderG02_Dashboard import TradingDashboard
from SpyderG_GUI.SpyderG04_OptionChainWidget import OptionChainWidget
from SpyderG_GUI.SpyderG05_ChartWidget import ChartWidget
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Window settings
WINDOW_TITLE = "SPYDER - Automated SPY Options Trading System"
DEFAULT_WIDTH = 1600
DEFAULT_HEIGHT = 900
MIN_WIDTH = 1200
MIN_HEIGHT = 700


# ==============================================================================
# MAIN WINDOW CLASS
# ==============================================================================
class SpyderMainWindow(QMainWindow):
    """Main application window for Spyder trading system."""

    def __init__(
        self, trading_engine=None, event_manager=None, config=None, parent=None
    ):
        super().__init__(parent)

        # Store references
        self.trading_engine = trading_engine
        self.event_manager = event_manager
        self.config = config

        # Initialize logger
        self.logger = SpyderLogger.get_logger(__name__)

        # Initialize components
        self.trading_engine = None
        self.ib_client = None
        self.connection_manager = None

        # GUI components
        self.dashboard = None
        self.option_chain_widget = None
        self.chart_widget = None

        # State
        self.is_connected = False
        self.current_mode = None

        # Initialize UI
        self.init_ui()

        # Setup components
        self._setup_components()

        # Register event handlers
        self._register_event_handlers()

        # Load settings
        self._load_settings()

        self.logger.info("Main window initialized")

    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle(WINDOW_TITLE)
        self.setGeometry(100, 100, DEFAULT_WIDTH, DEFAULT_HEIGHT)
        self.setMinimumSize(MIN_WIDTH, MIN_HEIGHT)

        # Set application style
        self.setStyle(QStyleFactory.create("Fusion"))
        self._set_dark_theme()

        # Create central widget with dashboard
        self.dashboard = TradingDashboard(self.event_manager)
        self.setCentralWidget(self.dashboard)

        # Create dockable widgets
        self._create_dock_widgets()

        # Create menus and toolbars
        self._create_menu_bar()
        self._create_tool_bar()
        self._create_status_bar()

        # Connect dashboard signals
        self.dashboard.mode_changed.connect(self._on_mode_changed)

    def _set_dark_theme(self):
        """Apply dark theme to application"""
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.WindowText, Qt.white)
        dark_palette.setColor(QPalette.Base, QColor(25, 25, 25))
        dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
        dark_palette.setColor(QPalette.ToolTipText, Qt.white)
        dark_palette.setColor(QPalette.Text, Qt.white)
        dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ButtonText, Qt.white)
        dark_palette.setColor(QPalette.BrightText, Qt.red)
        dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.HighlightedText, Qt.black)

        self.setPalette(dark_palette)

    def _create_dock_widgets(self):
        """Create dockable widgets"""
        # Option Chain Dock
        self.option_chain_dock = QDockWidget("Option Chain", self)
        self.option_chain_widget = OptionChainWidget(self.event_manager)
        self.option_chain_dock.setWidget(self.option_chain_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.option_chain_dock)

        # Chart Dock
        self.chart_dock = QDockWidget("Price Chart", self)
        self.chart_widget = ChartWidget(self.event_manager)
        self.chart_dock.setWidget(self.chart_widget)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.chart_dock)

        # Connect option chain signals
        self.option_chain_widget.strike_selected.connect(self._on_strike_selected)
        self.option_chain_widget.trade_requested.connect(self._on_trade_requested)

    def _create_menu_bar(self):
        """Create the menu bar"""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        connect_action = QAction("&Connect to IB", self)
        connect_action.setShortcut("Ctrl+K")
        connect_action.setStatusTip("Connect to Interactive Brokers")
        connect_action.triggered.connect(self._connect_to_ib)
        file_menu.addAction(connect_action)

        disconnect_action = QAction("&Disconnect", self)
        disconnect_action.setStatusTip("Disconnect from Interactive Brokers")
        disconnect_action.triggered.connect(self._disconnect_from_ib)
        file_menu.addAction(disconnect_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.setStatusTip("Exit application")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Trading menu
        trading_menu = menubar.addMenu("&Trading")

        mode_action = QAction("Change &Mode", self)
        mode_action.setShortcut("Ctrl+M")
        mode_action.setStatusTip("Change trading mode")
        mode_action.triggered.connect(self.dashboard.select_trading_mode)
        trading_menu.addAction(mode_action)

        trading_menu.addSeparator()

        start_action = QAction("&Start Trading", self)
        start_action.setShortcut("F5")
        start_action.setStatusTip("Start automated trading")
        start_action.triggered.connect(self.dashboard.start_trading)
        trading_menu.addAction(start_action)

        stop_action = QAction("S&top Trading", self)
        stop_action.setShortcut("F6")
        stop_action.setStatusTip("Stop automated trading")
        stop_action.triggered.connect(self.dashboard.stop_trading)
        trading_menu.addAction(stop_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        view_menu.addAction(self.option_chain_dock.toggleViewAction())
        view_menu.addAction(self.chart_dock.toggleViewAction())

        view_menu.addSeparator()

        fullscreen_action = QAction("&Fullscreen", self)
        fullscreen_action.setShortcut("F11")
        fullscreen_action.setCheckable(True)
        fullscreen_action.triggered.connect(self._toggle_fullscreen)
        view_menu.addAction(fullscreen_action)

        # Tools menu
        tools_menu = menubar.addMenu("&Tools")

        backtest_action = QAction("&Backtesting", self)
        backtest_action.setStatusTip("Open backtesting interface")
        backtest_action.triggered.connect(self._open_backtest)
        tools_menu.addAction(backtest_action)

        reports_action = QAction("&Reports", self)
        reports_action.setStatusTip("Generate performance reports")
        reports_action.triggered.connect(self._open_reports)
        tools_menu.addAction(reports_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.setStatusTip("About Spyder")
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _create_tool_bar(self):
        """Create the main toolbar"""
        toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)

        # Connection status
        self.connection_label = QLabel("Disconnected")
        self.connection_label.setStyleSheet(
            """
            QLabel {
                color: red;
                font-weight: bold;
                padding: 5px;
            }
        """
        )
        toolbar.addWidget(self.connection_label)

        toolbar.addSeparator()

        # Quick actions
        connect_btn = toolbar.addAction("Connect")
        connect_btn.triggered.connect(self._connect_to_ib)

        start_btn = toolbar.addAction("Start")
        start_btn.triggered.connect(self.dashboard.start_trading)

        stop_btn = toolbar.addAction("Stop")
        stop_btn.triggered.connect(self.dashboard.stop_trading)

        toolbar.addSeparator()

        # Mode indicator
        self.mode_label = QLabel("Mode: Not Selected")
        self.mode_label.setStyleSheet(
            """
            QLabel {
                font-weight: bold;
                padding: 5px;
            }
        """
        )
        toolbar.addWidget(self.mode_label)

    def _create_status_bar(self):
        """Create status bar"""
        self.status_bar = self.statusBar()

        # Market status
        self.market_status_label = QLabel("Market: Unknown")
        self.status_bar.addPermanentWidget(self.market_status_label)

        # Time
        self.time_label = QLabel()
        self.status_bar.addPermanentWidget(self.time_label)

        # Update timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_status_bar)
        self.status_timer.start(1000)

    def _setup_components(self):
        """Setup backend components"""
        try:
            # Get config manager
            if not self.config:
                from SpyderA_Core.SpyderA03_Configuration import get_config_manager

                self.config = get_config_manager()

            # Initialize IB client with proper parameters
            self.ib_client = IBClient(
                host=self.config.get("ib.host", "127.0.0.1"),
                port=self.config.get("ib.port", 7497),
                client_id=self.config.get("ib.client_id", 1),
            )

            # Initialize connection manager
            self.connection_manager = ConnectionManager(
                self.ib_client, self.event_manager
            )

            # Initialize trading engine with proper parameters
            if not self.trading_engine:
                self.trading_engine = TradingEngine(
                    ib_client=self.ib_client,
                    event_manager=self.event_manager,
                    config=self.config,
                )

            self.logger.info("Backend components initialized")

        except Exception as e:
            self.logger.error(f"Failed to setup components: {e}")
            QMessageBox.critical(
                self,
                "Initialization Error",
                f"Failed to initialize components: {str(e)}",
            )

    def _register_event_handlers(self):
        """Register event handlers"""
        try:
            if not self.event_manager:
                self.logger.warning("Event manager not available")
                return

            # Connection events - use string event types, not EventType attributes
            self.event_manager.subscribe("CONNECTION", self._handle_connection_event)

            # System events
            self.event_manager.subscribe("SYSTEM", self._handle_system_event)

            # Market data events
            self.event_manager.subscribe("MARKET_DATA", self._handle_market_data)

            self.logger.debug("Event handlers registered successfully")

        except Exception as e:
            self.logger.error(f"Failed to register event handlers: {e}")

    # ==========================================================================
    # SLOTS AND HANDLERS
    # ==========================================================================
    @pyqtSlot(str)
    def _on_mode_changed(self, mode: str):
        """Handle trading mode change"""
        self.current_mode = mode
        self.mode_label.setText(f"Mode: {mode}")

        # Update trading engine configuration
        if self.trading_engine:
            self.trading_engine.set_mode(mode)

        self.logger.info(f"Trading mode changed to: {mode}")

    @pyqtSlot(float, str, object)
    def _on_strike_selected(self, strike: float, option_type: str, expiration):
        """Handle strike selection from option chain"""
        self.logger.info(f"Strike selected: {strike} {option_type} {expiration}")

    @pyqtSlot(dict)
    def _on_trade_requested(self, trade_params: dict):
        """Handle trade request from option chain"""
        if not self.is_connected:
            QMessageBox.warning(
                self, "Not Connected", "Please connect to Interactive Brokers first"
            )
            return

        # Send trade to trading engine
        if self.trading_engine:
            self.trading_engine.execute_trade(trade_params)

    def _handle_connection_event(self, event: Event):
        """Handle connection events"""
        status = event.data.get("status")
        message = event.data.get("message", "")

        if status == "connected":
            self.is_connected = True
            self.connection_label.setText("Connected")
            self.connection_label.setStyleSheet(
                """
                QLabel {
                    color: green;
                    font-weight: bold;
                    padding: 5px;
                }
            """
            )
            self.status_bar.showMessage("Connected to Interactive Brokers", 5000)

        elif status == "disconnected":
            self.is_connected = False
            self.connection_label.setText("Disconnected")
            self.connection_label.setStyleSheet(
                """
                QLabel {
                    color: red;
                    font-weight: bold;
                    padding: 5px;
                }
            """
            )
            self.status_bar.showMessage("Disconnected from Interactive Brokers", 5000)

    def _handle_system_event(self, event: Event):
        """Handle system events"""
        event_type = event.data.get("type")

        if event_type == "trading_started":
            self.status_bar.showMessage("Trading started", 3000)
        elif event_type == "trading_stopped":
            self.status_bar.showMessage("Trading stopped", 3000)
        elif event_type == "error":
            error_msg = event.data.get("message", "Unknown error")
            QMessageBox.warning(self, "System Error", error_msg)

    def _handle_market_data(self, event: Event):
        """Handle market data updates"""
        # Update chart if it's SPY data
        if event.data.get("symbol") == "SPY" and hasattr(
            self.chart_widget, "update_current_price"
        ):
            price = event.data.get("last", 0)
            self.chart_widget.update_current_price(price)

    # ==========================================================================
    # ACTIONS
    # ==========================================================================
    def _connect_to_ib(self):
        """Connect to Interactive Brokers"""
        if self.is_connected:
            QMessageBox.information(
                self, "Already Connected", "Already connected to Interactive Brokers"
            )
            return

        if self.connection_manager:
            # Show connecting message
            self.status_bar.showMessage("Connecting to Interactive Brokers...")

            # Attempt connection
            if self.connection_manager.connect():
                self.logger.info("Successfully connected to IB")
            else:
                QMessageBox.critical(
                    self,
                    "Connection Failed",
                    "Failed to connect to Interactive Brokers.\n"
                    "Please ensure TWS/Gateway is running.",
                )

    def _disconnect_from_ib(self):
        """Disconnect from Interactive Brokers"""
        if not self.is_connected:
            return

        if self.connection_manager:
            self.connection_manager.disconnect()
            self.logger.info("Disconnected from IB")

    def _toggle_fullscreen(self, checked: bool):
        """Toggle fullscreen mode"""
        if checked:
            self.showFullScreen()
        else:
            self.showNormal()

    def _open_backtest(self):
        """Open backtesting interface"""
        QMessageBox.information(
            self, "Backtesting", "Backtesting interface will be implemented here"
        )

    def _open_reports(self):
        """Open reports interface"""
        QMessageBox.information(
            self, "Reports", "Reports interface will be implemented here"
        )

    def _show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            "About Spyder",
            "<h2>SPYDER Trading System</h2>"
            "<p>Automated SPY Options Trading System</p>"
            "<p>Version: 1.0.0</p>"
            "<p>Author: Mohamed Talib</p>"
            "<p>© 2025 - For Private Use Only</p>",
        )

    def _update_status_bar(self):
        """Update status bar information"""
        # Update time
        current_time = datetime.now().strftime("%H:%M:%S")
        self.time_label.setText(current_time)

        # Update market status
        now = datetime.now()
        if now.weekday() < 5:  # Monday to Friday
            market_open = now.replace(hour=9, minute=30, second=0)
            market_close = now.replace(hour=16, minute=0, second=0)

            if market_open <= now <= market_close:
                self.market_status_label.setText("Market: OPEN")
                self.market_status_label.setStyleSheet("color: green;")
            else:
                self.market_status_label.setText("Market: CLOSED")
                self.market_status_label.setStyleSheet("color: red;")
        else:
            self.market_status_label.setText("Market: WEEKEND")
            self.market_status_label.setStyleSheet("color: orange;")

    # ==========================================================================
    # SETTINGS
    # ==========================================================================
    def _load_settings(self):
        """Load application settings"""
        settings = QSettings("Spyder", "TradingSystem")

        # Window geometry
        geometry = settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

        # Window state
        state = settings.value("windowState")
        if state:
            self.restoreState(state)

    def _save_settings(self):
        """Save application settings"""
        settings = QSettings("Spyder", "TradingSystem")

        # Save geometry and state
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())

    # ==========================================================================
    # LIFECYCLE
    # ==========================================================================
    def closeEvent(self, event: QCloseEvent):
        """Handle window close event"""
        # Check if trading is active
        if hasattr(self.dashboard, "is_trading") and self.dashboard.is_trading:
            reply = QMessageBox.question(
                self,
                "Exit Confirmation",
                "Trading is active. Are you sure you want to exit?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )

            if reply != QMessageBox.Yes:
                event.ignore()
                return

        # Stop components
        if self.trading_engine:
            self.trading_engine.stop()

        if self.connection_manager and self.is_connected:
            self.connection_manager.disconnect()

        # Save settings
        self._save_settings()

        # Accept close
        event.accept()

        self.logger.info("Application closed")


# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================
def main():
    """Main entry point for the application"""
    app = QApplication(sys.argv)
    app.setApplicationName("Spyder")
    app.setApplicationDisplayName("Spyder Trading System")

    # Create and show main window
    window = SpyderMainWindow()
    window.show()

    # Run application
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
