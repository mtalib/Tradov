#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderP05_MultiStrategyAllocator.py
Group: P (Portfolio Management)
Purpose: Dynamic capital allocation across multiple trading strategies
Author: Mohamed Talib
Date Created: 2025-01-27
Last Updated: 2025-01-27 Time: 16:00:00

Description:
    This module provides sophisticated capital allocation across all 26 trading
    strategies (D01-D26) using Kelly criterion, correlation analysis, and
    performance-based weighting. It optimizes portfolio allocation while
    respecting risk limits, managing strategy correlations, and adapting to
    market regimes for maximum risk-adjusted returns.

Key Features:
    - Kelly criterion position sizing
    - Strategy correlation management
    - Performance-based dynamic weighting
    - Risk parity allocation
    - Mean-variance optimization
    - Regime-adaptive allocation
    - Capital efficiency monitoring
    - Integration with risk limits (E11)
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Any
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
from enum import Enum
import threading
from pathlib import Path
from types import SimpleNamespace

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from scipy.optimize import minimize, Bounds
from scipy.stats import pearsonr
import scipy.cluster.hierarchy as sch
from sklearn.covariance import LedoitWolf

# Institutional Portfolio Analytics
try:
    import riskfolio as rp
    HAS_RISKFOLIO = True
except ImportError:
    HAS_RISKFOLIO = False

# ==============================================================================
# SPYDER IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderI_Integration.SpyderI06_AgentMessageBus import Message, MessagePriority

# ==============================================================================
# HELPERS
# ==============================================================================

