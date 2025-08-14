#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Direct launcher for Spyder Trading Dashboard
Bypasses all import issues
"""

import os
import sys

from PyQt6.QtWidgets import QApplication

from SpyderG_GUI.SpyderG05_TradingDashboard import TradingDashboard

# Add Spyder directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import minimal requirements

# Import the dashboard directly

# Create a simple wrapper


class LiveDashboard(TradingDashboard):
    def __init__(self):
        super().__init__()

        # Fix connection status
        if hasattr(self, "connection_label"):
            self.connection_label.setText("IB DISCONNECTED")
            self.connection_label.setStyleSheet("color: #ff0000;")

        # Stop simulation timer
        if hasattr(self, "timer"):
            self.timer.stop()

        # Override start button
        if hasattr(self, "start_button"):
            self.start_button.clicked.connect(self.check_ib_connection)

    def check_ib_connection(self):
        """Check for IB Gateway when START clicked"""
        import socket

        # Check ports
        paper_ok = socket.socket().connect_ex(("127.0.0.1", 4002)) == 0
        live_ok = socket.socket().connect_ex(("127.0.0.1", 4001)) == 0

        if paper_ok or live_ok:
            mode = "PAPER (4002)" if paper_ok else "LIVE (4001)"
            self.connection_label.setText("IB CONNECTED   ")
            self.connection_label.setStyleSheet("color: #00ff00;")
            if hasattr(self, "add_ai_log"):
                self.add_ai_log(f"✅ Connected to IB Gateway - {mode}")
        else:
            if hasattr(self, "add_ai_log"):
                self.add_ai_log("❌ IB Gateway not found. Please start IB Gateway.")


# Main execution
if __name__ == "__main__":
    app = QApplication(sys.argv)
    dashboard = LiveDashboard()
    dashboard.show()
    sys.exit(app.exec())
