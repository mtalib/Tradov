#!/usr/bin/env python3
"""Focused tests for G05 event-clock risk-event wiring."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
import threading
from unittest.mock import MagicMock

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
from Spyder.SpyderG_GUI.SpyderG06_DashboardData import EventClockState


def _build_dashboard_stub() -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.logger = SimpleNamespace(debug=MagicMock())
    dash._event_clock_lock = threading.Lock()
    dash.event_clock_state = EventClockState()
    dash._update_event_clock_display = MagicMock()
    return dash


def test_handle_risk_event_uses_helper_plan_and_updates_state(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    helper_calls: list[dict[str, object]] = []
    single_shot = MagicMock()

    monkeypatch.setattr(
        g05,
        "build_event_clock_risk_event_plan",
        lambda event, *, timestamp: helper_calls.append(
            {"event": event, "timestamp": timestamp}
        )
        or SimpleNamespace(
            should_update=True,
            state_kwargs={
                "state": "live",
                "enabled": False,
                "sources": "calendar",
                "allowed_strategies": ["D03"],
                "blackout_pre_minutes": 15,
                "blackout_post_minutes": 20,
                "max_size_multiplier": 0.5,
                "timestamp": timestamp,
            },
        ),
    )
    monkeypatch.setattr(g05.QTimer, "singleShot", single_shot)

    event = {"data": {"ignored": True}}
    SpyderTradingDashboard._handle_risk_event(dash, event)

    assert helper_calls[0]["event"] == event
    assert isinstance(helper_calls[0]["timestamp"], datetime)
    assert dash.event_clock_state.state == "live"
    assert dash.event_clock_state.enabled is False
    assert dash.event_clock_state.allowed_strategies == ["D03"]
    single_shot.assert_called_once_with(0, dash._update_event_clock_display)


def test_handle_risk_event_skips_when_helper_rejects_payload(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    single_shot = MagicMock()

    monkeypatch.setattr(
        g05,
        "build_event_clock_risk_event_plan",
        lambda *_args, **_kwargs: SimpleNamespace(should_update=False, state_kwargs=None),
    )
    monkeypatch.setattr(g05.QTimer, "singleShot", single_shot)

    original_state = dash.event_clock_state
    SpyderTradingDashboard._handle_risk_event(dash, {"data": {"ignored": True}})

    assert dash.event_clock_state is original_state
    single_shot.assert_not_called()
