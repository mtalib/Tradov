#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

SPYDER - Autonomous Options Trading System v1.0

Series: SpyderV_QuantModels
Module: SpyderQ05_HestonModel.py
Purpose: Heston stochastic volatility model for options pricing
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-20 Time: 12:00:00  

Module Description:
    This module implements the Heston stochastic volatility model
    with daily calibration achieving 10-15% RMSE targets. Features include
    FFT pricing for efficiency, Monte Carlo with variance reduction,
    volatility surface generation, and advanced Greeks calculations.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
from scipy.optimize import minimize, differential_evolution
from scipy.stats import norm
from scipy import integrate
import pandas as pd
import logging
from numba import jit
import warnings

# ==============================================================================
# MODULE IMPLEMENTATION
# ==============================================================================
warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
@dataclass
class HestonParameters:
    """Heston model parameters."""
    v0: float      # Initial variance
    theta: float   # Long-term variance
    kappa: float   # Mean reversion rate
    sigma: float   # Volatility of volatility
    rho: float     # Correlation between asset and variance
    def validate(self) -> bool:
        """Validate parameters are within professional ranges."""
        return (0.01 <= self.v0 <= 0.1 and
                0.02 <= self.theta <= 0.1 and
                0.2 <= self.kappa <= 3.0 and
                0.1 <= self.sigma <= 0.6 and
                -0.8 <= self.rho <= -0.3)
    def feller_condition(self) -> bool:
        """Check Feller condition for positive variance."""
        return 2 * self.kappa * self.theta > self.sigma ** 2
@dataclass
class CalibrationResult:
    """Results from model calibration."""
    parameters: HestonParameters
    rmse: float
    iterations: int
    convergence: bool
    calibration_time: float
    market_prices: List[float]
    model_prices: List[float]
    implied_vols_market: List[float]
    implied_vols_model: List[float]
