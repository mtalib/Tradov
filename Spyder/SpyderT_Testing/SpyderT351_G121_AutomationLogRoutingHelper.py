#!/usr/bin/env python3
"""Focused tests for G121 automation-log routing helper."""

from Spyder.SpyderG_GUI.SpyderG121_AutomationLogRoutingHelper import (
    build_automation_log_routing_plan,
)


def test_build_automation_log_routing_plan_formats_non_autonomous_events_for_system_log() -> None:
    plan = build_automation_log_routing_plan(
        message="hello",
        event_type="legacy_status",
        source="dashboard",
        autonomous_event_type_allowlist={"AGENT_DECISION"},
    )

    assert plan.route == "system"
    assert plan.formatted_message == "[LEGACY_STATUS] hello"


def test_build_automation_log_routing_plan_formats_autonomous_events_for_automation_log() -> None:
    plan = build_automation_log_routing_plan(
        message="entered trade",
        event_type="agent_decision",
        source="x16",
        autonomous_event_type_allowlist={"AGENT_DECISION"},
    )

    assert plan.route == "automation"
    assert plan.formatted_message == "AGENT_DECISION [X16] entered trade"


def test_build_automation_log_routing_plan_uses_default_values_when_inputs_are_blank() -> None:
    plan = build_automation_log_routing_plan(
        message="heartbeat",
        event_type="",
        source="",
        autonomous_event_type_allowlist={"AGENT_OBSERVATION"},
    )

    assert plan.route == "system"
    assert plan.formatted_message == "[LEGACY_STATUS] heartbeat"