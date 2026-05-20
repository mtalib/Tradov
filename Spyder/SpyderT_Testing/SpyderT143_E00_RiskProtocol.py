#!/usr/bin/env python3
"""
Tests for SpyderE00_RiskProtocol

Covers: BoundarySignalType enum, RiskValidationRequest / RiskValidationResult
dataclass defaults, Protocol isinstance() checks with conforming objects,
and rejection of non-conforming objects.
"""

import os
import sys
import unittest
from datetime import datetime
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from Spyder.SpyderE_Risk.SpyderE00_RiskProtocol import (
    BoundarySignalType,
    OverlayPretradeVerdict,
    RiskManagerProtocol,
    RiskValidationRequest,
    RiskValidationResult,
    StrategyStateProvider,
)


class TestBoundarySignalType(unittest.TestCase):
    def test_all_values_present(self):
        expected = {"buy", "sell", "close", "adjust", "hold"}
        actual = {m.value for m in BoundarySignalType}
        self.assertEqual(actual, expected)


class TestRiskValidationRequest(unittest.TestCase):
    def test_defaults(self):
        req = RiskValidationRequest()
        self.assertEqual(req.symbol, "")
        self.assertEqual(req.quantity, 0)
        self.assertEqual(req.signal_type, BoundarySignalType.BUY)
        self.assertAlmostEqual(req.confidence, 0.0)
        self.assertEqual(req.metadata, {})

    def test_construction(self):
        req = RiskValidationRequest(
            symbol="SPY",
            quantity=10,
            signal_type=BoundarySignalType.SELL,
            strategy_id="iron_condor_1",
            entry_price=450.0,
            confidence=0.8,
        )
        self.assertEqual(req.symbol, "SPY")
        self.assertEqual(req.quantity, 10)
        self.assertAlmostEqual(req.entry_price, 450.0)


class TestRiskValidationResult(unittest.TestCase):
    def test_defaults(self):
        res = RiskValidationResult()
        self.assertFalse(res.approved)
        self.assertEqual(res.rejection_reason, "")
        self.assertAlmostEqual(res.risk_score, 0.0)
        self.assertEqual(res.violations, [])
        self.assertIsInstance(res.timestamp, datetime)

    def test_approved_result(self):
        res = RiskValidationResult(
            approved=True,
            risk_score=0.15,
            max_safe_quantity=5,
        )
        self.assertTrue(res.approved)
        self.assertEqual(res.max_safe_quantity, 5)

    def test_rejected_result_with_violations(self):
        res = RiskValidationResult(
            approved=False,
            rejection_reason="Delta limit exceeded",
            violations=["DELTA_LIMIT_EXCEEDED", "MAX_DAILY_LOSS"],
        )
        self.assertFalse(res.approved)
        self.assertIn("DELTA_LIMIT_EXCEEDED", res.violations)


class TestOverlayPretradeVerdict(unittest.TestCase):
    def test_defaults(self):
        verdict = OverlayPretradeVerdict()
        self.assertFalse(verdict.allow)
        self.assertEqual(verdict.reason_code, "")
        self.assertEqual(verdict.limits_snapshot, {})
        self.assertEqual(verdict.computed_values, {})
        self.assertIsInstance(verdict.timestamp, datetime)

    def test_construction(self):
        verdict = OverlayPretradeVerdict(
            allow=True,
            reason_code="admitted",
            limits_snapshot={"overlay_max_daily_risk_used_fraction": 0.60},
            computed_values={"daily_risk_used_fraction": 0.25},
        )
        self.assertTrue(verdict.allow)
        self.assertEqual(verdict.reason_code, "admitted")
        self.assertEqual(
            verdict.limits_snapshot["overlay_max_daily_risk_used_fraction"],
            0.60,
        )


class _ConformingRiskManager:
    """Minimal concrete class satisfying RiskManagerProtocol structurally."""

    def validate_signal(self, request: RiskValidationRequest) -> RiskValidationResult:
        return RiskValidationResult(approved=True)

    def validate_overlay_slot(self, request: RiskValidationRequest) -> OverlayPretradeVerdict:
        return OverlayPretradeVerdict(allow=True, reason_code="admitted")

    def get_risk_metrics(self) -> dict[str, Any]:
        return {"total_exposure": 0.0, "daily_pnl": 0.0}

    def get_positions(self) -> dict[str, Any]:
        return {}


class _ConformingStateProvider:
    """Minimal concrete class satisfying StrategyStateProvider structurally."""

    def get_state(self) -> dict[str, Any]:
        return {"state": "idle"}

    def get_performance_summary(self) -> dict[str, Any]:
        return {}

    def get_open_positions(self) -> list[Any]:
        return []


class TestRiskManagerProtocol(unittest.TestCase):
    def test_conforming_class_passes_isinstance(self):
        mgr = _ConformingRiskManager()
        self.assertIsInstance(mgr, RiskManagerProtocol)

    def test_nonconforming_object_fails_isinstance(self):
        self.assertNotIsInstance(object(), RiskManagerProtocol)

    def test_validate_signal_returns_result(self):
        mgr = _ConformingRiskManager()
        req = RiskValidationRequest(symbol="SPY", quantity=1)
        result = mgr.validate_signal(req)
        self.assertIsInstance(result, RiskValidationResult)
        self.assertTrue(result.approved)

    def test_validate_overlay_slot_returns_verdict(self):
        mgr = _ConformingRiskManager()
        req = RiskValidationRequest(symbol="SPY", quantity=1)
        result = mgr.validate_overlay_slot(req)
        self.assertIsInstance(result, OverlayPretradeVerdict)
        self.assertTrue(result.allow)


class TestStrategyStateProvider(unittest.TestCase):
    def test_conforming_class_passes_isinstance(self):
        provider = _ConformingStateProvider()
        self.assertIsInstance(provider, StrategyStateProvider)

    def test_nonconforming_object_fails_isinstance(self):
        self.assertNotIsInstance(object(), StrategyStateProvider)


if __name__ == "__main__":
    unittest.main()
