#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovG_GUI
Module: TradovG61_ReadinessAsyncPresenter.py
Purpose: Pure presentation helpers for async readiness status and failure copy
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReadinessAsyncFailurePresentation:
    """Operator-facing dialog and log copy for async readiness failures."""

    dialog_title: str
    dialog_text: str
    log_message: str


def build_readiness_async_start_log_message() -> str:
    """Return the log message shown when async readiness evaluation begins."""
    return "Running trading readiness evaluation in background..."


def build_readiness_async_already_running_log_message() -> str:
    """Return the log message shown when a readiness worker is already active."""
    return "Trading readiness evaluation already running"


def build_readiness_async_failure_presentation(
    error_message: str,
) -> ReadinessAsyncFailurePresentation:
    """Build dialog and log copy for an async readiness worker failure."""
    normalized_error_message = str(error_message or "Unknown error")
    return ReadinessAsyncFailurePresentation(
        dialog_title="Trading Readiness Error",
        dialog_text=(
            "Trading readiness evaluation failed:\n"
            f"{normalized_error_message}"
        ),
        log_message=(
            f"❌ Trading readiness evaluation failed: {normalized_error_message}"
        ),
    )
