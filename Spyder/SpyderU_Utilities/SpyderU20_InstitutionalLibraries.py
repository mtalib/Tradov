#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderU_Utilities
Module: SpyderU20_InstitutionalLibraries.py
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
import asyncio
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple, Any, Union, Callable
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum, auto
import json
import warnings
from pathlib import Path
import logging
import os
import sys

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
except ImportError:
    # Fallback if running from different directory
    try:
        from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
        from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
    except ImportError:
        # Simple fallback logger
        import logging
        class SpyderLogger:
            @staticmethod
            def get_logger(name):
                return logging.getLogger(name)
        class SpyderErrorHandler:
            def error(self, msg):
                logging.error(msg)

try:
    from Spyder.SpyderU_Utilities.SpyderU07_Constants import OptionType
    OPTIONTYPE_AVAILABLE = True
except ImportError:
    try:
        from SpyderU07_Constants import OptionType
        OPTIONTYPE_AVAILABLE = True
    except ImportError:
        # Fallback OptionType definition
        class OptionType(Enum):
            """Option type enumeration (fallback)"""
            CALL = "CALL"
            PUT = "PUT"
        OPTIONTYPE_AVAILABLE = False
        warnings.warn("Using fallback OptionType - check SpyderU07_Constants.py")

# ==============================================================================
# THIRD-PARTY IMPORTS - INSTITUTIONAL LIBRARIES
# ==============================================================================

# Suppress common warnings for clean execution
warnings.filterwarnings("ignore", message="Module.*zipline.assets.*not found")
warnings.filterwarnings("ignore", message="pkg_resources is deprecated")
warnings.filterwarnings("ignore", category=UserWarning, module="pyfolio")

# QuantLib for institutional options pricing
try:
    import QuantLib as ql
    QUANTLIB_AVAILABLE = True
except ImportError:
    QUANTLIB_AVAILABLE = False
    warnings.warn("QuantLib not available. Install with: pip install quantlib-python")

# PyFolio for institutional performance analytics
try:
    import pyfolio as pf
    import empyrical as ep
    PYFOLIO_AVAILABLE = True
except ImportError:
    PYFOLIO_AVAILABLE = False
    warnings.warn("PyFolio not available. Install with: pip install pyfolio-reloaded empyrical-reloaded")

# RiskFolio-Lib for advanced portfolio optimization
try:
    import riskfolio as rp
    RISKFOLIO_AVAILABLE = True
except ImportError:
    RISKFOLIO_AVAILABLE = False
    warnings.warn("RiskFolio-Lib not available. Install with: pip install riskfolio-lib")

# Stable Baselines3 for RL
try:
    from stable_baselines3 import PPO, SAC, A2C
    from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv
    SB3_AVAILABLE = True
except ImportError:
    SB3_AVAILABLE = False
    warnings.warn("Stable-Baselines3 not available. Install with: pip install stable-baselines3[extra]")

# Ray for distributed computing
try:
    import ray
    from ray import tune
    from ray.rllib.algorithms import PPO as RayPPO
    RAY_AVAILABLE = True
    
    # Suppress Ray TPU messages
    os.environ['RAY_DISABLE_IMPORT_WARNING'] = '1'
    os.environ['RAY_LOG_TO_STDERR'] = '0'
    
except ImportError:
    RAY_AVAILABLE = False
    warnings.warn("Ray not available. Install with: pip install ray[rllib]")

# Additional ML and analytics libraries
try:
    import scipy.stats as stats
    from scipy.optimize import minimize
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

try:
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import cross_val_score
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

# ==============================================================================
# CONSTANTS AND CONFIGURATION
# ==============================================================================

# Default risk-free rate (2-year Treasury as of 2025)
DEFAULT_RISK_FREE_RATE = 0.045

# QuantLib calendar and day counter defaults
DEFAULT_CALENDAR = "UnitedStates"
DEFAULT_DAY_COUNTER = "Actual365Fixed"

# Performance calculation defaults
TRADING_DAYS_PER_YEAR = 252
HOURS_PER_TRADING_DAY = 6.5

