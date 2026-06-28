#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovG_GUI
Module: TradovG66_ReadinessStartupStateHelper.py
Purpose: Pure helper for readiness startup-state cache decisions
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ReadinessStartupStatePlan:
    """Plan describing whether cached startup readiness state can be reused."""

    startup_state: dict[str, Any]
    refresh_cache: bool


def build_readiness_startup_state_plan(
    startup_state: object,
) -> ReadinessStartupStatePlan:
    """Decide whether cached startup readiness state should be reused or refreshed."""
    if isinstance(startup_state, dict) and startup_state:
        return ReadinessStartupStatePlan(
            startup_state=startup_state,
            refresh_cache=False,
        )

    return ReadinessStartupStatePlan(
        startup_state={},
        refresh_cache=True,
    )
