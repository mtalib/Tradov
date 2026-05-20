#!/usr/bin/env python3
"""Focused tests for G61 async readiness presenter."""

from Spyder.SpyderG_GUI.SpyderG61_ReadinessAsyncPresenter import (
    build_readiness_async_already_running_log_message,
    build_readiness_async_failure_presentation,
    build_readiness_async_start_log_message,
)


def test_build_readiness_async_start_log_message_returns_expected_copy() -> None:
    assert (
        build_readiness_async_start_log_message()
        == "Running trading readiness evaluation in background..."
    )


def test_build_readiness_async_already_running_log_message_returns_expected_copy() -> None:
    assert (
        build_readiness_async_already_running_log_message()
        == "Trading readiness evaluation already running"
    )


def test_build_readiness_async_failure_presentation_formats_dialog_and_log() -> None:
    presentation = build_readiness_async_failure_presentation("timeout")

    assert presentation.dialog_title == "Trading Readiness Error"
    assert presentation.dialog_text == "Trading readiness evaluation failed:\ntimeout"
    assert presentation.log_message == "❌ Trading readiness evaluation failed: timeout"
