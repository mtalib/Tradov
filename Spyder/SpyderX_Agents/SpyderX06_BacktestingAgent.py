#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderX_Agents
Module: SpyderX06_BacktestingAgent.py
Purpose: SPYDER - Automated SPY Options Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    SPYDER - Automated SPY Options Trading System

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import json
import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict, deque
from copy import deepcopy
import warnings

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import hashlib

warnings.filterwarnings('ignore')

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import differential_evolution

# Ollama integration
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    print("Warning: ollama package not installed. Install with: pip install ollama")
    OLLAMA_AVAILABLE = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
# Note: In standalone mode, we're not importing from other Spyder modules
# In production, these would be imported from the Spyder ecosystem

# ==============================================================================
# CONSTANTS
# ==============================================================================
# LLM Configuration
DEFAULT_LLM_MODEL = "llama3.2:3b-instruct-q4_K_M"
DEFAULT_TEMPERATURE = 0.3
MAX_TOKENS = 2000

# Backtesting Configuration
MIN_SAMPLE_SIZE = 252  # 1 year of trading days
CONFIDENCE_THRESHOLD = 0.95
MAX_CONCURRENT_TESTS = 5
WALK_FORWARD_PERIODS = 12
OUT_OF_SAMPLE_RATIO = 0.3

# Performance Thresholds
MIN_SHARPE_RATIO = 0.5
MAX_DRAWDOWN_LIMIT = 0.20
MIN_WIN_RATE = 0.45

# ==============================================================================
# LOGGING SETUP
# ==============================================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==============================================================================
# ENUMS
# ==============================================================================
class BacktestType(Enum):
    """Types of backtests"""
    SIMPLE = "simple"
    WALK_FORWARD = "walk_forward"
    MONTE_CARLO = "monte_carlo"
    STRESS_TEST = "stress_test"
    PARAMETER_SCAN = "parameter_scan"
    REGIME_BASED = "regime_based"
    BOOTSTRAP = "bootstrap"

class OptimizationObjective(Enum):
    """Optimization objectives"""
    SHARPE_RATIO = "sharpe_ratio"
    TOTAL_RETURN = "total_return"
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    CALMAR_RATIO = "calmar_ratio"
    SORTINO_RATIO = "sortino_ratio"
    MIN_DRAWDOWN = "min_drawdown"

class MarketRegime(Enum):
    """Market regimes for analysis"""
    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"
    HIGH_VOL = "high_vol"
    LOW_VOL = "low_vol"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class StrategyConfig:
    """Strategy configuration for backtesting"""
    name: str
    parameters: Dict[str, Any]
    entry_rules: Dict[str, Any]
    exit_rules: Dict[str, Any]
    position_sizing: Dict[str, Any]
    risk_limits: Dict[str, float]

@dataclass
class BacktestData:
    """Data for backtesting"""
    symbol: str
    timeframe: str
    start_date: datetime
    end_date: datetime
    price_data: pd.DataFrame
    options_data: Optional[pd.DataFrame] = None
    market_data: Optional[Dict[str, pd.DataFrame]] = None

@dataclass
class Trade:
    """Individual trade record"""
    entry_time: datetime
    exit_time: Optional[datetime]
    symbol: str
    quantity: int
    entry_price: float
    exit_price: Optional[float]
    pnl: Optional[float]
    return_pct: Optional[float]
    strategy: str
    signals: Dict[str, Any]

@dataclass
class BacktestResults:
    """Comprehensive backtest results"""
    test_id: str
    strategy_config: StrategyConfig
    test_type: BacktestType
    period: Tuple[datetime, datetime]
    trades: List[Trade]
    metrics: Dict[str, float]
    equity_curve: pd.Series
    drawdown_series: pd.Series
    regime_performance: Dict[MarketRegime, Dict[str, float]]
    parameter_sensitivity: Optional[Dict[str, Any]]
    statistical_significance: Dict[str, float]

@dataclass
class BacktestHypothesis:
    """Hypothesis for testing"""
    description: str
    test_parameters: Dict[str, Any]
    expected_outcome: str
    confidence_level: float

