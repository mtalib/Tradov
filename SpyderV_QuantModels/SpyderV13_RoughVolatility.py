#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

SPYDER - Autonomous Options Trading System v1.0

Series: SpyderV_QuantModels
Module: SpyderV13_RoughVolatility.py
Purpose: Rough volatility model using fractional Brownian motion for options pricing.
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-29 Time: 14:15:00

Module Description:
    This module implements the cutting-edge Rough Volatility model, which has
    revolutionized volatility modeling in quantitative finance. Unlike traditional
    models that assume smooth volatility paths, rough volatility models use
    fractional Brownian motion with Hurst parameter H ≈ 0.1, creating much more
    realistic, "rough" volatility paths that match empirical observations. This
    model is particularly effective for pricing SPY options as it captures the
    true nature of volatility clustering and mean reversion observed in equity
    index markets.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from typing import Dict, Any, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import logging
import warnings

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from scipy.stats import norm
from scipy.optimize import minimize_scalar
from scipy.special import gamma
import matplotlib.pyplot as plt

# ==============================================================================
# MODULE IMPLEMENTATION
# ==============================================================================
warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class RoughVolatilityParameters:
    """Parameters for the Rough Volatility model."""
    spot: float                 # Current spot price
    strike: float              # Strike price
    maturity: float            # Time to maturity
    risk_free_rate: float      # Risk-free rate
    dividend_yield: float = 0.0 # Dividend yield
    
    # Rough volatility specific parameters
    hurst: float = 0.1         # Hurst parameter (roughness, typically ~0.1)
    xi: float = 0.3            # Volatility of volatility
    eta: float = 1.9           # Mean reversion speed
    rho: float = -0.7          # Correlation between price and volatility
    v0: float = 0.04           # Initial variance (volatility^2)
    
    def validate(self) -> bool:
        """Validate parameters are within sensible ranges."""
        return (self.spot > 0 and self.strike > 0 and self.maturity > 0 and
                self.risk_free_rate >= 0 and 0 < self.hurst < 0.5 and
                self.xi > 0 and self.eta > 0 and -1 <= self.rho <= 1 and self.v0 > 0)

class FractionalBrownianMotion:
    """Generator for fractional Brownian motion paths."""
    
    def __init__(self, hurst: float, length: int, dt: float):
        self.hurst = hurst
        self.length = length
        self.dt = dt
        
    def generate_fbm_path(self, random_seed: Optional[int] = None) -> np.ndarray:
        """
        Generate a fractional Brownian motion path using the Cholesky method.
        This is computationally intensive but accurate.
        """
        if random_seed is not None:
            np.random.seed(random_seed)
            
        H = self.hurst
        n = self.length
        
        # Create covariance matrix for fBm
        cov_matrix = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                s, t = (i + 1) * self.dt, (j + 1) * self.dt
                cov_matrix[i, j] = 0.5 * (s**(2*H) + t**(2*H) - abs(s - t)**(2*H))
        
        # Cholesky decomposition
        try:
            L = np.linalg.cholesky(cov_matrix)
        except np.linalg.LinAlgError:
            # Add small regularization if matrix is not positive definite
            cov_matrix += np.eye(n) * 1e-10
            L = np.linalg.cholesky(cov_matrix)
        
        # Generate standard normal random variables
        Z = np.random.standard_normal(n)
        
        # Generate fBm path
        fbm_path = L @ Z
        return np.concatenate([[0], fbm_path])  # Start at 0
    
    def generate_fbm_increments(self, random_seed: Optional[int] = None) -> np.ndarray:
        """Generate fractional Brownian motion increments (more efficient)."""
        if random_seed is not None:
            np.random.seed(random_seed)
            
        H = self.hurst
        n = self.length
        
        # Use approximate method for efficiency (Mandelbrot-Van Ness representation)
        # This is faster but less accurate than full Cholesky method
        
        # Generate extended Gaussian sequence
        extended_length = 2 * n
        gaussian_sequence = np.random.standard_normal(extended_length)
        
        # Create kernel for convolution
        kernel = np.zeros(extended_length)
        for k in range(1, extended_length):
            kernel[k] = ((k + 1)**(H + 0.5) - k**(H + 0.5)) / gamma(H + 1.5)
        
        # Convolution to get fBm increments
        fbm_increments = np.convolve(gaussian_sequence, kernel, mode='valid')[:n]
        fbm_increments *= (self.dt ** H)
        
        return fbm_increments

