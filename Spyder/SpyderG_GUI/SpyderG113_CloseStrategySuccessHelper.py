#!/usr/bin/env python3
"""Pure success-path UX planning for close-strategy actions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class CloseStrategySuccessPlan:
    """Success log and dialog payload for a submitted close order."""

    order_id: object
    log_message: str
    dialog_title: str
    dialog_text: str


def build_close_strategy_success_plan(
    *,
    strategy_name: str,
    num_legs: int,
    response: Mapping[str, object],
) -> CloseStrategySuccessPlan:
    """Return the success UX bundle for a submitted close order."""
    order = response.get("order", {}) if isinstance(response.get("order", {}), Mapping) else {}
    order_id = order.get("id") or response.get("id")
    return CloseStrategySuccessPlan(
        order_id=order_id,
        log_message=f"✅ Close order submitted for {strategy_name} — order ID: {order_id}",
        dialog_title="Close Order Submitted",
        dialog_text=(
            f"Strategy '{strategy_name}' close order submitted successfully.\n\n"
            f"Order ID: {order_id}\n"
            f"Legs: {num_legs}\n"
            "Type: Market / Day\n\n"
            "Positions will update once fills are confirmed."
        ),
    )
