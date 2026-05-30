#!/usr/bin/env python3
"""Focused tests for S07 sector breadth expansion + data-quality feed (Phases 11/12)."""

import os
import sys
import types
import math
import importlib.util as _ilu
from datetime import datetime, timedelta
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

# Pre-stub short-form packages to avoid heavy import cascades
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

_S07_PATH = os.path.join(
    _ROOT, "Spyder", "SpyderS_Signals", "SpyderS07_CustomMetricsOrchestrator.py"
)
_spec = _ilu.spec_from_file_location("_s07_breadth_quality_module", _S07_PATH)
_s07_mod = _ilu.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_s07_mod)  # type: ignore[union-attr]

CustomMetricsOrchestrator = _s07_mod.CustomMetricsOrchestrator


def _make_orch():
    return CustomMetricsOrchestrator(config={"auto_start": False})


def test_current_metrics_contains_sector_breadth_and_quality_feed_keys():
    orch = _make_orch()
    for key in (
        "BREADTH_DEFENSIVE",
        "BREADTH_CYCLICAL",
        "BREADTH_SPREAD",
        "SECTOR_ADV_DEC",
        "SECTOR_MOMENTUM_DISPERSION",
        "PARTICIPATION_SCORE",
        "SECTOR_BREADTH",
        "DATA_QUALITY_FEED",
    ):
        assert key in orch.current_metrics
    assert "SECTOR_BREADTH" in orch.metric_quality


def test_update_tv_breadth_metrics_populates_sector_expansion_fields():
    orch = _make_orch()

    fake_tv = MagicMock()
    fake_tv.get_snapshot.return_value = {
        "tick": 420.0,
        "add": 1200.0,
        "trin": 0.92,
        "breadth_regime": "risk_on",
        "sector_defensive_breadth": 38.0,
        "sector_cyclical_breadth": 61.0,
        "sector_adv_dec": 870.0,
        "sector_momentum_dispersion": 1.85,
        "participation_score": 72.5,
        "snapshot_ts": datetime.now().isoformat(),
    }
    orch.tv_client = fake_tv

    updated: dict = {}
    errors: list = []
    ok = orch._update_tv_breadth_metrics(updated, errors)

    assert ok is True
    assert errors == []
    assert updated["BREADTH_DEFENSIVE"] == 38.0
    assert updated["BREADTH_CYCLICAL"] == 61.0
    assert updated["BREADTH_SPREAD"] == 23.0
    assert updated["SECTOR_ADV_DEC"] == 870.0
    assert updated["SECTOR_MOMENTUM_DISPERSION"] == 1.85
    assert updated["PARTICIPATION_SCORE"] == 72.5

    envelope = updated["SECTOR_BREADTH"]
    assert isinstance(envelope, dict)
    assert envelope["breadth_regime"] == "risk_on"
    assert envelope["spread"] == 23.0


def test_data_quality_feed_contains_slo_and_bucket_freshness():
    orch = _make_orch()

    # Force one stale bucket so freshness score is < 1.0
    stale_name = "BREADTH"
    orch.metric_quality[stale_name].last_successful_update = datetime.now() - timedelta(seconds=600)
    orch.metric_quality[stale_name].quality_score = 0.4

    feed = orch._build_data_quality_feed({"TICK": 100.0}, ["Breadth update error: timeout"])

    assert feed["feed"] == "data_quality"
    data = feed["data"]
    assert "overall_quality" in data
    assert "freshness_score" in data
    assert "slo_status" in data
    assert "quality_buckets" in data
    assert data["quality_buckets"][stale_name]["stale"] is True
    assert isinstance(data["slo_status"]["all_ok"], bool)


def test_format_metrics_includes_sector_breadth_and_quality_feed_entries():
    orch = _make_orch()

    feed = orch._build_data_quality_feed({}, [])
    orch.current_metrics.update({
        "BREADTH_DEFENSIVE": 42.0,
        "BREADTH_CYCLICAL": 58.0,
        "BREADTH_SPREAD": 16.0,
        "SECTOR_ADV_DEC": 900.0,
        "SECTOR_MOMENTUM_DISPERSION": 1.2,
        "PARTICIPATION_SCORE": 65.0,
        "SECTOR_BREADTH": {"breadth_regime": "risk_on"},
        "DATA_QUALITY_FEED": feed,
    })

    formatted = orch._format_metrics(orch.current_metrics)

    for key in (
        "BREADTH_DEFENSIVE",
        "BREADTH_CYCLICAL",
        "BREADTH_SPREAD",
        "SECTOR_ADV_DEC",
        "SECTOR_MOMENTUM_DISPERSION",
        "PARTICIPATION_SCORE",
        "SECTOR_BREADTH",
        "DATA_QUALITY_FEED",
    ):
        assert key in formatted
        assert "value" in formatted[key]
        assert "quality" in formatted[key]


def test_format_metrics_carries_quality_bucket_and_stale_metadata() -> None:
    orch = _make_orch()
    orch.metric_quality["BREADTH"].last_successful_update = datetime.now() - timedelta(seconds=600)

    feed = orch._build_data_quality_feed({"TICK": 100.0}, [])
    formatted = orch._format_metrics({"TICK": 100.0, "DATA_QUALITY_FEED": feed})

    assert formatted["TICK"]["quality_bucket"] == "BREADTH"
    assert formatted["TICK"]["stale"] is True


def test_get_current_market_conditions_includes_new_fields():
    orch = _make_orch()
    orch.current_metrics.update({
        "BREADTH_DEFENSIVE": 41.0,
        "BREADTH_CYCLICAL": 59.0,
        "BREADTH_SPREAD": 18.0,
        "SECTOR_ADV_DEC": 777.0,
        "SECTOR_MOMENTUM_DISPERSION": 1.4,
        "PARTICIPATION_SCORE": 70.0,
        "SECTOR_BREADTH": {"breadth_regime": "risk_on"},
        "DATA_QUALITY_FEED": {"feed": "data_quality", "data": {}},
    })

    conditions = orch.get_current_market_conditions()

    assert conditions["breadth_defensive"] == 41.0
    assert conditions["breadth_cyclical"] == 59.0
    assert conditions["breadth_spread"] == 18.0
    assert conditions["sector_adv_dec"] == 777.0
    assert conditions["sector_momentum_dispersion"] == 1.4
    assert conditions["participation_score"] == 70.0
    assert isinstance(conditions["sector_breadth"], dict)
    assert isinstance(conditions["data_quality_feed"], dict)
