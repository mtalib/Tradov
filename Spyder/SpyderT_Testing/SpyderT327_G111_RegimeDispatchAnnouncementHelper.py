#!/usr/bin/env python3
"""Focused tests for G111 regime dispatch announcement helper."""

from __future__ import annotations

from Spyder.SpyderG_GUI.SpyderG111_RegimeDispatchAnnouncementHelper import (
    build_regime_dispatch_announcement_plan,
)


def test_build_regime_dispatch_announcement_plan_halts_crisis_and_emits_warning() -> None:
    plan = build_regime_dispatch_announcement_plan(
        regime="CRISIS",
        raw_dispatch_state={"state": "IDLE", "reason": "no signals", "age_s": None},
        last_dispatch_state_key="",
    )

    assert plan.dispatch_state == {
        "state": "HALT",
        "reason": "regime=CRISIS",
        "age_s": None,
    }
    assert plan.dispatch_label == "HALT"
    assert plan.should_announce is True
    assert plan.autonomous_message == "D31 DISPATCH -> HALT (regime=CRISIS)"
    assert plan.system_log_message == "⚠️ D31 DISPATCH -> HALT (regime=CRISIS)"


def test_build_regime_dispatch_announcement_plan_suppresses_duplicate_announcements() -> None:
    plan = build_regime_dispatch_announcement_plan(
        regime="BULL",
        raw_dispatch_state={"state": "IDLE", "reason": "no signals", "age_s": None},
        last_dispatch_state_key="IDLE|no signals",
    )

    assert plan.dispatch_label == "IDLE"
    assert plan.should_announce is False
    assert plan.autonomous_message is None
    assert plan.system_log_message is None
