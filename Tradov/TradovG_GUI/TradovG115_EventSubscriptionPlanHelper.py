#!/usr/bin/env python3
"""Pure subscription planning for dashboard event wiring."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EventSubscriptionSpec:
    """Single event subscription descriptor for the dashboard."""

    event_type: object
    handler_attr_name: str
    handler_id_attr_name: str
    subscription_name: str
    handler_type: object
    log_message: str


def build_event_subscription_plan(
    *,
    event_type_cls: object,
    handler_type_cls: object,
) -> tuple[EventSubscriptionSpec, ...]:
    """Return the dashboard event subscription specs."""
    risk_alert_event_type = getattr(event_type_cls, "RISK_ALERT", event_type_cls.ALERT)
    risk_alert_label = getattr(risk_alert_event_type, "value", str(risk_alert_event_type))

    return (
        EventSubscriptionSpec(
            event_type=event_type_cls.RISK,
            handler_attr_name="_handle_risk_event",
            handler_id_attr_name="_event_clock_handler_id",
            subscription_name="G05_EventClockDisplay",
            handler_type=handler_type_cls.SYNC,
            log_message="✅ Subscribed to RISK events for event-clock display",
        ),
        EventSubscriptionSpec(
            event_type=event_type_cls.TRADE,
            handler_attr_name="_handle_trade_event",
            handler_id_attr_name="_execution_telemetry_handler_id",
            subscription_name="G05_ExecutionHealth",
            handler_type=handler_type_cls.SYNC,
            log_message="✅ Subscribed to TRADE events for execution-health display",
        ),
        EventSubscriptionSpec(
            event_type=event_type_cls.POSITION_UPDATED,
            handler_attr_name="_handle_position_updated_event",
            handler_id_attr_name="_position_update_handler_id",
            subscription_name="G05_PaperPositionRefresh",
            handler_type=handler_type_cls.SYNC,
            log_message="✅ Subscribed to POSITION_UPDATED events for paper position refresh",
        ),
        EventSubscriptionSpec(
            event_type=risk_alert_event_type,
            handler_attr_name="_handle_risk_alert_event",
            handler_id_attr_name="_risk_alert_handler_id",
            subscription_name="G05_RiskAlertDisplay",
            handler_type=handler_type_cls.SYNC,
            log_message=f"✅ Subscribed to {risk_alert_label} events for entry-block visibility",
        ),
    )
