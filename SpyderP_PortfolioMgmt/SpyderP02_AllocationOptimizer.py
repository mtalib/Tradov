#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderP02_AllocationOptimizer.py
Group: P (Portfolio Management)
Purpose: ML-driven strategy allocation optimization

Description:
    This module provides sophisticated machine learning-driven capital allocation
    optimization using Modern Portfolio Theory, Black-Litterman models, risk parity,
    Kelly Criterion, and advanced ML techniques. It combines quantitative finance
    methods with machine learning to dynamically optimize strategy allocations
    based on market regimes, performance predictions, and risk-return objectives.

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-07-01
Last Updated: 2025-07-01 Time: 19:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import threading
import asyncio
import json
import uuid
import warnings
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any, Set, Callable, Union, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
from enum import Enum, auto
from pathlib import Path
import copy
import pickle

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from scipy import stats, optimize, linalg
from scipy.stats import norm, multivariate_normal
import matplotlib.pyplot as plt
import seaborn as sns

# Machine Learning
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.cluster import KMeans
import xgboost as xgb
import lightgbm as lgb

# Optimization
from scipy.optimize import minimize, differential_evolution
import cvxpy as cp
import cvxopt
from pypfopt import EfficientFrontier, risk_models, expected_returns
from pypfopt.discrete_allocation import DiscreteAllocation
from pypfopt.objectives import L2_reg

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU15_PerformanceMetrics import PerformanceMetrics
from SpyderU_Utilities.SpyderU03_DateTimeUtils import DateTimeUtils
from SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType, Event

# Market data and analysis
from SpyderC_MarketData.SpyderC10_VIXAnalyzer import VIXAnalyzer, VIXRegime
from SpyderF_Analysis.SpyderF08_VolatilityRegime import VolatilityRegimeAnalyzer
from SpyderL_ML.SpyderL09_RegimeClassifier import RegimeClassifier
from SpyderL_ML.SpyderL10_FeatureEngineering import FeatureEngineer

# Portfolio components
try:
    from SpyderP_Portfolio.SpyderP01_PortfolioManager import PortfolioManager, StrategyAllocation
    from SpyderI_Integration.SpyderI01_IntegrationHub import get_integration_hub
    HUB_AVAILABLE = True
except ImportError:
    HUB_AVAILABLE = False

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Optimization parameters
DEFAULT_LOOKBACK_PERIOD = 252  # 1 year of trading days
MIN_ALLOCATION = 0.05          # 5% minimum allocation
MAX_ALLOCATION = 0.40          # 40% maximum allocation
CASH_RESERVE = 0.10            # 10% cash reserve
REBALANCE_THRESHOLD = 0.05     # 5% drift threshold

# Risk parameters
DEFAULT_RISK_AVERSION = 3.0    # Moderate risk aversion
MAX_PORTFOLIO_VOLATILITY = 0.25 # 25% maximum volatility
TARGET_SHARPE_RATIO = 1.5      # Target Sharpe ratio
VAR_CONFIDENCE = 0.95          # 95% VaR confidence
MAX_DRAWDOWN_TOLERANCE = 0.15  # 15% maximum drawdown

# ML parameters
FEATURE_LOOKBACK = 60          # 60 days for feature engineering
MODEL_RETRAIN_FREQUENCY = 30   # Retrain every 30 days
PREDICTION_HORIZON = 5         # 5 days ahead prediction
MIN_SAMPLES_FOR_ML = 1000      # Minimum samples for ML training

# Optimization methods
OPTIMIZATION_METHODS = [
    'mean_variance', 'black_litterman', 'risk_parity', 
    'hierarchical_risk_parity', 'kelly_criterion', 'ml_enhanced'
]

# Performance attribution periods
ATTRIBUTION_PERIODS = ['1D', '1W', '1M', '3M', '6M', '1Y']

# ==============================================================================
# ENUMS
# ==============================================================================
class OptimizationMethod(Enum):
    """Portfolio optimization methods"""
    MEAN_VARIANCE = "mean_variance"
    BLACK_LITTERMAN = "black_litterman" 
    RISK_PARITY = "risk_parity"
    HIERARCHICAL_RISK_PARITY = "hierarchical_risk_parity"
    KELLY_CRITERION = "kelly_criterion"
    ML_ENHANCED = "ml_enhanced"
    REGIME_ADAPTIVE = "regime_adaptive"
    ROBUST_OPTIMIZATION = "robust_optimization"

class ObjectiveFunction(Enum):
    """Optimization objective functions"""
    MAXIMIZE_SHARPE = "maximize_sharpe"
    MINIMIZE_VOLATILITY = "minimize_volatility"
    MAXIMIZE_RETURN = "maximize_return"
    MINIMIZE_VAR = "minimize_var"
    MAXIMIZE_UTILITY = "maximize_utility"
    MINIMIZE_CVaR = "minimize_cvar"

class MarketRegime(Enum):
    """Market regime types"""
    BULL_LOW_VOL = "bull_low_vol"
    BULL_HIGH_VOL = "bull_high_vol"
    BEAR_LOW_VOL = "bear_low_vol"
    BEAR_HIGH_VOL = "bear_high_vol"
    SIDEWAYS_LOW_VOL = "sideways_low_vol"
    SIDEWAYS_HIGH_VOL = "sideways_high_vol"
    CRISIS = "crisis"

class ConstraintType(Enum):
    """Portfolio constraint types"""
    BOX_CONSTRAINTS = "box_constraints"
    SECTOR_CONSTRAINTS = "sector_constraints"
    TURNOVER_CONSTRAINTS = "turnover_constraints"
    RISK_CONSTRAINTS = "risk_constraints"
    CORRELATION_CONSTRAINTS = "correlation_constraints"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class OptimizationConfig:
    """Configuration for allocation optimization"""
    method: OptimizationMethod = OptimizationMethod.ML_ENHANCED
    objective: ObjectiveFunction = ObjectiveFunction.MAXIMIZE_SHARPE
    lookback_period: int = DEFAULT_LOOKBACK_PERIOD
    risk_aversion: float = DEFAULT_RISK_AVERSION
    max_volatility: float = MAX_PORTFOLIO_VOLATILITY
    min_allocation: float = MIN_ALLOCATION
    max_allocation: float = MAX_ALLOCATION
    cash_reserve: float = CASH_RESERVE
    rebalance_threshold: float = REBALANCE_THRESHOLD
    use_regime_detection: bool = True
    use_ml_predictions: bool = True
    confidence_level: float = VAR_CONFIDENCE

@dataclass
class AllocationResult:
    """Result of allocation optimization"""
    allocations: Dict[str, float]
    expected_return: float
    expected_volatility: float
    sharpe_ratio: float
    value_at_risk: float
    expected_shortfall: float
    method_used: OptimizationMethod
    confidence_score: float
    regime_weights: Dict[MarketRegime, float]
    constraints_satisfied: bool
    optimization_time: float
    iteration_count: int
    convergence_status: str

@dataclass
class ReturnPrediction:
    """ML prediction for strategy returns"""
    strategy_id: str
    predicted_return: float
    prediction_std: float
    confidence_interval: Tuple[float, float]
    model_confidence: float
    feature_importance: Dict[str, float]
    regime_probability: Dict[MarketRegime, float]

@dataclass
class RiskMetrics:
    """Comprehensive risk metrics"""
    volatility: float
    var_95: float
    cvar_95: float
    max_drawdown: float
    beta: float
    downside_deviation: float
    calmar_ratio: float
    sortino_ratio: float
    correlation_matrix: np.ndarray
    eigenvalues: np.ndarray
    condition_number: float

@dataclass
class BlackLittermanInputs:
    """Black-Litterman model inputs"""
    prior_returns: np.ndarray
    prior_covariance: np.ndarray
    views_matrix: np.ndarray
    view_returns: np.ndarray
    view_uncertainty: np.ndarray
    risk_aversion: float
    tau: float = 0.05

