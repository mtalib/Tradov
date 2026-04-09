#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT124_MSeries.py
Purpose: Coverage tests for SpyderM_Monitoring — key modules (M01, M04, M06)

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
    _psutil.cpu_count = MagicMock(return_value=4)
    _psutil.virtual_memory = MagicMock(return_value=MagicMock(
        percent=50.0, total=8*1024**3, available=4*1024**3, used=4*1024**3))
    _psutil.disk_usage = MagicMock(return_value=MagicMock(
        percent=50.0, total=100, used=50, free=50))
    _psutil.net_io_counters = MagicMock(return_value=MagicMock(bytes_sent=0, bytes_recv=0))
    _psutil.Process = MagicMock(return_value=MagicMock(
        memory_info=MagicMock(return_value=MagicMock(rss=100*1024**2, vms=200*1024**2)),
        cpu_percent=MagicMock(return_value=5.0)))
    _psutil.NoSuchProcess = type("NoSuchProcess", (Exception,), {})
    _psutil.AccessDenied = type("AccessDenied", (Exception,), {})
    sys.modules["psutil"] = _psutil

# ---- sklearn / statsmodels stubs (M06 imports these) -----------------------
import types as _types

for _sk_key in ("sklearn", "sklearn.preprocessing", "sklearn.ensemble"):
    _m = _ensure_mod(_sk_key)
    _m.StandardScaler = MagicMock
    _m.RandomForestClassifier = MagicMock

for _sm_key in ("statsmodels", "statsmodels.tsa", "statsmodels.tsa.stattools"):
    _m = _ensure_mod(_sm_key)
    _m.adfuller = MagicMock(return_value=(0.0, 0.05, 0, 100, {}, 0.0))

if "hmmlearn" not in sys.modules:
    _hmmlearn = types.ModuleType("hmmlearn")
    _hmmlearn_hmm = types.ModuleType("hmmlearn.hmm")
    _hmmlearn_hmm.GaussianHMM = MagicMock
    _hmmlearn.hmm = _hmmlearn_hmm
    sys.modules["hmmlearn"] = _hmmlearn
    sys.modules["hmmlearn.hmm"] = _hmmlearn_hmm

# ---- M-series package pre-stub ----------------------------------------------
_m_path = os.path.join(_ROOT, "Spyder", "SpyderM_Monitoring")
_m_pkg = sys.modules.setdefault("Spyder.SpyderM_Monitoring",
                                  types.ModuleType("Spyder.SpyderM_Monitoring"))
_m_pkg.__path__ = [_m_path]
_m_pkg.__package__ = "Spyder.SpyderM_Monitoring"
_m_pkg.__file__ = os.path.join(_m_path, "__init__.py")


# ==============================================================================
# M01 — SystemMonitor
# ==============================================================================
from Spyder.SpyderM_Monitoring.SpyderM01_SystemMonitor import (
    HealthStatus,
    AlertLevel,
    MetricType,
    SystemMetrics,
    SystemMonitor,
)


class TestM01HealthStatusEnum(unittest.TestCase):
    def test_members(self):
        for name in ("HEALTHY", "WARNING", "CRITICAL", "UNKNOWN"):
            self.assertTrue(hasattr(HealthStatus, name), f"Missing: {name}")


class TestM01AlertLevelEnum(unittest.TestCase):
    def test_members(self):
        for name in ("INFO", "WARNING", "CRITICAL"):
            self.assertTrue(hasattr(AlertLevel, name), f"Missing: {name}")


class TestM01MetricTypeEnum(unittest.TestCase):
    def test_members(self):
        for name in ("CPU", "MEMORY", "DISK", "LATENCY", "ERROR_RATE"):
            self.assertTrue(hasattr(MetricType, name), f"Missing: {name}")


class TestM01SystemMetrics(unittest.TestCase):
    def test_is_dataclass(self):
        import dataclasses
        self.assertTrue(dataclasses.is_dataclass(SystemMetrics))

    def test_fields_exist(self):
        import dataclasses
        fields = {f.name for f in dataclasses.fields(SystemMetrics)}
        for name in ("cpu_percent", "memory_percent"):
            self.assertIn(name, fields)


class TestM01SystemMonitorClass(unittest.TestCase):
    def test_exists(self):
        self.assertTrue(callable(SystemMonitor))


# ==============================================================================
# M04 — TradingMetrics
# ==============================================================================
from Spyder.SpyderM_Monitoring.SpyderM04_TradingMetrics import (
    MetricPeriod,
    PerformanceStatus,
    MetricCategory,
    TradeMetrics,
)


class TestM04MetricPeriodEnum(unittest.TestCase):
    def test_members(self):
        for name in ("REAL_TIME", "MINUTE_1", "MINUTE_5", "DAILY"):
            self.assertTrue(hasattr(MetricPeriod, name), f"Missing: {name}")


class TestM04PerformanceStatusEnum(unittest.TestCase):
    def test_members(self):
        for name in ("EXCELLENT", "GOOD", "SATISFACTORY", "WARNING", "POOR", "CRITICAL"):
            self.assertTrue(hasattr(PerformanceStatus, name), f"Missing: {name}")


class TestM04TradeMetrics(unittest.TestCase):
    def test_is_dataclass(self):
        import dataclasses
        self.assertTrue(dataclasses.is_dataclass(TradeMetrics))


# ==============================================================================
# M06 — HMMRegimeDetector
# ==============================================================================
from Spyder.SpyderM_Monitoring.SpyderM06_HMMRegimeDetector import (
    MarketRegime,
    RegimeData,
    RegimeSignal,
    SpyderM06_HMMRegimeDetector,
    create_hmm_detector,
)


class TestM06MarketRegimeEnum(unittest.TestCase):
    def test_members(self):
        for name in ("LOW_VOLATILITY_TRENDING", "HIGH_VOLATILITY_MEAN_REVERTING",
                     "TRANSITIONAL_NEUTRAL"):
            self.assertTrue(hasattr(MarketRegime, name), f"Missing: {name}")


class TestM06Dataclasses(unittest.TestCase):
    def test_regime_data_is_dataclass(self):
        import dataclasses
        self.assertTrue(dataclasses.is_dataclass(RegimeData))

    def test_regime_signal_is_dataclass(self):
        import dataclasses
        self.assertTrue(dataclasses.is_dataclass(RegimeSignal))


class TestM06HMMDetectorClass(unittest.TestCase):
    def test_class_exists(self):
        self.assertTrue(callable(SpyderM06_HMMRegimeDetector))

    def test_factory_callable(self):
        self.assertTrue(callable(create_hmm_detector))


# ==============================================================================
if __name__ == "__main__":
    unittest.main()
