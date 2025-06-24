#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Performance Metrics (Alternative to empyrical)
Module: SpyderU15_PerformanceMetrics.py
Group: U (Utilities)
Purpose: Calculate trading performance metrics

Description:
    This module provides essential performance metrics as an alternative
    to the empyrical package which has Python 3.13 compatibility issues.
    Includes Sharpe ratio, max drawdown, Calmar ratio, and other key metrics.

Author: Mohamed Talib
Date: 2025-06-23
Version: 1.0
"""

import numpy as np
import pandas as pd
from typing import Union, Optional

def sharpe_ratio(returns: Union[pd.Series, np.ndarray], 
                risk_free_rate: float = 0.0,
                periods: int = 252) -> float:
    """
    Calculate Sharpe ratio
    
    Args:
        returns: Return series
        risk_free_rate: Risk-free rate (annualized)
        periods: Number of periods per year (252 for daily)
    
    Returns:
        Sharpe ratio
    """
    if len(returns) < 2:
        return 0.0
    
    excess_returns = returns - risk_free_rate / periods
    if excess_returns.std() == 0:
        return 0.0
    
    return np.sqrt(periods) * excess_returns.mean() / excess_returns.std()

def max_drawdown(returns: Union[pd.Series, np.ndarray]) -> float:
    """
    Calculate maximum drawdown
    
    Args:
        returns: Return series
    
    Returns:
        Maximum drawdown (negative value)
    """
    cumulative = (1 + returns).cumprod()
    running_max = cumulative.expanding().max()
    drawdown = (cumulative - running_max) / running_max
    return drawdown.min()

def calmar_ratio(returns: Union[pd.Series, np.ndarray],
                periods: int = 252) -> float:
    """
    Calculate Calmar ratio (Annual return / Max drawdown)
    
    Args:
        returns: Return series
        periods: Number of periods per year
    
    Returns:
        Calmar ratio
    """
    annual_return = (1 + returns.mean()) ** periods - 1
    max_dd = abs(max_drawdown(returns))
    
    if max_dd == 0:
        return 0.0
    
    return annual_return / max_dd

def sortino_ratio(returns: Union[pd.Series, np.ndarray],
                 target_return: float = 0.0,
                 periods: int = 252) -> float:
    """
    Calculate Sortino ratio
    
    Args:
        returns: Return series
        target_return: Target return threshold
        periods: Number of periods per year
    
    Returns:
        Sortino ratio
    """
    excess_returns = returns - target_return / periods
    downside_returns = excess_returns[excess_returns < 0]
    
    if len(downside_returns) == 0:
        return np.inf
    
    downside_deviation = np.sqrt((downside_returns ** 2).mean())
    
    if downside_deviation == 0:
        return 0.0
    
    return np.sqrt(periods) * excess_returns.mean() / downside_deviation

def calculate_all_metrics(returns: Union[pd.Series, np.ndarray]) -> dict:
    """
    Calculate all performance metrics
    
    Args:
        returns: Return series
    
    Returns:
        Dictionary of performance metrics
    """
    return {
        'total_return': (1 + returns).prod() - 1,
        'annual_return': (1 + returns.mean()) ** 252 - 1,
        'annual_volatility': returns.std() * np.sqrt(252),
        'sharpe_ratio': sharpe_ratio(returns),
        'sortino_ratio': sortino_ratio(returns),
        'max_drawdown': max_drawdown(returns),
        'calmar_ratio': calmar_ratio(returns),
        'win_rate': (returns > 0).mean(),
        'avg_win': returns[returns > 0].mean(),
        'avg_loss': returns[returns < 0].mean(),
    }
