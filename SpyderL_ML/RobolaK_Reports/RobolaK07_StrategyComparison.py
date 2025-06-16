#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderK07_StrategyComparison.py
Group: K (Reports)
Purpose: Advanced strategy comparison and portfolio optimization

Description:
    This module provides comprehensive strategy comparison tools including
    statistical analysis, correlation metrics, optimal allocation calculations,
    and market regime performance analysis. It helps identify the best strategy
    combinations and allocation weights for portfolio optimization.

Author: Mohamed Talib
Date: 2025-06-01
Version: 1.0.0
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import datetime
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from collections import defaultdict
import json
import itertools
from scipy import stats, optimize
from scipy.cluster import hierarchy
import warnings

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.patches import Rectangle
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderH_Storage.SpyderH07_PerformanceAnalytics import (
    PerformanceAnalytics, PerformanceMetrics, StrategyPerformance
)
from SpyderH_Storage.SpyderH02_TradeRepository import TradeRepository
from SpyderC_MarketData.SpyderC04_MarketInternals import MarketRegime

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Statistical parameters
MIN_CORRELATION_PERIOD = 30  # days
SIGNIFICANCE_LEVEL = 0.05
CONFIDENCE_INTERVAL = 0.95
MIN_TRADES_FOR_COMPARISON = 20

# Portfolio optimization
MAX_POSITION_SIZE = 0.40  # Maximum 40% in any strategy
MIN_POSITION_SIZE = 0.05  # Minimum 5% allocation
TARGET_VOLATILITY = 0.15  # 15% annual target volatility

# Comparison metrics
COMPARISON_METRICS = [
    'sharpe_ratio', 'sortino_ratio', 'calmar_ratio', 'win_rate',
    'profit_factor', 'max_drawdown', 'var_95', 'expectancy'
]

# Market regimes
MARKET_REGIMES = ['bull', 'bear', 'sideways', 'high_volatility', 'low_volatility']

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class StrategyComparison:
    """Strategy comparison results"""
    strategy1: str
    strategy2: str
    
    # Correlation metrics
    returns_correlation: float = 0.0
    rolling_correlation: pd.Series = field(default_factory=pd.Series)
    correlation_stability: float = 0.0
    
    # Performance comparison
    performance_differential: Dict[str, float] = field(default_factory=dict)
    statistical_significance: Dict[str, float] = field(default_factory=dict)
    
    # Risk metrics
    combined_sharpe: float = 0.0
    diversification_benefit: float = 0.0
    correlation_breakdown: Dict[str, float] = field(default_factory=dict)
    
    # Regime analysis
    regime_correlation: Dict[str, float] = field(default_factory=dict)
    regime_performance: Dict[str, Dict[str, float]] = field(default_factory=dict)

@dataclass
class PortfolioOptimization:
    """Optimal portfolio allocation results"""
    strategies: List[str]
    weights: Dict[str, float]
    
    # Portfolio metrics
    expected_return: float = 0.0
    expected_volatility: float = 0.0
    expected_sharpe: float = 0.0
    
    # Risk metrics
    portfolio_var: float = 0.0
    portfolio_cvar: float = 0.0
    max_drawdown: float = 0.0
    
    # Contribution analysis
    return_contribution: Dict[str, float] = field(default_factory=dict)
    risk_contribution: Dict[str, float] = field(default_factory=dict)
    
    # Efficient frontier
    efficient_frontier: pd.DataFrame = field(default_factory=pd.DataFrame)

@dataclass
class StrategyRanking:
    """Strategy ranking results"""
    metric: str
    rankings: Dict[str, float]
    
    # Statistical tests
    significance_matrix: pd.DataFrame = field(default_factory=pd.DataFrame)
    confidence_intervals: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    
    # Regime-specific rankings
    regime_rankings: Dict[str, Dict[str, float]] = field(default_factory=dict)