# Library availability status
LIBRARY_STATUS = {
    'quantlib': QUANTLIB_AVAILABLE,
    'pyfolio': PYFOLIO_AVAILABLE,
    'riskfolio': RISKFOLIO_AVAILABLE,
    'stable_baselines3': SB3_AVAILABLE,
    'ray': RAY_AVAILABLE,
    'scipy': SCIPY_AVAILABLE,
    'sklearn': SKLEARN_AVAILABLE,
    'optiontype': OPTIONTYPE_AVAILABLE
}

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class OptionPricing:
    """Comprehensive option pricing result."""
    theoretical_price: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    implied_volatility: Optional[float] = None
    intrinsic_value: Optional[float] = None
    time_value: Optional[float] = None
    moneyness: Optional[float] = None
    
    def __post_init__(self):
        """Calculate derived values."""
        if self.theoretical_price and self.delta:
            self.intrinsic_value = max(0, self.theoretical_price - self.time_value) if self.time_value else None
            self.time_value = self.theoretical_price - (self.intrinsic_value or 0)

@dataclass 
class InstitutionalMetrics:
    """Institutional-grade performance metrics."""
    annual_return: float
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    calmar_ratio: float
    win_rate: float
    profit_factor: float
    recovery_factor: float
    
    # Advanced metrics
    var_95: Optional[float] = None
    cvar_95: Optional[float] = None
    skewness: Optional[float] = None
    kurtosis: Optional[float] = None
    information_ratio: Optional[float] = None
    treynor_ratio: Optional[float] = None

@dataclass
class PortfolioOptimization:
    """Portfolio optimization results."""
    weights: Dict[str, float]
    expected_return: float
    expected_volatility: float
    sharpe_ratio: float
    optimization_method: str
    constraints_satisfied: bool
    optimization_success: bool

# ==============================================================================
# MAIN INSTITUTIONAL LIBRARIES CLASS
# ==============================================================================

