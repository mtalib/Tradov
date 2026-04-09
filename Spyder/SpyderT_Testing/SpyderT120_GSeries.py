#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT120_GSeries.py
Purpose: Coverage tests for SpyderG_GUI — headless-safe modules (G00, G06, G14)

Author: Spyder Dev
Year Created: 2026
Last Updated: 2026-04-03 Time: 00:00:00

Note: Only modules that can be imported without a running QApplication are tested
      here. Heavy Qt widget tests require a real display or 'offscreen' platform.
"""

# ==============================================================================
# BOOTSTRAP — must be set before any PySide6 import
# ==============================================================================
import os
import sys
import types
import logging
import unittest
from unittest.mock import MagicMock

logging.disable(logging.CRITICAL)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _ensure_mod(key):
    parts = key.split(".")
    for i in range(1, len(parts) + 1):
        anc = ".".join(parts[:i])
        if anc not in sys.modules:
            sys.modules[anc] = types.ModuleType(anc)
    return sys.modules[key]


# ---- Spyder utility stubs ---------------------------------------------------
class _Logger:
    @staticmethod
    def get_logger(name=""):
        return logging.getLogger(name)

for _k in ("Spyder.SpyderU_Utilities.SpyderU01_Logger",
           "SpyderU_Utilities.SpyderU01_Logger"):
    _m = _ensure_mod(_k)
    _m.SpyderLogger = _Logger

for _k in ("Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler",
           "SpyderU_Utilities.SpyderU02_ErrorHandler"):
    _m = _ensure_mod(_k)
    _m.SpyderErrorHandler = type("SpyderErrorHandler", (), {})

# ---- G-series package pre-stub ----------------------------------------------
_g_path = os.path.join(_ROOT, "Spyder", "SpyderG_GUI")
_g_pkg = sys.modules.setdefault("Spyder.SpyderG_GUI",
                                  types.ModuleType("Spyder.SpyderG_GUI"))
_g_pkg.__path__ = [_g_path]
_g_pkg.__package__ = "Spyder.SpyderG_GUI"
_g_pkg.__file__ = os.path.join(_g_path, "__init__.py")


# ==============================================================================
# G00 — ApplicationManager (non-widget enums + config)
# ==============================================================================
from Spyder.SpyderG_GUI.SpyderG00_ApplicationManager import (
    DisplayMode,
    AppState,
    ApplicationManager,
)


class TestG00DisplayModeEnum(unittest.TestCase):
    def test_members(self):
        for name in ("GUI", "HEADLESS", "OFFSCREEN"):
            self.assertTrue(hasattr(DisplayMode, name), f"Missing: {name}")


class TestG00AppStateEnum(unittest.TestCase):
    def test_members(self):
        for name in ("NOT_INITIALIZED", "INITIALIZING", "RUNNING",
                     "SHUTTING_DOWN", "SHUTDOWN"):
            self.assertTrue(hasattr(AppState, name), f"Missing: {name}")


class TestG00ApplicationManagerClass(unittest.TestCase):
    def test_class_callable(self):
        self.assertTrue(callable(ApplicationManager))

    def test_has_signals(self):
        # ApplicationManager declares class-level Qt signals
        self.assertTrue(hasattr(ApplicationManager, "app_initialized")
                        or hasattr(ApplicationManager, "app_shutdown"))


# ==============================================================================
# G06 — DashboardData (non-widget data model)
# ==============================================================================
try:
    from Spyder.SpyderG_GUI.SpyderG06_DashboardData import DashboardData
    _g06_available = True
except Exception:
    _g06_available = False


@unittest.skipUnless(_g06_available, "G06 import failed (likely missing Qt display)")
class TestG06DashboardData(unittest.TestCase):
    def test_class_callable(self):
        self.assertTrue(callable(DashboardData))


# ==============================================================================
# G14 — Dashboard (legacy stub — minimal class)
# ==============================================================================
try:
    from Spyder.SpyderG_GUI.SpyderG14_Dashboard import Dashboard
    _g14_available = True
except Exception:
    _g14_available = False


@unittest.skipUnless(_g14_available, "G14 import failed (likely missing Qt display)")
class TestG14DashboardClass(unittest.TestCase):
    def test_class_callable(self):
        self.assertTrue(callable(Dashboard))


# ==============================================================================
if __name__ == "__main__":
    unittest.main()
