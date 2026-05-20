#!/usr/bin/env python3
"""Focused tests for G62 readiness worker cleanup helper."""

from types import SimpleNamespace

from Spyder.SpyderG_GUI.SpyderG62_ReadinessWorkerCleanupHelper import (
    build_readiness_worker_cleanup_plan,
)


def test_build_readiness_worker_cleanup_plan_enables_button_and_filters_none() -> None:
    button = SimpleNamespace()
    worker = SimpleNamespace()
    thread = None

    plan = build_readiness_worker_cleanup_plan(
        readiness_button=button,
        readiness_worker=worker,
        readiness_worker_thread=thread,
    )

    assert plan.enable_button is True
    assert plan.delete_targets == (worker,)


def test_build_readiness_worker_cleanup_plan_handles_absent_button_and_targets() -> None:
    plan = build_readiness_worker_cleanup_plan(
        readiness_button=None,
        readiness_worker=None,
        readiness_worker_thread=None,
    )

    assert plan.enable_button is False
    assert plan.delete_targets == ()
