#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT129_ProtocolCompliance.py
Purpose: Runtime protocol compliance tests for recently-touched series
Author: SPYDER Trading System
Year Created: 2026
Last Updated: 2026-04-14

Module Description:
    Fast-running contract tests that would have caught the v5/v3 audit
    findings at merge time:
      - E01 RiskManager missing validate_signal() and the wrong
        get_risk_metrics() return type relative to RiskManagerProtocol.
      - F10 MarketRegimeDetector returning empty IndicatorSnapshot stubs
        that passed structural Protocol check but delivered no data.
      - C04 MarketInternals referencing non-existent MarketCondition.UNKNOWN.

    These tests rely on runtime-checkable Protocols plus a handful of
    semantic assertions (return type, shape, non-empty where required).
    Keep them cheap — no network, no broker, no GUI imports.
"""

from __future__ import annotations

import unittest
from typing import Any


class E01RiskManagerProtocolTest(unittest.TestCase):
    """Verify SpyderE01 RiskManager satisfies E00 RiskManagerProtocol."""

    def test_risk_manager_exposes_validate_signal(self) -> None:
        from Spyder.SpyderE_Risk.SpyderE01_RiskManager import RiskManager

        self.assertTrue(
            hasattr(RiskManager, "validate_signal"),
            "E01 RiskManager must implement validate_signal() per E00 protocol",
        )

    def test_risk_manager_factory_accepts_tradier_client(self) -> None:
        from Spyder.SpyderE_Risk.SpyderE01_RiskManager import create_risk_manager, RiskConfig

        rm = create_risk_manager(
            RiskConfig(enable_real_time_monitoring=False),
            connect_api=None,
            tradier_client=None,
        )
        self.assertIsNotNone(rm)
        self.assertIsNone(rm.tradier_client)


class F10RegimeDetectorStubContractTest(unittest.TestCase):
    """F10 is a regime detector; it must NOT silently return empty indicators."""

    def test_calculate_all_indicators_returns_none(self) -> None:
        from Spyder.SpyderF_Analysis.SpyderF10_MarketRegimeDetector import MarketRegimeDetector

        detector = MarketRegimeDetector()
        result = detector.calculate_all_indicators("SPY")
        self.assertIsNone(
            result,
            "F10 must return None (not an empty snapshot) — callers should "
            "route indicator requests to F01 IndicatorEngine",
        )


class C04MarketConditionEnumTest(unittest.TestCase):
    """C04 must only reference MarketCondition members that actually exist."""

    def test_get_current_condition_returns_valid_enum(self) -> None:
        from Spyder.SpyderC_MarketData.SpyderC04_MarketInternals import (
            MarketInternals,
            MarketCondition,
        )

        internals = MarketInternals()
        # Must not raise AttributeError from .UNKNOWN lookup.
        condition = internals.get_current_condition()
        self.assertIsInstance(condition, MarketCondition)


class F00AnalyticsProtocolSurfaceTest(unittest.TestCase):
    """F00 surface must match implementors — catches rename drift."""

    def test_protocol_exports_renamed_methods(self) -> None:
        from Spyder.SpyderF_Analysis import SpyderF00_AnalysisProtocol as protocol

        self.assertTrue(hasattr(protocol, "AnalyticsProviderProtocol"))
        proto: Any = protocol.AnalyticsProviderProtocol
        # The v5 rename moved from get_indicator_snapshot -> calculate_all_indicators.
        self.assertTrue(
            hasattr(proto, "calculate_all_indicators")
            or "calculate_all_indicators" in getattr(proto, "__abstractmethods__", set())
            or "calculate_all_indicators" in dir(proto),
            "F00 AnalyticsProviderProtocol must expose calculate_all_indicators",
        )


class RegimeCanonicalWiringTest(unittest.TestCase):
    """Verify that no production module calls E21/M06 regime APIs directly
    when L09 UnifiedRegimeEngine is available, per Overview §1."""

    def test_d30_regime_gated_selector_prefers_l09(self) -> None:
        """D30 must declare L09 as primary regime source (fallback to E21 is OK)."""
        import ast
        import pathlib

        d30_path = pathlib.Path(__file__).resolve().parents[1] / "SpyderD_Strategies" / "SpyderD30_RegimeGatedSelector.py"
        source = d30_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        # Collect all import aliases
        imported_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imported_names.add(alias.asname or alias.name)

        self.assertIn(
            "UnifiedRegimeEngine",
            imported_names,
            "D30 must import UnifiedRegimeEngine from L09 (canonical regime source)",
        )
        # E21 import is allowed as a fallback but L09 must be declared first
        l09_lineno: int | None = None
        e21_lineno: int | None = None
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if "SpyderL09" in node.module or "L09_Unified" in node.module:
                    l09_lineno = node.lineno
                if "SpyderE21" in node.module:
                    e21_lineno = node.lineno
        if l09_lineno is not None and e21_lineno is not None:
            self.assertLess(
                l09_lineno,
                e21_lineno,
                "D30 must import L09 before E21 (L09 is the canonical primary source)",
            )

    def test_y01_market_sense_agent_prefers_l09(self) -> None:
        """Y01 MarketSenseAgent must import L09 and try it before E21."""
        import pathlib

        y01_path = pathlib.Path(__file__).resolve().parents[1] / "SpyderY_AutoAgents" / "SpyderY01_MarketSenseAgent.py"
        source = y01_path.read_text(encoding="utf-8")

        self.assertIn(
            "L09_AVAILABLE",
            source,
            "Y01 must declare L09_AVAILABLE flag (signals canonical regime wiring)",
        )
        # L09 import block should appear before E21 import block
        l09_idx = source.find("L09_AVAILABLE")
        e21_idx = source.find("HMM_AVAILABLE")
        self.assertLess(
            l09_idx,
            e21_idx,
            "Y01 must check L09 availability before E21 (L09 is canonical primary)",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
