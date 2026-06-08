#!/usr/bin/env python3
"""Pure plan builder for market-worker shutdown gating."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketWorkerShutdownPlan:
    """Pure decision output for market-worker shutdown behavior."""

    action: str


def build_market_worker_shutdown_plan(
    *,
    has_worker: bool,
    has_stop_method: bool,
) -> MarketWorkerShutdownPlan:
    """Decide whether G05 should stop the market worker during shutdown."""
    if not has_worker or not has_stop_method:
        return MarketWorkerShutdownPlan(action="noop")

    return MarketWorkerShutdownPlan(action="disconnect_and_stop")
