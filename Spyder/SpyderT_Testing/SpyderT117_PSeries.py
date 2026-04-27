#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT117_PSeries.py
Purpose: Unit tests for SpyderP_PortfolioMgmt series (P01–P07)

Coverage targets:
    P01 PortfolioManager:
        - Enum members: PortfolioState, AllocationMethod, RebalanceReason, HedgeType
        - Dataclass instantiation: StrategyAllocation, PortfolioMetrics, HedgePosition
        - Constructor default attributes
        - add_strategy / remove_strategy basic validation
        - get_portfolio_summary returns expected keys

    P02 AllocationOptimizer:
        - Enum members: OptimizationMethod, ObjectiveFunction, MarketRegime, ConstraintType
        - Dataclass defaults: OptimizationConfig, AllocationResult
        - Constructor sets optimiser state attributes

    P03 CorrelationAnalyzer:
        - Enum members: CorrelationRegime
        - Dataclass defaults: CorrelationMetrics, ClusterResult, FactorResult, CorrelationForecast
        - Helper: detect_correlation_regime_simple
        - Constructor attributes

    P04 CapitalAllocator:
        - Enum members: AllocationMethod, MarketRegime, RiskLevel, RebalanceType
        - Dataclass defaults: AllocationConstraints, StrategyPerformance
        - Constructor defaults and risk-level parameter
        - Kelly fraction calculation edge cases
        - Allocation summary structure

    P05 MultiStrategyAllocator:
        - Enum members: AllocationMethod, OptimizationObjective, RebalanceReason
        - Dataclass defaults: StrategyMetrics, AllocationResult
        - Constructor default attributes

    P06 StrategyRotation:
        - Enum members: MarketRegime, RegimeIndicator, TransitionType, RotationReason
        - Dataclass defaults: RegimeState, RotationPlan
        - REGIME_STRATEGY_MAP structure
        - Constructor default attributes

    P07 RenaissancePositionSizer:
        - Enum members: PositionSizeMethod, TradeOutcome
        - Dataclass defaults: PositionSizeResult, PerformanceMetrics
        - PositionSizeResult.to_dict()
        - Constructor initialisation with custom parameters
        - Position sizing: confidence-scaled, risk-based, Kelly, fixed
        - Trade record creation and history tracking
        - Edge cases: low confidence, zero capital
