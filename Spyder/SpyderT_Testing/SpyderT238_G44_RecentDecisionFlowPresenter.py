#!/usr/bin/env python3
"""Focused tests for G44 recent decision-flow presenter helpers."""

from Spyder.SpyderG_GUI.SpyderG44_RecentDecisionFlowPresenter import (
    build_recent_decision_flow_panel_presentation,
    format_recent_decision_events,
)


def test_format_recent_decision_events_formats_timestamps_and_detail_lines() -> None:
    records = [
        {
            "ts_utc": "2026-05-13T14:35:00Z",
            "event": "dispatch_rejected",
            "detail": "Daily trade limit reached",
        },
        {
            "ts_utc": "2026-05-13 14:33:00",
            "event": "dispatch_submitted",
            "detail": "submitted",
        },
        {
            "ts_utc": "bad-timestamp",
            "reason": "session_window:outside_primary_window",
        },
    ]

    assert format_recent_decision_events(records) == (
        "14:35:00 | dispatch_rejected | Daily trade limit reached\n"
        "14:33:00 | dispatch_submitted | submitted\n"
        "bad-time | session_window:outside_primary_window"
    )


def test_format_recent_decision_events_returns_dash_for_empty_or_invalid_records() -> None:
    assert format_recent_decision_events([]) == "-"
    assert format_recent_decision_events(None) == "-"
    assert format_recent_decision_events(["invalid"]) == "-"


def test_build_recent_decision_flow_panel_presentation_uses_tooltip_fallback() -> None:
    presentation = build_recent_decision_flow_panel_presentation(
        {
            "decision_log": "",
            "dispatch": [],
            "drops": [
                {
                    "ts_utc": "2026-05-13T14:36:00Z",
                    "event": "signal_dropped",
                    "reason": "session_window:outside_primary_window",
                }
            ],
        }
    )

    assert presentation.dispatch_text == "-"
    assert presentation.drop_text == (
        "14:36:00 | signal_dropped | session_window:outside_primary_window"
    )
    assert presentation.tooltip == "Decision log unavailable"
