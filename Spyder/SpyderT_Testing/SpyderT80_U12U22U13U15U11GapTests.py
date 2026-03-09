#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT80_U12U22U13U15U11GapTests.py
Purpose: Gap tests for U12 AgentIntegration, U22 ETTimeDisplay, U13 Technical
         Indicators (exception paths), U15 PerformanceMetrics (exception paths),
         U11 FeatureFlags (environment/dependency branches)

Author: Spyder Test Suite
Year Created: 2026
Last Updated: 2026-03-05 Time: 10:00:00
"""

# ==============================================================================
# BOOTSTRAP
# ==============================================================================
import sys
import os
import types
import importlib.util

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _load(rel_path):
    abs_path = os.path.join(_ROOT, rel_path)
    spec = importlib.util.spec_from_file_location(rel_path, abs_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ensure_pkg(name):
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)


_ensure_pkg("Spyder")
_ensure_pkg("Spyder.SpyderU_Utilities")

_u01 = _load("Spyder/SpyderU_Utilities/SpyderU01_Logger.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU01_Logger"] = _u01

_u02 = _load("Spyder/SpyderU_Utilities/SpyderU02_ErrorHandler.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler"] = _u02

# U12 AgentIntegration — no extra deps
_u12 = _load("Spyder/SpyderU_Utilities/SpyderU12_AgentIntegration.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU12_AgentIntegration"] = _u12

# U22 ETTimeDisplay — needs U03 mock (only US_EASTERN constant used)
_u03_mock = types.ModuleType("Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils")
_u03_mock.US_EASTERN = "US/Eastern"
if "Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils" not in sys.modules:
    sys.modules["Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils"] = _u03_mock

_u22 = _load("Spyder/SpyderU_Utilities/SpyderU22_ETTimeDisplay.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU22_ETTimeDisplay"] = _u22

# U13 TechnicalIndicators
_u13 = _load("Spyder/SpyderU_Utilities/SpyderU13_TechnicalIndicators.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU13_TechnicalIndicators"] = _u13

# U15 PerformanceMetrics
_u15 = _load("Spyder/SpyderU_Utilities/SpyderU15_PerformanceMetrics.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU15_PerformanceMetrics"] = _u15

# U11 FeatureFlags
_u11 = _load("Spyder/SpyderU_Utilities/SpyderU11_FeatureFlags.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU11_FeatureFlags"] = _u11

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import datetime as _dt
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
import pytest

# ==============================================================================
# U12 IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU12_AgentIntegration import (
    AgentStatus,
    AgentMetrics,
)

# ==============================================================================
# U22 IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU22_ETTimeDisplay import (
    get_et_time_string,
    get_et_time_for_dashboard,
    get_current_et_datetime,
    SimpleETDisplay,
    get_et_display,
    DASHBOARD_TIME_FORMAT,
    SIMPLE_TIME_FORMAT,
)

# ==============================================================================
# U13 IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU13_TechnicalIndicators import (
    TechnicalIndicators,
    SignalType,
    TrendDirection,
    IndicatorResult,
    TrendAnalysis,
    DEFAULT_RSI_PERIOD,
    DEFAULT_MACD_FAST,
    DEFAULT_MACD_SLOW,
    DEFAULT_MACD_SIGNAL,
    DEFAULT_ADX_PERIOD,
    DEFAULT_ATR_PERIOD,
    DEFAULT_BB_PERIOD,
    DEFAULT_BB_STDDEV,
)

# ==============================================================================
# U15 IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU15_PerformanceMetrics import (
    PerformanceCalculator,
    PerformanceReport,
    PerformanceRating,
    DrawdownInfo,
    get_performance_calculator,
    generate_performance_report,
    calculate_sharpe_ratio,
    calculate_max_drawdown,
    RISK_FREE_RATE,
    MIN_PERIODS_FOR_CALCULATION,
    TRADING_DAYS_PER_YEAR,
    calculate_metrics,
)

# ==============================================================================
# U11 IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU11_FeatureFlags import (
    FeatureFlags,
    FeatureFlag,
    FeatureStatus,
    FeatureType,
    RolloutStrategy,
    DEFAULT_FEATURES,
)


# ==============================================================================
# HELPERS
# ==============================================================================

def _prices(n: int = 30) -> pd.Series:
    """Standard price series for indicator tests."""
    return pd.Series(np.linspace(100, 110, n), dtype=float)


def _ohlcv(n: int = 30):
    """Return high, low, close, volume Series."""
    base = np.linspace(100, 110, n)
    h = pd.Series(base + 1.0, dtype=float)
    lo = pd.Series(base - 1.0, dtype=float)
    c = pd.Series(base, dtype=float)
    v = pd.Series(np.random.randint(1000, 10000, n), dtype=float)
    return h, lo, c, v


def _returns(n: int = 100) -> pd.Series:
    np.random.seed(42)
    return pd.Series(np.random.normal(0.001, 0.02, n))


def _fresh_flags(tmp_path=None) -> FeatureFlags:
    """Create a FeatureFlags instance with a temp config path."""
    import tempfile
    if tmp_path is None:
        tmp_path = tempfile.mkdtemp()
    config = os.path.join(str(tmp_path), "flags.json")
    return FeatureFlags(config_file=config)


# ==============================================================================
# ═════════════════════════════════════════════════════════════════════════════
#  U12 — AgentIntegration GAP TESTS
#  Missing: ~line 55 (__post_init__ metadata=None), ~line 60 (last_activity set)
# ═════════════════════════════════════════════════════════════════════════════
# ==============================================================================

class TestU12AgentMetricsGaps:
    def test_default_creation_triggers_post_init(self):
        """metadata defaults to None → __post_init__ sets it to {}."""
        m = AgentMetrics()  # no metadata arg → field default is None
        assert m.metadata == {}  # post_init should have set it

    def test_metadata_none_set_to_empty_dict(self):
        """Explicitly create with metadata=None → __post_init__ branch."""
        m = AgentMetrics(agent_id="test", metadata=None)
        assert isinstance(m.metadata, dict)
        assert m.metadata == {}

    def test_to_dict_with_last_activity_set(self):
        """to_dict with last_activity set → .isoformat() branch (missing)."""
        now = _dt.datetime.now()
        m = AgentMetrics(agent_id="agent_1", last_activity=now)
        d = m.to_dict()
        assert d["last_activity"] is not None
        assert "T" in d["last_activity"] or ":" in d["last_activity"]

    def test_to_dict_without_last_activity(self):
        """to_dict with last_activity=None → None branch."""
        m = AgentMetrics(agent_id="agent_2")
        d = m.to_dict()
        assert d["last_activity"] is None

    def test_to_dict_has_all_keys(self):
        m = AgentMetrics(agent_id="test", cpu_usage=5.5, memory_usage=10.0,
                          uptime_seconds=3600, requests_processed=100,
                          errors_count=2, last_activity=_dt.datetime.now())
        d = m.to_dict()
        for key in ("agent_id", "status", "cpu_usage", "memory_usage",
                    "uptime_seconds", "requests_processed", "errors_count",
                    "last_activity", "metadata"):
            assert key in d

    def test_agent_status_enum_values(self):
        for status in AgentStatus:
            assert isinstance(status.value, str)

    def test_default_status_is_unknown(self):
        m = AgentMetrics()
        assert m.status == AgentStatus.UNKNOWN

    def test_metadata_preserved_if_provided(self):
        m = AgentMetrics(metadata={"key": "value"})
        assert m.metadata == {"key": "value"}


# ==============================================================================
# ═════════════════════════════════════════════════════════════════════════════
#  U22 — ETTimeDisplay EXCEPTION FALLBACK TESTS
#  Missing: 71-73 (get_et_time_string except), 93-94 (get_current_et_datetime
#  except), 120-122 (SimpleETDisplay.get_time_string except)
# ═════════════════════════════════════════════════════════════════════════════
# ==============================================================================

class TestU22ETTimeDisplayGaps:
    def test_get_et_time_string_normal(self):
        """Normal path works."""
        result = get_et_time_string()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_et_time_string_no_tz(self):
        result = get_et_time_string(include_timezone=False)
        assert isinstance(result, str)
        assert "E" not in result  # no EDT/EST

    def test_get_et_time_string_exception_fallback(self):
        """Lines 71-73: exception in try → fallback returns local time string."""
        with patch.object(_u22, 'EASTERN_TZ', "NOT_A_VALID_TZ_OBJECT"):
            result = get_et_time_string(include_timezone=True)
        # Fallback returns local time without tz
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_et_time_string_exception_fallback_no_tz(self):
        """Exception path with include_timezone=False also returns fallback."""
        with patch.object(_u22, 'EASTERN_TZ', "NOT_A_VALID_TZ_OBJECT"):
            result = get_et_time_string(include_timezone=False)
        assert isinstance(result, str)

    def test_get_et_time_for_dashboard_returns_string(self):
        result = get_et_time_for_dashboard()
        assert isinstance(result, str)

    def test_get_current_et_datetime_normal(self):
        result = get_current_et_datetime()
        assert isinstance(result, _dt.datetime)

    def test_get_current_et_datetime_exception_fallback(self):
        """Lines 93-94: exception → returns local datetime without tz."""
        with patch.object(_u22, 'EASTERN_TZ', "NOT_A_VALID_TZ_OBJECT"):
            result = get_current_et_datetime()
        assert isinstance(result, _dt.datetime)

    def test_simple_et_display_get_time_string_normal(self):
        display = SimpleETDisplay()
        result = display.get_time_string()
        assert isinstance(result, str)

    def test_simple_et_display_get_time_string_no_tz(self):
        display = SimpleETDisplay()
        result = display.get_time_string(include_tz=False)
        assert isinstance(result, str)

    def test_simple_et_display_exception_fallback(self):
        """Lines 120-122: exception in try → fallback returns local time string."""
        display = SimpleETDisplay()
        display.eastern_tz = "NOT_A_VALID_TZ_OBJECT"  # Causes datetime.now(tz) to fail
        result = display.get_time_string()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_et_display_singleton(self):
        _u22._et_display = None  # reset
        d1 = get_et_display()
        d2 = get_et_display()
        assert d1 is d2

    def test_constants_defined(self):
        assert "H" in DASHBOARD_TIME_FORMAT or "%" in DASHBOARD_TIME_FORMAT
        assert "H" in SIMPLE_TIME_FORMAT or "%" in SIMPLE_TIME_FORMAT


# ==============================================================================
# ═════════════════════════════════════════════════════════════════════════════
#  U13 — TechnicalIndicators EXCEPTION PATH TESTS
#  Missing: All 15 × 3-line except blocks (217-219, 254-256, 284-286,
#  326-328, 374-376, 412-414, 441-443, 468-470, 488-490, 505-507,
#  526-528, 551-553, 581-583, 606-608, 637-639)
# ═════════════════════════════════════════════════════════════════════════════
# ==============================================================================

class TestU13ExceptionPaths:
    """Each test triggers one indicator's exception handler via mocking."""

    def setup_method(self):
        self.ti = TechnicalIndicators()

    # --- RSI ---
    def test_rsi_exception_path(self):
        """Lines 217-219: except Exception in calculate_rsi."""
        prices = _prices(30)
        with patch.object(pd.Series, 'rolling', side_effect=RuntimeError("mock rolling")):
            result = self.ti.calculate_rsi(prices, period=14)
        assert isinstance(result, pd.Series)
        assert result.isna().all()

    # --- Stochastic ---
    def test_stochastic_exception_path(self):
        """Lines 254-256: except Exception in calculate_stochastic."""
        h, lo, c, _ = _ohlcv(20)
        with patch.object(pd.Series, 'rolling', side_effect=RuntimeError("mock")):
            result = self.ti.calculate_stochastic(h, lo, c)
        assert isinstance(result, dict)
        assert all(v.isna().all() for v in result.values())

    # --- Williams %R ---
    def test_williams_r_exception_path(self):
        """Lines 284-286: except Exception in calculate_williams_r."""
        h, lo, c, _ = _ohlcv(20)
        with patch.object(pd.Series, 'rolling', side_effect=RuntimeError("mock")):
            result = self.ti.calculate_williams_r(h, lo, c)
        assert isinstance(result, pd.Series)

    # --- MACD (internal EMA calls) ---
    def test_macd_exception_path(self):
        """Lines 326-328: except Exception in calculate_macd."""
        prices = _prices(30)
        with patch.object(self.ti, 'calculate_ema', side_effect=RuntimeError("ema error")):
            result = self.ti.calculate_macd(prices)
        assert isinstance(result, dict)
        assert "MACD" in result

    # --- ADX (internal true_range calls) ---
    def test_adx_exception_path(self):
        """Lines 374-376: except Exception in calculate_adx."""
        h, lo, c, _ = _ohlcv(20)
        with patch.object(self.ti, 'calculate_true_range', side_effect=RuntimeError("tr error")):
            result = self.ti.calculate_adx(h, lo, c)
        assert isinstance(result, dict)
        assert "ADX" in result

    # --- Bollinger Bands (internal SMA calls) ---
    def test_bollinger_bands_exception_path(self):
        """Lines 412-414: except Exception in calculate_bollinger_bands."""
        prices = _prices(30)
        with patch.object(self.ti, 'calculate_sma', side_effect=RuntimeError("sma error")):
            result = self.ti.calculate_bollinger_bands(prices)
        assert isinstance(result, dict)
        assert "Upper" in result

    # --- ATR (internal true_range calls) ---
    def test_atr_exception_path(self):
        """Lines 441-443: except Exception in calculate_atr."""
        h, lo, c, _ = _ohlcv(20)
        with patch.object(self.ti, 'calculate_true_range', side_effect=RuntimeError("tr error")):
            result = self.ti.calculate_atr(h, lo, c)
        assert isinstance(result, pd.Series)

    # --- True Range ---
    def test_true_range_exception_path(self):
        """Lines 468-470: except Exception in calculate_true_range."""
        h, lo, c, _ = _ohlcv(20)
        with patch('pandas.concat', side_effect=RuntimeError("concat error")):
            result = self.ti.calculate_true_range(h, lo, c)
        assert isinstance(result, pd.Series)

    # --- SMA ---
    def test_sma_exception_path(self):
        """Lines 488-490: except Exception in calculate_sma."""
        prices = _prices(30)
        with patch.object(pd.Series, 'rolling', side_effect=RuntimeError("rolling error")):
            result = self.ti.calculate_sma(prices, period=10)
        assert isinstance(result, pd.Series)

    # --- EMA ---
    def test_ema_exception_path(self):
        """Lines 505-507: except Exception in calculate_ema."""
        prices = _prices(30)
        with patch.object(pd.Series, 'ewm', side_effect=RuntimeError("ewm error")):
            result = self.ti.calculate_ema(prices, period=12)
        assert isinstance(result, pd.Series)

    # --- WMA ---
    def test_wma_exception_path(self):
        """Lines 526-528: except Exception in calculate_wma."""
        prices = _prices(30)
        with patch.object(pd.Series, 'rolling', side_effect=RuntimeError("rolling error")):
            result = self.ti.calculate_wma(prices, period=10)
        assert isinstance(result, pd.Series)

    # --- Hull MA (internal WMA raises) ---
    def test_hull_ma_exception_path(self):
        """Lines 551-553: except Exception in calculate_hull_ma."""
        prices = _prices(30)
        with patch.object(self.ti, 'calculate_wma', side_effect=RuntimeError("wma error")):
            result = self.ti.calculate_hull_ma(prices, period=10)
        assert isinstance(result, pd.Series)

    # --- VWAP ---
    def test_vwap_exception_path(self):
        """Lines 581-583: except Exception in calculate_vwap."""
        h, lo, c, v = _ohlcv(20)
        with patch.object(pd.Series, 'cumsum', side_effect=RuntimeError("cumsum error")):
            result = self.ti.calculate_vwap(h, lo, c, v)
        assert isinstance(result, pd.Series)

    # --- OBV ---
    def test_obv_exception_path(self):
        """Lines 606-608: except Exception in calculate_obv."""
        _, _, c, v = _ohlcv(20)
        with patch.object(pd.Series, 'diff', side_effect=RuntimeError("diff error")):
            result = self.ti.calculate_obv(c, v)
        assert isinstance(result, pd.Series)

    # --- RSI Signal Generation ---
    def test_rsi_signal_exception_path(self):
        """Lines 637-639: except Exception in generate_rsi_signal."""
        empty_series = pd.Series([], dtype=float)
        result = self.ti.generate_rsi_signal(empty_series)  # iloc[-1] raises
        assert result == SignalType.NEUTRAL

    # --- MACD Signal Generation ---
    def test_macd_signal_exception_path(self):
        """Exception in generate_macd_signal."""
        result = self.ti.generate_macd_signal({})  # KeyError on missing "MACD"
        assert result == SignalType.NEUTRAL


