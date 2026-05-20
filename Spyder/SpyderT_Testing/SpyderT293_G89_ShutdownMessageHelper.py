#!/usr/bin/env python3
"""Focused tests for G89 dashboard shutdown message helper."""

from Spyder.SpyderG_GUI.SpyderG89_ShutdownMessageHelper import (
    build_dashboard_shutdown_message_plan,
)


def test_build_dashboard_shutdown_message_plan_returns_close_event_messages_in_order() -> None:
    plan = build_dashboard_shutdown_message_plan()

    assert plan.close_event_system_messages == (
        "🔥 Enhanced Trading Dashboard shutting down...",
        "Dashboard session ended with heartbeat monitoring",
    )


def test_build_dashboard_shutdown_message_plan_returns_snapshot_message() -> None:
    plan = build_dashboard_shutdown_message_plan()

    assert plan.snapshot_system_message == "📦 Snapshot saved for PAPER+LIVE"
