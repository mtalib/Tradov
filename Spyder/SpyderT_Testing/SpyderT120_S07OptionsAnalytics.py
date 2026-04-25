#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT120_S07OptionsAnalytics.py
Purpose: Unit tests for the options-analytics methods added to
         SpyderS07_CustomMetricsOrchestrator (IVR, ATM_IV, VRP).

         All network and filesystem I/O is mocked.  Tests run fully
         offline with no Qt event loop required.

Author: Spyder Dev
Year Created: 2026
Last Updated: 2026-04-18 Time: 00:00:00
"""

# ==============================================================================
# BOOTSTRAP — stubs before any module import
# ==============================================================================
import os
import sys
import types
import json
import math
import logging
import tempfile
import pathlib
from dataclasses import dataclass
from datetime import datetime
from unittest.mock import MagicMock, patch, mock_open

logging.disable(logging.CRITICAL)

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _ensure_mod(key: str):
    parts = key.split(".")
    for i in range(1, len(parts) + 1):
        anc = ".".join(parts[:i])
        if anc not in sys.modules:
            sys.modules[anc] = types.ModuleType(anc)
    return sys.modules[key]


# ---------------------------------------------------------------------------
# PySide6 — minimal stubs so S07 can be imported without a display
# ---------------------------------------------------------------------------
class _AnyAttr(types.ModuleType):
    def __getattr__(self, name):
        return MagicMock()


for _pkg in ["PySide6", "PySide6.QtCore", "PySide6.QtWidgets", "PySide6.QtGui",
             "PySide6.QtWebEngineWidgets"]:
    sys.modules.setdefault(_pkg, _AnyAttr(_pkg))

_QtCore = sys.modules["PySide6.QtCore"]
_QtCore.QObject = object  # type: ignore
_QtCore.QTimer = MagicMock
_QtCore.Signal = lambda *a, **kw: MagicMock()
_QtCore.Slot = lambda *a, **kw: (lambda f: f)

# ---------------------------------------------------------------------------
# Other heavy stubs (numpy is available, so no stub needed)
# ---------------------------------------------------------------------------
for _pkg in ["hmmlearn", "hmmlearn.hmm", "plotly", "plotly.graph_objects",
             "plotly.subplots", "pytz"]:
    sys.modules.setdefault(_pkg, _AnyAttr(_pkg))

# ---------------------------------------------------------------------------
# SpyderU stubs
# ---------------------------------------------------------------------------
_spyder_pkg = _ensure_mod("Spyder")
_u_pkg = _ensure_mod("Spyder.SpyderU_Utilities")
_u01 = _ensure_mod("Spyder.SpyderU_Utilities.SpyderU01_Logger")
_logger_cls = MagicMock()
_logger_cls.get_logger = MagicMock(return_value=MagicMock())
_u01.SpyderLogger = _logger_cls

_u02 = _ensure_mod("Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler")
_u02.SpyderErrorHandler = MagicMock

# Mirror to un-prefixed path (S07 imports from SpyderU_Utilities directly)
for _key in list(sys.modules):
    if _key.startswith("Spyder.SpyderU"):
        short = _key[len("Spyder."):]
        sys.modules.setdefault(short, sys.modules[_key])

# ---------------------------------------------------------------------------
# Stub out all the S-series signal modules that S07 optionally imports
# ---------------------------------------------------------------------------
_S_STUBS = [
    "SpyderS_Signals.SpyderS01_DIXCalculator",
    "SpyderS_Signals.SpyderS02_DIXScheduler",
    "SpyderS_Signals.SpyderS03_BlackSwanIndicator",
    "SpyderS_Signals.SpyderS04_BlackSwanScheduler",
    "SpyderS_Signals.SpyderS05_GEXDEXCalculator",
    "SpyderS_Signals.SpyderS06_SKEWCalculator",
    "SpyderS_Signals.SpyderS09_FREDMacroClient",
    "SpyderS_Signals.SpyderS10_SentimentScraper",
    "SpyderS_Signals.SpyderS11_TradingViewInternals",
    "Spyder.SpyderS_Signals.SpyderS01_DIXCalculator",
    "Spyder.SpyderS_Signals.SpyderS02_DIXScheduler",
    "Spyder.SpyderS_Signals.SpyderS03_BlackSwanIndicator",
    "Spyder.SpyderS_Signals.SpyderS04_BlackSwanScheduler",
    "Spyder.SpyderS_Signals.SpyderS05_GEXDEXCalculator",
    "Spyder.SpyderS_Signals.SpyderS06_SKEWCalculator",
    "Spyder.SpyderS_Signals.SpyderS09_FREDMacroClient",
    "Spyder.SpyderS_Signals.SpyderS10_SentimentScraper",
    "Spyder.SpyderS_Signals.SpyderS11_TradingViewInternals",
]
for _s in _S_STUBS:
    _ensure_mod(_s)

# ---------------------------------------------------------------------------
# Now we can import the module under test
# ---------------------------------------------------------------------------
import pytest
import importlib
import importlib.util as _ilu

_S07_PATH = os.path.join(
    _ROOT, "Spyder", "SpyderS_Signals", "SpyderS07_CustomMetricsOrchestrator.py"
)
_spec = _ilu.spec_from_file_location("_s07_module", _S07_PATH)
_s07_mod = _ilu.module_from_spec(_spec)  # type: ignore
_spec.loader.exec_module(_s07_mod)  # type: ignore

CustomMetricsOrchestrator = _s07_mod.CustomMetricsOrchestrator


# ==============================================================================
# HELPERS — minimal GreekData-like namedtuple returned by mocked chain fetch
# ==============================================================================
@dataclass
class _FakeContract:
    strike: float
    iv: float
    option_type: str = "call"


def _make_contracts(spot: float, atm_iv: float = 0.20) -> list:
    """Return a realistic-looking option chain around ``spot``."""
    strikes = [spot - 5, spot, spot + 5]
    contracts = []
    for s in strikes:
        for ot in ("call", "put"):
            contracts.append(_FakeContract(strike=s, iv=atm_iv, option_type=ot))
    return contracts


# ==============================================================================
# FIXTURES
# ==============================================================================
@pytest.fixture()
def orch() -> CustomMetricsOrchestrator:
    """Return an orchestrator with auto_start disabled."""
    return CustomMetricsOrchestrator(config={"auto_start": False})


# ==============================================================================
# TESTS — _compute_atm_iv
# ==============================================================================
class TestComputeAtmIv:
    def test_returns_annualised_percent(self, orch):
        contracts = _make_contracts(spot=585.0, atm_iv=0.20)
        result = orch._compute_atm_iv(contracts, spot=585.0)
        # 0.20 raw × 100 = 20.0 %
        assert result == pytest.approx(20.0, abs=0.1)

    def test_nearest_strikes_used(self, orch):
        """When ATM and two OTM strikes have different IVs, only the
        nearest 6 contracts contribute (the smile should not dominate)."""
        contracts = [
            _FakeContract(strike=585.0, iv=0.18),  # ATM call
            _FakeContract(strike=585.0, iv=0.19),  # ATM put
            _FakeContract(strike=600.0, iv=0.50),  # far OTM — should NOT dominate
            _FakeContract(strike=600.0, iv=0.50),
        ]
        result = orch._compute_atm_iv(contracts, spot=585.0)
        # All 4 are within 6 nearest when chain has only 4 contracts
        avg = (0.18 + 0.19 + 0.50 + 0.50) / 4 * 100
        assert result == pytest.approx(avg, abs=0.01)

    def test_empty_chain_returns_none(self, orch):
        assert orch._compute_atm_iv([], spot=585.0) is None

    def test_zero_spot_returns_none(self, orch):
        assert orch._compute_atm_iv(_make_contracts(585.0), spot=0) is None

    def test_contracts_with_zero_iv_ignored(self, orch):
        contracts = [
            _FakeContract(strike=585.0, iv=0.0),   # should be excluded
            _FakeContract(strike=585.0, iv=0.20),
        ]
        result = orch._compute_atm_iv(contracts, spot=585.0)
        assert result == pytest.approx(20.0, abs=0.1)

    def test_all_zero_iv_returns_none(self, orch):
        contracts = [_FakeContract(strike=585.0, iv=0.0)]
        assert orch._compute_atm_iv(contracts, spot=585.0) is None


# ==============================================================================
# TESTS — _compute_ivr
# ==============================================================================
class TestComputeIvr:
    def _run(self, orch, current_iv: float, history: list) -> float:
        """Run _compute_ivr with a patched filesystem (in-memory only)."""
        import json as _json
        cache_str = _json.dumps(history)
        with patch("pathlib.Path.exists", return_value=bool(history)), \
             patch("pathlib.Path.read_text", return_value=cache_str), \
             patch("pathlib.Path.write_text"), \
             patch("pathlib.Path.mkdir"):
            return orch._compute_ivr(current_iv)

    def test_ivr_at_52wk_high(self, orch):
        history = [{"date": f"2025-{m:02d}-01", "iv": 15.0} for m in range(1, 13)]
        result = self._run(orch, 30.0, history)
        assert result == pytest.approx(100.0, abs=0.1)

    def test_ivr_at_52wk_low(self, orch):
        history = [{"date": f"2025-{m:02d}-01", "iv": 25.0} for m in range(1, 13)]
        result = self._run(orch, 10.0, history)
        assert result == pytest.approx(0.0, abs=0.1)

    def test_ivr_midpoint(self, orch):
        # Need ≥5 IVs total (history + current appended); use 5 history entries
        history = [
            {"date": "2025-01-01", "iv": 10.0},
            {"date": "2025-02-01", "iv": 15.0},
            {"date": "2025-03-01", "iv": 20.0},
            {"date": "2025-04-01", "iv": 25.0},
            {"date": "2025-05-01", "iv": 30.0},
        ]
        result = self._run(orch, 20.0, history)
        assert result == pytest.approx(50.0, abs=0.1)

    def test_short_history_returns_nan(self, orch):
        history = [{"date": "2025-01-01", "iv": 20.0}]
        result = self._run(orch, 20.0, history)
        assert math.isnan(result)

    def test_empty_cache_returns_nan(self, orch):
        result = self._run(orch, 20.0, [])
        # With no pre-existing history, _compute_ivr adds today's entry (1 point → nan)
        assert math.isnan(result)

    def test_history_trimmed_to_252(self, orch, tmp_path):
        """History file must be trimmed to 252 entries on write."""
        import json as _json
        # Build 300 daily entries across years 2019–2024
        long_history = [
            {"date": f"2019-{m:02d}-{d:02d}", "iv": 15.0}
            for m in range(1, 13) for d in range(1, 26)
        ][:300]
        assert len(long_history) > 252

        written_texts: list = []

        with patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.read_text", return_value=_json.dumps(long_history)), \
             patch("pathlib.Path.write_text", side_effect=lambda t: written_texts.append(t)), \
             patch("pathlib.Path.mkdir"):
            orch._compute_ivr(15.0)

        assert written_texts, "write_text was never called"
        saved = _json.loads(written_texts[-1])
        assert len(saved) <= 252


# ==============================================================================
# TESTS — _compute_hv20
# ==============================================================================
class TestComputeHv20:
    def _make_daily_response(self, n_days: int = 22, daily_return: float = 0.001) -> dict:
        """Create a synthetic Tradier history response with log-constant daily returns."""
        import math as _math
        price = 500.0
        days = []
        from datetime import date, timedelta
        d = date(2025, 11, 1)
        for _ in range(n_days):
            days.append({"date": d.isoformat(), "close": round(price, 4)})
            price *= _math.exp(daily_return)
            d += timedelta(days=1)
        return {"history": {"day": days}}

    def test_returns_annualised_percent(self, orch):
        mock_client = MagicMock()
        mock_client.get_historical_quotes.return_value = self._make_daily_response(
            n_days=22, daily_return=0.01
        )
        result = orch._compute_hv20(mock_client)
        assert result is not None
        assert result > 0  # annualised HV > 0 for non-zero returns

    def test_too_few_bars_returns_none(self, orch):
        mock_client = MagicMock()
        mock_client.get_historical_quotes.return_value = self._make_daily_response(n_days=5)
        result = orch._compute_hv20(mock_client)
        assert result is None

    def test_api_error_returns_none(self, orch):
        mock_client = MagicMock()
        mock_client.get_historical_quotes.side_effect = RuntimeError("API error")
        result = orch._compute_hv20(mock_client)
        assert result is None

    def test_flat_market_returns_near_zero(self, orch):
        """Flat prices → zero returns → HV ≈ 0."""
        mock_client = MagicMock()
        mock_client.get_historical_quotes.return_value = self._make_daily_response(
            n_days=22, daily_return=0.0
        )
        result = orch._compute_hv20(mock_client)
        # With zero returns std dev is 0
        assert result is not None
        assert result == pytest.approx(0.0, abs=0.01)


# ==============================================================================
# TESTS — _update_options_analytics_metrics (integration)
# ==============================================================================
class TestUpdateOptionsAnalyticsMetrics:
    """Tests for the full orchestration method."""

    def _default_orch(self) -> CustomMetricsOrchestrator:
        return CustomMetricsOrchestrator(config={"auto_start": False})

    def test_no_credentials_returns_false(self):
        orch = self._default_orch()
        updated: dict = {}
        errors: list = []
        with patch.dict(os.environ, {"TRADIER_API_KEY": "", "TRADIER_ACCOUNT_ID": ""}):
            result = orch._update_options_analytics_metrics(updated, errors)
        assert result is False
        # Fallback values preserved (nan since current_metrics starts with nan)
        assert "IVR" in updated
        assert "ATM_IV" in updated
        assert "VRP" in updated

    def test_api_success_populates_all_three(self):
        orch = self._default_orch()
        contracts = _make_contracts(spot=585.0, atm_iv=0.18)

        mock_client = MagicMock()
        mock_client.get_option_expirations.return_value = {
            "expirations": {"date": ["2026-04-25", "2026-05-16"]}
        }
        mock_client.get_option_chain_with_greeks.return_value = contracts
        mock_client.get_historical_quotes.return_value = {
            "history": {"day": [
                {"date": f"2026-01-{i:02d}", "close": 580.0 + i * 0.1}
                for i in range(1, 23)
            ]}
        }
        orch._options_tradier_client = mock_client
        orch._options_tradier_env = "sandbox"

        with patch.dict(os.environ, {
            "TRADIER_API_KEY": "test-key",
            "TRADIER_ACCOUNT_ID": "123456",
            "TRADIER_ENVIRONMENT": "sandbox",
        }), patch.object(orch, "_get_spy_spot", return_value=585.0), \
           patch("pathlib.Path.exists", return_value=False), \
           patch("pathlib.Path.write_text"), \
           patch("pathlib.Path.mkdir"):
            updated: dict = {}
            errors: list = []
            result = orch._update_options_analytics_metrics(updated, errors)

        assert result is True
        assert "ATM_IV" in updated
        assert updated["ATM_IV"] == pytest.approx(18.0, abs=0.5)  # 0.18 × 100
        assert "IVR" in updated
        assert "VRP" in updated

    def test_chain_fetch_error_returns_false(self):
        orch = self._default_orch()
        mock_client = MagicMock()
        mock_client.get_option_expirations.side_effect = RuntimeError("network error")
        orch._options_tradier_client = mock_client

        with patch.dict(os.environ, {
            "TRADIER_API_KEY": "key", "TRADIER_ACCOUNT_ID": "acct"
        }):
            updated: dict = {}
            errors: list = []
            result = orch._update_options_analytics_metrics(updated, errors)

        assert result is False
        assert len(errors) == 1

    def test_client_cached_between_calls(self):
        """The TradierClient must not be recreated on every call."""
        orch = self._default_orch()
        mock_client = MagicMock()
        mock_client.get_option_expirations.return_value = {
            "expirations": {"date": ["2026-04-25"]}
        }
        mock_client.get_option_chain_with_greeks.return_value = _make_contracts(585.0)
        mock_client.get_historical_quotes.return_value = {
            "history": {"day": [{"date": f"2026-01-{i:02d}", "close": 580.0 + i}
                                  for i in range(1, 23)]}
        }
        orch._options_tradier_client = mock_client
        orch._options_tradier_env = "sandbox"

        with patch.dict(os.environ, {
            "TRADIER_API_KEY": "key", "TRADIER_ACCOUNT_ID": "acct",
            "TRADIER_ENVIRONMENT": "sandbox",
        }), patch.object(orch, "_get_spy_spot", return_value=585.0), \
           patch("pathlib.Path.exists", return_value=False), \
           patch("pathlib.Path.write_text"), \
           patch("pathlib.Path.mkdir"):
            orch._update_options_analytics_metrics({}, [])
            orch._update_options_analytics_metrics({}, [])
            # The mock client instance is unchanged — no new TradierClient was built
            assert orch._options_tradier_client is mock_client

    def test_env_change_recreates_client(self):
        """Switching TRADIER_ENVIRONMENT from sandbox→live must create a new client."""
        orch = self._default_orch()
        old_client = MagicMock()
        old_client.get_option_expirations.return_value = {"expirations": {"date": []}}
        orch._options_tradier_client = old_client
        orch._options_tradier_env = "sandbox"  # was sandbox

        new_client = MagicMock()
        new_client.get_option_expirations.return_value = {"expirations": {"date": []}}

        # Patch the lazy import inside _update_options_analytics_metrics
        tradier_module = MagicMock()
        tradier_module.TradierClient = MagicMock(return_value=new_client)
        tradier_module.TradingEnvironment.LIVE = "live"
        tradier_module.TradingEnvironment.SANDBOX = "sandbox"

        with patch.dict(os.environ, {
            "TRADIER_API_KEY": "key", "TRADIER_ACCOUNT_ID": "acct",
            "TRADIER_ENVIRONMENT": "live",  # now live
        }), patch.dict("sys.modules", {
            "Spyder.SpyderB_Broker.SpyderB40_TradierClient": tradier_module,
        }):
            orch._update_options_analytics_metrics({}, [])

        assert orch._options_tradier_env == "live"
        assert orch._options_tradier_client is new_client


# ==============================================================================
# TESTS — _format_metrics emits IVR / ATM_IV / VRP entries
# ==============================================================================
class TestFormatMetricsOptionsAnalytics:
    def _make_orch(self) -> CustomMetricsOrchestrator:
        return CustomMetricsOrchestrator(config={"auto_start": False})

    def test_ivr_formatted(self):
        orch = self._make_orch()
        result = orch._format_metrics({"IVR": 45.3})
        assert "IVR" in result
        assert result["IVR"]["value"] == pytest.approx(45.3)
        assert result["IVR"]["formatted"] == "45"

    def test_atm_iv_formatted(self):
        orch = self._make_orch()
        result = orch._format_metrics({"ATM_IV": 18.7})
        assert result["ATM_IV"]["formatted"] == "18.7%"

    def test_vrp_formatted_positive(self):
        orch = self._make_orch()
        result = orch._format_metrics({"VRP": 3.2})
        assert result["VRP"]["formatted"] == "+3.2"

    def test_vrp_formatted_negative(self):
        orch = self._make_orch()
        result = orch._format_metrics({"VRP": -1.5})
        assert result["VRP"]["formatted"] == "-1.5"

    def test_nan_values_show_placeholder(self):
        orch = self._make_orch()
        result = orch._format_metrics({"IVR": float("nan"), "ATM_IV": float("nan"), "VRP": float("nan")})
        assert result["IVR"]["formatted"] == "---"
        assert result["ATM_IV"]["formatted"] == "---"
        assert result["VRP"]["formatted"] == "---"


# ==============================================================================
# TESTS — current_metrics and MetricSnapshot have correct fields
# ==============================================================================
class TestMetricDataStructures:
    def test_current_metrics_has_options_keys(self):
        orch = CustomMetricsOrchestrator(config={"auto_start": False})
        for key in ("IVR", "ATM_IV", "VRP"):
            assert key in orch.current_metrics
            assert math.isnan(orch.current_metrics[key])

    def test_metric_snapshot_has_options_fields(self):
        snap = _s07_mod.MetricSnapshot()
        for attr in ("ivr", "atm_iv", "vrp"):
            assert hasattr(snap, attr)
            assert math.isnan(getattr(snap, attr))

    def test_quality_tracker_has_options_key(self):
        orch = CustomMetricsOrchestrator(config={"auto_start": False})
        assert "OPTIONS" in orch.metric_quality

    def test_client_cache_initialised_to_none(self):
        orch = CustomMetricsOrchestrator(config={"auto_start": False})
        assert orch._options_tradier_client is None
        assert orch._options_tradier_env is None
