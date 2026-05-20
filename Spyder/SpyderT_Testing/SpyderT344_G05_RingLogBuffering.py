#!/usr/bin/env python3
"""Focused tests for G05 ring-log buffering and refresh routing."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard


def _build_dashboard_stub() -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.system_log = object()
    dash.auto_log = object()
    dash._system_log_flush_pending = False
    dash._automation_log_flush_pending = False
    dash._flush_log_widget = MagicMock()
    return dash


def test_append_to_ring_log_uses_helper_and_replaces_buffer(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    dash._schedule_log_widget_refresh = MagicMock()
    buffer = ["[09:30:00] old"]
    helper_calls: list[dict[str, object]] = []
    widget = object()

    def _helper(**kwargs):
        helper_calls.append(
            {
                "buffer": list(kwargs["buffer"]),
                "message": kwargs["message"],
                "max_buffer": kwargs["max_buffer"],
                "timestamp_text": kwargs["timestamp_text"],
            }
        )
        return SimpleNamespace(next_buffer=["[09:31:00] newer", "[09:31:01] newest"])

    monkeypatch.setattr(g05, "build_ring_log_append_plan", _helper)

    SpyderTradingDashboard._append_to_ring_log(
        dash,
        buffer,
        widget,
        "hello",
        max_buffer=2,
        display_count=5,
    )

    assert helper_calls == [
        {
            "buffer": ["[09:30:00] old"],
            "message": "hello",
            "max_buffer": 2,
            "timestamp_text": helper_calls[0]["timestamp_text"],
        }
    ]
    assert len(helper_calls[0]["timestamp_text"]) == 8
    assert buffer == ["[09:31:00] newer", "[09:31:01] newest"]
    dash._schedule_log_widget_refresh.assert_called_once_with(buffer, widget, 5)


def test_schedule_log_widget_refresh_uses_helper_for_scheduled_flush(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    timer_calls: list[tuple[int, object]] = []

    monkeypatch.setattr(
        g05,
        "build_log_widget_refresh_plan",
        lambda **_kwargs: SimpleNamespace(
            action="schedule",
            target="system",
            set_system_pending=True,
            set_automation_pending=False,
        ),
    )
    monkeypatch.setattr(g05.QTimer, "singleShot", lambda ms, cb: timer_calls.append((ms, cb)))

    SpyderTradingDashboard._schedule_log_widget_refresh(dash, ["one"], dash.system_log, 3)

    assert dash._system_log_flush_pending is True
    assert len(timer_calls) == 1
    assert timer_calls[0][0] == 75
    timer_calls[0][1]()
    dash._flush_log_widget.assert_called_once_with(["one"], dash.system_log, 3, "system")


def test_schedule_log_widget_refresh_uses_helper_for_immediate_flush(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    timer = MagicMock()
    widget = object()

    monkeypatch.setattr(
        g05,
        "build_log_widget_refresh_plan",
        lambda **_kwargs: SimpleNamespace(
            action="flush",
            target="other",
            set_system_pending=False,
            set_automation_pending=False,
        ),
    )
    monkeypatch.setattr(g05.QTimer, "singleShot", timer)

    SpyderTradingDashboard._schedule_log_widget_refresh(dash, ["one"], widget, 4)

    timer.assert_not_called()
    dash._flush_log_widget.assert_called_once_with(["one"], widget, 4, "other")
