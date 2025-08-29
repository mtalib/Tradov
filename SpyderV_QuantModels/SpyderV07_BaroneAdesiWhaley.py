#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

SPYDER - Autonomous Options Trading System v1.0

Series: SpyderV_QuantModels
Module: SpyderV07_BaroneAdesiWhaley.py
Purpose: Barone-Adesi-Whaley approximation for American options pricing.
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-29 Time: 13:15:00

Module Description:
    This module implements the Barone-Adesi and Whaley (1987) quadratic
    approximation for American option pricing. This method provides a fast,
    analytical approximation that is particularly valuable for real-time
    trading applications where speed is crucial. The approximation decomposes
    the American option value into the European option value plus an early
    exercise premium, making it highly efficient for risk management and
    high-frequency trading scenarios.
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
from scipy.optimize import brentq, newton
import matplotlib.pyplot as plt

# ==============================================================================
# MODULE IMPLEMENTATION
# ==============================================================================
warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class BAWParameters:
    """Parameters for the Barone-Adesi-Whaley model."""
    spot: float                 # Current spot price
    strike: float              # Strike price
    maturity: float            # Time to maturity
    risk_free_rate: float      # Risk-free rate
    dividend_yield: float = 0.0 # Dividend yield
    volatility: float = 0.2    # Volatility
    
    def validate(self) -> bool:
        """Validate parameters are within sensible ranges."""
        return (self.spot > 0 and self.strike > 0 and self.maturity > 0 and
                self.risk_free_rate >= 0 and self.dividend_yield >= 0 and
                self.volatility > 0)

