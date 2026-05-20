#!/usr/bin/env python3
"""Focused tests for G105 PAPER-to-LIVE switch helper."""

from __future__ import annotations

from Spyder.SpyderG_GUI.SpyderG105_PaperToLiveSwitchHelper import (
    build_paper_to_live_switch_plan,
)


def test_build_paper_to_live_switch_plan_returns_critical_dialog_copy() -> None:
    plan = build_paper_to_live_switch_plan()

    assert plan.api_disconnected.dialog_title == "Tradier EXEC Not Connected"
    assert "You must connect to Tradier EXEC before switching to LIVE trading." in plan.api_disconnected.dialog_text
    assert plan.market_data_disconnected.dialog_title == "No Data Feed Connected"
    assert "You must connect a market data feed (TRADIER DATA)" in plan.market_data_disconnected.dialog_text


def test_build_paper_to_live_switch_plan_returns_confirmation_bundle() -> None:
    plan = build_paper_to_live_switch_plan()

    assert plan.confirmation.required_phrase == "I WANT TO SWITCH TO REAL LIVE TRADING"
    assert plan.confirmation.dialog_title == "⚠️  ENABLE REAL — CONFIRMATION REQUIRED"
    assert plan.confirmation.header_text == "⚠️  YOU ARE ARMING REAL LIVE TRADING"
    assert plan.confirmation.confirm_button_text == "ENABLE REAL LIVE TRADING"
    assert plan.confirmation.declined_log_message == "Switch to LIVE cancelled by user"