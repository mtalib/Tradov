#!/usr/bin/env python3
"""Focused tests for G57 start-trading precheck presenter."""

from Spyder.SpyderG_GUI.SpyderG57_StartTradingPrecheckPresenter import (
    build_start_trading_precheck_presentation,
)


def test_build_start_trading_precheck_presentation_formats_mode_not_armed_copy() -> None:
    presentation = build_start_trading_precheck_presentation(
        guard="mode_not_armed",
        mode_label="paper",
    )

    assert presentation.dialog_title == "PAPER Trading Not Enabled"
    assert (
        presentation.dialog_text
        == "PAPER trading is not armed. Click ENABLE PAPER before starting."
    )
    assert presentation.log_message == "Start blocked: PAPER trading is not enabled"


def test_build_start_trading_precheck_presentation_formats_market_data_loading_copy() -> None:
    presentation = build_start_trading_precheck_presentation(
        guard="market_data_loading",
        queued_start_requested=False,
    )

    assert presentation.dialog_title == "Fresh Market Data Loading"
    assert presentation.dialog_text == (
        "Fresh market data is still loading.\n\n"
        "Trading will begin automatically after fresh market data is fetched and all startup checks pass."
    )
    assert presentation.log_message == (
        "⏳ Start requested — trading will begin automatically after fresh market data is fetched and all startup checks pass"
    )


def test_build_start_trading_precheck_presentation_formats_market_closed_copy() -> None:
    presentation = build_start_trading_precheck_presentation(
        guard="market_closed",
    )

    assert presentation.dialog_title == "Market Closed"
    assert presentation.dialog_text == (
        "Trading start blocked: market is closed (outside regular trading hours)."
    )
    assert presentation.log_message == "⛔ Trading start blocked: market is closed (outside RTH)"
