#!/usr/bin/env python3
"""Focused tests for G108 custom-metric breadth dialog sync helper."""

from __future__ import annotations

import math

from Spyder.SpyderG_GUI.SpyderG108_CustomMetricBreadthDialogSyncHelper import (
    build_custom_metric_breadth_dialog_payload,
)


def test_build_custom_metric_breadth_dialog_payload_returns_payload() -> None:
    payload = build_custom_metric_breadth_dialog_payload(
        {
            "TICK": {"value": 1200.0},
            "ADD": {"value": 250.0},
            "TRIN": {"value": 0.86},
            "NYMO": {"value": -12.0},
            "BREADTH_REGIME": {"value": "risk_on"},
        }
    )

    assert payload == {
        "tick": 1200.0,
        "add": 250.0,
        "trin": 0.86,
        "nymo": -12.0,
        "breadth_regime": "risk_on",
    }


def test_build_custom_metric_breadth_dialog_payload_rejects_missing_or_all_nan_core_values() -> None:
    assert build_custom_metric_breadth_dialog_payload(
        {
            "TICK": "bad",
            "ADD": {"value": 250.0},
            "TRIN": {"value": 0.86},
        }
    ) is None

    assert build_custom_metric_breadth_dialog_payload(
        {
            "TICK": {"value": float("nan")},
            "ADD": {"value": float("nan")},
            "TRIN": {"value": float("nan")},
            "NYMO": {"value": -12.0},
        }
    ) is None


def test_build_custom_metric_breadth_dialog_payload_marks_stale_core_values_unavailable() -> None:
    payload = build_custom_metric_breadth_dialog_payload(
        {
            "TICK": {"value": 1200.0, "stale": True},
            "ADD": {"value": 250.0},
            "TRIN": {"value": 0.86},
            "NYMO": {"value": -12.0},
            "BREADTH_REGIME": {"value": "risk_on", "stale": True},
        }
    )

    assert payload is not None
    assert math.isnan(payload["tick"])
    assert math.isnan(payload["add"])
    assert math.isnan(payload["trin"])
    assert math.isnan(payload["nymo"])
    assert payload["breadth_regime"] == ""
    assert payload["stale"] is True
