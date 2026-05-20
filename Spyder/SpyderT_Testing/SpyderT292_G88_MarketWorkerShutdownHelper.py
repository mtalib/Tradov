#!/usr/bin/env python3
"""Focused tests for G88 market-worker shutdown helper."""

from Spyder.SpyderG_GUI.SpyderG88_MarketWorkerShutdownHelper import (
    build_market_worker_shutdown_plan,
)


def test_build_market_worker_shutdown_plan_noops_without_worker() -> None:
    plan = build_market_worker_shutdown_plan(
        has_worker=False,
        has_stop_method=False,
    )

    assert plan.action == "noop"


def test_build_market_worker_shutdown_plan_noops_without_stop_method() -> None:
    plan = build_market_worker_shutdown_plan(
        has_worker=True,
        has_stop_method=False,
    )

    assert plan.action == "noop"


def test_build_market_worker_shutdown_plan_stops_when_worker_is_supported() -> None:
    plan = build_market_worker_shutdown_plan(
        has_worker=True,
        has_stop_method=True,
    )

    assert plan.action == "disconnect_and_stop"
