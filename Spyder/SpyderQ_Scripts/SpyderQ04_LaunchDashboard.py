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
import logging
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
                font-weight: normal;
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
                font-weight: normal;
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
                font-weight: normal;
            }
        """)

        self.init_ui()
        self.setup_tradier_connection()
        self.setup_timers()

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
        self.connection_status = QLabel("🟡 Tradier API (sandbox mode)")
        self.connection_status.setStyleSheet("color: #fbd38d; font-size: 14px;")

        self.connect_btn = QPushButton("🔌 Test Tradier Connection")
        self.connect_btn.clicked.connect(self.test_tradier_connection)

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
        self.last_price.setStyleSheet("font-size: 16px; font-weight: normal; color: #4fd1c7;")

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

    def setup_tradier_connection(self):
        """Set up broker connection state (Tradier REST API)"""
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

    def test_tradier_connection(self):
        """Test connectivity to the Tradier API."""
        import requests
        self.status_bar.setVisible(True)
        self.connect_btn.setEnabled(False)
        self.connection_status.setText("🔄 Testing Tradier connection...")
        self.connection_status.setStyleSheet("color: #fbd38d; font-size: 14px;")
        self.log_area.append("🔄 Testing Tradier API connectivity...")

        try:
            env = os.environ.get("TRADIER_ENVIRONMENT", "sandbox").lower()
            base_url = (
                "https://api.tradier.com/v1"
                if env == "production"
                else "https://sandbox.tradier.com/v1"
            )
            api_key = os.environ.get("TRADIER_API_KEY", "")
            headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
            resp = requests.get(f"{base_url}/user/profile", headers=headers, timeout=10)

            if resp.status_code == 200:
                self.is_connected = True
                self.connection_status.setText("✅ Tradier API connected")
                self.connection_status.setStyleSheet("color: #68d391; font-size: 14px;")
                self.log_area.append("✅ Tradier API reachable")
                self.disconnect_btn.setEnabled(True)
                self.connect_btn.setEnabled(False)
            else:
                self.connection_status.setText(f"❌ Tradier error {resp.status_code}")
                self.connection_status.setStyleSheet("color: #fc8181; font-size: 14px;")
                self.log_area.append(f"❌ Tradier API returned HTTP {resp.status_code}")
                self.connect_btn.setEnabled(True)
        except Exception as exc:
            self.connection_status.setText(f"❌ Connection error: {exc}")
            self.connection_status.setStyleSheet("color: #fc8181; font-size: 14px;")
            self.log_area.append(f"❌ Tradier connection failed: {exc}")
            self.connect_btn.setEnabled(True)

        self.status_bar.setVisible(False)

    def disconnect_from_gateway(self):
        """Reset Tradier connection state."""
        self.is_connected = False
        self.connection_status.setText("🔌 Disconnected")
        self.connection_status.setStyleSheet("color: #fbd38d; font-size: 14px;")
        self.disconnect_btn.setEnabled(False)
        self.connect_btn.setEnabled(True)
        self.log_area.append("🔌 Tradier connection reset")

    def update_portfolio(self):
        """Update portfolio display (Tradier positions)."""
        import requests
        try:
            env = os.environ.get("TRADIER_ENVIRONMENT", "sandbox").lower()
            base_url = (
                "https://api.tradier.com/v1"
                if env == "production"
                else "https://sandbox.tradier.com/v1"
            )
            account_id = os.environ.get("TRADIER_ACCOUNT_ID", "")
            api_key = os.environ.get("TRADIER_API_KEY", "")
            headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
            resp = requests.get(
                f"{base_url}/accounts/{account_id}/positions",
                headers=headers, timeout=10
            )
            if resp.status_code != 200:
                return
            positions = resp.json().get("positions", {}).get("position", []) or []
            if isinstance(positions, dict):
                positions = [positions]
            self.portfolio_table.setRowCount(len(positions))
            for row, pos in enumerate(positions):
                self.portfolio_table.setItem(row, 0, QTableWidgetItem(pos.get("symbol", "")))
                self.portfolio_table.setItem(row, 1, QTableWidgetItem(str(pos.get("quantity", ""))))
                self.portfolio_table.setItem(row, 2, QTableWidgetItem(str(pos.get("cost_basis", ""))))
                self.portfolio_table.setItem(row, 3, QTableWidgetItem("-"))
                self.portfolio_table.setItem(row, 4, QTableWidgetItem("-"))
        except Exception as exc:
            self.log_area.append(f"❌ Portfolio update error: {exc}")

    def update_market_data(self):
        """Update market data display via Tradier quotes."""
        if not self.is_connected:
            return
        import requests
        try:
            env = os.environ.get("TRADIER_ENVIRONMENT", "sandbox").lower()
            base_url = (
                "https://api.tradier.com/v1"
                if env == "production"
                else "https://sandbox.tradier.com/v1"
            )
            api_key = os.environ.get("TRADIER_API_KEY", "")
            headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
            resp = requests.get(
                f"{base_url}/markets/quotes",
                params={"symbols": "SPY"},
                headers=headers, timeout=5
            )
            if resp.status_code == 200:
                quote = resp.json().get("quotes", {}).get("quote", {})
                self.last_price.setText(f"Last: {quote.get('last', '---')}")
                self.bid_price.setText(f"Bid: {quote.get('bid', '---')}")
                self.ask_price.setText(f"Ask: {quote.get('ask', '---')}")
        except Exception as e:
            logging.getLogger(__name__).debug("Failed to fetch quote: %s", e)

    def place_order(self, action):
        """Place an order (sends to Tradier — not yet wired to SpyderB40)."""
        symbol = self.symbol_input.text().strip().upper() if hasattr(self.symbol_input, 'text') else "SPY"
        timestamp = datetime.now().strftime('%H:%M:%S')
        order_text = f"[{timestamp}] {action} {symbol} (route to SpyderB40_TradierClient)"
        self.order_history.append(order_text)
        self.log_area.append(f"📊 {action} order queued for {symbol} — connect to SpyderB40 to execute")

    def update_status(self):
        """Update status displays"""
        system_info = f"""System Status:
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Modules:
- PySide6: {'\u2705 Available' if HAS_QT else '\u274c Not Available'}

Broker:
- Tradier API: {'\u2705 Connected' if self.is_connected else '\u274c Not Connected'}

Market Data:
- Databento: configured via DATABENTO_API_KEY env var
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
