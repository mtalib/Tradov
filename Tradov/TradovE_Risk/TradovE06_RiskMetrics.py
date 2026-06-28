#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovE_Risk
Module: TradovE06_RiskMetrics.py
Purpose: TRADOV - Automated TRAD Options Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-06-26 Time: 13:25:07

Module Description:
    TRADOV - Automated TRAD Options Trading System

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from datetime import datetime, timedelta, UTC
from typing import Any
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import threading

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import math
import numpy as np
import pandas as pd
import logging

try:
    from scipy import stats
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    logging.info("WARNING: scipy not available. Some risk calculations will be limited.")

try:
    import empyrical
    HAS_EMPYRICAL = True
except ImportError:
    HAS_EMPYRICAL = False

# ==============================================================================
# LOCAL IMPORTS - SAFE PATTERN
# ==============================================================================
try:
    from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger
except ImportError:
    import logging
    TradovLogger = type('TradovLogger', (), {
        'get_logger': lambda name: logging.getLogger(name)
    })()

try:
    from Tradov.TradovU_Utilities.TradovU02_ErrorHandler import TradovErrorHandler
except ImportError:
    TradovErrorHandler = type('TradovErrorHandler', (), {
        'handle_error': lambda self, e, context: logging.warning("Error in %s: %s", context, e)
    })

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Risk-free rate (annual) - standardized across all modules
DEFAULT_RISK_FREE_RATE = 0.045  # 4.5% annual (current T-bill rate)
TREASURY_BILL_RATE = 0.045      # Current T-bill rate (updated 2026-01-16)

# Trading days
TRADING_DAYS_PER_YEAR = 252
TRADING_DAYS_PER_MONTH = 21
TRADING_DAYS_PER_WEEK = 5

# Calculation parameters
MIN_PERIODS_SHARPE = 30        # Minimum periods for Sharpe
MIN_PERIODS_SORTINO = 30       # Minimum periods for Sortino
CONFIDENCE_LEVEL_VAR = 0.95    # 95% VaR
CONFIDENCE_LEVEL_CVAR = 0.95   # 95% CVaR

# Performance thresholds
GOOD_SHARPE_RATIO = 1.0
EXCELLENT_SHARPE_RATIO = 2.0
GOOD_SORTINO_RATIO = 1.5
EXCELLENT_SORTINO_RATIO = 2.5

# Window sizes for rolling calculations
ROLLING_WINDOW_DAILY = 252     # 1 year
ROLLING_WINDOW_MONTHLY = 36    # 3 years
ROLLING_WINDOW_DRAWDOWN = 252  # 1 year

# ==============================================================================
# ENUMS
# ==============================================================================
class MetricType(Enum):
    """Types of risk metrics."""
    SHARPE_RATIO = "sharpe_ratio"
    SORTINO_RATIO = "sortino_ratio"
    CALMAR_RATIO = "calmar_ratio"
    INFORMATION_RATIO = "information_ratio"
    TREYNOR_RATIO = "treynor_ratio"
    MAX_DRAWDOWN = "max_drawdown"
    VAR = "value_at_risk"
    CVAR = "conditional_var"
    VOLATILITY = "volatility"
    DOWNSIDE_DEVIATION = "downside_deviation"
    BETA = "beta"
    ALPHA = "alpha"
    OMEGA_RATIO = "omega_ratio"
    GAIN_LOSS_RATIO = "gain_loss_ratio"