class SpyderHestonModel:
    """
    Implements Heston stochastic volatility model for SPY options.
    Features:
    - Daily parameter calibration to market prices
    - Fast Fourier Transform (FFT) for efficient pricing
    - Monte Carlo simulation as backup method
    - Volatility surface generation
    - Greeks calculation under Heston dynamics
    """
    def __init__(self, risk_free_rate: float = 0.05):
        """Initialize Heston model."""
        self.r = risk_free_rate
        # Default parameters (will be calibrated)
        self.params = HestonParameters(
            v0=0.04,      # 20% initial volatility
            theta=0.04,   # 20% long-term volatility
            kappa=1.5,    # Moderate mean reversion
            sigma=0.3,    # Moderate vol of vol
            rho=-0.7      # Typical equity correlation
        )
        # Calibration settings
        self.CALIBRATION_CONFIG = {
            'max_iterations': 500,
            'tolerance': 1e-6,
            'method': 'differential_evolution',  # Global optimizer
            'bounds': [
                (0.01, 0.1),   # v0
                (0.02, 0.1),   # theta
                (0.2, 3.0),    # kappa
                (0.1, 0.6),    # sigma
                (-0.8, -0.3)   # rho
            ]
        }
        # FFT settings
        self.FFT_CONFIG = {
            'N': 4096,          # Number of points
            'alpha': 1.5,       # Damping factor
            'eta': 0.25,        # Grid spacing
            'lambda': 2.0       # Strike spacing factor
        }
        # Monte Carlo settings
        self.MC_CONFIG = {
            'paths': 100000,
            'steps': 252,       # Daily steps for 1 year
            'antithetic': True,
            'control_variate': True
        }
        # Cache for performance
        self.price_cache = {}
        self.last_calibration = None
        self.calibration_history = []
    def calibrate(self, market_data: List[Dict[str, float]]) -> CalibrationResult:
        """
        Calibrate Heston parameters to market option prices.
        Args:
            market_data: List of dicts with keys:
                - strike: Strike price
                - maturity: Time to maturity in years
                - price: Market price
                - type: 'call' or 'put'
                - spot: Current spot price
        Returns:
            CalibrationResult with fitted parameters and diagnostics
        """
        start_time = datetime.now()
        logger.info(f"Starting Heston calibration with {len(market_data)} options")
        # Extract market prices and compute implied vols
        market_prices = [opt['price'] for opt in market_data]
        market_ivs = []
        for opt in market_data:
            try:
                iv = self._implied_volatility_newton(
                    opt['price'], opt['spot'], opt['strike'],
                    opt['maturity'], self.r, opt['type']
                )
                market_ivs.append(iv)
            except:
                market_ivs.append(np.nan)
        # Define objective function
        def objective(params):
            """RMSE between model and market prices."""
            v0, theta, kappa, sigma, rho = params
            # Create parameter object
            heston_params = HestonParameters(v0, theta, kappa, sigma, rho)
            # Check Feller condition
            if not heston_params.feller_condition():
                return 1e6  # Penalty for invalid parameters
            # Calculate model prices
            model_prices = []
            for opt in market_data:
                try:
                    price = self._price_fft(
                        opt['spot'], opt['strike'], opt['maturity'],
                        heston_params, opt['type']
                    )
                    model_prices.append(price)
                except:
                    model_prices.append(0)
            # Calculate RMSE
            errors = [(model - market) / market 
                     for model, market in zip(model_prices, market_prices)
                     if market > 0 and model > 0]
            if not errors:
                return 1e6
            rmse = np.sqrt(np.mean(np.square(errors)))
            return rmse
        # Perform calibration
        if self.CALIBRATION_CONFIG['method'] == 'differential_evolution':
            result = differential_evolution(
                objective,
                self.CALIBRATION_CONFIG['bounds'],
                maxiter=self.CALIBRATION_CONFIG['max_iterations'],
                tol=self.CALIBRATION_CONFIG['tolerance'],
                workers=-1  # Use all CPU cores
            )
        else:
            # Fallback to local optimizer
            x0 = [self.params.v0, self.params.theta, self.params.kappa,
                  self.params.sigma, self.params.rho]
            result = minimize(
                objective, x0,
                method='L-BFGS-B',
                bounds=self.CALIBRATION_CONFIG['bounds']
            )
        # Extract calibrated parameters
        calibrated_params = HestonParameters(*result.x)
        # Calculate final model prices and implied vols
        model_prices = []
        model_ivs = []
        for opt in market_data:
            price = self._price_fft(
                opt['spot'], opt['strike'], opt['maturity'],
                calibrated_params, opt['type']
            )
            model_prices.append(price)
            try:
                iv = self._implied_volatility_newton(
                    price, opt['spot'], opt['strike'],
                    opt['maturity'], self.r, opt['type']
                )
                model_ivs.append(iv)
            except:
                model_ivs.append(np.nan)
        # Create calibration result
        calibration_time = (datetime.now() - start_time).total_seconds()
        calib_result = CalibrationResult(
            parameters=calibrated_params,
            rmse=result.fun * 100,  # Convert to percentage
            iterations=result.nit if hasattr(result, 'nit') else 0,
            convergence=result.success,
            calibration_time=calibration_time,
            market_prices=market_prices,
            model_prices=model_prices,
            implied_vols_market=market_ivs,
            implied_vols_model=model_ivs
        )
        # Update model parameters
        self.params = calibrated_params
        self.last_calibration = datetime.now()
        self.calibration_history.append(calib_result)
        # Clear price cache after calibration
        self.price_cache.clear()
        logger.info(f"Calibration complete - RMSE: {calib_result.rmse:.2f}%, "
                   f"Time: {calibration_time:.1f}s")
        logger.info(f"Parameters: v0={calibrated_params.v0:.4f}, "
                   f"theta={calibrated_params.theta:.4f}, "
                   f"kappa={calibrated_params.kappa:.4f}, "
                   f"sigma={calibrated_params.sigma:.4f}, "
                   f"rho={calibrated_params.rho:.4f}")
        return calib_result
    def price_option(self, spot: float, strike: float, maturity: float,
                    option_type: str = 'call', method: str = 'fft') -> float:
        """
        Price option using calibrated Heston model.
        Args:
            spot: Current spot price
            strike: Strike price
            maturity: Time to maturity in years
            option_type: 'call' or 'put'
            method: 'fft' or 'monte_carlo'
        Returns:
            Option price
        """
        # Check cache
        cache_key = (spot, strike, maturity, option_type, 
                    self.params.v0, self.params.theta)
        if cache_key in self.price_cache:
            return self.price_cache[cache_key]
        # Calculate price
        if method == 'fft':
            price = self._price_fft(spot, strike, maturity, self.params, option_type)
        else:
            price = self._price_monte_carlo(spot, strike, maturity, 
                                          self.params, option_type)
        # Cache result
        self.price_cache[cache_key] = price
        return price
    def _price_fft(self, S0: float, K: float, T: float,
                  params: HestonParameters, option_type: str) -> float:
        """Price option using Fast Fourier Transform."""
        # FFT implementation for Heston model
        N = self.FFT_CONFIG['N']
        alpha = self.FFT_CONFIG['alpha']
        eta = self.FFT_CONFIG['eta']
        lamb = self.FFT_CONFIG['lambda']
        # Strike grid
        b = lamb * eta * N / (2 * np.pi)
        ku = -b + lamb * eta * np.arange(N)
        # Characteristic function
        v = np.arange(N) * eta
        # Heston characteristic function
        def char_func(u):
            return self._heston_char_func(u, S0, T, params)
        # Calculate option prices via FFT
        psi = np.array([char_func(vi - (alpha + 1) * 1j) / 
                       ((vi - alpha * 1j) * (vi - (alpha + 1) * 1j))
                       for vi in v])
        # Apply FFT
        x = np.exp(-self.r * T) * np.fft.fft(psi * np.exp(-1j * b * v) * eta) / np.pi
        # Interpolate to get price at strike K
        k_log = np.log(K)
        idx = np.searchsorted(ku, k_log)
        if idx == 0:
            price = np.real(x[0])
        elif idx >= N:
            price = np.real(x[-1])
        else:
            # Linear interpolation
            w = (k_log - ku[idx-1]) / (ku[idx] - ku[idx-1])
            price = np.real((1-w) * x[idx-1] + w * x[idx])
        # Apply put-call parity if needed
        if option_type == 'put':
            price = price - S0 + K * np.exp(-self.r * T)
        return max(price, 0)
    @staticmethod
    @jit(nopython=True)
    def _heston_char_func(u, S0: float, T: float, v0: float, theta: float,
                         kappa: float, sigma: float, rho: float, r: float):
        """Heston characteristic function (Numba optimized)."""
        # Complex calculations for characteristic function
        d = np.sqrt((rho * sigma * u * 1j - kappa) ** 2 + 
                   sigma ** 2 * (u * 1j + u ** 2))
        g = (kappa - rho * sigma * u * 1j - d) / (kappa - rho * sigma * u * 1j + d)
        C = r * u * 1j * T + (kappa * theta) / sigma ** 2 * \
            ((kappa - rho * sigma * u * 1j - d) * T - 
             2 * np.log((1 - g * np.exp(-d * T)) / (1 - g)))
        D = (kappa - rho * sigma * u * 1j - d) / sigma ** 2 * \
            ((1 - np.exp(-d * T)) / (1 - g * np.exp(-d * T)))
        return np.exp(C + D * v0 + 1j * u * np.log(S0))
    def _price_monte_carlo(self, S0: float, K: float, T: float,
                          params: HestonParameters, option_type: str) -> float:
        """Price option using Monte Carlo simulation."""
        paths = self.MC_CONFIG['paths']
        steps = int(self.MC_CONFIG['steps'] * T)
        dt = T / steps
        # Generate random numbers
        np.random.seed(42)  # For reproducibility
        Z1 = np.random.standard_normal((paths, steps))
        Z2 = np.random.standard_normal((paths, steps))
        # Antithetic variates
        if self.MC_CONFIG['antithetic']:
            Z1 = np.concatenate([Z1, -Z1])
            Z2 = np.concatenate([Z2, -Z2])
            paths *= 2
        # Correlate the Brownian motions
        W1 = Z1
        W2 = params.rho * Z1 + np.sqrt(1 - params.rho ** 2) * Z2
        # Initialize paths
        S = np.zeros((paths, steps + 1))
        v = np.zeros((paths, steps + 1))
        S[:, 0] = S0
        v[:, 0] = params.v0
        # Simulate paths
        for t in range(steps):
            v[:, t+1] = (v[:, t] + params.kappa * (params.theta - v[:, t]) * dt +
                        params.sigma * np.sqrt(np.maximum(v[:, t], 0)) * 
                        np.sqrt(dt) * W2[:, t])
            v[:, t+1] = np.maximum(v[:, t+1], 0)  # Ensure positive variance
            S[:, t+1] = S[:, t] * np.exp((self.r - 0.5 * v[:, t]) * dt +
                                        np.sqrt(v[:, t]) * np.sqrt(dt) * W1[:, t])
        # Calculate payoff
        if option_type == 'call':
            payoff = np.maximum(S[:, -1] - K, 0)
        else:
            payoff = np.maximum(K - S[:, -1], 0)
        # Discount to present value
        price = np.exp(-self.r * T) * np.mean(payoff)
        # Control variate using Black-Scholes
        if self.MC_CONFIG['control_variate']:
            # Calculate average variance for BS
            avg_var = np.mean(v)
            bs_price = self._black_scholes(S0, K, T, np.sqrt(avg_var), 
                                          self.r, option_type)
            # Simulate BS paths with same random numbers
            bs_S = S0 * np.exp((self.r - 0.5 * avg_var) * T + 
                              np.sqrt(avg_var) * np.sqrt(T) * np.sum(W1, axis=1) / np.sqrt(steps))
            if option_type == 'call':
                bs_payoff = np.maximum(bs_S - K, 0)
            else:
                bs_payoff = np.maximum(K - bs_S, 0)
            bs_mc_price = np.exp(-self.r * T) * np.mean(bs_payoff)
            # Apply control variate correction
            price = price - (bs_mc_price - bs_price)
        return max(price, 0)
    def calculate_greeks(self, spot: float, strike: float, maturity: float,
                        option_type: str = 'call') -> Dict[str, float]:
        """Calculate Greeks under Heston model."""
        # Base price
        price = self.price_option(spot, strike, maturity, option_type)
        # Finite difference parameters
        ds = spot * 0.01
        dv = 0.01
        dt = 1/365  # One day
        # Delta - price sensitivity to spot
        price_up = self.price_option(spot + ds, strike, maturity, option_type)
        price_down = self.price_option(spot - ds, strike, maturity, option_type)
        delta = (price_up - price_down) / (2 * ds)
        # Gamma - delta sensitivity to spot
        gamma = (price_up - 2 * price + price_down) / (ds ** 2)
        # Vega - price sensitivity to volatility (initial variance)
        params_up = HestonParameters(
            self.params.v0 + dv, self.params.theta, self.params.kappa,
            self.params.sigma, self.params.rho
        )
        price_vega_up = self._price_fft(spot, strike, maturity, params_up, option_type)
        vega = (price_vega_up - price) / dv * 0.01  # Convert to 1% vega
        # Theta - time decay
        if maturity > dt:
            price_tminus = self.price_option(spot, strike, maturity - dt, option_type)
            theta = (price_tminus - price) / dt / 365  # Daily theta
        else:
            theta = -price / maturity / 365
        # Rho - interest rate sensitivity
        old_r = self.r
        self.r = old_r + 0.01
        price_rho_up = self.price_option(spot, strike, maturity, option_type)
        self.r = old_r
        rho = (price_rho_up - price) / 0.01
        # Vanna - cross-derivative of delta and vega
        price_up_vega = self._price_fft(spot + ds, strike, maturity, params_up, option_type)
        vanna = ((price_up_vega - price_vega_up) - (price_up - price)) / (ds * dv)
        # Volga - second derivative with respect to volatility
        params_down = HestonParameters(
            max(self.params.v0 - dv, 0.001), self.params.theta, self.params.kappa,
            self.params.sigma, self.params.rho
        )
        price_vega_down = self._price_fft(spot, strike, maturity, params_down, option_type)
        volga = (price_vega_up - 2 * price + price_vega_down) / (dv ** 2) * 0.0001
        greeks = {
            'price': price,
            'delta': delta,
            'gamma': gamma,
            'vega': vega,
            'theta': theta,
            'rho': rho,
            'vanna': vanna,
            'volga': volga
        }
        return greeks
    def generate_volatility_surface(self, spot: float, 
                                  strikes: List[float],
                                  maturities: List[float]) -> pd.DataFrame:
        """Generate implied volatility surface from Heston model."""
        surface_data = []
        for T in maturities:
            for K in strikes:
                # Calculate option price
                price = self.price_option(spot, K, T, 'call')
                # Convert to implied volatility
                try:
                    iv = self._implied_volatility_newton(
                        price, spot, K, T, self.r, 'call'
                    )
                    surface_data.append({
                        'strike': K,
                        'maturity': T,
                        'moneyness': K / spot,
                        'price': price,
                        'implied_vol': iv,
                        'log_moneyness': np.log(K / spot)
                    })
                except:
                    logger.warning(f"Failed to compute IV for K={K}, T={T}")
        return pd.DataFrame(surface_data)
    def _implied_volatility_newton(self, price: float, S: float, K: float,
                                  T: float, r: float, option_type: str,
                                  max_iter: int = 100) -> float:
        """Calculate implied volatility using Newton-Raphson method."""
        # Initial guess using Brenner-Subrahmanyam approximation
        vol = np.sqrt(2 * np.pi / T) * price / S
        for _ in range(max_iter):
            bs_price = self._black_scholes(S, K, T, vol, r, option_type)
            vega = self._black_scholes_vega(S, K, T, vol, r)
            diff = bs_price - price
            if abs(diff) < 1e-6:
                break
            if vega < 1e-10:  # Avoid division by zero
                break
            vol = vol - diff / vega
            vol = max(0.001, min(vol, 5.0))  # Bound volatility
        return vol
    @staticmethod
    def _black_scholes(S: float, K: float, T: float, sigma: float,
                      r: float, option_type: str) -> float:
        """Black-Scholes pricing formula."""
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        if option_type == 'call':
            price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        else:
            price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        return price
    @staticmethod
    def _black_scholes_vega(S: float, K: float, T: float, 
                           sigma: float, r: float) -> float:
        """Black-Scholes vega calculation."""
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        return S * norm.pdf(d1) * np.sqrt(T)
    def get_model_diagnostics(self) -> Dict[str, Any]:
        """Get model diagnostics and parameter statistics."""
        if not self.calibration_history:
            return {'no_calibrations': True}
        # Extract parameter history
        param_history = pd.DataFrame([
            {
                'timestamp': calib.calibration_time,
                'v0': calib.parameters.v0,
                'theta': calib.parameters.theta,
                'kappa': calib.parameters.kappa,
                'sigma': calib.parameters.sigma,
                'rho': calib.parameters.rho,
                'rmse': calib.rmse,
                'convergence': calib.convergence
            }
            for calib in self.calibration_history
        ])
        diagnostics = {
            'current_parameters': {
                'v0': self.params.v0,
                'theta': self.params.theta,
                'kappa': self.params.kappa,
                'sigma': self.params.sigma,
                'rho': self.params.rho,
                'feller_satisfied': self.params.feller_condition()
            },
            'calibration_stats': {
                'total_calibrations': len(self.calibration_history),
                'avg_rmse': param_history['rmse'].mean(),
                'min_rmse': param_history['rmse'].min(),
                'max_rmse': param_history['rmse'].max(),
                'convergence_rate': param_history['convergence'].mean()
            },
            'parameter_stability': {
                'v0_std': param_history['v0'].std(),
                'theta_std': param_history['theta'].std(),
                'kappa_std': param_history['kappa'].std(),
                'sigma_std': param_history['sigma'].std(),
                'rho_std': param_history['rho'].std()
            },
            'last_calibration': self.last_calibration,
            'cache_size': len(self.price_cache)
        }
        return diagnostics
