#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: test_SpyderT103_U20InstitutionalLibraries.py
Purpose: Tests for SpyderU20_InstitutionalLibraries

Author: Spyder Dev
Year Created: 2025
Last Updated: 2025-01-01 Time: 00:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import types
import warnings
from unittest.mock import MagicMock, patch

# ==============================================================================
# PATH SETUP
# ==============================================================================
_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# ==============================================================================
# MODULE STUBS
# ==============================================================================


def _ensure_pkg(name: str) -> None:
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)

_ensure_pkg("Spyder")
_ensure_pkg("Spyder.SpyderU_Utilities")

_logger_mod = types.ModuleType("Spyder.SpyderU_Utilities.SpyderU01_Logger")


class _FakeSpyderLogger:
    @staticmethod
    def get_logger(name: str) -> MagicMock:
        return MagicMock()


_logger_mod.SpyderLogger = _FakeSpyderLogger
_logger_mod.get_logger = MagicMock(return_value=MagicMock())
sys.modules["Spyder.SpyderU_Utilities.SpyderU01_Logger"] = _logger_mod

_err_mod = types.ModuleType("Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler")
_err_mod.SpyderErrorHandler = MagicMock
sys.modules["Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler"] = _err_mod

# ==============================================================================
# THIRD-PARTY IMPORTS AND MODULE IMPORTS
# ==============================================================================
import pytest
import numpy as np
import pandas as pd

pytestmark = pytest.mark.filterwarnings(
    "ignore:.*Ray will no longer override accelerator visible devices env var.*:FutureWarning"
)

warnings.filterwarnings("ignore")   # suppress library-availability warnings globally
warnings.filterwarnings(
    "ignore",
    message=r"Tip: In future versions of Ray, Ray will no longer override accelerator visible devices env var.*",
    category=FutureWarning,
)

from Spyder.SpyderU_Utilities.SpyderU20_InstitutionalLibraries import (
    # dataclasses
    OptionPricing,
    InstitutionalMetrics,
    PortfolioOptimization,
    # main class
    InstitutionalLibraries,
    # module functions
    get_institutional_libraries,
    reset_institutional_libraries,
    # constants
    DEFAULT_RISK_FREE_RATE,
    TRADING_DAYS_PER_YEAR,
    HOURS_PER_TRADING_DAY,
    LIBRARY_STATUS,
    # availability flags
    QUANTLIB_AVAILABLE,
    SCIPY_AVAILABLE,
    SKLEARN_AVAILABLE,
)
from Spyder.SpyderU_Utilities.SpyderU20_InstitutionalLibraries import (
    test_institutional_libraries as run_institutional_libraries_smoke_test,
)

# OptionType may come from constants or internal fallback
from Spyder.SpyderU_Utilities.SpyderU20_InstitutionalLibraries import (
    OPTIONTYPE_AVAILABLE,
)

# Resolve OptionType (always available via fallback)
try:
    from Spyder.SpyderU_Utilities.SpyderU07_Constants import OptionType
except ImportError:
    # Use the fallback inside the module
    from enum import Enum
    class OptionType(Enum):
        CALL = "CALL"
        PUT = "PUT"

# ==============================================================================
# HELPERS
# ==============================================================================
_TRADING_DAYS = 252
np.random.seed(42)
_SAMPLE_RETURNS_1Y = pd.Series(np.random.normal(0.001, 0.02, _TRADING_DAYS))
_SAMPLE_RETURNS_POSITIVE = pd.Series(np.abs(np.random.normal(0.002, 0.01, _TRADING_DAYS)))
_SAMPLE_RETURNS_NEGATIVE = pd.Series(-np.abs(np.random.normal(0.002, 0.01, _TRADING_DAYS)))


def _fresh_libs() -> InstitutionalLibraries:
    """Create a fresh InstitutionalLibraries instance without touching singleton."""
    return InstitutionalLibraries()


def _make_returns_df(n_assets: int = 3, n_days: int = 100) -> pd.DataFrame:
    """Create a returns DataFrame for portfolio optimization tests."""
    np.random.seed(99)
    data = np.random.normal(0.001, 0.02, (n_days, n_assets))
    return pd.DataFrame(data, columns=[f"Asset{i}" for i in range(n_assets)])


# ==============================================================================
# CONSTANTS TESTS
# ==============================================================================


