#!/usr/bin/env python3
"""
Tests for SpyderZ00_BrokerProtocol

Covers: OrderSide / OrderType enums, NormalizedOrderRequest /
NormalizedOrderResult dataclass defaults, and Protocol isinstance() checks.
"""

import os
import sys
import unittest
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from Spyder.SpyderZ_Communication.SpyderZ00_BrokerProtocol import (
    BrokerClientProtocol,
    NormalizedOrderRequest,
    NormalizedOrderResult,
    OrderRouterProtocol,
    OrderSide,
    OrderType,
)


class TestOrderSideEnum(unittest.TestCase):
    def test_all_sides_present(self):
        expected = {"buy", "sell", "buy_to_open", "buy_to_close",
                    "sell_to_open", "sell_to_close"}
        actual = {m.value for m in OrderSide}
        self.assertEqual(actual, expected)


class TestOrderTypeEnum(unittest.TestCase):
    def test_all_types_present(self):
        expected = {"market", "limit", "stop", "stop_limit", "debit", "credit", "even"}
        actual = {m.value for m in OrderType}
        self.assertEqual(actual, expected)


class TestNormalizedOrderRequest(unittest.TestCase):
    def test_defaults(self):
        req = NormalizedOrderRequest()
        self.assertEqual(req.symbol, "")
        self.assertEqual(req.quantity, 0)
        self.assertEqual(req.side, OrderSide.BUY)
        self.assertEqual(req.order_type, OrderType.MARKET)
        self.assertIsNone(req.limit_price)
        self.assertEqual(req.metadata, {})

    def test_construction(self):
        req = NormalizedOrderRequest(
            symbol="SPY",
            quantity=5,
            side=OrderSide.SELL_TO_OPEN,
            order_type=OrderType.LIMIT,
            limit_price=450.50,
            strategy_id="iron_condor_1",
        )
        self.assertEqual(req.symbol, "SPY")
        self.assertEqual(req.side, OrderSide.SELL_TO_OPEN)
        self.assertAlmostEqual(req.limit_price, 450.50)


class TestNormalizedOrderResult(unittest.TestCase):
    def test_defaults(self):
        res = NormalizedOrderResult()
        self.assertFalse(res.success)
        self.assertEqual(res.order_id, "")
        self.assertEqual(res.status, "")
        self.assertIsNone(res.filled_price)
        self.assertEqual(res.filled_quantity, 0)
        self.assertIsNone(res.error_message)

    def test_successful_result(self):
        res = NormalizedOrderResult(
            success=True,
            order_id="TRD-12345",
            status="filled",
            filled_price=449.75,
            filled_quantity=5,
        )
        self.assertTrue(res.success)
        self.assertEqual(res.order_id, "TRD-12345")
        self.assertAlmostEqual(res.filled_price, 449.75)

    def test_failed_result(self):
        res = NormalizedOrderResult(
            success=False,
            error_message="Insufficient margin",
        )
        self.assertFalse(res.success)
        self.assertEqual(res.error_message, "Insufficient margin")


class _ConformingBrokerClient:
    """Minimal concrete satisfier of BrokerClientProtocol."""

    def submit_order(self, request: NormalizedOrderRequest) -> NormalizedOrderResult:
        return NormalizedOrderResult(success=True, order_id="TEST-001")

    def cancel_order(self, order_id: str) -> bool:
        return True

    def get_order_status(self, order_id: str) -> NormalizedOrderResult:
        return NormalizedOrderResult(success=True, order_id=order_id, status="filled")

    def get_positions(self) -> dict[str, Any]:
        return {}

    def get_account_info(self) -> dict[str, Any]:
        return {"balance": 100_000.0}


class _ConformingOrderRouter:
    """Minimal concrete satisfier of OrderRouterProtocol."""

    def route_order(self, request: NormalizedOrderRequest) -> NormalizedOrderResult:
        return NormalizedOrderResult(success=True)

    def get_routing_stats(self) -> dict[str, Any]:
        return {}


class TestBrokerClientProtocol(unittest.TestCase):
    def test_conforming_passes_isinstance(self):
        client = _ConformingBrokerClient()
        self.assertIsInstance(client, BrokerClientProtocol)

    def test_nonconforming_fails_isinstance(self):
        self.assertNotIsInstance(object(), BrokerClientProtocol)

    def test_submit_order_returns_result(self):
        client = _ConformingBrokerClient()
        req = NormalizedOrderRequest(symbol="SPY", quantity=1)
        result = client.submit_order(req)
        self.assertIsInstance(result, NormalizedOrderResult)
        self.assertTrue(result.success)


class TestOrderRouterProtocol(unittest.TestCase):
    def test_conforming_passes_isinstance(self):
        router = _ConformingOrderRouter()
        self.assertIsInstance(router, OrderRouterProtocol)

    def test_nonconforming_fails_isinstance(self):
        self.assertNotIsInstance(object(), OrderRouterProtocol)


if __name__ == "__main__":
    unittest.main()
