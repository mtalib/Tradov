#!/usr/bin/env python3
"""Focused tests for S07 liquidity diagnostics publication."""

import os
import sys
import types
import importlib.util as _ilu
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pandas as pd
import pytest


def _ensure_mod(key: str):
    parts = key.split(".")
    for i in range(1, len(parts) + 1):
        anc = ".".join(parts[:i])
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
_spec = _ilu.spec_from_file_location("_s07_liquidity_module", _S07_PATH)
_s07_mod = _ilu.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_s07_mod)  # type: ignore[union-attr]

CustomMetricsOrchestrator = _s07_mod.CustomMetricsOrchestrator


def test_s07_liquidity_diagnostics_publishes_observe_payload(monkeypatch):
    orch = CustomMetricsOrchestrator(config={"auto_start": False})
    orch.current_metrics["OGL"] = 585.0

    now = datetime.now()
    chain_df = pd.DataFrame([
        {
            "symbol": "SPY",
            "strike": 585.0,
            "expiry": now + timedelta(days=1),
            "option_type": "CALL",
            "bid": 1.00,
            "ask": 1.10,
            "mid_price": 1.05,
            "spread": 0.10,
            "volume": 120,
            "open_interest": 900,
            "timestamp": now - timedelta(milliseconds=900),
        },
        {
            "symbol": "SPY",
            "strike": 586.0,
            "expiry": now + timedelta(days=1),
            "option_type": "PUT",
            "bid": 1.20,
            "ask": 1.35,
            "mid_price": 1.275,
            "spread": 0.15,
            "volume": 75,
            "open_interest": 850,
            "timestamp": now - timedelta(milliseconds=1100),
        },
    ])

    monkeypatch.setattr(orch, "_load_options_chain_dataframe", lambda: chain_df)

    updated = {}
    errors = []
    result = orch._update_liquidity_diagnostics_metrics(updated, errors)

    assert result is True
    assert errors == []
    payload = updated["LIQUIDITY_DIAGNOSTICS"]
    assert payload["feed"] == "liquidity_diagnostics"
    assert payload["mode"] == "observe"
    assert payload["data"]["candidate_count"] == 2

    first = payload["data"]["candidates"][0]
    assert first["strike"] == pytest.approx(585.0)
    assert first["snapshot"]["spread_abs"] == pytest.approx(0.10)
    assert first["snapshot"]["spread_pct"] == pytest.approx(0.10 / 1.05)
    assert first["snapshot"]["quote_age_ms"] >= 0
    assert first["snapshot"]["snapshot_ts"]
    assert first["snapshot"]["bid_size"] is None
    assert first["snapshot"]["oi_change_pct"] is None


def test_s07_liquidity_diagnostics_returns_empty_payload_when_chain_unavailable(monkeypatch):
    orch = CustomMetricsOrchestrator(config={"auto_start": False})
    monkeypatch.setattr(orch, "_load_options_chain_dataframe", lambda: pd.DataFrame())

    updated = {}
    errors = []
    result = orch._update_liquidity_diagnostics_metrics(updated, errors)

    assert result is False
    assert updated["LIQUIDITY_DIAGNOSTICS"] == {}
    assert len(errors) == 1


def test_s07_liquidity_diagnostics_accepts_list_payload_fallback(monkeypatch):
    orch = CustomMetricsOrchestrator(config={"auto_start": False})
    orch.current_metrics["OGL"] = 585.0

    now = datetime.now()
    chain_rows = [
        {
            "symbol": "SPY",
            "strike": 585.0,
            "expiry": now + timedelta(days=1),
            "option_type": "call",
            "bid": 1.00,
            "ask": 1.12,
            "mid_price": 1.06,
            "spread": 0.12,
            "volume": 100,
            "open_interest": 700,
            "timestamp": now,
        }
    ]

    monkeypatch.setattr(orch, "_load_options_chain_dataframe", lambda: chain_rows)

    updated = {}
    errors = []
    result = orch._update_liquidity_diagnostics_metrics(updated, errors)

    assert result is True
    assert errors == []
    payload = updated["LIQUIDITY_DIAGNOSTICS"]
    assert payload["data"]["candidate_count"] == 1
    assert payload["data"]["source"] == "SpyderB40_TradierClient"


def test_s07_deduped_issue_logging_suppresses_repeated_messages():
    orch = CustomMetricsOrchestrator(config={"auto_start": False})
    orch.logger.warning = MagicMock()

    orch._log_deduped_issue("dup-channel", "repeat-me", level="warning")
    orch._log_deduped_issue("dup-channel", "repeat-me", level="warning")

    assert orch.logger.warning.call_count == 1


def test_s07_update_error_summary_dedupes_same_error_keys():
    orch = CustomMetricsOrchestrator(config={"auto_start": False})
    orch.logger.warning = MagicMock()
    orch.error_occurred = MagicMock()

    errs = [
        "FRED update error: timeout",
        "options analytics update failed: no expirations",
    ]
    orch._emit_update_error_summary(errs, success_count=10)
    orch._emit_update_error_summary(errs, success_count=10)

    assert orch.logger.warning.call_count == 1