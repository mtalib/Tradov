#!/usr/bin/env python3
"""
Tests for SpyderF00_AnalysisProtocol

Covers: AnalyticsSignalType enum, IndicatorSnapshot / RegimeSnapshot
dataclass construction and validation helpers, and Protocol isinstance() checks.
"""

import math
import os
import sys
import unittest
from datetime import datetime
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from Spyder.SpyderF_Analysis.SpyderF00_AnalysisProtocol import (
    AnalyticsProviderProtocol,
    AnalyticsSignalType,
    IndicatorSnapshot,
    RegimeAwareAgentProtocol,
    RegimeSnapshot,
)


class TestAnalyticsSignalType(unittest.TestCase):
    def test_all_members_present(self):
        expected = {"bullish", "bearish", "neutral", "undefined"}
        actual = {m.value for m in AnalyticsSignalType}
        self.assertEqual(actual, expected)


class TestIndicatorSnapshot(unittest.TestCase):
    def test_defaults_use_nan(self):
        snap = IndicatorSnapshot(symbol="SPY", timestamp=datetime.now())
        self.assertTrue(math.isnan(snap.rsi))
        self.assertTrue(math.isnan(snap.macd_signal))
        self.assertTrue(math.isnan(snap.atr))

    def test_construction_with_values(self):
        snap = IndicatorSnapshot(
            symbol="SPY",
            timestamp=datetime.now(),
            rsi=55.0,
            macd_signal=0.12,
            atr=3.5,
            bb_upper=460.0,
            bb_lower=440.0,
        )
        self.assertAlmostEqual(snap.rsi, 55.0)
        self.assertAlmostEqual(snap.macd_signal, 0.12)

    def test_is_valid_rsi(self):
        valid = IndicatorSnapshot(symbol="SPY", timestamp=datetime.now(), rsi=50.0)
        invalid = IndicatorSnapshot(symbol="SPY", timestamp=datetime.now())
        self.assertTrue(valid.is_valid_rsi())
        self.assertFalse(invalid.is_valid_rsi())


class TestRegimeSnapshot(unittest.TestCase):
    def test_defaults(self):
        snap = RegimeSnapshot(symbol="SPY", timestamp=datetime.now())
        self.assertEqual(snap.symbol, "SPY")
        self.assertEqual(snap.regime, "unknown")
        self.assertAlmostEqual(snap.confidence, 0.0)

    def test_construction(self):
        snap = RegimeSnapshot(
            symbol="SPY",
            timestamp=datetime.now(),
            regime="trending_up",
            confidence=0.85,
            iv_rank=45.0,
            vix_level=18.5,
        )
        self.assertEqual(snap.regime, "trending_up")
        self.assertAlmostEqual(snap.confidence, 0.85)
        self.assertAlmostEqual(snap.iv_rank, 45.0)

    def test_is_high_confidence(self):
        high = RegimeSnapshot(symbol="SPY", timestamp=datetime.now(), confidence=0.80)
        low = RegimeSnapshot(symbol="SPY", timestamp=datetime.now(), confidence=0.50)
        self.assertTrue(high.is_high_confidence())
        self.assertFalse(low.is_high_confidence())


class _ConformingAnalyticsProvider:
    """Minimal concrete satisfier of AnalyticsProviderProtocol."""

    def calculate_all_indicators(self, symbol: str, data: Any) -> IndicatorSnapshot:
        return IndicatorSnapshot(symbol=symbol, timestamp=datetime.now())

    def get_trading_signals(self, symbol: str) -> list[Any]:
        return []

    def get_current_regime(self, symbol: str) -> RegimeSnapshot:
        return RegimeSnapshot(symbol=symbol, timestamp=datetime.now())


class _ConformingRegimeAgent:
    """Minimal concrete satisfier of RegimeAwareAgentProtocol."""

    def on_regime_change(self, snapshot: RegimeSnapshot) -> None:
        pass

    def get_regime_context(self) -> RegimeSnapshot | None:
        return None


class TestAnalyticsProviderProtocol(unittest.TestCase):
    def test_conforming_passes_isinstance(self):
        provider = _ConformingAnalyticsProvider()
        self.assertIsInstance(provider, AnalyticsProviderProtocol)

    def test_nonconforming_fails_isinstance(self):
        self.assertNotIsInstance(object(), AnalyticsProviderProtocol)

    def test_calculate_returns_snapshot(self):
        provider = _ConformingAnalyticsProvider()
        snap = provider.calculate_all_indicators("SPY", {})
        self.assertIsInstance(snap, IndicatorSnapshot)


class TestRegimeAwareAgentProtocol(unittest.TestCase):
    def test_conforming_passes_isinstance(self):
        agent = _ConformingRegimeAgent()
        self.assertIsInstance(agent, RegimeAwareAgentProtocol)

    def test_nonconforming_fails_isinstance(self):
        self.assertNotIsInstance(object(), RegimeAwareAgentProtocol)


if __name__ == "__main__":
    unittest.main()