class TestU20Constants:
    """Tests for U20 module-level constants."""

    def test_default_risk_free_rate_is_float(self):
        assert isinstance(DEFAULT_RISK_FREE_RATE, float)

    def test_default_risk_free_rate_range(self):
        assert 0.0 < DEFAULT_RISK_FREE_RATE < 0.20

    def test_trading_days_per_year(self):
        assert TRADING_DAYS_PER_YEAR == 252

    def test_hours_per_trading_day(self):
        assert HOURS_PER_TRADING_DAY == 6.5

    def test_library_status_is_dict(self):
        assert isinstance(LIBRARY_STATUS, dict)

    def test_library_status_has_expected_keys(self):
        assert "quantlib" in LIBRARY_STATUS
        assert "scipy" in LIBRARY_STATUS
        assert "sklearn" in LIBRARY_STATUS

    def test_library_status_bool_values(self):
        for k, v in LIBRARY_STATUS.items():
            assert isinstance(v, bool), f"Key {k} has non-bool value: {v}"


# ==============================================================================
# DATACLASS TESTS
# ==============================================================================


class TestOptionPricingDataclass:
    """Tests for OptionPricing dataclass."""

    def test_basic_creation(self):
        op = OptionPricing(
            theoretical_price=5.0,
            delta=0.5,
            gamma=0.02,
            theta=-0.05,
            vega=0.15,
            rho=0.03,
        )
        assert op.theoretical_price == 5.0
        assert op.delta == 0.5

    def test_default_optional_fields(self):
        op = OptionPricing(
            theoretical_price=0.0,
            delta=0.0,
            gamma=0.0,
            theta=0.0,
            vega=0.0,
            rho=0.0,
        )
        assert op.implied_volatility is None
        assert op.moneyness is None

    def test_with_all_fields(self):
        op = OptionPricing(
            theoretical_price=10.0,
            delta=-0.7,
            gamma=0.01,
            theta=-0.08,
            vega=0.20,
            rho=-0.04,
            implied_volatility=0.25,
            intrinsic_value=8.0,
            time_value=2.0,
            moneyness=0.95,
        )
        assert op.implied_volatility == 0.25
        assert op.moneyness == 0.95

    def test_negative_delta(self):
        op = OptionPricing(
            theoretical_price=3.0, delta=-0.4, gamma=0.015,
            theta=-0.03, vega=0.12, rho=-0.02,
        )
        assert op.delta < 0

    def test_zero_price_creation(self):
        op = OptionPricing(
            theoretical_price=0.0, delta=0.0, gamma=0.0,
            theta=0.0, vega=0.0, rho=0.0,
        )
        assert op.theoretical_price == 0.0


class TestInstitutionalMetricsDataclass:
    """Tests for InstitutionalMetrics dataclass."""

    def _make(self, **kwargs):
        defaults = dict(
            annual_return=0.15,
            volatility=0.20,
            sharpe_ratio=0.75,
            sortino_ratio=1.0,
            max_drawdown=-0.15,
            calmar_ratio=1.0,
            win_rate=0.55,
            profit_factor=1.5,
            recovery_factor=2.0,
        )
        defaults.update(kwargs)
        return InstitutionalMetrics(**defaults)

    def test_basic_creation(self):
        m = self._make()
        assert m.annual_return == 0.15
        assert m.volatility == 0.20

    def test_sharpe_ratio_stored(self):
        m = self._make(sharpe_ratio=1.5)
        assert m.sharpe_ratio == 1.5

    def test_optional_var_none_by_default(self):
        m = self._make()
        assert m.var_95 is None
        assert m.cvar_95 is None

    def test_optional_skewness_set(self):
        m = self._make(skewness=-0.5, kurtosis=3.0)
        assert m.skewness == -0.5
        assert m.kurtosis == 3.0

    def test_max_drawdown_negative(self):
        m = self._make(max_drawdown=-0.25)
        assert m.max_drawdown < 0

    def test_win_rate_range(self):
        m = self._make(win_rate=0.60)
        assert 0.0 <= m.win_rate <= 1.0