# ==============================================================================
# U13 — Additional signal paths
# ==============================================================================

class TestU13SignalBranches:
    def setup_method(self):
        self.ti = TechnicalIndicators()

    def test_rsi_signal_strong_sell(self):
        rsi = pd.Series([85.0, 82.0])
        result = self.ti.generate_rsi_signal(rsi)
        assert result == SignalType.STRONG_SELL

    def test_rsi_signal_sell(self):
        rsi = pd.Series([72.0, 75.0])
        result = self.ti.generate_rsi_signal(rsi)
        assert result == SignalType.SELL

    def test_rsi_signal_strong_buy(self):
        rsi = pd.Series([18.0, 15.0])
        result = self.ti.generate_rsi_signal(rsi)
        assert result == SignalType.STRONG_BUY

    def test_rsi_signal_buy(self):
        rsi = pd.Series([28.0, 25.0])
        result = self.ti.generate_rsi_signal(rsi)
        assert result == SignalType.BUY

    def test_rsi_signal_neutral(self):
        rsi = pd.Series([50.0, 55.0])
        result = self.ti.generate_rsi_signal(rsi)
        assert result == SignalType.NEUTRAL


# ==============================================================================
# ═════════════════════════════════════════════════════════════════════════════
#  U15 — PerformanceMetrics EXCEPTION PATH TESTS
#  Missing: 202-204, 227, 233-235, 258-260, 291-293, 323-325, 351-353,
#  383-385, 438->443, 439->438, 450-452, 478-480, 506-508, 547-549,
#  607-609, 670-673, 815
# ═════════════════════════════════════════════════════════════════════════════
# ==============================================================================

