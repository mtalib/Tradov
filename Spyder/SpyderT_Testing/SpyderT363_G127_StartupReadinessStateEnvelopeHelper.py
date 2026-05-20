#!/usr/bin/env python3
"""Focused tests for G127 startup-readiness state envelope helper."""

from Spyder.SpyderG_GUI.SpyderG127_StartupReadinessStateEnvelopeHelper import (
    build_startup_readiness_base_state,
    build_startup_readiness_success_state_payload,
)


def test_build_startup_readiness_base_state_returns_fresh_defaults() -> None:
    first = build_startup_readiness_base_state()
    first["warnings"].append("warn-a")

    second = build_startup_readiness_base_state()

    assert second == {
        "checked": False,
        "pending": False,
        "mode": "paper",
        "automation_enabled": True,
        "warnings": [],
        "errors": [],
        "safe_fallback_applied": False,
        "live_blocking": False,
    }


def test_build_startup_readiness_success_state_payload_normalizes_values() -> None:
    payload = build_startup_readiness_success_state_payload(
        mode="live",
        automation_enabled=1,
        warnings=("warn-a",),
        errors=("err-a",),
        safe_fallback_applied=0,
        live_blocking=1,
    )

    assert payload == {
        "checked": True,
        "mode": "live",
        "automation_enabled": True,
        "warnings": ["warn-a"],
        "errors": ["err-a"],
        "safe_fallback_applied": False,
        "live_blocking": True,
    }