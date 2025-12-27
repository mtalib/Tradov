#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG16_CircuitBreakerMonitor.py
Purpose: Circuit Breaker Status Monitor Widget for Trading Dashboard
Author: Claude (AI Assistant)
Year Created: 2025
Last Updated: 2025-11-25 Time: 12:00:00

Module Description:
    Real-time circuit breaker monitoring widget for the Spyder trading dashboard.
    Displays status, statistics, and manual control for Tradier and Polygon.io
    circuit breakers with visual indicators and health metrics.

Key Features:
    • Real-time circuit breaker state monitoring (CLOSED/OPEN/HALF_OPEN)
    • Failure count tracking and threshold indicators
    • Recovery timeout countdowns
    • Manual reset capability
    • Visual color-coded status indicators
    • Integration with SpyderU40_RateLimiter and SpyderU41_CircuitBreaker

Dependencies:
    • PySide6: Qt6 GUI framework
    • SpyderU41_CircuitBreaker: Circuit breaker implementation
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QGroupBox, QFrame, QLCDNumber, QProgressBar
)
from PySide6.QtCore import QTimer, Signal, Qt
from PySide6.QtGui import QFont, QColor, QPalette

# ==============================================================================
# SPYDER IMPORTS
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU41_CircuitBreaker import (
        tradier_breaker, polygon_breaker, CircuitState
    )
    CIRCUIT_BREAKERS_AVAILABLE = True
except ImportError:
    CIRCUIT_BREAKERS_AVAILABLE = False
    print("⚠️ Circuit breakers not available - using simulation mode")

    # Mock circuit breaker for development
    class CircuitState:
        CLOSED = "CLOSED"
        OPEN = "OPEN"
        HALF_OPEN = "HALF_OPEN"

    class MockCircuitBreaker:
        def __init__(self, name):
            self.name = name
            self.state = CircuitState.CLOSED

        def get_stats(self):
            return {
                "state": self.state,
                "failure_count": 0,
                "success_count": 0,
                "last_failure_time": None,
                "failure_threshold": 5,
                "recovery_timeout": 60.0
            }

        async def reset(self):
            self.state = CircuitState.CLOSED

    tradier_breaker = MockCircuitBreaker("tradier")
    polygon_breaker = MockCircuitBreaker("polygon")

# ==============================================================================
# CIRCUIT BREAKER MONITOR WIDGET
# ==============================================================================