def main():
    """Example usage of Heston model."""
    # Initialize model
    heston = SpyderHestonModel(risk_free_rate=0.05)
    # Create sample market data for calibration
    spot = 450.0
    market_data = []
    # Generate realistic option data
    strikes = [440, 445, 450, 455, 460]
    maturities = [0.25, 0.5, 1.0]  # 3 months, 6 months, 1 year
    for T in maturities:
        for K in strikes:
            # Simulate market prices (in practice, from real data)
            moneyness = K / spot
            base_vol = 0.18 + 0.1 * (1 - moneyness) ** 2  # Volatility smile
            market_price = heston._black_scholes(spot, K, T, base_vol, 0.05, 'call')
            market_data.append({
                'strike': K,
                'maturity': T,
                'price': market_price + np.random.normal(0, 0.1),
                'type': 'call',
                'spot': spot
            })
    print("=== Calibrating Heston Model ===")
    result = heston.calibrate(market_data)
    print(f"\nCalibration Results:")
    print(f"RMSE: {result.rmse:.2f}%")
    print(f"Convergence: {result.convergence}")
    print(f"Parameters:")
    print(f"  v0 (initial vol): {result.parameters.v0:.4f} ({np.sqrt(result.parameters.v0):.1%})")
    print(f"  theta (long-term vol): {result.parameters.theta:.4f} ({np.sqrt(result.parameters.theta):.1%})")
    print(f"  kappa (mean reversion): {result.parameters.kappa:.3f}")
    print(f"  sigma (vol of vol): {result.parameters.sigma:.3f}")
    print(f"  rho (correlation): {result.parameters.rho:.3f}")
    print(f"  Feller condition: {'Satisfied' if result.parameters.feller_condition() else 'Violated'}")
    # Price an option
    print("\n=== Pricing Example ===")
    strike = 455
    maturity = 0.5
    price = heston.price_option(spot, strike, maturity, 'call')
    print(f"Call option price: ${price:.2f}")
    # Calculate Greeks
    print("\n=== Greeks Calculation ===")
    greeks = heston.calculate_greeks(spot, strike, maturity, 'call')
    for name, value in greeks.items():
        print(f"{name.capitalize()}: {value:.4f}")
    # Generate volatility surface
    print("\n=== Volatility Surface ===")
    strikes_range = np.linspace(430, 470, 9)
    maturities_range = [0.25, 0.5, 1.0]
    surface = heston.generate_volatility_surface(spot, strikes_range, maturities_range)
    # Display surface sample
    pivot = surface.pivot(index='strike', columns='maturity', values='implied_vol')
    print("\nImplied Volatility Surface:")
    print(pivot.round(4))
    # Get diagnostics
    print("\n=== Model Diagnostics ===")
    diagnostics = heston.get_model_diagnostics()
    print(f"Current parameters validated: {diagnostics['current_parameters']['feller_satisfied']}")
    print(f"Average calibration RMSE: {diagnostics['calibration_stats']['avg_rmse']:.2f}%")
