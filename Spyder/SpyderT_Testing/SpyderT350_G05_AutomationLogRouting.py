#!/usr/bin/env python3
"""Focused tests for G05 automation-log routing."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard


def _build_dashboard_stub() -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.add_system_log = MagicMock()
    dash._append_to_ring_log = MagicMock()
    dash.automation_logs = []
    dash.auto_log = object()
    return dash


def test_add_automation_log_routes_non_autonomous_events_to_system_log(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    helper_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        g05,
        "build_automation_log_routing_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or SimpleNamespace(route="system", formatted_message="[LEGACY_STATUS] hello"),
    )

    SpyderTradingDashboard.add_automation_log(
        dash,
        "hello",
        event_type="legacy_status",
        source="dashboard",
    )

    assert helper_calls == [
        {
            "message": "hello",
            "event_type": "legacy_status",
            "source": "dashboard",
            "autonomous_event_type_allowlist": g05._AUTONOMOUS_EVENT_TYPE_ALLOWLIST,
        }
    ]
    dash.add_system_log.assert_called_once_with("[LEGACY_STATUS] hello")
    dash._append_to_ring_log.assert_not_called()


def test_add_automation_log_routes_autonomous_events_to_automation_log(monkeypatch) -> None:
    dash = _build_dashboard_stub()

    monkeypatch.setattr(
        g05,
        "build_automation_log_routing_plan",
        lambda **_kwargs: SimpleNamespace(
            route="automation",
            formatted_message="AGENT_DECISION [X16] entered trade",
        ),
    )

    SpyderTradingDashboard.add_automation_log(
        dash,
        "entered trade",
        event_type="agent_decision",
        source="x16",
    )

    dash.add_system_log.assert_not_called()
    dash._append_to_ring_log.assert_called_once_with(
        dash.automation_logs,
        dash.auto_log,
        "AGENT_DECISION [X16] entered trade",
        max_buffer=100,
        display_count=100,
    )
