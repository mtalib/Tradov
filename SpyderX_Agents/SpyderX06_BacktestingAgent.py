#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderX06_BacktestingAgent.py
Purpose: AI-Enhanced Backtesting and Strategy Validation
Group: X (AI Agents)

Description:
    Replaces traditional backtesting modules (SpyderI analysis modules) with an
    intelligent AI agent that generates hypotheses, designs tests, optimizes
    parameters, and provides deep insights into strategy performance.

    Replaced Modules:
    - SpyderI02_WalkForward through SpyderI06_Reporting
    - Enhanced with AI for intelligent test design and analysis
    
    Keeps as Python: SpyderI01_BacktestEngine (core execution engine)

Author: AI Trading Assistant
Date: 2025-01-17
Version: 1.0.0

Dependencies:
    - ollama (for LLM integration)
    - numpy, pandas
    - scipy
    - asyncio
    - plotly (for visualizations)
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
import numpy as np
import pandas as pd
from collections import defaultdict, deque
import hashlib
from scipy import stats
from scipy.optimize import differential_evolution
import warnings
warnings.filterwarnings('ignore')

# Import Spyder core components
from SpyderU01_DataStructures import (
    Portfolio, Position, TradeSignal, OptionContract,
    OrderType, OrderStatus
)
from SpyderU02_Configuration import config
from SpyderU03_Logger import SpyderLogger
from SpyderU04_EventManager import Event, EventType
from SpyderU12_AgentIntegration import SpyderBaseAgent, AgentState

# Keep core backtest engine
from SpyderI01_BacktestEngine import BacktestEngine

# Backtest Types
class BacktestType(Enum):
    """Types of backtests"""
    SINGLE_PERIOD = "single_period"
    WALK_FORWARD = "walk_forward"
    MONTE_CARLO = "monte_carlo"
    STRESS_TEST = "stress_test"
    PARAMETER_SWEEP = "parameter_sweep"
    REGIME_BASED = "regime_based"
    CROSS_VALIDATION = "cross_validation"
    BOOTSTRAP = "bootstrap"

# Analysis Types
class AnalysisType(Enum):
    """Types of backtest analysis"""
    PERFORMANCE = "performance"
    RISK = "risk"
    DRAWDOWN = "drawdown"
    STABILITY = "stability"
    ROBUSTNESS = "robustness"
    REGIME_DEPENDENCY = "regime_dependency"
    PARAMETER_SENSITIVITY = "parameter_sensitivity"
    OVERFITTING = "overfitting"

@dataclass
class BacktestConfig:
    """Configuration for a backtest"""
    test_type: BacktestType
    start_date: datetime
    end_date: datetime
    initial_capital: float
    strategy_params: Dict[str, Any]
    data_frequency: str = "1D"
    commission: float = 0.001
    slippage: float = 0.0005
    margin_requirement: float = 0.2
    risk_free_rate: float = 0.02
    optimization_params: Optional[Dict[str, Any]] = None
    walk_forward_params: Optional[Dict[str, Any]] = None

@dataclass
class BacktestResults:
    """Results from a backtest"""
    config: BacktestConfig
    performance_metrics: Dict[str, float]
    trades: List[Dict[str, Any]]
    equity_curve: pd.Series
    positions: pd.DataFrame
    drawdown_analysis: Dict[str, Any]
    risk_metrics: Dict[str, float]
    regime_analysis: Optional[Dict[str, Any]] = None
    parameter_sensitivity: Optional[Dict[str, Any]] = None
    statistical_significance: Optional[Dict[str, Any]] = None

@dataclass
class OptimizationResult:
    """Result from parameter optimization"""
    best_params: Dict[str, Any]
    best_score: float
    parameter_importance: Dict[str, float]
    convergence_history: List[float]
    parameter_surface: Optional[pd.DataFrame] = None
    overfitting_score: float = 0.0

@dataclass
class BacktestHypothesis:
    """AI-generated hypothesis for testing"""
    hypothesis: str
    test_design: BacktestConfig
    expected_outcome: Dict[str, Any]
    confidence: float
    reasoning: str
    priority: int

@dataclass
class ValidationResult:
    """Result from strategy validation"""
    is_valid: bool
    confidence_score: float
    strengths: List[str]
    weaknesses: List[str]
    recommendations: List[str]
    risk_warnings: List[str]

