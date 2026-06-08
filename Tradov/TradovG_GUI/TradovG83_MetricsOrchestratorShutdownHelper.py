#!/usr/bin/env python3
"""Pure plan builder for dashboard metrics orchestrator shutdown."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricsOrchestratorShutdownPlan:
    """Pure decision output for metrics orchestrator shutdown."""

    action: str
    clear_owner: bool = False
    warning_template: str | None = None


def build_metrics_orchestrator_shutdown_plan(
    *,
    has_orchestrator: bool,
    has_stop_method: bool,
    stop_failed: bool,
) -> MetricsOrchestratorShutdownPlan:
    """Decide how dashboard-owned metrics orchestrator shutdown should proceed."""
    if not has_orchestrator or not has_stop_method:
        return MetricsOrchestratorShutdownPlan(action="noop")

    if stop_failed:
        return MetricsOrchestratorShutdownPlan(
            action="warn_and_clear",
            clear_owner=True,
            warning_template="Metrics orchestrator stop error: %s",
        )

    return MetricsOrchestratorShutdownPlan(
        action="stop_and_clear",
        clear_owner=True,
    )
