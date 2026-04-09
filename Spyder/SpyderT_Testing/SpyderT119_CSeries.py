#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT119_CSeries.py
Purpose: Coverage tests for SpyderC_MarketData — key modules (C00, C01, C06, C16)

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

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


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
    _m.TradingError = type("TradingError", (Exception,), {})
    _m.DataValidationError = type("DataValidationError", (Exception,), {})

for _k in ("Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils",
           "SpyderU_Utilities.SpyderU03_DateTimeUtils"):
    _m = _ensure_mod(_k)
    _m.DateTimeUtils = MagicMock()

for _k in ("Spyder.SpyderA_Core.SpyderA05_EventManager",
           "SpyderA_Core.SpyderA05_EventManager"):
    from enum import Enum as _Enum
    _m = _ensure_mod(_k)
    _m.EventType = _Enum("EventType", {"MARKET": "market", "SYSTEM": "system",
                                        "TRADE": "trade", "RISK": "risk"})
    _m.Event = type("Event", (), {"__init__": lambda self, *a, **k: None})
    _m.EventManager = type("EventManager", (), {"subscribe": lambda *a, **k: None,
                                                  "publish": lambda *a, **k: None})
    _m.get_event_manager = lambda: _m.EventManager()

for _k in ("Spyder.SpyderU_Utilities.SpyderU44_ShutdownCoordinator",
           "SpyderU_Utilities.SpyderU44_ShutdownCoordinator"):
    _m = _ensure_mod(_k)
    _m.get_shutdown_coordinator = MagicMock(return_value=MagicMock())

# ---- C16 MarketDataCache stub (C01 imports it) ------------------------------
_c16_key = "Spyder.SpyderC_MarketData.SpyderC16_MarketDataCache"
if _c16_key not in sys.modules:
    from enum import Enum as _Enum2
    _c16 = types.ModuleType(_c16_key)
    _c16.DataGranularity = _Enum2("DataGranularity",
                                   {"TICK": "tick", "SECOND": "second", "MINUTE": "minute",
                                    "HOUR": "hour", "DAY": "day"})
    _c16.MarketDataCache = type("MarketDataCache", (), {"__init__": lambda self, *a, **k: None})
    sys.modules[_c16_key] = _c16

# ---- C06 DataValidator stub (C01 imports it) --------------------------------
_c06_key = "Spyder.SpyderC_MarketData.SpyderC06_DataValidator"
if _c06_key not in sys.modules:
    _c06_stub = types.ModuleType(_c06_key)
    _c06_stub.DataValidator = type("DataValidator", (), {"__init__": lambda self, *a, **k: None})
    sys.modules[_c06_key] = _c06_stub

# ---- C series package pre-stub ----------------------------------------------
_c_path = os.path.join(_ROOT, "Spyder", "SpyderC_MarketData")
_c_pkg = sys.modules.setdefault("Spyder.SpyderC_MarketData",
                                  types.ModuleType("Spyder.SpyderC_MarketData"))
_c_pkg.__path__ = [_c_path]
_c_pkg.__package__ = "Spyder.SpyderC_MarketData"
_c_pkg.__file__ = os.path.join(_c_path, "__init__.py")


# ==============================================================================
# C00 — MarketDataProtocol
# ==============================================================================
from Spyder.SpyderC_MarketData.SpyderC00_MarketDataProtocol import (
    NormalizedQuote,
    NormalizedTrade,
    OptionsDataProvider,
    MarketDataStreamProvider,
)


class TestC00NormalizedQuote(unittest.TestCase):
    def test_fields(self):
        import dataclasses
        fields = {f.name for f in dataclasses.fields(NormalizedQuote)}
        for name in ("symbol", "bid", "ask"):
            self.assertIn(name, fields)

    def test_instantiation(self):
        q = NormalizedQuote(symbol="SPY", bid=500.0, ask=500.05)
        self.assertEqual(q.symbol, "SPY")
        self.assertAlmostEqual(q.bid, 500.0)


class TestC00NormalizedTrade(unittest.TestCase):
    def test_fields(self):
        import dataclasses
        fields = {f.name for f in dataclasses.fields(NormalizedTrade)}
        for name in ("symbol", "price", "size"):
            self.assertIn(name, fields)


class TestC00Protocols(unittest.TestCase):
    def test_options_provider_is_protocol(self):
        from typing import runtime_checkable
        from typing import Protocol
        # Just ensure the class exists and can be referenced
        self.assertTrue(callable(OptionsDataProvider))

    def test_stream_provider_is_protocol(self):
        self.assertTrue(callable(MarketDataStreamProvider))


