#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for GUI logging integration.

This script demonstrates how to test the GUI log handler
without running the full trading system.
"""

import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QTextEdit
    from PySide6.QtCore import QTimer
    from SpyderG_GUI.SpyderG99_GUILogHandler import setup_gui_logging
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Make sure PySide6 is installed: pip install PySide6")
    sys.exit(1)


class SimpleDashboard(QMainWindow):
    """Simple dashboard mock for testing."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("GUI Logging Test")
        self.setGeometry(100, 100, 800, 600)

        # Create central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # System log display
        self.system_log = QTextEdit()
        self.system_log.setReadOnly(True)
        self.system_log.setPlaceholderText("System Log (will appear here)")
        layout.addWidget(self.system_log)

        # Automation log display
        self.auto_log = QTextEdit()
        self.auto_log.setReadOnly(True)
        self.auto_log.setPlaceholderText("Automation Log (will appear here)")
        layout.addWidget(self.auto_log)

        # Storage for log messages
        self.system_logs = []
        self.automation_logs = []

    def add_system_log(self, message: str):
        """Add message to system log."""
        self.system_logs.append(message)
        if len(self.system_logs) > 100:
            self.system_logs = self.system_logs[-100:]

        # Update display
        self.system_log.clear()
        self.system_log.append("\n".join(self.system_logs[-20:]))

    def add_automation_log(self, message: str):
        """Add message to automation log."""
        self.automation_logs.append(message)
        if len(self.automation_logs) > 100:
            self.automation_logs = self.automation_logs[-100:]

        # Update display
        self.auto_log.clear()
        self.auto_log.append("\n".join(self.automation_logs[-20:]))


def test_logging():
    """Test the GUI logging integration."""

    # Initialize logging
    SpyderLogger.initialize_logging(log_level="INFO")

    # Create application
    app = QApplication(sys.argv)
    dashboard = SimpleDashboard()
    dashboard.show()

    # Setup GUI logging
    handler = setup_gui_logging(dashboard, log_level="INFO")
    print("✅ GUI logging handler setup complete")

    # Create test loggers
    system_logger = logging.getLogger("SpyderB_Broker")
    strategy_logger = logging.getLogger("SpyderD_Strategies")

    # Generate test logs
    def generate_test_logs():
        """Generate various test log messages."""
        system_logger.info("Connection established to Tradier API")
        system_logger.warning("Market data delayed by 15 seconds")

        strategy_logger.info("Iron Condor signal detected")
        strategy_logger.info("Position sizing: $5000")

        system_logger.error("Failed to fetch option chain")

        strategy_logger.info("Order submitted: BUY 10 SPY CALL 450")
        strategy_logger.info("Order filled at $2.50")

        print("✅ Test logs generated - check dashboard display!")

    # Generate logs after 1 second
    QTimer.singleShot(1000, generate_test_logs)

    # Generate more logs every 3 seconds
    timer = QTimer()
    counter = [0]

    def periodic_logs():
        counter[0] += 1
        system_logger.info(f"System heartbeat #{counter[0]}")
        strategy_logger.info(f"Strategy evaluation #{counter[0]}")

        if counter[0] % 3 == 0:
            system_logger.warning(f"Periodic warning #{counter[0]}")

        if counter[0] >= 10:
            timer.stop()
            print("✅ Test complete!")

    timer.timeout.connect(periodic_logs)
    timer.start(3000)

    # Run application
    sys.exit(app.exec())


if __name__ == "__main__":
    print("=" * 70)
    print("GUI LOGGING TEST")
    print("=" * 70)
    print("\nThis test will:")
    print("1. Create a simple dashboard with log displays")
    print("2. Setup GUI logging handler")
    print("3. Generate test log messages")
    print("4. Verify logs appear in both panels")
    print("\n" + "=" * 70)

    test_logging()
