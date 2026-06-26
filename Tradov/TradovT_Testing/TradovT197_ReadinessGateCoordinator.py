#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovT_Testing
Module: TradovT197_ReadinessGateCoordinator.py
Purpose: Tests for the headless readiness gate coordinator (R13)

Verifies that R13 reproduces the dashboard's GO/NO readiness decision without
any Qt dependency, reusing the same pure G63/G67/G70 helpers, and that the
TTL-cache semantics match _require_fresh_readiness_or_block.
"""

from __future__ import annotations

from datetime import datetime

import pytz

from Tradov.TradovR_Runtime.TradovR13_ReadinessGateCoordinator import (
    ReadinessGateCoordinator,
    ReadinessSnapshotInputs,
    evaluate_readiness,
    gather_inputs,
)

_ET = pytz.timezone("America/New_York")
# Wednesday 2026-06-24, 10:30 ET — a regular weekday during market hours.
MARKET_HOURS = _ET.localize(datetime(2026, 6, 24, 10, 30))
# Saturday 2026-06-27, 10:30 ET — weekend.
WEEKEND = _ET.localize(datetime(2026, 6, 27, 10, 30))


def _ready_inputs(**overrides) -> ReadinessSnapshotInputs:
    base = dict(
        api_connected=True,
        mkt_data_connected=True,
        data_status_label="LIVE",
        event_clock_enabled=False,
        event_clock_state="clear",
        startup_state={},
    )
    base.update(overrides)
    return ReadinessSnapshotInputs(**base)


# --------------------------------------------------------------------------- #
# Pure evaluation
# --------------------------------------------------------------------------- #
def test_ok_when_connected_during_market_hours():
    result = evaluate_readiness(_ready_inputs(), checked_at_et=MARKET_HOURS)
    assert result["decision"] == "OK"
    assert result["conditional"] is False
    assert result["reasons"] == []


def test_no_when_api_disconnected():
    result = evaluate_readiness(_ready_inputs(api_connected=False), checked_at_et=MARKET_HOURS)
    assert result["decision"] == "NO"
    assert any("execution API is disconnected" in r for r in result["reasons"])


def test_no_when_market_data_disconnected():
    result = evaluate_readiness(_ready_inputs(mkt_data_connected=False), checked_at_et=MARKET_HOURS)
    assert result["decision"] == "NO"
    assert any("Market data feed is disconnected" in r for r in result["reasons"])


def test_no_on_weekend():
    result = evaluate_readiness(_ready_inputs(), checked_at_et=WEEKEND)
    assert result["decision"] == "NO"
    assert any("weekend" in r.lower() for r in result["reasons"])


def test_no_when_startup_live_blocking():
    result = evaluate_readiness(
        _ready_inputs(startup_state={"live_blocking": True}), checked_at_et=MARKET_HOURS
    )
    assert result["decision"] == "NO"
    assert any("live-blocking" in r for r in result["reasons"])


def test_conditional_when_data_status_not_live():
    result = evaluate_readiness(
        _ready_inputs(data_status_label="DELAYED"), checked_at_et=MARKET_HOURS
    )
    # Warnings don't hard-block, but flag conditional readiness.
    assert result["decision"] == "OK"
    assert result["conditional"] is True
    assert any("not explicit LIVE" in w for w in result["warnings"])


# --------------------------------------------------------------------------- #
# Coordinator + cache semantics
# --------------------------------------------------------------------------- #
def test_decision_and_is_go_wrappers():
    coord = ReadinessGateCoordinator(et_clock=lambda: MARKET_HOURS)
    assert coord.decision(_ready_inputs()) == "OK"
    assert coord.is_go(_ready_inputs()) is True
    coord.invalidate()
    assert coord.is_go(_ready_inputs(api_connected=False)) is False


def test_cache_reuses_recent_decision_within_ttl():
    clock = {"t": 1000.0}
    coord = ReadinessGateCoordinator(
        ttl_seconds=5.0, clock=lambda: clock["t"], et_clock=lambda: MARKET_HOURS
    )
    first = coord.evaluate(_ready_inputs())
    assert first["decision"] == "OK"

    # Within TTL: even disconnected inputs return the cached OK (proves cache hit).
    clock["t"] = 1003.0
    cached = coord.evaluate(_ready_inputs(api_connected=False))
    assert cached["decision"] == "OK"
    assert cached is first


def test_cache_refreshes_after_ttl_expiry():
    clock = {"t": 1000.0}
    coord = ReadinessGateCoordinator(
        ttl_seconds=5.0, clock=lambda: clock["t"], et_clock=lambda: MARKET_HOURS
    )
    coord.evaluate(_ready_inputs())

    # Past TTL: stale cache is discarded and fresh inputs re-evaluated to NO.
    clock["t"] = 1010.0
    refreshed = coord.evaluate(_ready_inputs(api_connected=False))
    assert refreshed["decision"] == "NO"


def test_use_cache_false_forces_recompute():
    coord = ReadinessGateCoordinator(et_clock=lambda: MARKET_HOURS)
    coord.evaluate(_ready_inputs())
    forced = coord.evaluate(_ready_inputs(api_connected=False), use_cache=False)
    assert forced["decision"] == "NO"


# --------------------------------------------------------------------------- #
# Headless input assembly (injected connection probe — no GUI / no network)
# --------------------------------------------------------------------------- #
def test_gather_inputs_uses_injected_probe():
    inputs = gather_inputs(connection_probe=lambda: (True, "Tradier API (LIVE)"))
    assert inputs.api_connected is True
    assert inputs.mkt_data_connected is True  # defaults to API result

    down = gather_inputs(connection_probe=lambda: (False, "disconnected"))
    assert down.api_connected is False
    assert evaluate_readiness(down, checked_at_et=MARKET_HOURS)["decision"] == "NO"
