#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT132_BrokerProtocolParity.py
Purpose: Paper (R15) ↔ Live (B40) broker response-shape parity (v14 O2)

Module Description:
    Drives a fixed sequence of broker method calls against the R15 PaperBroker
    and a mocked B40 TradierClient, then asserts that the response *shapes*
    match on the keys that downstream consumers (R13 FillReconciler,
    R04 LiveEngine) rely on. This is the contract-level check that would have
    caught an accidental divergence between the paper and live broker paths
    before a live-trading regression.
"""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock


_CANNED_SEQUENCE = [
    ("place_order", (), {"symbol": "SPY", "side": "buy", "quantity": 1, "order_type": "market"}),
    ("get_order", ("DUMMY-1",), {}),
    ("cancel_order", ("DUMMY-1",), {}),
    ("get_positions", (), {}),
    ("get_account_balances", (), {}),
]


def _shape_of(value: Any) -> Any:
    """Return a normalized type signature for a value, ignoring concrete data."""
    if isinstance(value, dict):
        return {k: type(v).__name__ for k, v in value.items()}
    if isinstance(value, list):
        return [type(v).__name__ for v in value[:1]]  # first-element shape only
    return type(value).__name__


class T132BrokerProtocolParityTest(unittest.TestCase):
    """Verify PaperBroker and TradierClient return compatible response shapes."""

    def setUp(self) -> None:
        from Spyder.SpyderR_Runtime.SpyderR15_PaperBroker import create_paper_broker

        self.paper = create_paper_broker(event_manager=None, slippage_bps=0)
        self.paper.start()

        # Mock a TradierClient-shaped broker using Tradier's canonical response
        # shapes (per B40 docstrings / live broker observations).
        self.live = MagicMock()
        self.live.place_order = MagicMock(return_value={"order": {"id": "T-9999"}})
        self.live.get_order = MagicMock(
            return_value={"order": {"id": "T-9999", "status": "pending"}}
        )
        self.live.get_orders = MagicMock(return_value=[])
        self.live.cancel_order = MagicMock(return_value=True)
        self.live.get_positions = MagicMock(return_value=[])
        self.live.get_account_balances = MagicMock(return_value={"total_equity": 0.0})

    def tearDown(self) -> None:
        try:
            self.paper.stop()
        except Exception:
            pass

    def test_response_shapes_match_across_sequence(self) -> None:
        for method, args, kwargs in _CANNED_SEQUENCE:
            with self.subTest(method=method):
                paper_fn = getattr(self.paper, method, None)
                live_fn = getattr(self.live, method, None)
                self.assertIsNotNone(paper_fn, f"paper missing {method}")
                self.assertIsNotNone(live_fn, f"live mock missing {method}")

                try:
                    paper_rv = paper_fn(*args, **kwargs)
                except Exception:  # pragma: no cover — parity test does not raise
                    paper_rv = None
                live_rv = live_fn(*args, **kwargs)

                # Both must return the same *top-level* type.
                self.assertEqual(
                    type(paper_rv).__name__,
                    type(live_rv).__name__,
                    f"{method} top-level type mismatch",
                )

                # If dicts, the critical contract keys must overlap.
                if isinstance(live_rv, dict) and isinstance(paper_rv, dict):
                    # `place_order` → both must expose an "order" envelope with an "id".
                    if method == "place_order":
                        self.assertIn("order", paper_rv)
                        self.assertIn("id", paper_rv["order"])
                    # `get_order` → both envelopes must expose a status field.
                    if method == "get_order":
                        self.assertIn("order", paper_rv)
                        self.assertIn("status", paper_rv["order"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
