#!/usr/bin/env python3
"""Focused tests for S07 dealer-flow metrics update pipeline (Phase 9)."""

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

# Mirror Spyder.SpyderU_Utilities.* → SpyderU_Utilities.* (short-form aliases)
for _key in list(sys.modules):
    if _key.startswith("Spyder.SpyderU"):
        sys.modules.setdefault(_key[len("Spyder."):], sys.modules[_key])

# Pre-stub short-form S-series, F-series, N-series, A-series, C-series packages
# so their __init__.py are never executed when S07 does bare `from SpyderXXX import`
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
    "SpyderB_Broker",
]:
    sys.modules.setdefault(_shortpkg, _AnyAttr(_shortpkg))

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_S07_PATH = os.path.join(
    _ROOT, "Spyder", "SpyderS_Signals", "SpyderS07_CustomMetricsOrchestrator.py"
)
_spec = _ilu.spec_from_file_location("_s07_dealer_module", _S07_PATH)
_s07_mod = _ilu.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_s07_mod)  # type: ignore[union-attr]

CustomMetricsOrchestrator = _s07_mod.CustomMetricsOrchestrator

# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------
_WALLS_SNAPSHOT = {
    "zero_gamma_level": 575.5,
    "spot_to_zero_gamma_pct": 0.775,
    "call_wall_levels": [585.0, 590.0],
    "put_wall_levels": [570.0],
    "wall_confidence": 0.75,
    "net_gex": 2.5e9,
    "regime": "moderate_positive",
    "snapshot_ts": datetime.now().isoformat(),
}

_VC_SNAPSHOT = {
    "vanna_pressure": 42_000.0,
    "charm_pressure": 18_000.0,
    "flow_imbalance_score": 0.042,
    "dealer_position": "long_gamma",
    "snapshot_ts": datetime.now().isoformat(),
}


def _make_orch():
    return CustomMetricsOrchestrator(config={"auto_start": False})


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_dealer_flow_metrics_populate_from_snapshots(monkeypatch):
    orch = _make_orch()

    fake_n09 = MagicMock()
    fake_n09.get_dealer_walls_snapshot.return_value = _WALLS_SNAPSHOT
    fake_n11 = MagicMock()
    fake_n11.get_vanna_charm_snapshot.return_value = _VC_SNAPSHOT

    monkeypatch.setattr(orch, "_get_n09_gex_analyzer", lambda: fake_n09)
    monkeypatch.setattr(orch, "_get_n11_flow_analyzer", lambda: fake_n11)

    updated: dict = {}
    errors: list = []
    result = orch._update_dealer_flow_metrics(updated, errors)

    assert result is True
    assert errors == []
    assert updated["ZERO_GAMMA"] == 575.5
    assert updated["WALL_CONFIDENCE"] == 0.75
    assert updated["VANNA_PRESSURE"] == 42_000.0
    assert updated["CHARM_PRESSURE"] == 18_000.0
    assert updated["FLOW_IMBALANCE"] == 0.042

    df = updated["DEALER_FLOW"]
    assert df["regime"] == "moderate_positive"
    assert df["dealer_position"] == "long_gamma"
    assert df["call_wall_levels"] == [585.0, 590.0]


def test_dealer_flow_returns_false_and_records_error_when_n09_fails(monkeypatch):
    orch = _make_orch()

    monkeypatch.setattr(orch, "_get_n09_gex_analyzer",
                        MagicMock(side_effect=RuntimeError("n09 offline")))
    fake_n11 = MagicMock()
    fake_n11.get_vanna_charm_snapshot.return_value = _VC_SNAPSHOT
    monkeypatch.setattr(orch, "_get_n11_flow_analyzer", lambda: fake_n11)

    updated: dict = {}
    errors: list = []
    result = orch._update_dealer_flow_metrics(updated, errors)

    assert result is False
    assert any("dealer walls" in e for e in errors)


def test_dealer_flow_returns_false_when_both_fail(monkeypatch):
    orch = _make_orch()

    monkeypatch.setattr(orch, "_get_n09_gex_analyzer",
                        MagicMock(side_effect=RuntimeError("n09 offline")))
    monkeypatch.setattr(orch, "_get_n11_flow_analyzer",
                        MagicMock(side_effect=RuntimeError("n11 offline")))

    updated: dict = {}
    errors: list = []
    result = orch._update_dealer_flow_metrics(updated, errors)

    assert result is False
    assert len(errors) == 2


def test_current_metrics_contain_dealer_flow_keys():
    orch = _make_orch()

    for key in ("ZERO_GAMMA", "WALL_CONFIDENCE", "VANNA_PRESSURE", "CHARM_PRESSURE",
                "FLOW_IMBALANCE", "DEALER_FLOW"):
        assert key in orch.current_metrics, f"Missing key {key!r} in current_metrics"


def test_metric_quality_has_dealer_flow_bucket():
    orch = _make_orch()
    assert "DEALER_FLOW" in orch.metric_quality


def test_format_metrics_includes_dealer_flow_keys():
    orch = _make_orch()
    orch.current_metrics.update({
        "ZERO_GAMMA": 575.5,
        "WALL_CONFIDENCE": 0.75,
        "VANNA_PRESSURE": 42_000.0,
        "CHARM_PRESSURE": 18_000.0,
        "FLOW_IMBALANCE": 0.042,
        "DEALER_FLOW": {"dealer_position": "long_gamma", "call_wall_levels": []},
    })

    formatted = orch._format_metrics(orch.current_metrics)

    for key in ("ZERO_GAMMA", "WALL_CONFIDENCE", "VANNA_PRESSURE", "CHARM_PRESSURE",
                "FLOW_IMBALANCE", "DEALER_FLOW"):
        assert key in formatted, f"Key {key!r} missing from _format_metrics output"
        assert "value" in formatted[key]
        assert "quality" in formatted[key]


def test_get_current_market_conditions_includes_dealer_flow_scalars():
    orch = _make_orch()
    orch.current_metrics.update({
        "ZERO_GAMMA": 575.5,
        "WALL_CONFIDENCE": 0.75,
        "VANNA_PRESSURE": 42_000.0,
        "CHARM_PRESSURE": 18_000.0,
        "FLOW_IMBALANCE": 0.042,
        "DEALER_FLOW": {},
    })

    conditions = orch.get_current_market_conditions()

    for key in ("zero_gamma", "wall_confidence", "vanna_pressure", "charm_pressure",
                "flow_imbalance"):
        assert key in conditions, f"Key {key!r} missing from get_current_market_conditions()"
