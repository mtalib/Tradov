#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG34_AccountCapitalMath.py
Purpose: Pure helpers for account capital baselines and buying-power math
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from Spyder.SpyderG_GUI.SpyderG28_AccountPanelPresenter import parse_money_text


@dataclass(frozen=True)
class BuyingPowerUsage:
    """Normalized buying-power usage against an account capital baseline."""

    used: float
    capital: float
    percent: float


def _coerce_positive_float(value: Any) -> float:
    """Return a positive float or zero for invalid and non-positive values."""
    try:
        numeric = float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return numeric if numeric > 0 else 0.0


def resolve_capital_baseline(
    primary_raw: Any,
    *,
    secondary_raw: Any = None,
    fallback_text: str | None = None,
    default: float = 0.0,
) -> float:
    """Resolve a positive capital baseline from raw values or fallback label text."""
    primary_value = _coerce_positive_float(primary_raw)
    if primary_value > 0:
        return primary_value

    secondary_value = _coerce_positive_float(secondary_raw)
    if secondary_value > 0:
        return secondary_value

    if fallback_text is not None:
        text_value = parse_money_text(fallback_text)
        if text_value > 0:
            return text_value

    return _coerce_positive_float(default)


def calculate_buying_power_usage(
    spreads_detail: Sequence[Mapping[str, Any]] | None,
    *,
    capital_raw: Any,
    default_capital: float = 100_000.0,
) -> BuyingPowerUsage:
    """Calculate buying-power usage from spread details and a capital baseline."""
    used = 0.0
    for spread in spreads_detail or []:
        if not isinstance(spread, Mapping):
            continue
        try:
            used += float(spread.get("max_loss_per_contract", 0.0)) * int(spread.get("qty", 0))
        except (TypeError, ValueError):
            continue

    capital = resolve_capital_baseline(capital_raw, default=default_capital)
    percent = (used / capital * 100.0) if capital > 0 else 0.0
    return BuyingPowerUsage(used=used, capital=capital, percent=percent)


def derive_realized_pnl_delta_from_equity(
    equity: Any,
    *,
    capital_raw: Any,
    default_capital: float = 100_000.0,
) -> float:
    """Derive account-level realized P&L delta from equity vs. capital baseline."""
    try:
        equity_value = float(equity or 0.0)
    except (TypeError, ValueError):
        equity_value = 0.0

    capital = resolve_capital_baseline(capital_raw, default=default_capital)
    return equity_value - capital
