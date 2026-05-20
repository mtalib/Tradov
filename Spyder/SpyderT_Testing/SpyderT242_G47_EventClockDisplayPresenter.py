#!/usr/bin/env python3
"""Focused tests for G47 event-clock display presenter helpers."""

from Spyder.SpyderG_GUI.SpyderG06_DashboardData import COLORS, EventClockState
from Spyder.SpyderG_GUI.SpyderG47_EventClockDisplayPresenter import (
    build_event_clock_display_presentation,
)


def test_build_event_clock_display_presentation_formats_live_state() -> None:
    presentation = build_event_clock_display_presentation(
        EventClockState(
            state="live",
            enabled=True,
            sources="calendar+manual",
            allowed_strategies=["D03", "D04"],
            blackout_pre_minutes=30,
            blackout_post_minutes=45,
            max_size_multiplier=0.25,
        )
    )

    assert presentation.state_text == "◆ LIVE EVENT"
    assert presentation.state_style == f"color: {COLORS['negative']};"
    assert presentation.compact_text == "EC: ◆ LIVE EVENT"
    assert presentation.compact_style == (
        f"color: {COLORS['negative']}; font-size: 11px; font-weight: normal;"
    )
    assert presentation.policy_text == "Enabled | Sources: calendar+manual"
    assert presentation.windows_text == "Window -30m/+45m | Size 25% | Allowlist D03, D04"
    assert presentation.policy_and_windows_text == (
        "Enabled | Sources: calendar+manual | "
        "Window -30m/+45m | Size 25% | Allowlist D03, D04"
    )
    assert presentation.strategies_text == "Allowlist D03, D04"


def test_build_event_clock_display_presentation_formats_clear_state_without_allowlist() -> None:
    presentation = build_event_clock_display_presentation(
        EventClockState(
            state="clear",
            enabled=False,
            sources="manual",
            allowed_strategies=[],
            blackout_pre_minutes=10,
            blackout_post_minutes=20,
            max_size_multiplier=0.5,
        )
    )

    assert presentation.state_text == "✓ CLEAR"
    assert presentation.compact_text == "EC: CLEAR"
    assert presentation.policy_text == "Disabled | Sources: manual"
    assert presentation.windows_text == "Window -10m/+20m | Size 50% | Allowlist None"
    assert presentation.strategies_text == "Allowlist None"