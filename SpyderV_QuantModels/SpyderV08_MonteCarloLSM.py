#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

SPYDER - Autonomous Options Trading System v1.0

Series: SpyderV_QuantModels
Module: SpyderV08_MonteCarloLSM.py
Purpose: Least-Squares Monte Carlo method for American options pricing.
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-29 Time: 13:30:00

Module Description:
    This module implements the Longstaff-Schwartz Least-Squares Monte Carlo (LSM)
    method for pricing American options. The LSM algorithm solves the American
    option pricing problem by using regression to estimate continuation values
    at each time step, enabling optimal exercise decisions. This method is
    particularly powerful for complex payoffs and multi-dimensional problems
    where traditional finite difference methods become computationally intractable.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from typing import Dict, Any, Tuple, Optional, List
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
from scipy.special import eval_laguerre
import matplotlib.pyplot as plt

# ==============================================================================
# MODULE IMPLEMENTATION
# ==============================================================================
warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class LSMParameters:
    """Parameters for the Least-Squares Monte Carlo model."""
    spot: float                 # Current spot price
    strike: float              # Strike price
    maturity: float            # Time to maturity
    risk_free_rate: float      # Risk-free rate
    dividend_yield: float = 0.0 # Dividend yield
    volatility: float = 0.2    # Volatility
    num_paths: int = 10000     # Number of simulation paths
    num_steps: int = 50        # Number of time steps
    
    def validate(self) -> bool:
        """Validate parameters are within sensible ranges."""
        return (self.spot > 0 and self.strike > 0 and self.maturity > 0 and
                self.risk_free_rate >= 0 and self.dividend_yield >= 0 and
                self.volatility > 0 and self.num_paths > 0 and self.num_steps > 0)

