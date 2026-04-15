#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderQ_Scripts
Module: launch_spyder_dashboard_direct.py
Purpose: SPYDER - Direct Dashboard Launcher

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    SPYDER - Direct Dashboard Launcher

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import time
import logging
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
        QTextEdit,
        QProgressBar,
        QGroupBox,
        QGridLayout,
        QFrame,  # noqa: F401
        QMessageBox,  # noqa: F401
        QSplitter,
        QStatusBar,
        QTabWidget,  # noqa: F401
    )
    from PySide6.QtCore import Qt, QTimer, QThread, Signal  # noqa: F401
    from PySide6.QtGui import QFont, QIcon, QPalette, QColor, QPixmap  # noqa: F401

    GUI_AVAILABLE = True
except ImportError as e:
    print(f"❌ GUI imports failed: {e}")
    GUI_AVAILABLE = False
    sys.exit(1)

# Legacy broker integration removed - Spyder now uses Tradier API

# Logging configured by SpyderU01_Logger
logger = logging.getLogger(__name__)


class DirectConnectionWorker(QThread):
    """Worker thread for managing broker connections directly"""

    connection_established = Signal(int, str)  # client_id, description
    connection_failed = Signal(int, str)  # client_id, error
    all_connected = Signal()
    progress_updated = Signal(int, int)  # current, total

    def __init__(self, host="127.0.0.1", port=4002, parent=None):
        super().__init__(parent)
        self.host = host
        self.port = port
        self.connections = {}
        self.should_stop = False

        # Universal 8-Client configuration
        self.client_configs = {
            100: {
                "description": "Order Execution & Primary Trading",
                "symbols": ["SPY", "QQQ", "IWM"],
            },
            101: {
                "description": "Administrative & News Feeds",
                "symbols": ["SPY", "VIX", "TNX"],
            },
            102: {"description": "Core Market Data", "symbols": ["SPY", "SPX", "/ES"]},
            103: {"description": "SPY Options Chains", "symbols": ["SPY_OPTIONS"]},
            104: {
                "description": "Volatility & Market Internals",
                "symbols": ["VIX", "UVXY", "SVXY"],
            },
            105: {"description": "Major Indices", "symbols": ["DIA", "QQQ", "IWM"]},
            106: {
                "description": "Extended Assets & Sectors",
                "symbols": ["XLF", "XLK", "TLT"],
            },
            107: {
                "description": "International Markets",
                "symbols": ["EFA", "EEM", "FXI"],
            },
        }

    def run(self):
        """Run connection establishment in thread"""
        try:
            self.establish_connections()
        except Exception as e:
            logger.error("Connection worker error: %s", e)

    def establish_connections(self):
        """Establish all 8 client connections"""
        logger.info("Starting direct connection establishment...")

        connected_count = 0
        total_clients = len(self.client_configs)

        # IBKR connections removed — broker migrated to Tradier (SpyderB40_TradierClient).
        logger.warning(
            "establish_connections: IBKR multi-client connections are no longer supported. "
            "Use SpyderB40_TradierClient for broker connectivity."
        )
        return

        if connected_count == total_clients:
            self.all_connected.emit()
            logger.info("🎉 All clients connected successfully")
        else:
            logger.warning(
                "⚠️ Only %s/%s clients connected", connected_count, total_clients
            )

    def disconnect_all(self):
        """Disconnect all connections"""
        self.should_stop = True

        for client_id, ib in self.connections.items():
            try:
                ib.disconnect()
                logger.info("Disconnected client %s", client_id)
            except Exception as e:
                logger.error("Error disconnecting client %s: %s", client_id, e)

        self.connections.clear()


