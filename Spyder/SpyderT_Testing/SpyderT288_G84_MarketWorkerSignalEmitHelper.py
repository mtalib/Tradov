#!/usr/bin/env python3
"""Focused tests for G84 market-worker signal emit helper."""

from Spyder.SpyderG_GUI.SpyderG84_MarketWorkerSignalEmitHelper import (
    build_market_worker_signal_emit_plan,
)


def test_build_market_worker_signal_emit_plan_noops_without_worker() -> None:
    plan = build_market_worker_signal_emit_plan(
        has_worker=False,
        has_signal=False,
        has_emit_method=False,
    )

    assert plan.action == "noop"


def test_build_market_worker_signal_emit_plan_noops_without_signal_or_emit() -> None:
    plan = build_market_worker_signal_emit_plan(
        has_worker=True,
        has_signal=True,
        has_emit_method=False,
    )

    assert plan.action == "noop"


def test_build_market_worker_signal_emit_plan_emits_when_available() -> None:
    plan = build_market_worker_signal_emit_plan(
        has_worker=True,
        has_signal=True,
        has_emit_method=True,
    )

    assert plan.action == "emit"
