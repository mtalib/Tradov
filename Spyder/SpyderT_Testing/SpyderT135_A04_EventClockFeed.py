#!/usr/bin/env python3
"""Focused tests for A04 event-clock feed transitions."""

from datetime import datetime, timedelta
import sys
import types

from Spyder.SpyderA_Core.SpyderA04_Scheduler import EASTERN_TZ, Scheduler


class _DummyEventManager:
    def __init__(self):
        self.events = []

    def emit(self, event_type, payload):
        self.events.append((event_type, payload))


def _et_now() -> datetime:
    return datetime.now(EASTERN_TZ)


def test_event_clock_transitions_pre_to_clear_emit_on_change():
    em = _DummyEventManager()
    scheduler = Scheduler(event_manager=em)

    # Scheduler.__init__ adds default tasks which emit task_added SYSTEM
    # events.  This test cares only about event_clock_state transitions,
    # so we filter to those when counting.
    def _clock_events() -> list:
        return [
            (et, payload) for (et, payload) in em.events
            if isinstance(payload, dict) and payload.get("type") == "event_clock_state"
        ]

    now = _et_now()
    scheduler.set_event_clock_events(
        [
            {
                "event_id": "cpi-001",
                "event_type": "CPI",
                "importance": "high",
                "source": "econ_calendar",
                "event_time_et": now + timedelta(minutes=10),
            }
        ]
    )

    first = scheduler.publish_event_clock_state(now=now)
    assert first["feed"] == "event_clock"
    assert first["data"]["state"] == "pre"
    assert len(_clock_events()) == 1

    # Same state should not re-emit unless force_emit=True.
    scheduler.publish_event_clock_state(now=now + timedelta(minutes=1))
    assert len(_clock_events()) == 1

    later = scheduler.publish_event_clock_state(now=now + timedelta(minutes=80))
    assert later["data"]["state"] == "clear"
    assert len(_clock_events()) == 2


def test_event_clock_loads_effective_config_from_a03(monkeypatch):
    class _DummyConfigManager:
        config_data = {
            "autonomous_readiness": {
                "event_clock": {
                    "enabled": False,
                    "sources": "manual",
                    "high_impact_only": False,
                    "blackout_pre_minutes": 45,
                    "blackout_post_minutes": 15,
                    "max_size_multiplier_during_event": 0.4,
                    "allowlist_strategies": ["D03_CreditSpread", "", None],
                }
            }
        }

        def get(self, key, default=None):
            if key == "trading.mode":
                return "paper"
            return default

        def validate_autonomous_readiness_config(self, config, mode):
            return {
                "effective": self.config_data,
                "ok": True,
                "warnings": [],
                "errors": [],
            }

    fake_mod = types.SimpleNamespace(get_config_manager=lambda: _DummyConfigManager())
    monkeypatch.setitem(sys.modules, "Spyder.SpyderA_Core.SpyderA03_Configuration", fake_mod)

    scheduler = Scheduler(event_manager=_DummyEventManager())

    assert scheduler.event_clock_config["enabled"] is False
    assert scheduler.event_clock_config["sources"] == "manual"
    assert scheduler.event_clock_config["high_impact_only"] is False
    assert scheduler.event_clock_config["blackout_pre_minutes"] == 45
    assert scheduler.event_clock_config["blackout_post_minutes"] == 15
    assert scheduler.event_clock_config["max_size_multiplier"] == 0.4
    assert scheduler.event_clock_config["allowlist_strategies"] == ["D03_CreditSpread"]


def test_event_clock_manual_source_ignores_calendar_events():
    scheduler = Scheduler(event_manager=_DummyEventManager())
    scheduler.event_clock_config["sources"] = "manual"

    now = _et_now()
    scheduler.set_event_clock_events(
        [
            {
                "event_id": "cpi-001",
                "event_type": "CPI",
                "importance": "high",
                "source": "econ_calendar",
                "event_time_et": now + timedelta(minutes=10),
            }
        ]
    )

    payload = scheduler.publish_event_clock_state(now=now, force_emit=True)
    assert payload["data"]["state"] == "clear"
    assert payload["data"]["sources"] == "manual"


def test_event_clock_manual_override_publishes_blackout_state():
    scheduler = Scheduler(event_manager=_DummyEventManager())
    scheduler.event_clock_config["sources"] = "calendar+manual"
    scheduler.set_event_clock_manual_state(
        {
            "state": "pre",
            "event_id": "manual-1",
            "event_type": "operator_hold",
            "allowed_strategies": ["D03", ""],
            "max_size_multiplier": 0.2,
        }
    )

    payload = scheduler.publish_event_clock_state(now=_et_now(), force_emit=True)
    assert payload["data"]["state"] == "pre"
    assert payload["data"]["source"] == "manual"
    assert payload["data"]["allowed_strategies"] == ["D03"]
    assert payload["data"]["max_size_multiplier"] == 0.2


def test_event_clock_transitions_include_live_at_event_timestamp():
    em = _DummyEventManager()
    scheduler = Scheduler(event_manager=em)

    now = _et_now()
    scheduler.set_event_clock_events(
        [
            {
                "event_id": "fomc-001",
                "event_type": "FOMC",
                "importance": "high",
                "source": "econ_calendar",
                "event_time_et": now + timedelta(minutes=10),
            }
        ]
    )

    pre_payload = scheduler.publish_event_clock_state(now=now, force_emit=True)
    assert pre_payload["data"]["state"] == "pre"

    live_payload = scheduler.publish_event_clock_state(now=now + timedelta(minutes=10), force_emit=True)
    assert live_payload["data"]["state"] == "live"

    post_payload = scheduler.publish_event_clock_state(now=now + timedelta(minutes=11), force_emit=True)
    assert post_payload["data"]["state"] == "post"

    clear_payload = scheduler.publish_event_clock_state(now=now + timedelta(minutes=80), force_emit=True)
    assert clear_payload["data"]["state"] == "clear"


def test_event_clock_high_impact_only_ignores_non_high_events():
    scheduler = Scheduler(event_manager=_DummyEventManager())
    scheduler.event_clock_config["high_impact_only"] = True

    now = _et_now()
    scheduler.set_event_clock_events(
        [
            {
                "event_id": "low-001",
                "event_type": "sentiment_survey",
                "importance": "medium",
                "source": "econ_calendar",
                "event_time_et": now + timedelta(minutes=5),
            }
        ]
    )

    payload = scheduler.publish_event_clock_state(now=now, force_emit=True)
    assert payload["data"]["state"] == "clear"


def test_preflight_dispatch_emits_telegram_send_with_text_and_message_keys():
    em = _DummyEventManager()
    scheduler = Scheduler(event_manager=em)

    scheduler._dispatch_preflight_telegram(now_et=_et_now())

    telegram_events = [
        payload for (_, payload) in em.events
        if isinstance(payload, dict) and payload.get("type") == "telegram_send"
    ]
    assert telegram_events
    event = telegram_events[-1]
    assert isinstance(event.get("text"), str) and event.get("text")
    assert isinstance(event.get("message"), str) and event.get("message")


def test_regular_market_default_start_is_0930(monkeypatch):
    monkeypatch.setenv("SPYDER_SESSION_PRIMARY_START_ET", "09:30")
    scheduler = Scheduler(event_manager=_DummyEventManager())
    regular = scheduler.trading_windows.get("regular_market")
    assert regular is not None
    assert regular.start_time.hour == 9
    assert regular.start_time.minute == 30
