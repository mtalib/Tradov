#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

SPYDER - Autonomous Options Trading System v1.0

Series: SpyderV_QuantModels
Module: SpyderV10_GARCH.py
Purpose: GARCH volatility modeling and forecasting for options trading.
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-29 Time: 14:00:00

Module Description:
    This module implements GARCH (Generalized Autoregressive Conditional
    Heteroskedasticity) models for volatility forecasting. GARCH models
    capture the empirical fact that volatility clusters over time - periods
    of high volatility tend to be followed by high volatility, and calm
    periods by calm periods. This module serves as the volatility forecasting
    engine for the entire Spyder system, providing dynamic volatility inputs
    to all pricing models.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from typing import Dict, Any, Tuple, Optional, List
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import warnings

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import norm, jarque_bera, ljungbox
import matplotlib.pyplot as plt

# ==============================================================================
# MODULE IMPLEMENTATION
# ==============================================================================
warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class GARCHParameters:
    """Parameters for the GARCH model."""
    omega: float = 0.000001    # Constant term
    alpha: float = 0.1         # ARCH coefficient (short-term persistence)
    beta: float = 0.85         # GARCH coefficient (long-term persistence)
    
    def validate(self) -> bool:
        """Validate GARCH parameters for stationarity and positivity."""
        return (self.omega > 0 and self.alpha >= 0 and self.beta >= 0 and 
                self.alpha + self.beta < 1.0)  # Stationarity condition
    
    def unconditional_variance(self) -> float:
        """Calculate long-run unconditional variance."""
        if self.alpha + self.beta >= 1.0:
            return float('inf')
        return self.omega / (1 - self.alpha - self.beta)

