#!/usr/bin/env python3
"""Focused tests for G65 readiness event-clock snapshot helper."""

from types import SimpleNamespace

from Spyder.SpyderG_GUI.SpyderG65_ReadinessEventClockSnapshotHelper import (
    build_readiness_event_clock_snapshot,
)


def test_build_readiness_event_clock_snapshot_defaults_when_state_is_absent() -> None:
    snapshot = build_readiness_event_clock_snapshot(None)

    assert snapshot.enabled is True
    assert snapshot.state == "clear"


def test_build_readiness_event_clock_snapshot_normalizes_enabled_and_state() -> None:
    snapshot = build_readiness_event_clock_snapshot(
        SimpleNamespace(enabled=False, state="post")
    )

    assert snapshot.enabled is False
    assert snapshot.state == "post"
