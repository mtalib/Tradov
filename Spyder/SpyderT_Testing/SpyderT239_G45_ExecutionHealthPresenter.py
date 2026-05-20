#!/usr/bin/env python3
"""Focused tests for G45 execution-health presenter helpers."""

from Spyder.SpyderG_GUI.SpyderG45_ExecutionHealthPresenter import (
    build_execution_health_presentation,
)


def test_build_execution_health_presentation_formats_latest_metrics_and_ratios() -> None:
    presentation = build_execution_health_presentation(
        [
            {
                "slippage_bps": 7.5,
                "fill_latency_ms": 240.0,
                "partial_fill_ratio": 0.5,
                "reject_flag": False,
            },
            {
                "slippage_bps": 3.2,
                "fill_latency_ms": 125.0,
                "partial_fill_ratio": 0.25,
                "reject_flag": True,
            },
        ]
    )

    assert presentation.slippage_bps_text == "3.2 bps"
    assert presentation.fill_latency_text == "125 ms"
    assert presentation.reject_rate_text == "50.0%"
    assert presentation.partial_fill_text == "37.5%"


def test_build_execution_health_presentation_returns_dashes_for_empty_samples() -> None:
    presentation = build_execution_health_presentation([])

    assert presentation.slippage_bps_text == "-"
    assert presentation.fill_latency_text == "-"
    assert presentation.reject_rate_text == "-"
    assert presentation.partial_fill_text == "-"


def test_build_execution_health_presentation_ignores_invalid_records() -> None:
    presentation = build_execution_health_presentation(
        [
            "invalid",
            {
                "partial_fill_ratio": 0.2,
                "reject_flag": False,
            },
        ]
    )

    assert presentation.slippage_bps_text == "-"
    assert presentation.fill_latency_text == "-"
    assert presentation.reject_rate_text == "0.0%"
    assert presentation.partial_fill_text == "20.0%"