@dataclass
class OptimizationResult:
    """Parameter optimization result"""
    optimal_parameters: Dict[str, Any]
    objective_value: float
    parameter_history: List[Dict[str, Any]]
    convergence_plot: Optional[Any]
    robustness_score: float

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class SpyderX06_BacktestingAgent:
    """
    AI-Enhanced Backtesting Agent.
    
    This agent provides intelligent backtesting and strategy validation by
    generating hypotheses, designing tests, optimizing parameters, and
    providing deep insights into strategy performance using Ollama.
    
    Attributes:
        logger: Module logger instance
        config: Agent configuration
        ollama_client: Ollama LLM client
        test_history: History of backtests performed
        optimization_cache: Cache of optimization results
        
    Example:
        >>> agent = SpyderX06_BacktestingAgent()
        >>> results = await agent.backtest_strategy(strategy_config, data)
        >>> insights = await agent.analyze_results(results)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Backtesting Agent.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.logger = logger
        
        # LLM configuration
        self.model_name = self.config.get('llm_model', DEFAULT_LLM_MODEL)
        self.temperature = self.config.get('temperature', DEFAULT_TEMPERATURE)
        self.confidence_threshold = self.config.get('confidence_threshold', CONFIDENCE_THRESHOLD)
        
        # Initialize Ollama client
        self.ollama_client = None
        if OLLAMA_AVAILABLE:
            try:
                # Test if Ollama is running
                ollama.list()
                self.ollama_client = ollama
                self.logger.info(f"Ollama initialized with model: {self.model_name}")
            except Exception as e:
                self.logger.error(f"Failed to connect to Ollama: {e}")
                self.logger.info("Agent will work with reduced AI capabilities")
        
        # Test management
        self.active_tests: Dict[str, asyncio.Task] = {}
        self.test_history: List[BacktestResults] = []
        self.hypothesis_queue: deque = deque(maxlen=100)
        
        # Optimization tracking
        self.optimization_cache: Dict[str, OptimizationResult] = {}
        self.parameter_importance_history: defaultdict = defaultdict(list)
        
        # Performance tracking
        self.strategy_performance: Dict[str, List[float]] = defaultdict(list)
        self.regime_performance: Dict[str, Dict[MarketRegime, float]] = defaultdict(dict)
        
        # Statistical tests
        self.statistical_tests = {
            'sharpe': self._test_sharpe_significance,
            'returns': self._test_return_significance,
            'consistency': self._test_consistency,
            'regime_stability': self._test_regime_stability
        }
        
        self.logger.info(f"{self.__class__.__name__} initialized")
    
    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================
    async def backtest_strategy(
        self,
        strategy_config: StrategyConfig,
        data: BacktestData,
        test_type: BacktestType = BacktestType.SIMPLE,
        hypothesis: Optional[BacktestHypothesis] = None
    ) -> BacktestResults:
        """
        Run backtest for a strategy.
        
        Args:
            strategy_config: Strategy configuration
            data: Historical data for testing
            test_type: Type of backtest to run
            hypothesis: Optional hypothesis to test
            
        Returns:
            Comprehensive backtest results
        """
        start_time = datetime.now()
        test_id = self._generate_test_id(strategy_config.name, test_type)
        
        self.logger.info(f"Starting {test_type.value} backtest: {test_id}")
        
        # Validate data
        if not self._validate_data(data):
            raise ValueError("Invalid backtest data")
        
        # Run appropriate backtest type
        if test_type == BacktestType.SIMPLE:
            results = await self._run_simple_backtest(strategy_config, data)
        elif test_type == BacktestType.WALK_FORWARD:
            results = await self._run_walk_forward_test(strategy_config, data)
        elif test_type == BacktestType.MONTE_CARLO:
            results = await self._run_monte_carlo_test(strategy_config, data)
        elif test_type == BacktestType.PARAMETER_SCAN:
            results = await self._run_parameter_scan(strategy_config, data)
        else:
            results = await self._run_simple_backtest(strategy_config, data)
        
        # Add test metadata
        results.test_id = test_id
        results.test_type = test_type
        
        # Calculate additional metrics
        results.metrics.update(self._calculate_advanced_metrics(results))
        
        # Analyze by market regime
        results.regime_performance = self._analyze_regime_performance(results, data)
        
        # Statistical significance testing
        results.statistical_significance = self._test_statistical_significance(results)
        
        # Get AI insights if available
        if self.ollama_client and hypothesis:
            ai_insights = await self._get_ai_hypothesis_evaluation(
                hypothesis,
                results
            )
            results.metrics['ai_confidence'] = ai_insights.get('confidence', 0.5)
        
        # Store results
        self.test_history.append(results)
        self._update_performance_tracking(strategy_config.name, results)
        
        # Log performance
        elapsed = (datetime.now() - start_time).total_seconds()
        self.logger.info(
            f"Backtest {test_id} completed in {elapsed:.2f} seconds. "
            f"Sharpe: {results.metrics.get('sharpe_ratio', 0):.2f}"
        )
        
        return results
    
    async def generate_test_hypotheses(
        self,
        strategy_type: str,
        market_conditions: Dict[str, Any],
        historical_performance: Optional[Dict[str, Any]] = None
    ) -> List[BacktestHypothesis]:
        """
        Generate test hypotheses using AI.
        
        Args:
            strategy_type: Type of strategy
            market_conditions: Current market conditions
            historical_performance: Optional past performance data
            
        Returns:
            List of hypotheses to test
        """
        if self.ollama_client:
            hypotheses = await self._get_ai_test_hypotheses(
                strategy_type,
                market_conditions,
                historical_performance
            )
        else:
            hypotheses = self._get_default_hypotheses(strategy_type)
        
        # Add to queue
        self.hypothesis_queue.extend(hypotheses)
        
        return hypotheses
    
    async def optimize_parameters(
        self,
        strategy_config: StrategyConfig,
        data: BacktestData,
        objective: OptimizationObjective = OptimizationObjective.SHARPE_RATIO,
        constraints: Optional[Dict[str, Any]] = None
    ) -> OptimizationResult:
        """
        Optimize strategy parameters.
        
        Args:
            strategy_config: Base strategy configuration
            data: Historical data
            objective: Optimization objective
            constraints: Parameter constraints
            
        Returns:
            Optimization results with optimal parameters
        """
        self.logger.info(f"Starting parameter optimization for {strategy_config.name}")
        
        # Check cache
        cache_key = self._get_optimization_cache_key(
            strategy_config,
            data,
            objective
        )
        if cache_key in self.optimization_cache:
            self.logger.info("Using cached optimization results")
            return self.optimization_cache[cache_key]
        
        # Define parameter bounds
        bounds = self._get_parameter_bounds(strategy_config, constraints)
        
        # Objective function
        async def objective_function(params):
            # Update strategy config with new parameters
            test_config = deepcopy(strategy_config)
            test_config.parameters.update(
                dict(zip(bounds.keys(), params))
            )
            
            # Run backtest
            results = await self._run_simple_backtest(test_config, data)
            
            # Return objective value (negative for minimization)
            return -self._get_objective_value(results, objective)
        
        # Run optimization
        if self.ollama_client:
            # Get AI guidance on parameter ranges
            ai_guidance = await self._get_ai_optimization_guidance(
                strategy_config,
                objective,
                bounds
            )
            bounds = self._update_bounds_with_ai_guidance(bounds, ai_guidance)
        
        # Differential evolution optimization
        result = differential_evolution(
            lambda x: asyncio.run(objective_function(x)),
            list(bounds.values()),
            maxiter=50,
            popsize=15,
            disp=True
        )
        
        # Create optimization result
        optimal_params = dict(zip(bounds.keys(), result.x))
        
        optimization_result = OptimizationResult(
            optimal_parameters=optimal_params,
            objective_value=-result.fun,
            parameter_history=[],  # Simplified
            convergence_plot=None,
            robustness_score=self._calculate_robustness_score(
                optimal_params,
                strategy_config,
                data
            )
        )
        
        # Cache results
        self.optimization_cache[cache_key] = optimization_result
        
        return optimization_result
    
    async def analyze_results(
        self,
        results: BacktestResults,
        deep_analysis: bool = True
    ) -> Dict[str, Any]:
        """
        Analyze backtest results with AI insights.
        
        Args:
            results: Backtest results to analyze
            deep_analysis: Whether to perform deep analysis
            
        Returns:
            Analysis insights and recommendations
        """
        analysis = {
            'summary': self._generate_summary(results),
            'strengths': [],
            'weaknesses': [],
            'recommendations': [],
            'risk_factors': []
        }
        
        # Basic analysis
        analysis['strengths'], analysis['weaknesses'] = self._identify_strengths_weaknesses(results)
        analysis['risk_factors'] = self._identify_risk_factors(results)
        
        # Deep analysis if requested
        if deep_analysis:
            # Pattern analysis
            trade_patterns = self._analyze_trade_patterns(results.trades)
            analysis['trade_patterns'] = trade_patterns
            
            # Regime analysis
            regime_insights = self._analyze_regime_dependencies(results)
            analysis['regime_insights'] = regime_insights
        
        # Get AI insights if available
        if self.ollama_client:
            ai_analysis = await self._get_ai_results_analysis(results, analysis)
            analysis['ai_insights'] = ai_analysis.get('insights', [])
            analysis['recommendations'].extend(ai_analysis.get('recommendations', []))
            analysis['hidden_risks'] = ai_analysis.get('hidden_risks', [])
        else:
            # Basic recommendations
            analysis['recommendations'] = self._get_basic_recommendations(results)
        
        return analysis
    
    async def compare_strategies(
        self,
        strategy_results: List[BacktestResults],
        comparison_criteria: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Compare multiple strategy backtest results.
        
        Args:
            strategy_results: List of backtest results to compare
            comparison_criteria: Optional specific criteria to compare
            
        Returns:
            Comparison analysis and rankings
        """
        if not strategy_results:
            return {"error": "No strategies to compare"}
        
        # Default criteria
        if not comparison_criteria:
            comparison_criteria = [
                'sharpe_ratio', 'total_return', 'max_drawdown',
                'win_rate', 'profit_factor', 'consistency'
            ]
        
        # Build comparison matrix
        comparison_matrix = {}
        for criterion in comparison_criteria:
            comparison_matrix[criterion] = {}
            for result in strategy_results:
                strategy_name = result.strategy_config.name
                value = result.metrics.get(criterion, 0)
                comparison_matrix[criterion][strategy_name] = value
        
        # Rank strategies
        rankings = self._rank_strategies(comparison_matrix)
        
        # Statistical comparison
        statistical_comparison = self._statistical_comparison(strategy_results)
        
        # Get AI insights if available
        if self.ollama_client:
            ai_comparison = await self._get_ai_strategy_comparison(
                strategy_results,
                comparison_matrix
            )
            insights = ai_comparison.get('insights', [])
            best_strategy = ai_comparison.get('best_strategy')
        else:
            insights = []
            best_strategy = rankings[0][0] if rankings else None
        
        return {
            'comparison_matrix': comparison_matrix,
            'rankings': rankings,
            'statistical_comparison': statistical_comparison,
            'best_strategy': best_strategy,
            'insights': insights
        }
    
    # ==========================================================================
    # PRIVATE METHODS - BACKTESTING
    # ==========================================================================
    async def _run_simple_backtest(
        self,
        strategy_config: StrategyConfig,
        data: BacktestData
    ) -> BacktestResults:
        """Run simple backtest."""
        trades = []
        equity = [10000.0]  # Starting capital
        
        # Simplified backtest logic
        price_data = data.price_data
        position = None
        
        for i in range(1, len(price_data)):
            current_price = price_data.iloc[i]['close']
            
            # Entry logic (simplified)
            if position is None and self._check_entry_signal(
                strategy_config.entry_rules,
                price_data.iloc[i],
                i
            ):
                position = Trade(
                    entry_time=price_data.index[i],
                    exit_time=None,
                    symbol=data.symbol,
                    quantity=100,
                    entry_price=current_price,
                    exit_price=None,
                    pnl=None,
                    return_pct=None,
                    strategy=strategy_config.name,
                    signals={'entry_signal': True}
                )
            
            # Exit logic (simplified)
            elif position is not None and self._check_exit_signal(
                strategy_config.exit_rules,
                price_data.iloc[i],
                position,
                i
            ):
                position.exit_time = price_data.index[i]
                position.exit_price = current_price
                position.pnl = (position.exit_price - position.entry_price) * position.quantity
                position.return_pct = position.pnl / (position.entry_price * position.quantity)
                
                trades.append(position)
                equity.append(equity[-1] + position.pnl)
                position = None
            else:
                equity.append(equity[-1])
        
        # Close any open position
        if position is not None:
            position.exit_time = price_data.index[-1]
            position.exit_price = price_data.iloc[-1]['close']
            position.pnl = (position.exit_price - position.entry_price) * position.quantity
            position.return_pct = position.pnl / (position.entry_price * position.quantity)
            trades.append(position)
            equity.append(equity[-1] + position.pnl)
        
        # Create equity curve
        equity_curve = pd.Series(equity, index=price_data.index)
        
        # Calculate drawdown
        drawdown_series = self._calculate_drawdown_series(equity_curve)
        
        # Calculate metrics
        metrics = self._calculate_metrics(trades, equity_curve)
        
        return BacktestResults(
            test_id="",
            strategy_config=strategy_config,
            test_type=BacktestType.SIMPLE,
            period=(data.start_date, data.end_date),
            trades=trades,
            metrics=metrics,
            equity_curve=equity_curve,
            drawdown_series=drawdown_series,
            regime_performance={},
            parameter_sensitivity=None,
            statistical_significance={}
        )
    
    async def _run_walk_forward_test(
        self,
        strategy_config: StrategyConfig,
        data: BacktestData
    ) -> BacktestResults:
        """Run walk-forward analysis."""
        # Divide data into periods
        total_days = (data.end_date - data.start_date).days
        period_days = total_days // WALK_FORWARD_PERIODS
        
        all_trades = []
        combined_equity = []
        
        for period in range(WALK_FORWARD_PERIODS):
            # Define in-sample and out-of-sample periods
            period_start = data.start_date + timedelta(days=period * period_days)
            in_sample_end = period_start + timedelta(days=int(period_days * (1 - OUT_OF_SAMPLE_RATIO)))
            out_sample_end = period_start + timedelta(days=period_days)
            
            # Create data subsets
            in_sample_data = BacktestData(
                symbol=data.symbol,
                timeframe=data.timeframe,
                start_date=period_start,
                end_date=in_sample_end,
                price_data=data.price_data[period_start:in_sample_end],
                options_data=data.options_data[period_start:in_sample_end] if data.options_data is not None else None
            )
            
            out_sample_data = BacktestData(
                symbol=data.symbol,
                timeframe=data.timeframe,
                start_date=in_sample_end,
                end_date=out_sample_end,
                price_data=data.price_data[in_sample_end:out_sample_end],
                options_data=data.options_data[in_sample_end:out_sample_end] if data.options_data is not None else None
            )
            
            # Optimize on in-sample
            optimization = await self.optimize_parameters(
                strategy_config,
                in_sample_data,
                OptimizationObjective.SHARPE_RATIO
            )
            
            # Test on out-of-sample
            optimized_config = deepcopy(strategy_config)
            optimized_config.parameters.update(optimization.optimal_parameters)
            
            period_results = await self._run_simple_backtest(
                optimized_config,
                out_sample_data
            )
            
            all_trades.extend(period_results.trades)
            combined_equity.extend(period_results.equity_curve.values)
        
        # Combine results
        if combined_equity:
            equity_curve = pd.Series(combined_equity)
            drawdown_series = self._calculate_drawdown_series(equity_curve)
            metrics = self._calculate_metrics(all_trades, equity_curve)
        else:
            equity_curve = pd.Series([10000])
            drawdown_series = pd.Series([0])
            metrics = {}
        
        return BacktestResults(
            test_id="",
            strategy_config=strategy_config,
            test_type=BacktestType.WALK_FORWARD,
            period=(data.start_date, data.end_date),
            trades=all_trades,
            metrics=metrics,
            equity_curve=equity_curve,
            drawdown_series=drawdown_series,
            regime_performance={},
            parameter_sensitivity=None,
            statistical_significance={}
        )
    
    async def _run_monte_carlo_test(
        self,
        strategy_config: StrategyConfig,
        data: BacktestData,
        num_simulations: int = 1000
    ) -> BacktestResults:
        """Run Monte Carlo simulation."""
        # First get base results
        base_results = await self._run_simple_backtest(strategy_config, data)
        
        if not base_results.trades:
            return base_results
        
        # Extract returns
        returns = [trade.return_pct for trade in base_results.trades if trade.return_pct is not None]
        
        # Run Monte Carlo simulations
        simulation_results = []
        
        for _ in range(num_simulations):
            # Randomly sample returns with replacement
            simulated_returns = np.random.choice(returns, size=len(returns), replace=True)
            
            # Calculate equity curve
            equity = 10000
            equity_values = [equity]
            
            for ret in simulated_returns:
                equity *= (1 + ret)
                equity_values.append(equity)
            
            # Calculate metrics for simulation
            final_return = (equity - 10000) / 10000
            simulation_results.append(final_return)
        
        # Calculate confidence intervals
        confidence_intervals = {
            '5%': np.percentile(simulation_results, 5),
            '25%': np.percentile(simulation_results, 25),
            '50%': np.percentile(simulation_results, 50),
            '75%': np.percentile(simulation_results, 75),
            '95%': np.percentile(simulation_results, 95)
        }
        
        # Update base results with Monte Carlo analysis
        base_results.metrics['monte_carlo_confidence_intervals'] = confidence_intervals
        base_results.metrics['monte_carlo_expected_return'] = np.mean(simulation_results)
        base_results.metrics['monte_carlo_return_std'] = np.std(simulation_results)
        
        return base_results
    
    async def _run_parameter_scan(
        self,
        strategy_config: StrategyConfig,
        data: BacktestData
    ) -> BacktestResults:
        """Run parameter scan test."""
        # Define parameter grid (simplified)
        param_grid = self._create_parameter_grid(strategy_config)
        
        best_results = None
        best_sharpe = -np.inf
        sensitivity_results = []
        
        for params in param_grid:
            # Update config with test parameters
            test_config = deepcopy(strategy_config)
            test_config.parameters.update(params)
            
            # Run backtest
            results = await self._run_simple_backtest(test_config, data)
            
            # Track sensitivity
            sensitivity_results.append({
                'parameters': params,
                'sharpe_ratio': results.metrics.get('sharpe_ratio', 0),
                'total_return': results.metrics.get('total_return', 0),
                'max_drawdown': results.metrics.get('max_drawdown', 0)
            })
            
            # Keep best results
            if results.metrics.get('sharpe_ratio', 0) > best_sharpe:
                best_sharpe = results.metrics.get('sharpe_ratio', 0)
                best_results = results
        
        if best_results:
            best_results.parameter_sensitivity = {
                'scan_results': sensitivity_results,
                'best_parameters': best_results.strategy_config.parameters
            }
        
        return best_results or BacktestResults(
            test_id="",
            strategy_config=strategy_config,
            test_type=BacktestType.PARAMETER_SCAN,
            period=(data.start_date, data.end_date),
            trades=[],
            metrics={},
            equity_curve=pd.Series([10000]),
            drawdown_series=pd.Series([0]),
            regime_performance={},
            parameter_sensitivity={'scan_results': sensitivity_results},
            statistical_significance={}
        )
    
    # ==========================================================================
    # PRIVATE METHODS - SIGNAL GENERATION
    # ==========================================================================
    def _check_entry_signal(
        self,
        entry_rules: Dict[str, Any],
        current_data: pd.Series,
        index: int
    ) -> bool:
        """Check if entry conditions are met."""
        # Simplified entry logic
        # In production, would implement actual strategy rules
        if 'rsi_oversold' in entry_rules:
            # Mock RSI check
            return np.random.random() < 0.05  # 5% chance
        return np.random.random() < 0.02  # 2% chance
    
    def _check_exit_signal(
        self,
        exit_rules: Dict[str, Any],
        current_data: pd.Series,
        position: Trade,
        index: int
    ) -> bool:
        """Check if exit conditions are met."""
        # Simplified exit logic
        if 'profit_target' in exit_rules:
            current_pnl = (current_data['close'] - position.entry_price) * position.quantity
            if current_pnl >= exit_rules['profit_target']:
                return True
        
        if 'stop_loss' in exit_rules:
            current_pnl = (current_data['close'] - position.entry_price) * position.quantity
            if current_pnl <= -exit_rules['stop_loss']:
                return True
        
        # Time-based exit
        return np.random.random() < 0.1  # 10% chance
    
    # ==========================================================================
    # PRIVATE METHODS - METRICS CALCULATION
    # ==========================================================================
    def _calculate_metrics(
        self,
        trades: List[Trade],
        equity_curve: pd.Series
    ) -> Dict[str, float]:
        """Calculate performance metrics."""
        if not trades:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'sharpe_ratio': 0,
                'max_drawdown': 0,
                'total_return': 0
            }
        
        # Basic metrics
        winning_trades = [t for t in trades if t.pnl and t.pnl > 0]
        losing_trades = [t for t in trades if t.pnl and t.pnl < 0]
        
        metrics = {
            'total_trades': len(trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': len(winning_trades) / len(trades) if trades else 0,
        }
        
        # Profit factor
        gross_profits = sum(t.pnl for t in winning_trades)
        gross_losses = abs(sum(t.pnl for t in losing_trades))
        metrics['profit_factor'] = gross_profits / gross_losses if gross_losses > 0 else np.inf
        
        # Returns
        metrics['total_return'] = (equity_curve.iloc[-1] - equity_curve.iloc[0]) / equity_curve.iloc[0]
        
        # Sharpe ratio
        returns = equity_curve.pct_change().dropna()
        if len(returns) > 1:
            metrics['sharpe_ratio'] = (returns.mean() / returns.std()) * np.sqrt(252)
        else:
            metrics['sharpe_ratio'] = 0
        
        # Max drawdown
        drawdowns = self._calculate_drawdown_series(equity_curve)
        metrics['max_drawdown'] = drawdowns.min()
        
        # Average trade metrics
        if trades:
            metrics['avg_win'] = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
            metrics['avg_loss'] = np.mean([t.pnl for t in losing_trades]) if losing_trades else 0
            metrics['avg_trade'] = np.mean([t.pnl for t in trades if t.pnl is not None])
        
        return metrics
    
    def _calculate_advanced_metrics(self, results: BacktestResults) -> Dict[str, float]:
        """Calculate advanced performance metrics."""
        metrics = {}
        
        # Calmar ratio
        if results.metrics['max_drawdown'] != 0:
            metrics['calmar_ratio'] = results.metrics['total_return'] / abs(results.metrics['max_drawdown'])
        else:
            metrics['calmar_ratio'] = 0
        
        # Sortino ratio
        returns = results.equity_curve.pct_change().dropna()
        downside_returns = returns[returns < 0]
        if len(downside_returns) > 0:
            downside_std = downside_returns.std()
            metrics['sortino_ratio'] = (returns.mean() / downside_std) * np.sqrt(252) if downside_std > 0 else 0
        else:
            metrics['sortino_ratio'] = results.metrics.get('sharpe_ratio', 0)
        
        # Consistency
        if results.trades:
            monthly_returns = self._calculate_monthly_returns(results)
            positive_months = sum(1 for r in monthly_returns if r > 0)
            metrics['consistency'] = positive_months / len(monthly_returns) if monthly_returns else 0
        else:
            metrics['consistency'] = 0
        
        return metrics
    
    def _calculate_drawdown_series(self, equity_curve: pd.Series) -> pd.Series:
        """Calculate drawdown series."""
        cummax = equity_curve.cummax()
        drawdown = (equity_curve - cummax) / cummax
        return drawdown
    
    def _calculate_monthly_returns(self, results: BacktestResults) -> List[float]:
        """Calculate monthly returns from results."""
        # Group by month
        monthly_equity = results.equity_curve.resample('M').last()
        monthly_returns = monthly_equity.pct_change().dropna().tolist()
        return monthly_returns
    
    # ==========================================================================
    # PRIVATE METHODS - REGIME ANALYSIS
    # ==========================================================================
    def _analyze_regime_performance(
        self,
        results: BacktestResults,
        data: BacktestData
    ) -> Dict[MarketRegime, Dict[str, float]]:
        """Analyze performance by market regime."""
        regime_performance = {}
        
        # Identify regimes (simplified)
        regimes = self._identify_market_regimes(data.price_data)
        
        # Group trades by regime
        for regime in MarketRegime:
            regime_trades = []
            
            for trade in results.trades:
                if trade.entry_time in regimes.index:
                    trade_regime = regimes.loc[trade.entry_time]
                    if trade_regime == regime:
                        regime_trades.append(trade)
            
            if regime_trades:
                # Calculate metrics for regime
                regime_metrics = {
                    'total_trades': len(regime_trades),
                    'win_rate': sum(1 for t in regime_trades if t.pnl and t.pnl > 0) / len(regime_trades),
                    'avg_return': np.mean([t.return_pct for t in regime_trades if t.return_pct is not None])
                }
                regime_performance[regime] = regime_metrics
        
        return regime_performance
    
    def _identify_market_regimes(self, price_data: pd.DataFrame) -> pd.Series:
        """Identify market regimes from price data."""
        # Simplified regime identification
        # In production, would use more sophisticated methods
        
        # Calculate rolling metrics
        returns = price_data['close'].pct_change()
        volatility = returns.rolling(20).std()
        trend = price_data['close'].rolling(50).mean()
        
        regimes = []
        
        for i in range(len(price_data)):
            if i < 50:
                regimes.append(MarketRegime.SIDEWAYS)
                continue
            
            current_price = price_data.iloc[i]['close']
            current_trend = trend.iloc[i]
            current_vol = volatility.iloc[i] if i < len(volatility) else 0
            
            # Determine regime
            if current_vol > volatility.quantile(0.8):
                regime = MarketRegime.HIGH_VOL
            elif current_vol < volatility.quantile(0.2):
                regime = MarketRegime.LOW_VOL
            elif current_price > current_trend * 1.02:
                regime = MarketRegime.BULL
            elif current_price < current_trend * 0.98:
                regime = MarketRegime.BEAR
            else:
                regime = MarketRegime.SIDEWAYS
            
            regimes.append(regime)
        
        return pd.Series(regimes, index=price_data.index)
    
    # ==========================================================================
    # PRIVATE METHODS - STATISTICAL TESTING
    # ==========================================================================
    def _test_statistical_significance(
        self,
        results: BacktestResults
    ) -> Dict[str, float]:
        """Test statistical significance of results."""
        significance = {}
        
        # Test if returns are significantly different from zero
        if results.trades:
            returns = [t.return_pct for t in results.trades if t.return_pct is not None]
            if len(returns) > 30:
                t_stat, p_value = stats.ttest_1samp(returns, 0)
                significance['returns_t_stat'] = t_stat
                significance['returns_p_value'] = p_value
                significance['returns_significant'] = p_value < 0.05
        
        # Test Sharpe ratio significance
        sharpe_significance = self._test_sharpe_significance(results)
        significance.update(sharpe_significance)
        
        return significance
    
    def _test_sharpe_significance(self, results: BacktestResults) -> Dict[str, float]:
        """Test if Sharpe ratio is statistically significant."""
        sharpe = results.metrics.get('sharpe_ratio', 0)
        n_trades = len(results.trades)
        
        if n_trades > 0:
            # Standard error of Sharpe ratio
            se_sharpe = np.sqrt((1 + 0.5 * sharpe**2) / n_trades)
            
            # Z-score
            z_score = sharpe / se_sharpe
            
            # P-value (two-tailed)
            p_value = 2 * (1 - stats.norm.cdf(abs(z_score)))
            
            return {
                'sharpe_se': se_sharpe,
                'sharpe_z_score': z_score,
                'sharpe_p_value': p_value,
                'sharpe_significant': p_value < 0.05
            }
        
        return {}
    
    def _test_return_significance(self, results: BacktestResults) -> Dict[str, float]:
        """Test return significance."""
        # Implemented above in _test_statistical_significance
        return {}
    
    def _test_consistency(self, results: BacktestResults) -> Dict[str, float]:
        """Test strategy consistency."""
        monthly_returns = self._calculate_monthly_returns(results)
        
        if len(monthly_returns) > 12:
            # Test if monthly returns are consistently positive
            positive_months = sum(1 for r in monthly_returns if r > 0)
            total_months = len(monthly_returns)
            
            # Binomial test
            p_value = stats.binom_test(positive_months, total_months, 0.5)
            
            return {
                'consistency_ratio': positive_months / total_months,
                'consistency_p_value': p_value,
                'consistently_profitable': p_value < 0.05 and positive_months > total_months / 2
            }
        
        return {}
    
    def _test_regime_stability(self, results: BacktestResults) -> Dict[str, float]:
        """Test if performance is stable across regimes."""
        if not results.regime_performance:
            return {}
        
        # Extract win rates by regime
        win_rates = [
            metrics.get('win_rate', 0) 
            for metrics in results.regime_performance.values()
        ]
        
        if len(win_rates) > 2:
            # Chi-square test for homogeneity
            chi2_stat, p_value = stats.chisquare(win_rates)
            
            return {
                'regime_chi2': chi2_stat,
                'regime_p_value': p_value,
                'regime_stable': p_value > 0.05  # Want no significant difference
            }
        
        return {}
    
    # ==========================================================================
    # PRIVATE METHODS - ANALYSIS
    # ==========================================================================
    def _generate_summary(self, results: BacktestResults) -> str:
        """Generate summary of backtest results."""
        summary = (
            f"Strategy: {results.strategy_config.name}\n"
            f"Period: {results.period[0].strftime('%Y-%m-%d')} to {results.period[1].strftime('%Y-%m-%d')}\n"
            f"Total Trades: {results.metrics.get('total_trades', 0)}\n"
            f"Win Rate: {results.metrics.get('win_rate', 0):.1%}\n"
            f"Sharpe Ratio: {results.metrics.get('sharpe_ratio', 0):.2f}\n"
            f"Total Return: {results.metrics.get('total_return', 0):.1%}\n"
            f"Max Drawdown: {results.metrics.get('max_drawdown', 0):.1%}"
        )
        return summary
    
    def _identify_strengths_weaknesses(
        self,
        results: BacktestResults
    ) -> Tuple[List[str], List[str]]:
        """Identify strategy strengths and weaknesses."""
        strengths = []
        weaknesses = []
        
        # Analyze metrics
        if results.metrics.get('sharpe_ratio', 0) > 1.5:
            strengths.append("Excellent risk-adjusted returns")
        elif results.metrics.get('sharpe_ratio', 0) < 0.5:
            weaknesses.append("Poor risk-adjusted returns")
        
        if results.metrics.get('win_rate', 0) > 0.6:
            strengths.append("High win rate")
        elif results.metrics.get('win_rate', 0) < 0.4:
            weaknesses.append("Low win rate")
        
        if abs(results.metrics.get('max_drawdown', 0)) < 0.1:
            strengths.append("Low drawdown")
        elif abs(results.metrics.get('max_drawdown', 0)) > 0.25:
            weaknesses.append("High drawdown risk")
        
        if results.metrics.get('consistency', 0) > 0.7:
            strengths.append("Consistent performance")
        elif results.metrics.get('consistency', 0) < 0.5:
            weaknesses.append("Inconsistent performance")
        
        return strengths, weaknesses
    
    def _identify_risk_factors(self, results: BacktestResults) -> List[str]:
        """Identify risk factors in strategy."""
        risk_factors = []
        
        # Concentration risk
        if results.regime_performance:
            regime_variance = np.var([
                metrics.get('win_rate', 0) 
                for metrics in results.regime_performance.values()
            ])
            if regime_variance > 0.1:
                risk_factors.append("High regime dependency")
        
        # Drawdown risk
        if abs(results.metrics.get('max_drawdown', 0)) > 0.2:
            risk_factors.append("Significant drawdown risk")
        
        # Statistical significance
        if results.statistical_significance.get('returns_p_value', 1) > 0.1:
            risk_factors.append("Results may not be statistically significant")
        
        return risk_factors
    
    def _analyze_trade_patterns(self, trades: List[Trade]) -> Dict[str, Any]:
        """Analyze patterns in trades."""
        if not trades:
            return {}
        
        patterns = {}
        
        # Win/loss streaks
        streaks = self._calculate_streaks(trades)
        patterns['max_winning_streak'] = streaks['max_win']
        patterns['max_losing_streak'] = streaks['max_loss']
        
        # Time-based patterns
        trade_hours = [t.entry_time.hour for t in trades if t.entry_time]
        if trade_hours:
            patterns['most_active_hour'] = max(set(trade_hours), key=trade_hours.count)
        
        # Hold time analysis
        hold_times = []
        for trade in trades:
            if trade.exit_time and trade.entry_time:
                hold_time = (trade.exit_time - trade.entry_time).total_seconds() / 3600
                hold_times.append(hold_time)
        
        if hold_times:
            patterns['avg_hold_time_hours'] = np.mean(hold_times)
            patterns['max_hold_time_hours'] = max(hold_times)
        
        return patterns
    
    def _calculate_streaks(self, trades: List[Trade]) -> Dict[str, int]:
        """Calculate winning and losing streaks."""
        max_win_streak = 0
        max_loss_streak = 0
        current_win_streak = 0
        current_loss_streak = 0
        
        for trade in trades:
            if trade.pnl and trade.pnl > 0:
                current_win_streak += 1
                current_loss_streak = 0
                max_win_streak = max(max_win_streak, current_win_streak)
            elif trade.pnl and trade.pnl < 0:
                current_loss_streak += 1
                current_win_streak = 0
                max_loss_streak = max(max_loss_streak, current_loss_streak)
        
        return {
            'max_win': max_win_streak,
            'max_loss': max_loss_streak
        }
    
    def _analyze_regime_dependencies(
        self,
        results: BacktestResults
    ) -> List[str]:
        """Analyze regime dependencies."""
        insights = []
        
        if not results.regime_performance:
            return insights
        
        # Find best and worst regimes
        best_regime = None
        worst_regime = None
        best_win_rate = 0
        worst_win_rate = 1
        
        for regime, metrics in results.regime_performance.items():
            win_rate = metrics.get('win_rate', 0)
            if win_rate > best_win_rate:
                best_win_rate = win_rate
                best_regime = regime
            if win_rate < worst_win_rate:
                worst_win_rate = win_rate
                worst_regime = regime
        
        if best_regime:
            insights.append(f"Best performance in {best_regime.value} market (win rate: {best_win_rate:.1%})")
        if worst_regime:
            insights.append(f"Worst performance in {worst_regime.value} market (win rate: {worst_win_rate:.1%})")
        
        return insights
    
    def _get_basic_recommendations(self, results: BacktestResults) -> List[str]:
        """Get basic recommendations without AI."""
        recommendations = []
        
        # Based on metrics
        if results.metrics.get('sharpe_ratio', 0) < 0.5:
            recommendations.append("Consider improving entry/exit logic for better risk-adjusted returns")
        
        if results.metrics.get('win_rate', 0) < 0.45:
            recommendations.append("Focus on improving trade selection criteria")
        
        if abs(results.metrics.get('max_drawdown', 0)) > 0.2:
            recommendations.append("Implement stricter risk management to reduce drawdowns")
        
        if results.metrics.get('profit_factor', 0) < 1.5:
            recommendations.append("Optimize position sizing or improve win/loss ratio")
        
        return recommendations
    
    # ==========================================================================
    # PRIVATE METHODS - AI INTEGRATION
    # ==========================================================================
    async def _get_ai_hypothesis_evaluation(
        self,
        hypothesis: BacktestHypothesis,
        results: BacktestResults
    ) -> Dict[str, Any]:
        """Get AI evaluation of hypothesis test."""
        try:
            results_summary = self._generate_summary(results)
            
            prompt = f"""Evaluate this trading hypothesis test:

Hypothesis: {hypothesis.description}
Expected Outcome: {hypothesis.expected_outcome}
Confidence Level: {hypothesis.confidence_level:.1%}

Test Results:
{results_summary}

Statistical Significance:
- Returns p-value: {results.statistical_significance.get('returns_p_value', 'N/A')}
- Sharpe p-value: {results.statistical_significance.get('sharpe_p_value', 'N/A')}

Was the hypothesis confirmed? Provide confidence score (0-1) and explanation."""

            response = await asyncio.to_thread(
                self.ollama_client.generate,
                model=self.model_name,
                prompt=prompt,
                options={
                    'temperature': self.temperature,
                    'num_predict': MAX_TOKENS
                }
            )
            
            # Parse response
            text = response['response']
            
            # Extract confidence (look for number between 0 and 1)
            import re
            confidence_match = re.search(r'confidence[:\s]+([0-9.]+)', text.lower())
            confidence = float(confidence_match.group(1)) if confidence_match else 0.5
            
            return {
                'confidence': confidence,
                'evaluation': text
            }
            
        except Exception as e:
            self.logger.error(f"Error getting AI hypothesis evaluation: {e}")
            return {'confidence': 0.5, 'evaluation': 'Unable to evaluate'}
    
    async def _get_ai_test_hypotheses(
        self,
        strategy_type: str,
        market_conditions: Dict[str, Any],
        historical_performance: Optional[Dict[str, Any]] = None
    ) -> List[BacktestHypothesis]:
        """Get AI-generated test hypotheses."""
        try:
            perf_str = ""
            if historical_performance:
                perf_str = f"\nHistorical Performance: Sharpe={historical_performance.get('sharpe_ratio', 0):.2f}, Win Rate={historical_performance.get('win_rate', 0):.1%}"
            
            market_str = "\n".join([f"- {k}: {v}" for k, v in market_conditions.items()])
            
            prompt = f"""Generate testable hypotheses for options trading strategy backtesting:

Strategy Type: {strategy_type}
Market Conditions:
{market_str}
{perf_str}

Generate 3-5 specific, testable hypotheses about how to improve this strategy.
Focus on parameter adjustments, entry/exit rules, or market regime filters.

Format each hypothesis as:
"If we [specific change], then [expected outcome] because [reasoning]"
"""

            response = await asyncio.to_thread(
                self.ollama_client.generate,
                model=self.model_name,
                prompt=prompt,
                options={
                    'temperature': self.temperature,
                    'num_predict': MAX_TOKENS
                }
            )
            
            # Parse hypotheses
            hypotheses = []
            text = response['response']
            
            # Simple parsing - look for "If we" patterns
            import re
            hypothesis_matches = re.findall(r'If we (.+?), then (.+?)(?:because|\.)', text, re.IGNORECASE)
            
            for i, (change, outcome) in enumerate(hypothesis_matches[:5]):
                hypotheses.append(BacktestHypothesis(
                    description=f"If we {change}, then {outcome}",
                    test_parameters={'hypothesis_id': i},
                    expected_outcome=outcome,
                    confidence_level=0.7
                ))
            
            return hypotheses or self._get_default_hypotheses(strategy_type)
            
        except Exception as e:
            self.logger.error(f"Error getting AI test hypotheses: {e}")
            return self._get_default_hypotheses(strategy_type)
    
    def _get_default_hypotheses(self, strategy_type: str) -> List[BacktestHypothesis]:
        """Get default hypotheses."""
        return [
            BacktestHypothesis(
                description="If we tighten stop losses to 2%, then drawdowns will decrease",
                test_parameters={'stop_loss': 0.02},
                expected_outcome="Lower maximum drawdown",
                confidence_level=0.8
            ),
            BacktestHypothesis(
                description="If we filter trades by market regime, then win rate will improve",
                test_parameters={'regime_filter': True},
                expected_outcome="Higher win rate in trending markets",
                confidence_level=0.7
            ),
            BacktestHypothesis(
                description="If we increase position size in high confidence setups, then returns will improve",
                test_parameters={'dynamic_sizing': True},
                expected_outcome="Better risk-adjusted returns",
                confidence_level=0.6
            )
        ]
    
    async def _get_ai_optimization_guidance(
        self,
        strategy_config: StrategyConfig,
        objective: OptimizationObjective,
        bounds: Dict[str, Tuple[float, float]]
    ) -> Dict[str, Any]:
        """Get AI guidance for parameter optimization."""
        try:
            bounds_str = "\n".join([f"- {k}: [{v[0]}, {v[1]}]" for k, v in bounds.items()])
            
            prompt = f"""Guide parameter optimization for options trading strategy:

Strategy: {strategy_config.name}
Objective: Optimize {objective.value}
Current Parameters: {strategy_config.parameters}

Parameter Bounds:
{bounds_str}

Suggest which parameters are most important to optimize and recommended ranges.
Consider market conditions and typical options trading best practices."""

            response = await asyncio.to_thread(
                self.ollama_client.generate,
                model=self.model_name,
                prompt=prompt,
                options={
                    'temperature': self.temperature,
                    'num_predict': MAX_TOKENS
                }
            )
            
            # Extract guidance (simplified)
            return {
                'guidance': response['response'],
                'focus_parameters': list(bounds.keys())[:3]  # Top 3 parameters
            }
            
        except Exception as e:
            self.logger.error(f"Error getting AI optimization guidance: {e}")
            return {}
    
    async def _get_ai_results_analysis(
        self,
        results: BacktestResults,
        basic_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get AI analysis of backtest results."""
        try:
            summary = self._generate_summary(results)
            strengths_str = "\n".join([f"- {s}" for s in basic_analysis['strengths']])
            weaknesses_str = "\n".join([f"- {w}" for w in basic_analysis['weaknesses']])
            
            prompt = f"""Analyze these options trading backtest results:

{summary}

Strengths:
{strengths_str}

Weaknesses:
{weaknesses_str}

Win/Loss Pattern: Max Win Streak={basic_analysis.get('trade_patterns', {}).get('max_winning_streak', 0)}, Max Loss Streak={basic_analysis.get('trade_patterns', {}).get('max_losing_streak', 0)}

Provide:
1. Hidden insights not obvious from metrics
2. Specific recommendations to improve performance
3. Potential risks or biases in the strategy

Be specific and actionable."""

            response = await asyncio.to_thread(
                self.ollama_client.generate,
                model=self.model_name,
                prompt=prompt,
                options={
                    'temperature': self.temperature,
                    'num_predict': MAX_TOKENS
                }
            )
            
            # Parse response
            text = response['response']
            
            # Extract sections (simplified parsing)
            insights = []
            recommendations = []
            hidden_risks = []
            
            lines = text.split('\n')
            current_section = None
            
            for line in lines:
                line = line.strip()
                if 'insight' in line.lower() or 'hidden' in line.lower():
                    current_section = 'insights'
                elif 'recommend' in line.lower():
                    current_section = 'recommendations'
                elif 'risk' in line.lower() or 'bias' in line.lower():
                    current_section = 'risks'
                elif line and current_section:
                    if line.startswith(('-', '•', '*')) or line[0].isdigit():
                        clean_line = line.lstrip('-•*0123456789. ').strip()
                        if current_section == 'insights':
                            insights.append(clean_line)
                        elif current_section == 'recommendations':
                            recommendations.append(clean_line)
                        elif current_section == 'risks':
                            hidden_risks.append(clean_line)
            
            return {
                'insights': insights[:5],
                'recommendations': recommendations[:5],
                'hidden_risks': hidden_risks[:3]
            }
            
        except Exception as e:
            self.logger.error(f"Error getting AI results analysis: {e}")
            return {
                'insights': [],
                'recommendations': basic_analysis.get('recommendations', []),
                'hidden_risks': []
            }
    
    async def _get_ai_strategy_comparison(
        self,
        strategy_results: List[BacktestResults],
        comparison_matrix: Dict[str, Dict[str, float]]
    ) -> Dict[str, Any]:
        """Get AI comparison of strategies."""
        try:
            # Build comparison string
            comparison_str = ""
            for strategy in strategy_results[:5]:  # Limit to 5 strategies
                name = strategy.strategy_config.name
                comparison_str += f"\n{name}:"
                comparison_str += f"\n- Sharpe: {strategy.metrics.get('sharpe_ratio', 0):.2f}"
                comparison_str += f"\n- Win Rate: {strategy.metrics.get('win_rate', 0):.1%}"
                comparison_str += f"\n- Max DD: {strategy.metrics.get('max_drawdown', 0):.1%}"
                comparison_str += f"\n- Total Return: {strategy.metrics.get('total_return', 0):.1%}"
            
            prompt = f"""Compare these options trading strategies:
{comparison_str}

Which strategy is best overall and why? Consider:
1. Risk-adjusted returns
2. Consistency
3. Drawdown management
4. Practical implementation

Provide insights about when each strategy might be preferred."""

            response = await asyncio.to_thread(
                self.ollama_client.generate,
                model=self.model_name,
                prompt=prompt,
                options={
                    'temperature': self.temperature,
                    'num_predict': MAX_TOKENS
                }
            )
            
            # Extract best strategy (simplified)
            text = response['response']
            best_strategy = None
            
            for strategy in strategy_results:
                if strategy.strategy_config.name.lower() in text.lower():
                    best_strategy = strategy.strategy_config.name
                    break
            
            return {
                'best_strategy': best_strategy,
                'insights': [text[:500]]  # First 500 chars as insight
            }
            
        except Exception as e:
            self.logger.error(f"Error getting AI strategy comparison: {e}")
            return {}
    
    # ==========================================================================
    # PRIVATE METHODS - UTILITIES
    # ==========================================================================
    def _generate_test_id(self, strategy_name: str, test_type: BacktestType) -> str:
        """Generate unique test ID."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"{strategy_name}_{test_type.value}_{timestamp}"
    
    def _validate_data(self, data: BacktestData) -> bool:
        """Validate backtest data."""
        if data.price_data.empty:
            return False
        
        if len(data.price_data) < MIN_SAMPLE_SIZE:
            self.logger.warning(f"Data size ({len(data.price_data)}) below minimum ({MIN_SAMPLE_SIZE})")
        
        required_columns = ['open', 'high', 'low', 'close']
        if not all(col in data.price_data.columns for col in required_columns):
            return False
        
        return True
    
    def _get_optimization_cache_key(
        self,
        strategy_config: StrategyConfig,
        data: BacktestData,
        objective: OptimizationObjective
    ) -> str:
        """Generate cache key for optimization."""
        key_parts = [
            strategy_config.name,
            str(data.start_date),
            str(data.end_date),
            objective.value
        ]
        key_string = "_".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _get_parameter_bounds(
        self,
        strategy_config: StrategyConfig,
        constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Tuple[float, float]]:
        """Get parameter bounds for optimization."""
        bounds = {}
        
        # Default bounds based on parameter names
        for param, value in strategy_config.parameters.items():
            if isinstance(value, (int, float)):
                if 'stop' in param.lower() or 'loss' in param.lower():
                    bounds[param] = (0.005, 0.05)  # 0.5% to 5%
                elif 'target' in param.lower() or 'profit' in param.lower():
                    bounds[param] = (0.01, 0.1)  # 1% to 10%
                elif 'size' in param.lower():
                    bounds[param] = (1, 10)  # 1 to 10 contracts
                else:
                    # Generic bounds around current value
                    bounds[param] = (value * 0.5, value * 1.5)
        
        # Apply constraints if provided
        if constraints:
            for param, constraint in constraints.items():
                if param in bounds:
                    bounds[param] = constraint
        
        return bounds
    
    def _update_bounds_with_ai_guidance(
        self,
        bounds: Dict[str, Tuple[float, float]],
        ai_guidance: Dict[str, Any]
    ) -> Dict[str, Tuple[float, float]]:
        """Update bounds based on AI guidance."""
        # Focus on parameters AI suggests
        focus_params = ai_guidance.get('focus_parameters', [])
        
        # Tighten bounds for non-focus parameters
        for param in bounds:
            if param not in focus_params:
                current_min, current_max = bounds[param]
                center = (current_min + current_max) / 2
                range_reduction = 0.7  # Reduce range by 30%
                new_range = (current_max - current_min) * range_reduction
                bounds[param] = (
                    center - new_range / 2,
                    center + new_range / 2
                )
        
        return bounds
    
    def _get_objective_value(
        self,
        results: BacktestResults,
        objective: OptimizationObjective
    ) -> float:
        """Get objective value from results."""
        if objective == OptimizationObjective.SHARPE_RATIO:
            return results.metrics.get('sharpe_ratio', 0)
        elif objective == OptimizationObjective.TOTAL_RETURN:
            return results.metrics.get('total_return', 0)
        elif objective == OptimizationObjective.WIN_RATE:
            return results.metrics.get('win_rate', 0)
        elif objective == OptimizationObjective.PROFIT_FACTOR:
            return results.metrics.get('profit_factor', 0)
        elif objective == OptimizationObjective.CALMAR_RATIO:
            return results.metrics.get('calmar_ratio', 0)
        elif objective == OptimizationObjective.SORTINO_RATIO:
            return results.metrics.get('sortino_ratio', 0)
        elif objective == OptimizationObjective.MIN_DRAWDOWN:
            return -abs(results.metrics.get('max_drawdown', 0))
        else:
            return 0
    
    def _calculate_robustness_score(
        self,
        optimal_params: Dict[str, Any],
        base_config: StrategyConfig,
        data: BacktestData
    ) -> float:
        """Calculate robustness score for optimized parameters."""
        # Simplified robustness calculation
        # In production, would test parameter stability
        
        # Check if parameters are at bounds (less robust)
        at_bounds_penalty = 0
        for param, value in optimal_params.items():
            if param in base_config.parameters:
                base_value = base_config.parameters[param]
                if abs(value - base_value) / base_value > 0.5:
                    at_bounds_penalty += 0.1
        
        robustness = max(0, 1 - at_bounds_penalty)
        return robustness
    
    def _create_parameter_grid(self, strategy_config: StrategyConfig) -> List[Dict[str, Any]]:
        """Create parameter grid for scanning."""
        # Simplified grid creation
        grid = []
        
        # Get numeric parameters
        numeric_params = {
            k: v for k, v in strategy_config.parameters.items()
            if isinstance(v, (int, float))
        }
        
        if not numeric_params:
            return [strategy_config.parameters]
        
        # Create 3x3 grid for first two parameters
        param_names = list(numeric_params.keys())[:2]
        
        for i in range(3):
            for j in range(3):
                params = strategy_config.parameters.copy()
                
                if len(param_names) > 0:
                    base_value = numeric_params[param_names[0]]
                    params[param_names[0]] = base_value * (0.8 + i * 0.2)
                
                if len(param_names) > 1:
                    base_value = numeric_params[param_names[1]]
                    params[param_names[1]] = base_value * (0.8 + j * 0.2)
                
                grid.append(params)
        
        return grid
    
    def _update_performance_tracking(
        self,
        strategy_name: str,
        results: BacktestResults
    ):
        """Update performance tracking for strategy."""
        # Track returns
        total_return = results.metrics.get('total_return', 0)
        self.strategy_performance[strategy_name].append(total_return)
        
        # Track regime performance
        for regime, metrics in results.regime_performance.items():
            if strategy_name not in self.regime_performance:
                self.regime_performance[strategy_name] = {}
            self.regime_performance[strategy_name][regime] = metrics.get('win_rate', 0)
    
    def _rank_strategies(
        self,
        comparison_matrix: Dict[str, Dict[str, float]]
    ) -> List[Tuple[str, float]]:
        """Rank strategies based on comparison matrix."""
        # Simple scoring based on normalized metrics
        scores = {}
        
        for strategy in list(list(comparison_matrix.values())[0].keys()):
            score = 0
            weights = {
                'sharpe_ratio': 0.3,
                'total_return': 0.2,
                'max_drawdown': 0.2,  # Lower is better
                'win_rate': 0.15,
                'profit_factor': 0.15
            }
            
            for metric, weight in weights.items():
                if metric in comparison_matrix:
                    values = list(comparison_matrix[metric].values())
                    if values:
                        value = comparison_matrix[metric].get(strategy, 0)
                        
                        # Normalize
                        min_val = min(values)
                        max_val = max(values)
                        if max_val != min_val:
                            if metric == 'max_drawdown':  # Lower is better
                                normalized = 1 - (value - min_val) / (max_val - min_val)
                            else:
                                normalized = (value - min_val) / (max_val - min_val)
                        else:
                            normalized = 0.5
                        
                        score += normalized * weight
            
            scores[strategy] = score
        
        # Sort by score
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
    def _statistical_comparison(
        self,
        strategy_results: List[BacktestResults]
    ) -> Dict[str, Any]:
        """Perform statistical comparison of strategies."""
        comparison = {}
        
        # Extract returns for each strategy
        strategy_returns = {}
        for result in strategy_results:
            returns = [t.return_pct for t in result.trades if t.return_pct is not None]
            if returns:
                strategy_returns[result.strategy_config.name] = returns
        
        if len(strategy_returns) >= 2:
            # Perform ANOVA or Kruskal-Wallis test
            if all(len(returns) > 30 for returns in strategy_returns.values()):
                # ANOVA for normal distributions
                f_stat, p_value = stats.f_oneway(*strategy_returns.values())
                comparison['test'] = 'ANOVA'
                comparison['f_statistic'] = f_stat
                comparison['p_value'] = p_value
            else:
                # Kruskal-Wallis for non-parametric
                h_stat, p_value = stats.kruskal(*strategy_returns.values())
                comparison['test'] = 'Kruskal-Wallis'
                comparison['h_statistic'] = h_stat
                comparison['p_value'] = p_value
            
            comparison['significantly_different'] = p_value < 0.05
        
        return comparison
    
    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def clear_cache(self):
        """Clear optimization cache."""
        self.optimization_cache.clear()
        self.logger.info("Optimization cache cleared")
    
    def get_test_history(
        self,
        strategy_name: Optional[str] = None,
        test_type: Optional[BacktestType] = None
    ) -> List[BacktestResults]:
        """Get filtered test history."""
        history = self.test_history
        
        if strategy_name:
            history = [
                r for r in history 
                if r.strategy_config.name == strategy_name
            ]
        
        if test_type:
            history = [
                r for r in history 
                if r.test_type == test_type
            ]
        
        return history

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_backtesting_agent(config: Optional[Dict[str, Any]] = None) -> SpyderX06_BacktestingAgent:
    """
    Factory function to create Backtesting Agent.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        Configured SpyderX06_BacktestingAgent instance
    """
    return SpyderX06_BacktestingAgent(config)

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# Module-level initialization code
_module_instance: Optional[SpyderX06_BacktestingAgent] = None

def get_module_instance(config: Optional[Dict[str, Any]] = None) -> SpyderX06_BacktestingAgent:
    """
    Get singleton instance of the module.
    
    Args:
        config: Configuration if creating new instance
        
    Returns:
        Module instance
    """
    global _module_instance
    if _module_instance is None:
        _module_instance = SpyderX06_BacktestingAgent(config)
    return _module_instance

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    async def test_agent():
        """Test the Backtesting Agent."""
        # Create agent
        config = {
            'llm_model': 'llama3.2:3b-instruct-q4_K_M',
            'temperature': 0.3,
            'confidence_threshold': 0.95
        }
        
        agent = create_backtesting_agent(config)
        
        # Create sample strategy
        strategy_config = StrategyConfig(
            name="MA_Crossover",
            parameters={
                'fast_ma': 20,
                'slow_ma': 50,
                'stop_loss': 0.02,
                'profit_target': 0.05
            },
            entry_rules={'ma_cross': True},
            exit_rules={'profit_target': 500, 'stop_loss': 200},
            position_sizing={'fixed': 100},
            risk_limits={'max_loss': 1000}
        )
        
        # Create sample data
        dates = pd.date_range(end=datetime.now(), periods=500, freq='D')
        prices = 100 + np.cumsum(np.random.randn(500) * 2)
        
        price_data = pd.DataFrame({
            'open': prices + np.random.randn(500) * 0.5,
            'high': prices + abs(np.random.randn(500)) * 1,
            'low': prices - abs(np.random.randn(500)) * 1,
            'close': prices,
            'volume': np.random.randint(1000000, 5000000, 500)
        }, index=dates)
        
        backtest_data = BacktestData(
            symbol="SPY",
            timeframe="1D",
            start_date=dates[0],
            end_date=dates[-1],
            price_data=price_data
        )
        
        # Test backtest
        print("="*80)
        print("TESTING BACKTESTING AGENT")
        print("="*80)
        
        # 1. Simple backtest
        print("\n1. Running Simple Backtest...")
        results = await agent.backtest_strategy(
            strategy_config,
            backtest_data,
            BacktestType.SIMPLE
        )
        
        print(f"Total Trades: {results.metrics.get('total_trades', 0)}")
        print(f"Win Rate: {results.metrics.get('win_rate', 0):.1%}")
        print(f"Sharpe Ratio: {results.metrics.get('sharpe_ratio', 0):.2f}")
        print(f"Total Return: {results.metrics.get('total_return', 0):.1%}")
        print(f"Max Drawdown: {results.metrics.get('max_drawdown', 0):.1%}")
        
        # 2. Generate hypotheses
        print("\n2. Generating Test Hypotheses...")
        hypotheses = await agent.generate_test_hypotheses(
            "MA_Crossover",
            {'volatility': 'medium', 'trend': 'bullish'},
            results.metrics
        )
        
        for i, hypothesis in enumerate(hypotheses[:3]):
            print(f"\nHypothesis {i+1}:")
            print(f"  {hypothesis.description}")
            print(f"  Confidence: {hypothesis.confidence_level:.1%}")
        
        # 3. Analyze results
        print("\n3. Analyzing Results...")
        analysis = await agent.analyze_results(results)
        
        print("\nStrengths:")
        for strength in analysis['strengths']:
            print(f"  ✓ {strength}")
        
        print("\nWeaknesses:")
        for weakness in analysis['weaknesses']:
            print(f"  ✗ {weakness}")
        
        print("\nRecommendations:")
        for rec in analysis['recommendations'][:3]:
            print(f"  • {rec}")
        
        # 4. Parameter optimization
        print("\n4. Optimizing Parameters...")
        optimization = await agent.optimize_parameters(
            strategy_config,
            backtest_data,
            OptimizationObjective.SHARPE_RATIO
        )
        
        print(f"\nOptimal Parameters:")
        for param, value in optimization.optimal_parameters.items():
            original = strategy_config.parameters.get(param, 0)
            print(f"  {param}: {original:.3f} → {value:.3f}")
        print(f"Objective Value: {optimization.objective_value:.3f}")
        print(f"Robustness Score: {optimization.robustness_score:.2f}")
    
    # Run test
    asyncio.run(test_agent())
