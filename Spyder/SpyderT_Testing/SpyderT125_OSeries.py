#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT125_OSeries.py
Purpose: Coverage tests for SpyderO_TradingIntelligence — all 3 modules (O01–O03)

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
           "Spyder.SpyderU_Utilities.SpyderU01_Logger"):
    _m = _ensure_mod(_k)
    _m.SpyderLogger = _Logger

for _k in ("Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler",
           "Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler"):
    _m = _ensure_mod(_k)
    _m.SpyderErrorHandler = type("SpyderErrorHandler", (), {})

# ---- O-series package pre-stub ----------------------------------------------
_o_path = os.path.join(_ROOT, "Spyder", "SpyderO_TradingIntelligence")
_o_pkg = sys.modules.setdefault("Spyder.SpyderO_TradingIntelligence",
                                  types.ModuleType("Spyder.SpyderO_TradingIntelligence"))
_o_pkg.__path__ = [_o_path]
_o_pkg.__package__ = "Spyder.SpyderO_TradingIntelligence"
_o_pkg.__file__ = os.path.join(_o_path, "__init__.py")


# ==============================================================================
# O01 — CoreTechnicalIndicators
# ==============================================================================
from Spyder.SpyderO_TradingIntelligence.SpyderO01_CoreTechnicalIndicators import (
    SignalType,
    IndicatorStrength,
    TrendDirection,
    VolatilityRegime,
    IndicatorSignal,
    CoreTechnicalIndicators,
)


class TestO01SignalTypeEnum(unittest.TestCase):
    def test_members(self):
        for name in ("BULLISH", "BEARISH", "NEUTRAL", "DIVERGENCE", "BREAKOUT", "BREAKDOWN"):
            self.assertTrue(hasattr(SignalType, name), f"Missing: {name}")


class TestO01IndicatorStrengthEnum(unittest.TestCase):
    def test_members(self):
        for name in ("VERY_STRONG", "STRONG", "MODERATE", "WEAK", "VERY_WEAK"):
            self.assertTrue(hasattr(IndicatorStrength, name), f"Missing: {name}")


class TestO01TrendDirectionEnum(unittest.TestCase):
    def test_members(self):
        for name in ("STRONG_UPTREND", "UPTREND", "SIDEWAYS", "DOWNTREND", "STRONG_DOWNTREND"):
            self.assertTrue(hasattr(TrendDirection, name), f"Missing: {name}")


class TestO01VolatilityRegimeEnum(unittest.TestCase):
    def test_members(self):
        for name in ("VERY_LOW", "LOW", "MODERATE", "HIGH", "VERY_HIGH"):
            self.assertTrue(hasattr(VolatilityRegime, name), f"Missing: {name}")


class TestO01IndicatorSignal(unittest.TestCase):
    def test_is_dataclass(self):
        import dataclasses
        self.assertTrue(dataclasses.is_dataclass(IndicatorSignal))


class TestO01CoreTechnicalIndicatorsClass(unittest.TestCase):
    def test_exists(self):
        self.assertTrue(callable(CoreTechnicalIndicators))


# ---- L_ML package stub (prevents O02's get_unified_regime_engine chain hitting B_Broker) --
_l_path = os.path.join(_ROOT, "Spyder", "SpyderL_ML")
_l_pkg = types.ModuleType("Spyder.SpyderL_ML")
_l_pkg.__path__ = [_l_path]
_l_pkg.__package__ = "Spyder.SpyderL_ML"
sys.modules["Spyder.SpyderL_ML"] = _l_pkg
sys.modules["SpyderL_ML"] = _l_pkg

_l09_stub = _ensure_mod("SpyderL_ML.SpyderL09_UnifiedRegimeEngine")
_l09_stub.get_unified_regime_engine = MagicMock
sys.modules["Spyder.SpyderL_ML.SpyderL09_UnifiedRegimeEngine"] = _l09_stub


# ==============================================================================
# O02 — TradingOpportunityScanner
# ==============================================================================
from Spyder.SpyderO_TradingIntelligence.SpyderO02_TradingOpportunityScanner import (
    OpportunityType,
    OpportunityPriority,
    MarketBias,
    VolatilityEnvironment,
    TradingOpportunity,
    TradingOpportunityScanner,
)


class TestO02OpportunityTypeEnum(unittest.TestCase):
    def test_members(self):
        for name in ("CREDIT_SPREAD", "IRON_CONDOR", "LONG_STRADDLE"):
            self.assertTrue(hasattr(OpportunityType, name), f"Missing: {name}")


class TestO02OpportunityPriorityEnum(unittest.TestCase):
    def test_members(self):
        for name in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "MONITOR"):
            self.assertTrue(hasattr(OpportunityPriority, name), f"Missing: {name}")


class TestO02MarketBiasEnum(unittest.TestCase):
    def test_members(self):
        for name in ("STRONGLY_BULLISH", "BULLISH", "NEUTRAL", "BEARISH", "STRONGLY_BEARISH"):
            self.assertTrue(hasattr(MarketBias, name), f"Missing: {name}")


class TestO02TradingOpportunity(unittest.TestCase):
    def test_is_dataclass(self):
        import dataclasses
        self.assertTrue(dataclasses.is_dataclass(TradingOpportunity))


class TestO02ScannerClass(unittest.TestCase):
    def test_exists(self):
        self.assertTrue(callable(TradingOpportunityScanner))


# ==============================================================================
# O03 — StrategyOptimizers
# ==============================================================================
from Spyder.SpyderO_TradingIntelligence.SpyderO03_StrategyOptimizers import (
    PinRiskLevel,
    LiquidityTier,
    OptimizationObjective,
    PinRiskAnalysis,
    LiquidityScore,
    StrategyOptimization,
)


class TestO03PinRiskLevelEnum(unittest.TestCase):
    def test_members(self):
        for name in ("VERY_LOW", "LOW", "MODERATE", "HIGH", "VERY_HIGH"):
            self.assertTrue(hasattr(PinRiskLevel, name), f"Missing: {name}")


class TestO03LiquidityTierEnum(unittest.TestCase):
    def test_members(self):
        for name in ("EXCELLENT", "GOOD", "FAIR", "POOR", "VERY_POOR"):
            self.assertTrue(hasattr(LiquidityTier, name), f"Missing: {name}")


class TestO03OptimizationObjectiveEnum(unittest.TestCase):
    def test_members(self):
        for name in ("MAXIMIZE_PROFIT", "MAXIMIZE_PROBABILITY", "MINIMIZE_RISK"):
            self.assertTrue(hasattr(OptimizationObjective, name), f"Missing: {name}")


class TestO03Dataclasses(unittest.TestCase):
    def test_pin_risk_analysis_is_dataclass(self):
        import dataclasses
        self.assertTrue(dataclasses.is_dataclass(PinRiskAnalysis))

    def test_liquidity_score_is_dataclass(self):
        import dataclasses
        self.assertTrue(dataclasses.is_dataclass(LiquidityScore))

    def test_strategy_optimization_is_dataclass(self):
        import dataclasses
        self.assertTrue(dataclasses.is_dataclass(StrategyOptimization))


# ==============================================================================
if __name__ == "__main__":
    unittest.main()
