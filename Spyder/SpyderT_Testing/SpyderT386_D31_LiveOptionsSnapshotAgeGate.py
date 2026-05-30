#!/usr/bin/env python3
"""Focused regressions for D31 live options snapshot freshness gating."""

from __future__ import annotations

import importlib
import json
import os
import time
from pathlib import Path

import pandas as pd
import pytest


def _make_orchestrator():
    mod = importlib.import_module(
        "Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator"
    )
    orch = mod.StrategyOrchestrator.__new__(mod.StrategyOrchestrator)
    orch._live_options_metrics_loaded_monotonic = 0.0
    orch._live_options_metrics_snapshot = {}
    orch.market_data_cache = {}
    return orch


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_enrich_market_df_with_options_metrics_uses_fresh_overview_snapshot(
    monkeypatch,
    tmp_path: Path,
) -> None:
    orch = _make_orchestrator()
    home_dir = tmp_path / "home"
    market_data_dir = home_dir / "Projects" / "Spyder" / "market_data"
    _write_json(
        market_data_dir / "overview_metrics_snapshot.json",
        {
            "_saved_at": time.time(),
            "metrics": {
                "ATM_IV": {"value": 25.0},
                "IVR": {"value": 44.0},
            },
        },
    )

    monkeypatch.setattr(Path, "home", lambda: home_dir)

    enriched = orch._enrich_market_df_with_options_metrics(
        pd.DataFrame({"close": [500.0, 501.0]})
    )

    assert enriched["iv"].tolist() == pytest.approx([0.25, 0.25])
    assert enriched["iv_rank"].tolist() == pytest.approx([44.0, 44.0])


def test_enrich_market_df_with_options_metrics_ignores_stale_disk_snapshots(
    monkeypatch,
    tmp_path: Path,
) -> None:
    orch = _make_orchestrator()
    home_dir = tmp_path / "home"
    market_data_dir = home_dir / "Projects" / "Spyder" / "market_data"
    stale_saved_at = time.time() - 181.0

    _write_json(
        market_data_dir / "overview_metrics_snapshot.json",
        {
            "_saved_at": stale_saved_at,
            "metrics": {
                "ATM_IV": {"value": 25.0},
                "IVR": {"value": 44.0},
            },
        },
    )
    _write_json(
        market_data_dir / "live_data.json",
        {
            "ATM_IV": {"last": 25.0},
            "IVR": {"last": 44.0},
        },
    )
    _write_json(
        market_data_dir / "dashboard_snapshot.json",
        {
            "_saved_at": stale_saved_at,
            "data": {
                "ATM_IV": {"last": 25.0},
                "IVR": {"last": 44.0},
            },
        },
    )
    for file_name in ("live_data.json", "dashboard_snapshot.json"):
        os.utime(market_data_dir / file_name, (stale_saved_at, stale_saved_at))

    monkeypatch.setattr(Path, "home", lambda: home_dir)

    enriched = orch._enrich_market_df_with_options_metrics(
        pd.DataFrame({"close": [500.0, 501.0]})
    )

    assert "iv" not in enriched.columns
    assert "iv_rank" not in enriched.columns


def test_enrich_market_df_with_options_metrics_uses_fresh_live_data_fallback(
    monkeypatch,
    tmp_path: Path,
) -> None:
    orch = _make_orchestrator()
    home_dir = tmp_path / "home"
    market_data_dir = home_dir / "Projects" / "Spyder" / "market_data"
    _write_json(
        market_data_dir / "live_data.json",
        {
            "ATM_IV": {"last": 24.0},
            "IVR": {"last": 52.0},
        },
    )

    monkeypatch.setattr(Path, "home", lambda: home_dir)

    enriched = orch._enrich_market_df_with_options_metrics(
        pd.DataFrame({"close": [500.0, 501.0]})
    )

    assert enriched["iv"].tolist() == pytest.approx([0.24, 0.24])
    assert enriched["iv_rank"].tolist() == pytest.approx([52.0, 52.0])