class ConnectionStatusWidget(QWidget):
    """Widget to display connection status"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("🔌 Direct Connection Manager")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        title.setStyleSheet("color: #4fd1c7; margin-bottom: 10px;")
        layout.addWidget(title)

        # Status label
        self.status_label = QLabel("Status: Ready to connect")
        self.status_label.setStyleSheet(
            "color: #fbd38d; font-size: 12px; margin-bottom: 10px;"
        )
        layout.addWidget(self.status_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(8)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #4a5568;
                border-radius: 5px;
                text-align: center;
                background-color: #2d3748;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #38a169;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # Control buttons
        button_layout = QHBoxLayout()

        self.connect_btn = QPushButton("🚀 Connect All Clients")
        self.connect_btn.setStyleSheet(self.get_button_style("#38a169"))
        button_layout.addWidget(self.connect_btn)

        self.disconnect_btn = QPushButton("🔌 Disconnect All")
        self.disconnect_btn.setStyleSheet(self.get_button_style("#e53e3e"))
        self.disconnect_btn.setEnabled(False)
        button_layout.addWidget(self.disconnect_btn)

        layout.addLayout(button_layout)

        # Client status grid
        clients_group = QGroupBox("Client Status")
        clients_group.setStyleSheet("QGroupBox { font-weight: normal; color: #4fd1c7; }")
        clients_layout = QGridLayout(clients_group)

        self.client_labels = {}
        for i, client_id in enumerate([100, 101, 102, 103, 104, 105, 106, 107]):
            label = QLabel(f"Client {client_id}: ❌ Disconnected")
            label.setStyleSheet("font-size: 10px; color: #a0aec0; padding: 2px;")
            self.client_labels[client_id] = label

            row = i // 2
            col = i % 2
            clients_layout.addWidget(label, row, col)

        layout.addWidget(clients_group)

    def get_button_style(self, color="#4a5568"):
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 15px;
                font-weight: normal;
                font-size: 11px;
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

    def update_client_status(self, client_id, status, description=""):
        """Update individual client status"""
        if client_id in self.client_labels:
            if status == "connected":
                icon = "✅"
                color = "#68d391"
            elif status == "failed":
                icon = "❌"
                color = "#fc8181"
            else:
                icon = "🔄"
                color = "#fbd38d"

            text = f"Client {client_id}: {icon} {status.title()}"
            if description:
                text += f" - {description[:30]}..."

            self.client_labels[client_id].setText(text)
            self.client_labels[client_id].setStyleSheet(
                f"font-size: 10px; color: {color}; padding: 2px;"
            )

    def update_progress(self, current, total):
        """Update progress bar"""
        self.progress_bar.setValue(current)
        self.status_label.setText(f"Status: Connected {current}/{total} clients")

    def set_all_connected(self):
        """Set status to all connected"""
        self.status_label.setText("Status: All clients connected successfully!")
        self.status_label.setStyleSheet(
            "color: #68d391; font-size: 12px; font-weight: normal;"
        )
        self.connect_btn.setEnabled(False)
        self.disconnect_btn.setEnabled(True)


class MarketDataWidget(QWidget):
    """Widget to display market data"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("📈 Market Data Feed")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        title.setStyleSheet("color: #4fd1c7; margin-bottom: 10px;")
        layout.addWidget(title)

        # Data display
        self.data_display = QTextEdit()
        self.data_display.setStyleSheet("""
            QTextEdit {
                background-color: #1a202c;
                color: #e2e8f0;
                border: 1px solid #4a5568;
                border-radius: 8px;
                font-family: 'Courier New', monospace;
                font-size: 11px;
                padding: 10px;
            }
        """)

        # Initial message
        self.data_display.setText("""
🕷️ SPYDER Direct Dashboard - Ready

📊 Market Data:
   SPY: Waiting for connection...
   QQQ: Waiting for connection...
   VIX: Waiting for connection...

📡 Connection Status:
   Clients: Not connected
   Data Feed: Inactive

🎯 Instructions:
   1. Click 'Connect All Clients' to establish connections
   2. Monitor client status in the Connection Manager
   3. Market data will start flowing once connected

💡 Troubleshooting:
   - Ensure TRADIER_API_KEY is set in your .env file
   - Check TRADIER_ENVIRONMENT (sandbox or production)
    - Verify MASSIVE_API_KEY only if Massive fallback is enabled
        """)

        layout.addWidget(self.data_display)

    def update_market_data(self, symbol, price, change=None):
        """Update market data display"""
        self.data_display.toPlainText()

        # Add market data update
        timestamp = time.strftime("%H:%M:%S")
        update_line = f"[{timestamp}] {symbol}: ${price}"
        if change is not None:
            update_line += f" ({change:+.2f})"

        # Append to display
        self.data_display.append(update_line)

        # Keep only last 50 lines
        lines = self.data_display.toPlainText().split("\n")
        if len(lines) > 50:
            self.data_display.setPlainText("\n".join(lines[-50:]))

    def set_connection_status(self, connected_count, total_count):
        """Update connection status in display"""
        status_msg = (
            f"\n📡 Connection Update: {connected_count}/{total_count} clients connected"
        )
        self.data_display.append(status_msg)


