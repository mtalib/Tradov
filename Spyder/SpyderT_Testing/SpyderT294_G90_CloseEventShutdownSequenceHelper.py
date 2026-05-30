#!/usr/bin/env python3
"""Focused tests for G90 closeEvent shutdown sequence helper."""

from Spyder.SpyderG_GUI.SpyderG90_CloseEventShutdownSequenceHelper import (
    build_close_event_shutdown_sequence_plan,
)


def test_build_close_event_shutdown_sequence_plan_returns_pre_qthread_order() -> None:
    plan = build_close_event_shutdown_sequence_plan()

    assert plan.pre_qthread_methods == (
        "_cancel_start_button_loading_transition",
        "_stop_pre_worker_shutdown_timers",
        "_stop_market_worker_for_shutdown",
    )


def test_build_close_event_shutdown_sequence_plan_returns_qthread_specs() -> None:
    plan = build_close_event_shutdown_sequence_plan()

    assert tuple((spec.thread_attr, spec.label, spec.wait_ms, spec.terminate_wait_ms) for spec in plan.qthread_shutdown_specs) == (
        ("market_thread", "market_thread", 5000, 5000),
        ("_paper_thread", "paper_thread", 3000, 5000),
        ("_readiness_worker_thread", "readiness_worker_thread", 3000, 5000),
    )


def test_build_close_event_shutdown_sequence_plan_returns_post_qthread_order() -> None:
    plan = build_close_event_shutdown_sequence_plan()

    assert plan.post_qthread_methods == (
        "_stop_metrics_orchestrator_for_shutdown",
        "_stop_post_worker_shutdown_timers",
        "_save_snapshot_on_shutdown",
        "_log_close_event_shutdown_messages",
    )