# ==============================================================================
# STRATEGY COMPARISON CLASS
# ==============================================================================
class StrategyComparisonAnalyzer:
    """
    Advanced strategy comparison and portfolio optimization.
    
    This class provides comprehensive tools for comparing trading strategies,
    identifying correlations, optimizing portfolio allocations, and analyzing
    performance across different market regimes.
    """
    
    def __init__(
        self,
        performance_analytics: PerformanceAnalytics,
        trade_repository: TradeRepository
    ):
        """
        Initialize strategy comparison analyzer.
        
        Args:
            performance_analytics: Performance analytics instance
            trade_repository: Trade repository instance
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.performance_analytics = performance_analytics
        self.trade_repository = trade_repository
        
        # Cache for computed results
        self._correlation_cache = {}
        self._optimization_cache = {}
        self._returns_cache = {}
        
        self.logger.info("StrategyComparisonAnalyzer initialized")
    
    # ==========================================================================
    # PUBLIC METHODS - STRATEGY COMPARISON
    # ==========================================================================
    
    def compare_strategies(
        self,
        strategy1: str,
        strategy2: str,
        start_date: Optional[datetime.date] = None,
        end_date: Optional[datetime.date] = None,
        include_regime_analysis: bool = True
    ) -> StrategyComparison:
        """
        Perform comprehensive comparison between two strategies.
        
        Args:
            strategy1: First strategy name
            strategy2: Second strategy name
            start_date: Start date for comparison
            end_date: End date for comparison
            include_regime_analysis: Include market regime analysis
            
        Returns:
            StrategyComparison results
        """
        try:
            self.logger.info(f"Comparing {strategy1} vs {strategy2}")
            
            # Get performance data
            perf1 = self.performance_analytics.calculate_performance(
                strategy1, start_date, end_date
            )
            perf2 = self.performance_analytics.calculate_performance(
                strategy2, start_date, end_date
            )
            
            if not perf1 or not perf2:
                self.logger.error("Insufficient data for comparison")
                return StrategyComparison(strategy1, strategy2)
            
            # Get returns data
            returns1 = self._get_strategy_returns(strategy1, start_date, end_date)
            returns2 = self._get_strategy_returns(strategy2, start_date, end_date)
            
            # Align returns
            aligned_returns = pd.DataFrame({
                strategy1: returns1,
                strategy2: returns2
            }).dropna()
            
            comparison = StrategyComparison(strategy1, strategy2)
            
            # Calculate correlations
            comparison = self._calculate_correlations(comparison, aligned_returns)
            
            # Performance comparison
            comparison = self._compare_performance_metrics(comparison, perf1, perf2)
            
            # Statistical significance
            comparison = self._calculate_statistical_significance(
                comparison, aligned_returns
            )
            
            # Diversification analysis
            comparison = self._analyze_diversification_benefit(
                comparison, aligned_returns
            )
            
            # Regime analysis
            if include_regime_analysis:
                comparison = self._analyze_regime_performance(
                    comparison, aligned_returns, start_date, end_date
                )
            
            return comparison
            
        except Exception as e:
            self.logger.error(f"Error comparing strategies: {e}")
            self.error_handler.handle_error(e)
            return StrategyComparison(strategy1, strategy2)
    
    def compare_all_strategies(
        self,
        strategies: Optional[List[str]] = None,
        metric: str = 'sharpe_ratio',
        start_date: Optional[datetime.date] = None,
        end_date: Optional[datetime.date] = None
    ) -> pd.DataFrame:
        """
        Create comparison matrix for all strategies.
        
        Args:
            strategies: List of strategies or None for all
            metric: Metric to compare
            start_date: Start date
            end_date: End date
            
        Returns:
            DataFrame with comparison matrix
        """
        try:
            # Get all strategies if not specified
            if not strategies:
                all_trades = self.trade_repository.get_trades(
                    start_date=start_date, end_date=end_date
                )
                strategies = list(set(t.strategy for t in all_trades))
            
            # Create comparison matrix
            n = len(strategies)
            matrix = pd.DataFrame(
                index=strategies,
                columns=strategies,
                dtype=float
            )
            
            # Calculate pairwise comparisons
            for i in range(n):
                for j in range(n):
                    if i == j:
                        matrix.iloc[i, j] = 1.0
                    else:
                        comparison = self.compare_strategies(
                            strategies[i], strategies[j],
                            start_date, end_date,
                            include_regime_analysis=False
                        )
                        
                        if metric == 'correlation':
                            matrix.iloc[i, j] = comparison.returns_correlation
                        elif metric in comparison.performance_differential:
                            # Ratio of metric values
                            diff = comparison.performance_differential[metric]
                            matrix.iloc[i, j] = 1 + diff  # Convert differential to ratio
                        else:
                            matrix.iloc[i, j] = np.nan
            
            return matrix
            
        except Exception as e:
            self.logger.error(f"Error creating comparison matrix: {e}")
            return pd.DataFrame()
    
    # ==========================================================================
    # PUBLIC METHODS - PORTFOLIO OPTIMIZATION
    # ==========================================================================
    
    def optimize_portfolio(
        self,
        strategies: List[str],
        optimization_method: str = 'sharpe',
        constraints: Optional[Dict[str, Any]] = None,
        start_date: Optional[datetime.date] = None,
        end_date: Optional[datetime.date] = None
    ) -> PortfolioOptimization:
        """
        Optimize portfolio allocation across strategies.
        
        Args:
            strategies: List of strategies to include
            optimization_method: 'sharpe', 'min_variance', 'risk_parity'
            constraints: Additional constraints
            start_date: Start date for optimization
            end_date: End date for optimization
            
        Returns:
            PortfolioOptimization results
        """
        try:
            self.logger.info(f"Optimizing portfolio with {len(strategies)} strategies")
            
            # Get returns for all strategies
            returns_dict = {}
            for strategy in strategies:
                returns = self._get_strategy_returns(strategy, start_date, end_date)
                if not returns.empty:
                    returns_dict[strategy] = returns
            
            if len(returns_dict) < 2:
                self.logger.error("Need at least 2 strategies for optimization")
                return PortfolioOptimization(strategies, {})
            
            # Create aligned returns dataframe
            returns_df = pd.DataFrame(returns_dict).dropna()
            
            # Calculate optimization inputs
            mean_returns = returns_df.mean() * 252  # Annualized
            cov_matrix = returns_df.cov() * 252  # Annualized
            
            # Set up constraints
            if constraints is None:
                constraints = {}
            
            min_weight = constraints.get('min_weight', MIN_POSITION_SIZE)
            max_weight = constraints.get('max_weight', MAX_POSITION_SIZE)
            
            # Optimize based on method
            if optimization_method == 'sharpe':
                weights = self._optimize_sharpe_ratio(
                    mean_returns, cov_matrix, min_weight, max_weight
                )
            elif optimization_method == 'min_variance':
                weights = self._optimize_min_variance(
                    cov_matrix, min_weight, max_weight
                )
            elif optimization_method == 'risk_parity':
                weights = self._optimize_risk_parity(
                    cov_matrix, min_weight, max_weight
                )
            else:
                raise ValueError(f"Unknown optimization method: {optimization_method}")
            
            # Create optimization result
            result = PortfolioOptimization(
                strategies=strategies,
                weights=dict(zip(strategies, weights))
            )
            
            # Calculate portfolio metrics
            result = self._calculate_portfolio_metrics(
                result, returns_df, mean_returns, cov_matrix
            )
            
            # Calculate contribution analysis
            result = self._calculate_contribution_analysis(
                result, returns_df, cov_matrix
            )
            
            # Generate efficient frontier
            result.efficient_frontier = self._generate_efficient_frontier(
                mean_returns, cov_matrix, min_weight, max_weight
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error optimizing portfolio: {e}")
            self.error_handler.handle_error(e)
            return PortfolioOptimization(strategies, {})
    
    def calculate_optimal_allocation(
        self,
        strategies: List[str],
        target_risk: float = TARGET_VOLATILITY,
        rebalance_frequency: str = 'monthly'
    ) -> pd.DataFrame:
        """
        Calculate optimal allocation with periodic rebalancing.
        
        Args:
            strategies: List of strategies
            target_risk: Target portfolio volatility
            rebalance_frequency: 'daily', 'weekly', 'monthly'
            
        Returns:
            DataFrame with time series of optimal weights
        """
        try:
            # Get all trades to determine date range
            all_trades = self.trade_repository.get_trades()
            if not all_trades:
                return pd.DataFrame()
            
            start_date = min(t.entry_time.date() for t in all_trades)
            end_date = max(t.exit_time.date() for t in all_trades)
            
            # Create rebalancing dates
            if rebalance_frequency == 'daily':
                freq = 'D'
            elif rebalance_frequency == 'weekly':
                freq = 'W'
            elif rebalance_frequency == 'monthly':
                freq = 'M'
            else:
                freq = 'M'
            
            rebalance_dates = pd.date_range(
                start=start_date, end=end_date, freq=freq
            )
            
            # Calculate optimal weights for each period
            allocations = []
            
            for i in range(1, len(rebalance_dates)):
                period_start = rebalance_dates[i-1].date()
                period_end = rebalance_dates[i].date()
                
                # Optimize for this period
                optimization = self.optimize_portfolio(
                    strategies,
                    optimization_method='sharpe',
                    constraints={'target_volatility': target_risk},
                    start_date=period_start,
                    end_date=period_end
                )
                
                # Store allocation
                allocation = {
                    'date': period_end,
                    **optimization.weights
                }
                allocations.append(allocation)
            
            return pd.DataFrame(allocations).set_index('date')
            
        except Exception as e:
            self.logger.error(f"Error calculating optimal allocation: {e}")
            return pd.DataFrame()
    
    # ==========================================================================
    # PUBLIC METHODS - RANKING AND SCORING
    # ==========================================================================
    
    def rank_strategies(
        self,
        strategies: List[str],
        metrics: Optional[List[str]] = None,
        weights: Optional[Dict[str, float]] = None,
        start_date: Optional[datetime.date] = None,
        end_date: Optional[datetime.date] = None
    ) -> Dict[str, StrategyRanking]:
        """
        Rank strategies by multiple metrics.
        
        Args:
            strategies: List of strategies to rank
            metrics: Metrics to use for ranking
            weights: Weights for composite scoring
            start_date: Start date
            end_date: End date
            
        Returns:
            Dictionary of rankings by metric
        """
        try:
            if metrics is None:
                metrics = COMPARISON_METRICS
            
            rankings = {}
            
            # Get performance data for all strategies
            performance_data = {}
            for strategy in strategies:
                perf = self.performance_analytics.calculate_performance(
                    strategy, start_date, end_date
                )
                if perf:
                    performance_data[strategy] = perf
            
            # Rank by each metric
            for metric in metrics:
                ranking = StrategyRanking(metric=metric, rankings={})
                
                # Extract metric values
                metric_values = {}
                for strategy, perf in performance_data.items():
                    value = getattr(perf.metrics, metric, None)
                    if value is not None:
                        metric_values[strategy] = value
                
                # Sort and rank
                sorted_strategies = sorted(
                    metric_values.items(),
                    key=lambda x: x[1],
                    reverse=self._is_higher_better(metric)
                )
                
                ranking.rankings = {
                    strat: rank + 1
                    for rank, (strat, _) in enumerate(sorted_strategies)
                }
                
                # Calculate statistical significance
                ranking = self._calculate_ranking_significance(
                    ranking, metric_values, strategies
                )
                
                rankings[metric] = ranking
            
            # Calculate composite score if weights provided
            if weights:
                composite_ranking = self._calculate_composite_ranking(
                    rankings, weights, strategies
                )
                rankings['composite'] = composite_ranking
            
            return rankings
            
        except Exception as e:
            self.logger.error(f"Error ranking strategies: {e}")
            return {}
    
    def identify_best_combinations(
        self,
        strategies: List[str],
        combination_size: int = 2,
        metric: str = 'sharpe_ratio',
        top_n: int = 5
    ) -> List[Tuple[List[str], float]]:
        """
        Identify best strategy combinations.
        
        Args:
            strategies: List of strategies
            combination_size: Size of combinations
            metric: Metric to optimize
            top_n: Number of top combinations to return
            
        Returns:
            List of (strategies, score) tuples
        """
        try:
            combinations = []
            
            # Generate all combinations
            for combo in itertools.combinations(strategies, combination_size):
                # Optimize portfolio for this combination
                optimization = self.optimize_portfolio(
                    list(combo),
                    optimization_method='sharpe' if metric == 'sharpe_ratio' else 'min_variance'
                )
                
                # Get metric value
                if metric == 'sharpe_ratio':
                    score = optimization.expected_sharpe
                elif metric == 'return':
                    score = optimization.expected_return
                elif metric == 'volatility':
                    score = -optimization.expected_volatility  # Lower is better
                else:
                    score = 0
                
                combinations.append((list(combo), score))
            
            # Sort and return top N
            combinations.sort(key=lambda x: x[1], reverse=True)
            
            return combinations[:top_n]
            
        except Exception as e:
            self.logger.error(f"Error identifying best combinations: {e}")
            return []
    
    # ==========================================================================
    # PRIVATE METHODS - CORRELATION ANALYSIS
    # ==========================================================================
    
    def _calculate_correlations(
        self,
        comparison: StrategyComparison,
        aligned_returns: pd.DataFrame
    ) -> StrategyComparison:
        """Calculate correlation metrics"""
        if len(aligned_returns) < MIN_CORRELATION_PERIOD:
            return comparison
        
        # Overall correlation
        comparison.returns_correlation = aligned_returns.corr().iloc[0, 1]
        
        # Rolling correlation
        window = min(60, len(aligned_returns) // 3)  # 60 days or 1/3 of data
        rolling_corr = aligned_returns.iloc[:, 0].rolling(window).corr(
            aligned_returns.iloc[:, 1]
        )
        comparison.rolling_correlation = rolling_corr
        
        # Correlation stability (std of rolling correlation)
        comparison.correlation_stability = rolling_corr.std()
        
        # Correlation breakdown by return magnitude
        # Positive returns
        pos_mask = (aligned_returns.iloc[:, 0] > 0) & (aligned_returns.iloc[:, 1] > 0)
        if pos_mask.sum() > 10:
            comparison.correlation_breakdown['positive_returns'] = (
                aligned_returns[pos_mask].corr().iloc[0, 1]
            )
        
        # Negative returns
        neg_mask = (aligned_returns.iloc[:, 0] < 0) & (aligned_returns.iloc[:, 1] < 0)
        if neg_mask.sum() > 10:
            comparison.correlation_breakdown['negative_returns'] = (
                aligned_returns[neg_mask].corr().iloc[0, 1]
            )
        
        # Large moves (> 2 std)
        threshold = aligned_returns.std().mean() * 2
        large_mask = (
            (aligned_returns.iloc[:, 0].abs() > threshold) |
            (aligned_returns.iloc[:, 1].abs() > threshold)
        )
        if large_mask.sum() > 5:
            comparison.correlation_breakdown['large_moves'] = (
                aligned_returns[large_mask].corr().iloc[0, 1]
            )
        
        return comparison
    
    def _compare_performance_metrics(
        self,
        comparison: StrategyComparison,
        perf1: StrategyPerformance,
        perf2: StrategyPerformance
    ) -> StrategyComparison:
        """Compare performance metrics between strategies"""
        metrics1 = perf1.metrics
        metrics2 = perf2.metrics
        
        # Calculate differentials
        for metric in COMPARISON_METRICS:
            value1 = getattr(metrics1, metric, 0)
            value2 = getattr(metrics2, metric, 0)
            
            if value2 != 0:
                # Percentage difference
                comparison.performance_differential[metric] = (
                    (value1 - value2) / abs(value2)
                )
            else:
                comparison.performance_differential[metric] = float('inf') if value1 > 0 else 0
        
        return comparison
    
    def _calculate_statistical_significance(
        self,
        comparison: StrategyComparison,
        aligned_returns: pd.DataFrame
    ) -> StrategyComparison:
        """Calculate statistical significance of performance differences"""
        if len(aligned_returns) < MIN_TRADES_FOR_COMPARISON:
            return comparison
        
        returns1 = aligned_returns.iloc[:, 0]
        returns2 = aligned_returns.iloc[:, 1]
        
        # T-test for mean returns
        t_stat, p_value = stats.ttest_rel(returns1, returns2)
        comparison.statistical_significance['returns_ttest'] = p_value
        
        # Wilcoxon signed-rank test (non-parametric)
        if len(returns1) > 20:
            w_stat, p_value = stats.wilcoxon(returns1, returns2)
            comparison.statistical_significance['returns_wilcoxon'] = p_value
        
        # Test for variance differences
        f_stat, p_value = stats.levene(returns1, returns2)
        comparison.statistical_significance['variance_levene'] = p_value
        
        # Bootstrap confidence intervals for Sharpe ratio difference
        sharpe_diff_ci = self._bootstrap_sharpe_difference(returns1, returns2)
        comparison.statistical_significance['sharpe_diff_ci_lower'] = sharpe_diff_ci[0]
        comparison.statistical_significance['sharpe_diff_ci_upper'] = sharpe_diff_ci[1]
        
        return comparison
    
    def _analyze_diversification_benefit(
        self,
        comparison: StrategyComparison,
        aligned_returns: pd.DataFrame
    ) -> StrategyComparison:
        """Analyze diversification benefits of combining strategies"""
        if aligned_returns.empty:
            return comparison
        
        # Equal weight portfolio
        combined_returns = aligned_returns.mean(axis=1)
        
        # Individual Sharpe ratios
        sharpe1 = self._calculate_sharpe_ratio(aligned_returns.iloc[:, 0])
        sharpe2 = self._calculate_sharpe_ratio(aligned_returns.iloc[:, 1])
        
        # Combined Sharpe ratio
        combined_sharpe = self._calculate_sharpe_ratio(combined_returns)
        comparison.combined_sharpe = combined_sharpe
        
        # Diversification benefit (improvement in Sharpe)
        avg_individual_sharpe = (sharpe1 + sharpe2) / 2
        comparison.diversification_benefit = (
            (combined_sharpe - avg_individual_sharpe) / avg_individual_sharpe
            if avg_individual_sharpe != 0 else 0
        )
        
        return comparison
    
    def _analyze_regime_performance(
        self,
        comparison: StrategyComparison,
        aligned_returns: pd.DataFrame,
        start_date: Optional[datetime.date],
        end_date: Optional[datetime.date]
    ) -> StrategyComparison:
        """Analyze performance in different market regimes"""
        try:
            # Get market regimes (simplified - would use actual regime detection)
            regimes = self._identify_market_regimes(
                aligned_returns.index, start_date, end_date
            )
            
            # Calculate correlation by regime
            for regime in MARKET_REGIMES:
                regime_mask = regimes == regime
                if regime_mask.sum() > 20:  # Minimum data points
                    regime_returns = aligned_returns[regime_mask]
                    comparison.regime_correlation[regime] = (
                        regime_returns.corr().iloc[0, 1]
                    )
                    
                    # Performance in regime
                    comparison.regime_performance[regime] = {
                        comparison.strategy1: self._calculate_sharpe_ratio(
                            regime_returns.iloc[:, 0]
                        ),
                        comparison.strategy2: self._calculate_sharpe_ratio(
                            regime_returns.iloc[:, 1]
                        )
                    }
            
        except Exception as e:
            self.logger.error(f"Error in regime analysis: {e}")
        
        return comparison
    
    # ==========================================================================
    # PRIVATE METHODS - PORTFOLIO OPTIMIZATION
    # ==========================================================================
    
    def _optimize_sharpe_ratio(
        self,
        mean_returns: pd.Series,
        cov_matrix: pd.DataFrame,
        min_weight: float,
        max_weight: float
    ) -> np.ndarray:
        """Optimize portfolio for maximum Sharpe ratio"""
        n_assets = len(mean_returns)
        
        # Initial guess (equal weight)
        x0 = np.ones(n_assets) / n_assets
        
        # Objective function (negative Sharpe ratio)
        def neg_sharpe(weights):
            port_return = np.dot(weights, mean_returns)
            port_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
            sharpe = (port_return - RISK_FREE_RATE) / port_vol if port_vol > 0 else 0
            return -sharpe
        
        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}  # Sum to 1
        ]
        
        # Bounds
        bounds = tuple((min_weight, max_weight) for _ in range(n_assets))
        
        # Optimize
        result = optimize.minimize(
            neg_sharpe, x0, method='SLSQP',
            bounds=bounds, constraints=constraints
        )
        
        return result.x if result.success else x0
    
    def _optimize_min_variance(
        self,
        cov_matrix: pd.DataFrame,
        min_weight: float,
        max_weight: float
    ) -> np.ndarray:
        """Optimize portfolio for minimum variance"""
        n_assets = len(cov_matrix)
        
        # Initial guess
        x0 = np.ones(n_assets) / n_assets
        
        # Objective function (portfolio variance)
        def portfolio_variance(weights):
            return np.dot(weights.T, np.dot(cov_matrix, weights))
        
        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}
        ]
        
        # Bounds
        bounds = tuple((min_weight, max_weight) for _ in range(n_assets))
        
        # Optimize
        result = optimize.minimize(
            portfolio_variance, x0, method='SLSQP',
            bounds=bounds, constraints=constraints
        )
        
        return result.x if result.success else x0
    
    def _optimize_risk_parity(
        self,
        cov_matrix: pd.DataFrame,
        min_weight: float,
        max_weight: float
    ) -> np.ndarray:
        """Optimize portfolio for risk parity"""
        n_assets = len(cov_matrix)
        
        # Initial guess
        x0 = np.ones(n_assets) / n_assets
        
        # Risk parity objective
        def risk_parity_objective(weights):
            # Calculate risk contributions
            portfolio_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
            marginal_contrib = np.dot(cov_matrix, weights)
            contrib = weights * marginal_contrib / portfolio_vol
            
            # Minimize squared differences from equal contribution
            target_contrib = portfolio_vol / n_assets
            return np.sum((contrib - target_contrib) ** 2)
        
        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}
        ]
        
        # Bounds
        bounds = tuple((min_weight, max_weight) for _ in range(n_assets))
        
        # Optimize
        result = optimize.minimize(
            risk_parity_objective, x0, method='SLSQP',
            bounds=bounds, constraints=constraints
        )
        
        return result.x if result.success else x0
    
    def _calculate_portfolio_metrics(
        self,
        result: PortfolioOptimization,
        returns_df: pd.DataFrame,
        mean_returns: pd.Series,
        cov_matrix: pd.DataFrame
    ) -> PortfolioOptimization:
        """Calculate portfolio-level metrics"""
        weights = np.array(list(result.weights.values()))
        
        # Expected return and volatility
        result.expected_return = np.dot(weights, mean_returns)
        result.expected_volatility = np.sqrt(
            np.dot(weights.T, np.dot(cov_matrix, weights))
        )
        
        # Sharpe ratio
        result.expected_sharpe = (
            (result.expected_return - RISK_FREE_RATE) / result.expected_volatility
            if result.expected_volatility > 0 else 0
        )
        
        # Portfolio returns
        portfolio_returns = returns_df.dot(weights)
        
        # VaR and CVaR
        result.portfolio_var = np.percentile(portfolio_returns, 5) * np.sqrt(252)
        result.portfolio_cvar = (
            portfolio_returns[portfolio_returns <= np.percentile(portfolio_returns, 5)].mean()
            * np.sqrt(252)
        )
        
        # Maximum drawdown
        cumulative_returns = (1 + portfolio_returns).cumprod()
        running_max = cumulative_returns.expanding().max()
        drawdown = (cumulative_returns - running_max) / running_max
        result.max_drawdown = drawdown.min()
        
        return result
    
    def _calculate_contribution_analysis(
        self,
        result: PortfolioOptimization,
        returns_df: pd.DataFrame,
        cov_matrix: pd.DataFrame
    ) -> PortfolioOptimization:
        """Calculate return and risk contributions"""
        weights = np.array(list(result.weights.values()))
        strategies = result.strategies
        
        # Return contribution
        mean_returns = returns_df.mean() * 252
        for i, strategy in enumerate(strategies):
            result.return_contribution[strategy] = (
                weights[i] * mean_returns.iloc[i] / result.expected_return
                if result.expected_return != 0 else 0
            )
        
        # Risk contribution
        portfolio_vol = result.expected_volatility
        marginal_contrib = np.dot(cov_matrix, weights)
        
        for i, strategy in enumerate(strategies):
            result.risk_contribution[strategy] = (
                weights[i] * marginal_contrib[i] / (portfolio_vol ** 2)
                if portfolio_vol > 0 else 0
            )
        
        return result
    
    def _generate_efficient_frontier(
        self,
        mean_returns: pd.Series,
        cov_matrix: pd.DataFrame,
        min_weight: float,
        max_weight: float,
        n_portfolios: int = 50
    ) -> pd.DataFrame:
        """Generate efficient frontier"""
        # Target returns from min to max
        min_return = mean_returns.min()
        max_return = mean_returns.max()
        target_returns = np.linspace(min_return, max_return, n_portfolios)
        
        frontier_data = []
        
        for target_return in target_returns:
            # Optimize for minimum variance given target return
            n_assets = len(mean_returns)
            x0 = np.ones(n_assets) / n_assets
            
            # Constraints
            constraints = [
                {'type': 'eq', 'fun': lambda x: np.sum(x) - 1},
                {'type': 'eq', 'fun': lambda x: np.dot(x, mean_returns) - target_return}
            ]
            
            # Bounds
            bounds = tuple((min_weight, max_weight) for _ in range(n_assets))
            
            # Objective (variance)
            def variance(weights):
                return np.dot(weights.T, np.dot(cov_matrix, weights))
            
            # Optimize
            result = optimize.minimize(
                variance, x0, method='SLSQP',
                bounds=bounds, constraints=constraints
            )
            
            if result.success:
                vol = np.sqrt(result.fun)
                sharpe = (target_return - RISK_FREE_RATE) / vol if vol > 0 else 0
                
                frontier_data.append({
                    'return': target_return,
                    'volatility': vol,
                    'sharpe': sharpe
                })
        
        return pd.DataFrame(frontier_data)
    
    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    
    def _get_strategy_returns(
        self,
        strategy: str,
        start_date: Optional[datetime.date] = None,
        end_date: Optional[datetime.date] = None
    ) -> pd.Series:
        """Get daily returns for a strategy"""
        cache_key = f"{strategy}_{start_date}_{end_date}"
        
        if cache_key in self._returns_cache:
            return self._returns_cache[cache_key]
        
        # Get trades
        trades = self.trade_repository.get_trades(
            strategy=strategy,
            start_date=start_date,
            end_date=end_date
        )
        
        if not trades:
            return pd.Series()
        
        # Create daily P&L
        daily_pnl = defaultdict(float)
        
        for trade in trades:
            trade_date = trade.exit_time.date()
            daily_pnl[trade_date] += trade.profit
        
        # Convert to series
        dates = sorted(daily_pnl.keys())
        pnl_series = pd.Series(
            [daily_pnl[date] for date in dates],
            index=pd.DatetimeIndex(dates)
        )
        
        # Calculate returns (assuming fixed capital)
        capital = 100000  # Assumed capital
        returns = pnl_series / capital
        
        # Cache and return
        self._returns_cache[cache_key] = returns
        return returns
    
    def _calculate_sharpe_ratio(self, returns: pd.Series) -> float:
        """Calculate Sharpe ratio"""
        if len(returns) < 2:
            return 0.0
        
        excess_returns = returns - RISK_FREE_RATE / 252
        
        if returns.std() == 0:
            return 0.0
        
        return np.sqrt(252) * excess_returns.mean() / returns.std()
    
    def _bootstrap_sharpe_difference(
        self,
        returns1: pd.Series,
        returns2: pd.Series,
        n_bootstrap: int = 1000
    ) -> Tuple[float, float]:
        """Bootstrap confidence interval for Sharpe ratio difference"""
        sharpe_diffs = []
        
        n = len(returns1)
        
        for _ in range(n_bootstrap):
            # Resample with replacement
            idx = np.random.choice(n, n, replace=True)
            sample1 = returns1.iloc[idx]
            sample2 = returns2.iloc[idx]
            
            # Calculate Sharpe difference
            sharpe1 = self._calculate_sharpe_ratio(sample1)
            sharpe2 = self._calculate_sharpe_ratio(sample2)
            sharpe_diffs.append(sharpe1 - sharpe2)
        
        # Calculate confidence interval
        lower = np.percentile(sharpe_diffs, (1 - CONFIDENCE_INTERVAL) / 2 * 100)
        upper = np.percentile(sharpe_diffs, (1 + CONFIDENCE_INTERVAL) / 2 * 100)
        
        return (lower, upper)
    
    def _is_higher_better(self, metric: str) -> bool:
        """Check if higher values are better for a metric"""
        lower_better_metrics = ['max_drawdown', 'var_95', 'cvar_95']
        return metric not in lower_better_metrics
    
    def _calculate_ranking_significance(
        self,
        ranking: StrategyRanking,
        metric_values: Dict[str, float],
        strategies: List[str]
    ) -> StrategyRanking:
        """Calculate statistical significance of rankings"""
        n = len(strategies)
        
        # Create significance matrix
        sig_matrix = pd.DataFrame(
            index=strategies,
            columns=strategies,
            data=1.0  # Default: not significant
        )
        
        # Pairwise comparisons
        for i, strat1 in enumerate(strategies):
            for j, strat2 in enumerate(strategies):
                if i != j and strat1 in metric_values and strat2 in metric_values:
                    # Simple t-test approximation (would need actual returns for proper test)
                    diff = abs(metric_values[strat1] - metric_values[strat2])
                    # Rough significance based on difference magnitude
                    if diff > 0.1 * max(abs(metric_values[strat1]), abs(metric_values[strat2])):
                        sig_matrix.loc[strat1, strat2] = 0.05  # Significant
        
        ranking.significance_matrix = sig_matrix
        
        # Confidence intervals (simplified)
        for strategy in strategies:
            if strategy in metric_values:
                value = metric_values[strategy]
                # Rough CI based on value magnitude
                margin = 0.1 * abs(value)
                ranking.confidence_intervals[strategy] = (value - margin, value + margin)
        
        return ranking
    
    def _calculate_composite_ranking(
        self,
        rankings: Dict[str, StrategyRanking],
        weights: Dict[str, float],
        strategies: List[str]
    ) -> StrategyRanking:
        """Calculate composite ranking based on weighted metrics"""
        composite_scores = defaultdict(float)
        
        # Calculate weighted scores
        for metric, weight in weights.items():
            if metric in rankings:
                ranking = rankings[metric]
                # Convert rank to score (inverse)
                for strategy, rank in ranking.rankings.items():
                    score = 1.0 / rank  # Higher score for better rank
                    composite_scores[strategy] += weight * score
        
        # Convert to rankings
        sorted_strategies = sorted(
            composite_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        composite_ranking = StrategyRanking(
            metric='composite',
            rankings={
                strat: rank + 1
                for rank, (strat, _) in enumerate(sorted_strategies)
            }
        )
        
        return composite_ranking
    
    def _identify_market_regimes(
        self,
        dates: pd.DatetimeIndex,
        start_date: Optional[datetime.date],
        end_date: Optional[datetime.date]
    ) -> pd.Series:
        """Identify market regimes (simplified)"""
        # This is a simplified version - would use actual regime detection
        # For now, just create random regimes for demonstration
        regimes = pd.Series(
            index=dates,
            data=np.random.choice(MARKET_REGIMES, len(dates))
        )
        
        return regimes
    
    # ==========================================================================
    # VISUALIZATION METHODS
    # ==========================================================================
    
    def plot_correlation_matrix(
        self,
        strategies: List[str],
        save_path: Optional[str] = None
    ) -> None:
        """Plot strategy correlation matrix"""
        matrix = self.compare_all_strategies(strategies, metric='correlation')
        
        plt.figure(figsize=(10, 8))
        sns.heatmap(
            matrix,
            annot=True,
            cmap='RdBu_r',
            center=0,
            vmin=-1,
            vmax=1,
            square=True,
            linewidths=0.5,
            cbar_kws={'label': 'Correlation'}
        )
        
        plt.title('Strategy Correlation Matrix')
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path)
        else:
            plt.show()
    
    def plot_efficient_frontier(
        self,
        optimization_result: PortfolioOptimization,
        save_path: Optional[str] = None
    ) -> None:
        """Plot efficient frontier with optimal portfolio"""
        frontier = optimization_result.efficient_frontier
        
        if frontier.empty:
            self.logger.warning("No efficient frontier data to plot")
            return
        
        plt.figure(figsize=(10, 8))
        
        # Plot frontier
        plt.plot(
            frontier['volatility'] * 100,
            frontier['return'] * 100,
            'b-',
            linewidth=2,
            label='Efficient Frontier'
        )
        
        # Plot optimal portfolio
        plt.scatter(
            optimization_result.expected_volatility * 100,
            optimization_result.expected_return * 100,
            color='red',
            s=100,
            marker='*',
            label='Optimal Portfolio',
            zorder=5
        )
        
        # Plot individual strategies
        for strategy, weight in optimization_result.weights.items():
            if weight > 0:
                # Would need individual strategy returns/vol
                # For now, just annotate
                plt.annotate(
                    f"{strategy}: {weight:.1%}",
                    xy=(optimization_result.expected_volatility * 100,
                        optimization_result.expected_return * 100),
                    xytext=(10, 10),
                    textcoords='offset points',
                    fontsize=9,
                    alpha=0.7
                )
        
        plt.xlabel('Volatility (%)')
        plt.ylabel('Expected Return (%)')
        plt.title('Efficient Frontier')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path)
        else:
            plt.show()
    
    def plot_strategy_rankings(
        self,
        rankings: Dict[str, StrategyRanking],
        save_path: Optional[str] = None
    ) -> None:
        """Plot strategy rankings across metrics"""
        # Prepare data
        strategies = set()
        for ranking in rankings.values():
            strategies.update(ranking.rankings.keys())
        strategies = sorted(strategies)
        
        metrics = list(rankings.keys())
        
        # Create ranking matrix
        rank_matrix = pd.DataFrame(
            index=strategies,
            columns=metrics
        )
        
        for metric, ranking in rankings.items():
            for strategy, rank in ranking.rankings.items():
                rank_matrix.loc[strategy, metric] = rank
        
        # Plot heatmap
        plt.figure(figsize=(12, 8))
        sns.heatmap(
            rank_matrix.astype(float),
            annot=True,
            fmt='.0f',
            cmap='RdYlGn_r',
            cbar_kws={'label': 'Rank (1=Best)'}
        )
        
        plt.title('Strategy Rankings by Metric')
        plt.xlabel('Metric')
        plt.ylabel('Strategy')
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path)
        else:
            plt.show()
    
    def create_interactive_comparison(
        self,
        strategies: List[str],
        save_path: Optional[str] = None
    ) -> go.Figure:
        """Create interactive comparison dashboard"""
        # Get performance data
        performance_data = {}
        for strategy in strategies:
            perf = self.performance_analytics.calculate_performance(strategy)
            if perf:
                performance_data[strategy] = perf
        
        # Create subplots
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                'Risk-Return Scatter',
                'Performance Metrics',
                'Correlation Matrix',
                'Time-based Performance'
            ),
            specs=[
                [{'type': 'scatter'}, {'type': 'bar'}],
                [{'type': 'heatmap'}, {'type': 'scatter'}]
            ]
        )
        
        # Risk-Return scatter
        x_data = []
        y_data = []
        text_data = []
        
        for strategy, perf in performance_data.items():
            x_data.append(perf.metrics.max_drawdown * 100)
            y_data.append(perf.metrics.total_return * 100)
            text_data.append(strategy)
        
        fig.add_trace(
            go.Scatter(
                x=x_data,
                y=y_data,
                mode='markers+text',
                text=text_data,
                textposition='top center',
                marker=dict(size=10)
            ),
            row=1, col=1
        )
        
        # Performance metrics bar chart
        metrics = ['sharpe_ratio', 'win_rate', 'profit_factor']
        for i, strategy in enumerate(strategies):
            if strategy in performance_data:
                perf = performance_data[strategy]
                values = [
                    getattr(perf.metrics, metric, 0)
                    for metric in metrics
                ]
                
                fig.add_trace(
                    go.Bar(
                        name=strategy,
                        x=metrics,
                        y=values
                    ),
                    row=1, col=2
                )
        
        # Correlation matrix
        corr_matrix = self.compare_all_strategies(strategies, metric='correlation')
        
        fig.add_trace(
            go.Heatmap(
                z=corr_matrix.values,
                x=corr_matrix.columns,
                y=corr_matrix.index,
                colorscale='RdBu',
                zmid=0
            ),
            row=2, col=1
        )
        
        # Update layout
        fig.update_layout(
            title='Strategy Comparison Dashboard',
            height=800,
            showlegend=True
        )
        
        # Update axes
        fig.update_xaxes(title_text='Max Drawdown (%)', row=1, col=1)
        fig.update_yaxes(title_text='Total Return (%)', row=1, col=1)
        
        if save_path:
            fig.write_html(save_path)
        else:
            fig.show()
        
        return fig

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_strategy_comparison_analyzer(
    performance_analytics: PerformanceAnalytics,
    trade_repository: TradeRepository
) -> StrategyComparisonAnalyzer:
    """
    Factory function to create StrategyComparisonAnalyzer instance.
    
    Args:
        performance_analytics: Performance analytics instance
        trade_repository: Trade repository instance
        
    Returns:
        StrategyComparisonAnalyzer instance
    """
    return StrategyComparisonAnalyzer(performance_analytics, trade_repository)

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Example usage
    from SpyderH_Storage.SpyderH02_TradeRepository import get_trade_repository
    from SpyderH_Storage.SpyderH07_PerformanceAnalytics import create_performance_analytics
    
    # Initialize components
    repo = get_trade_repository()
    perf_analytics = create_performance_analytics(repo)
    
    # Create comparison analyzer
    analyzer = create_strategy_comparison_analyzer(perf_analytics, repo)
    
    # Example: Compare two strategies
    comparison = analyzer.compare_strategies('IronCondor', 'CreditSpread')
    
    print(f"Correlation: {comparison.returns_correlation:.3f}")
    print(f"Diversification Benefit: {comparison.diversification_benefit:.1%}")
    
    # Example: Optimize portfolio
    strategies = ['IronCondor', 'CreditSpread', 'ZeroDTE']
    optimization = analyzer.optimize_portfolio(strategies)
    
    print("\nOptimal Weights:")
    for strategy, weight in optimization.weights.items():
        print(f"  {strategy}: {weight:.1%}")
    
    print(f"\nExpected Sharpe: {optimization.expected_sharpe:.2f}")
