#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderH07_PerformanceAnalytics.py
Group: H (Data Storage)
Purpose: Comprehensive performance analytics and reporting

Description:
    This module provides advanced performance analytics for the trading system,
    including strategy-specific metrics, time-based analysis, risk-adjusted
    returns, and comparative performance evaluation. It integrates with the
    trade repository to analyze historical performance and generate insights
    for strategy optimization.

Author: Mohamed Talib
Date: 2025-06-01
Version: 1.4
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
import warnings

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from scipy import stats
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.dates import DateFormatter

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU03_DateTimeUtils import TradingCalendar
from SpyderH_Storage.SpyderH02_TradeRepository import TradeRepository, Trade
from SpyderE_Risk.SpyderE06_RiskMetrics import RiskMetricsCalculator

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Time periods for analysis
DAILY = 'D'
WEEKLY = 'W'
MONTHLY = 'M'
QUARTERLY = 'Q'
YEARLY = 'Y'

# Performance thresholds
MIN_TRADES_FOR_STATISTICS = 30
SIGNIFICANCE_LEVEL = 0.05
RISK_FREE_RATE = 0.02  # 2% annual

# Analysis periods
LOOKBACK_DAYS = {
    'short': 30,
    'medium': 90,
    'long': 252,
    'all': None
}

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics"""
    # Basic metrics
    total_return: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    
    # Profitability metrics
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    net_profit: float = 0.0
    profit_factor: float = 0.0
    average_win: float = 0.0
    average_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    
    # Risk metrics
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0
    var_95: float = 0.0
    cvar_95: float = 0.0
    
    # Consistency metrics
    win_rate_consistency: float = 0.0
    monthly_win_rate: float = 0.0
    profit_consistency: float = 0.0
    
    # Time-based metrics
    trades_per_day: float = 0.0
    average_trade_duration: float = 0.0
    time_in_market: float = 0.0
    
    # Additional metrics
    expectancy: float = 0.0
    kelly_criterion: float = 0.0
    recovery_factor: float = 0.0
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary"""
        return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}

@dataclass
class TimeAnalysis:
    """Time-based performance analysis"""
    # Hour of day analysis
    hourly_performance: Dict[int, float] = field(default_factory=dict)
    hourly_win_rate: Dict[int, float] = field(default_factory=dict)
    hourly_trade_count: Dict[int, int] = field(default_factory=dict)
    
    # Day of week analysis
    daily_performance: Dict[str, float] = field(default_factory=dict)
    daily_win_rate: Dict[str, float] = field(default_factory=dict)
    daily_trade_count: Dict[str, int] = field(default_factory=dict)
    
    # Monthly analysis
    monthly_returns: Dict[str, float] = field(default_factory=dict)
    monthly_sharpe: Dict[str, float] = field(default_factory=dict)
    
    # Best/worst periods
    best_hour: Optional[int] = None
    worst_hour: Optional[int] = None
    best_day: Optional[str] = None
    worst_day: Optional[str] = None
    best_month: Optional[str] = None
    worst_month: Optional[str] = None

@dataclass
class StrategyPerformance:
    """Strategy-specific performance data"""
    strategy_name: str
    metrics: PerformanceMetrics
    time_analysis: TimeAnalysis
    trade_distribution: Dict[str, Any] = field(default_factory=dict)
    parameter_performance: Dict[str, Any] = field(default_factory=dict)
    market_regime_performance: Dict[str, float] = field(default_factory=dict)

