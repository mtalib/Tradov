#!/usr/bin/env python3
"""Focused tests for G05 paper clean-slate startup guard behavior."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard, TradingMode


class _FakeEmptyPaperDB:
    """Minimal empty-paper DB stub for startup guard tests."""

    def get_latest_snapshot(self):
        return None

    def get_recent_trades(self, limit: int = 1):
        return []

    def get_open_positions(self):
        return []


def _build_dashboard_stub() -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.trading_mode = TradingMode.PAPER
    dash._paper_initial_capital = 100_000.0
    dash._account_snapshot_by_mode = {}
    dash._pnl_stats_by_mode = {TradingMode.PAPER: {"today_pnl": "$+480.00"}}
    dash.logger = SimpleNamespace(debug=lambda *_args, **_kwargs: None)
    return dash


def test_paper_clean_slate_guard_resets_to_baseline_when_state_and_db_empty(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    snapshot_calls: list[dict] = []
    panel_calls: list[dict] = []

    dash._apply_account_snapshot = lambda snapshot: snapshot_calls.append(dict(snapshot))
    dash._set_spyderbox_account_panel_values = (
        lambda **kwargs: panel_calls.append(dict(kwargs))
    )

    missing_state = Path("/tmp/spyder_nonexistent_paper_state_for_test.json")
    monkeypatch.setenv("SPYDER_PAPER_ACCOUNT_STATE_FILE", str(missing_state))
    monkeypatch.setitem(
        sys.modules,
        "Spyder.SpyderH_Storage.SpyderH05_TradingSessionDB",
        SimpleNamespace(
            TradingSessionDB=SimpleNamespace(for_paper=lambda: _FakeEmptyPaperDB())
        ),
    )

    SpyderTradingDashboard._apply_paper_clean_slate_startup_guard(dash)

    assert dash._account_snapshot_by_mode[TradingMode.PAPER] == {
        "settled_cash": 100_000.0,
        "buying_power": 100_000.0,
        "realized_pnl": 0.0,
        "unrealized_pnl": 0.0,
    }
    assert dash._pnl_stats_by_mode[TradingMode.PAPER] == {}
    assert snapshot_calls == [
        {
            "settled_cash": 100_000.0,
            "buying_power": 100_000.0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
        }
    ]
    assert panel_calls == [
        {
            "settled": 100_000.0,
            "buying": 100_000.0,
            "realized": 0.0,
            "unrealized": 0.0,
        }
    ]


def test_paper_clean_slate_guard_noops_when_state_file_exists(monkeypatch, tmp_path: Path) -> None:
    dash = _build_dashboard_stub()
    snapshot_calls: list[dict] = []
    panel_calls: list[dict] = []

    dash._apply_account_snapshot = lambda snapshot: snapshot_calls.append(dict(snapshot))
    dash._set_spyderbox_account_panel_values = (
        lambda **kwargs: panel_calls.append(dict(kwargs))
    )

    state_file = tmp_path / "paper_trading_state.json"
    state_file.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("SPYDER_PAPER_ACCOUNT_STATE_FILE", str(state_file))

    prior_account_snapshot = dict(dash._account_snapshot_by_mode)
    prior_pnl_stats = dict(dash._pnl_stats_by_mode)

    SpyderTradingDashboard._apply_paper_clean_slate_startup_guard(dash)

    assert dash._account_snapshot_by_mode == prior_account_snapshot
    assert dash._pnl_stats_by_mode == prior_pnl_stats
    assert snapshot_calls == []
    assert panel_calls == []
