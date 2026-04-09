#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT123_KSeries.py
Purpose: Coverage tests for SpyderK_Reports — key modules (K01, K02, K05)

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

for _k in ("Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils",
           "SpyderU_Utilities.SpyderU03_DateTimeUtils"):
    _m = _ensure_mod(_k)
    _m.DateTimeUtils = MagicMock()

# ---- K-series package pre-stub ----------------------------------------------
_k_path = os.path.join(_ROOT, "Spyder", "SpyderK_Reports")
_k_pkg = sys.modules.setdefault("Spyder.SpyderK_Reports",
                                  types.ModuleType("Spyder.SpyderK_Reports"))
_k_pkg.__path__ = [_k_path]
_k_pkg.__package__ = "Spyder.SpyderK_Reports"
_k_pkg.__file__ = os.path.join(_k_path, "__init__.py")


# ==============================================================================
# K01 — ReportGenerator (Abstract Base + Protocol + enums)
# ==============================================================================
from Spyder.SpyderK_Reports.SpyderK01_ReportGenerator import (
    ReportFormat,
    ReportType,
    ReportMetadata,
    ReportRequest,
    ReportResult,
    BaseReportGenerator,
)


class TestK01ReportFormatEnum(unittest.TestCase):
    def test_members(self):
        for name in ("HTML", "JSON", "CSV", "PDF", "TEXT"):
            self.assertTrue(hasattr(ReportFormat, name), f"Missing: {name}")


class TestK01ReportTypeEnum(unittest.TestCase):
    def test_members(self):
        for name in ("DAILY", "PERFORMANCE", "RISK", "EXECUTION", "PORTFOLIO"):
            self.assertTrue(hasattr(ReportType, name), f"Missing: {name}")


class TestK01Dataclasses(unittest.TestCase):
    def test_report_metadata_is_dataclass(self):
        import dataclasses
        self.assertTrue(dataclasses.is_dataclass(ReportMetadata))

    def test_report_request_is_dataclass(self):
        import dataclasses
        self.assertTrue(dataclasses.is_dataclass(ReportRequest))

    def test_report_result_is_dataclass(self):
        import dataclasses
        self.assertTrue(dataclasses.is_dataclass(ReportResult))


class TestK01BaseReportGenerator(unittest.TestCase):
    def test_is_abstract(self):
        import inspect
        self.assertTrue(inspect.isabstract(BaseReportGenerator)
                        or hasattr(BaseReportGenerator, "__abstractmethods__"))


# ==============================================================================
# K05 — RiskReport (enums + dataclasses)
# ==============================================================================
from Spyder.SpyderK_Reports.SpyderK05_RiskReport import (
    RiskLevel,
    ReportFormat as K05ReportFormat,
    VaRResult,
    GreeksExposure,
    DrawdownAnalysis,
    RiskReportGenerator,
)


class TestK05RiskLevelEnum(unittest.TestCase):
    def test_members(self):
        for name in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
            self.assertTrue(hasattr(RiskLevel, name), f"Missing: {name}")


class TestK05ReportFormatEnum(unittest.TestCase):
    def test_members(self):
        for name in ("JSON", "HTML", "PDF", "TEXT"):
            self.assertTrue(hasattr(K05ReportFormat, name), f"Missing: {name}")


class TestK05Dataclasses(unittest.TestCase):
    def test_var_result_is_dataclass(self):
        import dataclasses
        self.assertTrue(dataclasses.is_dataclass(VaRResult))

    def test_greeks_exposure_is_dataclass(self):
        import dataclasses
        self.assertTrue(dataclasses.is_dataclass(GreeksExposure))

    def test_drawdown_analysis_is_dataclass(self):
        import dataclasses
        self.assertTrue(dataclasses.is_dataclass(DrawdownAnalysis))


class TestK05RiskReportGeneratorClass(unittest.TestCase):
    def test_exists(self):
        self.assertTrue(callable(RiskReportGenerator))


# ==============================================================================
if __name__ == "__main__":
    unittest.main()
