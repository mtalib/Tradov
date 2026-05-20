#!/usr/bin/env python3
"""Focused tests for G125 veto controls state helper."""

from Spyder.SpyderG_GUI.SpyderG125_VetoControlsStateHelper import (
    resolve_veto_controls_enabled_state,
)


def test_resolve_veto_controls_enabled_state_uses_profile_data_when_available() -> None:
    result = resolve_veto_controls_enabled_state(
        profile_data={
            "enable_x16_veto": True,
            "enable_y03_trade_veto": False,
            "enable_y05_veto_consumption": True,
        },
        default_enabled=True,
        env_values={},
    )

    assert result is False


def test_resolve_veto_controls_enabled_state_falls_back_to_env_values() -> None:
    result = resolve_veto_controls_enabled_state(
        profile_data=None,
        default_enabled=True,
        env_values={
            "ENABLE_X16_VETO": "true",
            "ENABLE_Y03_TRADE_VETO": "on",
            "ENABLE_Y05_VETO_CONSUMPTION": "false",
        },
    )

    assert result is False


def test_resolve_veto_controls_enabled_state_uses_default_for_missing_env_values() -> None:
    result = resolve_veto_controls_enabled_state(
        profile_data=None,
        default_enabled=True,
        env_values={
            "ENABLE_X16_VETO": None,
            "ENABLE_Y03_TRADE_VETO": None,
            "ENABLE_Y05_VETO_CONSUMPTION": None,
        },
    )

    assert result is True
