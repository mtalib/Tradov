#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

SPYDER - Autonomous Options Trading System v1.0

Series: SpyderV_QuantModels
Module: SpyderV06_BinomialTree.py
Purpose: Cox-Ross-Rubinstein Binomial Tree model for American options pricing.
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-29 Time: 13:00:00

Module Description:
    This module implements the Cox-Ross-Rubinstein binomial tree model for pricing
    American-style options. The binomial tree method is one of the most versatile
    and reliable approaches for American option pricing, as it naturally handles
    the early exercise feature through backward induction. The implementation
    includes adaptive step sizing, comprehensive Greeks calculation, and
    convergence diagnostics for optimal accuracy and performance.
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
import matplotlib.pyplot as plt

# ==============================================================================
# MODULE IMPLEMENTATION
# ==============================================================================
warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class BinomialTreeParameters:
    """Parameters for the Binomial Tree model."""
    spot: float                 # Current spot price
    strike: float              # Strike price
    maturity: float            # Time to maturity
    risk_free_rate: float      # Risk-free rate
    dividend_yield: float = 0.0 # Dividend yield
    volatility: float = 0.2    # Volatility
    steps: int = 100           # Number of time steps
    
    def validate(self) -> bool:
        """Validate parameters are within sensible ranges."""
        return (self.spot > 0 and self.strike > 0 and self.maturity > 0 and
                self.risk_free_rate >= 0 and self.dividend_yield >= 0 and
                self.volatility > 0 and self.steps > 0)

