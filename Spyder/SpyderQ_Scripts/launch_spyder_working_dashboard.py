#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderQ_Scripts
Module: launch_spyder_working_dashboard.py
Purpose: Working SPYDER Dashboard - Simplified but Functional

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    Working SPYDER Dashboard - Simplified but Functional

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import os
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Try to import required modules
try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
        QWidget, QLabel, QPushButton, QTextEdit, QGroupBox,
        QProgressBar, QTabWidget, QTableWidget, QTableWidgetItem
    )
    from PySide6.QtCore import Qt, QTimer, Signal, QThread, QObject  # noqa: F401
    from PySide6.QtGui import QFont
    HAS_QT = True
except ImportError as e:
    print(f"ERROR: PySide6 not available: {e}")
    HAS_QT = False

try:
    from ib_async import IB, Stock  # noqa: F401
    HAS_IB_ASYNC = True
except ImportError as e:
    print(f"WARNING: ib_async not available: {e}")
    HAS_IB_ASYNC = False


class WorkingSpyderDashboard(QMainWindow):
    """Working SPYDER Dashboard with basic trading functionality"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("🕷️ SPYDER Trading Dashboard - Working Mode")
        self.setGeometry(100, 100, 1200, 800)

        # Set up style
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a202c;
                color: #e2e8f0;
            }
            QWidget {
                background-color: #1a202c;
                color: #e2e8f0;
            }
            QLabel {
                color: #e2e8f0;
                font-family: Arial, sans-serif;
            }
            QPushButton {
                background-color: #4fd1c7;
                color: #1a202c;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #38b2ac;
            }
            QPushButton:pressed {
                background-color: #319795;
            }
            QPushButton:disabled {
                background-color: #4a5568;
                color: #a0aec0;
            }
            QGroupBox {
                border: 2px solid #4a5568;
                border-radius: 8px;
                margin-top: 1ex;
                padding-top: 10px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #4fd1c7;
            }
            QTextEdit {
                background-color: #2d3748;
                color: #e2e8f0;
                border: 1px solid #4a5568;
                border-radius: 4px;
                padding: 8px;
                font-family: monospace;
                selection-background-color: #4a5568;
            }
            QTableWidget {
                background-color: #2d3748;
                color: #e2e8f0;
                border: 1px solid #4a5568;
                border-radius: 4px;
                gridline-color: #4a5568;
                selection-background-color: #4a5568;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QProgressBar {
                border: 1px solid #4a5568;
                border-radius: 4px;
                text-align: center;
                background-color: #2d3748;
                color: #e2e8f0;
            }
            QProgressBar::chunk {
                background-color: #4fd1c7;
                border-radius: 3px;
            }
            QTabWidget::pane {
                border: 1px solid #4a5568;
                background-color: #1a202c;
                border-radius: 5px;
            }
            QTabBar::tab {
                background-color: #2d3748;
                color: #a0aec0;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
            }
            QTabBar::tab:selected {
                background-color: #4fd1c7;
                color: #1a202c;
                font-weight: bold;
            }
        """)

        self.init_ui()
        self.setup_ib_connection()
        self.setup_timers()

        # IB Gateway fixes removed - no longer needed

    def init_ui(self):
        """Initialize the user interface"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Header
        header_layout = QHBoxLayout()
        title_label = QLabel("🕷️ SPYDER Trading Dashboard")
        title_font = QFont("Arial", 20)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #4fd1c7;")

        subtitle_label = QLabel("Working Mode - Functional Trading Dashboard")
        subtitle_font = QFont("Arial", 12)
        subtitle_label.setFont(subtitle_font)
        subtitle_label.setStyleSheet("color: #a0aec0;")

        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(subtitle_label)

        main_layout.addLayout(header_layout)

        # Connection status bar
        self.status_bar = QProgressBar()
        self.status_bar.setRange(0, 0)  # Indeterminate progress
        self.status_bar.setVisible(False)
        self.status_bar.setFixedHeight(5)
        main_layout.addWidget(self.status_bar)

        # Connection status
        status_layout = QHBoxLayout()
        self.connection_status = QLabel("❌ Not connected to IB Gateway")
        self.connection_status.setStyleSheet("color: #fc8181; font-size: 14px;")

        self.connect_btn = QPushButton("🔌 Connect to IB Gateway")
        self.connect_btn.clicked.connect(self.connect_to_gateway)

        self.disconnect_btn = QPushButton("🔌 Disconnect")
        self.disconnect_btn.clicked.connect(self.disconnect_from_gateway)
        self.disconnect_btn.setEnabled(False)

        status_layout.addWidget(self.connection_status)
        status_layout.addStretch()
        status_layout.addWidget(self.connect_btn)
        status_layout.addWidget(self.disconnect_btn)

        main_layout.addLayout(status_layout)

        # Create tab widget
        self.tabs = QTabWidget()

        # Trading tab
        self.trading_tab = self.create_trading_tab()
        self.tabs.addTab(self.trading_tab, "💹 Trading")

        # Portfolio tab
        self.portfolio_tab = self.create_portfolio_tab()
        self.tabs.addTab(self.portfolio_tab, "📊 Portfolio")

        # Status tab
        self.status_tab = self.create_status_tab()
        self.tabs.addTab(self.status_tab, "🔧 Status")

        main_layout.addWidget(self.tabs)

    def create_trading_tab(self):
        """Create the trading tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Trading controls
        controls_group = QGroupBox("Trading Controls")
        controls_layout = QVBoxLayout(controls_group)

        # Symbol input
        symbol_layout = QHBoxLayout()
        symbol_label = QLabel("Symbol:")
        symbol_label.setMinimumWidth(50)
        self.symbol_input = QLabel("SPY")
        self.symbol_input.setStyleSheet("""
            QLabel {
                background-color: #2d3748;
                color: #e2e8f0;
                border: 1px solid #4a5568;
                border-radius: 4px;
                padding: 5px;
                font-family: monospace;
            }
        """)
        symbol_layout.addWidget(symbol_label)
        symbol_layout.addWidget(self.symbol_input)
        symbol_layout.addStretch()

        # Order buttons
        buy_btn = QPushButton("📈 Buy")
        buy_btn.setStyleSheet("background-color: #48bb78;")
        buy_btn.clicked.connect(lambda: self.place_order("BUY"))

        sell_btn = QPushButton("📉 Sell")
        sell_btn.setStyleSheet("background-color: #f56565;")
        sell_btn.clicked.connect(lambda: self.place_order("SELL"))

        symbol_layout.addWidget(buy_btn)
        symbol_layout.addWidget(sell_btn)

        controls_layout.addLayout(symbol_layout)

        # Market data display
        market_data_layout = QHBoxLayout()

        self.last_price = QLabel("Last: ---")
        self.last_price.setStyleSheet("font-size: 16px; font-weight: bold; color: #4fd1c7;")

        self.bid_price = QLabel("Bid: ---")
        self.bid_price.setStyleSheet("font-size: 14px; color: #68d391;")

        self.ask_price = QLabel("Ask: ---")
        self.ask_price.setStyleSheet("font-size: 14px; color: #fc8181;")

        market_data_layout.addWidget(self.last_price)
        market_data_layout.addWidget(self.bid_price)
        market_data_layout.addWidget(self.ask_price)
        market_data_layout.addStretch()

        controls_layout.addLayout(market_data_layout)

        layout.addWidget(controls_group)

        # Order history
        history_group = QGroupBox("Order History")
        history_layout = QVBoxLayout(history_group)

        self.order_history = QTextEdit()
        self.order_history.setReadOnly(True)
        self.order_history.setMaximumHeight(200)
        self.order_history.setPlainText("Order history will appear here...")

        history_layout.addWidget(self.order_history)
        layout.addWidget(history_group)

        return tab

    def create_portfolio_tab(self):
        """Create the portfolio tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Portfolio table
        self.portfolio_table = QTableWidget()
        self.portfolio_table.setColumnCount(5)
        self.portfolio_table.setHorizontalHeaderLabels([
            "Symbol", "Position", "Market Price", "Market Value", "PnL"
        ])

        layout.addWidget(self.portfolio_table)

        return tab

    def create_status_tab(self):
        """Create the status tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # System status
        system_group = QGroupBox("System Status")
        system_layout = QVBoxLayout(system_group)

        self.system_status = QTextEdit()
        self.system_status.setReadOnly(True)
        self.system_status.setPlainText("Gathering system status...")
        system_layout.addWidget(self.system_status)

        layout.addWidget(system_group)

        # Log area
        log_group = QGroupBox("Activity Log")
        log_layout = QVBoxLayout(log_group)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumHeight(200)
        self.log_area.setPlainText("Activity log will appear here...")
        log_layout.addWidget(self.log_area)

        layout.addWidget(log_group)

        return tab

    def setup_ib_connection(self):
        """Set up IB connection"""
        self.ib = None
        self.is_connected = False

    def setup_timers(self):
        """Set up update timers"""
        # Status update timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(5000)  # Update every 5 seconds

        # Market data update timer
        self.market_data_timer = QTimer()
        self.market_data_timer.timeout.connect(self.update_market_data)
        self.market_data_timer.start(1000)  # Update every second

    def apply_1039_fixes(self):
        """IB Gateway 10.39 fixes removed - no longer needed"""
        self.log_area.append("ℹ️ IB Gateway 10.39 fixes have been removed")

    def connect_to_gateway(self):
        """Connect to IB Gateway"""
        if not HAS_IB_ASYNC:
            self.connection_status.setText("❌ ib_async not available")
            self.log_area.append("❌ ib_async not available")
            return

        self.status_bar.setVisible(True)
        self.connect_btn.setEnabled(False)
        self.connection_status.setText("🔄 Connecting to IB Gateway...")
        self.connection_status.setStyleSheet("color: #fbd38d; font-size: 14px;")
        self.log_area.append("🔄 Connecting to IB Gateway...")

        try:
            # Create IB instance
            self.ib = IB()

            # Connect to Gateway
            self.ib.connect('127.0.0.1', 4002, clientId=999, timeout=30)

            if self.ib.isConnected():
                self.is_connected = True
                self.connection_status.setText("✅ Connected to IB Gateway")
                self.connection_status.setStyleSheet("color: #68d391; font-size: 14px;")
                self.connect_btn.setEnabled(False)
                self.disconnect_btn.setEnabled(True)
                self.log_area.append("✅ Connected to IB Gateway")

                # Get account info
                try:
                    accounts = self.ib.managedAccounts()
                    account_info = f"Accounts: {', '.join(accounts)}"
                    self.log_area.append(f"📋 {account_info}")

                    # Update portfolio
                    self.update_portfolio()
                except Exception as e:
                    self.log_area.append(f"❌ Error getting account info: {e}")
            else:
                self.is_connected = False
                self.connection_status.setText("❌ Failed to connect to IB Gateway")
                self.connection_status.setStyleSheet("color: #fc8181; font-size: 14px;")
                self.connect_btn.setEnabled(True)
                self.log_area.append("❌ Failed to connect to IB Gateway")

        except Exception as e:
            self.is_connected = False
            self.connection_status.setText(f"❌ Connection error: {e}")
            self.connection_status.setStyleSheet("color: #fc8181; font-size: 14px;")
            self.connect_btn.setEnabled(True)
            self.log_area.append(f"❌ Connection error: {e}")

        self.status_bar.setVisible(False)

    def disconnect_from_gateway(self):
        """Disconnect from IB Gateway"""
        if self.ib and self.ib.isConnected():
            try:
                self.ib.disconnect()
                self.is_connected = False
                self.connection_status.setText("🔌 Disconnected from IB Gateway")
                self.connection_status.setStyleSheet("color: #fbd38d; font-size: 14px;")
                self.disconnect_btn.setEnabled(False)
                self.connect_btn.setEnabled(True)
                self.log_area.append("🔌 Disconnected from IB Gateway")
            except Exception as e:
                self.connection_status.setText(f"❌ Disconnect error: {e}")
                self.log_area.append(f"❌ Disconnect error: {e}")

    def update_portfolio(self):
        """Update portfolio display"""
        if not self.ib or not self.ib.isConnected():
            return

        try:
            # Get portfolio
            portfolio = []
            for account in self.ib.managedAccounts():
                for item in self.ib.portfolio(account):
                    portfolio.append(item)

            # Update table
            self.portfolio_table.setRowCount(len(portfolio))

            for row, item in enumerate(portfolio):
                self.portfolio_table.setItem(row, 0, QTableWidgetItem(item.contract.symbol))
                self.portfolio_table.setItem(row, 1, QTableWidgetItem(str(item.position)))
                self.portfolio_table.setItem(row, 2, QTableWidgetItem(str(item.marketPrice)))
                self.portfolio_table.setItem(row, 3, QTableWidgetItem(str(item.marketValue)))
                self.portfolio_table.setItem(row, 4, QTableWidgetItem(str(item.unrealizedPNL)))

        except Exception as e:
            self.log_area.append(f"❌ Error updating portfolio: {e}")

    def update_market_data(self):
        """Update market data display"""
        if not self.is_connected:
            return

        # For now, just display placeholder data
        # In a real implementation, you would subscribe to market data
        import random

        last_price = 450 + random.uniform(-5, 5)
        bid_price = last_price - random.uniform(0.01, 0.05)
        ask_price = last_price + random.uniform(0.01, 0.05)

        self.last_price.setText(f"Last: {last_price:.2f}")
        self.bid_price.setText(f"Bid: {bid_price:.2f}")
        self.ask_price.setText(f"Ask: {ask_price:.2f}")

    def place_order(self, action):
        """Place an order (placeholder implementation)"""
        symbol = self.symbol_input.text().strip().upper()
        if not symbol:
            return

        timestamp = datetime.now().strftime('%H:%M:%S')
        order_text = f"[{timestamp}] {action} {symbol} (placeholder implementation)"
        self.order_history.append(order_text)
        self.log_area.append(f"📊 {action} order for {symbol} (placeholder)")

    def update_status(self):
        """Update status displays"""
        # Update system status
        system_info = f"""System Status:
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Modules:
- PySide6: {'✅ Available' if HAS_QT else '❌ Not Available'}
- ib_async: {'✅ Available' if HAS_IB_ASYNC else '❌ Not Available'}

Gateway:
- Process Running: {'✅ Yes' if os.system('pgrep -f ibgateway > /dev/null 2>&1') == 0 else '❌ No'}
- Port 4002: {'✅ Accessible' if os.system('timeout 2 bash -c "</dev/tcp/127.0.0.1/4002" > /dev/null 2>&1') == 0 else '❌ Not Accessible'}

IB Connection:
- Connected: {'✅ Yes' if self.is_connected else '❌ No'}
"""

        self.system_status.setPlainText(system_info)


def main():
    """Main entry point for working SPYDER launcher"""

    if not HAS_QT:
        print("ERROR: PySide6 not available. Cannot launch GUI.")
        return 1

    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("SPYDER Trading Dashboard - Working Mode")

    # Create and show dashboard
    dashboard = WorkingSpyderDashboard()
    dashboard.show()

    # Run application
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
