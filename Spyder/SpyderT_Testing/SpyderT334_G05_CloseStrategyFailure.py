#!/usr/bin/env python3
"""Focused tests for G05 close-strategy failure-path wiring."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard


def _build_dashboard_stub() -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.logger = SimpleNamespace(exception=lambda *_args, **_kwargs: None)
    dash.logged_messages: list[str] = []
    dash.log_system_message = lambda message: dash.logged_messages.append(str(message))
    dash._get_tradier_client_for_mode = MagicMock(return_value="paper-client")
    dash._order_manager = SimpleNamespace(
        set_client=MagicMock(),
        submit_multileg_close=MagicMock(side_effect=ValueError("missing legs")),
    )
    return dash


def test_close_strategy_uses_failure_plan_helper_for_validation_errors(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    helper_calls: list[dict[str, object]] = []
    critical = MagicMock()

    monkeypatch.setattr(
        g05,
        "build_close_strategy_failure_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or SimpleNamespace(
            log_message="validation failure log",
            dialog_title="Close Strategy Failed",
            dialog_text="validation failure dialog",
        ),
    )
    monkeypatch.setattr(g05, "QMessageBox", SimpleNamespace(information=MagicMock(), critical=critical))

    strategy_data = {
        "strategy": "Iron Condor",
        "legs": [{"symbol": "SPY"}, {"symbol": "SPY"}],
    }

    SpyderTradingDashboard.close_strategy(dash, strategy_data)

    assert helper_calls == [{"failure_kind": "validation", "strategy_name": "Iron Condor", "error_text": "missing legs"}]
    assert dash.logged_messages == [
        "⚠️ MANUAL OVERRIDE: Closing Iron Condor strategy (2 legs)...",
        "validation failure log",
    ]
    critical.assert_called_once_with(dash, "Close Strategy Failed", "validation failure dialog")
