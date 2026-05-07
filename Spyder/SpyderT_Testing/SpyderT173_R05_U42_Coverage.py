#!/usr/bin/env python3
"""Focused tests for R05 liveness monitor and U42 strategy circuit breaker."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from Spyder.SpyderR_Runtime.SpyderR05_LivenessMonitor import (
    LivenessMonitor,
    create_liveness_monitor,
)
from Spyder.SpyderU_Utilities import SpyderU42_StrategyCircuitBreaker as u42
from Spyder.SpyderU_Utilities.SpyderU42_StrategyCircuitBreaker import (
    StrategyCircuitBreaker,
    StrategyCircuitBreakerConfig,
    StrategyCircuitBreakerState,
)


class _StubEventManager:
    def __init__(self) -> None:
        self.subscriptions = []
        self.emits = []

    def subscribe(self, event_type, handler, name=None):
        self.subscriptions.append((event_type, name))

    def emit(self, event_type, data, source=None):
        self.emits.append((event_type, data, source))


class _StubKillSwitch:
    def __init__(self, fired: bool) -> None:
        self._fired = fired

    def is_set(self) -> bool:
        return self._fired


def test_r05_snapshot_and_write_heartbeat(tmp_path: Path):
    em = _StubEventManager()
    engine = SimpleNamespace(
        _kill_switch_event=_StubKillSwitch(True),
        broker_connected=False,
        pending_orders={"a": object(), "b": object()},
        _reconciler=SimpleNamespace(_tracked={"x": object()}),
        config=SimpleNamespace(account_id="PAPER-123"),
    )

    hb_path = tmp_path / "hb.json"
    monitor = LivenessMonitor(event_manager=em, engine=engine, heartbeat_path=str(hb_path), healthz_port=0)

    snap = monitor._snapshot()
    assert snap["kill_switch"] is True
    assert snap["broker_connected"] is False
    assert snap["pending_orders_count"] == 2
    assert snap["tracked_orders_count"] == 1
    assert snap["deadman_fired"] is False

    monitor._write_heartbeat()
    payload = json.loads(hb_path.read_text())
    assert payload["kill_switch"] is True
    assert payload["pending_orders_count"] == 2


def test_r05_deadman_emits_kill_switch_when_market_open():
    em = _StubEventManager()
    monitor = LivenessMonitor(event_manager=em, engine=None, heartbeat_path="/tmp/spyder-hb-test", healthz_port=0, deadman_seconds=0.01)

    monitor._is_market_hours = lambda: True
    monitor._is_paper_mode = lambda: False
    monitor._last_event_ts = 0.0

    monitor._maybe_fire_deadman()

    assert monitor._deadman_fired is True
    assert len(em.emits) == 1
    _, data, source = em.emits[0]
    assert data["reason"] == "deadman"
    assert source == "LivenessMonitor"


def test_r05_deadman_suppressed_in_paper_mode():
    em = _StubEventManager()
    monitor = LivenessMonitor(event_manager=em, engine=None, heartbeat_path="/tmp/spyder-hb-test", healthz_port=0, deadman_seconds=0.01)

    monitor._is_market_hours = lambda: True
    monitor._is_paper_mode = lambda: True
    monitor._last_event_ts = 0.0

    monitor._maybe_fire_deadman()

    assert monitor._deadman_fired is False
    assert em.emits == []


def test_r05_create_liveness_monitor_factory_uses_defaults():
    em = _StubEventManager()
    monitor = create_liveness_monitor(event_manager=em, engine=None, healthz_port=0)
    assert isinstance(monitor, LivenessMonitor)


def test_u42_consecutive_failures_trip_and_half_open_recovery():
    cfg = StrategyCircuitBreakerConfig(failure_threshold=2, loss_threshold=-9999.0, recovery_timeout=0.0)
    scb = StrategyCircuitBreaker(config=cfg)

    sid = "strategy-a"
    assert scb.is_allowed(sid) is True

    scb.record_failure(sid, "fail-1")
    assert scb.get_state(sid) == StrategyCircuitBreakerState.CLOSED

    scb.record_failure(sid, "fail-2")
    assert scb.is_allowed(sid) is True
    assert scb.get_state(sid) == StrategyCircuitBreakerState.HALF_OPEN

    scb.record_success(sid)
    assert scb.get_state(sid) == StrategyCircuitBreakerState.CLOSED


def test_u42_loss_threshold_trip_and_manual_reset():
    cfg = StrategyCircuitBreakerConfig(failure_threshold=99, loss_threshold=-100.0, recovery_timeout=60.0)
    scb = StrategyCircuitBreaker(config=cfg)

    sid = "strategy-loss"
    scb.record_pnl(sid, -120.0)
    assert scb.get_state(sid) == StrategyCircuitBreakerState.OPEN

    scb.manually_reset(sid)
    state = scb.get_state(sid)
    assert state == StrategyCircuitBreakerState.CLOSED


def test_u42_half_open_failure_reopens_circuit():
    cfg = StrategyCircuitBreakerConfig(failure_threshold=1, loss_threshold=-9999.0, recovery_timeout=0.0)
    scb = StrategyCircuitBreaker(config=cfg)

    sid = "strategy-half-open"
    scb.record_failure(sid, "initial")
    assert scb.get_state(sid) == StrategyCircuitBreakerState.HALF_OPEN

    scb.record_failure(sid, "probe-failed")
    assert scb.get_state(sid) == StrategyCircuitBreakerState.HALF_OPEN


def test_u42_status_report_and_singleton_reuse():
    # Reset singleton for deterministic assertions.
    u42._strategy_circuit_breaker = None

    inst1 = u42.get_strategy_circuit_breaker(StrategyCircuitBreakerConfig(failure_threshold=3))
    inst2 = u42.get_strategy_circuit_breaker(StrategyCircuitBreakerConfig(failure_threshold=9))
    assert inst1 is inst2

    inst1.record_failure("strategy-report", "boom", pnl_impact=-12.0)
    report = inst1.get_status_report()

    assert "STRATEGY CIRCUIT BREAKER STATUS" in report
    assert "strategy-report" in report
