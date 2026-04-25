#!/usr/bin/env python3
"""Focused tests for E16 event-clock order restrictions."""

import asyncio

from Spyder.SpyderE_Risk.SpyderE16_CircuitBreakerProtocol import SpyderCircuitBreakerProtocol


def test_event_clock_blackout_blocks_non_allowlisted_strategy():
    protocol = SpyderCircuitBreakerProtocol()
    protocol.update_event_clock_state(
        {
            "state": "pre",
            "event_type": "CPI",
            "allowed_strategies": ["D03"],
        }
    )

    allowed, reason = asyncio.run(protocol.check_order_restrictions("LIMIT", strategy_id="D99"))

    assert allowed is False
    assert "Event-clock blackout" in reason


def test_event_clock_blackout_allows_allowlisted_strategy():
    protocol = SpyderCircuitBreakerProtocol()
    protocol.update_event_clock_state(
        {
            "state": "post",
            "event_type": "FOMC",
            "allowed_strategies": ["D03"],
        }
    )

    allowed, reason = asyncio.run(protocol.check_order_restrictions("LIMIT", strategy_id="D03"))

    assert allowed is True
    assert reason == "Order type allowed"
