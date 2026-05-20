#!/usr/bin/env python3
"""Regression tests for G18 EOD snapshot persistence behavior."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from Spyder.SpyderG_GUI import SpyderG18_MarketDataWorker as g18
from Spyder.SpyderG_GUI.SpyderG18_MarketDataWorker import ThreadSafeMarketDataWorker


def _build_worker(tmp_path: Path) -> ThreadSafeMarketDataWorker:
    worker = ThreadSafeMarketDataWorker.__new__(ThreadSafeMarketDataWorker)
    worker.data_file = tmp_path / "live_data.json"
    worker.eod_snapshot_fetched = SimpleNamespace(emit=MagicMock())
    worker.market_data_status_changed = SimpleNamespace(emit=MagicMock())
    return worker


class _Client:
    def __init__(self, quotes: list[dict]) -> None:
        self._quotes = quotes

    def get_quotes(self, _symbols: list[str]) -> dict:
        return {"quotes": {"quote": self._quotes}}

    def get_time_sales(self, *_args, **_kwargs) -> dict:
        return {}

    def get_historical_quotes(self, *_args, **_kwargs) -> dict:
        return {}


def test_eod_snapshot_writes_dia_sidecar(monkeypatch, tmp_path: Path) -> None:
    worker = _build_worker(tmp_path)
    quotes = [
        {"symbol": "SPY", "last": 739.17, "change": -9.0, "change_percentage": -1.21},
        {"symbol": "SPX", "last": 7408.5, "prevclose": 7408.5},
        {"symbol": "$DJI", "last": 49526.17, "prevclose": 50063.46},
        {"symbol": "DIA", "last": 495.37, "change": -5.16, "change_percentage": -1.03},
    ]

    monkeypatch.setattr(g18, "TRADIER_AVAILABLE", True)
    monkeypatch.setattr(g18, "_build_market_data_client", lambda: _Client(quotes))
    monkeypatch.setattr(g18, "_fetch_vxv_live_entry", lambda: None)

    ThreadSafeMarketDataWorker._fetch_eod_snapshot(worker)

    dia_sidecar = tmp_path / "dia_prev_day.json"
    assert dia_sidecar.exists()
    payload = json.loads(dia_sidecar.read_text())
    assert payload["close"] == 495.37
    assert payload["source"] == "tradier_eod_snapshot"

    worker.market_data_status_changed.emit.assert_called_once_with("EOD")
    worker.eod_snapshot_fetched.emit.assert_called_once_with(True)


def test_eod_snapshot_applies_cached_vxv_fallback(monkeypatch, tmp_path: Path) -> None:
    worker = _build_worker(tmp_path)

    # Seed cached VXV in the pre-existing live-data snapshot.
    worker.data_file.write_text(
        json.dumps({"VXV": {"last": 16.83, "change": 0.0, "change_pct": 0.0, "timestamp_ms": 1778876102000}}),
        encoding="utf-8",
    )

    quotes = [
        {"symbol": "SPY", "last": 739.17, "change": -9.0, "change_percentage": -1.21},
        {"symbol": "DIA", "last": 495.37, "change": -5.16, "change_percentage": -1.03},
    ]

    monkeypatch.setattr(g18, "TRADIER_AVAILABLE", True)
    monkeypatch.setattr(g18, "_build_market_data_client", lambda: _Client(quotes))
    monkeypatch.setattr(g18, "_fetch_vxv_live_entry", lambda: None)

    ThreadSafeMarketDataWorker._fetch_eod_snapshot(worker)

    eod_snapshot = tmp_path / "eod_snapshot.json"
    assert eod_snapshot.exists()
    payload = json.loads(eod_snapshot.read_text())
    assert "VXV" in payload
    assert payload["VXV"]["last"] == 16.83
    assert payload["VXV"].get("source") == "cached_vxv_fallback"


def test_eod_snapshot_fetches_live_vxv_when_cache_missing(monkeypatch, tmp_path: Path) -> None:
    worker = _build_worker(tmp_path)
    quotes = [
        {"symbol": "SPY", "last": 739.17, "change": -9.0, "change_percentage": -1.21},
        {"symbol": "DIA", "last": 495.37, "change": -5.16, "change_percentage": -1.03},
    ]

    monkeypatch.setattr(g18, "TRADIER_AVAILABLE", True)
    monkeypatch.setattr(g18, "_build_market_data_client", lambda: _Client(quotes))
    monkeypatch.setattr(
        g18,
        "_fetch_vxv_live_entry",
        lambda: {
            "last": 20.92,
            "change": -0.44,
            "change_pct": -2.06,
            "change_available": True,
            "timestamp_ms": 1779193531000,
            "source": "yfinance_vix3m",
        },
    )

    ThreadSafeMarketDataWorker._fetch_eod_snapshot(worker)

    payload = json.loads((tmp_path / "eod_snapshot.json").read_text())
    assert payload["VXV"]["last"] == 20.92
    assert payload["VXV"].get("source") == "yfinance_vix3m"


def test_live_fetch_adds_vxv_to_live_data(monkeypatch, tmp_path: Path) -> None:
    worker = ThreadSafeMarketDataWorker.__new__(ThreadSafeMarketDataWorker)
    worker.data_file = tmp_path / "live_data.json"
    worker._quiet_startup = True
    worker._shutdown_requested = False
    worker._emit_spy_market_data_event = MagicMock()

    quotes = [
        {"symbol": "SPY", "last": 739.17, "change": -9.0, "change_percentage": -1.21},
        {"symbol": "DIA", "last": 495.37, "change": -5.16, "change_percentage": -1.03},
    ]
    client = _Client(quotes)

    monkeypatch.setattr(g18, "TRADIER_AVAILABLE", True)
    monkeypatch.setattr(g18, "_build_market_data_client", lambda: client)
    monkeypatch.setattr(g18, "_get_cached_chain", lambda _client: None)
    monkeypatch.setattr(
        g18,
        "_fetch_vxv_live_entry",
        lambda: {
            "last": 20.92,
            "change": -0.44,
            "change_pct": -2.06,
            "change_available": True,
            "timestamp_ms": 1779193531000,
            "source": "yfinance_vix3m",
        },
    )

    ThreadSafeMarketDataWorker._fetch_live_data_from_tradier(worker)

    payload = json.loads(worker.data_file.read_text())
    assert payload["VXV"]["last"] == 20.92
    assert payload["VXV"].get("source") == "yfinance_vix3m"