class SpyderLSMModel:
    """
    Least-Squares Monte Carlo model for American options.
    
    Features:
    - Longstaff-Schwartz LSM algorithm
    - Multiple basis function types
    - Variance reduction techniques
    - Comprehensive path analysis
    - Performance optimization
    """
    
    def __init__(self, 
                 basis_functions: str = 'laguerre',
                 max_basis_degree: int = 3,
                 use_antithetic: bool = True,
                 random_seed: Optional[int] = None):
        self.basis_functions = basis_functions
        self.max_basis_degree = max_basis_degree
        self.use_antithetic = use_antithetic
        self.random_seed = random_seed
        self.last_simulation_data: Dict[str, Any] = {}
        
        if random_seed is not None:
            np.random.seed(random_seed)
    
    def price_option(self, 
                     params: LSMParameters, 
                     option_type: str = 'call') -> float:
        """
        Price an American option using the LSM method.
        
        Args:
            params: Model parameters
            option_type: 'call' or 'put'
            
        Returns:
            American option price
        """
        if not params.validate():
            raise ValueError("Invalid parameters provided")
            
        start_time = datetime.now()
        
        # Generate asset price paths
        paths = self._generate_paths(params)
        
        # Calculate option payoffs using LSM algorithm
        option_price = self._lsm_algorithm(paths, params, option_type)
        
        # Store simulation results
        end_time = datetime.now()
        self.last_simulation_data = {
            'calculation_time_ms': (end_time - start_time).total_seconds() * 1000,
            'num_paths': params.num_paths,
            'num_steps': params.num_steps,
            'basis_functions': self.basis_functions,
            'max_basis_degree': self.max_basis_degree,
            'use_antithetic': self.use_antithetic,
            'convergence_estimate': self._estimate_convergence(paths, params, option_type)
        }
        
        return option_price
    
    def _generate_paths(self, params: LSMParameters) -> np.ndarray:
        """
        Generate Monte Carlo paths for the underlying asset.
        
        Returns:
            Array of shape (num_paths, num_steps + 1) containing asset prices
        """
        dt = params.maturity / params.num_steps
        num_paths = params.num_paths
        
        if self.use_antithetic:
            # Use antithetic variates for variance reduction
            num_paths = num_paths // 2
        
        # Pre-calculate constants
        drift = (params.risk_free_rate - params.dividend_yield - 0.5 * params.volatility**2) * dt
        diffusion = params.volatility * np.sqrt(dt)
        
        # Generate random numbers
        random_numbers = np.random.standard_normal((num_paths, params.num_steps))
        
        # Calculate log returns
        log_returns = drift + diffusion * random_numbers
        
        # Calculate cumulative log returns
        log_prices = np.zeros((num_paths, params.num_steps + 1))
        log_prices[:, 0] = np.log(params.spot)
        log_prices[:, 1:] = np.log(params.spot) + np.cumsum(log_returns, axis=1)
        
        # Convert to prices
        paths = np.exp(log_prices)
        
        if self.use_antithetic:
            # Create antithetic paths
            antithetic_log_returns = drift - diffusion * random_numbers
            antithetic_log_prices = np.zeros((num_paths, params.num_steps + 1))
            antithetic_log_prices[:, 0] = np.log(params.spot)
            antithetic_log_prices[:, 1:] = np.log(params.spot) + np.cumsum(antithetic_log_returns, axis=1)
            antithetic_paths = np.exp(antithetic_log_prices)
            
            # Combine original and antithetic paths
            paths = np.vstack([paths, antithetic_paths])
        
        return paths
    
    def _lsm_algorithm(self, paths: np.ndarray, params: LSMParameters, option_type: str) -> float:
        """
        Implement the Longstaff-Schwartz LSM algorithm.
        
        Args:
            paths: Asset price paths
            params: Model parameters
            option_type: 'call' or 'put'
            
        Returns:
            Option price
        """
        num_paths, num_steps_plus_one = paths.shape
        num_steps = num_steps_plus_one - 1
        dt = params.maturity / num_steps
        discount_factor = np.exp(-params.risk_free_rate * dt)
        
        # Calculate intrinsic values
        if option_type.lower() == 'call':
            intrinsic_values = np.maximum(paths - params.strike, 0)
        else:
            intrinsic_values = np.maximum(params.strike - paths, 0)
        
        # Initialize cash flow matrix
        cash_flows = np.zeros((num_paths, num_steps + 1))
        cash_flows[:, -1] = intrinsic_values[:, -1]  # Terminal payoff
        
        # Backward induction
        for t in range(num_steps - 1, 0, -1):
            # Discount future cash flows
            cash_flows[:, t] = cash_flows[:, t + 1] * discount_factor
            
            # Find in-the-money paths
            in_money = intrinsic_values[:, t] > 0
            
            if np.sum(in_money) == 0:
                continue
            
            # Regression variables
            X = paths[in_money, t]
            Y = cash_flows[in_money, t]
            
            # Generate basis functions
            basis_matrix = self._generate_basis_functions(X)
            
            # Perform regression
            try:
                # Use least squares regression
                coefficients = np.linalg.lstsq(basis_matrix, Y, rcond=None)[0]
                continuation_values = basis_matrix @ coefficients
                
                # Exercise decision: exercise if intrinsic > continuation
                exercise_mask = intrinsic_values[in_money, t] > continuation_values
                
                # Update cash flows for early exercise
                cash_flows[in_money, t] = np.where(exercise_mask, 
                                                 intrinsic_values[in_money, t], 
                                                 cash_flows[in_money, t])
            except np.linalg.LinAlgError:
                # If regression fails, don't exercise early
                logger.warning(f"Regression failed at time step {t}")
                continue
        
        # Calculate option price
        cash_flows[:, 0] = cash_flows[:, 1] * discount_factor
        option_price = np.mean(cash_flows[:, 0])
        
        return option_price
    
    def _generate_basis_functions(self, X: np.ndarray) -> np.ndarray:
        """
        Generate basis functions for regression.
        
        Args:
            X: Asset prices for regression
            
        Returns:
            Matrix of basis function values
        """
        n = len(X)
        
        if self.basis_functions == 'laguerre':
            # Laguerre polynomials (optimal for exponential distributions)
            basis_matrix = np.ones((n, self.max_basis_degree + 1))
            for i in range(1, self.max_basis_degree + 1):
                basis_matrix[:, i] = eval_laguerre(i, X)
        
        elif self.basis_functions == 'power':
            # Simple power functions
            basis_matrix = np.ones((n, self.max_basis_degree + 1))
            for i in range(1, self.max_basis_degree + 1):
                basis_matrix[:, i] = X ** i
        
        elif self.basis_functions == 'hermite':
            # Hermite polynomials (good for normal distributions)
            basis_matrix = np.ones((n, self.max_basis_degree + 1))
            basis_matrix[:, 1] = X
            for i in range(2, self.max_basis_degree + 1):
                basis_matrix[:, i] = X * basis_matrix[:, i-1] - (i-1) * basis_matrix[:, i-2]
        
        else:
            raise ValueError(f"Unknown basis function type: {self.basis_functions}")
        
        return basis_matrix
    
    def _estimate_convergence(self, paths: np.ndarray, params: LSMParameters, option_type: str) -> float:
        """Estimate convergence by comparing with smaller sample."""
        if params.num_paths < 1000:
            return 0.0
        
        # Use half the paths for convergence estimate
        half_paths = paths[:params.num_paths // 2]
        half_params = LSMParameters(
            spot=params.spot, strike=params.strike, maturity=params.maturity,
            risk_free_rate=params.risk_free_rate, dividend_yield=params.dividend_yield,
            volatility=params.volatility, num_paths=params.num_paths // 2,
            num_steps=params.num_steps
        )
        
        half_price = self._lsm_algorithm(half_paths, half_params, option_type)
        full_price = self._lsm_algorithm(paths, params, option_type)
        
        return abs(full_price - half_price) / full_price if full_price > 0 else 0.0
    
    def calculate_greeks(self, 
                        params: LSMParameters,
                        option_type: str = 'call') -> Dict[str, float]:
        """
        Calculate option Greeks using finite differences.
        
        Returns:
            Dictionary containing Delta, Gamma, Theta, Vega, and Rho
        """
        base_price = self.price_option(params, option_type)
        
        greeks = {'price': base_price}
        
        # Delta and Gamma (spot price sensitivity)
        ds = params.spot * 0.01  # 1% spot move
        
        params_up = LSMParameters(
            spot=params.spot + ds, strike=params.strike, maturity=params.maturity,
            risk_free_rate=params.risk_free_rate, dividend_yield=params.dividend_yield,
            volatility=params.volatility, num_paths=params.num_paths, num_steps=params.num_steps
        )
        
        params_down = LSMParameters(
            spot=params.spot - ds, strike=params.strike, maturity=params.maturity,
            risk_free_rate=params.risk_free_rate, dividend_yield=params.dividend_yield,
            volatility=params.volatility, num_paths=params.num_paths, num_steps=params.num_steps
        )
        
        price_up = self.price_option(params_up, option_type)
        price_down = self.price_option(params_down, option_type)
        
        greeks['delta'] = (price_up - price_down) / (2 * ds)
        greeks['gamma'] = (price_up - 2 * base_price + price_down) / (ds ** 2)
        
        # Theta (time decay)
        dt = 1/365  # One day
        if params.maturity > dt:
            params_theta = LSMParameters(
                spot=params.spot, strike=params.strike, maturity=params.maturity - dt,
                risk_free_rate=params.risk_free_rate, dividend_yield=params.dividend_yield,
                volatility=params.volatility, num_paths=params.num_paths, 
                num_steps=max(1, int(params.num_steps * (params.maturity - dt) / params.maturity))
            )
            price_theta = self.price_option(params_theta, option_type)
            greeks['theta'] = price_theta - base_price  # Theta per day
        else:
            greeks['theta'] = 0.0
        
        # Vega (volatility sensitivity)
        dvol = 0.01  # 1% volatility move
        
        params_vega = LSMParameters(
            spot=params.spot, strike=params.strike, maturity=params.maturity,
            risk_free_rate=params.risk_free_rate, dividend_yield=params.dividend_yield,
            volatility=params.volatility + dvol, num_paths=params.num_paths, num_steps=params.num_steps
        )
        
        price_vega = self.price_option(params_vega, option_type)
        greeks['vega'] = (price_vega - base_price) / dvol
        
        # Rho (interest rate sensitivity)
        dr = 0.01  # 1% rate move
        
        params_rho = LSMParameters(
            spot=params.spot, strike=params.strike, maturity=params.maturity,
            risk_free_rate=params.risk_free_rate + dr, dividend_yield=params.dividend_yield,
            volatility=params.volatility, num_paths=params.num_paths, num_steps=params.num_steps
        )
        
        price_rho = self.price_option(params_rho, option_type)
        greeks['rho'] = (price_rho - base_price) / dr
        
        return greeks
    
    def get_simulation_diagnostics(self) -> Dict[str, Any]:
        """Get diagnostics from the last simulation."""
        return self.last_simulation_data
    
    def analyze_exercise_boundary(self, 
                                 params: LSMParameters,
                                 option_type: str = 'call') -> pd.DataFrame:
        """
        Analyze the optimal exercise boundary.
        
        Returns:
            DataFrame with exercise boundary analysis
        """
        # Generate paths for analysis
        paths = self._generate_paths(params)
        
        # Analyze exercise decisions at different time steps and price levels
        results = []
        
        for t_idx in range(1, params.num_steps):
            time_to_expiry = params.maturity * (params.num_steps - t_idx) / params.num_steps
            
            # Sample price levels
            current_prices = paths[:, t_idx]
            price_percentiles = np.percentile(current_prices, [10, 25, 50, 75, 90])
            
            for percentile, price_level in zip([10, 25, 50, 75, 90], price_percentiles):
                # Calculate intrinsic value
                if option_type.lower() == 'call':
                    intrinsic = max(0, price_level - params.strike)
                else:
                    intrinsic = max(0, params.strike - price_level)
                
                results.append({
                    'time_step': t_idx,
                    'time_to_expiry': time_to_expiry,
                    'price_percentile': percentile,
                    'price_level': price_level,
                    'intrinsic_value': intrinsic,
                    'moneyness': price_level / params.strike
                })
        
        return pd.DataFrame(results)

def main():
    """Example usage of the SpyderLSMModel."""
    print("="*60)
    print(" SPYDER - Least-Squares Monte Carlo Model Demonstration")
    print("="*60)
    
    # Set up model parameters
    params = LSMParameters(
        spot=450.0,
        strike=450.0,
        maturity=0.25,  # 3 months
        risk_free_rate=0.05,
        dividend_yield=0.015,
        volatility=0.20,
        num_paths=10000,
        num_steps=50
    )
    
    print("\n--- Model Parameters ---")
    print(f"  Spot: ${params.spot}, Strike: ${params.strike}")
    print(f"  Maturity: {params.maturity} years")
    print(f"  Risk-free rate: {params.risk_free_rate:.1%}")
    print(f"  Dividend yield: {params.dividend_yield:.1%}")
    print(f"  Volatility: {params.volatility:.1%}")
    print(f"  Simulation paths: {params.num_paths:,}")
    print(f"  Time steps: {params.num_steps}")
    
    # Initialize model
    model = SpyderLSMModel(basis_functions='laguerre', max_basis_degree=3, 
                          use_antithetic=True, random_seed=42)
    
    # --- 1. Price American Put Option ---
    print("\n--- Pricing American Put Option ---")
    american_put_price = model.price_option(params, 'put')
    print(f"    - American Put Price: ${american_put_price:.4f}")
    
    diagnostics = model.get_simulation_diagnostics()
    print(f"    - Calculation Time: {diagnostics['calculation_time_ms']:.1f} ms")
    print(f"    - Convergence Estimate: {diagnostics['convergence_estimate']:.2%}")
    print(f"    - Basis Functions: {diagnostics['basis_functions']}")
    print(f"    - Max Basis Degree: {diagnostics['max_basis_degree']}")
    print(f"    - Antithetic Variates: {diagnostics['use_antithetic']}")
    
    # --- 2. Calculate Greeks ---
    print("\n--- Greeks Calculation ---")
    print("    Computing Greeks (this may take a moment)...")
    greeks = model.calculate_greeks(params, 'put')
    print(f"    - Delta: {greeks['delta']:.4f}")
    print(f"    - Gamma: {greeks['gamma']:.4f}")
    print(f"    - Theta: {greeks['theta']:.4f} (per day)")
    print(f"    - Vega: {greeks['vega']:.4f}")
    print(f"    - Rho: {greeks['rho']:.4f}")
    
    # --- 3. Basis Function Comparison ---
    print("\n--- Basis Function Comparison ---")
    basis_types = ['laguerre', 'power', 'hermite']
    print("    " + "-" * 45)
    print(f"    {'Basis Type':<12} {'Put Price':<12} {'Time (ms)':<12} {'Conv Est':<8}")
    print("    " + "-" * 45)
    
    for basis in basis_types:
        test_model = SpyderLSMModel(basis_functions=basis, max_basis_degree=3, 
                                   use_antithetic=True, random_seed=42)
        
        start_time = datetime.now()
        price = test_model.price_option(params, 'put')
        end_time = datetime.now()
        
        calc_time = (end_time - start_time).total_seconds() * 1000
        conv_est = test_model.get_simulation_diagnostics()['convergence_estimate']
        
        print(f"    {basis:<12} ${price:<11.4f} {calc_time:<11.1f} {conv_est:<7.2%}")
    
    # --- 4. Path Dependency Analysis ---
    print("\n--- Path Dependency Analysis ---")
    path_counts = [1000, 5000, 10000, 20000]
    print("    " + "-" * 50)
    print(f"    {'Paths':<8} {'Put Price':<12} {'Time (ms)':<12} {'Price/Path':<12}")
    print("    " + "-" * 50)
    
    for num_paths in path_counts:
        path_params = LSMParameters(
            spot=params.spot, strike=params.strike, maturity=params.maturity,
            risk_free_rate=params.risk_free_rate, dividend_yield=params.dividend_yield,
            volatility=params.volatility, num_paths=num_paths, num_steps=params.num_steps
        )
        
        path_model = SpyderLSMModel(basis_functions='laguerre', max_basis_degree=3, 
                                   use_antithetic=True, random_seed=42)
        
        start_time = datetime.now()
        price = path_model.price_option(path_params, 'put')
        end_time = datetime.now()
        
        calc_time = (end_time - start_time).total_seconds() * 1000
        price_per_path = price / num_paths * 1000
        
        print(f"    {num_paths:<8,} ${price:<11.4f} {calc_time:<11.1f} {price_per_path:<11.6f}")
    
    # --- 5. Exercise Boundary Analysis ---
    print("\n--- Exercise Boundary Analysis ---")
    print("    Analyzing optimal exercise boundary...")
    
    boundary_analysis = model.analyze_exercise_boundary(params, 'put')
    
    # Show sample results
    sample_results = boundary_analysis[boundary_analysis['price_percentile'] == 50].head(5)
    print("    Sample results (50th percentile prices):")
    print("    " + "-" * 65)
    print(f"    {'Time Step':<10} {'Time Left':<10} {'Price':<10} {'Moneyness':<10} {'Intrinsic':<10}")
    print("    " + "-" * 65)
    
    for _, row in sample_results.iterrows():
        print(f"    {row['time_step']:<10.0f} {row['time_to_expiry']:<10.3f} "
              f"${row['price_level']:<9.2f} {row['moneyness']:<10.3f} ${row['intrinsic_value']:<9.4f}")
    
    # --- 6. Performance Summary ---
    print("\n--- Performance Summary ---")
    total_calculations = len(basis_types) * 1 + len(path_counts) * 1 + 5  # Greeks calculation
    avg_time = diagnostics['calculation_time_ms']
    
    print(f"    - Average calculation time: {avg_time:.1f} ms")
    print(f"    - Estimated accuracy: ±{diagnostics['convergence_estimate']:.2%}")
    print(f"    - Memory efficiency: {params.num_paths * params.num_steps * 8 / 1024 / 1024:.1f} MB")
    print(f"    - Suitable for: Real-time pricing, risk management, strategy backtesting")
    
    print("="*60)

if __name__ == "__main__":
    main()

