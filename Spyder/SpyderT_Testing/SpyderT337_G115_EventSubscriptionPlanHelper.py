#!/usr/bin/env python3
"""Focused tests for G115 event subscription plan helper."""

from __future__ import annotations

from enum import Enum

from Spyder.SpyderG_GUI.SpyderG115_EventSubscriptionPlanHelper import (
    build_event_subscription_plan,
)


class _EventTypeWithRiskAlert(Enum):
    RISK = "risk"
    TRADE = "trade"
    POSITION_UPDATED = "position_updated"
    ALERT = "alert"
    RISK_ALERT = "risk_alert"


class _EventTypeWithoutRiskAlert(Enum):
    RISK = "risk"
    TRADE = "trade"
    POSITION_UPDATED = "position_updated"
    ALERT = "alert"


class _HandlerType(Enum):
    SYNC = "sync"


def test_build_event_subscription_plan_uses_risk_alert_when_available() -> None:
    specs = build_event_subscription_plan(
        event_type_cls=_EventTypeWithRiskAlert,
        handler_type_cls=_HandlerType,
    )

    assert len(specs) == 4
    assert specs[0].event_type is _EventTypeWithRiskAlert.RISK
    assert specs[0].handler_attr_name == "_handle_risk_event"
    assert specs[3].event_type is _EventTypeWithRiskAlert.RISK_ALERT
    assert specs[3].log_message == "✅ Subscribed to risk_alert events for entry-block visibility"


def test_build_event_subscription_plan_falls_back_to_alert_when_risk_alert_missing() -> None:
    specs = build_event_subscription_plan(
        event_type_cls=_EventTypeWithoutRiskAlert,
        handler_type_cls=_HandlerType,
    )

    assert specs[3].event_type is _EventTypeWithoutRiskAlert.ALERT
    assert specs[3].handler_id_attr_name == "_risk_alert_handler_id"
    assert specs[3].log_message == "✅ Subscribed to alert events for entry-block visibility"