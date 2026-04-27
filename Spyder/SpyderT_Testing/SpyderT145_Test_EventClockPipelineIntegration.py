#!/usr/bin/env python3
"""Integration-style tests for A04 -> F09/E16 event-clock blackout pipeline."""

from datetime import datetime, timedelta
import asyncio

from Spyder.SpyderA_Core.SpyderA04_Scheduler import Scheduler, EASTERN_TZ
from Spyder.SpyderF_Analysis.SpyderF09_EntryFilters import EntryFilters, FilterType, FilterResult
from Spyder.SpyderE_Risk.SpyderE16_CircuitBreakerProtocol import SpyderCircuitBreakerProtocol


class _DummyEventManager:
    def __init__(self):
        self.events = []

    def emit(self, event_type, payload):
        self.events.append((event_type, payload))


class _MockConfigManager:
    def get_config(self, key, default=None):
        if key == "autonomous_readiness.event_clock":
            return {
                "enforce_blackout": True,
                "allowlist_strategies": [],
            }
        return default if default is not None else {}

    def is_feature_enabled(self, _key):
        return False


def _economic_event_check(checks):
    econ = [c for c in checks if c.filter_type == FilterType.ECONOMIC_EVENTS]
    assert len(econ) == 1
    return econ[0]


def test_a04_live_state_blocks_non_allowlisted_strategy_across_f09_and_e16():
    """A04 live payload should cause F09/E16 to block non-allowlisted strategies."""
    scheduler = Scheduler(event_manager=_DummyEventManager())
    scheduler.event_clock_config["allowlist_strategies"] = ["D03"]

    now = datetime.now(EASTERN_TZ)
    event_time = now + timedelta(minutes=10)
    scheduler.set_event_clock_events(
        [
            {
                "event_id": "fomc-100",
                "event_type": "FOMC",
                "importance": "high",
                "source": "econ_calendar",
                "event_time_et": event_time,
            }
        ]
    )

    live_payload = scheduler.publish_event_clock_state(now=event_time, force_emit=True)
    event_clock_state = live_payload["data"]
    assert event_clock_state["state"] == "live"

    ef = EntryFilters(_MockConfigManager())
    checks = ef._check_time_filters(
        {
            "current_time": event_time,
            "event_clock_state": event_clock_state,
            "strategy_id": "D99",
        }
    )
    econ_check = _economic_event_check(checks)
    assert econ_check.result == FilterResult.FAIL
    assert "(live)" in econ_check.message

    protocol = SpyderCircuitBreakerProtocol()
    protocol.update_event_clock_state(event_clock_state)
    allowed, reason = asyncio.run(protocol.check_order_restrictions("LIMIT", strategy_id="D99"))
    assert allowed is False
    assert "Event-clock blackout (live)" in reason


def test_a04_live_state_allows_allowlisted_strategy_across_f09_and_e16():
    """A04 live payload should warn-but-allow allowlisted strategies in F09/E16."""
    scheduler = Scheduler(event_manager=_DummyEventManager())
    scheduler.event_clock_config["allowlist_strategies"] = ["D03"]

    now = datetime.now(EASTERN_TZ)
    event_time = now + timedelta(minutes=5)
    scheduler.set_event_clock_events(
        [
            {
                "event_id": "cpi-200",
                "event_type": "CPI",
                "importance": "high",
                "source": "econ_calendar",
                "event_time_et": event_time,
            }
        ]
    )

    live_payload = scheduler.publish_event_clock_state(now=event_time, force_emit=True)
    event_clock_state = live_payload["data"]
    assert event_clock_state["state"] == "live"

    ef = EntryFilters(_MockConfigManager())
    checks = ef._check_time_filters(
        {
            "current_time": event_time,
            "event_clock_state": event_clock_state,
            "strategy_id": "D03",
        }
    )
    econ_check = _economic_event_check(checks)
    assert econ_check.result == FilterResult.WARNING
    assert "allowlisted strategy D03" in econ_check.message

    protocol = SpyderCircuitBreakerProtocol()
    protocol.update_event_clock_state(event_clock_state)
    allowed, reason = asyncio.run(protocol.check_order_restrictions("LIMIT", strategy_id="D03"))
    assert allowed is True
    assert reason == "Order type allowed"