class TestPortfolioOptimizationDataclass:
    """Tests for PortfolioOptimization dataclass."""

    def test_basic_creation(self):
        po = PortfolioOptimization(
            weights={"A": 0.5, "B": 0.5},
            expected_return=0.12,
            expected_volatility=0.15,
            sharpe_ratio=0.80,
            optimization_method="scipy_max_sharpe",
            constraints_satisfied=True,
            optimization_success=True,
        )
        assert po.optimization_success is True

    def test_weights_sum_to_one(self):
        po = PortfolioOptimization(
            weights={"A": 0.4, "B": 0.3, "C": 0.3},
            expected_return=0.10,
            expected_volatility=0.12,
            sharpe_ratio=0.65,
            optimization_method="scipy_min_vol",
            constraints_satisfied=True,
            optimization_success=True,
        )
        assert abs(sum(po.weights.values()) - 1.0) < 0.01

    def test_failed_optimization(self):
        po = PortfolioOptimization(
            weights={},
            expected_return=0.0,
            expected_volatility=0.0,
            sharpe_ratio=0.0,
            optimization_method="none",
            constraints_satisfied=False,
            optimization_success=False,
        )
        assert po.optimization_success is False

    def test_sharpe_stored(self):
        po = PortfolioOptimization(
            weights={"X": 1.0},
            expected_return=0.20,
            expected_volatility=0.10,
            sharpe_ratio=2.0,
            optimization_method="test",
            constraints_satisfied=True,
            optimization_success=True,
        )
        assert po.sharpe_ratio == 2.0


# ==============================================================================
# InstitutionalLibraries INIT TESTS
# ==============================================================================


class TestInstitutionalLibrariesInit:
    """Tests for InstitutionalLibraries initialization."""

    def test_creates_instance(self):
        libs = _fresh_libs()
        assert isinstance(libs, InstitutionalLibraries)

    def test_available_libraries_is_dict(self):
        libs = _fresh_libs()
        assert isinstance(libs.available_libraries, dict)

    def test_risk_free_rate_default(self):
        libs = _fresh_libs()
        assert libs.risk_free_rate == DEFAULT_RISK_FREE_RATE

    def test_option_type_exposed(self):
        libs = _fresh_libs()
        # OptionType must be accessible via the instance
        assert hasattr(libs, "OptionType")

    def test_option_type_has_call_put(self):
        libs = _fresh_libs()
        assert hasattr(libs.OptionType, "CALL")
        assert hasattr(libs.OptionType, "PUT")

    def test_calculation_cache_empty_on_init(self):
        libs = _fresh_libs()
        assert isinstance(libs._calculation_cache, dict)
        assert len(libs._calculation_cache) == 0

    def test_available_libraries_has_scipy(self):
        libs = _fresh_libs()
        assert "scipy" in libs.available_libraries


# ==============================================================================
# LIBRARY STATUS METHODS TESTS
# ==============================================================================


class TestLibraryStatusMethods:
    """Tests for library status and availability methods."""

    def setup_method(self):
        self.libs = _fresh_libs()

    def test_get_library_status_returns_dict(self):
        result = self.libs.get_library_status()
        assert isinstance(result, dict)

    def test_get_library_status_is_copy(self):
        result = self.libs.get_library_status()
        result["extra_key"] = True
        assert "extra_key" not in self.libs.available_libraries

    def test_get_available_libraries_count_returns_tuple(self):
        result = self.libs.get_available_libraries_count()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_available_count_non_negative(self):
        available, total = self.libs.get_available_libraries_count()
        assert available >= 0
        assert total > 0
        assert available <= total

    def test_is_library_available_scipy(self):
        result = self.libs.is_library_available("scipy")
        assert isinstance(result, bool)
        assert result == SCIPY_AVAILABLE

    def test_is_library_available_nonexistent(self):
        result = self.libs.is_library_available("nonexistent_library_xyz")
        assert result is False

    def test_is_library_available_quantlib(self):
        result = self.libs.is_library_available("quantlib")
        assert isinstance(result, bool)
        assert result == QUANTLIB_AVAILABLE


# ==============================================================================
# SET_RISK_FREE_RATE / CLEAR_CACHE TESTS
# ==============================================================================


class TestSetRiskFreeRate:
    """Tests for set_risk_free_rate method."""

    def setup_method(self):
        self.libs = _fresh_libs()

    def test_sets_correctly(self):
        self.libs.set_risk_free_rate(0.06)
        assert self.libs.risk_free_rate == pytest.approx(0.06)

    def test_sets_zero(self):
        self.libs.set_risk_free_rate(0.0)
        assert self.libs.risk_free_rate == 0.0

    def test_sets_high_rate(self):
        self.libs.set_risk_free_rate(0.10)
        assert self.libs.risk_free_rate == pytest.approx(0.10)


