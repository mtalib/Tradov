#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT126_QSeries.py
Purpose: Coverage tests for SpyderQ_Scripts — key modules (Q14, Q24, Q25)

Author: Spyder Dev
Year Created: 2026
Last Updated: 2026-04-03 Time: 00:00:00
"""

# ==============================================================================
# BOOTSTRAP
# ==============================================================================
import os
import sys
import types
import logging
import unittest
from unittest.mock import MagicMock

logging.disable(logging.CRITICAL)

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

# ---- psutil stub ------------------------------------------------------------
if "psutil" not in sys.modules:
    _psutil = types.ModuleType("psutil")
    _psutil.cpu_percent = MagicMock(return_value=10.0)
    _psutil.virtual_memory = MagicMock(return_value=MagicMock(
        percent=50.0, total=8*1024**3, available=4*1024**3))
    _psutil.disk_usage = MagicMock(return_value=MagicMock(
        percent=50.0, total=100, used=50, free=50))
    _psutil.Process = MagicMock(return_value=MagicMock(
        memory_info=MagicMock(return_value=MagicMock(rss=100*1024**2))))
    _psutil.NoSuchProcess = type("NoSuchProcess", (Exception,), {})
    sys.modules["psutil"] = _psutil

# ---- Spyder root package: set __path__ so package hierarchy works ----------
_spyder_path = os.path.join(_ROOT, "Spyder")
_spyder_pkg = sys.modules.setdefault("Spyder", types.ModuleType("Spyder"))
_spyder_pkg.__path__ = [_spyder_path]
_spyder_pkg.__package__ = "Spyder"

# ---- Q-series package pre-stub (needed since Q modules may all be in same pkg)
_q_path = os.path.join(_ROOT, "Spyder", "SpyderQ_Scripts")
_q_pkg = sys.modules.setdefault("Spyder.SpyderQ_Scripts",
                                  types.ModuleType("Spyder.SpyderQ_Scripts"))
_q_pkg.__path__ = [_q_path]
_q_pkg.__package__ = "Spyder.SpyderQ_Scripts"
_q_pkg.__file__ = os.path.join(_q_path, "__init__.py")

# ---- Bare-name stubs for Q14's module-level try/except imports ---------------
# Q14 tries these bare imports at module level inside try/except ImportError.
# Stubbing them prevents Python from loading real files (which can cascade to
# SpyderB_Broker/__init__.py and trigger a TypeError on TradierClient|None).
_ensure_mod("SpyderA_Core.SpyderA06_MasterController")
_ensure_mod("SpyderI_Integration.SpyderI01_IntegrationHub")
_ensure_mod("SpyderG_GUI.SpyderG05_TradingDashboard")
_ensure_mod("SpyderG_GUI.SpyderG01_MainWindow")
_ensure_mod("SpyderG_GUI.SpyderG02_GUIEntry")


# ==============================================================================
# Q14 — MainLauncher
# ==============================================================================
from Spyder.SpyderQ_Scripts.SpyderQ14_MainLauncher import (
    SystemState,
    SpyderLauncher,
)


class TestQ14SystemState(unittest.TestCase):
    def test_is_class(self):
        self.assertTrue(callable(SystemState))

    def test_fields_exist(self):
        for name in ("STARTING", "RUNNING", "STOPPED", "ERROR"):
            self.assertTrue(hasattr(SystemState, name), f"SystemState missing: {name}")


class TestQ14SpyderLauncherClass(unittest.TestCase):
    def test_exists(self):
        self.assertTrue(callable(SpyderLauncher))


# ==============================================================================
# Q24 — ProductionWatchdog
# ==============================================================================
from Spyder.SpyderQ_Scripts.SpyderQ24_ProductionWatchdog import (
    WatchdogState,
    ProductionWatchdog,
)


class TestQ24WatchdogStateEnum(unittest.TestCase):
    def test_members(self):
        for name in ("IDLE", "MONITORING", "RECOVERING", "STOPPED"):
            self.assertTrue(hasattr(WatchdogState, name), f"Missing: {name}")


class TestQ24ProductionWatchdogClass(unittest.TestCase):
    def test_exists(self):
        self.assertTrue(callable(ProductionWatchdog))


# ==============================================================================
# Q25 — SystemMonitor
# ==============================================================================
from Spyder.SpyderQ_Scripts.SpyderQ25_SystemMonitor import (
    SystemSnapshot,
    SystemMonitor,
)


class TestQ25SystemSnapshot(unittest.TestCase):
    def test_is_dataclass(self):
        import dataclasses
        self.assertTrue(dataclasses.is_dataclass(SystemSnapshot))


class TestQ25SystemMonitorClass(unittest.TestCase):
    def test_exists(self):
        self.assertTrue(callable(SystemMonitor))


# ==============================================================================
if __name__ == "__main__":
    unittest.main()
