#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderE06_RiskMetrics.py
Group: E (Risk Management)
Purpose: Risk metrics calculation (Sharpe, etc.)

Description:
    This module calculates comprehensive risk metrics for trading performance
    evaluation. It provides real-time and historical risk analytics including
    Sharpe ratio, Sortino ratio, maximum drawdown, Value at Risk (VaR),
    and other essential risk measurements used for portfolio management
    and strategy evaluation.

Author: Mohamed Talib
Date: 2025-06-01
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import deque
import numpy as np
import pandas as pd
from scipy import stats
import math

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU07_Constants import TRADING_DAYS_PER_YEAR

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Risk-free rate (annual)
DEFAULT_RISK_FREE_RATE = 0.02  # 2%

# Calculation periods
DAILY_PERIOD = 1
WEEKLY_PERIOD = 5
MONTHLY_PERIOD = 21
YEARLY_PERIOD = TRADING_DAYS_PER_YEAR

# Risk thresholds
MAX_ACCEPTABLE_DRAWDOWN = 0.20  # 20%
MIN_ACCEPTABLE_SHARPE = 1.0
MAX_ACCEPTABLE_VAR = 0.05  # 5%

# Rolling window sizes
DEFAULT_WINDOW_SIZE = 252  # 1 year of trading days
SHORT_WINDOW = 20  # 1 month
MEDIUM_WINDOW = 60  # 3 months

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class RiskMetrics:
    """Comprehensive risk metrics"""
    timestamp: datetime
    total_return: float
    annualized_return: float
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    current_drawdown: float
    var_95: float
    cvar_95: float
    calmar_ratio: float
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    consecutive_wins: int
    consecutive_losses: int
    recovery_factor: float
    risk_of_ruin: float
    kelly_criterion: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PortfolioRisk:
    """Portfolio-level risk metrics"""
    timestamp: datetime
    portfolio_value: float
    at_risk_capital: float
    leverage_ratio: float
    concentration_risk: float
    correlation_risk: float
    beta: float
    alpha: float
    r_squared: float
    tracking_error: float
    information_ratio: float
    treynor_ratio: float

@dataclass
class StrategyRisk:
    """Strategy-specific risk metrics"""
    strategy_name: str
    allocated_capital: float
    current_exposure: float
    position_count: int
    avg_position_size: float
    largest_position: float
    sector_concentration: float
    time_in_market: float
    risk_adjusted_return: float

# ==============================================================================
# STANDALONE FUNCTIONS
# ==============================================================================
def calculate_sharpe_ratio(returns: List[float], risk_free_rate: float = DEFAULT_RISK_FREE_RATE) -> float:
    """Calculate Sharpe ratio"""
    if not returns or len(returns) < 2:
        return 0.0
    
    mean_return = np.mean(returns)
    std_return = np.std(returns, ddof=1)
    
    if std_return == 0:
        return 0.0
    
    # Annualize
    annual_return = mean_return * TRADING_DAYS_PER_YEAR
    annual_std = std_return * np.sqrt(TRADING_DAYS_PER_YEAR)
    
    return (annual_return - risk_free_rate) / annual_std

def calculate_sortino_ratio(returns: List[float], risk_free_rate: float = DEFAULT_RISK_FREE_RATE) -> float:
    """Calculate Sortino ratio (uses downside deviation)"""
    if not returns or len(returns) < 2:
        return 0.0
    
    mean_return = np.mean(returns)
    downside_returns = [r for r in returns if r < 0]
    
    if not downside_returns:
        return float('inf') if mean_return > 0 else 0.0
    
    downside_std = np.std(downside_returns, ddof=1)
    
    if downside_std == 0:
        return 0.0
    
    # Annualize
    annual_return = mean_return * TRADING_DAYS_PER_YEAR
    annual_downside = downside_std * np.sqrt(TRADING_DAYS_PER_YEAR)
    
    return (annual_return - risk_free_rate) / annual_downside

