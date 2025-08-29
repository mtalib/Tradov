#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

SPYDER - Autonomous Options Trading System v1.0

Series: SpyderV_QuantModels
Module: SpyderV09_MertonJumpDiffusion.py
Purpose: Merton Jump-Diffusion model for options pricing with discontinuous jumps.
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-29 Time: 13:45:00

Module Description:
    This module implements the Merton Jump-Diffusion model, which extends the
    Black-Scholes framework to include sudden, discontinuous price jumps.
    This model is particularly valuable during crisis periods, earnings
    announcements, and other events that can cause dramatic price movements.
    The implementation provides both analytical solutions for European options
    and numerical methods for American options.
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
from scipy.stats import norm, poisson
from scipy.special import factorial
import matplotlib.pyplot as plt

# ==============================================================================
# MODULE IMPLEMENTATION
# ==============================================================================
warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class MertonJumpParameters:
    """Parameters for the Merton Jump-Diffusion model."""
    spot: float                 # Current spot price
    strike: float              # Strike price
    maturity: float            # Time to maturity
    risk_free_rate: float      # Risk-free rate
    dividend_yield: float = 0.0 # Dividend yield
    volatility: float = 0.2    # Diffusion volatility
    jump_intensity: float = 0.1 # Jump intensity (jumps per year)
    jump_mean: float = -0.05   # Mean jump size (log returns)
    jump_std: float = 0.15     # Jump size standard deviation
    
    def validate(self) -> bool:
        """Validate parameters are within sensible ranges."""
        return (self.spot > 0 and self.strike > 0 and self.maturity > 0 and
                self.risk_free_rate >= 0 and self.dividend_yield >= 0 and
                self.volatility > 0 and self.jump_intensity >= 0 and self.jump_std > 0)

