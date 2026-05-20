#!/usr/bin/env python3
"""Focused tests for G59 start-trading failure presenter."""

from Spyder.SpyderG_GUI.SpyderG59_StartTradingFailurePresenter import (
    build_start_trading_failure_presentation,
)


def test_build_start_trading_failure_presentation_formats_fail_closed_copy() -> None:
    presentation = build_start_trading_failure_presentation()

    assert presentation.dialog_title == "Start Failed"
    assert presentation.dialog_text == (
        "Unified backend session failed to start.\n"
        "Trading remains stopped (fail-closed)."
    )