def calculate_max_drawdown(equity_curve: List[float]) -> Tuple[float, int, int]:
    """Calculate maximum drawdown and peak/trough indices"""
    if not equity_curve or len(equity_curve) < 2:
        return 0.0, 0, 0
    
    peak = equity_curve[0]
    peak_idx = 0
    max_dd = 0.0
    max_dd_peak_idx = 0
    max_dd_trough_idx = 0
    
    for i, value in enumerate(equity_curve):
        if value > peak:
            peak = value
            peak_idx = i
        
        dd = (peak - value) / peak if peak > 0 else 0
        
        if dd > max_dd:
            max_dd = dd
            max_dd_peak_idx = peak_idx
            max_dd_trough_idx = i
    
    return max_dd, max_dd_peak_idx, max_dd_trough_idx

def calculate_var(returns: List[float], confidence_level: float = 0.95) -> float:
    """Calculate Value at Risk"""
    if not returns:
        return 0.0
    
    return np.percentile(returns, (1 - confidence_level) * 100)

def calculate_cvar(returns: List[float], confidence_level: float = 0.95) -> float:
    """Calculate Conditional Value at Risk (Expected Shortfall)"""
    if not returns:
        return 0.0
    
    var = calculate_var(returns, confidence_level)
    conditional_returns = [r for r in returns if r <= var]
    
    return np.mean(conditional_returns) if conditional_returns else var