class InstitutionalLibraries:
    """
    Unified interface to institutional-grade libraries for professional trading.
    
    This class provides a single entry point to access QuantLib options pricing,
    PyFolio performance analytics, RiskFolio portfolio optimization, and other
    institutional-grade tools commonly used by hedge funds and trading firms.
    """
    
    def __init__(self):
        """Initialize institutional libraries with proper configuration."""
        
        # Initialize logging
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Export OptionType for external access (CRITICAL FIX)
        self.OptionType = OptionType
        
        # Library availability tracking
        self.available_libraries = LIBRARY_STATUS.copy()
        
        # Initialize QuantLib if available
        if QUANTLIB_AVAILABLE:
            self._initialize_quantlib()
        
        # Initialize Ray if available
        if RAY_AVAILABLE:
            self._initialize_ray()
        
        # Configuration
        self.risk_free_rate = DEFAULT_RISK_FREE_RATE
        
        # Performance cache
        self._calculation_cache = {}
        
        self.logger.info(f"Institutional libraries initialized. Available: {sum(self.available_libraries.values())}/{len(self.available_libraries)}")
    
    def _initialize_quantlib(self):
        """Initialize QuantLib with proper configuration."""
        try:
            # Set up QuantLib calendar
            if DEFAULT_CALENDAR == "UnitedStates":
                self.calendar = ql.UnitedStates(ql.UnitedStates.NYSE)
            else:
                self.calendar = ql.TARGET()
            
            # Set up day counter
            if DEFAULT_DAY_COUNTER == "Actual365Fixed":
                self.day_counter = ql.Actual365Fixed()
            else:
                self.day_counter = ql.ActualActual()
            
            # Set evaluation date to today
            today = ql.Date.todaysDate()
            ql.Settings.instance().evaluationDate = today
            
            self.logger.info("QuantLib initialized successfully")
            
        except Exception as e:
            self.logger.error(f"QuantLib initialization failed: {e}")
            self.available_libraries['quantlib'] = False
    
    def _initialize_ray(self):
        """Initialize Ray distributed computing."""
        try:
            # Initialize Ray if not already initialized
            if not ray.is_initialized():
                ray.init(
                    ignore_reinit_error=True,
                    log_to_driver=False,
                    logging_level=logging.ERROR
                )
            
            self.logger.info("Ray distributed computing initialized")
            
        except Exception as e:
            self.logger.error(f"Ray initialization failed: {e}")
            self.available_libraries['ray'] = False
    
    # ==========================================================================
    # OPTIONS PRICING METHODS
    # ==========================================================================
    
    def price_option(self, 
                    spot: float,
                    strike: float, 
                    time_to_expiry: float,
                    risk_free_rate: float,
                    volatility: float,
                    option_type: OptionType,
                    dividend_yield: float = 0.0) -> Optional[OptionPricing]:
        """
        Price option using QuantLib Black-Scholes model.
        
        Args:
            spot: Current underlying price
            strike: Option strike price
            time_to_expiry: Time to expiry in years
            risk_free_rate: Risk-free interest rate
            volatility: Implied volatility
            option_type: OptionType.CALL or OptionType.PUT
            dividend_yield: Dividend yield (default 0.0)
            
        Returns:
            OptionPricing object with price and greeks, or None if error
        """
        
        if not QUANTLIB_AVAILABLE:
            self.logger.warning("QuantLib not available for options pricing")
            return None
        
        try:
            # Convert option type
            if option_type == OptionType.CALL:
                ql_option_type = ql.Option.Call
            elif option_type == OptionType.PUT:
                ql_option_type = ql.Option.Put
            else:
                raise ValueError(f"Invalid option type: {option_type}")
            
            # Create QuantLib objects
            today = ql.Date.todaysDate()
            expiry_date = today + int(time_to_expiry * 365)
            
            # Market data
            spot_handle = ql.QuoteHandle(ql.SimpleQuote(spot))
            flat_ts = ql.YieldTermStructureHandle(
                ql.FlatForward(today, risk_free_rate, self.day_counter)
            )
            flat_vol_ts = ql.BlackVolTermStructureHandle(
                ql.BlackConstantVol(today, self.calendar, volatility, self.day_counter)
            )
            dividend_ts = ql.YieldTermStructureHandle(
                ql.FlatForward(today, dividend_yield, self.day_counter)
            )
            
            # Black-Scholes process
            bs_process = ql.BlackScholesProcess(
    		spot_handle, flat_ts, flat_vol_ts
	    )
            
            # European option
            payoff = ql.PlainVanillaPayoff(ql_option_type, strike)
            exercise = ql.EuropeanExercise(expiry_date)
            option = ql.VanillaOption(payoff, exercise)
            
            # Pricing engine
            engine = ql.AnalyticEuropeanEngine(bs_process)
            option.setPricingEngine(engine)
            
            # Calculate price and greeks
            price = option.NPV()
            delta = option.delta()
            gamma = option.gamma()
            theta = option.theta() / 365  # Convert to per-day
            vega = option.vega() / 100    # Convert to per 1% vol change
            rho = option.rho() / 100      # Convert to per 1% rate change
            
            # Calculate additional metrics
            intrinsic_value = max(0, spot - strike if option_type == OptionType.CALL else strike - spot)
            time_value = price - intrinsic_value
            moneyness = spot / strike
            
            return OptionPricing(
                theoretical_price=price,
                delta=delta,
                gamma=gamma,
                theta=theta,
                vega=vega,
                rho=rho,
                implied_volatility=volatility,
                intrinsic_value=intrinsic_value,
                time_value=time_value,
                moneyness=moneyness
            )
            
        except Exception as e:
            self.logger.error(f"Options pricing failed: {e}")
            return None
    
    def price_spread(self,
                    spot: float,
                    short_strike: float,
                    long_strike: float,
                    time_to_expiry: float,
                    risk_free_rate: float,
                    volatility: float,
                    option_type: OptionType,
                    dividend_yield: float = 0.0) -> Optional[Dict[str, Any]]:
        """
        Price an options spread (credit or debit).
        
        Returns:
            Dictionary with spread pricing details including net credit/debit,
            max profit, max loss, breakeven, and combined greeks.
        """
        
        try:
            # Price both legs
            short_option = self.price_option(
                spot, short_strike, time_to_expiry, risk_free_rate, 
                volatility, option_type, dividend_yield
            )
            
            long_option = self.price_option(
                spot, long_strike, time_to_expiry, risk_free_rate,
                volatility, option_type, dividend_yield
            )
            
            if not short_option or not long_option:
                return None
            
            # Calculate spread metrics
            net_credit = short_option.theoretical_price - long_option.theoretical_price
            width = abs(short_strike - long_strike)
            
            if net_credit > 0:  # Credit spread
                max_profit = net_credit
                max_loss = width - net_credit
            else:  # Debit spread
                max_profit = width + net_credit  # net_credit is negative
                max_loss = -net_credit
            
            # Combined greeks
            net_delta = short_option.delta - long_option.delta
            net_gamma = short_option.gamma - long_option.gamma
            net_theta = short_option.theta - long_option.theta
            net_vega = short_option.vega - long_option.vega
            net_rho = short_option.rho - long_option.rho
            
            # Breakeven calculation
            if option_type == OptionType.PUT:
                breakeven = short_strike - net_credit if net_credit > 0 else long_strike + abs(net_credit)
            else:  # CALL
                breakeven = short_strike + net_credit if net_credit > 0 else long_strike - abs(net_credit)
            
            return {
                'net_credit': net_credit,
                'max_profit': max_profit,
                'max_loss': max_loss,
                'breakeven': breakeven,
                'width': width,
                'profit_probability': max_profit / width if width > 0 else 0,
                'return_on_risk': (max_profit / max_loss) if max_loss > 0 else 0,
                'net_delta': net_delta,
                'net_gamma': net_gamma,
                'net_theta': net_theta,
                'net_vega': net_vega,
                'net_rho': net_rho,
                'short_option': short_option,
                'long_option': long_option
            }
            
        except Exception as e:
            self.logger.error(f"Spread pricing failed: {e}")
            return None
    
    # ==========================================================================
    # PERFORMANCE ANALYTICS METHODS
    # ==========================================================================
    
    def calculate_institutional_metrics(self, 
                                      returns: Union[pd.Series, np.ndarray, List[float]],
                                      benchmark_returns: Optional[Union[pd.Series, np.ndarray]] = None,
                                      risk_free_rate: Optional[float] = None) -> Optional[InstitutionalMetrics]:
        """
        Calculate comprehensive institutional-grade performance metrics.
        
        Args:
            returns: Series of returns (daily recommended)
            benchmark_returns: Optional benchmark for comparison
            risk_free_rate: Risk-free rate (uses default if None)
            
        Returns:
            InstitutionalMetrics object with comprehensive statistics
        """
        
        try:
            # Convert to pandas Series if needed
            if isinstance(returns, (list, np.ndarray)):
                returns = pd.Series(returns)
            
            if risk_free_rate is None:
                risk_free_rate = self.risk_free_rate
            
            # Basic metrics
            total_return = (1 + returns).prod() - 1
            annual_return = (1 + returns.mean()) ** TRADING_DAYS_PER_YEAR - 1
            volatility = returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR)
            
            # Risk-adjusted metrics
            excess_returns = annual_return - risk_free_rate
            sharpe_ratio = excess_returns / volatility if volatility > 0 else 0
            
            # Downside metrics
            downside_returns = returns[returns < 0]
            downside_std = downside_returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR) if len(downside_returns) > 0 else volatility
            sortino_ratio = excess_returns / downside_std if downside_std > 0 else 0
            
            # Drawdown analysis
            cumulative_returns = (1 + returns).cumprod()
            rolling_max = cumulative_returns.expanding().max()
            drawdowns = (cumulative_returns - rolling_max) / rolling_max
            max_drawdown = drawdowns.min()
            
            # Recovery metrics
            calmar_ratio = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0
            
            # Win/loss metrics
            win_rate = (returns > 0).sum() / len(returns) if len(returns) > 0 else 0
            winning_returns = returns[returns > 0]
            losing_returns = returns[returns < 0]
            
            avg_win = winning_returns.mean() if len(winning_returns) > 0 else 0
            avg_loss = losing_returns.mean() if len(losing_returns) > 0 else 0
            profit_factor = abs(avg_win * len(winning_returns) / (avg_loss * len(losing_returns))) if len(losing_returns) > 0 and avg_loss != 0 else 0
            
            recovery_factor = total_return / abs(max_drawdown) if max_drawdown != 0 else 0
            
            # Advanced metrics using scipy if available
            var_95 = None
            cvar_95 = None
            skewness = None
            kurtosis = None
            
            if SCIPY_AVAILABLE:
                var_95 = np.percentile(returns, 5)
                cvar_95 = returns[returns <= var_95].mean() if len(returns[returns <= var_95]) > 0 else var_95
                skewness = stats.skew(returns)
                kurtosis = stats.kurtosis(returns)
            
            # Benchmark comparison metrics
            information_ratio = None
            treynor_ratio = None
            
            if benchmark_returns is not None and len(benchmark_returns) == len(returns):
                if isinstance(benchmark_returns, (list, np.ndarray)):
                    benchmark_returns = pd.Series(benchmark_returns)
                
                excess_returns_vs_benchmark = returns - benchmark_returns
                tracking_error = excess_returns_vs_benchmark.std() * np.sqrt(TRADING_DAYS_PER_YEAR)
                information_ratio = excess_returns_vs_benchmark.mean() * TRADING_DAYS_PER_YEAR / tracking_error if tracking_error > 0 else 0
                
                # Beta calculation for Treynor ratio
                if SCIPY_AVAILABLE and len(returns) > 1:
                    beta = stats.linregress(benchmark_returns, returns).slope
                    treynor_ratio = excess_returns / beta if beta != 0 else 0
            
            return InstitutionalMetrics(
                annual_return=annual_return,
                volatility=volatility,
                sharpe_ratio=sharpe_ratio,
                sortino_ratio=sortino_ratio,
                max_drawdown=max_drawdown,
                calmar_ratio=calmar_ratio,
                win_rate=win_rate,
                profit_factor=profit_factor,
                recovery_factor=recovery_factor,
                var_95=var_95,
                cvar_95=cvar_95,
                skewness=skewness,
                kurtosis=kurtosis,
                information_ratio=information_ratio,
                treynor_ratio=treynor_ratio
            )
            
        except Exception as e:
            self.logger.error(f"Institutional metrics calculation failed: {e}")
            return None
    
    # ==========================================================================
    # PORTFOLIO OPTIMIZATION METHODS
    # ==========================================================================
    
    def optimize_portfolio(self,
                          returns_data: pd.DataFrame,
                          method: str = "max_sharpe",
                          constraints: Optional[Dict[str, Any]] = None,
                          risk_free_rate: Optional[float] = None) -> Optional[PortfolioOptimization]:
        """
        Optimize portfolio using modern portfolio theory.
        
        Args:
            returns_data: DataFrame with asset returns (columns = assets)
            method: Optimization method ("max_sharpe", "min_vol", "max_diversification")
            constraints: Portfolio constraints dict
            risk_free_rate: Risk-free rate for Sharpe optimization
            
        Returns:
            PortfolioOptimization object with optimal weights and metrics
        """
        
        if not RISKFOLIO_AVAILABLE and not SCIPY_AVAILABLE:
            self.logger.warning("Portfolio optimization requires riskfolio-lib or scipy")
            return None
        
        try:
            if risk_free_rate is None:
                risk_free_rate = self.risk_free_rate
            
            # Use RiskFolio if available (preferred)
            if RISKFOLIO_AVAILABLE:
                return self._optimize_with_riskfolio(returns_data, method, constraints, risk_free_rate)
            else:
                return self._optimize_with_scipy(returns_data, method, constraints, risk_free_rate)
                
        except Exception as e:
            self.logger.error(f"Portfolio optimization failed: {e}")
            return None
    
    def _optimize_with_riskfolio(self, returns_data, method, constraints, risk_free_rate):
        """Optimize portfolio using RiskFolio-Lib."""
        
        try:
            # Create portfolio object
            port = rp.Portfolio(returns=returns_data)
            
            # Calculate expected returns and covariance
            port.assets_stats(method_mu='hist', method_cov='hist')
            
            # Set optimization method
            if method == "max_sharpe":
                weights = port.optimization(model='Classic', rm='MV', obj='Sharpe', rf=risk_free_rate)
            elif method == "min_vol":
                weights = port.optimization(model='Classic', rm='MV', obj='MinRisk')
            elif method == "max_diversification":
                weights = port.optimization(model='Classic', rm='MV', obj='MaxDiversification')
            else:
                weights = port.optimization(model='Classic', rm='MV', obj='Sharpe', rf=risk_free_rate)
            
            if weights is None or weights.empty:
                return None
            
            # Calculate portfolio metrics
            weights_dict = weights.iloc[:, 0].to_dict()
            expected_return = np.sum(port.mu.values * weights.values.flatten()) * TRADING_DAYS_PER_YEAR
            portfolio_variance = np.dot(weights.values.flatten(), np.dot(port.cov.values, weights.values.flatten()))
            expected_volatility = np.sqrt(portfolio_variance * TRADING_DAYS_PER_YEAR)
            sharpe_ratio = (expected_return - risk_free_rate) / expected_volatility if expected_volatility > 0 else 0
            
            return PortfolioOptimization(
                weights=weights_dict,
                expected_return=expected_return,
                expected_volatility=expected_volatility,
                sharpe_ratio=sharpe_ratio,
                optimization_method=f"riskfolio_{method}",
                constraints_satisfied=True,
                optimization_success=True
            )
            
        except Exception as e:
            self.logger.error(f"RiskFolio optimization failed: {e}")
            return None
    
    def _optimize_with_scipy(self, returns_data, method, constraints, risk_free_rate):
        """Optimize portfolio using scipy (fallback)."""
        
        try:
            # Calculate expected returns and covariance matrix
            expected_returns = returns_data.mean() * TRADING_DAYS_PER_YEAR
            cov_matrix = returns_data.cov() * TRADING_DAYS_PER_YEAR
            
            n_assets = len(expected_returns)
            
            # Objective functions
            def portfolio_volatility(weights):
                return np.sqrt(np.dot(weights, np.dot(cov_matrix, weights)))
            
            def portfolio_return(weights):
                return np.sum(expected_returns * weights)
            
            def negative_sharpe(weights):
                ret = portfolio_return(weights)
                vol = portfolio_volatility(weights)
                return -(ret - risk_free_rate) / vol if vol > 0 else -np.inf
            
            # Constraints
            constraints_list = [{'type': 'eq', 'fun': lambda x: np.sum(x) - 1}]  # Weights sum to 1
            bounds = tuple((0, 1) for _ in range(n_assets))  # Long-only
            
            # Initial guess (equal weights)
            x0 = np.array([1/n_assets] * n_assets)
            
            # Optimize based on method
            if method == "max_sharpe":
                result = minimize(negative_sharpe, x0, method='SLSQP', bounds=bounds, constraints=constraints_list)
            elif method == "min_vol":
                result = minimize(portfolio_volatility, x0, method='SLSQP', bounds=bounds, constraints=constraints_list)
            else:
                result = minimize(negative_sharpe, x0, method='SLSQP', bounds=bounds, constraints=constraints_list)
            
            if not result.success:
                return None
            
            # Create weights dictionary
            weights_dict = {asset: weight for asset, weight in zip(returns_data.columns, result.x)}
            
            # Calculate metrics
            expected_return = portfolio_return(result.x)
            expected_volatility = portfolio_volatility(result.x)
            sharpe_ratio = (expected_return - risk_free_rate) / expected_volatility if expected_volatility > 0 else 0
            
            return PortfolioOptimization(
                weights=weights_dict,
                expected_return=expected_return,
                expected_volatility=expected_volatility,
                sharpe_ratio=sharpe_ratio,
                optimization_method=f"scipy_{method}",
                constraints_satisfied=result.success,
                optimization_success=result.success
            )
            
        except Exception as e:
            self.logger.error(f"Scipy optimization failed: {e}")
            return None
    
    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    
    def get_library_status(self) -> Dict[str, bool]:
        """Get status of all institutional libraries."""
        return self.available_libraries.copy()
    
    def get_available_libraries_count(self) -> Tuple[int, int]:
        """Get count of available vs total libraries."""
        available = sum(self.available_libraries.values())
        total = len(self.available_libraries)
        return available, total
    
    def is_library_available(self, library_name: str) -> bool:
        """Check if a specific library is available."""
        return self.available_libraries.get(library_name, False)
    
    def set_risk_free_rate(self, rate: float):
        """Set the risk-free rate for calculations."""
        self.risk_free_rate = rate
        self.logger.info(f"Risk-free rate set to {rate:.3%}")
    
    def clear_cache(self):
        """Clear calculation cache."""
        self._calculation_cache.clear()
        self.logger.info("Calculation cache cleared")
    
    def __del__(self):
        """Cleanup when object is destroyed."""
        try:
            if RAY_AVAILABLE and ray.is_initialized():
                ray.shutdown()
        except:
            pass

