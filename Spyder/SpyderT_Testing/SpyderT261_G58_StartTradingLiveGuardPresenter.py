#!/usr/bin/env python3
"""Focused tests for G58 live start-trading guard presenter."""

from Spyder.SpyderG_GUI.SpyderG58_StartTradingLiveGuardPresenter import (
    build_start_trading_live_guard_presentation,
)


def test_build_start_trading_live_guard_presentation_formats_api_disconnected_copy() -> None:
    presentation = build_start_trading_live_guard_presentation(
        guard="api_disconnected",
    )

    assert presentation.dialog_title == "API Disconnected"
    assert presentation.dialog_text == "API is disconnected - cannot start trading"
    assert presentation.log_message == "Cannot start trading - API disconnected"


def test_build_start_trading_live_guard_presentation_formats_live_cancelled_copy() -> None:
    presentation = build_start_trading_live_guard_presentation(
        guard="live_cancelled",
    )

    assert presentation.dialog_title == ""
    assert presentation.dialog_text == ""
    assert presentation.log_message == "Live trading start cancelled by user"


def test_build_start_trading_live_guard_presentation_formats_no_live_data_copy() -> None:
    presentation = build_start_trading_live_guard_presentation(
        guard="no_live_data",
    )

    assert presentation.dialog_title == "No Live Data"
    assert presentation.dialog_text == (
        "NO LIVE DATA\n\nCannot start trading without live market data."
    )
    assert presentation.log_message == "Cannot start trading - No live data"
