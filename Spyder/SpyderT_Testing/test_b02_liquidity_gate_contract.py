#!/usr/bin/env python3
"""Focused tests for B02 liquidity gate contract behavior."""


def test_option_order_blocked_by_liquidity_gate(order_manager, sample_option_order):
    """Option order should be rejected when liquidity snapshot breaches thresholds."""
    sample_option_order.liquidity_snapshot = {
        "spread_pct": 0.25,
        "spread_abs": 0.35,
        "quote_age_ms": 2200,
        "top_of_book_size": 2,
        "open_interest": 100,
        "volume": 10,
        "oi_change_pct": -0.50,
    }

    result = order_manager.submit_order(sample_option_order)

    assert result.success is False
    assert result.error_code == "LIQUIDITY_GATE_BLOCK"
    assert sample_option_order.state.name == "REJECTED"
    assert order_manager.tradier.place_order.call_count == 0

    lfeed = order_manager.get_recent_liquidity_feeds(limit=1)[-1]
    assert lfeed["feed"] == "liquidity"
    assert lfeed["data"]["gate_passed"] is False
    assert len(lfeed["data"]["reasons"]) >= 1

    # P0-1 contract: liquidity block reasons should propagate into execution reject telemetry.
    efeed = order_manager.get_recent_execution_feeds(limit=1)[-1]
    reject_reason = efeed["data"].get("reject_reason") or ""
    assert efeed["data"]["event"] == "order_rejected"
    assert efeed["data"]["reject_flag"] is True
    assert reject_reason.startswith("liquidity_gate_block:")
    for reason in lfeed["data"]["reasons"]:
        assert reason in reject_reason


def test_option_order_passes_liquidity_gate(order_manager, sample_option_order):
    """Option order should submit when liquidity snapshot is within thresholds."""
    sample_option_order.liquidity_snapshot = {
        "spread_pct": 0.03,
        "spread_abs": 0.05,
        "quote_age_ms": 600,
        "top_of_book_size": 20,
        "open_interest": 1200,
        "volume": 180,
        "oi_change_pct": 0.05,
    }

    result = order_manager.submit_order(sample_option_order)

    assert result.success is True
    assert order_manager.tradier.place_order.call_count == 1

    lfeed = order_manager.get_recent_liquidity_feeds(limit=1)[-1]
    assert lfeed["data"]["gate_passed"] is True
    assert lfeed["data"]["reasons"] == []


def test_multileg_order_blocked_by_liquidity_gate(order_manager, sample_multileg_order):
    """Multileg order should be rejected when liquidity snapshot breaches thresholds."""
    sample_multileg_order.liquidity_snapshot = {
        "spread_pct": 0.40,
        "spread_abs": 0.45,
        "quote_age_ms": 3000,
        "top_of_book_size": 1,
        "open_interest": 50,
        "volume": 5,
        "oi_change_pct": -0.60,
    }

    result = order_manager.submit_order(sample_multileg_order)

    assert result.success is False
    assert result.error_code == "LIQUIDITY_GATE_BLOCK"
    assert sample_multileg_order.state.name == "REJECTED"
    assert order_manager.tradier.place_multileg_order.call_count == 0

    lfeed = order_manager.get_recent_liquidity_feeds(limit=1)[-1]
    assert lfeed["feed"] == "liquidity"
    assert lfeed["data"]["gate_passed"] is False
    assert len(lfeed["data"]["reasons"]) >= 1

    efeed = order_manager.get_recent_execution_feeds(limit=1)[-1]
    reject_reason = efeed["data"].get("reject_reason") or ""
    assert efeed["data"]["event"] == "order_rejected"
    assert efeed["data"]["reject_flag"] is True
    assert reject_reason.startswith("liquidity_gate_block:")
    for reason in lfeed["data"]["reasons"]:
        assert reason in reject_reason


def test_multileg_order_passes_liquidity_gate(order_manager, sample_multileg_order):
    """Multileg order should submit when liquidity snapshot is within thresholds."""
    sample_multileg_order.liquidity_snapshot = {
        "spread_pct": 0.02,
        "spread_abs": 0.04,
        "quote_age_ms": 400,
        "top_of_book_size": 25,
        "open_interest": 1500,
        "volume": 250,
        "oi_change_pct": 0.10,
    }

    result = order_manager.submit_order(sample_multileg_order)

    assert result.success is True
    assert order_manager.tradier.place_multileg_order.call_count == 1

    lfeed = order_manager.get_recent_liquidity_feeds(limit=1)[-1]
    assert lfeed["data"]["gate_passed"] is True
    assert lfeed["data"]["reasons"] == []
