#!/usr/bin/env python3
"""Focused tests for G05 close-strategy success-path wiring."""

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
        submit_multileg_close=MagicMock(return_value={"order": {"id": 12345}}),
    )
    return dash


def test_close_strategy_uses_success_plan_helper(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    helper_calls: list[dict[str, object]] = []
    information = MagicMock()

    monkeypatch.setattr(
        g05,
        "build_close_strategy_success_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or SimpleNamespace(
            order_id=12345,
            log_message="close success log",
            dialog_title="Close Order Submitted",
            dialog_text="close success dialog",
        ),
    )
    monkeypatch.setattr(g05, "QMessageBox", SimpleNamespace(information=information, critical=MagicMock()))

    strategy_data = {
        "strategy": "Iron Condor",
        "legs": [{"symbol": "SPY"}, {"symbol": "SPY"}],
    }

    SpyderTradingDashboard.close_strategy(dash, strategy_data)

    dash._order_manager.set_client.assert_called_once_with("paper-client")
    dash._order_manager.submit_multileg_close.assert_called_once_with("Iron Condor", strategy_data["legs"])
    assert helper_calls == [{"strategy_name": "Iron Condor", "num_legs": 2, "response": {"order": {"id": 12345}}}]
    assert dash.logged_messages == [
        "⚠️ MANUAL OVERRIDE: Closing Iron Condor strategy (2 legs)...",
        "close success log",
    ]
    information.assert_called_once_with(dash, "Close Order Submitted", "close success dialog")
