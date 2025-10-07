#!/usr/bin/env python3
"""
SPYDER - Connection Method Selector
Professional GUI for choosing between IB Gateway and TWS API connections
"""

import sys
import os
import subprocess
import json
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QPushButton,
    QLabel,
    QFrame,
    QMessageBox,
    QProgressBar,
    QTextEdit,
    QGroupBox,
    QRadioButton,
    QButtonGroup,
    QGridLayout,
    QCheckBox,
    QComboBox,
    QSpinBox,
    QLineEdit,
    QTabWidget,
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QSize
from PySide6.QtGui import QFont, QPixmap, QIcon, QPalette, QColor


class ConnectionTester(QThread):
    """Background thread for testing connections"""

    result_ready = Signal(str, bool, str)  # connection_type, success, message

    def __init__(self, connection_type, config=None):
        super().__init__()
        self.connection_type = connection_type
        self.config = config or {}

    def run(self):
        """Test the specified connection type"""
        try:
            if self.connection_type == "gateway":
                success, message = self.test_gateway_connection()
            elif self.connection_type == "remote_tws":
                success, message = self.test_remote_tws_connection()
            else:
                success, message = False, "Unknown connection type"

            self.result_ready.emit(self.connection_type, success, message)

        except Exception as e:
            self.result_ready.emit(
                self.connection_type, False, f"Test failed: {str(e)}"
            )

    def test_gateway_connection(self):
        """Test IB Gateway connection"""
        import socket
        import subprocess

        try:
            # Check if Gateway process is running
            result = subprocess.run(
                ["pgrep", "-f", "ibgateway"], capture_output=True, text=True, timeout=5
            )
            gateway_running = bool(result.stdout.strip())

            # Test connection to port 4002 (paper)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex(("127.0.0.1", 4002))
            sock.close()

            if result == 0:
                return True, f"✅ Gateway accessible on port 4002"
            elif gateway_running:
                return False, f"⚠️ Gateway running but port 4002 not accessible"
            else:
                return False, f"❌ Gateway not running"

        except Exception as e:
            return False, f"❌ Gateway test failed: {str(e)}"

    def test_remote_tws_connection(self):
        """Test Remote TWS connection"""
        import socket

        try:
            # Get IP from current config or use default
            tws_ip = self.config.get("tws_ip", "192.168.1.244")
            tws_port = self.config.get("tws_port", 7497)

            # Test connection
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((tws_ip, tws_port))
            sock.close()

            if result == 0:
                return True, f"✅ TWS accessible at {tws_ip}:{tws_port}"
            else:
                return False, f"❌ Cannot reach TWS at {tws_ip}:{tws_port}"

        except Exception as e:
            return False, f"❌ TWS test failed: {str(e)}"


