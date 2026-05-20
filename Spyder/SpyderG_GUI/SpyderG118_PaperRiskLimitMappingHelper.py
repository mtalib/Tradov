#!/usr/bin/env python3
"""Pure mapping from dashboard risk params to E01 risk limits."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PaperRiskLimitMappingPlan:
    """Mapped E01 risk limits plus optional warning copy."""

    risk_limits: dict[str, Any]
    warning_message: str | None = None


def build_paper_risk_limit_mapping_plan(
    *,
    default_risk_limits: dict[str, Any],
    current_risk_params: Any,
    initial_capital: float,
) -> PaperRiskLimitMappingPlan:
    """Overlay G09 dialog values onto E01 default limits."""
    limits = dict(default_risk_limits)
    params = current_risk_params or {}
    global_params = params.get("global", {}) if isinstance(params, dict) else {}
    if not isinstance(global_params, dict):
        global_params = {}

    try:
        if "max_buying_power" in global_params:
            limits["max_total_exposure"] = float(initial_capital) * (
                float(global_params["max_buying_power"]) / 100.0
            )
        if "max_daily_loss" in global_params:
            limits["max_daily_loss"] = float(initial_capital) * (
                float(global_params["max_daily_loss"]) / 100.0
            )
        if "max_contracts" in global_params:
            max_contracts = int(global_params["max_contracts"])
            limits["max_position_size"] = max_contracts
            limits["max_single_order_size"] = max_contracts
    except (TypeError, ValueError) as exc:
        return PaperRiskLimitMappingPlan(
            risk_limits=limits,
            warning_message=f"Could not map G09 params to E01 limits: {exc}",
        )

    return PaperRiskLimitMappingPlan(risk_limits=limits)
