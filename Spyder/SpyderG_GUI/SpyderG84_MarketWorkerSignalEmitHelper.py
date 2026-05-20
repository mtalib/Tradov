#!/usr/bin/env python3
"""Pure plan builder for market-worker signal emission."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketWorkerSignalEmitPlan:
    """Pure decision output for market-worker signal emission."""

    action: str


def build_market_worker_signal_emit_plan(
    *,
    has_worker: bool,
    has_signal: bool,
    has_emit_method: bool,
) -> MarketWorkerSignalEmitPlan:
    """Decide whether G05 should attempt to emit a worker signal."""
    if not has_worker or not has_signal or not has_emit_method:
        return MarketWorkerSignalEmitPlan(action="noop")

    return MarketWorkerSignalEmitPlan(action="emit")