# ==============================================================================
# C01 — DataFeed (enums + dataclasses only; no constructor, avoids I/O)
# ==============================================================================
from Spyder.SpyderC_MarketData.SpyderC01_DataFeed import (
    DataFeedStatus,
    DataSource,
    MarketTick,
    DataFeedConfig,
)


class TestC01DataFeedStatusEnum(unittest.TestCase):
    def test_members(self):
        for name in ("CONNECTED", "DISCONNECTED", "ERROR", "DEGRADED"):
            self.assertTrue(hasattr(DataFeedStatus, name), f"Missing: {name}")


class TestC01DataSourceEnum(unittest.TestCase):
    def test_members(self):
        for name in ("DATABENTO", "MASSIVE", "CACHE"):
            self.assertTrue(hasattr(DataSource, name), f"Missing: {name}")


class TestC01MarketTick(unittest.TestCase):
    def test_fields(self):
        import dataclasses
        fields = {f.name for f in dataclasses.fields(MarketTick)}
        for name in ("symbol", "bid", "ask", "price", "volume"):
            self.assertIn(name, fields)


class TestC01DataFeedConfig(unittest.TestCase):
    def test_fields(self):
        import dataclasses
        fields = {f.name for f in dataclasses.fields(DataFeedConfig)}
        for name in ("provider", "cache_enabled", "validation_enabled"):
            self.assertIn(name, fields)


# ==============================================================================
# C06 — DataValidator (enums + dataclasses)
# ==============================================================================
# Force-load real C06 (may have been stubbed above)
import importlib.util as _ilu

_c06_file = os.path.join(_c_path, "SpyderC06_DataValidator.py")
_c06_spec = _ilu.spec_from_file_location(
    "Spyder.SpyderC_MarketData.SpyderC06_DataValidator", _c06_file)
_c06_real = _ilu.module_from_spec(_c06_spec)
_c06_real.__package__ = "Spyder.SpyderC_MarketData"
sys.modules["Spyder.SpyderC_MarketData.SpyderC06_DataValidator"] = _c06_real
_c06_spec.loader.exec_module(_c06_real)

from Spyder.SpyderC_MarketData.SpyderC06_DataValidator import (
    DataQuality,
    ValidationStatus,
    AnomalyType,
    DataType,
    ValidationResult,
)


class TestC06DataQualityEnum(unittest.TestCase):
    def test_members(self):
        for name in ("EXCELLENT", "GOOD", "FAIR", "POOR", "INVALID"):
            self.assertTrue(hasattr(DataQuality, name), f"Missing: {name}")


class TestC06ValidationStatusEnum(unittest.TestCase):
    def test_members(self):
        for name in ("VALID", "WARNING", "ERROR", "REJECTED"):
            self.assertTrue(hasattr(ValidationStatus, name), f"Missing: {name}")


class TestC06AnomalyTypeEnum(unittest.TestCase):
    def test_members(self):
        self.assertGreater(len(list(AnomalyType)), 0)


class TestC06ValidationResult(unittest.TestCase):
    def test_exists(self):
        import dataclasses
        self.assertTrue(dataclasses.is_dataclass(ValidationResult))


# ==============================================================================
# C16 — MarketDataCache (force-load real module)
# ==============================================================================
_c16_file = os.path.join(_c_path, "SpyderC16_MarketDataCache.py")
_c16_spec = _ilu.spec_from_file_location(
    "Spyder.SpyderC_MarketData.SpyderC16_MarketDataCache", _c16_file)
_c16_real = _ilu.module_from_spec(_c16_spec)
_c16_real.__package__ = "Spyder.SpyderC_MarketData"
sys.modules["Spyder.SpyderC_MarketData.SpyderC16_MarketDataCache"] = _c16_real
_c16_spec.loader.exec_module(_c16_real)

from Spyder.SpyderC_MarketData.SpyderC16_MarketDataCache import (
    DataGranularity,
    MarketDataCache,
)


class TestC16DataGranularityEnum(unittest.TestCase):
    def test_members(self):
        for name in ("TICK", "SECOND", "MINUTE", "HOUR", "DAILY"):
            self.assertTrue(hasattr(DataGranularity, name), f"Missing: {name}")


class TestC16MarketDataCacheClass(unittest.TestCase):
    def test_exists(self):
        self.assertTrue(callable(MarketDataCache))


# ==============================================================================
if __name__ == "__main__":
    unittest.main()
