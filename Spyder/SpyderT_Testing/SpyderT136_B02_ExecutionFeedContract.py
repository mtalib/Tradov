#!/usr/bin/env python3
"""Focused tests for B02 execution telemetry feed contract."""

from datetime import datetime

from Spyder.SpyderB_Broker.SpyderB02_OrderManager import ExecutionReport, EventType


def test_submit_order_records_execution_feed(order_manager, sample_equity_order):
    """Successful submit should append an execution feed envelope."""
    result = order_manager.submit_order(sample_equity_order)

    assert result.success is True

    feeds = order_manager.get_recent_execution_feeds(limit=5)
    assert len(feeds) >= 1

    payload = feeds[-1]
    assert payload["feed"] == "execution"
    assert payload["version"] == "1.0"
    assert payload["data"]["event"] == EventType.ORDER_SUBMITTED.value

    required_data_keys = {
        "order_id",
        "strategy_id",
        "symbol",
        "decision_ts",
        "submit_ts",
        "ack_ts",
        "fill_ts",
        "decision_mid",
        "submit_limit",
        "avg_fill_price",
        "slippage_bps",
        "fill_latency_ms",
        "partial_fill_ratio",
        "reject_flag",
        "reject_reason",
        "cancel_replace_count",
        "session_id",
    }
    assert required_data_keys.issubset(set(payload["data"].keys()))


def test_submission_error_records_rejected_execution_feed(order_manager, sample_equity_order):
    """Submission failure should append a rejected execution feed envelope."""
    order_manager.tradier.place_order.side_effect = ConnectionError("network down")

    result = order_manager.submit_order(sample_equity_order)
    assert result.success is False

    payload = order_manager.get_recent_execution_feeds(limit=1)[-1]
    assert payload["data"]["event"] == EventType.ORDER_REJECTED.value
    assert payload["data"]["reject_flag"] is True
    assert "network down" in (payload["data"]["reject_reason"] or "")


def test_fill_records_filled_execution_feed(order_manager, sample_equity_order):
    """Fill processing should append an ORDER_FILLED execution envelope."""
    submit_result = order_manager.submit_order(sample_equity_order)
    assert submit_result.success is True

    order = sample_equity_order
    report = ExecutionReport(
        order_id=order.order_id,
        tradier_order_id=order.tradier_order_id,
        symbol=order.symbol,
        side=order.side,
        quantity=order.quantity,
        price=581.25,
        execution_id="exec-1",
        timestamp=datetime.now(),
    )

    order_manager._process_fill(order, report)

    payload = order_manager.get_recent_execution_feeds(limit=1)[-1]
    assert payload["data"]["event"] == EventType.ORDER_FILLED.value
    assert payload["data"]["partial_fill_ratio"] == 1.0
    assert payload["data"]["avg_fill_price"] == 581.25
    assert payload["data"]["reject_flag"] is False
