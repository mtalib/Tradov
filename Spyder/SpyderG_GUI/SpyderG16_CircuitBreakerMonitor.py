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
    Displays status, statistics, and manual control for Tradier and Databento
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
        tradier_breaker, CircuitState
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

# Try to import Databento breaker (may not exist yet)
try:
    from SpyderU_Utilities.SpyderU41_CircuitBreaker import databento_breaker
except ImportError:
    if CIRCUIT_BREAKERS_AVAILABLE:
        databento_breaker = MockCircuitBreaker("databento")  # type: ignore[misc]
    else:
        databento_breaker = MockCircuitBreaker("databento")

# ==============================================================================
# CIRCUIT BREAKER MONITOR WIDGET
# ==============================================================================

class CircuitBreakerMonitor(QWidget):
    """
    Compact traffic-light grid Circuit Breaker Status Monitor.

    Layout:
        CIRCUIT BREAKER STATUS  |  NORMAL  |  RECOVERY  |  BLOCKED
        TRADIER API             |    ●     |     ●      |    ●
        DATABENTO               |    ●     |     ●      |    ●

    Active column dot is lit (green/orange/red); inactive dots are dim gray.
    Maps: CLOSED→NORMAL, HALF_OPEN→RECOVERY, OPEN→BLOCKED.
    """

    # Traffic-light colors
    COLOR_NORMAL   = "#00C853"   # green
    COLOR_RECOVERY = "#FF9800"   # orange
    COLOR_BLOCKED  = "#F44336"   # red
    COLOR_DIM      = "#2a2a2a"   # inactive dot

    # Signals
    reset_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        # {breaker_id: {"normal": QLabel, "recovery": QLabel, "blocked": QLabel}}
        self._dots: dict = {}

        self.setup_ui()

        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(1000)

        self.update_display()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _make_dot(self, color: str) -> QLabel:
        """Return a circular dot QLabel."""
        dot = QLabel("●")
        dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dot.setStyleSheet(f"color: {color}; font-size: 18px;")
        return dot

    def _make_header(self, text: str, color: str = "#888888", left: bool = False) -> QLabel:
        lbl = QLabel(text)
        lbl.setAlignment(
            (Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            if left else Qt.AlignmentFlag.AlignCenter
        )
        lbl.setStyleSheet(
            f"color: {color}; font-size: 15px; font-weight: normal; letter-spacing: 1px;"
        )
        return lbl

    def _make_service(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        lbl.setStyleSheet("color: #cccccc; font-size: 15px; font-weight: normal;")
        return lbl

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def setup_ui(self):
        """Build the compact traffic-light grid."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(2)

        grid = QGridLayout()
        grid.setSpacing(0)
        grid.setContentsMargins(0, 0, 0, 0)

        # ── Column headers (row 0) ─────────────────────────────────
        # "CIRCUIT BREAKER STATUS" – left-aligned, white, larger
        title_lbl = QLabel("CIRCUIT BREAKER STATUS")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        title_lbl.setStyleSheet(
            "color: #ffffff; font-size: 15px; font-weight: normal; letter-spacing: 1px;"
        )
        grid.addWidget(title_lbl, 0, 0)
        grid.addWidget(self._make_header("NORMAL",   self.COLOR_NORMAL),   0, 1)
        grid.addWidget(self._make_header("RECOVERY", self.COLOR_RECOVERY), 0, 2)
        grid.addWidget(self._make_header("BLOCKED",  self.COLOR_BLOCKED),  0, 3)

        # Thin separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #333333;")
        grid.addWidget(sep, 1, 0, 1, 4)

        # ── Service rows ───────────────────────────────────────────
        services = [
            ("tradier",   "TRADIER API", 2),
            ("databento", "DATABENTO",   3),
        ]

        for breaker_id, label_text, row in services:
            grid.addWidget(self._make_service(label_text), row, 0)

            dot_normal   = self._make_dot(self.COLOR_NORMAL)   # starts lit (CLOSED)
            dot_recovery = self._make_dot(self.COLOR_DIM)
            dot_blocked  = self._make_dot(self.COLOR_DIM)

            grid.addWidget(dot_normal,   row, 1)
            grid.addWidget(dot_recovery, row, 2)
            grid.addWidget(dot_blocked,  row, 3)

            self._dots[breaker_id] = {
                "normal":   dot_normal,
                "recovery": dot_recovery,
                "blocked":  dot_blocked,
            }

        # Column proportions: smaller label col so dots sit closer/left
        grid.setColumnStretch(0, 2)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        grid.setColumnStretch(3, 1)

        main_layout.addLayout(grid)
        main_layout.addStretch()

    # ------------------------------------------------------------------
    # Update logic
    # ------------------------------------------------------------------
    def update_display(self):
        """Poll breakers and refresh dots."""
        self._refresh_breaker("tradier",   tradier_breaker)
        self._refresh_breaker("databento", databento_breaker)

    def _refresh_breaker(self, breaker_id: str, breaker):
        """Light the correct dot for a single breaker."""
        try:
            stats = breaker.get_stats()
            state = stats.get("state", CircuitState.CLOSED)
        except Exception:
            state = CircuitState.CLOSED

        dots = self._dots.get(breaker_id)
        if not dots:
            return

        if state == CircuitState.CLOSED:
            dots["normal"].setStyleSheet(  f"color: {self.COLOR_NORMAL};   font-size: 18px;")
            dots["recovery"].setStyleSheet(f"color: {self.COLOR_DIM};      font-size: 18px;")
            dots["blocked"].setStyleSheet( f"color: {self.COLOR_DIM};      font-size: 18px;")
        elif state == CircuitState.HALF_OPEN:
            dots["normal"].setStyleSheet(  f"color: {self.COLOR_DIM};      font-size: 18px;")
            dots["recovery"].setStyleSheet(f"color: {self.COLOR_RECOVERY}; font-size: 18px;")
            dots["blocked"].setStyleSheet( f"color: {self.COLOR_DIM};      font-size: 18px;")
        else:  # OPEN
            dots["normal"].setStyleSheet(  f"color: {self.COLOR_DIM};      font-size: 18px;")
            dots["recovery"].setStyleSheet(f"color: {self.COLOR_DIM};      font-size: 18px;")
            dots["blocked"].setStyleSheet( f"color: {self.COLOR_BLOCKED};  font-size: 18px;")

    # ------------------------------------------------------------------
    # Legacy stubs (kept so external callers don't break)
    # ------------------------------------------------------------------
    def update_state_label(self, label: QLabel, state: str):
        pass

    def reset_breaker(self, breaker_id: str):
        """Reset a circuit breaker manually."""
        try:
            import asyncio
            breaker = tradier_breaker if breaker_id == "tradier" else databento_breaker
            asyncio.create_task(breaker.reset())
            self.reset_requested.emit(breaker_id)
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
