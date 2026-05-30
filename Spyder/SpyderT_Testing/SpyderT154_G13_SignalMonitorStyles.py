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
    from PySide6.QtWidgets import QApplication, QVBoxLayout

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
        style = panel.ai_button.styleSheet()

        self.assertTrue(style.strip())
        self.assertIn("padding: 0px 0px 0px 22px;", style)
        self.assertIn("font-size: 12px;", style)
        self.assertEqual(panel.ai_button.minimumWidth(), 0)
        self.assertEqual(panel.ai_button.height(), 24)

        panel.close()

    def test_signal_monitor_panel_keeps_only_decision_state_buttons(self):
        """SignalMonitorPanel should expose only the consolidated decision-state pills."""
        panel = g13.SignalMonitorPanel()
        labels = sorted(button.text() for button in panel.findChildren(g13.TrafficLightButton))

        self.assertEqual(
            labels,
            sorted([
                "AI DECISION",
                "DIVERGENCE",
                "HMM",
                "RISK TRIGGERS",
                "RSI CONFLUENCE",
            ]),
        )
        self.assertEqual(panel.hmm_button.status, "yellow")

        panel.close()

    def test_signal_monitor_panel_uses_single_column_priority_stack(self):
        """SignalMonitorPanel should stack the five buttons in a single priority column."""
        panel = g13.SignalMonitorPanel()
        layout = panel.layout()

        self.assertIsInstance(layout, QVBoxLayout)
        self.assertEqual(panel.minimumHeight(), 130)
        self.assertEqual(layout.count(), 5)
        self.assertEqual(
            [layout.itemAt(index).widget().text() for index in range(layout.count())],
            [
                "AI DECISION",
                "RISK TRIGGERS",
                "HMM",
                "RSI CONFLUENCE",
                "DIVERGENCE",
            ],
        )

        panel.close()


if __name__ == "__main__":
    unittest.main()
