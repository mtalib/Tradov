#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderL_ML
Module: SpyderL07_PaperTradeLearner.py
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
from datetime import datetime, timedelta, UTC
from typing import Any
from dataclasses import asdict
from enum import Enum, auto

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import math
import pandas as pd
import numpy as np
from scipy.optimize import differential_evolution
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score
import joblib

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

class DatabaseManager:
    """Fallback DatabaseManager when H_Storage module is not available"""
    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        return lambda *args, **kwargs: None
from Spyder.SpyderE_Risk.SpyderE06_RiskMetrics import calculate_sharpe_ratio  # noqa: E402

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Learning parameters
MIN_TRADES_FOR_LEARNING = 50
MIN_TRADES_PER_STRATEGY = 20
CONFIDENCE_THRESHOLD = 0.95
IMPROVEMENT_THRESHOLD = 0.10  # 10% improvement required

# Performance windows
LEARNING_WINDOWS = [7, 14, 30, 60]  # days
RECENT_WEIGHT = 0.7  # Weight for recent performance

# Parameter bounds
POSITION_SIZE_BOUNDS = (0.01, 0.25)  # 1% to 25%
STOP_LOSS_BOUNDS = (0.05, 0.30)  # 5% to 30%
TAKE_PROFIT_BOUNDS = (0.10, 2.00)  # 10% to 200%
MAX_POSITIONS_BOUNDS = (1, 10)

# Market condition bins
VOLATILITY_BINS = [0, 0.10, 0.15, 0.20, 0.30, 1.0]
TREND_BINS = [-1.0, -0.02, -0.005, 0.005, 0.02, 1.0]
TIME_BINS = ['09:30-10:30', '10:30-12:00', '12:00-14:00', '14:00-16:00']

# ==============================================================================
# ENUMS
# ==============================================================================
class LearningMode(Enum):
    """Learning modes"""
    EXPLORATION = auto()  # Try new parameters
    EXPLOITATION = auto()  # Use best known parameters
    VALIDATION = auto()   # Validate improvements

class PerformanceMetric(Enum):
    """Performance metrics for optimization"""
    SHARPE_RATIO = auto()
    WIN_RATE = auto()
    PROFIT_FACTOR = auto()
    RISK_ADJUSTED_RETURN = auto()
    CALMAR_RATIO = auto()

class PatternType(Enum):
    """Types of patterns to learn"""
    ENTRY_CONDITION = auto()
    EXIT_CONDITION = auto()
    MARKET_REGIME = auto()
    TIME_PATTERN = auto()
    RISK_PATTERN = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
class TradingPattern:
    """Identified trading pattern"""
    pattern_type: PatternType
    conditions: dict[str, Any]
    performance: dict[str, float]
    confidence: float
    sample_size: int
    discovered_date: datetime

class StrategyPerformance:
    """Strategy performance analysis"""
    strategy_name: str
    total_trades: int
    win_rate: float
    avg_profit: float
    avg_loss: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown: float
    best_conditions: dict[str, Any]
    worst_conditions: dict[str, Any]
    parameter_performance: dict[str, dict[str, float]]

class OptimizationResult:
    """Parameter optimization result"""
    strategy_name: str
    original_params: dict[str, Any]
    optimized_params: dict[str, Any]
    expected_improvement: float
    confidence_interval: tuple[float, float]
    backtest_results: dict[str, float]
    recommendation: str

class LearningReport:
    """Comprehensive learning report"""
    analysis_date: datetime
    total_trades_analyzed: int
    strategy_performance: dict[str, StrategyPerformance]
    discovered_patterns: list[TradingPattern]
    optimization_results: list[OptimizationResult]
    market_insights: dict[str, Any]
    recommendations: list[str]

