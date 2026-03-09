#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderQ_Scripts
Module: launch_dashboard_with_proactive_connections.py
Purpose: SPYDER - Trading Dashboard with Proactive Connection Manager

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    SPYDER - Trading Dashboard with Proactive Connection Manager

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# GUI imports
try:
    from PySide6.QtWidgets import (
        QApplication,
        QMainWindow,
        QWidget,
        QVBoxLayout,
        QHBoxLayout,
        QPushButton,
        QLabel,
        QProgressBar,
        QTextEdit,
        QGroupBox,  # noqa: F401
        QGridLayout,
        QFrame,  # noqa: F401
        QScrollArea,  # noqa: F401
        QTabWidget,  # noqa: F401
        QMessageBox,
        QSplitter,
        QStatusBar,
    )
    from PySide6.QtCore import Qt, QTimer, QThread, Signal  # noqa: F401
    from PySide6.QtGui import QFont, QIcon, QPixmap, QPalette, QColor  # noqa: F401

    GUI_AVAILABLE = True
except ImportError as e:
    print(f"❌ GUI imports failed: {e}")
    GUI_AVAILABLE = False
    sys.exit(1)

# SPYDER imports
try:
    from SpyderB08_ProactiveConnectionManager import ProactiveConnectionManager
    from config.config import get_active_config  # noqa: F401

    CONNECTION_MANAGER_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Connection manager import failed: {e}")
    CONNECTION_MANAGER_AVAILABLE = False


class ConnectionStatusWidget(QWidget):
    """Widget to display connection status in dashboard"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("🔌 Connection Manager")
        title.setFont(QFont("Arial", 12, QFont.Bold))
        title.setStyleSheet("color: #4fd1c7; margin-bottom: 10px;")
        layout.addWidget(title)

        # Status display
        self.status_label = QLabel("Status: Not Connected")
        self.status_label.setStyleSheet("color: #fbd38d; font-size: 11px;")
        layout.addWidget(self.status_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(8)  # 8 clients
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #4a5568;
                border-radius: 5px;
                text-align: center;
                background-color: #2d3748;
            }
            QProgressBar::chunk {
                background-color: #38a169;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # Button layout
        button_layout = QHBoxLayout()

        # Connect button
        self.connect_btn = QPushButton("🚀 Connect")
        self.connect_btn.setStyleSheet(self.get_button_style("#38a169"))
        button_layout.addWidget(self.connect_btn)

        # Reconnect button
        self.reconnect_btn = QPushButton("🔄 Retry")
        self.reconnect_btn.setStyleSheet(self.get_button_style("#d69e2e"))
        button_layout.addWidget(self.reconnect_btn)

        # Status button
        self.status_btn = QPushButton("📊 Status")
        self.status_btn.setStyleSheet(self.get_button_style("#3182ce"))
        button_layout.addWidget(self.status_btn)

        layout.addLayout(button_layout)

        # Client status grid
        self.client_grid = QGridLayout()
        self.client_labels = {}

        # Create client status indicators
        for i in range(8):
            client_id = 100 + i
            label = QLabel(f"C{client_id}: ❌")
            label.setStyleSheet("font-size: 9px; color: #a0aec0;")
            self.client_labels[client_id] = label

            row = i // 4
            col = i % 4
            self.client_grid.addWidget(label, row, col)

        layout.addLayout(self.client_grid)

    def get_button_style(self, color="#4a5568"):
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 5px;
                padding: 5px 10px;
                font-weight: bold;
                font-size: 10px;
            }}
            QPushButton:hover {{
                background-color: {color}dd;
            }}
            QPushButton:pressed {{
                background-color: {color}aa;
            }}
            QPushButton:disabled {{
                background-color: #4a5568;
                color: #a0aec0;
            }}
        """

    def update_client_status(self, client_id, state):
        """Update individual client status"""
        if client_id in self.client_labels:
            status_icons = {
                "connected": "✅",
                "connecting": "🔄",
                "disconnected": "❌",
                "failed": "💥",
                "reconnecting": "🔁",
            }

            icon = status_icons.get(state, "❓")
            self.client_labels[client_id].setText(f"C{client_id}: {icon}")

    def update_progress(self, current, total=8):
        """Update progress bar"""
        self.progress_bar.setValue(current)
        self.progress_bar.setMaximum(total)

    def update_status(self, message):
        """Update status label"""
        self.status_label.setText(f"Status: {message}")


class MarketDataWidget(QWidget):
    """Widget to display market data (placeholder)"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("📈 Market Data")
        title.setFont(QFont("Arial", 12, QFont.Bold))
        title.setStyleSheet("color: #4fd1c7; margin-bottom: 10px;")
        layout.addWidget(title)

        # Data display (placeholder)
        self.data_display = QTextEdit()
        self.data_display.setStyleSheet("""
            QTextEdit {
                background-color: #1a202c;
                color: #e2e8f0;
                border: 1px solid #4a5568;
                border-radius: 5px;
                font-family: 'Courier New';
                font-size: 10px;
            }
        """)

        # Add sample data
        sample_data = """
