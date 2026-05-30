#!/usr/bin/env python3
"""Focused tests for S07 vol-surface publication."""

import os
import sys
import types
import importlib.util as _ilu
from unittest.mock import MagicMock


def _ensure_mod(key: str):
    parts = key.split('.')
    for i in range(1, len(parts) + 1):
        anc = '.'.join(parts[:i])
        if anc not in sys.modules:
            sys.modules[anc] = types.ModuleType(anc)
    return sys.modules[key]


class _AnyAttr(types.ModuleType):
    def __getattr__(self, name):
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

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_S07_PATH = os.path.join(
    _ROOT, "Spyder", "SpyderS_Signals", "SpyderS07_CustomMetricsOrchestrator.py"
)
_spec = _ilu.spec_from_file_location("_s07_vol_surface_module", _S07_PATH)
_s07_mod = _ilu.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_s07_mod)  # type: ignore[union-attr]

CustomMetricsOrchestrator = _s07_mod.CustomMetricsOrchestrator


def test_s07_vol_surface_metrics_populate_from_snapshot(monkeypatch):
    orch = CustomMetricsOrchestrator(config={"auto_start": False})
    fake_builder = MagicMock()
    fake_builder.get_term_structure_snapshot.return_value = {
        "atm_iv_0dte": 0.20,
        "atm_iv_1dte": 0.21,
        "atm_iv_7dte": 0.24,
        "atm_iv_30dte": 0.28,
        "term_slope_0_7": 2.08,
        "term_slope_7_30": 0.63,
        "rr_25d": 0.012,
        "fly_25d": 0.008,
        "surface_confidence": 0.87,
        "surface_age_ms": 1200,
        "snapshot_ts": "2026-04-25T12:00:00",
    }
    monkeypatch.setattr(orch, "_get_vol_surface_builder", lambda: fake_builder)

    updated = {}
    errors = []
    result = orch._update_vol_surface_metrics(updated, errors)

    assert result is True
    assert errors == []
    assert updated["ATM_IV_0DTE"] == 0.20
    assert updated["ATM_IV_7DTE"] == 0.24
    assert updated["TERM_SLOPE_0_7"] == 2.08
    assert updated["RR_25D"] == 0.012
    assert updated["SURFACE_CONFIDENCE"] == 0.87


def test_s07_vol_surface_metrics_build_surface_when_snapshot_missing(monkeypatch):
    orch = CustomMetricsOrchestrator(config={"auto_start": False})
    fake_builder = MagicMock()
    fake_builder.get_term_structure_snapshot.side_effect = [
        ValueError("No surface available for SPY"),
        {
            "atm_iv_0dte": 0.20,
            "atm_iv_1dte": 0.21,
            "atm_iv_7dte": 0.24,
            "atm_iv_30dte": 0.28,
            "term_slope_0_7": 2.08,
            "term_slope_7_30": 0.63,
            "rr_25d": 0.012,
            "fly_25d": 0.008,
            "surface_confidence": 0.87,
            "surface_age_ms": 1200,
            "snapshot_ts": "2026-04-25T12:00:00",
        },
    ]
    monkeypatch.setattr(orch, "_get_vol_surface_builder", lambda: fake_builder)
    fake_surface_data = object()
    monkeypatch.setattr(orch, "_get_spy_spot", lambda: 585.0)
    monkeypatch.setattr(orch, "_load_vol_surface_chain_dataframe", lambda: fake_surface_data)

    updated = {}
    errors = []
    result = orch._update_vol_surface_metrics(updated, errors)

    assert result is True
    assert errors == []
    fake_builder.build_surface.assert_called_once_with("SPY", fake_surface_data, 585.0)
    assert updated["ATM_IV_0DTE"] == 0.20
    assert updated["SURFACE_AGE_MS"] == 1200


def test_s07_vol_surface_metrics_fall_back_on_error(monkeypatch):
    orch = CustomMetricsOrchestrator(config={"auto_start": False})
    fake_builder = MagicMock()
    fake_builder.get_term_structure_snapshot.side_effect = RuntimeError("builder exploded")
    monkeypatch.setattr(orch, "_get_vol_surface_builder", lambda: fake_builder)

    updated = {}
    errors = []
    result = orch._update_vol_surface_metrics(updated, errors)

    assert result is False
    assert len(errors) == 1
    assert "vol surface update failed" in errors[0]