# ==============================================================================
# RISK METRICS CALCULATOR CLASS
# ==============================================================================
class RiskMetricsCalculator:
    """
    Calculates comprehensive risk metrics for trading strategies.
    
    Features:
    - Real-time risk calculations
    - Historical performance analysis
    - Multi-timeframe metrics
    - Portfolio and strategy-level analytics
    - Risk-adjusted return measures
    """
    
    def __init__(self, risk_free_rate: float = DEFAULT_RISK_FREE_RATE):
        """
        Initialize risk metrics calculator.
        
        Args:
            risk_free_rate: Annual risk-free rate
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        self.risk_free_rate = risk_free_rate
        
        # Data storage
        self.returns_history: deque = deque(maxlen=DEFAULT_WINDOW_SIZE * 2)
        self.equity_history: deque = deque(maxlen=DEFAULT_WINDOW_SIZE * 2)
        self.trade_history: List[Dict[str, Any]] = []
        
        # Cached calculations
        self._cache: Dict[str, Tuple[Any, datetime]] = {}
        self._cache_ttl = timedelta(minutes=5)
        
        self.logger.info("RiskMetricsCalculator initialized")
    
    # ==========================================================================
    # PUBLIC METHODS - CORE CALCULATIONS
    # ==========================================================================
    def calculate_metrics(self, returns: List[float], 
                         equity_curve: Optional[List[float]] = None,
                         trades: Optional[List[Dict[str, Any]]] = None) -> RiskMetrics:
        """
        Calculate comprehensive risk metrics.
        
        Args:
            returns: List of period returns
            equity_curve: List of equity values
            trades: List of trade dictionaries
            
        Returns:
            RiskMetrics object
        """
        if not returns:
            return self._empty_metrics()
        
        # Convert to numpy arrays
        returns_array = np.array(returns)
        
        # Basic statistics
        total_return = self._calculate_total_return(returns_array)
        annualized_return = self._annualize_return(np.mean(returns_array))
        volatility = self._annualize_volatility(np.std(returns_array, ddof=1))
        
        # Risk-adjusted returns
        sharpe = calculate_sharpe_ratio(returns, self.risk_free_rate)
        sortino = calculate_sortino_ratio(returns, self.risk_free_rate)
        
        # Drawdown analysis
        if equity_curve:
            max_dd, peak_idx, trough_idx = calculate_max_drawdown(equity_curve)
            current_dd = self._calculate_current_drawdown(equity_curve)
        else:
            max_dd = current_dd = 0.0
        
        # Value at Risk
        var_95 = calculate_var(returns, 0.95)
        cvar_95 = calculate_cvar(returns, 0.95)
        
        # Trade statistics
        trade_stats = self._calculate_trade_statistics(trades) if trades else {}
        
        # Additional metrics
        calmar = self._calculate_calmar_ratio(annualized_return, max_dd)
        recovery = self._calculate_recovery_factor(total_return, max_dd)
        kelly = self._calculate_kelly_criterion(trade_stats)
        risk_of_ruin = self._calculate_risk_of_ruin(trade_stats, volatility)
        
        return RiskMetrics(
            timestamp=datetime.now(),
            total_return=total_return,
            annualized_return=annualized_return,
            volatility=volatility,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=max_dd,
            current_drawdown=current_dd,
            var_95=var_95,
            cvar_95=cvar_95,
            calmar_ratio=calmar,
            win_rate=trade_stats.get('win_rate', 0),
            profit_factor=trade_stats.get('profit_factor', 0),
            avg_win=trade_stats.get('avg_win', 0),
            avg_loss=trade_stats.get('avg_loss', 0),
            largest_win=trade_stats.get('largest_win', 0),
            largest_loss=trade_stats.get('largest_loss', 0),
            consecutive_wins=trade_stats.get('consecutive_wins', 0),
            consecutive_losses=trade_stats.get('consecutive_losses', 0),
            recovery_factor=recovery,
            risk_of_ruin=risk_of_ruin,
            kelly_criterion=kelly
        )
    
    def calculate_portfolio_risk(self, positions: List[Dict[str, Any]], 
                               portfolio_value: float,
                               benchmark_returns: Optional[List[float]] = None) -> PortfolioRisk:
        """
        Calculate portfolio-level risk metrics.
        
        Args:
            positions: List of position dictionaries
            portfolio_value: Total portfolio value
            benchmark_returns: Benchmark return series
            
        Returns:
            PortfolioRisk object
        """
        # Portfolio composition
        at_risk_capital = sum(p.get('market_value', 0) for p in positions)
        leverage = at_risk_capital / portfolio_value if portfolio_value > 0 else 0
        
        # Concentration risk
        position_values = [abs(p.get('market_value', 0)) for p in positions]
        concentration = max(position_values) / portfolio_value if position_values and portfolio_value > 0 else 0
        
        # Portfolio Greeks
        portfolio_returns = list(self.returns_history)
        
        # CAPM metrics
        if benchmark_returns and len(portfolio_returns) >= 20:
            beta, alpha, r_squared = self._calculate_capm_metrics(portfolio_returns, benchmark_returns)
            tracking_error = self._calculate_tracking_error(portfolio_returns, benchmark_returns)
            info_ratio = self._calculate_information_ratio(portfolio_returns, benchmark_returns, tracking_error)
            treynor = self._calculate_treynor_ratio(self._annualize_return(np.mean(portfolio_returns)), beta)
        else:
            beta = alpha = r_squared = tracking_error = info_ratio = treynor = 0.0
        
        # Correlation risk
        correlation_risk = self._estimate_correlation_risk(positions)
        
        return PortfolioRisk(
            timestamp=datetime.now(),
            portfolio_value=portfolio_value,
            at_risk_capital=at_risk_capital,
            leverage_ratio=leverage,
            concentration_risk=concentration,
            correlation_risk=correlation_risk,
            beta=beta,
            alpha=alpha,
            r_squared=r_squared,
            tracking_error=tracking_error,
            information_ratio=info_ratio,
            treynor_ratio=treynor
        )
    
    def calculate_strategy_risk(self, strategy_name: str,
                              positions: List[Dict[str, Any]],
                              allocated_capital: float) -> StrategyRisk:
        """
        Calculate strategy-specific risk metrics.
        
        Args:
            strategy_name: Name of the strategy
            positions: Strategy positions
            allocated_capital: Capital allocated to strategy
            
        Returns:
            StrategyRisk object
        """
        # Position analysis
        position_count = len(positions)
        total_exposure = sum(abs(p.get('market_value', 0)) for p in positions)
        
        if position_count > 0:
            avg_position_size = total_exposure / position_count
            largest_position = max(abs(p.get('market_value', 0)) for p in positions)
        else:
            avg_position_size = largest_position = 0
        
        # Sector concentration (simplified)
        sectors = [p.get('sector', 'Unknown') for p in positions]
        if sectors:
            sector_counts = pd.Series(sectors).value_counts()
            sector_concentration = sector_counts.iloc[0] / len(sectors) if len(sector_counts) > 0 else 0
        else:
            sector_concentration = 0
        
        # Time in market
        if positions:
            active_time = sum(1 for p in positions if p.get('status') == 'active')
            time_in_market = active_time / len(positions)
        else:
            time_in_market = 0
        
        # Risk-adjusted return
        strategy_returns = [p.get('return', 0) for p in positions if 'return' in p]
        if strategy_returns:
            risk_adjusted_return = calculate_sharpe_ratio(strategy_returns, self.risk_free_rate)
        else:
            risk_adjusted_return = 0
        
        return StrategyRisk(
            strategy_name=strategy_name,
            allocated_capital=allocated_capital,
            current_exposure=total_exposure,
            position_count=position_count,
            avg_position_size=avg_position_size,
            largest_position=largest_position,
            sector_concentration=sector_concentration,
            time_in_market=time_in_market,
            risk_adjusted_return=risk_adjusted_return
        )
    
    # ==========================================================================
    # PUBLIC METHODS - DATA MANAGEMENT
    # ==========================================================================
    def add_return(self, return_value: float) -> None:
        """Add a return to history"""
        self.returns_history.append(return_value)
        self._invalidate_cache()
    
    def add_equity_point(self, equity_value: float) -> None:
        """Add an equity value to history"""
        self.equity_history.append(equity_value)
        self._invalidate_cache()
    
    def add_trade(self, trade: Dict[str, Any]) -> None:
        """
        Add a trade to history.
        
        Args:
            trade: Trade dictionary with pnl, entry_time, exit_time, etc.
        """
        self.trade_history.append(trade)
        self._invalidate_cache()
    
    # ==========================================================================
    # PUBLIC METHODS - ROLLING CALCULATIONS
    # ==========================================================================
    def get_rolling_metrics(self, window_size: int = DEFAULT_WINDOW_SIZE) -> pd.DataFrame:
        """
        Calculate rolling risk metrics.
        
        Args:
            window_size: Rolling window size
            
        Returns:
            DataFrame with rolling metrics
        """
        if len(self.returns_history) < window_size:
            return pd.DataFrame()
        
        returns_series = pd.Series(list(self.returns_history))
        
        # Calculate rolling metrics
        rolling_data = {
            'return': returns_series.rolling(window_size).mean() * TRADING_DAYS_PER_YEAR,
            'volatility': returns_series.rolling(window_size).std() * np.sqrt(TRADING_DAYS_PER_YEAR),
            'sharpe': returns_series.rolling(window_size).apply(
                lambda x: calculate_sharpe_ratio(x.tolist(), self.risk_free_rate)
            ),
            'var_95': returns_series.rolling(window_size).apply(
                lambda x: calculate_var(x.tolist(), 0.95)
            )
        }
        
        return pd.DataFrame(rolling_data)
    
    # ==========================================================================
    # PRIVATE METHODS - CALCULATIONS
    # ==========================================================================
    def _calculate_total_return(self, returns: np.ndarray) -> float:
        """Calculate total compounded return"""
        return float(np.prod(1 + returns) - 1)
    
    def _annualize_return(self, mean_return: float) -> float:
        """Annualize return"""
        return float((1 + mean_return) ** TRADING_DAYS_PER_YEAR - 1)
    
    def _annualize_volatility(self, std_dev: float) -> float:
        """Annualize volatility"""
        return float(std_dev * np.sqrt(TRADING_DAYS_PER_YEAR))
    
    def _calculate_current_drawdown(self, equity_curve: List[float]) -> float:
        """Calculate current drawdown from peak"""
        if not equity_curve:
            return 0.0
        
        peak = max(equity_curve)
        current = equity_curve[-1]
        
        if peak > 0:
            return float((peak - current) / peak * 100)
        return 0.0
    
    def _calculate_calmar_ratio(self, annual_return: float, max_drawdown: float) -> float:
        """Calculate Calmar ratio"""
        if max_drawdown == 0:
            return 0.0
        return float(annual_return / abs(max_drawdown) * 100)
    
    def _calculate_recovery_factor(self, total_return: float, max_drawdown: float) -> float:
        """Calculate recovery factor"""
        if max_drawdown == 0:
            return float('inf') if total_return > 0 else 0.0
        return float(total_return / abs(max_drawdown))
    
    def _calculate_kelly_criterion(self, trade_stats: Dict[str, float]) -> float:
        """Calculate Kelly criterion for position sizing"""
        win_rate = trade_stats.get('win_rate', 0)
        profit_factor = trade_stats.get('profit_factor', 0)
        
        if profit_factor == 0 or win_rate == 0:
            return 0.0
        
        avg_win = trade_stats.get('avg_win', 0)
        avg_loss = abs(trade_stats.get('avg_loss', 0))
        
        if avg_loss == 0:
            return 0.0
        
        # Kelly formula: (p*b - q) / b
        p = win_rate
        q = 1 - win_rate
        b = avg_win / avg_loss
        
        kelly = (p * b - q) / b
        
        # Cap at 25% (common practice)
        return float(min(kelly, 0.25))
    
    def _calculate_risk_of_ruin(self, trade_stats: Dict[str, float], volatility: float) -> float:
        """Estimate risk of ruin"""
        win_rate = trade_stats.get('win_rate', 0.5)
        
        if win_rate >= 1:
            return 0.0
        if win_rate <= 0:
            return 1.0
        
        # Simplified risk of ruin formula
        if volatility > 0:
            risk_of_ruin = ((1 - win_rate) / win_rate) ** (1 / volatility)
            return float(min(risk_of_ruin, 1.0))
        
        return 0.5
    
    def _calculate_trade_statistics(self, trades: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate trade-based statistics"""
        if not trades:
            return {}
        
        # Extract P&L values
        pnls = [t.get('pnl', 0) for t in trades]
        
        # Win/loss analysis
        wins = [pnl for pnl in pnls if pnl > 0]
        losses = [pnl for pnl in pnls if pnl < 0]
        
        win_rate = len(wins) / len(pnls) if pnls else 0
        
        # Profit factor
        gross_profit = sum(wins) if wins else 0
        gross_loss = abs(sum(losses)) if losses else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        # Average win/loss
        avg_win = np.mean(wins) if wins else 0
        avg_loss = np.mean(losses) if losses else 0
        
        # Largest win/loss
        largest_win = max(pnls) if pnls else 0
        largest_loss = min(pnls) if pnls else 0
        
        # Consecutive wins/losses
        consecutive_wins = self._max_consecutive(pnls, lambda x: x > 0)
        consecutive_losses = self._max_consecutive(pnls, lambda x: x < 0)
        
        return {
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'largest_win': largest_win,
            'largest_loss': largest_loss,
            'consecutive_wins': consecutive_wins,
            'consecutive_losses': consecutive_losses
        }
    
    def _max_consecutive(self, values: List[float], condition: callable) -> int:
        """Calculate maximum consecutive occurrences"""
        max_count = current_count = 0
        
        for value in values:
            if condition(value):
                current_count += 1
                max_count = max(max_count, current_count)
            else:
                current_count = 0
        
        return max_count
    
    def _calculate_capm_metrics(self, portfolio_returns: List[float],
                               benchmark_returns: List[float]) -> Tuple[float, float, float]:
        """Calculate CAPM metrics (beta, alpha, R-squared)"""
        if len(portfolio_returns) != len(benchmark_returns) or len(portfolio_returns) < 2:
            return 0.0, 0.0, 0.0
        
        # Convert to arrays
        y = np.array(portfolio_returns)
        x = np.array(benchmark_returns)
        
        # Add constant for intercept
        x_with_const = np.column_stack([np.ones(len(x)), x])
        
        # Linear regression
        try:
            coeffs, residuals, _, _ = np.linalg.lstsq(x_with_const, y, rcond=None)
            alpha, beta = coeffs
            
            # R-squared
            y_pred = alpha + beta * x
            ss_res = np.sum((y - y_pred) ** 2)
            ss_tot = np.sum((y - np.mean(y)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
            
            # Annualize alpha
            alpha_annual = (1 + alpha) ** TRADING_DAYS_PER_YEAR - 1
            
            return float(beta), float(alpha_annual), float(r_squared)
            
        except Exception:
            return 0.0, 0.0, 0.0
    
    def _calculate_tracking_error(self, portfolio_returns: List[float],
                                 benchmark_returns: List[float]) -> float:
        """Calculate tracking error"""
        if len(portfolio_returns) != len(benchmark_returns) or len(portfolio_returns) < 2:
            return 0.0
        
        # Calculate excess returns
        excess_returns = np.array(portfolio_returns) - np.array(benchmark_returns)
        
        # Annualized tracking error
        return float(np.std(excess_returns, ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR))
    
    def _calculate_information_ratio(self, portfolio_returns: List[float],
                                   benchmark_returns: List[float],
                                   tracking_error: float) -> float:
        """Calculate information ratio"""
        if tracking_error == 0 or len(portfolio_returns) != len(benchmark_returns):
            return 0.0
        
        # Average excess return
        excess_returns = np.array(portfolio_returns) - np.array(benchmark_returns)
        avg_excess = np.mean(excess_returns)
        
        # Annualized information ratio
        return float(avg_excess * TRADING_DAYS_PER_YEAR / tracking_error)
    
    def _calculate_treynor_ratio(self, portfolio_return: float, beta: float) -> float:
        """Calculate Treynor ratio"""
        if beta == 0:
            return 0.0
        
        # Annualized excess return over beta
        excess_return = portfolio_return - self.risk_free_rate / TRADING_DAYS_PER_YEAR
        return float(excess_return * TRADING_DAYS_PER_YEAR / beta)
    
    def _estimate_correlation_risk(self, positions: List[Dict[str, Any]]) -> float:
        """Estimate portfolio correlation risk (simplified)"""
        if len(positions) < 2:
            return 0.0
        
        # Simplified: assume higher correlation risk with fewer positions
        # In practice, would calculate actual correlation matrix
        diversification_factor = 1 / np.sqrt(len(positions))
        
        return float(min(diversification_factor, 1.0))
    
    # ==========================================================================
    # PRIVATE METHODS - UTILITIES
    # ==========================================================================
    def _empty_metrics(self) -> RiskMetrics:
        """Return empty risk metrics"""
        return RiskMetrics(
            timestamp=datetime.now(),
            total_return=0.0,
            annualized_return=0.0,
            volatility=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            max_drawdown=0.0,
            current_drawdown=0.0,
            var_95=0.0,
            cvar_95=0.0,
            calmar_ratio=0.0,
            win_rate=0.0,
            profit_factor=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            largest_win=0.0,
            largest_loss=0.0,
            consecutive_wins=0,
            consecutive_losses=0,
            recovery_factor=0.0,
            risk_of_ruin=0.0,
            kelly_criterion=0.0
        )
    
    def _invalidate_cache(self) -> None:
        """Invalidate cached calculations"""
        self._cache.clear()
    
    def _get_cached(self, key: str) -> Optional[Any]:
        """Get cached value if still valid"""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if datetime.now() - timestamp < self._cache_ttl:
                return value
        return None
    
    def _set_cached(self, key: str, value: Any) -> None:
        """Set cached value"""
        self._cache[key] = (value, datetime.now())


# ==============================================================================
# MODULE TESTING
# ==============================================================================
if __name__ == "__main__":
    # Create calculator
    calculator = RiskMetricsCalculator()
    
    # Generate sample returns
    np.random.seed(42)
    sample_returns = np.random.normal(0.001, 0.02, 252)  # 1 year of daily returns
    
    # Generate equity curve
    equity_curve = [100000]
    for ret in sample_returns:
        equity_curve.append(equity_curve[-1] * (1 + ret))
    
    # Calculate metrics
    metrics = calculator.calculate_metrics(
        returns=sample_returns.tolist(),
        equity_curve=equity_curve
    )
    
    print("Risk Metrics Calculation Test")
    print("=" * 50)
    print(f"Total Return: {metrics.total_return:.2%}")
    print(f"Annualized Return: {metrics.annualized_return:.2%}")
    print(f"Volatility: {metrics.volatility:.2%}")
    print(f"Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
    print(f"Sortino Ratio: {metrics.sortino_ratio:.2f}")
    print(f"Max Drawdown: {metrics.max_drawdown:.2%}")
    print(f"VaR (95%): {metrics.var_95:.2%}")
    print(f"CVaR (95%): {metrics.cvar_95:.2%}")
    
    # Test standalone functions
    print("\nStandalone Function Tests")
    print("=" * 50)
    print(f"Sharpe Ratio: {calculate_sharpe_ratio(sample_returns.tolist()):.2f}")
    print(f"Sortino Ratio: {calculate_sortino_ratio(sample_returns.tolist()):.2f}")
    
    max_dd, peak_idx, trough_idx = calculate_max_drawdown(equity_curve)
    print(f"Max Drawdown: {max_dd:.2%} (Peak: {peak_idx}, Trough: {trough_idx})")
    
    print("\n✅ Risk metrics calculation completed successfully")
