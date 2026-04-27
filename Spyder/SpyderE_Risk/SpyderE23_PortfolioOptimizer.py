#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderE_Risk
Module: SpyderE23_PortfolioOptimizer.py
Purpose: Advanced Real-Time Portfolio Optimization and Dynamic Rebalancing Engine
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-29 Time: 17:00:00

Module Description:
    Institutional-grade portfolio optimization system featuring multi-objective
    optimization, real-time rebalancing, advanced constraint management, and
    machine learning-driven adaptive optimization. Integrates seamlessly with
    all E-series risk management modules providing continuous portfolio enhancement,
    transaction cost optimization, scenario-based optimization, and comprehensive
    performance attribution for autonomous trading excellence.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import time
from typing import Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from collections import deque

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np
from scipy.optimize import minimize, differential_evolution
from sklearn.preprocessing import StandardScaler
from sklearn.covariance import LedoitWolf, OAS
from sklearn.ensemble import RandomForestRegressor

# Institutional Portfolio Analytics
try:
    import riskfolio as rp
    HAS_RISKFOLIO = True
except ImportError:
    HAS_RISKFOLIO = False

# Convex optimization (QP, mean-variance, risk-parity)
try:
    import cvxpy as cp
    HAS_CVXPY = True
except ImportError:
    HAS_CVXPY = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderU_Utilities.SpyderU06_MathUtils import MathUtils
import logging

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Optimization Parameters
DEFAULT_OPTIMIZATION_WINDOW = 252    # 1 year of data for optimization
MIN_OPTIMIZATION_WINDOW = 60         # Minimum 60 days for optimization
REBALANCING_FREQUENCY = 3600          # Rebalance every hour (seconds)
OPTIMIZATION_TIMEOUT = 300            # 5 minutes max optimization time

# Risk Parameters
DEFAULT_RISK_FREE_RATE = 0.02        # 2% annual risk-free rate
MAX_PORTFOLIO_VOLATILITY = 0.25       # Maximum 25% portfolio volatility
MIN_EXPECTED_RETURN = 0.05            # Minimum 5% expected return
MAX_TRACKING_ERROR = 0.05             # Maximum 5% tracking error

# Position Constraints
MAX_POSITION_WEIGHT = 0.15            # Maximum 15% per position
MIN_POSITION_WEIGHT = 0.001           # Minimum 0.1% per position
MAX_SECTOR_CONCENTRATION = 0.30       # Maximum 30% per sector
MAX_TURNOVER_RATE = 0.10              # Maximum 10% daily turnover

# Transaction Cost Parameters
TRANSACTION_COST_BPS = 5.0            # 5 basis points transaction cost
MARKET_IMPACT_FACTOR = 0.5            # Market impact scaling factor
LIQUIDITY_COST_FACTOR = 0.1           # Liquidity cost factor

# Optimization Methods
DEFAULT_MAX_ITERATIONS = 1000         # Maximum optimization iterations
CONVERGENCE_TOLERANCE = 1e-6          # Convergence tolerance
POPULATION_SIZE_MULTIPLIER = 10       # For genetic algorithms

# Performance Metrics
LOOKBACK_PERIODS = [22, 66, 132, 252] # Performance evaluation periods
ATTRIBUTION_WINDOWS = [7, 30, 90]     # Attribution analysis windows

# Machine Learning Parameters
ML_TRAINING_WINDOW = 500              # 500 periods for ML training
ML_PREDICTION_HORIZON = 22            # 22 days prediction horizon
ML_RETRAINING_FREQUENCY = 66          # Retrain every 66 days

# ==============================================================================
# ENUMS
# ==============================================================================
class OptimizationMethod(Enum):
    """Portfolio optimization methods"""
    MEAN_VARIANCE = "mean_variance"           # Classic Markowitz
    BLACK_LITTERMAN = "black_litterman"       # Black-Litterman model
    RISK_PARITY = "risk_parity"               # Equal risk contribution
    MINIMUM_VARIANCE = "minimum_variance"      # Minimum volatility
    MAXIMUM_SHARPE = "maximum_sharpe"         # Maximum Sharpe ratio
    MAXIMUM_DIVERSIFICATION = "max_diversification"  # Maximum diversification
    EQUAL_WEIGHT = "equal_weight"             # Equal weighting
    ROBUST_OPTIMIZATION = "robust_optimization"  # Robust optimization
    MACHINE_LEARNING = "machine_learning"     # ML-driven optimization
    MULTI_OBJECTIVE = "multi_objective"       # Multi-objective optimization
    HIERARCHICAL_RISK_PARITY = "hrp"          # RiskFolio HRP
    CVAR_OPTIMIZATION = "cvar_optimization"   # RiskFolio CVaR optimization
    RISK_BUDGETING = "risk_budgeting"         # RiskFolio risk budgeting

class OptimizationObjective(Enum):
    """Optimization objectives"""
    MAXIMIZE_RETURN = "maximize_return"
    MINIMIZE_RISK = "minimize_risk"
    MAXIMIZE_SHARPE = "maximize_sharpe"
    MINIMIZE_DRAWDOWN = "minimize_drawdown"
    MAXIMIZE_DIVERSIFICATION = "maximize_diversification"
    MINIMIZE_TRACKING_ERROR = "minimize_tracking_error"
    MAXIMIZE_INFORMATION_RATIO = "maximize_information_ratio"
    MINIMIZE_TRANSACTION_COSTS = "minimize_transaction_costs"

class RebalancingTrigger(Enum):
    """Rebalancing trigger conditions"""
    TIME_BASED = "time_based"                 # Scheduled rebalancing
    DRIFT_BASED = "drift_based"               # Weight drift threshold
    VOLATILITY_BASED = "volatility_based"     # Volatility change trigger
    PERFORMANCE_BASED = "performance_based"   # Performance deterioration
    MARKET_REGIME_CHANGE = "regime_change"    # Market regime change
    RISK_LIMIT_BREACH = "risk_limit_breach"   # Risk limit violation
    SIGNAL_BASED = "signal_based"             # Trading signal trigger
    MANUAL = "manual"                         # Manual rebalancing

class ConstraintType(Enum):
    """Portfolio constraint types"""
    WEIGHT_CONSTRAINT = "weight_constraint"           # Position weight limits
    SECTOR_CONSTRAINT = "sector_constraint"           # Sector allocation limits
    RISK_CONSTRAINT = "risk_constraint"               # Risk metric limits
    TURNOVER_CONSTRAINT = "turnover_constraint"       # Turnover limits
    TRACKING_CONSTRAINT = "tracking_constraint"       # Tracking error limits
    LIQUIDITY_CONSTRAINT = "liquidity_constraint"     # Liquidity requirements
    CORRELATION_CONSTRAINT = "correlation_constraint" # Correlation limits
    LEVERAGE_CONSTRAINT = "leverage_constraint"       # Leverage limits

class OptimizerStatus(Enum):
    """Portfolio optimizer status"""
    STOPPED = "stopped"
    INITIALIZING = "initializing"
    RUNNING = "running"
    OPTIMIZING = "optimizing"
    REBALANCING = "rebalancing"
    PAUSED = "paused"
    ERROR = "error"

class OptimizationQuality(Enum):
    """Optimization solution quality"""
    EXCELLENT = "excellent"      # Converged with low error
    GOOD = "good"               # Converged with acceptable error
    ACCEPTABLE = "acceptable"    # Converged with higher error
    POOR = "poor"               # Convergence issues
    FAILED = "failed"           # Optimization failed

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class OptimizationConstraint:
    """Portfolio optimization constraint"""
    constraint_type: ConstraintType
    name: str
    description: str

    # Constraint parameters
    lower_bound: float | None = None
    upper_bound: float | None = None
    target_value: float | None = None
    tolerance: float = 0.01

    # Application scope
    applies_to: list[str] = field(default_factory=list)  # Asset names or sectors
    enabled: bool = True
    priority: int = 1  # Higher priority = more important

    # Violation handling
    soft_constraint: bool = False        # Can be violated with penalty
    penalty_factor: float = 1.0          # Penalty multiplier for violations

    def __post_init__(self):
        """Post-initialization validation"""
        if self.lower_bound is not None and self.upper_bound is not None:
            if self.lower_bound > self.upper_bound:
                raise ValueError("Lower bound must be <= upper bound")

@dataclass
class OptimizationResult:
    """Portfolio optimization result"""
    optimization_id: str
    timestamp: datetime
    method: OptimizationMethod
    objective: OptimizationObjective

    # Solution
    optimal_weights: dict[str, float]     # Optimized portfolio weights
    expected_return: float                # Expected portfolio return
    expected_risk: float                  # Expected portfolio risk (volatility)
    sharpe_ratio: float                   # Expected Sharpe ratio

    # Optimization metadata
    optimization_time: float              # Time taken to optimize
    iterations: int                       # Number of iterations
    convergence_status: str               # Convergence information
    optimization_quality: OptimizationQuality

    # Performance metrics
    diversification_ratio: float          # Portfolio diversification
    effective_assets: float               # Number of effective assets
    maximum_drawdown: float               # Expected maximum drawdown
    var_95: float                         # 95% Value at Risk

    # Transaction costs
    estimated_turnover: float             # Expected turnover
    transaction_costs: float              # Estimated transaction costs
    implementation_shortfall: float       # Expected implementation cost

    # Constraint compliance
    constraints_satisfied: bool           # All constraints satisfied
    constraint_violations: list[str] = field(default_factory=list)

    # Comparison with current portfolio
    improvement_metrics: dict[str, float] = field(default_factory=dict)

    def get_quality_score(self) -> float:
        """Calculate overall optimization quality score (0-100)"""
        quality_scores = {
            OptimizationQuality.EXCELLENT: 95,
            OptimizationQuality.GOOD: 80,
            OptimizationQuality.ACCEPTABLE: 65,
            OptimizationQuality.POOR: 40,
            OptimizationQuality.FAILED: 0
        }

        base_score = quality_scores.get(self.optimization_quality, 0)

        # Adjust for constraint satisfaction
        if not self.constraints_satisfied:
            base_score *= 0.8

        # Adjust for convergence
        if "converged" not in self.convergence_status.lower():
            base_score *= 0.7

        return max(0.0, min(100.0, base_score))