# ==============================================================================
# PERFORMANCE ANALYTICS CLASS
# ==============================================================================
class PerformanceAnalytics:
    """
    Comprehensive performance analytics for trading strategies.
    
    This class provides detailed performance analysis including:
    - Strategy-specific metrics
    - Time-based performance patterns
    - Risk-adjusted returns
    - Comparative analysis
    - Statistical significance testing
    """
    
    def __init__(self, trade_repository: TradeRepository):
        """
        Initialize performance analytics.
        
        Args:
            trade_repository: Trade data repository
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.trade_repository = trade_repository
        self.calendar = TradingCalendar()
        self.risk_calculator = RiskMetricsCalculator()
        
        # Cache for performance data
        self._cache = {}
        self._cache_timestamp = None
        self._cache_duration = datetime.timedelta(minutes=5)
        
        self.logger.info("PerformanceAnalytics initialized")
    
    # ==========================================================================
    # PUBLIC METHODS - PERFORMANCE CALCULATION
    # ==========================================================================
    
    def calculate_performance(
        self,
        strategy: Optional[str] = None,
        start_date: Optional[datetime.date] = None,
        end_date: Optional[datetime.date] = None,
        include_time_analysis: bool = True
    ) -> Union[StrategyPerformance, Dict[str, StrategyPerformance]]:
        """
        Calculate comprehensive performance metrics.
        
        Args:
            strategy: Specific strategy name or None for all
            start_date: Start date for analysis
            end_date: End date for analysis
            include_time_analysis: Include time-based analysis
            
        Returns:
            Performance data for strategy or all strategies
        """
        try:
            # Check cache
            cache_key = f"{strategy}_{start_date}_{end_date}"
            if self._is_cache_valid(cache_key):
                return self._cache[cache_key]
            
            # Get trades
            trades = self._get_trades(strategy, start_date, end_date)
            
            if not trades:
                self.logger.warning(f"No trades found for {strategy or 'all strategies'}")
                return {} if strategy is None else None
            
            # Calculate performance
            if strategy:
                performance = self._calculate_strategy_performance(
                    strategy, trades, include_time_analysis
                )
                result = performance
            else:
                # Calculate for all strategies
                strategies = self._get_unique_strategies(trades)
                result = {}
                
                for strat in strategies:
                    strat_trades = [t for t in trades if t.strategy == strat]
                    performance = self._calculate_strategy_performance(
                        strat, strat_trades, include_time_analysis
                    )
                    result[strat] = performance
            
            # Cache result
            self._cache[cache_key] = result
            self._cache_timestamp = datetime.datetime.now()
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error calculating performance: {e}")
            self.error_handler.handle_error(e)
            return {} if strategy is None else None
    
    def calculate_rolling_performance(
        self,
        strategy: str,
        window_days: int = 30,
        step_days: int = 1
    ) -> pd.DataFrame:
        """
        Calculate rolling performance metrics.
        
        Args:
            strategy: Strategy name
            window_days: Rolling window size
            step_days: Step size between windows
            
        Returns:
            DataFrame with rolling metrics
        """
        try:
            # Get all trades
            trades = self._get_trades(strategy)
            if not trades:
                return pd.DataFrame()
            
            # Sort by exit time
            trades.sort(key=lambda x: x.exit_time)
            
            # Determine date range
            start_date = trades[0].exit_time.date()
            end_date = trades[-1].exit_time.date()
            
            # Calculate rolling windows
            results = []
            current_date = start_date
            
            while current_date <= end_date - datetime.timedelta(days=window_days):
                window_end = current_date + datetime.timedelta(days=window_days)
                
                # Get trades in window
                window_trades = [
                    t for t in trades
                    if current_date <= t.exit_time.date() <= window_end
                ]
                
                if window_trades:
                    # Calculate metrics
                    metrics = self._calculate_basic_metrics(window_trades)
                    
                    results.append({
                        'date': window_end,
                        'total_return': metrics.total_return,
                        'win_rate': metrics.win_rate,
                        'sharpe_ratio': metrics.sharpe_ratio,
                        'max_drawdown': metrics.max_drawdown,
                        'trade_count': metrics.total_trades,
                        'net_profit': metrics.net_profit
                    })
                
                current_date += datetime.timedelta(days=step_days)
            
            return pd.DataFrame(results)
            
        except Exception as e:
            self.logger.error(f"Error calculating rolling performance: {e}")
            return pd.DataFrame()
    
    def analyze_parameter_performance(
        self,
        strategy: str,
        parameter_name: str,
        bins: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Analyze performance by strategy parameter values.
        
        Args:
            strategy: Strategy name
            parameter_name: Parameter to analyze
            bins: Number of bins for continuous parameters
            
        Returns:
            DataFrame with parameter performance analysis
        """
        try:
            trades = self._get_trades(strategy)
            if not trades:
                return pd.DataFrame()
            
            # Extract parameter values
            param_data = defaultdict(list)
            
            for trade in trades:
                if trade.metadata and parameter_name in trade.metadata:
                    param_value = trade.metadata[parameter_name]
                    param_data[param_value].append(trade)
            
            if not param_data:
                self.logger.warning(f"No parameter data found for {parameter_name}")
                return pd.DataFrame()
            
            # Calculate metrics for each parameter value
            results = []
            
            for value, value_trades in param_data.items():
                if len(value_trades) >= 5:  # Minimum trades for statistics
                    metrics = self._calculate_basic_metrics(value_trades)
                    
                    results.append({
                        parameter_name: value,
                        'trade_count': len(value_trades),
                        'win_rate': metrics.win_rate,
                        'avg_profit': metrics.net_profit / len(value_trades),
                        'profit_factor': metrics.profit_factor,
                        'sharpe_ratio': metrics.sharpe_ratio,
                        'total_return': metrics.total_return
                    })
            
            df = pd.DataFrame(results)
            df.sort_values(parameter_name, inplace=True)
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error analyzing parameter performance: {e}")
            return pd.DataFrame()
    
    # ==========================================================================
    # PRIVATE METHODS - CALCULATION HELPERS
    # ==========================================================================
    
    def _calculate_strategy_performance(
        self,
        strategy: str,
        trades: List[Trade],
        include_time_analysis: bool
    ) -> StrategyPerformance:
        """Calculate performance for a specific strategy"""
        # Basic metrics
        metrics = self._calculate_basic_metrics(trades)
        
        # Advanced metrics
        metrics = self._calculate_advanced_metrics(trades, metrics)
        
        # Time analysis
        time_analysis = TimeAnalysis()
        if include_time_analysis:
            time_analysis = self._calculate_time_analysis(trades)
        
        # Trade distribution
        trade_distribution = self._calculate_trade_distribution(trades)
        
        # Create performance object
        performance = StrategyPerformance(
            strategy_name=strategy,
            metrics=metrics,
            time_analysis=time_analysis,
            trade_distribution=trade_distribution
        )
        
        return performance
    
    def _calculate_basic_metrics(self, trades: List[Trade]) -> PerformanceMetrics:
        """Calculate basic performance metrics"""
        metrics = PerformanceMetrics()
        
        if not trades:
            return metrics
        
        # Basic counts
        metrics.total_trades = len(trades)
        metrics.winning_trades = sum(1 for t in trades if t.profit > 0)
        metrics.losing_trades = sum(1 for t in trades if t.profit <= 0)
        metrics.win_rate = metrics.winning_trades / metrics.total_trades if metrics.total_trades > 0 else 0
        
        # Profit metrics
        winning_trades = [t for t in trades if t.profit > 0]
        losing_trades = [t for t in trades if t.profit <= 0]
        
        metrics.gross_profit = sum(t.profit for t in winning_trades)
        metrics.gross_loss = abs(sum(t.profit for t in losing_trades))
        metrics.net_profit = metrics.gross_profit - metrics.gross_loss
        
        # Average metrics
        metrics.average_win = metrics.gross_profit / len(winning_trades) if winning_trades else 0
        metrics.average_loss = metrics.gross_loss / len(losing_trades) if losing_trades else 0
        
        # Extremes
        all_profits = [t.profit for t in trades]
        metrics.largest_win = max(all_profits) if all_profits else 0
        metrics.largest_loss = min(all_profits) if all_profits else 0
        
        # Profit factor
        metrics.profit_factor = (
            metrics.gross_profit / metrics.gross_loss 
            if metrics.gross_loss > 0 else float('inf')
        )
        
        # Expectancy
        metrics.expectancy = (
            (metrics.win_rate * metrics.average_win) - 
            ((1 - metrics.win_rate) * metrics.average_loss)
        )
        
        return metrics
    
    def _calculate_advanced_metrics(
        self,
        trades: List[Trade],
        metrics: PerformanceMetrics
    ) -> PerformanceMetrics:
        """Calculate advanced risk-adjusted metrics"""
        if len(trades) < MIN_TRADES_FOR_STATISTICS:
            return metrics
        
        # Create equity curve
        equity_curve = self._create_equity_curve(trades)
        if equity_curve.empty:
            return metrics
        
        # Calculate returns
        returns = equity_curve.pct_change().dropna()
        
        # Risk metrics
        if len(returns) > 0:
            # Sharpe ratio
            excess_returns = returns - RISK_FREE_RATE / 252  # Daily risk-free rate
            metrics.sharpe_ratio = (
                np.sqrt(252) * excess_returns.mean() / returns.std()
                if returns.std() > 0 else 0
            )
            
            # Sortino ratio
            downside_returns = returns[returns < 0]
            if len(downside_returns) > 0:
                downside_std = downside_returns.std()
                metrics.sortino_ratio = (
                    np.sqrt(252) * excess_returns.mean() / downside_std
                    if downside_std > 0 else 0
                )
            
            # Maximum drawdown
            drawdown_data = self._calculate_drawdown(equity_curve)
            metrics.max_drawdown = drawdown_data['max_drawdown']
            metrics.max_drawdown_duration = drawdown_data['max_duration']
            
            # Calmar ratio
            annual_return = returns.mean() * 252
            metrics.calmar_ratio = (
                annual_return / abs(metrics.max_drawdown)
                if metrics.max_drawdown != 0 else 0
            )
            
            # VaR and CVaR
            metrics.var_95 = np.percentile(returns, 5)
            metrics.cvar_95 = returns[returns <= metrics.var_95].mean()
            
            # Recovery factor
            metrics.recovery_factor = (
                metrics.net_profit / abs(metrics.max_drawdown)
                if metrics.max_drawdown != 0 else 0
            )
        
        # Kelly criterion
        if metrics.average_loss > 0:
            b = metrics.average_win / metrics.average_loss
            p = metrics.win_rate
            q = 1 - p
            metrics.kelly_criterion = (p * b - q) / b if b > 0 else 0
            metrics.kelly_criterion = max(0, min(0.25, metrics.kelly_criterion))  # Cap at 25%
        
        # Time metrics
        metrics.trades_per_day = self._calculate_trades_per_day(trades)
        metrics.average_trade_duration = self._calculate_average_duration(trades)
        
        return metrics
    
    def _calculate_time_analysis(self, trades: List[Trade]) -> TimeAnalysis:
        """Analyze performance by time periods"""
        analysis = TimeAnalysis()
        
        # Hour of day analysis
        hourly_data = defaultdict(lambda: {'profit': 0, 'count': 0, 'wins': 0})
        
        for trade in trades:
            hour = trade.entry_time.hour
            hourly_data[hour]['profit'] += trade.profit
            hourly_data[hour]['count'] += 1
            if trade.profit > 0:
                hourly_data[hour]['wins'] += 1
        
        # Process hourly data
        for hour, data in hourly_data.items():
            analysis.hourly_performance[hour] = data['profit']
            analysis.hourly_trade_count[hour] = data['count']
            analysis.hourly_win_rate[hour] = (
                data['wins'] / data['count'] if data['count'] > 0 else 0
            )
        
        # Find best/worst hours
        if analysis.hourly_performance:
            analysis.best_hour = max(
                analysis.hourly_performance.items(),
                key=lambda x: x[1]
            )[0]
            analysis.worst_hour = min(
                analysis.hourly_performance.items(),
                key=lambda x: x[1]
            )[0]
        
        # Day of week analysis
        daily_data = defaultdict(lambda: {'profit': 0, 'count': 0, 'wins': 0})
        
        for trade in trades:
            day_name = trade.exit_time.strftime('%A')
            daily_data[day_name]['profit'] += trade.profit
            daily_data[day_name]['count'] += 1
            if trade.profit > 0:
                daily_data[day_name]['wins'] += 1
        
        # Process daily data
        for day, data in daily_data.items():
            analysis.daily_performance[day] = data['profit']
            analysis.daily_trade_count[day] = data['count']
            analysis.daily_win_rate[day] = (
                data['wins'] / data['count'] if data['count'] > 0 else 0
            )
        
        # Find best/worst days
        if analysis.daily_performance:
            analysis.best_day = max(
                analysis.daily_performance.items(),
                key=lambda x: x[1]
            )[0]
            analysis.worst_day = min(
                analysis.daily_performance.items(),
                key=lambda x: x[1]
            )[0]
        
        # Monthly analysis
        monthly_trades = defaultdict(list)
        
        for trade in trades:
            month_key = trade.exit_time.strftime('%Y-%m')
            monthly_trades[month_key].append(trade)
        
        for month, month_trades in monthly_trades.items():
            month_profit = sum(t.profit for t in month_trades)
            analysis.monthly_returns[month] = month_profit
            
            # Calculate monthly Sharpe if enough trades
            if len(month_trades) >= 20:
                equity_curve = self._create_equity_curve(month_trades)
                if not equity_curve.empty:
                    returns = equity_curve.pct_change().dropna()
                    if len(returns) > 0 and returns.std() > 0:
                        analysis.monthly_sharpe[month] = (
                            np.sqrt(252) * returns.mean() / returns.std()
                        )
        
        # Find best/worst months
        if analysis.monthly_returns:
            analysis.best_month = max(
                analysis.monthly_returns.items(),
                key=lambda x: x[1]
            )[0]
            analysis.worst_month = min(
                analysis.monthly_returns.items(),
                key=lambda x: x[1]
            )[0]
        
        return analysis
    
    def _calculate_trade_distribution(self, trades: List[Trade]) -> Dict[str, Any]:
        """Calculate trade distribution statistics"""
        if not trades:
            return {}
        
        profits = [t.profit for t in trades]
        
        distribution = {
            'mean': np.mean(profits),
            'median': np.median(profits),
            'std': np.std(profits),
            'skew': stats.skew(profits),
            'kurtosis': stats.kurtosis(profits),
            'percentiles': {
                '5%': np.percentile(profits, 5),
                '25%': np.percentile(profits, 25),
                '50%': np.percentile(profits, 50),
                '75%': np.percentile(profits, 75),
                '95%': np.percentile(profits, 95)
            }
        }
        
        # Profit bins
        bins = np.linspace(min(profits), max(profits), 11)
        hist, bin_edges = np.histogram(profits, bins=bins)
        
        distribution['histogram'] = {
            'counts': hist.tolist(),
            'bins': bin_edges.tolist()
        }
        
        return distribution
    
    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    
    def _get_trades(
        self,
        strategy: Optional[str] = None,
        start_date: Optional[datetime.date] = None,
        end_date: Optional[datetime.date] = None
    ) -> List[Trade]:
        """Get trades from repository"""
        return self.trade_repository.get_trades(
            strategy=strategy,
            start_date=start_date,
            end_date=end_date
        )
    
    def _get_unique_strategies(self, trades: List[Trade]) -> List[str]:
        """Get unique strategy names from trades"""
        return list(set(t.strategy for t in trades))
    
    def _create_equity_curve(self, trades: List[Trade]) -> pd.Series:
        """Create equity curve from trades"""
        if not trades:
            return pd.Series()
        
        # Sort trades by exit time
        sorted_trades = sorted(trades, key=lambda x: x.exit_time)
        
        # Create cumulative profit series
        dates = [t.exit_time for t in sorted_trades]
        cumulative_profit = np.cumsum([t.profit for t in sorted_trades])
        
        # Assume starting capital of 100,000
        starting_capital = 100000
        equity_values = starting_capital + cumulative_profit
        
        equity_curve = pd.Series(equity_values, index=dates)
        
        return equity_curve
    
    def _calculate_drawdown(self, equity_curve: pd.Series) -> Dict[str, Any]:
        """Calculate drawdown statistics"""
        if equity_curve.empty:
            return {'max_drawdown': 0, 'max_duration': 0}
        
        # Calculate running maximum
        running_max = equity_curve.expanding().max()
        
        # Calculate drawdown
        drawdown = (equity_curve - running_max) / running_max
        
        # Find maximum drawdown
        max_drawdown = abs(drawdown.min())
        
        # Calculate drawdown duration
        drawdown_start = None
        max_duration = 0
        current_duration = 0
        
        for date, dd in drawdown.items():
            if dd < 0:
                if drawdown_start is None:
                    drawdown_start = date
                current_duration = (date - drawdown_start).days
                max_duration = max(max_duration, current_duration)
            else:
                drawdown_start = None
                current_duration = 0
        
        return {
            'max_drawdown': max_drawdown,
            'max_duration': max_duration
        }
    
    def _calculate_trades_per_day(self, trades: List[Trade]) -> float:
        """Calculate average trades per trading day"""
        if not trades:
            return 0.0
        
        # Get date range
        start_date = min(t.entry_time.date() for t in trades)
        end_date = max(t.exit_time.date() for t in trades)
        
        # Count trading days
        trading_days = self.calendar.count_trading_days(start_date, end_date)
        
        return len(trades) / trading_days if trading_days > 0 else 0.0
    
    def _calculate_average_duration(self, trades: List[Trade]) -> float:
        """Calculate average trade duration in minutes"""
        if not trades:
            return 0.0
        
        durations = []
        for trade in trades:
            duration = (trade.exit_time - trade.entry_time).total_seconds() / 60
            durations.append(duration)
        
        return np.mean(durations)
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache is valid"""
        if cache_key not in self._cache:
            return False
        
        if self._cache_timestamp is None:
            return False
        
        age = datetime.datetime.now() - self._cache_timestamp
        return age < self._cache_duration
    
    # ==========================================================================
    # VISUALIZATION METHODS
    # ==========================================================================
    
    def plot_equity_curve(
        self,
        strategy: str,
        start_date: Optional[datetime.date] = None,
        end_date: Optional[datetime.date] = None,
        save_path: Optional[str] = None
    ) -> None:
        """Plot equity curve for strategy"""
        trades = self._get_trades(strategy, start_date, end_date)
        if not trades:
            self.logger.warning(f"No trades to plot for {strategy}")
            return
        
        equity_curve = self._create_equity_curve(trades)
        
        plt.figure(figsize=(12, 6))
        plt.plot(equity_curve.index, equity_curve.values, linewidth=2)
        plt.title(f'Equity Curve - {strategy}')
        plt.xlabel('Date')
        plt.ylabel('Equity ($)')
        plt.grid(True, alpha=0.3)
        
        # Format x-axis
        plt.gca().xaxis.set_major_formatter(DateFormatter('%Y-%m-%d'))
        plt.xticks(rotation=45)
        
        # Add drawdown visualization
        running_max = equity_curve.expanding().max()
        drawdown = (equity_curve - running_max) / running_max * 100
        
        ax2 = plt.gca().twinx()
        ax2.fill_between(drawdown.index, 0, drawdown.values, 
                        color='red', alpha=0.3, label='Drawdown')
        ax2.set_ylabel('Drawdown (%)')
        ax2.legend(loc='lower left')
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path)
        else:
            plt.show()
    
    def plot_performance_comparison(
        self,
        strategies: List[str],
        metric: str = 'cumulative_return',
        save_path: Optional[str] = None
    ) -> None:
        """Plot performance comparison between strategies"""
        plt.figure(figsize=(12, 8))
        
        for strategy in strategies:
            trades = self._get_trades(strategy)
            if not trades:
                continue
            
            equity_curve = self._create_equity_curve(trades)
            
            if metric == 'cumulative_return':
                values = (equity_curve / equity_curve.iloc[0] - 1) * 100
                ylabel = 'Cumulative Return (%)'
            elif metric == 'drawdown':
                running_max = equity_curve.expanding().max()
                values = (equity_curve - running_max) / running_max * 100
                ylabel = 'Drawdown (%)'
            else:
                values = equity_curve
                ylabel = 'Equity ($)'
            
            plt.plot(values.index, values.values, label=strategy, linewidth=2)
        
        plt.title(f'Strategy Comparison - {metric.replace("_", " ").title()}')
        plt.xlabel('Date')
        plt.ylabel(ylabel)
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        # Format x-axis
        plt.gca().xaxis.set_major_formatter(DateFormatter('%Y-%m-%d'))
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path)
        else:
            plt.show()
    
    def plot_time_analysis(
        self,
        strategy: str,
        analysis_type: str = 'hourly',
        save_path: Optional[str] = None
    ) -> None:
        """Plot time-based performance analysis"""
        performance = self.calculate_performance(strategy)
        if not performance:
            return
        
        time_analysis = performance.time_analysis
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
        
        if analysis_type == 'hourly':
            # Hourly performance
            hours = sorted(time_analysis.hourly_performance.keys())
            profits = [time_analysis.hourly_performance[h] for h in hours]
            win_rates = [time_analysis.hourly_win_rate[h] * 100 for h in hours]
            
            ax1.bar(hours, profits, alpha=0.7, color='blue')
            ax1.set_xlabel('Hour of Day')
            ax1.set_ylabel('Total Profit ($)')
            ax1.set_title(f'{strategy} - Hourly Performance')
            ax1.grid(True, alpha=0.3)
            
            ax2.plot(hours, win_rates, marker='o', color='green', linewidth=2)
            ax2.set_xlabel('Hour of Day')
            ax2.set_ylabel('Win Rate (%)')
            ax2.set_title(f'{strategy} - Hourly Win Rate')
            ax2.grid(True, alpha=0.3)
            ax2.set_ylim(0, 100)
            
        elif analysis_type == 'daily':
            # Daily performance
            days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
            profits = [time_analysis.daily_performance.get(d, 0) for d in days]
            win_rates = [time_analysis.daily_win_rate.get(d, 0) * 100 for d in days]
            
            ax1.bar(days, profits, alpha=0.7, color='blue')
            ax1.set_xlabel('Day of Week')
            ax1.set_ylabel('Total Profit ($)')
            ax1.set_title(f'{strategy} - Daily Performance')
            ax1.grid(True, alpha=0.3)
            
            ax2.plot(days, win_rates, marker='o', color='green', linewidth=2)
            ax2.set_xlabel('Day of Week')
            ax2.set_ylabel('Win Rate (%)')
            ax2.set_title(f'{strategy} - Daily Win Rate')
            ax2.grid(True, alpha=0.3)
            ax2.set_ylim(0, 100)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path)
        else:
            plt.show()
    
    # ==========================================================================
    # REPORTING METHODS
    # ==========================================================================
    
    def generate_performance_report(
        self,
        strategy: Optional[str] = None,
        output_format: str = 'dict'
    ) -> Union[Dict, str]:
        """
        Generate comprehensive performance report.
        
        Args:
            strategy: Strategy name or None for all
            output_format: 'dict', 'json', or 'text'
            
        Returns:
            Performance report in requested format
        """
        performance = self.calculate_performance(strategy)
        
        if output_format == 'dict':
            return self._format_report_dict(performance)
        elif output_format == 'json':
            return json.dumps(self._format_report_dict(performance), indent=2)
        elif output_format == 'text':
            return self._format_report_text(performance)
        else:
            raise ValueError(f"Unknown output format: {output_format}")
    
    def _format_report_dict(
        self,
        performance: Union[StrategyPerformance, Dict[str, StrategyPerformance]]
    ) -> Dict:
        """Format performance data as dictionary"""
        if isinstance(performance, StrategyPerformance):
            return {
                'strategy': performance.strategy_name,
                'metrics': performance.metrics.to_dict(),
                'time_analysis': {
                    'hourly_performance': performance.time_analysis.hourly_performance,
                    'daily_performance': performance.time_analysis.daily_performance,
                    'best_hour': performance.time_analysis.best_hour,
                    'best_day': performance.time_analysis.best_day
                },
                'trade_distribution': performance.trade_distribution
            }
        else:
            # Multiple strategies
            return {
                name: self._format_report_dict(perf)
                for name, perf in performance.items()
            }
    
    def _format_report_text(
        self,
        performance: Union[StrategyPerformance, Dict[str, StrategyPerformance]]
    ) -> str:
        """Format performance data as text report"""
        lines = ["=" * 80]
        lines.append("PERFORMANCE ANALYTICS REPORT")
        lines.append("=" * 80)
        lines.append(f"Generated: {datetime.datetime.now()}")
        lines.append("")
        
        if isinstance(performance, StrategyPerformance):
            strategies = [performance]
        else:
            strategies = list(performance.values())
        
        for perf in strategies:
            lines.append(f"\nSTRATEGY: {perf.strategy_name}")
            lines.append("-" * 40)
            
            metrics = perf.metrics
            
            # Basic metrics
            lines.append(f"Total Trades: {metrics.total_trades}")
            lines.append(f"Win Rate: {metrics.win_rate:.1%}")
            lines.append(f"Profit Factor: {metrics.profit_factor:.2f}")
            lines.append(f"Net Profit: ${metrics.net_profit:,.2f}")
            
            # Risk metrics
            lines.append(f"\nRisk Metrics:")
            lines.append(f"  Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
            lines.append(f"  Sortino Ratio: {metrics.sortino_ratio:.2f}")
            lines.append(f"  Max Drawdown: {metrics.max_drawdown:.1%}")
            lines.append(f"  VaR (95%): ${metrics.var_95:.2f}")
            
            # Time analysis
            if perf.time_analysis.best_day:
                lines.append(f"\nTime Analysis:")
                lines.append(f"  Best Day: {perf.time_analysis.best_day}")
                lines.append(f"  Worst Day: {perf.time_analysis.worst_day}")
                lines.append(f"  Best Hour: {perf.time_analysis.best_hour}:00")
                lines.append(f"  Worst Hour: {perf.time_analysis.worst_hour}:00")
            
            lines.append("")
        
        lines.append("=" * 80)
        
        return "\n".join(lines)

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_performance_analytics(trade_repository: TradeRepository) -> PerformanceAnalytics:
    """
    Factory function to create PerformanceAnalytics instance.
    
    Args:
        trade_repository: Trade repository instance
        
    Returns:
        PerformanceAnalytics instance
    """
    return PerformanceAnalytics(trade_repository)

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Example usage
    from SpyderH_Storage.SpyderH02_TradeRepository import get_trade_repository
    
    # Get repository
    repo = get_trade_repository()
    
    # Create analytics
    analytics = create_performance_analytics(repo)
    
    # Calculate performance for all strategies
    performance = analytics.calculate_performance()
    
    # Generate report
    report = analytics.generate_performance_report(output_format='text')
    print(report)
    
    # Plot equity curves
    for strategy in performance.keys():
        analytics.plot_equity_curve(strategy)
