#!/usr/bin/env python3
"""Focused tests for the PCA proxy custom metrics."""

from __future__ import annotations

import json
import os
import sys
import types
import importlib.util as _ilu
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import numpy as np
import pandas as pd


def _ensure_mod(key: str):
    parts = key.split(".")
    for i in range(1, len(parts) + 1):
        anc = ".".join(parts[:i])
        if anc not in sys.modules:
            sys.modules[anc] = types.ModuleType(anc)
    return sys.modules[key]


class _AnyAttr(types.ModuleType):
    pytest_plugins = None

    def __getattr__(self, name: str):
        return MagicMock()


for _pkg in ["PySide6", "PySide6.QtCore", "PySide6.QtWidgets", "PySide6.QtGui"]:
    sys.modules.setdefault(_pkg, _AnyAttr(_pkg))

_QtCore = sys.modules["PySide6.QtCore"]
_QtCore.QObject = object  # type: ignore[attr-defined]
_QtCore.QTimer = MagicMock
_QtCore.Signal = lambda *a, **kw: MagicMock()

_u01 = _ensure_mod("Spyder.SpyderU_Utilities.SpyderU01_Logger")
_logger_cls = MagicMock()
_logger_cls.get_logger = MagicMock(return_value=MagicMock())
_u01.SpyderLogger = _logger_cls

_u02 = _ensure_mod("Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler")
_u02.SpyderErrorHandler = MagicMock

_b40 = _ensure_mod("Spyder.SpyderB_Broker.SpyderB40_TradierClient")
_b40.create_tradier_client_from_env = MagicMock(side_effect=RuntimeError("stubbed"))

for _key in list(sys.modules):
    if _key.startswith("Spyder.SpyderU") or _key.startswith("Spyder.SpyderB"):
        sys.modules.setdefault(_key[len("Spyder."):], sys.modules[_key])

for _shortpkg in [
    "SpyderS_Signals",
    "SpyderS_Signals.SpyderS01_DIXCalculator",
    "SpyderS_Signals.SpyderS02_DIXScheduler",
    "SpyderS_Signals.SpyderS03_BlackSwanIndicator",
    "SpyderS_Signals.SpyderS04_BlackSwanScheduler",
    "SpyderS_Signals.SpyderS06_SKEWCalculator",
    "SpyderS_Signals.SpyderS11_TradingViewInternals",
    "SpyderF_Analysis",
    "SpyderF_Analysis.SpyderF04_VolatilityAnalysis",
    "SpyderF_Analysis.SpyderF08_VolatilityRegime",
    "SpyderF_Analysis.SpyderF09_EntryFilters",
    "SpyderN_OptionsAnalytics",
    "SpyderN_OptionsAnalytics.SpyderN06_VolatilitySurfaceBuilder",
    "SpyderN_OptionsAnalytics.SpyderN09_GammaExposure",
    "SpyderN_OptionsAnalytics.SpyderN11_OptionsGreeksFlow",
    "SpyderA_Core",
    "SpyderA_Core.SpyderA03_Configuration",
    "SpyderA_Core.SpyderA05_EventManager",
    "SpyderC_MarketData",
    "SpyderB_Broker",
]:
    sys.modules.setdefault(_shortpkg, _AnyAttr(_shortpkg))

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_S14_PATH = os.path.join(_ROOT, "Spyder", "SpyderS_Signals", "SpyderS14_PCASignals.py")
_s14_spec = _ilu.spec_from_file_location("_s14_pca_signals_module", _S14_PATH)
_s14_mod = _ilu.module_from_spec(_s14_spec)  # type: ignore[arg-type]
sys.modules[_s14_spec.name] = _s14_mod  # type: ignore[index]
_s14_spec.loader.exec_module(_s14_mod)  # type: ignore[union-attr]

sys.modules.setdefault("SpyderS_Signals.SpyderS14_PCASignals", _s14_mod)
sys.modules.setdefault("Spyder.SpyderS_Signals.SpyderS14_PCASignals", _s14_mod)

_S07_PATH = os.path.join(_ROOT, "Spyder", "SpyderS_Signals", "SpyderS07_CustomMetricsOrchestrator.py")
_s07_spec = _ilu.spec_from_file_location("_s07_pca_module", _S07_PATH)
_s07_mod = _ilu.module_from_spec(_s07_spec)  # type: ignore[arg-type]
sys.modules[_s07_spec.name] = _s07_mod  # type: ignore[index]
_s07_spec.loader.exec_module(_s07_mod)  # type: ignore[union-attr]