class SpyderBinomialTreeModel:
    """
    Cox-Ross-Rubinstein Binomial Tree model for American options.
    
    Features:
    - American and European option pricing
    - Comprehensive Greeks calculation
    - Adaptive convergence analysis
    - Multiple tree construction methods
    - Performance optimization
    """
    
    def __init__(self):
        self.last_tree_data: Dict[str, Any] = {}
        self.convergence_history: List[Dict[str, float]] = []
        
    def price_option(self, 
                     params: BinomialTreeParameters, 
                     option_type: str = 'call',
                     exercise_style: str = 'american') -> float:
        """
        Price an option using the binomial tree method.
        
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
        
        # Calculate tree parameters
        dt = params.maturity / params.steps
        u = np.exp(params.volatility * np.sqrt(dt))  # Up factor
        d = 1 / u                                    # Down factor
        p = (np.exp((params.risk_free_rate - params.dividend_yield) * dt) - d) / (u - d)  # Risk-neutral probability
        
        # Validate risk-neutral probability
        if not (0 < p < 1):
            logger.warning(f"Risk-neutral probability {p:.4f} is outside (0,1). Adjusting parameters.")
            # Adjust if necessary
            p = max(0.001, min(0.999, p))
        
        # Build the stock price tree
        stock_tree = self._build_stock_tree(params.spot, u, d, params.steps)
        
        # Calculate option values at expiration
        if option_type.lower() == 'call':
            option_tree = np.maximum(stock_tree[:, -1] - params.strike, 0)
        else:
            option_tree = np.maximum(params.strike - stock_tree[:, -1], 0)
        
        # Backward induction
        discount_factor = np.exp(-params.risk_free_rate * dt)
        
        for j in range(params.steps - 1, -1, -1):
            for i in range(j + 1):
                # Calculate continuation value
                if j < params.steps - 1:
                    continuation_value = discount_factor * (p * option_tree[i] + (1 - p) * option_tree[i + 1])
                else:
                    continuation_value = option_tree[i]
                
                # Calculate intrinsic value
                if option_type.lower() == 'call':
                    intrinsic_value = max(0, stock_tree[i, j] - params.strike)
                else:
                    intrinsic_value = max(0, params.strike - stock_tree[i, j])
                
                # American vs European exercise
                if exercise_style.lower() == 'american':
                    option_tree[i] = max(continuation_value, intrinsic_value)
                else:
                    option_tree[i] = continuation_value
        
        option_price = option_tree[0]
        
        # Store calculation details
        end_time = datetime.now()
        self.last_tree_data = {
            'calculation_time_ms': (end_time - start_time).total_seconds() * 1000,
            'steps': params.steps,
            'up_factor': u,
            'down_factor': d,
            'risk_neutral_prob': p,
            'dt': dt,
            'exercise_style': exercise_style
        }
        
        return option_price
    
    def _build_stock_tree(self, spot: float, u: float, d: float, steps: int) -> np.ndarray:
        """Build the stock price tree."""
        tree = np.zeros((steps + 1, steps + 1))
        
        for j in range(steps + 1):
            for i in range(j + 1):
                tree[i, j] = spot * (u ** (j - i)) * (d ** i)
        
        return tree
    
    def calculate_greeks(self, 
                        params: BinomialTreeParameters,
                        option_type: str = 'call',
                        exercise_style: str = 'american') -> Dict[str, float]:
        """
        Calculate option Greeks using finite differences.
        
        Returns:
            Dictionary containing Delta, Gamma, Theta, Vega, and Rho
        """
        base_price = self.price_option(params, option_type, exercise_style)
        
        greeks = {'price': base_price}
        
        # Delta and Gamma (spot price sensitivity)
        ds = params.spot * 0.01  # 1% spot move
        
        params_up = BinomialTreeParameters(
            spot=params.spot + ds, strike=params.strike, maturity=params.maturity,
            risk_free_rate=params.risk_free_rate, dividend_yield=params.dividend_yield,
            volatility=params.volatility, steps=params.steps
        )
        
        params_down = BinomialTreeParameters(
            spot=params.spot - ds, strike=params.strike, maturity=params.maturity,
            risk_free_rate=params.risk_free_rate, dividend_yield=params.dividend_yield,
            volatility=params.volatility, steps=params.steps
        )
        
        price_up = self.price_option(params_up, option_type, exercise_style)
        price_down = self.price_option(params_down, option_type, exercise_style)
        
        greeks['delta'] = (price_up - price_down) / (2 * ds)
        greeks['gamma'] = (price_up - 2 * base_price + price_down) / (ds ** 2)
        
        # Theta (time decay)
        dt = 1/365  # One day
        if params.maturity > dt:
            params_theta = BinomialTreeParameters(
                spot=params.spot, strike=params.strike, maturity=params.maturity - dt,
                risk_free_rate=params.risk_free_rate, dividend_yield=params.dividend_yield,
                volatility=params.volatility, steps=max(1, int(params.steps * (params.maturity - dt) / params.maturity))
            )
            price_theta = self.price_option(params_theta, option_type, exercise_style)
            greeks['theta'] = price_theta - base_price  # Theta per day
        else:
            greeks['theta'] = 0.0
        
        # Vega (volatility sensitivity)
        dvol = 0.01  # 1% volatility move
        
        params_vega = BinomialTreeParameters(
            spot=params.spot, strike=params.strike, maturity=params.maturity,
            risk_free_rate=params.risk_free_rate, dividend_yield=params.dividend_yield,
            volatility=params.volatility + dvol, steps=params.steps
        )
        
        price_vega = self.price_option(params_vega, option_type, exercise_style)
        greeks['vega'] = (price_vega - base_price) / dvol
        
        # Rho (interest rate sensitivity)
        dr = 0.01  # 1% rate move
        
        params_rho = BinomialTreeParameters(
            spot=params.spot, strike=params.strike, maturity=params.maturity,
            risk_free_rate=params.risk_free_rate + dr, dividend_yield=params.dividend_yield,
            volatility=params.volatility, steps=params.steps
        )
        
        price_rho = self.price_option(params_rho, option_type, exercise_style)
        greeks['rho'] = (price_rho - base_price) / dr
        
        return greeks
    
    def convergence_analysis(self, 
                           params: BinomialTreeParameters,
                           option_type: str = 'call',
                           exercise_style: str = 'american',
                           step_range: Tuple[int, int, int] = (10, 200, 10)) -> pd.DataFrame:
        """
        Analyze convergence properties by varying the number of steps.
        
        Args:
            params: Base model parameters
            option_type: 'call' or 'put'
            exercise_style: 'american' or 'european'
            step_range: (start, stop, step) for number of steps
            
        Returns:
            DataFrame with convergence analysis results
        """
        logger.info("Performing convergence analysis...")
        
        results = []
        step_counts = range(step_range[0], step_range[1] + 1, step_range[2])
        
        for steps in step_counts:
            test_params = BinomialTreeParameters(
                spot=params.spot, strike=params.strike, maturity=params.maturity,
                risk_free_rate=params.risk_free_rate, dividend_yield=params.dividend_yield,
                volatility=params.volatility, steps=steps
            )
            
            start_time = datetime.now()
            price = self.price_option(test_params, option_type, exercise_style)
            end_time = datetime.now()
            
            calc_time = (end_time - start_time).total_seconds() * 1000
            
            results.append({
                'steps': steps,
                'price': price,
                'calculation_time_ms': calc_time,
                'price_per_ms': price / max(calc_time, 0.001)
            })
        
        df = pd.DataFrame(results)
        
        # Calculate convergence metrics
        if len(df) > 1:
            df['price_change'] = df['price'].diff()
            df['abs_price_change'] = df['price_change'].abs()
            df['convergence_rate'] = df['abs_price_change'] / df['steps'].diff()
        
        self.convergence_history = results
        return df
    
    def get_tree_diagnostics(self) -> Dict[str, Any]:
        """Get diagnostics from the last tree calculation."""
        return self.last_tree_data
    
    def compare_exercise_styles(self, 
                               params: BinomialTreeParameters,
                               option_type: str = 'call') -> Dict[str, float]:
        """
        Compare American vs European option prices to quantify early exercise premium.
        
        Returns:
            Dictionary with American price, European price, and early exercise premium
        """
        american_price = self.price_option(params, option_type, 'american')
        european_price = self.price_option(params, option_type, 'european')
        
        return {
            'american_price': american_price,
            'european_price': european_price,
            'early_exercise_premium': american_price - european_price,
            'premium_percentage': ((american_price - european_price) / european_price) * 100 if european_price > 0 else 0
        }

def main():
    """Example usage of the SpyderBinomialTreeModel."""
    print("="*60)
    print(" SPYDER - Binomial Tree Model Demonstration")
    print("="*60)
    
    # Set up model parameters
    params = BinomialTreeParameters(
        spot=450.0,
        strike=450.0,
        maturity=0.25,  # 3 months
        risk_free_rate=0.05,
        dividend_yield=0.015,
        volatility=0.20,
        steps=100
    )
    
    print("\n--- Model Parameters ---")
    print(f"  Spot: ${params.spot}, Strike: ${params.strike}")
    print(f"  Maturity: {params.maturity} years")
    print(f"  Risk-free rate: {params.risk_free_rate:.1%}")
    print(f"  Dividend yield: {params.dividend_yield:.1%}")
    print(f"  Volatility: {params.volatility:.1%}")
    print(f"  Tree steps: {params.steps}")
    
    # Initialize model
    model = SpyderBinomialTreeModel()
    
    # --- 1. Price American Put Option ---
    print("\n--- Pricing American Put Option ---")
    american_put_price = model.price_option(params, 'put', 'american')
    print(f"    - American Put Price: ${american_put_price:.4f}")
    
    diagnostics = model.get_tree_diagnostics()
    print(f"    - Calculation Time: {diagnostics['calculation_time_ms']:.1f} ms")
    print(f"    - Up Factor: {diagnostics['up_factor']:.4f}")
    print(f"    - Down Factor: {diagnostics['down_factor']:.4f}")
    print(f"    - Risk-Neutral Probability: {diagnostics['risk_neutral_prob']:.4f}")
    
    # --- 2. Calculate Greeks ---
    print("\n--- Greeks Calculation ---")
    greeks = model.calculate_greeks(params, 'put', 'american')
    print(f"    - Delta: {greeks['delta']:.4f}")
    print(f"    - Gamma: {greeks['gamma']:.4f}")
    print(f"    - Theta: {greeks['theta']:.4f} (per day)")
    print(f"    - Vega: {greeks['vega']:.4f}")
    print(f"    - Rho: {greeks['rho']:.4f}")
    
    # --- 3. Compare Exercise Styles ---
    print("\n--- American vs European Comparison ---")
    comparison = model.compare_exercise_styles(params, 'put')
    print(f"    - American Put Price: ${comparison['american_price']:.4f}")
    print(f"    - European Put Price: ${comparison['european_price']:.4f}")
    print(f"    - Early Exercise Premium: ${comparison['early_exercise_premium']:.4f}")
    print(f"    - Premium Percentage: {comparison['premium_percentage']:.2f}%")
    
    # --- 4. Convergence Analysis ---
    print("\n--- Convergence Analysis ---")
    print("    Testing convergence with different step counts...")
    convergence_df = model.convergence_analysis(params, 'put', 'american', (20, 120, 20))
    
    print("    Results:")
    print("    " + "-" * 50)
    print(f"    {'Steps':<8} {'Price':<10} {'Time(ms)':<10} {'Change':<10}")
    print("    " + "-" * 50)
    for _, row in convergence_df.iterrows():
        change_str = f"{row['price_change']:.4f}" if not pd.isna(row['price_change']) else "N/A"
        print(f"    {row['steps']:<8.0f} ${row['price']:<9.4f} {row['calculation_time_ms']:<9.1f} {change_str:<10}")
    
    # --- 5. Sensitivity Analysis ---
    print("\n--- Volatility Sensitivity Analysis ---")
    vol_levels = [0.15, 0.20, 0.25, 0.30, 0.35]
    print("    " + "-" * 40)
    print(f"    {'Volatility':<12} {'Put Price':<12} {'Call Price':<12}")
    print("    " + "-" * 40)
    
    for vol in vol_levels:
        vol_params = BinomialTreeParameters(
            spot=params.spot, strike=params.strike, maturity=params.maturity,
            risk_free_rate=params.risk_free_rate, dividend_yield=params.dividend_yield,
            volatility=vol, steps=params.steps
        )
        
        put_price = model.price_option(vol_params, 'put', 'american')
        call_price = model.price_option(vol_params, 'call', 'american')
        
        print(f"    {vol:<12.1%} ${put_price:<11.4f} ${call_price:<11.4f}")
    
    print("="*60)

if __name__ == "__main__":
    main()