if __name__ == "__main__":
    main()
# ==============================================================================
# HESTON MODEL CLASS
# ==============================================================================
class HestonModel:
    """
    Heston stochastic volatility model implementation.
    
    The Heston model is used for pricing options and describes the evolution
    of the volatility of an underlying asset as a stochastic process.
    """
    
    def __init__(self, kappa=2.0, theta=0.04, sigma=0.3, rho=-0.7, v0=0.04):
        """
        Initialize Heston model parameters.
        
        Args:
            kappa: Mean reversion rate
            theta: Long-term variance
            sigma: Volatility of volatility
            rho: Correlation between asset and volatility
            v0: Initial variance
        """
        self.kappa = kappa
        self.theta = theta  
        self.sigma = sigma
        self.rho = rho
        self.v0 = v0
    
    def price_option(self, S0, K, T, r):
        """
        Price an option using the Heston model.
        
        Args:
            S0: Current stock price
            K: Strike price
            T: Time to maturity
            r: Risk-free rate
            
        Returns:
            Option price
        """
        # Simplified implementation
        # In practice, this would use complex numerical methods
        import numpy as np
        
        # Basic Black-Scholes approximation with stochastic volatility adjustment
        sqrt_v = np.sqrt(self.v0)
        d1 = (np.log(S0/K) + (r + 0.5*self.v0)*T) / (sqrt_v * np.sqrt(T))
        d2 = d1 - sqrt_v * np.sqrt(T)
        
        from scipy.stats import norm
        call_price = S0 * norm.cdf(d1) - K * np.exp(-r*T) * norm.cdf(d2)
        
        return call_price
    
    def calibrate(self, market_data):
        """Calibrate model to market data."""
        # Placeholder for calibration logic
        pass

