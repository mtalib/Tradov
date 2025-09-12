#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderG02_GUIEntry.py
Group: G (GUI)
Purpose: Simple GUI entry point to launch the trading dashboard

Description:
    Simplified entry point that launches the Spyder trading dashboard
    without requiring all dependencies to be present initially.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    """Main entry point"""
    try:
        # Try to import and launch the dashboard
        from PySide6.QtWidgets import QApplication

        from SpyderG_GUI.SpyderG05_TradingDashboard import TradingDashboard

        app = QApplication(sys.argv)
        app.setApplicationName("Spyder Trading System")

        # Create and show dashboard
        dashboard = TradingDashboard()
        dashboard.show()

        return app.exec()

    except ImportError as e:
        print(f"Import Error: {e}")
        print("\nMake sure you have installed all requirements:")
        print("pip install -r requirements.txt")

        # Try a basic PyQt window
        try:
            from PySide6.QtCore import Qt
            from PySide6.QtWidgets import (QApplication, QLabel, QMainWindow,
                                        QPushButton, QVBoxLayout, QWidget)

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
            label.setStyleSheet("font-size: 24px; font-weight: bold; margin: 20px;")
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
            print("PyQt6 not installed. Please run:")
            print("pip install PyQt6")
            return 1

    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
