#!/usr/bin/env python3
"""Pure plan builder for market-worker signal disconnect selection."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketWorkerSignalDisconnectPlan:
    """Pure decision output for worker signal disconnect attempts."""

    signal_names: tuple[str, ...]


def build_market_worker_signal_disconnect_plan(
    *,
    has_worker: bool,
    disconnectable_signals: dict[str, bool],
) -> MarketWorkerSignalDisconnectPlan:
    """Select which worker signals G05 should attempt to disconnect."""
    if not has_worker:
        return MarketWorkerSignalDisconnectPlan(signal_names=())

    selected_names = tuple(
        signal_name
        for signal_name in ("fetch_requested", "fast_fetch_requested")
        if disconnectable_signals.get(signal_name, False)
    )
    return MarketWorkerSignalDisconnectPlan(signal_names=selected_names)
