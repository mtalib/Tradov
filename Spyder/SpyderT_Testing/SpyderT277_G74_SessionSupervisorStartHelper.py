#!/usr/bin/env python3
"""Focused tests for G74 SessionSupervisor start helper."""

from Spyder.SpyderG_GUI.SpyderG74_SessionSupervisorStartHelper import (
    build_session_supervisor_start_plan,
)


def test_build_session_supervisor_start_plan_blocks_autostart() -> None:
    plan = build_session_supervisor_start_plan(
        has_supervisor=True,
        autostart_in_progress=True,
        supervisor_running=False,
    )

    assert plan.action == "block_autostart"


def test_build_session_supervisor_start_plan_accepts_running_supervisor() -> None:
    plan = build_session_supervisor_start_plan(
        has_supervisor=True,
        autostart_in_progress=False,
        supervisor_running=True,
    )

    assert plan.action == "already_running"


def test_build_session_supervisor_start_plan_reuses_existing_supervisor() -> None:
    plan = build_session_supervisor_start_plan(
        has_supervisor=True,
        autostart_in_progress=False,
        supervisor_running=False,
    )

    assert plan.action == "reuse_existing"


def test_build_session_supervisor_start_plan_creates_new_supervisor_when_missing() -> None:
    plan = build_session_supervisor_start_plan(
        has_supervisor=False,
        autostart_in_progress=False,
        supervisor_running=False,
    )

    assert plan.action == "create_new"
