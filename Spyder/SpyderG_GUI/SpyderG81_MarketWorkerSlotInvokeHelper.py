#!/usr/bin/env python3
"""Pure plan builder for market-worker slot invocation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketWorkerSlotInvokePlan:
    """Pure decision output for invoking a market-worker slot."""

    action: str
    warning_message: str | None = None


def build_market_worker_slot_invoke_plan(
    *,
    has_worker: bool,
    has_callable_slot: bool,
    thread_running: bool,
    slot_name: str,
) -> MarketWorkerSlotInvokePlan:
    """Decide how the dashboard should invoke a market-worker slot."""
    if not has_worker:
        return MarketWorkerSlotInvokePlan(action="return_false")

    if not has_callable_slot:
        return MarketWorkerSlotInvokePlan(
            action="warn_and_return_false",
            warning_message=f"Market worker slot unavailable: {slot_name}",
        )

    if not thread_running:
        return MarketWorkerSlotInvokePlan(action="call_direct")

    return MarketWorkerSlotInvokePlan(action="queue_invoke")