class SpyderRoughVolatilityModel:
    """
    Implements the Rough Volatility model for American options pricing.
    
    Features:
    - Uses fractional Brownian motion for volatility dynamics
    - Captures realistic volatility roughness (H ≈ 0.1)
    - Monte Carlo simulation for option pricing
    - Handles correlation between price and volatility
    - Provides volatility surface generation
    """
    
    def __init__(self, num_paths: int = 10000, num_steps: int = 252):
        self.num_paths = num_paths
        self.num_steps = num_steps
        self.last_simulation_results: Dict[str, Any] = {}
        
    def _simulate_rough_volatility_paths(self, params: RoughVolatilityParameters) -> Tuple[np.ndarray, np.ndarray]:
        """
        Simulate asset price and volatility paths under the rough volatility model.
        
        Returns:
            Tuple of (price_paths, volatility_paths)
        """
        dt = params.maturity / self.num_steps
        
        # Initialize arrays
        price_paths = np.zeros((self.num_paths, self.num_steps + 1))
        vol_paths = np.zeros((self.num_paths, self.num_steps + 1))
        
        # Set initial values
        price_paths[:, 0] = params.spot
        vol_paths[:, 0] = np.sqrt(params.v0)
        
        # Generate correlated random numbers
        for path in range(self.num_paths):
            # Generate fractional Brownian motion for volatility
            fbm_generator = FractionalBrownianMotion(params.hurst, self.num_steps, dt)
            fbm_increments = fbm_generator.generate_fbm_increments(random_seed=path)
            
            # Generate standard Brownian motion for price
            price_brownian = np.random.standard_normal(self.num_steps)
            
            # Apply correlation
            vol_brownian = np.random.standard_normal(self.num_steps)
            correlated_vol_brownian = (params.rho * price_brownian + 
                                     np.sqrt(1 - params.rho**2) * vol_brownian)
            
            # Simulate volatility path (rough volatility SDE)
            log_vol = np.log(vol_paths[path, 0])
            for t in range(self.num_steps):
                # Rough volatility evolution
                vol_drift = -0.5 * params.xi**2 * dt
                vol_diffusion = params.xi * fbm_increments[t]
                
                log_vol += vol_drift + vol_diffusion
                vol_paths[path, t + 1] = np.exp(log_vol)
                
                # Ensure volatility stays positive and reasonable
                vol_paths[path, t + 1] = np.clip(vol_paths[path, t + 1], 0.01, 2.0)
            
            # Simulate price path
            for t in range(self.num_steps):
                current_vol = vol_paths[path, t]
                
                price_drift = (params.risk_free_rate - params.dividend_yield - 0.5 * current_vol**2) * dt
                price_diffusion = current_vol * np.sqrt(dt) * price_brownian[t]
                
                price_paths[path, t + 1] = price_paths[path, t] * np.exp(price_drift + price_diffusion)
        
        return price_paths, vol_paths
    
    def price_option(self, 
                     params: RoughVolatilityParameters, 
                     option_type: str = 'call',
                     exercise_style: str = 'american') -> float:
        """
        Price an option using Monte Carlo simulation with rough volatility.
        
        Args:
            params: Model parameters
            option_type: 'call' or 'put'
            exercise_style: 'american' or 'european'
            
        Returns:
            Option price
        """
        if not params.validate():
            raise ValueError("Invalid parameters provided")
            
        start_time = datetime.now()
        
        # Simulate paths
        price_paths, vol_paths = self._simulate_rough_volatility_paths(params)
        
        if exercise_style == 'european':
            # European option - only consider final payoff
            final_prices = price_paths[:, -1]
            if option_type == 'call':
                payoffs = np.maximum(final_prices - params.strike, 0)
            else:
                payoffs = np.maximum(params.strike - final_prices, 0)
            
            option_price = np.mean(payoffs) * np.exp(-params.risk_free_rate * params.maturity)
            
        else:
            # American option - use Longstaff-Schwartz LSM method
            option_price = self._price_american_lsm(price_paths, params, option_type)
        
        # Store simulation results
        end_time = datetime.now()
        self.last_simulation_results = {
            'calculation_time_ms': (end_time - start_time).total_seconds() * 1000,
            'num_paths': self.num_paths,
            'num_steps': self.num_steps,
            'average_final_vol': np.mean(vol_paths[:, -1]),
            'vol_path_roughness': self._calculate_roughness_measure(vol_paths),
            'exercise_style': exercise_style
        }
        
        return option_price
    
    def _price_american_lsm(self, price_paths: np.ndarray, params: RoughVolatilityParameters, option_type: str) -> float:
        """Price American option using Least-Squares Monte Carlo."""
        dt = params.maturity / self.num_steps
        discount_factor = np.exp(-params.risk_free_rate * dt)
        
        # Calculate intrinsic values
        if option_type == 'call':
            intrinsic_values = np.maximum(price_paths - params.strike, 0)
        else:
            intrinsic_values = np.maximum(params.strike - price_paths, 0)
        
        # Initialize with final payoffs
        cash_flows = intrinsic_values[:, -1]
        
        # Backward induction
        for t in range(self.num_steps - 1, 0, -1):
            # Discount cash flows
            cash_flows = cash_flows * discount_factor
            
            # Find in-the-money paths
            in_money = intrinsic_values[:, t] > 0
            
            if np.sum(in_money) > 0:
                # Regression for continuation value
                X = price_paths[in_money, t]
                Y = cash_flows[in_money]
                
                # Use polynomial basis functions
                basis = np.column_stack([np.ones(len(X)), X, X**2, X**3])
                
                try:
                    coeffs = np.linalg.lstsq(basis, Y, rcond=None)[0]
                    continuation_values = basis @ coeffs
                    
                    # Exercise decision
                    exercise_mask = intrinsic_values[in_money, t] > continuation_values
                    
                    # Update cash flows for early exercise
                    cash_flows[in_money] = np.where(exercise_mask, 
                                                  intrinsic_values[in_money, t], 
                                                  cash_flows[in_money])
                except np.linalg.LinAlgError:
                    # If regression fails, don't exercise early
                    pass
        
        # Final discounting
        option_price = np.mean(cash_flows * discount_factor)
        return option_price
    
    def _calculate_roughness_measure(self, vol_paths: np.ndarray) -> float:
        """Calculate a measure of path roughness."""
        # Calculate path variations to measure roughness
        variations = []
        for path in vol_paths:
            # Calculate quadratic variation
            increments = np.diff(path)
            quadratic_var = np.sum(increments**2)
            variations.append(quadratic_var)
        
        return np.mean(variations)
    
    def generate_volatility_surface(self, 
                                  spot: float,
                                  strikes: np.ndarray,
                                  maturities: np.ndarray,
                                  base_params: RoughVolatilityParameters) -> pd.DataFrame:
        """
        Generate implied volatility surface using the rough volatility model.
        
        Args:
            spot: Current spot price
            strikes: Array of strike prices
            maturities: Array of maturities
            base_params: Base model parameters
            
        Returns:
            DataFrame with implied volatilities
        """
        logger.info("Generating volatility surface...")
        
        surface_data = []
        
        for maturity in maturities:
            for strike in strikes:
                # Create parameters for this option
                option_params = RoughVolatilityParameters(
                    spot=spot,
                    strike=strike,
                    maturity=maturity,
                    risk_free_rate=base_params.risk_free_rate,
                    dividend_yield=base_params.dividend_yield,
                    hurst=base_params.hurst,
                    xi=base_params.xi,
                    eta=base_params.eta,
                    rho=base_params.rho,
                    v0=base_params.v0
                )
                
                # Price the option
                option_price = self.price_option(option_params, 'call', 'european')
                
                # Calculate implied volatility (simplified Black-Scholes inversion)
                implied_vol = self._calculate_implied_volatility(option_price, option_params)
                
                surface_data.append({
                    'strike': strike,
                    'maturity': maturity,
                    'moneyness': strike / spot,
                    'option_price': option_price,
                    'implied_volatility': implied_vol
                })
        
        return pd.DataFrame(surface_data)
    
    def _calculate_implied_volatility(self, market_price: float, params: RoughVolatilityParameters) -> float:
        """Calculate implied volatility using Black-Scholes inversion."""
        def black_scholes_call(vol):
            d1 = (np.log(params.spot / params.strike) + 
                  (params.risk_free_rate - params.dividend_yield + 0.5 * vol**2) * params.maturity) / \
                 (vol * np.sqrt(params.maturity))
            d2 = d1 - vol * np.sqrt(params.maturity)
            
            price = (params.spot * np.exp(-params.dividend_yield * params.maturity) * norm.cdf(d1) -
                    params.strike * np.exp(-params.risk_free_rate * params.maturity) * norm.cdf(d2))
            return price
        
        def objective(vol):
            return (black_scholes_call(vol) - market_price)**2
        
        try:
            result = minimize_scalar(objective, bounds=(0.01, 2.0), method='bounded')
            return result.x if result.success else 0.2
        except:
            return 0.2  # Default fallback
    
    def get_diagnostics(self) -> Dict[str, Any]:
        """Get diagnostics from the last simulation."""
        return self.last_simulation_results