class SpyderBAWModel:
    """
    Barone-Adesi-Whaley approximation for American options.
    
    Features:
    - Fast analytical approximation for American options
    - Automatic fallback to European pricing when appropriate
    - Comprehensive Greeks calculation
    - Critical price boundary calculation
    - Performance diagnostics and validation
    """
    
    def __init__(self, max_iterations: int = 100, tolerance: float = 1e-6):
        self.max_iterations = max_iterations
        self.tolerance = tolerance
        self.last_calculation_data: Dict[str, Any] = {}
        
    def price_option(self, 
                     params: BAWParameters, 
                     option_type: str = 'call') -> float:
        """
        Price an American option using the BAW approximation.
        
        Args:
            params: Model parameters
            option_type: 'call' or 'put'
            
        Returns:
            American option price
        """
        if not params.validate():
            raise ValueError("Invalid parameters provided")
            
        start_time = datetime.now()
        
        # Calculate European option price first
        european_price = self._black_scholes_price(params, option_type)
        
        # Check if early exercise is never optimal
        if not self._is_early_exercise_possible(params, option_type):
            end_time = datetime.now()
            self.last_calculation_data = {
                'calculation_time_ms': (end_time - start_time).total_seconds() * 1000,
                'method_used': 'european_equivalent',
                'early_exercise_optimal': False,
                'critical_price': None,
                'iterations': 0
            }
            return european_price
        
        # Calculate American option price using BAW approximation
        try:
            if option_type.lower() == 'call':
                american_price, critical_price, iterations = self._baw_call(params)
            else:
                american_price, critical_price, iterations = self._baw_put(params)
            
            # Ensure American price is at least as valuable as European
            american_price = max(american_price, european_price)
            
            end_time = datetime.now()
            self.last_calculation_data = {
                'calculation_time_ms': (end_time - start_time).total_seconds() * 1000,
                'method_used': 'baw_approximation',
                'early_exercise_optimal': True,
                'critical_price': critical_price,
                'iterations': iterations,
                'european_price': european_price,
                'early_exercise_premium': american_price - european_price
            }
            
            return american_price
            
        except Exception as e:
            logger.warning(f"BAW approximation failed: {e}. Falling back to European pricing.")
            end_time = datetime.now()
            self.last_calculation_data = {
                'calculation_time_ms': (end_time - start_time).total_seconds() * 1000,
                'method_used': 'european_fallback',
                'early_exercise_optimal': False,
                'critical_price': None,
                'iterations': 0,
                'error': str(e)
            }
            return european_price
    
    def _black_scholes_price(self, params: BAWParameters, option_type: str) -> float:
        """Calculate European option price using Black-Scholes formula."""
        S, K, T, r, q, sigma = (params.spot, params.strike, params.maturity,
                               params.risk_free_rate, params.dividend_yield, params.volatility)
        
        d1 = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        
        if option_type.lower() == 'call':
            price = S * np.exp(-q * T) * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        else:
            price = K * np.exp(-r * T) * norm.cdf(-d2) - S * np.exp(-q * T) * norm.cdf(-d1)
        
        return price
    
    def _is_early_exercise_possible(self, params: BAWParameters, option_type: str) -> bool:
        """Check if early exercise can ever be optimal."""
        if option_type.lower() == 'call':
            # American call on dividend-paying stock
            return params.dividend_yield > 0
        else:
            # American put is always potentially exercisable early
            return True
    
    def _baw_call(self, params: BAWParameters) -> Tuple[float, float, int]:
        """Calculate American call price using BAW approximation."""
        S, K, T, r, q, sigma = (params.spot, params.strike, params.maturity,
                               params.risk_free_rate, params.dividend_yield, params.volatility)
        
        # Calculate auxiliary parameters
        b = r - q  # Cost of carry
        
        # Calculate beta and other parameters
        beta = (0.5 - b / sigma**2) + np.sqrt((b / sigma**2 - 0.5)**2 + 2 * r / sigma**2)
        B_infinity = beta / (beta - 1) * K
        B0 = max(K, r / (r - b) * K)
        
        # Calculate critical stock price
        h = -(b * T + 2 * sigma * np.sqrt(T)) * K / (B0 - K)
        seed = B0 + (B_infinity - B0) * (1 - np.exp(h))
        
        try:
            # Use Newton's method to find critical price
            critical_price = newton(self._call_critical_price_equation, seed, 
                                  args=(params,), maxiter=self.max_iterations, tol=self.tolerance)
            iterations = self.max_iterations  # Approximation for Newton iterations
        except:
            # Fallback to Brent's method
            try:
                critical_price = brentq(self._call_critical_price_equation, K, 5*K, args=(params,))
                iterations = self.max_iterations
            except:
                raise ValueError("Could not find critical stock price")
        
        if S >= critical_price:
            # Exercise immediately
            american_price = S - K
        else:
            # Calculate BAW approximation
            european_price = self._black_scholes_price(params, 'call')
            
            # Calculate A2 coefficient
            d1 = (np.log(critical_price / K) + (b + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
            A2 = (1 - np.exp(-q * T) * norm.cdf(d1)) * critical_price / beta
            
            american_price = european_price + A2 * (S / critical_price)**beta
        
        return american_price, critical_price, iterations
    
    def _baw_put(self, params: BAWParameters) -> Tuple[float, float, int]:
        """Calculate American put price using BAW approximation."""
        S, K, T, r, q, sigma = (params.spot, params.strike, params.maturity,
                               params.risk_free_rate, params.dividend_yield, params.volatility)
        
        # Calculate auxiliary parameters
        b = r - q  # Cost of carry
        
        # Calculate alpha and other parameters
        alpha = (0.5 - b / sigma**2) - np.sqrt((b / sigma**2 - 0.5)**2 + 2 * r / sigma**2)
        B_infinity = alpha / (alpha - 1) * K
        B0 = min(K, r / (r - b) * K)
        
        # Calculate critical stock price
        h = (b * T - 2 * sigma * np.sqrt(T)) * K / (B0 - K)
        seed = B0 - (B0 - B_infinity) * (1 - np.exp(h))
        
        try:
            # Use Newton's method to find critical price
            critical_price = newton(self._put_critical_price_equation, seed,
                                  args=(params,), maxiter=self.max_iterations, tol=self.tolerance)
            iterations = self.max_iterations
        except:
            # Fallback to Brent's method
            try:
                critical_price = brentq(self._put_critical_price_equation, 0.01*K, K, args=(params,))
                iterations = self.max_iterations
            except:
                raise ValueError("Could not find critical stock price")
        
        if S <= critical_price:
            # Exercise immediately
            american_price = K - S
        else:
            # Calculate BAW approximation
            european_price = self._black_scholes_price(params, 'put')
            
            # Calculate A1 coefficient
            d1 = (np.log(critical_price / K) + (b + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
            A1 = -(1 - np.exp(-q * T) * norm.cdf(-d1)) * critical_price / alpha
            
            american_price = european_price + A1 * (S / critical_price)**alpha
        
        return american_price, critical_price, iterations
    
    def _call_critical_price_equation(self, S_star: float, params: BAWParameters) -> float:
        """Equation to solve for critical stock price for calls."""
        K, T, r, q, sigma = params.strike, params.maturity, params.risk_free_rate, params.dividend_yield, params.volatility
        
        b = r - q
        beta = (0.5 - b / sigma**2) + np.sqrt((b / sigma**2 - 0.5)**2 + 2 * r / sigma**2)
        
        d1 = (np.log(S_star / K) + (b + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        
        lhs = S_star - K
        rhs = (self._black_scholes_price(
            BAWParameters(S_star, K, T, r, q, sigma), 'call') + 
               (1 - np.exp(-q * T) * norm.cdf(d1)) * S_star / beta)
        
        return lhs - rhs
    
    def _put_critical_price_equation(self, S_star: float, params: BAWParameters) -> float:
        """Equation to solve for critical stock price for puts."""
        K, T, r, q, sigma = params.strike, params.maturity, params.risk_free_rate, params.dividend_yield, params.volatility
        
        b = r - q
        alpha = (0.5 - b / sigma**2) - np.sqrt((b / sigma**2 - 0.5)**2 + 2 * r / sigma**2)
        
        d1 = (np.log(S_star / K) + (b + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        
        lhs = K - S_star
        rhs = (self._black_scholes_price(
            BAWParameters(S_star, K, T, r, q, sigma), 'put') - 
               (1 - np.exp(-q * T) * norm.cdf(-d1)) * S_star / alpha)
        
        return lhs - rhs
    
    def calculate_greeks(self, 
                        params: BAWParameters,
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
        
        params_up = BAWParameters(
            spot=params.spot + ds, strike=params.strike, maturity=params.maturity,
            risk_free_rate=params.risk_free_rate, dividend_yield=params.dividend_yield,
            volatility=params.volatility
        )
        
        params_down = BAWParameters(
            spot=params.spot - ds, strike=params.strike, maturity=params.maturity,
            risk_free_rate=params.risk_free_rate, dividend_yield=params.dividend_yield,
            volatility=params.volatility
        )
        
        price_up = self.price_option(params_up, option_type)
        price_down = self.price_option(params_down, option_type)
        
        greeks['delta'] = (price_up - price_down) / (2 * ds)
        greeks['gamma'] = (price_up - 2 * base_price + price_down) / (ds ** 2)
        
        # Theta (time decay)
        dt = 1/365  # One day
        if params.maturity > dt:
            params_theta = BAWParameters(
                spot=params.spot, strike=params.strike, maturity=params.maturity - dt,
                risk_free_rate=params.risk_free_rate, dividend_yield=params.dividend_yield,
                volatility=params.volatility
            )
            price_theta = self.price_option(params_theta, option_type)
            greeks['theta'] = price_theta - base_price  # Theta per day
        else:
            greeks['theta'] = 0.0
        
        # Vega (volatility sensitivity)
        dvol = 0.01  # 1% volatility move
        
        params_vega = BAWParameters(
            spot=params.spot, strike=params.strike, maturity=params.maturity,
            risk_free_rate=params.risk_free_rate, dividend_yield=params.dividend_yield,
            volatility=params.volatility + dvol
        )
        
        price_vega = self.price_option(params_vega, option_type)
        greeks['vega'] = (price_vega - base_price) / dvol
        
        # Rho (interest rate sensitivity)
        dr = 0.01  # 1% rate move
        
        params_rho = BAWParameters(
            spot=params.spot, strike=params.strike, maturity=params.maturity,
            risk_free_rate=params.risk_free_rate + dr, dividend_yield=params.dividend_yield,
            volatility=params.volatility
        )
        
        price_rho = self.price_option(params_rho, option_type)
        greeks['rho'] = (price_rho - base_price) / dr
        
        return greeks
    
    def get_calculation_diagnostics(self) -> Dict[str, Any]:
        """Get diagnostics from the last calculation."""
        return self.last_calculation_data
    
    def compare_with_european(self, 
                             params: BAWParameters,
                             option_type: str = 'call') -> Dict[str, float]:
        """
        Compare American option price with European equivalent.
        
        Returns:
            Dictionary with comparison metrics
        """
        american_price = self.price_option(params, option_type)
        european_price = self._black_scholes_price(params, option_type)
        
        return {
            'american_price': american_price,
            'european_price': european_price,
            'early_exercise_premium': american_price - european_price,
            'premium_percentage': ((american_price - european_price) / european_price) * 100 if european_price > 0 else 0
        }

def main():
    """Example usage of the SpyderBAWModel."""
    print("="*60)
    print(" SPYDER - Barone-Adesi-Whaley Model Demonstration")
    print("="*60)
    
    # Set up model parameters
    params = BAWParameters(
        spot=450.0,
        strike=450.0,
        maturity=0.25,  # 3 months
        risk_free_rate=0.05,
        dividend_yield=0.015,
        volatility=0.20
    )
    
    print("\n--- Model Parameters ---")
    print(f"  Spot: ${params.spot}, Strike: ${params.strike}")
    print(f"  Maturity: {params.maturity} years")
    print(f"  Risk-free rate: {params.risk_free_rate:.1%}")
    print(f"  Dividend yield: {params.dividend_yield:.1%}")
    print(f"  Volatility: {params.volatility:.1%}")
    
    # Initialize model
    model = SpyderBAWModel()
    
    # --- 1. Price American Put Option ---
    print("\n--- Pricing American Put Option ---")
    american_put_price = model.price_option(params, 'put')
    print(f"    - American Put Price: ${american_put_price:.4f}")
    
    diagnostics = model.get_calculation_diagnostics()
    print(f"    - Calculation Time: {diagnostics['calculation_time_ms']:.2f} ms")
    print(f"    - Method Used: {diagnostics['method_used']}")
    print(f"    - Early Exercise Optimal: {diagnostics['early_exercise_optimal']}")
    if diagnostics['critical_price']:
        print(f"    - Critical Stock Price: ${diagnostics['critical_price']:.2f}")
        print(f"    - Iterations: {diagnostics['iterations']}")
    
    # --- 2. Calculate Greeks ---
    print("\n--- Greeks Calculation ---")
    greeks = model.calculate_greeks(params, 'put')
    print(f"    - Delta: {greeks['delta']:.4f}")
    print(f"    - Gamma: {greeks['gamma']:.4f}")
    print(f"    - Theta: {greeks['theta']:.4f} (per day)")
    print(f"    - Vega: {greeks['vega']:.4f}")
    print(f"    - Rho: {greeks['rho']:.4f}")
    
    # --- 3. Compare with European ---
    print("\n--- American vs European Comparison ---")
    comparison = model.compare_with_european(params, 'put')
    print(f"    - American Put Price: ${comparison['american_price']:.4f}")
    print(f"    - European Put Price: ${comparison['european_price']:.4f}")
    print(f"    - Early Exercise Premium: ${comparison['early_exercise_premium']:.4f}")
    print(f"    - Premium Percentage: {comparison['premium_percentage']:.2f}%")
    
    # --- 4. Moneyness Analysis ---
    print("\n--- Moneyness Analysis ---")
    strikes = [400, 425, 450, 475, 500]
    print("    " + "-" * 55)
    print(f"    {'Strike':<8} {'Moneyness':<12} {'Put Price':<12} {'Call Price':<12} {'Premium':<10}")
    print("    " + "-" * 55)
    
    for strike in strikes:
        strike_params = BAWParameters(
            spot=params.spot, strike=strike, maturity=params.maturity,
            risk_free_rate=params.risk_free_rate, dividend_yield=params.dividend_yield,
            volatility=params.volatility
        )
        
        put_price = model.price_option(strike_params, 'put')
        call_price = model.price_option(strike_params, 'call')
        
        put_comparison = model.compare_with_european(strike_params, 'put')
        premium = put_comparison['early_exercise_premium']
        
        moneyness = params.spot / strike
        
        print(f"    ${strike:<7.0f} {moneyness:<11.3f} ${put_price:<11.4f} ${call_price:<11.4f} ${premium:<9.4f}")
    
    # --- 5. Time to Expiration Analysis ---
    print("\n--- Time to Expiration Analysis ---")
    maturities = [0.083, 0.25, 0.5, 1.0]  # 1 month, 3 months, 6 months, 1 year
    print("    " + "-" * 50)
    print(f"    {'Maturity':<12} {'Put Price':<12} {'Call Price':<12} {'Premium':<12}")
    print("    " + "-" * 50)
    
    for maturity in maturities:
        maturity_params = BAWParameters(
            spot=params.spot, strike=params.strike, maturity=maturity,
            risk_free_rate=params.risk_free_rate, dividend_yield=params.dividend_yield,
            volatility=params.volatility
        )
        
        put_price = model.price_option(maturity_params, 'put')
        call_price = model.price_option(maturity_params, 'call')
        
        put_comparison = model.compare_with_european(maturity_params, 'put')
        premium = put_comparison['early_exercise_premium']
        
        maturity_str = f"{maturity:.3f}y"
        print(f"    {maturity_str:<12} ${put_price:<11.4f} ${call_price:<11.4f} ${premium:<11.4f}")
    
    # --- 6. Performance Comparison ---
    print("\n--- Performance Analysis ---")
    print("    Timing 1000 option prices...")
    
    start_time = datetime.now()
    for _ in range(1000):
        model.price_option(params, 'put')
    end_time = datetime.now()
    
    total_time = (end_time - start_time).total_seconds() * 1000
    avg_time = total_time / 1000
    
    print(f"    - Total time for 1000 prices: {total_time:.1f} ms")
    print(f"    - Average time per price: {avg_time:.3f} ms")
    print(f"    - Prices per second: {1000 / (total_time / 1000):.0f}")
    
    print("="*60)

if __name__ == "__main__":
    main()