class TestClearCache:
    """Tests for clear_cache method."""

    def setup_method(self):
        self.libs = _fresh_libs()

    def test_clear_empty_cache_no_error(self):
        self.libs.clear_cache()
        assert len(self.libs._calculation_cache) == 0

    def test_clear_populated_cache(self):
        self.libs._calculation_cache["some_key"] = "some_value"
        self.libs.clear_cache()
        assert len(self.libs._calculation_cache) == 0

    def test_clear_multiple_times(self):
        self.libs.clear_cache()
        self.libs.clear_cache()
        assert len(self.libs._calculation_cache) == 0


# ==============================================================================
# CALCULATE_INSTITUTIONAL_METRICS TESTS
# ==============================================================================


class TestCalculateInstitutionalMetrics:
    """Tests for calculate_institutional_metrics method."""

    def setup_method(self):
        self.libs = _fresh_libs()

    def test_returns_institutional_metrics(self):
        result = self.libs.calculate_institutional_metrics(_SAMPLE_RETURNS_1Y)
        assert isinstance(result, InstitutionalMetrics)

    def test_accepts_list(self):
        result = self.libs.calculate_institutional_metrics(list(_SAMPLE_RETURNS_1Y))
        assert isinstance(result, InstitutionalMetrics)

    def test_accepts_ndarray(self):
        result = self.libs.calculate_institutional_metrics(_SAMPLE_RETURNS_1Y.values)
        assert isinstance(result, InstitutionalMetrics)

    def test_annual_return_is_float(self):
        result = self.libs.calculate_institutional_metrics(_SAMPLE_RETURNS_1Y)
        assert isinstance(result.annual_return, float)

    def test_volatility_positive(self):
        result = self.libs.calculate_institutional_metrics(_SAMPLE_RETURNS_1Y)
        assert result.volatility > 0

    def test_max_drawdown_non_positive(self):
        result = self.libs.calculate_institutional_metrics(_SAMPLE_RETURNS_1Y)
        assert result.max_drawdown <= 0

    def test_win_rate_between_zero_and_one(self):
        result = self.libs.calculate_institutional_metrics(_SAMPLE_RETURNS_1Y)
        assert 0.0 <= result.win_rate <= 1.0

    def test_positive_returns_positive_annual_return(self):
        result = self.libs.calculate_institutional_metrics(_SAMPLE_RETURNS_POSITIVE)
        assert result.annual_return > 0

    def test_negative_returns_negative_annual_return(self):
        result = self.libs.calculate_institutional_metrics(_SAMPLE_RETURNS_NEGATIVE)
        assert result.annual_return < 0

    def test_custom_risk_free_rate(self):
        r1 = self.libs.calculate_institutional_metrics(_SAMPLE_RETURNS_1Y, risk_free_rate=0.02)
        r2 = self.libs.calculate_institutional_metrics(_SAMPLE_RETURNS_1Y, risk_free_rate=0.08)
        # Different risk-free rates should produce different Sharpe ratios
        assert r1.sharpe_ratio != r2.sharpe_ratio

    def test_scipy_metrics_set_if_available(self):
        result = self.libs.calculate_institutional_metrics(_SAMPLE_RETURNS_1Y)
        if SCIPY_AVAILABLE:
            assert result.var_95 is not None
            assert result.skewness is not None
            assert result.kurtosis is not None
        else:
            assert result.var_95 is None


