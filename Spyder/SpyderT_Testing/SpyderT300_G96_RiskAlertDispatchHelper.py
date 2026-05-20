#!/usr/bin/env python3
"""Focused tests for G96 risk alert dispatch helper."""

from __future__ import annotations

from types import SimpleNamespace

from Spyder.SpyderG_GUI.SpyderG96_RiskAlertDispatchHelper import (
    build_risk_alert_dispatch_plan,
)


def test_build_risk_alert_dispatch_plan_skips_none_presentation() -> None:
    plan = build_risk_alert_dispatch_plan(
        presentation=None,
        last_digest="old",
        last_timestamp=100.0,
        now_monotonic=110.0,
    )

    assert plan.should_skip is True


def test_build_risk_alert_dispatch_plan_dedupes_recent_digest() -> None:
    plan = build_risk_alert_dispatch_plan(
        presentation=SimpleNamespace(
            digest="digest",
            system_log_message="system log",
            compact_display="BLOCK: compact",
        ),
        last_digest="digest",
        last_timestamp=100.0,
        now_monotonic=105.0,
    )

    assert plan.should_skip is True


def test_build_risk_alert_dispatch_plan_returns_dispatch_payload() -> None:
    plan = build_risk_alert_dispatch_plan(
        presentation=SimpleNamespace(
            digest="digest",
            system_log_message="system log",
            compact_display="BLOCK: compact",
        ),
        last_digest="old",
        last_timestamp=100.0,
        now_monotonic=120.0,
    )

    assert plan.should_skip is False
    assert plan.next_digest == "digest"
    assert plan.next_timestamp == 120.0
    assert plan.system_log_message == "system log"
    assert plan.compact_display == "BLOCK: compact"