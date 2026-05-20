#!/usr/bin/env python3
"""Focused tests for G123 veto toggle button helper."""

from Spyder.SpyderG_GUI.SpyderG123_VetoToggleButtonHelper import (
    build_veto_toggle_button_presentation,
)


def test_build_veto_toggle_button_presentation_for_enabled_state() -> None:
    presentation = build_veto_toggle_button_presentation(True)

    assert presentation.checked is True
    assert presentation.text == "VETO: ENABLED"
    assert presentation.tooltip == "X16/Y03/Y05 veto path is enabled"
    assert "#0D7A33" in presentation.style


def test_build_veto_toggle_button_presentation_for_disabled_state() -> None:
    presentation = build_veto_toggle_button_presentation(False)

    assert presentation.checked is False
    assert presentation.text == "VETO: DISABLED"
    assert presentation.tooltip == "X16/Y03/Y05 veto path is disabled"
    assert "#A94442" in presentation.style