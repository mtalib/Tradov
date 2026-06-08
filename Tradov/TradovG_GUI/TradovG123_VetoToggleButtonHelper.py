#!/usr/bin/env python3
"""Pure veto toggle button presentation for the dashboard."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VetoToggleButtonPresentation:
    """Pure button presentation for the veto toggle."""

    checked: bool
    text: str
    style: str
    tooltip: str


def build_veto_toggle_button_presentation(enabled: bool) -> VetoToggleButtonPresentation:
    """Return button presentation for the current veto-enabled state."""
    if enabled:
        return VetoToggleButtonPresentation(
            checked=True,
            text="VETO: ENABLED",
            style=(
                "background-color: #0D7A33; color: white; font-size: 12px; "
                "padding: 0 12px; border: 1px solid #1FA44C; border-radius: 3px;"
            ),
            tooltip="X16/Y03/Y05 veto path is enabled",
        )

    return VetoToggleButtonPresentation(
        checked=False,
        text="VETO: DISABLED",
        style=(
            "background-color: #A94442; color: white; font-size: 12px; "
            "padding: 0 12px; border: 1px solid #C96865; border-radius: 3px;"
        ),
        tooltip="X16/Y03/Y05 veto path is disabled",
    )