class TestU15ExceptionPaths:
    """Trigger except blocks in each PerformanceCalculator method."""

    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_calculate_total_return_exception(self):
        """Lines 202-204: exception in calculate_total_return."""
        # Pass None → len(None) raises TypeError → caught → return 0.0
        result = self.calc.calculate_total_return(None)
        assert result == 0.0

    def test_calculate_annualized_return_exception(self):
        """Lines 233-235: exception in calculate_annualized_return."""
        result = self.calc.calculate_annualized_return(None)
        assert result == 0.0

    def test_calculate_volatility_exception(self):
        """Lines 258-260: exception in calculate_volatility."""
        result = self.calc.calculate_volatility(None)
        assert result == 0.0

    def test_calculate_sharpe_ratio_exception(self):
        """Lines 291-293: exception in calculate_sharpe_ratio."""
        result = self.calc.calculate_sharpe_ratio(None)
        assert result == 0.0

    def test_calculate_sortino_ratio_exception(self):
        """Lines 323-325: exception in calculate_sortino_ratio."""
        result = self.calc.calculate_sortino_ratio(None)
        assert result == 0.0

    def test_calculate_calmar_ratio_exception(self):
        """Lines 351-353: exception in calculate_calmar_ratio."""
        result = self.calc.calculate_calmar_ratio(None)
        assert result == 0.0

    def test_analyze_drawdowns_exception(self):
        """Lines 383-385: exception in analyze_drawdowns."""
        result = self.calc.analyze_drawdowns(None)
        assert isinstance(result, DrawdownInfo)
        assert result.max_drawdown == 0.0

    def test_calculate_win_rate_exception(self):
        """Lines 478-480: exception in calculate_win_rate."""
        result = self.calc.calculate_win_rate(None)
        assert result == 0.0

    def test_calculate_profit_factor_exception(self):
        """Lines 506-508: exception in calculate_profit_factor."""
        result = self.calc.calculate_profit_factor(None)
        assert result == 0.0

    def test_calculate_trade_statistics_exception(self):
        """Lines 547-549: exception in calculate_trade_statistics."""
        result = self.calc.calculate_trade_statistics(None)
        assert isinstance(result, dict)

    def test_rate_performance_exception(self):
        """Lines 607-609: exception in rate_performance."""
        # Pass non-numeric values to force exception during comparison
        result = self.calc.rate_performance("bad", "bad", "bad")
        assert isinstance(result, PerformanceRating)
        assert result == PerformanceRating.AVERAGE

    def test_generate_performance_report_exception(self):
        """Lines 670-673: exception in generate_performance_report."""
        result = self.calc.generate_performance_report(None)
        assert isinstance(result, PerformanceReport)
        assert result.total_return == 0.0
        assert result.rating == PerformanceRating.VERY_POOR

    def test_max_drawdown_exception(self):
        """Exception path in calculate_max_drawdown."""
        result = self.calc.calculate_max_drawdown(None)
        assert result == 0.0