PCASignalEngine = _s14_mod.PCASignalEngine
PCAMetricSnapshot = _s14_mod.PCAMetricSnapshot
SECTOR_PROXY_SYMBOLS = _s14_mod.SECTOR_PROXY_SYMBOLS
PCA_IV_BOOTSTRAP_ROWS = _s14_mod.PCA_IV_BOOTSTRAP_ROWS
CustomMetricsOrchestrator = _s07_mod.CustomMetricsOrchestrator


def _synthetic_prices() -> pd.DataFrame:
    dates = pd.bdate_range("2025-01-02", periods=220)
    rng = np.random.default_rng(42)
    market = rng.normal(0.0005, 0.0085, len(dates))
    idiosyncratic = rng.normal(0.0, 0.0040, (len(dates), len(SECTOR_PROXY_SYMBOLS)))
    sector_bias = np.linspace(-0.30, 0.30, len(SECTOR_PROXY_SYMBOLS))
    returns = (market[:, None] * (1.0 + sector_bias)) + idiosyncratic
    prices = 100.0 * np.exp(np.cumsum(returns, axis=0))
    return pd.DataFrame(prices, index=dates, columns=SECTOR_PROXY_SYMBOLS)


def _seed_iv_surface_history(engine: PCASignalEngine, rows: int = 48) -> None:
    start = datetime(2026, 4, 1, 14, 30, tzinfo=timezone.utc)
    for idx in range(rows):
        theta = idx / 6.0
        level = 0.19 + 0.025 * np.sin(theta)
        front_curve = 0.012 + 0.004 * np.cos(theta * 1.1)
        back_curve = 0.009 + 0.003 * np.sin(theta * 0.7 + 0.3)
        rr_25d = -0.025 + 0.010 * np.sin(theta * 0.9)
        fly_25d = 0.008 + 0.003 * np.cos(theta * 0.6)
        engine.record_iv_surface_snapshot(
            {
                "underlying": "SPY",
                "atm_iv_0dte": level + front_curve,
                "atm_iv_1dte": level + (front_curve * 0.8),
                "atm_iv_7dte": level,
                "atm_iv_30dte": level - back_curve,
                "term_slope_0_7": front_curve / (7.0 / 365.0),
                "term_slope_7_30": back_curve / (23.0 / 365.0),
                "rr_25d": rr_25d,
                "fly_25d": fly_25d,
                "surface_confidence": 0.80 + (0.10 * np.sin(theta * 0.5)),
                "surface_age_ms": 1200.0 + idx,
                "snapshot_ts": (start + timedelta(minutes=idx)).isoformat(),
            }
        )


def _write_scalar_iv_history(path, rows: int = 90) -> None:
    start = datetime(2025, 12, 1, tzinfo=timezone.utc)
    payload = []
    for idx in range(rows):
        theta = idx / 8.0
        iv_percent = 18.5 + (2.4 * np.sin(theta)) + (1.2 * np.cos(theta * 0.45))
        payload.append(
            {
                "date": (start + timedelta(days=idx)).date().isoformat(),
                "iv": float(iv_percent),
            }
        )
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_pca_proxy_snapshot_computes_from_synthetic_prices(monkeypatch, tmp_path) -> None:
    engine = PCASignalEngine(
        iv_surface_history_path=tmp_path / "proxy_surface_history.jsonl",
        iv_scalar_history_path=tmp_path / "proxy_scalar_iv.json",
    )
    monkeypatch.setattr(engine, "_load_price_matrix", lambda symbols: (_synthetic_prices(), "synthetic"))

    snapshot = engine._build_proxy_snapshot()

    assert snapshot.source == "synthetic"
    assert snapshot.status == "live"
    assert snapshot.universe_size == len(SECTOR_PROXY_SYMBOLS)
    assert np.isfinite(snapshot.signal_value)
    assert np.isfinite(snapshot.change)
    assert 0.0 < snapshot.explained_variance < 1.0
    assert snapshot.confidence > 0.0
    assert len(snapshot.details["recent_signal_history"]) == snapshot.details["history_window"]
    assert snapshot.details["regime_band"]
    assert snapshot.details["regime_color"].startswith("#")


def test_pca_iv_placeholder_snapshot_is_explicit(tmp_path) -> None:
    engine = PCASignalEngine(
        iv_surface_history_path=tmp_path / "placeholder_surface_history.jsonl",
        iv_scalar_history_path=tmp_path / "placeholder_scalar_iv.json",
    )

    snapshot = engine.get_iv_placeholder_snapshot()

    assert snapshot.placeholder is True
    assert snapshot.status == "placeholder"
    assert snapshot.source == "placeholder"
    assert snapshot.signal_value == 0.0
    assert "future" in snapshot.details["message"].lower()