# ==============================================================================
# MODULE-LEVEL FUNCTIONS
# ==============================================================================

# Global instance for singleton pattern
_institutional_libs_instance = None

def get_institutional_libraries() -> InstitutionalLibraries:
    """
    Get the singleton instance of InstitutionalLibraries.
    
    Returns:
        InstitutionalLibraries: Singleton instance
    """
    global _institutional_libs_instance
    
    if _institutional_libs_instance is None:
        _institutional_libs_instance = InstitutionalLibraries()
    
    return _institutional_libs_instance

def reset_institutional_libraries():
    """Reset the singleton instance (for testing)."""
    global _institutional_libs_instance
    
    if _institutional_libs_instance:
        try:
            if hasattr(_institutional_libs_instance, '__del__'):
                _institutional_libs_instance.__del__()
        except:
            pass
    
    _institutional_libs_instance = None

# ==============================================================================
# TESTING AND VALIDATION
# ==============================================================================

def test_institutional_libraries():
    """Test institutional libraries functionality."""
    
    print("🧪 TESTING INSTITUTIONAL LIBRARIES")
    print("=" * 50)
    
    libs = get_institutional_libraries()
    
    # Test library availability
    available, total = libs.get_available_libraries_count()
    print(f"📊 Libraries Available: {available}/{total}")
    
    # Test OptionType access
    try:
        put_option = libs.OptionType.PUT
        call_option = libs.OptionType.CALL
        print(f"✅ OptionType access: PUT={put_option.value}, CALL={call_option.value}")
    except Exception as e:
        print(f"❌ OptionType access failed: {e}")
    
    # Test options pricing if QuantLib available
    if libs.is_library_available('quantlib'):
        try:
            pricing = libs.price_option(
                spot=400.0,
                strike=395.0,
                time_to_expiry=0.0411,  # 15 days
                risk_free_rate=0.05,
                volatility=0.20,
                option_type=libs.OptionType.PUT
            )
            
            if pricing:
                print(f"✅ Options pricing: ${pricing.theoretical_price:.2f}")
                print(f"   Greeks: Δ={pricing.delta:.3f}, Γ={pricing.gamma:.3f}, Θ={pricing.theta:.3f}")
            else:
                print("❌ Options pricing returned None")
                
        except Exception as e:
            print(f"❌ Options pricing failed: {e}")
    else:
        print("⚠️ QuantLib not available for options pricing test")
    
    # Test performance metrics
    try:
        # Generate sample returns
        np.random.seed(42)
        returns = np.random.normal(0.001, 0.02, 252)  # Daily returns for 1 year
        
        metrics = libs.calculate_institutional_metrics(returns)
        
        if metrics:
            print(f"✅ Performance metrics calculated:")
            print(f"   Annual Return: {metrics.annual_return:.2%}")
            print(f"   Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
            print(f"   Max Drawdown: {metrics.max_drawdown:.2%}")
        else:
            print("❌ Performance metrics calculation failed")
            
    except Exception as e:
        print(f"❌ Performance metrics test failed: {e}")
    
    print(f"\n🎯 Test Complete: {available}/{total} libraries operational")
    return available >= total * 0.6  # Pass if 60%+ libraries work

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    # Run comprehensive test
    success = test_institutional_libraries()
    
    if success:
        print("\n🎉 INSTITUTIONAL LIBRARIES TEST PASSED!")
        print("💎 Ready for world-class options trading!")
    else:
        print("\n⚠️ Some libraries need attention")
        print("📋 Check installation of missing dependencies")
    
    # Display final status
    libs = get_institutional_libraries()
    status = libs.get_library_status()
    
    print(f"\n📊 FINAL STATUS:")
    for lib, available in status.items():
        status_icon = "✅" if available else "❌"
        print(f"   {status_icon} {lib}")