class CircuitBreakerMonitor(QWidget):
    """
    Circuit Breaker Status Monitor Widget.

    Displays real-time status of Tradier and Polygon circuit breakers with
    visual indicators, statistics, and manual control capabilities.
    """

    # Signals
    reset_requested = Signal(str)  # breaker_name

    def __init__(self, parent=None):
        super().__init__(parent)

        # State tracking
        self.breaker_states = {
            "tradier": CircuitState.CLOSED,
            "polygon": CircuitState.CLOSED
        }

        # Setup UI
        self.setup_ui()

        # Setup update timer (update every 1 second)
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(1000)

        # Initial update
        self.update_display()

    def setup_ui(self):
        """Setup the user interface"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(10)

        # Title
        title_label = QLabel("🔒 Circuit Breaker Status")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(separator)

        # Circuit breaker panels
        self.tradier_panel = self.create_breaker_panel("Tradier API", "tradier")
        self.polygon_panel = self.create_breaker_panel("Polygon.io", "polygon")

        main_layout.addWidget(self.tradier_panel)
        main_layout.addWidget(self.polygon_panel)

        # Add stretch to push everything to the top
        main_layout.addStretch()

    def create_breaker_panel(self, service_name: str, breaker_id: str) -> QGroupBox:
        """Create a circuit breaker status panel"""
        panel = QGroupBox(f"🔌 {service_name}")
        panel_layout = QGridLayout()
        panel_layout.setSpacing(8)

        # State indicator
        state_label = QLabel("State:")
        state_label.setStyleSheet("font-weight: bold;")
        state_value = QLabel("CLOSED")
        state_value.setObjectName(f"{breaker_id}_state")
        state_value.setStyleSheet("padding: 5px; border-radius: 3px; font-weight: bold;")
        self.update_state_label(state_value, CircuitState.CLOSED)

        panel_layout.addWidget(state_label, 0, 0)
        panel_layout.addWidget(state_value, 0, 1)

        # Failure count with progress bar
        failure_label = QLabel("Failures:")
        failure_count = QLabel("0 / 5")
        failure_count.setObjectName(f"{breaker_id}_failures")

        failure_progress = QProgressBar()
        failure_progress.setObjectName(f"{breaker_id}_failure_progress")
        failure_progress.setRange(0, 5)  # Will be updated with actual threshold
        failure_progress.setValue(0)
        failure_progress.setTextVisible(False)
        failure_progress.setMaximumHeight(15)

        panel_layout.addWidget(failure_label, 1, 0)
        panel_layout.addWidget(failure_count, 1, 1)
        panel_layout.addWidget(failure_progress, 1, 2)

        # Success count
        success_label = QLabel("Successes:")
        success_count = QLabel("0")
        success_count.setObjectName(f"{breaker_id}_successes")

        panel_layout.addWidget(success_label, 2, 0)
        panel_layout.addWidget(success_count, 2, 1, 1, 2)

        # Recovery timeout (shown only when OPEN)
        recovery_label = QLabel("Recovery in:")
        recovery_label.setObjectName(f"{breaker_id}_recovery_label")
        recovery_time = QLabel("--")
        recovery_time.setObjectName(f"{breaker_id}_recovery_time")

        panel_layout.addWidget(recovery_label, 3, 0)
        panel_layout.addWidget(recovery_time, 3, 1, 1, 2)

        # Reset button
        reset_btn = QPushButton("🔄 Reset")
        reset_btn.setObjectName(f"{breaker_id}_reset_btn")
        reset_btn.clicked.connect(lambda: self.reset_breaker(breaker_id))
        reset_btn.setMaximumWidth(100)
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                padding: 5px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton:pressed {
                background-color: #E65100;
            }
        """)

        panel_layout.addWidget(reset_btn, 4, 0, 1, 3, Qt.AlignmentFlag.AlignCenter)

        # Set column stretch
        panel_layout.setColumnStretch(1, 1)
        panel_layout.setColumnStretch(2, 2)

        panel.setLayout(panel_layout)
        return panel

    def update_display(self):
        """Update circuit breaker status display"""
        if not CIRCUIT_BREAKERS_AVAILABLE:
            return

        # Update Tradier breaker
        self.update_breaker_display("tradier", tradier_breaker)

        # Update Polygon breaker
        self.update_breaker_display("polygon", polygon_breaker)

    def update_breaker_display(self, breaker_id: str, breaker):
        """Update display for a specific circuit breaker"""
        try:
            stats = breaker.get_stats()

            # Update state
            state = stats.get("state", CircuitState.CLOSED)
            state_label = self.findChild(QLabel, f"{breaker_id}_state")
            if state_label:
                state_label.setText(state)
                self.update_state_label(state_label, state)

            # Update failure count
            failure_count = stats.get("failure_count", 0)
            failure_threshold = stats.get("failure_threshold", 5)
            failure_label = self.findChild(QLabel, f"{breaker_id}_failures")
            if failure_label:
                failure_label.setText(f"{failure_count} / {failure_threshold}")

            # Update failure progress bar
            failure_progress = self.findChild(QProgressBar, f"{breaker_id}_failure_progress")
            if failure_progress:
                failure_progress.setRange(0, failure_threshold)
                failure_progress.setValue(failure_count)

                # Color code based on threshold
                if failure_count == 0:
                    color = "#4CAF50"  # Green
                elif failure_count < failure_threshold * 0.5:
                    color = "#8BC34A"  # Light green
                elif failure_count < failure_threshold * 0.8:
                    color = "#FF9800"  # Orange
                else:
                    color = "#F44336"  # Red

                failure_progress.setStyleSheet(f"""
                    QProgressBar {{
                        border: 1px solid #555;
                        border-radius: 3px;
                        background-color: #333;
                    }}
                    QProgressBar::chunk {{
                        background-color: {color};
                        border-radius: 2px;
                    }}
                """)

            # Update success count
            success_count = stats.get("success_count", 0)
            success_label = self.findChild(QLabel, f"{breaker_id}_successes")
            if success_label:
                success_label.setText(str(success_count))

            # Update recovery timeout (only if OPEN)
            recovery_label = self.findChild(QLabel, f"{breaker_id}_recovery_label")
            recovery_time_label = self.findChild(QLabel, f"{breaker_id}_recovery_time")

            if state == CircuitState.OPEN:
                last_failure = stats.get("last_failure_time")
                recovery_timeout = stats.get("recovery_timeout", 60.0)

                if last_failure and recovery_label and recovery_time_label:
                    elapsed = (datetime.now() - last_failure).total_seconds()
                    remaining = max(0, recovery_timeout - elapsed)

                    recovery_label.setVisible(True)
                    recovery_time_label.setVisible(True)
                    recovery_time_label.setText(f"{int(remaining)}s")
            else:
                if recovery_label and recovery_time_label:
                    recovery_label.setVisible(False)
                    recovery_time_label.setVisible(False)

            # Track state changes
            self.breaker_states[breaker_id] = state

        except Exception as e:
            print(f"Error updating {breaker_id} breaker display: {e}")

    def update_state_label(self, label: QLabel, state: str):
        """Update state label with appropriate styling"""
        if state == CircuitState.CLOSED:
            label.setStyleSheet("""
                background-color: #4CAF50;
                color: white;
                padding: 5px;
                border-radius: 3px;
                font-weight: bold;
            """)
        elif state == CircuitState.OPEN:
            label.setStyleSheet("""
                background-color: #F44336;
                color: white;
                padding: 5px;
                border-radius: 3px;
                font-weight: bold;
            """)
        elif state == CircuitState.HALF_OPEN:
            label.setStyleSheet("""
                background-color: #FF9800;
                color: white;
                padding: 5px;
                border-radius: 3px;
                font-weight: bold;
            """)

    def reset_breaker(self, breaker_id: str):
        """Reset a circuit breaker manually"""
        try:
            if breaker_id == "tradier":
                import asyncio
                asyncio.create_task(tradier_breaker.reset())
                print(f"✅ {breaker_id.title()} circuit breaker reset")
            elif breaker_id == "polygon":
                import asyncio
                asyncio.create_task(polygon_breaker.reset())
                print(f"✅ {breaker_id.title()} circuit breaker reset")

            # Emit signal
            self.reset_requested.emit(breaker_id)

            # Force immediate update
            self.update_display()

        except Exception as e:
            print(f"❌ Error resetting {breaker_id} circuit breaker: {e}")

# ==============================================================================
# FACTORY FUNCTION
# ==============================================================================

def create_circuit_breaker_monitor(parent=None) -> CircuitBreakerMonitor:
    """
    Factory function to create circuit breaker monitor widget.

    Args:
        parent: Parent widget

    Returns:
        CircuitBreakerMonitor widget instance
    """
    return CircuitBreakerMonitor(parent)

# ==============================================================================
# MAIN EXECUTION (TESTING)
# ==============================================================================

if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # Set dark theme
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(25, 25, 25))
    palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(35, 35, 35))
    app.setPalette(palette)

    # Create and show widget
    monitor = create_circuit_breaker_monitor()
    monitor.setWindowTitle("Circuit Breaker Monitor - Test")
    monitor.resize(400, 350)
    monitor.show()

    sys.exit(app.exec())