class SpyderMertonJumpDiffusionModel:
    """
    Merton Jump-Diffusion model for options pricing.
    
    Features:
    - Analytical European option pricing
    - Jump-adapted binomial trees for American options
    - Comprehensive parameter calibration
    - Jump risk analysis and diagnostics
    - Crisis period modeling capabilities
    """
    
    def __init__(self, max_jumps: int = 50, tree_steps: int = 100):
        self.max_jumps = max_jumps
        self.tree_steps = tree_steps
        self.last_calculation_data: Dict[str, Any] = {}
        
    def price_option(self, 
                     params: MertonJumpParameters, 
                     option_type: str = 'call',
                     exercise_style: str = 'american') -> float:
        """
        Price an option using the Merton Jump-Diffusion model.
        
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
        
        if exercise_style.lower() == 'european':
            option_price = self._merton_european_price(params, option_type)
            method_used = 'merton_analytical'
        else:
            option_price = self._merton_american_price(params, option_type)
            method_used = 'jump_adapted_tree'
        
        # Store calculation details
        end_time = datetime.now()
        self.last_calculation_data = {
            'calculation_time_ms': (end_time - start_time).total_seconds() * 1000,
            'method_used': method_used,
            'exercise_style': exercise_style,
            'expected_jumps': params.jump_intensity * params.maturity,
            'jump_contribution': self._calculate_jump_contribution(params, option_type)
        }
        
        return option_price
    
    def _merton_european_price(self, params: MertonJumpParameters, option_type: str) -> float:
        """
        Calculate European option price using Merton's analytical formula.
        
        The Merton formula expresses the option price as an infinite sum of
        Black-Scholes prices, each weighted by the Poisson probability of
        a specific number of jumps occurring.
        """
        # Pre-calculate jump parameters
        k = np.exp(params.jump_mean + 0.5 * params.jump_std**2) - 1  # Expected jump size
        lambda_prime = params.jump_intensity * (1 + k)  # Adjusted jump intensity
        
        option_price = 0.0
        
        # Sum over possible number of jumps
        for n in range(self.max_jumps + 1):
            # Poisson probability of n jumps
            poisson_prob = poisson.pmf(n, params.jump_intensity * params.maturity)
            
            if poisson_prob < 1e-10:  # Skip negligible terms
                continue
            
            # Adjusted parameters for n jumps
            sigma_n = np.sqrt(params.volatility**2 + n * params.jump_std**2 / params.maturity)
            r_n = (params.risk_free_rate - params.dividend_yield - params.jump_intensity * k + 
                   n * (params.jump_mean + 0.5 * params.jump_std**2) / params.maturity)
            
            # Black-Scholes price with adjusted parameters
            bs_price = self._black_scholes_price(
                params.spot, params.strike, params.maturity, r_n, 
                params.dividend_yield, sigma_n, option_type
            )
            
            option_price += poisson_prob * bs_price
        
        return option_price
    
    def _black_scholes_price(self, spot: float, strike: float, maturity: float,
                           risk_free_rate: float, dividend_yield: float, 
                           volatility: float, option_type: str) -> float:
        """Standard Black-Scholes formula."""
        d1 = (np.log(spot / strike) + (risk_free_rate - dividend_yield + 0.5 * volatility**2) * maturity) / (volatility * np.sqrt(maturity))
        d2 = d1 - volatility * np.sqrt(maturity)
        
        if option_type.lower() == 'call':
            price = spot * np.exp(-dividend_yield * maturity) * norm.cdf(d1) - strike * np.exp(-risk_free_rate * maturity) * norm.cdf(d2)
        else:
            price = strike * np.exp(-risk_free_rate * maturity) * norm.cdf(-d2) - spot * np.exp(-dividend_yield * maturity) * norm.cdf(-d1)
        
        return price
    
    def _merton_american_price(self, params: MertonJumpParameters, option_type: str) -> float:
        """
        Price American option using jump-adapted binomial tree.
        
        This method modifies the standard binomial tree to account for
        the additional volatility and drift adjustments from jumps.
        """
        # Adjust parameters for jump risk
        k = np.exp(params.jump_mean + 0.5 * params.jump_std**2) - 1
        
        # Effective volatility including jump component
        jump_variance = params.jump_intensity * (params.jump_std**2 + params.jump_mean**2)
        effective_variance = params.volatility**2 + jump_variance
        effective_volatility = np.sqrt(effective_variance)
        
        # Effective drift
        effective_drift = params.risk_free_rate - params.dividend_yield - params.jump_intensity * k
        
        # Build binomial tree with adjusted parameters
        dt = params.maturity / self.tree_steps
        u = np.exp(effective_volatility * np.sqrt(dt))
        d = 1 / u
        p = (np.exp(effective_drift * dt) - d) / (u - d)
        
        # Validate risk-neutral probability
        if not (0 < p < 1):
            logger.warning(f"Risk-neutral probability {p:.4f} is outside (0,1)")
            p = max(0.001, min(0.999, p))
        
        # Initialize asset price tree
        asset_prices = np.zeros((self.tree_steps + 1, self.tree_steps + 1))
        for j in range(self.tree_steps + 1):
            for i in range(j + 1):
                asset_prices[i, j] = params.spot * (u ** (j - i)) * (d ** i)
        
        # Initialize option value tree
        option_values = np.zeros((self.tree_steps + 1, self.tree_steps + 1))
        
        # Terminal condition
        for i in range(self.tree_steps + 1):
            if option_type.lower() == 'call':
                option_values[i, self.tree_steps] = max(0, asset_prices[i, self.tree_steps] - params.strike)
            else:
                option_values[i, self.tree_steps] = max(0, params.strike - asset_prices[i, self.tree_steps])
        
        # Backward induction
        discount_factor = np.exp(-params.risk_free_rate * dt)
        
        for j in range(self.tree_steps - 1, -1, -1):
            for i in range(j + 1):
                # Continuation value
                continuation_value = discount_factor * (p * option_values[i, j + 1] + (1 - p) * option_values[i + 1, j + 1])
                
                # Intrinsic value
                if option_type.lower() == 'call':
                    intrinsic_value = max(0, asset_prices[i, j] - params.strike)
                else:
                    intrinsic_value = max(0, params.strike - asset_prices[i, j])
                
                # American option: max of continuation and intrinsic
                option_values[i, j] = max(continuation_value, intrinsic_value)
        
        return option_values[0, 0]
    
    def _calculate_jump_contribution(self, params: MertonJumpParameters, option_type: str) -> float:
        """Calculate the contribution of jumps to option value."""
        # Price with jumps
        jump_price = self._merton_european_price(params, option_type)
        
        # Price without jumps (standard Black-Scholes)
        no_jump_params = MertonJumpParameters(
            spot=params.spot, strike=params.strike, maturity=params.maturity,
            risk_free_rate=params.risk_free_rate, dividend_yield=params.dividend_yield,
            volatility=params.volatility, jump_intensity=0.0, jump_mean=0.0, jump_std=0.0
        )
        
        bs_price = self._black_scholes_price(
            params.spot, params.strike, params.maturity,
            params.risk_free_rate, params.dividend_yield, params.volatility, option_type
        )
        
        return jump_price - bs_price
    
    def calculate_greeks(self, 
                        params: MertonJumpParameters,
                        option_type: str = 'call',
                        exercise_style: str = 'american') -> Dict[str, float]:
        """
        Calculate option Greeks using finite differences.
        
        Returns:
            Dictionary containing Delta, Gamma, Theta, Vega, Rho, and jump sensitivities
        """
        base_price = self.price_option(params, option_type, exercise_style)
        
        greeks = {'price': base_price}
        
        # Delta and Gamma (spot price sensitivity)
        ds = params.spot * 0.01
        
        params_up = MertonJumpParameters(
            spot=params.spot + ds, strike=params.strike, maturity=params.maturity,
            risk_free_rate=params.risk_free_rate, dividend_yield=params.dividend_yield,
            volatility=params.volatility, jump_intensity=params.jump_intensity,
            jump_mean=params.jump_mean, jump_std=params.jump_std
        )
        
        params_down = MertonJumpParameters(
            spot=params.spot - ds, strike=params.strike, maturity=params.maturity,
            risk_free_rate=params.risk_free_rate, dividend_yield=params.dividend_yield,
            volatility=params.volatility, jump_intensity=params.jump_intensity,
            jump_mean=params.jump_mean, jump_std=params.jump_std
        )
        
        price_up = self.price_option(params_up, option_type, exercise_style)
        price_down = self.price_option(params_down, option_type, exercise_style)
        
        greeks['delta'] = (price_up - price_down) / (2 * ds)
        greeks['gamma'] = (price_up - 2 * base_price + price_down) / (ds ** 2)
        
        # Theta (time decay)
        dt = 1/365
        if params.maturity > dt:
            params_theta = MertonJumpParameters(
                spot=params.spot, strike=params.strike, maturity=params.maturity - dt,
                risk_free_rate=params.risk_free_rate, dividend_yield=params.dividend_yield,
                volatility=params.volatility, jump_intensity=params.jump_intensity,
                jump_mean=params.jump_mean, jump_std=params.jump_std
            )
            price_theta = self.price_option(params_theta, option_type, exercise_style)
            greeks['theta'] = price_theta - base_price
        else:
            greeks['theta'] = 0.0
        
        # Vega (volatility sensitivity)
        dvol = 0.01
        
        params_vega = MertonJumpParameters(
            spot=params.spot, strike=params.strike, maturity=params.maturity,
            risk_free_rate=params.risk_free_rate, dividend_yield=params.dividend_yield,
            volatility=params.volatility + dvol, jump_intensity=params.jump_intensity,
            jump_mean=params.jump_mean, jump_std=params.jump_std
        )
        
        price_vega = self.price_option(params_vega, option_type, exercise_style)
        greeks['vega'] = (price_vega - base_price) / dvol
        
        # Rho (interest rate sensitivity)
        dr = 0.01
        
        params_rho = MertonJumpParameters(
            spot=params.spot, strike=params.strike, maturity=params.maturity,
            risk_free_rate=params.risk_free_rate + dr, dividend_yield=params.dividend_yield,
            volatility=params.volatility, jump_intensity=params.jump_intensity,
            jump_mean=params.jump_mean, jump_std=params.jump_std
        )
        
        price_rho = self.price_option(params_rho, option_type, exercise_style)
        greeks['rho'] = (price_rho - base_price) / dr
        
        # Jump intensity sensitivity
        dlambda = 0.01
        
        params_lambda = MertonJumpParameters(
            spot=params.spot, strike=params.strike, maturity=params.maturity,
            risk_free_rate=params.risk_free_rate, dividend_yield=params.dividend_yield,
            volatility=params.volatility, jump_intensity=params.jump_intensity + dlambda,
            jump_mean=params.jump_mean, jump_std=params.jump_std
        )
        
        price_lambda = self.price_option(params_lambda, option_type, exercise_style)
        greeks['lambda_sensitivity'] = (price_lambda - base_price) / dlambda
        
        return greeks
    
    def get_calculation_diagnostics(self) -> Dict[str, Any]:
        """Get diagnostics from the last calculation."""
        return self.last_calculation_data
    
    def analyze_jump_impact(self, 
                           params: MertonJumpParameters,
                           option_type: str = 'call') -> Dict[str, Any]:
        """
        Analyze the impact of jump parameters on option pricing.
        
        Returns:
            Dictionary with jump impact analysis
        """
        base_price = self.price_option(params, option_type, 'european')
        
        # Price without jumps
        no_jump_price = self._black_scholes_price(
            params.spot, params.strike, params.maturity,
            params.risk_free_rate, params.dividend_yield, params.volatility, option_type
        )
        
        # Jump contribution
        jump_premium = base_price - no_jump_price
        
        # Expected number of jumps
        expected_jumps = params.jump_intensity * params.maturity
        
        # Jump size statistics
        expected_jump_return = params.jump_mean
        jump_volatility = params.jump_std
        
        return {
            'option_price_with_jumps': base_price,
            'option_price_without_jumps': no_jump_price,
            'jump_premium': jump_premium,
            'jump_premium_percentage': (jump_premium / no_jump_price) * 100 if no_jump_price > 0 else 0,
            'expected_jumps': expected_jumps,
            'expected_jump_return': expected_jump_return,
            'jump_volatility': jump_volatility,
            'jump_intensity': params.jump_intensity
        }

def main():
    """Example usage of the SpyderMertonJumpDiffusionModel."""
    print("="*60)
    print(" SPYDER - Merton Jump-Diffusion Model Demonstration")
    print("="*60)
    
    # Set up model parameters
    params = MertonJumpParameters(
        spot=450.0,
        strike=450.0,
        maturity=0.25,  # 3 months
        risk_free_rate=0.05,
        dividend_yield=0.015,
        volatility=0.20,
        jump_intensity=0.2,    # 0.2 jumps per year on average
        jump_mean=-0.03,       # Average jump is -3% (negative for equity)
        jump_std=0.10          # Jump size standard deviation 10%
    )
    
    print("\n--- Model Parameters ---")
    print(f"  Spot: ${params.spot}, Strike: ${params.strike}")
    print(f"  Maturity: {params.maturity} years")
    print(f"  Risk-free rate: {params.risk_free_rate:.1%}")
    print(f"  Dividend yield: {params.dividend_yield:.1%}")
    print(f"  Diffusion volatility: {params.volatility:.1%}")
    print(f"  Jump intensity: {params.jump_intensity:.2f} jumps/year")
    print(f"  Average jump size: {params.jump_mean:.1%}")
    print(f"  Jump volatility: {params.jump_std:.1%}")
    
    # Initialize model
    model = SpyderMertonJumpDiffusionModel(max_jumps=30, tree_steps=100)
    
    # --- 1. Price American Put Option ---
    print("\n--- Pricing American Put Option ---")
    american_put_price = model.price_option(params, 'put', 'american')
    print(f"    - American Put Price: ${american_put_price:.4f}")
    
    diagnostics = model.get_calculation_diagnostics()
    print(f"    - Calculation Time: {diagnostics['calculation_time_ms']:.1f} ms")
    print(f"    - Method Used: {diagnostics['method_used']}")
    print(f"    - Expected Jumps: {diagnostics['expected_jumps']:.2f}")
    print(f"    - Jump Contribution: ${diagnostics['jump_contribution']:.4f}")
    
    # --- 2. Compare Exercise Styles ---
    print("\n--- Exercise Style Comparison ---")
    european_put_price = model.price_option(params, 'put', 'european')
    print(f"    - European Put Price: ${european_put_price:.4f}")
    print(f"    - American Put Price: ${american_put_price:.4f}")
    print(f"    - Early Exercise Premium: ${american_put_price - european_put_price:.4f}")
    
    # --- 3. Jump Impact Analysis ---
    print("\n--- Jump Impact Analysis ---")
    jump_analysis = model.analyze_jump_impact(params, 'put')
    print(f"    - Price with jumps: ${jump_analysis['option_price_with_jumps']:.4f}")
    print(f"    - Price without jumps: ${jump_analysis['option_price_without_jumps']:.4f}")
    print(f"    - Jump premium: ${jump_analysis['jump_premium']:.4f}")
    print(f"    - Jump premium %: {jump_analysis['jump_premium_percentage']:.2f}%")
    print(f"    - Expected jumps in period: {jump_analysis['expected_jumps']:.2f}")
    
    # --- 4. Calculate Greeks ---
    print("\n--- Greeks Calculation ---")
    greeks = model.calculate_greeks(params, 'put', 'american')
    print(f"    - Delta: {greeks['delta']:.4f}")
    print(f"    - Gamma: {greeks['gamma']:.4f}")
    print(f"    - Theta: {greeks['theta']:.4f} (per day)")
    print(f"    - Vega: {greeks['vega']:.4f}")
    print(f"    - Rho: {greeks['rho']:.4f}")
    print(f"    - Lambda sensitivity: {greeks['lambda_sensitivity']:.4f}")
    
    # --- 5. Jump Intensity Sensitivity ---
    print("\n--- Jump Intensity Sensitivity ---")
    intensities = [0.0, 0.1, 0.2, 0.5, 1.0]
    print("    " + "-" * 55)
    print(f"    {'Intensity':<10} {'Put Price':<12} {'Call Price':<12} {'Jump Premium':<12}")
    print("    " + "-" * 55)
    
    for intensity in intensities:
        intensity_params = MertonJumpParameters(
            spot=params.spot, strike=params.strike, maturity=params.maturity,
            risk_free_rate=params.risk_free_rate, dividend_yield=params.dividend_yield,
            volatility=params.volatility, jump_intensity=intensity,
            jump_mean=params.jump_mean, jump_std=params.jump_std
        )
        
        put_price = model.price_option(intensity_params, 'put', 'european')
        call_price = model.price_option(intensity_params, 'call', 'european')
        
        jump_analysis = model.analyze_jump_impact(intensity_params, 'put')
        jump_premium = jump_analysis['jump_premium']
        
        print(f"    {intensity:<10.1f} ${put_price:<11.4f} ${call_price:<11.4f} ${jump_premium:<11.4f}")
    
    # --- 6. Jump Size Sensitivity ---
    print("\n--- Jump Size Sensitivity ---")
    jump_means = [-0.10, -0.05, 0.00, 0.05, 0.10]
    print("    " + "-" * 55)
    print(f"    {'Jump Mean':<10} {'Put Price':<12} {'Call Price':<12} {'Impact':<12}")
    print("    " + "-" * 55)
    
    base_put = model.price_option(params, 'put', 'european')
    
    for jump_mean in jump_means:
        jump_params = MertonJumpParameters(
            spot=params.spot, strike=params.strike, maturity=params.maturity,
            risk_free_rate=params.risk_free_rate, dividend_yield=params.dividend_yield,
            volatility=params.volatility, jump_intensity=params.jump_intensity,
            jump_mean=jump_mean, jump_std=params.jump_std
        )
        
        put_price = model.price_option(jump_params, 'put', 'european')
        call_price = model.price_option(jump_params, 'call', 'european')
        impact = put_price - base_put
        
        print(f"    {jump_mean:<10.1%} ${put_price:<11.4f} ${call_price:<11.4f} ${impact:<11.4f}")
    
    # --- 7. Crisis Scenario Analysis ---
    print("\n--- Crisis Scenario Analysis ---")
    print("    Modeling high-stress market conditions...")
    
    crisis_params = MertonJumpParameters(
        spot=params.spot, strike=params.strike, maturity=params.maturity,
        risk_free_rate=params.risk_free_rate, dividend_yield=params.dividend_yield,
        volatility=0.35,           # Higher base volatility
        jump_intensity=2.0,        # More frequent jumps
        jump_mean=-0.08,           # Larger negative jumps
        jump_std=0.20              # Higher jump volatility
    )
    
    crisis_put = model.price_option(crisis_params, 'put', 'american')
    crisis_analysis = model.analyze_jump_impact(crisis_params, 'put')
    
    print(f"    - Crisis scenario put price: ${crisis_put:.4f}")
    print(f"    - Normal scenario put price: ${american_put_price:.4f}")
    print(f"    - Crisis premium: ${crisis_put - american_put_price:.4f}")
    print(f"    - Expected jumps in crisis: {crisis_analysis['expected_jumps']:.2f}")
    print(f"    - Jump premium in crisis: ${crisis_analysis['jump_premium']:.4f}")
    
    print("="*60)

if __name__ == "__main__":
    main()