def test_pca_iv_surface_history_seed_updates_placeholder_status(tmp_path) -> None:
    history_path = tmp_path / "spy_iv_surface_features.jsonl"
    engine = PCASignalEngine(
        iv_surface_history_path=history_path,
        iv_scalar_history_path=tmp_path / "seed_scalar_iv.json",
    )

    status = engine.record_iv_surface_snapshot(
        {
            "underlying": "SPY",
            "atm_iv_0dte": 0.18,
            "atm_iv_1dte": 0.19,
            "atm_iv_7dte": 0.21,
            "atm_iv_30dte": 0.24,
            "term_slope_0_7": 0.52,
            "term_slope_7_30": 0.31,
            "rr_25d": -0.03,
            "fly_25d": 0.01,
            "surface_confidence": 0.84,
            "surface_age_ms": 1500.0,
            "snapshot_ts": "2026-05-10T21:30:00+00:00",
        }
    )

    placeholder = engine.get_iv_placeholder_snapshot()

    assert history_path.exists()
    assert status["stored_snapshots"] == 1
    assert placeholder.details["stored_snapshots"] == 1
    assert placeholder.details["phase"] == "history-seeding"
    payload = json.loads(history_path.read_text(encoding="utf-8").splitlines()[0])
    assert payload["feature_vector_version"] == "v1"
    assert payload["feature_level"] == 0.21


def test_pca_iv_snapshot_computes_from_seeded_surface_history(tmp_path) -> None:
    history_path = tmp_path / "spy_iv_surface_features.jsonl"
    engine = PCASignalEngine(
        iv_surface_history_path=history_path,
        iv_scalar_history_path=tmp_path / "live_scalar_iv.json",
    )
    _seed_iv_surface_history(engine, rows=52)

    snapshot = engine.get_iv_snapshot()

    assert snapshot.status == "live"
    assert snapshot.placeholder is False
    assert snapshot.source == "surface-history"
    assert snapshot.universe_size >= 5
    assert 0.0 < snapshot.explained_variance < 1.0
    assert snapshot.details["phase"] == "live-seeding"
    assert snapshot.details["stored_snapshots"] == 52
    assert "feature_level" in snapshot.details["pc1_loadings"]
    assert len(snapshot.details["recent_signal_history"]) == snapshot.details["history_window"]


def test_pca_iv_bootstraps_from_scalar_iv_history(tmp_path) -> None:
    history_path = tmp_path / "spy_iv_surface_features.jsonl"
    scalar_history_path = tmp_path / "spy_iv_history.json"
    _write_scalar_iv_history(scalar_history_path, rows=96)

    engine = PCASignalEngine(
        iv_surface_history_path=history_path,
        iv_scalar_history_path=scalar_history_path,
    )

    status = engine.get_iv_surface_storage_status()
    snapshot = engine.get_iv_snapshot()

    assert history_path.exists()
    assert status["stored_snapshots"] == PCA_IV_BOOTSTRAP_ROWS
    assert status["phase"] == "live-seeding"
    assert snapshot.status == "live"
    assert snapshot.placeholder is False
    assert snapshot.details["stored_snapshots"] == PCA_IV_BOOTSTRAP_ROWS
    first_payload = json.loads(history_path.read_text(encoding="utf-8").splitlines()[0])
    assert first_payload["bootstrap_kind"] == "scalar-iv-history"
    assert 0.05 < first_payload["feature_level"] < 1.0


def test_s07_pca_metric_update_and_formatting() -> None:
    orch = CustomMetricsOrchestrator(config={"auto_start": False})
    now = datetime.now(timezone.utc)
    orch.pca_signal_engine = MagicMock()
    orch.pca_signal_engine.get_proxy_snapshot.return_value = PCAMetricSnapshot(
        signal_value=1.25,
        previous_value=0.75,
        explained_variance=0.41,
        spectral_gap=0.18,
        dispersion_score=0.67,
        universe_size=11,
        confidence=0.51,
        timestamp=now,
        source="synthetic",
        details={"pc1_score": 0.91},
    )
    orch.pca_signal_engine.get_iv_snapshot.return_value = PCAMetricSnapshot(
        signal_value=0.0,
        previous_value=0.0,
        explained_variance=0.0,
        spectral_gap=0.0,
        dispersion_score=0.0,
        universe_size=0,
        confidence=0.0,
        timestamp=now,
        source="placeholder",
        placeholder=True,
        status="placeholder",
        details={"message": "future iv pca"},
    )

    updated: dict = {}
    errors: list[str] = []
    ok = orch._update_pca_metrics(updated, errors)

    assert ok is True
    assert errors == []
    assert updated["PCA-PROXY"] == 1.25
    assert updated["PCA-PROXY_CHANGE"] == 0.5
    assert updated["PCA-IV"] == 0.0
    assert updated["PCA-IV_DETAILS"]["status"] == "placeholder"

    orch.current_metrics.update(updated)
    formatted = orch._format_metrics(orch.current_metrics)

    assert formatted["PCA-PROXY"]["change"] == 0.5
    assert formatted["PCA-PROXY"]["details"]["source"] == "synthetic"
    assert formatted["PCA-IV"]["formatted"] == "PEND"


