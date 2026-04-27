#!/usr/bin/env python3
"""Focused tests for S07 lead-lag metrics update pipeline (Phase 10)."""

import os
import sys
import types
import math
import importlib.util as _ilu
from datetime import datetime
from unittest.mock import MagicMock


def _ensure_mod(key: str):
    parts = key.split(".")
    for i in range(1, len(parts) + 1):
        anc = ".".join(parts[:i])
        if anc not in sys.modules:
            sys.modules[anc] = types.ModuleType(anc)
    return sys.modules[key]


class _AnyAttr(types.ModuleType):
    pytest_plugins = None  # prevent pytest UsageError during collection

    def __getattr__(self, name: str):
        return MagicMock()


for _pkg in ["PySide6", "PySide6.QtCore", "PySide6.QtWidgets", "PySide6.QtGui"]:
    sys.modules.setdefault(_pkg, _AnyAttr(_pkg))

_QtCore = sys.modules["PySide6.QtCore"]
_QtCore.QObject = object  # type: ignore
_QtCore.QTimer = MagicMock
_QtCore.Signal = lambda *a, **kw: MagicMock()

_u01 = _ensure_mod("Spyder.SpyderU_Utilities.SpyderU01_Logger")
_logger_cls = MagicMock()
_logger_cls.get_logger = MagicMock(return_value=MagicMock())
_u01.SpyderLogger = _logger_cls

_u02 = _ensure_mod("Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler")
_u02.SpyderErrorHandler = MagicMock

for _key in list(sys.modules):
    if _key.startswith("Spyder.SpyderU"):
        sys.modules.setdefault(_key[len("Spyder."):], sys.modules[_key])

# Pre-stub short-form S/F/N/A/C/B packages — prevents __init__.py import cascades
for _shortpkg in [
    "SpyderS_Signals",
    "SpyderS_Signals.SpyderS01_DIXCalculator",
    "SpyderS_Signals.SpyderS02_DIXScheduler",
    "SpyderS_Signals.SpyderS03_BlackSwanIndicator",
    "SpyderS_Signals.SpyderS04_BlackSwanScheduler",
    "SpyderS_Signals.SpyderS06_SKEWCalculator",
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
    "SpyderC_MarketData.SpyderC11_FuturesBasis",
    "SpyderB_Broker",
]:
    sys.modules.setdefault(_shortpkg, _AnyAttr(_shortpkg))

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_S07_PATH = os.path.join(
    _ROOT, "Spyder", "SpyderS_Signals", "SpyderS07_CustomMetricsOrchestrator.py"
)
_spec = _ilu.spec_from_file_location("_s07_lead_lag_module", _S07_PATH)
_s07_mod = _ilu.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_s07_mod)  # type: ignore[union-attr]

CustomMetricsOrchestrator = _s07_mod.CustomMetricsOrchestrator

# ---------------------------------------------------------------------------
# Shared fake snapshot
# ---------------------------------------------------------------------------
_LEAD_LAG_SNAPSHOT = {
    "es_price": 580.25,
    "spy_price": 579.75,
    "basis_bps": 8.5,
    "lead_lag_ms": 4.25,
    "es_impulse_score": 0.62,
    "confirm_direction": "up",
    "confirm_confidence": 0.62,
    "snapshot_ts": datetime.now().isoformat(),
}


def _make_orch():
    return CustomMetricsOrchestrator(config={"auto_start": False})


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_lead_lag_metrics_populate_from_snapshot(monkeypatch):
    """_update_lead_lag_metrics should write all scalar keys from the snapshot."""
    orch = _make_orch()

    fake_c11 = MagicMock()
    fake_c11.get_lead_lag_snapshot.return_value = _LEAD_LAG_SNAPSHOT
    monkeypatch.setattr(orch, "_get_c11_futures_basis", lambda: fake_c11)

    updated: dict = {}
    errors: list = []
    result = orch._update_lead_lag_metrics(updated, errors)

    assert result is True
    assert errors == []
    assert updated["ES_PRICE"] == 580.25
    assert updated["SPY_PRICE"] == 579.75
    assert updated["BASIS_BPS"] == 8.5
    assert updated["LEAD_LAG_MS"] == 4.25
    assert updated["ES_IMPULSE_SCORE"] == 0.62
    assert updated["CONFIRM_DIRECTION"] == "up"
    assert updated["CONFIRM_CONFIDENCE"] == 0.62

    ll = updated["LEAD_LAG"]
    assert isinstance(ll, dict)
    assert ll["basis_bps"] == 8.5
    assert ll["confirm_direction"] == "up"