def _json_default(obj):
    """JSON serialization helper: converts datetime/Enum/dataclass for json.dump."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    if hasattr(obj, '__dataclass_fields__'):
        return asdict(obj)
    return str(obj)


def _ns(d):
    """Recursively convert dicts to SimpleNamespace for attribute-compatible access."""
    if isinstance(d, dict):
        return SimpleNamespace(**{k: _ns(v) for k, v in d.items()})
    if isinstance(d, list):
        return [_ns(i) for i in d]
    return d


# ==============================================================================
# CONSTANTS
# ==============================================================================
# Strategy identifiers (D01-D26)
STRATEGY_IDS = [
    'D01_BaseStrategy', 'D02_IronCondor', 'D03_CreditSpread', 'D04_ZeroDTE',
    'D05_Straddle', 'D06_BullPutSpread', 'D07_BearCallSpread',
    'D08_OpeningRangeBreakout', 'D09_GreeksBased', 'D10_IronButterfly',
    'D11_SpecializedZeroDTE', 'D12_RSIMeanReversion', 'D13_MACrossover',
    'D14_CalendarSpread', 'D15_StraddleStrangle', 'D16_RatioSpreads',
    'D17_DiagonalSpread', 'D18_EvolvedCreditSpread', 'D19_JadeLizard',
    'D20_VerticalSpreadOptimizer', 'D21_DoubleCalendar', 'D22_AdaptiveVolatility',
    'D23_Reserved', 'D24_Reserved', 'D25_Reserved', 'D26_GammaScalper'
]

# Allocation constraints
MIN_ALLOCATION = 0.0  # Minimum allocation per strategy (0%)
MAX_ALLOCATION = 0.25  # Maximum allocation per strategy (25%)
MIN_ACTIVE_STRATEGIES = 3  # Minimum number of active strategies
MAX_ACTIVE_STRATEGIES = 10  # Maximum number of active strategies
KELLY_FRACTION = 0.25  # Fraction of Kelly criterion to use (quarter-Kelly)

# Risk parameters
MAX_PORTFOLIO_LEVERAGE = 2.0  # Maximum leverage
MAX_CORRELATION_THRESHOLD = 0.8  # Maximum correlation between strategies
MIN_SHARPE_RATIO = 0.5  # Minimum Sharpe ratio for allocation
TARGET_VOLATILITY = 0.15  # Annual target volatility (15%)

# Performance windows
PERFORMANCE_LOOKBACK = 60  # Days for performance calculation
CORRELATION_LOOKBACK = 90  # Days for correlation calculation
REBALANCE_FREQUENCY = 1  # Days between rebalancing

# ==============================================================================
# ENUMS
# ==============================================================================
class AllocationMethod(Enum):
    """Capital allocation methods"""
    EQUAL_WEIGHT = "equal_weight"
    RISK_PARITY = "risk_parity"
    MEAN_VARIANCE = "mean_variance"
    KELLY_CRITERION = "kelly_criterion"
    HIERARCHICAL = "hierarchical"
    MAX_DIVERSIFICATION = "max_diversification"
    MIN_CORRELATION = "min_correlation"

class OptimizationObjective(Enum):
    """Portfolio optimization objectives"""
    MAX_SHARPE = "max_sharpe"
    MIN_VARIANCE = "min_variance"
    MAX_RETURN = "max_return"
    RISK_PARITY = "risk_parity"
    MAX_DIVERSIFICATION = "max_diversification"

class RebalanceReason(Enum):
    """Reasons for portfolio rebalancing"""
    SCHEDULED = "scheduled"
    DRIFT = "drift"
    RISK_LIMIT = "risk_limit"
    PERFORMANCE = "performance"
    REGIME_CHANGE = "regime_change"
    CORRELATION_BREACH = "correlation_breach"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class StrategyMetrics:
    """Performance metrics for a strategy"""
    strategy_id: str
    current_return: float = 0.0
    avg_return: float = 0.0
    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    kelly_fraction: float = 0.0
    current_positions: int = 0
    capital_allocated: float = 0.0
    last_update: datetime = field(default_factory=datetime.now)

@dataclass
class AllocationResult:
    """Result of allocation optimization"""
    allocations: dict[str, float]  # strategy_id -> allocation percentage
    method: AllocationMethod
    objective_value: float
    expected_return: float
    expected_volatility: float
    sharpe_ratio: float
    max_drawdown_estimate: float
    diversification_ratio: float
    effective_strategies: int
    timestamp: datetime = field(default_factory=datetime.now)
    constraints_satisfied: bool = True
    warnings: list[str] = field(default_factory=list)

@dataclass
class PortfolioState:
    """Current portfolio state"""
    total_capital: float
    allocated_capital: float
    free_capital: float
    current_allocations: dict[str, float]
    active_strategies: list[str]
    portfolio_return: float
    portfolio_volatility: float
    portfolio_sharpe: float
    leverage: float
    last_rebalance: datetime
    next_rebalance: datetime

@dataclass
class RebalanceEvent:
    """Record of portfolio rebalancing"""
    timestamp: datetime
    reason: RebalanceReason
    old_allocations: dict[str, float]
    new_allocations: dict[str, float]
    trades_required: dict[str, float]  # strategy -> capital change
    expected_impact: float
    actual_impact: float | None = None

# ==============================================================================
# MAIN MULTI-STRATEGY ALLOCATOR CLASS
# ==============================================================================
class MultiStrategyAllocator:
    """
    Dynamic capital allocator for multiple trading strategies.

    Optimizes capital allocation across strategies using various methods
    including Kelly criterion, risk parity, and mean-variance optimization.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the Multi-Strategy Allocator"""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config = config or {}

        # Capital management
        self.total_capital = self.config.get('total_capital', 1000000)
        self.risk_free_rate = self.config.get('risk_free_rate', 0.05)

        # Strategy tracking
        self.strategy_metrics = {}
        self.strategy_returns = defaultdict(lambda: deque(maxlen=PERFORMANCE_LOOKBACK))
        self.strategy_positions = defaultdict(int)

        # Allocation state
        self.current_allocations = {}
        self.target_allocations = {}
        self.allocation_history = deque(maxlen=1000)

        # Performance tracking
        self.portfolio_returns = deque(maxlen=252)  # 1 year of daily returns
        self.rebalance_history = deque(maxlen=100)

        # Correlation and covariance
        self.correlation_matrix = None
        self.covariance_matrix = None
        self.last_correlation_update = None

        # Risk management
        self.max_loss_protection = None
        self.risk_limits = {}

        # Message bus for communication
        self.message_bus = None

        # Threading
        self._lock = threading.RLock()
        self._shutdown = threading.Event()

        # Initialize components
        self._initialize_strategies()
        self._initialize_risk_limits()
        self._load_historical_data()

        self.logger.info("MultiStrategyAllocator initialized with %s strategies", len(STRATEGY_IDS))

    def _initialize_strategies(self):
        """Initialize strategy metrics"""
        for strategy_id in STRATEGY_IDS:
            self.strategy_metrics[strategy_id] = StrategyMetrics(strategy_id=strategy_id)
            self.current_allocations[strategy_id] = 0.0
            self.target_allocations[strategy_id] = 0.0

    def _initialize_risk_limits(self):
        """Initialize risk limits for strategies"""
        # Default risk limits per strategy
        for strategy_id in STRATEGY_IDS:
            self.risk_limits[strategy_id] = {
                'max_allocation': MAX_ALLOCATION,
                'max_positions': 10,
                'max_drawdown': 0.10,  # 10% max drawdown
                'stop_loss': 0.05  # 5% stop loss
            }

        # Adjust for specific strategy types
        # Higher risk for 0DTE strategies
        for strategy_id in ['D04_ZeroDTE', 'D11_SpecializedZeroDTE']:
            self.risk_limits[strategy_id]['max_allocation'] = 0.10  # Max 10%
            self.risk_limits[strategy_id]['stop_loss'] = 0.03  # Tighter stop

        # Lower risk for complex strategies
        for strategy_id in ['D19_JadeLizard', 'D21_DoubleCalendar']:
            self.risk_limits[strategy_id]['max_positions'] = 5

    def _load_historical_data(self):
        """Load historical performance data"""
        try:
            history_file = Path("data/portfolio/allocation_history.json")
            # Backward-compat: migrate from legacy .pkl if .json not present
            if not history_file.exists():
                legacy = history_file.with_suffix('.pkl')
                if legacy.exists():
                    import joblib as _joblib
                    with open(legacy, 'rb') as _f:
                        _data = _joblib.load(_f)
                    history_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(history_file, 'w', encoding='utf-8') as _f:
                        json.dump(_data, _f, default=_json_default, indent=2)
            if history_file.exists():
                with open(history_file, encoding='utf-8') as f:
                    data = json.load(f)
                    self.allocation_history = deque(
                        (_ns(item) for item in data['allocations']), maxlen=1000
                    )
                    self.rebalance_history = deque(
                        (_ns(item) for item in data['rebalances']), maxlen=100
                    )
                    self.logger.info("Loaded %s historical allocations", len(self.allocation_history))  # noqa: E501
        except Exception as e:
            self.logger.warning("Could not load historical data: %s", e, exc_info=True)

    def update_strategy_performance(
        self,
        strategy_id: str,
        daily_return: float,
        positions: int = 0,
        metrics: dict[str, float] | None = None
    ):
        """
        Update strategy performance metrics.

        Args:
            strategy_id: Strategy identifier
            daily_return: Today's return
            positions: Current position count
            metrics: Additional metrics
        """
        with self._lock:
            if strategy_id not in self.strategy_metrics:
                self.logger.warning("Unknown strategy: %s", strategy_id)
                return

            # Update returns history
            self.strategy_returns[strategy_id].append(daily_return)

            # Update positions
            self.strategy_positions[strategy_id] = positions

            # Calculate metrics
            if len(self.strategy_returns[strategy_id]) >= 20:  # Need minimum history
                returns = np.array(self.strategy_returns[strategy_id])

                strategy = self.strategy_metrics[strategy_id]
                strategy.current_return = daily_return
                strategy.avg_return = np.mean(returns)
                strategy.volatility = np.std(returns) * np.sqrt(252)  # Annualized

                # Sharpe ratio
                if strategy.volatility > 0:
                    strategy.sharpe_ratio = (
                        (strategy.avg_return * 252 - self.risk_free_rate) /
                        strategy.volatility
                    )

                # Sortino ratio (downside deviation)
                downside_returns = returns[returns < 0]
                if len(downside_returns) > 0:
                    downside_dev = np.std(downside_returns) * np.sqrt(252)
                    if downside_dev > 0:
                        strategy.sortino_ratio = (
                            (strategy.avg_return * 252 - self.risk_free_rate) /
                            downside_dev
                        )

                # Max drawdown
                cumulative = np.cumprod(1 + returns)
                running_max = np.maximum.accumulate(cumulative)
                drawdown = (cumulative - running_max) / running_max
                strategy.max_drawdown = np.min(drawdown)

                # Win rate
                strategy.win_rate = len(returns[returns > 0]) / len(returns)

                # Kelly fraction
                if strategy.volatility > 0:
                    strategy.kelly_fraction = min(
                        strategy.avg_return / (strategy.volatility ** 2),
                        KELLY_FRACTION
                    )

                # Update from additional metrics
                if metrics:
                    strategy.profit_factor = metrics.get('profit_factor', 1.0)

                strategy.current_positions = positions
                strategy.last_update = datetime.now()

            # Trigger correlation update if needed
            if (self.last_correlation_update is None or
                (datetime.now() - self.last_correlation_update).days >= 7):
                self._update_correlation_matrix()

    def _update_correlation_matrix(self):
        """Update correlation and covariance matrices"""
        try:
            # Need at least 30 days of data
            min_history = 30

            # Collect returns data
            returns_data = {}
            for strategy_id in STRATEGY_IDS:
                if len(self.strategy_returns[strategy_id]) >= min_history:
                    returns_data[strategy_id] = list(self.strategy_returns[strategy_id])

            if len(returns_data) < 2:
                return

            # Create DataFrame
            df = pd.DataFrame(returns_data)

            # Calculate correlation matrix
            self.correlation_matrix = df.corr()

            # Calculate covariance matrix with shrinkage
            lw = LedoitWolf()
            self.covariance_matrix, _ = lw.fit(df.values)

            self.last_correlation_update = datetime.now()

            # Check for high correlations
            self._check_correlation_breaches()

        except Exception as e:
            self.logger.error("Failed to update correlation matrix: %s", e, exc_info=True)

    def _check_correlation_breaches(self):
        """Check for strategies with excessive correlation"""
        if self.correlation_matrix is None:
            return

        warnings = []
        for i, strat1 in enumerate(self.correlation_matrix.index):
            for j, strat2 in enumerate(self.correlation_matrix.columns):
                if i < j:  # Upper triangle only
                    corr = self.correlation_matrix.iloc[i, j]
                    if abs(corr) > MAX_CORRELATION_THRESHOLD:
                        warnings.append(
                            f"High correlation ({corr:.2f}) between {strat1} and {strat2}"
                        )

        if warnings:
            self.logger.warning("Correlation warnings: %s", warnings)
            # Could trigger rebalancing

    def optimize_allocation(
        self,
        method: AllocationMethod = AllocationMethod.MEAN_VARIANCE,
        objective: OptimizationObjective = OptimizationObjective.MAX_SHARPE,
        constraints: dict[str, Any] | None = None
    ) -> AllocationResult:
        """
        Optimize portfolio allocation.

        Args:
            method: Allocation method to use
            objective: Optimization objective
            constraints: Additional constraints

        Returns:
            AllocationResult with optimal allocations
        """
        with self._lock:
            try:
                # Get strategies with sufficient data
                eligible_strategies = self._get_eligible_strategies()

                if len(eligible_strategies) < MIN_ACTIVE_STRATEGIES:
                    self.logger.warning("Insufficient eligible strategies: %s", len(eligible_strategies))  # noqa: E501
                    return self._create_default_allocation()

                # Select optimization method
                if method == AllocationMethod.EQUAL_WEIGHT:
                    result = self._equal_weight_allocation(eligible_strategies)

                elif method == AllocationMethod.RISK_PARITY:
                    result = self._risk_parity_allocation(eligible_strategies)

                elif method == AllocationMethod.KELLY_CRITERION:
                    result = self._kelly_allocation(eligible_strategies)

                elif method == AllocationMethod.MEAN_VARIANCE:
                    result = self._mean_variance_optimization(eligible_strategies, objective)

                elif method == AllocationMethod.HIERARCHICAL:
                    result = self._hierarchical_allocation(eligible_strategies)

                elif method == AllocationMethod.MAX_DIVERSIFICATION:
                    result = self._max_diversification_allocation(eligible_strategies)

                else:
                    result = self._equal_weight_allocation(eligible_strategies)

                # Apply constraints
                result = self._apply_constraints(result, constraints)

                # Validate allocations
                result = self._validate_allocations(result)

                # Record allocation
                self.allocation_history.append(result)

                return result

            except Exception as e:
                self.logger.error("Allocation optimization failed: %s", e, exc_info=True)
                self.error_handler.handle_error(e, {"method": method.value})
                return self._create_default_allocation()

    def _get_eligible_strategies(self) -> list[str]:
        """Get strategies eligible for allocation"""
        eligible = []

        for strategy_id, metrics in self.strategy_metrics.items():
            # Check if strategy has enough history
            if len(self.strategy_returns[strategy_id]) < 30:
                continue

            # Check minimum Sharpe ratio
            if metrics.sharpe_ratio < MIN_SHARPE_RATIO:
                continue

            # Check max drawdown
            if abs(metrics.max_drawdown) > self.risk_limits[strategy_id]['max_drawdown']:
                continue

            eligible.append(strategy_id)

        return eligible

    def _equal_weight_allocation(self, strategies: list[str]) -> AllocationResult:
        """Equal weight allocation across strategies"""
        n = min(len(strategies), MAX_ACTIVE_STRATEGIES)
        selected = sorted(strategies,
                         key=lambda x: self.strategy_metrics[x].sharpe_ratio,
                         reverse=True)[:n]

        weight = 1.0 / n
        allocations = {s: weight for s in selected}

        # Calculate portfolio metrics
        metrics = self._calculate_portfolio_metrics(allocations)

        return AllocationResult(
            allocations=allocations,
            method=AllocationMethod.EQUAL_WEIGHT,
            objective_value=metrics['sharpe_ratio'],
            expected_return=metrics['expected_return'],
            expected_volatility=metrics['expected_volatility'],
            sharpe_ratio=metrics['sharpe_ratio'],
            max_drawdown_estimate=metrics['max_drawdown'],
            diversification_ratio=metrics['diversification_ratio'],
            effective_strategies=n
        )

    def _risk_parity_allocation(self, strategies: list[str]) -> AllocationResult:
        """Risk parity allocation - equal risk contribution"""
        n = len(strategies)

        # Get covariance matrix for eligible strategies
        cov_matrix = self._get_covariance_matrix(strategies)

        # Objective: minimize difference in risk contributions
        def risk_parity_objective(weights):
            portfolio_vol = np.sqrt(weights @ cov_matrix @ weights.T)
            marginal_contrib = cov_matrix @ weights.T
            contrib = weights * marginal_contrib / portfolio_vol

            # Target equal contribution
            target_contrib = portfolio_vol / n

            # Sum of squared differences from target
            return np.sum((contrib - target_contrib) ** 2)

        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}  # Sum to 1
        ]

        # Bounds
        bounds = Bounds(0, MAX_ALLOCATION)

        # Initial guess
        x0 = np.ones(n) / n

        # Optimize
        result = minimize(
            risk_parity_objective,
            x0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )

        if result.success:
            allocations = dict(zip(strategies, result.x, strict=False))
        else:
            # Fallback to equal weight
            allocations = {s: 1/n for s in strategies}

        metrics = self._calculate_portfolio_metrics(allocations)

        return AllocationResult(
            allocations=allocations,
            method=AllocationMethod.RISK_PARITY,
            objective_value=metrics['sharpe_ratio'],
            expected_return=metrics['expected_return'],
            expected_volatility=metrics['expected_volatility'],
            sharpe_ratio=metrics['sharpe_ratio'],
            max_drawdown_estimate=metrics['max_drawdown'],
            diversification_ratio=metrics['diversification_ratio'],
            effective_strategies=len([w for w in allocations.values() if w > 0.01])
        )

    def _kelly_allocation(self, strategies: list[str]) -> AllocationResult:
        """Kelly criterion based allocation"""
        allocations = {}

        for strategy_id in strategies:
            metrics = self.strategy_metrics[strategy_id]

            # Kelly fraction (already calculated and capped)
            kelly = metrics.kelly_fraction * KELLY_FRACTION  # Use fractional Kelly

            # Cap at maximum allocation
            kelly = min(kelly, MAX_ALLOCATION)

            allocations[strategy_id] = kelly

        # Normalize to sum to 1 if over-allocated
        total = sum(allocations.values())
        if total > 1:
            allocations = {k: v/total for k, v in allocations.items()}

        # Select top strategies if too many
        if len(allocations) > MAX_ACTIVE_STRATEGIES:
            sorted_strategies = sorted(allocations.items(),
                                     key=lambda x: x[1],
                                     reverse=True)
            allocations = dict(sorted_strategies[:MAX_ACTIVE_STRATEGIES])

            # Re-normalize
            total = sum(allocations.values())
            allocations = {k: v/total for k, v in allocations.items()}

        metrics = self._calculate_portfolio_metrics(allocations)

        return AllocationResult(
            allocations=allocations,
            method=AllocationMethod.KELLY_CRITERION,
            objective_value=metrics['sharpe_ratio'],
            expected_return=metrics['expected_return'],
            expected_volatility=metrics['expected_volatility'],
            sharpe_ratio=metrics['sharpe_ratio'],
            max_drawdown_estimate=metrics['max_drawdown'],
            diversification_ratio=metrics['diversification_ratio'],
            effective_strategies=len([w for w in allocations.values() if w > 0.01])
        )

    def _mean_variance_optimization(
        self,
        strategies: list[str],
        objective: OptimizationObjective
    ) -> AllocationResult:
        """Mean-variance portfolio optimization"""
        n = len(strategies)

        # Get expected returns and covariance
        returns = np.array([self.strategy_metrics[s].avg_return * 252
                          for s in strategies])
        cov_matrix = self._get_covariance_matrix(strategies)

        # Define objective function
        if objective == OptimizationObjective.MAX_SHARPE:
            def objective_func(weights):
                port_return = weights @ returns
                port_vol = np.sqrt(weights @ cov_matrix @ weights.T)
                sharpe = (port_return - self.risk_free_rate) / port_vol if port_vol > 0 else 0
                return -sharpe  # Minimize negative Sharpe

        elif objective == OptimizationObjective.MIN_VARIANCE:
            def objective_func(weights):
                return weights @ cov_matrix @ weights.T

        else:  # MAX_RETURN
            def objective_func(weights):
                return -(weights @ returns)

        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}  # Sum to 1
        ]

        # Add volatility constraint
        if objective != OptimizationObjective.MIN_VARIANCE:
            constraints.append({
                'type': 'ineq',
                'fun': lambda x: TARGET_VOLATILITY - np.sqrt(x @ cov_matrix @ x.T)
            })

        # Bounds
        bounds = Bounds(0, MAX_ALLOCATION)

        # Initial guess
        x0 = np.ones(n) / n

        # Optimize
        result = minimize(
            objective_func,
            x0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
            options={'maxiter': 1000}
        )

        if result.success:
            allocations = dict(zip(strategies, result.x, strict=False))
        else:
            self.logger.warning("Optimization failed, using equal weights")
            allocations = {s: 1/n for s in strategies}

        # Filter out tiny allocations
        allocations = {k: v for k, v in allocations.items() if v > 0.001}

        # Re-normalize
        total = sum(allocations.values())
        if total > 0:
            allocations = {k: v/total for k, v in allocations.items()}

        metrics = self._calculate_portfolio_metrics(allocations)

        return AllocationResult(
            allocations=allocations,
            method=AllocationMethod.MEAN_VARIANCE,
            objective_value=-result.fun if result.success else 0,
            expected_return=metrics['expected_return'],
            expected_volatility=metrics['expected_volatility'],
            sharpe_ratio=metrics['sharpe_ratio'],
            max_drawdown_estimate=metrics['max_drawdown'],
            diversification_ratio=metrics['diversification_ratio'],
            effective_strategies=len(allocations)
        )

    def _hierarchical_allocation(self, strategies: list[str]) -> AllocationResult:
        """Hierarchical risk parity allocation"""
        # Get correlation matrix
        corr_matrix = self._get_correlation_matrix(strategies)

        # Perform hierarchical clustering
        distance_matrix = np.sqrt(2 * (1 - corr_matrix))
        clusters = sch.linkage(distance_matrix, method='ward')

        # Get cluster order
        cluster_order = sch.dendrogram(clusters, no_plot=True)['leaves']

        # Reorder strategies
        ordered_strategies = [strategies[i] for i in cluster_order]

        # Apply risk parity within clusters
        # For simplicity, using equal weight here
        n = min(len(ordered_strategies), MAX_ACTIVE_STRATEGIES)
        selected = ordered_strategies[:n]

        allocations = {s: 1/n for s in selected}

        metrics = self._calculate_portfolio_metrics(allocations)

        return AllocationResult(
            allocations=allocations,
            method=AllocationMethod.HIERARCHICAL,
            objective_value=metrics['sharpe_ratio'],
            expected_return=metrics['expected_return'],
            expected_volatility=metrics['expected_volatility'],
            sharpe_ratio=metrics['sharpe_ratio'],
            max_drawdown_estimate=metrics['max_drawdown'],
            diversification_ratio=metrics['diversification_ratio'],
            effective_strategies=n
        )

    def _max_diversification_allocation(self, strategies: list[str]) -> AllocationResult:
        """Maximum diversification portfolio"""
        n = len(strategies)

        # Get covariance matrix and volatilities
        cov_matrix = self._get_covariance_matrix(strategies)
        volatilities = np.sqrt(np.diag(cov_matrix))

        # Objective: maximize diversification ratio
        def objective_func(weights):
            weighted_avg_vol = weights @ volatilities
            portfolio_vol = np.sqrt(weights @ cov_matrix @ weights.T)
            div_ratio = weighted_avg_vol / portfolio_vol if portfolio_vol > 0 else 0
            return -div_ratio  # Minimize negative

        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}
        ]

        # Bounds
        bounds = Bounds(0, MAX_ALLOCATION)

        # Initial guess
        x0 = np.ones(n) / n

        # Optimize
        result = minimize(
            objective_func,
            x0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )

        if result.success:
            allocations = dict(zip(strategies, result.x, strict=False))
        else:
            allocations = {s: 1/n for s in strategies}

        # Filter tiny allocations
        allocations = {k: v for k, v in allocations.items() if v > 0.001}

        # Re-normalize
        total = sum(allocations.values())
        if total > 0:
            allocations = {k: v/total for k, v in allocations.items()}

        metrics = self._calculate_portfolio_metrics(allocations)

        return AllocationResult(
            allocations=allocations,
            method=AllocationMethod.MAX_DIVERSIFICATION,
            objective_value=-result.fun if result.success else 0,
            expected_return=metrics['expected_return'],
            expected_volatility=metrics['expected_volatility'],
            sharpe_ratio=metrics['sharpe_ratio'],
            max_drawdown_estimate=metrics['max_drawdown'],
            diversification_ratio=metrics['diversification_ratio'],
            effective_strategies=len(allocations)
        )

    def _get_covariance_matrix(self, strategies: list[str]) -> np.ndarray:
        """Get robust covariance matrix for given strategies.

        Uses RiskFolio-Lib Ledoit-Wolf estimation when available,
        falls back to sklearn LedoitWolf, then to sample covariance.
        """
        n = len(strategies)

        # Collect strategy returns
        returns_data = []
        valid_strategies = []
        for strategy in strategies:
            if strategy in self.strategy_returns and len(self.strategy_returns[strategy]) >= 30:
                returns_data.append(list(self.strategy_returns[strategy]))
                valid_strategies.append(strategy)

        if len(returns_data) < 2:
            # Not enough data — use diagonal matrix with historical vol
            diag_vals = []
            for strategy in strategies:
                if strategy in self.strategy_returns and len(self.strategy_returns[strategy]) >= 5:
                    vol = np.var(list(self.strategy_returns[strategy])) * 252
                    diag_vals.append(max(vol, 0.001))
                else:
                    diag_vals.append(0.01)
            return np.diag(diag_vals)

        # Align returns to equal length
        min_len = min(len(r) for r in returns_data)
        returns_array = np.array([r[-min_len:] for r in returns_data]).T  # (T, N)

        # Try RiskFolio-Lib first (institutional-grade)
        if HAS_RISKFOLIO and returns_array.shape[0] >= 30:
            try:
                returns_df = pd.DataFrame(
                    returns_array,
                    columns=valid_strategies
                )
                port = rp.Portfolio(returns=returns_df)
                port.assets_stats(
                    method_mu='hist',
                    method_cov='ledoit_wolf'
                )
                cov = port.cov.values * 252  # Annualize

                # Pad with diagonal for missing strategies
                if len(valid_strategies) < n:
                    full_cov = np.eye(n) * 0.01
                    idx_map = {s: i for i, s in enumerate(strategies)}
                    for i, si in enumerate(valid_strategies):
                        for j, sj in enumerate(valid_strategies):
                            full_cov[idx_map[si], idx_map[sj]] = cov[i, j]
                    return full_cov

                return cov
            except Exception as e:
                self.logger.debug("Primary covariance estimation failed, trying LedoitWolf: %s", e)

        # Sklearn Ledoit-Wolf fallback
        try:
            lw = LedoitWolf()
            lw.fit(returns_array)
            cov = lw.covariance_ * 252  # Annualize

            if len(valid_strategies) < n:
                full_cov = np.eye(n) * 0.01
                idx_map = {s: i for i, s in enumerate(strategies)}
                for i, si in enumerate(valid_strategies):
                    for j, sj in enumerate(valid_strategies):
                        full_cov[idx_map[si], idx_map[sj]] = cov[i, j]
                return full_cov

            return cov
        except Exception as e:
            self.logger.warning("LedoitWolf covariance estimation failed, using sample covariance: %s", e, exc_info=True)  # noqa: E501

        # Final fallback: sample covariance
        cov = np.cov(returns_array, rowvar=False) * 252

        if len(valid_strategies) < n:
            full_cov = np.eye(n) * 0.01
            idx_map = {s: i for i, s in enumerate(strategies)}
            for i, si in enumerate(valid_strategies):
                for j, sj in enumerate(valid_strategies):
                    full_cov[idx_map[si], idx_map[sj]] = cov[i, j]
            return full_cov

        return cov

    def _get_correlation_matrix(self, strategies: list[str]) -> np.ndarray:
        """Get correlation matrix for given strategies"""
        n = len(strategies)
        corr_matrix = np.eye(n)

        for i, strat1 in enumerate(strategies):
            for j, strat2 in enumerate(strategies):
                if i < j:
                    returns1 = np.array(self.strategy_returns[strat1])
                    returns2 = np.array(self.strategy_returns[strat2])

                    if len(returns1) > 30 and len(returns2) > 30:
                        min_len = min(len(returns1), len(returns2))
                        corr, _ = pearsonr(returns1[-min_len:], returns2[-min_len:])
                        corr_matrix[i, j] = corr
                        corr_matrix[j, i] = corr

        return corr_matrix

    def _calculate_portfolio_metrics(self, allocations: dict[str, float]) -> dict[str, float]:
        """Calculate portfolio-level metrics"""
        if not allocations:
            return {
                'expected_return': 0,
                'expected_volatility': 0,
                'sharpe_ratio': 0,
                'max_drawdown': 0,
                'diversification_ratio': 0
            }

        # Get strategy returns and weights
        weights = []
        returns = []
        volatilities = []

        for strategy_id, weight in allocations.items():
            if weight > 0:
                metrics = self.strategy_metrics[strategy_id]
                weights.append(weight)
                returns.append(metrics.avg_return * 252)  # Annualized
                volatilities.append(metrics.volatility)

        weights = np.array(weights)
        returns = np.array(returns)
        volatilities = np.array(volatilities)

        # Portfolio return
        portfolio_return = weights @ returns

        # Portfolio volatility (simplified - assumes no correlation)
        # In practice, would use full covariance matrix
        portfolio_vol = np.sqrt(np.sum((weights * volatilities) ** 2))

        # Sharpe ratio
        sharpe = ((portfolio_return - self.risk_free_rate) / portfolio_vol
                 if portfolio_vol > 0 else 0)

        # Max drawdown estimate
        max_dd = np.sum(weights * np.array([
            abs(self.strategy_metrics[s].max_drawdown)
            for s in allocations
        ]))

        # Diversification ratio
        weighted_avg_vol = weights @ volatilities
        div_ratio = weighted_avg_vol / portfolio_vol if portfolio_vol > 0 else 1

        return {
            'expected_return': portfolio_return,
            'expected_volatility': portfolio_vol,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_dd,
            'diversification_ratio': div_ratio
        }

    def _apply_constraints(
        self,
        result: AllocationResult,
        constraints: dict[str, Any] | None
    ) -> AllocationResult:
        """Apply additional constraints to allocation"""
        if not constraints:
            return result

        allocations = result.allocations.copy()

        # Apply maximum position constraints
        if 'max_positions' in constraints:
            max_pos = constraints['max_positions']
            if len(allocations) > max_pos:
                # Keep top allocations
                sorted_allocs = sorted(allocations.items(),
                                     key=lambda x: x[1],
                                     reverse=True)
                allocations = dict(sorted_allocs[:max_pos])

        # Apply sector constraints
        if 'sector_limits' in constraints:
            # Would apply sector-based limits here
            pass

        # Re-normalize
        total = sum(allocations.values())
        if total > 0:
            allocations = {k: v/total for k, v in allocations.items()}

        result.allocations = allocations
        return result

    def _validate_allocations(self, result: AllocationResult) -> AllocationResult:
        """Validate and adjust allocations"""
        allocations = result.allocations.copy()
        warnings = []

        # Check sum to 1
        total = sum(allocations.values())
        if abs(total - 1.0) > 0.001:
            warnings.append(f"Allocations sum to {total:.3f}, normalizing")
            allocations = {k: v/total for k, v in allocations.items()}

        # Check individual limits
        for strategy_id, weight in list(allocations.items()):
            if weight > self.risk_limits[strategy_id]['max_allocation']:
                warnings.append(
                    f"{strategy_id} allocation {weight:.2%} exceeds limit "
                    f"{self.risk_limits[strategy_id]['max_allocation']:.2%}"
                )
                allocations[strategy_id] = self.risk_limits[strategy_id]['max_allocation']

            if weight < MIN_ALLOCATION:
                del allocations[strategy_id]

        # Check minimum strategies
        if len(allocations) < MIN_ACTIVE_STRATEGIES:
            warnings.append(f"Only {len(allocations)} active strategies")
            result.constraints_satisfied = False

        result.allocations = allocations
        result.warnings = warnings

        return result

    def _create_default_allocation(self) -> AllocationResult:
        """Create default safe allocation"""
        # Use top 3 strategies by Sharpe ratio
        sorted_strategies = sorted(
            self.strategy_metrics.items(),
            key=lambda x: x[1].sharpe_ratio,
            reverse=True
        )

        allocations = {}
        for strategy_id, _ in sorted_strategies[:3]:
            allocations[strategy_id] = 1/3

        return AllocationResult(
            allocations=allocations,
            method=AllocationMethod.EQUAL_WEIGHT,
            objective_value=0,
            expected_return=0,
            expected_volatility=0,
            sharpe_ratio=0,
            max_drawdown_estimate=0,
            diversification_ratio=1,
            effective_strategies=3,
            warnings=["Using default allocation"]
        )

    def rebalance_portfolio(
        self,
        target_allocations: dict[str, float] | None = None,
        reason: RebalanceReason = RebalanceReason.SCHEDULED
    ) -> RebalanceEvent:
        """
        Rebalance portfolio to target allocations.

        Args:
            target_allocations: Target allocation weights
            reason: Reason for rebalancing

        Returns:
            RebalanceEvent with trade details
        """
        with self._lock:
            # Use provided targets or optimize new ones
            if target_allocations is None:
                result = self.optimize_allocation()
                target_allocations = result.allocations

            # Calculate required trades
            trades = {}
            for strategy_id in set(list(self.current_allocations.keys()) +
                                  list(target_allocations.keys())):
                current = self.current_allocations.get(strategy_id, 0)
                target = target_allocations.get(strategy_id, 0)
                change = target - current

                if abs(change) > 0.001:  # Minimum change threshold
                    trades[strategy_id] = change * self.total_capital

            # Create rebalance event
            event = RebalanceEvent(
                timestamp=datetime.now(),
                reason=reason,
                old_allocations=self.current_allocations.copy(),
                new_allocations=target_allocations,
                trades_required=trades,
                expected_impact=self._estimate_rebalance_impact(trades)
            )

            # Update current allocations
            self.current_allocations = target_allocations.copy()
            self.target_allocations = target_allocations.copy()

            # Record event
            self.rebalance_history.append(event)

            # Send rebalance message
            self._send_rebalance_message(event)

            self.logger.info(
                f"Portfolio rebalanced: {len(trades)} trades required, "
                f"impact: {event.expected_impact:.2%}"
            )

            return event

    def _estimate_rebalance_impact(self, trades: dict[str, float]) -> float:
        """Estimate market impact of rebalancing"""
        # Simplified impact model
        total_turnover = sum(abs(v) for v in trades.values())
        impact = total_turnover / self.total_capital * 0.001  # 10 bps per 100% turnover
        return impact

    def _send_rebalance_message(self, event: RebalanceEvent):
        """Send rebalance event via message bus"""
        if self.message_bus:
            message = Message(
                topic="portfolio.rebalance",
                sender="MultiStrategyAllocator",
                priority=MessagePriority.HIGH,
                payload={
                    'timestamp': event.timestamp.isoformat(),
                    'trades': event.trades_required,
                    'new_allocations': event.new_allocations,
                    'reason': event.reason.value
                }
            )
            self.message_bus.publish(message)

    def get_portfolio_state(self) -> PortfolioState:
        """Get current portfolio state"""
        allocated = sum(self.current_allocations.values()) * self.total_capital
        active = [s for s, w in self.current_allocations.items() if w > 0.001]

        # Calculate portfolio metrics
        metrics = self._calculate_portfolio_metrics(self.current_allocations)

        # Calculate leverage
        leverage = allocated / self.total_capital

        # Get last rebalance
        last_rebalance = (self.rebalance_history[-1].timestamp
                         if self.rebalance_history else datetime.now())

        return PortfolioState(
            total_capital=self.total_capital,
            allocated_capital=allocated,
            free_capital=self.total_capital - allocated,
            current_allocations=self.current_allocations.copy(),
            active_strategies=active,
            portfolio_return=metrics['expected_return'],
            portfolio_volatility=metrics['expected_volatility'],
            portfolio_sharpe=metrics['sharpe_ratio'],
            leverage=leverage,
            last_rebalance=last_rebalance,
            next_rebalance=last_rebalance + timedelta(days=REBALANCE_FREQUENCY)
        )

    def get_allocation_report(self) -> dict[str, Any]:
        """Get comprehensive allocation report"""
        state = self.get_portfolio_state()

        # Get strategy details
        strategy_details = []
        for strategy_id, weight in self.current_allocations.items():
            if weight > 0:
                metrics = self.strategy_metrics[strategy_id]
                strategy_details.append({
                    'strategy': strategy_id,
                    'weight': weight,
                    'capital': weight * self.total_capital,
                    'sharpe': metrics.sharpe_ratio,
                    'return': metrics.avg_return * 252,
                    'volatility': metrics.volatility,
                    'positions': self.strategy_positions[strategy_id]
                })

        return {
            'timestamp': datetime.now().isoformat(),
            'portfolio_state': asdict(state),
            'strategy_allocations': strategy_details,
            'metrics': {
                'total_strategies': len(STRATEGY_IDS),
                'active_strategies': len(state.active_strategies),
                'portfolio_sharpe': state.portfolio_sharpe,
                'portfolio_return': state.portfolio_return,
                'portfolio_volatility': state.portfolio_volatility,
                'leverage': state.leverage
            },
            'recent_rebalances': len(self.rebalance_history),
            'correlation_warning': len([
                1 for i in range(len(self.correlation_matrix))
                for j in range(i+1, len(self.correlation_matrix))
                if self.correlation_matrix is not None and
                abs(self.correlation_matrix.iloc[i, j]) > MAX_CORRELATION_THRESHOLD
            ]) if self.correlation_matrix is not None else 0
        }

    def shutdown(self):
        """Shutdown allocator and save state"""
        self._shutdown.set()

        # Save allocation history
        try:
            history_file = Path("data/portfolio/allocation_history.json")
            history_file.parent.mkdir(parents=True, exist_ok=True)

            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'allocations': list(self.allocation_history),
                    'rebalances': list(self.rebalance_history),
                    'timestamp': datetime.now()
                }, f, default=_json_default, indent=2)

            self.logger.info("Allocation history saved")
        except Exception as e:
            self.logger.error("Failed to save history: %s", e, exc_info=True)

        self.logger.info("MultiStrategyAllocator shutdown complete")


# ==============================================================================
# FACTORY FUNCTION
# ==============================================================================
def create_multi_strategy_allocator(config: dict[str, Any] | None = None) -> MultiStrategyAllocator:
    """Create and initialize MultiStrategyAllocator instance"""
    return MultiStrategyAllocator(config)


# ==============================================================================
# MAIN EXECUTION (FOR TESTING)
# ==============================================================================
if __name__ == "__main__":
    # Test configuration
    config = {
        'total_capital': 1000000,
        'risk_free_rate': 0.05
    }

    # Create allocator
    allocator = create_multi_strategy_allocator(config)


    # Simulate strategy performance updates

    test_strategies = ['D02_IronCondor', 'D03_CreditSpread', 'D04_ZeroDTE',
                      'D05_Straddle', 'D06_BullPutSpread']

    # Add some fake historical returns
    for _ in range(60):  # 60 days of history
        for strategy in test_strategies:
            # Random returns
            daily_return = np.random.normal(0.001, 0.02)  # 0.1% mean, 2% std
            allocator.update_strategy_performance(strategy, daily_return,
                                                 positions=np.random.randint(1, 10))

    # Test different allocation methods
    methods = [
        AllocationMethod.EQUAL_WEIGHT,
        AllocationMethod.RISK_PARITY,
        AllocationMethod.KELLY_CRITERION,
        AllocationMethod.MEAN_VARIANCE
    ]


    for method in methods:
        result = allocator.optimize_allocation(method=method)


        if result.allocations:
            for _, weight in sorted(result.allocations.items(),
                                         key=lambda x: x[1], reverse=True)[:5]:
                if weight > 0.01:
                    pass

    # Test rebalancing

    event = allocator.rebalance_portfolio(reason=RebalanceReason.SCHEDULED)

    # Get portfolio state
    state = allocator.get_portfolio_state()

    # Get full report
    report = allocator.get_allocation_report()

    # Shutdown
    allocator.shutdown()