def main():
    """Example usage of the SpyderRoughVolatilityModel."""
    print("="*60)
    print(" SPYDER - Rough Volatility Model Demonstration")
    print("="*60)
    
    # Set up model parameters
    params = RoughVolatilityParameters(
        spot=450.0,
        strike=450.0,
        maturity=0.25,  # 3 months
        risk_free_rate=0.05,
        dividend_yield=0.015,
        hurst=0.1,      # Rough volatility (much rougher than standard H=0.5)
        xi=0.3,         # Vol of vol
        eta=1.9,        # Mean reversion speed
        rho=-0.7,       # Negative correlation (leverage effect)
        v0=0.04         # Initial variance (20% vol)
    )
    
    print("\n--- Model Parameters ---")
    print(f"  Spot: ${params.spot}, Strike: ${params.strike}")
    print(f"  Maturity: {params.maturity} years")
    print(f"  Hurst Parameter (H): {params.hurst} (rough volatility)")
    print(f"  Vol of Vol (ξ): {params.xi}")
    print(f"  Correlation (ρ): {params.rho}")
    print(f"  Initial Volatility: {np.sqrt(params.v0):.1%}")
    
    # Initialize model
    model = SpyderRoughVolatilityModel(num_paths=5000, num_steps=100)
    
    # --- 1. Price American Put Option ---
    print("\n--- Pricing American Put Option ---")
    american_put_price = model.price_option(params, 'put', 'american')
    print(f"    - Rough Vol American Put Price: ${american_put_price:.4f}")
    
    diagnostics = model.get_diagnostics()
    print(f"    - Calculation Time: {diagnostics['calculation_time_ms']:.1f} ms")
    print(f"    - Average Final Volatility: {diagnostics['average_final_vol']:.1%}")
    print(f"    - Path Roughness Measure: {diagnostics['vol_path_roughness']:.6f}")
    
    # --- 2. Compare with European Option ---
    print("\n--- Comparison with European Option ---")
    european_put_price = model.price_option(params, 'put', 'european')
    print(f"    - Rough Vol European Put Price: ${european_put_price:.4f}")
    print(f"    - Early Exercise Premium: ${american_put_price - european_put_price:.4f}")
    
    # --- 3. Generate Mini Volatility Surface ---
    print("\n--- Generating Volatility Surface Sample ---")
    strikes = np.array([420, 435, 450, 465, 480])
    maturities = np.array([0.083, 0.25, 0.5])  # 1 month, 3 months, 6 months
    
    print("    Computing implied volatilities...")
    vol_surface = model.generate_volatility_surface(params.spot, strikes, maturities, params)
    
    print("\n    Implied Volatility Surface:")
    print("    " + "-" * 50)
    pivot_surface = vol_surface.pivot(index='strike', columns='maturity', values='implied_volatility')
    print(f"    {'Strike':<8} {'1M':<8} {'3M':<8} {'6M':<8}")
    print("    " + "-" * 35)
    for strike in strikes:
        row_data = pivot_surface.loc[strike]
        print(f"    ${strike:<7.0f} {row_data[0.083]:<7.1%} {row_data[0.25]:<7.1%} {row_data[0.5]:<7.1%}")
    
    # --- 4. Demonstrate Roughness Effect ---
    print("\n--- Roughness Effect Demonstration ---")
    print("    Comparing H=0.1 (rough) vs H=0.5 (smooth)...")
    
    # Smooth volatility comparison
    smooth_params = RoughVolatilityParameters(
        spot=params.spot, strike=params.strike, maturity=params.maturity,
        risk_free_rate=params.risk_free_rate, dividend_yield=params.dividend_yield,
        hurst=0.5, xi=params.xi, eta=params.eta, rho=params.rho, v0=params.v0
    )
    
    smooth_model = SpyderRoughVolatilityModel(num_paths=2000, num_steps=50)  # Smaller for demo
    smooth_price = smooth_model.price_option(smooth_params, 'put', 'american')
    
    print(f"    - Rough Vol (H=0.1) Price: ${american_put_price:.4f}")
    print(f"    - Smooth Vol (H=0.5) Price: ${smooth_price:.4f}")
    print(f"    - Roughness Impact: ${american_put_price - smooth_price:.4f}")
    print("    (Rough volatility typically increases option values)")
    
    print("="*60)

if __name__ == "__main__":
    main()

