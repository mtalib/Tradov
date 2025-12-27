#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderU06_MathUtils.py
Group: U (Utilities)
Purpose: Mathematical utility functions

Description:
    This module provides mathematical utilities for financial calculations,
    statistical analysis, and technical computations used throughout the
    trading system. It includes functions for option pricing, risk metrics,
    statistical measures, and numerical methods optimized for trading applications.

Author: Mohamed Talib
Date: 2025-06-01
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import math
import statistics
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from typing import Callable, List, Optional, Tuple, Union

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
from scipy import optimize, stats
from scipy.special import ndtr

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Precision settings
PRICE_PRECISION = 2
PERCENTAGE_PRECISION = 4
GREEK_PRECISION = 6

# Statistical constants
TRADING_DAYS_PER_YEAR = 252
MINUTES_PER_TRADING_DAY = 390
CONFIDENCE_LEVELS = [0.90, 0.95, 0.99]

# Numerical method parameters
MAX_ITERATIONS = 100
CONVERGENCE_THRESHOLD = 1e-7

# ==============================================================================
# BASIC MATH FUNCTIONS
# ==============================================================================


def round_price(value: float, precision: int = PRICE_PRECISION) -> float:
    """
    Round a price to specified precision.

    Args:
        value: Price value
        precision: Decimal places

    Returns:
        Rounded price
    """
    return float(
        Decimal(str(value)).quantize(Decimal(f'0.{"0" * precision}'), rounding=ROUND_HALF_UP)
    )


def round_to_tick(value: float, tick_size: float) -> float:
    """
    Round to nearest tick size.

    Args:
        value: Value to round
        tick_size: Minimum tick size

    Returns:
        Rounded value
    """
    return round(value / tick_size) * tick_size


def calculate_percentage_change(old_value: float, new_value: float) -> float:
    """
    Calculate percentage change.

    Args:
        old_value: Previous value
        new_value: Current value

    Returns:
        Percentage change
    """
    if old_value == 0:
        return 0.0 if new_value == 0 else float("inf")

    return ((new_value - old_value) / abs(old_value)) * 100


def calculate_compound_return(returns: List[float]) -> float:
    """
    Calculate compound return from a series of returns.

    Args:
        returns: List of period returns (as decimals)

    Returns:
        Compound return
    """
    compound = 1.0
    for r in returns:
        compound *= 1 + r
    return compound - 1


# ==============================================================================
# STATISTICAL FUNCTIONS
# ==============================================================================


def calculate_mean(values: List[float]) -> float:
    """
    Calculate arithmetic mean.

    Args:
        values: List of values

    Returns:
        Mean value
    """
    if not values:
        return 0.0
    return statistics.mean(values)


def calculate_std_dev(values: List[float], sample: bool = True) -> float:
    """
    Calculate standard deviation.

    Args:
        values: List of values
        sample: Use sample standard deviation

    Returns:
        Standard deviation
    """
    if len(values) < 2:
        return 0.0

    if sample:
        return statistics.stdev(values)
    else:
        return statistics.pstdev(values)


