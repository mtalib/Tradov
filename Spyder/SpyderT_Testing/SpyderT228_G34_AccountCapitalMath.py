#!/usr/bin/env python3
"""Focused regressions for G34 account capital math extraction."""

from __future__ import annotations

from unittest.mock import MagicMock

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
import Spyder.SpyderH_Storage.SpyderH05_TradingSessionDB as h05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
from Spyder.SpyderG_GUI.SpyderG13_EnhancedWidgets import TradingMode
from Spyder.SpyderG_GUI.SpyderG34_AccountCapitalMath import (
    calculate_buying_power_usage,
    derive_realized_pnl_delta_from_equity,
    resolve_capital_baseline,
)


def test_resolve_capital_baseline_uses_raw_then_fallbacks() -> None:
    assert resolve_capital_baseline(125000.0, secondary_raw=100000.0, fallback_text="$90,000.00") == 125000.0
    assert resolve_capital_baseline(0.0, secondary_raw=110000.0, fallback_text="$90,000.00") == 110000.0
    assert resolve_capital_baseline(None, fallback_text="$95,500.25") == 95500.25
    assert resolve_capital_baseline(None, default=100000.0) == 100000.0


def test_calculate_buying_power_usage_sums_max_loss_and_percent() -> None:
    usage = calculate_buying_power_usage(
        [
            {"max_loss_per_contract": 500.0, "qty": 2},
            {"max_loss_per_contract": "250", "qty": "1"},
            {"max_loss_per_contract": "bad", "qty": 3},
        ],
        capital_raw=100000.0,
    )

    assert usage.used == 1250.0
    assert usage.capital == 100000.0
    assert usage.percent == 1.25


def test_derive_realized_pnl_delta_from_equity_uses_default_capital() -> None:
    assert derive_realized_pnl_delta_from_equity(101250.0, capital_raw=None) == 1250.0


def test_on_balance_updated_reconciles_idle_paper_realized_delta() -> None:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.trading_mode = TradingMode.PAPER
    dash.trading_active = False
    dash._paper_initial_capital = 100000.0
    dash._pnl_stats_by_mode = {TradingMode.PAPER: {"today_pnl": "$+0.00"}}
    dash._refresh_pnl_table = MagicMock()
    dash._apply_spyderbox_paper_account_snapshot = lambda: False
    calls: list[dict] = []
    dash._set_spyderbox_account_panel_values = lambda **kwargs: calls.append(kwargs)

    SpyderTradingDashboard._on_balance_updated(dash, "paper", 101250.0, 99000.0)

    assert calls == [
        {"settled": 101250.0, "buying": 99000.0},
        {"realized": 1250.0},
    ]
    dash._refresh_pnl_table.assert_called_once_with({"today_pnl": "$+0.00"})


def test_on_balance_updated_prefers_live_paper_cache_when_active(monkeypatch) -> None:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.trading_mode = TradingMode.PAPER
    dash.trading_active = True
    dash._paper_initial_capital = 100000.0
    dash._portfolio_summary_cache = {
        "equity": 100245.0,
        "cash": 100000.0,
        "realized_pnl": 0.0,
        "unrealized_pnl": 245.0,
        "spreads_unrealized_pnl": 245.0,
        "open_spreads_detail": [{"id": "spread-1"}],
    }
    dash._pnl_stats_by_mode = {TradingMode.PAPER: {"today_pnl": "$+0.00"}}
    dash._refresh_pnl_table = MagicMock()
    dash._get_mode_session_db = MagicMock(return_value=object())
    dash._is_paper_session_active_for_display = MagicMock(return_value=True)
    dash._apply_spyderbox_paper_account_snapshot = MagicMock(return_value=True)
    dash._set_spyderbox_account_panel_values = MagicMock()

    SpyderTradingDashboard._on_balance_updated(dash, "paper", 99850.0, 99850.0)

    dash._set_spyderbox_account_panel_values.assert_called_once_with(
        settled=100245.0,
        buying=100000.0,
        realized=0.0,
        unrealized=245.0,
    )
    dash._apply_spyderbox_paper_account_snapshot.assert_not_called()
    dash._refresh_pnl_table.assert_not_called()


def test_on_balance_updated_applies_latest_paper_snapshot_when_active_without_live_cache(monkeypatch) -> None:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.trading_mode = TradingMode.PAPER
    dash.trading_active = True
    dash._paper_initial_capital = 100000.0
    dash._portfolio_summary_cache = {}
    dash._pnl_stats_by_mode = {TradingMode.PAPER: {"today_pnl": "$+0.00"}}
    dash._refresh_pnl_table = MagicMock()
    dash._get_mode_session_db = MagicMock(return_value=object())
    dash._is_paper_session_active_for_display = MagicMock(return_value=True)
    dash._apply_spyderbox_paper_account_snapshot = MagicMock(return_value=True)
    dash._set_spyderbox_account_panel_values = MagicMock()

    SpyderTradingDashboard._on_balance_updated(dash, "paper", 100202.86, 100202.86)

    dash._set_spyderbox_account_panel_values.assert_called_once_with(
        settled=100202.86,
        buying=100202.86,
    )
    dash._apply_spyderbox_paper_account_snapshot.assert_called_once_with()
    dash._refresh_pnl_table.assert_not_called()


def test_apply_spyderbox_paper_account_snapshot_uses_latest_h05_values(monkeypatch) -> None:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.logger = MagicMock()
    calls: list[dict] = []
    dash._set_spyderbox_account_panel_values = lambda **kwargs: calls.append(kwargs)

    paper_db = MagicMock()
    paper_db.get_latest_snapshot.return_value = {
        "equity": 100202.86,
        "buying_power": 100202.86,
        "realized_pnl": 25.0,
        "unrealized_pnl": -320.35,
    }

    monkeypatch.setattr(
        h05,
        "TradingSessionDB",
        MagicMock(for_paper=MagicMock(return_value=paper_db)),
    )

    assert SpyderTradingDashboard._apply_spyderbox_paper_account_snapshot(dash) is True
    assert calls == [
        {
            "settled": 100202.86,
            "buying": 100202.86,
            "realized": 25.0,
            "unrealized": -320.35,
        },
    ]


def test_on_paper_metrics_uses_capital_baseline_fallback(monkeypatch) -> None:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash._paper_initial_capital = 125000.0
    dash._closed_trades_cache = []
    dash._set_spyderbox_account_panel_values = MagicMock()
    dash._refresh_pnl_table = MagicMock()
    captured: dict[str, float] = {}

    def _fake_build_today_trade_analytics(*args, **kwargs):
        _ = args
        captured["initial_capital"] = kwargs["initial_capital"]
        return {"today_pnl": "$+25.00"}

    monkeypatch.setattr(g05, "build_today_trade_analytics", _fake_build_today_trade_analytics)

    SpyderTradingDashboard._on_paper_metrics(
        dash,
        {
            "equity": "$101,000.00",
            "realized_pnl": "$+25.00",
            "max_drawdown": "0",
        },
    )

    assert captured["initial_capital"] == 125000.0
    dash._set_spyderbox_account_panel_values.assert_any_call(settled=101000.0)
    dash._set_spyderbox_account_panel_values.assert_any_call(realized=25.0)
    dash._refresh_pnl_table.assert_called_once()
