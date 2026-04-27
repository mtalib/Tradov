#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG14_Dashboard.py
Purpose: SPYDER - Automated SPY Options Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    SPYDER - Automated SPY Options Trading System

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
from pathlib import Path
import logging

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def main():
    """Main entry point"""
    try:
        # Try to import PySide6 first
        try:
            from PySide6.QtWidgets import QApplication
        except ImportError as e:
            logging.info("PySide6 import error: %s", e)
            # Fall back to basic window
            raise ImportError("PySide6 not available")

        # Then try to import the dashboard
        try:
            from SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
        except ImportError as e:
            logging.info("Dashboard import error: %s", e)
            logging.info("This might be due to missing dependencies in the dashboard modules.")
            # Fall back to basic window
            raise ImportError("Dashboard modules not found")

        app = QApplication(sys.argv)
        app.setApplicationName("Spyder Trading System")

        # CRITICAL: Desktop Integration for GNOME/Wayland
        desktop_file_name = os.environ.get("SPYDER_DESKTOP_FILE_NAME", "spyder-trading")
        app.setDesktopFileName(desktop_file_name)
        logging.info("✅ Desktop integration: %s", desktop_file_name)

        # Create and show dashboard
        dashboard = SpyderTradingDashboard()
        dashboard.show()

        return app.exec()

    except ImportError as e:
        logging.info("Import Error: %s", e)
        logging.info("\nMake sure you have installed all requirements:")
        logging.info("pip install -r requirements.txt")

        # Try a basic PyQt window
        try:
            from PySide6.QtCore import Qt
            from PySide6.QtWidgets import (
                QApplication,
                QLabel,
                QMainWindow,
                QPushButton,
                QVBoxLayout,
                QWidget,
            )

            app = QApplication(sys.argv)

            # Create basic window
            window = QMainWindow()
            window.setWindowTitle("Spyder Trading System")
            window.setGeometry(100, 100, 800, 600)

            # Central widget
            central = QWidget()
            layout = QVBoxLayout()

            # Add label
            label = QLabel("Spyder Trading Dashboard")
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("font-size: 24px; font-weight: normal; margin: 20px;")
            layout.addWidget(label)

            # Add status
            status = QLabel("Dashboard modules not found. Please check installation.")
            status.setAlignment(Qt.AlignCenter)
            layout.addWidget(status)

            # Add button
            btn = QPushButton("Close")
            btn.clicked.connect(app.quit)
            layout.addWidget(btn)

            central.setLayout(layout)
            window.setCentralWidget(central)

            window.show()
            return app.exec()

        except ImportError:
            logging.info("PyQt6 not installed. Please run:")
            logging.info("pip install PyQt6")
            return 1

    except Exception as e:
        logging.info("Error: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
