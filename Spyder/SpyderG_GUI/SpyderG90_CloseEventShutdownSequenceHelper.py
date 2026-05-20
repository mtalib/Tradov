#!/usr/bin/env python3
"""Pure shutdown sequence plan for dashboard closeEvent orchestration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QThreadShutdownSpec:
    """Pure QThread shutdown call specification."""

    thread_attr: str
    label: str
    wait_ms: int = 3000
    terminate_wait_ms: int = 5000


@dataclass(frozen=True)
class CloseEventShutdownSequencePlan:
    """Pure orchestration plan for dashboard closeEvent shutdown."""

    pre_qthread_methods: tuple[str, ...]
    qthread_shutdown_specs: tuple[QThreadShutdownSpec, ...]
    post_qthread_methods: tuple[str, ...]


def build_close_event_shutdown_sequence_plan() -> CloseEventShutdownSequencePlan:
    """Return the fixed shutdown sequence for the dashboard closeEvent."""
    return CloseEventShutdownSequencePlan(
        pre_qthread_methods=(
            "_cancel_start_button_loading_transition",
            "_stop_pre_worker_shutdown_timers",
            "_stop_market_worker_for_shutdown",
        ),
        qthread_shutdown_specs=(
            QThreadShutdownSpec(
                thread_attr="market_thread",
                label="market_thread",
                wait_ms=1500,
                terminate_wait_ms=2000,
            ),
            QThreadShutdownSpec(
                thread_attr="_paper_thread",
                label="paper_thread",
            ),
            QThreadShutdownSpec(
                thread_attr="_readiness_worker_thread",
                label="readiness_worker_thread",
            ),
        ),
        post_qthread_methods=(
            "_stop_metrics_orchestrator_for_shutdown",
            "_stop_post_worker_shutdown_timers",
            "_save_snapshot_on_shutdown",
            "_log_close_event_shutdown_messages",
        ),
    )
