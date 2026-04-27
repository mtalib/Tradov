#!/usr/bin/env python3
"""Focused tests for SpyderC11_FuturesBasis.get_lead_lag_snapshot()."""
import importlib.util as _ilu
import math
import os
import sys
import types
from contextlib import contextmanager
from collections import deque
from datetime import datetime, timedelta, date
from unittest.mock import MagicMock


class _AnyAttr(types.ModuleType):
    """Stub module: any attribute access returns MagicMock, pytest_plugins is None."""
    pytest_plugins = None  # prevent pytest UsageError during collection

    def __getattr__(self, name: str):
        return MagicMock()


def _ensure_mod(key: str):
    parts = key.split(".")
    for i in range(1, len(parts) + 1):
        anc = ".".join(parts[:i])
        if anc not in sys.modules:
            sys.modules[anc] = _AnyAttr(anc)
    return sys.modules[key]


@contextmanager
def _scoped_module_stubs(module_names: list[str]):
    """Temporarily inject stubs into sys.modules and restore after use."""
    original: dict[str, types.ModuleType] = {}
    injected: set[str] = set()
    for name in module_names:
        if name in sys.modules:
            original[name] = sys.modules[name]
        else:
            injected.add(name)
        sys.modules[name] = _AnyAttr(name)

    try:
        yield
    finally:
        for name in module_names:
            if name in original:
                sys.modules[name] = original[name]
            else:
                sys.modules.pop(name, None)

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_C11_PATH = os.path.join(_ROOT, "Spyder", "SpyderC_MarketData", "SpyderC11_FuturesBasis.py")
_C11_STUBS = [
    "Spyder", "Spyder.SpyderU_Utilities",
    "Spyder.SpyderU_Utilities.SpyderU01_Logger",
    "Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler",
    "Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils",
    "Spyder.SpyderU_Utilities.SpyderU10_TradingCalendar",
    "Spyder.SpyderC_MarketData",
    "Spyder.SpyderC_MarketData.SpyderC01_DataFeed",
    "Spyder.SpyderC_MarketData.SpyderC02_HistoricalData",
    "Spyder.SpyderA_Core",
    "Spyder.SpyderA_Core.SpyderA05_EventManager",
]

with _scoped_module_stubs(_C11_STUBS):
    # Concrete logger stub
    _u01 = sys.modules["Spyder.SpyderU_Utilities.SpyderU01_Logger"]
    _u01.SpyderLogger = MagicMock()
    _u01.SpyderLogger.get_logger = MagicMock(return_value=MagicMock())

    # get_data_feed_manager returns None (simulated mode)
    sys.modules["Spyder.SpyderC_MarketData.SpyderC01_DataFeed"].get_data_feed_manager = MagicMock(return_value=None)
    sys.modules["Spyder.SpyderC_MarketData.SpyderC02_HistoricalData"].HistoricalDataManager = MagicMock

    # EventManager stub with emit_event no-op
    _event_mod = sys.modules["Spyder.SpyderA_Core.SpyderA05_EventManager"]
    _mock_em = MagicMock()
    _mock_em.emit_event = MagicMock()
    _event_mod.get_event_manager = MagicMock(return_value=_mock_em)

    # EventType / Event stubs (scoped; no global pollution after module load)
    class _FakeEventType:
        DATA_UPDATE = "DATA_UPDATE"

    _event_mod.EventType = _FakeEventType
    _event_mod.Event = MagicMock(return_value=MagicMock())

    _spec = _ilu.spec_from_file_location("_c11_test_module", _C11_PATH)
    _c11_mod = _ilu.module_from_spec(_spec)  # type: ignore[arg-type]
    _spec.loader.exec_module(_c11_mod)  # type: ignore[union-attr]

FuturesBasisAnalyzer = _c11_mod.FuturesBasisAnalyzer
BasisData = _c11_mod.BasisData
BasisDirection = _c11_mod.BasisDirection
ESFuturesData = _c11_mod.ESFuturesData
SPYData = _c11_mod.SPYData


# ---------------------------------------------------------------------------
# Helper — build a FuturesBasisAnalyzer with pre-populated state
# ---------------------------------------------------------------------------
def _make_analyzer(es_price=575.0, spy_price=574.5, basis_bps=5.0):
    """Return analyzer with pre-built current data (bypasses live fetch)."""
    ana = FuturesBasisAnalyzer.__new__(FuturesBasisAnalyzer)
    # Minimal required attributes
    ana.logger = MagicMock()
    ana.error_handler = MagicMock()
    ana.error_handler.handle_error = MagicMock()
    ana.event_manager = _mock_em
    ana.data_feed = None  # simulated

    import numpy as _np
    ana.basis_history = deque(maxlen=500)
    ana.arbitrage_signals = deque(maxlen=1000)
    ana.alert_history = deque(maxlen=500)

    _now = datetime.now()
    _exp = date.today() + timedelta(days=60)

    ana.current_es_data = ESFuturesData(
        timestamp=_now,
        contract_month="M",
        expiration_date=_exp,
        price=es_price,
        bid=es_price - 0.25,
        ask=es_price + 0.25,
        volume=500_000,
        open_interest=2_000_000,
    )
    ana.current_spy_data = SPYData(
        timestamp=_now,
        price=spy_price,
        bid=spy_price - 0.01,
        ask=spy_price + 0.01,
        volume=50_000_000,
    )
    ana.current_basis = BasisData(
        timestamp=_now,
        es_price=es_price,
        spy_price=spy_price,
        raw_basis=es_price - spy_price,
        fair_value_basis=0.3,
        basis_points=basis_bps,
        direction=BasisDirection.POSITIVE,
        days_to_expiry=60,
        interest_rate=0.05,
        dividend_yield=0.015,
        cost_of_carry=0.0001,
    )
    return ana


