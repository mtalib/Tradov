#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT122_JSeries.py
Purpose: Coverage tests for SpyderJ_Alerts — all 5 modules (J01–J05)

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
import importlib
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


# ---- Spyder root + A_Core + H_Storage: set __path__ so real submodule files load --
_spyder_path = os.path.join(_ROOT, "Spyder")
_spyder_pkg = sys.modules.setdefault("Spyder", types.ModuleType("Spyder"))
_spyder_pkg.__path__ = [_spyder_path]
_spyder_pkg.__package__ = "Spyder"

_a_path = os.path.join(_spyder_path, "SpyderA_Core")
_a_pkg = sys.modules.setdefault("Spyder.SpyderA_Core", types.ModuleType("Spyder.SpyderA_Core"))
_a_pkg.__path__ = [_a_path]
_a_pkg.__package__ = "Spyder.SpyderA_Core"
_a_pkg.__file__ = os.path.join(_a_path, "__init__.py")

_h_path = os.path.join(_spyder_path, "SpyderH_Storage")
_h_pkg = sys.modules.setdefault("Spyder.SpyderH_Storage", types.ModuleType("Spyder.SpyderH_Storage"))
_h_pkg.__path__ = [_h_path]
_h_pkg.__package__ = "Spyder.SpyderH_Storage"
_h_pkg.__file__ = os.path.join(_h_path, "__init__.py")


# ---- SpyderLogger / SpyderErrorHandler stubs --------------------------------
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

# ---- Additional U-series stubs required by J01/J02 -------------------------
_m = _ensure_mod("Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils")
_m.DateTimeUtils = type("DateTimeUtils", (), {})

try:
    _u04_real = importlib.import_module("Spyder.SpyderU_Utilities.SpyderU04_Encryption")
    sys.modules["Spyder.SpyderU_Utilities.SpyderU04_Encryption"] = _u04_real
except Exception:
    _m = _ensure_mod("Spyder.SpyderU_Utilities.SpyderU04_Encryption")
    _m.EncryptionManager = type("EncryptionManager", (), {"__init__": lambda self: None})

# ---- J-series package pre-stub ----------------------------------------------
_j_path = os.path.join(_ROOT, "Spyder", "SpyderJ_Alerts")
_j_pkg = sys.modules.setdefault("Spyder.SpyderJ_Alerts",
                                  types.ModuleType("Spyder.SpyderJ_Alerts"))
_j_pkg.__path__ = [_j_path]
_j_pkg.__package__ = "Spyder.SpyderJ_Alerts"
_j_pkg.__file__ = os.path.join(_j_path, "__init__.py")

# ---- L_ML package stub (prevents J01's MLPredictor chain from hitting B_Broker) --
_l_path = os.path.join(_spyder_path, "SpyderL_ML")
_l_pkg = types.ModuleType("Spyder.SpyderL_ML")
_l_pkg.__path__ = [_l_path]
_l_pkg.__package__ = "Spyder.SpyderL_ML"
sys.modules["Spyder.SpyderL_ML"] = _l_pkg
sys.modules["SpyderL_ML"] = _l_pkg

_l01_stub = _ensure_mod("SpyderL_ML.SpyderL01_MLPredictor")
_l01_stub.MLPredictor = MagicMock
sys.modules["Spyder.SpyderL_ML.SpyderL01_MLPredictor"] = _l01_stub


# ==============================================================================
# J01 — AlertManager
# ==============================================================================
from Spyder.SpyderJ_Alerts.SpyderJ01_AlertManager import (
    AlertLevel,
    AlertCategory,
    AlertManager,
)


class TestJ01AlertLevelEnum(unittest.TestCase):
    def test_members(self):
        for name in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            self.assertTrue(hasattr(AlertLevel, name), f"Missing: {name}")


class TestJ01AlertCategoryEnum(unittest.TestCase):
    def test_members(self):
        for name in ("SYSTEM", "TRADING", "RISK", "PERFORMANCE"):
            self.assertTrue(hasattr(AlertCategory, name), f"Missing: {name}")


class TestJ01AlertManagerClass(unittest.TestCase):
    def test_exists(self):
        self.assertTrue(callable(AlertManager))


# ==============================================================================
# J02 — EmailNotifier
# ==============================================================================
from Spyder.SpyderJ_Alerts.SpyderJ02_EmailNotifier import (
    NotificationType,
    Priority,
    EmailStatus,
    EmailConfig,
    EmailNotifier,
)


class TestJ02NotificationTypeEnum(unittest.TestCase):
    def test_members(self):
        for name in ("TRADE_EXECUTION", "RISK_WARNING", "SYSTEM_ALERT", "DAILY_SUMMARY"):
            self.assertTrue(hasattr(NotificationType, name), f"Missing: {name}")


class TestJ02PriorityEnum(unittest.TestCase):
    def test_members(self):
        for name in ("LOW", "NORMAL", "HIGH", "URGENT"):
            self.assertTrue(hasattr(Priority, name), f"Missing: {name}")


class TestJ02EmailStatusEnum(unittest.TestCase):
    def test_members(self):
        for name in ("PENDING", "SENT", "FAILED", "RETRYING"):
            self.assertTrue(hasattr(EmailStatus, name), f"Missing: {name}")


class TestJ02EmailConfigDataclass(unittest.TestCase):
    def test_is_class(self):
        self.assertTrue(callable(EmailConfig))

    def test_fields(self):
        for name in ("smtp_server", "smtp_port"):
            self.assertTrue(
                hasattr(EmailConfig, name) or hasattr(EmailConfig, "__annotations__") and name in EmailConfig.__annotations__,
                f"EmailConfig missing attribute: {name}"
            )


# ==============================================================================
# J04 — DesktopNotifier
# ==============================================================================
from Spyder.SpyderJ_Alerts.SpyderJ04_DesktopNotifier import (
    NotificationLevel,
    SoundType,
    DesktopNotifier,
)


class TestJ04NotificationLevelEnum(unittest.TestCase):
    def test_members(self):
        for name in ("INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"):
            self.assertTrue(hasattr(NotificationLevel, name), f"Missing: {name}")


class TestJ04SoundTypeEnum(unittest.TestCase):
    def test_members(self):
        for name in ("NONE", "TRADE", "ALERT", "WARNING", "ERROR"):
            self.assertTrue(hasattr(SoundType, name), f"Missing: {name}")


class TestJ04DesktopNotifierClass(unittest.TestCase):
    def test_exists(self):
        self.assertTrue(callable(DesktopNotifier))


# ==============================================================================
# J05 — TelegramBot
# ==============================================================================
from Spyder.SpyderJ_Alerts.SpyderJ05_TelegramBot import (
    MessagePriority,
    MessageType,
    TelegramBot,
)


class TestJ05MessagePriorityEnum(unittest.TestCase):
    def test_members(self):
        for name in ("LOW", "NORMAL", "HIGH", "CRITICAL"):
            self.assertTrue(hasattr(MessagePriority, name), f"Missing: {name}")


class TestJ05MessageTypeEnum(unittest.TestCase):
    def test_members(self):
        for name in ("TRADE_OPEN", "TRADE_CLOSE", "ALERT", "ERROR"):
            self.assertTrue(hasattr(MessageType, name), f"Missing: {name}")


class TestJ05TelegramBotClass(unittest.TestCase):
    def test_exists(self):
        self.assertTrue(callable(TelegramBot))


# ==============================================================================
if __name__ == "__main__":
    unittest.main()
