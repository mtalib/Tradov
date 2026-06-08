#!/usr/bin/env python3
"""Pure shutdown message copy for dashboard close and snapshot save paths."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DashboardShutdownMessagePlan:
    """Pure presentation output for dashboard shutdown messaging."""

    close_event_system_messages: tuple[str, ...]
    snapshot_system_message: str


def build_dashboard_shutdown_message_plan() -> DashboardShutdownMessagePlan:
    """Return the fixed dashboard shutdown message copy."""
    return DashboardShutdownMessagePlan(
        close_event_system_messages=(
            "🔥 Enhanced Trading Dashboard shutting down...",
            "Dashboard session ended with heartbeat monitoring",
        ),
        snapshot_system_message="📦 Snapshot saved for PAPER+LIVE",
    )
