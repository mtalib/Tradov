#!/usr/bin/env python3
"""Focused tests for G05 cached metrics fallback payload wiring."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard


def _build_dashboard_stub(tmp_path: Path) -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash._METRICS_SNAPSHOT_FILE = tmp_path / "overview_metrics_snapshot.json"
    return dash


def test_build_cached_metrics_fallback_payload_uses_helper_with_loaded_sources(
    monkeypatch,
    tmp_path: Path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    helper_calls: list[dict[str, object]] = []
    fake_snapshot = SimpleNamespace(
        signal_value=2.5,
        change=0.1,
        status="live",
        details={"source": "pca"},
    )
    iv_history = [
        {"iv": 0.20},
        {"iv": 0.24},
        {"iv": 0.28},
        {"iv": 0.32},
        {"iv": 0.36},
    ]

    monkeypatch.chdir(tmp_path)
    dash._METRICS_SNAPSHOT_FILE.write_text(
        json.dumps({"metrics": {"GEX": {"value": 1.25, "status": "cached"}}}),
        encoding="utf-8",
    )
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "dix_history_20260515.json").write_text(
        json.dumps({"dix_percentage": 47.1, "sentiment": "bullish"}),
        encoding="utf-8",
    )
    (tmp_path / "black_swan_reports").mkdir(parents=True, exist_ok=True)
    (tmp_path / "black_swan_reports" / "daily_report_20260515.json").write_text(
        json.dumps({"results": [{"score": 8.5, "status": "watch"}]}),
        encoding="utf-8",
    )
    (tmp_path / "data" / "cache").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "cache" / "nymo_ema_state.json").write_text(
        json.dumps({"ema_fast": 14.2, "ema_slow": 10.0}),
        encoding="utf-8",
    )
    (tmp_path / "data" / "cache" / "spy_iv_history.json").write_text(
        json.dumps(iv_history),
        encoding="utf-8",
    )
    monkeypatch.setitem(
        sys.modules,
        "SpyderS_Signals.SpyderS14_PCASignals",
        SimpleNamespace(
            get_pca_signal_engine=lambda: SimpleNamespace(get_iv_snapshot=lambda: fake_snapshot)
        ),
    )
    monkeypatch.setattr(
        g05,
        "build_cached_metrics_fallback_payload_from_sources",
        lambda **kwargs: helper_calls.append(dict(kwargs)) or {"GEX": {"value": 1.25}},
    )

    result = SpyderTradingDashboard._build_cached_metrics_fallback_payload(dash)

    assert result == {"GEX": {"value": 1.25}}
    assert helper_calls == [
        {
            "persisted_metrics": {"GEX": {"value": 1.25, "status": "cached"}},
            "pca_iv_snapshot": fake_snapshot,
            "dix_payload": {"dix_percentage": 47.1, "sentiment": "bullish"},
            "swan_payload": {"results": [{"score": 8.5, "status": "watch"}]},
            "nymo_payload": {"ema_fast": 14.2, "ema_slow": 10.0},
            "iv_history_payload": iv_history,
        }
    ]


def test_build_cached_metrics_fallback_payload_preserves_parse_failure_boundary(
    monkeypatch,
    tmp_path: Path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    helper_calls: list[dict[str, object]] = []

    monkeypatch.chdir(tmp_path)
    dash._METRICS_SNAPSHOT_FILE.write_text("{invalid json\n", encoding="utf-8")
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "dix_history_20260515.json").write_text("{invalid json\n", encoding="utf-8")
    (tmp_path / "black_swan_reports").mkdir(parents=True, exist_ok=True)
    (tmp_path / "black_swan_reports" / "daily_report_20260515.json").write_text(
        "{invalid json\n",
        encoding="utf-8",
    )
    (tmp_path / "data" / "cache").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "cache" / "nymo_ema_state.json").write_text(
        "{invalid json\n",
        encoding="utf-8",
    )
    (tmp_path / "data" / "cache" / "spy_iv_history.json").write_text(
        "{invalid json\n",
        encoding="utf-8",
    )
    monkeypatch.setitem(
        sys.modules,
        "SpyderS_Signals.SpyderS14_PCASignals",
        SimpleNamespace(get_pca_signal_engine=lambda: (_ for _ in ()).throw(RuntimeError("pca down"))),
    )
    monkeypatch.setattr(
        g05,
        "build_cached_metrics_fallback_payload_from_sources",
        lambda **kwargs: helper_calls.append(dict(kwargs)) or {},
    )

    result = SpyderTradingDashboard._build_cached_metrics_fallback_payload(dash)

    assert result == {}
    assert helper_calls == [
        {
            "persisted_metrics": None,
            "pca_iv_snapshot": None,
            "dix_payload": None,
            "swan_payload": None,
            "nymo_payload": None,
            "iv_history_payload": None,
        }
    ]