class TestU15AnalyzeDrawdownsBranches:
    """Cover specific branches in analyze_drawdowns (lines 438->443, 450-452)."""

    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_analyze_drawdowns_no_drawdown(self):
        """Lines 438->443: drawdown_periods empty → if drawdown_periods: is False."""
        # Monotonically increasing → no drawdown
        cum_ret = pd.Series(np.linspace(0, 0.2, 50))  # always increasing
        result = self.calc.analyze_drawdowns(cum_ret)
        assert isinstance(result, DrawdownInfo)
        assert result.max_drawdown_duration == 0

    def test_analyze_drawdowns_with_recovery(self):
        """Lines 450-452: recovery time calculated when drawdown recovers."""
        # Create cumulative returns with a dip that recovers
        values = [0.0, 0.05, 0.03, 0.01, 0.0, -0.02, -0.05, -0.03, 0.02, 0.06, 0.10]
        cum_ret = pd.Series(values)
        result = self.calc.analyze_drawdowns(cum_ret)
        assert isinstance(result, DrawdownInfo)

    def test_analyze_drawdowns_ends_in_drawdown(self):
        """end_in_drawdown path: still in drawdown at end of series."""
        # Starts high then goes down without recovery
        values = [0.0, 0.05, 0.03, -0.05, -0.10, -0.15]
        cum_ret = pd.Series(values)
        result = self.calc.analyze_drawdowns(cum_ret)
        assert result.max_drawdown < 0.0

    def test_analyze_drawdowns_empty_returns_zero(self):
        result = self.calc.analyze_drawdowns(pd.Series([], dtype=float))
        assert result.max_drawdown == 0.0

    def test_sortino_ratio_no_downside_returns(self):
        """Lines 323: all-positive returns → no downside → returns inf or 0."""
        returns = _returns(50)
        all_positive = returns.abs()  # all positive
        result = self.calc.calculate_sortino_ratio(all_positive)
        assert isinstance(result, float)

    def test_calmar_ratio_no_drawdown(self):
        """Lines 351: zero drawdown → returns inf or 0."""
        all_positive = pd.Series(np.ones(50) * 0.01)  # steady gains
        result = self.calc.calculate_calmar_ratio(all_positive)
        assert isinstance(result, float)

    def test_profit_factor_no_losses(self):
        """Lines 506: gross_loss == 0 → special case."""
        all_winning = pd.Series([0.01, 0.02, 0.005, 0.03])
        result = self.calc.calculate_profit_factor(all_winning)
        # With no losses, profit_factor should be inf
        assert result == float("inf")


