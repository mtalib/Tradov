#!/usr/bin/env python3
"""Focused tests for G05 event-clock display delegation."""

import threading

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
from Spyder.SpyderG_GUI.SpyderG06_DashboardData import EventClockState
from Spyder.SpyderG_GUI.SpyderG47_EventClockDisplayPresenter import (
    EventClockDisplayPresentation,
)
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger


class _Label:
    def __init__(self) -> None:
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
    dash.event_clock_compact_label = _Label()
    dash.event_clock_policy_label = _Label()
    dash.event_clock_windows_label = _Label()
    dash.event_clock_strategies_label = _Label()
    return dash


def test_g05_update_event_clock_display_uses_presenter_output(monkeypatch) -> None:
    dash = _build_dashboard_stub()

    monkeypatch.setattr(
        g05,
        "build_event_clock_display_presentation",
        lambda state: EventClockDisplayPresentation(
            state_text="state",
            state_style="state-style",
            compact_text="compact",
            compact_style="compact-style",
            policy_text="policy",
            windows_text="windows",
            policy_and_windows_text="combined",
            strategies_text="strategies",
        ),
    )

    dash._update_event_clock_display()

    assert dash.event_clock_state_label.text == "state"
    assert dash.event_clock_state_label.style == "state-style"
    assert dash.event_clock_compact_label.text == "compact"
    assert dash.event_clock_compact_label.style == "compact-style"
    assert dash.event_clock_policy_label.text == "policy"
    assert dash.event_clock_windows_label.text == "windows"
    assert dash.event_clock_strategies_label.text == "strategies"


def test_g05_update_event_clock_display_combines_policy_when_windows_label_missing(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    dash.event_clock_windows_label = None

    monkeypatch.setattr(
        g05,
        "build_event_clock_display_presentation",
        lambda state: EventClockDisplayPresentation(
            state_text="state",
            state_style="state-style",
            compact_text="compact",
            compact_style="compact-style",
            policy_text="policy",
            windows_text="windows",
            policy_and_windows_text="combined",
            strategies_text="strategies",
        ),
    )

    dash._update_event_clock_display()

    assert dash.event_clock_policy_label.text == "combined"
