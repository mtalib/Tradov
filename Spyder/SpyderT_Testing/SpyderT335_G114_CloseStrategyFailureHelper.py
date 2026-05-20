#!/usr/bin/env python3
"""Focused tests for G114 close-strategy failure helper."""

from __future__ import annotations

from Spyder.SpyderG_GUI.SpyderG114_CloseStrategyFailureHelper import (
    build_close_strategy_failure_plan,
)


def test_build_close_strategy_failure_plan_formats_tradier_api_message() -> None:
    plan = build_close_strategy_failure_plan(
        failure_kind="tradier_api",
        strategy_name="Iron Condor",
        error_text="rate limit",
    )

    assert plan.log_message == "❌ Tradier API error closing Iron Condor: rate limit"
    assert plan.dialog_title == "Close Strategy Failed"
    assert plan.dialog_text == "Tradier API error while closing 'Iron Condor':\n\nrate limit"


def test_build_close_strategy_failure_plan_formats_validation_and_unexpected_messages() -> None:
    validation = build_close_strategy_failure_plan(
        failure_kind="validation",
        strategy_name="Iron Condor",
        error_text="missing legs",
    )
    unexpected = build_close_strategy_failure_plan(
        failure_kind="unexpected",
        strategy_name="Iron Condor",
        error_text="boom",
    )

    assert validation.log_message == "❌ Validation error closing Iron Condor: missing legs"
    assert validation.dialog_text == "Could not build close orders for 'Iron Condor':\n\nmissing legs"
    assert unexpected.log_message == "❌ Unexpected error closing Iron Condor: boom"
    assert unexpected.dialog_text == "Unexpected error while closing 'Iron Condor':\n\nboom"
