#!/usr/bin/env python3
"""Focused tests for G63 readiness snapshot helpers."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from Spyder.SpyderG_GUI.SpyderG63_ReadinessSnapshotHelper import (
    build_preopen_check_snapshot_payload,
    normalize_readiness_data_status_label,
)


def test_normalize_readiness_data_status_label_strips_and_uppercases() -> None:
    assert normalize_readiness_data_status_label("  live - real  ") == "LIVE - REAL"


def test_build_preopen_check_snapshot_payload_marks_market_hours_for_weekday_rth() -> None:
    checked_at = datetime(2026, 5, 15, 9, 31, tzinfo=ZoneInfo("America/New_York"))

    snapshot = build_preopen_check_snapshot_payload(
        startup_state={"seeded": True},
        api_connected=True,
        mkt_data_connected=True,
        data_status_label="LIVE",
        event_clock_enabled=True,
        event_clock_state="clear",
        checked_at_et=checked_at,
    )

    assert snapshot["startup_state"] == {"seeded": True}
    assert snapshot["api_connected"] is True
    assert snapshot["mkt_data_connected"] is True
    assert snapshot["data_status_label"] == "LIVE"
    assert snapshot["event_clock_enabled"] is True
    assert snapshot["event_clock_state"] == "clear"
    assert snapshot["is_weekend"] is False
    assert snapshot["is_market_hours"] is True
    assert snapshot["checked_at_et"] == checked_at.isoformat()


def test_build_preopen_check_snapshot_payload_marks_weekend_outside_hours() -> None:
    checked_at = datetime(2026, 5, 16, 9, 31, tzinfo=ZoneInfo("America/New_York"))

    snapshot = build_preopen_check_snapshot_payload(
        startup_state={},
        api_connected=False,
        mkt_data_connected=False,
        data_status_label="EOD",
        event_clock_enabled=False,
        event_clock_state="post",
        checked_at_et=checked_at,
    )

    assert snapshot["is_weekend"] is True
    assert snapshot["is_market_hours"] is False
    assert snapshot["checked_at_et"] == checked_at.isoformat()
