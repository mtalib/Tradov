#!/usr/bin/env python3
"""Focused tests for G05 dashboard snapshot payload shaping."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard, TradingMode


def test_save_snapshot_uses_helper_payload(monkeypatch, tmp_path: Path) -> None:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash._SNAPSHOT_FILE = tmp_path / "dashboard_snapshot.json"
    dash.data_file = tmp_path / "market_data" / "placeholder.json"
    dash.trading_mode = TradingMode.LIVE
    dash._account_snapshot_by_mode = {
        TradingMode.LIVE: {"settled": 1000.0},
        TradingMode.PAPER: {"settled": 999.0},
    }
    dash._pnl_stats_by_mode = {
        TradingMode.LIVE: {"today_pnl": "$+5.00"},
        TradingMode.PAPER: {"today_pnl": "$+7.00"},
    }
    dash.market_data = {"SPY": {"last": 530.5, "change": 1.2, "change_pct": 0.23}}
    remember_calls: list[str] = []
    helper_calls: list[dict[str, object]] = []
    info_calls: list[tuple[object, ...]] = []
    warning_calls: list[tuple[object, ...]] = []
    fake_payload = {
        "_saved_at": 123.4,
        "trading_mode": "LIVE",
        "account_by_mode": {"LIVE": {"settled": 1000.0}, "PAPER": {}},
        "pnl_stats_by_mode": {"LIVE": {"today_pnl": "$+5.00"}, "PAPER": {}},
        "data": {"SPY": {"last": 530.5, "change": 1.2, "change_pct": 0.23}},
    }

    monkeypatch.setattr(dash, "_remember_current_account_snapshot", lambda: remember_calls.append("remember"))
    monkeypatch.setattr(g05.time, "time", lambda: 123.4)
    monkeypatch.setattr(
        g05,
        "build_dashboard_snapshot_payload",
        lambda **kwargs: helper_calls.append(dict(kwargs)) or fake_payload,
    )
    monkeypatch.setattr(
        g05,
        "logger",
        SimpleNamespace(
            info=lambda *args: info_calls.append(args),
            warning=lambda *args: warning_calls.append(args),
        ),
    )

    SpyderTradingDashboard._save_snapshot(dash)

    assert remember_calls == ["remember"]
    assert len(helper_calls) == 1
    assert helper_calls[0]["saved_at"] == 123.4
    assert helper_calls[0]["trading_mode"] == TradingMode.LIVE.value
    assert tuple(helper_calls[0]["mode_keys"]) == tuple(TradingMode)
    assert helper_calls[0]["account_snapshot_by_mode"] is dash._account_snapshot_by_mode
    assert helper_calls[0]["pnl_stats_by_mode"] is dash._pnl_stats_by_mode
    assert helper_calls[0]["market_data"] is dash.market_data
    assert helper_calls[0]["reset_mode_names"] == (TradingMode.PAPER.value,)
    assert json.loads(dash._SNAPSHOT_FILE.read_text(encoding="utf-8")) == fake_payload
    assert info_calls == [("Dashboard snapshot saved (%d symbols)", 1)]
    assert warning_calls == []


def test_save_snapshot_preserves_warning_boundary_on_write_failure(monkeypatch, tmp_path: Path) -> None:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash._SNAPSHOT_FILE = SimpleNamespace(
        parent=tmp_path,
        write_text=lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk full")),
    )
    dash.data_file = tmp_path / "market_data" / "placeholder.json"
    dash.trading_mode = TradingMode.LIVE
    dash._account_snapshot_by_mode = {}
    dash._pnl_stats_by_mode = {}
    dash.market_data = {}
    warning_calls: list[tuple[object, ...]] = []

    monkeypatch.setattr(dash, "_remember_current_account_snapshot", lambda: None)
    monkeypatch.setattr(
        g05,
        "build_dashboard_snapshot_payload",
        lambda **kwargs: {"_saved_at": kwargs["saved_at"], "trading_mode": "LIVE", "account_by_mode": {}, "pnl_stats_by_mode": {}, "data": {}},
    )
    monkeypatch.setattr(
        g05,
        "logger",
        SimpleNamespace(
            info=lambda *args: None,
            warning=lambda *args: warning_calls.append(args),
        ),
    )

    SpyderTradingDashboard._save_snapshot(dash)

    assert len(warning_calls) == 1
    assert warning_calls[0][0] == "Could not save dashboard snapshot: %s"
    assert str(warning_calls[0][1]) == "disk full"
