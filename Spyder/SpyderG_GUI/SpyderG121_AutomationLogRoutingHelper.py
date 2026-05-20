#!/usr/bin/env python3
"""Pure routing and formatting for dashboard automation logs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AutomationLogRoutingPlan:
    """Pure routing decision for an automation log message."""

    route: str
    formatted_message: str


def build_automation_log_routing_plan(
    *,
    message: str,
    event_type: str,
    source: str,
    autonomous_event_type_allowlist: set[str],
) -> AutomationLogRoutingPlan:
    """Decide whether an automation message stays autonomous or falls back to system log."""
    normalized_type = str(event_type or "LEGACY_STATUS").strip().upper()
    if normalized_type not in autonomous_event_type_allowlist:
        return AutomationLogRoutingPlan(
            route="system",
            formatted_message=f"[{normalized_type}] {message}",
        )

    normalized_source = str(source or "dashboard").strip().upper()
    return AutomationLogRoutingPlan(
        route="automation",
        formatted_message=f"{normalized_type} [{normalized_source}] {message}",
    )