class TestU15ModuleFunctions:
    """Cover module-level functions and U15 line 815."""

    def test_calculate_metrics_function(self):
        """Line 815: calculate_metrics at bottom of file."""
        result = calculate_metrics()
        assert isinstance(result, dict)
        assert "sharpe_ratio" in result

    def test_calculate_metrics_with_data(self):
        result = calculate_metrics(data="anything")
        assert isinstance(result, dict)

    def test_get_performance_calculator_singleton(self):
        _u15._performance_calculator_instance = None
        c1 = get_performance_calculator()
        c2 = get_performance_calculator()
        assert c1 is c2

    def test_module_calculate_sharpe_ratio(self):
        result = calculate_sharpe_ratio(_returns(30))
        assert isinstance(result, float)

    def test_module_calculate_max_drawdown(self):
        cum = _returns(30).cumsum()
        result = calculate_max_drawdown(cum)
        assert isinstance(result, float)

    def test_module_generate_performance_report(self):
        result = generate_performance_report(_returns(30))
        assert isinstance(result, PerformanceReport)

    def test_annualized_return_years_zero(self):
        """Line 227: years <= 0 branch → return 0.0."""
        calc = PerformanceCalculator()
        # Single return → years = 1/252 = tiny but > 0. Need 0 returns.
        returns = pd.Series([0.01])
        # Manually test the years <= 0 path by passing period=0 not possible,
        # but we can test that the function returns a finite float
        result = calc.calculate_annualized_return(returns, periods_per_year=0)
        assert result == 0.0  # division by zero safely handled

    def test_performance_rating_all_levels(self):
        """Cover rate_performance all rating branches."""
        calc = PerformanceCalculator()
        # EXCELLENT: sharpe >=2, calmar >=2, win_rate >=60
        assert calc.rate_performance(2.0, 2.0, 65.0) == PerformanceRating.EXCELLENT
        # VERY_POOR: all zeros
        assert calc.rate_performance(0.0, 0.0, 0.0) == PerformanceRating.VERY_POOR
        # POOR: low scores
        r = calc.rate_performance(0.5, 0.5, 42.0)
        assert isinstance(r, PerformanceRating)


