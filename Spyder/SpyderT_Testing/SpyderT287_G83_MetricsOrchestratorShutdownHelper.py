#!/usr/bin/env python3
"""Focused tests for G83 metrics orchestrator shutdown helper."""

from Spyder.SpyderG_GUI.SpyderG83_MetricsOrchestratorShutdownHelper import (
    build_metrics_orchestrator_shutdown_plan,
)


def test_build_metrics_orchestrator_shutdown_plan_noops_without_owner() -> None:
    plan = build_metrics_orchestrator_shutdown_plan(
        has_orchestrator=False,
        has_stop_method=False,
        stop_failed=False,
    )

    assert plan.action == "noop"
    assert plan.clear_owner is False
    assert plan.warning_template is None


def test_build_metrics_orchestrator_shutdown_plan_noops_without_stop_method() -> None:
    plan = build_metrics_orchestrator_shutdown_plan(
        has_orchestrator=True,
        has_stop_method=False,
        stop_failed=False,
    )

    assert plan.action == "noop"
    assert plan.clear_owner is False
    assert plan.warning_template is None


def test_build_metrics_orchestrator_shutdown_plan_stops_and_clears() -> None:
    plan = build_metrics_orchestrator_shutdown_plan(
        has_orchestrator=True,
        has_stop_method=True,
        stop_failed=False,
    )

    assert plan.action == "stop_and_clear"
    assert plan.clear_owner is True
    assert plan.warning_template is None


def test_build_metrics_orchestrator_shutdown_plan_warns_and_clears_on_failure() -> None:
    plan = build_metrics_orchestrator_shutdown_plan(
        has_orchestrator=True,
        has_stop_method=True,
        stop_failed=True,
    )

    assert plan.action == "warn_and_clear"
    assert plan.clear_owner is True
    assert plan.warning_template == "Metrics orchestrator stop error: %s"