SPY: $432.50 ↑ +0.85 (+0.20%)
QQQ: $368.25 ↓ -0.45 (-0.12%)
VIX: 18.45 ↑ +0.22 (+1.21%)

Market Status: OPEN
Last Update: --:--:--
Data Source: Waiting for connection...
        """

        self.data_display.setText(sample_data.strip())
        layout.addWidget(self.data_display)

    def update_data(self, symbol, price, change):
        """Update market data (placeholder method)"""
        pass


class TradingControlsWidget(QWidget):
    """Widget for trading controls (placeholder)"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("🎯 Trading Controls")
        title.setFont(QFont("Arial", 12, QFont.Bold))
        title.setStyleSheet("color: #4fd1c7; margin-bottom: 10px;")
        layout.addWidget(title)

        # Controls (placeholder)
        self.controls_label = QLabel(
            "Trading controls will be enabled once connections are established."
        )
        self.controls_label.setStyleSheet("color: #a0aec0; font-style: italic;")
        layout.addWidget(self.controls_label)

        # Placeholder buttons
        button_layout = QHBoxLayout()

        self.strategy_btn = QPushButton("📊 Strategies")
        self.strategy_btn.setEnabled(False)
        button_layout.addWidget(self.strategy_btn)

        self.orders_btn = QPushButton("📋 Orders")
        self.orders_btn.setEnabled(False)
        button_layout.addWidget(self.orders_btn)

        self.positions_btn = QPushButton("💼 Positions")
        self.positions_btn.setEnabled(False)
        button_layout.addWidget(self.positions_btn)

        layout.addLayout(button_layout)

    def enable_controls(self, enabled=True):
        """Enable/disable trading controls"""
        self.strategy_btn.setEnabled(enabled)
        self.orders_btn.setEnabled(enabled)
        self.positions_btn.setEnabled(enabled)

        if enabled:
            self.controls_label.setText("Trading controls are now active!")
            self.controls_label.setStyleSheet("color: #68d391;")
        else:
            self.controls_label.setText(
                "Trading controls will be enabled once connections are established."
            )
            self.controls_label.setStyleSheet("color: #a0aec0; font-style: italic;")


class SPYDERTradingDashboard(QMainWindow):
    """Main SPYDER Trading Dashboard with Proactive Connection Management"""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("🕷️ SPYDER Trading Dashboard - Universal 8-Client System")
        self.setGeometry(100, 100, 1200, 800)

        # Initialize connection manager
        self.connection_manager = None
        if CONNECTION_MANAGER_AVAILABLE:
            self.connection_manager = ProactiveConnectionManager()

        self.setup_ui()
        self.setup_connections()
        self.apply_dark_theme()

        # Auto-trigger connections on startup
        if self.connection_manager:
            QTimer.singleShot(1000, self.auto_connect)  # Connect after 1 second

    def setup_ui(self):
        """Setup the user interface"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QHBoxLayout(central_widget)

        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # Left panel - Connection and status
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        # Connection status widget
        self.connection_widget = ConnectionStatusWidget()
        left_layout.addWidget(self.connection_widget)

        # Trading controls
        self.trading_widget = TradingControlsWidget()
        left_layout.addWidget(self.trading_widget)

        # Add stretch to push everything to top
        left_layout.addStretch()

        # Right panel - Market data
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Market data widget
        self.market_data_widget = MarketDataWidget()
        right_layout.addWidget(self.market_data_widget)

        # Add panels to splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)

        # Set initial splitter sizes (30% left, 70% right)
        splitter.setSizes([360, 840])

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("🕷️ SPYDER Dashboard Ready - Click Connect to start")

    def setup_connections(self):
        """Setup signal connections"""
        if not self.connection_manager:
            return

        # Connect button signals
        self.connection_widget.connect_btn.clicked.connect(self.trigger_connections)
        self.connection_widget.reconnect_btn.clicked.connect(
            self.retry_failed_connections
        )
        self.connection_widget.status_btn.clicked.connect(self.show_detailed_status)

        # Connect manager signals
        if hasattr(self.connection_manager, "connection_state_changed"):
            self.connection_manager.connection_state_changed.connect(
                self.on_connection_state_changed
            )

        if hasattr(self.connection_manager, "connection_progress"):
            self.connection_manager.connection_progress.connect(
                self.on_connection_progress
            )

        if hasattr(self.connection_manager, "all_connected"):
            self.connection_manager.all_connected.connect(self.on_all_connected)

        if hasattr(self.connection_manager, "error_occurred"):
            self.connection_manager.error_occurred.connect(self.on_error)

    def apply_dark_theme(self):
        """Apply dark theme to the dashboard"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a202c;
                color: #e2e8f0;
            }

            QWidget {
                background-color: #1a202c;
                color: #e2e8f0;
            }

            QGroupBox {
                background-color: #2d3748;
                border: 2px solid #4a5568;
                border-radius: 10px;
                padding-top: 15px;
                margin-top: 10px;
            }

            QGroupBox::title {
                subcontrol-origin: margin;
                left: 20px;
                padding: 0 5px 0 5px;
            }

            QLabel {
                color: #e2e8f0;
            }

            QStatusBar {
                background-color: #2d3748;
                color: #e2e8f0;
                border-top: 1px solid #4a5568;
            }
        """)

    def auto_connect(self):
        """Automatically trigger connections on startup"""
        if self.connection_manager:
            self.connection_widget.update_status("Auto-connecting...")
            self.trigger_connections()

    def trigger_connections(self):
        """Trigger connection establishment"""
        if not self.connection_manager:
            self.show_error("Connection manager not available")
            return

        self.connection_widget.connect_btn.setEnabled(False)
        self.connection_widget.connect_btn.setText("🔄 Connecting...")

        self.connection_widget.update_status("Establishing connections...")
        self.status_bar.showMessage("🔄 Connecting to IB Gateway...")

        # Use the connection manager's dashboard trigger method
        self.connection_manager.trigger_connections_from_dashboard()

    def retry_failed_connections(self):
        """Retry failed connections"""
        if not self.connection_manager:
            return

        self.connection_manager.trigger_reconnect_failed()
        self.connection_widget.update_status("Retrying failed connections...")

    def show_detailed_status(self):
        """Show detailed connection status"""
        if not self.connection_manager:
            return

        self.connection_manager.show_connection_status()

        # Also update the dashboard
        summary = self.connection_manager.get_connection_summary()

        status_text = f"""Connection Summary:

