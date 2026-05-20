#!/usr/bin/env python3
"""Pure veto controls persistence planning for the dashboard."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class VetoControlsPersistPlan:
    """Pure persistence plan for the unified veto toggle."""

    payload: dict[str, bool]
    serialized_profile_text: str
    env_updates: dict[str, str]


def build_veto_controls_persist_plan(
    *,
    existing_data: dict[str, Any] | None,
    enabled: bool,
) -> VetoControlsPersistPlan:
    """Return the merged profile payload, serialized file text, and env updates."""
    payload = {
        "enable_x16_veto": enabled,
        "enable_y03_trade_veto": enabled,
        "enable_y05_veto_consumption": enabled,
    }
    merged_data = dict(existing_data) if isinstance(existing_data, dict) else {}
    merged_data.update(payload)
    env_value = "true" if enabled else "false"
    return VetoControlsPersistPlan(
        payload=payload,
        serialized_profile_text=f"{json.dumps(merged_data, indent=2)}\n",
        env_updates={
            "ENABLE_X16_VETO": env_value,
            "ENABLE_Y03_TRADE_VETO": env_value,
            "ENABLE_Y05_VETO_CONSUMPTION": env_value,
        },
    )
