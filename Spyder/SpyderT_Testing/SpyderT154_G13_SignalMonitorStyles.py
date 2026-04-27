#!/usr/bin/env python3
"""Regression tests for G13 Signal Monitor styling integrity.

These tests guard against malformed Qt stylesheet syntax in the extracted
Signal Monitor widgets (for example, accidental doubled braces) that can
cause fallback rendering and visual degradation.
"""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import Spyder.SpyderG_GUI.SpyderG13_EnhancedWidgets as g13

try:
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except ImportError:  # pragma: no cover
    HAS_QT = False


@unittest.skipUnless(HAS_QT, "PySide6 not available")
class TestSignalMonitorStyles(unittest.TestCase):
    """Headless GUI regressions for Signal Monitor style safety."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_traffic_light_button_stylesheet_uses_valid_qss_braces(self):
        """TrafficLightButton must use valid QSS selector braces."""
        button = g13.TrafficLightButton("TEST")
        style = button.styleSheet()

        self.assertIn("QPushButton {", style)
        self.assertIn("QPushButton:hover {", style)
        self.assertIn("QToolTip {", style)

        self.assertNotIn("QPushButton {{", style)
        self.assertNotIn("QPushButton:hover {{", style)
        self.assertNotIn("QToolTip {{", style)

        button.close()

    def test_signal_monitor_panel_buttons_have_non_empty_stylesheet(self):
        """SignalMonitorPanel buttons should carry explicit custom styling."""
        panel = g13.SignalMonitorPanel()
        style = panel.vix_button.styleSheet()

        self.assertTrue(style.strip())
        self.assertIn("padding-left: 25px;", style)
        self.assertIn("font-size: 11px;", style)

        panel.close()


if __name__ == "__main__":
    unittest.main()
