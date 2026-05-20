#!/usr/bin/env python3
"""Pure failure-path UX planning for close-strategy actions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CloseStrategyFailurePlan:
    """Failure log and dialog payload for a rejected close order."""

    log_message: str
    dialog_title: str
    dialog_text: str


def build_close_strategy_failure_plan(
    *,
    failure_kind: str,
    strategy_name: str,
    error_text: str,
) -> CloseStrategyFailurePlan:
    """Return the failure UX bundle for a close-order error."""
    if failure_kind == "tradier_api":
        return CloseStrategyFailurePlan(
            log_message=f"❌ Tradier API error closing {strategy_name}: {error_text}",
            dialog_title="Close Strategy Failed",
            dialog_text=f"Tradier API error while closing '{strategy_name}':\n\n{error_text}",
        )
    if failure_kind == "validation":
        return CloseStrategyFailurePlan(
            log_message=f"❌ Validation error closing {strategy_name}: {error_text}",
            dialog_title="Close Strategy Failed",
            dialog_text=f"Could not build close orders for '{strategy_name}':\n\n{error_text}",
        )
    return CloseStrategyFailurePlan(
        log_message=f"❌ Unexpected error closing {strategy_name}: {error_text}",
        dialog_title="Close Strategy Failed",
        dialog_text=f"Unexpected error while closing '{strategy_name}':\n\n{error_text}",
    )
