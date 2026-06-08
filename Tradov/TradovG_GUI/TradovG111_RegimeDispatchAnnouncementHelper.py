#!/usr/bin/env python3
"""Pure dispatch announcement planning for the regime pill bar."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class RegimeDispatchAnnouncementPlan:
    """Effective dispatch state plus optional announcement messages."""

    dispatch_state: dict[str, object]
    dispatch_label: str
    dispatch_state_key: str
    should_announce: bool
    autonomous_message: str | None
    system_log_message: str | None


def build_regime_dispatch_announcement_plan(
    *,
    regime: str,
    raw_dispatch_state: Mapping[str, object] | None,
    last_dispatch_state_key: str,
) -> RegimeDispatchAnnouncementPlan:
    """Return the effective dispatch state and any announcement payload."""
    if regime in {"CRISIS", "EVENT"}:
        dispatch_state = {
            "state": "HALT",
            "reason": f"regime={regime}",
            "age_s": None,
        }
    else:
        dispatch_state = dict(raw_dispatch_state or {})

    dispatch_label = str(dispatch_state.get("state", "IDLE")).strip() or "IDLE"
    dispatch_reason = str(dispatch_state.get("reason", "")).strip()
    dispatch_state_key = f"{dispatch_label}|{dispatch_reason}"
    if dispatch_state_key == last_dispatch_state_key:
        return RegimeDispatchAnnouncementPlan(
            dispatch_state=dispatch_state,
            dispatch_label=dispatch_label,
            dispatch_state_key=dispatch_state_key,
            should_announce=False,
            autonomous_message=None,
            system_log_message=None,
        )

    autonomous_message = f"D31 DISPATCH -> {dispatch_label}"
    if dispatch_reason:
        autonomous_message = f"{autonomous_message} ({dispatch_reason})"

    system_log_message = None
    if dispatch_label in {"BLOCKED", "ERROR", "HALT"}:
        system_log_message = f"⚠️ {autonomous_message}"

    return RegimeDispatchAnnouncementPlan(
        dispatch_state=dispatch_state,
        dispatch_label=dispatch_label,
        dispatch_state_key=dispatch_state_key,
        should_announce=True,
        autonomous_message=autonomous_message,
        system_log_message=system_log_message,
    )