class TimeFrame(Enum):
    """Time frames for calculations."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    CUSTOM = "custom"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class RiskMetrics:
    """Comprehensive risk metrics."""
    timestamp: datetime
    period_start: datetime
    period_end: datetime
    num_periods: int

    # Return metrics
    total_return: float
    annualized_return: float
    average_return: float

    # Risk metrics
    volatility: float
    downside_deviation: float
    max_drawdown: float
    var_95: float
    cvar_95: float

    # Risk-adjusted returns
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    information_ratio: float | None = None
    treynor_ratio: float | None = None

    # Additional metrics
    win_rate: float = 0.0
    profit_factor: float = 0.0
    recovery_factor: float = 0.0
    gain_loss_ratio: float = 0.0
    omega_ratio: float = 0.0

    # Market correlation
    beta: float | None = None
    alpha: float | None = None
    correlation: float | None = None
    r_squared: float | None = None

    # Drawdown details
    current_drawdown: float = 0.0
    drawdown_duration: int = 0
    time_underwater: float = 0.0

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class DrawdownAnalysis:
    """Detailed drawdown analysis."""
    max_drawdown: float
    max_drawdown_duration: int
    current_drawdown: float
    current_duration: int
    recovery_time: int | None
    peak_index: int
    trough_index: int
    underwater_periods: int
    average_drawdown: float
    drawdown_volatility: float
    worst_drawdowns: list[tuple[float, int, int]]  # (drawdown, start_idx, end_idx)

@dataclass
class RollingMetrics:
    """Rolling window metrics."""
    window_size: int
    timestamps: list[datetime]
    sharpe_ratios: list[float]
    sortino_ratios: list[float]
    volatilities: list[float]
    drawdowns: list[float]
    returns: list[float]

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================
def calculate_returns(prices: list[float], method: str = 'simple') -> list[float]:
    """
    Calculate returns from price series.

    Args:
        prices: List of prices
        method: 'simple' or 'log' returns

    Returns:
        List of returns
    """
    if len(prices) < 2:
        return []

    returns = []
    for i in range(1, len(prices)):
        if prices[i-1] != 0:
            if method == 'log':
                ret = math.log(prices[i] / prices[i-1])
            else:
                ret = (prices[i] - prices[i-1]) / prices[i-1]
            returns.append(ret)

    return returns

def annualize_return(returns: list[float], periods_per_year: int = TRADING_DAYS_PER_YEAR) -> float:
    """Annualize returns."""
    if not returns:
        return 0.0

    total_return = np.prod([1 + r for r in returns]) - 1
    n_periods = len(returns)

    if n_periods == 0:
        return 0.0

    years = n_periods / periods_per_year
    if years <= 0:
        return 0.0

    return (1 + total_return) ** (1 / years) - 1

def annualize_volatility(returns: list[float], periods_per_year: int = TRADING_DAYS_PER_YEAR) -> float:  # noqa: E501
    """Annualize volatility."""
    if len(returns) < 2:
        return 0.0

    return np.std(returns) * np.sqrt(periods_per_year)

# ==============================================================================
# CORE METRIC CALCULATIONS
# ==============================================================================
def calculate_sharpe_ratio(returns: list[float],
                         risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
                         periods_per_year: int = TRADING_DAYS_PER_YEAR) -> float:
    """
    Calculate Sharpe ratio.

    Sharpe = (Return - Risk Free Rate) / Volatility
    """
    if len(returns) < MIN_PERIODS_SHARPE:
        return 0.0

    # Annualized metrics
    annual_return = annualize_return(returns, periods_per_year)
    annual_vol = annualize_volatility(returns, periods_per_year)

    if annual_vol == 0:
        return 0.0

    return (annual_return - risk_free_rate) / annual_vol

def calculate_sortino_ratio(returns: list[float],
                          risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
                          periods_per_year: int = TRADING_DAYS_PER_YEAR) -> float:
    """
    Calculate Sortino ratio (uses downside deviation).

    Sortino = (Return - Risk Free Rate) / Downside Deviation
    """
    if len(returns) < MIN_PERIODS_SORTINO:
        return 0.0

    # Calculate downside returns
    downside_returns = [r for r in returns if r < 0]

    if not downside_returns:
        return 0.0  # No downside risk

    # Annualized metrics
    annual_return = annualize_return(returns, periods_per_year)
    downside_dev = np.std(downside_returns) * np.sqrt(periods_per_year)

    if downside_dev == 0:
        return 0.0

    return (annual_return - risk_free_rate) / downside_dev

def calculate_calmar_ratio(returns: list[float], max_drawdown: float,
                         periods_per_year: int = TRADING_DAYS_PER_YEAR) -> float:
    """
    Calculate Calmar ratio.

    Calmar = Annualized Return / Max Drawdown
    """
    if not returns or max_drawdown == 0:
        return 0.0

    annual_return = annualize_return(returns, periods_per_year)

    return annual_return / abs(max_drawdown)

def calculate_max_drawdown(equity_curve: list[float]) -> tuple[float, int, int]:
    """
    Calculate maximum drawdown and peak/trough indices.

    Returns:
        Tuple of (max_drawdown, peak_index, trough_index)
    """
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

def calculate_var(returns: list[float], confidence_level: float = CONFIDENCE_LEVEL_VAR) -> float:
    """Calculate Value at Risk (VaR)."""
    if not returns:
        return 0.0

    return np.percentile(returns, (1 - confidence_level) * 100)

def calculate_cvar(returns: list[float], confidence_level: float = CONFIDENCE_LEVEL_CVAR) -> float:
    """Calculate Conditional Value at Risk (CVaR) or Expected Shortfall."""
    if not returns:
        return 0.0

    var = calculate_var(returns, confidence_level)
    conditional_returns = [r for r in returns if r <= var]

    return np.mean(conditional_returns) if conditional_returns else var

def calculate_omega_ratio(returns: list[float], threshold: float = 0.0) -> float:
    """
    Calculate Omega ratio.

    Omega = Sum of returns above threshold / Sum of returns below threshold
    """
    if not returns:
        return 0.0

    gains = sum(r - threshold for r in returns if r > threshold)
    losses = sum(threshold - r for r in returns if r < threshold)

    if losses == 0:
        return float('inf') if gains > 0 else 0.0

    return gains / losses

def calculate_information_ratio(returns: list[float], benchmark_returns: list[float],
                              periods_per_year: int = TRADING_DAYS_PER_YEAR) -> float:
    """
    Calculate Information ratio.

    IR = (Portfolio Return - Benchmark Return) / Tracking Error
    """
    if len(returns) != len(benchmark_returns) or len(returns) < 30:
        return 0.0

    # Calculate excess returns
    excess_returns = [r - b for r, b in zip(returns, benchmark_returns, strict=False)]

    # Annualized excess return
    annual_excess = annualize_return(excess_returns, periods_per_year)

    # Tracking error (std of excess returns)
    tracking_error = np.std(excess_returns) * np.sqrt(periods_per_year)

    if tracking_error == 0:
        return 0.0

    return annual_excess / tracking_error

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

    Attributes:
        risk_free_rate: Risk-free rate for calculations
        metrics_cache: Cache of calculated metrics

    Example:
        >>> calculator = RiskMetricsCalculator()
        >>> metrics = calculator.calculate_metrics(returns, equity_curve)
        >>> print(f"Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
    """

    def __init__(self, risk_free_rate: float = DEFAULT_RISK_FREE_RATE):
        """
        Initialize risk metrics calculator.

        Args:
            risk_free_rate: Annual risk-free rate
        """
        self.logger = TradovLogger.get_logger(__name__)
        self.error_handler = TradovErrorHandler()

        self.risk_free_rate = risk_free_rate

        # Thread safety
        self._lock = threading.RLock()

        # Caching
        self.metrics_cache: dict[str, RiskMetrics] = {}
        self.rolling_cache: dict[str, RollingMetrics] = {}

        # Historical data storage
        self.returns_history: deque = deque(maxlen=ROLLING_WINDOW_DAILY * 2)
        self.equity_history: deque = deque(maxlen=ROLLING_WINDOW_DAILY * 2)
        self.benchmark_history: deque = deque(maxlen=ROLLING_WINDOW_DAILY * 2)

        self.logger.info("RiskMetricsCalculator initialized")

    # ==========================================================================
    # PUBLIC METHODS - METRIC CALCULATION
    # ==========================================================================
    def calculate_metrics(self,
                        returns: list[float],
                        equity_curve: list[float],
                        benchmark_returns: list[float] | None = None,
                        period_start: datetime | None = None,
                        period_end: datetime | None = None) -> RiskMetrics:
        """
        Calculate comprehensive risk metrics.

        Args:
            returns: List of period returns
            equity_curve: List of equity values
            benchmark_returns: Optional benchmark returns
            period_start: Start date of period
            period_end: End date of period

        Returns:
            RiskMetrics object with all calculations
        """
        try:
            with self._lock:
                # Validate inputs
                if not returns or not equity_curve:
                    return self._create_empty_metrics()

                # Set period dates
                if not period_end:
                    period_end = datetime.now(UTC)
                if not period_start:
                    period_start = period_end - timedelta(days=len(returns))

                # Basic return metrics
                total_return = self._calculate_total_return(equity_curve)
                annual_return = annualize_return(returns)
                avg_return = np.mean(returns) if returns else 0

                # Risk metrics
                volatility = annualize_volatility(returns)
                downside_dev = self._calculate_downside_deviation(returns)
                max_dd, peak_idx, trough_idx = calculate_max_drawdown(equity_curve)
                var_95 = calculate_var(returns)
                cvar_95 = calculate_cvar(returns)

                # Risk-adjusted returns
                sharpe = calculate_sharpe_ratio(returns, self.risk_free_rate)
                sortino = calculate_sortino_ratio(returns, self.risk_free_rate)
                calmar = calculate_calmar_ratio(returns, max_dd)

                # Market correlation metrics
                info_ratio = None
                treynor = None
                beta = None
                alpha = None
                correlation = None
                r_squared = None

                if benchmark_returns and len(benchmark_returns) == len(returns):
                    info_ratio = calculate_information_ratio(returns, benchmark_returns)
                    beta, alpha, r_squared = self._calculate_capm_metrics(returns, benchmark_returns)  # noqa: E501
                    if beta and volatility:
                        treynor = (annual_return - self.risk_free_rate) / beta
                    correlation = np.corrcoef(returns, benchmark_returns)[0, 1]

                # Additional metrics
                win_rate = self._calculate_win_rate(returns)
                profit_factor = self._calculate_profit_factor(returns)
                recovery_factor = self._calculate_recovery_factor(returns, max_dd)
                gain_loss_ratio = self._calculate_gain_loss_ratio(returns)
                omega = calculate_omega_ratio(returns)

                # Drawdown analysis
                current_dd = self._calculate_current_drawdown(equity_curve)
                dd_duration = self._calculate_drawdown_duration(equity_curve)
                time_underwater = self._calculate_time_underwater(equity_curve)

                # Create metrics object
                metrics = RiskMetrics(
                    timestamp=datetime.now(UTC),
                    period_start=period_start,
                    period_end=period_end,
                    num_periods=len(returns),
                    total_return=total_return,
                    annualized_return=annual_return,
                    average_return=avg_return,
                    volatility=volatility,
                    downside_deviation=downside_dev,
                    max_drawdown=max_dd,
                    var_95=var_95,
                    cvar_95=cvar_95,
                    sharpe_ratio=sharpe,
                    sortino_ratio=sortino,
                    calmar_ratio=calmar,
                    information_ratio=info_ratio,
                    treynor_ratio=treynor,
                    win_rate=win_rate,
                    profit_factor=profit_factor,
                    recovery_factor=recovery_factor,
                    gain_loss_ratio=gain_loss_ratio,
                    omega_ratio=omega,
                    beta=beta,
                    alpha=alpha,
                    correlation=correlation,
                    r_squared=r_squared,
                    current_drawdown=current_dd,
                    drawdown_duration=dd_duration,
                    time_underwater=time_underwater,
                    metadata={
                        'risk_free_rate': self.risk_free_rate,
                        'calculation_timestamp': datetime.now(UTC).isoformat()
                    }
                )

                # Cache result
                cache_key = f"{period_start}_{period_end}_{len(returns)}"
                self.metrics_cache[cache_key] = metrics

                return metrics

        except Exception as e:
            self.logger.error("Error calculating metrics: %s", e)
            self.error_handler.handle_error(e, {"method": "calculate_metrics"})
            return self._create_empty_metrics()

    def calculate_empyrical_metrics(self,
                                   returns: list[float],
                                   benchmark_returns: list[float] | None = None) -> dict[str, float]:  # noqa: E501
        """
        Calculate institutional-grade metrics using empyrical library.

        Provides cross-validated metrics that match institutional reporting
        standards. Falls back to local calculations if empyrical unavailable.

        Args:
            returns: List of period returns.
            benchmark_returns: Optional benchmark returns for relative metrics.

        Returns:
            Dict of empyrical-validated performance metrics.
        """
        if not HAS_EMPYRICAL:
            self.logger.warning("empyrical not available — using local calculations")
            return self._calculate_fallback_metrics(returns, benchmark_returns)

        try:
            ret_series = pd.Series(returns)

            metrics = {
                'source': 'empyrical',

                # Core return metrics
                'annual_return': float(empyrical.annual_return(ret_series, period='daily')),
                'cumulative_return': float(empyrical.cum_returns_final(ret_series)),
                'annual_volatility': float(empyrical.annual_volatility(ret_series, period='daily')),

                # Risk-adjusted ratios
                'sharpe_ratio': float(empyrical.sharpe_ratio(ret_series, period='daily')),
                'sortino_ratio': float(empyrical.sortino_ratio(ret_series, period='daily')),
                'calmar_ratio': float(empyrical.calmar_ratio(ret_series, period='daily')),
                'omega_ratio': float(empyrical.omega_ratio(ret_series)),

                # Drawdown
                'max_drawdown': float(empyrical.max_drawdown(ret_series)),

                # Tail risk
                'var_5': float(empyrical.value_at_risk(ret_series, cutoff=0.05)),
                'cvar_5': float(empyrical.conditional_value_at_risk(ret_series, cutoff=0.05)),

                # Stability
                'stability': float(empyrical.stability_of_timeseries(ret_series)),
                'tail_ratio': float(empyrical.tail_ratio(ret_series)),
            }

            # Benchmark-relative metrics
            if benchmark_returns and len(benchmark_returns) == len(returns):
                bench_series = pd.Series(benchmark_returns)
                metrics['alpha'] = float(empyrical.alpha(ret_series, bench_series, period='daily'))
                metrics['beta'] = float(empyrical.beta(ret_series, bench_series))
                metrics['information_ratio'] = float(empyrical.information_ratio(ret_series, bench_series))  # noqa: E501
                excess = empyrical.excess_sharpe(ret_series, bench_series)
                metrics['excess_sharpe'] = float(excess)

            return metrics

        except Exception as e:
            self.logger.error("empyrical calculation error: %s", e)
            return self._calculate_fallback_metrics(returns, benchmark_returns)

    def _calculate_fallback_metrics(self,
                                   returns: list[float],
                                   benchmark_returns: list[float] | None = None) -> dict[str, float]:  # noqa: E501
        """Fallback metrics using local calculations when empyrical unavailable."""
        metrics = {
            'source': 'local',
            'annual_return': annualize_return(returns),
            'annual_volatility': annualize_volatility(returns),
            'sharpe_ratio': calculate_sharpe_ratio(returns, self.risk_free_rate),
            'sortino_ratio': calculate_sortino_ratio(returns, self.risk_free_rate),
            'omega_ratio': calculate_omega_ratio(returns),
            'max_drawdown': 0.0,
            'var_5': calculate_var(returns, 0.95),
            'cvar_5': calculate_cvar(returns, 0.95),
        }

        if benchmark_returns and len(benchmark_returns) == len(returns):
            metrics['information_ratio'] = calculate_information_ratio(returns, benchmark_returns)

        return metrics

    def cross_validate_metrics(self,
                              returns: list[float],
                              benchmark_returns: list[float] | None = None) -> dict[str, Any]:
        """
        Cross-validate local calculations against empyrical for audit trail.

        Compares locally-computed Sharpe, Sortino, VaR, etc. against empyrical's
        implementations and reports discrepancies above tolerance threshold.

        Args:
            returns: List of period returns.
            benchmark_returns: Optional benchmark returns.

        Returns:
            Dict with local metrics, empyrical metrics, and discrepancy report.
        """
        local = self._calculate_fallback_metrics(returns, benchmark_returns)
        institutional = self.calculate_empyrical_metrics(returns, benchmark_returns)

        discrepancies = {}
        tolerance = 0.01  # 1% relative tolerance

        for key in ['sharpe_ratio', 'sortino_ratio', 'annual_return', 'annual_volatility']:
            if key in local and key in institutional:
                local_val = local[key]
                inst_val = institutional[key]
                if abs(inst_val) > 1e-8:
                    relative_diff = abs(local_val - inst_val) / abs(inst_val)
                    if relative_diff > tolerance:
                        discrepancies[key] = {
                            'local': local_val,
                            'empyrical': inst_val,
                            'relative_diff': relative_diff
                        }

        if discrepancies:
            self.logger.warning("Metric discrepancies detected: %s", list(discrepancies.keys()))

        return {
            'local_metrics': local,
            'institutional_metrics': institutional,
            'discrepancies': discrepancies,
            'validation_passed': len(discrepancies) == 0
        }

    def calculate_rolling_metrics(self,
                                returns: list[float],
                                window_size: int = 252,
                                step_size: int = 1) -> RollingMetrics:
        """
        Calculate rolling window metrics.

        Args:
            returns: List of returns
            window_size: Size of rolling window
            step_size: Step between windows

        Returns:
            RollingMetrics object
        """
        if len(returns) < window_size:
            return RollingMetrics(
                window_size=window_size,
                timestamps=[],
                sharpe_ratios=[],
                sortino_ratios=[],
                volatilities=[],
                drawdowns=[],
                returns=[]
            )

        timestamps = []
        sharpe_ratios = []
        sortino_ratios = []
        volatilities = []
        returns_list = []

        for i in range(0, len(returns) - window_size + 1, step_size):
            window_returns = returns[i:i + window_size]

            # Calculate metrics for window
            sharpe = calculate_sharpe_ratio(window_returns, self.risk_free_rate)
            sortino = calculate_sortino_ratio(window_returns, self.risk_free_rate)
            vol = annualize_volatility(window_returns)
            avg_return = np.mean(window_returns)

            # Store results
            timestamps.append(datetime.now(UTC) - timedelta(days=len(returns) - i - window_size))
            sharpe_ratios.append(sharpe)
            sortino_ratios.append(sortino)
            volatilities.append(vol)
            returns_list.append(avg_return)

        return RollingMetrics(
            window_size=window_size,
            timestamps=timestamps,
            sharpe_ratios=sharpe_ratios,
            sortino_ratios=sortino_ratios,
            volatilities=volatilities,
            drawdowns=[],  # Would need equity curve
            returns=returns_list
        )

    def analyze_drawdowns(self, equity_curve: list[float]) -> DrawdownAnalysis:
        """
        Perform detailed drawdown analysis.

        Args:
            equity_curve: List of equity values

        Returns:
            DrawdownAnalysis object
        """
        if not equity_curve:
            return self._create_empty_drawdown_analysis()

        # Calculate all drawdowns
        drawdowns = []
        peak = equity_curve[0]
        peak_idx = 0
        in_drawdown = False

        for i, value in enumerate(equity_curve):
            if value > peak:
                if in_drawdown:
                    # Drawdown ended
                    drawdowns.append((peak_idx, i-1, peak, equity_curve[i-1]))
                    in_drawdown = False
                peak = value
                peak_idx = i
            else:
                if not in_drawdown and value < peak * 0.99:  # 1% threshold
                    in_drawdown = True

        # Get max drawdown
        max_dd, max_peak_idx, max_trough_idx = calculate_max_drawdown(equity_curve)

        # Calculate statistics
        all_dd_values = []
        all_dd_durations = []

        for start_idx, end_idx, peak_val, trough_val in drawdowns:
            dd_value = (peak_val - trough_val) / peak_val if peak_val > 0 else 0
            dd_duration = end_idx - start_idx
            all_dd_values.append(dd_value)
            all_dd_durations.append(dd_duration)

        # Sort drawdowns by magnitude
        worst_drawdowns = sorted(
            [(dd, start, end) for (start, end, _, _), dd in zip(drawdowns, all_dd_values, strict=False)],  # noqa: E501
            key=lambda x: x[0],
            reverse=True
        )[:5]  # Top 5 worst

        return DrawdownAnalysis(
            max_drawdown=max_dd,
            max_drawdown_duration=max_trough_idx - max_peak_idx if max_dd > 0 else 0,
            current_drawdown=self._calculate_current_drawdown(equity_curve),
            current_duration=self._calculate_drawdown_duration(equity_curve),
            recovery_time=None,  # Would need to track recovery
            peak_index=max_peak_idx,
            trough_index=max_trough_idx,
            underwater_periods=len(drawdowns),
            average_drawdown=np.mean(all_dd_values) if all_dd_values else 0,
            drawdown_volatility=np.std(all_dd_values) if all_dd_values else 0,
            worst_drawdowns=worst_drawdowns
        )

    # ==========================================================================
    # PRIVATE METHODS - CALCULATIONS
    # ==========================================================================
    def _calculate_total_return(self, equity_curve: list[float]) -> float:
        """Calculate total return from equity curve."""
        if not equity_curve or len(equity_curve) < 2:
            return 0.0

        start_value = equity_curve[0]
        end_value = equity_curve[-1]

        if start_value == 0:
            return 0.0

        return (end_value - start_value) / start_value

    def _calculate_downside_deviation(self, returns: list[float]) -> float:
        """Calculate annualized downside deviation."""
        downside_returns = [r for r in returns if r < 0]

        if not downside_returns:
            return 0.0

        return np.std(downside_returns) * np.sqrt(TRADING_DAYS_PER_YEAR)

    def _calculate_win_rate(self, returns: list[float]) -> float:
        """Calculate win rate (percentage of positive returns)."""
        if not returns:
            return 0.0

        positive_returns = sum(1 for r in returns if r > 0)
        return positive_returns / len(returns)

    def _calculate_profit_factor(self, returns: list[float]) -> float:
        """Calculate profit factor (gross profits / gross losses)."""
        if not returns:
            return 0.0

        gross_profits = sum(r for r in returns if r > 0)
        gross_losses = abs(sum(r for r in returns if r < 0))

        if gross_losses == 0:
            return float('inf') if gross_profits > 0 else 0.0

        return gross_profits / gross_losses

    def _calculate_recovery_factor(self, returns: list[float], max_drawdown: float) -> float:
        """Calculate recovery factor (net profit / max drawdown)."""
        if not returns or max_drawdown == 0:
            return 0.0

        net_profit = sum(returns)
        return net_profit / abs(max_drawdown)

    def _calculate_gain_loss_ratio(self, returns: list[float]) -> float:
        """Calculate average gain to average loss ratio."""
        gains = [r for r in returns if r > 0]
        losses = [abs(r) for r in returns if r < 0]

        if not gains or not losses:
            return 0.0

        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)

        if avg_loss == 0:
            return float('inf')

        return avg_gain / avg_loss

    def _calculate_capm_metrics(self, returns: list[float],
                              benchmark_returns: list[float]) -> tuple[float, float, float]:
        """Calculate CAPM metrics (beta, alpha, R-squared)."""
        if len(returns) != len(benchmark_returns) or len(returns) < 30:
            return None, None, None

        # Convert to arrays
        y = np.array(returns)
        x = np.array(benchmark_returns)

        # Add constant for intercept
        np.column_stack([np.ones(len(x)), x])

        try:
            # Linear regression
            if HAS_SCIPY:
                slope, intercept, r_value, _, _ = stats.linregress(x, y)
                beta = slope
                alpha = intercept * TRADING_DAYS_PER_YEAR  # Annualized
                r_squared = r_value ** 2
            else:
                # Manual calculation without scipy
                covariance = np.cov(x, y)[0, 1]
                variance = np.var(x)
                beta = covariance / variance if variance > 0 else 0
                alpha = np.mean(y) - beta * np.mean(x)
                alpha *= TRADING_DAYS_PER_YEAR

                # R-squared
                y_pred = alpha / TRADING_DAYS_PER_YEAR + beta * x
                ss_res = np.sum((y - y_pred) ** 2)
                ss_tot = np.sum((y - np.mean(y)) ** 2)
                r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

            return beta, alpha, r_squared

        except Exception as e:
            self.logger.error("CAPM calculation error: %s", e)
            return None, None, None

    def _calculate_current_drawdown(self, equity_curve: list[float]) -> float:
        """Calculate current drawdown from peak."""
        if not equity_curve:
            return 0.0

        peak = max(equity_curve)
        current = equity_curve[-1]

        if peak == 0:
            return 0.0

        return (peak - current) / peak

    def _calculate_drawdown_duration(self, equity_curve: list[float]) -> int:
        """Calculate current drawdown duration in periods."""
        if not equity_curve:
            return 0

        peak_value = max(equity_curve)
        equity_curve.index(peak_value)

        # If we're at peak, no drawdown
        if equity_curve[-1] >= peak_value * 0.99:  # 1% threshold
            return 0

        # Count periods since last peak
        duration = 0
        for i in range(len(equity_curve) - 1, -1, -1):
            if equity_curve[i] >= peak_value * 0.99:
                break
            duration += 1

        return duration

    def _calculate_time_underwater(self, equity_curve: list[float]) -> float:
        """Calculate percentage of time in drawdown."""
        if not equity_curve or len(equity_curve) < 2:
            return 0.0

        peak = equity_curve[0]
        periods_underwater = 0

        for value in equity_curve[1:]:
            if value >= peak:
                peak = value
            else:
                periods_underwater += 1

        return periods_underwater / len(equity_curve)

    def _create_empty_metrics(self) -> RiskMetrics:
        """Create empty metrics object."""
        return RiskMetrics(
            timestamp=datetime.now(UTC),
            period_start=datetime.now(UTC),
            period_end=datetime.now(UTC),
            num_periods=0,
            total_return=0.0,
            annualized_return=0.0,
            average_return=0.0,
            volatility=0.0,
            downside_deviation=0.0,
            max_drawdown=0.0,
            var_95=0.0,
            cvar_95=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            calmar_ratio=0.0
        )

    def _create_empty_drawdown_analysis(self) -> DrawdownAnalysis:
        """Create empty drawdown analysis."""
        return DrawdownAnalysis(
            max_drawdown=0.0,
            max_drawdown_duration=0,
            current_drawdown=0.0,
            current_duration=0,
            recovery_time=None,
            peak_index=0,
            trough_index=0,
            underwater_periods=0,
            average_drawdown=0.0,
            drawdown_volatility=0.0,
            worst_drawdowns=[]
        )

    # ==========================================================================
    # PUBLIC METHODS - UTILITIES
    # ==========================================================================
    def update_returns(self, returns: float | list[float]) -> None:
        """Update returns history."""
        with self._lock:
            if isinstance(returns, (int, float)):
                self.returns_history.append(returns)
            else:
                self.returns_history.extend(returns)

    def update_equity(self, equity: float) -> None:
        """Update equity history."""
        with self._lock:
            self.equity_history.append(equity)

    def update_benchmark(self, benchmark_return: float) -> None:
        """Update benchmark returns."""
        with self._lock:
            self.benchmark_history.append(benchmark_return)

    def get_metric_summary(self) -> dict[str, float]:
        """Get summary of key metrics."""
        if not self.returns_history:
            return {}

        returns = list(self.returns_history)
        equity = list(self.equity_history)

        metrics = self.calculate_metrics(returns, equity)

        return {
            'sharpe_ratio': metrics.sharpe_ratio,
            'sortino_ratio': metrics.sortino_ratio,
            'max_drawdown': metrics.max_drawdown,
            'volatility': metrics.volatility,
            'win_rate': metrics.win_rate,
            'profit_factor': metrics.profit_factor,
            'var_95': metrics.var_95,
            'annualized_return': metrics.annualized_return
        }

    def clear_cache(self) -> None:
        """Clear metrics cache."""
        with self._lock:
            self.metrics_cache.clear()
            self.rolling_cache.clear()
            self.logger.info("Metrics cache cleared")

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_risk_metrics_calculator(risk_free_rate: float = DEFAULT_RISK_FREE_RATE) -> RiskMetricsCalculator:  # noqa: E501
    """
    Create risk metrics calculator instance.

    Args:
        risk_free_rate: Annual risk-free rate

    Returns:
        RiskMetricsCalculator instance
    """
    return RiskMetricsCalculator(risk_free_rate)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":

    # Create calculator
    calculator = create_risk_metrics_calculator()

    # Generate sample data
    np.random.seed(42)

    # Simulate returns with positive drift
    daily_returns = np.random.normal(0.0005, 0.02, 252)  # 252 trading days

    # Add some winning streaks
    daily_returns[50:60] = np.random.normal(0.01, 0.005, 10)  # Good period
    daily_returns[150:160] = np.random.normal(-0.01, 0.005, 10)  # Bad period

    # Generate equity curve
    initial_equity = 100000
    equity_curve = [initial_equity]
    for ret in daily_returns:
        equity_curve.append(equity_curve[-1] * (1 + ret))

    # Generate benchmark returns (market)
    benchmark_returns = np.random.normal(0.0003, 0.015, 252)  # Slightly lower return

    # Calculate metrics
    metrics = calculator.calculate_metrics(
        returns=daily_returns.tolist(),
        equity_curve=equity_curve,
        benchmark_returns=benchmark_returns.tolist()
    )

    # Display results


    if metrics.information_ratio:
        pass


    if metrics.beta is not None:
        pass

    # Drawdown analysis
    dd_analysis = calculator.analyze_drawdowns(equity_curve)

    if dd_analysis.worst_drawdowns:
        for _i, (_dd, _start, _end) in enumerate(dd_analysis.worst_drawdowns[:3]):
            pass

    # Test rolling metrics
    rolling = calculator.calculate_rolling_metrics(daily_returns.tolist(), window_size=126, step_size=21)  # noqa: E501

    if rolling.sharpe_ratios:
        pass

    # Test metric summary
    summary = calculator.get_metric_summary()
    for key, value in summary.items():
        if isinstance(value, float):
            if 'return' in key or 'rate' in key:
                pass
            else:
                pass

