#!/usr/bin/env python3
"""Pure plan builder for Qt thread shutdown outcomes."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QThreadShutdownPlan:
    """Pure decision output for the next Qt thread shutdown step."""

    action: str
    warning_message: str | None = None
    error_message: str | None = None


def build_qthread_shutdown_plan(
    *,
    stop_succeeded_after_quit: bool,
    stop_succeeded_after_terminate: bool | None,
    label: str,
    wait_ms: int,
    terminate_wait_ms: int,
) -> QThreadShutdownPlan:
    """Decide the next shutdown step after quit/terminate waits."""
    if stop_succeeded_after_quit:
        return QThreadShutdownPlan(action="done")

    if stop_succeeded_after_terminate is None:
        return QThreadShutdownPlan(
            action="terminate_and_wait",
            warning_message=f"{label} did not stop within {wait_ms}ms; terminating thread",
        )

    if stop_succeeded_after_terminate:
        return QThreadShutdownPlan(action="done")

    return QThreadShutdownPlan(
        action="log_error",
        error_message=f"{label} still running after terminate wait of {terminate_wait_ms}ms",
    )