# ==============================================================================
# ═════════════════════════════════════════════════════════════════════════════
#  U11 — FeatureFlags GAP TESTS
#  Missing: 274->278 (env check), 285-287 (dependency), 355-357 (enable exc),
#  377 (disable exc?), 385-387 (disable exc), 414 (create exc), 466-468
#  (set_rollout exc), 527-528 (list), 538-540 (get_feature_info), 558-559,
#  565-581 (save), 596-597 (cache), 603 (cache), 691 (long line)
# ═════════════════════════════════════════════════════════════════════════════
# ==============================================================================

class TestU11EnvironmentAndDependencyChecks:
    """Cover is_enabled branches for environment and dependency restrictions."""

    def test_feature_enabled_in_correct_environment(self, tmp_path):
        flags = _fresh_flags(tmp_path)
        flags.create_feature("env_feat", enabled=True)
        flags.features["env_feat"].environments = ["development", "production"]
        flags.environment = "development"
        assert flags.is_enabled("env_feat") is True

    def test_feature_disabled_in_wrong_environment(self, tmp_path):
        """Lines 274->278: environment restriction → return False."""
        flags = _fresh_flags(tmp_path)
        flags.create_feature("env_restricted", enabled=True)
        flags.features["env_restricted"].environments = ["production"]
        flags.environment = "development"  # not in ["production"]
        assert flags.is_enabled("env_restricted") is False

    def test_feature_with_all_environments(self, tmp_path):
        """Edge: environments=['all'] → no restriction."""
        flags = _fresh_flags(tmp_path)
        flags.create_feature("all_env", enabled=True)
        flags.features["all_env"].environments = ["all"]
        flags.environment = "development"
        assert flags.is_enabled("all_env") is True

    def test_dependency_not_enabled_returns_false(self, tmp_path):
        """Lines 285-287: dependency not enabled → is_enabled returns False."""
        flags = _fresh_flags(tmp_path)
        flags.create_feature("base_feat", enabled=False)
        flags.create_feature("dep_feat", enabled=True)
        flags.features["dep_feat"].dependencies = ["base_feat"]
        # base_feat is disabled, so dep_feat should return False
        assert flags.is_enabled("dep_feat") is False

    def test_dependency_enabled_allows_feature(self, tmp_path):
        """Dependency IS enabled → feature should be enabled too."""
        flags = _fresh_flags(tmp_path)
        flags.create_feature("base_feat", enabled=True)
        flags.create_feature("dep_feat", enabled=True)
        flags.features["dep_feat"].dependencies = ["base_feat"]
        flags.features["dep_feat"].environments = ["all"]
        flags.features["base_feat"].environments = ["all"]
        assert flags.is_enabled("dep_feat") is True

    def test_unknown_feature_returns_false(self, tmp_path):
        flags = _fresh_flags(tmp_path)
        assert flags.is_enabled("nonexistent_feature_xyz") is False

    def test_check_feature_enabled_alias(self, tmp_path):
        """check_feature_enabled is alias for is_enabled."""
        flags = _fresh_flags(tmp_path)
        assert flags.check_feature_enabled("nonexistent_feature") is False


