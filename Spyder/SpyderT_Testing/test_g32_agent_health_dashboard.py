#!/usr/bin/env python3
"""
Tests for SpyderG32_AgentHealthDashboard

Covers: HAS_QT guard import safety, module-level constants,
status colour mapping, and headless-environment graceful degradation.
GUI widget construction tests are skipped when PySide6 is unavailable.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import Spyder.SpyderG_GUI.SpyderG32_AgentHealthDashboard as _mod


class TestModuleImportSafety(unittest.TestCase):
    def test_module_imports_without_pyside6(self):
        """The module must be importable even in a headless / no-Qt environment."""
        self.assertIsNotNone(_mod)

    def test_has_qt_flag_is_bool(self):
        self.assertIsInstance(_mod.HAS_QT, bool)

    def test_constants_present(self):
        self.assertIsInstance(_mod._REFRESH_INTERVAL_MS, int)
        self.assertGreater(_mod._REFRESH_INTERVAL_MS, 0)
        self.assertIsInstance(_mod._TABLE_COLS, list)
        self.assertGreater(len(_mod._TABLE_COLS), 0)

    def test_status_colours_map(self):
        colours = _mod._STATUS_COLOURS
        for status in ("UP", "DEGRADED", "DOWN", "UNKNOWN"):
            self.assertIn(status, colours)
            self.assertTrue(colours[status].startswith("#"))


class TestAgentHealthDashboardHeadless(unittest.TestCase):
    """Tests that run regardless of Qt availability."""

    def test_class_is_accessible(self):
        self.assertTrue(hasattr(_mod, "AgentHealthDashboard"))

    @unittest.skipIf(_mod.HAS_QT, "Skipped in Qt-enabled environment (GUI test)")
    def test_instantiation_raises_without_qt(self):
        """Without PySide6 the class should raise ImportError or RuntimeError."""
        with self.assertRaises((ImportError, RuntimeError, Exception)):
            _mod.AgentHealthDashboard()


@unittest.skipUnless(_mod.HAS_QT, "PySide6 not available")
class TestAgentHealthDashboardWithQt(unittest.TestCase):
    """Integration tests — only run when PySide6 is present."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_widget_constructs(self):
        widget = _mod.AgentHealthDashboard()
        self.assertIsNotNone(widget)

    def test_refresh_does_not_raise(self):
        widget = _mod.AgentHealthDashboard()
        widget.refresh()  # should silently degrade when registry unavailable

    def test_widget_has_expected_columns(self):
        widget = _mod.AgentHealthDashboard()
        # Table column count should match _TABLE_COLS
        self.assertEqual(widget.table.columnCount(), len(_mod._TABLE_COLS))


if __name__ == "__main__":
    unittest.main()
