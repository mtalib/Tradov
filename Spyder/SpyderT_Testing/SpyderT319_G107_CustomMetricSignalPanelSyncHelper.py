#!/usr/bin/env python3
"""Focused tests for G107 custom-metric signal-panel sync helper."""

from __future__ import annotations

from Spyder.SpyderG_GUI.SpyderG107_CustomMetricSignalPanelSyncHelper import (
    build_custom_metric_signal_panel_sync_plan,
)


def test_build_custom_metric_signal_panel_sync_plan_returns_regime_inputs_and_live_data() -> None:
    plan = build_custom_metric_signal_panel_sync_plan(
        metrics={
            "SWAN": {"value": 2.1},
            "DIX": {"value": 43.5},
            "SKEW": {"value": 124.0},
            "GEX": {"value": 1.25},
            "NYMO": {"value": -20.0},
            "TICK": {"value": 1100.0},
        },
        metric_routing={
            "GEX": ("GEX", 1.0),
            "NYMO": ("NYMO", 1.0),
            "TICK": ("TICK", 1.0),
        },
        regime_value="RISK OFF",
    )

    assert plan.regime_value == "RISK OFF"
    assert plan.swan == 2.1
    assert plan.dix == 43.5
    assert plan.skew == 124.0
    assert plan.gex == 1.25
    assert plan.live_data == {"GEX": 1.25, "NYMO": -20.0}


def test_build_custom_metric_signal_panel_sync_plan_uses_defaults_and_skips_bad_live_values() -> None:
    plan = build_custom_metric_signal_panel_sync_plan(
        metrics={
            "SWAN": {"value": float("nan")},
            "GEX": {"value": float("nan")},
            "SKEW": {"value": 130.0},
            "ADD": {"value": 25.0},
            "VRP": {"value": None},
            "WRS": "bad",
        },
        metric_routing={
            "ADD": ("ADD", 1.0),
            "GEX": ("GEX", 1.0),
            "VRP": ("VRP", 1.0),
            "WRS": ("WRS", 100.0),
        },
        regime_value="—",
    )

    assert plan.regime_value == "—"
    assert plan.swan == 1.9
    assert plan.dix == 42.0
    assert plan.skew == 130.0
    assert plan.gex == 0.0
    assert plan.live_data == {}


def test_build_custom_metric_signal_panel_sync_plan_clears_stale_live_keys() -> None:
    plan = build_custom_metric_signal_panel_sync_plan(
        metrics={
            "SWAN": {"value": 2.1, "stale": True},
            "DIX": {"value": 43.5},
            "GEX": {"value": 1.25, "stale": True},
            "NYMO": {"value": -20.0},
        },
        metric_routing={
            "GEX": ("GEX", 1.0),
            "NYMO": ("NYMO", 1.0),
            "SWAN": ("SWAN", 1.0),
        },
        regime_value="RISK OFF",
    )

    assert plan.regime_value == "RISK OFF"
    assert plan.swan == 1.9
    assert plan.dix == 43.5
    assert plan.skew == 120.0
    assert plan.gex == 0.0
    assert plan.live_data == {"NYMO": -20.0}
    assert plan.clear_live_keys == ("GEX", "SWAN")
