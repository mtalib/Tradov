#!/usr/bin/env python3
"""Pure prompt and outcome copy for the dashboard pending-orders gate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class PendingOrdersGatePrompt:
    """Pure prompt copy for the pending-orders mode-switch gate."""

    prompt_title: str
    prompt_text: str
    declined_log_message: str


@dataclass(frozen=True)
class PendingOrdersGateOutcome:
    """Pure success/failure copy for the pending-orders mode-switch gate."""

    failure_dialog_title: str
    failure_dialog_text: str
    success_log_message: str


def _normalize_pending_orders_source(pending_mode_name: str) -> str:
    normalized_mode_name = str(pending_mode_name or "").strip().lower()
    return "paper/local" if normalized_mode_name == "paper" else "LIVE"


def build_pending_orders_gate_prompt(
    *,
    pending_orders: Sequence[Mapping[str, Any]],
    pending_mode_name: str,
    target_label: str,
) -> PendingOrdersGatePrompt:
    """Build the pending-orders prompt shown before a mode switch."""
    source = _normalize_pending_orders_source(pending_mode_name)
    order_lines = "\n".join(
        f"  #{order.get('id')}  {order.get('symbol', '?')}  {str(order.get('side', '?')).upper()}"
        f"  qty {int(order.get('quantity', 0))}  [{str(order.get('status', '?')).upper()}]"
        for order in pending_orders[:10]
    )
    suffix = f"\n  … and {len(pending_orders) - 10} more" if len(pending_orders) > 10 else ""
    return PendingOrdersGatePrompt(
        prompt_title=f"Pending {source.title()} Orders Must Be Cancelled",
        prompt_text=(
            f"You have {len(pending_orders)} pending {source} order(s):\n\n"
            f"{order_lines}{suffix}\n\n"
            f"These must be cancelled before switching to {target_label}.\n\n"
            "Cancel all pending orders now and continue?"
        ),
        declined_log_message=(
            f"Switch to {target_label} cancelled — pending {source} orders remain"
        ),
    )


def build_pending_orders_gate_outcome(
    *,
    pending_mode_name: str,
    support_suffix: str,
    cancelled_count: int,
    failed_count: int,
) -> PendingOrdersGateOutcome:
    """Build the pending-orders cancellation outcome messages."""
    source = _normalize_pending_orders_source(pending_mode_name)
    return PendingOrdersGateOutcome(
        failure_dialog_title="Cancellation Failed",
        failure_dialog_text=(
            f"{failed_count} order(s) could not be cancelled.\n{support_suffix}"
        ),
        success_log_message=(
            f"✅ {cancelled_count} pending {source} order(s) cancelled — continuing switch"
        ),
    )