def test_s07_formats_live_pca_iv_metric() -> None:
    orch = CustomMetricsOrchestrator(config={"auto_start": False})
    now = datetime.now(timezone.utc)
    orch.pca_signal_engine = MagicMock()
    orch.pca_signal_engine.get_proxy_snapshot.return_value = PCAMetricSnapshot(
        signal_value=0.50,
        previous_value=0.25,
        explained_variance=0.40,
        spectral_gap=0.10,
        dispersion_score=0.20,
        universe_size=11,
        confidence=0.45,
        timestamp=now,
        source="synthetic",
        details={},
    )
    orch.pca_signal_engine.get_iv_snapshot.return_value = PCAMetricSnapshot(
        signal_value=0.84,
        previous_value=0.34,
        explained_variance=0.55,
        spectral_gap=0.22,
        dispersion_score=0.18,
        universe_size=7,
        confidence=0.68,
        timestamp=now,
        source="surface-history",
        status="live",
        details={
            "phase": "live-seeding",
            "stored_snapshots": 48,
            "pc1_loadings": {"feature_level": 0.61},
        },
    )

    updated: dict = {}
    errors: list[str] = []
    ok = orch._update_pca_metrics(updated, errors)

    assert ok is True
    assert errors == []
    assert updated["PCA-IV"] == 0.84
    assert updated["PCA-IV_DETAILS"]["status"] == "live"

    orch.current_metrics.update(updated)
    formatted = orch._format_metrics(orch.current_metrics)

    assert formatted["PCA-IV"]["formatted"] == "+0.84"
    assert formatted["PCA-IV"]["details"]["source"] == "surface-history"


def test_s07_vol_surface_update_seeds_pca_iv_history() -> None:
    orch = CustomMetricsOrchestrator(config={"auto_start": False})
    orch.pca_signal_engine = MagicMock()
    builder = MagicMock()
    builder.get_term_structure_snapshot.return_value = {
        "underlying": "SPY",
        "atm_iv_0dte": 0.18,
        "atm_iv_1dte": 0.19,
        "atm_iv_7dte": 0.21,
        "atm_iv_30dte": 0.24,
        "term_slope_0_7": 0.52,
        "term_slope_7_30": 0.31,
        "rr_25d": -0.03,
        "fly_25d": 0.01,
        "surface_confidence": 0.84,
        "surface_age_ms": 1500.0,
        "snapshot_ts": "2026-05-10T21:30:00+00:00",
    }
    orch._get_vol_surface_builder = MagicMock(return_value=builder)
    orch.pca_signal_engine.record_iv_surface_snapshot.return_value = {
        "history_path": "data/cache/pca_iv_surface_history/spy_iv_surface_features.jsonl",
        "stored_snapshots": 12,
        "first_snapshot_ts": "2026-05-10T20:00:00+00:00",
        "last_snapshot_ts": "2026-05-10T21:30:00+00:00",
        "target_snapshots": 120,
        "readiness_progress": 0.10,
        "phase": "history-seeding",
        "feature_columns": ["feature_level", "feature_skew"],
    }

    updated = {
        "PCA-IV_DETAILS": {
            "source": "placeholder",
            "status": "placeholder",
            "details": {
                "message": "Reserved for future SPY IV-surface PCA factor model.",
                "target_surface": "moneyness x dte implied-vol grid",
                "phase": "placeholder",
            },
        }
    }
    errors: list[str] = []

    ok = orch._update_vol_surface_metrics(updated, errors)

    assert ok is True
    assert errors == []
    orch.pca_signal_engine.record_iv_surface_snapshot.assert_called_once()
    assert updated["PCA-IV_DETAILS"]["details"]["stored_snapshots"] == 12
    assert updated["PCA-IV_DETAILS"]["details"]["phase"] == "history-seeding"