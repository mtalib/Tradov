#!/usr/bin/env python3
"""Focused tests for G81 market-worker slot invoke helper."""

from Spyder.SpyderG_GUI.SpyderG81_MarketWorkerSlotInvokeHelper import (
    build_market_worker_slot_invoke_plan,
)


def test_build_market_worker_slot_invoke_plan_returns_false_without_worker() -> None:
    plan = build_market_worker_slot_invoke_plan(
        has_worker=False,
        has_callable_slot=False,
        thread_running=False,
        slot_name="pause_periodic_updates",
    )

    assert plan.action == "return_false"
    assert plan.warning_message is None


def test_build_market_worker_slot_invoke_plan_warns_for_missing_slot() -> None:
    plan = build_market_worker_slot_invoke_plan(
        has_worker=True,
        has_callable_slot=False,
        thread_running=True,
        slot_name="pause_periodic_updates",
    )

    assert plan.action == "warn_and_return_false"
    assert plan.warning_message == "Market worker slot unavailable: pause_periodic_updates"


def test_build_market_worker_slot_invoke_plan_calls_direct_when_thread_not_running() -> None:
    plan = build_market_worker_slot_invoke_plan(
        has_worker=True,
        has_callable_slot=True,
        thread_running=False,
        slot_name="pause_periodic_updates",
    )

    assert plan.action == "call_direct"
    assert plan.warning_message is None


def test_build_market_worker_slot_invoke_plan_queues_when_thread_running() -> None:
    plan = build_market_worker_slot_invoke_plan(
        has_worker=True,
        has_callable_slot=True,
        thread_running=True,
        slot_name="pause_periodic_updates",
    )

    assert plan.action == "queue_invoke"
    assert plan.warning_message is None
