#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG46_ReadinessStatusPresenter.py
Purpose: Pure presentation helpers for trading-readiness status display
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping


@dataclass(frozen=True)
class ReadinessStatusPresentation:
    """Dashboard-ready readiness label, button, and start-button state."""

    status_text: str
    status_style: str
    button_text: str
    button_style: str
    start_enabled: bool | None
    start_tooltip: str | None


def build_readiness_status_presentation(
    result: Mapping[str, Any] | None,
    *,
    trading_mode: Any,
    trading_active: bool,
    colors: Mapping[str, str],
) -> ReadinessStatusPresentation:
    """Build readiness status label/button presentation from the latest decision."""
    trading_mode_text = "LIVE"
    button_text = "RE-EVALUATE TRADING READINESS"
    button_style = (
        "background-color: #0066CC; color: white; font-size: 12px; "
        "padding: 0 12px; border: 1px solid #2A7BD6; border-radius: 3px;"
    )

    if not isinstance(result, Mapping):
        return ReadinessStatusPresentation(
            status_text="<<READINESS PENDING>>",
            status_style="color: white; font-size: 13px; font-weight: 600;",
            button_text=button_text,
            button_style=button_style,
            start_enabled=True,
            start_tooltip="Start automated trading",
        )

    decision = str(result.get("decision", "NOT RUN"))
    conditional = bool(result.get("conditional", False))
    reasons = [str(reason) for reason in (result.get("reasons") or [])]
    warnings = [str(warning) for warning in (result.get("warnings") or [])]
    checked_at = str(result.get("checked_at_et", ""))
    ts_suffix = checked_at[11:19] if len(checked_at) >= 19 else "--:--:--"

    if decision == "NO":
        detail_text = "; ".join(reasons) if reasons else "Reason unavailable"
        return ReadinessStatusPresentation(
            status_text=(
                f"@ {ts_suffix} ET - NOT READY FOR {trading_mode_text} TRADING "
                f"| Reasons: {detail_text}"
            ),
            status_style=f"color: {colors['negative']}; font-size: 13px; font-weight: 600;",
            button_text=button_text,
            button_style=button_style,
            start_enabled=(False if not trading_active else None),
            start_tooltip=(
                "Start blocked: trading readiness is NO" if not trading_active else None
            ),
        )

    if conditional:
        warning_suffix = (
            f" | Warnings: {'; '.join(warnings)}" if warnings else ""
        )
        return ReadinessStatusPresentation(
            status_text=(
                f"@ {ts_suffix} ET - YES READY FOR {trading_mode_text} TRADING "
                f"(CONDITIONAL){warning_suffix}"
            ),
            status_style=f"color: {colors['warning']}; font-size: 13px; font-weight: 600;",
            button_text=button_text,
            button_style=button_style,
            start_enabled=True,
            start_tooltip="OK-CONDITIONAL active: reduced-risk confirmation required",
        )

    mode_key = str(getattr(trading_mode, "value", trading_mode) or "").strip().upper()
    start_tooltip = (
        "Start paper trading with simulated fills"
        if mode_key == "PAPER"
        else "Start LIVE trading with real order execution"
    )
    return ReadinessStatusPresentation(
        status_text=f"@ {ts_suffix} ET - YES READY FOR {trading_mode_text} TRADING",
        status_style=f"color: {colors['positive']}; font-size: 13px; font-weight: 600;",
        button_text=button_text,
        button_style=button_style,
        start_enabled=True,
        start_tooltip=start_tooltip,
    )