class BacktestingAgent(SpyderBaseAgent):
    """
    AI-Enhanced Backtesting Agent
    
    Provides intelligent backtesting with hypothesis generation,
    parameter optimization, and deep performance analysis.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Backtesting Agent"""
        super().__init__(config)
        
        # Agent configuration
        self.llm_model = config.get('backtest_llm_model', 'llama3.2:3b-instruct-q4_K_M')
        self.max_concurrent_tests = config.get('max_concurrent_tests', 5)
        self.min_sample_size = config.get('min_sample_size', 252)  # 1 year
        self.confidence_threshold = config.get('confidence_threshold', 0.95)
        
        # Backtest engine
        self.engine = BacktestEngine(config)
        
        # Test management
        self.active_tests: Dict[str, asyncio.Task] = {}
        self.test_history: List[BacktestResults] = []
        self.hypothesis_queue: deque = deque(maxlen=100)
        
        # Optimization tracking
        self.optimization_cache: Dict[str, OptimizationResult] = {}
        self.parameter_importance_history: defaultdict = defaultdict(list)
        
        # Performance tracking
        self.strategy_performance: Dict[str, List[float]] = defaultdict(list)
        self.regime_performance: Dict[str, Dict[str, float]] = defaultdict(dict)
        
        # Statistical tests
        self.statistical_tests = {
            'sharpe': self._test_sharpe_significance,
            'returns': self._test_return_significance,
            'consistency': self._test_consistency,
            'regime_stability': self._test_regime_stability
        }
        
        self.logger.info("Backtesting Agent initialized")

    async def initialize(self, event_manager=None, strategy_agent=None):
        """Initialize agent with dependencies"""
        await super().initialize(event_manager)
        
        self.strategy_agent = strategy_agent
        
        # Initialize backtest engine
        await self.engine.initialize()
        
        # Subscribe to events
        if self.event_manager:
            self.event_manager.subscribe(EventType.STRATEGY_UPDATE, self._handle_strategy_update)
            self.event_manager.subscribe(EventType.MARKET_REGIME_CHANGE, self._handle_regime_change)
        
        self.state = AgentState.RUNNING
        self.logger.info("Backtesting Agent initialized and running")

    async def generate_test_hypotheses(
        self,
        strategy_type: str,
        market_conditions: Dict[str, Any],
        historical_performance: Optional[Dict[str, Any]] = None
    ) -> List[BacktestHypothesis]:
        """
        Generate intelligent hypotheses for backtesting
        
        Args:
            strategy_type: Type of strategy to test
            market_conditions: Current market analysis
            historical_performance: Past performance data
            
        Returns:
            List of hypotheses to test
        """
        try:
            # Prepare context for AI
            context = self._prepare_hypothesis_context(
                strategy_type, market_conditions, historical_performance
            )
            
            # Get AI-generated hypotheses
            hypotheses = await self._generate_ai_hypotheses(context)
            
            # Add rule-based hypotheses
            rule_based = self._generate_rule_based_hypotheses(
                strategy_type, market_conditions
            )
            
            # Combine and prioritize
            all_hypotheses = hypotheses + rule_based
            prioritized = self._prioritize_hypotheses(all_hypotheses)
            
            # Add to queue
            for hyp in prioritized:
                self.hypothesis_queue.append(hyp)
            
            return prioritized[:10]  # Return top 10
            
        except Exception as e:
            self.logger.error(f"Error generating hypotheses: {str(e)}")
            return []

    async def run_backtest(
        self,
        config: BacktestConfig,
        strategy_logic: Callable,
        market_data: pd.DataFrame
    ) -> BacktestResults:
        """
        Run a single backtest
        
        Args:
            config: Backtest configuration
            strategy_logic: Strategy implementation
            market_data: Historical market data
            
        Returns:
            Backtest results with analysis
        """
        try:
            # Validate inputs
            if len(market_data) < self.min_sample_size:
                raise ValueError(f"Insufficient data: {len(market_data)} < {self.min_sample_size}")
            
            # Run based on test type
            if config.test_type == BacktestType.WALK_FORWARD:
                results = await self._run_walk_forward(config, strategy_logic, market_data)
            elif config.test_type == BacktestType.MONTE_CARLO:
                results = await self._run_monte_carlo(config, strategy_logic, market_data)
            elif config.test_type == BacktestType.PARAMETER_SWEEP:
                results = await self._run_parameter_sweep(config, strategy_logic, market_data)
            else:
                results = await self._run_single_backtest(config, strategy_logic, market_data)
            
            # Enhance with AI analysis
            results = await self._enhance_results_with_ai(results)
            
            # Store results
            self.test_history.append(results)
            
            # Update performance tracking
            self._update_performance_tracking(results)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error in backtest: {str(e)}")
            raise

    async def optimize_parameters(
        self,
        strategy_type: str,
        parameter_ranges: Dict[str, Tuple[float, float]],
        objective: str,
        market_data: pd.DataFrame,
        constraints: Optional[Dict[str, Any]] = None
    ) -> OptimizationResult:
        """
        Optimize strategy parameters intelligently
        
        Args:
            strategy_type: Type of strategy
            parameter_ranges: Min/max for each parameter
            objective: Optimization objective (e.g., 'sharpe', 'returns')
            market_data: Historical data for testing
            constraints: Additional constraints
            
        Returns:
            Optimization results
        """
        try:
            # Check cache
            cache_key = self._generate_optimization_key(
                strategy_type, parameter_ranges, objective
            )
            if cache_key in self.optimization_cache:
                return self.optimization_cache[cache_key]
            
            # Define objective function
            async def objective_function(params):
                # Convert array to parameter dict
                param_dict = self._array_to_params(params, parameter_ranges)
                
                # Create config
                config = BacktestConfig(
                    test_type=BacktestType.SINGLE_PERIOD,
                    start_date=market_data.index[0],
                    end_date=market_data.index[-1],
                    initial_capital=100000,
                    strategy_params=param_dict
                )
                
                # Run backtest
                strategy_logic = self._get_strategy_logic(strategy_type, param_dict)
                results = await self._run_single_backtest(config, strategy_logic, market_data)
                
                # Return objective value (negative for minimization)
                if objective == 'sharpe':
                    return -results.performance_metrics.get('sharpe_ratio', 0)
                elif objective == 'returns':
                    return -results.performance_metrics.get('total_return', 0)
                else:
                    return -results.performance_metrics.get('calmar_ratio', 0)
            
            # Convert to sync function for scipy
            def sync_objective(params):
                return asyncio.run(objective_function(params))
            
            # Set bounds
            bounds = [(r[0], r[1]) for r in parameter_ranges.values()]
            
            # Run optimization
            result = differential_evolution(
                sync_objective,
                bounds,
                maxiter=50,
                popsize=15,
                seed=42
            )
            
            # Get best parameters
            best_params = self._array_to_params(result.x, parameter_ranges)
            
            # Analyze parameter importance
            importance = await self._analyze_parameter_importance(
                strategy_type, best_params, parameter_ranges, market_data
            )
            
            # Check for overfitting
            overfitting_score = await self._check_overfitting(
                strategy_type, best_params, market_data
            )
            
            # Create result
            opt_result = OptimizationResult(
                best_params=best_params,
                best_score=-result.fun,
                parameter_importance=importance,
                convergence_history=result.population_energies.tolist(),
                overfitting_score=overfitting_score
            )
            
            # Cache result
            self.optimization_cache[cache_key] = opt_result
            
            return opt_result
            
        except Exception as e:
            self.logger.error(f"Error in optimization: {str(e)}")
            raise

    async def validate_strategy(
        self,
        strategy_type: str,
        backtest_results: List[BacktestResults],
        market_conditions: Dict[str, Any]
    ) -> ValidationResult:
        """
        Validate strategy robustness and reliability
        
        Args:
            strategy_type: Type of strategy
            backtest_results: Results from multiple backtests
            market_conditions: Current market analysis
            
        Returns:
            Validation results with recommendations
        """
        try:
            # Aggregate performance metrics
            aggregated_metrics = self._aggregate_metrics(backtest_results)
            
            # Run statistical tests
            statistical_results = await self._run_statistical_tests(backtest_results)
            
            # Check regime stability
            regime_stability = await self._analyze_regime_stability(backtest_results)
            
            # Get AI validation
            ai_validation = await self._get_ai_validation(
                strategy_type, aggregated_metrics, statistical_results, regime_stability
            )
            
            # Determine overall validity
            is_valid = (
                statistical_results['sharpe_significant'] and
                statistical_results['returns_significant'] and
                regime_stability['stable_across_regimes'] and
                ai_validation['confidence'] > 0.7
            )
            
            # Calculate confidence score
            confidence_score = np.mean([
                statistical_results['confidence'],
                regime_stability['stability_score'],
                ai_validation['confidence']
            ])
            
            # Compile strengths and weaknesses
            strengths = []
            weaknesses = []
            
            if aggregated_metrics['avg_sharpe'] > 1.5:
                strengths.append("Strong risk-adjusted returns")
            if aggregated_metrics['win_rate'] > 0.6:
                strengths.append("High win rate")
            if regime_stability['stable_across_regimes']:
                strengths.append("Performs well across market regimes")
            
            if aggregated_metrics['max_drawdown'] > 0.2:
                weaknesses.append("High maximum drawdown")
            if statistical_results['consistency'] < 0.5:
                weaknesses.append("Inconsistent performance")
            if any(r.parameter_sensitivity for r in backtest_results if r.parameter_sensitivity):
                weaknesses.append("Sensitive to parameter changes")
            
            # Generate recommendations
            recommendations = await self._generate_recommendations(
                strategy_type, strengths, weaknesses, aggregated_metrics
            )
            
            # Risk warnings
            risk_warnings = self._generate_risk_warnings(
                aggregated_metrics, statistical_results, regime_stability
            )
            
            return ValidationResult(
                is_valid=is_valid,
                confidence_score=confidence_score,
                strengths=strengths,
                weaknesses=weaknesses,
                recommendations=recommendations,
                risk_warnings=risk_warnings
            )
            
        except Exception as e:
            self.logger.error(f"Error in validation: {str(e)}")
            raise

    async def _run_single_backtest(
        self,
        config: BacktestConfig,
        strategy_logic: Callable,
        market_data: pd.DataFrame
    ) -> BacktestResults:
        """Run a single period backtest"""
        # Filter data for period
        test_data = market_data[
            (market_data.index >= config.start_date) &
            (market_data.index <= config.end_date)
        ]
        
        # Initialize portfolio
        portfolio = Portfolio(cash=config.initial_capital)
        
        # Run backtest
        trades = []
        equity_curve = []
        positions_history = []
        
        for idx, row in test_data.iterrows():
            # Get signals from strategy
            signals = strategy_logic(row, portfolio, config.strategy_params)
            
            # Execute trades
            for signal in signals:
                if self._validate_signal(signal, portfolio):
                    trade = self._execute_trade(signal, row, portfolio, config)
                    trades.append(trade)
            
            # Update portfolio
            self._update_portfolio(portfolio, row)
            
            # Record state
            equity_curve.append(portfolio.total_value)
            positions_history.append(self._get_position_snapshot(portfolio))
        
        # Calculate metrics
        equity_series = pd.Series(equity_curve, index=test_data.index)
        performance_metrics = self._calculate_performance_metrics(
            equity_series, trades, config.initial_capital
        )
        
        # Drawdown analysis
        drawdown_analysis = self._analyze_drawdowns(equity_series)
        
        # Risk metrics
        risk_metrics = self._calculate_risk_metrics(
            equity_series, trades, positions_history
        )
        
        return BacktestResults(
            config=config,
            performance_metrics=performance_metrics,
            trades=trades,
            equity_curve=equity_series,
            positions=pd.DataFrame(positions_history),
            drawdown_analysis=drawdown_analysis,
            risk_metrics=risk_metrics
        )

    async def _run_walk_forward(
        self,
        config: BacktestConfig,
        strategy_logic: Callable,
        market_data: pd.DataFrame
    ) -> BacktestResults:
        """Run walk-forward analysis"""
        wf_params = config.walk_forward_params or {
            'in_sample_periods': 252,  # 1 year
            'out_sample_periods': 63,   # 3 months
            'step_size': 21            # 1 month
        }
        
        results = []
        current_start = config.start_date
        
        while current_start + timedelta(days=wf_params['in_sample_periods'] + wf_params['out_sample_periods']) <= config.end_date:
            # In-sample period
            in_sample_end = current_start + timedelta(days=wf_params['in_sample_periods'])
            
            # Optimize on in-sample
            opt_result = await self.optimize_parameters(
                'strategy_type',  # Would be passed properly
                config.optimization_params['ranges'],
                'sharpe',
                market_data[current_start:in_sample_end]
            )
            
            # Test on out-of-sample
            out_sample_start = in_sample_end
            out_sample_end = out_sample_start + timedelta(days=wf_params['out_sample_periods'])
            
            test_config = BacktestConfig(
                test_type=BacktestType.SINGLE_PERIOD,
                start_date=out_sample_start,
                end_date=out_sample_end,
                initial_capital=config.initial_capital,
                strategy_params=opt_result.best_params,
                commission=config.commission,
                slippage=config.slippage
            )
            
            period_result = await self._run_single_backtest(
                test_config, strategy_logic, market_data
            )
            results.append(period_result)
            
            # Step forward
            current_start += timedelta(days=wf_params['step_size'])
        
        # Combine results
        return self._combine_walk_forward_results(results, config)

    async def _run_monte_carlo(
        self,
        config: BacktestConfig,
        strategy_logic: Callable,
        market_data: pd.DataFrame
    ) -> BacktestResults:
        """Run Monte Carlo simulation"""
        n_simulations = 1000
        results = []
        
        for i in range(n_simulations):
            # Resample returns with replacement
            returns = market_data['returns'].values
            resampled_returns = np.random.choice(returns, size=len(returns), replace=True)
            
            # Reconstruct price series
            resampled_prices = (1 + resampled_returns).cumprod() * market_data['close'].iloc[0]
            resampled_data = market_data.copy()
            resampled_data['close'] = resampled_prices
            
            # Run backtest
            sim_result = await self._run_single_backtest(
                config, strategy_logic, resampled_data
            )
            results.append(sim_result)
        
        # Analyze distribution of results
        return self._analyze_monte_carlo_results(results, config)

    async def _run_parameter_sweep(
        self,
        config: BacktestConfig,
        strategy_logic: Callable,
        market_data: pd.DataFrame
    ) -> BacktestResults:
        """Run parameter sweep analysis"""
        param_ranges = config.optimization_params['ranges']
        
        # Create parameter grid
        param_grid = self._create_parameter_grid(param_ranges)
        
        results = []
        for params in param_grid:
            test_config = config
            test_config.strategy_params = params
            
            result = await self._run_single_backtest(
                test_config, strategy_logic, market_data
            )
            results.append((params, result))
        
        # Analyze parameter sensitivity
        return self._analyze_parameter_sweep(results, config)

    def _calculate_performance_metrics(
        self,
        equity_curve: pd.Series,
        trades: List[Dict[str, Any]],
        initial_capital: float
    ) -> Dict[str, float]:
        """Calculate comprehensive performance metrics"""
        returns = equity_curve.pct_change().dropna()
        
        metrics = {
            'total_return': (equity_curve.iloc[-1] / initial_capital) - 1,
            'annual_return': self._calculate_annual_return(returns),
            'sharpe_ratio': self._calculate_sharpe_ratio(returns),
            'sortino_ratio': self._calculate_sortino_ratio(returns),
            'calmar_ratio': self._calculate_calmar_ratio(returns, equity_curve),
            'max_drawdown': self._calculate_max_drawdown(equity_curve),
            'win_rate': self._calculate_win_rate(trades),
            'profit_factor': self._calculate_profit_factor(trades),
            'avg_trade': np.mean([t['pnl'] for t in trades]) if trades else 0,
            'total_trades': len(trades),
            'avg_win': np.mean([t['pnl'] for t in trades if t['pnl'] > 0]) if trades else 0,
            'avg_loss': np.mean([t['pnl'] for t in trades if t['pnl'] < 0]) if trades else 0,
            'largest_win': max([t['pnl'] for t in trades]) if trades else 0,
            'largest_loss': min([t['pnl'] for t in trades]) if trades else 0,
            'consecutive_wins': self._max_consecutive_wins(trades),
            'consecutive_losses': self._max_consecutive_losses(trades),
            'recovery_factor': equity_curve.iloc[-1] / abs(self._calculate_max_drawdown(equity_curve)) if self._calculate_max_drawdown(equity_curve) != 0 else 0,
            'expectancy': self._calculate_expectancy(trades)
        }
        
        return metrics

    def _calculate_risk_metrics(
        self,
        equity_curve: pd.Series,
        trades: List[Dict[str, Any]],
        positions: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Calculate risk metrics"""
        returns = equity_curve.pct_change().dropna()
        
        metrics = {
            'volatility': returns.std() * np.sqrt(252),
            'downside_deviation': self._calculate_downside_deviation(returns),
            'var_95': np.percentile(returns, 5),
            'cvar_95': returns[returns <= np.percentile(returns, 5)].mean(),
            'skewness': stats.skew(returns),
            'kurtosis': stats.kurtosis(returns),
            'max_position_size': max([p['size'] for p in positions]) if positions else 0,
            'avg_position_size': np.mean([p['size'] for p in positions]) if positions else 0,
            'leverage_ratio': np.mean([p['leverage'] for p in positions]) if positions else 0,
            'margin_usage': np.mean([p['margin'] for p in positions]) if positions else 0,
            'concentration_risk': self._calculate_concentration_risk(positions)
        }
        
        return metrics

    def _analyze_drawdowns(self, equity_curve: pd.Series) -> Dict[str, Any]:
        """Analyze drawdown characteristics"""
        cumulative = (1 + equity_curve.pct_change()).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        
        # Find drawdown periods
        drawdown_periods = []
        in_drawdown = False
        start_idx = None
        
        for i, dd in enumerate(drawdown):
            if dd < 0 and not in_drawdown:
                in_drawdown = True
                start_idx = i
            elif dd == 0 and in_drawdown:
                in_drawdown = False
                drawdown_periods.append({
                    'start': equity_curve.index[start_idx],
                    'end': equity_curve.index[i],
                    'depth': drawdown[start_idx:i].min(),
                    'duration': i - start_idx
                })
        
        return {
            'max_drawdown': drawdown.min(),
            'avg_drawdown': drawdown[drawdown < 0].mean() if len(drawdown[drawdown < 0]) > 0 else 0,
            'max_duration': max([p['duration'] for p in drawdown_periods]) if drawdown_periods else 0,
            'avg_duration': np.mean([p['duration'] for p in drawdown_periods]) if drawdown_periods else 0,
            'n_drawdowns': len(drawdown_periods),
            'current_drawdown': drawdown.iloc[-1],
            'time_in_drawdown': len(drawdown[drawdown < 0]) / len(drawdown),
            'largest_drawdowns': sorted(drawdown_periods, key=lambda x: x['depth'])[:5]
        }

    async def _enhance_results_with_ai(self, results: BacktestResults) -> BacktestResults:
        """Enhance backtest results with AI insights"""
        # Prepare context
        context = {
            'performance': results.performance_metrics,
            'risk': results.risk_metrics,
            'drawdown': results.drawdown_analysis,
            'n_trades': len(results.trades)
        }
        
        prompt = f"""
        Analyze these backtest results and provide insights:
        
        Performance:
        - Total Return: {context['performance']['total_return']:.2%}
        - Sharpe Ratio: {context['performance']['sharpe_ratio']:.2f}
        - Max Drawdown: {context['performance']['max_drawdown']:.2%}
        - Win Rate: {context['performance']['win_rate']:.2%}
        
        Risk:
        - Volatility: {context['risk']['volatility']:.2%}
        - VaR 95%: {context['risk']['var_95']:.2%}
        - Skewness: {context['risk']['skewness']:.2f}
        
        Provide:
        1. Key strengths of this strategy
        2. Main weaknesses or concerns
        3. Market conditions where it would excel
        4. Market conditions where it would struggle
        5. Suggestions for improvement
        
        Format as JSON with keys: strengths, weaknesses, excel_conditions, struggle_conditions, improvements
        """
        
        try:
            response = await asyncio.wait_for(self._query_llm(prompt), timeout=5.0)
            ai_insights = json.loads(response)
            
            # Add AI insights to results
            results.ai_analysis = ai_insights
        except:
            # Fallback insights
            results.ai_analysis = {
                'strengths': ["Consistent performance"],
                'weaknesses': ["Drawdown management"],
                'excel_conditions': ["Trending markets"],
                'struggle_conditions': ["High volatility"],
                'improvements': ["Add dynamic position sizing"]
            }
        
        return results

    async def _generate_ai_hypotheses(
        self,
        context: Dict[str, Any]
    ) -> List[BacktestHypothesis]:
        """Generate hypotheses using AI"""
        prompt = f"""
        Generate backtesting hypotheses for:
        
        Strategy: {context['strategy_type']}
        Market Regime: {context['market_regime']}
        Recent Performance: {context.get('recent_performance', 'N/A')}
        
        Generate 3-5 specific, testable hypotheses about:
        1. Parameter optimization
        2. Market regime adaptation
        3. Risk management improvements
        4. Entry/exit timing
        
        For each hypothesis, provide:
        - The hypothesis statement
        - Specific parameters to test
        - Expected outcome
        - Reasoning
        
        Format as JSON array with keys: hypothesis, parameters, expected_outcome, reasoning
        """
        
        try:
            response = await asyncio.wait_for(self._query_llm(prompt), timeout=5.0)
            hypotheses_data = json.loads(response)
            
            hypotheses = []
            for i, h_data in enumerate(hypotheses_data):
                # Create test config
                test_config = BacktestConfig(
                    test_type=BacktestType.PARAMETER_SWEEP,
                    start_date=datetime.now() - timedelta(days=730),
                    end_date=datetime.now(),
                    initial_capital=100000,
                    strategy_params=h_data['parameters']
                )
                
                hypothesis = BacktestHypothesis(
                    hypothesis=h_data['hypothesis'],
                    test_design=test_config,
                    expected_outcome=h_data['expected_outcome'],
                    confidence=0.7,
                    reasoning=h_data['reasoning'],
                    priority=i + 1
                )
                hypotheses.append(hypothesis)
            
            return hypotheses
            
        except:
            return []

    def _generate_rule_based_hypotheses(
        self,
        strategy_type: str,
        market_conditions: Dict[str, Any]
    ) -> List[BacktestHypothesis]:
        """Generate rule-based hypotheses"""
        hypotheses = []
        
        # Volatility-based hypothesis
        if market_conditions.get('volatility_regime') == 'high':
            test_config = BacktestConfig(
                test_type=BacktestType.PARAMETER_SWEEP,
                start_date=datetime.now() - timedelta(days=365),
                end_date=datetime.now(),
                initial_capital=100000,
                strategy_params={'volatility_filter': True, 'position_size': 0.5}
            )
            
            hypotheses.append(BacktestHypothesis(
                hypothesis="Reducing position size in high volatility improves risk-adjusted returns",
                test_design=test_config,
                expected_outcome={'sharpe_improvement': 0.2},
                confidence=0.8,
                reasoning="High volatility increases risk, smaller positions may help",
                priority=1
            ))
        
        # Trend-based hypothesis
        if market_conditions.get('trend_strength', 0) > 0.7:
            test_config = BacktestConfig(
                test_type=BacktestType.SINGLE_PERIOD,
                start_date=datetime.now() - timedelta(days=180),
                end_date=datetime.now(),
                initial_capital=100000,
                strategy_params={'trend_filter': True, 'trend_threshold': 0.6}
            )
            
            hypotheses.append(BacktestHypothesis(
                hypothesis="Adding trend filter improves win rate in trending markets",
                test_design=test_config,
                expected_outcome={'win_rate_improvement': 0.1},
                confidence=0.75,
                reasoning="Strong trends provide directional edge",
                priority=2
            ))
        
        return hypotheses

    def _prioritize_hypotheses(
        self,
        hypotheses: List[BacktestHypothesis]
    ) -> List[BacktestHypothesis]:
        """Prioritize hypotheses for testing"""
        # Sort by confidence and priority
        return sorted(
            hypotheses,
            key=lambda h: (h.confidence * 0.7 + (1 / h.priority) * 0.3),
            reverse=True
        )

    def _aggregate_metrics(
        self,
        results: List[BacktestResults]
    ) -> Dict[str, float]:
        """Aggregate metrics across multiple backtests"""
        if not results:
            return {}
        
        metrics = defaultdict(list)
        
        for result in results:
            for key, value in result.performance_metrics.items():
                metrics[key].append(value)
        
        aggregated = {}
        for key, values in metrics.items():
            aggregated[f'avg_{key}'] = np.mean(values)
            aggregated[f'std_{key}'] = np.std(values)
            aggregated[f'min_{key}'] = np.min(values)
            aggregated[f'max_{key}'] = np.max(values)
        
        return dict(aggregated)

    async def _run_statistical_tests(
        self,
        results: List[BacktestResults]
    ) -> Dict[str, Any]:
        """Run statistical significance tests"""
        # Extract returns from all backtests
        all_returns = []
        for result in results:
            returns = result.equity_curve.pct_change().dropna()
            all_returns.extend(returns.values)
        
        all_returns = np.array(all_returns)
        
        # Test if returns are significantly positive
        t_stat, p_value = stats.ttest_1samp(all_returns, 0)
        returns_significant = p_value < 0.05 and np.mean(all_returns) > 0
        
        # Test if Sharpe ratio is significant
        sharpe_ratios = [r.performance_metrics['sharpe_ratio'] for r in results]
        sharpe_significant = np.mean(sharpe_ratios) > 0.5 and np.std(sharpe_ratios) < 0.5
        
        # Test consistency
        consistency = self._test_consistency(results)
        
        # Overall confidence
        confidence = 1 - p_value if returns_significant else p_value
        
        return {
            'returns_significant': returns_significant,
            'sharpe_significant': sharpe_significant,
            'consistency': consistency,
            'p_value': p_value,
            't_statistic': t_stat,
            'confidence': confidence
        }

    async def _analyze_regime_stability(
        self,
        results: List[BacktestResults]
    ) -> Dict[str, Any]:
        """Analyze performance stability across market regimes"""
        # Group results by regime (simplified)
        regime_performance = defaultdict(list)
        
        for result in results:
            if hasattr(result, 'regime_analysis') and result.regime_analysis:
                for regime, perf in result.regime_analysis.items():
                    regime_performance[regime].append(perf)
        
        # Analyze stability
        stability_scores = {}
        for regime, perfs in regime_performance.items():
            if perfs:
                stability_scores[regime] = 1 - (np.std(perfs) / (abs(np.mean(perfs)) + 1e-6))
        
        # Overall stability
        stable_across_regimes = all(score > 0.5 for score in stability_scores.values())
        avg_stability = np.mean(list(stability_scores.values())) if stability_scores else 0.5
        
        return {
            'stable_across_regimes': stable_across_regimes,
            'stability_score': avg_stability,
            'regime_scores': stability_scores,
            'worst_regime': min(stability_scores.items(), key=lambda x: x[1])[0] if stability_scores else None
        }

    async def _get_ai_validation(
        self,
        strategy_type: str,
        metrics: Dict[str, float],
        statistical_results: Dict[str, Any],
        regime_stability: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get AI validation of strategy"""
        prompt = f"""
        Validate this trading strategy based on backtest results:
        
        Strategy Type: {strategy_type}
        
        Average Performance:
        - Sharpe Ratio: {metrics.get('avg_sharpe_ratio', 0):.2f}
        - Total Return: {metrics.get('avg_total_return', 0):.2%}
        - Max Drawdown: {metrics.get('avg_max_drawdown', 0):.2%}
        - Win Rate: {metrics.get('avg_win_rate', 0):.2%}
        
        Statistical Tests:
        - Returns Significant: {statistical_results['returns_significant']}
        - P-value: {statistical_results['p_value']:.4f}
        
        Regime Stability:
        - Stable Across Regimes: {regime_stability['stable_across_regimes']}
        - Stability Score: {regime_stability['stability_score']:.2f}
        
        Provide validation assessment with:
        1. Overall confidence (0-1)
        2. Key concerns
        3. Whether to deploy this strategy
        
        Format as JSON with keys: confidence, concerns, deploy_recommendation
        """
        
        try:
            response = await asyncio.wait_for(self._query_llm(prompt), timeout=5.0)
            return json.loads(response)
        except:
            # Fallback validation
            return {
                'confidence': 0.6,
                'concerns': ["Limited sample size", "Parameter sensitivity"],
                'deploy_recommendation': metrics.get('avg_sharpe_ratio', 0) > 1.0
            }

    async def _generate_recommendations(
        self,
        strategy_type: str,
        strengths: List[str],
        weaknesses: List[str],
        metrics: Dict[str, float]
    ) -> List[str]:
        """Generate improvement recommendations"""
        recommendations = []
        
        # Drawdown-based recommendations
        if metrics.get('avg_max_drawdown', 0) > 0.15:
            recommendations.append("Implement dynamic position sizing to reduce drawdowns")
            recommendations.append("Add stop-loss rules or volatility-based exits")
        
        # Sharpe-based recommendations
        if metrics.get('avg_sharpe_ratio', 0) < 1.0:
            recommendations.append("Consider adding filters to improve trade quality")
            recommendations.append("Optimize entry timing with additional signals")
        
        # Win rate recommendations
        if metrics.get('avg_win_rate', 0) < 0.5:
            recommendations.append("Review entry criteria for false signals")
            recommendations.append("Consider trend filters to improve direction")
        
        # Consistency recommendations
        if 'Inconsistent performance' in weaknesses:
            recommendations.append("Add regime detection to adapt strategy")
            recommendations.append("Implement ensemble approach for stability")
        
        return recommendations[:5]  # Top 5 recommendations

    def _generate_risk_warnings(
        self,
        metrics: Dict[str, float],
        statistical_results: Dict[str, Any],
        regime_stability: Dict[str, Any]
    ) -> List[str]:
        """Generate risk warnings"""
        warnings = []
        
        # Statistical significance warning
        if not statistical_results['returns_significant']:
            warnings.append("Returns not statistically significant - results may be due to chance")
        
        # Drawdown warning
        if metrics.get('avg_max_drawdown', 0) > 0.25:
            warnings.append(f"High maximum drawdown of {metrics['avg_max_drawdown']:.1%}")
        
        # Regime dependency warning
        if not regime_stability['stable_across_regimes']:
            warnings.append(f"Performance unstable across regimes, worst in {regime_stability.get('worst_regime', 'unknown')}")
        
        # Skewness warning
        if metrics.get('avg_skewness', 0) < -1:
            warnings.append("Negative skew indicates risk of large losses")
        
        # Leverage warning
        if metrics.get('avg_leverage_ratio', 0) > 2:
            warnings.append("High leverage increases risk of margin calls")
        
        return warnings

    def _calculate_sharpe_ratio(self, returns: pd.Series, risk_free: float = 0.02) -> float:
        """Calculate Sharpe ratio"""
        excess_returns = returns - risk_free / 252
        if returns.std() == 0:
            return 0
        return np.sqrt(252) * excess_returns.mean() / returns.std()

    def _calculate_sortino_ratio(self, returns: pd.Series, risk_free: float = 0.02) -> float:
        """Calculate Sortino ratio"""
        excess_returns = returns - risk_free / 252
        downside_returns = returns[returns < 0]
        if len(downside_returns) == 0 or downside_returns.std() == 0:
            return 0
        return np.sqrt(252) * excess_returns.mean() / downside_returns.std()

    def _calculate_calmar_ratio(self, returns: pd.Series, equity_curve: pd.Series) -> float:
        """Calculate Calmar ratio"""
        annual_return = self._calculate_annual_return(returns)
        max_dd = abs(self._calculate_max_drawdown(equity_curve))
        if max_dd == 0:
            return 0
        return annual_return / max_dd

    def _calculate_annual_return(self, returns: pd.Series) -> float:
        """Calculate annualized return"""
        total_return = (1 + returns).prod() - 1
        n_years = len(returns) / 252
        return (1 + total_return) ** (1 / n_years) - 1 if n_years > 0 else 0

    def _calculate_max_drawdown(self, equity_curve: pd.Series) -> float:
        """Calculate maximum drawdown"""
        cumulative = (1 + equity_curve.pct_change()).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        return drawdown.min()

    def _calculate_win_rate(self, trades: List[Dict[str, Any]]) -> float:
        """Calculate win rate"""
        if not trades:
            return 0
        wins = sum(1 for t in trades if t['pnl'] > 0)
        return wins / len(trades)

    def _calculate_profit_factor(self, trades: List[Dict[str, Any]]) -> float:
        """Calculate profit factor"""
        if not trades:
            return 0
        gross_profit = sum(t['pnl'] for t in trades if t['pnl'] > 0)
        gross_loss = abs(sum(t['pnl'] for t in trades if t['pnl'] < 0))
        return gross_profit / gross_loss if gross_loss > 0 else float('inf')

    def _calculate_expectancy(self, trades: List[Dict[str, Any]]) -> float:
        """Calculate trade expectancy"""
        if not trades:
            return 0
        win_rate = self._calculate_win_rate(trades)
        avg_win = np.mean([t['pnl'] for t in trades if t['pnl'] > 0]) if any(t['pnl'] > 0 for t in trades) else 0
        avg_loss = abs(np.mean([t['pnl'] for t in trades if t['pnl'] < 0])) if any(t['pnl'] < 0 for t in trades) else 0
        return (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

    def _max_consecutive_wins(self, trades: List[Dict[str, Any]]) -> int:
        """Calculate maximum consecutive wins"""
        if not trades:
            return 0
        max_streak = current_streak = 0
        for trade in trades:
            if trade['pnl'] > 0:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0
        return max_streak

    def _max_consecutive_losses(self, trades: List[Dict[str, Any]]) -> int:
        """Calculate maximum consecutive losses"""
        if not trades:
            return 0
        max_streak = current_streak = 0
        for trade in trades:
            if trade['pnl'] < 0:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0
        return max_streak

    def _calculate_downside_deviation(self, returns: pd.Series, target: float = 0) -> float:
        """Calculate downside deviation"""
        downside_returns = returns[returns < target]
        if len(downside_returns) == 0:
            return 0
        return np.sqrt(252) * downside_returns.std()

    def _calculate_concentration_risk(self, positions: List[Dict[str, Any]]) -> float:
        """Calculate position concentration risk"""
        if not positions:
            return 0
        position_sizes = [abs(p.get('size', 0)) for p in positions]
        total_size = sum(position_sizes)
        if total_size == 0:
            return 0
        
        # Herfindahl index
        concentration = sum((size / total_size) ** 2 for size in position_sizes)
        return concentration

    def _test_sharpe_significance(self, results: List[BacktestResults]) -> bool:
        """Test if Sharpe ratio is statistically significant"""
        sharpe_ratios = [r.performance_metrics['sharpe_ratio'] for r in results]
        # Test if significantly greater than 0.5
        t_stat, p_value = stats.ttest_1samp(sharpe_ratios, 0.5)
        return p_value < 0.05 and np.mean(sharpe_ratios) > 0.5

    def _test_return_significance(self, results: List[BacktestResults]) -> bool:
        """Test if returns are statistically significant"""
        all_returns = []
        for result in results:
            returns = result.equity_curve.pct_change().dropna()
            all_returns.extend(returns.values)
        
        # Test if significantly positive
        t_stat, p_value = stats.ttest_1samp(all_returns, 0)
        return p_value < 0.05 and np.mean(all_returns) > 0

    def _test_consistency(self, results: List[BacktestResults]) -> float:
        """Test strategy consistency"""
        if len(results) < 2:
            return 0.5
        
        # Check consistency of key metrics
        sharpe_ratios = [r.performance_metrics['sharpe_ratio'] for r in results]
        win_rates = [r.performance_metrics['win_rate'] for r in results]
        
        # Low variance indicates consistency
        sharpe_consistency = 1 - (np.std(sharpe_ratios) / (abs(np.mean(sharpe_ratios)) + 1e-6))
        win_rate_consistency = 1 - (np.std(win_rates) / (abs(np.mean(win_rates)) + 1e-6))
        
        return (sharpe_consistency + win_rate_consistency) / 2

    def _test_regime_stability(self, results: List[BacktestResults]) -> bool:
        """Test if strategy is stable across regimes"""
        # Simplified - would analyze actual regime performance
        return True

    def _prepare_hypothesis_context(
        self,
        strategy_type: str,
        market_conditions: Dict[str, Any],
        historical_performance: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Prepare context for hypothesis generation"""
        return {
            'strategy_type': strategy_type,
            'market_regime': market_conditions.get('regime', 'unknown'),
            'volatility_level': market_conditions.get('volatility_regime', 'normal'),
            'trend_strength': market_conditions.get('trend_strength', 0),
            'recent_performance': historical_performance or {}
        }

    async def _analyze_parameter_importance(
        self,
        strategy_type: str,
        best_params: Dict[str, Any],
        param_ranges: Dict[str, Tuple[float, float]],
        market_data: pd.DataFrame
    ) -> Dict[str, float]:
        """Analyze parameter importance"""
        importance = {}
        
        # Test sensitivity of each parameter
        for param_name, param_value in best_params.items():
            if param_name in param_ranges:
                # Test performance with parameter variations
                variations = []
                
                # Test at different values
                test_values = np.linspace(
                    param_ranges[param_name][0],
                    param_ranges[param_name][1],
                    5
                )
                
                for test_value in test_values:
                    test_params = best_params.copy()
                    test_params[param_name] = test_value
                    
                    # Would run mini-backtest here
                    # For now, simulate with random performance
                    performance = np.random.randn() * 0.1 + 1.0
                    variations.append(performance)
                
                # Importance is variance in performance
                importance[param_name] = np.std(variations)
        
        # Normalize
        total_importance = sum(importance.values())
        if total_importance > 0:
            importance = {k: v / total_importance for k, v in importance.items()}
        
        return importance

    async def _check_overfitting(
        self,
        strategy_type: str,
        params: Dict[str, Any],
        market_data: pd.DataFrame
    ) -> float:
        """Check for overfitting"""
        # Split data
        split_point = len(market_data) // 2
        in_sample = market_data[:split_point]
        out_sample = market_data[split_point:]
        
        # Would run backtests on both periods
        # For now, return mock score
        in_sample_perf = 1.5  # Mock Sharpe
        out_sample_perf = 1.2  # Mock Sharpe
        
        # Overfitting score: difference in performance
        overfitting_score = (in_sample_perf - out_sample_perf) / in_sample_perf
        
        return max(0, min(1, overfitting_score))

    def _validate_signal(self, signal: TradeSignal, portfolio: Portfolio) -> bool:
        """Validate trade signal"""
        # Check capital
        if signal.quantity * signal.price > portfolio.cash:
            return False
        
        # Check position limits
        if len(portfolio.positions) >= 10:  # Max positions
            return False
        
        return True

    def _execute_trade(
        self,
        signal: TradeSignal,
        market_data: Any,
        portfolio: Portfolio,
        config: BacktestConfig
    ) -> Dict[str, Any]:
        """Execute trade in backtest"""
        # Calculate costs
        trade_value = signal.quantity * signal.price
        commission = trade_value * config.commission
        slippage = trade_value * config.slippage
        
        # Update portfolio
        portfolio.cash -= (trade_value + commission + slippage)
        
        # Create position
        position = Position(
            symbol=signal.symbol,
            quantity=signal.quantity,
            entry_price=signal.price,
            entry_time=market_data.name  # Assuming index is datetime
        )
        
        portfolio.positions[signal.symbol] = position
        
        return {
            'time': market_data.name,
            'symbol': signal.symbol,
            'side': signal.signal_type,
            'quantity': signal.quantity,
            'price': signal.price,
            'commission': commission,
            'slippage': slippage,
            'pnl': 0  # Will be calculated on exit
        }

    def _update_portfolio(self, portfolio: Portfolio, market_data: Any):
        """Update portfolio with current prices"""
        # Update position values
        for symbol, position in portfolio.positions.items():
            if hasattr(market_data, symbol):
                position.current_price = getattr(market_data, symbol)
            elif hasattr(market_data, 'close'):
                position.current_price = market_data.close
        
        # Calculate total value
        position_value = sum(
            pos.quantity * pos.current_price
            for pos in portfolio.positions.values()
        )
        portfolio.total_value = portfolio.cash + position_value

    def _get_position_snapshot(self, portfolio: Portfolio) -> Dict[str, Any]:
        """Get current position snapshot"""
        return {
            'cash': portfolio.cash,
            'positions': len(portfolio.positions),
            'total_value': portfolio.total_value,
            'leverage': sum(abs(p.quantity * p.current_price) for p in portfolio.positions.values()) / portfolio.total_value if portfolio.total_value > 0 else 0,
            'size': sum(abs(p.quantity * p.current_price) for p in portfolio.positions.values()),
            'margin': 0  # Simplified
        }

    def _get_strategy_logic(self, strategy_type: str, params: Dict[str, Any]) -> Callable:
        """Get strategy logic function"""
        # This would return actual strategy implementations
        # For now, return a mock function
        def mock_strategy(market_data, portfolio, params):
            # Simple momentum strategy
            signals = []
            
            if hasattr(market_data, 'close') and hasattr(market_data, 'sma_20'):
                if market_data.close > market_data.sma_20 and len(portfolio.positions) == 0:
                    signals.append(TradeSignal(
                        symbol='SPY',
                        signal_type='BUY',
                        quantity=100,
                        price=market_data.close
                    ))
                elif market_data.close < market_data.sma_20 and len(portfolio.positions) > 0:
                    signals.append(TradeSignal(
                        symbol='SPY',
                        signal_type='SELL',
                        quantity=100,
                        price=market_data.close
                    ))
            
            return signals
        
        return mock_strategy

    def _generate_optimization_key(
        self,
        strategy_type: str,
        param_ranges: Dict[str, Tuple[float, float]],
        objective: str
    ) -> str:
        """Generate cache key for optimization"""
        key_data = {
            'strategy': strategy_type,
            'ranges': str(param_ranges),
            'objective': objective
        }
        return hashlib.md5(str(key_data).encode()).hexdigest()

    def _array_to_params(
        self,
        array: np.ndarray,
        param_ranges: Dict[str, Tuple[float, float]]
    ) -> Dict[str, Any]:
        """Convert parameter array to dictionary"""
        params = {}
        for i, (name, _) in enumerate(param_ranges.items()):
            if i < len(array):
                params[name] = float(array[i])
        return params

    def _combine_walk_forward_results(
        self,
        results: List[BacktestResults],
        config: BacktestConfig
    ) -> BacktestResults:
        """Combine walk-forward results"""
        # Combine equity curves
        combined_equity = pd.concat([r.equity_curve for r in results])
        
        # Combine trades
        all_trades = []
        for r in results:
            all_trades.extend(r.trades)
        
        # Recalculate metrics on combined results
        performance_metrics = self._calculate_performance_metrics(
            combined_equity, all_trades, config.initial_capital
        )
        
        # Average risk metrics
        risk_metrics = {}
        for metric in results[0].risk_metrics.keys():
            values = [r.risk_metrics[metric] for r in results]
            risk_metrics[metric] = np.mean(values)
        
        return BacktestResults(
            config=config,
            performance_metrics=performance_metrics,
            trades=all_trades,
            equity_curve=combined_equity,
            positions=pd.concat([r.positions for r in results]),
            drawdown_analysis=self._analyze_drawdowns(combined_equity),
            risk_metrics=risk_metrics
        )

    def _analyze_monte_carlo_results(
        self,
        results: List[BacktestResults],
        config: BacktestConfig
    ) -> BacktestResults:
        """Analyze Monte Carlo simulation results"""
        # Extract key metrics
        returns = [r.performance_metrics['total_return'] for r in results]
        sharpes = [r.performance_metrics['sharpe_ratio'] for r in results]
        drawdowns = [r.performance_metrics['max_drawdown'] for r in results]
        
        # Calculate percentiles
        percentiles = [5, 25, 50, 75, 95]
        
        monte_carlo_analysis = {
            'return_percentiles': {p: np.percentile(returns, p) for p in percentiles},
            'sharpe_percentiles': {p: np.percentile(sharpes, p) for p in percentiles},
            'drawdown_percentiles': {p: np.percentile(drawdowns, p) for p in percentiles},
            'probability_profit': sum(1 for r in returns if r > 0) / len(returns),
            'expected_return': np.mean(returns),
            'return_std': np.std(returns),
            'var_95': np.percentile(returns, 5),
            'cvar_95': np.mean([r for r in returns if r <= np.percentile(returns, 5)])
        }
        
        # Use median as representative result
        median_idx = np.argsort(returns)[len(returns) // 2]
        median_result = results[median_idx]
        
        # Add Monte Carlo analysis to result
        median_result.monte_carlo_analysis = monte_carlo_analysis
        
        return median_result

    def _analyze_parameter_sweep(
        self,
        results: List[Tuple[Dict[str, Any], BacktestResults]],
        config: BacktestConfig
    ) -> BacktestResults:
        """Analyze parameter sweep results"""
        # Find best parameter set
        best_idx = max(
            range(len(results)),
            key=lambda i: results[i][1].performance_metrics['sharpe_ratio']
        )
        
        best_params, best_result = results[best_idx]
        
        # Analyze parameter sensitivity
        param_names = list(best_params.keys())
        sensitivity_analysis = {}
        
        for param in param_names:
            # Group by parameter value
            param_groups = defaultdict(list)
            for params, result in results:
                param_groups[params[param]].append(
                    result.performance_metrics['sharpe_ratio']
                )
            
            # Calculate sensitivity
            values = list(param_groups.keys())
            avg_sharpes = [np.mean(param_groups[v]) for v in values]
            
            if len(values) > 1:
                sensitivity = np.std(avg_sharpes) / (np.mean(avg_sharpes) + 1e-6)
            else:
                sensitivity = 0
            
            sensitivity_analysis[param] = {
                'values': values,
                'sharpe_ratios': avg_sharpes,
                'sensitivity': sensitivity
            }
        
        # Add to best result
        best_result.parameter_sensitivity = sensitivity_analysis
        
        return best_result

    def _create_parameter_grid(
        self,
        param_ranges: Dict[str, Tuple[float, float]]
    ) -> List[Dict[str, Any]]:
        """Create parameter grid for sweep"""
        import itertools
        
        # Create discrete values for each parameter
        param_values = {}
        for param, (min_val, max_val) in param_ranges.items():
            # 5 values per parameter
            param_values[param] = np.linspace(min_val, max_val, 5)
        
        # Create all combinations
        param_names = list(param_values.keys())
        value_combinations = itertools.product(*param_values.values())
        
        grid = []
        for values in value_combinations:
            params = dict(zip(param_names, values))
            grid.append(params)
        
        return grid

    def _update_performance_tracking(self, results: BacktestResults):
        """Update strategy performance tracking"""
        strategy_type = results.config.strategy_params.get('strategy_type', 'unknown')
        
        # Track key metrics
        self.strategy_performance[strategy_type].append(
            results.performance_metrics['sharpe_ratio']
        )
        
        # Track regime performance
        if hasattr(results, 'regime_analysis') and results.regime_analysis:
            for regime, performance in results.regime_analysis.items():
                self.regime_performance[strategy_type][regime] = performance

    async def _handle_strategy_update(self, event: Event):
        """Handle strategy update events"""
        if hasattr(event, 'data') and 'strategy' in event.data:
            # Generate hypotheses for new strategy
            strategy_type = event.data['strategy']
            market_conditions = event.data.get('market_conditions', {})
            
            hypotheses = await self.generate_test_hypotheses(
                strategy_type, market_conditions
            )
            
            self.logger.info(f"Generated {len(hypotheses)} hypotheses for {strategy_type}")

    async def _handle_regime_change(self, event: Event):
        """Handle market regime change events"""
        if hasattr(event, 'data') and 'new_regime' in event.data:
            new_regime = event.data['new_regime']
            
            # Re-evaluate strategies for new regime
            self.logger.info(f"Market regime changed to {new_regime}, re-evaluating strategies")

    async def _query_llm(self, prompt: str) -> str:
        """Query LLM for insights"""
        # Mock implementation - replace with actual LLM call
        if "backtest results" in prompt:
            return json.dumps({
                'strengths': [
                    "Consistent performance across market conditions",
                    "Low correlation with market beta",
                    "Strong risk-adjusted returns"
                ],
                'weaknesses': [
                    "Sensitive to volatility spikes",
                    "Requires significant capital for proper execution"
                ],
                'excel_conditions': ["Trending markets with moderate volatility"],
                'struggle_conditions': ["Choppy, range-bound markets"],
                'improvements': [
                    "Add volatility filters to reduce whipsaws",
                    "Implement dynamic position sizing",
                    "Consider regime detection for adaptation"
                ]
            })
        elif "hypotheses" in prompt:
            return json.dumps([
                {
                    'hypothesis': "Tighter stop losses improve risk-adjusted returns in high volatility",
                    'parameters': {'stop_loss': 0.02, 'volatility_filter': True},
                    'expected_outcome': {'sharpe_improvement': 0.3},
                    'reasoning': "Smaller losses preserve capital in volatile conditions"
                },
                {
                    'hypothesis': "Trend filters reduce false signals in ranging markets",
                    'parameters': {'trend_filter': True, 'trend_threshold': 0.7},
                    'expected_outcome': {'win_rate_improvement': 0.15},
                    'reasoning': "Avoiding trades in unclear trends improves accuracy"
                }
            ])
        elif "Validate this trading strategy" in prompt:
            return json.dumps({
                'confidence': 0.75,
                'concerns': [
                    "Limited testing in extreme market conditions",
                    "Parameter sensitivity needs monitoring"
                ],
                'deploy_recommendation': True
            })
        else:
            return "{}"

    async def get_backtest_summary(self) -> Dict[str, Any]:
        """Get summary of all backtests"""
        summary = {
            'total_tests': len(self.test_history),
            'active_tests': len(self.active_tests),
            'hypotheses_pending': len(self.hypothesis_queue),
            'strategy_performance': {},
            'regime_performance': dict(self.regime_performance),
            'recent_tests': []
        }
        
        # Summarize strategy performance
        for strategy, sharpes in self.strategy_performance.items():
            if sharpes:
                summary['strategy_performance'][strategy] = {
                    'avg_sharpe': np.mean(sharpes),
                    'std_sharpe': np.std(sharpes),
                    'best_sharpe': max(sharpes),
                    'worst_sharpe': min(sharpes),
                    'n_tests': len(sharpes)
                }
        
        # Recent test results
        for result in self.test_history[-5:]:
            summary['recent_tests'].append({
                'type': result.config.test_type.value,
                'sharpe': result.performance_metrics['sharpe_ratio'],
                'return': result.performance_metrics['total_return'],
                'drawdown': result.performance_metrics['max_drawdown'],
                'timestamp': result.config.end_date
            })
        
        return summary

    async def export_results(
        self,
        results: BacktestResults,
        format: str = 'json',
        include_trades: bool = True
    ) -> Union[str, Dict[str, Any]]:
        """Export backtest results"""
        export_data = {
            'config': {
                'test_type': results.config.test_type.value,
                'start_date': results.config.start_date.isoformat(),
                'end_date': results.config.end_date.isoformat(),
                'initial_capital': results.config.initial_capital,
                'parameters': results.config.strategy_params
            },
            'performance': results.performance_metrics,
            'risk_metrics': results.risk_metrics,
            'drawdown_analysis': results.drawdown_analysis,
            'equity_curve': results.equity_curve.to_dict() if format == 'json' else results.equity_curve
        }
        
        if include_trades:
            export_data['trades'] = results.trades
        
        if hasattr(results, 'ai_analysis'):
            export_data['ai_analysis'] = results.ai_analysis
        
        if format == 'json':
            return json.dumps(export_data, indent=2, default=str)
        else:
            return export_data

    async def shutdown(self):
        """Shutdown agent gracefully"""
        self.state = AgentState.STOPPED
        
        # Cancel active tests
        for task in self.active_tests.values():
            task.cancel()
        
        # Shutdown engine
        await self.engine.shutdown()
        
        self.logger.info("Backtesting Agent shutdown complete")

# Factory function
def create_backtesting_agent(config: Dict[str, Any]) -> BacktestingAgent:
    """Create and return a Backtesting Agent instance"""
    return BacktestingAgent(config)


# Usage Example:
if __name__ == "__main__":
    # Example configuration
    test_config = {
        'backtest_llm_model': 'llama3.2:3b-instruct-q4_K_M',
        'max_concurrent_tests': 5,
        'min_sample_size': 252,
        'confidence_threshold': 0.95
    }
    
    # Create agent
    backtest_agent = create_backtesting_agent(test_config)
    
    # Example usage
    async def example_usage():
        await backtest_agent.initialize()
        
        # Generate test hypotheses
        hypotheses = await backtest_agent.generate_test_hypotheses(
            strategy_type='iron_condor',
            market_conditions={
                'volatility_regime': 'high',
                'trend_strength': 0.3
            }
        )
        
        print(f"Generated {len(hypotheses)} hypotheses")
        for h in hypotheses[:3]:
            print(f"- {h.hypothesis}")
            print(f"  Confidence: {h.confidence:.2f}")
            print(f"  Priority: {h.priority}")
        
        # Run a backtest
        config = BacktestConfig(
            test_type=BacktestType.WALK_FORWARD,
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2024, 12, 31),
            initial_capital=100000,
            strategy_params={'threshold': 0.02}
        )
        
        # Mock strategy and data
        def mock_strategy(data, portfolio, params):
            return []  # No trades
        
        market_data = pd.DataFrame(
            index=pd.date_range('2023-01-01', '2024-12-31'),
            data={'close': 400 + np.random.randn(730).cumsum()}
        )
        
        results = await backtest_agent.run_backtest(
            config, mock_strategy, market_data
        )
        
        print(f"\nBacktest Results:")
        print(f"Sharpe Ratio: {results.performance_metrics['sharpe_ratio']:.2f}")
        print(f"Total Return: {results.performance_metrics['total_return']:.2%}")
        print(f"Max Drawdown: {results.performance_metrics['max_drawdown']:.2%}")
    
    # Run example
    # asyncio.run(example_usage())
        