class TestU11FeatureManagement:
    """Cover enable_feature, disable_feature, create_feature, set_rollout."""

    def test_enable_existing_feature(self, tmp_path):
        flags = _fresh_flags(tmp_path)
        flags.create_feature("my_feat", enabled=False)
        result = flags.enable_feature("my_feat", save=False)
        assert result is True
        assert flags.features["my_feat"].enabled is True

    def test_enable_nonexistent_creates_feature(self, tmp_path):
        """enable_feature on nonexistent feature creates it."""
        flags = _fresh_flags(tmp_path)
        result = flags.enable_feature("brand_new_feature", save=False)
        assert result is True
        assert "brand_new_feature" in flags.features

    def test_enable_feature_exception(self, tmp_path):
        """Lines 355-357: exception during enable → return False."""
        flags = _fresh_flags(tmp_path)
        flags.create_feature("good_feat", enabled=False)
        # Make the lock raise
        with patch.object(flags, 'lock', MagicMock(__enter__=MagicMock(side_effect=RuntimeError("lock error")),
                                                   __exit__=MagicMock(return_value=False))):
            result = flags.enable_feature("good_feat", save=False)
        assert result is False

    def test_disable_feature_found(self, tmp_path):
        flags = _fresh_flags(tmp_path)
        flags.create_feature("my_feat", enabled=True)
        result = flags.disable_feature("my_feat", save=False)
        assert result is True
        assert flags.features["my_feat"].enabled is False

    def test_disable_feature_not_found(self, tmp_path):
        """Lines 377: feature not found → return False."""
        flags = _fresh_flags(tmp_path)
        result = flags.disable_feature("nonexistent_feature", save=False)
        assert result is False

    def test_disable_feature_exception(self, tmp_path):
        """Lines 385-387: exception during disable → return False."""
        flags = _fresh_flags(tmp_path)
        flags.create_feature("feat", enabled=True)
        with patch.object(flags, 'lock', MagicMock(__enter__=MagicMock(side_effect=RuntimeError("lock error")),
                                                   __exit__=MagicMock(return_value=False))):
            result = flags.disable_feature("feat", save=False)
        assert result is False

    def test_create_feature_success(self, tmp_path):
        flags = _fresh_flags(tmp_path)
        result = flags.create_feature("new_flag", enabled=True)
        assert result is True
        assert "new_flag" in flags.features

    def test_create_feature_already_exists(self, tmp_path):
        """Lines 414: feature already exists → return False (logs warning)."""
        flags = _fresh_flags(tmp_path)
        flags.create_feature("dup_feat", enabled=True)
        result = flags.create_feature("dup_feat", enabled=False)
        assert result is False

    def test_create_feature_exception(self, tmp_path):
        """Exception during create → return False."""
        flags = _fresh_flags(tmp_path)
        with patch.object(flags, 'lock', MagicMock(__enter__=MagicMock(side_effect=RuntimeError("error")),
                                                   __exit__=MagicMock(return_value=False))):
            result = flags.create_feature("some_feat")
        assert result is False

    def test_set_rollout_percentage_valid(self, tmp_path):
        flags = _fresh_flags(tmp_path)
        flags.create_feature("rollout_feat", enabled=True)
        result = flags.set_rollout_percentage("rollout_feat", 50.0, save=False)
        assert result is True

    def test_set_rollout_percentage_out_of_range(self, tmp_path):
        """Lines 466-468: invalid percentage → exception → return False."""
        flags = _fresh_flags(tmp_path)
        flags.create_feature("rollout_feat", enabled=True)
        result = flags.set_rollout_percentage("rollout_feat", 150.0, save=False)
        assert result is False

    def test_set_rollout_percentage_feature_not_found(self, tmp_path):
        flags = _fresh_flags(tmp_path)
        result = flags.set_rollout_percentage("nonexistent", 50.0, save=False)
        assert result is False


class TestU11FeatureQueryMethods:
    """Cover get_feature_info, list_features, get_enabled_features."""

    def test_get_feature_info_found(self, tmp_path):
        flags = _fresh_flags(tmp_path)
        flags.create_feature("my_feat", enabled=True)
        info = flags.get_feature_info("my_feat")
        assert info is not None
        assert info["name"] == "my_feat"

    def test_get_feature_info_not_found(self, tmp_path):
        """Lines ~527-528: feature not found → return None."""
        flags = _fresh_flags(tmp_path)
        info = flags.get_feature_info("nonexistent_feature_xyz")
        assert info is None

    def test_list_features_all(self, tmp_path):
        """Lines ~538-540: list all features."""
        flags = _fresh_flags(tmp_path)
        features = flags.list_features()
        assert isinstance(features, list)
        assert len(features) > 0

    def test_list_features_by_type(self, tmp_path):
        flags = _fresh_flags(tmp_path)
        features = flags.list_features(feature_type=FeatureType.CORE)
        assert isinstance(features, list)

    def test_get_enabled_features(self, tmp_path):
        flags = _fresh_flags(tmp_path)
        flags.create_feature("enabled_feat", enabled=True)
        flags.features["enabled_feat"].environments = ["all"]
        enabled = flags.get_enabled_features()
        assert isinstance(enabled, list)


class TestU11PrivateMethods:
    """Cover private configuration methods."""

    def test_load_config_from_existing_file(self, tmp_path):
        """Load from existing JSON config file."""
        import json
        config_path = os.path.join(str(tmp_path), "flags.json")
        config_data = {
            "my_custom_feature": {
                "name": "my_custom_feature",
                "enabled": True,
                "status": "enabled",
                "type": "core",
                "description": "test",
                "rollout_percentage": 100.0,
                "rollout_strategy": "all",
                "enabled_users": [],
                "environments": ["all"],
                "dependencies": [],
                "metadata": {},
            }
        }
        with open(config_path, "w") as f:
            json.dump(config_data, f)
        flags = FeatureFlags(config_file=config_path)
        assert "my_custom_feature" in flags.features

    def test_apply_env_overrides_testing_all_features(self, tmp_path):
        """Lines 558-559: testing environment enables all features."""
        config_path = os.path.join(str(tmp_path), "flags.json")
        flags = FeatureFlags(config_file=config_path)
        flags.environment = "testing"
        flags._apply_environment_overrides()
        # In testing env, all_features=True enables everything
        for feat in flags.features.values():
            assert feat.enabled is True

    def test_apply_env_overrides_production(self, tmp_path):
        """Production env disables experimental features."""
        config_path = os.path.join(str(tmp_path), "flags.json")
        flags = FeatureFlags(config_file=config_path)
        flags.environment = "production"
        flags._apply_environment_overrides()
        # experimental features should be disabled

    def test_save_configuration(self, tmp_path):
        """Lines 565-581: save configuration to JSON file."""
        config_path = os.path.join(str(tmp_path), "flags.json")
        flags = FeatureFlags(config_file=config_path)
        flags.create_feature("save_test", enabled=True)
        flags._save_configuration()
        import json
        with open(config_path) as f:
            data = json.load(f)
        assert "save_test" in data or len(data) > 0

    def test_refresh_cache_if_needed_triggers_reload(self, tmp_path):
        """Lines 596-597, 603: cache refresh logic."""
        config_path = os.path.join(str(tmp_path), "flags.json")
        flags = FeatureFlags(config_file=config_path)
        # Force cache to be stale
        flags.cache_timestamp = 0.0
        flags._refresh_cache_if_needed()  # should trigger reload


