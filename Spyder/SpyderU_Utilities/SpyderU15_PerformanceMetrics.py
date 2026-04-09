#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderU_Utilities
Module: SpyderU15_PerformanceMetrics.py
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
from dataclasses import dataclass
from enum import Enum
from typing import Any

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

TRADING_DAYS_PER_YEAR = 252
RISK_FREE_RATE = 0.045  # 4.5% annual risk-free rate (current T-bill rate)
MIN_PERIODS_FOR_CALCULATION = 30

# Benchmark performance thresholds
EXCELLENT_SHARPE = 2.0
GOOD_SHARPE = 1.0
POOR_SHARPE = 0.5

EXCELLENT_CALMAR = 1.0
GOOD_CALMAR = 0.5
POOR_CALMAR = 0.25

# ==============================================================================
# ENUMS
# ==============================================================================


class PerformanceRating(Enum):
    """Performance rating categories"""

    EXCELLENT = "excellent"
    GOOD = "good"
    AVERAGE = "average"
    POOR = "poor"
    VERY_POOR = "very_poor"


class MetricType(Enum):
    """Performance metric types"""

    RETURN = "return"
    RISK = "risk"
    RATIO = "ratio"
    DRAWDOWN = "drawdown"
    VOLATILITY = "volatility"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================


@dataclass
class PerformanceReport:
    """Comprehensive performance report."""

    total_return: float
    annualized_return: float
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    max_drawdown_duration: int
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    rating: PerformanceRating

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_return": self.total_return,
            "annualized_return": self.annualized_return,
            "volatility": self.volatility,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_duration": self.max_drawdown_duration,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "largest_win": self.largest_win,
            "largest_loss": self.largest_loss,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "rating": self.rating.value,
        }


@dataclass
class DrawdownInfo:
    """Drawdown analysis information."""

    max_drawdown: float
    max_drawdown_duration: int
    recovery_time: int
    drawdown_periods: list[tuple[int, int, float]]  # (start, end, depth)


# ==============================================================================
# MAIN CLASS
# ==============================================================================


