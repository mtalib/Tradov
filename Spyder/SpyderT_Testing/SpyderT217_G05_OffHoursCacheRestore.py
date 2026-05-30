#!/usr/bin/env python3
"""Focused tests for G05 off-hours cache restore behavior."""

from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from Spyder.SpyderG_GUI import SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger


def _build_dashboard_stub(tmp_path: Path) -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.logger = SpyderLogger.get_logger(__name__)
    dash._shutdown_in_progress = False
    dash._SNAPSHOT_FILE = tmp_path / "dashboard_snapshot.json"
    dash._METRICS_SNAPSHOT_FILE = tmp_path / "overview_metrics_snapshot.json"
    dash._SNAPSHOT_STALE_HOURS = 24
    dash.data_file = tmp_path / "live_data.json"
    dash.market_data = {}
    dash.symbol_widgets = {
        "SPY": SimpleNamespace(update_data=MagicMock()),
        "SPX": SimpleNamespace(update_data=MagicMock()),
        "VIX": SimpleNamespace(update_data=MagicMock()),
        "DIX": SimpleNamespace(update_data=MagicMock()),
        "SWAN": SimpleNamespace(update_data=MagicMock()),
        "NYMO": SimpleNamespace(update_data=MagicMock()),
        "PCA-IV": SimpleNamespace(update_data=MagicMock()),
        "ATM_IV": SimpleNamespace(update_data=MagicMock()),
        "IVR": SimpleNamespace(update_data=MagicMock()),
        "GEX": SimpleNamespace(update_data=MagicMock()),
        "WRS": SimpleNamespace(update_data=MagicMock()),
    }
    dash.signal_panel = SimpleNamespace(update_live_data=MagicMock(), update_regime=MagicMock())
    dash.update_with_real_data = MagicMock()
    dash.update_toolbar_with_real_data = MagicMock()
    dash.update_data_status = MagicMock()
    dash.determine_data_status = MagicMock(return_value="REAL-TIME")
    dash.connection_info = SimpleNamespace(
        last_successful_data=None,
        data_was_live=False,
        market_data_status="NONE",
    )
    dash.trading_mode = g05.TradingMode.PAPER
    dash._account_snapshot_by_mode = {}
    dash._pnl_stats_by_mode = {}
    dash._apply_account_snapshot = MagicMock()
    dash.figure = None
    dash.canvas = None
    dash._last_custom_metrics_payload = {}
    dash._custom_metrics_live_announced = False
    dash._log_lines: list[str] = []
    dash.add_system_log = lambda message: dash._log_lines.append(str(message))
    dash.update_regime_pills = MagicMock()
    dash._update_liquidity_diagnostics_panel = MagicMock()
    dash.current_dialog = None
    dash._build_cached_metrics_fallback_payload = MagicMock(return_value={})
    return dash


