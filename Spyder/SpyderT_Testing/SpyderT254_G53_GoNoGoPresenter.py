#!/usr/bin/env python3
"""Focused tests for G53 pre-open Go/No-Go presenter."""

from Spyder.SpyderG_GUI.SpyderG53_GoNoGoPresenter import build_go_no_go_presentation


def test_build_go_no_go_presentation_maps_no_to_no_go_and_blocks_start() -> None:
    presentation = build_go_no_go_presentation(
        {
            "decision": "NO",
            "reasons": ["tradier disconnected"],
            "checked_at_et": "2026-05-15T09:31:22-04:00",
        }
    )

    assert presentation.decision == "NO-GO"
    assert presentation.status_text == "Pre-open: NO-GO"
    assert presentation.start_enabled is False
    assert presentation.button_style == "background-color: #c80000;"
    assert presentation.log_message == "Pre-open check: NO-GO — tradier disconnected"


def test_build_go_no_go_presentation_maps_conditional_to_warning_state() -> None:
    presentation = build_go_no_go_presentation(
        {
            "decision": "OK",
            "conditional": True,
            "warnings": ["event window active"],
            "checked_at_et": "2026-05-15T09:31:22-04:00",
        }
    )

    assert presentation.decision == "CONDITIONAL GO"
    assert presentation.status_text == "Pre-open: CONDITIONAL GO"
    assert presentation.start_enabled is True
    assert presentation.button_style == "background-color: #ffa500;"
    assert presentation.warnings == ("event window active",)


def test_build_go_no_go_presentation_maps_ready_to_go() -> None:
    presentation = build_go_no_go_presentation(
        {
            "decision": "OK",
            "checked_at_et": "2026-05-15T09:31:22-04:00",
        }
    )

    assert presentation.decision == "GO"
    assert presentation.status_text == "Pre-open: GO"
    assert presentation.start_enabled is True
    assert presentation.button_style == "background-color: #00c800;"
    assert presentation.log_message == "Pre-open check: GO"
