#!/usr/bin/env python3
"""Integration-style tests for A04 event-clock payload consumption by G05."""

from datetime import datetime, timedelta
import threading
from unittest.mock import patch

from Spyder.SpyderA_Core.SpyderA04_Scheduler import Scheduler, EASTERN_TZ
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
from Spyder.SpyderG_GUI.SpyderG06_DashboardData import EventClockState
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger


class _DummyEventManager:
    def __init__(self):
        self.events = []

    def emit(self, event_type, payload):
        self.events.append((event_type, payload))


class _Label:
    def __init__(self):
        self.text = ""
        self.style = ""

    def setText(self, value: str) -> None:  # noqa: N802
        self.text = value

    def setStyleSheet(self, value: str) -> None:  # noqa: N802
        self.style = value


def _build_dashboard_stub() -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.logger = SpyderLogger.get_logger(__name__)
    dash._event_clock_lock = threading.Lock()
    dash.event_clock_state = EventClockState()
    dash.event_clock_state_label = _Label()
    dash.event_clock_policy_label = _Label()
    dash.event_clock_windows_label = _Label()
    dash.event_clock_strategies_label = _Label()
    return dash


def test_g05_consumes_a04_live_payload_and_updates_labels():
    """A04 live payload should update G05 event-clock labels via RISK handler path."""
    scheduler = Scheduler(event_manager=_DummyEventManager())
    scheduler.event_clock_config["allowlist_strategies"] = ["D03"]

    now = datetime.now(EASTERN_TZ)
    event_time = now + timedelta(minutes=5)
    scheduler.set_event_clock_events(
        [
            {
                "event_id": "cpi-live-001",
                "event_type": "CPI",
                "importance": "high",
                "source": "econ_calendar",
                "event_time_et": event_time,
            }
        ]
    )
    payload = scheduler.publish_event_clock_state(now=event_time, force_emit=True)
    assert payload["data"]["state"] == "live"

    dash = _build_dashboard_stub()

    # Simulate A04/EventManager wrapped RISK event shape as consumed by G05.
    risk_event = {
        "data": {
            "type": "event_clock_state",
            "payload": payload,
            "timestamp": event_time,
        }
    }

    with patch("Spyder.SpyderG_GUI.SpyderG05_TradingDashboard.QTimer.singleShot", side_effect=lambda _ms, cb: cb()):
        dash._handle_risk_event(risk_event)

    assert dash.event_clock_state_label.text == "◆ LIVE EVENT"
    assert "Enabled" in dash.event_clock_policy_label.text
    assert "calendar+manual" in dash.event_clock_policy_label.text
    assert "-30m / +30m" in dash.event_clock_windows_label.text
    assert "25%" in dash.event_clock_windows_label.text
    assert "D03" in dash.event_clock_strategies_label.text