def test_apply_proven_real_data_pattern_logs_dia_and_vxv_detail(
    monkeypatch,
    tmp_path: Path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    (tmp_path / "eod_snapshot.json").write_text(
        json.dumps(
            {
                "SPY": {"last": 742.31},
                "SPX": {"last": 7444.25},
                "$DJI": {"last": 49526.17},
                "DIA": {"last": 495.37},
                "VXV": {"last": 16.83},
                "_eod_date": "2026-05-13",
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(g05, "is_tradier_window", lambda: False)

    SpyderTradingDashboard.apply_proven_real_data_pattern(dash)

    assert any("EOD snapshot loaded" in line for line in dash._log_lines)
    assert any("DIA:" in line and "VXV:" in line for line in dash._log_lines)
    dash.update_data_status.assert_called_once_with("EOD")


def test_seed_optional_symbol_placeholders_marks_tnx_unavailable(tmp_path: Path) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash.symbol_widgets["TNX"] = SimpleNamespace(
        price_label=SimpleNamespace(text=lambda: "---"),
        set_unavailable=MagicMock(),
    )

    SpyderTradingDashboard._seed_optional_symbol_placeholders(dash)

    dash.symbol_widgets["TNX"].set_unavailable.assert_called_once_with("N/A")


def test_restore_snapshot_falls_back_to_eod_cache_outside_market_hours(
    monkeypatch,
    tmp_path: Path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._SNAPSHOT_FILE.write_text(
        json.dumps(
            {
                "_saved_at": time.time(),
                "trading_mode": "PAPER",
                "account_by_mode": {"PAPER": {}, "LIVE": {}},
                "pnl_stats_by_mode": {"PAPER": {}, "LIVE": {}},
                "data": {},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "eod_snapshot.json").write_text(
        json.dumps(
            {
                "SPY": {"last": 742.31, "change": 4.13, "change_pct": 0.56, "timestamp_ms": 1778704182000},
                "SPX": {"last": 7444.25, "change": 43.29, "change_pct": 0.59, "timestamp_ms": 1778704183528},
                "VIX": {"last": 17.87, "change": -0.12, "change_pct": -0.67, "timestamp_ms": 1778703301314},
                "_eod_date": "2026-05-13",
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(g05, "is_market_hours", lambda: False)

    SpyderTradingDashboard._restore_snapshot(dash)

    assert dash.market_data["SPY"]["last"] == 742.31
    assert dash.market_data["SPX"]["last"] == 7444.25
    dash.symbol_widgets["SPY"].update_data.assert_called_once()
    dash.signal_panel.update_live_data.assert_called_once_with({"VIX": 17.87})
    dash.update_toolbar_with_real_data.assert_called_once()
    dash.update_data_status.assert_called_once_with("EOD")
    assert dash.connection_info.market_data_status == "EOD"
    assert any("EOD snapshot cache" in line for line in dash._log_lines)


def test_restore_snapshot_merges_live_only_symbols_into_eod_cache(
    monkeypatch,
    tmp_path: Path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash.symbol_widgets["CPC"] = SimpleNamespace(update_data=MagicMock())
    dash._SNAPSHOT_FILE.write_text(
        json.dumps(
            {
                "_saved_at": time.time(),
                "trading_mode": "PAPER",
                "account_by_mode": {"PAPER": {}, "LIVE": {}},
                "pnl_stats_by_mode": {"PAPER": {}, "LIVE": {}},
                "data": {},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "eod_snapshot.json").write_text(
        json.dumps(
            {
                "SPY": {"last": 742.31, "change": 4.13, "change_pct": 0.56, "timestamp_ms": 1778704182000},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "live_data.json").write_text(
        json.dumps(
            {
                "SPY": {"last": 999.99, "change": 0.0, "change_pct": 0.0, "timestamp_ms": 1778713622000},
                "CPC": {"last": 1.206, "change": 0.0, "change_pct": 0.0, "timestamp_ms": 1778713623246},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(g05, "is_market_hours", lambda: False)

    SpyderTradingDashboard._restore_snapshot(dash)

    assert dash.market_data["SPY"]["last"] == 742.31
    assert dash.market_data["CPC"]["last"] == 1.206
    dash.symbol_widgets["CPC"].update_data.assert_called_once_with(
        {"last": 1.206, "change": 0.0, "change_pct": 0.0, "timestamp_ms": 1778713623246}
    )
    dash.signal_panel.update_live_data.assert_called_once_with({"CPC": 1.206})
    assert any("EOD snapshot + cached live quotes cache" in line for line in dash._log_lines)


def test_load_chart_candles_uses_prev_day_cache_outside_market_hours(
    monkeypatch,
    tmp_path: Path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    prev_day_bars = [
        {
            "time": "2026-05-13T15:55:00",
            "open": 741.5,
            "high": 742.5,
            "low": 741.2,
            "close": 742.31,
            "volume": 12345,
        }
    ]
    current_bars = [
        {
            "time": "2026-05-12T15:55:00",
            "open": 731.5,
            "high": 732.5,
            "low": 731.2,
            "close": 732.31,
            "volume": 54321,
        }
    ]
    (tmp_path / "spy_5min_prev_day.json").write_text(json.dumps(prev_day_bars), encoding="utf-8")
    (tmp_path / "spy_5min_chart.json").write_text(json.dumps(current_bars), encoding="utf-8")

    monkeypatch.setattr(g05, "is_market_hours", lambda: False)

    candles, filter_to_today = SpyderTradingDashboard._load_chart_candles_from_cache(dash)

    assert candles == prev_day_bars
    assert filter_to_today is False


def test_on_custom_metrics_updated_merges_and_persists_partial_payloads(tmp_path: Path) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._custom_metrics_live_announced = True

    SpyderTradingDashboard._on_custom_metrics_updated(
        dash,
        {"GEX": {"value": 1.25, "status": "live"}},
    )
    SpyderTradingDashboard._on_custom_metrics_updated(
        dash,
        {"WRS": {"value": 0.02}},
    )

    assert dash._last_custom_metrics_payload["GEX"]["value"] == 1.25
    assert dash._last_custom_metrics_payload["WRS"]["value"] == 0.02
    persisted = json.loads(dash._METRICS_SNAPSHOT_FILE.read_text(encoding="utf-8"))
    assert persisted["metrics"]["GEX"]["value"] == 1.25
    assert persisted["metrics"]["WRS"]["value"] == 0.02


def test_restore_snapshot_hydrates_cached_market_overview_metrics(
    monkeypatch,
    tmp_path: Path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._build_cached_metrics_fallback_payload = lambda: {
        "GEX": {"value": 1.5, "status": "cached"},
        "NYMO": {"value": -20.5},
    }
    dash._METRICS_SNAPSHOT_FILE.write_text(
        json.dumps({"_saved_at": time.time(), "metrics": {}}),
        encoding="utf-8",
    )
    dash._SNAPSHOT_FILE.write_text(
        json.dumps(
            {
                "_saved_at": time.time(),
                "trading_mode": "PAPER",
                "account_by_mode": {"PAPER": {}, "LIVE": {}},
                "pnl_stats_by_mode": {"PAPER": {}, "LIVE": {}},
                "data": {},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "eod_snapshot.json").write_text(
        json.dumps(
            {
                "SPY": {"last": 742.31, "change": 4.13, "change_pct": 0.56, "timestamp_ms": 1778704182000},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(g05, "is_market_hours", lambda: False)

    SpyderTradingDashboard._restore_snapshot(dash)

    dash.symbol_widgets["GEX"].update_data.assert_called_once()
    dash.symbol_widgets["NYMO"].update_data.assert_called_once()
    assert any("Market Overview metrics" in line for line in dash._log_lines)


def test_restore_snapshot_skips_stale_cached_market_overview_metrics(
    monkeypatch,
    tmp_path: Path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._build_cached_metrics_fallback_payload = lambda: {
        "GEX": {"value": 1.5, "status": "cached"},
    }
    dash._METRICS_SNAPSHOT_FILE.write_text(
        json.dumps(
            {
                "_saved_at": time.time() - (SpyderTradingDashboard._CUSTOM_METRICS_SNAPSHOT_MAX_AGE_SECONDS + 1),
                "metrics": {},
            }
        ),
        encoding="utf-8",
    )
    dash._SNAPSHOT_FILE.write_text(
        json.dumps(
            {
                "_saved_at": time.time(),
                "trading_mode": "PAPER",
                "account_by_mode": {"PAPER": {}, "LIVE": {}},
                "pnl_stats_by_mode": {"PAPER": {}, "LIVE": {}},
                "data": {},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "eod_snapshot.json").write_text(
        json.dumps(
            {
                "SPY": {"last": 742.31, "change": 4.13, "change_pct": 0.56, "timestamp_ms": 1778704182000},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(g05, "is_market_hours", lambda: False)

    SpyderTradingDashboard._restore_snapshot(dash)

    dash.symbol_widgets["GEX"].update_data.assert_not_called()
    assert any("Skipped cached Market Overview metrics" in line for line in dash._log_lines)


def test_restore_snapshot_applies_live_account_snapshot_only(
    monkeypatch,
    tmp_path: Path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash.trading_mode = g05.TradingMode.LIVE
    live_account = {
        "settled_cash": 101000.0,
        "buying_power": 99000.0,
        "realized_pnl": 25.0,
        "unrealized_pnl": -5.0,
    }
    dash._SNAPSHOT_FILE.write_text(
        json.dumps(
            {
                "_saved_at": time.time(),
                "trading_mode": "LIVE",
                "account_by_mode": {
                    "PAPER": {"settled_cash": 1.0},
                    "LIVE": live_account,
                },
                "pnl_stats_by_mode": {"PAPER": {}, "LIVE": {}},
                "data": {},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "eod_snapshot.json").write_text(
        json.dumps(
            {
                "SPY": {"last": 742.31, "change": 4.13, "change_pct": 0.56, "timestamp_ms": 1778704182000},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(g05, "is_market_hours", lambda: False)

    SpyderTradingDashboard._restore_snapshot(dash)

    dash._apply_account_snapshot.assert_called_once_with(live_account)
