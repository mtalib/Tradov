#!/usr/bin/env python3
"""Focused tests for G60 readiness start-block presenter."""

from Spyder.SpyderG_GUI.SpyderG60_ReadinessStartBlockPresenter import (
    build_readiness_start_block_presentation,
)


def test_build_readiness_start_block_presentation_formats_title_body_and_log() -> None:
    presentation = build_readiness_start_block_presentation(
        mode_label="paper",
        reasons=["broker disconnected", "quotes stale"],
    )

    assert presentation.dialog_title == "PAPER Start Blocked (NO)"
    assert presentation.dialog_text == (
        "Trading readiness evaluation returned NO.\n\n"
        "Reasons:\n- broker disconnected\n- quotes stale"
    )
    assert presentation.log_message == "❌ PAPER start blocked by readiness evaluation"


def test_build_readiness_start_block_presentation_uses_unknown_reason_fallback() -> None:
    presentation = build_readiness_start_block_presentation(
        mode_label="live",
        reasons=[],
    )

    assert presentation.dialog_title == "LIVE Start Blocked (NO)"
    assert presentation.dialog_text == (
        "Trading readiness evaluation returned NO.\n\n"
        "Reasons:\n- Unknown readiness failure"
    )
    assert presentation.log_message == "❌ LIVE start blocked by readiness evaluation"