def test_lead_lag_returns_false_on_error(monkeypatch):
    """When the C11 getter raises, _update_lead_lag_metrics returns False and records error."""
    orch = _make_orch()

    monkeypatch.setattr(orch, "_get_c11_futures_basis",
                        MagicMock(side_effect=RuntimeError("c11 offline")))

    updated: dict = {}
    errors: list = []
    result = orch._update_lead_lag_metrics(updated, errors)

    assert result is False
    assert any("lead-lag" in e for e in errors)


def test_current_metrics_contain_lead_lag_keys():
    """All 8 LEAD_LAG-related keys must be in current_metrics at init time."""
    orch = _make_orch()
    for key in ("ES_PRICE", "SPY_PRICE", "BASIS_BPS", "LEAD_LAG_MS",
                "ES_IMPULSE_SCORE", "CONFIRM_DIRECTION", "CONFIRM_CONFIDENCE", "LEAD_LAG"):
        assert key in orch.current_metrics, f"Missing key {key!r} in current_metrics"


def test_metric_quality_has_lead_lag_bucket():
    orch = _make_orch()
    assert "LEAD_LAG" in orch.metric_quality


def test_format_metrics_includes_lead_lag_keys(monkeypatch):
    """_format_metrics output must contain all 8 LEAD_LAG entries with value + quality."""
    orch = _make_orch()
    orch.current_metrics.update({
        "ES_PRICE": 580.25,
        "SPY_PRICE": 579.75,
        "BASIS_BPS": 8.5,
        "LEAD_LAG_MS": 4.25,
        "ES_IMPULSE_SCORE": 0.62,
        "CONFIRM_DIRECTION": "up",
        "CONFIRM_CONFIDENCE": 0.62,
        "LEAD_LAG": _LEAD_LAG_SNAPSHOT,
    })

    formatted = orch._format_metrics(orch.current_metrics)

    for key in ("ES_PRICE", "SPY_PRICE", "BASIS_BPS", "LEAD_LAG_MS",
                "ES_IMPULSE_SCORE", "CONFIRM_DIRECTION", "CONFIRM_CONFIDENCE", "LEAD_LAG"):
        assert key in formatted, f"Key {key!r} missing from _format_metrics output"
        assert "value" in formatted[key], f"Key {key!r} has no 'value' sub-key"
        assert "quality" in formatted[key], f"Key {key!r} has no 'quality' sub-key"


def test_get_current_market_conditions_includes_lead_lag_scalars():
    """get_current_market_conditions must expose all lead-lag scalars + dict."""
    orch = _make_orch()
    orch.current_metrics.update({
        "ES_PRICE": 580.25,
        "SPY_PRICE": 579.75,
        "BASIS_BPS": 8.5,
        "LEAD_LAG_MS": 4.25,
        "ES_IMPULSE_SCORE": 0.62,
        "CONFIRM_DIRECTION": "up",
        "CONFIRM_CONFIDENCE": 0.62,
        "LEAD_LAG": {},
    })

    conditions = orch.get_current_market_conditions()

    for key in ("es_price", "spy_price", "basis_bps", "lead_lag_ms",
                "es_impulse_score", "confirm_direction", "confirm_confidence", "lead_lag"):
        assert key in conditions, f"Key {key!r} missing from get_current_market_conditions()"


def test_snapshot_confirm_direction_preserved_in_lead_lag_dict(monkeypatch):
    """LEAD_LAG dict entry should preserve the confirm_direction string."""
    orch = _make_orch()

    snap = {**_LEAD_LAG_SNAPSHOT, "confirm_direction": "down"}
    fake_c11 = MagicMock()
    fake_c11.get_lead_lag_snapshot.return_value = snap
    monkeypatch.setattr(orch, "_get_c11_futures_basis", lambda: fake_c11)

    updated: dict = {}
    orch._update_lead_lag_metrics(updated, [])

    assert updated["CONFIRM_DIRECTION"] == "down"
    assert updated["LEAD_LAG"]["confirm_direction"] == "down"


def test_lead_lag_metrics_defaults_preserved_on_error(monkeypatch):
    """On failure the original current_metrics values should be written as defaults."""
    orch = _make_orch()
    orch.current_metrics["BASIS_BPS"] = 3.14

    monkeypatch.setattr(orch, "_get_c11_futures_basis",
                        MagicMock(side_effect=RuntimeError("c11 offline")))

    updated: dict = {}
    orch._update_lead_lag_metrics(updated, [])

    # Default should come from current_metrics
    assert updated["BASIS_BPS"] == 3.14
