#!/usr/bin/env python3
"""Focused tests for G46 readiness status presenter helpers."""

from types import SimpleNamespace

from Spyder.SpyderG_GUI.SpyderG46_ReadinessStatusPresenter import (
    build_readiness_status_presentation,
)


COLORS = {
    "positive": "#00ff00",
    "warning": "#ffaa00",
    "negative": "#ff0000",
}


def test_build_readiness_status_presentation_pending_state() -> None:
    presentation = build_readiness_status_presentation(
        None,
        trading_mode=SimpleNamespace(value="PAPER"),
        trading_active=False,
        colors=COLORS,
    )

    assert presentation.status_text == "<<READINESS PENDING>>"
    assert "color: white" in presentation.status_style
    assert presentation.start_enabled is True
    assert presentation.start_tooltip == "Start automated trading"


def test_build_readiness_status_presentation_ready_state_uses_live_wording_and_mode_tooltip() -> None:
    presentation = build_readiness_status_presentation(
        {
            "decision": "OK",
            "checked_at_et": "2026-05-15T09:31:22-04:00",
        },
        trading_mode=SimpleNamespace(value="PAPER"),
        trading_active=False,
        colors=COLORS,
    )

    assert presentation.status_text == "@ 09:31:22 ET - YES READY FOR LIVE TRADING"
    assert COLORS["positive"] in presentation.status_style
    assert presentation.start_enabled is True
    assert presentation.start_tooltip == "Start paper trading with simulated fills"


def test_build_readiness_status_presentation_conditional_state_includes_warnings() -> None:
    presentation = build_readiness_status_presentation(
        {
            "decision": "OK",
            "conditional": True,
            "warnings": ["stale quote basket", "operator review required"],
            "checked_at_et": "2026-05-15T09:31:22-04:00",
        },
        trading_mode=SimpleNamespace(value="LIVE"),
        trading_active=False,
        colors=COLORS,
    )

    assert presentation.status_text == (
        "@ 09:31:22 ET - YES READY FOR LIVE TRADING "
        "(CONDITIONAL) | Warnings: stale quote basket; operator review required"
    )
    assert COLORS["warning"] in presentation.status_style
    assert presentation.start_enabled is True
    assert presentation.start_tooltip == "OK-CONDITIONAL active: reduced-risk confirmation required"


def test_build_readiness_status_presentation_no_state_blocks_start_only_when_idle() -> None:
    idle_presentation = build_readiness_status_presentation(
        {
            "decision": "NO",
            "reasons": ["tradier disconnected"],
            "checked_at_et": "2026-05-15T09:31:22-04:00",
        },
        trading_mode=SimpleNamespace(value="LIVE"),
        trading_active=False,
        colors=COLORS,
    )
    active_presentation = build_readiness_status_presentation(
        {
            "decision": "NO",
            "reasons": ["tradier disconnected"],
            "checked_at_et": "2026-05-15T09:31:22-04:00",
        },
        trading_mode=SimpleNamespace(value="LIVE"),
        trading_active=True,
        colors=COLORS,
    )

    assert idle_presentation.status_text == (
        "@ 09:31:22 ET - NOT READY FOR LIVE TRADING | Reasons: tradier disconnected"
    )
    assert COLORS["negative"] in idle_presentation.status_style
    assert idle_presentation.start_enabled is False
    assert idle_presentation.start_tooltip == "Start blocked: trading readiness is NO"
    assert active_presentation.start_enabled is None
    assert active_presentation.start_tooltip is None