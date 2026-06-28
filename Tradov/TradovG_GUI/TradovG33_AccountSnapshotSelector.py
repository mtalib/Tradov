#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovG_GUI
Module: TradovG33_AccountSnapshotSelector.py
Purpose: Pure helper for choosing which account snapshots G05 may restore
"""

from __future__ import annotations

from typing import Any
from collections.abc import Mapping


def get_restorable_account_snapshot(
    snapshots_by_mode: Mapping[Any, Mapping[str, Any]],
    mode: Any,
    *,
    paper_mode: Any,
) -> dict[str, Any] | None:
    """Return a copy of the active mode snapshot when it is valid to restore."""
    if mode == paper_mode:
        return None

    snapshot = snapshots_by_mode.get(mode)
    if not isinstance(snapshot, Mapping) or not snapshot:
        return None

    return dict(snapshot)