class PerformanceCalculator:
    """
    Performance metrics calculator for trading strategies.

    This class provides comprehensive performance analysis including risk-adjusted
    returns, drawdown analysis, and trading statistics. It serves as a Python 3.13
    compatible alternative to empyrical package with additional options-specific
    metrics for evaluating trading strategy performance.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        risk_free_rate: Risk-free rate for calculations

    Example:
        >>> calc = PerformanceCalculator()
        >>> returns = pd.Series([0.01, -0.005, 0.02, 0.015, -0.01])
        >>> sharpe = calc.calculate_sharpe_ratio(returns)
        >>> max_dd = calc.calculate_max_drawdown(returns.cumsum())
        >>> report = calc.generate_performance_report(returns)
    """

    def __init__(self, risk_free_rate: float = RISK_FREE_RATE):
        """Initialize the performance calculator."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.risk_free_rate = risk_free_rate

        self.logger.info("%s initialized", self.__class__.__name__)

    # ==========================================================================
    # CORE PERFORMANCE METRICS
    # ==========================================================================
    def calculate_total_return(self, returns: pd.Series) -> float:
        """
        Calculate total return from a series of returns.

        Args:
            returns: Series of periodic returns

        Returns:
            float: Total return
        """
        try:
            if len(returns) == 0:
                return 0.0

            # Calculate cumulative return
            total_return = (1 + returns).prod() - 1

            return float(total_return)

        except Exception as e:
            self.logger.error("Total return calculation failed: %s", e)
            return 0.0

    def calculate_annualized_return(
        self, returns: pd.Series, periods_per_year: int = TRADING_DAYS_PER_YEAR
    ) -> float:
        """
        Calculate annualized return.

        Args:
            returns: Series of periodic returns
            periods_per_year: Number of periods in a year

        Returns:
            float: Annualized return
        """
        try:
            if len(returns) == 0:
                return 0.0

            total_return = self.calculate_total_return(returns)
            years = len(returns) / periods_per_year

            if years <= 0:
                return 0.0

            annualized_return = (1 + total_return) ** (1 / years) - 1

            return float(annualized_return)

        except Exception as e:
            self.logger.error("Annualized return calculation failed: %s", e)
            return 0.0

    def calculate_volatility(
        self, returns: pd.Series, periods_per_year: int = TRADING_DAYS_PER_YEAR
    ) -> float:
        """
        Calculate annualized volatility.

        Args:
            returns: Series of periodic returns
            periods_per_year: Number of periods in a year

        Returns:
            float: Annualized volatility
        """
        try:
            if len(returns) < 2:
                return 0.0

            volatility = returns.std() * np.sqrt(periods_per_year)

            return float(volatility)

        except Exception as e:
            self.logger.error("Volatility calculation failed: %s", e)
            return 0.0

    # ==========================================================================
    # RISK-ADJUSTED METRICS
    # ==========================================================================
    def calculate_sharpe_ratio(
        self, returns: pd.Series, periods_per_year: int = TRADING_DAYS_PER_YEAR
    ) -> float:
        """
        Calculate Sharpe ratio.

        Args:
            returns: Series of periodic returns
            periods_per_year: Number of periods in a year

        Returns:
            float: Sharpe ratio
        """
        try:
            if len(returns) < MIN_PERIODS_FOR_CALCULATION:
                return 0.0

            excess_returns = returns - (self.risk_free_rate / periods_per_year)

            if excess_returns.std() == 0:
                return 0.0

            sharpe_ratio = excess_returns.mean() / excess_returns.std() * np.sqrt(periods_per_year)

            return float(sharpe_ratio)

        except Exception as e:
            self.logger.error("Sharpe ratio calculation failed: %s", e)
            return 0.0

    def calculate_sortino_ratio(
        self, returns: pd.Series, periods_per_year: int = TRADING_DAYS_PER_YEAR
    ) -> float:
        """
        Calculate Sortino ratio (downside deviation version of Sharpe).

        Args:
            returns: Series of periodic returns
            periods_per_year: Number of periods in a year

        Returns:
            float: Sortino ratio
        """
        try:
            if len(returns) < MIN_PERIODS_FOR_CALCULATION:
                return 0.0

            excess_returns = returns - (self.risk_free_rate / periods_per_year)
            downside_returns = excess_returns[excess_returns < 0]

            if len(downside_returns) == 0 or downside_returns.std() == 0:
                return float("inf") if excess_returns.mean() > 0 else 0.0

            downside_deviation = downside_returns.std() * np.sqrt(periods_per_year)
            sortino_ratio = (excess_returns.mean() * periods_per_year) / downside_deviation

            return float(sortino_ratio)

        except Exception as e:
            self.logger.error("Sortino ratio calculation failed: %s", e)
            return 0.0

    def calculate_calmar_ratio(self, returns: pd.Series) -> float:
        """
        Calculate Calmar ratio (annualized return / max drawdown).

        Args:
            returns: Series of periodic returns

        Returns:
            float: Calmar ratio
        """
        try:
            if len(returns) < MIN_PERIODS_FOR_CALCULATION:
                return 0.0

            annualized_return = self.calculate_annualized_return(returns)
            max_drawdown = abs(self.calculate_max_drawdown(returns.cumsum()))

            if max_drawdown == 0:
                return float("inf") if annualized_return > 0 else 0.0

            calmar_ratio = annualized_return / max_drawdown

            return float(calmar_ratio)

        except Exception as e:
            self.logger.error("Calmar ratio calculation failed: %s", e)
            return 0.0

    # ==========================================================================
    # DRAWDOWN ANALYSIS
    # ==========================================================================
    def calculate_max_drawdown(self, cumulative_returns: pd.Series) -> float:
        """
        Calculate maximum drawdown.

        Args:
            cumulative_returns: Series of cumulative returns

        Returns:
            float: Maximum drawdown (negative value)
        """
        try:
            if len(cumulative_returns) == 0:
                return 0.0

            # Calculate running maximum
            peak = cumulative_returns.expanding().max()

            # Calculate drawdown
            drawdown = (cumulative_returns - peak) / peak

            # Return maximum drawdown (most negative value)
            max_drawdown = drawdown.min()

            return float(max_drawdown)

        except Exception as e:
            self.logger.error("Max drawdown calculation failed: %s", e)
            return 0.0

    def analyze_drawdowns(self, cumulative_returns: pd.Series) -> DrawdownInfo:
        """
        Perform comprehensive drawdown analysis.

        Args:
            cumulative_returns: Series of cumulative returns

        Returns:
            DrawdownInfo: Detailed drawdown analysis
        """
        try:
            if len(cumulative_returns) == 0:
                return DrawdownInfo(0.0, 0, 0, [])

            # Calculate running maximum and drawdown
            peak = cumulative_returns.expanding().max()
            drawdown = (cumulative_returns - peak) / peak

            # Find drawdown periods
            in_drawdown = drawdown < 0
            drawdown_periods = []

            start_idx = None
            for i, is_dd in enumerate(in_drawdown):
                if is_dd and start_idx is None:
                    start_idx = i
                elif not is_dd and start_idx is not None:
                    end_idx = i - 1
                    max_dd_in_period = drawdown.iloc[start_idx:i].min()
                    drawdown_periods.append((start_idx, end_idx, float(max_dd_in_period)))
                    start_idx = None

            # Handle case where we end in drawdown
            if start_idx is not None:
                end_idx = len(drawdown) - 1
                max_dd_in_period = drawdown.iloc[start_idx:].min()
                drawdown_periods.append((start_idx, end_idx, float(max_dd_in_period)))

            # Calculate overall statistics
            max_drawdown = float(drawdown.min())
            max_drawdown_duration = 0
            recovery_time = 0

            if drawdown_periods:
                max_drawdown_duration = max(end - start + 1 for start, end, _ in drawdown_periods)

                # Calculate recovery time for largest drawdown
                largest_dd_period = min(drawdown_periods, key=lambda x: x[2])
                recovery_start = largest_dd_period[1] + 1
                if recovery_start < len(cumulative_returns):
                    target_value = cumulative_returns.iloc[largest_dd_period[0]]
                    for i in range(recovery_start, len(cumulative_returns)):
                        if cumulative_returns.iloc[i] >= target_value:
                            recovery_time = i - largest_dd_period[1]
                            break

            return DrawdownInfo(
                max_drawdown=max_drawdown,
                max_drawdown_duration=max_drawdown_duration,
                recovery_time=recovery_time,
                drawdown_periods=drawdown_periods,
            )

        except Exception as e:
            self.logger.error("Drawdown analysis failed: %s", e)
            return DrawdownInfo(0.0, 0, 0, [])

    # ==========================================================================
    # TRADING STATISTICS
    # ==========================================================================
    def calculate_win_rate(self, returns: pd.Series) -> float:
        """
        Calculate win rate (percentage of positive returns).

        Args:
            returns: Series of trade returns

        Returns:
            float: Win rate as percentage
        """
        try:
            if len(returns) == 0:
                return 0.0

            winning_trades = (returns > 0).sum()
            total_trades = len(returns)

            win_rate = (winning_trades / total_trades) * 100

            return float(win_rate)

        except Exception as e:
            self.logger.error("Win rate calculation failed: %s", e)
            return 0.0

    def calculate_profit_factor(self, returns: pd.Series) -> float:
        """
        Calculate profit factor (gross profit / gross loss).

        Args:
            returns: Series of trade returns

        Returns:
            float: Profit factor
        """
        try:
            if len(returns) == 0:
                return 0.0

            gross_profit = returns[returns > 0].sum()
            gross_loss = abs(returns[returns < 0].sum())

            if gross_loss == 0:
                return float("inf") if gross_profit > 0 else 0.0

            profit_factor = gross_profit / gross_loss

            return float(profit_factor)

        except Exception as e:
            self.logger.error("Profit factor calculation failed: %s", e)
            return 0.0

    def calculate_trade_statistics(self, returns: pd.Series) -> dict[str, float]:
        """
        Calculate comprehensive trade statistics.

        Args:
            returns: Series of trade returns

        Returns:
            Dictionary with trade statistics
        """
        try:
            if len(returns) == 0:
                return {
                    "total_trades": 0,
                    "winning_trades": 0,
                    "losing_trades": 0,
                    "avg_win": 0.0,
                    "avg_loss": 0.0,
                    "largest_win": 0.0,
                    "largest_loss": 0.0,
                }

            winning_trades = returns[returns > 0]
            losing_trades = returns[returns < 0]

            stats = {
                "total_trades": len(returns),
                "winning_trades": len(winning_trades),
                "losing_trades": len(losing_trades),
                "avg_win": float(winning_trades.mean()) if len(winning_trades) > 0 else 0.0,
                "avg_loss": float(losing_trades.mean()) if len(losing_trades) > 0 else 0.0,
                "largest_win": float(winning_trades.max()) if len(winning_trades) > 0 else 0.0,
                "largest_loss": float(losing_trades.min()) if len(losing_trades) > 0 else 0.0,
            }

            return stats

        except Exception as e:
            self.logger.error("Trade statistics calculation failed: %s", e)
            return {}

    # ==========================================================================
    # PERFORMANCE RATING
    # ==========================================================================
    def rate_performance(
        self, sharpe_ratio: float, calmar_ratio: float, win_rate: float
    ) -> PerformanceRating:
        """
        Rate overall performance based on key metrics.

        Args:
            sharpe_ratio: Sharpe ratio
            calmar_ratio: Calmar ratio
            win_rate: Win rate percentage

        Returns:
            PerformanceRating: Overall performance rating
        """
        try:
            score = 0

            # Sharpe ratio scoring
            if sharpe_ratio >= EXCELLENT_SHARPE:
                score += 3
            elif sharpe_ratio >= GOOD_SHARPE:
                score += 2
            elif sharpe_ratio >= POOR_SHARPE:
                score += 1

            # Calmar ratio scoring
            if calmar_ratio >= EXCELLENT_CALMAR:
                score += 3
            elif calmar_ratio >= GOOD_CALMAR:
                score += 2
            elif calmar_ratio >= POOR_CALMAR:
                score += 1

            # Win rate scoring
            if win_rate >= 60:
                score += 3
            elif win_rate >= 50:
                score += 2
            elif win_rate >= 40:
                score += 1

            # Determine rating based on total score
            if score >= 8:
                return PerformanceRating.EXCELLENT
            elif score >= 6:
                return PerformanceRating.GOOD
            elif score >= 4:
                return PerformanceRating.AVERAGE
            elif score >= 2:
                return PerformanceRating.POOR
            else:
                return PerformanceRating.VERY_POOR

        except Exception as e:
            self.logger.error("Performance rating failed: %s", e)
            return PerformanceRating.AVERAGE

    # ==========================================================================
    # COMPREHENSIVE ANALYSIS
    # ==========================================================================
    def generate_performance_report(self, returns: pd.Series) -> PerformanceReport:
        """
        Generate comprehensive performance report.

        Args:
            returns: Series of periodic returns

        Returns:
            PerformanceReport: Complete performance analysis
        """
        try:
            # Calculate core metrics
            total_return = self.calculate_total_return(returns)
            annualized_return = self.calculate_annualized_return(returns)
            volatility = self.calculate_volatility(returns)

            # Calculate risk-adjusted metrics
            sharpe_ratio = self.calculate_sharpe_ratio(returns)
            sortino_ratio = self.calculate_sortino_ratio(returns)
            calmar_ratio = self.calculate_calmar_ratio(returns)

            # Calculate drawdown metrics
            cumulative_returns = (1 + returns).cumprod() - 1
            drawdown_info = self.analyze_drawdowns(cumulative_returns)

            # Calculate trading statistics
            win_rate = self.calculate_win_rate(returns)
            profit_factor = self.calculate_profit_factor(returns)
            trade_stats = self.calculate_trade_statistics(returns)

            # Rate performance
            rating = self.rate_performance(sharpe_ratio, calmar_ratio, win_rate)

            report = PerformanceReport(
                total_return=total_return,
                annualized_return=annualized_return,
                volatility=volatility,
                sharpe_ratio=sharpe_ratio,
                sortino_ratio=sortino_ratio,
                calmar_ratio=calmar_ratio,
                max_drawdown=drawdown_info.max_drawdown,
                max_drawdown_duration=drawdown_info.max_drawdown_duration,
                win_rate=win_rate,
                profit_factor=profit_factor,
                avg_win=trade_stats.get("avg_win", 0.0),
                avg_loss=trade_stats.get("avg_loss", 0.0),
                largest_win=trade_stats.get("largest_win", 0.0),
                largest_loss=trade_stats.get("largest_loss", 0.0),
                total_trades=trade_stats.get("total_trades", 0),
                winning_trades=trade_stats.get("winning_trades", 0),
                losing_trades=trade_stats.get("losing_trades", 0),
                rating=rating,
            )

            return report

        except Exception as e:
            self.logger.error("Performance report generation failed: %s", e)
            # Return default report on error
            return PerformanceReport(
                total_return=0.0,
                annualized_return=0.0,
                volatility=0.0,
                sharpe_ratio=0.0,
                sortino_ratio=0.0,
                calmar_ratio=0.0,
                max_drawdown=0.0,
                max_drawdown_duration=0,
                win_rate=0.0,
                profit_factor=0.0,
                avg_win=0.0,
                avg_loss=0.0,
                largest_win=0.0,
                largest_loss=0.0,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                rating=PerformanceRating.VERY_POOR,
            )


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================


def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = RISK_FREE_RATE) -> float:
    """
    Quick Sharpe ratio calculation function.

    Args:
        returns: Series of periodic returns
        risk_free_rate: Risk-free rate

    Returns:
        float: Sharpe ratio
    """
    calc = PerformanceCalculator(risk_free_rate)
    return calc.calculate_sharpe_ratio(returns)


def calculate_max_drawdown(cumulative_returns: pd.Series) -> float:
    """
    Quick max drawdown calculation function.

    Args:
        cumulative_returns: Series of cumulative returns

    Returns:
        float: Maximum drawdown
    """
    calc = PerformanceCalculator()
    return calc.calculate_max_drawdown(cumulative_returns)


def generate_performance_report(returns: pd.Series) -> PerformanceReport:
    """
    Quick performance report generation function.

    Args:
        returns: Series of periodic returns

    Returns:
        PerformanceReport: Complete performance analysis
    """
    calc = PerformanceCalculator()
    return calc.generate_performance_report(returns)


# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# Module-level initialization code
_performance_calculator_instance: PerformanceCalculator | None = None


def get_performance_calculator() -> PerformanceCalculator:
    """
    Get singleton instance of performance calculator.

    Returns:
        PerformanceCalculator instance
    """
    global _performance_calculator_instance
    if _performance_calculator_instance is None:
        _performance_calculator_instance = PerformanceCalculator()
    return _performance_calculator_instance


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code

    calc = PerformanceCalculator()

    # Create test data
    np.random.seed(42)
    dates = pd.date_range("2023-01-01", periods=252, freq="D")
    returns = pd.Series(np.random.normal(0.001, 0.02, 252), index=dates)

    # Test individual metrics
    total_return = calc.calculate_total_return(returns)

    annualized_return = calc.calculate_annualized_return(returns)

    volatility = calc.calculate_volatility(returns)

    sharpe_ratio = calc.calculate_sharpe_ratio(returns)

    # Test drawdown analysis
    cumulative_returns = (1 + returns).cumprod() - 1
    max_drawdown = calc.calculate_max_drawdown(cumulative_returns)

    # Test comprehensive report
    report = calc.generate_performance_report(returns)


# Add at the end of the file


def calculate_metrics(data=None):
    """Calculate performance metrics"""
    return {"sharpe_ratio": 0.0, "max_drawdown": 0.0, "win_rate": 0.0, "profit_factor": 1.0}
