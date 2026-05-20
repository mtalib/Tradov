#!/usr/bin/env python3
"""Focused tests for G05 manual event-clock override wiring."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderA_Core import SpyderA05_EventManager as a05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard


class _Button:
    def __init__(self, checked: bool):
        self._checked = checked
        self.text = None

    def isChecked(self) -> bool:  # noqa: N802
        return self._checked

    def setText(self, value: str) -> None:  # noqa: N802
        self.text = value


def _build_dashboard_stub(checked: bool) -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.event_clock_override_button = _Button(checked)
    dash.event_clock_override_active = None
    dash.logger = SimpleNamespace(debug=MagicMock())
    return dash


def test_toggle_event_clock_override_uses_helper_and_emits_override(monkeypatch) -> None:
    dash = _build_dashboard_stub(checked=True)
    event_manager = SimpleNamespace(emit=MagicMock())
    helper_calls: list[bool] = []

    monkeypatch.setattr(
        a05,
        "EventManager",
        SimpleNamespace(get_instance=lambda: event_manager),
    )
    monkeypatch.setattr(a05, "EventType", SimpleNamespace(RISK="risk"))
    monkeypatch.setattr(
        g05,
        "build_event_clock_override_plan",
        lambda active: helper_calls.append(active)
        or SimpleNamespace(
            button_label="Manual Blackout: ON",
            event_name="event_clock_manual_override",
            event_payload={"state": "live"},
        ),
    )

    SpyderTradingDashboard._toggle_event_clock_override(dash)

    assert helper_calls == [True]
    assert dash.event_clock_override_active is True
    assert dash.event_clock_override_button.text == "Manual Blackout: ON"
    event_manager.emit.assert_called_once_with(
        "risk",
        {"type": "event_clock_manual_override", "payload": {"state": "live"}},
        priority="high",
    )


def test_toggle_event_clock_override_uses_helper_and_emits_clear(monkeypatch) -> None:
    dash = _build_dashboard_stub(checked=False)
    event_manager = SimpleNamespace(emit=MagicMock())

    monkeypatch.setattr(
        a05,
        "EventManager",
        SimpleNamespace(get_instance=lambda: event_manager),
    )
    monkeypatch.setattr(a05, "EventType", SimpleNamespace(RISK="risk"))
    monkeypatch.setattr(
        g05,
        "build_event_clock_override_plan",
        lambda _active: SimpleNamespace(
            button_label="Manual Blackout: OFF",
            event_name="event_clock_manual_clear",
            event_payload={},
        ),
    )

    SpyderTradingDashboard._toggle_event_clock_override(dash)

    assert dash.event_clock_override_active is False
    assert dash.event_clock_override_button.text == "Manual Blackout: OFF"
    event_manager.emit.assert_called_once_with(
        "risk",
        {"type": "event_clock_manual_clear", "payload": {}},
        priority="high",
    )