Total Clients: {summary["total_clients"]}
Connected: {summary["connected"]}
Failed: {summary["failed"]}
Critical Connected: {summary["critical_connected"]}/{summary["critical_total"]}

System Status: {"✅ OPERATIONAL" if summary["critical_connected"] == summary["critical_total"] else "⚠️ DEGRADED"}"""

        QMessageBox.information(self, "Connection Status", status_text)

    def on_connection_state_changed(self, client_id, state):
        """Handle connection state changes"""
        self.connection_widget.update_client_status(client_id, state)

        if state == "connected":
            self.status_bar.showMessage(f"✅ Client {client_id} connected")
        elif state == "failed":
            self.status_bar.showMessage(f"❌ Client {client_id} failed to connect")

    def on_connection_progress(self, current, total=8):
        """Handle connection progress updates"""
        self.connection_widget.update_progress(current, total)

        if current == total:
            self.connection_widget.update_status(f"All {total} clients connected!")
        else:
            self.connection_widget.update_status(f"Connecting... {current}/{total}")

    def on_all_connected(self):
        """Handle when all connections are established"""
        self.connection_widget.connect_btn.setText("✅ Connected")
        self.connection_widget.connect_btn.setEnabled(True)

        self.connection_widget.update_status("All 8 clients connected successfully!")
        self.status_bar.showMessage(
            "🎉 All connections established - Trading system active"
        )

        # Enable trading controls
        self.trading_widget.enable_controls(True)

        # Update market data display
        self.market_data_widget.data_display.append(
            "\n✅ Connection established - Live data feed starting..."
        )

    def on_error(self, error_message):
        """Handle connection errors"""
        self.show_error(f"Connection Error: {error_message}")

        self.connection_widget.connect_btn.setText("🚀 Connect")
        self.connection_widget.connect_btn.setEnabled(True)

        self.connection_widget.update_status("Connection failed - check IB Gateway")

    def show_error(self, message):
        """Show error message"""
        QMessageBox.critical(self, "SPYDER Error", message)

    def closeEvent(self, event):
        """Handle application close"""
        if self.connection_manager:
            self.connection_manager.shutdown()
        event.accept()


def main():
    """Main application entry point"""

    print("🕷️ SPYDER Trading Dashboard - Proactive Connection System")
    print("=" * 60)

    if not GUI_AVAILABLE:
        print("❌ GUI libraries not available")
        return 1

    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("SPYDER Trading Dashboard")
    app.setOrganizationName("SPYDER Trading")

    # Set application icon if available
    icon_path = Path(__file__).parent / "assets" / "spyder_icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Create and show main window
    dashboard = SPYDERTradingDashboard()
    dashboard.show()

    # Center window on screen
    screen = app.primaryScreen().geometry()
    size = dashboard.geometry()
    dashboard.move(
        (screen.width() - size.width()) // 2, (screen.height() - size.height()) // 2
    )

    print("✅ Dashboard launched successfully")
    print("💡 Click 'Connect' button to establish IB Gateway connections")

    # Run application
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
