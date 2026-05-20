#!/usr/bin/env python3
"""Focused regressions for G33 account snapshot selection."""

from __future__ import annotations

from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import TradingMode
from Spyder.SpyderG_GUI.SpyderG33_AccountSnapshotSelector import get_restorable_account_snapshot


def test_get_restorable_account_snapshot_returns_copy_for_live_mode() -> None:
    snapshots = {
        TradingMode.LIVE: {"settled_cash": 100000.0},
        TradingMode.PAPER: {"settled_cash": 50000.0},
    }

    restored = get_restorable_account_snapshot(
        snapshots,
        TradingMode.LIVE,
        paper_mode=TradingMode.PAPER,
    )

    assert restored == {"settled_cash": 100000.0}
    assert restored is not snapshots[TradingMode.LIVE]


def test_get_restorable_account_snapshot_skips_paper_and_empty_values() -> None:
    snapshots = {
        TradingMode.LIVE: {},
        TradingMode.PAPER: {"settled_cash": 50000.0},
    }

    assert (
        get_restorable_account_snapshot(
            snapshots,
            TradingMode.PAPER,
            paper_mode=TradingMode.PAPER,
        )
        is None
    )
    assert (
        get_restorable_account_snapshot(
            snapshots,
            TradingMode.LIVE,
            paper_mode=TradingMode.PAPER,
        )
        is None
    )
