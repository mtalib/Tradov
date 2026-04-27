#!/usr/bin/env python3
"""
Tests for SpyderK13_StrategyPnLLadder

Covers: dataclass construction, to_dict serialisation, to_dataframe,
empty-ladder graceful degradation, and singleton get_ladder().
"""

import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from Spyder.SpyderK_Reports.SpyderK13_StrategyPnLLadder import (
    PnLLadderSnapshot,
    StrategyPnLLadder,
    StrategyRow,
    get_ladder,
)


def _make_row(rank: int = 1, pnl: float = 500.0) -> StrategyRow:
    return StrategyRow(
        rank=rank,
        strategy_id=f"strat_{rank}",
        strategy_name=f"Strategy {rank}",
        strategy_type="credit_spread",
        allocation_pct=0.10,
        allocated_capital=10_000.0,
        pnl=pnl,
        contribution_pct=0.25,
        performance_score=0.75,
        risk_score=0.30,
        health_score=0.85,
    )


class TestStrategyRow(unittest.TestCase):
    def test_to_dict_keys(self):
        row = _make_row()
        d = row.to_dict()
        expected_keys = {
            "rank", "strategy_id", "strategy_name", "strategy_type",
            "allocation_pct", "allocated_capital", "pnl",
            "contribution_pct", "performance_score", "risk_score", "health_score",
        }
        self.assertEqual(set(d.keys()), expected_keys)

    def test_allocation_pct_is_percentage(self):
        row = _make_row()
        d = row.to_dict()
        # 0.10 fraction → 10.0 percent
        self.assertAlmostEqual(d["allocation_pct"], 10.0)

    def test_pnl_rounded(self):
        row = _make_row(pnl=123.456789)
        self.assertAlmostEqual(row.to_dict()["pnl"], 123.46)


class TestPnLLadderSnapshot(unittest.TestCase):
    def test_empty_snapshot_to_dict(self):
        snap = PnLLadderSnapshot()
        d = snap.to_dict()
        self.assertEqual(d["total_strategies"], 0)
        self.assertEqual(d["rows"], [])
        self.assertIn("timestamp", d)

    def test_snapshot_with_rows(self):
        snap = PnLLadderSnapshot(
            rows=[_make_row(1, 300.0), _make_row(2, 150.0)],
            portfolio_pnl=450.0,
            total_strategies=2,
        )
        d = snap.to_dict()
        self.assertEqual(len(d["rows"]), 2)
        self.assertAlmostEqual(d["portfolio_pnl"], 450.0)

    def test_to_dataframe_returns_df(self):
        try:
            import pandas as pd
        except ImportError:
            self.skipTest("pandas not installed")

        snap = PnLLadderSnapshot(rows=[_make_row(1), _make_row(2)])
        df = snap.to_dataframe()
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 2)

    def test_to_dataframe_empty(self):
        try:
            import pandas as pd
        except ImportError:
            self.skipTest("pandas not installed")

        snap = PnLLadderSnapshot()
        df = snap.to_dataframe()
        self.assertTrue(df.empty)


class TestStrategyPnLLadder(unittest.TestCase):
    def test_get_snapshot_returns_snapshot(self):
        ladder = StrategyPnLLadder()
        snap = ladder.get_snapshot()
        self.assertIsInstance(snap, PnLLadderSnapshot)

    def test_get_snapshot_graceful_without_dependencies(self):
        """Should return an empty ladder when D31 / F17 are unavailable."""
        ladder = StrategyPnLLadder()
        snap = ladder.get_snapshot()
        self.assertIsNotNone(snap)

    def test_build_ladder_returns_snapshot(self):
        ladder = StrategyPnLLadder()
        snap = ladder.build_ladder()
        self.assertIsInstance(snap, PnLLadderSnapshot)


class TestGetLadderSingleton(unittest.TestCase):
    def test_same_instance(self):
        l1 = get_ladder()
        l2 = get_ladder()
        self.assertIs(l1, l2)

    def test_is_ladder_type(self):
        self.assertIsInstance(get_ladder(), StrategyPnLLadder)


if __name__ == "__main__":
    unittest.main()
