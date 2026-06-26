#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovR_Runtime
Module: TradovR13_ReadinessGateCoordinator.py
Purpose: Headless start-trading readiness gate (no GUI dependency)

Author: Mohamed Talib (with Claude)
Year Created: 2026
Last Updated: 2026-06-26

Module Description:
    Headless coordinator that reproduces the dashboard's start-trading readiness
    decision without any Qt dependency. It reuses the *same* pure helpers the GUI
    relies on, so a non-GUI caller gets the exact decision the operator sees:

      - G63 build_preopen_check_snapshot_payload  (snapshot shaping)
      - G67 build_trading_readiness_evaluation    (GO/NO evaluation)
      - G70 build_readiness_cache_decision_plan   (TTL cache semantics)

    Why this exists:
        G05._build_preopen_check_snapshot reads a few values from Qt labels while
        assembling the readiness snapshot. Everything downstream of that
        assembly is already pure. This module supplies those scalars explicitly
        via ReadinessSnapshotInputs — sourced from the session/connection layer
        (e.g. R12_SessionSupervisor + a connection probe) instead of widgets —
        so the inbound signal receiver (TradovZ10) and scripts can gate orders
        through the same logic the dashboard uses.

    The connection probe is injected (a Callable) rather than imported, because
    the dashboard's check_api_connection lives in G18_MarketDataWorker which
    imports PySide6; importing it here would re-introduce the GUI dependency.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from Tradov.TradovU_Utilities.TradovU03_DateTimeUtils import now_et
from Tradov.TradovG_GUI.TradovG63_ReadinessSnapshotHelper import (
    build_preopen_check_snapshot_payload,
    normalize_readiness_data_status_label,
)
from Tradov.TradovG_GUI.TradovG67_ReadinessDecisionHelper import (
    build_trading_readiness_evaluation,
)
from Tradov.TradovG_GUI.TradovG70_ReadinessCacheDecisionHelper import (
    build_readiness_cache_decision_plan,
)


@dataclass(frozen=True)
class ReadinessSnapshotInputs:
    """Scalar inputs for a readiness evaluation, sourced headlessly.

    Mirrors exactly what G05._build_preopen_check_snapshot assembles, but the
    caller supplies the values (from the session/connection layer) rather than
    reading them from Qt widgets.
    """

    api_connected: bool
    mkt_data_connected: bool
    data_status_label: str = ""
    event_clock_enabled: bool = False
    event_clock_state: str = "clear"
    startup_state: Mapping[str, Any] = field(default_factory=dict)


def build_readiness_snapshot(
    inputs: ReadinessSnapshotInputs,
    *,
    checked_at_et: datetime | None = None,
) -> dict[str, object]:
    """Build the immutable readiness snapshot payload from headless inputs."""
    checked_at = checked_at_et or now_et()
    return build_preopen_check_snapshot_payload(
        startup_state=dict(inputs.startup_state),
        api_connected=bool(inputs.api_connected),
        mkt_data_connected=bool(inputs.mkt_data_connected),
        data_status_label=normalize_readiness_data_status_label(inputs.data_status_label),
        event_clock_enabled=bool(inputs.event_clock_enabled),
        event_clock_state=str(inputs.event_clock_state),
        checked_at_et=checked_at,
    )


def evaluate_readiness(
    inputs: ReadinessSnapshotInputs,
    *,
    checked_at_et: datetime | None = None,
) -> dict[str, object]:
    """One-shot, cache-free readiness evaluation -> result dict.

    Returns the same shape as G67: {decision, conditional, reasons, warnings,
    checked_at_et, startup_state}. ``decision`` is "OK" or "NO".
    """
    snapshot = build_readiness_snapshot(inputs, checked_at_et=checked_at_et)
    return build_trading_readiness_evaluation(snapshot)


def gather_inputs(
    *,
    connection_probe: Callable[[], tuple[bool, str]],
    market_data_connected: bool | None = None,
    data_status_label: str = "",
    event_clock_enabled: bool = False,
    event_clock_state: str = "clear",
    startup_state: Mapping[str, Any] | None = None,
) -> ReadinessSnapshotInputs:
    """Assemble inputs from an injected connection probe + caller-supplied state.

    ``connection_probe()`` must return ``(connected, mode_label)`` for the
    Tradier API — the headless analogue of G18.check_api_connection. Market-data
    connectivity defaults to the API result unless given explicitly.
    """
    api_connected, _mode = connection_probe()
    mkt = api_connected if market_data_connected is None else market_data_connected
    return ReadinessSnapshotInputs(
        api_connected=bool(api_connected),
        mkt_data_connected=bool(mkt),
        data_status_label=data_status_label,
        event_clock_enabled=event_clock_enabled,
        event_clock_state=event_clock_state,
        startup_state=dict(startup_state or {}),
    )


class ReadinessGateCoordinator:
    """Headless readiness gate with the dashboard's TTL-cache semantics.

    Mirrors G05._require_fresh_readiness_or_block minus the Qt dialog: returns a
    fresh GO/NO decision, reusing a recent decision within ``ttl_seconds``.
    """

    def __init__(
        self,
        *,
        ttl_seconds: float = 5.0,
        clock: Callable[[], float] = time.time,
        et_clock: Callable[[], datetime] = now_et,
    ) -> None:
        self._ttl_seconds = float(ttl_seconds)
        self._clock = clock
        self._et_clock = et_clock
        self._last_ts: float | None = None
        self._last_result: dict[str, object] | None = None

    @property
    def last_result(self) -> dict[str, object] | None:
        return self._last_result

    def invalidate(self) -> None:
        """Drop any cached decision so the next evaluate() recomputes."""
        self._last_ts = None
        self._last_result = None

    def evaluate(
        self,
        inputs: ReadinessSnapshotInputs,
        *,
        use_cache: bool = True,
    ) -> dict[str, object]:
        """Return a readiness result dict, reusing a fresh cached one if allowed."""
        if use_cache:
            cache_plan = build_readiness_cache_decision_plan(
                last_readiness_ts=self._last_ts,
                last_readiness_result=self._last_result,
                now=self._clock(),
                ttl_seconds=self._ttl_seconds,
            )
            if not cache_plan.refresh_required and self._last_result is not None:
                return self._last_result

        result = evaluate_readiness(inputs, checked_at_et=self._et_clock())
        self._last_result = result
        self._last_ts = self._clock()
        return result

    def decision(self, inputs: ReadinessSnapshotInputs, *, use_cache: bool = True) -> str:
        """Return the hard-gate decision: 'OK' or 'NO'."""
        return str(self.evaluate(inputs, use_cache=use_cache).get("decision", "NO"))

    def is_go(self, inputs: ReadinessSnapshotInputs, *, use_cache: bool = True) -> bool:
        """True only when the hard gate is OK (an OK-CONDITIONAL still counts as go)."""
        return self.decision(inputs, use_cache=use_cache) == "OK"