class SPYDERDirectDashboard(QMainWindow):
    """Main SPYDER Direct Dashboard"""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("🕷️ SPYDER Direct Trading Dashboard")
        self.setGeometry(100, 100, 1200, 800)

        # Connection worker
        self.connection_worker = None

        self.setup_ui()
        self.setup_connections()
        self.apply_dark_theme()

    def setup_ui(self):
        """Setup the user interface"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout with splitter
        main_layout = QHBoxLayout(central_widget)
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # Left panel - Connection management
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        self.connection_widget = ConnectionStatusWidget()
        left_layout.addWidget(self.connection_widget)

        # Configuration display
        config_group = QGroupBox("Configuration")
        config_group.setStyleSheet("QGroupBox { font-weight: normal; color: #4fd1c7; }")
        config_layout = QVBoxLayout(config_group)

        self.config_label = QLabel("""
        Broker: Tradier REST API
        Market Data: Tradier primary / Massive fallback
        Environment: sandbox / production (via .env)
        Mode: Direct Connection
        """)
        self.config_label.setStyleSheet(
            "color: #a0aec0; font-size: 10px; font-family: monospace;"
        )
        config_layout.addWidget(self.config_label)

        left_layout.addWidget(config_group)
        left_layout.addStretch()

        # Right panel - Market data
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        self.market_data_widget = MarketDataWidget()
        right_layout.addWidget(self.market_data_widget)

        # Add panels to splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 800])

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(
            "🕷️ SPYDER Direct Dashboard Ready - Click Connect to start"
        )

    def setup_connections(self):
        """Setup signal connections"""
        self.connection_widget.connect_btn.clicked.connect(self.start_connections)
        self.connection_widget.disconnect_btn.clicked.connect(self.stop_connections)

    def apply_dark_theme(self):
        """Apply dark theme"""
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
                border-radius: 8px;
                padding-top: 15px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 20px;
                padding: 0 5px 0 5px;
            }
            QStatusBar {
                background-color: #2d3748;
                color: #e2e8f0;
                border-top: 1px solid #4a5568;
            }
        """)

    def start_connections(self):
        """Start connection process"""
        if self.connection_worker and self.connection_worker.isRunning():
            return

        self.connection_widget.connect_btn.setEnabled(False)
        self.connection_widget.connect_btn.setText("🔄 Connecting...")

        # Create and configure worker
        self.connection_worker = DirectConnectionWorker()

        # Connect signals
        self.connection_worker.connection_established.connect(
            self.on_connection_established
        )
        self.connection_worker.connection_failed.connect(self.on_connection_failed)
        self.connection_worker.all_connected.connect(self.on_all_connected)
        self.connection_worker.progress_updated.connect(self.on_progress_updated)

        # Start worker
        self.connection_worker.start()

        self.status_bar.showMessage("🔄 Establishing connections to Tradier API...")

    def stop_connections(self):
        """Stop all connections"""
        if self.connection_worker:
            self.connection_worker.disconnect_all()

        # Reset UI
        self.connection_widget.connect_btn.setEnabled(True)
        self.connection_widget.connect_btn.setText("🚀 Connect All Clients")
        self.connection_widget.disconnect_btn.setEnabled(False)
        self.connection_widget.progress_bar.setValue(0)

        # Reset client status
        for client_id in range(100, 108):
            self.connection_widget.update_client_status(client_id, "disconnected")

        self.status_bar.showMessage("🔌 All connections closed")

    def on_connection_established(self, client_id, description):
        """Handle successful connection"""
        self.connection_widget.update_client_status(client_id, "connected", description)
        self.status_bar.showMessage(f"✅ Client {client_id} connected")

    def on_connection_failed(self, client_id, error):
        """Handle failed connection"""
        self.connection_widget.update_client_status(client_id, "failed", error)
        self.status_bar.showMessage(f"❌ Client {client_id} failed: {error}")

    def on_progress_updated(self, current, total):
        """Handle progress update"""
        self.connection_widget.update_progress(current, total)
        self.market_data_widget.set_connection_status(current, total)

    def on_all_connected(self):
        """Handle all connections established"""
        self.connection_widget.set_all_connected()
        self.status_bar.showMessage(
            "🎉 All 8 clients connected - Trading system active"
        )

        # Start market data simulation
        self.start_market_data_simulation()

    def start_market_data_simulation(self):
        """Start simulated market data feed"""
        self.market_data_widget.data_display.append("\n🎉 All clients connected!")
        self.market_data_widget.data_display.append("📊 Market data feed starting...")
        self.market_data_widget.data_display.append(
            "💡 In production, real market data would flow here"
        )

    def closeEvent(self, event):
        """Handle application close"""
        if self.connection_worker:
            self.connection_worker.disconnect_all()
            self.connection_worker.quit()
            self.connection_worker.wait()
        event.accept()


def main():
    """Main application entry point"""

    print("🕷️ SPYDER Direct Trading Dashboard")
    print("=" * 50)

    if not GUI_AVAILABLE:
        print("❌ GUI libraries not available")
        return 1

    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("SPYDER Direct Dashboard")
    app.setOrganizationName("SPYDER Trading")

    # Set application icon if available
    icon_path = Path(__file__).parent / "assets" / "spyder_icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Create and show dashboard
    dashboard = SPYDERDirectDashboard()
    dashboard.show()

    # Center window
    screen = app.primaryScreen().geometry()
    size = dashboard.geometry()
    dashboard.move(
        (screen.width() - size.width()) // 2, (screen.height() - size.height()) // 2
    )

    print("✅ Direct dashboard launched successfully")
    print("💡 This version bypasses connection manager timeout issues")
    print("💡 Click 'Connect All Clients' to establish direct connections")

    # Run application
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
