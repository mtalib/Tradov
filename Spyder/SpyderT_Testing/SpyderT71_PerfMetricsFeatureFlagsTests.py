#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT71_PerfMetricsFeatureFlagsTests.py
Purpose: Tests for U15 PerformanceMetrics and U11 FeatureFlags

Author: Spyder Test Suite
Year Created: 2026
Last Updated: 2026-03-04 Time: 20:00:00
"""

# ==============================================================================
# BOOTSTRAP — load modules without installing Spyder as a package
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

_u01 = _load("Spyder/Spyder.SpyderU_Utilities/SpyderU01_Logger.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU01_Logger"] = _u01

_u02 = _load("Spyder/Spyder.SpyderU_Utilities/SpyderU02_ErrorHandler.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler"] = _u02

_u15 = _load("Spyder/Spyder.SpyderU_Utilities/SpyderU15_PerformanceMetrics.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU15_PerformanceMetrics"] = _u15

_u11 = _load("Spyder/Spyder.SpyderU_Utilities/SpyderU11_FeatureFlags.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU11_FeatureFlags"] = _u11

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import math
import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# ==============================================================================
# MODULE IMPORTS — U15
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU15_PerformanceMetrics import (
    PerformanceRating,
    MetricType,
    PerformanceReport,
    DrawdownInfo,
    PerformanceCalculator,
    calculate_sharpe_ratio,
    calculate_max_drawdown,
    generate_performance_report,
    get_performance_calculator,
    RISK_FREE_RATE,
    TRADING_DAYS_PER_YEAR,
    MIN_PERIODS_FOR_CALCULATION,
    EXCELLENT_SHARPE,
    GOOD_SHARPE,
    POOR_SHARPE,
)

# ==============================================================================
# MODULE IMPORTS — U11
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU11_FeatureFlags import (
    FeatureStatus,
    RolloutStrategy,
    FeatureType,
    FeatureFlag,
    FeatureFlags,
    check_feature_enabled,
    is_feature_enabled,
    enable_feature,
    disable_feature,
    get_feature_flags,
)

# ==============================================================================
# HELPERS
# ==============================================================================
def _make_returns(n=60, mean=0.001, std=0.01, seed=42):
    """Generate a reproducible pd.Series of daily returns."""
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(mean, std, n))


def _all_positive_returns(n=60):
    return pd.Series([0.005] * n)


def _mixed_returns():
    """Mix of wins and losses — 36 positive, 24 negative."""
    pos = [0.01] * 36
    neg = [-0.005] * 24
    return pd.Series(pos + neg)


def _declining_returns(n=60):
    """Steadily falling returns."""
    return pd.Series([-0.005] * n)


# ==============================================================================
# U15 — ENUM TESTS
# ==============================================================================
class TestPerformanceRatingEnum:
    def test_excellent_value(self):
        assert PerformanceRating.EXCELLENT.value == "excellent"

    def test_good_value(self):
        assert PerformanceRating.GOOD.value == "good"

    def test_very_poor_value(self):
        assert PerformanceRating.VERY_POOR.value == "very_poor"

    def test_five_members(self):
        assert len(list(PerformanceRating)) == 5


class TestMetricTypeEnum:
    def test_return_value(self):
        assert MetricType.RETURN.value == "return"

    def test_risk_value(self):
        assert MetricType.RISK.value == "risk"

    def test_ratio_value(self):
        assert MetricType.RATIO.value == "ratio"

    def test_drawdown_value(self):
        assert MetricType.DRAWDOWN.value == "drawdown"

    def test_volatility_value(self):
        assert MetricType.VOLATILITY.value == "volatility"


# ==============================================================================
# U15 — PerformanceReport TESTS
# ==============================================================================
class TestPerformanceReport:
    def _make_report(self, **kwargs):
        defaults = dict(
            total_return=0.10, annualized_return=0.12, volatility=0.15,
            sharpe_ratio=1.5, sortino_ratio=2.0, calmar_ratio=0.8,
            max_drawdown=-0.05, max_drawdown_duration=10, win_rate=55.0,
            profit_factor=1.3, avg_win=0.008, avg_loss=-0.004,
            largest_win=0.05, largest_loss=-0.03, total_trades=100,
            winning_trades=55, losing_trades=45, rating=PerformanceRating.GOOD,
        )
        defaults.update(kwargs)
        return PerformanceReport(**defaults)

    def test_basic_creation(self):
        rpt = self._make_report()
        assert rpt.sharpe_ratio == 1.5
        assert rpt.total_trades == 100

    def test_to_dict_contains_all_keys(self):
        rpt = self._make_report()
        d = rpt.to_dict()
        for key in ("total_return", "annualized_return", "volatility", "sharpe_ratio",
                    "sortino_ratio", "calmar_ratio", "max_drawdown", "win_rate",
                    "profit_factor", "avg_win", "avg_loss", "largest_win", "largest_loss",
                    "total_trades", "winning_trades", "losing_trades", "rating"):
            assert key in d

    def test_to_dict_rating_is_string(self):
        rpt = self._make_report(rating=PerformanceRating.EXCELLENT)
        d = rpt.to_dict()
        assert d["rating"] == "excellent"


# ==============================================================================
# U15 — DrawdownInfo TESTS
# ==============================================================================
class TestDrawdownInfo:
    def test_basic_creation(self):
        dd = DrawdownInfo(max_drawdown=-0.1, max_drawdown_duration=5,
                          recovery_time=10, drawdown_periods=[(0, 4, -0.1)])
        assert dd.max_drawdown == -0.1
        assert dd.max_drawdown_duration == 5

    def test_empty_periods(self):
        dd = DrawdownInfo(max_drawdown=0.0, max_drawdown_duration=0,
                          recovery_time=0, drawdown_periods=[])
        assert dd.drawdown_periods == []


# ==============================================================================
# U15 — PerformanceCalculator.calculate_total_return TESTS
# ==============================================================================
class TestCalculateTotalReturn:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_empty_series(self):
        assert self.calc.calculate_total_return(pd.Series([], dtype=float)) == 0.0

    def test_all_positive(self):
        r = pd.Series([0.01, 0.01, 0.01])
        result = self.calc.calculate_total_return(r)
        expected = (1.01 ** 3) - 1
        assert result == pytest.approx(expected, rel=1e-6)

    def test_mixed_returns_loses_overall(self):
        r = pd.Series([0.05, -0.10])  # 1.05 * 0.90 - 1 = -0.055
        result = self.calc.calculate_total_return(r)
        assert result < 0

    def test_single_return(self):
        r = pd.Series([0.03])
        assert self.calc.calculate_total_return(r) == pytest.approx(0.03, rel=1e-6)

    def test_returns_float(self):
        r = _make_returns()
        assert isinstance(self.calc.calculate_total_return(r), float)


# ==============================================================================
# U15 — PerformanceCalculator.calculate_annualized_return TESTS
# ==============================================================================
class TestCalculateAnnualizedReturn:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_empty_series(self):
        assert self.calc.calculate_annualized_return(pd.Series([], dtype=float)) == 0.0

    def test_long_series_positive(self):
        r = _all_positive_returns(n=252)
        result = self.calc.calculate_annualized_return(r, periods_per_year=252)
        assert result > 0

    def test_returns_float(self):
        r = _make_returns()
        result = self.calc.calculate_annualized_return(r)
        assert isinstance(result, float)

    def test_single_period(self):
        r = pd.Series([0.05])
        # Only 1 period — result != 0 (1/252th of a year)
        result = self.calc.calculate_annualized_return(r)
        assert isinstance(result, float)


# ==============================================================================
# U15 — PerformanceCalculator.calculate_volatility TESTS
# ==============================================================================
class TestCalculateVolatility:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_empty_series(self):
        assert self.calc.calculate_volatility(pd.Series([], dtype=float)) == 0.0

    def test_single_element(self):
        assert self.calc.calculate_volatility(pd.Series([0.01])) == 0.0

    def test_constant_returns_zero_vol(self):
        r = pd.Series([0.01] * 10)
        assert self.calc.calculate_volatility(r) == pytest.approx(0.0, abs=1e-10)

    def test_positive_for_varying_returns(self):
        r = _make_returns(n=100)
        assert self.calc.calculate_volatility(r) > 0

    def test_annualised_by_sqrt_periods(self):
        r = _make_returns(n=100, std=0.01)
        vol = self.calc.calculate_volatility(r, TRADING_DAYS_PER_YEAR)
        # Approx 0.01 * sqrt(252) ≈ 0.1587
        assert 0.05 < vol < 0.5


# ==============================================================================
# U15 — PerformanceCalculator.calculate_sharpe_ratio TESTS
# ==============================================================================
class TestCalculateSharpeRatio:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_too_few_periods(self):
        r = pd.Series([0.01] * 5)  # Less than MIN_PERIODS_FOR_CALCULATION
        assert self.calc.calculate_sharpe_ratio(r) == 0.0

    def test_constant_excess_returns_zero_std(self):
        # Same excess return each day → std = 0 → Sharpe = 0
        daily_rf = RISK_FREE_RATE / TRADING_DAYS_PER_YEAR
        r = pd.Series([daily_rf] * 50)
        result = self.calc.calculate_sharpe_ratio(r)
        assert result == 0.0

    def test_positive_sharpe_for_good_returns(self):
        r = _all_positive_returns(n=60)
        result = self.calc.calculate_sharpe_ratio(r)
        assert result > 0

    def test_negative_sharpe_for_losing_returns(self):
        r = _declining_returns(n=60)
        result = self.calc.calculate_sharpe_ratio(r)
        assert result < 0

    def test_returns_float(self):
        r = _make_returns(n=60)
        assert isinstance(self.calc.calculate_sharpe_ratio(r), float)


# ==============================================================================
# U15 — PerformanceCalculator.calculate_sortino_ratio TESTS
# ==============================================================================
class TestCalculateSortinoRatio:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_too_few_periods(self):
        r = pd.Series([0.01] * 5)
        assert self.calc.calculate_sortino_ratio(r) == 0.0

    def test_no_downside_returns_inf(self):
        # All returns positive — no downside → + inf
        r = _all_positive_returns(n=60)
        result = self.calc.calculate_sortino_ratio(r)
        assert result == float("inf")

    def test_mixed_returns_positive(self):
        r = _mixed_returns()
        result = self.calc.calculate_sortino_ratio(r)
        assert isinstance(result, float)

    def test_declining_returns_negative(self):
        r = _declining_returns(n=60)
        result = self.calc.calculate_sortino_ratio(r)
        assert result < 0


# ==============================================================================
# U15 — PerformanceCalculator.calculate_calmar_ratio TESTS
# ==============================================================================
class TestCalculateCalmarRatio:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_too_few_periods(self):
        r = pd.Series([0.01] * 5)
        assert self.calc.calculate_calmar_ratio(r) == 0.0

    def test_no_drawdown_positive_returns_inf(self):
        r = _all_positive_returns(n=60)
        result = self.calc.calculate_calmar_ratio(r)
        assert result == float("inf")

    def test_mixed_returns_returns_float(self):
        r = _make_returns(n=60)
        assert isinstance(self.calc.calculate_calmar_ratio(r), float)


# ==============================================================================
# U15 — PerformanceCalculator.calculate_max_drawdown TESTS
# ==============================================================================
class TestCalculateMaxDrawdown:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_empty_series(self):
        assert self.calc.calculate_max_drawdown(pd.Series([], dtype=float)) == 0.0

    def test_monotonically_increasing_no_drawdown(self):
        # Cumulative returns only go up — peak == current → drawdown == 0
        cum = pd.Series([0.01, 0.02, 0.03, 0.05, 0.08])
        result = self.calc.calculate_max_drawdown(cum)
        assert result == pytest.approx(0.0, abs=1e-9)

    def test_drawdown_is_negative(self):
        # Goes up then down
        cum = pd.Series([0.00, 0.05, 0.10, 0.07, 0.04])
        result = self.calc.calculate_max_drawdown(cum)
        assert result < 0

    def test_returns_float(self):
        cum = pd.Series([0.0, 0.05, 0.02, 0.08])
        assert isinstance(self.calc.calculate_max_drawdown(cum), float)


# ==============================================================================
# U15 — PerformanceCalculator.analyze_drawdowns TESTS
# ==============================================================================
class TestAnalyzeDrawdowns:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_empty_series(self):
        dd = self.calc.analyze_drawdowns(pd.Series([], dtype=float))
        assert dd.max_drawdown == 0.0
        assert dd.drawdown_periods == []

    def test_monotonically_increasing_no_periods(self):
        cum = pd.Series([0.00, 0.02, 0.05, 0.09])
        dd = self.calc.analyze_drawdowns(cum)
        assert dd.max_drawdown == pytest.approx(0.0, abs=1e-9)

    def test_detects_drawdown_period(self):
        # Peak at 3rd element, then retreat
        cum = pd.Series([0.00, 0.05, 0.10, 0.08, 0.06, 0.10, 0.12])
        dd = self.calc.analyze_drawdowns(cum)
        assert len(dd.drawdown_periods) >= 1
        assert dd.max_drawdown < 0

    def test_returns_drawdown_info_instance(self):
        cum = pd.Series([0.0, 0.05, 0.03, 0.07])
        dd = self.calc.analyze_drawdowns(cum)
        assert isinstance(dd, DrawdownInfo)

    def test_max_drawdown_duration_nonneg(self):
        cum = pd.Series([0.0, 0.05, 0.02, 0.08])
        dd = self.calc.analyze_drawdowns(cum)
        assert dd.max_drawdown_duration >= 0

    def test_recovery_time_nonneg(self):
        cum = pd.Series([0.0, 0.05, 0.02, 0.08, 0.10])
        dd = self.calc.analyze_drawdowns(cum)
        assert dd.recovery_time >= 0


# ==============================================================================
# U15 — PerformanceCalculator.calculate_win_rate TESTS
# ==============================================================================
class TestCalculateWinRate:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_empty_returns(self):
        assert self.calc.calculate_win_rate(pd.Series([], dtype=float)) == 0.0

    def test_all_positive(self):
        r = pd.Series([0.01, 0.02, 0.03])
        assert self.calc.calculate_win_rate(r) == pytest.approx(100.0)

    def test_all_negative(self):
        r = pd.Series([-0.01, -0.02])
        assert self.calc.calculate_win_rate(r) == pytest.approx(0.0)

    def test_half_positive(self):
        r = pd.Series([0.01, 0.01, -0.01, -0.01])
        assert self.calc.calculate_win_rate(r) == pytest.approx(50.0)

    def test_three_out_of_four(self):
        r = pd.Series([0.01, 0.02, 0.03, -0.01])
        assert self.calc.calculate_win_rate(r) == pytest.approx(75.0)


# ==============================================================================
# U15 — PerformanceCalculator.calculate_profit_factor TESTS
# ==============================================================================
class TestCalculateProfitFactor:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_empty_returns(self):
        assert self.calc.calculate_profit_factor(pd.Series([], dtype=float)) == 0.0

    def test_all_positive_inf(self):
        r = pd.Series([0.01, 0.02, 0.03])
        result = self.calc.calculate_profit_factor(r)
        assert result == float("inf")

    def test_mixed_returns_above_one(self):
        # 3 wins of 0.01, 1 loss of -0.005 → PF = 0.03 / 0.005 = 6
        r = pd.Series([0.01, 0.01, 0.01, -0.005])
        result = self.calc.calculate_profit_factor(r)
        assert result == pytest.approx(6.0, rel=1e-6)

    def test_all_negative_zero(self):
        r = pd.Series([-0.01, -0.02])
        assert self.calc.calculate_profit_factor(r) == 0.0


# ==============================================================================
# U15 — PerformanceCalculator.calculate_trade_statistics TESTS
# ==============================================================================
class TestCalculateTradeStatistics:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_empty_returns_zeroes(self):
        stats = self.calc.calculate_trade_statistics(pd.Series([], dtype=float))
        assert stats["total_trades"] == 0

    def test_counts_are_correct(self):
        r = _mixed_returns()
        stats = self.calc.calculate_trade_statistics(r)
        assert stats["total_trades"] == 60
        assert stats["winning_trades"] == 36
        assert stats["losing_trades"] == 24

    def test_avg_win_positive(self):
        r = _mixed_returns()
        stats = self.calc.calculate_trade_statistics(r)
        assert stats["avg_win"] > 0

    def test_avg_loss_negative(self):
        r = _mixed_returns()
        stats = self.calc.calculate_trade_statistics(r)
        assert stats["avg_loss"] < 0

    def test_largest_win_max_of_positives(self):
        r = pd.Series([0.01, 0.05, -0.02, 0.03])
        stats = self.calc.calculate_trade_statistics(r)
        assert stats["largest_win"] == pytest.approx(0.05)

    def test_largest_loss_min_of_negatives(self):
        r = pd.Series([0.01, -0.05, -0.02, 0.03])
        stats = self.calc.calculate_trade_statistics(r)
        assert stats["largest_loss"] == pytest.approx(-0.05)

    def test_all_positive_no_losses(self):
        r = pd.Series([0.01, 0.02])
        stats = self.calc.calculate_trade_statistics(r)
        assert stats["avg_loss"] == 0.0
        assert stats["largest_loss"] == 0.0

    def test_all_negative_no_wins(self):
        r = pd.Series([-0.01, -0.02])
        stats = self.calc.calculate_trade_statistics(r)
        assert stats["avg_win"] == 0.0
        assert stats["largest_win"] == 0.0


# ==============================================================================
# U15 — PerformanceCalculator.rate_performance TESTS
# ==============================================================================
class TestRatePerformance:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_excellent_rating(self):
        # EXCELLENT_SHARPE >= 2.0, EXCELLENT_CALMAR >= 1.0, win_rate >= 60
        rating = self.calc.rate_performance(
            sharpe_ratio=EXCELLENT_SHARPE + 0.5,
            calmar_ratio=1.5,
            win_rate=65.0,
        )
        assert rating == PerformanceRating.EXCELLENT

    def test_very_poor_rating(self):
        rating = self.calc.rate_performance(
            sharpe_ratio=-1.0, calmar_ratio=-0.5, win_rate=20.0
        )
        assert rating == PerformanceRating.VERY_POOR

    def test_average_rating_mid_scores(self):
        # POOR_SHARPE = 0.5, POOR_CALMAR = 0.25
        rating = self.calc.rate_performance(
            sharpe_ratio=POOR_SHARPE + 0.1,
            calmar_ratio=0.3,
            win_rate=45.0,
        )
        assert rating in (PerformanceRating.POOR, PerformanceRating.AVERAGE)

    def test_returns_performance_rating_instance(self):
        result = self.calc.rate_performance(1.5, 0.6, 55.0)
        assert isinstance(result, PerformanceRating)


# ==============================================================================
# U15 — PerformanceCalculator.generate_performance_report TESTS
# ==============================================================================
class TestGeneratePerformanceReport:
    def setup_method(self):
        self.calc = PerformanceCalculator()

    def test_returns_performance_report(self):
        r = _make_returns(n=60)
        result = self.calc.generate_performance_report(r)
        assert isinstance(result, PerformanceReport)

    def test_total_trades_counted(self):
        r = _mixed_returns()  # 60 returns
        result = self.calc.generate_performance_report(r)
        assert result.total_trades == 60

    def test_winning_losing_trades_sum_to_total(self):
        r = _mixed_returns()
        result = self.calc.generate_performance_report(r)
        assert result.winning_trades + result.losing_trades == result.total_trades

    def test_win_rate_within_range(self):
        r = _mixed_returns()
        result = self.calc.generate_performance_report(r)
        assert 0.0 <= result.win_rate <= 100.0

    def test_max_drawdown_non_positive(self):
        r = _declining_returns(n=60)
        result = self.calc.generate_performance_report(r)
        assert result.max_drawdown <= 0.0

    def test_to_dict_works_on_report(self):
        r = _make_returns(n=60)
        result = self.calc.generate_performance_report(r)
        d = result.to_dict()
        assert "sharpe_ratio" in d
        assert "rating" in d

    def test_rating_is_performance_rating(self):
        r = _make_returns(n=60)
        result = self.calc.generate_performance_report(r)
        assert isinstance(result.rating, PerformanceRating)


# ==============================================================================
# U15 — MODULE-LEVEL FUNCTION TESTS
# ==============================================================================
class TestModuleFunctionCalculateSharpeRatio:
    def test_returns_float(self):
        r = _make_returns(n=60)
        result = calculate_sharpe_ratio(r)
        assert isinstance(result, float)

    def test_empty_series(self):
        result = calculate_sharpe_ratio(pd.Series([], dtype=float))
        assert result == 0.0


class TestModuleFunctionCalculateMaxDrawdown:
    def test_returns_float(self):
        cum = pd.Series([0.0, 0.05, 0.03, 0.08])
        result = calculate_max_drawdown(cum)
        assert isinstance(result, float)

    def test_empty_series(self):
        result = calculate_max_drawdown(pd.Series([], dtype=float))
        assert result == 0.0


class TestModuleFunctionGeneratePerformanceReport:
    def test_returns_performance_report(self):
        r = _make_returns(n=60)
        result = generate_performance_report(r)
        assert isinstance(result, PerformanceReport)


class TestGetPerformanceCalculatorSingleton:
    def test_returns_performance_calculator(self):
        calc = get_performance_calculator()
        assert isinstance(calc, PerformanceCalculator)


# ==============================================================================
# U11 — ENUM TESTS
# ==============================================================================
class TestFeatureStatusEnum:
    def test_enabled_value(self):
        assert FeatureStatus.ENABLED.value == "enabled"

    def test_disabled_value(self):
        assert FeatureStatus.DISABLED.value == "disabled"

    def test_testing_value(self):
        assert FeatureStatus.TESTING.value == "testing"

    def test_rollout_value(self):
        assert FeatureStatus.ROLLOUT.value == "rollout"

    def test_deprecated_value(self):
        assert FeatureStatus.DEPRECATED.value == "deprecated"


class TestRolloutStrategyEnum:
    def test_all_value(self):
        assert RolloutStrategy.ALL.value == "all"

    def test_percentage_value(self):
        assert RolloutStrategy.PERCENTAGE.value == "percentage"

    def test_user_list_value(self):
        assert RolloutStrategy.USER_LIST.value == "user_list"

    def test_canary_value(self):
        assert RolloutStrategy.CANARY.value == "canary"

    def test_gradual_value(self):
        assert RolloutStrategy.GRADUAL.value == "gradual"


class TestFeatureTypeEnum:
    def test_core_value(self):
        assert FeatureType.CORE.value == "core"

    def test_strategy_value(self):
        assert FeatureType.STRATEGY.value == "strategy"

    def test_experimental_value(self):
        assert FeatureType.EXPERIMENTAL.value == "experimental"

    def test_ui_value(self):
        assert FeatureType.UI.value == "ui"


# ==============================================================================
# U11 — FeatureFlag TESTS
# ==============================================================================
def _make_flag(name="test_feature", enabled=True, status=FeatureStatus.ENABLED,
               ftype=FeatureType.EXPERIMENTAL, rollout=100.0,
               strategy=RolloutStrategy.ALL, **kwargs):
    return FeatureFlag(name=name, enabled=enabled, status=status,
                       type=ftype, rollout_percentage=rollout,
                       rollout_strategy=strategy, **kwargs)


class TestFeatureFlagCreation:
    def test_basic_creation(self):
        flag = _make_flag()
        assert flag.name == "test_feature"
        assert flag.enabled is True

    def test_empty_name_raises(self):
        with pytest.raises(ValueError):
            FeatureFlag(name="", enabled=True, status=FeatureStatus.ENABLED,
                        type=FeatureType.EXPERIMENTAL)

    def test_rollout_below_zero_raises(self):
        with pytest.raises(ValueError):
            _make_flag(rollout=-1.0)

    def test_rollout_above_100_raises(self):
        with pytest.raises(ValueError):
            _make_flag(rollout=101.0)

    def test_rollout_exactly_zero_ok(self):
        flag = _make_flag(rollout=0.0)
        assert flag.rollout_percentage == 0.0

    def test_rollout_exactly_100_ok(self):
        flag = _make_flag(rollout=100.0)
        assert flag.rollout_percentage == 100.0

    def test_default_environments(self):
        flag = _make_flag()
        assert "all" in flag.environments


class TestFeatureFlagIsExpired:
    def test_not_expired_when_no_expires_date(self):
        flag = _make_flag()
        assert flag.is_expired() is False

    def test_expired_when_past_date(self):
        flag = _make_flag(expires_date=datetime.now() - timedelta(hours=1))
        assert flag.is_expired() is True

    def test_not_expired_when_future_date(self):
        flag = _make_flag(expires_date=datetime.now() + timedelta(days=30))
        assert flag.is_expired() is False


class TestFeatureFlagIsEnabledForUser:
    def test_disabled_flag_returns_false(self):
        flag = _make_flag(enabled=False)
        assert flag.is_enabled_for_user("user1") is False

    def test_expired_flag_returns_false(self):
        flag = _make_flag(expires_date=datetime.now() - timedelta(hours=1))
        assert flag.is_enabled_for_user("user1") is False

    def test_all_strategy_returns_true(self):
        flag = _make_flag(strategy=RolloutStrategy.ALL)
        assert flag.is_enabled_for_user("any_user") is True

    def test_user_list_strategy_included_user(self):
        flag = _make_flag(strategy=RolloutStrategy.USER_LIST,
                          enabled_users=["alice", "bob"])
        assert flag.is_enabled_for_user("alice") is True

    def test_user_list_strategy_excluded_user(self):
        flag = _make_flag(strategy=RolloutStrategy.USER_LIST,
                          enabled_users=["alice"])
        assert flag.is_enabled_for_user("charlie") is False

    def test_percentage_strategy_deterministic(self):
        flag = _make_flag(strategy=RolloutStrategy.PERCENTAGE, rollout=100.0)
        # 100% rollout — always True
        assert flag.is_enabled_for_user("any_user") is True

    def test_percentage_strategy_zero_rollout(self):
        flag = _make_flag(strategy=RolloutStrategy.PERCENTAGE, rollout=0.0)
        # 0% rollout — always False (hash % 100 + 1 >= 1 > 0)
        assert flag.is_enabled_for_user("some_user") is False

    def test_canary_strategy_falls_through(self):
        # Canary strategy not explicitly handled → falls through to self.enabled
        flag = _make_flag(strategy=RolloutStrategy.CANARY, enabled=True)
        assert flag.is_enabled_for_user("user1") is True


class TestFeatureFlagToDict:
    def test_to_dict_has_required_keys(self):
        flag = _make_flag()
        d = flag.to_dict()
        for key in ("name", "enabled", "status", "type", "description",
                    "rollout_percentage", "rollout_strategy", "enabled_users",
                    "environments", "created_date", "modified_date",
                    "expires_date", "dependencies", "metadata"):
            assert key in d

    def test_expires_date_none_when_not_set(self):
        flag = _make_flag()
        d = flag.to_dict()
        assert d["expires_date"] is None

    def test_expires_date_is_iso_string_when_set(self):
        flag = _make_flag(expires_date=datetime(2026, 12, 31))
        d = flag.to_dict()
        assert isinstance(d["expires_date"], str)
        datetime.fromisoformat(d["expires_date"])

    def test_status_is_string(self):
        flag = _make_flag(status=FeatureStatus.TESTING)
        d = flag.to_dict()
        assert isinstance(d["status"], str)


# ==============================================================================
# U11 — FeatureFlags TESTS
# ==============================================================================
# All FeatureFlags instances are created with a non-existent config file
# so _load_configuration gracefully starts empty.
_NO_CONFIG = "/tmp/nonexistent_spyder_flags_12345.json"


class TestFeatureFlagsInit:
    def test_instantiation(self):
        ff = FeatureFlags(config_file=_NO_CONFIG)
        assert ff is not None

    def test_features_is_dict(self):
        ff = FeatureFlags(config_file=_NO_CONFIG)
        assert isinstance(ff.features, dict)

    def test_has_logger(self):
        ff = FeatureFlags(config_file=_NO_CONFIG)
        assert hasattr(ff, "logger")

    def test_has_lock(self):
        ff = FeatureFlags(config_file=_NO_CONFIG)
        assert hasattr(ff, "lock")


class TestFeatureFlagsIsEnabled:
    def setup_method(self):
        self.ff = FeatureFlags(config_file=_NO_CONFIG)

    def test_unknown_feature_returns_false(self):
        assert self.ff.is_enabled("nonexistent_feature") is False

    def test_enabled_feature_returns_true(self):
        self.ff.enable_feature("my_feature", save=False)
        assert self.ff.is_enabled("my_feature") is True

    def test_disabled_feature_returns_false(self):
        self.ff.enable_feature("feat", save=False)
        self.ff.disable_feature("feat", save=False)
        assert self.ff.is_enabled("feat") is False

    def test_environment_restriction(self):
        """Feature restricted to 'production' is disabled in dev environment."""
        self.ff.features["prod_only"] = _make_flag(
            name="prod_only", environments=["production"]
        )
        # ff.environment is "development" by default
        if self.ff.environment != "production":
            assert self.ff.is_enabled("prod_only") is False

    def test_dependency_chain(self):
        """Feature with unsatisfied dependency is disabled."""
        # Parent disabled, child depends on parent
        self.ff.features["parent"] = _make_flag(name="parent", enabled=False)
        self.ff.features["child"] = _make_flag(
            name="child", enabled=True, dependencies=["parent"]
        )
        assert self.ff.is_enabled("child") is False

    def test_dependency_chain_satisfied(self):
        self.ff.features["base"] = _make_flag(name="base", enabled=True)
        self.ff.features["derived"] = _make_flag(
            name="derived", enabled=True, dependencies=["base"]
        )
        assert self.ff.is_enabled("derived") is True

    def test_check_feature_enabled_alias(self):
        self.ff.enable_feature("alias_feat", save=False)
        assert self.ff.check_feature_enabled("alias_feat") is True


class TestFeatureFlagsEnableDisable:
    def setup_method(self):
        self.ff = FeatureFlags(config_file=_NO_CONFIG)

    def test_enable_new_feature(self):
        result = self.ff.enable_feature("brand_new", save=False)
        assert result is True
        assert self.ff.is_enabled("brand_new") is True

    def test_enable_existing_feature(self):
        self.ff.features["existing"] = _make_flag(name="existing", enabled=False)
        result = self.ff.enable_feature("existing", save=False)
        assert result is True
        assert self.ff.is_enabled("existing") is True

    def test_disable_existing_feature(self):
        self.ff.enable_feature("to_disable", save=False)
        result = self.ff.disable_feature("to_disable", save=False)
        assert result is True
        assert self.ff.is_enabled("to_disable") is False

    def test_disable_nonexistent_feature_returns_false(self):
        result = self.ff.disable_feature("ghost_feature", save=False)
        assert result is False

    def test_enable_returns_bool(self):
        assert isinstance(self.ff.enable_feature("bool_test", save=False), bool)


class TestFeatureFlagsGetEnabledFeatures:
    def setup_method(self):
        self.ff = FeatureFlags(config_file=_NO_CONFIG)

    def test_returns_list(self):
        # Even fresh, may have defaults — just check it's a list
        result = self.ff.get_enabled_features()
        assert isinstance(result, list)

    def test_returns_only_enabled(self):
        self.ff.enable_feature("enabled_one", save=False)
        self.ff.enable_feature("enabled_two", save=False)
        self.ff.features["disabled_one"] = _make_flag(name="disabled_one", enabled=False)
        enabled = self.ff.get_enabled_features()
        assert "enabled_one" in enabled
        assert "enabled_two" in enabled
        assert "disabled_one" not in enabled

    def test_user_id_passed_through(self):
        self.ff.enable_feature("user_feature", save=False)
        enabled = self.ff.get_enabled_features(user_id="alice")
        assert "user_feature" in enabled


# ==============================================================================
# U11 — MODULE-LEVEL FUNCTION TESTS
# ==============================================================================
class TestModuleFunctionCheckFeatureEnabled:
    def test_returns_bool(self):
        result = check_feature_enabled("some_feature")
        assert isinstance(result, bool)

    def test_unknown_feature_false(self):
        assert check_feature_enabled("definitely_not_a_real_feature_xyz") is False


class TestModuleFunctionIsFeatureEnabled:
    def test_returns_bool(self):
        result = is_feature_enabled("some_feature")
        assert isinstance(result, bool)


class TestModuleFunctionEnableFeature:
    def test_returns_bool(self):
        result = enable_feature("module_level_test_feat")
        assert isinstance(result, bool)

    def test_enables_feature(self):
        enable_feature("module_enabled")
        os.path.join(_ROOT, "config/feature_flags.json")
        # We just verify it returns True without checking file persistence
        assert enable_feature("module_enabled") is True


class TestModuleFunctionDisableFeature:
    def test_returns_bool(self):
        result = disable_feature("some_nonexistent_feat_xyz")
        assert isinstance(result, bool)


class TestGetFeatureFlagsSingleton:
    def test_returns_feature_flags_instance(self):
        ff = get_feature_flags()
        assert isinstance(ff, FeatureFlags)

    def test_returns_same_instance_on_repeat(self):
        ff1 = get_feature_flags()
        ff2 = get_feature_flags()
        assert ff1 is ff2
