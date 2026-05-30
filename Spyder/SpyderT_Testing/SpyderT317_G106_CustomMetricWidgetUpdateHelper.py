#!/usr/bin/env python3
"""Focused tests for G106 custom-metric widget update helper."""

from __future__ import annotations

import pytest

from Spyder.SpyderG_GUI.SpyderG106_CustomMetricWidgetUpdateHelper import (
    build_custom_metric_widget_update_plan,
)


def test_build_custom_metric_widget_update_plan_uses_precomputed_change() -> None:
    plan = build_custom_metric_widget_update_plan(
        entry={
            "value": 10.0,
            "change": 2.0,
            "details": {"status": "live", "details": {"phase": "active"}},
        },
        scale=1.0,
        previous_value=None,
    )

    assert plan is not None
    assert plan.payload == {
        "last": 10.0,
        "change": 2.0,
        "change_pct": 25.0,
        "status": "live",
        "phase": "active",
    }
    assert plan.next_previous_value is None


def test_build_custom_metric_widget_update_plan_uses_previous_value_and_sets_next_prev() -> None:
    plan = build_custom_metric_widget_update_plan(
        entry={"value": 10.0, "details": "bad"},
        scale=2.0,
        previous_value=16.0,
    )

    assert plan is not None
    assert plan.payload == {
        "last": 20.0,
        "change": 4.0,
        "change_pct": pytest.approx(25.0),
        "status": None,
        "phase": None,
    }
    assert plan.next_previous_value == 20.0


def test_build_custom_metric_widget_update_plan_rejects_invalid_or_nan_entries() -> None:
    assert build_custom_metric_widget_update_plan(
        entry=None,
        scale=1.0,
        previous_value=None,
    ) is None
    assert build_custom_metric_widget_update_plan(
        entry={"value": float("nan")},
        scale=1.0,
        previous_value=None,
    ) is None
    assert build_custom_metric_widget_update_plan(
        entry={"value": 1.0, "stale": True},
        scale=1.0,
        previous_value=None,
    ) is None
