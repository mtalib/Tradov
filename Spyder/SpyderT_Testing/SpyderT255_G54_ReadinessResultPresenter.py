#!/usr/bin/env python3
"""Focused tests for G54 readiness result presenter."""

from Spyder.SpyderG_GUI.SpyderG54_ReadinessResultPresenter import (
    build_readiness_result_log_presentation,
)


def test_build_readiness_result_log_presentation_formats_no_state_lines() -> None:
    presentation = build_readiness_result_log_presentation(
        {
            "decision": "NO",
            "reasons": ["tradier disconnected", "market data disconnected"],
        }
    )

    assert presentation.detail_lines == (
        "  ✗ tradier disconnected",
        "  ✗ market data disconnected",
    )
    assert presentation.summary_line == "NO - tradier disconnected; market data disconnected"


def test_build_readiness_result_log_presentation_formats_conditional_summary() -> None:
    presentation = build_readiness_result_log_presentation(
        {
            "decision": "OK",
            "conditional": True,
            "warnings": ["event window active"],
        }
    )

    assert presentation.detail_lines == ()
    assert presentation.summary_line == "OK - CONDITIONAL: event window active"


def test_build_readiness_result_log_presentation_uses_ready_fallback() -> None:
    presentation = build_readiness_result_log_presentation({"decision": "OK"})

    assert presentation.detail_lines == ()
    assert presentation.summary_line == "OK - READY"