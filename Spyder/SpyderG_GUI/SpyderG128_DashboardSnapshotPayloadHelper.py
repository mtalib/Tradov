#!/usr/bin/env python3
"""Pure dashboard snapshot payload shaping for cold-start restore."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def _normalize_mode_name(mode_key: object) -> str:
    """Normalize an enum-like mode key to its payload string."""
    return str(getattr(mode_key, "value", mode_key))


def build_dashboard_snapshot_payload(
    *,
    saved_at: float,
    trading_mode: str,
    mode_keys: Iterable[object],
    account_snapshot_by_mode: Mapping[object, object],
    pnl_stats_by_mode: Mapping[object, object],
    market_data: Mapping[str, Any],
    reset_mode_names: Iterable[str] = ("PAPER",),
) -> dict[str, object]:
    """Build the persisted dashboard snapshot payload from current in-memory state."""
    account_by_mode: dict[str, dict[str, Any]] = {}
    normalized_pnl_by_mode: dict[str, dict[str, Any]] = {}

    for mode_key in mode_keys:
        mode_name = _normalize_mode_name(mode_key)
        account_values = account_snapshot_by_mode.get(mode_key, {})
        pnl_values = pnl_stats_by_mode.get(mode_key, {})
        account_by_mode[mode_name] = dict(account_values) if isinstance(account_values, Mapping) else {}
        normalized_pnl_by_mode[mode_name] = dict(pnl_values) if isinstance(pnl_values, Mapping) else {}

    for mode_name in {str(name) for name in reset_mode_names}:
        account_by_mode[mode_name] = {}
        normalized_pnl_by_mode[mode_name] = {}

    data: dict[str, dict[str, Any]] = {}
    for symbol, entry in market_data.items():
        if not isinstance(entry, Mapping):
            continue
        if entry.get("last") is None:
            continue
        data[str(symbol)] = {
            "last": entry.get("last", 0.0),
            "change": entry.get("change", 0.0),
            "change_pct": entry.get("change_pct", 0.0),
        }

    return {
        "_saved_at": saved_at,
        "trading_mode": trading_mode,
        "account_by_mode": account_by_mode,
        "pnl_stats_by_mode": normalized_pnl_by_mode,
        "data": data,
    }
