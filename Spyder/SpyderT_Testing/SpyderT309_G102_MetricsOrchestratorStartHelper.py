#!/usr/bin/env python3
"""Focused tests for G102 metrics orchestrator start helper."""

from __future__ import annotations

from Spyder.SpyderG_GUI.SpyderG102_MetricsOrchestratorStartHelper import (
    build_metrics_orchestrator_start_plan,
)


def test_build_metrics_orchestrator_start_plan_returns_active_logs_when_hydrated() -> None:
    plan = build_metrics_orchestrator_start_plan(hydrated_snapshot=True)

    assert plan.live_announced_after_start is True
    assert plan.log_messages == (
        "✅ Custom metrics orchestrator started (DIX + Black Swan schedulers active)",
        "AUTONOMOUS METRICS ACTIVE - DIX/SWAN stress monitor online",
    )


def test_build_metrics_orchestrator_start_plan_returns_waiting_log_when_not_hydrated() -> None:
    plan = build_metrics_orchestrator_start_plan(hydrated_snapshot=False)

    assert plan.live_announced_after_start is False
    assert plan.log_messages == ()