def calculate_sharpe_ratio(
    returns: List[float],
    risk_free_rate: float = 0.02,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> float:
    """
    Calculate Sharpe ratio.

    Args:
        returns: List of period returns
        risk_free_rate: Annual risk-free rate
        periods_per_year: Number of periods per year

    Returns:
        Sharpe ratio
    """
    if len(returns) < 2:
        return 0.0

    # Convert to numpy array
    returns_array = np.array(returns)

    # Calculate excess returns
    period_rf_rate = risk_free_rate / periods_per_year
    excess_returns = returns_array - period_rf_rate

    # Calculate Sharpe ratio
    mean_excess = np.mean(excess_returns)
    std_excess = np.std(excess_returns, ddof=1)

    if std_excess == 0:
        return 0.0

    # Annualize
    sharpe = mean_excess / std_excess * np.sqrt(periods_per_year)

    return float(sharpe)


def calculate_sortino_ratio(
    returns: List[float],
    risk_free_rate: float = 0.02,
    target_return: float = 0.0,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> float:
    """
    Calculate Sortino ratio.

    Args:
        returns: List of period returns
        risk_free_rate: Annual risk-free rate
        target_return: Target return for downside deviation
        periods_per_year: Number of periods per year

    Returns:
        Sortino ratio
    """
    if len(returns) < 2:
        return 0.0

    # Convert to numpy array
    returns_array = np.array(returns)

    # Calculate excess returns
    period_rf_rate = risk_free_rate / periods_per_year
    excess_returns = returns_array - period_rf_rate

    # Calculate downside deviation
    downside_returns = excess_returns[excess_returns < target_return]

    if len(downside_returns) == 0:
        return float("inf")  # No downside risk

    downside_std = np.std(downside_returns, ddof=1)

    if downside_std == 0:
        return 0.0

    # Calculate Sortino ratio
    mean_excess = np.mean(excess_returns)
    sortino = mean_excess / downside_std * np.sqrt(periods_per_year)

    return float(sortino)


def calculate_max_drawdown(equity_curve: List[float]) -> Tuple[float, int, int]:
    """
    Calculate maximum drawdown.

    Args:
        equity_curve: List of equity values

    Returns:
        Tuple of (max_drawdown_percentage, peak_index, trough_index)
    """
    if len(equity_curve) < 2:
        return 0.0, 0, 0

    # Convert to numpy array
    equity = np.array(equity_curve)

    # Calculate running maximum
    running_max = np.maximum.accumulate(equity)

    # Calculate drawdown
    drawdown = (equity - running_max) / running_max

    # Find maximum drawdown
    max_dd_idx = np.argmin(drawdown)
    max_dd = drawdown[max_dd_idx]

    # Find peak before the maximum drawdown
    peak_idx = np.argmax(equity[: max_dd_idx + 1])

    return float(max_dd * 100), int(peak_idx), int(max_dd_idx)


def calculate_var(
    returns: List[float], confidence_level: float = 0.95, method: str = "historical"
) -> float:
    """
    Calculate Value at Risk (VaR).

    Args:
        returns: List of returns
        confidence_level: Confidence level (0.95 for 95%)
        method: 'historical' or 'parametric'

    Returns:
        VaR value
    """
    if not returns:
        return 0.0

    if method == "historical":
        # Historical VaR
        sorted_returns = sorted(returns)
        index = int((1 - confidence_level) * len(sorted_returns))
        return -sorted_returns[index] if index < len(sorted_returns) else 0.0

    elif method == "parametric":
        # Parametric VaR (assumes normal distribution)
        mean = np.mean(returns)
        std = np.std(returns, ddof=1)
        z_score = stats.norm.ppf(1 - confidence_level)
        return -(mean + z_score * std)

    else:
        raise ValueError(f"Unknown VaR method: {method}")


def calculate_cvar(returns: List[float], confidence_level: float = 0.95) -> float:
    """
    Calculate Conditional Value at Risk (CVaR).

    Args:
        returns: List of returns
        confidence_level: Confidence level

    Returns:
        CVaR value
    """
    if not returns:
        return 0.0

    # Get VaR threshold
    var = calculate_var(returns, confidence_level, "historical")

    # Calculate average of returns below VaR
    below_var = [r for r in returns if r <= -var]

    if below_var:
        return -np.mean(below_var)
    else:
        return var


# ==============================================================================
# PROBABILITY FUNCTIONS
# ==============================================================================


@lru_cache(maxsize=1024)
def normal_cdf(x: float) -> float:
    """
    Cumulative distribution function for standard normal.

    Args:
        x: Value

    Returns:
        CDF value
    """
    return float(ndtr(x))


@lru_cache(maxsize=1024)
def normal_pdf(x: float) -> float:
    """
    Probability density function for standard normal.

    Args:
        x: Value

    Returns:
        PDF value
    """
    return float(np.exp(-0.5 * x**2) / np.sqrt(2 * np.pi))


def calculate_probability_touch(
    current_price: float, target_price: float, volatility: float, days_to_expiry: float
) -> float:
    """
    Calculate probability of touching a price level.

    Args:
        current_price: Current price
        target_price: Target price level
        volatility: Annualized volatility
        days_to_expiry: Days until expiration

    Returns:
        Probability of touch
    """
    if days_to_expiry <= 0 or volatility <= 0:
        return 0.0 if target_price != current_price else 1.0

    # Calculate parameters
    time_to_expiry = days_to_expiry / TRADING_DAYS_PER_YEAR
    vol_sqrt_time = volatility * np.sqrt(time_to_expiry)

    # Calculate z-score
    z = abs(np.log(target_price / current_price)) / vol_sqrt_time

    # Probability of touch is approximately 2 * N(-z)
    prob_touch = 2 * normal_cdf(-z)

    return float(min(prob_touch, 1.0))


def calculate_probability_profit(
    breakeven_price: float,
    current_price: float,
    volatility: float,
    days_to_expiry: float,
    is_bullish: bool = True,
) -> float:
    """
    Calculate probability of profit at expiration.

    Args:
        breakeven_price: Breakeven price
        current_price: Current underlying price
        volatility: Annualized volatility
        days_to_expiry: Days until expiration
        is_bullish: True for bullish, False for bearish

    Returns:
        Probability of profit
    """
    if days_to_expiry <= 0:
        if is_bullish:
            return 1.0 if current_price > breakeven_price else 0.0
        else:
            return 1.0 if current_price < breakeven_price else 0.0

    # Calculate parameters
    time_to_expiry = days_to_expiry / TRADING_DAYS_PER_YEAR
    drift = 0  # Assuming risk-neutral

    # Calculate z-score
    z = (np.log(breakeven_price / current_price) - drift * time_to_expiry) / (
        volatility * np.sqrt(time_to_expiry)
    )

    # Probability depends on direction
    if is_bullish:
        return float(1 - normal_cdf(z))
    else:
        return float(normal_cdf(z))


# ==============================================================================
# OPTIMIZATION FUNCTIONS
# ==============================================================================


def find_root(
    func: Callable[[float], float],
    a: float,
    b: float,
    tol: float = CONVERGENCE_THRESHOLD,
    max_iter: int = MAX_ITERATIONS,
) -> Optional[float]:
    """
    Find root using Brent's method.

    Args:
        func: Function to find root of
        a: Lower bound
        b: Upper bound
        tol: Tolerance
        max_iter: Maximum iterations

    Returns:
        Root value or None
    """
    try:
        root = optimize.brentq(func, a, b, xtol=tol, maxiter=max_iter)
        return float(root)
    except ValueError:
        # No sign change in interval
        return None
    except Exception:
        return None


def minimize_scalar(
    func: Callable[[float], float], bounds: Tuple[float, float], tol: float = CONVERGENCE_THRESHOLD
) -> Tuple[Optional[float], Optional[float]]:
    """
    Minimize scalar function.

    Args:
        func: Function to minimize
        bounds: (lower, upper) bounds
        tol: Tolerance

    Returns:
        Tuple of (minimum_x, minimum_value)
    """
    try:
        result = optimize.minimize_scalar(
            func, bounds=bounds, method="bounded", options={"xatol": tol}
        )

        if result.success:
            return float(result.x), float(result.fun)
        else:
            return None, None

    except Exception:
        return None, None


# ==============================================================================
# FINANCIAL CALCULATIONS
# ==============================================================================


def calculate_position_size(
    account_value: float,
    risk_percent: float,
    stop_loss_points: float,
    contract_multiplier: float = 1.0,
) -> int:
    """
    Calculate position size based on risk.

    Args:
        account_value: Total account value
        risk_percent: Risk percentage per trade
        stop_loss_points: Stop loss in points
        contract_multiplier: Contract multiplier

    Returns:
        Position size (number of contracts)
    """
    if stop_loss_points <= 0 or risk_percent <= 0:
        return 0

    # Calculate dollar risk
    dollar_risk = account_value * (risk_percent / 100)

    # Calculate position size
    position_size = dollar_risk / (stop_loss_points * contract_multiplier)

    return int(position_size)


def calculate_kelly_criterion(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """
    Calculate Kelly criterion for position sizing.

    Args:
        win_rate: Probability of winning (0-1)
        avg_win: Average win amount
        avg_loss: Average loss amount (positive)

    Returns:
        Kelly percentage (0-1)
    """
    if avg_loss <= 0 or win_rate <= 0 or win_rate >= 1:
        return 0.0

    # Calculate win/loss ratio
    win_loss_ratio = avg_win / avg_loss

    # Kelly formula: f = (p * b - q) / b
    # where p = win_rate, q = 1 - win_rate, b = win_loss_ratio
    kelly = (win_rate * win_loss_ratio - (1 - win_rate)) / win_loss_ratio

    # Limit to reasonable range
    return max(0.0, min(kelly, 0.25))  # Cap at 25%


def calculate_risk_reward_ratio(
    entry_price: float, target_price: float, stop_price: float
) -> float:
    """
    Calculate risk/reward ratio.

    Args:
        entry_price: Entry price
        target_price: Target price
        stop_price: Stop loss price

    Returns:
        Risk/reward ratio
    """
    risk = abs(entry_price - stop_price)
    reward = abs(target_price - entry_price)

    if risk == 0:
        return float("inf") if reward > 0 else 0.0

    return reward / risk


# ==============================================================================
# INTERPOLATION FUNCTIONS
# ==============================================================================


def linear_interpolation(x: float, x1: float, y1: float, x2: float, y2: float) -> float:
    """
    Linear interpolation between two points.

    Args:
        x: X value to interpolate at
        x1, y1: First point
        x2, y2: Second point

    Returns:
        Interpolated y value
    """
    if x2 == x1:
        return y1

    return y1 + (x - x1) * (y2 - y1) / (x2 - x1)


def cubic_spline_interpolation(
    x_points: List[float], y_points: List[float], x_new: Union[float, List[float]]
) -> Union[float, List[float]]:
    """
    Cubic spline interpolation.

    Args:
        x_points: X coordinates of data points
        y_points: Y coordinates of data points
        x_new: New x value(s) to interpolate

    Returns:
        Interpolated y value(s)
    """
    from scipy.interpolate import CubicSpline

    if len(x_points) < 2:
        raise ValueError("Need at least 2 points for interpolation")

    # Create cubic spline
    cs = CubicSpline(x_points, y_points)

    # Interpolate
    return float(cs(x_new)) if isinstance(x_new, (int, float)) else cs(x_new).tolist()


# ==============================================================================
# ARRAY OPERATIONS
# ==============================================================================


def rolling_window(
    data: List[float], window_size: int, func: Callable[[List[float]], float]
) -> List[float]:
    """
    Apply function over rolling window.

    Args:
        data: Input data
        window_size: Window size
        func: Function to apply to each window

    Returns:
        List of results
    """
    if window_size > len(data):
        return []

    results = []
    for i in range(window_size - 1, len(data)):
        window = data[i - window_size + 1 : i + 1]
        results.append(func(window))

    return results


def exponential_moving_average(data: List[float], period: int) -> List[float]:
    """
    Calculate exponential moving average.

    Args:
        data: Input data
        period: EMA period

    Returns:
        EMA values
    """
    if not data or period <= 0:
        return []

    alpha = 2 / (period + 1)
    ema = [data[0]]

    for i in range(1, len(data)):
        ema.append(alpha * data[i] + (1 - alpha) * ema[-1])

    return ema


# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================


# ==============================================================================
# MATHUTILS CLASS WRAPPER
# ==============================================================================
class MathUtils:
    """
    Mathematical utilities class wrapper.

    This class wraps all the mathematical utility functions for easier importing
    and organization. All methods are static methods.
    """

    @staticmethod
    def round_price(value: float, precision: int = PRICE_PRECISION) -> float:
        """Round a price to specified precision."""
        return round_price(value, precision)

    @staticmethod
    def round_to_tick(value: float, tick_size: float) -> float:
        """Round to nearest tick size."""
        return round_to_tick(value, tick_size)

    @staticmethod
    def calculate_percentage_change(old_value: float, new_value: float) -> float:
        """Calculate percentage change."""
        return calculate_percentage_change(old_value, new_value)

    @staticmethod
    def calculate_compound_return(returns: list) -> float:
        """Calculate compound return."""
        return calculate_compound_return(returns)

    @staticmethod
    def calculate_mean(values: list) -> float:
        """Calculate arithmetic mean."""
        return calculate_mean(values)

    @staticmethod
    def calculate_std_dev(values: list, sample: bool = True) -> float:
        """Calculate standard deviation."""
        return calculate_std_dev(values, sample)

    @staticmethod
    def calculate_sharpe_ratio(
        returns: list, risk_free_rate: float = 0.02, periods_per_year: int = TRADING_DAYS_PER_YEAR
    ) -> float:
        """Calculate Sharpe ratio."""
        return calculate_sharpe_ratio(returns, risk_free_rate, periods_per_year)

    @staticmethod
    def calculate_sortino_ratio(
        returns: list,
        risk_free_rate: float = 0.02,
        target_return: float = 0.0,
        periods_per_year: int = TRADING_DAYS_PER_YEAR,
    ) -> float:
        """Calculate Sortino ratio."""
        return calculate_sortino_ratio(returns, risk_free_rate, target_return, periods_per_year)


# ==============================================================================
# UPDATE MODULE EXPORTS
# ==============================================================================


__all__ = ["MathUtils"]
if __name__ == "__main__":
    # Test mathematical utilities
    print("Testing Mathematical Utilities...")

    # Test basic functions
    print(f"\nRound price 123.456: {round_price(123.456)}")
    print(f"Round to tick 123.456 (0.25): {round_to_tick(123.456, 0.25)}")
    print(f"Percentage change 100->110: {calculate_percentage_change(100, 110):.2f}%")

    # Test statistical functions
    returns = [0.01, -0.02, 0.015, 0.005, -0.01, 0.02, -0.005, 0.01]
    print(f"\nReturns: {returns}")
    print(f"Mean: {calculate_mean(returns):.4f}")
    print(f"Std Dev: {calculate_std_dev(returns):.4f}")
    print(f"Sharpe Ratio: {calculate_sharpe_ratio(returns):.2f}")
    print(f"VaR (95%): {calculate_var(returns, 0.95):.4f}")

    # Test probability functions
    print(
        f"\nProbability of touch (450->460, 20% vol, 30 days): "
        f"{calculate_probability_touch(450, 460, 0.20, 30):.2%}"
    )

    # Test position sizing
    position = calculate_position_size(100000, 1.0, 5.0, 100)
    print(f"\nPosition size ($100k, 1% risk, $5 stop): {position} contracts")