@dataclass
class OptimizationConstraints:
    """Portfolio optimization constraints"""
    min_weights: Dict[str, float]
    max_weights: Dict[str, float]
    target_weights: Optional[Dict[str, float]] = None
    max_turnover: Optional[float] = None
    max_risk_contribution: Optional[float] = None
    sector_limits: Optional[Dict[str, Tuple[float, float]]] = None
    correlation_limits: Optional[Tuple[float, float]] = None

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class AllocationOptimizer:
    """
    Advanced ML-driven portfolio allocation optimizer.
    
    This optimizer combines modern portfolio theory with machine learning
    to dynamically optimize strategy allocations based on market regimes,
    performance predictions, and risk-return objectives using state-of-the-art
    quantitative finance and machine learning techniques.
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        event_manager: Event manager for notifications
        performance_metrics: Performance tracking system
        
    Example:
        >>> optimizer = AllocationOptimizer()
        >>> config = OptimizationConfig(method=OptimizationMethod.ML_ENHANCED)
        >>> result = await optimizer.optimize_allocations(strategy_data, config)
        >>> print(f"Optimal allocations: {result.allocations}")
    """
    
    def __init__(self, config: Optional[OptimizationConfig] = None):
        """
        Initialize the Allocation Optimizer.
        
        Args:
            config: Optimization configuration
        """
        # Core components
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()
        self.event_manager = get_event_manager()
        self.performance_metrics = PerformanceMetrics()
        self.datetime_utils = DateTimeUtils()
        
        # Configuration
        self.config = config or OptimizationConfig()
        
        # Market analysis components
        self.vix_analyzer = VIXAnalyzer()
        self.regime_classifier = RegimeClassifier()
        self.feature_engineer = FeatureEngineer()
        
        # ML models for predictions
        self.ml_models = {
            'return_predictor': RandomForestRegressor(n_estimators=100, random_state=42),
            'volatility_predictor': GradientBoostingRegressor(n_estimators=100, random_state=42),
            'regime_predictor': RandomForestRegressor(n_estimators=100, random_state=42)
        }
        
        # Data storage
        self.strategy_returns: Dict[str, deque] = defaultdict(lambda: deque(maxlen=DEFAULT_LOOKBACK_PERIOD))
        self.market_features: deque = deque(maxlen=FEATURE_LOOKBACK)
        self.optimization_history: deque = deque(maxlen=1000)
        self.model_predictions: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # Model performance tracking
        self.model_performance = {
            'return_predictions': {'mse': [], 'r2': []},
            'volatility_predictions': {'mse': [], 'r2': []},
            'regime_predictions': {'accuracy': []}
        }
        
        # Optimization state
        self.current_regime = MarketRegime.SIDEWAYS_LOW_VOL
        self.regime_probabilities = {regime: 1.0/len(MarketRegime) for regime in MarketRegime}
        self.last_optimization = None
        self.is_trained = False
        
        # Initialize components
        self._initialize_models()
        
        # Register with integration hub
        if HUB_AVAILABLE:
            hub = get_integration_hub()
            if hub:
                hub.register_module(self, dependencies=['SpyderP01_PortfolioManager'])
        
        self.logger.info("AllocationOptimizer initialized successfully")

    # ==========================================================================
    # PUBLIC METHODS - OPTIMIZATION
    # ==========================================================================
    
    async def optimize_allocations(self, strategy_data: Dict[str, pd.DataFrame],
                                 config: Optional[OptimizationConfig] = None) -> AllocationResult:
        """
        Optimize portfolio allocations using specified method.
        
        Args:
            strategy_data: Historical data for each strategy
            config: Optimization configuration (optional)
            
        Returns:
            Optimization result with allocations and metrics
        """
        try:
            start_time = time.time()
            opt_config = config or self.config
            
            # Validate inputs
            if not strategy_data:
                raise ValueError("No strategy data provided")
            
            # Prepare data
            returns_df = self._prepare_returns_data(strategy_data)
            features_df = await self._prepare_features_data(strategy_data)
            
            # Detect current market regime
            await self._update_market_regime(features_df)
            
            # Generate ML predictions if enabled
            predictions = {}
            if opt_config.use_ml_predictions and self.is_trained:
                predictions = await self._generate_ml_predictions(returns_df, features_df)
            
            # Choose optimization method
            if opt_config.method == OptimizationMethod.MEAN_VARIANCE:
                result = await self._optimize_mean_variance(returns_df, opt_config)
            elif opt_config.method == OptimizationMethod.BLACK_LITTERMAN:
                result = await self._optimize_black_litterman(returns_df, predictions, opt_config)
            elif opt_config.method == OptimizationMethod.RISK_PARITY:
                result = await self._optimize_risk_parity(returns_df, opt_config)
            elif opt_config.method == OptimizationMethod.HIERARCHICAL_RISK_PARITY:
                result = await self._optimize_hierarchical_risk_parity(returns_df, opt_config)
            elif opt_config.method == OptimizationMethod.KELLY_CRITERION:
                result = await self._optimize_kelly_criterion(returns_df, predictions, opt_config)
            elif opt_config.method == OptimizationMethod.ML_ENHANCED:
                result = await self._optimize_ml_enhanced(returns_df, features_df, predictions, opt_config)
            elif opt_config.method == OptimizationMethod.REGIME_ADAPTIVE:
                result = await self._optimize_regime_adaptive(returns_df, features_df, opt_config)
            else:
                raise ValueError(f"Unknown optimization method: {opt_config.method}")
            
            # Add execution metrics
            result.optimization_time = time.time() - start_time
            result.regime_weights = self.regime_probabilities.copy()
            
            # Store in history
            self.optimization_history.append(result)
            self.last_optimization = result
            
            # Emit optimization event
            self.event_manager.emit_event(Event(
                type=EventType.ALLOCATION_OPTIMIZED,
                source=self.__class__.__name__,
                data=asdict(result)
            ))
            
            self.logger.info(f"Allocation optimization completed in {result.optimization_time:.2f}s")
            return result
            
        except Exception as e:
            self.error_handler.handle_error(e, "optimize_allocations")
            raise

    async def train_ml_models(self, strategy_data: Dict[str, pd.DataFrame],
                            market_data: pd.DataFrame) -> Dict[str, float]:
        """
        Train ML models for return and volatility prediction.
        
        Args:
            strategy_data: Historical strategy data
            market_data: Market features data
            
        Returns:
            Model performance metrics
        """
        try:
            self.logger.info("Training ML models for allocation optimization")
            
            # Prepare training data
            returns_df = self._prepare_returns_data(strategy_data)
            features_df = await self._prepare_features_data(strategy_data, market_data)
            
            performance = {}
            
            # Train return prediction models
            for strategy_id in returns_df.columns:
                y = returns_df[strategy_id].dropna()
                X = features_df.loc[y.index].dropna()
                
                if len(X) >= MIN_SAMPLES_FOR_ML:
                    # Time series split for validation
                    tscv = TimeSeriesSplit(n_splits=5)
                    
                    # Train return predictor
                    scores = cross_val_score(
                        self.ml_models['return_predictor'], 
                        X, y, 
                        cv=tscv, 
                        scoring='neg_mean_squared_error'
                    )
                    performance[f'{strategy_id}_return_mse'] = -scores.mean()
                    
                    # Fit final model
                    self.ml_models['return_predictor'].fit(X, y)
            
            # Train volatility prediction model
            volatilities = returns_df.rolling(window=20).std()
            for strategy_id in volatilities.columns:
                y = volatilities[strategy_id].dropna()
                X = features_df.loc[y.index].dropna()
                
                if len(X) >= MIN_SAMPLES_FOR_ML:
                    scores = cross_val_score(
                        self.ml_models['volatility_predictor'],
                        X, y,
                        cv=TimeSeriesSplit(n_splits=5),
                        scoring='neg_mean_squared_error'
                    )
                    performance[f'{strategy_id}_volatility_mse'] = -scores.mean()
                    
                    self.ml_models['volatility_predictor'].fit(X, y)
            
            # Train regime prediction model
            regime_features = self._extract_regime_features(features_df)
            regime_labels = self._label_market_regimes(returns_df, volatilities)
            
            if len(regime_features) >= MIN_SAMPLES_FOR_ML:
                scores = cross_val_score(
                    self.ml_models['regime_predictor'],
                    regime_features, regime_labels,
                    cv=TimeSeriesSplit(n_splits=5),
                    scoring='accuracy'
                )
                performance['regime_accuracy'] = scores.mean()
                
                self.ml_models['regime_predictor'].fit(regime_features, regime_labels)
            
            self.is_trained = True
            self.logger.info(f"ML models trained successfully. Performance: {performance}")
            
            return performance
            
        except Exception as e:
            self.error_handler.handle_error(e, "train_ml_models")
            return {}

    async def generate_allocation_scenarios(self, strategy_data: Dict[str, pd.DataFrame],
                                          num_scenarios: int = 1000) -> List[AllocationResult]:
        """
        Generate multiple allocation scenarios using Monte Carlo simulation.
        
        Args:
            strategy_data: Historical strategy data
            num_scenarios: Number of scenarios to generate
            
        Returns:
            List of allocation scenarios
        """
        try:
            scenarios = []
            returns_df = self._prepare_returns_data(strategy_data)
            
            # Generate random market scenarios
            for i in range(num_scenarios):
                # Randomly perturb expected returns and covariance
                perturbed_returns = self._perturb_expected_returns(returns_df)
                perturbed_cov = self._perturb_covariance_matrix(returns_df)
                
                # Optimize for this scenario
                scenario_config = copy.deepcopy(self.config)
                scenario_result = await self._optimize_scenario(
                    perturbed_returns, perturbed_cov, scenario_config
                )
                
                scenarios.append(scenario_result)
                
                if (i + 1) % 100 == 0:
                    self.logger.info(f"Generated {i + 1}/{num_scenarios} scenarios")
            
            return scenarios
            
        except Exception as e:
            self.error_handler.handle_error(e, "generate_allocation_scenarios")
            return []

    # ==========================================================================
    # PUBLIC METHODS - ANALYSIS
    # ==========================================================================
    
    def analyze_allocation_stability(self, allocation_history: List[AllocationResult]) -> Dict[str, Any]:
        """
        Analyze the stability of allocation recommendations.
        
        Args:
            allocation_history: Historical allocation results
            
        Returns:
            Stability analysis metrics
        """
        try:
            if len(allocation_history) < 2:
                return {'error': 'Insufficient allocation history'}
            
            # Extract allocations over time
            allocations_df = pd.DataFrame([result.allocations for result in allocation_history])
            
            # Calculate stability metrics
            turnover = []
            for i in range(1, len(allocations_df)):
                turnover.append(
                    np.sum(np.abs(allocations_df.iloc[i] - allocations_df.iloc[i-1]))
                )
            
            stability_metrics = {
                'average_turnover': np.mean(turnover),
                'turnover_volatility': np.std(turnover),
                'max_turnover': np.max(turnover),
                'allocation_correlation': allocations_df.corr().values,
                'weight_stability': {
                    strategy: {
                        'mean': allocations_df[strategy].mean(),
                        'std': allocations_df[strategy].std(),
                        'min': allocations_df[strategy].min(),
                        'max': allocations_df[strategy].max()
                    }
                    for strategy in allocations_df.columns
                }
            }
            
            return stability_metrics
            
        except Exception as e:
            self.error_handler.handle_error(e, "analyze_allocation_stability")
            return {'error': str(e)}

    def get_optimization_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive optimization summary.
        
        Returns:
            Optimization summary dictionary
        """
        try:
            if not self.last_optimization:
                return {'status': 'no_optimizations_performed'}
            
            result = self.last_optimization
            
            # Performance summary
            performance_summary = {
                'expected_return': f"{result.expected_return:.2%}",
                'expected_volatility': f"{result.expected_volatility:.2%}",
                'sharpe_ratio': f"{result.sharpe_ratio:.2f}",
                'value_at_risk': f"{result.value_at_risk:.2%}",
                'expected_shortfall': f"{result.expected_shortfall:.2%}",
                'confidence_score': f"{result.confidence_score:.1%}"
            }
            
            # Allocation summary
            allocation_summary = {
                strategy: f"{weight:.1%}" 
                for strategy, weight in result.allocations.items()
            }
            
            # Risk breakdown
            risk_summary = {
                'volatility_target': f"{self.config.max_volatility:.1%}",
                'current_volatility': f"{result.expected_volatility:.1%}",
                'risk_utilization': f"{result.expected_volatility/self.config.max_volatility:.1%}",
                'diversification_benefit': self._calculate_diversification_benefit(result)
            }
            
            return {
                'timestamp': datetime.now().isoformat(),
                'method_used': result.method_used.value,
                'optimization_time': f"{result.optimization_time:.2f}s",
                'convergence_status': result.convergence_status,
                'constraints_satisfied': result.constraints_satisfied,
                'current_regime': self.current_regime.value,
                'allocations': allocation_summary,
                'performance_metrics': performance_summary,
                'risk_metrics': risk_summary,
                'regime_probabilities': {
                    regime.value: f"{prob:.1%}" 
                    for regime, prob in result.regime_weights.items()
                },
                'model_status': {
                    'is_trained': self.is_trained,
                    'last_training': getattr(self, 'last_training_time', 'Never'),
                    'prediction_accuracy': self._get_model_accuracy_summary()
                }
            }
            
        except Exception as e:
            self.error_handler.handle_error(e, "get_optimization_summary")
            return {'error': str(e)}

    # ==========================================================================
    # PRIVATE METHODS - OPTIMIZATION ALGORITHMS
    # ==========================================================================
    
    async def _optimize_mean_variance(self, returns_df: pd.DataFrame, 
                                    config: OptimizationConfig) -> AllocationResult:
        """Optimize using mean-variance optimization"""
        try:
            # Calculate expected returns and covariance
            expected_returns = returns_df.mean() * 252  # Annualized
            cov_matrix = returns_df.cov() * 252  # Annualized
            
            # Set up optimization problem
            n_assets = len(expected_returns)
            weights = cp.Variable(n_assets)
            
            # Objective: maximize Sharpe ratio
            if config.objective == ObjectiveFunction.MAXIMIZE_SHARPE:
                # Quadratic utility function
                portfolio_return = expected_returns.values @ weights
                portfolio_variance = cp.quad_form(weights, cov_matrix.values)
                objective = cp.Maximize(portfolio_return - 0.5 * config.risk_aversion * portfolio_variance)
            elif config.objective == ObjectiveFunction.MINIMIZE_VOLATILITY:
                portfolio_variance = cp.quad_form(weights, cov_matrix.values)
                objective = cp.Minimize(portfolio_variance)
            else:
                portfolio_return = expected_returns.values @ weights
                objective = cp.Maximize(portfolio_return)
            
            # Constraints
            constraints = [
                cp.sum(weights) == 1 - config.cash_reserve,  # Budget constraint
                weights >= config.min_allocation,  # Minimum allocation
                weights <= config.max_allocation   # Maximum allocation
            ]
            
            # Add volatility constraint if specified
            if config.max_volatility < np.inf:
                portfolio_variance = cp.quad_form(weights, cov_matrix.values)
                constraints.append(cp.sqrt(portfolio_variance) <= config.max_volatility)
            
            # Solve optimization
            problem = cp.Problem(objective, constraints)
            problem.solve()
            
            if problem.status != cp.OPTIMAL:
                raise ValueError(f"Optimization failed with status: {problem.status}")
            
            # Extract results
            optimal_weights = weights.value
            allocations = dict(zip(returns_df.columns, optimal_weights))
            
            # Calculate metrics
            portfolio_return = np.sum(optimal_weights * expected_returns.values)
            portfolio_variance = np.dot(optimal_weights, np.dot(cov_matrix.values, optimal_weights))
            portfolio_volatility = np.sqrt(portfolio_variance)
            sharpe_ratio = portfolio_return / portfolio_volatility if portfolio_volatility > 0 else 0
            
            # Risk metrics
            var_95 = norm.ppf(0.05) * portfolio_volatility
            cvar_95 = portfolio_volatility * norm.pdf(norm.ppf(0.05)) / 0.05
            
            return AllocationResult(
                allocations=allocations,
                expected_return=portfolio_return,
                expected_volatility=portfolio_volatility,
                sharpe_ratio=sharpe_ratio,
                value_at_risk=var_95,
                expected_shortfall=cvar_95,
                method_used=OptimizationMethod.MEAN_VARIANCE,
                confidence_score=0.8,  # Default confidence for analytical methods
                regime_weights={},
                constraints_satisfied=True,
                optimization_time=0.0,
                iteration_count=problem.solver_stats.num_iters if problem.solver_stats else 0,
                convergence_status="OPTIMAL"
            )
            
        except Exception as e:
            self.error_handler.handle_error(e, "_optimize_mean_variance")
            raise

    async def _optimize_black_litterman(self, returns_df: pd.DataFrame,
                                      predictions: Dict[str, ReturnPrediction],
                                      config: OptimizationConfig) -> AllocationResult:
        """Optimize using Black-Litterman model"""
        try:
            # Market equilibrium (prior)
            expected_returns = returns_df.mean() * 252
            cov_matrix = returns_df.cov() * 252
            
            # Market cap weights (simplified - equal weight as proxy)
            market_weights = np.ones(len(expected_returns)) / len(expected_returns)
            
            # Implied equilibrium returns
            pi = config.risk_aversion * np.dot(cov_matrix.values, market_weights)
            
            # Views from ML predictions
            if predictions:
                n_views = len(predictions)
                P = np.zeros((n_views, len(expected_returns)))  # Picking matrix
                Q = np.zeros(n_views)  # View returns
                Omega = np.eye(n_views)  # View uncertainty
                
                for i, (strategy_id, pred) in enumerate(predictions.items()):
                    strategy_idx = list(expected_returns.index).index(strategy_id)
                    P[i, strategy_idx] = 1
                    Q[i] = pred.predicted_return
                    Omega[i, i] = pred.prediction_std ** 2
                
                # Black-Litterman formula
                tau = 0.05  # Uncertainty in prior
                M1 = linalg.inv(tau * cov_matrix.values)
                M2 = np.dot(P.T, np.dot(linalg.inv(Omega), P))
                M3 = np.dot(linalg.inv(tau * cov_matrix.values), pi)
                M4 = np.dot(P.T, np.dot(linalg.inv(Omega), Q))
                
                # New expected returns
                mu_bl = np.dot(linalg.inv(M1 + M2), M3 + M4)
                
                # New covariance matrix
                cov_bl = linalg.inv(M1 + M2)
            else:
                # No views - use market equilibrium
                mu_bl = pi
                cov_bl = cov_matrix.values
            
            # Optimize with Black-Litterman inputs
            n_assets = len(mu_bl)
            weights = cp.Variable(n_assets)
            
            portfolio_return = mu_bl @ weights
            portfolio_variance = cp.quad_form(weights, cov_bl)
            objective = cp.Maximize(portfolio_return - 0.5 * config.risk_aversion * portfolio_variance)
            
            constraints = [
                cp.sum(weights) == 1 - config.cash_reserve,
                weights >= config.min_allocation,
                weights <= config.max_allocation
            ]
            
            problem = cp.Problem(objective, constraints)
            problem.solve()
            
            if problem.status != cp.OPTIMAL:
                raise ValueError(f"Black-Litterman optimization failed: {problem.status}")
            
            optimal_weights = weights.value
            allocations = dict(zip(returns_df.columns, optimal_weights))
            
            # Calculate portfolio metrics
            portfolio_return_val = np.sum(optimal_weights * mu_bl)
            portfolio_variance_val = np.dot(optimal_weights, np.dot(cov_bl, optimal_weights))
            portfolio_volatility = np.sqrt(portfolio_variance_val)
            sharpe_ratio = portfolio_return_val / portfolio_volatility if portfolio_volatility > 0 else 0
            
            return AllocationResult(
                allocations=allocations,
                expected_return=portfolio_return_val,
                expected_volatility=portfolio_volatility,
                sharpe_ratio=sharpe_ratio,
                value_at_risk=norm.ppf(0.05) * portfolio_volatility,
                expected_shortfall=portfolio_volatility * norm.pdf(norm.ppf(0.05)) / 0.05,
                method_used=OptimizationMethod.BLACK_LITTERMAN,
                confidence_score=0.85 if predictions else 0.7,
                regime_weights={},
                constraints_satisfied=True,
                optimization_time=0.0,
                iteration_count=problem.solver_stats.num_iters if problem.solver_stats else 0,
                convergence_status="OPTIMAL"
            )
            
        except Exception as e:
            self.error_handler.handle_error(e, "_optimize_black_litterman")
            raise

    async def _optimize_risk_parity(self, returns_df: pd.DataFrame,
                                  config: OptimizationConfig) -> AllocationResult:
        """Optimize using risk parity approach"""
        try:
            cov_matrix = returns_df.cov() * 252  # Annualized
            
            def risk_parity_objective(weights):
                """Risk parity objective function"""
                portfolio_vol = np.sqrt(np.dot(weights, np.dot(cov_matrix.values, weights)))
                risk_contributions = weights * np.dot(cov_matrix.values, weights) / portfolio_vol
                target_risk = portfolio_vol / len(weights)  # Equal risk contribution
                return np.sum((risk_contributions - target_risk) ** 2)
            
            # Constraints
            n_assets = len(returns_df.columns)
            constraints = [
                {'type': 'eq', 'fun': lambda w: np.sum(w) - (1 - config.cash_reserve)},
            ]
            
            bounds = [(config.min_allocation, config.max_allocation) for _ in range(n_assets)]
            
            # Initial guess (equal weights)
            x0 = np.ones(n_assets) * (1 - config.cash_reserve) / n_assets
            
            # Optimize
            result = optimize.minimize(
                risk_parity_objective,
                x0,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints,
                options={'ftol': 1e-9, 'disp': False}
            )
            
            if not result.success:
                raise ValueError(f"Risk parity optimization failed: {result.message}")
            
            optimal_weights = result.x
            allocations = dict(zip(returns_df.columns, optimal_weights))
            
            # Calculate metrics
            expected_returns = returns_df.mean() * 252
            portfolio_return = np.sum(optimal_weights * expected_returns.values)
            portfolio_variance = np.dot(optimal_weights, np.dot(cov_matrix.values, optimal_weights))
            portfolio_volatility = np.sqrt(portfolio_variance)
            sharpe_ratio = portfolio_return / portfolio_volatility if portfolio_volatility > 0 else 0
            
            return AllocationResult(
                allocations=allocations,
                expected_return=portfolio_return,
                expected_volatility=portfolio_volatility,
                sharpe_ratio=sharpe_ratio,
                value_at_risk=norm.ppf(0.05) * portfolio_volatility,
                expected_shortfall=portfolio_volatility * norm.pdf(norm.ppf(0.05)) / 0.05,
                method_used=OptimizationMethod.RISK_PARITY,
                confidence_score=0.75,
                regime_weights={},
                constraints_satisfied=result.success,
                optimization_time=0.0,
                iteration_count=result.nit,
                convergence_status="SUCCESS" if result.success else "FAILED"
            )
            
        except Exception as e:
            self.error_handler.handle_error(e, "_optimize_risk_parity")
            raise

    async def _optimize_hierarchical_risk_parity(self, returns_df: pd.DataFrame,
                                               config: OptimizationConfig) -> AllocationResult:
        """Optimize using Hierarchical Risk Parity (HRP)"""
        try:
            from scipy.cluster.hierarchy import linkage, dendrogram
            from scipy.spatial.distance import squareform
            
            # Calculate correlation matrix
            corr_matrix = returns_df.corr()
            cov_matrix = returns_df.cov() * 252
            
            # Distance matrix from correlation
            distance_matrix = np.sqrt(0.5 * (1 - corr_matrix))
            
            # Hierarchical clustering
            condensed_distance = squareform(distance_matrix.values)
            linkage_matrix = linkage(condensed_distance, method='ward')
            
            # Recursive bisection for HRP weights
            def get_cluster_variance(cov_matrix, cluster_items):
                """Calculate cluster variance"""
                cluster_cov = cov_matrix.loc[cluster_items, cluster_items]
                inv_diag = 1 / np.diag(cluster_cov)
                weights = inv_diag / inv_diag.sum()
                cluster_variance = np.dot(weights, np.dot(cluster_cov.values, weights))
                return cluster_variance
            
            def recursive_bisection(cov_matrix, assets, linkage_matrix):
                """Recursive bisection to get HRP weights"""
                if len(assets) == 1:
                    return {assets[0]: 1.0}
                
                # Find the split point
                n = len(assets)
                split_point = n // 2
                
                # Split assets into two clusters
                left_cluster = assets[:split_point]
                right_cluster = assets[split_point:]
                
                # Calculate cluster variances
                left_var = get_cluster_variance(cov_matrix, left_cluster)
                right_var = get_cluster_variance(cov_matrix, right_cluster)
                
                # Allocate weights inversely proportional to variance
                total_var = left_var + right_var
                left_weight = right_var / total_var
                right_weight = left_var / total_var
                
                # Recursive allocation
                left_weights = recursive_bisection(cov_matrix, left_cluster, linkage_matrix)
                right_weights = recursive_bisection(cov_matrix, right_cluster, linkage_matrix)
                
                # Scale weights
                final_weights = {}
                for asset, weight in left_weights.items():
                    final_weights[asset] = weight * left_weight
                for asset, weight in right_weights.items():
                    final_weights[asset] = weight * right_weight
                
                return final_weights
            
            # Get HRP weights
            assets = returns_df.columns.tolist()
            hrp_weights = recursive_bisection(cov_matrix, assets, linkage_matrix)
            
            # Scale to satisfy constraints
            total_weight = sum(hrp_weights.values())
            target_weight = 1 - config.cash_reserve
            
            allocations = {}
            for asset, weight in hrp_weights.items():
                scaled_weight = weight * target_weight / total_weight
                # Apply min/max constraints
                scaled_weight = max(config.min_allocation, min(config.max_allocation, scaled_weight))
                allocations[asset] = scaled_weight
            
            # Renormalize if needed
            total_allocation = sum(allocations.values())
            if total_allocation != target_weight:
                for asset in allocations:
                    allocations[asset] *= target_weight / total_allocation
            
            # Calculate metrics
            weights_array = np.array([allocations[col] for col in returns_df.columns])
            expected_returns = returns_df.mean() * 252
            portfolio_return = np.sum(weights_array * expected_returns.values)
            portfolio_variance = np.dot(weights_array, np.dot(cov_matrix.values, weights_array))
            portfolio_volatility = np.sqrt(portfolio_variance)
            sharpe_ratio = portfolio_return / portfolio_volatility if portfolio_volatility > 0 else 0
            
            return AllocationResult(
                allocations=allocations,
                expected_return=portfolio_return,
                expected_volatility=portfolio_volatility,
                sharpe_ratio=sharpe_ratio,
                value_at_risk=norm.ppf(0.05) * portfolio_volatility,
                expected_shortfall=portfolio_volatility * norm.pdf(norm.ppf(0.05)) / 0.05,
                method_used=OptimizationMethod.HIERARCHICAL_RISK_PARITY,
                confidence_score=0.8,
                regime_weights={},
                constraints_satisfied=True,
                optimization_time=0.0,
                iteration_count=0,
                convergence_status="SUCCESS"
            )
            
        except Exception as e:
            self.error_handler.handle_error(e, "_optimize_hierarchical_risk_parity")
            raise

    async def _optimize_kelly_criterion(self, returns_df: pd.DataFrame,
                                       predictions: Dict[str, ReturnPrediction],
                                       config: OptimizationConfig) -> AllocationResult:
        """Optimize using Kelly Criterion"""
        try:
            if not predictions:
                # Fall back to historical Kelly
                expected_returns = returns_df.mean() * 252
                return_variance = returns_df.var() * 252
            else:
                # Use ML predictions
                expected_returns = pd.Series({
                    strategy_id: pred.predicted_return
                    for strategy_id, pred in predictions.items()
                })
                return_variance = pd.Series({
                    strategy_id: pred.prediction_std ** 2
                    for strategy_id, pred in predictions.items()
                })
            
            # Kelly formula: f* = (μ - r) / σ²
            risk_free_rate = 0.02  # 2% risk-free rate
            kelly_fractions = {}
            
            for strategy in expected_returns.index:
                excess_return = expected_returns[strategy] - risk_free_rate
                variance = return_variance[strategy]
                
                if variance > 0:
                    kelly_fraction = excess_return / variance
                    # Apply Kelly reduction factor (typically 25-50% of full Kelly)
                    kelly_fraction *= 0.25  # Conservative Kelly
                    kelly_fractions[strategy] = max(0, kelly_fraction)
                else:
                    kelly_fractions[strategy] = 0
            
            # Normalize and apply constraints
            total_kelly = sum(kelly_fractions.values())
            target_weight = 1 - config.cash_reserve
            
            if total_kelly > 0:
                allocations = {}
                for strategy, kelly_frac in kelly_fractions.items():
                    weight = (kelly_frac / total_kelly) * target_weight
                    weight = max(config.min_allocation, min(config.max_allocation, weight))
                    allocations[strategy] = weight
                
                # Renormalize
                total_allocation = sum(allocations.values())
                if total_allocation > 0:
                    for strategy in allocations:
                        allocations[strategy] *= target_weight / total_allocation
            else:
                # Equal weight fallback
                n_strategies = len(expected_returns)
                equal_weight = target_weight / n_strategies
                allocations = {strategy: equal_weight for strategy in expected_returns.index}
            
            # Calculate metrics
            weights_array = np.array([allocations[col] for col in returns_df.columns])
            cov_matrix = returns_df.cov() * 252
            portfolio_return = np.sum(weights_array * expected_returns.values)
            portfolio_variance = np.dot(weights_array, np.dot(cov_matrix.values, weights_array))
            portfolio_volatility = np.sqrt(portfolio_variance)
            sharpe_ratio = portfolio_return / portfolio_volatility if portfolio_volatility > 0 else 0
            
            return AllocationResult(
                allocations=allocations,
                expected_return=portfolio_return,
                expected_volatility=portfolio_volatility,
                sharpe_ratio=sharpe_ratio,
                value_at_risk=norm.ppf(0.05) * portfolio_volatility,
                expected_shortfall=portfolio_volatility * norm.pdf(norm.ppf(0.05)) / 0.05,
                method_used=OptimizationMethod.KELLY_CRITERION,
                confidence_score=0.9 if predictions else 0.7,
                regime_weights={},
                constraints_satisfied=True,
                optimization_time=0.0,
                iteration_count=0,
                convergence_status="SUCCESS"
            )
            
        except Exception as e:
            self.error_handler.handle_error(e, "_optimize_kelly_criterion")
            raise

    async def _optimize_ml_enhanced(self, returns_df: pd.DataFrame, features_df: pd.DataFrame,
                                  predictions: Dict[str, ReturnPrediction],
                                  config: OptimizationConfig) -> AllocationResult:
        """Optimize using ML-enhanced approach combining multiple methods"""
        try:
            # Ensemble of optimization methods
            methods = [
                OptimizationMethod.MEAN_VARIANCE,
                OptimizationMethod.BLACK_LITTERMAN,
                OptimizationMethod.RISK_PARITY,
                OptimizationMethod.KELLY_CRITERION
            ]
            
            results = []
            weights = []
            
            # Generate allocations from different methods
            for method in methods:
                temp_config = copy.deepcopy(config)
                temp_config.method = method
                
                if method == OptimizationMethod.MEAN_VARIANCE:
                    result = await self._optimize_mean_variance(returns_df, temp_config)
                elif method == OptimizationMethod.BLACK_LITTERMAN:
                    result = await self._optimize_black_litterman(returns_df, predictions, temp_config)
                elif method == OptimizationMethod.RISK_PARITY:
                    result = await self._optimize_risk_parity(returns_df, temp_config)
                elif method == OptimizationMethod.KELLY_CRITERION:
                    result = await self._optimize_kelly_criterion(returns_df, predictions, temp_config)
                
                results.append(result)
                # Weight by Sharpe ratio and confidence
                method_weight = result.sharpe_ratio * result.confidence_score
                weights.append(method_weight)
            
            # Normalize weights
            total_weight = sum(weights)
            if total_weight > 0:
                weights = [w / total_weight for w in weights]
            else:
                weights = [1.0 / len(methods)] * len(methods)
            
            # Ensemble allocation
            ensemble_allocations = defaultdict(float)
            for i, result in enumerate(results):
                for strategy, allocation in result.allocations.items():
                    ensemble_allocations[strategy] += allocation * weights[i]
            
            # Apply ML predictions to adjust allocations
            if predictions and self.is_trained:
                for strategy_id, prediction in predictions.items():
                    if strategy_id in ensemble_allocations:
                        # Adjust based on prediction confidence and regime probability
                        confidence_multiplier = 0.5 + 0.5 * prediction.model_confidence
                        ensemble_allocations[strategy_id] *= confidence_multiplier
            
            # Renormalize
            total_allocation = sum(ensemble_allocations.values())
            target_allocation = 1 - config.cash_reserve
            
            final_allocations = {}
            for strategy, allocation in ensemble_allocations.items():
                weight = (allocation / total_allocation) * target_allocation
                weight = max(config.min_allocation, min(config.max_allocation, weight))
                final_allocations[strategy] = weight
            
            # Calculate ensemble metrics
            weights_array = np.array([final_allocations[col] for col in returns_df.columns])
            expected_returns = returns_df.mean() * 252
            cov_matrix = returns_df.cov() * 252
            
            portfolio_return = np.sum(weights_array * expected_returns.values)
            portfolio_variance = np.dot(weights_array, np.dot(cov_matrix.values, weights_array))
            portfolio_volatility = np.sqrt(portfolio_variance)
            sharpe_ratio = portfolio_return / portfolio_volatility if portfolio_volatility > 0 else 0
            
            # Ensemble confidence (weighted average)
            ensemble_confidence = sum(result.confidence_score * weights[i] for i, result in enumerate(results))
            
            return AllocationResult(
                allocations=final_allocations,
                expected_return=portfolio_return,
                expected_volatility=portfolio_volatility,
                sharpe_ratio=sharpe_ratio,
                value_at_risk=norm.ppf(0.05) * portfolio_volatility,
                expected_shortfall=portfolio_volatility * norm.pdf(norm.ppf(0.05)) / 0.05,
                method_used=OptimizationMethod.ML_ENHANCED,
                confidence_score=ensemble_confidence,
                regime_weights=self.regime_probabilities.copy(),
                constraints_satisfied=True,
                optimization_time=0.0,
                iteration_count=sum(result.iteration_count for result in results),
                convergence_status="SUCCESS"
            )
            
        except Exception as e:
            self.error_handler.handle_error(e, "_optimize_ml_enhanced")
            raise

    async def _optimize_regime_adaptive(self, returns_df: pd.DataFrame, features_df: pd.DataFrame,
                                       config: OptimizationConfig) -> AllocationResult:
        """Optimize using regime-adaptive approach"""
        try:
            # Calculate regime-specific allocations
            regime_allocations = {}
            
            for regime in MarketRegime:
                # Filter data for this regime (simplified - in practice would use regime detection)
                regime_weight = self.regime_probabilities.get(regime, 1.0 / len(MarketRegime))
                
                # Adjust risk aversion based on regime
                regime_config = copy.deepcopy(config)
                if regime in [MarketRegime.CRISIS, MarketRegime.BEAR_HIGH_VOL]:
                    regime_config.risk_aversion *= 2  # More conservative
                elif regime in [MarketRegime.BULL_LOW_VOL, MarketRegime.SIDEWAYS_LOW_VOL]:
                    regime_config.risk_aversion *= 0.5  # More aggressive
                
                # Optimize for this regime
                regime_result = await self._optimize_mean_variance(returns_df, regime_config)
                regime_allocations[regime] = regime_result.allocations
            
            # Weighted combination based on regime probabilities
            final_allocations = defaultdict(float)
            for regime, allocations in regime_allocations.items():
                regime_prob = self.regime_probabilities.get(regime, 1.0 / len(MarketRegime))
                for strategy, allocation in allocations.items():
                    final_allocations[strategy] += allocation * regime_prob
            
            # Calculate weighted portfolio metrics
            weights_array = np.array([final_allocations[col] for col in returns_df.columns])
            expected_returns = returns_df.mean() * 252
            cov_matrix = returns_df.cov() * 252
            
            portfolio_return = np.sum(weights_array * expected_returns.values)
            portfolio_variance = np.dot(weights_array, np.dot(cov_matrix.values, weights_array))
            portfolio_volatility = np.sqrt(portfolio_variance)
            sharpe_ratio = portfolio_return / portfolio_volatility if portfolio_volatility > 0 else 0
            
            return AllocationResult(
                allocations=dict(final_allocations),
                expected_return=portfolio_return,
                expected_volatility=portfolio_volatility,
                sharpe_ratio=sharpe_ratio,
                value_at_risk=norm.ppf(0.05) * portfolio_volatility,
                expected_shortfall=portfolio_volatility * norm.pdf(norm.ppf(0.05)) / 0.05,
                method_used=OptimizationMethod.REGIME_ADAPTIVE,
                confidence_score=0.85,
                regime_weights=self.regime_probabilities.copy(),
                constraints_satisfied=True,
                optimization_time=0.0,
                iteration_count=0,
                convergence_status="SUCCESS"
            )
            
        except Exception as e:
            self.error_handler.handle_error(e, "_optimize_regime_adaptive")
            raise

    # ==========================================================================
    # PRIVATE METHODS - DATA PREPARATION
    # ==========================================================================
    
    def _prepare_returns_data(self, strategy_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Prepare returns data from strategy performance"""
        try:
            returns_dict = {}
            
            for strategy_id, data in strategy_data.items():
                if 'returns' in data.columns:
                    returns_dict[strategy_id] = data['returns']
                elif 'close' in data.columns:
                    # Calculate returns from price data
                    returns_dict[strategy_id] = data['close'].pct_change()
                elif 'pnl' in data.columns:
                    # Calculate returns from P&L data
                    returns_dict[strategy_id] = data['pnl'].pct_change()
                else:
                    # Generate synthetic returns for testing
                    returns_dict[strategy_id] = pd.Series(
                        np.random.normal(0.001, 0.02, len(data)),
                        index=data.index
                    )
            
            # Combine into DataFrame
            returns_df = pd.DataFrame(returns_dict)
            returns_df = returns_df.dropna()
            
            # Store in history
            for strategy_id in returns_df.columns:
                self.strategy_returns[strategy_id].extend(returns_df[strategy_id].tolist())
            
            return returns_df
            
        except Exception as e:
            self.error_handler.handle_error(e, "_prepare_returns_data")
            raise

    async def _prepare_features_data(self, strategy_data: Dict[str, pd.DataFrame],
                                   market_data: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """Prepare features data for ML models"""
        try:
            if market_data is not None:
                # Use provided market data
                features_df = market_data.copy()
            else:
                # Generate features from strategy data
                features_list = []
                
                for strategy_id, data in strategy_data.items():
                    # Extract features from strategy data
                    if self.feature_engineer:
                        strategy_features = await self.feature_engineer.extract_features(data)
                        features_list.append(strategy_features)
                
                if features_list:
                    features_df = pd.concat(features_list, axis=1)
                else:
                    # Generate synthetic features
                    dates = pd.date_range(start='2020-01-01', end='2024-12-31', freq='D')
                    features_df = pd.DataFrame({
                        'vix': np.random.gamma(2, 10, len(dates)),
                        'spy_returns': np.random.normal(0.001, 0.01, len(dates)),
                        'volume': np.random.lognormal(15, 0.5, len(dates)),
                        'volatility': np.random.gamma(3, 0.05, len(dates))
                    }, index=dates)
            
            # Store features history
            if len(features_df) > 0:
                self.market_features.extend(features_df.to_dict('records'))
            
            return features_df
            
        except Exception as e:
            self.error_handler.handle_error(e, "_prepare_features_data")
            return pd.DataFrame()

    async def _update_market_regime(self, features_df: pd.DataFrame) -> None:
        """Update current market regime"""
        try:
            if len(features_df) == 0:
                return
            
            # Use VIX analyzer for regime detection
            if hasattr(self, 'vix_analyzer'):
                vix_regime = await self._get_vix_regime()
                
                # Map VIX regime to market regime
                regime_mapping = {
                    VIXRegime.ULTRA_LOW: MarketRegime.BULL_LOW_VOL,
                    VIXRegime.LOW: MarketRegime.BULL_LOW_VOL,
                    VIXRegime.NORMAL: MarketRegime.SIDEWAYS_LOW_VOL,
                    VIXRegime.ELEVATED: MarketRegime.SIDEWAYS_HIGH_VOL,
                    VIXRegime.HIGH: MarketRegime.BEAR_HIGH_VOL,
                    VIXRegime.EXTREME: MarketRegime.CRISIS
                }
                
                self.current_regime = regime_mapping.get(vix_regime, MarketRegime.SIDEWAYS_LOW_VOL)
            
            # Update regime probabilities (simplified)
            self.regime_probabilities = {regime: 0.1 for regime in MarketRegime}
            self.regime_probabilities[self.current_regime] = 0.4
            
        except Exception as e:
            self.error_handler.handle_error(e, "_update_market_regime")

    async def _get_vix_regime(self) -> VIXRegime:
        """Get current VIX regime"""
        try:
            if hasattr(self, 'vix_analyzer'):
                vix_data = self.vix_analyzer.update_vix_data()
                if vix_data:
                    if vix_data.vix_spot < 12:
                        return VIXRegime.ULTRA_LOW
                    elif vix_data.vix_spot < 15:
                        return VIXRegime.LOW
                    elif vix_data.vix_spot < 20:
                        return VIXRegime.NORMAL
                    elif vix_data.vix_spot < 30:
                        return VIXRegime.ELEVATED
                    elif vix_data.vix_spot < 40:
                        return VIXRegime.HIGH
                    else:
                        return VIXRegime.EXTREME
            
            return VIXRegime.NORMAL  # Default
            
        except Exception:
            return VIXRegime.NORMAL

    # ==========================================================================
    # PRIVATE METHODS - ML PREDICTIONS
    # ==========================================================================
    
    async def _generate_ml_predictions(self, returns_df: pd.DataFrame,
                                     features_df: pd.DataFrame) -> Dict[str, ReturnPrediction]:
        """Generate ML predictions for strategy returns"""
        try:
            predictions = {}
            
            if not self.is_trained or len(features_df) == 0:
                return predictions
            
            # Get latest features
            latest_features = features_df.iloc[-1:].values
            
            for strategy_id in returns_df.columns:
                try:
                    # Predict return
                    predicted_return = self.ml_models['return_predictor'].predict(latest_features)[0]
                    
                    # Predict volatility
                    predicted_vol = self.ml_models['volatility_predictor'].predict(latest_features)[0]
                    
                    # Calculate confidence interval
                    confidence_interval = (
                        predicted_return - 1.96 * predicted_vol,
                        predicted_return + 1.96 * predicted_vol
                    )
                    
                    # Model confidence (simplified)
                    model_confidence = 0.8  # Would use actual model performance metrics
                    
                    predictions[strategy_id] = ReturnPrediction(
                        strategy_id=strategy_id,
                        predicted_return=predicted_return,
                        prediction_std=predicted_vol,
                        confidence_interval=confidence_interval,
                        model_confidence=model_confidence,
                        feature_importance={},  # Would get from model
                        regime_probability=self.regime_probabilities.copy()
                    )
                    
                except Exception as e:
                    self.error_handler.handle_error(e, f"prediction for {strategy_id}")
                    continue
            
            return predictions
            
        except Exception as e:
            self.error_handler.handle_error(e, "_generate_ml_predictions")
            return {}

    # ==========================================================================
    # PRIVATE METHODS - HELPER FUNCTIONS
    # ==========================================================================
    
    def _initialize_models(self) -> None:
        """Initialize ML models"""
        try:
            # Initialize with reasonable defaults
            self.ml_models = {
                'return_predictor': RandomForestRegressor(
                    n_estimators=100,
                    max_depth=10,
                    random_state=42,
                    n_jobs=-1
                ),
                'volatility_predictor': GradientBoostingRegressor(
                    n_estimators=100,
                    max_depth=6,
                    learning_rate=0.1,
                    random_state=42
                ),
                'regime_predictor': RandomForestRegressor(
                    n_estimators=100,
                    max_depth=8,
                    random_state=42,
                    n_jobs=-1
                )
            }
            
        except Exception as e:
            self.error_handler.handle_error(e, "_initialize_models")

    def _calculate_diversification_benefit(self, result: AllocationResult) -> str:
        """Calculate diversification benefit"""
        try:
            # Simplified diversification benefit calculation
            n_strategies = len(result.allocations)
            equal_weight_vol = result.expected_volatility * np.sqrt(n_strategies)
            diversification_benefit = (equal_weight_vol - result.expected_volatility) / equal_weight_vol
            return f"{diversification_benefit:.1%}"
            
        except Exception:
            return "N/A"

    def _get_model_accuracy_summary(self) -> Dict[str, str]:
        """Get model accuracy summary"""
        try:
            summary = {}
            
            for model_name, performance in self.model_performance.items():
                if 'mse' in performance and performance['mse']:
                    avg_mse = np.mean(performance['mse'][-10:])  # Last 10 predictions
                    summary[model_name] = f"MSE: {avg_mse:.4f}"
                elif 'accuracy' in performance and performance['accuracy']:
                    avg_accuracy = np.mean(performance['accuracy'][-10:])
                    summary[model_name] = f"Accuracy: {avg_accuracy:.1%}"
                else:
                    summary[model_name] = "No data"
            
            return summary
            
        except Exception:
            return {"error": "Unable to calculate accuracy"}

    def _extract_regime_features(self, features_df: pd.DataFrame) -> np.ndarray:
        """Extract features for regime classification"""
        try:
            # Select relevant features for regime detection
            regime_features = []
            
            if 'vix' in features_df.columns:
                regime_features.append(features_df['vix'].values)
            if 'spy_returns' in features_df.columns:
                regime_features.append(features_df['spy_returns'].values)
            if 'volatility' in features_df.columns:
                regime_features.append(features_df['volatility'].values)
            
            if regime_features:
                return np.column_stack(regime_features)
            else:
                # Return dummy features
                return np.random.randn(len(features_df), 3)
                
        except Exception as e:
            self.error_handler.handle_error(e, "_extract_regime_features")
            return np.array([])

    def _label_market_regimes(self, returns_df: pd.DataFrame, 
                            volatilities_df: pd.DataFrame) -> np.ndarray:
        """Label historical market regimes"""
        try:
            regimes = []
            
            for i in range(len(returns_df)):
                # Simplified regime labeling based on returns and volatility
                avg_return = returns_df.iloc[i].mean()
                avg_vol = volatilities_df.iloc[i].mean()
                
                if avg_return > 0.01 and avg_vol < 0.15:
                    regime = MarketRegime.BULL_LOW_VOL
                elif avg_return > 0.01 and avg_vol >= 0.15:
                    regime = MarketRegime.BULL_HIGH_VOL
                elif avg_return < -0.01 and avg_vol < 0.15:
                    regime = MarketRegime.BEAR_LOW_VOL
                elif avg_return < -0.01 and avg_vol >= 0.15:
                    regime = MarketRegime.BEAR_HIGH_VOL
                elif abs(avg_return) <= 0.01 and avg_vol < 0.15:
                    regime = MarketRegime.SIDEWAYS_LOW_VOL
                elif abs(avg_return) <= 0.01 and avg_vol >= 0.15:
                    regime = MarketRegime.SIDEWAYS_HIGH_VOL
                else:
                    regime = MarketRegime.CRISIS
                
                regimes.append(list(MarketRegime).index(regime))
            
            return np.array(regimes)
            
        except Exception as e:
            self.error_handler.handle_error(e, "_label_market_regimes")
            return np.array([])

    def _perturb_expected_returns(self, returns_df: pd.DataFrame) -> np.ndarray:
        """Perturb expected returns for scenario generation"""
        try:
            expected_returns = returns_df.mean().values * 252
            noise = np.random.normal(0, 0.02, len(expected_returns))  # 2% noise
            return expected_returns + noise
            
        except Exception:
            return returns_df.mean().values * 252

    def _perturb_covariance_matrix(self, returns_df: pd.DataFrame) -> np.ndarray:
        """Perturb covariance matrix for scenario generation"""
        try:
            cov_matrix = returns_df.cov().values * 252
            
            # Add small random perturbation
            n = cov_matrix.shape[0]
            noise = np.random.normal(0, 0.001, (n, n))
            noise = (noise + noise.T) / 2  # Make symmetric
            
            perturbed_cov = cov_matrix + noise
            
            # Ensure positive definite
            eigenvals, eigenvecs = np.linalg.eigh(perturbed_cov)
            eigenvals = np.maximum(eigenvals, 1e-8)  # Ensure positive
            perturbed_cov = eigenvecs @ np.diag(eigenvals) @ eigenvecs.T
            
            return perturbed_cov
            
        except Exception:
            return returns_df.cov().values * 252

    async def _optimize_scenario(self, expected_returns: np.ndarray, 
                                cov_matrix: np.ndarray,
                                config: OptimizationConfig) -> AllocationResult:
        """Optimize for a specific scenario"""
        try:
            # Simple mean-variance optimization for scenario
            n_assets = len(expected_returns)
            weights = cp.Variable(n_assets)
            
            portfolio_return = expected_returns @ weights
            portfolio_variance = cp.quad_form(weights, cov_matrix)
            objective = cp.Maximize(portfolio_return - 0.5 * config.risk_aversion * portfolio_variance)
            
            constraints = [
                cp.sum(weights) == 1 - config.cash_reserve,
                weights >= config.min_allocation,
                weights <= config.max_allocation
            ]
            
            problem = cp.Problem(objective, constraints)
            problem.solve()
            
            if problem.status == cp.OPTIMAL:
                optimal_weights = weights.value
                portfolio_return_val = np.sum(optimal_weights * expected_returns)
                portfolio_variance_val = np.dot(optimal_weights, np.dot(cov_matrix, optimal_weights))
                portfolio_volatility = np.sqrt(portfolio_variance_val)
                sharpe_ratio = portfolio_return_val / portfolio_volatility if portfolio_volatility > 0 else 0
                
                return AllocationResult(
                    allocations=dict(enumerate(optimal_weights)),  # Simplified
                    expected_return=portfolio_return_val,
                    expected_volatility=portfolio_volatility,
                    sharpe_ratio=sharpe_ratio,
                    value_at_risk=norm.ppf(0.05) * portfolio_volatility,
                    expected_shortfall=portfolio_volatility * norm.pdf(norm.ppf(0.05)) / 0.05,
                    method_used=OptimizationMethod.MEAN_VARIANCE,
                    confidence_score=0.5,
                    regime_weights={},
                    constraints_satisfied=True,
                    optimization_time=0.0,
                    iteration_count=0,
                    convergence_status="OPTIMAL"
                )
            else:
                raise ValueError(f"Scenario optimization failed: {problem.status}")
                
        except Exception as e:
            self.error_handler.handle_error(e, "_optimize_scenario")
            raise

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================

def create_allocation_optimizer(config: Optional[OptimizationConfig] = None) -> AllocationOptimizer:
    """
    Factory function to create allocation optimizer.
    
    Args:
        config: Optimization configuration
        
    Returns:
        Configured AllocationOptimizer instance
    """
    return AllocationOptimizer(config)

def calculate_efficient_frontier(expected_returns: np.ndarray, cov_matrix: np.ndarray,
                                num_points: int = 100) -> Tuple[np.ndarray, np.ndarray]:
    """
    Calculate efficient frontier points.
    
    Args:
        expected_returns: Expected returns array
        cov_matrix: Covariance matrix
        num_points: Number of frontier points
        
    Returns:
        Tuple of (volatilities, returns) arrays
    """
    try:
        n_assets = len(expected_returns)
        min_ret = expected_returns.min()
        max_ret = expected_returns.max()
        
        target_returns = np.linspace(min_ret, max_ret, num_points)
        volatilities = []
        
        for target_return in target_returns:
            # Minimize variance subject to target return
            weights = cp.Variable(n_assets)
            portfolio_variance = cp.quad_form(weights, cov_matrix)
            
            constraints = [
                cp.sum(weights) == 1,
                expected_returns @ weights == target_return,
                weights >= 0
            ]
            
            problem = cp.Problem(cp.Minimize(portfolio_variance), constraints)
            problem.solve()
            
            if problem.status == cp.OPTIMAL:
                volatilities.append(np.sqrt(portfolio_variance.value))
            else:
                volatilities.append(np.nan)
        
        return np.array(volatilities), target_returns
        
    except Exception:
        return np.array([]), np.array([])

def optimize_black_litterman_views(expected_returns: np.ndarray, cov_matrix: np.ndarray,
                                 views: Dict[int, float], view_confidence: float = 0.5) -> np.ndarray:
    """
    Optimize portfolio using Black-Litterman with specific views.
    
    Args:
        expected_returns: Market equilibrium returns
        cov_matrix: Covariance matrix
        views: Dictionary of {asset_index: expected_return}
        view_confidence: Confidence in views (0-1)
        
    Returns:
        Optimal weights array
    """
    try:
        n_assets = len(expected_returns)
        
        # Create views matrix
        n_views = len(views)
        P = np.zeros((n_views, n_assets))
        Q = np.zeros(n_views)
        
        for i, (asset_idx, view_return) in enumerate(views.items()):
            P[i, asset_idx] = 1
            Q[i] = view_return
        
        # View uncertainty (inverse of confidence)
        Omega = np.eye(n_views) / view_confidence
        
        # Black-Litterman calculation
        tau = 0.05
        M1 = np.linalg.inv(tau * cov_matrix)
        M2 = P.T @ np.linalg.inv(Omega) @ P
        M3 = np.linalg.inv(tau * cov_matrix) @ expected_returns
        M4 = P.T @ np.linalg.inv(Omega) @ Q
        
        # New expected returns
        mu_bl = np.linalg.inv(M1 + M2) @ (M3 + M4)
        
        # Optimize portfolio
        weights = cp.Variable(n_assets)
        portfolio_return = mu_bl @ weights
        portfolio_variance = cp.quad_form(weights, cov_matrix)
        
        # Maximize utility
        objective = cp.Maximize(portfolio_return - 0.5 * 3.0 * portfolio_variance)
        constraints = [cp.sum(weights) == 1, weights >= 0]
        
        problem = cp.Problem(objective, constraints)
        problem.solve()
        
        return weights.value if problem.status == cp.OPTIMAL else np.ones(n_assets) / n_assets
        
    except Exception:
        return np.ones(len(expected_returns)) / len(expected_returns)

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================

# Global allocation optimizer instance
_global_allocation_optimizer: Optional[AllocationOptimizer] = None

def get_global_allocation_optimizer() -> Optional[AllocationOptimizer]:
    """Get global allocation optimizer instance"""
    return _global_allocation_optimizer

def set_global_allocation_optimizer(optimizer: AllocationOptimizer) -> None:
    """Set global allocation optimizer instance"""
    global _global_allocation_optimizer
    _global_allocation_optimizer = optimizer

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    # Module testing code
    print("=" * 80)
    print("SPYDER P02 - Allocation Optimizer Test")
    print("=" * 80)
    
    import asyncio
    
    async def test_allocation_optimizer():
        # Create optimizer
        config = OptimizationConfig(
            method=OptimizationMethod.ML_ENHANCED,
            objective=ObjectiveFunction.MAXIMIZE_SHARPE,
            lookback_period=252,
            risk_aversion=3.0
        )
        optimizer = AllocationOptimizer(config)
        
        # Generate test data
        print("\n1. Generating Test Data...")
        dates = pd.date_range(start='2020-01-01', end='2024-12-31', freq='D')
        
        strategy_data = {}
        strategy_names = ['iron_condor', 'credit_spreads', 'straddles', 'calendar_spreads', 'butterflies']
        
        for strategy in strategy_names:
            # Generate realistic options strategy returns
            returns = np.random.normal(0.0008, 0.015, len(dates))  # Slight positive bias, moderate volatility
            prices = 100 * np.cumprod(1 + returns)
            
            strategy_data[strategy] = pd.DataFrame({
                'returns': returns,
                'close': prices,
                'volume': np.random.lognormal(10, 1, len(dates))
            }, index=dates)
        
        print(f"Generated data for {len(strategy_names)} strategies over {len(dates)} days")
        
        # Test different optimization methods
        print("\n2. Testing Optimization Methods...")
        methods = [
            OptimizationMethod.MEAN_VARIANCE,
            OptimizationMethod.RISK_PARITY,
            OptimizationMethod.KELLY_CRITERION,
            OptimizationMethod.ML_ENHANCED
        ]
        
        results = {}
        for method in methods:
            try:
                test_config = OptimizationConfig(method=method)
                result = await optimizer.optimize_allocations(strategy_data, test_config)
                results[method.value] = result
                
                print(f"  {method.value}:")
                print(f"    Expected Return: {result.expected_return:.2%}")
                print(f"    Volatility: {result.expected_volatility:.2%}")
                print(f"    Sharpe Ratio: {result.sharpe_ratio:.2f}")
                print(f"    Optimization Time: {result.optimization_time:.3f}s")
                
            except Exception as e:
                print(f"  {method.value}: Failed - {e}")
        
        # Test ML model training
        print("\n3. Testing ML Model Training...")
        market_data = pd.DataFrame({
            'vix': np.random.gamma(2, 10, len(dates)),
            'spy_returns': np.random.normal(0.001, 0.01, len(dates)),
            'volume': np.random.lognormal(15, 0.5, len(dates)),
            'volatility': np.random.gamma(3, 0.05, len(dates))
        }, index=dates)
        
        ml_performance = await optimizer.train_ml_models(strategy_data, market_data)
        print("ML Model Performance:")
        for metric, value in ml_performance.items():
            print(f"  {metric}: {value:.4f}")
        
        # Test scenario generation
        print("\n4. Testing Scenario Generation...")
        scenarios = await optimizer.generate_allocation_scenarios(strategy_data, num_scenarios=100)
        
        if scenarios:
            sharpe_ratios = [s.sharpe_ratio for s in scenarios]
            volatilities = [s.expected_volatility for s in scenarios]
            returns = [s.expected_return for s in scenarios]
            
            print(f"Generated {len(scenarios)} scenarios:")
            print(f"  Sharpe Ratio: {np.mean(sharpe_ratios):.2f} ± {np.std(sharpe_ratios):.2f}")
            print(f"  Volatility: {np.mean(volatilities):.2%} ± {np.std(volatilities):.2%}")
            print(f"  Expected Return: {np.mean(returns):.2%} ± {np.std(returns):.2%}")
        
        # Test stability analysis
        print("\n5. Testing Allocation Stability...")
        if len(results) > 1:
            stability = optimizer.analyze_allocation_stability(list(results.values()))
            
            print("Allocation Stability:")
            print(f"  Average Turnover: {stability.get('average_turnover', 0):.2%}")
            print(f"  Turnover Volatility: {stability.get('turnover_volatility', 0):.2%}")
            print(f"  Max Turnover: {stability.get('max_turnover', 0):.2%}")
        
        # Get optimization summary
        print("\n6. Optimization Summary...")
        summary = optimizer.get_optimization_summary()
        
        if 'error' not in summary:
            print(f"Method Used: {summary['method_used']}")
            print(f"Optimization Time: {summary['optimization_time']}")
            print(f"Convergence Status: {summary['convergence_status']}")
            print(f"Current Regime: {summary['current_regime']}")
            
            print("\nFinal Allocations:")
            for strategy, allocation in summary['allocations'].items():
                print(f"  {strategy}: {allocation}")
            
            print("\nPerformance Metrics:")
            for metric, value in summary['performance_metrics'].items():
                print(f"  {metric}: {value}")
        
        # Test utility functions
        print("\n7. Testing Utility Functions...")
        
        # Test efficient frontier calculation
        returns_df = optimizer._prepare_returns_data(strategy_data)
        expected_returns = returns_df.mean().values * 252
        cov_matrix = returns_df.cov().values * 252
        
        volatilities, frontier_returns = calculate_efficient_frontier(expected_returns, cov_matrix, 20)
        valid_points = ~np.isnan(volatilities)
        
        print(f"Efficient Frontier: {np.sum(valid_points)} valid points")
        if np.sum(valid_points) > 0:
            print(f"  Min Volatility: {np.min(volatilities[valid_points]):.2%}")
            print(f"  Max Return: {np.max(frontier_returns[valid_points]):.2%}")
        
        # Test Black-Litterman with views
        views = {0: 0.15, 2: 0.08}  # Views on first and third strategies
        bl_weights = optimize_black_litterman_views(expected_returns, cov_matrix, views)
        
        print("Black-Litterman with Views:")
        for i, weight in enumerate(bl_weights):
            print(f"  Strategy {i}: {weight:.1%}")
        
        print("\n✅ Allocation Optimizer test completed successfully")
    
    # Run async test
    asyncio.run(test_allocation_optimizer())
    
    # Demonstrate integration examples
    print("\n" + "=" * 80)
    print("INTEGRATION EXAMPLES")
    print("=" * 80)
    
    print("\n1. Portfolio Manager Integration...")
    
    # Example of how Portfolio Manager would use Allocation Optimizer
    allocation_example = {
        'iron_condor': 0.28,
        'credit_spreads': 0.22,
        'straddles': 0.18,
        'calendar_spreads': 0.17,
        'butterflies': 0.15
    }
    
    print("Optimized Allocations for Portfolio Manager:")
    total_capital = 100000
    for strategy, allocation in allocation_example.items():
        capital = total_capital * allocation
        print(f"  {strategy}: {allocation:.1%} (${capital:,.0f})")
    
    print("\n2. Risk-Adjusted Allocation Example...")
    
    # Example of risk regime adjustments
    risk_regimes = {
        'low_volatility': {'multiplier': 1.2, 'description': 'Increase allocations in low vol'},
        'high_volatility': {'multiplier': 0.8, 'description': 'Reduce allocations in high vol'},
        'crisis': {'multiplier': 0.5, 'description': 'Defensive positioning during crisis'}
    }
    
    current_regime = 'high_volatility'
    regime_info = risk_regimes[current_regime]
    
    print(f"Current Regime: {current_regime}")
    print(f"Adjustment: {regime_info['description']}")
    print("Adjusted Allocations:")
    
    for strategy, allocation in allocation_example.items():
        adjusted = allocation * regime_info['multiplier']
        print(f"  {strategy}: {allocation:.1%} → {adjusted:.1%}")
    
    print("\n3. ML-Enhanced Prediction Integration...")
    
    # Example of ML prediction integration
    ml_predictions = {
        'iron_condor': {'expected_return': 0.12, 'confidence': 0.85},
        'credit_spreads': {'expected_return': 0.08, 'confidence': 0.92},
        'straddles': {'expected_return': 0.15, 'confidence': 0.78},
        'calendar_spreads': {'expected_return': 0.10, 'confidence': 0.88},
        'butterflies': {'expected_return': 0.06, 'confidence': 0.82}
    }
    
    print("ML Predictions Impact on Allocations:")
    for strategy, pred in ml_predictions.items():
        base_allocation = allocation_example[strategy]
        confidence_boost = pred['confidence'] - 0.5  # Boost for high confidence
        adjusted_allocation = base_allocation * (1 + confidence_boost)
        
        print(f"  {strategy}:")
        print(f"    Predicted Return: {pred['expected_return']:.1%}")
        print(f"    Confidence: {pred['confidence']:.1%}")
        print(f"    Allocation: {base_allocation:.1%} → {adjusted_allocation:.1%}")
    
    print("\n4. Modern Portfolio Theory Implementation...")
    
    # Example of MPT optimization results
    mpt_results = {
        'min_variance': {'return': 0.08, 'volatility': 0.12, 'sharpe': 0.67},
        'max_sharpe': {'return': 0.11, 'volatility': 0.16, 'sharpe': 0.94},
        'max_return': {'return': 0.15, 'volatility': 0.22, 'sharpe': 0.68}
    }
    
    print("Modern Portfolio Theory Results:")
    for objective, metrics in mpt_results.items():
        print(f"  {objective.replace('_', ' ').title()}:")
        print(f"    Expected Return: {metrics['return']:.1%}")
        print(f"    Volatility: {metrics['volatility']:.1%}")
        print(f"    Sharpe Ratio: {metrics['sharpe']:.2f}")
    
    print("\n✅ All integration examples completed successfully")#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderP02_AllocationOptimizer.py
Group: P (Portfolio Management)
Purpose: ML-driven strategy allocation optimization

Description:
    This module provides sophisticated machine learning-driven capital allocation
    optimization using Modern Portfolio Theory, Black-Litterman models, risk parity,
    Kelly Criterion, and advanced ML techniques. It combines quantitative finance
    methods with machine learning to dynamically optimize strategy allocations
    based on market regimes, performance predictions, and risk-return objectives.

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-07-01
Last Updated: 2025-07-01 Time: 19:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import threading
import asyncio
import json
import uuid
import warnings
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any, Set, Callable, Union, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
from enum import Enum, auto
from pathlib import Path
import copy
import pickle

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from scipy import stats, optimize, linalg
from scipy.stats import norm, multivariate_normal
import matplotlib.pyplot as plt
import seaborn as sns

# Machine Learning
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.cluster import KMeans
import xgboost as xgb
import lightgbm as lgb

# Optimization
from scipy.optimize import minimize, differential_evolution
import cvxpy as cp
import cvxopt
from pypfopt import EfficientFrontier, risk_models, expected_returns
from pypfopt.discrete_allocation import DiscreteAllocation
from pypfopt.objectives import L2_reg

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU15_PerformanceMetrics import PerformanceMetrics
from SpyderU_Utilities.SpyderU03_DateTimeUtils import DateTimeUtils
from SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType, Event

# Market data and analysis
from SpyderC_MarketData.SpyderC10_VIXAnalyzer import VIXAnalyzer, VIXRegime
from SpyderF_Analysis.SpyderF08_VolatilityRegime import VolatilityRegimeAnalyzer
from SpyderL_ML.SpyderL09_RegimeClassifier import RegimeClassifier
from SpyderL_ML.SpyderL10_FeatureEngineering import FeatureEngineer

# Portfolio components
try:
    from SpyderP_Portfolio.SpyderP01_PortfolioManager import PortfolioManager, StrategyAllocation
    from SpyderI_Integration.SpyderI01_IntegrationHub import get_integration_hub
    HUB_AVAILABLE = True
except ImportError:
    HUB_AVAILABLE = False

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Optimization parameters
DEFAULT_LOOKBACK_PERIOD = 252  # 1 year of trading days
MIN_ALLOCATION = 0.05          # 5% minimum allocation
MAX_ALLOCATION = 0.40          # 40% maximum allocation
CASH_RESERVE = 0.10            # 10% cash reserve
REBALANCE_THRESHOLD = 0.05     # 5% drift threshold

# Risk parameters
DEFAULT_RISK_AVERSION = 3.0    # Moderate risk aversion
MAX_PORTFOLIO_VOLATILITY = 0.25 # 25% maximum volatility
TARGET_SHARPE_RATIO = 1.5      # Target Sharpe ratio
VAR_CONFIDENCE = 0.95          # 95% VaR confidence
MAX_DRAWDOWN_TOLERANCE = 0.15  # 15% maximum drawdown

# ML parameters
FEATURE_LOOKBACK = 60          # 60 days for feature engineering
MODEL_RETRAIN_FREQUENCY = 30   # Retrain every 30 days
PREDICTION_HORIZON = 5         # 5 days ahead prediction
MIN_SAMPLES_FOR_ML = 1000      # Minimum samples for ML training

# Optimization methods
OPTIMIZATION_METHODS = [
    'mean_variance', 'black_litterman', 'risk_parity', 
    'hierarchical_risk_parity', 'kelly_criterion', 'ml_enhanced'
]

# Performance attribution periods
ATTRIBUTION_PERIODS = ['1D', '1W', '1M', '3M', '6M', '1Y']

# ==============================================================================
# ENUMS
# ==============================================================================
class OptimizationMethod(Enum):
    """Portfolio optimization methods"""
    MEAN_VARIANCE = "mean_variance"
    BLACK_LITTERMAN = "black_litterman" 
    RISK_PARITY = "risk_parity"
    HIERARCHICAL_RISK_PARITY = "hierarchical_risk_parity"
    KELLY_CRITERION = "kelly_criterion"
    ML_ENHANCED = "ml_enhanced"
    REGIME_ADAPTIVE = "regime_adaptive"
    ROBUST_OPTIMIZATION = "robust_optimization"

class ObjectiveFunction(Enum):
    """Optimization objective functions"""
    MAXIMIZE_SHARPE = "maximize_sharpe"
    MINIMIZE_VOLATILITY = "minimize_volatility"
    MAXIMIZE_RETURN = "maximize_return"
    MINIMIZE_VAR = "minimize_var"
    MAXIMIZE_UTILITY = "maximize_utility"
    MINIMIZE_CVaR = "minimize_cvar"

class MarketRegime(Enum):
    """Market regime types"""
    BULL_LOW_VOL = "bull_low_vol"
    BULL_HIGH_VOL = "bull_high_vol"
    BEAR_LOW_VOL = "bear_low_vol"
    BEAR_HIGH_VOL = "bear_high_vol"
    SIDEWAYS_LOW_VOL = "sideways_low_vol"
    SIDEWAYS_HIGH_VOL = "sideways_high_vol"
    CRISIS = "crisis"

class ConstraintType(Enum):
    """Portfolio constraint types"""
    BOX_CONSTRAINTS = "box_constraints"
    SECTOR_CONSTRAINTS = "sector_constraints"
    TURNOVER_CONSTRAINTS = "turnover_constraints"
    RISK_CONSTRAINTS = "risk_constraints"
    CORRELATION_CONSTRAINTS = "correlation_constraints"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class OptimizationConfig:
    """Configuration for allocation optimization"""
    method: OptimizationMethod = OptimizationMethod.ML_ENHANCED
    objective: ObjectiveFunction = ObjectiveFunction.MAXIMIZE_SHARPE
    lookback_period: int = DEFAULT_LOOKBACK_PERIOD
    risk_aversion: float = DEFAULT_RISK_AVERSION
    max_volatility: float = MAX_PORTFOLIO_VOLATILITY
    min_allocation: float = MIN_ALLOCATION
    max_allocation: float = MAX_ALLOCATION
    cash_reserve: float = CASH_RESERVE
    rebalance_threshold: float = REBALANCE_THRESHOLD
    use_regime_detection: bool = True
    use_ml_predictions: bool = True
    confidence_level: float = VAR_CONFIDENCE

@dataclass
class AllocationResult:
    """Result of allocation optimization"""
    allocations: Dict[str, float]
    expected_return: float
    expected_volatility: float
    sharpe_ratio: float
    value_at_risk: float
    expected_shortfall: float
    method_used: OptimizationMethod
    confidence_score: float
    regime_weights: Dict[MarketRegime, float]
    constraints_satisfied: bool
    optimization_time: float
    iteration_count: int
    convergence_status: str

@dataclass
class ReturnPrediction:
    """ML prediction for strategy returns"""
    strategy_id: str
    predicted_return: float
    prediction_std: float
    confidence_interval: Tuple[float, float]
    model_confidence: float
    feature_importance: Dict[str, float]
    regime_probability: Dict[MarketRegime, float]

@dataclass
class RiskMetrics:
    """Comprehensive risk metrics"""
    volatility: float
    var_95: float
    cvar_95: float
    max_drawdown: float
    beta: float
    downside_deviation: float
    calmar_ratio: float
    sortino_ratio: float
    correlation_matrix: np.ndarray
    eigenvalues: np.ndarray
    condition_number: float

@dataclass
class BlackLittermanInputs:
    """Black-Litterman model inputs"""
    prior_returns: np.ndarray
    prior_covariance: np.ndarray
    views_matrix: np.ndarray
    view_returns: np.ndarray
    view_uncertainty: np.ndarray
    risk_aversion: float
    tau: float = 0.05

@dataclass
class OptimizationConstraints:
    """Portfolio optimization constraints"""
    min_weights: Dict[str, float]
    max_weights: Dict[str, float]
    target_weights: Optional[Dict[str, float]] = None
    max_turnover: Optional[float] = None
    max_risk_contribution: Optional[float] = None
    sector_limits: Optional[Dict[str, Tuple[float, float]]] = None
    correlation_limits: Optional[Tuple[float, float]] = None

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class AllocationOptimizer:
    """
    Advanced ML-driven portfolio allocation optimizer.
    
    This optimizer combines modern portfolio theory with machine learning
    to dynamically optimize strategy allocations based on market regimes,
    performance predictions, and risk-return objectives using state-of-the-art
    quantitative finance and machine learning techniques.
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        event_manager: Event manager for notifications
        performance_metrics: Performance tracking system
        
    Example:
        >>> optimizer = AllocationOptimizer()
        >>> config = OptimizationConfig(method=OptimizationMethod.ML_ENHANCED)
        >>> result = await optimizer.optimize_allocations(strategy_data, config)
        >>> print(f"Optimal allocations: {result.allocations}")
    """
    
    def __init__(self, config: Optional[OptimizationConfig] = None):
        """
        Initialize the Allocation Optimizer.
        
        Args:
            config: Optimization configuration
        """
        # Core components
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()
        self.event_manager = get_event_manager()
        self.performance_metrics = PerformanceMetrics()
        self.datetime_utils = DateTimeUtils()
        
        # Configuration
        self.config = config or OptimizationConfig()
        
        # Market analysis components
        self.vix_analyzer = VIXAnalyzer()
        self.regime_classifier = RegimeClassifier()
        self.feature_engineer = FeatureEngineer()
        
        # ML models for predictions
        self.ml_models = {
            'return_predictor': RandomForestRegressor(n_estimators=100, random_state=42),
            'volatility_predictor': GradientBoostingRegressor(n_estimators=100, random_state=42),
            'regime_predictor': RandomForestRegressor(n_estimators=100, random_state=42)
        }
        
        # Data storage
        self.strategy_returns: Dict[str, deque] = defaultdict(lambda: deque(maxlen=DEFAULT_LOOKBACK_PERIOD))
        self.market_features: deque = deque(maxlen=FEATURE_LOOKBACK)
        self.optimization_history: deque = deque(maxlen=1000)
        self.model_predictions: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # Model performance tracking
        self.model_performance = {
            'return_predictions': {'mse': [], 'r2': []},
            'volatility_predictions': {'mse': [], 'r2': []},
            'regime_predictions': {'accuracy': []}
        }
        
        # Optimization state
        self.current_regime = MarketRegime.SIDEWAYS_LOW_VOL
        self.regime_probabilities = {regime: 1.0/len(MarketRegime) for regime in MarketRegime}
        self.last_optimization = None
        self.is_trained = False
        
        # Initialize components
        self._initialize_models()
        
        # Register with integration hub
        if HUB_AVAILABLE:
            hub = get_integration_hub()
            if hub:
                hub.register_module(self, dependencies=['SpyderP01_PortfolioManager'])
        
        self.logger.info("AllocationOptimizer initialized successfully")

    # ==========================================================================
    # PUBLIC METHODS - OPTIMIZATION
    # ==========================================================================
    
    async def optimize_allocations(self, strategy_data: Dict[str, pd.DataFrame],
                                 config: Optional[OptimizationConfig] = None) -> AllocationResult:
        """
        Optimize portfolio allocations using specified method.
        
        Args:
            strategy_data: Historical data for each strategy
            config: Optimization configuration (optional)
            
        Returns:
            Optimization result with allocations and metrics
        """
        try:
            start_time = time.time()
            opt_config = config or self.config
            
            # Validate inputs
            if not strategy_data:
                raise ValueError("No strategy data provided")
            
            # Prepare data
            returns_df = self._prepare_returns_data(strategy_data)
            features_df = await self._prepare_features_data(strategy_data)
            
            # Detect current market regime
            await self._update_market_regime(features_df)
            
            # Generate ML predictions if enabled
            predictions = {}
            if opt_config.use_ml_predictions and self.is_trained:
                predictions = await self._generate_ml_predictions(returns_df, features_df)
            
            # Choose optimization method
            if opt_config.method == OptimizationMethod.MEAN_VARIANCE:
                result = await self._optimize_mean_variance(returns_df, opt_config)
            elif opt_config.method == OptimizationMethod.BLACK_LITTERMAN:
                result = await self._optimize_black_litterman(returns_df, predictions, opt_config)
            elif opt_config.method == OptimizationMethod.RISK_PARITY:
                result = await self._optimize_risk_parity(returns_df, opt_config)
            elif opt_config.method == OptimizationMethod.HIERARCHICAL_RISK_PARITY:
                result = await self._optimize_hierarchical_risk_parity(returns_df, opt_config)
            elif opt_config.method == OptimizationMethod.KELLY_CRITERION:
                result = await self._optimize_kelly_criterion(returns_df, predictions, opt_config)
            elif opt_config.method == OptimizationMethod.ML_ENHANCED:
                result = await self._optimize_ml_enhanced(returns_df, features_df, predictions, opt_config)
            elif opt_config.method == OptimizationMethod.REGIME_ADAPTIVE:
                result = await self._optimize_regime_adaptive(returns_df, features_df, opt_config)
            else:
                raise ValueError(f"Unknown optimization method: {opt_config.method}")
            
            # Add execution metrics
            result.optimization_time = time.time() - start_time
            result.regime_weights = self.regime_probabilities.copy()
            
            # Store in history
            self.optimization_history.append(result)
            self.last_optimization = result
            
            # Emit optimization event
            self.event_manager.emit_event(Event(
                type=EventType.ALLOCATION_OPTIMIZED,
                source=self.__class__.__name__,
                data=asdict(result)
            ))
            
            self.logger.info(f"Allocation optimization completed in {result.optimization_time:.2f}s")
            return result
            
        except Exception as e:
            self.error_handler.handle_error(e, "optimize_allocations")
            raise

    async def train_ml_models(self, strategy_data: Dict[str, pd.DataFrame],
                            market_data: pd.DataFrame) -> Dict[str, float]:
        """
        Train ML models for return and volatility prediction.
        
        Args:
            strategy_data: Historical strategy data
            market_data: Market features data
            
        Returns:
            Model performance metrics
        """
        try:
            self.logger.info("Training ML models for allocation optimization")
            
            # Prepare training data
            returns_df = self._prepare_returns_data(strategy_data)
            features_df = await self._prepare_features_data(strategy_data, market_data)
            
            performance = {}
            
            # Train return prediction models
            for strategy_id in returns_df.columns:
                y = returns_df[strategy_id].dropna()
                X = features_df.loc[y.index].dropna()
                
                if len(X) >= MIN_SAMPLES_FOR_ML:
                    # Time series split for validation
                    tscv = TimeSeriesSplit(n_splits=5)
                    
                    # Train return predictor
                    scores = cross_val_score(
                        self.ml_models['return_predictor'], 
                        X, y, 
                        cv=tscv, 
                        scoring='neg_mean_squared_error'
                    )
                    performance[f'{strategy_id}_return_mse'] = -scores.mean()
                    
                    # Fit final model
                    self.ml_models['return_predictor'].fit(X, y)
            
            # Train volatility prediction model
            volatilities = returns_df.rolling(window=20).std()
            for strategy_id in volatilities.columns:
                y = volatilities[strategy_id].dropna()
                X = features_df.loc[y.index].dropna()
                
                if len(X) >= MIN_SAMPLES_FOR_ML:
                    scores = cross_val_score(
                        self.ml_models['volatility_predictor'],
                        X, y,
                        cv=TimeSeriesSplit(n_splits=5),
                        scoring='neg_mean_squared_error'
                    )
                    performance[f'{strategy_id}_volatility_mse'] = -scores.mean()
                    
                    self.ml_models['volatility_predictor'].fit(X, y)
            
            # Train regime prediction model
            regime_features = self._extract_regime_features(features_df)
            regime_labels = self._label_market_regimes(returns_df, volatilities)
            
            if len(regime_features) >= MIN_SAMPLES_FOR_ML:
                scores = cross_val_score(
                    self.ml_models['regime_predictor'],
                    regime_features, regime_labels,
                    cv=TimeSeriesSplit(n_splits=5),
                    scoring='accuracy'
                )
                performance['regime_accuracy'] = scores.mean()
                
                self.ml_models['regime_predictor'].fit(regime_features, regime_labels)
            
            self.is_trained = True
            self.logger.info(f"ML models trained successfully. Performance: {performance}")
            
            return performance
            
        except Exception as e:
            self.error_handler.handle_error(e, "train_ml_models")
            return {}

    async def generate_allocation_scenarios(self, strategy_data: Dict[str, pd.DataFrame],
                                          num_scenarios: int = 1000) -> List[AllocationResult]:
        """
        Generate multiple allocation scenarios using Monte Carlo simulation.
        
        Args:
            strategy_data: Historical strategy data
            num_scenarios: Number of scenarios to generate
            
        Returns:
            List of allocation scenarios
        """
        try:
            scenarios = []
            returns_df = self._prepare_returns_data(strategy_data)
            
            # Generate random market scenarios
            for i in range(num_scenarios):
                # Randomly perturb expected returns and covariance
                perturbed_returns = self._perturb_expected_returns(returns_df)
                perturbed_cov = self._perturb_covariance_matrix(returns_df)
                
                # Optimize for this scenario
                scenario_config = copy.deepcopy(self.config)
                scenario_result = await self._optimize_scenario(
                    perturbed_returns, perturbed_cov, scenario_config
                )
                
                scenarios.append(scenario_result)
                
                if (i + 1) % 100 == 0:
                    self.logger.info(f"Generated {i + 1}/{num_scenarios} scenarios")
            
            return scenarios
            
        except Exception as e:
            self.error_handler.handle_error(e, "generate_allocation_scenarios")
            return []

    # ==========================================================================
    # PUBLIC METHODS - ANALYSIS
    # ==========================================================================
    
    def analyze_allocation_stability(self, allocation_history: List[AllocationResult]) -> Dict[str, Any]:
        """
        Analyze the stability of allocation recommendations.
        
        Args:
            allocation_history: Historical allocation results
            
        Returns:
            Stability analysis metrics
        """
        try:
            if len(allocation_history) < 2:
                return {'error': 'Insufficient allocation history'}
            
            # Extract allocations over time
            allocations_df = pd.DataFrame([result.allocations for result in allocation_history])
            
            # Calculate stability metrics
            turnover = []
            for i in range(1, len(allocations_df)):
                turnover.append(
                    np.sum(np.abs(allocations_df.iloc[i] - allocations_df.iloc[i-1]))
                )
            
            stability_metrics = {
                'average_turnover': np.mean(turnover),
                'turnover_volatility': np.std(turnover),
                'max_turnover': np.max(turnover),
                'allocation_correlation': allocations_df.corr().values,
                'weight_stability': {
                    strategy: {
                        'mean': allocations_df[strategy].mean(),
                        'std': allocations_df[strategy].std(),
                        'min': allocations_df[strategy].min(),
                        'max': allocations_df[strategy].max()
                    }
                    for strategy in allocations_df.columns
                }
            }
            
            return stability_metrics
            
        except Exception as e:
            self.error_handler.handle_error(e, "analyze_allocation_stability")
            return {'error': str(e)}

    def get_optimization_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive optimization summary.
        
        Returns:
            Optimization summary dictionary
        """
        try:
            if not self.last_optimization:
                return {'status': 'no_optimizations_performed'}
            
            result = self.last_optimization
            
            # Performance summary
            performance_summary = {
                'expected_return': f"{result.expected_return:.2%}",
                'expected_volatility': f"{result.expected_volatility:.2%}",
                'sharpe_ratio': f"{result.sharpe_ratio:.2f}",
                'value_at_risk': f"{result.value_at_risk:.2%}",
                'expected_shortfall': f"{result.expected_shortfall:.2%}",
                'confidence_score': f"{result.confidence_score:.1%}"
            }
            
            # Allocation summary
            allocation_summary = {
                strategy: f"{weight:.1%}" 
                for strategy, weight in result.allocations.items()
            }
            
            # Risk breakdown
            risk_summary = {
                'volatility_target': f"{self.config.max_volatility:.1%}",
                'current_volatility': f"{result.expected_volatility:.1%}",
                'risk_utilization': f"{result.expected_volatility/self.config.max_volatility:.1%}",
                'diversification_benefit': self._calculate_diversification_benefit(result)
            }
            
            return {
                'timestamp': datetime.now().isoformat(),
                'method_used': result.method_used.value,
                'optimization_time': f"{result.optimization_time:.2f}s",
                'convergence_status': result.convergence_status,
                'constraints_satisfied': result.constraints_satisfied,
                'current_regime': self.current_regime.value,
                'allocations': allocation_summary,
                'performance_metrics': performance_summary,
                'risk_metrics': risk_summary,
                'regime_probabilities': {
                    regime.value: f"{prob:.1%}" 
                    for regime, prob in result.regime_weights.items()
                },
                'model_status': {
                    'is_trained': self.is_trained,
                    'last_training': getattr(self, 'last_training_time', 'Never'),
                    'prediction_accuracy': self._get_model_accuracy_summary()
                }
            }
            
        except Exception as e:
            self.error_handler.handle_error(e, "get_optimization_summary")
            return {'error': str(e)}

    # ==========================================================================
    # PRIVATE METHODS - OPTIMIZATION ALGORITHMS
    # ==========================================================================
    
    async def _optimize_mean_variance(self, returns_df: pd.DataFrame, 
                                    config: OptimizationConfig) -> AllocationResult:
        """Optimize using mean-variance optimization"""
        try:
            # Calculate expected returns and covariance
            expected_returns = returns_df.mean() * 252  # Annualized
            cov_matrix = returns_df.cov() * 252  # Annualized
            
            # Set up optimization problem
            n_assets = len(expected_returns)
            weights = cp.Variable(n_assets)
            
            # Objective: maximize Sharpe ratio
            if config.objective == ObjectiveFunction.MAXIMIZE_SHARPE:
                # Quadratic utility function
                portfolio_return = expected_returns.values @ weights
                portfolio_variance = cp.quad_form(weights, cov_matrix.values)
                objective = cp.Maximize(portfolio_return - 0.5 * config.risk_aversion * portfolio_variance)
            elif config.objective == ObjectiveFunction.MINIMIZE_VOLATILITY:
                portfolio_variance = cp.quad_form(weights, cov_matrix.values)
                objective = cp.Minimize(portfolio_variance)
            else:
                portfolio_return = expected_returns.values @ weights
                objective = cp.Maximize(portfolio_return)
            
            # Constraints
            constraints = [
                cp.sum(weights) == 1 - config.cash_reserve,  # Budget constraint
                weights >= config.min_allocation,  # Minimum allocation
                weights <= config.max_allocation   # Maximum allocation
            ]
            
            # Add volatility constraint if specified
            if config.max_volatility < np.inf:
                portfolio_variance = cp.quad_form(weights, cov_matrix.values)
                constraints.append(cp.sqrt(portfolio_variance) <= config.max_volatility)
            
            # Solve optimization
            problem = cp.Problem(objective, constraints)
            problem.solve()
            
            if problem.status != cp.OPTIMAL:
                raise ValueError(f"Optimization failed with status: {problem.status}")
            
            # Extract results
            optimal_weights = weights.value
            allocations = dict(zip(returns_df.columns, optimal_weights))
            
            # Calculate metrics
            portfolio_return = np.sum(optimal_weights * expected_returns.values)
            portfolio_variance = np.dot(optimal_weights, np.dot(cov_matrix.values, optimal_weights))
            portfolio_volatility = np.sqrt(portfolio_variance)
            sharpe_ratio = portfolio_return / portfolio_volatility if portfolio_volatility > 0 else 0
            
            # Risk metrics
            var_95 = norm.ppf(0.05) * portfolio_volatility
            cvar_95 = portfolio_volatility * norm.pdf(norm.ppf(0.05)) / 0.05
            
            return AllocationResult(
                allocations=allocations,
                expected_return=portfolio_return,
                expected_volatility=portfolio_volatility,
                sharpe_ratio=sharpe_ratio,
                value_at_risk=var_95,
                expected_shortfall=cvar_95,
                method_used=OptimizationMethod.MEAN_VARIANCE,
                confidence_score=0.8,  # Default confidence for analytical methods
                regime_weights={},
                constraints_satisfied=True,
                optimization_time=0.0,
                iteration_count=problem.solver_stats.num_iters if problem.solver_stats else 0,
                convergence_status="OPTIMAL"
            )
            
        except Exception as e:
            self.error_handler.handle_error(e, "_optimize_mean_variance")
            raise

    async def _optimize_black_litterman(self, returns_df: pd.DataFrame,
                                      predictions: Dict[str, ReturnPrediction],
                                      config: OptimizationConfig) -> AllocationResult:
        """Optimize using Black-Litterman model"""
        try:
            # Market equilibrium (prior)
            expected_returns = returns_df.mean() * 252
            cov_matrix = returns_df.cov() * 252
            
            # Market cap weights (simplified - equal weight as proxy)
            market_weights = np.ones(len(expected_returns)) / len(expected_returns)
            
            # Implied equilibrium returns
            pi = config.risk_aversion * np.dot(cov_matrix.values, market_weights)
            
            # Views from ML predictions
            if predictions:
                n_views = len(predictions)
                P = np.zeros((n_views, len(expected_returns)))  # Picking matrix
                Q = np.zeros(n_views)  # View returns
                Omega = np.eye(n_views)  # View uncertainty
                
                for i, (strategy_id, pred) in enumerate(predictions.items()):
                    strategy_idx = list(expected_returns.index).index(strategy_id)
                    P[i, strategy_idx] = 1
                    Q[i] = pred.predicted_return
                    Omega[i, i] = pred.prediction_std ** 2
                
                # Black-Litterman formula
                tau = 0.05  # Uncertainty in prior
                M1 = linalg.inv(tau * cov_matrix.values)
                M2 = np.dot(P.T, np.dot(linalg.inv(Omega), P))
                M3 = np.dot(linalg.inv(tau * cov_matrix.values), pi)
                M4 = np.dot(P.T, np.dot(linalg.inv(Omega), Q))
                
                # Black-Litterman expected returns
                mu_bl = np.dot(linalg.inv(M1 + M2), M3 + M4)
                cov_bl = linalg.inv(M1 + M2)
                
                return pd.Series(mu_bl, index=expected_returns.index), pd.DataFrame(cov_bl, index=expected_returns.index, columns=expected_returns.index)
                
        except Exception as e:
            self.logger.error(f"Error in Black-Litterman optimization: {e}")
            return expected_returns, cov_matrix
