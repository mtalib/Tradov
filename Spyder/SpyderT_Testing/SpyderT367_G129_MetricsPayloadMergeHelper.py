#!/usr/bin/env python3
"""Focused tests for the G129 metrics payload merge helper."""

from __future__ import annotations

import math

from Spyder.SpyderG_GUI.SpyderG129_MetricsPayloadMergeHelper import (
    merge_metrics_payload,
)


def test_merge_metrics_payload_preserves_existing_values_when_update_is_missing() -> None:
    result = merge_metrics_payload(
        {"SPY": {"value": 1.0, "details": {"status": "cached"}}},
        {"SPY": {"value": None, "details": {}, "phase": "live"}},
    )

    assert result == {
        "SPY": {"value": 1.0, "details": {"status": "cached"}, "phase": "live"}
    }


def test_merge_metrics_payload_rejects_nan_and_empty_string_updates() -> None:
    result = merge_metrics_payload(
        {"SPY": {"value": 1.0, "status": "cached"}},
        {"SPY": {"value": math.nan, "status": ""}},
    )

    assert result == {"SPY": {"value": 1.0, "status": "cached"}}


def test_merge_metrics_payload_adds_new_valid_entries() -> None:
    result = merge_metrics_payload(
        None,
        {
            "SPY": {"value": 1.0, "status": "live"},
            "QQQ": "invalid",
        },
    )

    assert result == {"SPY": {"value": 1.0, "status": "live"}}