class SpyderGARCHModel:
    """
    GARCH volatility modeling and forecasting system.
    
    Features:
    - GARCH(1,1) estimation using Maximum Likelihood
    - Multi-step ahead volatility forecasting
    - Model diagnostics and validation
    - Real-time volatility updates
    - Integration with options pricing models
    """
    
    def __init__(self, 
                 model_type: str = 'garch',
                 distribution: str = 'normal'):
        self.model_type = model_type.lower()
        self.distribution = distribution.lower()
        self.parameters: Optional[GARCHParameters] = None
        self.fitted_data: Optional[pd.Series] = None
        self.conditional_volatility: Optional[np.ndarray] = None
        self.log_likelihood: Optional[float] = None
        self.estimation_results: Dict[str, Any] = {}
        
    def fit(self, returns: pd.Series, method: str = 'MLE') -> Dict[str, Any]:
        """
        Fit GARCH model to return data.
        
        Args:
            returns: Time series of returns
            method: Estimation method ('MLE' for Maximum Likelihood)
            
        Returns:
            Dictionary with estimation results
        """
        if len(returns) < 50:
            raise ValueError("Need at least 50 observations to fit GARCH model")
        
        logger.info(f"Fitting GARCH model to {len(returns)} observations...")
        
        # Store data
        self.fitted_data = returns.copy()
        
        # Initial parameter estimates
        initial_params = self._get_initial_parameters(returns)
        
        # Maximum likelihood estimation
        if method.upper() == 'MLE':
            result = self._mle_estimation(returns, initial_params)
        else:
            raise ValueError(f"Unknown estimation method: {method}")
        
        # Store results
        self.parameters = GARCHParameters(
            omega=result['params'][0],
            alpha=result['params'][1], 
            beta=result['params'][2]
        )
        
        self.log_likelihood = result['log_likelihood']
        self.conditional_volatility = result['conditional_volatility']
        
        # Calculate diagnostics
        self.estimation_results = {
            'parameters': self.parameters,
            'log_likelihood': self.log_likelihood,
            'aic': -2 * self.log_likelihood + 2 * 3,  # 3 parameters
            'bic': -2 * self.log_likelihood + np.log(len(returns)) * 3,
            'convergence': result['convergence'],
            'num_iterations': result.get('num_iterations', 0),
            'estimation_time': result.get('estimation_time', 0)
        }
        
        # Model validation
        self._validate_model(returns)
        
        logger.info(f"GARCH estimation completed. Log-likelihood: {self.log_likelihood:.2f}")
        
        return self.estimation_results
    
    def _get_initial_parameters(self, returns: pd.Series) -> np.ndarray:
        """Get initial parameter estimates for optimization."""
        # Use sample variance for initial omega
        sample_var = np.var(returns)
        
        # Standard initial values
        omega_init = sample_var * 0.01
        alpha_init = 0.1
        beta_init = 0.8
        
        return np.array([omega_init, alpha_init, beta_init])
    
    def _mle_estimation(self, returns: pd.Series, initial_params: np.ndarray) -> Dict[str, Any]:
        """Maximum Likelihood Estimation of GARCH parameters."""
        start_time = datetime.now()
        
        def negative_log_likelihood(params):
            omega, alpha, beta = params
            
            # Parameter constraints
            if omega <= 0 or alpha < 0 or beta < 0 or alpha + beta >= 1:
                return 1e6
            
            # Calculate conditional variances
            T = len(returns)
            sigma2 = np.zeros(T)
            sigma2[0] = np.var(returns)  # Initial variance
            
            for t in range(1, T):
                sigma2[t] = omega + alpha * returns.iloc[t-1]**2 + beta * sigma2[t-1]
            
            # Avoid numerical issues
            sigma2 = np.maximum(sigma2, 1e-8)
            
            # Log-likelihood calculation
            if self.distribution == 'normal':
                log_likelihood = -0.5 * np.sum(np.log(2 * np.pi * sigma2) + returns**2 / sigma2)
            else:
                raise ValueError(f"Distribution {self.distribution} not implemented")
            
            return -log_likelihood
        
        # Optimization constraints
        constraints = [
            {'type': 'ineq', 'fun': lambda x: x[0]},  # omega > 0
            {'type': 'ineq', 'fun': lambda x: x[1]},  # alpha >= 0
            {'type': 'ineq', 'fun': lambda x: x[2]},  # beta >= 0
            {'type': 'ineq', 'fun': lambda x: 0.999 - x[1] - x[2]}  # alpha + beta < 1
        ]
        
        # Bounds
        bounds = [(1e-8, 1), (0, 1), (0, 1)]
        
        # Optimize
        result = minimize(
            negative_log_likelihood,
            initial_params,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
            options={'maxiter': 1000, 'ftol': 1e-9}
        )
        
        end_time = datetime.now()
        
        # Calculate final conditional volatilities
        omega, alpha, beta = result.x
        T = len(returns)
        sigma2 = np.zeros(T)
        sigma2[0] = np.var(returns)
        
        for t in range(1, T):
            sigma2[t] = omega + alpha * returns.iloc[t-1]**2 + beta * sigma2[t-1]
        
        return {
            'params': result.x,
            'log_likelihood': -result.fun,
            'conditional_volatility': np.sqrt(sigma2),
            'convergence': result.success,
            'num_iterations': result.nit,
            'estimation_time': (end_time - start_time).total_seconds()
        }
    
    def _validate_model(self, returns: pd.Series):
        """Perform model validation tests."""
        if self.conditional_volatility is None:
            return
        
        # Standardized residuals
        standardized_residuals = returns / self.conditional_volatility
        
        # Ljung-Box test for serial correlation in standardized residuals
        try:
            lb_stat, lb_pvalue = ljungbox(standardized_residuals, lags=10, return_df=False)
            self.estimation_results['ljung_box_stat'] = lb_stat[-1]
            self.estimation_results['ljung_box_pvalue'] = lb_pvalue[-1]
        except:
            self.estimation_results['ljung_box_stat'] = None
            self.estimation_results['ljung_box_pvalue'] = None
        
        # Ljung-Box test for serial correlation in squared standardized residuals
        try:
            lb_stat_sq, lb_pvalue_sq = ljungbox(standardized_residuals**2, lags=10, return_df=False)
            self.estimation_results['ljung_box_squared_stat'] = lb_stat_sq[-1]
            self.estimation_results['ljung_box_squared_pvalue'] = lb_pvalue_sq[-1]
        except:
            self.estimation_results['ljung_box_squared_stat'] = None
            self.estimation_results['ljung_box_squared_pvalue'] = None
        
        # Jarque-Bera test for normality
        try:
            jb_stat, jb_pvalue = jarque_bera(standardized_residuals)
            self.estimation_results['jarque_bera_stat'] = jb_stat
            self.estimation_results['jarque_bera_pvalue'] = jb_pvalue
        except:
            self.estimation_results['jarque_bera_stat'] = None
            self.estimation_results['jarque_bera_pvalue'] = None
    
    def forecast(self, horizon: int = 1) -> np.ndarray:
        """
        Generate volatility forecasts.
        
        Args:
            horizon: Number of periods ahead to forecast
            
        Returns:
            Array of volatility forecasts
        """
        if self.parameters is None or self.conditional_volatility is None:
            raise ValueError("Model must be fitted before forecasting")
        
        forecasts = np.zeros(horizon)
        
        # Get last conditional variance
        last_variance = self.conditional_volatility[-1]**2
        last_return = self.fitted_data.iloc[-1]
        
        # Multi-step ahead forecasting
        for h in range(horizon):
            if h == 0:
                # One-step ahead
                forecasts[h] = np.sqrt(
                    self.parameters.omega + 
                    self.parameters.alpha * last_return**2 + 
                    self.parameters.beta * last_variance
                )
            else:
                # Multi-step ahead (converges to unconditional volatility)
                unconditional_var = self.parameters.unconditional_variance()
                persistence = self.parameters.alpha + self.parameters.beta
                
                forecast_var = (unconditional_var + 
                               (last_variance - unconditional_var) * persistence**h)
                forecasts[h] = np.sqrt(forecast_var)
        
        return forecasts
    
    def update_forecast(self, new_return: float) -> float:
        """
        Update volatility forecast with new return observation.
        
        Args:
            new_return: New return observation
            
        Returns:
            Updated volatility forecast
        """
        if self.parameters is None or self.conditional_volatility is None:
            raise ValueError("Model must be fitted before updating")
        
        # Calculate new conditional variance
        last_variance = self.conditional_volatility[-1]**2
        
        new_variance = (self.parameters.omega + 
                       self.parameters.alpha * new_return**2 + 
                       self.parameters.beta * last_variance)
        
        new_volatility = np.sqrt(new_variance)
        
        # Update stored data
        self.fitted_data = pd.concat([self.fitted_data, pd.Series([new_return])])
        self.conditional_volatility = np.append(self.conditional_volatility, new_volatility)
        
        return new_volatility
    
    def get_current_volatility(self) -> float:
        """Get the most recent conditional volatility estimate."""
        if self.conditional_volatility is None:
            raise ValueError("Model must be fitted first")
        
        return self.conditional_volatility[-1]
    
    def get_model_diagnostics(self) -> Dict[str, Any]:
        """Get comprehensive model diagnostics."""
        if not self.estimation_results:
            raise ValueError("Model must be fitted first")
        
        diagnostics = self.estimation_results.copy()
        
        # Add parameter interpretation
        if self.parameters:
            diagnostics['persistence'] = self.parameters.alpha + self.parameters.beta
            diagnostics['half_life'] = np.log(0.5) / np.log(self.parameters.alpha + self.parameters.beta)
            diagnostics['unconditional_volatility'] = np.sqrt(self.parameters.unconditional_variance())
        
        return diagnostics
    
    def plot_volatility(self, figsize: Tuple[int, int] = (12, 8)) -> None:
        """Plot conditional volatility and returns."""
        if self.fitted_data is None or self.conditional_volatility is None:
            raise ValueError("Model must be fitted first")
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=figsize)
        
        # Plot returns
        ax1.plot(self.fitted_data.index, self.fitted_data.values, alpha=0.7, linewidth=0.5)
        ax1.set_title('Returns')
        ax1.set_ylabel('Return')
        ax1.grid(True, alpha=0.3)
        
        # Plot conditional volatility
        ax2.plot(self.fitted_data.index, self.conditional_volatility, color='red', linewidth=1)
        ax2.set_title('Conditional Volatility (GARCH)')
        ax2.set_ylabel('Volatility')
        ax2.set_xlabel('Date')
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.show()

