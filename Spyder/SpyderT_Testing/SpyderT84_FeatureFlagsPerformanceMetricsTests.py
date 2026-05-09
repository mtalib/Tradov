#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT84_FeatureFlagsPerformanceMetricsTests.py
Purpose: Comprehensive tests for U11 FeatureFlags and U15 PerformanceMetrics

Author: Spyder Test Suite
Year Created: 2026
Last Updated: 2026-03-05 Time: 14:00:00
"""

# ==============================================================================
# BOOTSTRAP
# ==============================================================================
import sys
import os
import types
import importlib.util
import tempfile

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

_u01 = _load("Spyder/Spyder.SpyderU_Utilities/SpyderU01_Logger.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU01_Logger"] = _u01

_u02 = _load("Spyder/Spyder.SpyderU_Utilities/SpyderU02_ErrorHandler.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler"] = _u02

_u11 = _load("Spyder/Spyder.SpyderU_Utilities/SpyderU11_FeatureFlags.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU11_FeatureFlags"] = _u11

_u15 = _load("Spyder/Spyder.SpyderU_Utilities/SpyderU15_PerformanceMetrics.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU15_PerformanceMetrics"] = _u15

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import math
import numpy as np
import pandas as pd
import pytest
from datetime import datetime, timedelta

# ==============================================================================
# U11 IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU11_FeatureFlags import (
    FeatureStatus,
    RolloutStrategy,
    FeatureType,
    FeatureFlag,
    FeatureFlags,
    DEFAULT_FEATURES,
    SPYDERX_FEATURE_FLAGS,
    get_feature_flags,
)

# ==============================================================================
# U15 IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU15_PerformanceMetrics import (
    PerformanceRating,
    MetricType,
    PerformanceReport,
    DrawdownInfo,
    PerformanceCalculator,
    TRADING_DAYS_PER_YEAR,
    RISK_FREE_RATE,
    MIN_PERIODS_FOR_CALCULATION,
    calculate_sharpe_ratio,
    calculate_max_drawdown,
    generate_performance_report,
    get_performance_calculator,
    calculate_metrics,
)


# ==============================================================================
# HELPERS
# ==============================================================================
def _make_feature_flags(tmpdir=None):
    """Create a FeatureFlags instance using a temp config file."""
    if tmpdir is None:
        tmpdir = tempfile.mkdtemp()
    config_path = os.path.join(tmpdir, "config", "feature_flags.json")
    return FeatureFlags(config_file=config_path)


def _make_returns(n=50, mean=0.001, std=0.02, seed=42):
    """Create a pd.Series of n random daily returns."""
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(mean, std, n))


def _make_positive_returns(n=50):
    """All-positive returns for edge-case tests."""
    return pd.Series([0.01] * n)


def _make_negative_returns(n=50):
    """All-negative returns for edge-case tests."""
    return pd.Series([-0.01] * n)


# ==============================================================================
# ═════════════════════════════════════════════════════════════════════════════
#  U11 — FEATURE FLAGS
# ═════════════════════════════════════════════════════════════════════════════
# ==============================================================================

class TestU11Enums:
    def test_feature_status_values(self):
        assert FeatureStatus.ENABLED.value == "enabled"
        assert FeatureStatus.DISABLED.value == "disabled"
        assert FeatureStatus.TESTING.value == "testing"
        assert FeatureStatus.ROLLOUT.value == "rollout"
        assert FeatureStatus.DEPRECATED.value == "deprecated"

    def test_rollout_strategy_values(self):
        assert RolloutStrategy.ALL.value == "all"
        assert RolloutStrategy.PERCENTAGE.value == "percentage"
        assert RolloutStrategy.USER_LIST.value == "user_list"
        assert RolloutStrategy.CANARY.value == "canary"
        assert RolloutStrategy.GRADUAL.value == "gradual"

    def test_feature_type_values(self):
        assert FeatureType.CORE.value == "core"
        assert FeatureType.STRATEGY.value == "strategy"
        assert FeatureType.ANALYTICS.value == "analytics"
        assert FeatureType.UI.value == "ui"
        assert FeatureType.EXPERIMENTAL.value == "experimental"
        assert FeatureType.INTEGRATION.value == "integration"


class TestU11FeatureFlag:
    def _make(self, **kwargs):
        defaults = dict(
            name="test_feature",
            enabled=True,
            status=FeatureStatus.ENABLED,
            type=FeatureType.CORE,
        )
        defaults.update(kwargs)
        return FeatureFlag(**defaults)

    def test_basic_creation(self):
        ff = self._make()
        assert ff.name == "test_feature"
        assert ff.enabled is True
        assert ff.rollout_percentage == 100.0

    def test_empty_name_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            FeatureFlag(name="", enabled=True, status=FeatureStatus.ENABLED, type=FeatureType.CORE)

    def test_invalid_rollout_pct_raises(self):
        with pytest.raises(ValueError, match="Rollout percentage"):
            FeatureFlag(
                name="x", enabled=True, status=FeatureStatus.ENABLED,
                type=FeatureType.CORE, rollout_percentage=101
            )

    def test_is_expired_no_date(self):
        ff = self._make()
        assert ff.is_expired() is False

    def test_is_expired_past_date(self):
        ff = self._make(expires_date=datetime.now() - timedelta(days=1))
        assert ff.is_expired() is True

    def test_is_expired_future_date(self):
        ff = self._make(expires_date=datetime.now() + timedelta(days=30))
        assert ff.is_expired() is False

    def test_is_enabled_for_user_disabled(self):
        ff = self._make(enabled=False)
        assert ff.is_enabled_for_user("user1") is False

    def test_is_enabled_for_user_all_strategy(self):
        ff = self._make(enabled=True, rollout_strategy=RolloutStrategy.ALL)
        assert ff.is_enabled_for_user("anyone") is True

    def test_is_enabled_for_user_user_list_match(self):
        ff = self._make(
            enabled=True,
            rollout_strategy=RolloutStrategy.USER_LIST,
            enabled_users=["alice", "bob"],
        )
        assert ff.is_enabled_for_user("alice") is True
        assert ff.is_enabled_for_user("charlie") is False

    def test_is_enabled_for_user_percentage_consistent(self):
        ff = self._make(
            enabled=True,
            rollout_strategy=RolloutStrategy.PERCENTAGE,
            rollout_percentage=50.0,
        )
        # Same user should get same result every time
        result1 = ff.is_enabled_for_user("user_xyz")
        result2 = ff.is_enabled_for_user("user_xyz")
        assert result1 == result2

    def test_to_dict(self):
        ff = self._make(description="Test description")
        d = ff.to_dict()
        assert d["name"] == "test_feature"
        assert d["enabled"] is True
        assert d["description"] == "Test description"
        assert "status" in d
        assert "type" in d

    def test_is_enabled_for_user_expired(self):
        ff = self._make(enabled=True, expires_date=datetime.now() - timedelta(hours=1))
        assert ff.is_enabled_for_user("user1") is False


class TestU11FeatureFlags:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.flags = _make_feature_flags(self.tmpdir)

    def test_init_creates_features(self):
        assert len(self.flags.features) > 0

    def test_init_loads_default_features(self):
        for key in DEFAULT_FEATURES:
            assert key in self.flags.features

    def test_is_enabled_known_feature(self):
        # "advanced_risk_management" is True by default
        result = self.flags.is_enabled("advanced_risk_management")
        assert isinstance(result, bool)

    def test_is_enabled_unknown_feature_returns_false(self):
        result = self.flags.is_enabled("no_such_feature_xyz")
        assert result is False

    def test_check_feature_enabled_alias(self):
        r1 = self.flags.is_enabled("alert_notifications")
        r2 = self.flags.check_feature_enabled("alert_notifications")
        assert r1 == r2

    def test_enable_feature_existing(self):
        # Disable first
        self.flags.disable_feature("alert_notifications", save=False)
        assert self.flags.is_enabled("alert_notifications") is False
        # Re-enable
        result = self.flags.enable_feature("alert_notifications", save=False)
        assert result is True
        assert self.flags.is_enabled("alert_notifications") is True

    def test_enable_feature_new(self):
        result = self.flags.enable_feature("brand_new_feature_xyz", save=False)
        assert result is True
        assert "brand_new_feature_xyz" in self.flags.features
        assert self.flags.features["brand_new_feature_xyz"].enabled is True

    def test_disable_feature_existing(self):
        # Enable first
        self.flags.enable_feature("advanced_risk_management", save=False)
        result = self.flags.disable_feature("advanced_risk_management", save=False)
        assert result is True
        assert self.flags.is_enabled("advanced_risk_management") is False

    def test_disable_feature_unknown_returns_false(self):
        result = self.flags.disable_feature("nonexistent_xyz", save=False)
        assert result is False

    def test_set_rollout_percentage(self):
        self.flags.enable_feature("iron_condor_automation", save=False)
        result = self.flags.set_rollout_percentage("iron_condor_automation", 50.0, save=False)
        assert result is True
        assert self.flags.features["iron_condor_automation"].rollout_percentage == 50.0

    def test_set_rollout_percentage_invalid(self):
        result = self.flags.set_rollout_percentage("iron_condor_automation", 150.0, save=False)
        assert result is False

    def test_set_rollout_percentage_unknown(self):
        result = self.flags.set_rollout_percentage("no_such_feat", 25.0, save=False)
        assert result is False

    def test_create_feature_new(self):
        result = self.flags.create_feature("my_new_feature", enabled=True, description="Test")
        assert result is True
        assert "my_new_feature" in self.flags.features
        assert self.flags.features["my_new_feature"].enabled is True

    def test_create_feature_duplicate_returns_false(self):
        self.flags.create_feature("dup_feature", enabled=False)
        result = self.flags.create_feature("dup_feature", enabled=True)
        assert result is False

    def test_get_feature_info_known(self):
        info = self.flags.get_feature_info("advanced_risk_management")
        assert info is not None
        assert info["name"] == "advanced_risk_management"
        assert "enabled" in info
        assert "status" in info

    def test_get_feature_info_unknown_returns_none(self):
        info = self.flags.get_feature_info("unknown_xyz")
        assert info is None

    def test_list_features_all(self):
        features = self.flags.list_features()
        assert isinstance(features, list)
        assert len(features) == len(self.flags.features)
        # Should be sorted by name
        names = [f["name"] for f in features]
        assert names == sorted(names)

    def test_list_features_by_type(self):
        features = self.flags.list_features(feature_type=FeatureType.CORE)
        for f in features:
            assert f["type"] == FeatureType.CORE.value

    def test_get_enabled_features(self):
        enabled = self.flags.get_enabled_features()
        assert isinstance(enabled, list)
        for name in enabled:
            assert self.flags.is_enabled(name) is True

    def test_feature_with_dependency_enabled(self):
        # Create a dep feature and a feature that depends on it
        self.flags.create_feature("base_feat", enabled=True)
        self.flags.features["dependent_feat"] = FeatureFlag(
            name="dependent_feat",
            enabled=True,
            status=FeatureStatus.ENABLED,
            type=FeatureType.CORE,
            dependencies=["base_feat"],
        )
        assert self.flags.is_enabled("dependent_feat") is True

    def test_feature_with_dependency_disabled(self):
        self.flags.create_feature("dep_off", enabled=False)
        self.flags.features["dep_child"] = FeatureFlag(
            name="dep_child",
            enabled=True,
            status=FeatureStatus.ENABLED,
            type=FeatureType.CORE,
            dependencies=["dep_off"],
        )
        assert self.flags.is_enabled("dep_child") is False


class TestU11ModuleFunctions:
    def setup_method(self):
        _u11._feature_flags_instance = None

    def test_get_feature_flags_returns_instance(self):
        inst = _make_feature_flags()
        _u11._feature_flags_instance = inst
        result = get_feature_flags()
        assert isinstance(result, FeatureFlags)

    def test_spyderx_feature_flags_dict(self):
        assert isinstance(SPYDERX_FEATURE_FLAGS, dict)
        for val in SPYDERX_FEATURE_FLAGS.values():
            assert isinstance(val, bool)

    def test_default_features_dict(self):
        assert isinstance(DEFAULT_FEATURES, dict)
        for name, val in DEFAULT_FEATURES.items():
            assert isinstance(name, str)
            assert isinstance(val, bool)


# ==============================================================================
# ═════════════════════════════════════════════════════════════════════════════
#  U15 — PERFORMANCE METRICS
# ═════════════════════════════════════════════════════════════════════════════
# ==============================================================================

class TestU15Enums:
    def test_performance_rating_values(self):
        assert PerformanceRating.EXCELLENT.value == "excellent"
        assert PerformanceRating.GOOD.value == "good"
        assert PerformanceRating.AVERAGE.value == "average"
        assert PerformanceRating.POOR.value == "poor"
        assert PerformanceRating.VERY_POOR.value == "very_poor"

    def test_metric_type_values(self):
        assert MetricType.RETURN.value == "return"
        assert MetricType.RISK.value == "risk"
        assert MetricType.RATIO.value == "ratio"
        assert MetricType.DRAWDOWN.value == "drawdown"
        assert MetricType.VOLATILITY.value == "volatility"


class TestU15PerformanceReport:
    def test_to_dict(self):
        report = PerformanceReport(
            total_return=0.15,
            annualized_return=0.12,
            volatility=0.2,
            sharpe_ratio=1.5,
            sortino_ratio=2.0,
            calmar_ratio=0.8,
            max_drawdown=-0.1,
            max_drawdown_duration=5,
            win_rate=55.0,
            profit_factor=1.5,
            avg_win=0.02,
            avg_loss=-0.01,
            largest_win=0.05,
            largest_loss=-0.04,
            total_trades=50,
            winning_trades=28,
            losing_trades=22,
            rating=PerformanceRating.GOOD,
        )
        d = report.to_dict()
        assert d["total_return"] == 0.15
        assert d["sharpe_ratio"] == 1.5
        assert d["rating"] == "good"

    def test_drawdown_info_creation(self):
        dd = DrawdownInfo(max_drawdown=-0.1, max_drawdown_duration=5, recovery_time=3, drawdown_periods=[])
        assert dd.max_drawdown == -0.1
        assert dd.max_drawdown_duration == 5


class TestU15Constants:
    def test_trading_days(self):
        assert TRADING_DAYS_PER_YEAR == 252

    def test_min_periods(self):
        assert MIN_PERIODS_FOR_CALCULATION == 30

    def test_risk_free_rate_reasonable(self):
        assert 0.0 < RISK_FREE_RATE < 0.20  # between 0 and 20%


class TestU15CalculatorInit:
    def test_default_init(self):
        calc = PerformanceCalculator()
        assert calc.risk_free_rate == RISK_FREE_RATE

    def test_custom_risk_free_rate(self):
        calc = PerformanceCalculator(risk_free_rate=0.05)
        assert calc.risk_free_rate == 0.05


class TestU15TotalReturn:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_total_return_positive(self):
        returns = pd.Series([0.01, 0.02, 0.01, 0.03])
        result = self.calc.calculate_total_return(returns)
        assert result > 0

    def test_total_return_empty(self):
        result = self.calc.calculate_total_return(pd.Series([]))
        assert result == 0.0

    def test_total_return_all_negative(self):
        returns = pd.Series([-0.01, -0.02, -0.01])
        result = self.calc.calculate_total_return(returns)
        assert result < 0

    def test_total_return_zero_returns(self):
        returns = pd.Series([0.0, 0.0, 0.0])
        result = self.calc.calculate_total_return(returns)
        assert abs(result) < 1e-10

    def test_total_return_compound(self):
        # 10% and then -10%: net slightly negative
        returns = pd.Series([0.10, -0.10])
        result = self.calc.calculate_total_return(returns)
        assert abs(result - (-0.01)) < 1e-6


class TestU15AnnualizedReturn:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_annualized_return_empty(self):
        result = self.calc.calculate_annualized_return(pd.Series([]))
        assert result == 0.0

    def test_annualized_return_positive(self):
        returns = _make_returns(252, mean=0.003, std=0.01)
        result = self.calc.calculate_annualized_return(returns)
        assert result > 0

    def test_annualized_return_consistent_positive(self):
        # 1% per day: annualized should be very positive
        returns = pd.Series([0.01] * 252)
        result = self.calc.calculate_annualized_return(returns)
        assert result > 10.0  # Very high annualized return


class TestU15Volatility:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_volatility_empty_or_one(self):
        assert self.calc.calculate_volatility(pd.Series([])) == 0.0
        assert self.calc.calculate_volatility(pd.Series([0.01])) == 0.0

    def test_volatility_positive(self):
        returns = _make_returns(100)
        result = self.calc.calculate_volatility(returns)
        assert result > 0

    def test_volatility_constant_returns_zero(self):
        returns = pd.Series([0.01] * 50)
        result = self.calc.calculate_volatility(returns)
        assert abs(result) < 1e-10  # floating-point near-zero

    def test_volatility_annualized_scaling(self):
        daily_std = 0.02
        returns = pd.Series(np.random.default_rng(42).normal(0, daily_std, 252))
        vol = self.calc.calculate_volatility(returns)
        # Should be approximately daily_std * sqrt(252) ≈ 0.317
        expected_approx = daily_std * math.sqrt(252)
        assert abs(vol - expected_approx) < 0.05


class TestU15SharpeRatio:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_sharpe_too_few_periods(self):
        returns = _make_returns(20)
        result = self.calc.calculate_sharpe_ratio(returns)
        assert result == 0.0

    def test_sharpe_positive_for_good_returns(self):
        returns = _make_returns(50, mean=0.005, std=0.01)
        result = self.calc.calculate_sharpe_ratio(returns)
        assert result > 0

    def test_sharpe_returns_float(self):
        returns = _make_returns(50)
        result = self.calc.calculate_sharpe_ratio(returns)
        assert isinstance(result, float)

    def test_sharpe_zero_std_returns_zero(self):
        # All exactly same returns → std=0 → 0.0
        rfr_daily = RISK_FREE_RATE / TRADING_DAYS_PER_YEAR
        returns = pd.Series([rfr_daily] * 50)  # excess returns have std=0
        result = self.calc.calculate_sharpe_ratio(returns)
        assert result == 0.0


class TestU15SortinoRatio:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_sortino_too_few_periods(self):
        returns = _make_returns(20)
        result = self.calc.calculate_sortino_ratio(returns)
        assert result == 0.0

    def test_sortino_all_positive_returns_inf(self):
        # No downside returns → inf
        returns = _make_positive_returns(50)
        result = self.calc.calculate_sortino_ratio(returns)
        assert math.isinf(result) or result > 100

    def test_sortino_returns_float(self):
        returns = _make_returns(50)
        result = self.calc.calculate_sortino_ratio(returns)
        assert isinstance(result, float)


class TestU15CalmarRatio:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_calmar_too_few_periods(self):
        returns = _make_returns(20)
        result = self.calc.calculate_calmar_ratio(returns)
        assert result == 0.0

    def test_calmar_returns_float(self):
        returns = _make_returns(50)
        result = self.calc.calculate_calmar_ratio(returns)
        assert isinstance(result, float)

    def test_calmar_no_drawdown_returns_inf_or_large(self):
        # All-positive: max_drawdown=0 → inf if positive annualized return
        returns = _make_positive_returns(50)
        result = self.calc.calculate_calmar_ratio(returns)
        assert math.isinf(result) or result > 1.0


class TestU15MaxDrawdown:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_max_drawdown_empty(self):
        result = self.calc.calculate_max_drawdown(pd.Series([]))
        assert result == 0.0

    def test_max_drawdown_monotone_down(self):
        # Cumulative returns going from 0.1 down to 0
        cumulative = pd.Series([0.10, 0.08, 0.05, 0.02, 0.0])
        result = self.calc.calculate_max_drawdown(cumulative)
        assert result < 0

    def test_max_drawdown_monotone_up(self):
        # Always rising → 0 drawdown
        cumulative = pd.Series([0.01, 0.02, 0.03, 0.04, 0.05])
        result = self.calc.calculate_max_drawdown(cumulative)
        assert result == 0.0

    def test_max_drawdown_known_value(self):
        # Rise to 2 then fall to 1 → drawdown of (1-2)/2 = -0.5
        cumulative = pd.Series([1.0, 2.0, 1.0])
        result = self.calc.calculate_max_drawdown(cumulative)
        assert abs(result - (-0.5)) < 1e-6

    def test_max_drawdown_negative_value(self):
        returns = _make_returns(100, mean=-0.001)
        cumulative = (1 + returns).cumprod() - 1
        result = self.calc.calculate_max_drawdown(cumulative)
        assert result <= 0


class TestU15AnalyzeDrawdowns:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_analyze_drawdowns_empty(self):
        result = self.calc.analyze_drawdowns(pd.Series([]))
        assert isinstance(result, DrawdownInfo)
        assert result.max_drawdown == 0.0

    def test_analyze_drawdowns_structure(self):
        cumulative = pd.Series([0.01, 0.02, 0.015, 0.03, 0.025, 0.04])
        result = self.calc.analyze_drawdowns(cumulative)
        assert isinstance(result.max_drawdown, float)
        assert isinstance(result.max_drawdown_duration, int)
        assert isinstance(result.drawdown_periods, list)

    def test_analyze_drawdowns_monotone_up(self):
        cumulative = pd.Series([0.01, 0.02, 0.03, 0.04])
        result = self.calc.analyze_drawdowns(cumulative)
        assert result.max_drawdown == 0.0
        assert result.drawdown_periods == []


class TestU15WinRate:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_win_rate_empty(self):
        assert self.calc.calculate_win_rate(pd.Series([])) == 0.0

    def test_win_rate_all_positive(self):
        assert self.calc.calculate_win_rate(pd.Series([0.01, 0.02, 0.03])) == 100.0

    def test_win_rate_all_negative(self):
        assert self.calc.calculate_win_rate(pd.Series([-0.01, -0.02])) == 0.0

    def test_win_rate_half(self):
        returns = pd.Series([0.01, -0.01, 0.02, -0.02])
        result = self.calc.calculate_win_rate(returns)
        assert abs(result - 50.0) < 1e-6

    def test_win_rate_range(self):
        returns = _make_returns(100)
        result = self.calc.calculate_win_rate(returns)
        assert 0.0 <= result <= 100.0


class TestU15ProfitFactor:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_profit_factor_empty(self):
        assert self.calc.calculate_profit_factor(pd.Series([])) == 0.0

    def test_profit_factor_all_positive(self):
        result = self.calc.calculate_profit_factor(pd.Series([0.01, 0.02]))
        assert math.isinf(result)

    def test_profit_factor_all_negative(self):
        result = self.calc.calculate_profit_factor(pd.Series([-0.01, -0.02]))
        assert result == 0.0

    def test_profit_factor_balanced(self):
        # Same gains and losses → profit factor = 1.0
        returns = pd.Series([0.10, -0.10, 0.20, -0.20])
        result = self.calc.calculate_profit_factor(returns)
        assert abs(result - 1.0) < 1e-6

    def test_profit_factor_positive(self):
        returns = pd.Series([0.02, 0.02, 0.02, -0.01])
        result = self.calc.calculate_profit_factor(returns)
        assert result > 1.0


class TestU15TradeStatistics:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_trade_stats_empty_keys(self):
        result = self.calc.calculate_trade_statistics(pd.Series([]))
        assert result["total_trades"] == 0
        assert result["winning_trades"] == 0

    def test_trade_stats_all_positive(self):
        returns = pd.Series([0.01, 0.02, 0.03])
        result = self.calc.calculate_trade_statistics(returns)
        assert result["total_trades"] == 3
        assert result["winning_trades"] == 3
        assert result["losing_trades"] == 0
        assert result["avg_loss"] == 0.0

    def test_trade_stats_all_negative(self):
        returns = pd.Series([-0.01, -0.02, -0.03])
        result = self.calc.calculate_trade_statistics(returns)
        assert result["winning_trades"] == 0
        assert result["losing_trades"] == 3
        assert result["avg_win"] == 0.0

    def test_trade_stats_mixed(self):
        returns = pd.Series([0.03, -0.01, 0.02, -0.01])
        result = self.calc.calculate_trade_statistics(returns)
        assert result["total_trades"] == 4
        assert result["winning_trades"] == 2
        assert result["losing_trades"] == 2
        assert result["avg_win"] > 0
        assert result["avg_loss"] < 0
        assert result["largest_win"] == pytest.approx(0.03)
        assert result["largest_loss"] == pytest.approx(-0.01)


class TestU15PerformanceRating:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_rate_excellent(self):
        # High sharpe, high calmar, high win rate
        rating = self.calc.rate_performance(sharpe_ratio=3.0, calmar_ratio=2.0, win_rate=65.0)
        assert rating == PerformanceRating.EXCELLENT

    def test_rate_very_poor(self):
        rating = self.calc.rate_performance(sharpe_ratio=0.1, calmar_ratio=0.1, win_rate=30.0)
        assert rating == PerformanceRating.VERY_POOR

    def test_rate_good(self):
        rating = self.calc.rate_performance(sharpe_ratio=1.5, calmar_ratio=0.8, win_rate=55.0)
        assert rating in (PerformanceRating.GOOD, PerformanceRating.EXCELLENT)

    def test_rating_returns_enum(self):
        result = self.calc.rate_performance(1.0, 0.5, 50.0)
        assert isinstance(result, PerformanceRating)


class TestU15GenerateReport:
    def setup_method(self):
        self.calc = PerformanceCalculator()
        np.random.seed(42)
        self.returns = _make_returns(252, mean=0.001, std=0.015)

    def test_report_is_performance_report(self):
        report = self.calc.generate_performance_report(self.returns)
        assert isinstance(report, PerformanceReport)

    def test_report_fields_populated(self):
        report = self.calc.generate_performance_report(self.returns)
        assert report.total_trades == len(self.returns)
        assert report.volatility > 0
        assert isinstance(report.rating, PerformanceRating)

    def test_report_to_dict(self):
        report = self.calc.generate_performance_report(self.returns)
        d = report.to_dict()
        assert "total_return" in d
        assert "sharpe_ratio" in d
        assert "rating" in d

    def test_report_empty_returns(self):
        report = self.calc.generate_performance_report(pd.Series([]))
        assert isinstance(report, PerformanceReport)
        assert report.total_return == 0.0

    def test_report_win_rate_in_range(self):
        report = self.calc.generate_performance_report(self.returns)
        assert 0.0 <= report.win_rate <= 100.0

    def test_report_max_drawdown_nonpositive(self):
        report = self.calc.generate_performance_report(self.returns)
        assert report.max_drawdown <= 0


class TestU15ModuleFunctions:
    def setup_method(self):
        _u15._performance_calculator_instance = None

    def test_calculate_sharpe_ratio_module_fn(self):
        returns = _make_returns(50, mean=0.005)
        result = calculate_sharpe_ratio(returns)
        assert isinstance(result, float)

    def test_calculate_max_drawdown_module_fn(self):
        cumulative = pd.Series([0.01, 0.02, 0.015, 0.03])
        result = calculate_max_drawdown(cumulative)
        assert isinstance(result, float)

    def test_generate_performance_report_module_fn(self):
        returns = _make_returns(50)
        result = generate_performance_report(returns)
        assert isinstance(result, PerformanceReport)

    def test_get_performance_calculator_singleton(self):
        c1 = get_performance_calculator()
        c2 = get_performance_calculator()
        assert c1 is c2

    def test_calculate_metrics_returns_dict(self):
        result = calculate_metrics()
        assert isinstance(result, dict)
        assert "sharpe_ratio" in result
        assert "max_drawdown" in result
        assert "win_rate" in result
        assert "profit_factor" in result
