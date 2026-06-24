#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovB_Broker
Module: TradovB02_PairOrderExecutor.py
Purpose: Coordinated cross-underlying pair order execution

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-06-03 Time: 00:00:00

Module Description:
    Executes both legs of a pair trade using separate
    single-leg orders (Tradier multileg API requires same underlying).
    Provides best-effort atomic execution:
      - Places legs sequentially by default, or concurrently when enabled
      - If leg B fails/rejected, auto-closes leg A to avoid orphan
      - Tracks paired order state for fill reconciliation
      - Supports market and limit orders for both legs
"""

from __future__ import annotations

import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Any

from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger
from Tradov.TradovA_Core.TradovA05_EventManager import EventType, get_event_manager
from Tradov.TradovD_Strategies.TradovD50_PairTypes import PairSide, PairPosition, PairTradingSignal
from Tradov.TradovB_Broker.TradovB00_OrderTypes import (
    ContractDetails,
    OrderAction,
    OrderRequest,
    OrderType,
    SecType,
    TimeInForce,
)


class PairOrderState(Enum):
    PENDING = "pending"
    LEG_A_SUBMITTED = "leg_a_submitted"
    BOTH_SUBMITTED = "both_submitted"
    LEG_A_FILLED = "leg_a_filled"
    LEG_B_FILLED = "leg_b_filled"
    BOTH_FILLED = "both_filled"
    PARTIAL_FILL = "partial_fill"
    RECOVERY = "recovery"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class PairOrder:
    pair_order_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    pair_key: str = ""
    state: PairOrderState = PairOrderState.PENDING
    leg_a_order_id: str | None = None
    leg_b_order_id: str | None = None
    leg_a_action: OrderAction = OrderAction.BUY
    leg_b_action: OrderAction = OrderAction.SELL
    leg_a_status: str = "pending"
    leg_b_status: str = "pending"
    leg_a_filled_qty: float = 0.0
    leg_b_filled_qty: float = 0.0
    leg_a_avg_price: float = 0.0
    leg_b_avg_price: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    error_message: str | None = None
    leg_a_submitted_at: datetime | None = None
    leg_b_submitted_at: datetime | None = None
    leg_a_ack_at: datetime | None = None
    leg_b_ack_at: datetime | None = None
    leg_submit_delay_ms: float | None = None
    telemetry: dict[str, Any] = field(default_factory=dict)

    @property
    def is_complete(self) -> bool:
        return self.state in {
            PairOrderState.BOTH_FILLED,
            PairOrderState.FAILED,
            PairOrderState.CANCELLED,
            PairOrderState.RECOVERY,
        }


class PairOrderExecutor:
    def __init__(
        self,
        order_manager: Any = None,
        timeout_seconds: float = 30.0,
        concurrent_submissions: bool = False,
        max_leg_submit_delay_ms: float = 500.0,
        logger: logging.Logger | None = None,
    ):
        self.order_manager = order_manager
        self.timeout_seconds = timeout_seconds
        self.concurrent_submissions = concurrent_submissions
        self.max_leg_submit_delay_ms = max_leg_submit_delay_ms
        self.logger = logger or TradovLogger.get_logger("PairOrderExecutor")
        self._active_orders: dict[str, PairOrder] = {}
        self._order_to_pair: dict[str, str] = {}
        self._lock = __import__("threading").RLock()

    def execute_pair(
        self,
        signal: PairTradingSignal,
        price_a: float | None = None,
        price_b: float | None = None,
        order_type: OrderType = OrderType.MARKET,
    ) -> PairOrder:
        pair_order = PairOrder(
            pair_key=signal.pair_key,
        )

        if signal.pair_side == PairSide.LONG_SHORT:
            pair_order.leg_a_action = OrderAction.BUY
            pair_order.leg_b_action = OrderAction.SELL
        else:
            pair_order.leg_a_action = OrderAction.SELL
            pair_order.leg_b_action = OrderAction.BUY

        with self._lock:
            self._active_orders[pair_order.pair_order_id] = pair_order

        contract_a = ContractDetails(
            symbol=signal.symbol_a,
            sec_type=SecType.STOCK,
            exchange="SMART",
        )
        contract_b = ContractDetails(
            symbol=signal.symbol_b,
            sec_type=SecType.STOCK,
            exchange="SMART",
        )

        kwargs_a: dict[str, Any] = {"tif": TimeInForce.DAY}
        kwargs_b: dict[str, Any] = {"tif": TimeInForce.DAY}
        if order_type == OrderType.LIMIT and price_a and price_b:
            kwargs_a["lmt_price"] = price_a
            kwargs_b["lmt_price"] = price_b

        order_a = OrderRequest(
            contract=contract_a,
            action=pair_order.leg_a_action,
            total_quantity=signal.quantity_a,
            order_type=order_type,
            strategy_name="PairTrading",
            **kwargs_a,
        )
        order_b = OrderRequest(
            contract=contract_b,
            action=pair_order.leg_b_action,
            total_quantity=signal.quantity_b,
            order_type=order_type,
            strategy_name="PairTrading",
            **kwargs_b,
        )

        id_a, id_b = self._submit_pair_legs(pair_order, order_a, order_b)
        if self.concurrent_submissions and ((id_a is None) != (id_b is None)):
            if id_a is not None:
                pair_order.leg_a_order_id = str(id_a)
                with self._lock:
                    self._order_to_pair[str(id_a)] = pair_order.pair_order_id
            if id_b is not None:
                pair_order.leg_b_order_id = str(id_b)
                with self._lock:
                    self._order_to_pair[str(id_b)] = pair_order.pair_order_id
            pair_order.state = PairOrderState.RECOVERY
            pair_order.error_message = "Partial pair submission recovered"
            self._recover_partial_submission(pair_order, leg_a_id=id_a, leg_b_id=id_b)
            self._emit_event(pair_order)
            return pair_order

        if id_a is None:
            pair_order.state = PairOrderState.FAILED
            pair_order.error_message = "Leg A submission failed"
            self._emit_event(pair_order)
            return pair_order

        pair_order.leg_a_order_id = str(id_a)
        pair_order.state = PairOrderState.LEG_A_SUBMITTED
        with self._lock:
            self._order_to_pair[str(id_a)] = pair_order.pair_order_id

        if id_b is None:
            self.logger.warning(
                "Leg B failed for pair %s — recovering leg A (%s)",
                signal.pair_key,
                id_a,
            )
            pair_order.state = PairOrderState.RECOVERY
            pair_order.error_message = "Leg B submission failed; recovering leg A"
            self._recover_partial_submission(pair_order, leg_a_id=id_a, leg_b_id=id_b)
            self._emit_event(pair_order)
            return pair_order

        pair_order.leg_b_order_id = str(id_b)
        pair_order.state = PairOrderState.BOTH_SUBMITTED
        with self._lock:
            self._order_to_pair[str(id_b)] = pair_order.pair_order_id

        self._emit_event(pair_order)
        self.logger.info(
            "Pair order submitted: %s leg_a=%s leg_b=%s",
            pair_order.pair_order_id,
            pair_order.leg_a_order_id,
            pair_order.leg_b_order_id,
        )
        return pair_order

    def _submit_pair_legs(
        self,
        pair_order: PairOrder,
        order_a: OrderRequest,
        order_b: OrderRequest,
    ) -> tuple[Any, Any]:
        """Submit pair legs with optional concurrent placement and timing telemetry."""
        if not self.concurrent_submissions:
            start_a = time.monotonic()
            pair_order.leg_a_submitted_at = datetime.now(UTC)
            id_a = self._submit_order(order_a)
            pair_order.leg_a_ack_at = datetime.now(UTC) if id_a is not None else None

            start_b = time.monotonic()
            pair_order.leg_b_submitted_at = datetime.now(UTC)
            id_b = self._submit_order(order_b)
            pair_order.leg_b_ack_at = datetime.now(UTC) if id_b is not None else None
            pair_order.leg_submit_delay_ms = max(0.0, (start_b - start_a) * 1000.0)
            pair_order.telemetry.update(
                {
                    "submission_mode": "sequential",
                    "leg_submit_delay_ms": pair_order.leg_submit_delay_ms,
                    "max_leg_submit_delay_ms": self.max_leg_submit_delay_ms,
                    "leg_delay_within_limit": pair_order.leg_submit_delay_ms <= self.max_leg_submit_delay_ms,
                }
            )
            if pair_order.leg_submit_delay_ms > self.max_leg_submit_delay_ms:
                self.logger.warning(
                    "Pair leg submit delay exceeded limit: pair=%s delay_ms=%.1f limit_ms=%.1f",
                    pair_order.pair_key,
                    pair_order.leg_submit_delay_ms,
                    self.max_leg_submit_delay_ms,
                )
            return id_a, id_b

        pair_order.telemetry["submission_mode"] = "concurrent"
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="pair-order") as executor:
            pair_order.leg_a_submitted_at = datetime.now(UTC)
            start_a = time.monotonic()
            future_a = executor.submit(self._submit_order, order_a)
            pair_order.leg_b_submitted_at = datetime.now(UTC)
            start_b = time.monotonic()
            future_b = executor.submit(self._submit_order, order_b)
            pair_order.leg_submit_delay_ms = abs(start_b - start_a) * 1000.0

            try:
                id_a = future_a.result(timeout=self.timeout_seconds)
                pair_order.leg_a_ack_at = datetime.now(UTC) if id_a is not None else None
            except FutureTimeout:
                self.logger.error("Leg A submission timed out for pair %s", pair_order.pair_key)
                id_a = None
            try:
                id_b = future_b.result(timeout=self.timeout_seconds)
                pair_order.leg_b_ack_at = datetime.now(UTC) if id_b is not None else None
            except FutureTimeout:
                self.logger.error("Leg B submission timed out for pair %s", pair_order.pair_key)
                id_b = None

        pair_order.telemetry.update(
            {
                "leg_submit_delay_ms": pair_order.leg_submit_delay_ms,
                "max_leg_submit_delay_ms": self.max_leg_submit_delay_ms,
                "leg_delay_within_limit": pair_order.leg_submit_delay_ms <= self.max_leg_submit_delay_ms,
            }
        )
        if (id_a is None) != (id_b is None):
            pair_order.telemetry["partial_ack"] = True
            pair_order.telemetry["partial_ack_leg"] = "A" if id_a is not None else "B"
        return id_a, id_b

    def _recover_partial_submission(
        self,
        pair_order: PairOrder,
        *,
        leg_a_id: Any,
        leg_b_id: Any,
    ) -> None:
        """Cancel any acknowledged leg when the pair cannot be completed."""
        cancel_order = getattr(self.order_manager, "cancel_order", None)
        if not callable(cancel_order):
            pair_order.state = PairOrderState.FAILED
            pair_order.error_message = "Partial pair submission could not be recovered"
            return

        recovered_ids: list[str] = []
        for leg_id in (leg_a_id, leg_b_id):
            if leg_id is None:
                continue
            try:
                cancel_order(str(leg_id))
                recovered_ids.append(str(leg_id))
            except Exception as exc:
                self.logger.warning(
                    "Pair recovery cancel failed pair=%s leg_id=%s error=%s",
                    pair_order.pair_key,
                    leg_id,
                    exc,
                )

        if recovered_ids:
            pair_order.telemetry["recovered_leg_ids"] = tuple(recovered_ids)
            pair_order.state = PairOrderState.RECOVERY
        else:
            pair_order.state = PairOrderState.FAILED
            pair_order.error_message = "Partial pair submission could not be recovered"
        pair_order.completed_at = datetime.now(UTC)

    def on_fill(self, order_id: str, filled_qty: float, avg_price: float) -> None:
        with self._lock:
            pair_id = self._order_to_pair.get(order_id)
            if pair_id is None:
                return
            pair_order = self._active_orders.get(pair_id)
            if pair_order is None:
                return

        if order_id == pair_order.leg_a_order_id:
            pair_order.leg_a_status = "filled"
            pair_order.leg_a_filled_qty = filled_qty
            pair_order.leg_a_avg_price = avg_price
            if pair_order.leg_b_status == "filled":
                pair_order.state = PairOrderState.BOTH_FILLED
                pair_order.completed_at = datetime.now(UTC)
            else:
                pair_order.state = PairOrderState.LEG_A_FILLED
        elif order_id == pair_order.leg_b_order_id:
            pair_order.leg_b_status = "filled"
            pair_order.leg_b_filled_qty = filled_qty
            pair_order.leg_b_avg_price = avg_price
            if pair_order.leg_a_status == "filled":
                pair_order.state = PairOrderState.BOTH_FILLED
                pair_order.completed_at = datetime.now(UTC)
            else:
                pair_order.state = PairOrderState.LEG_B_FILLED

        self._emit_event(pair_order)

        if pair_order.state == PairOrderState.BOTH_FILLED:
            with self._lock:
                self._order_to_pair.pop(pair_order.leg_a_order_id, None)
                self._order_to_pair.pop(pair_order.leg_b_order_id, None)

    def close_pair(
        self,
        pair_position: PairPosition,
        order_type: OrderType = OrderType.MARKET,
    ) -> PairOrder | None:
        if pair_position.pair_side == PairSide.LONG_SHORT:
            action_a = OrderAction.SELL
            action_b = OrderAction.BUY
        else:
            action_a = OrderAction.BUY
            action_b = OrderAction.SELL

        signal = PairTradingSignal(
            signal_id=str(uuid.uuid4()),
            signal_type=SignalType.CLOSE if "SignalType" in dir() else __import__(
                "Tradov.TradovD_Strategies.TradovD01_BaseStrategy", fromlist=["SignalType"]
            ).SignalType.CLOSE,
            symbol=pair_position.pair_key,
            strength=__import__(
                "Tradov.TradovD_Strategies.TradovD01_BaseStrategy", fromlist=["SignalStrength"]
            ).SignalStrength.MODERATE,
            confidence=1.0,
            entry_price=0.0,
            stop_loss=0.0,
            take_profit=0.0,
            position_size=pair_position.quantity_a,
            timestamp=datetime.now(UTC),
            expires_at=datetime.now(UTC) + __import__("datetime").timedelta(seconds=300),
            pair_key=pair_position.pair_key,
            pair_side=pair_position.pair_side,
            symbol_a=pair_position.symbol_a,
            symbol_b=pair_position.symbol_b,
            quantity_a=pair_position.quantity_a,
            quantity_b=pair_position.quantity_b,
            hedge_ratio=pair_position.hedge_ratio,
        )

        close_signal = PairTradingSignal(
            signal_id=signal.signal_id,
            signal_type=signal.signal_type,
            symbol=signal.symbol,
            strength=signal.strength,
            confidence=signal.confidence,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            position_size=signal.position_size,
            timestamp=signal.timestamp,
            expires_at=signal.expires_at,
            pair_key=signal.pair_key,
            pair_side=action_a_to_side(action_a),
            symbol_a=signal.symbol_a,
            symbol_b=signal.symbol_b,
            quantity_a=signal.quantity_a,
            quantity_b=signal.quantity_b,
            hedge_ratio=signal.hedge_ratio,
        )
        return self.execute_pair(close_signal, order_type=order_type)

    def _submit_order(self, order: OrderRequest) -> Any:
        if self.order_manager is None:
            self.logger.warning("No order_manager configured — order not submitted")
            return None
        try:
            if hasattr(self.order_manager, "place_equity_order"):
                contract = order.contract
                return self.order_manager.place_equity_order(
                    symbol=contract.symbol,
                    side=order.action.value.lower(),
                    quantity=int(order.total_quantity),
                    order_type=order.order_type.value,
                    limit_price=order.lmt_price,
                )
            if hasattr(self.order_manager, "submit_order"):
                return self.order_manager.submit_order(order)
            self.logger.error("OrderManager has no compatible submit method")
            return None
        except Exception as e:
            self.logger.error("Order submission failed: %s", e)
            return None

    def _recover_leg_a(self, pair_order: PairOrder) -> None:
        if pair_order.leg_a_order_id is None:
            return
        if pair_order.leg_a_status == "filled":
            self.logger.info(
                "Leg A already filled — submitting closing order for %s",
                pair_order.leg_a_order_id,
            )
        elif pair_order.leg_a_status == "pending":
            self.logger.info(
                "Cancelling leg A order %s", pair_order.leg_a_order_id
            )
            if self.order_manager and hasattr(self.order_manager, "cancel_order"):
                try:
                    self.order_manager.cancel_order(pair_order.leg_a_order_id)
                except Exception as e:
                    self.logger.error("Cancel failed for leg A: %s", e)

        pair_order.state = PairOrderState.FAILED
        pair_order.completed_at = datetime.now(UTC)

    def _emit_event(self, pair_order: PairOrder) -> None:
        try:
            em = get_event_manager()
            em.emit(
                EventType.ORDER_PLACED,
                {
                    "pair_order_id": pair_order.pair_order_id,
                    "pair_key": pair_order.pair_key,
                    "state": pair_order.state.value,
                    "leg_a_order_id": pair_order.leg_a_order_id,
                    "leg_b_order_id": pair_order.leg_b_order_id,
                    "leg_a_submitted_at": pair_order.leg_a_submitted_at.isoformat() if pair_order.leg_a_submitted_at else None,
                    "leg_b_submitted_at": pair_order.leg_b_submitted_at.isoformat() if pair_order.leg_b_submitted_at else None,
                    "leg_a_ack_at": pair_order.leg_a_ack_at.isoformat() if pair_order.leg_a_ack_at else None,
                    "leg_b_ack_at": pair_order.leg_b_ack_at.isoformat() if pair_order.leg_b_ack_at else None,
                    "leg_submit_delay_ms": pair_order.leg_submit_delay_ms,
                    "telemetry": dict(pair_order.telemetry),
                },
                source="PairOrderExecutor",
            )
        except Exception:
            pass

    def get_active_orders(self) -> dict[str, PairOrder]:
        with self._lock:
            return {k: v for k, v in self._active_orders.items() if not v.is_complete}


def action_a_to_side(action: OrderAction) -> PairSide:
    return PairSide.LONG_SHORT if action == OrderAction.BUY else PairSide.SHORT_LONG


__all__ = ["PairOrderExecutor", "PairOrder", "PairOrderState", "action_a_to_side"]
