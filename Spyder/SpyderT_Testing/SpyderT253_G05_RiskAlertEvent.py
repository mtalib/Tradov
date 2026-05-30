#!/usr/bin/env python3
"""Focused tests for G05 risk alert event handling."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
from Spyder.SpyderG_GUI.SpyderG50_EntryBlockCompactPresenter import EntryBlockAlertPresentation
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger


def _build_dashboard_stub() -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.logger = SpyderLogger.get_logger(__name__)
    dash._last_entry_block_message = ""
    dash._last_entry_block_ts = 0.0
    dash.logged_messages: list[str] = []
    dash.compact_updates: list[str] = []
    dash.log_system_message = lambda message: dash.logged_messages.append(message)
    dash._update_entry_block_compact_label = lambda text: dash.compact_updates.append(text)
    return dash


def test_g05_handle_risk_alert_event_uses_presenter_output(monkeypatch) -> None:
    dash = _build_dashboard_stub()

    monkeypatch.setattr(
        g05,
        "build_entry_block_alert_presentation",
        lambda reason, *, message=None, detail=None: EntryBlockAlertPresentation(
            digest="digest",
            compact_display="BLOCK: compact",
            system_log_message="system log",
        ),
    )

    with patch("Spyder.SpyderG_GUI.SpyderG05_TradingDashboard.QTimer.singleShot", side_effect=lambda _ms, cb: cb()):
        dash._handle_risk_alert_event({"reason": "entry_trust_gate_rejected", "message": "ignored"})

    assert dash._last_entry_block_message == "digest"
    assert dash.logged_messages == ["system log"]
    assert dash.compact_updates == ["BLOCK: compact"]


def test_g05_handle_risk_alert_event_dedupes_repeated_digest(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    monotonic_values = iter([100.0, 105.0])
    monkeypatch.setattr(g05.time, "monotonic", lambda: next(monotonic_values))

    with patch("Spyder.SpyderG_GUI.SpyderG05_TradingDashboard.QTimer.singleShot", side_effect=lambda _ms, cb: cb()):
        dash._handle_risk_alert_event(
            {"reason": "entry_trust_gate_rejected", "detail": "spread quality too low"}
        )
        dash._handle_risk_alert_event(
            {"reason": "entry_trust_gate_rejected", "detail": "spread quality too low"}
        )

    assert dash.logged_messages == [
        "⛔ Entry blocked (entry_trust_gate_rejected): spread quality too low"
    ]
    assert dash.compact_updates == ["BLOCK: spread quality too low"]


def test_g05_handle_risk_alert_event_uses_dispatch_helper(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    helper_calls: list[dict[str, object]] = []

    monkeypatch.setattr(g05.time, "monotonic", lambda: 123.0)
    monkeypatch.setattr(
        g05,
        "build_entry_block_alert_presentation",
        lambda reason, *, message=None, detail=None: EntryBlockAlertPresentation(
            digest="digest",
            compact_display="BLOCK: compact",
            system_log_message="system log",
        ),
    )
    monkeypatch.setattr(
        g05,
        "build_risk_alert_dispatch_plan",
        lambda **kwargs: helper_calls.append(
            {
                "last_digest": kwargs["last_digest"],
                "last_timestamp": kwargs["last_timestamp"],
                "now_monotonic": kwargs["now_monotonic"],
                "presentation_digest": getattr(kwargs["presentation"], "digest", None),
            }
        )
        or SimpleNamespace(
            should_skip=False,
            next_digest="digest",
            next_timestamp=123.0,
            system_log_message="system log",
            compact_display="BLOCK: compact",
        ),
    )

    with patch("Spyder.SpyderG_GUI.SpyderG05_TradingDashboard.QTimer.singleShot", side_effect=lambda _ms, cb: cb()):
        dash._handle_risk_alert_event({"reason": "entry_trust_gate_rejected", "message": "ignored"})

    assert helper_calls == [
        {
            "last_digest": "",
            "last_timestamp": 0.0,
            "now_monotonic": 123.0,
            "presentation_digest": "digest",
        }
    ]
    assert dash._last_entry_block_message == "digest"
    assert dash._last_entry_block_ts == 123.0
    assert dash.logged_messages == ["system log"]
    assert dash.compact_updates == ["BLOCK: compact"]


def test_g05_handle_risk_alert_event_displays_zero_dte_force_close_alert() -> None:
    dash = _build_dashboard_stub()

    with patch("Spyder.SpyderG_GUI.SpyderG05_TradingDashboard.QTimer.singleShot", side_effect=lambda _ms, cb: cb()):
        dash._handle_risk_alert_event(
            {
                "reason": "zero_dte_eod_force_close",
                "message": "0DTE paper options still open after 15:55 ET (2)",
                "detail": "SPY260528C00754000, SPY260528C00756000",
            }
        )

    assert dash.logged_messages == [
        "⚠️ 0DTE paper options still open after 15:55 ET (2): "
        "SPY260528C00754000, SPY260528C00756000"
    ]
    assert dash.compact_updates == ["BLOCK: 0DTE paper options still open after 15:55 ET (2)"]
