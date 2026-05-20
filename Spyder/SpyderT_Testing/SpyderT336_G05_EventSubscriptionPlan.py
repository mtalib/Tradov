#!/usr/bin/env python3
"""Focused tests for G05 event subscription plan wiring."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, call

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderA_Core import SpyderA05_EventManager as a05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard


def _build_dashboard_stub() -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.logger = SimpleNamespace(info=MagicMock(), warning=MagicMock())
    dash._handle_risk_event = MagicMock()
    dash._handle_trade_event = MagicMock()
    dash._handle_position_updated_event = MagicMock()
    dash._handle_risk_alert_event = MagicMock()
    dash._shutdown_in_progress = False
    dash._event_subscriptions_started = False
    return dash


def test_subscribe_to_events_uses_subscription_plan_helper(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    event_types = SimpleNamespace(ALERT="alert")
    handler_types = SimpleNamespace(SYNC="sync")
    event_manager = SimpleNamespace(subscribe=MagicMock(side_effect=[11, 22]))
    helper_calls: list[dict[str, object]] = []

    monkeypatch.setattr(a05, "EventType", event_types)
    monkeypatch.setattr(a05, "HandlerType", handler_types)
    monkeypatch.setattr(a05, "get_event_manager", lambda: event_manager)
    monkeypatch.setattr(
        g05,
        "build_event_subscription_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or (
            SimpleNamespace(
                event_type="risk",
                handler_attr_name="_handle_risk_event",
                handler_id_attr_name="_event_clock_handler_id",
                subscription_name="G05_EventClockDisplay",
                handler_type="sync",
                log_message="risk log",
            ),
            SimpleNamespace(
                event_type="risk_alert",
                handler_attr_name="_handle_risk_alert_event",
                handler_id_attr_name="_risk_alert_handler_id",
                subscription_name="G05_RiskAlertDisplay",
                handler_type="sync",
                log_message="alert log",
            ),
        ),
    )

    SpyderTradingDashboard._subscribe_to_events(dash)

    assert helper_calls == [{"event_type_cls": event_types, "handler_type_cls": handler_types}]
    assert event_manager.subscribe.call_args_list == [
        call("risk", dash._handle_risk_event, name="G05_EventClockDisplay", handler_type="sync"),
        call("risk_alert", dash._handle_risk_alert_event, name="G05_RiskAlertDisplay", handler_type="sync"),
    ]
    assert dash._event_clock_handler_id == 11
    assert dash._risk_alert_handler_id == 22
    assert dash._event_subscriptions_started is True
    dash.logger.info.assert_has_calls([call("risk log"), call("alert log")])