class SpyderConnectionSelector(QMainWindow):
    """Main connection selector window"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("🕷️ SPYDER - Connection & Trading Mode Selector")
        self.setFixedSize(900, 700)
        self.setStyleSheet(self.get_dark_stylesheet())

        # Center window
        self.center_window()

        # Initialize UI
        self.setup_ui()

        # Load current configuration
        self.load_current_config()

        # Update button states after UI is fully initialized
        self.update_launch_buttons()

        # Test connections on startup
        self.test_all_connections()

    def center_window(self):
        """Center the window on screen"""
        screen = QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        x = (screen_geometry.width() - self.width()) // 2
        y = (screen_geometry.height() - self.height()) // 2
        self.move(x, y)

    def setup_ui(self):
        """Setup the user interface"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        # Header
        self.setup_header(layout)

        # Connection and trading mode options
        self.setup_connection_options(layout)

        # Status section
        self.setup_status_section(layout)

        # Action buttons
        self.setup_action_buttons(layout)

        # Current config display
        self.setup_current_config(layout)

    def setup_header(self, layout):
        """Setup header section"""
        header_frame = QFrame()
        header_frame.setFrameStyle(QFrame.Box)
        header_frame.setStyleSheet(
            "QFrame { background-color: #2d3748; border-radius: 10px; padding: 20px; }"
        )

        header_layout = QVBoxLayout(header_frame)

        title = QLabel("🕷️ SPYDER Trading System")
        title.setFont(QFont("Arial", 24, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #4fd1c7; margin-bottom: 10px;")

        subtitle = QLabel("Choose Connection Method & Trading Mode")
        subtitle.setFont(QFont("Arial", 16))
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #a0aec0; margin-bottom: 10px;")

        description = QLabel(
            "Select connection method (Gateway vs TWS) and trading mode (Paper vs Live)\n"
            "All combinations are fully supported with automatic configuration"
        )
        description.setFont(QFont("Arial", 11))
        description.setAlignment(Qt.AlignCenter)
        description.setStyleSheet("color: #718096;")
        description.setWordWrap(True)

        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        header_layout.addWidget(description)

        layout.addWidget(header_frame)

    def setup_connection_options(self, layout):
        """Setup connection option selection"""
        options_frame = QFrame()
        options_frame.setFrameStyle(QFrame.Box)
        options_frame.setStyleSheet(
            "QFrame { background-color: #2d3748; border-radius: 10px; }"
        )

        options_layout = QGridLayout(options_frame)
        options_layout.setSpacing(20)
        options_layout.setContentsMargins(20, 20, 20, 20)

        # Create tabbed interface for connection and mode selection
        self.setup_tabs = QTabWidget()
        self.setup_tabs.setStyleSheet("""
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

        # Connection Method Tab
        connection_tab = QWidget()
        connection_layout = QGridLayout(connection_tab)
        connection_layout.setSpacing(20)

        # Connection type selection
        self.connection_group = QButtonGroup()

        # IB Gateway Option
        self.gateway_option = self.create_connection_option(
            title="🏪 IB Gateway (Local)",
            description="Connect to local IB Gateway\n• Localhost connection (127.0.0.1)\n• Ports 4001/4002\n• No network dependency\n• Proven stable for your setup",
            status_label="gateway_status",
            test_button="test_gateway",
            pros=[
                "✅ No network latency",
                "✅ Local control",
                "✅ Your current working setup",
            ],
            cons=["⚠️ Gateway handshake issues (known)", "⚠️ Resource usage on Ubuntu"],
        )

        # TWS API Option
        self.tws_option = self.create_connection_option(
            title="🌐 TWS API (Remote)",
            description="Connect to TWS on Windows computer\n• Remote connection (192.168.1.244)\n• Ports 7496/7497\n• Professional architecture\n• Eliminates Gateway issues",
            status_label="tws_status",
            test_button="test_tws",
            pros=[
                "✅ No handshake timeouts",
                "✅ Better stability",
                "✅ Visual TWS interface",
            ],
            cons=["⚠️ Network dependency", "⚠️ Requires Windows computer"],
        )

        connection_layout.addWidget(self.gateway_option, 0, 0)
        connection_layout.addWidget(self.tws_option, 0, 1)

        self.setup_tabs.addTab(connection_tab, "🔌 Connection Method")

        # Trading Mode Tab
        mode_tab = QWidget()
        mode_layout = QGridLayout(mode_tab)
        mode_layout.setSpacing(20)

        # Trading mode selection
        self.trading_mode_group = QButtonGroup()

        # Paper Trading Option
        self.paper_option = self.create_trading_mode_option(
            title="📝 Paper Trading",
            description="Simulated trading with virtual money\n• Risk-free testing\n• Full functionality\n• Perfect for development\n• IB provides realistic simulation",
            pros=[
                "✅ Zero financial risk",
                "✅ Perfect for testing",
                "✅ Full feature access",
                "✅ Real market data",
            ],
            cons=["⚠️ No real profits", "⚠️ May have different fills"],
        )

        # Live Trading Option
        self.live_option = self.create_trading_mode_option(
            title="💰 Live Trading",
            description="Real trading with actual money\n• Real profits and losses\n• Actual market execution\n• Production environment\n• Requires sufficient capital",
            pros=[
                "✅ Real trading profits",
                "✅ Actual market fills",
                "✅ True market conditions",
            ],
            cons=[
                "🚨 Real financial risk",
                "🚨 Requires live account",
                "🚨 Capital requirements",
            ],
        )

        mode_layout.addWidget(self.paper_option, 0, 0)
        mode_layout.addWidget(self.live_option, 0, 1)

        self.setup_tabs.addTab(mode_tab, "📊 Trading Mode")

        options_layout.addWidget(self.setup_tabs, 0, 0)

        layout.addWidget(options_frame)

    def create_connection_option(
        self, title, description, status_label, test_button, pros, cons
    ):
        """Create a connection option widget"""
        option_frame = QFrame()
        option_frame.setFrameStyle(QFrame.StyledPanel)
        option_frame.setStyleSheet("""
            QFrame {
                background-color: #1a202c;
                border: 2px solid #4a5568;
                border-radius: 15px;
                padding: 15px;
            }
            QFrame:hover {
                border-color: #4fd1c7;
            }
        """)

        layout = QVBoxLayout(option_frame)
        layout.setSpacing(15)

        # Title with radio button
        title_layout = QHBoxLayout()
        radio = QRadioButton()
        radio.setStyleSheet("QRadioButton::indicator { width: 20px; height: 20px; }")
        self.connection_group.addButton(radio)

        title_label = QLabel(title)
        title_label.setFont(QFont("Arial", 14, QFont.Bold))
        title_label.setStyleSheet("color: #4fd1c7;")

        title_layout.addWidget(radio)
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        # Description
        desc_label = QLabel(description)
        desc_label.setFont(QFont("Arial", 10))
        desc_label.setStyleSheet("color: #a0aec0; padding: 10px 0px;")
        desc_label.setWordWrap(True)

        # Pros and Cons
        pros_cons_layout = QHBoxLayout()

        # Pros
        pros_widget = QWidget()
        pros_layout = QVBoxLayout(pros_widget)
        pros_title = QLabel("Advantages:")
        pros_title.setFont(QFont("Arial", 9, QFont.Bold))
        pros_title.setStyleSheet("color: #68d391;")
        pros_layout.addWidget(pros_title)

        for pro in pros:
            pro_label = QLabel(pro)
            pro_label.setFont(QFont("Arial", 8))
            pro_label.setStyleSheet("color: #68d391; padding-left: 10px;")
            pros_layout.addWidget(pro_label)

        # Cons
        cons_widget = QWidget()
        cons_layout = QVBoxLayout(cons_widget)
        cons_title = QLabel("Considerations:")
        cons_title.setFont(QFont("Arial", 9, QFont.Bold))
        cons_title.setStyleSheet("color: #fc8181;")
        cons_layout.addWidget(cons_title)

        for con in cons:
            con_label = QLabel(con)
            con_label.setFont(QFont("Arial", 8))
            con_label.setStyleSheet("color: #fc8181; padding-left: 10px;")
            cons_layout.addWidget(con_label)

        pros_cons_layout.addWidget(pros_widget)
        pros_cons_layout.addWidget(cons_widget)

        # Status and test button
        status_layout = QHBoxLayout()
        status = QLabel("Status: Testing...")
        status.setFont(QFont("Arial", 10))
        status.setStyleSheet("color: #fbd38d;")
        setattr(self, status_label, status)

        test_btn = QPushButton("Test Connection")
        test_btn.setStyleSheet(self.get_button_style())
        test_btn.clicked.connect(lambda: self.test_connection_type(test_button))
        setattr(self, test_button, test_btn)

        status_layout.addWidget(status)
        status_layout.addStretch()
        status_layout.addWidget(test_btn)

        # Connect radio button to frame selection
        radio.toggled.connect(
            lambda checked: self.on_option_selected(option_frame, checked)
        )

        # Store radio button reference
        if "gateway" in status_label:
            self.gateway_radio = radio
        else:
            self.tws_radio = radio

        layout.addLayout(title_layout)
        layout.addWidget(desc_label)
        layout.addLayout(pros_cons_layout)
        layout.addLayout(status_layout)

        return option_frame

    def create_trading_mode_option(self, title, description, pros, cons):
        """Create a trading mode option widget"""
        option_frame = QFrame()
        option_frame.setFrameStyle(QFrame.StyledPanel)
        option_frame.setStyleSheet("""
            QFrame {
                background-color: #1a202c;
                border: 2px solid #4a5568;
                border-radius: 15px;
                padding: 15px;
            }
            QFrame:hover {
                border-color: #4fd1c7;
            }
        """)

        layout = QVBoxLayout(option_frame)
        layout.setSpacing(15)

        # Title with radio button
        title_layout = QHBoxLayout()
        radio = QRadioButton()
        radio.setStyleSheet("QRadioButton::indicator { width: 20px; height: 20px; }")
        self.trading_mode_group.addButton(radio)

        title_label = QLabel(title)
        title_label.setFont(QFont("Arial", 14, QFont.Bold))
        title_label.setStyleSheet("color: #4fd1c7;")

        title_layout.addWidget(radio)
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        # Description
        desc_label = QLabel(description)
        desc_label.setFont(QFont("Arial", 10))
        desc_label.setStyleSheet("color: #a0aec0; padding: 10px 0px;")
        desc_label.setWordWrap(True)

        # Pros and Cons
        pros_cons_layout = QHBoxLayout()

        # Pros
        pros_widget = QWidget()
        pros_layout = QVBoxLayout(pros_widget)
        pros_title = QLabel("Advantages:")
        pros_title.setFont(QFont("Arial", 9, QFont.Bold))
        pros_title.setStyleSheet("color: #68d391;")
        pros_layout.addWidget(pros_title)

        for pro in pros:
            pro_label = QLabel(pro)
            pro_label.setFont(QFont("Arial", 8))
            pro_label.setStyleSheet("color: #68d391; padding-left: 10px;")
            pros_layout.addWidget(pro_label)

        # Cons
        cons_widget = QWidget()
        cons_layout = QVBoxLayout(cons_widget)
        cons_title = QLabel("Considerations:")
        cons_title.setFont(QFont("Arial", 9, QFont.Bold))
        cons_title.setStyleSheet("color: #fc8181;")
        cons_layout.addWidget(cons_title)

        for con in cons:
            con_label = QLabel(con)
            con_label.setFont(QFont("Arial", 8))
            con_label.setStyleSheet("color: #fc8181; padding-left: 10px;")
            cons_layout.addWidget(con_label)

        pros_cons_layout.addWidget(pros_widget)
        pros_cons_layout.addWidget(cons_widget)

        # Connect radio button to frame selection
        radio.toggled.connect(
            lambda checked: self.on_mode_option_selected(option_frame, checked)
        )

        # Store radio button reference
        if "Paper" in title:
            self.paper_radio = radio
            radio.setChecked(True)  # Default to paper trading
        else:
            self.live_radio = radio

        layout.addLayout(title_layout)
        layout.addWidget(desc_label)
        layout.addLayout(pros_cons_layout)

        return option_frame

    def setup_status_section(self, layout):
        """Setup connection status section"""
        status_frame = QFrame()
        status_frame.setFrameStyle(QFrame.Box)
        status_frame.setStyleSheet(
            "QFrame { background-color: #2d3748; border-radius: 10px; }"
        )

        status_layout = QVBoxLayout(status_frame)
        status_layout.setContentsMargins(20, 15, 20, 15)

        status_title = QLabel("🔍 Connection Status")
        status_title.setFont(QFont("Arial", 14, QFont.Bold))
        status_title.setStyleSheet("color: #4fd1c7; margin-bottom: 10px;")

        self.status_text = QTextEdit()
        self.status_text.setMaximumHeight(120)
        self.status_text.setStyleSheet("""
            QTextEdit {
                background-color: #1a202c;
                color: #e2e8f0;
                border: 1px solid #4a5568;
                border-radius: 5px;
                padding: 10px;
                font-family: 'Courier New', monospace;
                font-size: 10px;
            }
        """)
        self.status_text.setReadOnly(True)

        status_layout.addWidget(status_title)
        status_layout.addWidget(self.status_text)

        layout.addWidget(status_frame)

    def setup_action_buttons(self, layout):
        """Setup action buttons"""
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)

        # Test All button
        self.test_all_btn = QPushButton("🔍 Test All Connections")
        self.test_all_btn.setStyleSheet(self.get_button_style("#3182ce"))
        self.test_all_btn.clicked.connect(self.test_all_connections)

        # Launch with Selected button
        self.launch_btn = QPushButton("🚀 Launch SPYDER")
        self.launch_btn.setStyleSheet(self.get_button_style("#38a169"))
        self.launch_btn.setEnabled(False)
        self.launch_btn.clicked.connect(self.launch_spyder)

        # Switch Config button
        self.switch_btn = QPushButton("🔄 Switch & Save Config")
        self.switch_btn.setStyleSheet(self.get_button_style("#d69e2e"))
        self.switch_btn.setEnabled(False)
        self.switch_btn.clicked.connect(self.switch_configuration)

        # Cancel button
        cancel_btn = QPushButton("❌ Cancel")
        cancel_btn.setStyleSheet(self.get_button_style("#e53e3e"))
        cancel_btn.clicked.connect(self.close)

        button_layout.addWidget(self.test_all_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.switch_btn)
        button_layout.addWidget(self.launch_btn)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

    def setup_current_config(self, layout):
        """Setup current configuration display"""
        config_frame = QFrame()
        config_frame.setFrameStyle(QFrame.Box)
        config_frame.setStyleSheet(
            "QFrame { background-color: #2d3748; border-radius: 10px; }"
        )

        config_layout = QVBoxLayout(config_frame)
        config_layout.setContentsMargins(20, 15, 20, 15)

        config_title = QLabel("⚙️ Current Configuration")
        config_title.setFont(QFont("Arial", 12, QFont.Bold))
        config_title.setStyleSheet("color: #4fd1c7;")

        self.current_config_label = QLabel("Loading...")
        self.current_config_label.setFont(QFont("Arial", 10))
        self.current_config_label.setStyleSheet("color: #a0aec0; padding: 10px 0px;")

        config_layout.addWidget(config_title)
        config_layout.addWidget(self.current_config_label)

        layout.addWidget(config_frame)

    def get_dark_stylesheet(self):
        """Get dark theme stylesheet"""
        return """
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
            }
            QRadioButton {
                color: #e2e8f0;
                spacing: 10px;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
            }
            QRadioButton::indicator:unchecked {
                border: 2px solid #4a5568;
                border-radius: 9px;
                background-color: #2d3748;
            }
            QRadioButton::indicator:checked {
                border: 2px solid #4fd1c7;
                border-radius: 9px;
                background-color: #4fd1c7;
            }
        """

    def get_button_style(self, color="#4fd1c7"):
        """Get button stylesheet"""
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 11px;
                min-width: 120px;
            }}
            QPushButton:hover {{
                background-color: {color}aa;
            }}
            QPushButton:pressed {{
                background-color: {color}88;
            }}
            QPushButton:disabled {{
                background-color: #4a5568;
                color: #718096;
            }}
        """

    def on_option_selected(self, frame, checked):
        """Handle connection method selection"""
        if checked:
            frame.setStyleSheet(frame.styleSheet().replace("#4a5568", "#4fd1c7"))
            self.update_launch_buttons()
        else:
            frame.setStyleSheet(frame.styleSheet().replace("#4fd1c7", "#4a5568"))

    def on_mode_option_selected(self, frame, checked):
        """Handle trading mode selection"""
        if checked:
            frame.setStyleSheet(frame.styleSheet().replace("#4a5568", "#4fd1c7"))
            self.update_launch_buttons()
        else:
            frame.setStyleSheet(frame.styleSheet().replace("#4fd1c7", "#4a5568"))

    def update_launch_buttons(self):
        """Update launch button states based on selections"""
        # Safety check - buttons might not be created yet during initialization
        if not hasattr(self, "launch_btn") or not hasattr(self, "switch_btn"):
            return

        connection_selected = (
            self.gateway_radio.isChecked() or self.tws_radio.isChecked()
        )
        mode_selected = self.paper_radio.isChecked() or self.live_radio.isChecked()

        if connection_selected and mode_selected:
            self.launch_btn.setEnabled(True)
            self.switch_btn.setEnabled(True)
        else:
            self.launch_btn.setEnabled(False)
            self.switch_btn.setEnabled(False)

    def load_current_config(self):
        """Load and display current configuration"""
        try:
            config_path = Path(__file__).parent / "config" / "config.py"

            if config_path.exists():
                with open(config_path, "r") as f:
                    content = f.read()

                if "remote_tws" in content:
                    # Extract IP address
                    import re

                    ip_match = re.search(r'"ip_address":\s*"([^"]+)"', content)
                    ip = ip_match.group(1) if ip_match else "Unknown"

                    config_text = f"🌐 Remote TWS Configuration Active\n📍 Windows Computer: {ip}\n🔌 Ports: 7496 (Live) / 7497 (Paper)"
                    self.tws_radio.setChecked(True)

                elif "127.0.0.1" in content and "4002" in content:
                    config_text = f"🏪 IB Gateway Configuration Active\n📍 Local Host: 127.0.0.1\n🔌 Ports: 4001 (Live) / 4002 (Paper)"
                    self.gateway_radio.setChecked(True)

                else:
                    config_text = "❓ Unknown configuration detected"

            else:
                config_text = "⚠️ No configuration file found"

            self.current_config_label.setText(config_text)

        except Exception as e:
            self.current_config_label.setText(f"❌ Error loading config: {str(e)}")

    def test_all_connections(self):
        """Test all available connections"""
        self.status_text.clear()
        self.status_text.append("🔍 Testing all connection methods...\n")

        # Update status labels
        self.gateway_status.setText("Status: Testing...")
        self.tws_status.setText("Status: Testing...")

        # Test Gateway
        self.test_connection_type("gateway")

        # Test TWS (with small delay)
        QTimer.singleShot(1000, lambda: self.test_connection_type("tws"))

    def test_connection_type(self, connection_type):
        """Test specific connection type"""
        if connection_type == "gateway" or connection_type == "test_gateway":
            self.gateway_status.setText("Status: Testing...")
            self.gateway_tester = ConnectionTester("gateway")
            self.gateway_tester.result_ready.connect(self.on_test_result)
            self.gateway_tester.start()

        elif connection_type == "tws" or connection_type == "test_tws":
            self.tws_status.setText("Status: Testing...")
            # Get current TWS IP from config if available
            config = {}
            try:
                config_path = Path(__file__).parent / "config" / "config.py"
                if config_path.exists():
                    with open(config_path, "r") as f:
                        content = f.read()
                    import re

                    ip_match = re.search(r'"ip_address":\s*"([^"]+)"', content)
                    if ip_match:
                        config["tws_ip"] = ip_match.group(1)
            except:
                pass

            self.tws_tester = ConnectionTester("remote_tws", config)
            self.tws_tester.result_ready.connect(self.on_test_result)
            self.tws_tester.start()

    def on_test_result(self, connection_type, success, message):
        """Handle test results"""
        timestamp = QTimer().remainingTime()  # Simple timestamp

        # Update status text
        status_icon = "✅" if success else "❌"
        self.status_text.append(f"{status_icon} {connection_type.upper()}: {message}")

        # Update status labels
        if connection_type == "gateway":
            self.gateway_status.setText(
                f"Status: {'✅ Available' if success else '❌ Unavailable'}"
            )
            self.gateway_status.setStyleSheet(
                f"color: {'#68d391' if success else '#fc8181'};"
            )
        elif connection_type == "remote_tws":
            self.tws_status.setText(
                f"Status: {'✅ Available' if success else '❌ Unavailable'}"
            )
            self.tws_status.setStyleSheet(
                f"color: {'#68d391' if success else '#fc8181'};"
            )

    def get_selected_connection(self):
        """Get the selected connection type"""
        if self.gateway_radio.isChecked():
            return "gateway"
        elif self.tws_radio.isChecked():
            return "remote_tws"
        return None

    def get_selected_trading_mode(self):
        """Get the selected trading mode"""
        if self.paper_radio.isChecked():
            return "paper"
        elif self.live_radio.isChecked():
            return "live"
        return "paper"  # Default fallback

    def switch_configuration(self):
        """Switch to selected configuration"""
        selected_connection = self.get_selected_connection()
        selected_mode = self.get_selected_trading_mode()

        if not selected_connection:
            QMessageBox.warning(
                self,
                "No Selection",
                "Please select both connection method and trading mode.",
            )
            return

        try:
            config_dir = Path(__file__).parent / "config"
            current_config = config_dir / "config.py"

            # Backup current config
            if current_config.exists():
                backup_path = (
                    config_dir
                    / "backups"
                    / f"config_backup_{int(QTimer().remainingTime())}.py"
                )
                backup_path.parent.mkdir(exist_ok=True)
                import shutil

                shutil.copy2(current_config, backup_path)

            # Switch configuration
            if selected_connection == "gateway":
                source_config = config_dir / "config_gateway.py"
            else:
                source_config = config_dir / "config_remote_tws.py"

            if source_config.exists():
                import shutil

                shutil.copy2(source_config, current_config)

                self.status_text.append(
                    f"\n✅ Switched to {selected_connection} ({selected_mode} mode) configuration"
                )
                self.load_current_config()

                QMessageBox.information(
                    self,
                    "Configuration Switched",
                    f"Successfully switched to {selected_connection.replace('_', ' ').title()} configuration.\n"
                    f"Trading mode: {selected_mode.title()}\n\n"
                    f"You can now launch SPYDER with the new settings.",
                )
            else:
                QMessageBox.critical(
                    self,
                    "Configuration Error",
                    f"Source configuration file not found: {source_config}",
                )

        except Exception as e:
            QMessageBox.critical(
                self, "Switch Failed", f"Failed to switch configuration:\n{str(e)}"
            )

    def launch_spyder(self):
        """Launch SPYDER with selected configuration"""
        selected_connection = self.get_selected_connection()
        selected_mode = self.get_selected_trading_mode()

        if not selected_connection:
            QMessageBox.warning(
                self,
                "No Selection",
                "Please select both connection method and trading mode.",
            )
            return

        try:
            # Switch config first if needed
            self.switch_configuration()

            # Launch appropriate script with trading mode
            script_dir = Path(__file__).parent

            if selected_connection == "gateway":
                launch_script = script_dir / "launch_spyder_gateway.sh"
                if launch_script.exists():
                    subprocess.Popen(
                        ["bash", str(launch_script), f"--mode={selected_mode}"]
                    )
                else:
                    # Fallback to production launcher with environment variable
                    import os

                    os.environ["TRADING_MODE"] = selected_mode
                    launch_script = script_dir / "launch_dashboard_production.py"
                    subprocess.Popen([sys.executable, str(launch_script)])
            else:
                # Remote TWS - use TWS launcher
                launch_script = script_dir / "launch_spyder_tws.sh"
                if launch_script.exists():
                    subprocess.Popen(
                        ["bash", str(launch_script), f"--mode={selected_mode}"]
                    )
                else:
                    # Fallback to production launcher with environment variable
                    import os

                    os.environ["TRADING_MODE"] = selected_mode
                    launch_script = script_dir / "launch_dashboard_production.py"
                    subprocess.Popen([sys.executable, str(launch_script)])

            self.status_text.append(
                f"\n🚀 Launching SPYDER with {selected_connection} ({selected_mode} mode)..."
            )

            # Close selector after short delay
            QTimer.singleShot(2000, self.close)

        except Exception as e:
            QMessageBox.critical(
                self, "Launch Failed", f"Failed to launch SPYDER:\n{str(e)}"
            )


def main():
    """Main application entry point"""
    app = QApplication(sys.argv if hasattr(sys, "argv") else [])
    app.setApplicationName("SPYDER Connection Selector")
    app.setOrganizationName("SPYDER Trading")

    # Set application icon if available
    icon_path = Path(__file__).parent / "assets" / "spyder_icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    selector = SpyderConnectionSelector()
    selector.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
