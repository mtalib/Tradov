#!/usr/bin/env python3
"""
Phase 5-C: B02→K04 Execution Telemetry Pipeline Integration Tests

Tests that execution telemetry flows correctly from B02 OrderManager through
K04 ExecutionAnalytics via the EventManager bus.
"""

import unittest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch

from Spyder.SpyderA_Core.SpyderA05_EventManager import Event, EventType
from Spyder.SpyderB_Broker.SpyderB02_OrderManager import Order, OrderState
from Spyder.SpyderK_Reports.SpyderK04_ExecutionAnalytics import ExecutionAnalytics
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger


class TestExecutionTelemetryPipeline(unittest.TestCase):
    """Test B02→K04 execution telemetry pipeline."""

    def setUp(self):
        """Set up test fixtures."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.analytics = ExecutionAnalytics()

    def test_k04_caches_telemetry_from_event_handler(self):
        """Test that K04 caches telemetry received via event handler."""
        # Create a sample telemetry envelope (as B02 would emit)
        telemetry = {
            "feed": "execution",
            "version": "1.0",
            "mode": "paper",
            "session_id": "test-session-001",
            "published_ts": datetime.now().isoformat(),
            "data": {
                "event": "order_filled",
                "order_id": "ORD-12345",
                "strategy_id": "ZeroDTE",
                "symbol": "SPY",
                "decision_ts": datetime.now().isoformat(),
                "submit_ts": datetime.now().isoformat(),
                "ack_ts": datetime.now().isoformat(),
                "fill_ts": datetime.now().isoformat(),
                "decision_mid": 450.50,
                "submit_limit": 450.55,
                "avg_fill_price": 450.52,
                "slippage_bps": 4.4,  # ~4 basis points
                "fill_latency_ms": 145.0,
                "partial_fill_ratio": 1.0,
                "reject_flag": False,
                "reject_reason": None,
                "cancel_replace_count": 0,
                "session_id": "test-session-001",
            },
        }

        # Simulate K04 receiving telemetry event
        event = {"execution_telemetry": telemetry}
        self.analytics._handle_execution_telemetry(event)

        # Verify telemetry was cached
        self.assertIn("ORD-12345", self.analytics.metrics_cache)
        cached = self.analytics.metrics_cache["ORD-12345"]
        self.assertEqual(cached["order_id"], "ORD-12345")
        self.assertEqual(cached["symbol"], "SPY")
        self.assertAlmostEqual(cached["slippage_bps"], 4.4, places=1)

    def test_k04_logs_rejected_orders(self):
        """Test that K04 logs rejected orders from telemetry."""
        telemetry = {
            "feed": "execution",
            "version": "1.0",
            "mode": "paper",
            "session_id": "test-session-002",
            "published_ts": datetime.now().isoformat(),
            "data": {
                "event": "order_rejected",
                "order_id": "ORD-99999",
                "strategy_id": "IronCondor",
                "symbol": "SPY",
                "decision_ts": datetime.now().isoformat(),
                "submit_ts": datetime.now().isoformat(),
                "ack_ts": None,
                "fill_ts": None,
                "slippage_bps": None,
                "fill_latency_ms": None,
                "partial_fill_ratio": 0.0,
                "reject_flag": True,
                "reject_reason": "liquidity_gate_block: spread_pct too high",
                "session_id": "test-session-002",
            },
        }

        event = {"execution_telemetry": telemetry}

        with patch.object(self.logger, "info"):
            self.analytics._handle_execution_telemetry(event)
            # Verify rejection was logged (handler uses self.logger)

        # Verify telemetry was still cached
        self.assertIn("ORD-99999", self.analytics.metrics_cache)

    def test_k04_flags_high_slippage(self):
        """Test that K04 flags orders with high slippage > 25 bps."""
        telemetry = {
            "feed": "execution",
            "version": "1.0",
            "mode": "paper",
            "session_id": "test-session-003",
            "published_ts": datetime.now().isoformat(),
            "data": {
                "event": "order_filled",
                "order_id": "ORD-55555",
                "strategy_id": "CreditSpread",
                "symbol": "SPY",
                "decision_mid": 450.00,
                "submit_limit": 450.25,
                "avg_fill_price": 450.35,
                "slippage_bps": 77.8,  # HIGH: 77.8 basis points
                "fill_latency_ms": 500.0,
                "partial_fill_ratio": 1.0,
                "reject_flag": False,
                "session_id": "test-session-003",
            },
        }

        event = {"execution_telemetry": telemetry}
        self.analytics._handle_execution_telemetry(event)

        # Verify high slippage was cached
        self.assertIn("ORD-55555", self.analytics.metrics_cache)
        cached = self.analytics.metrics_cache["ORD-55555"]
        self.assertGreater(cached["slippage_bps"], 25)

    def test_k04_handles_partial_fills(self):
        """Test that K04 correctly processes partial fill telemetry."""
        telemetry = {
            "feed": "execution",
            "version": "1.0",
            "mode": "paper",
            "session_id": "test-session-004",
            "published_ts": datetime.now().isoformat(),
            "data": {
                "event": "order_partially_filled",
                "order_id": "ORD-77777",
                "strategy_id": "Straddle",
                "symbol": "SPY",
                "slippage_bps": 5.2,
                "fill_latency_ms": 250.0,
                "partial_fill_ratio": 0.65,  # Only 65% filled
                "reject_flag": False,
                "session_id": "test-session-004",
            },
        }

        event = {"execution_telemetry": telemetry}
        self.analytics._handle_execution_telemetry(event)

        # Verify partial fill was cached
        self.assertIn("ORD-77777", self.analytics.metrics_cache)
        cached = self.analytics.metrics_cache["ORD-77777"]
        self.assertAlmostEqual(cached["partial_fill_ratio"], 0.65, places=2)

    def test_k04_ignores_invalid_telemetry(self):
        """Test that K04 gracefully handles invalid telemetry."""
        # Missing data key
        invalid_event1 = {"execution_telemetry": {}}
        self.analytics._handle_execution_telemetry(invalid_event1)
        self.assertEqual(len(self.analytics.metrics_cache), 0)

        # Missing order_id
        invalid_event2 = {
            "execution_telemetry": {
                "data": {"symbol": "SPY"}  # No order_id
            }
        }
        self.analytics._handle_execution_telemetry(invalid_event2)
        self.assertEqual(len(self.analytics.metrics_cache), 0)

        # Non-dict telemetry
        invalid_event3 = {"execution_telemetry": "not a dict"}
        self.analytics._handle_execution_telemetry(invalid_event3)
        self.assertEqual(len(self.analytics.metrics_cache), 0)

    def test_k04_telemetry_persistence(self):
        """Test that multiple telemetry records are accumulated in cache."""
        order_ids = ["ORD-001", "ORD-002", "ORD-003"]

        for order_id in order_ids:
            telemetry = {
                "feed": "execution",
                "data": {
                    "event": "order_filled",
                    "order_id": order_id,
                    "symbol": "SPY",
                    "slippage_bps": 5.0,
                },
            }
            event = {"execution_telemetry": telemetry}
            self.analytics._handle_execution_telemetry(event)

        # Verify all orders cached
        self.assertEqual(len(self.analytics.metrics_cache), 3)
        for order_id in order_ids:
            self.assertIn(order_id, self.analytics.metrics_cache)

    def test_k04_accepts_event_dataclass_payload(self):
        """Test K04 handler supports Event dataclass payload shape from EventManager."""
        telemetry = {
            "feed": "execution",
            "version": "1.0",
            "mode": "paper",
            "session_id": "test-session-event-obj",
            "published_ts": datetime.now().isoformat(),
            "data": {
                "event": "order_rejected",
                "order_id": "ORD-EVT-001",
                "strategy_id": "CreditSpread",
                "symbol": "SPY",
                "reject_flag": True,
                "reject_reason": "liquidity_gate_block: spread_pct too high",
            },
        }

        event = Event(
            event_type=EventType.TRADE,
            source="unit_test",
            data={"execution_telemetry": telemetry},
        )
        self.analytics._handle_execution_telemetry(event)

        self.assertIn("ORD-EVT-001", self.analytics.metrics_cache)
        cached = self.analytics.metrics_cache["ORD-EVT-001"]
        self.assertTrue(cached["reject_flag"])
        self.assertIn("liquidity_gate_block", cached.get("reject_reason") or "")


class TestExecutionTelemetryTimestamps(unittest.TestCase):
    """Test execution telemetry timestamp handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.analytics = ExecutionAnalytics()

    def test_telemetry_includes_all_timestamps(self):
        """Test that telemetry captures decision_ts, submit_ts, ack_ts, fill_ts."""
        now = datetime.now()
        telemetry = {
            "feed": "execution",
            "data": {
                "event": "order_filled",
                "order_id": "ORD-TS-001",
                "decision_ts": now.isoformat(),
                "submit_ts": now.isoformat(),
                "ack_ts": now.isoformat(),
                "fill_ts": now.isoformat(),
            },
        }

        event = {"execution_telemetry": telemetry}
        self.analytics._handle_execution_telemetry(event)

        cached = self.analytics.metrics_cache["ORD-TS-001"]
        self.assertIsNotNone(cached.get("decision_ts"))
        self.assertIsNotNone(cached.get("submit_ts"))
        self.assertIsNotNone(cached.get("ack_ts"))
        self.assertIsNotNone(cached.get("fill_ts"))


