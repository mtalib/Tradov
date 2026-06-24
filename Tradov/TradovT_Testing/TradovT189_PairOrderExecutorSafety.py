from __future__ import annotations

from datetime import UTC, datetime, timedelta

from Tradov.TradovB_Broker.TradovB00_OrderTypes import OrderType
from Tradov.TradovB_Broker.TradovB02_PairOrderExecutor import (
    PairOrderExecutor,
    PairOrderState,
)
from Tradov.TradovD_Strategies.TradovD01_BaseStrategy import SignalStrength, SignalType
from Tradov.TradovD_Strategies.TradovD50_PairTypes import PairSide, PairTradingSignal


class _FakeOrderManager:
    def __init__(self, ids):
        self.ids = list(ids)
        self.submitted = []
        self.cancelled = []

    def place_equity_order(self, **kwargs):
        self.submitted.append(kwargs)
        return self.ids.pop(0) if self.ids else None

    def cancel_order(self, order_id):
        self.cancelled.append(order_id)


def _signal() -> PairTradingSignal:
    now = datetime.now(UTC)
    return PairTradingSignal(
        signal_id="sig-1",
        signal_type=SignalType.BUY,
        symbol="AAA/BBB",
        strength=SignalStrength.MODERATE,
        confidence=0.9,
        entry_price=0.0,
        stop_loss=0.0,
        take_profit=0.0,
        position_size=1,
        timestamp=now,
        expires_at=now + timedelta(minutes=5),
        pair_key="AAA/BBB",
        pair_side=PairSide.LONG_SHORT,
        symbol_a="AAA",
        symbol_b="BBB",
        quantity_a=10,
        quantity_b=12,
    )


def test_sequential_pair_submission_recovers_leg_a_when_leg_b_fails():
    order_manager = _FakeOrderManager(["A-1", None])
    executor = PairOrderExecutor(order_manager=order_manager)

    pair_order = executor.execute_pair(_signal(), order_type=OrderType.MARKET)

    assert pair_order.state is PairOrderState.RECOVERY
    assert pair_order.leg_a_order_id == "A-1"
    assert order_manager.cancelled == ["A-1"]
    assert pair_order.telemetry["submission_mode"] == "sequential"
    assert pair_order.leg_submit_delay_ms is not None
    assert pair_order.telemetry["recovered_leg_ids"] == ("A-1",)
    assert executor.get_active_orders() == {}


def test_concurrent_pair_submission_records_timing_and_both_ids():
    order_manager = _FakeOrderManager(["A-1", "B-1"])
    executor = PairOrderExecutor(
        order_manager=order_manager,
        concurrent_submissions=True,
        max_leg_submit_delay_ms=1000.0,
    )

    pair_order = executor.execute_pair(_signal(), order_type=OrderType.MARKET)

    assert pair_order.state is PairOrderState.BOTH_SUBMITTED
    assert pair_order.leg_a_order_id == "A-1"
    assert pair_order.leg_b_order_id == "B-1"
    assert pair_order.telemetry["submission_mode"] == "concurrent"
    assert pair_order.telemetry["leg_delay_within_limit"] is True