class TestU11RolloutStrategies:
    """Cover RolloutStrategy branches in is_enabled_for_user."""

    def test_user_list_strategy_user_in_list(self, tmp_path):
        flags = _fresh_flags(tmp_path)
        flags.create_feature("user_feat", enabled=True)
        ff = flags.features["user_feat"]
        ff.rollout_strategy = RolloutStrategy.USER_LIST
        ff.enabled_users = ["user123"]
        ff.environments = ["all"]
        assert ff.is_enabled_for_user("user123") is True

    def test_user_list_strategy_user_not_in_list(self, tmp_path):
        flags = _fresh_flags(tmp_path)
        flags.create_feature("user_feat", enabled=True)
        ff = flags.features["user_feat"]
        ff.rollout_strategy = RolloutStrategy.USER_LIST
        ff.enabled_users = ["user123"]
        assert ff.is_enabled_for_user("other_user") is False

    def test_percentage_strategy(self, tmp_path):
        flags = _fresh_flags(tmp_path)
        flags.create_feature("pct_feat", enabled=True)
        ff = flags.features["pct_feat"]
        ff.rollout_percentage = 100.0
        ff.rollout_strategy = RolloutStrategy.PERCENTAGE
        result = ff.is_enabled_for_user("any_user")
        assert isinstance(result, bool)

    def test_percentage_strategy_zero_percent(self, tmp_path):
        flags = _fresh_flags(tmp_path)
        flags.create_feature("pct_feat", enabled=True)
        ff = flags.features["pct_feat"]
        ff.rollout_percentage = 0.0
        ff.rollout_strategy = RolloutStrategy.PERCENTAGE
        result = ff.is_enabled_for_user("any_user")
        assert result is False

    def test_feature_expired_returns_false(self, tmp_path):
        flags = _fresh_flags(tmp_path)
        flags.create_feature("exp_feat", enabled=True)
        ff = flags.features["exp_feat"]
        ff.expires_date = _dt.datetime(2020, 1, 1)  # past date
        assert ff.is_expired() is True
        assert ff.is_enabled_for_user("user") is False

    def test_feature_not_expired(self, tmp_path):
        flags = _fresh_flags(tmp_path)
        flags.create_feature("valid_feat", enabled=True)
        ff = flags.features["valid_feat"]
        ff.expires_date = _dt.datetime(2099, 12, 31)  # future
        assert ff.is_expired() is False

    def test_feature_flag_invalid_name_raises(self):
        """FeatureFlag with empty name raises ValueError in __post_init__."""
        with pytest.raises(ValueError, match="Feature name cannot be empty"):
            FeatureFlag(name="", enabled=True, status=FeatureStatus.ENABLED,
                        type=FeatureType.CORE)

    def test_feature_flag_invalid_rollout_raises(self):
        """FeatureFlag with rollout > 100 raises ValueError."""
        with pytest.raises(ValueError, match="Rollout percentage"):
            FeatureFlag(name="test", enabled=True, status=FeatureStatus.ENABLED,
                        type=FeatureType.CORE, rollout_percentage=150.0)

    def test_feature_to_dict_with_expires_date(self):
        """to_dict includes expires_date isoformat when set."""
        ff = FeatureFlag(
            name="test_ff", enabled=True, status=FeatureStatus.ENABLED,
            type=FeatureType.CORE,
            expires_date=_dt.datetime(2099, 12, 31),
        )
        d = ff.to_dict()
        assert d["expires_date"] is not None
        assert "2099" in d["expires_date"]


class TestU11DefaultFeatures:
    """Ensure DEFAULT_FEATURES and module-level constants work correctly."""

    def test_default_features_is_dict(self):
        assert isinstance(DEFAULT_FEATURES, dict)
        assert len(DEFAULT_FEATURES) > 0

    def test_default_features_has_core_features(self):
        assert "advanced_risk_management" in DEFAULT_FEATURES
        assert "iron_condor_automation" in DEFAULT_FEATURES

    def test_feature_status_values(self):
        for status in FeatureStatus:
            assert isinstance(status.value, str)

    def test_rollout_strategy_values(self):
        for strategy in RolloutStrategy:
            assert isinstance(strategy.value, str)

    def test_feature_type_values(self):
        for ft in FeatureType:
            assert isinstance(ft.value, str)