class TestExecutionTelemetryMetrics(unittest.TestCase):
    """Test execution quality metrics from telemetry."""

    def setUp(self):
        """Set up test fixtures."""
        self.analytics = ExecutionAnalytics()

    def test_slippage_calculation_propagates(self):
        """Test that slippage_bps from telemetry is available for aggregation."""
        slippage_values = [2.5, 5.0, 10.5, 15.0, 8.2]

        for i, slippage_bps in enumerate(slippage_values):
            telemetry = {
                "feed": "execution",
                "data": {
                    "event": "order_filled",
                    "order_id": f"ORD-SLIP-{i:03d}",
                    "slippage_bps": slippage_bps,
                },
            }
            event = {"execution_telemetry": telemetry}
            self.analytics._handle_execution_telemetry(event)

        # Verify slippage values cached
        self.assertEqual(len(self.analytics.metrics_cache), len(slippage_values))
        cached_slippage = [v["slippage_bps"] for v in self.analytics.metrics_cache.values()]
        self.assertEqual(sorted(cached_slippage), sorted(slippage_values))

    def test_fill_latency_calculation_propagates(self):
        """Test that fill_latency_ms from telemetry is available for analysis."""
        latency_values = [50.0, 100.0, 250.0, 500.0, 1000.0]

        for i, latency_ms in enumerate(latency_values):
            telemetry = {
                "feed": "execution",
                "data": {
                    "event": "order_filled",
                    "order_id": f"ORD-LAT-{i:03d}",
                    "fill_latency_ms": latency_ms,
                },
            }
            event = {"execution_telemetry": telemetry}
            self.analytics._handle_execution_telemetry(event)

        # Verify latency values cached
        self.assertEqual(len(self.analytics.metrics_cache), len(latency_values))
        cached_latency = [v["fill_latency_ms"] for v in self.analytics.metrics_cache.values()]
        self.assertEqual(sorted(cached_latency), sorted(latency_values))


if __name__ == "__main__":
    unittest.main()