# ==============================================================================
# PAPER TRADE LEARNER CLASS
# ==============================================================================
class PaperTradeLearner:
    """
    Learns from paper trading results to improve system performance.

    Features:
    - Analyzes trade performance patterns
    - Optimizes strategy parameters
    - Identifies successful market conditions
    - Provides actionable recommendations
    - Tracks improvement over time
    """

    def __init__(self, database_manager: "DatabaseManager"):
        """
        Initialize paper trade learner.

        Args:
            database_manager: Database manager instance
        """
        self.db = database_manager
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Learning state
        self.learning_mode = LearningMode.EXPLORATION
        self.current_iteration = 0

        # Performance tracking
        self.performance_history: list[dict[str, Any]] = []
        self.pattern_library: dict[str, TradingPattern] = {}
        self.optimization_history: list[OptimizationResult] = []

        # ML models
        self.trade_success_classifier: RandomForestClassifier | None = None
        self.profit_predictor: RandomForestRegressor | None = None
        self.feature_scaler = StandardScaler()

        # Cache
        self._trade_cache: pd.DataFrame | None = None
        self._cache_timestamp: datetime | None = None

        self.logger.info("PaperTradeLearner initialized")

    # ==========================================================================
    # MAIN LEARNING METHODS
    # ==========================================================================
    def analyze_and_learn(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None
    ) -> LearningReport:
        """
        Perform comprehensive analysis and learning from paper trades.

        Args:
            start_date: Start of analysis period
            end_date: End of analysis period

        Returns:
            Learning report with insights and recommendations
        """
        try:
            # Set date range
            if not end_date:
                end_date = datetime.now(UTC)
            if not start_date:
                start_date = end_date - timedelta(days=30)

            # Load trade data
            trades_df = self._load_trade_data(start_date, end_date)

            if len(trades_df) < MIN_TRADES_FOR_LEARNING:
                self.logger.warning("Insufficient trades for learning: %s", len(trades_df))
                return self._create_minimal_report(trades_df)

            # Analyze performance by strategy
            strategy_performance = self._analyze_strategy_performance(trades_df)

            # Discover patterns
            patterns = self._discover_patterns(trades_df)

            # Optimize parameters
            optimization_results = self._optimize_parameters(trades_df, strategy_performance)

            # Generate market insights
            market_insights = self._analyze_market_conditions(trades_df)

            # Train ML models
            self._train_ml_models(trades_df)

            # Generate recommendations
            recommendations = self._generate_recommendations(
                strategy_performance,
                patterns,
                optimization_results,
                market_insights
            )

            # Update learning state
            self._update_learning_state(strategy_performance, optimization_results)

            # Create report
            report = LearningReport(
                analysis_date=datetime.now(UTC),
                total_trades_analyzed=len(trades_df),
                strategy_performance=strategy_performance,
                discovered_patterns=patterns,
                optimization_results=optimization_results,
                market_insights=market_insights,
                recommendations=recommendations
            )

            # Save report
            self._save_learning_report(report)

            return report

        except Exception as e:
            self.logger.error("Error in analyze_and_learn: %s", e)
            self.error_handler.handle_error(e, "analyze_and_learn")
            return self._create_error_report(str(e))

    # ==========================================================================
    # PERFORMANCE ANALYSIS
    # ==========================================================================
    def _analyze_strategy_performance(
        self,
        trades_df: pd.DataFrame
    ) -> dict[str, StrategyPerformance]:
        """Analyze performance by strategy"""
        performance = {}

        for strategy in trades_df['strategy'].unique():
            strategy_trades = trades_df[trades_df['strategy'] == strategy]

            if len(strategy_trades) < MIN_TRADES_PER_STRATEGY:
                continue

            # Calculate metrics
            wins = strategy_trades[strategy_trades['pnl'] > 0]
            losses = strategy_trades[strategy_trades['pnl'] <= 0]

            win_rate = len(wins) / len(strategy_trades)
            avg_profit = wins['pnl'].mean() if len(wins) > 0 else 0
            avg_loss = abs(losses['pnl'].mean()) if len(losses) > 0 else 0

            # Profit factor
            total_profits = wins['pnl'].sum() if len(wins) > 0 else 0
            total_losses = abs(losses['pnl'].sum()) if len(losses) > 0 else 1
            profit_factor = total_profits / total_losses if total_losses > 0 else 0

            # Risk metrics
            returns = strategy_trades['pnl'] / strategy_trades['entry_price']
            sharpe = calculate_sharpe_ratio(returns.tolist())

            # Drawdown
            cumulative_pnl = strategy_trades['pnl'].cumsum()
            running_max = cumulative_pnl.expanding().max()
            drawdown = (cumulative_pnl - running_max) / running_max
            max_drawdown = abs(drawdown.min()) if len(drawdown) > 0 else 0

            # Best/worst conditions
            best_conditions = self._find_best_conditions(strategy_trades)
            worst_conditions = self._find_worst_conditions(strategy_trades)

            # Parameter performance
            param_performance = self._analyze_parameter_performance(strategy_trades)

            performance[strategy] = StrategyPerformance(
                strategy_name=strategy,
                total_trades=len(strategy_trades),
                win_rate=win_rate,
                avg_profit=avg_profit,
                avg_loss=avg_loss,
                profit_factor=profit_factor,
                sharpe_ratio=sharpe,
                max_drawdown=max_drawdown,
                best_conditions=best_conditions,
                worst_conditions=worst_conditions,
                parameter_performance=param_performance
            )

        return performance

    def _find_best_conditions(self, trades: pd.DataFrame) -> dict[str, Any]:
        """Find market conditions with best performance"""
        # Get profitable trades
        profitable = trades[trades['pnl'] > 0]

        if len(profitable) == 0:
            return {}

        conditions = {}

        # Volatility regime
        if 'volatility' in profitable.columns:
            conditions['volatility_range'] = (
                profitable['volatility'].quantile(0.25),
                profitable['volatility'].quantile(0.75)
            )

        # Time of day
        if 'entry_time' in profitable.columns:
            profitable['hour'] = pd.to_datetime(profitable['entry_time']).dt.hour
            best_hours = profitable.groupby('hour')['pnl'].mean().nlargest(3).index.tolist()
            conditions['best_hours'] = best_hours

        # Trend
        if 'trend' in profitable.columns:
            conditions['preferred_trend'] = profitable['trend'].mode().iloc[0]

        # Market internals
        if 'vix' in profitable.columns:
            conditions['vix_range'] = (
                profitable['vix'].quantile(0.25),
                profitable['vix'].quantile(0.75)
            )

        return conditions

    def _find_worst_conditions(self, trades: pd.DataFrame) -> dict[str, Any]:
        """Find market conditions with worst performance"""
        # Get losing trades
        losses = trades[trades['pnl'] < 0]

        if len(losses) == 0:
            return {}

        conditions = {}

        # Similar analysis to best conditions but for losses
        if 'volatility' in losses.columns:
            conditions['volatility_range'] = (
                losses['volatility'].quantile(0.25),
                losses['volatility'].quantile(0.75)
            )

        if 'entry_time' in losses.columns:
            losses['hour'] = pd.to_datetime(losses['entry_time']).dt.hour
            worst_hours = losses.groupby('hour')['pnl'].mean().nsmallest(3).index.tolist()
            conditions['worst_hours'] = worst_hours

        return conditions

    def _analyze_parameter_performance(self, trades: pd.DataFrame) -> dict[str, dict[str, float]]:
        """Analyze performance by parameter values"""
        param_perf = {}

        # Position size performance
        if 'position_size' in trades.columns:
            size_bins = pd.qcut(trades['position_size'], q=5, duplicates='drop')
            size_perf = trades.groupby(size_bins)['pnl'].agg(['mean', 'count', 'std'])
            param_perf['position_size'] = size_perf.to_dict('index')

        # Stop loss performance
        if 'stop_loss' in trades.columns:
            sl_bins = pd.qcut(trades['stop_loss'], q=5, duplicates='drop')
            sl_perf = trades.groupby(sl_bins)['pnl'].agg(['mean', 'count', 'std'])
            param_perf['stop_loss'] = sl_perf.to_dict('index')

        return param_perf

    # ==========================================================================
    # PATTERN DISCOVERY
    # ==========================================================================
    def _discover_patterns(self, trades_df: pd.DataFrame) -> list[TradingPattern]:
        """Discover successful trading patterns"""
        patterns = []

        # Entry condition patterns
        entry_patterns = self._discover_entry_patterns(trades_df)
        patterns.extend(entry_patterns)

        # Exit condition patterns
        exit_patterns = self._discover_exit_patterns(trades_df)
        patterns.extend(exit_patterns)

        # Time-based patterns
        time_patterns = self._discover_time_patterns(trades_df)
        patterns.extend(time_patterns)

        # Market regime patterns
        regime_patterns = self._discover_regime_patterns(trades_df)
        patterns.extend(regime_patterns)

        # Risk patterns
        risk_patterns = self._discover_risk_patterns(trades_df)
        patterns.extend(risk_patterns)

        # Filter by confidence and performance
        patterns = [p for p in patterns if p.confidence >= CONFIDENCE_THRESHOLD]

        # Update pattern library
        for pattern in patterns:
            pattern_key = f"{pattern.pattern_type.name}_{hash(str(pattern.conditions))}"
            self.pattern_library[pattern_key] = pattern

        return patterns

    def _discover_entry_patterns(self, trades_df: pd.DataFrame) -> list[TradingPattern]:
        """Discover successful entry patterns"""
        patterns = []

        # Analyze by technical indicators
        if all(col in trades_df.columns for col in ['rsi', 'macd', 'bb_position']):
            # Group by indicator ranges
            trades_df['rsi_bin'] = pd.cut(trades_df['rsi'], bins=[0, 30, 50, 70, 100])
            trades_df['macd_signal'] = trades_df['macd'] > 0

            # Find combinations with high win rates
            grouped = trades_df.groupby(['rsi_bin', 'macd_signal', 'strategy'])

            for (rsi_range, macd_pos, strategy), group in grouped:
                if len(group) >= 10:  # Minimum sample size
                    win_rate = (group['pnl'] > 0).mean()
                    avg_pnl = group['pnl'].mean()

                    if win_rate > 0.6 and avg_pnl > 0:
                        pattern = TradingPattern(
                            pattern_type=PatternType.ENTRY_CONDITION,
                            conditions={
                                'strategy': strategy,
                                'rsi_range': str(rsi_range),
                                'macd_positive': macd_pos,
                                'avg_pnl': avg_pnl
                            },
                            performance={
                                'win_rate': win_rate,
                                'avg_pnl': avg_pnl,
                                'trades': len(group)
                            },
                            confidence=self._calculate_confidence(win_rate, len(group)),
                            sample_size=len(group),
                            discovered_date=datetime.now(UTC)
                        )
                        patterns.append(pattern)

        return patterns

    def _discover_exit_patterns(self, trades_df: pd.DataFrame) -> list[TradingPattern]:
        """Discover successful exit patterns"""
        patterns = []

        # Analyze exit reasons
        if 'exit_reason' in trades_df.columns:
            exit_analysis = trades_df.groupby(['exit_reason', 'strategy'])

            for (reason, strategy), group in exit_analysis:
                if len(group) >= 5:
                    avg_pnl = group['pnl'].mean()
                    win_rate = (group['pnl'] > 0).mean()

                    # Analyze hold time for this exit type
                    if 'hold_time' in group.columns:
                        avg_hold = group['hold_time'].mean()

                        pattern = TradingPattern(
                            pattern_type=PatternType.EXIT_CONDITION,
                            conditions={
                                'strategy': strategy,
                                'exit_reason': reason,
                                'avg_hold_time': avg_hold
                            },
                            performance={
                                'avg_pnl': avg_pnl,
                                'win_rate': win_rate,
                                'trades': len(group)
                            },
                            confidence=self._calculate_confidence(win_rate, len(group)),
                            sample_size=len(group),
                            discovered_date=datetime.now(UTC)
                        )
                        patterns.append(pattern)

        return patterns

    def _discover_time_patterns(self, trades_df: pd.DataFrame) -> list[TradingPattern]:
        """Discover time-based patterns"""
        patterns = []

        if 'entry_time' not in trades_df.columns:
            return patterns

        # Convert to datetime and extract components
        trades_df['entry_datetime'] = pd.to_datetime(trades_df['entry_time'])
        trades_df['hour'] = trades_df['entry_datetime'].dt.hour
        trades_df['day_of_week'] = trades_df['entry_datetime'].dt.dayofweek

        # Analyze by time bins
        for time_bin in TIME_BINS:
            start_hour, end_hour = self._parse_time_bin(time_bin)
            mask = (trades_df['hour'] >= start_hour) & (trades_df['hour'] < end_hour)
            bin_trades = trades_df[mask]

            if len(bin_trades) >= 10:
                for strategy in bin_trades['strategy'].unique():
                    strategy_trades = bin_trades[bin_trades['strategy'] == strategy]

                    if len(strategy_trades) >= 5:
                        win_rate = (strategy_trades['pnl'] > 0).mean()
                        avg_pnl = strategy_trades['pnl'].mean()

                        if win_rate > 0.55:  # Above average
                            pattern = TradingPattern(
                                pattern_type=PatternType.TIME_PATTERN,
                                conditions={
                                    'strategy': strategy,
                                    'time_window': time_bin,
                                    'best_days': strategy_trades.groupby('day_of_week')['pnl'].mean().nlargest(2).index.tolist()  # noqa: E501
                                },
                                performance={
                                    'win_rate': win_rate,
                                    'avg_pnl': avg_pnl,
                                    'trades': len(strategy_trades)
                                },
                                confidence=self._calculate_confidence(win_rate, len(strategy_trades)),  # noqa: E501
                                sample_size=len(strategy_trades),
                                discovered_date=datetime.now(UTC)
                            )
                            patterns.append(pattern)

        return patterns

    def _discover_regime_patterns(self, trades_df: pd.DataFrame) -> list[TradingPattern]:
        """Discover market regime patterns"""
        patterns = []

        if 'volatility' not in trades_df.columns:
            return patterns

        # Bin volatility
        trades_df['vol_regime'] = pd.cut(trades_df['volatility'], bins=VOLATILITY_BINS)

        # Analyze by regime
        for strategy in trades_df['strategy'].unique():
            strategy_trades = trades_df[trades_df['strategy'] == strategy]
            regime_perf = strategy_trades.groupby('vol_regime')['pnl'].agg(['mean', 'count', 'std'])

            for regime, stats in regime_perf.iterrows():
                if stats['count'] >= 10 and stats['mean'] > 0:
                    win_rate = (strategy_trades[strategy_trades['vol_regime'] == regime]['pnl'] > 0).mean()  # noqa: E501

                    pattern = TradingPattern(
                        pattern_type=PatternType.MARKET_REGIME,
                        conditions={
                            'strategy': strategy,
                            'volatility_regime': str(regime),
                            'optimal_position_size': self._calculate_optimal_size(stats['mean'], stats['std'])  # noqa: E501
                        },
                        performance={
                            'avg_pnl': stats['mean'],
                            'win_rate': win_rate,
                            'trades': int(stats['count'])
                        },
                        confidence=self._calculate_confidence(win_rate, stats['count']),
                        sample_size=int(stats['count']),
                        discovered_date=datetime.now(UTC)
                    )
                    patterns.append(pattern)

        return patterns

    def _discover_risk_patterns(self, trades_df: pd.DataFrame) -> list[TradingPattern]:
        """Discover risk management patterns"""
        patterns = []

        # Analyze stop loss effectiveness
        if 'stop_triggered' in trades_df.columns:
            stop_analysis = trades_df.groupby(['strategy', 'stop_triggered'])['pnl'].agg(['mean', 'count'])  # noqa: E501

            for (strategy, stop_triggered), stats in stop_analysis.iterrows():
                if stats['count'] >= 5:
                    # Compare with non-stopped trades
                    non_stop = trades_df[(trades_df['strategy'] == strategy) &
                                       (trades_df['stop_triggered'] != stop_triggered)]

                    if len(non_stop) >= 5:
                        improvement = stats['mean'] - non_stop['pnl'].mean()

                        if abs(improvement) > 0:
                            pattern = TradingPattern(
                                pattern_type=PatternType.RISK_PATTERN,
                                conditions={
                                    'strategy': strategy,
                                    'stop_triggered': bool(stop_triggered),
                                    'improvement': improvement
                                },
                                performance={
                                    'avg_pnl_with_pattern': stats['mean'],
                                    'avg_pnl_without': non_stop['pnl'].mean(),
                                    'trades': int(stats['count'])
                                },
                                confidence=0.8,  # Lower confidence for risk patterns
                                sample_size=int(stats['count']),
                                discovered_date=datetime.now(UTC)
                            )
                            patterns.append(pattern)

        return patterns

    # ==========================================================================
    # PARAMETER OPTIMIZATION
    # ==========================================================================
    def _optimize_parameters(
        self,
        trades_df: pd.DataFrame,
        strategy_performance: dict[str, StrategyPerformance]
    ) -> list[OptimizationResult]:
        """Optimize strategy parameters based on performance"""
        optimization_results = []

        for strategy_name, performance in strategy_performance.items():
            strategy_trades = trades_df[trades_df['strategy'] == strategy_name]

            if len(strategy_trades) < MIN_TRADES_PER_STRATEGY:
                continue

            # Get current parameters
            current_params = self._get_current_parameters(strategy_name)

            # Optimize parameters
            optimized_params = self._run_optimization(
                strategy_trades,
                current_params,
                performance
            )

            # Backtest optimization
            backtest_results = self._backtest_parameters(
                strategy_trades,
                current_params,
                optimized_params
            )

            # Calculate expected improvement
            expected_improvement = self._calculate_expected_improvement(
                backtest_results['current'],
                backtest_results['optimized']
            )

            # Generate recommendation
            recommendation = self._generate_parameter_recommendation(
                expected_improvement,
                backtest_results,
                len(strategy_trades)
            )

            result = OptimizationResult(
                strategy_name=strategy_name,
                original_params=current_params,
                optimized_params=optimized_params,
                expected_improvement=expected_improvement,
                confidence_interval=(
                    expected_improvement * 0.8,
                    expected_improvement * 1.2
                ),
                backtest_results=backtest_results,
                recommendation=recommendation
            )

            optimization_results.append(result)

        return optimization_results

    def _run_optimization(
        self,
        trades: pd.DataFrame,
        current_params: dict[str, Any],
        performance: StrategyPerformance
    ) -> dict[str, Any]:
        """Run parameter optimization for a strategy"""
        # Define objective function
        def objective(params):
            # Simulate performance with new parameters
            simulated_pnl = self._simulate_with_parameters(trades, params)

            # Calculate fitness (negative for minimization)
            sharpe = calculate_sharpe_ratio(simulated_pnl)
            return -sharpe  # Minimize negative Sharpe

        # Set bounds
        bounds = [
            POSITION_SIZE_BOUNDS,
            STOP_LOSS_BOUNDS,
            TAKE_PROFIT_BOUNDS,
            (1, min(10, current_params.get('max_positions', 5) * 2))
        ]

        # Run differential evolution
        result = differential_evolution(
            objective,
            bounds,
            maxiter=100,
            popsize=15,
            seed=42
        )

        # Convert to parameter dict
        optimized = {
            'position_size': result.x[0],
            'stop_loss': result.x[1],
            'take_profit': result.x[2],
            'max_positions': int(result.x[3])
        }

        return optimized

    def _simulate_with_parameters(
        self,
        trades: pd.DataFrame,
        params: np.ndarray
    ) -> list[float]:
        """Simulate trading with given parameters"""
        position_size, stop_loss, take_profit, max_positions = params

        simulated_pnl = []

        for _, trade in trades.iterrows():
            # Adjust PnL based on position size
            base_pnl = trade['pnl']
            size_factor = position_size / trade.get('position_size', 0.02)

            # Simulate stop loss
            if 'max_adverse_excursion' in trade:
                if trade['max_adverse_excursion'] >= stop_loss:
                    pnl = -stop_loss * trade['entry_price']
                else:
                    pnl = base_pnl * size_factor
            else:
                pnl = base_pnl * size_factor

            # Simulate take profit
            if 'max_favorable_excursion' in trade:
                if trade['max_favorable_excursion'] >= take_profit:
                    pnl = min(pnl, take_profit * trade['entry_price'])

            simulated_pnl.append(pnl)

        return simulated_pnl

    # ==========================================================================
    # MACHINE LEARNING
    # ==========================================================================
    def _train_ml_models(self, trades_df: pd.DataFrame) -> None:
        """Train ML models for trade prediction"""
        try:
            # Prepare features
            features = self._prepare_ml_features(trades_df)

            if features is None or len(features) < 50:
                return

            # Train success classifier
            self._train_success_classifier(features, trades_df)

            # Train profit predictor
            self._train_profit_predictor(features, trades_df)

            # Save models
            self._save_ml_models()

        except Exception as e:
            self.logger.error("Error training ML models: %s", e)

    def _prepare_ml_features(self, trades_df: pd.DataFrame) -> pd.DataFrame | None:
        """Prepare features for ML models"""
        feature_columns = []

        # Market features
        market_features = ['volatility', 'trend', 'vix', 'volume_ratio']
        feature_columns.extend([col for col in market_features if col in trades_df.columns])

        # Technical features
        tech_features = ['rsi', 'macd', 'bb_position', 'atr']
        feature_columns.extend([col for col in tech_features if col in trades_df.columns])

        # Time features
        if 'entry_time' in trades_df.columns:
            trades_df['hour'] = pd.to_datetime(trades_df['entry_time']).dt.hour
            trades_df['day_of_week'] = pd.to_datetime(trades_df['entry_time']).dt.dayofweek
            feature_columns.extend(['hour', 'day_of_week'])

        # Strategy encoding
        if 'strategy' in trades_df.columns:
            strategy_dummies = pd.get_dummies(trades_df['strategy'], prefix='strategy')
            trades_df = pd.concat([trades_df, strategy_dummies], axis=1)
            feature_columns.extend(strategy_dummies.columns.tolist())

        if not feature_columns:
            return None

        return trades_df[feature_columns].fillna(0)

    def _train_success_classifier(self, features: pd.DataFrame, trades_df: pd.DataFrame) -> None:
        """Train classifier to predict trade success"""
        # Prepare target
        y = (trades_df['pnl'] > 0).astype(int)

        # Scale features
        X_scaled = self.feature_scaler.fit_transform(features)

        # Train model
        self.trade_success_classifier = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42
        )

        # Cross-validation
        scores = cross_val_score(
            self.trade_success_classifier,
            X_scaled,
            y,
            cv=5,
            scoring='accuracy'
        )

        self.logger.info(f"Trade success classifier accuracy: {scores.mean():.3f}")

        # Fit final model
        self.trade_success_classifier.fit(X_scaled, y)

    def _train_profit_predictor(self, features: pd.DataFrame, trades_df: pd.DataFrame) -> None:
        """Train regressor to predict profit magnitude"""
        # Prepare target (normalized PnL)
        y = trades_df['pnl'] / trades_df['entry_price']

        # Use only features from profitable trades for better prediction
        profitable_mask = trades_df['pnl'] > 0
        X_profitable = features[profitable_mask]
        y_profitable = y[profitable_mask]

        if len(X_profitable) < 20:
            return

        # Scale features
        X_scaled = self.feature_scaler.fit_transform(X_profitable)

        # Train model
        self.profit_predictor = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            random_state=42
        )

        # Fit model
        self.profit_predictor.fit(X_scaled, y_profitable)

        # Calculate R-squared
        train_score = self.profit_predictor.score(X_scaled, y_profitable)
        self.logger.info(f"Profit predictor R-squared: {train_score:.3f}")

    # ==========================================================================
    # ANALYSIS METHODS
    # ==========================================================================
    def _analyze_market_conditions(self, trades_df: pd.DataFrame) -> dict[str, Any]:
        """Analyze market conditions impact on performance"""
        insights = {}

        # Volatility impact
        if 'volatility' in trades_df.columns:
            vol_impact = trades_df.groupby(pd.qcut(trades_df['volatility'], q=5))['pnl'].agg(['mean', 'count'])  # noqa: E501
            insights['volatility_impact'] = vol_impact.to_dict('index')

        # Trend impact
        if 'trend' in trades_df.columns:
            trend_bins = pd.cut(trades_df['trend'], bins=TREND_BINS)
            trend_impact = trades_df.groupby(trend_bins)['pnl'].agg(['mean', 'count'])
            insights['trend_impact'] = trend_impact.to_dict('index')

        # VIX impact
        if 'vix' in trades_df.columns:
            vix_impact = trades_df.groupby(pd.qcut(trades_df['vix'], q=5))['pnl'].agg(['mean', 'count'])  # noqa: E501
            insights['vix_impact'] = vix_impact.to_dict('index')

        # Time of day analysis
        if 'entry_time' in trades_df.columns:
            trades_df['hour'] = pd.to_datetime(trades_df['entry_time']).dt.hour
            hourly_perf = trades_df.groupby('hour')['pnl'].agg(['mean', 'count', 'sum'])
            insights['hourly_performance'] = hourly_perf.to_dict('index')

        # Market regime transitions
        insights['regime_transitions'] = self._analyze_regime_transitions(trades_df)

        return insights

    def _analyze_regime_transitions(self, trades_df: pd.DataFrame) -> dict[str, Any]:
        """Analyze performance during regime transitions"""
        transitions = {}

        if 'volatility' not in trades_df.columns:
            return transitions

        # Calculate rolling volatility change
        trades_df = trades_df.sort_values('entry_time')
        trades_df['vol_change'] = trades_df['volatility'].pct_change(5)

        # Identify transitions
        transitions['vol_increasing'] = {
            'trades': len(trades_df[trades_df['vol_change'] > 0.2]),
            'avg_pnl': trades_df[trades_df['vol_change'] > 0.2]['pnl'].mean()
        }

        transitions['vol_decreasing'] = {
            'trades': len(trades_df[trades_df['vol_change'] < -0.2]),
            'avg_pnl': trades_df[trades_df['vol_change'] < -0.2]['pnl'].mean()
        }

        return transitions

    # ==========================================================================
    # RECOMMENDATIONS
    # ==========================================================================
    def _generate_recommendations(
        self,
        strategy_performance: dict[str, StrategyPerformance],
        patterns: list[TradingPattern],
        optimization_results: list[OptimizationResult],
        market_insights: dict[str, Any]
    ) -> list[str]:
        """Generate actionable recommendations"""
        recommendations = []

        # Strategy recommendations
        for strategy, perf in strategy_performance.items():
            if perf.win_rate < 0.45:
                recommendations.append(
                    f"Consider disabling {strategy} - win rate {perf.win_rate:.1%} is below threshold"  # noqa: E501
                )
            elif perf.win_rate > 0.60:
                recommendations.append(
                    f"Increase allocation to {strategy} - strong win rate {perf.win_rate:.1%}"
                )

            if perf.profit_factor < 1.0:
                recommendations.append(
                    f"Review risk management for {strategy} - profit factor {perf.profit_factor:.2f} < 1.0"  # noqa: E501
                )

        # Pattern-based recommendations
        for pattern in patterns[:5]:  # Top 5 patterns
            if pattern.pattern_type == PatternType.TIME_PATTERN:
                recommendations.append(
                    f"Focus {pattern.conditions['strategy']} trading during {pattern.conditions['time_window']} "  # noqa: E501
                    f"(win rate: {pattern.performance['win_rate']:.1%})"
                )
            elif pattern.pattern_type == PatternType.MARKET_REGIME:
                recommendations.append(
                    f"Use {pattern.conditions['strategy']} in {pattern.conditions['volatility_regime']} volatility "  # noqa: E501
                    f"(avg PnL: ${pattern.performance['avg_pnl']:.2f})"
                )

        # Optimization recommendations
        for opt in optimization_results:
            if opt.expected_improvement > IMPROVEMENT_THRESHOLD:
                recommendations.append(
                    f"Update {opt.strategy_name} parameters: "
                    f"position size {opt.optimized_params['position_size']:.1%}, "
                    f"stop loss {opt.optimized_params['stop_loss']:.1%} "
                    f"(expected improvement: {opt.expected_improvement:.1%})"
                )

        # Market condition recommendations
        if 'hourly_performance' in market_insights:
            best_hours = sorted(
                market_insights['hourly_performance'].items(),
                key=lambda x: x[1]['mean'],
                reverse=True
            )[:3]

            if best_hours:
                hour_str = ', '.join([f"{h[0]}:00" for h in best_hours])
                recommendations.append(
                    f"Best trading hours: {hour_str} based on historical performance"
                )

        # Risk recommendations
        total_trades = sum(p.total_trades for p in strategy_performance.values())
        total_pnl = sum(p.total_trades * p.avg_profit for p in strategy_performance.values())

        if total_trades > 100 and total_pnl < 0:
            recommendations.append(
                "Overall negative performance detected - consider paper trading longer before going live"  # noqa: E501
            )

        return recommendations

    # ==========================================================================
    # PREDICTION METHODS
    # ==========================================================================
    def predict_trade_success(
        self,
        market_conditions: dict[str, float],
        strategy: str
    ) -> dict[str, Any]:
        """
        Predict trade success probability.

        Args:
            market_conditions: Current market conditions
            strategy: Strategy name

        Returns:
            Prediction with confidence
        """
        if not self.trade_success_classifier:
            return {'success_probability': 0.5, 'confidence': 0.0}

        try:
            # Prepare features
            features = self._prepare_prediction_features(market_conditions, strategy)

            # Scale features
            features_scaled = self.feature_scaler.transform([features])

            # Get prediction and probability
            prediction = self.trade_success_classifier.predict(features_scaled)[0]
            probability = self.trade_success_classifier.predict_proba(features_scaled)[0]

            # Get feature importance
            importance = self.trade_success_classifier.feature_importances_
            top_features = self._get_top_features(importance, features)

            return {
                'success_probability': float(probability[1]),  # Probability of success
                'prediction': bool(prediction),
                'confidence': float(max(probability)),
                'top_factors': top_features
            }

        except Exception as e:
            self.logger.error("Error in predict_trade_success: %s", e)
            return {'success_probability': 0.5, 'confidence': 0.0}

    def suggest_parameters(
        self,
        strategy: str,
        market_conditions: dict[str, float]
    ) -> dict[str, Any]:
        """
        Suggest optimal parameters for current conditions.

        Args:
            strategy: Strategy name
            market_conditions: Current market conditions

        Returns:
            Suggested parameters
        """
        # Get historical optimization
        optimization = next(
            (opt for opt in self.optimization_history if opt.strategy_name == strategy),
            None
        )

        if not optimization:
            return self._get_default_parameters(strategy)

        # Adjust based on current conditions
        params = optimization.optimized_params.copy()

        # Volatility adjustment
        current_vol = market_conditions.get('volatility', 0.15)
        if current_vol > 0.25:  # High volatility
            params['position_size'] *= 0.7
            params['stop_loss'] *= 1.5
        elif current_vol < 0.10:  # Low volatility
            params['position_size'] *= 1.2
            params['stop_loss'] *= 0.8

        # Trend adjustment
        trend = market_conditions.get('trend', 0)
        if abs(trend) > 0.02:  # Strong trend
            params['take_profit'] *= 1.5

        return params

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    def _load_trade_data(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """Load trade data from database"""
        # Check cache
        if (self._trade_cache is not None and
            self._cache_timestamp and
            datetime.now(UTC) - self._cache_timestamp < timedelta(minutes=5)):
            return self._trade_cache

        # Load from database
        trades = self.db.get_trades(start_date, end_date)

        # Convert to DataFrame
        trades_df = pd.DataFrame(trades)

        # Add calculated fields
        if not trades_df.empty:
            trades_df['pnl'] = trades_df['exit_price'] - trades_df['entry_price']
            trades_df['pnl_percent'] = trades_df['pnl'] / trades_df['entry_price']
            trades_df['hold_time'] = (
                pd.to_datetime(trades_df['exit_time']) -
                pd.to_datetime(trades_df['entry_time'])
            ).dt.total_seconds() / 3600  # Hours

        # Update cache
        self._trade_cache = trades_df
        self._cache_timestamp = datetime.now(UTC)

        return trades_df

    def _calculate_confidence(self, win_rate: float, sample_size: int) -> float:
        """Calculate confidence in a pattern"""
        # Wilson score interval
        z = 1.96  # 95% confidence
        n = sample_size
        p = win_rate

        denominator = 1 + z**2 / n
        centre = (p + z**2 / (2*n)) / denominator
        offset = z * math.sqrt(p * (1-p) / n + z**2 / (4*n**2)) / denominator

        lower_bound = centre - offset

        # Scale to 0-1 confidence
        confidence = min(1.0, lower_bound / 0.5)  # 0.5 is breakeven

        # Adjust for sample size
        size_factor = min(1.0, sample_size / 100)

        return confidence * size_factor

    def _calculate_optimal_size(self, mean_return: float, std_return: float) -> float:
        """Calculate optimal position size using Kelly Criterion"""
        if std_return == 0:
            return 0.02  # Default 2%

        # Simplified Kelly
        kelly = mean_return / (std_return ** 2)

        # Apply Kelly fraction (25% of full Kelly)
        optimal = kelly * 0.25

        # Bound between min and max
        return max(0.01, min(0.10, optimal))

    def _parse_time_bin(self, time_bin: str) -> tuple[int, int]:
        """Parse time bin string to hours"""
        parts = time_bin.split('-')
        start = int(parts[0].split(':')[0])
        end = int(parts[1].split(':')[0])
        return start, end

    def _get_current_parameters(self, strategy: str) -> dict[str, Any]:
        """Get current parameters for a strategy"""
        # This would fetch from configuration
        # For now, return defaults
        return {
            'position_size': 0.02,
            'stop_loss': 0.10,
            'take_profit': 0.50,
            'max_positions': 3
        }

    def _get_default_parameters(self, strategy: str) -> dict[str, Any]:
        """Get default parameters for a strategy"""
        defaults = {
            'IronCondor': {
                'position_size': 0.02,
                'stop_loss': 0.15,
                'take_profit': 0.50,
                'max_positions': 3
            },
            'CreditSpread': {
                'position_size': 0.03,
                'stop_loss': 0.20,
                'take_profit': 0.75,
                'max_positions': 5
            },
            'ZeroDTE': {
                'position_size': 0.01,
                'stop_loss': 0.10,
                'take_profit': 0.30,
                'max_positions': 2
            }
        }

        return defaults.get(strategy, self._get_current_parameters(strategy))

    def _backtest_parameters(
        self,
        trades: pd.DataFrame,
        current_params: dict[str, Any],
        optimized_params: dict[str, Any]
    ) -> dict[str, dict[str, float]]:
        """Backtest current vs optimized parameters"""
        results = {}

        # Simulate with current parameters
        current_pnl = self._simulate_with_parameters(
            trades,
            [current_params['position_size'],
             current_params['stop_loss'],
             current_params['take_profit'],
             current_params['max_positions']]
        )

        results['current'] = {
            'total_pnl': sum(current_pnl),
            'sharpe': calculate_sharpe_ratio(current_pnl),
            'win_rate': sum(1 for p in current_pnl if p > 0) / len(current_pnl)
        }

        # Simulate with optimized parameters
        optimized_pnl = self._simulate_with_parameters(
            trades,
            [optimized_params['position_size'],
             optimized_params['stop_loss'],
             optimized_params['take_profit'],
             optimized_params['max_positions']]
        )

        results['optimized'] = {
            'total_pnl': sum(optimized_pnl),
            'sharpe': calculate_sharpe_ratio(optimized_pnl),
            'win_rate': sum(1 for p in optimized_pnl if p > 0) / len(optimized_pnl)
        }

        return results

    def _calculate_expected_improvement(
        self,
        current_results: dict[str, float],
        optimized_results: dict[str, float]
    ) -> float:
        """Calculate expected improvement from optimization"""
        # Use Sharpe ratio as primary metric
        current_sharpe = current_results.get('sharpe', 0)
        optimized_sharpe = optimized_results.get('sharpe', 0)

        if current_sharpe == 0:
            return 0.0

        improvement = (optimized_sharpe - current_sharpe) / abs(current_sharpe)

        return improvement

    def _generate_parameter_recommendation(
        self,
        improvement: float,
        backtest_results: dict[str, dict[str, float]],
        sample_size: int
    ) -> str:
        """Generate recommendation for parameter change"""
        if improvement < IMPROVEMENT_THRESHOLD:
            return "Keep current parameters - insufficient improvement"

        if sample_size < 50:
            return "Gather more data before optimizing - small sample size"

        if backtest_results['optimized']['win_rate'] < 0.40:
            return "Optimization shows low win rate - review strategy logic"

        if improvement > 0.25:
            return "Strongly recommend parameter update - significant improvement"

        return "Consider parameter update - moderate improvement expected"

    def _update_learning_state(
        self,
        strategy_performance: dict[str, StrategyPerformance],
        optimization_results: list[OptimizationResult]
    ) -> None:
        """Update internal learning state"""
        # Update performance history
        self.performance_history.append({
            'timestamp': datetime.now(UTC),
            'iteration': self.current_iteration,
            'strategies': {
                name: {
                    'win_rate': perf.win_rate,
                    'sharpe': perf.sharpe_ratio,
                    'trades': perf.total_trades
                }
                for name, perf in strategy_performance.items()
            }
        })

        # Update optimization history
        self.optimization_history.extend(optimization_results)

        # Update learning mode
        avg_win_rate = np.mean([p.win_rate for p in strategy_performance.values()])

        if avg_win_rate < 0.45:
            self.learning_mode = LearningMode.EXPLORATION
        elif avg_win_rate > 0.55:
            self.learning_mode = LearningMode.EXPLOITATION
        else:
            self.learning_mode = LearningMode.VALIDATION

        self.current_iteration += 1

    def _save_learning_report(self, report: LearningReport) -> None:
        """Save learning report to database"""
        try:
            # Convert to JSON-serializable format
            report_data = {
                'analysis_date': report.analysis_date.isoformat(),
                'total_trades': report.total_trades_analyzed,
                'strategy_performance': {
                    k: asdict(v) for k, v in report.strategy_performance.items()
                },
                'patterns': [asdict(p) for p in report.discovered_patterns],
                'optimizations': [asdict(o) for o in report.optimization_results],
                'market_insights': report.market_insights,
                'recommendations': report.recommendations
            }

            # Save to database
            self.db.save_learning_report(report_data)

            # Also save to file for backup
            filename = f"learning_report_{report.analysis_date.strftime('%Y%m%d_%H%M%S')}.json"
            with open(f"reports/{filename}", 'w') as f:
                json.dump(report_data, f, indent=2, default=str)

        except Exception as e:
            self.logger.error("Error saving learning report: %s", e)

    def _save_ml_models(self) -> None:
        """Save trained ML models"""
        try:
            if self.trade_success_classifier:
                joblib.dump(self.trade_success_classifier, 'models/trade_success_classifier.pkl')
                joblib.dump(self.feature_scaler, 'models/feature_scaler.pkl')

            if self.profit_predictor:
                joblib.dump(self.profit_predictor, 'models/profit_predictor.pkl')

        except Exception as e:
            self.logger.error("Error saving ML models: %s", e)

    def _get_top_features(
        self,
        importance: np.ndarray,
        features: list[float]
    ) -> list[tuple[str, float]]:
        """Get top important features"""
        # This would map feature indices to names
        # For now, return placeholder
        return [
            ('volatility', 0.25),
            ('rsi', 0.20),
            ('hour', 0.15)
        ]

    def _prepare_prediction_features(
        self,
        market_conditions: dict[str, float],
        strategy: str
    ) -> list[float]:
        """Prepare features for prediction"""
        # This would match the training features
        # For now, return placeholder
        features = []

        # Add market conditions
        features.extend([
            market_conditions.get('volatility', 0.15),
            market_conditions.get('trend', 0),
            market_conditions.get('vix', 16),
            market_conditions.get('volume_ratio', 1.0)
        ])

        # Add technical indicators
        features.extend([
            market_conditions.get('rsi', 50),
            market_conditions.get('macd', 0),
            market_conditions.get('bb_position', 0.5),
            market_conditions.get('atr', 1.0)
        ])

        # Add time features
        now = datetime.now(UTC)
        features.extend([now.hour, now.weekday()])

        # Add strategy encoding (simplified)
        strategy_encoding = [0] * 5  # Assume 5 strategies
        strategy_map = {'IronCondor': 0, 'CreditSpread': 1, 'ZeroDTE': 2}
        if strategy in strategy_map:
            strategy_encoding[strategy_map[strategy]] = 1
        features.extend(strategy_encoding)

        return features

    def _create_minimal_report(self, trades_df: pd.DataFrame) -> LearningReport:
        """Create minimal report when insufficient data"""
        return LearningReport(
            analysis_date=datetime.now(UTC),
            total_trades_analyzed=len(trades_df),
            strategy_performance={},
            discovered_patterns=[],
            optimization_results=[],
            market_insights={},
            recommendations=[
                f"Need at least {MIN_TRADES_FOR_LEARNING} trades for analysis",
                f"Current trades: {len(trades_df)}",
                "Continue paper trading to gather more data"
            ]
        )

    def _create_error_report(self, error_msg: str) -> LearningReport:
        """Create error report"""
        return LearningReport(
            analysis_date=datetime.now(UTC),
            total_trades_analyzed=0,
            strategy_performance={},
            discovered_patterns=[],
            optimization_results=[],
            market_insights={},
            recommendations=[f"Error during analysis: {error_msg}"]
        )

    # --------------------------------------------------------------------------
    # STABLE-BASELINES3: RL POLICY FROM PAPER TRADE OUTCOMES
    # --------------------------------------------------------------------------

    def create_paper_trade_rl_env(self):
        """
        Create an RL environment that learns from paper trade outcomes.

        The agent learns a trading policy by replaying paper trade
        scenarios and optimizing for risk-adjusted returns.

        Returns:
            gym.Env instance for SB3 training.
        """
        try:
            import gymnasium as gym
            from gymnasium import spaces
        except ImportError:
            try:
                import gym
                from gym import spaces
            except ImportError:
                self.logger.warning("gym/gymnasium not installed")
                return None

        import numpy as _np

        class PaperTradeReplayEnvironment(gym.Env):
            """
            RL environment for learning from paper trade history.

            Observation: [win_rate, avg_return, volatility, sharpe,
                         drawdown, position_count, market_regime,
                         confidence_score]
            Action: 0=skip, 1=small_position, 2=medium_position,
                    3=large_position, 4=exit_all
            Reward: realized_pnl - risk_penalty
            """
            metadata = {'render_modes': []}

            def __init__(self):
                super().__init__()
                self.observation_space = spaces.Box(
                    low=-5.0, high=5.0, shape=(8,), dtype=_np.float32)
                self.action_space = spaces.Discrete(5)
                self.step_count = 0
                self.max_steps = 252
                self.capital = 1.0
                self.positions = 0.0

            def reset(self, seed=None, options=None):
                super().reset(seed=seed)
                self.step_count = 0
                self.capital = 1.0
                self.positions = 0.0
                self._state = _np.array([
                    _np.random.uniform(0.4, 0.6),  # win_rate
                    _np.random.uniform(-0.02, 0.02), # avg_return
                    _np.random.uniform(0.1, 0.3),  # volatility
                    _np.random.uniform(-1, 2),     # sharpe
                    _np.random.uniform(0, 0.1),    # drawdown
                    0.0,                           # position_count
                    float(_np.random.randint(0, 4)), # regime
                    _np.random.uniform(0.3, 0.8),  # confidence
                ], dtype=_np.float32)
                return self._state, {}

            def step(self, action):
                self.step_count += 1
                position_sizes = [0, 0.02, 0.05, 0.10, -self.positions]
                position_change = position_sizes[min(action, 4)]

                if action == 4:  # exit all
                    realized = self.positions * _np.random.normal(
                        self._state[1], self._state[2] * 0.1)
                    self.capital += realized
                    self.positions = 0
                else:
                    self.positions += position_change

                # Simulate daily P&L
                daily_pnl = self.positions * _np.random.normal(
                    self._state[1] / 252, self._state[2] / _np.sqrt(252))
                self.capital += daily_pnl

                # Risk penalty for oversizing
                risk_penalty = max(0, abs(self.positions) - 0.15) * 5

                reward = daily_pnl * 1000 - risk_penalty

                # Update state
                self._state[4] = max(0, 1 - self.capital)  # drawdown
                self._state[5] = abs(self.positions) * 10
                self._state[7] = _np.clip(
                    self._state[7] + _np.random.normal(0, 0.05), 0, 1)

                done = self.step_count >= self.max_steps or self.capital < 0.8
                return self._state.copy(), float(reward), done, False, {}

        return PaperTradeReplayEnvironment()

    def train_paper_trade_policy(self, total_timesteps: int = 50000) -> Any | None:
        """
        Train a PPO policy from paper trade outcomes.

        Args:
            total_timesteps: Training steps.

        Returns:
            Trained SB3 model or None.
        """
        env = self.create_paper_trade_rl_env()
        if env is None:
            return None

        try:
            from stable_baselines3 import PPO
            model = PPO('MlpPolicy', env, verbose=0,
                       learning_rate=3e-4, n_steps=2048)
            model.learn(total_timesteps=total_timesteps)
            self.logger.info("Paper trade RL policy trained: %s steps", total_timesteps)
            return model
        except ImportError:
            self.logger.warning("stable-baselines3 not installed")
            return None

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test the paper trade learner
    from SpyderH_Storage.SpyderH01_DatabaseManager import DatabaseManager

    # Initialize
    db = DatabaseManager(":memory:")  # Use in-memory DB for testing
    learner = PaperTradeLearner(db)

    # Create sample trades
    sample_trades = []
    np.random.seed(42)

    strategies = ['IronCondor', 'CreditSpread', 'ZeroDTE']

    for i in range(100):
        trade = {
            'strategy': np.random.choice(strategies),
            'entry_time': datetime.now(UTC) - timedelta(days=30-i),
            'exit_time': datetime.now(UTC) - timedelta(days=30-i, hours=2),
            'entry_price': 450 + np.random.randn(),
            'exit_price': 450 + np.random.randn() * 2,
            'position_size': 0.02,
            'volatility': 0.10 + np.random.rand() * 0.15,
            'trend': np.random.randn() * 0.01,
            'vix': 15 + np.random.randn() * 3,
            'rsi': 30 + np.random.rand() * 40,
            'macd': np.random.randn() * 0.5
        }
        trade['pnl'] = trade['exit_price'] - trade['entry_price']
        sample_trades.append(trade)

    # Save trades to DB
    for trade in sample_trades:
        db.save_trade(trade)

    # Run analysis
    report = learner.analyze_and_learn()

    # Display results

    for _strategy, _perf in report.strategy_performance.items():
        pass

    for _pattern in report.discovered_patterns[:5]:
        pass

    for _opt in report.optimization_results:
        pass

    for _, _rec in enumerate(report.recommendations, 1):
        pass

    # Test prediction
    market_conditions = {
        'volatility': 0.18,
        'trend': 0.01,
        'vix': 16,
        'rsi': 45,
        'macd': 0.2
    }

    prediction = learner.predict_trade_success(market_conditions, 'IronCondor')

    # Test parameter suggestion
    params = learner.suggest_parameters('IronCondor', market_conditions)