class TestCalculateMetricsWithBenchmark:
    """Tests for calculate_institutional_metrics with benchmark."""

    def setup_method(self):
        self.libs = _fresh_libs()
        np.random.seed(7)
        self.benchmark = pd.Series(np.random.normal(0.0008, 0.015, _TRADING_DAYS))

    def test_information_ratio_set_with_benchmark(self):
        result = self.libs.calculate_institutional_metrics(
            _SAMPLE_RETURNS_1Y, benchmark_returns=self.benchmark
        )
        assert isinstance(result, InstitutionalMetrics)
        assert result.information_ratio is not None

    def test_information_ratio_is_float(self):
        result = self.libs.calculate_institutional_metrics(
            _SAMPLE_RETURNS_1Y, benchmark_returns=self.benchmark
        )
        assert isinstance(result.information_ratio, float)

    def test_treynor_ratio_set_with_scipy(self):
        result = self.libs.calculate_institutional_metrics(
            _SAMPLE_RETURNS_1Y, benchmark_returns=self.benchmark
        )
        if SCIPY_AVAILABLE:
            assert result.treynor_ratio is not None

    def test_benchmark_wrong_length_handles_gracefully(self):
        short_benchmark = pd.Series(np.random.normal(0, 0.01, 50))
        result = self.libs.calculate_institutional_metrics(
            _SAMPLE_RETURNS_1Y, benchmark_returns=short_benchmark
        )
        # Should still return metrics, just without benchmark-dependent ones
        assert isinstance(result, InstitutionalMetrics)
        assert result.information_ratio is None


# ==============================================================================
# PRICE_OPTION TESTS
# ==============================================================================


class TestPriceOption:
    """Tests for price_option method (QuantLib-dependent)."""

    def setup_method(self):
        self.libs = _fresh_libs()

    def test_returns_none_when_quantlib_unavailable(self):
        if QUANTLIB_AVAILABLE:
            pytest.skip("QuantLib is available — testing fallback behavior not applicable")
        result = self.libs.price_option(
            spot=400.0, strike=400.0, time_to_expiry=0.1,
            risk_free_rate=0.05, volatility=0.20,
            option_type=OptionType.CALL,
        )
        assert result is None

    @pytest.mark.skipif(not QUANTLIB_AVAILABLE, reason="QuantLib required")
    def test_price_call_returns_option_pricing(self):
        result = self.libs.price_option(
            spot=400.0, strike=400.0, time_to_expiry=0.1,
            risk_free_rate=0.05, volatility=0.20,
            option_type=OptionType.CALL,
        )
        assert isinstance(result, OptionPricing)

    @pytest.mark.skipif(not QUANTLIB_AVAILABLE, reason="QuantLib required")
    def test_price_put_returns_option_pricing(self):
        result = self.libs.price_option(
            spot=400.0, strike=400.0, time_to_expiry=0.1,
            risk_free_rate=0.05, volatility=0.20,
            option_type=OptionType.PUT,
        )
        assert isinstance(result, OptionPricing)

    @pytest.mark.skipif(not QUANTLIB_AVAILABLE, reason="QuantLib required")
    def test_call_delta_positive(self):
        result = self.libs.price_option(
            spot=400.0, strike=400.0, time_to_expiry=0.1,
            risk_free_rate=0.05, volatility=0.20,
            option_type=OptionType.CALL,
        )
        assert result.delta > 0

    @pytest.mark.skipif(not QUANTLIB_AVAILABLE, reason="QuantLib required")
    def test_put_delta_negative(self):
        result = self.libs.price_option(
            spot=400.0, strike=400.0, time_to_expiry=0.1,
            risk_free_rate=0.05, volatility=0.20,
            option_type=OptionType.PUT,
        )
        assert result.delta < 0


# ==============================================================================
# PRICE_SPREAD TESTS
# ==============================================================================


class TestPriceSpread:
    """Tests for price_spread method."""

    def setup_method(self):
        self.libs = _fresh_libs()

    def test_returns_none_when_quantlib_unavailable(self):
        if QUANTLIB_AVAILABLE:
            pytest.skip("QuantLib available — testing None return not applicable")
        result = self.libs.price_spread(
            spot=400.0, short_strike=395.0, long_strike=390.0,
            time_to_expiry=0.1, risk_free_rate=0.05, volatility=0.20,
            option_type=OptionType.PUT,
        )
        assert result is None

    @pytest.mark.skipif(not QUANTLIB_AVAILABLE, reason="QuantLib required")
    def test_spread_returns_dict(self):
        result = self.libs.price_spread(
            spot=400.0, short_strike=395.0, long_strike=390.0,
            time_to_expiry=0.1, risk_free_rate=0.05, volatility=0.20,
            option_type=OptionType.PUT,
        )
        assert result is not None
        assert isinstance(result, dict)

    @pytest.mark.skipif(not QUANTLIB_AVAILABLE, reason="QuantLib required")
    def test_spread_has_expected_keys(self):
        result = self.libs.price_spread(
            spot=400.0, short_strike=395.0, long_strike=390.0,
            time_to_expiry=0.1, risk_free_rate=0.05, volatility=0.20,
            option_type=OptionType.PUT,
        )
        assert "net_credit" in result
        assert "max_profit" in result
        assert "max_loss" in result
        assert "breakeven" in result

    @pytest.mark.skipif(not QUANTLIB_AVAILABLE, reason="QuantLib required")
    def test_spread_width_correct(self):
        result = self.libs.price_spread(
            spot=400.0, short_strike=395.0, long_strike=390.0,
            time_to_expiry=0.1, risk_free_rate=0.05, volatility=0.20,
            option_type=OptionType.PUT,
        )
        assert result["width"] == pytest.approx(5.0, abs=0.01)