def main():
    """Example usage of the SpyderGARCHModel."""
    print("="*60)
    print(" SPYDER - GARCH Volatility Model Demonstration")
    print("="*60)
    
    # Generate synthetic return data with volatility clustering
    np.random.seed(42)
    T = 1000
    returns = np.zeros(T)
    sigma = np.zeros(T)
    
    # True GARCH parameters
    omega_true = 0.00001
    alpha_true = 0.08
    beta_true = 0.90
    
    sigma[0] = 0.02  # Initial volatility
    
    for t in range(1, T):
        sigma[t] = np.sqrt(omega_true + alpha_true * returns[t-1]**2 + beta_true * sigma[t-1]**2)
        returns[t] = sigma[t] * np.random.standard_normal()
    
    # Create pandas series with dates
    dates = pd.date_range(start='2020-01-01', periods=T, freq='D')
    returns_series = pd.Series(returns, index=dates)
    
    print(f"\n--- Generated {T} synthetic returns with volatility clustering ---")
    print(f"True parameters: ω={omega_true:.6f}, α={alpha_true:.3f}, β={beta_true:.3f}")
    print(f"Sample statistics:")
    print(f"  Mean return: {returns_series.mean():.4f}")
    print(f"  Return volatility: {returns_series.std():.4f}")
    print(f"  Skewness: {returns_series.skew():.4f}")
    print(f"  Kurtosis: {returns_series.kurtosis():.4f}")
    
    # Initialize and fit GARCH model
    garch_model = SpyderGARCHModel(model_type='garch', distribution='normal')
    
    print("\n--- Fitting GARCH Model ---")
    estimation_results = garch_model.fit(returns_series)
    
    print("Estimation Results:")
    params = estimation_results['parameters']
    print(f"  ω (omega): {params.omega:.6f}")
    print(f"  α (alpha): {params.alpha:.4f}")
    print(f"  β (beta):  {params.beta:.4f}")
    print(f"  Persistence (α+β): {params.alpha + params.beta:.4f}")
    print(f"  Log-likelihood: {estimation_results['log_likelihood']:.2f}")
    print(f"  AIC: {estimation_results['aic']:.2f}")
    print(f"  BIC: {estimation_results['bic']:.2f}")
    print(f"  Convergence: {estimation_results['convergence']}")
    
    # Model diagnostics
    print("\n--- Model Diagnostics ---")
    diagnostics = garch_model.get_model_diagnostics()
    print(f"  Persistence: {diagnostics['persistence']:.4f}")
    print(f"  Half-life: {diagnostics['half_life']:.1f} days")
    print(f"  Unconditional volatility: {diagnostics['unconditional_volatility']:.4f}")
    
    if diagnostics.get('ljung_box_pvalue'):
        print(f"  Ljung-Box test p-value: {diagnostics['ljung_box_pvalue']:.4f}")
        print(f"  Ljung-Box squared test p-value: {diagnostics['ljung_box_squared_pvalue']:.4f}")
        print(f"  Jarque-Bera test p-value: {diagnostics['jarque_bera_pvalue']:.4f}")
    
    # Volatility forecasting
    print("\n--- Volatility Forecasting ---")
    forecast_horizon = 10
    volatility_forecasts = garch_model.forecast(forecast_horizon)
    
    current_vol = garch_model.get_current_volatility()
    print(f"  Current volatility: {current_vol:.4f}")
    print("  Forecasts:")
    for h in range(min(5, forecast_horizon)):
        print(f"    {h+1} day ahead: {volatility_forecasts[h]:.4f}")
    
    # Real-time update simulation
    print("\n--- Real-time Update Simulation ---")
    print("  Simulating new return observations...")
    
    # Generate 5 new returns
    new_returns = np.random.normal(0, 0.02, 5)
    
    for i, new_return in enumerate(new_returns):
        updated_vol = garch_model.update_forecast(new_return)
        print(f"    Day {i+1}: Return = {new_return:.4f}, Updated Vol = {updated_vol:.4f}")
    
    # Parameter comparison with true values
    print("\n--- Parameter Recovery Analysis ---")
    print("    " + "-" * 45)
    print(f"    {'Parameter':<10} {'True':<10} {'Estimated':<12} {'Error':<10}")
    print("    " + "-" * 45)
    
    omega_error = abs(params.omega - omega_true) / omega_true * 100
    alpha_error = abs(params.alpha - alpha_true) / alpha_true * 100
    beta_error = abs(params.beta - beta_true) / beta_true * 100
    
    print(f"    {'ω (omega)':<10} {omega_true:<10.6f} {params.omega:<12.6f} {omega_error:<9.1f}%")
    print(f"    {'α (alpha)':<10} {alpha_true:<10.4f} {params.alpha:<12.4f} {alpha_error:<9.1f}%")
    print(f"    {'β (beta)':<10} {beta_true:<10.4f} {params.beta:<12.4f} {beta_error:<9.1f}%")
    
    # Volatility clustering demonstration
    print("\n--- Volatility Clustering Analysis ---")
    high_vol_periods = garch_model.conditional_volatility > np.percentile(garch_model.conditional_volatility, 90)
    clustering_measure = np.mean(high_vol_periods[1:] == high_vol_periods[:-1])
    
    print(f"  High volatility periods: {np.sum(high_vol_periods)} days ({np.mean(high_vol_periods):.1%})")
    print(f"  Volatility clustering measure: {clustering_measure:.3f}")
    print(f"  (Values > 0.5 indicate clustering)")
    
    # Performance metrics
    print("\n--- Performance Summary ---")
    print(f"  Estimation time: {estimation_results.get('estimation_time', 0):.3f} seconds")
    print(f"  Model complexity: 3 parameters")
    print(f"  Data requirements: Minimum 50 observations")
    print(f"  Forecast horizon: Unlimited (with convergence to unconditional)")
    print(f"  Real-time updates: Supported")
    print(f"  Integration ready: Yes (provides volatility inputs to pricing models)")
    
    print("="*60)

if __name__ == "__main__":
    main()

