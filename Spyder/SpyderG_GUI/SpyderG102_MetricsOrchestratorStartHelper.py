#!/usr/bin/env python3
"""Pure start-plan helpers for the custom metrics orchestrator."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricsOrchestratorStartPlan:
    """Final live-announcement state and startup logs for S07 startup."""

    live_announced_after_start: bool
    log_messages: tuple[str, ...]


def build_metrics_orchestrator_start_plan(
    *,
    hydrated_snapshot: bool,
) -> MetricsOrchestratorStartPlan:
    """Return the final startup presentation for metrics orchestrator boot."""
    if hydrated_snapshot:
        return MetricsOrchestratorStartPlan(
            live_announced_after_start=True,
            log_messages=(
                "✅ Custom metrics orchestrator started (DIX + Black Swan schedulers active)",
                "AUTONOMOUS METRICS ACTIVE - DIX/SWAN stress monitor online",
            ),
        )

    return MetricsOrchestratorStartPlan(
        live_announced_after_start=False,
        log_messages=(),
    )