# ==============================================================================
# OPTIMIZE_PORTFOLIO TESTS
# ==============================================================================


class TestOptimizePortfolio:
    """Tests for optimize_portfolio method."""

    def setup_method(self):
        self.libs = _fresh_libs()
        self.returns_df = _make_returns_df(n_assets=3, n_days=120)

    def test_max_sharpe_with_scipy(self):
        if not SCIPY_AVAILABLE:
            pytest.skip("scipy required")
        result = self.libs.optimize_portfolio(self.returns_df, method="max_sharpe")
        # May succeed or return None depending on convergence
        assert result is None or isinstance(result, PortfolioOptimization)

    def test_min_vol_with_scipy(self):
        if not SCIPY_AVAILABLE:
            pytest.skip("scipy required")
        result = self.libs.optimize_portfolio(self.returns_df, method="min_vol")
        assert result is None or isinstance(result, PortfolioOptimization)

    def test_successful_optimization_weights_sum(self):
        if not SCIPY_AVAILABLE:
            pytest.skip("scipy required")
        result = self.libs.optimize_portfolio(self.returns_df, method="max_sharpe")
        if result and result.optimization_success:
            assert abs(sum(result.weights.values()) - 1.0) < 0.01

    def test_successful_optimization_positive_volatility(self):
        if not SCIPY_AVAILABLE:
            pytest.skip("scipy required")
        result = self.libs.optimize_portfolio(self.returns_df, method="min_vol")
        if result and result.optimization_success:
            assert result.expected_volatility >= 0

    def test_optimization_method_name_recorded(self):
        if not SCIPY_AVAILABLE:
            pytest.skip("scipy required")
        result = self.libs.optimize_portfolio(self.returns_df, method="max_sharpe")
        if result and result.optimization_success:
            assert "max_sharpe" in result.optimization_method

    def test_no_quantlib_no_riskfolio_no_scipy(self):
        """When neither riskfolio nor scipy available, returns None."""
        with patch(
            "Spyder.SpyderU_Utilities.SpyderU20_InstitutionalLibraries.RISKFOLIO_AVAILABLE",
            False,
        ), patch(
            "Spyder.SpyderU_Utilities.SpyderU20_InstitutionalLibraries.SCIPY_AVAILABLE",
            False,
        ):
            result = self.libs.optimize_portfolio(self.returns_df)
            assert result is None


# ==============================================================================
# MODULE-LEVEL FUNCTION TESTS
# ==============================================================================


class TestGlobalInstitutionalFunctions:
    """Tests for U20 module-level functions."""

    def setup_method(self):
        reset_institutional_libraries()

    def test_get_institutional_libraries_returns_instance(self):
        result = get_institutional_libraries()
        assert isinstance(result, InstitutionalLibraries)

    def test_get_institutional_libraries_singleton(self):
        lib1 = get_institutional_libraries()
        lib2 = get_institutional_libraries()
        assert lib1 is lib2

    def test_reset_institutional_libraries_clears_singleton(self):
        lib1 = get_institutional_libraries()
        reset_institutional_libraries()
        lib2 = get_institutional_libraries()
        assert lib1 is not lib2

    def test_test_institutional_libraries_returns_bool(self):
        result = run_institutional_libraries_smoke_test()
        assert isinstance(result, bool)

    def test_get_institutional_libraries_after_reset(self):
        reset_institutional_libraries()
        result = get_institutional_libraries()
        assert isinstance(result, InstitutionalLibraries)
        assert result.risk_free_rate == DEFAULT_RISK_FREE_RATE