"""

import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Guard against sys.modules contamination from earlier test files (e.g. T114)
# that insert types.ModuleType stubs into sys.modules for various Spyder
# packages.  We purge any stub (module lacking __file__) in the namespaces
# that P-series modules depend on, so fresh real imports succeed.
# ---------------------------------------------------------------------------
import importlib
import sys
import types as _types

_PURGE_PREFIXES = (
    "Spyder.SpyderP_PortfolioMgmt",
    "Spyder.SpyderC_MarketData",
    "Spyder.SpyderF_Analysis",
    "Spyder.SpyderE_Risk",
    "Spyder.SpyderN_OptionsAnalytics",
    "Spyder.SpyderD_Strategies",
)
for _k in list(sys.modules):
    for _pfx in _PURGE_PREFIXES:
        if (_k == _pfx or _k.startswith(_pfx + ".")) and isinstance(
            sys.modules[_k], _types.ModuleType
        ) and not getattr(sys.modules[_k], "__file__", None):
            del sys.modules[_k]
            break

importlib.invalidate_caches()

from Spyder.SpyderP_PortfolioMgmt import SpyderP01_PortfolioManager  # noqa: E402


# ===========================================================================
# P01 - PortfolioManager
# ===========================================================================


class TestP01Enums(unittest.TestCase):
    """PortfolioManager enums must have all expected members."""

    def test_portfolio_state_members(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP01_PortfolioManager import PortfolioState

        for name in ("INITIALIZING", "ACTIVE", "REBALANCING", "DEFENSIVE",
                      "EMERGENCY", "SHUTDOWN"):
            self.assertTrue(hasattr(PortfolioState, name), f"Missing: {name}")

    def test_allocation_method_members(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP01_PortfolioManager import AllocationMethod

        for name in ("EQUAL_WEIGHT", "RISK_PARITY", "PERFORMANCE_BASED",
                      "VOLATILITY_ADJUSTED", "KELLY_CRITERION"):
            self.assertTrue(hasattr(AllocationMethod, name), f"Missing: {name}")

    def test_rebalance_reason_members(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP01_PortfolioManager import RebalanceReason

        for name in ("SCHEDULED", "DRIFT_THRESHOLD", "RISK_BREACH",
                      "PERFORMANCE_TRIGGER", "MARKET_REGIME_CHANGE", "EMERGENCY"):
            self.assertTrue(hasattr(RebalanceReason, name), f"Missing: {name}")

    def test_hedge_type_members(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP01_PortfolioManager import HedgeType

        for name in ("DELTA_HEDGE", "VOLATILITY_HEDGE", "CORRELATION_HEDGE",
                      "TAIL_RISK_HEDGE", "SECTOR_HEDGE"):
            self.assertTrue(hasattr(HedgeType, name), f"Missing: {name}")



class TestP01Dataclasses(unittest.TestCase):
    """PortfolioManager dataclasses must instantiate with expected defaults."""

    def test_strategy_allocation_fields(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP01_PortfolioManager import StrategyAllocation

        alloc = StrategyAllocation(
            strategy_id="iron_condor",
            strategy_name="Iron Condor",
            target_allocation=0.2,
            current_allocation=0.18,
            allocated_capital=20000.0,
            available_capital=2000.0,
            used_capital=18000.0,
            performance_mtd=0.05,
            performance_ytd=0.12,
            sharpe_ratio=1.5,
            max_drawdown=0.03,
            volatility=0.10,
            correlation_to_portfolio=0.6,
            last_rebalance=datetime.now(),
        )
        self.assertEqual(alloc.strategy_id, "iron_condor")
        self.assertEqual(alloc.status, "active")

    def test_hedge_position_defaults(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP01_PortfolioManager import (
            HedgePosition, HedgeType,
        )

        hedge = HedgePosition(
            hedge_id="H001",
            hedge_type=HedgeType.DELTA_HEDGE,
            hedge_ratio=0.5,
            target_exposure=0.0,
            hedge_instruments=[],
            cost_basis=100.0,
            effectiveness=0.85,
            created_at=datetime.now(),
        )
        self.assertIsNone(hedge.expires_at)
        self.assertTrue(hedge.is_active)



class TestP01PortfolioManagerInit(unittest.TestCase):
    """PortfolioManager constructor must set default attributes."""

    def test_default_capital(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP01_PortfolioManager import (
            PortfolioManager, DEFAULT_PORTFOLIO_SIZE, PortfolioState,
        )

        pm = PortfolioManager()
        self.assertEqual(pm.initial_capital, DEFAULT_PORTFOLIO_SIZE)
        self.assertEqual(pm.state, PortfolioState.INITIALIZING)
        self.assertIsInstance(pm.strategy_allocations, dict)

    def test_custom_capital(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP01_PortfolioManager import PortfolioManager

        pm = PortfolioManager(initial_capital=50_000.0)
        self.assertEqual(pm.initial_capital, 50_000.0)



class TestP01AddRemoveStrategy(unittest.TestCase):
    """PortfolioManager add/remove strategy basic validation."""

    def test_add_strategy_returns_bool(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP01_PortfolioManager import PortfolioManager

        pm = PortfolioManager()
        result = pm.add_strategy("strat_1", None, 0.2)
        self.assertIsInstance(result, bool)

    def test_add_strategy_stored(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP01_PortfolioManager import PortfolioManager

        pm = PortfolioManager()
        pm.add_strategy("strat_1", None, 0.2)
        self.assertIn("strat_1", pm.strategy_allocations)

    def test_remove_nonexistent_strategy(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP01_PortfolioManager import PortfolioManager

        pm = PortfolioManager()
        result = pm.remove_strategy("nonexistent")
        self.assertFalse(result)



class TestP01PortfolioSummary(unittest.TestCase):
    """get_portfolio_summary must return a dict with expected keys."""

    def test_summary_returns_dict(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP01_PortfolioManager import PortfolioManager

        pm = PortfolioManager()
        summary = pm.get_portfolio_summary()
        self.assertIsInstance(summary, dict)

    def test_summary_has_state(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP01_PortfolioManager import PortfolioManager

        pm = PortfolioManager()
        summary = pm.get_portfolio_summary()
        self.assertIn("state", summary)


# ===========================================================================
# P02 - AllocationOptimizer
# ===========================================================================


class TestP02Enums(unittest.TestCase):
    """AllocationOptimizer enums must have all expected members."""

    def test_optimization_method_members(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP02_AllocationOptimizer import OptimizationMethod

        for name in ("MEAN_VARIANCE", "BLACK_LITTERMAN", "RISK_PARITY",
                      "KELLY_CRITERION", "ML_ENHANCED", "ROBUST_OPTIMIZATION"):
            self.assertTrue(hasattr(OptimizationMethod, name), f"Missing: {name}")

    def test_objective_function_members(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP02_AllocationOptimizer import ObjectiveFunction

        for name in ("MAXIMIZE_SHARPE", "MINIMIZE_VOLATILITY", "MAXIMIZE_RETURN",
                      "MINIMIZE_VAR", "MAXIMIZE_UTILITY"):
            self.assertTrue(hasattr(ObjectiveFunction, name), f"Missing: {name}")

    def test_constraint_type_members(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP02_AllocationOptimizer import ConstraintType

        for name in ("BOX_CONSTRAINTS", "SECTOR_CONSTRAINTS", "TURNOVER_CONSTRAINTS",
                      "RISK_CONSTRAINTS"):
            self.assertTrue(hasattr(ConstraintType, name), f"Missing: {name}")


class TestP02Dataclasses(unittest.TestCase):
    """AllocationOptimizer dataclasses must accept keyword args with defaults."""

    def test_optimization_config_defaults(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP02_AllocationOptimizer import (
            OptimizationConfig, OptimizationMethod, ObjectiveFunction,
            DEFAULT_LOOKBACK_PERIOD, DEFAULT_RISK_AVERSION,
        )

        cfg = OptimizationConfig()
        self.assertEqual(cfg.method, OptimizationMethod.ML_ENHANCED)
        self.assertEqual(cfg.objective, ObjectiveFunction.MAXIMIZE_SHARPE)
        self.assertEqual(cfg.lookback_period, DEFAULT_LOOKBACK_PERIOD)
        self.assertEqual(cfg.risk_aversion, DEFAULT_RISK_AVERSION)
        self.assertTrue(cfg.use_regime_detection)
        self.assertTrue(cfg.use_ml_predictions)

    def test_optimization_config_override(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP02_AllocationOptimizer import (
            OptimizationConfig, OptimizationMethod,
        )

        cfg = OptimizationConfig(method=OptimizationMethod.RISK_PARITY, risk_aversion=5.0)
        self.assertEqual(cfg.method, OptimizationMethod.RISK_PARITY)
        self.assertEqual(cfg.risk_aversion, 5.0)


class TestP02AllocationOptimizerInit(unittest.TestCase):
    """AllocationOptimizer constructor must complete without error."""

    @patch("Spyder.SpyderP_PortfolioMgmt.SpyderP02_AllocationOptimizer.VIXAnalyzer")
    def test_default_construction(self, _mock_vix):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP02_AllocationOptimizer import AllocationOptimizer

        opt = AllocationOptimizer()
        self.assertIsNotNone(opt)

    @patch("Spyder.SpyderP_PortfolioMgmt.SpyderP02_AllocationOptimizer.VIXAnalyzer")
    def test_custom_config_construction(self, _mock_vix):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP02_AllocationOptimizer import (
            AllocationOptimizer, OptimizationConfig,
        )

        cfg = OptimizationConfig(risk_aversion=2.0)
        opt = AllocationOptimizer(config=cfg)
        self.assertEqual(opt.config.risk_aversion, 2.0)

    @patch("Spyder.SpyderP_PortfolioMgmt.SpyderP02_AllocationOptimizer.VIXAnalyzer")
    def test_get_optimization_summary(self, _mock_vix):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP02_AllocationOptimizer import AllocationOptimizer

        opt = AllocationOptimizer()
        summary = opt.get_optimization_summary()
        self.assertIsInstance(summary, dict)


# ===========================================================================
# P03 - CorrelationAnalyzer
# ===========================================================================


class TestP03Enums(unittest.TestCase):
    """CorrelationAnalyzer enums must have expected members."""

    def test_correlation_regime_members(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP03_CorrelationAnalyzer import CorrelationRegime

        for name in ("CRISIS_CORRELATION", "HIGH_CORRELATION",
                      "NORMAL_CORRELATION", "LOW_CORRELATION", "DECORRELATION"):
            self.assertTrue(hasattr(CorrelationRegime, name), f"Missing: {name}")


class TestP03Dataclasses(unittest.TestCase):
    """CorrelationAnalyzer dataclasses must instantiate with defaults."""

    def test_correlation_metrics_defaults(self):
        import numpy as np
        from Spyder.SpyderP_PortfolioMgmt.SpyderP03_CorrelationAnalyzer import (
            CorrelationMetrics, CorrelationRegime,
        )

        cm = CorrelationMetrics(
            correlation_matrix=np.eye(3),
            average_correlation=0.5,
            max_correlation=0.8,
        )
        self.assertEqual(cm.min_correlation, 0.0)
        self.assertEqual(cm.correlation_dispersion, 0.0)
        self.assertEqual(cm.condition_number, 1.0)
        self.assertEqual(cm.diversification_ratio, 1.0)
        self.assertEqual(cm.regime, CorrelationRegime.NORMAL_CORRELATION)

    def test_cluster_result_defaults(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP03_CorrelationAnalyzer import ClusterResult

        cr = ClusterResult(clusters={0: ["strat_a", "strat_b"]})
        self.assertEqual(cr.silhouette_score, 0.0)
        self.assertIsNone(cr.linkage_matrix)

    def test_correlation_forecast_defaults(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP03_CorrelationAnalyzer import CorrelationForecast

        cf = CorrelationForecast()
        self.assertEqual(cf.predicted_correlation, 0.0)
        self.assertEqual(cf.model_confidence, 0.0)
        self.assertEqual(cf.forecast_horizon, 10)


class TestP03CorrelationAnalyzerInit(unittest.TestCase):
    """CorrelationAnalyzer constructor must set up defaults."""

    def test_default_construction(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP03_CorrelationAnalyzer import CorrelationAnalyzer

        ca = CorrelationAnalyzer()
        self.assertIsNotNone(ca)
        self.assertIsInstance(ca.correlation_history, list)

    def test_custom_config(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP03_CorrelationAnalyzer import CorrelationAnalyzer

        ca = CorrelationAnalyzer(config={"rolling_window": 90})
        self.assertEqual(ca.config["rolling_window"], 90)

    def test_get_correlation_summary(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP03_CorrelationAnalyzer import CorrelationAnalyzer

        ca = CorrelationAnalyzer()
        summary = ca.get_correlation_summary()
        self.assertIsInstance(summary, dict)


class TestP03DetectRegimeSimple(unittest.TestCase):
    """detect_correlation_regime_simple helper must classify regimes."""

    def test_high_correlation_detected(self):
        import numpy as np
        from Spyder.SpyderP_PortfolioMgmt.SpyderP03_CorrelationAnalyzer import (
            detect_correlation_regime_simple, CorrelationRegime,
        )

        # High correlation matrix
        high_corr = np.array([
            [1.0, 0.90, 0.88],
            [0.90, 1.0, 0.92],
            [0.88, 0.92, 1.0],
        ])
        regime = detect_correlation_regime_simple(high_corr)
        self.assertIn(regime, (CorrelationRegime.CRISIS_CORRELATION,
                               CorrelationRegime.HIGH_CORRELATION))

    def test_low_correlation_detected(self):
        import numpy as np
        from Spyder.SpyderP_PortfolioMgmt.SpyderP03_CorrelationAnalyzer import (
            detect_correlation_regime_simple, CorrelationRegime,
        )

        low_corr = np.array([
            [1.0, 0.10, 0.05],
            [0.10, 1.0, 0.08],
            [0.05, 0.08, 1.0],
        ])
        regime = detect_correlation_regime_simple(low_corr)
        self.assertIn(regime, (CorrelationRegime.LOW_CORRELATION,
                               CorrelationRegime.DECORRELATION))


# ===========================================================================
# P04 - CapitalAllocator
# ===========================================================================


class TestP04Enums(unittest.TestCase):
    """CapitalAllocator enums must have expected members."""

    def test_allocation_method_members(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP04_CapitalAllocator import AllocationMethod

        for name in ("KELLY", "RISK_PARITY", "EQUAL_WEIGHT", "MEAN_VARIANCE",
                      "MAX_SHARPE", "HIERARCHICAL", "DYNAMIC"):
            self.assertTrue(hasattr(AllocationMethod, name), f"Missing: {name}")

    def test_market_regime_members(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP04_CapitalAllocator import MarketRegime

        for name in ("BULL", "BEAR", "SIDEWAYS", "HIGH_VOLATILITY", "CRASH", "RECOVERY"):
            self.assertTrue(hasattr(MarketRegime, name), f"Missing: {name}")

    def test_risk_level_members(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP04_CapitalAllocator import RiskLevel

        for name in ("CONSERVATIVE", "MODERATE", "AGGRESSIVE", "VERY_AGGRESSIVE"):
            self.assertTrue(hasattr(RiskLevel, name), f"Missing: {name}")

    def test_rebalance_type_members(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP04_CapitalAllocator import RebalanceType

        for name in ("PERIODIC", "THRESHOLD", "DYNAMIC", "TACTICAL"):
            self.assertTrue(hasattr(RebalanceType, name), f"Missing: {name}")


class TestP04Dataclasses(unittest.TestCase):
    """CapitalAllocator dataclasses must instantiate with expected defaults."""

    def test_allocation_constraints_defaults(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP04_CapitalAllocator import (
            AllocationConstraints, MAX_POSITION_SIZE, MIN_POSITION_SIZE,
            MAX_LEVERAGE, MAX_STRATEGIES, MIN_STRATEGIES, MAX_CORRELATION,
            TARGET_VOLATILITY, EMERGENCY_CASH_RESERVE, DEFAULT_KELLY_FRACTION,
        )

        ac = AllocationConstraints()
        self.assertEqual(ac.max_position_size, MAX_POSITION_SIZE)
        self.assertEqual(ac.min_position_size, MIN_POSITION_SIZE)
        self.assertEqual(ac.max_leverage, MAX_LEVERAGE)
        self.assertEqual(ac.max_strategies, MAX_STRATEGIES)
        self.assertEqual(ac.min_strategies, MIN_STRATEGIES)
        self.assertEqual(ac.max_correlation, MAX_CORRELATION)
        self.assertEqual(ac.target_volatility, TARGET_VOLATILITY)
        self.assertEqual(ac.cash_reserve, EMERGENCY_CASH_RESERVE)
        self.assertEqual(ac.kelly_fraction, DEFAULT_KELLY_FRACTION)
        self.assertFalse(ac.allow_short)
        self.assertEqual(ac.sector_limits, {})

    def test_strategy_performance_fields(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP04_CapitalAllocator import StrategyPerformance

        sp = StrategyPerformance(
            strategy_id="strat_1",
            returns=[0.01, -0.005, 0.02],
            sharpe_ratio=1.5,
            sortino_ratio=2.0,
            max_drawdown=0.05,
            win_rate=0.6,
            profit_factor=1.8,
            avg_win=0.02,
            avg_loss=-0.01,
            volatility=0.15,
            downside_deviation=0.10,
            var_95=0.03,
            cvar_95=0.04,
            calmar_ratio=3.0,
            recovery_time_days=5.0,
            correlation_to_market=0.3,
        )
        self.assertEqual(sp.strategy_id, "strat_1")
        self.assertEqual(len(sp.returns), 3)


class TestP04CapitalAllocatorInit(unittest.TestCase):
    """CapitalAllocator constructor must set initial capital and risk level."""

    def test_default_risk_level(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP04_CapitalAllocator import (
            CapitalAllocator, RiskLevel,
        )

        ca = CapitalAllocator(initial_capital=100_000.0)
        self.assertEqual(ca.initial_capital, 100_000.0)
        self.assertEqual(ca.risk_level, RiskLevel.MODERATE)

    def test_custom_risk_level(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP04_CapitalAllocator import (
            CapitalAllocator, RiskLevel,
        )

        ca = CapitalAllocator(initial_capital=50_000.0, risk_level=RiskLevel.CONSERVATIVE)
        self.assertEqual(ca.risk_level, RiskLevel.CONSERVATIVE)

    def test_allocation_summary_returns_dict(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP04_CapitalAllocator import CapitalAllocator

        ca = CapitalAllocator(initial_capital=100_000.0)
        summary = ca.get_allocation_summary()
        self.assertIsInstance(summary, dict)


class TestP04KellyFraction(unittest.TestCase):
    """Kelly fraction calculation must handle edge cases."""

    def test_kelly_with_no_performance_data(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP04_CapitalAllocator import CapitalAllocator

        ca = CapitalAllocator(initial_capital=100_000.0)
        # No returns data — should return 0 or a safe minimum
        result = ca.calculate_kelly_fraction("nonexistent")
        self.assertIsInstance(result, float)
        self.assertGreaterEqual(result, 0.0)

    def test_kelly_with_performance_data(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP04_CapitalAllocator import CapitalAllocator

        ca = CapitalAllocator(initial_capital=100_000.0)
        ca.add_returns("strat_1", [0.01, 0.02, -0.005, 0.015, 0.03, -0.01])
        result = ca.calculate_kelly_fraction("strat_1")
        self.assertIsInstance(result, float)
        self.assertGreaterEqual(result, 0.0)
        self.assertLessEqual(result, 1.0)


class TestP04AllocateCapital(unittest.TestCase):
    """allocate_capital must return normalised weights."""

    def test_equal_weight_with_strategies(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP04_CapitalAllocator import (
            CapitalAllocator, AllocationMethod,
        )

        ca = CapitalAllocator(initial_capital=100_000.0)
        strats = ["s1", "s2", "s3", "s4"]
        for s in strats:
            ca.add_returns(s, [0.01, -0.005, 0.02] * 10)
        result = ca.allocate_capital(strats, method=AllocationMethod.EQUAL_WEIGHT)
        self.assertIsInstance(result, list)

    def test_allocation_with_empty_strategies(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP04_CapitalAllocator import CapitalAllocator

        ca = CapitalAllocator(initial_capital=100_000.0)
        result = ca.allocate_capital([])
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 0)


# ===========================================================================
# P05 - MultiStrategyAllocator
# ===========================================================================


class TestP05Enums(unittest.TestCase):
    """MultiStrategyAllocator enums must have expected members."""

    def test_allocation_method_members(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP05_MultiStrategyAllocator import AllocationMethod

        for name in ("EQUAL_WEIGHT", "RISK_PARITY", "MEAN_VARIANCE",
                      "KELLY_CRITERION", "HIERARCHICAL"):
            self.assertTrue(hasattr(AllocationMethod, name), f"Missing: {name}")

    def test_optimization_objective_members(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP05_MultiStrategyAllocator import OptimizationObjective

        for name in ("MAX_SHARPE", "MIN_VARIANCE", "MAX_RETURN", "RISK_PARITY"):
            self.assertTrue(hasattr(OptimizationObjective, name), f"Missing: {name}")

    def test_rebalance_reason_members(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP05_MultiStrategyAllocator import RebalanceReason

        for name in ("SCHEDULED", "DRIFT", "RISK_LIMIT", "PERFORMANCE",
                      "REGIME_CHANGE", "CORRELATION_BREACH"):
            self.assertTrue(hasattr(RebalanceReason, name), f"Missing: {name}")


class TestP05Dataclasses(unittest.TestCase):
    """MultiStrategyAllocator dataclasses must accept keyword args."""

    def test_strategy_metrics_defaults(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP05_MultiStrategyAllocator import StrategyMetrics

        sm = StrategyMetrics(strategy_id="D02_IronCondor")
        self.assertEqual(sm.current_return, 0.0)
        self.assertEqual(sm.sharpe_ratio, 0.0)
        self.assertEqual(sm.max_drawdown, 0.0)
        self.assertEqual(sm.current_positions, 0)
        self.assertEqual(sm.capital_allocated, 0.0)

    def test_allocation_result_defaults(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP05_MultiStrategyAllocator import (
            AllocationResult, AllocationMethod,
        )

        ar = AllocationResult(
            allocations={"s1": 0.5, "s2": 0.5},
            method=AllocationMethod.EQUAL_WEIGHT,
            objective_value=1.5,
            expected_return=0.10,
            expected_volatility=0.15,
            sharpe_ratio=1.5,
            max_drawdown_estimate=0.05,
            diversification_ratio=1.8,
            effective_strategies=2,
        )
        self.assertTrue(ar.constraints_satisfied)
        self.assertEqual(ar.warnings, [])


class TestP05MultiStrategyAllocatorInit(unittest.TestCase):
    """MultiStrategyAllocator constructor must set up default state."""

    def test_default_construction(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP05_MultiStrategyAllocator import (
            MultiStrategyAllocator,
        )

        msa = MultiStrategyAllocator()
        self.assertIsNotNone(msa)

    def test_custom_config(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP05_MultiStrategyAllocator import (
            MultiStrategyAllocator,
        )

        msa = MultiStrategyAllocator(config={"total_capital": 200_000.0})
        self.assertIsNotNone(msa)

    def test_total_capital_from_config(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP05_MultiStrategyAllocator import (
            MultiStrategyAllocator,
        )

        msa = MultiStrategyAllocator(config={"total_capital": 200_000.0})
        self.assertEqual(msa.total_capital, 200_000.0)


# ===========================================================================
# P06 - StrategyRotation
# ===========================================================================


class TestP06Enums(unittest.TestCase):
    """StrategyRotation enums must have expected members."""

    def test_market_regime_members(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP06_StrategyRotation import MarketRegime

        for name in ("TRENDING_UP", "TRENDING_DOWN", "RANGE_BOUND",
                      "HIGH_VOLATILITY", "LOW_VOLATILITY", "CRISIS",
                      "RECOVERY", "TRANSITIONAL"):
            self.assertTrue(hasattr(MarketRegime, name), f"Missing: {name}")

    def test_regime_indicator_members(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP06_StrategyRotation import RegimeIndicator

        for name in ("TREND", "VOLATILITY", "MOMENTUM", "MEAN_REVERSION",
                      "VOLUME", "CORRELATION", "SENTIMENT"):
            self.assertTrue(hasattr(RegimeIndicator, name), f"Missing: {name}")

    def test_transition_type_members(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP06_StrategyRotation import TransitionType

        for name in ("IMMEDIATE", "GRADUAL", "SCALED", "HEDGED"):
            self.assertTrue(hasattr(TransitionType, name), f"Missing: {name}")

    def test_rotation_reason_members(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP06_StrategyRotation import RotationReason

        for name in ("REGIME_CHANGE", "PERFORMANCE", "RISK_LIMIT",
                      "CORRELATION", "MANUAL", "REBALANCE"):
            self.assertTrue(hasattr(RotationReason, name), f"Missing: {name}")


class TestP06RegimeStrategyMap(unittest.TestCase):
    """REGIME_STRATEGY_MAP must cover all non-transitional regimes."""

    def test_map_keys_exist(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP06_StrategyRotation import REGIME_STRATEGY_MAP

        expected_keys = {"TRENDING_UP", "TRENDING_DOWN", "RANGE_BOUND",
                         "HIGH_VOLATILITY", "LOW_VOLATILITY", "CRISIS", "RECOVERY"}
        for key in expected_keys:
            self.assertIn(key, REGIME_STRATEGY_MAP, f"Missing key: {key}")

    def test_each_regime_has_strategies(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP06_StrategyRotation import REGIME_STRATEGY_MAP

        for regime, strategies in REGIME_STRATEGY_MAP.items():
            self.assertIsInstance(strategies, list)
            self.assertGreater(len(strategies), 0, f"Empty list for {regime}")


class TestP06Dataclasses(unittest.TestCase):
    """StrategyRotation dataclasses must instantiate correctly."""

    def test_regime_state_fields(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP06_StrategyRotation import (
            RegimeState, MarketRegime,
        )

        rs = RegimeState(
            regime=MarketRegime.RANGE_BOUND,
            confidence=0.8,
            indicators={},
            start_time=datetime.now(),
            duration_days=5,
            strength=0.7,
            volatility=0.12,
            trend=0.0,
            features={},
        )
        self.assertEqual(rs.regime, MarketRegime.RANGE_BOUND)
        self.assertEqual(rs.confidence, 0.8)


class TestP06StrategyRotationInit(unittest.TestCase):
    """StrategyRotation constructor must set default attributes."""

    def test_default_construction(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP06_StrategyRotation import StrategyRotation

        sr = StrategyRotation()
        self.assertIsNotNone(sr)

    def test_get_regime_analysis(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP06_StrategyRotation import StrategyRotation

        sr = StrategyRotation()
        analysis = sr.get_regime_analysis()
        self.assertIsInstance(analysis, dict)


# ===========================================================================
# P07 - RenaissancePositionSizer
# ===========================================================================


class TestP07Enums(unittest.TestCase):
    """RenaissancePositionSizer enums must have expected members."""

    def test_position_size_method_members(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP07_RenaissancePositionSizer import PositionSizeMethod

        for name in ("FIXED_FRACTION", "RISK_BASED", "KELLY", "CONFIDENCE_SCALED"):
            self.assertTrue(hasattr(PositionSizeMethod, name), f"Missing: {name}")

    def test_trade_outcome_members(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP07_RenaissancePositionSizer import TradeOutcome

        for name in ("WIN", "LOSS", "BREAKEVEN"):
            self.assertTrue(hasattr(TradeOutcome, name), f"Missing: {name}")


class TestP07Dataclasses(unittest.TestCase):
    """RenaissancePositionSizer dataclasses must instantiate with defaults."""

    def test_position_size_result_defaults(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP07_RenaissancePositionSizer import (
            PositionSizeResult, PositionSizeMethod,
        )

        psr = PositionSizeResult(
            num_contracts=5,
            position_value=2500.0,
            risk_per_trade=500.0,
            confidence_used=0.75,
            method_used=PositionSizeMethod.CONFIDENCE_SCALED,
            reasoning="test",
        )
        self.assertEqual(psr.max_loss, 0.0)
        self.assertEqual(psr.risk_reward_ratio, 0.0)
        self.assertEqual(psr.portfolio_risk_pct, 0.0)

    def test_position_size_result_to_dict(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP07_RenaissancePositionSizer import (
            PositionSizeResult, PositionSizeMethod,
        )

        psr = PositionSizeResult(
            num_contracts=3,
            position_value=1500.0,
            risk_per_trade=300.0,
            confidence_used=0.80,
            method_used=PositionSizeMethod.KELLY,
            reasoning="kelly sizing",
        )
        d = psr.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["num_contracts"], 3)
        self.assertEqual(d["position_value"], 1500.0)

    def test_performance_metrics_defaults(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP07_RenaissancePositionSizer import PerformanceMetrics

        pm = PerformanceMetrics()
        self.assertEqual(pm.total_trades, 0)
        self.assertEqual(pm.winning_trades, 0)
        self.assertEqual(pm.losing_trades, 0)
        self.assertEqual(pm.win_rate, 0.0)
        self.assertEqual(pm.total_pnl, 0.0)
        self.assertEqual(pm.max_drawdown, 0.0)


class TestP07RenaissancePositionSizerInit(unittest.TestCase):
    """RenaissancePositionSizer constructor must initialise all attributes."""

    def test_default_construction(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP07_RenaissancePositionSizer import (
            RenaissancePositionSizer,
            DEFAULT_MAX_POSITION_SIZE,
            DEFAULT_MAX_PORTFOLIO_RISK,
            DEFAULT_MIN_CONFIDENCE,
        )

        rps = RenaissancePositionSizer()
        self.assertEqual(rps.initial_capital, 100_000.0)
        self.assertEqual(rps.max_position_size, DEFAULT_MAX_POSITION_SIZE)
        self.assertEqual(rps.max_portfolio_risk, DEFAULT_MAX_PORTFOLIO_RISK)
        self.assertEqual(rps.min_confidence, DEFAULT_MIN_CONFIDENCE)

    def test_custom_capital(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP07_RenaissancePositionSizer import (
            RenaissancePositionSizer,
        )

        rps = RenaissancePositionSizer(initial_capital=50_000.0)
        self.assertEqual(rps.initial_capital, 50_000.0)


class TestP07PositionSizing(unittest.TestCase):
    """Position sizing methods must return valid PositionSizeResult."""

    def test_confidence_scaled_sizing(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP07_RenaissancePositionSizer import (
            RenaissancePositionSizer, PositionSizeMethod,
        )

        rps = RenaissancePositionSizer(initial_capital=100_000.0)
        result = rps.calculate_position_size(
            entry_price=5.00,
            stop_loss=4.00,
            confidence=0.75,
            method=PositionSizeMethod.CONFIDENCE_SCALED,
        )
        self.assertGreaterEqual(result.num_contracts, 0)
        self.assertEqual(result.method_used, PositionSizeMethod.CONFIDENCE_SCALED)
        self.assertEqual(result.confidence_used, 0.75)

    def test_risk_based_sizing(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP07_RenaissancePositionSizer import (
            RenaissancePositionSizer, PositionSizeMethod,
        )

        rps = RenaissancePositionSizer(initial_capital=100_000.0)
        result = rps.calculate_position_size(
            entry_price=5.00,
            stop_loss=4.50,
            confidence=0.70,
            method=PositionSizeMethod.RISK_BASED,
        )
        self.assertGreaterEqual(result.num_contracts, 0)
        self.assertEqual(result.method_used, PositionSizeMethod.RISK_BASED)

    def test_kelly_sizing(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP07_RenaissancePositionSizer import (
            RenaissancePositionSizer, PositionSizeMethod,
        )

        rps = RenaissancePositionSizer(initial_capital=100_000.0)
        result = rps.calculate_position_size(
            entry_price=5.00,
            stop_loss=4.00,
            confidence=0.80,
            method=PositionSizeMethod.KELLY,
        )
        self.assertGreaterEqual(result.num_contracts, 0)
        self.assertEqual(result.method_used, PositionSizeMethod.KELLY)

    def test_fixed_fraction_sizing(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP07_RenaissancePositionSizer import (
            RenaissancePositionSizer, PositionSizeMethod,
        )

        rps = RenaissancePositionSizer(initial_capital=100_000.0)
        result = rps.calculate_position_size(
            entry_price=5.00,
            stop_loss=4.00,
            confidence=0.65,
            method=PositionSizeMethod.FIXED_FRACTION,
        )
        self.assertGreaterEqual(result.num_contracts, 0)
        self.assertEqual(result.method_used, PositionSizeMethod.FIXED_FRACTION)

    def test_low_confidence_returns_zero_contracts(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP07_RenaissancePositionSizer import (
            RenaissancePositionSizer, PositionSizeMethod,
        )

        rps = RenaissancePositionSizer(initial_capital=100_000.0, min_confidence=0.60)
        result = rps.calculate_position_size(
            entry_price=5.00,
            stop_loss=4.00,
            confidence=0.30,
            method=PositionSizeMethod.CONFIDENCE_SCALED,
        )
        self.assertEqual(result.num_contracts, 0)


class TestP07TradeHistory(unittest.TestCase):
    """Trade recording and history tracking."""

    def test_record_trade_creates_entry(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP07_RenaissancePositionSizer import (
            RenaissancePositionSizer,
        )

        rps = RenaissancePositionSizer(initial_capital=100_000.0)
        record = rps.record_trade(
            symbol="SPY",
            entry_price=5.00,
            exit_price=6.00,
            position_size=10,
            confidence=0.8,
            entry_time=datetime(2025, 6, 1, 10, 0),
            exit_reason="target_hit",
        )
        self.assertEqual(record.symbol, "SPY")
        self.assertEqual(record.entry_price, 5.00)
        self.assertEqual(record.exit_price, 6.00)
        self.assertEqual(record.position_size, 10)

    def test_get_metrics_returns_dict(self):
        from Spyder.SpyderP_PortfolioMgmt.SpyderP07_RenaissancePositionSizer import (
            RenaissancePositionSizer,
        )

        rps = RenaissancePositionSizer(initial_capital=100_000.0)
        metrics = rps.get_metrics()
        self.assertIsInstance(metrics, dict)


if __name__ == "__main__":
    unittest.main()