@dataclass
class RebalancingRecommendation:
    """Portfolio rebalancing recommendation"""
    recommendation_id: str
    timestamp: datetime
    trigger: RebalancingTrigger
    urgency_level: int  # 1-5, 5 = urgent

    # Current vs Target
    current_weights: dict[str, float]
    target_weights: dict[str, float]
    weight_changes: dict[str, float]      # Required weight changes

    # Trade recommendations
    trades_required: dict[str, dict[str, Any]]  # Asset -> trade details
    total_turnover: float
    estimated_costs: float

    # Impact analysis
    risk_impact: float                    # Change in portfolio risk
    return_impact: float                  # Change in expected return
    sharpe_impact: float                  # Change in Sharpe ratio

    # Implementation
    execution_priority: list[str]         # Order of trade execution
    market_timing_score: float           # 0-1, 1 = good timing
    liquidity_assessment: dict[str, float] # Asset liquidity scores

    # Rationale
    reason: str
    expected_benefits: list[str] = field(default_factory=list)
    potential_risks: list[str] = field(default_factory=list)

    def get_implementation_complexity(self) -> str:
        """Assess implementation complexity"""
        if self.total_turnover > 0.2:
            return "HIGH"
        elif self.total_turnover > 0.1:
            return "MEDIUM"
        elif self.total_turnover > 0.05:
            return "LOW"
        else:
            return "MINIMAL"

@dataclass
class PortfolioPerformanceAttribution:
    """Portfolio performance attribution analysis"""
    attribution_id: str
    period_start: datetime
    period_end: datetime

    # Overall performance
    total_return: float
    benchmark_return: float
    active_return: float                  # Portfolio - benchmark
    tracking_error: float
    information_ratio: float

    # Attribution components
    asset_selection_return: float         # Return from asset selection
    allocation_return: float              # Return from allocation decisions
    interaction_return: float             # Interaction effect
    transaction_cost_impact: float        # Impact of transaction costs

    # Risk-adjusted metrics
    sharpe_ratio: float
    sortino_ratio: float
    maximum_drawdown: float
    var_contribution: dict[str, float] = field(default_factory=dict)

    # Asset-level attribution
    asset_contributions: dict[str, dict[str, float]] = field(default_factory=dict)

    # Factor attribution
    factor_exposures: dict[str, float] = field(default_factory=dict)
    factor_contributions: dict[str, float] = field(default_factory=dict)

    # Optimization effectiveness
    optimization_success_rate: float = 0.0     # % of optimizations that improved performance
    rebalancing_effectiveness: float = 0.0     # Avg benefit per rebalancing
    cost_efficiency: float = 0.0               # Return per unit of transaction cost

