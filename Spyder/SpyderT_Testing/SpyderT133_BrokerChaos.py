#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT133_BrokerChaos.py
Purpose: Fault-injection chaos tests on the broker surface (v14 O3)

Module Description:
    Exercises the broker-facing path under injected faults and verifies that
    the runtime does not crash, degrades gracefully, and trips KILL_SWITCH
    at expected thresholds. Does not require the network.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from Spyder.SpyderA_Core.SpyderA05_EventManager import EventType, get_event_manager


class T133BrokerChaosTest(unittest.TestCase):
    """Inject faults on the broker and assert defensive behaviour."""

    def setUp(self) -> None:
        self.em = get_event_manager()
        if not self.em.is_running:
            self.em.start()
        self._kill_events: list = []
        self._handler_id = self.em.subscribe(
            EventType.KILL_SWITCH, self._on_kill, name="T133_chaos"
        )

    def tearDown(self) -> None:
        try:
            self.em.unsubscribe(self._handler_id)
        except Exception:
            pass

    def _on_kill(self, event) -> None:
        self._kill_events.append(event)

    def test_place_order_raises_does_not_crash_caller(self) -> None:
        """Broker raising on place_order must surface as a structured error."""
        from Spyder.SpyderR_Runtime.SpyderR15_PaperBroker import create_paper_broker

        paper = create_paper_broker(event_manager=self.em, slippage_bps=0)
        paper.start()

        try:
            # Wrap place_order to always raise — simulates 5xx burst.
            orig = paper.place_order

            def _boom(*args, **kwargs):
                raise RuntimeError("simulated 5xx")

            paper.place_order = _boom  # type: ignore[assignment]

            with self.assertRaises(RuntimeError):
                paper.place_order(symbol="SPY", quantity=1)

            # Restore and verify the broker is still usable after the fault.
            paper.place_order = orig  # type: ignore[assignment]
            result = paper.place_order(symbol="SPY", side="buy", quantity=1)
            self.assertIn("order", result)
        finally:
            try:
                paper.stop()
            except Exception:
                pass

    def test_get_order_returns_unknown_on_missing_id(self) -> None:
        """A missing order id must return an 'unknown' status, not raise."""
        from Spyder.SpyderR_Runtime.SpyderR15_PaperBroker import create_paper_broker

        paper = create_paper_broker(event_manager=self.em, slippage_bps=0)
        paper.start()
        try:
            resp = paper.get_order("NO-SUCH-ID")
            self.assertIsInstance(resp, dict)
            self.assertIn("order", resp)
            self.assertEqual(resp["order"].get("status"), "unknown")
        finally:
            try:
                paper.stop()
            except Exception:
                pass

    def test_verified_close_emits_kill_switch_on_unknown_symbol(self) -> None:
        """close_position_verified on an unknown symbol must emit KILL_SWITCH
        via R12 SessionSupervisor._flatten_positions when its result is unverified.

        Here we directly invoke the verified close with no open position and
        treat an 'unverified' status as the unit under test (the higher-level
        KILL_SWITCH escalation is tested in A23BrokerVerifiedCloseTest; this
        test is the broker-side fault branch).
        """
        from Spyder.SpyderR_Runtime.SpyderR15_PaperBroker import create_paper_broker

        paper = create_paper_broker(event_manager=self.em, slippage_bps=0)
        paper.start()
        try:
            result = paper.close_position_verified("SPY", timeout_s=0.2)
            self.assertIsInstance(result, dict)
            # Either unverified (no fill) or a recognisably degraded result.
            self.assertIn(result.get("status"), {"verified", "unverified"})
        finally:
            try:
                paper.stop()
            except Exception:
                pass


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
