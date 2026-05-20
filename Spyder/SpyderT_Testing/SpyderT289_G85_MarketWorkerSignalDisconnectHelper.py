#!/usr/bin/env python3
"""Focused tests for G85 market-worker signal disconnect helper."""

from Spyder.SpyderG_GUI.SpyderG85_MarketWorkerSignalDisconnectHelper import (
    build_market_worker_signal_disconnect_plan,
)


def test_build_market_worker_signal_disconnect_plan_noops_without_worker() -> None:
    plan = build_market_worker_signal_disconnect_plan(
        has_worker=False,
        disconnectable_signals={
            "fetch_requested": True,
            "fast_fetch_requested": True,
        },
    )

    assert plan.signal_names == ()


def test_build_market_worker_signal_disconnect_plan_selects_only_disconnectable_signals() -> None:
    plan = build_market_worker_signal_disconnect_plan(
        has_worker=True,
        disconnectable_signals={
            "fetch_requested": True,
            "fast_fetch_requested": False,
        },
    )

    assert plan.signal_names == ("fetch_requested",)


def test_build_market_worker_signal_disconnect_plan_preserves_known_order() -> None:
    plan = build_market_worker_signal_disconnect_plan(
        has_worker=True,
        disconnectable_signals={
            "fetch_requested": True,
            "fast_fetch_requested": True,
        },
    )

    assert plan.signal_names == ("fetch_requested", "fast_fetch_requested")