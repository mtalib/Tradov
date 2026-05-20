#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG44_RecentDecisionFlowPresenter.py
Purpose: Pure presentation helpers for recent decision-flow diagnostics
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class RecentDecisionFlowPanelPresentation:
    """Dashboard-ready recent decision-flow panel text and tooltip state."""

    dispatch_text: str
    drop_text: str
    tooltip: str


def format_recent_decision_events(records: Sequence[Mapping[str, Any]] | None) -> str:
    """Format compact recent decision events for the execution-health panel."""
    if not records:
        return "-"

    lines: list[str] = []
    for record in records:
        if not isinstance(record, Mapping):
            continue

        ts_raw = str(record.get("ts_utc") or "").strip()
        time_text = "--:--:--"
        if ts_raw:
            try:
                time_text = datetime.fromisoformat(ts_raw.replace("Z", "+00:00")).strftime("%H:%M:%S")
            except ValueError:
                time_text = ts_raw[11:19] if len(ts_raw) >= 19 else ts_raw[:8]

        event_text = str(record.get("event") or record.get("reason") or "-").strip()
        detail_text = str(record.get("detail") or record.get("reason") or "").strip()
        if detail_text and detail_text != event_text:
            lines.append(f"{time_text} | {event_text} | {detail_text}")
        else:
            lines.append(f"{time_text} | {event_text}")

    return "\n".join(lines) if lines else "-"


def build_recent_decision_flow_panel_presentation(
    flow: Mapping[str, Any] | None,
) -> RecentDecisionFlowPanelPresentation:
    """Build recent decision-flow panel text and tooltip state from diagnostics."""
    data = flow if isinstance(flow, Mapping) else {}
    decision_log_path = str(data.get("decision_log") or "").strip()

    return RecentDecisionFlowPanelPresentation(
        dispatch_text=format_recent_decision_events(data.get("dispatch")),
        drop_text=format_recent_decision_events(data.get("drops")),
        tooltip=decision_log_path or "Decision log unavailable",
    )