def _add_basis_history(ana, n=20, start_bps=4.0, step=0.1):
    """Populate basis_history with n entries of increasing basis_points."""
    _now = datetime.now()
    _exp = date.today() + timedelta(days=60)
    for i in range(n):
        bd = BasisData(
            timestamp=_now - timedelta(seconds=n - i),
            es_price=575.0,
            spy_price=574.5,
            raw_basis=0.5,
            fair_value_basis=0.3,
            basis_points=start_bps + i * step,
            direction=BasisDirection.POSITIVE,
            days_to_expiry=60,
            interest_rate=0.05,
            dividend_yield=0.015,
            cost_of_carry=0.0001,
        )
        ana.basis_history.append(bd)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_snapshot_returns_all_expected_keys():
    ana = _make_analyzer()
    snap = ana.get_lead_lag_snapshot()
    for key in ("es_price", "spy_price", "basis_bps", "lead_lag_ms",
                "es_impulse_score", "confirm_direction", "confirm_confidence", "snapshot_ts"):
        assert key in snap, f"Key {key!r} missing"


def test_snapshot_es_spy_prices_match_state():
    ana = _make_analyzer(es_price=580.0, spy_price=579.5)
    snap = ana.get_lead_lag_snapshot()
    assert snap["es_price"] == 580.0
    assert snap["spy_price"] == 579.5


def test_snapshot_basis_bps_matches_state():
    ana = _make_analyzer(basis_bps=12.0)
    snap = ana.get_lead_lag_snapshot()
    assert snap["basis_bps"] == 12.0


def test_lead_lag_ms_is_positive_for_premium():
    """Positive basis → positive lead_lag_ms (ES leading higher)."""
    ana = _make_analyzer(basis_bps=10.0)
    snap = ana.get_lead_lag_snapshot()
    assert snap["lead_lag_ms"] > 0.0


def test_lead_lag_ms_clipped_to_250():
    """Extreme basis capped at ±250 ms."""
    ana = _make_analyzer(basis_bps=600.0)
    snap = ana.get_lead_lag_snapshot()
    assert snap["lead_lag_ms"] == 250.0


def test_es_impulse_score_computed_from_history():
    """Impulse score should be in [-1, 1] when history is available."""
    ana = _make_analyzer()
    _add_basis_history(ana, n=20, start_bps=3.0, step=0.2)
    # Ensure current_basis matches last history entry roughly
    snap = ana.get_lead_lag_snapshot()
    assert not math.isnan(snap["es_impulse_score"])
    assert -1.0 <= snap["es_impulse_score"] <= 1.0


def test_es_impulse_score_nan_without_history():
    """Without ≥5 history entries, impulse falls back to basis magnitude."""
    ana = _make_analyzer(basis_bps=3.0)
    # Only 2 entries → can't compute delta over 5 samples
    _add_basis_history(ana, n=2)
    snap = ana.get_lead_lag_snapshot()
    # With < 5 history, impulse score is NaN; confirm_direction uses static basis fallback
    assert math.isnan(snap["es_impulse_score"])
    # Static fallback: basis_bps=3 > 2.0 → "up"
    assert snap["confirm_direction"] == "up"


def test_confirm_direction_up_on_expanding_basis():
    ana = _make_analyzer()
    _add_basis_history(ana, n=20, start_bps=0.0, step=0.5)  # strongly expanding
    snap = ana.get_lead_lag_snapshot()
    assert snap["confirm_direction"] == "up"


def test_confirm_direction_neutral_on_flat_basis():
    ana = _make_analyzer()
    _add_basis_history(ana, n=20, start_bps=5.0, step=0.0)  # perfectly flat
    snap = ana.get_lead_lag_snapshot()
    assert snap["confirm_direction"] == "neutral"


def test_confirm_confidence_in_range():
    ana = _make_analyzer()
    _add_basis_history(ana, n=20, start_bps=3.0, step=0.1)
    snap = ana.get_lead_lag_snapshot()
    assert not math.isnan(snap["confirm_confidence"])
    assert 0.0 <= snap["confirm_confidence"] <= 1.0


def test_snapshot_ts_is_valid_iso():
    ana = _make_analyzer()
    snap = ana.get_lead_lag_snapshot()
    # Must parse without exception
    datetime.fromisoformat(snap["snapshot_ts"])


def test_snapshot_defaults_when_no_data_and_update_fails():
    """When no data and update_market_data raises, all values are NaN / 'unknown'."""
    ana = _make_analyzer()
    ana.current_es_data = None
    ana.current_spy_data = None
    ana.current_basis = None

    def _failing_update():
        raise RuntimeError("no data")

    ana.update_market_data = _failing_update

    snap = ana.get_lead_lag_snapshot()
    assert math.isnan(snap["es_price"])
    assert math.isnan(snap["basis_bps"])
    assert snap["confirm_direction"] == "unknown"