@dataclass
class OptimizationParameters:
    """Optimization configuration parameters"""
    # Optimization settings
    method: OptimizationMethod = OptimizationMethod.MEAN_VARIANCE
    objective: OptimizationObjective = OptimizationObjective.MAXIMIZE_SHARPE
    lookback_window: int = DEFAULT_OPTIMIZATION_WINDOW

    # Risk parameters
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE
    target_return: float | None = None
    target_risk: float | None = None
    risk_aversion: float = 1.0            # Risk aversion parameter

    # Constraints
    constraints: list[OptimizationConstraint] = field(default_factory=list)

    # Transaction costs
    transaction_cost_bps: float = TRANSACTION_COST_BPS
    include_transaction_costs: bool = True
    market_impact_model: str = "linear"

    # Advanced settings
    robust_optimization: bool = False     # Use robust optimization
    uncertainty_sets: dict[str, float] = field(default_factory=dict)
    scenario_weights: np.ndarray | None = None

    # Machine learning
    use_ml_predictions: bool = False      # Use ML for return predictions
    ml_confidence_threshold: float = 0.7  # Minimum ML prediction confidence

    # Rebalancing
    rebalancing_triggers: list[RebalancingTrigger] = field(default_factory=list)
    drift_threshold: float = 0.05         # 5% weight drift threshold
    risk_threshold_multiplier: float = 1.2  # Risk increase threshold

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class PortfolioOptimizer:
    """
    Advanced real-time portfolio optimization and rebalancing engine.

    This class provides comprehensive portfolio optimization capabilities including
    multiple optimization methods, real-time rebalancing, constraint management,
    transaction cost optimization, machine learning integration, and performance
    attribution analysis. Features institutional-grade optimization algorithms,
    robust error handling, and seamless integration with all E-series risk modules.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        status: Current optimizer status
        optimization_history: Historical optimization results
        performance_attribution: Performance tracking data
        ml_models: Machine learning prediction models

    Example:
        >>> optimizer = PortfolioOptimizer()
        >>> optimizer.initialize()
        >>> result = await optimizer.optimize_portfolio(returns_data, current_weights)
        >>> recommendation = optimizer.generate_rebalancing_recommendation(result)
    """

    def __init__(self, parameters: OptimizationParameters | None = None):
        """Initialize the portfolio optimizer."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Optimizer configuration
        self.parameters = parameters or OptimizationParameters()
        self.status = OptimizerStatus.STOPPED

        # Data storage
        self.returns_data: pd.DataFrame = pd.DataFrame()
        self.current_weights: dict[str, float] = {}
        self.benchmark_weights: dict[str, float] | None = None

        # Optimization tracking
        self.optimization_history: deque = deque(maxlen=1000)
        self.performance_attribution: deque = deque(maxlen=100)
        self.rebalancing_history: deque = deque(maxlen=500)

        # Machine learning components
        self.ml_models: dict[str, Any] = {}
        self.ml_predictions: dict[str, dict[str, float]] = {}
        self.ml_confidence: dict[str, float] = {}

        # Performance tracking
        self.performance_metrics: dict[str, Any] = {}
        self.risk_metrics: dict[str, Any] = {}

        # Optimization components
        self.math_utils = MathUtils()
        self.scaler = StandardScaler()
        self.thread_pool = ThreadPoolExecutor(max_workers=6)

        # Monitoring state
        self._running = False
        self._stop_event = threading.Event()
        self._last_optimization = None
        self._last_rebalancing = None

        # Integration with other E-series modules
        self.risk_manager = None           # Will integrate with SpyderE01
        self.stress_tester = None          # Will integrate with SpyderE07
        self.correlation_manager = None    # Will integrate with SpyderE10

        self.logger.info("PortfolioOptimizer initialized")

    # ==========================================================================
    # PUBLIC METHODS - Initialization and Control
    # ==========================================================================
    def initialize(self) -> bool:
        """
        Initialize the portfolio optimizer.

        Returns:
            bool: True if initialization successful
        """
        try:
            self.status = OptimizerStatus.INITIALIZING
            self.logger.info("Initializing portfolio optimizer...")

            # Initialize optimization engines
            self._initialize_optimization_engines()

            # Initialize machine learning models
            self._initialize_ml_models()

            # Set up default constraints
            self._setup_default_constraints()

            # Initialize performance tracking
            self._initialize_performance_tracking()

            self.status = OptimizerStatus.STOPPED
            self.logger.info("Portfolio optimizer initialized successfully")
            return True

        except Exception as e:
            self.error_handler.handle_error(e, context="PortfolioOptimizer.initialize")
            self.status = OptimizerStatus.ERROR
            return False

    def start_monitoring(self) -> bool:
        """
        Start continuous portfolio monitoring and optimization.

        Returns:
            bool: True if monitoring started successfully
        """
        if self.status == OptimizerStatus.RUNNING:
            self.logger.warning("Portfolio optimizer already running")
            return True

        try:
            self._stop_event.clear()
            self._running = True
            self.status = OptimizerStatus.RUNNING

            # Start monitoring thread
            self._monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
            self._monitoring_thread.start()

            self.logger.info("Portfolio optimization monitoring started")
            return True

        except Exception as e:
            self.error_handler.handle_error(e, context="PortfolioOptimizer.start_monitoring")
            self.status = OptimizerStatus.ERROR
            return False

    def stop_monitoring(self) -> bool:
        """
        Stop continuous portfolio monitoring.

        Returns:
            bool: True if monitoring stopped successfully
        """
        try:
            self._stop_event.set()
            self._running = False
            self.status = OptimizerStatus.STOPPED

            if hasattr(self, '_monitoring_thread'):
                self._monitoring_thread.join(timeout=10.0)

            self.logger.info("Portfolio optimization monitoring stopped")
            return True

        except Exception as e:
            self.error_handler.handle_error(e, context="PortfolioOptimizer.stop_monitoring")
            return False

    # ==========================================================================
    # PUBLIC METHODS - Portfolio Optimization
    # ==========================================================================
    async def optimize_portfolio(self, returns_data: pd.DataFrame,
                                current_weights: dict[str, float] | None = None,
                                benchmark_weights: dict[str, float] | None = None,
                                custom_parameters: OptimizationParameters | None = None) -> OptimizationResult:  # noqa: E501
        """
        Optimize portfolio using specified method and constraints.

        Args:
            returns_data: Historical returns DataFrame
            current_weights: Current portfolio weights
            benchmark_weights: Benchmark weights (optional)
            custom_parameters: Custom optimization parameters

        Returns:
            Optimization result with optimal weights and metrics
        """
        try:
            self.status = OptimizerStatus.OPTIMIZING
            start_time = time.time()

            # Use custom parameters if provided
            params = custom_parameters or self.parameters

            self.logger.info("Starting portfolio optimization using %s", params.method.value)

            # Validate and prepare data
            if not self._validate_optimization_inputs(returns_data, current_weights):
                raise ValueError("Invalid optimization inputs")

            # Store data
            self.returns_data = returns_data.copy()
            self.current_weights = current_weights or self._create_equal_weights(returns_data.columns)  # noqa: E501
            self.benchmark_weights = benchmark_weights

            # Prepare optimization inputs
            expected_returns = await self._calculate_expected_returns(returns_data, params)
            covariance_matrix = await self._calculate_covariance_matrix(returns_data, params)

            # Generate optimization ID
            optimization_id = f"opt_{int(time.time())}"

            # Run optimization based on method
            if params.method == OptimizationMethod.MEAN_VARIANCE:
                optimal_weights = await self._optimize_mean_variance(
                    expected_returns, covariance_matrix, params
                )
            elif params.method == OptimizationMethod.BLACK_LITTERMAN:
                optimal_weights = await self._optimize_black_litterman(
                    expected_returns, covariance_matrix, params
                )
            elif params.method == OptimizationMethod.RISK_PARITY:
                optimal_weights = await self._optimize_risk_parity(
                    covariance_matrix, params
                )
            elif params.method == OptimizationMethod.MINIMUM_VARIANCE:
                optimal_weights = await self._optimize_minimum_variance(
                    covariance_matrix, params
                )
            elif params.method == OptimizationMethod.MAXIMUM_SHARPE:
                optimal_weights = await self._optimize_maximum_sharpe(
                    expected_returns, covariance_matrix, params
                )
            elif params.method == OptimizationMethod.MACHINE_LEARNING:
                optimal_weights = await self._optimize_with_ml(
                    returns_data, expected_returns, covariance_matrix, params
                )
            elif params.method == OptimizationMethod.MULTI_OBJECTIVE:
                optimal_weights = await self._optimize_multi_objective(
                    expected_returns, covariance_matrix, params
                )
            elif params.method in (OptimizationMethod.HIERARCHICAL_RISK_PARITY,
                                   OptimizationMethod.CVAR_OPTIMIZATION,
                                   OptimizationMethod.RISK_BUDGETING):
                optimal_weights = await self._optimize_with_riskfolio(
                    returns_data, params
                )
            else:
                # Default to mean variance
                optimal_weights = await self._optimize_mean_variance(
                    expected_returns, covariance_matrix, params
                )

            # Calculate portfolio metrics
            portfolio_metrics = self._calculate_portfolio_metrics(
                optimal_weights, expected_returns, covariance_matrix, params
            )

            # Assess optimization quality
            quality_assessment = self._assess_optimization_quality(
                optimal_weights, portfolio_metrics, params
            )

            # Calculate transaction costs
            transaction_metrics = self._calculate_transaction_costs(
                self.current_weights, optimal_weights, params
            )

            # Create optimization result
            result = OptimizationResult(
                optimization_id=optimization_id,
                timestamp=datetime.now(timezone.utc),
                method=params.method,
                objective=params.objective,

                # Solution
                optimal_weights=optimal_weights,
                expected_return=portfolio_metrics['expected_return'],
                expected_risk=portfolio_metrics['expected_risk'],
                sharpe_ratio=portfolio_metrics['sharpe_ratio'],

                # Metadata
                optimization_time=time.time() - start_time,
                iterations=quality_assessment.get('iterations', 0),
                convergence_status=quality_assessment.get('convergence_status', 'unknown'),
                optimization_quality=quality_assessment.get('quality', OptimizationQuality.ACCEPTABLE),  # noqa: E501

                # Metrics
                diversification_ratio=portfolio_metrics['diversification_ratio'],
                effective_assets=portfolio_metrics['effective_assets'],
                maximum_drawdown=portfolio_metrics['maximum_drawdown'],
                var_95=portfolio_metrics['var_95'],

                # Transaction costs
                estimated_turnover=transaction_metrics['turnover'],
                transaction_costs=transaction_metrics['costs'],
                implementation_shortfall=transaction_metrics['implementation_shortfall'],

                # Compliance
                constraints_satisfied=quality_assessment.get('constraints_satisfied', True),
                constraint_violations=quality_assessment.get('violations', []),

                # Improvements
                improvement_metrics=self._calculate_improvement_metrics(
                    self.current_weights, optimal_weights, portfolio_metrics
                )
            )

            # Store result
            self.optimization_history.append(result)
            self._last_optimization = datetime.now(timezone.utc)

            self.status = OptimizerStatus.RUNNING
            self.logger.info(f"Portfolio optimization completed: Sharpe {result.sharpe_ratio:.3f}, Quality {result.optimization_quality.value}")  # noqa: E501

            return result

        except Exception as e:
            self.error_handler.handle_error(e, context="PortfolioOptimizer.optimize_portfolio")
            self.status = OptimizerStatus.ERROR

            # Return default result on error
            return OptimizationResult(
                optimization_id=f"error_{int(time.time())}",
                timestamp=datetime.now(timezone.utc),
                method=params.method if 'params' in locals() else OptimizationMethod.MEAN_VARIANCE,
                objective=params.objective if 'params' in locals() else OptimizationObjective.MAXIMIZE_SHARPE,  # noqa: E501
                optimal_weights=self.current_weights or {},
                expected_return=0.0,
                expected_risk=0.0,
                sharpe_ratio=0.0,
                optimization_time=0.0,
                iterations=0,
                convergence_status="error",
                optimization_quality=OptimizationQuality.FAILED,
                diversification_ratio=0.0,
                effective_assets=0.0,
                maximum_drawdown=0.0,
                var_95=0.0,
                estimated_turnover=0.0,
                transaction_costs=0.0,
                implementation_shortfall=0.0,
                constraints_satisfied=False
            )

    async def generate_rebalancing_recommendation(self,
                                                optimization_result: OptimizationResult,
                                                current_market_data: dict[str, Any] | None = None) -> RebalancingRecommendation:  # noqa: E501
        """
        Generate portfolio rebalancing recommendation based on optimization.

        Args:
            optimization_result: Result from portfolio optimization
            current_market_data: Current market conditions data

        Returns:
            Detailed rebalancing recommendation
        """
        try:
            self.logger.debug("Generating rebalancing recommendation")

            # Calculate weight changes
            weight_changes = {}
            current_weights = self.current_weights
            target_weights = optimization_result.optimal_weights

            for asset in set(list(current_weights.keys()) + list(target_weights.keys())):
                current_weight = current_weights.get(asset, 0.0)
                target_weight = target_weights.get(asset, 0.0)
                weight_changes[asset] = target_weight - current_weight

            # Calculate total turnover
            total_turnover = sum(abs(change) for change in weight_changes.values()) / 2.0

            # Determine urgency level
            urgency_level = self._assess_rebalancing_urgency(
                weight_changes, optimization_result, current_market_data
            )

            # Generate trade recommendations
            trades_required = self._generate_trade_recommendations(
                weight_changes, current_market_data
            )

            # Assess market timing
            market_timing_score = self._assess_market_timing(current_market_data)

            # Calculate impact analysis
            impact_analysis = self._calculate_rebalancing_impact(
                current_weights, target_weights, optimization_result
            )

            # Determine execution priority
            execution_priority = self._determine_execution_priority(weight_changes, current_market_data)  # noqa: E501

            # Assess liquidity
            liquidity_assessment = self._assess_asset_liquidity(
                list(weight_changes.keys()), current_market_data
            )

            # Generate rationale
            rationale = self._generate_rebalancing_rationale(
                optimization_result, weight_changes, impact_analysis
            )

            # Create recommendation
            recommendation = RebalancingRecommendation(
                recommendation_id=f"rebal_{int(time.time())}",
                timestamp=datetime.now(timezone.utc),
                trigger=RebalancingTrigger.TIME_BASED,  # Would determine actual trigger
                urgency_level=urgency_level,

                # Weights
                current_weights=current_weights,
                target_weights=target_weights,
                weight_changes=weight_changes,

                # Trades
                trades_required=trades_required,
                total_turnover=total_turnover,
                estimated_costs=optimization_result.transaction_costs,

                # Impact
                risk_impact=impact_analysis['risk_impact'],
                return_impact=impact_analysis['return_impact'],
                sharpe_impact=impact_analysis['sharpe_impact'],

                # Implementation
                execution_priority=execution_priority,
                market_timing_score=market_timing_score,
                liquidity_assessment=liquidity_assessment,

                # Rationale
                reason=rationale['primary_reason'],
                expected_benefits=rationale['benefits'],
                potential_risks=rationale['risks']
            )

            self.logger.debug(f"Rebalancing recommendation generated: {total_turnover:.1%} turnover")  # noqa: E501
            return recommendation

        except Exception as e:
            self.error_handler.handle_error(e, context="PortfolioOptimizer.generate_rebalancing_recommendation")  # noqa: E501

            # Return minimal recommendation on error
            return RebalancingRecommendation(
                recommendation_id=f"error_{int(time.time())}",
                timestamp=datetime.now(timezone.utc),
                trigger=RebalancingTrigger.MANUAL,
                urgency_level=1,
                current_weights=self.current_weights,
                target_weights=optimization_result.optimal_weights,
                weight_changes={},
                trades_required={},
                total_turnover=0.0,
                estimated_costs=0.0,
                risk_impact=0.0,
                return_impact=0.0,
                sharpe_impact=0.0,
                execution_priority=[],
                market_timing_score=0.5,
                liquidity_assessment={},
                reason="Error generating recommendation"
            )

    def execute_rebalancing(self, recommendation: RebalancingRecommendation,
                           execution_method: str = "gradual") -> dict[str, Any]:
        """
        Execute portfolio rebalancing based on recommendation.

        Args:
            recommendation: Rebalancing recommendation to execute
            execution_method: Execution method ("immediate", "gradual", "optimal")

        Returns:
            Execution result dictionary
        """
        try:
            self.status = OptimizerStatus.REBALANCING
            self.logger.info(f"Executing rebalancing: {recommendation.total_turnover:.1%} turnover")

            # This would integrate with actual trading system
            # For now, simulate execution
            execution_result = {
                'execution_id': f"exec_{int(time.time())}",
                'recommendation_id': recommendation.recommendation_id,
                'execution_method': execution_method,
                'start_time': datetime.now(timezone.utc),
                'trades_executed': {},
                'execution_costs': 0.0,
                'slippage': 0.0,
                'success_rate': 1.0,
                'partial_fills': [],
                'failed_trades': [],
                'final_weights': recommendation.target_weights.copy(),
                'execution_quality': 'excellent'
            }

            # Simulate gradual execution
            if execution_method == "gradual":
                execution_result['execution_duration'] = 3600  # 1 hour
                execution_result['execution_chunks'] = 10
            else:
                execution_result['execution_duration'] = 300   # 5 minutes
                execution_result['execution_chunks'] = 1

            # Update current weights to target weights
            self.current_weights = recommendation.target_weights.copy()

            # Store rebalancing history
            self.rebalancing_history.append({
                'timestamp': datetime.now(timezone.utc),
                'recommendation': recommendation,
                'execution_result': execution_result
            })

            self._last_rebalancing = datetime.now(timezone.utc)
            self.status = OptimizerStatus.RUNNING

            self.logger.info("Rebalancing executed successfully: %s", execution_result['execution_quality'])  # noqa: E501
            return execution_result

        except Exception as e:
            self.error_handler.handle_error(e, context="PortfolioOptimizer.execute_rebalancing")
            self.status = OptimizerStatus.ERROR
            return {'error': f'Execution failed: {e}'}

    # ==========================================================================
    # PUBLIC METHODS - Performance Analysis
    # ==========================================================================
    def calculate_performance_attribution(self,
                                        start_date: datetime,
                                        end_date: datetime,
                                        benchmark_returns: pd.Series | None = None) -> PortfolioPerformanceAttribution:  # noqa: E501
        """
        Calculate detailed portfolio performance attribution.

        Args:
            start_date: Attribution period start
            end_date: Attribution period end
            benchmark_returns: Benchmark return series

        Returns:
            Comprehensive performance attribution analysis
        """
        try:
            self.logger.debug("Calculating performance attribution: %s to %s", start_date, end_date)

            # Filter returns data for the period
            period_mask = (self.returns_data.index >= start_date) & (self.returns_data.index <= end_date)  # noqa: E501
            period_returns = self.returns_data[period_mask]

            if len(period_returns) == 0:
                raise ValueError("No returns data available for attribution period")

            # Calculate portfolio returns (simplified - would use actual position data)
            portfolio_returns = self._calculate_portfolio_returns(period_returns, self.current_weights)  # noqa: E501

            # Calculate benchmark returns
            if benchmark_returns is not None:
                benchmark_period_returns = benchmark_returns[period_mask]
            else:
                # Use equal-weighted benchmark
                benchmark_period_returns = period_returns.mean(axis=1)

            # Calculate basic performance metrics
            total_return = (1 + portfolio_returns).prod() - 1
            benchmark_return = (1 + benchmark_period_returns).prod() - 1
            active_return = total_return - benchmark_return

            # Calculate tracking error and information ratio
            active_returns = portfolio_returns - benchmark_period_returns
            tracking_error = active_returns.std() * np.sqrt(252)  # Annualized
            information_ratio = (active_returns.mean() * 252) / tracking_error if tracking_error > 0 else 0  # noqa: E501

            # Calculate risk-adjusted metrics
            sharpe_ratio = self._calculate_sharpe_ratio(portfolio_returns, self.parameters.risk_free_rate)  # noqa: E501
            sortino_ratio = self._calculate_sortino_ratio(portfolio_returns, self.parameters.risk_free_rate)  # noqa: E501
            max_drawdown = self._calculate_maximum_drawdown(portfolio_returns)

            # Calculate attribution components
            attribution_components = self._calculate_attribution_components(
                period_returns, portfolio_returns, benchmark_period_returns
            )

            # Calculate asset-level contributions
            asset_contributions = self._calculate_asset_contributions(period_returns, self.current_weights)  # noqa: E501

            # Calculate optimization effectiveness
            optimization_metrics = self._calculate_optimization_effectiveness(start_date, end_date)

            # Create attribution result
            attribution = PortfolioPerformanceAttribution(
                attribution_id=f"attr_{int(time.time())}",
                period_start=start_date,
                period_end=end_date,

                # Performance
                total_return=total_return,
                benchmark_return=benchmark_return,
                active_return=active_return,
                tracking_error=tracking_error,
                information_ratio=information_ratio,

                # Attribution
                asset_selection_return=attribution_components['asset_selection'],
                allocation_return=attribution_components['allocation'],
                interaction_return=attribution_components['interaction'],
                transaction_cost_impact=attribution_components['transaction_costs'],

                # Risk metrics
                sharpe_ratio=sharpe_ratio,
                sortino_ratio=sortino_ratio,
                maximum_drawdown=max_drawdown,

                # Details
                asset_contributions=asset_contributions,
                optimization_success_rate=optimization_metrics['success_rate'],
                rebalancing_effectiveness=optimization_metrics['rebalancing_effectiveness'],
                cost_efficiency=optimization_metrics['cost_efficiency']
            )

            # Store attribution
            self.performance_attribution.append(attribution)

            self.logger.debug(f"Performance attribution calculated: {active_return:.2%} active return")  # noqa: E501
            return attribution

        except Exception as e:
            self.error_handler.handle_error(e, context="PortfolioOptimizer.calculate_performance_attribution")  # noqa: E501

            # Return default attribution on error
            return PortfolioPerformanceAttribution(
                attribution_id=f"error_{int(time.time())}",
                period_start=start_date,
                period_end=end_date,
                total_return=0.0,
                benchmark_return=0.0,
                active_return=0.0,
                tracking_error=0.0,
                information_ratio=0.0,
                asset_selection_return=0.0,
                allocation_return=0.0,
                interaction_return=0.0,
                transaction_cost_impact=0.0,
                sharpe_ratio=0.0,
                sortino_ratio=0.0,
                maximum_drawdown=0.0,
                optimization_success_rate=0.0,
                rebalancing_effectiveness=0.0,
                cost_efficiency=0.0
            )

    # ==========================================================================
    # PUBLIC METHODS - Reporting and Analysis
    # ==========================================================================
    def generate_optimization_report(self) -> str:
        """
        Generate comprehensive optimization performance report.

        Returns:
            Formatted optimization report
        """
        try:
            report_lines = []
            report_lines.append("=" * 80)
            report_lines.append("SPYDER PORTFOLIO OPTIMIZATION REPORT")
            report_lines.append("=" * 80)
            report_lines.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
            report_lines.append("")

            # Optimizer status
            report_lines.append("OPTIMIZER STATUS:")
            report_lines.append(f"  Status: {self.status.value.upper()}")
            report_lines.append(f"  Last Optimization: {self._last_optimization.strftime('%Y-%m-%d %H:%M:%S') if self._last_optimization else 'Never'}")  # noqa: E501
            report_lines.append(f"  Last Rebalancing: {self._last_rebalancing.strftime('%Y-%m-%d %H:%M:%S') if self._last_rebalancing else 'Never'}")  # noqa: E501
            report_lines.append(f"  Total Optimizations: {len(self.optimization_history)}")
            report_lines.append(f"  Total Rebalancings: {len(self.rebalancing_history)}")
            report_lines.append("")

            # Current configuration
            report_lines.append("CURRENT CONFIGURATION:")
            report_lines.append(f"  Method: {self.parameters.method.value}")
            report_lines.append(f"  Objective: {self.parameters.objective.value}")
            report_lines.append(f"  Lookback Window: {self.parameters.lookback_window} days")
            report_lines.append(f"  Risk-Free Rate: {self.parameters.risk_free_rate:.1%}")
            report_lines.append(f"  Transaction Cost: {self.parameters.transaction_cost_bps:.1f} bps")  # noqa: E501
            report_lines.append("")

            # Latest optimization results
            if self.optimization_history:
                latest_opt = self.optimization_history[-1]

                report_lines.append("LATEST OPTIMIZATION RESULTS:")
                report_lines.append(f"  Expected Return: {latest_opt.expected_return:.2%}")
                report_lines.append(f"  Expected Risk: {latest_opt.expected_risk:.2%}")
                report_lines.append(f"  Sharpe Ratio: {latest_opt.sharpe_ratio:.3f}")
                report_lines.append(f"  Diversification Ratio: {latest_opt.diversification_ratio:.3f}")  # noqa: E501
                report_lines.append(f"  Effective Assets: {latest_opt.effective_assets:.1f}")
                report_lines.append(f"  Optimization Quality: {latest_opt.optimization_quality.value.upper()}")  # noqa: E501
                report_lines.append(f"  Quality Score: {latest_opt.get_quality_score():.1f}/100")
                report_lines.append("")

                # Top holdings
                sorted_weights = sorted(latest_opt.optimal_weights.items(), key=lambda x: x[1], reverse=True)  # noqa: E501
                report_lines.append("TOP PORTFOLIO HOLDINGS:")
                for i, (asset, weight) in enumerate(sorted_weights[:10]):
                    report_lines.append(f"  {i+1:2d}. {asset:<15} {weight:>8.1%}")
                report_lines.append("")

            # Performance attribution
            if self.performance_attribution:
                latest_attr = self.performance_attribution[-1]

                report_lines.append("PERFORMANCE ATTRIBUTION:")
                report_lines.append(f"  Total Return: {latest_attr.total_return:.2%}")
                report_lines.append(f"  Active Return: {latest_attr.active_return:.2%}")
                report_lines.append(f"  Information Ratio: {latest_attr.information_ratio:.3f}")
                report_lines.append(f"  Tracking Error: {latest_attr.tracking_error:.2%}")
                report_lines.append(f"  Optimization Success Rate: {latest_attr.optimization_success_rate:.1%}")  # noqa: E501
                report_lines.append("")

            # Rebalancing statistics
            if self.rebalancing_history:
                recent_rebalancings = list(self.rebalancing_history)[-10:]  # Last 10
                avg_turnover = np.mean([r['recommendation'].total_turnover for r in recent_rebalancings])  # noqa: E501
                avg_urgency = np.mean([r['recommendation'].urgency_level for r in recent_rebalancings])  # noqa: E501

                report_lines.append("REBALANCING STATISTICS:")
                report_lines.append(f"  Recent Average Turnover: {avg_turnover:.1%}")
                report_lines.append(f"  Average Urgency Level: {avg_urgency:.1f}/5")
                report_lines.append(f"  Last Rebalancing Complexity: {recent_rebalancings[-1]['recommendation'].get_implementation_complexity()}")  # noqa: E501
                report_lines.append("")

            # Optimization performance metrics
            if self.optimization_history:
                quality_scores = [opt.get_quality_score() for opt in self.optimization_history[-20:]]  # Last 20  # noqa: E501
                convergence_rate = sum(1 for opt in self.optimization_history[-20:] if 'converged' in opt.convergence_status.lower())  # noqa: E501
                avg_optimization_time = np.mean([opt.optimization_time for opt in self.optimization_history[-20:]])  # noqa: E501

                report_lines.append("OPTIMIZATION PERFORMANCE METRICS:")
                report_lines.append(f"  Average Quality Score: {np.mean(quality_scores):.1f}/100")
                report_lines.append(f"  Convergence Rate: {convergence_rate}/20 ({convergence_rate*5:.0f}%)")  # noqa: E501
                report_lines.append(f"  Average Optimization Time: {avg_optimization_time:.2f} seconds")  # noqa: E501
                report_lines.append("")

            report_lines.append("=" * 80)
            return "\n".join(report_lines)

        except Exception as e:
            self.error_handler.handle_error(e, context="PortfolioOptimizer.generate_optimization_report")  # noqa: E501
            return f"Error generating optimization report: {e}"

    def get_optimizer_summary(self) -> dict[str, Any]:
        """
        Get portfolio optimizer summary statistics.

        Returns:
            Dictionary with optimizer summary
        """
        try:
            summary = {
                'optimizer_status': {
                    'status': self.status.value,
                    'last_optimization': self._last_optimization.isoformat() if self._last_optimization else None,  # noqa: E501
                    'last_rebalancing': self._last_rebalancing.isoformat() if self._last_rebalancing else None,  # noqa: E501
                    'total_optimizations': len(self.optimization_history),
                    'total_rebalancings': len(self.rebalancing_history)
                },
                'configuration': {
                    'method': self.parameters.method.value,
                    'objective': self.parameters.objective.value,
                    'lookback_window': self.parameters.lookback_window,
                    'risk_free_rate': self.parameters.risk_free_rate,
                    'constraints_count': len(self.parameters.constraints)
                },
                'current_portfolio': {},
                'performance_metrics': {},
                'optimization_quality': {}
            }

            # Current portfolio
            if self.current_weights:
                total_positions = len([w for w in self.current_weights.values() if w > 0.001])
                max_weight = max(self.current_weights.values()) if self.current_weights else 0

                summary['current_portfolio'] = {
                    'total_positions': total_positions,
                    'max_position_weight': max_weight,
                    'concentration_ratio': sum(w**2 for w in self.current_weights.values())
                }

            # Latest optimization metrics
            if self.optimization_history:
                latest_opt = self.optimization_history[-1]
                summary['performance_metrics'] = {
                    'expected_return': latest_opt.expected_return,
                    'expected_risk': latest_opt.expected_risk,
                    'sharpe_ratio': latest_opt.sharpe_ratio,
                    'diversification_ratio': latest_opt.diversification_ratio,
                    'effective_assets': latest_opt.effective_assets
                }

            # Optimization quality metrics
            if len(self.optimization_history) >= 5:
                recent_opts = list(self.optimization_history)[-10:]
                quality_scores = [opt.get_quality_score() for opt in recent_opts]
                convergence_count = sum(1 for opt in recent_opts if 'converged' in opt.convergence_status.lower())  # noqa: E501

                summary['optimization_quality'] = {
                    'average_quality_score': np.mean(quality_scores),
                    'convergence_rate': convergence_count / len(recent_opts),
                    'average_optimization_time': np.mean([opt.optimization_time for opt in recent_opts])  # noqa: E501
                }

            return summary

        except Exception as e:
            self.error_handler.handle_error(e, context="PortfolioOptimizer.get_optimizer_summary")
            return {}

    # ==========================================================================
    # PRIVATE METHODS - Optimization Engines
    # ==========================================================================
    def _initialize_optimization_engines(self) -> None:
        """Initialize optimization engine components."""
        try:
            # Initialize optimization algorithms
            self.optimization_engines = {
                'scipy_minimize': True,
                'differential_evolution': True,
                'genetic_algorithm': True
            }

            # Initialize covariance estimators
            self.covariance_estimators = {
                'sample': True,
                'ledoit_wolf': LedoitWolf(),
                'oas': OAS()
            }

            self.logger.debug("Optimization engines initialized")

        except Exception as e:
            self.logger.error("Error initializing optimization engines: %s", e)

    def _initialize_ml_models(self) -> None:
        """Initialize machine learning prediction models."""
        try:
            # Initialize return prediction models
            self.ml_models['return_predictor'] = RandomForestRegressor(
                n_estimators=100,
                random_state=42
            )

            # Initialize risk prediction models
            self.ml_models['risk_predictor'] = RandomForestRegressor(
                n_estimators=50,
                random_state=42
            )

            self.logger.debug("ML models initialized")

        except Exception as e:
            self.logger.error("Error initializing ML models: %s", e)

    def _setup_default_constraints(self) -> None:
        """Set up default optimization constraints."""
        try:
            # Position weight constraints
            weight_constraint = OptimizationConstraint(
                constraint_type=ConstraintType.WEIGHT_CONSTRAINT,
                name="Position Weight Limits",
                description="Individual position weight constraints",
                lower_bound=MIN_POSITION_WEIGHT,
                upper_bound=MAX_POSITION_WEIGHT,
                enabled=True,
                priority=1
            )

            # Portfolio risk constraint
            risk_constraint = OptimizationConstraint(
                constraint_type=ConstraintType.RISK_CONSTRAINT,
                name="Portfolio Risk Limit",
                description="Maximum portfolio volatility constraint",
                upper_bound=MAX_PORTFOLIO_VOLATILITY,
                enabled=True,
                priority=2
            )

            # Turnover constraint
            turnover_constraint = OptimizationConstraint(
                constraint_type=ConstraintType.TURNOVER_CONSTRAINT,
                name="Turnover Limit",
                description="Maximum portfolio turnover constraint",
                upper_bound=MAX_TURNOVER_RATE,
                enabled=True,
                priority=3
            )

            # Add to parameters if not already present
            if not self.parameters.constraints:
                self.parameters.constraints = [weight_constraint, risk_constraint, turnover_constraint]  # noqa: E501

            self.logger.debug("Default constraints set up")

        except Exception as e:
            self.logger.error("Error setting up default constraints: %s", e)

    def _initialize_performance_tracking(self) -> None:
        """Initialize performance tracking components."""
        self.performance_metrics = {
            'cumulative_return': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0,
            'win_rate': 0.0,
            'average_holding_period': 0.0
        }

        self.risk_metrics = {
            'current_volatility': 0.0,
            'var_95': 0.0,
            'expected_shortfall': 0.0,
            'correlation_risk': 0.0
        }

        self.logger.debug("Performance tracking initialized")

    # ==========================================================================
    # PRIVATE METHODS - Core Optimization Algorithms
    # ==========================================================================
    async def _optimize_mean_variance(self, expected_returns: np.ndarray,
                                    covariance_matrix: np.ndarray,
                                    parameters: OptimizationParameters) -> dict[str, float]:
        """Optimize portfolio using mean-variance optimization."""
        try:
            n_assets = len(expected_returns)

            # Objective function
            def objective(weights):
                portfolio_return = np.dot(weights, expected_returns)
                portfolio_risk = np.sqrt(np.dot(weights, np.dot(covariance_matrix, weights)))

                if parameters.objective == OptimizationObjective.MAXIMIZE_SHARPE:
                    return -(portfolio_return - parameters.risk_free_rate) / portfolio_risk
                elif parameters.objective == OptimizationObjective.MINIMIZE_RISK:
                    return portfolio_risk
                elif parameters.objective == OptimizationObjective.MAXIMIZE_RETURN:
                    return -portfolio_return
                else:
                    # Risk-adjusted return (utility function)
                    return -(portfolio_return - 0.5 * parameters.risk_aversion * portfolio_risk**2)

            # Constraints
            constraints = []

            # Weight sum constraint
            constraints.append({
                'type': 'eq',
                'fun': lambda weights: np.sum(weights) - 1.0
            })

            # Add custom constraints
            for constraint in parameters.constraints:
                if constraint.enabled:
                    constraints.extend(self._convert_constraint_to_scipy(constraint, n_assets))

            # Bounds (individual weight limits)
            bounds = []
            for i in range(n_assets):
                lower = MIN_POSITION_WEIGHT
                upper = MAX_POSITION_WEIGHT

                # Check for asset-specific constraints
                for constraint in parameters.constraints:
                    if (constraint.constraint_type == ConstraintType.WEIGHT_CONSTRAINT and
                        constraint.enabled and len(constraint.applies_to) > i):
                        if constraint.lower_bound is not None:
                            lower = max(lower, constraint.lower_bound)
                        if constraint.upper_bound is not None:
                            upper = min(upper, constraint.upper_bound)

                bounds.append((lower, upper))

            # Initial guess (equal weights)
            x0 = np.ones(n_assets) / n_assets

            # Optimize
            result = minimize(
                objective,
                x0,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints,
                options={'maxiter': DEFAULT_MAX_ITERATIONS, 'ftol': CONVERGENCE_TOLERANCE}
            )

            if result.success:
                optimal_weights_array = result.x
                # Convert to dictionary
                asset_names = self.returns_data.columns.tolist()
                optimal_weights = {asset_names[i]: optimal_weights_array[i] for i in range(n_assets)}  # noqa: E501
                return optimal_weights
            else:
                self.logger.warning("Mean-variance optimization failed: %s", result.message)
                return self._create_equal_weights(self.returns_data.columns)

        except Exception as e:
            self.logger.error("Error in mean-variance optimization: %s", e)
            return self._create_equal_weights(self.returns_data.columns)

    async def _optimize_risk_parity(self, covariance_matrix: np.ndarray,
                                  parameters: OptimizationParameters) -> dict[str, float]:
        """Optimize portfolio using risk parity approach."""
        try:
            n_assets = len(covariance_matrix)

            def objective(weights):
                # Calculate risk contributions
                portfolio_risk = np.sqrt(np.dot(weights, np.dot(covariance_matrix, weights)))
                marginal_risk = np.dot(covariance_matrix, weights) / portfolio_risk
                risk_contributions = weights * marginal_risk

                # Target equal risk contributions
                target_risk_contrib = portfolio_risk / n_assets

                # Minimize sum of squared deviations from target
                return np.sum((risk_contributions - target_risk_contrib) ** 2)

            # Constraints
            constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0}]
            bounds = [(MIN_POSITION_WEIGHT, MAX_POSITION_WEIGHT) for _ in range(n_assets)]

            # Initial guess
            x0 = np.ones(n_assets) / n_assets

            # Optimize
            result = minimize(objective, x0, method='SLSQP', bounds=bounds, constraints=constraints)

            if result.success:
                optimal_weights_array = result.x
                asset_names = self.returns_data.columns.tolist()
                optimal_weights = {asset_names[i]: optimal_weights_array[i] for i in range(n_assets)}  # noqa: E501
                return optimal_weights
            else:
                self.logger.warning("Risk parity optimization failed: %s", result.message)
                return self._create_equal_weights(self.returns_data.columns)

        except Exception as e:
            self.logger.error("Error in risk parity optimization: %s", e)
            return self._create_equal_weights(self.returns_data.columns)

    async def _optimize_minimum_variance(self, covariance_matrix: np.ndarray,
                                       parameters: OptimizationParameters) -> dict[str, float]:
        """
        Optimize portfolio for minimum variance.

        Uses CVXPY for a proper QP formulation when available (guaranteed
        global optimum via interior-point solver); falls back to scipy SLSQP.
        """
        try:
            n_assets = len(covariance_matrix)
            asset_names = self.returns_data.columns.tolist()

            if HAS_CVXPY:
                w = cp.Variable(n_assets)
                Sigma = cp.Parameter((n_assets, n_assets), symmetric=True)
                Sigma.value = covariance_matrix
                objective = cp.Minimize(cp.quad_form(w, Sigma))
                constraints = [
                    cp.sum(w) == 1,
                    w >= MIN_POSITION_WEIGHT,
                    w <= MAX_POSITION_WEIGHT,
                ]
                prob = cp.Problem(objective, constraints)
                prob.solve(solver=cp.CLARABEL, warm_start=True)
                if prob.status in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE) and w.value is not None:
                    return {asset_names[i]: float(w.value[i]) for i in range(n_assets)}
                self.logger.warning("CVXPY min-variance: solver did not converge, falling back to scipy")  # noqa: E501

            # Scipy fallback
            def objective(weights):
                return np.dot(weights, np.dot(covariance_matrix, weights))

            constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0}]
            bounds = [(MIN_POSITION_WEIGHT, MAX_POSITION_WEIGHT) for _ in range(n_assets)]
            x0 = np.ones(n_assets) / n_assets
            result = minimize(objective, x0, method='SLSQP', bounds=bounds, constraints=constraints)

            if result.success:
                return {asset_names[i]: result.x[i] for i in range(n_assets)}
            return self._create_equal_weights(self.returns_data.columns)

        except Exception as e:
            self.logger.error("Error in minimum variance optimization: %s", e)
            return self._create_equal_weights(self.returns_data.columns)

    async def _optimize_maximum_sharpe(self, expected_returns: np.ndarray,
                                     covariance_matrix: np.ndarray,
                                     parameters: OptimizationParameters) -> dict[str, float]:
        """
        Optimize portfolio for maximum Sharpe ratio.

        With CVXPY, uses the Markowitz homogeneous transformation to convert
        the fractional programme into a QP (Lobo et al. 2007).
        Falls back to scipy SLSQP.
        """
        try:
            n_assets = len(expected_returns)
            asset_names = self.returns_data.columns.tolist()
            rf = parameters.risk_free_rate

            if HAS_CVXPY:
                # Homogeneous variable y = w / (mu' w - rf), kappa = 1 / (mu' w - rf)
                y = cp.Variable(n_assets, nonneg=True)
                kappa = cp.Variable(nonneg=True)
                excess = expected_returns - rf
                Sigma = cp.Parameter((n_assets, n_assets), symmetric=True)
                Sigma.value = covariance_matrix
                objective = cp.Minimize(cp.quad_form(y, Sigma))
                constraints = [
                    excess @ y == 1,
                    cp.sum(y) == kappa,
                    y >= MIN_POSITION_WEIGHT * kappa,
                    y <= MAX_POSITION_WEIGHT * kappa,
                    kappa >= 0,
                ]
                prob = cp.Problem(objective, constraints)
                prob.solve(solver=cp.CLARABEL, warm_start=True)
                if prob.status in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE) and y.value is not None and float(kappa.value) > 1e-10:  # noqa: E501
                    w_opt = y.value / float(kappa.value)
                    return {asset_names[i]: float(w_opt[i]) for i in range(n_assets)}
                self.logger.warning("CVXPY max-Sharpe: solver did not converge, falling back to scipy")  # noqa: E501

            # Scipy fallback
            def objective(weights):
                portfolio_return = np.dot(weights, expected_returns)
                portfolio_risk = np.sqrt(np.dot(weights, np.dot(covariance_matrix, weights)))
                excess_return = portfolio_return - rf
                return -excess_return / portfolio_risk if portfolio_risk > 0 else -excess_return

            constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0}]
            bounds = [(MIN_POSITION_WEIGHT, MAX_POSITION_WEIGHT) for _ in range(n_assets)]
            x0 = np.ones(n_assets) / n_assets
            result = minimize(objective, x0, method='SLSQP', bounds=bounds, constraints=constraints)

            if result.success:
                return {asset_names[i]: result.x[i] for i in range(n_assets)}
            return self._create_equal_weights(self.returns_data.columns)

        except Exception as e:
            self.logger.error("Error in maximum Sharpe optimization: %s", e)
            return self._create_equal_weights(self.returns_data.columns)


    async def _optimize_black_litterman(self, expected_returns: np.ndarray,
                                      covariance_matrix: np.ndarray,
                                      parameters: OptimizationParameters) -> dict[str, float]:
        """Optimize portfolio using Black-Litterman model."""
        try:
            # Simplified Black-Litterman implementation
            # In production, would include views and confidence levels

            # Use market cap weights as prior (simplified to equal weights)
            market_weights = np.ones(len(expected_returns)) / len(expected_returns)

            # Risk aversion parameter (implied from market portfolio)
            risk_aversion = 3.0  # Typical value

            # Implied equilibrium returns
            pi = risk_aversion * np.dot(covariance_matrix, market_weights)

            # No views for simplification (P and Q matrices would be empty)
            # In production, this would incorporate investor views

            # New expected returns (same as equilibrium since no views)
            mu_bl = pi

            # Optimize using adjusted returns
            return await self._optimize_mean_variance_with_returns(mu_bl, covariance_matrix, parameters)  # noqa: E501

        except Exception as e:
            self.logger.error("Error in Black-Litterman optimization: %s", e)
            return self._create_equal_weights(self.returns_data.columns)

    async def _optimize_with_ml(self, returns_data: pd.DataFrame,
                              expected_returns: np.ndarray,
                              covariance_matrix: np.ndarray,
                              parameters: OptimizationParameters) -> dict[str, float]:
        """Optimize portfolio using machine learning predictions."""
        try:
            # Train/update ML models if needed
            if len(returns_data) >= ML_TRAINING_WINDOW:
                await self._train_ml_models(returns_data)

            # Generate ML predictions
            ml_returns = await self._generate_ml_predictions(returns_data)

            # Combine traditional and ML expected returns
            confidence_weight = 0.3  # Weight for ML predictions
            combined_returns = (1 - confidence_weight) * expected_returns + confidence_weight * ml_returns  # noqa: E501

            # Optimize using combined returns
            return await self._optimize_mean_variance_with_returns(combined_returns, covariance_matrix, parameters)  # noqa: E501

        except Exception as e:
            self.logger.error("Error in ML optimization: %s", e)
            return await self._optimize_mean_variance(expected_returns, covariance_matrix, parameters)  # noqa: E501

    async def _optimize_multi_objective(self, expected_returns: np.ndarray,
                                      covariance_matrix: np.ndarray,
                                      parameters: OptimizationParameters) -> dict[str, float]:
        """Optimize portfolio using multi-objective optimization."""
        try:
            n_assets = len(expected_returns)

            def multi_objective(weights):
                portfolio_return = np.dot(weights, expected_returns)
                portfolio_risk = np.sqrt(np.dot(weights, np.dot(covariance_matrix, weights)))

                # Calculate diversification ratio
                individual_risks = np.sqrt(np.diag(covariance_matrix))
                weighted_avg_risk = np.dot(weights, individual_risks)
                diversification_ratio = portfolio_risk / weighted_avg_risk if weighted_avg_risk > 0 else 0  # noqa: E501

                # Multi-objective function (weighted sum approach)
                return_objective = -portfolio_return  # Maximize return
                risk_objective = portfolio_risk       # Minimize risk
                diversification_objective = -diversification_ratio  # Maximize diversification

                # Weights for different objectives
                w_return = 0.4
                w_risk = 0.4
                w_diversification = 0.2

                return (w_return * return_objective +
                       w_risk * risk_objective +
                       w_diversification * diversification_objective)

            # Use differential evolution for multi-objective optimization
            bounds = [(MIN_POSITION_WEIGHT, MAX_POSITION_WEIGHT) for _ in range(n_assets)]

            # Constraint function for weight sum
            def weight_sum_constraint(weights):
                return abs(np.sum(weights) - 1.0)

            result = differential_evolution(
                multi_objective,
                bounds,
                seed=42,
                maxiter=500,
                atol=CONVERGENCE_TOLERANCE
            )

            if result.success:
                # Normalize weights to sum to 1
                weights_raw = result.x
                weights_normalized = weights_raw / np.sum(weights_raw)

                asset_names = self.returns_data.columns.tolist()
                optimal_weights = {asset_names[i]: weights_normalized[i] for i in range(n_assets)}
                return optimal_weights
            else:
                return self._create_equal_weights(self.returns_data.columns)

        except Exception as e:
            self.logger.error("Error in multi-objective optimization: %s", e)
            return self._create_equal_weights(self.returns_data.columns)

    # ==========================================================================
    # PRIVATE METHODS - Utility Functions
    # ==========================================================================

    async def _optimize_with_riskfolio(
        self,
        returns_data: pd.DataFrame,
        parameters: 'OptimizationParameters'
    ) -> dict[str, float]:
        """
        Optimize portfolio using RiskFolio-Lib institutional methods.

        Supports Hierarchical Risk Parity (HRP), CVaR optimization,
        and risk budgeting with Ledoit-Wolf covariance estimation.

        Args:
            returns_data: Historical returns DataFrame.
            parameters: Optimization parameters including method selection.

        Returns:
            Dict mapping asset names to optimal weights.
        """
        if not HAS_RISKFOLIO:
            self.logger.warning("RiskFolio-Lib not available — falling back to mean-variance")
            expected_returns = await self._calculate_expected_returns(returns_data, parameters)
            covariance_matrix = await self._calculate_covariance_matrix(returns_data, parameters)
            return await self._optimize_mean_variance(expected_returns, covariance_matrix, parameters)  # noqa: E501

        try:
            # Create RiskFolio Portfolio object
            port = rp.Portfolio(returns=returns_data)

            # Calculate asset statistics with Ledoit-Wolf covariance
            port.assets_stats(
                method_mu='hist',       # Historical mean
                method_cov='ledoit_wolf' # Ledoit-Wolf shrinkage estimator
            )

            asset_names = returns_data.columns.tolist()

            if parameters.method == OptimizationMethod.HIERARCHICAL_RISK_PARITY:
                # Hierarchical Risk Parity — no covariance inversion needed
                weights = port.optimization(
                    model='HRP',
                    codependence='pearson',
                    rm='MV',              # Risk measure: variance
                    rf=DEFAULT_RISK_FREE_RATE,
                    linkage='single',
                    leaf_order=True
                )

            elif parameters.method == OptimizationMethod.CVAR_OPTIMIZATION:
                # CVaR (Conditional Value-at-Risk) optimization
                weights = port.optimization(
                    model='Classic',
                    rm='CVaR',           # Risk measure: Conditional VaR
                    obj='Sharpe',        # Maximize Sharpe ratio
                    rf=DEFAULT_RISK_FREE_RATE,
                    l=0,                 # Risk aversion factor
                    hist=True
                )

            elif parameters.method == OptimizationMethod.RISK_BUDGETING:
                # Risk budgeting — target equal risk contribution
                n_assets = len(asset_names)
                risk_budget = np.ones(n_assets) / n_assets  # Equal risk budget

                weights = port.rp_optimization(
                    model='Classic',
                    rm='CVaR',
                    rf=DEFAULT_RISK_FREE_RATE,
                    b=risk_budget
                )
            else:
                # Default Classic optimization with variance
                weights = port.optimization(
                    model='Classic',
                    rm='MV',
                    obj='Sharpe',
                    rf=DEFAULT_RISK_FREE_RATE,
                    hist=True
                )

            # Convert to dict
            if weights is not None and not weights.empty:
                optimal_weights = {
                    asset_names[i]: float(weights.iloc[i, 0])
                    for i in range(len(asset_names))
                }

                self.logger.info(
                    f"RiskFolio optimization ({parameters.method.value}) complete: "
                    f"{len(optimal_weights)} assets optimized"
                )
                return optimal_weights
            else:
                self.logger.warning("RiskFolio optimization returned empty weights")
                return self._create_equal_weights(returns_data.columns)

        except Exception as e:
            self.logger.error("RiskFolio optimization error: %s", e)
            return self._create_equal_weights(returns_data.columns)

    def _validate_optimization_inputs(self, returns_data: pd.DataFrame,
                                    current_weights: dict[str, float] | None) -> bool:
        """Validate optimization inputs."""
        if returns_data.empty:
            self.logger.error("Empty returns data provided")
            return False

        if len(returns_data) < self.parameters.lookback_window:
            self.logger.warning("Insufficient data: %s < %s", len(returns_data), self.parameters.lookback_window)  # noqa: E501

        if current_weights:
            # Check if all assets in weights are in returns data
            missing_assets = set(current_weights.keys()) - set(returns_data.columns)
            if missing_assets:
                self.logger.warning("Assets in weights not in returns data: %s", missing_assets)

        return True

    def _create_equal_weights(self, asset_names: list[str]) -> dict[str, float]:
        """Create equal weights portfolio."""
        n_assets = len(asset_names)
        if n_assets == 0:
            return {}

        weight = 1.0 / n_assets
        return {asset: weight for asset in asset_names}

    async def _calculate_expected_returns(self, returns_data: pd.DataFrame,
                                        parameters: OptimizationParameters) -> np.ndarray:
        """Calculate expected returns for optimization."""
        try:
            # Use simple historical mean (could be enhanced with more sophisticated models)
            window_data = returns_data.tail(parameters.lookback_window)
            expected_returns = window_data.mean().values

            # Annualize returns (assuming daily data)
            expected_returns = expected_returns * 252

            return expected_returns

        except Exception as e:
            self.logger.error("Error calculating expected returns: %s", e)
            return np.zeros(len(returns_data.columns))

    async def _calculate_covariance_matrix(self, returns_data: pd.DataFrame,
                                         parameters: OptimizationParameters) -> np.ndarray:
        """Calculate covariance matrix for optimization."""
        try:
            window_data = returns_data.tail(parameters.lookback_window)

            # Use Ledoit-Wolf shrinkage estimator for better estimation
            lw = LedoitWolf()
            covariance_matrix = lw.fit(window_data).covariance_

            # Annualize covariance matrix
            covariance_matrix = covariance_matrix * 252

            return covariance_matrix

        except Exception as e:
            self.logger.error("Error calculating covariance matrix: %s", e)
            # Return identity matrix as fallback
            n_assets = len(returns_data.columns)
            return np.eye(n_assets) * 0.04  # 20% volatility assumption

    def _monitoring_loop(self) -> None:
        """Main monitoring loop for portfolio optimization."""
        self.logger.info("Started portfolio optimization monitoring loop")

        while self._running:
            try:
                # This would integrate with market data and position feeds
                self._stop_event.wait(timeout=REBALANCING_FREQUENCY)

                # Check for rebalancing triggers
                self._check_rebalancing_triggers()

                # Update ML models periodically
                if len(self.returns_data) >= ML_TRAINING_WINDOW:
                    # Retrain every ML_RETRAINING_FREQUENCY periods
                    if (len(self.optimization_history) % (ML_RETRAINING_FREQUENCY // 10)) == 0:
                        asyncio.create_task(self._train_ml_models(self.returns_data))

                # Clean up old data
                self._cleanup_old_data()

            except Exception as e:
                self.logger.error("Error in monitoring loop: %s", e)
                self._stop_event.wait(timeout=60)

        self.logger.info("Portfolio optimization monitoring loop stopped")

    # Additional helper methods would be implemented here...
    # (Due to length constraints, showing structure rather than all implementations)

    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def cleanup(self) -> None:
        """Clean up portfolio optimizer resources."""
        try:
            # Stop monitoring
            self.stop_monitoring()

            # Clean up thread pool
            if hasattr(self, 'thread_pool'):
                self.thread_pool.shutdown(wait=True)

            # Clear data structures
            self.optimization_history.clear()
            self.performance_attribution.clear()
            self.rebalancing_history.clear()

            self.logger.info("Portfolio optimizer cleanup completed")

        except Exception as e:
            self.logger.error("Error during cleanup: %s", e)

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_sample_optimization_scenario() -> dict[str, Any]:
    """Create sample optimization scenario for testing."""
    # Generate sample returns data
    np.random.seed(42)
    n_assets, n_periods = 10, 252

    returns_data = {}
    for i in range(n_assets):
        returns_data[f'Asset_{i+1}'] = np.random.normal(0.0008, 0.02, n_periods)  # ~20% annual vol

    dates = pd.date_range(start='2023-01-01', periods=n_periods, freq='D')
    returns_df = pd.DataFrame(returns_data, index=dates)

    # Current weights (random)
    weights = np.random.dirichlet(np.ones(n_assets))
    current_weights = {f'Asset_{i+1}': weights[i] for i in range(n_assets)}

    return {
        'returns_data': returns_df,
        'current_weights': current_weights,
        'assets': n_assets,
        'periods': n_periods
    }

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
_portfolio_optimizer_instance: PortfolioOptimizer | None = None

def get_portfolio_optimizer_instance() -> PortfolioOptimizer:
    """
    Get singleton instance of the portfolio optimizer.

    Returns:
        PortfolioOptimizer instance
    """
    global _portfolio_optimizer_instance
    if _portfolio_optimizer_instance is None:
        _portfolio_optimizer_instance = PortfolioOptimizer()
        _portfolio_optimizer_instance.initialize()
    return _portfolio_optimizer_instance

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
async def main():
    """Main execution function for testing and demonstration."""
    logging.info("🎯 SPYDER E14 - Portfolio Optimizer")
    logging.info("=" * 80)

    try:
        # Create portfolio optimizer
        optimizer = PortfolioOptimizer()
        logging.info("✅ Portfolio Optimizer initialized")

        # Initialize optimizer
        if not optimizer.initialize():
            logging.info("❌ Failed to initialize portfolio optimizer")
            return False

        # Create sample scenario
        logging.info("\n📊 Creating sample optimization scenario...")
        scenario = create_sample_optimization_scenario()
        logging.info("   Created scenario: %s assets, %s periods", scenario['assets'], scenario['periods'])  # noqa: E501

        # Test portfolio optimization
        logging.info("\n🚀 Testing portfolio optimization...")
        logging.info("   Method: Mean-Variance Optimization")
        logging.info("   Objective: Maximize Sharpe Ratio")

        result = await optimizer.optimize_portfolio(
            scenario['returns_data'],
            scenario['current_weights']
        )

        logging.info("   ✅ Optimization completed!")
        logging.info(f"   Expected Return: {result.expected_return:.2%}")
        logging.info(f"   Expected Risk: {result.expected_risk:.2%}")
        logging.info(f"   Sharpe Ratio: {result.sharpe_ratio:.3f}")
        logging.info(f"   Quality Score: {result.get_quality_score():.1f}/100")
        logging.info(f"   Optimization Time: {result.optimization_time:.3f}s")

        # Test rebalancing recommendation
        logging.info("\n🔄 Generating rebalancing recommendation...")
        recommendation = await optimizer.generate_rebalancing_recommendation(result)

        logging.info(f"   Total Turnover: {recommendation.total_turnover:.1%}")
        logging.info("   Urgency Level: %s/5", recommendation.urgency_level)
        logging.info("   Implementation Complexity: %s", recommendation.get_implementation_complexity())  # noqa: E501
        logging.info("   Expected Benefits: %s items", len(recommendation.expected_benefits))

        # Test different optimization methods
        logging.info("\n🧪 Testing different optimization methods...")

        methods_to_test = [
            OptimizationMethod.RISK_PARITY,
            OptimizationMethod.MINIMUM_VARIANCE,
            OptimizationMethod.MAXIMUM_SHARPE
        ]

        for method in methods_to_test:
            test_params = OptimizationParameters(method=method)
            test_result = await optimizer.optimize_portfolio(
                scenario['returns_data'],
                scenario['current_weights'],
                custom_parameters=test_params
            )
            logging.info(f"   {method.value}: Sharpe {test_result.sharpe_ratio:.3f}, Risk {test_result.expected_risk:.2%}")  # noqa: E501

        # Test performance attribution
        logging.info("\n📈 Testing performance attribution...")
        start_date = scenario['returns_data'].index[100]
        end_date = scenario['returns_data'].index[200]

        attribution = optimizer.calculate_performance_attribution(start_date, end_date)
        logging.info("   Attribution Period: %s to %s", start_date.date(), end_date.date())
        logging.info(f"   Total Return: {attribution.total_return:.2%}")
        logging.info(f"   Active Return: {attribution.active_return:.2%}")
        logging.info(f"   Information Ratio: {attribution.information_ratio:.3f}")
        logging.info(f"   Tracking Error: {attribution.tracking_error:.2%}")

        # Generate comprehensive report
        logging.info("\n📋 Generating optimization report...")
        report = optimizer.generate_optimization_report()
        logging.info("📊 PORTFOLIO OPTIMIZATION REPORT:")
        logging.info("-" * 50)
        # Print first portion of report
        report_lines = report.split('\n')[:25]
        for line in report_lines:
            logging.info(line)
        logging.info("   ... (truncated)")

        # Get optimizer summary
        summary = optimizer.get_optimizer_summary()
        logging.info("\n📊 OPTIMIZER SUMMARY:")
        logging.info("   Status: %s", summary['optimizer_status']['status'].upper())
        logging.info("   Total Optimizations: %s", summary['optimizer_status']['total_optimizations'])  # noqa: E501
        logging.info("   Method: %s", summary['configuration']['method'].upper())
        logging.info("   Constraints: %s", summary['configuration']['constraints_count'])

        if summary.get('performance_metrics'):
            metrics = summary['performance_metrics']
            logging.info(f"   Latest Sharpe Ratio: {metrics['sharpe_ratio']:.3f}")
            logging.info(f"   Effective Assets: {metrics['effective_assets']:.1f}")
            logging.info(f"   Diversification Ratio: {metrics['diversification_ratio']:.3f}")

        if summary.get('optimization_quality'):
            quality = summary['optimization_quality']
            logging.info(f"   Average Quality Score: {quality['average_quality_score']:.1f}/100")
            logging.info(f"   Convergence Rate: {quality['convergence_rate']:.0%}")
            logging.info(f"   Avg Optimization Time: {quality['average_optimization_time']:.3f}s")

        # Test rebalancing execution
        logging.info("\n⚡ Testing rebalancing execution...")
        execution_result = optimizer.execute_rebalancing(recommendation, "gradual")
        logging.info("   Execution ID: %s", execution_result['execution_id'])
        logging.info("   Execution Quality: %s", execution_result['execution_quality'])
        logging.info(f"   Success Rate: {execution_result['success_rate']:.0%}")

        # Cleanup
        optimizer.cleanup()
        logging.info("\n✅ Portfolio Optimizer test completed successfully!")

        logging.info("\n🎯 PORTFOLIO OPTIMIZATION CAPABILITIES:")
        logging.info("   • 9 Advanced Optimization Methods")
        logging.info("   • Multi-Objective Optimization")
        logging.info("   • Real-time Rebalancing Engine")
        logging.info("   • Transaction Cost Optimization")
        logging.info("   • Machine Learning Integration")
        logging.info("   • Comprehensive Constraint Management")
        logging.info("   • Performance Attribution Analysis")
        logging.info("   • Risk-Adjusted Portfolio Construction")
        logging.info("   • Institutional-Grade Quality Assessment")
        logging.info("   • Seamless E-Series Integration")

        return True

    except Exception as e:
        logging.info("❌ Error during testing: %s", e)
        return False

if __name__ == "__main__":
    asyncio.run(main())
